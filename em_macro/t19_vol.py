"""Trial T19: volatility forecasting for sizing (pre-registration docs/prereg/T16-T19_risk_batch.md, section 3.4).

The one change to v1.0: its volatility estimate (trailing 36-month standard deviation x sqrt(12), min 12
months) is replaced, at every point where v1.0 uses it, by the spec's floored EWMA (spec section 7):

    sigma_est = max( sigma_EWMA(HL 60 days), 0.8 * sigma_EWMA(HL 250 days) )
    sigma_EWMA(HL)_t = sqrt( 12 * EWM_mean(x^2; halflife HL months, adjust=True, min_periods=12)_t )

on monthly returns, half-lives 60/21 and 250/21 months.  It applies to (1) the instrument volatility in
book_weights, (2) the book scaler and (3) the total scaler.  Everything else is v1.0's, imported from the
frozen em_macro/systematic.py (never modified): signals, thirds, 50/50 mix, 6x cap, 25% band, costs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import systematic as SY
from . import tstrend as TS

HL_SHORT_MONTHS = 60 / 21          # 60 trading days
HL_LONG_MONTHS = 250 / 21          # 250 trading days
FLOOR = 0.8
MIN_MONTHS = 12
V1 = ["carry", "trend", "value"]


def ewma_sigma(x, hl: float, min_periods: int = MIN_MONTHS):
    """Annualised zero-mean EWMA volatility of monthly returns (Series or DataFrame)."""
    return np.sqrt(12.0 * (x ** 2).ewm(halflife=hl, min_periods=min_periods, adjust=True).mean())


def vol_est(x):
    """sigma_est = max(EWMA short, FLOOR * EWMA long); NaN where either is undefined."""
    s, l = ewma_sigma(x, HL_SHORT_MONTHS), ewma_sigma(x, HL_LONG_MONTHS)
    return np.maximum(s, FLOOR * l)


def v1_vol_fn(x):
    """v1.0's own estimator (for the identity test): trailing 36-month std x sqrt(12), min 12."""
    return x.rolling(SY.DESIGN["vol_lookback_months"], min_periods=SY.DESIGN["vol_min_months"]).std() * np.sqrt(12)


def _last_vol(x: pd.Series, vol_fn) -> float:
    v = vol_fn(x).iloc[-1]
    return float(v) if pd.notna(v) else np.nan


def book_weights(book: dict, use: list[str], vol_fn=vol_est) -> pd.DataFrame:
    """systematic.book_weights with the volatility estimator replaced (instrument vol and book scaler).
    With vol_fn = v1_vol_fn it reproduces v1.0 exactly (the book scaler then sees the same 36 months)."""
    sig = SY.signals(book)
    comp = pd.concat([sig[k] for k in use], keys=use).groupby(level=1).mean().reindex(book["ret"].index)
    r = book["ret"]
    vol = vol_fn(r)
    W = pd.DataFrame(0.0, index=r.index, columns=r.columns)
    for t in r.index:
        s = comp.loc[t].dropna()
        s = s[vol.loc[t, s.index].notna()]
        n = len(s) // 3
        if len(s) < 3 or n == 0:
            continue
        rk = s.sort_values()
        raw = pd.Series(0.0, index=r.columns)
        raw[rk.index[-n:]] = 1 / vol.loc[t, rk.index[-n:]]
        raw[rk.index[:n]] = -1 / vol.loc[t, rk.index[:n]]
        hist = r.loc[:t].fillna(0.0)
        pv = _last_vol(hist @ raw, vol_fn)
        if pv > 0:
            W.loc[t] = raw * SY.DESIGN["book_target_vol"] / pv
    return W


def scale_to_vol(W: pd.DataFrame, R: pd.DataFrame, vol_fn=vol_est, target: float | None = None) -> pd.DataFrame:
    """The total scaler with the estimator replaced: pv = vol_fn(pro-forma series up to t)."""
    target = SY.DESIGN["portfolio_target_vol"] if target is None else target
    scale = pd.Series(np.nan, index=W.index)
    for t in W.index:
        hist = R.loc[:t].fillna(0.0)
        pv = _last_vol(hist @ W.loc[t], vol_fn) if len(hist) >= MIN_MONTHS else np.nan
        scale[t] = target / pv if pv and pv > 0 else 0.0
    return W.mul(scale.fillna(0.0), axis=0)


def targets(inp: dict, books=TS.BOOKS, vol_fn=vol_est) -> pd.DataFrame:
    """T19 target weights after the 10% total rescaling (before the 6x cap and the band)."""
    W = {b: book_weights(inp[b], V1, vol_fn) for b in books}
    allW = pd.concat([W[b] * (0.5 if len(books) == 2 else 1.0) for b in books], axis=1)
    return scale_to_vol(allW, TS.all_returns(inp, books), vol_fn)


def run(inp: dict, books=TS.BOOKS, vol_fn=vol_est) -> pd.DataFrame:
    """T19 monthly P&L (systematic.run's output columns; attrs['weights'] = held weights)."""
    return TS.finish(inp, targets(inp, books, vol_fn), books)


def floor_binds(x) -> pd.DataFrame:
    """Where the long-run floor sets the estimate (FLOOR * long > short)."""
    s, l = ewma_sigma(x, HL_SHORT_MONTHS), ewma_sigma(x, HL_LONG_MONTHS)
    return (FLOOR * l > s) & s.notna() & l.notna()
