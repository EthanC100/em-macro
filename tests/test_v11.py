"""v1.1 = frozen v1.0 + the T18 rule (em_macro/systematic_v11.py, docs/v1.1_freeze.md).

Synthetic inputs check that v1.1 is exactly T18's code on v1.0's targets and that its monthly update writes only
its own folders; the committed files check the freeze record (hashes, the T18 reproduction, the cost diagnostic)
and the live outputs; the workflow checks that v1.1 runs after v1.0 and cannot stop v1.0's commit."""
import hashlib
import json
import os
import subprocess
import textwrap

import numpy as np
import pandas as pd
import pytest
import yaml

from em_macro import systematic as SY
from em_macro import systematic_v11 as V11
from em_macro import t18_rebal as T18
from em_macro.config import ROOT

from test_tstrend import _toy_inputs

V1 = ["carry", "trend", "value"]
FX_REAL = ["BRL", "MXN", "ZAR", "TRY", "IDR", "PLN"]
BOND_REAL = ["BR10Y", "MX10Y", "FR-DE", "IT-DE", "DE10Y"]

# SHA-256 recorded in docs/v1.1_freeze.md
V11_HASHES = {
    **V11.FROZEN,
    "em_macro/systematic_v11.py": "b3c4404ed80209efd1b3fa0e993f30bbac2650b2a9af042f07f8e21175885952",
}


@pytest.fixture(scope="module")
def inp():
    x = _toy_inputs(3)
    ren = dict(zip(["F1", "F2", "F3", "F4", "F5", "F6", "B1", "B2", "B3", "B4", "B5"], FX_REAL + BOND_REAL))
    for b in ("fx", "bond"):
        x[b] = {k: v.rename(columns=ren) for k, v in x[b].items()}
    x["cost"] = {ren[k]: v for k, v in x["cost"].items()}
    rng = np.random.default_rng(9)
    x["carry_basket"] = pd.Series(rng.normal(0, 0.02, len(x["months"])), index=x["months"])
    x["spx"] = pd.Series(rng.normal(0.008, 0.04, len(x["months"])), index=x["months"])
    return x


# ------------------------------------------------------------------ definition
@pytest.mark.parametrize("path,sha", sorted(V11_HASHES.items()))
def test_v11_frozen_files_unchanged(path, sha):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha


def test_rule_is_t18_as_preregistered():
    assert V11.RULE["band_risk_units"] == T18.BAND_RISK == 0.10
    assert V11.RULE["partial_rebalancing"] == T18.PARTIAL == 0.5
    assert V11.LIVE_START_MONTH == "2026-12" and V11.LIVE_SINCE == "2026-12-03"


def test_v11_is_t18_run_exactly(inp):
    a, la = V11.run(inp)
    b, lb = T18.run(inp)
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(a.attrs["weights"], b.attrs["weights"])
    pd.testing.assert_frame_equal(la, lb)


def test_only_change_is_the_band(inp):
    # targets before the band are v1.0's (v1.0 with no band holds exactly them) ...
    nb = SY.run(inp, V1, band=0)
    pd.testing.assert_frame_equal(T18.capped_targets(inp), nb.attrs["weights"], check_names=False)
    # ... and the P&L path with v1.0's own band reproduces v1.0
    held = SY._apply_band(T18.capped_targets(inp), SY.DESIGN["no_trade_band"])
    assert (T18.pnl(inp, held)["net"] - SY.run(inp, V1)["net"]).abs().max() == 0.0


def test_turnover_matches_cost_with_uniform_costs(inp):
    x = {**inp, "cost": {k: 0.002 for k in inp["cost"]}}
    res, _ = V11.run(x)
    pd.testing.assert_series_equal(V11.turnover(res) * 0.002, res["cost"], check_names=False)


