"""Analyst estimates with their publication and capture times; consensus rebuilt as of a moment, never taken from a
vendor's (possibly revised) consensus history.

    book = EstimateBook()
    book.add(Estimate("C1", "B07", "eps", period_end=date(2010, 12, 31), value=1.32, currency="USD",
                      published=..., captured=..., action="revise"))
    book.consensus("C1", "eps", date(2010, 12, 31), at=some_aware_datetime)

**Estimate vintage identity.** An estimate is one broker's number for one company, metric and fiscal period,
published at one time. A revision is a new estimate; nothing is overwritten. ``action`` records what the broker
did: ``initiate`` (coverage starts), ``revise``, ``reiterate`` (same number confirmed: it refreshes the estimate's
age), ``drop`` (coverage of that period or company stops: the broker leaves the consensus).

**Consensus at a moment** ``at`` (timezone-aware) uses, per broker, its latest estimate whose **effective time** is
at or before ``at``: the effective time is ``max(published, captured)`` when the vendor's capture time is known, so a
revision a vendor backfilled later — a "late revision" — is not in the consensus at ``at``. **An estimate without a
capture time is unverifiable (S8 R4):** its publication time may have been reconstructed by the vendor. It is still
usable for description, but every consensus it enters is flagged ``reconstructed`` and is never eligible as
historical evidence (``Consensus.evidence_eligible``); ``require_capture=True`` refuses it at the door. Estimates older than
``max_age_days`` are stale and left out. A vendor history without capture times can be refused outright
(``require_capture=True``): reconstructed consensus histories are a known source of look-ahead.

Outputs: mean, median, standard deviation (dispersion), the number of brokers and their ids. ``revisions`` counts up
and down revisions in a span and their breadth ``(up − down) / brokers``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np

from .errors import CurrencyError, EquityDataError, TemporalError
from .sessions import require_aware

ACTIONS = ("initiate", "revise", "reiterate", "drop")


@dataclass(frozen=True)
class Estimate:
    company_id: str
    broker_id: str
    metric: str
    period_end: date
    value: float | None                   # None only for a drop
    currency: str | None
    published: datetime
    captured: datetime | None = None
    action: str = "revise"

    def __post_init__(self):
        if self.action not in ACTIONS:
            raise EquityDataError(f"unknown estimate action {self.action!r}")
        require_aware(self.published, "estimate published time")
        if self.captured is not None:
            require_aware(self.captured, "estimate capture time")
            if self.captured < self.published:
                raise TemporalError(f"{self.company_id} {self.broker_id}: captured before it was published")
        if self.action != "drop" and (self.value is None or not np.isfinite(self.value)):
            raise EquityDataError(f"{self.company_id} {self.broker_id}: an estimate needs a finite value")

    def effective(self) -> datetime:
        return max(self.published, self.captured) if self.captured is not None else self.published


@dataclass(frozen=True)
class Consensus:
    company_id: str
    metric: str
    period_end: date
    at: datetime
    n: int
    mean: float
    median: float
    std: float
    brokers: tuple
    currency: str | None
    reconstructed: bool = False          # a contributing estimate has no vendor capture time (S8 R4)

    @property
    def evidence_eligible(self) -> bool:
        """A consensus with an estimate of unverifiable timing can never be historical evidence."""
        return not self.reconstructed


class EstimateBook:
    def __init__(self, *, max_age_days: int = 120, require_capture: bool = False):
        self.max_age = timedelta(days=max_age_days)
        self.require_capture = require_capture
        self._est: dict[tuple, list[Estimate]] = {}

    def add(self, e: Estimate) -> None:
        if self.require_capture and e.captured is None:
            raise TemporalError(f"{e.company_id} {e.broker_id}: no capture time (the history may be reconstructed)")
        lst = self._est.setdefault((e.company_id, e.metric, e.period_end), [])
        for o in lst:
            if o.broker_id == e.broker_id and o.published == e.published and o != e:
                raise EquityDataError(f"{e.company_id} {e.broker_id}: two different estimates published at the same "
                                      "time")
        lst.append(e)

    def _latest_by_broker(self, company_id, metric, period_end, at: datetime) -> dict[str, Estimate]:
        require_aware(at, "consensus time")
        latest: dict[str, Estimate] = {}
        for e in self._est.get((company_id, metric, period_end), []):
            if e.effective() > at:
                continue
            cur = latest.get(e.broker_id)
            if cur is None or (e.effective(), e.published) > (cur.effective(), cur.published):
                latest[e.broker_id] = e
        return latest

    def consensus(self, company_id: str, metric: str, period_end: date, at: datetime) -> Consensus | None:
        latest = self._latest_by_broker(company_id, metric, period_end, at)
        live = [e for e in latest.values() if e.action != "drop" and at - e.effective() <= self.max_age]
        if not live:
            return None
        curs = {e.currency for e in live}
        if len(curs) > 1:
            raise CurrencyError(f"{company_id} {metric}: estimates in several currencies {sorted(map(str, curs))}")
        v = np.array([e.value for e in live], dtype=float)
        return Consensus(company_id, metric, period_end, at, int(v.size), float(v.mean()), float(np.median(v)),
                         float(v.std(ddof=1)) if v.size > 1 else 0.0, tuple(sorted(e.broker_id for e in live)),
                         curs.pop(), reconstructed=any(e.captured is None for e in live))

    @property
    def reconstructed(self) -> bool:
        """True when any estimate in the book lacks a vendor capture time: its history may be backfilled."""
        return any(e.captured is None for lst in self._est.values() for e in lst)

    def revisions(self, company_id: str, metric: str, period_end: date, start: datetime, end: datetime) -> dict:
        """Up and down revisions with effective time in ``(start, end]``, against each broker's estimate in force
        just before; breadth ``(up − down) / brokers live at end``."""
        require_aware(start, "revision window start")
        require_aware(end, "revision window end")
        if end <= start:
            raise TemporalError("a revision window ends after it starts")
        ests = sorted(self._est.get((company_id, metric, period_end), []), key=lambda e: (e.effective(), e.published))
        prior: dict[str, float] = {}
        up = down = 0
        for e in ests:
            if e.effective() > end:
                break
            if e.action == "drop":
                prior.pop(e.broker_id, None)
                continue
            if e.effective() > start and e.broker_id in prior and e.action == "revise":
                up += e.value > prior[e.broker_id]
                down += e.value < prior[e.broker_id]
            prior[e.broker_id] = e.value
        c = self.consensus(company_id, metric, period_end, end)
        n = c.n if c else 0
        return {"up": int(up), "down": int(down), "brokers": n,
                "breadth": float((up - down) / n) if n else float("nan")}

    def coverage(self, company_id: str, at: datetime) -> tuple:
        """Brokers with a live (not dropped, not stale) estimate of any metric and period at ``at``."""
        out = set()
        for (c, m, p) in self._est:
            if c != company_id:
                continue
            for b, e in self._latest_by_broker(c, m, p, at).items():
                if e.action != "drop" and at - e.effective() <= self.max_age:
                    out.add(b)
        return tuple(sorted(out))
