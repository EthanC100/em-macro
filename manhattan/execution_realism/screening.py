"""Tier 1: HTE-shaped matrices with an execution lag (proportional costs; label at most ``screening_net``).

HTE (PR #89, ``manhattan/hte/kernels.py``) evaluates ``(n, A)`` position and return matrices with a same-close
fill. Its own next step 3 (``docs/manhattan/hte/LIMITATIONS.md`` section 4) is "an execution lag as a policy field
with default 1". This module is a plain reference implementation of that step, outside HTE, so that HTE's
vectorised kernels can be checked against it later. It does not import or change HTE.

**Alignment.** With warm-up ``W``, fence ``F`` and lag ``L``, the position earning day ``W + i`` is the row decided
at the close of day ``W − 1 − L + i``:

    align_lagged(P, R, W, F, L) = (P[W-1-L : F-1-L], R[W : F])

At ``L = 0`` this is HTE's ``kernels.align`` exactly. No row at or past the fence is read; the first ``L`` rows of
the window use decisions from before it, so ``W − 1 − L >= 0`` is required.

**The volatility-target trap.** HTE scales period ``i`` by an EWMA of the strategy's own returns ``g[:i]``. Shifting
the positions by ``L`` and keeping that rule would scale a position decided at close ``W − 1 − L + i`` with returns
up to close ``W − 1 + i``: ``L`` days the decision could not have seen. The scale must move with the decision:
``s[i]`` uses ``g[: i − L]`` only (``lagged_scales``). The tests show the naive version reads the future.

**Costs.** HTE's form, per unit notional: ``c·Σ|ΔW| + k·Σ|ΔW|^1.5`` on the scaled weights. ``costs.
hte_equivalent_coefficients`` maps a contract-level cost model onto ``(c, k)`` at a stated capital and liquidity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .errors import UnitError


def align_lagged(P: np.ndarray, R: np.ndarray, warmup: int, fence: int, lag: int) -> tuple[np.ndarray, np.ndarray]:
    if isinstance(lag, bool) or not isinstance(lag, int) or lag < 0:
        raise UnitError("lag is a whole number of days, 0 or more")
    if P.shape[0] < fence or R.shape[0] < fence:
        raise ValueError("arrays shorter than the fence")
    if warmup - 1 - lag < 0:
        raise UnitError(f"warm-up {warmup} leaves no decision row for lag {lag}")
    return P[warmup - 1 - lag: fence - 1 - lag], R[warmup:fence]


def lagged_scales(g: np.ndarray, active: np.ndarray, *, halflife: int, min_obs: int, target_daily: float,
                  cap: float, lag: int) -> np.ndarray:
    """Vol-target scale per earning period of one candidate: ``s[i]`` reads ``g[: i - lag]`` only. At ``lag = 0``
    it is HTE's ``_scales`` / ``ref_stage3_series`` rule, operation for operation."""
    n = g.shape[0]
    lam = 0.5 ** (1.0 / halflife)
    ev = wv = 0.0
    nobs = 0
    s0 = np.empty(n)
    for t in range(n):
        sd = math.sqrt(ev / wv) if wv > 0 else 0.0
        s0[t] = min(cap, target_daily / sd) if (nobs >= min_obs and sd > 0) else 1.0
        if active[t]:
            ev = ev * lam + (1 - lam) * (g[t] * g[t])
            wv = wv * lam + (1 - lam)
            nobs += 1
    if lag == 0:
        return s0
    s = np.ones(n)
    s[lag:] = s0[: n - lag]
    return s


@dataclass(frozen=True, eq=False)
class ScreeningResult:
    lag: int
    net: np.ndarray
    scale: np.ndarray
    turnover: float
    cost_sources: dict
    data_kind: str = "synthetic"
    tier: str = "proportional"


def series(P: np.ndarray, R: np.ndarray, *, warmup: int, fence: int, lag: int, c: float, k: float,
           vol_target_ann: float = 0.10, vol_halflife: int = 20, vol_min_obs: int = 20, leverage_cap: float = 5.0,
           cost_sources: dict | None = None, data_kind: str = "synthetic") -> ScreeningResult:
    """One candidate's net series under lag ``lag`` (HTE stage 3's arithmetic, in its operation order)."""
    Pw, Rw = align_lagged(P, R, warmup, fence, lag)
    n, A = Pw.shape
    g = np.zeros(n)
    active = np.zeros(n, bool)
    for t in range(n):
        acc = 0.0                       # plain += in asset order, as HTE: builtin sum() is compensated since 3.12
        for a in range(A):
            p = float(Pw[t, a])
            acc += p * float(Rw[t, a])
            active[t] = active[t] or p != 0.0
        g[t] = acc
    s = lagged_scales(g, active, halflife=vol_halflife, min_obs=vol_min_obs,
                      target_daily=vol_target_ann / math.sqrt(252.0), cap=leverage_cap, lag=lag)
    prevW = [0.0] * A
    out = np.zeros(n)
    turn = 0.0
    for t in range(n):
        lin = imp = 0.0
        for a in range(A):
            w = s[t] * float(Pw[t, a])
            d = abs(w - prevW[a])
            lin += d
            imp += d * math.sqrt(d)
            prevW[a] = w
        turn += lin
        out[t] = s[t] * g[t] - (c * lin + k * imp)
    return ScreeningResult(lag, out, s, turn / n, cost_sources or {}, data_kind)
