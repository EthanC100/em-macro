"""Continuous futures series **as of a date** (DESIGN.md section 2.4).

A back-adjusted continuous series changes its whole history at every roll, so a series computed once over the full
sample and then read "as of" an earlier date leaks every later roll gap into the past. Here a continuous series is
always computed for one decision day ``t``, from a ``manhattan.engine.pit.Window`` (so the fence has already
decided what may be read) and from values known at ``t`` only:

* **Roll schedule** from contract reference data alone (last trade and first notice dates are scheduled in
  advance): on session ``d`` hold the earliest contract whose notice date is more than ``roll_sessions`` weekdays
  after ``d``.
* **Prices** of each contract as known at the close of ``t`` (``Window.as_of``): a revision published after ``t``
  is not used, nor is any session after ``t``.
* **Adjustment events** (multiplier, tick, price-unit changes, redenominations) are applied only when announced at
  or before the decision time of ``t``.
* **Methods**: ``none`` (stitched raw prices, gaps left in), ``difference`` (Panama: earlier prices shifted by the
  roll-day gap) and ``ratio`` (earlier prices scaled by the roll-day ratio). A roll whose two prices are not both
  known on the last day of the old contract stops the build with an error: a missing price is never filled.
"""
from __future__ import annotations

from datetime import date, datetime

import numpy as np

from .errors import MarketDataError
from .schema import AdjustmentEvent, Contract, session_dates
from .vintages import series_name

METHODS = ("none", "difference", "ratio")


def _sub_weekdays(d: date, n: int) -> date:
    return np.busday_offset(np.datetime64(d), -n, roll="backward").astype(object)


def front_contract(contracts, d: date, roll_sessions: int) -> Contract:
    live = [c for c in contracts if _sub_weekdays(c.notice, roll_sessions) > d]
    if not live:
        raise MarketDataError(f"no contract is held on {d}")
    return min(live, key=lambda c: (c.notice, c.contract_id))


def roll_schedule(contracts, start: date, end: date, roll_sessions: int = 5) -> list:
    """[(session, contract_id)] for weekdays from ``start`` to ``end``."""
    return [(d, front_contract(contracts, d, roll_sessions).contract_id) for d in session_dates(start, end)]


def build(window, source_id: str, instrument_id: str, contracts, t: date, *, method: str = "difference",
          field: str = "settle", roll_sessions: int = 5, adjustments=(), decision_time: datetime | None = None):
    """(sessions, values, held contract ids) of the continuous series as known at day ``t``."""
    if method not in METHODS:
        raise MarketDataError(f"method must be one of {METHODS}")
    if decision_time is None:
        raise MarketDataError("decision_time (the decision moment of t) is required to judge adjustment events")
    events = sorted((e for e in adjustments if isinstance(e, AdjustmentEvent) and e.instrument_id == instrument_id
                     and e.kind != "roll" and e.announced_utc <= decision_time),    # unknown at t: never applied
                    key=lambda e: (e.effective_date, e.kind))

    def adjusted(d, v):
        for ev in events:
            if d < ev.effective_date:
                v = v * ev.factor + ev.offset
        return v

    known = {}
    for c in contracts:
        name = series_name(source_id, instrument_id, c.contract_id, field)
        if window.has(name):
            p, v = window.as_of(name, t)
            known[c.contract_id] = {pp.astype(object): adjusted(pp.astype(object), float(vv)) for pp, vv in zip(p, v)}
    days, vals, held = [], [], []
    for d, cid in roll_schedule(contracts, window.start, min(t, window.end), roll_sessions):
        v = known.get(cid, {}).get(d)
        if v is not None:
            days.append(d)
            vals.append(v)
            held.append(cid)
    vals = np.array(vals, dtype=float)
    if method != "none":
        for i in range(len(held) - 1, 0, -1):
            if held[i] == held[i - 1]:
                continue
            last_old = days[i - 1]
            old, new = known.get(held[i - 1], {}).get(last_old), known.get(held[i], {}).get(last_old)
            if old is None or new is None:
                raise MarketDataError(f"roll {held[i - 1]} -> {held[i]}: both prices are not known on {last_old}")
            if method == "difference":
                vals[:i] += new - old
            else:
                if old <= 0 or new <= 0:
                    raise MarketDataError("ratio adjustment needs positive prices on the roll day")
                vals[:i] *= new / old
    return days, vals, held
