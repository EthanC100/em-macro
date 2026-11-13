"""Q016: a blocked queue item returns to approved once its machine-checkable ``unblock_when`` condition holds.

Before Q016, ``nightshift.queue auto-approve`` (run by night-start every night) only moved ``proposed`` items, so an
item set to ``blocked`` while it waited for something (Q012: ``nightshift.config.load_main`` on dev) stayed blocked
until someone edited dev by hand. Now an eligible blocked item (type bug/data/lab, Opposition cell ``no block``)
whose ``### Qnnn`` evidence section has exactly one line ``unblock_when: <kind>:<arg>`` at the start of a line goes
back to ``approved`` once the condition is true, and that line is marked fired so it never fires twice.

Kinds (queue text is data, hard rule 12: never eval, exec, import or a shell):
* ``symbol:<module>:<name>``: the module's source on the checked-out branch defines <name> at top level (a def or
  an assignment, found with ``ast``; a comment, docstring, string or import does not count);
* ``commit:<sha>``: the sha fullmatches [0-9a-f]{7,40} and is an ancestor of HEAD (list argv, --end-of-options).

A temporary git repository and fixture queues only: never the live docs/queue.md or the real remote.
"""
from __future__ import annotations

import builtins
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from nightshift import config as C
from nightshift import queue as Q


def git(cwd: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *a],
                       cwd=cwd, capture_output=True, text=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


# config.py before PR #29: load_main is named only in a comment, a docstring, a string, an import alias and nested
# definitions, none of which is a top-level definition.
CONFIG_BEFORE = '''"""Night-shift config. load_main will read main's copy (PR #29)."""
# def load_main(): coming in PR #29
from os import path as load_main_alias
NOTE = "load_main"


def load():
    def load_main():
        return None
    return {}


class Loader:
    load_main = None
'''
CONFIG_AFTER = CONFIG_BEFORE + '''

def load_main():
    return {}
'''

HEAD = """# Night-shift queue

<!-- queue:start -->
| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |
|---|---|---|---|---|---|---|---|
"""


def row(qid, typ="bug", status="blocked", opposition="no block, p=50%"):
    return f"| {qid} | {typ} | {status} | t {qid} | test_{qid.lower()} |  | {opposition} | none |\n"


def section(qid, *lines):
    return f"\n### {qid}\n\nEvidence for {qid}.\n" + "".join(f"{l}\n" for l in lines)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    (r / "nightshift").mkdir(parents=True)
    (r / "nightshift/__init__.py").write_text("", encoding="utf-8")
    (r / "nightshift/config.py").write_text(CONFIG_BEFORE, encoding="utf-8")
    git(r, "init", "-q", "-b", "dev")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    monkeypatch.setattr(C, "ROOT", r)     # the checked-out branch is the temporary repository, never this one
    return r


def write_queue(tmp_path: Path, rows: str, sections: str) -> Path:
    p = tmp_path / "queue.md"
    p.write_text(HEAD + rows + "<!-- queue:end -->\n" + sections, encoding="utf-8")
    return p


def status(path: Path) -> dict:
    return {it["id"]: it["status"] for it in Q.parse(path.read_text(encoding="utf-8"))}


def test_q012_condition_unblocks_once_symbol_is_defined(repo, tmp_path, capsys):
    cond = "unblock_when: symbol:nightshift.config:load_main"
    qp = write_queue(tmp_path, row("Q012"), section("Q012", "Waiting for PR #29.", "", cond))

    # Before load_main is defined at top level (comment, docstring, string, import, nested defs only): stays blocked.
    assert Q.main(["auto-approve", "--queue", str(qp)]) == 0
    assert status(qp)["Q012"] == "blocked"
    assert cond in qp.read_text(encoding="utf-8").splitlines()

    # load_main lands on the checked-out branch: Q012 goes back to approved and its line is marked fired.
    (repo / "nightshift/config.py").write_text(CONFIG_AFTER, encoding="utf-8")
    git(repo, "commit", "-qam", "PR #29: load_main")
    assert Q.main(["auto-approve", "--queue", str(qp)]) == 0
    assert status(qp)["Q012"] == "approved", "blocked forever: no code moves a blocked item back to approved"
    out = capsys.readouterr().out
    assert "Q012" in out
    text = qp.read_text(encoding="utf-8")
    assert cond not in text.splitlines()
    assert re.search(r"^unblock_when \(fired \d{4}-\d{2}-\d{2}\): symbol:nightshift\.config:load_main$", text, re.M)
    assert not Q.validate(Q.parse(text))

    # Fires once: blocked again later (e.g. the worker blocks it), the fired line never re-approves it.
    items = Q.parse(text)
    items[0]["status"] = "blocked"
    qp.write_text(Q.write(text, items), encoding="utf-8")
    assert Q.main(["auto-approve", "--queue", str(qp)]) == 0
    assert status(qp)["Q012"] == "blocked"


