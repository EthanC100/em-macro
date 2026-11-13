"""Dormancy under Protocol v3.1 section 9.1, as revised before adoption (manhattan/stats/dormancy.py): criterion
C-24 of docs/manhattan/MANHATTAN_PROGRESS.md. Scripted sequences; no data.

The rule: dormant when, at two consecutive reviews with at least 252 forward days each, both the forecast
``PP^max`` and the probability of an edge ``Π^max`` are below 0.05; reactivated when either is at least 0.15.
The tiers are version 3.0's, stepped by ``tiers.step``, which is not edited.
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path

from manhattan.stats import dormancy, tiers
from manhattan.stats.tiers import Review, State
from manhattan.testing import reads_hand_edited_file

ROOT = Path(__file__).resolve().parents[1]


def R(pi_min=0.01, pp=0.0, days=600, pos=True, **kw):
    return Review(pi_min=pi_min, forward_days=days, forward_mean_positive=pos, pp_max=pp, **kw)


def run(state, reviews):
    """``reviews``: pairs (Review, Π^max)."""
    out = []
    for r, pi_max in reviews:
        state = dormancy.step(state, r, pi_max)
        out.append(state)
    return out


def test_no_number_is_new():
    """0.05 and 0.15 are the dormancy levels of 3.0; 252 forward days and two reviews are the Promising exit's."""
    assert dormancy.PP_BELOW == dormancy.PI_BELOW == tiers.DORMANT_BELOW == 0.05
    assert dormancy.REACTIVATE_AT == tiers.REACTIVATE_AT == 0.15
    assert dormancy.MIN_FORWARD_DAYS == tiers.DAYS_PROMISING_EXIT == 252 and dormancy.CONSECUTIVE == 2


def test_dormant_needs_both_numbers_low_at_two_consecutive_reviews():
    a, b = run(State(), [(R(pp=0.04), 0.04), (R(pp=0.04), 0.04)])
    assert not a.dormant and a.low_pp == 1 and b.dormant and "dormant" in b.events and b.low_pp == 0
    # the forecast alone, which was the whole rule of 3.0, is no longer enough: the pilot's retired families
    # had PP^max = 0 and a central probability of an edge near 0.6
    assert not any(s.dormant for s in run(State(), [(R(pp=0.0), 0.62)] * 6))
    assert not any(s.dormant for s in run(State(), [(R(pp=0.0), 0.05)] * 6))             # strictly below 0.05
    # nor is a low probability of an edge while the forecast still gives the family a chance
    assert not any(s.dormant for s in run(State(), [(R(pp=0.05), 0.01)] * 6))
    # one review that is not low breaks the count
    a, b, c, d = run(State(), [(R(pp=0.0), 0.01), (R(pp=0.0), 0.20), (R(pp=0.0), 0.01), (R(pp=0.0), 0.01)])
    assert (a.low_pp, b.low_pp, c.low_pp) == (1, 0, 1) and not c.dormant and d.dormant


def test_a_review_counts_only_with_252_forward_days():
    assert not any(s.dormant for s in run(State(), [(R(days=251), 0.01)] * 4))
    a, b, c = run(State(), [(R(days=200), 0.01), (R(days=252), 0.01), (R(days=315), 0.01)])
    assert not a.dormant and a.low_pp == 0 and not b.dormant and c.dormant
    # in particular a family is never retired on its history alone, however poor
    assert not any(s.dormant for s in run(State(), [(R(days=0), 0.0), (R(days=63), 0.0), (R(days=126), 0.0)]))


def test_reactivation_by_either_number_or_by_ethan():
    dormant = run(State(), [(R(), 0.01), (R(), 0.01)])[-1]
    assert dormant.dormant
    assert dormancy.step(dormant, R(pp=0.14), 0.14).dormant                                # below 0.15 on both: stays
    for r, pi_max in ((R(pp=0.15), 0.01), (R(pp=0.0), 0.15), (R(pp=0.0, ethan_reactivates=True), 0.01)):
        s = dormancy.step(dormant, r, pi_max)
        assert not s.dormant and "reactivated" in s.events and s.recording
    # hysteresis: between 0.05 and 0.15 nothing changes in either direction
    awake = State()
    assert not any(s.dormant for s in run(awake, [(R(pp=0.0), 0.10)] * 5))
    assert all(s.dormant for s in run(dormant, [(R(pp=0.0), 0.10)] * 5))
    # woken by Ethan with both numbers still low: one more low review does not retire it, two do
    a, b = run(dormant, [(R(ethan_reactivates=True), 0.01), (R(), 0.01)])
    assert not a.dormant and a.low_pp == 1 and b.dormant


def test_the_last_review_has_no_forecast_so_nobody_becomes_dormant_there_but_a_family_can_wake():
    a, b = run(State(), [(R(), 0.01), (R(pp=None), 0.01)])
    assert a.low_pp == 1 and not b.dormant and b.low_pp == 1                               # the count is left as it is
    dormant = run(State(), [(R(), 0.01), (R(), 0.01)])[-1]
    assert dormancy.step(dormant, R(pp=None), 0.01).dormant
    assert not dormancy.step(dormant, R(pp=None), 0.20).dormant


