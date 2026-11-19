"""Databento ``statistics`` records (GLBX.MDP3 and other venues): settlements with receipt timestamps.

Input: a CSV export of ``statistics`` records (``DBNStore.to_csv``), with columns ``ts_recv, ts_event, rtype,
publisher_id, instrument_id, ts_ref, price, quantity, sequence, ts_in_delta, stat_type, channel_id,
update_action, stat_flags, symbol``. Timestamps are integer nanoseconds since the epoch (``ts_format: "ns"``) or
ISO 8601 (``"iso"``); prices are fixed point at 1e-9 (``price_format: "fixed_1e9"``) or decimal (``"decimal"``).
The request says which: nothing is inferred.

Mapping (Databento ``StatType``): 3 settlement price -> ``settle`` (``stat_flags`` bit 0 set: ``final``; clear:
``preliminary``), 6 cleared volume -> ``volume``, 9 open interest -> ``open_interest`` (both from ``quantity``).
Other stat types are counted in the notes and skipped. The session date is the UTC date of ``ts_ref`` (the trading
date the statistic refers to, as ``em_macro.commod_databento.final_settlements`` reads it). ``ts_recv`` is the
publication time: when Databento received the message. ``ts_event`` is the message's send time, which for a final
settlement is after midnight, so it is **not** taken as the observation time (that stays the instrument's declared
close). Raw symbols map to contract ids through ``request["symbol_map"]`` (the planned request knows them); an
unknown symbol is refused, never decoded by guessing the decade.

Preliminary then final settlement for one key are a **revision with real timestamps**: a point-in-time read
before the final's receipt time sees the preliminary value.

**Licence.** Databento passes on CME's terms; settlements are stored only in em-macro-data (ledger/settlements.py).
The descriptor is ``licensed``.

**Fetch.** Refused. A historical request costs money (hard rule 11) and shares the US$1 daily cap and spend log of
``ledger.settlements``; any Manhattan purchase is Ethan's decision (ETHAN_ACTIONS item 8). ``plan_request`` builds
the request parameters (pure; no network), so the cost can be quoted by the authorised path (DESIGN.md section 9).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone

from ..errors import SchemaError
from ..provenance import SourceDescriptor
from ..schema import MONTH_CODES, Observation, parse_contract
from .base import Adapter, ParseResult

UTC = timezone.utc
UNDEF_PRICE = 9223372036854775807
STAT_FIELD = {3: "settle", 6: "volume", 9: "open_interest"}
DATASET, SCHEMA = "GLBX.MDP3", "statistics"


def databento_source(dataset: str = DATASET) -> SourceDescriptor:
    return SourceDescriptor(source_id=f"databento_{dataset.lower().replace('.', '_')}_statistics",
                            vendor="Databento", dataset=f"{dataset} statistics", licence="licensed",
                            redistribution=False, timestamp_semantics="vendor_receipt",
                            licence_reference="Databento terms, passing on the venue's licence (CME); "
                                              "docs/manhattan/AUDIT.md section 1.3")


def plan_request(contract_ids, start: date, end: date, dataset: str = DATASET) -> dict:
    """Parameters for ``Historical.timeseries.get_range`` (and ``metadata.get_cost``), plus the symbol map the
    parser needs. Raw symbols use a two-digit year; Databento's resolution of one- versus two-digit symbols over a
    date range is checked by the authorised fetch, as em_macro.commod_databento.resolve_symbols does."""
    symbol_map = {}
    for cid in sorted(contract_ids):
        root, y, m = parse_contract(cid)
        symbol_map[f"{root}{MONTH_CODES[m - 1]}{y % 100:02d}"] = cid
    return {"dataset": dataset, "schema": SCHEMA, "stype_in": "raw_symbol", "symbols": sorted(symbol_map),
            "start": start.isoformat(), "end": end.isoformat(), "symbol_map": symbol_map,
            "ts_format": "ns", "price_format": "fixed_1e9"}


def _ts(raw: str, fmt: str) -> datetime:
    if fmt == "ns":
        ns = int(raw)
        return datetime.fromtimestamp(ns // 1_000_000_000, UTC).replace(microsecond=(ns % 1_000_000_000) // 1000)
    if fmt == "iso":
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if t.tzinfo is None:
            raise SchemaError("Databento ISO timestamps carry a zone")
        return t.astimezone(UTC)
    raise SchemaError("ts_format must be 'ns' or 'iso'")


class DatabentoStatisticsAdapter(Adapter):
    name, version = "databento_statistics", "1"

    def __init__(self, instruments: dict, source: SourceDescriptor | None = None):
        self.source = source or databento_source()
        if self.source.timestamp_semantics != "vendor_receipt":
            raise SchemaError("Databento records carry receipt times: vendor_receipt semantics")
        self.by_root = {i.root: i.instrument_id for i in instruments.values() if i.asset_class == "future"}

    def parse(self, files, request, retrieved_utc, gate) -> ParseResult:
        symbol_map = request.get("symbol_map")
        if not isinstance(symbol_map, dict) or not symbol_map:
            raise SchemaError("a Databento parse needs request['symbol_map'] (raw symbol -> contract id)")
        ts_fmt, px_fmt = request.get("ts_format"), request.get("price_format")
        if px_fmt not in ("fixed_1e9", "decimal"):
            raise SchemaError("price_format must be 'fixed_1e9' or 'decimal'")
        obs, skipped = [], {}
        for name in sorted(files):
            for r in csv.DictReader(io.StringIO(files[name].decode("utf-8"))):
                stat = int(r["stat_type"])
                if stat not in STAT_FIELD:
                    skipped[stat] = skipped.get(stat, 0) + 1
                    continue
                cid = symbol_map.get(r["symbol"])
                if cid is None:
                    raise SchemaError(f"raw symbol {r['symbol']!r} is not in the request's symbol map")
                iid = self.by_root.get(parse_contract(cid)[0])
                if iid is None:
                    raise SchemaError(f"no instrument has root {parse_contract(cid)[0]}")
                d = _ts(r["ts_ref"], ts_fmt).date()
                if not gate.admit(iid, d):                       # before any value is converted
                    continue
                fld = STAT_FIELD[stat]
                if fld == "settle":
                    raw = int(r["price"]) if px_fmt == "fixed_1e9" else None
                    if raw == UNDEF_PRICE:
                        continue
                    value = raw / 1e9 if raw is not None else float(r["price"])
                    status = "final" if int(r["stat_flags"]) & 1 else "preliminary"
                else:
                    value, status = float(int(r["quantity"])), "not_applicable"
                obs.append(Observation(instrument_id=iid, contract_id=cid, session_date=d, field=fld,
                                       value=round(value, 9), settlement_status=status,
                                       published_at_utc=_ts(r["ts_recv"], ts_fmt),
                                       first_seen_utc=retrieved_utc, source_id=self.source.source_id))
        notes = [f"skipped stat_type {k}: {v} records" for k, v in sorted(skipped.items())]
        return ParseResult(obs, notes=notes)
