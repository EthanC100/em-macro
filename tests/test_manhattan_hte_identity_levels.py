"""S11: HTE evaluation identity against PR #86's evaluation key (the residual of S10 F7).

PR #86 decides evaluation / rerun / nondeterminism by ``Ledger.key`` = ``(spec_hash, data_hash, window id)``.
Before this fix the adapter's ``spec_hash`` held no code and no numerical environment, so a new engine was recorded
as a ``rerun`` of the old engine's look (same bits) or as a ``nondeterminism`` that suspended the family (other
bits). The adapter now keeps two levels: the code-free *binding* (the scientific evaluation) and the *executable*
(binding + engine digest + numerical environment), whose hash is PR #86's ``spec_hash``.

The first group of tests needs nothing but this package. The second group runs against PR #86's real ledger and
needs PR #86 merged (an integration worktree, or main after the merge); without it those tests are skipped, and
the skip says so.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from manhattan import ledger as L
from manhattan.hte import adapters, data as D, fixtures as X, ids
from manhattan.hte.policy import Policy
from manhattan.hte.runner import Runner, Workspace

WINDOW = {"id": "synthetic", "start": "2001-03-01", "end": "2002-07-15", "frequency": "daily"}
COMMIT = "1" * 40
PR86 = hasattr(L, "validate_attempt_identity") and getattr(L, "ATTEMPT_SCHEMA", None) == 2
needs_pr86 = pytest.mark.skipif(not PR86, reason="needs PR #86 (attempt schema 2) merged into this tree")


@pytest.fixture(scope="module")
def runner(tmp_path_factory):
    ws = Workspace(tmp_path_factory.mktemp("hte_ids"))
    reg = ws.registry()
    reg.submit(X.small_bundles())
    reg.freeze()
    return Runner(ws, D.generate(X.SMALL_PANEL), Policy())


def _code(r, *, engine: str | None = None, env: str | None = None) -> dict:
    """The runner's real code identity, optionally with another engine digest or numerical environment."""
    code = dict(r.code, commit=COMMIT)
    if engine is not None:
        code["engine_sha256"] = engine
    if env is not None:
        code["numeric_environment"] = dict(code["numeric_environment"], blas=dict(
            code["numeric_environment"]["blas"], runtime_core=env))
        code["numeric_environment_sha256"] = ids.full_hash(code["numeric_environment"])
    return code


def _ident(r, code, i=3, policy=Policy()):
    return adapters.to_pr86_identity(r.view, i, run_id="HR-test", data_hash=r.data_hash, code=code, window=WINDOW,
                                     policy=policy, fence=r.panel.fence)


def _lin(r, code, i=3, policy=Policy()):
    return adapters.lineage(r.view, i, code=code, policy=policy, fence=r.panel.fence)


def _key(ident):
    return ident["spec_hash"], ident["data_hash"], ident["window"]["id"]


SCIENTIFIC = ("family", "hypothesis", "variant", "candidate", "binding")


# -- 1. identity levels (no PR #86 needed) ---------------------------------------------------------------------------

def test_engine_change_is_a_new_executable_and_a_new_pr86_key(runner):
    a, b = _code(runner), _code(runner, engine="e" * 64)
    ia, ib = _ident(runner, a), _ident(runner, b)
    assert _key(ia) != _key(ib)                                           # never a rerun of the other engine's look
    assert ia["executable"] == ia["spec_hash"] and ib["executable"] == ib["spec_hash"]
    assert ib["code_version"]["engine_sha256"] == "e" * 64
    la, lb = _lin(runner, a), _lin(runner, b)
    assert all(la[k] == lb[k] for k in SCIENTIFIC)                       # the same scientific evaluation
    assert {k: ia[k] for k in ("variant", "hypothesis", "family")} == {k: ib[k] for k in ("variant", "hypothesis",
                                                                                          "family")}


