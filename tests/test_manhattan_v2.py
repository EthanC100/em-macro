"""SIM_PREREG_v2: the routing of runs, the hedged pipeline, the HB pipeline with the analytic model,
the metrics, the report and the run package. Synthetic data only.

Version 1's code files are not touched by version 2 (``run.CODE_FILES`` hash to what they did), so its records
on file keep counting; these tests check that only the runs version 2 names go to the new code.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from manhattan import prereg_v2
from manhattan.sim import criteria, criteria_v2, hb, hb_v2, metrics_v2, pipeline, pipeline_v2, report_v2, run, runlog, seeds, world
from manhattan.stats import dormancy, hier_analytic, tiers
from manhattan.testing import prereg_or_skip, reads_hand_edited_file

ROOT = Path(__file__).resolve().parents[1]
SHA = prereg_or_skip()
TINY = world.Size("STD", 3, 4, 5, 2, 3, 4, 6)
TINY_HB = world.Size("HB", 4, 5, 5, 2, 3, 5, 10)


@pytest.fixture
def tiny(monkeypatch):
    monkeypatch.setitem(world.SIZES, "STD", TINY)
    monkeypatch.setitem(world.SIZES, "HB", TINY_HB)
    # a coarse grid in every dimension: these tests are about plumbing, and an HB replication now has 40 reviews
    # of six fits each (the grid of Protocol 3.1 Appendix B is checked in tests/test_manhattan_hier_analytic.py)
    monkeypatch.setattr(hier_analytic, "MU_A_GRID", hier_analytic.MU_A_GRID[::12])
    monkeypatch.setattr(hier_analytic, "TAU_A_GRID", hier_analytic.TAU_A_GRID[::3])
    monkeypatch.setattr(hier_analytic, "MU_RHO_Z", hier_analytic.MU_RHO_Z[::4])
    monkeypatch.setattr(hier_analytic, "SIGMA_RHO_GRID", hier_analytic.SIGMA_RHO_GRID[::2])
    w = np.exp(hier_analytic.NU_LOGW[::3])
    monkeypatch.setattr(hier_analytic, "NU_GRID", hier_analytic.NU_GRID[::3])
    monkeypatch.setattr(hier_analytic, "NU_LOGW", np.log(w / w.sum()))
    return TINY


# ------------------------------------------------------------------ version 1 stays as it was

def test_version_1_is_untouched_by_the_v2_code_lists():
    assert run.CODE_FILES_V2[: len(run.CODE_FILES)] == run.CODE_FILES
    assert set(run.CODE_FILES_V2) - set(run.CODE_FILES) == {"manhattan/stats/spa_hedged.py", "manhattan/sim/pipeline_v2.py"}
    assert "manhattan/stats/hier.py" not in run.CODE_FILES_V2_HB                    # the sampler is not in the main loop
    assert {"manhattan/stats/hier_analytic.py", "manhattan/sim/hb_v2.py", "manhattan/ledger.py"} <= set(run.CODE_FILES_V2_HB)
    # the revised dormancy rule is a new file; version 1's tier code is in both lists and is the same file
    assert "manhattan/stats/dormancy.py" in run.CODE_FILES_V2_HB and "manhattan/stats/dormancy.py" not in run.CODE_FILES_HB
    assert "manhattan/stats/tiers.py" in run.CODE_FILES_V2_HB and "manhattan/stats/tiers.py" in run.CODE_FILES_HB
    assert run.code_hash("HB") == "0b8dd1af6db62c9f" and run.code_hash("STD") == "da641c096d17bbf4"      # version 1's, as on its records
    hashes = {run.code_hash("STD"), run.code_hash("HB"), run.code_hash("STD", version="v2"), run.code_hash("HB", version="v2")}
    assert len(hashes) == 4


# ------------------------------------------------------------------ which code runs what

def test_only_what_v2_changed_is_routed_to_the_new_code():
    for scenario, size in run.development_plan("v1"):
        assert run.route(scenario, size, "v1") == "v1"
        want = "v2" if (size == "HB" or scenario == "D11") else "v1"
        assert run.route(scenario, size, "v2") == want, (scenario, size)
    assert all(run.route(t, "STD", "v2") == "v2" for t in criteria_v2.TWINS)
    with pytest.raises(ValueError):
        run.route("D01", "STD", "v3")
    v1, v2 = run.development_plan(), run.development_plan("v2")
    assert [p for p in v2 if p in v1] == v1 and set(v2) - set(v1) == {(t, "STD") for t in criteria_v2.TWINS}
    assert v2.index(("D01h", "STD")) > v2.index(("D02", "LONG")) and v2.index(("D08h", "STD")) < v2.index(("D01", "HB"))


def test_a_twin_exists_for_every_development_scenario_where_v3_is_required():
    required = [s for s in criteria.V3_REQUIRED if s in world.SCENARIOS and not world.SCENARIOS[s].hedge]
    assert sorted(criteria_v2.TWINS.values()) == sorted(required) and criteria_v2.TWINS is pipeline_v2.TWINS
    assert all(t == base + "h" for t, base in criteria_v2.TWINS.items())
    for t, base in criteria_v2.TWINS.items():
        scn, src = pipeline_v2.scenario(t), world.SCENARIOS[base]
        assert scn.hedge and scn.id == t and scn.sizes == ("STD",) and pipeline_v2.stream_id(t) == base
        assert (scn.weights, scn.dist, scn.pi1, scn.garch, scn.ar, scn.select_k, scn.m) == \
            (src.weights, src.dist, src.pi1, src.garch, src.ar, src.select_k, src.m)
    assert pipeline_v2.scenario("D11") is world.SCENARIOS["D11"]
    with pytest.raises(ValueError, match="no estimated hedge"):
        pipeline_v2.scenario("D05")
    assert criteria_v2.HEDGED_HELD_OUT == ("H12",) and "H12" not in world.HELD_OUT        # defined in the text, not coded


# ------------------------------------------------------------------ the hedged pipeline

def test_the_unhedged_returns_are_those_the_world_hedged(tiny):
    scn = world.SCENARIOS["D11"]
    st = seeds.Streams(SHA, 0, "D11", "STD", 0)
    cm = world.common(scn, st)
    for _, _, fams in world.batches(scn, TINY, st):
        for fam in fams:
            assert pipeline_v2.hedge_reproduces_the_world(fam, st, cm)
            r, C = pipeline_v2.unhedged(fam, st, cm)
            assert r.shape == (fam.X.shape[0] * fam.X.shape[1], fam.X.shape[2]) and C.shape == (1, fam.X.shape[2])
        break


def test_d11_under_v2_keeps_the_30_test_beside_the_hedge_aware_one(tiny):
    v2 = pipeline_v2.run_replication("D11", "STD", 0)
    v1 = pipeline.run_replication("D11", "STD", 0)
    assert v2["kind"] == "full" and v2["n_reserve_null"] == v1["n_reserve_null"] and v2["n_families"] == v1["n_families"]
    for a in pipeline.P_LEVELS:                                       # the 3.0 column is version 1's own result
        assert v2[f"v30_p{a}_num"] == v1[f"m3_p{a}_num"]
        assert v2[f"m3_p{a}_num"] == v2[f"v31_p{a}_num"]              # and the p-value of record is the hedge-aware one
    assert v2["v30_rw_num"] == v1["m3_rw_num"] and v2["m3_rw_num"] == v2["v31_rw_num"]
    assert {f"{k}_{x}" for k in pipeline_v2.METHODS for x in ("pl05_num", "pu05_num", "mean_B")} <= set(v2)
    assert all(k in v2 for k in ("m1_i_b3", "m2_i_y10", "m4_i", "m5_20_num", "fwd_enrolled_ii"))
    again = pipeline_v2.run_replication("D11", "STD", 0)
    assert {k: v for k, v in v2.items() if k != "seconds"} == {k: v for k, v in again.items() if k != "seconds"}


def test_a_twins_oracle_is_its_version_1_scenario(tiny):
    twin = pipeline_v2.run_spa_replication("D05h", 0)
    base = pipeline.run_replication("D05", "STD", 0)
    assert twin["kind"] == "spa_only" and twin["n_families"] == base["n_families"]
    assert twin["n_reserve_null"] == base["n_reserve_null"] and twin["m3_rw_den"] == base["m3_rw_den"]
    for a in pipeline.P_LEVELS:
        assert twin[f"oracle_p{a}_num"] == base[f"m3_p{a}_num"]
    assert twin["oracle_rw_num"] == base["m3_rw_num"] and twin["oracle_mean_B"] == pytest.approx(base["mean_B"])
    assert not any(k.startswith(("m1_", "m2_", "fwd_")) for k in twin)              # no screening, no forward test


# ------------------------------------------------------------------ the HB pipeline

def test_common_share_is_version_1s_correlation_without_its_shrinkage():
    rng = np.random.default_rng(3)
    c = rng.standard_normal(600)
    series = [0.6 * c[s : s + n] + rng.standard_normal(n) for s, n in ((0, 400), (100, 400), (200, 300), (350, 250))]
    starts = [0, 100, 200, 350]
    C = 2.0 * hb.overlap_correlation(series, starts, 600) - np.eye(4)              # undo the half-way shrinkage
    off = C[~np.eye(4, dtype=bool)].mean()
    assert hb_v2.common_share(series, starts, 600) == pytest.approx(off, abs=1e-12) and off > 0.05
    assert hb_v2.common_share(series[:1], starts[:1], 600) == 0.0
    assert hb_v2.common_share([c[:300], c[:300], c[:300]], [0, 0, 0], 600) == hier_analytic.R_F_MAX     # capped
    assert hb_v2.common_share([c[:300], -c[:300]], [0, 0], 600) == 0.0                                    # floored


def test_hb_replication_with_the_analytic_model(tiny):
    r = hb_v2.run_replication("D02", 0)
    assert r["model"] == hb_v2.MODEL and r["size"] == "HB" and r["n_families"] == 20 and "sampler" not in r
    # amendment 1 of SIM_PREREG_v2: a review every 63 days, 40 of them; M7 and M9 are read at years 2, 4, 7 and 10
    assert r["review_step"] == hb_v2.REVIEW_STEP == 63 and r["review_days"] == list(range(63, 2521, 63)) == hb_v2.review_days()
    assert len(r["review_days"]) == 40 and all(y * world.YEAR in r["review_days"] for y in hb.EVAL_YEARS)
    assert list(r["reviews"]) == ["2", "4", "7", "10"] and r["eval_years"] == [2, 4, 7, 10] == list(hb.EVAL_YEARS)
    assert [v["day"] for v in r["reviews"].values()] == [504, 1008, 1764, 2520]
    q = r["quarterly"]
    assert all(len(q[k]) == 40 for k in ("ok", "edge_mass", "n_live", "six_fits_seconds", "r_F", "written_i", "written_ii",
                                         "dormant_i", "dormant_ii"))
    assert q["n_live"] == [5] * 10 + [10] * 10 + [15] * 10 + [20] * 10             # a batch of five every 2.5 years
    assert r["reviews_not_computed"] == sum(not x for x in q["ok"]) == 0             # M12 is counted over all 40
    assert [q["ok"][i] for i in (7, 15, 27, 39)] == [v["review_ok"] for v in r["reviews"].values()]
    assert [q["n_live"][i] for i in (7, 15, 27, 39)] == [v["n_live"] for v in r["reviews"].values()]
    assert q["dormant_i"][:4] == [0] * 4 and q["dormant_ii"][:4] == [0] * 4          # p^F needs 252 forward days, at two reviews
    for v in r["reviews"].values():
        assert v["review_ok"] and v["ok"] == [True] * 6 and max(v["edge_mass"]) <= hier_analytic.EDGE_MASS_MAX
        assert 0.0 <= v["r_F"] <= hier_analytic.R_F_MAX and len(v["fit_seconds"]) == 6 and v["six_fits_seconds"] > 0
        assert sum(v["cal_n"]) == v["n_eval"] == v["n_live"] and {"mu_A", "tau_A", "psi", "nu", "rho_0"} <= set(v["hyper"])
    assert all(f"m8_den_{c}" in r and f"end_dormant_{c}" in r for c in pipeline.CANDIDATES)
    # the dormancy rule of Protocol 3.1 section 9.1, and what the report needs about attention and the tier
    assert r["dormancy"] == dormancy.RULE and r["family_reviews"] == sum(q["n_live"]) == 500
    assert len(r["edge_true"]) == len(r["edge_freeze"]) == r["m8_den_i"] and all(x >= world.THETA_MIN for x in r["edge_true"])
    for c in pipeline.CANDIDATES:
        assert len(r[f"edge_first_supported_day_{c}"]) == len(r[f"edge_dormant_end_{c}"]) == r[f"m8_den_{c}"]
        assert set(r[f"edge_first_supported_day_{c}"]) <= {0, *r["review_days"]}      # the day of a review, or never
        assert r[f"written_{c}"] == sum(q[f"written_{c}"]) <= r["family_reviews"]
        assert all(0 <= d <= n and w >= n - d for d, w, n in zip(q[f"dormant_{c}"], q[f"written_{c}"], q["n_live"]))
        assert [q[f"dormant_{c}"][i] for i in (7, 15, 27, 39)] == [v[f"dormant_{c}"] for v in r["reviews"].values()]
        assert r[f"null_dormant_{c}"] + sum(r[f"edge_dormant_end_{c}"]) == r[f"end_dormant_{c}"]
    again = hb_v2.run_replication("D02", 0)
    strip = lambda x: {k: ({y: ({a: b for a, b in rv.items() if "seconds" not in a} if k == "reviews" else rv)
                            for y, rv in v.items() if "seconds" not in y} if k in ("reviews", "quarterly") else v)
                       for k, v in x.items() if "seconds" not in k}
    assert strip(r) == strip(again)                                                  # nothing in it is random


# ------------------------------------------------------------------ the runner

def test_the_runner_keeps_v2_records_apart_and_logs_the_hashes(tiny, tmp_path):
    with pytest.raises(SystemExit, match="pass --prereg v2"):
        run.run_scenario("D05h", "STD", 1, label="test", out=tmp_path, quiet=True)
    with pytest.raises(SystemExit, match="STD only"):
        run.run_scenario("D05h", "LONG", 1, label="test", out=tmp_path, quiet=True, prereg_version="v2")
    with pytest.raises(SystemExit, match="fewer than the pre-registered 400"):
        run.run_scenario("D05h", "STD", 1, out=tmp_path, quiet=True, prereg_version="v2", label="full")
    reps = run.run_scenario("D11", "STD", 1, label="test", out=tmp_path, quiet=True, prereg_version="v2")
    assert reps[0]["code"] == run.code_hash("STD", version="v2") and (tmp_path / "v2/reps/D11_STD_b0.jsonl").exists()
    run.run_scenario("D05h", "STD", 1, label="test", out=tmp_path, quiet=True, prereg_version="v2")
    run.run_scenario("D02", "HB", 1, label="test", out=tmp_path, quiet=True, prereg_version="v2")
    old = run.run_scenario("D05", "STD", 1, label="test", out=tmp_path, quiet=True, prereg_version="v2")
    assert old[0]["code"] == run.code_hash("STD") and (tmp_path / "reps/D05_STD_b0.jsonl").exists()   # unchanged: version 1
    assert sorted(p.name for p in (tmp_path / "v2/reps").iterdir()) == ["D02_HB_b0.jsonl", "D05h_STD_b0.jsonl", "D11_STD_b0.jsonl"]
    assert run.load_reps("D11", "STD", out=tmp_path) == [] and len(run.load_reps("D11", "STD", out=tmp_path, version="v2")) == 1
    log = runlog.read(tmp_path / "runs.jsonl")
    v2 = [r for r in log if r["options"].get("prereg_version") == "v2"]
    assert [r["scenario"] for r in v2 if r["event"] == "end"] == ["D11", "D05h", "D02"]
    assert all(r["options"]["prereg_v2_sha256"] == prereg_v2.prereg_v2_hash()
               and r["options"]["protocol_v31_sha256"] == prereg_v2.protocol_v31_hash() and r["prereg_sha256"] == SHA for r in v2)
    assert [r for r in log if r["scenario"] == "D05"][0]["options"].get("prereg_version") is None
    assert [r["options"]["required_replications"] for r in v2 if r["event"] == "start"] == [2000, 400, 400]
    # a second call continues, it does not repeat
    again = run.run_scenario("D11", "STD", 1, label="test", out=tmp_path, quiet=True, prereg_version="v2")
    assert len(again) == 1 and runlog.read(tmp_path / "runs.jsonl")[-1]["replications"]["completed"] == 0
    text, _ = run.status(tmp_path, prereg_version="v2")
    assert re.search(r"D11\s+STD\s+1\s+2000\s+v2", text) and re.search(r"D05h\s+STD\s+1\s+400\s+v2", text)
    assert re.search(r"D05\s+STD\s+1\s+2000\s+v1", text) and re.search(r"D02\s+HB\s+1\s+400\s+v2", text)
    assert "D05h" not in run.status(tmp_path)[0]                                     # version 1's table is version 1's
    # the report of the changed parts
    text, summary = report_v2.build(tmp_path)
    assert text.startswith("# Manhattan simulation, the parts changed by Protocol v3.1: PILOT report")
    assert "| D11 | 1 |" in text and "| D05h | 1 |" in text and "### D02 at HB" in text and "Held-out runs made: 0." in text
    assert set(summary["runs"]) == {"D11_STD", "D05h_STD", "D02_HB"} and "pipeline_rows" in summary["runs"]["D11_STD"]
    assert "### Dormancy under Protocol 3.1 §9.1" in text and "| D02 | 1 |" in text and set(summary["dormancy"]) == {"D02"}
    assert "### Who reaches Statistically supported, by true Sharpe ratio" in text and "all with a true edge" in summary["tier_power"]["D02"]
    assert all("pass" != r["verdict"] and "FAIL" != r["verdict"] for v in summary["runs"].values() for r in v["rows"])
    assert summary["cost"]["HB"]["runs"] == 5 and summary["cost"]["twin"]["runs"] == 9 and summary["cost"]["D11"]["runs"] == 1
    assert summary["cost"]["v1"]["runs"] == len([p for p in run.development_plan() if p[1] != "HB" and p[0] != "D11"])


# ------------------------------------------------------------------ metrics

def spa_rep(**kw) -> dict:
    base = {"n_reserve_null": 450, "m3_rw_den": 470, "n_families": 475, "seconds": 200.0, "mean_L": 5.0}
    for k, (hi, lo, tiny_, rw) in {"v31": (90, 22, 0, 23), "v30": (120, 36, 1, 36), "oracle": (92, 24, 0, 24)}.items():
        base.update({f"{k}_p0.2_num": hi, f"{k}_p0.05_num": lo, f"{k}_p0.001_num": tiny_, f"{k}_rw_num": rw,
                     f"{k}_pl05_num": lo + 2, f"{k}_pu05_num": lo, f"{k}_mean_B": 2500.0})
    base.update(kw)
    return base


def test_spa_rows_judge_the_hedge_aware_test_and_report_the_others(monkeypatch):
    reps = [spa_rep(**{"v31_p0.05_num": 22 + (i % 3)}) for i in range(30)]
    rows = {r.what: r for r in metrics_v2.summarise_spa(reps, "D11")}
    aware = rows["hedge-aware test (3.1): SPA size at 0.05"]
    assert aware.estimate == pytest.approx(23 / 450) and aware.criterion == "V3" and aware.required
    assert aware.threshold == "upper bound ≤ 0.06" and aware.verdict.startswith("pilot: not decided")
    old = rows["3.0 test on the estimated hedge: SPA size at 0.05"]
    assert old.estimate == pytest.approx(0.08) and old.verdict == "reported" and not old.required and old.threshold == ""
    assert rows["3.0 test on the true hedged returns (oracle): SPA size at 0.2"].estimate == pytest.approx(92 / 450)
    assert rows["hedge-aware test (3.1): SPA size at 0.001 (pooled)"].kind == "ratio"
    diff = rows["paired difference at 0.05: hedge-aware test (3.1) minus the oracle"]
    assert diff.estimate == pytest.approx(-1 / 450) and diff.lo < diff.estimate < diff.hi
    assert rows["paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge"].estimate \
        == pytest.approx(-13 / 450)
    assert not any(r.metric == "precision" for r in rows.values())                  # D11 runs to version 1's 2,000
    monkeypatch.setitem(criteria.REPLICATIONS, "STD", 30)                           # at its count the same numbers are decided
    full = {r.what: r for r in metrics_v2.summarise_spa(reps, "D11")}
    assert full[aware.what].verdict == "pass" and full[old.what].verdict == "reported"
    bad = {r.what: r for r in metrics_v2.summarise_spa([spa_rep(**{"v31_p0.05_num": 36}) for _ in range(30)], "D11")}
    assert bad[aware.what].verdict == "FAIL"


def test_a_twin_is_decided_only_at_400_replications_and_the_precision_target(monkeypatch):
    few = [spa_rep(**{"v31_p0.05_num": 22 + (i % 3)}) for i in range(30)]
    rows = {r.what: r for r in metrics_v2.summarise_spa(few, "D05h")}
    assert rows["hedge-aware test (3.1): SPA size at 0.05"].verdict.startswith("pilot")
    assert rows["95% half-width of the hedge-aware size at 0.05"].verdict == "pilot"
    monkeypatch.setattr(criteria_v2, "REPLICATIONS_TWIN", 30)
    rows = {r.what: r for r in metrics_v2.summarise_spa(few, "D05h")}
    assert rows["hedge-aware test (3.1): SPA size at 0.05"].verdict == "pass"
    assert rows["95% half-width of the hedge-aware size at 0.05"].verdict == "met"
    wild = [spa_rep(**{"v31_p0.05_num": 0 if i % 2 else 45}) for i in range(30)]      # half-width 0.018 > 0.01
    rows = {r.what: r for r in metrics_v2.summarise_spa(wild, "D05h")}
    assert rows["95% half-width of the hedge-aware size at 0.05"].verdict == "not met: continue the run"
    assert rows["hedge-aware test (3.1): SPA size at 0.05"].verdict.startswith("pilot")      # not decided until it is met
    assert criteria_v2.TWIN_HALF_WIDTH_MAX == {0.20: 0.02, 0.05: 0.01}


def hb_rep(ok=True) -> dict:
    def review():
        r = {"ok": [ok] * 6, "edge_mass": [0.0 if ok else 0.4] * 6, "fit_seconds": [1.0] * 6, "six_fits_seconds": 6.0,
             "grid_points": [200] * 6, "n_live": 100, "r_F": 0.05, "review_ok": ok,
             "hyper": {"mu_A": 0.05, "tau_A": 0.1, "psi": 1.06, "nu": 0.1, "rho_0": 0.4, "rho_1": 0.5, "rho_2": 0.45}}
        if ok:
            r.update({"n_eval": 100, "n_edge": 10, "pimin80_n": 5, "pimin80_true": 4, "pimin40_n": 12, "pimin40_true": 6,
                      "cal_n": [80, 5, 3, 2, 2, 2, 1, 1, 2, 2], "cal_true": [2, 1, 1, 1, 1, 1, 1, 1, 2, 2],
                      "cal_p": [4.0, 0.75, 0.75, 0.7, 0.9, 1.1, 0.65, 0.75, 1.7, 1.9]})
            for c in ("i", "ii"):
                for g in ("prom", "supp"):
                    r.update({f"m9_{g}_{c}_n": 6, f"m9_{g}_{c}_model": -0.3, f"m9_{g}_{c}_naive": 3.0})
        return r

    r = {"model": hb_v2.MODEL, "eval_years": [2, 4, 7, 10], "seconds": 80.0, "model_seconds": 30.0, "forecast_seconds": 4.0,
         "reviews": {str(y): review() for y in (2, 4, 7, 10)}, "n_families": 240, "family_reviews": 400,
         "dormancy": dormancy.RULE, "review_step": hb_v2.REVIEW_STEP, "review_days": hb_v2.review_days(),
         "quarterly": {"ok": [ok] * 40, "edge_mass": [0.0 if ok else 0.4] * 40, "n_live": [10] * 40,
                       "six_fits_seconds": [6.0] * 40, "r_F": [0.05] * 40},
         "reviews_not_computed": 0 if ok else 40,
         # ten families with a true edge: Sharpe ratio, freeze day, and the first date each held the tier (0: never)
         "edge_true": [0.3, 0.3, 0.4, 0.6, 0.6, 0.9, 1.2, 1.2, 1.6, 2.0],
         "edge_freeze": [0, 600, 1300, 0, 1300, 0, 0, 2000, 0, 600]}
    for c in ("i", "ii"):
        r.update({f"m8_den_{c}": 10, f"m8_num_{c}": 1, f"screened_{c}": 2, f"end_promising_{c}": 3,
                  f"end_supported_{c}": 1, f"end_dormant_{c}": 50, f"null_dormant_{c}": 49, f"written_{c}": 330,
                  f"edge_first_supported_day_{c}": [0, 0, 0, 0, 0, 2520, 1701, 0, 945, 1008],   # the day of the first review in the tier
                  f"edge_dormant_end_{c}": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0]})
        for y, v in r["reviews"].items():
            v.update({f"written_{c}": 90, f"dormant_{c}": 0 if y == "2" else 50})
    return r


def test_attention_and_tier_power_are_counted_from_the_records():
    reps = [hb_rep() for _ in range(8)]
    att = metrics_v2.attention(reps)
    assert att["family_reviews"] == 400 and att["written"][0] == 330 and att["dormant_end"][0] == 50
    assert att["null_dormant_share"][0] == pytest.approx(49 / 230) and att["edge_dormant_share"][0] == pytest.approx(0.1)
    pw = metrics_v2.tier_power(reps)
    assert list(pw) == ["0.25 to 0.5", "0.5 to 0.75", "0.75 to 1", "1 to 1.5", "1.5 and above", "all with a true edge"]
    # a family counts once it is frozen (day 600 is after year 2, day 1300 after year 4, day 2000 after year 7)
    assert [pw["0.25 to 0.5"][y][3] for y in (2, 4, 7, 10)] == [8, 16, 24, 24]
    assert all(pw["0.25 to 0.5"][y][0] == 0 for y in (2, 4, 7, 10))                 # the weakest never hold the tier
    assert [pw["1.5 and above"][y][0] for y in (2, 4, 7, 10)] == [0.0, 1.0, 1.0, 1.0]
    assert [pw["1.5 and above"][y][3] for y in (2, 4, 7, 10)] == [8, 16, 16, 16]
    assert [pw["1 to 1.5"][y][0] for y in (4, 7, 10)] == [0.0, 1.0, 0.5]           # the one frozen in year 8 never enters
    assert pw["0.75 to 1"][10][0] == 1.0 and pw["0.75 to 1"][7][0] == 0.0
    assert pw["all with a true edge"][10][0] == pytest.approx(0.4) and pw["all with a true edge"][10][3] == 80
    rows = {r.what: r for r in metrics_v2.summarise_hb(reps, "D02")}
    assert rows["dormancy rule"].verdict == dormancy.RULE
    assert rows["attention: reviews written per replication, candidate (i) (of 400 family-reviews; a family dormant before "
                "and after a date needs none)"].estimate == 330
    assert rows["year 7: families dormant after the review / reviews written / families evaluated (means), candidate (i)"].verdict \
        == "50.0 / 90.0 / 100.0"
    # records that kept the year of entry instead of the day (four review dates) give the same table
    by_year = [{**{k: v for k, v in r.items() if "first_supported_day" not in k},
                **{f"edge_first_supported_{c}": [0, 0, 0, 0, 0, 10, 7, 0, 4, 4] for c in ("i", "ii")}} for r in reps]
    assert metrics_v2.tier_power(by_year) == pw
    # records made before the fields existed are still summarised: the new rows are simply absent
    old = [{k: v for k, v in r.items() if not k.startswith(("edge_", "written_", "null_dormant_", "family_reviews", "dormancy",
                                                            "quarterly", "review_", "reviews_not", "forecast_"))}
           for r in reps]
    assert metrics_v2.attention(old) == {} and metrics_v2.tier_power(old) == {}
    assert "dormancy rule" not in {r.what for r in metrics_v2.summarise_hb(old, "D02")}


def test_hb_rows_are_version_1s_verdicts_plus_the_grid_gate(monkeypatch):
    reps = [hb_rep() for _ in range(60)]
    rows = {r.what: r for r in metrics_v2.summarise_hb(reps, "D01")}
    gate = rows["reviews not computed (a fit fails the grid gate), of 2400"]             # 60 replications of 40 reviews each
    assert rows["review calendar"].verdict == "a review every 63 trading days (40 reviews a replication); M7 and M9 read at years 2, 4, 7, 10"
    assert gate.metric == "M12" and gate.estimate == 0 and gate.criterion == "V12" and gate.verdict.startswith("pilot")
    share = rows["year 4: share with a true edge among families with Π^min ≥ 0.8 (300 family observations)"]
    assert share.estimate == pytest.approx(0.8) and share.threshold == "lower bound ≥ 0.7" and share.verdict.startswith("pilot")
    assert rows["premature elimination: families with a true edge that end dormant, candidate (i)"].threshold == "upper bound ≤ 0.1"
    assert not any("R-hat" in w or "sampler" in w or "converged" in w for w in rows)           # nothing is sampled
    assert rows["year 10: seconds for the six fits of a review (100 families)"].estimate == 6.0
    assert rows["seconds per replication spent on the model (estimates, six fits at every review, forecasts)"].estimate == 30.0
    assert rows["of which the dormancy forecasts"].estimate == 4.0
    assert rows["seconds for the six fits of a review, mean over every review"].estimate == 6.0
    assert rows["model"].verdict == hb_v2.MODEL
    monkeypatch.setitem(criteria.REPLICATIONS, "HB", 60)
    full = {r.what: r for r in metrics_v2.summarise_hb(reps, "D01")}
    assert full[gate.what].verdict == "pass" and full[share.what].verdict == "pass"
    broken = [hb_rep() for _ in range(59)] + [hb_rep(ok=False)]
    bad = {r.what: r for r in metrics_v2.summarise_hb(broken, "D01")}
    assert bad[gate.what].estimate == 40 and bad[gate.what].verdict == "FAIL"                  # one is one too many
    # a single review of the 2,400 that is not computed, between two dates at which M7 is read, fails V12 as well
    one = [hb_rep() for _ in range(60)]
    one[17]["quarterly"]["ok"][11] = False
    late = {r.what: r for r in metrics_v2.summarise_hb(one, "D01")}
    assert late[gate.what].estimate == 1 and late[gate.what].verdict == "FAIL"


def test_records_of_another_review_step_are_refused(tmp_path):
    """SIM_PREREG_v2 amendment 1: the step is in every record, and records of another calendar are never pooled."""
    good = hb_rep()
    hb_v2.require_review_step([good, good])
    for bad in ({**good, "review_step": 252}, {k: v for k, v in good.items() if k != "review_step"}):
        with pytest.raises(ValueError, match="not every 63: refused"):
            hb_v2.require_review_step([good, bad], "D02 at HB")
    # the report counts only records made at the pre-registered step, whatever code hash they carry
    path = run.reps_path("D02", "HB", seeds.DEVELOPMENT, tmp_path, "v2")
    path.parent.mkdir(parents=True)
    code = run.code_hash("HB", version="v2")
    rows = [{**hb_rep(), "rep": 0, "code": code}, {**hb_rep(), "rep": 1, "code": code, "review_step": 252},
            {**{k: v for k, v in hb_rep().items() if k != "review_step"}, "rep": 2, "code": "an-older-code"}]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    found = report_v2.collect(tmp_path)
    assert [r["rep"] for r in found[("D02", "HB")]["reps"]] == [0] and found[("D02", "HB")]["other_code_reps"] == 2
    path.write_text(json.dumps(rows[2]) + "\n", encoding="utf-8")                   # only records of another calendar on file
    assert ("D02", "HB") not in report_v2.collect(tmp_path)


def test_the_report_shows_the_small_sample_interval_beside_premature_elimination(tmp_path):
    """On a pilot "0.000 (0.000 to 0.000)" means no event in the replications run. The report prints beside it the
    interval with the replication as the unit: the exact bound over replications when no replication had an event."""
    code = run.code_hash("HB", version="v2")
    for scenario, gone in (("D02", 0), ("D05", 1)):
        path = run.reps_path(scenario, "HB", seeds.DEVELOPMENT, tmp_path, "v2")
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{**hb_rep(), "rep": k, "code": code, "scenario": scenario, "m8_num_i": gone if k % 2 else 0} for k in range(12)]
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    text, summary = report_v2.build(tmp_path)
    d02, d05 = summary["dormancy"]["D02"], summary["dormancy"]["D05"]
    assert (d02["retired"], d02["n_edge"], d02["m8"][0]) == (0, 120, 0.0)
    assert d02["m8_small_sample"] == pytest.approx((0.0, 1 - 0.025 ** (1 / 12)))      # 0.265, above the bound of 0.10
    assert "| D02 | 12 | 120 | 0 | 0.000 (0.000 to 0.000) | **0.000 (0.000 to 0.265)** |" in text
    # with events in some replications: the jackknife standard error and a Student-t quantile on 11 degrees of freedom
    lo, hi = d05["m8_small_sample"]
    assert d05["retired"] == 6 and d05["m8"][0] == pytest.approx(0.05) and lo < d05["m8"][1] <= 0.05 <= d05["m8"][2] < hi
    assert "**the same, small-sample interval**" in text and "not a rate of zero" in text


# ------------------------------------------------------------------ the text

@reads_hand_edited_file
def test_v2_adds_requirements_and_loosens_no_threshold():
    """Every number of version 1 is the object version 2 uses, and the numbers written in SIM_PREREG_v2.md are
    those numbers."""
    for name in ("V3_SIZE_MAX", "V3_FWER_MAX", "V6_SHARE_MIN", "V6_ECE_MAX", "V6_D01_HIGH_MAX", "V7_ELIM_MAX",
                 "V7_LATE_MAX", "V8_BIAS_MAX", "V8_BIAS_MIN", "REPLICATIONS"):
        assert getattr(criteria_v2, name) is getattr(criteria, name) or getattr(criteria_v2, name) == getattr(criteria, name)
    assert criteria_v2.REPLICATIONS is criteria.REPLICATIONS == {"STD": 2000, "LONG": 2000, "HB": 400}
    assert set(criteria.V3_REQUIRED) < set(criteria_v2.V3_REQUIRED)                 # a strict superset: nothing removed
    assert set(criteria_v2.V3_REQUIRED) - set(criteria.V3_REQUIRED) == set(criteria_v2.TWINS) | {"H12"}
    assert criteria_v2.replications("D05h", "STD") == 400 and criteria_v2.replications("D11", "STD") == 2000
    assert criteria_v2.V12_REVIEWS_NOT_COMPUTED_MAX == 0 and criteria_v2.EDGE_MASS_MAX == hier_analytic.EDGE_MASS_MAX
    text = (ROOT / "docs/manhattan/SIM_PREREG_v2.md").read_text(encoding="utf-8")

    def row(vid):
        m = re.search(rf"^\| {re.escape(vid)} \|(.*)$", text, re.M)
        assert m, vid
        return m.group(1)

    v3 = row("V3")
    assert all(f"**{x}**" in v3 for x in ("0.22", "0.06", "0.0015")) and v3.count("**0.06**") == 2
    assert all(t in v3 for t in criteria_v2.TWINS) and "H12" in v3
    v678 = row("V6, V7, V8")
    assert all(f"**{x}**" in v678 for x in ("0.70", "0.30", "0.10", "0.01", "0.25", "+0.10", "−0.25"))
    assert "**0**" in row("V12") and "bit-for-bit identical" in row("V13") and "**no** output" in row("V14")
    assert "**Every threshold of version 1.0 stands, with its number.** None is loosened." in text
    assert "**2,000** for D11 and H12 (STD), **400** for every HB scenario. None is lowered." in text
    assert "**Hedged twins: 400, then as many more as the precision target needs.**" in text
    assert "at most 0.02 at the 0.20 level and 0.01 at the 0.05 level" in text
    assert ", ".join(criteria_v2.TWINS) in text and "| H12 |" in text
    assert "D11, D09b and D10 are development scenarios" in text and "It is\nnot coded." in text
    for needle in ("756 actual days", "199 resamples", "63 forward days", "At most 1% of the posterior mass",
                   "200 draws", "floored at 0 and capped at 0.9"):
        assert needle in text, needle
    assert hb.SE_RESAMPLES == 199 and hb.MIN_FWD_DAYS == 63 and hb.PP_DRAWS == 200
    # the dormancy rule of Protocol 3.1 section 9.1, as the code applies it; V7's number is version 1's
    assert ("a family becomes dormant when `PP^max < 0.05` and `p^F < 0.05` at two\n  consecutive dates, and is "
            "reactivated when either is at least 0.15") in text
    assert "`p^F = Φ((y^F_f − θ_min)/s^F_f)`" in text and "at least 252 forward days" in text
    assert (dormancy.DORMANT_BELOW, dormancy.MIN_FORWARD_DAYS, dormancy.REACTIVATE_AT, dormancy.THETA_MIN) == (0.05, 252, 0.15, 0.25)
    assert criteria_v2.V7_ELIM_MAX is criteria.V7_ELIM_MAX or criteria_v2.V7_ELIM_MAX == criteria.V7_ELIM_MAX == 0.10
    # amendment 1: quarterly reviews in the HB runs; a tightening, written into the text and into the code
    amend = text[text.index("## 11. Amendment 1, made before adoption (2026-11-13)"):]
    for needle in ("**Reviews every 63 trading days**", "**40 reviews**", "**M7 and M9 are read at years 2, 4, 7 and 10**",
                   "**M12 is counted over all 40 reviews**", "**The review step is written into every replication record.**",
                   "`manhattan/sim/hb.py` and `manhattan/stats/tiers.py`", "**Why it tightens and never loosens.**",
                   "No threshold moves."):
        assert needle in amend, needle
    assert hb_v2.REVIEW_STEP == 63 and len(hb_v2.review_days()) == 40 and world.YEAR % hb_v2.REVIEW_STEP == 0
    assert "over all 40 reviews of every replication (amendment 1)" in row("V12")
    assert "**counted over all 40 reviews**" in row("M12") and "Reduction (c)" in text
    assert "for that change **no threshold, metric,\nscenario or replication count was touched**" in text
    assert "Sections 4, 6.1 to 6.10, 8.1 and 8.2 of the protocol, and\nsections 9.2 and 9.3, are identical in the two versions." in text
    assert "**no** e-LOND rejection, bar or count changes with the outcome of the check" in row("V15")
    assert "- **A run made in pieces.**" in text and "`python -m manhattan.sim.collect`" in text
    assert "V7 as it stands (M8 and its bound of 0.10 are version 1.0's, unchanged)" in text


@reads_hand_edited_file
def test_protocol_31_keeps_every_constant_of_30_and_says_what_changed():
    old = (ROOT / "docs/manhattan/PROTOCOL_v3.md").read_text(encoding="utf-8")
    new = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    assert "Version **3.1.0**" in new and "Version **3.0.0**" in old
    assert new.index("## What changed from 3.0.0, and why") < new.index("## 1. Symbols")       # the change log is at the top
    for needle in ("D11", "0.077 (0.061 to 0.094)", "50,000 CPU-hours", "D09b", "0.344 (0.307 to 0.380)",
                   "Wording only; no rule changed", "why it is not tuning to held-out results"):
        assert needle in new[: new.index("## 1. Symbols")], needle
    # sections the pilot gave no reason to touch are word for word those of 3.0.0
    def section(text, start, end):
        a = text.index(start)
        return text[a:text.index(end, a)]
    for start, end in (("## 4. Across-family screening", "## 5. Within a family"),
                       ("## 8. Tiers", "### 8.3 Live-experiment eligible"), ("### 9.2 The cost", "## 10. Governance"),
                       ("## Appendix A. Proofs", "## Appendix B.")):
        assert section(new, start, end) == section(old, start, end), start
    # section 6: 6.1 to 6.10 are 3.0's word for word; 6.11 (the tail-risk check, change 6) is added after them
    assert section(new, "## 6. Forward e-process", "### 6.11 The tail-risk check") == \
        section(old, "## 6. Forward e-process", "---\n\n## 7. One hierarchical model")
    assert "### 6.11" not in old and new.index("### 6.10 Within") < new.index("### 6.11 The tail-risk check") < new.index("## 7. One")
    # sections 8.3 to 8.5 are 3.0's with the check named once in each, and nothing else
    live31, live30 = section(new, "### 8.3 Live-experiment eligible", "## 9. Dormancy"), section(old, "### 8.3 Live-experiment eligible", "## 9. Dormancy")
    for added in ("the tail-risk check of section 6.11 holds; ", "; the tail-risk check of section 6.11 holds",
                  ", **and** the tail-risk check of section 6.11",
                  "The rejection is recorded and counted from its date whatever the tail-risk check says; only the label waits for\n"
                  "the check. A rejected family that does not meet it is reported as \"e-LOND rejection on record; label withheld\n"
                  "(tail-risk check, section 6.11)\", at every review at which that is so.\n\n"):
        assert live31.count(added) == 1, added
        live31 = live31.replace(added, "")
    assert live31 == live30
    # section 9.1 is the one rule changed before adoption (change 5): the forecast is kept, with 3.0's levels, and
    # a test of the family's own forward record is added; what 3.0 said about the forecast and about a dormant
    # family still stands, and sections 9.2 and 9.3 are 3.0's word for word (the loop above)
    rule30, rule31 = section(old, "### 9.1 The rule", "### 9.2 The cost"), section(new, "### 9.1 The rule", "### 9.2 The cost")
    assert "| **Become dormant** | `PP_f^max < 0.05` at two consecutive reviews |" in rule30
    assert "| **Become dormant** | `PP_f^max < 0.05` **and** `p^F_f < 0.05`, both at two consecutive reviews |" in rule31
    for line in rule30.splitlines():
        if line.startswith(("PP_f = Pr(", "| **While dormant**", "With `programme.end` unset")):
            assert line in rule31, line
    top = new[: new.index("## 1. Symbols")]
    assert "| 5 | §9.1" in top and "**pre-adoption change**" in top and "D02, D05,\nD08 and D10 are development scenarios" not in top
    assert "D08 and D10 are development scenarios" in top.replace("\n", " ")
    assert "| 3.1.0, revised before adoption | 2026-11-12 |" in new and "| 3.1.0, pre-adoption change | 2026-11-13 |" in new
    # every row of 3.0's table of constants is still there
    consts = section(old, "## Appendix B. Constants fixed in v3.0", "## Appendix C.")
    for line in consts.splitlines():
        if line.startswith("| `") or line.startswith("| scale") or line.startswith("| test") or line.startswith("| variance"):
            assert line in new, line
    # the two wording fixes of ETHAN_ACTIONS item 14, and the stale sentence of Appendix C
    assert "the latter being White's reality check" not in new and "This is the \"consistent\" p-value of Hansen (2005)." not in new
    assert "the p-value counts ties and adds one, which can only\nmake it larger than Hansen's" in new
    assert "the least-favourable null of White's reality check applied to the studentised statistic" in new
    assert "written from\nmemory" not in new and "written from memory" not in new
    assert "| 3.1.0 | 2026-11-12 |" in new and "| 3.0.0 | 2026-11-12 | first committed version" in new


# ------------------------------------------------------------------ the run package

def test_the_run_script_runs_v2_for_the_changed_parts():
    text = (ROOT / "scripts/manhattan_sim_run.sh").read_text(encoding="utf-8")
    assert 'PREREG="${PREREG:-v2}"' in text and '--prereg "$PREREG"' in text         # version 2 unless told otherwise
    assert "manhattan.prereg verify" in text and "manhattan.prereg_v2 verify" in text
    assert "manhattan.sim.report --out" in text and "manhattan.sim.report_v2 --out" in text
    assert "--plan development" in text and "--confirm" not in text and "set -euo pipefail" in text
    assert 'SIZES="${SIZES:-STD,LONG,HB}"' in text and "--reps-twin" in text         # the model half is now part of the run
    plist = (ROOT / "scripts/com.horizons.manhattan.sim.plist.template").read_text(encoding="utf-8")
    assert "<string>STD,LONG,HB</string>" in plist and "<key>PREREG</key><string>v2</string>" in plist
