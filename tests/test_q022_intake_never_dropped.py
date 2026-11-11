"""Q022 (approved by Ethan 2026-11-11): a pending ledger-intake run (an issue form) can never be dropped.

* ledger-intake has its own concurrency group per issue; ledger-daily, private-commitments and shadows-setup share
  "ledger-writers" (before: all four shared "ledger-intake", whose single pending slot a newly queued run takes);
* the entry is written through scripts/ledger_commit.sh on a fresh main, so a rejected push re-runs the intake there
  and two forms racing get consecutive ids (before: `git pull --rebase` after allocating the id, which cannot
  re-allocate it);
* ledger-daily re-runs intake for an open Ledger form with no intake comment 30 minutes after it was opened or last
  edited (ledger/intake_runs.py).

Temporary repositories, a bare origin and fixtures only: never the live ledger or the real remote."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from conftest import seed_ledger
from ledger import intake_runs as R
from test_ledger import PASTE_DECISION, TODAY

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows"


def wf(name):
    doc = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)


# ----------------------------------------------------------------------------- (1) the concurrency groups
def test_intake_has_its_own_group_per_issue_and_the_writers_share_another():
    doc, on = wf("ledger-intake.yml")
    group = doc["concurrency"]["group"]
    assert "github.event.issue.number" in group and "inputs.issue" in group and not doc["concurrency"]["cancel-in-progress"]
    assert on["workflow_dispatch"]["inputs"]["issue"]["required"]
    for name in ("ledger-daily.yml", "private-commitments.yml", "shadows-setup.yml"):
        d, _ = wf(name)
        assert d["concurrency"]["group"] == "ledger-writers", name
    for f in WF.glob("*.yml"):                          # no other workflow can take an intake run's pending slot
        if f.name != "ledger-intake.yml":
            g = str((yaml.safe_load(f.read_text(encoding="utf-8")).get("concurrency") or {}).get("group", ""))
            assert not g.startswith("ledger-intake"), f.name


def test_intake_writes_through_ledger_commit_and_never_rebases_an_allocated_id():
    doc, _ = wf("ledger-intake.yml")
    runs = {s.get("name"): str(s.get("run", "")) for s in doc["jobs"]["intake"]["steps"]}
    write = runs["Write the entry through scripts/ledger_commit.sh"]
    assert "scripts/ledger_commit.sh" in write and "--fail-unless-ok" in write and "LEDGER_MSG_FILE" in write
    assert not any("pull --rebase" in r for r in runs.values())
    assert "Seal the new entry" not in runs                # ledger_commit.sh seals
    daily, _ = wf("ledger-daily.yml")
    assert any("ledger.intake_runs sweep" in str(s.get("run", "")) and "gh workflow run ledger-intake.yml" in
               str(s.get("run", "")) for s in daily["jobs"]["daily"]["steps"])


# ----------------------------------------------------------------------------- (2) two forms racing
def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _repo(tmp_path):
    origin, work = tmp_path / "origin.git", tmp_path / "a"
    work.mkdir()
    for d in ("ledger", "scripts"):
        shutil.copytree(ROOT / d, work / d, ignore=shutil.ignore_patterns("__pycache__", "site"))
    seed_ledger(work)
    shutil.copytree(ROOT / "data/janus", work / "data/janus")
    (work / ".gitignore").write_text("__pycache__/\n")
    _git("init", "-q", "-b", "test", cwd=work)
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        _git("config", k, v, cwd=work)
    _git("add", "-A", cwd=work)
    _git("commit", "-q", "-m", "init", cwd=work)
    _git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    _git("remote", "add", "origin", str(origin), cwd=work)
    _git("push", "-q", "origin", "test", cwd=work)
    other = tmp_path / "b"
    _git("clone", "-q", "-b", "test", str(origin), str(other), cwd=tmp_path)
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        _git("config", k, v, cwd=other)
    return origin, work, other


def _env(issue, body, tmp_path):
    return {**os.environ, "LEDGER_BRANCH": "test", "ISSUE_NUMBER": str(issue), "ISSUE_TITLE": f"[Paste] form {issue}",
            "ISSUE_BODY": body, "ISSUE_LABELS": "ledger", "TODAY": TODAY.isoformat(),
            "LEDGER_MSG_FILE": str(tmp_path / f"msg{issue}.txt"), "PYTHONDONTWRITEBYTECODE": "1"}


def _write_cmd(issue, tmp_path):
    return ["bash", "scripts/ledger_commit.sh", f"Ledger entry (issue #{issue})", "--", sys.executable, "-m",
            "ledger.intake", "--out", str(tmp_path / f"final{issue}.json"), "--fail-unless-ok"]


def test_two_forms_racing_get_consecutive_ids_and_both_are_committed(tmp_path):
    origin, a, b = _repo(tmp_path)
    body_b = PASTE_DECISION.replace("Size: 1.5%", "Size: 1%")
    # form A's write: on its first attempt, form B is logged from the other checkout and pushed first, so A's push
    # is rejected and ledger_commit.sh starts again from the new main, re-running A's intake there
    flag = tmp_path / "raced"
    race = (f"import os, subprocess, sys\n"
            f"if not os.path.exists({str(flag)!r}):\n"
            f"    open({str(flag)!r}, 'w').close()\n"
            f"    subprocess.run({_write_cmd(102, tmp_path)!r}, cwd={str(b)!r}, env={_env(102, body_b, tmp_path)!r},"
            f" check=True, capture_output=True)\n"
            f"sys.exit(subprocess.run([sys.executable, '-m', 'ledger.intake', '--out', {str(tmp_path / 'final101.json')!r},"
            f" '--fail-unless-ok']).returncode)\n")
    p = subprocess.run(["bash", "scripts/ledger_commit.sh", "Ledger entry (issue #101)", "--", sys.executable, "-c", race],
                       cwd=a, env=_env(101, PASTE_DECISION, tmp_path), capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "push rejected (attempt 1)" in p.stderr                     # the race really happened
    log = _git("log", "--format=%s", "origin/test", cwd=a).splitlines()
    assert log[:2] == ["Ledger decision D004 (issue #101)", "Ledger decision D003 (issue #102)"], log
    rows = _git("show", "origin/test:data/ledger/decisions.csv", cwd=a)
    assert rows.count("\nD003,") == 1 and rows.count("\nD004,") == 1
    assert json.loads((tmp_path / "final101.json").read_text())["id"] == "D004"   # the comment names the real id
    v = subprocess.run([sys.executable, "-m", "ledger.audit", "verify"], cwd=a, capture_output=True, text=True)
    assert v.returncode == 0, v.stdout + v.stderr


def test_an_entry_that_fails_on_the_fresh_main_writes_nothing(tmp_path):
    origin, a, _ = _repo(tmp_path)
    head = _git("rev-parse", "origin/test", cwd=a)
    p = subprocess.run(_write_cmd(103, tmp_path), cwd=a,
                       env=_env(103, PASTE_DECISION.replace("Size: 1.5%", "Size: 2.5%"), tmp_path),
                       capture_output=True, text=True)
    assert p.returncode == 1 and "nothing committed" in p.stderr
    _git("fetch", "-q", "origin", cwd=a)
    assert _git("rev-parse", "origin/test", cwd=a) == head


# ----------------------------------------------------------------------------- (3) the sweep
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


def issue(n, title="[Decision] MX10Y", created="2026-11-12T10:00:00Z", edited=None, comments=(), labels=("ledger:decision",),
          body="### Instrument\n\nMX10Y"):
    return {"number": n, "title": title, "body": body, "createdAt": created, "lastEditedAt": edited,
            "labels": {"nodes": [{"name": x} for x in labels]},
            "comments": {"nodes": [{"author": {"login": who}, "createdAt": t} for who, t in comments]}}


def test_the_sweep_flags_an_open_form_with_no_intake_comment_after_30_minutes():
    issues = {"data": {"repository": {"issues": {"nodes": [
        issue(1),                                                                        # lost: no intake comment
        issue(2, comments=[("github-actions", "2026-11-12T10:01:00Z")]),                 # processed
        issue(3, created="2026-11-12T11:45:00Z"),                                        # under 30 minutes old
        issue(4, edited="2026-11-12T11:00:00Z", comments=[("github-actions", "2026-11-12T10:01:00Z")]),  # re-edited
        issue(5, comments=[("EthanC100", "2026-11-12T10:05:00Z")]),                      # only a human comment
        issue(6, title="notes", labels=()),                                              # not a Ledger form
        issue(7, title="[Paste] MX10Y", labels=("ledger",), body="DECISION RECORD\nDate: 12 Nov 2026"),   # pasted
    ]}}}}
    assert R.needs_intake(issues, NOW) == [1, 4, 5, 7]


def test_the_issue_loader_matches_the_job_condition(tmp_path):
    ev = {"number": 9, "title": "[Forecast] Fed", "body": "x\ny", "state": "open", "author_association": "OWNER",
          "user": {"login": "EthanC100"}, "labels": [{"name": "ledger:forecast"}]}
    env = R.issue_env(ev)
    assert (env["LEDGER_FORM"], env["ISSUE_LABELS"], env["AUTHOR_ASSOCIATION"]) == ("true", "ledger:forecast", "OWNER")
    assert R.issue_env({**ev, "title": "notes", "labels": []})["LEDGER_FORM"] == "false"
    out = tmp_path / "env"
    R.write_env(env, out)
    text = out.read_text()
    assert "ISSUE_BODY<<EOF_" in text and "\nx\ny\n" in text                          # multi-line safe


# ----------------------------------------------------------------------------- the tests-before-push rule
def test_every_workflow_step_that_pipes_test_output_runs_with_pipefail():
    """CLAUDE.md hard rule 15: a piped test run must fail its step when the tests fail. GitHub runs `shell: bash`
    as `bash --noprofile --norc -eo pipefail`; its default shell has no pipefail."""
    for f in WF.glob("*.yml"):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for jname, job in (doc.get("jobs") or {}).items():
            default = ((job.get("defaults") or {}).get("run") or {}).get("shell") or \
                ((doc.get("defaults") or {}).get("run") or {}).get("shell")
            for s in job.get("steps") or []:
                run = str(s.get("run", ""))
                if "pytest" in run and "|" in run.split("pytest", 1)[1].split("\n", 1)[0]:
                    shell = s.get("shell") or default
                    assert shell == "bash" or "pipefail" in run, f"{f.name} {jname}: {s.get('name')}"
    rule = " ".join((ROOT / "CLAUDE.md").read_text(encoding="utf-8").split())
    assert "pipefail" in rule and "never push after a failed or unverified test run" in rule.lower()
