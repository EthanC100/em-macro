"""Q033: docs/agent-system.md does not describe a :45 Janus quick check as running when the records show none, and
its one quoted docs/todo.md line (the Ledger forecast resolver row) exists in docs/todo.md.

Two checks:
- a line of docs/agent-system.md that names a :45 slot (``:45`` not part of a clock time such as 23:45, or "every
  30 minutes", or "two hourly") describes that slot as running unless it carries a dated observation ("none since"
  or "none recorded since"). Such a line is stale while the quick-check records (``type`` ``check`` in
  data/janus/records.jsonl) hold fewer than ``MIN_RUNS`` checks in the :45 half-hour (minutes 45-14 past the hour,
  the other half from Q028's :15 slot) in the 7 days ending at the latest check;
- the docs/todo.md text quoted on the Ledger forecast resolver row (`` `docs/todo.md`: "..." ``) exists in
  docs/todo.md. Only that one row is checked, so later edits to other todo.md lines on main cannot fail it.

docs/agent-system.md and docs/todo.md are hand-edited prose and data/janus/ belongs to the Janus writers;
systematic-monthly runs the whole suite before it commits the rebalance, so the check on the real files never
blocks that commit: if a file is absent or unreadable it skips, and a stale line found skips with a message unless
NIGHT_SHIFT_STRICT=1 (pr-review, promote), where it fails. The matchers themselves are tested on fixture text and
fixture records, which no writer or hand edit on main can change.
"""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENT_SYSTEM = ROOT / "docs/agent-system.md"
TODO = ROOT / "docs/todo.md"
RECORDS = ROOT / "data/janus/records.jsonl"

MIN_RUNS = 3
WINDOW = timedelta(days=7)

SLOT_45 = re.compile(r"(?<![\d:]):45\b|every 30 minutes|two hourly", re.I)
OBSERVED = re.compile(r"\bnone (?:recorded )?since\b", re.I)
RESOLVER_ROW = re.compile(r"ledger forecast resolver", re.I)
TODO_QUOTE = re.compile(r"`docs/todo\.md`:\s*\"([^\"]+)\"")


def slot45_runs(records, window=WINDOW):
    """True if the `window` ending at the latest quick check holds at least MIN_RUNS checks in the :45 half-hour."""
    times = []
    for r in records:
        if r.get("type") != "check":
            continue
        try:
            times.append(datetime.fromisoformat(str(r.get("time") or r.get("recorded_at"))))
        except ValueError:
            continue
    if not times:
        return False
    last = max(times)
    return sum(1 for t in times if last - t < window and not 15 <= t.minute < 45) >= MIN_RUNS


def stale_45_lines(text, runs45):
    """Return (line number, line) for each line that describes a :45 slot as running when none runs."""
    if runs45:
        return []
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1)
            if SLOT_45.search(line) and not OBSERVED.search(line)]


