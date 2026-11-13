"""A two-group ("spike and slab") version of the analytic model of Protocol v3.1 section 7: a **development
candidate**, tried for scenario D08 and **not adopted** (``results/manhattan_sim/v2/D08_SPIKE_SLAB.md``).

No run of record uses this file: it is in no code list of ``manhattan/sim/run.py``, and no tier, forecast or
report figure comes from it. It is kept so that the identification check can be repeated.

The model of ``hier_analytic`` describes every family by one hump: ``θ_f = ρ a_f + η_f``. Where a large share of
families has an edge of exactly zero and the rest have clear ones (D08), one hump has to stretch over both
groups and says too much in the middle of the scale (Protocol 3.1 section 7.2(d)). The candidate adds a second
group:

    slab   (probability π):      θ_f = ρ_{m(f)} a_f + η_f,   η_f ~ (1 − w) Normal(0, 0.02²) + w Normal(0, s_R²)
                                 exactly the model of ``hier_analytic``
    spike  (probability 1 − π):  θ_f = η_f,                  η_f ~ Normal(0, 0.02²)
                                 the slab at retention 0 with the existing 0.02 innovation: no new constant
    π ("edge share"):            uniform on ten nodes, 0.05, 0.15, ..., 0.95; one share for the whole programme

``a_f``, the reserve estimate, the forward estimate and the common shock are those of ``hier_analytic`` in both
groups, so a family's likelihood is ``π · L_slab + (1 − π) · L_spike`` with both terms in closed form, and the
share is one more axis of the fixed grid. **With the share fixed at 1 this is ``hier_analytic``, number for
number** (``tests/test_manhattan_hier_spike.py``).

``Fit.pi`` and the other per-family numbers are computed as in ``hier_analytic`` (a second pass over the grid
cells that carry weight). There are no posterior draws: the dormancy forecast would need them, and the
candidate was stopped before that (the share is not identified by the data a programme has).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from scipy.special import logsumexp, ndtr
from scipy.stats import norm

from . import hier_analytic as ha

SHARE_GRID = 0.05 + 0.10 * np.arange(10)        # uniform prior on the edge share: ten nodes of equal weight


@dataclass
class Fit:
    spec: str
    ok: bool
    edge_mass: float
    pi: np.ndarray              # (F,) Pr(θ_f ≥ θ_min | data)
    mean: np.ndarray            # (F,) posterior mean of θ_f
    sd: np.ndarray              # (F,) posterior standard deviation of θ_f
    conflict: np.ndarray        # (F,) posterior weight of the wide component of η_f (slab only)
    slab: np.ndarray            # (F,) posterior probability that the family is in the slab
    hyper: dict
    log_evidence: float
    grid_points: int
    share_grid: np.ndarray      # the nodes of the edge share
    share_post: np.ndarray      # posterior weight of each node
    share_loglik: np.ndarray    # log marginal likelihood of the data at each node (every other parameter integrated)
    seconds: float = 0.0

    @property
    def share_mean(self) -> float:
        return float(self.share_post @ self.share_grid)

    @property
    def share_sd(self) -> float:
        m = self.share_mean
        return float(math.sqrt(max(self.share_post @ (self.share_grid - m) ** 2, 0.0)))


def _spike_components(d: ha.Data, sel, mu, tau, psi, nu, k, now, moments: bool = True):
    """The spike's two normal components (narrow and wide ``a_f``; ``η_f`` narrow only) for the families
    ``sel``: ``hier_analytic``'s own formulas at retention 0, read at the narrow component of ``η``. The retention
    axis is kept with length 1 so that the result broadcasts against the slab's."""
    zero = np.zeros_like(np.asarray(mu, dtype=float))
    ll, m, c = ha._components(d, sel, mu, tau, psi, zero, nu, k, now, moments=moments)
    if not moments:
        return ll[..., 0], None, None
    return ll[..., 0], m[..., 0], c[..., 0]


def _mix_a(ll, w: float):
    """Mix the two components of ``a`` with robust weight ``w``: the spike's log likelihood."""
    lw = ll + np.log(np.array([1.0 - w, w]))
    top = lw.max(axis=-1)
    return top + np.log(np.exp(lw - top[..., None]).sum(axis=-1))


