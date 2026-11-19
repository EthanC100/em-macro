"""Synthetic futures execution, cost and roll model (manhattan/execution, docs/manhattan/EXECUTION_MODEL.md).

Every number here is synthetic: made-up contracts (roots SYNA, SYNC, SYNE), made-up prices on a made-up calendar
and made-up cost terms. None is a market value, and nothing is read from a file or the network.
"""
from __future__ import annotations

import ast
import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from manhattan import execution as X
from manhattan.execution import adjust, errors as E
from manhattan.execution.account import Unfilled

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "manhattan/execution"
UTC = timezone.utc
SGT = timezone(timedelta(hours=8))
ROLL = X.RollPolicy(buffer_days=35, roll_before_notice_days=10)


# ------------------------------------------------------------------ synthetic world
def weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def close(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 19, 30, tzinfo=UTC)


def published(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 21, 0, tzinfo=UTC)


def month_add(y: int, m: int, k: int) -> tuple[int, int]:
    n = y * 12 + m - 1 + k
    return n // 12, n % 12 + 1


def syna(month: int, year: int = 2027, **kw) -> X.ContractSpec:
    """Physically settled, USD, quoted in dollars: tick 0.01, multiplier 1,000, tick value 10."""
    py, pm = month_add(year, month, -1)
    dm = f"{year}-{month:02d}"
    args = dict(contract_id=X.contract_id("SYNA", dm), root="SYNA", exchange="SYNX", delivery_month=dm,
                currency="USD", tick_size=0.01, tick_value=10.0, multiplier=1000.0, price_unit_value=1.0,
                first_trade=date(2026, 1, 2), last_trade=date(py, pm, 27), settlement_type="physical",
                first_notice=date(py, pm, 25), initial_margin=5000.0)
    args.update(kw)
    return X.ContractSpec(**args)


def sync(month: int, year: int = 2027) -> X.ContractSpec:
    """Quoted in US cents: tick 0.25 cents, 5,000 units, price unit 0.01 USD, so tick value 12.5 USD."""
    py, pm = month_add(year, month, -1)
    dm = f"{year}-{month:02d}"
    return X.ContractSpec(X.contract_id("SYNC", dm), "SYNC", "SYNX", dm, "USD", 0.25, 12.5, 5000.0, 0.01,
                          date(2026, 1, 2), date(py, pm, 27), "physical", first_notice=date(py, pm, 25))


def syne(month: int, year: int = 2027) -> X.ContractSpec:
    """Cash settled, EUR: tick 0.5, multiplier 10, tick value 5 EUR; last trade on the 15th of the month."""
    dm = f"{year}-{month:02d}"
    return X.ContractSpec(X.contract_id("SYNE", dm), "SYNE", "SYNX", dm, "EUR", 0.5, 5.0, 10.0, 1.0,
                          date(2026, 1, 2), date(year, month, 15), "cash", initial_margin=800.0)


def price_syna(i: int, spec: X.ContractSpec) -> float:
    # an upward-sloping curve (contango of 0.50 a month) that rises 0.10 a day; whole cents
    return round(50.0 + 0.10 * i + 0.50 * int(spec.delivery_month[5:]), 2)


def price_sync(i: int, spec: X.ContractSpec) -> float:
    return 400.0 + 0.25 * (i % 7) + 2.0 * int(spec.delivery_month[5:])


def price_syne(i: int, spec: X.ContractSpec) -> float:
    return 1000.0 - 0.5 * i + 5.0 * int(spec.delivery_month[5:])


def world(n: int = 40, *, roots=("SYNA",), adv: float = 1000.0, vol: float = 0.8, eurusd: float | None = 1.10,
          drop=(), fx_drop=(), extra_specs=(), start: date = date(2027, 1, 4)) -> X.MarketData:
    days = weekdays(start, n)
    specs = list(extra_specs)
    makers = {"SYNA": (syna, price_syna, range(1, 10)), "SYNC": (sync, price_sync, range(1, 10)),
              "SYNE": (syne, price_syne, range(1, 10))}
    pricer = {}
    for r in roots:
        mk, pf, months = makers[r]
        for m in months:
            s = mk(m)
            specs.append(s)
            pricer[s.contract_id] = pf
    px = [X.Settlement(s.contract_id, d, pricer[s.contract_id](i, s), published(d))
          for i, d in enumerate(days) for s in specs if s.tradable_on(d) and s.contract_id in pricer
          and (s.contract_id, d) not in drop]
    liq = [X.Liquidity(s.contract_id, adv, vol, datetime(2026, 12, 31, tzinfo=UTC)) for s in specs]
    fx = [X.FxRate("EUR", "USD", d, eurusd, published(d)) for d in days if d not in fx_drop] if eurusd else []
    return X.MarketData(calendar=[X.TradingDay(d, close(d)) for d in days], contracts=specs, settlements=px,
                        liquidity=liq, fx=fx)


def terms(**kw) -> X.CostTerms:
    t = dict(fee_currency="USD", commission_per_contract=1.0, exchange_fee_per_contract=0.5, half_spread_ticks=0.5,
             slippage_ticks=0.5, impact_coefficient=0.0, max_participation=0.1, margin_funding_bps_per_year=0.0)
    t.update(kw)
    return X.CostTerms(**t)


def scenario(name="synthetic base", roots=("SYNA",), **kw) -> X.CostScenario:
    return X.CostScenario(name, "synthetic", tuple((r, terms(**kw)) for r in roots))


ZERO = dict(commission_per_contract=0.0, exchange_fee_per_contract=0.0, half_spread_ticks=0.0, slippage_ticks=0.0,
            impact_coefficient=0.0)


def policy(**kw) -> X.ExecutionPolicy:
    a = dict(base_currency="USD", roll=ROLL)
    a.update(kw)
    return X.ExecutionPolicy(**a)


def at(d: date, h: int = 20) -> datetime:
    return datetime(d.year, d.month, d.day, h, 0, tzinfo=UTC)


def liq(cid: str, adv=1000.0, vol=0.8, t=datetime(2026, 12, 31, tzinfo=UTC)) -> X.Liquidity:
    return X.Liquidity(cid, adv, vol, t)


def st(cid: str, d: date, p: float) -> X.Settlement:
    return X.Settlement(cid, d, p, published(d))


D0 = date(2027, 1, 4)
T0 = at(D0)                 # after the first close: executes on the second trading day


# ------------------------------------------------------------------ long and short orders
def test_buy_fills_above_and_sell_below_the_reference():
    s = syna(4)
    b = X.fill_order(s, st(s.contract_id, D0, 50.0), 3, liq(s.contract_id), terms(), decided_at=T0 - timedelta(hours=1))
    sl = X.fill_order(s, st(s.contract_id, D0, 50.0), -3, liq(s.contract_id), terms(), decided_at=T0 - timedelta(hours=1))
    assert b.fill_price == pytest.approx(50.01) and sl.fill_price == pytest.approx(49.99)
    assert b.filled == 3 and sl.filled == -3
    for f in (b, sl):
        assert f.execution_cost == pytest.approx(30.0)          # 0.01 points x 1,000 x 3 contracts
        assert f.execution_cost == pytest.approx((f.fill_price - f.reference_price) * f.filled * s.point_value)
        assert f.commission == pytest.approx(3.0) and f.exchange_fee == pytest.approx(1.5)


def test_short_position_earns_when_the_price_falls():
    m = world(roots=("SYNE",))
    r = X.run(m, [X.Decision("SYNE", -2, T0)], policy(), scenario(roots=("SYNE",), fee_currency="EUR", **ZERO))
    # SYNE falls 0.5 a day; 2 short x 0.5 x multiplier 10 = 10 EUR a day, at 1.10 USD per EUR
    assert all(d.gross == pytest.approx(11.0) for d in r.days[2:])
    assert r.days[-1].net_exposure < 0 < r.days[-1].gross_exposure


def test_quantities_must_be_whole_contracts():
    for bad in (1.5, 2.0, True, "3", None):
        with pytest.raises(E.UnitError):
            X.Decision("SYNA", bad, T0)
    s = syna(4)
    with pytest.raises(E.UnitError):
        X.fill_order(s, st(s.contract_id, D0, 50.0), 2.0, liq(s.contract_id), terms(), decided_at=T0)


# ------------------------------------------------------------------ multipliers and units
def test_gross_pnl_uses_multiplier_and_price_unit():
    m = world(roots=("SYNA", "SYNC"))
    sc = X.CostScenario("free", "synthetic", (("SYNA", terms(**ZERO)), ("SYNC", terms(**ZERO))))
    r = X.run(m, [X.Decision("SYNA", 3, T0)], policy(), sc)
    assert r.days[2].gross == pytest.approx(3 * 0.10 * 1000)                   # 300 USD a day
    r = X.run(m, [X.Decision("SYNC", 2, T0)], policy(), sc)
    i = 2
    move = price_sync(i, sync(4)) - price_sync(i - 1, sync(4))                 # 0.25 cents
    assert r.days[i].gross == pytest.approx(2 * move * 5000 * 0.01)             # 25 USD, not 2,500
    held = dict(r.days[i].positions)
    assert X.contract_id("SYNC", "2027-03") in held or X.contract_id("SYNC", "2027-04") in held


def test_tick_value_must_agree_with_the_multiplier_and_price_unit():
    with pytest.raises(E.UnitError, match="price unit"):
        X.ContractSpec("SYNCH2027", "SYNC", "SYNX", "2027-03", "USD", 0.25, 12.5, 5000.0, 1.0,   # cents as dollars
                       date(2026, 1, 2), date(2027, 2, 27), "physical", first_notice=date(2027, 2, 25))


@pytest.mark.parametrize("ccy", ["usd", "US$", "USc", "US", "EURO", "", None])
def test_ambiguous_currency_codes_are_refused(ccy):
    with pytest.raises(E.UnitError):
        syna(3, currency=ccy)


def test_contract_ids_need_a_four_digit_year_and_must_match():
    assert X.contract_id("SYNA", "2027-03") == "SYNAH2027"
    with pytest.raises(E.UnitError):
        syna(3, contract_id="SYNAH7")
    with pytest.raises(E.UnitError):
        syna(3, contract_id="SYNAM2027")
    with pytest.raises(E.UnitError):
        X.contract_id("SYNA", "27-03")


# ------------------------------------------------------------------ tick rounding
def test_tick_rounding_modes():
    assert X.round_to_tick(50.0025, 0.01, "up") == pytest.approx(50.01)
    assert X.round_to_tick(50.0025, 0.01, "down") == pytest.approx(50.00)
    assert X.round_to_tick(50.004, 0.01, "nearest") == pytest.approx(50.00)
    assert X.round_to_tick(70.23, 0.01, "up") == 70.23                         # binary noise is not a tick
    assert X.round_to_tick(0.1 + 0.2, 0.1, "up") == pytest.approx(0.3)
    assert X.round_to_tick(-37.634, 0.01, "down") == pytest.approx(-37.64)     # negative prices work
    assert X.adverse_round(400.1, 0.25, 1) == 400.25 and X.adverse_round(400.1, 0.25, -1) == 400.0
    with pytest.raises(ValueError):
        X.round_to_tick(1.0, 0.01, "sideways")


def test_fill_is_rounded_against_the_trader_and_the_rounding_is_its_own_cost():
    s = syna(4)
    t = terms(half_spread_ticks=0.25, slippage_ticks=0.0)
    b = X.fill_order(s, st(s.contract_id, D0, 50.0), 1, liq(s.contract_id), t, decided_at=T0)
    sl = X.fill_order(s, st(s.contract_id, D0, 50.0), -1, liq(s.contract_id), t, decided_at=T0)
    assert b.fill_price == pytest.approx(50.01) and sl.fill_price == pytest.approx(49.99)
    assert b.spread_cost == pytest.approx(2.5) and b.rounding_cost == pytest.approx(7.5)
    assert sl.spread_cost == pytest.approx(2.5) and sl.rounding_cost == pytest.approx(7.5)


