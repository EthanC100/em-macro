"""Ledger integrity II (S17_NEXT_PRS.md PR-1; S17_COMPREHENSIVE_AUDIT.md C4 and C6).

C4: the hash covers only ``FIELDS``, so a line could carry keys no hash protects (an outcome smuggled into the public
index), repeat a key (readers disagree on the record) or spell the record differently. Every reader now requires the
key set ``FIELDS`` plus ``hash``, the canonical line ``record_line(record)`` byte for byte, and no repeated key.

C6: appends took ``seq`` and ``prev_hash`` from the handle's memory with no lock, so two handles forked the chain.
An append now holds an exclusive ``flock`` on the ledger file itself (so every alias of the file shares it), refuses
a stale handle (the file's last record is not its head) with nothing written, and syncs before releasing. A write that
fails part-way leaves the handle unusable. A path replaced, renamed or removed around the lock is refused.

Acceptance ids P1-a .. P1-f are those of S17_NEXT_PRS.md; P1-c is also covered by the existing ledger suites.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from manhattan import ledger as L

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "f" * 64


def _book(path, cls=L.Ledger, writer="w"):
    return cls(path, writer=writer, protocol=PROTOCOL)


def _public(path) -> L.PublicIndex:
    """A public index of three records: a freeze, a screening decision and a run summary."""
    idx = _book(path, L.PublicIndex)
    idx.append("batch_freeze", {"batch": "B-1", "specs": 3})
    idx.append("screening_decision", {"batch": "B-1", "decision": "screened", "note": "café/route"})
    idx.append("run_summary", {"ledger_records": 12, "ledger_head": "a" * 64, "merkle_root": "b" * 64})
    return idx


def _lines(path) -> list[str]:
    return path.read_bytes().decode("utf-8").split("\n")[:-1]


def _write(path, lines) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def _refused_everywhere(path, *, cls=L.Ledger) -> list[str]:
    """Every reader refuses the file: ``verify`` reports, opening raises, the fast path hands over, ``read`` raises."""
    errs = L.verify(path)
    assert errs
    with pytest.raises(L.LedgerError, match="does not verify"):
        _book(path, cls)
    with pytest.raises(L.IrregularSnapshot):
        with path.open("rb") as f:
            list(L.iter_verified(f))
    with pytest.raises(L.LedgerError):
        L.read(path)
    return errs


# ------------------------------------------------------------------------------------------------ P1-a (C4 repro)

def test_p1a_outcome_keys_and_a_duplicate_key_in_the_public_index_are_refused(tmp_path):
    """The S17 reproduction: ``p_value`` and ``summary`` added at the top level of record 2 of a public index (its
    hash still valid: the hash covers FIELDS only), and a duplicate ``"payload"`` put first in line 3 (``json`` keeps
    the last, so the hash is valid and a raw reader sees 999). On main ``verify`` returned [] for this file."""
    path = tmp_path / "index.jsonl"
    _public(path)
    lines = _lines(path)
    rec2 = json.loads(lines[1])
    rec2.update(p_value=0.001, summary={"sharpe": 2.5})
    lines[1] = L.record_line(rec2)                       # canonical spelling of a record with extra keys
    assert lines[2].startswith('{"hash":')
    lines[2] = '{"payload":{"ledger_records":999},' + lines[2][1:]
    _write(path, lines)
    assert L.record_hash(rec2) == rec2["hash"]           # the hash alone cannot see either change
    assert json.loads(lines[2])["payload"]["ledger_records"] == 12

    errs = _refused_everywhere(path, cls=L.PublicIndex)
    assert any(e.startswith("record 2:") and "p_value" in e and "summary" in e for e in errs), errs
    assert any(e.startswith("record 3:") and "duplicate key payload" in e for e in errs), errs
    with pytest.raises(L.LedgerError, match="does not verify"):
        _book(path)                                      # the full-ledger class refuses it too
    records, errs2 = L.verify_snapshot(path.read_bytes())
    assert errs2 == errs and [r["seq"] for r in records] == [1, 2, 3]   # the chain itself is intact: both reported


def test_p1a_each_violation_alone_is_refused(tmp_path):
    for which in ("extra_keys", "duplicate"):
        path = tmp_path / f"{which}.jsonl"
        _public(path)
        lines = _lines(path)
        if which == "extra_keys":
            rec = json.loads(lines[1])
            rec["p_value"] = 0.001
            lines[1] = L.record_line(rec)
        else:
            lines[2] = '{"payload":{"ledger_records":999},' + lines[2][1:]
        _write(path, lines)
        errs = _refused_everywhere(path, cls=L.PublicIndex)
        assert len(errs) == 1, errs


# ------------------------------------------------------------------------------------------------ P1-b

def _respell(line: str, how: str) -> str:
    rec = json.loads(line)
    if how == "spaces":
        return json.dumps(rec, sort_keys=True, ensure_ascii=False)
    if how == "key_order":
        return json.dumps(dict(reversed(list(rec.items()))), separators=(",", ":"), ensure_ascii=False)
    if how == "ascii_escapes":
        return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if how == "trailing_space":
        return line + " "
    if how == "leading_space":
        return " " + line
    if how == "escaped_slash":
        return line.replace("café/route", "café\\/route")
    if how == "number_spelling":
        return line.replace('"x":0}', '"x":-0}')
    if how == "nested_duplicate":
        return line.replace('"x":0}', '"x":7,"x":0}')
    raise AssertionError(how)


@pytest.mark.parametrize("how", ["spaces", "key_order", "ascii_escapes", "trailing_space", "leading_space",
                                 "escaped_slash", "number_spelling", "nested_duplicate"])
def test_p1b_a_non_canonical_spelling_of_a_valid_record_is_refused(tmp_path, how):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"note": "first"})
    book.append("screening_decision", {"note": "café/route", "x": 0})
    book.append("screening_decision", {"note": "last"})
    lines = _lines(path)
    spelled = _respell(lines[1], how)
    assert spelled != lines[1]
    rec = json.loads(spelled)
    assert rec == json.loads(lines[1]) and L.record_hash(rec) == rec["hash"]   # the same, hash-valid record
    lines[1] = spelled
    _write(path, lines)
    errs = _refused_everywhere(path)
    want = "duplicate key x" if how == "nested_duplicate" else "not the canonical form"
    assert len(errs) == 1 and errs[0].startswith("record 2:") and want in errs[0], errs


# ------------------------------------------------------------------------------------------------ P1-c

def test_p1c_ledgers_the_writer_produces_verify_on_every_path(tmp_path):
    """No false positive: what the writer writes (unicode, escapes, line separators, floats, nesting) passes the
    fast path, ``verify_snapshot`` and ``read`` alike."""
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    payloads = [{"note": "plain"}, {"note": "café \u2028 \x85 \u2029 \"q\" \\ / \t"}, {"x": 1.5, "y": -0.0,
                "z": 1e-300, "big": 10 ** 30, "nested": {"b": [1, {"a": None}], "a": True}}, {"emoji": "\U0001f600"}]
    for p in payloads:
        book.append("screening_decision", p)
    book.correction(1, {"note": {"old": "plain", "new": "plainer"}}, "a reason with \u2028 in it")
    snapshot = path.read_bytes()
    assert L.verify(path) == [] and L.verify_snapshot(snapshot)[1] == []
    assert [line for _, line in L.iter_verified(io.BytesIO(snapshot))] == _lines(path)
    assert L.read(path) == book.records() == _book(path).records()


def test_p1c_the_committed_exploration_ledger_still_verifies():
    path = ROOT / "results/manhattan_engine/exploration_ledger.jsonl"
    assert L.verify(path) == []
    with path.open("rb") as f:
        assert sum(1 for _ in L.iter_verified(f)) == len(_book(path)) > 0
    assert not path.with_name(path.name + ".lock").exists()   # no sidecar: the lock is on the ledger file itself


def test_p1c_opening_a_ledger_creates_nothing(tmp_path):
    path = tmp_path / "missing" / "ledger.jsonl"
    assert len(_book(path)) == 0
    assert not (tmp_path / "missing").exists()


# ------------------------------------------------------------------------------------------------ P1-d (C6 repro)

_WORKER = r"""
import os, sys, time
from manhattan import ledger as L
path, who, other, sync = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
n, burst, overlap, lead = (int(x) for x in sys.argv[5:9])


