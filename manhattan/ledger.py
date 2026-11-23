"""The Manhattan ledger: a hash-chained, append-only record of every evaluation (ARCHITECTURE.md section 4).

Each record is one JSON line: ``seq`` (from 1), ``ts_utc``, ``type``, ``writer``, ``protocol`` (SHA-256 of the
protocol version in force), ``payload``, ``prev_hash`` (64 zeros for the first) and ``hash`` (SHA-256 of the
canonical form of all the other fields). A record is never edited; a mistake is fixed by a ``correction`` record.
Editing any line breaks every later hash. Replacing the whole file would not, so the head hash is anchored
outside the file (the public index, the batch tag, an external timestamp): ``verify`` takes the anchor.

Two ledgers of one design: the **full ledger** (private; holds outcomes) and the **public index**
(``data/manhattan/ledger/index.jsonl``; no outcome field is ever written to it).

Rerun detection (section 4.2). The key of an evaluation is ``(spec_hash, data_hash, window id)``:
unseen: ``evaluation`` (one look); seen with the same ``result_hash``: ``rerun`` (the same look); seen with a
different one: ``nondeterminism`` (both kept, the family suspended from tier changes); the same spec on a window
with a different ``data_hash``: a new ``evaluation`` flagged ``data_changed``, the first designated result
staying the result of record.

Integrity of the file itself (ledger integrity II, S17 C4 and C6). On every read, a record's keys are exactly
``FIELDS`` and ``hash``, its line is ``record_line(record)`` byte for byte (the file is exactly those lines, each
ending in ``"\\n"`` and nothing else), and no JSON object in it repeats a key:
the hash covers only ``FIELDS``, so anything else on a line (an extra key, a repeated key, another spelling) would be
data no hash protects. Appends are serialized across processes by an exclusive ``flock`` on the ledger file itself;
under it the file's last record must be this handle's head (a stale handle is refused and nothing is written), and the
line is written and made durable (``fsync``; also ``F_FULLFSYNC`` on macOS; the directory too when the file is
created) before the lock is released. A write that fails part-way leaves the handle unusable; ``recover_torn_tail``
is the recovery path.

Lock identity (S17 C6, alias review). The lock is taken on the open ledger file, never on a name derived from the
path a caller passed: ``flock`` belongs to the file (its inode), so every alias of one ledger (a symlink, a hard link,
a relative or ``..`` path, a bind mount) shares one lock. Each operation opens the path once, refuses anything that
is not a regular file, locks that descriptor, and only then checks that the path still names that same file (device
and inode, still linked); every byte it reads or writes goes through that one descriptor. A path replaced, renamed or
removed around the lock is refused, and an append whose file was replaced while it wrote raises (the handle becomes
unusable) instead of reporting a record that the ledger path no longer holds. Threat model: local POSIX file systems
on which ``flock`` is coherent across every process using the ledger (Linux ext4, xfs, btrfs, tmpfs; macOS APFS).
Network and user-space file systems (NFS, SMB, FUSE) are not supported: their locking is not assumed. The adversary
is concurrent or misconfigured processes (aliases, stale handles, a replaced file), not a local user with write
access to the file, who can rewrite it outright; that is what an anchor kept outside the file is for (``verify``).
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import spec as S

GENESIS = "0" * 64
TYPES = ("batch_freeze", "critic_review", "evaluation_started", "evaluation", "rerun", "nondeterminism",
         "screening_decision", "eprocess_update", "tier_change", "dormancy", "window_retired", "correction",
         "run_summary", "attempt_failed", "attempt_aborted")
FIELDS = ("seq", "ts_utc", "type", "writer", "protocol", "payload", "prev_hash")
RECORD_KEYS = frozenset((*FIELDS, "hash"))          # every key a stored record has, and the only ones
ROLES = ("exploration", "reserve", "forward")
# Phase 4B: the identity every new registered attempt must carry, and the reason classes a terminal may give
IDENTITY_FIELDS = ("executable", "variant", "hypothesis", "family", "batch", "role", "channel", "designated",
                   "spec_hash", "data_hash", "window", "code_version")
ATTEMPT_SCHEMA = 2
TERMINAL_REASONS = ("execution_error", "data_unavailable", "interrupted", "cancelled", "validation_error")
COMPLETIONS = ("evaluation", "rerun", "nondeterminism")
# Written only through their own methods (start_evaluation, record_evaluation, end_attempt), never by append (S7 M5)
LIFECYCLE_TYPES = ("evaluation_started", *COMPLETIONS, "attempt_failed", "attempt_aborted")
PROTECTED_ROLES = ("reserve", "forward")
# keys that carry an outcome: never written to the public index
OUTCOME_KEYS = frozenset({"summary", "returns", "return_series", "result", "results", "p_value", "p", "e_value",
                          "wealth", "sharpe", "mean", "pnl", "t_stat", "tstat", "posterior", "pi", "outcome",
                          "n_obs"})


class LedgerError(RuntimeError):
    pass


# Characters that ``str.splitlines()`` (which ``verify_snapshot`` uses) treats as line boundaries but
# ``json.dumps(ensure_ascii=False)`` writes unescaped. JSON escapes every other one, since all are below U+0020.
LINE_BREAKS = {"\x85": "\\u0085", "\u2028": "\\u2028", "\u2029": "\\u2029"}


def record_line(rec: dict) -> str:
    """The line a record is written as: its JSON with sorted keys and no spaces, and with U+0085, U+2028 and U+2029
    written as JSON escapes.

    These characters can only occur inside JSON strings, where ``\\uXXXX`` is the same character, so the line parses
    to the same record, and its hash (computed over the parsed record, ``record_hash``) is unchanged. Written raw they
    are line boundaries to ``verify_snapshot``, which then cannot read the ledger (U+2028/U+2029/U+0085 ledger
    defect). Lines without them are unchanged, byte for byte."""
    line = json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    for ch, escaped in LINE_BREAKS.items():
        if ch in line:
            line = line.replace(ch, escaped)
    return line


class _DuplicateKey(ValueError):
    pass


def _duplicates(pairs: list) -> list:
    seen: set = set()
    return [k for k, _ in pairs if k in seen or seen.add(k)]


def _unique_pairs(pairs: list) -> dict:
    """``object_pairs_hook`` refusing a JSON object that repeats a key (``json`` alone keeps the last silently)."""
    d = dict(pairs)
    if len(d) != len(pairs):
        raise _DuplicateKey(_duplicates(pairs)[0])
    return d


def _line_problem(rec: dict, line: str) -> str | None:
    """What makes a parsed record's line other than ``record_line(rec)``: keys outside the hashed record, or another
    spelling of it (whitespace, key order, escapes). None for a canonical line."""
    extra = set(rec) - RECORD_KEYS
    if extra:
        return "fields outside the hashed record: " + ", ".join(sorted(map(str, extra)))
    if line != record_line(rec):
        return "the line is not the canonical form of its record (record_line)"
    return None


def record_hash(rec: dict) -> str:
    return hashlib.sha256(S.canonical_bytes({k: rec[k] for k in FIELDS})).hexdigest()


def merkle_root(hashes: list[str]) -> str:
    """Merkle root of hex SHA-256 digests in the order given (the last one is paired with itself when a level is
    odd). The root of no hashes is 64 zeros."""
    if not hashes:
        return GENESIS
    level = [bytes.fromhex(h) for h in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def evidential_weight(channel: str, role: str, designated: bool = False, reconstructed: bool = False) -> int:
    """ARCHITECTURE section 6.3: 1 only for a blind spec's designated reserve evaluation and for forward data
    dated after the spec's freeze that were recorded as they happened."""
    if role == "exploration":
        return 0
    if role == "reserve":
        return 1 if (channel == "blind" and designated and not reconstructed) else 0
    if role == "forward":
        return 0 if reconstructed else 1
    raise LedgerError(f"unknown role {role}")


