"""The U+2028 / U+2029 / U+0085 ledger defect, fixed on the writer side (``ledger.record_line``).

``verify_snapshot`` splits a ledger file with ``str.splitlines()``, which also breaks lines at U+0085, U+2028 and
U+2029; ``json.dumps(ensure_ascii=False)`` wrote those characters raw. A payload string holding one therefore made
the ledger unopenable and unauditable. The writer now writes them as JSON escapes. These tests cover writing,
reopening, reconciliation, hashing and tampering, and that nothing else changes. Recovering ledgers already written
with a raw separator is not done here (owner decision; see the PR).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime as _dt

import pytest

import manhattan_ledger_reference as RL
from manhattan import access as A, attempts as AT, ledger as L, roles

SEPARATORS = [" ", " ", "\x85"]
PROTOCOL = "f" * 64
FENCE = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)


class _Clock(_dt):
    @classmethod
    def now(cls, tz=None):
        return _dt(2026, 11, 21, 12, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    monkeypatch.setattr(L, "datetime", _Clock)
    monkeypatch.setattr(RL, "datetime", _Clock)


def _h(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def _identity(i: int) -> dict:
    return {"executable": _h("exe", i), "variant": f"v{i}", "hypothesis": "h", "family": "f", "batch": "B-1",
            "role": "exploration", "channel": "blind", "designated": False, "spec_hash": _h("spec", i),
            "data_hash": _h("data"), "window": {"id": "w", "start": "2001-01-02", "end": "2004-12-31",
                                                "frequency": "daily"},
            "code_version": {"commit": "a" * 40, "engine_sha256": "b" * 64}}


def _register(book, ident) -> str:
    dw = A.DeclaredWindow("w", "synthetic:separators", date(2001, 1, 2), date(2004, 12, 31), "exploration",
                          "evaluation", ident["data_hash"])
    return A.register_evaluation(book, identity=ident, windows=[dw], caller="session", fence=FENCE).attempt_id


def _book(path) -> L.Ledger:
    return L.Ledger(path, writer="w", protocol=PROTOCOL)


def _full_lifecycle(book, sep: str) -> None:
    """Every writer path carries the separator: a plain record, a completion summary, a correction reason, a failed
    attempt's neighbour, and a key that holds it."""
    book.append("screening_decision", {"note": f"a{sep}b", f"key{sep}": [f"{sep}", {"deep": f"x{sep}y"}]})
    ident = _identity(1)
    a = _register(book, ident)
    book.record_evaluation(**ident, result_hash=_h("r", 1), n_obs=10, summary={"comment": f"c{sep}d"}, seed=1,
                           attempt_id=a)
    b = _register(book, _identity(2))
    book.end_attempt(b, status="failed", reason="execution_error", data_read=True)
    book.correction(1, {"note": {"old": f"a{sep}b", "new": f"a{sep}{sep}b"}}, f"reason with {sep} inside")


def _anchor(book) -> dict:
    return {"records": len(book), "head": book.head}


@pytest.mark.parametrize("sep", SEPARATORS)
def test_the_writer_escapes_the_separator_and_keeps_the_content(tmp_path, sep):
    book = _book(tmp_path / "l.jsonl")
    _full_lifecycle(book, sep)
    raw = book.path.read_bytes()
    assert sep.encode() not in raw                                      # never written raw
    assert ("\\u%04x" % ord(sep)).encode() in raw
    assert len(raw.decode().splitlines()) == len(book)                  # one record per line, for every reader
    recs = [json.loads(x) for x in raw.splitlines()]
    assert recs[0]["payload"]["note"] == f"a{sep}b"                    # the content is the character itself
    assert recs[0]["payload"][f"key{sep}"][1]["deep"] == f"x{sep}y"
    assert all(r["hash"] == L.record_hash(r) for r in recs)


@pytest.mark.parametrize("sep", SEPARATORS)
def test_the_ledger_reopens_reconciles_and_verifies(tmp_path, sep):
    book = _book(tmp_path / "l.jsonl")
    _full_lifecycle(book, sep)
    again = _book(book.path)
    assert again.head == book.head and again.records() == book.records()
    assert L.verify(book.path) == [] and L.verify(book.path, anchor=book.head) == []
    rep = AT.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
    assert rep["violations"] == [] and rep["completed"] == 1 and rep["failed"] == 1 and rep["unfinished"] == 0
    assert AT.reconcile_lifecycle(book.path, anchor=book.head)["registered"] == 2
    # and a ledger that keeps growing after reopening stays readable
    again.append("screening_decision", {"note": sep * 3})
    assert _book(book.path).head == again.head


