"""Daily backtester: an executable and a window of point-in-time data in, a daily net return series out.

Protocol v3 section 2.1: positions are fixed with the information available before the period and executed at
the next available price.

**Time line.** The calendar ``D_0 .. D_n`` is the days on which any instrument has a price. A **decision** is
taken at the close of a rebalance day ``D_j`` from a ``View``: what was available at that close and nothing
else. It is **executed** at the close of ``D_{j+lag}`` (``lag = 1`` by default: the next available price) and
the new positions earn the returns of the days after that. With ``lag = 0`` the decision is traded at the close
it was taken at, which assumes that close could be both seen and traded.

**The signal sees a view, never the data.** ``signal(view)`` returns target weights by instrument name
(fractions of capital; a name left out is 0), or ``None`` to leave positions alone. ``View.get`` returns a
series as known at the decision; there is no other way in. A value published late is seen late.

**Volatility target** (optional). Targets are multiplied, at each decision, by
``vol_target / σ̂``, where ``σ̂`` is the annualised EWMA standard deviation (about zero, half-life
``vol_halflife`` days) of the **unscaled** strategy's own net returns over the days whose marks were all
available at the decision. Fewer than ``vol_min_obs`` such days: no position (a burn-in).

The accounting is ``manhattan.engine.accounting``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import accounting
from .pit import Window

REBALANCE = ("D", "W", "M")
YEAR = 252.0


@dataclass(frozen=True)
class Instrument:
    name: str
    price: str                      # series of marks: an excess-return index (futures) or a cash price or total-return index
    kind: str = "excess"            # "excess": no financing; "cash": financed at ``rate``
    rate: str | None = None         # series of annual short rates as decimals, for a cash instrument
    cost: float = 0.0               # one-way proportional trading cost

    def __post_init__(self):
        if self.kind not in ("excess", "cash"):
            raise ValueError("an instrument is 'excess' or 'cash'")
        if (self.kind == "cash") != (self.rate is not None):
            raise ValueError("a cash instrument names its short-rate series, and only a cash instrument does")
        if self.cost < 0:
            raise ValueError("a cost cannot be negative")


@dataclass(frozen=True)
class Strategy:
    """The engine's side of an executable: instruments, a signal and the trading rules."""
    instruments: tuple
    signal: Callable
    rebalance: str = "D"
    lag: int = 1
    vol_target: float | None = None     # annualised; None: trade the signal's weights as they are
    vol_halflife: float = 60.0
    vol_min_obs: int = 60
    max_scale: float | None = None      # cap on the volatility-target multiplier

    def __post_init__(self):
        if self.rebalance not in REBALANCE:
            raise ValueError(f"rebalance is one of {REBALANCE}")
        if isinstance(self.lag, bool) or int(self.lag) != self.lag or self.lag < 0:
            raise ValueError("the execution lag is a whole number of periods, 0 or more")
        if len({i.name for i in self.instruments}) != len(self.instruments) or not self.instruments:
            raise ValueError("instruments need distinct names, and there must be one")


