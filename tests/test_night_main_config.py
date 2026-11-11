"""The guard, promote and state read config/night.yaml from main, fetched fresh on every run (never dev's copy, never
a stale local ref), and fail safe when it cannot be read. config/night.yaml is a protected path. Git checks run on
temporary repositories; the live config and the real remote are never used."""
import inspect
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from nightshift import config as C
from nightshift import guard as G
from nightshift import promote as PR
from nightshift import protected as P
from nightshift import state as S

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures/night/night.yaml"


def _cfg(safe: bool) -> dict:
    c = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    c["safe_mode"]["enabled"] = safe
    return c


def _git(repo, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=repo, check=True,
                          capture_output=True, text=True).stdout


def _commit_cfg(repo, cfg_text, msg):
    (repo / "config").mkdir(exist_ok=True)
    (repo / "config/night.yaml").write_text(cfg_text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def clone(tmp_path):
    """origin (bare) with main = safe mode off; a clone on a dev branch. Returns (clone, upstream work repo)."""
    up = tmp_path / "up"
    up.mkdir()
    _git(up, "init", "-q", "-b", "main")
    _commit_cfg(up, yaml.safe_dump(_cfg(False)), "off")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(up), str(bare)], check=True)
    _git(up, "remote", "add", "origin", str(bare))
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True)
    _git(work, "checkout", "-q", "-b", "dev")
    return work, up


def test_load_main_fetches_fresh_and_ignores_the_checkout(clone):
    work, up = clone
    assert C.run_cap(C.load_main(work)) == 12
    _commit_cfg(up, yaml.safe_dump(_cfg(True)), "safe mode on")        # Ethan turns safe mode on, on main
    _git(up, "push", "-q", "origin", "main")
    assert C.run_cap(C.load(work / "config/night.yaml")) == 12           # dev's copy and the local ref are stale
    cfg = C.load_main(work)                                             # fetched now
    assert C.run_cap(cfg) == 4 and C.explorer_model(cfg) == "sonnet"


def test_load_main_fails_safe(clone, tmp_path):
    work, up = clone
    _git(work, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    with pytest.raises(C.MainConfigError, match="fetch"):
        C.load_main(work)
    work2 = tmp_path / "work2"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin.git"), str(work2)], check=True)
    _commit_cfg(up, "window: [unclosed\n", "broken")
    _git(up, "push", "-q", "origin", "main")
    with pytest.raises(C.MainConfigError, match="parse"):
        C.load_main(work2)
    _commit_cfg(up, "run_cap: 3\n", "no window")
    _git(up, "push", "-q", "origin", "main")
    with pytest.raises(C.MainConfigError, match="window"):
        C.load_main(work2)


def test_guard_enforces_mains_cap_not_devs(monkeypatch, tmp_path, capsys):
    st = S.empty()
    st["night"], st["runs_used"] = "2026-11-09", 4
    monkeypatch.setattr(S, "load", lambda *a, **k: json.loads(json.dumps(st)))
    monkeypatch.setattr(G, "busy_runs", lambda cfg, **k: [])
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg(False))         # dev's copy says cap 12
    monkeypatch.setattr(C, "load_main", lambda *a, **k: _cfg(True))     # main says safe mode, cap 4
    assert G.main(["check", "night-worker", "--now", "2026-11-09T23:00:00+08:00"]) == 4
    out = json.loads(capsys.readouterr().out)
    assert out["cap"] == 4 and any("run cap reached (4 of 4)" in r for r in out["reasons"])
    monkeypatch.setattr(C, "load_main", lambda *a, **k: _cfg(False))
    assert G.main(["check", "night-worker", "--now", "2026-11-09T23:00:00+08:00"]) == 0


def _unreadable(*a, **k):
    raise C.MainConfigError("git fetch origin main failed: offline")


def test_guard_refuses_when_mains_config_is_unreadable(monkeypatch, capsys):
    monkeypatch.setattr(C, "load_main", _unreadable)
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg(False))
    assert G.main(["check", "night-worker", "--now", "2026-11-09T23:00:00+08:00"]) == 4
    out = json.loads(capsys.readouterr().out)
    assert out["go"] is False and "main's config/night.yaml" in out["reasons"][0]
    assert G.main(["next", "--now", "2026-11-09T23:00:00+08:00"]) == 4
    assert json.loads(capsys.readouterr().out)["next"] == "stop"


def test_state_acquire_uses_main_and_release_never_needs_it(monkeypatch, tmp_path, capsys):
    path = tmp_path / "state.json"
    monkeypatch.setattr(C, "load_main", _unreadable)
    assert S.main(["acquire", "night-worker", "--state", str(path)]) == 3
    assert "refused" in capsys.readouterr().out and not path.exists()
    assert S.main(["release", "night-worker", "--state", str(path), "--outcome", "empty"]) == 0
    assert S.main(["stop", "--state", str(path), "--reason", "x"]) == 0
    seen = []
    monkeypatch.setattr(C, "load_main", lambda *a, **k: seen.append(1) or _cfg(True))
    assert S.main(["status", "--state", str(path)]) == 0
    assert json.loads(capsys.readouterr().out.split("chain stopped: x\n")[-1])["cap"] == 4 and seen


def test_promote_refuses_when_mains_config_is_unreadable(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(C, "load_main", _unreadable)
    monkeypatch.setattr(PR, "run", lambda *a, **k: pytest.fail("checks must not run without main's config"))
    out = tmp_path / "p.json"
    assert PR.main(["--check-only", "--today", "2026-11-11", "--out", str(out)]) == 5
    rec = json.loads(out.read_text())
    assert rec["ok"] is False and rec["checks"]["config"]["ok"] is False
    assert any("config/night.yaml unreadable" in r for r in rec["reasons"])


def test_guard_promote_state_never_read_the_checkout_config():
    for fn in (G.main, PR.main, S.main):
        src = inspect.getsource(fn)
        assert "C.load_main(" in src and "C.load()" not in src, fn.__module__


def test_night_config_is_protected_everywhere():
    assert P.protected(["config/night.yaml"]) == ["config/night.yaml"]                       # CODEOWNERS block
    block = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8").split("# protected:start")[1]
    assert "/config/night.yaml @EthanC100" in block.split("# protected:end")[0]
    assert not P.protected(["config/brief.yaml", "tests/fixtures/night/night.yaml"])
    assert "/config/night.yaml" in P.ALWAYS


def test_promote_check_c_refuses_config_even_with_an_old_codeowners(tmp_path):
    """dev's CODEOWNERS may predate this change; promote check (c) still refuses a dev edit to config/night.yaml."""
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / ".github").mkdir()
    (r / ".github/CODEOWNERS").write_text("# protected:start\n/trials.csv @E\n# protected:end\n")
    _commit_cfg(r, yaml.safe_dump(_cfg(False)), "base")
    _git(r, "checkout", "-q", "-b", "dev")
    _commit_cfg(r, yaml.safe_dump(_cfg(True)), "agent edits the switches")
    changed = PR.changed_on_head(r, "main", "dev")
    assert P.protected(changed, P.patterns(r / ".github/CODEOWNERS")) == ["config/night.yaml"]


def test_claude_md_says_agents_never_edit_the_night_config():
    t = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    rules = t.split("## Night shift: hard rules", 1)[1]
    assert "config/night.yaml" in rules and "Agents never edit `config/night.yaml`" in rules
