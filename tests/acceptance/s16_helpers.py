"""Helpers for the S16 acceptance tests (imported by name; nothing here is a fixture or a hook)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

import s16_capabilities as CAP


def unbound(capability: str, criteria: str):
    """Called by an integration test once its capability is present: the test must now be bound to the real API."""
    pytest.fail(f"{CAP.UNBOUND}[{capability}]: the capability is present ({CAP.probe(capability)[1]}) but this "
                f"acceptance test is not yet bound to its API. Acceptance criteria to implement: {criteria}")


def hte_workspace(path: Path, bundles):
    from manhattan.hte.runner import Workspace
    ws = Workspace(path)
    reg = ws.registry()
    rep = reg.submit(bundles)
    frozen = reg.freeze()
    return ws, rep, frozen


def fresh_hte_run(path: Path, *, chunk_size: int = 60, bundles=None):
    """A separate small HTE workspace and closed run, for tests that damage artifacts."""
    from manhattan.hte import data as D, fixtures as X
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    panel = D.generate(X.SMALL_PANEL)
    ws, _, _ = hte_workspace(path, bundles if bundles is not None else X.small_bundles())
    out = Runner(ws, panel, Policy(), chunk_size=chunk_size).run()
    return ws, panel, out


HTE_SUBPROCESS = """
import json, sys
from manhattan.hte import data as D, fixtures as X
from manhattan.hte.runner import Workspace, Runner
from manhattan.hte.policy import Policy
ws = Workspace(sys.argv[1])
reg = ws.registry()
if len(reg) == 0:
    reg.submit(X.small_bundles()); reg.freeze()
out = Runner(ws, D.generate(X.SMALL_PANEL), Policy(), chunk_size=int(sys.argv[2]), workers=1).run()
print(json.dumps({"root": out.get("result_root"), "closed": out.get("closed", True), "run_id": out["run_id"]}))
"""


def hte_subprocess(path: Path, fault: str | None = None, chunk: int = 16):
    """Run the HTE experiment in a child process, optionally with an injected hard fault (HTE_FAULT)."""
    import subprocess
    env = dict(os.environ, PYTHONPATH=str(CAP.ROOT), OPENBLAS_NUM_THREADS="1")
    env.pop("HTE_FAULT", None)
    if fault:
        env["HTE_FAULT"] = fault
    return subprocess.run([sys.executable, "-c", HTE_SUBPROCESS, str(path), str(chunk)], env=env, cwd=CAP.ROOT,
                          capture_output=True, text=True, timeout=900)
