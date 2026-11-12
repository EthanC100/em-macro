"""Helpers for Manhattan's own tests: the repository's convention for tests inside the existing writers' workflows.

``systematic-monthly`` runs the whole test suite before it commits the rebalance. A Manhattan check of a
hand-edited file (the frozen pre-registration, ``config/manhattan.yaml``) must never stop that workflow, so such a
check **fails** in every Claude Code session and wherever ``NIGHT_SHIFT_STRICT=1`` or ``MANHATTAN_STRICT=1`` is set,
and **skips with a message** inside a GitHub Actions workflow that sets neither (ETHAN_ACTIONS item 11; the same
rule as ``tests/test_manhattan_prereg.py``). Tests of code alone always run.
"""
from __future__ import annotations

import functools
import os


def strict() -> bool:
    env = os.environ
    in_writer_workflow = env.get("GITHUB_ACTIONS") == "true"
    return not in_writer_workflow or env.get("NIGHT_SHIFT_STRICT") == "1" or env.get("MANHATTAN_STRICT") == "1"


def prereg_or_skip() -> str:
    """The pre-registration's SHA-256 for a test module that needs it (the simulation's seeds descend from it).
    When the file no longer matches its recorded hash: an error in a session, a module-level skip in a writer's
    workflow."""
    import pytest

    from manhattan.sim import seeds
    try:
        return seeds.prereg_hash()
    except RuntimeError as e:
        if strict():
            raise
        pytest.skip(f"Manhattan simulation tests skipped in a writer's workflow (set MANHATTAN_STRICT=1 to enforce): {e}",
                    allow_module_level=True)


def reads_hand_edited_file(test):
    """Decorator for a test that compares code with a hand-edited file: a failure is a skip in a writer's workflow."""
    import pytest

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        try:
            return test(*args, **kwargs)
        except Exception as e:                     # an assertion, or the checked code refusing the file
            if strict():
                raise
            pytest.skip(f"Manhattan check failed, skipped in a writer's workflow (set MANHATTAN_STRICT=1 to enforce): {e}")
    return wrapper
