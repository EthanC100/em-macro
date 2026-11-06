"""T25-T26 pre-registration, availability check (counts and dates only; no price is summarised or stored, no
return is computed).

    DATABENTO_API_KEY=... python -m em_macro.t2526_avail run

For each market of the a160bfd T21 and T22 universes on Databento GLBX.MDP3 (CME, CBOT, NYMEX, COMEX, CME FX):
1. it lists the contracts the a160bfd roll rule (commodities spec §2.3, 35-day buffer, Amendment 3 guard) would hold
   as F1 and F2 at the twelve rebalances December 2026 .. November 2027. It uses the exchange LTD/FND rules of
   em_macro/commod_data.py on a weekday calendar without US federal holidays or Good Friday;
2. it resolves each contract's Globex raw symbol (one-digit year, then two);
3. it counts, over the check window, the trading days on which each contract has a **final** settlement
   (statistics schema, stat_type 3, final bit of stat_flags). The market's trading days are the union of its
   contracts' final-settlement dates.

The pre-registered qualification rule (docs/prereg/T25-T26_live_shadows.md §3.2) is applied to the counts. The request
is quoted first and refused above US$0.50. Settlement values are read only to test that a final settlement exists:
none is kept, printed or written. Outputs: results/T25-T26/availability.md, availability_counts.csv,
availability.json.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import commod_data as CD

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/T25-T26"
CHECK_START = "2026-08-03"
QUOTE_CAP_USD = 0.50
COVERAGE_MIN = 0.95
FIRST_REBALANCE = pd.Period("2026-12", "M")
N_REBALANCES = 12
BUFFER_DAYS, GUARD_DAYS = 35, 10
# the a160bfd universes (results/T20-T22_commodity_trials.md; Build 0 drops 6L, 6Z, FBON, PA stand)
T21_A160 = ["CL", "B", "RB", "HO", "NG", "G", "HG", "ZC", "ZS", "ZW", "KE", "ZM", "ZL", "SB", "KC", "CC", "CT",
            "LE", "GF", "HE"]
T22_A160 = ["CL", "B", "RB", "HO", "NG", "G", "HG", "GC", "SI", "PL", "ZC", "ZS", "ZW", "KE", "ZM", "ZL", "SB", "KC",
            "CC", "CT", "LE", "GF", "HE", "6E", "6B", "6M", "FGBL", "FOAT", "FBTP", "R"]
GLBX_EXCHANGES = {"CME", "CBOT", "NYMEX", "COMEX"}
NOTICE_IS_LTD = {"CL", "B", "RB", "HO", "NG", "G", "SB", "GF", "HE"}      # Amendment 3's markets


def calendar() -> CD.BizCal:
    return CD.BizCal(CD._future_bdays(pd.Timestamp("2025-01-01"), pd.Timestamp("2026-11-05")), "2029-12-31")


def ltd(cal, code: str, y: int, m: int) -> pd.Timestamp:
    return CD.LTD_RULES[CD.MARKETS[code].ltd_rule](cal, y, m)


def notice(cal, code: str, y: int, m: int) -> pd.Timestamp:
    mk = CD.MARKETS[code]
    lt = ltd(cal, code, y, m)
    if mk.fnd_rule:
        return min(CD.FND_RULES[mk.fnd_rule](cal, y, m), lt)
    return lt


def execution(cal, p: pd.Period) -> pd.Timestamp:
    return cal.on_or_after(pd.Timestamp(p.year, p.month, 3))


def designated(code: str, start: pd.Period, n: int = 40) -> list[tuple[int, int]]:
    months = CD.MARKETS[code].months
    out, p = [], start
    while len(out) < n:
        if CD.MONTH_CODES[p.month - 1] in months:
            out.append((p.year, p.month))
        p += 1
    return out


def roll_contracts(cal, code: str, p: pd.Period) -> tuple[tuple[int, int], tuple[int, int]]:
    """(F1, F2) at rebalance month p under the a160bfd rule."""
    ex = execution(cal, p)
    nxt = execution(cal, p + 1)
    cands = designated(code, p - 1)
    for i, (y, m) in enumerate(cands):
        if notice(cal, code, y, m) <= ex + pd.Timedelta(days=BUFFER_DAYS):
            continue
        if code in NOTICE_IS_LTD and cal.count_between(nxt, ltd(cal, code, y, m)) <= GUARD_DAYS:
            continue
        return (y, m), cands[i + 1]
    raise ValueError(code)


def raw_symbols(code: str, y: int, m: int) -> list[str]:
    base = f"{code}{CD.MONTH_CODES[m - 1]}"
    return [f"{base}{y % 10}", f"{base}{y % 100:02d}"]


def plan() -> dict:
    cal = calendar()
    markets = sorted(set(T21_A160) | set(T22_A160), key=(T21_A160 + T22_A160).index)
    out = {}
    for code in markets:
        mk = CD.MARKETS[code]
        row = {"code": code, "name": mk.name, "exchange": mk.exchange, "in_T21": code in T21_A160,
               "in_T22": code in T22_A160, "on_glbx": mk.exchange in GLBX_EXCHANGES}
        if row["on_glbx"]:
            f1s, f2s = [], []
            for k in range(N_REBALANCES):
                a, b = roll_contracts(cal, code, FIRST_REBALANCE + k)
                f1s.append(a)
                f2s.append(b)
            row["dec2026"] = {"F1": f1s[0], "F2": f2s[0]}
            row["contracts_F1"] = sorted(set(f1s))
            row["contracts_F2"] = sorted(set(f2s))
        out[code] = row
    return out


def run() -> dict:
    from .commod_databento import DATASET, SCHEMA, client
    c = client()
    pl = plan()
    rng = c.metadata.get_dataset_range(dataset=DATASET)
    end = str((rng.get("schema", {}).get(SCHEMA) or {}).get("end") or rng["end"])[:19] + "Z"
    sym_of: dict[str, tuple[str, tuple[int, int]]] = {}
    for code, r in pl.items():
        if r["on_glbx"]:
            for ym in sorted(set(r["contracts_F1"]) | set(r["contracts_F2"])):
                for s in raw_symbols(code, *ym):
                    sym_of[s] = (code, ym)
    res = c.symbology.resolve(dataset=DATASET, symbols=list(sym_of), stype_in="raw_symbol", stype_out="instrument_id",
                              start_date=CHECK_START, end_date=end[:10])
    found = {k for k, v in (res.get("result") or {}).items() if v} - set(res.get("not_found") or [])
    chosen: dict[tuple[str, tuple[int, int]], str] = {}
    for s, k in sym_of.items():
        if s in found and k not in chosen:
            chosen[k] = s
    # one request per market (the single request timed out): every request quoted first; refused if the total of
    # the quotes exceeds QUOTE_CAP_USD
    by_market: dict[str, list[str]] = {}
    for (code, ym), s in chosen.items():
        by_market.setdefault(code, []).append(s)
    reqs = {code: dict(dataset=DATASET, symbols=sorted(syms), stype_in="raw_symbol", schema=SCHEMA,
                       start=f"{CHECK_START}T00:00:00Z", end=end) for code, syms in by_market.items()}
    quotes = {code: float(c.metadata.get_cost(**kw)) for code, kw in reqs.items()}
    quote = sum(quotes.values())
    if quote > QUOTE_CAP_USD:
        raise SystemExit(f"refused: total quote US${quote:.4f} above US${QUOTE_CAP_USD}")
    days: dict[str, set] = {}
    for code, kw in reqs.items():
        df = c.timeseries.get_range(**kw).to_df(map_symbols=True).reset_index()
        fin = df[(df["stat_type"] == 3) & ((df["stat_flags"].astype(int) & 1) == 1)]
        for s, g in fin.groupby("symbol"):
            days[s] = set(pd.to_datetime(g["ts_ref"]).dt.date)
        del df, fin                                        # nothing but the dates is kept
        print(f"{code}: {len(kw['symbols'])} contracts counted", flush=True)
    rows, summary = [], {}
    for code, r in pl.items():
        if not r["on_glbx"]:
            summary[code] = {**{k: r[k] for k in ("name", "exchange", "in_T21", "in_T22")}, "qualifies": False,
                             "reason": "not on Databento GLBX.MDP3 (ICE or Eurex): excluded by §3.1"}
            continue
        syms = {ym: chosen.get((code, ym)) for ym in sorted(set(r["contracts_F1"]) | set(r["contracts_F2"]))}
        mdays = set().union(*[days.get(s, set()) for s in syms.values() if s]) if any(syms.values()) else set()
        n = len(mdays)
        cov = {}
        for ym, s in syms.items():
            k = len(days.get(s, set())) if s else 0
            cov[ym] = k / n if n else 0.0
            rows.append({"market": code, "contract": f"{code}-{ym[0]}{CD.MONTH_CODES[ym[1] - 1]}",
                         "symbol": s or "", "role": "/".join(x for x, lst in (("F1", r["contracts_F1"]),
                                                                              ("F2", r["contracts_F2"])) if ym in lst),
                         "final_settlement_days": k, "market_days": n, "share": round(cov[ym], 4)})
        need = set(r["contracts_F1"]) | (set(r["contracts_F2"]) if r["in_T21"] else set())
        f1_ok = all(cov[ym] >= COVERAGE_MIN for ym in r["contracts_F1"])
        f2_ok = all(cov[ym] >= COVERAGE_MIN for ym in r["contracts_F2"])
        q21 = r["in_T21"] and f1_ok and f2_ok
        q22 = r["in_T22"] and f1_ok
        summary[code] = {**{k: r[k] for k in ("name", "exchange", "in_T21", "in_T22")}, "market_days": n,
                         "dec2026_F1": f"{code}-{r['dec2026']['F1'][0]}{CD.MONTH_CODES[r['dec2026']['F1'][1] - 1]}",
                         "dec2026_F2": f"{code}-{r['dec2026']['F2'][0]}{CD.MONTH_CODES[r['dec2026']['F2'][1] - 1]}",
                         "min_share_F1": round(min(cov[ym] for ym in r["contracts_F1"]), 4),
                         "min_share_F2": round(min(cov[ym] for ym in r["contracts_F2"]), 4),
                         "unresolved": [f"{code}-{ym[0]}{CD.MONTH_CODES[ym[1] - 1]}" for ym, s in syms.items() if not s and ym in need],
                         "qualifies_T25": q21, "qualifies_T26": q22}
    meta = {"run_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "dataset": DATASET,
            "schema": SCHEMA, "window": [CHECK_START, end], "quote_usd": round(quote, 6),
            "symbols_requested": len(chosen), "rule": "docs/prereg/T25-T26_live_shadows.md §3.2"}
    write(rows, summary, meta)
    return {"meta": meta, "summary": summary}


def write(rows, summary, meta):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "availability_counts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (OUT / "availability.json").write_text(json.dumps({"meta": meta, "markets": summary}, indent=1, default=str) + "\n")
    t25 = [c for c, s in summary.items() if s.get("qualifies_T25")]
    t26 = [c for c, s in summary.items() if s.get("qualifies_T26")]
    lines = ["# T25-T26 availability check (counts and dates only)", "",
             f"Run {meta['run_at']}, Databento {meta['dataset']} `{meta['schema']}`, final settlements, window "
             f"{meta['window'][0]} .. {meta['window'][1]}; {meta['symbols_requested']} contracts; quoted US${meta['quote_usd']:.4f}. "
             "No settlement value is kept, printed or summarised.", "",
             f"**T25 (T21 rules) qualifying markets ({len(t25)}):** {' '.join(t25)}", "",
             f"**T26 (T22 rules) qualifying markets ({len(t26)}):** {' '.join(t26)}", "",
             "| market | exchange | in T21 | in T22 | market days | F1 at Dec 2026 | F2 at Dec 2026 | min share F1 | min share F2 | T25 | T26 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, s in summary.items():
        if "market_days" not in s:
            lines.append(f"| {c} | {s['exchange']} | {'yes' if s['in_T21'] else ''} | {'yes' if s['in_T22'] else ''} | — | — | — | — | — | no | no |")
            continue
        lines.append(f"| {c} | {s['exchange']} | {'yes' if s['in_T21'] else ''} | {'yes' if s['in_T22'] else ''} | "
                     f"{s['market_days']} | {s['dec2026_F1']} | {s['dec2026_F2']} | {s['min_share_F1']:.3f} | "
                     f"{s['min_share_F2']:.3f} | {'yes' if s['qualifies_T25'] else ('no' if s['in_T21'] else '—')} | "
                     f"{'yes' if s['qualifies_T26'] else ('no' if s['in_T22'] else '—')} |")
    lines += ["", "Shares: final-settlement days of each contract over the market's settlement days in the window; "
              "min over the F1 (and F2) contracts of the twelve rebalances Dec 2026 .. Nov 2027. Per-contract counts: "
              "`availability_counts.csv`.", ""]
    (OUT / "availability.md").write_text("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        print(json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in plan().items()}, indent=1, default=str))
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        r = run()
        print(json.dumps(r["meta"]))
        for c, s in r["summary"].items():
            print(c, s.get("qualifies_T25"), s.get("qualifies_T26"), s.get("min_share_F1"), s.get("min_share_F2"),
                  s.get("unresolved"))
    else:
        print(__doc__)