def test_numerical_environment_change_is_a_new_executable_and_is_explicit(runner):
    a, b = _code(runner), _code(runner, env="SomeOtherCore")
    ia, ib = _ident(runner, a), _ident(runner, b)
    assert ia["code_version"]["engine_sha256"] == ib["code_version"]["engine_sha256"]
    assert _key(ia) != _key(ib)
    assert ia["code_version"]["numeric_environment_sha256"] == a["numeric_environment_sha256"]
    assert ib["code_version"]["numeric_environment_sha256"] == b["numeric_environment_sha256"]
    assert all(_lin(runner, a)[k] == _lin(runner, b)[k] for k in SCIENTIFIC)


def test_same_binding_engine_and_environment_keep_one_key(runner):
    code = _code(runner)
    assert _ident(runner, code) == _ident(runner, dict(code))             # deterministic: reruns stay reruns
    assert _ident(runner, code)["spec_hash"] != _ident(runner, code, i=4)["spec_hash"]


def test_binding_is_code_free_and_is_the_s10_f7_evaluation_spec(runner):
    spec = adapters.evaluation_spec(runner.view, 3, policy=Policy(), fence=runner.panel.fence)
    lin = _lin(runner, _code(runner))
    assert lin["binding"] == ids.full_hash(spec)
    assert lin["executable"] == ids.full_hash(adapters.executable_spec(lin["binding"], _code(runner)))
    assert lin["binding"] != lin["executable"]
    for policy in (Policy(bootstrap_B=499), Policy(vol_target_ann=0.2)):  # F7 still holds at the binding level
        assert _lin(runner, _code(runner), policy=policy)["binding"] != lin["binding"]


def test_real_engine_source_change_changes_the_executable(runner, tmp_path, monkeypatch):
    """Not a hand-set digest: one byte of an engine module changed in a copy of the package."""
    pkg = tmp_path / "hte"
    shutil.copytree(ids.PKG_DIR, pkg, ignore=shutil.ignore_patterns("__pycache__"))
    before = ids.code_identity()
    monkeypatch.setattr(ids, "PKG_DIR", pkg)
    assert ids.code_identity()["engine_sha256"] == before["engine_sha256"]
    k = pkg / "kernels.py"
    k.write_text(k.read_text() + "\n# engine change\n")
    after = ids.code_identity()
    assert after["engine_sha256"] != before["engine_sha256"]
    assert _key(_ident(runner, dict(before, commit=COMMIT))) != _key(_ident(runner, dict(after, commit=COMMIT)))


@pytest.mark.parametrize("breakage", ["no_env", "zero_env", "mismatched_env", "no_engine", "short_engine"])
def test_code_identity_without_explicit_engine_and_environment_is_refused(runner, breakage):
    code = _code(runner)
    if breakage == "no_env":
        code.pop("numeric_environment_sha256")
    elif breakage == "zero_env":
        code["numeric_environment_sha256"] = "0" * 64
    elif breakage == "mismatched_env":
        code["numeric_environment_sha256"] = "a" * 64
    elif breakage == "no_engine":
        code.pop("engine_sha256")
    else:
        code["engine_sha256"] = "abc"
    with pytest.raises(ValueError):
        _ident(runner, code)


def _completion(ident, type_, result):
    return {"type": type_, "payload": dict(ident, result_hash=result)}


def test_accounting_separates_executions_from_scientific_units(runner):
    codes = [_code(runner), _code(runner, engine="e" * 64), _code(runner, env="SomeOtherCore")]
    lins = {}
    recs = []
    for n, code in enumerate(codes):
        ident, lin = _ident(runner, code), _lin(runner, code)
        lins[lin["executable"]] = lin
        recs.append(_completion(ident, "evaluation", "a" * 64))
        if n == 0:
            recs.append(_completion(ident, "rerun", "a" * 64))
    out = adapters.executable_accounting(recs, lins)
    assert (out["completions"], out["looks"], out["executables"]) == (4, 3, 3)
    assert out["scientific"] == {k: 1 for k in SCIENTIFIC}                # engine/environment never add a test unit
    assert out["independent_statistical_tests"] is None and "D-1" in out["independent_statistical_tests_reason"]
    [g] = out["cross_executable"]
    assert (g["executables"], g["engines"], g["environments"], g["divergent"]) == (3, 2, 2, False)
    assert out["hold_families"] == []
    recs[-1]["payload"]["result_hash"] = "b" * 64                         # the environment changed the answer
    out = adapters.executable_accounting(recs, lins)
    assert out["cross_executable"][0]["divergent"] is True
    assert out["hold_families"] == [lins[recs[0]["payload"]["executable"]]["family"]]
    with pytest.raises(ValueError, match="lineage"):
        adapters.executable_accounting(recs, {})


