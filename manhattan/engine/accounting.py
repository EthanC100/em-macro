"""Accounting: from marks and trades to a daily net return, per unit of capital, in excess of cash.

Protocol v3 section 2.1: ``r_{x,t}`` is the gross return minus trading and financing costs, as a fraction of the
executable's notional capital, in excess of cash. Futures returns are excess returns already; cash instruments
are financed at the local short rate.

The calendar is ``D_0 .. D_n``. Entry ``k`` of every output is about day ``D_k``:

    r_{i,k}     = P_{i,k} / (last mark of i) − 1            0 while i has no new price; the whole gap when it returns
    gross_k     = Σ_i e_{i,k} · r_{i,k}                      e = exposure held over (D_{k−1}, D_k], a fraction of capital
    financing_k = Σ_{i cash} e_{i,k} · rate_{i,k−1} · days(D_{k−1}, D_k) / 365
    drift       e'_i = e_{i,k} (1 + r_{i,k}) / (1 + gross_k − financing_k)
    trade at the close of D_k (if any): turnover_{i,k} = |target_{i,k} − e'_i|
    cost_k      = (1 + gross_k − financing_k) · Σ_i turnover_{i,k} · cost_i
    net_k       = gross_k − financing_k − cost_k            exactly

Targets are fractions of the capital left after the trade's cost. An instrument with no price on a trade day is
not traded that day: its exposure stays where it drifted, and the skipped trade is counted. No day is dropped:
a position in an instrument whose price is missing keeps its last mark, and the return of the whole gap is
booked on the day the price is back. Day 0 has no return; a trade at its close costs ``cost_0``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Ledger:
    """Daily accounts of one run. Arrays are ``(n + 1,)`` or ``(n + 1, m)``, entry ``k`` about day ``D_k``."""
    net: np.ndarray
    gross: np.ndarray
    financing: np.ndarray
    cost: np.ndarray
    turnover: np.ndarray            # Σ_i |trade| at the close of each day
    exposure: np.ndarray            # (n + 1, m): held after the close of each day (so over the next period)
    skipped: int                    # instrument-trades not made because the instrument had no price that day


def run(dates, price: np.ndarray, target: np.ndarray, trade: np.ndarray, *, cash=None, rate=None, cost=0.0) -> Ledger:
    """Account for trading ``target`` weights at the close of the days marked in ``trade``.

    ``price`` is ``(n + 1, m)`` with NaN where an instrument has no price; ``target`` is ``(n + 1, m)`` (rows of
    days without a trade are ignored; a NaN target leaves that instrument alone); ``cash`` marks the instruments
    financed at ``rate`` (``(n + 1, m)``, annual, as a decimal: the rate in force from that day's close);
    ``cost`` is the one-way proportional cost of each instrument."""
    dates = np.asarray(dates, dtype="datetime64[D]")
    price = np.atleast_2d(np.asarray(price, dtype=float))
    n1, m = price.shape
    target = np.asarray(target, dtype=float).reshape(n1, m)
    trade = np.asarray(trade, dtype=bool).reshape(n1)
    cash = np.zeros(m, dtype=bool) if cash is None else np.asarray(cash, dtype=bool).reshape(m)
    rate = np.zeros((n1, m)) if rate is None else np.asarray(rate, dtype=float).reshape(n1, m)
    cost_i = np.broadcast_to(np.asarray(cost, dtype=float), (m,))
    if dates.shape != (n1,) or (np.diff(dates) <= np.timedelta64(0, "D")).any():
        raise ValueError("dates must be one strictly increasing day per row of prices")
    if cash.any() and not np.isfinite(rate[:, cash]).all():
        raise ValueError("a cash instrument needs a short rate on every day")
    days = np.diff(dates).astype(float)
    out = Ledger(*(np.zeros(n1) for _ in range(5)), exposure=np.zeros((n1, m)), skipped=0)
    e = np.zeros(m)
    mark = np.full(m, np.nan)
    for k in range(n1):
        px = price[k]
        have = np.isfinite(px)
        growth = 1.0
        if k:
            r = np.where(have & np.isfinite(mark), px / np.where(np.isfinite(mark), mark, 1.0) - 1.0, 0.0)
            out.gross[k] = float(e @ r)
            out.financing[k] = float(e[cash] @ rate[k - 1, cash]) * days[k - 1] / 365.0
            growth = 1.0 + out.gross[k] - out.financing[k]
            if growth <= 0:
                raise ValueError(f"capital is exhausted on {dates[k]}: the position lost everything")
            e = e * (1.0 + r) / growth
        mark = np.where(have, px, mark)
        if trade[k]:
            want = np.isfinite(target[k])
            can = want & have
            out.skipped += int(np.count_nonzero(want & ~have & (np.abs(np.where(want, target[k], 0.0) - e) > 0)))
            new = np.where(can, target[k], e)
            turn = np.abs(new - e)
            out.turnover[k] = float(turn.sum())
            out.cost[k] = growth * float(turn @ cost_i)
            e = new
        out.net[k] = out.gross[k] - out.financing[k] - out.cost[k]
        out.exposure[k] = e
    return out


def sharpe(net: np.ndarray, periods_per_year: float = 252.0) -> float:
    """Annualised Sharpe ratio of a series of excess returns (NaN when it cannot be computed)."""
    x = np.asarray(net, dtype=float)
    sd = x.std(ddof=1) if x.size > 1 else 0.0
    return float(x.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else float("nan")
