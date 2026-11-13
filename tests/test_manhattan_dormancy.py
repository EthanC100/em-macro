"""Dormancy as revised in Protocol v3.1 section 9.1 before adoption (``manhattan/stats/dormancy.py``): the
forecast of 3.0 **and** the family's own forward record. Synthetic inputs only.

The rule of 3.0 is in ``manhattan/stats/tiers.py``, which is version 1's code and is not edited; its tests are in
``tests/test_manhattan_tiers.py``.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

from manhattan.sim import run
from manhattan.stats import dormancy, tiers
from manhattan.testing import reads_hand_edited_file

ROOT = Path(__file__).resolve().parents[1]


def review(pp=0.0, pi=0.10, days=1000, **kw) -> tiers.Review:
    return tiers.Review(pi_min=pi, forward_days=days, forward_mean_positive=True, pp_max=pp, **kw)


def walk(steps, s=None):
    s = s or tiers.State()
    for r, p in steps:
        s = dormancy.step(s, r, p)
    return s


# ------------------------------------------------------------------ the forward record's p-value

def test_forward_p_is_the_one_sided_p_value_of_the_forward_record_against_theta_min():
    # hand numbers: at the edge itself 0.5; 1.645 standard errors below it 0.05; two above it 0.977
    p = dormancy.forward_p([0.25, 0.25 - 1.6449 * 0.5, 0.25 + 2 * 0.4, -0.75], [0.5, 0.5, 0.4, 0.5], [800, 800, 800, 800])
    assert p == pytest.approx([0.5, 0.05, 0.97725, norm.cdf(-2.0)], abs=1e-4)
    # no forward estimate, no standard error, or less than a year of forward days: no evidence against the family
    assert dormancy.forward_p([math.nan, -3.0, -3.0, -3.0], [1.0, 0.0, 1.0, math.nan], [800, 800, 251, 800]).tolist() == [1.0] * 4
    assert dormancy.forward_p([-3.0], [1.0], [252])[0] < 0.001                    # 252 days is enough
    assert dormancy.MIN_FORWARD_DAYS == 252 == tiers.DAYS_PROMISING_EXIT
    assert (dormancy.DORMANT_BELOW, dormancy.REACTIVATE_AT) == (0.05, 0.15) == (tiers.DORMANT_BELOW, tiers.REACTIVATE_AT)
    assert dormancy.THETA_MIN == tiers.THETA_MIN == 0.25


# ------------------------------------------------------------------ the rule

def test_a_hopeless_forecast_alone_no_longer_retires_a_family():
    """The case the pilot found: the forecast is zero at every review, the family's own record is not against it."""
    s = walk([(review(pp=0.0), 0.60)] * 5)
    assert not s.dormant and s.low_pp == 0
    old = tiers.State()
    for _ in range(2):
        old = tiers.step(old, review(pp=0.0))
    assert old.dormant                                                            # the rule of 3.0 did


def test_both_conditions_at_two_consecutive_reviews():
    s = walk([(review(pp=0.01), 0.01)])
    assert not s.dormant and s.low_pp == 1
    s = dormancy.step(s, review(pp=0.01), 0.04)
    assert s.dormant and "dormant" in s.events and s.recording                    # a cheap family keeps recording
    assert not dormancy.step(tiers.State(low_pp=1), review(pp=0.01, cheap=False), 0.01).recording
    # a review in between at which either condition fails starts the count again
    for r, p in ((review(pp=0.01), 0.05), (review(pp=0.05), 0.01)):               # 0.05 is not below 0.05
        s = walk([(review(pp=0.01), 0.01), (r, p)])
        assert not s.dormant and s.low_pp == 0
        assert not dormancy.step(s, review(pp=0.01), 0.01).dormant
    # the forward record alone is not enough either
    assert not walk([(review(pp=0.06), 0.001)] * 4).dormant


def test_reactivation_by_either_condition_with_hysteresis():
    dormant = walk([(review(pp=0.01), 0.01)] * 2)
    assert dormant.dormant
    for r, p in ((review(pp=0.01), 0.15), (review(pp=0.15), 0.01), (review(pp=0.01, ethan_reactivates=True), 0.01)):
        s = dormancy.step(dormant, r, p)
        assert not s.dormant and "reactivated" in s.events and s.low_pp in (0, 1)
    for r, p in ((review(pp=0.14), 0.14), (review(pp=0.01), 0.10)):               # between the two thresholds: stays put aside
        assert dormancy.step(dormant, r, p).dormant
    # a reactivated family needs two more reviews to be put aside again
    s = dormancy.step(dormant, review(pp=0.20), 0.01)
    assert not s.dormant and not dormancy.step(s, review(pp=0.01), 0.01).dormant
    assert dormancy.step(dormancy.step(s, review(pp=0.01), 0.01), review(pp=0.01), 0.01).dormant


