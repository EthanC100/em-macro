"""HTE → PR #86 attempt accounting. **Dormant** (``bridge.ENABLED`` is a constant ``False``).

Registers every HTE candidate evaluation as a PR #86 exploration attempt, completes it with a deterministic
per-candidate result hash, stores candidate outcomes in batches of at most 512, and cross-checks HTE's native log
against the PR #86 ledger. Owner decisions D-1, D-10 and B4 are explicit policy fields with no default
(``policy``). Synthetic data and the exploration role only; never evidence.

This package lives outside ``manhattan/hte/`` so that HTE itself keeps importing nothing from PR #86. It imports
PR #86 modules only when a bridge is constructed. See docs/manhattan/hte_accounting/BRIDGE.md.
"""
from .policy import (B4_ALTERNATIVES, D1_ALTERNATIVES, D10_ALTERNATIVES, BridgePolicy, OwnerDecisionRequired,
                     OwnerDecisionUnsupported, denominator)

__all__ = ["BridgePolicy", "OwnerDecisionRequired", "OwnerDecisionUnsupported", "denominator", "D1_ALTERNATIVES",
           "D10_ALTERNATIVES", "B4_ALTERNATIVES"]
