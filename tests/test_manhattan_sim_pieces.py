"""A run made in pieces (``manhattan/sim/run.py``: a replication range, a time budget, lazy submission;
``manhattan/sim/collect.py``: plan, merge, status) and the workflow that makes one on GitHub's runners
(``.github/workflows/manhattan-sim.yml``). Synthetic data only; the workflow is read, never started.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import re
import time
from pathlib import Path

import pytest
import yaml

from manhattan.sim import collect, criteria_v2, hb_v2, run, runlog, seeds, world
from manhattan.stats import hier_analytic
from manhattan.testing import prereg_or_skip

ROOT = Path(__file__).resolve().parents[1]
SHA = prereg_or_skip()
WF = ROOT / ".github/workflows/manhattan-sim.yml"
FORK = multiprocessing.get_start_method() == "fork"        # the patched worker function reaches the pool only by fork


def fake_rep(scenario, size, rep, **kw):
    return {"scenario": scenario, "size": size, "rep": rep, "branch": 0, "seconds": 1.0, "value": rep * rep, **kw}


def fake_one(args):
    """Stands in for one replication: its number squared, after a short wait; replication 3 of D03 fails."""
    scenario, size, rep, branch, sha, version = args
    marks = os.environ.get("MANHATTAN_TEST_MARKS")
    if marks:
        Path(marks, f"{scenario}_{rep}").write_text("started", encoding="utf-8")
    time.sleep(float(os.environ.get("MANHATTAN_TEST_SLEEP", "0")))
    if scenario == "D03" and rep == 3:
        raise RuntimeError("replication 3 broke")
    return fake_rep(scenario, size, rep)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "_one", fake_one)
    monkeypatch.setenv("MANHATTAN_TEST_MARKS", str(tmp_path / "marks"))
    (tmp_path / "marks").mkdir()
    return tmp_path


def ends(out: Path) -> list[dict]:
    return [r for r in runlog.read(out / "runs.jsonl") if r["event"] == "end"]


# ------------------------------------------------------------------ the runner: a range of replications

def test_a_piece_runs_only_its_range_and_is_labelled_part(fake):
    out = fake / "piece"
    reps = run.run_scenario("D02", "STD", 9, first=6, out=out, quiet=True)
    assert [r["rep"] for r in reps] == [6, 7, 8] and [r["value"] for r in reps] == [36, 49, 64]      # it does not start at 0
    start, end = runlog.read(out / "runs.jsonl")
    assert start["label"] == end["label"] == "part" and start["options"]["first"] == 6
    assert start["replications"] == {"first": 6, "requested": 3, "completed": 0} and end["replications"]["completed"] == 3
    assert end["status"] == "completed"
    # a second call continues inside the range and repeats nothing
    more = run.run_scenario("D02", "STD", 12, first=6, out=out, quiet=True)
    assert [r["rep"] for r in more] == [6, 7, 8, 9, 10, 11] and ends(out)[-1]["replications"] == {"first": 9, "requested": 3, "completed": 3}
    # the whole pre-registered count from 0 is still "full"; anything short of it needs a label that says so
    with pytest.raises(SystemExit, match="fewer than the pre-registered 2000"):
        run.run_scenario("D02", "STD", 2000, first=1990, out=out, quiet=True, label="full")
    with pytest.raises(SystemExit, match="label it pilot"):
        run.run_scenario("D02", "STD", 10, out=out, quiet=True, label="full")
    with pytest.raises(SystemExit, match="--first 11 must lie between 0 and --reps 10"):
        run.run_scenario("D02", "STD", 10, first=11, out=out, quiet=True)
    assert run.run_scenario("D02", "STD", 4, out=fake / "pilot", quiet=True)[0]["rep"] == 0
    assert runlog.read(fake / "pilot" / "runs.jsonl")[0]["label"] == "pilot"


# ------------------------------------------------------------------ the runner: a time budget and the three statuses

def test_a_time_budget_stops_cleanly_and_the_three_statuses_keep_their_meaning(fake, monkeypatch):
    out = fake / "o"
    outcome: dict = {}
    # a budget already spent: nothing is started; the end record is "interrupted" with the reason and what is left
    run.run_scenario("D02", "STD", 5, out=out, quiet=True, deadline=time.time() - 1, outcome=outcome, label="test")
    end = ends(out)[-1]
    assert outcome == {"status": "interrupted", "reason": "time budget reached", "completed": 0, "left": 5}
    assert (end["status"], end["reason"], end["left"], end["replications"]["completed"]) == ("interrupted", "time budget reached", 5, 0)
    assert list((fake / "marks").iterdir()) == []
    # a budget that ends part-way: what was started is finished and saved, nothing more is started
    monkeypatch.setenv("MANHATTAN_TEST_SLEEP", "0.3")
    run.run_scenario("D02", "STD", 5, out=out, quiet=True, deadline=time.time() + 0.4, outcome=outcome, label="test")
    assert outcome["status"] == "interrupted" and 1 <= outcome["completed"] <= 3 and outcome["left"] == 5 - outcome["completed"]
    assert len(list((fake / "marks").iterdir())) == outcome["completed"]              # every replication started was saved
    monkeypatch.setenv("MANHATTAN_TEST_SLEEP", "0")
    # no budget: completed
    reps = run.run_scenario("D02", "STD", 5, out=out, quiet=True, outcome=outcome, label="test")
    assert outcome["status"] == "completed" and outcome["reason"] == "" and outcome["left"] == 0
    assert [r["rep"] for r in reps] == [0, 1, 2, 3, 4] and ends(out)[-1]["status"] == "completed"
    # a replication that raises: "failed", with the reason, and the records made before it are on file
    with pytest.raises(RuntimeError, match="replication 3 broke"):
        run.run_scenario("D03", "STD", 6, out=out, quiet=True, outcome=outcome, label="test")
    end = ends(out)[-1]
    assert outcome["status"] == "failed" and end["status"] == "failed" and "replication 3 broke" in end["reason"]
    assert [r["rep"] for r in run.load_reps("D03", "STD", out=out)] == [0, 1, 2] and end["replications"]["completed"] == 3
    assert {r["status"] for r in ends(out)} == {"interrupted", "completed", "failed"}     # runlog.finish's three, and only those
    with pytest.raises(ValueError):
        runlog.finish(runlog.read(out / "runs.jsonl")[0], "stopped", 0, path=out / "runs.jsonl")


@pytest.mark.skipif(not FORK, reason="the stand-in for a replication reaches worker processes only by fork")
def test_work_is_handed_out_lazily_so_the_pool_stops_cleanly(fake, monkeypatch):
    out = fake / "o"
    outcome: dict = {}
    monkeypatch.setenv("MANHATTAN_TEST_SLEEP", "0.25")
    # two workers, a budget of about one replication: at most one per worker is ever in flight when it ends
    run.run_scenario("D02", "STD", 40, workers=2, out=out, quiet=True, deadline=time.time() + 0.3, outcome=outcome, label="test")
    started = len(list((fake / "marks").iterdir()))
    assert outcome["status"] == "interrupted" and outcome["completed"] == started <= 4 and outcome["left"] == 40 - started
    assert sorted(r["rep"] for r in run.load_reps("D02", "STD", out=out)) == list(range(started))
    # a failure: the replications already in flight are saved, no later one is started, and the run is "failed"
    for m in (fake / "marks").iterdir():
        m.unlink()
    with pytest.raises(RuntimeError, match="replication 3 broke"):
        run.run_scenario("D03", "STD", 40, workers=2, out=out, quiet=True, outcome=outcome, label="test")
    started = sorted(int(m.name.split("_")[1]) for m in (fake / "marks").iterdir())
    saved = sorted(r["rep"] for r in run.load_reps("D03", "STD", out=out))
    assert outcome["status"] == "failed" and max(started) <= 5 and saved == [r for r in started if r != 3]
    assert ends(out)[-1]["status"] == "failed" and ends(out)[-1]["replications"]["completed"] == len(saved)
    # and without trouble the pool gives every replication, each once
    monkeypatch.setenv("MANHATTAN_TEST_SLEEP", "0")
    reps = run.run_scenario("D04", "STD", 23, workers=3, out=out, quiet=True, outcome=outcome, label="test")
    assert [r["rep"] for r in reps] == list(range(23)) and outcome == {"status": "completed", "reason": "", "completed": 23, "left": 0}


def test_the_command_line_takes_a_range_and_a_budget(fake, capsys):
    out = fake / "cli"
    assert run.main(["--scenario", "D02", "--size", "STD", "--first", "2", "--reps", "5", "--label", "part", "--workers", "1",
                     "--out", str(out)]) == 0
    assert [r["rep"] for r in run.load_reps("D02", "STD", out=out)] == [2, 3, 4]
    code = run.main(["--scenario", "D02", "--size", "STD", "--first", "5", "--reps", "8", "--label", "part", "--workers", "1",
                     "--time-budget-minutes", "0", "--out", str(out)])
    assert code == run.EXIT_BUDGET == 75 and "run the same command again to continue" in capsys.readouterr().err
    assert ends(out)[-1]["status"] == "interrupted"
    with pytest.raises(SystemExit):
        run.main(["--plan", "development", "--first", "3", "--out", str(out)])
    # with --plan the budget covers the whole call: the first run that hits it ends the call
    assert run.main(["--plan", "development", "--reps-std", "2", "--reps-hb", "1", "--label", "test", "--workers", "1",
                     "--time-budget-minutes", "0", "--out", str(fake / "plan")]) == 75
    assert len(runlog.read(fake / "plan" / "runs.jsonl")) == 2                       # one start and one end: no second run began


# ------------------------------------------------------------------ the collector

def write_piece(root: Path, name: str, scenario: str, size: str, reps, version="v1", code=None, log=True, **kw) -> Path:
    piece = root / name
    path = run.reps_path(scenario, size, seeds.DEVELOPMENT, piece, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    code = code or run.code_hash(size, version=version)
    with path.open("a", encoding="utf-8") as f:
        for r in reps:
            f.write(json.dumps({**fake_rep(scenario, size, r, **kw), "code": code, "commit": "abc", "run_id": name}) + "\n")
    if log:
        runlog.append({"run_id": name, "event": "end", "time_utc": f"2026-11-13T00:00:{len(name):02d}Z", "status": "completed",
                       "scenario": scenario, "size": size, "options": {}}, piece / "runs.jsonl")
    return piece


def test_the_plan_cuts_what_is_missing_into_pieces_a_job_can_finish(tmp_path):
    out = tmp_path / "out"
    p = collect.plan(out)
    pieces = p["include"]
    assert p["left_out"] == 0 and len(pieces) <= collect.MAX_JOBS == 256
    need = {(s, z): criteria_v2.replications(s, z) for s, z in run.development_plan("v2")}
    assert len(need) == 32 and sum(need.values()) == 41600                           # the whole development programme
    covered: dict = {}
    for x in pieces:
        assert x["id"] == f"{x['scenario']}-{x['size']}-{x['first']:04d}-{x['reps'] - 1:04d}" and x["replications"] == x["reps"] - x["first"]
        assert 1 <= x["workers"] <= collect.JOB_WORKERS and re.fullmatch(r"[A-Za-z0-9-]+", x["id"])
        covered.setdefault((x["scenario"], x["size"]), []).extend(range(x["first"], x["reps"]))
    assert {k: sorted(v) for k, v in covered.items()} == {k: list(range(n)) for k, n in need.items()}      # each replication once
    # a piece is sized to what a job can do: 285 minutes of its workers at 60%, at the seconds the table gives
    for x in pieces:
        secs = collect.DEFAULT_SECONDS[collect.kind(x["scenario"], x["size"])]
        assert x["replications"] * secs <= collect.JOB_MINUTES * 60 * x["workers"] * collect.FILL + secs
    assert collect.JOB_MINUTES == 285 and p["cpu_hours"] == pytest.approx(sum(x["cpu_hours"] for x in pieces), rel=0.01)
    assert len({x["id"] for x in pieces}) == len(pieces)
    # replications on file are not planned again, and a gap in the middle is planned as its own piece
    write_piece(tmp_path, "out", "D02", "STD", list(range(0, 12)) + list(range(20, 2000)), log=False)
    again = [x for x in collect.plan(out)["include"] if (x["scenario"], x["size"]) == ("D02", "STD")]
    assert [(x["first"], x["reps"]) for x in again] == [(12, 20)]
    only = collect.plan(out, sizes=("HB",), only=("D05", "D08"))["include"]
    assert {(x["scenario"], x["size"]) for x in only} == {("D05", "HB"), ("D08", "HB")}
    assert collect.plan(out, max_jobs=5)["left_out"] == len(collect.plan(out)["include"]) - 5
    assert collect._ranges([0, 1, 2, 7, 9, 10]) == [(0, 3), (7, 8), (9, 11)] and collect._ranges([]) == []


def test_merge_appends_new_records_once_and_reports_what_is_missing(tmp_path):
    out, pieces = tmp_path / "out", tmp_path / "pieces"
    write_piece(tmp_path, "out", "D02", "STD", [0, 1], log=False)                     # two pilot replications already on file
    write_piece(pieces, "manhattan-sim-piece-D02-STD-0002-0004", "D02", "STD", [2, 3, 4])
    write_piece(pieces, "manhattan-sim-piece-D02-STD-0005-0006", "D02", "STD", [5, 6, 1])       # 1 again: the same record
    write_piece(pieces / "earlier" / "77", "manhattan-sim-piece-D05h-STD-0000-0001", "D05h", "STD", [0, 1], version="v2")
    assert [p.name for p in collect.find_pieces(pieces)] == ["manhattan-sim-piece-D05h-STD-0000-0001", "manhattan-sim-piece-D02-STD-0002-0004",
                                                             "manhattan-sim-piece-D02-STD-0005-0006"]
    dry = collect.merge(pieces, out, dry_run=True)
    assert dry["added"] == {"D02_STD": 5, "D05h_STD": 2} and run.load_reps("D05h", "STD", out=out, version="v2") == []
    s = collect.merge(pieces, out)
    assert s == {"pieces": 3, "added": {"D02_STD": 5, "D05h_STD": 2}, "already_on_file": {"D02_STD": 1, "D05h_STD": 0},
                 "run_log_records": 3}
    assert [r["rep"] for r in run.load_reps("D02", "STD", out=out)] == list(range(7))
    assert [r["rep"] for r in run.load_reps("D05h", "STD", out=out, version="v2")] == [0, 1]
    assert len(runlog.read(out / "runs.jsonl")) == 3
    # merging the same pieces again adds nothing: not a record, not a run-log line
    s2 = collect.merge(pieces, out)
    assert s2["added"] == {"D02_STD": 0, "D05h_STD": 0} and s2["run_log_records"] == 0
    assert len(run.reps_path("D02", "STD", 0, out).read_text().splitlines()) == 7
    text, left = collect.status(out)
    assert "| D02 | STD | v1 | 7 | 2000 | 7 to 1999 |" in text and "| D05h | STD | v2 | 2 | 400 | 2 to 399 |" in text
    assert left == 41600 - 9 and f"Replications still to run: {left}." in text
    assert collect.main(["status", "--out", str(out)]) == 1 and collect.main(["merge", str(pieces), "--out", str(out)]) == 0
    assert collect.main(["plan", "--out", str(out), "--only", "D02", "--sizes", "LONG", "--github-output", str(tmp_path / "gh")]) == 0
    gh = dict(line.split("=", 1) for line in (tmp_path / "gh").read_text().splitlines())
    assert int(gh["pieces"]) == len(json.loads(gh["matrix"])["include"]) > 0


def test_merge_refuses_what_may_not_be_pooled_and_then_writes_nothing(tmp_path):
    out = tmp_path / "out"
    write_piece(tmp_path, "out", "D02", "STD", [0], log=False)
    before = run.reps_path("D02", "STD", 0, out).read_text()

    def refused(build, match):
        pieces = tmp_path / f"p{len(list(tmp_path.iterdir()))}"
        write_piece(pieces, "good", "D02", "STD", [1, 2])                             # a good piece beside the bad one
        build(pieces)
        with pytest.raises(collect.Refused, match=match):
            collect.merge(pieces, out)
        assert run.reps_path("D02", "STD", 0, out).read_text() == before and not (out / "runs.jsonl").exists()
        assert collect.main(["merge", str(pieces), "--out", str(out)]) == 2

    refused(lambda p: write_piece(p, "old-code", "D02", "STD", [3], code="0123456789abcdef"), "records of different code are never pooled")
    refused(lambda p: write_piece(p, "beyond", "D02", "STD", [2000]), "replication 2000 is outside 0 to 1999")
    refused(lambda p: write_piece(p, "other", "D02", "STD", [1], value=-1), "differs from the same replication in another piece")
    refused(lambda p: write_piece(p, "changed", "D02", "STD", [0], value=-1), "differs from the record already on file")
    refused(lambda p: write_piece(p, "wrong-folder", "D02", "STD", [3], version="v2", code=run.code_hash("STD")), "other pre-registration version")
    refused(lambda p: write_piece(p, "not-planned", "H01", "STD", [0]), "not a run of the development plan")

    def confirmation(p):
        path = write_piece(p, "confirm", "D02", "STD", [3]) / "reps" / "D02_STD_b0.jsonl"
        path.rename(path.with_name("D02_STD_b1.jsonl"))
    refused(confirmation, "confirmation branch")

    # HB records reviewed at another step are refused by the collector (SIM_PREREG_v2, amendment 1)
    hb_code = run.code_hash("HB", version="v2")
    refused(lambda p: write_piece(p, "yearly", "D05", "HB", [0], version="v2", code=hb_code, review_step=252), "not every 63: refused")
    refused(lambda p: write_piece(p, "no-step", "D05", "HB", [0], version="v2", code=hb_code), "not every 63: refused")
    ok = tmp_path / "ok"
    write_piece(ok, "quarterly", "D05", "HB", [0, 1], version="v2", code=hb_code, review_step=hb_v2.REVIEW_STEP)
    assert collect.merge(ok, out)["added"] == {"D05_HB": 2}
    # timings and the identity of the run are not results: the same replication from two runs is one record
    assert collect._same({"rep": 1, "seconds": 3.0, "run_id": "a", "reviews": {"2": {"fit_seconds": [1.0], "ok": True}}},
                         {"rep": 1, "seconds": 9.0, "run_id": "b", "reviews": {"2": {"fit_seconds": [2.0], "ok": True}}})
    assert not collect._same({"rep": 1, "x": 1.0}, {"rep": 1, "x": 1.0000001})


def test_pieces_made_by_the_real_runner_merge_into_the_run_one_machine_would_have_made(tmp_path, monkeypatch):
    """End to end on a tiny world: one call for replications 0 to 3 against two pieces merged."""
    monkeypatch.setitem(world.SIZES, "STD", world.Size("STD", 3, 4, 5, 2, 3, 4, 6))
    whole, a, b, merged = (tmp_path / n for n in ("whole", "a", "b", "merged"))
    one = run.run_scenario("D05", "STD", 4, label="test", out=whole, quiet=True)
    run.run_scenario("D05", "STD", 2, label="part", out=a / "piece-1", quiet=True)
    run.run_scenario("D05", "STD", 4, first=2, out=b / "piece-2", quiet=True)
    for src in (a, b):
        (tmp_path / "pieces").mkdir(exist_ok=True)
        next(src.iterdir()).rename(tmp_path / "pieces" / next(src.iterdir()).name)
    assert collect.merge(tmp_path / "pieces", merged)["added"] == {"D05_STD": 4}
    got = run.load_reps("D05", "STD", out=merged)
    assert [collect._strip(r) for r in got] == [collect._strip(r) for r in one]         # the same numbers, replication by replication
    assert [r["label"] for r in runlog.read(merged / "runs.jsonl") if r["event"] == "start"] == ["part", "part"]


# ------------------------------------------------------------------ the workflow

def load():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)


def test_the_workflow_is_started_by_hand_only_and_reads_no_secret():
    doc, on = load()
    text = WF.read_text(encoding="utf-8")
    assert set(on) == {"workflow_dispatch"}                                          # no schedule, no push, no pull_request
    assert not re.search(r"^\s*(schedule|cron)\s*:", text, re.M)
    assert "secrets." not in text and "${{ secrets" not in text                      # no repository secret
    assert doc["permissions"] == {"contents": "read", "actions": "read"}             # the automatic token, read-only
    assert not any("permissions" in job for job in doc["jobs"].values())             # no job widens it
    assert doc["concurrency"] == {"group": "manhattan-sim", "cancel-in-progress": False}
    for word in ("git push", "git commit", "gh pr", "gh issue", "contents: write", "pull-requests: write", "environment:"):
        assert word not in text, word
    assert "must be merged to main before it can be started" in text


def test_every_job_runs_from_main_only_under_six_hours_with_pipefail():
    doc, _ = load()
    assert list(doc["jobs"]) == ["plan", "piece", "collect"]
    for name, job in doc["jobs"].items():
        assert "github.ref == 'refs/heads/main'" in job["if"], name
        assert job["timeout-minutes"] < 360 and job["defaults"]["run"]["shell"] == "bash" and job["runs-on"] == "ubuntu-latest"
        co = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout"))
        assert co["with"] == {"persist-credentials": False}                          # the commit it was started from; no stored token
    piece = doc["jobs"]["piece"]
    assert piece["strategy"]["fail-fast"] is False and piece["strategy"]["max-parallel"] == 20
    assert piece["strategy"]["matrix"] == "${{ fromJSON(needs.plan.outputs.matrix) }}"
    run_step = next(s for s in piece["steps"] if s.get("name") == "Run the piece")["run"]
    budget = int(re.search(r"--time-budget-minutes (\d+)", run_step).group(1))
    assert budget == collect.JOB_MINUTES and budget + 60 <= piece["timeout-minutes"]  # an hour to install and to finish what is in flight
    assert '--first "$FIRST" --reps "$REPS"' in run_step and "--label part" in run_step and "--prereg v2" in run_step
    assert "--confirm" not in WF.read_text(encoding="utf-8")                         # never a held-out scenario


def test_pieces_are_checkpointed_as_artifacts_and_resumable():
    doc, _ = load()
    piece, collect_job, plan = doc["jobs"]["piece"], doc["jobs"]["collect"], doc["jobs"]["plan"]
    restore = next(s for s in piece["steps"] if s.get("uses", "").startswith("actions/download-artifact"))
    upload = next(s for s in piece["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
    assert restore["with"]["name"] == upload["with"]["name"] == "manhattan-sim-piece-${{ matrix.id }}"
    assert restore["continue-on-error"] is True and restore["with"]["path"] == upload["with"]["path"]
    assert upload["if"] == "always()" and upload["with"]["overwrite"] is True         # uploaded even when the piece fails
    steps = [s.get("name") or s.get("uses") for s in piece["steps"]]
    assert steps.index("Records of an earlier attempt of this piece") < steps.index("Run the piece") < steps.index("Upload the piece's records")
    assert collect_job["needs"] == ["plan", "piece"] and collect_job["if"].startswith("always()")
    merge = next(s for s in collect_job["steps"] if s.get("id") == "merge")["run"]
    assert "manhattan.sim.collect merge" in merge and "manhattan.sim.collect status" in merge and "GITHUB_STEP_SUMMARY" in merge
    results = next(s for s in collect_job["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
    assert results["with"]["name"] == "manhattan-sim-results" and results["if"] == "always()"
    earlier = next(s for s in plan["steps"] if s.get("name") == "Records of earlier runs")
    assert "gh run download" in earlier["run"] and "manhattan.sim.collect merge" in earlier["run"]
    assert earlier["env"] == {"EARLIER_RUNS": "${{ inputs.earlier_runs }}", "GH_TOKEN": "${{ github.token }}"}
    assert "manhattan.prereg_v2 verify" in "".join(s.get("run", "") for s in plan["steps"])


def test_inputs_and_matrix_values_reach_the_scripts_through_env_only():
    doc, _ = load()
    for job in doc["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), step.get("name")                # nothing is pasted into a shell line


def test_the_workflow_is_not_one_of_the_writers_and_the_script_is_the_module():
    writers = (ROOT / "tests/test_systematic_main_only.py").read_text(encoding="utf-8")
    assert "manhattan-sim.yml" not in writers                                        # it writes nothing to the repository
    script = (ROOT / "scripts/manhattan_sim_collect.py").read_text(encoding="utf-8")
    assert "from manhattan.sim import collect" in script and "collect.main()" in script
    assert "manhattan/sim/collect.py" not in run.CODE_FILES + run.CODE_FILES_HB + run.CODE_FILES_V2 + run.CODE_FILES_V2_HB
    assert hier_analytic.EDGE_MASS_MAX == 0.01                                       # (the model is not touched by any of this)
