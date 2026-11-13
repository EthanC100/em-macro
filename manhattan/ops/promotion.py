"""Promotion to any tier is disabled in code (criterion O-04).

A tier change (Protocol v3 section 8), a screening pass and formal support all rest on a protocol version that has
passed its simulation. None has: Protocol v3.0.0 and the draft v3.1 are not in force, and ``claims.enabled`` is
false. Until Ethan adopts a validated version, ``promote`` refuses everything.

Adopting is two deliberate acts, both Ethan's:

1. add the SHA-256 of the validated protocol file to ``ADOPTED_PROTOCOLS`` below, in a pull request he reviews
   (this file should be added to the protected block of ``.github/CODEOWNERS``:
   ``docs/manhattan/ops/ETHAN_OPS_ACTIONS.md`` step 8);
2. set ``claims.enabled: true`` in ``config/manhattan.yaml`` on main (already protected).

Neither alone is enough, so neither a config edit nor a code edit by a session can switch promotion on.
"""
from __future__ import annotations

ADOPTED_PROTOCOLS: frozenset[str] = frozenset()       # empty: no protocol version is validated and adopted
TIERS = ("screening_pass", "promising", "statistically_supported", "live_experiment_eligible", "scale_eligible",
         "formally_supported")


class PromotionDisabled(PermissionError):
    pass


def status(protocol_hash: str | None, config: dict | None) -> tuple[bool, str]:
    """(enabled, reason). Enabled only with an adopted protocol hash and ``claims.enabled: true``."""
    if not ADOPTED_PROTOCOLS:
        return False, "no_adopted_protocol"
    if protocol_hash not in ADOPTED_PROTOCOLS:
        return False, "protocol_not_adopted"
    if not (config or {}).get("claims", {}).get("enabled", False):
        return False, "claims_disabled"
    return True, "enabled"


def promote(family_id: str, tier: str, *, protocol_hash: str | None, config: dict | None) -> dict:
    """Request a tier change. Raises ``PromotionDisabled`` unless ``status`` says enabled; even then this returns
    only an intent for the statistics module (milestone H), which does not exist yet."""
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier}")
    enabled, reason = status(protocol_hash, config)
    if not enabled:
        raise PromotionDisabled(f"promotion to {tier} is disabled: {reason}")
    return {"family": family_id, "tier": tier, "protocol": protocol_hash, "state": "intent_needs_stats_module"}
