"""Forward e-LOND across enrolled families (Protocol v3 sections 6.8 and 6.10; proof in Appendix A.2).

Family ``i`` (numbered in enrolment order) holds ``γ^F_i = γ(i; N_F)``. At each period, with ``R`` families
already rejected, the eligible families (enrolled, not yet rejected, guard holding) are tested together:

    k_t = max{ k ≥ 1 : at least k eligible families have  W_i ≥ 1 / ( α_F γ^F_i (R + k) ) }
    reject every eligible family with  W_i ≥ 1 / ( α_F γ^F_i (R + k_t) )

A rejection is permanent; the wealth used is the current wealth, not its past maximum.
"""
from __future__ import annotations

import numpy as np

from .schedule import gamma
from .screening import elond_levels

ALPHA_F = 0.05


def run(wealth: np.ndarray, guard: np.ndarray, start: np.ndarray, N_F: int, alpha: float = ALPHA_F,
        gammas: np.ndarray | None = None) -> dict:
    """Run the rule over a common clock of periods.

    ``wealth[i, t]`` is family ``i``'s test wealth after period ``t`` and ``guard[i, t]`` whether its guard
    holds then; both are read only for ``t ≥ start[i]`` (the family's first test period). Families must be given
    in enrolment order (ties already broken by family ID); family ``i`` (0-based) gets ``γ(i + 1; N_F)``.

    Returns ``reject_at`` (period of rejection, −1 if never), ``R`` (rejections after each period) and
    ``level`` (the bar ``1/(α γ_i R_t)`` in force at each family's rejection, for the within-family rule).
    """
    wealth = np.asarray(wealth, dtype=float)
    n_fam, n_per = wealth.shape
    g = gamma(np.arange(1, n_fam + 1), N_F) if gammas is None and n_fam else np.asarray(gammas, dtype=float)
    reject_at = np.full(n_fam, -1, dtype=int)
    R_path = np.zeros(n_per, dtype=int)
    R = 0
    alive = np.ones(n_fam, dtype=bool)
    for t in range(n_per):
        elig = np.flatnonzero(alive & (start <= t) & guard[:, t])
        if elig.size:
            rej, k = elond_levels(wealth[elig, t], g[elig], R, alpha)
            if k:
                hit = elig[rej]
                reject_at[hit] = t
                alive[hit] = False
                R += k
        R_path[t] = R
    return {"reject_at": reject_at, "R": R_path, "gamma": g}


def component_named(component_wealth: np.ndarray, gamma_i: float, R: int, alpha: float = ALPHA_F) -> np.ndarray:
    """Section 6.10: component ``j`` of a rejected family with ``H + 1`` components is individually supported
    when ``W_j ≥ (H + 1) / ( α_F γ^F_i R )``."""
    w = np.asarray(component_wealth, dtype=float)
    return w >= w.size / (alpha * gamma_i * R) if R > 0 else np.zeros(w.size, dtype=bool)
