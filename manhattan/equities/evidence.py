"""The boundary between research candidates and evidence, and the protocol-scope gate for equities.

Everything this package produces — a pair candidate, an analogue match, a feature, a sensitivity, a diagnostic —
is a **research candidate** with evidential weight 0. A synthetic test shows that code behaves, not that a strategy
earns anything. A historical fit is at most an exploration-role result (ARCHITECTURE §6.3: weight 0).

``promote`` is the only door from a candidate towards a tier, and it is shut twice:

1. **Manhattan's own gate** (``manhattan.ops.promotion.status``): no protocol version is adopted and
   ``claims.enabled`` is false. This module calls it; it does not copy or change it.
2. **The equity-scope gate** (``EQUITY_COVERING_PROTOCOLS``, empty): Protocol v3.0/v3.1 and the simulation
   pre-registrations were written for the existing macro universe. Their core hedge (§2.2) names carry, trend,
   value and buy-and-hold factors per asset class, and no daily core factors are defined for single equities;
   the simulation scenarios contain no long/short equity books, borrow costs or delisting outcomes. The existing
   pre-registration is therefore **not** taken to cover a new asset class. A future protocol version that does
   (docs/manhattan/equities/PROTOCOL_EXTENSION_PROPOSAL.md) is Ethan's to write, simulate and adopt; only then would
   its hash be added here, in a reviewed pull request.

``scope_status`` lists every reason the gate is shut, for reports.
"""
from __future__ import annotations

from dataclasses import dataclass

from manhattan.ops import promotion

from .errors import EvidenceError

EQUITY_COVERING_PROTOCOLS: frozenset[str] = frozenset()     # empty: no adopted protocol covers single equities
CANDIDATE_KINDS = ("pair_candidate", "analogue_match", "feature", "sensitivity", "diagnostic", "synthetic_test",
                   "catalogue_entry")
PREREQUISITES = (
    "an adopted Manhattan protocol version whose scope names single technology equities",
    "equity core factors (market, sector, size, value, momentum, quality, ...) defined, daily, PIT and frozen",
    "simulation scenarios with long/short equity books, borrow costs, delistings and earnings events, passed",
    "binding attempt accounting implemented and approved (no reserve or forward test before it)",
    "licensed point-in-time equity data held outside the public repository, with verified contracts",
    "a frozen batch of equity hypothesis specs (Ethan's freeze; hard rule 4)",
)


@dataclass(frozen=True)
class ResearchRecord:
    kind: str
    ref: str                          # provenance hash of the output (manhattan.equities.provenance)
    evidential_weight: int = 0

    def __post_init__(self):
        if self.kind not in CANDIDATE_KINDS:
            raise EvidenceError(f"unknown research record kind {self.kind!r}")
        if self.evidential_weight != 0:
            raise EvidenceError("a research candidate carries zero evidential weight")


def scope_status(*, protocol_hash: str | None = None, config: dict | None = None) -> dict:
    enabled, reason = promotion.status(protocol_hash, config)
    reasons = [] if enabled else [f"manhattan promotion gate: {reason}"]
    if protocol_hash not in EQUITY_COVERING_PROTOCOLS:
        reasons.append("no adopted protocol version covers single equities (EQUITY_COVERING_PROTOCOLS is empty)")
    return {"open": not reasons, "reasons": tuple(reasons), "prerequisites": PREREQUISITES}


def promote(record: ResearchRecord, tier: str, *, protocol_hash: str | None = None, config: dict | None = None):
    """Refuses: a candidate becomes evidence only through a frozen spec evaluated under an adopted protocol that
    covers equities. Raises ``EvidenceError`` with every reason."""
    if tier not in promotion.TIERS:
        raise ValueError(f"unknown tier {tier}")
    st = scope_status(protocol_hash=protocol_hash, config=config)
    if record.kind in ("synthetic_test", "catalogue_entry"):
        raise EvidenceError(f"a {record.kind} is never evidence about markets")
    if not st["open"]:
        raise EvidenceError(f"promotion of {record.kind} {record.ref[:12]} to {tier} refused: "
                            + "; ".join(st["reasons"]))
    # Even with both gates open, a research candidate itself is not what gets promoted: the family's frozen
    # executables are, through manhattan.ops.promotion and the statistics module.
    raise EvidenceError("research candidates are inputs to hypothesis specs; promote the frozen family instead")
