"""Observation time, publication time and research availability (DESIGN.md section 5).

Three questions, three answers, never merged:

1. **When did the market produce the value?** ``observed_at_utc`` (the settlement or close). If the source does
   not say, the session date and the instrument's declared close stand in, and that is recorded as declared.
2. **When could anyone outside the exchange have had it?** The publication time: the vendor's own receipt time
   (``vendor_receipt`` sources), or the session close plus the source's declared delay (``declared_delay``).
3. **When could this project's research have used it?** The research availability time, derived as follows:

    vendor_receipt   available = published_at. The row was published then whether we downloaded it then or years
                     later; the receipt time is the vendor's, so the basis is ``vendor_timestamp`` (a declaration
                     by the vendor, not an authentication).
    declared_delay   nominal = session close + declared delay.
                       first seen by nominal + grace           -> available = max(nominal, first seen), basis
                                                                  ``first_seen``
                       nominal before the series' monitoring   -> available = nominal, basis ``backfill``,
                       start (history that existed before we      **reconstructed**
                       first captured this series)
                       otherwise (we saw it late)              -> available = first seen, basis ``late``,
                                                                  **reconstructed**

A revision (a second value for a key, in a later vintage) is available from its own publication or first-seen
time: never earlier than the vintage that carried it.

The **research clock** turns an availability time into an availability **day**: the first day at whose decision
time the value may be used. A value available after the decision time on day D is first usable on D + 1. That day
is what ``manhattan.engine.pit.PitStore`` stores as ``available``, so everything downstream (the ``Reader``, the
fence, the engine) is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .errors import MarketDataError
from .provenance import SourceDescriptor
from .schema import Instrument, Observation

VENDOR, FIRST_SEEN, BACKFILL, LATE = "vendor_timestamp", "first_seen", "backfill", "late"
RECONSTRUCTED_BASES = (BACKFILL, LATE)


@dataclass(frozen=True)
class ResearchClock:
    """The research decision time: ``decision_time`` local time in ``tz``, every calendar day."""
    tz: str
    decision_time: time

    def __post_init__(self):
        ZoneInfo(self.tz)
        if not isinstance(self.decision_time, time) or self.decision_time.tzinfo is not None:
            raise MarketDataError("decision_time is a local time without a zone")

    def available_day(self, t: datetime) -> date:
        if t.tzinfo is None:
            raise MarketDataError("availability times must carry a zone")
        local = t.astimezone(ZoneInfo(self.tz))
        if local.time().replace(tzinfo=None) <= self.decision_time:
            return local.date()
        return local.date() + timedelta(days=1)


@dataclass(frozen=True)
class Availability:
    observed_utc: datetime            # the observation time used (row's, or the declared close)
    observed_declared: bool           # True when the row did not carry one
    published_utc: datetime           # vendor receipt, or nominal close + declared delay
    available_utc: datetime           # research availability time
    basis: str                        # vendor_timestamp | first_seen | backfill | late

    @property
    def reconstructed(self) -> bool:
        return self.basis in RECONSTRUCTED_BASES


def availability(obs: Observation, inst: Instrument, src: SourceDescriptor,
                 monitoring_start: datetime | None = None) -> Availability:
    """Availability of one observation. ``monitoring_start``: the first time this project captured this series
    (source, instrument, contract, field): the earliest retrieval of a delivery holding any row of it. Defaults to
    the observation's own first-seen time."""
    if obs.source_id != src.source_id:
        raise MarketDataError(f"observation from {obs.source_id} judged with source {src.source_id}")
    observed = obs.observed_at_utc or inst.close_utc(obs.session_date)
    declared = obs.observed_at_utc is None
    seen = obs.first_seen_utc
    if src.timestamp_semantics == "vendor_receipt":
        if obs.published_at_utc is None:
            raise MarketDataError(f"{src.source_id} promises a vendor receipt time and a row has none")
        return Availability(observed, declared, obs.published_at_utc, obs.published_at_utc, VENDOR)
    if not src.availability_ready:
        raise MarketDataError(f"{src.source_id}: availability cannot be computed: " + "; ".join(src.provenance_gaps()))
    nominal = observed + timedelta(minutes=src.declared_delay_minutes)
    if obs.published_at_utc is not None:
        raise MarketDataError(f"{src.source_id} is declared_delay but a row carries a publication time")
    start = monitoring_start or seen
    if seen <= nominal + timedelta(minutes=src.grace_minutes):
        return Availability(observed, declared, nominal, max(nominal, seen), FIRST_SEEN)
    if nominal < start:
        return Availability(observed, declared, nominal, nominal, BACKFILL)
    return Availability(observed, declared, nominal, seen, LATE)
