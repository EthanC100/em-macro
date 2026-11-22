"""Deterministic synthetic fixtures for the equities package. Invented companies, invented prices: nothing here is,
resembles or is calibrated to market data. Every generator takes a seed and returns the same output for it.

    cal = calendar()                                     # 2004-2008 weekdays minus a few fixed closures
    days, ly, lx = cointegrated_pair(seed=1)             # stable relationship
    days, ly, lx = cointegrated_pair(seed=1, break_at=500)   # cointegration breaks at observation 500
    w = world()                                          # master, prices, classes, fundamentals, borrow, events
"""
from __future__ import annotations

import hashlib
import json
import sys
import weakref
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import numpy as np

from .costs import BorrowBook, BorrowRecord
from .errors import EquityDataError
from .fundamentals import Fact, FundamentalStore
from .identity import Company, LifecycleEvent, Security, SecurityMaster, TickerInterval
from .prices import Bar, CorporateAction, DelistingReturn, PriceBook, ShareCount
from .sessions import MarketCalendar
from .universe import Classification, ClassificationHistory

_SYNTHETIC: dict = {}            # id -> (weak reference, provenance hash): worlds made by this package's generators
_GENERATORS = ("manhattan.equities.synthetic", "manhattan.equities.sector_synthetic")


def _provenance(frame) -> str:
    """SHA-256 of the generator (module and function) and the arguments it was called with."""
    code = frame.f_code
    names = code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]
    desc = {"generator": f"{frame.f_globals.get('__name__')}.{code.co_name}",
            "arguments": {n: repr(frame.f_locals.get(n)) for n in names}}
    return hashlib.sha256(json.dumps(desc, sort_keys=True).encode("utf-8")).hexdigest()


def _register(world, *, provenance: str):
    _SYNTHETIC[id(world)] = (weakref.ref(world), provenance)
    return world


def mark_synthetic(world):
    """Record a world returned by one of this package's synthetic generators, and nothing else (S17 C1).

    Callable only from a generator module of this package (``_GENERATORS``): any other caller is refused, so no
    production code can mark an arbitrary object synthetic. The record keeps the world's provenance hash (generator
    and arguments), which is the data identity a registered holdout look declares."""
    caller = sys._getframe(1)
    if caller.f_globals.get("__name__") not in _GENERATORS:
        raise EquityDataError("only this package's synthetic generators mark a world synthetic")
    return _register(world, provenance=_provenance(caller))


def is_synthetic(world) -> bool:
    """True only for a world a synthetic generator here returned. Research entry points that run a portfolio rule
    or a registered experiment require it: nothing in the equities package runs on market data (issue #102)."""
    e = _SYNTHETIC.get(id(world))
    return e is not None and e[0]() is world


def provenance(world) -> str | None:
    """The provenance hash of a synthetic world (``None`` for anything else)."""
    e = _SYNTHETIC.get(id(world))
    return e[1] if e is not None and e[0]() is world else None


HOLIDAYS = (date(2005, 1, 17), date(2005, 7, 4), date(2005, 12, 26), date(2006, 7, 4), date(2006, 12, 25),
            date(2007, 7, 4), date(2007, 12, 25), date(2008, 7, 4))


def calendar(start: date = date(2004, 1, 1), end: date = date(2008, 12, 31)) -> MarketCalendar:
    return MarketCalendar.synthetic("SYN-XNYS", start, end, holidays=[h for h in HOLIDAYS if start <= h <= end],
                                    half_days=[date(2006, 11, 24)] if start <= date(2006, 11, 24) <= end else ())


def cointegrated_pair(seed: int = 0, n: int = 750, *, beta: float = 1.3, phi: float = 0.9, sd_x: float = 0.02,
                      sd_e: float = 0.01, break_at: int | None = None, break_kind: str = "random_walk",
                      new_beta: float = 0.6):
    """Log prices of y and x with y = 0.2 + β x + u, u an AR(1) with coefficient φ. From ``break_at`` on the
    relationship breaks: ``random_walk`` (u becomes a random walk: cointegration lost) or ``beta_shift`` (β jumps
    to ``new_beta``)."""
    rng = np.random.default_rng(seed)
    x = 3.0 + np.cumsum(rng.normal(0, sd_x, n))
    e = rng.normal(0, sd_e, n)
    u = np.zeros(n)
    for t in range(1, n):
        if break_at is not None and t >= break_at and break_kind == "random_walk":
            u[t] = u[t - 1] + e[t]
        else:
            u[t] = phi * u[t - 1] + e[t]
    b = np.full(n, beta)
    if break_at is not None and break_kind == "beta_shift":
        b[break_at:] = new_beta
        # keep the level continuous at the break so the shift is in the hedge ratio, not a jump
        x0 = x[break_at]
        y = 0.2 + np.where(np.arange(n) < break_at, beta * x, beta * x0 + new_beta * (x - x0)) + u
    else:
        y = 0.2 + b * x + u
    days = _session_days(n)
    return days, y, x


