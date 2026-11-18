"""The boundary between research candidates and evidence, and the equity research and promotion gates.

Everything this package produces — a pair candidate, an analogue match, a feature, a sensitivity, a diagnostic —
is a **research candidate** with evidential weight 0. A synthetic test shows that code behaves, not that a strategy
earns anything. A historical fit is at most an exploration-role result (ARCHITECTURE §6.3: weight 0).

**What is enforced, and where (S8 H3).** Both gates below live in this package and bind only code that calls them:
``promote`` here, and ``manhattan.equities.research`` (which calls ``require_research_scope``). They are **not**
integrated into Manhattan's protected pipeline: ``manhattan.ops.promotion.promote``, ``manhattan.engine.evaluate``
and the runner know nothing about asset classes, so an equity family spec pushed through them would meet only their
own gates (no adopted protocol, ``claims.enabled: false``, and after PR #86 the attempt registration). Making the
protected pipeline refuse out-of-scope domains is a change to owner-reviewed code and is recorded as an owner
decision (docs/manhattan/equities/PROTOCOL_EXTENSION_PROPOSAL.md section 3); it is not claimed here.

1. **Research gate** (``EQUITY_RESEARCH_APPROVED``, False): until Ethan approves an equities protocol extension,
   the research entry points accept only synthetic sources. Real-data equity research (public or licensed) is
   refused. A contract's licence is a declaration; the gate cannot see what bytes a store holds.
2. **Promotion** (``promote``) is shut twice: Manhattan's own gate (``manhattan.ops.promotion.status``: no protocol
   adopted, ``claims.enabled`` false), called, not copied; and ``EQUITY_COVERING_PROTOCOLS`` (empty). Protocol
   v3.0/v3.1 and the simulation pre-registrations were written for the existing macro universe: their core hedge
   (§2.2) names carry, trend, value and buy-and-hold factors per asset class, none is defined for single equities,
   and no simulation scenario has long/short equity books, borrow or delistings. The existing pre-registration is
   therefore **not** taken to cover a new asset class.

Changing either constant is a reviewed pull request after Ethan's decision, like ``promotion.ADOPTED_PROTOCOLS``.
``scope_status`` lists every reason the gates are shut.
"""
from __future__ import annotations

from dataclasses import dataclass

from manhattan.ops import promotion

from .errors import EvidenceError

EQUITY_COVERING_PROTOCOLS: frozenset[str] = frozenset()     # empty: no adopted protocol covers single equities
EQUITY_RESEARCH_APPROVED: bool = False                      # Ethan's approval of an equities protocol extension
CANDIDATE_KINDS = ("pair_candidate", "analogue_match", "feature", "sensitivity", "diagnostic", "synthetic_test",
                   "catalogue_entry")
PREREQUISITES = (
    "an adopted Manhattan protocol version whose scope names single technology equities",
    "equity core factors (market, sector, size, value, momentum, quality, ...) defined, daily, PIT and frozen",
    "simulation scenarios with long/short equity books, borrow costs, delistings and earnings events, passed",
    "binding attempt accounting implemented and approved (no reserve or forward test before it)",
    "licensed point-in-time equity data held outside the public repository, with verified contracts",
    "a frozen batch of equity hypothesis specs (Ethan's freeze; hard rule 4)",
    "the protected pipeline (promotion, evaluation, runner) refusing domains outside an adopted protocol's scope",
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
        if not (isinstance(self.ref, str) and len(self.ref) == 64 and all(c in "0123456789abcdef" for c in self.ref)):
            raise EvidenceError("a research record names its output by a SHA-256 provenance hash")


def require_research_scope(contracts) -> None:
    """Refuse research on anything but synthetic sources while equity research is not approved. ``contracts`` is a
    ``ContractRegistry`` (or iterable of ``DataContract``) declaring every source the research reads."""
    items = [contracts.contract(k) for k in contracts.kinds()] if hasattr(contracts, "kinds") else list(contracts)
    if not items:
        raise EvidenceError("research must declare the contracts of the data it reads")
    real = sorted(c.name for c in items if c.licence != "synthetic")
    if real and not EQUITY_RESEARCH_APPROVED:
        raise EvidenceError(f"equity research on non-synthetic sources {real} is not approved: it waits for Ethan's "
                            "decision on an equities protocol extension (EQUITY_RESEARCH_APPROVED is False)")


def scope_status(*, protocol_hash: str | None = None, config: dict | None = None) -> dict:
    enabled, reason = promotion.status(protocol_hash, config)
    reasons = [] if enabled else [f"manhattan promotion gate: {reason}"]
    if not EQUITY_RESEARCH_APPROVED:
        reasons.append("equity research on real data is not approved (EQUITY_RESEARCH_APPROVED is False)")
    if protocol_hash not in EQUITY_COVERING_PROTOCOLS:
        reasons.append("no adopted protocol version covers single equities (EQUITY_COVERING_PROTOCOLS is empty)")
    return {"open": not reasons, "reasons": tuple(reasons), "prerequisites": PREREQUISITES,
            "enforced_in_protected_pipeline": False}


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
