"""Technology equities, research family A: pair discovery and spread diagnostics on synthetic data.

These tests check that the prototype can tell a stable synthetic relationship from one that breaks, and that it
cannot see past its information boundary. They say nothing about whether any real pair trade earns money.
"""
from __future__ import annotations

from datetime import date
from functools import partial

import numpy as np
import pytest

from manhattan.equities import synthetic as syn
from manhattan.equities.costs import BorrowBook, BorrowRecord, EquityCostModel
from manhattan.equities.errors import BorrowError, EquityDataError, TemporalError
from manhattan.equities.pairs import (Boundary, PairDiscovery, PairRules, beta_neutral_hedge, half_life, ols_hedge,
                                      out_of_sample, position_from_z, feasibility, residual_spread, rolling_hedge)

CAL = syn.calendar()
PD = partial(PairDiscovery, calendar=CAL)          # every discovery and diagnostic counts sessions on the exchange
OOS = partial(out_of_sample, calendar=CAL)         # calendar (S8 M2)
NOLINK = PairRules(require_link=False)
COST = dict(half_spread=0.0005, commission=0.0001, impact=0.1, short_financing=0.0, long_financing=0.0,
            recall_cost=0.002, reference="test assumption")
SEEDS = range(20)


def boundary(days):
    return Boundary(days[0], days[499], days[505], days[-1])


def classify(seed, **kw):
    days, y, x = syn.cointegrated_pair(seed, **kw)
    bd = boundary(days)
    c = PD(days, {"Y": y, "X": x}, bd, NOLINK).evaluate_pair("X", "Y")
    if not c.passed:
        return "rejected"
    return "stable" if OOS(c, days, {"Y": y, "X": x}).stable else "broken"


def test_stable_relationship_is_distinguished_from_a_structural_break():
    stable = [classify(s) for s in SEEDS]
    broken_rw = [classify(s, break_at=505, break_kind="random_walk") for s in SEEDS]
    broken_beta = [classify(s, break_at=505, break_kind="beta_shift") for s in SEEDS]
    kept = [c for c in stable if c != "rejected"]
    assert len(kept) >= 16
    assert kept.count("stable") / len(kept) >= 0.85
    for res in (broken_rw, broken_beta):
        passed = [c for c in res if c != "rejected"]
        assert passed.count("broken") / len(passed) >= 0.9
    # the formation windows are identical with and without the break, so formation decisions must agree
    assert [c == "rejected" for c in stable] == [c == "rejected" for c in broken_rw]


def test_break_inside_formation_is_rejected_at_discovery():
    res = []
    for s in SEEDS:
        days, y, x = syn.cointegrated_pair(s, break_at=300, break_kind="random_walk")
        c = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK).evaluate_pair("X", "Y")
        res.append(c.passed)
    assert sum(res) <= 2


def test_correlation_without_cointegration_is_rejected():
    for s in SEEDS:
        days, a, b = syn.correlated_walks(s, rho=0.9)
        c = PD(days, {"A": a, "B": b}, boundary(days), NOLINK).evaluate_pair("A", "B")
        assert c.return_corr > 0.8
        assert not c.passed


def test_pair_selection_cannot_see_past_formation_end():
    days, y, x = syn.cointegrated_pair(5)
    bd = boundary(days)
    base = PD(days, {"Y": y, "X": x}, bd, NOLINK).candidates(include_failed=True)
    y2, x2 = y.copy(), x.copy()
    y2[500:] = np.cumsum(np.ones(250)) + 50          # an absurd future
    x2[500:] = -x2[500:]
    again = PD(days, {"Y": y2, "X": x2}, bd, NOLINK).candidates(include_failed=True)
    assert base == again
    d = PD(days, {"Y": y, "X": x}, bd, NOLINK)
    assert max(d.days) == bd.formation_end and all(len(v) == 500 for v in d.prices.values())


