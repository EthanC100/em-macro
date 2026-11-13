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
