"""S16 system acceptance suite: markers, capability gating and the shared synthetic experiment.

Every test carries ``@pytest.mark.acceptance(id=..., area=..., requires=(...))``. Before it runs, each required
capability is probed (s16_capabilities.py); if one is missing the test is skipped with a reason that starts with
``BLOCKED[...]``. The runner (tests/acceptance/run.py) reports those as BLOCKED, never as PASS.

The suite is synthetic only. It never reads em-macro-data, real, licensed, reserve or forward data, never writes
under data/ or results/ of this repository (every workspace is a pytest temporary directory), and enables nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parents[1])):        # appended, never prepended: nothing here shadows tests/
    if _p not in sys.path:
        sys.path.append(_p)

import s16_capabilities as CAP  # noqa: E402
from s16_helpers import hte_workspace as _hte_workspace  # noqa: E402

AREAS = ("registration", "identity", "synthetic_data", "authorization", "accounting", "statistics",
         "reconciliation", "research_only", "execution", "equities", "lookahead", "duplicates", "interruption",
         "corruption", "promotion", "protected_data", "observability", "integration", "harness")


def pytest_configure(config):
    config.addinivalue_line("markers", "acceptance(id, area, requires): S16 system acceptance test")


def pytest_collection_modifyitems(config, items):
    seen = {}
    for item in items:
        m = item.get_closest_marker("acceptance")
        if m is None:
            continue
        aid, area = m.kwargs["id"], m.kwargs["area"]
        assert area in AREAS, f"{item.nodeid}: unknown area {area}"
        base = item.nodeid.split("[")[0]
        assert seen.setdefault(aid, base) == base, f"acceptance id {aid} used by two tests"
        item.user_properties.append(("acceptance_id", aid))
        item.user_properties.append(("area", area))
        item.user_properties.append(("requires", ",".join(m.kwargs.get("requires", ()))))


def pytest_runtest_setup(item):
    m = item.get_closest_marker("acceptance")
    if m is None:
        return
    reason = CAP.blocked_reason(m.kwargs.get("requires", ()))
    if reason:
        pytest.skip(reason)


# ------------------------------------------------------------------------------------------------ shared experiment

@pytest.fixture(autouse=True)
def _no_private_store(monkeypatch):
    """The private settlement store must be unreachable from every acceptance test."""
    monkeypatch.setenv("EM_MACRO_DATA", "/nonexistent/em-macro-data")
    monkeypatch.setenv("DATA_REPO_URL", "/nonexistent/em-macro-data.git")
    monkeypatch.delenv("DATA_REPO_READ_TOKEN", raising=False)


@pytest.fixture(scope="session")
def hte_null_experiment(tmp_path_factory):
    """E2E experiment on the null synthetic world: register and freeze, then run stages 1-4, then reconcile."""
    ok, why = CAP.probe("hte")
    if not ok:
        pytest.skip(f"{CAP.BLOCKED}[hte]: {why}")
    from manhattan.hte import data as D, fixtures as X
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    root = tmp_path_factory.mktemp("s16_null")
    panel = D.generate(X.SMALL_PANEL)
    ws, rep, frozen = _hte_workspace(root, X.small_bundles())
    runner = Runner(ws, panel, Policy(), chunk_size=32)
    out = runner.run()
    return {"ws": ws, "panel": panel, "submit": rep, "frozen": frozen, "runner": runner, "out": out,
            "policy": Policy()}


@pytest.fixture(scope="session")
def hte_planted_experiment(tmp_path_factory):
    """The same pipeline on a synthetic world with a planted trend effect (a power check, not a discovery)."""
    ok, why = CAP.probe("hte")
    if not ok:
        pytest.skip(f"{CAP.BLOCKED}[hte]: {why}")
    from manhattan.hte import data as D, fixtures as X
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    root = tmp_path_factory.mktemp("s16_planted")
    panel = D.generate(D.PanelParams(seed=7, n_days=760, protected_days=100, planted=0.6))
    ws, rep, frozen = _hte_workspace(root, X.small_bundles(templates=("trend", "carry")))
    out = Runner(ws, panel, Policy(), chunk_size=64).run()
    return {"ws": ws, "panel": panel, "out": out}
