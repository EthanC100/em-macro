"""Exchange sessions and the mapping of a public timestamp to the first close at which it may be used.

    cal = MarketCalendar.synthetic("XNYS-SYN", date(2010, 1, 1), date(2012, 12, 31), holidays=[...])
    cal.usable_close(public_time)               # the session whose close may first act on the information

**Sessions are listed, never inferred.** A calendar is an explicit list of sessions, each with an open and a close
as timezone-aware datetimes. A weekday that is not listed is a closure (holiday, emergency closure); a session can
be shortened (half day). ``synthetic`` builds weekday sessions minus the given closures, for tests only: a real
calendar must come from a declared source (``manhattan.equities.sources``).

**Timestamps must be timezone-aware.** A naive datetime is refused: "16:05" means nothing without a zone, and a
release mislabelled by a few hours moves an announcement across a close.

**Conservative usability (default).** Information made public at ``ts`` may first be acted on at the close of the
first session whose **open** is at or after ``ts`` (``policy="next_open"``). A release before the open is usable at
that day's close; one during a session or after the close is usable at the next session's close; one on a weekend
or holiday is usable at the next session's close. The less conservative ``policy="same_close"`` lets a release be
used at the close of the session in progress if it was public at least ``buffer_minutes`` before that close. The
Manhattan engine then trades a decision at the next close (``lag = 1``), so with the default policy an after-market
release is traded two closes later.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone  # noqa: F401

from .errors import TemporalError

POLICIES = ("next_open", "same_close")


def require_aware(ts: datetime, what: str = "timestamp") -> datetime:
    """``ts`` if it is a timezone-aware datetime; ``TemporalError`` otherwise."""
    if not isinstance(ts, datetime):
        raise TemporalError(f"{what} must be a datetime, not {type(ts).__name__}")
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise TemporalError(f"{what} is naive: a timestamp needs a time zone")
    return ts


def _zone(name: str):
    """The IANA zone ``name``. Without a time-zone database this fails closed: a fixed offset would put every
    summer-time release an hour off and move releases across the open or the close."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        raise TemporalError(f"time zone {name!r} is unavailable (no tz database); refusing a fixed-offset "
                            "substitute") from None


@dataclass(frozen=True)
class Session:
    day: date
    open: datetime
    close: datetime

    def __post_init__(self):
        require_aware(self.open, "session open")
        require_aware(self.close, "session close")
        if not self.open < self.close:
            raise TemporalError(f"session {self.day}: the open must precede the close")


class MarketCalendar:
    """An explicit, ordered list of sessions of one exchange."""

    def __init__(self, name: str, sessions):
        sessions = sorted(sessions, key=lambda s: s.day)
        days = [s.day for s in sessions]
        if len(set(days)) != len(days):
            raise TemporalError(f"{name}: a day appears twice")
        for a, b in zip(sessions, sessions[1:]):
            if not a.close < b.open:
                raise TemporalError(f"{name}: sessions {a.day} and {b.day} overlap")
        self.name = name
        self._sessions = tuple(sessions)
        self._days = tuple(days)
        self._opens = tuple(s.open for s in sessions)
        self._closes = tuple(s.close for s in sessions)
        self._pos = {d: i for i, d in enumerate(days)}

    @classmethod
    def synthetic(cls, name: str, start: date, end: date, *, holidays=(), half_days=(), tz: str = "America/New_York",
                  open_at: time = time(9, 30), close_at: time = time(16, 0), half_close: time = time(13, 0)):
        """Weekdays from ``start`` to ``end`` without ``holidays``; ``half_days`` close at ``half_close``.
        For synthetic tests only."""
        zone = _zone(tz)
        hol, half = set(holidays), set(half_days)
        out, d = [], start
        while d <= end:
            if d.weekday() < 5 and d not in hol:
                c = half_close if d in half else close_at
                out.append(Session(d, datetime.combine(d, open_at, zone), datetime.combine(d, c, zone)))
            d += timedelta(days=1)
        return cls(name, out)

    # ---- sessions
    @property
    def tz(self):
        """The exchange's time zone (that of its first session)."""
        if not self._sessions:
            raise TemporalError(f"{self.name}: an empty calendar has no time zone")
        return self._sessions[0].open.tzinfo

    @property
    def days(self) -> tuple:
        return self._days

    def is_session(self, day: date) -> bool:
        return day in self._pos

    def session(self, day: date) -> Session:
        try:
            return self._sessions[self._pos[day]]
        except KeyError:
            raise TemporalError(f"{self.name}: {day} is not a session") from None

    def sessions_between(self, start: date, end: date) -> tuple:
        """Session days ``d`` with ``start <= d <= end``."""
        return self._days[bisect_left(self._days, start):bisect_right(self._days, end)]

    def next_session(self, day: date) -> date:
        """The first session strictly after ``day``."""
        i = bisect_right(self._days, day)
        if i >= len(self._days):
            raise TemporalError(f"{self.name}: no session after {day}")
        return self._days[i]

    def previous_session(self, day: date) -> date:
        """The last session strictly before ``day``."""
        i = bisect_left(self._days, day)
        if i == 0:
            raise TemporalError(f"{self.name}: no session before {day}")
        return self._days[i - 1]

    def session_on_or_before(self, day: date) -> date:
        i = bisect_right(self._days, day)
        if i == 0:
            raise TemporalError(f"{self.name}: no session on or before {day}")
        return self._days[i - 1]

    def offset(self, day: date, n: int) -> date:
        """The session ``n`` sessions after (``n > 0``) or before (``n < 0``) session ``day``."""
        i = self._pos.get(day)
        if i is None:
            raise TemporalError(f"{self.name}: {day} is not a session")
        j = i + n
        if not 0 <= j < len(self._days):
            raise TemporalError(f"{self.name}: offset {n} from {day} leaves the calendar")
        return self._days[j]

    def count_between(self, a: date, b: date) -> int:
        """Number of sessions ``d`` with ``a < d <= b``."""
        return bisect_right(self._days, b) - bisect_right(self._days, a)

    # ---- usability of information
    def usable_close(self, ts: datetime, *, policy: str = "next_open", buffer_minutes: int = 15) -> date:
        """The session at whose close information public at ``ts`` may first be used (see the module docstring)."""
        require_aware(ts)
        if policy not in POLICIES:
            raise TemporalError(f"unknown usability policy {policy!r}; one of {POLICIES}")
        if policy == "next_open":
            i = bisect_left(self._opens, ts)                # first session with open >= ts
        else:
            i = bisect_left(self._closes, ts + timedelta(minutes=buffer_minutes))   # first close >= ts + buffer
        if i >= len(self._days):
            raise TemporalError(f"{self.name}: {ts.isoformat()} is after the last session")
        return self._days[i]

    def close_of(self, day: date) -> datetime:
        return self.session(day).close

    def known_by_close(self, ts: datetime, day: date, *, policy: str = "next_open", buffer_minutes: int = 15) -> bool:
        """Whether information public at ``ts`` may be used at the close of session ``day``."""
        return self.usable_close(ts, policy=policy, buffer_minutes=buffer_minutes) <= day


def utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    """A UTC timestamp (a helper for fixtures)."""
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)
