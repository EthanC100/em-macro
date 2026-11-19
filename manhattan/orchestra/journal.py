"""The orchestrator's journal and its file locks.

The journal is an append-only JSONL hash chain, the same construction as the Manhattan Ledger and the HTE attempt
log: each line is ``{"seq", "type", "payload", "prev_hash", "hash"}`` plus an informative ``ts_utc`` outside the hash.
Every append is fsynced. Editing a line breaks every later hash; deleting a suffix is detected against an anchor kept
elsewhere (``head()``; the status snapshot carries the latest one).

Writers: the supervisor and the CLI (register, cancel, requeue, pause). Each append happens under the journal lock
(``Journal.locked``, a blocking ``flock`` with a timeout) after re-reading the file, so two writers never fork the
chain. Invocation processes never write the journal: they leave files that the supervisor imports.

A crash during an append can leave a final line without a newline. Reading tolerates it; the next writer, under the
lock, moves the partial line to ``journal.jsonl.torn-<n>`` (fsynced first) and records ``journal_torn_tail`` with its
SHA-256. A damaged line that ends in a newline is never repaired: reading raises and the orchestrator stops.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


class JournalError(RuntimeError):
    """The journal is damaged, or a write was refused."""


def canonical(obj) -> bytes:
    """Canonical JSON (sorted keys, no whitespace, UTF-8). Floats must be finite."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def full_hash(obj) -> str:
    return sha256_bytes(canonical(obj))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# -- file locks -----------------------------------------------------------------------------------------------

_HELD: set[int] = set()


def _close_inherited() -> None:
    """In a forked child, close every lock descriptor this process held. An ``flock`` belongs to the open file
    description, which a fork shares; a worker that kept it would keep the lock after its parent died."""
    for fd in list(_HELD):
        try:
            os.close(fd)
        except OSError:
            pass
    _HELD.clear()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_close_inherited)


class FileLock:
    """An exclusive ``flock`` on one file. Released by the operating system when the process dies; never inherited
    by forked children (see ``_close_inherited``) or by exec'd ones (Python opens files non-inheritable)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._f = None

    def acquire(self, timeout: float = 0.0, poll: float = 0.05) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.path, "a+")
        end = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    f.close()
                    return False
                time.sleep(poll)
        self._f = f
        _HELD.add(f.fileno())
        return True

    def release(self) -> None:
        if self._f is None:
            return
        _HELD.discard(self._f.fileno())
        try:
            fcntl.flock(self._f.fileno(), fcntl.LOCK_UN)
        finally:
            self._f.close()
            self._f = None

    @property
    def held(self) -> bool:
        return self._f is not None

    def __enter__(self):
        if not self.acquire():
            raise JournalError(f"{self.path} is held by another process")
        return self

    def __exit__(self, *exc):
        self.release()


def is_held_elsewhere(path: Path) -> bool:
    """True when another process holds the lock on ``path``. Probing takes the lock for an instant, so the holder
    must acquire with a timeout (``FileLock.acquire(timeout=...)``), never once."""
    path = Path(path)
    if not path.exists():
        return False
    lk = FileLock(path)
    if lk.acquire(timeout=0.0):
        lk.release()
        return False
    return True


# -- atomic files ---------------------------------------------------------------------------------------------

def fsync_dir(path: Path) -> None:
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


def atomic_write(path: Path, data: bytes) -> str:
    """Write ``data`` to ``path`` atomically (temporary file, fsync, rename, fsync of the directory). Returns its
    SHA-256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fsync_dir(path.parent)
    return sha256_bytes(data)


def atomic_write_json(path: Path, obj) -> str:
    return atomic_write(path, json.dumps(obj, sort_keys=True, indent=1, allow_nan=False).encode() + b"\n")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# -- the journal ----------------------------------------------------------------------------------------------

def _record_hash(seq: int, typ: str, payload: dict, prev: str) -> str:
    return full_hash({"seq": seq, "type": typ, "payload": payload, "prev_hash": prev})


