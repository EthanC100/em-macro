"""Manhattan ops: the nightly runner's rules (O-07, O-20, O-29, O-30). Synthetic data, local bare repositories."""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from manhattan.generate import parse_reply
from manhattan.ops import data as D
from manhattan.ops import freeze_pr, mockgen
from manhattan.ops import runner as R
from manhattan.ops import store as ST
from manhattan.ops import timing as TM

ROOT = Path(__file__).resolve().parents[1]
MERGED = "2026-11-13T15:00:00Z"


class Clock:
    def __init__(self):
        self.t = None

    def at(self, s):
        self.t = TM.parse_time(s)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


@pytest.fixture
def setup(tmp_path):
    req = mockgen.blind_request(n_families=2, max_hypotheses=1, domains=("syn_daily",))
    fams, hyps = parse_reply(mockgen.mock_reply(req, n=2), "blind")
    prep = freeze_pr.prepare(1, fams, hyps, out_root=tmp_path / "batches", code_version="c" * 40,
                             protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock",
                             template_hash=req.template_hash, fence={})
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    clock = Clock()
    n = {"run": 0}

    def cfg(asof, **kw):
        n["run"] += 1
        return R.RunConfig(ledger_dir=tmp_path / f"rt{n['run']}/private/ledger", remote=str(remote),
                           batches_dir=tmp_path / "batches", asof=asof, sources=("synthetic",), run_id=str(n["run"]),
                           private_dir=tmp_path / f"rt{n['run']}/private", run_calendar="synthetic", **kw)

    def night(asof, at, fetch=None, **kw):
        clock.at(at)
        return R.nightly(cfg(asof, **kw), fetch or {"synthetic": lambda: D.synthetic_csv(asof)}, clock=clock)

    def register(witness=True, at="2026-11-13T16:45:00Z"):
        clock.at(at)
        w = TM.Witness("opentimestamps", prep["manifest_hash"], TM.parse_time("2026-11-13T16:30:00Z"), True) \
            if witness else None
        return R.register(cfg(date(2026, 11, 13)), 1,
                          {"merged": True, "merged_at": MERGED, "merge_commit_sha": "d" * 40}, w, clock=clock)

    def ledger():
        return ST.Store(workdir=tmp_path / f"peek{n['run']}", remote=str(remote)).open()

    return {"night": night, "register": register, "ledger": ledger, "prep": prep, "clock": clock, "cfg": cfg}


def test_rerun_on_the_same_day_adds_nothing(setup):
    s = setup
    s["night"](date(2026, 11, 12), "2026-11-12T23:30:00Z")
    s["register"]()
    h1 = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    before = [r for r in s["ledger"]().records if r["type"] not in ("lock", "unlock")]
    h2 = s["night"](date(2026, 11, 16), "2026-11-16T23:50:00Z")
    after = [r for r in s["ledger"]().records if r["type"] not in ("lock", "unlock")]
    assert h1["observations_new"] > 0 and h2["observations_new"] == 0 and h2["captures_new"] == 0
    assert after == before and h2["status"] == "ok"


def test_capture_is_recorded_before_any_observation_of_the_run(setup):
    s = setup
    s["register"]()
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    recs = s["ledger"]().records
    cap = max(r["seq"] for r in recs if r["type"] == "capture")
    assert all(r["seq"] > cap for r in recs if r["type"] == "observation")


def test_provisional_until_witnessed_then_witnessed_wins(setup):
    s = setup
    h = s["register"](witness=False)
    assert h["predictions_provisional"] == h["predictions_registered"] > 0
    s["register"](witness=True, at="2026-11-13T17:00:00Z")
    regs = R.registrations(s["ledger"]())
    assert all(r["registration_status"] == "witnessed" for r in regs.values())
    kinds = {r["key"][2] for r in s["ledger"]().of_type("registration")}
    assert kinds == {"provisional", "witnessed"}                       # both kept


def test_revision_never_replaces_the_first_seen_value(setup):
    s = setup
    s["night"](date(2026, 11, 12), "2026-11-12T23:30:00Z")
    rev = {("syn_px_A", "2026-11-10"): 1.0}
    s["night"](date(2026, 11, 13), "2026-11-13T23:30:00Z",
               {"synthetic": lambda: D.synthetic_csv(date(2026, 11, 13), revise=rev)})
    fs = D.first_seen(s["ledger"](), ("synthetic",))
    assert fs.revisions == 1 and fs.values[("syn_px_A", "2026-11-10")] != 1.0


