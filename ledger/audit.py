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

Corrections. A logged field is never edited silently. One correction (``correct_many``, CLI ``correct-file``) may
change several fields of one or more entries for a single stated reason: it appends one record per entry, all with
the same correction id, each listing its ``fields`` (old and new value), and verification then checks that the
correction changed those fields and nothing else.

Single field: ``python -m ledger.audit correct <decision|forecast> <id>
<field> <new value> --reason "..."`` changes one entry field in the CSV and appends a ``correction`` seal (ids
K001, K002, ...) with the old and new value, the reason, and the entry's digest before (``old_digest``) and after
(``digest``). Verification accepts a changed entry only through such a chain of corrections: each correction's
``old_digest`` must equal the entry's sealed digest at that point, and the current row with the corrected field
set back to its old value must hash to ``old_digest`` (so the correction changed that field and nothing else).

Janus records (from K004, config change C06). Janus's chain (data/janus/records.jsonl) is append-only and is never
edited, so a correction to a Janus record changes nothing in it: ``python -m ledger.audit correct-janus spec.json``
appends a ``correction`` seal of kind ``janus`` naming the record (``janus_seq``, ``janus_hash``) and, for each field
(a dotted path such as ``below_budget.until``), the value as recorded (``old``) and the correct value or its effect
(``new``). Verification checks that the record still exists with that hash and still holds every ``old`` value.
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
    # futures/options terms of a decision (ledger/derivs.py) and implied-volatility updates: entry fields only
    "derivative": ("data/ledger/derivatives.csv", []),
    "iv_update": ("data/ledger/iv_updates.csv", []),
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


def _link(seals: list[dict], rec: dict) -> dict:
    rec = {**rec, "seq": len(seals) + 1, "prev_hash": seals[-1]["hash"] if seals else GENESIS}
    rec["hash"] = hashlib.sha256((rec["prev_hash"] + _h({k: v for k, v in rec.items() if k != "hash"})).encode()).hexdigest()
    return rec


def seal(path: Path = SEALS, now: str | None = None) -> list[dict]:
    seals = load(path)
    latest = {}
    for s in seals:
        part = "entry" if s["part"] == "correction" else s["part"]
        latest[(s["kind"], s["id"], part)] = s["digest"]
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


def _dotted(rec: dict, field: str):
    cur = rec
    for k in field.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _check_janus_correction(s: dict, janus: list[dict]) -> str | None:
    """None if a Janus correction seal matches its record (same hash, every old value as recorded), else the error."""
    rec = next((r for r in janus if r.get("seq") == s.get("janus_seq")), None)
    if rec is None or rec.get("hash") != s.get("janus_hash"):
        return f"correction {s.get('correction_id')}: Janus record {s.get('janus_seq')} is missing or changed"
    for f, v in (s.get("fields") or {}).items():
        if str(_dotted(rec, f)) != str(v.get("old")):
            return f"correction {s.get('correction_id')}: Janus record {s.get('janus_seq')} {f} is not {v.get('old')!r}"
    return None


def verify_seals(path: Path = SEALS, janus_path: Path | None = None) -> dict:
    seals = load(path)
    janus = None
    prev = GENESIS
    expected: dict[tuple, str] = {}           # (kind, id) -> the entry digest the chain says is current
    last_corr: dict[tuple, dict] = {}
    for i, s in enumerate(seals, 1):
        if s.get("seq") != i or s.get("prev_hash") != prev:
            return {"ok": False, "error": f"seal {i}: chain broken"}
        h = hashlib.sha256((prev + _h({k: v for k, v in s.items() if k != "hash"})).encode()).hexdigest()
        if h != s.get("hash"):
            return {"ok": False, "error": f"seal {i}: content does not match its hash"}
        prev = s["hash"]
        key = (s["kind"], s["id"])
        if s["part"] == "correction" and s["kind"] == "janus":
            janus = JN.load(janus_path or JN.RECORDS) if janus is None else janus
            err = _check_janus_correction(s, janus)
            if err:
                return {"ok": False, "error": err}
            continue
        if s["part"] == "entry":
            expected[key] = s["digest"]
        elif s["part"] == "correction":
            if expected.get(key) != s.get("old_digest"):
                return {"ok": False, "error": f"correction {s.get('correction_id')} ({s['kind']} {s['id']}) does not "
                                              "follow the entry's sealed state"}
            expected[key] = s["digest"]
            last_corr[key] = s
    out = {"ok": True, "error": None, "n_seals": len(seals), "pending": [],
           "corrections": [s for s in seals if s["part"] == "correction"]}
    for kind, (rel, _) in FILES.items():
        rows = {r["id"]: r for r in _rows(rel)}
        for (k, i), dg in expected.items():
            if k != kind:
                continue
            if i not in rows:
                return {**out, "ok": False, "error": f"{kind} {i} was removed after it was sealed"}
            entry = fields(kind, rows[i])[0]
            if _h(entry) != dg:
                return {**out, "ok": False, "error": f"{kind} {i}: logged fields changed after sealing "
                                                     "(changes are made only through a correction record)"}
            c = last_corr.get((k, i))
            if c and _h({**entry, **_old_fields(c)}) != c["old_digest"]:
                return {**out, "ok": False, "error": f"correction {c['correction_id']} changed more than "
                                                     f"{', '.join(_old_fields(c))}"}
        out["pending"] += [f"{kind} {i}" for i in rows if (kind, i) not in expected]
        out[f"n_{kind}s"] = len(rows)
    return out


