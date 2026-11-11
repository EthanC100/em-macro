"""Q018 (approved by Ethan 2026-11-11): GitHub creates this repository's schedule events 5.5-10.5 hours late, so a
Claude Code scheduled task ("ledger-daily kick") dispatches ledger-daily at 06:07 and 22:07 UTC, the crons stay as
backups, and the watchdog opens "[ALERT] ledger-daily late" when a kick window had no run. Pure helpers and the
workflow YAML only: no network."""
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ledger import watchdog as W

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def wf(name):
    doc = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)          # PyYAML reads the bare key `on` as True


def test_ledger_daily_keeps_dispatch_and_both_crons_as_backups():
    doc, on = wf("ledger-daily.yml")
    assert "workflow_dispatch" in on
    assert [c["cron"] for c in on["schedule"]] == ["52 5 * * *", "22 9 * * *"]
    steps = "\n".join(str(s.get("run", "")) for s in doc["jobs"]["daily"]["steps"])
    assert "--late-runs" in steps and "--lateness" in steps
    wd, _ = wf("ledger-watchdog.yml")
    assert wd["permissions"].get("actions") == "read"
    assert "--late-runs" in "\n".join(str(s.get("run", "")) for s in wd["jobs"]["watchdog"]["steps"])


def test_the_kick_task_is_in_the_inventory():
    doc = (ROOT / "docs/agent-system.md").read_text(encoding="utf-8")
    row = next(l for l in doc.splitlines() if "**ledger-daily kick**" in l)
    assert "06:07 and 22:07 UTC" in row and "dispatch" in row and "claude-sonnet-5-5" in row


def runs(*starts):
    return {"workflow_runs": [{"event": "workflow_dispatch", "run_started_at": s} for s in starts]}


def test_a_kick_window_without_a_run_is_late():
    now = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    # 11 Nov 22:07 and 12 Nov 06:07 kicked on time; after that only a cron run 1.5 hours after the 13 Nov 06:07 kick
    res = W.late_check(runs("2026-11-11T22:07:09Z", "2026-11-12T06:08:00Z", "2026-11-13T07:40:00Z"), now)
    assert res["late"] and res["title"] == W.LATE_TITLE
    assert res["missed"] == ["2026-11-12T22:07:00+00:00", "2026-11-13T06:07:00+00:00"]
    assert "2026-11-12 22:07 UTC" in res["body"] and res["stale"]            # marks_alert.sh reads "stale"
    ok = W.late_check(runs("2026-11-11T22:07:09Z", "2026-11-12T06:08:00Z", "2026-11-12T22:30:00Z",
                           "2026-11-13T05:55:00Z"), now)
    assert not ok["late"] and ok["missed"] == [] and ok["close_comment"]


def test_windows_before_the_task_existed_or_still_open_are_not_judged():
    assert W.late_check(runs(), datetime(2026, 11, 11, 22, 30, tzinfo=UTC))["missed"] == []     # window still open
    assert W.late_check(runs(), datetime(2026, 11, 11, 22, 53, tzinfo=UTC))["missed"] == ["2026-11-11T22:07:00+00:00"]
    assert W.kick_windows(datetime(2026, 11, 11, 20, 0, tzinfo=UTC)) == []                     # before the task


def test_a_successful_late_run_does_not_close_the_lateness_alert():
    """ledger-daily's success step closes every open alert whose title starts with "[ALERT] ledger-daily"; the lateness
    alert must not match, or a late run would close the alert about its own lateness."""
    doc, _ = wf("ledger-daily.yml")
    close = next(s["run"] for s in doc["jobs"]["daily"]["steps"] if s.get("name") == "Close alert issues after a successful run")
    prefix = close.split('startswith("', 1)[1].split('"', 1)[0]
    assert prefix == "[ALERT] ledger-daily" and not W.LATE_TITLE.startswith(prefix)


def test_the_job_summary_states_how_late_the_run_started():
    line = W.lateness("schedule", datetime(2026, 11, 10, 13, 48, 23, tzinfo=UTC), "52 5 * * *")
    assert "476 minutes after 05:52 UTC" in line and "LATE" in line
    line = W.lateness("workflow_dispatch", datetime(2026, 11, 11, 22, 9, 30, tzinfo=UTC))
    assert "2 minutes after 22:07 UTC" in line and "LATE" not in line
