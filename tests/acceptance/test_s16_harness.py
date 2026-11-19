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


@pytest.mark.acceptance(id="HARNESS-03", area="harness", requires=())
def test_harness03_an_unimplemented_or_unbound_adapter_never_passes(monkeypatch):
    """Phase 2: every adapter acceptance case carries its adapter's capability, so a missing adapter is BLOCKED; a
    present adapter with no binding fails as UNBOUND; and oracle results are reported under ORC- ids only."""
    import s16_drivers as DRV
    for kind, cap in DRV.ADAPTER_CAPABILITY.items():
        adapter, oracle = DRV.driver_params(kind, "X-01", "integration", ("hte",))
        (am,), (om,) = adapter.marks, oracle.marks
        assert am.kwargs["id"] == "X-01" and cap in am.kwargs["requires"]
        assert om.kwargs["id"] == "ORC-X-01" and cap not in om.kwargs["requires"] and om.kwargs["area"] == "harness"
        assert DRV.ADAPTER_BINDINGS[kind] is None                           # S16 binds nothing it has not seen
        with pytest.raises(pytest.fail.Exception, match=r"UNBOUND\[" + cap):
            DRV.get(kind, DRV.ADAPTER)
    # as shipped, an adapter whose probe is absent is BLOCKED by its own capability
    monkeypatch.setattr(CAP, "probe", lambda name: (name != "adapter:hte->access", "S16 harness simulation"))
    assert CAP.blocked_reason(("hte", "adapter:hte->access")).startswith("BLOCKED[adapter:hte->access]")
    # an oracle pass never satisfies an adapter id in the verdict
    tests = _all()
    tests = [t if t["id"] != "ACC86-01" else _t("ACC86-01", RUN.BLOCKED_) for t in tests]
    v = RUN.verdict(tests, pytest_exit=0)
    assert v["verdict"] == "NOT_READY" and v["by_id"]["ORC-ACC86-01"] == RUN.PASS and v["by_id"]["ACC86-01"] == "BLOCKED"
