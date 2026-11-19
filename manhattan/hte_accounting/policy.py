"""Owner decisions the HTE → PR #86 attempt bridge depends on. Every one is explicit; none has a default.

The bridge never settles an owner decision by itself. A ``BridgePolicy`` whose field is ``None`` makes every
operation that needs that decision raise ``OwnerDecisionRequired``; an alternative that this code does not implement
raises ``OwnerDecisionUnsupported`` with the reason. The alternatives are listed here so that the decision can be
made from this file.

D-10 (PR #86, BINDING_ACCOUNTING.md): whether exploration evaluations register attempts.

    "unregistered"               PR #86's current position. HTE evaluations stay in HTE's own log only; the bridge
                                 registers nothing (it refuses, so a caller cannot believe it registered).
    "register_every_evaluation"  every HTE candidate evaluation that computes (the run until it closes, and every
                                 ``verify_rerun`` invocation) is a registered PR #86 exploration attempt.
    (rejected) "register_selected_only": registering only candidates that reach stage 3 would make the registered set
                                 depend on outcomes (stage-2 dominance, top-k): a denominator chosen after looking.

D-1 (PR #86): which counting unit enters a multiple-testing denominator. The bridge itself never needs it: it
records attempts and reports every unit separately (``crosscheck``). Only ``denominator()`` needs it, and refuses
without it. The units it can return are ``D1_ALTERNATIVES``.

B4 (PR #89): the cardinality of HTE work to PR #86 attempts.

    "per_candidate_attempts"     one PR #86 attempt per candidate evaluation (PR #86's contract: an attempt is one
                                 executable), with candidate outcomes stored in batches of at most 512 per file and
                                 referenced from each completion. Implemented. 2 ledger records and about 3.56 kB of
                                 ledger per candidate (measured, section 6 of docs/manhattan/hte_accounting/BRIDGE.md).
    "per_chunk_attempt"          one PR #86 attempt per HTE chunk of up to 512 candidates. Not implementable without a
                                 new PR #86 attempt kind (its identity is one executable): a change to PR #86's
                                 accounting, which this bridge does not make. Refused.
"""
from __future__ import annotations

from dataclasses import dataclass

D10_ALTERNATIVES = ("unregistered", "register_every_evaluation")
D10_REJECTED = {"register_selected_only": "the registered set would depend on stage-1/2 outcomes"}
D1_ALTERNATIVES = ("registered_executions", "completed_evaluation_keys", "executables", "bindings", "candidates",
                   "variants", "hypotheses", "families")
B4_ALTERNATIVES = ("per_candidate_attempts", "per_chunk_attempt")
B4_IMPLEMENTED = ("per_candidate_attempts",)


class OwnerDecisionRequired(PermissionError):
    """An operation needs an owner decision that the policy does not state."""


class OwnerDecisionUnsupported(PermissionError):
    """The policy names an alternative this code does not implement (or rejects)."""


@dataclass(frozen=True)
class BridgePolicy:
    """The owner decisions, each with the reference to where it was approved. ``None`` means "not decided"."""
    d10_registration: str | None = None
    d1_counting_unit: str | None = None
    b4_cardinality: str | None = None
    approval_ref: str | None = None           # where the owner recorded the decisions (PR, issue, doc); required

    def __post_init__(self):
        d10 = D10_ALTERNATIVES + tuple(D10_REJECTED)
        for name, value, allowed in (("d10_registration", self.d10_registration, d10),
                                     ("d1_counting_unit", self.d1_counting_unit, D1_ALTERNATIVES),
                                     ("b4_cardinality", self.b4_cardinality, B4_ALTERNATIVES)):
            if value is not None and value not in allowed:
                raise ValueError(f"{name} must be one of {allowed} or None (undecided)")

    def require_registration(self) -> None:
        """The decisions the bridge needs before it writes anything to PR #86."""
        if self.d10_registration is None:
            raise OwnerDecisionRequired("D-10 (do exploration evaluations register attempts?) is not decided; "
                                        f"alternatives: {D10_ALTERNATIVES}")
        if self.d10_registration in D10_REJECTED:
            raise OwnerDecisionUnsupported(f"D-10 '{self.d10_registration}' is rejected: "
                                           f"{D10_REJECTED[self.d10_registration]}")
        if self.d10_registration == "unregistered":
            raise OwnerDecisionUnsupported("D-10 is 'unregistered': HTE evaluations are not registered in PR #86, "
                                           "so the bridge writes nothing")
        if self.b4_cardinality is None:
            raise OwnerDecisionRequired(f"B4 (attempt cardinality) is not decided; alternatives: {B4_ALTERNATIVES}")
        if self.b4_cardinality not in B4_IMPLEMENTED:
            raise OwnerDecisionUnsupported(f"B4 '{self.b4_cardinality}' needs a new PR #86 attempt kind (an attempt "
                                           "is one executable); not implemented")
        if not (isinstance(self.approval_ref, str) and self.approval_ref.strip()):
            raise OwnerDecisionRequired("the policy names no approval reference for its decisions")

    def as_dict(self) -> dict:
        return {"d10_registration": self.d10_registration, "d1_counting_unit": self.d1_counting_unit,
                "b4_cardinality": self.b4_cardinality, "approval_ref": self.approval_ref}


def denominator(report: dict, policy: BridgePolicy) -> dict:
    """The count of the D-1 unit from a ``crosscheck`` report. Refuses while D-1 is undecided; never a default."""
    if policy.d1_counting_unit is None:
        raise OwnerDecisionRequired(f"D-1 (counting unit) is not decided; alternatives: {D1_ALTERNATIVES}. "
                                    "Every unit is reported separately in report['units'].")
    if not (isinstance(policy.approval_ref, str) and policy.approval_ref.strip()):
        raise OwnerDecisionRequired("the policy names no approval reference for D-1")
    return {"unit": policy.d1_counting_unit, "count": report["units"][policy.d1_counting_unit],
            "approval_ref": policy.approval_ref}
