"""Manhattan phase 3: the indexed ledger, the streamed reconciler and the remembered fence decisions.

Three kinds of test:

* **Differential.** Random lifecycles are run through the current ``manhattan.ledger`` and through the reference
  copy of the ledger as merged on main before this change (``manhattan_ledger_reference``). The files must be
  byte-identical, every call must return the same record or raise the same error, every query must give the same
  answer (after every step, and again after reopening), and the strict reconciler (current against
  ``manhattan_attempts_reference``) must give the same report.
* **Adversarial.** What indexing must not hide: conflicting results, forged starts and completions, records written
  around the index by another writer, edited and rewritten records, irregular files.
* **The fence decision memo** in ``access``: the same decision as ``roles.check_read`` for every input, never a
  remembered refusal, never a reserve read, never a bypass of a replaced function.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime as _dt, timedelta

import pytest

import manhattan_attempts_reference as RA
import manhattan_ledger_reference as RL
from manhattan import access as A, attempts as AT, ledger as L, roles

PROTOCOL = "f" * 64
COMMIT = "a" * 40
CODE = {"commit": COMMIT, "engine_sha256": "b" * 64}
FENCE = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
TYPES_ALL = L.TYPES


class _Clock(_dt):
    @classmethod
    def now(cls, tz=None):
        return _dt(2026, 11, 19, 12, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    monkeypatch.setattr(L, "datetime", _Clock)
    monkeypatch.setattr(RL, "datetime", _Clock)


def _h(*parts) -> str:
    import hashlib
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def _window(w: int) -> dict:
    return {"id": f"win-{w}", "start": "2001-01-02", "end": f"200{3 + w}-12-31", "frequency": "daily"}


def _declared(ident: dict) -> A.DeclaredWindow:
    w = ident["window"]
    return A.DeclaredWindow(w["id"], "synthetic:scaling", date.fromisoformat(w["start"]),
                            date.fromisoformat(w["end"]), "exploration", "evaluation", ident["data_hash"])


def identity(spec: int, data: int = 0, w: int = 0, *, family: str | None = None, batch: str = "B-1") -> dict:
    return {"executable": _h("exe", spec), "variant": f"v{spec}", "hypothesis": f"h{spec % 3}",
            "family": family or f"f{spec % 2}", "batch": batch, "role": "exploration", "channel": "blind",
            "designated": spec % 2 == 0, "spec_hash": _h("spec", spec), "data_hash": _h("data", data),
            "window": _window(w), "code_version": dict(CODE)}


def schema2(ident: dict, *, valid_auth: bool = True) -> dict:
    auth = (A.authorization("engine_evaluation", (_declared(ident),), caller="session", fence=FENCE, freeze=None,
                            holding=0, token=None, identity=ident, config=None)
            if valid_auth else {"caller": "session"})
    return {**ident, "attempt_schema": L.ATTEMPT_SCHEMA, "kind": "engine_evaluation", "authorization": auth}


def legacy(ident: dict) -> dict:
    return {k: ident[k] for k in ("executable", "family", "batch", "spec_hash", "data_hash", "window", "variant",
                                  "hypothesis", "role", "channel", "designated", "code_version")}


def completion(ident: dict, result: int, **kw) -> dict:
    return dict(ident, result_hash=_h("result", result), n_obs=100, summary={"r": result}, seed=7, **kw)


# ------------------------------------------------------------------------------------------------- differential

def _call(fn):
    try:
        return ("ok", fn())
    except Exception as exc:                              # noqa: BLE001 - compared, never swallowed
        return ("raise", type(exc).__name__, str(exc))


def _answers(book, ids: list[str], keys: list[tuple]) -> dict:
    return {
        "len": len(book), "head": book.head, "looks": book.looks(),
        "records": book.records(), "by_type": {t: book.records(t) for t in TYPES_ALL},
        "unfinished": book.unfinished(), "suspended": _call(book.suspended_families),
        "result_of_record": {k: _call(lambda k=k: book.result_of_record(*k)) for k in keys},
        "superseded": [book.is_superseded(a) for a in ids],
        "active": [_call(lambda a=a: book.active_attempt(a)) for a in ids],
        "designated": book.designated_reserve_starts("B-1", "synthetic:scaling"),
        "summary": book.run_summary_payload(), "evaluations": book._evaluations(),
    }


def _random_step(rng: random.Random, ids: list[str], keys_seen: list):
    spec, data, w, res = rng.randrange(4), rng.randrange(3), rng.randrange(2), rng.randrange(3)
    ident = identity(spec, data, w)
    op = rng.choice(["start2", "start2", "start_legacy", "retry", "complete", "complete", "complete_unlinked",
                     "end", "append", "correction", "start2_bad_auth"])
    if op == "start2":
        return op, lambda b: b.start_evaluation(schema2(ident))
    if op == "start2_bad_auth":
        return op, lambda b: b.start_evaluation(schema2(ident, valid_auth=False))
    if op == "start_legacy":
        return op, lambda b: b.start_evaluation(legacy(ident))
    if op == "retry" and ids:
        a = rng.choice(ids)
        pick = rng.random()
        return op, lambda b: b.start_evaluation(_retry_payload(b, a, ident, pick), supersedes=a)
    if op in ("complete", "complete_unlinked"):
        a = rng.choice(ids) if ids and op == "complete" else None
        same = rng.random() < 0.8

        def go(b):
            base = ident
            if a is not None and same:
                start = next((r for r in b.records("evaluation_started") if r["hash"] == a), None)
                if start is not None:
                    base = {k: start["payload"][k] for k in L.IDENTITY_FIELDS if k in start["payload"]}
                    base = identity_from(base)
            return b.record_evaluation(**completion(base, res), attempt_id=a)
        return op, go
    if op == "end" and ids:
        a = rng.choice(ids)
        status, reason = rng.choice(["failed", "aborted"]), rng.choice(L.TERMINAL_REASONS)
        data_read = rng.choice([True, False, None])
        return op, lambda b: b.end_attempt(a, status=status, reason=reason, data_read=data_read)
    if op == "correction":
        n = rng.randrange(1, 4)
        return op, lambda b: b.correction(n, {"note": {"old": 1, "new": 2}}, "differential test")
    return "append", lambda b: b.append("screening_decision", {"spec": spec, "decision": "hold"})


def _retry_payload(b, a: str, ident: dict, pick: float) -> dict:
    start = next((r for r in b.records("evaluation_started") if r["hash"] == a), None)
    if start is None or pick > 0.9:
        return schema2(ident)                             # a retry that does not match: refused by both
    return {k: v for k, v in start["payload"].items() if k != "supersedes"}


def identity_from(p: dict) -> dict:
    """The keyword arguments of a completion for a start's identity (legacy starts lack some fields)."""
    full = identity(0)
    return {k: p.get(k, full[k]) for k in L.IDENTITY_FIELDS}


