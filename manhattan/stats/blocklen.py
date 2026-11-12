"""Automatic block length for the stationary bootstrap (Protocol v3 section 5.2).

Politis and White (2004), Econometric Reviews 23(1): the flat-top window and eq. (8)-(9) on p. 58, the rule for
``m̂`` in footnote c on p. 59, ``M = 2m̂`` on p. 59 and 62. Patton, Politis and White (2009), Econometric Reviews
28(4), p. 373: ``D̂_SB = 2 ĝ(0)²`` replaces eq. (8)'s expression.

    R̂(k)  = N⁻¹ Σ_{i=1}^{N−|k|} (X_i − X̄)(X_{i+|k|} − X̄)
    λ(t)   = 1 on |t| ≤ 1/2,  2(1 − |t|) on 1/2 ≤ |t| ≤ 1,  0 beyond
    Ĝ      = Σ_{k=−M}^{M} λ(k/M) |k| R̂(k),        ĝ(0) = Σ_{k=−M}^{M} λ(k/M) R̂(k)
    b̂     = ( 2 Ĝ² / (2 ĝ(0)²) )^(1/3) · N^(1/3)
    m̂     = the smallest positive integer with |ρ̂(m̂ + k)| < c √(log₁₀N / N) for k = 1..K_N,
             c = 2, K_N = max(5, √log₁₀N)

Two conventions the papers leave open, fixed here (they follow the reference code the 2009 correction points to):
lags are examined up to ``⌈√N⌉ + K_N``; when no ``m̂`` exists in that range, ``m̂`` is the largest lag there whose
autocorrelation is significant (1 if none), and ``M`` never exceeds the range.
"""
from __future__ import annotations

import math

import numpy as np

C_SIG = 2.0
L_MIN_DAILY, L_MIN_MONTHLY = 5, 2


def flat_top(t):
    """The trapezoidal lag window ``λ(t)`` of Politis and Romano (1995), as Politis-White p. 58 write it."""
    a = np.abs(np.asarray(t, dtype=float))
    return np.where(a <= 0.5, 1.0, np.where(a <= 1.0, 2.0 * (1.0 - a), 0.0))


def autocov(x: np.ndarray, max_lag: int) -> np.ndarray:
    """``R̂(0..max_lag)`` for each row of ``x`` (shape ``(m, N)``), with the ``1/N`` divisor."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    n = x.shape[1]
    xc = x - x.mean(axis=1, keepdims=True)
    out = np.empty((x.shape[0], max_lag + 1))
    for k in range(max_lag + 1):
        out[:, k] = np.einsum("ij,ij->i", xc[:, : n - k], xc[:, k:]) / n
    return out


def k_n(n: int) -> int:
    return max(5, math.ceil(math.sqrt(math.log10(n))))


def m_hat(rho: np.ndarray, n: int) -> int:
    """``m̂`` from the autocorrelations ``rho[1..]`` (``rho[0]`` is lag 0) of a series of length ``n``."""
    kn = k_n(n)
    crit = C_SIG * math.sqrt(math.log10(n) / n)
    small = np.abs(rho) < crit
    top = len(rho) - 1
    for m in range(1, top - kn + 1):
        if small[m + 1 : m + kn + 1].all():
            return m
    big = np.flatnonzero(~small[1:]) + 1
    return int(big.max()) if big.size else 1


def pw_block_length(x: np.ndarray) -> np.ndarray:
    """``b̂_opt,SB`` for each row of ``x`` (not rounded, not capped). A constant row gives 1."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    n = x.shape[1]
    top = min(math.ceil(math.sqrt(n)) + k_n(n), n - 1)
    acv = autocov(x, top)
    out = np.ones(x.shape[0])
    for i, r in enumerate(acv):
        if r[0] <= 0:
            continue
        m = min(2 * m_hat(r / r[0], n), top)
        k = np.arange(1, m + 1)
        lam = flat_top(k / m)
        g_hat = 2.0 * np.sum(lam * k * r[1 : m + 1])
        g0 = r[0] + 2.0 * np.sum(lam * r[1 : m + 1])
        d_sb = 2.0 * g0 * g0
        if d_sb <= 0:
            continue
        out[i] = (2.0 * g_hat * g_hat / d_sb) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return out


def l_max(n: int) -> int:
    """Protocol v3 section 5.2: ``⌈min(3√n, n/3)⌉``."""
    return math.ceil(min(3.0 * math.sqrt(n), n / 3.0))


def protocol_block_length(d: np.ndarray, holding: int = 1, l_min: int = L_MIN_DAILY) -> float:
    """``L = min( max( Q90_k(b̂_k), H_f, L_min ), L_max )`` for a family's variants ``d`` (shape ``(m, n)``)."""
    d = np.atleast_2d(d)
    q90 = float(np.quantile(pw_block_length(d), 0.90))
    return float(min(max(q90, holding, l_min), l_max(d.shape[1])))


def theoretical_ar1(rho: float, n: int) -> float:
    """``b_opt,SB`` of an AR(1) with coefficient ``rho``: ``(2G²/D_SB)^(1/3) N^(1/3)`` with ``D_SB = 2g(0)²``."""
    return (abs(2.0 * rho / (1.0 - rho * rho))) ** (2.0 / 3.0) * n ** (1.0 / 3.0)