def test_live_queue_q012_condition_is_read(repo):
    """Q012's existing line in docs/queue.md is in the form the checker reads (skips if Q012 is gone or reworded)."""
    live = Path(__file__).resolve().parents[1] / "docs/queue.md"
    if not live.exists():
        pytest.skip("docs/queue.md not present")
    text = live.read_text(encoding="utf-8")
    conds = Q.unblock_conditions(text, "Q012")
    if conds != ["symbol:nightshift.config:load_main"] and os.environ.get("NIGHT_SHIFT_STRICT") != "1":
        pytest.skip(f"Q012's unblock_when line is fired, removed or reworded: {conds}")
    if not conds:
        pytest.skip("Q012 has no live unblock_when line (fired or removed)")
    assert conds == ["symbol:nightshift.config:load_main"]
    assert Q.check_condition(conds[0], repo) == (False, None)
    (repo / "nightshift/config.py").write_text(CONFIG_AFTER, encoding="utf-8")
    assert Q.check_condition(conds[0], repo) == (True, None)


def test_assignment_counts_and_symbol_paths(repo):
    (repo / "nightshift/config.py").write_text(CONFIG_BEFORE + "\nload_main = load\n", encoding="utf-8")
    assert Q.check_condition("symbol:nightshift.config:load_main", repo) == (True, None)
    (repo / "nightshift/config.py").write_text(CONFIG_BEFORE + "\nload_main: object = load\n", encoding="utf-8")
    assert Q.check_condition("symbol:nightshift.config:load_main", repo) == (True, None)
    (repo / "nightshift/config.py").write_text(CONFIG_BEFORE + "\nother, load_main = 1, 2\n", encoding="utf-8")
    assert Q.check_condition("symbol:nightshift.config:load_main", repo) == (True, None)
    # a package's __init__ is its source
    (repo / "nightshift/__init__.py").write_text("VERSION = 1\n", encoding="utf-8")
    assert Q.check_condition("symbol:nightshift:VERSION", repo) == (True, None)
    # a missing module is simply not true yet
    assert Q.check_condition("symbol:nightshift.nothere:x", repo) == (False, None)
    # malformed module or name: reported
    for bad in ("symbol:../etc/passwd:x", "symbol:nightshift.config", "symbol:nightshift.config:load-main",
                "symbol:nightshift..config:x", "symbol:/abs:x", "symbol:nightshift.config:x:y"):
        ok, why = Q.check_condition(bad, repo)
        assert ok is False and why, bad


def test_commit_condition(repo, tmp_path):
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("x", encoding="utf-8")
    git(repo, "add", "side.txt")
    git(repo, "commit", "-qm", "side")
    side = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "dev")
    assert Q.check_condition(f"commit:{base}", repo) == (True, None)
    assert Q.check_condition(f"commit:{base[:7]}", repo) == (True, None)
    assert Q.check_condition(f"commit:{side}", repo) == (False, None)
    for bad in ("commit:--output=x", "commit:-h", "commit:HEAD", "commit:abc123", "commit:" + "a" * 41,
                f"commit:{base.upper()}", f"commit:{base} ", "commit:"):
        ok, why = Q.check_condition(bad, repo)
        assert ok is False and why, bad
    assert not (repo / "x").exists() and not (Path.cwd() / "x").exists()

    qp = write_queue(tmp_path, row("Q040") + row("Q041"),
                     section("Q040", f"unblock_when: commit:{base[:12]}") + section("Q041", f"unblock_when: commit:{side}"))
    assert Q.main(["auto-approve", "--queue", str(qp)]) == 0
    assert status(qp) == {"Q040": "approved", "Q041": "blocked"}


