"""Execution realism adapter (manhattan/execution_realism, docs/manhattan/EXECUTION_REALISM.md).

Every number is synthetic: made-up roots (SYNA, SYNR, SYNE, SYNX), made-up prices, calendars and costs. Nothing is
read from a file other than this repository's own sources (isolation checks) and nothing touches the network.

Two cross-checks run only when a checkout of the reviewed code is given (they need unmerged branches):

    EXEC_REALISM_PR85_CHECKOUT=<checkout of PR #85 at 3f6b213>   conformance of fills, rolls, FX, liquidity
    EXEC_REALISM_HTE_CHECKOUT=<checkout of PR #89 at 232d0d6>    lag-0 identity with HTE's alignment and stage 3
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import math
import os
import random
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from manhattan import execution_realism as XR
from manhattan.execution_realism import adapter as AD
from manhattan.execution_realism import costs as C
from manhattan.execution_realism import errors as E
from manhattan.execution_realism import fixtures as F
from manhattan.execution_realism import instruments as I
from manhattan.execution_realism import panel as PN
from manhattan.execution_realism import provenance as PV
from manhattan.execution_realism import realism as RL
from manhattan.execution_realism import screening as SC
from manhattan.execution_realism import sensitivity as S
from manhattan.execution_realism import timing as TM

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "manhattan/execution_realism"
SYNX = I.Instrument("SYNX", "USD", 1.0, 10.0, 10.0)          # tick 1 point, 10 USD per point
SYNA = F.ROOTS["SYNA"][0]


def lag(k: int) -> TM.ExecutionTiming:
    return TM.ExecutionTiming(k, allow_same_close=(k == 0))


def pol(k: int = 1, **kw) -> AD.ExecutionPolicy:
    kw.setdefault("capital", 1_000_000.0)
    return AD.ExecutionPolicy(timing=lag(k), **kw)


def terms(fee="USD", fxc=None, **kw) -> C.RootCosts:
    v = dict(commission=0.0, exchange_fee=0.0, half_spread_ticks=0.0, slippage_ticks=0.0, impact_coefficient=0.0,
             max_participation=1.0)
    v.update(kw)
    return C.RootCosts(fee, *(C.synthetic(v[k]) for k in ("commission", "exchange_fee", "half_spread_ticks",
                                                          "slippage_ticks", "impact_coefficient",
                                                          "max_participation")),
                       None if fxc is None else C.synthetic(fxc))


def model(root="SYNX", **kw) -> C.CostModel:
    return C.CostModel("t", ((root, terms(**kw)),))


def mini(levels, *, inst=SYNX, roll=None, exit_level=None, adv=1e6, vol=0.0, fx=None, data_kind="synthetic"):
    lv = np.array(levels, float).reshape(-1, 1)
    n = lv.shape[0]
    rl = np.zeros((n, 1), bool) if roll is None else np.array(roll, bool).reshape(-1, 1)
    ex = lv.copy() if exit_level is None else np.array(exit_level, float).reshape(-1, 1)
    advs = np.broadcast_to(np.array(adv, float).reshape(-1, 1) if np.ndim(adv) else adv, (n, 1))
    return PN.SettlementPanel(days=tuple(F.weekdays(date(2001, 1, 2), n)), instruments=(inst,), level=lv,
                              exit_level=ex, roll=rl, adv=advs, vol_points=np.full((n, 1), vol),
                              base_currency="USD", fx=fx or {}, data_kind=data_kind)


def plan(n, pairs):
    """Contracts targets: {row: target}."""
    c = np.full((n, 1), np.nan)
    for t, v in pairs.items():
        c[t, 0] = v
    return c


# ================================================================== 1. timing
def test_the_three_conventions_and_hte_label():
    assert TM.CONVENTIONS["hte_same_close"]["lag"] == 0
    assert TM.CONVENTIONS["hte_same_close"]["label"] == "same_close_fill_next_day_return/v1"
    assert TM.CONVENTIONS["pr85_lag"]["lag"] == 1 and TM.CONVENTIONS["engine_lag"]["lag"] == 1
    assert TM.DEFAULT_LAG == 1 and AD.ExecutionPolicy(capital=1.0).lag == 1


def test_same_close_needs_an_explicit_allowance():
    with pytest.raises(E.OptimisticExecutionError):
        TM.ExecutionTiming(0)
    assert TM.ExecutionTiming(0, allow_same_close=True).label == TM.HTE_SAME_CLOSE
    for bad in (-1, True, 1.0):
        with pytest.raises(E.UnitError):
            TM.ExecutionTiming(bad)


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_a_decision_at_close_t_first_earns_day_t_plus_lag_plus_1(k):
    levels = [100, 101, 103, 106, 110, 115, 121]
    r = AD.execute(mini(levels), model(), pol(k), contracts=plan(7, {0: 1}))
    g = r.gross[:, 0] / SYNX.point_value
    first = TM.ExecutionTiming(k, allow_same_close=True).first_return_day(0)
    assert np.all(g[:first] == 0)
    assert g[first] == levels[first] - levels[first - 1]          # earns exactly from the fill at close t + lag
    assert r.fills[0].day == k and r.fills[0].reference_price == levels[k]


def test_decisions_past_the_last_day_are_reported_not_executed():
    r = AD.execute(mini([10, 11, 12]), model(), pol(2), contracts=plan(3, {0: 1, 1: 2}))
    assert [(u.decision_day, u.target) for u in r.unexecuted] == [(1, 2)]
    assert r.positions[2, 0] == 1


def test_a_missing_price_never_shortens_the_lag():
    # decision at 0, lag 1: day 1 has no settlement; under hold the order waits to day 2, never earlier than day 1
    r = AD.execute(mini([10, np.nan, 12, 13]), model(), pol(1, on_missing_price="hold"), contracts=plan(4, {0: 2}))
    assert [f.day for f in r.fills] == [2] and r.fills[0].reason == "carry"
    assert [(u.day, u.why) for u in r.unfilled] == [(1, "no settlement")]
    with pytest.raises(E.MissingInputError):
        AD.execute(mini([10, np.nan, 12, 13]), model(), pol(1), contracts=plan(4, {0: 2}))


# ================================================================== 2. contracts, ticks, costs
def test_tick_value_identity_refuses_a_cents_unit_error():
    with pytest.raises(E.UnitError):
        I.Instrument("SYNC", "USD", 0.25, 12.5, 5000.0, 1.0)     # cents quote described in dollars
    I.Instrument("SYNC", "USD", 0.25, 12.5, 5000.0, 0.01)


def test_fractional_ticks_cost_whole_ticks_and_parts_add_up():
    t = terms(half_spread_ticks=0.5, slippage_ticks=0.25, impact_coefficient=0.7, commission=2.0, exchange_fee=1.0)
    for q in (3, -3):
        f = C.fill(SYNA, t, day=0, leg="outright", reason="decision", requested=q, quantity=q, ref=70.23,
                   adv=900.0, vol_points=0.37, liquidity_day=0)
        assert I.on_tick(f.fill_price, SYNA.tick_size)
        assert (f.fill_price - 70.23) * q > 0
        assert f.execution_cost == pytest.approx((f.fill_price - 70.23) * q * SYNA.point_value, abs=1e-9)
        assert min(f.spread, f.slippage, f.impact) > 0 and f.rounding >= -1e-9
        assert (f.commission, f.exchange_fee) == (6.0, 3.0)
    half = C.fill(SYNA, terms(half_spread_ticks=0.5), day=0, leg="outright", reason="decision", requested=1,
                  quantity=1, ref=70.23, adv=1.0, vol_points=0.0, liquidity_day=0)
    assert half.fill_price == 70.24                                # half a tick fills a whole tick away
    assert half.spread == pytest.approx(5.0) and half.rounding == pytest.approx(5.0)


def test_fees_are_per_side_so_a_round_trip_pays_twice():
    r = AD.execute(mini([10, 10, 10, 10]), model(commission=1.5, exchange_fee=0.5), pol(1),
                   contracts=plan(4, {0: 4, 1: 0}))
    t = r.totals()
    assert t["commission"] == 2 * 4 * 1.5 and t["exchange_fee"] == 2 * 4 * 0.5 and t["gross"] == 0


def test_sizing_from_weights_rounds_and_uses_the_decision_time_price_and_fx():
    p = mini([60.0, 61.0, 62.0], inst=SYNA)
    W = np.array([[0.3], [np.nan], [np.nan]])
    tg, _ = AD.size(p, W, pol(1))
    assert tg[0, 0] == 5                                            # 0.3 x 1e6 / (60 x 1000)
    tz, _ = AD.size(p, W * 0.99, pol(1, sizing_rounding="toward_zero"))
    assert tz[0, 0] == 4                                            # 4.95 -> 4
    syne = F.ROOTS["SYNE"][0]
    pe = mini([3000.0, 3000.5], inst=syne, fx={"EUR": np.array([1.25, 2.0])})
    te, _ = AD.size(pe, np.array([[0.75], [np.nan]]), pol(1))
    assert te[0, 0] == 20                                           # 0.75e6 / (3000 x 10 x 1.25): day 0's rate, not 2.0


def test_a_zero_price_cannot_be_sized_and_a_negative_price_is_marked_by_sign():
    with pytest.raises(E.UnitError):
        AD.size(mini([0.0, 1.0]), np.array([[0.1], [np.nan]]), pol(1))
    r = AD.execute(mini([-5.0, -5.0, -3.0]), model(), pol(1), contracts=plan(3, {0: 2}))
    assert r.gross[2, 0] == 2 * 2 * SYNX.point_value               # long gains as the price rises through negatives
    assert r.net_exposure[2, 0] > 0                                 # a long is a positive exposure at any price


def test_adjusted_or_off_tick_prices_are_refused():
    for kind in PN.PRICE_KINDS_REFUSED:
        with pytest.raises(E.UnitError, match="refused"):
            replace_kind = dict(days=(date(2001, 1, 2),), instruments=(SYNX,), level=[[1.0]], exit_level=[[1.0]],
                                roll=[[False]], adv=[[1.0]], vol_points=[[0.0]], base_currency="USD",
                                price_kind=kind)
            PN.SettlementPanel(**replace_kind)
    with pytest.raises(E.UnitError, match="tick"):
        mini([60.005, 60.0], inst=SYNA)


# ================================================================== 3. liquidity
def test_participation_cap_raise_and_clip_with_the_right_liquidity_day():
    adv = [30.0, 1000.0, 1000.0, 1000.0, 1000.0]                    # cap 3 on the decision's own estimate
    p = mini([10] * 5, adv=adv)
    with pytest.raises(E.LiquidityError):
        AD.execute(p, model(max_participation=0.1), pol(1), contracts=plan(5, {0: 8}))
    r = AD.execute(p, model(max_participation=0.1), pol(1, on_liquidity_shortfall="clip"), contracts=plan(5, {0: 8}))
    assert [(f.day, f.filled, f.liquidity_day, f.reason) for f in r.fills] == [(1, 3, 0, "decision"),
                                                                               (2, 5, 1, "carry")]
    assert r.unfilled[0].why == "liquidity"


def test_a_later_liquidity_estimate_is_never_used():
    # the decision is taken when ADV is 20 (cap 2); the estimate published at the execution close is 1e6
    p = mini([10] * 4, adv=[20.0, 1e6, 1e6, 1e6])
    r = AD.execute(p, model(max_participation=0.1), pol(1, on_liquidity_shortfall="clip"), contracts=plan(4, {0: 5}))
    assert r.fills[0].filled == 2 and r.fills[0].liquidity_day == 0


def test_zero_adv_fills_nothing_under_clip_and_stops_under_raise():
    p = mini([10] * 3, adv=0.0)
    r = AD.execute(p, model(max_participation=0.1), pol(1, on_liquidity_shortfall="clip"), contracts=plan(3, {0: 1}))
    assert not r.fills and r.positions[:, 0].tolist() == [0, 0, 0] and r.totals()["costs"] == 0
    with pytest.raises(E.LiquidityError):
        AD.execute(p, model(max_participation=0.1), pol(1), contracts=plan(3, {0: 1}))


def test_single_month_reversal_closes_first_like_pr85():
    # +5 -> -4 with 3 a day: PR #85 closes 3, then closes 2 and opens 1, then opens 3 (positions 2, -1, -4)
    p = mini([10] * 7, adv=30.0)
    r = AD.execute(p, model(max_participation=0.1), pol(1, on_liquidity_shortfall="clip"),
                   contracts=plan(7, {0: 3, 1: 5, 2: -4}))
    assert r.positions[:, 0].tolist()[1:] == [3, 5, 2, -1, -4, -4]
    assert all(abs(r.positions[t, 0]) <= max(abs(r.positions[t - 1, 0]), 4) for t in range(3, 7))


# ================================================================== 4. rolls
def roll_panel(adv=1e6):
    # held month A until day 2's close, then month B (100 points above): a calendar gap that is never P&L
    lv = [50, 51, 152, 154, 155]
    ex = [50, 51, 52, 154, 155]
    return mini(lv, exit_level=ex, roll=[0, 0, 1, 0, 0], adv=adv)


@pytest.mark.parametrize("new,old_leg,new_leg,moved,reasons", [
    (5, -5, 5, 5, ("roll", "roll")),
    (8, -5, 8, 5, ("roll", "roll+decision")),
    (2, -5, 2, 2, ("roll+decision", "roll")),
    (-3, -5, -3, 0, ("decision", "decision")),
    (0, -5, None, 0, ("decision",)),
])
def test_roll_day_table_matches_pr85_design_section_7(new, old_leg, new_leg, moved, reasons):
    r = AD.execute(roll_panel(), model(half_spread_ticks=1.0), pol(1), contracts=plan(5, {0: 5, 1: new}))
    day2 = [f for f in r.fills if f.day == 2]
    assert [f.filled for f in day2] == [x for x in (old_leg, new_leg) if x is not None]
    assert tuple(f.reason for f in day2) == reasons
    assert [e.contracts for e in r.rolls] == ([moved] if moved else [])
    assert r.gross[2, 0] == 5 * (52 - 51) * SYNX.point_value        # the old month's own change, no calendar gap
    assert r.positions[2, 0] == new
    if moved:
        assert r.rolls[0].calendar_gap_points == 100


def test_a_roll_pays_both_legs():
    base = AD.execute(roll_panel(), model(commission=1.0, half_spread_ticks=1.0), pol(1), contracts=plan(5, {0: 5}))
    assert base.totals()["commission"] == 5 + 5 + 5                 # open 5, roll out 5, roll in 5
    assert base.totals()["spread"] == 15 * 1.0 * SYNX.point_value


def test_a_roll_that_cannot_complete_fails_closed():
    p = roll_panel(adv=[1e6, 30.0, 30.0, 1e6, 1e6])                 # the roll day uses day 1's estimate: cap 3
    with pytest.raises(E.RollError):
        AD.execute(p, model(max_participation=0.1), pol(1, on_liquidity_shortfall="clip"), contracts=plan(5, {0: 5, 1: 6}))
    with pytest.raises(E.LiquidityError):
        AD.execute(p, model(max_participation=0.1), pol(1), contracts=plan(5, {0: 5, 1: 6}))
    # holding 3 with cap 3: the roll completes; only the increase beyond the rolled 3 is clipped (as PR #85)
    r = AD.execute(p, model(max_participation=0.1), pol(1, on_liquidity_shortfall="clip"), contracts=plan(5, {0: 3, 1: 5}))
    assert [f.filled for f in r.fills if f.day == 2] == [-3, 3] and r.rolls[0].contracts == 3
    assert r.positions[3, 0] == 5 and r.unfilled[0].leg == "roll_in"
    gap = mini([50, 51, 152, 154], exit_level=[50, 51, np.nan, 154], roll=[0, 0, 1, 0])
    with pytest.raises(E.RollError):
        AD.execute(gap, model(), pol(1, on_missing_price="hold"), contracts=plan(4, {0: 1}))


# ================================================================== 5. missing prices and FX
def test_hold_keeps_the_last_mark_and_books_the_gap_when_the_price_returns():
    p = mini([10, 11, np.nan, np.nan, 15, 16])
    r = AD.execute(p, model(), pol(1, on_missing_price="hold"), contracts=plan(6, {0: 2}))
    assert [d for d, _ in r.stale_marks] == [2, 3]
    assert r.gross[4, 0] == 2 * (15 - 11) * SYNX.point_value
    assert r.gross.sum() == 2 * (16 - 11) * SYNX.point_value     # filled at day 1's 11 (lag 1)
    with pytest.raises(E.MissingInputError):
        AD.execute(p, model(), pol(1), contracts=plan(6, {0: 2}))


def test_missing_fx_or_liquidity_always_stops_the_run():
    syne = F.ROOTS["SYNE"][0]
    p = mini([3000.0, 3000.0, 3000.0], inst=syne, fx={"EUR": np.array([1.1, np.nan, 1.1])})
    with pytest.raises(E.MissingInputError, match="EURUSD"):       # even though the day's P&L is zero
        AD.execute(p, model("SYNE", fee="EUR"), pol(1, on_missing_price="hold"), contracts=plan(3, {0: 1}))
    q = mini([10, 10, 10], adv=[np.nan, 1e6, 1e6])
    with pytest.raises(E.MissingInputError, match="ADV"):
        AD.execute(q, model(), pol(1), contracts=plan(3, {0: 1}))


def test_foreign_roots_convert_at_the_days_fix_and_fx_conversion_cost_is_charged():
    syne = F.ROOTS["SYNE"][0]
    fx = {"EUR": np.array([1.0, 1.2, 1.5, 2.0])}
    p = mini([3000.0, 3000.0, 3010.0, 3020.0], inst=syne, fx=fx)
    r = AD.execute(p, C.CostModel("t", (("SYNE", terms(fee="USD", commission=1.0, fxc=10.0)),)), pol(1),
                   contracts=plan(4, {0: 2}))
    assert r.gross[2, 0] == pytest.approx(2 * 10 * 10 * 1.5)
    assert r.gross[3, 0] == pytest.approx(2 * 10 * 10 * 2.0)
    assert r.parts["commission"][1, 0] == 2.0                       # fee currency is USD: not converted
    assert r.parts["fx_conversion"][2, 0] == pytest.approx(200 * 1.5 * 10 / 1e4)
    assert r.fx_conversion_unmodelled == ()
    r2 = AD.execute(p, model("SYNE", fee="EUR", commission=1.0), pol(1), contracts=plan(4, {0: 2}))
    assert r2.parts["commission"][1, 0] == pytest.approx(2.0 * 1.2) and r2.fx_conversion_unmodelled == ("SYNE",)


# ================================================================== 6. conservation and identity
def test_net_is_gross_minus_costs_every_day_and_root():
    p = F.world(300)
    r = AD.execute(p, F.synthetic_costs(), pol(1, capital=1e7, on_liquidity_shortfall="clip"),
                   weights=F.reversal_weights(p))
    assert np.array_equal(r.net, r.gross - sum(r.parts[k] for k in AD.COST_PARTS))
    assert np.all(r.costs >= -1e-9)


def test_cash_identity_on_usd_roots():
    p = F.world(300, roots=("SYNA", "SYNR"))
    cm = F.synthetic_costs(("SYNA", "SYNR"))
    r = AD.execute(p, cm, pol(1, capital=1e7), weights=F.trend_weights(p))
    insts = {i.root: i for i in p.instruments}
    cash = sum(-f.filled * f.fill_price * insts[f.root].point_value - f.commission - f.exchange_fee for f in r.fills)
    final = sum(r.positions[-1, a] * p.level[-1, a] * insts[root].point_value for a, root in enumerate(p.roots))
    assert r.net.sum() == pytest.approx(cash + final, rel=1e-10, abs=1e-6)


def test_result_hash_is_stable_and_moves_with_every_input():
    p = F.world(200)
    W = F.trend_weights(p, lookback=20)
    run = lambda **kw: AD.execute(kw.get("p", p), kw.get("c", F.synthetic_costs()), kw.get("pl", pol(1, capital=1e7)),
                                  weights=W).result_hash()
    h = run()
    assert h == run()
    assert h != run(pl=pol(2, capital=1e7))
    assert h != run(c=F.synthetic_costs().scaled(1.5))
    lv = np.array(p.level)
    lv[150, 0] += 0.01
    ex = np.array(p.exit_level)
    ex[150, 0] += 0.01
    p2 = PN.SettlementPanel(days=p.days, instruments=p.instruments, level=lv, exit_level=ex, roll=p.roll, adv=p.adv,
                            vol_points=p.vol_points, base_currency="USD", fx=dict(p.fx))
    assert p2.digest() != p.digest() and run(p=p2) != h
    with pytest.raises(ValueError):
        p.level[0, 0] = 1.0                                         # the panel is read-only


# ================================================================== 7. provenance and the realism gate
def test_refused_and_incomplete_provenance():
    for bad in PV.REFUSED:
        with pytest.raises(E.ProvenanceError):
            PV.Source(bad, "x")
    with pytest.raises(E.ProvenanceError):
        PV.Source("literature_estimate")                          # no reference
    with pytest.raises(E.ProvenanceError):
        PV.Source("recorded", "quotes")                           # known needs its dates
    s = PV.Source("recorded", "quotes", date(2010, 1, 1), date(2012, 12, 31))
    assert s.for_window(date(2011, 1, 1), date(2012, 1, 1)) is s
    x = s.for_window(date(2005, 1, 1), date(2011, 1, 1))
    assert x.kind == "extrapolated" and x.cls == "estimated"


def test_scaled_costs_are_scenario_class_and_keep_their_origin():
    cm = F.fixture_sourced_costs().scaled(2.0)
    t = cm.for_root("SYNA")
    assert t.half_spread_ticks.value == 1.0 and t.half_spread_ticks.source.kind == "scenario"
    assert "literature_estimate" in t.half_spread_ticks.source.reference
    assert t.max_participation.value == 0.1                         # the cap is not scaled


def historical_world(**kw):
    # synthetic numbers labelled "historical" ONLY to exercise the gate's success branch; never a real panel
    return F.world(260, data_kind="historical", **kw)


def test_labels_follow_the_requirements():
    p = historical_world()
    W = F.trend_weights(p)
    run = lambda c, k=1: AD.execute(p, c, pol(k, capital=1e7, on_liquidity_shortfall="clip"), weights=W)
    assert RL.assess(run(F.fixture_sourced_costs(), 0)).label == "throughput_only"
    a = RL.assess(run(F.synthetic_costs()))
    assert a.label == "screening_net" and a.cost_class == "scenario" and any(u.startswith("R4") for u in a.unmet)
    ok = RL.assess(run(F.fixture_sourced_costs()))
    assert ok.label == "exploratory_grade" and ok.unmet == () and ok.cost_class == "estimated"
    no_fxc = C.CostModel("x", tuple((r, replace(t, fx_conversion_bps=None)) for r, t in F.fixture_sourced_costs().terms))
    assert any(u.startswith("R8") for u in RL.assess(run(no_fxc)).unmet)
    stale = RL.assess(run(F.fixture_sourced_costs(known_to=date(2001, 3, 31))))
    assert stale.cost_class == "estimated" and any("extrapolated" in w for w in stale.warnings)


def test_same_close_statistics_are_renamed_and_cannot_be_presented():
    p = historical_world()
    W = F.reversal_weights(p)
    r0 = AD.execute(p, F.fixture_sourced_costs(), pol(0, capital=1e7, on_liquidity_shortfall="clip"), weights=W)
    s = r0.summary()
    assert s["label"] == "throughput_only" and s["realistic_return_claims"] is False
    assert s["stats"] and all(k.startswith("same_close_optimistic_") for k in s["stats"])
    rows = S.grid(p, F.fixture_sourced_costs(), pol(0, capital=1e7, on_liquidity_shortfall="clip"), weights=W,
                  lags=(0, 1))
    with pytest.raises(E.OptimisticExecutionError, match="throughput_only"):
        RL.present_trading_return(r0, rows)


def test_present_trading_return_needs_grade_historical_data_and_sensitivity():
    costs = F.fixture_sourced_costs()
    pl = pol(1, capital=1e7, on_liquidity_shortfall="clip")
    p = historical_world()
    W = F.trend_weights(p)
    r = AD.execute(p, costs, pl, weights=W)
    with pytest.raises(E.OptimisticExecutionError, match="R9"):
        RL.present_trading_return(r, S.grid(p, costs, pl, weights=W, lags=(1,)))
    rows = S.grid(p, costs, pl, weights=W)
    out = RL.present_trading_return(r, rows)
    assert out["evidence"] is False and out["realistic_return_claims"] is False and out["label"] == "exploratory_grade"
    ps = F.world(260)
    rs = AD.execute(ps, costs, pl, weights=F.trend_weights(ps))
    with pytest.raises(E.OptimisticExecutionError, match="synthetic"):
        RL.present_trading_return(rs, S.grid(ps, costs, pl, weights=F.trend_weights(ps)))
    with pytest.raises(E.OptimisticExecutionError):
        RL.present_trading_return(SC.series(np.ones((40, 1)), np.zeros((40, 1)), warmup=21, fence=40, lag=1, c=0, k=0,
                                            data_kind="historical"), rows)


# ================================================================== 8. how assumptions change performance
@pytest.fixture(scope="module")
def world():
    return F.world()


def test_the_reversal_exists_only_under_same_close(world):
    W = F.reversal_weights(world)
    pl = pol(1, capital=1e7, on_liquidity_shortfall="clip")
    gap = S.optimism_gap(world, F.synthetic_costs(), pl, weights=W)
    assert gap["same_close_sharpe"] > 3 and gap["delayed_sharpe"] < 0 and gap["gap_sharpe"] > 3
    assert gap["same_close_label"] == "throughput_only"
    g1 = AD.execute(world, F.synthetic_costs().scaled(0.0), pl, weights=W).stats()
    assert abs(g1["sharpe"]) < 1.0                                  # gross at lag 1: nothing to earn
    assert S.break_even_multiple(world, F.synthetic_costs(), pl, weights=W) == 0.0


def test_same_close_bias_can_have_either_sign(world):
    gap = S.optimism_gap(world, F.synthetic_costs(), pol(1, capital=1e7, on_liquidity_shortfall="clip"),
                         weights=F.trend_weights(world))
    assert gap["gap_sharpe"] < 0                                    # a trend loses the lag-1 reversal at same close


def test_trend_survives_the_lag_but_not_unlimited_costs(world):
    pl = pol(1, capital=1e7, on_liquidity_shortfall="clip")
    W = F.trend_weights(world)
    rows = S.grid(world, F.synthetic_costs(), pl, weights=W, lags=(1,), multiples=(0, 0.5, 1, 2, 4, 8, 16))
    nets = [r["net"] for r in rows]
    assert all(b <= a + 1e-6 for a, b in zip(nets, nets[1:]))       # never better with higher costs
    assert nets[2] > 0 and nets[-1] < 0
    be = S.break_even_multiple(world, F.synthetic_costs(), pl, weights=W)
    assert 4 < be < 16
    assert AD.execute(world, F.synthetic_costs().scaled(be + 0.01), pl, weights=W).totals()["net"] <= 0


def test_spread_and_slippage_shocks_never_improve_net(world):
    n, A = world.shape
    W = F.reversal_weights(world)
    pl = pol(1, capital=1e7, on_liquidity_shortfall="clip")
    base = AD.execute(world, F.synthetic_costs(), pl, weights=W)
    rng = np.random.default_rng(1)
    sh = AD.Shocks("random widening", spread=1 + 3 * rng.random((n, A)), slippage=1 + 3 * rng.random((n, A)))
    hit = AD.execute(world, F.synthetic_costs(), pl, weights=W, shocks=sh)
    assert np.array_equal(hit.positions, base.positions)
    price_moving = lambda r: sum(r.parts[k] for k in AD.COST_PARTS if k != "fx_conversion")
    assert np.all(price_moving(hit) >= price_moving(base) - 1e-6)   # fx conversion is on the net local amount
    assert hit.totals()["net"] < base.totals()["net"]
    assert hit.result_hash() != base.result_hash()


def test_a_liquidity_drought_leaves_targets_unmet_and_costs_more_per_contract(world):
    n, A = world.shape
    W = F.reversal_weights(world)
    pl = pol(1, capital=1e7, on_liquidity_shortfall="clip")
    base = AD.execute(world, F.synthetic_costs(), pl, weights=W)
    dry = AD.Shocks("drought", adv=np.where((np.arange(n) % 63 > 5)[:, None], 0.02, 1.0) * np.ones((n, A)))
    hit = AD.execute(world, F.synthetic_costs(), pl, weights=W, shocks=dry)
    assert len(hit.unfilled) > len(base.unfilled) + 50
    per = lambda r: r.totals()["impact"] / r.totals()["contracts_traded"]
    assert per(hit) > per(base)
    with pytest.raises(E.LiquidityError):
        AD.execute(world, F.synthetic_costs(), pol(1, capital=1e7), weights=W, shocks=dry)


def test_missing_data_hold_versus_raise_on_the_fixture():
    miss = [(t, "SYNA") for t in range(100, 104)] + [(200, "SYNE")]
    p = F.world(300, missing=miss)
    W = F.trend_weights(p)
    with pytest.raises(E.MissingInputError):
        AD.execute(p, F.synthetic_costs(), pol(1, capital=1e7), weights=W)
    r = AD.execute(p, F.synthetic_costs(), pol(1, capital=1e7, on_missing_price="hold"), weights=W)
    assert {(d, s) for d, s in r.stale_marks} <= set(miss) and r.stale_marks
    assert np.array_equal(r.net, r.gross - r.costs)


def test_hte_equivalent_coefficients_match_a_contract_fill_without_rounding():
    t = terms(half_spread_ticks=2.0, slippage_ticks=1.0, commission=2.5, exchange_fee=0.5, impact_coefficient=0.4)
    price, adv, vol, cap = 64.0, 5000.0, 0.9, 1e7
    c, k = C.hte_equivalent_coefficients(SYNA, t, price=price, adv=adv, vol_points=vol, capital=cap)
    n = 40
    dW = n * price * SYNA.point_value / cap
    f = C.fill(SYNA, t, day=0, leg="outright", reason="decision", requested=n, quantity=n, ref=price, adv=adv,
               vol_points=vol, liquidity_day=0)
    unrounded = f.spread + f.slippage + f.impact + f.commission + f.exchange_fee
    assert (c * dW + k * dW ** 1.5) * cap == pytest.approx(unrounded, rel=1e-12)
    assert C.one_way_cost_fraction(SYNA, t, price=price, contracts=n, adv=adv, vol_points=vol) * n * price * 1000 \
        == pytest.approx(unrounded + f.rounding, rel=1e-12)


# ================================================================== 9. the HTE-shaped tier
def hte_align(P, R, warmup, fence):          # HTE kernels.align at 232d0d6, restated
    return P[warmup - 1: fence - 1], R[warmup:fence]


def test_align_lagged_at_zero_is_hte_and_lag_moves_the_position_rows():
    rng = np.random.default_rng(3)
    P, R = rng.standard_normal((80, 4)), rng.standard_normal((80, 4))
    for a, b in zip(SC.align_lagged(P, R, 30, 70, 0), hte_align(P, R, 30, 70)):
        assert np.array_equal(a, b)
    Pw, Rw = SC.align_lagged(P, R, 30, 70, 2)
    assert np.array_equal(Pw, P[27:67]) and np.array_equal(Rw, R[30:70])
    with pytest.raises(E.UnitError):
        SC.align_lagged(P, R, 2, 70, 2)


def test_lagged_vol_scales_never_read_returns_after_the_decision():
    rng = np.random.default_rng(4)
    g = rng.standard_normal(120) * 0.01
    act = np.ones(120, bool)
    kw = dict(halflife=10, min_obs=5, target_daily=0.006, cap=5.0)
    for L in (1, 2, 5):
        s = SC.lagged_scales(g, act, lag=L, **kw)
        for i in (20, 60, 100):
            g2 = g.copy()
            g2[i - L:] *= 7.0                                       # change everything the decision could not see
            assert SC.lagged_scales(g2, act, lag=L, **kw)[i] == s[i]
            naive = SC.lagged_scales(g, act, lag=0, **kw)           # HTE's rule kept after shifting the positions
            assert SC.lagged_scales(g2, act, lag=0, **kw)[i] != naive[i]   # ... reads the future


def test_screening_tier_reproduces_the_reversal_collapse(world):
    ch = F.same_contract_changes(world)
    P = np.nan_to_num(F.reversal_weights(world))
    m = {L: SC.series(P, ch, warmup=300, fence=756, lag=L, c=0.0, k=0.0).net.mean() for L in (0, 1)}
    assert m[0] > 0 and m[1] < m[0] / 5
    r = SC.series(P, ch, warmup=300, fence=756, lag=1, c=1e-4, k=0.0)
    assert RL.assess(r).label == "screening_net"


# ================================================================== 10. isolation
STDLIB_OK = {"__future__", "dataclasses", "datetime", "decimal", "hashlib", "json", "math", "re", "types"}


def _py_files():
    return sorted(PKG.glob("*.py"))


def test_imports_only_the_standard_library_numpy_and_itself():
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in STDLIB_OK | {"numpy"}, (f.name, a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert node.module.split(".")[0] in STDLIB_OK | {"numpy"}, (f.name, node.module)


def test_no_file_network_environment_subprocess_or_broker():
    banned_names = {"open", "exec", "eval", "__import__", "input"}
    banned_attrs = {"environ", "getenv", "system", "popen", "urlopen", "socket", "write_text", "write_bytes",
                    "to_csv", "savetxt", "save", "tofile", "unlink", "remove", "mkdir", "now", "today", "time"}
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    assert fn.id not in banned_names, (f.name, fn.id)
                if isinstance(fn, ast.Attribute):
                    assert fn.attr not in banned_attrs, (f.name, fn.attr)
        text = f.read_text().lower()
        for word in ("ib_insync", "ibapi", "alpaca", "ccxt", "oanda", "interactive brokers", "tradestation",
                     "databento", "norgate", "place_order", "send_order", "api_key"):
            assert word not in text, (f.name, word)


def test_nothing_in_the_repository_imports_it():
    me = Path(__file__).resolve()
    for f in ROOT.rglob("*.py"):
        if PKG in f.parents or f.resolve() == me or ".git" in f.parts:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        assert "execution_realism" not in text, f


def test_running_it_leaves_the_manhattan_config_unchanged():
    cfg = ROOT / "config/manhattan.yaml"
    before = hashlib.sha256(cfg.read_bytes()).hexdigest()
    from manhattan.execution_realism import demo
    t = demo.tables()
    assert t and hashlib.sha256(cfg.read_bytes()).hexdigest() == before
    assert XR.CALIBRATED is False and XR.RESEARCH_ONLY is True


# ================================================================== 11. conformance with the reviewed code
def _from_checkout(env: str, sub: str):
    path = os.environ.get(env)
    if not path:
        pytest.skip(f"{env} not set (needs an unmerged branch checkout)")
    import manhattan
    extra = str(Path(path) / "manhattan")
    before = set(sys.modules)
    manhattan.__path__.append(extra)
    try:
        return importlib.import_module(f"manhattan.{sub}"), before
    finally:
        manhattan.__path__.remove(extra)


def _forget(before):
    for k in set(sys.modules) - before:
        if k.startswith("manhattan."):
            del sys.modules[k]


UTC = timezone.utc


FIXED_TARGETS = {"SYNA": {0: 5, 2: 12, 5: -4, 9: 3, 15: 7, 20: 2, 22: 4, 29: 8, 33: -6, 36: 0},
                 "SYNE": {1: 3, 10: -2, 25: 4}}
FIXED_ADV = {2: 40.0, 5: 30.0, 6: 50.0}                             # caps 4, 3, 5 on those days' estimates


def _pr85_world(X, *, seed=85, targets=FIXED_TARGETS, low_adv=FIXED_ADV, missing_h=(23,)):
    """Two roots in PR #85's own terms and the same world as a panel. The fixed plan has a roll, an increase on the
    roll day, reversals, clipped orders, a held month with no settlement, carries, and a EUR root with a moving fix
    and EUR fees."""
    days = F.weekdays(date(2027, 1, 4), 40)
    close = lambda d: datetime(d.year, d.month, d.day, 19, 30, tzinfo=UTC)
    pub = lambda d: datetime(d.year, d.month, d.day, 21, 0, tzinfo=UTC)
    rnd = random.Random(seed)

    def syna(m):
        return X.ContractSpec(X.contract_id("SYNA", f"2027-{m:02d}"), "SYNA", "SYNX", f"2027-{m:02d}", "USD", 0.01,
                              10.0, 1000.0, 1.0, date(2026, 1, 2), date(2027, m - 1, 27), "physical",
                              first_notice=date(2027, m - 1, 25))

    def syne(m):
        return X.ContractSpec(X.contract_id("SYNE", f"2027-{m:02d}"), "SYNE", "SYNX", f"2027-{m:02d}", "EUR", 0.5,
                              5.0, 10.0, 1.0, date(2026, 1, 2), date(2027, m, 15), "cash")
    specs = [syna(3), syna(4), syna(5), syne(3), syne(4)]
    base_a = np.cumsum([5000] + [rnd.randint(-30, 30) for _ in days[1:]])
    base_e = np.cumsum([4000] + [rnd.randint(-6, 6) for _ in days[1:]])
    prices = {}
    for s in specs:
        m = int(s.delivery_month[5:])
        if s.root == "SYNA":
            prices[s.contract_id] = np.round((base_a + 50 * m) * 0.01, 10)
        else:
            prices[s.contract_id] = (base_e + 20 * m) * 0.5
    H = X.contract_id("SYNA", "2027-03")
    prices[H] = prices[H].copy()
    for t in missing_h:
        prices[H][t] = np.nan                                       # the held month has no settlement that day
    adv = np.full(40, 1000.0)
    for t, v in low_adv.items():
        adv[t] = v
    vol = 0.8 + 0.01 * np.arange(40)
    eurusd = np.round(1.08 + 0.002 * np.sin(np.arange(40)), 6)
    st = [X.Settlement(s.contract_id, d, float(prices[s.contract_id][i]), pub(d)) for s in specs
          for i, d in enumerate(days) if np.isfinite(prices[s.contract_id][i])]
    liq = [X.Liquidity(s.contract_id, float(adv[i]), float(vol[i]), close(d)) for s in specs
           for i, d in enumerate(days)]
    fxr = [X.FxRate("EUR", "USD", d, float(eurusd[i]), pub(d)) for i, d in enumerate(days)]
    market = X.MarketData(calendar=[X.TradingDay(d, close(d)) for d in days], contracts=specs, settlements=st,
                          liquidity=liq, fx=fxr)
    decisions = [X.Decision(r, v, pub(days[t]), inputs_known_at=close(days[t])) for r, tv in targets.items()
                 for t, v in tv.items()]
    roll = X.RollPolicy(buffer_days=35, roll_before_notice_days=10)
    # the held month: H until the roll window opens (10 days before its 25 Feb notice), then J; SYNE month 3
    J = X.contract_id("SYNA", "2027-04")
    held_a = [H if (date(2027, 2, 25) - d).days > 10 else J for d in days]
    held_e = [X.contract_id("SYNE", "2027-03")] * 40
    insts = (I.Instrument("SYNA", "USD", 0.01, 10.0, 1000.0), I.Instrument("SYNE", "EUR", 0.5, 5.0, 10.0))
    panel = PN.SettlementPanel.from_contracts(
        days=days, instruments=insts,
        prices={"SYNA": {c: prices[c] for c in (H, J)}, "SYNE": {held_e[0]: prices[held_e[0]]}},
        held={"SYNA": held_a, "SYNE": held_e}, adv=np.stack([adv, adv], 1), vol_points=np.stack([vol, vol], 1),
        base_currency="USD", fx={"EUR": eurusd})
    contracts = np.full((40, 2), np.nan)
    for a, r in enumerate(("SYNA", "SYNE")):
        for t, v in targets.get(r, {}).items():
            contracts[t, a] = v
    return market, decisions, roll, panel, contracts


def _run_both(X, k, world):
    market, decisions, roll, panel, contracts = world
    kw = dict(fee_currency="USD", commission_per_contract=1.25, exchange_fee_per_contract=0.4,
              half_spread_ticks=0.5, slippage_ticks=0.75, impact_coefficient=0.3, max_participation=0.1,
              margin_funding_bps_per_year=0.0)
    sc = X.CostScenario("synthetic conformance", "synthetic",
                        (("SYNA", X.CostTerms(**kw)), ("SYNE", X.CostTerms(**{**kw, "fee_currency": "EUR"}))))
    ref = X.run(market, decisions, X.ExecutionPolicy("USD", roll, lag=k, on_missing_price="hold",
                                                     on_liquidity_shortfall="clip"), sc)
    mk = lambda fee: terms(fee=fee, commission=1.25, exchange_fee=0.4, half_spread_ticks=0.5,
                           slippage_ticks=0.75, impact_coefficient=0.3, max_participation=0.1)
    cm = C.CostModel("conformance", (("SYNA", mk("USD")), ("SYNE", mk("EUR"))))
    mine = AD.execute(panel, cm, pol(k, on_missing_price="hold", on_liquidity_shortfall="clip"), contracts=contracts)
    return ref, mine, panel


def _assert_same(ref, mine, panel, tag):
    assert len(ref.days) == panel.shape[0]
    for i, day in enumerate(ref.days):
        assert mine.gross[i].sum() == pytest.approx(day.gross, abs=1e-8), (tag, i)
        for part in ("spread", "slippage", "impact", "rounding", "commission", "exchange_fee"):
            assert mine.parts[part][i].sum() == pytest.approx(getattr(day, part), abs=1e-8), (tag, i, part)
        assert mine.turnover[i].sum() == pytest.approx(day.turnover, abs=1e-6), (tag, i)
        assert mine.gross_exposure[i].sum() == pytest.approx(day.gross_exposure, abs=1e-6), (tag, i)
        by_root = {}
        for cid, q in day.positions:
            by_root[cid[:4]] = by_root.get(cid[:4], 0) + q
        assert {r: int(mine.positions[i, a]) for a, r in enumerate(panel.roots) if mine.positions[i, a]} \
            == {r: q for r, q in by_root.items() if q}, (tag, i)
    assert sum(1 for f in mine.fills if f.filled) == sum(1 for f in ref.fills if f.filled), tag
    assert [(e.day, e.contracts) for e in mine.rolls] == [(panel.days.index(e.day), e.contracts)
                                                         for e in ref.rolls], tag
    assert {(d, r) for d, r in mine.stale_marks} == {(i, c[:4]) for i, day in enumerate(ref.days)
                                                     for c in day.stale_marks}, tag
    assert len(mine.unfilled) == len(ref.unfilled), tag


def test_conformance_with_pr85_daily_gross_costs_turnover_positions():
    X, before = _from_checkout("EXEC_REALISM_PR85_CHECKOUT", "execution")
    try:
        for k in (1, 2):
            ref, mine, panel = _run_both(X, k, _pr85_world(X))
            # the plan exercises what it claims to: a roll, a stale mark, clipped and waiting orders, carries
            assert ref.rolls and any(d.stale_marks for d in ref.days) and ref.unfilled
            assert {"decision", "carry", "roll"} <= {f.reason for f in ref.fills}
            _assert_same(ref, mine, panel, k)
    finally:
        _forget(before)


def test_conformance_with_pr85_seeded_fuzz():
    """40 seeded random plans per lag, inside the documented common ground: clipping only on days 0-10 (so no
    position is left flat inside PR #85's earlier-opening window, divergence D1, and no roll is capacity-bound,
    D2), non-zero targets until the last decisions, random missing settlements of the held month under hold."""
    X, before = _from_checkout("EXEC_REALISM_PR85_CHECKOUT", "execution")
    try:
        n_cases = n_unfilled = n_stale = 0
        for seed in range(40):
            rnd = random.Random(1000 + seed)
            nz = lambda: rnd.choice([v for v in range(-12, 13) if v])
            ta = {0: nz(), **{t: nz() for t in sorted(rnd.sample(range(1, 34), rnd.randint(2, 9)))}}
            if rnd.random() < 0.5:
                ta[rnd.randint(34, 37)] = 0
            te = {1: nz(), **{t: nz() for t in sorted(rnd.sample(range(2, 36), rnd.randint(0, 5)))}}
            low = {t: float(rnd.choice([0, 15, 25, 40, 60])) for t in rnd.sample(range(0, 10), rnd.randint(0, 4))}
            miss = tuple(t for t in range(11, 29) if rnd.random() < 0.08)
            for k in (1, 2):
                world = _pr85_world(X, seed=seed, targets={"SYNA": ta, "SYNE": te}, low_adv=low, missing_h=miss)
                ref, mine, panel = _run_both(X, k, world)
                _assert_same(ref, mine, panel, (seed, k))
                n_cases += 1
                n_unfilled += len(ref.unfilled)
                n_stale += sum(1 for d in ref.days if d.stale_marks)
        assert n_cases == 80 and n_unfilled > 20 and n_stale > 10       # the fuzz reaches clipping and gaps
    finally:
        _forget(before)


def test_conformance_with_hte_alignment_and_stage3_at_lag_zero():
    K, before = _from_checkout("EXEC_REALISM_HTE_CHECKOUT", "hte.kernels")
    try:
        assert K.EXECUTION_TIMING == TM.HTE_SAME_CLOSE
        pol_mod = importlib.import_module("manhattan.hte.policy")
        rng = np.random.default_rng(89)
        P = np.where(rng.random((420, 5)) < 0.7, np.round(rng.standard_normal((420, 5)), 2), 0.0)
        R = 0.01 * rng.standard_normal((420, 5))
        for a, b in zip(SC.align_lagged(P, R, 300, 420, 0), K.align(P, R, 300, 420)):
            assert np.array_equal(a, b)
        hp = pol_mod.Policy()
        Pw, Rw = K.align(P, R, 300, 420)
        ref = K.ref_stage3_series(Pw, Rw, 4e-4, 2e-3, hp)
        mine = SC.series(P, R, warmup=300, fence=420, lag=0, c=4e-4, k=2e-3, vol_target_ann=hp.vol_target_ann,
                         vol_halflife=hp.vol_halflife, vol_min_obs=hp.vol_min_obs, leverage_cap=hp.leverage_cap)
        assert np.array_equal(mine.net, ref)                        # bit for bit at lag 0
    finally:
        _forget(before)
