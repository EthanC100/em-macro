"""Norgate Futures end-of-day: the export layout written by ``scripts/norgate_export.py`` on the Windows server.

Input (one snapshot folder, as bytes keyed by relative path):

    manifest.csv                      file, market, norgate_symbol, contract, rows, first_date, last_date,
                                      missing_fields, bytes, sha256
    manifest.json                     generated_utc, close_is ("settlement price"), adjustment ("none"), entries
    contracts/<MARKET>/<CONTRACT>.csv date, open, high, low, close, volume, open_interest (CRLF; unadjusted;
                                      close is the settlement)
    metadata.csv (optional; the      market, contract, as_of, first_quoted_date, last_quoted_date,
    ``*_metadata`` snapshot)          first_notice_date, point_value, tick_size, ...

Checks before any value is read: every contract file is listed in ``manifest.csv`` with the same byte count and
SHA-256 (a file not listed, or listed and absent, is refused); ``manifest.json`` says the close is the settlement
and the prices are unadjusted; ``generated_utc`` is not after the retrieval time (an export cannot be retrieved
before it was made); each market maps to a known instrument (``market_map``; never guessed).

Mapping: ``close`` -> field ``settle`` (Norgate's close is the settlement price), ``open``/``high``/``low`` ->
themselves, ``volume``/``open_interest`` -> themselves. Contract ids keep Norgate's ``-<YYYY><month>`` suffix on the
instrument's root.

**Timing.** Norgate's export carries a session date only and no publication time, so the source is
``declared_delay``. Its delay is **not** declared here: Norgate does not publish a per-row release time, and the
right assumption (and who accepts it) is Ethan's (DESIGN.md section 9). Until ``norgate_source`` is given a delay,
its reference and the owner's approval, a Norgate dataset can be ingested, validated and stored, but no
availability can be computed and it cannot become a point-in-time store. Every row of a snapshot that predates the
snapshot's retrieval is **backfill** (reconstructed: no confirmatory evidential weight), because nobody captured it
when it was published.

**Contracts.** ``metadata.csv`` gives first and last quoted dates and first notice dates. For an expired contract
Norgate's last quoted date is its final bar, which this adapter takes as the last trade date and flags in the notes
(``em_macro.commod_data`` documents the exceptions: lean hogs, stray far months). Without metadata the caller
supplies the contract table.

**Licence.** Norgate Personal Use: no redistribution (hard rule 7). The descriptor is ``licensed``; the ingestion
pipeline refuses to write its rows anywhere inside this repository.

**Fetch.** None. Norgate data exist only through Norgate Data Updater on the Windows server
(docs/infra/norgate_pipeline.md); this adapter reads what that server exported.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime

from ..errors import ProvenanceError, SchemaError
from ..provenance import SourceDescriptor
from ..schema import Contract, Observation, as_date, as_utc, contract_id, parse_contract
from .base import Adapter, ParseResult

FIELD_MAP = {"open": "open", "high": "high", "low": "low", "close": "settle", "volume": "volume",
             "open_interest": "open_interest"}
COLUMNS = ["date", "open", "high", "low", "close", "volume", "open_interest"]


def norgate_source(*, delay_minutes: int | None = None, delay_reference: str = "", owner_approval: str = "",
                   grace_minutes: int = 0) -> SourceDescriptor:
    """The Norgate source. Without the three timing arguments it is valid but not availability-ready."""
    return SourceDescriptor(source_id="norgate_futures_eod", vendor="Norgate Data",
                            dataset="Norgate Futures end-of-day, per contract (norgatedata export)",
                            licence="licensed", redistribution=False, timestamp_semantics="declared_delay",
                            declared_delay_minutes=delay_minutes, delay_reference=delay_reference,
                            owner_approval=owner_approval, grace_minutes=grace_minutes,
                            licence_reference="Norgate Data Personal Use licence (no redistribution); "
                                              "docs/manhattan/AUDIT.md section 1.3")


def _csv(data: bytes) -> list:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


class NorgateExportAdapter(Adapter):
    name, version = "norgate_export", "1"

    def __init__(self, market_map: dict, instruments: dict, source: SourceDescriptor | None = None):
        """``market_map``: Norgate market code (the export's ``market`` column) -> instrument_id."""
        self.source = source or norgate_source()
        if self.source.vendor != "Norgate Data":
            raise ProvenanceError("the Norgate adapter takes a Norgate source descriptor")
        self.market_map, self.instruments = dict(market_map), instruments
        for m, iid in self.market_map.items():
            inst = instruments.get(iid)
            if inst is None or inst.asset_class != "future":
                raise SchemaError(f"market {m} maps to {iid}, which is not a known futures instrument")

    def _check_manifest(self, files: dict, retrieved_utc: datetime) -> list:
        if "manifest.csv" not in files or "manifest.json" not in files:
            raise ProvenanceError("a Norgate export needs manifest.csv and manifest.json")
        meta = json.loads(files["manifest.json"].decode("utf-8"))
        if meta.get("close_is") != "settlement price" or meta.get("adjustment") != "none":
            raise ProvenanceError("manifest.json must say close_is 'settlement price' and adjustment 'none'")
        gen = as_utc(meta.get("generated_utc"), "manifest.json generated_utc")
        if gen is None or gen > retrieved_utc:
            raise ProvenanceError("the export's generated_utc is missing or after the retrieval time")
        entries = [e for e in _csv(files["manifest.csv"]) if e["file"].startswith("contracts/")]
        listed = {e["file"] for e in entries}
        present = {f for f in files if f.startswith("contracts/")}
        if present - listed:
            raise ProvenanceError(f"contract files not in manifest.csv: {sorted(present - listed)[:3]}")
        for e in entries:
            data = files.get(e["file"])
            if data is None:
                continue                      # a partial delivery may omit markets; only delivered files are read
            if len(data) != int(e["bytes"]) or hashlib.sha256(data).hexdigest() != e["sha256"]:
                raise ProvenanceError(f"{e['file']} does not match its manifest hash or size")
        return [e for e in entries if e["file"] in files]

    def _contract_id(self, market: str, norgate_contract: str) -> tuple[str, str]:
        iid = self.market_map.get(market)
        if iid is None:
            raise SchemaError(f"Norgate market {market!r} has no instrument mapping (never guessed)")
        _, y, m = parse_contract(norgate_contract)
        return iid, contract_id(self.instruments[iid].root, y, m)

    def contracts_from_metadata(self, data: bytes) -> dict:
        out = {}
        for r in _csv(data):
            if r["market"] not in self.market_map:
                continue
            iid, cid = self._contract_id(r["market"], r["contract"])
            if not r["last_quoted_date"]:
                raise SchemaError(f"{r['contract']}: metadata has no last quoted date")
            out[cid] = Contract(cid, iid, last_trade=as_date(r["last_quoted_date"]),
                                first_notice=as_date(r["first_notice_date"]) if r["first_notice_date"] else None,
                                first_trade=as_date(r["first_quoted_date"]) if r["first_quoted_date"] else None)
        return out

    def parse(self, files, request, retrieved_utc, gate) -> ParseResult:
        entries = self._check_manifest(files, retrieved_utc)
        obs, notes = [], [f"norgate export generated {json.loads(files['manifest.json'])['generated_utc']}"]
        contracts = {}
        if "metadata.csv" in files:
            contracts = self.contracts_from_metadata(files["metadata.csv"])
            notes.append("contract last_trade = Norgate last_quoted_date (final bar for expired contracts)")
        for e in sorted(entries, key=lambda e: e["file"]):
            iid, cid = self._contract_id(e["market"], e["contract"])
            text = files[e["file"]].decode("utf-8-sig")
            rd = csv.reader(io.StringIO(text))
            header = [h.strip().lower() for h in next(rd)]
            if header != COLUMNS:
                raise SchemaError(f"{e['file']}: columns {header}, expected {COLUMNS}")
            for row in rd:
                if not row:
                    continue
                d = as_date(row[0].strip(), "date")
                if not gate.admit(iid, d):                     # before any value is converted
                    continue
                for col, raw in zip(COLUMNS[1:], row[1:]):
                    raw = raw.strip()
                    if raw == "":
                        continue
                    obs.append(Observation(instrument_id=iid, contract_id=cid, session_date=d,
                                           field=FIELD_MAP[col], value=float(raw),
                                           settlement_status="final" if col == "close" else "not_applicable",
                                           first_seen_utc=retrieved_utc, source_id=self.source.source_id))
        return ParseResult(obs, contracts=contracts, notes=notes)