def progress(name):
    # the other writer's completed appends, as it last published them (never more than the truth)
    try:
        with open(os.path.join(sync, "progress-" + name)) as f:
            return int(f.read())
    except FileNotFoundError:
        return 0


def publish(count):
    tmp = os.path.join(sync, f"progress-{who}.tmp")
    with open(tmp, "w") as f:
        f.write(str(count))
    os.replace(tmp, os.path.join(sync, "progress-" + who))


def wait(ready, what):
    deadline = time.time() + 120
    while not ready():
        if time.time() > deadline:
            raise SystemExit(f"{who}: timed out waiting for {what}")
        time.sleep(0.0005)


wait(lambda: os.path.exists(os.path.join(sync, "go")), "the start signal")
book = L.Ledger(path, writer=who, protocol="f" * 64)
done = stale = 0


def my_turn():
    # Bursts of `burst` appends, the leader's burst j first, then the other's burst j. A burst may start once the
    # other writer is within `overlap` appends of finishing its preceding burst, so the two really append at the
    # same time (on the lock, with stale handles) at every handover.
    j = done // burst
    return progress(other) >= min((j if lead else j + 1) * burst - overlap, n)


while done < n:
    wait(my_turn, other + "'s burst")
    try:
        book.append("screening_decision", {"by": who, "i": done})
    except L.LedgerError as e:
        if "stale" not in str(e):
            raise
        stale += 1                                   # the other process appended: reopen and try again
        book = L.Ledger(path, writer=who, protocol="f" * 64)
        continue
    done += 1
    publish(done)
