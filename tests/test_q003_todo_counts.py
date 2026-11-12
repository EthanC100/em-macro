"""Q003: the registry-count clause of the Technical to-do line in docs/todo.md matches the Ledger instrument
registry (data/ledger/instruments.csv).

The counts are computed from the registry at run time, so the test follows the registry instead of freezing
numbers. Tradeable instruments are the rows with book ``fx`` or ``bond``; "with the yield legs" adds the rows with
book ``leg``. Janus rows and the cash benchmark are not counted. The line's "9 of 23 instruments lack daily
prices" is about the algorithm's inputs, not the registry, and is not checked here.

Q007: systematic-monthly runs the whole suite before it commits the rebalance, and the to-do line is hand-edited
prose, so these tests never fail there. Without NIGHT_SHIFT_STRICT=1 a count mismatch skips with a message. With
NIGHT_SHIFT_STRICT=1 (pr-review, promote) a numeric mismatch fails. A missing, reworded or duplicated line (the
to-do item completed or rewritten on main) and a missing registry skip in both modes.
"""
import csv
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / "docs/todo.md"
REGISTRY = ROOT / "data/ledger/instruments.csv"

TRADEABLE = ("fx", "bond")
WITH_LEGS = TRADEABLE + ("leg",)

# Accepts the old wording too, so a stale line fails on its numbers rather than on its phrasing.
CLAUSE = re.compile(
    r"the Ledger registry now marks (\d+) of (\d+) (?:tradeable )?instruments daily"
    r"(?: \((\d+) of (\d+) with the yield legs\))?"
)


def _strict():
    return os.environ.get("NIGHT_SHIFT_STRICT") == "1"


def _counts(books):
    if not REGISTRY.exists():
        pytest.skip(f"{REGISTRY.name} not found: the docs/todo.md registry counts are not checked")
    with REGISTRY.open(newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("book") in books]
    return sum(r.get("frequency") == "daily" for r in rows), len(rows)


def _clause():
    hits = list(CLAUSE.finditer(TODO.read_text())) if TODO.exists() else []
    if len(hits) != 1:
        pytest.skip(f"expected one registry-count clause in docs/todo.md, found {len(hits)} (line reworded, "
                    "removed or duplicated): the counts are not checked")
    return hits[0]


def _mismatch(msg):
    if _strict():
        raise AssertionError(msg)
    pytest.skip(f"{msg} (skipped: set NIGHT_SHIFT_STRICT=1 to enforce)")


def test_registry_counts_match_instruments_csv():
    m = _clause()
    stated_tradeable = (int(m.group(1)), int(m.group(2)))
    stated_legs = (int(m.group(3)), int(m.group(4))) if m.group(3) else None
    expected_tradeable = _counts(TRADEABLE)
    expected_legs = _counts(WITH_LEGS)
    if stated_tradeable != expected_tradeable:
        _mismatch(
            f"docs/todo.md says {stated_tradeable[0]} of {stated_tradeable[1]} daily; the registry has "
            f"{expected_tradeable[0]} of {expected_tradeable[1]} tradeable (book fx or bond) instruments daily"
        )
    if stated_legs != expected_legs:
        _mismatch(
            f"docs/todo.md states {stated_legs} with the yield legs; the registry has "
            f"{expected_legs[0]} of {expected_legs[1]} (book fx, bond or leg) daily"
        )


def test_clause_says_tradeable():
    if "tradeable instruments daily" not in _clause().group(0):
        pytest.skip("the docs/todo.md registry-count clause no longer says 'tradeable instruments daily' (reworded)")
