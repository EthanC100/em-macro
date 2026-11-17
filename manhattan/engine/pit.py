"""Point-in-time data: every value knows the period it describes and the day it became available.

    store.add("fx_spot", periods, values, lag_days=1)          # published the next calendar day
    reader = Reader(store, caller="session", domain="fx_daily", fence=fence)
    window = reader.window(date(2005, 1, 3), date(2019, 12, 31))  # manhattan.roles.check_read decides
    window.as_of("fx_spot", day)                                # what was known at the end of that day

**Two dates per value.** ``period`` is the day (or the last day of the month, quarter ...) the value is about.
``available`` is the first day at whose close the value may be used for a decision. A value is never returned by
a read as of an earlier day. A **revision** is a second value for the same period with a later ``available``: it
shows from that day on, and a read as of an earlier day still returns the earlier value. Availability is given
explicitly, or by the low-level daily lag API. Source-aware ingestion uses ``add_source``;
``lags_from_spec`` accepts only explicit daily observation-date lag contracts. Non-daily
releases need availability per vintage; a value with neither is refused.

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
import re
from dataclasses import dataclass
from datetime import date, datetime, time

import numpy as np

from manhattan import roles
from manhattan.availability import AvailabilityError, sources_from_spec, validate_source

DAY = np.timedelta64(1, "D")


class PitError(ValueError):
    """Data that cannot be stored or read point in time."""


def _days(x) -> np.ndarray:
    """Daily dates only: never silently round a release/query timestamp down."""
    def check_unit(dtype):
        unit, step = np.datetime_data(dtype)
        units = {"D": 1, "h": 24, "m": 1440, "s": 86400, "ms": 86400000,
                 "us": 86400000000, "ns": 86400000000000, "ps": 86400000000000000,
                 "fs": 86400000000000000000, "as": 86400000000000000000000}
        if unit not in units or step > units[unit]:
            raise PitError("numpy dates require day precision or finer, not period or generic units")

    try:
        # Check elements before NumPy can promote mixed month/day scalars to days.
        for value in np.asarray(x, dtype=object).flat:
            if isinstance(value, np.datetime64):
                check_unit(value.dtype)
        raw = np.asarray(x)
        if raw.dtype.kind == "M":
            check_unit(raw.dtype)
            if np.isnat(raw).any():
                raise PitError("a daily date is missing")
            result = raw.astype("datetime64[D]")
            if (raw != result).any():
                raise PitError("a daily date is missing or contains intraday precision")
            return result
        for value in raw.flat:
            if isinstance(value, np.datetime64):
                if np.isnat(value) or value != value.astype("datetime64[D]"):
                    raise PitError("a daily date is missing or contains intraday precision")
            elif isinstance(value, datetime):
                if value.tzinfo is not None or value.time() != time.min:
                    raise PitError("map timestamps to availability days explicitly")
            elif isinstance(value, date):
                pass
            elif not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise PitError("a daily date is missing or requires explicit timestamp mapping")
        result = np.asarray(x, dtype="datetime64[D]")
        if np.isnat(result).any():
            raise PitError("a daily date is missing")
        return result
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, PitError):
            raise
        raise PitError("invalid daily date") from None


def _day(x) -> np.datetime64:
    result = _days(x)
    if result.ndim != 0:
        raise PitError("a query needs one daily date")
    return result[()]


def _lag(value) -> int:
    try:
        if isinstance(value, (bool, np.bool_, str)) or int(value) != value or value < 0:
            raise ValueError
        return int(value)
    except (TypeError, ValueError, OverflowError):
        raise PitError("a publication lag is a whole number of days, 0 or more") from None


class PitStore:
    """Values by series, each with its period and its availability day. Append-only: a value is never changed
    or removed; a correction is a revision with its own availability."""

    def __init__(self):
        self._period: dict[str, np.ndarray] = {}
        self._available: dict[str, np.ndarray] = {}
        self._value: dict[str, np.ndarray] = {}
        self._simple: dict[str, bool] = {}
        self._reconstructed = False

    def add(self, series: str, periods, values, *, available=None, lag_days: int | None = None,
            reconstructed: bool = False) -> None:
        """Add values of ``series``. Give ``available`` (one day per value) or ``lag_days`` (calendar days after
        the period; 0 means usable at that day's close)."""
        if not isinstance(reconstructed, bool):
            raise PitError("reconstructed must be a boolean")
        p = np.atleast_1d(_days(periods))
        v = np.atleast_1d(np.asarray(values, dtype=float))
        if p.shape != v.shape or p.ndim != 1:
            raise PitError(f"{series}: periods and values must be two lists of the same length")
        if (available is None) == (lag_days is None):
            raise PitError(f"{series}: give either an availability day for each value or a publication lag, not both or neither")
        if lag_days is not None:
            a = p + _lag(lag_days) * DAY
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
        p, a, v = p[order], a[order], v[order]
        same = (p[1:] == p[:-1]) & (a[1:] == a[:-1])
        if (same & (v[1:].view(np.uint64) != v[:-1].view(np.uint64))).any():
            raise PitError(f"{series}: conflicting values share one period and availability day")
        unique = np.r_[True, ~same] if p.size else np.array([], dtype=bool)
        self._period[series], self._available[series], self._value[series] = p[unique], a[unique], v[unique]
        self._reconstructed |= reconstructed
        p, a = self._period[series], self._available[series]
        # the fast path: one value per period, and availability never runs backwards
        self._simple[series] = bool(p.size == 0 or ((np.diff(p) > np.timedelta64(0, "D")).all()
                                                    and (np.diff(a) >= np.timedelta64(0, "D")).all()))

    def require_historical_evidence(self) -> None:
        """Reject reconstructed inputs, including warm-up dependencies.

        This necessary check does not authenticate release history or certify data.
        Conservative store-wide taint cannot be removed by adding later rows.
        """
        if self._reconstructed:
            raise PitError("reconstructed/backfilled data cannot be confirmatory historical evidence")

    def add_source(self, source: dict, periods, values, *, available=None) -> None:
        """Ingest an explicit source contract; non-daily availability is per vintage.

        Release calendars must be resolved externally, including revisions and
        irregular schedules. Conservative assumptions require an owner reference;
        their rows are reconstructed, never authenticated historical evidence.
        """
        try:
            validate_source(source)
        except AvailabilityError as exc:
            raise PitError(str(exc)) from None
        kind = source["availability"]["kind"]
        if kind == "daily_lag":
            if available is not None:
                raise PitError("explicit availability conflicts with daily_lag")
            self.add(source["name"], periods, values, lag_days=source["publication_lag_days"])
        else:
            if available is None:
                raise PitError("per-vintage availability days are required; period labels are not release dates")
            self.add(source["name"], periods, values, available=available, reconstructed=kind == "conservative")

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
            h.update(p[order].astype("<i8").tobytes())
            h.update(a[order].astype("<i8").tobytes())
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
            return p[lo:hi].copy(), v[lo:hi].copy(), a[lo:hi].copy()
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
        if n is not None and (isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 0):
            raise PitError("n must be a nonnegative whole number of periods")
        p, v, _ = self._known(series, t)
        if n == 0:
            return p[:0], v[:0]
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

    @property
    def reconstructed(self) -> bool:
        return self._store._reconstructed

    def require_historical_evidence(self) -> None:
        self._store.require_historical_evidence()

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
    """Only explicit daily lag contracts can be represented by this legacy API.

    Non-daily releases/calendars/assumptions require add_source with per-vintage
    availability; never silently substitute period-start plus a constant lag.
    """
    try:
        sources = sources_from_spec(hypothesis_spec)
    except AvailabilityError as exc:
        raise PitError(str(exc)) from None
    if any(src["availability"]["kind"] != "daily_lag" for src in sources.values()):
        raise PitError("source requires per-vintage availability, not a fixed lag")
    return {name: src["publication_lag_days"] for name, src in sources.items()}
