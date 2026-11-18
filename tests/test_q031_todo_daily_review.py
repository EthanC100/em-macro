"""Q031: docs/todo.md does not list the Janus daily review as an uncreated scheduled task once its runs are recorded.

The daily review is a scheduled task firing at about 23:07 UTC; each run leaves a ``type`` ``run`` record with
``session`` ``daily_review`` in data/janus/records.jsonl. The task "runs" if those records show evening runs (22:00
UTC or later, the scheduled slot; hand-started morning reviews do not count) on at least ``MIN_DAYS`` distinct days.
Missed days are tolerated: there is no recency window, so a gap (13-16 Nov 2026) never makes the task look uncreated.
Once it runs, an unticked "Create ... scheduled tasks" line that still lists the Janus daily review is stale.

docs/todo.md is hand-edited prose and data/janus/ belongs to the Janus writers; systematic-monthly runs the whole
suite before it commits the rebalance, so the check on the real files never blocks that commit: if either file is
absent or unreadable it skips, and a stale line found skips with a message unless NIGHT_SHIFT_STRICT=1 (pr-review,
promote), where it fails. The matcher itself is tested on fixture text and fixture records, which no writer or hand
edit on main can change.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / "docs/todo.md"
RECORDS = ROOT / "data/janus/records.jsonl"

MIN_DAYS = 3
SLOT_FROM_HOUR = 22  # the task fires at about 23:07 UTC (config/night.yaml busy_windows_utc)

UNTICKED = re.compile(r"^\s*[-*]\s+\[ \]")
TICKED = re.compile(r"^\s*[-*]\s+\[[xX]\]")
CREATE_TASKS = re.compile(r"\bcreate\b.*\bscheduled tasks?\b", re.I)
DAILY_REVIEW = re.compile(r"daily[- ]review", re.I)
PENDING = {
    "quick check at :45": re.compile(r"quick[- ]check\b.*:45\b", re.I),
    "forecast resolver": re.compile(r"forecast resolver", re.I),
    "monthly letters": re.compile(r"monthly letters", re.I),
}


def review_days(records):
    """Return the sorted distinct UTC dates with a daily-review run record in the scheduled evening slot."""
    days = set()
    for r in records:
        if r.get("type") != "run" or r.get("session") != "daily_review":
            continue
        try:
            t = datetime.fromisoformat(str(r.get("decided_at") or r.get("recorded_at")))
        except ValueError:
            continue
        if t.hour >= SLOT_FROM_HOUR:
            days.add(t.date().isoformat())
    return sorted(days)


def review_task_runs(records):
    return len(review_days(records)) >= MIN_DAYS


def stale_lines(text, runs):
    """Return (line number, line) for each unticked create-scheduled-tasks line listing the running daily review."""
    if not runs:
        return []
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1)
            if UNTICKED.match(line) and CREATE_TASKS.search(line) and DAILY_REVIEW.search(line)]


def pending_items(text):
    """Return the names in PENDING that appear on an unticked line."""
    unticked = [line for line in text.splitlines() if UNTICKED.match(line)]
    return sorted(name for name, rx in PENDING.items() if any(rx.search(line) for line in unticked))


def _strict():
    return os.environ.get("NIGHT_SHIFT_STRICT") == "1"


# --- the matcher, on fixture text and records --------------------------------------------------------------------

OLD = (
    "## Automation\n\n"
    "- [x] Janus in Claude Code sessions (quick check hourly at :15 as a scheduled task, daily review after the US "
    "close; post-mortems in the daily review)\n"
    "- [x] Create the Janus quick-check scheduled task at :15 (hourly; its checks are in the Janus records from "
    "17 Nov 2026)\n"
    "- [ ] Create the remaining scheduled tasks (Janus quick check at :45, Janus daily review, Ledger forecast "
    "resolver, Ledger monthly letters)\n"
)

NEW = (
    "## Automation\n\n"
    "- [x] Janus in Claude Code sessions (quick check hourly at :15 as a scheduled task, daily review after the US "
    "close; post-mortems in the daily review)\n"
    "- [x] Create the Janus quick-check scheduled task at :15 (hourly; its checks are in the Janus records from "
    "17 Nov 2026)\n"
    "- [x] Create the Janus daily-review scheduled task (about 23:07 UTC, after the US close; its runs are in the "
    "Janus records from 6 Nov 2026)\n"
    "- [ ] Create the remaining scheduled tasks (Janus quick check at :45, Ledger forecast resolver, Ledger monthly "
    "letters)\n"
)


def _run(stamp, session="daily_review"):
    return {"type": "run", "session": session, "decided_at": stamp}


# 6-12 Nov evening runs, a gap on 13-16 Nov, then 17 Nov: the shape of the real records.
EVENINGS = [_run(f"2026-11-{d:02d}T23:{7 + d:02d}:00+00:00") for d in (6, 7, 8, 9, 10, 11, 12, 17)]
MORNINGS = [_run("2026-11-10T07:05:34+00:00"), _run("2026-11-10T10:30:09+00:00"), _run("2026-11-06T12:11:53+00:00")]
QUICK = [_run(f"2026-11-1{d}T23:20:00+00:00", session="quick_check") for d in range(5)]
CHECKS = [{"type": "check", "time": f"2026-11-1{d}T23:17:00+00:00"} for d in range(5)]


def test_review_days_from_records():
    assert review_days(EVENINGS) == ["2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09", "2026-11-10",
                                     "2026-11-11", "2026-11-12", "2026-11-17"]
    assert review_task_runs(EVENINGS)
    # Hand-started morning reviews, quick-check runs and check records do not show a scheduled daily review.
    assert review_days(MORNINGS + QUICK + CHECKS) == []
    assert not review_task_runs(MORNINGS + QUICK + CHECKS)
    assert not review_task_runs(EVENINGS[:2])
    assert not review_task_runs([])


def test_missed_days_are_tolerated():
    # Three evening runs weeks apart still show the task; the latest run being days old does not hide it.
    spread = [_run("2026-11-06T23:09:55+00:00"), _run("2026-11-12T23:19:01+00:00"),
              _run("2026-11-17T23:13:50+00:00")]
    assert review_task_runs(spread)
    assert review_task_runs(EVENINGS[:7])  # records ending on 12 Nov, before the 13-16 Nov gap


def test_matcher_flags_the_old_line_when_the_review_runs():
    assert stale_lines(OLD, review_task_runs(EVENINGS)) == [(5, OLD.splitlines()[4].strip())]


def test_matcher_accepts_the_split_lines():
    assert stale_lines(NEW, review_task_runs(EVENINGS)) == []


def test_matcher_ignores_lines_when_no_review_runs():
    assert stale_lines(OLD, review_task_runs(MORNINGS)) == []


def test_split_keeps_the_other_tasks_unticked():
    assert pending_items(OLD) == pending_items(NEW) == ["forecast resolver", "monthly letters",
                                                        "quick check at :45"]


def test_split_wording_passes_the_q028_matcher():
    from test_q028_todo_scheduled_tasks import stale_lines as q028_stale

    for slots in ({":15": True, ":45": False}, {":15": True, ":45": True}, {":15": False, ":45": False}):
        assert q028_stale(NEW, slots) == []


# --- the real files ----------------------------------------------------------------------------------------------

def test_todo_daily_review_line():
    if not TODO.exists():
        pytest.skip("docs/todo.md not found: the daily-review task line is not checked")
    if not RECORDS.exists():
        pytest.skip("data/janus/records.jsonl not found: the daily-review task line is not checked")
    try:
        records = [json.loads(line) for line in RECORDS.read_text().splitlines() if line.strip()]
    except (OSError, ValueError) as exc:
        pytest.skip(f"data/janus/records.jsonl unreadable ({exc}): the daily-review task line is not checked")
    days = review_days(records)
    stale = stale_lines(TODO.read_text(), len(days) >= MIN_DAYS)
    if not stale:
        return
    msg = (f"docs/todo.md lists the Janus daily review as an uncreated scheduled task, but the Janus records show "
           f"scheduled daily-review runs on {len(days)} days ({days[0]} to {days[-1]}): "
           + "; ".join(f"line {n}: {line}" for n, line in stale))
    if _strict():
        raise AssertionError(msg)
    pytest.skip(f"{msg} (skipped: set NIGHT_SHIFT_STRICT=1 to enforce)")
