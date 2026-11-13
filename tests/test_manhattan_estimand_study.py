"""The study of what the forward e-process tests (``manhattan/sim/estimand_study.py``): the simulated processes,
the proposed tail-risk check and the skipping experiment, at a small size. Synthetic series only."""
from __future__ import annotations

import math

import numpy as np
import pytest

from manhattan.sim import estimand_study as es
from manhattan.stats import eprocess


def test_a_process_has_the_sharpe_ratio_it_is_given_crashes_included():
    d = es.Dgp("crash", J=20.0, per_decade=2.0, sharpe=0.0)
    assert d.p == pytest.approx(2 / 2520) and d.daily_mean == 0.0
    assert d.premium == pytest.approx(d.p * 20.0)                       # what it earns while nothing happens pays for the crash
    x = es.simulate(d, 400, np.random.default_rng(1))
    assert x.shape == (400, es.BURN + 2520) and abs(x.mean()) < 0.01
    assert x.std() == pytest.approx(d.daily_sd, rel=0.05)
    up = es.Dgp("normal", sharpe=1.0)
    assert up.daily_mean == pytest.approx(1 / math.sqrt(252)) and up.premium == up.daily_mean
    sym = es.Dgp("two-sided", J=20.0, per_decade=5.0, symmetric=True, sharpe=0.0)
    assert sym.premium == 0.0 and sym.daily_sd == pytest.approx(math.sqrt(1 + sym.p * 400))


def test_the_weekly_inputs_are_the_protocols_own():
    x = es.simulate(es.Dgp("t3", dist="t3"), 30, np.random.default_rng(2))
    w = es.weekly(x)
    ref = eprocess.weekly_inputs(x, es.BURN, 504, es.SCALE_FLOOR)
    assert all(np.array_equal(w[k], ref[k]) for k in ("Z", "Y", "bet", "s"))
    assert (w["Y"] >= -eprocess.C_WEEKLY).all() and (w["Y"] >= w["Z"]).all()


def test_the_proposed_tail_check_on_hand_made_records():
    assert es.poisson_upper(np.array([0, 1, 2])) == pytest.approx([2.9957, 4.7439, 6.2958], abs=1e-4)   # the rule of three
    Z = np.full((1, 100), 0.5)
    # no truncated week, worst loss none, declared stress 12: the record must have earned 3 x (12 - 6) = 18
    assert es.tail_check(Z, Z, 12.0)[0]                                 # 50 > 17.97
    assert not es.tail_check(Z[:, :35], Z[:, :35], 12.0)[0]             # 17.5 < 17.97
    assert not es.tail_check(Z, Z, 30.0)[0]                             # 50 < 3 x 24
    crash = Z.copy()
    crash[0, 10] = -40.0                                                # one week 40 standard deviations down
    Y = np.maximum(crash, -6.0)
    # truncated total 49.5 - 6 = 43.5; one truncated week: 4.74 x (40 - 6) = 161 to pay for; and the raw total is positive
    assert Y.sum() == pytest.approx(43.5) and crash.sum() > 0 and not es.tail_check(crash, Y, 12.0)[0]
    assert not es.tail_check(-Z, -Z, 12.0)[0]                           # a losing record never passes


def test_signs_and_skipping_at_a_small_size():
    rng = np.random.default_rng(3)
    flat = es.study_signs(es.Dgp("normal", sharpe=0.0), 200, rng)
    assert flat["gap"] == 0.0 and not flat["population_sign_differs"] and flat["y10_sign_differs"] == 0.0
    crash = es.study_signs(es.Dgp("crash", J=100.0, per_decade=2.0, sharpe=0.0), 200, rng)
    assert crash["crash_in_weekly_sd"] == pytest.approx(100 / math.sqrt(5)) and crash["declared_stress"] == crash["crash_in_weekly_sd"]
    assert crash["mean_Z"] == 0.0 and crash["mean_Y"] > 0.05 and crash["population_sign_differs"]
    assert crash["y10_sign_differs"] > 0.2 and crash["y10_check_declared"] < 0.05 < crash["y10_check_floor"]
    rows = es.study_skipping(300, rng)
    by = {(r["series"], r["rule"]): r for r in rows}
    fair = by[("normal", "variance-ratio rule (past only)")]
    cheat = by[("normal", "weeks dropped after the fact (Z < -2)")]
    assert fair["reach_20"] <= 0.05 and 0.9 < fair["bet_rate"] < 1.0
    assert cheat["reach_20"] > 0.05 + 0.02 and cheat["mean_Y_bet_weeks"] > 0.03       # dropping losses after the fact breaks Ville's bound
    spell = [r for r in rows if r["series"].startswith("zero mean overall")]
    assert spell[1]["bet_rate"] < 0.8 and spell[1]["mean_Y_bet_weeks"] > spell[1]["mean_Y_all_weeks"] + 0.03
