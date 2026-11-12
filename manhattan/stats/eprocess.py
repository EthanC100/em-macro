"""The forward betting process of Protocol v3 section 6 (also replayed through the reserve window, section 4.5).

For one component (a hypothesis portfolio or the family portfolio) with daily returns ``P``:

    daily scale     s_d   = max( EWMA standard deviation of P over days before d, half-life 60 ,  s_floor )
    test period     one week of trading days;  P_w = the week's summed return
    weekly scale    s_w   = √(days in the week) · s_d on the week's first day   (so it uses only earlier days)
    standardised    Z_w   = P_w / s_w ;          truncated  Y_w = max( Z_w, −c ),  c = 6
    variance ratio  VR̂   = 1 + 2 Σ_{j=1}^{4} (1 − j/5) ρ̂_j  over the 252 daily standardised returns before the
                            week;  VR̂ > 1.25  ⇒  no bet that week
    wealth          W     = (1/6) Σ_{λ in Λ} Π_w ( 1 + λ Y_w ),   Λ = { 0.9/c · 2^(−j) : j = 0..5 }
    family          W_f   = mean of its components' wealth (each started at 1 at the same week)
    guard           the one-sided asymptotic confidence sequence of section 6.3 on the untruncated Z

Everything used for week ``w`` (scale, bet-or-not, the six fractions) is a function of days before the week. The
EWMA standard deviation is taken about zero (a root mean square), with weights renormalised over the days
available, so a short history is an average of what exists and not a value biased towards zero.

Arrays are ``(components, days)`` or ``(components, weeks)``; weeks are consecutive blocks of ``DAYS`` days
counted from a given first day.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import lfilter

C_WEEKLY = 6.0
DAYS = 5
HALF_LIFE = 60.0
N_LAMBDA = 6
VR_WINDOW, VR_LIMIT, VR_LAGS = 252, 1.25, 4
GUARD_M, ALPHA_G = 52, 0.05


def lambdas(c: float = C_WEEKLY) -> np.ndarray:
    """``Λ`` of section 6.4: ``0.9/c · 2^(−j)``, ``j = 0..5`` (0.15, 0.075, ... for ``c = 6``)."""
    return 0.9 / c * 2.0 ** -np.arange(N_LAMBDA)


def daily_scale(P: np.ndarray, floor: float, half_life: float = HALF_LIFE) -> np.ndarray:
    """``s_d`` for every day: ``s[..., d]`` uses ``P[..., :d]`` only. With no history it is the floor."""
    P = np.asarray(P, dtype=float)
    a = 0.5 ** (1.0 / half_life)
    num = lfilter([0.0, 1.0], [1.0, -a], P * P, axis=-1)            # Σ_{u<d} a^(d−1−u) P_u²
    den = lfilter([0.0, 1.0], [1.0, -a], np.ones(P.shape[-1]))      # Σ_{u<d} a^(d−1−u)
    with np.errstate(invalid="ignore", divide="ignore"):
        ewma = np.sqrt(np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0))
    return np.maximum(ewma, floor)


def variance_ratio(z: np.ndarray) -> float:
    """``VR̂`` of one window of daily standardised returns (the reference form of section 6.7)."""
    z = np.asarray(z, dtype=float)
    x = z - z.mean()
    den = float(x @ x)
    if den <= 0:
        return 1.0
    return 1.0 + 2.0 * sum((1.0 - j / 5.0) * float(x[j:] @ x[:-j]) / den for j in range(1, VR_LAGS + 1))


def weekly_variance_ratio(z: np.ndarray, first_day: int, n_weeks: int) -> np.ndarray:
    """``VR̂`` before each week: week ``w`` starts on day ``first_day + 5w`` and looks at the 252 days before it.
    Shape ``(components, n_weeks)``. A week with fewer than 252 earlier days gets 1 (the rule cannot fire)."""
    z = np.atleast_2d(np.asarray(z, dtype=float))
    out = np.ones((z.shape[0], n_weeks))
    starts = first_day + DAYS * np.arange(n_weeks)
    ok = starts >= VR_WINDOW
    if not ok.any():
        return out
    win = np.lib.stride_tricks.sliding_window_view(z, VR_WINDOW, axis=1)[:, starts[ok] - VR_WINDOW, :]
    x = win - win.mean(axis=2, keepdims=True)
    den = np.einsum("kwi,kwi->kw", x, x)
    vr = np.ones(den.shape)
    for j in range(1, VR_LAGS + 1):
        vr += 2.0 * (1.0 - j / 5.0) * np.einsum("kwi,kwi->kw", x[:, :, j:], x[:, :, :-j]) / np.where(den > 0, den, 1)
    out[:, ok] = np.where(den > 0, vr, 1.0)
    return out


def weekly_inputs(P: np.ndarray, first_day: int, n_weeks: int, floor: float, c: float = C_WEEKLY) -> dict:
    """Standardised weekly returns and the bet-or-not decision for ``n_weeks`` weeks from day ``first_day``.

    ``P`` is ``(components, days)`` and must hold the days before ``first_day`` that supply the start-up history.
    Returns ``Z`` (untruncated), ``Y`` (truncated at ``−c``), ``bet`` (False where ``VR̂ > 1.25``), ``vr`` and the
    weekly scale ``s``, each ``(components, n_weeks)``.
    """
    P = np.atleast_2d(np.asarray(P, dtype=float))
    last = first_day + DAYS * n_weeks
    if last > P.shape[1]:
        raise ValueError("not enough days for that many weeks")
    s_d = daily_scale(P, floor)
    week_sum = P[:, first_day:last].reshape(P.shape[0], n_weeks, DAYS).sum(axis=2)
    s_w = math.sqrt(DAYS) * s_d[:, first_day:last:DAYS]
    Z = week_sum / s_w
    vr = weekly_variance_ratio(P / s_d, first_day, n_weeks)
    return {"Z": Z, "Y": np.maximum(Z, -c), "bet": vr <= VR_LIMIT, "vr": vr, "s": s_w}


def log_increments(Y: np.ndarray, bet: np.ndarray, c: float = C_WEEKLY) -> np.ndarray:
    """``ln(1 + λ Y_w)`` for each ``λ`` in ``Λ``, zero where no bet is placed: ``(components, 6, weeks)``."""
    lam = lambdas(c)[None, :, None]
    return np.where(bet[:, None, :], np.log1p(lam * Y[:, None, :]), 0.0)


def cumulative_log(inc: np.ndarray) -> np.ndarray:
    """Running sums with a leading zero: ``cum[..., j]`` is the log-growth of the first ``j`` weeks."""
    out = np.zeros(inc.shape[:-1] + (inc.shape[-1] + 1,))
    np.cumsum(inc, axis=-1, out=out[..., 1:])
    return out


def wealth_paths(cum: np.ndarray, start: int = 0) -> np.ndarray:
    """Component wealth after each week from ``start`` (wealth 1 before week ``start``):
    ``(components, weeks − start + 1)``, first column 1. Each is the equal-weight mean of six products."""
    return np.exp(cum[:, :, start:] - cum[:, :, start : start + 1]).mean(axis=1)


def family_wealth(component_wealth: np.ndarray) -> np.ndarray:
    """Section 6.5: the equal-weight mean of the components' wealth."""
    return component_wealth.mean(axis=0)


