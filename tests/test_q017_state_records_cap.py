"""Q017: the state log records the run cap and safe-mode flag applied to each counted run.

1. ``state.acquire`` of a counted routine (night-worker, night-explorer) refuses when runs_used >= the cap read from
   the config it is given, so the cap it records is one it enforced (not only the guard's separate read).
2. acquire then release gives a log entry with ``cap`` and ``safe_mode`` (4/true in safe mode, 12/false otherwise).
3. The explorer model is recorded only on night-explorer entries, as ``explorer_model_config`` (config intent, not
   the model that ran).
4. The CLI acquire reads through C.load_main (the guard's loader) and refuses when it raises, so no entry ever
   carries dev's cap.
5. Taking over a stale lock acquired before this change (no cap fields) writes the failed entry with cap null
   instead of crashing; existing state files still load.

Fixture configs and temporary state files only; C.load_main, C.load, C.now_utc and busy_runs are monkeypatched.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from nightshift import config as C
from nightshift import guard as G
from nightshift import state as S

FIXTURE = Path(__file__).resolve().parent / "fixtures/night/night.yaml"
NOW = datetime.fromisoformat("2026-11-09T23:40:00+08:00")      # inside the chain window, no busy window


def _cfg(safe: bool) -> dict:
    c = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    c["safe_mode"]["enabled"] = safe
    return c


@pytest.fixture
def env(monkeypatch, tmp_path):
    box = {"cfg": _cfg(True), "now": NOW}
    monkeypatch.setattr(C, "load_main", lambda *a, **k: box["cfg"]() if callable(box["cfg"]) else box["cfg"])
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg(False))     # dev's copy: cap 12; must never be used
    monkeypatch.setattr(C, "now_utc", lambda: box["now"])
    monkeypatch.setattr(G, "busy_runs", lambda cfg, **k: [])
    monkeypatch.setattr(G, "gate_for", lambda routine: [])          # Q019's explorer gate passed open explicitly
    box["path"] = tmp_path / "state.json"
    return box


# ------------------------------------------------------------------------------- 1. acquire enforces its own cap
@pytest.mark.parametrize("routine", ["night-worker", "night-explorer"])
@pytest.mark.parametrize("safe, cap", [(True, 4), (False, 12)])
def test_acquire_refuses_at_the_cap_of_its_own_config(routine, safe, cap):
    st = S.empty() | {"night": "2026-11-09", "runs_used": cap}
    ok, msg = S.acquire(st, routine, NOW, _cfg(safe))
    assert not ok and f"run cap reached ({cap} of {cap})" in msg, msg
    assert st["lock"] is None and st["log"] == []
    st["runs_used"] = cap - 1
    ok, _ = S.acquire(st, routine, NOW, _cfg(safe))
    assert ok and st["lock"]["cap"] == cap and st["lock"]["safe_mode"] is safe


def test_acquire_of_promote_is_not_capped():
    st = S.empty() | {"night": "2026-11-09", "runs_used": 12}
    ok, _ = S.acquire(st, "promote", NOW, _cfg(False))
    assert ok


def test_a_cap_refusal_does_not_take_over_a_stale_lock():
    old = (NOW - timedelta(hours=3)).isoformat()
    st = S.empty() | {"night": "2026-11-09", "runs_used": 4,
                      "lock": {"routine": "night-worker", "acquired_at": old, "session": None}}
    ok, msg = S.acquire(st, "night-worker", NOW, _cfg(True))
    assert not ok and "run cap reached (4 of 4)" in msg
    assert st["lock"]["acquired_at"] == old and st["log"] == []


# ------------------------------------------------------------------------------- 2. entries carry cap and safe_mode
@pytest.mark.parametrize("safe, cap", [(True, 4), (False, 12)])
def test_release_entry_records_the_cap_and_safe_mode_applied(env, capsys, safe, cap):
    env["cfg"] = _cfg(safe)
    assert S.main(["acquire", "night-worker", "--state", str(env["path"]), "--session", "s"]) == 0
    assert S.main(["release", "night-worker", "--state", str(env["path"]), "--outcome", "merged",
                   "--items", "Q017"]) == 0
    e = json.loads(env["path"].read_text())["log"][-1]
    assert e["routine"] == "night-worker" and e["run"] == 1
    assert e["cap"] == cap and e["safe_mode"] is safe, e
    assert "explorer_model_config" not in e and "explorer_model" not in e


# ------------------------------------------------------------------------------- 3. explorer model on explorer only
@pytest.mark.parametrize("safe, model", [(True, "sonnet"), (False, "opus")])
def test_explorer_model_is_recorded_only_on_explorer_entries(env, capsys, safe, model):
    env["cfg"] = _cfg(safe)
    p = str(env["path"])
    assert S.main(["acquire", "night-explorer", "--state", p, "--session", "s"]) == 0
    assert S.main(["release", "night-explorer", "--state", p, "--outcome", "ok"]) == 0
    env["now"] = NOW + timedelta(minutes=30)
    assert S.main(["acquire", "promote", "--state", p]) == 0
    assert S.main(["release", "promote", "--state", p, "--outcome", "ok"]) == 0
    log = json.loads(env["path"].read_text())["log"]
    ex, pr = log[-2], log[-1]
    assert ex["routine"] == "night-explorer" and ex["explorer_model_config"] == model
    assert ex["cap"] == (4 if safe else 12) and ex["safe_mode"] is safe
    assert pr["routine"] == "promote" and "explorer_model_config" not in pr
    assert all("explorer_model" not in e for e in log)


# ------------------------------------------------------------------------------- 4. the CLI reads main's config only
def test_cli_acquire_records_mains_cap_never_devs(env, capsys):
    env["cfg"] = _cfg(True)                                         # main: safe mode on, cap 4; dev's copy: 12
    assert S.main(["acquire", "night-worker", "--state", str(env["path"])]) == 0
    assert json.loads(env["path"].read_text())["lock"]["cap"] == 4


@pytest.mark.parametrize("exc", [C.MainConfigError("git fetch origin main failed: offline"),
                                 RuntimeError("unexpected")])
def test_cli_acquire_refuses_when_load_main_raises(env, capsys, exc):
    def boom(*a, **k):
        raise exc
    env["cfg"] = boom
    assert S.main(["acquire", "night-worker", "--state", str(env["path"])]) == 3
    assert "refused" in capsys.readouterr().out and not env["path"].exists()


# ------------------------------------------------------------------------------- 5. old locks and state files
def test_stale_takeover_of_a_pre_change_lock_records_cap_null():
    old = (NOW - timedelta(hours=3)).isoformat()
    st = S.empty() | {"night": "2026-11-09", "runs_used": 1,
                      "lock": {"routine": "night-explorer", "acquired_at": old, "session": "x"}}
    ok, msg = S.acquire(st, "night-worker", NOW, _cfg(True))
    assert ok and "stale" in msg
    e = st["log"][-1]
    assert e["outcome"] == "failed" and e["routine"] == "night-explorer"
    assert "cap" in e and e["cap"] is None and e["safe_mode"] is None


def test_stale_takeover_of_a_new_lock_carries_its_fields():
    st = S.empty()
    assert S.acquire(st, "night-explorer", NOW, _cfg(True))[0]
    ok, _ = S.acquire(st, "night-worker", NOW + timedelta(hours=2, minutes=1), _cfg(False))
    e = st["log"][-1]
    assert ok and e["outcome"] == "failed" and e["cap"] == 4 and e["safe_mode"] is True
    assert e["explorer_model_config"] == "sonnet"
    assert st["lock"]["cap"] == 12 and st["lock"]["safe_mode"] is False


def test_release_of_a_pre_change_lock_and_old_state_files_still_load(tmp_path):
    p = tmp_path / "state.json"
    old = {"schema": 1, "night": "2026-11-09", "runs_used": 0, "last_kind": None, "chain_stopped": None,
           "lock": {"routine": "night-worker", "acquired_at": NOW.isoformat(), "session": "s"},
           "log": [{"routine": "night-worker", "started_at": "a", "finished_at": "b", "outcome": "merged",
                    "items": ["Q001"], "commits": [], "note": "", "session": None, "run": 1}]}
    p.write_text(json.dumps(old), encoding="utf-8")
    st = S.load(p)
    e = S.release(st, "night-worker", NOW + timedelta(minutes=10), "merged", ["Q017"])
    assert e["cap"] is None and e["safe_mode"] is None and st["lock"] is None
    S.save(st, p)
    assert S.load(p)["log"][0] == old["log"][0]
