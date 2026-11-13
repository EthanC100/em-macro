"""Intervals with the replication as the unit of clustering (``manhattan/sim/cluster_ci.py``): the
delete-one-replication jackknife with a Student-t quantile, and the exact bound where nothing happened."""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import t as student_t

from manhattan.sim import cluster_ci, metrics
from manhattan.sim.metrics import Row, mean_ci, ratio_ci


def mean_rows(reps):
    e, lo, hi = mean_ci([r["x"] for r in reps])
    f, flo, fhi = ratio_ci([r["num"] for r in reps], [r["den"] for r in reps])
    z = mean_ci([r["zero"] for r in reps])
    one = ratio_ci([r["den"] for r in reps], [r["den"] for r in reps])
    return [Row("M3", "a mean of per-replication values", e, lo, hi, len(reps), "mean", "V3", "upper bound ≤ 0.06", True,
                "pilot: not decided (within threshold so far)"),
            Row("M8", f"a pooled ratio ({int(sum(r['den'] for r in reps))} family observations)", f, flo, fhi, 1, "ratio", "V7",
                "upper bound ≤ 0.1", True, "pilot: not decided (within threshold so far)"),
            Row("M2", "no event in any replication", *z, len(reps), "mean", "V2", "upper bound ≤ 0.06", True,
                "pilot: not decided (within threshold so far)"),
            Row("M6", "an event in every one", *one, 1, "ratio", "V11", "lower bound ≥ 0.5", True, "pilot"),
            Row("M7", "a small group (3 family observations)", e, lo, hi, 3, "ratio", "V6", "lower bound ≥ 0.7", True,
                "not evaluated: fewer than 200 observations"),
            Row("cost", "seconds per replication", 1.0, None, None, len(reps), "mean")]


def test_the_jackknife_is_sd_over_root_r_for_a_mean_and_the_linearised_error_for_a_ratio():
    rng = np.random.default_rng(5)
    R = 12
    reps = [{"x": float(x), "num": float(n), "den": float(d), "zero": 0.0}
            for x, n, d in zip(rng.normal(0.05, 0.01, R), rng.integers(0, 6, R), rng.integers(40, 90, R))]
    rows = {r["what"]: r for r in cluster_ci.jackknife(mean_rows, reps)}
    assert set(rows) == {"a mean of per-replication values", "a pooled ratio (%d family observations)" % sum(r["den"] for r in reps),
                         "no event in any replication", "an event in every one", "a small group (3 family observations)"}
    tq = student_t.ppf(0.975, R - 1)
    assert tq == pytest.approx(2.201, abs=1e-3)
    x = np.array([r["x"] for r in reps])
    m = rows["a mean of per-replication values"]
    assert m["se"] == pytest.approx(x.std(ddof=1) / math.sqrt(R), rel=1e-9)
    assert (m["lo"], m["hi"]) == pytest.approx((x.mean() - tq * m["se"], x.mean() + tq * m["se"]))
    assert m["hi"] - m["lo"] == pytest.approx((m["old_hi"] - m["old_lo"]) * tq / 1.96)       # wider by exactly t over z
    num, den = (np.array([r[k] for r in reps]) for k in ("num", "den"))
    ratio = next(v for k, v in rows.items() if k.startswith("a pooled ratio"))
    lin = math.sqrt(R / (R - 1) * ((num - num.sum() / den.sum() * den) ** 2).sum()) / den.sum()
    assert ratio["estimate"] == pytest.approx(num.sum() / den.sum()) and ratio["se"] == pytest.approx(lin, rel=0.08)
    assert ratio["rule"] == "jackknife-t"


def test_no_event_in_any_replication_gets_the_exact_bound_and_the_verdict_can_change():
    reps = [{"x": 0.05, "num": 1.0, "den": 50.0, "zero": 0.0} for _ in range(12)]
    rows = {r["what"]: r for r in cluster_ci.jackknife(mean_rows, reps)}
    z = rows["no event in any replication"]
    assert (z["old_lo"], z["old_hi"]) == (0.0, 0.0) and z["lo"] == 0.0
    assert z["hi"] == pytest.approx(1 - 0.025 ** (1 / 12)) == pytest.approx(0.2646, abs=1e-4)
    assert z["old_side"] == "within" and z["new_side"] == "outside" and z["changed"]        # 0.26 is not below 0.06
    one = rows["an event in every one"]
    assert one["hi"] == 1.0 and one["lo"] == pytest.approx(0.025 ** (1 / 12)) and not one["changed"]   # 0.735 is above 0.5
    same = rows["a mean of per-replication values"]                                 # identical, not zero: left alone
    assert same["se"] == 0.0 and same["lo"] == same["hi"] == pytest.approx(0.05) and not same["changed"]
    small = rows["a small group (3 family observations)"]
    assert small["old_side"] is None and small["new_side"] is None and not small["changed"]   # the small-groups rule stands
    assert 1 - 0.025 ** (1 / 36) == pytest.approx(0.0974, abs=1e-4) and 1 - 0.025 ** (1 / 400) < 0.01


