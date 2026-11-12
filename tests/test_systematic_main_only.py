"""Writer workflows run only from refs/heads/main on their intended events (Ethan, 2026-11-12; systematic-monthly's run
#9 was dispatched from test/kick-gate): systematic-monthly and ledger-daily on a schedule or a workflow_dispatch,
private-commitments and shadows-setup on a workflow_dispatch, v1-rules-monitor on a workflow_dispatch or after a
systematic-monthly run of main. Each job's `if:` is evaluated here as GitHub would, for every event and ref, and no
writer has a pull_request or push trigger. CLAUDE.md rule 16 says who may dispatch them. No network."""
import re
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WRITERS = ("systematic.yml", "ledger-daily.yml", "v1-rules-monitor.yml", "private-commitments.yml", "shadows-setup.yml",
           "promote-merge.yml")
MAIN, BRANCH = "refs/heads/main", "refs/heads/test/kick-gate"
EVENTS = ("schedule", "workflow_dispatch", "pull_request", "pull_request_target", "push", "workflow_run",
          "repository_dispatch")


def wf(name):
    doc = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)          # PyYAML reads the bare key `on` as True


def ev(expr, event, ref, schedule="", due_result="success", due_run="true", cancelled=False, wr_branch="main",
       wr_event="workflow_dispatch", ran_run="true", wr_repo="EthanC100/em-macro"):
    """Evaluate a GitHub Actions `if:` expression of the kind the writer workflows use (==, !=, &&, ||, !, ())."""
    e = expr.strip()
    if e.startswith("${{"):
        e = e[3:-2]
    assert re.fullmatch(r"[\w.\s'=!&|()*,\-/]+", e), e          # nothing but the operators this evaluator handles
    py = e.replace("&&", " and ").replace("||", " or ").replace("!cancelled()", " not cancelled() ")
    assert "!" not in py.replace("!=", ""), py
    ctx = {"github": NS(ref=ref, event_name=event, repository="EthanC100/em-macro",
                        event=NS(schedule=schedule, workflow_run=NS(head_branch=wr_branch, event=wr_event,
                                                                    head_repository=NS(full_name=wr_repo)))),
           "needs": NS(due=NS(result=due_result, outputs=NS(run=due_run)), ran=NS(outputs=NS(run=ran_run))),
           "cancelled": lambda: cancelled}
    return bool(eval(py, {"__builtins__": {}}, ctx))


def test_no_writer_runs_on_pull_request_or_push():
    for name in WRITERS:
        _, on = wf(name)
        bad = {"pull_request", "pull_request_target", "push"} & set(on)
        assert not bad, f"{name} runs on {bad}"
    assert {k: set(wf(k)[1]) for k in WRITERS} == {
        "systematic.yml": {"schedule", "workflow_dispatch"}, "ledger-daily.yml": {"schedule", "workflow_dispatch"},
        "v1-rules-monitor.yml": {"workflow_run", "workflow_dispatch"},
        "private-commitments.yml": {"workflow_dispatch"}, "shadows-setup.yml": {"workflow_dispatch"},
        "promote-merge.yml": {"workflow_run"}}


def test_every_writer_job_is_guarded():
    for name in WRITERS:
        for job, spec in wf(name)[0]["jobs"].items():
            assert "github.ref == 'refs/heads/main'" in str(spec.get("if", "")), f"{name}:{job} has no main-only guard"


REFS = [MAIN, BRANCH, "refs/pull/42/merge", "refs/tags/v1.0-frozen"]


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ref", REFS)
def test_ledger_daily_private_commitments_and_shadows_setup_run_only_from_main(event, ref):
    assert ev(wf("ledger-daily.yml")[0]["jobs"]["daily"]["if"], event, ref) == \
        (ref == MAIN and event in ("schedule", "workflow_dispatch"))
    for name, job in (("private-commitments.yml", "recommit"), ("shadows-setup.yml", "setup")):
        assert ev(wf(name)[0]["jobs"][job]["if"], event, ref) == (ref == MAIN and event == "workflow_dispatch"), name


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ref", REFS)
def test_v1_rules_monitor_runs_only_from_main_after_a_main_run(event, ref):
    jobs = wf("v1-rules-monitor.yml")[0]["jobs"]
    for wr_branch in ("main", "test/kick-gate"):
        for wr_event in ("schedule", "workflow_dispatch", "pull_request"):
            ok = ref == MAIN and (event == "workflow_dispatch" or (event == "workflow_run" and wr_branch == "main"
                                                                   and wr_event != "pull_request"))
            assert ev(jobs["ran"]["if"], event, ref, wr_branch=wr_branch, wr_event=wr_event) == ok
            for ran_run in ("true", "false"):
                assert ev(jobs["monitor"]["if"], event, ref, wr_branch=wr_branch, wr_event=wr_event,
                          ran_run=ran_run) == (ok and ran_run == "true")


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ref", REFS)
def test_update_and_keep_cache_run_only_on_schedule_or_dispatch_from_main(event, ref):
    jobs = wf("systematic.yml")[0]["jobs"]
    allowed = ref == MAIN and event in ("schedule", "workflow_dispatch")
    for sched in ("23 7 3 * *", "23 7 4 * *", "37 6 * * 1,4", ""):
        for due_result, due_run in (("success", "true"), ("failure", ""), ("success", "false")):
            upd = ev(jobs["update"]["if"], event, ref, sched, due_result, due_run)
            assert upd == (allowed and (due_result == "failure" or due_run == "true")), (event, ref, sched, due_result)
        assert ev(jobs["keep-cache"]["if"], event, ref, sched) == (allowed and event == "schedule"
                                                                    and sched == "37 6 * * 1,4")
        assert ev(jobs["due"]["if"], event, ref, sched) == (allowed and (event == "workflow_dispatch"
                                                                         or sched in ("23 7 3 * *", "23 7 4 * *")))


def test_the_update_job_never_runs_when_cancelled_or_when_due_was_skipped():
    upd = wf("systematic.yml")[0]["jobs"]["update"]["if"]
    assert not ev(upd, "workflow_dispatch", MAIN, cancelled=True)
    assert not ev(upd, "schedule", MAIN, "37 6 * * 1,4", due_result="skipped", due_run="")


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ref", REFS)
def test_promote_merge_acts_only_on_the_tests_of_the_dev_promotion_pr(event, ref):
    """promote-merge (Ethan, 2026-11-12) runs only on main, after a tests run of a pull request from this repository's
    dev; it has no workflow_dispatch, so nobody can start it by hand."""
    doc, on = wf("promote-merge.yml")
    assert on["workflow_run"] == {"workflows": ["tests"], "types": ["completed"]}
    expr = doc["jobs"]["merge"]["if"]
    for wr_branch in ("dev", "main", "night/Q019"):
        for wr_event in ("pull_request", "push", "workflow_dispatch"):
            for wr_repo in ("EthanC100/em-macro", "someone/fork"):
                ok = (ref == MAIN and event == "workflow_run" and wr_event == "pull_request" and wr_branch == "dev"
                      and wr_repo == "EthanC100/em-macro")
                assert ev(expr, event, ref, wr_branch=wr_branch, wr_event=wr_event, wr_repo=wr_repo) == ok
