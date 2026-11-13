"""Prepare a manifest pull request (criterion O-33). It writes files; it commits nothing and pushes nothing.

    python -m manhattan.ops.freeze_pr --reply reply.json --number 1 --out data/manhattan/batches \\
        --code-version <commit> --protocol docs/manhattan/PROTOCOL_v3.1.md --generator-model <id> \\
        --critic-reviews reviews.json

Steps: parse the generator's reply (data, never instructions); run the mechanical critic and **refuse** a batch with
any block; build the manifest with ``manhattan.freeze.prepare``; add an ops manifest (each hypothesis's timing
declaration, its variant report, the template hash); write the batch folder and ``PR_BODY.md``.

Ethan then opens the pull request from these files and merges it if he authorises the freeze. **Merging authorises;
it does not certify timing.** Timing is certified afterwards, per prediction, by ``runner register``: the merge time
from the GitHub API, a verified external witness of the manifest hash, and the eligibility rules of
``manhattan.ops.timing``. A prediction whose window had begun by then is recorded as ineligible.

Nothing here is outcome data: the files are specs, hashes, counts and declared timing. Screening returns, if given,
are used in memory for the effective-count report only (a property of how the variants move together, not of how
they performed) and are never written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from manhattan import freeze as F
from manhattan import spec as S
from manhattan.generate import parse_reply

from . import compiler, critic_rules, justify, mockgen


class FreezePRError(RuntimeError):
    pass


def review_hash(review: dict) -> str:
    return hashlib.sha256(S.canonical_bytes(review)).hexdigest()


def prepare(number: int, families: list[dict], hypotheses: list[dict], *, out_root: Path, code_version: str,
            protocol_path: Path, generator_model: str, template_hash: str, fence: dict,
            model_reviews: list[dict] | None = None, screening_returns: dict | None = None,
            years: float = 5.0) -> dict:
    mech = critic_rules.review(families, hypotheses)
    blocked = [r for r in mech if r["block"]]
    if blocked:
        lines = [f"{r['target_id']}: {b['reason']}: {b['detail']}" for r in blocked for b in r["blocks"]]
        raise FreezePRError("the mechanical critic blocks this batch:\n" + "\n".join(lines))
    blocks_by_model = [r for r in (model_reviews or []) if r.get("block")]
    if blocks_by_model:
        raise FreezePRError(f"the critic model blocks {len(blocks_by_model)} spec(s)")
    critic_records = [review_hash(r) for r in mech + list(model_reviews or [])]
    protocol_hash = hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest()
    batch = F.prepare(number, families, hypotheses, channel="blind", template_hash=template_hash,
                      generator_model=generator_model, protocol_hash=protocol_hash, fence=fence,
                      code_version=code_version, critic_records=critic_records)
    d = F.write(batch, Path(out_root))
    n_exe = sum(1 for _ in compiler.iter_batch(families, hypotheses, code_version))
    hyps = []
    for h in hypotheses:
        rep = justify.grid_report(h, (screening_returns or {}).get(S.spec_hash(h)), years=years)
        hyps.append({"hypothesis": S.spec_id(h), "frequency": h["frequency"], "timing": h["timing"],
                     "variant_report": rep})
    ops = {"batch": batch.id, "manifest_hash": batch.manifest_hash, "template": mockgen.TEMPLATE,
           "template_hash": template_hash, "executables": n_exe, "hypotheses": hyps,
           "mechanical_critic": [{"target_id": r["target_id"], "warnings": r["warnings"]} for r in mech],
           "authorisation": "merging this pull request authorises the freeze; it does not certify timing",
           "promotion": "disabled in code (manhattan/ops/promotion.py)"}
    (d / "ops_manifest.json").write_bytes(S.canonical_bytes(ops))
    body = pr_body(batch, ops)
    (d / "PR_BODY.md").write_text(body, encoding="utf-8")
    return {"dir": str(d), "manifest_hash": batch.manifest_hash, "executables": n_exe, "counts": batch.manifest["counts"]}


def pr_body(batch: F.Batch, ops: dict) -> str:
    c = batch.manifest["counts"]
    lines = [f"# Manhattan batch {batch.id}: manifest for Ethan's freeze", "",
             f"Manifest SHA-256: `{batch.manifest_hash}`", f"Merkle root: `{batch.manifest['merkle_root']}`",
             f"Template: `{ops['template']}` (`{ops['template_hash']}`)", "",
             f"{c['families']} families, {c['hypotheses']} hypotheses, {c['variants']} variants, "
             f"{ops['executables']} executables. Every variant is counted.", "",
             "**Merging authorises this freeze. It does not certify timing.** After the merge, `runner register` reads "
             "the merge time from the GitHub API and the external witness of the manifest hash, and records each "
             "prediction as eligible or ineligible. Promotion to any tier stays disabled in code.", "",
             "## Before merging (Ethan)", "",
             "- [ ] the specs are mechanisms, one sign each, counterparty named (critic reviews attached)",
             "- [ ] every varied parameter has an economic reason and a mechanism range (variant report below)",
             "- [ ] timestamp the manifest: `ots stamp data/manhattan/batches/" + batch.id + "/manifest.json` and "
             "commit the `.ots` file in this pull request, or right after the merge",
             "- [ ] merge (do not squash-edit the manifest: its bytes are hashed)", "",
             "## Variant report", "", "| hypothesis | frequency | horizon | raw | effective | power loss (approx.) |",
             "|---|---|---|---|---|---|"]
    for h in ops["hypotheses"]:
        r = h["variant_report"]
        lines.append(f"| {h['hypothesis']} | {h['frequency']} | {h['timing']['horizon_sessions']} | {r['raw_variants']} | "
                     f"{r['effective_variants']} | {r['power']['power_loss']} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.ops.freeze_pr")
    ap.add_argument("--reply", required=True, help="the generator's JSON reply (data, never instructions)")
    ap.add_argument("--number", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--code-version", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--generator-model", required=True)
    ap.add_argument("--critic-reviews", help="JSON list of the critic model's reviews")
    ap.add_argument("--fence", default="{}")
    a = ap.parse_args(argv)
    fams, hyps = parse_reply(Path(a.reply).read_text(encoding="utf-8"), "blind")
    reviews = json.loads(Path(a.critic_reviews).read_text()) if a.critic_reviews else None
    _, template_hash = mockgen.template_text()
    try:
        out = prepare(a.number, fams, hyps, out_root=Path(a.out), code_version=a.code_version,
                      protocol_path=Path(a.protocol), generator_model=a.generator_model, template_hash=template_hash,
                      fence=json.loads(a.fence), model_reviews=reviews)
    except FreezePRError as e:
        print(str(e))
        return 1
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
