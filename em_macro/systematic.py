"""Systematic macro strategy on the 13-country data (currencies and 10-year bonds).

    python -m em_macro.systematic fit       # design on 2005-2019 only -> results/systematic/fit/ (frozen)
    python -m em_macro.systematic test      # 2020+ once, with the frozen design -> results/systematic/test/
    python -m em_macro.systematic refresh   # rebuild the data the strategy reads (used by the monthly workflow)
    python -m em_macro.systematic update    # positions.csv and paper_pnl.csv with the frozen design

Two books, run side by side and combined:
  FX book    10 currencies vs USD: BRL MXN ZAR TRY IDR PLN GBP COP CLP and EUR (once, for FR/IT/ES/DE)
  bond book  13 bond positions: 10y local bonds of BR MX ZA TR ID CO CL (excess return over the local
             policy rate), the 10y spread over the Bund of FR IT ES GB PL (long the country bond, short the
             Bund, duration-matched), and the Bund itself (excess over the ECB rate)

Signals (each z-scored across the instruments of a book every month), equally weighted:
  carry  FX: local policy rate minus fed funds.  Bonds: 10y yield minus policy rate; spread level for
         the European spreads; Bund yield minus ECB rate
  trend  average of the z-scores of the 12-month and 3-month excess return
  value  FX: log real exchange rate (local per USD, CPI lagged one month) minus its 5-year average
         (positive = cheap currency).  Bonds: the risk model's v1 frozen mispricing (spread minus fair
         value; positive = cheap bond).  No value signal for the Bund.
Portfolio: rank the composite, long the top third and short the bottom third of each book, size each
position to equal volatility, scale each book and then the total to 10% annualised volatility, rebalance
monthly, pay transaction costs on traded notional.  The earlier frozen results are not touched.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import carry as CARRY
from . import panel_sources as PS
from . import sources as S
from .config import PROC, RESULTS, ROOT

OUT = RESULTS / "systematic"
FIT_DIR, TEST_DIR = OUT / "fit", OUT / "test"
FIT_END, TEST_START = pd.Period("2019-12", "M"), pd.Period("2020-01", "M")
CODE_FILE = ROOT / "em_macro" / "systematic.py"

# --------------------------------------------------------- frozen design choices
DESIGN = {
    "signals": ["carry", "trend", "value"],
    "signal_weights": "equal (mean of the available signal z-scores)",
    "trend_windows_months": [12, 3],
    "value_fx_window_months": 60, "value_fx_min_months": 36,
    "zscore": "cross-sectional within each book every month, at least 3 instruments",
    "selection": "long top third, short bottom third of each book (n = floor(N/3) per side, N >= 3)",
    "vol_lookback_months": 36, "vol_min_months": 12,
    "position_sizing": "inverse of trailing annualised volatility (equal risk per position)",
    "book_target_vol": 0.10, "portfolio_target_vol": 0.10, "book_mix": "50/50 after scaling each book to 10%",
    "gross_leverage_cap": 6.0,
    "no_trade_band": 0.25,     # chosen on 2005-2019 over "no band" (the only alternative tried; see README)
    "costs": {"major": 0.001, "high_cost": 0.003, "high_cost_countries": ["TR", "ID", "CO", "CL"],
              "spread_legs": 2, "basis": "per unit of notional traded (one-way), charged at each rebalance"},
    "bond_execution_lag_months": 1,
    "bond_return": "excess return from monthly-average yields: (y - funding)/12 - D*dy + C*dy^2/2, D and C of a "
                   "10-year par bond; weights decided at the end of month t earn the change between the "
                   "averages of t+1 and t+2 (avoids the look-ahead in month averages)",
    "rebalance": "monthly, month-end",
}
FX_INSTR = {"BRL": "BR", "MXN": "MX", "ZAR": "ZA", "TRY": "TR", "IDR": "ID", "PLN": "PL", "GBP": "GB",
            "COP": "CO", "CLP": "CL", "EUR": "XM"}
EM_BONDS = ["BR", "MX", "ZA", "TR", "ID", "CO", "CL"]
EU_SPREADS = ["FR", "IT", "ES", "GB", "PL"]
ISO3 = {"BR": "BRA", "MX": "MEX", "ZA": "ZAF", "TR": "TUR", "ID": "IDN", "PL": "POL", "FR": "FRA", "IT": "ITA",
        "ES": "ESP", "GB": "GBR", "CO": "COL", "CL": "CHL", "DE": "DEU"}
NAME = {"BR": "Brazil", "MX": "Mexico", "ZA": "South Africa", "TR": "Turkey", "ID": "Indonesia", "PL": "Poland",
        "FR": "France", "IT": "Italy", "ES": "Spain", "GB": "United Kingdom", "CO": "Colombia", "CL": "Chile",
        "DE": "Germany", "XM": "euro area"}


def _code_hash() -> str:
    return hashlib.sha256(CODE_FILE.read_bytes()).hexdigest()[:16]


def _me(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return s.groupby(s.index.to_period("M")).last()


def _ma(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return s.groupby(s.index.to_period("M")).mean()


# ============================================================ inputs and returns
def complete_months() -> pd.PeriodIndex:
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    last = daily.index.max()
    end = last.to_period("M") - (0 if last >= (last + pd.offsets.BMonthEnd(0)) else 1)
    return pd.period_range("2005-01", end, freq="M")


def build_inputs() -> dict:
    months = complete_months()
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    panel = pd.read_csv(PROC / "country_month_panel.csv")
    panel["month"] = pd.PeriodIndex(panel["month"], freq="M")
    iso2 = {v: k for k, v in ISO3.items()}
    panel["c"] = panel["iso3"].map(iso2)
    pw = lambda col: panel.pivot(index="month", columns="c", values=col).reindex(months)

    # ---- FX: month-end spot (local per USD), local and US rates, CPI levels
    spot = {}
    for k, c in FX_INSTR.items():
        if c in ("BR", "MX", "ZA", "TR", "ID", "PL"):
            spot[k] = _me(daily[f"FX_{c}"])
    spot["GBP"] = _me(1 / S.fred("DEXUSUK"))
    spot["EUR"] = _me(1 / S.fred("DEXUSEU"))
    spot["COP"] = _me(PS.colombia_trm())
    spot["CLP"] = _me(PS.chile_dolar_observado())
    spot = pd.DataFrame(spot).reindex(months)
    us = _ma(S.fred("DFF")).reindex(months)
    loc = pd.DataFrame({k: _ma(S.bis_policy(c)).reindex(months) for k, c in FX_INSTR.items()})
    cpi_us = PS.bis_cpi_index("US").reindex(months)
    cpi = pd.DataFrame({k: PS.bis_cpi_index(c).reindex(months) for k, c in FX_INSTR.items()})

    tau = pd.Series(months.to_timestamp(how="end").days_in_month / 365, index=months)
    rfx = (spot.shift(1) / spot) * (1 + loc.shift(1) / 100 * tau.values[:, None]) \
        - (1 + us.shift(1).values[:, None] / 100 * tau.values[:, None])
    fx_carry = loc.sub(us, axis=0)
    rer = np.log(spot * cpi_us.shift(1).values[:, None] / cpi.shift(1))     # CPI known with a one-month lag
    w, mn = DESIGN["value_fx_window_months"], DESIGN["value_fx_min_months"]
    fx_value = rer - rer.rolling(w, min_periods=mn).mean()

    # ---- bonds: monthly-average yields from the 13-country panel
    y10, pol, spr = pw("y10"), pw("policy_rate"), pw("spread_vs_de_bp") / 100
    bond_y, bond_f, bond_dur_y = {}, {}, {}
    for c in EM_BONDS:
        bond_y[f"{c}10Y"], bond_f[f"{c}10Y"], bond_dur_y[f"{c}10Y"] = y10[c], pol[c], y10[c]
    for c in EU_SPREADS:
        bond_y[f"{c}-DE"], bond_f[f"{c}-DE"], bond_dur_y[f"{c}-DE"] = spr[c], 0 * spr[c], y10[c]
    bond_y["DE10Y"], bond_f["DE10Y"], bond_dur_y["DE10Y"] = y10["DE"], pol["DE"], y10["DE"]
    by, bf, bd = pd.DataFrame(bond_y), pd.DataFrame(bond_f), pd.DataFrame(bond_dur_y)
    D, C = _duration(bd.shift(1) / 100)
    dy = by.diff() / 100
    rb = (by.shift(1) - bf.shift(1)) / 100 / 12 - D * dy + 0.5 * C * dy ** 2
    bond_carry = by - bf

    # bond value: v1 frozen risk-model mispricing (bp; + = spread above fair value = cheap bond)
    from . import risk_model as RM
    fr = RM.load_frozen("v1")
    pdx, _ = RM.predict(fr["equations"]["spread"], RM.load_data())
    gap = pdx.pivot(index="month", columns="c", values="gap").reindex(months)
    bond_value = pd.DataFrame({b: gap[b[:2]] if b[:2] in gap and b != "DE10Y" else np.nan for b in by.columns},
                              index=months)

    # costs per unit of notional traded
    hc = set(DESIGN["costs"]["high_cost_countries"])
    cost = {k: DESIGN["costs"]["high_cost"] if c in hc else DESIGN["costs"]["major"] for k, c in FX_INSTR.items()}
    for b in by.columns:
        base = DESIGN["costs"]["high_cost"] if b[:2] in hc else DESIGN["costs"]["major"]
        cost[b] = base * (DESIGN["costs"]["spread_legs"] if b.endswith("-DE") else 1)

    # benchmarks
    carry_basket = CARRY.carry_returns(daily)["EW"].reindex(months)          # original six-currency basket
    spx = S.yahoo("^SP500TR")
    spx = _me(spx).pct_change().reindex(months)
    return {"months": months, "fx": {"ret": rfx, "carry": fx_carry, "value": fx_value},
            "bond": {"ret": rb, "carry": bond_carry, "value": bond_value},
            "cost": cost, "carry_basket": carry_basket, "spx": spx}


def _duration(y: pd.DataFrame, n: int = 10):
    """Modified duration and convexity of an n-year annual-coupon par bond at yield y."""
    y = y.clip(lower=1e-4)
    D = (1 - (1 + y) ** -n) / y
    t = np.arange(1, n + 1)
    C = sum((y * tt * (tt + 1) * (1 + y) ** -(tt + 2)) for tt in t) + n * (n + 1) * (1 + y) ** -(n + 2)
    return D, C


# ===================================================================== signals
def _xs_z(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score per month (rows), needs >= 3 instruments."""
    m, s, n = df.mean(axis=1), df.std(axis=1), df.notna().sum(axis=1)
    z = df.sub(m, axis=0).div(s.replace(0, np.nan), axis=0)
    return z.mask(n < 3, np.nan)


