"""Technology equities: point-in-time universe, classification history and cross-sectional features. Synthetic only."""
from __future__ import annotations

import copy
from datetime import date

import numpy as np
import pytest

from manhattan.equities import features as F
from manhattan.equities import synthetic as syn
from manhattan.equities.errors import EquityDataError, IdentityError, NeutralizationError
from manhattan.equities.prices import Bar
from manhattan.equities.universe import (Classification, ClassificationHistory, EligibilityRules, UniverseBuilder,
                                         assert_snapshot_for)

RULES = EligibilityRules(min_market_cap=1e8)


@pytest.fixture(scope="module")
def world():
    return syn.world()


def builder(w, **kw):
    return UniverseBuilder(w.master, w.prices, w.classes, kw.pop("rules", RULES), fundamentals=w.fundamentals, **kw)


def test_survivorship_delisted_and_acquired_names_are_members_before_they_leave(world):
    snap = builder(world).snapshot(date(2006, 6, 30))
    assert "S04" in snap.members                  # delisted for performance after this close
    assert "S06" in snap.members                  # acquired in 2007
    later = builder(world).snapshot(date(2007, 6, 29))
    assert "S04" not in later.members and "S06" not in later.members and "S04" not in later.excluded


def test_ipos_are_absent_before_listing_and_need_history(world):
    assert "S05" not in builder(world).snapshot(date(2005, 6, 30)).excluded       # not yet listed: not a candidate
    snap = builder(world).snapshot(date(2006, 6, 30))
    assert any("history" in r for r in snap.excluded["S05"])
    assert "S05" in builder(world).snapshot(date(2007, 6, 29)).members


def test_future_data_cannot_change_a_snapshot(world):
    day = date(2006, 6, 30)
    before = builder(world).snapshot(day)
    w2 = copy.deepcopy(world)
    # tamper with everything after the day: prices, a crash, a late reclassification, a new issuer
    for sid in w2.prices.securities():
        for d in w2.calendar.sessions_between(date(2006, 7, 3), date(2006, 7, 31)):
            w2.prices._bars.get(sid, {}).pop(d, None)
            w2.prices.add_bar(Bar(sid, d, 0.5, "USD", 1.0))
    w2.classes.add(Classification("C01", "non_technology", date(2000, 1, 1), known_from=date(2006, 7, 5)))
    after = builder(w2).snapshot(day)
    assert before.members == after.members and before.excluded == after.excluded
    assert before.membership_hash() == after.membership_hash()


def test_late_reclassification_is_not_used_before_publication(world):
    # C08 was reclassified to digital advertising effective 2005, but published only on 2007-01-15
    assert world.classes.category("C08", date(2006, 6, 30)) == "consumer_internet"
    assert world.classes.category("C08", date(2006, 6, 30), as_known_at=date(2007, 2, 1)) == "digital_advertising"
    assert builder(world).snapshot(date(2006, 6, 30)).categories["S08"] == "consumer_internet"
    assert builder(world).snapshot(date(2008, 6, 30)).categories["S08"] == "digital_advertising"


def test_category_filter_and_rules_reasons(world):
    r = EligibilityRules(categories=("semiconductors",), min_market_cap=1e8)
    snap = builder(world, rules=r).snapshot(date(2006, 6, 30))
    assert snap.members == ("S01", "S02")
    assert any("category" in x for x in snap.excluded["S03"])
    with pytest.raises(EquityDataError, match="session"):
        builder(world).snapshot(date(2006, 7, 4))


def test_borrow_requirement_without_data_fails_closed(world):
    with pytest.raises(EquityDataError, match="borrow"):
        UniverseBuilder(world.master, world.prices, world.classes, EligibilityRules(require_borrow=True))
    from manhattan.equities.costs import BorrowBook
    snap = UniverseBuilder(world.master, world.prices, world.classes,
                           EligibilityRules(require_borrow=True, min_market_cap=1e8), fundamentals=world.fundamentals,
                           borrow=BorrowBook()).snapshot(date(2006, 6, 30))
    assert snap.members == () and all("borrow unknown" in r for r in snap.excluded.values())


def test_snapshot_must_match_the_computation_date(world):
    snap = builder(world).snapshot(date(2006, 6, 30))
    with pytest.raises(IdentityError, match="future or stale"):
        assert_snapshot_for(snap, date(2006, 6, 29))


def test_classification_conflict_in_one_publication():
    h = ClassificationHistory([Classification("C1", "cybersecurity", date(2005, 1, 1), known_from=date(2005, 1, 1))])
    with pytest.raises(EquityDataError):
        h.add(Classification("C1", "networking", date(2005, 6, 1), known_from=date(2005, 1, 1)))


# ----------------------------------------------------------------------------- features
def panel(world, ids, start=date(2004, 1, 2), end=date(2008, 12, 31)):
    days = np.array(world.calendar.sessions_between(start, end), dtype=object)
    R = np.full((len(days), len(ids)), np.nan)
    for j, s in enumerate(ids):
        lp = world.log_prices[s]
        r = np.r_[np.nan, np.diff(lp)]
        R[:, j] = np.expm1(r)[: len(days)]
    return F.ReturnPanel(days, tuple(ids), R)


