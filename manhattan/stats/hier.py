"""The hierarchical model of Protocol v3 section 7: one model for reserve and forward results.

    mechanism m:   logit(ρ̄_m) ~ Normal(μ_ρ, σ_ρ²)
    family f:      ρ_f ~ Beta(ρ̄_{m(f)} φ, (1 − ρ̄_{m(f)}) φ)
                   A_f ~ (1 − w) Normal(μ_A, τ_A²) + w Student-t_3(μ_A, s_R)
    hypothesis h:  a_h = A_f + σ_dom ε_h,  ε_h ~ Normal(0, 1)
                   θ_h = ρ_f a_h + δ_h,    δ_h ~ (1 − w) Normal(0, 0.02²) + w Student-t_3(0, s_R)
    family edge:   θ_f = ρ_f A_f
    data:          â^H ~ MVN(a, ψ_H² Σ^H),   θ̂^F ~ MVN(θ, ψ_F² Σ^F)
    reported:      Π_f = Pr(θ_f ≥ θ_min | data),  θ_min = 0.25

All hyperparameters are sampled with the No-U-Turn sampler, 4 chains. A fit is used only if ``R̂ ≤ 1.01`` for
every parameter, the effective sample size is at least 400 and there are no divergent transitions; otherwise
``converged`` is False and the caller must report "model not converged" and change no tier.

``Π_f`` is a posterior probability under this model. It is never an error rate.

The six models of section 7.2(e) differ only in the fields of ``Spec``. Under S5 (forward decay) the forward
estimate of a hypothesis observed over forward ages ``0..u`` years has mean ``θ_h`` times the average of
``2^(−t/3)`` over that record, and ``Π_f`` is about the edge at the family's current forward age.

**How the two robust mixtures are sampled.** Sampled directly, ``δ_h`` (a spike of width 0.02 beside a slab of
scale 1.5) does not mix: chains stay in the spike or in the slab and ``R̂`` is far above 1.01. The model is
therefore sampled in other coordinates, without changing it: ``δ_h = Q_δ(Φ(z_h))`` and
``A_f = μ_A + Q_A(Φ(z_f); τ_A)`` with ``z ~ Normal(0, 1)``, where ``Q`` is the quantile function of the mixture.
A variable built that way has exactly the mixture as its distribution. ``Q`` is tabulated once (by bisection on
the mixture's distribution function) and interpolated, so the priors are those of section 7.1 up to the table's
interpolation error (``TABLE_Z_STEP``); a test compares draws made through the tables with the mixtures.
Retention is treated the same way for the same reason (a funnel between ``ρ_f`` and ``φ``): the sampler moves
``z = (logit ρ_f − its prior mean) / its prior standard deviation``, with the Beta density and the Jacobian
added explicitly, which is again the Beta prior of section 7.1 in other coordinates.

Needs ``numpyro`` (requirements-manhattan.txt); imported only when a fit is made.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import partial

import numpy as np
from scipy import stats as _st
from scipy.linalg import solve_triangular

THETA_MIN = 0.25
W_ROBUST, S_ROBUST = 0.10, 1.5
DELTA_SD = 0.02
RHAT_MAX, ESS_MIN = 1.01, 400
HALF_LIFE_S5 = 3.0


@dataclass(frozen=True)
class Spec:
    name: str
    mu_rho: float = 0.35            # centre of the retention prior, on the probability scale
    w: float = W_ROBUST
    diagonal: bool = False          # S4: no cross-correlation
    psi_fixed: float | None = None  # S4: ψ_H = ψ_F = 1.5
    decay: bool = False             # S5


SPECS = (Spec("S0"), Spec("S1", mu_rho=0.15), Spec("S2", mu_rho=0.60), Spec("S3", w=0.25),
         Spec("S4", diagonal=True, psi_fixed=1.5), Spec("S5", decay=True))
PRIORS = {"mu_rho_sd": 1.0, "sigma_rho": 1.0, "phi": (2.0, 0.1), "mu_A": (0.3, 0.3), "tau_A": 0.5,
          "sigma_dom": 0.3, "psi_excess": 0.25}


TABLE_Z_MAX, TABLE_Z_STEP, TABLE_Z_STEP_A = 8.0, 0.002, 0.02
TAU_GRID = np.exp(np.linspace(math.log(1e-3), math.log(20.0), 100))
_TABLES: dict = {}


def mixture_cdf(x, sd, w: float):
    """Distribution function of ``(1 − w) Normal(0, sd²) + w Student-t_3(0, s_R)``."""
    return (1.0 - w) * _st.norm.cdf(x / sd) + w * _st.t.cdf(x / S_ROBUST, 3)


def mixture_quantile(z, sd, w: float) -> np.ndarray:
    """``Q(Φ(z))``: the mixture's quantile at the probability a standard normal gives ``z``. ``sd`` and ``z``
    broadcast. Solved by bisection on the lower half and mirrored (the mixture is symmetric)."""
    z, sd = np.broadcast_arrays(np.asarray(z, dtype=float), np.asarray(sd, dtype=float))
    target = _st.norm.cdf(-np.abs(z))
    lo, hi = np.full(z.shape, -1e9), np.zeros(z.shape)
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        below = mixture_cdf(mid, sd, w) < target
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    return np.sign(z) * -0.5 * (lo + hi)


def z_grid(step: float = TABLE_Z_STEP) -> np.ndarray:
    return np.linspace(-TABLE_Z_MAX, TABLE_Z_MAX, int(round(2 * TABLE_Z_MAX / step)) + 1)


def tables(w: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(z grid of δ, quantile table of δ, z grid of A, quantile table of ``A − μ_A`` by row of ``TAU_GRID``) for
    robust weight ``w``. δ's table is fine (its spike is narrow); A's mixture is smooth and needs fewer points."""
    if w not in _TABLES:
        z, za = z_grid(), z_grid(TABLE_Z_STEP_A)
        _TABLES[w] = (z, mixture_quantile(z, DELTA_SD, w), za, mixture_quantile(za[None, :], TAU_GRID[:, None], w))
    return _TABLES[w]


