"""The First Light data-access cap: nothing dated or published after 2019-12-31 can be loaded or read.

Defence in depth for hard rule 4 (no 2020+ returns outside a confirmatory test filed by Ethan). Manhattan's general
fence takes its exploration end from ``config/manhattan.yaml``; the S17 audit (B.8) showed that a later
``exploration.data_end`` there validates cleanly and turns 2021 reads into exploration reads, and that a runner with
a caller-supplied freeze date reads 2020+ dates in the forward role (C9). First Light must not depend on either.
So the cap here is:

* **a constant in code** (``DATA_END``), never read from configuration;
* **applied at ingestion**: a ``CappedStore`` refuses any value whose period *or* availability day is after
  ``DATA_END``. A value describing 2019-12-31 but published on 2020-01-03 (a weekly report, a revision) was not
  known in 2019 and is refused. Nothing after the cap is ever in memory;
* **applied at every read**: a ``CappedReader`` opens exploration-role reads only, through ``pit.Reader`` with a fence
  built here (exploration to ``DATA_END``, no reserve), and takes no freeze date and no runner token, so no read can
  be promoted to the forward or reserve role. A read ending after ``DATA_END`` raises ``CapError`` before the fence
  is even asked;
* **tamper-evident**: the reader refuses a store changed other than through ``CappedStore.add`` (its data hash is
  compared with the one recorded at the last capped addition);
* **strict about types**: only ``datetime.date`` (not ``datetime``, strings or numbers) or ``datetime64[D]`` arrays
  are accepted, so a time of day or a time zone can never move a value across the boundary.

Availability days are calendar days, a value being usable at that day's close (``manhattan.engine.pit``). The cap is
inclusive: 2019-12-31 is readable, 2020-01-01 is not.

Dormant: nothing imports this module, and it changes no existing behaviour. Registering First Light's attempts
(``check_declared_windows``) is for the bound path once owner decision D-10 is made.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from manhattan import roles
from manhattan.engine import pit

DATA_END = date(2019, 12, 31)          # hard rule 4's boundary; a constant, deliberately not configurable
_CAP64 = np.datetime64(DATA_END.isoformat(), "D")


class CapError(PermissionError):
    """A load or read would reach past the First Light cap (fail closed)."""


def as_day(value, what: str) -> date:
    """A calendar day, or ``CapError``. A ``datetime`` is refused (it is a ``date`` subclass with a time of day)."""
    if type(value) is not date:
        raise CapError(f"{what} must be a datetime.date, not {type(value).__name__} {value!r}")
    return value


def _days(values, what: str) -> np.ndarray:
    """Calendar days as ``datetime64[D]``: from ``date`` objects or a ``datetime64[D]`` array, nothing else."""
    if isinstance(values, np.ndarray) and values.dtype.kind == "M":
        if np.datetime_data(values.dtype) != ("D", 1):          # [3D] etc. would quantize 2020 days onto 2019
            raise CapError(f"{what} must be whole days (datetime64[D]), not {values.dtype}")
        out = values.astype("datetime64[D]")
    else:
        seq = list(values) if isinstance(values, (list, tuple)) else None
        if seq is None:
            raise CapError(f"{what} must be a list of datetime.date or a datetime64[D] array")
        for v in seq:
            as_day(v, what)
        out = np.array([v.isoformat() for v in seq], dtype="datetime64[D]")
    if np.isnat(out).any():
        raise CapError(f"{what} has a missing day")
    return out


def fence() -> roles.Fence:
    """First Light's fence: exploration to ``DATA_END``, no reserve window, reserve disabled. Built here, never
    read from ``config/manhattan.yaml``."""
    return roles.Fence(exploration_end=DATA_END, reserve={}, enabled=False)


class CappedStore:
    """A fresh ``pit.PitStore`` that only ever holds values with period and availability on or before ``DATA_END``."""

    def __init__(self, *, synthetic: bool):
        self._pit = pit.PitStore(synthetic=synthetic)
        self._hash = self._pit.data_hash()

    @property
    def store(self) -> pit.PitStore:
        """The underlying store (read it through ``reader``; anything added to it directly is detected there)."""
        return self._pit

    def add(self, series: str, periods, values, *, available=None, lag_days: int | None = None) -> None:
        """As ``PitStore.add``, but refuses the whole call if any value's period or availability day is after the
        cap. Nothing is added when it refuses."""
        p = _days(periods, f"{series}: periods")
        if (available is None) == (lag_days is None):
            raise CapError(f"{series}: give either an availability day for each value or a publication lag")
        if lag_days is not None:
            if isinstance(lag_days, bool) or not isinstance(lag_days, int) or lag_days < 0:
                raise CapError(f"{series}: lag_days must be a nonnegative whole number of days")
            a = p + np.timedelta64(lag_days, "D")
        else:
            a = _days(available, f"{series}: availability days")
            if a.shape != p.shape:
                raise CapError(f"{series}: one availability day per value")
        if p.size and (p.max() > _CAP64 or a.max() > _CAP64):
            late_p, late_a = int((p > _CAP64).sum()), int((a > _CAP64).sum())
            raise CapError(f"{series}: {late_p} value(s) dated and {late_a} value(s) published after "
                           f"{DATA_END.isoformat()}; First Light loads nothing after the cap")
        self._verify_unchanged()
        if lag_days is not None:
            self._pit.add(series, p, values, lag_days=lag_days)
        else:
            self._pit.add(series, p, values, available=a)
        self._hash = self._pit.data_hash()

    def _verify_unchanged(self) -> None:
        if self._pit.data_hash() != self._hash:
            raise CapError("the store was changed outside CappedStore.add: it may hold values after the cap")

    def reader(self, *, caller: str, domain: str) -> "CappedReader":
        return CappedReader(self, caller=caller, domain=domain)


class CappedReader:
    """Exploration-role reads of a ``CappedStore``, ending on or before ``DATA_END``. Takes no freeze date, runner
    token or attempt: no read here can be in the forward or reserve role."""

    def __init__(self, capped: CappedStore, *, caller: str, domain: str):
        if not isinstance(capped, CappedStore):
            raise CapError("a First Light reader reads a CappedStore")
        self._capped = capped
        self._reader = pit.Reader(capped.store, caller=caller, domain=domain, fence=fence())

    def window(self, start: date, end: date):
        """An exploration window ``[start, end]``, or ``CapError`` if it reaches past the cap (checked before the
        fence), or the fence's own refusal."""
        start, end = as_day(start, "start"), as_day(end, "end")
        if end > DATA_END or start > DATA_END:
            raise CapError(f"the read {start.isoformat()}..{end.isoformat()} reaches past "
                           f"{DATA_END.isoformat()}: refused")
        self._capped._verify_unchanged()
        w = self._reader.window(start, end)
        if w.role != roles.EXPLORATION:          # cannot happen with this fence; checked anyway (fail closed)
            raise CapError(f"a First Light read must be in the exploration role, not {w.role}")
        return w


def check_declared_windows(windows) -> None:
    """For First Light attempts on the bound path (after D-10): every declared window is exploration-role and ends
    on or before the cap. Accepts ``access.DeclaredWindow`` objects or anything with ``start``, ``end`` and
    ``role``."""
    windows = list(windows)
    if not windows:
        raise CapError("an attempt declares at least one window")
    for w in windows:
        start, end = as_day(getattr(w, "start", None), "window start"), as_day(getattr(w, "end", None), "window end")
        if getattr(w, "role", None) != roles.EXPLORATION:
            raise CapError(f"a First Light window is exploration-role, not {getattr(w, 'role', None)!r}")
        if end > DATA_END or start > DATA_END:
            raise CapError(f"a declared window {start.isoformat()}..{end.isoformat()} reaches past "
                           f"{DATA_END.isoformat()}")


__all__ = ["DATA_END", "CapError", "CappedStore", "CappedReader", "as_day", "check_declared_windows", "fence"]
