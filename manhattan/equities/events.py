"""Earnings-release timing and surprise primitives.

**Scheduled is not released.** A company's announced date (``scheduled``, known from ``schedule_known``) tells when a
release is expected; only ``released`` (a timezone-aware time stamp) tells when the numbers became public. A
surprise needs the release time; a scheduled date alone raises ``TemporalError``. The scheduled date may be used as
a calendar feature ("a release is due within five sessions") only from the day the schedule itself was public.

**Session label and time stamp must agree.** ``time_of_day`` is ``before_open``, ``during``, ``after_close`` or
``unknown``. A label that contradicts the time stamp (an "after close" release stamped 08:00) is refused: one of
the two is wrong and the conservative choice cannot be made.

**Conservative usability** (``manhattan.equities.sessions``, policy ``next_open``): a release before the open is
usable at that day's close; one during the session or after the close at the next session's close; a release with a
date but ``unknown`` time of day is treated as after the close.

**Surprise** compares the reported value with the consensus **strictly before** the release (the consensus at
``released − 1 second``), scaled by the dispersion of estimates with a floor, or by price. Estimates published at
or after the release (post-release revisions) cannot enter it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .errors import TemporalError
from .estimates import EstimateBook
from .sessions import MarketCalendar, require_aware

TIMES_OF_DAY = ("before_open", "during", "after_close", "unknown")


@dataclass(frozen=True)
class EarningsEvent:
    company_id: str
    period_end: date
    scheduled: date | None = None
    schedule_known: date | None = None
    released: datetime | None = None
    time_of_day: str = "unknown"

    def __post_init__(self):
        if self.time_of_day not in TIMES_OF_DAY:
            raise TemporalError(f"{self.company_id}: unknown time of day {self.time_of_day!r}")
        if self.scheduled is not None and self.schedule_known is None:
            raise TemporalError(f"{self.company_id}: a scheduled date needs the date the schedule became public")
        if self.schedule_known is not None and self.scheduled is not None and self.schedule_known > self.scheduled:
            raise TemporalError(f"{self.company_id}: the schedule became public after the scheduled date")
        if self.released is not None:
            require_aware(self.released, f"{self.company_id} release time")
            if self.released.date() < self.period_end:
                raise TemporalError(f"{self.company_id}: released before the fiscal period ended")


def _local(ts: datetime, calendar: MarketCalendar) -> datetime:
    return ts.astimezone(calendar.tz)


def check_label(event: EarningsEvent, calendar: MarketCalendar) -> None:
    """Refuse a time-of-day label that contradicts the release time stamp."""
    if event.released is None or event.time_of_day == "unknown":
        return
    day = _local(event.released, calendar).date()
    if not calendar.is_session(day):
        if event.time_of_day == "during":
            raise TemporalError(f"{event.company_id}: labelled 'during' a session on {day}, which is not a session")
        return
    s = calendar.session(day)
    actual = "before_open" if event.released < s.open else ("during" if event.released < s.close else "after_close")
    if actual != event.time_of_day:
        raise TemporalError(f"{event.company_id}: labelled {event.time_of_day!r} but stamped "
                            f"{event.released.isoformat()} ({actual}); resolve before use")


def usable_close(event: EarningsEvent, calendar: MarketCalendar) -> date:
    """The first close at which the release may be acted on (conservative)."""
    if event.released is None:
        raise TemporalError(f"{event.company_id} {event.period_end}: no release time; a scheduled date is not a "
                            "release")
    check_label(event, calendar)
    ts = event.released
    if event.time_of_day == "unknown":                    # an unknown time of day: as if after that day's close
        local = _local(ts, calendar)
        ts = datetime.combine(local.date(), time(23, 59), calendar.tz)
    return calendar.usable_close(ts, policy="next_open")


def scheduled_known(event: EarningsEvent, as_of: date) -> date | None:
    """The scheduled date, if the schedule was public by ``as_of``; else None."""
    if event.scheduled is None or event.schedule_known is None or event.schedule_known > as_of:
        return None
    return event.scheduled


def surprise(event: EarningsEvent, actual: float, book: EstimateBook, metric: str, *, scale: str = "dispersion",
             price: float | None = None, floor: float = 0.01) -> dict:
    """Standardised surprise against the consensus just before the release."""
    if event.released is None:
        raise TemporalError(f"{event.company_id}: a surprise needs the release time, not the scheduled date")
    before = event.released - timedelta(seconds=1)
    c = book.consensus(event.company_id, metric, event.period_end, before)
    if c is None:
        return {"surprise": float("nan"), "n": 0, "consensus": float("nan"), "at": before}
    raw = actual - c.mean
    if scale == "dispersion":
        den = max(c.std, floor * max(abs(c.mean), 1e-12))
    elif scale == "price":
        if price is None or price <= 0:
            raise TemporalError("a price-scaled surprise needs the last close known before the release")
        den = price
    else:
        raise ValueError("scale is 'dispersion' or 'price'")
    return {"surprise": float(raw / den), "n": c.n, "consensus": c.mean, "dispersion": c.std, "at": before}