def delta_from_z(z, w: float) -> np.ndarray:
    """``δ`` for standard-normal ``z`` (NumPy version of what the sampler does)."""
    grid, qd, _, _ = tables(w)
    return np.interp(np.clip(z, -TABLE_Z_MAX, TABLE_Z_MAX), grid, qd)


def a_from_z(z, tau: float, w: float) -> np.ndarray:
    """``A − μ_A`` for standard-normal ``z`` and scale ``τ_A`` (NumPy version of what the sampler does)."""
    _, _, grid, qa = tables(w)
    pos = np.clip((math.log(tau) - math.log(TAU_GRID[0])) / (math.log(TAU_GRID[1]) - math.log(TAU_GRID[0])),
                  0, TAU_GRID.size - 1 - 1e-9)
    i = int(pos)
    row = (1 - (pos - i)) * qa[i] + (pos - i) * qa[i + 1]
    return np.interp(np.clip(z, -TABLE_Z_MAX, TABLE_Z_MAX), grid, row)


@dataclass
class Data:
    """Inputs of one fit. Hypotheses are numbered 0..n_h−1; ``fam`` maps each to its family, ``mech`` each
    family to its mechanism class. ``fwd`` lists the hypotheses that have a forward estimate."""
    a_hat: np.ndarray           # (n_h,) reserve sample Sharpe ratios (annualised)
    cov_H: np.ndarray           # (n_h, n_h)
    fam: np.ndarray             # (n_h,) family index
    mech: np.ndarray            # (n_f,) mechanism class index
    fwd: np.ndarray             # (n_fwd,) hypothesis indices with a forward estimate
    theta_hat: np.ndarray       # (n_fwd,) forward sample Sharpe ratios (annualised)
    cov_F: np.ndarray           # (n_fwd, n_fwd)
    age: np.ndarray             # (n_f,) forward age of each family in years (0 when it has no forward record)

    @property
    def n_f(self) -> int:
        return int(self.mech.size)


