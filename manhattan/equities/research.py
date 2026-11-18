"""Authorized research entry points: the only functions of this package that read dated data (S8 H4).

The rest of the package is two kinds of code:

* **numerical primitives** (``pairs``, ``analogues``, ``features``, ``risk``, ``macro.sensitivity`` ...): pure
  functions of arrays and records the caller supplies. They hold no data and authorize nothing; whatever they are
  given is the caller's responsibility. Tests call them directly on synthetic arrays.
* **data contracts and point-in-time stores** (``prices``, ``fundamentals``, ``estimates``, ``universe`` ...):
  bitemporal records with their own as-of rules, exported to Manhattan's ``PitStore`` by ``pit_bridge``.

An entry point here (1) checks the research gate (``evidence.require_research_scope``: synthetic sources only until
Ethan approves equity research), (2) opens its window through ``manhattan.engine.pit.Reader`` — never by constructing
a ``Window`` — so ``manhattan.roles.check_read`` decides the role (exploration only: no attempt is registered here,
and after PR #86 a reserve or forward read without an ``AttemptContext`` raises), and (3) reads through that window
as of the information boundary, so later data never reach the primitive.

    w = open_window(store, domain="us_tech_equities_synthetic", start=..., end=..., fence=fence, contracts=reg)
    disc = discover_pairs(w, ["S01", "S02"], boundary, rules, calendar=cal, link=...)   # as of formation end
    report = evaluate_pair(w, candidate, rules, calendar=cal)                           # retrospective

Nothing here registers an attempt, writes a ledger record or produces evidence: outputs carry evidential weight 0.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from manhattan import roles
from manhattan.engine.pit import Reader

from . import pairs
from .errors import EquityDataError
from .evidence import require_research_scope

CALLER = "session"


def open_window(store, *, domain: str, start: date, end: date, fence: roles.Fence, contracts):
    """An exploration window opened by a ``Reader`` after the research gate. Reserve or forward dates raise
    ``roles.RoleError`` (``check_read``); no window is ever constructed directly."""
    require_research_scope(contracts)
    return Reader(store, caller=CALLER, domain=domain, fence=fence).window(start, end)


def _panel(window, securities, as_of: date, days):
    """Log total-return indices of ``securities`` as known at ``as_of``, on the session grid ``days`` (NaN where a
    security has no value known at ``as_of``)."""
    arr = {}
    for s in securities:
        p, v = window.as_of(f"eq.px.{s}", as_of)
        known = dict(zip(p.astype("datetime64[D]").astype(object), np.log(v)))
        arr[s] = np.array([known.get(d, np.nan) for d in days], float)
    if not any(np.isfinite(a).any() for a in arr.values()):
        raise EquityDataError(f"no prices known at {as_of}")
    return arr


def discover_pairs(window, securities, boundary: pairs.Boundary, rules: pairs.PairRules = pairs.PairRules(), *,
                   calendar, link=None) -> pairs.PairDiscovery:
    """Pair discovery on data read through ``window`` as known at the formation end; returns the discovery object
    after running it (``result`` holds every evaluated pair, ``attempts`` counts every pair looked at). The session
    grid comes from ``calendar`` (an exchange calendar is published in advance: it is not data from the future)."""
    days = np.array(calendar.sessions_between(boundary.formation_start, boundary.evaluation_start), dtype=object)
    arr = _panel(window, securities, boundary.formation_end, days)
    disc = pairs.PairDiscovery(days, arr, boundary, rules, calendar=calendar, link=link)
    disc.result = disc.candidates(include_failed=True)
    return disc


def evaluate_pair(window, candidate: pairs.PairCandidate, rules: pairs.PairRules = pairs.PairRules(), *, calendar,
                  events=()):
    """The retrospective break diagnostic, reading the window as known at the evaluation end (never earlier)."""
    bd = candidate.boundary
    if window.end < bd.evaluation_end:
        raise EquityDataError("the window ends before the evaluation window: a retrospective diagnostic needs it all")
    days = np.array(calendar.sessions_between(bd.formation_end, bd.evaluation_end), dtype=object)
    arr = _panel(window, [candidate.y, candidate.x], bd.evaluation_end, days)
    return pairs.out_of_sample(candidate, days, arr, rules, calendar=calendar, events=events)