def guard_lower(Z: np.ndarray, alpha_g: float = ALPHA_G, m: int = GUARD_M) -> np.ndarray:
    """``low_t`` of section 6.3 after each of the weeks in ``Z`` (``(components, weeks)``), counted from the
    first column. Entries before week ``m`` are ``-inf`` (the guard cannot hold before 52 weeks)."""
    Z = np.atleast_2d(np.asarray(Z, dtype=float))
    k, w = Z.shape
    out = np.full((k, w), -np.inf)
    if w < m:
        return out
    t = np.arange(1, w + 1, dtype=float)
    mu = np.cumsum(Z, axis=1) / t
    var = np.maximum(np.cumsum(Z * Z, axis=1) / t - mu * mu, 0.0)
    var_m = var[:, m - 1]
    good = var_m > 0
    la = -2.0 * math.log(alpha_g)
    rho2 = np.where(good, (la + math.log(la) + 1.0) / (np.where(good, var_m, 1.0) * m * math.log(m)), np.nan)[:, None]
    a = t * var * rho2 + 1.0
    width = np.sqrt(2.0 * a / (t * t * rho2) * np.log(1.0 + np.sqrt(a) / (2.0 * alpha_g)))
    low = mu - width
    out[:, m - 1 :] = np.where(good[:, None], low, -np.inf)[:, m - 1 :]
    return out


def family_guard(component_wealth: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """Whether the guard holds after each week: the lower end for the **leading** component (largest wealth
    after that week) is above zero. ``component_wealth`` is ``(components, weeks + 1)`` from ``wealth_paths``;
    ``Z`` is ``(components, weeks)`` over the same weeks. Returns ``(weeks,)`` booleans."""
    low = guard_lower(Z)
    lead = np.argmax(component_wealth[:, 1:], axis=0)
    return low[lead, np.arange(low.shape[1])] > 0.0


def tail_record(Z: np.ndarray, Y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``N_trunc`` (weeks truncated) and tail debt ``D = Σ (Y − Z) ≥ 0`` for each component."""
    return np.count_nonzero(Y > Z, axis=-1), (Y - Z).sum(axis=-1)
