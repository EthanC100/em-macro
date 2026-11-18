"""Security and company identity through time. A ticker is a label with a validity interval, never an identity.

    master = SecurityMaster()
    master.add_company(Company("C0001", "Synthetic Semis"))
    master.add_security(Security("S0001", "C0001", "A", "common", "USD", listed_from=date(2001, 3, 1)))
    master.add_ticker(TickerInterval("S0001", "SYNA", "XNAS", start=date(2001, 3, 1), known_from=date(2001, 3, 1)))
    master.resolve("SYNA", on=date(2005, 6, 1))          # -> "S0001"

**Two permanent identifiers.** ``company_id`` names an issuer; ``security_id`` names one listed instrument of it
(one share class, one listing). A company may have several securities at once (share classes, a primary listing
and an ADR); a security belongs to exactly one company for its life. Neither identifier is ever reused.

**Validity and knowledge.** Every security, ticker interval and lifecycle event has an effective date and a
**required** ``known_from`` date (the first day the record was public); nothing defaults to its effective date. An
ended ticker interval also states when its end was public (``end_known_from``). A query ``as_known_at=d`` sees only records known by ``d``: a ticker change
announced after ``d`` is not used to interpret data at ``d``, and a ticker that is later reassigned to another
issuer resolves, at each date, to the security that held it then.

**Fail closed.** ``resolve`` raises ``IdentityError`` when no security, or more than one, holds the ticker on that
day. ``validate`` refuses overlapping tickers, intervals outside a listing, a security listed twice for the same
share class (a duplicate) and events that contradict the listing dates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .errors import IdentityError

SECURITY_TYPES = ("common", "adr", "preferred", "etf", "unit", "warrant", "right", "tracking_stock", "reit", "other")
EVENT_KINDS = ("ipo", "delisting", "merger", "acquisition", "spin_off", "bankruptcy", "exchange_change",
               "ticker_change", "share_class_created", "reverse_merger")
DELISTING_REASONS = ("performance", "merger", "acquisition", "bankruptcy", "voluntary", "exchange_move", "other",
                     "unknown")


@dataclass(frozen=True)
class Company:
    company_id: str
    name: str

    def __post_init__(self):
        if not self.company_id or not isinstance(self.company_id, str):
            raise IdentityError("a company needs a permanent company_id")


@dataclass(frozen=True)
class Security:
    security_id: str
    company_id: str
    share_class: str
    security_type: str
    currency: str
    listed_from: date
    listed_to: date | None              # last trading day; None while listed (stated explicitly)
    known_from: date                    # first day the security was public (a prospectus or listing notice)

    def __post_init__(self):
        if not self.security_id or not self.company_id:
            raise IdentityError("a security needs a permanent security_id and its company_id")
        if self.security_type not in SECURITY_TYPES:
            raise IdentityError(f"{self.security_id}: unknown security type {self.security_type!r}")
        if not (isinstance(self.currency, str) and len(self.currency) == 3 and self.currency.isupper()):
            raise IdentityError(f"{self.security_id}: currency must be an ISO 4217 code")
        if self.listed_to is not None and self.listed_to < self.listed_from:
            raise IdentityError(f"{self.security_id}: delisted before it was listed")
        if not isinstance(self.known_from, date):
            raise IdentityError(f"{self.security_id}: known_from is required (no default: a record is not known "
                                "merely because it took effect)")

    def listed_on(self, day: date) -> bool:
        return self.listed_from <= day and (self.listed_to is None or day <= self.listed_to)


@dataclass(frozen=True)
class TickerInterval:
    """``ticker`` on ``exchange`` named ``security_id`` from ``start`` up to and including ``end``."""
    security_id: str
    ticker: str
    exchange: str
    start: date
    end: date | None                    # None while the ticker is in use (stated explicitly)
    known_from: date                    # first day the assignment was public
    end_known_from: date | None = None  # first day the end was public; required with ``end``

    def __post_init__(self):
        if not self.ticker or not self.exchange:
            raise IdentityError("a ticker interval needs a ticker and an exchange")
        if self.end is not None and self.end < self.start:
            raise IdentityError(f"{self.ticker}: interval ends before it starts")
        if not isinstance(self.known_from, date):
            raise IdentityError(f"{self.ticker}: known_from is required (no default)")
        if self.end is not None and not isinstance(self.end_known_from, date):
            raise IdentityError(f"{self.ticker}: an ended interval needs end_known_from (when the end was public)")

    def covers(self, day: date, known: date | None = None) -> bool:
        """In force on ``day`` as believed at ``known`` (default: the true interval). An end that was not yet public
        at ``known`` is not applied."""
        end = self.end
        if known is not None and end is not None and self.end_known_from > known:
            end = None
        return self.start <= day and (end is None or day <= end)


@dataclass(frozen=True)
class LifecycleEvent:
    security_id: str
    kind: str
    effective: date
    known_from: date
    counterparty_security: str | None = None     # acquirer, parent of a spin-off, new security of a share class
    reason: str | None = None                    # for a delisting: one of DELISTING_REASONS
    detail: str = ""

    def __post_init__(self):
        if self.kind not in EVENT_KINDS:
            raise IdentityError(f"unknown lifecycle event {self.kind!r}")
        if self.kind == "delisting" and self.reason not in DELISTING_REASONS:
            raise IdentityError(f"{self.security_id}: a delisting needs a reason from {DELISTING_REASONS}")
        if self.kind in ("merger", "acquisition", "spin_off") and not self.counterparty_security:
            raise IdentityError(f"{self.security_id}: a {self.kind} names its counterparty security")


def _overlap(a_start, a_end, b_start, b_end) -> bool:
    far = date.max
    return a_start <= (b_end or far) and b_start <= (a_end or far)


class SecurityMaster:
    """Companies, securities, ticker intervals and lifecycle events, with point-in-time queries."""

    def __init__(self):
        self.companies: dict[str, Company] = {}
        self.securities: dict[str, Security] = {}
        self.tickers: list[TickerInterval] = []
        self.events: list[LifecycleEvent] = []

    # ---- building
    def add_company(self, c: Company) -> None:
        if c.company_id in self.companies and self.companies[c.company_id] != c:
            raise IdentityError(f"company {c.company_id} redefined")
        self.companies[c.company_id] = c

    def add_security(self, s: Security) -> None:
        if s.company_id not in self.companies:
            raise IdentityError(f"{s.security_id}: unknown company {s.company_id}")
        if s.security_id in self.securities and self.securities[s.security_id] != s:
            raise IdentityError(f"security {s.security_id} redefined (identifiers are permanent and never reused)")
        for o in self.securities.values():
            if o.security_id != s.security_id and o.company_id == s.company_id and o.share_class == s.share_class \
                    and o.security_type == s.security_type and _overlap(o.listed_from, o.listed_to, s.listed_from,
                                                                        s.listed_to):
                raise IdentityError(f"duplicate security: {s.security_id} and {o.security_id} are the same share "
                                    f"class of {s.company_id} listed at the same time")
        self.securities[s.security_id] = s

    def add_ticker(self, t: TickerInterval) -> None:
        sec = self.securities.get(t.security_id)
        if sec is None:
            raise IdentityError(f"ticker {t.ticker}: unknown security {t.security_id}")
        if t.start < sec.listed_from or (sec.listed_to is not None and (t.end is None or t.end > sec.listed_to)):
            raise IdentityError(f"ticker {t.ticker}: interval lies outside the listing of {t.security_id}")
        for o in self.tickers:
            if o.ticker == t.ticker and o.exchange == t.exchange and _overlap(o.start, o.end, t.start, t.end):
                raise IdentityError(f"ticker {t.ticker} on {t.exchange} is held by {o.security_id} and "
                                    f"{t.security_id} at the same time")
            if o.security_id == t.security_id and o.exchange == t.exchange and _overlap(o.start, o.end, t.start, t.end):
                raise IdentityError(f"{t.security_id} has two tickers on {t.exchange} at the same time")
        self.tickers.append(t)

    def add_event(self, e: LifecycleEvent) -> None:
        sec = self.securities.get(e.security_id)
        if sec is None:
            raise IdentityError(f"event {e.kind}: unknown security {e.security_id}")
        if e.counterparty_security and e.counterparty_security not in self.securities:
            raise IdentityError(f"event {e.kind}: unknown counterparty {e.counterparty_security}")
        if e.kind == "ipo" and e.effective != sec.listed_from:
            raise IdentityError(f"{e.security_id}: IPO date differs from the listing date")
        if e.kind == "delisting" and sec.listed_to != e.effective:
            raise IdentityError(f"{e.security_id}: delisting date differs from the last trading day")
        if e.kind in ("merger", "acquisition") and sec.listed_to is None:
            raise IdentityError(f"{e.security_id}: an absorbed security must have a last trading day")
        self.events.append(e)

    # ---- queries
    def security(self, security_id: str) -> Security:
        try:
            return self.securities[security_id]
        except KeyError:
            raise IdentityError(f"unknown security {security_id}") from None

    def company_of(self, security_id: str) -> str:
        return self.security(security_id).company_id

    def resolve(self, ticker: str, on: date, *, as_known_at: date | None = None, exchange: str | None = None) -> str:
        """The one security that held ``ticker`` on ``on``, using records known by ``as_known_at`` (default ``on``)."""
        known = on if as_known_at is None else as_known_at
        hits = {t.security_id for t in self.tickers
                if t.ticker == ticker and t.covers(on, known) and t.known_from <= known
                and (exchange is None or t.exchange == exchange)}
        if not hits:
            raise IdentityError(f"no security held ticker {ticker} on {on} (as known at {known})")
        if len(hits) > 1:
            raise IdentityError(f"ticker {ticker} on {on} is ambiguous: {sorted(hits)}; give the exchange")
        return hits.pop()

    def ticker_of(self, security_id: str, on: date, *, as_known_at: date | None = None) -> str:
        known = on if as_known_at is None else as_known_at
        hits = sorted({t.ticker for t in self.tickers
                       if t.security_id == security_id and t.covers(on, known) and t.known_from <= known})
        if len(hits) != 1:
            raise IdentityError(f"{security_id} on {on}: {'no' if not hits else 'several'} tickers {hits}")
        return hits[0]

    def listed(self, on: date, *, as_known_at: date | None = None) -> tuple:
        """Securities listed on ``on`` and known by ``as_known_at`` (default ``on``). Built from the master, never
        from a list of today's survivors: a security delisted later is listed before its delisting."""
        known = on if as_known_at is None else as_known_at
        return tuple(sorted(s.security_id for s in self.securities.values()
                            if s.listed_on(on) and s.known_from <= known))

    def securities_of(self, company_id: str, on: date) -> tuple:
        return tuple(sorted(s.security_id for s in self.securities.values()
                            if s.company_id == company_id and s.listed_on(on)))

    def events_known(self, security_id: str, as_known_at: date) -> tuple:
        return tuple(sorted((e for e in self.events if e.security_id == security_id and e.known_from <= as_known_at),
                            key=lambda e: (e.effective, e.kind)))

    def delisting(self, security_id: str) -> LifecycleEvent | None:
        hits = [e for e in self.events if e.security_id == security_id and e.kind == "delisting"]
        if len(hits) > 1:
            raise IdentityError(f"{security_id} has two delisting events")
        return hits[0] if hits else None

    def validate(self) -> list[str]:
        """Problems of the whole master (empty when consistent)."""
        errs = []
        for s in self.securities.values():
            if not any(t.security_id == s.security_id for t in self.tickers):
                errs.append(f"{s.security_id}: no ticker interval")
            if s.listed_to is not None and self.delisting(s.security_id) is None:
                errs.append(f"{s.security_id}: has a last trading day but no delisting event (reason unknown)")
        return errs
