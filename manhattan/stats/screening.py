"""Across-family screening: the two candidates of Protocol v3 sections 4.3 and 4.4, and the admission levels of
section 5.5. Exactly one will be in force, chosen by SIM_PREREG section 7 from simulation results only.

Candidate (i), ``Batch-BH^PRDS`` (Zrnic, Jiang, Ramdas and Jordan 2020):

    α_b = min( α_S, α_S γ_b (n_b + R_{<b}) / n_b )
    k_b = max{ k : p_(k) ≤ k α_b / n_b };  reject the k_b smallest p-values;  a_f = k_b α_b / n_b

Candidate (ii), e-BH inside the batch at e-LOND's level (Protocol v3 Appendix A.1):

    k_b = max{ k ≥ 1 : at least k families have E_f ≥ n_b / ( α_S γ_b (R_{<b} + k) ) }
    reject every family with E_f ≥ n_b / ( α_S γ_b (R_{<b} + k_b) );  a_f = α_S γ_b (R_{<b} + k_b) / n_b

Both are online: a batch is decided from its own statistics and the count of earlier rejections, nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schedule import gamma

ALPHA_S = 0.20


@dataclass(frozen=True)
class BatchDecision:
    rejected: np.ndarray        # boolean mask over the batch's families, in the order given
    k: int
    level: float                # α_b for (i); α_S γ_b for (ii)
    admission: float            # a_f of section 5.5 for the rejected families (0.0 when none is rejected)


class BatchBH:
    """Candidate (i). Feed batches in freeze order with ``step``."""

    name = "batch_bh_prds"

    def __init__(self, N: int, alpha: float = ALPHA_S):
        self.N, self.alpha, self.R, self.b = N, alpha, 0, 0
        self.wealth_estimate = 0.0     # the paper's Σ_s α_s n_s / (n_s + R_{<s}), kept at or below α

    def step(self, pvals) -> BatchDecision:
        p = np.asarray(pvals, dtype=float)
        n = p.size
        self.b += 1
        if n == 0:
            return BatchDecision(np.zeros(0, dtype=bool), 0, 0.0, 0.0)
        g = gamma(self.b, self.N)
        level = min(self.alpha, self.alpha * g * (n + self.R) / n)
        self.wealth_estimate += level * n / (n + self.R)
        order = np.argsort(p, kind="stable")
        ok = p[order] <= np.arange(1, n + 1) * level / n
        k = int(np.flatnonzero(ok).max() + 1) if ok.any() else 0
        rejected = np.zeros(n, dtype=bool)
        rejected[order[:k]] = True
        self.R += k
        return BatchDecision(rejected, k, level, k * level / n)


class EbhElond:
    """Candidate (ii). Feed batches in freeze order with ``step``."""

    name = "ebh_elond"

    def __init__(self, N: int, alpha: float = ALPHA_S):
        self.N, self.alpha, self.R, self.b = N, alpha, 0, 0

    def step(self, evals) -> BatchDecision:
        e = np.asarray(evals, dtype=float)
        n = e.size
        self.b += 1
        if n == 0:
            return BatchDecision(np.zeros(0, dtype=bool), 0, 0.0, 0.0)
        g = gamma(self.b, self.N)
        level = self.alpha * g
        desc = np.sort(e)[::-1]
        ks = np.arange(1, n + 1)
        ok = desc >= n / (level * (self.R + ks))          # the k-th largest clears the bar set for k
        k = int(ks[ok].max()) if ok.any() else 0
        rejected = e >= n / (level * (self.R + k)) if k else np.zeros(n, dtype=bool)
        self.R += k
        return BatchDecision(rejected, k, level, level * self.R / n if k else 0.0)


def elond_levels(wealth: np.ndarray, gammas: np.ndarray, R: int, alpha: float) -> tuple[np.ndarray, int]:
    """One step of the forward rule of Protocol v3 section 6.8 on the eligible families' current wealth.

    Returns (mask of families rejected now, ``k_t``): ``k_t`` is the largest ``k`` such that at least ``k``
    families have ``W_i ≥ 1 / (α γ_i (R + k))``.
    """
    s = alpha * np.asarray(wealth, dtype=float) * np.asarray(gammas, dtype=float)
    if s.size == 0:
        return np.zeros(0, dtype=bool), 0
    desc = np.sort(s)[::-1]
    ks = np.arange(1, s.size + 1)
    ok = desc * (R + ks) >= 1.0
    k = int(ks[ok].max()) if ok.any() else 0
    return (s * (R + k) >= 1.0) if k else np.zeros(s.size, dtype=bool), k