def correlated_walks(seed: int = 0, n: int = 750, rho: float = 0.8, sd: float = 0.015):
    """Two random walks whose increments have correlation ``rho``: highly correlated, not cointegrated."""
    rng = np.random.default_rng(seed)
    z1, z2 = rng.normal(0, sd, n), rng.normal(0, sd, n)
    a = np.cumsum(z1)
    b = np.cumsum(rho * z1 + np.sqrt(1 - rho ** 2) * z2)
    days = _session_days(n)
    return days, 3.0 + a, 3.0 + b


def _session_days(n: int) -> np.ndarray:
    """The first ``n`` sessions of the synthetic calendar from 2004-01-02 (exchange sessions, not calendar days)."""
    days = calendar().sessions_between(date(2004, 1, 2), date(2008, 12, 31))
    if n > len(days):
        raise ValueError(f"the synthetic calendar has {len(days)} sessions, not {n}")
    return np.array(days[:n], dtype=object)


def _ts(cal: MarketCalendar, d: date, hh: int = 7, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), cal.tz)


@dataclass
class World:
    calendar: MarketCalendar
    master: SecurityMaster
    prices: PriceBook
    classes: ClassificationHistory
    fundamentals: FundamentalStore
    borrow: BorrowBook
    log_prices: dict                   # security -> log total-return index aligned with days (NaN when not listed)
    days: np.ndarray


# id: (company, category, listed_from, listed_to, delisting reason, ticker, drift, beta)
_END_KNOWN = {"S04": date(2006, 6, 30), "S06": date(2006, 12, 1)}     # when the delisting was announced
_SPEC = {
    "S01": ("C01", "semiconductors", date(2004, 1, 2), None, None, "SEMA", 0.0003, 1.2),
    "S02": ("C02", "semiconductors", date(2004, 1, 2), None, None, "SEMB", 0.0002, 1.1),
    "S03": ("C03", "enterprise_software", date(2004, 1, 2), None, None, "SOFA", 0.0004, 1.0),
    "S04": ("C04", "enterprise_software", date(2004, 1, 2), date(2006, 6, 30), "performance", "SOFB", -0.002, 1.3),
    "S05": ("C05", "cloud_infrastructure", date(2005, 9, 1), None, None, "CLDA", 0.0005, 1.4),     # IPO later
    "S06": ("C06", "networking", date(2004, 1, 2), date(2007, 3, 30), "acquisition", "NETA", 0.0002, 1.0),
    "S07": ("C07", "consumer_internet", date(2004, 1, 2), None, None, "WEBA", 0.0001, 1.2),
    "S08": ("C08", "consumer_internet", date(2004, 1, 2), None, None, "WEBB", 0.0002, 1.25),
    "S09": ("C09", "cybersecurity", date(2007, 6, 1), None, None, "SOFB", 0.0003, 1.3),   # reuses S04's ticker
}


