"""Dormancy under Protocol v3.1 section 9.1 (``manhattan/stats/dormancy.py``): the forecast of 3.0 **and** a
one-sided test of the family's own forward record against an edge of 0.25. Criterion C-24 of
docs/manhattan/MANHATTAN_PROGRESS.md. Synthetic inputs only.

The module and these eleven tests of the rule were written on branch ``claude/epic-mayer-kfhpsh`` (commit
``1124fe7``) and brought here when Ethan chose this rule (ETHAN_ACTIONS item 22); the test of the protocol's
text reads the text as it stands on this branch. That branch's shadow paths in the HB pipeline (the same fits
stepped under three rules) were not brought over: ``results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`` already
holds that comparison.

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
    assert dormancy.RULE == "protocol-3.1-section-9.1-forward-record"                       # the id every HB record carries
    assert "dormancy.RULE" in (ROOT / "manhattan/sim/hb_v2.py").read_text(encoding="utf-8")


@reads_hand_edited_file
def test_protocol_31_states_the_revised_rule_and_its_reason():
    text = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    top = text[: text.index("## 1. Symbols")]
    for needle in ("Pre-adoption change (Ethan's decision of 2026-11-13)", "0.167 (0.045 to 0.261)", "0.179 (0.138 to 0.216)",
                   "0.108 (0.081 to 0.138)", "0.146 (0.092 to 0.197)", "| 5 | §9.1", "ETHAN_ACTIONS item 22",
                   "against an edge of `θ_min = 0.25`", "**What it replaces:**", "DORMANCY_SECOND_LOOK.md"):
        assert needle in top, needle
    rule = text[text.index("### 9.1 The rule"):text.index("### 9.2 The cost")]
    assert "| **Become dormant** | `PP_f^max < 0.05` **and** `p^F_f < 0.05`, both at two consecutive reviews |" in rule
    assert "| **Reactivate** | `PP_f^max ≥ 0.15` **or** `p^F_f ≥ 0.15` at any review, or on Ethan's recorded request |" in rule
    assert "p^F_f = Φ( (y^F_f − θ_min) / s^F_f )" in rule and "252 forward days" in rule
    assert "a one-sided test of the record against an edge of 0.25" in rule
    assert "Π_f^max" not in rule.split("> **Why not the model's own probability of an edge.**")[0]      # it is no part of the rule
    assert "| dormancy thresholds | 0.05 (twice) / 0.15 | §9 |" in text            # the numbers of 3.0, unchanged
    assert "| dormancy: the family's own forward record |" in text and "| dormancy: what the thresholds apply to |" not in text
    assert "dormancy uses\nthe forecast of the most hopeful model, `PP_f^max`, and the family's own forward record**" in text
    log = text[text.index("### Change log"):text.index("## Appendix A.")]
    assert "| 3.1.0, pre-adoption change | 2026-11-13 |" in log and "§9.1" in log and "superseded by the next row" in log
    prereg = (ROOT / "docs/manhattan/SIM_PREREG_v2.md").read_text(encoding="utf-8")
    assert "**0.10**" in prereg and "PROTOCOL_v3.1.md §9.1" in prereg and "p^F" in prereg
    assert "a family becomes dormant when `PP^max < 0.05` and `p^F < 0.05` at two\n  consecutive dates" in prereg