def signals(book: dict) -> dict[str, pd.DataFrame]:
    r = book["ret"]
    cum = np.log1p(r.fillna(0)).cumsum().where(r.notna())
    tr = [_xs_z(np.expm1(cum - cum.shift(h)).where(r.rolling(h).count() == h)) for h in DESIGN["trend_windows_months"]]
    trend = (tr[0] + tr[1]) / 2
    return {"carry": _xs_z(book["carry"]), "trend": trend, "value": _xs_z(book["value"])}


# ================================================================== portfolio
def _vol(r: pd.DataFrame) -> pd.DataFrame:
    return r.rolling(DESIGN["vol_lookback_months"], min_periods=DESIGN["vol_min_months"]).std() * np.sqrt(12)


def book_weights(book: dict, use: list[str]) -> pd.DataFrame:
    """Weights decided at the end of each month (row), scaled so that the book
    alone would have run at the target volatility over the trailing window."""
    sig = signals(book)
    comp = pd.concat([sig[k] for k in use], keys=use).groupby(level=1).mean().reindex(book["ret"].index)
    vol = _vol(book["ret"])
    r = book["ret"]
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
        hist = r.loc[:t].iloc[-DESIGN["vol_lookback_months"]:].fillna(0.0)
        pv = (hist @ raw).std() * np.sqrt(12)
        if pv > 0:
            W.loc[t] = raw * DESIGN["book_target_vol"] / pv
    return W


