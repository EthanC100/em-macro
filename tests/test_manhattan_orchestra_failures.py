"""Manhattan orchestra: deterministic synthetic smoke tests and failure-injection tests, with real processes.

Every test runs the supervisor against a throw-away run root and a copy of ``manhattan/`` and its configuration (a
"mini repository"), so the invocation processes import exactly that copy and a test can change code without
touching the checkout. Jobs are the synthetic ``smoke`` kind (seconds each); the HTE test runs only where
``manhattan.hte`` exists (PR #89).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from manhattan.orchestra import limits as L
from manhattan.orchestra import smoke
from manhattan.orchestra.journal import FileLock, canonical, read_json, sha256_bytes
from manhattan.orchestra.supervisor import Supervisor

REPO = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="process groups and /proc: Linux")


def make_repo(dst: Path) -> Path:
    shutil.copytree(REPO / "manhattan", dst / "manhattan", ignore=shutil.ignore_patterns("__pycache__"))
    (dst / "config").mkdir()
    shutil.copy(REPO / "config" / "manhattan.yaml", dst / "config" / "manhattan.yaml")
    for f in REPO.glob("requirements*"):
        shutil.copy(f, dst / f.name)
    return dst


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    return make_repo(tmp_path_factory.mktemp("repo"))


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(root)).encode() + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


FAST = dict(require_clean_tree=False, backoff_base_s=0, backoff_max_s=0, launch_grace_s=5, cancel_grace_s=2,
            progress_interval_s=1, max_running_jobs=4, max_total_workers=4)


def sup_for(tmp_path, repo, clock=None, **kw):
    return Supervisor(tmp_path / "root", limits=L.Limits(**{**FAST, **kw}), repo=repo,
                      **({"clock": clock} if clock else {}))


def run_until(sup, cond, timeout=90.0):
    end = time.time() + timeout
    while time.time() < end:
        sup.tick()
        st = sup.state()
        if cond(st):
            return st
        time.sleep(0.2)
    raise AssertionError(json.dumps({j: (x["status"], x["reason"]) for j, x in sup.state()["jobs"].items()}))


def settled(st):
    return all(j["status"] not in ("queued", "retry_wait", "launching", "running", "cancelling")
               for j in st["jobs"].values())


def status_of(jid):
    return lambda st: st["jobs"][jid]["status"]


def expected_root(units, seed=20261119, work=200):
    return sha256_bytes(canonical({"values": [smoke.unit_value(seed, u, work) for u in range(units)]}))


def kind_log(sup, jid):
    return [json.loads(x) for x in (sup.job_dir(jid) / "work" / "attempts.jsonl").read_text().splitlines()]


# -- smoke ----------------------------------------------------------------------------------------------------

def test_smoke_jobs_complete_reconcile_and_never_touch_the_repository(tmp_path, mini):
    before = tree_hash(mini / "config") + tree_hash(mini / "manhattan" / "orchestra")
    sup = sup_for(tmp_path, mini)
    a = sup.register("smoke", {"units": 37, "chunk": 5, "work": 20})["job_id"]
    b = sup.register("smoke", {"units": 37, "chunk": 9, "work": 20}, priority=5)["job_id"]
    st = run_until(sup, settled)
    for jid in (a, b):
        j = st["jobs"][jid]
        assert j["status"] == "completed" and j["n_invocations"] == 1
        assert j["reconcile"]["state"] == "closed" and j["reconcile"]["violations"] == []
        assert j["reconcile"]["result_root"] == expected_root(37, work=20)      # chunking does not change results
        assert j["anchor"]["records"] == len(kind_log(sup, jid))
        man = read_json(sup.root / j["invocations"][0]["inv_dir"] / "manifest.json")
        assert man["identity"] == j["identity"]
    assert st["jobs"][b]["invocations"][0]["intent_seq"] < st["jobs"][a]["invocations"][0]["intent_seq"]
    assert sup.audit(a)["state"] == "closed"
    assert tree_hash(mini / "config") + tree_hash(mini / "manhattan" / "orchestra") == before
    snap = read_json(sup.root / "status.json")
    assert snap["counts"]["completed"] == 2 and snap["budget"]["month"]
    assert all(st["jobs"][x]["reserved_vcpu_h"] > 0 and st["jobs"][x]["cpu_s"] > 0 for x in (a, b))


def test_duplicate_registration_is_refused_and_journaled_a_new_look_is_explicit(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    a = sup.register("smoke", {"units": 8})
    again = sup.register("smoke", {"chunk": 8, "units": 8})          # same normalised parameters
    assert again == {"job_id": a["job_id"], "duplicate": True, "status": "queued"}
    assert [r["type"] for r in sup.journal.records()].count("duplicate_registration") == 1
    look = sup.register("smoke", {"units": 8}, look=1)
    assert look["job_id"] != a["job_id"] and not look["duplicate"]


def test_registration_refuses_a_dirty_tree_by_default(tmp_path, mini):
    sup = Supervisor(tmp_path / "root", repo=mini)                     # default limits; mini is no git checkout
    from manhattan.orchestra.safety import Refused
    with pytest.raises(Refused, match="require_clean_tree"):
        sup.register("smoke", {"units": 4})


# -- failure injection ----------------------------------------------------------------------------------------

def test_hard_crash_is_retried_without_duplicating_or_losing_attempts(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 30, "chunk": 4, "work": 20, "faults": {"crash_at_unit": 13}})["job_id"]
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert j["status"] == "completed" and [i["ended"]["outcome"] for i in j["invocations"]] == ["lost", "done"]
    log = kind_log(sup, jid)
    starts = {r["hash"]: r["payload"] for r in log if r["type"] == "attempt_started"}
    interrupted = [r["payload"] for r in log if r["type"] == "attempt_interrupted"]
    assert len(interrupted) == 1 and interrupted[0]["lo"] == 12                  # the crashed attempt is kept
    retry = [p for p in starts.values() if p.get("supersedes")]
    assert len(retry) == 1 and retry[0]["supersedes"] == [interrupted[0]["attempt_id"]]
    assert j["reconcile"]["counts"]["covered"] == 30 and j["reconcile"]["violations"] == []
    assert j["reconcile"]["result_root"] == expected_root(30, work=20)                     # identical to a clean run


def test_repeated_errors_fail_the_job_and_every_failed_attempt_stays_recorded(tmp_path, mini):
    sup = sup_for(tmp_path, mini, max_consecutive_errors=3)
    jid = sup.register("smoke", {"units": 12, "chunk": 4, "faults": {"raise_at_unit": 5},
                                 "fault_invocations": [1, 2, 3, 4]})["job_id"]
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert j["status"] == "failed" and "3 consecutive errors" in j["reason"]
    assert [i["ended"]["outcome"] for i in j["invocations"]] == ["error"] * 3
    log = kind_log(sup, jid)
    assert sum(r["type"] == "attempt_failed" for r in log) == 3
    assert sum(r["type"] == "attempt_completed" for r in log) == 1                # units 0-3, once
    fails = [r["payload"] for r in log if r["type"] == "attempt_failed"]
    assert all((f["lo"], f["hi"]) == (4, 8) and f["error_class"] == "RuntimeError" for f in fails)
    sups = [r["payload"].get("supersedes", []) for r in log if r["type"] == "attempt_started"]
    assert len(sups[-1]) == 2                                                     # the last retry names both
    with pytest.raises(Exception, match="no job"):
        sup.requeue("OJ-nonexistent")                                             # unknown job refused
    sup.requeue(jid, "fixed the fault", extra_invocations=0)
    assert sup.state()["jobs"][jid]["status"] == "queued"


def test_invocation_cap_leaves_the_job_incomplete_and_requeue_continues_it(tmp_path, mini):
    sup = sup_for(tmp_path, mini, max_consecutive_errors=10)
    jid = sup.register("smoke", {"units": 12, "chunk": 4, "faults": {"crash_at_unit": 5}, "fault_invocations": [1, 2]},
                       max_invocations=2)["job_id"]
    st = run_until(sup, settled)
    assert st["jobs"][jid]["status"] == "incomplete" and "invocation cap" in st["jobs"][jid]["reason"]
    sup.requeue(jid, extra_invocations=1)
    st = run_until(sup, settled)
    assert st["jobs"][jid]["status"] == "completed" and st["jobs"][jid]["n_invocations"] == 3
    assert st["jobs"][jid]["reconcile"]["result_root"] == expected_root(12)


def test_deadline_stops_a_hung_invocation_and_the_next_one_finishes(tmp_path, mini):
    sup = sup_for(tmp_path, mini, max_wall_minutes_per_invocation=0.06)
    jid = sup.register("smoke", {"units": 12, "chunk": 4, "faults": {"hang_at_unit": 6}})["job_id"]
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert [i["ended"]["outcome"] for i in j["invocations"]] == ["timeout", "done"]
    assert (sup.root / j["invocations"][0]["inv_dir"] / "deadline").exists()
    log = kind_log(sup, jid)
    assert any(r["type"] == "attempt_interrupted" and r["payload"]["reason"] == "cancelled" for r in log)
    assert j["reconcile"]["result_root"] == expected_root(12)


def test_cancel_a_running_job_then_requeue_it(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 12, "chunk": 4, "faults": {"hang_at_unit": 6}})["job_id"]
    run_until(sup, lambda st: st["jobs"][jid]["status"] == "running"
              and (sup.root / st["jobs"][jid]["invocations"][0]["inv_dir"] / "pid.json").exists())
    sup.cancel(jid, "operator test")
    assert sup.state()["jobs"][jid]["status"] == "cancelling"
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert j["status"] == "cancelled" and j["invocations"][0]["ended"]["outcome"] == "cancelled"
    assert j["reconcile"]["counts"]["attempts"]["unfinished"] == 0               # the cut attempt is recorded
    sup.requeue(jid, "resume after cancel")
    st = run_until(sup, settled)
    assert st["jobs"][jid]["status"] == "completed"
    assert st["jobs"][jid]["reconcile"]["result_root"] == expected_root(12)


def test_cancel_a_queued_job_runs_nothing(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    sup.cancel(jid)
    sup.tick()
    j = sup.state()["jobs"][jid]
    assert j["status"] == "cancelled" and j["n_invocations"] == 0


def test_memory_cap_kills_the_process_group(tmp_path, mini):
    sup = sup_for(tmp_path, mini, max_memory_mb_per_job=150)
    jid = sup.register("smoke", {"units": 8, "chunk": 4, "faults": {"alloc_mb": 300, "hang_at_unit": 5}})["job_id"]
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert [i["ended"]["outcome"] for i in j["invocations"]] == ["memory_exceeded", "done"]
    assert j["status"] == "completed"


def test_supervisor_crash_after_spawn_is_adopted_not_duplicated(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 8, "chunk": 4, "sleep_per_chunk_s": 0.5})["job_id"]
    real = sup.journal.append

    def crashing(typ, payload):
        if typ == "invocation_started" and not payload.get("adopted"):
            raise RuntimeError("simulated supervisor crash after spawn")
        return real(typ, payload)
    sup.journal.append = crashing
    with pytest.raises(RuntimeError, match="simulated"):
        sup.tick()
    sup.journal.append = real
    fresh = sup_for(tmp_path, mini)                                   # a restarted supervisor
    st = run_until(fresh, settled)
    j = st["jobs"][jid]
    assert j["status"] == "completed" and j["n_invocations"] == 1
    started = [r["payload"] for r in fresh.journal.records() if r["type"] == "invocation_started"]
    assert len(started) == 1 and started[0]["adopted"] is True


def test_intent_without_a_process_is_recovered_after_the_launch_grace(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    (sup.root / "jobs" / jid / "inv-0001").mkdir()
    with sup.journal.locked():                                        # a crash between intent and spawn
        sup.journal.append("invocation_intent", {"job_id": jid, "n": 1, "inv_dir": f"jobs/{jid}/inv-0001",
                                                 "workers": 1, "intent_epoch": time.time() - 60,
                                                 "deadline_epoch": time.time() + 600, "anchor_in": None})
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert [i["ended"]["outcome"] for i in j["invocations"]] == ["lost_before_start", "done"]


def test_a_second_supervisor_and_a_second_invocation_are_both_refused(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    with FileLock(sup.root / ".supervisor.lock"):
        assert sup.tick() == {"skipped": "another supervisor holds this root"}
    lk = FileLock(sup.job_dir(jid) / ".run.lock")
    assert lk.acquire()
    try:
        out = sup.tick()                                              # the job lock is held: not started
        assert out["started"] == [] and "job lock" in out["deferred"][0]["reason"]
        with sup.journal.locked():
            sup._start(sup.state()["jobs"][jid], time.time())         # bypass the check: the child refuses
        st = run_until(sup, lambda s: s["jobs"][jid]["status"] == "blocked")
        assert st["jobs"][jid]["reason"] == "duplicate_invocation_detected"
        assert read_json(sup.root / st["jobs"][jid]["invocations"][0]["inv_dir"] / "exit.json")["outcome"] == \
            "duplicate_refused"
    finally:
        lk.release()
    sup.requeue(jid, "checked: no other invocation")
    assert run_until(sup, settled)["jobs"][jid]["status"] == "completed"


def test_log_truncated_between_invocations_fails_the_job_on_integrity(tmp_path, mini):
    offset = [0.0]
    sup = sup_for(tmp_path, mini, clock=lambda: time.time() + offset[0], backoff_base_s=3600, backoff_max_s=3600)
    jid = sup.register("smoke", {"units": 16, "chunk": 4, "faults": {"crash_at_unit": 9}})["job_id"]
    run_until(sup, lambda st: st["jobs"][jid]["status"] == "retry_wait")
    p = sup.job_dir(jid) / "work" / "attempts.jsonl"
    lines = p.read_bytes().splitlines(keepends=True)
    p.write_bytes(b"".join(lines[:-2]))                               # a suffix deleted while the job waited
    offset[0] = 7200.0
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert j["status"] == "failed" and j["reason"].startswith("integrity") and "suffix deleted" in j["reason"]
    with pytest.raises(Exception, match="not requeueable"):
        sup.requeue(jid)


def test_audit_detects_tampering_after_completion(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 8, "chunk": 4})["job_id"]
    run_until(sup, settled)
    res = sup.job_dir(jid) / "work" / "result.json"
    res.write_bytes(res.read_bytes().replace(b"[", b"[1,", 1))
    rec = sup.audit(jid)
    assert rec["state"] == "corrupted" and rec["violations"][0]["code"] == "results_tampered"
    sup.tick()
    snap = read_json(sup.root / "status.json")
    assert snap["attention"] and snap["attention"][0]["job_id"] == jid


def test_code_change_between_invocations_blocks_the_job(tmp_path):
    repo = make_repo(tmp_path / "own-repo")
    offset = [0.0]
    sup = sup_for(tmp_path, repo, clock=lambda: time.time() + offset[0], backoff_base_s=3600, backoff_max_s=3600)
    jid = sup.register("smoke", {"units": 12, "chunk": 4, "faults": {"crash_at_unit": 5}})["job_id"]
    run_until(sup, lambda st: st["jobs"][jid]["status"] == "retry_wait")
    (repo / "manhattan" / "orchestra" / "_edited_between_invocations.py").write_text("X = 1\n")
    offset[0] = 7200.0
    st = run_until(sup, settled)
    assert (st["jobs"][jid]["status"], st["jobs"][jid]["reason"]) == ("blocked", "code_changed")


def test_budget_disk_pause_and_switches_hold_every_start(tmp_path):
    repo = make_repo(tmp_path / "own-repo")
    sup = sup_for(tmp_path, repo, monthly_vcpu_hours=1.0, max_wall_minutes_per_invocation=120)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    out = sup.tick()
    assert out["started"] == [] and "monthly vCPU-hour budget" in out["deferred"][0]["reason"]
    sup.tick()
    assert [r["type"] for r in sup.journal.records()].count("start_deferred") == 1    # journaled once, not per tick
    sup2 = Supervisor(sup.root, limits=L.Limits(**{**FAST, "price_sgd_per_vcpu_hour": 1.0,
                                                    "monthly_budget_sgd": 2.0}), repo=repo)
    assert "spend cap" in sup2.tick()["deferred"][0]["reason"]
    sup3 = Supervisor(sup.root, limits=L.Limits(**{**FAST, "min_free_disk_mb": 10**9}), repo=repo)
    assert "free disk" in sup3.tick()["deferred"][0]["reason"]
    ok = Supervisor(sup.root, limits=L.Limits(**FAST), repo=repo)
    (ok.root / "PAUSE").touch()
    assert ok.tick()["started"] == [] and read_json(ok.root / "status.json")["paused"]
    (ok.root / "PAUSE").unlink()
    cfg = repo / "config" / "manhattan.yaml"
    cfg.write_text(cfg.read_text().replace("real_money: false", "real_money: true"))
    out = ok.tick()
    assert out["started"] == [] and out["switches_closed"]
    cfg.write_text(cfg.read_text().replace("real_money: true", "real_money: false"))
    st = run_until(ok, settled)
    assert st["jobs"][jid]["status"] == "completed"
    types = [r["type"] for r in ok.journal.records()]
    assert "switches_closed" in types and "switches_open" in types


def test_secrets_never_reach_an_invocation(tmp_path, mini, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_should_never_be_seen")
    monkeypatch.setenv("DATA_REPO_READ_TOKEN", "should_never_be_seen")
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4, "chunk": 4, "faults": {"hang_at_unit": 0}})["job_id"]
    st = run_until(sup, lambda s: s["jobs"][jid]["status"] == "running"
                   and (sup.root / s["jobs"][jid]["invocations"][0]["inv_dir"] / "pid.json").exists())
    pid = read_json(sup.root / st["jobs"][jid]["invocations"][0]["inv_dir"] / "pid.json")["pid"]
    env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    assert not any(b"should_never_be_seen" in e for e in env)
    assert b"EM_MACRO_DATA=/nonexistent/em-macro-data" in env
    sup.cancel(jid)
    assert run_until(sup, settled)["jobs"][jid]["status"] == "cancelled"


# -- HTE (where the engine exists) ----------------------------------------------------------------------------

def _has_hte(repo: Path) -> bool:
    return (repo / "manhattan" / "hte" / "runner.py").exists()


@pytest.mark.skipif(not _has_hte(REPO), reason="manhattan.hte is not in this checkout (PR #89)")
def test_hte_job_survives_an_engine_crash_and_closes_with_an_anchored_log(tmp_path, mini):
    sup = sup_for(tmp_path, mini, max_total_workers=2)
    jid = sup.register("hte", {"target": 300, "chunk_size": 16, "workers": 2,
                               "test_fault": "exit_after_start:3"})["job_id"]
    st = run_until(sup, settled, timeout=300)
    j = st["jobs"][jid]
    assert j["status"] == "completed", j["reason"]
    assert [i["ended"]["outcome"] for i in j["invocations"]] == ["lost", "done"]
    rec = j["reconcile"]
    assert rec["state"] == "closed" and rec["violations"] == []
    assert rec["counts"]["attempts"]["interrupted"] >= 1                          # the engine kept the crash
    assert rec["access_reconciled"] is False and rec["independent_statistical_tests"] is None
    assert j["anchor"]["records"] > 0
    assert sup.audit(jid)["state"] == "closed"
