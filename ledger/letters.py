"""Monthly investor letter per book (Me, Algorithm, Janus): figures from the data, narrative from a Claude Code
session (docs/letters/monthly_letters.md, a scheduled task on the 3rd). No API call is made here.

    python -m ledger.letters figures [--month 2026-11]       # JSON: is the month booked, the figures, letters written
    python -m ledger.letters write --month 2026-11 --book me --file N.json --model M

``write`` checks the narrative (summary, what_worked, what_did_not, risk; plain text) and that every percentage it
quotes matches a figure in the data (within rounding), refuses before the algorithm's month is booked by the
3rd-of-month run, and refuses a second letter for the same book and month. It writes
data/ledger/reports/<YYYY-MM-03>_letter-<book>-<month>.md (type "investor letter"), with the figures inserted
verbatim by code, so the narrative can never change a number.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data/ledger/reports"

BOOKS = ("me", "algorithm", "janus")
NARRATIVE_KEYS = ("summary", "what_worked", "what_did_not", "risk")
PCT = re.compile(r"([+\-\u2212]?\d+(?:\.\d+)?)\s*(?:%|per ?cent|percentage points?|pp\b)")


def month_bounds(month: str) -> tuple[date, date]:
    y, m = int(month[:4]), int(month[5:7])
    return date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def figures(month: str, bk: dict) -> dict:
    s, e = month_bounds(month)

    def change(series):
        pts = [p for p in series if p[0] <= e.isoformat()]
        before = [p for p in series if p[0] < s.isoformat()]
        if not pts:
            return None
        base = before[-1][1] if before else 100.0
        return round(pts[-1][1] - base, 4), round(pts[-1][1], 4)
    me, alg, jn = bk["me"], bk["algorithm"], bk["janus"]
    out = {"me": {"month_change_index_pts": change(me["series"]), "open_positions": [
        {k: p.get(k) for k in ("id", "instrument", "action", "size_pct", "live_pnl_pct", "horizon")}
        for p in me["positions"] if p["status"] == "open" and p["action"] in ("Buy", "Sell")],
        "risk_used_pct": me["risk_used_pct"], "brier": me["brier"],
        "resolved_in_month": [p["id"] for p in me["positions"] if p["status"] == "resolved"]}}
    vers = []
    for v in alg["versions"]:
        months = [m for m in (bk.get("_alg_months", {}).get(v["id"]) or []) if m["month"] == month]
        vers.append({"version": v["id"], "live": v["is_live"], "official_month_net_pct":
                     round(100 * months[0]["net"], 3) if months and months[0].get("net") is not None else None,
                     "index": v["index"], "gross_leverage": v["gross_leverage"], "capacity_flagged": v["capacity_flagged"],
                     "attribution": v["attribution"]})
    out["algorithm"] = {"versions": vers}
    js = jn["summary"]
    out["janus"] = {"month_change_index_pts": change(jn["series"]), "open": [
        {k: p.get(k) for k in ("id", "instrument", "direction", "risk_pct", "net_pnl_pct", "horizon")} for p in js["open"]],
        "closed": [{k: p.get(k) for k in ("id", "instrument", "direction", "net_pnl_pct")} for p in js["closed"]],
        "hit_rate": js["hit_rate"], "brier": js["brier"], "risk_used_pct": js["risk_used_pct"],
        "no_trade_weeks": len(js["no_trades"])}
    return out


def render(book: str, month: str, figs: dict, narrative: dict | None, model: str | None) -> str:
    s, e = month_bounds(month)
    letter_date = (e + timedelta(days=3)).isoformat()
    title = {"me": "Me", "algorithm": "Algorithm (v1.0 and v1.1, mechanical rules)", "janus": "Janus (AI experiment)"}[book]
    lines = ["---", f"title: Investor letter, {title}, {s:%B %Y}", f"date: {letter_date}", "type: investor letter",
             "country: Global", "---", "", f"# {title}: {s:%B %Y}", ""]
    n = narrative or {}
    if narrative:
        lines += [n.get("summary", ""), "", "## What worked", "", n.get("what_worked", ""), "",
                  "## What did not", "", n.get("what_did_not", ""), "", "## Risk", "", n.get("risk", ""), ""]
    else:
        lines += ["_No narrative; figures below._", ""]
    lines += ["## Figures (from the data)", "", "```json", json.dumps(figs, indent=1, default=str), "```", "",
              f"_Figures computed by ledger/letters.py from the repository; narrative by {model or '—'}. "
              "Forecasts are scored by Brier only and are not in any P&L._"]
    return "\n".join(lines) + "\n"


def letter_path(book: str, month: str) -> Path:
    _, e = month_bounds(month)
    return REPORTS / f"{(e + timedelta(days=3)).isoformat()}_letter-{book}-{month}.md"


def _numbers(obj) -> list[float]:
    out = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        for v in obj.values():
            out += _numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += _numbers(v)
    return out


def check_narrative(narr: dict, figs: dict) -> list[str]:
    errs = []
    for k in NARRATIVE_KEYS:
        v = narr.get(k)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{k} is required (plain text)")
        elif len(v) > 1500:
            errs.append(f"{k} is longer than 1,500 characters")
    known = [abs(x) for x in _numbers(figs)]
    for k in NARRATIVE_KEYS:
        for m in PCT.finditer(str(narr.get(k) or "")):
            x = abs(float(m.group(1).replace("\u2212", "-")))
            if not any(abs(x - y) <= 0.051 or abs(x - round(y, 0)) < 1e-9 for y in known):
                errs.append(f"{k}: '{m.group(0)}' matches no figure in the data (never invent a number)")
    return errs


def booked(month: str, alg_months: list[dict]) -> bool:
    return any(m["month"] == month and m.get("net") is not None for m in alg_months)


def _context(month: str):
    from . import books as B
    from . import build
    today = date.today()
    alg = build.build_algorithm()
    bk = B.build_books(today, alg)
    bk["_alg_months"] = {"v1.0": alg["months"], "v1.1": alg["v11"]["months"]}
    return figures(month, bk), booked(month, alg["months"])


def write(book: str, month: str, narr: dict, model: str) -> Path:
    if book not in BOOKS:
        raise ValueError(f"book must be one of {BOOKS}")
    if not str(model or "").strip():
        raise ValueError("model is required")
    path = letter_path(book, month)
    if path.exists():
        raise ValueError(f"the {book} letter for {month} already exists ({path.name}); letters are written once")
    figs, is_booked = _context(month)
    if not is_booked:
        raise ValueError(f"{month} is not booked yet (the 3rd-of-month run has not written it); try again later")
    errs = check_narrative(narr, figs[book])
    if errs:
        raise ValueError("; ".join(errs))
    REPORTS.mkdir(parents=True, exist_ok=True)
    path.write_text(render(book, month, figs[book], {k: " ".join(narr[k].split()) for k in NARRATIVE_KEYS}, model.strip()),
                    encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["figures", "write"])
    ap.add_argument("--month", default=None, help="YYYY-MM; default: the month that just ended")
    ap.add_argument("--book", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--model", default="")
    a = ap.parse_args(argv)
    month = a.month or (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    if a.cmd == "figures":
        figs, is_booked = _context(month)
        print(json.dumps({"month": month, "booked": is_booked,
                          "written": [b for b in BOOKS if letter_path(b, month).exists()],
                          "figures": figs}, indent=1, default=str))
        return 0
    try:
        narr = json.loads(Path(a.file).read_text(encoding="utf-8"))
        model = a.model or narr.pop("model", "")
        print(write(a.book, month, narr, model).relative_to(ROOT))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
