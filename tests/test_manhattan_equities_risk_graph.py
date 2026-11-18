"""Technology equities: relationship graph, costs and borrow, exposure reports and macro diagnostics. Synthetic only."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from manhattan.engine.pit import PitStore, Window
from manhattan.equities import macro, risk
from manhattan.equities import synthetic as syn
from manhattan.equities.costs import BorrowBook, BorrowRecord, EquityCostModel
from manhattan.equities.errors import BorrowError, EquityDataError, TemporalError
from manhattan.equities.graph import Relationship, RelationshipGraph
from manhattan.equities.integration import conforms

CAL = syn.calendar()


def rel(s, d, t="supplier_of", vf=date(2005, 1, 3), pf=date(2005, 1, 3), rf=date(2005, 1, 3), conf=0.8, vt=None):
    return Relationship(s, d, t, vf, pf, rf, "synthetic filing note", conf, vt)


# ----------------------------------------------------------------------------- graph
def test_backdated_relationships_are_not_usable_before_they_were_recorded():
    g = RelationshipGraph([rel("EQUIP", "FAB", vf=date(2004, 1, 2), pf=date(2004, 1, 2), rf=date(2007, 5, 1))])
    e = g._edges[0]
    assert e.backdated
    assert g.edges(date(2005, 6, 1)).edges == ()
    retro = g.edges(date(2005, 6, 1), retrospective=True)
    assert len(retro.edges) == 1 and retro.retrospective
    assert len(g.edges(date(2007, 5, 1)).edges) == 1


def test_undisclosed_and_expired_relationships_are_not_usable():
    g = RelationshipGraph([rel("A", "B", vf=date(2005, 1, 3), pf=date(2005, 6, 1), rf=date(2005, 6, 1)),
                           rel("C", "B", vt=date(2005, 12, 30))])
    assert [x.source for x in g.edges(date(2005, 3, 1)).edges] == ["C"]
    assert [x.source for x in g.edges(date(2006, 3, 1)).edges] == ["A"]


def test_relationship_validation():
    with pytest.raises(TemporalError):
        rel("A", "B", pf=date(2005, 6, 1), rf=date(2005, 1, 3))
    with pytest.raises(EquityDataError):
        rel("A", "A")
    with pytest.raises(EquityDataError):
        rel("A", "B", conf=1.5)
    with pytest.raises(EquityDataError):
        Relationship("A", "B", "supplier_of", date(2005, 1, 3), date(2005, 1, 3), date(2005, 1, 3), "", 0.5)


def test_propagation_is_lagged_and_point_in_time():
    g = RelationshipGraph([rel("S1", "D", conf=1.0), rel("S2", "D", conf=0.5),
                           rel("S3", "D", rf=date(2006, 6, 1))])         # S3 known only later
    seen = []

    def feature_at(node, d):
        seen.append(d)
        return {"S1": 1.0, "S2": 4.0, "S3": 100.0}[node]

    t = date(2006, 3, 1)
    out = g.propagate(feature_at, ["D", "S1"], t, lag_sessions=5, calendar=CAL)
    assert out["D"] == pytest.approx((1.0 * 1 + 0.5 * 4) / 1.5)
    assert out["S1"] is None
    assert set(seen) == {CAL.offset(t, -5)}
    with pytest.raises(TemporalError):
        g.propagate(feature_at, ["D"], t, lag_sessions=-1, calendar=CAL)


def test_symmetric_relationships():
    g = RelationshipGraph([rel("A", "B", t="competitor_of")])
    assert g.neighbours("A", date(2006, 1, 3)) == [("B", 0.8)]
    assert g.neighbours("B", date(2006, 1, 3)) == [("A", 0.8)]


# ----------------------------------------------------------------------------- costs and borrow
def test_borrow_is_point_in_time_and_stale_records_expire():
    b = BorrowBook([BorrowRecord("S1", date(2006, 3, 1), date(2006, 3, 2), True, 0.004)], max_staleness_days=5)
    with pytest.raises(BorrowError):
        b.status("S1", date(2006, 3, 1))                  # published the next morning
    assert b.status("S1", date(2006, 3, 2)).fee_annual == 0.004
    with pytest.raises(BorrowError, match="old"):
        b.status("S1", date(2006, 3, 20))
    with pytest.raises(EquityDataError):
        BorrowRecord("S1", date(2006, 3, 2), date(2006, 3, 1), True, 0.0)


def test_cost_model_prices_trades_and_holding():
    m = EquityCostModel(half_spread=0.0005, commission=0.0001, impact=0.1,
                        borrow=BorrowBook([BorrowRecord("S2", date(2006, 3, 1), date(2006, 3, 1), True, 0.0365)]))
    assert m.trade_cost(1e6, 1e8, 0.02) == pytest.approx(0.0006 + 0.1 * 0.02 * 0.1)
    w = {"S1": 0.5, "S2": -0.5}
    assert m.holding_cost_daily(w, date(2006, 3, 1)) == pytest.approx(0.5 * 0.0365 / 365)
    with pytest.raises(BorrowError, match="omission"):
        EquityCostModel().holding_cost_daily(w, date(2006, 3, 1))
    with pytest.raises(EquityDataError):
        m.turnover_cost({}, {"S1": 0.1}, 1e6, {}, {})
    assert conforms(m, "execution_costs")


# ----------------------------------------------------------------------------- exposure reports
def _ls():
    w = {"A": 0.3, "B": 0.2, "C": -0.25, "D": -0.25}
    common = dict(betas={"A": 1.2, "B": 1.0, "C": 0.9, "D": 1.1}, industries={"A": "semiconductors",
                  "B": "enterprise_software", "C": "semiconductors", "D": "enterprise_software"},
                  factors={"growth": {"A": 1.0, "B": 0.5, "C": -0.2, "D": 0.1}},
                  adv={"A": 1e7, "B": 1e7, "C": 1e6, "D": 2e7}, capital=1e7)
    return w, common


def test_long_short_report():
    w, common = _ls()
    rep = risk.long_short_report(w, borrow_fees={"C": 0.05, "D": 0.003}, days_to_cover={"C": 12.0},
                                 earnings_soon={"A": True}, **common)
    assert rep.gross == pytest.approx(1.0) and rep.net == pytest.approx(0.0)
    assert rep.beta == pytest.approx(0.36 + 0.2 - 0.225 - 0.275)
    assert rep.industry["semiconductors"] == pytest.approx(0.05)
    assert rep.factors["growth"] == pytest.approx(0.3 + 0.1 + 0.05 - 0.025)
    assert rep.extra["borrow_cost_annual"] == pytest.approx(0.25 * 0.05 + 0.25 * 0.003)
    assert rep.extra["squeeze_risk_names"] == ("C",) and rep.extra["earnings_event_gross"] == pytest.approx(0.3)
    assert rep.liquidity_days_max == pytest.approx(0.25 * 1e7 / (0.1 * 1e6))


def test_missing_exposures_are_not_zero():
    w, common = _ls()
    with pytest.raises(EquityDataError, match="borrow fee"):
        risk.long_short_report(w, borrow_fees={"C": 0.05}, **common)
    common["betas"].pop("D")
    with pytest.raises(EquityDataError, match="beta"):
        risk.long_short_report(w, borrow_fees={"C": 0.05, "D": 0.01}, **common)


def test_directional_report_and_turnover():
    w = {"A": 0.6, "B": 0.4}
    rep = risk.directional_report(w, betas={"A": 1.3, "B": 1.1}, industries={"A": "semiconductors", "B": "ecommerce"},
                                  factors=None, adv={"A": 1e7, "B": 1e7}, capital=1e6, previous={"A": 0.5, "C": 0.5},
                                  rate_sensitivity={"A": -2.0, "B": -1.0})
    assert rep.extra["turnover_one_way"] == pytest.approx(0.5)
    assert rep.extra["rate_sensitivity"] == pytest.approx(-1.6)
    with pytest.raises(EquityDataError):
        risk.directional_report({"A": -0.1}, betas={"A": 1}, industries={"A": "x"}, factors=None, adv={"A": 1},
                                capital=1)


def test_different_tickers_are_not_diversification():
    rng = np.random.default_rng(0)
    f = rng.normal(0, 0.02, 2000)
    one_factor = np.column_stack([f + rng.normal(0, 0.002, 2000) for _ in range(10)])
    indep = rng.normal(0, 0.02, (2000, 10))
    ids = tuple(f"S{i}" for i in range(10))
    w = {s: 0.1 for s in ids}
    assert risk.effective_bets(w, np.cov(one_factor, rowvar=False), ids) < 1.5
    assert risk.effective_bets(w, np.cov(indep, rowvar=False), ids) > 8


def test_shared_factor_across_books_is_counted_once():
    w, common = _ls()
    ls = risk.long_short_report(w, borrow_fees={"C": 0.05, "D": 0.003}, **common)
    d = risk.directional_report({"A": 1.0}, betas={"A": 1.2}, industries={"A": "semiconductors"},
                                factors={"growth": {"A": 1.0}}, adv={"A": 1e7}, capital=1e6)
    agg = risk.aggregate_factor_exposure({"long_short": ls, "directional": d})
    assert agg["shared"] == {"growth": ("directional", "long_short")}
    assert agg["total"]["growth"] == pytest.approx(ls.factors["growth"] + 1.0)


def test_drawdown():
    dd = risk.drawdown(np.array([0.1, -0.5, 0.1, 0.1, 1.0]))
    assert dd["max_drawdown"] == pytest.approx(-0.5) and dd["longest_underwater"] == 3


# ----------------------------------------------------------------------------- macro
def test_macro_sensitivity_uses_the_past_only():
    rng = np.random.default_rng(1)
    days = np.array(CAL.sessions_between(date(2005, 1, 3), date(2006, 12, 29)), dtype=object)
    n = len(days)
    mkt, dy = rng.normal(0, 0.01, n), rng.normal(0, 0.0005, n)
    stock = 1.1 * mkt - 8.0 * dy + rng.normal(0, 0.005, n)
    t = date(2006, 6, 30)
    a = macro.sensitivity(days, stock, dy, mkt, t)
    stock2 = stock.copy()
    stock2[np.array([d > t for d in days])] = 9.0
    assert macro.sensitivity(days, stock2, dy, mkt, t) == a
    assert a["macro"] == pytest.approx(-8.0, abs=1.5)


def test_incremental_information_sees_through_a_relabelled_market_factor():
    rng = np.random.default_rng(2)
    n = 3000
    mkt, sector, novel = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
    y = 0.5 * mkt + 0.3 * sector + 0.2 * novel + rng.normal(size=n)
    controls = np.column_stack([mkt, sector])
    relabelled = 2 * mkt - sector + rng.normal(0, 1e-3, n)       # a "macro feature" that is just common factors
    r1 = macro.incremental_information(relabelled, y, controls)
    r2 = macro.incremental_information(novel, y, controls)
    assert abs(r1["partial_corr"]) < 0.05 and r2["partial_corr"] > 0.1
    assert r1["evidential_weight"] == 0


def test_macro_reads_go_through_the_existing_window():
    store = PitStore()
    store.add("real_yield_10y", np.array(["2006-03-01", "2006-03-01"], dtype="datetime64[D]"), [1.0, 1.2],
              available=np.array(["2006-03-02", "2006-04-10"], dtype="datetime64[D]"))   # a revision
    w = Window(store, date(2006, 1, 2), date(2006, 12, 29), "exploration", "macro_test", "session")
    assert list(macro.macro_as_of(w, "real_yield_10y", date(2006, 3, 15))[1]) == [1.0]
    assert list(macro.macro_as_of(w, "real_yield_10y", date(2006, 4, 10))[1]) == [1.2]