@pytest.mark.parametrize("seed", range(12))
def test_random_lifecycles_match_the_reference_ledger_exactly(tmp_path, seed):
    rng = random.Random(seed)
    new = L.Ledger(tmp_path / "new.jsonl", writer="w", protocol=PROTOCOL)
    ref = RL.Ledger(tmp_path / "ref.jsonl", writer="w", protocol=PROTOCOL)
    ids: list[str] = []
    keys = [(_h("spec", s), f"win-{w}") for s in range(4) for w in range(2)]
    for step in range(160):
        op, fn = _random_step(rng, ids, keys)
        got, want = _call(lambda: fn(new)), _call(lambda: fn(ref))
        assert got == want, (seed, step, op)
        if got[0] == "ok" and got[1]["type"] == "evaluation_started":
            ids.append(got[1]["hash"])
        if step % 20 == 0:
            assert _answers(new, ids, keys) == _answers(ref, ids, keys), (seed, step)
    assert (tmp_path / "new.jsonl").read_bytes() == (tmp_path / "ref.jsonl").read_bytes()
    assert _answers(new, ids, keys) == _answers(ref, ids, keys)
    # reopened, each implementation on the other's file
    re_new = L.Ledger(tmp_path / "ref.jsonl", writer="w", protocol=PROTOCOL)
    re_ref = RL.Ledger(tmp_path / "new.jsonl", writer="w", protocol=PROTOCOL)
    assert _answers(re_new, ids, keys) == _answers(re_ref, ids, keys) == _answers(ref, ids, keys)
    # the indexes rebuilt from the file are the indexes kept in step with the appends
    assert _index_state(re_new) == _index_state(new)
    # the strict reconciler, at the head and at earlier anchors, unscoped and scoped to a batch
    n = len(new)
    for cut in sorted({0, 1, n // 3, n // 2, n}):
        anchor = {"records": cut, "head": L.GENESIS if cut == 0 else new.records()[cut - 1]["hash"]}
        for batch in (None, "B-1", "B-2"):
            got = _call(lambda: AT.reconcile(ledger_path=new.path, ledger_anchor=anchor, batch=batch))
            want = _call(lambda: RA.reconcile(ledger_path=ref.path, ledger_anchor=anchor, batch=batch))
            assert got == want, (seed, cut, batch)


def _index_state(book) -> dict:
    return {k: (sorted(map(repr, v)) if isinstance(v, set) else v) for k, v in vars(book).items()
            if k.startswith("_")}


def test_the_differential_covers_every_outcome():
    """The random lifecycles above reach every record type the rules decide (else they would prove little)."""
    import tempfile
    from pathlib import Path
    seen = set()
    with tempfile.TemporaryDirectory() as d:
        for seed in range(12):
            rng = random.Random(seed)
            book = L.Ledger(Path(d) / f"{seed}.jsonl", writer="w", protocol=PROTOCOL)
            ids: list[str] = []
            for _ in range(160):
                _, fn = _random_step(rng, ids, [])
                out = _call(lambda: fn(book))
                if out[0] == "ok":
                    seen.add(out[1]["type"])
                    if out[1]["type"] == "evaluation_started":
                        ids.append(out[1]["hash"])
                    if out[1]["payload"].get("data_changed"):
                        seen.add("data_changed")
                    if out[1]["payload"].get("supersedes"):
                        seen.add("retry")
    assert {"evaluation", "rerun", "nondeterminism", "attempt_failed", "attempt_aborted", "data_changed",
            "retry", "correction"} <= seen


# ------------------------------------------------------------------------------------------------- adversarial

def _book(tmp_path, name="l.jsonl"):
    return L.Ledger(tmp_path / name, writer="w", protocol=PROTOCOL)


def _register(book, ident):
    return A.register_evaluation(book, identity=ident, windows=[_declared(ident)], caller="session",
                                 fence=FENCE).attempt_id


def _anchor(book):
    return {"records": len(book), "head": book.head}


def test_conflicting_results_are_never_hidden_by_the_index(tmp_path):
    book = _book(tmp_path)
    ident = identity(1)
    book.record_evaluation(**completion(ident, 0), attempt_id=_register(book, ident))
    assert book.record_evaluation(**completion(ident, 0), attempt_id=_register(book, ident))["type"] == "rerun"
    r = book.record_evaluation(**completion(ident, 1), attempt_id=_register(book, ident))
    assert r["type"] == "nondeterminism" and r["payload"]["first_result_hash"] == _h("result", 0)
    assert book.suspended_families() == {ident["family"]} and book.looks() == 1
    again = _book(tmp_path)                                # rebuilt from the file
    assert again.suspended_families() == {ident["family"]} and again.looks() == 1
    assert again.record_evaluation(**completion(ident, 0), attempt_id=_register(again, ident))["type"] == \
        "nondeterminism"                                   # after a conflict, never a rerun again


def test_records_written_around_the_index_are_seen_on_reopen(tmp_path):
    """Another writer appends a hash-valid completion with a conflicting result; this object's index does not know
    it, but the file does: the next ledger opened on it decides from it, and the reconciler reports the write."""
    from manhattan_attempt_fixtures import forge
    book = _book(tmp_path)
    ident = identity(2)
    a = _register(book, ident)
    book.record_evaluation(**completion(ident, 0), attempt_id=a)
    other = _book(tmp_path)
    forge(other, "evaluation", dict(completion(ident, 5), attempt_id=a, evidential_weight=0, reconstructed=False))
    reopened = _book(tmp_path)
    r = reopened.record_evaluation(**completion(ident, 0), attempt_id=_register(reopened, ident))
    assert r["type"] == "nondeterminism"                   # the forged conflicting result is on the key
    rep = AT.reconcile(ledger_path=reopened.path, ledger_anchor=_anchor(reopened))
    assert "duplicate_or_contradictory_terminal" in {v["code"] for v in rep["violations"]}
    assert rep == RA.reconcile(ledger_path=reopened.path, ledger_anchor=_anchor(reopened))


@pytest.mark.parametrize("forgery", ["escalated_start", "foreign_completion", "unknown_attempt", "double_terminal",
                                     "identity_mismatch"])
def test_forged_attempts_are_reported_by_the_streamed_reconciler(tmp_path, forgery):
    from manhattan_attempt_fixtures import forge
    book = _book(tmp_path)
    ident = identity(3)
    a = _register(book, ident)
    if forgery == "escalated_start":
        forge(book, "evaluation_started", dict(schema2(ident), role="reserve", designated=True))
        want = "invalid_identity_or_authorization"
    elif forgery == "foreign_completion":
        forge(book, "evaluation", dict(completion(identity(4), 0), attempt_id=a, evidential_weight=0,
                                       reconstructed=False))
        want = "identity_or_role_escalation"
    elif forgery == "unknown_attempt":
        forge(book, "evaluation", dict(completion(ident, 0), attempt_id="c" * 64, evidential_weight=0,
                                       reconstructed=False))
        want = "terminal_without_active_attempt"
    elif forgery == "double_terminal":
        book.end_attempt(a, status="failed", reason="execution_error", data_read=True)
        forge(book, "attempt_aborted", {"attempt_id": a, "reason": "interrupted", "data_read": True})
        want = "terminal_without_active_attempt"
    else:
        forge(book, "evaluation", dict(completion(ident, 0), attempt_id=a, evidential_weight=0,
                                       reconstructed=False, window=_window(1)))
        want = "identity_or_role_escalation"
    got = AT.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
    assert want in {v["code"] for v in got["violations"]}
    assert got == RA.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
    assert _call(lambda: _book(tmp_path).unfinished()) == _call(
        lambda: RL.Ledger(book.path, writer="w", protocol=PROTOCOL).unfinished())


def _lines(path):
    return path.read_bytes().splitlines(keepends=True)


@pytest.mark.parametrize("damage", ["edit_result", "drop_record", "swap_records", "truncate_tail", "not_utf8",
                                    "rehashed_rewrite", "appended_garbage", "unknown_type"])
def test_corrupted_ledgers_are_refused_exactly_as_before(tmp_path, damage):
    from manhattan_attempt_fixtures import forge
    book = _book(tmp_path)
    for s in range(3):
        ident = identity(s)
        book.record_evaluation(**completion(ident, s), attempt_id=_register(book, ident))
    anchor = _anchor(book)
    lines = _lines(book.path)
    if damage == "edit_result":
        lines[3] = lines[3].replace(_h("result", 1).encode(), _h("result", 2).encode())
    elif damage == "drop_record":
        del lines[2]
    elif damage == "swap_records":
        lines[1], lines[2] = lines[2], lines[1]
    elif damage == "truncate_tail":
        lines[-1] = lines[-1][:40]
    elif damage == "not_utf8":
        lines[2] = lines[2][:-2] + b"\xff\n"
    elif damage == "rehashed_rewrite":
        # an attacker rewrites the whole chain with a different result: every hash valid, the anchor is not
        recs = [json.loads(x) for x in lines]
        recs[3]["payload"]["result_hash"] = _h("result", 9)
        prev = L.GENESIS
        for r in recs:
            r["prev_hash"] = prev
            r["hash"] = L.record_hash(r)
            prev = r["hash"]
        lines = [(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode() for r in recs]
    elif damage == "appended_garbage":
        lines.append(b"{not json}\n")
    if damage == "unknown_type":
        rec = forge(book, "evaluation", {})               # hash-valid; then its type is changed and rehashed
        lines = _lines(book.path)
        rec["type"] = "invented"
        rec["hash"] = L.record_hash(rec)
        lines[-1] = (json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n").encode()
    book.path.write_bytes(b"".join(lines))
    opened = _call(lambda: _index_state(_book(tmp_path)))
    reference = _call(lambda: RL.Ledger(book.path, writer="w", protocol=PROTOCOL).records())
    assert opened[0] == reference[0]
    if opened[0] == "raise":
        assert opened == reference                         # the same refusal, word for word
    got = _call(lambda: AT.reconcile(ledger_path=book.path, ledger_anchor=anchor))
    assert got == _call(lambda: RA.reconcile(ledger_path=book.path, ledger_anchor=anchor))
    assert got[0] == "raise" or got[1]["violations"]
    if damage != "appended_garbage":
        assert opened[0] == "raise" or damage == "rehashed_rewrite"


@pytest.mark.parametrize("irregular", ["crlf", "blank_lines", "line_separator_in_string", "nbsp_line", "bom",
                                       "no_final_newline"])
def test_irregular_files_take_the_reference_path(tmp_path, irregular):
    """Inputs the streaming fast path does not cover are answered by ``verify_snapshot`` on the same bytes: the
    current ledger and reconciler accept exactly what the reference accepts, with the same records."""
    book = _book(tmp_path)
    ident = identity(5)
    a = _register(book, ident)
    note = "x y" if irregular == "line_separator_in_string" else "plain"
    book.append("screening_decision", {"note": note})
    book.record_evaluation(**completion(ident, 0), attempt_id=a)
    anchor = _anchor(book)
    raw = book.path.read_bytes()
    if irregular == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    elif irregular == "blank_lines":
        raw = raw.replace(b"\n", b"\n\n  \n")
    elif irregular == "line_separator_in_string":
        raw = raw.replace(b"\\u2028", "\u2028".encode())       # as a ledger written before the escaping fix
        assert "\u2028".encode() in raw
    elif irregular == "nbsp_line":
        raw = raw.replace(b"\n", b"\n\xc2\xa0\n", 1)
    elif irregular == "bom":
        raw = b"\xef\xbb\xbf" + raw
    elif irregular == "no_final_newline":
        raw = raw.rstrip(b"\n")
    book.path.write_bytes(raw)
    got = _call(lambda: _book(tmp_path).records())
    assert got == _call(lambda: RL.Ledger(book.path, writer="w", protocol=PROTOCOL).records())
    assert _call(lambda: AT.reconcile(ledger_path=book.path, ledger_anchor=anchor)) == \
        _call(lambda: RA.reconcile(ledger_path=book.path, ledger_anchor=anchor))


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85"])
def test_line_separators_in_payloads_are_written_escaped_and_reopen(tmp_path, separator):
    """The U+2028/U+2029/U+0085 ledger defect is fixed on the writer side (tests/test_manhattan_ledger_line_separators.py
    has the full set): the current ledger writes the character as a JSON escape, so the file reopens, reconciles and
    verifies, while main's writer (the reference) wrote it raw and could not reopen its own file. Both files hold
    the same records with the same hashes."""
    out = {}
    for name, M, R in (("new", L, AT), ("ref", RL, RA)):
        path = tmp_path / f"{name}.jsonl"
        book = M.Ledger(path, writer="w", protocol=PROTOCOL)
        book.append("screening_decision", {"note": f"a{separator}b"})
        book.append("screening_decision", {"note": "after"})
        anchor = {"records": len(book), "head": book.head}
        out[name] = (path.read_bytes(), _call(lambda: M.Ledger(path, writer="w", protocol=PROTOCOL).records()),
                     _call(lambda: R.reconcile(ledger_path=path, ledger_anchor=anchor)), M.verify(path), book.head)
    new, ref = out["new"], out["ref"]
    assert separator.encode() not in new[0] and separator.encode() in ref[0]
    assert new[1][0] == "ok" and new[2][0] == "ok" and new[3] == []
    assert ref[1][0] == "raise" and ref[2][0] == "raise" and ref[3]       # main's behaviour, for contrast
    assert new[4] == ref[4]                                               # the same chain: same hashes, same head
    assert new[1][1][0]["payload"]["note"] == f"a{separator}b"


def test_a_stale_ledger_object_cannot_fork_the_chain_unnoticed(tmp_path):
    first, second = _book(tmp_path), _book(tmp_path)
    second.append("screening_decision", {"by": "second"})
    first.append("screening_decision", {"by": "first"})   # appended on its stale head
    with pytest.raises(L.LedgerError, match="does not verify"):
        _book(tmp_path)
    with pytest.raises(L.LedgerError, match="does not verify"):
        RL.Ledger(first.path, writer="w", protocol=PROTOCOL)


def test_a_malformed_forged_evaluation_makes_the_rule_refuse_not_decide(tmp_path):
    """A record only a forged write can produce (an evaluation without a spec hash): the 4A-1a scan raised
    ``KeyError`` on it; the index refuses with ``LedgerError`` at the same rule and never classifies past it."""
    from manhattan_attempt_fixtures import forge
    book = _book(tmp_path)
    forge(book, "evaluation", {"window": _window(0), "designated": True})
    ident = identity(6)
    a = _register(book, ident)
    with pytest.raises(L.LedgerError, match="without a spec"):
        book.record_evaluation(**completion(ident, 0), attempt_id=a)
    with pytest.raises(KeyError):
        RL.Ledger(book.path, writer="w", protocol=PROTOCOL).record_evaluation(**completion(ident, 0), attempt_id=a)
    with pytest.raises(L.LedgerError):
        book.result_of_record(ident["spec_hash"], "win-0")
    assert len(_book(tmp_path)) == len(book)              # nothing was written


def test_every_candidate_keeps_its_own_auditable_attempt_and_outcome(tmp_path):
    book = _book(tmp_path)
    aids = {}
    for s in range(40):
        ident = identity(s, batch="B-7")
        aids[s] = _register(book, ident)
        if s % 7 == 0:
            book.end_attempt(aids[s], status="failed", reason="execution_error", data_read=True)
        else:
            book.record_evaluation(**completion(ident, s), attempt_id=aids[s])
    by_attempt = {r["payload"].get("attempt_id"): r for r in book.iter_records() if r["type"] != "evaluation_started"}
    for s, a in aids.items():
        r = by_attempt[a]
        assert r["type"] == ("attempt_failed" if s % 7 == 0 else "evaluation")
        if r["type"] == "evaluation":
            assert r["payload"]["spec_hash"] == _h("spec", s) and r["payload"]["result_hash"] == _h("result", s)
    rep = AT.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book), batch="B-7")
    assert rep["registered_executions"] == 40 and rep["completed"] == 34 and rep["failed"] == 6
    assert not rep["violations"] and rep["completed_evaluation_keys"] == 34


def test_records_are_held_as_their_verified_lines(tmp_path):
    book = _book(tmp_path)
    ident = identity(8)
    book.record_evaluation(**completion(ident, 0), attempt_id=_register(book, ident))
    lines = book.path.read_bytes().splitlines()
    assert list(book._lines) == lines and all(isinstance(x, bytes) for x in book._lines)
    assert book.records() == [json.loads(x) for x in lines]
    assert book.records() is not book.records() and book.records()[0] is not book.records()[0]


# ------------------------------------------------------------------------------------------------- fence memo

def _fence(rng: random.Random):
    reserve = {}
    if rng.random() < 0.6:
        s = date(2015, 1, 1) + timedelta(days=rng.randrange(0, 900))
        reserve[rng.choice(["d1", "d2"])] = (s, s + timedelta(days=rng.randrange(10, 400)))
    return roles.Fence(exploration_end=date(2016, 1, 1) + timedelta(days=rng.randrange(0, 1500)), reserve=reserve,
                       enabled=rng.random() < 0.5)


@pytest.mark.parametrize("seed", range(4))
def test_remembered_fence_decisions_equal_check_read(seed):
    rng = random.Random(seed)
    A._ALLOWED_READS.clear()
    for _ in range(400):
        fence = _fence(rng)
        start = date(2012, 1, 1) + timedelta(days=rng.randrange(0, 3000))
        end = start + timedelta(days=rng.randrange(0, 900))
        dw = A.DeclaredWindow(rng.choice(["w1", "w2"]), rng.choice(["d1", "d2", "d3"]), start, end, "exploration",
                              "evaluation", "e" * 64)
        caller = rng.choice(roles.CALLERS)
        freeze = rng.choice([None, date(2018, 6, 1), date(2021, 1, 1)])
        holding = rng.randrange(0, 4)
        want = _call(lambda: roles.check_read(caller, dw.domain, dw.start, dw.end, fence, freeze=freeze,
                                              holding=holding, token=None, window_id=dw.id))
        for _ in range(2):                                # the second call may be answered from the memo
            assert _call(lambda: A._allowed_role(caller, dw, fence=fence, freeze=freeze, holding=holding,
                                                 token=None)) == want
    assert A._ALLOWED_READS and all(v in (roles.EXPLORATION, roles.FORWARD) for v in A._ALLOWED_READS.values())


def test_the_memo_never_bypasses_a_replaced_check_or_a_changed_fence(monkeypatch):
    A._ALLOWED_READS.clear()
    dw = A.DeclaredWindow("w", "d1", date(2010, 1, 4), date(2012, 1, 4), "exploration", "evaluation", "e" * 64)
    reserve: dict = {}
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve=reserve, enabled=False)
    assert A._allowed_role("session", dw, fence=fence, freeze=None, holding=0, token=None) == roles.EXPLORATION
    reserve["d1"] = (date(2011, 1, 3), date(2013, 1, 3))  # the same Fence object, new content: decided anew
    with pytest.raises(roles.RoleError):
        A._allowed_role("session", dw, fence=fence, freeze=None, holding=0, token=None)
    calls = []

    def refuse(*a, **k):
        calls.append(a)
        raise roles.RoleError("replaced")
    monkeypatch.setattr(roles, "check_read", refuse)
    plain = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
    with pytest.raises(roles.RoleError, match="replaced"):
        A._allowed_role("session", dw, fence=plain, freeze=None, holding=0, token=None)
    assert calls


def test_reserve_reads_and_refusals_are_never_remembered(monkeypatch):
    A._ALLOWED_READS.clear()
    calls = []
    real = roles.check_read

    def counting(*a, **k):
        calls.append(k.get("token"))
        return real(*a, **k)
    monkeypatch.setattr(roles, "check_read", counting)
    dw = A.DeclaredWindow("w", "d1", date(2015, 1, 5), date(2015, 6, 5), "reserve", "evaluation", "e" * 64)
    fence = roles.Fence(exploration_end=date(2014, 1, 1), reserve={"d1": (date(2015, 1, 1), date(2015, 12, 31))},
                        enabled=True)
    token = roles.RunnerToken("B", "f" * 64, True, frozenset({("d1", "w")}), frozenset())
    for _ in range(3):
        assert A._allowed_role("runner", dw, fence=fence, freeze=None, holding=0, token=token) == roles.RESERVE
        with pytest.raises(roles.RoleError):
            A._allowed_role("session", dw, fence=fence, freeze=None, holding=0, token=None)
    assert len(calls) == 6 and not A._ALLOWED_READS


# ------------------------------------------- the memo after the independent security review (PR #100, 2026-11-20)

def _uncached(caller, dw, fence, freeze=None, holding=0):
    return _call(lambda: roles.check_read(caller, dw.domain, dw.start, dw.end, fence, freeze=freeze, holding=holding,
                                          token=None, window_id=dw.id))


def _cached(caller, dw, fence, freeze=None, holding=0):
    return _call(lambda: A._allowed_role(caller, dw, fence=fence, freeze=freeze, holding=holding, token=None))


@pytest.mark.parametrize("key", [1, True, None, 1.5])
def test_a_non_string_reserve_key_cannot_poison_the_reconciler(key):
    """Review finding 1: the fence used to be keyed by its JSON text, where the domain key 1 and "1" are equal. A
    registration under a fence whose reserve is keyed by the integer (``yaml.safe_load`` gives such keys) stored an
    allowed decision that then let the reconciler accept a recorded reserve window on the domain "1"."""
    A._ALLOWED_READS.clear()
    domain = json.dumps(key)                               # "1", "true", "null", "1.5"
    window = (date(2015, 1, 1), date(2016, 12, 31))
    dw = A.DeclaredWindow("w", domain, date(2015, 3, 2), date(2015, 6, 1), "exploration", "evaluation", "e" * 64)
    ident = {"window": {"id": "w", "start": "2015-03-02", "end": "2015-06-01"}, "role": "exploration",
             "data_hash": "e" * 64, "designated": False}
    auth = {"caller": "session", "windows": [dw.as_dict()], "freeze": None, "holding": 0, "token": None,
            "config": None, "fence": {"exploration_end": "2019-12-31", "reserve_enabled": True,
                                      "reserve_window": ["2015-01-01", "2016-12-31"]}}
    before = _call(lambda: A.check_recorded("screening", ident, auth))
    assert before[0] == "raise"
    poison = roles.Fence(exploration_end=date(2019, 12, 31), reserve={key: window}, enabled=True)
    A.check_declaration("screening", ident, (dw,), caller="session", fence=poison, freeze=None, holding=0, token=None)
    assert _call(lambda: A.check_recorded("screening", ident, auth)) == before


def test_only_exact_types_are_remembered():
    """Review findings 2 and 3: a window with extra elements, a list window, a date subclass that lies about its
    value, an int enabled flag or numpy holding are decided by check_read itself, never from the memo."""
    import numpy as np

    class Lying(date):
        def isoformat(self):
            return "2030-01-01"

    honest = (date(2015, 1, 1), date(2016, 12, 31))
    dw = A.DeclaredWindow("w", "d1", date(2015, 3, 2), date(2015, 6, 1), "exploration", "evaluation", "e" * 64)
    variants = [
        roles.Fence(date(2019, 12, 31), {"d1": honest + ("x",)}, True),
        roles.Fence(date(2019, 12, 31), {"d1": list(honest)}, True),
        roles.Fence(date(2019, 12, 31), {"d1": (Lying(2030, 1, 1), Lying(2030, 12, 31))}, True),
        roles.Fence(date(2019, 12, 31), {"d1": honest}, 1),
        roles.Fence(Lying(2019, 12, 31), {}, False),
    ]
    for fence in variants:
        A._ALLOWED_READS.clear()
        assert _cached("session", dw, fence) == _uncached("session", dw, fence)
        assert not A._ALLOWED_READS                        # never remembered
        assert _cached("session", dw, roles.Fence(date(2019, 12, 31), {"d1": honest}, True)) == \
            _uncached("session", dw, roles.Fence(date(2019, 12, 31), {"d1": honest}, True))
    A._ALLOWED_READS.clear()
    plain = roles.Fence(date(2019, 12, 31), {}, False)
    assert _cached("session", dw, plain, holding=np.int64(0)) == _uncached("session", dw, plain, holding=np.int64(0))
    assert not A._ALLOWED_READS


@pytest.mark.parametrize("setting", ["MAX_READ_DAYS", "NO_DATA", "CALLERS"])
def test_a_tightened_roles_setting_is_never_bypassed(monkeypatch, setting):
    """Review finding 4: AttemptContext re-checks its windows through the memo; a setting tightened after a cached
    decision must refuse as check_read does."""
    A._ALLOWED_READS.clear()
    dw = A.DeclaredWindow("w", "d1", date(2010, 1, 4), date(2012, 1, 4), "exploration", "evaluation", "e" * 64)
    fence = roles.Fence(date(2019, 12, 31), {}, False)
    assert _cached("explorer", dw, fence) == ("ok", roles.EXPLORATION)
    new = {"MAX_READ_DAYS": 10, "NO_DATA": roles.NO_DATA + ("explorer",),
           "CALLERS": tuple(c for c in roles.CALLERS if c != "explorer")}[setting]
    monkeypatch.setattr(roles, setting, new)
    assert _cached("explorer", dw, fence)[0] == "raise"
    assert _cached("explorer", dw, fence) == _uncached("explorer", dw, fence)


def test_the_decision_is_made_on_the_keyed_snapshot(monkeypatch):
    """Review finding 5: the reserve mapping is read once; the decision is made on a fence built from the same
    values as the key, so a mapping changed while check_read runs cannot store one content's answer under
    another's key."""
    A._ALLOWED_READS.clear()
    dw = A.DeclaredWindow("w", "d1", date(2015, 3, 2), date(2015, 6, 1), "exploration", "evaluation", "e" * 64)
    reserve: dict = {}
    fence = roles.Fence(date(2019, 12, 31), reserve, True)
    seen = []
    real = roles.check_read

    def mutating(caller, domain, start, end, f, **kw):
        reserve["d1"] = (date(2015, 1, 1), date(2016, 12, 31))    # another thread, mid-call
        seen.append(f is fence)
        return real(caller, domain, start, end, f, **kw)
    monkeypatch.setattr(roles, "check_read", mutating)
    assert _cached("session", dw, fence) == ("ok", roles.EXPLORATION)   # decided on the snapshot: no reserve
    assert seen == [False]
    monkeypatch.setattr(roles, "check_read", real)
    fresh = roles.Fence(date(2019, 12, 31), {"d1": (date(2015, 1, 1), date(2016, 12, 31))}, True)
    assert _cached("session", dw, fresh) == _uncached("session", dw, fresh)
    assert _cached("session", dw, fresh)[0] == "raise"


def test_a_key_that_cannot_be_built_is_decided_not_refused():
    """Review finding 6: an error while building the key (a malformed window on another domain) falls back to
    check_read, which allows what it allows; the memo never adds a refusal of its own."""
    A._ALLOWED_READS.clear()
    dw = A.DeclaredWindow("w", "d1", date(2010, 1, 4), date(2012, 1, 4), "exploration", "evaluation", "e" * 64)
    fence = roles.Fence(date(2019, 12, 31), {"other": (date(2015, 1, 1),)}, True)
    assert _cached("session", dw, fence) == _uncached("session", dw, fence) == ("ok", roles.EXPLORATION)
