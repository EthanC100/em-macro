"""Q020: night-worker runs as one daily session that loops over items (23:35 SGT), so the per-run checks must bind
per item in code, not in the routine's prose:

1. ``state acquire night-worker`` refuses (exit 3) unless the guard check for night-worker passes, with main's
   config (C.load_main): window, run cap, chain stopped, busy writers, and fail safe when the Actions API cannot be
   read or main's config cannot be fetched. A loop that acquires per item therefore re-checks the guard per item.
2. ``guard next --for night-worker`` answers night-worker while approved items remain and those checks pass, else
   stop; never night-explorer, whatever ``max_hypotheses_per_night`` says. Plain ``guard next`` and ``guard.check``
   are unchanged (promote uses check).
3. A night-worker release names one item (several are refused), and each counted release adds one run, so a loop of
   acquire/release per item stops at the cap.
4. No heartbeat and no staleness exemption: a 2-hour-old worker lock is still taken over.

Fixture config and temporary state files only; C.load_main, C.now_utc and busy_runs are monkeypatched (no network).
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from nightshift import config as C
from nightshift import guard as G
from nightshift import queue as Q
from nightshift import state as S

FIXTURE = Path(__file__).resolve().parent / "fixtures/night/night.yaml"
NOW = datetime.fromisoformat("2026-11-09T23:40:00+08:00")      # inside the chain window, no busy window


def _cfg(safe: bool = False, hyp: int = 3) -> dict:
    c = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    c["safe_mode"]["enabled"] = safe
    c["explorer"]["max_hypotheses_per_night"] = hyp
    return c


def _unreadable(*a, **k):
    raise C.MainConfigError("git fetch origin main failed: offline")


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Patches main's config, the clock and the Actions API; returns a setter for each and the state path."""
    box = {"cfg": _cfg(), "now": NOW, "busy": []}
    monkeypatch.setattr(C, "load_main", lambda *a, **k: box["cfg"]() if callable(box["cfg"]) else box["cfg"])
    monkeypatch.setattr(C, "now_utc", lambda: box["now"])
    monkeypatch.setattr(G, "busy_runs", lambda cfg, **k: box["busy"])
    box["path"] = tmp_path / "state.json"
    return box


def _acquire(env, routine="night-worker") -> int:
    return S.main(["acquire", routine, "--state", str(env["path"]), "--session", "s"])


def _release(env, items="Q001", outcome="ok", routine="night-worker") -> int:
    return S.main(["release", routine, "--state", str(env["path"]), "--outcome", outcome, "--items", items])


# ------------------------------------------------------------------------------------- 1. acquire runs the guard
def test_acquire_night_worker_passes_when_the_guard_passes(env, capsys):
    assert _acquire(env) == 0
    st = json.loads(env["path"].read_text())
    assert st["lock"]["routine"] == "night-worker"


@pytest.mark.parametrize("case, expect", [
    ("outside_window", "outside the night window"),
    ("cap", "run cap reached (4 of 4)"),
    ("chain_stopped", "chain stopped: done for tonight"),
    ("busy", "busy: ledger-daily running"),
    ("api_unreadable", "could not read the GitHub Actions API"),
])
def test_acquire_night_worker_refuses_unless_the_guard_passes(env, capsys, case, expect):
    if case == "outside_window":
        env["now"] = datetime.fromisoformat("2026-11-10T05:10:00+08:00")
    elif case == "cap":
        env["cfg"] = _cfg(safe=True)
        st = S.empty() | {"night": "2026-11-09", "runs_used": 4}
        S.save(st, env["path"])
    elif case == "chain_stopped":
        st = S.empty() | {"night": "2026-11-09", "chain_stopped": {"reason": "done for tonight", "at": "x"}}
        S.save(st, env["path"])
    elif case == "busy":
        env["busy"] = ["ledger-daily"]
    elif case == "api_unreadable":
        env["busy"] = None
    before = env["path"].read_text() if env["path"].exists() else None
    assert _acquire(env) == 3
    out = capsys.readouterr().out
    assert "refused" in out and expect in out, out
    after = env["path"].read_text() if env["path"].exists() else None
    assert after == before                                         # nothing written, no lock taken


def test_acquire_night_worker_fails_safe_when_mains_config_is_unreadable(env, capsys):
    env["cfg"] = _unreadable
    assert _acquire(env) == 3
    assert "refused" in capsys.readouterr().out and not env["path"].exists()


def test_acquire_promote_is_not_gated_by_the_night_window(env, capsys):
    """promote runs its own guard check before acquire (05:30-07:00, outside the chain window): unchanged."""
    env["now"] = datetime.fromisoformat("2026-11-10T05:31:00+08:00")
    env["busy"] = None
    assert _acquire(env, "promote") == 0


# ------------------------------------------------------------------------------------- 2. guard next --for night-worker
def _queue(tmp_path, monkeypatch, n_approved):
    rows = "\n".join(f"| Q00{i} | bug | {'approved' if i <= n_approved else 'done'} | t{i} | test_x |  | "
                     f"no block, p=50% | none |" for i in range(1, 4))
    p = tmp_path / "queue.md"
    p.write_text("# Queue\n<!-- queue:start -->\n| id | type | status | title | acceptance test | branch/PR | "
                 "opposition | ledger diff |\n|---|---|---|---|---|---|---|---|\n" + rows + "\n<!-- queue:end -->\n",
                 encoding="utf-8")
    monkeypatch.setattr(Q, "QUEUE", p)


