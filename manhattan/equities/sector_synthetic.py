"""Deterministic synthetic multi-sector equity world: technology and non-technology companies on one pipeline.

    w = sector_world()                       # the same World shape as synthetic.world(), more sectors
    w = sector_world(planted_momentum=0.002, planted_track="non_technology_equities")

Invented companies and invented prices: nothing here is, resembles or is calibrated to market data. The world
exists to exercise the controls issue #102 requires, each with a fixture that would catch it failing:

* **Survivorship.** The world has three delistings:
  - an energy producer goes bankrupt; its delisting return is known only weeks later;
  - a bank is acquired for cash, with the terms announced in advance;
  - a technology company fails.

  It also has an IPO that lists later and an illiquid consumer company that the liquidity screen must exclude.
* **Point-in-time classification across tracks.** Two companies cross between tracks:
  - an IT-services company is reclassified to ``payments`` (financials), announced in advance;
  - a hardware company is reclassified to ``automobiles``, and the vendor publishes the move a year and a half late
    (a backfill).
* **Corporate actions.** The world has a 3:1 split and quarterly utility dividends: the raw close drops on each
  ex-date, and the total return must not.
* **Instruments outside the equity tracks.** A REIT is in the real-estate sector. A bond ETF must be in no equity
  track.
* **Volatility is measured, not assumed.** Energy, materials and biotechnology are given *higher* volatility than
  most technology companies, and utilities and staples lower.
* **Track separation.** ``planted_momentum`` adds a causal cross-sectional momentum effect to one track only. It
  uses returns up to t−1. A comparison must find it in that track and not in the other.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .costs import BorrowBook
from .fundamentals import Fact, FundamentalStore
from .identity import Company, LifecycleEvent, Security, SecurityMaster, TickerInterval
from .prices import Bar, CorporateAction, DelistingReturn, PriceBook, ShareCount
from .sectors import NON_TECHNOLOGY_TRACK, TECHNOLOGY_TRACK, track_of
from .synthetic import World, _quarters, _ts, calendar, mark_synthetic
from .universe import Classification, ClassificationHistory

# sector -> (market beta, sector-factor daily vol, idiosyncratic daily vol). Invented, chosen only so that some
# non-technology sectors are MORE volatile than technology and some less.
SECTOR_RISK = {
    "technology": (1.2, 0.010, 0.016),
    "healthcare": (0.8, 0.006, 0.022),       # biotechnology names dominate idiosyncratic risk
    "financials": (1.1, 0.009, 0.012),
    "industrials": (1.0, 0.006, 0.012),
    "utilities": (0.4, 0.004, 0.007),
    "consumer_staples": (0.5, 0.004, 0.008),
    "consumer_discretionary": (1.1, 0.007, 0.015),
    "materials": (1.1, 0.012, 0.018),
    "energy": (0.9, 0.018, 0.022),
    "real_estate": (0.8, 0.007, 0.011),
    "communication_services": (0.8, 0.005, 0.011),
}

# id: (company, sector, category, listed_from, listed_to, ticker, security_type)
_SPEC = {
    "T01": ("CT1", "technology", "semiconductors", None, None, "TSEM", "common"),
    "T02": ("CT2", "technology", "enterprise_software", None, None, "TSOF", "common"),
    "T03": ("CT3", "technology", "cloud_infrastructure", None, None, "TCLD", "common"),
    "T04": ("CT4", "technology", "networking", None, None, "TNET", "common"),
    "T05": ("CT5", "technology", "cybersecurity", None, date(2007, 3, 30), "TCYB", "common"),     # fails
    "T06": ("CT6", "technology", "it_services", None, None, "TITS", "common"),                   # -> payments
    "T07": ("CT7", "technology", "technology_hardware", None, None, "THWD", "common"),            # -> automobiles
    "T08": ("CT8", "technology", "consumer_internet", None, None, "TWEB", "adr"),
    "H01": ("CH1", "healthcare", "pharmaceuticals", None, None, "HPHA", "common"),
    "H02": ("CH2", "healthcare", "biotechnology", date(2006, 4, 3), None, "HBIO", "common"),       # IPO later
    "F01": ("CF1", "financials", "banks", None, date(2007, 6, 29), "FBNK", "common"),             # acquired
    "F02": ("CF2", "financials", "insurance", None, None, "FINS", "common"),
    "I01": ("CI1", "industrials", "machinery", None, None, "IMAC", "common"),                     # 3:1 split
    "I02": ("CI2", "industrials", "transportation", None, None, "ITRN", "common"),
    "U01": ("CU1", "utilities", "electric_utilities", None, None, "UELE", "common"),              # dividends
    "U02": ("CU2", "utilities", "gas_utilities", None, None, "UGAS", "common"),                   # dividends
    "S01": ("CS1", "consumer_staples", "food_beverage", None, None, "SFOO", "common"),
    "S02": ("CS2", "consumer_staples", "household_products", None, None, "SHOU", "common"),
    "D01": ("CD1", "consumer_discretionary", "retail_specialty", None, None, "DRET", "common"),
    "D02": ("CD2", "consumer_discretionary", "apparel", None, None, "DAPP", "common"),             # illiquid
    "M01": ("CM1", "materials", "chemicals", None, None, "MCHE", "common"),
    "M02": ("CM2", "materials", "metals_mining", None, None, "MMIN", "common"),
    "E01": ("CE1", "energy", "oil_gas_producers", None, date(2006, 9, 29), "EPRO", "common"),     # bankrupt
    "E02": ("CE2", "energy", "oil_gas_services", None, None, "ESRV", "common"),
    "E03": ("CE3", "energy", "midstream", None, None, "EMID", "common"),
    "R01": ("CR1", "real_estate", "equity_reits", None, None, "RREI", "reit"),
    "R02": ("CR2", "real_estate", "real_estate_operators", None, None, "RROP", "common"),
    "C01": ("CC1", "communication_services", "telecom_carriers", None, None, "CTEL", "common"),
    "C02": ("CC2", "communication_services", "media_broadcasting", None, None, "CMED", "common"),
    "X01": ("CX1", None, None, None, None, "XBND", "etf"),                                         # a bond ETF
}
ILLIQUID = {"D02"}
DIVIDENDS = {"U01": 0.40, "U02": 0.35}                 # quarterly cash dividend per share
SPLIT = ("I01", date(2006, 5, 15), 3.0)
DELISTINGS = {   # id: (reason, announced, delisting return, return known)
    "E01": ("performance", date(2006, 9, 29), -0.60, date(2006, 10, 20)),
    "F01": ("acquisition", date(2007, 2, 15), 0.25, date(2007, 2, 15)),
    "T05": ("performance", date(2007, 3, 30), -0.45, date(2007, 4, 25)),
}
# company: (new category, effective, published). One announced in advance, one backfilled late.
RECLASSIFICATIONS = {
    "CT6": ("payments", date(2006, 3, 20), date(2006, 3, 1)),
    "CT7": ("automobiles", date(2005, 7, 1), date(2007, 2, 1)),
}


def sector_world(seed: int = 102, start: date = date(2004, 1, 2), end: date = date(2008, 12, 31), *,
                 planted_momentum: float = 0.0, planted_track: str = NON_TECHNOLOGY_TRACK,
                 momentum_lookback: int = 63, planted_from: date | None = None) -> World:
    """``planted_from``: the planted effect starts on this day (worlds identical before it, for leakage tests)."""
    if planted_track not in (TECHNOLOGY_TRACK, NON_TECHNOLOGY_TRACK):
        raise ValueError("planted_track is an equity research track")
    cal = calendar(start - timedelta(days=1), end + timedelta(days=40))
    rng = np.random.default_rng(seed)
    master, book = SecurityMaster(), PriceBook(cal)
    classes, fs = ClassificationHistory(), FundamentalStore(cal)
    days = np.array(cal.sessions_between(start, end), dtype=object)
    n = len(days)
    market = rng.normal(0.0003, 0.010, n)
    sector_f = {s: rng.normal(0.0, v[1], n) for s, v in SECTOR_RISK.items()}
    ids = list(_SPEC)
    live = {}
    base = {}
    for sid in ids:
        cid, sector, cat, lf, lt, tick, stype = _SPEC[sid]
        lf = lf or start
        live[sid] = np.array([lf <= d and (lt is None or d <= lt) for d in days])
        if sector is None:                                  # the bond ETF: low-volatility, no sector factor
            base[sid] = 0.0001 + rng.normal(0, 0.003, n)
        else:
            beta, _sv, iv = SECTOR_RISK[sector]
            base[sid] = 0.0002 + beta * market + sector_f[sector] + rng.normal(0, iv, n)
    ret = {sid: np.where(live[sid], base[sid], 0.0) for sid in ids}
    if planted_momentum:
        # causal: day t's addition depends only on returns through t-1, cross-sectionally within the planted track
        members = [sid for sid in ids if _SPEC[sid][2] and track_of(_SPEC[sid][2]) == planted_track]
        cum = {sid: np.cumsum(ret[sid]) for sid in members}
        for t in range(momentum_lookback + 1, n):
            if planted_from is not None and days[t] < planted_from:
                continue
            past = {sid: cum[sid][t - 1] - cum[sid][t - 1 - momentum_lookback] for sid in members
                    if live[sid][t] and live[sid][t - 1 - momentum_lookback]}
            if len(past) < 4:
                continue
            med = float(np.median(list(past.values())))
            for sid, p in past.items():
                ret[sid][t] += planted_momentum * np.sign(p - med)
            for sid in past:
                cum[sid][t:] = np.cumsum(ret[sid])[t:]
    for sid in ids:
        cid, sector, cat, lf, lt, tick, stype = _SPEC[sid]
        lf = lf or start
        master.add_company(Company(cid, f"Synthetic {cid}"))
        master.add_security(Security(sid, cid, "A", stype, "USD", listed_from=lf, listed_to=lt,
                                     known_from=lf - timedelta(days=21)))
        if cat is not None:
            classes.add(Classification(cid, cat, date(2000, 1, 1), None, known_from=date(2000, 1, 1),
                                       source="synthetic"))
        lv = live[sid]
        price = np.empty(n)
        p = 90.0 if sid == SPLIT[0] else (12.0 if sid in ILLIQUID else 30.0)
        div = DIVIDENDS.get(sid, 0.0)
        ex_days = set()
        if div:
            ex_days = {d for d in days if d.month in (3, 6, 9, 12) and 10 <= d.day <= 16 and d.weekday() == 0}
        actions = []
        for i, d in enumerate(days):
            if lv[i]:
                p = p * (1 + ret[sid][i])
                if d in ex_days:
                    p -= div                                   # the raw close drops by the cash paid
                    actions.append(CorporateAction(sid, "cash_dividend", d, d - timedelta(days=30), amount=div,
                                                   currency="USD", captured=d - timedelta(days=30)))
            price[i] = p
        closes = price.copy()
        if sid == SPLIT[0]:
            closes[days >= SPLIT[1]] /= SPLIT[2]
            actions.append(CorporateAction(sid, "split", SPLIT[1], SPLIT[1] - timedelta(days=40), ratio=SPLIT[2],
                                           captured=SPLIT[1] - timedelta(days=40)))
        vol = np.where(lv, (6e3 if sid in ILLIQUID else 6e5) * (1 + 0.6 * rng.random(n)), 0.0)
        for i, d in enumerate(days):
            if lv[i]:
                book.add_bar(Bar(sid, d, float(closes[i]), "USD", float(vol[i])))
        for a in actions:
            book.add_action(a)
        for d in days[::21]:
            if lv[days == d][0]:
                n_sh = 5e7 * (SPLIT[2] if sid == SPLIT[0] and d >= SPLIT[1] else 1)
                book.add_share_count(ShareCount(sid, d, n_sh, d + timedelta(days=5), "synthetic"))
        for q in _quarters(lf, end):
            pub = _ts(cal, cal.session_on_or_before(q + timedelta(days=35)), 16, 30)
            if lt is not None and pub.date() > lt:
                break
            rev = 100.0 * (1.01 ** ((q - date(2004, 1, 1)).days / 91)) * (1 + 0.1 * rng.normal())
            fs.add(Fact(cid, "revenue", q, "quarter", rev, "USD", pub, source="synthetic"))
        end_known = DELISTINGS[sid][1] if sid in DELISTINGS else None
        master.add_ticker(TickerInterval(sid, tick, "XNYS", lf, lt, known_from=lf, end_known_from=end_known))
    master.add_event(LifecycleEvent("H02", "ipo", date(2006, 4, 3), date(2006, 3, 10)))
    for sid, (reason, announced, dret, known) in DELISTINGS.items():
        last = _SPEC[sid][4]
        master.add_event(LifecycleEvent(sid, "delisting", last, announced, reason=reason))
        book.add_delisting_return(DelistingReturn(sid, last, dret, known, "synthetic"))
        book.mark_delisted(sid, last, reason)
    for cid, (cat, effective, published) in RECLASSIFICATIONS.items():
        classes.add(Classification(cid, cat, effective, None, known_from=published, source="synthetic vendor"))
    logp = {sid: np.where(live[sid], np.cumsum(ret[sid]), np.nan) for sid in ids}
    return mark_synthetic(World(cal, master, book, classes, fs, BorrowBook(), logp, days))


def sector_of_security(sid: str) -> str | None:
    """The fixture's original sector of a security (description only; the PIT category decides membership)."""
    return _SPEC[sid][1]
