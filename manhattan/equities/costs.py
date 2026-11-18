"""Trading costs and shorting: borrow availability and fees, recall risk, financing, spread crossing and impact.

These are research **assumptions** with explicit parameters, none defaulted; they are not measured costs. Protocol v3.1 §10.3
re-estimates cost models from recorded spreads once a year; nothing here replaces that. Session 4's futures
execution model is a separate thing: ``integration.ExecutionCostModel`` is the contract the two can share later.

**Borrow is data, not an assumption of zero.** ``BorrowBook.status(security, day)`` returns the record in force at the
close of ``day`` (published by then and not older than ``max_staleness_days``). No record means **not shortable**:
``BorrowError``, never a free borrow. A hard-to-borrow security carries its fee; a recall probability per day turns
into an expected forced-close cost.

**A cost model that can price a short must name its borrow source.** ``EquityCostModel.check_book`` refuses a book
with short positions when the model has no borrow book (the "borrow-cost omission").

    trade cost (fraction of traded notional) = half_spread + commission + impact · σ_daily · sqrt(traded / ADV)
    holding cost per day (fraction of capital) = Σ_short |w| · (fee_annual + short_financing) / 365
                                               + Σ_long-levered financing + Σ_short |w| · p_recall · recall_cost
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from .errors import BorrowError, EquityDataError


@dataclass(frozen=True)
class BorrowRecord:
    security_id: str
    day: date                         # the day the record describes
    known_from: date                  # the day it was published (locate files are usually next-morning)
    available: bool
    fee_annual: float                 # decimal per year (0.003 = 30 bp); general collateral is a positive fee
    recall_prob_daily: float = 0.0
    source: str = ""

    def __post_init__(self):
        if self.known_from < self.day:
            raise EquityDataError(f"{self.security_id}: a borrow record published before the day it describes")
        if not (np.isfinite(self.fee_annual) and self.fee_annual >= 0):
            raise EquityDataError(f"{self.security_id}: a borrow fee is a non-negative number")
        if not 0 <= self.recall_prob_daily <= 1:
            raise EquityDataError(f"{self.security_id}: recall probability is in [0, 1]")


class BorrowBook:
    def __init__(self, records=(), *, max_staleness_days: int = 5):
        self.max_staleness_days = max_staleness_days
        self._rec: dict[str, list[BorrowRecord]] = {}
        for r in records:
            self.add(r)

    def add(self, r: BorrowRecord) -> None:
        self._rec.setdefault(r.security_id, []).append(r)

    def status(self, security_id: str, day: date) -> BorrowRecord:
        """The latest record known at ``day`` (published on or before it), if recent enough; else ``BorrowError``."""
        recs = [r for r in self._rec.get(security_id, []) if r.known_from <= day]
        if not recs:
            raise BorrowError(f"{security_id}: no borrow information known at {day}; treated as not shortable")
        r = max(recs, key=lambda r: (r.day, r.known_from))
        if (day - r.day).days > self.max_staleness_days:
            raise BorrowError(f"{security_id}: borrow information at {day} is {(day - r.day).days} days old")
        return r


@dataclass(frozen=True, kw_only=True)
class EquityCostModel:
    """Every parameter is stated by the caller with a ``reference`` for where it came from (S8 M10): no default can
    make a strategy look cheap by omission. Values are fractions (``half_spread=0.0005`` is 5 bp)."""
    half_spread: float                        # fraction of traded notional
    commission: float
    impact: float                             # coefficient on σ_daily · sqrt(participation)
    short_financing: float                    # extra annual spread paid on short proceeds beyond the fee
    long_financing: float                     # annual spread over cash on leverage above 100% long
    recall_cost: float                        # cost of a forced buy-in, fraction of the position
    reference: str                            # where these numbers come from (a measurement, a broker schedule)
    borrow: BorrowBook | None = None
    name: str = "equity-cost-assumption"

    def __post_init__(self):
        for k in ("half_spread", "commission", "impact", "short_financing", "long_financing", "recall_cost"):
            v = getattr(self, k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or v < 0:
                raise EquityDataError(f"cost parameter {k} must be a finite number, 0 or more")
        if not isinstance(self.reference, str) or not self.reference.strip():
            raise EquityDataError("a cost model states the reference for its parameters")

    def trade_cost(self, traded_notional: float, adv_notional: float, daily_vol: float) -> float:
        """Cost as a fraction of the traded notional."""
        if traded_notional < 0 or adv_notional <= 0 or daily_vol < 0:
            raise EquityDataError("trade cost needs traded notional ≥ 0, ADV > 0 and volatility ≥ 0")
        return self.half_spread + self.commission + self.impact * daily_vol * float(np.sqrt(traded_notional /
                                                                                            adv_notional))

    def check_book(self, weights: dict, day: date) -> None:
        """Refuse a book whose short positions cannot be priced or are not borrowable at ``day``."""
        shorts = [s for s, w in weights.items() if w < 0]
        if not shorts:
            return
        if self.borrow is None:
            raise BorrowError("the book has short positions and the cost model has no borrow source "
                              "(borrow-cost omission)")
        for s in shorts:
            if not self.borrow.status(s, day).available:
                raise BorrowError(f"{s}: not borrowable at {day}")

    def holding_cost_daily(self, weights: dict, day: date) -> float:
        """Expected holding cost of one calendar day, as a fraction of capital."""
        self.check_book(weights, day)
        cost = 0.0
        for s, w in weights.items():
            if w < 0:
                r = self.borrow.status(s, day)
                cost += -w * ((r.fee_annual + self.short_financing) / 365.0 + r.recall_prob_daily * self.recall_cost)
        long_gross = sum(w for w in weights.values() if w > 0)
        cost += max(long_gross - 1.0, 0.0) * self.long_financing / 365.0
        return float(cost)

    def turnover_cost(self, before: dict, after: dict, capital: float, adv: dict, vol: dict) -> float:
        """Cost of moving from ``before`` to ``after`` weights, as a fraction of capital."""
        total = 0.0
        for s in set(before) | set(after):
            dw = abs(after.get(s, 0.0) - before.get(s, 0.0))
            if dw == 0:
                continue
            if s not in adv or s not in vol:
                raise EquityDataError(f"{s}: trade cost needs its ADV and volatility")
            total += dw * self.trade_cost(dw * capital, adv[s], vol[s])
        return float(total)
