"""systematic.yml `due` check.  It applies to the monthly schedule ('23 7 3 * *') and to a dispatch with
only_if_due=true: before the 3rd of the month (UTC) nothing runs; from the 3rd the update is skipped when the month's
rebalance is already in results/systematic/rebalance_log.csv and runs when it is not.  A dispatch WITHOUT the input is
the manual override and always runs; the keep-cache schedule never runs update.  If the due job fails, update still
runs.  The workflow part is checked through the real YAML (the update condition is evaluated for each case) and the
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


def _log(tmp_path, *rows, name="rebalance_log.csv"):
    p = tmp_path / name
    p.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    return p


NOV = "2026-10,2026-11,2026-11-03,2026-11-04,1,LATE by 1 day,8"
DEC = "2026-11,2026-12,2026-12-03,2026-12-03,0,on time,8"


KICK, SCHED, MANUAL = ("workflow_dispatch", "true"), ("schedule", ""), ("workflow_dispatch", "")


def test_skips_when_month_is_recorded_for_kick_and_schedule(tmp_path):
    log = _log(tmp_path, NOV)
    for ev in (KICK, SCHED):
        assert D.decide(*ev, date(2026, 11, 12), log)[0] is False
        assert D.decide(*ev, date(2026, 11, 30), log)[0] is False
        assert D.decide(*ev, date(2026, 11, 3), log)[0] is False


def test_runs_when_month_is_not_recorded_for_kick_and_schedule(tmp_path):
    log = _log(tmp_path, NOV)
    for ev in (KICK, SCHED):
        assert D.decide(*ev, date(2026, 12, 3), log)[0] is True
        assert D.decide(*ev, date(2027, 11, 3), log)[0] is True            # same month, other year
        assert D.decide(*ev, date(2026, 12, 3), _log(tmp_path, name="empty.csv"))[0] is True
        assert D.decide(*ev, date(2026, 12, 4), _log(tmp_path, NOV, DEC, name="both.csv"))[0] is False


def test_before_the_3rd_never_runs(tmp_path):
    for log in (_log(tmp_path, name="a.csv"), _log(tmp_path, NOV, name="b.csv")):                      # recorded or not
        for ev in (KICK, SCHED):
            for day in (1, 2):
                run, reason = D.decide(*ev, date(2026, 12, day), log)
                assert run is False and "before the 3rd" in reason, (ev, day)
    assert D.decide(*KICK, date(2026, 12, 3), _log(tmp_path, name="c.csv"))[0] is True   # the 3rd itself is allowed
    assert D.decide(*KICK, date(2027, 1, 1), _log(tmp_path, DEC, name="d.csv"))[0] is False


def test_manual_dispatch_without_the_input_always_runs(tmp_path):
    log = _log(tmp_path, NOV)
    for flag in ("", "false", "False"):
        for d in (date(2026, 11, 12), date(2026, 12, 1), date(2026, 12, 3)):   # recorded, before the 3rd, not recorded
            assert D.decide("workflow_dispatch", flag, d, log)[0] is True, (flag, d)


def test_unreadable_or_missing_log_runs(tmp_path):
    assert D.decide(*KICK, date(2026, 11, 12), tmp_path / "nope.csv")[0] is True
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00garbage")
    assert D.decide(*SCHED, date(2026, 11, 12), bad)[0] is True


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
    assert _run_job_script(tmp_path, "workflow_dispatch", "true", "2026, 12, 2")[0] == "run=false"
    assert _run_job_script(tmp_path, "schedule", "", "2026, 11, 12")[0] == "run=false"
    assert _run_job_script(tmp_path, "schedule", "", "2026, 12, 3")[0] == "run=true"
    assert _run_job_script(tmp_path, "workflow_dispatch", "", "2026, 11, 12")[0] == "run=true"      # manual override
    assert _run_job_script(tmp_path, "workflow_dispatch", "", "2026, 12, 1")[0] == "run=true"


# ---- the workflow itself ----------------------------------------------------------------------------------------
UPDATE_IF = ("${{ !cancelled() && (github.event_name != 'schedule' || github.event.schedule == '23 7 3 * *') "
             "&& (needs.due.result != 'success' || needs.due.outputs.run == 'true') }}")
MONTHLY, KEEP = "23 7 3 * *", "37 6 * * 1,4"


def update_runs(event, schedule, due_result, due_run, cancelled=False):
    """Evaluate the update job's real `if` expression for one case (GitHub's operators mapped to Python)."""
    import re
    expr = WF["jobs"]["update"]["if"].strip()
    expr = expr[3:-2].strip() if expr.startswith("${{") else expr
    expr = expr.replace("!cancelled()", "(not CANCELLED)").replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!(?!=)", " not ", expr)
    for k, v in {"github.event_name": "EVENT", "github.event.schedule": "SCHEDULE", "needs.due.result": "DUE_RESULT",
                 "needs.due.outputs.run": "DUE_RUN"}.items():
        expr = expr.replace(k, v)
    return bool(eval(expr, {"EVENT": event, "SCHEDULE": schedule, "DUE_RESULT": due_result, "DUE_RUN": due_run,
                            "CANCELLED": cancelled}))


def test_workflow_input_and_gating():
    on = WF.get("on") or WF.get(True)
    inp = on["workflow_dispatch"]["inputs"]["only_if_due"]
    assert inp["type"] == "boolean" and inp["default"] is False
    assert on["schedule"] == [{"cron": MONTHLY}, {"cron": KEEP}]                          # schedules untouched
    due, update = WF["jobs"]["due"], WF["jobs"]["update"]
    assert due["if"] == "github.event_name != 'schedule' || github.event.schedule == '23 7 3 * *'"
    assert update["needs"] == "due" and update["if"] == UPDATE_IF                          # exact condition
    assert due["outputs"]["run"] == "${{ steps.check.outputs.run }}"
    assert due["permissions"] == {"contents": "read"}
    run = next(s for s in due["steps"] if s.get("id") == "check")
    assert run["run"] == "python3 -m em_macro.rebalance_due"
    assert run["env"]["ONLY_IF_DUE"] == "${{ github.event.inputs.only_if_due }}"
    assert run["env"]["EVENT_NAME"] == "${{ github.event_name }}"
    assert WF["jobs"]["keep-cache"]["if"].endswith("'37 6 * * 1,4'") and "needs" not in WF["jobs"]["keep-cache"]


def test_due_job_checks_out_the_head_of_main():
    co = WF["jobs"]["due"]["steps"][0]
    assert co["uses"].startswith("actions/checkout@") and co["with"] == {"ref": "main"}


def test_update_condition_cases():
    # due succeeded: update follows its answer
    assert update_runs("schedule", MONTHLY, "success", "true") is True
    assert update_runs("schedule", MONTHLY, "success", "false") is False                   # schedule skip
    assert update_runs("workflow_dispatch", "", "success", "true") is True
    assert update_runs("workflow_dispatch", "", "success", "false") is False               # kick: recorded / before the 3rd
    # fail-safe: due failed (or was cancelled by a step error): update still runs, never skips silently
    for ev, sch in (("schedule", MONTHLY), ("workflow_dispatch", "")):
        assert update_runs(ev, sch, "failure", "") is True
    # keep-cache never runs update, whatever due did
    for res, run in (("skipped", ""), ("success", "true"), ("failure", "")):
        assert update_runs("schedule", KEEP, res, run) is False
    # a cancelled workflow does not start update
    assert update_runs("workflow_dispatch", "", "failure", "", cancelled=True) is False


def test_update_steps_are_untouched():
    steps = WF["jobs"]["update"]["steps"]
    assert steps[0] == {"uses": "actions/checkout@v4"}
    assert not any("needs.due" in str(s) or "steps.check" in str(s) for s in steps)      # no step gained a condition