# -- 2. against PR #86's real ledger ---------------------------------------------------------------------------------

def _ledger(tmp_path):
    return L.Ledger(tmp_path / "ledger.jsonl", writer="hte-s11-test", protocol="f" * 64)


def _start(book, ident, supersedes=None):
    """A schema-2 start straight through ``Ledger.start_evaluation`` (no window authorization: exploration attempts
    are unregistered in PR #86, D-10; this exercises the key and lifecycle rules only)."""
    return book.start_evaluation({**ident, "attempt_schema": 2, "kind": "evaluation",
                                  "authorization": {"synthetic": True}}, supersedes=supersedes)["hash"]


def _complete(book, ident, attempt_id, result):
    return book.record_evaluation(**ident, result_hash=result, n_obs=10, summary={}, seed=0, attempt_id=attempt_id)


@needs_pr86
def test_identities_validate_against_pr86(runner):
    for code in (_code(runner), _code(runner, engine="e" * 64), _code(runner, env="SomeOtherCore")):
        L.validate_attempt_identity(_ident(runner, code))
    assert set(adapters.PR86_IDENTITY_FIELDS) == set(L.IDENTITY_FIELDS)
    ident = _ident(runner, _code(runner))
    assert L.Ledger.key(ident) == _key(ident)                             # PR86_KEY states the real key


@needs_pr86
@pytest.mark.parametrize("change", ["engine", "environment"])
def test_pr86_records_a_new_engine_or_environment_as_a_new_look(runner, tmp_path, change):
    book = _ledger(tmp_path)
    a = _ident(runner, _code(runner))
    b = _ident(runner, _code(runner, engine="e" * 64) if change == "engine" else _code(runner, env="SomeOtherCore"))
    assert _complete(book, a, _start(book, a), "a" * 64)["type"] == "evaluation"
    assert _complete(book, b, _start(book, b), "a" * 64)["type"] == "evaluation"      # not a rerun
    assert _complete(book, b, _start(book, b), "b" * 64)["type"] == "nondeterminism"  # same executable: real
    assert book.looks() == 2 and len(book.records("evaluation_started")) == 3
    assert book.suspended_families() == {a["family"]}


@needs_pr86
def test_pr86_other_bits_from_another_engine_do_not_suspend_the_family(runner, tmp_path):
    book = _ledger(tmp_path)
    a, b = _ident(runner, _code(runner)), _ident(runner, _code(runner, engine="e" * 64))
    _complete(book, a, _start(book, a), "a" * 64)
    rec = _complete(book, b, _start(book, b), "b" * 64)
    assert rec["type"] == "evaluation" and "data_changed" not in rec["payload"]
    assert book.suspended_families() == set()
    lins = {x["executable"]: _lin(runner, c) for x, c in ((a, _code(runner)), (b, _code(runner, engine="e" * 64)))}
    out = adapters.executable_accounting(book.records("evaluation"), lins)
    assert out["hold_families"] == [a["family"]] and out["cross_executable"][0]["divergent"] is True


@needs_pr86
def test_the_pre_fix_mapping_collapsed_engines_in_pr86(runner, tmp_path):
    """The defect, reproduced: with ``spec_hash`` = binding (the approved PR #89 mapping) PR #86 calls a new
    engine's identical result a rerun, and a different one a nondeterminism that suspends the family."""
    book = _ledger(tmp_path)
    old = []
    for code in (_code(runner), _code(runner, engine="e" * 64), _code(runner, engine="d" * 64)):
        x = _ident(runner, code)
        x["spec_hash"] = _lin(runner, code)["binding"]
        old.append(x)
    assert _complete(book, old[0], _start(book, old[0]), "a" * 64)["type"] == "evaluation"
    assert _complete(book, old[1], _start(book, old[1]), "a" * 64)["type"] == "rerun"
    assert _complete(book, old[2], _start(book, old[2]), "b" * 64)["type"] == "nondeterminism"
    assert book.looks() == 1 and book.suspended_families() == {old[0]["family"]}