def test_off_tick_settlements_are_refused():
    s = syna(4)
    with pytest.raises(E.UnitError, match="tick"):
        X.MarketData(calendar=[X.TradingDay(D0, close(D0))], contracts=[s], settlements=[st(s.contract_id, D0, 50.005)])


# ------------------------------------------------------------------ spread, slippage, impact and fees
def test_spread_slippage_impact_and_fees_add_up_exactly():
    s = syna(4)
    t = terms(half_spread_ticks=1.0, slippage_ticks=2.0, impact_coefficient=0.1, commission_per_contract=2.0,
              exchange_fee_per_contract=0.75)
    f = X.fill_order(s, st(s.contract_id, D0, 50.0), 4, liq(s.contract_id, adv=100.0, vol=0.5), t, decided_at=T0)
    # impact = 0.1 x 0.5 x sqrt(4 / 100) = 0.01 points; raw = 50 + 0.01 + 0.02 + 0.01 = 50.04 (on the tick)
    assert f.fill_price == pytest.approx(50.04)
    assert (f.spread_cost, f.slippage_cost, f.impact_cost) == pytest.approx((40.0, 80.0, 40.0))
    assert f.rounding_cost == pytest.approx(0.0, abs=1e-9)
    assert f.commission == pytest.approx(8.0) and f.exchange_fee == pytest.approx(3.0)
    assert f.traded_notional == pytest.approx(4 * 50.0 * 1000)


def test_one_way_cost_fraction_matches_a_single_fill():
    s = syna(4)
    t = terms(half_spread_ticks=1.0, slippage_ticks=1.0, commission_per_contract=2.0, exchange_fee_per_contract=1.0)
    f = X.fill_order(s, st(s.contract_id, D0, 50.0), 2, liq(s.contract_id), t, decided_at=T0)
    frac = X.one_way_cost_fraction(s, 50.0, 2, liq(s.contract_id), t)
    assert frac == pytest.approx((f.execution_cost + f.commission + f.exchange_fee) / f.traded_notional)


def test_provenance_cannot_claim_calibration():
    for bad in ("calibrated", "measured", "empirical", ""):
        with pytest.raises(E.UnitError):
            X.CostScenario("x", bad, (("SYNA", terms()),))
    assert X.CALIBRATED is False and X.RESEARCH_ONLY is True


def test_cost_terms_have_no_defaults_and_refuse_negative_values():
    with pytest.raises(TypeError):
        X.CostTerms("USD")                                         # every term must be given
    with pytest.raises(E.UnitError):
        terms(half_spread_ticks=-0.5)
    with pytest.raises(E.UnitError):
        terms(max_participation=1.5)
    with pytest.raises(E.UnitError):
        terms(max_participation=0.0)
    with pytest.raises(E.UnitError):
        X.CostScenario("x", "synthetic", (("SYNA", terms()), ("SYNA", terms())))


# ------------------------------------------------------------------ rolls
def test_roll_happens_on_the_first_day_within_the_window_and_pays_both_legs():
    m = world()
    r = X.run(m, [X.Decision("SYNA", 5, T0)], policy(), scenario())
    first = r.fills[0]
    assert first.day == date(2027, 1, 5) and first.contract_id == "SYNAH2027"   # notice 2027-02-25 > 5 Jan + 35
    assert len(r.rolls) == 1
    ev = r.rolls[0]
    h = X.contract_id("SYNA", "2027-03")
    assert ev.from_contracts == (h,) and ev.to_contract == "SYNAJ2027" and ev.contracts == 5
    assert ev.day == date(2027, 2, 15)                       # first trading day with notice (2-25) − day ≤ 10
    assert (m.specs[h].notice - date(2027, 2, 12)).days > 10
    legs = [f for f in r.fills if f.day == ev.day]
    assert {f.reason for f in legs} == {"roll"} and sorted(f.filled for f in legs) == [-5, 5]
    day = next(d for d in r.days if d.day == ev.day)
    assert day.commission == pytest.approx(10 * 1.0) and day.exchange_fee == pytest.approx(10 * 0.5)
    assert day.spread == pytest.approx(10 * 0.005 * 1000)


def test_roll_yield_is_in_the_same_contract_pnl_and_the_gap_is_not_booked():
    m = world()
    r = X.run(m, [X.Decision("SYNA", 1, T0)], policy(), scenario(**ZERO))
    ev = r.rolls[0]
    assert ev.calendar_gap_points == pytest.approx(0.5)        # J is one month after H: 0.50 of contango
    # every day's gross is the held contract's own change: 0.10 x 1,000, including the roll day and the day after
    assert all(d.gross == pytest.approx(100.0) for d in r.days[2:])
    spliced = adjust.build(m, "SYNA", ROLL, "spliced")
    k = spliced.days.index(ev.day)
    # a naive spliced series books the 1.0-point gap on the roll day as if it were earned
    assert (spliced.values[k] - spliced.values[k - 1]) * 1000 == pytest.approx(100.0 + 500.0)


def test_a_physical_contract_is_never_carried_into_first_notice():
    # zero liquidity on every later month: the roll can never be done under the clip policy
    m = world(n=60, adv=1000.0)
    lq = [liq(c, adv=(1000.0 if c == "SYNAH2027" else 0.0)) for c in m.specs]
    m2 = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                      liquidity=lq)
    with pytest.raises(E.InvalidContractError, match="close of 2027-02-24 .* first notice date 2027-02-25"):
        X.run(m2, [X.Decision("SYNA", 5, T0)], policy(on_liquidity_shortfall="clip"), scenario())


def test_no_eligible_contract_is_an_invalid_contract_error():
    m = world(n=5)
    one = [s for s in m.specs.values() if s.delivery_month <= "2027-02"]
    m2 = X.MarketData(calendar=m.calendar, contracts=one, settlements=[v for v in m.settlements.values()
                                                                        if v.contract_id in {s.contract_id for s in one}],
                      liquidity=[liq(s.contract_id) for s in one])
    with pytest.raises(E.InvalidContractError, match="notice date"):
        X.run(m2, [X.Decision("SYNA", 1, T0)], policy(), scenario())


def test_trading_outside_a_contract_life_is_refused():
    s = syna(4, first_trade=date(2027, 1, 10))
    with pytest.raises(E.InvalidContractError, match="not listed"):
        s.require_tradable(D0)
    with pytest.raises(E.InvalidContractError):
        X.ContractSpec("SYNAH2027", "SYNA", "SYNX", "2027-03", "USD", 0.01, 10.0, 1000.0, 1.0, date(2027, 3, 1),
                       date(2027, 2, 1), "cash")


def test_roll_policy_must_leave_room():
    with pytest.raises(E.UnitError):
        X.RollPolicy(10, 10)
    with pytest.raises(E.UnitError):
        X.RollPolicy(35.0, 10)


# ------------------------------------------------------------------ adjusted versus tradable prices
def test_adjusted_series_are_never_tradable():
    m = world()
    for method in adjust.METHODS:
        a = adjust.build(m, "SYNA", ROLL, method)
        assert a.tradable is False
        p = a.point(5)
        with pytest.raises(TypeError, match="tradable"):
            X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=[p])
        s = m.specs[a.held[5]]
        with pytest.raises(TypeError, match="tradable"):
            X.fill_order(s, p, 1, liq(s.contract_id), terms(), decided_at=T0)


def test_back_adjusted_levels_are_not_prices_but_their_changes_match_the_held_contract():
    m = world()
    diff = adjust.build(m, "SYNA", ROLL, "difference")
    ratio = adjust.build(m, "SYNA", ROLL, "ratio")
    chained = adjust.build(m, "SYNA", ROLL, "chained")
    r = X.run(m, [X.Decision("SYNA", 1, at(date(2027, 1, 1)))], policy(), scenario(**ZERO))   # held from day 0
    gross = [d.gross for d in r.days]
    for k in range(1, len(diff.days)):
        assert (diff.values[k] - diff.values[k - 1]) * 1000 == pytest.approx(gross[k])        # points: exact
        assert ratio.values[k] / ratio.values[k - 1] == pytest.approx(chained.values[k] / chained.values[k - 1])
    # before the roll, the difference-adjusted level is not the price of the contract held that day
    assert diff.values[0] != pytest.approx(m.settlement(diff.held[0], diff.days[0]).price)
    assert diff.values[0] - m.settlement(diff.held[0], diff.days[0]).price == pytest.approx(0.5)   # the later gap
    # and its percentage change differs from the held contract's return
    c, d0, d1 = diff.held[0], diff.days[0], diff.days[1]
    true_ret = m.settlement(c, d1).price / m.settlement(c, d0).price - 1
    assert diff.values[1] / diff.values[0] - 1 != pytest.approx(true_ret, rel=1e-6)


# ------------------------------------------------------------------ currency conversion
def test_foreign_currency_contract_is_converted_at_the_days_rate():
    m = world(roots=("SYNE",), eurusd=1.25)
    r = X.run(m, [X.Decision("SYNE", 3, T0)], policy(), scenario(roots=("SYNE",), fee_currency="EUR", **ZERO))
    assert r.days[2].gross == pytest.approx(3 * -0.5 * 10 * 1.25)
    held = dict(r.days[2].positions)
    (cid, q), = held.items()
    px = m.settlement(cid, r.days[2].day).price
    assert r.days[2].net_exposure == pytest.approx(3 * px * 10 * 1.25)
    assert r.days[2].margin == pytest.approx(3 * 800.0 * 1.25)
    # the same rate quoted the other way gives the same result
    days = [t.day for t in m.calendar]
    inv = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                       liquidity=[liq(c) for c in m.specs], fx=[X.FxRate("USD", "EUR", d, 0.8, published(d)) for d in days])
    r2 = X.run(inv, [X.Decision("SYNE", 3, T0)], policy(), scenario(roots=("SYNE",), fee_currency="EUR", **ZERO))
    assert [d.gross for d in r2.days] == pytest.approx([d.gross for d in r.days])


def test_fees_in_another_currency_are_converted():
    m = world(roots=("SYNE",), eurusd=1.25)
    sc = scenario(roots=("SYNE",), fee_currency="USD", commission_per_contract=2.0, exchange_fee_per_contract=0.0,
                  half_spread_ticks=0.0, slippage_ticks=0.0)
    r = X.run(m, [X.Decision("SYNE", 3, T0)], policy(base_currency="EUR"), sc)
    assert r.days[1].commission == pytest.approx(6.0 / 1.25)


def test_missing_fx_rate_fails_and_no_cross_rate_is_used():
    m = world(roots=("SYNE",), fx_drop=(date(2027, 1, 7),))
    with pytest.raises(E.MissingInputError, match="EUR/USD"):
        X.run(m, [X.Decision("SYNE", 1, T0)], policy(), scenario(roots=("SYNE",), fee_currency="EUR"))
    m = world(roots=("SYNE",), eurusd=1.1)
    with pytest.raises(E.MissingInputError, match="EUR/GBP"):
        m.rate("EUR", "GBP", D0)
    with pytest.raises(E.UnitError):
        X.FxRate("EUR", "EUR", D0, 1.0, published(D0))


