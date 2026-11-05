"""Build 0 acceptance tests A1-A11 for trials T20-T22 (docs/prereg/T20-T22_commodity_trials.md §6).

    EM_MACRO_DATA=/path/to/em-macro-data python -m em_macro.commod_build0 run

Computes only what the A-tests require.  Aggregate statistics (counts, shares, correlations, pass/fail) go to
results/T20-T22/build0.json; every per-market price, return, roll or intermediate table goes to the private
data repo under norgate/derived/build0/ (never into this repository).  A8: nothing here reports a return, Sharpe
ratio, drawdown or P&L of any sleeve or signal; the A3 and A4 series are written privately and only their
correlations with the AQR benchmarks are reported.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import commod_data as CD
from .config import ROOT

OUT_JSON = ROOT / "results" / "T20-T22" / "build0.json"
AQR_DIR_ENV = "AQR_DATA"          # folder with the two AQR workbooks (kept outside the repository)
AQR_CFLR = "Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx"
AQR_COFP = "Century-of-Factor-Premia-Monthly.xlsx"
GAP_LIMIT = 5                     # §2.1 rule 4
MAD_K = 8.0                       # A9
MAD_WINDOW = 252
REVERSAL_TOL = 0.10               # "fully reverses": the two-day move is within 10% of the first day's move
LAST_DAYS = 10                    # spec §7: never hold a contract into its last 10 trading days
LIMIT_SECTORS = ("grains and oilseeds", "livestock")


# ------------------------------------------------------------------------------------------------ helpers
def _months(a: pd.Period, b: pd.Period):
    return pd.period_range(a, b, freq="M")


def entry_month(md: CD.MarketData, r1: pd.DataFrame) -> pd.Period:
    """First rebalance whose decision date has >= 252 F1 daily returns and 12 months of F1 history (§2.1 rule 2)."""
    days = r1.index
    first = days[0]
    for month, row in md.rolls.iterrows():
        t = row["decision"]
        n = int((days <= t).sum())
        if n >= 252 and t >= first + pd.DateOffset(months=12):
            return month
    return None


def first_last_settle(md: CD.MarketData):
    return md.all_contracts.set_index("contract")[["first", "last"]]


# ------------------------------------------------------------------------------------------------ A1
def a1_contract_table(md: CD.MarketData) -> dict:
    ct = md.contracts
    lo, hi = CD.ASSEMBLY_START, pd.Timestamp("2026-10-31")
    use = ct[(ct["ltd"] >= lo) & (ct["first"] <= hi)]
    # designated months that should exist (by contract month) but have no Norgate contract
    lo_ym, hi_ym = int(use["ym"].min()), int(use["ym"].max())
    expected = [((ym - 1) // 12, (ym - 1) % 12 + 1) for ym in range(lo_ym, hi_ym + 1)]
    expected = [(y, m) for y, m in expected if CD.MONTH_CODES[m - 1] in md.m.months]
    have = set(zip(ct["year"], ct["month"]))
    missing = [f"{y}{CD.MONTH_CODES[m - 1]}" for y, m in expected if (y, m) not in have]
    # LTD rule against the primary source's final settlement (expired contracts with LTD in 2000-2026)
    exp = ct[(~ct["live"]) & (~ct["stopped_early"]) & (ct["ltd"] >= "2000-01-01")]
    cal = md.calendar
    diff = [cal.count_between(min(a, b), max(a, b)) - 1 for a, b in zip(exp["ltd_rule"], exp["ltd"])]
    diff = np.array(diff)
    out = {"contracts": int(len(use)), "live": int(use["live"].sum()),
           "first_contract": use.index[0], "last_contract": use.index[-1],
           "missing_designated": missing[:20], "n_missing_designated": len(missing),
           "ltd_rule_n": int(len(exp)),
           "ltd_rule_exact": float(np.mean(diff == 0)) if len(diff) else None,
           "ltd_rule_within_2bd": float(np.mean(diff <= 2)) if len(diff) else None,
           "stopped_early": list(ct.index[ct["stopped_early"] & (ct["ltd_rule"] >= "1990-01-01")]),
           "final_settlement_rows": int((ct["final_settlement_row"] & (ct["ltd"] >= "2000-01-01")).sum()),
           "notice": "min(FND, LTD)" if md.m.fnd_rule else "LTD",
           "fnd_rule": md.m.fnd_rule, "ltd_rule": md.m.ltd_rule}
    return out


# ------------------------------------------------------------------------------------------------ A2 / A10
def coverage(md: CD.MarketData, entry: pd.Period) -> dict:
    r = md.rolls
    start = max(CD.COVERAGE_START, entry) if entry is not None else CD.COVERAGE_START
    sel = r.loc[start:CD.COVERAGE_END]
    ok = [md.has_settle(a, t) and md.has_settle(b, t) for a, b, t in zip(sel["F1"], sel["F2"], sel["decision"])]
    miss = [str(m) for m, o in zip(sel.index, ok) if not o]
    return {"start": str(start), "months": int(len(sel)), "covered": int(sum(ok)),
            "coverage": float(np.mean(ok)) if len(ok) else None, "missing_months": miss}


# ------------------------------------------------------------------------------------------------ A6
def a6_roll_checks(md: CD.MarketData) -> dict:
    ct = md.contracts
    r = md.rolls.dropna(subset=["F1"])
    cal = md.calendar
    first = ct["first"]
    res = {"rebalances": int(len(r))}
    bad_first = [(str(m), w) for m, row in r.iterrows() for w in ("F1", "F2")
                 if row[w] is not None and first[row[w]] > row["decision"]]
    used13 = r.dropna(subset=["F13"])
    bad_first13 = [str(m) for m, row in used13.iterrows()
                   if md.has_settle(row["F13"], row["decision"]) and first[row["F13"]] > row["decision"]]
    bad_notice = [str(m) for m, row in r.iterrows()
                  if not ct.at[row["F1"], "notice"] > row["execution"] + pd.Timedelta(days=CD.BUFFER_DAYS)]
    res["first_settle_after_decision"] = len(bad_first) + len(bad_first13)
    res["first_settle_examples"] = bad_first[:5]
    res["notice_violations"] = len(bad_notice)
    # last-10-trading-days check: every held day from entry settlement to exit settlement (both inclusive)
    ex = list(r["execution"])
    for which in ("F1", "F2"):
        viol, viol_excl_exit, min_left = [], [], 10 ** 6
        for k in range(len(r) - 1):
            c = r[which].iloc[k]
            if c is None:
                continue
            ltd = ct.at[c, "ltd"]
            exit_day = ex[k + 1]
            left_at_exit = cal.count_between(exit_day, ltd)       # trading days d..LTD inclusive, d = exit day
            prev_day = cal.before(exit_day)
            left_before_exit = cal.count_between(prev_day, ltd)
            min_left = min(min_left, left_at_exit)
            if left_at_exit <= LAST_DAYS:
                viol.append(str(r.index[k]))
            if left_before_exit <= LAST_DAYS:
                viol_excl_exit.append(str(r.index[k]))
        res[f"{which}_last10_violations"] = len(viol)
        res[f"{which}_last10_violations_2000_2026"] = sum(v >= "2000-01" for v in viol)
        res[f"{which}_last10_violations_excl_exit_day"] = len(viol_excl_exit)
        res[f"{which}_last10_examples"] = viol[:6]
        res[f"{which}_min_trading_days_left_at_exit"] = int(min_left)
    return res


# ------------------------------------------------------------------------------------------------ A7
def a7_option_a(md: CD.MarketData, entry: pd.Period) -> dict:
    r = md.rolls
    start = max(CD.DESIGN_START, entry) if entry is not None else CD.DESIGN_START
    sel = r.loc[start:CD.DESIGN_END]
    ok = [md.has_settle(f, t) for f, t in zip(sel["F13"], sel["decision"])]
    share = float(np.mean(ok)) if ok else None
    return {"months": int(len(sel)), "with_F13": int(sum(ok)), "share": share,
            "option": "A" if share is not None and share >= 0.90 else "B"}


# ------------------------------------------------------------------------------------------------ A9
def _consecutive_runs(flags: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    runs, start, n, prev = [], None, 0, None
    for d, f in flags.items():
        if f:
            if start is None:
                start, n = d, 0
            n += 1
            prev = d
        elif start is not None:
            runs.append((start, prev, n))
            start = None
    if start is not None:
        runs.append((start, prev, n))
    return runs


def a9_quality(md: CD.MarketData, rets: dict[str, pd.DataFrame]) -> tuple[dict, pd.DataFrame]:
    """Held-contract gaps (> 5 consecutive missing days) and 8-MAD one-day spikes that fully reverse."""
    out, rows = {}, []
    tick = md.m.tick
    for which, df in rets.items():
        df = df[df.index >= CD.ASSEMBLY_START]
        # gaps, per held contract run
        long_gaps = []
        for c, g in df.groupby("contract"):
            for a, b, n in _consecutive_runs(g["filled"]):
                if n > GAP_LIMIT:
                    long_gaps.append({"series": which, "contract": c, "from": a, "to": b, "days": n,
                                      "type": "gap"})
        # spikes
        r = df["r"].where(~df["filled"])
        med = r.rolling(MAD_WINDOW, min_periods=60).median().shift(1)
        mad = (r - med).abs().rolling(MAD_WINDOW, min_periods=60).median().shift(1)
        floor = tick / df["prev_price"].abs()
        mad = np.maximum(mad, floor)
        z = (r - med).abs() / mad
        nxt = r.shift(-1)
        same = df["contract"].shift(-1) == df["contract"]
        two = (1 + r) * (1 + nxt) - 1
        spike = (z > MAD_K) & same & (np.sign(nxt) == -np.sign(r)) & (two.abs() <= REVERSAL_TOL * r.abs())
        spikes = []
        for d in df.index[spike.fillna(False).to_numpy()]:
            spikes.append({"series": which, "contract": df.at[d, "contract"], "from": d, "to": d,
                           "days": 1, "type": "spike", "mad_multiple": float(z.at[d])})
        # limit-locked flags (grains, livestock): unchanged settlement after a > 3-MAD move, flagged only
        locked = 0
        if md.m.sector in LIMIT_SECTORS:
            prevz = z.shift(1)
            locked = int(((r == 0) & (prevz > 3) & same.shift(1, fill_value=False)).sum())
        out[which] = {"gaps_gt5": len(long_gaps), "spikes": len(spikes), "limit_locked_flags": locked,
                      "filled_days": int(df["filled"].sum())}
        rows += long_gaps + spikes
    return out, pd.DataFrame(rows)


def resolve_spikes(md: CD.MarketData, issues: pd.DataFrame) -> pd.DataFrame:
    """A spike is resolved as a genuine market move when an adjacent designated contract of the same market moved
    the same way on the same day by at least half as much and reversed the next day as well (the curve confirms
    it); otherwise it stays unresolved (or is resolved by the Databento comparison, A5)."""
    if issues.empty:
        return issues
    issues = issues.copy()
    status = []
    names = list(md.contracts.index)
    f2_held = md.code in CD.XS_UNIVERSE       # the F2 series is held only by T21 (20-market universe)
    close = md.close
    for _, row in issues.iterrows():
        if row["type"] != "spike":
            held = row["series"] == "F1" or f2_held
            status.append("unresolved" if held else "not held by any trial (F2 of a market outside T21)")
            continue
        d, c = row["from"], row["contract"]
        i = close.index.get_loc(d)
        if i < 1 or i + 1 >= len(close.index):
            status.append("unresolved")
            continue
        d0, d2 = close.index[i - 1], close.index[i + 1]
        own = close.at[d, c] / close.at[d0, c] - 1 if np.isfinite(close.at[d0, c]) else np.nan
        k = names.index(c)
        conf = False
        for j in (k - 1, k + 1, k + 2):
            if 0 <= j < len(names) and names[j] in close.columns:
                o = close[names[j]]
                a, b, e = o.get(d0), o.get(d), o.get(d2)
                if all(np.isfinite(x) for x in (a, b, e)) and a != 0 and b != 0:
                    mv, back = b / a - 1, e / b - 1
                    if np.sign(mv) == np.sign(own) and abs(mv) >= 0.5 * abs(own) and np.sign(back) == -np.sign(mv):
                        conf = True
                        break
        status.append("genuine (curve confirms)" if conf else "unresolved")
    issues["status"] = status
    return issues


# ------------------------------------------------------------------------------------------------ A11
def a11_listed(md: CD.MarketData) -> dict:
    """F2 and F13 are listed on every date they are used and were not delisted before expiry."""
    ct = md.contracts
    r = md.rolls.dropna(subset=["F1"])
    bad = []
    for m, row in r.iterrows():
        t = row["decision"]
        for w in ("F2", "F13"):
            c = row[w]
            if c is None:
                continue
            if not md.has_settle(c, t):
                continue             # no settlement on t: not used that month (missing value, §2.1 rule 3)
            rec = ct.loc[c]
            month_start = pd.Timestamp(int(rec["year"]), int(rec["month"]), 1)
            listed = rec["first"] <= t <= rec["last"]
            expired_normally = rec["live"] or (not rec["stopped_early"]
                                               and rec["last"] >= month_start - pd.DateOffset(months=2))
            if not (listed and expired_normally):
                bad.append((str(m), w, c))
    return {"checked": int(len(r)), "violations": len(bad), "examples": bad[:5]}


# ------------------------------------------------------------------------------------------------ A3 / A4
def monthly_f1_returns(rets: pd.DataFrame) -> pd.Series:
    """Calendar-month excess return of the F1 chained index (§2.3), full months only."""
    r = rets["r"].fillna(0.0)
    idx = (1 + r).cumprod()
    me = idx.groupby(idx.index.to_period("M")).last()
    out = me.pct_change()
    return out.iloc[1:]


def carry_portfolio_inputs(md: CD.MarketData, rets: pd.DataFrame) -> pd.DataFrame:
    """Per rebalance: carry_log(F1, F2) at the decision date and the F1 holding-period excess return from this
    execution date to the next (written privately; used only for the A4 correlation)."""
    ct = md.contracts
    r = md.rolls.dropna(subset=["F1"])
    ex = list(r["execution"])
    idx = (1 + rets["r"].fillna(0.0)).cumprod()
    # the index is 1 at the first execution settlement (its first return is the next day), so the first
    # rebalance month has a holding return too (A4 diagnostic (a), docs/prereg/T20-T22_A4_diagnostic.md)
    idx = pd.concat([pd.Series([1.0], index=[ex[0]]), idx[idx.index > ex[0]]])
    rows = []
    for k in range(len(r) - 1):
        row = r.iloc[k]
        t = row["decision"]
        f1, f2 = md.settle(row["F1"], t), md.settle(row["F2"], t)
        carry = np.nan
        if np.isfinite(f1) and np.isfinite(f2) and f1 > 0 and f2 > 0:
            d1 = (ct.at[row["F1"], "ltd"] - t).days
            d2 = (ct.at[row["F2"], "ltd"] - t).days
            if d2 > d1:
                carry = (np.log(f1) - np.log(f2)) * 365.0 / (d2 - d1)
        a, b = ex[k], ex[k + 1]
        hold = idx.asof(b) / idx.asof(a) - 1
        rows.append({"month": r.index[k], "carry_log": carry, "hold_ret": hold})
    return pd.DataFrame(rows).set_index("month")


def rank_weights(sig: pd.Series) -> pd.Series:
    s = sig.dropna()
    n = len(s)
    if n < 2:
        return pd.Series(dtype=float)
    w = s.rank() - (n + 1) / 2
    return w / w.abs().sum() * 2


def load_aqr() -> tuple[pd.Series, pd.Series]:
    import os
    folder = Path(os.environ.get(AQR_DIR_ENV, CD.data_root().parent / "aqr"))
    cf = pd.read_excel(folder / AQR_CFLR, sheet_name=0, header=None)
    hdr = cf.index[cf.iloc[:, 1].astype(str).str.startswith("Excess return of equal-weight")][0]
    body = cf.iloc[hdr + 1:, :2].dropna()
    ew = pd.Series(body.iloc[:, 1].astype(float).values,
                   index=pd.to_datetime(body.iloc[:, 0]).dt.to_period("M"), name="aqr_ew")
    fp = pd.read_excel(folder / AQR_COFP, sheet_name=0, header=None)
    hrow = fp.index[fp.iloc[:, 0].astype(str) == "Date"][0]
    cols = list(fp.iloc[hrow])
    j = cols.index("Commodities Carry")
    body = fp.iloc[hrow + 1:, [0, j]]
    body = body[pd.to_numeric(body.iloc[:, 1], errors="coerce").notna()]
    carry = pd.Series(body.iloc[:, 1].astype(float).values,
                      index=pd.to_datetime(body.iloc[:, 0], format="%m/%d/%Y").dt.to_period("M"),
                      name="aqr_carry")
    return ew, carry


# ------------------------------------------------------------------------------------------------ extra checks
def spec_change_check(md: CD.MarketData) -> dict:
    """Report only.  Adjacent-contract log spread ln(F2/F1) on decision dates: its month-on-month change around
    a known specification change, in multiples of the market's median absolute monthly change 2000-2026, and the
    largest such moves in 2000-2026 (dates only).  Same-contract returns never cross a contract, so a respecified
    contract cannot create a jump in r_ex; it can only shift the curve."""
    r = md.rolls.loc[CD.COVERAGE_START:CD.COVERAGE_END]
    sp = pd.Series({m: (np.log(md.settle(a, t)) - np.log(md.settle(b, t)))
                    if md.settle(a, t) > 0 and md.settle(b, t) > 0 else np.nan
                    for m, a, b, t in zip(r.index, r["F1"], r["F2"], r["decision"])})
    ch = sp.diff().abs()
    scale = ch.median()
    z = ch / scale
    top = z.sort_values(ascending=False).head(3)
    res = {"top_moves": [(str(k), round(float(v), 1)) for k, v in top.items() if np.isfinite(v)]}
    res["changes"] = []
    for p, what in CD.SPEC_CHANGES.get(md.code, []):
        p = pd.Period(p, "M")
        win = z.loc[p - 3:p + 3].dropna()
        rank = int((z.dropna() > win.max()).sum()) + 1 if len(win) else None
        res["changes"].append({"change": what, "month": str(p),
                               "window_max_multiple": round(float(win.max()), 1) if len(win) else None,
                               "window_max_month": str(win.idxmax()) if len(win) else None,
                               "rank_in_2000_2026": rank, "of": int(z.notna().sum())})
    # price-unit breaks: same-contract one-day moves > 30% that do not reverse (would show a rescaled series)
    return res


def unit_breaks(rets: pd.DataFrame) -> int:
    r = rets["r"]
    r = r[(r.index >= "2000-01-01")]
    nxt = r.shift(-1)
    big = (r.abs() > 0.30) & (((1 + r) * (1 + nxt) - 1).abs() > 0.5 * r.abs())
    return int(big.sum())


def coverage_gaps_in_window(md: CD.MarketData) -> pd.DataFrame:
    """Missing days (no row for a contract on a market day within the contract's own range) inside 2000-2026,
    and whether the contract was F1, F2 or an F13 candidate on any affected day (the roll rule's use)."""
    close = md.close
    days = close.index
    r = md.rolls.loc[CD.COVERAGE_START:CD.ASSEMBLY_END_MONTH]
    rows = []
    fl = first_last_settle(md)
    designated = set(md.contracts.index)
    for c in close.columns:
        a, b = fl.at[c, "first"], fl.at[c, "last"]
        if b < pd.Timestamp("2000-01-01"):
            continue
        s = close[c]
        if c in md.contracts.index and md.contracts.at[c, "final_settlement_row"]:
            b = md.contracts.at[c, "ltd"]        # the day(s) before a final-settlement row are not a gap
        rng = (days >= max(a, pd.Timestamp("2000-01-01"))) & (days <= b)
        miss = days[rng & s.isna().to_numpy()]
        if len(miss) == 0:
            continue
        roles = set()
        for m, row in r.iterrows():
            nxt = row["execution"] + pd.DateOffset(months=1, days=5)
            win = (miss >= row["decision"]) & (miss <= nxt)
            if win.any():
                for w in ("F1", "F2", "F13"):
                    if row[w] == c:
                        roles.add(w)
        on_decision = any((row["decision"] in set(miss)) and c in (row["F1"], row["F2"], row["F13"])
                          for _, row in r.iterrows())
        rows.append({"contract": c, "designated": c in designated, "missing_days": int(len(miss)),
                     "first_missing": miss[0].date(), "last_missing": miss[-1].date(),
                     "roles_near_missing": ",".join(sorted(roles)), "missing_on_a_decision_date_in_role": on_decision})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ main
def run(markets: list[str] | None = None, write_private: bool = True) -> dict:
    markets = markets or CD.COMMODITIES
    priv = CD.derived_dir()
    if write_private:
        priv.mkdir(parents=True, exist_ok=True)
    res: dict = {"snapshot": CD.SNAPSHOT, "markets": {}}
    f1_monthly, carry_in, issues_all, gaps_all = {}, {}, [], []
    for code in markets:
        print(f"[build0] {code}", file=sys.stderr, flush=True)
        md = CD.MarketData(code)
        rets = {w: md.daily_returns(w) for w in ("F1", "F2")}
        entry = entry_month(md, rets["F1"])
        mres = {"entry": str(entry)}
        mres["A1"] = a1_contract_table(md)
        mres["coverage"] = coverage(md, entry)
        mres["A6"] = a6_roll_checks(md)
        if code in CD.XS_UNIVERSE:
            mres["A7"] = a7_option_a(md, entry)
        q, issues = a9_quality(md, rets)
        issues = resolve_spikes(md, issues)
        mres["A9"] = q
        if not issues.empty:
            issues.insert(0, "market", code)
            issues_all.append(issues)
        mres["A11"] = a11_listed(md)
        mres["spec_change"] = spec_change_check(md)
        mres["unit_breaks_2000_2026"] = unit_breaks(rets["F1"])
        g = coverage_gaps_in_window(md)
        if not g.empty:
            g.insert(0, "market", code)
            gaps_all.append(g)
        f1_monthly[code] = monthly_f1_returns(rets["F1"])
        carry_in[code] = carry_portfolio_inputs(md, rets["F1"])
        res["markets"][code] = mres
        if write_private:
            ct = md.contracts.drop(columns=["ym"])
            ct.to_csv(priv / f"contracts_{code}.csv")
            md.rolls.to_csv(priv / f"rolls_{code}.csv")
    # A3: equal-weight index of available markets, calendar months
    m1 = pd.DataFrame(f1_monthly)
    ew = m1.mean(axis=1, skipna=True)
    ew = ew[m1.notna().sum(axis=1) > 0]
    aqr_ew, aqr_carry = load_aqr()
    j = pd.concat([ew.rename("ours"), aqr_ew], axis=1, join="inner").dropna()
    res["A3"] = {"months": int(len(j)), "first": str(j.index[0]), "last": str(j.index[-1]),
                 "corr": float(j.corr().iloc[0, 1]),
                 "corr_2000_on": float(j.loc["2000-01":].corr().iloc[0, 1]),
                 "markets_per_month_min": int(m1.loc[j.index].notna().sum(axis=1).min()),
                 "markets_per_month_max": int(m1.loc[j.index].notna().sum(axis=1).max())}
    # A4: KMPV-style carry portfolio, all markets, rank weights on carry_log(F1, F2), no vol scaling, gross
    sig = pd.DataFrame({c: d["carry_log"] for c, d in carry_in.items()})
    hold = pd.DataFrame({c: d["hold_ret"] for c, d in carry_in.items()})
    port = {}
    for m in sig.index:
        w = rank_weights(sig.loc[m].where(hold.loc[m].notna()))
        if len(w) >= 2:
            port[m] = float((w * hold.loc[m, w.index]).sum())
    port = pd.Series(port, name="ours")
    j4 = pd.concat([port, aqr_carry], axis=1, join="inner").dropna()
    res["A4"] = {"months": int(len(j4)), "first": str(j4.index[0]), "last": str(j4.index[-1]),
                 "corr": float(j4.corr().iloc[0, 1]),
                 "corr_2000_on": float(j4.loc["2000-01":].corr().iloc[0, 1]),
                 "markets_per_month_min": int(sig.loc[j4.index].notna().sum(axis=1).min())}
    issues_df = pd.concat(issues_all) if issues_all else pd.DataFrame()
    gaps_df = pd.concat(gaps_all) if gaps_all else pd.DataFrame()
    if write_private:
        m1.to_csv(priv / "A3_f1_monthly_excess_returns.csv")
        ew.rename("ew").to_csv(priv / "A3_equal_weight_index_returns.csv")
        sig.to_csv(priv / "A4_carry_log_signal.csv")
        port.to_csv(priv / "A4_carry_portfolio_returns.csv")
        issues_df.to_csv(priv / "A9_issues.csv", index=False)
        gaps_df.to_csv(priv / "coverage_gaps_2000_2026.csv", index=False)
    res["A9_issue_counts"] = (issues_df.groupby(["type", "status"]).size().to_dict()
                              if not issues_df.empty else {})
    res["A9_issue_counts"] = {f"{k[0]}|{k[1]}": int(v) for k, v in res["A9_issue_counts"].items()}
    return res, issues_df, gaps_df


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--markets", nargs="*")
    a = ap.parse_args(argv)
    res, issues, gaps = run(a.markets)
    OUT_JSON.write_text(json.dumps(res, indent=1, default=str))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
