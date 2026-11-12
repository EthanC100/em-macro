"""Freezing a batch (ARCHITECTURE.md section 5.4).

A batch is frozen as a whole: its specs are validated, hashed and enumerated; a manifest lists every spec hash
and their Merkle root, the template hash, the generator model, the protocol hash, the data-role fence in force,
the designated evaluations and the critic records; the commit that holds them gets a **signed tag** and the
manifest hash an **external timestamp**. Only then may a designated evaluation start.

Under CLAUDE.md hard rule 4 a freeze is a pre-registration and is Ethan's (``freeze.authority: ethan_only``):
an agent **prepares** a batch (``prepare``), Ethan reviews, merges, tags and timestamps. ``authorise`` refuses an
agent's freeze. ``verify_frozen`` is the runner's check before any designated evaluation, and it refuses a batch
whose tag is missing or unsigned, whose manifest or specs no longer match their hashes, or whose timestamp proof
is missing.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import ledger as L
from . import spec as S

MANIFEST = "manifest.json"
TIMESTAMP_PROOF = "manifest.json.ots"
TAG = "manhattan-batch-{n:04d}"
CHANNELS = S.CHANNELS


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
    evaluation there. Adaptive specs get none (they carry no evidential weight on the reserve)."""
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


def git_tag_is_signed(tag: str, root: Path) -> bool:
    """True when ``git verify-tag`` accepts the tag (a lightweight or unsigned tag does not pass)."""
    try:
        return subprocess.run(["git", "verify-tag", tag], cwd=root, capture_output=True).returncode == 0
    except OSError:
        return False


def verify_frozen(directory: Path, number: int, *, expected_manifest_hash: str | None = None, root: Path | None = None,
                  tag_is_signed=git_tag_is_signed) -> dict:
    """The runner's check before a designated evaluation: returns the manifest or raises ``FreezeError``."""
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
    hashes = []
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
    if L.merkle_root(hashes) != manifest["merkle_root"]:
        raise FreezeError(f"batch {number}: the Merkle root does not match the specs")
    if not (d / TIMESTAMP_PROOF).is_file():
        raise FreezeError(f"batch {number}: no external timestamp proof ({TIMESTAMP_PROOF})")
    if not tag_is_signed(TAG.format(n=number), root or directory):
        raise FreezeError(f"batch {number}: the tag {TAG.format(n=number)} is missing or not signed")
    return manifest
