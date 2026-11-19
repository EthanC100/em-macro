"""The canonical historical market-data schema (docs/manhattan/marketdata/DESIGN.md section 2).

Four record types. Every one is a frozen dataclass whose constructor validates it, so a record that exists is a
record that fits.

``Instrument``   what is traded or quoted: a futures root (one row per root, not per contract), a spot or forward
                 currency pair, a cash bond, a commodity spot price or an index. Carries the exchange time zone and
                 session close needed to place an observation in time, and the fence ``domain``
                 (``manhattan.roles``) its observations belong to.
``Contract``     one listed futures contract of a root: ``<ROOT>-<YYYY><month code>`` (Norgate's own form), with
                 its last trade date and, where the exchange has one, its first notice date.
``Observation``  one value of one field of one instrument (and contract) for one session, in one vintage. Three
                 times are kept apart:

                     session_date        the trading day the value is about (the period; what the fence reads)
                     observed_at_utc     when the market produced it (the settlement or close), if known
                     published_at_utc    when the vendor or exchange made it available, if the source says so
                     first_seen_utc      when this project first captured the bytes that hold it (always known:
                                         the retrieval time of the raw file)

                 The research availability time is derived from those, never stored as a free field
                 (``manhattan.marketdata.timing``).
``AdjustmentEvent``  a change that makes raw prices on the two sides of a date not comparable: a roll between
                 contracts, a contract multiplier, tick or price-unit change, a currency redenomination. Each has
                 the time it was announced, so an adjusted series can be built only from events known at the time.

Prices are stored **unadjusted**, per contract, in the exchange's quoting units. Adjusted or continuous series are
derived, as of a date, by ``manhattan.marketdata.continuous``; they are never stored as if they were observations
(``adjustment`` is ``"none"`` on every stored observation; anything else is refused at validation).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import SchemaError

UTC = timezone.utc
SCHEMA_VERSION = 1
MONTH_CODES = "FGHJKMNQUVXZ"

ASSET_CLASSES = ("future", "fx_spot", "fx_forward", "bond_cash", "commodity_spot", "index")
FIELDS = ("open", "high", "low", "close", "settle", "volume", "open_interest", "bid", "ask", "mid", "yield",
          "fixing")
PRICE_FIELDS = ("open", "high", "low", "close", "settle", "bid", "ask", "mid", "fixing")
COUNT_FIELDS = ("volume", "open_interest")
PRICE_BASES = ("exchange_units", "clean", "dirty", "percent_of_par", "rate")
ADJUSTMENT_KINDS = ("roll", "multiplier_change", "tick_change", "price_unit_change", "redenomination")
SETTLEMENT_STATUS = ("final", "preliminary", "not_applicable")
_CONTRACT_RE = re.compile(r"^([A-Z0-9]{1,8})-(\d{4})([FGHJKMNQUVXZ])$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def _text(v, name: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise SchemaError(f"{name} must be a non-empty string")
    return v


def _ident(v, name: str) -> str:
    if not isinstance(v, str) or not _ID_RE.match(v):
        raise SchemaError(f"{name} must match {_ID_RE.pattern}")
    return v


def as_date(v, name: str = "date") -> date:
    if isinstance(v, datetime):
        raise SchemaError(f"{name} is a date, not a time")
    if isinstance(v, date):
        return v
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        try:
            return date.fromisoformat(v)
        except ValueError:
            pass
    raise SchemaError(f"{name} must be a date YYYY-MM-DD")


def as_utc(v, name: str) -> datetime | None:
    """An aware time, normalised to UTC. Naive times are refused: a time without a zone is not a time."""
    if v is None:
        return None
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise SchemaError(f"{name} must be an ISO 8601 time with a zone") from None
    if not isinstance(v, datetime):
        raise SchemaError(f"{name} must be a time")
    if v.tzinfo is None or v.utcoffset() is None:
        raise SchemaError(f"{name} has no time zone; naive times are refused")
    return v.astimezone(UTC)


def iso(t: datetime | None) -> str | None:
    """Canonical UTC text of a time: microseconds always shown, so text order is time order."""
    return None if t is None else t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def contract_id(root: str, year: int, month: int) -> str:
    if not 1 <= month <= 12:
        raise SchemaError("contract month must be 1-12")
    return f"{root}-{year:04d}{MONTH_CODES[month - 1]}"


def parse_contract(cid: str) -> tuple[str, int, int]:
    m = _CONTRACT_RE.match(cid or "")
    if not m:
        raise SchemaError(f"contract id {cid!r} is not <ROOT>-<YYYY><month code>")
    return m.group(1), int(m.group(2)), MONTH_CODES.index(m.group(3)) + 1


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    asset_class: str
    domain: str                      # the fence domain (manhattan.roles), e.g. "futures_daily", "fx_daily"
    exchange_tz: str                 # IANA zone of the venue whose session close dates the observation
    session_close: time              # local close (settlement) time of a session
    currency: str
    exchange: str = ""
    root: str | None = None          # futures: the root in contract ids
    multiplier: float | None = None  # futures: currency units per 1.0 of price per contract
    tick: float | None = None
    base: str | None = None          # fx: base currency (price = quote currency per one base)
    quote: str | None = None
    price_basis: str = "exchange_units"
    maturity: date | None = None     # bond_cash
    coupon: float | None = None      # bond_cash, percent per year

    def __post_init__(self):
        _ident(self.instrument_id, "instrument_id")
        if self.asset_class not in ASSET_CLASSES:
            raise SchemaError(f"asset_class must be one of {ASSET_CLASSES}")
        _ident(self.domain, "domain")
        try:
            ZoneInfo(_text(self.exchange_tz, "exchange_tz"))
        except ZoneInfoNotFoundError:
            raise SchemaError(f"unknown time zone {self.exchange_tz}") from None
        if not isinstance(self.session_close, time) or self.session_close.tzinfo is not None:
            raise SchemaError("session_close is a local time without a zone (the zone is exchange_tz)")
        if not re.fullmatch(r"[A-Z]{3}", self.currency or ""):
            raise SchemaError("currency must be a three-letter code")
        if self.price_basis not in PRICE_BASES:
            raise SchemaError(f"price_basis must be one of {PRICE_BASES}")
        if self.asset_class == "future":
            if not self.root or not re.fullmatch(r"[A-Z0-9]{1,8}", self.root):
                raise SchemaError("a future needs a root of 1-8 capitals or digits")
            for name in ("multiplier", "tick"):
                v = getattr(self, name)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or not v > 0 or not math.isfinite(v):
                    raise SchemaError(f"a future needs a positive {name}")
        elif self.root is not None:
            raise SchemaError("only futures have a root")
        if self.asset_class in ("fx_spot", "fx_forward"):
            for name in ("base", "quote"):
                if not re.fullmatch(r"[A-Z]{3}", getattr(self, name) or ""):
                    raise SchemaError(f"a currency pair needs a three-letter {name}")
            if self.base == self.quote:
                raise SchemaError("base and quote must differ")
            if self.currency != self.quote:
                raise SchemaError("a currency pair is priced in its quote currency")
        if self.asset_class == "bond_cash":
            if self.maturity is None or self.price_basis not in ("clean", "dirty", "percent_of_par", "rate"):
                raise SchemaError("a cash bond needs a maturity and a clean, dirty, percent_of_par or rate basis")
            object.__setattr__(self, "maturity", as_date(self.maturity, "maturity"))

    def close_utc(self, session_date: date) -> datetime:
        """The session's close as a UTC time (DST-aware)."""
        return datetime.combine(session_date, self.session_close, tzinfo=ZoneInfo(self.exchange_tz)).astimezone(UTC)

    def local_date(self, t: datetime) -> date:
        return t.astimezone(ZoneInfo(self.exchange_tz)).date()

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["session_close"] = self.session_close.isoformat()
        d["maturity"] = self.maturity.isoformat() if self.maturity else None
        return d


