"""Non-technology equities as a fourth research track on the shared equity pipeline (issue #102). Synthetic only.

Covers: the sector taxonomy and classification policy; point-in-time sector membership with reclassifications
across tracks; survivorship (delistings, IPO, liquidity); corporate actions; instruments outside the equity tracks;
measured volatility; the technology-only, non-technology-only and combined portfolio comparison with costs,
lagged execution and out-of-sample controls; and the non-technology hypothesis catalogue with cross-track counting.
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from manhattan.equities import catalogue as C
from manhattan.equities import sector_synthetic as SS
from manhattan.equities import sectors as SEC
from manhattan.equities import track_compare as TC
from manhattan.equities import universe as U
from manhattan.equities.costs import EquityCostModel
from manhattan.equities.errors import CorporateActionError, EquityDataError

ROOT = Path(__file__).resolve().parents[1]
TECH, NONTECH = SEC.TECHNOLOGY_TRACK, SEC.NON_TECHNOLOGY_TRACK
COSTS = dict(half_spread=0.0005, commission=0.0001, impact=0.1, short_financing=0.0, long_financing=0.0,
             recall_cost=0.0, reference="S16 synthetic test assumption, not a measurement")
CFG = TC.CompareConfig(is_end=date(2006, 12, 29), lookbacks=(63, 126))


@pytest.fixture(scope="module")
def world():
    return SS.sector_world()


@pytest.fixture(scope="module")
def rules():
    return {t: U.track_rules(t) for t in SEC.EQUITY_TRACKS}


def _snaps(w, rules, d):
    return U.track_snapshots(w.master, w.prices, w.classes, w.calendar.session_on_or_before(d), rules)


def _member_track(snaps, sid):
    hits = [t for t, s in snaps.items() if sid in s.members]
    assert len(hits) <= 1
    return hits[0] if hits else None


# ------------------------------------------------------------------------------------------------ taxonomy

def test_the_ten_non_technology_sectors_and_their_categories():
    assert set(SEC.NON_TECH_SECTORS) == {"healthcare", "financials", "industrials", "utilities", "consumer_staples",
                                         "consumer_discretionary", "materials", "energy", "real_estate",
                                         "communication_services"}
    cats = [c for cs in SEC.NON_TECH_SECTORS.values() for c in cs]
    assert len(cats) == len(set(cats)) and not set(cats) & set(U.TECH_CATEGORIES)
    for c in cats:
        assert SEC.track_of(c) == NONTECH and SEC.sector_of(c) in SEC.NON_TECH_SECTORS
    for c in U.TECH_CATEGORIES:
        assert SEC.track_of(c) == TECH and SEC.sector_of(c) == "technology"
    # boundary policy: the package taxonomy, not vendor sector names
    assert SEC.track_of("consumer_internet") == SEC.track_of("digital_advertising") == TECH
    assert SEC.sector_of("payments") == "financials" and SEC.sector_of("telecom_carriers") == "communication_services"
    # the legacy catch-all and unknown labels are in no track (fail closed)
    assert SEC.track_of(SEC.LEGACY_UNASSIGNED) is None and SEC.track_of("widgets") is None and SEC.track_of(None) is None


def test_track_rules_share_everything_but_categories_and_refuse_strays():
    t, n = U.track_rules(TECH), U.track_rules(NONTECH)
    shared = {k: v for k, v in t.__dict__.items() if k not in ("categories", "security_types")}
    assert shared == {k: v for k, v in n.__dict__.items() if k not in ("categories", "security_types")}
    assert "reit" in n.security_types and "reit" not in t.security_types
    with pytest.raises(EquityDataError):
        U.track_rules(NONTECH, categories=("banks", "semiconductors"))
    with pytest.raises(EquityDataError):
        U.track_rules(NONTECH, security_types=("common", "etf"))
    with pytest.raises(ValueError):
        U.track_rules("combined_equities")
    with pytest.raises(EquityDataError):                     # an unknown category cannot even be recorded
        U.Classification("CZ", "widgets", date(2000, 1, 1), None, known_from=date(2000, 1, 1))


# ------------------------------------------------------------------------------- point-in-time membership

def test_tracks_are_disjoint_and_together_equal_one_shared_universe(world, rules):
    union_rules = U.EligibilityRules(categories=U.TECH_CATEGORIES + SEC.NON_TECH_CATEGORIES,
                                     security_types=SEC.NON_TECH_SECURITY_TYPES)
    for d in world.days[300::63]:
        snaps = U.track_snapshots(world.master, world.prices, world.classes, d, rules)
        assert not set(snaps[TECH].members) & set(snaps[NONTECH].members)
        both = U.UniverseBuilder(world.master, world.prices, world.classes, union_rules).snapshot(d)
        tech_cats = set(U.TECH_CATEGORIES)
        expected = set(snaps[NONTECH].members) | {s for s in snaps[TECH].members}
        got = {s for s in both.members if both.categories[s] not in tech_cats or
               world.master.security(s).security_type in ("common", "adr")}
        assert got == expected, d


def test_a_misconfigured_track_universe_is_refused(world, rules):
    d = world.calendar.session_on_or_before(date(2006, 6, 30))
    wrong = {TECH: U.EligibilityRules(categories=U.TECH_CATEGORIES + ("banks",)), NONTECH: rules[NONTECH]}
    with pytest.raises(EquityDataError, match="not in the technology_equities track"):
        U.track_snapshots(world.master, world.prices, world.classes, d, wrong)


def test_a_reclassification_moves_track_only_from_its_publication(world, rules):
    # CT6 -> payments, effective 2006-03-20, announced 2006-03-01
    assert _member_track(_snaps(world, rules, date(2006, 3, 17)), "T06") == TECH
    assert _member_track(_snaps(world, rules, date(2006, 3, 20)), "T06") == NONTECH
    # CT7 -> automobiles, effective 2005-07-01 but published 2007-02-01 (a vendor backfill)
    assert _member_track(_snaps(world, rules, date(2006, 6, 30)), "T07") == TECH
    assert _member_track(_snaps(world, rules, date(2007, 2, 1)), "T07") == NONTECH
    # the retrospective label exists for description, and the universe never uses it
    assert world.classes.category("CT7", date(2006, 6, 30), as_known_at=date(2008, 1, 2)) == "automobiles"
    assert world.classes.category("CT7", date(2006, 6, 30)) == "technology_hardware"
    hist = SEC.track_history(world.classes, "CT7", [date(2006, 6, 30), date(2007, 1, 31), date(2007, 2, 1)])
    assert [t for _, t in hist] == [TECH, TECH, NONTECH]


def test_survivorship_delistings_ipo_and_liquidity(world, rules):
    before = _snaps(world, rules, date(2006, 6, 30))
    after = _snaps(world, rules, date(2006, 11, 30))
    assert "E01" in before[NONTECH].members and "E01" not in after[NONTECH].members      # bankrupt later
    assert "F01" in _snaps(world, rules, date(2007, 5, 31))[NONTECH].members              # acquired later
    assert "T05" in _snaps(world, rules, date(2006, 12, 29))[TECH].members                # failed later
    assert "H02" not in _snaps(world, rules, date(2006, 3, 31))[NONTECH].excluded          # not yet listed
    assert "H02" not in _snaps(world, rules, date(2006, 3, 31))[NONTECH].members
    assert any("history" in r for r in _snaps(world, rules, date(2006, 9, 29))[NONTECH].excluded["H02"])
    assert "H02" in _snaps(world, rules, date(2007, 6, 29))[NONTECH].members
    for d in (date(2005, 6, 30), date(2007, 6, 29)):
        assert "dollar volume" in _snaps(world, rules, d)[NONTECH].excluded["D02"]
    # the delisting return is part of the outcome once known, and refused before it was known
    last = date(2006, 9, 29)
    with pytest.raises(CorporateActionError, match="survivorship"):
        world.prices.total_returns("E01", date(2006, 9, 1), date(2006, 10, 2), as_of=date(2006, 10, 2))
    rs = world.prices.total_returns("E01", date(2006, 9, 1), date(2006, 10, 31), as_of=date(2006, 10, 31))
    assert rs.delisting_day == world.calendar.next_session(last) and rs.returns[-1] < -0.55   # booked next session


def test_corporate_actions_change_raw_prices_not_total_returns(world):
    days = list(world.days)
    i = days.index(date(2006, 5, 15))                                      # the 3:1 split
    bars = world.prices.bars("I01", days[i - 1], days[i])
    assert bars[1].close < bars[0].close / 2.5
    rs = world.prices.total_returns("I01", days[i - 1], days[i], as_of=days[i])
    assert abs(rs.returns[-1]) < 0.15
    ex = [d for d in days if d.month == 6 and d.year == 2006 and 10 <= d.day <= 16 and d.weekday() == 0][0]
    j = days.index(ex)                                                     # a utility dividend
    raw = world.prices.bars("U01", days[j - 1], ex)
    tr = world.prices.total_returns("U01", days[j - 1], ex, as_of=ex).returns[-1]
    assert tr - (raw[1].close / raw[0].close - 1) == pytest.approx(SS.DIVIDENDS["U01"] / raw[0].close, rel=1e-6)


def test_funds_and_unassigned_companies_are_in_no_equity_track(world, rules):
    for d in world.days[300::126]:
        snaps = U.track_snapshots(world.master, world.prices, world.classes, d, rules)
        assert _member_track(snaps, "X01") is None
        assert any("security type etf" in r or "category None" in r for r in snaps[NONTECH].excluded["X01"])
    assert "R01" in _snaps(world, rules, date(2006, 6, 30))[NONTECH].members              # the REIT is in


def test_volatility_is_measured_not_assumed(world):
    v = TC.sector_volatility(world, date(2004, 1, 2), date(2008, 12, 31))["by_sector"]
    tech = v["technology"]["sector_index_ann_vol"]
    calmer = [s for s, x in v.items() if s != "technology" and x["sector_index_ann_vol"] < tech]
    riskier = [s for s, x in v.items() if s != "technology" and x["sector_index_ann_vol"] > tech]
    assert "energy" in riskier and "utilities" in calmer
    assert riskier, "a non-technology sector is more volatile than technology in this world: never assume otherwise"
    assert set(v) == set(SEC.NON_TECH_SECTORS) | {"technology"}


# ------------------------------------------------------------------------------------ portfolio comparison

@pytest.fixture(scope="module")
def cost_model():
    return EquityCostModel(**COSTS)


@pytest.fixture(scope="module")
def null_report(world, cost_model):
    return TC.compare(world, CFG, cost_model)


@pytest.fixture(scope="module")
def planted_report(cost_model):
    return TC.compare(SS.sector_world(planted_momentum=0.004, planted_track=NONTECH), CFG, cost_model)


def test_reports_are_labelled_infrastructure_never_evidence(null_report):
    r = null_report
    assert (r["evidential_weight"], r["confirmatory"], r["scientifically_validated"]) == (0, False, False)
    assert r["evidence_class"] == "synthetic_infrastructure"
    assert r["execution"] == {"lag_sessions": 1, "fill": "close of decision day + lag", "same_close": False}
    assert r["combined_equities"]["components_counted_in"] == [TECH, NONTECH]
    assert r["cost_model"]["reference"] == COSTS["reference"]


def test_every_variant_is_reported_and_chosen_in_sample_only(null_report):
    for t in (TECH, NONTECH):
        v = null_report["tracks"][t]
        assert v["variants_tried"] == len(CFG.lookbacks) and set(v["in_sample_by_variant"]) == set(CFG.lookbacks)
        best = max(CFG.lookbacks, key=lambda lb: (v["in_sample_by_variant"][lb]["sharpe"], -lb))
        assert v["chosen_lookback"] == best
        for part in (v["out_of_sample_chosen"], v["benchmark_equal_weight"]["out_of_sample"],
                     v["out_of_sample_excess_over_benchmark"]):
            assert np.isfinite(part["sharpe"]) and part["max_drawdown"] <= 0
        assert v["out_of_sample_chosen"]["cost_drag"] > 0
    assert -1 <= null_report["out_of_sample_correlation_tech_vs_nontech"] <= 1


def test_excess_is_over_the_tracks_own_costed_equal_weight_universe(null_report):
    for t in (TECH, NONTECH):
        v = null_report["tracks"][t]
        ex, sl, bm = (v["out_of_sample_excess_over_benchmark"], v["out_of_sample_chosen"],
                      v["benchmark_equal_weight"]["out_of_sample"])
        assert ex["ann_return"] == pytest.approx(sl["ann_return"] - bm["ann_return"], abs=1e-12)
        assert ex["days"] == sl["days"] == bm["days"]


def test_in_sample_results_do_not_depend_on_anything_after_the_cutoff(world, cost_model, null_report):
    cut = TC.compare(world, CFG, cost_model, end=world.calendar.session_on_or_before(date(2007, 1, 31)))
    for t in (TECH, NONTECH):
        a, b = null_report["tracks"][t], cut["tracks"][t]
        assert a["chosen_lookback"] == b["chosen_lookback"]
        assert a["in_sample_by_variant"] == b["in_sample_by_variant"]


def test_a_planted_effect_is_found_in_its_track_only(null_report, planted_report):
    nt = planted_report["tracks"][NONTECH]["out_of_sample_excess_over_benchmark"]["sharpe"]
    assert nt > 1.0
    assert planted_report["tracks"][TECH] == null_report["tracks"][TECH]   # the technology sleeve is untouched


def test_outcomes_carry_delisting_returns_and_then_cash(world):
    o = TC._Outcomes(world).get("E01")
    booked = world.calendar.next_session(date(2006, 9, 29))
    assert o[booked] < -0.55 and max(o) == booked                          # the loss is booked; then nothing (cash)
    assert TC._Outcomes(world).get("F01")[world.calendar.next_session(date(2007, 6, 29))] > 0.2


def test_same_close_execution_and_missing_costs_are_refused(world):
    with pytest.raises(EquityDataError, match="lag"):
        TC.CompareConfig(is_end=date(2006, 12, 29), lag=0)
    with pytest.raises(EquityDataError, match="cost model"):
        TC.run_sleeve(world, CFG, None, {NONTECH: 63}, name="x")
    with pytest.raises(EquityDataError):
        TC.run_sleeve(world, CFG, EquityCostModel(**COSTS), {"combined_equities": 63}, name="x")


def test_costs_lower_net_returns_and_vanish_with_zero_costs(world):
    free = EquityCostModel(**{**COSTS, "half_spread": 0.0, "commission": 0.0, "impact": 0.0})
    a = TC.run_sleeve(world, CFG, EquityCostModel(**COSTS), {NONTECH: 63}, name="a", end=date(2006, 6, 30))
    b = TC.run_sleeve(world, CFG, free, {NONTECH: 63}, name="b", end=date(2006, 6, 30))
    assert np.array_equal(a.gross, b.gross) and sum(b.costs) == 0 and sum(a.costs) > 0
    assert a.net.sum() < b.net.sum()
    for d, e, n_members, n_held in a.decisions:                           # every fill strictly after its decision
        assert e > d and 0 < n_held <= n_members


# ----------------------------------------------------------------------------------------------- catalogue

@pytest.fixture(scope="module")
def cats():
    return C.load(), C.load(C.NT_PATH)


def test_nontech_catalogue_validates_and_counts_with_the_technology_catalogue(cats):
    te, nt = cats
    assert C.validate(te) == [] and C.validate(nt) == []
    assert C.programme_of(nt) == NONTECH and C.programme_of(te) == TECH
    rep = C.cross_track_report(te, nt)
    assert rep["problems"] == [] and rep["by_track"] == {TECH: 39, NONTECH: 5} and rep["combined_families"] == 44
    names = {f["research_family"] for f in nt["families"]}
    assert names == set(C.NT_RESEARCH_FAMILIES)
    for link in rep["links"]:
        assert link["role"] == "related_not_designated"
        assert link["independent_evidence"] is (False if link["technology"] else None)
    for f in nt["families"]:
        d = C.family_draft(f, programme=NONTECH)
        assert d["programme"] == NONTECH and d["status"] == "draft" and d["cross_track_mechanism"].startswith("XM-")


@pytest.mark.parametrize("mutate,expect", [
    (lambda f: f.update(grouped_variants="lookbacks only"), "sector-neutral"),
    (lambda f: f["cross_track"].update(role="confirmed"), "role"),
    (lambda f: f["cross_track"].update(technology_counterpart=None, role="designated_replication"), "replication"),
    (lambda f: f.update(cross_sector_validation="none"), "leave_one_sector_out"),
    (lambda f: f.update(id="TE-M09"), "NT-"),
    (lambda f: f.update(rationale=f["rationale"] + " It earned 12% a year."), "performance"),
])
def test_nontech_catalogue_validation_catches_bad_entries(cats, mutate, expect):
    nt = copy.deepcopy(cats[1])
    mutate(nt["families"][2])
    assert any(expect in e for e in C.validate(nt)), C.validate(nt)


def test_cross_track_links_must_resolve_and_never_share_a_mechanism(cats):
    te, nt = copy.deepcopy(cats[0]), copy.deepcopy(cats[1])
    nt["families"][0]["cross_track"]["technology_counterpart"] = "TE-Z99"
    nt["families"][1]["cross_track"]["mechanism"] = nt["families"][2]["cross_track"]["mechanism"]
    probs = C.cross_track_report(te, nt)["problems"]
    assert any("TE-Z99" in p for p in probs) and any("already used" in p for p in probs)


def test_rendered_nontech_catalogue_document_is_in_sync(cats):
    doc = ROOT / "docs/manhattan/equities/HYPOTHESIS_CATALOGUE_NONTECH.md"
    assert doc.read_text(encoding="utf-8") == C.render(cats[1]) + "\n", \
        "regenerate with: python -m manhattan.equities.catalogue render --programme non_technology_equities " \
        "--out docs/manhattan/equities/HYPOTHESIS_CATALOGUE_NONTECH.md"