def missing_todo_quotes(text, todo_text):
    """Return (line number, quote) for each docs/todo.md quote on the forecast resolver row missing from todo.md."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if RESOLVER_ROW.search(line):
            out.extend((n, q) for q in TODO_QUOTE.findall(line) if q not in todo_text)
    return out


def _strict():
    return os.environ.get("NIGHT_SHIFT_STRICT") == "1"


# --- the matchers, on fixture text and records -------------------------------------------------------------------

OLD = (
    "| **Janus Quick Check** (trig_x; `docs/janus/quick_check.md`) | hourly at :15, every day | same | same |\n"
    "| **Janus Quick Check 2** (trig_y) | hourly at :45, every day | same | same | same |\n"
    "| Ledger forecast resolver (`docs/ledger/forecast_resolver.md`) | documented as a daily task, **but not on the "
    "account's task list** (`docs/todo.md`: \"Create the scheduled tasks\", unticked) | would be Ethan | x | - |\n"
    "Janus daily review (23:00-23:45 UTC), so the Janus quick checks (every 30 minutes, all night) never collide.\n"
)

NEW = (
    "| **Janus Quick Check** (trig_x; `docs/janus/quick_check.md`) | hourly at :15, every day | same | same |\n"
    "| **Janus Quick Check 2** (trig_y) | hourly at :45 until 2026-11-13 12:49Z, none recorded since (Ethan to "
    "confirm) | same | same | same |\n"
    "| Ledger forecast resolver (`docs/ledger/forecast_resolver.md`) | documented as a daily task, **but not on the "
    "account's task list** (`docs/todo.md`: \"Create the remaining scheduled tasks\", unticked) | would be Ethan | "
    "x | - |\n"
    "Janus daily review (23:00-23:45 UTC), so the Janus quick checks (hourly, all night) never collide.\n"
)

TODO_FIXTURE = (
    "- [x] Create the Janus quick-check scheduled task at :15\n"
    "- [ ] Create the remaining scheduled tasks (Janus quick check at :45, Ledger forecast resolver, Ledger monthly "
    "letters)\n"
)


def _checks(day, minutes_by_hour):
    return [{"type": "check", "time": f"{day}T{h:02d}:{m:02d}:00+00:00"} for h, m in minutes_by_hour]


BOTH_13 = _checks("2026-11-13", [(h, m) for h in range(0, 13) for m in (18, 47)])
ONLY_15_23 = _checks("2026-11-23", [(h, 17) for h in range(0, 15)])
BOTH_20 = _checks("2026-11-20", [(h, m) for h in range(0, 4) for m in (18, 47)])


def test_slot45_from_records():
    assert slot45_runs(BOTH_13) is True
    assert slot45_runs(ONLY_15_23) is False
    # :45 checks ten days before the latest check are outside the 7-day window.
    assert slot45_runs(BOTH_13 + ONLY_15_23) is False
    # Three days before the latest check they are inside it.
    assert slot45_runs(BOTH_20 + ONLY_15_23) is True
    # One stray check in the :45 half is not a running task.
    assert slot45_runs(ONLY_15_23 + _checks("2026-11-22", [(15, 1)])) is False
    assert slot45_runs([]) is False
    assert slot45_runs([{"type": "review", "time": "2026-11-23T12:47:00+00:00"}] * 5) is False


def test_matcher_flags_the_old_lines_when_no_45_check_runs():
    assert [n for n, _ in stale_45_lines(OLD, slot45_runs(BOTH_13 + ONLY_15_23))] == [2, 4]
    assert missing_todo_quotes(OLD, TODO_FIXTURE) == [(3, "Create the scheduled tasks")]


def test_matcher_accepts_the_dated_observation():
    assert stale_45_lines(NEW, slot45_runs(BOTH_13 + ONLY_15_23)) == []
    assert missing_todo_quotes(NEW, TODO_FIXTURE) == []


def test_matcher_accepts_the_old_lines_while_the_45_task_runs():
    assert stale_45_lines(OLD, slot45_runs(BOTH_13)) == []


def test_clock_times_are_not_slots():
    assert stale_45_lines("windows 23:00-23:45 UTC and 07:15-09:30 UTC; 12:45:00Z\n", False) == []


# --- the real files ----------------------------------------------------------------------------------------------

def _read(path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(ROOT)} not found: docs/agent-system.md's quick-check lines are not checked")
    try:
        return path.read_text()
    except OSError as exc:
        pytest.skip(f"{path.relative_to(ROOT)} unreadable ({exc}): docs/agent-system.md's lines are not checked")


def _report(msg):
    if _strict():
        raise AssertionError(msg)
    pytest.skip(f"{msg} (skipped: set NIGHT_SHIFT_STRICT=1 to enforce)")


def test_agent_system_45_slot_lines():
    text = _read(AGENT_SYSTEM)
    raw = _read(RECORDS)
    try:
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    except ValueError as exc:
        pytest.skip(f"data/janus/records.jsonl unreadable ({exc}): docs/agent-system.md's lines are not checked")
    stale = stale_45_lines(text, slot45_runs(records))
    if stale:
        _report(f"docs/agent-system.md describes a :45 quick check as running, but the records show fewer than "
                f"{MIN_RUNS} :45 checks in the last 7 days: "
                + "; ".join(f"line {n}: {line}" for n, line in stale))


def test_agent_system_todo_quote_exists():
    missing = missing_todo_quotes(_read(AGENT_SYSTEM), _read(TODO))
    if missing:
        _report("docs/agent-system.md quotes docs/todo.md text that docs/todo.md no longer has: "
                + "; ".join(f"line {n}: \"{q}\"" for n, q in missing))