def test_boundary_requires_estimation_before_evaluation_with_embargo():
    with pytest.raises(TemporalError):
        Boundary(date(2005, 1, 3), date(2006, 1, 3), date(2006, 1, 3), date(2006, 6, 30))
    with pytest.raises(TemporalError):
        Boundary(date(2005, 1, 3), date(2006, 1, 3), date(2005, 6, 1), date(2006, 6, 30))


def test_economic_link_is_required_by_default():
    days, y, x = syn.cointegrated_pair(1)
    with pytest.raises(EquityDataError, match="link"):
        PD(days, {"Y": y, "X": x}, boundary(days))
    linked = PD(days, {"Y": y, "X": x}, boundary(days),
                           link=lambda a, b, t: "same category" if t <= date(2005, 12, 31) else None)
    assert linked.evaluate_pair("X", "Y") is not None
    unlinked = PD(days, {"Y": y, "X": x}, boundary(days), link=lambda a, b, t: None)
    assert unlinked.candidates(include_failed=True) == []


def test_candidates_carry_zero_weight_and_a_formation_hash():
    days, y, x = syn.cointegrated_pair(2)
    c = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK).evaluate_pair("X", "Y")
    assert c.status == "candidate" and c.evidential_weight == 0 and len(c.formation_hash) == 64


def test_rolling_hedge_uses_only_the_past_and_tracks_a_changing_ratio():
    days, y, x = syn.cointegrated_pair(4, break_at=400, break_kind="beta_shift", new_beta=0.6)
    a, b = rolling_hedge(y, x, 120)
    y2 = y.copy()
    y2[300] += 5.0                                    # a shock at t = 300 cannot change the ratio used at t = 300
    a2, b2 = rolling_hedge(y2, x, 120)
    assert b[300] == b2[300] and b[301] != b2[301]
    assert abs(np.nanmedian(b[250:400]) - 1.3) < 0.25
    assert abs(np.nanmedian(b[600:]) - 0.6) < 0.25


def test_primitives():
    a, b = ols_hedge(np.array([1.0, 3.0, 5.0, 7.0]), np.array([0.0, 1.0, 2.0, 3.0]))
    assert a == pytest.approx(1.0) and b == pytest.approx(2.0)
    rng = np.random.default_rng(0)
    u = np.zeros(2000)
    for t in range(1, 2000):
        u[t] = 0.9 * u[t - 1] + rng.normal()
    assert half_life(u) == pytest.approx(np.log(2) / -np.log(0.9), rel=0.3)
    assert half_life(np.cumsum(rng.normal(size=500)) + np.arange(500) * 0.1) in (float("inf"),) or \
        half_life(np.cumsum(rng.normal(size=500))) > 20
    assert beta_neutral_hedge(1.2, 0.8) == pytest.approx(1.5)
    with pytest.raises(EquityDataError):
        beta_neutral_hedge(1.0, 0.0)


def test_residual_spread_removes_a_shared_factor_with_formation_loadings_only():
    rng = np.random.default_rng(9)
    n = 600
    f = rng.normal(0, 0.01, n)
    ry = 1.5 * f + rng.normal(0, 0.002, n)
    rx = 0.5 * f + rng.normal(0, 0.002, n)
    form = np.arange(n) < 400
    s = residual_spread(ry, rx, f, form)
    raw = np.cumsum(ry - rx)
    assert np.std(np.diff(s)) < 0.5 * np.std(np.diff(raw))
    f2 = f.copy()
    f2[400:] *= 10                                     # changing later factor values cannot change the loadings
    ry2 = ry.copy()
    s2 = residual_spread(ry2, rx, f2, form)
    assert np.allclose(s[:400], s2[:400])