# ------------------------------------------------------------------ zero and extreme liquidity
def test_zero_liquidity_refuses_or_fills_nothing():
    s = syna(4)
    z = liq(s.contract_id, adv=0.0)
    with pytest.raises(E.LiquidityError):
        X.fill_order(s, st(s.contract_id, D0, 50.0), 1, z, terms(), decided_at=T0)
    f = X.fill_order(s, st(s.contract_id, D0, 50.0), 1, z, terms(), decided_at=T0, shortfall="clip")
    assert f.filled == 0 and f.execution_cost == 0 and f.commission == 0
    m = world(adv=0.0)
    r = X.run(m, [X.Decision("SYNA", 3, T0)], policy(on_liquidity_shortfall="clip"), scenario())
    assert all(d.positions == () for d in r.days) and r.totals()["costs"] == 0
    assert r.unfilled and all(u.why == "liquidity" and u.filled == 0 for u in r.unfilled)


def test_extreme_liquidity_has_negligible_impact():
    s = syna(4)
    t = terms(half_spread_ticks=0.0, slippage_ticks=0.0, impact_coefficient=1.0)
    f = X.fill_order(s, st(s.contract_id, D0, 50.0), 10, liq(s.contract_id, adv=1e15, vol=1.0), t, decided_at=T0)
    assert f.impact_cost < 1e-2 and f.fill_price == pytest.approx(50.01)      # the rest is one tick of rounding


def test_participation_cap_clips_and_the_rest_is_worked_the_next_day():
    m = world(adv=30.0)                      # cap = floor(0.1 x 30) = 3 contracts a day
    r = X.run(m, [X.Decision("SYNA", 7, T0)], policy(on_liquidity_shortfall="clip"), scenario())
    first = [f.filled for f in r.fills[:3]]
    assert first == [3, 3, 1] and [f.reason for f in r.fills[:3]] == ["decision", "carry", "carry"]
    assert r.unfilled[0] == Unfilled(date(2027, 1, 5), "SYNAH2027", 7, 3, "liquidity", "decision")
    assert r.unfilled[1] == Unfilled(date(2027, 1, 6), "SYNAH2027", 4, 3, "liquidity", "carry")
    with pytest.raises(E.LiquidityError):
        X.run(m, [X.Decision("SYNA", 7, T0)], policy(), scenario())


# ------------------------------------------------------------------ missing metadata and inputs
def test_missing_contract_metadata_is_refused():
    m = world()
    with pytest.raises(E.MissingInputError, match="root 'SYNZ'"):
        X.run(m, [X.Decision("SYNZ", 1, T0)], policy(), scenario())
    with pytest.raises(E.MissingInputError, match="no contract metadata"):
        X.MarketData(calendar=m.calendar, contracts=[], settlements=[st("SYNAH2027", D0, 50.0)])
    with pytest.raises(E.MissingInputError, match="first notice"):
        syna(3, first_notice=None)
    with pytest.raises(E.MissingInputError, match="no cost terms for root"):
        X.run(world(roots=("SYNA", "SYNE")), [X.Decision("SYNE", 1, T0)], policy(), scenario())


def test_missing_settlement_raises_by_default_and_hold_books_the_gap_later():
    gap = date(2027, 1, 12)
    m = world(drop=(("SYNAH2027", gap),))
    with pytest.raises(E.MissingInputError, match="no settlement for held contract"):
        X.run(m, [X.Decision("SYNA", 2, T0)], policy(), scenario(**ZERO))
    r = X.run(m, [X.Decision("SYNA", 2, T0)], policy(on_missing_price="hold"), scenario(**ZERO))
    k = [d.day for d in r.days].index(gap)
    assert r.days[k].gross == 0 and r.days[k].stale_marks == ("SYNAH2027",)
    assert r.days[k + 1].gross == pytest.approx(2 * 2 * 0.10 * 1000)          # two days' move on the return


def test_missing_liquidity_or_margin_fails():
    m = world()
    bare = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()))
    with pytest.raises(E.MissingInputError, match="no liquidity"):
        X.run(bare, [X.Decision("SYNA", 1, T0)], policy(), scenario())
    nomargin = world(roots=("SYNC",))
    with pytest.raises(E.MissingInputError, match="initial margin"):
        X.run(nomargin, [X.Decision("SYNC", 1, T0)], policy(), scenario(roots=("SYNC",), margin_funding_bps_per_year=50))
    with pytest.raises(E.MissingInputError, match="initial margin"):
        X.run(nomargin, [X.Decision("SYNC", 1, T0)], policy(report_margin=True), scenario(roots=("SYNC",)))
    r = X.run(nomargin, [X.Decision("SYNC", 1, T0)], policy(), scenario(roots=("SYNC",)))
    assert r.days[-1].margin is None                                         # unknown, never reported as zero


def test_margin_funding_is_a_separate_cost():
    m = world()
    r = X.run(m, [X.Decision("SYNA", 4, T0)], policy(), scenario(margin_funding_bps_per_year=100.0, **ZERO))
    # held from the close of 5 Jan; Friday 8 Jan -> Monday 11 Jan is three days
    k = [d.day for d in r.days].index(date(2027, 1, 11))
    assert r.days[k].financing == pytest.approx(4 * 5000.0 * 0.01 * 3 / 365)
    assert r.days[k].net == pytest.approx(r.days[k].gross - r.days[k].financing)
    assert r.days[1].financing == 0                                          # nothing was held before the first close


# ------------------------------------------------------------------ timestamps and look-ahead
def test_naive_and_date_timestamps_are_refused():
    with pytest.raises(E.TimestampError, match="naive"):
        X.Decision("SYNA", 1, datetime(2027, 1, 4, 20))
    with pytest.raises(E.TimestampError, match="date"):
        X.Decision("SYNA", 1, D0)
    with pytest.raises(E.TimestampError):
        X.TradingDay(D0, datetime(2027, 1, 4, 19, 30))
    with pytest.raises(E.TimestampError):
        X.Settlement("SYNAH2027", datetime(2027, 1, 4, tzinfo=UTC), 50.0, published(D0))


def test_settlement_known_before_the_close_is_refused():
    s = syna(4)
    with pytest.raises(E.TimestampError, match="before that day's close"):
        X.MarketData(calendar=[X.TradingDay(D0, close(D0))], contracts=[s],
                     settlements=[X.Settlement(s.contract_id, D0, 50.0, close(D0) - timedelta(minutes=1))])
    with pytest.raises(E.TimestampError, match="not in the trading calendar"):
        X.MarketData(calendar=[X.TradingDay(D0, close(D0))], contracts=[s],
                     settlements=[st(s.contract_id, date(2027, 1, 5), 50.0)])


def test_calendar_must_strictly_increase():
    d1 = date(2027, 1, 5)
    with pytest.raises(E.TimestampError):
        X.MarketData(calendar=[X.TradingDay(d1, close(d1)), X.TradingDay(D0, close(D0))], contracts=[])
    with pytest.raises(E.TimestampError):
        X.MarketData(calendar=[X.TradingDay(D0, close(D0)), X.TradingDay(d1, close(D0))], contracts=[])


def test_decision_never_trades_at_a_price_already_printed():
    m = world()
    on_close = X.run(m, [X.Decision("SYNA", 1, close(D0))], policy(), scenario())
    before = X.run(m, [X.Decision("SYNA", 1, close(D0) - timedelta(seconds=1))], policy(), scenario())
    assert on_close.fills[0].day == date(2027, 1, 5)            # exactly at the close: the next day
    assert before.fills[0].day == D0
    lag2 = X.run(m, [X.Decision("SYNA", 1, T0)], policy(lag=2), scenario())
    assert lag2.fills[0].day == date(2027, 1, 6)
    # time zones are converted, not ignored: 03:00 on 5 Jan in Singapore is 19:00 UTC on 4 Jan, before the close
    sg = X.run(m, [X.Decision("SYNA", 1, datetime(2027, 1, 5, 3, 0, tzinfo=SGT))], policy(), scenario())
    assert sg.fills[0].day == D0
    with pytest.raises(E.UnitError):
        policy(lag=0)


def test_inputs_and_liquidity_from_the_future_are_refused():
    with pytest.raises(E.LookAheadError):
        X.Decision("SYNA", 1, T0, inputs_known_at=T0 + timedelta(seconds=1))
    s = syna(4)
    late = liq(s.contract_id, t=T0 + timedelta(hours=1))
    with pytest.raises(E.LookAheadError):
        X.fill_order(s, st(s.contract_id, D0, 50.0), 1, late, terms(), decided_at=T0)
    m = world()
    m2 = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                      liquidity=[liq(c, t=T0 + timedelta(days=3)) for c in m.specs])
    with pytest.raises(E.LookAheadError):
        X.run(m2, [X.Decision("SYNA", 1, T0)], policy(), scenario())


def test_liquidity_used_is_the_latest_known_at_the_decision():
    m = world()
    early = liq("SYNAH2027", adv=10.0, t=datetime(2026, 12, 31, tzinfo=UTC))
    later = liq("SYNAH2027", adv=10_000.0, t=T0 + timedelta(hours=1))
    m2 = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                      liquidity=[early, later] + [liq(c) for c in m.specs if c != "SYNAH2027"])
    assert m2.liquidity_as_of("SYNAH2027", T0) is early
    with pytest.raises(E.LiquidityError):                     # the bigger ADV was not known yet
        X.run(m2, [X.Decision("SYNA", 5, T0)], policy(), scenario())


def test_decisions_after_the_calendar_are_reported_not_executed():
    m = world(n=5)
    last = m.calendar[-1].close_at
    r = X.run(m, [X.Decision("SYNA", 1, last)], policy(), scenario())
    assert r.fills == () and len(r.unexecuted) == 1


def test_conflicting_simultaneous_decisions_are_ambiguous():
    m = world()
    with pytest.raises(E.UnitError, match="ambiguous"):
        X.run(m, [X.Decision("SYNA", 1, T0), X.Decision("SYNA", 2, T0)], policy(), scenario())
    r = X.run(m, [X.Decision("SYNA", 1, T0), X.Decision("SYNA", 2, T0 + timedelta(minutes=5))], policy(), scenario())
    assert r.fills[0].filled == 2                             # the later decision of the day wins


# ------------------------------------------------------------------ zero trades
def test_no_decisions_means_no_trades_and_no_costs():
    m = world()
    r = X.run(m, [], policy(), scenario())
    assert r.fills == () and r.rolls == () and r.totals()["net"] == 0 and r.totals()["turnover"] == 0
    assert all(d.positions == () and d.gross_exposure == 0 and d.margin is not None for d in r.days)
    flat = X.run(m, [X.Decision("SYNA", 0, T0)], policy(), scenario())
    assert flat.fills == () and flat.days == r.days
    assert flat.result_hash() != r.result_hash()                    # same numbers, but a decision was recorded (N4)


def test_zero_trades_need_no_fx_or_liquidity():
    m = world(roots=("SYNE",), eurusd=None)
    r = X.run(m, [], policy(), scenario(roots=("SYNE",), fee_currency="EUR"))
    assert r.totals()["net"] == 0


# ------------------------------------------------------------------ no double counting
def test_net_equals_cash_flows_at_fill_prices_minus_fees():
    m = world(n=60)
    decisions = [X.Decision("SYNA", 4, T0), X.Decision("SYNA", -3, at(date(2027, 1, 20))),
                 X.Decision("SYNA", 2, at(date(2027, 3, 1)))]
    sc = scenario(half_spread_ticks=0.5, slippage_ticks=1.25, impact_coefficient=0.2, margin_funding_bps_per_year=40)
    r = X.run(m, decisions, policy(), sc)
    assert r.rolls, "the plan should include a roll"
    t = r.totals()
    cash = sum(-f.filled * f.fill_price * m.specs[f.contract_id].point_value for f in r.fills)
    last = r.days[-1]
    cash += sum(q * m.settlement(c, last.day).price * m.specs[c].point_value for c, q in last.positions)
    cash -= t["commission"] + t["exchange_fee"] + t["financing"]
    assert t["net"] == pytest.approx(cash, rel=1e-12, abs=1e-6)
    assert t["costs"] == pytest.approx(sum(d.costs for d in r.days))
    for d in r.days:
        assert d.net == pytest.approx(d.gross - d.costs, abs=1e-9)
    assert t["execution_costs"] == pytest.approx(sum(f.execution_cost for f in r.fills))


