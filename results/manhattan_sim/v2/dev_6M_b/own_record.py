"""An alternative dormancy rule that is NOT adopted: the forecast and the family's own forward record.

Written by session "6M Manhattan C: dormancy fix and statistical checks" before it found that another session had
already revised Protocol 3.1 section 9.1 on build/manhattan (the forecast and ``Π^max``, ``manhattan/stats/dormancy.py``).
It is kept here, outside the package, so that the two rules can be compared on the same fits (``paths.py``). Nothing
in the pipeline imports it.

    p^F_f = Φ( (y^F_f − θ_min) / s^F_f )      one-sided p-value of the forward record against "the edge is at
                                               least θ_min"; defined with at least 252 forward days, else 1

    become dormant   PP^max < 0.05  and  p^F < 0.05,  both at two consecutive reviews
    reactivate       PP^max ≥ 0.15  or  p^F ≥ 0.15  at any review,  or on Ethan's recorded request

``p^F`` uses nothing but the family's own forward returns: no prior, no other family, no history. If the family's
edge is exactly ``θ_min`` it is below 0.05 at a given review with probability 0.05, and with a larger edge less
often, whatever the other families are. It is also the posterior probability of ``θ_f ≥ θ_min`` under a flat
prior on the family's own forward record. The tiers are ``tiers.step``, called with its own dormancy switched off.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy.special import ndtr

from manhattan.stats import tiers

DORMANT_BELOW, REACTIVATE_AT = tiers.DORMANT_BELOW, tiers.REACTIVATE_AT       # 0.05 and 0.15: the numbers of 3.0
MIN_FORWARD_DAYS = tiers.DAYS_PROMISING_EXIT                                  # 252, as for leaving Promising (8.1)
THETA_MIN = tiers.THETA_MIN
CONSECUTIVE = 2


def forward_p(y_F, s_F, forward_days) -> np.ndarray:
    """``p^F_f`` for every family: 1 where there is no forward estimate yet (NaN), no positive standard error
    or fewer than 252 forward days."""
    y, s, d = (np.asarray(x, dtype=float) for x in (y_F, s_F, forward_days))
    ok = np.isfinite(y) & np.isfinite(s) & (s > 0) & (d >= MIN_FORWARD_DAYS)
    z = (np.where(ok, y, 0.0) - THETA_MIN) / np.where(ok, s, 1.0)
    return np.where(ok, ndtr(z), 1.0)


def step(s: tiers.State, r: tiers.Review, p_forward: float | None) -> tiers.State:
    """Apply one review under Protocol 3.1. ``r.pp_max`` is the forecast (None when there is none);
    ``p_forward`` is ``p^F_f`` (None is read as 1: no forward evidence against the family)."""
    p = 1.0 if p_forward is None else float(p_forward)
    ev: list[str] = []
    if s.dormant:
        if r.ethan_reactivates or (r.pp_max is not None and r.pp_max >= REACTIVATE_AT) or p >= REACTIVATE_AT:
            s = replace(s, dormant=False, low_pp=0, recording=True)
            ev.append("reactivated")
        else:                                           # still dormant: only formal support is recorded
            return tiers.step(s, replace(r, pp_max=None, ethan_reactivates=False))
    low_before = s.low_pp
    s = tiers.step(s, replace(r, pp_max=None, ethan_reactivates=False))       # the tiers; no dormancy of 3.0
    ev += list(s.events)
    if r.pi_min is None:                                # "model not computed": no tier change, no new dormancy
        return replace(s, low_pp=low_before, events=tuple(ev))
    if not s.supported and r.t_end_set and r.pp_max is not None:
        low = low_before + 1 if (r.pp_max < DORMANT_BELOW and p < DORMANT_BELOW) else 0
        if low >= CONSECUTIVE:
            s = replace(s, dormant=True, low_pp=0, recording=r.cheap)
            ev.append("dormant")
        else:
            s = replace(s, low_pp=low)
    elif s.supported:
        s = replace(s, low_pp=0)
    else:                                               # no forecast at this review: the streak neither grows nor resets
        s = replace(s, low_pp=low_before)
    return replace(s, events=tuple(ev))