def test_thresholds_sides_and_keys():
    assert cluster_ci.limits("upper bound ≤ 0.06") == [("upper", 0.06)] and cluster_ci.limits("lower bound ≥ 0.7") == [("lower", 0.7)]
    assert cluster_ci.limits("upper bound ≤ +0.1 and lower bound ≥ -0.25") == [("upper", 0.1), ("lower", -0.25)]
    assert cluster_ci.limits("exactly 0") == [] and cluster_ci.limits("") == []
    assert cluster_ci.side(0.01, 0.05, [("upper", 0.06)]) == "within" and cluster_ci.side(0.01, 0.07, [("upper", 0.06)]) == "outside"
    assert cluster_ci.side(-0.3, 0.05, [("upper", 0.1), ("lower", -0.25)]) == "outside"
    assert cluster_ci.side(None, None, [("upper", 0.06)]) is None and cluster_ci.side(0.0, 0.1, []) is None
    a = Row("M4", "linked average error, candidate (i) (140 families passed)", 0.0, 0.0, 0.0, 12, "mean")
    b = Row("M4", "linked average error, candidate (i) (131 families passed)", 0.0, 0.0, 0.0, 11, "mean")
    c = Row("M12", "reviews not computed (a fit fails the grid gate), of 48", 0.0, None, None, 48, "count")
    assert cluster_ci.key(a) == cluster_ci.key(b) and cluster_ci.key(c)[1] == "reviews not computed (a fit fails the grid gate)"


def test_a_metric_undefined_without_one_replication_is_said_to_be_so():
    def rows_fn(reps):
        e, lo, hi = ratio_ci([r["num"] for r in reps], [r["den"] for r in reps])
        return [Row("M9", "a group held by one replication", e, lo, hi, 1, "ratio")]
    reps = [{"num": 1.0, "den": 4.0}] + [{"num": 0.0, "den": 0.0} for _ in range(5)]
    (row,) = cluster_ci.jackknife(rows_fn, reps)
    assert row["lo"] is None and row["rule"].startswith("not computable") and not row["changed"]


def test_the_report_on_the_records_in_the_repository():
    text, summary = cluster_ci.build()
    assert text.startswith("# Manhattan simulation: every interval with the replication as the unit of clustering")
    assert summary["runs"] >= 18 and summary["intervals"] > 500                    # version 1's 18 pilots at least
    assert 0 < summary["changed"] <= summary["judged"] <= summary["intervals"]
    assert summary["mean_width_ratio"] > 1.0                                       # never narrower on average
    rows = summary["rows"]
    assert all(r["estimate"] == r["estimate"] for r in rows)                       # the estimate is never touched
    mean_rows_ = [r for r in rows if r["rule"] == "jackknife-t" and r["what"].startswith("SPA size at 0.05") and r["se"] > 0]
    r = mean_rows_[0]
    tq = student_t.ppf(0.975, r["replications"] - 1)
    assert (r["hi"] - r["lo"]) / (r["old_hi"] - r["old_lo"]) == pytest.approx(tq / metrics.Z95, rel=1e-6)
    assert all(not r["changed"] for r in rows if r["old_verdict"].startswith("not evaluated"))


def test_the_hb_runs_of_the_code_now_checked_out_can_be_reported_alone():
    """``--current-hb``: the pilot of the drafts as they stand, without the superseded pilots beside it."""
    text, summary = cluster_ci.build(current_hb=True)
    assert text.startswith("# Manhattan simulation: every interval with the replication as the unit of clustering: the HB runs")
    assert {r["source"] for r in summary["rows"]} <= {cluster_ci.HB_CURRENT} and all(r["run"].endswith(" HB") for r in summary["rows"])
    assert "PILOT_RERUN3_REPORT.md" in cluster_ci.HB_CURRENT and "quarterly reviews" in cluster_ci.HB_CURRENT
    # the two earlier HB pilots keep their own labels in the full file and are never pooled with the current one
    assert set(cluster_ci.HB_SOURCES) == {cluster_ci.PILOT_5M_HB_CODE, cluster_ci.PILOT_6M_HB_CODE}
    assert "superseded" in cluster_ci.HB_SOURCES[cluster_ci.PILOT_5M_HB_CODE] and "Π^max" in cluster_ci.HB_SOURCES[cluster_ci.PILOT_6M_HB_CODE]