def parse(raw: bytes, path="journal") -> list[dict]:
    out, prev = [], GENESIS
    for i, line in enumerate(raw.splitlines(), 1):
        try:
            d = json.loads(line)
        except json.JSONDecodeError as e:
            raise JournalError(f"{path}: line {i} is not JSON") from e
        if d.get("seq") != i:
            raise JournalError(f"{path}: line {i} has seq {d.get('seq')}")
        if d.get("prev_hash") != prev:
            raise JournalError(f"{path}: line {i} breaks the chain")
        if _record_hash(d["seq"], d["type"], d["payload"], d["prev_hash"]) != d.get("hash"):
            raise JournalError(f"{path}: line {i} hash mismatch (edited)")
        out.append({k: d[k] for k in ("seq", "type", "payload", "prev_hash", "hash", "ts_utc") if k in d})
        prev = d["hash"]
    return out


class Journal:
    LOCK_TIMEOUT = 30.0

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
            fsync_dir(self.path.parent)
        self._lock = FileLock(self.path.parent / ".journal.lock")
        self._depth = 0

    @contextmanager
    def locked(self, timeout: float | None = None):
        """Hold the journal lock (re-entrant within this object). Every append happens under it."""
        if self._depth == 0:
            if not self._lock.acquire(timeout=self.LOCK_TIMEOUT if timeout is None else timeout):
                raise JournalError("the journal lock is busy")
            try:
                self._recover_torn_tail()
            except BaseException:
                self._lock.release()
                raise
        self._depth += 1
        try:
            yield self
        finally:
            self._depth -= 1
            if self._depth == 0:
                self._lock.release()

    def records(self) -> list[dict]:
        """The verified complete records; a torn final line (no newline) is ignored here and quarantined by the
        next writer."""
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raw = raw[: raw.rfind(b"\n") + 1]
        return parse(raw, self.path)

    def torn(self) -> bool:
        raw = self.path.read_bytes()
        return bool(raw) and not raw.endswith(b"\n")

    def head(self) -> dict:
        recs = self.records()
        return {"records": len(recs), "head": recs[-1]["hash"] if recs else GENESIS}

    def verify(self, anchor: dict | None = None) -> dict:
        recs = self.records()
        head = {"records": len(recs), "head": recs[-1]["hash"] if recs else GENESIS}
        if anchor is not None:
            n = int(anchor["records"])
            if n > len(recs):
                raise JournalError(f"anchor names {n} records, the journal has {len(recs)} (suffix deleted)")
            if (recs[n - 1]["hash"] if n else GENESIS) != anchor["head"]:
                raise JournalError(f"record {n} does not match the anchor (history replaced)")
        return head

    def append(self, typ: str, payload: dict) -> dict:
        if self._depth == 0:
            raise JournalError("append outside the journal lock")
        recs = self.records()                       # re-read under the lock: never a stale seq or prev_hash
        seq = len(recs) + 1
        prev = recs[-1]["hash"] if recs else GENESIS
        payload = json.loads(canonical(payload))
        rec = {"seq": seq, "type": typ, "payload": payload, "prev_hash": prev,
               "hash": _record_hash(seq, typ, payload, prev), "ts_utc": utc_now()}
        data = json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"
        with open(self.path, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        return rec

    def _recover_torn_tail(self) -> None:
        raw = self.path.read_bytes()
        if not raw or raw.endswith(b"\n"):
            return
        cut = raw.rfind(b"\n") + 1
        torn = raw[cut:]
        n = len(list(self.path.parent.glob(self.path.name + ".torn-*")))
        q = self.path.with_name(f"{self.path.name}.torn-{n}")
        atomic_write(q, torn)
        with open(self.path, "r+b") as f:
            f.truncate(cut)
            f.flush()
            os.fsync(f.fileno())
        self._depth += 1
        try:
            self.append("journal_torn_tail", {"bytes": len(torn), "sha256": sha256_bytes(torn), "quarantine": q.name})
        finally:
            self._depth -= 1
