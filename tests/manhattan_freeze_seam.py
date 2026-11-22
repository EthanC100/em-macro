"""TEST-ONLY seam for the freeze check and the equities gate (PR-2; S17 C1, C2). Never imported by production code.

``manhattan.freeze.verify_frozen`` takes no substitutable signature or timestamp check, and its production pin
(``ALLOWED_FREEZE_SIGNERS``) is empty, so every real freeze is refused. Tests that need an admitted batch use this
module, which lives under ``tests/`` (not in the ``manhattan`` package), and a static test
(``tests/test_manhattan_freeze_verification.py``) pins that no module under ``manhattan/`` references it, or the
private names it reaches (``freeze._TRUST``, ``registration._mint``, ``synthetic._register``).

Everything here is a deterministic **fixture**: an HMAC "signature" by a fixture key, and a fixture "timestamp
proof" that is the manifest's SHA-256 behind a fixture prefix. Neither is a cryptographic signature or an
OpenTimestamps proof; the production verifiers refuse both.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
from pathlib import Path

from manhattan import freeze as FZ

# obviously fake fingerprints: never a real key
FIXTURE_OWNER = "F1" * 20                       # the fixture "owner" key: pinned by fixture_trust()
FIXTURE_OTHER = "E2" * 20                       # a fixture key the fixture verifier knows, but that is not pinned
_SECRETS = {FIXTURE_OWNER: b"test fixture owner key, not a secret", FIXTURE_OTHER: b"test fixture other key"}
FIXTURE_OTS_PREFIX = b"MANHATTAN-TEST-FIXTURE-OTS/1\x00"
SIGNATURE_FILE = "tag.fixture-signature.json"


def _mac(signer: str, tag: str, raw: bytes) -> str:
    return hmac.new(_SECRETS[signer], tag.encode() + b"\x00" + hashlib.sha256(raw).digest(), hashlib.sha256).hexdigest()


def sign(directory: Path, number: int, signer: str = FIXTURE_OWNER) -> None:
    """A fixture "signed tag" over the batch's manifest by a fixture key."""
    d = Path(directory) / f"AB-{number:04d}"
    raw = (d / FZ.MANIFEST).read_bytes()
    tag = FZ.TAG.format(n=number)
    (d / SIGNATURE_FILE).write_text(json.dumps({"tag": tag, "signer": signer, "mac": _mac(signer, tag, raw)}))


def stamp(directory: Path, number: int) -> None:
    """A fixture timestamp proof of the batch's manifest."""
    d = Path(directory) / f"AB-{number:04d}"
    (d / FZ.TIMESTAMP_PROOF).write_bytes(FIXTURE_OTS_PREFIX + hashlib.sha256((d / FZ.MANIFEST).read_bytes()).digest())


def fixture_tag_signer(tag: str, root: Path, manifest_path: Path, raw: bytes) -> str | None:
    """The fixture counterpart of ``freeze.git_tag_signer``: the fixture key whose valid MAC covers (tag, manifest)."""
    f = Path(manifest_path).parent / SIGNATURE_FILE
    try:
        rec = json.loads(f.read_text())
    except (OSError, ValueError):
        return None
    signer = rec.get("signer")
    if rec.get("tag") != tag or signer not in _SECRETS or not hmac.compare_digest(
            str(rec.get("mac")), _mac(signer, tag, raw)):
        return None
    return signer


class FixtureTimestampVerifier:
    def verify(self, proof: bytes, digest: bytes) -> None:
        if proof != FIXTURE_OTS_PREFIX + digest:
            raise FZ.FreezeError("the timestamp proof does not verify against the manifest hash (fixture verifier)")


@contextlib.contextmanager
def trust(*, signers=frozenset({FIXTURE_OWNER}), tag_signer=fixture_tag_signer, timestamp=None):
    """Swap the trust ``verify_frozen`` uses for the duration (default: the fixture owner key and fixture proofs)."""
    old = FZ._TRUST
    FZ._TRUST = FZ._Trust(frozenset(signers), tag_signer, timestamp or FixtureTimestampVerifier())
    try:
        yield
    finally:
        FZ._TRUST = old


def fixture_trust():
    return trust()


def freeze_fixture(directory: Path, number: int, *, signer: str | None = FIXTURE_OWNER, ots: bool = True) -> None:
    """Sign and stamp a batch already written with ``freeze.write`` (fixture key and fixture proof)."""
    if signer is not None:
        sign(directory, number, signer)
    if ots:
        stamp(directory, number)


# ------------------------------------------------------------------ the equities gate

def mint(obj):
    """Issue an object as the equities gate would (forged locks and handles, to test the gate's content checks)."""
    from manhattan.equities import registration as R
    return R._mint(obj)


def mark_synthetic(world, label: str):
    """Register a test-built world (for instance an instrumented copy of a generator's world) as synthetic."""
    from manhattan.equities import synthetic as SY
    return SY._register(world, provenance=hashlib.sha256(f"test fixture world: {label}".encode()).hexdigest())


@contextlib.contextmanager
def production_trust():
    """The production trust (empty pin, git tag check, OpenTimestamps verifier), inside a fixture-trust block."""
    old = FZ._TRUST
    FZ._TRUST = FZ._PRODUCTION
    try:
        yield
    finally:
        FZ._TRUST = old