def _reduce_a(ll, m, c, w: float):
    """Under the spike's posterior over the two components of ``a``: ``Pr(θ ≥ θ_min)``, mean, second moment."""
    lw = ll + np.log(np.array([1.0 - w, w]))
    p = np.exp(lw - lw.max(axis=-1, keepdims=True))
    p /= p.sum(axis=-1, keepdims=True)
    return ((p * ndtr((m - ha.THETA_MIN) / np.sqrt(c))).sum(axis=-1), (p * m).sum(axis=-1), (p * (c + m * m)).sum(axis=-1))


def fit_many(data: ha.Data, specs=ha.SPECS, *, share_grid=SHARE_GRID) -> list[Fit]:
    """Fit several of the six models with the edge share on ``share_grid`` (equal prior weight on every node).
    ``share_grid=[1.0]`` is ``hier_analytic.fit_many``."""
    share = np.asarray(share_grid, dtype=float)
    if share.ndim != 1 or share.size < 1 or np.any(share <= 0) or np.any(share > 1):
        raise ValueError("the edge share's nodes must lie in (0, 1]")
    with np.errstate(divide="ignore"):
        l_in, l_out = np.log(share), np.log1p(-share)                     # log π, log(1 − π); −inf at π = 1
    l_share = np.full(share.size, -math.log(share.size))
    P = share.size
    out: dict[str, Fit] = {}
    groups: dict[tuple, list[ha.Spec]] = {}
    for sp in specs:
        groups.setdefault((sp.psi_fixed, sp.decay), []).append(sp)
    F = data.n_f
    classes = np.unique(data.mech)
    cls = np.searchsorted(classes, data.mech)
    nu, lnu = (ha.NU_GRID, ha.NU_LOGW) if data.r_F > 0 and data.has_forward.any() else (np.zeros(1), np.zeros(1))
    G, V = ha.RHO_GRID.size, nu.size
    for (psi_fixed, decay), members in groups.items():
        t0 = time.time()
        psi_grid = ha.PSI_GRID if psi_fixed is None else np.array([float(psi_fixed)])
        ws = tuple(sorted({sp.w for sp in members}))
        kept = ha._reserve_keep(data, psi_grid, ha.ALL_W)
        i_mu, i_tau, i_psi = np.unravel_index(kept, (ha.MU_A_GRID.size, ha.TAU_A_GRID.size, psi_grid.size))
        mu, tau, psi = ha.MU_A_GRID[i_mu], ha.TAU_A_GRID[i_tau], psi_grid[i_psi]
        lprior = norm.logpdf(mu, *ha.PRIORS["mu_A"])
        k_f, now_f = ha.decay_factors(data.age) if decay else (np.ones(F), np.ones(F))
        N = kept.size
        # pass 1: every class's log likelihood on the whole grid, for every node of the share
        Lm = {w: np.zeros((P, classes.size, N, G, V)) for w in ws}
        step = max(1, ha.CHUNK_CELLS // (N * G * V * P))
        for a in range(0, F, step):
            sel = np.arange(a, min(F, a + step))
            ll, _, _ = ha._components(data, sel, mu[:, None, None, None], tau[:, None, None, None], psi[:, None, None, None],
                                      ha.RHO_GRID[None, :, None, None], nu[None, None, :, None], k_f[sel], now_f[sel],
                                      moments=False)                                          # (N, G, V, f, 2, 2)
            ls, _, _ = _spike_components(data, sel, mu[:, None, None, None], tau[:, None, None, None],
                                         psi[:, None, None, None], nu[None, None, :, None], k_f[sel], now_f[sel],
                                         moments=False)                                       # (N, 1, V, f, 2)
            for w in ws:
                slab, spike = ha._mix_loglik(ll, w), _mix_a(ls, w)                            # (N, G, V, f), (N, 1, V, f)
                for p in range(P):
                    tot = np.logaddexp(l_in[p] + slab, l_out[p] + spike)                      # exactly ``slab`` at π = 1
                    for j in np.unique(cls[sel]):
                        Lm[w][p, j] += tot[..., cls[sel] == j].sum(axis=-1)
        weights = {}
        for sp in members:
            lq, lph = ha.rho_prior(sp.mu_rho)                                                 # (Hn, G), (Hn,)
            L = Lm[sp.w]                                                                      # (P, M, N, G, V)
            A = np.stack([logsumexp(lq[None, None, :, :, None] + L[p][:, :, None, :, :], axis=3) for p in range(P)])   # (P, M, N, Hn, V)
            T = (lprior[None, :, None, None] + lph[None, None, :, None] + lnu[None, None, None, :]
                 + l_share[:, None, None, None] + A.sum(axis=1))                              # (P, N, Hn, V)
            logZ = float(logsumexp(T))
            W = np.stack([np.exp(logsumexp((T[p] - logZ)[None, :, :, None, :] - A[p][:, :, :, None, :]
                                           + lq[None, None, :, :, None], axis=2) + L[p]) for p in range(P)])   # (P, M, N, G, V)
            weights[sp.name] = (W, T, logZ)
        # pass 2: each family's closed-form posterior on the cells that carry weight under that model
        acc = {}
        for sp in members:
            W = weights[sp.name][0]
            Wm = np.moveaxis(W, 1, 0).reshape(classes.size, -1)                               # (M, P·N·G·V)
            live = np.flatnonzero(Wm.max(axis=0) >= ha.CELL_MIN)
            p_i, n_i, g_i, v_i = np.unravel_index(live, (P, N, G, V))
            Wc = Wm[:, live]
            Wc = Wc / Wc.sum(axis=1, keepdims=True)
            acc[sp.name] = np.zeros((5, F))                                                   # Π, mean, 2nd moment, conflict, slab
            step = max(1, ha.CHUNK_CELLS // live.size)
            for a in range(0, F, step):
                sel = np.arange(a, min(F, a + step))
                ll, m, c = ha._components(data, sel, mu[n_i][:, None], tau[n_i][:, None], psi[n_i][:, None],
                                          ha.RHO_GRID[g_i][:, None], nu[v_i][:, None], k_f[sel], now_f[sel])   # (cells, f, 2, 2)
                ls, ms, cs = _spike_components(data, sel, mu[n_i][:, None], tau[n_i][:, None], psi[n_i][:, None],
                                               nu[v_i][:, None], k_f[sel], now_f[sel])                          # (cells, f, 2)
                l_slab = l_in[p_i][:, None] + ha._mix_loglik(ll, sp.w)
                l_spike = l_out[p_i][:, None] + _mix_a(ls, sp.w)
                q = np.exp(l_slab - np.logaddexp(l_slab, l_spike))                            # Pr(slab | cell, data): 1 at π = 1
                pi_a, m_a, m2_a, conflict = ha._reduce(ll, m, c, sp.w)
                pi_s, m_s, m2_s = _reduce_a(ls, ms, cs, sp.w)
                wt = Wc[cls[sel]].T
                parts = np.stack([q * pi_a + (1 - q) * pi_s, q * m_a + (1 - q) * m_s, q * m2_a + (1 - q) * m2_s,
                                  q * conflict, q])
                acc[sp.name][:, sel] = (parts * wt).sum(axis=1)
        shared = time.time() - t0
        for sp in members:
            t1 = time.time()
            W, T, logZ = weights[sp.name]
            pi, mean, m2, conflict, slab = acc[sp.name]
            wn = np.exp(logsumexp(T, axis=(0, 2, 3)) - logZ)                                  # posterior weight of each (μ_A, τ_A, ψ) node
            ends = (i_mu == 0) | (i_mu == ha.MU_A_GRID.size - 1)
            edge = float(wn[ends].sum())
            hyper = {"mu_A": float(wn @ mu), "tau_A": float(wn @ tau), "psi": float(wn @ psi),
                     "nu": float(W[:, 0].sum(axis=(0, 1, 2)) @ nu)}
            for j, m_id in enumerate(classes):
                hyper[f"rho_{int(m_id)}"] = float(W[:, j].sum(axis=(0, 1, 3)) @ ha.RHO_GRID)
            l_node = logsumexp(T - l_share[:, None, None, None], axis=(1, 2, 3))              # log p(data | share node)
            post = np.exp(logsumexp(T, axis=(1, 2, 3)) - logZ)
            hyper["share"] = float(post @ share)
            fit = Fit(spec=sp.name, ok=bool(edge <= ha.EDGE_MASS_MAX and np.isfinite(logZ)), edge_mass=edge,
                      pi=np.clip(pi, 0.0, 1.0), mean=mean, sd=np.sqrt(np.maximum(m2 - mean * mean, 0.0)),
                      conflict=conflict, slab=slab, hyper=hyper, log_evidence=logZ, grid_points=int(N),
                      share_grid=share.copy(), share_post=post, share_loglik=l_node)
            fit.seconds = shared / len(members) + time.time() - t1
            out[sp.name] = fit
    return [out[sp.name] for sp in specs]


def fit(data: ha.Data, spec: ha.Spec = ha.SPECS[0], *, share_grid=SHARE_GRID) -> Fit:
    """Fit one model."""
    return fit_many(data, (spec,), share_grid=share_grid)[0]
