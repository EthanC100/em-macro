"""Manhattan orchestra: unit tests (journal, limits, lifecycle, safety guards, kinds, manifest, status, cost).

The process-level smoke and failure-injection tests are in tests/test_manhattan_orchestra_failures.py.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from manhattan.orchestra import cost as C
from manhattan.orchestra import kinds as K
from manhattan.orchestra import limits as L
from manhattan.orchestra import manifest as M
from manhattan.orchestra import safety
from manhattan.orchestra import state as ST
from manhattan.orchestra import status as S
from manhattan.orchestra.journal import FileLock, Journal, JournalError, is_held_elsewhere
from manhattan.orchestra.supervisor import decide

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "manhattan" / "orchestra"


# -- journal --------------------------------------------------------------------------------------------------

def test_journal_chain_detects_edits_and_truncation(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    with j.locked():
        for i in range(5):
            j.append("x", {"i": i})
    anchor = j.head()
    assert j.verify(anchor) == anchor
    lines = (tmp_path / "j.jsonl").read_bytes().splitlines(keepends=True)
    (tmp_path / "j.jsonl").write_bytes(b"".join(lines[:3]))            # suffix deleted
    with pytest.raises(JournalError, match="suffix deleted"):
        j.verify(anchor)
    edited = lines[1].replace(b'"i":1', b'"i":7')
    (tmp_path / "j.jsonl").write_bytes(lines[0] + edited + b"".join(lines[2:]))
    with pytest.raises(JournalError, match="edited"):
        j.records()


def test_journal_append_needs_the_lock_and_quarantines_a_torn_tail(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    with pytest.raises(JournalError, match="outside the journal lock"):
        j.append("x", {})
    with j.locked():
        j.append("x", {"i": 0})
    with open(tmp_path / "j.jsonl", "ab") as f:
        f.write(b'{"seq": 2, "type": "x", "pay')                       # a crash mid-append
    assert len(j.records()) == 1                                     # reading tolerates it
    with j.locked():
        j.append("x", {"i": 1})
    recs = j.records()
    assert [r["type"] for r in recs] == ["x", "journal_torn_tail", "x"]
    q = tmp_path / recs[1]["payload"]["quarantine"]
    assert q.read_bytes() == b'{"seq": 2, "type": "x", "pay'


def test_journal_lock_excludes_a_second_writer(tmp_path):
    a, b = Journal(tmp_path / "j.jsonl"), Journal(tmp_path / "j.jsonl")
    with a.locked():
        with pytest.raises(JournalError, match="busy"):
            with b.locked(timeout=0.1):
                pass
        a.append("x", {})
    with b.locked():
        b.append("y", {})                       # b re-reads: no stale seq
    assert [r["seq"] for r in a.records()] == [1, 2]


def test_file_lock_probe(tmp_path):
    p = tmp_path / ".lock"
    assert not is_held_elsewhere(p)
    lk = FileLock(p)
    assert lk.acquire()
    # a probe from this process uses a new open file description, so it sees the lock as held
    assert is_held_elsewhere(p)
    lk.release()
    assert not is_held_elsewhere(p)


# -- limits ---------------------------------------------------------------------------------------------------

def test_limits_override_can_only_tighten(tmp_path):
    d = L.DEFAULT
    t = d.tighten({"max_running_jobs": 1, "monthly_vcpu_hours": 100, "min_free_disk_mb": 9000,
                   "price_sgd_per_vcpu_hour": 0.07})
    assert (t.max_running_jobs, t.monthly_vcpu_hours, t.min_free_disk_mb) == (1, 100.0, 9000)
    for bad in ({"max_running_jobs": d.max_running_jobs + 1}, {"monthly_budget_sgd": 501},
                {"min_free_disk_mb": 1}, {"require_clean_tree": False}, {"cancel_grace_s": 1},
                {"no_such_limit": 1}, {"max_workers_per_job": -1}, {"max_running_jobs": True},
                {"max_memory_mb_per_job": 0}, {"max_wall_minutes_per_invocation": 0}, {"max_running_jobs": 0}):
        with pytest.raises(L.LimitsError):
            d.tighten(bad)
    (tmp_path / "limits.json").write_text(json.dumps({"max_total_workers": 2}))
    assert L.load(tmp_path).max_total_workers == 2
    (tmp_path / "limits.json").write_text(json.dumps({"max_total_workers": 999}))
    with pytest.raises(L.LimitsError, match="raise the ceiling"):
        L.load(tmp_path)


def test_backoff_is_exponential_and_capped():
    lim = L.Limits(backoff_base_s=60, backoff_max_s=600)
    assert [L.backoff_seconds(lim, k) for k in (1, 2, 3, 4, 5)] == [60, 120, 240, 480, 600]


# -- lifecycle decisions --------------------------------------------------------------------------------------

def _job(**kw):
    j = {"consecutive_errors": 0, "n_invocations": 1, "max_invocations": 5, "cancel": None}
    j.update(kw)
    return j


@pytest.mark.parametrize("outcome,expect", [
    ("done", "completed"), ("cancelled", "cancelled"), ("integrity", "failed"), ("refused", "failed"),
    ("blocked", "blocked"), ("duplicate_refused", "blocked"), ("foreign_host", "blocked"),
    ("unfinished", "retry_wait"), ("timeout", "retry_wait"), ("interrupted", "retry_wait"),
    ("lost", "retry_wait"), ("error", "retry_wait"), ("memory_exceeded", "retry_wait"),
    ("no_progress", "retry_wait"), ("lost_before_start", "retry_wait")])
def test_decide_outcomes(outcome, expect):
    assert decide(_job(), outcome, L.DEFAULT, 1000.0)["next_status"] == expect


def test_decide_error_cap_backoff_and_invocation_cap():
    lim = L.Limits(max_consecutive_errors=3, backoff_base_s=10, backoff_max_s=100)
    d = decide(_job(consecutive_errors=1), "error", lim, 1000.0)
    assert d["next_status"] == "retry_wait" and d["consecutive_errors"] == 2 and d["not_before_epoch"] == 1020.0
    assert decide(_job(consecutive_errors=2), "error", lim, 0)["next_status"] == "failed"
    d = decide(_job(consecutive_errors=2), "timeout", lim, 0)
    assert d["consecutive_errors"] == 0 and d["not_before_epoch"] == 0.0             # a timeout resets errors
    assert decide(_job(n_invocations=5), "timeout", lim, 0)["next_status"] == "incomplete"
    assert decide(_job(n_invocations=5), "done", lim, 0)["next_status"] == "completed"


def test_fold_lifecycle():
    def rec(seq, t, **p):
        return {"seq": seq, "type": t, "payload": p, "ts_utc": "x"}
    reg = dict(job_id="J", kind="smoke", params={}, identity={}, identity_sha256="h", max_invocations=3, workers=1)
    recs = [rec(1, "job_registered", **reg),
            rec(2, "invocation_intent", job_id="J", n=1, intent_epoch=0, deadline_epoch=99, workers=1,
                inv_dir="jobs/J/inv-0001")]
    st = ST.fold(recs)["jobs"]["J"]
    assert (st["status"], st["category"]) == ("launching", "active")
    recs.append(rec(3, "invocation_started", job_id="J", n=1, pid=1))
    recs.append(rec(4, "cancel_requested", job_id="J", reason="r"))
    assert ST.fold(recs)["jobs"]["J"]["status"] == "cancelling"
    recs.append(rec(5, "invocation_ended", job_id="J", n=1, outcome="cancelled", ended_epoch=1.7e9,
                    reserved_vcpu_h=0.5, consecutive_errors=0, next_status="cancelled"))
    f = ST.fold(recs)
    assert f["jobs"]["J"]["status"] == "cancelled" and f["jobs"]["J"]["open_invocation"] is None
    assert sum(f["usage"].values()) == 0.5
    recs.append(rec(6, "job_requeued", job_id="J", extra_invocations=2))
    j = ST.fold(recs)["jobs"]["J"]
    assert (j["status"], j["max_invocations"], j["cancel"]) == ("queued", 5, None)


# -- safety ---------------------------------------------------------------------------------------------------

def test_child_env_is_an_allowlist():
    base = {"PATH": "/bin", "HOME": "/h", "GH_TOKEN": "s", "DATA_REPO_READ_TOKEN": "s", "AWS_SECRET_ACCESS_KEY": "s",
            "MANHATTAN_LEDGER_DEPLOY_KEY": "s", "ANTHROPIC_API_KEY": "s", "SSH_AUTH_SOCK": "/x", "LC_ALL": "C",
            "HTE_FAULT": "exit_after_start:1", "HTTPS_PROXY": "http://real-proxy"}
    env, dropped = safety.child_env(base)
    assert dropped == 8                     # all but PATH, HOME and LC_ALL
    assert not any(v == "s" for v in env.values())
    assert "HTE_FAULT" not in env and "SSH_AUTH_SOCK" not in env
    assert env["HTTPS_PROXY"] == safety.CLOSED_PROXY and env["EM_MACRO_DATA"] == safety.NONEXISTENT_STORE
    assert env["OPENBLAS_NUM_THREADS"] == "1" and env["LC_ALL"] == "C"


def test_root_must_be_outside_the_repository(tmp_path):
    with pytest.raises(safety.Refused, match="absolute"):
        safety.check_root(Path("relative/root"))
    for bad in (REPO, REPO / "results" / "orchestra", REPO / "data" / "ledger", REPO.parent):
        with pytest.raises(safety.Refused, match="outside the repository"):
            safety.check_root(bad)
    assert safety.check_root(tmp_path / "root") == (tmp_path / "root").resolve()


def test_switches_open_on_main_config_and_closed_when_anything_is_activated(tmp_path):
    assert safety.manhattan_switches(REPO) == []
    cfg = (REPO / "config" / "manhattan.yaml").read_text()
    for old, new in (("enabled: false               # no screening", "enabled: true               # no screening"),
                     ("real_money: false", "real_money: true"), ("loss_cap_usd: 0", "loss_cap_usd: 500"),
                     ("evaluate_adaptive: false", "evaluate_adaptive: true"),
                     ("authority: ethan_only", "authority: delegated"),
                     ("count_in_trials_csv: false", "count_in_trials_csv: true"),
                     ("  enabled: false               # stays false", "  enabled: true               # stays false")):
        assert old in cfg
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "config" / "manhattan.yaml").write_text(cfg.replace(old, new))
        assert safety.manhattan_switches(tmp_path), old
    (tmp_path / "config" / "manhattan.yaml").write_text("::: not yaml")
    assert safety.manhattan_switches(tmp_path)                       # unreadable: fail closed
    shutil.rmtree(tmp_path / "config")
    assert safety.manhattan_switches(tmp_path)                       # missing: fail closed


FORBIDDEN_IMPORTS = ("manhattan.ops", "manhattan.ledger", "manhattan.freeze", "manhattan.critic", "manhattan.roles",
                     "ledger", "nightshift", "em_macro", "janus", "lab", "requests", "urllib", "http.client",
                     "smtplib", "ftplib", "boto3", "botocore", "paramiko", "github", "manhattan.hte.protected",
                     "manhattan.hte.adapters", "manhattan.execution")


def _imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


def test_orchestra_imports_no_access_layer_no_network_client_and_no_writer():
    for f in sorted(PKG.glob("*.py")):
        for name in _imports(f):
            assert not any(name == b or name.startswith(b + ".") for b in FORBIDDEN_IMPORTS), (f.name, name)


def test_orchestra_runs_no_git_write_no_dispatch_and_only_its_own_child():
    for f in sorted(PKG.glob("*.py")):
        src = f.read_text()
        for word in ("git push", "\"push\"", "workflow_dispatch", "gh api", "\"gh\"", "promote", "--force",
                     "force=True",
                     "allow_test_templates=True", "allow_new_environment", "verify_rerun=False"):
            assert word not in src, (f.name, word)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "_git":
                first = node.args[0]
                assert isinstance(first, ast.Constant) and first.value in ("ls-files", "rev-parse", "status"), f.name
            if isinstance(node, ast.Attribute) and node.attr in ("Popen", "run", "call", "check_output") and \
                    getattr(node.value, "id", "") == "subprocess":
                assert f.name in ("supervisor.py", "manifest.py", "procs.py"), f.name
            if f.name == "procs.py" and isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_cmd":
                assert node.args[0].value in ("ioreg", "sysctl", "ps", "mount"), node.args[0].value


def test_status_server_refuses_a_non_loopback_address(tmp_path):
    with pytest.raises(PermissionError, match="loopback"):
        S.serve_http(tmp_path, host="0.0.0.0", port=0)


# -- kinds ----------------------------------------------------------------------------------------------------

def test_kind_allowlist_and_strict_parameters():
    with pytest.raises(K.ParamError, match="unknown job kind"):
        K.get("shell")
    sm = K.get("smoke")
    assert sm.normalise({})["units"] == 64
    for bad in ({"units": 0}, {"units": True}, {"rm": 1}, {"faults": {"format_disk": 1}}, {"workers": 2},
                {"fault_invocations": [0]}):
        with pytest.raises(K.ParamError):
            sm.normalise(bad)
    assert sm.normalise({"sleep_per_chunk_s": 1})["sleep_per_chunk_s"] == 1.0


def test_hte_kind_refuses_stage_5_and_every_policy_or_template_override():
    h = K.get("hte")
    assert h.normalise({"stages": [3, 1, 2, 4]})["stages"] == [1, 2, 3, 4]
    for bad in ({"stages": [1, 2, 3, 4, 5]}, {"stages": [5]}, {"stages": [2, 3]}, {"policy": {"top_k": 5}},
                {"allow_test_templates": True}, {"benchmark_only": True}, {"registry_root": "x"},
                {"allow_new_environment": True}, {"test_fault": "rm -rf"}, {"target": 10**9}):
        with pytest.raises(K.ParamError):
            h.normalise(bad)


def test_sim_kind_refuses_held_out_confirmation_and_pooled_reruns():
    s = K.get("sim")
    ok = s.normalise({"scenario": "D01", "size": "STD", "reps": 2, "label": "pilot"})
    assert ok["prereg"] == "v2"
    assert s.normalise({"scenario": "D01h", "size": "STD", "reps": 400})["scenario"] == "D01h"
    for bad in ({"scenario": "H01", "size": "STD", "reps": 2}, {"scenario": "H11", "size": "HB", "reps": 2},
                {"scenario": "D01", "size": "STD", "reps": 2, "confirm": 1},
                {"scenario": "D01", "size": "STD", "reps": 2, "pooled_rerun": True},
                {"scenario": "D01", "size": "STD", "reps": 2, "plan": "development"},
                {"scenario": "D01", "size": "STD", "reps": 2, "out": "/repo/results"},
                {"scenario": "D01", "size": "XL", "reps": 2}, {"scenario": "ZZ", "size": "STD", "reps": 2},
                {"scenario": "D01", "size": "STD", "reps": 2, "first": 3}):
        with pytest.raises(K.ParamError):
            s.normalise(bad)


def test_sim_reconciliation_counts_replications_and_flags_duplicates(tmp_path):
    from manhattan.sim import run as SR
    s = K.get("sim")
    p = s.normalise({"scenario": "D01", "size": "STD", "reps": 3, "label": "pilot"})
    code = SR.code_hash("STD", version=SR.route("D01", "STD", "v2"))
    reps = tmp_path / "sim_out" / "reps"
    reps.mkdir(parents=True)
    rows = [{"rep": 0, "code": code}, {"rep": 1, "code": code}, {"rep": 2, "code": "other-code"}]
    (reps / "D01_STD_0.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "sim_out" / "runs.jsonl").write_text(json.dumps({"event": "start", "run_id": "a"}) + "\n")
    rec = s.reconcile(p, tmp_path, None)
    assert rec["state"] == "incomplete" and rec["counts"]["on_file"] == 2 and rec["counts"]["run_log_abandoned"] == 1
    with open(reps / "D01_STD_0.jsonl", "a") as f:
        f.write(json.dumps({"rep": 2, "code": code}) + "\n" + json.dumps({"rep": 1, "code": code}) + "\n")
    rec = s.reconcile(p, tmp_path, None)
    assert rec["state"] == "corrupted" and rec["violations"][0]["code"] == "duplicate_replication"


# -- manifest -------------------------------------------------------------------------------------------------

def _mini(tmp_path) -> Path:
    r = tmp_path / "repo"
    (r / "manhattan").mkdir(parents=True)
    (r / "manhattan" / "a.py").write_text("x = 1\n")
    (r / "requirements.txt").write_text("numpy\n")
    return r


def test_manifest_identity_follows_code_content(tmp_path):
    r = _mini(tmp_path)
    a = M.build({"k": 1}, r)
    assert M.build({"k": 1}, r)["identity"] == a["identity"]
    (r / "manhattan" / "a.py").write_text("x = 2\n")
    b = M.build({"k": 1}, r)
    assert M.compare(a["identity"], b["identity"]) == "code_changed"
    (r / "manhattan" / "a.py").write_text("x = 1\n")
    (r / "manhattan" / "new.py").write_text("")                     # an added module changes it too
    assert M.compare(a["identity"], M.build({"k": 1}, r)["identity"]) == "code_changed"
    (r / "manhattan" / "new.py").unlink()
    assert M.compare(a["identity"], M.build({"k": 2}, r)["identity"]) == "job_spec_changed"
    env = dict(a["identity"], numeric_environment_sha256="other")
    assert M.compare(a["identity"], env) == "environment_changed"
    assert M.compare(a["identity"], env, strict_environment=False) is None
    assert a["numeric_environment"]["threads"]["OPENBLAS_NUM_THREADS"] == "1"


def test_manifest_of_this_checkout_names_the_commit():
    m = M.build({"kind": None})
    assert len(m["code"]["commit"]) == 40 and m["code"]["files"] > 50
    assert m["numeric_environment"]["numpy"] and m["packages"]


# -- status and cost ------------------------------------------------------------------------------------------

def test_status_snapshot_health_and_http(tmp_path):
    from manhattan.orchestra.supervisor import Supervisor
    sup = Supervisor(tmp_path / "root", limits=L.Limits(require_clean_tree=False), check_switches=False)
    sup.register("smoke", {"units": 4})
    snap = S.snapshot(sup.root)
    assert snap["schema"] == "manhattan-orchestra/1" and snap["evidence"] is None
    assert set(snap["counts"]) == set(ST.CATEGORIES) and snap["counts"]["queued"] == 1
    assert snap["journal"]["records"] == len(sup.journal.records())
    line, rc = S.health(snap)
    assert rc == 2 and "SUPERVISOR SILENT" in line                       # queued work, no tick yet
    sup.pause("maintenance")
    sup.tick()
    snap = S.snapshot(sup.root)
    assert snap["paused"] and not snap["supervisor"]["stale"] and snap["counts"]["active"] == 0
    assert S.health(snap)[1] == 0 and "PAUSED" in S.health(snap)[0]
    assert "smoke units=4" in S.render(snap)
    blob = json.dumps(snap)
    assert "GH_TOKEN" not in blob and "PATH" not in blob

    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    th = threading.Thread(target=S.serve_http, args=(sup.root,), kwargs={"port": port, "max_requests": 2})
    th.start()
    time.sleep(0.3)
    try:
        got = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/status.json", timeout=5).read())
        assert got["counts"]["queued"] == 1
        req = urllib.request.Request(f"http://127.0.0.1:{port}/status.json", data=b"x", method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        assert e.value.code == 405
    finally:
        th.join(timeout=5)


def test_cost_table_against_the_budget():
    t = {r["option"]: r for r in C.table(C.WORKLOADS["sim_development_programme"]["vcpu_h"])}
    assert t["owned_hardware"]["sgd"] == 0 and t["github_public_runners"]["sgd"] == 0
    assert t["aws_c7a_2xlarge_on_demand"]["sgd"] < 500                 # the whole programme fits one month
    assert t["hetzner_ax42_dedicated"]["fits_one_month"] is True
    assert C.vcpu_hours_for_budget("aws_c7a_2xlarge_on_demand") > 5000
    assert C.vcpu_hours_for_budget("hetzner_ax42_dedicated") is None    # flat rent below the budget
    assert C.monthly("owned_hardware", 100 * C.WORKLOADS["hte_1m_full"]["vcpu_h"])["sgd"] == 0


# -- review findings (S15 independent read) --------------------------------------------------------------------

def test_members_match_only_this_invocation_on_proc_and_on_ps(tmp_path):
    import subprocess
    import sys
    from manhattan.orchestra import procs
    from manhattan.orchestra.supervisor import _members
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "manhattan.orchestra.child",
                          str(tmp_path / "inv-0001")], start_new_session=True)
    try:
        time.sleep(0.3)
        assert _members(p.pid, tmp_path / "inv-0001") == [p.pid]
        assert _members(p.pid, tmp_path / "inv-0002") == []                 # another invocation: never killed
        via_ps = procs.group(p.pid, use_proc=False)                         # the macOS path, run on Linux
        assert [x[0] for x in via_ps] == [p.pid] and via_ps[0][1] > 0
        assert via_ps[0][1] == pytest.approx(procs.group(p.pid, use_proc=True)[0][1], rel=0.5)
    finally:
        p.kill()
        p.wait()


def test_host_facts():
    from manhattan.orchestra import procs
    assert procs.machine_id() and procs.boot_id() != "unknown"
    assert procs.fs_type(REPO) is not None


def test_a_pending_cancel_never_hides_integrity_refusal_or_block(tmp_path):
    from manhattan.orchestra.supervisor import Supervisor
    sup = Supervisor(tmp_path / "root", limits=L.Limits(require_clean_tree=False), check_switches=False)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    now = time.time()
    with sup.journal.locked():
        sup.journal.append("invocation_intent", {"job_id": jid, "n": 1, "inv_dir": f"jobs/{jid}/inv-0001",
                                                 "workers": 1, "intent_epoch": now, "deadline_epoch": now + 60})
        sup.journal.append("cancel_requested", {"job_id": jid, "reason": "r"})
        j = sup.state()["jobs"][jid]
        sup._end(j, j["open_invocation"], {"outcome": "integrity", "exit_code": 65, "reason": "anchor"}, now,
                 {"ended": []})
    j = sup.state()["jobs"][jid]
    assert j["status"] == "failed" and j["reason"].startswith("integrity")


def test_budget_counts_the_whole_window_of_running_invocations():
    from manhattan.orchestra.supervisor import reserved_window
    inv = {"workers": 2, "intent_epoch": 1000.0, "deadline_epoch": 1000.0 + 3600}
    assert reserved_window(inv) == 2.0                  # time already used still counts until the invocation ends
