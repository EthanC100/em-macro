"""The analytic hierarchical model of Protocol v3.1 section 7: one model for reserve and forward results, with
closed-form posteriors and no sampler.

    class m:      logit(ρ_m) ~ Normal(μ_ρ, σ_ρ²)                                    retention of mechanism class m
    family f:     a_f ~ (1 − w) Normal(μ_A, τ_A²) + w Normal(μ_A, s_R²)             apparent historical edge
                  θ_f = ρ_{m(f)} a_f + η_f                                           true forward edge
                  η_f ~ (1 − w) Normal(0, σ_η²) + w Normal(0, s_R²)
    data:         y^H_f = a_f + ψ s^H_f ε^H_f              reserve estimate, only where its evidential weight is 1
                  y^F_f = θ_f + ψ s^F_f ( √r ν + √(1−r) ε^F_f )      forward estimate, every family that has one
                  ε^H_f, ε^F_f, ν ~ Normal(0, 1), independent;  ν is one shock common to every family
    reported:     Π_f = Pr(θ_f ≥ θ_min | all data),  θ_min = 0.25

Everything is an annualised Sharpe ratio of the **family portfolio** (core-hedged, net).

**Why it is closed-form.** Given the hyperparameters ``(μ_A, τ_A, ψ, ρ_m)``, the common shock ``ν`` and which
mixture component each of ``a_f`` and ``η_f`` came from, ``(a_f, θ_f, y^H_f, y^F_f)`` is jointly normal: the
likelihood of a family's data and the posterior of ``θ_f`` are textbook normal-normal formulas. A family is
therefore a mixture of four normals with closed-form weights, families are independent given the
hyperparameters and ``ν``, and those are integrated on a **fixed grid** with the priors below as weights. There
is no random number in a fit, nothing to converge, and the same data always give the same answer.

**The common forward shock.** Families' forward records share calendar days, so their estimates share luck: a
market-wide move lifts or lowers all of them together. ``r`` (``Data.r_F``) is the share of a forward
estimate's sampling variance that is common: the average sampling correlation between the forward estimates of
different families, measured from their returns and floored at zero. Without it the model takes the average
forward level as known to within ``s/√F`` and reads a common piece of luck as a common edge (seen in the
development scenario with fat tails). With ``r = 0`` the term vanishes.

**One combined decay and contamination parameter.** ``ρ`` is the only link from history to the future, as in
v3.0: one number per mechanism class, partially pooled across classes.

**Selection handled once.** Every family enters, whatever its result; shrinkage towards the group is the only
adjustment. No further haircut exists in this file.

**Robust components.** A tenth of the prior mass of ``a_f`` and of ``η_f`` sits in a wide normal (standard
deviation ``s_R = 1.5``). A family far from its group, or whose forward record contradicts its history, moves
its own weight to the wide component; ``Fit.conflict`` reports that weight for ``η_f``.

**Adaptive-channel families carry zero evidential weight on the reserve** (ARCHITECTURE section 6.3; the
evidence is pilot scenario D09b). The weight is not an input: it is computed here from the family's channel by
``manhattan.ledger.evidential_weight``, and a family whose weight is 0 has no reserve term at all, whatever
number is stored for it.

``Π_f`` is a posterior probability under this model. It is never an error rate.

The six models of section 7.2(e): S1 and S2 move the centre of the retention prior, S3 has more robust mass, S4
fixes ``ψ = 1.5``, S5 lets the forward edge halve every three years (the forward estimate of a record of ``u``
years then has mean ``θ_f`` times the average of ``2^(−t/3)`` over the record, and ``Π_f`` is about the edge at
the family's current age).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.special import log_ndtr, logsumexp, ndtr
from scipy.stats import norm

from manhattan.ledger import evidential_weight

THETA_MIN = 0.25
W_ROBUST, S_ROBUST = 0.10, 1.5
ETA_SD = 0.02
HALF_LIFE_S5 = 3.0
EDGE_MASS_MAX = 0.01            # a fit is used only if at most this much posterior mass sits on the ends of μ_A's grid
PRUNE_LOG = 18.0                # grid points whose reserve-only posterior is below e^−18 of the best are dropped
CELL_MIN = 1e-10                # grid cells with less posterior weight than this (in every class) are not carried
CHUNK_CELLS = 1_500_000         # (grid cells × families) evaluated at a time: bounds memory, changes no number


@dataclass(frozen=True)
class Spec:
    name: str
    mu_rho: float = 0.35            # centre of the retention prior, on the probability scale
    w: float = W_ROBUST
    psi_fixed: float | None = None  # S4
    decay: bool = False             # S5


SPECS = (Spec("S0"), Spec("S1", mu_rho=0.15), Spec("S2", mu_rho=0.60), Spec("S3", w=0.25),
         Spec("S4", psi_fixed=1.5), Spec("S5", decay=True))
ALL_W = tuple(sorted({sp.w for sp in SPECS}))
PRIORS = {"mu_rho_sd": 1.0, "sigma_rho": 1.0, "mu_A": (0.3, 0.3), "tau_A": 0.5, "psi_excess": 0.25}


def _half_normal_nodes(scale: float, k: int) -> np.ndarray:
    """``k`` equal-probability nodes of a half-normal: its quantiles at ``(i + ½)/k``."""
    return scale * norm.ppf(0.5 + (np.arange(k) + 0.5) / (2 * k))


# The fixed quadrature grid (Protocol v3.1 Appendix B). Nothing here depends on data.
MU_A_STEP = 0.02
MU_A_GRID = PRIORS["mu_A"][0] + MU_A_STEP * np.arange(-60, 61)                # 0.3 ± 4 prior sd, 121 nodes
TAU_A_GRID = _half_normal_nodes(PRIORS["tau_A"], 10)
PSI_GRID = 1.0 + _half_normal_nodes(PRIORS["psi_excess"], 3)
RHO_EDGES = np.linspace(0.0, 1.0, 21)
RHO_GRID = 0.5 * (RHO_EDGES[:-1] + RHO_EDGES[1:])                             # 0.025, 0.075, ..., 0.975
MU_RHO_Z = norm.ppf((np.arange(9) + 0.5) / 9)                                 # nodes of μ_ρ, in prior sd
SIGMA_RHO_GRID = _half_normal_nodes(PRIORS["sigma_rho"], 5)
NU_GRID, _NU_W = np.polynomial.hermite_e.hermegauss(7)                        # the common shock: Gauss-Hermite, 7 nodes
NU_LOGW = np.log(_NU_W / _NU_W.sum())
R_F_MAX = 0.9


def rho_prior(mu_rho_centre: float) -> tuple[np.ndarray, np.ndarray]:
    """``(log p(ρ in cell g | node h), log p(node h))`` for the nodes ``h = (μ_ρ, σ_ρ)`` of the retention prior
    centred at ``mu_rho_centre`` (a probability). Shapes ``(45, 20)`` and ``(45,)``."""
    centre = math.log(mu_rho_centre / (1.0 - mu_rho_centre))
    mu = centre + PRIORS["mu_rho_sd"] * MU_RHO_Z
    with np.errstate(divide="ignore"):
        edges = np.log(RHO_EDGES) - np.log1p(-RHO_EDGES)                      # logit; −inf and +inf at the ends
    mu_h, sg_h = (x.ravel() for x in np.meshgrid(mu, SIGMA_RHO_GRID, indexing="ij"))
    cdf = ndtr((edges[None, :] - mu_h[:, None]) / sg_h[:, None])
    mass = np.maximum(np.diff(cdf, axis=1), 1e-300)
    return np.log(mass), np.full(mu_h.size, -math.log(mu_h.size))


def decay_factors(age_years: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """S5: (average of ``2^(−t/3)`` over a record of that many years, its value at the end of the record)."""
    u = np.asarray(age_years, dtype=float)
    k = math.log(2.0) / HALF_LIFE_S5
    with np.errstate(invalid="ignore", divide="ignore"):
        avg = np.where(u > 0, (1.0 - np.exp(-k * u)) / (k * np.where(u > 0, u, 1.0)), 1.0)
    return avg, np.exp(-k * u)


@dataclass
class Data:
    """Inputs of one fit, one row per family.

    ``y_F`` is NaN for a family with no forward estimate yet. ``channel`` is ``"blind"`` or ``"adaptive"`` and
    ``designated`` says whether the reserve estimate is the family's designated evaluation: together they fix
    the reserve estimate's evidential weight, which cannot be set by hand."""
    y_H: np.ndarray             # (F,) reserve sample Sharpe ratio of the family portfolio (annualised)
    s_H: np.ndarray             # (F,) its standard error
    y_F: np.ndarray             # (F,) forward sample Sharpe ratio; NaN where there is none
    s_F: np.ndarray             # (F,) its standard error
    mech: np.ndarray            # (F,) mechanism class index
    age: np.ndarray             # (F,) forward age in years (0 with no forward record)
    channel: np.ndarray | None = None       # (F,) "blind" | "adaptive"; default: all blind
    designated: np.ndarray | None = None    # (F,) bool; default: all designated
    r_F: float = 0.0                        # share of a forward estimate's sampling variance common to all families

    def __post_init__(self):
        F = int(np.asarray(self.mech).size)
        self.r_F = float(self.r_F)
        if not 0.0 <= self.r_F <= R_F_MAX:
            raise ValueError(f"r_F must be between 0 and {R_F_MAX}")
        self.mech = np.asarray(self.mech, dtype=int)
        self.age = np.asarray(self.age, dtype=float)
        self.channel = np.full(F, "blind") if self.channel is None else np.asarray(self.channel, dtype=str)
        self.designated = np.ones(F, dtype=bool) if self.designated is None else np.asarray(self.designated, dtype=bool)
        for name in ("y_H", "s_H", "y_F", "s_F"):
            setattr(self, name, np.asarray(getattr(self, name), dtype=float))
        for name in ("y_H", "s_H", "y_F", "s_F", "age", "channel", "designated"):
            if getattr(self, name).shape != (F,):
                raise ValueError(f"{name} must have one entry per family")
        bad = set(np.unique(self.channel)) - {"blind", "adaptive"}
        if bad:
            raise ValueError(f"unknown channel {sorted(bad)}")
        w = self.reserve_weight
        if np.any(w & ~(np.isfinite(self.y_H) & (self.s_H > 0))):
            raise ValueError("a reserve estimate with evidential weight 1 needs a finite value and a positive standard error")
        f = self.has_forward
        if np.any(f & ~(self.s_F > 0)):
            raise ValueError("a forward estimate needs a positive standard error")

    @property
    def n_f(self) -> int:
        return int(self.mech.size)

    @property
    def reserve_weight(self) -> np.ndarray:
        """ARCHITECTURE section 6.3, through the ledger's own rule: 1 only for a blind family's designated
        reserve evaluation. An adaptive-channel family is always 0."""
        return np.array([evidential_weight(str(c), "reserve", bool(d)) == 1
                         for c, d in zip(self.channel, self.designated)], dtype=bool)

    @property
    def has_forward(self) -> np.ndarray:
        return np.isfinite(self.y_F)