def test_missed_observation_then_late_arrival_is_reconstructed(setup):
    s = setup
    s["night"](date(2026, 11, 12), "2026-11-12T23:30:00Z")
    s["register"]()
    gap = {("syn_px_A", "2026-11-16")}
    for d, at in ((date(2026, 11, 16), "2026-11-16T23:30:00Z"), (date(2026, 11, 17), "2026-11-17T23:30:00Z"),
                  (date(2026, 11, 18), "2026-11-18T23:30:00Z"), (date(2026, 11, 19), "2026-11-19T23:30:00Z"),
                  (date(2026, 11, 20), "2026-11-20T23:30:00Z")):
        s["night"](d, at, {"synthetic": (lambda d=d: D.synthetic_csv(d, drop=gap))})
    led = s["ledger"]()
    missed = {r["payload"]["date"] for r in led.of_type("missed_observation")}
    assert missed == {"2026-11-16"}
    assert not [r for r in led.of_type("observation") if r["payload"]["date"] == "2026-11-16"]
    s["night"](date(2026, 11, 23), "2026-11-23T23:30:00Z")              # the value arrives at last
    led = s["ledger"]()
    late = [r for r in led.of_type("observation") if r["payload"]["date"] == "2026-11-16"]
    assert late and all(r["payload"]["reconstructed"] and r["payload"]["evidential_weight"] == 0 for r in late)
    assert {r["payload"]["date"] for r in led.of_type("missed_observation")} == {"2026-11-16"}     # stays missed


def test_no_return_on_or_before_the_first_observation_is_recorded(setup):
    s = setup
    s["register"]()
    s["night"](date(2026, 11, 17), "2026-11-17T23:30:00Z")
    led = s["ledger"]()
    regs = R.registrations(led)
    assert all(o["payload"]["date"] > regs[o["payload"]["prediction"]]["first_observation"]
               for o in led.of_type("observation"))


def test_source_failure_is_recorded_and_the_run_is_partial(setup):
    s = setup

    def boom():
        raise OSError("connection refused 0.0123456789")

    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z", {"synthetic": boom})
    assert h["status"] == "partial" and h["sources_failed"] == ["synthetic"]
    assert s["ledger"]().of_type("capture_failed")


def test_live_lock_stops_the_run_and_failure_releases_its_lock(setup, monkeypatch):
    s = setup
    s["clock"].at("2026-11-16T23:00:00Z")
    holder = ST.Store(workdir=Path(s["cfg"](date(2026, 11, 16)).ledger_dir), remote=s["cfg"](date(2026, 11, 16)).remote,
                      run_id="other", clock=s["clock"]).open()
    holder.acquire()
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:10:00Z")
    assert h["status"] == "locked"
    holder.release()

    def broken(*a, **k):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(R, "observation_intents", broken)
    s["register"]()
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:20:00Z")
    assert h["status"] == "failed" and h["stage"] == "evaluate" and h["error_class"] == "RuntimeError"
    assert s["ledger"]().active_locks() == []