def test_sample_labels():
    P = lambda s: pd.Period(s, "M")
    assert V11.sample_label(P("2019-12")).startswith("design")
    assert V11.sample_label(P("2020-01")).startswith("test") and V11.sample_label(P("2026-09")).startswith("test")
    assert V11.sample_label(P("2026-10")) == V11.sample_label(P("2026-11")) == "pre-live (not counted)"
    assert V11.sample_label(P("2026-12")) == "live paper trading (v1.1)"


# ------------------------------------------------------------------ monthly update
def test_update_writes_only_v11_folders(inp, tmp_path, monkeypatch):
    monkeypatch.setattr(SY, "build_inputs", lambda: inp)
    before = {p: (ROOT / "results/systematic" / p).read_bytes() for p in ("positions.csv", "paper_pnl.csv")}
    pos = V11.stage_update(out=tmp_path / "v11", compare_dir=tmp_path / "cmp")
    after = {p: (ROOT / "results/systematic" / p).read_bytes() for p in before}
    assert before == after                                         # v1.0's outputs untouched
    res, _ = V11.run(inp)
    W, t = res.attrs["weights"], inp["months"][-1]
    assert set(pos["instrument"]) == {k for k in W.columns if abs(W.at[t, k]) >= 1e-9}
    assert (pos["as_of"] == str(t)).all() and (pos["effective_from"] == str(t + 1)).all()
    for _, r in pos.iterrows():
        assert r["size_pct_of_capital"] == round(100 * W.at[t, r["instrument"]], 2)
    assert pos["risk_share_pct"].sum() == pytest.approx(100, abs=0.5)
    pnl = pd.read_csv(tmp_path / "v11/paper_pnl.csv")
    assert np.allclose(pnl["net"], res["net"].values, atol=5e-7)
    cmp = pd.read_csv(tmp_path / "cmp/turnover.csv")
    assert np.allclose(cmp["v1.1_turnover"], V11.turnover(res).values, atol=5e-7)
    assert np.allclose(cmp["v1.0_turnover"].dropna(),
                       V11.turnover(SY.run(inp, V1)).reindex(pd.PeriodIndex(cmp["month"], freq="M")).dropna().values,
                       atol=5e-7)


def test_update_refuses_if_a_frozen_file_changed(monkeypatch):
    monkeypatch.setitem(V11.FROZEN, "em_macro/t18_rebal.py", "0" * 64)
    with pytest.raises(SystemExit, match="refuses to run"):
        V11.check_frozen()


# ------------------------------------------------------------------ committed outputs
def test_committed_reproduction_is_exact():
    rep = json.loads((ROOT / "results/systematic_v1.1/freeze/reproduction.json").read_text())
    assert rep["t18_reproduced_exactly"] and rep["v1.0_reproduced_exactly"]
    assert all(c["identical"] for c in rep["checks"].values())
    for p, h in V11.FROZEN.items():
        assert rep["sha256"][p] == h


def test_committed_cost_diagnostic():
    tab = pd.read_csv(ROOT / "results/systematic_v1.1/freeze/cost_sensitivity.csv")
    assert tab["scenario"].nunique() == 6 and len(tab) == 12 and (tab["months"] == 81).all()
    meta = json.loads((ROOT / "results/systematic_v1.1/freeze/cost_sensitivity.json").read_text())
    assert meta["max_abs_diff_v1.0_vs_cost_audit_step3_at_4dp"] == 0.0
    assert meta["max_abs_diff_v1.1_vs_T18_performance_at_4dp"] == 0.0
    one = tab[tab.scenario.str.startswith("1x")].set_index("strategy")
    assert one.loc["v1.0", "sharpe"] == pytest.approx(0.6536, abs=1e-4)
    assert one.loc["v1.1", "sharpe"] == pytest.approx(0.9163, abs=1e-4)
    # turnover does not depend on costs (same positions in every scenario)
    assert tab.groupby("strategy")["turnover_x_pa"].nunique().eq(1).all()


