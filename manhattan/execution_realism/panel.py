"""A contract-aware daily panel: what the adapter needs to fill, mark and roll futures for many roots at once.

For each trading day ``t`` and root ``a`` (arrays are ``(n, A)``):

* ``level[t, a]``: the tradable **settlement** on day ``t`` of the contract month held **after** the close of ``t``.
  It sizes decisions, prices trades and is the tick grid. ``NaN`` means no settlement was published.
* ``exit_level[t, a]``: the settlement on day ``t`` of the month held **before** that close (held after ``t-1``).
  It equals ``level`` except on a roll day, where it prices the leg that closes the old month.
* ``roll[t, a]``: the held month changes at the close of ``t``.
* ``adv[t, a]``, ``vol_points[t, a]``: the liquidity estimate (contracts per day; standard deviation of daily
  settlement changes, in price points) **known at the close of** ``t``. A decision at ``t`` uses row ``t``; a carried
  order on day ``d`` uses row ``d - 1`` (PR #85's rule).
* ``fx[ccy][t]``: units of the base currency per one unit of ``ccy``, day ``t``'s fix (valuation; ``NaN`` missing).

**P&L comes from same-contract changes.** The mark of day ``t`` is ``exit_level[t] − (the last mark of that same
month)``; nothing is booked for the gap between two months at a roll. A back-adjusted, ratio-adjusted or spliced
continuous series is **not** a tradable price and is refused (``price_kind``); PR #85 design section 8 lists what
each gets wrong.

``from_contracts`` builds the panel from per-month settlements and a held-month schedule, the form a research
script would produce from a point-in-time store; the panel itself reads nothing.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

import numpy as np

from .errors import MissingInputError, UnitError
from .instruments import Instrument, currency, on_tick

PRICE_KINDS_REFUSED = {
    "back_adjusted": "a difference back-adjusted series is revised at every later roll and is not a price",
    "ratio_adjusted": "a ratio back-adjusted series is not a price and gets point changes wrong",
    "spliced": "a spliced series books the calendar gap between months as P&L on roll days",
    "continuous": "a continuous series is not the settlement of a contract that could be traded",
}
DATA_KINDS = ("synthetic", "historical")


def _frozen(a, dtype=float) -> np.ndarray:
    x = np.array(a, dtype=dtype, copy=True)
    x.setflags(write=False)
    return x


@dataclass(frozen=True, eq=False)
class SettlementPanel:
    days: tuple                 # datetime.date, strictly increasing
    instruments: tuple          # Instrument, one per root (column order)
    level: np.ndarray
    exit_level: np.ndarray
    roll: np.ndarray
    adv: np.ndarray
    vol_points: np.ndarray
    base_currency: str
    fx: dict = field(default_factory=dict)
    data_kind: str = "synthetic"
    price_kind: str = "tradable_settlement"
    held: np.ndarray | None = None      # optional (n, A) contract ids, for audit only

    def __post_init__(self):
        if self.price_kind in PRICE_KINDS_REFUSED:
            raise UnitError(f"price_kind {self.price_kind!r} refused: {PRICE_KINDS_REFUSED[self.price_kind]}")
        if self.price_kind != "tradable_settlement":
            raise UnitError("price_kind must be 'tradable_settlement'")
        if self.data_kind not in DATA_KINDS:
            raise UnitError(f"data_kind is one of {DATA_KINDS}")
        currency(self.base_currency)
        days = tuple(self.days)
        if not days or any(not isinstance(d, date) for d in days):
            raise UnitError("days is a non-empty sequence of datetime.date")
        if any(b <= a for a, b in zip(days, days[1:])):
            raise UnitError("days must strictly increase")
        insts = tuple(self.instruments)
        if not insts or any(not isinstance(i, Instrument) for i in insts):
            raise UnitError("instruments is a non-empty sequence of Instrument")
        if len({i.root for i in insts}) != len(insts):
            raise UnitError("each root appears once")
        n, A = len(days), len(insts)
        object.__setattr__(self, "days", days)
        object.__setattr__(self, "instruments", insts)
        for f in ("level", "exit_level", "adv", "vol_points"):
            x = _frozen(getattr(self, f))
            if x.shape != (n, A):
                raise UnitError(f"{f} has shape {x.shape}, expected {(n, A)}")
            object.__setattr__(self, f, x)
        r = _frozen(self.roll, bool)
        if r.shape != (n, A):
            raise UnitError(f"roll has shape {r.shape}, expected {(n, A)}")
        if r[0].any():
            raise UnitError("no roll on the first day: there is no earlier month to roll from")
        object.__setattr__(self, "roll", r)
        same = ~r
        lv, ex = self.level, self.exit_level
        both_nan = np.isnan(lv) & np.isnan(ex)
        if not np.all(both_nan[same] | (lv[same] == ex[same])):
            raise UnitError("exit_level must equal level on every day that is not a roll day")
        for a, inst in enumerate(insts):
            for arr, what in ((lv, "level"), (ex, "exit_level")):
                col = arr[:, a]
                if np.isinf(col).any():
                    raise UnitError(f"{inst.root} {what} has an infinite value")
                for t in np.flatnonzero(np.isfinite(col)):
                    if not on_tick(float(col[t]), inst.tick_size):
                        raise UnitError(f"{inst.root} {what} on {days[t]} = {col[t]!r} is off the tick grid "
                                        f"{inst.tick_size}: probably a unit error or an adjusted series")
        if (np.nan_to_num(self.adv, nan=0.0) < 0).any() or (np.nan_to_num(self.vol_points, nan=0.0) < 0).any():
            raise UnitError("adv and vol_points cannot be negative")
        fx = {}
        for ccy, arr in dict(self.fx).items():
            currency(ccy)
            if ccy == self.base_currency:
                raise UnitError("the base currency needs no FX series")
            x = _frozen(arr)
            if x.shape != (n,):
                raise UnitError(f"fx[{ccy}] has shape {x.shape}, expected {(n,)}")
            if (x[np.isfinite(x)] <= 0).any():
                raise UnitError(f"fx[{ccy}] must be positive")
            fx[ccy] = x
        object.__setattr__(self, "fx", MappingProxyType(fx))
        if self.held is not None:
            h = np.array(self.held, dtype=object, copy=True)
            if h.shape != (n, A):
                raise UnitError("held has the panel's shape")
            h.setflags(write=False)
            object.__setattr__(self, "held", h)

    @property
    def shape(self) -> tuple[int, int]:
        return self.level.shape

    @property
    def roots(self) -> tuple:
        return tuple(i.root for i in self.instruments)

    def fx_rate(self, ccy: str, t: int) -> float:
        """Base-currency units per one ``ccy`` on day ``t``; refuses a missing rate (even for a zero amount)."""
        if ccy == self.base_currency:
            return 1.0
        arr = self.fx.get(ccy)
        if arr is None:
            raise MissingInputError(f"no FX series for {ccy} -> {self.base_currency}")
        v = float(arr[t])
        if not np.isfinite(v):
            raise MissingInputError(f"no {ccy}{self.base_currency} rate on {self.days[t]}")
        return v

    def digest(self) -> str:
        """SHA-256 of every input the panel holds (calendar, metadata, prices, rolls, liquidity, FX, kinds).
        It identifies the numbers; it does not authenticate where they came from."""
        h = hashlib.sha256()
        head = {"v": 1, "days": [d.isoformat() for d in self.days],
                "instruments": [i.as_dict() for i in self.instruments], "base": self.base_currency,
                "data_kind": self.data_kind, "price_kind": self.price_kind, "fx": sorted(self.fx)}
        h.update(json.dumps(head, sort_keys=True, separators=(",", ":")).encode())
        for arr in (self.level, self.exit_level, self.adv, self.vol_points):
            h.update(np.ascontiguousarray(arr, dtype="<f8").tobytes())
        h.update(np.ascontiguousarray(self.roll, dtype=np.uint8).tobytes())
        for ccy in sorted(self.fx):
            h.update(ccy.encode() + np.ascontiguousarray(self.fx[ccy], dtype="<f8").tobytes())
        return h.hexdigest()

    @classmethod
    def from_contracts(cls, *, days, instruments, prices: dict, held: dict, adv, vol_points, base_currency: str,
                       fx=None, data_kind: str = "synthetic") -> "SettlementPanel":
        """``prices[root][contract_id]``: that month's settlements over ``days`` (NaN where none); ``held[root]``:
        the contract id held after each day's close (``None`` = the root is not available that day: no level).
        """
        n, A = len(days), len(instruments)
        level = np.full((n, A), np.nan)
        exit_level = np.full((n, A), np.nan)
        roll = np.zeros((n, A), bool)
        ids = np.empty((n, A), dtype=object)
        for a, inst in enumerate(instruments):
            sched = list(held[inst.root])
            if len(sched) != n:
                raise UnitError(f"held[{inst.root}] has {len(sched)} entries for {n} days")
            book = {k: np.asarray(v, float) for k, v in prices[inst.root].items()}
            for t in range(n):
                c = sched[t]
                ids[t, a] = c
                if c is not None:
                    if c not in book:
                        raise MissingInputError(f"no settlements for {c}")
                    level[t, a] = book[c][t]
                prev = sched[t - 1] if t else c
                if t and prev is not None and c is not None and prev != c:
                    roll[t, a] = True
                    exit_level[t, a] = book[prev][t]
                else:
                    exit_level[t, a] = level[t, a]
        return cls(days=tuple(days), instruments=tuple(instruments), level=level, exit_level=exit_level,
                   roll=roll, adv=np.asarray(adv, float), vol_points=np.asarray(vol_points, float),
                   base_currency=base_currency, fx=dict(fx or {}), data_kind=data_kind, held=ids)
