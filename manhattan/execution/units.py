"""Units and timestamps: the checks every other module of the execution model relies on.

* **Currencies** are ISO 4217 style codes, three upper-case letters (``USD``, ``EUR``). Anything else, such as
  ``usd``, ``US$`` or a minor unit like ``USc``, is refused: a price quoted in cents is described by the
  contract's ``price_unit_value`` (0.01), never by a currency code.
* **Quantities** are whole contracts, signed: positive is long, negative is short. ``True``/``False`` and
  fractional numbers are refused.
* **Timestamps** are timezone-aware ``datetime`` objects and are converted to UTC. A naive datetime, or a ``date``
  where a time is needed, is refused: the model cannot tell when it was.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone

from .errors import TimestampError, UnitError

_CCY = re.compile(r"^[A-Z]{3}$")


def currency(code) -> str:
    if not isinstance(code, str) or not _CCY.match(code):
        raise UnitError(f"currency must be a three-letter upper-case code such as 'USD', not {code!r}")
    return code


def contracts(q, what: str = "quantity") -> int:
    """A signed whole number of contracts."""
    if isinstance(q, bool) or not isinstance(q, int):
        if isinstance(q, float) and math.isfinite(q) and q == int(q):
            raise UnitError(f"{what} must be an int number of contracts, not the float {q!r}")
        raise UnitError(f"{what} must be a whole number of contracts (int), not {q!r}")
    return q


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


def utc(t, what: str = "timestamp") -> datetime:
    """A timezone-aware datetime, converted to UTC."""
    if not isinstance(t, datetime):
        kind = "a date" if isinstance(t, date) else repr(t)
        raise TimestampError(f"{what} must be a timezone-aware datetime, not {kind}")
    if t.tzinfo is None or t.utcoffset() is None:
        raise TimestampError(f"{what} is naive ({t.isoformat()}): give a timezone-aware datetime")
    return t.astimezone(timezone.utc)


def day(d, what: str = "day") -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TimestampError(f"{what} must be a calendar date (datetime.date), not {d!r}")
    return d