def forward_observation_weight(*, eligible: bool, registration_weight: int, reconstructed: bool,
                               channel: str = "blind") -> int:
    """The weight of one recorded forward observation: the runner's existing rule, in one place so the runner and
    the reconciler apply the same function. An ineligible or weight-0 registration gives 0; otherwise
    ``evidential_weight`` for the forward role (0 when reconstructed)."""
    if not eligible or registration_weight == 0:
        return 0
    return evidential_weight(channel, "forward", False, reconstructed)


def _framing_problems(text: str) -> list[str]:
    """Where a decoded ledger file is not exactly record lines each ending in ``"\\n"`` (lines counted by ``"\\n"``):
    a blank or whitespace-only line, another line break (``"\\r"``, ``"\\x0c"``, ``"\\x1c"``, ``"\\x85"``, ...) in
    or at the end of a line, a last line without its newline. ``str.splitlines`` alone would accept all of these.
    The first problem is reported, with the number of further ones."""
    found = []
    segments = text.split("\n")
    last = segments.pop()
    for n, seg in enumerate(segments, 1):
        if not seg.strip():
            found.append(f"line {n}: a blank line (a ledger file holds record lines only)")
        elif seg.splitlines() != [seg]:
            found.append(f"line {n}: another line break in the line (a record line ends in \\n alone)")
    if last:
        found.append(f"line {len(segments) + 1}: no final newline (a torn write: recover_torn_tail)")
    if len(found) > 1:
        return [f"{found[0]}; and {len(found) - 1} more such line(s)"]
    return found


def read(path: Path) -> list[dict]:
    """The records of a ledger file, not verified as a chain, but held to the file format: every line its record's
    canonical form, ending in ``"\\n"`` alone. A repeated JSON key, a key outside the hashed record, another
    spelling or another framing raises ``LedgerError``. Read under the shared lock on the ledger file."""
    with _locked_ledger(Path(path), exclusive=False) as (fd, _):
        if fd is None:
            return []
        text = _read_all(fd).decode("utf-8")
    framing = _framing_problems(text)
    if framing:
        raise LedgerError(framing[0])
    out = []
    for n, line in enumerate(text.split("\n")[:-1], 1):
        try:
            rec = json.loads(line, object_pairs_hook=_unique_pairs)
        except _DuplicateKey as e:
            raise LedgerError(f"line {n}: duplicate key {e.args[0]!r}") from None
        bad = _line_problem(rec, line) if isinstance(rec, dict) else None
        if bad:
            raise LedgerError(f"line {n}: {bad}")
        out.append(rec)
    return out


def verify(path: Path, anchor: str | None = None) -> list[str]:
    """Problems found in a ledger file; preserve the legacy optional-anchor API. The file is read under the shared
    lock on the ledger file, so a line being appended is never seen half-written."""
    with _locked_ledger(Path(path), exclusive=False) as (fd, _):
        snapshot = b"" if fd is None else _read_all(fd)
    return verify_snapshot(snapshot, anchor=anchor)[1]


