"""A4 diagnostic step (c): AQR's documented commodity carry construction, computed once on our Norgate data.

Specification: results/T20-T22/build0_a4_diagnostic.md, "(c) ... specification", committed before this ran.
Writes the factor series privately; returns only its correlation with AQR's "Commodities Carry".
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import commod_build0 as B
from . import commod_data as CD

START, END = pd.Period("1990-01", "M"), pd.Period("2026-02", "M")


def market_inputs(code: str) -> pd.DataFrame:
    """Per month t: carry at month-end t-1 and the return in month t (spec items 2-4)."""
    md = CD.MarketData(code)
    close = md.close
    ym = {c: y * 12 + m for c, (y, m) in ((c, CD.parse_contract(c)) for c in close.columns)}
    order = sorted(close.columns, key=lambda c: ym[c])
    days = close.index
    month_end = pd.Series(days, index=days).groupby(days.to_period("M")).max()   # item 2
    lead = 3 if code == "B" else 2
    rows = []
    for t in pd.period_range(START, END, freq="M"):
        if t - 1 not in month_end.index or t not in month_end.index:
            continue
        e0, e1 = month_end[t - 1], month_end[t]
        p0, p1 = close.loc[e0], close.loc[e1]
        # item 3: carry at month-end t-1 from the two nearest contracts with a settlement that day
        quoted = [c for c in order if np.isfinite(p0[c])]
        carry = np.nan
        if len(quoted) >= 2:
            fn, fx = p0[quoted[0]], p0[quoted[1]]
            if fn > 0 and fx > 0:
                carry = (fn - fx) / fx
        # item 4: desired contract and fallbacks
        tym = t.year * 12 + t.month
        k = next((i for i, c in enumerate(order) if ym[c] >= tym + lead), None)
        ret = np.nan
        if k is not None:
            tries = order[k:k + 5] + ([order[k - 1]] if k >= 1 else [])
            for c in tries:
                if np.isfinite(p0[c]) and np.isfinite(p1[c]) and p0[c] != 0:
                    ret = p1[c] / p0[c] - 1
                    break
        rows.append({"month": t, "carry": carry, "ret": ret})
    return pd.DataFrame(rows).set_index("month")


def run_c() -> dict:
    carry, ret = {}, {}
    for code in CD.COMMODITIES:
        print(f"[c] {code}", file=sys.stderr, flush=True)
        d = market_inputs(code)
        carry[code], ret[code] = d["carry"], d["ret"]
    carry, ret = pd.DataFrame(carry), pd.DataFrame(ret)
    port, n = {}, {}
    for t in carry.index:                                                          # item 5
        ok = carry.loc[t].notna() & ret.loc[t].notna()
        if ok.sum() < 2:
            continue
        w = B.rank_weights(carry.loc[t][ok])
        port[t] = float((w * ret.loc[t][ok]).sum())
        n[t] = int(ok.sum())
    port = pd.Series(port, name="ours_aqr_construction")
    port.to_csv(CD.derived_dir() / "A4diag_c_aqr_construction_returns.csv")
    _, aqr = B.load_aqr()
    j = pd.concat([port, aqr], axis=1, join="inner").dropna()                      # item 7
    return {"months": int(len(j)), "first": str(j.index[0]), "last": str(j.index[-1]),
            "corr": float(j.corr().iloc[0, 1]),
            "markets_per_month_min": int(min(n.values())), "markets_per_month_max": int(max(n.values()))}
