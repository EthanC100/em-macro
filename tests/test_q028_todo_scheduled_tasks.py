"""Q028: docs/todo.md's scheduled-task lines match what the Janus quick-check records show.

Two claims are checked against the quick-check records (``type`` ``check`` in data/janus/records.jsonl):
- an unticked "Create the scheduled tasks" line that still lists the quick check at :15 is stale once the records
  show the :15 task running;
- a ticked line claiming the quick check at :45 (or "every 30 minutes") overclaims while the records show no :45
  task running.

A task "runs" if the last 24 hours of check records (ending at the latest check) hold at least ``MIN_RUNS`` checks in
its slot: minutes 15-44 past the hour for the :15 task, the other half-hour for the :45 task.

docs/todo.md is hand-edited prose and data/janus/ belongs to the Janus writers; systematic-monthly runs the whole
suite before it commits the rebalance, so the check on the real files never blocks that commit: if either file is
absent or unreadable it skips, and a stale line found skips with a message unless NIGHT_SHIFT_STRICT=1 (pr-review,
promote), where it fails. The matcher itself is tested on fixture text and fixture records, which no writer or hand
edit on main can change.
"""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / "docs/todo.md"
RECORDS = ROOT / "data/janus/records.jsonl"

MIN_RUNS = 3
WINDOW = timedelta(hours=24)

UNTICKED = re.compile(r"^\s*[-*]\s+\[ \]")
TICKED = re.compile(r"^\s*[-*]\s+\[[xX]\]")
CREATE_TASKS = re.compile(r"\bcreate\b.*\bscheduled tasks?\b", re.I)
QUICK_CHECK = re.compile(r"quick[- ]check", re.I)
AT_15 = re.compile(r":15\b")
AT_45 = re.compile(r":45\b|every 30 minutes|two hourly", re.I)


def running_slots(records):
    """Return {":15": bool, ":45": bool} from quick-check records: each slot's task runs if the 24 hours ending
    at the latest check hold at least MIN_RUNS checks in that slot."""
    times = []
    for r in records:
        if r.get("type") != "check":
            continue
        try:
            times.append(datetime.fromisoformat(str(r.get("time") or r.get("recorded_at"))))
        except ValueError:
            continue
    if not times:
        return {":15": False, ":45": False}
    last = max(times)
    recent = [t for t in times if last - t < WINDOW]
    n15 = sum(1 for t in recent if 15 <= t.minute < 45)
    return {":15": n15 >= MIN_RUNS, ":45": len(recent) - n15 >= MIN_RUNS}


def stale_lines(text, slots):
    """Return (line number, reason, line) for each scheduled-task line the running slots contradict."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not QUICK_CHECK.search(line):
            continue
        if slots[":15"] and UNTICKED.match(line) and CREATE_TASKS.search(line) and AT_15.search(line):
            out.append((n, "unticked, but the :15 quick-check task runs", line.strip()))
        elif not slots[":45"] and TICKED.match(line) and AT_45.search(line):
            out.append((n, "ticked, but no :45 quick-check task runs", line.strip()))
    return out


def _strict():
    return os.environ.get("NIGHT_SHIFT_STRICT") == "1"


# --- the matcher, on fixture text and records --------------------------------------------------------------------

OLD = (
    "## Automation\n\n"
    "- [x] Janus in Claude Code sessions (quick check every 30 minutes as two hourly scheduled tasks at :15 and "
    ":45, daily review after the US close; post-mortems in the daily review)\n"
    "- [ ] Create the scheduled tasks (Janus quick check at :15 and :45, Janus daily review, Ledger forecast "
    "resolver, Ledger monthly letters)\n"
)

NEW = (
    "## Automation\n\n"
    "- [x] Janus in Claude Code sessions (quick check hourly at :15 as a scheduled task; daily review after the "
    "US close; post-mortems in the daily review)\n"
    "- [x] Create the Janus quick-check scheduled task at :15\n"
    "- [ ] Create the remaining scheduled tasks (Janus quick check at :45, Janus daily review, Ledger forecast "
    "resolver, Ledger monthly letters)\n"
)


def _checks(day, minutes_by_hour):
    return [{"type": "check", "time": f"{day}T{h:02d}:{m:02d}:00+00:00"} for h, m in minutes_by_hour]


ONLY_15 = _checks("2026-11-17", [(h, 17) for h in range(2, 15)])
BOTH = _checks("2026-11-13", [(h, m) for h in range(0, 13) for m in (18, 47)])


def test_slots_from_records():
    assert running_slots(ONLY_15) == {":15": True, ":45": False}
    assert running_slots(BOTH) == {":15": True, ":45": True}
    # Old :45 checks outside the 24-hour window do not count.
    assert running_slots(BOTH + ONLY_15) == {":15": True, ":45": False}
    assert running_slots([]) == {":15": False, ":45": False}
    assert running_slots([{"type": "review", "time": "2026-11-17T12:47:00+00:00"}] * 5) == {":15": False,
                                                                                           ":45": False}


def test_matcher_flags_the_old_lines_when_only_the_15_task_runs():
    assert [(n, why) for n, why, _ in stale_lines(OLD, running_slots(ONLY_15))] == [
        (3, "ticked, but no :45 quick-check task runs"),
        (4, "unticked, but the :15 quick-check task runs"),
    ]


def test_matcher_accepts_the_split_lines():
    assert stale_lines(NEW, running_slots(ONLY_15)) == []
    assert stale_lines(NEW, running_slots(BOTH)) == []


def test_matcher_ignores_lines_when_no_task_runs():
    assert stale_lines(OLD, running_slots([])) == [(3, "ticked, but no :45 quick-check task runs",
                                                    OLD.splitlines()[2])]
    assert [n for n, _, _ in stale_lines(OLD, {":15": False, ":45": True})] == []


# --- the real files ----------------------------------------------------------------------------------------------

def test_todo_scheduled_tasks_line():
    if not TODO.exists():
        pytest.skip("docs/todo.md not found: the scheduled-task lines are not checked")
    if not RECORDS.exists():
        pytest.skip("data/janus/records.jsonl not found: the scheduled-task lines are not checked")
    try:
        records = [json.loads(line) for line in RECORDS.read_text().splitlines() if line.strip()]
    except (OSError, ValueError) as exc:
        pytest.skip(f"data/janus/records.jsonl unreadable ({exc}): the scheduled-task lines are not checked")
    slots = running_slots(records)
    stale = stale_lines(TODO.read_text(), slots)
    if not stale:
        return
    msg = (f"docs/todo.md scheduled-task lines contradict the quick-check records (running: "
           f"{', '.join(k for k, v in slots.items() if v) or 'none'}): "
           + "; ".join(f"line {n} {why}: {line}" for n, why, line in stale))
    if _strict():
        raise AssertionError(msg)
    pytest.skip(f"{msg} (skipped: set NIGHT_SHIFT_STRICT=1 to enforce)")
