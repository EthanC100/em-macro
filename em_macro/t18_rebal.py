"""Trial T18: turnover reduction (pre-registration docs/prereg/T16-T19_risk_batch.md, section 3.3).

The one change to v1.0: its 25% relative no-trade band is replaced by the spec's two rebalancing rules
(spec section 8) with the spec's values:

    band in risk units   trade only if |delta w_i| * sigma_i > 0.1 * the position's risk budget
    partial rebalancing  w_new = w + 0.5 * (w* - w)

w* = v1.0's targets after the 10% rescaling and the 6x cap (identical to v1.0's pre-band targets);
sigma_i = v1.0's 36-month vol; the position's risk budget = the equal risk v1.0 gives each selected
position of its book, b_{book,t} = mean |w*_i| sigma_i over the book's selected instruments.  The band
is applied to the proposed half-trade; the residual of an exited position (target 0) is closed once its
half-trade falls inside the band.  Everything else is v1.0's (frozen em_macro/systematic.py, imported).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import systematic as SY
from . import tstrend as TS

BAND_RISK = 0.10        # spec section 8: 0.1 x the position's risk budget
PARTIAL = 0.5           # spec section 8: w_new = w + 0.5 (w* - w)
V1 = ["carry", "trend", "value"]
LAG = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}


def capped_targets(inp: dict, books=TS.BOOKS) -> pd.DataFrame:
    """v1.0's targets after the 10% total rescaling and the 6x gross cap (its pre-band weights)."""
    W = TS.core_targets(inp, V1, books)
    gross = W.abs().sum(axis=1)
    return W.mul(np.minimum(1.0, SY.DESIGN["gross_leverage_cap"] / gross.replace(0, np.nan)).fillna(0.0), axis=0)


def instrument_vol(inp: dict, books=TS.BOOKS) -> pd.DataFrame:
    return pd.concat([SY._vol(inp[b]["ret"]) for b in books], axis=1)


def book_of(inp: dict, books=TS.BOOKS) -> dict[str, str]:
    return {c: b for b in books for c in inp[b]["ret"].columns}


def apply_rules(target: pd.DataFrame, sigma: pd.DataFrame, book: dict[str, str],
                band: float = BAND_RISK, partial: float = PARTIAL) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Held weights under the risk-unit band and partial rebalancing.  Returns (held, log) where log
    records per month and instrument the proposed trade, whether it cleared the band, and the budget.
    With band = 0 and partial = 1 every target is traded in full (v1.0 with no band)."""
    held = target.copy() * 0.0
    prev = pd.Series(0.0, index=target.columns)
    rows = []
    books = sorted(set(book.values()))
    for t in target.index:
        tgt = target.loc[t]
        sig = sigma.loc[t].reindex(target.columns)
        budget = {}
        for b in books:
            cols = [c for c in target.columns if book[c] == b]
            sel = [c for c in cols if tgt[c] != 0]
            budget[b] = float((tgt[sel].abs() * sig[sel]).mean()) if sel else np.nan
        new = prev.copy()
        for c in target.columns:
            gap = tgt[c] - prev[c]
            delta = partial * gap
            b = budget[book[c]]
            risk = abs(delta) * sig[c]
            if np.isnan(b):                       # no selected position in the book: trade to target (zero)
                traded, new[c] = gap != 0, tgt[c]
            elif pd.isna(sig[c]) and prev[c] != 0:  # no vol for a held position: trade
                traded, new[c] = delta != 0, prev[c] + delta
            elif risk > band * b:
                traded, new[c] = True, prev[c] + delta
            elif tgt[c] == 0 and prev[c] != 0:    # residual of an exited position: closed
                traded, new[c] = True, 0.0
            else:
                traded = False
            if gap != 0:
                rows.append({"month": str(t), "instrument": c, "target": tgt[c], "held_before": prev[c],
                             "proposed_trade": delta, "trade_risk": risk, "budget": b,
                             "traded": traded, "executed": new[c] - prev[c]})
        prev = new
        held.loc[t] = prev
    return held, pd.DataFrame(rows)


def pnl(inp: dict, held: pd.DataFrame, books=TS.BOOKS) -> pd.DataFrame:
    """v1.0's P&L accounting (systematic.run) on given held weights: execution lags, per-instrument costs."""
    months = inp["months"]
    cost = pd.Series(inp["cost"]).reindex(held.columns).values
    out = pd.DataFrame(index=months)
    for b in books:
        cols = inp[b]["ret"].columns
        w = held[cols]
        p = (w.shift(LAG[b]) * inp[b]["ret"]).sum(axis=1, min_count=1)
        tc = (w.diff().abs().shift(LAG[b]) * cost[[held.columns.get_loc(c) for c in cols]]).sum(axis=1)
        out[f"{b}_gross"] = p.fillna(0.0)
        out[f"{b}_cost"] = tc.fillna(0.0)
    out["gross"] = out[[f"{b}_gross" for b in books]].sum(axis=1)
    out["cost"] = out[[f"{b}_cost" for b in books]].sum(axis=1)
    out["net"] = out["gross"] - out["cost"]
    out["gross_leverage"] = held.abs().sum(axis=1).shift(1)
    live = out["gross_leverage"].fillna(0) > 0
    first = live.idxmax() if live.any() else months[-1]
    out = out.loc[first:]
    out.attrs["weights"] = held
    return out


def run(inp: dict, books=TS.BOOKS, band: float = BAND_RISK, partial: float = PARTIAL) -> tuple[pd.DataFrame, pd.DataFrame]:
    """T18 monthly P&L and the trade log."""
    tgt = capped_targets(inp, books)
    held, log = apply_rules(tgt, instrument_vol(inp, books), book_of(inp, books), band, partial)
    return pnl(inp, held, books), log
