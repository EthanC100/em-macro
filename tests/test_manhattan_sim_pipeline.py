"""The simulation pipeline, its metrics and its runner (manhattan/sim/): criteria C-15, C-16 and the mechanics of
C-17 in docs/manhattan/MANHATTAN_PROGRESS.md. Synthetic data only.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from manhattan.sim import criteria, metrics, pipeline, run, runlog, seeds, world
from manhattan.stats import schedule

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/manhattan/SIM_PREREG.md").read_text(encoding="utf-8")
TINY = world.Size("STD", 3, 4, 5, 2, 3, 4, 6)


@pytest.fixture
def tiny(monkeypatch):
    monkeypatch.setitem(world.SIZES, "STD", TINY)
    return TINY


# ------------------------------------------------------------------ C-16: V10(a)

@pytest.mark.parametrize("scenario", ["D09a", "D09b"])
def test_blind_statistics_are_bit_for_bit_identical_with_and_without_the_adaptive_channel(scenario, tiny):
    scn = world.SCENARIOS[scenario]
    p1, e1 = pipeline.designated_statistics(scn, scenario, "STD", 0, max_batches=2)
    p0, e0 = pipeline.designated_statistics(world.without_adaptive(scn), scenario, "STD", 0, max_batches=2)
    assert p1.size >= 8 and np.array_equal(p1, p0) and np.array_equal(e1, e0)
    assert np.all((p1 > 0) & (p1 <= 1)) and np.all(e1 > 0)


def test_adaptive_test_is_only_computed_in_d09b(tiny):
    r = pipeline.run_replication("D09b", "STD", 0)
    assert r["m11_den"] > 0 and 0 <= r["m11_num"] <= r["m11_den"]
    assert "m11_den" not in pipeline.run_replication("D09a", "STD", 0)


# ------------------------------------------------------------------ pipeline pieces

def fake_eval(idx, freeze, *, passed=True, forward_null=True, growth=0.0, weeks=None, reserve_null=True, batch=0):
    """A family whose three components all earn ``growth`` log-wealth a week at every bet size."""
    weeks = weeks if weeks is not None else (world.T_END - freeze) // world.WEEK
    cum = np.zeros((3, 6, weeks + 1))
    cum[:] = growth * np.arange(weeks + 1)
    Z = np.full((3, weeks), 1.0 if growth > 0 else 0.0) + 0.01 * np.sin(np.arange(weeks))
    return pipeline.FamilyEval(idx=idx, batch=batch, freeze=freeze, reserve_null=reserve_null, forward_null=forward_null,
                               has_edge=not forward_null, true_sharpe_f=0.0, p_c=0.5, p_l=0.5, p_u=0.5, B=999, L=5.0,
                               E=1.0, no_edge=np.ones(6, bool), rw05=np.zeros(6, bool), comp_null=np.ones(3, bool),
                               cum_fwd=cum, Z_fwd=Z, track_max=np.ones(3), passed={"i": passed, "ii": passed},
                               admission={"i": 0.01, "ii": 0.01}, rw_adm_null={"i": False, "ii": False},
                               rw_adm_any={"i": False, "ii": False})


def test_enrolment_is_at_the_first_review_on_or_after_the_freeze():
    evs = [fake_eval(0, 0), fake_eval(1, 60), fake_eval(2, 125), fake_eval(3, 130), fake_eval(4, 60, passed=False)]
    got = pipeline.enrolment(evs, "i")
    # reviews are days 63, 126, 189: first test weeks 13 (day 65), 13, 26 (day 130), 38 (day 190)
    assert [(w, e.idx) for w, e in got] == [(13, 0), (13, 1), (26, 2), (38, 3)]
    all_ = pipeline.enrolment(evs, None)
    assert [(w, e.idx) for w, e in all_] == [(0, 0), (12, 1), (12, 4), (25, 2), (26, 3)]      # at freeze, ties by ID


def test_forward_test_rejects_a_growing_family_after_the_guard_and_the_lag():
    bar = 1 / (0.05 * schedule.gamma(1, 120))
    g = 0.2
    strong, flat = fake_eval(0, 0, forward_null=False, growth=g), fake_eval(1, 0)
    out = pipeline.forward_test([strong, flat], "i", 120)
    need = math.ceil(math.log(bar) / g)                    # weeks of growth to reach the bar
    first_possible = max(need, 52)                          # and the guard needs 52 weeks
    assert need < 52 and out["reject_day"][1] == -1
    week = 13 + first_possible - 1                          # test starts at week 13; rejected on its 52nd test week
    assert out["reject_day"][0] == 5 * (week + 1 + pipeline.LAG_WEEKS)
    late = fake_eval(2, 2400, forward_null=False, growth=5.0)
    assert pipeline.forward_test([late], "i", 120)["reject_day"][0] == -1     # fewer than 52 weeks left: no guard


def test_forward_and_screening_counts_in_the_replication_summary():
    scn, size = world.SCENARIOS["D02"], world.SIZES["STD"]
    evs = [fake_eval(0, 0, forward_null=False, growth=0.2, reserve_null=False),
           fake_eval(1, 0, forward_null=True, growth=0.2),               # a false forward discovery
           fake_eval(2, 0, passed=False), fake_eval(3, 1260, forward_null=False, growth=0.0, reserve_null=False, batch=20)]
    fw = {c: pipeline.forward_test(evs, c, size.N_F) for c in pipeline.CANDIDATES}
    s = pipeline.summarise(evs, scn, size, fw)
    assert s["n_families"] == 4 and s["n_reserve_null"] == 2
    assert s["scr_rej_i_b10"] == 2 and s["scr_false_i_b10"] == 1 and s["m1_i_b10"] == 0.5
    assert s["scr_rej_i_b40"] == 3 and s["m1_i_b40"] == pytest.approx(1 / 3)
    assert s["m6_scr_den"] == 2 and s["m6_scr_num_i"] == 2
    assert s["fwd_enrolled_i"] == 3 and s["fwd_rej_i_y3"] == 2 and s["m2_i_y3"] == 0.5 and s["fwd_false_i_y10"] == 1
    assert s["m6_fwd_den_i"] == 1 and s["m6_fwd_num_i"] == 1         # first-quarter families that are not forward-null
    assert len(s["m6_fwd_years_i"]) == 1 and 1.0 < s["m6_fwd_years_i"][0] < 1.5
    assert s["m5_den"] == 12 and s["m5_20_num"] == 0


def test_one_replication_end_to_end_is_reproducible(tiny):
    a = pipeline.run_replication("P4", "STD", 0)
    b = pipeline.run_replication("P4", "STD", 0)
    for k in a:
        if k != "seconds":
            assert a[k] == b[k], k
    assert a != pipeline.run_replication("P4", "STD", 1) and a["n_families"] >= 12
    assert "fwd_enrolled_all" in pipeline.run_replication("D01", "STD", 0)
    assert "fwd_enrolled_all" not in a


# ------------------------------------------------------------------ runner: resumable, logged

def test_runner_continues_a_run_and_logs_every_call(tiny, tmp_path):
    first = run.run_scenario("D01", "STD", 2, label="test", out=tmp_path, quiet=True)
    assert [r["rep"] for r in first] == [0, 1]
    more = run.run_scenario("D01", "STD", 3, label="test", out=tmp_path, quiet=True)
    assert [r["rep"] for r in more] == [0, 1, 2]
    lines = (tmp_path / "reps/D01_STD_b0.jsonl").read_text().splitlines()
    assert len(lines) == 3                                              # the first two were not run again
    assert all(json.loads(l)["code"] == run.code_hash("STD") for l in lines)
    log = runlog.read(tmp_path / "runs.jsonl")
    assert [(r["event"], r["status"]) for r in log] == [("start", "started"), ("end", "completed")] * 2
    assert log[0]["options"]["to_run"] == 2 and log[2]["options"] == {**log[2]["options"], "already_on_file": 2, "to_run": 1}
    assert log[1]["replications"]["completed"] == 2 and log[3]["replications"]["completed"] == 1
    assert log[0]["label"] == "test" and log[0]["options"]["required_replications"] == 2000
    assert run.load_reps("D01", "STD", out=tmp_path, code="other") == []      # another code's results are never pooled


def test_a_failed_run_is_logged_as_failed(tiny, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(pipeline, "run_replication", boom)
    with pytest.raises(RuntimeError):
        run.run_scenario("D01", "STD", 1, label="test", out=tmp_path, quiet=True)
    log = runlog.read(tmp_path / "runs.jsonl")
    assert [r["status"] for r in log] == ["started", "failed"] and "synthetic failure" in log[1]["reason"]


def test_development_plan_is_every_scenario_at_every_listed_size():
    plan = run.development_plan()
    assert len(plan) == 23 and len(set(plan)) == 23
    assert ("D01", "STD") in plan and ("D01", "LONG") in plan and ("D10", "HB") in plan and ("D03", "LONG") not in plan
    assert not any(world.is_heldout(s) for s, _ in plan)


# ------------------------------------------------------------------ C-15: intervals, thresholds, verdicts

def test_mean_interval_is_mean_plus_or_minus_196_sd_over_root_r():
    v = np.array([0.0, 0.2, 0.4, 0.2, 0.2])
    m, lo, hi = metrics.mean_ci(v)
    half = 1.96 * v.std(ddof=1) / math.sqrt(5)
    assert (m, lo, hi) == pytest.approx((0.2, 0.2 - half, 0.2 + half))


def test_ratio_interval_resamples_whole_replications():
    num, den = np.array([1, 0, 3, 2, 0, 4]), np.array([10, 10, 10, 10, 0, 10])
    est, lo, hi = metrics.ratio_ci(num, den)
    assert est == pytest.approx(10 / 50) and lo < est < hi and lo >= 0 and hi <= 0.4
    same = metrics.ratio_ci(np.full(50, 2), np.full(50, 10))
    assert same == pytest.approx((0.2, 0.2, 0.2))                       # no variation between replications
    assert all(math.isnan(x) for x in metrics.ratio_ci(np.zeros(3), np.zeros(3)))
    assert criteria.BOOTSTRAP_RESAMPLES == 2000


def rep(**kw):
    base = {"n_families": 480, "n_reserve_null": 460, "seconds": 1.0, "mean_B": 999, "bet_rate": 0.97, "n_trunc": 0,
            "m6_scr_den": 20, "m3_rw_den": 480, "m3_rw_num": 20, "m3_p0.2_num": 92, "m3_p0.05_num": 23,
            "m3_p0.001_num": 0, "m3_pl05_num": 25, "m3_pu05_num": 22, "m5_den": 1440, "m5_20_num": 30, "m5_100_num": 5}
    for c in ("i", "ii"):
        base.update({f"m1_{c}_b{k}": 0.1 for k in (10, 20, 40)})
        base.update({f"m2_{c}_y{y}": 0.0 for y in (3, 5, 10)})
        base.update({f"m4_{c}": 0.05, f"m4_n_{c}": 10, f"m6_scr_num_{c}": 12, f"fwd_enrolled_{c}": 12,
                     f"m6_fwd_den_{c}": 5, f"m6_fwd_num_{c}": 2, f"m6_fwd_years_{c}": [4.0, 6.0]})
    base.update(kw)
    return base


def test_summary_rows_carry_thresholds_and_a_pilot_is_never_decided(monkeypatch):
    reps = [rep() for _ in range(30)]
    rows = metrics.summarise(reps, "D01", "STD")
    by = {r.what: r for r in rows}
    r = by["screening FDR, candidate (i), batch 40"]
    assert r.metric == "M1" and r.criterion == "V1" and r.required and r.threshold == "upper bound ≤ 0.22"
    assert r.estimate == pytest.approx(0.1) and r.verdict.startswith("pilot: not decided")
    assert all("pass" != x.verdict and "FAIL" != x.verdict for x in rows)
    assert by["SPA size at 0.05"].estimate == pytest.approx(23 / 460) and by["SPA size at 0.05"].threshold == "upper bound ≤ 0.06"
    assert by["SPA size at 0.001 (pooled)"].kind == "ratio" and by["SPA size at 0.001 (pooled)"].n == 460 * 30
    assert by["null component wealth ever reaches 20"].estimate == pytest.approx(30 / 1440)
    assert "not evaluated" not in by["linked average error, candidate (i) (300 families passed)"].verdict
    assert by["median years from freeze to formal support, enrolment by candidate (i)"].estimate == 5.0
    few = metrics.summarise([rep() for _ in range(10)], "D01", "STD")
    link = [x for x in few if x.metric == "M4"][0]
    assert link.verdict == "not evaluated: fewer than 200 observations"            # 100 passed families
    # at the pre-registered count the same numbers are decided
    monkeypatch.setitem(criteria.REPLICATIONS, "STD", 30)
    full = {x.what: x for x in metrics.summarise(reps, "D01", "STD")}
    assert full["screening FDR, candidate (i), batch 40"].verdict == "pass"
    bad = {x.what: x for x in metrics.summarise([rep(m1_i_b40=0.3) for _ in range(30)], "D01", "STD")}
    assert bad["screening FDR, candidate (i), batch 40"].verdict == "FAIL"
    power = full["screening power, candidate (i)"]
    assert power.estimate == pytest.approx(0.6) and not power.required and power.verdict.startswith("reported")
    assert {x.what: x for x in metrics.summarise(reps, "P4", "STD")}["screening power, candidate (i)"].verdict == "pass"
    v3 = {x.what: x for x in metrics.summarise(reps, "P4", "STD")}["SPA size at 0.05"]
    assert not v3.required and v3.verdict.startswith("reported")                   # V3 is not required in P4


def test_power_difference_for_the_selection_rule():
    reps = {s: [rep(m6_scr_num_i=15, m6_scr_num_ii=12) for _ in range(20)] for s in criteria.POWER_SCENARIOS}
    d = metrics.power_difference(reps)
    assert d["power_i"] == pytest.approx(0.75) and d["power_ii"] == pytest.approx(0.6)
    assert d["difference"] == pytest.approx(0.15) and d["lo"] == pytest.approx(0.15) and d["hi"] == pytest.approx(0.15)


def test_thresholds_and_counts_equal_the_preregistration_text():
    """Every number in manhattan/sim/criteria.py is read back from SIM_PREREG.md (which is never edited)."""
    def row(vid):
        m = re.search(rf"^\| {vid} \|(.*)$", PREREG, re.M)
        assert m, vid
        return m.group(1)
    bold = lambda vid: [float(x.replace("+", "").replace("−", "-")) for x in re.findall(r"\*\*([+−]?[0-9.]+)\*\*", row(vid))]
    assert bold("V1") == [criteria.V1_FDR_MAX]
    assert bold("V2") == [criteria.V2_FDR_MAX]
    assert bold("V3") == [criteria.V3_SIZE_MAX[0.20], criteria.V3_SIZE_MAX[0.05], criteria.V3_SIZE_MAX[0.001], criteria.V3_FWER_MAX]
    assert bold("V4") == [criteria.V4_LINK_MAX]
    assert bold("V5") == [criteria.V5_CROSS_MAX[20], criteria.V5_CROSS_MAX[100]]
    assert bold("V6") == [criteria.V6_SHARE_MIN[0.80], criteria.V6_SHARE_MIN[0.40], criteria.V6_ECE_MAX, criteria.V6_D01_HIGH_MAX]
    assert bold("V7") == [criteria.V7_ELIM_MAX, criteria.V7_LATE_MAX]
    assert bold("V8") == [criteria.V8_BIAS_MAX, criteria.V8_BIAS_MIN]
    assert bold("V10") == [criteria.V10_M11_MAX]
    assert bold("V11") == [criteria.V11_POWER_MIN, criteria.V11_POWER_MIN]
    assert "**2,000 replications** for every scenario at STD or LONG, and **400 replications** for every scenario at HB" in PREREG
    assert criteria.REPLICATIONS == {"STD": 2000, "LONG": 2000, "HB": 400}
    assert "fewer\nthan 200 family observations" in PREREG and criteria.SMALL_GROUP == 200
    assert "exceeds candidate (ii)'s by at least 0.05" in PREREG and criteria.SELECTION_MARGIN == 0.05
    assert "D01-D08, D11, H01, H02a, H03, H04" in row("V3") and "D01, D05, D06, D07b, H01, H04" in row("V5")
    assert set(criteria.V3_REQUIRED) == {"D01", "D02", "D03", "D04", "D05", "D06", "D07a", "D07b", "D08", "D11",
                                         "H01", "H02a", "H03", "H04"}
    assert "**except** H05 and H11" in row("V1") and "H08x" in row("V1") and "**except** H08x" in row("V2")
    assert criteria.required("V1", "D09a", "STD") and not criteria.required("V1", "H05", "STD")
    assert not criteria.required("V1", "D01", "HB") and criteria.required("V2", "H05", "STD")
    assert not criteria.required("V2", "H08x", "STD") and criteria.required("V6", "D10", "HB")
    assert criteria.required("V11", "P4", "STD") and not criteria.required("V11", "P3", "STD")
    # the scenario table: every development id of section 3.1 exists, and no held-out one does
    dev_ids = re.findall(r"^\| (D[0-9]+[ab]?(?:, D[0-9]+[ab]?)?|P1-P4) \|", PREREG, re.M)
    listed = {i.strip() for row_ in dev_ids for i in row_.replace("P1-P4", "P1,P2,P3,P4").split(",")}
    assert listed == set(world.SCENARIOS)
    held = set(re.findall(r"^\| (H[0-9]+[a-z]?) \|", PREREG, re.M))
    assert held == set(world.HELD_OUT)
