"""Manhattan ops: PR #86's binding attempt accounting, verified through the runner's real entry point.

Every run here is a separate process executing ``manhattan.ops.runner.main`` (the function
``python -m manhattan.ops.runner`` and the workflow call) with ``--rehearsal``: the synthetic source and a local bare
repository standing in for the private ledger. ``tests/manhattan_runner_harness.py`` adds read probes and hard
process deaths (``os._exit``: no handler, no ``finally``) and changes nothing else. Synthetic data only; no network.

Evidence written up in docs/manhattan/ops/ENTRYPOINT_EVIDENCE.md.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

import manhattan_attempt_fixtures as F
from manhattan import attempts
from manhattan.generate import parse_reply
from manhattan.ops import freeze_pr, leakscan as LS, mockgen
from manhattan.ops import store as ST

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/manhattan_runner_harness.py"
ACCOUNTING = ("attempt_started", "attempt_completed", "attempt_failed", "attempt_aborted")
TERMINALS = ACCOUNTING[1:]


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


class Rig:
    """A synthetic frozen batch, a bare 'private ledger' and the CLI, one process per call."""

    def __init__(self, root: Path, n_families: int = 3):
        self.root = root
        req = mockgen.blind_request(n_families=n_families, max_hypotheses=1, domains=("syn_daily",))
        fams, hyps = parse_reply(mockgen.mock_reply(req, n=n_families), "blind")
        self.prep = freeze_pr.prepare(1, fams, hyps, out_root=root / "batches", code_version="c" * 40,
                                      protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock",
                                      template_hash=req.template_hash, fence={})
        self.remote = root / "remote.git"
        git("init", "-q", "--bare", "-b", "main", str(self.remote), cwd=root)
        (root / "pr.json").write_text(json.dumps({"merged": True, "merged_at": "2026-11-13T15:00:00Z",
                                                  "merge_commit_sha": "d" * 40}))
        (root / "witness.json").write_text(json.dumps({"kind": "opentimestamps", "digest": self.prep["manifest_hash"],
                                                       "attested_utc": "2026-11-13T16:30:00Z", "verified": True}))
        self.n = 0

    def run(self, cmd: str, *, clock: str, asof: str | None = None, run_id: str | None = None, attempt: int = 1,
            fault: str | None = None, probe: bool = False, extra: tuple = (), env: dict | None = None,
            background: bool = False):
        self.n += 1
        tag = f"{self.n}"
        run_id = run_id or str(100 + self.n)
        work = self.root / f"rt{tag}"
        health, evidence = work / "health.json", work / "evidence.jsonl"
        work.mkdir()
        argv = [cmd, "--rehearsal", "--rehearsal-clock", clock, "--ledger-dir", str(work / "private/ledger"),
                "--private-dir", str(work / "private"), "--remote", str(self.remote),
                "--batches", str(self.root / "batches"), "--run-id", run_id, "--attempt", str(attempt),
                "--commit", F.HEAD, "--health-out", str(health), *extra]
        if cmd == "nightly":
            argv += ["--asof", asof, "--sources", "synthetic"]
        else:
            argv += ["--batch", "1", "--pr-json", str(self.root / "pr.json"),
                     "--witness-json", str(self.root / "witness.json")]
        e = {"PATH": "/usr/bin:/bin", "HOME": str(self.root), "PYTHONDONTWRITEBYTECODE": "1",
             "GIT_CONFIG_GLOBAL": "/dev/null", **(env or {})}
        if fault:
            e["HARNESS_FAULT"] = fault
        if probe:
            e["HARNESS_PROBE"] = "1"
        full = [sys.executable, str(HARNESS), str(evidence), "--", *argv]
        if background:
            return subprocess.Popen(full, cwd=ROOT, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True), health, evidence
        p = subprocess.run(full, cwd=ROOT, env=e, capture_output=True, text=True, timeout=300)
        return Result(p.returncode, p.stdout, p.stderr, health, evidence)

    def ledger(self) -> ST.Store:
        self.n += 1
        return ST.Store(workdir=self.root / f"peek{self.n}", remote=str(self.remote)).open()

    def setup_registered(self):
        r0 = self.run("nightly", clock="2026-11-12T23:30:00Z", asof="2026-11-12")
        r1 = self.run("register", clock="2026-11-13T16:45:00Z")
        assert (r0.rc, r1.rc) == (0, 0), (r0.out, r0.err, r1.out, r1.err)


class Result:
    def __init__(self, rc, out, err, health_path: Path, evidence_path: Path):
        self.rc, self.out, self.err = rc, out, err
        self.health = json.loads(health_path.read_text()) if health_path.exists() else None
        self.events = [json.loads(x) for x in evidence_path.read_text().splitlines()] if evidence_path.exists() else []


def audit(led: ST.Store) -> dict:
    return attempts.reconcile(store_chain=led.workdir / ST.CHAIN, store_anchor={"records": len(led.records),
                                                                                "head": led.head})


def terminals_by_attempt(led: ST.Store) -> Counter:
    return Counter(r["payload"]["attempt_id"] for t in TERMINALS for r in led.of_type(t))


def records_by_commit(remote: Path) -> dict:
    """{record hash: the remote commit that first added it to chain.jsonl}, walking the remote's history."""
    out = {}
    for c in git("rev-list", "--reverse", "main", cwd=remote).split():
        try:
            text = git("show", f"{c}:{ST.CHAIN}", cwd=remote)
        except subprocess.CalledProcessError:
            continue
        for line in text.splitlines():
            if line.strip():
                out.setdefault(json.loads(line)["hash"], c)
    return out


