"""Source descriptors and immutable dataset identities (DESIGN.md sections 4 and 6).

**Sources.** A ``SourceDescriptor`` says who produced the data, under which licence, and what its timestamps mean.
Two timestamp semantics exist:

    vendor_receipt   every row carries the vendor's own receipt or publication time (Databento ``ts_recv``).
                     Availability is read from the row.
    declared_delay   rows carry a session date only (Norgate's export, most end-of-day files). The nominal
                     publication time is the session close plus ``declared_delay_minutes``. For anything but a
                     synthetic fixture this delay is an assumption about the vendor, so it must name where it comes
                     from (``delay_reference``) and who approved it (``owner_approval``); without both, no
                     availability can be computed and the dataset cannot be turned into a point-in-time store.

A descriptor never fills a field it was not given. Missing provenance stays missing and is listed in
``provenance_gaps``; a dataset with gaps can be stored and inspected but not used as historical evidence.

**Dataset identity.** A dataset is the canonical rows produced by one adapter version from one set of raw files.
Its manifest holds the source descriptor, the adapter name and version, the request (symbols, dates, schema), the
retrieval time, every raw file's name, size and SHA-256, and the SHA-256 of the canonical rows. The dataset id is
``MD-`` and the first 16 hex characters of the SHA-256 of the manifest's canonical bytes
(``manhattan.spec.canonical_bytes``). Same raw bytes, same adapter, same request: same id, byte for byte. Any
change to any of them: a new id. Nothing in the manifest depends on the wall clock at ingestion time, or on the
order in which files or rows arrived.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime

from manhattan import spec as S
from manhattan.availability import validate_source

from .errors import ProvenanceError
from .schema import as_utc, iso

LICENCES = ("synthetic", "public", "licensed")
SEMANTICS = ("vendor_receipt", "declared_delay")
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    vendor: str
    dataset: str                       # the vendor's dataset or product name, e.g. "GLBX.MDP3 statistics"
    licence: str                       # synthetic | public | licensed
    redistribution: bool               # may rows (or rows derived from them) be published?
    timestamp_semantics: str           # vendor_receipt | declared_delay
    declared_delay_minutes: int | None = None
    delay_reference: str = ""          # where the declared delay comes from
    owner_approval: str = ""           # who accepted the declared delay as an assumption (non-synthetic only)
    grace_minutes: int = 0             # a capture later than nominal + grace is "late"
    licence_reference: str = ""        # the licence or terms document

    def __post_init__(self):
        for name in ("source_id", "vendor", "dataset"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ProvenanceError(f"source {name} is required")
        if self.licence not in LICENCES:
            raise ProvenanceError(f"licence must be one of {LICENCES}")
        if not isinstance(self.redistribution, bool):
            raise ProvenanceError("redistribution must be true or false")
        if self.licence == "licensed" and self.redistribution:
            raise ProvenanceError("licensed sources in this project are never redistributable (hard rule 7)")
        if self.licence != "synthetic" and not self.licence_reference.strip():
            raise ProvenanceError("a non-synthetic source names its licence or terms (licence_reference)")
        if self.timestamp_semantics not in SEMANTICS:
            raise ProvenanceError(f"timestamp_semantics must be one of {SEMANTICS}")
        lag = self.declared_delay_minutes
        if lag is not None and (isinstance(lag, bool) or not isinstance(lag, int) or lag < 0):
            raise ProvenanceError("declared_delay_minutes is a whole number of minutes, 0 or more")
        if self.timestamp_semantics == "vendor_receipt" and lag is not None:
            raise ProvenanceError("vendor_receipt sources read availability from each row, not a declared delay")
        if isinstance(self.grace_minutes, bool) or not isinstance(self.grace_minutes, int) or self.grace_minutes < 0:
            raise ProvenanceError("grace_minutes is a whole number, 0 or more")

    @property
    def availability_ready(self) -> bool:
        """Whether availability can be computed without inventing anything."""
        if self.timestamp_semantics == "vendor_receipt":
            return True
        if self.declared_delay_minutes is None:
            return False
        if self.licence == "synthetic":
            return True
        return bool(self.delay_reference.strip() and self.owner_approval.strip())

    def provenance_gaps(self) -> list[str]:
        gaps = []
        if self.timestamp_semantics == "declared_delay":
            if self.declared_delay_minutes is None:
                gaps.append("declared_delay_minutes: the vendor's publication delay is not declared")
            if self.licence != "synthetic" and not self.delay_reference.strip():
                gaps.append("delay_reference: no source for the declared publication delay")
            if self.licence != "synthetic" and not self.owner_approval.strip():
                gaps.append("owner_approval: the delay assumption is not approved by the owner")
        return gaps

    def availability_contract(self) -> dict:
        """The same source as a ``manhattan.availability`` contract, so the existing PIT layer accepts it.
        vendor_receipt -> per-vintage release dates; declared_delay -> a conservative assumption with its owner
        approval (synthetic fixtures: the fixture itself is the reference)."""
        if self.timestamp_semantics == "vendor_receipt":
            contract = {"name": self.source_id, "frequency": "daily", "period_label": "observation_date",
                        "availability": {"kind": "release_dates", "reference": f"{self.vendor} {self.dataset}",
                                         "day_mapping": "vendor receipt time per row, mapped by the research clock"}}
        else:
            if not self.availability_ready:
                raise ProvenanceError("; ".join(self.provenance_gaps()))
            contract = {"name": self.source_id, "frequency": "daily", "period_label": "observation_date",
                        "availability": {"kind": "conservative",
                                         "reference": self.delay_reference or f"synthetic fixture {self.source_id}",
                                         "day_mapping": f"session close + {self.declared_delay_minutes} minutes, "
                                                        "mapped by the research clock",
                                         "assumption": f"publication {self.declared_delay_minutes} minutes after close",
                                         "owner_approval": self.owner_approval or "synthetic fixture (tests only)",
                                         "release_history_unavailable": "vendor publishes no per-row release time"}}
        validate_source(contract)
        return contract

    def to_dict(self) -> dict:
        return asdict(self)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass(frozen=True)
class RawFile:
    name: str             # the file's path inside the delivery (posix), e.g. "contracts/XA/XA-2010H.csv"
    sha256: str
    bytes: int

    @classmethod
    def of(cls, name: str, data: bytes) -> "RawFile":
        if not isinstance(name, str) or not name or name.startswith("/") or ".." in name.split("/"):
            raise ProvenanceError(f"raw file name {name!r} must be a relative posix path")
        return cls(name, sha256_bytes(data), len(data))


@dataclass(frozen=True)
class DatasetManifest:
    source: SourceDescriptor
    adapter: str
    adapter_version: str
    request: dict                      # what was asked for: symbols, start, end, schema, snapshot name
    retrieved_utc: datetime            # when the raw bytes were captured; supplied, never taken from the clock
    raw_files: tuple                   # RawFile, sorted by name
    rows_sha256: str
    row_count: int
    coverage: dict                     # {"first_session": ..., "last_session": ..., "instruments": [...]}
    fence: dict                        # what the fence check decided at ingestion (roles, excluded counts)
    reference_sha256: str = ""         # instruments and contracts the rows were validated against
    validation_sha256: str = ""        # the validation report (warnings) stored with the dataset
    notes: tuple = field(default_factory=tuple)   # adapter facts about the delivery (no values)
    provenance_gaps: tuple = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, "retrieved_utc", as_utc(self.retrieved_utc, "retrieved_utc"))
        if self.retrieved_utc is None:
            raise ProvenanceError("retrieved_utc is required: the time the raw bytes were captured")
        names = [f.name for f in self.raw_files]
        if not names:
            raise ProvenanceError("a dataset comes from at least one raw file")
        if names != sorted(names) or len(set(names)) != len(names):
            raise ProvenanceError("raw files must be unique and sorted by name")

    def to_dict(self) -> dict:
        return {"manifest_version": MANIFEST_VERSION, "source": self.source.to_dict(), "adapter": self.adapter,
                "adapter_version": self.adapter_version, "request": self.request,
                "retrieved_utc": iso(self.retrieved_utc),
                "raw_files": [asdict(f) for f in self.raw_files], "rows_sha256": self.rows_sha256,
                "row_count": self.row_count, "coverage": self.coverage, "fence": self.fence,
                "reference_sha256": self.reference_sha256, "validation_sha256": self.validation_sha256,
                "notes": list(self.notes), "provenance_gaps": list(self.provenance_gaps)}

    def canonical_bytes(self) -> bytes:
        return S.canonical_bytes(self.to_dict())

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.canonical_bytes())

    @property
    def dataset_id(self) -> str:
        return "MD-" + self.sha256[:16]

    @property
    def provenance_complete(self) -> bool:
        return not self.provenance_gaps
