"""Milestone E: the point-in-time store, the accounting, the daily and the event backtester, the look-ahead test
and the record of an evaluation (manhattan/engine/). Criteria E-01 to E-07 of docs/manhattan/MANHATTAN_PROGRESS.md.

Synthetic data only: every price path here is written by hand or drawn from a seeded generator, and every
expected number is a hand calculation written beside it.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from manhattan import config as mconfig
from manhattan import ledger as L
from manhattan import roles, spec
from manhattan.engine import accounting, backtest, evaluate, events, lookahead, pit
from manhattan.engine.backtest import Instrument, Strategy

D0 = date(2010, 1, 4)                                    # a Monday
FENCE = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)


def days(n: int, start: date = D0, business: bool = True) -> np.ndarray:
    out, d = [], start
    while len(out) < n:
        if not business or d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return np.array(out, dtype="datetime64[D]")


def window(store: pit.PitStore, start=None, end=None, **kw) -> pit.Window:
    names = store.names()
    lo = min(store.span(n)[0] for n in names) if start is None else start
    hi = max(store.span(n)[1] for n in names) if end is None else end
    return pit.Reader(store, caller="session", domain="test_daily", fence=FENCE, **kw).window(lo, hi)


def one(prices, name="A", lag_days=0, start=D0, business=True) -> pit.PitStore:
    s = pit.PitStore()
    s.add(name, days(len(prices), start, business), prices, lag_days=lag_days)
    return s


# ------------------------------------------------------------------ E-01: the point-in-time store

def test_a_read_as_of_a_day_returns_nothing_that_became_available_later():
    s = pit.PitStore()
    d = days(6)
    s.add("x", d, [1, 2, 3, 4, 5, 6], lag_days=2)                    # Monday's value is usable on Wednesday
    w = window(s)
    for k in range(6):
        p, v = w.as_of("x", d[k])
        known = [i for i in range(6) if d[i] + np.timedelta64(2, "D") <= d[k]]
        assert list(v) == [float(i + 1) for i in known] and list(p) == [d[i] for i in known]
    p, v, a = w.as_of_with_availability("x", d[5])
    assert all(a <= d[5]) and list(a) == [d[i] + np.timedelta64(2, "D") for i in range(len(a))]
    assert list(w.as_of("x", d[5], n=2)[1]) == [4.0, 5.0]             # by the next Monday, Friday's is out and Monday's own is not
    assert w.as_of("x", d[0])[1].size == 0                           # nothing at all is known on the first day


def test_a_revision_shows_from_its_own_day_and_never_erases_the_first_value():
    s = pit.PitStore()
    d = days(5)
    s.add("gdp", [d[0], d[1]], [1.0, 2.0], lag_days=1)
    s.add("gdp", [d[0]], [1.5], available=[d[3]])                    # the first value is revised on day 3
    w = window(s, start=D0, end=d[4].astype(object))
    assert list(w.as_of("gdp", d[1])[1]) == [1.0]
    assert list(w.as_of("gdp", d[2])[1]) == [1.0, 2.0]
    assert list(w.as_of("gdp", d[3])[1]) == [1.5, 2.0] and list(w.as_of("gdp", d[4])[1]) == [1.5, 2.0]
    assert list(w.as_of("gdp", d[2])[1]) == [1.0, 2.0]               # reading the past again still gives the first value
    assert list(w.final("gdp")[1]) == [1.5, 2.0]


def test_availability_is_a_date_or_the_specs_publication_lag_and_one_of_them_is_required():
    s = pit.PitStore()
    d = days(3)
    with pytest.raises(pit.PitError, match="either"):
        s.add("x", d, [1, 2, 3])
    with pytest.raises(pit.PitError, match="either"):
        s.add("x", d, [1, 2, 3], available=d, lag_days=0)
    with pytest.raises(pit.PitError, match="before the period"):
        s.add("x", d, [1, 2, 3], available=d - np.timedelta64(1, "D"))
    with pytest.raises(pit.PitError, match="whole number"):
        s.add("x", d, [1, 2, 3], lag_days=-1)
    with pytest.raises(pit.PitError, match="same length"):
        s.add("x", d, [1, 2])
    fam = spec.family(mechanism="m", mechanism_class="risk_premium", sign="+", counterparty="c", kill_condition="k",
                      tail_exposure="t")
    hyp = spec.hypothesis(fam, domain="test_daily", signal="s", grid={"k": [1]},
                          data_sources=[{"name": "fx", "publication_lag_days": 1}, {"name": "cpi", "publication_lag_days": 45}],
                          primary_binding={"universe_id": "u", "cost_model_id": "c", "sizing_id": "z"})
    lags = pit.lags_from_spec(hyp)
    assert lags == {"fx": 1, "cpi": 45}
    s.add("cpi", d, [1, 2, 3], lag_days=lags["cpi"])
    w = window(s, end=date(2010, 3, 31))
    assert w.as_of("cpi", d[2] + np.timedelta64(44, "D"))[1].size == 2 and w.as_of("cpi", d[2] + np.timedelta64(45, "D"))[1].size == 3
    with pytest.raises(pit.PitError, match="publication_lag_days"):
        pit.lags_from_spec({"data_sources": [{"name": "fx"}]})
    s.add("gap", d, [1.0, np.nan, 3.0], lag_days=0)                  # a missing value is not stored as a value
    assert list(w.final("gap")[1]) == [1.0, 3.0]


def test_the_data_hash_follows_the_content_and_not_the_order_it_was_added_in():
    d = days(4)
    a, b = pit.PitStore(), pit.PitStore()
    a.add("x", d, [1, 2, 3, 4], lag_days=1); a.add("y", d[:2], [5, 6], lag_days=0)
    b.add("y", d[:2], [5, 6], lag_days=0); b.add("x", d[2:], [3, 4], lag_days=1); b.add("x", d[:2], [1, 2], lag_days=1)
    assert a.data_hash() == b.data_hash() and len(a.data_hash()) == 64
    for change in (lambda s: s.add("x", d[:1], [1.0000001], available=[d[3]]),           # a revision
                   lambda s: s.add("z", d[:1], [0.0], lag_days=0)):                       # a new series
        c = pit.PitStore()
        c.add("x", d, [1, 2, 3, 4], lag_days=1); c.add("y", d[:2], [5, 6], lag_days=0)
        change(c)
        assert c.data_hash() != a.data_hash()
    c = pit.PitStore()
    c.add("x", d, [1, 2, 3, 4], lag_days=2); c.add("y", d[:2], [5, 6], lag_days=0)       # only an availability differs
    assert c.data_hash() != a.data_hash()


# ------------------------------------------------------------------ E-02: every read goes through check_read

def test_data_come_out_only_through_a_reader_and_the_fence_decides(monkeypatch):
    s = pit.PitStore()
    d = np.arange(np.datetime64("2019-12-23"), np.datetime64("2020-01-11"))
    s.add("x", d, np.arange(d.size, dtype=float), lag_days=0)
    assert not [n for n in dir(s) if not n.startswith("_") and n not in ("add", "names", "span", "data_hash")]
    reader = pit.Reader(s, caller="session", domain="fx_daily", fence=FENCE)
    w = reader.window(date(2019, 12, 23), date(2019, 12, 31))
    assert w.role == roles.EXPLORATION and w.final("x")[0][-1] == np.datetime64("2019-12-31")
    assert w.as_of("x", date(2020, 1, 10))[0][-1] == np.datetime64("2019-12-31")        # asking later gives no more
    for start, end in ((date(2019, 12, 23), date(2020, 1, 2)), (date(2020, 1, 2), date(2020, 1, 10))):
        with pytest.raises(roles.RoleError):
            reader.window(start, end)                                # 2020 is no role at all for a session
    with pytest.raises(roles.RoleError):                             # forward dates are the runner's
        pit.Reader(s, caller="session", domain="fx_daily", fence=FENCE, freeze=date(2020, 1, 1)).window(date(2020, 1, 2), date(2020, 1, 10))
    for nobody in ("critic", "generator_blind"):
        with pytest.raises(roles.RoleError):
            pit.Reader(s, caller=nobody, domain="fx_daily", fence=FENCE).window(date(2019, 12, 23), date(2019, 12, 31))
    seen = []
    monkeypatch.setattr(roles, "check_read", lambda *a, **k: seen.append((a, k)) or roles.EXPLORATION)
    reader.window(date(2019, 12, 23), date(2019, 12, 24))
    assert len(seen) == 1 and seen[0][0][:4] == ("session", "fx_daily", date(2019, 12, 23), date(2019, 12, 24))


def test_with_the_repositorys_configuration_nothing_after_2019_can_be_read():
    fence = roles.Fence.from_config(mconfig.load())
    assert fence.exploration_end == date(2019, 12, 31) and not fence.enabled
    s = one([1.0, 2.0, 3.0], start=date(2019, 12, 30), business=False)
    reader = pit.Reader(s, caller="session", domain="fx_daily", fence=fence)
    assert reader.window(date(2019, 12, 30), date(2019, 12, 31)).final("A")[1].tolist() == [1.0, 2.0]
    with pytest.raises(roles.RoleError):
        reader.window(date(2019, 12, 30), date(2020, 1, 1))


# ------------------------------------------------------------------ E-03: accounting, against hand calculations

def test_buy_and_hold_is_the_instruments_return():
    led = accounting.run(days(4), [[100.0], [110.0], [99.0], [99.0]], [[1.0], [np.nan], [np.nan], [np.nan]],
                         [True, False, False, False])
    assert led.net == pytest.approx([0.0, 0.10, -0.10, 0.0]) and led.exposure[:, 0] == pytest.approx([1, 1, 1, 1])
    assert led.cost.sum() == 0 and led.turnover.tolist() == [1.0, 0, 0, 0]
    twice = accounting.run(days(3), [[100.0], [110.0], [99.0]], [[2.0], [np.nan], [np.nan]], [True, False, False])
    assert twice.net == pytest.approx([0.0, 0.20, 2 * 1.1 / 1.2 * -0.10])               # 2x, drifted to 1.8333x
    assert twice.exposure[1, 0] == pytest.approx(2 * 1.1 / 1.2)


def test_weights_drift_and_a_trade_costs_its_turnover():
    price = [[100.0, 100.0], [110.0, 100.0], [110.0, 100.0]]
    target = [[0.5, 0.5], [0.5, 0.5], [np.nan, np.nan]]
    led = accounting.run(days(3), price, target, [True, True, False], cost=[0.001, 0.002])
    # day 0: buy 0.5 of each: cost 0.5·0.001 + 0.5·0.002 = 0.0015
    assert led.cost[0] == pytest.approx(0.0015) and led.net[0] == pytest.approx(-0.0015)
    # day 1: A +10%: gross 0.05; drifted weights 0.55/1.05 and 0.50/1.05; back to 0.5 each
    drift = np.array([0.55, 0.50]) / 1.05
    assert led.gross[1] == pytest.approx(0.05)
    assert led.turnover[1] == pytest.approx(np.abs(0.5 - drift).sum()) == pytest.approx(2 * (0.55 / 1.05 - 0.5))
    assert led.cost[1] == pytest.approx(1.05 * (abs(0.5 - drift[0]) * 0.001 + abs(0.5 - drift[1]) * 0.002))
    assert led.net[1] == pytest.approx(0.05 - led.cost[1]) and led.exposure[1] == pytest.approx([0.5, 0.5])
    assert led.net[2] == 0.0 and led.exposure[2] == pytest.approx([0.5, 0.5])
    no_trade = accounting.run(days(3), price, target, [True, False, False])
    assert no_trade.exposure[1] == pytest.approx(drift) and no_trade.turnover[1] == 0


def test_a_cash_instrument_is_financed_for_the_calendar_days_held_and_a_future_is_not():
    d = np.array(["2010-01-07", "2010-01-08", "2010-01-11"], dtype="datetime64[D]")        # Thursday, Friday, Monday
    price = [[100.0, 100.0], [101.0, 101.0], [101.0, 101.0]]
    rate = [[0.0365, 0.0365], [0.0730, 0.0730], [0.0, 0.0]]
    led = accounting.run(d, price, [[1.0, 1.0]] + [[np.nan, np.nan]] * 2, [True, False, False],
                         cash=[True, False], rate=rate)
    assert led.gross[1] == pytest.approx(0.02)
    assert led.financing[1] == pytest.approx(1.0 * 0.0365 * 1 / 365)                       # one day at Thursday's rate
    e = 1.01 / (1.02 - 0.0001)
    assert led.financing[2] == pytest.approx(e * 0.0730 * 3 / 365)                         # the week-end at Friday's rate
    assert led.net == pytest.approx(led.gross - led.financing - led.cost)
    with pytest.raises(ValueError, match="short rate"):
        accounting.run(d, price, [[1.0, 1.0]] * 3, [True, False, False], cash=[True, False],
                       rate=[[np.nan, 0.0]] * 3)


def test_a_missing_price_drops_no_day_the_gap_is_booked_when_the_price_is_back():
    price = [[100.0, 100.0], [np.nan, 105.0], [np.nan, 105.0], [121.0, 105.0]]
    led = accounting.run(days(4), price, [[1.0, 1.0]] + [[np.nan] * 2] * 3, [True, False, False, False])
    assert led.gross == pytest.approx([0.0, 0.05, 0.0, 1.0 / 1.05 * 0.21])                 # A's 21% arrives on day 3
    total = np.prod(1 + led.net) - 1
    assert total == pytest.approx(0.21 + 0.05)                                             # nothing was lost
    # an instrument with no price on a trade day is not traded: its exposure stays where it was
    led = accounting.run(days(4), price, [[1.0, 1.0], [0.0, 0.0], [np.nan] * 2, [np.nan] * 2], [True, True, False, False])
    assert led.skipped == 1 and led.exposure[1, 1] == 0.0 and led.exposure[1, 0] == pytest.approx(1.0 / 1.05)
    assert led.gross[3] == pytest.approx(led.exposure[2, 0] * 0.21)


def test_net_is_gross_less_financing_less_cost_and_a_wiped_out_book_stops():
    rng = np.random.default_rng(1)
    n, m = 300, 4
    price = 100 * np.exp(np.cumsum(0.01 * rng.standard_normal((n, m)), axis=0))
    target = rng.uniform(-1, 1, (n, m))
    trade = rng.random(n) < 0.3
    led = accounting.run(days(n), price, target, trade, cash=[True, True, False, False],
                         rate=np.full((n, m), 0.03), cost=[0.0005, 0.001, 0.0, 0.002])
    assert np.allclose(led.net, led.gross - led.financing - led.cost, rtol=0, atol=1e-15)
    assert led.cost[~trade].sum() == 0 and (led.cost[trade] > 0).all() and led.financing[1:].any()
    with pytest.raises(ValueError, match="exhausted"):
        accounting.run(days(2), [[100.0], [40.0]], [[2.0], [np.nan]], [True, False])       # 2x long, minus 60%
    with pytest.raises(ValueError, match="strictly increasing"):
        accounting.run(days(2)[::-1], [[1.0], [1.0]], [[1.0], [1.0]], [True, False])
    assert accounting.sharpe(np.array([0.01, -0.01, 0.02, 0.0])) == pytest.approx(0.005 / np.std([0.01, -0.01, 0.02, 0.0], ddof=1) * np.sqrt(252))


# ------------------------------------------------------------------ E-04: the daily backtester

PATH = [100.0, 101.0, 103.0, 102.0, 100.0, 99.0, 101.0, 104.0]


def momentum(view: backtest.View) -> dict:
    """Long after an up day, short after a down day, flat with fewer than two prices."""
    _, v = view.get("A", 2)
    return {"A": 0.0 if v.size < 2 else float(np.sign(v[-1] - v[-2]))}


def test_a_constant_signal_is_buy_and_hold():
    w = window(one(PATH))
    hold = np.diff(PATH) / np.array(PATH[:-1])
    r0 = backtest.run(w, Strategy((Instrument("A", "A"),), lambda v: {"A": 1.0}, lag=0))
    assert r0.returns == pytest.approx(hold)
    r1 = backtest.run(w, Strategy((Instrument("A", "A"),), lambda v: {"A": 1.0}))          # lag 1: in from the close of day 1
    assert r1.returns == pytest.approx(np.r_[0.0, hold[1:]])
    assert r1.role == roles.EXPLORATION and r1.instruments == ("A",) and r1.lag == 1


def test_a_momentum_rule_on_a_hand_made_path():
    r = backtest.run(window(one(PATH)), Strategy((Instrument("A", "A", cost=0.001),), momentum))
    # decision at the close of day j: 0, +1, +1, −1, −1, −1, +1 (j = 0..6); executed at the close of day j + 1
    held_over = [0, 0, 1, 1, -1, -1, -1]                                                   # position over day k = 1..7
    step = np.diff(PATH) / np.array(PATH[:-1])
    gross = [h * s for h, s in zip(held_over, step)]
    assert r.gross[1:] == pytest.approx(gross)
    assert [r.decisions[j][0] for j in range(7)] == [0, 1, 1, -1, -1, -1, 1] and 7 not in r.decisions
    # trades at the closes of days 1..7. A long of 1 stays 1 as the price moves; a short of −1 drifts and is
    # traded back: after day 5 (−1%) it is −0.99/1.01, after day 6 (+2/99) it is −(101/99)/(1 − 2/99), and after
    # day 7 (+3/101) it is −(104/101)/(1 − 3/101), from where the trade to +1 is that much more than 2
    assert r.turnover == pytest.approx([0, 0, 1, 0, 2, 1 - 0.99 / 1.01, (101 / 99) / (1 - 2 / 99) - 1,
                                        (104 / 101) / (1 - 3 / 101) + 1])
    growth = 1 + np.array(r.gross) - np.array(r.financing)
    assert r.cost == pytest.approx(growth * r.turnover * 0.001)
    assert r.net == pytest.approx(r.gross - r.cost)
    same = backtest.run(window(one(PATH)), Strategy((Instrument("A", "A", cost=0.001),), momentum))
    assert same.result_hash() == r.result_hash() and len(r.result_hash()) == 64
    other = backtest.run(window(one(PATH[:-1] + [104.5])), Strategy((Instrument("A", "A", cost=0.001),), momentum))
    assert other.result_hash() != r.result_hash()                                          # one mark moved
    s = r.summary()
    assert s["n_obs"] == 7 and s["sharpe"] == pytest.approx(accounting.sharpe(r.returns)) and s["skipped_trades"] == 0


def test_a_value_published_late_is_seen_late():
    seen = {}

    def spy(view):
        seen[view.index] = view.get("A")[1].tolist()
        return {"A": 1.0}

    late = window(one(PATH[:5], lag_days=1))
    r = backtest.run(late, Strategy((Instrument("A", "A"),), spy))
    assert seen == {0: [], 1: [100.0], 2: [100.0, 101.0]}                                  # each close is known a day later
    assert r.dates.size == 4 and late.final("A")[1].tolist() == PATH[:4]                   # the last mark is out after the window ends
    with pytest.raises(ValueError, match="not in the strategy"):
        backtest.run(window(one(PATH)), Strategy((Instrument("A", "A"),), lambda v: {"B": 1.0}))
    with pytest.raises(ValueError, match="finite"):
        backtest.run(window(one(PATH)), Strategy((Instrument("A", "A"),), lambda v: {"A": float("nan")}))


def test_weekly_and_monthly_decisions_are_on_the_last_day_of_the_week_and_the_month():
    cal = days(46)                                                                        # 4 January to 8 March 2010
    weekly = backtest.rebalance_days(cal, "W")
    assert [cal[i].astype(object).weekday() for i in weekly[:-1]] == [4] * (weekly.size - 1)      # Fridays
    monthly = backtest.rebalance_days(cal, "M")
    assert [str(cal[i]) for i in monthly] == ["2010-01-29", "2010-02-26", "2010-03-08"]
    assert backtest.rebalance_days(cal, "D").tolist() == list(range(46))
    s = one(100 + np.arange(46.0))
    r = backtest.run(window(s), Strategy((Instrument("A", "A"),), lambda v: {"A": 1.0}, rebalance="M", lag=0))
    assert sorted(r.decisions) == monthly.tolist()                 # with lag 0 the last day's decision is traded at its close
    assert r.exposure[: monthly[0], 0].tolist() == [0.0] * monthly[0] and r.exposure[monthly[0], 0] == 1.0
    with pytest.raises(ValueError):
        Strategy((Instrument("A", "A"),), momentum, rebalance="Q")
    with pytest.raises(ValueError):
        Strategy((Instrument("A", "A"),), momentum, lag=-1)
    with pytest.raises(ValueError):
        Instrument("A", "A", kind="cash")                                                  # a cash instrument names its rate


def random_walks(n=700, m=3, seed=2, lag_days=0) -> pit.PitStore:
    rng = np.random.default_rng(seed)
    s = pit.PitStore()
    d = days(n)
    for i in range(m):
        s.add(f"P{i}", d, 100 * np.exp(np.cumsum(0.0003 + 0.01 * (1 + i) * rng.standard_normal(n))), lag_days=lag_days)
    s.add("sig", d, rng.standard_normal(n), lag_days=1)
    s.add("rf", d, np.full(n, 0.02), lag_days=1)
    return s


def trend(view: backtest.View) -> dict:
    """A continuous rule: the 20-day return of each instrument over its 20-day volatility, tilted by a signal
    series. Any change in what it sees changes its weights."""
    out = {}
    tilt = view.last("sig", 0.0)
    for name in view.instruments:
        _, v = view.get(name, 21)
        if v.size < 21:
            out[name] = 0.0
            continue
        r = np.diff(np.log(v))
        out[name] = float(r.sum() / (r.std() * np.sqrt(20)) / 3 + 0.05 * tilt)
    return out


def trend_strategy(**kw) -> Strategy:
    ins = (Instrument("P0", "P0", cost=0.0005), Instrument("P1", "P1", cost=0.0005),
           Instrument("P2", "P2", kind="cash", rate="rf", cost=0.001))
    return Strategy(ins, trend, **kw)


def test_volatility_target_uses_the_past_only_and_reaches_its_target():
    w = window(random_walks())
    plain = backtest.run(w, trend_strategy())
    scaled = backtest.run(w, trend_strategy(vol_target=0.10, vol_min_obs=60))
    first = min(j for j, s in scaled.scale.items() if s > 0)
    assert all(scaled.scale[j] == 0.0 for j in scaled.scale if j < first) and first >= 60 + 20     # a burn-in with no position
    assert (scaled.exposure[: first + 1] == 0).all() and set(plain.scale.values()) == {1.0}
    live = scaled.returns[first + 60:]
    assert live.std(ddof=1) * np.sqrt(252) == pytest.approx(0.10, rel=0.25)
    assert plain.returns.std(ddof=1) * np.sqrt(252) > 0.15                                 # unscaled, it was far from it
    j = max(scaled.scale)
    assert np.allclose(scaled.decisions[j], plain.decisions[j] * scaled.scale[j])
    capped = backtest.run(w, trend_strategy(vol_target=5.0, max_scale=3.0))
    assert max(capped.scale.values()) == 3.0


# ------------------------------------------------------------------ E-05: the event backtester

def test_an_event_is_traded_after_it_is_known_held_and_closed_and_other_days_return_exactly_zero():
    d = days(10)
    s = one(100 + np.arange(10.0) ** 2 / 10)                                               # 100, 100.1, 100.4, 100.9, ...
    s.add("ev", [d[2]], [1.0], available=[d[3]])                                           # an event of day 2, known on day 3
    strat = events.strategy((Instrument("A", "A"),), {"A": "ev"}, hold=2)
    r = backtest.run(window(s), strat)
    px = 100 + np.arange(10.0) ** 2 / 10
    # known at the close of day 3, bought at the close of day 4, held over days 5 and 6, sold at the close of day 6
    want = np.zeros(10)
    want[5], want[6] = px[5] / px[4] - 1, px[6] / px[5] - 1
    assert r.net == pytest.approx(want) and (r.net[[0, 1, 2, 3, 4, 7, 8, 9]] == 0.0).all()
    assert r.exposure[:, 0] == pytest.approx([0, 0, 0, 0, 1, px[5] / px[4] / (1 + want[5]), 0, 0, 0, 0])
    same_day = backtest.run(window(s), events.strategy((Instrument("A", "A"),), {"A": "ev"}, hold=2, lag=0))
    assert np.flatnonzero(same_day.net).tolist() == [4, 5]                                 # lag 0: in at the close it was known at
    with pytest.raises(ValueError):
        events.event_signal({"A": "ev"}, hold=0)
    with pytest.raises(ValueError):
        events.strategy((Instrument("A", "A"),), {"B": "ev"}, hold=1)


def test_overlapping_events_add_and_an_event_known_late_is_traded_late_never_early():
    d = days(12)
    s = one(np.full(12, 100.0) * 1.01 ** np.arange(12))                                    # +1% a day
    s.add("ev", [d[1], d[2], d[3]], [1.0, 0.5, -2.0], available=[d[1], d[2], d[8]])        # the third is known on day 8
    r = backtest.run(window(s), events.strategy((Instrument("A", "A"),), {"A": "ev"}, hold=3))
    # decisions: day 1: 1.0; day 2: 1.5; day 3: 1.5; day 4: 0.5; day 5 to 7: 0; day 8 to 10: −2
    assert [round(float(r.decisions[j][0]), 12) for j in range(11)] == [0, 1, 1.5, 1.5, 0.5, 0, 0, 0, -2, -2, -2]
    assert (r.exposure[:8, 0] >= 0).all() and r.exposure[8, 0] == 0.0                      # nothing short before day 9
    assert r.exposure[9, 0] == pytest.approx(-2.0) and r.net[9] == 0.0 and r.net[10] == pytest.approx(-0.02)
    # an event dated day 3 is not in the position of days 4 to 8 although its date has passed
    assert r.exposure[5, 0] == pytest.approx(0.5) and r.net[6] == pytest.approx(0.5 * 0.01)


# ------------------------------------------------------------------ E-06: the look-ahead test

CUTOFFS = [days(700)[k] for k in (150, 301, 452, 640)]


@pytest.mark.parametrize("kw", [dict(), dict(vol_target=0.10), dict(rebalance="W", lag=0), dict(lag=3)])
def test_a_clean_strategy_passes_the_look_ahead_test(kw):
    store = random_walks(lag_days=1 if kw.get("lag") == 3 else 0)
    run = lambda s: backtest.run(window(s), trend_strategy(**kw))
    cut = [c for c in CUTOFFS] if kw.get("rebalance") != "W" else [days(700)[k] for k in (154, 304, 454, 639)]   # Fridays
    assert lookahead.violations(run, store, cut) == []


def test_a_clean_event_strategy_passes_and_changing_the_future_really_changes_the_future():
    store = random_walks()
    d = days(700)
    rng = np.random.default_rng(5)
    when = np.sort(rng.choice(690, 40, replace=False))
    store.add("ev", d[when], rng.choice([-1.0, 1.0], 40), available=d[when] + np.timedelta64(2, "D"))
    strat = events.strategy((Instrument("P0", "P0"),), {"P0": "ev"}, hold=5)
    run = lambda s: backtest.run(window(s), strat)
    assert lookahead.violations(run, store, CUTOFFS) == []
    a, b = run(store), run(lookahead.tampered_after(store, CUTOFFS[1]))
    assert not np.array_equal(a.net, b.net) and np.array_equal(a.net[:300], b.net[:300])


@pytest.mark.parametrize("series", ["P0", "P1", "P2", "sig", "rf"])
def test_the_look_ahead_test_fails_when_any_one_input_is_shifted_forward(series):
    """Each input in turn is seen one observation early: prices (which the signal and the accounting read), the
    signal series, and the short rate (which the accounting reads)."""
    store = random_walks()
    run = lambda s: backtest.run(window(s), trend_strategy())
    assert lookahead.violations(run, store, CUTOFFS) == []
    found = lookahead.violations(run, store, CUTOFFS, prepare=lambda s: lookahead.shifted(s, series))
    assert found, series
    assert all(("depends on data that became available after" in f) or ("marks were all known" in f) for f in found)


def test_a_signal_that_peeks_through_the_window_cannot_exist():
    """The view is the only thing a signal is handed, and asking it for a later day gives nothing more."""
    store = random_walks(n=60)
    w = window(store)
    v = backtest.View(w, days(60), 10, ("P0",))
    assert v.get("P0")[0][-1] == days(60)[10] and v.last("sig") == w.as_of("sig", days(60)[10])[1][-1]
    assert w.as_of("sig", days(60)[10])[0][-1] == days(60)[9]                              # the signal series is a day late
    assert not hasattr(v, "store") and not [n for n in vars(v) if "store" in n]


# ------------------------------------------------------------------ E-07: records

def specs():
    fam = spec.family(mechanism="trend persists", mechanism_class="behavioural", sign="+", counterparty="hedgers",
                      kill_condition="none", tail_exposure="reversals")
    hyp = spec.hypothesis(fam, domain="test_daily", signal="20-day return over volatility", grid={"k": [20]},
                          data_sources=[{"name": "P", "publication_lag_days": 0}],
                          primary_binding={"universe_id": "three_walks", "cost_model_id": "bp5", "sizing_id": "raw"})
    var = spec.variants(hyp)[0]
    return fam, hyp, var, spec.primary_executable(hyp, var, code_version="test")


@pytest.fixture
def cutoff(monkeypatch):
    from nightshift import logs
    monkeypatch.setattr(logs, "main_cutoff", lambda: date(2019, 12, 31))


def test_an_evaluation_is_a_ledger_record_and_an_exploration_variant_row(tmp_path, cutoff):
    import csv
    fam, hyp, var, exe = specs()
    led = L.Ledger(tmp_path / "ledger.jsonl", writer="session", protocol="0" * 64)
    log = tmp_path / "log.csv"
    store = random_walks(n=300)
    kw = dict(ledger=led, executable=exe, variant=var, hypothesis=hyp, family=fam, log_path=log,
              version={"commit": "test", "engine_sha256": "0" * 64})
    result, rec = evaluate.evaluate(window(store), trend_strategy(), **kw)
    p = rec["payload"]
    assert rec["type"] == "evaluation" and p["role"] == "exploration" and p["evidential_weight"] == 0
    assert p["data_hash"] == store.data_hash() and p["result_hash"] == result.result_hash()
    assert p["spec_hash"] == spec.spec_hash(exe) and p["executable"] == spec.spec_id(exe) and p["n_obs"] == 299
    assert p["window"] == {"id": "test_daily:2010-01-04:2011-02-25", "start": "2010-01-04", "end": "2011-02-25", "frequency": "daily"}
    # the ledger stores numbers in the spec's canonical form: decimals as strings
    assert float(p["summary"]["sharpe"]) == pytest.approx(result.summary()["sharpe"]) and p["code_version"]["commit"] == "test"
    rows = list(csv.DictReader(log.open()))
    assert len(rows) == 1 and rows[0]["code_ref"] == rec["hash"] and rows[0]["variant_id"] == spec.spec_id(exe)
    assert rows[0]["data_end"] == "2011-02-25" and float(rows[0]["value"]) == pytest.approx(result.summary()["sharpe"], abs=1e-6)
    # the same evaluation again is the same look; a different result on the same key is a nondeterminism
    _, again = evaluate.evaluate(window(store), trend_strategy(), **kw)
    assert again["type"] == "rerun" and again["payload"]["first_seq"] == rec["seq"] and led.looks() == 1
    assert len(list(csv.DictReader(log.open()))) == 1                                      # a rerun is not a new variant
    _, odd = evaluate.evaluate(window(store), trend_strategy(lag=2), **kw)
    assert odd["type"] == "nondeterminism" and led.suspended_families() == {spec.spec_id(fam)}
    assert L.verify(led.path) == []
    with pytest.raises(ValueError, match="log_path"):
        evaluate.evaluate(window(store), trend_strategy(), **{**kw, "log_path": None})
    v = evaluate.code_version()
    assert set(v) == {"commit", "engine_sha256"} and len(v["engine_sha256"]) == 64


def test_no_evaluation_and_no_variant_row_can_be_dated_after_the_exploration_cut_off(tmp_path, cutoff):
    from nightshift import logs
    fam, hyp, var, exe = specs()
    store = one(np.linspace(100, 110, 30), name="P0", start=date(2019, 12, 2))            # into January 2020
    with pytest.raises(roles.RoleError):
        window(store)                                                                     # refused before anything runs
    row = {"hypothesis_id": "h", "variant_id": "v", "description": "d", "data_start": "2019-12-02", "data_end": "2020-01-10",
           "n_obs": "30", "metric": "m", "value": "0", "params": "", "code_ref": "", "nominated": "", "notes": ""}
    with pytest.raises(ValueError, match="exploration never uses 2020"):
        logs.log_variant(row, path=tmp_path / "log.csv")
    assert not (tmp_path / "log.csv").exists()