def verify_snapshot(snapshot: bytes, anchor: str | None = None) -> tuple[list[dict], list[str]]:
    """Parse and verify one immutable byte snapshot; return its records and problems.

    Callers must process these returned records, rather than reopen the file.
    ``verify`` retains its historic optional-anchor API.

    Records are read from ``str.splitlines()`` lines and each problem is reported as before; when the chain is read
    to its end, the bytes must also be exactly ``record_line(record) + "\\n"`` for each record in turn, so any other
    framing (CRLF, blank lines, other line breaks, no final newline) is reported too (``_framing_problems``).
    """
    errs: list[str] = []
    prev = GENESIS
    recs = []
    try:
        text = snapshot.decode("utf-8")
    except UnicodeDecodeError:
        return [], ["ledger is not UTF-8"]
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        dups: list = []
        try:
            rec = json.loads(line, object_pairs_hook=lambda pairs: _noting_duplicates(pairs, dups))
        except json.JSONDecodeError:
            return recs, errs + [f"line {n}: not JSON"]
        if not isinstance(rec, dict):
            return recs, errs + [f"line {n}: record is not an object"]
        recs.append(rec)
        if rec.get("seq") != len(recs):
            return recs, errs + [f"line {n}: seq is {rec.get('seq')}, expected {len(recs)} (a record was removed, added or moved)"]
        if rec.get("prev_hash") != prev:
            return recs, errs + [f"record {rec['seq']}: prev_hash does not match the record before it"]
        if any(k not in rec for k in FIELDS) or rec.get("hash") != record_hash(rec):
            return recs, errs + [f"record {rec['seq']}: hash does not match its content (the record was edited)"]
        if rec["type"] not in TYPES:
            errs.append(f"record {rec['seq']}: unknown type {rec['type']}")
        # The hash covers FIELDS only: anything else the line says is reported, and the chain is read on (S17 C4).
        if dups:
            errs.append(f"record {rec['seq']}: duplicate key {', '.join(sorted(set(map(str, dups))))} in its line "
                        "(a reader may take either value)")
        else:
            bad = _line_problem(rec, line)
            if bad:
                errs.append(f"record {rec['seq']}: {bad}")
        prev = rec["hash"]
    errs += _framing_problems(text)
    if anchor is not None and prev != anchor:
        errs.append(f"head hash is {prev}, but the anchor says {anchor} (records are missing or the file was replaced)")
    return recs, errs


def _noting_duplicates(pairs: list, dups: list) -> dict:
    """``object_pairs_hook`` for ``verify_snapshot``: the object ``json`` builds (the last value of a repeated key),
    with each repeated key noted in ``dups``, so that the line is reported rather than read silently."""
    d = dict(pairs)
    if len(d) != len(pairs):
        dups.extend(_duplicates(pairs))
    return d


class IrregularSnapshot(Exception):
    """The fast path met something ``verify_snapshot`` might treat differently or report: use ``verify_snapshot``."""


def iter_verified(lines):
    """Yield ``(record, line)`` for each record of an iterable of byte lines (a file opened ``"rb"``, or
    ``io.BytesIO(snapshot)``), checking the chain exactly as ``verify_snapshot`` does, one line at a time, so that
    nothing but the current record is held in memory.

    It covers the regular case only: every line valid UTF-8, exactly one record per ``\\n``-terminated line, every
    record valid. At the first thing ``verify_snapshot`` would report or might split differently (invalid UTF-8,
    another line break in a line, a blank line, no final newline, JSON that does not parse, a sequence, chain,
    hash or type problem, an exception),
    it raises ``IrregularSnapshot`` and the caller answers from ``verify_snapshot`` on the same bytes. The fast path
    therefore never accepts what ``verify_snapshot`` refuses, and never reports a different problem. That includes
    the line checks: a repeated key, a key outside the hashed record, a line other than ``record_line(record)``."""
    prev, n = GENESIS, 0
    for raw in lines:
        if not raw.endswith(b"\n"):
            raise IrregularSnapshot                       # no final newline: a framing problem
        try:
            line = raw[:-1].decode("utf-8")
        except UnicodeDecodeError:
            raise IrregularSnapshot from None
        if line.splitlines() != [line] or not line.strip():
            raise IrregularSnapshot                       # another line break, or a blank line
        pieces = [line]
        try:
            rec = json.loads(pieces[0], object_pairs_hook=_unique_pairs)
            n += 1
            ok = (isinstance(rec, dict) and rec.get("seq") == n and rec.get("prev_hash") == prev
                  and all(k in rec for k in FIELDS) and rec.get("hash") == record_hash(rec) and rec["type"] in TYPES
                  and _line_problem(rec, pieces[0]) is None)
        except Exception:                                 # noqa: BLE001 - verify_snapshot decides what it was
            raise IrregularSnapshot from None
        if not ok:
            raise IrregularSnapshot
        prev = rec["hash"]
        yield rec, pieces[0]