print(stale)
"""


def test_p1d_two_processes_appending_concurrently_keep_one_linear_chain(tmp_path):
    """The S17 fork reproduction with two real processes, 1,000 appends each, started together, each appending
    through its own long-lived handle. On main both handles appended on their own heads and the file forked
    (``seq is 2, expected 3``; unopenable).

    The interleaving is deterministic: a file handshake makes the writers take bursts of ``burst`` appends in
    turn, each burst starting while the other writer still has ``overlap`` appends of its burst to make, so at
    every handover both append at once. Whatever the scheduler does, A's burst j+1 cannot start before B's burst j
    has, nor B's burst j+1 before A's burst j+1: B[0] < A[K] < B[K] < A[2K] < ... is forced, at least
    ``2 * (n // burst) - 2`` switches. Each switch after the first means the resuming writer held a handle the other
    had made stale: refused and reopened, never forked."""
    n, burst, overlap = 1000, 8, 2
    path, sync = tmp_path / "ledger.jsonl", tmp_path / "sync"
    sync.mkdir()
    env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    procs = [subprocess.Popen([sys.executable, "-c", _WORKER, str(path), who, other, str(sync), str(n), str(burst),
                               str(overlap), lead], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True)
             for who, other, lead in (("A", "B", "1"), ("B", "A", "0"))]
    (sync / "go").touch()
    outs = [p.communicate(timeout=600) for p in procs]
    assert [p.returncode for p in procs] == [0, 0], outs
    assert L.verify(path) == []
    book = _book(path)                                   # reopen OK
    recs = book.records()
    assert [r["seq"] for r in recs] == list(range(1, 2 * n + 1))
    assert len({r["prev_hash"] for r in recs}) == 2 * n  # 0 forks: no record shares a predecessor
    assert all(r["prev_hash"] == q["hash"] for q, r in zip(recs, recs[1:]))
    for who in ("A", "B"):
        assert [r["payload"]["i"] for r in recs if r["writer"] == who] == list(range(n))
    writers = [r["writer"] for r in recs]
    switches = sum(a != b for a, b in zip(writers, writers[1:]))
    assert switches >= 2 * (n // burst) - 2              # interleaved by construction (here at least 248)
    assert sum(int(o) for o, _ in outs) >= switches - 1  # each resumption after the first met a stale handle
    assert book.append("screening_decision", {"by": "after"})["seq"] == 2 * n + 1


def test_p1d_an_append_waits_for_the_writer_lock(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"n": 1})
    fd = os.open(path, os.O_RDWR)                        # the lock is on the ledger file itself
    fcntl.flock(fd, fcntl.LOCK_EX)                       # another writer holds the lock
    done = threading.Event()
    t = threading.Thread(target=lambda: (book.append("screening_decision", {"n": 2}), done.set()))
    try:
        t.start()
        assert not done.wait(0.5)                        # blocked behind the lock, nothing written
        assert len(_lines(path)) == 1
    finally:
        os.close(fd)                                     # release
    t.join(10)
    assert done.is_set() and len(_book(path)) == 2


# ------------------------------------------------------------------------------------------------ P1-e

def test_p1e_a_stale_handle_cannot_append_and_writes_nothing(tmp_path):
    path = tmp_path / "ledger.jsonl"
    first, second = _book(path), _book(path)
    first.append("screening_decision", {"by": "first"})
    before = path.read_bytes()
    with pytest.raises(L.LedgerError, match="stale"):
        second.append("screening_decision", {"by": "second"})
    with pytest.raises(L.LedgerError, match="stale"):
        second.start_evaluation({"executable": "e", "family": "f", "batch": "b", "spec_hash": "s",
                                 "data_hash": "d", "window": {"id": "w"}})
    assert path.read_bytes() == before and len(second) == 0
    assert L.verify(path) == []
    again = _book(path)                                  # reopening gives a current handle
    assert again.append("screening_decision", {"by": "second"})["seq"] == 2
    with pytest.raises(L.LedgerError, match="stale"):
        first.append("screening_decision", {"by": "first"})   # now first is the stale one
    assert len(_book(path)) == 2 and L.verify(path) == []


def test_p1e_a_handle_whose_file_was_replaced_or_truncated_is_stale(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    for i in range(3):
        book.append("screening_decision", {"i": i})
    lines = _lines(path)
    _write(path, lines[:2])                              # truncated by someone else
    with pytest.raises(L.LedgerError, match="stale"):
        book.append("screening_decision", {"i": 3})
    assert _lines(path) == lines[:2]
    path.unlink()                                        # removed
    with pytest.raises(L.LedgerError, match="stale"):
        book.append("screening_decision", {"i": 3})
    assert not path.exists()


def test_p1e_no_line_is_glued_onto_a_partial_last_line(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    path.write_bytes(path.read_bytes().rstrip(b"\n"))   # a complete record that lost its newline
    before = path.read_bytes()
    with pytest.raises(L.LedgerError, match="partial line"):
        book.append("screening_decision", {"i": 1})
    assert path.read_bytes() == before
    assert L.recover_torn_tail(path) == {"status": "newline_restored"}
    assert book.append("screening_decision", {"i": 1})["seq"] == 2 and L.verify(path) == []


# ------------------------------------------------------------------------------------------------ P1-f

def test_p1f_a_partial_write_makes_the_handle_unusable_and_recovery_restores_the_file(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    for i in range(2):
        book.append("screening_decision", {"i": i})
    good = path.read_bytes()
    real_write, calls = os.write, []

    def torn_write(fd, data):
        calls.append(len(data))
        if len(calls) == 1:
            real_write(fd, bytes(data[: len(data) // 2]))
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", torn_write)
    with pytest.raises(OSError):
        book.append("screening_decision", {"i": 2, "pad": "x" * 200})
    monkeypatch.setattr(os, "write", real_write)
    torn = path.read_bytes()
    assert torn.startswith(good) and len(torn) > len(good) and not torn.endswith(b"\n")
    assert len(book) == 2                                # nothing indexed
    with pytest.raises(L.LedgerError, match="unusable"):
        book.append("screening_decision", {"i": 2})
    with pytest.raises(L.LedgerError, match="unusable"):
        book.correction(1, {"i": {"old": 0, "new": 1}}, "after a torn write")
    assert path.read_bytes() == torn                     # no further bytes after the torn ones
    with pytest.raises(L.LedgerError, match="does not verify"):
        _book(path)
    report = L.recover_torn_tail(path)
    assert report["status"] == "torn_tail_quarantined" and path.read_bytes() == good
    assert (tmp_path / report["quarantine"]).read_bytes() == torn[len(good):]
    assert L.verify(path) == []
    fresh = _book(path)
    assert len(fresh) == 2 and fresh.append("screening_decision", {"i": 2})["seq"] == 3
    assert L.verify(path) == []


def test_p1f_a_failed_sync_also_makes_the_handle_unusable(tmp_path, monkeypatch):
    """The line may be on file but not indexed by this handle: it must not append on a head it no longer knows."""
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})

    def failing_fsync(fd):
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(OSError):
        book.append("screening_decision", {"i": 1})
    monkeypatch.undo()
    with pytest.raises(L.LedgerError, match="unusable"):
        book.append("screening_decision", {"i": 2})
    assert len(_book(path)) == 2 and L.verify(path) == []   # the written record is read by a fresh handle


def test_a_refused_append_before_writing_leaves_the_handle_usable(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    with pytest.raises(L.LedgerError):
        book.append("not_a_type", {})
    with pytest.raises(Exception):
        book.append("screening_decision", {"bad": object()})
    assert not path.exists()
    assert book.append("screening_decision", {"ok": 1})["seq"] == 1


# ------------------------------------------------------------------------------------------------ durability

def test_appends_sync_the_file_and_on_creation_the_directory(tmp_path, monkeypatch):
    calls = []
    real_fsync = os.fsync
    monkeypatch.setattr(L, "_fsync_dir", lambda d: calls.append(("dir", Path(d))))
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(("file", fd)), real_fsync(fd))[1])
    path = tmp_path / "sub" / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    assert [c[0] for c in calls] == ["file", "dir"] and calls[1][1] == path.parent
    calls.clear()
    book.append("screening_decision", {"i": 1})
    assert [c[0] for c in calls] == ["file"]


def test_on_macos_appends_also_full_fsync(tmp_path, monkeypatch):
    """``F_FULLFSYNC`` after ``fsync`` where the platform has it (``fcntl.F_FULLFSYNC`` is 51 on macOS); simulated
    here on any platform. On macOS itself the real call runs in every append of this suite."""
    seen = []
    real_fcntl = fcntl.fcntl
    monkeypatch.setattr(L, "_FULLFSYNC", 51)
    monkeypatch.setattr(fcntl, "fcntl", lambda fd, cmd, *a: seen.append(cmd) if cmd == 51 else real_fcntl(fd, cmd, *a))
    book = _book(tmp_path / "ledger.jsonl")
    book.append("screening_decision", {"i": 0})
    book.append("screening_decision", {"i": 1})
    assert seen == [51, 51]
    if sys.platform == "darwin":
        assert hasattr(fcntl, "F_FULLFSYNC")


def test_recover_torn_tail_waits_for_the_writer_lock(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _book(path).append("screening_decision", {"i": 0})
    path.write_bytes(path.read_bytes() + b'{"hash":"ab')
    fd = os.open(path, os.O_RDWR)                        # the lock is on the ledger file itself
    fcntl.flock(fd, fcntl.LOCK_EX)
    result = {}
    t = threading.Thread(target=lambda: result.update(L.recover_torn_tail(path)))
    try:
        t.start()
        time.sleep(0.3)
        assert not result and path.read_bytes().endswith(b'{"hash":"ab')
    finally:
        os.close(fd)
    t.join(10)
    assert result["status"] == "torn_tail_quarantined" and L.verify(path) == []


def test_an_unsupported_full_fsync_does_not_fail_a_written_append(tmp_path, monkeypatch):
    """``F_FULLFSYNC`` runs after the line is written and ``fsync``ed. Where it is not supported (ENOTSUP) the append
    has succeeded: reporting it as failed would poison the handle and invite a duplicate registration on retry."""
    real_fcntl = fcntl.fcntl

    def unsupported(fd, cmd, *a):
        if cmd == 51:
            raise OSError(errno.ENOTSUP, "Operation not supported")
        return real_fcntl(fd, cmd, *a)

    monkeypatch.setattr(L, "_FULLFSYNC", 51)
    monkeypatch.setattr(fcntl, "fcntl", unsupported)
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    first = book.append("screening_decision", {"i": 0})
    second = book.append("screening_decision", {"i": 1})          # the handle is still usable
    assert (first["seq"], second["seq"]) == (1, 2)
    assert L.verify(path) == [] and _book(path).records() == book.records()


# ------------------------------------------------------------------------------------------------ framing

def _framed(path, how: str) -> None:
    """Re-frame a valid three-record file; every record line itself stays canonical."""
    raw = path.read_bytes()
    first = raw.index(b"\n")
    if how == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    elif how == "crlf_one_line":
        raw = raw[:first] + b"\r" + raw[first:]
    elif how == "cr_as_terminator":
        raw = raw[:first] + b"\r" + raw[first + 1:]
    elif how in ("ff", "fs", "gs", "rs", "nel", "vt"):
        ch = {"ff": "\x0c", "fs": "\x1c", "gs": "\x1d", "rs": "\x1e", "nel": "\x85", "vt": "\x0b"}[how]
        raw = raw[:-1] + ch.encode() + b"\n"                      # a trailing line break on the last line
    elif how == "blank_line":
        raw = raw[:first + 1] + b"\n" + raw[first + 1:]
    elif how == "whitespace_line":
        raw = raw[:first + 1] + b"  \t\n" + raw[first + 1:]
    elif how == "trailing_blank_line":
        raw = raw + b"\n"
    elif how == "no_final_newline":
        raw = raw[:-1]
    else:
        raise AssertionError(how)
    path.write_bytes(raw)


FRAMINGS = ["crlf", "crlf_one_line", "cr_as_terminator", "ff", "fs", "gs", "rs", "nel", "vt", "blank_line",
            "whitespace_line", "trailing_blank_line", "no_final_newline"]


@pytest.mark.parametrize("how", FRAMINGS)
def test_the_file_must_be_exactly_canonical_lines_each_ending_in_a_newline(tmp_path, how):
    """``str.splitlines`` accepted CRLF, other line breaks (``\\x0c``, ``\\x1c``-``\\x1e``, ``\\x85``, ...), blank
    lines and a missing final newline; the hash sees none of them. Every reader now refuses them."""
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    for i in range(3):
        book.append("screening_decision", {"i": i})
    _framed(path, how)
    errs = _refused_everywhere(path)
    want = {"blank_line": "a blank line", "whitespace_line": "a blank line", "trailing_blank_line": "a blank line",
            "no_final_newline": "no final newline"}.get(how, "another line break")
    assert len(errs) == 1 and want in errs[0], errs
    records, _ = L.verify_snapshot(path.read_bytes())
    assert len(records) == 3                                      # the chain itself is intact: framing alone
    if how in ("crlf", "ff", "fs", "gs", "rs", "nel", "vt", "trailing_blank_line", "no_final_newline"):
        before = path.read_bytes()
        with pytest.raises(L.LedgerError):
            book.append("screening_decision", {"i": 3})          # the last line is checked byte for byte
        assert path.read_bytes() == before
    assert L.verify(path) == errs


def test_many_framing_problems_are_summarized(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    for i in range(5):
        book.append("screening_decision", {"i": i})
    _framed(path, "crlf")
    assert L.verify(path) == ["line 1: another line break in the line (a record line ends in \\n alone); "
                              "and 4 more such line(s)"]


# ------------------------------------------------------------------------------------------------ readers' lock

@pytest.mark.parametrize("reader", ["Ledger", "PublicIndex", "verify", "read"])
def test_readers_wait_for_a_writer_holding_the_lock(tmp_path, reader):
    """``Ledger()``, ``verify`` and ``read`` take the shared lock (when the lock file exists), so they never read
    while an append holds the exclusive lock (a half-written line)."""
    path = tmp_path / "ledger.jsonl"
    cls = L.PublicIndex if reader == "PublicIndex" else L.Ledger
    _book(path, cls).append("screening_decision", {"i": 0})
    call = {"Ledger": lambda: len(_book(path)), "PublicIndex": lambda: len(_book(path, L.PublicIndex)),
            "verify": lambda: L.verify(path), "read": lambda: len(L.read(path))}[reader]
    fd = os.open(path, os.O_RDWR)                        # the lock is on the ledger file itself
    fcntl.flock(fd, fcntl.LOCK_EX)                                # a writer is mid-append
    result = []
    t = threading.Thread(target=lambda: result.append(call()))
    try:
        t.start()
        time.sleep(0.4)
        assert result == []                                       # still waiting
    finally:
        os.close(fd)
    t.join(10)
    assert result == [[] if reader == "verify" else 1]


# ------------------------------------------------------------------------------------------------ code identity

# SHA-256 of every file of the simulation's code identities (manhattan/sim/run.py CODE_FILES, CODE_FILES_HB,
# CODE_FILES_V2, CODE_FILES_V2_HB) other than manhattan/ledger.py, as on main when this PR was written.
SIM_CODE_FILES = {
    "manhattan/sim/hb.py": "467508a312bd5106dcc3a8662950c368a76f2ecf91f3c4161e272b7ace700c51",
    "manhattan/sim/hb_v2.py": "740ceb1e3ba9eec3dcc9882d895e0ac919e12f5f877a747d548c637a91aaf4cd",
    "manhattan/sim/pipeline.py": "79a1613090158000880271cd33561c26b361a8e1965f5a6efc4b2a360f634310",
    "manhattan/sim/pipeline_v2.py": "ce1069cfeb912c7a86d47f702256db88f143e2079b565cfa32012bbe22dc05ff",
    "manhattan/sim/seeds.py": "a79eed4e41732769653a93260f6ac8264e5c77b71fc29c4a46ac3671792741ca",
    "manhattan/sim/world.py": "2c8655326a4db6f6a35f8529838163612af958bc35b44855dfb25b794bf300ee",
    "manhattan/stats/blocklen.py": "556ffbd8c16f446bc134e402ca08fb78819e69637e2d4070bc1d60dedc6f0aa3",
    "manhattan/stats/bootstrap.py": "fa6f1c0fa7b74692f50fdf1ded8243589d602b929d3e96d70d28345ae1e8f238",
    "manhattan/stats/dormancy.py": "b9c55f2390d747552e04ad02da6fbb4d45d985a06c94414ca2f167fd9822857a",
    "manhattan/stats/elond.py": "cfdb08fb23ef668735b44bc92a821bfa07fa50770cd446f2d96c756ff75ae047",
    "manhattan/stats/eprocess.py": "cdc328c055b4a6b403183bec4f81e5e32d72efe186a84d66704b283fb7edfb92",
    "manhattan/stats/hedge.py": "edc57222768221f16d7f89e098c145eca99f6d5c58fcccd024079b5d1d07e958",
    "manhattan/stats/hier.py": "0112493a8b2481db16939a1b333ee85b09b06b3af308504553cba8a0b0401738",
    "manhattan/stats/hier_analytic.py": "5acb257bb39afb34b25cf1b5ac164565089035055b6620c2437dfba5d35f40d9",
    "manhattan/stats/schedule.py": "4fd9f36eaa96c23db4c0094fce917cae3b1b09719370197b425b9e2e68fb8d46",
    "manhattan/stats/screening.py": "2290ba73663185b84dc96608bb07bba7e63b48716845ec3e082afb8fa5cd1a82",
    "manhattan/stats/spa.py": "19572f7c5a608b713b49fc7d4ed745195e3eccf0949f71c0f3f0ed257b50a82d",
    "manhattan/stats/spa_hedged.py": "c79b976b81ec9eb752dfc7ef5b5100022e3d7838fb2cefd8122aa3a9562978f3",
    "manhattan/stats/tiers.py": "3cd501612672827f08f5da9f5e0189217611261f3acb744ded2a566d2a8f3b23",
}


def test_no_simulation_code_file_but_the_ledger_changed():
    """This PR changes only ``manhattan/ledger.py`` among the simulation's code files. It is listed in
    ``CODE_FILES_V2_HB`` alone, so the HB v2 code identity changes (acceptable: the HB rerun waits for this PR, K1);
    version 1's and STD v2's identities are unchanged."""
    from manhattan.sim import run
    sets = {"CODE_FILES": run.CODE_FILES, "CODE_FILES_HB": run.CODE_FILES_HB, "CODE_FILES_V2": run.CODE_FILES_V2,
            "CODE_FILES_V2_HB": run.CODE_FILES_V2_HB}
    assert {k for k, files in sets.items() if "manhattan/ledger.py" in files} == {"CODE_FILES_V2_HB"}
    union = set().union(*sets.values()) - {"manhattan/ledger.py"}
    assert union == set(SIM_CODE_FILES)
    for rel, digest in SIM_CODE_FILES.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel
    assert run.code_hash("STD") == "da641c096d17bbf4" and run.code_hash("HB") == "0b8dd1af6db62c9f"
    assert run.code_hash("STD", version="v2") == "9d1b680ff7e19ca7"


# ------------------------------------------------------------------------------------- lock identity across aliases
# Review of #108 (2026-11-23, alias blocker): the lock used to be a sidecar named from the path the caller passed
# (``<path>.lock``), so the same ledger opened through its real path and through a symlink or a hard link took two
# different locks, and two concurrent appends could both write seq 2 (a forked, unopenable chain). The lock is now
# ``flock`` on the ledger file itself, which every alias shares. Threat model: local POSIX file systems with coherent
# ``flock`` (not NFS, SMB or FUSE); concurrent or misconfigured processes, not a writer who rewrites the file.

def _alias(tmp_path, path, kind):
    """Another name for the ledger file ``path``: a symlink to it, a hard link, a ``..`` path, or the same name
    through a symlinked directory."""
    if kind == "symlink":
        alias = tmp_path / "alias.jsonl"
        alias.symlink_to(path)
    elif kind == "hardlink":
        alias = tmp_path / "hard.jsonl"
        os.link(path, alias)
    elif kind == "dotdot":
        (tmp_path / "sub").mkdir()
        alias = tmp_path / "sub" / ".." / path.name
    else:                                                   # symlinked_dir
        (tmp_path / "linkdir").symlink_to(tmp_path, target_is_directory=True)
        alias = tmp_path / "linkdir" / path.name
    assert os.path.samefile(alias, path) and str(alias) != str(path)
    return alias


_ALIAS_WORKER = r"""
import json, os, sys, time
from manhattan import ledger as L
alias, sync = sys.argv[1], sys.argv[2]
book = L.Ledger(alias, writer="B", protocol="f" * 64)          # loads the same head as the parent's handle
open(os.path.join(sync, "loaded"), "w").close()
deadline = time.time() + 60
while not os.path.exists(os.path.join(sync, "go")):
    if time.time() > deadline:
        raise SystemExit("timed out waiting for go")
    time.sleep(0.001)
try:
    out = {"ok": book.append("screening_decision", {"by": "B"})["seq"]}
except L.LedgerError as e:
    out = {"refused": str(e)}
tmp = os.path.join(sync, "result.tmp")
with open(tmp, "w") as f:
    f.write(json.dumps(out))
os.replace(tmp, os.path.join(sync, "result"))
"""


def _wait_for(p: Path, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while not p.exists():
        assert time.time() < deadline, f"timed out waiting for {p.name}"
        time.sleep(0.005)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "dotdot", "symlinked_dir"])
def test_alias_two_processes_same_head_at_most_one_append_at_seq_2(tmp_path, monkeypatch, kind):
    """Deterministic interleaving. Both handles load the ledger at seq 1: B in another process through an alias, A
    here through the real path. A takes the writer lock, checks its head and is held just before writing (a gated
    write); only then is B told to append. B must wait for A's lock (the same file), and once A has written seq 2,
    B's append is refused as stale with nothing written. On the sidecar lock, B took another lock, appended seq 2
    while A held its own, and A then wrote a second seq 2: a fork."""
    path = tmp_path / "ledger.jsonl"
    _book(path).append("screening_decision", {"i": 0})
    alias = _alias(tmp_path, path, kind)
    sync = tmp_path / "sync"
    sync.mkdir()
    env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    proc = subprocess.Popen([sys.executable, "-c", _ALIAS_WORKER, str(alias), str(sync)], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _wait_for(sync / "loaded")
        book_a = _book(path, writer="A")
        entered, release = threading.Event(), threading.Event()
        real_write = L._write_all

        def gated(fd, data):                               # A holds the lock and has checked its head
            entered.set()
            assert release.wait(60)
            return real_write(fd, data)

        monkeypatch.setattr(L, "_write_all", gated)
        got = {}
        t = threading.Thread(target=lambda: got.update(seq=book_a.append("screening_decision", {"by": "A"})["seq"]))
        t.start()
        assert entered.wait(60)
        (sync / "go").touch()
        time.sleep(1.5)
        b_finished_while_a_held_the_lock = (sync / "result").exists()
        release.set()
        t.join(60)
        out, err = proc.communicate(timeout=120)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, err
    assert not b_finished_while_a_held_the_lock            # B waited on the same lock as A
    assert got["seq"] == 2
    result = json.loads((sync / "result").read_text())
    assert "refused" in result and "stale" in result["refused"], result
    assert L.verify(path) == [] and L.verify(alias) == []
    recs = L.read(alias)
    assert [r["seq"] for r in recs] == [1, 2] and recs[1]["writer"] == "A"
    assert len({r["prev_hash"] for r in recs}) == 2         # one linear chain, no fork
    assert _book(alias).append("screening_decision", {"after": 1})["seq"] == 3


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "dotdot", "symlinked_dir"])
def test_alias_stale_head_is_refused_and_nothing_is_written(tmp_path, kind):
    path = tmp_path / "ledger.jsonl"
    _book(path).append("screening_decision", {"i": 0})
    alias = _alias(tmp_path, path, kind)
    a, b = _book(path, writer="A"), _book(alias, writer="B")
    assert a.append("screening_decision", {"by": "A"})["seq"] == 2
    before = path.read_bytes()
    with pytest.raises(L.LedgerError, match="stale"):
        b.append("screening_decision", {"by": "B"})
    assert path.read_bytes() == before and L.verify(alias) == []
    assert _book(alias, writer="B").append("screening_decision", {"by": "B"})["seq"] == 3   # after reopening


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
@pytest.mark.parametrize("op", ["append", "Ledger", "verify", "read", "recover_torn_tail"])
def test_alias_operations_wait_for_a_lock_held_through_the_real_path(tmp_path, kind, op):
    path = tmp_path / "ledger.jsonl"
    _book(path).append("screening_decision", {"i": 0})
    alias = _alias(tmp_path, path, kind)
    book = _book(alias)
    call = {"append": lambda: book.append("screening_decision", {"i": 1})["seq"],
            "Ledger": lambda: len(_book(alias)), "verify": lambda: L.verify(alias),
            "read": lambda: len(L.read(alias)), "recover_torn_tail": lambda: L.recover_torn_tail(alias)["status"]}[op]
    fd = os.open(path, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)                         # a writer on the real path is mid-append
    result = []
    t = threading.Thread(target=lambda: result.append(call()))
    try:
        t.start()
        time.sleep(0.5)
        assert result == []                                # waiting on the same lock
    finally:
        os.close(fd)
    t.join(10)
    assert result == [{"append": 2, "Ledger": 1, "verify": [], "read": 1, "recover_torn_tail": "clean"}[op]]


@pytest.mark.parametrize("sidecar", ["held_file", "symlink_to_ledger", "dangling_symlink", "fifo", "directory"])
def test_a_stale_or_hostile_lock_sidecar_is_ignored(tmp_path, sidecar):
    """No ``<ledger>.lock`` is used any more: whatever sits at that name (a file another process holds locked, a
    symlink, a FIFO that would block an opener, a directory) neither blocks nor changes any operation."""
    path = tmp_path / "ledger.jsonl"
    _book(path).append("screening_decision", {"i": 0})
    side = tmp_path / "ledger.jsonl.lock"
    held = None
    if sidecar == "held_file":
        side.write_bytes(b"")
        held = os.open(side, os.O_RDWR)
        fcntl.flock(held, fcntl.LOCK_EX)
    elif sidecar == "symlink_to_ledger":
        side.symlink_to(path)
    elif sidecar == "dangling_symlink":
        side.symlink_to(tmp_path / "nowhere")
    elif sidecar == "fifo":
        os.mkfifo(side)
    else:
        side.mkdir()
    done = []
    t = threading.Thread(target=lambda: done.append((_book(path).append("screening_decision", {"i": 1})["seq"],
                                                     L.verify(path), len(L.read(path)),
                                                     L.recover_torn_tail(path)["status"])), daemon=True)
    try:
        t.start()
        t.join(10)
    finally:
        if held is not None:
            os.close(held)
    assert done == [(2, [], 2, "clean")]
    assert not (tmp_path / "nowhere").exists()


def test_a_path_replaced_before_the_lock_is_refused_and_nothing_is_written(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    copy = tmp_path / "copy.jsonl"
    copy.write_bytes(path.read_bytes())
    old = os.stat(path).st_ino
    real_lock = L._lock_fd

    def replace_then_lock(fd, exclusive):                  # the path is replaced between open and lock
        if exclusive:
            os.replace(copy, path)
        return real_lock(fd, exclusive)

    monkeypatch.setattr(L, "_lock_fd", replace_then_lock)
    before = path.read_bytes()
    with pytest.raises(L.LedgerError, match="replaced"):
        book.append("screening_decision", {"i": 1})
    assert os.stat(path).st_ino != old and path.read_bytes() == before and L.verify(path) == []


def test_a_path_replaced_during_the_append_raises_and_the_handle_is_unusable(tmp_path, monkeypatch):
    """The record lands in the file the descriptor holds; the path no longer names it, so the append must not report
    success."""
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    copy = tmp_path / "copy.jsonl"
    copy.write_bytes(path.read_bytes())
    real_write = L._write_all

    def replace_then_write(fd, data):
        os.replace(copy, path)
        return real_write(fd, data)

    monkeypatch.setattr(L, "_write_all", replace_then_write)
    with pytest.raises(L.LedgerError, match="replaced"):
        book.append("screening_decision", {"i": 1})
    monkeypatch.setattr(L, "_write_all", real_write)
    assert [r["seq"] for r in L.read(path)] == [1] and L.verify(path) == []
    with pytest.raises(L.LedgerError, match="unusable"):
        book.append("screening_decision", {"i": 2})
    assert _book(path).append("screening_decision", {"i": 2})["seq"] == 2


@pytest.mark.parametrize("op", ["append", "recover_torn_tail", "Ledger"])
def test_a_path_renamed_or_removed_around_the_lock_is_refused(tmp_path, monkeypatch, op):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    real_lock = L._lock_fd

    def rename_then_lock(fd, exclusive):
        os.rename(path, tmp_path / "moved.jsonl")
        monkeypatch.setattr(L, "_lock_fd", real_lock)
        return real_lock(fd, exclusive)

    monkeypatch.setattr(L, "_lock_fd", rename_then_lock)
    call = {"append": lambda: book.append("screening_decision", {"i": 1}),
            "recover_torn_tail": lambda: L.recover_torn_tail(path), "Ledger": lambda: _book(path)}[op]
    with pytest.raises(L.LedgerError, match="replaced, renamed or removed"):
        call()
    assert not path.exists() and [r["seq"] for r in L.read(tmp_path / "moved.jsonl")] == [1]


def test_a_handle_whose_ledger_was_removed_creates_nothing(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    path.unlink()
    with pytest.raises(L.LedgerError, match="no longer exists"):
        book.append("screening_decision", {"i": 1})
    assert not path.exists()


def test_a_ledger_removed_as_append_opens_it_is_not_recreated(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    real_open = os.open
    opened = []

    def remove_then_open(name, flags, *args, **kwargs):
        if name == path:
            if not opened:
                path.unlink()
            opened.append(flags)
        return real_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(L.os, "open", remove_then_open)
    with pytest.raises(L.LedgerError, match="no longer exists"):
        book.append("screening_decision", {"i": 1})
    assert opened and all(not flags & os.O_CREAT for flags in opened)
    assert not path.exists()


@pytest.mark.parametrize("complete_record", [True, False])
def test_recovery_refuses_a_path_replaced_during_sync(tmp_path, monkeypatch, complete_record):
    path = tmp_path / "ledger.jsonl"
    book = _book(path)
    book.append("screening_decision", {"i": 0})
    valid = path.read_bytes()
    path.write_bytes(valid[:-1] if complete_record else valid + b'{"hash":"')
    replacement = tmp_path / "replacement.jsonl"
    replacement.write_bytes(valid)
    real_fsync = os.fsync
    repaired_inode = path.stat().st_ino

    def replace_then_sync(fd):
        if os.fstat(fd).st_ino == repaired_inode:
            os.replace(replacement, path)
        return real_fsync(fd)

    monkeypatch.setattr(L.os, "fsync", replace_then_sync)
    with pytest.raises(L.LedgerError, match="during recovery"):
        L.recover_torn_tail(path)
    assert path.stat().st_ino != repaired_inode
    assert path.read_bytes() == valid
    assert L.verify(path) == []


def test_a_dangling_symlink_is_never_created_through(tmp_path):
    target, link = tmp_path / "target.jsonl", tmp_path / "link.jsonl"
    link.symlink_to(target)
    book = _book(link)
    assert len(book) == 0
    with pytest.raises(L.LedgerError, match="dangling symlink"):
        book.append("screening_decision", {"i": 0})
    assert not target.exists()


@pytest.mark.parametrize("kind", ["fifo", "directory"])
@pytest.mark.parametrize("op", ["Ledger", "verify", "read", "append", "recover_torn_tail"])
def test_a_ledger_path_that_is_not_a_regular_file_is_refused_without_blocking(tmp_path, kind, op):
    path = tmp_path / "ledger.jsonl"
    os.mkfifo(path) if kind == "fifo" else path.mkdir()
    book = L.Ledger.__new__(L.Ledger)                       # an empty handle, as if loaded before the swap
    book.path, book.writer, book.protocol, book._unusable = path, "w", PROTOCOL, None
    book._reset()
    call = {"Ledger": lambda: _book(path), "verify": lambda: L.verify(path), "read": lambda: L.read(path),
            "append": lambda: book.append("screening_decision", {"i": 0}),
            "recover_torn_tail": lambda: L.recover_torn_tail(path)}[op]
    out = []

    def run():
        try:
            call()
            out.append("accepted")
        except (L.LedgerError, IsADirectoryError) as e:
            out.append(type(e).__name__)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(10)
    assert out and out[0] != "accepted", out