@dataclass(frozen=True)
class Contract:
    contract_id: str
    instrument_id: str
    last_trade: date
    first_notice: date | None = None
    first_trade: date | None = None

    def __post_init__(self):
        parse_contract(self.contract_id)
        _ident(self.instrument_id, "instrument_id")
        object.__setattr__(self, "last_trade", as_date(self.last_trade, "last_trade"))
        for name in ("first_notice", "first_trade"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, as_date(getattr(self, name), name))
        if self.first_trade and self.first_trade > self.last_trade:
            raise SchemaError(f"{self.contract_id}: first trade after last trade")

    @property
    def root(self) -> str:
        return parse_contract(self.contract_id)[0]

    @property
    def notice(self) -> date:
        """The first day a long holder can be made to take delivery, or the last trade: whichever is first."""
        return min(self.first_notice, self.last_trade) if self.first_notice else self.last_trade


@dataclass(frozen=True)
class Observation:
    instrument_id: str
    session_date: date
    field: str
    value: float
    source_id: str
    first_seen_utc: datetime
    contract_id: str | None = None
    observed_at_utc: datetime | None = None
    published_at_utc: datetime | None = None
    settlement_status: str = "not_applicable"
    adjustment: str = "none"

    def __post_init__(self):
        _ident(self.instrument_id, "instrument_id")
        _ident(self.source_id, "source_id")
        object.__setattr__(self, "session_date", as_date(self.session_date, "session_date"))
        if self.field not in FIELDS:
            raise SchemaError(f"field must be one of {FIELDS}")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise SchemaError("value must be a number")
        v = float(self.value)
        if not math.isfinite(v):
            raise SchemaError("value must be finite (a missing value is no observation, not NaN)")
        object.__setattr__(self, "value", v)
        if self.contract_id is not None:
            parse_contract(self.contract_id)
        for name in ("first_seen_utc", "observed_at_utc", "published_at_utc"):
            object.__setattr__(self, name, as_utc(getattr(self, name), name))
        if self.first_seen_utc is None:
            raise SchemaError("first_seen_utc (the retrieval time of the raw bytes) is required")
        if self.settlement_status not in SETTLEMENT_STATUS:
            raise SchemaError(f"settlement_status must be one of {SETTLEMENT_STATUS}")
        if not isinstance(self.adjustment, str):
            raise SchemaError("adjustment must be a string")

    @property
    def key(self) -> tuple:
        """What the value is about. Two observations with one key and different values are a revision (across
        vintages or a preliminary/final pair) or a conflict (within one vintage at one publication time)."""
        return (self.instrument_id, self.contract_id or "", self.session_date.isoformat(), self.field)

    def sort_key(self) -> tuple:
        return self.key + (iso(self.published_at_utc) or "", iso(self.first_seen_utc), self.source_id,
                           self.settlement_status, float(self.value).hex())

    def to_row(self) -> dict:
        return {"instrument_id": self.instrument_id, "contract_id": self.contract_id or "",
                "session_date": self.session_date.isoformat(), "field": self.field, "value": repr(self.value),
                "settlement_status": self.settlement_status, "adjustment": self.adjustment,
                "observed_at_utc": iso(self.observed_at_utc) or "", "published_at_utc": iso(self.published_at_utc) or "",
                "first_seen_utc": iso(self.first_seen_utc), "source_id": self.source_id}

    @classmethod
    def from_row(cls, r: dict) -> "Observation":
        return cls(instrument_id=r["instrument_id"], contract_id=r["contract_id"] or None,
                   session_date=r["session_date"], field=r["field"], value=float(r["value"]),
                   settlement_status=r["settlement_status"], adjustment=r["adjustment"],
                   observed_at_utc=r["observed_at_utc"] or None, published_at_utc=r["published_at_utc"] or None,
                   first_seen_utc=r["first_seen_utc"], source_id=r["source_id"])