def _next_for(env, monkeypatch, st, capsys, now=NOW):
    monkeypatch.setattr(S, "load", lambda *a, **k: json.loads(json.dumps(st)))
    code = G.main(["next", "--for", "night-worker", "--now", now.isoformat()])
    return code, json.loads(capsys.readouterr().out)


def test_next_for_worker_never_answers_explorer(env, monkeypatch, tmp_path, capsys):
    _queue(tmp_path, monkeypatch, 2)
    st = S.empty() | {"night": "2026-11-09", "runs_used": 1, "last_kind": "worker"}
    # plain next (unchanged) alternates to the explorer here ...
    assert G.next_routine(NOW, _cfg(hyp=3), json.loads(json.dumps(st)), Q.parse(Q.QUEUE.read_text()), 0,
                          explorer_gate=[])["next"] == "night-explorer"      # Q019 gate passed open explicitly
    # ... the worker's own question never does, even with explorer hypotheses left
    code, out = _next_for(env, monkeypatch, st, capsys)
    assert code == 0 and out["next"] == "night-worker", out


@pytest.mark.parametrize("case", ["empty_queue", "cap", "busy", "api_unreadable", "after_0500", "chain_stopped",
                                  "config_unreadable"])
def test_next_for_worker_says_stop_otherwise(env, monkeypatch, tmp_path, capsys, case):
    _queue(tmp_path, monkeypatch, 0 if case == "empty_queue" else 2)
    st = S.empty() | {"night": "2026-11-09", "runs_used": 1, "last_kind": "worker"}
    now = NOW
    if case == "cap":
        env["cfg"] = _cfg(safe=True)
        st["runs_used"] = 4
    elif case == "busy":
        env["busy"] = ["systematic-monthly"]
    elif case == "api_unreadable":
        env["busy"] = None
    elif case == "after_0500":
        now = datetime.fromisoformat("2026-11-10T05:01:00+08:00")
    elif case == "chain_stopped":
        st["chain_stopped"] = {"reason": "x", "at": "y"}
    elif case == "config_unreadable":
        env["cfg"] = _unreadable
    code, out = _next_for(env, monkeypatch, st, capsys, now)
    assert out["next"] == "stop" and code == 4, out


def test_next_for_rejects_other_routines(env, capsys):
    with pytest.raises(SystemExit):
        G.main(["next", "--for", "night-explorer"])


def test_guard_check_verdicts_unchanged_for_promote():
    cfg, st = _cfg(), S.empty()
    assert G.check("promote", datetime.fromisoformat("2026-11-10T05:31:00+08:00"), cfg, st, [])["go"]
    assert not G.check("promote", datetime.fromisoformat("2026-11-10T05:31:00+08:00"), cfg, st, None)["go"]
    assert not G.check("promote", datetime(2026, 11, 9, 23, 10, tzinfo=timezone.utc), cfg, S.empty(), [])["go"]


# ------------------------------------------------------------------------------------- 3. one item per counted release
def test_release_with_several_items_is_refused(env, capsys):
    assert _acquire(env) == 0
    before = env["path"].read_text()
    assert _release(env, items="Q001,Q002") == 2
    assert "refused" in capsys.readouterr().out
    assert env["path"].read_text() == before                       # not counted, lock kept
    with pytest.raises(ValueError):
        S.release(json.loads(before), "night-worker", NOW, "ok", ["Q001", "Q002"])


def test_release_of_worked_item_must_name_it(env, capsys):
    assert _acquire(env) == 0
    assert _release(env, items="", outcome="ok") == 2
    assert _release(env, items="", outcome="empty") == 0             # nothing approved: no item to name
    assert json.loads(env["path"].read_text())["runs_used"] == 1


def test_a_per_item_loop_stops_at_the_cap(env, capsys):
    env["cfg"] = _cfg(safe=True)                                    # cap 4
    done = 0
    for i in range(1, 8):
        env["now"] = NOW + timedelta(minutes=20 * i)
        if _acquire(env) != 0:
            break
        assert _release(env, items=f"Q00{i}") == 0
        done += 1
    st = json.loads(env["path"].read_text())
    assert done == 4 and st["runs_used"] == 4 and st["lock"] is None
    assert "run cap reached (4 of 4)" in capsys.readouterr().out
    assert [e["run"] for e in st["log"] if e["routine"] == "night-worker"] == [1, 2, 3, 4]


# ------------------------------------------------------------------------------------- 4. no staleness exemption
def test_a_loop_holding_the_lock_past_two_hours_is_still_taken_over(env, capsys):
    assert _acquire(env) == 0
    env["now"] = NOW + timedelta(minutes=30)
    assert _acquire(env) == 3                                      # held, not stale
    env["now"] = NOW + timedelta(hours=2, minutes=1)
    assert _acquire(env) == 0
    st = json.loads(env["path"].read_text())
    assert st["log"][-1]["outcome"] == "failed" and "stale" in st["log"][-1]["note"]
    assert not hasattr(S, "heartbeat") and not hasattr(S, "refresh")
