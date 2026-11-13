"""Point-in-time data: every value knows the period it describes and the day it became available.

    store.add("fx_spot", periods, values, lag_days=1)          # published the next calendar day
    reader = Reader(store, caller="session", domain="fx_daily", fence=fence)
    window = reader.window(date(2005, 1, 3), date(2019, 12, 31))  # manhattan.roles.check_read decides
    window.as_of("fx_spot", day)                                # what was known at the end of that day

**Two dates per value.** ``period`` is the day (or the last day of the month, quarter ...) the value is about.
``available`` is the first day at whose close the value may be used for a decision. A value is never returned by
a read as of an earlier day. A **revision** is a second value for the same period with a later ``available``: it
shows from that day on, and a read as of an earlier day still returns the earlier value. Availability is given
explicitly, or as the period plus a publication lag in calendar days (the hypothesis spec's
``data_sources[*].publication_lag_days``); a value with neither is refused.

**One door.** A ``PitStore`` gives no data away. Data come out through a ``Reader``, which is bound to a caller,
a domain and the fence of ``config/manhattan.yaml``, and every window it opens is first put to
``manhattan.roles.check_read``. A session therefore cannot read reserve, embargoed or forward dates, and with
the default configuration nothing dated after 2019-12-31. The engine takes a ``Window``; it never sees a store.

**Data hash.** ``PitStore.data_hash()`` is the SHA-256 of the canonical form of everything in the store (series
names, periods, availabilities, values, in a fixed order). It is the ``data_hash`` of a ledger record.

Daily resolution. Minute data are out of scope here (ARCHITECTURE section 6.4).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

import numpy as np

from manhattan import roles

DAY = np.timedelta64(1, "D")


class PitError(ValueError):
    """Data that cannot be stored or read point in time."""


def _days(x) -> np.ndarray:
    return np.asarray(x, dtype="datetime64[D]")


def _day(x) -> np.datetime64:
    return np.datetime64(x, "D")


class PitStore:
    """Values by series, each with its period and its availability day. Append-only: a value is never changed
    or removed; a correction is a revision with its own availability."""

    def __init__(self):
        self._period: dict[str, np.ndarray] = {}
        self._available: dict[str, np.ndarray] = {}
        self._value: dict[str, np.ndarray] = {}
        self._simple: dict[str, bool] = {}

    def add(self, series: str, periods, values, *, available=None, lag_days: int | None = None) -> None:
        """Add values of ``series``. Give ``available`` (one day per value) or ``lag_days`` (calendar days after
        the period; 0 means usable at that day's close)."""
        p = np.atleast_1d(_days(periods))
        v = np.atleast_1d(np.asarray(values, dtype=float))
        if p.shape != v.shape or p.ndim != 1:
            raise PitError(f"{series}: periods and values must be two lists of the same length")
        if (available is None) == (lag_days is None):
            raise PitError(f"{series}: give either an availability day for each value or a publication lag, not both or neither")
        if lag_days is not None:
            if isinstance(lag_days, bool) or int(lag_days) != lag_days or lag_days < 0:
                raise PitError(f"{series}: a publication lag is a whole number of days, 0 or more")
            a = p + int(lag_days) * DAY
        else:
            a = np.atleast_1d(_days(available))
            if a.shape != p.shape:
                raise PitError(f"{series}: one availability day per value")
        if np.isnat(p).any() or np.isnat(a).any():
            raise PitError(f"{series}: a period or an availability day is missing")
        if (a < p).any():
            raise PitError(f"{series}: a value cannot be available before the period it describes")
        keep = np.isfinite(v)                                   # a missing value is simply not there
        p, a, v = p[keep], a[keep], v[keep]
        if series in self._period:
            p, a, v = (np.concatenate([old[series], new]) for old, new in
                       ((self._period, p), (self._available, a), (self._value, v)))
        order = np.lexsort((np.arange(p.size), a, p))           # by period, then availability, then arrival
        self._period[series], self._available[series], self._value[series] = p[order], a[order], v[order]
        p, a = self._period[series], self._available[series]
        # the fast path: one value per period, and availability never runs backwards
        self._simple[series] = bool(p.size == 0 or ((np.diff(p) > np.timedelta64(0, "D")).all()
                                                    and (np.diff(a) >= np.timedelta64(0, "D")).all()))

    def names(self) -> list[str]:
        return sorted(self._period)

    def __contains__(self, series: str) -> bool:
        return series in self._period

    def span(self, series: str) -> tuple[date, date]:
        """First and last period of a series (dates only: no value is given away)."""
        p = self._period[series]
        return p[0].astype(object), p[-1].astype(object)

    def data_hash(self) -> str:
        h = hashlib.sha256()
        for name in self.names():
            p, a, v = self._period[name], self._available[name], self._value[name]
            order = np.lexsort((v, a, p))                       # insertion order does not matter
            h.update(json.dumps(name).encode("utf-8"))
            h.update(p[order].astype("int64").tobytes())
            h.update(a[order].astype("int64").tobytes())
            h.update(np.ascontiguousarray(v[order], dtype="<f8").tobytes())
        return h.hexdigest()

    # ---- private: only a Window may call these
    def _as_of(self, series: str, t: np.datetime64, start: np.datetime64, end: np.datetime64):
        """(periods, values, availabilities) known at the close of day ``t``, periods within ``[start, end]``."""
        if series not in self._period:
            raise PitError(f"unknown series {series}")
        p, a, v = self._period[series], self._available[series], self._value[series]
        lo = int(np.searchsorted(p, start, "left"))
        if self._simple[series]:
            hi = min(int(np.searchsorted(p, end, "right")), int(np.searchsorted(a, t, "right")))
            return p[lo:hi], v[lo:hi], a[lo:hi]
        hi = int(np.searchsorted(p, end, "right"))
        p, a, v = p[lo:hi], a[lo:hi], v[lo:hi]
        known = a <= t
        p, a, v = p[known], a[known], v[known]
        if p.size == 0:
            return p, v, a
        last = np.append(p[1:] != p[:-1], True)                 # the latest vintage of each period known at t
        return p[last], v[last], a[last]


@dataclass(frozen=True)
class Window:
    """Permission to read one domain's data over ``start..end``, granted by ``roles.check_read``. Everything
    the engine learns about data, it learns here."""
    _store: PitStore
    start: date
    end: date
    role: str
    domain: str
    caller: str

    def as_of(self, series: str, t, n: int | None = None) -> tuple[np.ndarray, np.ndarray]:
        """(periods, values) of ``series`` as known at the close of day ``t``: for each period in the window, the
        latest value available on or before ``t``. ``n`` keeps the last ``n`` periods."""
        p, v, _ = self._known(series, t)
        return (p, v) if n is None else (p[-n:], v[-n:])

    def as_of_with_availability(self, series: str, t) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """As ``as_of``, with the day each value became available (an event is traded when it is known)."""
        return self._known(series, t)

    def final(self, series: str) -> tuple[np.ndarray, np.ndarray]:
        """The window's values as known at its end: what the accounting marks positions with. A value that
        became available only after the window's end is not in it."""
        p, v, _ = self._known(series, self.end)
        return p, v

    def _known(self, series: str, t):
        t = min(_day(t), _day(self.end))                       # nothing after the window's end is ever known here
        return self._store._as_of(series, t, _day(self.start), _day(self.end))

    def data_hash(self) -> str:
        return self._store.data_hash()

    def has(self, series: str) -> bool:
        return series in self._store


class Reader:
    """The only way to data: a caller, a domain and a fence. ``window`` asks ``manhattan.roles.check_read``."""

    def __init__(self, store: PitStore, *, caller: str, domain: str, fence: roles.Fence, freeze: date | None = None,
                 holding: int = 0, token: roles.RunnerToken | None = None, window_id: str | None = None):
        self._store, self.caller, self.domain, self.fence = store, caller, domain, fence
        self._kw = dict(freeze=freeze, holding=holding, token=token, window_id=window_id)

    def window(self, start: date, end: date) -> Window:
        """A window in one role, or ``roles.RoleError``."""
        role = roles.check_read(self.caller, self.domain, start, end, self.fence, **self._kw)
        return Window(self._store, _day(start).astype(object), _day(end).astype(object), role, self.domain, self.caller)


def lags_from_spec(hypothesis_spec: dict) -> dict[str, int]:
    """Publication lags by source name, from a hypothesis spec's ``data_sources``."""
    out = {}
    for src in hypothesis_spec.get("data_sources", []):
        if not isinstance(src, dict) or "name" not in src or "publication_lag_days" not in src:
            raise PitError("every data source needs a name and publication_lag_days")
        out[src["name"]] = int(src["publication_lag_days"])
    return out