def test_gross_does_not_depend_on_costs():
    m = world(n=60)
    dec = [X.Decision("SYNA", 4, T0), X.Decision("SYNA", -3, at(date(2027, 1, 20)))]
    free = X.run(m, dec, policy(), scenario(**ZERO))
    dear = X.run(m, dec, policy(), scenario(half_spread_ticks=3, slippage_ticks=2, impact_coefficient=0.5,
                                            commission_per_contract=5))
    assert [d.gross for d in free.days] == pytest.approx([d.gross for d in dear.days])
    assert free.totals()["costs"] == 0 and dear.totals()["costs"] > 0
    assert dear.totals()["net"] == pytest.approx(free.totals()["net"] - dear.totals()["costs"])


def test_turnover_counts_each_contract_traded_once():
    m = world()
    r = X.run(m, [X.Decision("SYNA", 5, T0)], policy(), scenario())
    expected = sum(abs(f.filled) * f.reference_price * 1000 for f in r.fills)
    assert r.totals()["turnover"] == pytest.approx(expected)
    assert r.totals()["contracts_traded"] == 15                 # 5 opened, 5 closed and 5 opened at the roll


# ------------------------------------------------------------------ reproducibility and sensitivity
def scen_grid():
    base = scenario("synthetic base", impact_coefficient=0.1)
    return [base, base.scaled(0.0, "synthetic zero"), base.scaled(2.0, "synthetic x2"), base.scaled(4.0, "synthetic x4")]


def test_scenario_outputs_are_reproducible_and_order_free():
    m = world(n=60)
    dec = [X.Decision("SYNA", 4, T0), X.Decision("SYNA", -2, at(date(2027, 2, 2)))]
    a = X.sensitivity_table(X.run_scenarios(m, dec, policy(capital=1e6), scen_grid()))
    b = X.sensitivity_table(X.run_scenarios(m, list(reversed(dec)), policy(capital=1e6), list(reversed(scen_grid()))))
    assert a == b
    assert [row["scenario"] for row in a] == sorted(row["scenario"] for row in a)
    costs = {row["scenario"]: row["costs"] for row in a}
    assert costs["synthetic zero"] == 0 < costs["synthetic base"]
    assert costs["synthetic base"] < costs["synthetic x2"] < costs["synthetic x4"]
    nets = {row["scenario"]: row["net"] for row in a}
    assert nets["synthetic zero"] > nets["synthetic base"] > nets["synthetic x2"] > nets["synthetic x4"]
    assert len({row["gross"] for row in a}) == 1
    assert a[0]["net_fraction_of_capital"] == pytest.approx(a[0]["net"] / 1e6)


def test_result_hash_is_stable_and_sensitive():
    m = world()
    r1 = X.run(m, [X.Decision("SYNA", 2, T0)], policy(), scenario())
    r2 = X.run(world(), [X.Decision("SYNA", 2, T0)], policy(), scenario())
    r3 = X.run(m, [X.Decision("SYNA", 3, T0)], policy(), scenario())
    assert r1.result_hash() == r2.result_hash() != r3.result_hash()
    assert re.fullmatch(r"[0-9a-f]{64}", r1.result_hash())


def test_scenario_id_is_a_content_address():
    a, b = scenario(), scenario()
    assert a.scenario_id() == b.scenario_id() and a.scenario_id().startswith("AC-")
    assert scenario(slippage_ticks=0.75).scenario_id() != a.scenario_id()
    with pytest.raises(E.UnitError, match="unique"):
        X.run_scenarios(world(), [], policy(), [a, b])


# ------------------------------------------------------------------ no production pathway
ALLOWED_IMPORTS = {"__future__", "bisect", "dataclasses", "datetime", "decimal", "hashlib", "json", "math", "re",
                   "types", "manhattan", "manhattan.spec"}


def _sources():
    return sorted(PKG.glob("*.py"))


def test_the_package_imports_nothing_that_trades_reads_or_records():
    for p in _sources():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:                                   # relative: inside manhattan.execution
                    continue
                names = [node.module]
            else:
                continue
            for n in names:
                assert n in ALLOWED_IMPORTS, f"{p.name} imports {n}"
        text = p.read_text(encoding="utf-8")
        for bad in ("open(", "os.environ", "getenv", "subprocess", "socket", "urllib", "requests", "http.client",
                    "Path(", "write_text", "write_bytes"):
            assert bad not in text, f"{p.name} contains {bad!r}"


def test_no_order_routing_or_broker_names_exist():
    import manhattan.execution.account as A
    import manhattan.execution.contracts as C
    import manhattan.execution.costs as K
    import manhattan.execution.market as M
    names = {n.lower() for mod in (X, A, C, K, M, adjust) for n in dir(mod)}
    for bad in ("submit", "send", "broker", "route", "connect", "credential", "token", "login", "place_order"):
        assert not any(bad in n for n in names), bad


# Test files explicitly authorised to reference the execution model. Each runs PR #85's model only as a reference in
# a cross-check that is skipped unless its gate variable is set. Production code has no exemption.
AUTHORISED_TEST_REFERENCES: dict = {
    # PR #93: the dormant HTE execution bridge's PR #85 cross-check (skipped unless the gate variable is set)
    "tests/test_manhattan_hte_execution_bridge.py": "EXEC_REALISM_PR85_CHECKOUT",
}
# Test directories explicitly authorised (S16, PR #91): the system acceptance suite probes and exercises this model
# from the test tree. Only this directory is exempt; every other file, including every other test, is still scanned,
# and ``test_production_never_reaches_the_authorised_test_directories`` keeps production code from importing it.
AUTHORISED_TEST_DIRS = ("tests/acceptance/",)
# ``\b``: ``manhattan.execution_realism`` is a different package and is not a reference to this model
EXECUTION_REF = re.compile(r"manhattan\.execution\b|from manhattan import[^\n]*\bexecution\b")
_OWN = ("manhattan/execution/", "tests/test_manhattan_execution.py", ".git/")
_ACCEPTANCE_REF = re.compile(r"tests[./]acceptance|\bs16_(capabilities|drivers|fixtures|helpers)\b")


def _execution_references(root: Path, files: dict = AUTHORISED_TEST_REFERENCES,
                          dirs: tuple = AUTHORISED_TEST_DIRS) -> tuple[list, set, list]:
    """(prohibited, authorised files in use, files in authorised directories) for every reference to the model under
    ``root``, outside the model's own package and its own test file."""
    hits, used, in_dirs = [], set(), []
    for p in root.rglob("*.py"):
        rel = p.relative_to(root).as_posix()
        if rel.startswith(_OWN):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if EXECUTION_REF.search(text):
            gate = files.get(rel)
            if gate is not None and gate in text:
                used.add(rel)
            elif rel.startswith(dirs):
                in_dirs.append(rel)
            else:
                hits.append(rel)
    for p in (root / ".github/workflows").glob("*.yml"):
        if "manhattan.execution" in p.read_text(encoding="utf-8") or "manhattan/execution" in p.read_text(encoding="utf-8"):
            hits.append(p.name)
    return hits, used, in_dirs


def test_nothing_in_production_imports_the_execution_model():
    hits, used, in_dirs = _execution_references(ROOT)
    assert used == set(AUTHORISED_TEST_REFERENCES), "an authorised exemption is stale: remove it"
    assert all(r.startswith("tests/") for r in AUTHORISED_TEST_REFERENCES)
    assert all(d.startswith("tests/") and d.endswith("/") for d in AUTHORISED_TEST_DIRS)
    # a declared directory that exists must be in use; one not yet in this tree (S16's suite before PR #91 merges)
    # exempts nothing, and is enforced as soon as it exists
    present = {d for d in AUTHORISED_TEST_DIRS if (ROOT / d).is_dir()}
    assert {d for d in present if any(r.startswith(d) for r in in_dirs)} == present, \
        "an authorised test directory is stale: remove it"
    assert hits == []


def test_the_import_scanner_still_catches_every_reference_form():
    for ref in ("import manhattan.execution", "import manhattan.execution as X", "from manhattan.execution import run",
                "from manhattan.execution.account import Decision", "from manhattan import execution",
                "from manhattan import config, execution as X", 'importlib.import_module("manhattan.execution")',
                "importlib.import_module('manhattan.execution.costs')"):
        assert EXECUTION_REF.search(ref), ref
    for other in ("from manhattan.execution_realism import adapter", "import manhattan.execution_realism.demo",
                  "from manhattan import execution_realism"):
        assert not EXECUTION_REF.search(other), other
    # no production path is exempt, and the dormant packages contain no reference of any form
    assert not any(r.startswith("manhattan/") for r in AUTHORISED_TEST_REFERENCES)
    for pkg in ("manhattan/execution_realism", "manhattan/hte_execution_bridge"):
        for p in (ROOT / pkg).glob("*.py"):
            assert not EXECUTION_REF.search(p.read_text(encoding="utf-8")), p


def test_the_authorised_test_directory_exemption_is_narrow(tmp_path):
    """Production modules, scripts, other tests, a look-alike directory and workflows are still caught; only files
    under an authorised test directory are exempt."""
    for rel, text in {"manhattan/hte/leak.py": "from manhattan.execution import run\n",
                      "manhattan/ops/leak2.py": "from manhattan import config, execution\n",
                      "scripts/leak3.py": "import manhattan.execution.account\n",
                      "tests/test_other.py": "import manhattan.execution\n",
                      "tests/acceptance_evil/x.py": "import manhattan.execution\n",
                      "tests/acceptance/s16_probe.py": "import manhattan.execution\n",
                      "tests/acceptance/s16_realism.py": "import manhattan.execution_realism\n",
                      ".github/workflows/w.yml": "run: python -m manhattan.execution\n"}.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    hits, used, in_dirs = _execution_references(tmp_path, files={}, dirs=("tests/acceptance/",))
    assert sorted(hits) == ["manhattan/hte/leak.py", "manhattan/ops/leak2.py", "scripts/leak3.py",
                            "tests/acceptance_evil/x.py", "tests/test_other.py", "w.yml"]
    assert in_dirs == ["tests/acceptance/s16_probe.py"] and used == set()


def test_production_never_reaches_the_authorised_test_directories():
    """No module outside tests/ may name the acceptance suite, so the exemption cannot carry the model into
    production."""
    hits = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", ".git/")):
            continue
        if _ACCEPTANCE_REF.search(p.read_text(encoding="utf-8", errors="replace")):
            hits.append(rel)
    assert hits == []


def test_running_the_model_changes_no_switch_and_writes_no_file(tmp_path, monkeypatch):
    from manhattan import config as mconfig
    before = hashlib.sha256(mconfig.CONFIG.read_bytes()).hexdigest()
    monkeypatch.chdir(tmp_path)
    X.sensitivity_table(X.run_scenarios(world(n=60), [X.Decision("SYNA", 3, T0)], policy(), scen_grid()))
    assert list(tmp_path.iterdir()) == []
    cfg = mconfig.load()
    assert hashlib.sha256(mconfig.CONFIG.read_bytes()).hexdigest() == before
    assert cfg["forward"]["real_money"] is False and cfg["claims"]["enabled"] is False
    assert cfg["reserve"]["enabled"] is False



