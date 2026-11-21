"""Instrument metadata and tick arithmetic.

``Instrument`` describes one futures **root** (every month of it shares tick, multiplier and currency here; the
held month is the panel's business). The tick-value identity ``tick_value = tick_size × multiplier ×
price_unit_value`` is checked at construction, so a cents-quoted contract described in dollars (a factor-of-100
error) is refused. The rounding arithmetic is decimal on the ``repr`` of the floats, the same convention as PR #85
(``manhattan/execution/contracts.py`` at 3f6b213), so ``70.23`` stays ``70.23`` and the two models round alike.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal

from .errors import UnitError

_CCY = re.compile(r"^[A-Z]{3}$")
_ON_TICK_TOL = Decimal("1e-9")


def currency(code) -> str:
    if not isinstance(code, str) or not _CCY.match(code):
        raise UnitError(f"currency must be a three-letter upper-case code such as 'USD', not {code!r}")
    return code


def finite(x, what: str, *, positive: bool = False, nonneg: bool = False) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise UnitError(f"{what} must be a number, not {x!r}")
    x = float(x)
    if not math.isfinite(x):
        raise UnitError(f"{what} must be finite, not {x!r}")
    if positive and x <= 0:
        raise UnitError(f"{what} must be greater than 0, not {x!r}")
    if nonneg and x < 0:
        raise UnitError(f"{what} cannot be negative ({x!r})")
    return x


@dataclass(frozen=True)
class Instrument:
    root: str
    currency: str                   # currency of prices, tick value and P&L
    tick_size: float                # price units
    tick_value: float               # currency per tick per contract
    multiplier: float               # underlying units per contract
    price_unit_value: float = 1.0   # currency per price unit per underlying unit (1.0 dollars, 0.01 cents)

    def __post_init__(self):
        if not isinstance(self.root, str) or not self.root.isalnum() or not self.root.isupper():
            raise UnitError(f"root must be upper-case letters and digits, not {self.root!r}")
        currency(self.currency)
        for f in ("tick_size", "tick_value", "multiplier", "price_unit_value"):
            finite(getattr(self, f), f, positive=True)
        implied = self.tick_size * self.multiplier * self.price_unit_value
        if abs(implied - self.tick_value) > 1e-9 * max(1.0, abs(self.tick_value)):
            raise UnitError(f"{self.root}: tick_value {self.tick_value} disagrees with tick_size x multiplier x "
                            f"price_unit_value = {implied:.10g}; check the price unit")

    @property
    def point_value(self) -> float:
        """Currency per one price point per contract."""
        return self.multiplier * self.price_unit_value

    def as_dict(self) -> dict:
        return {"root": self.root, "currency": self.currency, "tick_size": self.tick_size,
                "tick_value": self.tick_value, "multiplier": self.multiplier,
                "price_unit_value": self.price_unit_value}


def _d(x: float) -> Decimal:
    return Decimal(repr(float(x)))


def _ticks(price: float, tick: float) -> tuple[Decimal, Decimal]:
    n = _d(price) / _d(tick)
    return n, n.to_integral_value(rounding=ROUND_HALF_EVEN)


def on_tick(price: float, tick: float) -> bool:
    n, k = _ticks(price, tick)
    return abs(n - k) <= _ON_TICK_TOL


def round_to_tick(price: float, tick: float, mode: str) -> float:
    """``nearest`` (half to even), ``up`` or ``down``; a price on the grid (within 1e-9 tick) stays put."""
    if mode not in ("nearest", "up", "down"):
        raise UnitError(f"mode is 'nearest', 'up' or 'down', not {mode!r}")
    n, k = _ticks(price, tick)
    if abs(n - k) > _ON_TICK_TOL:
        if mode == "up":
            k = n.to_integral_value(rounding=ROUND_CEILING)
        elif mode == "down":
            k = n.to_integral_value(rounding=ROUND_FLOOR)
    return float(k * _d(tick))


def adverse_round(price: float, tick: float, side: int) -> float:
    """Round against the trader: a buy (+1) up, a sell (-1) down."""
    if side not in (1, -1):
        raise UnitError("side is +1 (buy) or -1 (sell)")
    return round_to_tick(price, tick, "up" if side > 0 else "down")
