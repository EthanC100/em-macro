"""Phase 4B: binding authorization of protected windows and the Ledger side of attempt accounting.

Deterministic synthetic adversarial fixtures only: hand-made prices, fabricated fences, tokens and valid-format
hashes. No real data, no simulation runs. docs/manhattan/BINDING_ACCOUNTING.md describes what is enforced.
"""
from __future__ import annotations

import ast
import dataclasses
import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from manhattan import access, attempts, ledger as L, roles
from manhattan.engine import backtest, evaluate, lookahead, pit
from manhattan.engine.backtest import Instrument, Strategy
from manhattan.ops import data as D

import manhattan_attempt_fixtures as F

ROOT = Path(__file__).resolve().parents[1]
DOM = "test"
EXPLORE_END = date(2009, 12, 31)
RES = (date(2010, 1, 4), date(2010, 3, 31))
RESERVE_FENCE = F.reserve_fence(DOM, *RES, EXPLORE_END)
FWD_FENCE = roles.Fence(exploration_end=EXPLORE_END, reserve={}, enabled=False)
FREEZE = date(2010, 1, 3)


def store(start=date(2009, 11, 2), n=60, synthetic=False, reconstructed=False) -> pit.PitStore:
    s = pit.PitStore(synthetic=synthetic)
    days = np.array([d for d in np.arange(np.datetime64(start), np.datetime64(start) + np.timedelta64(120, "D"))
                     if np.is_busday(d)][:n], dtype="datetime64[D]")
    s.add("A", days, 100.0 + np.arange(days.size), lag_days=0, reconstructed=reconstructed)
    return s


def hold():
    return Strategy((Instrument("A", "A"),), lambda v: {"A": 1.0}, rebalance="D", lag=0)


def book(tmp_path, name="ledger.jsonl") -> L.Ledger:
    return L.Ledger(tmp_path / name, writer="fixture", protocol="0" * 64)


def anchor(b: L.Ledger) -> dict:
    return {"records": len(b), "head": b.head}


def reserve_ctx(b, st, wid="test:reserve", start=date(2010, 1, 4), end=date(2010, 1, 15), **kw):
    return F.register(b, st, domain=DOM, start=start, end=end, role="reserve", window_id=wid,
                      fence=RESERVE_FENCE, token=F.reserve_token(DOM, wid), designated=True, **kw)


def forward_ctx(b, st, start=date(2010, 1, 4), end=date(2010, 1, 15), **kw):
    return F.register(b, st, domain=DOM, start=start, end=end, role="forward", fence=FWD_FENCE, freeze=FREEZE,
                      **kw)


# ------------------------------------------------------------------ unauthorized reserve and forward access

def test_reserve_read_needs_a_registered_attempt_even_with_a_valid_token():
    st = store()
    wid = "test:reserve"
    reader = pit.Reader(st, caller="runner", domain=DOM, fence=RESERVE_FENCE, token=F.reserve_token(DOM, wid),
                        window_id=wid)
    assert roles.check_read("runner", DOM, date(2010, 1, 4), date(2010, 1, 15), RESERVE_FENCE,
                            token=F.reserve_token(DOM, wid), window_id=wid) == "reserve"   # the fence allows it
    with pytest.raises(pit.AccessError, match="registered attempt"):
        reader.window(date(2010, 1, 4), date(2010, 1, 15))


def test_forward_read_needs_a_registered_attempt():
    st = store()
    reader = pit.Reader(st, caller="runner", domain=DOM, fence=FWD_FENCE, freeze=FREEZE)
    with pytest.raises(pit.AccessError):
        reader.window(date(2010, 1, 4), date(2010, 1, 15))


def test_existing_role_fences_still_refuse_first():
    st = store()
    for caller in ("session", "explorer"):
        with pytest.raises(roles.RoleError):
            pit.Reader(st, caller=caller, domain=DOM, fence=RESERVE_FENCE).window(date(2010, 1, 4), date(2010, 1, 15))
    with pytest.raises(roles.RoleError):                         # a token that does not name this window
        pit.Reader(st, caller="runner", domain=DOM, fence=RESERVE_FENCE, token=F.reserve_token(DOM, "other"),
                   window_id="test:reserve").window(date(2010, 1, 4), date(2010, 1, 15))


