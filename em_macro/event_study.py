"""Event-study engine.

Timing convention (same for every event and every series)
---------------------------------------------------------
* event date  d = vote day / announcement day (local calendar date)
* base        b = last weekday strictly before d          ("day -1")
* horizon h   e_h = h-th weekday strictly after d           (h = 1, 5, 20)

A move "at h days" is level(e_h) - level(b); levels are the last available
observation on or before the date (max 5 days stale).  Day 1 therefore spans
the event day itself plus the next session, which captures the reaction
regardless of the time of day the news came out (Sunday elections -> Friday
close to Monday close; Copom after-close decision -> previous close to the next
day's close; intraday decisions are fully inside the window).

Units: FX = % change of the local currency's value in USD (positive =
appreciation); bonds = change in the 10y yield in basis points.

Abnormal moves remove same-window moves in DXY, US10Y and VIX using betas
estimated on 2005-2021 non-overlapping 5-day changes only (never on the
hold-out):  y = a + b1*dDXY + b2*dUS10 + b3*dlogVIX + e.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import COUNTRIES, FIT_END

HORIZONS = (1, 5, 20)
FACTORS = ["DXY", "US10", "VIX"]


def asset_levels(panel: pd.DataFrame) -> dict[str, pd.Series]:
    """Series used for moves, in units where differences are the reported move."""
    out = {"DXY": 100 * np.log(panel["DXY"]), "US10": 100 * panel["US10Y"], "VIX": 100 * np.log(panel["VIX"])}
    for c in COUNTRIES:
        out[f"FX_{c}"] = -100 * np.log(panel[f"FX_{c}"])          # % value of local ccy in USD
        if f"Y10_{c}" in panel:
            out[f"Y10_{c}"] = 100 * panel[f"Y10_{c}"]                # bp
    return out


def factor_betas(levels: dict, step: int = 5, end: str = FIT_END) -> pd.DataFrame:
    """OLS of non-overlapping `step`-day changes on factor changes, fit sample only."""
    rows = []
    levels = {k: v.ffill(limit=5) for k, v in levels.items()}
    X = pd.concat({f: levels[f] for f in FACTORS}, axis=1).loc[:end]
    for k, s in levels.items():
        if k in FACTORS:
            continue
        df = pd.concat([s.loc[:end].rename("y"), X], axis=1).iloc[::step].diff().dropna()
        if len(df) < 100:
            continue
        m = sm.OLS(df["y"], sm.add_constant(df[FACTORS])).fit()
        rows.append({"asset": k, "alpha_per_day": m.params["const"] / step,
                     **{f"b_{f}": m.params[f] for f in FACTORS}, "r2": m.rsquared,
                     "resid_sd_per_day": np.sqrt(m.scale / step), "n": int(m.nobs),
                     "start": df.index[0].date(), "end": df.index[-1].date()})
    return pd.DataFrame(rows).set_index("asset")


def window_dates(event_date, bdays: pd.DatetimeIndex, horizons=HORIZONS) -> dict:
    d = pd.Timestamp(event_date)
    i = bdays.searchsorted(d, side="left")          # first weekday >= d
    j = bdays.searchsorted(d, side="right")         # first weekday  > d
    out = {"base": bdays[i - 1] if i > 0 else None}
    for h in horizons:
        out[h] = bdays[j + h - 1] if j + h - 1 < len(bdays) else None
    return out


def _at(s: pd.Series, d, after=None):
    """Last observation on or before d (at most 7 calendar days, i.e. 5 weekdays,
    stale -- the same tolerance as forward-filling 5 weekdays); if `after` is
    given, the observation must be dated strictly after it (so a window end
    never reuses the base-day price when the series has stopped updating)."""
    if d is None:
        return np.nan
    v = s.loc[:d].dropna()
    if v.empty or (pd.Timestamp(d) - v.index[-1]).days > 7:
        return np.nan
    if after is not None and v.index[-1] <= after:
        return np.nan
    return v.iloc[-1]


def _obs_date(s: pd.Series, d):
    v = s.loc[:d].dropna() if d is not None else s.iloc[:0]
    return v.index[-1] if len(v) else None


def event_moves(events: pd.DataFrame, levels: dict, betas: pd.DataFrame,
                horizons=HORIZONS) -> pd.DataFrame:
    """One row per event x asset (own-country FX and 10y) with raw and abnormal
    moves at each horizon, plus the post-day-1 moves used for drift tests."""
    bdays = pd.bdate_range("2004-12-01", "2027-12-31")
    rows = []
    for ev in events.itertuples():
        w = window_dates(ev.event_date, bdays, horizons)
        # factors: a US holiday (no fresh print) correctly counts as no move
        fac = {f: {h: _at(levels[f], w[h]) - _at(levels[f], w["base"]) for h in horizons} for f in FACTORS}
        for kind in ("FX", "Y10"):
            key = f"{kind}_{ev.country}"
            if key not in levels or key not in betas.index:
                continue
            s, b = levels[key], betas.loc[key]
            base, base_obs = _at(s, w["base"]), _obs_date(s, w["base"])
            r = {"event_id": ev.event_id, "asset": kind, "country": ev.country, "base_date": w["base"]}
            for h in horizons:
                raw = _at(s, w[h], base_obs) - base
                ndays = h + 1                               # weekdays from base to e_h
                pred = b.alpha_per_day * ndays + sum(b[f"b_{f}"] * fac[f][h] for f in FACTORS)
                r[f"raw_{h}"] = raw
                r[f"ab_{h}"] = raw - pred
                r[f"sd_{h}"] = b.resid_sd_per_day * np.sqrt(ndays)    # normal-time sd of ab_h
                for f in FACTORS:
                    r[f"{f}_{h}"] = fac[f][h]
            for h in horizons[1:]:
                r[f"post_{h}"] = r[f"ab_{h}"] - r[f"ab_1"]               # move from day 1 to day h
                r[f"postraw_{h}"] = r[f"raw_{h}"] - r[f"raw_1"]
            rows.append(r)
    out = pd.DataFrame(rows)
    return out.merge(events, on=["event_id", "country"], how="left")


def summarize(m: pd.DataFrame, by: list[str], horizons=HORIZONS) -> pd.DataFrame:
    """Mean/median abnormal move, cross-sectional t, standardized z (each move
    divided by its normal-time sd, Boehmer-style), and the ratio of the mean
    squared abnormal move to its normal-time variance (>1 = event moves are
    bigger than ordinary days)."""
    rows = []
    for key, g in m.groupby(by, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        for h in horizons:
            x = g[f"ab_{h}"].dropna()
            if len(x) == 0:
                continue
            sd = g.loc[x.index, f"sd_{h}"]
            z = x / sd
            n = len(x)
            rows.append({**dict(zip(by, key)), "h": h, "n": n,
                         "mean_raw": g[f"raw_{h}"].mean(), "mean_ab": x.mean(), "median_ab": x.median(),
                         "mean_abs_ab": x.abs().mean(),
                         "t_cs": x.mean() / (x.std(ddof=1) / np.sqrt(n)) if n > 2 else np.nan,
                         "z_bmp": z.mean() / (z.std(ddof=1) / np.sqrt(n)) if n > 2 else np.nan,
                         "var_ratio": (z ** 2).mean(), "share_pos": (x > 0).mean()})
    return pd.DataFrame(rows)


def drift_regression(m: pd.DataFrame, h: int, kind: str = "ab") -> dict:
    """post_h = a + b * day1 : b>0 continuation (drift), b<0 reversal.
    kind='ab' uses factor-adjusted moves, kind='raw' unadjusted moves (the
    tradeable version: the raw day-1 move is known at the day-1 price).
    Moves are standardized by normal-time sd so countries are comparable."""
    x1, post = ("ab_1", f"post_{h}") if kind == "ab" else ("raw_1", f"postraw_{h}")
    d = m[[x1, post, "sd_1"]].dropna()
    if len(d) < 8:
        return {"n": len(d)}
    x = d[x1] / d["sd_1"]
    y = d[post] / d["sd_1"]
    res = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HC1")
    return {"n": len(d), "slope": res.params.iloc[1], "t": res.tvalues.iloc[1], "p": res.pvalues.iloc[1],
            "intercept": res.params.iloc[0], "r2": res.rsquared}


def placebo_events(events: pd.DataFrame, start: str, end: str, step: int = 7, gap: int = 3) -> pd.DataFrame:
    """Pseudo-events: every `step`-th weekday per country, excluding weekdays
    within `gap` weekdays of a real event of that country."""
    bdays = pd.bdate_range(start, end)
    rows = []
    for c in COUNTRIES:
        real = pd.DatetimeIndex(events.loc[events.country == c, "event_date"])
        pos = bdays.searchsorted(real)
        near = set()
        for p in pos:
            near.update(range(p - gap, p + gap + 1))
        for i in range(0, len(bdays), step):
            if i not in near:
                rows.append({"event_id": f"PB_{c}_{bdays[i]:%Y%m%d}", "country": c, "event_type": "placebo",
                             "subtype": "placebo", "event_date": bdays[i]})
    return pd.DataFrame(rows)
