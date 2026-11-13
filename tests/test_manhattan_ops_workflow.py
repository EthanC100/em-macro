"""Manhattan ops: the runner workflow is dispatch-only, main-only and leaks nothing by construction (O-05b, O-31)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/manhattan-ops-runner.yml"


def load():
    doc = yaml.safe_load(WF.read_text())
    return doc, doc.get("on") or doc.get(True)


def test_schedule_disabled_dispatch_only():
    doc, on = load()
    assert set(on) == {"workflow_dispatch"}                       # no schedule, no push, no pull_request
    assert "# schedule:" in WF.read_text()                         # present, commented out


def test_main_only_concurrency_and_permissions():
    doc, _ = load()
    assert doc["permissions"] == {"contents": "read", "issues": "write"}
    assert doc["concurrency"] == {"group": "manhattan-ops-ledger", "cancel-in-progress": False}
    for job in doc["jobs"].values():
        assert "github.ref == 'refs/heads/main'" in job["if"]
        assert job["environment"] == "manhattan-ledger"          # secrets live in a main-only environment
        assert job["defaults"]["run"]["shell"] == "bash"


def test_no_artifact_no_output_cache_no_persisted_credentials():
    doc, _ = load()
    text = WF.read_text()
    assert "upload-artifact" not in text and "actions/cache" not in text
    steps = doc["jobs"]["nightly"]["steps"]
    co = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    assert co["with"]["persist-credentials"] is False
    py = next(s for s in steps if s.get("uses", "").startswith("actions/setup-python"))
    assert py["with"]["cache"] == "pip"


def test_keys_go_to_files_with_mode_600_and_a_pinned_host_key():
    text = WF.read_text()
    assert "umask 077" in text and "StrictHostKeyChecking=yes" in text and "ssh-ed25519" in text
    assert "echo \"$LEDGER_KEY\"" not in text and "cat \"$P/ledger_key\"" not in text
    assert 'rm -rf "$RUNNER_TEMP/private"' in text


def test_inputs_reach_the_script_through_env_only():
    text = WF.read_text()
    for line in text.splitlines():
        if "${{ inputs." in line:
            assert line.strip().startswith("ASOF_INPUT:"), line


def test_failure_issue_uses_the_health_record_only():
    doc, _ = load()
    step = next(s for s in doc["jobs"]["nightly"]["steps"] if s.get("if") == "failure()")
    assert "issue-body --health" in step["run"] and "--body-file" in step["run"]
