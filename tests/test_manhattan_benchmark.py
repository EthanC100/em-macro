"""The timing slice (``manhattan/sim/benchmark.py``): what it covers and how its numbers are summarised. The
benchmark itself is not run here (it takes minutes); it writes no replication record and no run-log record."""
from __future__ import annotations

import inspect

import pytest

from manhattan.sim import benchmark, criteria_v2, run


def test_the_slice_has_one_run_of_each_kind_of_code():
    kinds = {(run.route(s, z, "v2"), z, criteria_v2.is_twin(s)) for s, z, _ in benchmark.SLICE}
    assert kinds == {("v1", "STD", False), ("v1", "LONG", False), ("v2", "STD", False), ("v2", "STD", True), ("v2", "HB", False)}
    assert all(run.route(s, z, "v2") == v for s, z, v in benchmark.SLICE)            # each job runs the code the full run would
    assert set(benchmark.QUICK) <= set(benchmark.SLICE)
    src = inspect.getsource(benchmark)
    assert "runlog" not in src and "reps_path" not in src and ".open(" not in src     # timing only: nothing is recorded


def test_summary_of_hand_made_timings():
    out = {"workers": 2, "busy_wall_total": 150.0,
           "alone": [{"scenario": "D02", "size": "STD", "version": "v1", "rep": 0, "wall": 60.0, "cpu": 59.0, "peak_rss_mb": 300.0},
                     {"scenario": "D08", "size": "HB", "version": "v2", "rep": 0, "wall": 120.0, "cpu": 118.0, "peak_rss_mb": 500.0}],
           "busy": [{"scenario": "D02", "size": "STD", "version": "v1", "rep": 0, "wall": 75.0, "cpu": 60.0, "peak_rss_mb": 310.0},
                    {"scenario": "D02", "size": "STD", "version": "v1", "rep": 1, "wall": 85.0, "cpu": 62.0, "peak_rss_mb": 305.0},
                    {"scenario": "D08", "size": "HB", "version": "v2", "rep": 0, "wall": 150.0, "cpu": 119.0, "peak_rss_mb": 520.0},
                    {"scenario": "D08", "size": "HB", "version": "v2", "rep": 1, "wall": 130.0, "cpu": 119.0, "peak_rss_mb": 480.0}]}
    s = benchmark.summarise(out)
    assert s["kinds"]["D02 STD"]["efficiency"] == pytest.approx(60 / 80) and s["kinds"]["D02 STD"]["efficiency_same_replication"] == 0.8
    assert s["kinds"]["D08 HB"]["busy_wall_mean"] == 140.0 and s["kinds"]["D08 HB"]["peak_rss_mb"] == 520.0
    assert s["efficiency"] == pytest.approx(180 / 220, abs=1e-3) and s["efficiency_same_replication"] == pytest.approx(180 / 225)
    assert s["busy_cpu_hours"] == pytest.approx(360 / 3600) and s["busy_cpu_share_of_cores"] == pytest.approx(360 / 300)
    assert s["peak_rss_mb_per_worker"] == 520.0 and s["peak_rss_mb_all_workers"] == 1040.0
