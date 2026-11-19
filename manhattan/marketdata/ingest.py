"""The ingestion pipeline: raw delivery -> fenced, validated, content-addressed dataset (DESIGN.md section 8).

    result = ingest(adapter, files, request=..., retrieved_utc=..., instruments=..., store=..., fence=...,
                    caller="session")

Steps, in order; any failure stops the ingestion and nothing is stored:

1. **Licence.** Licensed sources need a store that accepts licensed data, which is never inside this repository.
2. **Retrieval time** is given by the caller (never read from the clock), with a zone.
3. **Fence.** The adapter parses with a ``FenceGate``: rows on dates the caller may not read are refused or
   excluded before their values are read.
4. **Reference data.** Contracts delivered by the vendor are merged with those supplied; a contract defined
   differently by the two is refused.
5. **Validation** (``manhattan.marketdata.validate``). Any error stops ingestion.
6. **Identity.** Canonical rows, reference data and the validation report are hashed into the manifest; the
   manifest's hash is the dataset id.
7. **Store.** Written once, read-only, registered in the hash-chained registry. Raw files are copied only when the
   fence admitted every row.

Deterministic: the same files (in any order), request, retrieval time, reference data, fence and caller give the
same dataset id and the same bytes, on any machine.
"""
from __future__ import annotations

from dataclasses import dataclass

from manhattan import roles
from manhattan import spec as S

from .errors import LicenceError, MarketDataError, ProvenanceError, ValidationFailed
from .fence import FenceGate
from .provenance import DatasetManifest, RawFile, sha256_bytes
from .schema import SCHEMA_VERSION, as_utc
from .store import DatasetStore, rows_bytes
from .validate import Rules, validate


@dataclass(frozen=True)
class IngestResult:
    dataset_id: str
    manifest: DatasetManifest
    report: dict
    created: bool


def reference_bytes(instruments: dict, contracts: dict, observations) -> bytes:
    used_i = sorted({o.instrument_id for o in observations})
    used_c = sorted({o.contract_id for o in observations if o.contract_id})
    ref = {"schema_version": SCHEMA_VERSION,
           "instruments": [instruments[i].to_dict() for i in used_i],
           "contracts": [{"contract_id": c, "instrument_id": contracts[c].instrument_id,
                          "last_trade": contracts[c].last_trade.isoformat(),
                          "first_notice": contracts[c].first_notice.isoformat() if contracts[c].first_notice else None,
                          "first_trade": contracts[c].first_trade.isoformat() if contracts[c].first_trade else None}
                         for c in used_c if c in contracts]}
    return S.canonical_bytes(ref)


def _merge_contracts(supplied: dict, delivered: dict) -> dict:
    out = dict(supplied)
    for cid, c in delivered.items():
        if cid in out and out[cid] != c:
            raise MarketDataError(f"contract {cid} is defined differently by the vendor and the supplied table")
        out[cid] = c
    return out


def ingest(adapter, files: dict, *, request: dict, retrieved_utc, instruments: dict, store: DatasetStore,
           fence: roles.Fence, caller: str, contracts: dict | None = None, policy: str = "refuse",
           rules: Rules = Rules(), freeze=None, holding: int = 0, token: roles.RunnerToken | None = None,
           window_id: str | None = None) -> IngestResult:
    src = adapter.source
    if src.licence == "licensed" and not store.allow_licensed:
        raise LicenceError(f"{src.source_id} is licensed: ingest into a store outside the repository "
                           "created with allow_licensed=True (hard rule 7)")
    retrieved = as_utc(retrieved_utc, "retrieved_utc")
    if retrieved is None:
        raise ProvenanceError("retrieved_utc is required")
    if not files:
        raise ProvenanceError("an ingestion needs at least one raw file")
    gate = FenceGate(fence, instruments, caller, policy=policy, freeze=freeze, holding=holding, token=token,
                     window_id=window_id)
    parsed = adapter.parse(files, request, retrieved, gate)
    all_contracts = _merge_contracts(contracts or {}, parsed.contracts)
    obs, report = validate(parsed.observations, instruments, all_contracts, src, retrieved, rules)
    if not report.ok:
        raise ValidationFailed(report)
    if not obs:
        raise MarketDataError("the delivery holds no admitted observation")
    rows = rows_bytes(obs)
    ref = reference_bytes(instruments, all_contracts, obs)
    val = S.canonical_bytes(report.to_dict())
    days = sorted({o.session_date for o in obs})
    manifest = DatasetManifest(
        source=src, adapter=adapter.name, adapter_version=adapter.version,
        request={k: v for k, v in sorted(request.items())}, retrieved_utc=retrieved,
        raw_files=tuple(sorted((RawFile.of(n, b) for n, b in files.items()), key=lambda f: f.name)),
        rows_sha256=sha256_bytes(rows), row_count=len(obs),
        coverage={"first_session": days[0].isoformat(), "last_session": days[-1].isoformat(),
                  "instruments": sorted({o.instrument_id for o in obs}),
                  "contracts": len({o.contract_id for o in obs if o.contract_id}),
                  "fields": sorted({o.field for o in obs})},
        fence=gate.decision(), reference_sha256=sha256_bytes(ref), validation_sha256=sha256_bytes(val),
        notes=tuple(parsed.notes), provenance_gaps=tuple(src.provenance_gaps()))
    raw = None if gate.excluded_any else dict(files)
    created = store.put(manifest, rows, ref, val, raw)
    return IngestResult(manifest.dataset_id, manifest, report.to_dict(), created)
