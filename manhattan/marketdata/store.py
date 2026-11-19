"""The immutable dataset store and its registry (DESIGN.md section 6).

Layout under a store root (a directory the caller chooses; for licensed data it must be outside this repository,
which ``DatasetStore`` checks):

    datasets/<MD-id>/manifest.json     the manifest's canonical bytes (its SHA-256 gives the id)
    datasets/<MD-id>/rows.csv          canonical rows (sorted, fixed columns, repr floats, LF)
    datasets/<MD-id>/reference.json    instruments and contracts the rows were validated against
    datasets/<MD-id>/validation.json   the validation report (warnings; errors never reach the store)
    raw/<sha256>.bin                   raw delivery files, content-addressed (only when the ingestion admitted
                                       every row: raw files that hold protected dates are never copied)
    registry.jsonl                     append-only, hash-chained: one record per dataset

**Immutable.** A dataset directory is written once (to a temporary directory, then renamed) and made read-only.
Putting the same dataset again is a no-op; putting different bytes under an existing id is refused
(``ImmutableError``). ``load`` re-hashes every file against the manifest, so a changed byte is detected.

**Registry.** Each record holds seq, dataset id, manifest SHA-256, source, licence, row count, coverage dates,
retrieval time, ``prev_hash`` and ``hash`` (SHA-256 of the canonical form of the rest). ``verify`` recomputes the
chain. Re-registering an id is a no-op if the record matches and refused otherwise.
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

from manhattan import spec as S

from .errors import ImmutableError, LicenceError, ProvenanceError
from .provenance import DatasetManifest, sha256_bytes
from .schema import ROW_COLUMNS, Observation

REPO_ROOT = Path(__file__).resolve().parents[2]
GENESIS = "0" * 64


def rows_bytes(observations) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(ROW_COLUMNS), lineterminator="\n")
    w.writeheader()
    for o in sorted(observations, key=Observation.sort_key):
        w.writerow(o.to_row())
    return buf.getvalue().encode("utf-8")


def parse_rows(data: bytes) -> list:
    return [Observation.from_row(r) for r in csv.DictReader(io.StringIO(data.decode("utf-8")))]


def inside_repo(path: Path) -> bool:
    p = Path(path).resolve()
    return p == REPO_ROOT or REPO_ROOT in p.parents


def _readonly(path: Path):
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file():
            p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


class DatasetStore:
    def __init__(self, root: Path, *, allow_licensed: bool = False):
        """``allow_licensed``: this store may hold licensed rows. Refused for any root inside the repository."""
        self.root = Path(root)
        self.allow_licensed = allow_licensed
        if allow_licensed and inside_repo(self.root):
            raise LicenceError("a store for licensed data must be outside the public repository (hard rule 7)")

    # ---- datasets
    def path(self, dataset_id: str) -> Path:
        return self.root / "datasets" / dataset_id

    def has(self, dataset_id: str) -> bool:
        return (self.path(dataset_id) / "manifest.json").exists()

    def put(self, manifest: DatasetManifest, rows: bytes, reference: bytes, validation: bytes,
            raw: dict | None = None) -> bool:
        """Store a dataset. Returns True when written, False when an identical copy was already there."""
        if manifest.source.licence == "licensed" and not self.allow_licensed:
            raise LicenceError(f"{manifest.source.source_id} is licensed; this store does not accept licensed data")
        if sha256_bytes(rows) != manifest.rows_sha256:
            raise ProvenanceError("rows do not match the manifest's rows_sha256")
        if sha256_bytes(reference) != manifest.reference_sha256 or sha256_bytes(validation) != manifest.validation_sha256:
            raise ProvenanceError("reference or validation bytes do not match the manifest")
        files = {"manifest.json": manifest.canonical_bytes(), "rows.csv": rows, "reference.json": reference,
                 "validation.json": validation}
        did = manifest.dataset_id
        target = self.path(did)
        for f in (raw or {}).values():
            self._put_raw(f)
        if target.exists():
            for name, data in files.items():
                p = target / name
                if not p.exists() or p.read_bytes() != data:
                    raise ImmutableError(f"{did} exists with different contents ({name})")
            self._register(manifest)
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=f".{did}.", dir=target.parent))
        try:
            for name, data in files.items():
                (tmp / name).write_bytes(data)
            os.rename(tmp, target)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
            if target.exists():                         # a concurrent writer won: check it is the same dataset
                return self.put(manifest, rows, reference, validation, raw)
            raise
        _readonly(target)
        self._register(manifest)
        return True

    def _put_raw(self, data: bytes):
        sha = sha256_bytes(data)
        p = self.root / "raw" / f"{sha}.bin"
        if p.exists():
            if sha256_bytes(p.read_bytes()) != sha:
                raise ImmutableError(f"raw/{sha}.bin is corrupt")
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)
        p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    def raw(self, sha: str) -> bytes:
        data = (self.root / "raw" / f"{sha}.bin").read_bytes()
        if sha256_bytes(data) != sha:
            raise ImmutableError(f"raw/{sha}.bin does not match its name")
        return data

    def load(self, dataset_id: str) -> dict:
        """Manifest (as a dict), observations, reference and validation of a stored dataset, all re-verified."""
        d = self.path(dataset_id)
        mbytes = (d / "manifest.json").read_bytes()
        if "MD-" + sha256_bytes(mbytes)[:16] != dataset_id:
            raise ImmutableError(f"{dataset_id}: manifest bytes do not hash to the id")
        manifest = json.loads(mbytes)
        rows, ref, val = ((d / n).read_bytes() for n in ("rows.csv", "reference.json", "validation.json"))
        if sha256_bytes(rows) != manifest["rows_sha256"]:
            raise ImmutableError(f"{dataset_id}: rows.csv was changed")
        if sha256_bytes(ref) != manifest["reference_sha256"] or sha256_bytes(val) != manifest["validation_sha256"]:
            raise ImmutableError(f"{dataset_id}: reference.json or validation.json was changed")
        obs = parse_rows(rows)
        if len(obs) != manifest["row_count"]:
            raise ImmutableError(f"{dataset_id}: row count differs from the manifest")
        return {"manifest": manifest, "observations": obs, "reference": json.loads(ref),
                "validation": json.loads(val)}

    # ---- registry
    @property
    def registry_path(self) -> Path:
        return self.root / "registry.jsonl"

    def registry(self) -> list:
        if not self.registry_path.exists():
            return []
        return [json.loads(line) for line in self.registry_path.read_text(encoding="utf-8").splitlines() if line]

    def verify(self) -> int:
        """Recompute the registry chain and each dataset's id. Returns the record count."""
        prev = GENESIS
        for i, rec in enumerate(self.registry(), 1):
            body = {k: v for k, v in rec.items() if k != "hash"}
            if rec["seq"] != i or rec["prev_hash"] != prev or sha256_bytes(S.canonical_bytes(body)) != rec["hash"]:
                raise ImmutableError(f"registry record {i} breaks the chain")
            m = (self.path(rec["dataset_id"]) / "manifest.json").read_bytes()
            if sha256_bytes(m) != rec["manifest_sha256"]:
                raise ImmutableError(f"registry record {i}: manifest of {rec['dataset_id']} changed")
            prev = rec["hash"]
        return len(self.registry())

    def _register(self, manifest: DatasetManifest):
        recs = self.registry()
        body = {"dataset_id": manifest.dataset_id, "manifest_sha256": manifest.sha256,
                "source_id": manifest.source.source_id, "licence": manifest.source.licence,
                "row_count": manifest.row_count, "coverage": manifest.coverage,
                "retrieved_utc": manifest.to_dict()["retrieved_utc"],
                "provenance_complete": manifest.provenance_complete}
        for r in recs:
            if r["dataset_id"] == manifest.dataset_id:
                if r["manifest_sha256"] != body["manifest_sha256"]:
                    raise ImmutableError(f"{manifest.dataset_id} is registered with a different manifest")
                return
        body = {"seq": len(recs) + 1, **body, "prev_hash": recs[-1]["hash"] if recs else GENESIS}
        rec = {**body, "hash": sha256_bytes(S.canonical_bytes(body))}
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
