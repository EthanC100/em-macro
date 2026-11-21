"""The HTE → PR #86 attempt bridge (``manhattan.hte_accounting``): dormancy, owner decisions, outcome hashing,
and the cross-PR contract against PR #86's real ledger and strict reconciler.

The first group needs only PR #89 + #90. The second group needs PR #86 in the tree (an integration worktree, or
main after the merges); without it, it is skipped and the skip says so. Every ledger here is a temporary file.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from manhattan import ledger as L
from manhattan.hte import data as D, fixtures as X, ids, registry as R, store
from manhattan.hte.log import AttemptLog
from manhattan.hte.policy import Policy
from manhattan.hte.runner import S1, S3, Runner, Workspace
from manhattan.hte_accounting import (BridgePolicy, OwnerDecisionRequired, OwnerDecisionUnsupported, bridge as B,
                                      denominator, outcomes as O)

ROOT = Path(__file__).resolve().parents[1]
PR86 = hasattr(L, "validate_attempt_identity") and getattr(L, "ATTEMPT_SCHEMA", None) == 2
needs_pr86 = pytest.mark.skipif(not PR86, reason="needs PR #86 (attempt schema 2) merged into this tree")
DECIDED = BridgePolicy("register_every_evaluation", None, "per_candidate_attempts", "test fixture, not an approval")


@pytest.fixture(scope="module")
def panel():
    return D.generate(X.SMALL_PANEL)


def _ws(path, bundles=None) -> Workspace:
    ws = Workspace(path)
    reg = ws.registry()
    b = bundles if bundles is not None else X.small_bundles()
    from manhattan.hte import templates as TP
    reg.submit(b, allow_test_templates=any(TP.TEMPLATES[x.spec["template"]].test_only for x in b))
    reg.freeze()
    return ws


# -- 1. dormancy and owner decisions (no PR #86 needed) ---------------------------------------------------------------

def test_the_switch_is_off_in_source_and_refuses():
    assert B.ENABLED is False
    assert "\nENABLED = False\n" in Path(B.__file__).read_text()
    with pytest.raises(B.BridgeDisabled):
        B.Bridge(object(), DECIDED, fence=None)


@pytest.mark.parametrize("policy,err", [
    (BridgePolicy(None, None, "per_candidate_attempts", "x"), OwnerDecisionRequired),          # D-10 undecided
    (BridgePolicy("unregistered", None, "per_candidate_attempts", "x"), OwnerDecisionUnsupported),
    (BridgePolicy("register_selected_only", None, "per_candidate_attempts", "x"), OwnerDecisionUnsupported),
    (BridgePolicy("register_every_evaluation", None, None, "x"), OwnerDecisionRequired),       # B4 undecided
    (BridgePolicy("register_every_evaluation", None, "per_chunk_attempt", "x"), OwnerDecisionUnsupported),
    (BridgePolicy("register_every_evaluation", None, "per_candidate_attempts", None), OwnerDecisionRequired),
    (BridgePolicy("register_every_evaluation", None, "per_candidate_attempts", " "), OwnerDecisionRequired),
])
def test_undecided_or_unsupported_owner_decisions_fail_closed(policy, err):
    with pytest.raises(err):
        policy.require_registration()


def test_policy_values_are_closed_sets():
    with pytest.raises(ValueError):
        BridgePolicy("register_everything")
    with pytest.raises(ValueError):
        BridgePolicy(d1_counting_unit="whatever_is_smallest")


def test_d1_is_never_defaulted():
    report = {"units": {"registered_executions": 240, "completed_evaluation_keys": 120, "executables": 120,
                        "bindings": 120, "candidates": 120, "variants": 60, "hypotheses": 10, "families": 5}}
    with pytest.raises(OwnerDecisionRequired, match="D-1"):
        denominator(report, DECIDED)
    with pytest.raises(OwnerDecisionRequired):
        denominator(report, BridgePolicy(d1_counting_unit="variants"))                       # no approval reference
    out = denominator(report, BridgePolicy(d1_counting_unit="variants", approval_ref="test only"))
    assert out == {"unit": "variants", "count": 60, "approval_ref": "test only"}


def test_package_uses_no_private_pr86_names_and_hte_stays_independent():
    src = "".join(p.read_text() for p in (ROOT / "manhattan" / "hte_accounting").glob("*.py"))
    for name in ("_open_window", "_SEAL_KEY", "_CTX_KEY", "_PROOF_KEY", "CompletionProof", "._append(", "_starts",
                 "run_bound", "forward_window", "Norgate", "Databento", "em-macro-data"):
        assert name not in src, name
    hte = "".join(p.read_text() for p in (ROOT / "manhattan" / "hte").glob("*.py"))
    assert "hte_accounting" not in hte                                          # HTE never imports the bridge


# -- 2. outcome hashing (no PR #86 needed) ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def closed_run(tmp_path_factory, panel):
    ws = _ws(tmp_path_factory.mktemp("closed"))
    r = Runner(ws, panel, Policy(), chunk_size=32)
    out = r.run()
    return ws, r, store.read_arrays(r.dir / out["results_file"], out["results_sha256"])


def _cands(r):
    return np.stack([np.frombuffer(bytes.fromhex(r.view.candidate_hash(i)), np.uint8) for i in range(len(r.view))])


def test_result_hashes_are_deterministic_and_aliases_take_their_representatives_status(closed_run):
    _, r, t = closed_run
    c = _cands(r)
    i1, i2 = O.intrinsic_columns(t), O.intrinsic_columns(dict(t))
    assert np.array_equal(O.row_hashes(O.RESULT_DOMAIN, c, i1), O.row_hashes(O.RESULT_DOMAIN, c, i2))
    al = np.flatnonzero(t["alias_of"] >= 0)
    assert al.size, "the fixture should contain behavioural aliases"
    assert not (i1["s3"] == S3["alias"]).any()
    assert np.array_equal(i1["s3"][al], t["s3"][t["alias_of"][al]])
    # every candidate gets its own hash, and the hash moves with any intrinsic value
    h = O.row_hashes(O.RESULT_DOMAIN, c, i1)
    assert len({bytes(x) for x in h}) == len(h)
    bumped = dict(i1, stats2=i1["stats2"].copy())
    bumped["stats2"][5, 0] = np.nextafter(bumped["stats2"][5, 0], np.inf)
    h2 = O.row_hashes(O.RESULT_DOMAIN, c, bumped)
    assert [i for i in range(len(h)) if bytes(h[i]) != bytes(h2[i])] == [5]


def test_result_hashes_do_not_depend_on_chunking_or_workspace(closed_run, tmp_path, panel):
    _, r, t = closed_run
    r2 = Runner(_ws(tmp_path / "other"), panel, Policy(), chunk_size=7)
    out2 = r2.run()
    t2 = store.read_arrays(r2.dir / out2["results_file"], out2["results_sha256"])
    c = _cands(r)
    assert np.array_equal(c, _cands(r2))
    for dom, cols in ((O.RESULT_DOMAIN, O.intrinsic_columns), (O.COHORT_DOMAIN, lambda x: O.cohort_columns(x, c))):
        assert np.array_equal(O.row_hashes(dom, c, cols(t)), O.row_hashes(dom, c, cols(t2)))


def test_cohort_values_are_outside_the_result_hash(closed_run):
    _, r, t = closed_run
    c = _cands(r)
    t2 = dict(t, stats3=t["stats3"].copy(), cross_family_behaviour=~t["cross_family_behaviour"])
    t2["stats3"][:, O._P] = 0.5                                           # every bootstrap p-value changed
    assert np.array_equal(O.row_hashes(O.RESULT_DOMAIN, c, O.intrinsic_columns(t)),
                          O.row_hashes(O.RESULT_DOMAIN, c, O.intrinsic_columns(t2)))
    assert not np.array_equal(O.row_hashes(O.COHORT_DOMAIN, c, O.cohort_columns(t, c)),
                              O.row_hashes(O.COHORT_DOMAIN, c, O.cohort_columns(t2, c)))


def test_outcome_batches_hold_at_most_512_rows_and_detect_a_changed_row(closed_run, tmp_path):
    _, r, t = closed_run
    c = _cands(r)
    n = len(c)
    fake = np.zeros((n, 32), np.uint8)
    with pytest.raises(O.OutcomeError):
        O.write_batches(tmp_path, candidates=c, executables=fake, attempts=fake, intr=O.intrinsic_columns(t),
                        coh=O.cohort_columns(t, c), batch_size=513)
    batches, rh, _, _ = O.write_batches(tmp_path, candidates=c, executables=fake, attempts=fake + 1,
                                        intr=O.intrinsic_columns(t), coh=O.cohort_columns(t, c), batch_size=50)
    assert [(b["lo"], b["hi"]) for b in batches] == [(0, 50), (50, 100), (100, n)]
    arr = O.read_batch(tmp_path, batches[1])
    assert O.verify_batch(arr) == []
    assert np.array_equal(arr["result_hash"], rh[50:100])
    arr["i_stats2"] = arr["i_stats2"].copy()
    arr["i_stats2"][7, 1] += 1e-12                                        # one value of one candidate
    assert O.verify_batch(arr) == [7]


# -- 3. the bridge against PR #86's real ledger ----------------------------------------------------------------------

def _fence():
    from manhattan import roles
    return roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(B, "ENABLED", True)


def WRITE(book, **completion):
    """Test-only completion writer. PR #86 lets only ledger.py and engine/evaluate.py call ``record_evaluation`` from
    ``manhattan/``; whether the bridge may is owner decision A-1, so the bridge never calls it itself."""
    return book.record_evaluation(**completion)


def _book(path):
    return L.Ledger(Path(path) / "ledger.jsonl", writer="hte-bridge-test", protocol="f" * 64)


def _bridge(book, policy=DECIDED):
    return B.Bridge(book, policy, fence=_fence())


def _cycle(br, ws, panel, *, verify=False, **kw):
    r = Runner(ws, panel, Policy(), chunk_size=32, **kw)
    reg = br.begin(r, verify_rerun=verify)
    out = r.run(verify_rerun=verify)
    return r, reg, out, br.complete(r, completion_writer=WRITE)


def _types(ws, run_id):
    return [x["type"] for x in AttemptLog(ws.log_path).records() if x["payload"].get("run_id") == run_id]


@needs_pr86
def test_every_candidate_is_registered_before_computing_and_completed_after(on, tmp_path, panel):
    from manhattan import attempts as A
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r, reg, out, comp = _cycle(br, ws, panel)
    n = len(r.view)
    assert reg["attempts"] == reg["new"] == n and reg["retries"] == 0
    seq = _types(ws, r.run_id)
    assert seq.index("pr86_registered") < seq.index("run_started") < seq.index("run_closed") < \
        seq.index("pr86_completed")
    assert comp["terminals"] == {"evaluation": n}
    assert all(b["hi"] - b["lo"] <= O.BATCH_MAX for b in comp["batches"])
    # PR #86's own strict audit accepts the whole ledger
    rep86 = A.reconcile(ledger_path=book.path, ledger_anchor={"records": len(book), "head": book.head})
    assert rep86["violations"] == [] and rep86["registered_executions"] == n and rep86["completed"] == n
    assert rep86["independent_statistical_tests"] is None
    # every individual outcome is retrievable and verifiable from its completion alone
    ev = book.records("evaluation")[17]["payload"]
    b = next(x for x in comp["batches"] if x["sha256"] == ev["summary"]["outcome_batch"])
    row = O.read_batch(r.dir / "pr86", b)
    k = ev["summary"]["row"]
    assert bytes(row["result_hash"][k]).hex() == ev["result_hash"]
    assert bytes(row["attempt"][k]).hex() == ev["attempt_id"]
    assert O.verify_batch(row) == []
    rep = crosscheck(r, book)
    assert rep["consistent"], rep["violations"]
    assert rep["units"] == {"registered_executions": n, "completed_evaluation_keys": n, "executables": n,
                            "bindings": n, "candidates": n, "variants": rep["units"]["variants"],
                            "hypotheses": rep["units"]["hypotheses"], "families": rep["units"]["families"]}
    assert rep["hte"]["chunk_attempts"]["started"] < n                    # chunks are not attempts
    assert rep["independent_statistical_tests"] is None


@needs_pr86
def test_without_a_completion_writer_nothing_is_written_and_attempts_stay_open(on, tmp_path, panel):
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    br.begin(r)
    r.run()
    before = len(book)
    with pytest.raises(OwnerDecisionRequired, match="A-1"):
        br.complete(r)
    assert len(book) == before
    assert not list((r.dir / "pr86").glob("outcomes_*.bin"))
    assert "pr86_completed" not in _types(ws, r.run_id)
    assert br.complete(r, completion_writer=WRITE)["terminals"] == {"evaluation": len(r.view)}


@needs_pr86
def test_verify_rerun_is_a_duplicate_evaluation_and_a_reused_run_registers_nothing(on, tmp_path, panel):
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r, _, _, _ = _cycle(br, ws, panel)
    n, before = len(r.view), len(book)
    with pytest.raises(B.BridgeRefused, match="reuses"):
        br.begin(Runner(ws, panel, Policy(), chunk_size=32))
    assert len(book) == before
    r2, reg2, out2, comp2 = _cycle(br, ws, panel, verify=True)
    assert out2["verified"] is True and comp2["terminals"] == {"rerun": n}
    assert book.looks() == n
    rep = crosscheck(r2, book)
    assert rep["consistent"], rep["violations"]
    assert rep["pr86"]["attempts"] == 2 * n and rep["pr86"]["rerun"] == n
    assert rep["units"]["completed_evaluation_keys"] == n and rep["units"]["bindings"] == n
    assert rep["accounting"]["completions"] == 2 * n and rep["accounting"]["looks"] == n
    assert rep["hte"]["computing_invocations"] == 2 and rep["hte"]["registrations"] == 2


SCRIPT = """
import sys
from datetime import date
from pathlib import Path
from manhattan import ledger as L, roles
from manhattan.hte import data as D, fixtures as X
from manhattan.hte.policy import Policy
from manhattan.hte.runner import Runner, Workspace
from manhattan.hte_accounting import BridgePolicy, bridge as B
B.ENABLED = True
ws = Workspace(Path(sys.argv[1]))
book = L.Ledger(Path(sys.argv[2]), writer="hte-bridge-test", protocol="f" * 64)
br = B.Bridge(book, BridgePolicy("register_every_evaluation", None, "per_candidate_attempts",
                                 "test fixture, not an approval"),
              fence=roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False))
