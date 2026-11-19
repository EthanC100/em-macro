"""Bitemporal financial statements: what each value was, for which fiscal period, and from when it was known.

    store = FundamentalStore(calendar)
    store.add(Fact("C1", "revenue", period_end=date(2009, 3, 31), period_kind="quarter", value=410.0,
                   currency="USD", public_time=..., capture_time=..., vintage="original"))
    store.value("C1", "revenue", as_of=date(2009, 6, 1))           # latest period known at that close

**Two clocks.** ``period_end`` is the fiscal period a value describes; ``public_time`` (a filing's acceptance time,
timezone-aware) is when it became public. A vendor's ``capture_time`` is when the vendor recorded it; if it is
later than the public time (a backfilled history), the value is usable only from the capture (``availability``
``"capture_aware"``, the default) — or it is refused when ``require_capture=True``. The usable close is
``calendar.usable_close(max(public, capture))``.

**A value describing an earlier quarter is not thereby known.** The Q1 revenue of a company with a fiscal quarter
ending 31 March is unknown on 1 April; it becomes known at the close after its filing is accepted.

**Restatements are new records, never edits.** A restated value is a ``Fact`` with ``vintage="restated"`` and its
own public time. A query as of a date returns, per fiscal period, the latest vintage known by then
(``vintage="latest_known"``) or the first one (``vintage="original"``). A restatement published after the date is
invisible at the date.

**Capture provenance.** A fact without ``capture_time`` is usable from its public time, but nothing shows that the
vendor held it then: its history may have been rebuilt later. ``capture_known`` says which facts lack it, and the
export to the PIT store marks such series ``reconstructed`` (never confirmatory evidence). ``require_capture=True``
refuses them outright.

**Fiscal calendars differ.** Cross-sectional comparisons use "the latest period known at ``t``" for each company,
never a calendar-quarter label. ``ttm`` requires four consecutive fiscal quarters known at ``t``; ``growth``
compares two periods as both were known at ``t`` (one knowledge state, so a restatement cannot mix vintages).

**Currencies and units** travel with each value; combining two metrics in different currencies raises
``CurrencyError``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from .errors import CurrencyError, EquityDataError, TemporalError
from .sessions import MarketCalendar, require_aware

PERIOD_KINDS = ("quarter", "half", "annual")
VINTAGES = ("original", "restated", "amended")
QUERY_VINTAGES = ("latest_known", "original")


@dataclass(frozen=True)
class Fact:
    company_id: str
    metric: str
    period_end: date
    period_kind: str
    value: float
    currency: str | None                 # None for ratios and counts (shares, employees)
    public_time: datetime
    capture_time: datetime | None = None
    vintage: str = "original"
    source: str = ""
    basis: str = ""                      # accounting basis, e.g. "US-GAAP", "IFRS"
    unit: str = ""                       # e.g. "millions", "shares"

    def __post_init__(self):
        if self.period_kind not in PERIOD_KINDS:
            raise EquityDataError(f"{self.company_id} {self.metric}: unknown period kind {self.period_kind!r}")
        if self.vintage not in VINTAGES:
            raise EquityDataError(f"{self.company_id} {self.metric}: unknown vintage {self.vintage!r}")
        if not np.isfinite(self.value):
            raise EquityDataError(f"{self.company_id} {self.metric}: a fact is a finite number (omit missing ones)")
        require_aware(self.public_time, f"{self.company_id} {self.metric} public_time")
        if self.public_time.date() < self.period_end:
            raise TemporalError(f"{self.company_id} {self.metric} {self.period_end}: public before the period ended "
                                f"({self.public_time.isoformat()})")
        if self.capture_time is not None:
            require_aware(self.capture_time, f"{self.company_id} {self.metric} capture_time")
            if self.capture_time < self.public_time:
                raise TemporalError(f"{self.company_id} {self.metric} {self.period_end}: captured before it was "
                                    "public: one of the two time stamps is wrong")


@dataclass(frozen=True)
class Known:
    """A value as known at a date, with the record it came from."""
    period_end: date
    value: float
    currency: str | None
    usable_from: date
    fact: Fact


class FundamentalStore:
    def __init__(self, calendar: MarketCalendar, *, availability: str = "capture_aware",
                 require_capture: bool = False, policy: str = "next_open"):
        if availability not in ("capture_aware", "public_only"):
            raise EquityDataError("availability is 'capture_aware' or 'public_only'")
        self.calendar, self.availability, self.require_capture, self.policy = calendar, availability, \
            require_capture, policy
        self._facts: dict[tuple[str, str], list[Fact]] = {}

    def add(self, f: Fact) -> None:
        if self.require_capture and f.capture_time is None:
            raise TemporalError(f"{f.company_id} {f.metric}: no capture time, and this store requires one "
                                "(the history may have been backfilled)")
        facts = self._facts.setdefault((f.company_id, f.metric), [])
        for o in facts:
            same = o.period_end == f.period_end and o.period_kind == f.period_kind
            if same and o.public_time == f.public_time and o.value != f.value:
                raise EquityDataError(f"{f.company_id} {f.metric} {f.period_end}: two values published at the same "
                                      "time")
            if o.currency != f.currency and o.period_end == f.period_end:
                raise CurrencyError(f"{f.company_id} {f.metric} {f.period_end}: values in different currencies")
        if f.vintage == "original" and any(o.period_end == f.period_end and o.period_kind == f.period_kind
                                           and o.vintage == "original" for o in facts):
            raise EquityDataError(f"{f.company_id} {f.metric} {f.period_end} ({f.period_kind}): two originals; a "
                                  "later value is a restatement")
        facts.append(f)

    def usable_from(self, f: Fact) -> date:
        t = f.public_time
        if self.availability == "capture_aware" and f.capture_time is not None:
            t = max(t, f.capture_time)
        return self.calendar.usable_close(t, policy=self.policy)

    def known(self, company_id: str, metric: str, as_of: date, *, vintage: str = "latest_known",
              kind: str | None = None) -> list[Known]:
        """Per fiscal period (period end and kind), the value known at the close of ``as_of``, ordered by period end.
        An annual figure and a fourth-quarter figure ending on the same day are two periods, never one."""
        if vintage not in QUERY_VINTAGES:
            raise EquityDataError(f"vintage is one of {QUERY_VINTAGES}")
        best: dict[tuple, tuple] = {}
        for f in self._facts.get((company_id, metric), []):
            if kind is not None and f.period_kind != kind:
                continue
            u = self.usable_from(f)
            if u > as_of:
                continue
            key = (u, f.public_time, f.capture_time or f.public_time)
            cur = best.get((f.period_end, f.period_kind))
            if cur is None or (key > cur[0] if vintage == "latest_known" else key < cur[0]):
                best[(f.period_end, f.period_kind)] = (key, Known(f.period_end, f.value, f.currency, u, f))
        return [best[p][1] for p in sorted(best, key=lambda p: (p[0], PERIOD_KINDS.index(p[1])))]

    def value(self, company_id: str, metric: str, as_of: date, *, vintage: str = "latest_known",
              kind: str | None = None, max_age_days: int | None = None) -> Known | None:
        """The most recent fiscal period's value known at ``as_of`` (None if none, or older than ``max_age_days``
        measured from the period end)."""
        k = self.known(company_id, metric, as_of, vintage=vintage, kind=kind)
        if not k:
            return None
        last = k[-1]
        tied = [x for x in k if x.period_end == last.period_end]
        if len(tied) > 1:                       # an annual and a fourth quarter ending on the same day (S8 L3)
            if len({x.value for x in tied}) > 1:
                raise EquityDataError(f"{company_id} {metric} {last.period_end}: an annual and a "
                                      f"{tied[0].fact.period_kind} value end on the same day and differ; ask for a kind")
            last = tied[0]
        if max_age_days is not None and (as_of - last.period_end).days > max_age_days:
            return None
        return last

    def ttm(self, company_id: str, metric: str, as_of: date, *, vintage: str = "latest_known") -> float | None:
        """Sum of the last four fiscal quarters known at ``as_of`` (a flow metric); None unless they are
        consecutive. See ``ttm_detail``."""
        d = self.ttm_detail(company_id, metric, as_of, vintage=vintage)
        return None if d is None else d["value"]

    def ttm_detail(self, company_id: str, metric: str, as_of: date, *, vintage: str = "latest_known") -> dict | None:
        """The last four consecutive fiscal quarters known at ``as_of`` (S8 L3). Companies often report no separate
        fourth quarter: only the annual figure. Then the fourth quarter is derived as annual minus the first three
        quarters of that fiscal year, all as known at ``as_of``, and flagged ``derived_q4``. A reported fourth quarter
        is always preferred; an annual figure is never added to quarters (no double counting), and when both exist
        their disagreement beyond 1% is reported (``inconsistent_with_annual``), not hidden. For flow metrics only
        (revenue, income, cash flow): a stock metric (assets, shares) has no trailing sum."""
        quarters = {k.period_end: (k.value, False, k) for k in
                    self.known(company_id, metric, as_of, vintage=vintage, kind="quarter")}
        annual = self.known(company_id, metric, as_of, vintage=vintage, kind="annual")
        inconsistent = []
        for a in annual:
            prior = [q for q in quarters if 0 < (a.period_end - q).days <= 290 and q != a.period_end]
            prior = sorted(prior)[-3:]
            if len(prior) != 3 or any(not 80 <= (b - c).days <= 100 for c, b in zip(prior, prior[1:] + [a.period_end])):
                continue
            three = sum(quarters[q][0] for q in prior)
            if a.period_end in quarters:
                total = three + quarters[a.period_end][0]
                if abs(total - a.value) > 0.01 * max(abs(a.value), 1e-12):
                    inconsistent.append(a.period_end)
            else:
                _same_currency([a] + [quarters[q][2] for q in prior])
                quarters[a.period_end] = (a.value - three, True, a)
        ends = sorted(quarters)[-4:]
        if len(ends) < 4 or any(not 80 <= (b - c).days <= 100 for c, b in zip(ends, ends[1:])):
            return None
        _same_currency([quarters[e][2] for e in ends])
        return {"value": float(sum(quarters[e][0] for e in ends)), "periods": tuple(ends),
                "derived_q4": tuple(e for e in ends if quarters[e][1]),
                "inconsistent_with_annual": tuple(e for e in inconsistent if e in ends)}

    def growth(self, company_id: str, metric: str, as_of: date, *, lag: int = 4, kind: str = "quarter",
               vintage: str = "latest_known") -> float | None:
        """Growth of the latest period over the period ``lag`` periods earlier, both as known at ``as_of``."""
        k = self.known(company_id, metric, as_of, vintage=vintage, kind=kind)
        if len(k) <= lag:
            return None
        now, then = k[-1], k[-1 - lag]
        expected = {"quarter": 91, "half": 182, "annual": 365}[kind] * lag
        if abs((now.period_end - then.period_end).days - expected) > 20 * lag:
            return None                                         # a missing period in between
        _same_currency([now, then])
        if then.value <= 0:
            return None
        return float(now.value / then.value - 1.0)

    def ratio(self, company_id: str, num: str, den: str, as_of: date, **kw) -> float | None:
        a, b = self.value(company_id, num, as_of, **kw), self.value(company_id, den, as_of, **kw)
        if a is None or b is None or b.value == 0:
            return None
        if a.currency and b.currency and a.currency != b.currency:
            raise CurrencyError(f"{company_id}: {num} in {a.currency}, {den} in {b.currency}")
        return float(a.value / b.value)

    def capture_known(self, company_id: str, metric: str) -> bool:
        """Whether every fact of the series carries a vendor capture time."""
        return all(f.capture_time is not None for f in self._facts.get((company_id, metric), []))

    def facts(self, company_id: str, metric: str) -> list[Fact]:
        return list(self._facts.get((company_id, metric), []))

    def companies(self) -> tuple:
        return tuple(sorted({c for c, _ in self._facts}))

    def metrics(self) -> tuple:
        return tuple(sorted({m for _, m in self._facts}))


def _same_currency(ks) -> None:
    curs = {k.currency for k in ks}
    if len(curs) > 1:
        raise CurrencyError(f"values in several currencies combined: {sorted(map(str, curs))}")
