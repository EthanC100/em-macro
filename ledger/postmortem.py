"""Post-mortems of closed positions in every book, written in the Janus daily review session (no API call).

    python -m ledger.postmortem due                          # closed positions without a post-mortem (JSON)
    python -m ledger.postmortem show <book> <id>             # the position record to judge (JSON)
    python -m ledger.postmortem write <book> <id> --file PM.json [--model M]

Candidates: my resolved positions (decisions.csv), Janus's closes (data/janus) and the algorithm's positions closed
at a live rebalance (an instrument dropped or flipped between two committed positions files). The session judges:
was the thesis right, was the result skill or luck, and what to do differently. ``write`` checks the required fields
(thesis_right, skill_or_luck, assessment, do_differently) and writes data/ledger/postmortems/<book>-<id>.json; for
Janus it also appends a ``postmortem`` record to its hash chain. A post-mortem is written once and never edited.
"""
from __future__ import annotations

import argparse
import csv
import json
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

REQUIRED = {"thesis_right": ("yes", "no", "partly", "untested"), "skill_or_luck": ("skill", "luck", "mixed", "unclear"),
            "assessment": None, "do_differently": None}


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
        # C08: a resize closes one segment and continues the same view in its replacement, like the algorithm's
        # resizes; post-mortems are due for real closes (stops, side flips, exclusions, C08 rule 5), as for the algorithm
        if p["close"] and p["close"].get("reason") != "C08 rebalance":
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


def due(marks_rows: list[dict] | None = None) -> list[dict]:
    DIR.mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in DIR.glob("*.json")}
    return [c for c in candidates(marks_rows if marks_rows is not None else read_marks())
            if f"{c['book']}-{c['id']}" not in done]


def write(book: str, pid: str, pm: dict, model: str, now: str | None = None) -> Path:
    c = next((x for x in due() if x["book"] == book and x["id"] == pid), None)
    if c is None:
        raise ValueError(f"{book}-{pid} is not a closed position awaiting a post-mortem (see `due`)")
    errs = []
    for k, allowed in REQUIRED.items():
        v = str(pm.get(k) or "").strip()
        if not v:
            errs.append(f"{k} is required")
        elif allowed and v.lower() not in allowed:
            errs.append(f"{k} must be one of {allowed}")
    if not str(model or "").strip():
        errs.append("model is required")
    if errs:
        raise ValueError("; ".join(errs))
    out = {"book": book, "id": pid, "model": model.strip(),
           "generated_at": now or datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "postmortem": pm}
    path = DIR / f"{book}-{pid}.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    if book == "janus":
        recs = JN.load()
        JN.append(recs, {"type": "postmortem", "position_id": pid, "date": date.today().isoformat(), "model": model.strip(),
                         "postmortem": pm})
    return path


def load_all() -> list[dict]:
    if not DIR.exists():
        return []
    return sorted((json.loads(p.read_text(encoding="utf-8")) for p in DIR.glob("*.json")),
                  key=lambda x: x.get("generated_at", ""), reverse=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["due", "show", "write"])
    ap.add_argument("book", nargs="?")
    ap.add_argument("id", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--model", default="")
    a = ap.parse_args(argv)
    if a.cmd == "due":
        print(json.dumps([{"book": c["book"], "id": c["id"]} for c in due()], indent=1))
        return 0
    if a.cmd == "show":
        c = next((x for x in candidates(read_marks()) if x["book"] == a.book and x["id"] == a.id), None)
        print(json.dumps(c, indent=1, default=str) if c else "not found")
        return 0 if c else 1
    try:
        pm = json.loads(Path(a.file).read_text(encoding="utf-8"))
        model = a.model or pm.pop("model", "")
        print(write(a.book, a.id, pm, model))
    except (OSError, ValueError, TypeError) as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
