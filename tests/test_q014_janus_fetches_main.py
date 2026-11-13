"""Q014: the morning report's Janus section fetches origin main in code before it reads the Janus records.

Before Q014, janus_section read ``origin/main:data/janus/records.jsonl`` from whatever origin/main ref the checkout
already held (the fetch was only in the morning-report routine's prose), and fell back silently to the working
tree's copy when the read failed. Now it fetches ``origin main`` with an explicit refspec (its own return code
checked, a timeout, GIT_TERMINAL_PROMPT=0), reads with ``git show`` and never checks out; a failed fetch still
reports but marks the C05 line "main not refreshed (fetch failed)"; with no origin/main ref the lines are labelled
"dev copy"; the section always prints "as of <newest recorded_at>".

A temporary bare origin and synthetic fixture records only: ROOT is the temporary checkout and ledger.janus.load's
default path points at its working-tree copy, so the live data/janus records and the real remote are never read.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

from ledger import janus as J
from nightshift import config as C
from nightshift import morning as M
from nightshift import state as S

TODAY = date(2026, 11, 11)
REL = "data/janus/records.jsonl"
CHECK_1 = {"type": "check", "seq": 1, "recorded_at": "2026-11-10T14:21:07+00:00", "result": "main check one"}
CHECK_2 = {"type": "check", "seq": 2, "recorded_at": "2026-11-10T14:46:02+00:00", "result": "main check two"}
DEV_CHECK = {"type": "check", "seq": 1, "recorded_at": "2026-11-09T09:00:00+00:00", "result": "dev copy check"}


def git(cwd: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *a],
                       cwd=cwd, capture_output=True, text=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _write(repo: Path, recs: list[dict]) -> None:
    p = repo / REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in recs), encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """origin.git (bare) whose main holds CHECK_1 then CHECK_2; work is a clone whose origin/main ref is one quick
    check behind (CHECK_1 only), checked out on a dev branch whose working-tree records hold only DEV_CHECK."""
    origin, seed, work = tmp_path / "origin.git", tmp_path / "seed", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _write(seed, [CHECK_1])
    git(seed, "add", "-A")
    git(seed, "commit", "-qm", "janus: check 1")
    git(seed, "push", "-q", str(origin), "main")
    git(tmp_path, "clone", "-q", str(origin), str(work))
    git(work, "checkout", "-q", "-b", "dev")
    _write(work, [DEV_CHECK])
    git(work, "commit", "-qam", "dev copy")
    _write(seed, [CHECK_1, CHECK_2])
    git(seed, "commit", "-qam", "janus: check 2")
    git(seed, "push", "-q", str(origin), "main")                  # the remote is now one check ahead of work's ref
    assert json.loads(git(work, "show", f"origin/main:{REL}"))["seq"] == 1
    monkeypatch.setattr(M, "ROOT", work)
    monkeypatch.setattr(J.load, "__defaults__", (work / REL,))     # never the live data/janus
    return work, origin


def test_q014_stale_ref_is_refreshed_and_the_newer_check_shown(env):
    work, _ = env
    lines = M.janus_section(TODAY)
    check = [l for l in lines if "Last quick check" in l]
    assert check and "main check two" in check[0], lines          # fails before Q014: "main check one"
    assert "2026-11-10T14:46Z" in check[0]
    assert not any("dev copy" in l or "not refreshed" in l for l in lines), lines
    assert json.loads(git(work, "show", f"origin/main:{REL}").splitlines()[-1])["seq"] == 2


def test_q014_section_prints_as_of_newest_recorded_at(env):
    lines = M.janus_section(TODAY)
    assert any("as of 2026-11-10T14:46Z" in l for l in lines), lines
    c05 = [l for l in lines if "C05: " in l]
    assert c05 and "as of 2026-11-10T14:46Z" in c05[0], lines


def test_q014_failed_fetch_marks_the_c05_line(env):
    work, _ = env
    git(work, "remote", "set-url", "origin", str(work.parent / "missing.git"))
    lines = M.janus_section(TODAY)
    c05 = [l for l in lines if "C05: " in l]
    assert c05 and "main not refreshed (fetch failed)" in c05[0], lines
    check = [l for l in lines if "Last quick check" in l]
    assert check and "main check one" in check[0], lines          # the old ref is still read, and marked
    assert any("as of 2026-11-10T14:21Z" in l for l in lines), lines


def test_q014_failed_fetch_still_writes_the_report_and_exits_0(env, monkeypatch):
    work, _ = env
    git(work, "remote", "set-url", "origin", str(work.parent / "missing.git"))
    (work / "docs").mkdir()
    (work / "docs/queue.md").write_text(
        "<!-- queue:start -->\n| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |\n"
        "|---|---|---|---|---|---|---|---|\n<!-- queue:end -->\n", encoding="utf-8")
    cfg = {"run_cap": 12, "safe_mode": {"enabled": False, "run_cap": 4},
           "window": {"start": "22:30", "chain_stop": "05:00", "promote": "05:30", "promote_latest": "07:30"}}
    monkeypatch.setattr(S, "load", lambda *a, **k: S.empty())
    monkeypatch.setattr(C, "load", lambda *a, **k: cfg)
    monkeypatch.setattr(C, "load_main", lambda *a, **k: cfg, raising=False)
    monkeypatch.setattr(M, "promoted", lambda *a, **k: "no - fixture")
    monkeypatch.setattr(M, "merged_into_dev", lambda *a, **k: [])
    monkeypatch.setattr(M, "v1_rules_state", lambda *a, **k: None)
    monkeypatch.setattr(M, "v1_rules_section", lambda *a, **k: ["fixture"])
    monkeypatch.setattr(M, "lab_section", lambda *a, **k: ["fixture"])
    assert M.main(["--date", TODAY.isoformat()]) == 0
    text = (work / f"results/night/morning/{TODAY.isoformat()}.md").read_text(encoding="utf-8")
    c05 = [l for l in text.splitlines() if "C05: " in l]
    assert c05 and "main not refreshed (fetch failed)" in c05[0], text


@pytest.mark.parametrize("how", ["missing path", "no remote"])
def test_q014_no_origin_main_ref_is_labelled_dev_copy(env, how):
    work, _ = env
    if how == "missing path":
        git(work, "remote", "set-url", "origin", str(work.parent / "missing.git"))
        git(work, "update-ref", "-d", "refs/remotes/origin/main")
    else:
        git(work, "remote", "remove", "origin")                    # removes refs/remotes/origin/* too
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "refs/remotes/origin/main"], cwd=work,
                          capture_output=True).returncode != 0
    lines = M.janus_section(TODAY)
    assert lines and all("dev copy" in l for l in lines), lines    # never shown unlabelled
    assert any("dev copy check" in l for l in lines), lines
    assert any("as of 2026-11-09T09:00Z" in l for l in lines), lines
    assert "main not refreshed (fetch failed)" in [l for l in lines if "C05: " in l][0], lines


def test_q014_fetch_has_refspec_timeout_no_prompt_and_never_checks_out(env, monkeypatch):
    work, _ = env
    head, tree = git(work, "rev-parse", "HEAD"), (work / REL).read_text(encoding="utf-8")
    calls = []
    real = subprocess.run

    def spy(argv, *a, **k):
        calls.append((list(argv), k))
        return real(argv, *a, **k)
    monkeypatch.setattr(M.subprocess, "run", spy)
    M.janus_section(TODAY)
    gits = [(argv, k) for argv, k in calls if argv[:1] == ["git"]]
    fetches = [(argv, k) for argv, k in gits if "fetch" in argv]
    assert len(fetches) == 1, gits
    argv, k = fetches[0]
    assert "origin" in argv and "+refs/heads/main:refs/remotes/origin/main" in argv, argv
    assert k.get("timeout") and k["timeout"] <= 300, k
    assert (k.get("env") or {}).get("GIT_TERMINAL_PROMPT") == "0", k
    assert k.get("cwd") == work
    assert any("show" in a and f"origin/main:{REL}" in a for a, _ in gits), gits
    for a, _ in gits:
        assert not {"checkout", "restore", "reset", "switch", "merge", "pull"} & set(a), a
    assert git(work, "rev-parse", "HEAD") == head
    assert (work / REL).read_text(encoding="utf-8") == tree         # the dev checkout's copy is untouched
    assert git(work, "status", "--porcelain") == ""


def test_q014_fetch_timeout_is_a_failed_fetch_not_a_crash(env, monkeypatch):
    real = subprocess.run

    def hang(argv, *a, **k):
        if "fetch" in argv:
            raise subprocess.TimeoutExpired(argv, k.get("timeout"))
        return real(argv, *a, **k)
    monkeypatch.setattr(M.subprocess, "run", hang)
    lines = M.janus_section(TODAY)
    assert "main not refreshed (fetch failed)" in [l for l in lines if "C05: " in l][0], lines