def test_short_leg_needs_borrow_and_its_cost():
    days, y, x = syn.cointegrated_pair(2)
    c = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK).evaluate_pair("X", "Y")
    pos = position_from_z(c, z=2.0, gross=1.0)        # spread rich: short the first leg
    assert pos.short == "X" and pos.long == "Y"
    day = date(2006, 3, 1)
    betas = {"X": 0.9, "Y": 1.6}
    with pytest.raises(BorrowError, match="omission"):
        feasibility(pos, day, EquityCostModel(**COST), betas)
    with pytest.raises(BorrowError, match="no borrow information"):
        feasibility(pos, day, EquityCostModel(**COST, borrow=BorrowBook()), betas)
    hard = BorrowBook([BorrowRecord("X", date(2006, 2, 28), date(2006, 3, 1), False, 0.25)])
    with pytest.raises(BorrowError, match="not borrowable"):
        feasibility(pos, day, EquityCostModel(**COST, borrow=hard), betas)
    ok = BorrowBook([BorrowRecord("X", date(2006, 2, 28), date(2006, 3, 1), True, 0.08, recall_prob_daily=0.01)])
    rep = feasibility(pos, day, EquityCostModel(**COST, borrow=ok), betas, earnings_within={"Y": True})
    assert rep["borrow_fee_annual"] == 0.08 and rep["holding_cost_daily"] > 0
    assert rep["earnings_in_window"] and abs(rep["beta"]) > 0.05   # "neutral" in dollars, not in beta
    # a borrow record published after the decision day is not known at it
    late = BorrowBook([BorrowRecord("X", date(2006, 2, 28), date(2006, 3, 2), True, 0.01)])
    with pytest.raises(BorrowError):
        feasibility(pos, day, EquityCostModel(**COST, borrow=late), betas)


def test_events_in_evaluation_window_are_counted():
    days, y, x = syn.cointegrated_pair(3)
    c = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK).evaluate_pair("X", "Y")
    rep = OOS(c, days, {"Y": y, "X": x}, events=[days[100], days[600], days[700]])
    assert rep.events_in_window == 2


# ----------------------------------------------------------------------------- S8 correction round: regressions
def _run(seed, mutate=None, **kw):
    days, y, x = syn.cointegrated_pair(seed, **kw)
    if mutate is not None:
        y, x = mutate(y.copy(), x.copy())
    bd = boundary(days)
    c = PD(days, {"Y": y, "X": x}, bd, NOLINK).evaluate_pair("X", "Y")
    if not c.passed:
        return "rejected", c, None
    r = OOS(c, days, {"Y": y, "X": x})
    return ("stable" if r.stable else "broken"), c, r


def test_s8_m1_a_leg_that_stops_trading_is_never_reported_stable():
    """S8 M1: with leg Y missing after observation 620 the pair was reported stable on the 115 remaining
    observations (flags=())."""
    def delist(y, x):
        y[620:] = np.nan
        return y, x
    for s in SEEDS:
        verdict, c, r = _run(s, delist)
        if verdict != "rejected":
            assert verdict == "broken" and any("stops trading" in f for f in r.flags), (s, r.flags)


def test_s8_m1_missing_observations_and_discontinuities_are_flagged():
    def holes(y, x):
        y[[560, 600, 640, 680, 700, 720]] = np.nan
        return y, x

    def gap(y, x):
        x[600:606] = np.nan
        return y, x
    for mut, word in ((holes, "missing"), (gap, "discontinuity")):
        for s in SEEDS:
            verdict, c, r = _run(s, mut)
            if verdict != "rejected":
                assert verdict == "broken" and any(word in f for f in r.flags), (s, r.flags)


def test_s8_m1_formation_gaps_make_a_pair_insufficient_data():
    days, y, x = syn.cointegrated_pair(2)
    y = y.copy()
    y[100:130] = np.nan
    d = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK)
    c = d.evaluate_pair("X", "Y")
    assert not c.passed and any("discontinuity" in r for r in c.reasons)
    assert d.attempts["insufficient_data"] == 1