r = Runner(ws, D.generate(X.SMALL_PANEL), Policy(), chunk_size=32)
br.begin(r)
r.run()
"""


def _crash(ws, book, fault):
    env = dict(os.environ, PYTHONPATH=str(ROOT), OPENBLAS_NUM_THREADS="1", HTE_FAULT=fault)
    return subprocess.run([sys.executable, "-c", SCRIPT, str(ws.root), str(book.path)], env=env, cwd=ROOT,
                          capture_output=True, text=True, timeout=600)


@needs_pr86
def test_an_interrupted_run_is_retried_under_pr86_and_completes_once(on, tmp_path, panel):
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    p = _crash(ws, book, "exit_after_start:2")
    assert p.returncode == 77, p.stderr[-2000:]
    book = _book(tmp_path)                                                # the crashed process's writes, re-read
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    n = len(r.view)
    with pytest.raises(B.BridgeRefused, match="run_closed"):
        br.complete(r, completion_writer=WRITE)            # nothing closed: attempts stay open
    reg = br.begin(r)
    assert reg["retries"] == n and reg["new"] == 0
    r.run()
    assert br.complete(r, completion_writer=WRITE)["terminals"] == {"evaluation": n}
    assert book.looks() == n and len(book.records("evaluation_started")) == 2 * n
    rep = crosscheck(r, book)
    assert rep["consistent"], rep["violations"]
    assert rep["pr86"]["retries"] == n and rep["pr86"]["open"] == 0
    assert rep["hte"]["chunk_attempts"]["interrupted"] >= 1
    assert rep["hte"]["computing_invocations"] == 2 and rep["hte"]["registrations"] == 2


@needs_pr86
def test_a_resume_without_re_registration_is_refused_and_flagged(on, tmp_path, panel):
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    assert _crash(ws, book, "exit_after_start:2").returncode == 77
    book = _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    r.run()                                                               # resumed without begin
    with pytest.raises(B.BridgeRefused, match="more than one invocation"):
        br.complete(r, completion_writer=WRITE)
    with pytest.raises(B.BridgeRefused, match="reuses"):
        br.begin(r)                                                       # closed: no post-hoc registration
    rep = crosscheck(r, book)
    assert "unregistered_computation" in {x["code"] for x in rep["violations"]}
    out = br.abandon(r, "resumed without registration")
    assert out["aborted"] == len(r.view)
    assert crosscheck(r, book)["pr86"]["attempt_aborted"] == len(r.view)


@needs_pr86
def test_a_crash_during_completion_is_finished_by_calling_complete_again(on, tmp_path, panel, monkeypatch):
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    br.begin(r)
    r.run()
    real, calls = book.record_evaluation, []

    def flaky(**kw):
        if len(calls) == 40:
            raise OSError("injected crash")
        calls.append(1)
        return real(**kw)

    monkeypatch.setattr(book, "record_evaluation", flaky)
    with pytest.raises(OSError):
        br.complete(r, completion_writer=WRITE)
    monkeypatch.setattr(book, "record_evaluation", real)
    out = br.complete(r, completion_writer=WRITE)
    assert out["resumed"] == 40 and sum(out["terminals"].values()) == len(r.view) - 40
    rep = crosscheck(r, book)
    assert rep["consistent"], rep["violations"]
    assert rep["pr86"]["evaluation"] == len(r.view)


@needs_pr86
def test_failed_candidates_are_failed_attempts_and_stay_counted(on, tmp_path, panel):
    from tests.test_manhattan_hte_funnel import _poison_bundles
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws", _poison_bundles()), _book(tmp_path)
    br = _bridge(book)
    r, _, _, comp = _cycle(br, ws, panel)
    assert comp["terminals"]["attempt_failed"] == 4
    rep = crosscheck(r, book)
    assert rep["consistent"], rep["violations"]
    assert rep["units"]["registered_executions"] == len(r.view) and rep["pr86"]["attempt_failed"] == 4
    failed = [x for x in book.records("attempt_failed")]
    assert all(x["payload"]["reason"] == "execution_error" and x["payload"]["data_read"] is True for x in failed)


@needs_pr86
def test_corrupted_results_fail_every_attempt_and_complete_nothing(on, tmp_path, panel):
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    br.begin(r)
    r.run()
    f = r.dir / "results.bin"
    raw = bytearray(f.read_bytes())
    raw[-9] ^= 0xFF
    f.write_bytes(bytes(raw))
    with pytest.raises(B.BridgeRefused, match="corrupted"):
        br.complete(r, completion_writer=WRITE)
    assert len(book.records("attempt_failed")) == len(r.view) and not book.records("evaluation")
    assert all(x["payload"]["reason"] == "validation_error" for x in book.records("attempt_failed"))
    rep = crosscheck(r, book)
    assert "hte_run_corrupted" in {x["code"] for x in rep["violations"]}
    assert rep["pr86"]["open"] == 0 and rep["pr86"]["reconciler_violations"] == 0


@needs_pr86
def test_tampered_outcomes_and_forged_attempts_are_detected(on, tmp_path, panel):
    from tests.manhattan_attempt_fixtures import forge
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r, _, _, comp = _cycle(br, ws, panel)
    f = r.dir / "pr86" / comp["batches"][0]["file"]
    good = f.read_bytes()
    f.write_bytes(good[:-1] + bytes([good[-1] ^ 1]))
    assert "outcome_batch_corrupt" in {x["code"] for x in crosscheck(r, book)["violations"]}
    f.write_bytes(good)
    # a start in the run's batch that no HTE registration names
    s = book.records("evaluation_started")[0]["payload"]
    forge(book, "evaluation_started", dict(s, executable="f" * 64, spec_hash="f" * 64))
    codes = {x["code"] for x in crosscheck(r, book)["violations"]}
    assert "foreign_attempt" in codes


@needs_pr86
@pytest.mark.parametrize("change", ["engine", "environment"])
def test_engine_or_environment_change_is_a_new_executable_and_new_looks(on, tmp_path, panel, monkeypatch, change):
    from manhattan.hte import adapters
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r1, _, _, _ = _cycle(br, ws, panel)
    real = ids.code_identity

    def other():
        c = real()
        if change == "engine":
            c["engine_sha256"] = "e" * 64
        else:
            c["numeric_environment"] = dict(c["numeric_environment"], blas=dict(
                c["numeric_environment"]["blas"], runtime_core="SomeOtherCore"))
            c["numeric_environment_sha256"] = ids.full_hash(c["numeric_environment"])
        return c

    monkeypatch.setattr(ids, "code_identity", other)
    r2, _, _, comp2 = _cycle(br, ws, panel)
    n = len(r1.view)
    assert r2.run_id != r1.run_id
    assert comp2["terminals"] == {"evaluation": n}                        # never a rerun of the other engine
    assert book.looks() == 2 * n and book.suspended_families() == set()
    rep1, rep2 = crosscheck(r1, book), crosscheck(r2, book)
    assert rep1["consistent"] and rep2["consistent"], (rep1["violations"], rep2["violations"])
    _, l1 = B.identities(r1)
    _, l2 = B.identities(r2)
    comps = book.records("evaluation")
    acc = adapters.executable_accounting(comps, {x["executable"]: x for x in l1 + l2})
    assert acc["scientific"]["binding"] == n and acc["executables"] == 2 * n
    assert len(acc["cross_executable"]) == n and not any(g["divergent"] for g in acc["cross_executable"])


@needs_pr86
def test_registry_growth_reruns_old_candidates_without_a_false_nondeterminism(on, tmp_path, panel):
    """A new freeze is a new HTE run (its registry root is in the run identity) but the same executables for the
    old candidates: PR #86 sees reruns with identical intrinsic results, never a nondeterminism."""
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r1, _, _, _ = _cycle(br, ws, panel)
    fam = R.family("unrelated", "TEST", "+", "dense")
    hyp = R.hypothesis(fam, "commodity")
    reg = ws.registry()
    reg.submit([R.Bundle(fam, hyp, R.strategy_spec(hyp, "trend", {"lookback": [33], "shape": ["sign"],
                                                                  "vol_halflife": [20], "rebalance": [1]}))])
    reg.freeze()
    r2, _, _, comp2 = _cycle(br, ws, panel)
    assert r2.run_id != r1.run_id and len(r2.view) == len(r1.view) + 1
    assert comp2["terminals"] == {"rerun": len(r1.view), "evaluation": 1}
    assert book.suspended_families() == set() and not book.records("nondeterminism")
    assert crosscheck(r2, book)["consistent"]


