"""S16 harness self-test: the verdict can only be READY when everything required ran and passed, and the report
never claims scientific verification. Runs on any tree (no capability needed)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import s16_capabilities as CAP

_spec = importlib.util.spec_from_file_location("s16_acceptance_run", Path(__file__).with_name("run.py"))
RUN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RUN)


def _t(i, outcome):
    return {"id": i, "outcome": outcome, "nodeid": f"x::{i}"}


def _all(outcome=RUN.PASS):
    return [_t(i, outcome) for i in RUN.REQUIRED_IDS]


@pytest.mark.acceptance(id="HARNESS-01", area="harness", requires=())
def test_harness01_verdict_is_fail_closed():
    ok = RUN.verdict(_all(), pytest_exit=0)
    assert ok["verdict"] == "READY" and ok["exit"] == 0 and ok["scientifically_verified"] is False
    for outcome, exit_ in ((RUN.BLOCKED_, 0), (RUN.SKIPPED, 0), (RUN.FAIL, 1), (RUN.UNBOUND_, 1), (RUN.ERROR, 1)):
        tests = _all()
        tests[3] = _t(tests[3]["id"], outcome)
        v = RUN.verdict(tests, pytest_exit=0 if exit_ == 0 else 1)
        assert v["verdict"] == "NOT_READY" and v["exit"] == exit_, outcome
        assert v["scientifically_verified"] is False
    v = RUN.verdict(_all()[1:], pytest_exit=0)                       # a required id deleted
    assert v["verdict"] == "NOT_READY" and v["exit"] == 1 and "missing" in v["reasons"][0]
    v = RUN.verdict(_all(), pytest_exit=2)                           # pytest itself broke
    assert v["verdict"] == "NOT_READY" and v["exit"] == 1
    # one parametrised case failing fails its id even when the others pass
    v = RUN.verdict(_all() + [_t("ADV-COR-01", RUN.FAIL)], pytest_exit=1)
    assert v["by_id"]["ADV-COR-01"] == RUN.FAIL and v["verdict"] == "NOT_READY"


@pytest.mark.acceptance(id="HARNESS-02", area="harness", requires=())
def test_harness02_probes_never_raise_and_name_their_source():
    snap = CAP.snapshot()
    assert set(snap) == set(CAP.PROBES)
    for name, s in snap.items():
        assert isinstance(s["present"], bool) and s["detail"] and s["source"], name
    assert CAP.probe("no-such-capability") == (False, "unknown capability 'no-such-capability'")
    assert CAP.blocked_reason(("no-such-capability",)).startswith("BLOCKED[no-such-capability]")
