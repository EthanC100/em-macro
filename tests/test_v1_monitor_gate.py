"""v1-rules-monitor acts only when the triggering systematic-monthly run's `update` job ran and succeeded (Ethan,
2026-11-12): not after a run whose due gate (Q002) skipped the update, nor after a keep-cache run. The gate step is
run here as written in the workflow, with a stub `gh` (no network)."""
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = yaml.safe_load((ROOT / ".github/workflows/v1-rules-monitor.yml").read_text(encoding="utf-8"))


def test_monitor_waits_for_the_gate():
    on = WF.get("on") or WF.get(True)
    assert on["workflow_run"] == {"workflows": ["systematic-monthly"], "types": ["completed"]}
    assert "workflow_dispatch" in on
    ran, mon = WF["jobs"]["ran"], WF["jobs"]["monitor"]
    assert ran["permissions"] == {"actions": "read"} and ran["outputs"]["run"] == "${{ steps.gate.outputs.run }}"
    assert mon["needs"] == "ran" and mon["if"] == "needs.ran.outputs.run == 'true'"
    assert "workflow_run.conclusion" not in str(mon)                  # the job's own result decides, not the run's
    step = ran["steps"][0]
    assert step["env"]["RUN_ID"] == "${{ github.event.workflow_run.id }}" and "git push" not in step["run"]


def gate(tmp_path, event, api_out="", api_rc=0):
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    (stub / "gh").write_text('#!/bin/bash\necho "$*" >> "$STUB_LOG"\nprintf "%s" "$STUB_OUT"\nexit "$STUB_RC"\n')
    (stub / "gh").chmod(0o755)
    out, log = tmp_path / "out.txt", tmp_path / "gh.log"
    out.write_text("")
    env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "STUB_LOG": str(log),
           "STUB_OUT": api_out, "STUB_RC": str(api_rc), "EVENT": event, "RUN_ID": "43182461362",
           "GITHUB_REPOSITORY": "EthanC100/em-macro", "GH_TOKEN": "x"}
    r = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", WF["jobs"]["ran"]["steps"][0]["run"]],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    calls = log.read_text() if log.exists() else ""
    return out.read_text().strip(), calls


def test_gate_runs_only_after_a_successful_update(tmp_path):
    out, calls = gate(tmp_path, "workflow_run", "success")
    assert out == "run=true" and "actions/runs/43182461362/jobs" in calls
    assert gate(tmp_path, "workflow_run", "skipped")[0] == "run=false"       # due gate: already rebalanced
    assert gate(tmp_path, "workflow_run", "absent")[0] == "run=false"        # keep-cache run: no update job
    assert gate(tmp_path, "workflow_run", "failure")[0] == "run=false"


def test_gate_runs_by_hand_and_when_the_api_is_unreadable(tmp_path):
    out, calls = gate(tmp_path, "workflow_dispatch")
    assert out == "run=true" and calls == ""                                 # no API call for a manual run
    assert gate(tmp_path, "workflow_run", "HTTP 502", api_rc=1)[0] == "run=true"
