"""What changed since the previous update (Home > What changed).

    python -m ledger.changes        # after each automated run: compare with data/ledger/state.json, write
                                    # data/ledger/changes.json, then store the new state

Lists, since the previous update: each book's P&L move (index points; the algorithm's is the estimate, month to date,
until the month is booked), new trades (my decisions, Janus's opens, an algorithm rebalance), stops hit, horizon and
other closes, and forecasts resolved. Forecasts are listed as resolved only: they carry no P&L.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/ledger/state.json"
CHANGES = ROOT / "data/ledger/changes.json"


def _rows(rel):
    p = ROOT / rel
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def snapshot(books: dict, now: str) -> dict:
    a = books["algorithm"]["versions"]
    j = books["janus"]["summary"]
    return {
        "at": now, "as_of": books["as_of"], "latest_mark": books.get("latest_mark"),
        "index": {"me": books["me"]["series"][-1][1] if books["me"]["series"] else 100.0,
                  "algorithm v1.0": a[0]["index"], "algorithm v1.1": a[1]["index"],
                  "janus": j["equity"][-1][1] if j["equity"] else 100.0},
        "algo_effective": {v["id"]: v["effective_from"] for v in a},
        "decisions": {d["id"]: {"status": d.get("status"), "outcome": d.get("outcome"),
                                "note": (d.get("resolution_note") or "")[:120], "instrument": d.get("instrument"),
                                "action": d.get("action")} for d in _rows("data/ledger/decisions.csv")},
        "forecasts": {f["id"]: {"status": f.get("status"), "outcome": f.get("outcome"), "question": f.get("question")}
                      for f in _rows("data/ledger/forecasts.csv")},
        "janus": {p["id"]: {"status": p["status"], "instrument": p["instrument"], "direction": p["direction"],
                            "reason": (p.get("close") or {}).get("reason"), "net": (p.get("close") or {}).get("net_pnl_pct")}
                  for p in j["positions"]},
        "janus_no_trades": len(j["no_trades"]),
    }


def diff(prev: dict | None, cur: dict) -> list[dict]:
    items = []
    if not prev:
        return [{"book": "all", "kind": "baseline", "text": "First snapshot: changes are listed from the next update on."}]
    for b, v in cur["index"].items():
        pv = prev.get("index", {}).get(b)
        if pv is not None and v is not None and abs(v - pv) >= 0.0005:
            items.append({"book": b.split(" ")[0], "kind": "pnl", "label": b, "change": round(v - pv, 4),
                          "text": f"{b}: {v - pv:+.2f} index points (to {v:.2f})"})
    for vid, eff in cur["algo_effective"].items():
        if eff != prev.get("algo_effective", {}).get(vid):
            items.append({"book": "algorithm", "kind": "trade", "text": f"Algorithm {vid} rebalanced: positions effective {eff}"})
    for i, d in cur["decisions"].items():
        p = prev.get("decisions", {}).get(i)
        if p is None:
            items.append({"book": "me", "kind": "trade", "link": f"#/position/me/{i}",
                          "text": f"New decision {i}: {d['action']} {d['instrument']}"})
        elif p["status"] != d["status"] and d["status"] == "resolved":
            stop = "stop hit" in (d.get("note") or "").lower()
            items.append({"book": "me", "kind": "stop" if stop else "close", "link": f"#/position/me/{i}",
                          "text": f"{i} {'stop hit' if stop else 'closed'}: outcome {d.get('outcome')}"})
    for i, f in cur["forecasts"].items():
        p = prev.get("forecasts", {}).get(i)
        if p and p["status"] != f["status"] and f["status"] == "resolved":
            items.append({"book": "forecasts", "kind": "forecast", "link": "#/forecasts",
                          "text": f"Forecast {i} resolved {f.get('outcome')} (Brier only, no P&L)"})
    for i, j in cur["janus"].items():
        p = prev.get("janus", {}).get(i)
        if p is None:
            items.append({"book": "janus", "kind": "trade", "link": f"#/position/janus/{i}",
                          "text": f"Janus opened {i}: {j['direction']} {j['instrument']}"})
        elif p["status"] != j["status"]:
            if j["status"] == "closed":
                kind = "stop" if j.get("reason") == "stop" else "close"
                items.append({"book": "janus", "kind": kind, "link": f"#/position/janus/{i}",
                              "text": f"Janus {i} closed ({j.get('reason')}): net {j.get('net'):+.2f}%"})
            elif j["status"] == "open":
                items.append({"book": "janus", "kind": "trade", "link": f"#/position/janus/{i}",
                              "text": f"Janus {i} filled: {j['direction']} {j['instrument']}"})
            elif j["status"] == "cancelled":
                items.append({"book": "janus", "kind": "close", "link": f"#/position/janus/{i}", "text": f"Janus {i} cancelled"})
    if cur["janus_no_trades"] > prev.get("janus_no_trades", 0):
        items.append({"book": "janus", "kind": "no trade", "link": "#/janus", "text": "Janus reviewed and opened nothing (no-trade record)"})
    return items


def main(argv=None) -> int:
    from . import books as B
    from . import build
    today = date.today()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    bk = B.build_books(today, build.build_algorithm())
    cur = snapshot(bk, now)
    prev = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    items = diff(prev, cur)
    if prev and not items:
        print("no changes since", prev.get("at"))
        return 0
    CHANGES.write_text(json.dumps({"since": prev.get("at") if prev else None, "at": now, "items": items}, indent=1),
                       encoding="utf-8")
    STATE.write_text(json.dumps(cur, indent=1, sort_keys=True), encoding="utf-8")
    for it in items:
        print(it["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