def _apply_band(target: pd.DataFrame, band: float) -> pd.DataFrame:
    """Keep the current position unless the target differs from it by more than
    `band` x |target|; exits (target 0) and sign changes always trade."""
    held = target.copy() * 0.0
    prev = pd.Series(0.0, index=target.columns)
    for t in target.index:
        tgt = target.loc[t]
        trade = (tgt == 0) | (np.sign(tgt) != np.sign(prev)) | ((tgt - prev).abs() > band * tgt.abs())
        prev = prev.where(~trade, tgt)
        held.loc[t] = prev
    return held


def run(inp: dict, use: list[str], books=("fx", "bond"), band: float | None = None) -> pd.DataFrame:
    """Monthly P&L.  FX weights decided at t earn the return of t+1; bond weights
    earn the return of t+2 (execution lag for monthly-average yields)."""
    months = inp["months"]
    lag = {"fx": 1, "bond": 1 + DESIGN["bond_execution_lag_months"]}
    W = {b: book_weights(inp[b], use) for b in books}
    # combine 50/50 and rescale the total to the target using trailing pro-forma returns
    allW = pd.concat([W[b] * (0.5 if len(books) == 2 else 1.0) for b in books], axis=1)
    allR = pd.concat([inp[b]["ret"] for b in books], axis=1)          # returns observed up to each month
    scale = pd.Series(np.nan, index=months)
    for t in months:
        hist = allR.loc[:t].iloc[-DESIGN["vol_lookback_months"]:].fillna(0.0)
        pv = (hist @ allW.loc[t]).std() * np.sqrt(12) if len(hist) >= DESIGN["vol_min_months"] else np.nan
        scale[t] = DESIGN["portfolio_target_vol"] / pv if pv and pv > 0 else 0.0
    allW = allW.mul(scale.fillna(0.0), axis=0)
    gross = allW.abs().sum(axis=1)
    cap = DESIGN["gross_leverage_cap"]
    allW = allW.mul(np.minimum(1.0, cap / gross.replace(0, np.nan)).fillna(0.0), axis=0)
    band = DESIGN["no_trade_band"] if band is None else band
    if band:
        allW = _apply_band(allW, band)
    cost = pd.Series(inp["cost"]).reindex(allW.columns).values
    out = pd.DataFrame(index=months)
    for b in books:
        cols = inp[b]["ret"].columns
        w = allW[cols]
        pnl = (w.shift(lag[b]) * inp[b]["ret"]).sum(axis=1, min_count=1)
        # cost of the trade that sets up the new weights, charged in the month they start earning
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


