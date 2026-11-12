"""Tiers and dormancy (manhattan/stats/tiers.py): criterion C-14 of docs/manhattan/MANHATTAN_PROGRESS.md, against
docs/manhattan/PROTOCOL_v3.md sections 8.1, 8.2, 8.5 and 9. Scripted sequences; no data.
"""
from __future__ import annotations

import numpy as np
import pytest

from manhattan.stats import tiers
from manhattan.stats.tiers import Review, State, step


def R(pi, days=600, pos=True, **kw):
    return Review(pi_min=pi, forward_days=days, forward_mean_positive=pos, **kw)


def run(state, reviews):
    out = []
    for r in reviews:
        state = step(state, r)
        out.append(state)
    return out


def test_thresholds_are_the_protocols():
    assert (tiers.PROMISING_ENTER, tiers.PROMISING_EXIT) == (0.40, 0.20)
    assert (tiers.SUPPORTED_ENTER, tiers.SUPPORTED_EXIT, tiers.SUPPORTED_EXIT_NOW) == (0.80, 0.60, 0.40)
    assert (tiers.DAYS_PROMISING, tiers.DAYS_PROMISING_EXIT, tiers.DAYS_SUPPORTED_RW, tiers.DAYS_SUPPORTED) == (126, 252, 252, 504)
    assert (tiers.DORMANT_BELOW, tiers.REACTIVATE_AT, tiers.COVERAGE_MIN, tiers.THETA_MIN) == (0.05, 0.15, 0.90, 0.25)


def test_promising_by_screening_and_by_posterior():
    assert tiers.at_freeze(True).promising and not tiers.at_freeze(False).promising
    s = step(State(), R(0.45, days=125))
    assert not s.promising                                   # 126 forward days are needed
    assert not step(State(), R(0.39, days=300)).promising
    assert not step(State(), R(0.45, days=300, coverage=0.89)).promising
    s = step(State(), R(0.40, days=126))
    assert s.promising and s.enrolled and "promising:posterior" in s.events and "enrolled" in s.events
    assert step(tiers.at_freeze(True), R(0.01, days=10)).enrolled       # a screened family is enrolled at its first review


def test_promising_exit_needs_two_consecutive_low_reviews_and_252_days():
    s0 = tiers.at_freeze(True)
    a, b = run(s0, [R(0.20), R(0.20)])
    assert a.promising and not b.promising and "left promising" in b.events
    a, b, c = run(s0, [R(0.20), R(0.21), R(0.20)])
    assert c.promising                                        # the streak was broken
    a, b = run(s0, [R(0.10, days=251), R(0.10, days=251)])
    assert b.promising                                        # too little forward data to give up
    a, b, c = run(s0, [R(0.10, days=200), R(0.10, days=260), R(0.10, days=330)])
    assert b.promising and not c.promising


def test_supported_entry_needs_every_condition():
    s0 = tiers.at_freeze(True)
    assert step(s0, R(0.80, days=504)).supported
    assert not step(s0, R(0.79, days=504)).supported
    assert not step(s0, R(0.95, days=504, pos=False)).supported
    assert not step(s0, R(0.95, days=503)).supported
    assert step(s0, R(0.95, days=252, rw_reserve=True)).supported      # 252 days when Romano-Wolf named a variant
    assert not step(s0, R(0.95, days=251, rw_reserve=True)).supported
    assert not step(s0, R(0.95, days=504, integrity_flag=True)).supported
    s = step(State(), R(0.95, days=504))                                # not screened: Promising by route (b) first,
    assert s.promising and s.supported                                  # and supported at the same review


def test_supported_exits_and_hysteresis():
    sup = step(tiers.at_freeze(True), R(0.9))
    assert sup.supported
    a, b = run(sup, [R(0.59), R(0.59)])
    assert a.supported and not b.supported
    a, b, c = run(sup, [R(0.59), R(0.60), R(0.59)])
    assert c.supported
    assert not step(sup, R(0.39)).supported                             # at once below 0.40
    assert not step(sup, R(0.95, integrity_flag=True)).supported        # at once on an integrity record
    back = run(sup, [R(0.39), R(0.70)])[-1]
    assert not back.supported and back.promising                        # 0.70 is above the exit but below the entry
    assert run(sup, [R(0.39), R(0.80)])[-1].supported


