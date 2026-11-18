"""Canonical identities for the HTE engine.

Canonical form is Manhattan's (``manhattan.spec.canonical_bytes``: sorted keys, NFC strings, integers as integers,
other numbers as decimal strings), so ``5`` and ``5.0`` and ``0.50`` and ``0.5`` are the same value and a
re-ordered mapping is the same mapping.

Identity levels (prefixes are distinct from the frozen-spec prefixes AF/AH/AV/AX of ``manhattan.spec`` because HTE
registrations are not frozen Manhattan specs):

    HF-  family          one mechanism, one predicted sign (synthetic labels in benchmarks)
    HH-  hypothesis      the family in one domain (asset class, universe, frequency); contains the family hash
    HS-  strategy spec   a signal template with its declared parameter grid, bound to a hypothesis
    HV-  variant         one grid point of a strategy spec; contains the spec hash
    HC-  candidate       a variant bound to a cost model, a sizing rule and the evaluation methodology version

Code and data identity are deliberately **not** part of the candidate identity: the same registered candidate can
be evaluated with several code versions or on several synthetic datasets, and every such evaluation is a separate,
counted *attempt* whose identity carries both (``attempt_identity``). This mirrors PR #86, where the attempt
identity holds ``spec_hash``, ``data_hash`` and ``code_version`` as separate fields.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path

import numpy as np

from manhattan.spec import canonical_bytes

PREFIX = {"family": "HF", "hypothesis": "HH", "strategy_spec": "HS", "variant": "HV", "candidate": "HC"}
ID_HEX = 16
PKG_DIR = Path(__file__).resolve().parent
ROOT = PKG_DIR.parent.parent


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def full_hash(obj: dict) -> str:
    return sha256_bytes(canonical_bytes(obj))


def short_id(level: str, h: str) -> str:
    return f"{PREFIX[level]}-{h[:ID_HEX]}"


def merkle_root(hashes) -> str:
    """Merkle root over hex SHA-256 leaves, taken in the order given (callers sort first). Odd nodes are paired
    with themselves. The empty set has the root of the empty string."""
    level = [bytes.fromhex(h) for h in hashes]
    if not level:
        return sha256_bytes(b"")
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def merkle_root_array(digests: np.ndarray) -> str:
    """Merkle root of an ``(n, 32)`` uint8 array of raw SHA-256 digests (row order kept). Same result as
    ``merkle_root`` on the hex strings; used for registries of a million candidates."""
    level = [bytes(r) for r in np.ascontiguousarray(digests, dtype=np.uint8)]
    if not level:
        return sha256_bytes(b"")
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def code_identity(root: Path = ROOT) -> dict:
    """The code that evaluates: SHA-256 of every ``manhattan/hte/*.py`` (path and bytes, sorted), the numeric
    stack, and the git commit when it is known. ``engine_sha256`` alone decides whether two runs used the same
    evaluation code; the commit is informative (a dirty tree has the same commit and a different digest)."""
    h = hashlib.sha256()
    for p in sorted(PKG_DIR.glob("*.py")):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                                timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {
        "engine_sha256": h.hexdigest(),
        "commit": commit,
        "numpy": np.__version__,
        "python": platform.python_version(),
    }


def source_hash(*modules) -> str:
    """SHA-256 of the source of the given modules (feature cache keys include the feature code's hash)."""
    h = hashlib.sha256()
    for m in modules:
        h.update(Path(m.__file__).read_bytes())
    return h.hexdigest()


def attempt_identity(*, candidate_hash: str, data_hash: str, code: dict, policy_hash: str, stage: int) -> dict:
    """What makes two evaluations of a candidate 'the same look' (a rerun) rather than a new look."""
    return {"candidate": candidate_hash, "data": data_hash, "engine_sha256": code["engine_sha256"],
            "policy": policy_hash, "stage": int(stage)}
