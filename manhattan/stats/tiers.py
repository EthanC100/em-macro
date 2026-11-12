"""Tiers and dormancy (Protocol v3 sections 8.1, 8.2, 8.5 and 9), as a state machine stepped once per review.

Only the tiers the simulation tests are here: Promising, Statistically supported, Formally supported, and the
dormant flag. The live tiers (8.3, 8.4) need measured costs and Ethan's approval and are not built.

    Promising      enter  (a) passed screening at the designated evaluation, or
                          (b) at a review: Π^min ≥ 0.40, at least 126 forward days, coverage ≥ 90%
                   exit   Π^min ≤ 0.20 at two consecutive reviews, with at least 252 forward days
    Supported      enter  Promising; Π^min ≥ 0.80; forward mean of P_f positive; at least 252 forward days when
                          Romano-Wolf named a variant on the reserve at a_f, otherwise 504; no integrity flag
                   exit   Π^min < 0.60 at two consecutive reviews; at once if Π^min < 0.40 or on an integrity flag
    Formally       enter  an e-LOND rejection; never left ("decayed since" is set when the family leaves Promising)
    Dormant        become PP^max < 0.05 at two consecutive reviews (families below Supported, T_end set)
                   wake   PP^max ≥ 0.15 at any review, or on Ethan's recorded request

A review at which the model did not converge (``pi_min is None``) changes no tier and no streak. While dormant
only the reactivation check is made. ``Π`` and ``PP`` are posterior probabilities under a stated model, never
error rates.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from scipy.stats import norm

PROMISING_ENTER, PROMISING_EXIT = 0.40, 0.20
SUPPORTED_ENTER, SUPPORTED_EXIT, SUPPORTED_EXIT_NOW = 0.80, 0.60, 0.40
DAYS_PROMISING, DAYS_PROMISING_EXIT, DAYS_SUPPORTED_RW, DAYS_SUPPORTED = 126, 252, 252, 504
COVERAGE_MIN = 0.90
DORMANT_BELOW, REACTIVATE_AT = 0.05, 0.15
THETA_MIN = 0.25


@dataclass(frozen=True)
class State:
    promising: bool = False
    supported: bool = False
    formal: bool = False
    decayed_since: bool = False
    dormant: bool = False
    enrolled: bool = False              # in the forward test (once, at the first review as Promising or higher)
    low_promising: int = 0              # consecutive reviews with Π^min ≤ 0.20 (and ≥ 252 forward days)
    low_supported: int = 0              # consecutive reviews with Π^min < 0.60
    low_pp: int = 0                     # consecutive reviews with PP^max < 0.05
    recording: bool = True              # forward recording goes on (always, for a cheap family)
    events: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class Review:
    pi_min: float | None                # None: "model not converged", no tier changes
    forward_days: int
    forward_mean_positive: bool
    rw_reserve: bool = False            # Romano-Wolf named at least one variant on the reserve at a_f
    coverage: float = 1.0
    integrity_flag: bool = False
    pp_max: float | None = None         # None when T_end is unset or the forecast could not be made
    t_end_set: bool = True
    cheap: bool = True
    ethan_reactivates: bool = False
    elond_rejected: bool = False        # an e-LOND rejection on record by this review


def at_freeze(passed_screening: bool) -> State:
    """Route (a): a blind family that passed screening is Promising from its designated evaluation."""
    return State(promising=passed_screening, events=("promising:screening",) if passed_screening else ())


def step(s: State, r: Review) -> State:
    """Apply one review."""
    ev = []
    if r.elond_rejected and not s.formal:
        s = replace(s, formal=True)
        ev.append("formal")
    if s.dormant:
        if r.ethan_reactivates or (r.pp_max is not None and r.pp_max >= REACTIVATE_AT):
            s = replace(s, dormant=False, low_pp=0, recording=True)
            ev.append("reactivated")
        else:
            return replace(s, events=tuple(ev))
    if r.pi_min is None:
        return replace(s, events=tuple(ev + ["model not converged: no tier change"]))
    pi = r.pi_min
    # Statistically supported: exits first, then entry
    if s.supported:
        low = s.low_supported + 1 if pi < SUPPORTED_EXIT else 0
        if pi < SUPPORTED_EXIT_NOW or r.integrity_flag or low >= 2:
            s = replace(s, supported=False, low_supported=0)
            ev.append("left supported")
        else:
            s = replace(s, low_supported=low)
    # Promising: exit, then entry by route (b)
    if s.promising:
        low = s.low_promising + 1 if (pi <= PROMISING_EXIT and r.forward_days >= DAYS_PROMISING_EXIT) else 0
        if low >= 2 and not s.supported:
            s = replace(s, promising=False, low_promising=0, decayed_since=s.formal)
            ev.append("left promising")
        else:
            s = replace(s, low_promising=low)
    elif pi >= PROMISING_ENTER and r.forward_days >= DAYS_PROMISING and r.coverage >= COVERAGE_MIN:
        s = replace(s, promising=True, low_promising=0)
        ev.append("promising:posterior")
    if s.promising and not s.enrolled:
        s = replace(s, enrolled=True)
        ev.append("enrolled")
    if (s.promising and not s.supported and pi >= SUPPORTED_ENTER and r.forward_mean_positive
            and not r.integrity_flag
            and r.forward_days >= (DAYS_SUPPORTED_RW if r.rw_reserve else DAYS_SUPPORTED)):
        s = replace(s, supported=True, low_supported=0)
        ev.append("supported")
    # dormancy: families below Statistically supported, only when the programme has an end
    if not s.supported and r.t_end_set and r.pp_max is not None:
        low = s.low_pp + 1 if r.pp_max < DORMANT_BELOW else 0
        if low >= 2:
            s = replace(s, dormant=True, low_pp=0, recording=r.cheap)
            ev.append("dormant")
        else:
            s = replace(s, low_pp=low)
    elif s.supported:
        s = replace(s, low_pp=0)
    return replace(s, events=tuple(ev))


def support_probability(draws: np.ndarray, post_mean: np.ndarray, post_sd: np.ndarray, *, fwd_years: np.ndarray,
                        fwd_sum: np.ndarray, promising: np.ndarray, rw_reserve: np.ndarray, review_gaps,
                        rng: np.random.Generator, decay_model: int | None = None, half_life: float = 3.0,
                        unit_sd: np.ndarray | float = 1.0) -> np.ndarray:
    """``PP_f`` under each model (section 9.1): the probability that a family enters Statistically supported at
    some later review, from simulated future forward records.

    ``draws[k, s, f]`` are posterior draws of ``θ_f`` under model ``k``; ``post_mean[k, f]`` and ``post_sd[k, f]``
    summarise the same posteriors. ``review_gaps`` are the years between the coming reviews, up to ``T_end``.
    ``fwd_years[f]`` and ``fwd_sum[f]`` are the forward record so far (years, and the sum of annualised Sharpe
    units, so that ``fwd_sum / fwd_years`` is the forward Sharpe estimate).

    **Approximation, declared:** the model is not refitted on each simulated future. Each model's future
    posterior of ``θ_f`` is its current one, treated as normal, updated by the simulated future record as a normal
    observation with variance ``unit_sd² / years``; ``Π^min`` is the minimum over the six. A family that is not
    Promising now is taken to become so when ``Π^min ≥ 0.40`` with 126 forward days; later exits are ignored.
    Returns ``PP[k, f]``.
    """
    K, S, F = draws.shape
    gaps = np.asarray(review_gaps, dtype=float)
    out = np.zeros((K, F))
    if gaps.size == 0:
        return out
    t_end = np.cumsum(gaps)
    t_start = t_end - gaps
    prec0 = 1.0 / np.maximum(post_sd, 1e-6) ** 2                     # (K, F)
    unit = np.broadcast_to(np.asarray(unit_sd, dtype=float), (F,))
    for k in range(K):
        theta = draws[k]                                             # (S, F)
        entered = np.zeros((S, F), dtype=bool)
        prom = np.broadcast_to(promising, (S, F)).copy()
        csum = np.zeros((S, F))
        for j, gap in enumerate(gaps):
            if decay_model is not None and k == decay_model:
                c = np.log(2.0) / half_life
                mean = theta * (np.exp(-c * t_start[j]) - np.exp(-c * t_end[j])) / c
            else:
                mean = theta * gap
            csum += mean + np.sqrt(gap) * unit * rng.standard_normal((S, F))
            years = t_end[j]
            prec = prec0[:, None, :] + years / unit**2               # (K, 1, F)
            m = (post_mean[:, None, :] * prec0[:, None, :] + csum[None, :, :] / unit**2) / prec
            pi_min = norm.sf((THETA_MIN - m) * np.sqrt(prec)).min(axis=0)             # (S, F)
            days = (fwd_years + years) * 252.0
            prom |= (pi_min >= PROMISING_ENTER) & (days >= DAYS_PROMISING)
            ok_days = days >= np.where(rw_reserve, DAYS_SUPPORTED_RW, DAYS_SUPPORTED)
            entered |= prom & (pi_min >= SUPPORTED_ENTER) & ((fwd_sum + csum) > 0) & ok_days
        out[k] = entered.mean(axis=0)
    return out
