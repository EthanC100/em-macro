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
# Linux (CI: tests / pytest) and macOS (CI: orchestra-macos, a GitHub-hosted Mac): the same tests, so that every
# behaviour they check is verified on both systems, not only reasoned about for macOS
pytestmark = pytest.mark.skipif(sys.platform not in ("linux", "darwin"), reason="POSIX process groups: Linux, macOS")


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
    with pytest.raises(Exception, match="pass extra_invocations"):
        sup.requeue(jid)                                                          # at its cap: say how many more
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


@pytest.mark.skipif(not Path("/proc/self/environ").exists(), reason="reads /proc/<pid>/environ (Linux)")
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


def test_a_directory_left_by_a_crash_before_the_intent_does_not_wedge_the_root(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    stale = sup.job_dir(jid) / "inv-0001"
    stale.mkdir()
    (stale / "invocation.json").write_text("{}")                      # mkdir and spec written, intent never
    st = run_until(sup, settled)
    assert st["jobs"][jid]["status"] == "completed"
    assert (sup.job_dir(jid) / "inv-0001.orphan-0" / "invocation.json").exists()      # kept, renamed
    assert [r["payload"]["renamed_to"] for r in sup.journal.records() if r["type"] == "orphan_invocation_dir"] == \
        ["inv-0001.orphan-0"]


def test_limits_file_is_reread_every_tick_and_a_bad_one_stops_starts(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    a = sup.register("smoke", {"units": 4})["job_id"]
    (sup.root / "limits.json").write_text(json.dumps({"max_running_jobs": 0}))       # 0 is refused, not "off"
    out = sup.tick()
    assert out["started"] == [] and out["limits_ok"] is False
    snap = read_json(sup.root / "status.json")
    assert "must be positive" in snap["limits_error"]
    from manhattan.orchestra import status as S
    assert S.health(snap)[1] == 1
    (sup.root / "limits.json").write_text(json.dumps({"max_running_jobs": 1, "monthly_vcpu_hours": 0.001}))
    out = sup.tick()
    assert out["limits_ok"] and out["started"] == [] and "budget" in out["deferred"][0]["reason"]
    assert sup.limits.max_running_jobs == 1 and read_json(sup.root / "status.json")["limits_error"] is None
    (sup.root / "limits.json").unlink()
    assert run_until(sup, settled)["jobs"][a]["status"] == "completed"


def test_running_invocations_hold_their_whole_window_against_the_budget(tmp_path, mini):
    offset = [0.0]
    sup = sup_for(tmp_path, mini, clock=lambda: time.time() + offset[0], monthly_vcpu_hours=1.0,
                  max_wall_minutes_per_invocation=40)
    a = sup.register("smoke", {"units": 4, "faults": {"hang_at_unit": 0}})["job_id"]
    b = sup.register("smoke", {"units": 5})["job_id"]
    out = sup.tick()
    assert out["started"] == [a] and "budget" in out["deferred"][0]["reason"]
    run_until(sup, lambda st: (sup.root / st["jobs"][a]["invocations"][0]["inv_dir"] / "pid.json").exists())
    offset[0] = 35 * 60.0                                             # 35 minutes into A's 40-minute window
    out = sup.tick()
    assert out["started"] == [] and out["deferred"][0]["job_id"] == b
    offset[0] = 0.0
    sup.cancel(a)
    run_until(sup, lambda st: st["jobs"][a]["status"] == "cancelled")



def test_an_invalid_limits_file_stops_starts_but_never_supervision(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 8, "chunk": 4, "sleep_per_chunk_s": 1.0})["job_id"]
    run_until(sup, lambda st: st["jobs"][jid]["status"] == "running")
    other = sup.register("smoke", {"units": 3})["job_id"]
    (sup.root / "limits.json").write_text('{"monthly_vcpu_hours": NaN}')
    st = run_until(sup, lambda s: s["jobs"][jid]["status"] == "completed")     # its exit is still imported
    assert st["jobs"][other]["status"] == "queued"
    assert [r["type"] for r in sup.journal.records()].count("limits_invalid") == 1
    (sup.root / "limits.json").unlink()
    assert run_until(sup, settled)["jobs"][other]["status"] == "completed"


def test_orphan_names_skip_any_that_exist(tmp_path, mini):
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    for name in ("inv-0001", "inv-0001.orphan-1"):                 # orphan-0 was deleted by a person earlier
        (sup.job_dir(jid) / name).mkdir()
        (sup.job_dir(jid) / name / "invocation.json").write_text("{}")
    assert run_until(sup, settled)["jobs"][jid]["status"] == "completed"
    assert (sup.job_dir(jid) / "inv-0001.orphan-0" / "invocation.json").exists()
    assert (sup.job_dir(jid) / "inv-0001.orphan-1" / "invocation.json").exists()


def test_serve_survives_a_failing_tick(tmp_path, mini, capsys):
    sup = sup_for(tmp_path, mini)
    real, calls = sup.tick, []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("disk hiccup")
        return real()
    sup.tick = flaky
    sup.serve(interval=0.01, max_ticks=2)
    assert len(calls) == 2 and "disk hiccup" in capsys.readouterr().err


# -- second re-review ----------------------------------------------------------------------------------------------

def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    st = Path(f"/proc/{pid}/stat")
    if st.exists():                                                   # a zombie is not alive
        return st.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    return True


def test_spawn_workers_of_a_dead_invocation_are_killed_before_the_next_starts(tmp_path, mini):
    """macOS starts pool workers by spawn: their command lines do not name the invocation. The invocation records
    them (members.json, pid and start time); after it dies, the supervisor kills them, and a new invocation never
    starts while one is alive."""
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 12, "chunk": 4, "sleep_per_chunk_s": 1.5,
                                 "faults": {"spawn_helper": 1, "crash_at_unit": 9}})["job_id"]
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert [i["ended"]["outcome"] for i in j["invocations"]] == ["lost", "done"] and j["status"] == "completed"
    helper = int((sup.job_dir(jid) / "work" / "helper-1.pid").read_text())
    members = read_json(sup.root / j["invocations"][0]["inv_dir"] / "members.json")
    assert helper in [m[0] for m in members]                          # recorded while the invocation lived
    end = time.time() + 10
    while _alive(helper) and time.time() < end:
        time.sleep(0.2)
    assert not _alive(helper)                                         # killed although it never named the invocation


