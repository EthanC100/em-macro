"""Validation of a candidate dataset before it is stored (DESIGN.md section 3).

``validate`` returns a ``ValidationReport``: every issue with a code, a severity, the key it concerns and a short
detail. Errors stop ingestion (``manhattan.marketdata.ingest``); warnings are stored in the dataset's report. An
issue's detail names dates, fields and counts, never a price, so a report of licensed data can be read anywhere.

Codes (severity):

    unknown_instrument, unknown_contract, contract_root_mismatch,
    future_without_contract, contract_on_non_future                 error   reference data
    duplicate_conflict                                               error   one key, one vintage and one
                                                                             publication time, two values
    duplicate_exact                                                  warning identical rows (kept once)
    adjusted_price_stored                                            error   only unadjusted prices are stored
    missing_publication_time, unexpected_publication_time,
    source_mismatch                                                  error   rows that contradict their source's
                                                                             timestamp semantics or identity
    published_before_observed                                        error   timestamp inconsistency
    seen_before_published                                            error   captured before it existed
    observed_date_mismatch                                           error   observed_at is on another local date
    non_session_date                                                 error   not a session of the calendar
    before_first_trade, after_last_trade                             error   outside the contract's life
    lookahead_future_session                                         error   a session whose close is after the
                                                                             retrieval: data from the future
    lookahead_published_after_retrieval                              error   published after we retrieved it
    lookahead_seen_after_retrieval                                   error   first seen after the delivery's
                                                                             retrieval time
    ohlc_inconsistent                                                error   high/low do not bound open/close
    nonpositive_price                                                error for currencies and bonds; warning
                                                                             for futures (negative settlements
                                                                             happen)
    negative_count                                                   error   volume or open interest below zero
    missing_session                                                  warning an expected session has no row
    missing_fraction                                                 error   more than ``max_missing_fraction``
                                                                             of a series' sessions are missing
    stale_run                                                        warning ``stale_run`` or more sessions with
                                                                             an unchanged value
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from .provenance import SourceDescriptor
from .schema import (COUNT_FIELDS, PRICE_FIELDS, Contract, Instrument, Observation, parse_contract, session_dates)


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str           # error | warning
    key: tuple
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "key": list(self.key), "detail": self.detail}


@dataclass
class ValidationReport:
    issues: list = field(default_factory=list)
    rows_in: int = 0
    rows_out: int = 0

    def add(self, code, severity, key, detail):
        self.issues.append(Issue(code, severity, tuple(key), detail))

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def codes(self, severity: str | None = None) -> dict:
        out = defaultdict(int)
        for i in self.issues:
            if severity is None or i.severity == severity:
                out[i.code] += 1
        return dict(sorted(out.items()))

    def to_dict(self) -> dict:
        issues = sorted(self.issues, key=lambda i: (i.severity, i.code, i.key, i.detail))
        return {"ok": self.ok, "rows_in": self.rows_in, "rows_out": self.rows_out,
                "errors": self.codes("error"), "warnings": self.codes("warning"),
                "issues": [i.to_dict() for i in issues]}


@dataclass(frozen=True)
class Rules:
    stale_run: int = 5                    # sessions with an unchanged value before a warning
    stale_fields: tuple = ("settle", "close", "mid", "fixing")
    max_missing_fraction: float = 0.05    # of a series' expected sessions
    missing_fields: tuple = ("settle", "close", "mid", "fixing")   # fields whose gaps are counted
    calendars: dict | None = None         # instrument_id -> set of session dates (default: weekdays)


def _dedupe(obs, rep):
    seen, out = {}, []
    for o in sorted(obs, key=Observation.sort_key):
        k = o.sort_key()
        if k in seen:
            rep.add("duplicate_exact", "warning", o.key, "identical row delivered twice; kept once")
            continue
        seen[k] = o
        out.append(o)
    return out


def validate(observations, instruments: dict, contracts: dict, source: SourceDescriptor,
             retrieved_utc: datetime, rules: Rules = Rules()) -> tuple[list, ValidationReport]:
    """Check ``observations`` (from one delivery of ``source`` retrieved at ``retrieved_utc``). Returns the
    deduplicated, canonically ordered rows and the report."""
    rep = ValidationReport(rows_in=len(observations))
    obs = _dedupe(observations, rep)
    groups = defaultdict(list)                      # conflict detection: one key, one vintage, one publication
    for o in obs:
        inst: Instrument | None = instruments.get(o.instrument_id)
        if inst is None:
            rep.add("unknown_instrument", "error", o.key, f"instrument {o.instrument_id} is not in the reference data")
            continue
        if o.adjustment != "none":
            rep.add("adjusted_price_stored", "error", o.key, f"adjustment {o.adjustment!r}: store unadjusted prices "
                    "and derive adjusted series as of a date")
        if inst.asset_class == "future":
            if o.contract_id is None:
                rep.add("future_without_contract", "error", o.key, "a futures observation names its contract")
            else:
                c: Contract | None = contracts.get(o.contract_id)
                if parse_contract(o.contract_id)[0] != inst.root:
                    rep.add("contract_root_mismatch", "error", o.key, f"{o.contract_id} is not a {inst.root} contract")
                if c is None:
                    rep.add("unknown_contract", "error", o.key, f"{o.contract_id} is not in the contract table")
                else:
                    if o.session_date > c.last_trade:
                        rep.add("after_last_trade", "error", o.key, f"session {o.session_date} after last trade {c.last_trade}")
                    if c.first_trade and o.session_date < c.first_trade:
                        rep.add("before_first_trade", "error", o.key, f"session {o.session_date} before first trade")
        elif o.contract_id is not None:
            rep.add("contract_on_non_future", "error", o.key, f"{inst.asset_class} observations have no contract")
        cal = (rules.calendars or {}).get(o.instrument_id)
        if (o.session_date not in cal) if cal is not None else (o.session_date.weekday() >= 5):
            rep.add("non_session_date", "error", o.key, f"{o.session_date} is not a session")
        close = inst.close_utc(o.session_date)
        if close > retrieved_utc:
            rep.add("lookahead_future_session", "error", o.key,
                    f"session {o.session_date} closes after the retrieval time")
        if o.first_seen_utc > retrieved_utc:
            rep.add("lookahead_seen_after_retrieval", "error", o.key, "first seen after the delivery was retrieved")
        if o.observed_at_utc is not None:
            if inst.local_date(o.observed_at_utc) != o.session_date:
                rep.add("observed_date_mismatch", "error", o.key,
                        f"observed on local date {inst.local_date(o.observed_at_utc)}, session {o.session_date}")
        if source.timestamp_semantics == "vendor_receipt" and o.published_at_utc is None:
            rep.add("missing_publication_time", "error", o.key, "a vendor_receipt source row has no receipt time")
        if source.timestamp_semantics == "declared_delay" and o.published_at_utc is not None:
            rep.add("unexpected_publication_time", "error", o.key,
                    "a declared_delay source row carries a publication time: declare the source vendor_receipt")
        if o.source_id != source.source_id:
            rep.add("source_mismatch", "error", o.key, f"row from {o.source_id} in a {source.source_id} delivery")
        if o.published_at_utc is not None:
            if o.published_at_utc < (o.observed_at_utc or close):
                rep.add("published_before_observed", "error", o.key,
                        "published before the market produced it (observation time, or the declared close)")
            if o.first_seen_utc < o.published_at_utc:
                rep.add("seen_before_published", "error", o.key, "first seen before it was published")
            if o.published_at_utc > retrieved_utc:
                rep.add("lookahead_published_after_retrieval", "error", o.key, "published after the retrieval time")
        if o.field in PRICE_FIELDS and o.value <= 0:
            sev = "warning" if inst.asset_class == "future" else "error"
            rep.add("nonpositive_price", sev, o.key, f"{o.field} is zero or negative")
        if o.field in COUNT_FIELDS and o.value < 0:
            rep.add("negative_count", "error", o.key, f"{o.field} is negative")
        groups[(o.key, o.published_at_utc, o.first_seen_utc, o.settlement_status)].append(o)
    for (k, *_), rows in groups.items():
        if len({r.value for r in rows}) > 1:
            rep.add("duplicate_conflict", "error", k, f"{len(rows)} different values for one key in one vintage")
    _ohlc(obs, rep)
    _missing_and_stale(obs, instruments, contracts, rules, rep)
    rep.rows_out = len(obs)
    return obs, rep


def _latest(obs):
    """Per key, the value of the latest publication in this delivery (final over preliminary)."""
    best = {}
    for o in obs:
        rank = (o.settlement_status == "final", o.published_at_utc or o.first_seen_utc)
        if o.key not in best or rank >= best[o.key][0]:
            best[o.key] = (rank, o)
    return {k: v[1] for k, v in best.items()}


def _ohlc(obs, rep):
    bars = defaultdict(dict)
    for k, o in _latest(obs).items():
        bars[k[:3]][o.field] = o.value
    for k, b in sorted(bars.items()):
        lo, hi = b.get("low"), b.get("high")
        body = [b[f] for f in ("open", "close", "settle") if f in b]
        if lo is not None and hi is not None and lo > hi:
            rep.add("ohlc_inconsistent", "error", k, "low above high")
        elif body and ((lo is not None and lo > min(body)) or (hi is not None and hi < max(body))):
            # settle may legitimately sit outside a thin day's traded range on some venues: only open/close bind
            traded = [b[f] for f in ("open", "close") if f in b]
            if traded and ((lo is not None and lo > min(traded)) or (hi is not None and hi < max(traded))):
                rep.add("ohlc_inconsistent", "error", k, "open or close outside the high-low range")


def _missing_and_stale(obs, instruments, contracts, rules, rep):
    series = defaultdict(dict)
    for k, o in _latest(obs).items():
        if o.field in rules.missing_fields or o.field in rules.stale_fields:
            series[(o.instrument_id, o.contract_id or "", o.field)][o.session_date] = o.value
    for (iid, cid, fld), by_day in sorted(series.items()):
        days = sorted(by_day)
        cal = (rules.calendars or {}).get(iid)
        expected = [d for d in (sorted(cal) if cal is not None else session_dates(days[0], days[-1]))
                    if days[0] <= d <= days[-1]]
        if fld in rules.missing_fields and expected:
            missing = [d for d in expected if d not in by_day]
            for d in missing:
                rep.add("missing_session", "warning", (iid, cid, d.isoformat(), fld), "expected session has no row")
            if len(missing) > rules.max_missing_fraction * len(expected):
                rep.add("missing_fraction", "error", (iid, cid, "", fld),
                        f"{len(missing)} of {len(expected)} expected sessions missing")
        if fld in rules.stale_fields:
            run, start = 1, days[0]
            for a, b in zip(days, days[1:]):
                if by_day[b] == by_day[a]:
                    run += 1
                else:
                    if run >= rules.stale_run:
                        rep.add("stale_run", "warning", (iid, cid, start.isoformat(), fld),
                                f"{run} sessions unchanged from {start} to {a}")
                    run, start = 1, b
            if run >= rules.stale_run:
                rep.add("stale_run", "warning", (iid, cid, start.isoformat(), fld),
                        f"{run} sessions unchanged from {start} to {days[-1]}")