def test_registration_cannot_escalate_past_the_fence(tmp_path):
    b, st = book(tmp_path), store()
    with pytest.raises(roles.RoleError):                         # reserve without a token
        F.register(b, st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="reserve",
                   fence=RESERVE_FENCE)
    with pytest.raises(pit.AccessError, match="declared role"):  # forward dates declared as exploration
        F.register(b, st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="exploration",
                   fence=FWD_FENCE, freeze=FREEZE)
    with pytest.raises(roles.RoleError):                         # forward without a freeze
        F.register(b, st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="forward", fence=FWD_FENCE)
    with pytest.raises(pit.AccessError):                         # a session cannot hold a protected attempt
        F.register(b, st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="forward",
                   fence=FWD_FENCE, freeze=FREEZE, caller="session")
    assert len(b) == 0                                           # nothing was written


def test_an_exploration_attempt_cannot_open_reserve_or_forward_dates(tmp_path):
    b, st = book(tmp_path), store()
    ctx = F.register(b, st, domain=DOM, start=date(2009, 11, 2), end=date(2009, 12, 31), role="exploration",
                     fence=RESERVE_FENCE, caller="session")
    wid = "test:reserve"
    reader = pit.Reader(st, caller="runner", domain=DOM, fence=RESERVE_FENCE, token=F.reserve_token(DOM, wid),
                        window_id=wid, attempt=ctx)
    with pytest.raises(pit.AccessError):
        reader.window(date(2010, 1, 4), date(2010, 1, 15))
    with pytest.raises(pit.AccessError):                         # its own dates, but read by another caller
        reader.window(date(2009, 11, 2), date(2009, 12, 31))
    w = pit.Reader(st, caller="session", domain=DOM, fence=RESERVE_FENCE, attempt=ctx).window(
        date(2009, 11, 2), date(2009, 12, 31))
    assert w.attempt_id == ctx.attempt_id and w.purpose == "evaluation"


# ------------------------------------------------------------------ direct and alternate paths

def test_windows_cannot_be_constructed_or_copied():
    st = store()
    with pytest.raises(pit.AccessError):
        pit.Window(st, date(2010, 1, 4), date(2010, 1, 15), "forward", DOM, "runner")
    with pytest.raises(pit.AccessError):
        pit.Window(st, date(2010, 1, 4), date(2010, 1, 15), "exploration", DOM, "session", _seal="f" * 64)
    w = pit.Reader(st, caller="session", domain=DOM, fence=FWD_FENCE).window(date(2009, 11, 2), date(2009, 12, 31))
    for change in ({"role": "forward"}, {"end": date(2010, 1, 15)}, {"attempt_id": "a" * 64},
                   {"purpose": "evaluation"}, {"_store": store()}):
        with pytest.raises(pit.AccessError):
            dataclasses.replace(w, **change)


def test_forward_adapter_needs_a_forward_observation_attempt(tmp_path):
    st = store()
    with pytest.raises(pit.AccessError):                         # the pre-4B call shape
        D.forward_window(st, DOM, date(2009, 11, 2), date(2010, 1, 15))
    ctx = forward_ctx(book(tmp_path), st)
    with pytest.raises(pit.AccessError):                         # an engine attempt is not the R-1 adapter
        D.forward_window(ctx, st)


def test_diagnostic_windows_are_synthetic_only_and_never_evidence(tmp_path):
    with pytest.raises(pit.AccessError):
        pit.diagnostic_window(store(), date(2010, 1, 4), date(2010, 1, 15), role="forward", domain=DOM)
    syn = store(synthetic=True)
    w = pit.diagnostic_window(syn, date(2010, 1, 4), date(2010, 1, 15), role="forward", domain=DOM)
    assert backtest.run(w, hold()).returns.size > 0             # capacity/timing diagnostics keep working
    with pytest.raises(pit.AccessError):
        evaluate.evaluate(w, hold(), ledger=book(tmp_path), **F.spec_kwargs(), log_path=tmp_path / "log.csv")