def world(seed: int = 7, start: date = date(2004, 1, 2), end: date = date(2008, 12, 31)) -> World:
    """A small technology universe with an IPO, a performance delisting (with delisting return), an acquisition,
    a ticker change, a ticker later reused by another issuer, a 2:1 split, a special dividend, a reclassification
    published late, quarterly fundamentals with one restatement, and borrow records."""
    cal = calendar(start - timedelta(days=1), end + timedelta(days=40))
    rng = np.random.default_rng(seed)
    master, book = SecurityMaster(), PriceBook(cal)
    classes, fs = ClassificationHistory(), FundamentalStore(cal)
    borrow = BorrowBook()
    days = np.array(cal.sessions_between(start, end), dtype=object)    # the calendar runs on past ``end``
    n = len(days)
    market = rng.normal(0.0003, 0.011, n)
    logp = {}
    for sid, (cid, cat, lf, lt, reason, tick, drift, beta) in _SPEC.items():
        master.add_company(Company(cid, f"Synthetic {cid}"))
        master.add_security(Security(sid, cid, "A", "common", "USD", listed_from=lf, listed_to=lt,
                                     known_from=lf - timedelta(days=21)))       # a prospectus or listing notice
        classes.add(Classification(cid, cat, date(2000, 1, 1), None, known_from=date(2000, 1, 1), source="synthetic"))
        r = drift + beta * market + rng.normal(0, 0.015, n)
        live = np.array([lf <= d and (lt is None or d <= lt) for d in days])
        price = 30.0 * np.exp(np.cumsum(np.where(live, r, 0.0)))
        lp = np.where(live, np.log(price), np.nan)
        closes = price.copy()
        if sid == "S01":                                  # 2:1 split ex 2006-03-01: raw closes halve
            sp = date(2006, 3, 1)
            closes[days >= sp] /= 2.0
            book_actions = [CorporateAction(sid, "split", sp, date(2006, 1, 20), ratio=2.0, captured=date(2006, 1, 20))]
        elif sid == "S03":                                # special dividend
            book_actions = [CorporateAction(sid, "special_dividend", date(2007, 5, 15), date(2007, 4, 20),
                                            amount=0.5, currency="USD", captured=date(2007, 4, 20))]
            k = days >= date(2007, 5, 15)
            closes[k] *= 1 - 0.5 / price[np.argmax(k) - 1]  # raw closes drop by the distribution on the ex-date
        else:
            book_actions = []
        vol = np.where(live, 6e5 + 4e5 * rng.random(n), 0.0)
        for i, d in enumerate(days):
            if live[i]:
                book.add_bar(Bar(sid, d, float(closes[i]), "USD", float(vol[i])))
        for a in book_actions:
            book.add_action(a)
        for i, d in enumerate(days[::21]):              # monthly share counts, public five days later
            if live[days == d][0]:
                n_sh = 5e7 * (2 if sid == "S01" and d >= date(2006, 3, 1) else 1)
                book.add_share_count(ShareCount(sid, d, n_sh, d + timedelta(days=5), "synthetic"))
        logp[sid] = lp
        for q in _quarters(lf, end):
            pub = _ts(cal, cal.session_on_or_before(q + timedelta(days=35)), 16, 30)    # after the close
            rev = 100.0 * (1.02 ** ((q - date(2004, 1, 1)).days / 91)) * (1 + 0.1 * rng.normal())
            if lt is not None and pub.date() > lt:
                break
            fs.add(Fact(cid, "revenue", q, "quarter", rev, "USD", pub, source="synthetic"))
            fs.add(Fact(cid, "shares_outstanding", q, "quarter", 5e7 * (2 if sid == "S01" and q >= date(2006, 3, 31)
                                                                          else 1), None, pub, source="synthetic"))
        for d in days[::5]:
            if live[days == d][0]:
                borrow.add(BorrowRecord(sid, d, cal.next_session(d), True, 0.0030 if sid != "S04" else 0.15))
    # ticker intervals: S07 changes ticker (announced two weeks ahead); S04's ticker is reused by S09 from 2007
    for sid, (cid, cat, lf, lt, reason, tick, *_rest) in _SPEC.items():
        if sid == "S07":
            master.add_ticker(TickerInterval(sid, "WEBA", "XNAS", lf, date(2006, 9, 29), known_from=lf,
                                             end_known_from=date(2006, 9, 15)))
            master.add_ticker(TickerInterval(sid, "WEBX", "XNAS", date(2006, 10, 2), None, known_from=date(2006, 9, 15)))
        else:
            master.add_ticker(TickerInterval(sid, tick, "XNAS", lf, lt, known_from=lf,
                                             end_known_from=_END_KNOWN.get(sid)))
    master.add_event(LifecycleEvent("S05", "ipo", date(2005, 9, 1), date(2005, 8, 15)))
    master.add_event(LifecycleEvent("S04", "delisting", date(2006, 6, 30), date(2006, 6, 30), reason="performance"))
    master.add_event(LifecycleEvent("S06", "acquisition", date(2007, 3, 30), date(2006, 12, 1),
                                    counterparty_security="S02"))
    master.add_event(LifecycleEvent("S06", "delisting", date(2007, 3, 30), date(2006, 12, 1), reason="acquisition"))
    book.add_delisting_return(DelistingReturn("S04", date(2006, 6, 30), -0.35, date(2006, 7, 20), "synthetic OTC"))
    book.add_delisting_return(DelistingReturn("S06", date(2007, 3, 30), 0.02, date(2007, 3, 30), "cash terms"))
    book.mark_delisted("S04", date(2006, 6, 30), "performance")
    book.mark_delisted("S06", date(2007, 3, 30), "acquisition")
    # S08 reclassified to digital advertising from 2005, but the vendor published it only in 2007 (backfilled)
    classes.add(Classification("C08", "digital_advertising", date(2005, 1, 1), None, known_from=date(2007, 1, 15)))
    # one restatement: C03's revenue for 2005-06-30, restated down in 2006
    fs.add(Fact("C03", "revenue", date(2005, 6, 30), "quarter", 50.0, "USD", _ts(cal, date(2006, 2, 1), 17),
                vintage="restated", source="synthetic"))
    return mark_synthetic(World(cal, master, book, classes, fs, borrow, logp, days))


def _quarters(start: date, end: date):
    out, y = [], start.year
    while True:
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            q = date(y, m, d)
            if q >= start and q <= end - timedelta(days=60):
                out.append(q)
            if q > end:
                return out
        y += 1
