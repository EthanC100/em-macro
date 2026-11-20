"""Manhattan orchestra: unit tests (journal, limits, lifecycle, safety guards, kinds, manifest, status, cost).

The process-level smoke and failure-injection tests are in tests/test_manhattan_orchestra_failures.py.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sys
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
                {"max_memory_mb_per_job": 0}, {"max_wall_minutes_per_invocation": 0}, {"max_running_jobs": 0},
                {"max_memory_mb_per_job": 0.5}, {"max_log_mb_per_invocation": 0.9},
                {"monthly_vcpu_hours": float("nan")}, {"min_free_disk_mb": float("inf")},
                {"monthly_vcpu_hours": float("inf")}, {"max_running_jobs": "1"}, {"min_free_disk_mb": 10**400},
                {"monthly_vcpu_hours": 10**400}):
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
                     "manhattan.hte.adapters", "manhattan." + "execution")   # split: main scans every file for the dotted name


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

    srv = S.make_server(sup.root, port=0)                  # bound and listening on return: no race, no sleep
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)     # a failure can never hang the test run
    th.start()
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never a system proxy (macOS)
    try:
        got = json.loads(direct.open(f"http://127.0.0.1:{port}/status.json", timeout=10).read())
        assert got["counts"]["queued"] == 1
        assert direct.open(f"http://127.0.0.1:{port}/health", timeout=10).status == 200
        req = urllib.request.Request(f"http://127.0.0.1:{port}/status.json", data=b"x", method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            direct.open(req, timeout=10)
        assert e.value.code == 405
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(timeout=10)


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
        assert [x.pid for x in via_ps] == [p.pid] and via_ps[0].rss > 0 and via_ps[0].start.startswith("lstart:")
        if Path("/proc/self/stat").exists():
            assert via_ps[0].rss == pytest.approx(procs.group(p.pid, use_proc=True)[0].rss, rel=0.5)
    finally:
        p.kill()
        p.wait()


def test_host_facts():
    from manhattan.orchestra import procs
    assert procs.machine_id() and procs.boot_id()
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


# -- re-review (S15, after the merge of PR #89 and PR #99) -------------------------------------------------------

MAC_MOUNT = """/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)
devfs on /dev (devfs, local, nobrowse)
/dev/disk3s5 on /System/Volumes/Data (apfs, local, journaled, nobrowse, protect)
map auto_home on /System/Volumes/Data/home (autofs, automounted, nobrowse)
//ethan@nas._smb._tcp.local/research on /Volumes/research (smbfs, nodev, nosuid, mounted by ethan)
afp_0TQBbz0x9ZmA0d4V0J3s1@nas.local/old on /Volumes/old (afpfs, nodev, nosuid, mounted by ethan)
https://dav.example.org/files on /Volumes/files (webdav, nodev, noexec, nosuid, mounted by ethan)
sshfs@macfuse0 on /Volumes/remote (macfuse, nodev, nosuid, synchronous, mounted by ethan)
nas.local:/export/data on /Volumes/data (nfs, nodev, nosuid, mounted by ethan)
/dev/disk5s1 on /Volumes/Fast SSD (apfs, local, nodev, nosuid, journaled, noowners)
"""
MAC_IOREG = """+-o J456AP  <class IOPlatformExpertDevice, id 0x100000243, registered, matched, active, busy 0 (14 ms)>
    {
      "IOPlatformSerialNumber" = "C02XXXXXXX"
      "IOPlatformUUID" = "8A2B0C77-1F3E-4D2A-9C1B-3E5F6A7B8C9D"
    }
