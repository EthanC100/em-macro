"""Trial T01: time-series trend (TSMOM) sleeve and the T01 combined strategy.

Pre-registration: docs/prereg/T01_ts_trend.md (committed before any T01 run).  v1.0 is not modified:
this module imports the frozen em_macro/systematic.py (tag v1.0-frozen, commit 7886867) and re-uses its
inputs, book weights, no-trade band, vol rule, cost model and execution lags.

    core sleeve   v1.0 with the composite = mean(carry z, value z)   (trend removed), at 10% vol
    trend sleeve  TREND = mean_k clip(sum_k r / (sigma sqrt(k/12)), -2, 2) / 2, k in {1, 3, 6, 12}
                  w_i = TREND_i * 0.10 / sigma_i / n_active, sigma = EWMA vol, centre of mass 60 trading
                  days (= 60/21 months on the monthly return series), then scaled to 10% vol
    T01           0.80 core + 0.20 trend, rescaled to 10% vol, 6x gross cap, 25% no-trade band, v1.0 costs
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import systematic as SY

TSMOM_K = (1, 3, 6, 12)
EWMA_COM_MONTHS = 60 / 21          # 60 trading days at 21 trading days a month
EWMA_MIN_MONTHS = 12
SLEEVE_TARGET_VOL = 0.10
RISK_BUDGET = {"core": 0.80, "trend": 0.20}
CORE_SIGNALS = ["carry", "value"]
BOOKS = ("fx", "bond")


# ============================================================ trend signal
def ewma_vol(r: pd.DataFrame, com: float = EWMA_COM_MONTHS, min_periods: int = EWMA_MIN_MONTHS) -> pd.DataFrame:
    """Annualised EWMA volatility of monthly returns (demeaned, bias-corrected pandas ewm std)."""
    return r.ewm(com=com, min_periods=min_periods).std() * np.sqrt(12)


def tsmom(r: pd.DataFrame, sigma: pd.DataFrame, ks=TSMOM_K) -> pd.DataFrame:
    """TREND = mean over k of clip(sum of the last k returns / (sigma * sqrt(k/12)), -2, 2) / 2.
    NaN unless all k-month windows are complete and sigma > 0."""
    sig = sigma.where(sigma > 0)
    parts = []
    for k in ks:
        sk = r.rolling(k, min_periods=k).sum()
        parts.append((sk / (sig * np.sqrt(k / 12))).clip(-2, 2) / 2)
    return sum(parts) / len(parts)          # NaN propagates: all k required


def trend_raw_weights(r: pd.DataFrame, target: float = SLEEVE_TARGET_VOL) -> pd.DataFrame:
    """w_i = TREND_i * target / sigma_i / n_active (n_active counted across all instruments)."""
    sigma = ewma_vol(r)
    trend = tsmom(r, sigma)
    active = trend.notna() & (sigma > 0)
    n = active.sum(axis=1).replace(0, np.nan)
    w = (trend * target / sigma).where(active).div(n, axis=0)
    return w.fillna(0.0)


# ============================================================ v1.0 machinery, re-used
def all_returns(inp: dict, books=BOOKS) -> pd.DataFrame:
    return pd.concat([inp[b]["ret"] for b in books], axis=1)


def scale_to_vol(W: pd.DataFrame, R: pd.DataFrame, target: float | None = None) -> pd.DataFrame:
    """v1.0's total-scaling rule (systematic.run): trailing 36-month pro-forma vol of the current
    weights, at least 12 months; scale 0 when undefined."""
    target = SY.DESIGN["portfolio_target_vol"] if target is None else target
    L, m = SY.DESIGN["vol_lookback_months"], SY.DESIGN["vol_min_months"]
    scale = pd.Series(np.nan, index=W.index)
    for t in W.index:
        hist = R.loc[:t].iloc[-L:].fillna(0.0)
        pv = (hist @ W.loc[t]).std() * np.sqrt(12) if len(hist) >= m else np.nan
        scale[t] = target / pv if pv and pv > 0 else 0.0
    return W.mul(scale.fillna(0.0), axis=0)


def core_targets(inp: dict, use=CORE_SIGNALS, books=BOOKS) -> pd.DataFrame:
    """v1.0's targets after the 10% total rescaling, before the leverage cap and band."""
    W = {b: SY.book_weights(inp[b], list(use)) for b in books}
    allW = pd.concat([W[b] * (0.5 if len(books) == 2 else 1.0) for b in books], axis=1)
    return scale_to_vol(allW, all_returns(inp, books))


