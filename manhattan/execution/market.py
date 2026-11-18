"""Synthetic market inputs, each stamped with when it could have been known.

Everything here is supplied by the caller. The model reads no file, no network and no vendor: a test or a research
script builds these objects from synthetic numbers.

* ``TradingDay(day, close_at)``: one day of the trading calendar and the UTC time of its settlement.
* ``Settlement(contract_id, day, price, known_at)``: the **tradable** final settlement of one contract month on one
  day, published at ``known_at`` (no earlier than the day's close). Only settlements are used as reference prices
  for fills and marks; an adjusted continuous series (``manhattan.execution.adjust``) is a different type and is
  refused.
* ``Liquidity(contract_id, adv_contracts, daily_vol_points, known_at)``: the caller's estimate of average daily
  volume (contracts) and of the standard deviation of daily settlement changes (price points), as known at
  ``known_at``. Sizing and impact use the latest estimate known **at the decision**, never a later one.
* ``FxRate(base, quote, day, rate, known_at)``: ``rate`` units of ``quote`` per one unit of ``base`` (``EUR``,
  ``USD``, 1.08 means 1 EUR = 1.08 USD). Conversion uses a direct or an inverted pair of the same day, never a
  cross through a third currency and never another day's rate.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime

from . import units as U
from .contracts import ContractSpec, on_tick
from .errors import LookAheadError, MissingInputError, TimestampError, UnitError


@dataclass(frozen=True)
class TradingDay:
    day: date
    close_at: datetime

    def __post_init__(self):
        U.day(self.day)
        object.__setattr__(self, "close_at", U.utc(self.close_at, f"close_at of {self.day}"))


@dataclass(frozen=True)
class Settlement:
    contract_id: str
    day: date
    price: float
    known_at: datetime
    tradable: bool = field(default=True, init=False)

    def __post_init__(self):
        U.day(self.day)
        U.finite(self.price, f"settlement of {self.contract_id} on {self.day}")     # may be zero or negative
        object.__setattr__(self, "known_at", U.utc(self.known_at, f"known_at of {self.contract_id} {self.day}"))


@dataclass(frozen=True)
class Liquidity:
    contract_id: str
    adv_contracts: float            # average daily volume, contracts; 0 means nothing can be traded
    daily_vol_points: float         # standard deviation of daily settlement changes, in price points
    known_at: datetime

    def __post_init__(self):
        U.finite(self.adv_contracts, f"adv_contracts of {self.contract_id}", nonneg=True)
        U.finite(self.daily_vol_points, f"daily_vol_points of {self.contract_id}", nonneg=True)
        object.__setattr__(self, "known_at", U.utc(self.known_at, f"known_at of liquidity for {self.contract_id}"))


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    day: date
    rate: float                     # units of ``quote`` per one ``base``
    known_at: datetime

    def __post_init__(self):
        U.currency(self.base)
        U.currency(self.quote)
        if self.base == self.quote:
            raise UnitError(f"an FX rate needs two different currencies, not {self.base}/{self.quote}")
        U.day(self.day)
        U.finite(self.rate, f"{self.base}{self.quote} rate on {self.day}", positive=True)
        object.__setattr__(self, "known_at", U.utc(self.known_at, f"known_at of {self.base}{self.quote} {self.day}"))


class MarketData:
    """Validated, indexed inputs. Construction checks every cross-reference and timestamp; nothing is filled in."""

    def __init__(self, *, calendar, contracts, settlements=(), liquidity=(), fx=()):
        cal = tuple(calendar)
        for t in cal:
            if not isinstance(t, TradingDay):
                raise TypeError("the calendar is a sequence of TradingDay")
        if not cal:
            raise MissingInputError("the trading calendar is empty")
        for a, b in zip(cal, cal[1:]):
            if b.day <= a.day or b.close_at <= a.close_at:
                raise TimestampError(f"the calendar must strictly increase in day and close time ({a.day}, {b.day})")
        self.calendar = cal
        self.day_index = {t.day: i for i, t in enumerate(cal)}

        specs = {}
        for s in contracts:
            if not isinstance(s, ContractSpec):
                raise TypeError("contracts is a sequence of ContractSpec")
            if s.contract_id in specs:
                raise UnitError(f"contract {s.contract_id} is described twice")
            specs[s.contract_id] = s
        self.specs = specs

        px = {}
        for s in settlements:
            if not isinstance(s, Settlement) or not getattr(s, "tradable", False):
                raise TypeError(f"only tradable Settlement objects can be reference prices, not {type(s).__name__} "
                                "(an adjusted continuous series is not a tradable price)")
            spec = specs.get(s.contract_id)
            if spec is None:
                raise MissingInputError(f"a settlement names {s.contract_id!r}, which has no contract metadata")
            i = self.day_index.get(s.day)
            if i is None:
                raise TimestampError(f"settlement of {s.contract_id} on {s.day}: that day is not in the trading calendar")
            if s.known_at < cal[i].close_at:
                raise TimestampError(f"settlement of {s.contract_id} on {s.day} is stamped known at "
                                     f"{s.known_at.isoformat()}, before that day's close {cal[i].close_at.isoformat()}")
            if not spec.tradable_on(s.day):
                raise TimestampError(f"settlement of {s.contract_id} on {s.day} is outside its trading life "
                                     f"({spec.first_trade} to {spec.last_trade})")
            if not on_tick(s.price, spec.tick_size):
                raise UnitError(f"settlement {s.price} of {s.contract_id} on {s.day} is not a multiple of the tick "
                                f"{spec.tick_size}: wrong price unit?")
            key = (s.contract_id, s.day)
            if key in px:
                raise UnitError(f"two settlements for {s.contract_id} on {s.day}")
            px[key] = s
        self.settlements = px

        liq = {}
        for q in liquidity:
            if not isinstance(q, Liquidity):
                raise TypeError("liquidity is a sequence of Liquidity")
            if q.contract_id not in specs:
                raise MissingInputError(f"a liquidity estimate names {q.contract_id!r}, which has no contract metadata")
            liq.setdefault(q.contract_id, []).append(q)
        self.liquidity = {}
        for cid, rows in liq.items():
            rows.sort(key=lambda q: q.known_at)
            if any(a.known_at == b.known_at for a, b in zip(rows, rows[1:])):
                raise TimestampError(f"two liquidity estimates for {cid} share a known_at time")
            self.liquidity[cid] = (tuple(q.known_at for q in rows), tuple(rows))

        rates = {}
        for r in fx:
            if not isinstance(r, FxRate):
                raise TypeError("fx is a sequence of FxRate")
            if r.day not in self.day_index:
                raise TimestampError(f"{r.base}{r.quote} rate on {r.day}: that day is not in the trading calendar")
            key = (r.base, r.quote, r.day)
            if key in rates or (r.quote, r.base, r.day) in rates:
                raise UnitError(f"two rates for {r.base}/{r.quote} on {r.day}")
            rates[key] = r
        self.fx = rates

    # -------------------------------------------------------------- lookups
    def settlement(self, cid: str, d: date) -> Settlement | None:
        return self.settlements.get((cid, d))

    def liquidity_as_of(self, cid: str, t: datetime) -> Liquidity:
        """The latest liquidity estimate known at ``t``; refuses when there is none."""
        t = U.utc(t)
        times, rows = self.liquidity.get(cid, ((), ()))
        i = bisect_right(times, t)
        if i == 0:
            if rows:
                raise LookAheadError(f"the first liquidity estimate for {cid} is known at {rows[0].known_at.isoformat()}, "
                                     f"after the decision at {t.isoformat()}")
            raise MissingInputError(f"no liquidity estimate for {cid}")
        return rows[i - 1]

    def rate(self, frm: str, to: str, d: date) -> float:
        """Units of ``to`` per one unit of ``frm`` on day ``d``: the day's fix, for **valuation** of day ``d``'s
        amounts. Its publication time is not checked here (ex-post valuation); ``ExecutionPolicy``'s
        ``fx_valuation_cutoff`` checks it for contemporaneous valuation, and ``rate_as_of`` serves decisions."""
        U.currency(frm)
        U.currency(to)
        if frm == to:
            return 1.0
        r = self.fx.get((frm, to, d))
        if r is not None:
            return r.rate
        r = self.fx.get((to, frm, d))
        if r is not None:
            return 1.0 / r.rate
        raise MissingInputError(f"no {frm}/{to} rate on {d} (no cross rates and no other day's rate are used)")

    def rate_as_of(self, frm: str, to: str, t: datetime) -> tuple[float, date]:
        """For a **decision** at ``t``: the most recent ``frm``/``to`` rate already published at ``t`` (direct or
        inverted pair), and the day it is for. A rate published after ``t`` is never used, whatever day it is for;
        refuses when none was known."""
        U.currency(frm)
        U.currency(to)
        t = U.utc(t, "decision time")
        if frm == to:
            return 1.0, None
        best = None
        for (b, q, d), r in self.fx.items():
            if {b, q} == {frm, to} and r.known_at <= t and (best is None or (d, r.known_at) > (best[1], best[0].known_at)):
                best = (r, d)
        if best is None:
            later = [r for (b, q, _), r in self.fx.items() if {b, q} == {frm, to}]
            if later:
                raise LookAheadError(f"no {frm}/{to} rate was published by {t.isoformat()}")
            raise MissingInputError(f"no {frm}/{to} rate at all")
        r, d = best
        return (r.rate if r.base == frm else 1.0 / r.rate), d

    def convert(self, amount: float, frm: str, to: str, d: date) -> float:
        return amount * self.rate(frm, to, d)          # the rate is required even for a zero amount
