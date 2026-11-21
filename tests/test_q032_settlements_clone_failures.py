"""Q032: the morning report shows the quick checks since the last report that could not read the settlements clone.

On 19 Nov 2026 the Janus quick checks at 07:17, 08:17 and 13:23Z could not read the futures settlements clone
("futures settlements clone failed (no stop changes possible)", "futures settlements not read (clone unavailable)"),
so no stop could be checked in those hours, yet the morning report showed only the latest check (which read the clone)
and the failures earlier in the day were lost. The "Janus checks" line now counts and times the quick checks since
the last report whose result mentions a settlements clone failure; a check whose settlements wording matches neither
known failure nor known success phrasing is "settlements status unknown", never ok.

Fixture records only (made up in the 19 Nov style): never the live data/janus records, origin/main, the remote or
the settlements clone. ROOT is a temporary directory wherever previous reports are looked up.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from nightshift import config as C
from nightshift import morning as M

DAY = date(2026, 11, 20)                                         # the report written on the morning of 20 Nov
NOW = datetime(2026, 11, 19, 22, 50, tzinfo=timezone.utc)        # 06:50 Singapore, 20 Nov
SINCE = datetime(2026, 11, 19, 5, 0, tzinfo=C.SGT)               # the 19 Nov report's morning (21:00Z, 18 Nov)

BASE = "no change; no flags, all 20 positions are C08 so changes are noted only; no news search; "
FAIL_A = "futures settlements clone failed (no stop changes possible)"
FAIL_B = "futures settlements not read (clone unavailable)"


def check(at: str, tail: str) -> dict:
    return {"type": "check", "session": "quick_check", "recorded_at": f"2026-11-{at}+00:00", "result": BASE + tail}


def nov19() -> list[dict]:
    """A 19 Nov-style day: clone failures at 07:17, 08:17 and 13:23Z, later checks read the clone."""
    return [
        {"type": "run", "session": "daily_review", "date": "2026-11-19", "recorded_at": "2026-11-19T00:30:00+00:00",
         "sources_read": [{"title": "a", "url": "https://example.org/a"}]},
        check("18T20:16:00", FAIL_A),                         # before the last report: already reported, not counted
        check("19T05:17:51", "futures settlements clone ok"),
        check("19T06:18:01", "futures settlements clone ok"),
        check("19T07:17:03", FAIL_A),
        check("19T08:17:16", FAIL_A),
        check("19T09:17:56", "futures settlements clone worked"),
        check("19T10:18:01", "futures settlements clone worked"),
        check("19T11:18:18", "futures settlements read via clone"),
        check("19T12:19:14", "futures settlements read via clone"),
        check("19T13:23:36", FAIL_B),
        check("19T14:20:07", "settlements read via clone"),
        check("19T22:17:00", "C08 book, settlements clone ok, no web news check"),
    ]


def jline(records: list[dict], since=SINCE) -> str:
    line, _ = M.janus_checks_line(records, "", DAY, NOW, since=since)
    return line


def test_q032_19_nov_failures_are_counted_and_timed():
    line = jline(nov19())
    assert "settlements clone FAILED in 3 of 11 quick checks since 19 Nov 05:00 SGT" in line, line
    assert "19 Nov 07:17Z, 08:17Z, 13:23Z" in line, line
    assert "20:16" not in line, line                          # the 18 Nov failure was in the previous report
    assert "settlements status unknown" not in line, line
    # the latest check read the clone: the line still starts as before (last quick check, daily review)
    assert line.startswith("Janus checks: last quick check 19 Nov 22:17Z (1 h ago); last daily review 2026-11-19 (ok)")


def test_q032_failures_do_not_escalate_janus_behaviour():
    """Making the gap visible only: a clone failure does not mark the Janus checks late or failing (C05 is Ethan's)."""
    lines, needs = M.status_section(DAY, NOW, (nov19(), ""), lambda url: None, since=SINCE)
    jl = [l for l in lines if l.startswith("Janus checks:")]
    assert len(jl) == 1 and "settlements clone FAILED in 3 of 11" in jl[0], lines
    assert not any(n.startswith("Janus checks late or failing") for n in needs), needs


def test_q032_all_read_says_so():
    recs = [r for r in nov19() if FAIL_A not in r.get("result", "") and FAIL_B not in r.get("result", "")]
    line = jline(recs)
    assert "settlements clone read in all 8 quick checks since 19 Nov 05:00 SGT" in line, line
    assert "FAILED" not in line and "unknown" not in line, line


def test_q032_unrecognised_wording_is_unknown_not_ok():
    recs = nov19() + [check("19T22:47:00", "futures settlements clone flaky"),
                      check("19T22:48:00", "no futures stop within 1 ATR")]      # no settlements wording at all
    line = jline(recs)
    assert "settlements status unknown in 2 quick checks: 19 Nov 22:47Z, 22:48Z" in line, line
    assert "FAILED in 3 of 13" in line, line
    only = jline([check("19T22:47:00", "futures settlements clone flaky")])
    assert "settlements status unknown in 1 of 1 quick check since 19 Nov 05:00 SGT (last report): 19 Nov 22:47Z" \
        in only, only
    assert "read in all" not in only and "FAILED" not in only, only


@pytest.mark.parametrize("result", [
    "futures clone unavailable (none held)",                                   # seq 215
    "futures clone failed at start (none held)",                               # seq 219
    "futures settlements clone failed (rates book, not needed)",               # seq 237
    "settlements clone failed (no futures held)",                              # seq 272
    "em-macro-data clone failed (no futures settlements); no news search",     # seq 519
    "futures settlements clone failed",                                        # seq 595
    FAIL_A, FAIL_B,                                                            # seq 601, 602, 607
])
def test_q032_known_failure_phrasing(result):
    assert M.settlements_status(BASE + result) == "failed"


@pytest.mark.parametrize("result", [
    "futures settlements clone ok", "settlements clone ok after add_repo", "C08 book, settlements clone ok, no web",
    "futures settlements clone worked", "futures settlements read via clone", "settlements read via clone",
    "settlements clone made after add_repo", "settlements clone restored via add_repo", "futures clone ok (none held)",
])
def test_q032_known_success_phrasing(result):
    assert M.settlements_status(BASE + result) == "ok"


@pytest.mark.parametrize("result", [
    "futures settlements clone flaky", "settlements clone needed add_repo", "futures settlements n/a",
    "no futures held", "",
])
def test_q032_anything_else_is_unknown(result):
    assert M.settlements_status(BASE + result) == "unknown"


def test_q032_since_is_the_last_report(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "ROOT", tmp_path)
    assert M.last_report_at(DAY) == datetime(2026, 11, 19, 5, 0, tzinfo=C.SGT)    # no report: the day before
    d = tmp_path / "results/night/morning"
    d.mkdir(parents=True)
    for name in ("2026-11-15.md", "2026-11-17.md", "notes.md", "2026-11-20.md", "2026-11-21.md"):
        (d / name).write_text("x\n", encoding="utf-8")
    assert M.last_report_at(DAY) == datetime(2026, 11, 17, 5, 0, tzinfo=C.SGT)    # 18 and 19 Nov missing
    assert M.last_report_at(date(2026, 11, 17)) == datetime(2026, 11, 15, 5, 0, tzinfo=C.SGT)


def test_q032_morning_report_shows_the_failures(tmp_path, monkeypatch):
    """The written report (build) carries the count and times, with 'since' taken from the previous report."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/queue.md").write_text(
        "<!-- queue:start -->\n| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |\n"
        "|---|---|---|---|---|---|---|---|\n<!-- queue:end -->\n", encoding="utf-8")
    (tmp_path / "results/night/morning").mkdir(parents=True)
    (tmp_path / "results/night/morning/2026-11-19.md").write_text("# fixture\n", encoding="utf-8")
    cfg = {"run_cap": 12, "safe_mode": {"enabled": True, "run_cap": 4}, "window": {}}
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M.S, "load", lambda *a, **k: {"log": []})
    monkeypatch.setattr(M.C, "load", lambda *a, **k: cfg)
    monkeypatch.setattr(M.C, "load_main", lambda *a, **k: cfg)
    monkeypatch.setattr(M.C, "now_utc", lambda: NOW)
    monkeypatch.setattr(M.G, "_fetch", lambda url: None)
    for name, val in (("promoted", "no - fixture"), ("merged_into_dev", []), ("v1_rules_state", None),
                      ("v1_rules_section", ["fixture"]), ("lab_section", ["fixture"]), ("janus_section", ["fixture"])):
        monkeypatch.setattr(M, name, lambda *a, _v=val, **k: _v)
    monkeypatch.setattr(M, "janus_records", lambda: (nov19(), ""))
    text = M.build(DAY, "origin/dev", [])
    jl = [l for l in text.splitlines() if l.startswith("- Janus checks:")]
    assert len(jl) == 1, text
    assert "settlements clone FAILED in 3 of 11 quick checks since 19 Nov 05:00 SGT (last report): " \
           "19 Nov 07:17Z, 08:17Z, 13:23Z" in jl[0], jl[0]