def test_a_bad_limits_file_present_at_start_never_stops_supervision(tmp_path, mini):
    from manhattan.orchestra.limits import LimitsError
    root = tmp_path / "root"
    root.mkdir()
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 8, "chunk": 4, "faults": {"hang_at_unit": 4}})["job_id"]
    run_until(sup, lambda s: s["jobs"][jid]["status"] == "running"
              and (sup.root / s["jobs"][jid]["invocations"][0]["inv_dir"] / "pid.json").exists())
    (root / "limits.json").write_text('{"max_memory_mb_per_job": 0}')
    fresh = sup_for(tmp_path, mini)                                   # a cron tick builds a new supervisor
    assert fresh.limits_error and "positive" in fresh.limits_error
    with pytest.raises(LimitsError, match="registration waits"):
        fresh.register("smoke", {"units": 3})
    fresh.cancel(jid, "operator")                                     # cancels are still recorded and delivered
    st = run_until(fresh, lambda s: s["jobs"][jid]["status"] == "cancelled")
    assert read_json(fresh.root / "status.json")["limits_error"]
    from manhattan.orchestra import __main__ as CLI
    assert CLI.main(["--root", str(root), "health"]) == 1               # attention, not "supervisor silent"


def test_a_child_started_by_hand_leads_its_own_process_group(tmp_path, mini, monkeypatch):
    import subprocess
    sup = sup_for(tmp_path, mini)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("not now")))
    with sup.journal.locked():
        sup._start(sup.state()["jobs"][jid], time.time())             # writes invocation.json; the spawn "fails"
    monkeypatch.undo()
    inv = sup.root / sup.state()["jobs"][jid]["invocations"][0]["inv_dir"]
    env, _ = __import__("manhattan.orchestra.safety", fromlist=["x"]).child_env()
    r = subprocess.run([sys.executable, "-m", "manhattan.orchestra.child", str(inv)], cwd=mini, env=env)
    assert r.returncode == 0                                          # same process group as this test, at first
    pid = read_json(inv / "pid.json")
    assert pid["pgid"] == pid["pid"] != os.getpgid(0)                 # it moved to a group of its own


def test_an_unreadable_process_table_stops_the_invocation(tmp_path):
    repo = make_repo(tmp_path / "own-repo")
    p = repo / "manhattan" / "orchestra" / "procs.py"
    p.write_text(p.read_text().replace('''    use_proc = PROC.is_dir()''', '''    raise ProcsUnavailable("test")
    use_proc = PROC.is_dir()''', 1))
    c = repo / "manhattan" / "orchestra" / "child.py"
    c.write_text(c.read_text().replace("UNMEASURABLE_AFTER_S = 30", "UNMEASURABLE_AFTER_S = 2", 1))
    sup = sup_for(tmp_path, repo, max_consecutive_errors=1)
    jid = sup.register("smoke", {"units": 4, "chunk": 4, "faults": {"hang_at_unit": 0}})["job_id"]
    st = run_until(sup, settled)
    j = st["jobs"][jid]
    assert j["invocations"][0]["ended"]["outcome"] == "memory_unmeasurable" and j["status"] == "failed"
