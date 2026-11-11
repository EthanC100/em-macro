"""The pull-request test workflow (.github/workflows/tests.yml): it runs the full suite on every PR to main, fails the
check when pytest fails (pipefail), and writes nothing."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/tests.yml"


def load():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    return doc, doc.get("on") or doc.get(True)          # PyYAML reads the bare key `on` as True


def test_it_runs_the_full_suite_on_every_pull_request_to_main():
    doc, on = load()
    assert set(on) == {"pull_request"} and on["pull_request"]["branches"] == ["main"]
    steps = doc["jobs"]["pytest"]["steps"]
    run = next(s["run"] for s in steps if s.get("name") == "Full test suite")
    assert run.startswith("python -m pytest -q") and " tests/" not in run          # the whole suite, not a subset
    install = next(s["run"] for s in steps if s.get("name") == "Install")
    assert "requirements.txt" in install and "requirements-elections.txt" in install


def test_a_failing_test_fails_the_check():
    doc, _ = load()
    assert doc["jobs"]["pytest"]["defaults"]["run"]["shell"] == "bash"      # GitHub runs it with -eo pipefail
    steps = doc["jobs"]["pytest"]["steps"]
    run = next(s for s in steps if s.get("name") == "Full test suite")
    assert "continue-on-error" not in run and "|| true" not in run["run"]


def test_it_writes_nothing():
    doc, _ = load()
    assert doc["permissions"] == {"contents": "read"}
    assert "permissions" not in doc["jobs"]["pytest"]
    steps = doc["jobs"]["pytest"]["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False
    text = WF.read_text(encoding="utf-8")
    body = text.split("jobs:", 1)[1]
    for w in ("git push", "git commit", "gh issue", "gh pr", "gh api", "upload-artifact", "secrets.", "GITHUB_TOKEN",
              "ledger_commit"):
        assert w not in body, w
    assert all(str(s.get("uses", "")).split("@")[0] in ("actions/checkout", "actions/setup-python", "")
               for s in steps)
    env = doc["jobs"]["pytest"]["env"]
    assert env["EM_MACRO_DATA"].startswith("/nonexistent") and env["DATA_REPO_URL"].startswith("/nonexistent")