@needs_pr86
def test_pr86_duplicate_evaluations_are_reruns_and_every_attempt_is_kept(runner, tmp_path):
    book = _ledger(tmp_path)
    a = _ident(runner, _code(runner))
    types = [_complete(book, a, _start(book, a), "a" * 64)["type"] for _ in range(3)]
    assert types == ["evaluation", "rerun", "rerun"]
    assert book.looks() == 1 and len(book.records("evaluation_started")) == 3
    assert [r["payload"]["evidential_weight"] for r in book.records() if r["type"] in L.COMPLETIONS] == [0, 0, 0]


@needs_pr86
def test_pr86_interrupted_attempt_resumes_only_under_its_own_engine_and_environment(runner, tmp_path):
    book = _ledger(tmp_path)
    a = _ident(runner, _code(runner))
    first = _start(book, a)                                               # interrupted: no terminal
    for other in (_ident(runner, _code(runner, engine="e" * 64)), _ident(runner, _code(runner, env="SomeOtherCore"))):
        with pytest.raises(L.LedgerError, match="retry identity differs"):
            _start(book, other, supersedes=first)
    retry = _start(book, a, supersedes=first)
    assert _complete(book, a, retry, "a" * 64)["type"] == "evaluation"
    assert book.is_superseded(first) and len(book.records("evaluation_started")) == 2
    # a new engine after an interruption: the old attempt is closed as interrupted, the new one is a new look
    b = _ident(runner, _code(runner, engine="e" * 64))
    stale = _start(book, a)
    book.end_attempt(stale, status="aborted", reason="interrupted", data_read=False)
    assert _complete(book, b, _start(book, b), "a" * 64)["type"] == "evaluation"
    assert len(book.records("evaluation_started")) == 4 and len(book.records("attempt_aborted")) == 1
    # PR #86 keeps the superseded original visible as unfinished (ATTEMPT_ACCOUNTING.md): nothing is hidden
    assert [r["hash"] for r in book.unfinished()] == [first] and book.looks() == 2
    assert L.verify(book.path) == []


@needs_pr86
def test_pr86_reconciler_accepts_hte_executables_and_counts_every_level(runner, tmp_path):
    """PR #86's strict audit (``attempts.reconcile``) over HTE identities: the extended ``code_version`` is accepted,
    no violation is reported, and its counts match the adapter's at the execution level."""
    from datetime import date
    from manhattan import access, attempts as A, roles
    book = _ledger(tmp_path)
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)

    def register(x):                                  # the real registration path, exploration role only
        w = access.DeclaredWindow(WINDOW["id"], "hte-synthetic", date.fromisoformat(WINDOW["start"]),
                                  date.fromisoformat(WINDOW["end"]), "exploration", "evaluation", x["data_hash"])
        return access.register_evaluation(book, identity=x, windows=[w], caller=roles.RUNNER, fence=fence).attempt_id

    codes = [_code(runner), _code(runner, engine="e" * 64), _code(runner, env="SomeOtherCore")]
    lins = {}
    for code in codes:
        x = _ident(runner, code)
        lins[x["executable"]] = _lin(runner, code)
        _complete(book, x, register(x), "a" * 64)
    a = _ident(runner, codes[0])
    _complete(book, a, register(a), "a" * 64)                             # a rerun of the first executable
    rep = A.reconcile(ledger_path=book.path, ledger_anchor={"records": len(book), "head": book.head})
    assert rep["violations"] == [] and rep["unfinished"] == 0
    assert rep["registered_executions"] == 4 and rep["completed"] == 4
    assert rep["distinct_specifications"] == 3 and rep["completed_evaluation_keys"] == 3
    assert rep["independent_statistical_tests"] is None
    out = adapters.executable_accounting([r for r in book.records() if r["type"] in L.COMPLETIONS], lins)
    assert (out["completions"], out["looks"], out["executables"]) == (4, 3, 3)
    assert out["scientific"]["binding"] == 1 and out["scientific"]["family"] == 1