def test_a_clipped_roll_moves_both_legs_together():
    m = world(n=60)
    # the new month can absorb 2 contracts a day (0.1 x 20): the old month is closed only as fast as that
    lq = [liq(c, adv=(20.0 if c == "SYNAJ2027" else 1000.0)) for c in m.specs]
    m2 = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                      liquidity=lq)
    r = X.run(m2, [X.Decision("SYNA", 5, T0)], policy(on_liquidity_shortfall="clip"), scenario())
    roll_days = [d for d in r.days if any(c == "SYNAJ2027" for c, _ in d.positions)][:3]
    assert [dict(d.positions) for d in roll_days] == [{"SYNAH2027": 3, "SYNAJ2027": 2},
                                                      {"SYNAH2027": 1, "SYNAJ2027": 4}, {"SYNAJ2027": 5}]
    assert all(sum(q for _, q in d.positions) == 5 for d in r.days[1:])        # exposure never doubles or lapses
    assert [ev.contracts for ev in r.rolls[:3]] == [2, 2, 1]


def test_hold_policy_waits_for_a_price_before_trading():
    m = world(drop=(("SYNAH2027", date(2027, 1, 5)),))
    r = X.run(m, [X.Decision("SYNA", 2, T0)], policy(on_missing_price="hold"), scenario())
    assert r.unfilled[0] == Unfilled(date(2027, 1, 5), "SYNAH2027", 2, 0, "no settlement", "decision")
    assert r.fills[0].day == date(2027, 1, 6) and r.fills[0].reason == "carry"
    with pytest.raises(E.MissingInputError, match="cannot be filled"):
        X.run(m, [X.Decision("SYNA", 2, T0)], policy(), scenario())


def test_a_roll_waits_when_the_new_month_has_no_price():
    roll_day = date(2027, 2, 15)
    m = world(drop=(("SYNAJ2027", roll_day),))
    r = X.run(m, [X.Decision("SYNA", 3, T0)], policy(on_missing_price="hold"), scenario())
    k = [d.day for d in r.days].index(roll_day)
    assert dict(r.days[k].positions) == {"SYNAH2027": 3}                       # still held, not dropped
    assert dict(r.days[k + 1].positions) == {"SYNAJ2027": 3} and r.rolls[0].day == r.days[k + 1].day
    with pytest.raises(E.MissingInputError, match="SYNAJ2027 on 2027-02-15, so the trade cannot be filled"):
        X.run(m, [X.Decision("SYNA", 3, T0)], policy(), scenario())


def test_the_unit_guard_on_the_repositorys_own_contract_table():
    """Section 16 of the design: ledger/settlements.CONTRACTS gives ``multiplier`` as currency per price point, so
    it maps with price_unit_value 1.0; reading the cents-quoted grains' multiplier as bushels is refused."""
    from ledger.settlements import CONTRACTS
    for prod, c in CONTRACTS.items():
        kw = dict(contract_id=X.contract_id("SYNQ", "2027-03"), root="SYNQ", exchange="SYNX", delivery_month="2027-03",
                  currency="USD", tick_size=c["tick"], tick_value=c["tick_value"], multiplier=float(c["multiplier"]),
                  first_trade=date(2026, 1, 2), last_trade=date(2027, 2, 20), settlement_type="cash")
        assert X.ContractSpec(price_unit_value=1.0, **kw).point_value == pytest.approx(c["multiplier"]), prod
        if "cents" in c["unit"]:
            with pytest.raises(E.UnitError, match="price unit"):
                X.ContractSpec(price_unit_value=0.01, **kw)


def test_a_fill_cannot_use_a_price_published_before_the_decision():
    s = syna(4)
    with pytest.raises(E.LookAheadError, match="already seen"):
        X.fill_order(s, st(s.contract_id, D0, 50.0), 1, liq(s.contract_id), terms(), decided_at=published(D0))


# ================================================================== S6 review follow-up
# H1: a decision that executes on the roll day must not bypass the paired roll.
ROLL_DAY = date(2027, 2, 15)                       # first day SYNAH2027 is within 10 days of its notice (2027-02-25)
ON_ROLL_DAY = at(date(2027, 2, 12))                # Friday 20:00 UTC: executes at the 15 Feb settlement
H, J = "SYNAH2027", "SYNAJ2027"


def thin(adv_by: dict, n: int = 60, **kw) -> X.MarketData:
    m = world(n=n, **kw)
    return X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                        liquidity=[liq(c, adv=adv_by.get(c, 1000.0)) for c in m.specs])


def on(r, day):
    return next(x for x in r.days if x.day == day)


def check_books(m, r):
    """Invariants every run must keep: net = gross − costs each day; the net equals cash flows at fill prices plus
    final marks minus fees and financing; turnover and fees are per contract traded; exposure is from positions."""
    t = r.totals()
    cash = sum(-f.filled * f.fill_price * m.specs[f.contract_id].point_value for f in r.fills)
    last = r.days[-1]
    cash += sum(q * m.settlement(c, last.day).price * m.specs[c].point_value for c, q in last.positions)
    assert t["net"] == pytest.approx(cash - t["commission"] - t["exchange_fee"] - t["financing"], rel=1e-12, abs=1e-6)
    for d in r.days:
        assert d.net == pytest.approx(d.gross - d.costs, abs=1e-9)
        fd = [f for f in r.fills if f.day == d.day]
        assert d.commission == pytest.approx(sum(abs(f.filled) * 1.0 for f in fd))
        assert d.exchange_fee == pytest.approx(sum(abs(f.filled) * 0.5 for f in fd))
        assert d.turnover == pytest.approx(sum(f.traded_notional for f in fd))
        mk = {c: m.settlement(c, d.day).price for c, _ in d.positions if m.settlement(c, d.day)}
        if len(mk) == len(d.positions):
            assert d.net_exposure == pytest.approx(sum(q * abs(mk[c]) * 1000 for c, q in d.positions))


@pytest.mark.parametrize("case, mkt, pol", [
    ("thin new month, clip", lambda: thin({J: 20.0}), dict(on_liquidity_shortfall="clip")),
    ("thin old month, clip", lambda: thin({H: 20.0}), dict(on_liquidity_shortfall="clip")),
    ("missing old price, hold", lambda: world(n=60, drop=((H, ROLL_DAY),)), dict(on_missing_price="hold")),
])
def test_h1_a_roll_day_decision_keeps_the_roll_paired(case, mkt, pol):
    m = mkt()
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 5, ON_ROLL_DAY)], policy(**pol), scenario())
    # S6 found net 2, 8 and 10 here: once built, the position stays at the target through every day of the roll
    built = next(i for i, d in enumerate(r.days) if sum(q for _, q in d.positions) == 5)
    assert built < 10 and all(sum(q for _, q in d.positions) == 5 for d in r.days[built:]), case
    assert all(len(d.positions) <= 2 for d in r.days)
    feb = [ev for ev in r.rolls if ev.day.month == 2]
    assert feb and sum(ev.contracts for ev in feb) == 5 and all(ev.to_contract == J for ev in feb), case
    for ev in feb:
        legs = [f for f in r.fills if f.day == ev.day]
        assert sorted(f.roll_quantity for f in legs) == [-ev.contracts, ev.contracts]
        assert {f.reason for f in legs} == {"roll"}                 # the target did not change: a pure roll
    # every day's gross is the held contracts' own change (0.10 a day x 1,000 x 5), the roll days included; after
    # a stale mark the day the price returns books both days' move
    for i in range(built + 1, len(r.days)):
        days_moved = 2 if r.days[i - 1].stale_marks else (0 if r.days[i].stale_marks else 1)
        assert r.days[i].gross == pytest.approx(500.0 * days_moved), (case, r.days[i].day)
    check_books(m, r)


def test_h1_before_the_fix_numbers_are_gone():
    """The three S6 reproductions, as figures on the roll day itself."""
    pos = {}
    for case, m, pol in (("new", thin({J: 20.0}), dict(on_liquidity_shortfall="clip")),
                         ("old", thin({H: 20.0}), dict(on_liquidity_shortfall="clip")),
                         ("missing", world(n=60, drop=((H, ROLL_DAY),)), dict(on_missing_price="hold"))):
        r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 5, ON_ROLL_DAY)], policy(**pol), scenario())
        pos[case] = dict(on(r, ROLL_DAY).positions)
    assert pos == {"new": {H: 3, J: 2}, "old": {H: 3, J: 2}, "missing": {H: 5}}


@pytest.mark.parametrize("new_target, after, roll_n, reasons", [
    (8, {J: 8}, 5, {H: ("roll", -5), J: ("roll+decision", 5)}),          # increase: roll 5, buy 3 more
    (2, {J: 2}, 2, {H: ("roll+decision", -2), J: ("roll", 2)}),          # decrease: roll 2, sell 3 outright
    (-3, {J: -3}, 0, {H: ("decision", 0), J: ("decision", 0)}),          # reversal: nothing is rolled
    (0, {}, 0, {H: ("decision", 0)}),                                    # flat
])
def test_h1_target_changes_on_the_roll_day(new_target, after, roll_n, reasons):
    m = world(n=60)
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", new_target, ON_ROLL_DAY)], policy(), scenario())
    assert dict(on(r, ROLL_DAY).positions) == after
    legs = {f.contract_id: (f.reason, f.roll_quantity) for f in r.fills if f.day == ROLL_DAY}
    assert legs == reasons
    feb = [ev for ev in r.rolls if ev.day == ROLL_DAY]
    assert [ev.contracts for ev in feb] == ([roll_n] if roll_n else [])
    # each contract is traded once and costed once: |H| + |J| contracts of fees
    traded = sum(abs(f.filled) for f in r.fills if f.day == ROLL_DAY)
    assert traded == 5 + abs(new_target)
    assert on(r, ROLL_DAY).commission == pytest.approx(traded * 1.0)
    check_books(m, r)


def test_h1_increase_with_a_thin_new_month_rolls_first_then_buys_what_is_left():
    m = thin({J: 60.0})                                              # J: 6 contracts a day
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 8, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    assert dict(on(r, ROLL_DAY).positions) == {J: 6}
    assert [ev.contracts for ev in r.rolls if ev.day == ROLL_DAY] == [5]
    u = [x for x in r.unfilled if x.day == ROLL_DAY]
    assert u == [Unfilled(ROLL_DAY, J, 8, 6, "liquidity", "roll+decision")]
    nxt = r.days[[d.day for d in r.days].index(ROLL_DAY) + 1]
    assert dict(nxt.positions) == {J: 8}
    assert [(f.reason, f.filled) for f in r.fills if f.day == nxt.day] == [("carry", 2)]
    check_books(m, r)


def test_h1_zero_liquidity_in_the_new_month_keeps_the_old_position():
    m = thin({J: 0.0}, n=40)
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 8, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    assert dict(on(r, ROLL_DAY).positions) == {H: 5}                # neither dropped nor doubled
    u = {x.contract_id: x for x in r.unfilled if x.day == ROLL_DAY}
    assert u[J].why == "liquidity" and u[J].filled == 0 and u[H].why == "paired leg" and u[H].filled == 0
    assert not [f for f in r.fills if f.day == ROLL_DAY] and not [ev for ev in r.rolls if ev.to_contract == J]
    with pytest.raises(E.LiquidityError):
        X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 8, ON_ROLL_DAY)], policy(), scenario())