def test_issue_body_cli_never_fails(tmp_path):
    out = subprocess.run([sys.executable, "-m", "manhattan.ops.runner", "issue-body", "--health",
                          str(tmp_path / "missing.json")], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "| status | failed |" in out.stdout
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"status": "failed", "stage": "capture", "error_class": "OSError", "sharpe": 1.5}))
    out = subprocess.run([sys.executable, "-m", "manhattan.ops.runner", "issue-body", "--health", str(p)], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode == 0 and "1.5" not in out.stdout                 # a bad record is not passed through


def test_handled_failure_log_preserved_privately_without_heartbeat(setup, monkeypatch, capfd):
    s = setup
    s["register"]()
    capfd.readouterr()

    def broken(*a, **kw):
        raise RuntimeError("private_canary_0.192837465")

    monkeypatch.setattr(R, "observation_intents", broken)
    health = s["night"](date(2026, 11, 16), "2026-11-16T23:20:00Z")
    public = capfd.readouterr()
    assert health["status"] == "failed"
    assert "private_canary" not in public.out + public.err
    ledger = s["ledger"]()
    logs = list((ledger.workdir / "logs").glob("*.log"))
    assert logs and any("private_canary_0.192837465" in p.read_text() for p in logs)
    assert ledger.of_type("heartbeat") == []
    assert not (ledger.workdir / "heartbeat.json").exists()


def test_log_persistence_failure_stays_private_and_reports_failure(setup, monkeypatch, capfd):
    def unavailable(*a, **kw):
        raise OSError("private_storage_canary_0.918273645")

    monkeypatch.setattr(ST.Store, "put_files", unavailable)
    health = setup["night"](date(2026, 11, 16), "2026-11-16T23:20:00Z")
    public = capfd.readouterr()
    assert health["status"] == "failed" and health["stage"] == "private-log"
    assert "private_storage_canary" not in public.out + public.err


def test_mirror_contains_final_private_log_commit(setup, tmp_path):
    mirror = tmp_path / "mirror.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(mirror)], check=True)
    health = setup["night"](date(2026, 11, 16), "2026-11-16T23:20:00Z", mirror=str(mirror))
    assert health["status"] == "ok" and health["mirror_ok"]
    listing = subprocess.run(["git", "--git-dir", str(mirror), "ls-tree", "-r", "--name-only", "main"],
                             check=True, capture_output=True, text=True).stdout
    assert "logs/run-1-1.log" in listing and "heartbeat.json" in listing


def test_rejected_final_log_mirror_cannot_report_success(setup, tmp_path, monkeypatch):
    mirror = tmp_path / "mirror.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(mirror)], check=True)
    original = ST.Store.mirror
    calls = 0

    def reject_final(self, url):
        nonlocal calls
        calls += 1
        return original(self, url) if calls == 1 else {"status": "rejected"}

    monkeypatch.setattr(ST.Store, "mirror", reject_final)
    health = setup["night"](date(2026, 11, 16), "2026-11-16T23:20:00Z", mirror=str(mirror))
    assert health["status"] == "partial"
    assert health["mirror_status"] == "rejected" and health["mirror_ok"] is False


def test_registration_failure_releases_lock_and_preserves_private_diagnostics(setup, monkeypatch, capfd):
    def broken(*a, **kw):
        raise RuntimeError("private_registration_canary_0.918273645")

    monkeypatch.setattr(R, "registration_intents", broken)
    health = setup["register"]()
    public = capfd.readouterr()
    ledger = setup["ledger"]()
    assert health["status"] == "failed" and health["stage"] == "register"
    assert ledger.active_locks() == [] and ledger.of_type("registration") == []
    assert ledger.of_type("heartbeat") == []
    logs = list((ledger.workdir / "logs").glob("register-*-1.log"))
    assert len(logs) == 1 and "private_registration_canary" in logs[0].read_text()
    assert "private_registration_canary" not in public.out + public.err


def test_registration_log_storage_failure_is_sanitized(setup, monkeypatch, capfd):
    def unavailable(*a, **kw):
        raise OSError("private_storage_canary_0.123456789")

    monkeypatch.setattr(ST.Store, "put_files", unavailable)
    health = setup["register"]()
    public = capfd.readouterr()
    assert health["status"] == "failed" and health["stage"] == "private-log"
    assert setup["ledger"]().active_locks() == []
    assert "private_storage_canary" not in public.out + public.err


def test_registration_attempt_logs_are_distinct_and_mirrored(setup, tmp_path):
    mirror = tmp_path / "mirror.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(mirror)], check=True)
    for attempt in (1, 2):
        cfg = setup["cfg"](date(2026, 11, 13), run_attempt=attempt, mirror=str(mirror))
        cfg.run_id = "same-run"
        setup["clock"].at("2026-11-13T16:45:00Z")
        health = R.register(cfg, 1, {"merged": True, "merged_at": MERGED, "merge_commit_sha": "d" * 40},
                            None, clock=setup["clock"])
        assert health["status"] == "ok" and health["mirror_ok"]
    tree = subprocess.run(["git", "--git-dir", str(mirror), "ls-tree", "-r", "--name-only", "main"],
                          check=True, capture_output=True, text=True).stdout
    assert "logs/register-same-run-1.log" in tree and "logs/register-same-run-2.log" in tree


@pytest.mark.parametrize("raw", ["[]", "null", "3", '{"status":"failed","status":"ok"}'])
def test_issue_body_cli_invalid_shapes_are_sanitized(tmp_path, raw):
    path = tmp_path / "health.json"
    path.write_text(raw)
    result = subprocess.run([sys.executable, "-m", "manhattan.ops.runner", "issue-body", "--health", str(path)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and "| status | failed |" in result.stdout
    assert not result.stderr


def test_cli_sanitizes_failures_outside_the_private_redirect(tmp_path, monkeypatch, capfd):
    from contextlib import contextmanager

    @contextmanager
    def broken(*a):
        raise OSError("private_startup_canary_0.192837465")
        yield

    monkeypatch.setattr(R.B, "quiet", broken)
    output = tmp_path / "health.json"
    status = R.main(["nightly", "--ledger-dir", str(tmp_path / "ledger"), "--remote", "synthetic",
                     "--batches", str(tmp_path / "batches"), "--health-out", str(output)])
    public = capfd.readouterr()
    assert status == 1 and not public.err and "private_startup_canary" not in public.out
    assert json.loads(public.out)["status"] == "failed"
    assert json.loads(output.read_text())["error_class"] == "OSError"


@pytest.mark.parametrize("verified", ["false", "true", 1, 0, None])
def test_witness_verification_does_not_coerce_non_booleans(tmp_path, verified):
    path = tmp_path / "synthetic-witness.json"
    path.write_text(json.dumps({"kind": "synthetic", "digest": "a" * 64, "verified": verified}))
    with pytest.raises(ValueError):
        R._witness(str(path))


def test_explicit_false_witness_remains_unverified(tmp_path):
    path = tmp_path / "synthetic-witness.json"
    path.write_text(json.dumps({"kind": "synthetic", "digest": "a" * 64, "verified": False}))
    assert R._witness(str(path)).verified is False