@pytest.fixture
def rig(tmp_path):
    r = Rig(tmp_path)
    r.setup_registered()
    return r


# ------------------------------------------------------------------ registration before exposure, at the entry point

def test_entry_point_registers_every_attempt_before_its_first_protected_read(rig):
    r = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16", probe=True)
    assert r.rc == 0 and r.health["status"] == "ok", (r.out, r.err)
    reads = [e for e in r.events if e["event"] == "first_protected_read"]
    led = rig.ledger()
    starts = led.of_type("attempt_started")
    assert len(reads) == len(starts) == r.health["attempts_registered"] > 0
    assert all(e["start_durable_on_remote"] and e["role"] == "forward" for e in reads)
    assert {e["attempt"] for e in reads} == {s["key"][1] for s in starts}
    rep = audit(led)
    assert rep["access_reconciled"], rep["violations"]
    assert (rep["registered_executions"], rep["completed"], rep["unfinished"]) == (len(starts), len(starts), 0)


def test_results_and_their_terminals_are_one_remote_commit_and_one_journal_entry(rig):
    r = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16")
    assert r.rc == 0
    led = rig.ledger()
    by_commit = records_by_commit(rig.remote)
    by_key = {tuple(x["key"]): x for x in led.records}
    done = led.of_type("attempt_completed")
    assert done
    for t in done:
        new = [x for x in t["payload"]["results"] if x["disposition"] == "new"]
        assert new
        commits = {by_commit[t["hash"]]} | {by_commit[by_key[tuple(x["key"])]["hash"]] for x in new}
        assert len(commits) == 1                                    # the result and its terminal arrived together
        starts = by_commit[led.get(("attempt_started", t["payload"]["attempt_id"]))["hash"]]
        assert starts not in commits                                # and the start was durable before, separately
    entries = {}
    for j in led.journal():
        if j["state"] == "committed":
            for h in j["record_hashes"]:
                entries[h] = j["entry"]
    for t in done:
        linked = {entries[by_key[tuple(x["key"])]["hash"]] for x in t["payload"]["results"]
                  if x["disposition"] == "new"}
        assert linked == {entries[t["hash"]]}


# ------------------------------------------------------------------ process death, restart, recovery

def test_hard_kill_after_a_protected_read_then_restart(rig):
    dead = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16", run_id="500",
                   fault="kill_after_first_read")
    assert dead.rc == 137 and dead.health is None                   # died: no health, no handler ran
    led = rig.ledger()
    started = led.of_type("attempt_started")
    assert started and not led.of_type("observation") and not any(led.of_type(t) for t in TERMINALS)
    assert audit(led)["access_reconciled"] is False                 # unfinished attempts are never certified
    # the workflow's "re-run": same run id, attempt 2 (an earlier attempt's lock is broken)
    again = rig.run("nightly", clock="2026-11-16T23:40:00Z", asof="2026-11-16", run_id="500", attempt=2, probe=True)
    assert again.rc == 0 and again.health["status"] == "ok", (again.out, again.err)
    assert again.health["attempts_recovered"] == len(started)
    led = rig.ledger()
    killed = {s["key"][1] for s in started}
    for aid in killed:
        t = led.get(("attempt_terminal", aid))
        assert t["type"] == "attempt_aborted" and t["payload"]["reason"] == "interrupted"
        assert t["payload"]["data_read"] is None                     # unknown: never claimed unread
    retries = [s for s in led.of_type("attempt_started") if s["key"][1] not in killed]
    assert {s["payload"]["retry_of"] for s in retries} == killed     # each retry names its interrupted predecessor
    assert all(e["start_durable_on_remote"] for e in again.events if e["event"] == "first_protected_read")
    assert set(terminals_by_attempt(led).values()) == {1}            # exactly one terminal per attempt
    rep = audit(led)
    assert rep["access_reconciled"], rep["violations"]
    assert rep["registered_executions"] == 2 * len(started) and rep["unfinished"] == 0


