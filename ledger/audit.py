"""Audit: hash chains over my decisions, my forecasts and Janus's records.

    python -m ledger.audit seal      # append a seal for every new entry or changed resolution (workflows)
    python -m ledger.audit verify    # verify all three chains (exit 1 on failure); the app shows the result

decisions.csv and forecasts.csv are edited in place when an entry is resolved, so their chain lives beside them in
data/ledger/seals.jsonl. Each seal records the SHA-256 of one entry's *entry fields* (everything written when it
was logged) or of its *resolution fields*, linked to the previous seal (``prev_hash``/``hash`` as in Janus's chain).

Verification fails when:
  * any seal's hash or link does not recompute (the seal file was edited);
  * an entry's current entry fields differ from its sealed ones (a logged decision or forecast was changed);
  * an entry was removed after being sealed.
A changed resolution is not a failure (a Resolve form may override an automatic resolution); it gets a new seal,
so its history stays visible. Entries not yet sealed are reported as ``pending`` (sealed by the next run).
The first seals (2026-11-06) cover the entries as they stood then.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import janus as JN

ROOT = Path(__file__).resolve().parents[1]
SEALS = ROOT / "data/ledger/seals.jsonl"
FILES = {
    "decision": ("data/ledger/decisions.csv",
                 ["status", "outcome", "exit_price", "pnl_pct", "resolved_date", "resolution_note"]),
    "forecast": ("data/ledger/forecasts.csv", ["status", "outcome", "result", "resolved_date"]),
}
GENESIS = "0" * 64


def _rows(rel: str) -> list[dict]:
    p = ROOT / rel
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def fields(kind: str, row: dict) -> tuple[dict, dict]:
    res_cols = FILES[kind][1]
    entry = {k: (v or "") for k, v in row.items() if k not in res_cols}
    res = {k: (row.get(k) or "") for k in res_cols}
    return entry, res


def load(path: Path = SEALS) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def seal(path: Path = SEALS, now: str | None = None) -> list[dict]:
    seals = load(path)
    latest = {}
    for s in seals:
        latest[(s["kind"], s["id"], s["part"])] = s["digest"]
    new = []
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for kind, (rel, _) in FILES.items():
        for row in _rows(rel):
            entry, res = fields(kind, row)
            for part, obj in (("entry", entry), ("resolution", res)):
                if part == "resolution" and not any(obj.values()):
                    continue
                dg = _h(obj)
                if latest.get((kind, row["id"], part)) == dg:
                    continue
                if part == "entry" and (kind, row["id"], "entry") in latest:
                    continue          # never re-seal a changed entry: verify reports it
                rec = {"seq": len(seals) + 1, "kind": kind, "id": row["id"], "part": part, "digest": dg,
                       "sealed_at": now, "prev_hash": seals[-1]["hash"] if seals else GENESIS}
                rec["hash"] = hashlib.sha256((rec["prev_hash"] + _h({k: v for k, v in rec.items() if k != "hash"})).encode()).hexdigest()
                seals.append(rec)
                new.append(rec)
                latest[(kind, row["id"], part)] = dg
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return new


def verify_seals(path: Path = SEALS) -> dict:
    seals = load(path)
    prev = GENESIS
    for i, s in enumerate(seals, 1):
        if s.get("seq") != i or s.get("prev_hash") != prev:
            return {"ok": False, "error": f"seal {i}: chain broken"}
        h = hashlib.sha256((prev + _h({k: v for k, v in s.items() if k != "hash"})).encode()).hexdigest()
        if h != s.get("hash"):
            return {"ok": False, "error": f"seal {i}: content does not match its hash"}
        prev = s["hash"]
    sealed_entry = {}
    for s in seals:
        if s["part"] == "entry":
            sealed_entry[(s["kind"], s["id"])] = s["digest"]
    out = {"ok": True, "error": None, "n_seals": len(seals), "pending": []}
    for kind, (rel, _) in FILES.items():
        rows = {r["id"]: r for r in _rows(rel)}
        for (k, i), dg in sealed_entry.items():
            if k != kind:
                continue
            if i not in rows:
                return {**out, "ok": False, "error": f"{kind} {i} was removed after it was sealed"}
            if _h(fields(kind, rows[i])[0]) != dg:
                return {**out, "ok": False, "error": f"{kind} {i}: logged fields changed after sealing"}
        out["pending"] += [f"{kind} {i}" for i in rows if (kind, i) not in sealed_entry]
        out[f"n_{kind}s"] = len(rows)
    return out


def verify_all() -> dict:
    s = verify_seals()
    j = JN.verify(JN.load())
    ok = s["ok"] and j["ok"]
    parts = []
    parts.append(f"decisions and forecasts: {'verified' if s['ok'] else 'FAILED: ' + str(s['error'])}"
                 + (f" ({len(s['pending'])} awaiting their seal)" if s.get("pending") else ""))
    parts.append(f"Janus: {'verified' if j['ok'] else 'FAILED: ' + str(j['error'])} ({j['n']} records)")
    return {"ok": ok, "label": "record verified" if ok else "record verification FAILED", "detail": "; ".join(parts),
            "seals": s, "janus": j, "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["verify"])[0]
    if cmd == "seal":
        new = seal()
        print(f"{len(new)} new seal(s)")
    v = verify_all()
    print(json.dumps({k: v[k] for k in ("ok", "label", "detail")}))
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
