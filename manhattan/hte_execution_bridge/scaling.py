"""Volatility scaling with what was known at each decision, turned into decision-row weights.

HTE stage 3 scales period ``i`` of the evaluation window by an EWMA of the candidate's own unscaled returns
``g[:i]`` (``kernels._scales``). Under a lag ``L`` the position earning day ``W + i`` is decided at the close of
``W − 1 − L + i``; by then only ``g[: i − L]`` has been realised. ``execution_realism.screening.lagged_scales``
implements exactly that, and at ``L = 0`` it is HTE's rule bit for bit (cross-checked against PR #89).

``decision_weights`` returns, for every row of the panel, the vol-scaled target weight decided at that row's
close (``NaN`` outside the decision rows ``[W − 1 − L, F − 1 − L)``), so that the positions earn exactly the
evaluation window ``[W, F)`` HTE evaluates. ``g`` is computed from HTE's continuous returns of the *lagged,
unscaled* positions: public data and the candidate's own rule, both known at the decision. Changing any return
after a decision's close cannot change its weight (tested by perturbation).
"""
from __future__ import annotations

import numpy as np

from manhattan.execution_realism import screening as SC

from .errors import BridgeError


def decision_weights(P, R, *, warmup: int, fence: int, lag: int, vol_target_ann: float, vol_halflife: int,
                     vol_min_obs: int, leverage_cap: float) -> dict:
    P = np.asarray(P, float)
    R = np.asarray(R, float)
    if P.shape != R.shape or P.ndim != 2 or P.shape[0] < fence:
        raise BridgeError("positions and returns must have the same (days, assets) shape, at least to the fence")
    lo, hi = warmup - 1 - lag, fence - 1 - lag
    if lo < 0:
        raise BridgeError(f"warm-up {warmup} leaves no decision row for lag {lag}")
    if not np.isfinite(P[lo:hi]).all():
        raise BridgeError(f"positions are undefined in decision rows [{lo}, {hi}): raise the warm-up")
    s = SC.series(P, R, warmup=warmup, fence=fence, lag=lag, c=0.0, k=0.0, vol_target_ann=vol_target_ann,
                  vol_halflife=vol_halflife, vol_min_obs=vol_min_obs, leverage_cap=leverage_cap).scale
    W = np.full((fence, P.shape[1]), np.nan)
    W[lo:hi] = s[:, None] * P[lo:hi]
    W[lo:hi] += 0.0                                   # no negative zeros
    return {"weights": W, "scale": s, "rows": np.arange(lo, hi)}
