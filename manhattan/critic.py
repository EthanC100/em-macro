"""The Manhattan critic (ARCHITECTURE.md section 5.2): reviews every family and hypothesis before a freeze.

The critic sees **specs only**. ``review_input`` builds what it is given and refuses a bundle that carries any
outcome. ``parse_review`` validates what it returns: the JSON of The Opposition (a probability that the idea
works, a summary, and at most a block). It can block only for the four reasons below; "weak economics" is an
opinion, logged with its probability, and never a block. The review is data, not instructions.

This module builds and checks; it does not call a model. The critic's definition under ``.claude/agents/`` is
Ethan's to add (ETHAN_ACTIONS item 7).
"""
from __future__ import annotations

import json

from . import ledger as L
from . import spec as S

BLOCK_REASONS = ("look_ahead", "duplicate_t25_t26", "licensed_data_leak", "undeclared_grid")
QUESTIONS = ("Is the mechanism one mechanism?", "Is the sign predicted?", "Is the counterparty named?",
             "Does any data definition look ahead (publication lags, vintages)?", "Is the grid declared and bounded?",
             "Does the family duplicate an existing family, a trial or the T25-T26 shadows?",
             "Is the tail exposure declared?")


class CriticError(ValueError):
    pass


def review_input(families: list[dict], hypotheses: list[dict]) -> str:
    """The critic's whole input: the specs in canonical form and the questions. Nothing else can be passed in,
    and a spec that carries an outcome field is refused before the critic sees it."""
    for sp in families + hypotheses:
        bad = L.outcome_keys_in(sp)
        if bad:
            raise CriticError(f"{S.spec_id(sp)} carries outcome fields ({', '.join(bad)}): the critic sees specs only")
    errs = [e for f in families for e in S.validate_family(f)] + [e for h in hypotheses for e in S.validate_hypothesis(h)]
    if errs:
        raise CriticError("; ".join(errs))
    body = {"questions": list(QUESTIONS), "block_only_for": list(BLOCK_REASONS),
            "specs": [json.loads(S.canonical_bytes(sp)) for sp in families + hypotheses]}
    return json.dumps(body, sort_keys=True, ensure_ascii=False)


def parse_review(reply: str, target: dict) -> dict:
    """A validated review of one spec: ``{target, p_works, summary, block, block_reason}``."""
    try:
        obj = json.loads(reply)
    except json.JSONDecodeError as e:
        raise CriticError(f"the review is not JSON: {e}") from e
    if not isinstance(obj, dict):
        raise CriticError("the review must be a JSON object")
    p = obj.get("p_works")
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 100:
        raise CriticError("p_works must be a number from 0 to 100")
    summary = obj.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise CriticError("the review needs a summary")
    block = bool(obj.get("block", False))
    reason = obj.get("block_reason")
    if block and reason not in BLOCK_REASONS:
        raise CriticError(f"a block needs one of the allowed reasons {BLOCK_REASONS}; anything else is advice")
    if not block and reason is not None:
        reason = None
    return {"target": S.spec_hash(target), "target_id": S.spec_id(target), "p_works": float(p),
            "summary": summary.strip(), "block": block, "block_reason": reason}


def record(ledger: L.Ledger, review: dict) -> dict:
    """Write a review to the full ledger as a ``critic_review`` record; its hash goes in the batch manifest."""
    return ledger.append("critic_review", review)


def blocked(reviews: list[dict]) -> list[dict]:
    return [r for r in reviews if r["block"]]
