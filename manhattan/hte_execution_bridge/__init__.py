"""Dormant bridge from HTE candidates (PR #89) to the execution-realism adapter (PR #93), with PR #85's timing.
**Research only; synthetic inputs only; wired into nothing.**

Design and connection requirements: docs/manhattan/HTE_EXECUTION_BRIDGE.md.

    clock      HTE rows -> decision timestamps; PR #85's "lag-th close strictly after decided_at"
    market     HTE returns -> contract-aware synthetic settlements, rolls, ADV, FX; HTE costs -> contract terms
    scaling    vol scaling from what each decision could know, as decision-row weights
    identity   the executable spec with the execution assumptions in it; data hash and market digest
    bridge     CandidateInput, BridgeSettings (lag 1 default), translate, evaluate, from_hte, disabled stage
    compare    HTE throughput-only versus delayed contract execution, labelled, without profitability claims
    fixtures   HTE-shaped synthetic candidates with planted effects

**What this is not.** It imports neither HTE nor PR #85 (HTE's functions are passed in by a caller); it places no
order, has no broker or network connection, reads no file or environment variable and writes no record.
``ENABLED`` is ``False``; ``HteExecutionStage`` refuses construction until ``CONNECTION_REQUIREMENTS`` are met.
"""
from .bridge import (CONNECTION_REQUIREMENTS, ENABLED, BridgeResult, BridgeSettings, CandidateInput,
                     HteExecutionStage, evaluate, from_hte, pr85_decision_records, translate)
from .errors import BridgeDisabled, BridgeError

RESEARCH_ONLY = True
CALIBRATED = False

__all__ = ["CALIBRATED", "CONNECTION_REQUIREMENTS", "ENABLED", "RESEARCH_ONLY", "BridgeDisabled", "BridgeError",
           "BridgeResult", "BridgeSettings", "CandidateInput", "HteExecutionStage", "evaluate", "from_hte",
           "pr85_decision_records", "translate"]
