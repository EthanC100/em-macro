"""Q023: docs/todo.md does not call the election tracker unmerged or its jobs inactive once it is on main.

Preconditions: ``data/elections/`` and ``.github/workflows/elections-daily.yml`` exist (the tracker is merged).
Then docs/todo.md must have no unticked line saying the election tracker is unmerged or its jobs inactive, and no
line (ticked or not) saying ``data/elections/`` does not exist on main.

docs/todo.md is hand-edited prose and systematic-monthly runs the whole suite before it commits the rebalance, so
the check on the real file never blocks that commit: if the preconditions or docs/todo.md are absent it skips, and
a stale line found skips with a message unless NIGHT_SHIFT_STRICT=1 (pr-review, promote), where it fails. The
matcher itself is tested on fixture text, which no writer or hand edit on main can change.
"""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / "docs/todo.md"
ELECTIONS_DIR = ROOT / "data/elections"
ELECTIONS_DAILY = ROOT / ".github/workflows/elections-daily.yml"

UNTICKED = re.compile(r"^\s*[-*]\s+\[ \]")
TRACKER = re.compile(r"election[- ]tracker", re.I)
UNMERGED = re.compile(r"\bunmerged\b|\bnot (?:yet )?merged\b|\buntil merged\b|\binactive\b", re.I)
NO_DIR = re.compile(
    r"data/elections/?`?\s+(?:does not|doesn't|do not) exist|data/elections/?`?\s+(?:is )?(?:not|missing) on main",
    re.I,
)


def stale_lines(text):
    """Return (line number, line) for each line that calls the merged election tracker unmerged or inactive."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if NO_DIR.search(line) or (UNTICKED.match(line) and TRACKER.search(line) and UNMERGED.search(line)):
            out.append((n, line.strip()))
    return out


def _strict():
    return os.environ.get("NIGHT_SHIFT_STRICT") == "1"


# --- the matcher, on fixture text -------------------------------------------------------------------------------

OLD = (
    "## Technical\n\n"
    "- [ ] Election tracker unmerged (`build/election-tracker`; `data/elections/` does not exist on main, "
    "the app falls back to `data/events/`)\n"
    "- [ ] Background file overstates the election edge\n\n"
    "## Automation\n\n"
    "- [ ] Election-tracker jobs inactive until merged\n"
)


def test_matcher_flags_the_stale_wording():
    assert [n for n, _ in stale_lines(OLD)] == [3, 8]


def test_matcher_flags_the_missing_directory_claim_even_when_ticked():
    assert stale_lines("- [x] Done (`data/elections/` does not exist on main)\n")


def test_matcher_ignores_ticked_and_unrelated_lines():
    text = (
        "- [x] Election tracker unmerged\n"
        "- [x] Election-tracker jobs inactive until merged\n"
        "- [ ] Background file overstates the election edge\n"
        "- [ ] Election tracker merged (`data/elections/` on main)\n"
        "- [ ] Some other job inactive\n"
    )
    assert stale_lines(text) == []


# --- the real file -----------------------------------------------------------------------------------------------

def test_todo_election_lines():
    if not (ELECTIONS_DIR.is_dir() and ELECTIONS_DAILY.exists()):
        pytest.skip("data/elections/ or .github/workflows/elections-daily.yml not found: the election tracker "
                    "is not merged here, so the docs/todo.md election lines are not checked")
    if not TODO.exists():
        pytest.skip("docs/todo.md not found: the election lines are not checked")
    stale = stale_lines(TODO.read_text())
    if not stale:
        return
    msg = ("docs/todo.md calls the election tracker unmerged or inactive, but data/elections/ and "
           "elections-daily.yml exist: " + "; ".join(f"line {n}: {line}" for n, line in stale))
    if _strict():
        raise AssertionError(msg)
    pytest.skip(f"{msg} (skipped: set NIGHT_SHIFT_STRICT=1 to enforce)")