@pytest.mark.parametrize("fault", ["kill_after_results_pending", "kill_after_results_commit"])
def test_hard_kill_while_committing_results_keeps_results_and_terminals_together(tmp_path, fault):
    ref = Rig(tmp_path / "ref")
    ref.setup_registered()
    assert ref.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16").rc == 0
    expected = {tuple(r["key"]) for r in ref.ledger().of_type("observation")}

    rig = Rig(tmp_path / "crash")
    rig.setup_registered()
    dead = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16", run_id="600", fault=fault)
    assert dead.rc == 137 and any(e["event"] == "killed" for e in dead.events)
    led = rig.ledger()
    obs, done = led.of_type("observation"), led.of_type("attempt_completed")
    if fault == "kill_after_results_pending":
        assert not obs and not done                                 # neither, until the journal is finished
    else:
        assert obs and len(done) == len(led.of_type("attempt_started"))   # both
    again = rig.run("nightly", clock="2026-11-16T23:40:00Z", asof="2026-11-16", run_id="600", attempt=2)
    assert again.rc == 0 and again.health["status"] == "ok", (again.out, again.err)
    led = rig.ledger()
    first = led.of_type("attempt_started")[:len(done) or None]
    # the crashed run's attempts completed (journal recovery finished their entry); none was also aborted
    crashed = [s["key"][1] for s in led.of_type("attempt_started") if s["payload"]["run"]["run_attempt"] == 1]
    assert crashed and all(led.get(("attempt_terminal", a))["type"] == "attempt_completed" for a in crashed)
    assert set(terminals_by_attempt(led).values()) == {1}
    assert again.health["attempts_recovered"] == 0 and first
    assert {tuple(r["key"]) for r in led.of_type("observation")} == expected   # nothing lost, nothing doubled
    rep = audit(led)
    assert rep["access_reconciled"], rep["violations"]


# ------------------------------------------------------------------ duplicated work

def test_same_day_rerun_is_a_second_execution_with_duplicate_results_only(rig):
    assert rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16").rc == 0
    before = rig.ledger()
    evidence = [r for r in before.records if r["type"] in ("observation", "missed_observation")]
    r2 = rig.run("nightly", clock="2026-11-16T23:50:00Z", asof="2026-11-16")
    assert r2.rc == 0 and r2.health["observations_new"] == 0
    led = rig.ledger()
    assert [r for r in led.records if r["type"] in ("observation", "missed_observation")] == evidence
    second = [t for t in led.of_type("attempt_completed") if t["provenance"]["run_id"] == "%d" % (100 + rig.n - 1)]
    assert len(second) == r2.health["attempts_registered"] > 0
    assert all(x["disposition"] == "duplicate" for t in second for x in t["payload"]["results"])
    assert audit(led)["access_reconciled"]


def test_a_second_process_during_a_live_run_is_locked_out_and_registers_nothing(rig, tmp_path):
    go = tmp_path / "go"
    a, a_health, a_ev = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16", run_id="700",
                                fault="pause_after_lock", env={"HARNESS_GO": str(go)}, background=True)
    deadline = time.time() + 120
    while time.time() < deadline and not (a_ev.exists() and "holding_lock" in a_ev.read_text()):
        time.sleep(0.05)
    try:
        b = rig.run("nightly", clock="2026-11-16T23:31:00Z", asof="2026-11-16", run_id="701")
    finally:
        go.write_text("go")
        a_out, a_err = a.communicate(timeout=300)
    assert b.rc == 1 and b.health["status"] == "locked"
    assert a.returncode == 0, (a_out, a_err)
    led = rig.ledger()
    runs = {s["payload"]["run"]["run_id"] for s in led.of_type("attempt_started")}
    assert runs == {"700"}                                          # the locked-out process registered nothing
    assert audit(led)["access_reconciled"]


# ------------------------------------------------------------------ entry-point guards and public output

def test_synthetic_data_and_real_ledgers_are_kept_apart_at_the_entry_point(rig, tmp_path):
    from manhattan.ops import runner as R
    led = len(rig.ledger().records)
    for argv in (["nightly", "--sources", "synthetic"],                              # synthetic without rehearsal
                 ["nightly", "--rehearsal", "--sources", "fred_DEXBZUS"],            # a real source in rehearsal
                 ["nightly", "--rehearsal-clock", "2026-11-16T23:30:00Z"]):          # rehearsal clock alone
        rc = R.main([*argv, "--ledger-dir", str(tmp_path / "x"), "--remote", str(rig.remote), "--batches",
                     str(rig.root / "batches"), "--asof", "2026-11-16", "--commit", F.HEAD])
        assert rc == 1
    rc = R.main(["nightly", "--rehearsal", "--sources", "synthetic", "--ledger-dir", str(tmp_path / "y"),
                 "--remote", "ledger-primary:EthanC100/manhattan-ledger.git", "--batches", str(rig.root / "batches"),
                 "--asof", "2026-11-16", "--commit", F.HEAD])
    assert rc == 1 and not (tmp_path / "y").exists()                # refused before any clone
    assert len(rig.ledger().records) == led