def stats(r: pd.Series, spx: pd.Series | None = None) -> dict:
    r = r.dropna()
    if len(r) < 12:
        return {"months": len(r)}
    w = (1 + r).cumprod()
    yrs = len(r) / 12
    out = {"start": str(r.index[0]), "end": str(r.index[-1]), "months": len(r),
           "ann_return_%": 100 * (w.iloc[-1] ** (1 / yrs) - 1), "ann_vol_%": 100 * r.std() * np.sqrt(12),
           "sharpe": r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan,
           "max_drawdown_%": 100 * (w / w.cummax() - 1).min()}
    if spx is not None:
        out["corr_sp500"] = r.corr(spx.reindex(r.index))
    return out


VARIANTS = {"combined": ["carry", "trend", "value"], "carry only": ["carry"], "trend only": ["trend"],
            "value only": ["value"]}


def evaluate(inp: dict, period: slice) -> pd.DataFrame:
    rows = []
    for name, use in VARIANTS.items():
        for books, label in ((("fx", "bond"), "both books"), (("fx",), "FX book"), (("bond",), "bond book")):
            res = run(inp, use, books)
            r = res["net"].loc[period]
            rows.append({"strategy": name, "books": label, **stats(r, inp["spx"]),
                         "avg_gross_leverage": res["gross_leverage"].loc[period].mean(),
                         "cost_drag_%_pa": 100 * res["cost"].loc[period].mean() * 12})
    cb = inp["carry_basket"].loc[period]
    rows.append({"strategy": "carry basket (hold, 6 EM currencies)", "books": "benchmark", **stats(cb, inp["spx"])})
    rows.append({"strategy": "S&P 500 total return", "books": "benchmark", **stats(inp["spx"].loc[period])})
    return pd.DataFrame(rows)


# ===================================================================== stages
def stage_fit():
    FIT_DIR.mkdir(parents=True, exist_ok=True)
    inp = build_inputs()
    period = slice(None, FIT_END)
    tab = evaluate(inp, period)          # every number here uses data up to 2019-12 only (rolling, causal)
    tab.to_csv(FIT_DIR / "performance_2005_2019.csv", index=False, float_format="%.4f")
    frozen = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "code_sha256_16": _code_hash(), "fit_end": str(FIT_END), "test_start": str(TEST_START),
              "design": DESIGN, "instruments": {"fx": list(FX_INSTR), "bond": list(inp["bond"]["ret"].columns)},
              "costs": inp["cost"]}
    (FIT_DIR / "frozen_design.json").write_text(json.dumps(frozen, indent=1))
    print(tab[tab.books.isin(["both books", "benchmark"])].round(3).to_string())


def _check_frozen(strict: bool = True) -> dict:
    """The test refuses to run if the code changed after freezing; the monthly
    update only requires the design parameters to be unchanged."""
    fr = json.loads((FIT_DIR / "frozen_design.json").read_text())
    if fr["design"] != json.loads(json.dumps(DESIGN)):
        sys.exit("the strategy design changed after freezing; restore the frozen design first.")
    if strict and fr["code_sha256_16"] != _code_hash():
        sys.exit("systematic.py changed after freezing; restore the frozen version before testing.")
    return fr