@pytest.mark.parametrize("missing, new_target, after", [
    (H, 8, {H: 5, J: 3}),       # old month unpriced: the roll waits, the net increase still trades in the new month
    (H, 2, {H: 5}),             # old month unpriced: nothing can reduce the position today
    (J, 8, {H: 5}),             # new month unpriced: neither the roll nor the increase can trade
])
def test_h1_missing_settlements_on_the_roll_day(missing, new_target, after):
    m = world(n=60, drop=((missing, ROLL_DAY),))
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", new_target, ON_ROLL_DAY)],
              policy(on_missing_price="hold"), scenario())
    assert dict(on(r, ROLL_DAY).positions) == after
    assert not [ev for ev in r.rolls if ev.day == ROLL_DAY]
    nxt = r.days[[d.day for d in r.days].index(ROLL_DAY) + 1]
    assert dict(nxt.positions) == {J: new_target}                   # finished the next day
    check_books(m, r)
    with pytest.raises(E.MissingInputError, match=f"{missing} on {ROLL_DAY}"):
        X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", new_target, ON_ROLL_DAY)], policy(), scenario())


def test_h1_roll_quantity_must_fit_the_order():
    s = syna(4)
    with pytest.raises(E.UnitError):
        X.fill_order(s, st(s.contract_id, D0, 50.0), 2, liq(s.contract_id), terms(), decided_at=T0, roll_quantity=3)
    with pytest.raises(E.UnitError):
        X.fill_order(s, st(s.contract_id, D0, 50.0), 2, liq(s.contract_id), terms(), decided_at=T0, roll_quantity=-1)


# M4: physical delivery
def test_m4_a_roll_window_of_zero_still_exits_before_first_notice():
    m = world(n=60)
    r = X.run(m, [X.Decision("SYNA", 2, T0)], policy(roll=X.RollPolicy(35, 0)), scenario())
    ev = r.rolls[0]
    assert ev.from_contracts == (H,) and ev.day == date(2027, 2, 24)       # the last trading day before 25 Feb
    assert all(d.day < m.specs[c].first_notice for d in r.days for c, _ in d.positions)


def test_m4_no_trade_in_a_physical_contract_in_its_delivery_period():
    s = syna(3)                                                       # first notice 2027-02-25, last trade 02-27
    d = date(2027, 2, 25)
    with pytest.raises(E.InvalidContractError, match="delivery period"):
        X.fill_order(s, st(s.contract_id, d, 50.0), -1, liq(s.contract_id), terms(), decided_at=at(d, 12))
    assert s.tradable_on(d) and not s.may_hold_into(d) and s.may_hold_into(date(2027, 2, 24))


def test_m4_a_cash_settled_contract_is_not_carried_past_its_last_trade():
    s = syne(2)                                                       # last trade 2027-02-15
    assert s.may_hold_into(date(2027, 2, 15)) and not s.may_hold_into(date(2027, 2, 16))
    m = world(n=60, roots=("SYNE",))
    lq = [liq(c, adv=(1000.0 if c in ("SYNEF2027", "SYNEG2027") else 0.0)) for c in m.specs]
    m2 = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                      liquidity=lq, fx=list(m.fx.values()))
    with pytest.raises(E.InvalidContractError, match="after its last trading day 2027-02-15"):
        X.run(m2, [X.Decision("SYNE", 1, T0)], policy(on_liquidity_shortfall="clip"),
              scenario(roots=("SYNE",), fee_currency="EUR"))


# M5: fractional-tick costs (convention kept, made visible)
def test_m5_half_a_tick_of_spread_costs_a_whole_tick_and_shows_why():
    s = syna(4)
    t = terms(half_spread_ticks=0.5, slippage_ticks=0.0)
    f = X.fill_order(s, st(s.contract_id, D0, 50.0), 1, liq(s.contract_id), t, decided_at=T0)
    assert f.fill_price == pytest.approx(50.01)
    assert (f.spread_cost, f.rounding_cost, f.execution_cost) == pytest.approx((5.0, 5.0, 10.0))


# L4: FX availability
def fx_world(publish_delay: timedelta):
    m = world(roots=("SYNE",))
    days = [t.day for t in m.calendar]
    rates = [X.FxRate("EUR", "USD", d, 1.10 + 0.01 * i, published(d) + publish_delay) for i, d in enumerate(days)]
    return X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                        liquidity=[liq(c) for c in m.specs], fx=rates)


def test_l4_valuation_is_ex_post_unless_a_cut_off_is_set():
    m = fx_world(timedelta(days=3))                                   # each fix published three days late
    sc = scenario(roots=("SYNE",), fee_currency="EUR")
    r = X.run(m, [X.Decision("SYNE", 1, T0)], policy(), sc)          # ex-post: the day's fix, whenever published
    assert r.meta["fx_valuation"] == "ex_post"
    assert r.days[2].gross == pytest.approx(-0.5 * 10 * (1.10 + 0.02))
    with pytest.raises(E.LookAheadError, match="valuation cut-off"):
        X.run(m, [X.Decision("SYNE", 1, T0)], policy(fx_valuation_cutoff=timedelta(hours=6)), sc)
    on_time = fx_world(timedelta(0))
    r2 = X.run(on_time, [X.Decision("SYNE", 1, T0)], policy(fx_valuation_cutoff=timedelta(hours=6)), sc)
    assert [d.gross for d in r2.days] == pytest.approx([d.gross for d in r.days])
    assert r2.result_hash() != X.run(on_time, [X.Decision("SYNE", 1, T0)], policy(), sc).result_hash()
    with pytest.raises(E.UnitError):
        policy(fx_valuation_cutoff=timedelta(hours=-1))


def test_l4_decision_time_fx_never_uses_a_later_publication():
    m = fx_world(timedelta(days=3))
    t = at(date(2027, 1, 12))
    rate, day = m.rate_as_of("EUR", "USD", t)
    assert day == date(2027, 1, 8) and rate == pytest.approx(1.14)  # 8 Jan's fix, published 11 Jan 21:00; 11 Jan's not yet
    usd_eur, _ = m.rate_as_of("USD", "EUR", t)
    assert usd_eur == pytest.approx(1 / 1.14)
    with pytest.raises(E.LookAheadError, match="published by"):
        m.rate_as_of("EUR", "USD", at(date(2027, 1, 5)))
    with pytest.raises(E.MissingInputError):
        m.rate_as_of("EUR", "GBP", t)


# Low severity
def test_negative_prices_keep_the_exposure_sign_of_the_position():
    neg = syna(4, first_trade=date(2026, 1, 2))
    days = weekdays(D0, 6)
    prices = [-1.00, -1.50, -2.00, -1.20, 0.00, 0.50]
    m = X.MarketData(calendar=[X.TradingDay(d, close(d)) for d in days], contracts=[neg],
                     settlements=[st(neg.contract_id, d, p) for d, p in zip(days, prices)],
                     liquidity=[liq(neg.contract_id)])
    r = X.run(m, [X.Decision("SYNA", 2, at(D0, 12))], policy(roll=X.RollPolicy(30, 5)), scenario(**ZERO))
    assert dict(r.days[0].positions) == {neg.contract_id: 2}
    for d, p in zip(r.days, prices):
        assert d.gross_exposure == pytest.approx(2 * abs(p) * 1000)
        assert d.net_exposure == pytest.approx(2 * abs(p) * 1000)       # long stays long at a negative price
    assert [d.gross for d in r.days[1:]] == pytest.approx([2 * (b - a) * 1000 for a, b in zip(prices, prices[1:])])
    short = X.run(m, [X.Decision("SYNA", -2, at(D0, 12))], policy(roll=X.RollPolicy(30, 5)), scenario(**ZERO))
    assert all(d.net_exposure <= 0 for d in short.days)


def test_deferred_orders_are_labelled_by_what_they_are():
    m = world(adv=30.0)                                             # 3 contracts a day
    r = X.run(m, [X.Decision("SYNA", 7, T0)], policy(on_liquidity_shortfall="clip"), scenario())
    assert [(f.reason, f.filled, f.roll_quantity) for f in r.fills[:3]] == [("decision", 3, 0), ("carry", 3, 0),
                                                                             ("carry", 1, 0)]
    assert [u.reason for u in r.unfilled[:2]] == ["decision", "carry"]


def test_scenario_id_ignores_the_name_and_result_hash_covers_the_policy():
    a = scenario("one name")
    assert a.scenario_id() == scenario("another name").scenario_id()
    assert a.scenario_id() != X.CostScenario("one name", "caller-supplied", a.terms).scenario_id()
    m = world()
    r1 = X.run(m, [X.Decision("SYNA", 2, T0)], policy(), a)
    r2 = X.run(m, [X.Decision("SYNA", 2, T0)], policy(on_missing_price="hold"), a)   # nothing is missing
    assert [d.net for d in r1.days] == [d.net for d in r2.days]
    assert r1.result_hash() != r2.result_hash()
    assert r1.result_hash() == X.run(world(), [X.Decision("SYNA", 2, T0)], policy(), scenario("renamed")).result_hash()


def test_back_adjusted_history_is_revised_by_later_rolls():
    m = world()
    before = adjust.build(m, "SYNA", ROLL, "difference", as_of=date(2027, 2, 12))
    after = adjust.build(m, "SYNA", ROLL, "difference")
    assert before.values[0] == pytest.approx(m.settlement(before.held[0], before.days[0]).price)  # no roll yet
    assert after.values[0] - before.values[0] == pytest.approx(0.5)  # the 15 Feb roll rewrote 4 Jan
    sp_b = adjust.build(m, "SYNA", ROLL, "spliced", as_of=date(2027, 2, 12))
    sp_a = adjust.build(m, "SYNA", ROLL, "spliced")
    assert sp_a.values[: len(sp_b.values)] == sp_b.values           # not revised
    with pytest.raises(E.MissingInputError):
        adjust.build(m, "SYNA", ROLL, "spliced", as_of=date(2026, 12, 1))


# ================================================================== S6 re-review (N1, N2)
def root_book(r, day):
    d = next(x for x in r.days if x.day == day)
    return dict(d.positions)


def gross_contracts(pos: dict) -> int:
    return sum(abs(q) for q in pos.values())


def assert_reversal_safe(r, m, start: date, end_target: int):
    """From ``start``: never both sides open, gross contracts never above max(previous, |target|), no roll legs."""
    prev = None
    for d in r.days:
        if d.day < start:
            prev = dict(d.positions)
            continue
        pos = dict(d.positions)
        signs = {_s(q) for q in pos.values()}
        assert len(signs) <= 1, (d.day, pos)
        assert gross_contracts(pos) <= max(gross_contracts(prev), abs(end_target)), (d.day, pos, prev)
        assert all(f.roll_quantity == 0 for f in r.fills if f.day == d.day and _s(f.filled) == _s(end_target)
                   and not any(ev.day == d.day for ev in r.rolls)), d.day
        prev = pos
    check_books(m, r)


def _s(x):
    return (x > 0) - (x < 0)


def test_n1_reversal_with_a_thin_old_month_closes_before_it_opens():
    m = thin({H: 20.0})                                             # H: 2 contracts a day
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    days = [d.day for d in r.days]
    k = days.index(ROLL_DAY)
    # S6 found {H: +3, J: -4} (gross 7); now the old side is worked down first: +3, +1, then flat and -4
    assert [dict(r.days[k + i].positions) for i in range(3)] == [{H: 3}, {H: 1}, {J: -4}]
    assert [(f.contract_id, f.filled, f.reason) for f in r.fills if f.day == days[k + 2]] == [(H, -1, "carry"),
                                                                                              (J, -4, "carry")]
    u = [x for x in r.unfilled if x.day == ROLL_DAY]
    assert u == [Unfilled(ROLL_DAY, H, -5, -2, "liquidity", "decision"),
                 Unfilled(ROLL_DAY, J, -4, 0, "reversal: old side not closed", "decision")]
    assert not [ev for ev in r.rolls if ev.day >= ROLL_DAY and ev.to_contract == J]    # never booked as a roll
    assert_reversal_safe(r, m, ROLL_DAY, -4)