def test_s8_m2_embargo_of_at_least_one_session_is_enforced():
    days, y, x = syn.cointegrated_pair(1)
    no_gap = Boundary(days[0], days[499], days[500], days[-1])        # adjacent: zero sessions in between
    with pytest.raises(TemporalError, match="embargo"):
        PD(days, {"Y": y, "X": x}, no_gap, NOLINK)
    c = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK).evaluate_pair("X", "Y")
    with pytest.raises(TemporalError, match="embargo"):
        OOS(c, days, {"Y": y, "X": x}, PairRules(require_link=False, embargo_sessions=10))
    with pytest.raises(TemporalError):
        PairRules(embargo_sessions=0)


def test_s8_m3_reports_are_labelled_retrospective_and_usable_only_after_the_window():
    verdict, c, r = _run(3)
    assert r.kind == "retrospective" and r.usable_from == c.boundary.evaluation_end


def test_s8_l8_every_pair_looked_at_is_counted():
    days, y, x = syn.cointegrated_pair(4)
    _, a, b = syn.correlated_walks(4)
    prices = {"Y": y, "X": x, "A": a, "B": b}
    link = lambda p, q, t: "same category" if {p, q} != {"A", "Y"} else None      # noqa: E731
    d = PD(days, prices, boundary(days), link=link)
    passed = d.candidates()
    assert d.attempts["considered"] == 6 == len(d.attempt_log)
    assert d.attempts["no_link"] == 1 and d.attempts["passed"] == len(passed)
    assert sum(d.attempts[k] for k in ("no_link", "insufficient_data", "rejected", "passed")) == 6


def test_s8_adversarial_delayed_breaks_are_mostly_caught_by_segment_checks():
    for kind in ("random_walk", "beta_shift"):
        res = [_run(s, break_at=650, break_kind=kind)[0] for s in SEEDS]
        passed = [v for v in res if v != "rejected"]
        assert passed.count("broken") / len(passed) >= 0.85, (kind, res)


def test_s8_adversarial_slow_mean_reversion_is_rejected_not_overconfidently_accepted():
    """Low power, documented: a genuine but slow relationship (φ = 0.97 or 0.99) rarely passes formation. The
    filter errs towards missing it, never towards calling a non-reverting spread a candidate."""
    for phi in (0.97, 0.99):
        res = [_run(s, phi=phi)[0] for s in SEEDS]
        assert res.count("rejected") >= 18, (phi, res)


# ----------------------------------------------------------------------------- S8 final review: L6, M2
def test_s8_l6_negative_hedge_ratio_is_rejected_not_mis_oriented():
    """S8 L6: with β = −0.77 the position was built from |β| as a long/short pair, the wrong orientation."""
    days, y, x = syn.cointegrated_pair(3, beta=-0.77)
    c = PD(days, {"Y": y, "X": x}, boundary(days), NOLINK).evaluate_pair("Y", "X")
    assert c.beta < 0 and not c.passed and any("not positive" in r for r in c.reasons)
    with pytest.raises(EquityDataError, match="hedge ratio"):
        position_from_z(c, z=2.0, gross=1.0)


def test_s8_m2_friday_to_monday_has_no_session_and_fails_a_one_session_embargo():
    days, y, x = syn.cointegrated_pair(1)
    fridays = [i for i, d in enumerate(days) if d.weekday() == 4 and 400 < i < 600 and days[i + 1].weekday() == 0]
    i = fridays[0]
    friday, monday = days[i], days[i + 1]
    bd = Boundary(days[0], friday, monday, days[-1])                  # Sat and Sun are dates, not sessions
    with pytest.raises(TemporalError, match="exchange sessions"):
        PD(days, {"Y": y, "X": x}, bd, NOLINK)
    # calendar days that are not sessions are refused outright
    from datetime import timedelta
    cal_days = np.array([days[0] + timedelta(days=k) for k in range(len(days))], dtype=object)
    with pytest.raises(TemporalError, match="not sessions"):
        PD(cal_days, {"Y": y, "X": x}, boundary(days), NOLINK)
    # Friday to Tuesday: exactly one session (Monday) in between
    PD(days, {"Y": y, "X": x}, Boundary(days[0], friday, days[i + 2], days[-1]), NOLINK)
