"""Manhattan ops, end-to-end proof on a synthetic batch (O-05, O-34, O-35).

Ten SYNTHETIC families from a mock generator (no model) go through the mechanical critic, compilation, screening on
labelled exploration data, the freeze tooling, registration with eligibility checks and nightly cycles, with a local
bare repository standing in for the private ledger and another for its mirror. The second nightly cycle is crashed
half-way through writing the chain and then recovered. The whole flow runs twice, with and without the crash, and
the two private ledgers are compared. Then every public channel is searched for the performance values the private
ledger holds. Synthetic data only; no network; nothing is written to the repository.
"""
import contextlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from manhattan import config as MC
from manhattan import roles
from manhattan import spec as S
from manhattan.engine.pit import PitStore
from manhattan.generate import parse_reply
from manhattan.ops import blinding as B
from manhattan.ops import compiler as CP
from manhattan.ops import data as D
from manhattan.ops import freeze_pr, leakscan as LS, mockgen
from manhattan.ops import runner as R
from manhattan.ops import store as ST
from manhattan.ops import timing as TM

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
LATE = {3: "2026-11-12"}                    # family 4 declares a first observation the day before the merge


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


@contextlib.contextmanager
def public_log(path: Path):
    """What GitHub Actions would show: everything on file descriptors 1 and 2."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    with open(path, "a") as f:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


class Clock:
    def __init__(self):
        self.t = None

    def at(self, s):
        self.t = TM.parse_time(s)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


def flow(root: Path, crash: bool) -> dict:
    root.mkdir(parents=True)
    clock = Clock()
    logs = root / "public_log.txt"
    summary = root / "step_summary.md"
    artifacts = root / "artifacts"
    artifacts.mkdir()
    out = {"root": root, "logs": logs, "summary": summary, "artifacts": artifacts}

    # ---- generation (mock, no model) in its own sandbox
    gen = root / "generator"
    gen.mkdir()
    req = mockgen.blind_request(n_families=10, max_hypotheses=2, domains=("syn_daily",))
    (gen / "prompt.txt").write_text(req.prompt)
    reply = mockgen.mock_reply(req, declared=LATE)
    (gen / "reply.json").write_text(reply)
    fams, hyps = parse_reply(reply, "blind")
    out["prompt_before"] = req.prompt

    # ---- private ledger stand-in and mirror
    remote, mirror = root / "manhattan-ledger.git", root / "mirror.git"
    for b in (remote, mirror):
        git("init", "-q", "--bare", "-b", "main", str(b), cwd=root)

    # ---- screening on labelled exploration data (synthetic, to 2019-12-31), recorded privately
    clock.at("2026-11-12T12:00:00Z")
    exes = list(CP.iter_batch(fams, hyps, "c" * 40))
    rows = D.synthetic_rows(date(2019, 12, 31))
    st_ = PitStore()
    by = {}
    for s_, p_, v_ in rows:
        by.setdefault(s_, ([], []))
        by[s_][0].append(p_)
        by[s_][1].append(v_)
    for s_, (ps, vs) in by.items():
        st_.add(s_, ps, vs, lag_days=0 if "px" in s_ or "evt" in s_ else 1)
    fence = roles.Fence.from_config(MC.load())
    with public_log(logs):
        sc = ST.Store(workdir=root / "rt-screen/private/ledger", remote=str(remote), run_id="900", commit="c" * 40,
                      clock=clock).open()
        returns = R.screen(sc, exes, st_, fence, date(2015, 1, 2), date(2019, 12, 31))

    # ---- freeze tooling (critic, manifest, PR body) into the public stand-in, then "Ethan merges"
    public = root / "public"
    public.mkdir()
    git("init", "-q", "-b", "main", cwd=public)
    git("config", "user.email", "t@example.invalid", cwd=public)
    git("config", "user.name", "t", cwd=public)
    prep = freeze_pr.prepare(1, fams, hyps, out_root=public / "data/manhattan/batches", code_version="c" * 40,
                             protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock-no-model",
                             template_hash=req.template_hash, fence={}, screening_returns=returns)
    git("add", "-A", cwd=public)
    git("commit", "-qm", "Manhattan batch AB-0001 manifest (synthetic)", cwd=public)
    out["prep"] = prep
    batches = public / "data/manhattan/batches"

    def cfg(asof, run, attempt=1, crash_at=None):
        return R.RunConfig(ledger_dir=root / f"rt{run}.{attempt}/private/ledger", remote=str(remote),
                           batches_dir=batches, asof=asof, sources=("synthetic",), mirror=str(mirror), run_id=str(run),
                           run_attempt=attempt, commit="c" * 40, private_dir=root / f"rt{run}.{attempt}/private",
                           run_calendar="synthetic", crash_at=crash_at)

    fetch = lambda a: {"synthetic": (lambda: D.synthetic_csv(a))}
    healths = []
    with public_log(logs):
        # cycle 0: Thursday night, before anything is registered (capture only)
        clock.at("2026-11-12T23:30:00Z")
        healths.append(R.nightly(cfg(date(2026, 11, 12), 101), fetch(date(2026, 11, 12)), clock=clock,
                                 summary_path=str(summary)))
        # registration: merged Friday 15:00 UTC (GitHub API), witnessed 16:30 UTC (stand-in for OpenTimestamps)
        clock.at("2026-11-13T16:45:00Z")
        pr = {"merged": True, "merged_at": "2026-11-13T15:00:00Z", "merge_commit_sha": "d" * 40}
        w = TM.Witness("opentimestamps", prep["manifest_hash"], TM.parse_time("2026-11-13T16:30:00Z"), True)
        healths.append(R.register(cfg(date(2026, 11, 13), 102), 1, pr, w, clock=clock))
        # cycle 1: Monday night (Friday night's run never happened)
        clock.at("2026-11-16T23:30:00Z")
        healths.append(R.nightly(cfg(date(2026, 11, 16), 103), fetch(date(2026, 11, 16)), clock=clock,
                                 summary_path=str(summary)))
        out["after_cycle1"] = [json.dumps(r, sort_keys=True) for r in
                               ST.Store(workdir=root / "peek1", remote=str(remote)).open().records]
        # cycle 2: Tuesday night, crashed half-way through writing the chain, then rerun (attempt 2)
        clock.at("2026-11-17T23:30:00Z")
        if crash:
            with pytest.raises(ST.SimulatedCrash):
                R.nightly(cfg(date(2026, 11, 17), 104, 1, crash_at="mid_chain_write"), fetch(date(2026, 11, 17)),
                          clock=clock, summary_path=str(summary))
            out["after_crash"] = [json.dumps(r, sort_keys=True) for r in
                                  ST.Store(workdir=root / "peek2", remote=str(remote)).open().records]
            clock.at("2026-11-17T23:40:00Z")
            healths.append(R.nightly(cfg(date(2026, 11, 17), 104, 2), fetch(date(2026, 11, 17)), clock=clock,
                                     summary_path=str(summary)))
        else:
            healths.append(R.nightly(cfg(date(2026, 11, 17), 104), fetch(date(2026, 11, 17)), clock=clock,
                                     summary_path=str(summary)))
        # an attempt to overwrite a recorded observation
        clock.at("2026-11-18T09:00:00Z")
        s = ST.Store(workdir=root / "rt-overwrite/private/ledger", remote=str(remote), run_id="900", run_attempt=2,
                     commit="c" * 40, clock=clock).open()
        first = s.of_type("observation")[0]
        out["overwrite"] = s.write([ST.Intent("observation", tuple(first["key"]), {**first["payload"], "net": "0.5"})],
                                   "overwrite attempt")
        # a run that fails inside evaluation, with a performance value in the exception message
        clock.at("2026-11-18T23:30:00Z")
        value = float(first["payload"]["net"]) if float(first["payload"]["net"]) else 0.012345678901
        out["fail_value"] = value
        orig = R.observation_intents

        def broken(*a, **k):
            raise ValueError(f"synthetic failure: net return was {value!r}, sharpe {value * 15.87:.6f}")

        R.observation_intents = broken
        try:
            fail = R.nightly(cfg(date(2026, 11, 18), 105), fetch(date(2026, 11, 18)), clock=clock,
                             summary_path=str(summary))
        finally:
            R.observation_intents = orig
        rp = root / "fail_health.json"
        rp.write_text(B.render(fail))
        out["issue_body"] = subprocess.run([sys.executable, "-m", "manhattan.ops.runner", "issue-body", "--health",
                                            str(rp)], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        healths.append(fail)
    out["healths"] = healths
    final = ST.Store(workdir=root / "final", remote=str(remote)).open()
    out["final"] = final
    out["mirror_check"] = final.verify_mirror(str(mirror), root / "mirror-check")
    out["prompt_after"] = mockgen.blind_request(n_families=10, max_hypotheses=2, domains=("syn_daily",)).prompt
    return out


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("e2e")
    return {"crash": flow(base / "crash", True), "reference": flow(base / "reference", False)}


def content(records):
    """Type, key and payload of every record but the locks. A conflict's ``existing_hash`` is the hash of the record
    it protects, which covers that record's random nonce and time, so it differs between two runs by design."""
    def payload(r):
        return {k: v for k, v in r["payload"].items() if not (r["type"] == "conflict" and k == "existing_hash")}
    return sorted(json.dumps([r["type"], r["key"], payload(r)], sort_keys=True) for r in records
                  if r["type"] not in ("lock", "unlock", "lock_broken"))


