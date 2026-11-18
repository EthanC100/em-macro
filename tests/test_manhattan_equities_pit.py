"""Technology equities: point-in-time data contracts (docs/manhattan/equities/DESIGN.md sections 4 and 5).

Synthetic data only. Each test names the hazard it guards against; a failure means information from the future,
a wrong identity or an unpriced outcome could reach a historical model.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pytest

from manhattan.engine.pit import PitStore, Window
from manhattan.equities import pit_bridge, sources
from manhattan.equities import synthetic as syn
from manhattan.equities.errors import (ContractError, CorporateActionError, CurrencyError, EquityDataError,
                                       IdentityError, TemporalError)
from manhattan.equities.estimates import Estimate, EstimateBook
from manhattan.equities.events import EarningsEvent, check_label, scheduled_known, surprise, usable_close
from manhattan.equities.fundamentals import Fact, FundamentalStore
from manhattan.equities.identity import Company, LifecycleEvent, Security, SecurityMaster, TickerInterval
from manhattan.equities.prices import Bar, CorporateAction, DelistingPolicy, DelistingReturn, PriceBook
from manhattan.equities.sessions import MarketCalendar

CAL = syn.calendar()
NY = CAL.tz


def ny(d: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), NY)


# ----------------------------------------------------------------------------- sessions and timestamps
def test_naive_timestamps_are_refused():
    with pytest.raises(TemporalError, match="naive"):
        CAL.usable_close(datetime(2006, 3, 1, 8, 0))


def test_conservative_usability_before_during_after_and_on_closures():
    d = date(2006, 3, 1)                                      # a Wednesday
    assert CAL.usable_close(ny(d, 8)) == d                    # before the open: that day's close
    assert CAL.usable_close(ny(d, 11)) == date(2006, 3, 2)    # during: the next close (conservative)
    assert CAL.usable_close(ny(d, 16, 5)) == date(2006, 3, 2)  # after the close
    assert CAL.usable_close(ny(date(2006, 3, 4), 12)) == date(2006, 3, 6)   # Saturday: Monday
    # market closure: 4 July 2006 is not a session; news that day is first usable on the 5th
    assert not CAL.is_session(date(2006, 7, 4))
    assert CAL.usable_close(ny(date(2006, 7, 4), 7)) == date(2006, 7, 5)
    # the less conservative policy still needs the buffer before the close
    assert CAL.usable_close(ny(d, 11), policy="same_close") == d
    assert CAL.usable_close(ny(d, 15, 50), policy="same_close") == date(2006, 3, 2)


def test_timezones_are_respected():
    d = date(2006, 3, 1)
    utc_1330 = datetime(2006, 3, 1, 13, 30, tzinfo=timezone.utc)   # 08:30 New York (EST): before the open
    assert CAL.usable_close(utc_1330) == d
    utc_1500 = datetime(2006, 3, 1, 15, 0, tzinfo=timezone.utc)    # 10:00 New York: during the session
    assert CAL.usable_close(utc_1500) == date(2006, 3, 2)


def test_half_day_close():
    s = CAL.session(date(2006, 11, 24))
    assert s.close.time() == time(13, 0)
    assert CAL.usable_close(ny(date(2006, 11, 24), 14), policy="same_close") == date(2006, 11, 27)


def test_calendar_refuses_duplicate_days():
    s = CAL.session(date(2006, 3, 1))
    with pytest.raises(TemporalError):
        MarketCalendar("bad", [s, s])


# ----------------------------------------------------------------------------- source contracts
def test_unknown_timing_or_overwritten_history_cannot_be_a_signal():
    with pytest.raises(ContractError, match="timing"):
        sources.DataContract("v", "fundamentals_pit", "vendorX", "licensed", "doc", "unknown", "vintaged", True,
                             ("signal",))
    with pytest.raises(ContractError, match="overwritten"):
        sources.DataContract("v", "fundamentals_pit", "vendorX", "licensed", "doc", "filing_acceptance_time",
                             "overwritten", True, ("signal",))
    c = sources.DataContract("v", "fundamentals_pit", "vendorX", "licensed", "doc", "filing_acceptance_time",
                             "overwritten", True, ("descriptive",))
    assert c.permits("descriptive") and not c.permits("signal")
    with pytest.raises(ContractError):
        c.require("signal")


def test_outcome_prices_must_include_delistings():
    with pytest.raises(ContractError, match="delisted"):
        sources.DataContract("p", "prices_daily", "v", "public", "doc", "date_only", "immutable", True,
                             ("evaluation_outcome",), includes_delisted=False)


def test_alternative_data_is_descriptive_only_until_verified():
    c = sources.alternative_contract("patents_x", "patents", "some office", "reference")
    assert c.permits("descriptive")
    assert not c.permits("signal")
    with pytest.raises(ContractError):
        sources.alternative_contract("x", "prices_daily", "v", "r")


def test_licensed_data_never_publishable_and_registry_requires_declarations():
    lic = sources.DataContract("n", "prices_daily", "vendor", "licensed", "doc", "date_only", "immutable", True,
                               ("signal",), includes_delisted=True)
    with pytest.raises(ContractError, match="public repository"):
        lic.assert_publishable()
    reg = sources.ContractRegistry([sources.synthetic_contract("prices_daily")])
    reg.require("prices_daily", "signal")
    with pytest.raises(ContractError, match="no contract"):
        reg.require("analyst_estimates_pit", "signal")
    with pytest.raises(ContractError, match="two different"):
        reg.add(lic)


def test_daily_contract_speaks_the_existing_availability_contract():
    src = sources.synthetic_contract("prices_daily").as_availability_source()
    from manhattan.availability import validate_source
    validate_source(src)                                       # the existing Manhattan validator accepts it
    unk = sources.DataContract("u", "prices_daily", "v", "public", "doc", "unknown", "unknown", False,
                               ("descriptive",))
    with pytest.raises(ContractError):
        unk.as_availability_source()


# ----------------------------------------------------------------------------- identity
def _master():
    m = SecurityMaster()
    m.add_company(Company("C1", "one"))
    m.add_company(Company("C2", "two"))
    m.add_security(Security("S1", "C1", "A", "common", "USD", date(2001, 1, 2), date(2005, 6, 30)))
    m.add_security(Security("S2", "C2", "A", "common", "USD", date(2006, 1, 3)))
    m.add_ticker(TickerInterval("S1", "ABC", "XNAS", date(2001, 1, 2), date(2003, 3, 31)))
    m.add_ticker(TickerInterval("S1", "ABCD", "XNAS", date(2003, 4, 1), date(2005, 6, 30), known_from=date(2003, 3, 20)))
    m.add_ticker(TickerInterval("S2", "ABC", "XNAS", date(2006, 1, 3)))      # the old ticker, reused
    return m


def test_ticker_change_and_reuse_resolve_by_date():
    m = _master()
    assert m.resolve("ABC", date(2002, 5, 1)) == "S1"
    assert m.resolve("ABCD", date(2004, 5, 3)) == "S1"
    assert m.resolve("ABC", date(2007, 5, 1)) == "S2"           # same ticker, different issuer
    assert m.company_of(m.resolve("ABC", date(2002, 5, 1))) != m.company_of(m.resolve("ABC", date(2007, 5, 1)))
    with pytest.raises(IdentityError):
        m.resolve("ABC", date(2005, 9, 1))                        # nobody held it then
    # a ticker change announced on 2003-03-20 is unknown on 2003-03-10
    with pytest.raises(IdentityError):
        m.resolve("ABCD", date(2003, 4, 1), as_known_at=date(2003, 3, 10))


def test_duplicate_securities_and_overlapping_tickers_are_refused():
    m = _master()
    with pytest.raises(IdentityError, match="duplicate"):
        m.add_security(Security("S1bis", "C1", "A", "common", "USD", date(2002, 1, 2)))
    m.add_security(Security("S4", "C1", "B", "common", "USD", date(2002, 1, 2)))
    with pytest.raises(IdentityError, match="same time"):
        m.add_ticker(TickerInterval("S4", "ABC", "XNAS", date(2002, 1, 2), date(2002, 12, 31)))
    with pytest.raises(IdentityError, match="outside the listing"):
        m.add_ticker(TickerInterval("S2", "XYZ", "XNAS", date(2004, 1, 2)))
    with pytest.raises(IdentityError, match="redefined"):
        m.add_security(Security("S2", "C1", "A", "common", "USD", date(2006, 1, 3)))
    # two share classes of one company are distinct securities, not duplicates
    m.add_security(Security("S3", "C2", "B", "common", "USD", date(2006, 1, 3)))
    assert m.securities_of("C2", date(2007, 1, 2)) == ("S2", "S3")


def test_lifecycle_events_must_agree_with_listing():
    m = _master()
    with pytest.raises(IdentityError, match="reason"):
        LifecycleEvent("S1", "delisting", date(2005, 6, 30), date(2005, 6, 30))
    with pytest.raises(IdentityError, match="last trading day"):
        m.add_event(LifecycleEvent("S1", "delisting", date(2005, 7, 29), date(2005, 6, 30), reason="merger"))
    with pytest.raises(IdentityError, match="counterparty"):
        LifecycleEvent("S1", "acquisition", date(2005, 6, 30), date(2005, 1, 3))
    assert m.validate() == ["S1: has a last trading day but no delisting event (reason unknown)"]


def test_listed_on_a_date_includes_later_delisted_and_excludes_later_ipos():
    m = _master()
    assert m.listed(date(2004, 1, 5)) == ("S1",)
    assert m.listed(date(2007, 1, 5)) == ("S2",)


# ----------------------------------------------------------------------------- prices and corporate actions
def _book(**kw):
    b = PriceBook(CAL, **kw)
    days = CAL.sessions_between(date(2006, 2, 1), date(2006, 3, 31))
    closes = np.linspace(40, 44, len(days))
    split = date(2006, 3, 1)
    closes = np.where(np.array(days) >= split, closes / 2, closes)
    b.add_bars("S1", days, closes, currency="USD", volumes=np.full(len(days), 1e6))
    return b, days


def test_missing_split_is_detected_and_a_known_split_is_applied():
    b, days = _book()
    with pytest.raises(CorporateActionError, match="split"):
        b.total_returns("S1", date(2006, 2, 1), date(2006, 3, 31), as_of=date(2006, 3, 31))
    b.add_action(CorporateAction("S1", "split", date(2006, 3, 1), date(2006, 1, 20), ratio=2.0))
    r = b.total_returns("S1", date(2006, 2, 1), date(2006, 3, 31), as_of=date(2006, 3, 31))
    assert np.abs(r.returns).max() < 0.01
    assert b.corporate_action_complete("S1", date(2006, 2, 1), date(2006, 3, 31), as_of=date(2006, 3, 31))


def test_split_adjustment_is_point_in_time():
    b, days = _book()
    b.add_action(CorporateAction("S1", "split", date(2006, 3, 1), date(2006, 1, 20), ratio=2.0))
    d0, c0 = b.split_adjusted_closes("S1", date(2006, 2, 1), date(2006, 2, 28), as_of=date(2006, 2, 28))
    d1, c1 = b.split_adjusted_closes("S1", date(2006, 2, 1), date(2006, 2, 28), as_of=date(2006, 3, 31))
    assert np.allclose(c0, 2 * c1)              # before the ex-date the history is not yet adjusted
    with pytest.raises(TemporalError):
        b.split_adjusted_closes("S1", date(2006, 2, 1), date(2006, 3, 31), as_of=date(2006, 3, 1))


def test_dividends_enter_total_return_and_currency_must_match():
    b = PriceBook(CAL)
    days = CAL.sessions_between(date(2006, 2, 1), date(2006, 2, 28))
    b.add_bars("S1", days, np.full(len(days), 50.0), currency="USD")
    b.add_action(CorporateAction("S1", "special_dividend", date(2006, 2, 15), date(2006, 2, 1), amount=1.0,
                                 currency="USD"))
    r = b.total_returns("S1", days[0], days[-1], as_of=days[-1])
    assert r.returns[list(r.days).index(date(2006, 2, 15))] == pytest.approx(0.02)
    with pytest.raises(CurrencyError):
        b.add_action(CorporateAction("S1", "cash_dividend", date(2006, 2, 16), date(2006, 2, 1), amount=1.0,
                                     currency="EUR"))
    with pytest.raises(CurrencyError):
        b.add_bar(Bar("S1", date(2006, 3, 1), 50.0, "EUR"))


def test_bars_on_market_closures_are_refused():
    b = PriceBook(CAL)
    with pytest.raises(TemporalError, match="closed"):
        b.add_bar(Bar("S1", date(2006, 7, 4), 10.0, "USD"))


def test_suspensions_and_missing_sessions_span_returns():
    b = PriceBook(CAL)
    days = CAL.sessions_between(date(2006, 2, 1), date(2006, 2, 10))
    for i, d in enumerate(days):
        if d == date(2006, 2, 6):
            b.add_bar(Bar("S1", d, 1.0, "USD", status="suspended"))
        elif d != date(2006, 2, 7):
            b.add_bar(Bar("S1", d, 10.0 + i, "USD"))
    r = b.total_returns("S1", days[0], days[-1], as_of=days[-1])
    assert date(2006, 2, 6) not in r.days and date(2006, 2, 7) not in r.days
    i = list(r.days).index(date(2006, 2, 8))
    assert r.multi_session[i] and r.returns[i] == pytest.approx((10 + 5) / (10 + 2) - 1)


def test_missing_delisting_return_fails_closed_and_assumptions_are_flagged():
    w = syn.world()
    r = w.prices.total_returns("S04", date(2006, 1, 3), date(2006, 12, 29), as_of=date(2006, 12, 29))
    assert r.delisting_day == date(2006, 7, 3) and r.returns[-1] == pytest.approx(-0.35) and not r.delisting_assumed
    # the delisting proceeds were known only on 2006-07-20: on 2006-07-10 there is no delisting return yet
    with pytest.raises(CorporateActionError, match="survivorship"):
        w.prices.total_returns("S04", date(2006, 1, 3), date(2006, 7, 10), as_of=date(2006, 7, 10))
    pol = DelistingPolicy.assume({"performance": -0.3}, "declared assumption for the test")
    r2 = w.prices.total_returns("S04", date(2006, 1, 3), date(2006, 7, 10), as_of=date(2006, 7, 10), delisting=pol)
    assert r2.delisting_assumed and r2.returns[-1] == -0.3
    with pytest.raises(CorporateActionError):
        DelistingPolicy.assume({}, "")


def test_actions_cannot_be_published_after_their_ex_date():
    with pytest.raises(TemporalError):
        CorporateAction("S1", "split", date(2006, 3, 1), date(2006, 3, 5), ratio=2.0)


# ----------------------------------------------------------------------------- fundamentals
def _fs(**kw):
    fs = FundamentalStore(CAL, **kw)
    q = date(2006, 3, 31)
    fs.add(Fact("C1", "revenue", q, "quarter", 100.0, "USD", ny(date(2006, 5, 2), 16, 30)))       # after the close
    fs.add(Fact("C1", "revenue", q, "quarter", 90.0, "USD", ny(date(2007, 2, 14), 17), vintage="restated"))
    return fs, q


def test_a_quarter_is_not_known_because_it_ended():
    fs, q = _fs()
    assert fs.value("C1", "revenue", date(2006, 4, 3)) is None
    assert fs.value("C1", "revenue", date(2006, 5, 2)) is None            # filed after that close
    assert fs.value("C1", "revenue", date(2006, 5, 3)).value == 100.0


def test_restatements_are_invisible_before_publication():
    fs, q = _fs()
    assert fs.value("C1", "revenue", date(2006, 12, 29)).value == 100.0
    assert fs.value("C1", "revenue", date(2007, 2, 15)).value == 90.0
    assert fs.value("C1", "revenue", date(2007, 2, 15), vintage="original").value == 100.0


def test_late_vendor_capture_delays_availability():
    fs = FundamentalStore(CAL)
    fs.add(Fact("C1", "revenue", date(2006, 3, 31), "quarter", 100.0, "USD", ny(date(2006, 5, 2), 8),
                capture_time=ny(date(2006, 8, 1), 9)))
    assert fs.value("C1", "revenue", date(2006, 7, 31)) is None
    assert fs.value("C1", "revenue", date(2006, 8, 2)).value == 100.0
    strict = FundamentalStore(CAL, require_capture=True)
    with pytest.raises(TemporalError, match="capture"):
        strict.add(Fact("C1", "revenue", date(2006, 3, 31), "quarter", 1.0, "USD", ny(date(2006, 5, 2), 8)))


def test_invalid_fundamental_timestamps():
    with pytest.raises(TemporalError, match="naive"):
        Fact("C1", "revenue", date(2006, 3, 31), "quarter", 1.0, "USD", datetime(2006, 5, 2, 8))
    with pytest.raises(TemporalError, match="before the period ended"):
        Fact("C1", "revenue", date(2006, 3, 31), "quarter", 1.0, "USD", ny(date(2006, 3, 30), 8))
    with pytest.raises(TemporalError, match="captured before"):
        Fact("C1", "revenue", date(2006, 3, 31), "quarter", 1.0, "USD", ny(date(2006, 5, 2), 8),
             capture_time=ny(date(2006, 5, 1), 8))


def test_ttm_growth_and_currency_consistency():
    fs = FundamentalStore(CAL)
    qs = [date(2005, 3, 31), date(2005, 6, 30), date(2005, 9, 30), date(2005, 12, 31), date(2006, 3, 31)]
    for i, q in enumerate(qs):
        fs.add(Fact("C1", "revenue", q, "quarter", 100.0 + 10 * i, "USD", ny(q + timedelta(days=40), 7)))
    t = date(2006, 6, 1)
    assert fs.ttm("C1", "revenue", t) == pytest.approx(110 + 120 + 130 + 140)
    assert fs.growth("C1", "revenue", t) == pytest.approx(140 / 100 - 1)
    fs.add(Fact("C1", "total_assets", date(2006, 3, 31), "quarter", 500.0, "EUR", ny(date(2006, 5, 10), 7)))
    with pytest.raises(CurrencyError):
        fs.ratio("C1", "revenue", "total_assets", t)
    with pytest.raises(CurrencyError):
        fs.add(Fact("C1", "revenue", date(2006, 3, 31), "quarter", 1.0, "EUR", ny(date(2006, 9, 1), 7),
                    vintage="restated"))


def test_two_originals_for_one_period_are_refused():
    fs, q = _fs()
    with pytest.raises(EquityDataError, match="two originals"):
        fs.add(Fact("C1", "revenue", q, "quarter", 101.0, "USD", ny(date(2006, 6, 1), 8)))


# ----------------------------------------------------------------------------- analyst estimates
def test_late_analyst_revisions_are_excluded_from_consensus():
    book = EstimateBook()
    p = date(2006, 12, 31)
    book.add(Estimate("C1", "B1", "eps", p, 1.00, "USD", ny(date(2006, 9, 1), 8), ny(date(2006, 9, 1), 9)))
    book.add(Estimate("C1", "B2", "eps", p, 1.10, "USD", ny(date(2006, 9, 5), 8), ny(date(2006, 9, 5), 9)))
    # B1 revises on 2006-10-02, but the vendor recorded the revision only on 2006-11-20 (backfilled)
    book.add(Estimate("C1", "B1", "eps", p, 1.40, "USD", ny(date(2006, 10, 2), 8), ny(date(2006, 11, 20), 9)))
    c = book.consensus("C1", "eps", p, ny(date(2006, 10, 15), 12))
    assert c.n == 2 and c.mean == pytest.approx(1.05)
    c2 = book.consensus("C1", "eps", p, ny(date(2006, 11, 21), 12))
    assert c2.mean == pytest.approx(1.25)
    rv = book.revisions("C1", "eps", p, ny(date(2006, 9, 10), 0), ny(date(2006, 10, 15), 0))
    assert rv["up"] == 0                                         # the late revision is not yet seen
    rv = book.revisions("C1", "eps", p, ny(date(2006, 9, 10), 0), ny(date(2006, 12, 1), 0))
    assert rv["up"] == 1 and rv["breadth"] == pytest.approx(0.5)


def test_coverage_termination_and_staleness():
    book = EstimateBook(max_age_days=60)
    p = date(2006, 12, 31)
    book.add(Estimate("C1", "B1", "eps", p, 1.0, "USD", ny(date(2006, 6, 1), 8), action="initiate"))
    book.add(Estimate("C1", "B2", "eps", p, 2.0, "USD", ny(date(2006, 9, 1), 8), action="initiate"))
    book.add(Estimate("C1", "B2", "eps", p, None, None, ny(date(2006, 9, 20), 8), action="drop"))
    assert book.consensus("C1", "eps", p, ny(date(2006, 9, 10), 12)).n == 1      # B1 stale, B2 live
    assert book.consensus("C1", "eps", p, ny(date(2006, 9, 25), 12)) is None    # B1 stale, B2 dropped
    assert book.coverage("C1", ny(date(2006, 9, 10), 12)) == ("B2",)


# ----------------------------------------------------------------------------- earnings events
def test_scheduled_date_is_not_a_release_and_labels_must_match():
    ev = EarningsEvent("C1", date(2006, 3, 31), scheduled=date(2006, 5, 2), schedule_known=date(2006, 4, 10))
    with pytest.raises(TemporalError, match="scheduled"):
        usable_close(ev, CAL)
    assert scheduled_known(ev, date(2006, 4, 1)) is None and scheduled_known(ev, date(2006, 4, 11)) == date(2006, 5, 2)
    bad = EarningsEvent("C1", date(2006, 3, 31), released=ny(date(2006, 5, 2), 8), time_of_day="after_close")
    with pytest.raises(TemporalError, match="labelled"):
        check_label(bad, CAL)
    amc = EarningsEvent("C1", date(2006, 3, 31), released=ny(date(2006, 5, 2), 16, 5), time_of_day="after_close")
    bmo = EarningsEvent("C1", date(2006, 3, 31), released=ny(date(2006, 5, 2), 7), time_of_day="before_open")
    unk = EarningsEvent("C1", date(2006, 3, 31), released=ny(date(2006, 5, 2), 7), time_of_day="unknown")
    assert usable_close(amc, CAL) == date(2006, 5, 3)
    assert usable_close(bmo, CAL) == date(2006, 5, 2)
    assert usable_close(unk, CAL) == date(2006, 5, 3)             # unknown time of day: treated as after close


def test_surprise_uses_only_estimates_before_release():
    book = EstimateBook()
    p = date(2006, 3, 31)
    book.add(Estimate("C1", "B1", "eps", p, 1.0, "USD", ny(date(2006, 4, 1), 8)))
    book.add(Estimate("C1", "B2", "eps", p, 1.2, "USD", ny(date(2006, 4, 3), 8)))
    ev = EarningsEvent("C1", p, released=ny(date(2006, 5, 2), 16, 5), time_of_day="after_close")
    s0 = surprise(ev, 1.5, book, "eps")
    # a revision published right after the release must not enter the surprise's consensus
    book.add(Estimate("C1", "B1", "eps", p, 1.5, "USD", ny(date(2006, 5, 2), 16, 30)))
    assert surprise(ev, 1.5, book, "eps") == s0
    assert s0["consensus"] == pytest.approx(1.1) and s0["n"] == 2


# ----------------------------------------------------------------------------- bridge to the existing PIT store
def test_restatement_exported_to_pitstore_follows_the_stores_own_rules():
    fs, q = _fs()
    store = PitStore()
    names = pit_bridge.fundamentals_to_pit(fs, store, sources.synthetic_contract("fundamentals_pit"))
    assert names == ["eq.fund.C1.revenue"]
    w = Window(store, date(2005, 1, 3), date(2008, 12, 31), "exploration", "equities_test", "session")
    _, v = w.as_of("eq.fund.C1.revenue", date(2006, 6, 1))
    assert list(v) == [100.0]
    _, v = w.as_of("eq.fund.C1.revenue", date(2007, 3, 1))
    assert list(v) == [90.0]
    _, v = w.as_of("eq.fund.C1.revenue", date(2006, 5, 2))
    assert list(v) == []


def test_bridge_refuses_licensed_or_unverified_sources():
    fs, _ = _fs()
    lic = sources.DataContract("lic", "fundamentals_pit", "v", "licensed", "doc", "filing_acceptance_time",
                               "vintaged", True, ("signal",))
    with pytest.raises(ContractError, match="public repository"):
        pit_bridge.fundamentals_to_pit(fs, PitStore(), lic)
    pit_bridge.fundamentals_to_pit(fs, PitStore(), lic, private_store=True)
    desc = sources.DataContract("d", "fundamentals_pit", "v", "public", "doc", "unknown", "unknown", False,
                                ("descriptive",))
    with pytest.raises(ContractError):
        pit_bridge.fundamentals_to_pit(fs, PitStore(), desc)


def test_prices_bridge_includes_delisting_return():
    w = syn.world()
    store = PitStore()
    pit_bridge.prices_to_pit(w.prices, store, sources.synthetic_contract("prices_daily"), ["S04"],
                             date(2006, 1, 3), date(2006, 12, 29))
    win = Window(store, date(2006, 1, 3), date(2006, 12, 29), "exploration", "equities_test", "session")
    p, v = win.as_of("eq.px.S04", date(2006, 12, 29))
    assert p[-1] == np.datetime64("2006-07-03") and v[-1] / v[-2] - 1 == pytest.approx(-0.35)
