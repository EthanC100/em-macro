"""Decision timestamps: when an HTE position row is decided, and when PR #85 would execute it.

HTE positions have no timestamps. Row ``t`` is "the position held from the close of day ``t``, built only from data
through that close" (``manhattan/hte/templates.py``). The bridge gives each row an explicit decision time:

    decided_at(t) = close_t + publication_delay          (strictly after the settlement it reads is published)
    execution day = the lag-th trading day whose close is strictly after decided_at      (PR #85, account.py)

With ``0 < publication_delay < close_{t+1} − close_t`` the execution day is exactly ``t + lag``, which is the
row-based rule of the execution-realism adapter (#93). The clock **checks** that for every row and refuses a delay
that would reach the next close: the adapter would then size and read liquidity at a row the decision had not
reached. ``inputs_known_at`` is ``close_t`` plus the settlement publication delay (no later than the decision).

Closes are given per domain in UTC (a synthetic convention: HTE's calendar has no exchange). PR #85's own
``execution_index`` is the reference; a cross-check runs it on these timestamps when a PR #85 checkout is given.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import numpy as np

from .errors import BridgeError

DEFAULT_CLOSES = {"commodity": time(19, 30), "rates": time(20, 0), "fx": time(21, 0)}


def as_dates(dates) -> tuple:
    """HTE's ``datetime64[D]`` calendar (or dates) as a tuple of ``datetime.date``."""
    out = []
    for d in np.asarray(dates).ravel():
        if isinstance(d, np.datetime64):
            d = d.astype("datetime64[D]").astype(object)
        if not isinstance(d, date) or isinstance(d, datetime):
            raise BridgeError(f"calendar entries must be dates, not {d!r}")
        out.append(d)
    if any(b <= a for a, b in zip(out, out[1:])):
        raise BridgeError("the calendar must strictly increase")
    return tuple(out)


@dataclass(frozen=True)
class DecisionClock:
    closes_utc: dict = field(default_factory=lambda: dict(DEFAULT_CLOSES))
    settlement_publication: timedelta = timedelta(minutes=30)    # settlement known_at = close + this
    decision_delay: timedelta = timedelta(minutes=45)            # decided_at = close + this (>= publication)

    def __post_init__(self):
        if not (timedelta(0) < self.settlement_publication <= self.decision_delay):
            raise BridgeError("need 0 < settlement_publication <= decision_delay: a decision reads a published "
                              "settlement")
        for k, v in self.closes_utc.items():
            if not isinstance(v, time) or v.tzinfo is not None:
                raise BridgeError(f"close of {k!r} is a naive datetime.time read as UTC")

    def close_at(self, domain: str, d: date) -> datetime:
        if domain not in self.closes_utc:
            raise BridgeError(f"no close time for domain {domain!r}")
        return datetime.combine(d, self.closes_utc[domain], tzinfo=timezone.utc)

    def published_at(self, domain: str, d: date) -> datetime:
        return self.close_at(domain, d) + self.settlement_publication

    def decided_at(self, domain: str, d: date) -> datetime:
        return self.close_at(domain, d) + self.decision_delay

    def execution_rows(self, domain: str, dates, rows, lag: int) -> np.ndarray:
        """PR #85's rule on these timestamps, for decision ``rows``: the lag-th close strictly after
        ``decided_at``. Refuses a decision that reaches the next close; returns ``rows + lag`` (−1 past the end)."""
        days = as_dates(dates)
        closes = [self.close_at(domain, d) for d in days]
        out = np.full(len(rows), -1, dtype=np.int64)
        for j, t in enumerate(np.asarray(rows, dtype=np.int64)):
            dec = self.decided_at(domain, days[t])
            if dec <= closes[t]:
                raise BridgeError("a decision cannot be at or before the close whose settlement it reads")
            if t + 1 < len(days) and dec >= closes[t + 1]:
                raise BridgeError(f"decision of {days[t]} at {dec.isoformat()} reaches the next close "
                                  f"{closes[t + 1].isoformat()}: the row-based adapter would read later data")
            k = t + lag if lag > 0 else t        # lag 0 is the same-close convention (measurement only)
            out[j] = k if k < len(days) else -1
        return out

    def as_dict(self) -> dict:
        return {"closes_utc": {k: v.isoformat() for k, v in sorted(self.closes_utc.items())},
                "settlement_publication_s": int(self.settlement_publication.total_seconds()),
                "decision_delay_s": int(self.decision_delay.total_seconds())}