# ---- O-34

def test_ten_synthetic_families_through_every_stage(runs):
    r = runs["crash"]
    assert r["prep"]["counts"]["families"] == 10
    fam_specs = [S.read(p) for p in (Path(r["prep"]["dir"]) / "specs").glob("AF-*.json")]
    assert len(fam_specs) == 10 and all("SYNTHETIC" in f["mechanism"] for f in fam_specs)
    f = r["final"]
    types = {x["type"] for x in f.records}
    assert {"screening", "capture", "registration", "observation", "missed_run", "heartbeat", "conflict"} <= types
    scr = f.of_type("screening")
    assert len(scr) == r["prep"]["executables"]
    assert all(x["payload"]["role"] == "exploration" and x["payload"]["evidential_weight"] == 0 for x in scr)
    body = (Path(r["prep"]["dir"]) / "PR_BODY.md").read_text()
    assert "does not certify timing" in body


def test_registration_checks_eligibility_and_keeps_the_late_ones(runs):
    f = runs["crash"]["final"]
    regs = R.registrations(f)
    late = [p for p in regs.values() if not p["eligible"]]
    ok = [p for p in regs.values() if p["eligible"]]
    assert late and ok
    assert all(p["ineligible_reasons"] == ["window_begun_at_registration"] for p in late)
    assert all(p["registration_utc"] == "2026-11-13T16:30:00Z" and p["first_eligible_observation"] == "2026-11-13"
               for p in regs.values())
    late_ids = {p["prediction"] for p in late}
    obs_late = [o for o in f.of_type("observation") if o["payload"]["prediction"] in late_ids]
    assert obs_late and all(o["payload"]["evidential_weight"] == 0 for o in obs_late)   # tracked, never dropped