@needs_pr86
def test_guards_refuse_production_ledgers_protected_fences_and_gated_policies(on, tmp_path, panel):
    from manhattan import roles
    inside = L.Ledger(ROOT / "results" / "manhattan_hte" / ".bridge_test_never_written.jsonl", writer="t",
                      protocol="f" * 64)
    with pytest.raises(B.BridgeRefused, match="inside the repository"):
        _bridge(inside)
    assert not inside.path.exists()
    book = _book(tmp_path)
    for fence in (roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=True),
                  roles.Fence(exploration_end=date(2019, 12, 31), reserve={"x": (date(2020, 1, 1), date(2021, 1, 1))}),
                  None):
        with pytest.raises(B.BridgeRefused):
            B.Bridge(book, DECIDED, fence=fence)
    with pytest.raises(B.BridgeRefused):
        B.Bridge(book, DECIDED, fence=_fence(), caller="critic")
    ws = _ws(tmp_path / "ws")
    gated = Runner(ws, panel, Policy(stage3_selection="top_k_per_spec", top_k=2, benchmark_only=True))
    with pytest.raises(B.BridgeRefused, match="performance-gated"):
        _bridge(book).begin(gated)
    early = _bridge(book)
    early.fence = roles.Fence(exploration_end=date(2001, 1, 1), reserve={}, enabled=False)
    with pytest.raises(B.BridgeRefused, match="exploration"):
        early.begin(Runner(ws, panel, Policy()))
    assert len(book) == 0


