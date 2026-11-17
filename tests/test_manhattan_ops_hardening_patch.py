"""Exercise the proposed workflow patch in a temporary checkout only."""
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = Path(".github/workflows/manhattan-ops-runner.yml")


def test_owner_patch_keeps_schedule_and_permissions_unchanged(tmp_path):
    target = tmp_path / WF
    target.parent.mkdir(parents=True)
    original = (ROOT / WF).read_text()
    target.write_text(original)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "apply", str(ROOT / "docs/manhattan/ops/patches/runner-integrity.patch")],
                   cwd=tmp_path, check=True)
    before, after = yaml.safe_load(original), yaml.safe_load(target.read_text())
    assert before[True] == after[True] == {"workflow_dispatch": before[True]["workflow_dispatch"]}
    assert before["permissions"] == after["permissions"]
    assert before["concurrency"] == after["concurrency"]
    steps = after["jobs"]["nightly"]["steps"]
    assert all(re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", s["uses"]) for s in steps if "uses" in s)
    install = next(s["run"] for s in steps if s.get("name") == "Install")
    assert "--require-hashes" in install and "--only-binary=:all:" in install
    assert "requirements-manhattan-runner.lock" in install
    assert after["jobs"]["nightly"]["environment"] == "manhattan-ledger"
    assert after["jobs"]["nightly"]["if"] == before["jobs"]["nightly"]["if"]


def test_lock_has_only_exact_versions_and_wheel_hashes():
    lines = [s for s in (ROOT / "requirements-manhattan-runner.lock").read_text().splitlines()
             if s and not s.startswith("#")]
    assert len(lines) == 6
    assert all(re.fullmatch(r"[a-z0-9-]+==[0-9.]+ --hash=sha256:[a-f0-9]{64}", s) for s in lines)
