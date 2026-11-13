"""Event backtester: one position per event, on the daily grid.

Protocol v3 section 1: an event strategy is on the daily grid with return 0 when it holds nothing.

An event is a value in a point-in-time series: its period is the event's date, its value the position it calls
for (sign and size, a fraction of capital), its availability the day it became known. ``event_signal`` turns
such series into a signal for ``manhattan.engine.backtest`` with daily decisions:

    an event is **entered** at the first decision at whose close it is known, and executed ``lag`` days later
    (``lag = 1``: the next available price after the event became known);
    it is **held** for ``hold`` days and then closed;
    events that overlap **add**;
    an event that becomes known late is entered late. It is never entered before it is known.

Days with no open event have no position and a return of exactly zero.
"""
from __future__ import annotations

import numpy as np

from .backtest import Instrument, Strategy, View


def event_signal(events: dict[str, str], hold: int):
    """A signal from ``events`` (instrument name -> event series) with positions held ``hold`` days."""
    if isinstance(hold, bool) or int(hold) != hold or hold < 1:
        raise ValueError("an event position is held a whole number of days, at least 1")

    def signal(view: View) -> dict:
        out = {}
        for name, series in events.items():
            _, values, available = view.known(series)
            # the decision at which each known event was first known: the first calendar day on or after its availability
            entered = np.searchsorted(view.calendar, available, "left")
            live = (entered <= view.index) & (view.index < entered + hold)
            out[name] = float(values[live].sum())
        return out

    return signal


def strategy(instruments: tuple, events: dict[str, str], hold: int, *, lag: int = 1, **kw) -> Strategy:
    """A daily event strategy: ``instruments`` (``backtest.Instrument``), their event series and the holding
    period."""
    names = {i.name for i in instruments}
    if set(events) - names:
        raise ValueError("an event series is given for an instrument the strategy does not hold")
    if not all(isinstance(i, Instrument) for i in instruments):
        raise TypeError("instruments are backtest.Instrument objects")
    return Strategy(instruments=tuple(instruments), signal=event_signal(events, hold), rebalance="D", lag=lag, **kw)
