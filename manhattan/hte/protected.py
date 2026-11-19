"""Stage 5: protected evaluation. **Disabled.** Every entry point refuses, whatever it is passed.

Protected evaluation would mean evaluating registered candidates on reserve or forward data under the Manhattan
access layer (PR #86) and the frozen protocols. None of its preconditions exist in this engine, and none can be
supplied by a caller:

* no verified access authorization (PR #86 is unmerged and dormant; this package does not import its private names);
* no independently retained anchor for this engine's attempt log;
* ``config/manhattan.yaml``: ``reserve.enabled`` and ``claims.enabled`` are false (read, never written);
* the engine runs on synthetic panels only (``data.verify_synthetic``);
* owner decisions D-1 (which unit is a test), D-8 and D-10 of PR #86 are open.

``status()`` lists these blockers; it reads the config and reports, it never changes anything.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ENABLED = False


class ProtectedEvaluationDisabled(PermissionError):
    """Stage 5 is disabled in code."""


def status() -> dict:
    blockers = [
        "stage 5 is disabled in code (manhattan.hte.protected.ENABLED is a constant False)",
        "PR #86 access layer is not merged; the adapter is disabled (manhattan.hte.adapters)",
        "no independently retained anchor for the HTE attempt log",
        "HTE accepts synthetic panels only",
        "owner decisions D-1, D-8, D-10 (PR #86) are open",
    ]
    try:
        cfg = yaml.safe_load((ROOT / "config" / "manhattan.yaml").read_text()) or {}
        if not (cfg.get("reserve") or {}).get("enabled", False):
            blockers.append("config/manhattan.yaml reserve.enabled is false")
        if not (cfg.get("claims") or {}).get("enabled", False):
            blockers.append("config/manhattan.yaml claims.enabled is false")
    except OSError:
        blockers.append("config/manhattan.yaml unreadable: fail closed")
    return {"enabled": False, "blockers": blockers}


def evaluate(*args, **kwargs):
    raise ProtectedEvaluationDisabled("stage 5 (protected evaluation) is disabled: " + "; ".join(status()["blockers"]))
