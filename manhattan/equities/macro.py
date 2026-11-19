"""Macro and cross-asset interactions: point-in-time macro inputs, sensitivities and an incremental-information
diagnostic. Candidate mechanisms only (catalogue family F); nothing here establishes a predictive relation.

**Macro data come through the existing door.** Vintaged macro series (yields, policy expectations, credit spreads,
energy prices, FX) live in a ``manhattan.engine.pit.PitStore`` and are read through a ``Window`` that
``manhattan.roles.check_read`` granted. ``macro_as_of`` only wraps ``Window.as_of``: the equity package does not
build a second macro store and does not modify the existing one.

**Sensitivities from the past only.** ``sensitivity`` regresses a stock's returns on a macro change and the market
over the ``window`` sessions up to and including ``as_of`` (``days <= as_of``); later observations cannot change it.

**Incremental, not raw.** ``incremental_information`` asks whether a feature says anything about a target once
controls (market, sector, common factors) are partialled out of both; it returns the partial correlation and the
gain in R². It is a descriptive exploration statistic with zero evidential weight: a test is a frozen hypothesis
evaluated under Protocol v3.1, not this function.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from .errors import EquityDataError


def macro_as_of(window, series: str, t: date, n: int | None = None):
    """(periods, values) of a macro series as known at the close of ``t`` (``manhattan.engine.pit.Window``)."""
    return window.as_of(series, t, n)


def sensitivity(days, stock: np.ndarray, macro_change: np.ndarray, market: np.ndarray, as_of: date, *,
                window: int = 252, min_obs: int = 126) -> dict:
    """Loadings of ``stock`` on ``macro_change`` and ``market`` over the last ``window`` sessions up to ``as_of``."""
    keep = np.array([d <= as_of for d in days], bool)
    y, m, k = (np.asarray(a, float)[keep][-window:] for a in (stock, macro_change, market))
    ok = np.isfinite(y) & np.isfinite(m) & np.isfinite(k)
    if ok.sum() < min_obs:
        raise EquityDataError(f"{int(ok.sum())} observations up to {as_of}; need {min_obs}")
    X = np.column_stack([np.ones(ok.sum()), m[ok], k[ok]])
    b, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    return {"macro": float(b[1]), "market": float(b[2]), "n": int(ok.sum()), "as_of": as_of}


def _resid(y: np.ndarray, C: np.ndarray) -> np.ndarray:
    X = np.column_stack([np.ones(len(y)), C]) if C.size else np.ones((len(y), 1))
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ b


def incremental_information(feature: np.ndarray, target: np.ndarray, controls: np.ndarray) -> dict:
    """Partial correlation of ``feature`` and ``target`` given ``controls`` (rows are observations), and the R²
    gained by adding the feature to a regression of the target on the controls. Descriptive only."""
    f, y = np.asarray(feature, float), np.asarray(target, float)
    C = np.asarray(controls, float).reshape(len(y), -1)
    ok = np.isfinite(f) & np.isfinite(y) & np.isfinite(C).all(1)
    f, y, C = f[ok], y[ok], C[ok]
    if ok.sum() <= C.shape[1] + 3:
        raise EquityDataError("too few observations for the controls")
    rf, ry = _resid(f, C), _resid(y, C)
    den = np.sqrt((rf @ rf) * (ry @ ry))
    pc = float(rf @ ry / den) if den > 0 else 0.0
    tss = ((y - y.mean()) ** 2).sum()
    r2_c = 1 - (ry @ ry) / tss if tss > 0 else 0.0
    r_full = _resid(y, np.column_stack([C, f]))
    r2_f = 1 - (r_full @ r_full) / tss if tss > 0 else 0.0
    return {"partial_corr": pc, "r2_controls": float(r2_c), "r2_gain": float(r2_f - r2_c), "n": int(ok.sum()),
            "evidential_weight": 0}
