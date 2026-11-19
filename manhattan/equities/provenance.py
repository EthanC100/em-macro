"""Provenance of research outputs: a content hash of what went in, how, and under which information boundary.

A provenance record is a mapping in ``manhattan.spec`` canonical form (sorted keys, NFC strings, decimals as
strings, dates as YYYY-MM-DD), hashed with ``manhattan.spec.spec_hash``: the same canonicalisation as every
Manhattan spec, not a second one. It names the inputs by their hashes (a ``PitStore.data_hash()``, a universe
``membership_hash``, a pair's ``formation_hash``), the parameters, the information boundary, the code version and
the data roles. It contains no values, so it may be committed even when its inputs are licensed.
"""
from __future__ import annotations

import re
from datetime import date

from manhattan import spec as S

from .errors import EvidenceError
from .sources import ContractRegistry


def record(kind: str, *, inputs: dict, params: dict, boundary: dict, code_version: str,
           contracts: ContractRegistry | None = None, role: str = "exploration") -> dict:
    """A provenance mapping with its hash under ``"id"``. ``inputs`` maps names to SHA-256 hashes."""
    if not (isinstance(code_version, str) and re.fullmatch(r"[0-9a-f]{7,40}", code_version)):
        raise EvidenceError("code_version must be a git commit (7 to 40 hex characters), not free text")
    if role != "exploration":
        raise EvidenceError("research outputs of this package are exploration-role only")
    for k, v in inputs.items():
        if not (isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)):
            raise EvidenceError(f"input {k!r} must be named by its SHA-256, not by its values")
    body = {"kind": kind, "inputs": dict(inputs), "params": dict(params),
            "boundary": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in boundary.items()},
            "code_version": code_version, "role": role, "evidential_weight": 0,
            "contracts": [] if contracts is None else [
                {"kind": c.kind, "name": c.name, "licence": c.licence, "revision": c.revision_behaviour,
                 "timestamps": c.timestamp_semantics} for c in (contracts.contract(k) for k in contracts.kinds())]}
    return {**body, "id": "EQ-" + S.spec_hash(body)[:16], "hash": S.spec_hash(body)}


def verify(rec: dict) -> bool:
    body = {k: v for k, v in rec.items() if k not in ("id", "hash")}
    return rec.get("hash") == S.spec_hash(body)