@dataclass
class Fit:
    spec: str
    ok: bool                    # the grid gate: False means "model not computed", and no tier may change
    edge_mass: float            # posterior mass on the two end nodes of μ_A's grid
    pi: np.ndarray              # (F,) Pr(θ_f ≥ θ_min | data)
    mean: np.ndarray            # (F,) posterior mean of θ_f
    sd: np.ndarray              # (F,) posterior standard deviation of θ_f
    conflict: np.ndarray        # (F,) posterior weight of the wide component of η_f (history and forward disagree)
    hyper: dict                 # posterior means of the hyperparameters
    log_evidence: float
    grid_points: int            # (μ_A, τ_A, ψ) nodes kept after pruning
    seconds: float = 0.0
    draws: np.ndarray | None = field(default=None, repr=False)      # (draws, F) of θ_f, when asked for

    @property
    def converged(self) -> bool:
        """The name the tier code of v3.0 uses for "this fit may be used"."""
        return self.ok


def _log_normal(x, mean, var):
    return -0.5 * (np.log(2.0 * math.pi * var) + (x - mean) ** 2 / var)


def _components(d: Data, sel, mu, tau, psi, rho, nu, k, now, moments: bool = True):
    """The four normal components of the families ``sel`` at hyperparameter values (and common shock ``nu``)
    that broadcast against a trailing family axis. Returns ``(log likelihood, posterior mean, posterior
    variance)`` of ``θ_f`` (times the S5 factor ``now``), each with two trailing axes ``(component of a,
    component of η)`` after the family axis. Mixture weights are **not** included. With ``moments=False`` only
    the log likelihood is computed."""
    wH, hasF = d.reserve_weight[sel], d.has_forward[sel]
    yH = np.where(wH, d.y_H[sel], 0.0)                       # a weight-0 reserve estimate is never read
    sH = np.where(wH, d.s_H[sel], 1.0)
    yF = np.where(hasF, d.y_F[sel], 0.0)
    sF = np.where(hasF, d.s_F[sel], 1.0)
    mu, tau, psi, rho, nu = (np.asarray(x, dtype=float)[..., None] for x in (mu, tau, psi, rho, nu))   # + component-of-a axis
    va = np.concatenate(np.broadcast_arrays((tau * tau), np.full_like(tau * tau, S_ROBUST**2)), axis=-1)
    eH = (psi * sH[..., None]) ** 2                          # sampling variance of the reserve estimate
    tot = va + eH
    lres = np.where(wH[..., None], _log_normal(yH[..., None], mu, tot), 0.0)
    m_a = np.where(wH[..., None], mu + va / tot * (yH[..., None] - mu), mu)
    c_a = np.where(wH[..., None], va * eH / tot, va)
    # component-of-η axis
    u = np.array([ETA_SD**2, S_ROBUST**2])
    rho_, k_, now_ = rho[..., None], np.asarray(k, dtype=float)[..., None, None], np.asarray(now, dtype=float)[..., None, None]
    m0 = rho_ * m_a[..., None]
    c0 = rho_ * rho_ * c_a[..., None] + u
    seF = psi * sF[..., None]                                # standard error of the forward estimate
    eF = ((1.0 - d.r_F) * seF * seF)[..., None]              # its part that is the family's own
    yF_ = (yF[..., None] - math.sqrt(d.r_F) * seF * nu)[..., None]      # the forward estimate less the common shock
    hF = hasF[..., None, None]
    pred = k_ * k_ * c0 + eF
    lfwd = np.where(hF, _log_normal(yF_, k_ * m0, pred), 0.0)
    if not moments:
        return lres[..., None] + lfwd, None, None
    c1 = np.where(hF, c0 * eF / pred, c0)
    m1 = np.where(hF, m0 + k_ * c0 / pred * (yF_ - k_ * m0), m0)
    return lres[..., None] + lfwd, now_ * m1, now_ * now_ * c1


