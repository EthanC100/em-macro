"""promote-merge (Ethan, 2026-11-12): the dev -> main promotion PR is merged by main's code only when promote's checks
passed (report naming the PR), the tests workflow is green on the PR's head, dev changed only bookkeeping after the
checked commit, no protected path changed and there is no conflict; otherwise nothing is merged, the PR stays open
and the morning report flags it. A throwaway repository; no network."""
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from nightshift import morning as MO
from nightshift import promote_merge as PM

REPO = "EthanC100/em-macro"
CODEOWNERS = "# protected:start\n/docs/prereg/ @EthanC100\n/trials.csv @EthanC100\n# protected:end\n"


def git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, files, msg):
    for k, v in files.items():
        (repo / k).parent.mkdir(parents=True, exist_ok=True)
        (repo / k).write_text(v)
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    commit(r, {".github/CODEOWNERS": CODEOWNERS, "a.txt": "a\n"}, "base")
    git(r, "checkout", "-q", "-b", "dev")
    checked = commit(r, {"nightshift/x.py": "x = 1\n"}, "Merge Q030: something")
    return r, checked


def report(checked, pr=7, ok=True, mode="promote", reasons=()):
    return json.dumps({"ok": ok, "mode": mode, "head": checked[:7], "base": "abc1234", "pr":
                       f"https://github.com/{REPO}/pull/{pr}", "reasons": list(reasons)}, indent=1) + "\n"


def pr(head, number=7, **over):
    return {"number": number, "state": "open", "draft": False, "mergeable": True,
            "base": {"ref": "main"}, "head": {"ref": "dev", "sha": head, "repo": {"full_name": REPO}}} | over


def run(head, conclusion="success", **over):
    return {"event": "pull_request", "head_branch": "dev", "head_sha": head, "conclusion": conclusion} | over


def decide(r, p, ru):
    return PM.decide(PM.gather(r, p, ru, REPO, base="main"))


def test_merges_when_everything_passed_and_only_bookkeeping_followed(repo):
    r, checked = repo
    commit(r, {"docs/agent-state.json": "{}\n"}, "promote: lock")
    head = commit(r, {"results/night/promote/2026-11-13.json": report(checked)}, "promote: ok (2026-11-12)")
    d = decide(r, pr(head), run(head))
    assert d["action"] == "merge" and d["number"] == 7 and d["sha"] == head, d
    assert "merging (merge commit)" in PM.comment(d)


@pytest.mark.parametrize("case,expect", [
    ("tests_failed", "tests workflow concluded failure"),
    ("checks_failed", "promote's checks failed: (a) test suite: 1 failed"),
    ("check_only", "not a promote run"),
    ("other_pr", "does not name this PR"),
    ("unchecked_change", "dev changed after promote's checks: nightshift/y.py"),
    ("protected", "protected paths changed: docs/prereg/T30.md"),
    ("conflict", "merge conflicts"),
    ("no_report", "no promote report"),
    ("draft", "draft"),
])
def test_holds_and_merges_nothing(repo, case, expect):
    r, checked = repo
    files = {}
    if case == "unchecked_change":
        files["nightshift/y.py"] = "y = 2\n"
    if case == "protected":
        r_ = commit(r, {"docs/prereg/T30.md": "x\n"}, "night: a prereg file")     # before the check: also protected
        checked = r_
    rep = {"checks_failed": report(checked, ok=False, reasons=["(a) test suite: 1 failed"]),
           "check_only": report(checked, mode="check only"), "other_pr": report(checked, pr=6)}.get(case, report(checked))
    if case != "no_report":
        files["results/night/promote/2026-11-13.json"] = rep
    head = commit(r, files or {"results/night/morning/2026-11-13.md": "m\n"}, "promote: recorded")
    p = pr(head, mergeable=False) if case == "conflict" else pr(head, draft=True) if case == "draft" else pr(head)
    ru = run(head, "failure") if case == "tests_failed" else run(head)
    d = decide(r, p, ru)
    assert d["action"] == "hold" and any(expect in x for x in d["reasons"]), d
    assert "not merged" in PM.comment(d)


def test_ignores_other_branches_superseded_and_cancelled_runs(repo):
    r, checked = repo
    head = commit(r, {"results/night/promote/2026-11-13.json": report(checked)}, "promote: ok")
    assert decide(r, pr(head), run(head, head_branch="night/Q030"))["action"] == "ignore"
    assert decide(r, pr(head), run(checked))["action"] == "ignore"              # tests of an older head
    assert decide(r, pr(head), run(head, "cancelled"))["action"] == "ignore"
    assert PM.decide({"pr": {}, "run": run(head)})["action"] == "ignore"


def test_a_rewritten_dev_or_unknown_checked_commit_holds(repo):
    r, checked = repo
    head = commit(r, {"results/night/promote/2026-11-13.json": report("f" * 40)}, "promote: ok")
    d = decide(r, pr(head), run(head))
    assert d["action"] == "hold" and "is not known" in d["reasons"][0]


def test_the_newest_report_naming_the_pr_is_used(repo):
    r, checked = repo
    commit(r, {"results/night/promote/2026-11-12.json": report(checked, pr=5, ok=False)}, "older night")
    head = commit(r, {"results/night/promote/2026-11-13.json": report(checked),
                      "results/night/promote/2026-11-10_as-if-setup-PR-merged.json": "{}"}, "promote: ok")
    path, rep = PM.find_report(r, head, 7)
    assert path == "results/night/promote/2026-11-13.json" and rep["ok"]


def test_the_cli_writes_the_decision_and_comment(repo, tmp_path, monkeypatch):
    r, checked = repo
    head = commit(r, {"results/night/promote/2026-11-13.json": report(checked)}, "promote: ok")
    monkeypatch.setattr(PM, "ROOT", r)
    (tmp_path / "pr.json").write_text(json.dumps(pr(head)))
    (tmp_path / "run.json").write_text(json.dumps(run(head)))
    PM.main(["decide", "--pr", str(tmp_path / "pr.json"), "--run", str(tmp_path / "run.json"), "--repo-name", REPO,
             "--base", "main", "--out", str(tmp_path / "d.json"), "--comment-file", str(tmp_path / "c.md")])
    assert json.loads((tmp_path / "d.json").read_text())["action"] == "merge"
    assert (tmp_path / "c.md").read_text().startswith(PM.MARKER)


def test_morning_report_flags_a_promotion_that_is_not_on_main(repo, monkeypatch):
    r, checked = repo
    day = date(2026, 11, 13)
    monkeypatch.setattr(MO, "ROOT", r)
    url = f"https://github.com/{REPO}/pull/7"
    assert MO.promoted(day, main="main") == "no - promote did not run (no record)"
    commit(r, {"results/night/promote/2026-11-13.json": report(checked)}, "promote: ok")
    assert MO.promoted(day, main="main").startswith(f"NOT MERGED - {url} is open: checks passed")
    commit(r, {"results/night/promote/2026-11-13.json": report(checked, ok=False, reasons=["(c) protected paths touched: trials.csv"])},
           "promote: refused")
    assert MO.promoted(day, main="main") == f"NOT MERGED - {url} left open; (c) protected paths touched: trials.csv"
    commit(r, {"results/night/promote/2026-11-13.json": report(checked)}, "promote: ok")
    git(r, "checkout", "-q", "main")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "-m", "Night shift: promote dev", "dev")
    assert MO.promoted(day, main="main") == f"yes - merged into main ({url})"
    commit(r, {"results/night/promote/2026-11-13.json": report(checked, mode="check only")}, "check only")
    assert MO.promoted(day, main="main").startswith("no - check only")
