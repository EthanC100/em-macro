"""SIM_PREREG_v2 as data: what changed with Protocol v3.1, and nothing else.

Every threshold of version 1 stands (``manhattan/sim/criteria.py``); this file adds scenarios and requirements
and loosens nothing. A test compares these numbers with the text of docs/manhattan/SIM_PREREG_v2.md.
"""
from __future__ import annotations

from . import criteria as v1
from .pipeline_v2 import TWINS                      # SPA only: a version 1 scenario with D11's hedge layer

# section 3: runs made by version 2's code. Everything else is run by version 1's code, unchanged.
HEDGED_FULL = ("D11",)                              # the full pipeline with the hedge-aware SPA test
HEDGED_HELD_OUT = ("H12",)                          # defined in section 3.2 of v2; not coded, not run

# section 6: replication counts. None of version 1's is lowered.
REPLICATIONS = v1.REPLICATIONS                      # the same object: STD 2,000, LONG 2,000, HB 400
REPLICATIONS_TWIN = 400                             # then extended until the half-widths below are met
TWIN_HALF_WIDTH_MAX = {0.20: 0.02, 0.05: 0.01}      # version 1's precision target (its section 6)

# section 5: thresholds. V3 is version 1's, now also required on the hedge-aware test in D11, the twins and H12.
V3_SIZE_MAX = v1.V3_SIZE_MAX
V3_FWER_MAX = v1.V3_FWER_MAX
V3_REQUIRED = v1.V3_REQUIRED + tuple(TWINS) + HEDGED_HELD_OUT
# V6-V8 are version 1's, on the analytic model. New: every review must be computed.
V6_SHARE_MIN, V6_ECE_MAX, V6_D01_HIGH_MAX = v1.V6_SHARE_MIN, v1.V6_ECE_MAX, v1.V6_D01_HIGH_MAX
V7_ELIM_MAX, V7_LATE_MAX = v1.V7_ELIM_MAX, v1.V7_LATE_MAX
V8_BIAS_MAX, V8_BIAS_MIN = v1.V8_BIAS_MAX, v1.V8_BIAS_MIN
V12_REVIEWS_NOT_COMPUTED_MAX = 0                    # V12: no review may be "model not computed"
EDGE_MASS_MAX = 0.01                                # the gate that replaces the sampler's convergence gate


def is_twin(scenario: str) -> bool:
    return scenario in TWINS


def replications(scenario: str, size: str) -> int:
    return REPLICATIONS_TWIN if is_twin(scenario) else REPLICATIONS[size]
