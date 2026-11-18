"""The funnel policy: every rule that decides what is computed, fixed and hashed before a run starts.

The policy hash is part of the run identity, so changing any rule after seeing results creates a *new* run that
is logged and counted as another look at the same candidates (packages report how many runs looked at each set).

**No performance threshold by default.** The default policy advances every eligible candidate to stage 3. The only
stage-1 gates are outcome-sign-blind:

* ``degenerate``: the candidate never holds a position in the evaluation window (no return series to test);
* ``behavioural alias``: its positions and binding are bit-identical to an earlier candidate's (same results by
  construction; computed once, reported for every member, still counted);
* ``dominated``: an exact Hölder bound shows its stage-2 net mean cannot be positive (kernels.stage1). The bound
  uses ``|r|`` only, so flipping the sign of every return leaves every stage-1 decision unchanged (tested).
  ``skip_stage3_if_dominated`` decides whether such candidates also skip stage 3; they stay registered, counted and
  packaged either way. Stage 4's family SPA is complete only when no non-degenerate candidate skipped stage 3.

``stage3_selection = "top_k_per_spec"`` is a *performance gate* (ranked on stage-2 t-statistics). It exists for
benchmarking the selection path and is marked ``benchmark_only``: packages built under it say that their stage-3
statistics are conditional on a recorded selection and are not adjusted for it. It is never a research threshold.

Every numeric constant here is an engineering default of this synthetic engine, not a value from the frozen
protocols (PROTOCOL_v3.1, SIM_PREREG_v2), which this module neither reads nor changes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from . import ids

SELECTIONS = ("all_eligible", "top_k_per_spec")


@dataclass(frozen=True)
class Policy:
    name: str = "hte-default"
    version: int = 1
    warmup: int = 300                    # first evaluated day; every feature is defined by then (MAX_LOOKBACK 260)
    skip_stage3_if_dominated: bool = True
    dedup_behavioural: bool = True
    stage3_selection: str = "all_eligible"
    top_k: int = 0
    vol_target_ann: float = 0.10
    vol_halflife: int = 20
    vol_min_obs: int = 20
    leverage_cap: float = 5.0
    bootstrap_B: int = 999               # the Protocol's first SPA step size; descriptive here
    bootstrap_L: int = 20                # fixed mean block length (the Protocol estimates L; this engine fixes it)
    meff_cap: int = 1000                 # stage 4: M_eff on at most this many series per hypothesis (outcome-blind)
    benchmark_only: bool = False

    def __post_init__(self):
        if self.stage3_selection not in SELECTIONS:
            raise ValueError(f"stage3_selection must be one of {SELECTIONS}")
        if self.stage3_selection == "top_k_per_spec":
            if self.top_k < 1:
                raise ValueError("top_k_per_spec needs top_k >= 1")
            if not self.benchmark_only:
                raise ValueError("a performance-ranked selection is allowed only with benchmark_only=True")
        if self.bootstrap_B < 99 or self.bootstrap_L < 1 or self.warmup < 261:
            raise ValueError("bootstrap_B >= 99, bootstrap_L >= 1 and warmup >= 261 are required")

    @property
    def performance_gate(self) -> bool:
        return self.stage3_selection != "all_eligible"

    def as_dict(self) -> dict:
        return asdict(self)

    def hash(self) -> str:
        return ids.full_hash(self.as_dict())