# ------------------------------------------------- the indexed ledger (PR #100): streamed reads, fail-closed reports

@needs_pr86
def test_the_bridge_and_cross_check_never_load_the_whole_ledger(on, tmp_path, panel, monkeypatch):
    """begin, complete, abandon and crosscheck stream the ledger with ``iter_records`` (PR #100) and never call
    ``records()``, which builds every record as objects at once."""
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)

    def refuse(*a, **k):
        raise AssertionError("Ledger.records() called: the whole ledger would be held in memory")
    monkeypatch.setattr(book, "records", refuse)
    br = _bridge(book)
    r, _, _, comp = _cycle(br, ws, panel)
    rep = crosscheck(r, book)
    assert rep["consistent"], rep["violations"]
    assert comp["terminals"] and rep["pr86"]["attempts"] == len(r.view)


@needs_pr86
def test_a_resumed_completion_refuses_an_attempt_with_two_terminals(on, tmp_path, panel, monkeypatch):
    """A duplicated or forged terminal on an attempt is never silently accepted on resume: the bridge refuses and the
    cross-check reports it."""
    from tests.manhattan_attempt_fixtures import forge
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    reg = br.begin(r)
    r.run()
    real, calls = book.record_evaluation, []

    def flaky(**kw):
        if len(calls) == 5:
            raise OSError("injected crash")
        calls.append(1)
        return real(**kw)
    monkeypatch.setattr(book, "record_evaluation", flaky)
    with pytest.raises(OSError):
        br.complete(r, completion_writer=WRITE)
    monkeypatch.setattr(book, "record_evaluation", real)
    done = next(x for x in book.iter_records() if x["type"] == "evaluation")
    forge(book, "attempt_aborted", {"attempt_id": done["payload"]["attempt_id"], "reason": "interrupted",
                                    "data_read": True})
    with pytest.raises(B.BridgeRefused, match="2 terminals"):
        br.complete(r, completion_writer=WRITE)
    assert reg["attempts"] == len(r.view)
    rep = crosscheck(r, book)
    assert not rep["consistent"]