def test_a_review_without_a_forecast_puts_nobody_aside_but_can_wake():
    """The programme's last date, or T_end unset: there is no forecast."""
    s = walk([(review(pp=0.01), 0.01), (review(pp=None), 0.001)])
    assert not s.dormant and s.low_pp == 1                                        # the count neither grows nor resets
    assert dormancy.step(s, review(pp=0.01), 0.01).dormant
    assert not walk([(review(pp=0.01, t_end_set=False), 0.001)] * 4).dormant      # no programme end, no dormancy
    dormant = walk([(review(pp=0.01), 0.01)] * 2)
    assert dormancy.step(dormant, review(pp=None), 0.01).dormant
    assert not dormancy.step(dormant, review(pp=None), 0.30).dormant              # its own record wakes it at the last date
    assert not dormancy.step(tiers.State(), review(pp=0.0), None).dormant         # no p-value is read as no evidence


def test_while_dormant_only_the_reactivation_check_and_formal_support():
    dormant = walk([(review(pp=0.01), 0.01)] * 2)
    s = dormancy.step(dormant, review(pp=0.01, pi=0.95), 0.01)
    assert s.dormant and not s.promising and not s.supported                      # no tier evaluation
    s = dormancy.step(dormant, review(pp=0.01, elond_rejected=True), 0.01)
    assert s.dormant and s.formal and s.events == ("formal",)
    woke = dormancy.step(dormant, review(pp=0.01, pi=0.95, days=600), 0.50)
    assert not woke.dormant and woke.promising and woke.events[0] == "reactivated"


def test_supported_families_and_uncomputed_reviews():
    supported = tiers.State(promising=True, supported=True, enrolled=True, low_pp=1)
    s = dormancy.step(supported, review(pp=0.0, pi=0.90), 0.0)
    assert s.supported and not s.dormant and s.low_pp == 0
    s = dormancy.step(tiers.State(low_pp=1), tiers.Review(pi_min=None, forward_days=900, forward_mean_positive=True, pp_max=0.0), 0.0)
    assert not s.dormant and s.low_pp == 1 and "model not converged: no tier change" in s.events


def test_the_tiers_are_those_of_tiers_step_and_with_a_record_always_against_it_the_rule_is_that_of_30():
    rng = np.random.default_rng(31)
    keep = ("promising", "supported", "formal", "decayed_since", "enrolled", "low_promising", "low_supported")
    for _ in range(200):
        a = b = c = d = tiers.State()
        for k in range(12):
            r = tiers.Review(pi_min=float(rng.choice([0.05, 0.15, 0.3, 0.5, 0.7, 0.9])), forward_days=126 * (k + 1),
                             forward_mean_positive=bool(rng.random() < 0.7), rw_reserve=bool(rng.random() < 0.3),
                             pp_max=float(rng.choice([0.0, 0.02, 0.1, 0.2])), elond_rejected=bool(rng.random() < 0.03))
            a = dormancy.step(a, r, 1.0)                           # the record never speaks against the family
            b = tiers.step(b, replace(r, pp_max=None))             # 3.0's tiers with no dormancy
            c = dormancy.step(c, r, 0.0)                           # the record always speaks against it
            d = tiers.step(d, r)                                   # the rule of 3.0
            assert not a.dormant and all(getattr(a, f) == getattr(b, f) for f in keep)
            assert c.dormant == d.dormant and c.low_pp == d.low_pp and all(getattr(c, f) == getattr(d, f) for f in keep)


def test_a_family_whose_edge_is_theta_min_is_rarely_put_aside_whatever_the_forecast_says():
    """The property the rule was revised for. Families with an edge of exactly θ_min (the least favourable case)
    and a forecast of zero at every review: the forward record is a random walk around the edge, read at years
    2, 4 and 7 (a forecast exists) and 10 (it does not), as in the simulation. Under the rule of 3.0 every one
    of them ends dormant; under 3.1 fewer than 5% do, and the families with no edge that do are several times
    as many."""
    rng = np.random.default_rng(2026)
    n, years = 20000, (2, 4, 7, 10)

    def ended_dormant(theta: float) -> float:
        inc = rng.standard_normal((n, 10)) + theta                 # one year's Sharpe-unit increments
        cum = inc.cumsum(axis=1)
        gone = 0
        for i in range(0, n, 1):
            s = tiers.State()
            for y in years:
                p = float(dormancy.forward_p(cum[i, y - 1] / y, 1.0 / math.sqrt(y), 252 * y))
                s = dormancy.step(s, review(pp=None if y == 10 else 0.0, days=252 * y), p)
            gone += s.dormant
        return gone / n

    at_edge, no_edge, strong = ended_dormant(0.25), ended_dormant(0.0), ended_dormant(0.75)
    assert at_edge < 0.05 and strong < 0.002
    assert no_edge > 2.5 * at_edge and no_edge > 0.03