def stage_test(force: bool = False):
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    guard = TEST_DIR / "TEST_RUN.json"
    if guard.exists() and not force:
        sys.exit(f"hold-out already evaluated ({guard}).")
    fr = _check_frozen()
    inp = build_inputs()
    end = inp["months"][-1]
    tab = evaluate(inp, slice(TEST_START, end))
    tab.to_csv(TEST_DIR / "performance_2020_on.csv", index=False, float_format="%.4f")
    guard.write_text(json.dumps({"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "frozen_created_utc": fr["created_utc"], "last_month": str(end)}, indent=1))
    print(tab[tab.books.isin(["both books", "benchmark"])].round(3).to_string())


def stage_update():
    """positions.csv (this month's book) and paper_pnl.csv (full history)."""
    fr = _check_frozen(strict=False)
    inp = build_inputs()
    res = run(inp, VARIANTS["combined"])
    W = res.attrs["weights"]
    t = inp["months"][-1]
    sig = {b: signals(inp[b]) for b in ("fx", "bond")}
    vol = {b: _vol(inp[b]["ret"]) for b in ("fx", "bond")}
    rows = []
    for b in ("fx", "bond"):
        for k in inp[b]["ret"].columns:
            w = W.at[t, k]
            if abs(w) < 1e-9:
                continue
            c = FX_INSTR.get(k, k[:2])
            desc = (f"{k} vs USD ({NAME.get(c, c)})" if b == "fx" else
                    f"{NAME[c]} 10y bond spread over the Bund (long {NAME[c]}, short Bund)" if k.endswith("-DE")
                    else "German 10y Bund (excess over the ECB rate)" if k == "DE10Y"
                    else f"{NAME[c]} 10y local-currency bond (excess over local policy rate)")
            rows.append({"as_of": f"{t}", "effective_from": f"{t + 1}", "book": b, "instrument": k, "description": desc,
                         "side": "long" if w > 0 else "short", "size_pct_of_capital": round(100 * w, 2),
                         "risk_share_pct": np.nan, "instrument_vol_pct": round(100 * vol[b].at[t, k], 2),
                         "carry_z": sig[b]["carry"].at[t, k], "trend_z": sig[b]["trend"].at[t, k],
                         "value_z": sig[b]["value"].at[t, k], "cost_pct_per_trade": 100 * inp["cost"][k]})
    pos = pd.DataFrame(rows)
    if len(pos):
        rv = (pos["size_pct_of_capital"].abs() * pos["instrument_vol_pct"])
        pos["risk_share_pct"] = (100 * rv / rv.sum()).round(1)
        pos = pos.sort_values(["book", "side", "size_pct_of_capital"], ascending=[True, True, False])
    OUT.mkdir(parents=True, exist_ok=True)
    pos.to_csv(OUT / "positions.csv", index=False, float_format="%.3f")
    freeze_month = pd.Period(fr["created_utc"][:7], "M")
    pnl = res[["fx_gross", "bond_gross", "cost", "net", "gross_leverage"]].copy()
    pnl["sample"] = np.where(pnl.index <= FIT_END, "design 2005-2019 (in-sample)",
                             np.where(pnl.index <= freeze_month, "test 2020+ (backtest, evaluated once)",
                                      "live paper trading (after freeze)"))
    pnl["cumulative_net"] = (1 + pnl["net"]).cumprod()
    pnl["carry_basket"] = inp["carry_basket"].reindex(pnl.index)
    pnl["sp500_tr"] = inp["spx"].reindex(pnl.index)
    pnl.index.name = "month"
    pnl.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(OUT / "paper_pnl.csv", index=False,
                                                                           float_format="%.6f")
    print(pos.to_string())


def stage_refresh():
    """Rebuild the inputs: daily panel (light sources re-downloaded; BondSpot and
    Borsa Istanbul fetched incrementally), the 13-country panel and the risk-model
    design matrix.  Frozen results are not re-run."""
    from . import build_data, panel, risk_model
    build_data.build(refresh=True)
    panel.build()
    risk_model.build_data()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fit":
        stage_fit()
    elif cmd == "test":
        stage_test("--force" in sys.argv)
    elif cmd == "update":
        stage_update()
    elif cmd == "refresh":
        stage_refresh()
    else:
        sys.exit(__doc__)
