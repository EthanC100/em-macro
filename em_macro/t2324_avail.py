"""Phase 1 of T23-T24: data availability per month, 1978-01..1999-12 (counts and dates only).

    EM_MACRO_DATA=... python -m em_macro.t2324_avail run     # -> results/T23-T24/availability.{json,md,csv}

For every market of T21 (20 commodities), T22 (the 30 instruments of the a160bfd run) and the T20 carry control,
this checks, on the 1978-01..1999-12 schedule built by the unchanged a160bfd code (commod_data, with the schedule and
contract loading moved earlier by t2324_window):

* the Build 0 coverage gate (pre-registration §2.1 rule 1: F1 and F2 both settle on the decision date, >= 95% of
  decision dates from the later of 1978-01 and entry to 1999-12);
* the Build 0 roll-rule checks A6 (notice > execution + 35 days; no held F1 or F2 inside its last 10 trading days,
  Amendment 3 guard in force; every used contract settles on or before t; Amendment 4.4 missing months) and A11
  (F2/F13 listed when used);
* §2.1 rule 4 (no held F1, and for T21 no F2, contract gap of more than 5 consecutive market days);
* the entry month (§2.1 rule 2, B0.entry_month) and, per month, whether the market would be active for each trial
  (entered, not missing under Amendment 4.4, and the trial's look-back available).

Only the existence of a settlement on a date and the contract calendar are used: no price is summarised and no
return, signal or statistic is computed.  Per-market monthly flags stay in memory; the repository receives counts
and dates.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from . import commod_build0 as B0
from . import commod_data as CD
from . import t2324_window as WIN
from .config import RESULTS

OUT = RESULTS / "T23-T24"
MIN_ACTIVE = 6          # pre-registration §2.1 rule 3 (T20-T22)
COVERAGE_MIN = 0.95     # §2.1 rule 1
GAP_LIMIT = 5           # §2.1 rule 4
LAST_DAYS = 10


def t22_universe() -> list[str]:
    b0 = json.loads((RESULTS / "T20-T22" / "build0.json").read_text())
    drop = {c for c, m in b0["markets"].items() if m["coverage"]["coverage"] is not None
            and m["coverage"]["coverage"] < COVERAGE_MIN}
    drop |= {c for c, m in CD.MARKETS.items() if m.norgate is None}
    return [c for c in CD.COMMODITIES + CD.FINANCIALS if c not in drop]


def build0_options() -> dict[str, str]:
    b0 = json.loads((RESULTS / "T20-T22" / "build0.json").read_text())
    return {c: b0["markets"][c]["A7"]["option"] for c in CD.XS_UNIVERSE}


def has_data_before(code: str, end: pd.Period) -> bool:
    folder = CD.snapshot_dir(CD.snapshot_for(code)) / "contracts" / code
    if CD.MARKETS[code].norgate is None or not folder.is_dir():
        return False
    man = pd.read_csv(CD.snapshot_dir(CD.snapshot_for(code)) / "manifest.csv", usecols=["market", "first_date"])
    fd = pd.to_datetime(man.loc[man["market"] == code, "first_date"])
    return bool(len(fd)) and fd.min() <= end.end_time


def gap_runs(md: CD.MarketData, which: str, lo: pd.Timestamp, hi: pd.Timestamp) -> list[dict]:
    """Runs of more than GAP_LIMIT consecutive market days with no settlement for the held contract (rule 4)."""
    held = md.held_series(which)
    prev = held.shift(1)
    days = held.index
    sel = (days >= lo) & (days <= hi) & prev.notna().to_numpy()
    out = []
    run_c, run_start, n, last = None, None, 0, None
    for d, c in zip(days[sel], prev[sel]):
        missing = not md.has_settle(c, d)
        if missing and c == run_c:
            n += 1
            last = d
            continue
        if run_c is not None and n > GAP_LIMIT:
            out.append({"contract": run_c, "from": str(run_start.date()), "to": str(last.date()), "days": n})
        run_c, run_start, n, last = (c, d, 1, d) if missing else (None, None, 0, None)
    if run_c is not None and n > GAP_LIMIT:
        out.append({"contract": run_c, "from": str(run_start.date()), "to": str(last.date()), "days": n})
    return out


def market_check(code: str, option: str | None) -> tuple[dict, pd.DataFrame]:
    md = CD.MarketData(code)
    ct = md.contracts
    rolls = md.rolls
    r = rolls.dropna(subset=["F1"])
    cal = md.calendar
    held1, held2 = md.held_series("F1"), md.held_series("F2")
    r1_days = held1.index[1:]                      # = md.daily_returns("F1").index (rows where d-1 is held)
    idx1_first = r1_days[0] if len(r1_days) else None
    idx2_first = held2.index[1] if len(held2) > 1 else None
    entry = B0.entry_month(md, pd.DataFrame(index=r1_days))
    lo_m, hi_m = WIN.CHECK
    start = max(lo_m, entry) if entry is not None else None

    res = {"entry": str(entry) if entry is not None else None, "first_schedule_month": str(rolls.index[0]),
           "first_F1_month": str(r.index[0]) if len(r) else None}
    flags = pd.DataFrame(index=pd.period_range(lo_m, hi_m, freq="M"))
    if start is None or start > hi_m:
        res.update({"in_window": False})
        for k in ("T21", "T22", "T20"):
            flags[k] = False
        return res, flags

    def settled(c, t):
        return isinstance(c, str) and md.has_settle(c, t)

    win = rolls.loc[start:hi_m]
    missing = pd.Series([not (settled(a, t) and settled(b, t)) for a, b, t in
                         zip(win["F1"], win["F2"], win["decision"])], index=win.index)
    cov = float((~missing).mean())
    res.update({"in_window": True, "window_start": str(start), "months": int(len(win)),
                "covered": int((~missing).sum()), "coverage": cov,
                "missing_months": [str(m) for m in missing.index[missing]]})

    # A6 on the window's rebalances (and the exit of the last window month at the 2000-01 execution)
    rw = r.loc[start:hi_m]
    pos = {m: i for i, m in enumerate(r.index)}
    notice_bad = [str(m) for m, row in rw.iterrows()
                  if not ct.at[row["F1"], "notice"] > row["execution"] + pd.Timedelta(days=CD.BUFFER_DAYS)]
    last10, min_left = {"F1": [], "F2": []}, {"F1": 10 ** 6, "F2": 10 ** 6}
    for m, row in rw.iterrows():
        i = pos[m]
        if i + 1 >= len(r):
            continue
        exit_day = r["execution"].iloc[i + 1]
        for w in ("F1", "F2"):
            c = row[w]
            if not isinstance(c, str):
                continue
            left = cal.count_between(exit_day, ct.at[c, "ltd"])
            min_left[w] = min(min_left[w], left)
            if left <= LAST_DAYS:
                last10[w].append(str(m))
    first_bad = [(str(m), w) for m, row in rw.iterrows() for w in ("F1", "F2", "F13")
                 if settled(row[w], row["decision"]) and ct.at[row[w], "first"] > row["decision"]]
    unused = [(str(m), w) for m, row in rw.iterrows() for w in ("F1", "F2")
              if isinstance(row[w], str) and not settled(row[w], row["decision"])]
    # A11: F2 / F13 listed and not delisted early when used
    a11 = []
    for m, row in rw.iterrows():
        t = row["decision"]
        for w in ("F2", "F13"):
            c = row[w]
            if not settled(c, t):
                continue
            rec = ct.loc[c]
            month_start = pd.Timestamp(int(rec["year"]), int(rec["month"]), 1)
            ok = rec["first"] <= t <= rec["last"] and (rec["live"] or (not rec["stopped_early"] and rec["last"]
                                                                        >= month_start - pd.DateOffset(months=2)))
            if not ok:
                a11.append((str(m), w, c))
    lo_d, hi_d = rw["execution"].iloc[0], (r["execution"].iloc[pos[rw.index[-1]] + 1]
                                            if pos[rw.index[-1]] + 1 < len(r) else md.latest)
    gaps1 = gap_runs(md, "F1", lo_d, hi_d)
    gaps2 = gap_runs(md, "F2", lo_d, hi_d)
    # contract-table sources for contracts used in the window
    used = pd.unique(pd.concat([rw["F1"], rw["F2"], rw["F13"]]).dropna())
    cu = ct.loc[[c for c in used if c in ct.index]]
    res["A6"] = {"rebalances": int(len(rw)), "notice_violations": len(notice_bad),
                 "F1_last10_violations": len(last10["F1"]), "F2_last10_violations": len(last10["F2"]),
                 "F1_min_trading_days_left_at_exit": int(min_left["F1"]) if min_left["F1"] < 10 ** 6 else None,
                 "F2_min_trading_days_left_at_exit": int(min_left["F2"]) if min_left["F2"] < 10 ** 6 else None,
                 "first_settle_after_decision": len(first_bad),
                 "chosen_without_settlement_A4.4": len(unused), "chosen_without_settlement_examples": unused[:6],
                 "notice_examples": notice_bad[:6], "last10_examples": {k: v[:6] for k, v in last10.items()}}
    res["A11"] = {"violations": len(a11), "examples": a11[:5]}
    res["gaps_F1"] = gaps1
    res["gaps_F2"] = gaps2
    res["contracts_used"] = int(len(cu))
    res["fnd_source"] = {k: int(v) for k, v in cu["fnd_source"].value_counts().items()}
    res["ltd_source"] = {k: int(v) for k, v in cu["ltd_source"].value_counts().items()}
    res["stopped_early_used"] = [c for c in cu.index if cu.at[c, "stopped_early"]]
    # designated contract months absent from the vendor between the first designated contract and 1999-12
    d = ct[(ct["ym"] <= hi_m.year * 12 + hi_m.month)]
    if len(d):
        lo_ym = int(d["ym"].min())
        exp = [ym for ym in range(lo_ym, hi_m.year * 12 + hi_m.month + 1)
               if CD.MONTH_CODES[(ym - 1) % 12] in md.m.months]
        have = set(d["ym"])
        res["missing_designated"] = [f"{(ym - 1) // 12}{CD.MONTH_CODES[(ym - 1) % 12]}" for ym in exp if ym not in have]
    roll_ok = (len(notice_bad) == 0 and not last10["F1"] and not last10["F2"] and not first_bad and not a11)
    res["checks"] = {"coverage_ok": cov >= COVERAGE_MIN, "roll_rule_ok": roll_ok,
                     "no_F1_gap_over_5": not gaps1, "no_F2_gap_over_5": not gaps2}

    # per-month activity (dates and existence only)
    dec = rolls["decision"]
    ok_month = pd.Series(False, index=flags.index)
    ok_month.loc[missing.index] = ~missing.to_numpy()
    entered = pd.Series(flags.index >= start, index=flags.index)
    base = entered & ok_month
    t21 = []
    for m in flags.index:
        t0 = dec.get(m - 12)
        t21.append(bool(t0 is not None and pd.notna(t0) and idx1_first is not None and idx2_first is not None
                        and t0 >= idx1_first and t0 >= idx2_first))
    t22 = [bool(m in dec.index and idx1_first is not None
                and dec[m] - pd.DateOffset(months=12) >= idx1_first) for m in flags.index]
    if option == "A":
        t20 = [bool(m in rolls.index and settled(rolls.at[m, "F13"], dec[m])) for m in flags.index]
    elif option == "B":
        valid = {m: settled(rolls.at[m, "F1"], dec[m]) and settled(rolls.at[m, "F2"], dec[m])
                 for m in rolls.index}
        t20 = [bool(valid.get(m, False) and sum(valid.get(m - 12 * k, False) for k in range(1, 6)) >= 3)
               for m in flags.index]
    else:
        t20 = [False] * len(flags)
    flags["T21"] = base & pd.Series(t21, index=flags.index)
    flags["T22"] = base & pd.Series(t22, index=flags.index)
    flags["T20"] = base & pd.Series(t20, index=flags.index)
    return res, flags


def run() -> dict:
    WIN.apply()
    OUT.mkdir(parents=True, exist_ok=True)
    xs = list(CD.XS_UNIVERSE)
    t22 = t22_universe()
    opt = build0_options()
    markets = [c for c in CD.MARKETS if c in set(xs) | set(t22)]
    per, flags = {}, {}
    for c in markets:
        if not has_data_before(c, WIN.CHECK[1]):
            per[c] = {"in_window": False, "reason": "no contract with a settlement before 2000 in the primary source"}
            continue
        print(f"[avail] {c}", file=sys.stderr, flush=True)
        per[c], flags[c] = market_check(c, opt.get(c))
    # which markets pass the per-market window checks (trial-specific: T21 and the T20 control also use F2's series)
    def passes(c: str, trial: str) -> bool:
        p = per.get(c, {})
        if not p.get("in_window"):
            return False
        k = p["checks"]
        ok = k["coverage_ok"] and k["roll_rule_ok"] and k["no_F1_gap_over_5"]
        if trial in ("T21", "T20"):
            ok = ok and k["no_F2_gap_over_5"]
        return bool(ok)

    universes = {"T21": xs, "T22": t22, "T20": xs}
    months = pd.period_range(*WIN.CHECK, freq="M")
    counts = pd.DataFrame(0, index=months, columns=["T21", "T22", "T20"])
    passing = {t: [c for c in u if passes(c, t)] for t, u in universes.items()}
    for t, codes in passing.items():
        for c in codes:
            counts[t] += flags[c][t].astype(int)
    first_ok = {t: (str(counts.index[counts[t] >= MIN_ACTIVE][0]) if (counts[t] >= MIN_ACTIVE).any() else None)
                for t in counts}
    # months inside [first_ok, 1999-12] with fewer than MIN_ACTIVE (would hold nothing under rule 3)
    below = {t: [str(m) for m in counts.index if first_ok[t] and m >= pd.Period(first_ok[t], "M")
                 and counts.at[m, t] < MIN_ACTIVE] for t in counts}
    a2 = sum(1 for c in xs if per.get(c, {}).get("in_window") and per[c]["checks"]["coverage_ok"])
    out = {"window_check": [str(WIN.CHECK[0]), str(WIN.CHECK[1])], "min_active": MIN_ACTIVE,
           "universes": universes, "passing": passing,
           "failing": {t: [c for c in u if c not in passing[t]] for t, u in universes.items()},
           "first_month_with_min_active": first_ok, "months_below_min_after_start": below,
           "A2_analogue_xs_markets_with_coverage_ge_95": a2, "markets": per,
           "note": "counts and dates only; no price summarised, no return, signal or statistic computed"}
    (OUT / "availability.json").write_text(json.dumps(out, indent=1, default=str))
    c2 = counts.copy()
    c2.index = c2.index.astype(str)
    c2.index.name = "month"
    c2.rename(columns={"T21": "T21_active_markets", "T22": "T22_active_instruments",
                       "T20": "T20_control_active_markets"}).to_csv(OUT / "availability_counts.csv")
    write_md(out, counts)
    WIN.restore()
    return out


def write_md(out: dict, counts: pd.DataFrame) -> None:
    L = ["# T23-T24 Phase 1: market availability per month, 1978-01..1999-12 (counts and dates only)", "",
         "Produced by `python -m em_macro.t2324_avail run` with the a160bfd data code (`commod_data`, "
         "`commod_build0`) unchanged and the schedule and contract loading moved earlier (`t2324_window`). Only the "
         "existence of a settlement on a date and the contract calendar are used: no price is summarised and no "
         "return, signal or statistic is computed.", "",
         "## First month with at least 6 active markets (pre-registration T20-T22 §2.1 rule 3)", "",
         "| trial | universe checked | markets passing the window checks | first month >= 6 active | months below 6 after it |",
         "|---|---|---|---|---|"]
    names = {"T21": "T21 basis-momentum (T23)", "T22": "T22 diversified trend (T24)", "T20": "T20 carry (control)"}
    for t in ("T21", "T22", "T20"):
        L.append(f"| {names[t]} | {len(out['universes'][t])} | {len(out['passing'][t])}: {' '.join(out['passing'][t])} "
                 f"| **{out['first_month_with_min_active'][t]}** | {len(out['months_below_min_after_start'][t])} |")
    L += ["", f"A2 analogue (20-market cross-sectional universe, F1/F2 coverage >= 95% from the later of 1978-01 and "
          f"entry to 1999-12): **{out['A2_analogue_xs_markets_with_coverage_ge_95']} of 20**.", "",
          "## Per market", "",
          "| market | entry | window from | coverage | A6 notice / F1 last-10 / F2 last-10 / first-settle | A4.4 missing | A11 | F1 gaps > 5d | F2 gaps > 5d | FND source (used contracts) | result T21 / T22 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, p in out["markets"].items():
        if not p.get("in_window"):
            L.append(f"| {c} | {p.get('entry', '—')} | — | — | — | — | — | — | — | — | not in window: "
                     f"{p.get('reason', 'entry after 1999-12')} |")
            continue
        a6 = p["A6"]
        res = " / ".join(("pass" if c in out["passing"][t] else ("fail" if c in out["universes"][t] else "—"))
                         for t in ("T21", "T22"))
        L.append(f"| {c} | {p['entry']} | {p['window_start']} | {100 * p['coverage']:.1f}% ({p['covered']}/{p['months']}) "
                 f"| {a6['notice_violations']} / {a6['F1_last10_violations']} / {a6['F2_last10_violations']} / "
                 f"{a6['first_settle_after_decision']} | {a6['chosen_without_settlement_A4.4']} | "
                 f"{p['A11']['violations']} | {len(p['gaps_F1'])} | {len(p['gaps_F2'])} | "
                 f"{', '.join(f'{k} {v}' for k, v in p['fnd_source'].items())} | {res} |")
    L += ["", "## Active markets per month (December of each year, and the yearly minimum and maximum)", "",
          "| year | T21 Dec | T21 min-max | T22 Dec | T22 min-max | T20 control Dec | T20 min-max |",
          "|---|---|---|---|---|---|---|"]
    for y, g in counts.groupby(counts.index.year):
        L.append(f"| {y} | {g['T21'].iloc[-1]} | {g['T21'].min()}-{g['T21'].max()} | {g['T22'].iloc[-1]} | "
                 f"{g['T22'].min()}-{g['T22'].max()} | {g['T20'].iloc[-1]} | {g['T20'].min()}-{g['T20'].max()} |")
    L += ["", "Monthly counts: `results/T23-T24/availability_counts.csv`; per-market detail: `availability.json`."]
    (OUT / "availability.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        o = run()
        print(json.dumps({k: o[k] for k in ("first_month_with_min_active", "months_below_min_after_start",
                                            "passing", "failing", "A2_analogue_xs_markets_with_coverage_ge_95")},
                         indent=1))
    else:
        sys.exit(__doc__)
