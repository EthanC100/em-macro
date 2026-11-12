"""Q002 (approved by Ethan 2026-11-12): a kick dispatches systematic-monthly at 07:23 UTC on the 3rd, the 3rd's cron
stays as a backup and a second backup runs on the 4th; a `due` gate lets only one of them rebalance, and never changes
what the update job computes. Pure helpers, the workflow YAML and a temporary results folder: no network, no git."""
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from em_macro import rebalance as R
from em_macro import rebalance_due as D

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/systematic.yml"
HEADER = ",".join(R.LOG_COLUMNS) + "\n"
NOV = HEADER + "2026-10,2026-11,2026-11-03,2026-11-04,1,LATE by 1 day,8\n"            # today's log on main
DEC = NOV + "2026-11,2026-12,2026-12-03,2026-12-03,0,on time,8\n"


def wf():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)          # PyYAML reads the bare key `on` as True


def test_the_workflow_has_the_kick_input_and_two_backup_schedules():
    doc, on = wf()
    assert [c["cron"] for c in on["schedule"]] == ["23 7 3 * *", "23 7 4 * *", "37 6 * * 1,4"]
    inp = on["workflow_dispatch"]["inputs"]["only_if_due"]
    assert inp["type"] == "boolean" and inp["default"] is False
    due, update = doc["jobs"]["due"], doc["jobs"]["update"]
    assert "'23 7 3 * *'" in due["if"] and "'23 7 4 * *'" in due["if"] and "37 6" not in due["if"]
    assert due["permissions"] == {"contents": "read"} and due["outputs"]["run"] == "${{ steps.gate.outputs.run }}"
    gate = "\n".join(str(s.get("run", "")) for s in due["steps"])
    assert "git fetch" in gate and "FETCH_HEAD:results/systematic/rebalance_log.csv" in gate
    assert "em_macro.rebalance_due" in gate and "GITHUB_OUTPUT" in gate
    assert "git push" not in gate and "git commit" not in gate                       # the gate writes nothing
    assert update["needs"] == "due"
    assert "needs.due.outputs.run == 'true'" in update["if"] and "needs.due.result == 'failure'" in update["if"]
    assert "needs.due.result != 'skipped'" in update["if"]                            # keep-cache never rebalances
    assert doc["jobs"]["keep-cache"]["if"] == "github.event_name == 'schedule' && github.event.schedule == '37 6 * * 1,4'"
    assert doc["concurrency"] == {"group": "systematic-monthly", "cancel-in-progress": False}


def test_the_update_job_computes_exactly_as_before():
    """The update job's steps (and so what it computes and commits) are the ones main had before Q002 (a5f9dd4).
    Skipped where that commit is not in the checkout (systematic-monthly's own depth-1 checkout), so this test can
    never stop a rebalance commit (Q007)."""
    got = subprocess.run(["git", "show", "a5f9dd4:.github/workflows/systematic.yml"], cwd=ROOT,
                         capture_output=True, text=True)
    if got.returncode != 0:
        pytest.skip("commit a5f9dd4 (main before Q002) is not in this checkout")
    before = yaml.safe_load(got.stdout)
    doc, _ = wf()
    for k in ("steps", "runs-on", "timeout-minutes", "defaults"):
        assert doc["jobs"]["update"][k] == before["jobs"]["update"][k]
    assert doc["permissions"] == before["permissions"]