def decay_factors(age_years: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """S5: (average of ``2^(−t/3)`` over a record of that many years, its value at the end of the record)."""
    u = np.asarray(age_years, dtype=float)
    k = math.log(2.0) / HALF_LIFE_S5
    with np.errstate(invalid="ignore", divide="ignore"):
        avg = np.where(u > 0, (1.0 - np.exp(-k * u)) / (k * np.where(u > 0, u, 1.0)), 1.0)
    return avg, np.exp(-k * u)


def _model(d: dict, spec: Spec, n: dict):
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist
    import jax
    from jax.scipy.special import betaln, digamma, polygamma

    mu_rho = numpyro.sample("mu_rho", dist.Normal(math.log(spec.mu_rho / (1 - spec.mu_rho)), PRIORS["mu_rho_sd"]))
    sigma_rho = numpyro.sample("sigma_rho", dist.HalfNormal(PRIORS["sigma_rho"]))
    phi = numpyro.sample("phi", dist.Gamma(*PRIORS["phi"]))
    mu_A = numpyro.sample("mu_A", dist.Normal(*PRIORS["mu_A"]))
    tau_A = numpyro.sample("tau_A", dist.HalfNormal(PRIORS["tau_A"]))
    sigma_dom = numpyro.sample("sigma_dom", dist.HalfNormal(PRIORS["sigma_dom"]))
    if spec.psi_fixed is None:
        psi_H = 1.0 + numpyro.sample("psi_H_excess", dist.HalfNormal(PRIORS["psi_excess"]))
        psi_F = 1.0 + numpyro.sample("psi_F_excess", dist.HalfNormal(PRIORS["psi_excess"]))
    else:
        psi_H = psi_F = spec.psi_fixed
    z_m = numpyro.sample("z_m", dist.Normal(0.0, 1.0).expand([n["n_m"]]))
    rho_bar = jnp.clip(1.0 / (1.0 + jnp.exp(-(mu_rho + sigma_rho * z_m))), 1e-6, 1 - 1e-6)
    rb = rho_bar[d["mech"]]
    al, be = rb * phi, (1.0 - rb) * phi
    # ρ_f ~ Beta(al, be), sampled as logit ρ_f = (its prior mean) + (its prior sd) · z_rho: same distribution
    loc = digamma(al) - digamma(be)
    scale = jnp.sqrt(polygamma(1, al) + polygamma(1, be))
    z_rho = numpyro.sample("z_rho", dist.ImproperUniform(dist.constraints.real, (), (n["n_f"],)))
    x = loc + scale * z_rho
    rho = jax.nn.sigmoid(x)
    # log density of x = logit ρ under Beta(al, be): al·log σ(x) + be·log σ(−x) − log B(al, be); plus log|dx/dz|
    numpyro.factor("rho_prior", jnp.sum(al * jax.nn.log_sigmoid(x) + be * jax.nn.log_sigmoid(-x) - betaln(al, be)
                                         + jnp.log(scale)))
    numpyro.deterministic("rho", rho)
    zg, qd, zga, qa = d["zg"], d["qd"], d["zga"], d["qa"]
    z_A = numpyro.sample("z_A", dist.Normal(0.0, 1.0).expand([n["n_f"]]))
    pos = jnp.clip((jnp.log(tau_A) - d["tau0"]) / d["dtau"], 0.0, qa.shape[0] - 1 - 1e-9)
    i = jnp.floor(pos).astype(jnp.int32)
    row = (1.0 - (pos - i)) * qa[i] + (pos - i) * qa[i + 1]
    A = numpyro.deterministic("A", mu_A + jnp.interp(jnp.clip(z_A, -TABLE_Z_MAX, TABLE_Z_MAX), zga, row))
    eps = numpyro.sample("eps", dist.Normal(0.0, 1.0).expand([n["n_h"]]))
    z_delta = numpyro.sample("z_delta", dist.Normal(0.0, 1.0).expand([n["n_h"]]))
    delta = jnp.interp(jnp.clip(z_delta, -TABLE_Z_MAX, TABLE_Z_MAX), zg, qd)
    a = A[d["fam"]] + sigma_dom * eps
    theta = rho[d["fam"]] * a + delta
    numpyro.deterministic("theta_f", rho * A * d["now"])
    # Likelihood. y ~ MVN(mean, ψ² Σ) with Σ = L L' is written through the whitened residual r = L⁻¹(y − mean)/ψ:
    # log p = −½ r'r − n log ψ − log|L| − (n/2) log 2π. L⁻¹ is computed once per fit, so a gradient costs one
    # matrix-vector product instead of a triangular solve. For S4 (diagonal) L⁻¹ is diagonal.
    def loglik(y, mean, W, logdet, psi):
        r = (W @ (y - mean)) / psi
        k = y.shape[0]
        return -0.5 * jnp.sum(r * r) - k * jnp.log(psi) - logdet - 0.5 * k * math.log(2.0 * math.pi)

    numpyro.factor("a_hat", loglik(d["a_hat"], a, d["W_H"], d["logdet_H"], psi_H))
    if n["n_fwd"]:
        numpyro.factor("theta_hat", loglik(d["theta_hat"], theta[d["fwd"]] * d["avg"], d["W_F"], d["logdet_F"], psi_F))


def _prepare(data: Data, spec: Spec) -> dict:
    import jax.numpy as jnp
    avg, now = decay_factors(data.age) if spec.decay else (np.ones(data.n_f), np.ones(data.n_f))
    zg, qd, zga, qa = tables(spec.w)
    out = {"zg": jnp.asarray(zg), "qd": jnp.asarray(qd), "zga": jnp.asarray(zga), "qa": jnp.asarray(qa),
           "tau0": math.log(TAU_GRID[0]), "dtau": math.log(TAU_GRID[1]) - math.log(TAU_GRID[0]),
           "mech": jnp.asarray(data.mech), "fam": jnp.asarray(data.fam), "fwd": jnp.asarray(data.fwd),
           "a_hat": jnp.asarray(data.a_hat), "theta_hat": jnp.asarray(data.theta_hat),
           "avg": jnp.asarray(avg[data.fam[data.fwd]]), "now": jnp.asarray(now)}
    for name, cov in (("H", data.cov_H), ("F", data.cov_F)):
        if cov.shape[0] == 0:
            out[f"W_{name}"], out[f"logdet_{name}"] = jnp.zeros((0, 0)), 0.0
            continue
        if spec.diagonal:                                         # S4: no cross-correlation
            sd = np.sqrt(np.diag(cov))
            W, logdet = np.diag(1.0 / sd), float(np.log(sd).sum())
        else:
            Lc = np.linalg.cholesky(cov)
            W = solve_triangular(Lc, np.eye(Lc.shape[0]), lower=True)
            logdet = float(np.log(np.diag(Lc)).sum())
        out[f"W_{name}"], out[f"logdet_{name}"] = jnp.asarray(W), logdet
    return out


@dataclass
class Fit:
    spec: str
    converged: bool
    rhat_max: float
    ess_min: float
    divergences: int
    pi: np.ndarray              # (n_f,) Pr(θ_f ≥ θ_min | data)
    mean: np.ndarray            # (n_f,) posterior mean of θ_f
    sd: np.ndarray              # (n_f,) posterior standard deviation of θ_f
    hyper: dict                 # posterior means of the hyperparameters
    seconds: float = 0.0
    draws: np.ndarray | None = None      # (draws, n_f) a thinned sample of θ_f, when asked for


_CACHE: dict = {}


def fit(data: Data, spec: Spec, seed: int, *, warmup: int = 1000, samples: int = 1000, chains: int = 4,
        target_accept: float = 0.9, keep_draws: int = 0, max_tree_depth: int = 10) -> Fit:
    """Fit one model. The compiled sampler is reused for later fits of the same shape."""
    import time

    import jax
    import numpyro
    from numpyro.diagnostics import effective_sample_size, split_gelman_rubin
    from numpyro.infer import MCMC, NUTS, init_to_median

    numpyro.enable_x64()
    t0 = time.time()
    d = _prepare(data, spec)
    n = {"n_f": data.n_f, "n_h": int(data.a_hat.size), "n_m": int(data.mech.max()) + 1, "n_fwd": int(data.fwd.size)}
    key = (spec, tuple(n.values()), warmup, samples, chains, target_accept, max_tree_depth)
    mcmc = _CACHE.get(key)
    if mcmc is None:
        kernel = NUTS(partial(_model, spec=spec, n=n), target_accept_prob=target_accept,
                      init_strategy=init_to_median(num_samples=10), max_tree_depth=max_tree_depth)
        mcmc = MCMC(kernel, num_warmup=warmup, num_samples=samples, num_chains=chains, chain_method="vectorized",
                    progress_bar=False, jit_model_args=True)
        _CACHE[key] = mcmc
    if hasattr(mcmc, "_init_state_cache"):
        mcmc._init_state_cache = {}       # a second run with the same key and data must start afresh, not from a cache
    mcmc.run(jax.random.PRNGKey(int(seed) % (2**31)), d, extra_fields=("diverging",))
    post = mcmc.get_samples(group_by_chain=True)
    rhat_max, ess_min = 0.0, math.inf
    for name, v in post.items():
        if name in ("theta_f", "A", "rho"):        # deterministic functions of sampled parameters
            continue
        v = np.asarray(v).reshape(v.shape[0], v.shape[1], -1)
        rhat_max = max(rhat_max, float(np.nanmax(split_gelman_rubin(v))))
        ess_min = min(ess_min, float(np.nanmin(effective_sample_size(v))))
    div = int(np.asarray(mcmc.get_extra_fields()["diverging"]).sum())
    th = np.asarray(post["theta_f"]).reshape(-1, n["n_f"])
    hyper = {k: float(np.asarray(post[k]).mean()) for k in ("mu_rho", "sigma_rho", "phi", "mu_A", "tau_A", "sigma_dom")}
    out = Fit(spec=spec.name, converged=bool(rhat_max <= RHAT_MAX and ess_min >= ESS_MIN and div == 0),
              rhat_max=rhat_max, ess_min=ess_min, divergences=div, pi=(th >= THETA_MIN).mean(axis=0),
              mean=th.mean(axis=0), sd=th.std(axis=0), hyper=hyper, seconds=time.time() - t0)
    if keep_draws:
        step = max(1, th.shape[0] // keep_draws)
        out.draws = th[::step][:keep_draws]
    return out
