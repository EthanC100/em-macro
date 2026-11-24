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


def reserve_ctx(b, st, wid="test:reserve", start=date(2010, 1, 4), end=date(2010, 1, 15), designated=True, **kw):
    return F.register(b, st, domain=DOM, start=start, end=end, role="reserve", window_id=wid,
                      fence=RESERVE_FENCE, token=F.reserve_token(DOM, wid), designated=designated, **kw)


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
    """Every name a module defines, imports, references as an attribute or a name, or spells as an exact string
    constant (``getattr(pit, "_open_window")``)."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            out.update(a.name.rsplit(".", 1)[-1] for a in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


# Who may touch each private access path (BINDING_ACCOUNTING.md section 1). Adding a module here is a reviewable
# decision, not a refactor. Names are the access-control capabilities and the raw writers behind them.
PIT, ACCESS, LEDGER, STORE = ("manhattan/engine/pit.py", "manhattan/access.py", "manhattan/ledger.py",
                              "manhattan/ops/store.py")
EVALUATE, RUNNER = "manhattan/engine/evaluate.py", "manhattan/ops/runner.py"
# PR-2 (S17 C1, C2): the freeze check's trust and the equities gate's minting, marking and unchecked readers
EQ_FREEZE, EQ_REG = "manhattan/freeze.py", "manhattan/equities/registration.py"
EQ_SYN, EQ_TC = "manhattan/equities/synthetic.py", "manhattan/equities/track_compare.py"
ALLOWED = {
    # pit: minting, sealing and the per-process grant registry
    "_open_window": {PIT, ACCESS}, "_SEAL_KEY": {PIT}, "_seal": {PIT}, "_GRANTS": {PIT}, "_fields": {PIT},
    "_guard": {PIT}, "_Meter": {PIT, ACCESS}, "_meter": {PIT, ACCESS}, "_open_read": {PIT, ACCESS},
    "_as_of": {PIT}, "_store": {PIT, ACCESS},
    "_value": {PIT, "manhattan/engine/lookahead.py"}, "_period": {PIT, "manhattan/engine/lookahead.py"},
    "diagnostic_window": {PIT, "manhattan/ops/capacity.py"},
    "Window": {PIT, "manhattan/engine/backtest.py", EVALUATE, "manhattan/ops/data.py",
               "manhattan/factors/reproduce.py", ACCESS},
    # access: contexts, proofs, seals, bindings and settlement
    "_CTX_KEY": {ACCESS}, "_PROOF_KEY": {ACCESS}, "_mac": {ACCESS}, "_store_mac": {ACCESS},
    "_sealed_write": {ACCESS}, "_MINTED": {ACCESS}, "_BOUND": {ACCESS}, "_COMMIT_PENDING": {ACCESS},
    "_settle_failed_commit": {ACCESS}, "_StoreBackend": {ACCESS}, "_LedgerBackend": {ACCESS, EVALUATE},
    "_completion_proof": {ACCESS, EVALUATE}, "_mark_completed": {ACCESS, EVALUATE}, "_backend": {ACCESS, EVALUATE},
    "_require_active": {ACCESS}, "_ended": {ACCESS}, "CompletionProof": {ACCESS},
    "verify_completion": {ACCESS, LEDGER}, "store_seal_ok": {ACCESS, STORE},
    "run_bound": {ACCESS, RUNNER}, "commit_results": {ACCESS, RUNNER}, "commit_failures": {ACCESS, RUNNER},
    "commit_recovery": {ACCESS, RUNNER}, "forward_window": {"manhattan/ops/data.py", RUNNER, ACCESS},
    # S7 final hardening: the verified-fence capability, the one computation, the recomputed forward plan
    "_COMPUTED": {ACCESS}, "_computing": {ACCESS}, "_may_read": {ACCESS}, "_FS_CACHE": {ACCESS},
    "_check_forward_plan": {ACCESS}, "_tag": {ACCESS}, "_git_config": {ACCESS}, "_fence_of": {ACCESS},
    "_fence_key": {ACCESS},
    # the Ledger's raw writer and lifecycle indexes
    "record_evaluation": {LEDGER, EVALUATE}, "_append": {LEDGER}, "_index": {LEDGER}, "_starts": {LEDGER},
    "_terminated": {LEDGER}, "_superseded": {LEDGER}, "_designated": {LEDGER},
    # the Store's raw writer (journal, git) behind the sealed write
    "_append_local": {STORE}, "_commit": {STORE}, "_push": {STORE}, "_transact": {STORE}, "_apply": {STORE},
    "_verify_entry": {STORE}, "_reset_to_remote": {STORE, ACCESS},
    # PR-2: freeze.verify_frozen's trust (the pin, the tag check, the timestamp verifier); the equities gate's seal,
    # the synthetic-world registry, and the readers that do not stop at the registered selection end. Tests reach
    # them through tests/manhattan_freeze_seam.py only (not scanned: it is not under manhattan/)
    "_TRUST": {EQ_FREEZE}, "_PRODUCTION": {EQ_FREEZE}, "_Trust": {EQ_FREEZE}, "_verify_batch": {EQ_FREEZE},
    "_mint": {EQ_REG}, "_HANDLE_KEY": {EQ_REG}, "_seal_of": {EQ_REG}, "_sealed": {EQ_REG},
    "_SYNTHETIC": {EQ_SYN}, "_register_world": {EQ_SYN}, "_world_provenance": {EQ_SYN}, "_GENERATORS": {EQ_SYN},
    "_sleeve": {EQ_TC, EQ_REG}, "_compare": {EQ_TC},
    "manhattan_freeze_seam": set(),
}


def scan(sources: dict) -> dict:
    """{name: [modules that reference it without being allowed]} over {relative path: source text}."""
    found: dict[str, set[str]] = {k: set() for k in ALLOWED}
    for rel, text in sources.items():
        refs = _refs(ast.parse(text))
        for name in ALLOWED:
            if name in refs:
                found[name].add(rel)
    return {k: sorted(v - ALLOWED[k]) for k, v in found.items() if v - ALLOWED[k]}


def test_private_access_paths_are_used_only_where_allowed():
    sources = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
               for p in sorted((ROOT / "manhattan").rglob("*.py"))}
    assert scan(sources) == {}
    # and nothing outside pit.py calls the Window constructor (its seal would fail anyway)
    for rel, text in sources.items():
        if rel == PIT:
            continue
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                assert name != "Window", rel


@pytest.mark.parametrize("snippet,name", [
    ("from manhattan.engine.pit import _open_window", "_open_window"),
    ("import manhattan.engine.pit as p\nw = p._open_window", "_open_window"),
    ("getattr(__import__('manhattan.engine.pit'), '_GRANTS')", "_GRANTS"),
    ("from manhattan import access\nk = access._PROOF_KEY", "_PROOF_KEY"),
    ("from manhattan.access import _sealed_write", "_sealed_write"),
    ("def f(store):\n    store._append_local([])\n    store._push()", "_append_local"),
    ("def f(ledger, p):\n    return ledger._append('evaluation', p)", "_append"),
    ("from manhattan.access import CompletionProof", "CompletionProof"),
    ("def f(ctx):\n    return ctx._completion_proof('c' * 64)", "_completion_proof"),
    ("x = {'name': '_BOUND'}", "_BOUND"),
    ("from manhattan import access\naccess._COMPUTED.discard('a')", "_COMPUTED"),
    ("def f(ctx):\n    ctx._computing = True", "_computing"),
    ("def f(vf):\n    object.__setattr__(vf, '_tag', 'x')", "_tag"),
    # PR-2 review: the forms that reached freeze's trust past the first, import-based scan
    ("import dataclasses\nfrom manhattan.equities import registration as R\n"
     "R.FZ._TRUST = dataclasses.replace(R.FZ._TRUST, signers={'ME'}, tag_signer=lambda *a: 'ME')", "_TRUST"),
    ("from manhattan.equities.registration import FZ\nFZ._TRUST = None", "_TRUST"),
    ("from manhattan import freeze\nsetattr(freeze, '_TRUST', None)", "_TRUST"),
    ("import sys\nt = sys.modules['manhattan.freeze']._TRUST", "_TRUST"),
    ("from manhattan.freeze import verify_frozen\nverify_frozen.__globals__['_TRUST'] = None", "_TRUST"),
    ("import manhattan.freeze as anything\nanything._PRODUCTION", "_PRODUCTION"),
    ("import importlib\nimportlib.import_module('manhattan.freeze')._Trust", "_Trust"),
    ("from manhattan.freeze import _verify_batch", "_verify_batch"),
    ("from manhattan.equities import registration as R\nh = R._mint(object())", "_mint"),
    ("k = getattr(__import__('manhattan.equities.registration'), '_HANDLE_KEY')", "_HANDLE_KEY"),
    ("from manhattan.equities import synthetic as SY\nSY._SYNTHETIC[id(o)] = o", "_SYNTHETIC"),
    ("from manhattan.equities.synthetic import _register_world", "_register_world"),
    ("from manhattan.equities.track_compare import _sleeve", "_sleeve"),
    ("from manhattan.equities import track_compare as TC\nTC._compare(w, c, m)", "_compare"),
    ("import manhattan_freeze_seam", "manhattan_freeze_seam"),
])
def test_the_scan_detects_prohibited_references(snippet, name):
    """N3: a module outside the allowlist that reaches a private access path is flagged."""
    assert name in scan({"manhattan/ops/rogue.py": snippet})
    owners = ALLOWED[name]
    owner = {"_append_local": STORE, "_append": LEDGER, "_GRANTS": PIT}.get(name) or (
        ACCESS if ACCESS in owners or not owners else sorted(owners)[0])
    if not owners:
        assert name in scan({owner: snippet})                   # nobody is allowed (the test-only seam)
    else:
        assert scan({owner: snippet}).get(name) is None


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
    with pytest.raises(L.LedgerError, match="completion proof"):     # an attempt ID alone writes nothing (D-5)
        b.record_evaluation(**base, role="reserve", designated=True, attempt_id=ctx.attempt_id)
    with pytest.raises(L.LedgerError, match="completion proof"):     # the right identity, still no proof
        b.record_evaluation(**base, role="forward", designated=False, attempt_id=ctx.attempt_id)
    with pytest.raises(L.LedgerError, match="registered"):           # no attempt at all
        b.record_evaluation(**base, role="forward", designated=False)
    assert b.records()[-1]["type"] == "evaluation_started" and ctx.active()
    # an exploration attempt cannot be completed implicitly by key either
    ex = F.register(b, st, domain=DOM, start=date(2009, 11, 2), end=date(2009, 11, 30), role="exploration",
                    fence=FWD_FENCE, caller="session")
    e = ex.identity
    with pytest.raises(L.LedgerError, match="own attempt_id"):
        b.record_evaluation(**{**base, "window": e["window"], "data_hash": e["data_hash"]}, role="exploration",
                            designated=False)
    for kind in L.LIFECYCLE_TYPES:                                    # nor through the public append
        with pytest.raises(L.LedgerError, match="lifecycle"):
            b.append(kind, {"attempt_id": ctx.attempt_id})


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
    # another batch (D-6 allows one designated reserve evaluation per batch and domain)
    ctx2 = F.register(b, reconstructed, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="reserve",
                      window_id="test:reserve2", fence=RESERVE_FENCE, batch="AB-0002", designated=True,
                      token=F.reserve_token(DOM, "test:reserve2", batch="AB-0002"))
    with pytest.raises(pit.PitError, match="reconstructed"):
        evaluate.evaluate(ctx2.window(reconstructed), hold(), ledger=b,
                          **F.spec_kwargs(designated=True, batch="AB-0002"), attempt=ctx2)


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
    F.forge(b, "evaluation", forged)                               # hash-valid: a writer bug or forgery
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert not r["access_reconciled"]
    assert [v["code"] for v in r["violations"]] == ["evidential_weight_mismatch"]


def test_unregistered_protected_evaluations_and_forged_authorizations(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    ident = ctx.identity
    F.forge(b, "evaluation", dict(executable=ident["executable"], variant=ident["variant"],
                                  hypothesis=ident["hypothesis"], family=ident["family"], batch="AB-0001",
                                  channel="blind", role="reserve",
                                  window={"id": "x", "start": "2010-01-04", "end": "2010-01-05", "frequency": "daily"},
                                  designated=True, spec_hash="a" * 64, data_hash="d" * 64,
                                  code_version=ident["code_version"], result_hash="c" * 64, n_obs=1, summary={},
                                  seed=0, reconstructed=False, evidential_weight=1))   # bypassing every API
    start = b.records("evaluation_started")[0]["payload"]
    forged = json.loads(json.dumps(start))
    forged["role"] = "exploration"                                 # forward dates relabelled exploration
    for w in forged["authorization"]["windows"]:
        w["role"] = "exploration"
    F.forge(b, "evaluation_started", forged)
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


# ================================================================== S7 audit corrections (each failed before)

import copy
import multiprocessing
import pickle
import subprocess
import sys


# ---- H1: the runner imports and runs without PyYAML (the hash-locked runner environment)

def test_runner_imports_without_pyyaml():
    """The runner module imports without PyYAML; reading the fence without it fails closed (D-12: no injected
    fence, no unverified fallback)."""
    code = ("import sys; sys.modules['yaml'] = None; sys.path.insert(0, %r); "
            "from manhattan.ops import runner as R; from manhattan import access as A; "
            "from datetime import date; import subprocess; "
            "head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=%r, capture_output=True, text=True).stdout.strip(); "
            "cfg = R.RunConfig(ledger_dir='x', remote='x', batches_dir='x', asof=date(2026, 1, 2), commit=head)\n"
            "try:\n    R.run_fence(cfg)\n    raise SystemExit('read a fence without PyYAML')\n"
            "except A.AccessError:\n    pass\n"
            "assert 'manhattan.config' not in sys.modules" % (str(ROOT), str(ROOT)))
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("case", ["verified", "pinned", "wrong_pin", "unknown_commit", "zero_commit",
                                  "edited_config", "not_a_mapping"])
def test_the_runner_fence_is_verified_against_its_pinned_identity(tmp_path, case):
    """D-12: the authoritative configuration must equal its version at the registered commit (and an explicit pin,
    if given), parsed with safe_load; anything else fails closed. A caller cannot inject a fence."""
    from manhattan.ops import runner as R
    cfg = R.RunConfig(ledger_dir=tmp_path, remote="", batches_dir=tmp_path, asof=date(2026, 1, 2), commit=F.HEAD)
    assert not hasattr(cfg, "fence")
    if case in ("verified", "pinned"):
        vf = R.run_fence(cfg)
        assert isinstance(vf, access.VerifiedFence) and vf.valid() and vf.commit == F.HEAD
        assert vf.fence == roles.Fence.from_config(__import__("manhattan.config", fromlist=["load"]).load())
        if case == "pinned":
            cfg.config_sha256 = vf.config_sha256
            assert R.run_fence(cfg).record() == vf.record()
        return
    root = ROOT
    if case == "wrong_pin":
        cfg.config_sha256 = "f" * 64
    elif case == "unknown_commit":
        cfg.commit = "a" * 40
    elif case == "zero_commit":
        cfg.commit = "0" * 40
    else:                                                # a working copy whose configuration was edited
        import shutil
        root = tmp_path / "repo"
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "config").mkdir()
        shutil.copy(ROOT / "config/manhattan.yaml", root / "config/manhattan.yaml")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-qm", "c"], check=True)
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
        text = "reserve:\n  enabled: true\n" if case == "edited_config" else "[1, 2]\n"
        if case == "not_a_mapping":
            (root / "config/manhattan.yaml").write_text(text)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                            "commit", "-qam", "d"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                                    text=True, check=True).stdout.strip()
        else:
            (root / "config/manhattan.yaml").write_text(text)          # not committed
        with pytest.raises(access.AccessError):
            access.verified_fence(commit, root=root)
        return
    with pytest.raises(access.AccessError):
        R.run_fence(cfg)


# ---- H2: a protected window reads only while its attempt is registered and active

def test_no_read_after_abort_and_data_read_stays_true(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    w = ctx.window(st)
    ctx.abort("cancelled")
    assert b.records()[-1]["payload"]["data_read"] is False
    with pytest.raises(pit.AccessError, match="not registered and active"):
        backtest.run(w, hold())
    with pytest.raises(pit.AccessError):
        w.as_of("A", date(2010, 1, 8))
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["completed"] == 0 and r["terminals_by_data_read"]["aborted_unread"] == 1
    ctx2 = forward_ctx(b, st, end=date(2010, 1, 14))               # a read, then an abort: data_read is true
    ctx2.window(st).as_of("A", date(2010, 1, 8))
    ctx2.abort("cancelled")
    assert b.records()[-1]["payload"]["data_read"] is True


@pytest.mark.parametrize("ending", ["identity_failure", "execution_failure", "completion", "superseded_retry"])
def test_no_read_after_any_ending(tmp_path, ending):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    w = ctx.window(st)
    if ending == "identity_failure":
        with pytest.raises(pit.AccessError):
            evaluate.evaluate(w, hold(), ledger=b, **F.spec_kwargs(designated=True), attempt=ctx)
    elif ending == "execution_failure":
        bad = Strategy((Instrument("A", "A"),), lambda v: 1 / 0, rebalance="D", lag=0)
        with pytest.raises(ZeroDivisionError):
            evaluate.evaluate(w, bad, ledger=b, **F.spec_kwargs(), attempt=ctx)
    elif ending == "completion":
        evaluate.evaluate(w, hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    else:                                                             # a retry supersedes the attempt
        forward_ctx(b, st, supersedes=ctx.attempt_id)
    with pytest.raises(pit.AccessError, match="not registered and active"):
        backtest.run(w, hold())


# ---- H3: windows are not copied, serialized, altered or inherited

def test_windows_cannot_be_copied_serialized_or_altered(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    open_w = pit.Reader(st, caller="session", domain=DOM, fence=FWD_FENCE).window(date(2009, 11, 2),
                                                                                   date(2009, 12, 31))
    for w in (ctx.window(st), open_w):
        for clone in (copy.copy, copy.deepcopy, lambda x: pickle.loads(pickle.dumps(x))):
            with pytest.raises(pit.AccessError):
                clone(w)
    assert not ctx.data_read
    for field, value in (("end", date(2010, 1, 29)), ("role", "forward"), ("start", date(2009, 1, 2)),
                         ("purpose", "diagnostic"), ("attempt_id", "a" * 64)):
        w = pit.Reader(st, caller="session", domain=DOM, fence=FWD_FENCE).window(date(2009, 11, 2),
                                                                                  date(2009, 12, 31))
        object.__setattr__(w, field, value)                          # widening through the back door
        with pytest.raises(pit.AccessError, match="not opened in this process"):
            w.as_of("A", date(2010, 1, 29))


def _read_in_child(window, q):
    try:
        window.as_of("A", date(2010, 1, 8))
        q.put("read")
    except Exception as exc:                                         # noqa: BLE001 - reported to the parent
        q.put(type(exc).__name__)


@pytest.mark.skipif(sys.platform != "linux", reason="fork start method")
def test_a_forked_child_cannot_read_an_inherited_window(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    w = ctx.window(st)
    mp = multiprocessing.get_context("fork")
    q = mp.Queue()
    child = mp.Process(target=_read_in_child, args=(w, q))
    child.start()
    child.join(60)
    assert q.get(timeout=10) == "AccessError" and not ctx.data_read
    with pytest.raises(pit.AccessError):                              # and spawn needs pickling, which is refused
        multiprocessing.get_context("spawn").Process(target=_read_in_child, args=(w, q)).start()


# ---- M3: the running code identity is computed, never taken from the caller

def test_fabricated_matching_version_is_refused(tmp_path):
    b, st = book(tmp_path), store()
    fake = {"commit": "a" * 40, "engine_sha256": "b" * 64}
    ctx = forward_ctx(b, st, version=fake)
    with pytest.raises(pit.AccessError, match="running code"):
        evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx, version=fake)
    assert b.records()[-1]["type"] == "attempt_failed"
    ctx2 = forward_ctx(b, st, end=date(2010, 1, 14), version=fake)  # no version given: the running one is used
    with pytest.raises(pit.AccessError, match="registered identity"):
        evaluate.evaluate(ctx2.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx2)
    assert attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))["completed"] == 0


# ---- M4: every completion is validated, linked or not

@pytest.mark.parametrize("bad", ["exploration_weight_1", "invalid_role", "no_writer", "rerun_without_first"])
def test_invalid_unlinked_completions_never_reconcile(tmp_path, bad):
    from test_manhattan_attempts import ev
    b = book(tmp_path)
    p = {**ev(designated=False, role="exploration"), "reconstructed": False, "evidential_weight": 0}
    kind, writer = "evaluation", None
    if bad == "exploration_weight_1":
        p["evidential_weight"] = 1
    elif bad == "invalid_role":
        p["role"] = "admin"
    elif bad == "no_writer":
        writer = ""
    else:
        kind = "rerun"
    F.forge(b, kind, p, writer=writer)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["violations"] and not r["access_reconciled"]
    assert r["legacy"]["unlinked_exploration"] == 0                  # never reclassified as open exploration


# ---- M5 (D-5): a protected completion needs the attempt's own proof

def test_completion_proofs_are_single_use_bound_and_require_a_read(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    with pytest.raises(pit.AccessError, match="read nothing"):
        ctx._completion_proof("c" * 64)
    ctx.window(st).as_of("A", date(2010, 1, 8))
    proof = ctx._completion_proof("c" * 64)
    i = ctx.identity
    kw = dict(executable=i["executable"], variant=i["variant"], hypothesis=i["hypothesis"], family=i["family"],
              batch=i["batch"], channel=i["channel"], role="forward", window=i["window"], designated=False,
              spec_hash=i["spec_hash"], data_hash=i["data_hash"], code_version=i["code_version"], n_obs=1,
              summary={}, seed=0, attempt_id=ctx.attempt_id)
    with pytest.raises(L.LedgerError, match="completion proof"):     # bound to its result
        b.record_evaluation(**kw, result_hash="d" * 64, proof=proof)
    with pytest.raises(L.LedgerError, match="completion proof|registered"):     # bound to its ledger
        book(tmp_path, "other.jsonl").record_evaluation(**kw, result_hash="c" * 64, proof=proof)
    for clone in (copy.copy, copy.deepcopy, lambda x: pickle.loads(pickle.dumps(x))):
        with pytest.raises(pit.AccessError):
            clone(proof)
    with pytest.raises(pit.AccessError):
        access.CompletionProof(_key=object(), attempt_id=ctx.attempt_id, result_hash="c" * 64, ledger_id=id(b))


# ---- M6: reserve tokens are bound to the attempt they authorize

@pytest.mark.parametrize("mismatch", ["batch", "spec", "window", "unverified", "manifest", "token_on_forward"])
def test_reserve_token_must_match_the_attempt(tmp_path, mismatch):
    b, st = book(tmp_path), store()
    wid = "test:reserve"
    tok = F.reserve_token(DOM, wid)
    if mismatch == "batch":
        tok = dataclasses.replace(tok, batch="AB-9999")
    elif mismatch == "spec":
        tok = dataclasses.replace(tok, specs=frozenset({"e" * 64}))
    elif mismatch == "window":
        tok = dataclasses.replace(tok, designated=frozenset({(DOM, "test:other")}))
    elif mismatch == "unverified":
        tok = dataclasses.replace(tok, verified=False)
    elif mismatch == "manifest":
        tok = dataclasses.replace(tok, manifest_hash="not-a-hash")
    if mismatch == "token_on_forward":
        with pytest.raises(pit.AccessError):
            forward_ctx(b, st, token=tok)
    else:
        with pytest.raises((pit.AccessError, roles.RoleError)):
            F.register(b, st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="reserve",
                       window_id=wid, fence=RESERVE_FENCE, token=tok, designated=True)
    assert len(b) == 0


def test_a_recorded_token_for_another_batch_or_spec_is_a_violation(tmp_path):
    b, st = book(tmp_path), store()
    ctx = reserve_ctx(b, st)
    start = json.loads(json.dumps(b.records("evaluation_started")[0]["payload"]))
    start["authorization"]["token"]["batch"] = "AB-9999"
    start["batch"] = "AB-0001"
    F.forge(b, "evaluation_started", start)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert "invalid_identity_or_authorization" in [v["code"] for v in r["violations"]]
    assert ctx.active()


# ---- D-6: one designated reserve evaluation per batch and domain, conservatively

def test_one_designated_reserve_evaluation_per_batch_and_domain(tmp_path):
    b, st = book(tmp_path), store()
    first = reserve_ctx(b, st, wid="test:r1")
    with pytest.raises(pit.AccessError, match="D-6"):                # even while the first is unfinished
        reserve_ctx(b, st, wid="test:r2", end=date(2010, 1, 14))
    del first
    b = book(tmp_path)                                                # crash; the retry of the same attempt is allowed
    retry = reserve_ctx(b, st, wid="test:r1", supersedes=b.unfinished()[0]["hash"])
    retry.fail("execution_error")                                     # a failed designated attempt consumes it
    with pytest.raises(pit.AccessError, match="D-6"):
        reserve_ctx(b, st, wid="test:r3", end=date(2010, 1, 13))
    other = F.register(b, st, domain=DOM, start=date(2010, 1, 4), end=date(2010, 1, 15), role="reserve",
                       window_id="test:r4", fence=RESERVE_FENCE, batch="AB-0002", designated=True,
                       token=F.reserve_token(DOM, "test:r4", batch="AB-0002"))
    assert other.active()                                             # another batch is another designation


def test_a_forged_second_designated_reserve_attempt_is_a_violation(tmp_path):
    b, st = book(tmp_path), store()
    reserve_ctx(b, st)
    twin = json.loads(json.dumps(b.records("evaluation_started")[0]["payload"]))
    twin["window"]["id"] = "test:twin"
    for w in twin["authorization"]["windows"]:
        w["id"] = "test:twin"
    F.forge(b, "evaluation_started", twin)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert "designated_reserve_reused" in [v["code"] for v in r["violations"]]


# ---- D-7: assurance levels are reported, never conflated

def test_reconciliation_never_claims_independent_certification(tmp_path):
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"] and r["independently_certified"] is False
    assert r["assurance"] == {"internally_consistent": True, "checked_against_supplied_anchor": True,
                              "independently_anchored": False}
    assert r["independent_statistical_tests"] is None
    assert r["protected_attempts_with_unpinned_fence"] == 1        # a caller-supplied fence is reported (G-3)


# ================================================================== S7 re-review (N1, N4, D-13)

def test_non_designated_reserve_attempts_are_refused(tmp_path):
    """N1: a reserve read is the designated evaluation of its (batch, domain) or nothing; even a token that names
    the window does not allow a non-designated read. Nothing is written, nothing is read."""
    b, st = book(tmp_path), store()
    for _ in range(5):
        with pytest.raises(pit.AccessError, match="non-designated"):
            reserve_ctx(b, st, designated=False)
    assert len(b) == 0
    ctx = reserve_ctx(b, st)                                       # the designated evaluation is still available
    _, rec = evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(designated=True), attempt=ctx)
    assert rec["payload"]["evidential_weight"] == 1
    assert attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))["access_reconciled"]


def test_a_designation_is_consumed_even_without_a_read(tmp_path):
    """D-13: a designated reserve attempt that ended before any read still consumes its (batch, domain)
    designation; it is never released or recycled."""
    b, st = book(tmp_path), store()
    first = reserve_ctx(b, st)
    first.abort("cancelled")
    assert b.records()[-1]["payload"]["data_read"] is False
    for designated in (True, False):
        with pytest.raises(pit.AccessError):
            reserve_ctx(b, st, wid="test:again", end=date(2010, 1, 14), designated=designated)


@pytest.mark.parametrize("prefix", [0, 1, 5])
def test_forged_non_designated_reserve_history_never_reconciles(tmp_path, prefix):
    """N1 in a hostile history: non-designated reserve attempts that read and were cancelled before a designated
    evaluation are violations, as is any second reserve attempt of the (batch, domain)."""
    b, st = book(tmp_path), store()
    ctx = reserve_ctx(b, st)
    _, rec = evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(designated=True), attempt=ctx)
    start = b.records("evaluation_started")[0]["payload"]
    forged = book(tmp_path, "forged.jsonl")
    for i in range(prefix):
        p = json.loads(json.dumps(start))
        p["designated"] = False
        p["window"]["id"] = f"test:probe{i}"
        for w in p["authorization"]["windows"]:
            w["id"] = f"test:probe{i}"
        s_ = F.forge(forged, "evaluation_started", p)
        F.forge(forged, "attempt_aborted", {"attempt_id": s_["hash"], "reason": "cancelled", "data_read": True})
    s_ = F.forge(forged, "evaluation_started", start)
    F.forge(forged, "evaluation", {**rec["payload"], "attempt_id": s_["hash"]})
    r = attempts.reconcile(ledger_path=forged.path, ledger_anchor=anchor(forged))
    codes = [v["code"] for v in r["violations"]]
    if prefix == 0:
        assert r["access_reconciled"], codes                      # the clean history reconciles
    else:
        assert codes.count("non_designated_reserve_attempt") == prefix and "designated_reserve_reused" in codes
        assert not r["access_reconciled"]


def _evaluate_forward(b, st, strategy, end=date(2010, 1, 15)):
    ctx = forward_ctx(b, st, end=end)
    return evaluate.evaluate(ctx.window(st), strategy, ledger=b, **F.spec_kwargs(), attempt=ctx)[1]


def test_protected_weights_through_the_real_path(tmp_path):
    """N4: through registered forward attempts (never the storage API): the first valid evaluation has weight 1; a
    rerun with the same result, a nondeterministic result and a changed-data evaluation of the same key have
    weight 0; the family is suspended; reconciliation recomputes every weight and agrees."""
    b, st = book(tmp_path), store()
    first = _evaluate_forward(b, st, hold())
    assert (first["type"], first["payload"]["evidential_weight"]) == ("evaluation", 1)
    rerun = _evaluate_forward(b, st, hold())
    assert (rerun["type"], rerun["payload"]["evidential_weight"], rerun["payload"]["first_seq"]) == \
        ("rerun", 0, first["seq"])
    half = Strategy((Instrument("A", "A"),), lambda v: {"A": 0.5}, rebalance="D", lag=0)
    odd = _evaluate_forward(b, st, half)                           # same spec, data and window; another result
    assert (odd["type"], odd["payload"]["evidential_weight"]) == ("nondeterminism", 0)
    assert odd["payload"]["first_result_hash"] == first["payload"]["result_hash"]
    assert b.suspended_families() == {first["payload"]["family"]}
    revised = store()
    revised.add("A", ["2010-01-06"], [999.0], available=["2010-01-12"])   # a vendor revision: new data identity
    changed = _evaluate_forward(b, revised, hold())
    p = changed["payload"]
    assert (changed["type"], p["evidential_weight"], p["data_changed"]) == ("evaluation", 0, True)
    assert p["result_of_record_seq"] == first["seq"] and b.looks() == 2
    r = attempts.reconcile(ledger_path=b.path, ledger_anchor=anchor(b))
    assert r["access_reconciled"], r["violations"]
    assert (r["completed"], r["completed_evaluation_keys"], r["registered_executions"]) == (4, 2, 4)


def test_reserve_weight_1_once_and_no_protected_rerun(tmp_path):
    """N4 for the reserve: the designated evaluation has weight 1; a rerun, a nondeterministic or a changed-data
    reserve evaluation of the same batch and domain cannot even be registered (D-6, N1)."""
    b, st = book(tmp_path), store()
    ctx = reserve_ctx(b, st)
    _, rec = evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(designated=True), attempt=ctx)
    assert (rec["type"], rec["payload"]["evidential_weight"]) == ("evaluation", 1)
    revised = store()
    revised.add("A", ["2010-01-06"], [999.0], available=["2010-01-12"])
    for s_ in (st, revised):
        with pytest.raises(pit.AccessError, match="D-6"):
            reserve_ctx(b, s_)
