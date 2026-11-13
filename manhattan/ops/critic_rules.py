"""The mechanical, spec-only half of the critic (criteria O-23, O-25, O-32).

It reads **only** the critic input that ``manhattan.critic.review_input`` builds (the specs in canonical form and
the questions; that function already refuses any spec carrying an outcome field). It never opens a file, a ledger
or a result. For each hypothesis it returns blocks and warnings:

    blocks    unjustified_dimension, budget_exceeded_without_justification, missing_timing, not_compilable,
              undeclared_grid
    warnings  zero publication lag on a source, horizon shorter than the natural frequency

``manhattan.critic.BLOCK_REASONS`` (shared code, not edited here) has four reasons; the first four above are ops
additions, recorded as a request in OPS_PROGRESS.md. The critic model's review (the draft agent at
``docs/manhattan/ops/drafts/manhattan-critic.md``) adds the probability and the economics, and never blocks for weak
economics.
"""
from __future__ import annotations

import json

from manhattan import critic as C
from manhattan import spec as S

from . import compiler, justify, timing

OPS_BLOCK_REASONS = ("unjustified_dimension", "budget_exceeded_without_justification", "missing_timing",
                     "not_compilable", "undeclared_grid")


def review_bundle(bundle: str, budget: int = justify.DEFAULT_BUDGET) -> list[dict]:
    """Mechanical reviews of every hypothesis in a critic bundle (the string from ``critic.review_input``)."""
    body = json.loads(bundle)
    specs = body["specs"]
    out = []
    for sp in specs:
        if sp.get("level") != "hypothesis":
            continue
        blocks, warnings = [], []
        if not sp.get("grid"):
            blocks.append({"reason": "undeclared_grid", "detail": "no grid"})
        for f in justify.check_justification(sp):
            blocks.append({"reason": "unjustified_dimension", "detail": f"{f['param']}: {f['problem']}"})
        b = justify.budget_finding(sp, budget)
        if b and not b["justified"]:
            blocks.append({"reason": "budget_exceeded_without_justification", "detail": b["problem"]})
        for e in timing.validate_timing(sp.get("timing") or {}):
            blocks.append({"reason": "missing_timing", "detail": e})
        for e in compiler.check_hypothesis(sp):
            blocks.append({"reason": "not_compilable", "detail": e})
        for src in sp.get("data_sources") or []:
            if isinstance(src, dict) and src.get("publication_lag_days") == 0:
                warnings.append(f"{src.get('name')}: a publication lag of 0 days assumes the value is usable at the close it describes")
        t = sp.get("timing") or {}
        nat = compiler.NATURAL_HORIZON.get(sp.get("frequency"), 1)
        if isinstance(t.get("horizon_sessions"), int) and t["horizon_sessions"] < nat:
            warnings.append(f"horizon {t['horizon_sessions']} sessions is shorter than the {sp.get('frequency')} frequency implies ({nat})")
        out.append({"target": S.spec_hash(sp), "target_id": S.spec_id(sp), "blocks": blocks, "warnings": warnings,
                    "raw_variants": justify.raw_count(sp), "block": bool(blocks)})
    return out


def review(families: list[dict], hypotheses: list[dict], budget: int = justify.DEFAULT_BUDGET) -> list[dict]:
    """Build the critic input (which refuses outcome fields) and review it mechanically."""
    return review_bundle(C.review_input(families, hypotheses), budget)