# ------------------------------------------------------------------ the code list and the text

def test_the_revised_rule_is_part_of_the_hb_code_of_version_2_only():
    assert "manhattan/stats/dormancy.py" in run.CODE_FILES_V2_HB
    assert "manhattan/stats/dormancy.py" not in run.CODE_FILES_HB + run.CODE_FILES_V2      # version 1 and the SPA runs keep their hash
    assert "manhattan/stats/tiers.py" in run.CODE_FILES_HB                                  # 3.0's rule stays where it was


@reads_hand_edited_file
def test_protocol_31_states_the_revised_rule_and_its_reason():
    text = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    top = text[: text.index("## 1. Symbols")]
    for needle in ("Pre-adoption change (2026-11-13)", "0.167 (0.045 to 0.261)", "0.179 (0.138 to 0.216)", "0.108 (0.081 to 0.138)",
                   "0.146 (0.092 to 0.197)", "§9.1"):
        assert needle in top, needle
    rule = text[text.index("### 9.1 The rule"):text.index("### 9.2 The cost")]
    assert "| **Become dormant** | `PP_f^max < 0.05` **and** `p^F_f < 0.05`, both at two consecutive reviews |" in rule
    assert "| **Reactivate** | `PP_f^max ≥ 0.15` **or** `p^F_f ≥ 0.15` at any review, or on Ethan's recorded request |" in rule
    assert "p^F_f = Φ( (y^F_f − θ_min) / s^F_f )" in rule and "252 forward days" in rule
    assert "| dormancy thresholds | 0.05 (twice) / 0.15 | §9 |" in text            # the numbers of 3.0, unchanged
    assert "| dormancy: the family's own forward record |" in text
    log = text[text.index("### Change log"):text.index("## Appendix A.")]
    assert "pre-adoption change" in log and "§9.1" in log and "0.108 to 0.179" in log
    prereg = (ROOT / "docs/manhattan/SIM_PREREG_v2.md").read_text(encoding="utf-8")
    assert "**0.10**" in prereg and "PROTOCOL_v3.1.md §9.1" in prereg and "p^F" in prereg


# ------------------------------------------------------------------ the HB pipeline's paths and diagnostics

from types import SimpleNamespace          # noqa: E402

from manhattan.sim import hb_v2, metrics_v2, world          # noqa: E402


def fam(idx, true, freeze=0, passed=False):
    return SimpleNamespace(idx=idx, true=true, freeze=freeze, ev=SimpleNamespace(passed={"i": passed}))


def scripted(script: list) -> dict:
    """Step the three paths through reviews at years 2, 4, 7 and 10 (no forecast at year 10) for hand-made
    families: ``[(family, [(pi_min, pp_max, p_forward), ...]), ...]``. Returns the three tracks."""
    fams = [f for f, _ in script]
    steps_by_family = {f.idx: steps for f, steps in script}
    tracks = {rule: hb_v2.Track(rule, "i", fams) for rule in hb_v2.RULES}
    for k, year in enumerate((2, 4, 7, 10)):
        for f in fams:
            pi, pp, p = steps_by_family[f.idx][k]
            rev = tiers.Review(pi_min=pi, forward_days=year * 252 - f.freeze, forward_mean_positive=True,
                               pp_max=None if year == 10 else pp)
            for tr in tracks.values():
                tr.review(f, year * 252, rev, p, last=year == 10)
    for tr in tracks.values():
        tr.close(world.T_END)
    return tracks