def test_never_dormant_without_a_programme_end_never_while_supported_and_not_when_the_model_was_not_computed():
    assert not any(s.dormant for s in run(State(), [(R(t_end_set=False), 0.0)] * 4))
    s = dormancy.step(tiers.at_freeze(True), R(pi_min=0.9, pp=0.0), 0.95)
    assert s.supported and not s.dormant and s.low_pp == 0
    a, b, c = run(State(), [(R(), 0.01), (R(pi_min=None), None), (R(), 0.01)])
    assert a.low_pp == 1 and b.low_pp == 1 and not b.dormant and "model not converged: no tier change" in b.events
    assert c.dormant                                                                        # the uncomputed review did not break the count
    dormant = c
    assert dormancy.step(dormant, R(pi_min=None, pp=None), None).dormant                    # and it wakes nobody


def test_while_dormant_only_the_reactivation_check_is_made():
    dormant = run(State(), [(R(), 0.01), (R(), 0.01)])[-1]
    s = dormancy.step(dormant, R(pi_min=0.45, pp=0.0, days=900), 0.10)                      # would enter Promising if evaluated
    assert s.dormant and not s.promising
    s = dormancy.step(dormant, R(pi_min=0.45, pp=0.0, days=900), 0.50)                      # woken: evaluated at the same review
    assert not s.dormant and s.promising and s.enrolled
    s = dormancy.step(dormant, R(elond_rejected=True), 0.01)                                # a formal rejection is still recorded
    assert s.dormant and s.formal
    assert dormancy.step(dormant, R(cheap=False, pp=0.0), 0.01).dormant                    # still dormant
    assert not run(State(), [(R(cheap=False), 0.01), (R(cheap=False), 0.01)])[-1].recording  # a costly family may stop recording


def test_the_tiers_are_version_30s_whatever_the_dormancy_numbers():
    """With the family awake, every tier field is what ``tiers.step`` gives without a forecast."""
    reviews = [R(pi_min=p, pp=pp, days=d, pos=pos) for p, pp, d, pos in
               itertools.product((0.1, 0.2, 0.45, 0.7, 0.85), (0.0, 0.3), (100, 300, 600), (True, False))]
    for start in (State(), tiers.at_freeze(True)):
        s30, s31 = start, start
        for r in reviews:
            s30 = tiers.step(s30, replace(r, pp_max=None))
            s31 = dormancy.step(s31, r, 0.5)                                               # Π^max = 0.5: never low, never dormant
            assert (s31.promising, s31.supported, s31.formal, s31.enrolled, s31.low_promising, s31.low_supported) == \
                (s30.promising, s30.supported, s30.formal, s30.enrolled, s30.low_promising, s30.low_supported)
            assert not s31.dormant


def test_the_revised_rule_never_retires_a_family_the_30_rule_keeps():
    """It adds conditions and removes none: on any sequence, dormant under 3.1 implies dormant under 3.0 at the
    same review or earlier (while the family is awake under both, the 3.1 count never runs ahead)."""
    import random
    rng = random.Random(7)
    for _ in range(300):
        s30 = s31 = State()
        for _ in range(8):
            pp, pi_max = rng.choice((0.0, 0.03, 0.07, 0.2)), rng.choice((0.01, 0.04, 0.1, 0.3))
            r = R(pi_min=min(0.02, pi_max), pp=pp, days=rng.choice((100, 300, 700)))
            was30, was31 = s30.dormant, s31.dormant
            s30, s31 = tiers.step(s30, r), dormancy.step(s31, r, pi_max)
            if s31.dormant and not was31:
                assert s30.dormant, "3.1 retired a family that 3.0 keeps"


@reads_hand_edited_file
def test_the_protocol_states_the_rule_the_code_applies():
    text = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    sec = text[text.index("### 9.1 The rule"):text.index("### 9.2 The cost")]
    assert "| **Become dormant** | `PP_f^max < 0.05` **and** `Π_f^max < 0.05`, at two consecutive reviews, each with at least 252 forward days |" in sec
    assert "| **Reactivate** | `PP_f^max ≥ 0.15` **or** `Π_f^max ≥ 0.15` at any review, or on Ethan's recorded request |" in sec
    assert "With `programme.end` unset (the default), `T_end` is undefined and no family becomes dormant." in sec
    top = text[: text.index("## 1. Symbols")]
    for needle in ("| 5 | §9.1", "0.167 (0.045 to 0.261)", "0.179 (0.138 to 0.216)", "0.108 (0.081 to 0.138)",
                   "0.146 (0.092 to 0.197)", "pre-adoption"):
        assert needle in top, needle
    assert "| dormancy thresholds | 0.05 (twice) / 0.15 | §9 |" in text                    # 3.0's row, unchanged
    assert "| dormancy: what the thresholds apply to |" in text