@needs_pr86
@pytest.mark.parametrize("damage", ["edited", "truncated"])
def test_a_damaged_ledger_file_is_reported_not_raised(on, tmp_path, panel, damage):
    """The cross-check reports a ledger file that no longer verifies (and PR #86's reconciler refusing it) as
    violations, so its report is never 'consistent' and it never stops on an exception."""
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r, _, _, _ = _cycle(br, ws, panel)
    raw = book.path.read_bytes().splitlines(keepends=True)
    if damage == "edited":
        i = next(k for k, x in enumerate(raw) if b'"type":"evaluation"' in x)
        raw[i] = raw[i].replace(b'"n_obs":', b'"n_obs":1', 1)     # a different value: the hash no longer matches
    else:
        raw = raw[:-1]
    book.path.write_bytes(b"".join(raw))
    rep = crosscheck(r, book)
    codes = {x["code"] for x in rep["violations"]}
    assert not rep["consistent"]
    assert "pr86_reconciler" in codes
    if damage == "edited":
        assert "ledger_does_not_verify" in codes


# ------------------------------------------------------------- independent review (2026-11-21): guards and anchors

@needs_pr86
@pytest.mark.parametrize("change", ["switch", "policy", "fence_enabled", "fence_reserve", "caller", "root"])
def test_guards_are_re_checked_on_every_operation(on, tmp_path, panel, monkeypatch, change):
    """Changing the switch, the policy, the fence, the caller or ROOT on an existing bridge is refused by begin,
    complete and abandon, and nothing is written."""
    from manhattan import roles
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    br.begin(r)
    r.run()
    n = len(book)
    if change == "switch":
        monkeypatch.setattr(B, "ENABLED", False)
    elif change == "policy":
        br.policy = BridgePolicy(None, None, None, None)
    elif change == "fence_enabled":
        br.fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=True)
    elif change == "fence_reserve":
        br.fence = roles.Fence(exploration_end=date(2019, 12, 31),
                               reserve={"x": (date(2015, 1, 1), date(2016, 1, 1))}, enabled=False)
    elif change == "caller":
        br.caller = "runner"
    else:
        monkeypatch.setattr(B, "ROOT", tmp_path)
    for op in (lambda: br.begin(r, verify_rerun=True), lambda: br.complete(r, completion_writer=WRITE),
               lambda: br.abandon(r, "test")):
        with pytest.raises((PermissionError, B.BridgeRefused)):
            op()
    assert len(book) == n