def require_code_identity(version) -> None:
    """A known Git commit and an engine or Git-tree content digest.

    Required for retries (4A-1a) and for every new registered attempt (``attempt_schema`` 2). Non-retry legacy
    evaluation APIs continue to accept their historical metadata. This validates identity syntax; authenticity
    of the running code is checked where the engine runs (``engine.evaluate``), not here.
    """
    def git_hash(value):
        return (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is not None
                and set(value) != {"0"})

    if not isinstance(version, dict) or not git_hash(version.get("commit")):
        raise LedgerError("retry requires a known code identity: Git commit and content digest")
    if not any(k in version for k in ("tree", "engine_sha256")):
        raise LedgerError("retry requires a known code identity: content digest missing")
    if ("tree" in version and not git_hash(version["tree"])) or (
            "engine_sha256" in version and (not isinstance(version["engine_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", version["engine_sha256"]) is None
                or set(version["engine_sha256"]) == {"0"})):
        raise LedgerError("retry requires a known code identity: malformed content digest")


require_retry_code_identity = require_code_identity          # the 4A-1a name, kept for callers


def _sha(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_attempt_identity(p: dict) -> None:
    """Structural validation of a schema-2 attempt identity (Phase 4B). Never a statistical decision."""
    if not isinstance(p, dict):
        raise LedgerError("attempt identity must be an object")
    missing = [k for k in IDENTITY_FIELDS if k not in p]
    if missing:
        raise LedgerError("attempt identity is missing " + ", ".join(missing))
    w = p["window"]
    if (any(not isinstance(p[k], str) or not p[k].strip()
            for k in ("executable", "variant", "hypothesis", "family", "batch"))
            or p["role"] not in ROLES or p["channel"] not in S.CHANNELS or type(p["designated"]) is not bool
            or not _sha(p["spec_hash"]) or not _sha(p["data_hash"])
            or not isinstance(w, dict) or set(w) != {"id", "start", "end", "frequency"}
            or any(not isinstance(w[k], str) or not w[k].strip() for k in w)):
        raise LedgerError("malformed attempt identity")
    require_code_identity(p["code_version"])


def same_identity(start: dict, completion: dict) -> bool:
    """Whether a completion keeps every identity field its start registered (no role or window escalation).

    A ``data_changed`` evaluation is written with ``designated: false`` by the existing rule (the first designated
    result stays the result of record); that override is the only difference allowed."""
    for k in IDENTITY_FIELDS:
        if k not in start:
            continue
        if k == "designated" and completion.get("data_changed") is True and completion.get(k) is False:
            continue
        if completion.get(k) != start[k]:
            return False
    return True


def _reserve_domain(p: dict) -> str | None:
    """The evaluation domain of a schema-2 reserve start (designated or not: every reserve attempt consumes its
    (batch, domain) designation, S7 N1), else None."""
    if p.get("attempt_schema") != ATTEMPT_SCHEMA or p.get("role") != "reserve":
        return None
    auth = p.get("authorization")
    windows = auth.get("windows") if isinstance(auth, dict) else None
    for w in windows if isinstance(windows, list) else []:
        if isinstance(w, dict) and w.get("purpose") == "evaluation" and isinstance(w.get("domain"), str):
            return w["domain"]
    return None


def _safe_key(p) -> tuple | None:
    try:
        k = (p["spec_hash"], p["data_hash"], p["window"]["id"])
        hash(k)
        return k
    except (KeyError, TypeError):
        return None


_BAD = object()                                   # an indexed field the record does not have (or not as a value)


def _field(p, *path, hashable: bool = False):
    """``p[a][b]...``, or ``_BAD`` where that lookup would raise (or, with ``hashable``, where the value cannot be
    a set member)."""
    try:
        for k in path:
            p = p[k]
        if hashable:
            hash(p)
        return p
    except (KeyError, TypeError, IndexError):
        return _BAD


def _i(v):
    """One shared object for equal identifier strings (hashes, window IDs) across the indexes: equality, and so
    every rule, is unchanged; only the copies are saved."""
    return sys.intern(v) if type(v) is str else v


def _hashable(v) -> bool:
    try:
        hash(v)
        return True
    except TypeError:
        return False


# ---- the writer lock and durable appends (S17 C6)
_FULLFSYNC = getattr(fcntl, "F_FULLFSYNC", None) if sys.platform == "darwin" else None


def _identity(st: os.stat_result) -> tuple[int, int]:
    return st.st_dev, st.st_ino


def _lock_fd(fd: int, exclusive: bool) -> None:
    """``flock`` on the open ledger file (blocking). A separate function only so that tests can interleave."""
    fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)


def _same_file(path: Path, fd: int) -> bool:
    """Whether ``path`` (following symlinks) still names the open, still-linked file ``fd``."""
    try:
        now = os.stat(path)
    except OSError:
        return False
    st = os.fstat(fd)
    return st.st_nlink > 0 and _identity(now) == _identity(st)


@contextlib.contextmanager
def _locked_ledger(path: Path, *, exclusive: bool, create: bool = False):
    """Open the ledger file once and lock that descriptor: exclusive for a writer, shared for a reader. Yields
    ``(fd, created)``, or ``(None, False)`` when the file does not exist and ``create`` is false (a reader never
    creates anything). The lock is on the file itself, so every alias of it shares the lock; after locking, the path
    must still name the same file, or ``LedgerError`` (fail closed: a ledger file is never replaced). Anything that is
    not a regular file is refused before it is locked (``O_NONBLOCK``: a FIFO never blocks the open). Every read and
    write of the operation goes through the yielded descriptor, never through the path again."""
    path = Path(path)
    flags = ((os.O_RDWR | os.O_APPEND) if exclusive else os.O_RDONLY) | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    created = False
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        if not create:
            fd = None
        else:
            try:
                fd, created = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o666), True
            except FileExistsError:                       # another writer created it first: use theirs
                try:
                    fd = os.open(path, flags)
                except FileNotFoundError:                 # a dangling symlink, or a path that keeps changing
                    raise LedgerError(f"{path} names no ledger file and one cannot be created there safely (a "
                                      "dangling symlink or a path that is changing): refused") from None
    if fd is None:
        yield None, False
        return
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise LedgerError(f"{path} is not a regular file: a ledger is one")
        _lock_fd(fd, exclusive)
        if not _same_file(path, fd):
            raise LedgerError("the ledger path was replaced, renamed or removed while it was being opened: refused "
                              "(nothing was written); a ledger file is never replaced")
        yield fd, created
    finally:
        os.close(fd)                                      # closing the descriptor releases the lock


def _read_all(fd: int) -> bytes:
    """Every byte of the open file, read from offset 0 (independent of the descriptor's position)."""
    chunks, off = [], 0
    while True:
        b = os.pread(fd, 1 << 20, off)
        if not b:
            return b"".join(chunks)
        chunks.append(b)
        off += len(b)


