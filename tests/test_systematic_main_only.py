"""systematic-monthly's jobs run only on a schedule event or a workflow_dispatch from refs/heads/main (Ethan,
2026-11-12; run #9 was dispatched from test/kick-gate). Each job's `if:` is evaluated here as GitHub would, for every
event and ref, and the writer workflows are checked for pull_request/push triggers. No network."""
import re
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WRITERS = ("systematic.yml", "ledger-daily.yml", "v1-rules-monitor.yml", "private-commitments.yml", "shadows-setup.yml")
MAIN, BRANCH = "refs/heads/main", "refs/heads/test/kick-gate"
EVENTS = ("schedule", "workflow_dispatch", "pull_request", "pull_request_target", "push", "workflow_run",
          "repository_dispatch")


def wf(name):
    doc = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)          # PyYAML reads the bare key `on` as True


def ev(expr, event, ref, schedule="", due_result="success", due_run="true", cancelled=False):
    """Evaluate a GitHub Actions `if:` expression of the kind used in systematic.yml (==, !=, &&, ||, !, ())."""
    e = expr.strip()
    if e.startswith("${{"):
        e = e[3:-2]
    assert re.fullmatch(r"[\w.\s'=!&|()*,\-/]+", e), e          # nothing but the operators this evaluator handles
    py = e.replace("&&", " and ").replace("||", " or ").replace("!cancelled()", " not cancelled() ")
    assert "!" not in py.replace("!=", ""), py
    ctx = {"github": NS(ref=ref, event_name=event, event=NS(schedule=schedule)),
           "needs": NS(due=NS(result=due_result, outputs=NS(run=due_run))), "cancelled": lambda: cancelled}
    return bool(eval(py, {"__builtins__": {}}, ctx))


def test_no_writer_runs_on_pull_request_or_push():
    for name in WRITERS:
        _, on = wf(name)
        bad = {"pull_request", "pull_request_target", "push"} & set(on)
        assert not bad, f"{name} runs on {bad}"
    _, on = wf("systematic.yml")
    assert set(on) == {"schedule", "workflow_dispatch"}


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ref", [MAIN, BRANCH, "refs/pull/42/merge", "refs/tags/v1.0-frozen"])
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
