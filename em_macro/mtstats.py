"""Multiple-testing statistics for a Sharpe ratio (spec §0.2, §17.2 Build 3).

Conventions follow docs/research/algorithm_spec_2026-11.md:
  * `sr` in psr / sr0 / dsr / min_trl is the per-period (monthly) Sharpe ratio, T the number of periods;
  * g3 = skewness, g4 = raw (non-excess) kurtosis (normal = 3);
  * the haircut functions take the annualised Sharpe ratio and the sample length in years.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649


def sr_sigma(sr: float, T: int, g3: float = 0.0, g4: float = 3.0) -> float:
    """Standard error of a per-period Sharpe ratio under non-normal returns."""
    return float(np.sqrt((1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) / (T - 1)))


def psr(sr: float, T: int, g3: float = 0.0, g4: float = 3.0, s0: float = 0.0) -> float:
    """Probabilistic Sharpe ratio (Bailey and Lopez de Prado 2012): P(true SR > s0)."""
    return float(norm.cdf((sr - s0) / sr_sigma(sr, T, g3, g4)))


def sr0(N: int, sd: float) -> float:
    """Expected maximum Sharpe ratio of N independent trials whose Sharpe ratios
    have cross-sectional standard deviation `sd` (same units as sd)."""
    return float(sd * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / N) + EULER_GAMMA * norm.ppf(1 - 1 / (N * np.e))))


def dsr(sr: float, T: int, N: int, sd: float, g3: float = 0.0, g4: float = 3.0) -> float:
    """Deflated Sharpe ratio (Bailey and Lopez de Prado 2014): PSR against SR0."""
    return psr(sr, T, g3, g4, s0=sr0(N, sd))


def min_trl(sr: float, g3: float, g4: float, c: float, s0: float = 0.0) -> float:
    """Minimum track record length (periods) for P(true SR > s0) >= c."""
    return float(1 + (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) * (norm.ppf(c) / (sr - s0)) ** 2)


def naive_test(sr_ann: float, years: float) -> dict:
    t = sr_ann * np.sqrt(years)
    return {"t": float(t), "p_two_sided": float(2 * (1 - norm.cdf(t))), "p_one_sided": float(1 - norm.cdf(t)),
            "se_sr_ann": float(np.sqrt((1 + 0.5 * sr_ann ** 2) / years))}


def _sr_from_p(p: float, years: float) -> float:
    return float(norm.ppf(1 - min(1.0, p) / 2) / np.sqrt(years)) if p < 1 else 0.0


def haircut_bonferroni(sr_ann: float, years: float, M: int) -> float:
    """Harvey-Liu (2015) Bonferroni-adjusted annualised Sharpe ratio (equals Holm
    for the top-ranked test)."""
    p = 2 * (1 - norm.cdf(sr_ann * np.sqrt(years)))
    return _sr_from_p(min(1.0, M * p), years)


def haircut_sidak(sr_ann: float, years: float, M: int) -> float:
    p = 2 * (1 - norm.cdf(sr_ann * np.sqrt(years)))
    return _sr_from_p(1 - (1 - p) ** M, years)


def haircut_bhy(sr_ann: float, years: float, M: int, other_p: list[float] | None = None) -> float:
    """Benjamini-Hochberg-Yekutieli adjustment.  Without the other tests' p-values
    the tested strategy is treated as the top-ranked (rank 1) test."""
    p = 2 * (1 - norm.cdf(sr_ann * np.sqrt(years)))
    c = sum(1 / i for i in range(1, M + 1))
    ps = sorted([p] + list(other_p or []))
    k = ps.index(p) + 1
    adj = min(1.0, min(ps[j] * M * c / (j + 1) for j in range(k - 1, len(ps))))
    return _sr_from_p(adj, years)
