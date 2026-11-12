"""Q007: tests/test_q003_todo_counts.py must never stop the monthly rebalance commit.

systematic-monthly runs ``python -m pytest -q tests`` before it commits the rebalance, so a to-do sentence in
docs/todo.md (hand-edited by Ethan) compared with data/ledger/instruments.csv (a writer's file) must not fail there:
- without NIGHT_SHIFT_STRICT=1, a count mismatch, a reworded line or a removed line skips with a message;
- with NIGHT_SHIFT_STRICT=1 (pr-review, promote), a numeric mismatch still fails, but a missing or reworded line
  skips, so completing the to-do item on main never blocks promotion.

The Q003 tests are driven against temporary copies of the two files (the module's TODO and REGISTRY paths are
monkeypatched); the live files are never edited.
"""
import csv

import pytest

import test_q003_todo_counts as q003

FIELDS = ["id", "book", "frequency"]
# 3 tradeable (fx/bond), 2 daily; 1 leg (daily); 1 janus row (not counted)
ROWS = [("A", "fx", "daily"), ("B", "bond", "daily"), ("C", "bond", "monthly"), ("L", "leg", "daily"),
        ("J", "janus", "daily")]
GOOD = ("- [ ] 9 of 23 instruments lack daily prices (the Ledger registry now marks 2 of 3 tradeable instruments "
        "daily (3 of 4 with the yield legs), but the algorithm's inputs are unchanged)\n")


def _setup(tmp_path, monkeypatch, todo_text, rows=ROWS, strict=False):
    reg = tmp_path / "instruments.csv"
    with reg.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        w.writerows(rows)
    todo = tmp_path / "todo.md"
    todo.write_text("# To do\n\n## Technical\n\n" + todo_text)
    monkeypatch.setattr(q003, "TODO", todo)
    monkeypatch.setattr(q003, "REGISTRY", reg)
    if strict:
        monkeypatch.setenv("NIGHT_SHIFT_STRICT", "1")
    else:
        monkeypatch.delenv("NIGHT_SHIFT_STRICT", raising=False)


def _outcome(fn):
    try:
        fn()
    except pytest.skip.Exception as e:
        return "skipped", str(e)
    except AssertionError as e:
        return "failed", str(e)
    return "passed", ""


Q003_TESTS = (q003.test_registry_counts_match_instruments_csv, q003.test_clause_says_tradeable)
CHANGED_FREQ = [r if r[0] != "C" else ("C", "bond", "daily") for r in ROWS]     # registry now 3 of 3 daily
REWORDED = GOOD.replace("the Ledger registry now marks", "the registry has")
REMOVED = "- [ ] something else entirely\n"
TICKED = GOOD.replace("- [ ]", "- [x]")
OLD_WORDING = GOOD.replace("2 of 3 tradeable instruments", "2 of 3 instruments")


@pytest.mark.parametrize("strict", [False, True])
def test_matching_counts_pass_in_both_modes(tmp_path, monkeypatch, strict):
    for todo in (GOOD, TICKED):
        _setup(tmp_path, monkeypatch, todo, strict=strict)
        for t in Q003_TESTS:
            assert _outcome(t) == ("passed", ""), (t.__name__, todo)


def test_frequency_change_skips_with_message_when_not_strict(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, GOOD, rows=CHANGED_FREQ)
    status, msg = _outcome(q003.test_registry_counts_match_instruments_csv)
    assert status == "skipped", (status, msg)
    assert "2 of 3" in msg and "3 of 3" in msg and "NIGHT_SHIFT_STRICT" in msg


@pytest.mark.parametrize("todo", [REWORDED, REMOVED, GOOD + GOOD], ids=["reworded", "removed", "duplicated"])
@pytest.mark.parametrize("strict", [False, True])
def test_missing_or_reworded_line_skips_in_both_modes(tmp_path, monkeypatch, todo, strict):
    _setup(tmp_path, monkeypatch, todo, strict=strict)
    for t in Q003_TESTS:
        status, msg = _outcome(t)
        assert status == "skipped", (t.__name__, status, msg)
        assert "docs/todo.md" in msg


@pytest.mark.parametrize("strict", [False, True])
def test_old_wording_without_tradeable_skips(tmp_path, monkeypatch, strict):
    _setup(tmp_path, monkeypatch, OLD_WORDING, strict=strict)
    status, msg = _outcome(q003.test_clause_says_tradeable)
    assert status == "skipped", (status, msg)


def test_numeric_mismatch_still_fails_when_strict(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, GOOD, rows=CHANGED_FREQ, strict=True)
    status, msg = _outcome(q003.test_registry_counts_match_instruments_csv)
    assert status == "failed", (status, msg)
    assert "2 of 3" in msg and "3 of 3" in msg


def test_legs_mismatch_skips_or_fails_by_mode(tmp_path, monkeypatch):
    rows = [r if r[0] != "L" else ("L", "leg", "monthly") for r in ROWS]    # legs 2 of 4, tradeable unchanged
    _setup(tmp_path, monkeypatch, GOOD, rows=rows)
    assert _outcome(q003.test_registry_counts_match_instruments_csv)[0] == "skipped"
    _setup(tmp_path, monkeypatch, GOOD, rows=rows, strict=True)
    assert _outcome(q003.test_registry_counts_match_instruments_csv)[0] == "failed"


def test_missing_registry_skips_in_both_modes(tmp_path, monkeypatch):
    for strict in (False, True):
        _setup(tmp_path, monkeypatch, GOOD, strict=strict)
        monkeypatch.setattr(q003, "REGISTRY", tmp_path / "absent.csv")
        assert _outcome(q003.test_registry_counts_match_instruments_csv)[0] == "skipped"