def _mix_logw(w: float) -> np.ndarray:
    lw = np.log(np.array([1.0 - w, w]))
    return lw[:, None] + lw[None, :]


def _mix_loglik(ll, w: float) -> np.ndarray:
    """The family's log likelihood: the four components mixed with robust weight ``w``."""
    lw = ll + _mix_logw(w)
    top = lw.max(axis=(-2, -1))
    return top + np.log(np.exp(lw - top[..., None, None]).sum(axis=(-2, -1)))


def _reduce(ll, m, c, w: float):
    """Under the family's posterior over its four components (robust weight ``w``): ``Pr(θ ≥ θ_min)``, the
    mean, the second moment and the weight of the wide ``η``."""
    lw = ll + _mix_logw(w)
    p = np.exp(lw - lw.max(axis=(-2, -1), keepdims=True))
    p /= p.sum(axis=(-2, -1), keepdims=True)
    return ((p * ndtr((m - THETA_MIN) / np.sqrt(c))).sum(axis=(-2, -1)), (p * m).sum(axis=(-2, -1)),
            (p * (c + m * m)).sum(axis=(-2, -1)), p[..., 1].sum(axis=-1))


def _reserve_keep(d: Data, psi_grid: np.ndarray, ws: tuple[float, ...]) -> np.ndarray:
    """Indices of the ``(μ_A, τ_A, ψ)`` nodes worth evaluating: those whose reserve-only posterior, under any of
    the robust weights ``ws``, is within ``e^−PRUNE_LOG`` of the best. The forward data cannot rescue a node the
    reserve data rule out by that much, and dropping it changes no reported number at the precision shown."""
    wH = d.reserve_weight
    shape = (MU_A_GRID.size, TAU_A_GRID.size, psi_grid.size)
    lprior = norm.logpdf(MU_A_GRID, *PRIORS["mu_A"])[:, None, None] + np.zeros(shape)
    keep = np.zeros(shape, dtype=bool)
    if not wH.any():
        return np.flatnonzero(np.ones(shape, dtype=bool).ravel())
    y, s = d.y_H[wH], d.s_H[wH]
    mu = MU_A_GRID[:, None, None, None]
    e = (psi_grid[None, None, :, None] * s) ** 2
    l_core = _log_normal(y, mu, TAU_A_GRID[None, :, None, None] ** 2 + e)
    l_rob = _log_normal(y, mu, S_ROBUST**2 + e)
    for w in ws:
        post = np.logaddexp(math.log(1.0 - w) + l_core, math.log(w) + l_rob).sum(axis=-1) + lprior
        keep |= post >= post.max() - PRUNE_LOG
    return np.flatnonzero(keep.ravel())