def test_not_converged_changes_nothing():
    sup = step(tiers.at_freeze(True), R(0.9))
    low = step(sup, R(0.59))
    held = step(low, R(None))
    assert held.supported and held.low_supported == 1 and "model not converged: no tier change" in held.events
    assert not step(held, R(0.59)).supported                            # the streak resumes where it was
    s = step(State(), R(None))
    assert s == State(events=("model not converged: no tier change",))


def test_formal_support_is_permanent_and_marks_decay():
    s = step(tiers.at_freeze(True), R(0.5, elond_rejected=True))
    assert s.formal and "formal" in s.events
    a, b = run(s, [R(0.1), R(0.1)])
    assert b.formal and not b.promising and b.decayed_since
    assert step(b, R(0.0)).formal


def test_dormancy_needs_two_low_forecasts_and_wakes_at_015():
    s0 = State()
    a, b = run(s0, [R(0.1, pp_max=0.04), R(0.1, pp_max=0.04)])
    assert not a.dormant and b.dormant and "dormant" in b.events and b.recording        # cheap: still recorded
    a, b, c = run(s0, [R(0.1, pp_max=0.04), R(0.1, pp_max=0.05), R(0.1, pp_max=0.04)])
    assert not c.dormant
    d = run(s0, [R(0.1, pp_max=0.0), R(0.1, pp_max=0.0)])[-1]
    still = step(d, R(0.9, pp_max=0.14))
    assert still.dormant and not still.promising                        # while dormant: no tier evaluation
    woke = step(d, R(0.45, pp_max=0.15))
    assert not woke.dormant and "reactivated" in woke.events and woke.promising         # evaluated again at once
    assert not step(d, R(0.1, pp_max=0.0, ethan_reactivates=True)).dormant
    costly = run(s0, [R(0.1, pp_max=0.0, cheap=False), R(0.1, pp_max=0.0, cheap=False)])[-1]
    assert costly.dormant and not costly.recording


def test_never_dormant_without_a_programme_end_and_never_while_supported():
    a, b, c = run(State(), [R(0.1, pp_max=0.0, t_end_set=False)] * 3)
    assert not c.dormant
    a, b, c = run(State(), [R(0.1, pp_max=None)] * 3)
    assert not c.dormant
    sup = step(tiers.at_freeze(True), R(0.9))
    assert not run(sup, [R(0.9, pp_max=0.0), R(0.9, pp_max=0.0)])[-1].dormant


def test_support_probability_is_high_for_a_strong_family_and_low_for_a_null_one():
    rng = np.random.default_rng(0)
    K, S = 6, 400
    mean = np.tile(np.array([1.5, 0.0, 0.0]), (K, 1))
    sd = np.tile(np.array([0.3, 0.05, 0.3]), (K, 1))
    draws = mean[:, None, :] + sd[:, None, :] * rng.standard_normal((K, S, 3))
    kw = dict(fwd_years=np.array([1.0, 1.0, 1.0]), fwd_sum=np.array([1.5, 0.0, 0.0]),
              promising=np.array([True, False, False]), rw_reserve=np.zeros(3, bool))
    pp = tiers.support_probability(draws, mean, sd, review_gaps=[2, 3, 3], rng=np.random.default_rng(1), **kw)
    assert pp.shape == (K, 3) and np.all((pp >= 0) & (pp <= 1))
    assert pp[:, 0].min() > 0.9 and pp[:, 1].max() < 0.02 and pp[:, 1].max() <= pp[:, 2].max() + 0.02
    none = tiers.support_probability(draws, mean, sd, review_gaps=[], rng=np.random.default_rng(1), **kw)
    assert np.all(none == 0)
    # a decaying truth (S5) is less likely to make it than a constant one
    slow = np.tile(np.array([0.6, 0.6, 0.6]), (K, 1))
    d2 = slow[:, None, :] + 0.05 * rng.standard_normal((K, S, 3))
    args = dict(fwd_years=np.zeros(3), fwd_sum=np.zeros(3), promising=np.ones(3, bool), rw_reserve=np.zeros(3, bool),
                review_gaps=[2, 2, 3, 3])
    pp2 = tiers.support_probability(d2, slow, np.full((K, 3), 0.4), rng=np.random.default_rng(2), decay_model=5, **args)
    assert pp2[5].mean() < pp2[0].mean() - 0.05
