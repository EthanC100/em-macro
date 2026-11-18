"""The HTE attempt log: append-only, hash-chained, fsynced JSONL.

Each line is ``{"seq", "type", "payload", "prev_hash", "hash"}`` plus ``"ts_utc"`` (wall clock, informative only:
it is outside the hashed content so that two identical runs produce identical chains, which is what makes a
registration a *deterministic* record). ``hash`` is the SHA-256 of the canonical form of
``{seq, type, payload, prev_hash}``.

Guarantees and their limits (the same as the Manhattan Ledger's, ARCHITECTURE section 4.1):

* editing or deleting a line breaks every later hash (``verify``);
* deleting a suffix, or replacing the whole file, is detected only against an anchor kept elsewhere
  (``head()`` returns ``{"records", "head"}``; ``verify(anchor=...)`` checks it). Nothing here keeps that anchor
  independently: that is an integration requirement (docs/manhattan/hte/ARCHITECTURE.md section 7);
* a crash during an append can leave a final line without a newline. ``recover_torn_tail`` moves exactly that
  partial line to a quarantine file and appends a ``torn_tail_quarantined`` record naming its SHA-256. A damaged
  line that *does* end in a newline is never repaired: ``verify`` fails and the run stops.

Single writer: the runner's parent process is the only writer; workers return results to it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from manhattan.spec import canonical_bytes

from .ids import sha256_bytes

GENESIS = "0" * 64


class LogError(RuntimeError):
    """The log is damaged, or an append was refused."""


def _record_hash(seq: int, typ: str, payload: dict, prev: str) -> str:
    return sha256_bytes(canonical_bytes({"seq": seq, "type": typ, "payload": payload, "prev_hash": prev}))


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


class AttemptLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
            _fsync_dir(self.path.parent)
        self._records: list[dict] | None = None

    # -- reading -------------------------------------------------------------------------------------------
    def records(self) -> list[dict]:
        if self._records is None:
            self._records = read(self.path)
        return self._records

    def head(self) -> dict:
        recs = self.records()
        return {"records": len(recs), "head": recs[-1]["hash"] if recs else GENESIS}

    # -- writing -------------------------------------------------------------------------------------------
    def append(self, typ: str, payload: dict) -> dict:
        recs = self.records()
        seq = len(recs) + 1
        prev = recs[-1]["hash"] if recs else GENESIS
        # canonicalise the payload once, so what is hashed is exactly what is stored
        payload = json.loads(canonical_bytes(payload))
        rec = {"seq": seq, "type": typ, "payload": payload, "prev_hash": prev,
               "hash": _record_hash(seq, typ, payload, prev)}
        line = dict(rec, ts_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        data = (json.dumps(line, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        with open(self.path, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        recs.append(rec)
        return rec

    def of_type(self, *types: str) -> list[dict]:
        return [r for r in self.records() if r["type"] in types]


def read(path: Path) -> list[dict]:
    """Parse and verify the chain. A file whose last line has no newline raises (call ``recover_torn_tail``)."""
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise LogError(f"{path}: torn final line (no newline); run recover_torn_tail")
    out: list[dict] = []
    prev = GENESIS
    for i, line in enumerate(raw.splitlines(), 1):
        try:
            d = json.loads(line)
        except json.JSONDecodeError as e:
            raise LogError(f"{path}: line {i} is not JSON") from e
        if d.get("seq") != i:
            raise LogError(f"{path}: line {i} has seq {d.get('seq')}")
        if d.get("prev_hash") != prev:
            raise LogError(f"{path}: line {i} breaks the chain")
        h = _record_hash(d["seq"], d["type"], d["payload"], d["prev_hash"])
        if h != d.get("hash"):
            raise LogError(f"{path}: line {i} hash mismatch (edited)")
        out.append({k: d[k] for k in ("seq", "type", "payload", "prev_hash", "hash")})
        prev = h
    return out


def verify(path: Path, anchor: dict | None = None) -> dict:
    recs = read(path)
    head = {"records": len(recs), "head": recs[-1]["hash"] if recs else GENESIS}
    if anchor is not None:
        n = int(anchor["records"])
        if n > len(recs):
            raise LogError(f"{path}: anchor names {n} records, file has {len(recs)} (suffix deleted)")
        at = recs[n - 1]["hash"] if n else GENESIS
        if at != anchor["head"]:
            raise LogError(f"{path}: record {n} does not match the anchor (history replaced)")
    return head


def recover_torn_tail(path: Path) -> dict | None:
    """If the last line has no newline, move it to ``<path>.torn-<n>`` and log the quarantine. Returns the
    quarantine record, or None when the file was intact."""
    path = Path(path)
    raw = path.read_bytes()
    if not raw or raw.endswith(b"\n"):
        return None
    cut = raw.rfind(b"\n") + 1
    torn = raw[cut:]
    n = len(list(path.parent.glob(path.name + ".torn-*")))
    q = path.with_name(f"{path.name}.torn-{n}")
    q.write_bytes(torn)
    with open(path, "r+b") as f:
        f.truncate(cut)
        f.flush()
        os.fsync(f.fileno())
    log = AttemptLog(path)
    log.records()           # verifies the remaining chain
    return log.append("torn_tail_quarantined", {"bytes": len(torn), "sha256": sha256_bytes(torn),
                                                "quarantine": q.name})