@pytest.mark.parametrize("sep", SEPARATORS)
def test_hashes_and_chain_are_those_of_the_unescaped_record(tmp_path, sep):
    """The record hash is computed over the parsed record, so escaping changes no hash: main's writer (the
    reference, which wrote the character raw) and the fixed writer produce the same records, hashes and head."""
    new, ref = _book(tmp_path / "new.jsonl"), RL.Ledger(tmp_path / "ref.jsonl", writer="w", protocol=PROTOCOL)
    for book in (new, ref):
        book.append("screening_decision", {"note": f"a{sep}b"})
        book.append("screening_decision", {"note": "plain"})
    assert new.head == ref.head
    new_lines = new.path.read_bytes().split(b"\n")
    ref_lines = ref.path.read_bytes().split(b"\n")                      # split on \n only: the raw file's records
    assert [json.loads(x) for x in new_lines if x] == [json.loads(x) for x in ref_lines if x]
    assert new_lines[1:] == ref_lines[1:]                               # the record without the character: same bytes


def test_records_without_the_characters_are_written_byte_for_byte_as_before(tmp_path):
    new, ref = _book(tmp_path / "new.jsonl"), RL.Ledger(tmp_path / "ref.jsonl", writer="w", protocol=PROTOCOL)
    for book in (new, ref):
        book.append("screening_decision", {"note": "plain", "unicode": "é ü 中文   ‧ ‪ \u0084 \u0086"})
        book.correction(1, {"note": {"old": "plain", "new": "plainer"}}, "a reason")
    assert new.path.read_bytes() == ref.path.read_bytes()


@pytest.mark.parametrize("sep", SEPARATORS)
@pytest.mark.parametrize("tamper", ["change_character", "remove_escape", "raw_separator", "next_record_edited"])
def test_tampering_with_an_escaped_record_is_detected(tmp_path, sep, tamper):
    """Every change to the content is still refused on reopening and by the reconciler. Rewriting the escape as the
    raw character (the old, unreadable form) is refused too: it splits the record."""
    book = _book(tmp_path / "l.jsonl")
    book.append("screening_decision", {"note": f"a{sep}b"})
    book.append("screening_decision", {"note": "after"})
    anchor = _anchor(book)
    esc = ("\\u%04x" % ord(sep)).encode()
    raw = book.path.read_bytes()
    changed = {
        "change_character": raw.replace(esc, b"\\u2027", 1),
        "remove_escape": raw.replace(esc, b"", 1),
        "raw_separator": raw.replace(esc, sep.encode(), 1),
        "next_record_edited": raw.replace(b'"note":"after"', b'"note":"later"', 1),
    }[tamper]
    assert changed != raw
    book.path.write_bytes(changed)
    with pytest.raises(L.LedgerError, match="does not verify"):
        _book(book.path)
    with pytest.raises(AT.ReconciliationError):
        AT.reconcile(ledger_path=book.path, ledger_anchor=anchor)
    assert L.verify(book.path)


def test_a_ledger_written_raw_before_the_fix_is_still_refused_not_repaired(tmp_path):
    """Ledgers written by main's writer with a raw separator stay exactly as main treats them: refused on reopening
    and by the reconciler, and left untouched on disk. Recovering them is an owner decision (see the PR)."""
    ref = RL.Ledger(tmp_path / "old.jsonl", writer="w", protocol=PROTOCOL)
    ref.append("screening_decision", {"note": "a b"})
    before = ref.path.read_bytes()
    with pytest.raises(L.LedgerError, match="does not verify"):
        _book(ref.path)
    with pytest.raises(AT.ReconciliationError):
        AT.reconcile(ledger_path=ref.path, ledger_anchor={"records": 1, "head": ref.head})
    assert L.recover_torn_tail(ref.path) == {"status": "clean"}        # not a torn write: nothing is moved
    assert ref.path.read_bytes() == before


def test_the_escape_table_is_exactly_the_line_boundaries_json_leaves_raw():
    """Every character ``str.splitlines()`` breaks at is either escaped by JSON or in ``LINE_BREAKS``."""
    boundaries = [chr(c) for c in range(0x110000) if len(("a" + chr(c) + "b").splitlines()) > 1]
    raw_in_json = [c for c in boundaries if c in json.dumps(c, ensure_ascii=False)]
    assert sorted(raw_in_json) == sorted(L.LINE_BREAKS)
    for ch, escaped in L.LINE_BREAKS.items():
        assert json.loads(f'"{escaped}"') == ch
