"""Freezing a batch (ARCHITECTURE.md section 5.4).

A batch is frozen as a whole: its specs are validated, hashed and enumerated; a manifest lists every spec hash
and their Merkle root, the template hash, the generator model, the protocol hash, the data-role fence in force,
the designated evaluations and the critic records; the commit that holds them gets a **signed tag** and the
manifest hash an **external timestamp**. Only then may a designated evaluation start.

Under CLAUDE.md hard rule 4 a freeze is a pre-registration and is Ethan's (``freeze.authority: ethan_only``):
an agent **prepares** a batch (``prepare``), Ethan reviews, merges, tags and timestamps. ``authorise`` refuses an
agent's freeze. ``verify_frozen`` is the runner's check before any designated evaluation, and it refuses a batch
whose manifest or specs no longer match their hashes, whose timestamp proof does not **verify** against the manifest
hash, or whose tag is missing, unsigned, signed by a key that is not pinned, or not on the frozen manifest.

**Fail closed (S17 C2; PR-2).** Verification needs two things this module does not invent:

- ``ALLOWED_FREEZE_SIGNERS``: the owner's signing-key fingerprint(s). It is **empty**, so every real freeze is
  refused until Ethan adds his fingerprint in a reviewed change on main (``NO_PINNED_SIGNER`` names the action).
- an OpenTimestamps verifier able to check the proof's Bitcoin attestation (``OpenTimestampsVerifier``). Only the
  proof's structure and its digest are checked here; the attestation cannot be verified without a block-header
  source, so the production verifier refuses (fail closed) rather than trust a file's existence.

The signature and timestamp checks are not parameters of ``verify_frozen``: a caller cannot substitute them. Tests
reach a deterministic fixture key and fixture proof through a test-only seam under ``tests/`` (a static
test pins that no module under ``manhattan/`` references it or the private trust it swaps).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import ledger as L
from . import spec as S

MANIFEST = "manifest.json"
TIMESTAMP_PROOF = "manifest.json.ots"
TAG = "manhattan-batch-{n:04d}"
CHANNELS = S.CHANNELS

# The owner's signing-key fingerprints (GPG primary-key fingerprint, 40 upper-case hex, or an SSH "SHA256:..." key
# fingerprint). EMPTY in production: no key is pinned, so every real batch freeze is refused (owner action below).
ALLOWED_FREEZE_SIGNERS: frozenset = frozenset()
NO_PINNED_SIGNER = ("no owner signing key is pinned (manhattan.freeze.ALLOWED_FREEZE_SIGNERS is empty), so every "
                    "batch freeze is refused. Owner action, both needed before any freeze verifies: Ethan adds his "
                    "signing-key fingerprint to ALLOWED_FREEZE_SIGNERS in a reviewed change on main, and an "
                    "OpenTimestamps attestation verifier (with a Bitcoin block-header source) is provided for "
                    "OpenTimestampsVerifier, which refuses every proof until then")


class FreezeError(RuntimeError):
    pass


@dataclass
class Batch:
    """A prepared batch: every spec (families, hypotheses, variants, primary executables) and its manifest."""
    number: int
    manifest: dict
    specs: list[dict]

    @property
    def id(self) -> str:
        return f"AB-{self.number:04d}"

    @property
    def manifest_hash(self) -> str:
        return S.spec_hash(self.manifest)


def prepare(number: int, families: list[dict], hypotheses: list[dict], *, channel: str, template_hash: str,
            generator_model: str, protocol_hash: str, fence: dict, code_version: str, critic_records: list[str],
            reserve_window_ids: dict | None = None) -> Batch:
    """Steps 1 to 3 of the freeze: validate, hash, enumerate, build the manifest. Anyone may do this.

    Every hypothesis must belong to a family of the batch, and every family must have at least one hypothesis: a
    family is registered in one batch with all its hypotheses. ``reserve_window_ids`` maps a domain to the id of
    its reserve window; each primary executable of a **blind** hypothesis in such a domain gets one designated
    evaluation there. Only one hypothesis may be designated per domain (D-6); ambiguous batches are refused
    before selection. Adaptive specs get none (they carry no evidential weight on the reserve)."""
    if channel not in CHANNELS:
        raise FreezeError(f"channel must be one of {CHANNELS}")
    errs = [e for f in families for e in S.validate_family(f)] + [e for h in hypotheses for e in S.validate_hypothesis(h)]
    fam_hashes = {S.spec_hash(f) for f in families}
    if len(fam_hashes) != len(families):
        errs.append("a family appears twice in the batch")
    used = set()
    for h in hypotheses:
        if h.get("family") not in fam_hashes:
            errs.append(f"hypothesis {S.spec_id(h)} names a family that is not in this batch")
        used.add(h.get("family"))
    errs += [f"family {S.spec_id(f)} has no hypothesis in the batch" for f in families if S.spec_hash(f) not in used]
    if channel == "blind":
        domains = [h["domain"] for h in hypotheses if (reserve_window_ids or {}).get(h["domain"]) is not None]
        if len(domains) != len(set(domains)):
            errs.append("only one designated hypothesis per (batch, domain) is supported")
    if not critic_records:
        errs.append("no critic record: every family and hypothesis is reviewed before freezing")
    if errs:
        raise FreezeError("; ".join(errs))
    reg = S.Registry()
    specs, designated = [], []
    for sp in families + hypotheses:
        reg.add(sp)
        specs.append(sp)
    for h in hypotheses:
        for v in S.variants(h):
            x = S.primary_executable(h, v, code_version)
            reg.add(v), reg.add(x)
            specs += [v, x]
            window = (reserve_window_ids or {}).get(h["domain"])
            if channel == "blind" and window is not None:
                designated.append({"executable": S.spec_hash(x), "window": window, "domain": h["domain"]})
    hashes = [S.spec_hash(sp) for sp in specs]
    manifest = {"batch": number, "channel": channel, "template_hash": template_hash, "generator_model": generator_model,
                "protocol": protocol_hash, "fence": fence, "spec_hashes": hashes, "merkle_root": L.merkle_root(hashes),
                "designated_evaluations": designated, "critic_records": list(critic_records),
                "counts": {"families": len(families), "hypotheses": len(hypotheses),
                           "variants": sum(1 for sp in specs if sp["level"] == "variant")}}
    return Batch(number, manifest, specs)


def write(batch: Batch, directory: Path) -> Path:
    """Write the spec files and the manifest (step 4's files; committing them is the caller's job)."""
    d = directory / batch.id
    for sp in batch.specs:
        S.write(sp, d / "specs")
    (d / MANIFEST).write_bytes(S.canonical_bytes(batch.manifest))
    return d


def authorise(actor: str, config: dict) -> None:
    """Who may freeze. With ``freeze.authority: ethan_only`` (the default) only Ethan; an agent prepares."""
    authority = config.get("freeze", {}).get("authority", "ethan_only")
    if actor == "ethan":
        return
    if authority != "delegated":
        raise FreezeError("freeze.authority is ethan_only: an agent prepares a batch and Ethan freezes it "
                          "(CLAUDE.md hard rule 4)")
    if actor != "runner":
        raise FreezeError("a delegated freeze is the runner's, and the signed tag is still Ethan's")


# ---------------------------------------------------------------- verification (S17 C2)

OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
OTS_SHA256 = 0x08


class OpenTimestampsVerifier:
    """The production timestamp verifier: ``verify(proof, digest)`` returns only if ``proof`` is an OpenTimestamps
    proof of ``digest`` (the manifest's SHA-256) with a verified Bitcoin attestation, and raises ``FreezeError``
    otherwise.

    The detached-proof header is parsed here (magic, major version 1, SHA-256 file-hash operation, digest), so a
    file that is not a proof, or a proof of another file, is refused with its reason. Verifying the attestation
    needs an OpenTimestamps verifier with a Bitcoin block-header source; none is configured (no network client is
    installed or called), so every proof is then **refused**: fail closed, never accepted for existing."""

    def verify(self, proof: bytes, digest: bytes) -> None:
        if not isinstance(proof, (bytes, bytearray)) or not proof.startswith(OTS_MAGIC):
            raise FreezeError("the timestamp proof is not an OpenTimestamps proof")
        rest = bytes(proof[len(OTS_MAGIC):])
        if len(rest) < 2 + 32 or rest[0] != 0x01 or rest[1] != OTS_SHA256:
            raise FreezeError("the timestamp proof is not a version-1 OpenTimestamps proof of a SHA-256 file hash")
        if rest[2:34] != digest:
            raise FreezeError("the timestamp proof is for another file than this manifest")
        raise FreezeError("the timestamp proof's Bitcoin attestation cannot be verified: no OpenTimestamps verifier "
                          "with a block-header source is configured (fail closed). Owner action: provide one")


def _git(args: list, root: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None


_GPG_VALIDSIG = re.compile(r"^\[GNUPG:\] VALIDSIG (?:\S+ ){9}([0-9A-F]{40})\s*$", re.M)
_SSH_GOOD = re.compile(r'^Good "git" signature for \S+ with \S+ key (SHA256:[A-Za-z0-9+/=]+)\s*$', re.M)


def git_tag_signer(tag: str, root: Path, manifest_path: Path, raw: bytes) -> str | None:
    """The fingerprint of the key whose good signature ``git verify-tag`` accepts on ``tag``, provided the tagged
    commit holds exactly this manifest; ``None`` otherwise (no tag, a lightweight or unsigned tag, a bad signature,
    another manifest at the tag). GPG: the primary-key fingerprint of ``VALIDSIG``; SSH: the key's SHA256
    fingerprint. The signed object must name this batch and include exactly one
    manifest-sha256 line matching the manifest bytes. Signature and content checks use one immutable tag OID.
    Whether that key is the owner's is decided by the pin, not here."""
    root = Path(root).resolve()
    resolved = _git(["rev-parse", "--verify", f"refs/tags/{tag}^{{tag}}"], root)
    if resolved is None or resolved.returncode != 0:
        return None
    oid = resolved.stdout.decode("ascii", "replace").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
        return None
    obj = _git(["cat-file", "tag", oid], root)
    if obj is None or obj.returncode != 0:
        return None
    headers, sep, message = obj.stdout.partition(b"\n\n")
    lines = headers.splitlines()
    if not sep or [x for x in lines if x.startswith(b"type ")] != [b"type commit"] or \
            [x for x in lines if x.startswith(b"tag ")] != [b"tag " + tag.encode("ascii")]:
        return None
    digest_line = b"manifest-sha256: " + hashlib.sha256(raw).hexdigest().encode("ascii")
    if [x for x in message.splitlines() if x.startswith(b"manifest-sha256:")] != [digest_line]:
        return None
    v = _git(["verify-tag", "--raw", oid], root)
    if v is None or v.returncode != 0:
        return None
    out = (v.stderr or b"").decode("utf-8", "replace") + (v.stdout or b"").decode("utf-8", "replace")
    found = _GPG_VALIDSIG.findall(out) + _SSH_GOOD.findall(out)
    if len(set(found)) != 1:
        return None
    # ``<rev>:<path>`` is resolved from the repository's top level, whatever directory ``root`` is in it (the
    # batches directory by default): take the manifest's path relative to the top level
    top = _git(["rev-parse", "--show-toplevel"], root)
    if top is None or top.returncode != 0:
        return None
    try:
        toplevel = Path(top.stdout.decode("utf-8").strip()).resolve()
        rel = Path(manifest_path).resolve().relative_to(toplevel).as_posix()
    except (UnicodeDecodeError, ValueError):
        return None
    shown = _git(["show", f"{oid}^{{commit}}:{rel}"], root)
    if shown is None or shown.returncode != 0 or shown.stdout != raw:
        return None
    return found[0]


@dataclass(frozen=True)
class _Trust:
    """What ``verify_frozen`` trusts: the pinned signers, the tag-signature check and the timestamp verifier."""
    signers: frozenset
    tag_signer: Callable
    timestamp: object


_PRODUCTION = _Trust(frozenset(ALLOWED_FREEZE_SIGNERS), git_tag_signer, OpenTimestampsVerifier())
_TRUST = _PRODUCTION          # swapped only by the test-only seam under tests/ (pinned by a static test)


def verify_frozen(directory: Path, number: int, *, expected_manifest_hash: str | None = None,
                  root: Path | None = None) -> dict:
    """The runner's check before a designated evaluation: returns the manifest or raises ``FreezeError``.

    Internal consistency (canonical manifest, recorded hash, every spec, Merkle root), then the pin (an empty
    ``ALLOWED_FREEZE_SIGNERS`` refuses every batch), then the timestamp proof **verified** against the manifest's
    SHA-256, then the tag: signed, by a pinned key, on a commit holding this manifest. ``root``: the repository
    holding the tag (default ``directory``)."""
    return _verify_batch(Path(directory), number, expected_manifest_hash, root, _TRUST)


def _verify_batch(directory: Path, number: int, expected_manifest_hash: str | None, root, trust: _Trust) -> dict:
    d = directory / f"AB-{number:04d}"
    path = d / MANIFEST
    if not path.is_file():
        raise FreezeError(f"batch {number}: no manifest")
    raw = path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    if S.canonical_bytes(manifest) != raw:
        raise FreezeError(f"batch {number}: the manifest is not in canonical form (it was edited)")
    if expected_manifest_hash is not None and S.spec_hash(manifest) != expected_manifest_hash:
        raise FreezeError(f"batch {number}: the manifest does not match the hash recorded at its freeze")
    if type(manifest.get("batch")) is not int or manifest["batch"] != number:
        raise FreezeError(f"batch {number}: manifest batch identity mismatch")
    hashes, by_hash = [], {}
    for want in manifest["spec_hashes"]:
        matches = list((d / "specs").glob(f"*-{want[:S.ID_HEX]}.json"))
        if not matches:
            raise FreezeError(f"batch {number}: a spec named in the manifest is missing ({want[:S.ID_HEX]})")
        try:
            spec = S.read(matches[0])
        except S.SpecError as e:
            raise FreezeError(f"batch {number}: {e}") from e
        if S.spec_hash(spec) != want:
            raise FreezeError(f"batch {number}: {matches[0].name} no longer matches the manifest")
        hashes.append(want)
        by_hash[want] = spec
    designated_hypotheses = {}
    designations = manifest.get("designated_evaluations", [])
    if not isinstance(designations, list):
        raise FreezeError(f"batch {number}: malformed designated hypothesis binding")
    for designation in designations:
        try:
            exe = by_hash[designation["executable"]]
            variant = by_hash[exe["variant"]]
            hyp_hash = variant["hypothesis"]
            hyp = by_hash[hyp_hash]
            domain = designation["domain"]
            if exe["level"] != "executable" or variant["level"] != "variant" or hyp["level"] != "hypothesis" \
                    or hyp["domain"] != domain:
                raise ValueError("inconsistent designation")
            designated_hypotheses.setdefault(domain, set()).add(hyp_hash)
        except (KeyError, TypeError, ValueError):
            raise FreezeError(f"batch {number}: malformed designated hypothesis binding") from None
    if any(len(hs) != 1 for hs in designated_hypotheses.values()):
        raise FreezeError(f"batch {number}: only one designated hypothesis per (batch, domain) is supported")
    if L.merkle_root(hashes) != manifest["merkle_root"]:
        raise FreezeError(f"batch {number}: the Merkle root does not match the specs")
    if not trust.signers:
        raise FreezeError(f"batch {number}: {NO_PINNED_SIGNER}")
    proof = d / TIMESTAMP_PROOF
    if not proof.is_file():
        raise FreezeError(f"batch {number}: no external timestamp proof ({TIMESTAMP_PROOF})")
    try:
        trust.timestamp.verify(proof.read_bytes(), hashlib.sha256(raw).digest())
    except FreezeError as e:
        raise FreezeError(f"batch {number}: {e}") from None
    tag = TAG.format(n=number)
    signer = trust.tag_signer(tag, Path(root) if root is not None else directory, path, raw)
    if not signer:
        raise FreezeError(f"batch {number}: the tag {tag} is missing or not signed, or does not hold this manifest")
    if signer not in trust.signers:
        raise FreezeError(f"batch {number}: the tag {tag} is signed by {signer}, which is not a pinned owner key "
                          "(ALLOWED_FREEZE_SIGNERS)")
    return manifest
