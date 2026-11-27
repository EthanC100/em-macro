"""Q035: a Janus quick check's freshness claim names the oldest held-instrument mark, not the newest.

On 26 Nov 2026 the quick checks said "marks of 25 Nov" although the held GB10Y (Riksbank, about two business days
behind) had no 25 Nov mark: its newest mark was 24 Nov. The check result is free text, so the fix gives the session
a computed claim to quote: ``python -m ledger.janus context`` emits ``mark_freshness``, built on the existing
``_stale_weekdays`` / ``_is_stale``, whose ``summary`` names the oldest held mark and the instruments on it, and
docs/janus/quick_check.md tells Janus to quote it. There is no new CLI validation of the ``--result`` text.

The CLI is tested on fixture records and fixture marks only (no file under data/ is read for them). The doc check
reads docs/janus/quick_check.md, hand-edited on main: if the instruction is missing it skips with a message unless
NIGHT_SHIFT_STRICT=1 (pr-review, promote), where it fails.
"""
import os
from datetime import date
from pathlib import Path

import pytest

from ledger import janus as J
from test_janus_c08 import c08, day_marks, marks, run

ROOT = Path(__file__).resolve().parents[1]
QUICK_CHECK = ROOT / "docs/janus/quick_check.md"
TODAY = date(2026, 11, 26)                     # Thursday


@pytest.fixture(autouse=True)
def no_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "no-store"))


def book(tmp_path):
    """A fixture C08 book (10 positions, GB10Y among them), written to a temporary records file."""
    res = run(tmp_path, c08())
    assert res["ok"], res["errors"]
    return J.load(tmp_path / "r.jsonl")


def held_marks(gb10y="2026-11-24", others="2026-11-25"):
    """Marks with GB10Y's newest on ``gb10y`` and every other held instrument's newest on ``others``."""
    return (marks("2026-11-10") + day_marks("2026-11-12")
            + [m for m in day_marks(others) if m["instrument"] != "GB10Y"]
            + [m for m in day_marks(gb10y) if m["instrument"] == "GB10Y"])


def context_for(tmp_path, monkeypatch, mk):
    recs = book(tmp_path)
    monkeypatch.setattr(J, "load", lambda path=None: recs)
    monkeypatch.setattr(J, "RECORDS", tmp_path / "r.jsonl")       # futures P&L file: none in tmp_path
    return J.context(marks_rows=mk, today=TODAY)


def test_context_names_oldest_held_mark(tmp_path, monkeypatch):
    ctx = context_for(tmp_path, monkeypatch, held_marks())
    assert "mark_freshness" in ctx, "context emits no mark-freshness summary"
    mf = ctx["mark_freshness"]
    assert mf["oldest_mark_date"] == "2026-11-24"
    assert mf["oldest_instruments"] == ["GB10Y"]
    assert mf["newest_mark_date"] == "2026-11-25"
    assert "marks from 24 Nov (GB10Y)" in mf["summary"]
    assert "marks of 25 Nov" not in mf["summary"]
    # one weekday (25 Nov) without a GB10Y mark: not stale under DATA_STALE_WEEKDAYS = 2
    assert mf["stale"] == []


def test_all_held_marks_same_day(tmp_path, monkeypatch):
    mf = context_for(tmp_path, monkeypatch, held_marks(gb10y="2026-11-25"))["mark_freshness"]
    assert mf["oldest_mark_date"] == mf["newest_mark_date"] == "2026-11-25"
    assert mf["summary"].startswith("marks of 25 Nov (all 10 held)")


def test_stale_held_mark_named(tmp_path, monkeypatch):
    mf = context_for(tmp_path, monkeypatch, held_marks(gb10y="2026-11-20"))["mark_freshness"]
    n = J._stale_weekdays(date(2026, 11, 20), TODAY)
    assert J._is_stale(date(2026, 11, 20), TODAY) and n == 3
    assert mf["stale"] == [{"instrument": "GB10Y", "mark_date": "2026-11-20", "stale_weekdays": n}]
    assert "marks from 20 Nov (GB10Y)" in mf["summary"]
    assert "GB10Y stale" in mf["summary"]


def test_freshness_pure_cases():
    rows = [{"instrument": "US10Y", "mark_date": "2026-11-25"}, {"instrument": "CL", "mark_date": None}]
    mf = J.mark_freshness(rows, TODAY)
    assert mf["no_mark"] == ["CL"]
    assert "no mark yet: CL" in mf["summary"]
    assert J.mark_freshness([], TODAY)["summary"] == "no open positions"


def test_quick_check_doc_quotes_freshness():
    if not QUICK_CHECK.is_file():
        pytest.skip("docs/janus/quick_check.md is absent")
    text = QUICK_CHECK.read_text(encoding="utf-8")
    if "mark_freshness" not in text:
        msg = "docs/janus/quick_check.md does not tell Janus to quote mark_freshness.summary"
        if os.environ.get("NIGHT_SHIFT_STRICT") == "1":
            pytest.fail(msg)
        pytest.skip(msg)