def test_missed_run_recorded_as_missed(runs):
    f = runs["crash"]["final"]
    assert [x["payload"]["date"] for x in f.of_type("missed_run")] == ["2026-11-13"]
    h = runs["crash"]["healths"][2]
    assert h["missed_runs_new"] == 1 and h["status"] == "ok"


def test_observations_start_after_the_first_observation(runs):
    f = runs["crash"]["final"]
    regs = R.registrations(f)
    for o in f.of_type("observation"):
        assert o["payload"]["date"] > regs[o["payload"]["prediction"]]["first_observation"]
    on_time = sorted({o["payload"]["date"] for o in f.of_type("observation") if o["payload"]["eligible"]})
    late = sorted({o["payload"]["date"] for o in f.of_type("observation") if not o["payload"]["eligible"]})
    assert on_time == ["2026-11-16", "2026-11-17"]
    assert late == ["2026-11-13", "2026-11-16", "2026-11-17"]          # declared from 12 November: tracked from 13
    # Friday's marks were captured on Monday (the Friday run was missed): reconstructed, weight 0
    fri = [o for o in f.of_type("observation") if o["payload"]["date"] == "2026-11-13"]
    assert fri and all(o["payload"]["reconstructed"] and o["payload"]["evidential_weight"] == 0 for o in fri)
    mon = [o for o in f.of_type("observation") if o["payload"]["date"] == "2026-11-16"]
    assert all(o["payload"]["reconstructed"] for o in mon)                # its base (Friday) was captured late
    tue = [o for o in f.of_type("observation") if o["payload"]["date"] == "2026-11-17" and o["payload"]["eligible"]]
    assert tue and all(not o["payload"]["reconstructed"] and o["payload"]["evidential_weight"] == 1 for o in tue)