def test_attempt_contexts_come_from_registration_only():
    with pytest.raises(pit.AccessError):
        access.AttemptContext(_key=object(), backend=None, attempt_id="a" * 64, kind="engine_evaluation",
                              identity={}, windows=(), caller="runner", fence=FWD_FENCE, freeze=None, holding=0,
                              token=None)


def _refs(tree: ast.AST) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.ImportFrom):
            out.update(a.name for a in node.names)
    return out


# Who may touch each private access path (BINDING_ACCOUNTING.md section 1). Adding a module here is a reviewable
# decision, not a refactor.
ALLOWED = {
    "_open_window": {"manhattan/engine/pit.py", "manhattan/access.py"},
    "_SEAL_KEY": {"manhattan/engine/pit.py"},
    "_seal": {"manhattan/engine/pit.py"},
    "_CTX_KEY": {"manhattan/access.py"},
    "_as_of": {"manhattan/engine/pit.py"},
    "_store": {"manhattan/engine/pit.py", "manhattan/access.py"},
    "_value": {"manhattan/engine/pit.py", "manhattan/engine/lookahead.py"},
    "_period": {"manhattan/engine/pit.py", "manhattan/engine/lookahead.py"},
    "diagnostic_window": {"manhattan/engine/pit.py", "manhattan/ops/capacity.py"},
    "forward_window": {"manhattan/ops/data.py", "manhattan/ops/runner.py", "manhattan/access.py"},
    "record_evaluation": {"manhattan/ledger.py", "manhattan/engine/evaluate.py"},
    "Window": {"manhattan/engine/pit.py", "manhattan/engine/backtest.py", "manhattan/engine/evaluate.py",
               "manhattan/ops/data.py", "manhattan/factors/reproduce.py", "manhattan/access.py"},
}


def test_private_access_paths_are_used_only_where_allowed():
    found: dict[str, set[str]] = {k: set() for k in ALLOWED}
    for path in sorted((ROOT / "manhattan").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        refs = _refs(ast.parse(path.read_text(encoding="utf-8")))
        for name in ALLOWED:
            if name in refs:
                found[name].add(rel)
    bad = {k: sorted(v - ALLOWED[k]) for k, v in found.items() if v - ALLOWED[k]}
    assert bad == {}
    # and nothing outside pit.py calls the Window constructor (its seal would fail anyway)
    for path in sorted((ROOT / "manhattan").rglob("*.py")):
        if path.name == "pit.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                assert name != "Window", path


# ------------------------------------------------------------------ identities

@pytest.mark.parametrize("field", L.IDENTITY_FIELDS)
def test_missing_identity_field_registers_nothing(tmp_path, field):
    b, st = book(tmp_path), store()
    ident = F.identity(st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="forward")
    del ident[field]
    with pytest.raises((L.LedgerError, pit.AccessError, KeyError)):
        access.register_evaluation(b, identity=ident, windows=F.declared(st, domain=DOM, start=date(2010, 1, 4),
                                                                         end=date(2010, 1, 15), role="forward"),
                                   caller="runner", fence=FWD_FENCE, freeze=FREEZE)
    assert len(b) == 0


@pytest.mark.parametrize("field,value", [
    ("executable", ""), ("batch", None), ("role", "admin"), ("channel", "secret"), ("designated", 1),
    ("spec_hash", "x" * 64), ("data_hash", "A" * 64), ("window", {"id": "w"}),
    ("code_version", {"commit": "unknown", "engine_sha256": "b" * 64}),
    ("code_version", {"commit": "0" * 40, "engine_sha256": "b" * 64}),
    ("code_version", {"commit": "a" * 40}), ("code_version", {"commit": "a" * 7, "tree": "b" * 40}),
])
def test_malformed_identity_registers_nothing(tmp_path, field, value):
    b, st = book(tmp_path), store()
    ident = F.identity(st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="forward")
    ident[field] = value
    with pytest.raises((L.LedgerError, pit.AccessError)):
        access.register_evaluation(b, identity=ident, windows=F.declared(st, domain=DOM, start=date(2010, 1, 4),
                                                                         end=date(2010, 1, 15), role="forward"),
                                   caller="runner", fence=FWD_FENCE, freeze=FREEZE)
    assert len(b) == 0


def test_declared_windows_must_match_identity_and_data(tmp_path):
    b, st = book(tmp_path), store()
    ident = F.identity(st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="forward")
    other = F.declared(st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 20), role="forward")
    wrong_data = [access.DeclaredWindow(f"{DOM}:2010-01-04:2010-01-15", DOM, date(2010, 1, 4), date(2010, 1, 15),
                                        "forward", "evaluation", "e" * 64)]
    warm = [access.DeclaredWindow("w", DOM, date(2009, 12, 1), date(2010, 1, 3), "forward", "signal_warmup",
                                  st.data_hash())]
    for windows in (other, wrong_data, F.declared(st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15),
                                                  role="forward") + warm, []):
        with pytest.raises(pit.AccessError):
            access.register_evaluation(b, identity=ident, windows=windows, caller="runner", fence=FWD_FENCE,
                                       freeze=FREEZE)
    assert len(b) == 0


