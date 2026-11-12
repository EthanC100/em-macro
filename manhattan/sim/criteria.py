"""SIM_PREREG sections 5 and 6 as data: thresholds, where each criterion is required, replication counts.

A test compares these numbers with the text of docs/manhattan/SIM_PREREG.md, so they cannot drift from it. No
threshold here is ever weakened to pass a method (section 8.1): a failing method is revised and tested again.
"""
from __future__ import annotations

REPLICATIONS = {"STD": 2000, "LONG": 2000, "HB": 400}
BOOTSTRAP_RESAMPLES = 2000
SMALL_GROUP = 200

V1_FDR_MAX = 0.22                       # M1, every checkpoint
V2_FDR_MAX = 0.06                       # M2, every checkpoint
V3_SIZE_MAX = {0.20: 0.22, 0.05: 0.06, 0.001: 0.0015}
V3_FWER_MAX = 0.06
V4_LINK_MAX = 0.22
V5_CROSS_MAX = {20: 0.06, 100: 0.015}
V6_SHARE_MIN = {0.80: 0.70, 0.40: 0.30}
V6_ECE_MAX = 0.10
V6_D01_HIGH_MAX = 0.01
V7_ELIM_MAX = 0.10
V7_LATE_MAX = 0.25
V8_BIAS_MAX, V8_BIAS_MIN = 0.10, -0.25
V10_M11_MAX = 0.06
V11_POWER_MIN = 0.50
SELECTION_MARGIN = 0.05                 # section 7: (i) only if better by at least this in average power

V1_EXEMPT = ("H05", "H11", "H08x")
V2_EXEMPT = ("H08x",)
V3_REQUIRED = ("D01", "D02", "D03", "D04", "D05", "D06", "D07a", "D07b", "D08", "D11", "H01", "H02a", "H03", "H04")
V5_REQUIRED = ("D01", "D05", "D06", "D07b", "H01", "H04")
V10_REQUIRED = ("D09a", "D09b")
V11_REQUIRED = ("P4",)
POWER_SCENARIOS = ("P1", "P2", "P3", "P4")


def required(criterion: str, scenario: str, size: str) -> bool:
    """Whether SIM_PREREG section 5 requires ``criterion`` (``"V1"`` ...) in this scenario at this size."""
    screen = size in ("STD", "LONG")
    if criterion in ("V1", "V4"):
        return screen and scenario not in V1_EXEMPT
    if criterion == "V2":
        return screen and scenario not in V2_EXEMPT
    if criterion == "V3":
        return scenario in V3_REQUIRED
    if criterion == "V5":
        return scenario in V5_REQUIRED
    if criterion in ("V6", "V7", "V8"):
        return size == "HB"
    if criterion == "V9":
        return scenario in ("H08m", "H08x")
    if criterion == "V10":
        return scenario in V10_REQUIRED
    if criterion == "V11":
        return scenario in V11_REQUIRED
    raise ValueError(criterion)
