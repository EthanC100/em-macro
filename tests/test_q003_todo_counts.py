"""Q003: the registry-count clause of the Technical to-do line in docs/todo.md matches the Ledger instrument
registry (data/ledger/instruments.csv).

The counts are computed from the registry at run time, so the test follows the registry instead of freezing
numbers. Tradeable instruments are the rows with book ``fx`` or ``bond``; "with the yield legs" adds the rows with
book ``leg``. Janus rows and the cash benchmark are not counted. The line's "9 of 23 instruments lack daily
prices" is about the algorithm's inputs, not the registry, and is not checked here.
"""
import csv
import re
from pathlib import Path

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


def _counts(books):
    with REGISTRY.open(newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["book"] in books]
    return sum(r["frequency"] == "daily" for r in rows), len(rows)


def _clause():
    hits = [m for m in CLAUSE.finditer(TODO.read_text())]
    assert len(hits) == 1, f"expected one registry-count clause in docs/todo.md, found {len(hits)}"
    return hits[0]


def test_registry_counts_match_instruments_csv():
    m = _clause()
    stated_tradeable = (int(m.group(1)), int(m.group(2)))
    stated_legs = (int(m.group(3)), int(m.group(4))) if m.group(3) else None
    expected_tradeable = _counts(TRADEABLE)
    expected_legs = _counts(WITH_LEGS)
    assert stated_tradeable == expected_tradeable, (
        f"docs/todo.md says {stated_tradeable[0]} of {stated_tradeable[1]} daily; the registry has "
        f"{expected_tradeable[0]} of {expected_tradeable[1]} tradeable (book fx or bond) instruments daily"
    )
    assert stated_legs == expected_legs, (
        f"docs/todo.md states {stated_legs} with the yield legs; the registry has "
        f"{expected_legs[0]} of {expected_legs[1]} (book fx, bond or leg) daily"
    )


def test_clause_says_tradeable():
    assert "tradeable instruments daily" in _clause().group(0)
