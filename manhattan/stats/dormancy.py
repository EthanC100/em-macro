"""Dormancy under Protocol v3.1 section 9.1, as revised before adoption.

Version 3.0's rule (``tiers.step``) made a family dormant on one number, ``PP^max``: the largest, over the six
models, of the probability that the family enters Statistically supported before the programme ends. That tier
needs ``Π^min ≥ 0.80``, the most cautious of the six, so the forecast is small for most families that have an
edge: on the pilot rerun the rule retired families the central model gave a 60% chance of an edge, with a
positive forward record, because none of them could reach that tier in time
(``results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md``).

The revised rule keeps that condition and adds the one section 7.2(e) always named ("dormancy uses ``Π^max``"):

    become dormant   at two consecutive reviews, each with at least 252 forward days:
                     PP^max < 0.05   and   Π^max < 0.05
    reactivate       PP^max ≥ 0.15   or   Π^max ≥ 0.15   at any review, or on Ethan's recorded request

``Π^max`` is the largest of the six models' posterior probabilities that the family's edge is at least
``θ_min``. A family is therefore retired only when even the most hopeful model says it very probably has no
edge worth having, on a forward record of its own. No number is new: 0.05 and 0.15 are the dormancy levels of
3.0, and 252 forward days and "two consecutive reviews" are those of the Promising exit (section 8.1), of which
this rule is the stricter sibling (the most hopeful model instead of the most cautious, 0.05 instead of 0.20).

The tiers themselves are version 3.0's and are stepped by ``tiers.step``, which this module calls with no
forecast so that its own dormancy branch is never reached. ``manhattan/stats/tiers.py`` is not edited: it is a
code file of version 1's records.
"""
from __future__ import annotations

from dataclasses import replace

from . import tiers

PP_BELOW = tiers.DORMANT_BELOW                  # 0.05: the forecast of reaching Statistically supported
PI_BELOW = tiers.DORMANT_BELOW                  # 0.05: the probability of an edge of at least θ_min
REACTIVATE_AT = tiers.REACTIVATE_AT             # 0.15: for either of the two
MIN_FORWARD_DAYS = tiers.DAYS_PROMISING_EXIT    # 252: the forward record a family needs before a review can count
CONSECUTIVE = 2
RULE = "protocol-3.1-section-9.1-revised"          # written into every replication record


def low(r: tiers.Review, pi_max: float | None) -> bool | None:
    """Whether this review counts towards dormancy. ``None``: the review cannot say (the programme has no end,
    no forecast could be made, or the model was not computed), and the count of low reviews is left as it is."""
    if not r.t_end_set or r.pp_max is None or pi_max is None or r.pi_min is None:
        return None
    return bool(r.pp_max < PP_BELOW and pi_max < PI_BELOW and r.forward_days >= MIN_FORWARD_DAYS)


def wakes(r: tiers.Review, pi_max: float | None) -> bool:
    """Whether a dormant family is reactivated at this review."""
    return bool(r.ethan_reactivates or (r.pp_max is not None and r.pp_max >= REACTIVATE_AT)
                or (pi_max is not None and r.pi_min is not None and pi_max >= REACTIVATE_AT))


def step(s: tiers.State, r: tiers.Review, pi_max: float | None) -> tiers.State:
    """Apply one review: the tiers of sections 8.1, 8.2 and 8.5 by ``tiers.step``, dormancy by section 9.1 of
    Protocol v3.1. ``pi_max`` is ``Π^max`` (``None`` when the model was not computed).

    While dormant only the reactivation check is made. A review at which the model was not computed changes no
    tier, no count and no dormancy, except that Ethan's request and an e-LOND rejection are still recorded.
    """
    ev: list[str] = []
    if s.dormant and wakes(r, pi_max):
        s = replace(s, dormant=False, low_pp=0, recording=True)
        ev.append("reactivated")
    streak = s.low_pp
    s = tiers.step(s, replace(r, pp_max=None, ethan_reactivates=False))       # tiers only; no forecast is passed
    ev += list(s.events)
    if s.dormant:
        return replace(s, events=tuple(ev))
    if s.supported:
        return replace(s, low_pp=0, events=tuple(ev))
    verdict = low(r, pi_max)
    if verdict is None:
        return replace(s, low_pp=streak, events=tuple(ev))
    streak = streak + 1 if verdict else 0
    if streak >= CONSECUTIVE:
        ev.append("dormant")
        return replace(s, dormant=True, low_pp=0, recording=r.cheap, events=tuple(ev))
    return replace(s, low_pp=streak, events=tuple(ev))
