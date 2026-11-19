"""Continuous series for research comparison only: none of them is a tradable price.

A continuous futures series joins contract months into one line. However it is joined, its **level** is not a
price anyone could trade at:

* ``spliced`` (unadjusted): the held month's settlement each day. Its change across a roll includes the price
  difference between two different contracts, a jump nobody earned or lost.
* ``difference`` (back-adjusted by the roll gap): earlier history is shifted so that point changes equal the held
  contract's point changes. Levels drift away from any real price (they can turn negative), so percentage returns,
  notional and costs in basis points computed from them are wrong.
* ``ratio`` (back-adjusted by the price ratio): earlier history is scaled so that percentage changes equal the held
  contract's. Point changes, and so P&L per contract, are wrong; it needs positive prices.
* ``chained``: an index of chained same-contract returns (``docs/research/commodities_spec_2026-11.md`` §2.3,
  ``em_macro/commod_data.py``). The repository's convention for returns; a return index, not a price.

``AdjustedSeries`` is a different type from ``Settlement`` and has ``tradable = False``: ``MarketData`` and
``fill_order`` refuse it, so an adjusted level can never be used as a fill or a mark.

The hold schedule comes from the roll rule (``RollPolicy``), contract metadata only: the contract held over
``(D_{k−1}, D_k]`` is the one chosen at ``D_{k−1}``'s close, and a roll happens at the close of the roll day.

**Not point in time.** ``difference`` and ``ratio`` move every earlier value at each later roll, so a value read
from a series built today is not the value a researcher saw on that day. ``build(..., as_of=d)`` gives the series
as it could have been built after ``d``'s settlements; any signal that reads back-adjusted levels must use one
built as of its decision, never the full-window series. ``spliced`` and ``chained`` are not revised by later rolls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .contracts import RollPolicy
from .errors import MissingInputError, UnitError
from .market import MarketData

METHODS = ("spliced", "difference", "ratio", "chained")


@dataclass(frozen=True)
class AdjustedPoint:
    root: str
    day: date
    value: float
    method: str
    tradable: bool = field(default=False, init=False)


@dataclass(frozen=True)
class AdjustedSeries:
    root: str
    method: str
    days: tuple
    values: tuple
    held: tuple                     # contract held after each day's close
    tradable: bool = field(default=False, init=False)

    def point(self, i: int) -> AdjustedPoint:
        return AdjustedPoint(self.root, self.days[i], self.values[i], self.method)


def hold_schedule(market: MarketData, root: str, roll: RollPolicy, as_of: date | None = None) -> tuple:
    """((day, contract held after that day's close), ...) for an always-invested holder of ``root``, with the
    same exit rule as the accounting (``RollPolicy.must_exit``: roll window, delivery boundary, last trade)."""
    cal = [td.day for td in market.calendar if as_of is None or td.day <= as_of]
    out, held = [], None
    for i, d in enumerate(cal):
        nxt = market.calendar[i + 1].day if i + 1 < len(market.calendar) else d + timedelta(days=1)
        if held is None or roll.must_exit(market.specs[held], d, nxt):
            held = roll.select(market.specs, root, d).contract_id
        out.append((d, held))
    return tuple(out)


def _px(market: MarketData, cid: str, d: date) -> float:
    s = market.settlement(cid, d)
    if s is None:
        raise MissingInputError(f"no settlement for {cid} on {d}: a continuous series cannot be built across it")
    return s.price


def build(market: MarketData, root: str, roll: RollPolicy, method: str, as_of: date | None = None) -> AdjustedSeries:
    """The series over the calendar, or over the days up to ``as_of`` only: what a researcher could have built
    after ``as_of``'s settlements were published. A back-adjusted series built later rewrites these values."""
    if method not in METHODS:
        raise UnitError(f"method is one of {METHODS}, not {method!r}")
    sched = hold_schedule(market, root, roll, as_of)
    if not sched:
        raise MissingInputError(f"no trading day on or before {as_of}")
    days = tuple(d for d, _ in sched)
    held = tuple(c for _, c in sched)
    n = len(days)
    if method == "chained":
        vals = [1.0]
        for k in range(1, n):
            c = held[k - 1]
            a, b = _px(market, c, days[k - 1]), _px(market, c, days[k])
            if a <= 0:
                raise UnitError(f"{c} settles at {a} on {days[k - 1]}: a return index needs positive prices")
            vals.append(vals[-1] * b / a)
        return AdjustedSeries(root, method, days, tuple(vals), held)
    level = [_px(market, held[k], days[k]) for k in range(n)]
    if method == "spliced":
        return AdjustedSeries(root, method, days, tuple(level), held)
    # back-adjust: walk backwards through the rolls (a roll at the close of day k: held[k] != held[k-1])
    vals = list(level)
    for k in range(n - 1, 0, -1):
        if held[k] == held[k - 1]:
            continue
        old, new = _px(market, held[k - 1], days[k]), _px(market, held[k], days[k])
        if method == "difference":
            gap = new - old
            for j in range(k):
                vals[j] += gap
        else:
            if old <= 0 or new <= 0:
                raise UnitError(f"ratio adjustment needs positive prices at the {days[k]} roll")
            for j in range(k):
                vals[j] *= new / old
    return AdjustedSeries(root, method, days, tuple(vals), held)
