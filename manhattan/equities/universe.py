"""Technology-equity universe: categories, classification history and point-in-time eligibility.

    builder = UniverseBuilder(master, prices, classes, rules, fundamentals=..., borrow=...)
    snap = builder.snapshot(date(2008, 6, 30))         # members and, for every other candidate, why not

**No hard-coded list.** Candidates on a day are the securities the ``SecurityMaster`` shows as listed and known on
that day. A company that later failed or was acquired is a candidate before it left; one that listed later is not.

**Classification is history, too.** A company's technology category is an interval with a ``known_from`` date. A
reclassification published later (a vendor moving a company from "consumer internet" to "cloud infrastructure"
after the fact) is not used before it was published, and ``known_from`` earlier than the interval's start is
allowed only when the classification was public in advance.

**Eligibility from data known at the close of the day.** Price, trailing dollar volume, market capitalisation
(close × shares outstanding as known), trading history, corporate-action completeness, fundamental coverage and
borrow availability are all evaluated with information available at that close. Every exclusion has a reason, so
a snapshot can be audited. ``snapshot`` never reads a bar, action, fact or classification dated after its day.

**Shares are split-adjusted (S8 M6).** Market capitalisation uses ``split_adjusted_shares``: a share count reported
for a quarter is multiplied by the splits after its publication, so a split does not halve (or double) market
capitalisation until the next filing.

**Unresolved price moves are holds, not silent drops (S8 M7).** A security whose history has a split-like move that
neither a recorded split nor share counts explain is excluded with reason "unresolved price move" and listed in
``Snapshot.holds``: excluding it silently would remove crashed stocks from the universe, a survivorship bias.

**One bad record excludes one security (S8 N2).** A fundamental query that fails closed for a security — for example an
annual and a fourth-quarter share count for the same period end that disagree — excludes that security, with the
error as its reason. It does not raise out of ``snapshot``, which would halt the whole universe.

**Two equity research tracks, one pipeline (issue #102).** ``track_rules`` gives the eligibility rules of the
technology and the non-technology track. They share every rule except the categories (``sectors``) and, for
non-technology, REITs as a security type. ``track_snapshots`` forms both universes on one day from the same data and
checks that they are disjoint and that no member sits outside its track.

**Scope.** The default categories are US-listed technology sub-industries in this package's own taxonomy (vendor
industry codes are licensed and may be mapped onto it). Listing currency is checked against the rules' currency:
an international extension adds calendars, currencies and a currency rule, not a second universe framework.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .errors import EquityDataError, IdentityError
from .fundamentals import FundamentalStore
from .identity import SecurityMaster
from .prices import PriceBook

TECH_CATEGORIES = (
    "semiconductors", "semiconductor_equipment", "enterprise_software", "cloud_infrastructure", "cybersecurity",
    "consumer_internet", "digital_advertising", "ecommerce", "ai_infrastructure", "data_centres", "networking",
    "technology_hardware", "it_services", "emerging_technology",
)


@dataclass(frozen=True)
class Classification:
    company_id: str
    category: str
    start: date
    end: date | None                     # None while in force (stated explicitly)
    known_from: date                     # first day the assignment was published (no default)
    source: str = ""

    def __post_init__(self):
        from .sectors import all_categories
        if self.category not in all_categories():
            raise EquityDataError(f"{self.company_id}: unknown category {self.category!r}")
        if self.end is not None and self.end < self.start:
            raise EquityDataError(f"{self.company_id}: classification ends before it starts")
        if not isinstance(self.known_from, date):
            raise EquityDataError(f"{self.company_id}: known_from is required (a classification is not known "
                                  "because it took effect)")


class ClassificationHistory:
    def __init__(self, items=()):
        self._items: list[Classification] = []
        for c in items:
            self.add(c)

    def add(self, c: Classification) -> None:
        for o in self._items:
            if o.company_id == c.company_id and o.known_from == c.known_from and o.start <= (c.end or date.max) \
                    and c.start <= (o.end or date.max) and o.category != c.category:
                raise EquityDataError(f"{c.company_id}: two categories for one period from one publication")
        self._items.append(c)

    def category(self, company_id: str, on: date, *, as_known_at: date | None = None) -> str | None:
        """The category in force on ``on`` according to records published by ``as_known_at`` (default ``on``); the
        latest-published record wins when two cover the day."""
        known = on if as_known_at is None else as_known_at
        hits = [c for c in self._items if c.company_id == company_id and c.start <= on
                and (c.end is None or on <= c.end) and c.known_from <= known]
        if not hits:
            return None
        return max(hits, key=lambda c: (c.known_from, c.start)).category


@dataclass(frozen=True)
class EligibilityRules:
    categories: tuple = TECH_CATEGORIES
    security_types: tuple = ("common", "adr")
    currency: str = "USD"
    min_price: float = 5.0
    min_dollar_volume: float = 5e6           # median daily dollar volume over adv_sessions
    adv_sessions: int = 63
    min_market_cap: float = 3e8
    min_history_sessions: int = 252
    require_action_complete: bool = True
    required_metrics: tuple = ()             # fundamental metrics that must be known (and recent) at the date
    metric_max_age_days: int = 200
    require_borrow: bool = False             # for the short side of relative-value books
    shares_metric: str = "shares_outstanding"

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    day: date
    members: tuple
    excluded: dict = field(default_factory=dict)     # security_id -> tuple of reasons
    categories: dict = field(default_factory=dict)   # member security_id -> category
    rules_hash: str = ""
    holds: tuple = ()                                 # securities excluded only by an unresolved price move

    def membership_hash(self) -> str:
        """SHA-256 of the day and the sorted members: a feature or a neutralisation that names this hash was
        computed on this universe and no other."""
        return hashlib.sha256(json.dumps([self.day.isoformat(), list(self.members)]).encode()).hexdigest()


class UniverseBuilder:
    def __init__(self, master: SecurityMaster, prices: PriceBook, classes: ClassificationHistory,
                 rules: EligibilityRules, *, fundamentals: FundamentalStore | None = None, borrow=None):
        self.master, self.prices, self.classes, self.rules = master, prices, classes, rules
        self.fundamentals, self.borrow = fundamentals, borrow
        if rules.required_metrics and fundamentals is None:
            raise EquityDataError("rules require fundamental metrics but no fundamental store was given")
        if rules.require_borrow and borrow is None:
            raise EquityDataError("rules require borrow availability but no borrow book was given")

    def snapshot(self, day: date) -> Snapshot:
        r = self.rules
        cal = self.prices.calendar
        if not cal.is_session(day):
            raise EquityDataError(f"{day} is not a session: a universe is formed at a close")
        members, excluded, cats, holds = [], {}, {}, []
        for sid in self.master.listed(day):
            why = []
            sec = self.master.security(sid)
            cat = self.classes.category(sec.company_id, day)
            if cat not in r.categories:
                why.append(f"category {cat}")
            if sec.security_type not in r.security_types:
                why.append(f"security type {sec.security_type}")
            if sec.currency != r.currency:
                why.append(f"currency {sec.currency}")
            last = self.prices.last_traded(sid, day)
            if last is None:
                why.append("no traded price")
                excluded[sid] = tuple(why)
                continue
            if last != day:
                why.append(f"not traded on the day (last {last})")
            bars = self.prices.bars(sid, date.min, day)
            traded = [b for b in bars if b.status == "traded"]
            close = traded[-1].close
            if close < r.min_price:
                why.append(f"price {close:.2f} below {r.min_price}")
            if len(traded) < r.min_history_sessions:
                why.append(f"history {len(traded)} sessions")
            dv = self.prices.dollar_volume(sid, day, r.adv_sessions)
            if dv.size < min(r.adv_sessions, r.min_history_sessions) or float(np.median(dv)) < r.min_dollar_volume:
                why.append("dollar volume")
            shares, sh_why = split_adjusted_shares(self.prices, self.fundamentals, sid, sec.company_id, day,
                                                   r.shares_metric, r.metric_max_age_days)
            if shares is None:
                if r.min_market_cap > 0:
                    why.append(f"market capitalisation unknown ({sh_why})")
            elif close * shares < r.min_market_cap:
                why.append("market capitalisation")
            if self.fundamentals is not None:
                for m in r.required_metrics:
                    try:
                        if self.fundamentals.value(sec.company_id, m, day, max_age_days=r.metric_max_age_days) is None:
                            why.append(f"{m} not known")
                    except EquityDataError as exc:      # one security's conflicting record never halts the universe
                        why.append(f"{m} ambiguous: {exc}")
            if r.require_action_complete and traded:
                start = traded[max(0, len(traded) - r.min_history_sessions)].day
                issue = self.prices.action_issue(sid, start, day, as_of=day)
                if issue == "suspected_split":
                    why.append("unresolved price move (data hold: review, do not drop silently)")
                    holds.append(sid)
                elif issue:
                    why.append("corporate actions incomplete")
            if r.require_borrow:
                try:
                    rec = self.borrow.status(sid, day)
                    if not rec.available:
                        why.append("not borrowable")
                except EquityDataError:
                    why.append("borrow unknown")
            if why:
                excluded[sid] = tuple(why)
            else:
                members.append(sid)
                cats[sid] = cat
        holds = tuple(sorted(s for s in holds if len(excluded.get(s, ())) == 1))
        return Snapshot(day, tuple(sorted(members)), excluded, cats, r.hash(), holds)


def split_adjusted_shares(prices: PriceBook, fundamentals, security_id: str, company_id: str, day: date,
                          shares_metric: str = "shares_outstanding", max_age_days: int = 200):
    """(shares on ``day`` as known at its close, or None; the reason when None). Share counts in the price book
    come first (adjusted for later splits). A reported share count is adjusted for splits after its publication;
    a split between its period end and its publication is ambiguous (financial statements may already restate it,
    ASC 260), so the count is refused rather than guessed (S8 M6)."""
    s = prices.shares_outstanding(security_id, day, as_of=day)
    if s is not None:
        return s, ""
    if fundamentals is None:
        return None, "no share count"
    try:
        k = fundamentals.value(company_id, shares_metric, day, max_age_days=max_age_days)
    except EquityDataError as exc:              # e.g. an annual and a Q4 count that disagree (S8 N2): this security
        return None, f"shares ambiguous: {exc}"  # only is excluded, with the reason; the universe is not halted
    if k is None:
        return None, "shares outstanding unknown"
    published = k.usable_from
    if prices.splits_between(security_id, k.period_end, published, as_of=day):
        return None, "shares ambiguous: a split between the period end and the filing"
    return k.value * prices.split_factor(security_id, published, day, as_of=day), ""


def assert_snapshot_for(snapshot: Snapshot, day: date) -> None:
    """A computation at ``day`` must use the universe formed at ``day``, not a later (or earlier) one."""
    if snapshot.day != day:
        raise IdentityError(f"universe formed on {snapshot.day} used at {day}: future or stale membership")


def track_rules(track: str, **over) -> EligibilityRules:
    """Eligibility rules of one equity research track. The rules are identical across tracks apart from the
    categories and, for non-technology, the REIT security type (owner decisions NT-1 and NT-2). Any field may be
    overridden, but the categories must stay inside the track."""
    from . import sectors
    cats = sectors.categories_of_track(track)
    base = {"categories": cats}
    if track == sectors.NON_TECHNOLOGY_TRACK:
        base["security_types"] = sectors.NON_TECH_SECURITY_TYPES
    base.update(over)
    stray = [c for c in base["categories"] if sectors.track_of(c) != track]
    if stray:
        raise EquityDataError(f"categories {stray} are not in the {track} track")
    bad_types = [t for t in base.get("security_types", ()) if t in sectors.NEVER_IN_EQUITY_TRACKS]
    if bad_types:
        raise EquityDataError(f"security types {bad_types} are never in an equity research track")
    return EligibilityRules(**base)


def track_snapshots(master: SecurityMaster, prices: PriceBook, classes: ClassificationHistory, day: date,
                    rules_by_track: dict, *, fundamentals: FundamentalStore | None = None, borrow=None) -> dict:
    """``{track: Snapshot}`` for each equity track, formed on ``day`` from the same data. Raises when a security is
    a member of two tracks or a member's category (as known on ``day``) is outside its track. Both are invariants of
    the taxonomy, so either one means a configuration error."""
    from . import sectors
    snaps = {t: UniverseBuilder(master, prices, classes, r, fundamentals=fundamentals, borrow=borrow).snapshot(day)
             for t, r in rules_by_track.items()}
    seen: dict = {}
    for t, snap in snaps.items():
        for sid, cat in snap.categories.items():
            if sectors.track_of(cat) != t:
                raise EquityDataError(f"{sid}: category {cat} is not in the {t} track on {day}")
            if sid in seen:
                raise EquityDataError(f"{sid} is a member of both {seen[sid]} and {t} on {day}")
            seen[sid] = t
    return snaps