def test_the_gate():
    d3, d4 = date(2026, 12, 3), date(2026, 12, 4)
    assert D.due_as_of(d3) == "2026-11" and D.due_as_of(date(2027, 1, 3)) == "2026-12"
    # 3 Dec: November's row is last month's rebalance, so December's is due (kick and backups alike)
    for event, only in (("workflow_dispatch", True), ("schedule", False)):
        assert D.decide(event, only, NOV, d3)[0] is True
    # once the kick's run committed, the late 3rd cron and the 4th's backup do nothing
    run, reason = D.decide("schedule", False, DEC, d3)
    assert run is False and "already rebalanced this month" in reason
    assert D.decide("schedule", False, DEC, d4)[0] is False
    assert D.decide("workflow_dispatch", True, DEC, d4)[0] is False                   # a second kick too
    # a manual "Run workflow" always runs (re-runs after a D005 or v1.1 failure)
    assert D.decide("workflow_dispatch", False, DEC, d4) == (True, "manual dispatch: runs whatever the log says")
    # a re-run of November's rebalance on 1 December does not count as December's
    early = NOV.replace("2026-11-04,1,LATE by 1 day", "2026-12-01,28,LATE by 28 days")
    assert D.decide("schedule", False, early, d3)[0] is True
    # fail-open: an unreadable or garbled log runs the update
    assert D.decide("schedule", False, None, d3)[0] is True
    assert D.decide("schedule", False, "not,a\nlog", d3)[0] is True
    # 12 Nov (today): November's rebalance has run, so a kick dispatched now would do nothing
    assert D.decide("workflow_dispatch", True, NOV, date(2026, 11, 12))[0] is False


def test_the_cli_prints_github_output_lines(tmp_path):
    log = tmp_path / "rebalance_log.csv"
    log.write_text(DEC, encoding="utf-8")
    out = subprocess.run([sys.executable, "-m", "em_macro.rebalance_due", "--event", "schedule", "--log", str(log),
                          "--today", "2026-12-04"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert out.splitlines()[0] == "run=false" and out.splitlines()[1].startswith("reason=already rebalanced")
    out = subprocess.run([sys.executable, "-m", "em_macro.rebalance_due", "--event", "workflow_dispatch",
                          "--only-if-due", "true", "--log", str(tmp_path / "missing.csv"), "--today", "2026-12-03"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert out.splitlines()[0] == "run=true" and "fail-open" in out


def test_a_failed_first_run_is_retried_by_the_backup_and_logged_late_with_unchanged_positions(tmp_path):
    """3 Dec: the kick's run fails before its commit, so main's log still ends with November's row. The 4th's
    backup finds the rebalance due, runs the unchanged update job, and the rebalance log says LATE by 1 day; the
    position values written by `systematic update` are kept verbatim."""
    out = tmp_path / "systematic"
    out.mkdir()
    (out / "rebalance_log.csv").write_text(NOV, encoding="utf-8")
    assert D.decide("schedule", False, (out / "rebalance_log.csv").read_text(), date(2026, 12, 3))[0] is True
    # the failed run committed nothing: the backup on the 4th is still due
    assert D.decide("schedule", False, (out / "rebalance_log.csv").read_text(), date(2026, 12, 4))[0] is True
    pos = pd.DataFrame({"as_of": ["2026-11"] * 2, "effective_from": ["2026-12"] * 2, "instrument": ["BRL", "MX10Y"],
                        "size_pct_of_capital": ["34.810", "-125.850"]})
    pos.to_csv(out / "positions.csv", index=False)
    row = R.record(today=date(2026, 12, 4), out=out)
    assert row["status"] == "LATE by 1 day" and row["scheduled_date"] == "2026-12-03"
    after = pd.read_csv(out / "positions.csv", dtype=str)
    assert list(after["size_pct_of_capital"]) == ["34.810", "-125.850"]
    log = (out / "rebalance_log.csv").read_text(encoding="utf-8")
    assert "2026-11,2026-12,2026-12-03,2026-12-04,1,LATE by 1 day,2" in log
    # and once that is on main, nothing else rebalances in December
    assert D.decide("schedule", False, log, date(2026, 12, 4))[0] is False


def test_the_kick_task_is_in_the_inventory():
    doc = (ROOT / "docs/agent-system.md").read_text(encoding="utf-8")
    row = next(l for l in doc.splitlines() if "**systematic-monthly kick**" in l)
    assert "07:23 UTC on the 3rd" in row and "only_if_due" in row and "claude-sonnet-5-5" in row
