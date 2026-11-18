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

**Sealed windows (Phase 4B, docs/manhattan/BINDING_ACCOUNTING.md).** A ``Window`` cannot be constructed or
copied: its fields are bound by a seal that only this module mints, for a ``Reader`` (exploration, after
``check_read``) or for a registered ``manhattan.access.AttemptContext`` (reserve and forward roles always; exploration
optionally). A protected window also refuses reads once its store has changed since authorization. A synthetic store
(``PitStore(synthetic=True)``) may be opened under any role label for operational diagnostics only; such a window can
never produce an evaluation record. This is a structural guard within Manhattan code, not a sandbox: see the trust
boundary in BINDING_ACCOUNTING.md section 1.

**Data hash.** ``PitStore.data_hash()`` is the SHA-256 of the canonical form of everything in the store (series
names, periods, availabilities, values, in a fixed order). It is the ``data_hash`` of a ledger record.

Daily resolution. Minute data are out of scope here (ARCHITECTURE section 6.4).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import weakref
from dataclasses import dataclass, field
from datetime import date, datetime, time

import numpy as np

from manhattan import roles
from manhattan.availability import AvailabilityError, sources_from_spec, validate_source

DAY = np.timedelta64(1, "D")
PROTECTED_ROLES = (roles.RESERVE, roles.FORWARD)
PURPOSES = ("exploration", "evaluation", "forward_observation", "diagnostic")
_SEAL_KEY = secrets.token_bytes(32)          # per process; never persisted, logged or exported


class PitError(ValueError):
    """Data that cannot be stored or read point in time."""


class AccessError(roles.RoleError):
    """A window was asked for without the authorization its role and purpose need (Phase 4B)."""


class _Meter:
    """Counts reads through the windows of one authorization, so a terminal can say whether data were read, and
    holds the authorization's liveness check: a bound window reads only while ``alive()`` says its attempt is
    registered and active (set by ``manhattan.access.AttemptContext``)."""
    __slots__ = ("reads", "alive")

    def __init__(self):
        self.reads = 0
        self.alive = None


# Every window this process minted, by object identity: its sealed fields and the minting process. A read is
# allowed only through a window found here unchanged, so copies, deep copies, unpickled objects, windows altered
# with object.__setattr__ and windows inherited by a forked child are refused (Phase 4B correction, S7 H3).
_GRANTS: dict[int, tuple] = {}


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

    def __init__(self, *, synthetic: bool = False):
        if not isinstance(synthetic, bool):
            raise PitError("synthetic must be a boolean")
        self._period: dict[str, np.ndarray] = {}
        self._available: dict[str, np.ndarray] = {}
        self._value: dict[str, np.ndarray] = {}
        self._simple: dict[str, bool] = {}
        self._reconstructed = False
        self._version = 0                       # bumped by every add: a protected window refuses a changed store
        self._synthetic = synthetic             # declared by the code that builds the store; diagnostics only

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
        self._version += 1
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