def test_public_output_of_the_entry_point_is_the_health_record_only(rig):
    r = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16")
    assert r.rc == 0
    lines = [x for x in r.out.splitlines() if x.strip()]
    assert len(lines) == 1 and r.err == ""
    led = rig.ledger()
    needles = LS.Needles(LS.performance_values([o for o in led.records if o["type"] in
                                                ("observation", "attempt_completed", "screening")]))
    assert len(needles) > 0
    assert LS.scan_text(r.out, needles, "stdout") == [] and LS.scan_text(r.err, needles, "stderr") == []
    log = next((rig.root / f"rt{rig.n - 1}/private").glob("run-*.log"))   # the private log stays private
    assert log.exists()


def test_step_summary_and_failure_notification_carry_no_private_value(rig, tmp_path):
    summary = tmp_path / "summary.md"
    ok = rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16",
                 env={"GITHUB_STEP_SUMMARY": str(summary)})
    assert ok.rc == 0
    led = rig.ledger()
    values = LS.performance_values([o for o in led.records if o["type"] in ("observation", "attempt_completed")])
    secret = repr(values[0])
    bad = rig.run("nightly", clock="2026-11-17T23:30:00Z", asof="2026-11-17", fault="raise_in_evaluate",
                  env={"GITHUB_STEP_SUMMARY": str(summary), "HARNESS_SECRET": secret})
    assert bad.rc == 1 and bad.health["status"] == "failed" and bad.health["stage"] == "evaluate"
    hp = rig.root / f"rt{rig.n}/health.json"
    issue = subprocess.run([sys.executable, "-m", "manhattan.ops.runner", "issue-body", "--health", str(hp)],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout
    needles = LS.Needles(values + [float(secret)])
    for where, text in (("stdout", ok.out + bad.out), ("stderr", ok.err + bad.err), ("summary", summary.read_text()),
                        ("health", hp.read_text()), ("issue", issue)):
        assert LS.scan_text(text, needles, where) == [], where
    led = rig.ledger()                                               # the failure closed its attempts, reason only
    failed = led.of_type("attempt_failed")
    assert failed and all(f["payload"]["reason"] == "execution_error" for f in failed)
    assert secret not in json.dumps([f["payload"] for f in failed])
    log = next((hp.parent / "private").glob("run-*.log")).read_text()
    assert secret in log                                             # the diagnostics exist, privately


# ------------------------------------------------------------------ audit against a retained anchor

def test_audit_cli_reconciles_and_detects_a_rewritten_history(rig, tmp_path):
    from manhattan.ops import audit as AU
    assert rig.run("nightly", clock="2026-11-16T23:30:00Z", asof="2026-11-16").rc == 0
    anchor = AU.audit(str(rig.remote), None)                       # what the custodian retains
    (tmp_path / "anchor.json").write_text(json.dumps({"records": anchor["records"], "head": anchor["head"]}))
    rc = AU.main(["--remote", str(rig.remote), "--anchor", str(tmp_path / "anchor.json"),
                  "--json", str(tmp_path / "out.json")])
    out = json.loads((tmp_path / "out.json").read_text())
    assert rc == 0 and out["access_reconciled"] and out["counts"]["unfinished"] == 0
    assert out["certification"] == "checked_against_supplied_anchor"
    assert LS.scan_text(json.dumps(out), LS.Needles(LS.performance_values(rig.ledger().records)), "audit") == []
    # the writer rewrites history: drop the last record and force the remote (what a key holder could do)
    w = tmp_path / "rewrite"
    git("clone", "-q", str(rig.remote), str(w), cwd=tmp_path)
    lines = (w / ST.CHAIN).read_text().splitlines(keepends=True)
    (w / ST.CHAIN).write_text("".join(lines[:-1]))
    git("-c", "user.email=x@example.invalid", "-c", "user.name=x", "commit", "-qam", "rewrite", cwd=w)
    git("push", "-qf", "origin", "HEAD:main", cwd=w)
    rc = AU.main(["--remote", str(rig.remote), "--anchor", str(tmp_path / "anchor.json"),
                  "--json", str(tmp_path / "out2.json")])
    bad = json.loads((tmp_path / "out2.json").read_text())
    assert rc == 1 and bad["integrity_ok"] is False and set(bad) == {"integrity_ok", "error_class"}
