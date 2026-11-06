"""Monthly investor letter per book, generated on the 3rd (figures from the data, narrative via the API).

    python -m ledger.letters [--month 2026-11]     # default: the month that just ended

One letter per book (Me, Algorithm, Janus), written to data/ledger/reports/<YYYY-MM-03>_letter-<book>-<month>.md
(type "investor letter") and archived under Reports. The figures (performance, contributors, positions, risk) are
computed here from the repository's data and inserted as they are; the model writes only the narrative sections
(what worked, what did not, outlook for the risk) and must not invent figures. Without ANTHROPIC_API_KEY the letter
is written with the figures and a note in place of the narrative.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data/ledger/reports"

SYSTEM = """You write the narrative sections of a short monthly investor letter for one paper-trading book. Use ONLY the figures given; never invent a number, a position or an event that is not in the data. Plain, direct English, no hype. If the book is the algorithm, it is a frozen set of mechanical rules: describe what the rules did, do not second-guess them. If the book is Janus, it is an AI experiment with no claimed edge.

Reply with ONLY one JSON object:
{"summary": "2-3 sentences", "what_worked": "2-4 sentences", "what_did_not": "2-4 sentences", "risk": "2-3 sentences on current positions and risk"}"""


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
        lines += ["_Narrative not generated (ANTHROPIC_API_KEY not set); figures below._", ""]
    lines += ["## Figures (from the data)", "", "```json", json.dumps(figs, indent=1, default=str), "```", "",
              f"_Figures computed by ledger/letters.py from the repository; narrative by {model or '—'}. "
              "Forecasts are scored by Brier only and are not in any P&L._"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    from . import books as B
    from . import build
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=None)
    a = ap.parse_args(argv)
    today = date.today()
    month = a.month or (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    alg = build.build_algorithm()
    bk = B.build_books(today, alg)
    bk["_alg_months"] = {"v1.0": alg["months"], "v1.1": alg["v11"]["months"]}
    figs = figures(month, bk)
    REPORTS.mkdir(parents=True, exist_ok=True)
    from . import llm
    for book in ("me", "algorithm", "janus"):
        narrative, model = None, None
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                res = llm.call(SYSTEM, f"BOOK: {book}\nMONTH: {month}\nFIGURES:\n{json.dumps(figs[book], indent=1, default=str)}",
                               purpose="investor letter", ref=f"{book}-{month}", effort="medium", web_search=0, max_tokens=8000)
                narrative, model = llm.parse_json(res.get("text", ""), "summary"), res.get("model")
            except llm.KeyRejected as e:
                print(f"narrative skipped: {e}")
        _, e = month_bounds(month)
        path = REPORTS / f"{(e + timedelta(days=3)).isoformat()}_letter-{book}-{month}.md"
        path.write_text(render(book, month, figs[book], narrative, model), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
