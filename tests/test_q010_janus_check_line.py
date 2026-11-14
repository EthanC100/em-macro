"""Q010: the morning report's Janus quick-check line never cuts a word, and marks a cut with "...".

Fixture records only: ledger.janus.load, nightshift.morning._git and (since Q014, which fetches origin main in
janus_records) nightshift.morning.janus_records are stubbed, so the live data/janus records, origin/main and the
remote are never read. The fixture is served as a freshly fetched main copy (no "[dev copy]" label).
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from ledger import janus as J
from nightshift import morning as M

TODAY = date(2026, 11, 10)
PREFIX = "Last quick check 2026-11-10T14:21Z: "

# 130 characters, ending in a meaningful clause (as seq 220 of 10 Nov 14:21Z).
RESULT_130 = ("no change; all marks within limits, no stop within 1 ATR, no review flag; "
              "no dated news firing trigger; budget ok; no futures held")


def _check(result: str) -> dict:
    return {"type": "check", "seq": 220, "recorded_at": "2026-11-10T14:21:07+00:00", "result": result}


def _line(monkeypatch, result: str) -> str:
    monkeypatch.setattr(J, "load", lambda *a, **k: [_check(result)])
    monkeypatch.setattr(M, "_git", lambda *a, **k: "")
    monkeypatch.setattr(M, "janus_records", lambda *a, **k: ([_check(result)], ""))
    lines = [l for l in M.janus_section(TODAY) if l.startswith("Last quick check")]
    assert len(lines) == 1, lines
    assert lines[0].startswith(PREFIX), lines[0]
    return lines[0][len(PREFIX):]


def _words_ok(shown: str, full: str) -> None:
    """Every word shown is a whole word of the full result, in order (no partial word)."""
    body = shown[:-3] if shown.endswith("...") else shown
    got, want = body.split(), full.split()
    assert got == want[:len(got)], f"partial word printed: {shown!r}"


def test_q010_fixture_is_130_chars():
    assert len(RESULT_130) == 130 and RESULT_130.endswith("no futures held")


def test_q010_130_char_result_shown_in_full(monkeypatch):
    shown = _line(monkeypatch, RESULT_130)
    assert shown.endswith("no futures held"), shown
    assert shown == RESULT_130
    _words_ok(shown, RESULT_130)


def test_q010_long_result_ends_in_whole_word_and_marker(monkeypatch):
    words = [f"clause{i:02d}" for i in range(80)]
    full = " ".join(words)                                   # far longer than any phone line
    shown = _line(monkeypatch, full)
    assert shown.endswith("..."), shown
    assert len(shown) < len(full)
    _words_ok(shown, full)
    assert re.search(r"clause\d\d\.\.\.$", shown), shown      # a whole word, then the marker


@pytest.mark.parametrize("n", range(121, 400, 7))
def test_q010_no_partial_word_any_length(monkeypatch, n):
    text = ("no futures held; " * 40)[:n].rstrip()
    shown = _line(monkeypatch, text)
    if shown == text:
        return
    assert shown.endswith("..."), shown
    body = shown[:-3]
    assert text.startswith(body), shown
    assert text[len(body)] in " ;,", f"cut inside a word: {shown!r}"   # cut falls at a word boundary


def test_q010_single_overlong_token_is_not_printed_partially(monkeypatch):
    token = "x" * 500
    shown = _line(monkeypatch, token)
    assert "x" * 10 not in shown or shown == token
    assert shown.endswith("...")