def _seal(store, start, end, role, domain, caller, purpose, attempt_id, window_id, signal_start, version,
          meter) -> str:
    msg = json.dumps([id(store), str(start), str(end), role, domain, caller, purpose, attempt_id, window_id,
                      None if signal_start is None else str(signal_start), version, id(meter)],
                     separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, msg, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Window:
    """Permission to read one domain's data over ``start..end``, granted by ``roles.check_read`` (exploration) or by
    a registered attempt (``manhattan.access``). Everything the engine learns about data, it learns here.

    Only ``Reader.window`` and ``manhattan.access.AttemptContext`` open one; direct construction and
    ``dataclasses.replace`` raise ``AccessError``. ``purpose``: ``exploration`` (open), ``evaluation`` (a declared
    window of a registered attempt), ``forward_observation`` (the runner's R-1 adapter: warm-up from ``start``,
    observations from ``signal_start``), ``diagnostic`` (synthetic stores only, never evidence)."""
    _store: PitStore
    start: date
    end: date
    role: str
    domain: str
    caller: str
    purpose: str = "exploration"
    attempt_id: str | None = None
    window_id: str | None = None
    signal_start: date | None = None
    _version: int = field(default=-1, repr=False)
    _meter: _Meter | None = field(default=None, repr=False, compare=False)
    _seal: str | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        expected = _seal(self._store, self.start, self.end, self.role, self.domain, self.caller, self.purpose,
                         self.attempt_id, self.window_id, self.signal_start, self._version, self._meter)
        if not isinstance(self._seal, str) or not hmac.compare_digest(self._seal, expected):
            raise AccessError("a Window is opened by a Reader or a registered attempt; it is never constructed "
                              "or copied directly")

    # A window is a capability of this process: it is never copied, deep-copied or serialized.
    def __copy__(self):
        raise AccessError("a Window cannot be copied; open another through its Reader or attempt")

    def __deepcopy__(self, memo):
        raise AccessError("a Window cannot be copied; open another through its Reader or attempt")

    def __reduce_ex__(self, protocol):
        raise AccessError("a Window cannot be serialized or sent to another process")

    def __getstate__(self):
        raise AccessError("a Window cannot be serialized or sent to another process")

    def _fields(self) -> tuple:
        return (id(self._store), self.start, self.end, self.role, self.domain, self.caller, self.purpose,
                self.attempt_id, self.window_id, self.signal_start, self._version, id(self._meter), self._seal)

    @property
    def bound(self) -> bool:
        """Whether this window belongs to a registered attempt or carries a protected role (diagnostic windows on
        synthetic stores excepted)."""
        return self.attempt_id is not None or (self.role in PROTECTED_ROLES and self.purpose != "diagnostic")

    def _guard(self) -> None:
        """Checked at every read, not only when the window is opened: the window is the one minted here (not a
        copy, an unpickled or an altered object), in this process; and a bound window's store is unchanged and its
        attempt still registered and active."""
        grant = _GRANTS.get(id(self))
        if grant is None or grant[0] != self._fields() or grant[1] != os.getpid():
            raise AccessError("this window was not opened in this process as it now stands (copied, deserialized, "
                              "altered or inherited)")
        if self.bound:
            if self._store._version != self._version:
                raise PitError("the store changed after this window was authorized (data identity)")
            alive = self._meter.alive
            if alive is None or not alive():
                raise AccessError("the window's attempt is not registered and active (ended, failed or superseded), "
                                  "or the read is outside its one computation")

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
        self._guard()
        self._meter.reads += 1                                 # counted before any value can leave
        t = min(_day(t), _day(self.end))                       # nothing after the window's end is ever known here
        return self._store._as_of(series, t, _day(self.start), _day(self.end))

    @property
    def reads(self) -> int:
        return self._meter.reads

    @property
    def reconstructed(self) -> bool:
        return self._store._reconstructed

    def require_historical_evidence(self) -> None:
        self._store.require_historical_evidence()

    def data_hash(self) -> str:
        self._guard()
        return self._store.data_hash()

    def has(self, series: str) -> bool:
        self._guard()
        return series in self._store


def _open_window(store: PitStore, start, end, role: str, domain: str, caller: str, *, purpose: str,
                 attempt_id: str | None = None, window_id: str | None = None, signal_start=None,
                 meter: _Meter | None = None) -> Window:
    """Mint a sealed window. Private: callers are ``Reader`` and ``manhattan.access`` only (a static test pins
    this). It checks only the combination; the caller has already authorized the read."""
    if not isinstance(store, PitStore):
        raise AccessError("a window reads a PitStore")
    if role not in (roles.EXPLORATION, roles.RESERVE, roles.FORWARD):
        raise AccessError(f"unknown role {role}")
    if purpose not in PURPOSES:
        raise AccessError(f"unknown window purpose {purpose}")
    if purpose == "diagnostic":
        if store._synthetic is not True or attempt_id is not None:
            raise AccessError("a diagnostic window opens a synthetic store only, outside any attempt")
    elif purpose == "exploration":
        if role != roles.EXPLORATION or attempt_id is not None:
            raise AccessError("an open window is exploration-role and belongs to no attempt")
    else:
        if not isinstance(attempt_id, str) or re.fullmatch(r"[0-9a-f]{64}", attempt_id) is None:
            raise AccessError("an attempt window needs its registered attempt ID")
        if purpose == "forward_observation" and role != roles.FORWARD:
            raise AccessError("the forward-observation adapter opens forward-role windows only")
    s, e = _day(start).astype(object), _day(end).astype(object)
    if signal_start is not None:
        signal_start = _day(signal_start).astype(object)
    meter = meter or _Meter()
    seal = _seal(store, s, e, role, domain, caller, purpose, attempt_id, window_id, signal_start, store._version,
                 meter)
    w = Window(store, s, e, role, domain, caller, purpose, attempt_id, window_id, signal_start, store._version,
               meter, seal)
    key = id(w)
    _GRANTS[key] = (w._fields(), os.getpid())
    weakref.finalize(w, _GRANTS.pop, key, None)
    return w


def diagnostic_window(store: PitStore, start, end, *, role: str, domain: str, caller: str = roles.RUNNER) -> Window:
    """An operational diagnostic (capacity, timing) on a synthetic store, under any role label. Never evidence:
    ``engine.evaluate`` and the runner's observation path refuse it."""
    if role not in (roles.EXPLORATION, roles.RESERVE, roles.FORWARD):
        raise AccessError(f"unknown role {role}")
    return _open_window(store, start, end, role, domain, caller, purpose="diagnostic")


class Reader:
    """The only open way to data: a caller, a domain and a fence. ``window`` asks ``manhattan.roles.check_read``.

    Reserve and forward reads also need ``attempt``, a registered ``manhattan.access.AttemptContext`` that declared
    exactly this window; without one they raise ``AccessError`` even when ``check_read`` allows them. An exploration
    read with an attempt is bound to it."""

    def __init__(self, store: PitStore, *, caller: str, domain: str, fence: roles.Fence, freeze: date | None = None,
                 holding: int = 0, token: roles.RunnerToken | None = None, window_id: str | None = None,
                 attempt=None):
        self._store, self.caller, self.domain, self.fence = store, caller, domain, fence
        self._kw = dict(freeze=freeze, holding=holding, token=token, window_id=window_id)
        self._attempt = attempt

    def window(self, start: date, end: date) -> Window:
        """A window in one role, or ``roles.RoleError`` (``AccessError`` for a missing authorization)."""
        role = roles.check_read(self.caller, self.domain, start, end, self.fence, **self._kw)
        if self._attempt is None:
            if role in PROTECTED_ROLES:
                raise AccessError(f"a {role} read needs a registered attempt (manhattan.access.AttemptContext)")
            return _open_window(self._store, start, end, role, self.domain, self.caller, purpose="exploration")
        return self._attempt._open_read(self, start, end, role)


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