def test_committed_live_outputs_are_consistent():
    d = ROOT / "results/systematic_v1.1"
    pnl = pd.read_csv(d / "paper_pnl.csv")
    pos = pd.read_csv(d / "positions.csv")
    live = pnl[pnl["sample"] == "live paper trading (v1.1)"]
    assert (live["month"] >= V11.LIVE_START_MONTH).all()
    assert (pnl.loc[pnl["month"] >= V11.LIVE_START_MONTH, "sample"] == "live paper trading (v1.1)").all()
    assert pos["as_of"].nunique() == 1 and (pos["version"] == "v1.1").all()
    cmp = pd.read_csv(ROOT / "results/live_compare/turnover.csv").set_index("month")
    m = pnl.set_index("month")["turnover"]
    assert np.allclose(cmp.loc[m.index, "v1.1_turnover"], m, atol=1e-6)
    # the T18 test period inside v1.1's paper P&L equals T18's committed monthly returns at 6 decimals,
    # up to input refreshes after the freeze (the monthly workflow rebuilds the inputs)
    t18 = pd.read_csv(ROOT / "results/T16-T19/monthly_net.csv").set_index("month")["all|1x|T18"]
    test = pnl.set_index("month").loc["2020-01":"2026-09", "net"]
    assert (test - t18.loc[test.index]).abs().max() < 1e-3


# ------------------------------------------------------------------ workflow
def _steps():
    wf = yaml.safe_load((ROOT / ".github/workflows/systematic.yml").read_text())
    return wf["jobs"]["update"]["steps"]


def test_workflow_runs_v11_after_v10_without_blocking_it():
    steps = _steps()
    ids = [s.get("id") for s in steps]
    for sid in ("update", "rebalance", "overlay"):
        assert ids.index(sid) < ids.index("update_v11") < ids.index("rebalance_v11") < ids.index("commit")
    by = {s.get("id"): s for s in steps}
    assert by["update"]["run"].startswith("python -m em_macro.systematic update")           # v1.0 step as before
    assert by["update_v11"]["continue-on-error"] and by["rebalance_v11"]["continue-on-error"]
    assert "systematic_v11 update" in by["update_v11"]["run"]
    commit = by["commit"]["run"]
    assert "results/systematic/positions.csv results/systematic/paper_pnl.csv" in commit
    assert "results/systematic_v1.1" in commit and "results/live_compare" in commit
    alert = next(s for s in steps if s.get("name") == "Open or update the alert issue")
    assert "steps.update_v11.outcome == 'failure'" in alert["if"]
    close = next(s for s in steps if s.get("name") == "Close open alert issues after a successful run")
    assert "steps.update_v11.outcome == 'success'" in close["if"]


@pytest.mark.parametrize("commit,expect", [("success", "Only the v1.1 step failed"),
                                           ("skipped", "This month's rebalance has not been committed")])
def test_alert_body_for_a_v11_failure(tmp_path, commit, expect):
    alert = next(s for s in _steps() if s.get("name") == "Open or update the alert issue")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "gh").write_text(textwrap.dedent(f'''\
        #!/usr/bin/env bash
        prev=""
        for a in "$@"; do
          if [ "$prev" = "--body-file" ]; then cp "$a" "{tmp_path}/body.md"; fi
          prev="$a"
        done
        exit 0
    '''))
    (bin_ / "gh").chmod(0o755)
    (tmp_path / "update_v11.log").write_text("Traceback: v1.1 broke\n")
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "GH_TOKEN": "x", "RUNNER_TEMP": str(tmp_path),
           "GITHUB_REPOSITORY": "owner/em-macro", "RUN_URL": "https://example/run/1", "RUN_ATTEMPT": "1",
           "COMMIT_OUTCOME": commit,
           "OUTCOMES": "install=success refresh=success update=success rebalance=success overlay=success "
                       f"update_v11=failure rebalance_v11=skipped tests=success commit={commit}"}
    p = subprocess.run(["bash", "-eo", "pipefail", "-c", alert["run"]], env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    body = (tmp_path / "body.md").read_text()
    assert "**Failing step:** v1.1 positions and paper P&L" in body and "v1.1 broke" in body
    assert expect in body
