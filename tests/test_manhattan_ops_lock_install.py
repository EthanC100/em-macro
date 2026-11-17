"""CI-compatible clean-environment dependency closure and dry-run regression."""
import os
from pathlib import Path
import platform
import subprocess
import sys
import venv

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "linux" or platform.machine() != "x86_64" or sys.version_info[:2] != (3, 12),
                    reason="candidate wheel lock targets CPython 3.12 / Linux x86_64 only")
def test_hash_locked_runner_in_clean_environment(tmp_path):
    clean = tmp_path / "locked-venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(clean)
    python = clean / "bin/python"
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV", "GITHUB_STEP_SUMMARY"}}
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    command = [str(python), "-I", "-m", "pip", "--isolated", "install", "--require-hashes",
               "--only-binary=:all:", "--no-cache-dir", "-r", str(ROOT / "requirements-manhattan-runner.lock")]
    # Optional offline wheelhouse avoids network in restricted test sandboxes.
    # CI can use its normal package index; no live workflow change is needed.
    wheelhouse = os.environ.get("MANHATTAN_RUNNER_WHEELHOUSE")
    if wheelhouse:
        command += ["--no-index", "--find-links", str(Path(wheelhouse).resolve(strict=True))]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    probe = subprocess.run([str(python), "-I", str(ROOT / "tests/runner_locked_probe.py")],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert probe.returncode == 0, probe.stdout + probe.stderr