def fit_many(data: Data, specs=SPECS, *, draws: int = 0, seed: int = 0) -> list[Fit]:
    """Fit several of the six models to the same data. Models that share their likelihood (S0, S1 and S2) share
    the first pass; a model's numbers do not depend on which other models are fitted with it. ``draws > 0`` adds that many posterior draws of ``θ_f`` per family to each fit (used only
    by the dormancy forecast; the generator is seeded from ``seed`` and the model's name, and nothing else in a
    fit is random).

    Two passes over the families. The first sums each class's log likelihood over the whole grid, which gives
    the posterior weight of every grid cell. The second evaluates each family's closed-form posterior on the
    cells that carry weight (the rest hold less than ``CELL_MIN`` each) and averages it with those weights."""
    out: dict[str, Fit] = {}
    groups: dict[tuple, list[Spec]] = {}
    for sp in specs:
        groups.setdefault((sp.psi_fixed, sp.decay), []).append(sp)
    F = data.n_f
    classes = np.unique(data.mech)
    cls = np.searchsorted(classes, data.mech)
    nu, lnu = (NU_GRID, NU_LOGW) if data.r_F > 0 and data.has_forward.any() else (np.zeros(1), np.zeros(1))
    G, V = RHO_GRID.size, nu.size
    for (psi_fixed, decay), members in groups.items():
        t0 = time.time()
        psi_grid = PSI_GRID if psi_fixed is None else np.array([float(psi_fixed)])
        ws = tuple(sorted({sp.w for sp in members}))
        kept = _reserve_keep(data, psi_grid, ALL_W)       # the same nodes whichever models are asked for
        i_mu, i_tau, i_psi = np.unravel_index(kept, (MU_A_GRID.size, TAU_A_GRID.size, psi_grid.size))
        mu, tau, psi = MU_A_GRID[i_mu], TAU_A_GRID[i_tau], psi_grid[i_psi]
        lprior = norm.logpdf(mu, *PRIORS["mu_A"])                              # τ_A and ψ nodes have equal weight
        k_f, now_f = decay_factors(data.age) if decay else (np.ones(F), np.ones(F))
        N = kept.size
        # pass 1: the log likelihood of every class on the whole grid
        Lm = {w: np.zeros((classes.size, N, G, V)) for w in ws}
        step = max(1, CHUNK_CELLS // (N * G * V))
        for a in range(0, F, step):
            sel = np.arange(a, min(F, a + step))
            ll, _, _ = _components(data, sel, mu[:, None, None, None], tau[:, None, None, None], psi[:, None, None, None],
                                   RHO_GRID[None, :, None, None], nu[None, None, :, None], k_f[sel], now_f[sel],
                                   moments=False)                                            # (N, G, V, f, 2, 2)
            for w in ws:
                tot = _mix_loglik(ll, w)                                                    # (N, G, V, f)
                for j in np.unique(cls[sel]):
                    Lm[w][j] += tot[..., cls[sel] == j].sum(axis=-1)
        weights = {}
        for sp in members:
            lq, lph = rho_prior(sp.mu_rho)                                                  # (Hn, G), (Hn,)
            L = Lm[sp.w]
            A = logsumexp(lq[None, None, :, :, None] + L[:, :, None, :, :], axis=3)         # (M, N, Hn, V)
            T = lprior[:, None, None] + lph[None, :, None] + lnu[None, None, :] + A.sum(axis=0)     # (N, Hn, V)
            logZ = float(logsumexp(T))
            # posterior weight of (node, ρ cell, shock) for each class: Σ_h exp(T − A_m + log q) · exp(L_m) / Z
            W = np.exp(logsumexp((T - logZ)[None, :, :, None, :] - A[:, :, :, None, :] + lq[None, None, :, :, None],
                                 axis=2) + L)                                               # (M, N, G, V)
            weights[sp.name] = (W, np.exp(logsumexp(T, axis=(1, 2)) - logZ), logZ)
        # pass 2: each family's closed-form posterior on the cells that carry weight under that model
        acc = {}
        for sp in members:
            W = weights[sp.name][0]
            live = np.flatnonzero(W.max(axis=0).ravel() >= CELL_MIN)
            n_i, g_i, v_i = np.unravel_index(live, (N, G, V))
            Wc = W.reshape(classes.size, -1)[:, live]
            Wc = Wc / Wc.sum(axis=1, keepdims=True)                                         # (M, cells)
            acc[sp.name] = np.zeros((4, F))                                                 # Π, mean, 2nd moment, conflict
            step = max(1, CHUNK_CELLS // live.size)
            for a in range(0, F, step):
                sel = np.arange(a, min(F, a + step))
                ll, m, c = _components(data, sel, mu[n_i][:, None], tau[n_i][:, None], psi[n_i][:, None],
                                       RHO_GRID[g_i][:, None], nu[v_i][:, None], k_f[sel], now_f[sel])    # (cells, f, 2, 2)
                acc[sp.name][:, sel] = (np.stack(_reduce(ll, m, c, sp.w)) * Wc[cls[sel]].T).sum(axis=1)
        shared = time.time() - t0
        for sp in members:
            t1 = time.time()
            W, wn, logZ = weights[sp.name]
            pi, mean, m2, conflict = acc[sp.name]
            ends = (i_mu == 0) | (i_mu == MU_A_GRID.size - 1)
            edge = float(wn[ends].sum())
            hyper = {"mu_A": float(wn @ mu), "tau_A": float(wn @ tau), "psi": float(wn @ psi),
                     "nu": float(W[0].sum(axis=(0, 1)) @ nu)}
            for j, m_id in enumerate(classes):
                hyper[f"rho_{int(m_id)}"] = float(W[j].sum(axis=(0, 2)) @ RHO_GRID)
            fit = Fit(spec=sp.name, ok=bool(edge <= EDGE_MASS_MAX and np.isfinite(logZ)), edge_mass=edge,
                      pi=np.clip(pi, 0.0, 1.0), mean=mean, sd=np.sqrt(np.maximum(m2 - mean * mean, 0.0)),
                      conflict=conflict, hyper=hyper, log_evidence=logZ, grid_points=int(N))
            if draws:
                fit.draws = _draw(data, sp, W, cls, (mu, tau, psi, nu), k_f, now_f, draws, seed)
            fit.seconds = shared / len(members) + time.time() - t1
            out[sp.name] = fit
    return [out[sp.name] for sp in specs]


def _draw(data: Data, sp: Spec, W: np.ndarray, cls: np.ndarray, nodes, k_f, now_f, draws: int, seed: int) -> np.ndarray:
    """``draws`` independent draws of ``θ_f`` from each family's closed-form posterior: a (node, ρ, shock) cell
    from its class's weights, a component from the family's four, then a normal. Shape ``(draws, F)``."""
    mu, tau, psi, nu = nodes
    rng = np.random.default_rng([int(seed) % (2**32), sum(sp.name.encode())])
    F, G, V = data.n_f, RHO_GRID.size, nu.size
    cell = np.empty((F, draws), dtype=int)
    for j in range(W.shape[0]):
        fam = np.flatnonzero(cls == j)
        p = W[j].ravel()
        cell[fam] = rng.choice(p.size, size=(fam.size, draws), p=p / p.sum())
    n_i, g_i, v_i = np.unravel_index(cell.T, (mu.size, G, V))                               # each (draws, F)
    ll, m, c = _components(data, np.arange(F), mu[n_i], tau[n_i], psi[n_i], RHO_GRID[g_i], nu[v_i], k_f, now_f)
    lw = (ll + _mix_logw(sp.w)).reshape(draws, F, 4)
    p = np.exp(lw - logsumexp(lw, axis=2, keepdims=True))
    comp = (p.cumsum(axis=2) < rng.random((draws, F, 1))).sum(axis=2).clip(0, 3)
    take = lambda x: np.take_along_axis(x.reshape(draws, F, 4), comp[..., None], axis=2)[..., 0]
    return take(m) + np.sqrt(take(c)) * rng.standard_normal((draws, F))


def fit(data: Data, spec: Spec = SPECS[0], *, draws: int = 0, seed: int = 0) -> Fit:
    """Fit one model."""
    return fit_many(data, (spec,), draws=draws, seed=seed)[0]


def family_posterior(y_H: float | None, s_H: float | None, y_F: float | None, s_F: float | None, *, mu_A: float,
                     tau_A: float, psi: float, rho: float, w: float = W_ROBUST, nu: float = 0.0,
                     r_F: float = 0.0) -> dict:
    """The closed form for one family at **given** hyperparameters and common shock (no grid): the four
    components' weights, means and standard deviations of ``θ_f``, and ``Π_f``. For tests, and for reading the
    model by hand. ``y_H=None`` is a family with no reserve term; ``y_F=None`` one with no forward record."""
    d = Data(y_H=[0.0 if y_H is None else y_H], s_H=[1.0 if s_H is None else s_H],
             y_F=[math.nan if y_F is None else y_F], s_F=[1.0 if s_F is None else s_F], mech=[0], age=[0.0],
             channel=["adaptive" if y_H is None else "blind"], r_F=r_F)
    ll, m, c = _components(d, np.arange(1), mu_A, tau_A, psi, rho, nu, np.ones(1), np.ones(1))
    lw = ll[0] + _mix_logw(w)
    p = np.exp(lw - logsumexp(lw))
    return {"weights": p, "mean": m[0], "sd": np.sqrt(c[0]), "log_lik": float(logsumexp(lw)),
            "pi": float((p * ndtr((m[0] - THETA_MIN) / np.sqrt(c[0]))).sum())}