def test_features_ignore_data_after_as_of(world):
    day = date(2006, 6, 30)
    snap = builder(world).snapshot(day)
    p = panel(world, sorted(world.log_prices))
    m = np.nansum(p.R, axis=1) / np.maximum(np.isfinite(p.R).sum(axis=1), 1)
    a = F.momentum(p, snap, day).values
    b = F.residual_momentum(p, m, snap, day).values
    R2 = p.R.copy()
    later = np.array([d > day for d in p.days])
    R2[later] = 0.5                                       # an absurd future
    p2 = F.ReturnPanel(p.days, p.ids, R2)
    m2 = m.copy()
    m2[later] = 0.5
    assert np.array_equal(a, F.momentum(p2, snap, day).values, equal_nan=True)
    assert np.array_equal(b, F.residual_momentum(p2, m2, snap, day).values, equal_nan=True)
    assert np.array_equal(F.rolling_beta(p, m, snap, day).values, F.rolling_beta(p2, m2, snap, day).values,
                          equal_nan=True)


def test_feature_on_a_different_universe_date_is_refused(world):
    snap = builder(world).snapshot(date(2006, 6, 30))
    p = panel(world, sorted(world.log_prices))
    with pytest.raises(IdentityError):
        F.momentum(p, snap, date(2006, 7, 31))


def test_industry_relative_sums_to_zero_within_category(world):
    day = date(2006, 6, 30)
    snap = builder(world).snapshot(day)
    p = panel(world, sorted(world.log_prices))
    rel = F.industry_relative(F.momentum(p, snap, day), snap)
    for cat in set(snap.categories.values()):
        v = np.array([x for s, x in zip(rel.ids, rel.values) if snap.categories[s] == cat])
        if np.isfinite(v).sum() >= 2:
            assert abs(np.nansum(v)) < 1e-12


def test_correct_neutralisation_is_verified_and_incorrect_is_caught():
    rng = np.random.default_rng(3)
    n = 200
    beta, size = rng.normal(1, 0.3, n), rng.normal(0, 1, n)
    x = 0.8 * beta + 0.5 * size + rng.normal(0, 1, n)
    expos = np.column_stack([beta, size])
    res = F.neutralize(x, expos)
    F.check_neutral(res, expos, names=["beta", "size"])
    # neutralising against beta only leaves the size exposure: caught
    res_beta_only = F.neutralize(x, beta)
    with pytest.raises(NeutralizationError, match="size"):
        F.check_neutral(res_beta_only, expos, names=["beta", "size"])
    # demeaning (a common shortcut) is not beta neutralisation
    with pytest.raises(NeutralizationError):
        F.check_neutral(x - x.mean(), beta[:, None], names=["beta"])
    # collinear design is refused rather than silently solved
    with pytest.raises(NeutralizationError, match="rank"):
        F.neutralize(x, np.column_stack([beta, 2 * beta]))
    with pytest.raises(NeutralizationError):
        F.neutralize(x[:3], beta[:3])


def test_group_neutralisation_and_candidate_signals_need_a_hypothesis():
    rng = np.random.default_rng(4)
    n = 60
    g = np.array(["a", "b", "c"] * 20)
    beta = rng.normal(1, 0.2, n)
    x = rng.normal(0, 1, n) + (g == "a") * 2 + beta
    r = F.neutralize(x, beta, groups=g)
    for k in "abc":
        assert abs(r[g == k].mean()) < 1e-10
    cs = F.CrossSection("x", date(2006, 6, 30), tuple(f"S{i}" for i in range(n)), x)
    with pytest.raises(EquityDataError, match="hypothesis"):
        F.CrossSection("x", cs.as_of, cs.ids, x, kind="candidate_signal")
    sig = F.candidate_signal(cs, "TE-A07", neutral_to=beta, groups=g, names=["beta"])
    assert sig.kind == "candidate_signal" and sig.hypothesis == "TE-A07" and sig.evidential_weight == 0
    with pytest.raises(EquityDataError, match="evidential"):
        F.CrossSection("x", cs.as_of, cs.ids, x, evidential_weight=1)


def test_normalisers():
    x = np.array([1.0, 2.0, 2.0, np.nan, 100.0])
    r = F.rank_normalize(x)
    assert np.isnan(r[3]) and r[1] == r[2] and r[4] > r[0]
    z = F.zscore(x)
    assert np.nanmean(z) == pytest.approx(0.0)
    wz = F.winsorize(np.arange(100.0), 0.05, 0.95)
    assert wz.max() < 99 and wz.min() > 0


def test_fundamental_exposures_use_known_values(world):
    day = date(2006, 6, 30)
    snap = builder(world).snapshot(day)
    g = F.growth_exposure("revenue", world.fundamentals, snap, day, world.master.company_of)
    assert g.kind == "exposure" and len(g.values) == len(snap.members)
    v = F.valuation_exposure("revenue", world.fundamentals, world.prices, snap, day, world.master.company_of)
    assert np.isfinite(v.values).all()
    with pytest.raises(EquityDataError):
        F.fundamental_exposure("not_a_factor", world.fundamentals, snap, day, world.master.company_of)