class View:
    """What a signal may know: the window's data as available at the close of the decision day ``t``."""

    def __init__(self, window: Window, calendar: np.ndarray, index: int, names: tuple):
        self._window, self.calendar, self.index, self.instruments = window, calendar, index, names
        self.t = calendar[index]

    def get(self, series: str, n: int | None = None) -> tuple[np.ndarray, np.ndarray]:
        """(periods, values) of a series as known now; ``n`` keeps the last ``n``."""
        return self._window.as_of(series, self.t, n)

    def last(self, series: str, default: float = float("nan")) -> float:
        _, v = self._window.as_of(series, self.t, 1)
        return float(v[-1]) if v.size else default

    def known(self, series: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(periods, values, day each became available), for signals that act when something becomes known."""
        return self._window.as_of_with_availability(series, self.t)


@dataclass
class Result:
    dates: np.ndarray               # (n + 1,) the calendar
    net: np.ndarray                 # (n + 1,) daily net return in excess of cash; entry 0 is day 0 (no return)
    gross: np.ndarray
    financing: np.ndarray
    cost: np.ndarray
    turnover: np.ndarray
    exposure: np.ndarray            # (n + 1, m) held after each day's close
    decisions: dict                 # decision index -> target weights traded at index + lag (after scaling)
    scale: dict                     # decision index -> volatility-target multiplier (1.0 without a target)
    marks_known: np.ndarray         # (n + 1,) the day on which every mark of day k had become available
    instruments: tuple
    lag: int
    skipped: int = 0
    role: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def returns(self) -> np.ndarray:
        """The daily net returns of periods 1..n."""
        return self.net[1:]

    def summary(self) -> dict:
        r = self.returns
        return {"n_obs": int(r.size), "mean_annual": float(r.mean() * YEAR) if r.size else float("nan"),
                "vol_annual": float(r.std(ddof=1) * np.sqrt(YEAR)) if r.size > 1 else float("nan"),
                "sharpe": accounting.sharpe(r, YEAR), "turnover_annual": float(self.turnover.sum() / max(r.size, 1) * YEAR),
                "cost_annual": float(self.cost.sum() / max(r.size, 1) * YEAR), "skipped_trades": int(self.skipped)}

    def result_hash(self) -> str:
        """SHA-256 of the result in a canonical form: the calendar, the net returns and the exposures, rounded
        to 12 decimals. The same inputs give the same hash; any change of a return or a position changes it."""
        h = hashlib.sha256()
        h.update(self.dates.astype("datetime64[D]").astype("int64").tobytes())
        for a in (self.net, self.exposure):
            h.update(np.ascontiguousarray(np.round(a, 12) + 0.0, dtype="<f8").tobytes())
        h.update(json.dumps([list(self.instruments), self.lag], separators=(",", ":")).encode("utf-8"))
        return h.hexdigest()


def rebalance_days(calendar: np.ndarray, rule: str) -> np.ndarray:
    """Indices of the decision days: every day, or the last calendar day of each week or month."""
    n = calendar.size
    if rule == "D":
        return np.arange(n)
    # weeks run Monday to Sunday (day 0 of numpy's calendar, 1 January 1970, was a Thursday)
    key = (calendar.astype("datetime64[D]").astype("int64") + 3) // 7 if rule == "W" else calendar.astype("datetime64[M]")
    last = np.append(key[1:] != key[:-1], True)
    return np.flatnonzero(last)


def _grid(window: Window, instruments: tuple):
    """The calendar, the marks, the day each day's marks were all available, and the short rates."""
    series = {}
    for ins in instruments:
        p, v, a = window.as_of_with_availability(ins.price, window.end)
        series[ins.name] = (p, v, a)
    calendar = np.unique(np.concatenate([p for p, _, _ in series.values()]))
    if calendar.size < 2:
        raise ValueError("the window holds fewer than two days of prices")
    m = len(instruments)
    price = np.full((calendar.size, m), np.nan)
    known = np.full((calendar.size, m), calendar[0])
    for i, ins in enumerate(instruments):
        p, v, a = series[ins.name]
        at = np.searchsorted(calendar, p)
        price[at, i], known[at, i] = v, a
    rate = np.zeros((calendar.size, m))
    for i, ins in enumerate(instruments):
        if ins.kind == "cash":
            p, v, a = window.as_of_with_availability(ins.rate, window.end)
            if p.size == 0:
                raise ValueError(f"{ins.name}: no short rate in the window")
            at = np.searchsorted(p, calendar, "right") - 1            # the last rate on or before each day
            if (at < 0).any():
                raise ValueError(f"{ins.name}: the short rate starts after the first price")
            rate[:, i] = v[at]
            known[1:, i] = np.maximum(known[1:, i], a[at[:-1]])       # day k is financed at the rate of day k − 1
    marks_known = np.maximum.accumulate(known.max(axis=1))            # all marks up to day k were known by then
    return calendar, price, marks_known, rate


def _weights(raw, names: tuple) -> np.ndarray | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        unknown = set(raw) - set(names)
        if unknown:
            raise ValueError(f"the signal named instruments that are not in the strategy: {sorted(unknown)}")
        w = np.array([float(raw.get(n, 0.0)) for n in names])
    else:
        w = np.asarray(raw, dtype=float).reshape(len(names))
    if not np.isfinite(w).all():
        raise ValueError("a target weight must be a finite number")
    return w


def _ewma_vol(net: np.ndarray, halflife: float) -> float:
    """Annualised EWMA standard deviation about zero, weights renormalised over the days there are."""
    a = 0.5 ** (1.0 / halflife)
    w = a ** np.arange(net.size - 1, -1, -1)
    return float(np.sqrt((w @ (net * net)) / w.sum() * YEAR))


def run(window: Window, strategy: Strategy) -> Result:
    """Run ``strategy`` over ``window``."""
    names = tuple(i.name for i in strategy.instruments)
    calendar, price, marks_known, rate = _grid(window, strategy.instruments)
    n1, m = price.shape
    cash = np.array([i.kind == "cash" for i in strategy.instruments])
    cost = np.array([i.cost for i in strategy.instruments])
    decide = rebalance_days(calendar, strategy.rebalance)
    raw = {}
    for j in decide:
        if j + strategy.lag >= n1:
            continue                                                  # it could never be executed inside the window
        w = _weights(strategy.signal(View(window, calendar, int(j), names)), names)
        if w is not None:
            raw[int(j)] = w

    def account(decisions: dict) -> accounting.Ledger:
        target = np.full((n1, m), np.nan)
        trade = np.zeros(n1, dtype=bool)
        for j, w in decisions.items():
            target[j + strategy.lag], trade[j + strategy.lag] = w, True
        return accounting.run(calendar, price, target, trade, cash=cash, rate=rate, cost=cost)

    scale = {j: 1.0 for j in raw}
    decisions = raw
    if strategy.vol_target is not None:
        unscaled = account(raw).net
        for j in raw:
            k = int(np.searchsorted(marks_known, calendar[j], "right")) - 1      # the last day fully marked by now
            seen = unscaled[1 : k + 1]
            moved = np.flatnonzero(seen != 0.0)
            seen = seen[moved[0] :] if moved.size else seen[:0]       # from the first day with a position
            if seen.size < strategy.vol_min_obs:
                scale[j] = 0.0
                continue
            vol = _ewma_vol(seen, strategy.vol_halflife)
            s = strategy.vol_target / vol if vol > 0 else 0.0
            scale[j] = min(s, strategy.max_scale) if strategy.max_scale is not None else s
        decisions = {j: raw[j] * scale[j] for j in raw}
    led = account(decisions)
    return Result(dates=calendar, net=led.net, gross=led.gross, financing=led.financing, cost=led.cost,
                  turnover=led.turnover, exposure=led.exposure, decisions=decisions, scale=scale,
                  marks_known=marks_known, instruments=names, lag=int(strategy.lag), skipped=led.skipped,
                  role=window.role, meta={"rebalance": strategy.rebalance, "vol_target": strategy.vol_target})