def test_the_three_paths_on_hand_made_families():
    a = fam(0, 0.60)            # an edge; the forecast is zero throughout, its own record is fine: the pilot's case
    b = fam(1, 0.00)            # no edge; forecast and own record both low from the start
    c = fam(2, 0.40)            # an edge; put aside at year 4 on a poor start, its record recovers by year 7
    d = fam(3, 0.90, passed=True)   # an edge that enters the tier at year 7 unless it is dormant by then
    tracks = scripted([(a, [(0.1, 0.0, 0.6)] * 4), (b, [(0.05, 0.0, 0.01)] * 4),
                       (c, [(0.1, 0.0, 0.02), (0.1, 0.0, 0.04), (0.1, 0.0, 0.30), (0.1, 0.0, 0.50)]),
                       (d, [(0.5, 0.0, 0.7), (0.6, 0.0, 0.8), (0.9, 0.0, 0.9), (0.9, 0.0, 0.9)])])
    fams = [a, b, c, d]
    new, old, none = (tracks[r].summary(fams, world.T_END, None if r == "none" else tracks["none"]) for r in ("v31", "v30", "none"))
    # the rule of 3.0 retires all four at year 4 and none comes back: three families with an edge are lost
    assert old["m8_num"] == 3 and old["m8_den"] == 3 and old["edge_ever_dormant"] == 3 and old["null_end_dormant"] == 1
    assert old["reviews_written"] == 8 and old["reviews_possible"] == 16          # written at years 2 and 4 only
    assert old["edge_entry_lost"] == 1 and old["edge_entry_without_dormancy"] == 1 and old["edge_supported_ever"] == 0
    # the rule of 3.1 puts aside the family with no edge, and c for three years (year 4 to year 7)
    assert new["m8_num"] == 0 and new["edge_ever_dormant"] == 1 and new["null_ever_dormant"] == 1 and new["null_end_dormant"] == 1
    assert new["edge_dormant_share"] == [round(3 * 252 / 2520, 4)] and new["edge_woken"] == 1 and new["edge_reactivations"] == 1
    assert new["edge_woken_end_dormant"] == 0 and new["edge_dormant_at_last"] == 0 and new["m8_num_no_last_wake"] == 0
    assert new["reviews_written"] == 14                                           # b misses years 7 and 10; c is woken at 7
    assert new["edge_entry_lost"] == 0 and new["edge_entry_delay_years"] == [0.0] and new["edge_entry_years"] == [7.0]
    # at the nine reviews with a forecast of a family that is neither dormant nor supported when the review starts:
    # both low for b and c at years 2 and 4; the forecast alone for a and d at years 2, 4 and 7
    assert new["gate"] == [4, 6, 0, 0]
    assert new["edge_families"] == [[0.6, 0, -1, -1], [0.4, 0, -1, -1], [0.9, 0, 7 * 252, 7 * 252]]
    # with no dormancy nothing is ever dormant and every review is written
    assert none["edge_ever_dormant"] == none["null_ever_dormant"] == 0 and none["reviews_written"] == 16
    assert "gate" not in old and "edge_entry_lost" not in none
    assert tracks["v31"].gone(c, world.T_END) is False and tracks["v30"].gone(c, world.T_END) is True

    # the rows of the report, and the table of tier entry
    rep = {"diag": {"i": {"v31": new, "v30": old, "none": none}}, "forecast_seconds": 1.5, "eval_years": [2, 4, 7, 10]}
    rows = {r.what: r for r in metrics_v2.dormancy_rows([rep, rep])}
    assert rows["rule of 3.0 (forecast alone), shadow: premature elimination (M8) on the same fits"].estimate == 1.0
    assert rows["rule of 3.1 (forecast and own forward record): share of families with a true edge ever made dormant"].estimate \
        == pytest.approx(1 / 3)
    assert rows["rule of 3.1 (forecast and own forward record): share of family-reviews with a write-up (attention spent; "
                "1 with no dormancy)"].estimate == pytest.approx(14 / 16)
    assert all(r.metric in ("diag", "cost") and r.threshold == "" and not r.required for r in rows.values())
    assert metrics_v2.dormancy_rows([{"reviews": {}}]) == []                      # records made before the diagnostics
    tab = {(t["sharpe_lo"], y): v for t in metrics_v2.tier_entry_table([rep, rep], (4, 7, 10)) for y, v in t["years"].items()}
    assert tab[(0.70, 4)] == {"share": 0.0, "lo": 0.0, "hi": 0.0, "n": 2, "entered": 0}
    assert tab[(0.70, 7)]["share"] == 1.0 and tab[(0.70, 10)]["entered"] == 2 and tab[(0.40, 10)]["share"] == 0.0
    assert tab[(1.40, 10)]["n"] == 0 and math.isnan(tab[(1.40, 10)]["share"])
    by_age = metrics_v2.tier_entry_table([rep], (7,), by="age", rule="none")
    assert by_age[2]["years"][7] == {"share": 1.0, "lo": 1.0, "hi": 1.0, "n": 1, "entered": 1}