def trend_targets(inp: dict, books=BOOKS) -> pd.DataFrame:
    R = all_returns(inp, books)
    return scale_to_vol(trend_raw_weights(R), R)


def mix(core: pd.DataFrame, trend: pd.DataFrame, w_core: float = RISK_BUDGET["core"]) -> pd.DataFrame:
    trend = trend.reindex(index=core.index, columns=core.columns).fillna(0.0)
    return w_core * core + (1 - w_core) * trend


def finish(inp: dict, targets: pd.DataFrame, books=BOOKS, band: float | None = None) -> pd.DataFrame:
    """v1.0's final steps (systematic.run): 6x gross cap, no-trade band, P&L with execution lags and
    per-instrument costs.  Output columns as systematic.run; attrs['weights'] = held weights."""
    months = inp["months"]
    lag = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}
    allW = targets.copy()
    gross = allW.abs().sum(axis=1)
    cap = SY.DESIGN["gross_leverage_cap"]
    allW = allW.mul(np.minimum(1.0, cap / gross.replace(0, np.nan)).fillna(0.0), axis=0)
    band = SY.DESIGN["no_trade_band"] if band is None else band
    if band:
        allW = SY._apply_band(allW, band)
    cost = pd.Series(inp["cost"]).reindex(allW.columns).values
    out = pd.DataFrame(index=months)
    for b in books:
        cols = inp[b]["ret"].columns
        w = allW[cols]
        pnl = (w.shift(lag[b]) * inp[b]["ret"]).sum(axis=1, min_count=1)
        tc = (w.diff().abs().shift(lag[b]) * cost[[allW.columns.get_loc(c) for c in cols]]).sum(axis=1)
        out[f"{b}_gross"] = pnl.fillna(0.0)
        out[f"{b}_cost"] = tc.fillna(0.0)
    out["gross"] = out[[f"{b}_gross" for b in books]].sum(axis=1)
    out["cost"] = out[[f"{b}_cost" for b in books]].sum(axis=1)
    out["net"] = out["gross"] - out["cost"]
    out["gross_leverage"] = allW.abs().sum(axis=1).shift(1)
    live = out["gross_leverage"].fillna(0) > 0
    first = live.idxmax() if live.any() else months[-1]
    out = out.loc[first:]
    out.attrs["weights"] = allW
    return out


# ============================================================ strategies
def run_t01(inp: dict, books=BOOKS) -> dict[str, pd.DataFrame]:
    """T01 combined plus its two stand-alone sleeves (each through the same final steps)."""
    R = all_returns(inp, books)
    core = core_targets(inp, CORE_SIGNALS, books)
    trend = trend_targets(inp, books)
    total = scale_to_vol(mix(core, trend), R)
    # the sleeve targets are already at 10% (v1.0 rule), so the stand-alone runs only add cap, band, costs;
    # finish(core) is identical to systematic.run(inp, ["carry", "value"]) (tested)
    return {"T01": finish(inp, total, books),
            "trend sleeve": finish(inp, trend, books),
            "core sleeve": finish(inp, core, books)}


def with_costs(inp: dict, mult: float) -> dict:
    return {**inp, "cost": {k: v * mult for k, v in inp["cost"].items()}}


def subset(inp: dict, instruments: list[str]) -> dict:
    """The inputs restricted to a list of instruments (for the cross-sectional holdout)."""
    keep = set(instruments)
    out = dict(inp)
    for b in BOOKS:
        cols = [c for c in inp[b]["ret"].columns if c in keep]
        out[b] = {k: v[cols] for k, v in inp[b].items()}
    return out
