"""Exact null distribution of the largest of ``m`` equicorrelated standard normal statistics.

If ``Z_1..Z_m`` are standard normal with every pairwise correlation ``ρ ≥ 0``, write ``Z_k = √ρ S + √(1−ρ) E_k``
with ``S, E_k`` independent standard normals. Then

    P( max_k Z_k ≤ t ) = E_S[ Φ( (t − √ρ S) / √(1−ρ) )^m ]

which is computed here by Gauss-Hermite quadrature over ``S`` (probabilists' weight ``e^{−s²/2}``), with the power
taken in logs so that ``m`` up to 10^7 is exact to quadrature error.

Why it is here. Hansen's SPA test (``manhattan.stats.spa``) approximates the null distribution of the family's
largest studentised mean with a stationary bootstrap. When variant statistics really are equicorrelated normals,
this function is that distribution **exactly**: it is the SPA test an infinitely large bootstrap with a known
correlation would give at the least favourable null (``p_u``). It is used as an oracle, (a) to check the bootstrap
SPA in synthetic worlds and (b) to evaluate across-family procedures at programme scale, where running a bootstrap
for every one of 10^5 families and hundreds of replications would cost hours and would mix bootstrap error into
what is being measured. It is not a substitute for the SPA test on real returns, whose correlation is unknown and
not equicorrelated.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import log_ndtr, ndtr, ndtri

N_NODES = 96
_x, _w = np.polynomial.hermite_e.hermegauss(N_NODES)
NODES, WEIGHTS = _x, _w / math.sqrt(2.0 * math.pi)


def _check(m, rho):
    if np.any(np.asarray(m) < 1):
        raise ValueError("m must be at least 1")
    if not 0.0 <= rho <= 1.0:
        raise ValueError("rho must be in [0, 1]")


def max_sf(t, m, rho: float) -> np.ndarray:
    """``P(max_k Z_k ≥ t)`` for ``m`` equicorrelated standard normals (vectorised over ``t`` and ``m``).

    Computed as ``E_S[1 − Φ(u)^m]`` with ``expm1`` so that small tail probabilities keep their precision.
    """
    _check(m, rho)
    t = np.asarray(t, dtype=float)
    m = np.asarray(m, dtype=float)
    if rho >= 1.0:
        return np.broadcast_to(ndtr(-t), np.broadcast(t, m).shape).copy()
    if rho == 0.0:
        return -np.expm1(m * log_ndtr(t))
    u = (t[..., None] - math.sqrt(rho) * NODES) / math.sqrt(1.0 - rho)
    inner = -np.expm1(m[..., None] * log_ndtr(u))
    return np.clip(inner @ WEIGHTS, 0.0, 1.0)


def family_p(z_max, m, rho: float) -> np.ndarray:
    """Oracle family p-value: ``P(max of m null statistics ≥ observed max)``."""
    return max_sf(z_max, m, rho)


def critical(alpha: float, m: float, rho: float) -> float:
    """``c`` with ``P(max_k Z_k ≥ c) = α``: the bar the best of ``m`` variants must clear at level ``α``."""
    _check(m, rho)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    lo = float(ndtri(1.0 - alpha)) - 1e-9           # m = 1 (or ρ = 1) is the smallest possible bar
    hi = lo + math.sqrt(2.0 * math.log(max(m, 2.0))) + 2.0
    return float(brentq(lambda c: float(max_sf(c, m, rho)) - alpha, lo, hi, xtol=1e-10))


def power_single(delta: float, alpha: float, m: float, rho: float) -> float:
    """Power when exactly one of ``m`` variants has mean ``delta`` (in standard errors) and the rest are null.

    ``P(max(δ + Z_1, Z_2..Z_m) ≥ c) = 1 − E_S[ Φ(u − δ') Φ(u)^{m−1} ]`` with the same quadrature, where
    ``δ' = δ / √(1−ρ)`` is the effect on the idiosyncratic scale.
    """
    c = critical(alpha, m, rho)
    if rho >= 1.0:
        return float(ndtr(delta - c))
    s = math.sqrt(1.0 - rho)
    u = (c - math.sqrt(rho) * NODES) / s
    log_cdf = log_ndtr(u - delta / s) + (m - 1.0) * log_ndtr(u)
    return float(np.clip(-np.expm1(log_cdf) @ WEIGHTS, 0.0, 1.0))


def mde_single(alpha: float, power: float, m: float, rho: float) -> float:
    """Smallest single-variant effect (in standard errors of its mean) detected with the given power."""
    c = critical(alpha, m, rho)
    return float(brentq(lambda d: power_single(d, alpha, m, rho) - power, -5.0, c + 10.0, xtol=1e-8))


def sharpe_from_se(delta: float, years: float) -> float:
    """An effect of ``delta`` standard errors on a record of ``years`` is an annualised Sharpe ratio of
    ``delta / √years`` (iid returns; serial correlation raises it)."""
    return delta / math.sqrt(years)
