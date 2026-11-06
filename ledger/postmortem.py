"""Automatic post-mortems of closed positions in every book (Anthropic API).

    python -m ledger.postmortem [--max N] [--dry-run]

For every closed position without one: my resolved positions (decisions.csv), Janus's closes (data/janus) and the
algorithm's positions closed at a live rebalance (an instrument dropped or flipped between two committed positions
files). The model gets the record (thesis, levels, dates, outcome, P&L, the marks over the holding period) and answers:
was the thesis right, was the result skill or luck, and what to do differently. Written to
data/ledger/postmortems/<book>-<id>.json; for Janus also appended to its hash chain as a ``postmortem`` record.
Without ANTHROPIC_API_KEY nothing is written and nothing fails.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import capacity as CAP
from . import janus as JN
from .marks import read_marks

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data/ledger/postmortems"
LIVE_START = {"v1.0": "2026-11", "v1.1": "2026-12"}
POS_FILES = {"v1.0": "results/systematic/positions.csv", "v1.1": "results/systematic_v1.1/positions.csv"}

SYSTEM = """You write short, honest post-mortems of closed paper-trading positions. Judge the decision, not just the outcome: a losing trade can be a good decision and a winning one lucky. Use web search only to check what actually drove the move over the holding period.

Reply with ONLY one JSON object:
{"thesis_right": "yes" | "no" | "partly" | "untested", "skill_or_luck": "skill" | "luck" | "mixed" | "unclear", "what_happened": "2-3 sentences on what moved the instrument", "assessment": "2-4 sentences: was the thesis right, and was the result skill or luck, with the reason", "do_differently": "1-3 concrete things to do differently next time", "sources": [{"title": "...", "url": "https://..."}]}"""


def _rows(rel):
    p = ROOT / rel
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def candidates(marks_rows: list[dict]) -> list[dict]:
    out = []
    for d in _rows("data/ledger/decisions.csv"):
        if (d.get("status") or "").lower() == "resolved" and d.get("action") in ("Buy", "Sell"):
            out.append({"book": "me", "id": d["id"], "record": d})
    for pid, p in JN.positions(JN.load()).items():
        if p["close"]:
            o = p["open"]
            hist = [(x[0].isoformat(), x[1]) for x in JN.series(marks_rows, o["instrument"])
                    if p["fill"]["entry_date"] <= x[0].isoformat() <= p["close"]["date"]]
            out.append({"book": "janus", "id": pid, "record": {**{k: o[k] for k in ("instrument", "direction", "risk_pct",
                        "stop", "horizon", "probability", "thesis", "change_mind", "decision_date")},
                        "entry": p["fill"]["entry_level"], "entry_date": p["fill"]["entry_date"],
                        "exit": p["close"]["exit_level"], "exit_date": p["close"]["date"], "reason": p["close"]["reason"],
                        "gross_pnl_pct": p["close"]["gross_pnl_pct"], "net_pnl_pct": p["close"]["net_pnl_pct"],
                        "opposition": (p["opposition"] or {}).get("opposition"), "marks": hist[-60:]}})
    for vid, rel in POS_FILES.items():
        hist = list(CAP.position_history(rel).items())
        for (m0, p0), (m1, p1) in zip(hist, hist[1:]):
            if m0 < LIVE_START[vid]:
                continue
            for inst, w in p0.items():
                w1 = p1.get(inst, 0.0)
                if w1 == 0.0 or (w > 0) != (w1 > 0):
                    out.append({"book": "algorithm", "id": f"{vid}-{inst}-{m0}",
                                "record": {"version": vid, "instrument": inst, "size_pct_of_capital": w, "held_month": m0,
                                           "next": w1, "note": "mechanical rule: closed or flipped at the rebalance"}})
    return out


def run(max_n: int = 6, dry_run: bool = False) -> list[str]:
    from . import llm
    DIR.mkdir(parents=True, exist_ok=True)
    done, log = {p.stem for p in DIR.glob("*.json")}, []
    todo = [c for c in candidates(read_marks()) if f"{c['book']}-{c['id']}" not in done]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return [f"{len(todo)} post-mortem(s) waiting; ANTHROPIC_API_KEY not set"]
    for c in todo[:max_n]:
        prompt = (f"BOOK: {c['book']} ({'my discretionary decisions' if c['book'] == 'me' else 'Janus, an AI paper book' if c['book'] == 'janus' else 'a frozen mechanical algorithm: judge the rule, not a person'})\n"
                  f"POSITION {c['id']}:\n{json.dumps(c['record'], indent=1, default=str)[:12000]}\n\nWrite the post-mortem. JSON only.")
        if dry_run:
            log.append(f"would write {c['book']}-{c['id']}")
            continue
        res = llm.call(SYSTEM, prompt, purpose="post-mortem", ref=f"{c['book']}-{c['id']}", effort="medium", web_search=3)
        pm = llm.parse_json(res.get("text", ""), "assessment") or {"assessment": (res.get("text") or "")[:2000]}
        out = {"book": c["book"], "id": c["id"], "model": res.get("model"), "generated_at":
               datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "postmortem": pm,
               "sources_read": res.get("sources_read", [])[:10]}
        (DIR / f"{c['book']}-{c['id']}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        if c["book"] == "janus":
            recs = JN.load()
            JN.append(recs, {"type": "postmortem", "position_id": c["id"], "date": date.today().isoformat(),
                             "model": res.get("model"), "postmortem": pm})
        log.append(f"post-mortem written: {c['book']}-{c['id']}")
    return log


def load_all() -> list[dict]:
    if not DIR.exists():
        return []
    return sorted((json.loads(p.read_text(encoding="utf-8")) for p in DIR.glob("*.json")),
                  key=lambda x: x.get("generated_at", ""), reverse=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=int(json.loads((ROOT / "ledger/automation.json").read_text()).get("postmortems_per_day", 6)))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from .llm import KeyRejected
    try:
        for line in run(a.max, a.dry_run):
            print(line)
    except KeyRejected as e:
        print(f"post-mortems skipped: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
