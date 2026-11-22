"""A LOCAL-FILE stand-in for the external ledger anchors of docs/manhattan/audit/S17_ANCHOR_DESIGN.md (design only).

It implements the record format of section 3 (without the signature, which needs the owner's runner key) and the
verification of section 5, so that the harness and its tamper drills exercise the same interface the real anchors
repository will have. It is **not** independent custody: the anchors file sits next to the ledger and is written
by the same process, so ``independently_anchored`` is always ``False`` here (owner decision D-7). Nothing here
creates a repository, a key, a token or a network connection.

    write_anchor(anchors_dir, ledger_path, event=..., run_id=..., code_commit=..., utc=...)
    verify_against_anchor(ledger_path, anchors_dir)  ->  {"ok": bool, "problems": [...], ...}

Anchor line (canonical JSON: sorted keys, no spaces), one per line in ``<anchors_dir>/<ledger_id>.jsonl``::

    {"schema": "manhattan.anchor/1-localstub", "ledger_id": sha256(first ledger line), "records": n,
     "head": hash of record n, "event": ..., "run_id": ..., "code_commit": ..., "utc": ...,
     "prev_anchor": sha256(previous anchor line) | "genesis", "custody": "local-file stub ..."}

Verification (section 5): the anchors' own ``prev_anchor`` chain and ledger id; the ledger's hash chain; the ledger
holds at least the latest anchor's records (truncation below an anchor is refused); the record at every anchor's
position has that anchor's head (a hash-valid rewrite of an anchored prefix is refused); records after the latest
anchor are an unanchored tail, allowed only while a run is open.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from manhattan import ledger as L

SCHEMA = "manhattan.anchor/1-localstub"
EVENTS = ("batch_freeze", "run_close", "heartbeat", "key_rotation", "incident")
GENESIS_ANCHOR = "genesis"
CUSTODY = "local-file stub: same custody as the ledger, not independent (D-7); no signature, no timestamp proof"
FIELDS = ("schema", "ledger_id", "records", "head", "event", "run_id", "code_commit", "utc", "prev_anchor", "custody")


class AnchorError(RuntimeError):
    """An anchor cannot be written (fail closed)."""


def _line(rec: dict) -> bytes:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ledger_lines(snapshot: bytes) -> list[bytes]:
    return [x for x in snapshot.split(b"\n") if x.strip()]


def ledger_id(snapshot: bytes) -> str:
    """SHA-256 of the ledger's first record line: stable across copies and paths."""
    lines = ledger_lines(snapshot)
    if not lines:
        raise AnchorError("an empty ledger has no identity to anchor")
    return _sha(lines[0])


def anchors_path(anchors_dir: Path, lid: str) -> Path:
    return Path(anchors_dir) / f"{lid}.jsonl"


def read_anchors(path: Path) -> list[tuple[dict, bytes]]:
    if not path.is_file():
        return []
    return [(json.loads(x.decode("utf-8")), x) for x in path.read_bytes().split(b"\n") if x.strip()]


def write_anchor(anchors_dir: Path, ledger_path: Path, *, event: str, run_id: str, code_commit: str,
                 utc: str | None = None) -> dict:
    """Append one anchor of the ledger's current state. Refuses if the ledger does not verify or does not extend
    the anchors already written (an anchor never papers over a mismatch)."""
    if event not in EVENTS:
        raise AnchorError(f"unknown anchor event {event}")
    snapshot = Path(ledger_path).read_bytes()
    recs, errs = L.verify_snapshot(snapshot)
    if errs:
        raise AnchorError("the ledger does not verify: " + "; ".join(errs))
    lid = ledger_id(snapshot)
    path = anchors_path(anchors_dir, lid)
    prior = read_anchors(path)
    if prior:
        check = verify_against_anchor(ledger_path, anchors_dir, open_run=True)
        if not check["ok"]:
            raise AnchorError("the ledger no longer matches its anchors: " + "; ".join(check["problems"]))
    rec = {"schema": SCHEMA, "ledger_id": lid, "records": len(recs), "head": recs[-1]["hash"], "event": event,
           "run_id": run_id, "code_commit": code_commit,
           "utc": utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "prev_anchor": _sha(prior[-1][1]) if prior else GENESIS_ANCHOR, "custody": CUSTODY}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        f.write(_line(rec) + b"\n")
    return rec


def verify_against_anchor(ledger_path: Path, anchors_dir: Path, *, open_run: bool = False) -> dict:
    """S17_ANCHOR_DESIGN.md section 5 against the local anchors file. Never raises for a mismatch: returns
    ``ok: False`` with the problems (fail closed for every caller that checks ``ok``)."""
    problems: list[str] = []
    out = {"ok": False, "problems": problems, "ledger_records": 0, "anchored_records": 0, "tail": 0, "anchors": 0,
           "latest_event": None, "checked_against_anchor": False, "independently_anchored": False,
           "custody": CUSTODY}
    try:
        snapshot = Path(ledger_path).read_bytes()
    except OSError:
        problems.append("the ledger cannot be read")
        return out
    recs, errs = L.verify_snapshot(snapshot)
    problems += [f"ledger chain: {e}" for e in errs]
    out["ledger_records"] = len(recs)
    if not recs:
        problems.append("the ledger is empty")
        return out
    lid = ledger_id(snapshot)
    anchors = read_anchors(anchors_path(anchors_dir, lid))
    if not anchors:
        problems.append("no anchor for this ledger id (its first record was rewritten, or it was never anchored)")
        return out
    out["anchors"] = len(anchors)
    prev, last_n = GENESIS_ANCHOR, 0
    for i, (a, raw) in enumerate(anchors, 1):
        if set(a) != set(FIELDS) or _line(a) != raw or a["schema"] != SCHEMA or a["event"] not in EVENTS:
            problems.append(f"anchor {i}: malformed or not canonical")
            return out
        if a["prev_anchor"] != prev:
            problems.append(f"anchor {i}: prev_anchor breaks the anchor chain (an anchor was removed or edited)")
        if a["ledger_id"] != lid:
            problems.append(f"anchor {i}: names another ledger")
        if type(a["records"]) is not int or a["records"] < max(last_n, 1):
            problems.append(f"anchor {i}: record count runs backwards")
        prev, last_n = _sha(raw), a["records"] if type(a["records"]) is int else last_n
    latest = anchors[-1][0]
    out["anchored_records"], out["latest_event"] = latest["records"], latest["event"]
    if len(recs) < latest["records"]:
        problems.append(f"truncated: the ledger holds {len(recs)} records, the latest anchor {latest['records']}")
    for i, (a, _) in enumerate(anchors, 1):
        n = a["records"]
        if type(n) is int and 1 <= n <= len(recs) and recs[n - 1]["hash"] != a["head"]:
            problems.append(f"anchor {i}: record {n} no longer has the anchored head (the prefix was rewritten)")
    tail = max(len(recs) - latest["records"], 0)
    out["tail"] = tail
    if tail and not open_run:
        problems.append(f"{tail} record(s) after the latest anchor: unanchored, allowed only while a run is open")
    out["checked_against_anchor"] = out["ok"] = not problems
    return out