"""
INV = "/Users/ethan/orchestra/jobs/OJ-1/inv-0003"
T = "Fri Nov 20 01:02:03 2026"
MAC_PS = (f"  501   501  204800 {T} /usr/local/bin/python3 -m manhattan.orchestra.child {INV}\n"
          f"  502   501  102400 {T} /usr/local/bin/python3 -m manhattan.orchestra.child {INV}\n"
          f"  503   501    1024 {T} /bin/sleep 100\n"
          f"  504   501   51200 {T} /usr/local/bin/python3 -c from multiprocessing.spawn import spawn_main; "
          f"spawn_main(tracker_fd=5, pipe_handle=7) --multiprocessing-fork\n"
          f"  505   501    2048 {T} /usr/local/bin/python3 -m manhattan.orchestra.child /x{INV}\n"
          f"  601   601  999999 {T} /usr/local/bin/python3 -m manhattan.orchestra.child {INV[:-1]}4\n")


@pytest.fixture
def macos(monkeypatch, tmp_path):
    """No /proc, and the macOS tools answer with recorded output."""
    from manhattan.orchestra import procs
    monkeypatch.setattr(procs, "PROC", tmp_path / "no-proc")
    real_read = Path.read_text

    def read_text(self, *a, **kw):
        if str(self) in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            raise FileNotFoundError(str(self))
        return real_read(self, *a, **kw)
    monkeypatch.setattr(Path, "read_text", read_text)
    answers = {("mount",): MAC_MOUNT, ("ioreg", "-rd1", "-c", "IOPlatformExpertDevice"): MAC_IOREG,
               ("ps", "-A", "-o", "pid=,pgid=,rss=,lstart=,command="): MAC_PS,
               ("sysctl", "-n", "kern.bootsessionuuid"): "6F1B2C3D-0000-4E5F-8A9B-112233445566\n"}
    calls = []

    def cmd(*args, timeout=10.0):
        calls.append(args)
        return answers.get(tuple(args))
    monkeypatch.setattr(procs, "_cmd", cmd)
    return {"answers": answers, "calls": calls}


def test_macos_identity_from_ioreg_and_boot_session(macos):
    from manhattan.orchestra import procs
    assert procs.machine_id() == "8A2B0C77-1F3E-4D2A-9C1B-3E5F6A7B8C9D"
    assert procs.boot_id() == "bootsession:6F1B2C3D-0000-4E5F-8A9B-112233445566"
    del macos["answers"][("sysctl", "-n", "kern.bootsessionuuid")]
    macos["answers"][("sysctl", "-n", "kern.boottime")] = "{ sec = 1763500000, usec = 4221 } Thu Nov 19 04:00:00 2026\n"
    a = procs.boot_id()
    macos["answers"][("sysctl", "-n", "kern.boottime")] = "{ sec = 1763500000, usec = 4221 } Thu Nov 19 12:00:00 2026\n"
    assert a == procs.boot_id() == "boottime:1763500000"        # the local-time text (TZ) never changes it
    del macos["answers"][("ioreg", "-rd1", "-c", "IOPlatformExpertDevice")]
    del macos["answers"][("sysctl", "-n", "kern.boottime")]
    assert procs.machine_id() is None and procs.boot_id() is None  # unknown, never the hostname


def test_macos_group_memory_and_members_from_ps(macos):
    from manhattan.orchestra import procs
    from manhattan.orchestra.child import group_rss_mb
    from manhattan.orchestra.supervisor import _members
    g = procs.group(501)
    assert [(p.pid, p.rss) for p in g] == [(501, 204800 * 1024), (502, 102400 * 1024), (503, 1024 * 1024),
                                           (504, 51200 * 1024), (505, 2048 * 1024)]
    assert all(p.start == "lstart:" + T for p in g)
    assert group_rss_mb(501) == pytest.approx((204800 + 102400 + 1024 + 51200 + 2048) / 1024)   # KiB -> MiB
    assert _members(501, Path(INV)) == [501, 502]       # not the sleep, not the root /x... (exact last argument)
    assert _members(601, Path(INV)) == []                          # another invocation, another group


def test_macos_spawn_workers_are_matched_only_by_their_recorded_start(macos, tmp_path):
    """Spawn-mode workers (macOS's default) do not name the invocation: they match only through members.json, by
    pid *and* start time, so a reused pid does not."""
    from manhattan.orchestra.journal import atomic_write_json
    from manhattan.orchestra.supervisor import _members
    inv = tmp_path / "inv-0001"
    old = INV
    macos["answers"][("ps", "-A", "-o", "pid=,pgid=,rss=,lstart=,command=")] = MAC_PS.replace(old, str(inv))
    atomic_write_json(inv / "members.json", [[504, "lstart:" + T]])
    assert _members(501, inv) == [501, 502, 504]
    atomic_write_json(inv / "members.json", [[504, "lstart:Thu Nov 19 09:00:00 2026"]])     # same pid, reused
    assert _members(501, inv) == [501, 502]


def test_an_unreadable_process_table_is_never_an_empty_group(macos):
    from manhattan.orchestra import procs
    from manhattan.orchestra.child import group_rss_mb
    from manhattan.orchestra.supervisor import _members
    del macos["answers"][("ps", "-A", "-o", "pid=,pgid=,rss=,lstart=,command=")]
    with pytest.raises(procs.ProcsUnavailable):
        procs.group(501)
    with pytest.raises(procs.ProcsUnavailable):
        group_rss_mb(501)                                   # the monitor counts this, then stops the invocation
    assert _members(501, Path(INV)) == []                   # nothing verified, nothing killed; retried next tick


def test_macos_network_volumes_are_refused_and_local_ones_accepted(macos, monkeypatch, tmp_path):
    from manhattan.orchestra import procs
    want = {"/Users/ethan/orchestra": "apfs", "/private/tmp/orchestra": "apfs", "/Volumes/Fast SSD/o": "apfs",
            "/Volumes/research/o": "smbfs", "/Volumes/old/o": "afpfs", "/Volumes/files/o": "webdav",
            "/Volumes/remote/o": "macfuse", "/Volumes/data/o": "nfs", "/System/Volumes/Data/home/e/o": "autofs"}
    for path, typ in want.items():
        assert procs.fs_type(Path(path)) == typ, path
        assert safety.is_network_fs(typ) is (typ != "apfs"), typ
    for typ in ("osxfuse", "fuse.sshfs", "fuse", "nfs4", "smb3", "davfs", None):
        assert safety.is_network_fs(typ), typ
    for typ in ("apfs", "hfs", "ext4", "xfs", "btrfs", "zfs", "tmpfs", "fuseblk"):
        assert not safety.is_network_fs(typ), typ
    for typ in ("smbfs", "afpfs", "webdav", "macfuse", "autofs", None):
        monkeypatch.setattr(procs, "fs_type", lambda p, t=typ: t)
        with pytest.raises(safety.Refused, match="local disk"):
            safety.check_root(tmp_path / "root")


def test_macos_tools_are_called_by_absolute_path_with_a_fixed_path(monkeypatch, tmp_path):
    import subprocess
    from manhattan.orchestra import procs
    exe = tmp_path / "sysctl"
    exe.write_text("#!/bin/sh\necho x\n")
    exe.chmod(0o755)
    monkeypatch.setitem(procs.TOOLS, "sysctl", ("/nonexistent/sysctl", str(exe)))
    assert procs.tool("sysctl") == str(exe)
    assert procs.tool("no-such-tool") == "no-such-tool"
    seen = {}

    def run(args, **kw):
        seen["args"], seen["env"] = args, kw.get("env")
        return subprocess.CompletedProcess(args, 0, b"ok\n", b"")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")                    # cron's PATH: no /usr/sbin, no /sbin
    assert procs._cmd("sysctl", "-n", "kern.bootsessionuuid") == "ok\n"
    assert seen["args"][0] == str(exe) and "/usr/sbin" in seen["env"]["PATH"]


def test_peak_rss_units_per_platform():
    from manhattan.orchestra.child import maxrss_mb
    assert maxrss_mb(300 * 2**20, "darwin") == 300.0              # bytes on macOS
    assert maxrss_mb(300 * 1024, "linux") == 300.0                 # KiB on Linux


def test_numeric_switch_positions_compare_by_value(tmp_path):
    cfg = (REPO / "config" / "manhattan.yaml").read_text()
    (tmp_path / "config").mkdir()
    for v, closed in (("0.0", False), ("0", False), ("500", True), ("true", True), ("false", True)):
        (tmp_path / "config" / "manhattan.yaml").write_text(cfg.replace("loss_cap_usd: 0 ", f"loss_cap_usd: {v} "))
        assert bool(safety.manhattan_switches(tmp_path)) is closed, v


@pytest.mark.parametrize("old,new", [
    ('data_end: "2019-12-31"', 'data_end: "2026-11-20"'), ("store: imac_only", "store: private_repo"),
    ("windows: {}", "windows: {fx_daily: {start: 2020-01-01, end: 2026-09-30}}"),
    ("mode: shared_window", "mode: disjoint_slices"), ("end: null ", "end: 2027-12-31 "),
    ("screening_method: null", "screening_method: ebh_elond")])
def test_every_conservative_switch_position_stops_starts(tmp_path, old, new):
    cfg = (REPO / "config" / "manhattan.yaml").read_text()
    assert old in cfg
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "manhattan.yaml").write_text(cfg.replace(old, new, 1))
    assert safety.manhattan_switches(tmp_path)


def test_a_non_finite_limits_file_is_refused_on_load(tmp_path):
    for text in ('{"monthly_vcpu_hours": NaN}', '{"min_free_disk_mb": Infinity}', '{"max_running_jobs": 1e999}',
                 '{"min_free_disk_mb": 1' + "0" * 400 + '}',
                 '[1]', '{"max_running_jobs": 1', '\xff'):
        (tmp_path / "limits.json").write_bytes(text.encode("latin-1"))
        with pytest.raises(L.LimitsError):
            L.load(tmp_path)


def _sup(tmp_path, **kw):
    from manhattan.orchestra.supervisor import Supervisor
    return Supervisor(tmp_path / "root", limits=L.Limits(require_clean_tree=False, **kw), check_switches=False)


def _open_invocation(sup, jid, now, *, workers=1):
    (sup.job_dir(jid) / "inv-0001").mkdir(parents=True, exist_ok=True)
    with sup.journal.locked():
        sup.journal.append("invocation_intent", {"job_id": jid, "n": 1, "inv_dir": f"jobs/{jid}/inv-0001",
                                                 "workers": workers, "intent_epoch": now,
                                                 "deadline_epoch": now + 600})
    return sup.state()["jobs"][jid]


def test_cancel_is_applied_after_every_reclassification(tmp_path):
    sup = _sup(tmp_path)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    now = time.time()
    _open_invocation(sup, jid, now)
    with sup.journal.locked():
        sup.journal.append("cancel_requested", {"job_id": jid, "reason": "r"})
        j = sup.state()["jobs"][jid]
        # exit 0 but the run is not closed: "unfinished" first, then the cancel
        sup._end(j, j["open_invocation"], {"outcome": "done", "exit_code": 0, "reconcile": {"state": "incomplete"},
                                           "anchor": {"records": 3, "head": "h"}}, now, {"ended": []})
    j = sup.state()["jobs"][jid]
    assert j["status"] == "cancelled" and j["invocations"][0]["ended"]["outcome"] == "cancelled"


def test_a_cancel_left_on_a_waiting_job_is_honoured_instead_of_starting_it(tmp_path):
    sup = _sup(tmp_path)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    now = time.time()
    _open_invocation(sup, jid, now)
    with sup.journal.locked():                       # an older journal: cancel recorded, invocation ended to retry
        sup.journal.append("cancel_requested", {"job_id": jid, "reason": "r"})
        sup.journal.append("invocation_ended", {"job_id": jid, "n": 1, "outcome": "unfinished", "ended_epoch": now,
                                                "consecutive_errors": 0, "next_status": "retry_wait",
                                                "not_before_epoch": 0.0})
    out = sup.tick()
    assert out["started"] == [] and sup.state()["jobs"][jid]["status"] == "cancelled"


def test_a_timeout_that_wrote_nothing_is_no_progress(tmp_path):
    sup = _sup(tmp_path)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    now = time.time()
    j = _open_invocation(sup, jid, now)
    with sup.journal.locked():
        sup._end(j, j["open_invocation"], {"outcome": "timeout", "exit_code": 130, "anchor": None}, now,
                 {"ended": []})
    assert sup.state()["jobs"][jid]["invocations"][0]["ended"]["outcome"] == "no_progress"


def test_startup_race_pid_written_after_the_lock_probe_is_not_killed(tmp_path, monkeypatch):
    """The child takes the lock and writes pid.json just after the supervisor's lock probe. pid.json is read first,
    so the supervisor sees "still launching", never "pid.json and a free lock" (which would mean dead)."""
    from manhattan.orchestra import supervisor as SV
    from manhattan.orchestra.journal import atomic_write_json
    sup = _sup(tmp_path)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    now = time.time()
    j = _open_invocation(sup, jid, now)
    pidf = sup.root / j["open_invocation"]["inv_dir"] / "pid.json"
    real = SV.is_held_elsewhere
    killed = []

    def probe(path):
        held = real(path)
        if path.name == ".run.lock" and not pidf.exists():
            atomic_write_json(pidf, {"pid": 999999, "pgid": 999999, "host": "h", "started_epoch": now})
        return held
    monkeypatch.setattr(SV, "is_held_elsewhere", probe)
    monkeypatch.setattr(SV, "_kill", lambda pids, sig: killed.append((pids, sig)) or 0)
    with sup.journal.locked():
        sup._supervise(j, j["open_invocation"], {"ended": [], "signalled": []})
    j = sup.state()["jobs"][jid]
    assert j["status"] == "launching" and j["invocations"][0]["ended"] is None and killed == []


def test_an_unknown_machine_id_never_marks_an_invocation_foreign(tmp_path, monkeypatch):
    from manhattan.orchestra.journal import atomic_write_json
    sup = _sup(tmp_path)
    jid = sup.register("smoke", {"units": 4})["job_id"]
    now = time.time() - 3600
    j = _open_invocation(sup, jid, now)
    atomic_write_json(sup.root / j["open_invocation"]["inv_dir"] / "pid.json",
                      {"pid": 999999, "pgid": 999999, "host": "old-name.local", "machine_id": None, "boot_id": None,
                       "started_epoch": now})
    with sup.journal.locked():
        sup._supervise(sup.state()["jobs"][jid], j["open_invocation"], {"ended": [], "signalled": []})
    assert sup.state()["jobs"][jid]["invocations"][0]["ended"]["outcome"] == "lost"       # not foreign_host


# -- real macOS (runs only on a Mac: CI job orchestra-macos on a GitHub-hosted runner) ----------------------------

darwin = pytest.mark.skipif(sys.platform != "darwin", reason="real macOS only")


@darwin
def test_real_macos_tools_identity_and_file_system(tmp_path):
    import re
    from manhattan.orchestra import procs
    assert procs.tool("ps") == "/bin/ps" and procs.tool("mount") == "/sbin/mount"
    assert procs.tool("sysctl") == "/usr/sbin/sysctl" and procs.tool("ioreg") == "/usr/sbin/ioreg"
    assert not Path("/proc/self/stat").exists()
    assert re.fullmatch(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}", procs.machine_id() or "")
    b = procs.boot_id()
    assert b and b.startswith(("bootsession:", "boottime:")) and b == procs.boot_id()
    assert procs.fs_type(tmp_path) == "apfs" and procs.fs_type(Path.home()) == "apfs"
    assert not safety.is_network_fs(procs.fs_type(tmp_path))
    assert safety.check_root(tmp_path / "root") == (tmp_path / "root").resolve()


@darwin
def test_real_macos_ps_reports_full_command_lines_and_resident_memory(tmp_path):
    import subprocess
    from manhattan.orchestra import procs
    from manhattan.orchestra.child import group_rss_mb
    from manhattan.orchestra.supervisor import _members
    inv = (tmp_path / ("x" * 200) / "jobs" / "OJ-0" / "inv-0001").resolve()     # a long path: no truncation
    code = "import time; b = bytearray(200 * 2**20); b[::4096] = b'1' * len(b[::4096]); time.sleep(30)"
    p = subprocess.Popen([sys.executable, "-c", code, "manhattan.orchestra.child", str(inv)], start_new_session=True)
    try:
        deadline = time.time() + 20
        while time.time() < deadline and group_rss_mb(p.pid) < 180:
            time.sleep(0.2)
        assert group_rss_mb(p.pid) >= 180                  # ps rss is KiB on macOS: 200 MiB touched reads ~200
        assert _members(p.pid, inv) == [p.pid]             # the whole directory survives in ps's command column
        assert _members(p.pid, inv.with_name("inv-0002")) == []
    finally:
        p.kill()
        p.wait()


@darwin
def test_real_macos_peak_rss_units():
    import resource
    from manhattan.orchestra.child import maxrss_mb
    block = bytearray(64 * 2**20)
    block[::4096] = b"1" * len(block[::4096])
    mb = maxrss_mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    assert 64 <= mb < 8192                                  # bytes on macOS; as KiB it would read ~1000x larger