def test_data_identity_is_checked_when_opening_and_while_reading(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    with pytest.raises(pit.AccessError, match="data identity"):
        ctx.window(store(n=59))                                   # a different store
    w = ctx.window(st)
    st.add("B", ["2010-01-05"], [1.0], lag_days=0)                # the store changes after authorization
    with pytest.raises(pit.PitError, match="changed"):
        w.as_of("A", date(2010, 1, 6))
    with pytest.raises(pit.AccessError):
        ctx.window(st)
    open_w = pit.Reader(st, caller="session", domain=DOM, fence=FWD_FENCE).window(date(2009, 11, 2),
                                                                                   date(2009, 12, 31))
    st.add("C", ["2009-12-01"], [1.0], lag_days=0)
    assert open_w.as_of("A", date(2009, 12, 31))[1].size > 0      # open exploration windows keep their behaviour


def test_a_tampered_lookahead_copy_cannot_be_opened_under_the_attempt(tmp_path):
    st = store()
    ctx = forward_ctx(book(tmp_path), st)
    with pytest.raises(pit.AccessError, match="data identity"):
        ctx.window(lookahead.tampered_after(st, date(2010, 1, 6)))


# ------------------------------------------------------------------ escalation between registration and completion

def test_completion_cannot_escalate_designation_or_identity(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    w = ctx.window(st)
    with pytest.raises(pit.AccessError, match="registered identity"):
        evaluate.evaluate(w, hold(), ledger=b, **F.spec_kwargs(designated=True), attempt=ctx)
    assert b.records()[-1]["type"] == "attempt_failed" and b.records()[-1]["payload"] == {
        "attempt_id": ctx.attempt_id, "reason": "validation_error", "data_read": False}
    with pytest.raises(pit.AccessError):                          # a failed attempt opens nothing more
        ctx.window(st)


def test_storage_api_refuses_escalated_or_implicit_completion(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    ident = ctx.identity
    base = dict(executable=ident["executable"], variant=ident["variant"], hypothesis=ident["hypothesis"],
                family=ident["family"], batch=ident["batch"], channel=ident["channel"], window=ident["window"],
                spec_hash=ident["spec_hash"], data_hash=ident["data_hash"], code_version=ident["code_version"],
                result_hash="c" * 64, n_obs=1, summary={}, seed=0)
    with pytest.raises(L.LedgerError, match="identity"):
        b.record_evaluation(**base, role="reserve", designated=True, attempt_id=ctx.attempt_id)
    with pytest.raises(L.LedgerError, match="own attempt_id"):
        b.record_evaluation(**base, role="forward", designated=False)
    assert b.records()[-1]["type"] == "evaluation_started"


def test_wrong_ledger_or_running_code_is_refused(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    with pytest.raises(pit.AccessError, match="different ledger"):
        evaluate.evaluate(ctx.window(st), hold(), ledger=book(tmp_path, "other.jsonl"), **F.spec_kwargs(),
                          attempt=ctx)
    ctx2 = forward_ctx(b, st, end=date(2010, 1, 14))
    with pytest.raises(pit.AccessError):                          # the code that runs is not the code registered
        evaluate.evaluate(ctx2.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx2,
                          version={"commit": "a" * 40, "engine_sha256": "b" * 64})
    with pytest.raises(pit.AccessError):                          # a protected window without its attempt
        evaluate.evaluate(forward_ctx(b, st, end=date(2010, 1, 13)).window(st), hold(), ledger=b, **F.spec_kwargs())


# ------------------------------------------------------------------ the lifecycle, crashes and recovery

def test_forward_evaluation_end_to_end_reconciles(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    result, rec = evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    assert rec["type"] == "evaluation" and rec["payload"]["attempt_id"] == ctx.attempt_id
    assert rec["payload"]["evidential_weight"] == 1 and ctx.data_read and not ctx.active()
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"] and r["violations"] == []
    assert (r["registered_executions"], r["completed"], r["completed_evaluation_keys"],
            r["independent_statistical_tests"]) == (1, 1, 1, None)


def test_reserve_designated_evaluation_and_its_report(tmp_path):
    b, st = book(tmp_path), store()
    ctx = reserve_ctx(b, st)
    _, rec = evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(designated=True), attempt=ctx)
    assert rec["payload"]["evidential_weight"] == 1
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"] and r["designated_reserve_completions"] == {"AB-0001|test": 1}
    reconstructed = store(reconstructed=True)                     # Q019/PIT: no reconstructed reserve evidence
    ctx2 = reserve_ctx(b, reconstructed, wid="test:reserve2")
    with pytest.raises(pit.PitError, match="reconstructed"):
        evaluate.evaluate(ctx2.window(reconstructed), hold(), ledger=b, **F.spec_kwargs(designated=True),
                          attempt=ctx2)


def test_crash_after_registration_then_retry(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    del ctx, b                                                    # the process dies: nothing but the file remains
    b = book(tmp_path)
    (start,) = b.unfinished()
    assert start["payload"]["attempt_schema"] == 2
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert not r["access_reconciled"] and r["unfinished"] == 1
    assert {"code": "missing_terminal", "store": "ledger", "seq": 1} in r["violations"]
    retry = forward_ctx(b, st, supersedes=start["hash"])
    evaluate.evaluate(retry.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=retry)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"] and (r["registered_executions"], r["retries"], r["superseded_interrupted"],
                                       r["completed"], r["completed_evaluation_keys"]) == (2, 1, 1, 1, 1)


def test_retry_must_repeat_the_identity_and_cannot_target_a_finished_attempt(tmp_path):
    b, st = book(tmp_path), store()
    first = forward_ctx(b, st)
    with pytest.raises(L.LedgerError):
        forward_ctx(b, st, end=date(2010, 1, 14), supersedes=first.attempt_id)
    evaluate.evaluate(first.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=first)
    with pytest.raises(L.LedgerError):
        forward_ctx(b, st, supersedes=first.attempt_id)


def test_crash_during_result_commit_is_recovered_without_losing_the_start(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    lines = b.path.read_bytes().splitlines(keepends=True)
    b.path.write_bytes(b"".join(lines[:-1]) + lines[-1][: len(lines[-1]) // 2])   # the completion was cut short
    with pytest.raises(L.LedgerError):
        book(tmp_path)
    report = L.recover_torn_tail(b.path)
    assert report["status"] == "torn_tail_quarantined" and (tmp_path / report["quarantine"]).exists()
    b = book(tmp_path)
    (start,) = b.unfinished()
    retry = forward_ctx(b, st, supersedes=start["hash"])
    evaluate.evaluate(retry.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=retry)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"] and r["completed"] == 1 and r["retries"] == 1


def test_torn_tail_recovery_never_removes_a_complete_or_mid_file_record(tmp_path):
    b, st = book(tmp_path), store()
    forward_ctx(b, st)
    forward_ctx(b, st, end=date(2010, 1, 14))
    assert L.recover_torn_tail(b.path) == {"status": "clean"}
    data = b.path.read_bytes()
    b.path.write_bytes(data[:-1])                                 # a complete record that lost its newline
    assert L.recover_torn_tail(b.path)["status"] == "newline_restored" and b.path.read_bytes() == data
    lines = data.splitlines(keepends=True)
    for damaged in (lines[0][:20] + lines[1][:-1],                # a fragment, then a whole record: not torn
                    lines[0] + b'{"hash":"' + b"0" * 30 + b'","seq":7,'):   # a fragment of the wrong record
        b.path.write_bytes(damaged)
        with pytest.raises(L.LedgerError):
            L.recover_torn_tail(b.path)
        assert b.path.read_bytes() == damaged                     # nothing was removed


def test_failures_are_classified_and_never_completed(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)

    def boom(view):
        view.get("A")
        raise RuntimeError("private value 0.123456 must not be recorded")

    bad = Strategy((Instrument("A", "A"),), boom, rebalance="D", lag=0)
    with pytest.raises(RuntimeError):
        evaluate.evaluate(ctx.window(st), bad, ledger=b, **F.spec_kwargs(), attempt=ctx)
    end = b.records()[-1]
    assert end["type"] == "attempt_failed" and end["payload"] == {
        "attempt_id": ctx.attempt_id, "reason": "execution_error", "data_read": True}
    assert "0.123456" not in b.path.read_text()
    ctx2 = forward_ctx(b, st, end=date(2010, 1, 14))
    ctx2.abort("cancelled")                                        # aborted with an unread window
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert (r["completed"], r["failed"], r["aborted"], r["completed_evaluation_keys"]) == (0, 1, 1, 0)
    assert r["terminals_by_data_read"]["failed_read"] == 1 and r["terminals_by_data_read"]["aborted_unread"] == 1
    assert r["access_reconciled"]


def test_ledger_lifecycle_queries_do_not_rescan(tmp_path, monkeypatch):
    b, st = book(tmp_path), store()
    ctxs = [forward_ctx(b, st, end=date(2010, 1, 5 + i)) for i in range(5)]
    monkeypatch.setattr(L.Ledger, "unfinished", lambda self: pytest.fail("rescanned"))
    monkeypatch.setattr(L.Ledger, "records", lambda self, t=None: pytest.fail("rescanned"))
    for c in ctxs:
        assert c.active()
        c.fail("execution_error")


# ------------------------------------------------------------------ history, anchors and forgery

@pytest.mark.parametrize("damage", ["delete", "alter", "truncate", "replace"])
def test_deleted_or_altered_history_is_detected(tmp_path, damage):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    a = anchor(b)
    rows = b.path.read_text().splitlines()
    if damage == "delete":
        del rows[0]
    elif damage == "truncate":
        rows.pop()
    elif damage == "alter":
        r = json.loads(rows[1]); r["payload"]["evidential_weight"] = 0; rows[1] = json.dumps(r)
    else:
        other = book(tmp_path, "other.jsonl")
        forward_ctx(other, st)
        rows = other.path.read_text().splitlines()
    b.path.write_text("\n".join(rows) + "\n")
    with pytest.raises(attempts.ReconciliationError):
        attempts.reconcile(ledger_path=b.path, ledger_anchor=a)


@pytest.mark.parametrize("bad", [None, {}, {"records": 1}, {"records": -1, "head": "a" * 64},
                                 {"records": True, "head": "a" * 64}, {"records": 1, "head": "A" * 64},
                                 {"records": 99, "head": "a" * 64}, {"records": 1, "head": "a" * 64}])
def test_external_anchor_failure(tmp_path, bad):
    b, st = book(tmp_path), store()
    forward_ctx(b, st)
    with pytest.raises(attempts.ReconciliationError):
        attempts.reconcile(ledger_path=b.path, ledger_anchor=bad)
    with pytest.raises(attempts.ReconciliationError):
        attempts.reconcile(ledger_path=tmp_path / "missing.jsonl", ledger_anchor=anchor(b))


def test_records_after_the_anchor_are_outside_the_boundary(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    a = anchor(b)
    forward_ctx(b, st, end=date(2010, 1, 14))                       # after the batch boundary
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=a)
    assert r["access_reconciled"] and r["boundary"]["ledger"]["beyond"] == 1 and r["registered_executions"] == 1


def test_evidential_weight_inconsistency_is_reported(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    _, rec = evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    ctx2 = forward_ctx(b, st, end=date(2010, 1, 14))
    forged = {**rec["payload"], "attempt_id": ctx2.attempt_id, "window": ctx2.identity["window"],
              "reconstructed": True}                               # weight 1 kept although reconstructed
    b.append("evaluation", forged)                                 # hash-valid: a writer bug or forgery
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert not r["access_reconciled"]
    assert [v["code"] for v in r["violations"]] == ["evidential_weight_mismatch"]


def test_unregistered_protected_evaluations_and_forged_authorizations(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    ident = ctx.identity
    b.record_evaluation(executable=ident["executable"], variant=ident["variant"], hypothesis=ident["hypothesis"],
                        family=ident["family"], batch="AB-0001", channel="blind", role="reserve",
                        window={"id": "x", "start": "2010-01-04", "end": "2010-01-05", "frequency": "daily"},
                        designated=True, spec_hash="a" * 64, data_hash="d" * 64, code_version=ident["code_version"],
                        result_hash="c" * 64, n_obs=1, summary={}, seed=0)   # the legacy storage API
    start = b.records("evaluation_started")[0]["payload"]
    forged = json.loads(json.dumps(start))
    forged["role"] = "exploration"                                 # forward dates relabelled exploration
    for w in forged["authorization"]["windows"]:
        w["role"] = "exploration"
    b.append("evaluation_started", forged)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    codes = sorted(v["code"] for v in r["violations"])
    assert "unregistered_protected_evaluation" in codes and "invalid_identity_or_authorization" in codes
    assert not r["access_reconciled"]


def test_legacy_records_stay_readable_but_are_never_certified(tmp_path):
    from test_manhattan_attempts import ev
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    b.record_evaluation(**ev(), attempt_id=a["hash"])
    assert attempts.reconcile_lifecycle(b.path, anchor=b.head)["completed"] == 1   # 4A-1a audit still reads it
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["violations"] == [] and r["legacy"]["starts"] == 1 and not r["access_reconciled"]


# ------------------------------------------------------------------ legitimate exploration

def test_exploration_stays_open_and_unregistered_exploration_is_not_a_violation(tmp_path):
    b, st = book(tmp_path), store()
    w = pit.Reader(st, caller="session", domain=DOM, fence=FWD_FENCE).window(date(2009, 11, 2), date(2009, 12, 31))
    _, rec = evaluate.evaluate(w, hold(), ledger=b, **F.spec_kwargs(), log_path=tmp_path / "variants.csv")
    assert rec["payload"]["evidential_weight"] == 0 and "attempt_id" not in rec["payload"]
    other = {k: {**v, "fixture": "second"} for k, v in F.SPECS.items()}
    ctx = F.register(b, st, domain=DOM, start=date(2009, 11, 2), end=date(2009, 11, 30), role="exploration",
                     fence=FWD_FENCE, caller="session", specs=other)
    w2 = pit.Reader(st, caller="session", domain=DOM, fence=FWD_FENCE, attempt=ctx).window(date(2009, 11, 2),
                                                                                           date(2009, 11, 30))
    _, rec2 = evaluate.evaluate(w2, hold(), ledger=b, **F.spec_kwargs(other), attempt=ctx,
                                log_path=tmp_path / "variants.csv")
    assert rec2["payload"]["attempt_id"] == ctx.attempt_id
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"] and r["legacy"]["unlinked_exploration"] == 1 and r["completed"] == 1


def test_exploration_cutoff_is_unchanged_for_open_reads():
    fence = roles.Fence.from_config(__import__("manhattan.config", fromlist=["load"]).load())
    st = store(start=date(2019, 11, 1))
    with pytest.raises(roles.RoleError):
        pit.Reader(st, caller="session", domain=DOM, fence=fence).window(date(2019, 12, 2), date(2020, 1, 3))
