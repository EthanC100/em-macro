"""Synthetic fixtures in the canonical row layout, and the generator of every synthetic test delivery.

**Canonical fixture CSV** (``FixtureAdapter``): columns ``instrument_id, contract_id, session_date, field, value``
and optional ``settlement_status, observed_at_utc, published_at_utc``. ``first_seen_utc`` is the retrieval time.

**Synthetic vendor-layout deliveries** (``synthetic_norgate_export``, ``synthetic_databento_statistics``): the
same layouts the real vendors deliver, filled with deterministic synthetic numbers for fictitious roots (``XA``,
``XB``). They exercise the real adapters without any licensed byte. Values depend on (seed, root, contract,
session) only, so two deliveries made on different days agree where they overlap, and a "revision" is an explicit
argument. Nothing here describes a market.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime, time, timedelta, timezone

from ..errors import SchemaError
from ..provenance import SourceDescriptor
from ..schema import (MONTH_CODES, Contract, Instrument, Observation, as_date, contract_id, parse_contract,
                      session_dates)
from .base import Adapter, ParseResult

UTC = timezone.utc

SYNTHETIC_EOD = SourceDescriptor(source_id="synthetic_eod", vendor="synthetic", dataset="canonical fixture",
                                 licence="synthetic", redistribution=True, timestamp_semantics="declared_delay",
                                 declared_delay_minutes=60, grace_minutes=24 * 60)
SYNTHETIC_RECEIPT = SourceDescriptor(source_id="synthetic_receipt", vendor="synthetic",
                                     dataset="canonical fixture with receipt times", licence="synthetic",
                                     redistribution=True, timestamp_semantics="vendor_receipt")


class FixtureAdapter(Adapter):
    name, version = "fixture_csv", "1"

    def __init__(self, source: SourceDescriptor = SYNTHETIC_EOD):
        if source.licence != "synthetic":
            raise SchemaError("the fixture adapter reads synthetic fixtures only")
        self.source = source

    def parse(self, files, request, retrieved_utc, gate) -> ParseResult:
        out = []
        for name in sorted(files):
            for r in csv.DictReader(io.StringIO(files[name].decode("utf-8"))):
                d = as_date(r["session_date"], "session_date")
                if not gate.admit(r["instrument_id"], d):
                    continue
                if r["value"].strip() == "":
                    continue                                   # a gap is no observation
                out.append(Observation(instrument_id=r["instrument_id"], contract_id=r.get("contract_id") or None,
                                       session_date=d, field=r["field"], value=float(r["value"]),
                                       settlement_status=r.get("settlement_status") or "not_applicable",
                                       observed_at_utc=r.get("observed_at_utc") or None,
                                       published_at_utc=r.get("published_at_utc") or None,
                                       first_seen_utc=retrieved_utc, source_id=self.source.source_id))
        return ParseResult(out)


# ---------------------------------------------------------------- synthetic reference data

def synthetic_instruments() -> dict:
    """Two fictitious futures roots, one currency pair and one cash bond, in two fence domains."""
    insts = [
        Instrument("SYN_XA", "future", "futures_daily", "America/Chicago", time(13, 30), "USD", "SYNX", root="XA",
                   multiplier=1000.0, tick=0.01),
        Instrument("SYN_XB", "future", "futures_daily", "Europe/Berlin", time(17, 15), "EUR", "SYNE", root="XB",
                   multiplier=1000.0, tick=0.01),
        Instrument("SYN_FXAB", "fx_spot", "fx_daily", "America/New_York", time(17, 0), "BBB", "SYNFX",
                   base="AAA", quote="BBB"),
        Instrument("SYN_BOND10", "bond_cash", "bonds_daily", "Europe/London", time(16, 30), "GBP", "SYNB",
                   price_basis="clean", maturity=date(2035, 6, 30), coupon=4.0),
    ]
    return {i.instrument_id: i for i in insts}


def synthetic_contracts(root: str, instrument_id: str, first_year: int, last_year: int,
                        months=(3, 6, 9, 12)) -> dict:
    """Quarterly contracts: last trade on the third Friday of the contract month, first notice five weekdays
    before it, first trade 15 months before."""
    out = {}
    for y in range(first_year, last_year + 1):
        for m in months:
            d = date(y, m, 1)
            fridays = [d + timedelta(days=k) for k in range(31)
                       if (d + timedelta(days=k)).month == m and (d + timedelta(days=k)).weekday() == 4]
            ltd = fridays[2]
            fnd = ltd - timedelta(days=7)
            cid = contract_id(root, y, m)
            ft = date(y - 1 if m > 3 else y - 2, (m + 9 - 1) % 12 + 1, 1)
            out[cid] = Contract(cid, instrument_id, last_trade=ltd, first_notice=fnd, first_trade=ft)
    return out


def _synthetic_fraction(seed: int, *parts) -> float:
    """A deterministic number in [0, 1) from the parts (SHA-256; no RNG state, so order never matters)."""
    h = hashlib.sha256(json.dumps([seed, *map(str, parts)]).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def synthetic_price(seed: int, root: str, cid: str, d: date) -> float:
    """A synthetic settlement path: a slow sinusoid in time plus a per-contract term structure offset plus noise,
    rounded to the 0.01 tick. Depends on (seed, root, contract, day) only."""
    import math
    t = (d - date(2000, 1, 3)).days
    _, y, m = parse_contract(cid)
    months_out = (y * 12 + m) - (d.year * 12 + d.month)
    base = 50.0 + 10.0 * math.sin(t / 300.0 + _synthetic_fraction(seed, root) * 6) + 0.15 * months_out
    return round(base + 2.0 * (_synthetic_fraction(seed, root, cid, d) - 0.5), 2)


# ---------------------------------------------------------------- synthetic Norgate-layout export

def synthetic_norgate_export(contracts: dict, asof: date, seed: int = 0, *, drop=frozenset(), revise=None,
                             generated_utc: datetime | None = None, crlf: bool = True,
                             market_of=lambda cid: parse_contract(cid)[0]) -> dict:
    """Files of a Norgate export (scripts/norgate_export.py layout) for ``contracts`` with sessions up to
    ``asof``: ``contracts/<MARKET>/<CONTRACT>.csv`` (date,open,high,low,close,volume,open_interest; close is the
    settlement), ``manifest.csv``, ``manifest.json`` and ``metadata.csv``. ``drop``: {(contract, date)} withheld;
    ``revise``: {(contract, date): settle} replaced (a vendor revision in a later snapshot)."""
    revise = revise or {}
    nl = "\r\n" if crlf else "\n"
    files, entries, meta_rows = {}, [], []
    for cid in sorted(contracts):
        c = contracts[cid]
        root = parse_contract(cid)[0]
        days = [d for d in session_dates(c.first_trade or date(2000, 1, 3), min(c.last_trade, asof))]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator=nl)
        w.writerow(["date", "open", "high", "low", "close", "volume", "open_interest"])
        n, first, last = 0, None, None
        for d in days:
            if (cid, d) in drop:
                continue
            s = revise.get((cid, d), synthetic_price(seed, root, cid, d))
            spread = round(0.2 + _synthetic_fraction(seed, "rng", cid, d), 2)
            o = round(s + 0.5 * (_synthetic_fraction(seed, "o", cid, d) - 0.5), 2)
            hi, lo = round(max(o, s) + spread, 2), round(min(o, s) - spread, 2)
            vol = int(1000 * _synthetic_fraction(seed, "v", cid, d))
            oi = int(5000 * _synthetic_fraction(seed, "oi", cid, d))
            w.writerow([d.isoformat(), f"{o:.2f}", f"{hi:.2f}", f"{lo:.2f}", f"{s:.2f}", vol, oi])
            n, first, last = n + 1, first or d, d
        rel = f"contracts/{market_of(cid)}/{cid}.csv"
        data = buf.getvalue().encode("utf-8")
        files[rel] = data
        entries.append({"file": rel, "market": market_of(cid), "norgate_symbol": market_of(cid), "contract": cid,
                        "rows": n, "first_date": str(first or ""), "last_date": str(last or ""),
                        "missing_fields": "", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        live = c.last_trade > asof
        meta_rows.append({"market": market_of(cid), "norgate_symbol": market_of(cid), "contract": cid,
                          "as_of": asof.isoformat(), "first_quoted_date": str(first or ""),
                          "last_quoted_date": (c.last_trade if live else (last or c.last_trade)).isoformat(),
                          "first_notice_date": c.first_notice.isoformat() if c.first_notice else "",
                          "point_value": "1000", "tick_size": "0.01", "lowest_ever_tick_size": "0.01",
                          "currency": "USD", "exchange": "SYNX", "name": f"Synthetic {root}"})
    mbuf = io.StringIO()
    cols = ["file", "market", "norgate_symbol", "contract", "rows", "first_date", "last_date", "missing_fields",
            "bytes", "sha256"]
    w = csv.DictWriter(mbuf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(entries)
    files["manifest.csv"] = mbuf.getvalue().encode("utf-8")
    gen = generated_utc or datetime.combine(asof + timedelta(days=1), time(2, 0), tzinfo=UTC)
    files["manifest.json"] = json.dumps({"generated_utc": gen.isoformat(timespec="seconds"),
                                         "source": "SYNTHETIC fixture in the Norgate export layout",
                                         "columns": ["date", "open", "high", "low", "close", "volume",
                                                     "open_interest"],
                                         "close_is": "settlement price", "adjustment": "none",
                                         "files": len(entries), "entries": entries}, indent=1).encode("utf-8")
    mcols = ["market", "norgate_symbol", "contract", "as_of", "first_quoted_date", "last_quoted_date",
             "first_notice_date", "point_value", "tick_size", "lowest_ever_tick_size", "currency", "exchange", "name"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=mcols, lineterminator="\n")
    w.writeheader()
    w.writerows(meta_rows)
    files["metadata.csv"] = buf.getvalue().encode("utf-8")
    return files


# ---------------------------------------------------------------- synthetic Databento statistics export

def _ns(t: datetime) -> int:
    return int(t.timestamp()) * 1_000_000_000 + t.microsecond * 1000


def synthetic_databento_statistics(contracts: dict, inst: Instrument, start: date, end: date, seed: int = 0, *,
                                   final_delay=timedelta(hours=11), prelim_delay=timedelta(minutes=1),
                                   revise_final=None) -> tuple[bytes, dict]:
    """A CSV in the layout of a Databento ``statistics`` record export (``DBNStore.to_csv`` with integer
    nanosecond timestamps and fixed-point prices at 1e-9): one preliminary settlement (stat_flags 0) published
    ``prelim_delay`` after the close and one final settlement (stat_flags 1) published ``final_delay`` after it,
    plus cleared volume (stat_type 6) and open interest (stat_type 9). ``revise_final``: {(contract, date): settle}
    where the final differs from the preliminary. Returns (bytes, symbol_map raw symbol -> contract id)."""
    revise_final = revise_final or {}
    rows, symbol_map = [], {}
    for cid in sorted(contracts):
        c = contracts[cid]
        root, y, m = parse_contract(cid)
        raw = f"{root}{MONTH_CODES[m - 1]}{y % 100:02d}"
        symbol_map[raw] = cid
        for d in session_dates(max(start, c.first_trade or start), min(end, c.last_trade)):
            close = inst.close_utc(d)
            ref = _ns(datetime.combine(d, time(0), tzinfo=UTC))
            prelim = synthetic_price(seed, root, cid, d)
            final = revise_final.get((cid, d), prelim)
            for stat, flags, px, qty, recv in (
                    (3, 0, prelim, 0, close + prelim_delay),
                    (3, 1, final, 0, close + final_delay),
                    (6, 1, 0, int(1000 * _synthetic_fraction(seed, "v", cid, d)), close + final_delay),
                    (9, 1, 0, int(5000 * _synthetic_fraction(seed, "oi", cid, d)), close + final_delay)):
                rows.append([_ns(recv), _ns(recv) - 1000, 24, 1, 1000 + len(symbol_map), ref,
                             int(round(px * 1e9)) if stat == 3 else 9223372036854775807, qty, len(rows), 0, stat,
                             0, 1, flags, raw])
    rows.sort(key=lambda r: (r[0], r[-1], r[10]))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ts_recv", "ts_event", "rtype", "publisher_id", "instrument_id", "ts_ref", "price", "quantity",
                "sequence", "ts_in_delta", "stat_type", "channel_id", "update_action", "stat_flags", "symbol"])
    w.writerows(rows)
    return buf.getvalue().encode("utf-8"), symbol_map