def _last_hash(fd: int) -> str:
    """The ``hash`` of the last record in the open ledger file (``GENESIS`` when it holds none), read backwards from
    the end. A file that does not end with a newline ends in a partial line: refused, so that a new line is never
    glued onto it (``recover_torn_tail`` is the recovery). The last line is the bytes between the last two
    newlines, exactly as the readers frame it; a blank one is refused (such a file does not verify)."""
    size = os.fstat(fd).st_size
    if size == 0:
        return GENESIS
    if os.pread(fd, 1, size - 1) != b"\n":
        raise LedgerError("the ledger file ends in a partial line: run recover_torn_tail before appending")
    pos, buf = size - 1, b""                              # the final newline excluded
    while True:
        start = max(0, pos - 65536)
        buf, pos = os.pread(fd, pos - start, start) + buf, start
        cut = buf.rfind(b"\n")
        if cut != -1 or pos == 0:
            break
    last = buf[cut + 1:]
    try:
        rec = json.loads(last.decode("utf-8"))
        head = rec["hash"]
    except (UnicodeDecodeError, ValueError, TypeError, KeyError):
        raise LedgerError("the ledger file's last line is not a record: the file does not verify") from None
    if not isinstance(head, str) or not isinstance(rec, dict) or record_line(rec).encode("utf-8") != last:
        raise LedgerError("the ledger file's last line is not a record: the file does not verify")
    return head


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Ledger:
    """One ledger file. ``append`` is the only way a record is written.

    Lifecycle queries are served from indexes kept in step with ``append`` (Phase 4B), so registering and completing
    attempts does not rescan the ledger. Their answers are those of the 4A-1a scans they replace.

    Scaling (Manhattan phase 3, docs/manhattan/LEDGER_SCALING.md). Records are held as their verified JSON lines,
    not as parsed objects, and are decoded when read; the indexes hold only what the rules look up (keys, sequence
    numbers, result hashes, the attempt links). Every query that used to scan the whole ledger is answered from an
    index (the ``data_changed`` rule's earlier evaluations of a spec on a window, the result of record, suspended
    families, records of a type). The rules, the records written and every answer are those of the scans; a record
    an index cannot place (a malformed record that only a forged write can produce) makes the query that would have
    met it refuse, as the scan raised there. ``records()`` returns new objects on each call."""

    public = False

    def __init__(self, path: Path, writer: str, protocol: str):
        self.path, self.writer, self.protocol = Path(path), writer, protocol
        self._unusable: str | None = None             # why appends are refused after a failed write (S17 C1-7)
        with _locked_ledger(self.path, exclusive=False) as (fd, _):   # never a line a writer is still writing
            self._load(fd)

    def _load(self, fd: int | None) -> None:
        """Index the records of the open, share-locked ledger file ``fd`` (``None``: there is no file yet)."""
        self._reset()
        if fd is None:
            return
        try:
            with open(fd, "rb", closefd=False) as f:
                for rec, line in iter_verified(f):
                    self._index(rec, line)
        except IrregularSnapshot:
            # the exact 4A-1a answer: verify, then index every record of the verified snapshot
            self._reset()
            recs, errs = verify_snapshot(_read_all(fd))
            if errs:
                raise LedgerError("the ledger does not verify: " + "; ".join(errs)) from None
            for rec in recs:
                self._index(rec)

    def _reset(self) -> None:
        self._lines: list[bytes] = []                 # record seq n is self._lines[n - 1], as written in the file
        self._head = GENESIS
        self._by_type: dict[str, list[int]] = {}       # type -> positions, in order
        self._starts: dict[str, tuple] = {}            # attempt ID -> (position, seq, key)
        self._starts_by_key: dict[tuple, list] = {}    # key -> attempt IDs, in order
        self._terminated: set[str] = set()             # attempt IDs with a linked completion or terminal
        self._superseded: set[str] = set()
        self._evals_by_key: dict[tuple, list] = {}     # key -> (seq, result_hash), in order
        self._evals: list[int] = []                    # positions of completions
        self._legacy_last: dict[tuple, int] = {}       # key -> seq of the latest unlinked completion
        self._designated: dict[tuple, list] = {}       # (batch, domain) -> every schema-2 reserve start
        # the data_changed rule and the result of record: (spec_hash, window id) -> (seq, position, designated) of
        # every record of type "evaluation", in order; and what the scan would have raised on
        self._evaluated: dict[tuple, list] = {}
        self._eval_unplaceable = False                 # an "evaluation" (object payload) without a spec_hash
        self._eval_nonobject = False                   # an "evaluation" whose payload is not an object
        self._eval_bad_window: set = set()             # spec hashes of an "evaluation" without a window id
        self._families: set = set()                    # families of nondeterminism records
        self._family_unplaceable = False

    def _index(self, rec: dict, line: str | bytes | None = None) -> None:
        if line is None:
            line = record_line(rec)
        pos = len(self._lines)
        self._lines.append(line.encode("utf-8") if isinstance(line, str) else bytes(line))
        self._head = rec["hash"]
        t, p = rec["type"], rec["payload"]
        self._by_type.setdefault(t, []).append(pos)
        if t == "evaluation" and not isinstance(p, dict):
            self._eval_nonobject = True
        if t == "nondeterminism":
            fam = _field(p, "family", hashable=True)
            if fam is _BAD:
                self._family_unplaceable = True
            else:
                self._families.add(fam)
        if not isinstance(p, dict):
            return                                    # malformed: the reconciler reports it
        k = _safe_key(p)
        if k is not None:
            k = tuple(map(_i, k))
        if t == "evaluation_started":
            aid = _i(rec["hash"])
            self._starts[aid] = (pos, rec["seq"], k)
            if k is not None:
                self._starts_by_key.setdefault(k, []).append(aid)
            if isinstance(p.get("supersedes"), str):
                self._superseded.add(_i(p["supersedes"]))
            dom = _reserve_domain(p)
            if dom is not None:
                self._designated.setdefault((p.get("batch"), dom), []).append(rec["hash"])
        elif t in COMPLETIONS:
            self._evals.append(pos)
            if k is not None:
                self._evals_by_key.setdefault(k, []).append((rec["seq"], _field(p, "result_hash")))
            if isinstance(p.get("attempt_id"), str):
                self._terminated.add(_i(p["attempt_id"]))
            elif "attempt_id" not in p and k is not None:
                self._legacy_last[k] = rec["seq"]
            if t == "evaluation":
                sh = _field(p, "spec_hash")
                wid = _field(p, "window", "id")
                if sh is _BAD:
                    self._eval_unplaceable = True
                elif not _hashable(sh):
                    pass                              # equal to no spec hash a caller passes: never matched
                elif wid is _BAD:
                    self._eval_bad_window.add(sh)
                elif _hashable(wid):
                    self._evaluated.setdefault((_i(sh), _i(wid)), []).append(
                        (rec["seq"], pos, _field(p, "designated")))
        elif t in ("attempt_failed", "attempt_aborted") and isinstance(p.get("attempt_id"), str):
            self._terminated.add(_i(p["attempt_id"]))

    def _record(self, pos: int) -> dict:
        return json.loads(self._lines[pos])

    def _start(self, attempt_id) -> dict | None:
        meta = self._starts.get(attempt_id) if isinstance(attempt_id, str) else None
        return None if meta is None else self._record(meta[0])

    def _earlier(self, spec_hash, window_id, *, objects_only: bool = True) -> list:
        """The ``evaluation`` records of a spec on a window, as (seq, position, designated); refuses where the scan
        of every evaluation would have raised (a malformed record only a forged write produces). The completion
        rule scanned only records with an object payload; ``result_of_record`` scanned every one."""
        if (self._eval_unplaceable or (not objects_only and self._eval_nonobject)
                or (_hashable(spec_hash) and spec_hash in self._eval_bad_window)):
            raise LedgerError("the ledger holds an evaluation record without a spec and window: the reconciler "
                              "reports it; no rule is applied past it")
        return self._evaluated.get((spec_hash, window_id), []) if _hashable((spec_hash, window_id)) else []

    # ---- reading
    def records(self, type_: str | None = None) -> list[dict]:
        return list(self.iter_records(type_))

    def iter_records(self, type_: str | None = None):
        """``records(type_)`` one record at a time (for callers that need not hold every record at once)."""
        if type_ is None:
            return (json.loads(x) for x in self._lines)
        return (self._record(i) for i in (self._by_type.get(type_, []) if _hashable(type_) else []))

    @property
    def head(self) -> str:
        return self._head

    def __len__(self) -> int:
        return len(self._lines)

    # ---- writing
    def append(self, type_: str, payload: dict, ts_utc: str | None = None) -> dict:
        """Append one record of a non-lifecycle type. Starts, completions and terminals are written only by
        ``start_evaluation``, ``record_evaluation`` and ``end_attempt``, which apply their rules (Phase 4B, S7 M5)."""
        if type_ in LIFECYCLE_TYPES:
            raise LedgerError(f"{type_} records are written by the lifecycle methods only")
        return self._append(type_, payload, ts_utc)

    def _append(self, type_: str, payload: dict, ts_utc: str | None = None) -> dict:
        """Append one record. The line is flushed and ``fsync``ed before this returns, so a registration that
        returned survives a crash of the process (Phase 4B).

        Under an exclusive ``flock`` on the ledger file itself (S17 C6; every alias of the file shares it): the
        file's last record must be this handle's head, else the handle is stale (another handle or process appended)
        and ``LedgerError`` is raised with nothing written; then the line is written, ``fsync``ed (and
        ``F_FULLFSYNC``ed on macOS), and the directory ``fsync``ed when this append created the file. A handle whose
        ledger file has disappeared is refused before anything is created. If the path stops naming the written file
        before the lock is released (the file was replaced), ``LedgerError`` is raised and the handle is unusable:
        the record is not in the file the path names. If writing or syncing raises, the file may hold a partial line
        or a record this handle has not indexed: the handle refuses every later append (reopen it;
        ``recover_torn_tail`` first if the file ends in a partial line)."""
        if type_ not in TYPES:
            raise LedgerError(f"unknown record type {type_}")
        if self._unusable is not None:
            raise LedgerError(f"this ledger handle is unusable ({self._unusable}): reopen the ledger, after "
                              "recover_torn_tail if the file ends in a partial line")
        rec = {"seq": len(self._lines) + 1,
               "ts_utc": ts_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "type": type_, "writer": self.writer, "protocol": self.protocol,
               "payload": json.loads(S.canonical_bytes(payload)), "prev_hash": self.head}
        rec["hash"] = record_hash(rec)
        line = record_line(rec)
        data = (line + "\n").encode("utf-8")           # what cannot be encoded raises here, before any write
        if self._head != GENESIS and not os.path.lexists(self.path):
            raise LedgerError("stale ledger handle: its ledger file no longer exists; nothing was written")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _locked_ledger(self.path, exclusive=True, create=True) as (fd, created):
            on_file = _last_hash(fd)
            if on_file != self._head:
                raise LedgerError("stale ledger handle: the file's last record is not this handle's head "
                                  "(another handle or process appended); nothing was written: reopen the ledger")
            try:
                _write_all(fd, data)
                os.fsync(fd)
                if _FULLFSYNC is not None:
                    try:
                        fcntl.fcntl(fd, _FULLFSYNC)
                    except OSError:
                        pass                              # unsupported here (ENOTSUP, some file systems); fsync ran,
                                                          # and the record is written: report the append, as SQLite does
                if created:
                    _fsync_dir(Path(os.path.realpath(self.path)).parent)
            except BaseException as e:
                self._unusable = f"an append failed part-way: {type(e).__name__}"
                raise
            if not _same_file(self.path, fd):
                self._unusable = "the ledger file was replaced while a record was being appended"
                raise LedgerError("the ledger path was replaced, renamed or removed during the append: the record "
                                  "was written to a file the path no longer names; this handle is unusable")
        self._index(rec, line)
        return rec

    def correction(self, target_seq: int, fields: dict, reason: str) -> dict:
        """Record that fields of an earlier record were wrong. ``fields`` maps each to {"old": ..., "new": ...};
        the earlier record stays as it is."""
        if not 1 <= target_seq <= len(self._lines):
            raise LedgerError("a correction must name an existing record")
        if not reason or not reason.strip():
            raise LedgerError("a correction needs a reason")
        if not fields or any(set(v) != {"old", "new"} for v in fields.values()):
            raise LedgerError("a correction lists each field with its old and new value")
        target = self._record(target_seq - 1)
        return self.append("correction", {"target_seq": target_seq, "target_hash": target["hash"],
                                          "fields": fields, "reason": reason})

    # ---- evaluations
    @staticmethod
    def key(payload: dict) -> tuple[str, str, str]:
        return payload["spec_hash"], payload["data_hash"], payload["window"]["id"]

    def _evaluations(self) -> list[dict]:
        return [self._record(i) for i in self._evals]

    def start_evaluation(self, payload: dict, *, supersedes: str | None = None) -> dict:
        """Register an execution; the returned start record's hash is its attempt ID.

        Retries name an unfinished start and preserve it in the denominator. A payload with ``attempt_schema: 2``
        (written by ``manhattan.access``) must carry the full identity of ``IDENTITY_FIELDS`` with a known code
        identity, and keeps its ``kind`` and ``authorization``. This API alone does not authorize a PIT read:
        ``manhattan.access.register_evaluation`` validates the declared windows first.
        """
        fields = ("executable", "family", "batch", "spec_hash", "data_hash", "window")
        if payload.get("attempt_schema") == ATTEMPT_SCHEMA:
            validate_attempt_identity(payload)
            if not isinstance(payload.get("kind"), str) or not isinstance(payload.get("authorization"), dict):
                raise LedgerError("a registered attempt declares its kind and authorization")
            p = {k: payload[k] for k in (*IDENTITY_FIELDS, "attempt_schema", "kind", "authorization")}
        elif "attempt_schema" in payload:
            raise LedgerError("unknown attempt schema")
        else:
            p = {k: payload[k] for k in fields}
            p.update({k: payload[k] for k in ("variant", "hypothesis", "role", "channel", "designated",
                                              "code_version") if k in payload})
        if supersedes is not None:
            old = self.active_attempt(supersedes)
            require_code_identity(p.get("code_version"))
            require_code_identity(old["payload"].get("code_version"))
            if old["payload"] != p:
                # Only the retry link itself may differ across repeated interruptions.
                prior = {k: v for k, v in old["payload"].items() if k != "supersedes"}
                if prior != p:
                    raise LedgerError("retry identity differs from interrupted attempt")
            p["supersedes"] = supersedes
        return self._append("evaluation_started", p)

    def active_attempt(self, attempt_id: str) -> dict:
        meta = self._starts.get(attempt_id) if isinstance(attempt_id, str) else None
        if meta is None or not self._unfinished_id(attempt_id):
            raise LedgerError("attempt is not registered and unfinished")
        if attempt_id in self._superseded:
            raise LedgerError("attempt has been superseded")
        return self._record(meta[0])

    def _unfinished_id(self, attempt_id: str) -> bool:
        """The 4A-1a ``unfinished`` predicate for one start."""
        if attempt_id in self._terminated:
            return False
        if attempt_id in self._superseded:
            return True
        _, seq, k = self._starts[attempt_id]
        return k is None or self._legacy_last.get(k, 0) < seq

    def _unfinished_one(self, r: dict) -> bool:
        """The 4A-1a ``unfinished`` predicate for one start record."""
        if r["hash"] in self._terminated:
            return False
        if r["hash"] in self._superseded:
            return True
        k = _safe_key(r["payload"])
        return k is None or self._legacy_last.get(k, 0) < r["seq"]

    def end_attempt(self, attempt_id: str, *, status: str, reason: str, data_read: bool | None = None) -> dict:
        """Safe classified failure/abortion only; never exception text or outcomes.

        ``data_read`` (Phase 4B) says whether any value was read through the attempt's windows; registered
        (schema-2) attempts must state it, legacy attempts may not."""
        if status not in ("failed", "aborted"):
            raise LedgerError("terminal status must be failed or aborted")
        if reason not in TERMINAL_REASONS:
            raise LedgerError("unknown attempt reason classification")
        start = self.active_attempt(attempt_id)
        payload = {"attempt_id": attempt_id, "reason": reason}
        if start["payload"].get("attempt_schema") == ATTEMPT_SCHEMA:
            if type(data_read) is not bool:
                raise LedgerError("a registered attempt's terminal states whether data were read")
            payload["data_read"] = data_read
        elif data_read is not None:
            raise LedgerError("legacy attempts carry no data_read flag")
        return self._append("attempt_" + status, payload)

    def record_evaluation(self, *, executable: str, variant: str, hypothesis: str, family: str, batch: str,
                          channel: str, role: str, window: dict, designated: bool, spec_hash: str, data_hash: str,
                          code_version: dict, result_hash: str, n_obs: int, summary: dict, seed: int,
                          reconstructed: bool = False, attempt_id: str | None = None, proof=None) -> dict:
        """Record one evaluation, deciding by its key whether it is a new look, a rerun or a nondeterminism.

        A reserve or forward completion (owner decision D-5, S7 M5) needs ``proof``: the one-use
        ``access.CompletionProof`` that only ``engine.evaluate`` obtains, from the active attempt that read its
        window, for this result. An attempt ID alone never writes a protected result."""
        if role not in ROLES or channel not in S.CHANNELS:
            raise LedgerError("role must be exploration, reserve or forward; channel blind or adaptive")
        if role in PROTECTED_ROLES:
            from manhattan import access
            start = self._start(attempt_id)
            if start is None or start["payload"].get("attempt_schema") != ATTEMPT_SCHEMA:
                raise LedgerError("a reserve or forward completion needs a registered (schema 2) attempt")
            access.verify_completion(proof, attempt_id=attempt_id, result_hash=result_hash, ledger=self)
        payload = {"executable": executable, "variant": variant, "hypothesis": hypothesis, "family": family,
                   "batch": batch, "channel": channel, "role": role, "window": window, "designated": bool(designated),
                   "spec_hash": spec_hash, "data_hash": data_hash, "code_version": code_version,
                   "result_hash": result_hash, "n_obs": n_obs, "summary": summary, "seed": seed,
                   "reconstructed": bool(reconstructed),
                   "evidential_weight": evidential_weight(channel, role, designated, reconstructed)}
        if attempt_id is None:
            candidates = [a for a in self._starts_by_key.get(self.key(payload), [])
                          if self._unfinished_id(a) and a not in self._superseded]
            if len(candidates) > 1:
                raise LedgerError("ambiguous attempt: supply attempt_id")
            if candidates:
                if self._start(candidates[0])["payload"].get("attempt_schema") == ATTEMPT_SCHEMA:
                    raise LedgerError("a registered attempt completes only through its own attempt_id")
                attempt_id = candidates[0]
        if attempt_id is not None:
            start = self.active_attempt(attempt_id)
            if not same_identity(start["payload"], payload):
                raise LedgerError("completion identity differs from attempt")
            payload["attempt_id"] = attempt_id
        same_key = self._evals_by_key.get(self.key(payload), [])
        if same_key:
            if any(rh is _BAD for _, rh in same_key):
                raise LedgerError("the ledger holds a completion without a result hash on this key: the reconciler "
                                  "reports it; no rule is applied past it")
            first_seq, first_rh = same_key[0]
            if all(rh == result_hash for _, rh in same_key):
                payload.update(evidential_weight=0, first_seq=first_seq)
                return self._append("rerun", payload)
            payload.update(evidential_weight=0, first_seq=first_seq, first_result_hash=first_rh)
            return self._append("nondeterminism", payload)
        earlier = self._earlier(spec_hash, window["id"])
        if earlier:
            of_record = earlier[0]
            for e in earlier:
                if e[2] is _BAD:
                    raise LedgerError("the ledger holds an evaluation record without a designation")
                if e[2]:
                    of_record = e
                    break
            payload.update(data_changed=True, designated=False, evidential_weight=0, result_of_record_seq=of_record[0])
        return self._append("evaluation", payload)

    def designated_reserve_starts(self, batch: str, domain: str) -> list[str]:
        """Attempt IDs of every registered reserve attempt of (batch, domain) (D-6, S7 N1)."""
        return list(self._designated.get((batch, domain), []))

    def is_superseded(self, attempt_id: str) -> bool:
        return attempt_id in self._superseded

    def looks(self) -> int:
        """Distinct evaluations (reruns are the same look and count once)."""
        return len(self._evals_by_key)

    def unfinished(self) -> list[dict]:
        return [self._record(m[0]) for a, m in self._starts.items() if self._unfinished_id(a)]

    def suspended_families(self) -> set[str]:
        """Families with a nondeterminism on record: no tier change until the cause is found."""
        if self._family_unplaceable:
            raise LedgerError("the ledger holds a nondeterminism record without a family: the reconciler reports it")
        return set(self._families)

    def result_of_record(self, spec_hash: str, window_id: str) -> dict | None:
        """The first designated evaluation of a spec on a window, which later data revisions never replace."""
        for _, pos, designated in self._earlier(spec_hash, window_id, objects_only=False):
            if designated is _BAD:
                raise LedgerError("the ledger holds an evaluation record without a designation")
            if designated:
                return self._record(pos)
        return None

    def run_summary_payload(self) -> dict:
        """What the public index stores about this ledger at the end of a run: no outcome."""
        return {"ledger_records": len(self._lines), "ledger_head": self.head,
                "merkle_root": merkle_root([r["hash"] for r in self.iter_records()])}


