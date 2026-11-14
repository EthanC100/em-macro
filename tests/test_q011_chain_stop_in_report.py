"""Q011: the morning report lists an abnormal chain stop under "Failed or empty runs".

``nightshift.state stop`` sets ``chain_stopped`` and adds nothing to the run log, so a night whose chain was stopped
(10 Nov 22:41 SGT: dev conflicted with main) was reported as "none (outputs verified)". A stop with one of guard.next's
normal end-of-night reasons (after 05:00, run cap reached, nothing left to do; night-start's "nothing to do") is how
most nights end and is not listed.

Fixture state, config and queue only: build() runs with nightshift.state.load, the config loaders, ROOT and every
section that reads git or live data stubbed, so the live docs/agent-state.json, config/night.yaml, data/janus and the
remote are never read.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from nightshift import config as C
from nightshift import guard as G
from nightshift import morning as M
from nightshift import state as S

DAY = date(2026, 11, 11)                  # the morning of 11 Nov reports the night of 10 Nov
NIGHT = "2026-11-10"
CONFLICT = ("dev conflicts with main: docs/queue.md, results/opposition/calibration.csv, docs/agent-system.md, "
            ".claude/routines/night-start.md, nightshift/merge.py")
CFG = {"run_cap": 12, "safe_mode": {"enabled": False, "run_cap": 4},
       "window": {"start": "22:30", "chain_stop": "05:00", "promote": "05:30", "promote_latest": "07:30"},
       "explorer": {"max_hypotheses_per_night": 3}}
QUEUE = ("<!-- queue:start -->\n| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |\n"
         "|---|---|---|---|---|---|---|---|\n<!-- queue:end -->\n")


def _state(reason: str | None, at: str | None, log=()) -> dict:
    st = S.empty()
    st.update(night=NIGHT, log=list(log))
    if reason is not None or at is not None:
        st["chain_stopped"] = {"reason": reason, "at": at}
    return st


def _failed_section(monkeypatch, tmp_path, st: dict) -> list[str]:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/queue.md").write_text(QUEUE, encoding="utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(S, "load", lambda *a, **k: st)
    monkeypatch.setattr(C, "load", lambda *a, **k: CFG)
    monkeypatch.setattr(C, "load_main", lambda *a, **k: CFG, raising=False)
    monkeypatch.setattr(M, "promoted", lambda *a, **k: "no - fixture")
    monkeypatch.setattr(M, "merged_into_dev", lambda *a, **k: [])
    monkeypatch.setattr(M, "janus_section", lambda *a, **k: ["fixture"])
    monkeypatch.setattr(M, "v1_rules_state", lambda *a, **k: None)
    monkeypatch.setattr(M, "v1_rules_section", lambda *a, **k: ["fixture"])
    monkeypatch.setattr(M, "lab_section", lambda *a, **k: ["fixture"])
    monkeypatch.setattr(M, "on_branch", lambda *a, **k: pytest.fail("no merged run in the fixture: git not needed"))
    lines = M.build(DAY, "origin/dev", []).splitlines()
    i = lines.index("**Failed or empty runs:**")
    out = []
    for l in lines[i + 1:]:
        if not l.startswith("- "):
            break
        out.append(l[2:])
    return out


def test_q011_conflict_stop_is_listed(monkeypatch, tmp_path):
    """The 10 Nov 22:41 SGT conflict stop (0 runs logged) appears under Failed or empty runs, shortened by _short."""
    got = _failed_section(monkeypatch, tmp_path, _state(CONFLICT, "2026-11-10T22:41:59+08:00"))
    want = f"chain stopped 22:41: {M._short(CONFLICT)}"
    assert want in got, got
    assert "none (outputs verified)" not in got, got
    assert M._short(CONFLICT) != CONFLICT          # the fixture reason is long enough to be shortened


def test_q011_stop_after_midnight_counts_for_previous_night(monkeypatch, tmp_path):
    got = _failed_section(monkeypatch, tmp_path, _state("busy: ledger-daily running", "2026-11-11T01:30:00+08:00"))
    assert got == ["chain stopped 01:30: busy: ledger-daily running"], got


def test_q011_stop_time_shown_in_singapore_time(monkeypatch, tmp_path):
    got = _failed_section(monkeypatch, tmp_path, _state(CONFLICT, "2026-11-10T14:41:59+00:00"))
    assert got[0].startswith("chain stopped 22:41: "), got


@pytest.mark.parametrize("reason", [
    "after 05:00 SGT (or outside the window)",
    "run cap reached (4 of 4)",
    "run cap reached (4 of 4); PR #40 (Q019) awaits review and merge",
    "nothing left to do: approved queue empty and explorer done for the night",
    "nothing to do",
    "no approved items left",
    "outside the night window (22:30-05:00 SGT)",
])
def test_q011_normal_end_of_night_stop_not_listed(monkeypatch, tmp_path, reason):
    got = _failed_section(monkeypatch, tmp_path, _state(reason, "2026-11-11T00:42:49+08:00"))
    assert got == ["none (outputs verified)"], got


@pytest.mark.parametrize("at", ["2026-11-09T23:10:00+08:00", "2026-11-11T22:41:59+08:00", "2026-11-11T12:00:00+08:00"])
def test_q011_stop_from_another_night_not_listed(monkeypatch, tmp_path, at):
    got = _failed_section(monkeypatch, tmp_path, _state(CONFLICT, at))
    assert got == ["none (outputs verified)"], got


def test_q011_unreadable_stop_time_is_listed_not_a_crash(monkeypatch, tmp_path):
    got = _failed_section(monkeypatch, tmp_path, _state("dev conflicts with main: x", "10 Nov late"))
    assert got == ["chain stopped (time unreadable: '10 Nov late'): dev conflicts with main: x"], got


def test_q011_no_stop_unchanged(monkeypatch, tmp_path):
    assert _failed_section(monkeypatch, tmp_path, _state(None, None)) == ["none (outputs verified)"]


def test_q011_stop_listed_with_failed_runs(monkeypatch, tmp_path):
    run = {"routine": "night-worker", "started_at": "2026-11-10T23:00:00+08:00",
           "finished_at": "2026-11-10T23:20:00+08:00", "outcome": "failed", "note": "tests failed"}
    got = _failed_section(monkeypatch, tmp_path, _state(CONFLICT, "2026-11-10T23:41:00+08:00", [run]))
    assert got == [f"chain stopped 23:41: {M._short(CONFLICT)}", "night-worker 23:20: failed - tests failed"], got


def test_q011_guard_next_stop_reasons_are_normal():
    """The reasons guard.next actually gives at the end of a night are the ones the report treats as normal."""
    st = S.empty()
    late = datetime.fromisoformat("2026-11-11T05:30:00+08:00")
    night = datetime.fromisoformat("2026-11-10T23:30:00+08:00")
    whys = [G.next_routine(late, CFG, dict(st), [], 0, explorer_gate=[])["why"],
            G.next_routine(night, CFG, {**st, "night": NIGHT, "runs_used": 12}, [], 0, explorer_gate=[])["why"],
            G.next_routine(night, CFG, {**st, "night": NIGHT}, [], 3, explorer_gate=[])["why"],
            G.next_for_worker(night, CFG, {**st, "night": NIGHT}, [], [])["why"],
            G.next_for_worker(late, CFG, dict(st), [{"status": "approved"}], [])["why"]]
    for why in whys:
        assert M.normal_stop(why), why
    assert not M.normal_stop(CONFLICT)
    assert not M.normal_stop("")