@needs_pr86
def test_the_runner_caller_is_refused(on, tmp_path):
    with pytest.raises(B.BridgeRefused, match="runner"):
        B.Bridge(_book(tmp_path), DECIDED, fence=_fence(), caller="runner")


@needs_pr86
def test_a_finished_but_uncompleted_run_is_never_superseded_as_interrupted(on, tmp_path, panel, monkeypatch):
    """Review finding 1b: begin, run, then begin(verify_rerun) without complete used to supersede every attempt of
    the finished computation as an interrupted one. It is refused now, and the cross-check flags such a history."""
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r = Runner(ws, panel, Policy(), chunk_size=32)
    br.begin(r)
    r.run()
    n = len(book)
    with pytest.raises(B.BridgeRefused, match="never completed or abandoned"):
        br.begin(r, verify_rerun=True)
    assert len(book) == n
    # the history the old code produced is flagged
    monkeypatch.setattr(B, "_unclosed_finished_registration", lambda recs: None)
    br.begin(r, verify_rerun=True)
    assert "finished_invocation_superseded" in {x["code"] for x in crosscheck(r, book)["violations"]}


@needs_pr86
def test_a_registration_whose_invocation_computed_nothing_is_flagged(on, tmp_path, panel):
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r, _, _, _ = _cycle(br, ws, panel)
    br.begin(r, verify_rerun=True)
    r.run()                                                # a plain invocation: reuses, computes nothing
    codes = {x["code"] for x in crosscheck(r, book)["violations"]}
    assert "registration_without_computation" in codes


@needs_pr86
def test_the_cross_check_reads_the_file_not_a_stale_ledger_object(on, tmp_path, panel):
    """Review finding 4: a hash-valid rewrite of the file is caught as an anchor mismatch even when the caller's
    ledger object still holds the old records."""
    from manhattan.hte_accounting.crosscheck import crosscheck
    ws, book = _ws(tmp_path / "ws"), _book(tmp_path)
    br = _bridge(book)
    r, _, _, _ = _cycle(br, ws, panel)
    recs = [json.loads(x) for x in book.path.read_bytes().splitlines()]
    recs[0]["payload"]["executable"] = "e" * 64                # rewritten and re-hashed: every hash valid
    prev = L.GENESIS
    for rec in recs:
        rec["prev_hash"] = prev
        rec["hash"] = L.record_hash(rec)
        prev = rec["hash"]
    book.path.write_bytes(b"".join((json.dumps(x, sort_keys=True, separators=(",", ":")) + "\n").encode()
                                   for x in recs))
    codes = {x["code"] for x in crosscheck(r, book)["violations"]}
    assert {"ledger_anchor_mismatch", "ledger_object_differs_from_file"} <= codes