# ---- O-35: immutability and exact recovery

def test_records_are_immutable(runs):
    for r in runs.values():
        after = [json.dumps(x, sort_keys=True) for x in r["final"].records]
        assert after[: len(r["after_cycle1"])] == r["after_cycle1"]
        assert r["overwrite"]["conflict"] == 1 and r["overwrite"]["appended"] == 0
    c = runs["crash"]
    assert [json.dumps(x, sort_keys=True) for x in c["final"].records][: len(c["after_crash"])] == c["after_crash"]


def test_recovery_is_exact(runs):
    c, ref = runs["crash"]["final"], runs["reference"]["final"]
    assert content(c.records) == content(ref.records)
    assert ST.verify_chain(c.records) == [] and c.unfinished() == []
    assert runs["crash"]["mirror_check"]["status"] == "equal"
    assert len(runs["crash"]["after_crash"]) < len(c.records)          # the crash really cut the cycle short
    keys = [tuple(x["key"]) for x in c.records]
    assert len(keys) == len(set(keys))


# ---- O-05 and O-35: nothing leaks to the public stand-in or to the generator

def needles(run):
    vals = LS.performance_values([x for x in run["final"].records if x["type"] in ("observation", "screening")])
    return LS.Needles(vals + [run["fail_value"], run["fail_value"] * 15.87])


def test_no_performance_value_in_any_public_channel(runs):
    r = runs["crash"]
    n = needles(r)
    assert len(n) > 300
    runner_temp = [p for p in r["root"].iterdir() if p.name.startswith("rt")]
    channels = {
        "public_repo_tree": ("tree", r["root"] / "public"),
        "public_repo_git": ("git", r["root"] / "public"),
        "actions_log": ("text", r["logs"].read_text()),
        "step_summary": ("text", r["summary"].read_text()),
        "issue_body": ("text", r["issue_body"]),
        "artifacts": ("tree", r["artifacts"]),
    }
    for i, p in enumerate(runner_temp):
        channels[f"runner_temp_{i}"] = ("tree_excluding", (p, [p / "private"]))
    found = LS.scan_channels(channels, n)
    assert found == [], found[:5]
    # the runner's own public output holds no decimal number at all
    for name in ("actions_log", "step_summary", "issue_body"):
        text = channels[name][1]
        assert not re.search(r"\d\.\d{3,}", text), name
    assert r["healths"][-1]["status"] == "failed" and r["healths"][-1]["error_class"] == "ValueError"
    assert "synthetic failure" not in r["logs"].read_text() + r["issue_body"]


def test_the_scanner_would_have_caught_a_leak_in_each_channel(runs, tmp_path):
    r = runs["crash"]
    n = needles(r)
    v = LS.performance_values(r["final"].of_type("observation"))
    leak = next(x for x in v if 1e-3 < abs(x) < 1 and len(repr(abs(x))[2:].lstrip("0")) >= 8)
    assert LS.scan_text(f"net={leak!r}", n, "actions_log")
    assert LS.scan_text(f"| x | {leak * 100:.5f}% |", n, "step_summary")
    d = tmp_path / "artifacts"
    d.mkdir()
    (d / "a.json").write_text(json.dumps({"v": leak}))
    assert LS.scan_tree(d, n, "artifacts")
    pub = tmp_path / "pub"
    pub.mkdir()
    git("init", "-q", cwd=pub)
    (pub / "f.txt").write_text(f"{leak:.8f}")
    git("add", "-A", cwd=pub)
    git("-c", "user.name=t", "-c", "user.email=t@e.invalid", "commit", "-qm", "c", cwd=pub)
    assert LS.scan_git(pub, n, "git")


def test_nothing_reaches_the_generator(runs):
    r = runs["crash"]
    assert r["prompt_after"] == r["prompt_before"]                     # the blind request does not depend on results
    assert LS.scan_tree(r["root"] / "generator", needles(r), "generator") == []
    assert sorted(p.name for p in (r["root"] / "generator").iterdir()) == ["prompt.txt", "reply.json"]


def test_public_health_records_are_health_only(runs):
    for h in runs["crash"]["healths"]:
        B.health({k: v for k, v in h.items() if k != "schema_version"})
        assert not any(isinstance(v, float) for v in h.values())
