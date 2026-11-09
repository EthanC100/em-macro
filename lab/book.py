"""Lab - experimental: one paper sleeve per idea, frozen at launch.

**Sleeves.** ``lab/sleeves/<id>.yaml`` holds the rules, sizing and retirement date. At launch its SHA-256 is
appended to ``lab/registry.csv``; the book refuses a sleeve whose file no longer matches, so changing a sleeve
means launching a new one with a new id. Required fields:

    id: L001                      # L + 3 digits, equal to the file name
    title: ...
    launched: YYYY-MM-DD
    retire_on: YYYY-MM-DD         # default launch + 6 months; at most 12 months
    nominated_by: explorer        # with the variant ids in exploration_variants
    exploration_variants: [V...]  # rows of results/exploration/log.csv (data to 2019-12-31 only)
    opposition: {p_works: 0-100, summary: "...", model: "..."}   # The Opposition's case, written before launch
    rules: "plain-language rule, frozen"
    kind: static                  # a fixed position held from launch to stop or retirement
    instrument: US10Y             # a daily-marked, non-monthly instrument of data/ledger/instruments.csv
    direction: long | short       # ledger conventions (yields: long = long the bond; FX: long = long the currency)
    stop: <level>                 # in the instrument's own unit, on the losing side of the entry mark
    risk_pct: 0.5                 # % of the Lab account lost at the stop; at most 0.5

**Limits.** 0.5% at risk per sleeve, 5% for the whole Lab (config/night.yaml ``lab``); a launch that would breach
either is refused. **Fills** at the first first-hand daily mark dated on or after the launch date (ledger.marks
``mark_can_act``), like Janus; **closes** at the first acting mark through the stop, or at the last mark on or before
the retirement date. P&L is in % of the Lab account, scaled so that the stop costs exactly ``risk_pct``.

python -m lab.book validate | launch <id> | show [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SLEEVES = ROOT / "lab/sleeves"
REGISTRY = ROOT / "lab/registry.csv"
REG_COLS = ["id", "launched", "sha256", "file"]
LABEL = "Lab - experimental"
MAX_SLEEVE_RISK = 0.5
MAX_TOTAL_RISK = 5.0
MAX_MONTHS = 12
REQUIRED = ("id", "title", "launched", "retire_on", "nominated_by", "opposition", "rules", "kind", "instrument",
            "direction", "stop", "risk_pct")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry(path: Path = REGISTRY) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_sleeve(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _months(a: date, b: date) -> float:
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 31.0


def validate_sleeve(s: dict, fname: str, instruments: dict[str, dict]) -> list[str]:
    errs = [f"{k} is required" for k in REQUIRED if s.get(k) in (None, "")]
    if errs:
        return errs
    sid = str(s["id"])
    if not re.fullmatch(r"L\d{3}", sid) or fname != f"{sid}.yaml":
        errs.append("id must look like L001 and match the file name")
    try:
        launched, retire = date.fromisoformat(str(s["launched"])), date.fromisoformat(str(s["retire_on"]))
        if not 0 < _months(launched, retire) <= MAX_MONTHS:
            errs.append(f"retire_on must be after launch and at most {MAX_MONTHS} months later")
    except ValueError:
        errs.append("launched and retire_on must be YYYY-MM-DD")
    if s["kind"] != "static":
        errs.append("kind must be 'static' (other kinds need code review by Ethan first)")
    reg = instruments.get(str(s["instrument"]))
    if not reg:
        errs.append(f"instrument {s['instrument']} is not in data/ledger/instruments.csv")
    elif reg.get("frequency") != "daily":
        errs.append(f"instrument {s['instrument']} has no daily mark (monthly marks never act)")
    if str(s["direction"]).lower() not in ("long", "short"):
        errs.append("direction must be long or short")
    try:
        r = float(s["risk_pct"])
        if not 0 < r <= MAX_SLEEVE_RISK + 1e-9:
            errs.append(f"risk_pct must be in (0, {MAX_SLEEVE_RISK}]")
        float(s["stop"])
    except (TypeError, ValueError):
        errs.append("risk_pct and stop must be numbers")
    op = s.get("opposition") or {}
    if not isinstance(op, dict) or op.get("p_works") is None or not str(op.get("summary") or "").strip():
        errs.append("opposition must give p_works and summary (The Opposition writes its case before launch)")
    text = json.dumps(s).lower()
    if any(w in text for w in ("norgate", "databento", "settlement")):
        errs.append("sleeves use public daily marks only: no Norgate data or licensed settlements")
    return errs


def _instruments() -> dict[str, dict]:
    from ledger.marks import load_registry
    return {r["instrument"]: r for r in load_registry()}


def sleeves(root: Path = SLEEVES) -> list[tuple[Path, dict]]:
    return [(p, load_sleeve(p)) for p in sorted(root.glob("L*.yaml"))]


def check_frozen(items: list[tuple[Path, dict]], reg: list[dict]) -> list[str]:
    by_id = {r["id"]: r for r in reg}
    errs = []
    for p, s in items:
        r = by_id.get(str(s.get("id")))
        if r and r["sha256"] != sha256(p):
            errs.append(f"{s.get('id')}: file changed after launch (frozen); launch a new sleeve instead")
    return errs


def launch(sid: str, today: date, root: Path = SLEEVES, reg_path: Path = REGISTRY,
           instruments: dict | None = None) -> dict:
    p = root / f"{sid}.yaml"
    s = load_sleeve(p)
    instruments = instruments if instruments is not None else _instruments()
    errs = validate_sleeve(s, p.name, instruments)
    reg = registry(reg_path)
    if any(r["id"] == sid for r in reg):
        errs.append(f"{sid} is already launched")
    live = [x for _, x in sleeves(root) if any(r["id"] == str(x.get("id")) for r in reg)
            and date.fromisoformat(str(x["retire_on"])) >= today]
    total = sum(float(x["risk_pct"]) for x in live) + float(s.get("risk_pct") or 0)
    if total > MAX_TOTAL_RISK + 1e-9:
        errs.append(f"the Lab would have {total:.2f}% at risk, above {MAX_TOTAL_RISK}%")
    if errs:
        raise ValueError("; ".join(errs))
    new = not reg_path.exists()
    with reg_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REG_COLS)
        if new:
            w.writeheader()
        row = {"id": sid, "launched": today.isoformat(), "sha256": sha256(p), "file": f"lab/sleeves/{p.name}"}
        w.writerow(row)
    return row


def sleeve_pnl(s: dict, marks: list[dict], reg: dict, today: date) -> dict:
    """Daily P&L (% of the Lab account) of a static sleeve from public daily marks."""
    from ledger import pricing as PX
    from ledger.marks import mark_can_act
    k = PX.kind_of(reg)
    inst, direction, stop, risk = s["instrument"], str(s["direction"]).lower(), float(s["stop"]), float(s["risk_pct"])
    launched, retire = date.fromisoformat(str(s["launched"])), date.fromisoformat(str(s["retire_on"]))
    rows = sorted((r for r in marks if r.get("instrument") == inst and mark_can_act(r)
                   and r.get("value") not in (None, "")), key=lambda r: r["date"])
    rows = [r for r in rows if launched <= date.fromisoformat(r["date"]) <= min(today, retire)]
    out = {"id": s["id"], "title": s["title"], "instrument": inst, "direction": direction, "risk_pct": risk,
           "launched": str(launched), "retire_on": str(retire), "status": "pending", "series": [], "pnl_pct": 0.0}
    if not rows:
        return out
    entry = float(rows[0]["value"])
    sr = PX.stop_return(k, direction, entry, stop)
    if sr is None or sr >= 0:
        return {**out, "status": "cancelled", "note": "the entry mark was already through the stop"}
    out.update(status="open", entry=entry, entry_date=rows[0]["date"])
    for r in rows:
        v = float(r["value"])
        ret = PX.position_return(k, direction, entry, v)
        pnl = max(-risk, risk * ret / abs(sr)) if ret is not None else None
        if pnl is None:
            continue
        out["series"].append([r["date"], round(pnl, 4)])
        out["pnl_pct"] = round(pnl, 4)
        if PX.stop_hit(k, direction, entry, stop, v):
            out.update(status="closed (stop)", closed=r["date"])
            break
    if out["status"] == "open" and today >= retire:
        out.update(status="retired", closed=out["series"][-1][0] if out["series"] else str(retire))
    return out


def build(today: date) -> dict:
    """The Lab page's data: its own account index, sleeves and limits. Never merged into any other book."""
    from ledger.marks import read_marks
    reg = registry()
    items = sleeves()
    launched = {r["id"] for r in reg}
    inst = _instruments()
    marks = read_marks()
    errs = check_frozen(items, reg)
    out_sleeves, by_day = [], {}
    for p, s in items:
        if str(s.get("id")) not in launched:
            continue
        e = validate_sleeve(s, p.name, inst)
        if e:
            errs += [f"{s.get('id')}: {x}" for x in e]
            continue
        sp = sleeve_pnl(s, marks, inst[s["instrument"]], today)
        out_sleeves.append(sp)
        for d, v in sp["series"]:
            by_day.setdefault(d, {})[sp["id"]] = v
    # account index: 100 + sum of each sleeve's latest cumulative P&L on each day (carried between marks)
    series, cur = [], {}
    for d in sorted(by_day):
        cur.update(by_day[d])
        series.append([d, round(100 + sum(cur.values()), 4)])
    at_risk = sum(x["risk_pct"] for x in out_sleeves if x["status"] in ("open", "pending"))
    return {"label": LABEL, "today": today.isoformat(), "series": series, "sleeves": out_sleeves,
            "proposed": [str(s.get("id")) for _, s in items if str(s.get("id")) not in launched],
            "risk_used_pct": round(at_risk, 4), "limits": {"per_sleeve_pct": MAX_SLEEVE_RISK, "total_pct": MAX_TOTAL_RISK},
            "errors": errs,
            "note": ("Lab - experimental: paper sleeves launched by the night shift from ideas tested on data to "
                     "2019-12-31 only. Separate from my book, the algorithm, Janus, the T25-T26 shadows and the "
                     "fund; nothing here is a trial result or claims an edge. Public daily marks only.")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["validate", "launch", "show"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()
    if a.cmd == "validate":
        inst, errs = _instruments(), check_frozen(sleeves(), registry())
        for p, s in sleeves():
            errs += [f"{p.name}: {e}" for e in validate_sleeve(s, p.name, inst)]
        print("\n".join(errs) or "lab ok")
        return 1 if errs else 0
    if a.cmd == "launch":
        try:
            print(json.dumps(launch(a.id, today)))
        except ValueError as e:
            print(f"refused: {e}")
            return 1
        return 0
    print(json.dumps(build(today), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
