"""systematic.yml `only_if_due`: a dispatch with only_if_due=true does nothing when this month's rebalance is already
in results/systematic/rebalance_log.csv and runs normally when it is not; the 3rd-of-month schedule and a dispatch
without the input behave exactly as before (always run).  The workflow part is checked through the real YAML and the
real `python3 -m em_macro.rebalance_due` process, so the dry run below is what the `due` job executes."""
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

from em_macro import rebalance_due as D

ROOT = Path(__file__).resolve().parents[1]
WF = yaml.safe_load((ROOT / ".github/workflows/systematic.yml").read_text(encoding="utf-8"))
HEADER = "as_of,effective_from,scheduled_date,run_date,days_late,status,n_positions\n"


def _log(tmp_path, *rows):
    p = tmp_path / "rebalance_log.csv"
    p.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    return p


NOV = "2026-10,2026-11,2026-11-03,2026-11-04,1,LATE by 1 day,8"
DEC = "2026-11,2026-12,2026-12-03,2026-12-03,0,on time,8"


def test_only_if_due_skips_when_month_is_recorded(tmp_path):
    log = _log(tmp_path, NOV)
    assert D.decide("workflow_dispatch", "true", date(2026, 11, 12), log)[0] is False
    assert D.decide("workflow_dispatch", "true", date(2026, 11, 30), log)[0] is False


def test_only_if_due_runs_when_month_is_not_recorded(tmp_path):
    log = _log(tmp_path, NOV)
    assert D.decide("workflow_dispatch", "true", date(2026, 12, 3), log)[0] is True
    assert D.decide("workflow_dispatch", "true", date(2027, 11, 3), log)[0] is True      # same month, other year
    assert D.decide("workflow_dispatch", "true", date(2026, 12, 3), _log(tmp_path))[0] is True     # empty log
    assert D.decide("workflow_dispatch", "true", date(2026, 12, 4), _log(tmp_path, NOV, DEC))[0] is False


def test_unreadable_or_missing_log_runs(tmp_path):
    assert D.decide("workflow_dispatch", "true", date(2026, 11, 12), tmp_path / "nope.csv")[0] is True
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00garbage")
    assert D.decide("workflow_dispatch", "true", date(2026, 11, 12), bad)[0] is True


def test_schedule_and_plain_dispatch_always_run(tmp_path):
    log = _log(tmp_path, NOV)                                   # month already recorded: still runs, as before
    for event, flag in [("schedule", ""), ("schedule", "true"), ("workflow_dispatch", ""),
                        ("workflow_dispatch", "false"), ("push", "true")]:
        assert D.decide(event, flag, date(2026, 11, 12), log)[0] is True, (event, flag)


def _run_job_script(tmp_path, event, flag, today_in_log_month):
    """Run the due job's real command as a process; return the run= line it writes to $GITHUB_OUTPUT."""
    out = tmp_path / "out.txt"
    out.write_text("")
    # freeze 'today' through a sitecustomize-free wrapper: patch the date the module computes
    code = ("import datetime as d, em_macro.rebalance_due as m;"
            f"m.datetime = type('X', (), {{'now': staticmethod(lambda tz=None: d.datetime({today_in_log_month}, tzinfo=d.timezone.utc))}});"
            f"m.LOG = __import__('pathlib').Path(r'{tmp_path / 'rebalance_log.csv'}'); m.recorded.__defaults__ = (m.LOG,);"
            "m.decide.__defaults__ = (m.LOG,); m.main()")
    env = {**os.environ, "EVENT_NAME": event, "ONLY_IF_DUE": flag, "GITHUB_OUTPUT": str(out)}
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out.read_text().strip(), r.stdout


def test_dry_run_of_the_due_script(tmp_path):
    _log(tmp_path, NOV)
    assert _run_job_script(tmp_path, "workflow_dispatch", "true", "2026, 11, 12")[0] == "run=false"
    assert _run_job_script(tmp_path, "workflow_dispatch", "true", "2026, 12, 3")[0] == "run=true"
    assert _run_job_script(tmp_path, "workflow_dispatch", "", "2026, 11, 12")[0] == "run=true"
    assert _run_job_script(tmp_path, "schedule", "", "2026, 11, 12")[0] == "run=true"


# ---- the workflow itself ----------------------------------------------------------------------------------------
def test_workflow_input_and_gating():
    on = WF.get("on") or WF.get(True)
    inp = on["workflow_dispatch"]["inputs"]["only_if_due"]
    assert inp["type"] == "boolean" and inp["default"] is False
    assert on["schedule"] == [{"cron": "23 7 3 * *"}, {"cron": "37 6 * * 1,4"}]          # schedules untouched
    due, update = WF["jobs"]["due"], WF["jobs"]["update"]
    assert due["if"] == "github.event_name != 'schedule' || github.event.schedule == '23 7 3 * *'"
    assert update["needs"] == "due" and update["if"] == "needs.due.outputs.run == 'true'"
    assert due["outputs"]["run"] == "${{ steps.check.outputs.run }}"
    assert due["permissions"] == {"contents": "read"}
    run = next(s for s in due["steps"] if s.get("id") == "check")
    assert run["run"] == "python3 -m em_macro.rebalance_due"
    assert run["env"]["ONLY_IF_DUE"] == "${{ github.event.inputs.only_if_due }}"
    assert WF["jobs"]["keep-cache"]["if"].endswith("'37 6 * * 1,4'") and "needs" not in WF["jobs"]["keep-cache"]


def test_update_steps_are_untouched():
    steps = WF["jobs"]["update"]["steps"]
    assert steps[0] == {"uses": "actions/checkout@v4"}
    assert not any("needs.due" in str(s) or "steps.check" in str(s) for s in steps)      # no step gained a condition
