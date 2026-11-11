"""D004: v1.0's pre-committed cut and stop rules, monitored after each official month-end v1.0 run. Flags only.

    python -m ledger.v1_rules monitor            # after the monthly run (workflow v1-rules-monitor.yml)
    python -m ledger.v1_rules monitor --dry-run  # print the result, write nothing
    python -m ledger.v1_rules freeze             # ONE-OFF: computed the rule-5 threshold (refuses to overwrite)

Decision D004 (data/ledger/decisions.csv, 11 Nov 2026) commits to five rules for the frozen v1.0 book (tag
v1.0-frozen, commit 7886867), measured on the official month-end v1.0 index from the 1 Nov 2026 live start:

1. Halve: index 20% or more below its live peak -> halve gross exposure at the next rebalance; restore full
   exposure once the drawdown is back within 10%.
2. Stop: 27% or more below its live peak -> close v1.0 entirely at the next rebalance; restart only as a new
   pre-registered version.
3. Time: live Sharpe after costs below zero at 24 months -> stop v1.0.
4. Instrument: capital controls, a closed market, or a managed peg or crawl in a held currency -> drop it at the
   next rebalance.
5. Carry-spread review: the long-minus-short carry spread below its 2005-2019 10th percentile at two consecutive
   month-ends -> a written review within 7 days. No automatic cut.

**This module never changes exposure.** It reads the official files the monthly run writes and writes only its own
two files, data/ledger/v1_rules.json (the latest evaluation and its flags, shown in the Ledger app and the night
shift's morning report) and data/ledger/v1_rules_history.csv (one row per month-end). Nothing frozen is changed:
em_macro/systematic.py is only imported, read-only, by the one-off ``freeze``. Ethan acts on the flags.

Definitions (all fixed with D004; docs/ledger/v1_rules.md):

* **Official month-end v1.0 index:** 100 on 31 Oct 2026, times (1 + net) for every booked live month (month >=
  2026-11) of results/systematic/paper_pnl.csv, net = ``final_net`` (else ``net``): the same series and column as
  the Ledger app's v1.0 index (ledger/build.py ``build_algorithm``, ledger/books.py ``algo_book``).
* **Live peak / drawdown:** the highest index value so far, the 100 start included; drawdown = index / peak - 1.
* **Rule 1 state:** "halved" from the first month-end with drawdown <= -20% until the first later month-end with
  drawdown >= -10% (then "restore"). It is measured on the official index, which is the frozen book at full exposure.
* **Live Sharpe after costs:** ``ledger.build.perf_stats`` on the live monthly nets (mean x 12 / (sd x sqrt 12),
  sample sd), the app's figure. Net is after the frozen cost model and is an excess-of-cash return. Rule 3 is
  evaluated at the month-end of the 24th live month (2028-10, booked at the 3 Nov 2028 run).
* **Carry spread (rule 5), position-weighted:** at each month-end, the sum over v1.0's positions of signed weight x
  carry, divided by gross exposure (the sum of absolute weights), FX and bonds together, in percentage points a
  year: the carry the book earns per unit of gross exposure. Weights are v1.0's actual month-end weights (live:
  ``size_pct_of_capital`` in results/systematic/positions.csv; history: the frozen run's weights). Carry is the
  algorithm's own (em_macro.systematic ``build_inputs``: FX, local policy rate minus fed funds, monthly averages;
  EM bonds, 10y yield minus the local policy rate; euro spreads, the spread; DE10Y, yield minus policy rate), with
  the latest available month when the current one is missing (as the screener does). Live values come from the
  screener file of the month (results/screener/screener_<as_of>.csv, written by the same monthly run from the same
  inputs). Month-ends counted from as_of 2026-10, the positions held at the live start.
* **Threshold (rule 5):** the 10th percentile (numpy linear interpolation) of that spread over v1.0's month-end
  positions 2006-01..2019-12, computed once from the frozen code, stored with its method and source in
  results/v1_rules/carry_spread_threshold.json and pinned here by its SHA-256 (FROZEN_THRESHOLD_SHA256).
  Definition change (Ethan, 11 Nov 2026, before the first live evaluation): the first threshold used an
  equal-weighted long-minus-short spread, which TRY's carry (about 33pp) dominated; it is kept for the record,
  byte-identical, in results/v1_rules/superseded/ (SUPERSEDED_THRESHOLD_SHA256) and is never used.
* **Rule 4:** a held instrument listed in config/v1_rules_rule4.csv (Ethan's list of capital controls, closed
  markets and managed pegs or crawls, with a date and a source) with a start on or before the month-end and no end.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION_ID = "D004"
LIVE_START_MONTH = "2026-11"          # first booked live month of v1.0 (ledger/build.py LIVE_START_MONTH)
LIVE_START_DAY = "2026-10-31"         # index 100
FIRST_POSITIONS_AS_OF = "2026-10"     # positions held at the live start (effective 2026-11)
HALVE_DD, RESTORE_DD, STOP_DD = -0.20, -0.10, -0.27
TIME_MONTHS = 24
CARRY_CONSECUTIVE = 2
REVIEW_DAYS = 7
THRESHOLD_FILE = ROOT / "results/v1_rules/carry_spread_threshold.json"
THRESHOLD_HISTORY = ROOT / "results/v1_rules/carry_spread_2005_2019.csv"
FROZEN_THRESHOLD_SHA256 = "9ed2edaed46ca6468c67acf1648c428c747b7a3c934e5458425da2eb33641d0c"  # set by `freeze` (position-weighted, 11 Nov 2026)
# the first (equal-weighted) threshold, superseded before the first live evaluation and kept for the record
SUPERSEDED_DIR = ROOT / "results/v1_rules/superseded"
SUPERSEDED_THRESHOLD_FILE = SUPERSEDED_DIR / "carry_spread_threshold_equal_weight.json"
SUPERSEDED_HISTORY_FILE = SUPERSEDED_DIR / "carry_spread_2005_2019_equal_weight.csv"
SUPERSEDED_THRESHOLD_SHA256 = "ef2ca46b9447c4a74ada63003310f15a23435cc5c1f4835d7de45f6246853af3"
RULE4_FILE = ROOT / "config/v1_rules_rule4.csv"
RULE4_COLUMNS = ["instrument", "currency", "event", "start", "end", "source", "note"]
RULE4_EVENTS = ("capital controls", "closed market", "managed peg", "crawl")
STATE_FILE = ROOT / "data/ledger/v1_rules.json"
HISTORY_FILE = ROOT / "data/ledger/v1_rules_history.csv"
HISTORY_COLUMNS = ["as_of", "evaluated_at", "live_months", "index", "peak", "drawdown_pct", "halved", "sharpe",
                   "carry_spread_pp", "carry_threshold_pp", "carry_below", "carry_streak", "rule4_hits", "flags"]
PAPER_PNL = "results/systematic/paper_pnl.csv"
POSITIONS = "results/systematic/positions.csv"
SCREENER = "results/screener/screener_{as_of}.csv"


# ----------------------------------------------------------------------------- small helpers
def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def month_end(month: str) -> date:
    y, m = int(month[:4]), int(month[5:7])
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def next_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y + (m == 12):04d}-{m % 12 + 1:02d}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- the carry spread (rule 5)
def carry_spread(holdings: list[tuple[str, float | None, float | None]]) -> float | None:
    """(instrument, signed weight, carry pp) for every position -> sum(weight x carry) / sum(|weight|), the
    position-weighted carry per unit of gross exposure. Zero weights are ignored. None when nothing is held, or when
    a held position has no weight or no carry."""
    held = [(w, c) for _, w, c in holdings if w is None or w != 0]
    if not held or any(w is None or c is None for w, c in held):
        return None
    gross = sum(abs(w) for w, _ in held)
    return sum(w * c for w, c in held) / gross if gross > 0 else None


def percentile(values: list[float], q: float) -> float:
    """numpy's default (linear interpolation) percentile, without numpy."""
    xs = sorted(values)
    if not xs:
        raise ValueError("no values")
    k = (len(xs) - 1) * q / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def load_threshold(path: Path = THRESHOLD_FILE, expected_sha: str | None = None) -> dict:
    """The frozen threshold, checked against its pinned hash. Returns {} plus an error when missing or changed."""
    expected_sha = FROZEN_THRESHOLD_SHA256 if expected_sha is None else expected_sha
    if not path.exists():
        return {"error": f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} is missing"}
    sha = sha256_file(path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if expected_sha and sha != expected_sha:
        obj["error"] = (f"threshold file changed: SHA-256 {sha[:12]} is not the frozen {expected_sha[:12]} "
                        "(the D004 threshold is computed once and never edited)")
    return obj


def live_carry(as_of: str, positions: list[dict], root: Path = ROOT) -> dict:
    """Rule-5 spread at one month-end from the screener file of that month (carry as the algorithm) and the
    official positions with their signed weights (size_pct_of_capital)."""
    sc = {r["instrument"]: r for r in _rows(root / SCREENER.format(as_of=as_of)) if r.get("as_of") == as_of}
    if not sc:
        return {"spread": None, "error": f"no screener file for {as_of} ({SCREENER.format(as_of=as_of)})"}
    hold, missing, stale, unsized = [], [], [], []
    for p in positions:
        side = (p.get("side") or "").lower()
        if side not in ("long", "short"):
            continue
        r = sc.get(p["instrument"])
        c = _f(r.get("carry")) if r else None
        w = _f(p.get("size_pct_of_capital"))
        if w is not None:
            w = abs(w) if side == "long" else -abs(w)            # the side decides the sign
        if c is None:
            missing.append(p["instrument"])
        elif str(r.get("stale")).lower() == "true":
            stale.append(f"{p['instrument']} ({r.get('data_month')})")
        if w is None:
            unsized.append(p["instrument"])
        hold.append((p["instrument"], w, c))
    out = {"spread": carry_spread(hold), "stale": stale,
           "holdings": [{"instrument": i, "weight_pct": w, "carry_pp": c} for i, w, c in hold]}
    errs = ([f"no carry for held {', '.join(missing)} in the {as_of} screener file"] if missing else []) \
        + ([f"no size_pct_of_capital for held {', '.join(unsized)} in {POSITIONS}"] if unsized else [])
    if errs:
        out["error"] = "; ".join(errs)
    return out


# ----------------------------------------------------------------------------- the official index (rules 1-3)
def official_months(root: Path = ROOT) -> list[dict]:
    """Booked live months of v1.0: [{"month", "net"}], net = final_net (else net), month >= LIVE_START_MONTH."""
    out = []
    for r in _rows(root / PAPER_PNL):
        m = r.get("month") or ""
        if m < LIVE_START_MONTH:
            continue
        net = _f(r.get("final_net")) if _f(r.get("final_net")) is not None else _f(r.get("net"))
        if net is None:
            continue
        out.append({"month": m, "net": net})
    return sorted(out, key=lambda x: x["month"])


def sharpe(nets: list[float]) -> float | None:
    from .build import perf_stats       # the app's own figure
    s = perf_stats(nets).get("sharpe")
    return None if s is None else float(s)


def index_path(months: list[dict]) -> list[dict]:
    """Month-end index, live peak, drawdown and the rule-1 state after every booked live month."""
    idx, peak, halved, out = 100.0, 100.0, False, []
    for i, m in enumerate(months):
        idx *= 1 + m["net"]
        peak = max(peak, idx)
        dd = idx / peak - 1
        was = halved
        if not halved and dd <= HALVE_DD + 1e-12:
            halved = True
        elif halved and dd >= RESTORE_DD - 1e-12:
            halved = False
        out.append({"month": m["month"], "net": m["net"], "index": idx, "peak": peak, "drawdown": dd,
                    "halved": halved, "halve_on": halved and not was, "restore": was and not halved,
                    "stop": dd <= STOP_DD + 1e-12, "live_months": i + 1})
    return out


# v1.0's FX instruments are currency codes; a currency's country also has a bond (XX10Y) or a spread (XX-DE)
CURRENCY_COUNTRY = {"BRL": "BR", "MXN": "MX", "ZAR": "ZA", "TRY": "TR", "IDR": "ID", "PLN": "PL", "GBP": "GB",
                    "COP": "CO", "CLP": "CL"}


def rule4_instruments(currency: str) -> set[str]:
    """The v1.0 instruments exposed to a currency's market: the currency itself and its country's bond or spread."""
    cur = (currency or "").strip().upper()
    cc = CURRENCY_COUNTRY.get(cur)
    return {cur} | ({f"{cc}10Y", f"{cc}-DE"} if cc else set()) if cur else set()


def rule4_hits(positions: list[dict], as_of: str, root: Path = ROOT) -> list[dict]:
    """Held instruments listed in config/v1_rules_rule4.csv (by instrument, or by currency: the currency and its
    country's bond), with a start on or before the month-end and no end on or before it."""
    end = month_end(as_of).isoformat()
    held = [p["instrument"] for p in positions if (p.get("side") or "").lower() in ("long", "short")]
    hits = []
    for r in _rows(root / RULE4_FILE.relative_to(ROOT)):
        start, stop = (r.get("start") or "").strip(), (r.get("end") or "").strip()
        if not start or start > end or (stop and stop <= end):
            continue
        keys = rule4_instruments(r.get("currency", "")) | ({r["instrument"].strip().upper()} if (r.get("instrument") or "").strip() else set())
        for inst in held:
            if inst.upper() in keys and inst not in {h["instrument"] for h in hits}:
                hits.append({"instrument": inst, "event": (r.get("event") or "").strip(), "start": start,
                             "source": (r.get("source") or "").strip(), "note": (r.get("note") or "").strip()})
    return hits


# ----------------------------------------------------------------------------- the evaluation
def evaluate(root: Path = ROOT, now: datetime | None = None, threshold: dict | None = None,
             previous: list[dict] | None = None) -> dict:
    """Evaluate every rule at the latest official month-end. Pure: reads files, writes nothing."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    threshold = load_threshold() if threshold is None else threshold
    positions = _rows(root / POSITIONS)
    as_of = (positions[0].get("as_of") if positions else None) or ""
    months = official_months(root)
    path = index_path(months)
    last = path[-1] if path else None
    nets = [m["net"] for m in months]
    sr = sharpe(nets) if len(nets) >= 2 else None
    thr = _f(threshold.get("threshold_pp"))
    carry = live_carry(as_of, positions, root) if as_of else {"spread": None, "error": "no positions file"}
    spread = carry.get("spread")
    below = (spread < thr) if (spread is not None and thr is not None) else None

    # consecutive month-ends below the threshold, from the history (one row per as_of) plus this month-end
    prev = [r for r in (previous if previous is not None else _rows(root / HISTORY_FILE.relative_to(ROOT)))
            if r.get("as_of") and r["as_of"] < as_of and r["as_of"] >= FIRST_POSITIONS_AS_OF]
    prev = sorted(prev, key=lambda r: r["as_of"])
    streak = 0
    if below:
        streak, expect = 1, as_of
        for r in reversed(prev):
            # only an unbroken run of consecutive month-ends counts
            y, m = int(expect[:4]), int(expect[5:7])
            want = f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"
            if r["as_of"] != want or str(r.get("carry_below")).lower() != "true":
                break
            streak, expect = streak + 1, r["as_of"]

    hits4 = rule4_hits(positions, as_of, root) if as_of else []
    next_rebalance = f"{next_month(as_of)}-03" if as_of else None   # the next scheduled monthly run (3rd)
    rules, flags = [], []

    def rule(n, name, status, detail, action=""):
        rules.append({"rule": n, "name": name, "status": status, "detail": detail, "action": action})
        if status == "triggered":
            flags.append(f"D004 rule {n} ({name}) triggered: {detail}" + (f" -> {action}" if action else ""))

    dd_txt = (f"index {last['index']:.2f}, live peak {last['peak']:.2f}, drawdown {100 * last['drawdown']:.2f}%"
              if last else "no live month booked yet (first official month-end: Nov 2026, booked at the 3 Dec 2026 run)")
    # rule 1: halve / restore
    if last and last["halve_on"]:
        rule(1, "halve", "triggered", f"{dd_txt} (<= -20%)", "halve gross exposure at the next rebalance")
    elif last and last["restore"]:
        rule(1, "halve", "triggered", f"{dd_txt}, back within 10% after a halving",
             "restore full exposure at the next rebalance")
    elif last and last["halved"]:
        rule(1, "halve", "in force", f"{dd_txt}; halved since the rule triggered, restore at a drawdown within 10%",
             "keep gross exposure halved")
    else:
        rule(1, "halve", "ok", f"{dd_txt} (halve at -20%)" if last else dd_txt)
    # rule 2: stop (sticky: once hit, v1.0 is closed for good)
    stop_month = next((p["month"] for p in path if p["stop"]), None)
    if stop_month:
        rule(2, "stop", "triggered", f"drawdown reached -27% or worse at the {stop_month} month-end; now {dd_txt}",
             "close v1.0 entirely at the next rebalance; restart only as a new pre-registered version")
    else:
        rule(2, "stop", "ok", f"{dd_txt} (stop at -27%)" if last else dd_txt)
    # rule 3: time
    n = len(months)
    if n >= TIME_MONTHS:
        sr24 = sharpe(nets[:TIME_MONTHS])
        if sr24 is not None and sr24 < 0:
            rule(3, "time", "triggered", f"live Sharpe after costs {sr24:.2f} < 0 at 24 months ({months[TIME_MONTHS - 1]['month']})",
                 "stop v1.0")
        else:
            rule(3, "time", "passed", f"live Sharpe after costs {sr24 if sr24 is None else round(sr24, 2)} at 24 months "
                                      f"({months[TIME_MONTHS - 1]['month']}): v1.0 continues")
    else:
        rule(3, "time", "ok", f"{n} of 24 live months; live Sharpe after costs "
                              + (f"{sr:.2f}" if sr is not None else "n/a (needs 2 months)") + "; evaluated at 24 months")
    # rule 4: instrument
    if hits4:
        rule(4, "instrument", "triggered",
             "; ".join(f"{h['instrument']}: {h['event']} since {h['start']} ({h['source']})" for h in hits4),
             "drop " + ", ".join(sorted({h['instrument'] for h in hits4})) + " at the next rebalance")
    else:
        rule(4, "instrument", "ok", "no held instrument on the rule-4 list (config/v1_rules_rule4.csv)")
    # rule 5: carry-spread review
    if threshold.get("error"):
        rule(5, "carry-spread review", "error", threshold["error"])
        flags.append(f"D004 rule 5 cannot be checked: {threshold['error']}")
    elif spread is None:
        rule(5, "carry-spread review", "error", carry.get("error") or "carry spread unavailable")
        flags.append(f"D004 rule 5 cannot be checked at {as_of}: {carry.get('error') or 'carry spread unavailable'}")
    else:
        txt = f"carry spread {spread:.2f}pp vs threshold {thr:.2f}pp (2005-2019 10th percentile) at {as_of}"
        if streak >= CARRY_CONSECUTIVE:
            due = (now.date() + timedelta(days=REVIEW_DAYS)).isoformat()
            rule(5, "carry-spread review", "triggered", f"{txt}; below for {streak} consecutive month-ends",
                 f"written review by {due} (no automatic cut)")
        elif below:
            rule(5, "carry-spread review", "watch", f"{txt}; below at 1 month-end (review if below again next month-end)")
        else:
            rule(5, "carry-spread review", "ok", txt)
    if carry.get("stale"):
        rules[-1]["detail"] += f"; stale carry inputs: {', '.join(carry['stale'])}"

    return {
        "decision": DECISION_ID, "as_of": as_of, "month_end": month_end(as_of).isoformat() if as_of else None,
        "evaluated_at": now.isoformat().replace("+00:00", "Z"), "next_rebalance": next_rebalance,
        "live_start": LIVE_START_DAY, "live_months": n, "last_booked_month": last["month"] if last else None,
        "index": round(last["index"], 4) if last else 100.0, "peak": round(last["peak"], 4) if last else 100.0,
        "drawdown_pct": round(100 * last["drawdown"], 3) if last else 0.0, "halved": bool(last and last["halved"]),
        "sharpe": round(sr, 3) if sr is not None else None,
        "carry_spread_pp": round(spread, 4) if spread is not None else None,
        "carry_threshold_pp": round(thr, 4) if thr is not None else None, "carry_below": below,
        "carry_streak": streak, "carry_holdings": carry.get("holdings", []), "rule4_hits": hits4,
        "rules": rules, "flags": flags, "flagged": bool(flags),
        "note": ("Flags only: this monitor never changes exposure and never touches frozen v1.0 code, configs or tags. "
                 "Ethan acts on the flags. Rules and definitions: docs/ledger/v1_rules.md."),
    }


def history_row(res: dict) -> dict:
    return {"as_of": res["as_of"], "evaluated_at": res["evaluated_at"], "live_months": res["live_months"],
            "index": res["index"], "peak": res["peak"], "drawdown_pct": res["drawdown_pct"], "halved": res["halved"],
            "sharpe": "" if res["sharpe"] is None else res["sharpe"],
            "carry_spread_pp": "" if res["carry_spread_pp"] is None else res["carry_spread_pp"],
            "carry_threshold_pp": "" if res["carry_threshold_pp"] is None else res["carry_threshold_pp"],
            "carry_below": "" if res["carry_below"] is None else res["carry_below"], "carry_streak": res["carry_streak"],
            "rule4_hits": ";".join(h["instrument"] for h in res["rule4_hits"]), "flags": " | ".join(res["flags"])}


def write(res: dict, root: Path = ROOT) -> list[str]:
    """data/ledger/v1_rules.json (latest) and one history row per as_of (a re-run of the same month replaces it)."""
    state, hist = root / STATE_FILE.relative_to(ROOT), root / HISTORY_FILE.relative_to(ROOT)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = [r for r in _rows(hist) if r.get("as_of") != res["as_of"]] + [history_row(res)]
    rows.sort(key=lambda r: r["as_of"])
    with hist.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in HISTORY_COLUMNS})
    return [str(STATE_FILE.relative_to(ROOT)), str(HISTORY_FILE.relative_to(ROOT))]


def load_state(root: Path = ROOT) -> dict | None:
    p = root / STATE_FILE.relative_to(ROOT)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def summary_lines(res: dict | None) -> list[str]:
    """Phone lines for the morning report."""
    if not res:
        return ["no evaluation yet (python -m ledger.v1_rules monitor runs after each monthly v1.0 run)"]
    head = (f"{res['as_of']} month-end: index {res['index']:.2f}, drawdown {res['drawdown_pct']:.1f}% from the live peak, "
            f"{res['live_months']} live month(s), Sharpe {res['sharpe'] if res['sharpe'] is not None else 'n/a'}, "
            f"carry spread {res['carry_spread_pp'] if res['carry_spread_pp'] is not None else 'n/a'}pp "
            f"(threshold {res['carry_threshold_pp'] if res['carry_threshold_pp'] is not None else 'n/a'}pp)")
    if not res.get("flags"):
        return [head, "No rule triggered."]
    return [head] + [f"FLAG: {f}" for f in res["flags"]]


# ----------------------------------------------------------------------------- one-off: the threshold
def compute_history(end: str = "2019-12") -> tuple[list[dict], dict]:
    """v1.0's month-end position-weighted carry spread from its first positions to ``end``, from the frozen code
    (read only). Returns (rows, provenance)."""
    import pandas as pd
    from em_macro import systematic as SY
    real_yahoo = SY.S.yahoo
    # the S&P 500 total-return benchmark is not an input to any position; it is stubbed so that the run does not
    # depend on Yahoo (the frozen code itself is not changed)
    SY.S.yahoo = lambda *a, **k: pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    try:
        inp = SY.build_inputs()
        out = SY.run(inp, SY.DESIGN["signals"])
    finally:
        SY.S.yahoo = real_yahoo
    W = out.attrs["weights"]
    C = pd.concat([inp["fx"]["carry"], inp["bond"]["carry"]], axis=1)[W.columns].ffill()
    rows = []
    for t in W.index:
        if str(t) > end:
            break
        w = W.loc[t]
        hold = [(c, float(w[c]), _f(C.at[t, c])) for c in W.columns if w[c] != 0]
        s = carry_spread(hold)
        if s is None:
            continue
        rows.append({"as_of": str(t), "carry_spread_pp": round(s, 6),
                     "gross_leverage": round(sum(abs(h[1]) for h in hold), 6),
                     "n_long": sum(1 for h in hold if h[1] > 0), "n_short": sum(1 for h in hold if h[1] < 0),
                     "positions": " ".join(f"{h[0]}:{h[1]:+.4f}" for h in hold)})
    # provenance: the reproduced net P&L must equal the official in-sample paper P&L
    official = {r["month"]: _f(r.get("net")) for r in _rows(ROOT / PAPER_PNL) if (r.get("month") or "") <= end}
    diffs = [abs(float(out["net"].loc[p]) - official[str(p)]) for p in out.index
             if str(p) <= end and official.get(str(p)) is not None]
    prov = {"months_compared": len(diffs), "max_abs_diff_net": max(diffs) if diffs else None,
            "systematic_py_sha256": sha256_file(ROOT / "em_macro/systematic.py"),
            "daily_panel_sha256": sha256_file(ROOT / "data/processed/daily_panel.csv"),
            "country_month_panel_sha256": sha256_file(ROOT / "data/processed/country_month_panel.csv")}
    return rows, prov


def freeze(now: datetime | None = None) -> dict:
    if THRESHOLD_FILE.exists():
        raise SystemExit(f"{THRESHOLD_FILE.relative_to(ROOT)} exists: the D004 threshold is computed once and frozen")
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    prev = json.loads(SUPERSEDED_THRESHOLD_FILE.read_text(encoding="utf-8")) if SUPERSEDED_THRESHOLD_FILE.exists() else {}
    rows, prov = compute_history("2019-12")
    vals = [r["carry_spread_pp"] for r in rows]
    thr = percentile(vals, 10)
    THRESHOLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with THRESHOLD_HISTORY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["as_of", "carry_spread_pp", "gross_leverage", "n_long", "n_short", "positions"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    obj = {
        "decision": DECISION_ID, "rule": 5, "frozen": True,
        "computed_at": now.isoformat().replace("+00:00", "Z"),
        "threshold_pp": round(thr, 4), "percentile": 10, "window": f"{rows[0]['as_of']}..{rows[-1]['as_of']}",
        "n_month_ends": len(rows), "data_through": "2019-12",
        "distribution_pp": {"min": round(min(vals), 4), "p05": round(percentile(vals, 5), 4),
                            "p10": round(thr, 4), "p25": round(percentile(vals, 25), 4),
                            "median": round(percentile(vals, 50), 4), "max": round(max(vals), 4)},
        "method": ("At each month-end t from v1.0's first positions (2006-01) to 2019-12: v1.0's held positions after the "
                   "no-trade band (em_macro.systematic.run(build_inputs(), DESIGN['signals']).attrs['weights'], frozen "
                   "design, read only); carry of each held instrument at t as the algorithm defines it (build_inputs: FX "
                   "= local policy rate minus fed funds, monthly averages; EM bonds = 10y yield minus local policy rate; "
                   "euro spreads = the spread; DE10Y = yield minus policy rate; percentage points a year; the latest "
                   "available month when t is missing); spread = sum over the held positions of signed weight x carry, "
                   "divided by gross exposure (sum of absolute weights), FX and bonds together, with v1.0's actual "
                   "month-end weights (the same weights as size_pct_of_capital / 100 in the live positions file). "
                   "Threshold = the 10th "
                   "percentile of the monthly spreads (linear interpolation, as numpy.percentile). Only month-ends to "
                   "2019-12 are used; no 2020+ value enters the threshold."),
        "source": ("Frozen v1.0 code em_macro/systematic.py (tag v1.0-frozen, commit 7886867) on the repository's "
                   "processed panels (data/processed/daily_panel.csv, country_month_panel.csv) and the public "
                   "series it downloads (FRED DFF, DEXUSUK, DEXUSEU; BIS policy rates and CPI; Banco de la Republica "
                   "TRM; Banco Central de Chile dolar observado). The S&P 500 benchmark download is stubbed (not a "
                   "position input). Monthly values: results/v1_rules/carry_spread_2005_2019.csv."),
        "reproduction_check": prov,
        "definition_change": {
            "date": "2026-11-11", "decided_by": "Ethan",
            "before_first_live_evaluation": True,
            "previous_definition": ("equal-weighted mean carry of the long positions minus equal-weighted mean carry "
                                    "of the short positions"),
            "previous_threshold_pp": prev.get("threshold_pp"),
            "previous_file": str(SUPERSEDED_THRESHOLD_FILE.relative_to(ROOT)),
            "previous_file_sha256": SUPERSEDED_THRESHOLD_SHA256,
            "why": ("The equal-weighted spread was dominated by TRY (carry about 33pp at the 2026-10 month-end): one "
                    "instrument moved the average of a three-to-five-name side by several points, whatever its size "
                    "in the book. Weighting by v1.0's actual positions measures the carry the book earns per unit of "
                    "gross exposure. Changed on 11 Nov 2026, before the first live evaluation (the 2026-11 month-end, "
                    "booked at the 3 Dec 2026 run); only the 2026-10 baseline had been evaluated, and it is re-run."),
        },
        "note": "Computed once for D004 and never recomputed or edited; ledger/v1_rules.py pins this file's SHA-256.",
    }
    THRESHOLD_FILE.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")
    return {**obj, "sha256": sha256_file(THRESHOLD_FILE)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("monitor", "freeze", "show"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "freeze":
        res = freeze()
        print(json.dumps({k: res[k] for k in ("threshold_pp", "window", "n_month_ends", "sha256",
                                              "reproduction_check")}, indent=1))
        return 0
    if a.command == "show":
        print("\n".join(summary_lines(load_state())))
        return 0
    res = evaluate()
    if not a.dry_run:
        for p in write(res):
            print(f"wrote {p}")
    print("\n".join(summary_lines(res)))
    for r in res["rules"]:
        print(f"  rule {r['rule']} {r['name']}: {r['status']} - {r['detail']}" + (f" -> {r['action']}" if r["action"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