def test_n1_reversal_with_the_old_month_unpriced_waits():
    m = world(n=60, drop=((H, ROLL_DAY),))
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, ON_ROLL_DAY)],
              policy(on_missing_price="hold"), scenario())
    k = [d.day for d in r.days].index(ROLL_DAY)
    assert dict(r.days[k].positions) == {H: 5}                      # S6 found {H: +5, J: -4} (gross 9)
    assert dict(r.days[k + 1].positions) == {J: -4}
    assert_reversal_safe(r, m, ROLL_DAY, -4)
    with pytest.raises(E.MissingInputError, match=f"{H} on {ROLL_DAY}"):
        X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, ON_ROLL_DAY)], policy(), scenario())


@pytest.mark.parametrize("start, flip", [(5, -4), (-5, 4)])
def test_n1_both_directions_and_several_days(start, flip):
    m = thin({H: 20.0, J: 30.0})                                    # H 2 a day, J 3 a day
    r = X.run(m, [X.Decision("SYNA", start, T0), X.Decision("SYNA", flip, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    k = [d.day for d in r.days].index(ROLL_DAY)
    seq = [dict(r.days[k + i].positions) for i in range(4)]
    s = _s(start)
    assert seq == [{H: 3 * s}, {H: 1 * s}, {J: -3 * s}, {J: -4 * s}]  # close 2, 2, 1; then open 3 (J's cap), 1
    assert_reversal_safe(r, m, ROLL_DAY, flip)


def test_n1_zero_liquidity_in_the_old_month_never_opens_and_fails_closed():
    m = thin({H: 0.0})
    # H could never be traded: the build never happens, so give H liquidity only before the roll
    lq = [liq(H, adv=1000.0, t=datetime(2026, 12, 31, tzinfo=UTC)), liq(H, adv=0.0, t=at(date(2027, 2, 10)))]
    m2 = X.MarketData(calendar=m.calendar, contracts=list(m.specs.values()), settlements=list(m.settlements.values()),
                      liquidity=lq + [liq(c) for c in m.specs if c != H])
    with pytest.raises(E.InvalidContractError, match="first notice date 2027-02-25"):
        X.run(m2, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    # and before that boundary, J is never opened
    short = X.MarketData(calendar=m2.calendar[:33], contracts=list(m.specs.values()),
                         settlements=[v for v in m.settlements.values() if v.day <= m2.calendar[32].day],
                         liquidity=lq + [liq(c) for c in m.specs if c != H])
    r = X.run(short, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    assert all(dict(d.positions) in ({H: 5}, {}) or d.day < ROLL_DAY for d in r.days)
    assert all(J not in dict(d.positions) for d in r.days)


def test_n1_zero_liquidity_in_the_new_month_ends_flat_not_reversed():
    m = thin({J: 0.0}, n=40)
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    assert root_book(r, ROLL_DAY) == {}                             # closing is never blocked by the new month
    assert [u.why for u in r.unfilled if u.day == ROLL_DAY] == ["liquidity"]


def test_n1_reversal_during_an_unfinished_roll():
    m = thin({J: 20.0})                                             # J: 2 a day, so the roll takes three days
    dec = at(ROLL_DAY)                                               # executes on 16 Feb, mid-roll
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", -4, dec)],
              policy(on_liquidity_shortfall="clip"), scenario())
    k = [d.day for d in r.days].index(ROLL_DAY)
    assert dict(r.days[k].positions) == {H: 3, J: 2}               # the roll was under way
    # 16 Feb: J's whole capacity goes to closing its +2 and H closes its +3: flat; then -2 a day in J
    assert [dict(r.days[k + i].positions) for i in range(1, 4)] == [{}, {J: -2}, {J: -4}]
    assert [ev.day for ev in r.rolls if ev.to_contract == J] == [ROLL_DAY]
    assert_reversal_safe(r, m, ROLL_DAY, -4)


def test_n1_reversal_off_the_roll_day_follows_the_same_rule():
    m = world(adv=20.0)                                             # every month: 2 a day
    r = X.run(m, [X.Decision("SYNA", 4, T0), X.Decision("SYNA", -2, at(date(2027, 1, 18)))],
              policy(on_liquidity_shortfall="clip"), scenario())
    seq = [dict(d.positions) for d in r.days if date(2027, 1, 19) <= d.day <= date(2027, 1, 22)]
    assert seq == [{H: 2}, {}, {J: -2}, {J: -2}]                     # a new position opens in the roll rule's month
    assert_reversal_safe(r, m, date(2027, 1, 19), -2)


def late_notice_world(adv_after: float = 0.0) -> X.MarketData:
    """SYNA, but March's first notice (3 Mar) falls after its last trading day (27 Feb)."""
    base = world(n=60)
    late = syna(3, first_notice=date(2027, 3, 3))
    specs = [late if s.contract_id == H else s for s in base.specs.values()]
    px = [st(s.contract_id, t.day, price_syna(i, s)) for i, t in enumerate(base.calendar) for s in specs
          if s.tradable_on(t.day)]
    lq = [liq(s.contract_id, adv=(1000.0 if s.contract_id == H else adv_after)) for s in specs]
    return X.MarketData(calendar=base.calendar, contracts=specs, settlements=px, liquidity=lq)


def test_holding_past_the_last_trade_day_stops_the_run():
    """Restored (S6 N2): last trade binds for a physical contract whose first notice comes later."""
    m = late_notice_world()
    s = m.specs[H]
    assert s.last_trade < s.first_notice and s.notice == s.last_trade
    assert s.may_hold_into(date(2027, 2, 26)) and not s.may_hold_into(date(2027, 3, 1))
    for missing in ("raise", "hold"):
        with pytest.raises(E.InvalidContractError, match="close of 2027-02-26 .* after its last trading day 2027-02-27"):
            X.run(m, [X.Decision("SYNA", 5, T0)], policy(on_liquidity_shortfall="clip", on_missing_price=missing),
                  scenario())


def test_n2_with_liquidity_the_late_notice_contract_rolls_before_its_last_trade():
    m = late_notice_world(adv_after=1000.0)
    r = X.run(m, [X.Decision("SYNA", 5, T0)], policy(), scenario())
    ev = [e for e in r.rolls if H in e.from_contracts]
    assert ev and ev[0].day <= date(2027, 2, 26)
    assert all(H not in dict(d.positions) for d in r.days if d.day > date(2027, 2, 26))


def test_n2_may_hold_into_respects_both_boundaries():
    phys = syna(3)                                                   # first notice 02-25, last trade 02-27
    late = syna(3, first_notice=date(2027, 3, 3))
    cash = syne(3)                                                   # last trade 03-15
    assert [phys.may_hold_into(d) for d in (date(2027, 2, 24), date(2027, 2, 25), date(2027, 2, 28))] == [True, False, False]
    assert [late.may_hold_into(d) for d in (date(2027, 2, 27), date(2027, 2, 28), date(2027, 3, 3))] == [True, False, False]
    assert [cash.may_hold_into(d) for d in (date(2027, 3, 15), date(2027, 3, 16))] == [True, False]
    assert "first notice" in phys.hold_boundary(date(2027, 2, 25))
    assert "last trading day" in late.hold_boundary(date(2027, 2, 28))
    assert phys.hold_boundary(date(2027, 2, 24)) is None


# ------------------------------------------------------------------ adversarial fuzzing (seeded, deterministic)
FUZZ_SEEDS = range(400)


def _fuzz_case(seed: int):
    import random
    rng = random.Random(seed)
    roots = ("SYNA",) if rng.random() < 0.7 else ("SYNA", "SYNE")
    n = 60
    m0 = world(n=n, roots=roots)
    days = [t.day for t in m0.calendar]
    drop = tuple((c, d) for c in m0.specs for d in days[1:-1] if rng.random() < 0.03)
    m1 = world(n=n, roots=roots, drop=drop)
    advs = (0.0, 10.0, 20.0, 30.0, 60.0, 1000.0)
    lq = [liq(c, adv=rng.choice(advs)) for c in m1.specs]
    m = X.MarketData(calendar=m1.calendar, contracts=list(m1.specs.values()), settlements=list(m1.settlements.values()),
                     liquidity=lq, fx=list(m1.fx.values()))
    decs, seen = [], set()
    for _ in range(rng.randint(1, 6)):
        root, t = rng.choice(roots), at(rng.choice(days[:-1]), rng.choice((12, 20)))
        if (root, t) not in seen:                                   # two different targets at one instant are refused
            seen.add((root, t))
            decs.append(X.Decision(root, rng.randint(-8, 8), t))
    pol = (policy(on_liquidity_shortfall="clip", on_missing_price="hold") if rng.random() < 0.7 else
           policy(on_liquidity_shortfall=rng.choice(("clip", "raise")), on_missing_price=rng.choice(("hold", "raise"))))
    sc = X.CostScenario("fuzz", "synthetic", tuple((r, terms(fee_currency="USD", impact_coefficient=0.1))
                                                   for r in roots))
    return m, decs, pol, sc


def _targets_by_day(m, decs, pol):
    from manhattan.execution.account import execution_index
    out = {}
    for dec in sorted(decs, key=lambda x: (x.decided_at, x.root, x.contracts)):
        k = execution_index(m, dec.decided_at, pol.lag)
        if k is not None:
            out.setdefault(k, {})[dec.root] = dec.contracts
    return out


@pytest.mark.parametrize("seed", FUZZ_SEEDS)
def test_fuzz_invariants(seed):
    m, decs, pol, sc = _fuzz_case(seed)
    try:
        r = X.run(m, decs, pol, sc)
    except (E.MissingInputError, E.LiquidityError, E.InvalidContractError):
        return                                                   # fail closed is an allowed outcome
    assert r.result_hash() == X.run(m, list(reversed(decs)), pol, sc).result_hash()
    by_day = _targets_by_day(m, decs, pol)
    target, prev = {}, {}
    for k, d in enumerate(r.days):
        target.update(by_day.get(k, {}))
        pos = dict(d.positions)
        for root in {m.specs[c].root for c in pos} | set(target):
            now = {c: q for c, q in pos.items() if m.specs[c].root == root}
            before = {c: q for c, q in prev.items() if m.specs[c].root == root}
            assert len({_s(q) for q in now.values()}) <= 1, (seed, d.day, now)          # never both sides
            assert gross_contracts(now) <= max(gross_contracts(before), abs(target.get(root, 0))), (seed, d.day)
            assert len(now) <= 2, (seed, d.day, now)
        for c in pos:
            assert m.specs[c].may_hold_into(m.calendar[k + 1].day if k + 1 < len(m.calendar) else d.day), (seed, c)
        fd = [f for f in r.fills if f.day == d.day]
        for root in {f.root for f in fd}:
            legs = [f.roll_quantity for f in fd if f.root == root and f.roll_quantity]
            assert sum(legs) == 0, (seed, d.day, legs)                                    # roll legs pair
            evs = [ev for ev in r.rolls if ev.day == d.day and ev.root == root]
            assert sum(ev.contracts for ev in evs) == sum(x for x in legs if x > 0), (seed, d.day)
        assert d.net == pytest.approx(d.gross - d.costs, abs=1e-9)
        prev = pos
    t = r.totals()
    last = r.days[-1]
    if not last.stale_marks:
        cash = sum(-f.filled * f.fill_price * m.specs[f.contract_id].point_value
                   * (1.10 if m.specs[f.contract_id].currency == "EUR" else 1.0) for f in r.fills)
        cash += sum(q * m.settlement(c, last.day).price * m.specs[c].point_value
                    * (1.10 if m.specs[c].currency == "EUR" else 1.0) for c, q in last.positions)
        assert t["net"] == pytest.approx(cash - t["commission"] - t["exchange_fee"] - t["financing"],
                                         rel=1e-12, abs=1e-6), seed


# ------------------------------------------------------------------ N3: risk-reducing trades before the roll
def test_n3_a_target_cut_on_the_roll_day_reduces_before_it_rolls():
    m = thin({H: 20.0})                                             # H: 2 contracts a day
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 2, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    k = [d.day for d in r.days].index(ROLL_DAY)
    path = [dict(r.days[k + i].positions) for i in range(3)]
    assert path == [{H: 3}, {H: 1, J: 1}, {J: 2}]                  # was {H 3, J 2} (gross 5), {H 1, J 2}, {J 2}
    assert [gross_contracts(p) for p in path] == [3, 2, 2]
    assert [(f.contract_id, f.filled, f.reason, f.roll_quantity) for f in r.fills if f.day == ROLL_DAY] == [
        (H, -2, "decision", 0)]
    day2 = [(f.contract_id, f.filled, f.reason, f.roll_quantity) for f in r.fills if f.day == r.days[k + 1].day]
    assert day2 == [(H, -2, "roll+carry", -1), (J, 1, "roll", 1)]
    check_books(m, r)


def test_n3_cutting_first_never_slows_the_exit_from_the_old_month():
    for adv_h, adv_j in ((20.0, 1000.0), (20.0, 10.0), (1000.0, 10.0), (30.0, 20.0)):
        m = thin({H: adv_h, J: adv_j})
        r = X.run(m, [X.Decision("SYNA", 6, T0), X.Decision("SYNA", 2, ON_ROLL_DAY)],
                  policy(on_liquidity_shortfall="clip"), scenario())
        k = [d.day for d in r.days].index(ROLL_DAY)
        cap_h, cap_j = int(adv_h * 0.1), int(adv_j * 0.1)
        books = [dict(d.positions) for d in r.days[k - 1:k + 8]]
        for before, after in zip(books, books[1:]):
            h0, h1 = before.get(H, 0), after.get(H, 0)
            cut_left = max(h0 + before.get(J, 0) - 2, 0)        # all of the cut is in H (J is below the target)
            x = min(cut_left, cap_h)                            # cut first ...
            y = min(h0 - cut_left, cap_j, cap_h - x)            # ... then the paired roll with what H has left
            y_old = min(h0 - cut_left, cap_j, cap_h)            # roll-first (0.2) for comparison
            x_old = min(cut_left, cap_h - y_old)
            assert h0 - h1 == x + y >= x_old + y_old, (adv_h, adv_j, books)     # never a slower exit
            assert sum(after.values()) >= 2 and gross_contracts(after) <= gross_contracts(before)
        assert books[-1] == {J: 2}, books
        check_books(m, r)


def test_n3_an_increase_still_rolls_before_it_adds():
    m = thin({J: 60.0})                                             # J: 6 a day
    r = X.run(m, [X.Decision("SYNA", 5, T0), X.Decision("SYNA", 8, ON_ROLL_DAY)],
              policy(on_liquidity_shortfall="clip"), scenario())
    assert root_book(r, ROLL_DAY) == {J: 6}                         # roll 5 first, then 1 of the 3 extra


# ------------------------------------------------------------------ N4: input digests in the result identity
def test_n4_market_digest_is_deterministic_and_order_free():
    a, b = world(), world()
    assert a.digest() == b.digest() and re.fullmatch(r"[0-9a-f]{64}", a.digest())
    shuffled = X.MarketData(calendar=a.calendar, contracts=list(reversed(list(a.specs.values()))),
                            settlements=list(reversed(list(a.settlements.values()))),
                            liquidity=[liq(c) for c in reversed(list(a.specs))], fx=list(reversed(list(a.fx.values()))))
    assert shuffled.digest() == a.digest()


@pytest.mark.parametrize("change", ["price", "published", "liquidity", "fx", "metadata", "unused contract", "calendar"])
def test_n4_any_input_change_changes_the_digest_and_the_result_hash(change):
    base = world(roots=("SYNA", "SYNE"))
    specs, px = list(base.specs.values()), list(base.settlements.values())
    lq, fxr, cal = [liq(c) for c in base.specs], list(base.fx.values()), list(base.calendar)
    i = next(j for j, v in enumerate(px) if v.contract_id == H and v.day == date(2027, 1, 7))
    if change == "price":
        px[i] = st(H, px[i].day, px[i].price + 0.01)
    elif change == "published":
        px[i] = X.Settlement(H, px[i].day, px[i].price, px[i].known_at + timedelta(minutes=1))
    elif change == "liquidity":
        lq[0] = liq(lq[0].contract_id, adv=999.0)
    elif change == "fx":
        fxr[0] = X.FxRate("EUR", "USD", fxr[0].day, 1.1000001, fxr[0].known_at)
    elif change == "metadata":
        specs = [syna(3, initial_margin=5001.0) if s.contract_id == H else s for s in specs]
    elif change == "unused contract":
        specs = [syna(9, initial_margin=1.0) if s.contract_id == "SYNAU2027" else s for s in specs]
    else:
        cal[3] = X.TradingDay(cal[3].day, cal[3].close_at - timedelta(minutes=1))
    m = X.MarketData(calendar=cal, contracts=specs, settlements=px, liquidity=lq, fx=fxr)
    assert m.digest() != base.digest()
    dec = [X.Decision("SYNA", 2, T0)]
    assert X.run(m, dec, policy(), scenario()).result_hash() != X.run(base, dec, policy(), scenario()).result_hash()


def test_n4_result_records_both_digests_and_decisions_are_order_free():
    m = world()
    decs = [X.Decision("SYNA", 2, T0), X.Decision("SYNA", -1, at(date(2027, 1, 20)))]
    r = X.run(m, iter(decs), policy(), scenario())                 # a one-shot iterable is read once
    assert r.market_digest == m.digest() and r.fills
    assert r.decisions_digest == X.run(m, list(reversed(decs)), policy(), scenario()).decisions_digest
    other = X.run(m, [X.Decision("SYNA", 2, T0), X.Decision("SYNA", -1, at(date(2027, 1, 20), 12))], policy(), scenario())
    assert other.decisions_digest != r.decisions_digest and other.result_hash() != r.result_hash()


# ================================================================== S6 final hardening (L1, L2)
def test_l1_market_data_cannot_be_changed_after_its_digest():
    m = world()
    before = m.digest()
    old = m.settlement(H, D0)
    with pytest.raises(TypeError):                                   # read-only containers
        m.settlements[(H, D0)] = X.Settlement(H, D0, old.price + 1.0, old.known_at)
    with pytest.raises(TypeError):
        m.specs[H] = syna(3, initial_margin=1.0)
    with pytest.raises(TypeError):
        m.fx[("EUR", "USD", D0)] = None
    with pytest.raises(TypeError):
        m.liquidity[H] = ((), ())
    with pytest.raises(TypeError):
        m.day_index[D0] = 5
    for name in ("settlements", "specs", "fx", "liquidity", "calendar", "day_index", "_frozen"):
        with pytest.raises(AttributeError, match="immutable"):      # no reassignment or deletion either
            setattr(m, name, {})
        with pytest.raises(AttributeError, match="immutable"):
            delattr(m, name)
    assert m.digest() == before and m.settlement(H, D0) is old


def test_l1_a_stale_digest_cannot_survive_even_a_deliberate_bypass():
    """The digest is never cached: if the immutability is bypassed on purpose, the identity follows the contents."""
    from types import MappingProxyType
    m = world()
    first = m.digest()
    r1 = X.run(m, [X.Decision("SYNA", 2, T0)], policy(), scenario())
    old = m.settlement(H, D0)
    changed = dict(m.settlements)
    changed[(H, date(2027, 1, 7))] = st(H, date(2027, 1, 7), m.settlement(H, date(2027, 1, 7)).price + 0.5)
    object.__setattr__(m, "settlements", MappingProxyType(changed))   # bypass, as only a determined caller could
    assert m.digest() != first
    r2 = X.run(m, [X.Decision("SYNA", 2, T0)], policy(), scenario())
    assert r2.market_digest == m.digest() != r1.market_digest
    assert r2.result_hash() != r1.result_hash()
    assert m.settlement(H, D0) is old


def test_l1_construction_copies_its_inputs():
    specs = [syna(3), syna(4)]
    days = weekdays(D0, 3)
    px = [st(s.contract_id, d, 50.0) for s in specs for d in days]
    m = X.MarketData(calendar=[X.TradingDay(d, close(d)) for d in days], contracts=specs, settlements=px)
    first = m.digest()
    px.append(st(specs[0].contract_id, days[0], 51.0))               # the caller's lists are not the model's
    specs.pop()
    assert m.digest() == first and len(m.specs) == 2


DK = T0 - timedelta(hours=1)


def test_l2_decisions_differing_only_in_inputs_known_at_hash_deterministically():
    from manhattan.execution.account import decisions_digest
    a = X.Decision("SYNA", 2, T0)
    b = X.Decision("SYNA", 2, T0, inputs_known_at=DK)
    c = X.Decision("SYNA", 2, T0, inputs_known_at=DK - timedelta(minutes=1))
    perms = [[a, b, c], [c, b, a], [b, a, c], [c, a, b]]
    digests = {decisions_digest(p) for p in perms}
    assert len(digests) == 1 and re.fullmatch(r"[0-9a-f]{64}", digests.pop())
    assert decisions_digest([a, b]) != decisions_digest([a]) != decisions_digest([b])   # each supplied decision counts
    assert decisions_digest([a, a]) != decisions_digest([a])


def test_l2_runs_with_such_decisions_are_deterministic_and_trade_once():
    m = world()
    a = X.Decision("SYNA", 2, T0)
    b = X.Decision("SYNA", 2, T0, inputs_known_at=DK)
    r1 = X.run(m, [a, b], policy(), scenario())
    r2 = X.run(m, [b, a], policy(), scenario())
    assert r1.result_hash() == r2.result_hash()
    assert [f.filled for f in r1.fills[:1]] == [2] and r1.days == X.run(m, [a], policy(), scenario()).days
    # unexecuted decisions (after the calendar) are listed in one order whatever the input order
    last = m.calendar[-1].close_at
    u1 = X.Decision("SYNA", 1, last)
    u2 = X.Decision("SYNA", 1, last, inputs_known_at=last - timedelta(hours=2))
    ra = X.run(m, [u2, u1], policy(), scenario())
    rb = X.run(m, [u1, u2], policy(), scenario())
    assert ra.unexecuted == rb.unexecuted == (u1, u2) and ra.result_hash() == rb.result_hash()


def test_l2_different_targets_at_one_instant_stay_ambiguous():
    m = world()
    with pytest.raises(E.UnitError, match="ambiguous"):
        X.run(m, [X.Decision("SYNA", 2, T0), X.Decision("SYNA", 3, T0, inputs_known_at=DK)], policy(), scenario())


def test_l2_non_decisions_are_refused_before_hashing():
    with pytest.raises(TypeError, match="Decision objects"):
        X.run(world(), [X.Decision("SYNA", 2, T0), ("SYNA", 2, T0)], policy(), scenario())