def recover_torn_tail(path: Path) -> dict:
    """Crash recovery for a write cut short (Phase 4B). Never removes a complete record.

    Only a final fragment that has no newline and does not parse as a JSON object is moved, byte for byte, to
    ``<name>.torn-<sha256>`` beside the ledger; a complete final record that lost only its newline gets the newline.
    Anything else (a damaged record in the middle, an edited record) is not a torn tail and is refused: ``verify``
    reports it and the ledger stays unopenable. Returns what was done. Runs under the writers' exclusive lock on the
    ledger file (shared by every alias of it), so it never meets an append in progress; the file is repaired in place
    through the locked descriptor, never replaced."""
    path = Path(path)
    with _locked_ledger(path, exclusive=True) as (fd, _):
        if fd is None:
            return {"status": "clean"}
        return _recover_torn_tail(path, fd)


def _recover_torn_tail(path: Path, fd: int) -> dict:
    data = _read_all(fd)
    if not data or data.endswith(b"\n"):
        return {"status": "clean"}
    cut = data.rfind(b"\n") + 1
    head, tail = data[:cut], data[cut:]
    try:
        rec = json.loads(tail.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        rec = None
    if isinstance(rec, dict):
        if verify_snapshot(data + b"\n")[1]:
            raise LedgerError("the final record is complete JSON but does not verify: not a torn write")
        _write_all(fd, b"\n")                             # the descriptor appends (O_APPEND)
        os.fsync(fd)
        return {"status": "newline_restored"}
    head_recs, head_errs = verify_snapshot(head)
    if head_errs:
        raise LedgerError("the ledger before the torn tail does not verify: not a torn write")
    # A torn append is a prefix of exactly one record line, which (sort_keys) begins with '{"hash":"'. A fragment
    # holding a second record start, or naming another sequence number, is damage, not a torn write.
    lead = b'{"hash":"'
    seq = re.search(rb'"seq":(\d+)[,}]', tail)
    if not (tail.startswith(lead) or lead.startswith(tail)) or tail.find(lead, 1) != -1 or \
            (seq is not None and int(seq.group(1)) != len(head_recs) + 1):
        raise LedgerError("the final fragment is not one partial record: not a torn write")
    digest = hashlib.sha256(tail).hexdigest()
    side = path.with_name(f"{path.name}.torn-{digest}")
    side.write_bytes(tail)
    os.ftruncate(fd, cut)
    os.fsync(fd)
    return {"status": "torn_tail_quarantined", "bytes": len(tail), "quarantine": side.name}


def outcome_keys_in(obj, path: str = "") -> list[str]:
    """Paths of keys that carry an outcome, anywhere inside ``obj``."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}" if path else str(k)
            if str(k).lower() in OUTCOME_KEYS:
                found.append(here)
            found += outcome_keys_in(v, here)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            found += outcome_keys_in(v, f"{path}[{i}]")
    return found


class PublicIndex(Ledger):
    """The public index: the same chain, and a refusal of anything that carries an outcome."""

    public = True
    ALLOWED = ("batch_freeze", "run_summary", "screening_decision", "tier_change", "correction", "window_retired")

    def append(self, type_: str, payload: dict, ts_utc: str | None = None) -> dict:
        if type_ not in self.ALLOWED:
            raise LedgerError(f"the public index does not hold {type_} records")
        bad = outcome_keys_in(payload)
        if bad:
            raise LedgerError("the public index never holds an outcome: " + ", ".join(bad))
        return super().append(type_, payload, ts_utc)
