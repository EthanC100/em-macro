"""FX data and moves for the election tracker (free public sources only).

Level x = -100 * ln(local currency per USD), so differences are % changes in the local
currency's USD value (+ = appreciation), exactly as in the study (em_macro/event_study.py).

Sources, in order: Yahoo Finance daily close via yfinance (the study's source for TRY, IDR
and PLN), then the ECB reference rate via frankfurter.app (14:15 CET; no COP/CLP/PEN/TWD).
Abnormal moves need DXY (Yahoo DX-Y.NYB) and US 10y / VIX (FRED, keyless CSV) and the frozen
2005-2021 factor betas, which exist only for the study's six countries.
"""
from __future__ import annotations

import datetime as dt
import io
import math

import numpy as np
import pandas as pd
import requests

from .rule import FROZEN, HOLD_DAYS, ewma_vol
from .wiki import UA

HORIZONS = (1, 5)


# ------------------------------------------------------------------ data
def _yahoo(ticker: str, start: str, end: str) -> pd.Series:
    import yfinance as yf
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    s = df["Close"]
    s = s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s.dropna().astype(float)


def _frankfurter(ccy: str, start: str, end: str) -> pd.Series:
    r = requests.get(f"https://api.frankfurter.app/{start}..{end}", params={"from": "USD", "to": ccy},
                     headers=UA, timeout=60)
    r.raise_for_status()
    rates = r.json().get("rates", {})
    s = pd.Series({pd.Timestamp(d): v[ccy] for d, v in rates.items() if ccy in v}, dtype=float)
    return s.sort_index()


def _fred(series_id: str, start: str) -> pd.Series:
    r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id, "cosd": start},
                     headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "v"]
    s = pd.to_numeric(df["v"], errors="coerce")
    s.index = pd.to_datetime(df["date"])
    return s.dropna()


def spot(ccy: str, ticker: str | None, start: str, end: str) -> tuple[pd.Series, str]:
    """Local currency per USD, daily. Returns (series, source label)."""
    if ticker:
        try:
            s = _yahoo(ticker, start, end)
            if len(s) > 20:
                return s, f"Yahoo {ticker}"
        except Exception as e:                  # fall through to the ECB rate
            print(f"Yahoo {ticker} failed: {e}")
    s = _frankfurter(ccy, start, end)
    return s, "ECB reference rate (frankfurter.app)"


def level(s: pd.Series) -> pd.Series:
    return -100.0 * np.log(s)


# ------------------------------------------------------------------ study windows
def window_dates(vote_date, horizons=HORIZONS) -> dict:
    """base = last weekday before the vote; day h = h-th weekday after it (study convention)."""
    d = pd.Timestamp(vote_date)
    bdays = pd.bdate_range(d - pd.Timedelta(days=10), d + pd.Timedelta(days=60))
    i, j = bdays.searchsorted(d, side="left"), bdays.searchsorted(d, side="right")
    return {"base": bdays[i - 1], **{h: bdays[j + h - 1] for h in horizons}}


def _at(x: pd.Series, d, after=None) -> float:
    """Last value on or before d, at most 7 calendar days stale; strictly after `after`."""
    v = x.loc[:d].dropna()
    if v.empty or (pd.Timestamp(d) - v.index[-1]).days > 7:
        return float("nan")
    if after is not None and v.index[-1] <= after:
        return float("nan")
    return float(v.iloc[-1])


def raw_moves(x: pd.Series, vote_date, horizons=HORIZONS) -> dict:
    w = window_dates(vote_date, horizons)
    base = x.loc[:w["base"]].dropna()
    if base.empty:
        return {h: float("nan") for h in horizons}
    b, b_date = float(base.iloc[-1]), base.index[-1]
    return {h: _at(x, w[h], b_date) - b for h in horizons}


def frozen_betas(iso2: str) -> dict | None:
    import json
    with open(FROZEN) as f:
        rows = json.load(f)["factor_betas"]
    return next((r for r in rows if r["asset"] == f"FX_{iso2}"), None)


def factor_levels(start: str, end: str) -> dict[str, pd.Series]:
    return {"DXY": 100 * np.log(_yahoo("DX-Y.NYB", start, end)),
            "US10": 100 * _fred("DGS10", start), "VIX": 100 * np.log(_fred("VIXCLS", start))}


def abnormal_moves(raw: dict, vote_date, betas: dict, factors: dict[str, pd.Series]) -> dict:
    """raw - [alpha * (h + 1) + sum b_f * d factor_f], as in event_study.event_moves."""
    w = window_dates(vote_date, tuple(raw))
    out = {}
    for h, r in raw.items():
        pred = betas["alpha_per_day"] * (h + 1)
        for f in ("DXY", "US10", "VIX"):
            pred += betas[f"b_{f}"] * (_at(factors[f], w[h]) - _at(factors[f], w["base"]))
        out[h] = r - pred
    return out


# ------------------------------------------------------------------ trade
def entry_date(results_known) -> pd.Timestamp:
    """Close of the first full trading day after the result: the first weekday after the
    date the result became known (local). Same-night results on a Sunday -> Monday."""
    d = pd.Timestamp(results_known)
    return pd.bdate_range(d + pd.Timedelta(days=1), d + pd.Timedelta(days=10))[0]


def exit_date(entry: pd.Timestamp, hold: int = HOLD_DAYS) -> pd.Timestamp:
    return pd.bdate_range(entry + pd.Timedelta(days=1), entry + pd.Timedelta(days=30))[hold - 1]


def sigma_daily(x: pd.Series, asof, n: int = 250) -> float:
    """EWMA (half-life 60) sd of daily changes in x, using data up to `asof`."""
    r = x.loc[:pd.Timestamp(asof)].dropna().diff().dropna().iloc[-n:]
    return ewma_vol(r.tolist())


def trade_return(x: pd.Series, entry: pd.Timestamp, direction: int, stop_pct: float,
                 hold: int = HOLD_DAYS) -> dict:
    """Signed % return from the entry close to the exit close, with a close-based stop."""
    ex = exit_date(entry, hold)
    path = x.loc[entry:ex].dropna()
    if path.empty or path.index[0] != entry or path.index[-1] < ex - pd.Timedelta(days=3):
        return {"trade_return_pct": float("nan"), "stopped": None, "exit": ex.date()}
    pnl = direction * (path - path.iloc[0])
    hit = pnl[pnl <= -stop_pct]
    if len(hit):
        return {"trade_return_pct": float(hit.iloc[0]), "stopped": True, "exit": hit.index[0].date()}
    return {"trade_return_pct": float(pnl.iloc[-1]), "stopped": False, "exit": path.index[-1].date()}


def is_nan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def today_str() -> str:
    return dt.date.today().isoformat()