def test_eligibility_and_reported_problems(repo, tmp_path, capsys):
    (repo / "nightshift/config.py").write_text(CONFIG_AFTER, encoding="utf-8")
    true = "unblock_when: symbol:nightshift.config:load_main"
    rows = (row("Q030", opposition="BLOCK (c): uses 2021 returns")
            + row("Q031", typ="research")
            + row("Q032", opposition="")
            + row("Q033") + row("Q034") + row("Q035") + row("Q036") + row("Q037")
            + row("Q038", typ="data") + row("Q039", typ="lab", status="approved")
            + row("Q042", status="proposed", opposition=""))
    secs = (section("Q030", true) + section("Q031", true) + section("Q032", true)
            + section("Q033", "unblock_when: url:https://example.com/ok")
            + section("Q034", true, "unblock_when: commit:abcdef0")
            + section("Q035", "unblock_when: symbol nightshift.config load_main")
            + section("Q036", "Indented or inline lines are not conditions:", "  " + true,
                      "see `unblock_when: symbol:nightshift.config:load_main` above")
            + section("Q037", "unblock_when:symbol:nightshift.config:load_main")
            + section("Q038", true) + section("Q039", true) + section("Q042", true))
    qp = write_queue(tmp_path, rows, secs)
    assert Q.main(["auto-approve", "--queue", str(qp)]) == 0
    st = status(qp)
    # never BLOCK (x), never research, never an item with no Opposition review (awaiting Ethan)
    assert st["Q030"] == st["Q031"] == st["Q032"] == "blocked"
    # unknown kind, more than one condition, malformed: stays blocked and is reported
    assert st["Q033"] == st["Q034"] == st["Q035"] == "blocked"
    # no condition at the start of a line: nothing to do
    assert st["Q036"] == "blocked"
    # a condition with no space after the colon is still one condition; data items are eligible
    assert st["Q037"] == st["Q038"] == "approved"
    # only blocked items are moved by a condition
    assert st["Q039"] == "approved" and st["Q042"] == "proposed"
    out = capsys.readouterr().out
    for qid, word in (("Q030", "BLOCK"), ("Q031", "research"), ("Q032", "no block"), ("Q033", "unknown"),
                      ("Q034", "more than one"), ("Q035", "malformed")):
        line = next((l for l in out.splitlines() if qid in l), "")
        assert word.lower() in line.lower(), (qid, out)
    assert "Q036" not in out
    text = qp.read_text(encoding="utf-8")
    # the lines of items that did not fire are untouched
    assert text.count(true + "\n") == 7      # Q030, Q031, Q032, Q034, Q039, Q042 and Q036's indented copy
    assert "unblock_when (fired" in text.split("### Q038", 1)[1]


def test_queue_validated_before_write(repo, tmp_path, capsys):
    (repo / "nightshift/config.py").write_text(CONFIG_AFTER, encoding="utf-8")
    qp = write_queue(tmp_path, row("Q012") + row("Q050", status="proposed") + row("Q051", status="weird"),
                     section("Q012", "unblock_when: symbol:nightshift.config:load_main"))
    before = qp.read_bytes()
    assert Q.main(["auto-approve", "--queue", str(qp)]) != 0
    assert qp.read_bytes() == before
    assert "Q051" in capsys.readouterr().out


def test_no_eval_exec_import_or_shell(repo, tmp_path, monkeypatch):
    sentinel = tmp_path / "IMPORTED"
    (repo / "nightshift/trap.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('imported')\nthing = 1\n", encoding="utf-8")
    (repo / "nightshift/config.py").write_text(CONFIG_AFTER, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "trap")
    base = git(repo, "rev-parse", "HEAD")
    text = (HEAD + row("Q012") + row("Q060") + row("Q061") + "<!-- queue:end -->\n"
            + section("Q012", "unblock_when: symbol:nightshift.config:load_main")
            + section("Q060", "unblock_when: symbol:nightshift.trap:thing")
            + section("Q061", f"unblock_when: commit:{base}"))

    def boom(*a, **k):
        raise AssertionError("queue text reached eval/exec/import/shell")

    real_popen_init = subprocess.Popen.__init__

    def popen_init(self, *a, **k):
        if k.get("shell") or (len(a) > 8 and a[8]):
            raise AssertionError("shell=True")
        return real_popen_init(self, *a, **k)

    monkeypatch.setattr(subprocess.Popen, "__init__", popen_init)
    monkeypatch.setattr(os, "system", boom)
    monkeypatch.setattr(os, "popen", boom)
    monkeypatch.setattr(importlib, "import_module", boom)
    monkeypatch.setattr(builtins, "eval", boom)
    monkeypatch.setattr(builtins, "exec", boom)
    real_import = builtins.__import__
    named = {"nightshift", "nightshift.config", "nightshift.trap"}     # the modules the conditions name

    def no_import(name, globals=None, locals=None, fromlist=(), level=0):
        # The standard library re-imports modules it has already loaded (subprocess -> os.get_exec_path ->
        # ``import warnings``); that loads no code. Any module not yet loaded, or any module a condition names
        # (even the real, already loaded nightshift.config), is refused.
        if level or name in named or name.split(".")[0] in named or name not in sys.modules:
            raise AssertionError(f"queue text reached import ({name})")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", no_import)
    try:
        new, changed, problems = Q.run_auto_approve(text, root=repo)
    finally:
        builtins.__import__ = real_import
    assert sorted(changed) == ["Q012", "Q060", "Q061"] and not problems
    assert not sentinel.exists()
    assert {it["id"]: it["status"] for it in Q.parse(new)} == {"Q012": "approved", "Q060": "approved",
                                                               "Q061": "approved"}


def test_existing_auto_approve_unchanged():
    """Without the queue text, auto_approve keeps its old behaviour (proposed items only)."""
    items = [{"id": "Q001", "type": "bug", "status": "blocked", "opposition": "no block, p=50%"},
             {"id": "Q002", "type": "bug", "status": "proposed", "opposition": "no block, p=50%"}]
    assert Q.auto_approve(items) == ["Q002"]
    assert items[0]["status"] == "blocked"