def _old_fields(c: dict) -> dict:
    """{field: old value} of a correction record (one field, or several)."""
    if c.get("fields"):
        return {f: v["old"] for f, v in c["fields"].items()}
    return {c["field"]: c["old_value"]}


def corrections(path: Path = SEALS) -> list[dict]:
    """Every correction, oldest first, one item per corrected field (for the app)."""
    out = []
    keys = ("correction_id", "kind", "id", "reason", "sealed_at", "old_digest", "digest", "hash", "seq")
    for s in load(path):
        if s["part"] != "correction":
            continue
        if s.get("fields"):
            out += [{**{k: s.get(k) for k in keys}, "field": f, "old_value": v["old"], "new_value": v["new"]}
                    for f, v in s["fields"].items()]
        else:
            out.append({**{k: s.get(k) for k in keys}, "field": s.get("field"), "old_value": s.get("old_value"),
                        "new_value": s.get("new_value")})
    return out


def correct_many(changes: list[tuple[str, str, dict]], reason: str, path: Path = SEALS, now: str | None = None) -> list[dict]:
    """One correction (one id) changing several logged fields of one or more entries: ``changes`` is a list of
    (kind, id, {field: new value}). Appends one correction record per entry; all or nothing."""
    if not changes:
        raise ValueError("no changes")
    if not (reason or "").strip():
        raise ValueError("a correction needs a reason")
    v = verify_seals(path)
    if not v["ok"]:
        raise ValueError(f"the seal chain does not verify ({v['error']}); fix that first")
    seals = load(path)
    expected = {(s["kind"], s["id"]) for s in seals if s["part"] in ("entry", "correction")}
    n = len({s["correction_id"] for s in seals if s["part"] == "correction"}) + 1
    cid = f"K{n:03d}"
    files, recs = {}, []
    for kind, rid, new_fields in changes:
        if kind not in FILES:
            raise ValueError(f"kind must be one of {sorted(FILES)}")
        rel, res_cols = FILES[kind]
        if rel not in files:
            with (ROOT / rel).open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                files[rel] = (list(reader.fieldnames or []), [dict(r) for r in reader])
        columns, rows = files[rel]
        row = next((r for r in rows if r["id"] == rid), None)
        if row is None:
            raise ValueError(f"{kind} {rid} not found")
        if (kind, rid) not in expected:
            raise ValueError(f"{kind} {rid} is not sealed yet; run `python -m ledger.audit seal` first")
        bad = [f for f in new_fields if f == "id" or f in res_cols or f not in columns]
        if bad:
            raise ValueError(f"{kind} {rid}: not logged entry fields: {', '.join(bad)}")
        same = [f for f, val in new_fields.items() if (row.get(f) or "") == val]
        if same:
            raise ValueError(f"{kind} {rid}: the new value equals the current one for {', '.join(same)}")
        old_digest = _h(fields(kind, row)[0])
        flds = {f: {"old": row.get(f) or "", "new": val} for f, val in new_fields.items()}
        row.update(new_fields)
        recs.append({"kind": kind, "id": rid, "part": "correction", "correction_id": cid, "fields": flds,
                     "field": ", ".join(flds), "reason": " ".join(reason.split()), "old_digest": old_digest,
                     "digest": _h(fields(kind, row)[0]),
                     "sealed_at": now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    linked = []
    for r in recs:
        linked.append(_link(seals + linked, r))
    for rel, (columns, rows) in files.items():
        with (ROOT / rel).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    with path.open("a", encoding="utf-8") as f:
        for r in linked:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return linked


def correct_janus(seq: int, new_fields: dict, reason: str, path: Path = SEALS, janus_path: Path | None = None,
                  now: str | None = None) -> dict:
    """Append a correction seal for one Janus record without editing it (see the module docstring). ``new_fields``:
    {dotted field: correct value or its effect}; the old value is read from the record."""
    if not (reason or "").strip():
        raise ValueError("a correction needs a reason")
    if not new_fields:
        raise ValueError("no fields")
    janus = JN.load(janus_path or JN.RECORDS)
    jv = JN.verify(janus)
    if not jv["ok"]:
        raise ValueError(f"the Janus chain does not verify ({jv['error']})")
    v = verify_seals(path, janus_path)
    if not v["ok"]:
        raise ValueError(f"the seal chain does not verify ({v['error']}); fix that first")
    rec = next((r for r in janus if r.get("seq") == int(seq)), None)
    if rec is None:
        raise ValueError(f"Janus record {seq} not found")
    flds = {}
    for f, new in new_fields.items():
        old = _dotted(rec, f)
        if old is None:
            raise ValueError(f"Janus record {seq} has no field {f}")
        if str(old) == str(new):
            raise ValueError(f"{f}: the new value equals the recorded one")
        flds[f] = {"old": str(old), "new": " ".join(str(new).split())}
    seals = load(path)
    n = len({s["correction_id"] for s in seals if s["part"] == "correction"}) + 1
    out = _link(seals, {"kind": "janus", "id": f"{rec['type']}-{rec['seq']}", "part": "correction",
                        "correction_id": f"K{n:03d}", "janus_seq": rec["seq"], "janus_hash": rec["hash"],
                        "digest": rec["hash"],
                        "record_edited": False, "fields": flds, "field": ", ".join(flds),
                        "reason": " ".join(reason.split()),
                        "sealed_at": now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
    return out


def correct(kind: str, rid: str, field: str, new_value: str, reason: str, path: Path = SEALS,
            now: str | None = None) -> dict:
    """Change one logged field of a sealed entry and append the correction record (see the module docstring)."""
    if kind not in FILES:
        raise ValueError(f"kind must be one of {sorted(FILES)}")
    rel, res_cols = FILES[kind]
    if field == "id" or field in res_cols:
        raise ValueError(f"{field} is not a logged entry field (resolutions are changed with a Resolve form)")
    if not (reason or "").strip():
        raise ValueError("a correction needs a reason")
    v = verify_seals(path)
    if not v["ok"]:
        raise ValueError(f"the seal chain does not verify ({v['error']}); fix that first")
    seals = load(path)
    expected = {}
    for s in seals:
        if s["part"] in ("entry", "correction"):
            expected[(s["kind"], s["id"])] = s["digest"]
    p = ROOT / rel
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    row = next((r for r in rows if r["id"] == rid), None)
    if row is None:
        raise ValueError(f"{kind} {rid} not found")
    if field not in columns:
        raise ValueError(f"{rel} has no column {field}")
    if (kind, rid) not in expected:
        raise ValueError(f"{kind} {rid} is not sealed yet; run `python -m ledger.audit seal` first")
    old_value = row.get(field) or ""
    if old_value == new_value:
        raise ValueError("the new value equals the current one")
    old_digest = _h(fields(kind, row)[0])
    row[field] = new_value
    new_digest = _h(fields(kind, row)[0])
    n = len({s["correction_id"] for s in seals if s["part"] == "correction"}) + 1
    rec = _link(seals, {"kind": kind, "id": rid, "part": "correction", "correction_id": f"K{n:03d}", "field": field,
                        "old_value": old_value, "new_value": new_value, "reason": " ".join(reason.split()),
                        "old_digest": old_digest, "digest": new_digest,
                        "sealed_at": now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return rec


def verify_all() -> dict:
    s = verify_seals()
    j = JN.verify(JN.load())
    ok = s["ok"] and j["ok"]
    parts = []
    parts.append(f"decisions and forecasts: {'verified' if s['ok'] else 'FAILED: ' + str(s['error'])}"
                 + (f" ({len(s['pending'])} awaiting their seal)" if s.get("pending") else "")
                 + (f"; {len({c['correction_id'] for c in s['corrections']})} documented correction(s)"
                    if s.get("corrections") else ""))
    parts.append(f"Janus: {'verified' if j['ok'] else 'FAILED: ' + str(j['error'])} ({j['n']} records)")
    return {"ok": ok, "label": "record verified" if ok else "record verification FAILED", "detail": "; ".join(parts),
            "seals": s, "janus": j, "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    cmd = (args or ["verify"])[0]
    if cmd == "correct":
        import argparse
        ap = argparse.ArgumentParser(prog="python -m ledger.audit correct")
        ap.add_argument("kind", choices=sorted(FILES))
        ap.add_argument("id")
        ap.add_argument("field")
        ap.add_argument("value")
        ap.add_argument("--reason", required=True)
        a = ap.parse_args(args[1:])
        rec = correct(a.kind, a.id, a.field, a.value, a.reason)
        print(json.dumps({k: rec[k] for k in ("correction_id", "kind", "id", "field", "old_value", "new_value")}, indent=1))
    if cmd == "correct-file":
        # {"reason": "...", "changes": [{"kind": "derivative", "id": "D003", "fields": {"field": "new value"}}]}
        spec = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        recs = correct_many([(c["kind"], c["id"], c["fields"]) for c in spec["changes"]], spec["reason"])
        print(json.dumps([{k: r[k] for k in ("correction_id", "kind", "id", "fields")} for r in recs], indent=1))
    if cmd == "correct-janus":
        # {"seq": 199, "reason": "...", "fields": {"below_budget.until": "the correct value or its effect"}}
        spec = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        rec = correct_janus(spec["seq"], spec["fields"], spec["reason"])
        print(json.dumps({k: rec[k] for k in ("correction_id", "kind", "id", "janus_seq", "fields")}, indent=1))
    if cmd == "seal":
        new = seal()
        print(f"{len(new)} new seal(s)")
    v = verify_all()
    print(json.dumps({k: v[k] for k in ("ok", "label", "detail")}))
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
