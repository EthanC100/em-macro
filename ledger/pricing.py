"""Instrument returns between two marks, shared by the daily estimates, Janus and the stress tests.

Direction convention (all books): ``long`` is long the price-like instrument.
  * FX "X per USD" (BRL, MXN, JPY, ...): long = long X against the dollar; return = v0 / v1 - 1.
  * FX "USD per X" (EUR, GBP): long = long X; return = v1 / v0 - 1.
  * yield (% a year): long = long the 10-year bond (gains when the yield falls);
    return = -D x (y1 - y0) / 100, D the modified duration of a 10-year par bond at y0 (semi-annual coupons).
    ``carry=True`` adds (y0 - funding) x days / 365 (the algorithm's excess-return carry).
  * spread (bp over the Bund): long = long the country's bond, short the Bund (gains when the spread tightens);
    return = -D x (s1 - s0) / 10,000, D at the country leg's yield (default 4%).
  * commodity (price): long = long the front-month future; return = v1 / v0 - 1 (P&L on the spot proxy where
    no free futures settlement exists; see data/janus/universe.json).
  * cash (% a year, e.g. 3-month T-bill): return = y0 / 100 x days / 365.

Stops are levels in the instrument's own unit. ``stop_return`` is the return from entry to the stop (negative
for a valid stop); a stop is hit when the return from entry to a mark is at or below it. This works for every
kind without a side table, and makes "tighten only" a simple rule: the new stop's return must be higher.
"""
from __future__ import annotations

import math


def duration_10y(yield_pct: float | None) -> float:
    """Modified duration of a 10-year par bond with semi-annual coupons at ``yield_pct``."""
    y = (yield_pct if yield_pct is not None and yield_pct > 0.05 else 4.0) / 100.0
    return (1 - (1 + y / 2) ** -20) / y


def kind_of(row: dict) -> str:
    """fx_per_usd, usd_per_fx, yield, spread, commodity or cash, from a registry row."""
    unit = (row.get("unit") or "").strip()
    kind = (row.get("kind") or "").strip()
    if kind == "fx" or unit.endswith("per USD") or unit.startswith("USD per"):
        return "usd_per_fx" if unit.startswith("USD per") else "fx_per_usd"
    if kind == "spread" or unit == "bp":
        return "spread"
    if kind == "cash":
        return "cash"
    if kind == "commodity":
        return "commodity"
    return "yield"


def ret_long(kind: str, v0: float, v1: float, days: float = 0.0, carry: bool = False, funding: float | None = None,
             leg_yield: float | None = None) -> float | None:
    """Return of a long position (fraction of notional) from v0 to v1."""
    if v0 is None or v1 is None:
        return None
    if kind == "fx_per_usd":
        return v0 / v1 - 1 if v1 else None
    if kind == "usd_per_fx":
        return v1 / v0 - 1 if v0 else None
    if kind == "commodity":
        return v1 / v0 - 1 if v0 else None
    if kind == "cash":
        return v0 / 100.0 * days / 365.0
    if kind == "spread":
        r = -duration_10y(leg_yield) * (v1 - v0) / 1e4
        if carry:
            r += v0 / 1e4 * days / 365.0
        return r
    # yield
    r = -duration_10y(v0) * (v1 - v0) / 100.0
    if carry:
        r += ((v0 - (funding or 0.0)) / 100.0) * days / 365.0
    return r


def signed(direction: str) -> float:
    return -1.0 if str(direction).lower() in ("short", "sell", "-1") else 1.0


def position_return(kind: str, direction: str, v0: float, v1: float, **kw) -> float | None:
    r = ret_long(kind, v0, v1, **kw)
    return None if r is None else signed(direction) * r


def stop_return(kind: str, direction: str, entry: float, stop: float) -> float | None:
    return position_return(kind, direction, entry, stop)


def stop_hit(kind: str, direction: str, entry: float, stop: float, mark: float) -> bool:
    s = stop_return(kind, direction, entry, stop)
    m = position_return(kind, direction, entry, mark)
    return s is not None and m is not None and m <= s + 1e-12


def valid_stop(kind: str, direction: str, ref: float, stop: float) -> bool:
    """A stop must be on the losing side of the reference level."""
    s = stop_return(kind, direction, ref, stop)
    return s is not None and s < 0


def ann_vol_pct(points: list[tuple], kind: str, window: int = 60) -> float | None:
    """Annualised volatility (%) of daily long returns over the last ``window`` observations."""
    pts = [p for p in points if p[1] is not None][-(window + 1):]
    rets = [ret_long(kind, a[1], b[1]) for a, b in zip(pts, pts[1:])]
    rets = [r for r in rets if r is not None]
    if len(rets) < 10:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var * 252) * 100, 2)