ROW_COLUMNS = ("instrument_id", "contract_id", "session_date", "field", "value", "settlement_status", "adjustment",
               "observed_at_utc", "published_at_utc", "first_seen_utc", "source_id")


@dataclass(frozen=True)
class AdjustmentEvent:
    instrument_id: str
    kind: str
    effective_date: date             # first session on which the new basis applies
    announced_utc: datetime          # when the change became public; an adjusted series uses it only after this
    factor: float = 1.0              # new-basis value = old-basis value * factor + offset
    offset: float = 0.0
    from_contract: str | None = None # roll: the contract held before effective_date
    to_contract: str | None = None
    reference: str = ""              # where the event is documented (exchange notice, vendor field)

    def __post_init__(self):
        _ident(self.instrument_id, "instrument_id")
        if self.kind not in ADJUSTMENT_KINDS:
            raise SchemaError(f"kind must be one of {ADJUSTMENT_KINDS}")
        object.__setattr__(self, "effective_date", as_date(self.effective_date, "effective_date"))
        object.__setattr__(self, "announced_utc", as_utc(self.announced_utc, "announced_utc"))
        if self.announced_utc is None:
            raise SchemaError("an adjustment needs the time it was announced")
        for name in ("factor", "offset"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise SchemaError(f"{name} must be a finite number")
        if self.factor == 0:
            raise SchemaError("factor cannot be zero")
        if self.kind == "roll":
            if not (self.from_contract and self.to_contract):
                raise SchemaError("a roll names the contract held before and after")
            parse_contract(self.from_contract)
            parse_contract(self.to_contract)
        elif not self.reference.strip():
            raise SchemaError("a non-roll adjustment needs a reference (exchange notice or vendor field)")


def session_dates(start: date, end: date, holidays=frozenset()) -> list[date]:
    """Weekdays from ``start`` to ``end`` that are not in ``holidays``: the default expected-session calendar.
    An exchange calendar can be passed to validation instead."""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            out.append(d)
        d += timedelta(days=1)
    return out
