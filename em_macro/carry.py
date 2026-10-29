"""Carry benchmark: long each EM currency vs USD, earning local minus US short rate.

Monthly rebalancing.  For month t, positions are set at the last observation of
month t-1 using the rates known then:

    r_t = (S_{t-1} / S_t) * (1 + i_loc * tau) - (1 + i_us * tau) - cost

S = local currency per USD, tau = calendar days / 365, cost = 0.10% round trip
per month (the position is assumed to be closed and re-opened every month).
r_t is an excess return over USD cash, so Sharpe = mean / std * sqrt(12).
The equal-weight basket averages r_t over the currencies available that month.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import COUNTRIES, FIT_END, NAMES, PROC, RESULTS, TEST_START

COST = 0.001


def month_end(panel: pd.DataFrame, col: str) -> pd.Series:
    s = panel[col].dropna()
    return s.groupby(s.index.to_period("M")).last()


def carry_returns(panel: pd.DataFrame, rate: str = "policy") -> pd.DataFrame:
    """rate='policy': BIS policy rates for every country (base case);
    rate='market': CDI / TIIE-28 / JIBAR-3M where available, else policy."""
    i_us = month_end(panel, "US_FF")
    out = {}
    for c in COUNTRIES:
        s = month_end(panel, f"FX_{c}")
        i_loc = month_end(panel, f"POL_{c}")
        if rate == "market" and f"STR_{c}" in panel:
            i_loc = month_end(panel, f"STR_{c}").combine_first(i_loc)
        df = pd.concat({"s": s, "i": i_loc, "u": i_us}, axis=1)
        tau = df.index.to_timestamp(how="end").days_in_month / 365   # holding period length
        tau = pd.Series(np.asarray(tau), index=df.index)
        prev = df.shift(1)
        r = prev["s"] / df["s"] * (1 + prev["i"] / 100 * tau) - (1 + prev["u"] / 100 * tau) - COST
        out[c] = r
    rets = pd.DataFrame(out).dropna(how="all")
    rets = rets[rets.index >= pd.Period("2005-02", "M")]
    last = panel.index.max()
    if last < last + pd.offsets.BMonthEnd(0):          # drop the incomplete current month
        rets = rets[rets.index < last.to_period("M")]
    rets["EW"] = rets[COUNTRIES].mean(axis=1)
    return rets


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 6:
        return {}
    wealth = (1 + r).cumprod()
    dd = wealth / wealth.cummax() - 1
    years = len(r) / 12
    return {"start": str(r.index[0]), "end": str(r.index[-1]), "months": len(r),
            "ann_return_%": 100 * (wealth.iloc[-1] ** (1 / years) - 1),
            "ann_mean_%": 100 * r.mean() * 12, "ann_vol_%": 100 * r.std() * np.sqrt(12),
            "sharpe": r.mean() / r.std() * np.sqrt(12), "max_drawdown_%": 100 * dd.min(),
            "worst_month_%": 100 * r.min()}


def run(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant in ["policy", "market"]:
        rets = carry_returns(panel, variant)
        if variant == "policy":
            rets.to_csv(PROC / "carry_monthly_returns.csv", float_format="%.6f")
        for c in rets.columns:
            for label, sl in [("2005-2021 (fit)", slice(None, FIT_END[:7])),
                              ("2022- (hold-out)", slice(TEST_START[:7], None)),
                              ("full", slice(None, None))]:
                st = stats(rets[c].loc[sl])
                if st:
                    rows.append({"rates": variant, "series": NAMES.get(c, "Equal-weight basket"),
                                 "period": label, **st})
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "carry_benchmark.csv", index=False, float_format="%.3f")
    return tab


def to_markdown(tab: pd.DataFrame) -> str:
    t = tab[tab.rates == "policy"]
    L = ["| series | period | months | ann. return % | ann. vol % | Sharpe | max drawdown % |",
         "|---|---|---|---|---|---|---|"]
    for r in t.itertuples():
        L.append(f"| {r.series} | {r.period} | {r.months} | {r[7]:.1f} | {r[9]:.1f} | {r.sharpe:.2f} | {r[11]:.1f} |")
    return "\n".join(L)
