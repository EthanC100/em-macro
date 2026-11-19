"""Execution timing: one lag convention that names the three the repository already uses.

**The convention here.** A decision row ``t`` is taken at the close of trading day ``t`` from data published by
then. It executes at the settlement of trading day ``t + lag``. The position then earns from the close of
``t + lag``: its first return is day ``t + lag + 1``'s.

| convention | where | rule | ``lag`` here |
|---|---|---|---|
| ``same_close_fill_next_day_return/v1`` | HTE, PR #89 at 232d0d6, ``manhattan/hte/kernels.py`` | position row ``t`` is traded **at** close ``t`` and earns day ``t + 1`` | 0 |
| PR #85 ``ExecutionPolicy.lag`` | PR #85 at 3f6b213, ``manhattan/execution/account.py`` | executes at the settlement of the ``lag``-th close **strictly after** ``decided_at``; ``lag >= 1`` enforced | ``lag`` (a decision stamped at or after close ``t`` and before close ``t+1``) |
| ``Strategy.lag`` | main, ``manhattan/engine/backtest.py`` (Protocol v3.1 section 2.1) | decided at close ``D_j``, executed at close ``D_{j+lag}``; default 1, 0 allowed | ``lag`` (periods of the engine's union calendar, not trading days of one exchange) |

**Default 1, as PR #85.** A settlement is published after the close it belongs to (PR #85 requires ``known_at >=
close_at``), so a decision that reads close ``t`` cannot also have traded at it. Same-close (``lag = 0``) is
accepted only with ``allow_same_close=True`` and only to **measure** how optimistic it is; every result at lag 0 is
labelled ``throughput_only`` and cannot be presented as a trading return (``realism.py``).

**Lag counts trading days of the panel's calendar.** A day with no settlement for a root is still a calendar day:
the order then waits (``hold``) or the run stops (``raise``), as in PR #85. It is not skipped over, so a missing
price never shortens the lag.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import OptimisticExecutionError, UnitError

HTE_SAME_CLOSE = "same_close_fill_next_day_return/v1"
CONVENTIONS = {
    "hte_same_close": {"source": "PR #89 manhattan/hte/kernels.py EXECUTION_TIMING", "label": HTE_SAME_CLOSE,
                       "lag": 0, "realistic": False},
    "pr85_lag": {"source": "PR #85 manhattan/execution/account.py ExecutionPolicy.lag", "label": "pr85/lag>=1",
                 "lag": 1, "realistic": True},
    "engine_lag": {"source": "main manhattan/engine/backtest.py Strategy.lag (Protocol v3.1 section 2.1)",
                   "label": "engine/lag", "lag": 1, "realistic": True},
}
DEFAULT_LAG = 1


@dataclass(frozen=True)
class ExecutionTiming:
    lag: int = DEFAULT_LAG
    allow_same_close: bool = False

    def __post_init__(self):
        if isinstance(self.lag, bool) or not isinstance(self.lag, int) or self.lag < 0:
            raise UnitError("lag is a whole number of trading days, 0 or more")
        if self.lag == 0 and not self.allow_same_close:
            raise OptimisticExecutionError(
                "lag 0 fills at the close the decision was taken from (HTE's same-close convention): that price "
                "was not tradable once seen. Pass allow_same_close=True only to measure the optimism gap; the "
                "result is labelled throughput_only")

    @property
    def same_close(self) -> bool:
        return self.lag == 0

    @property
    def label(self) -> str:
        return HTE_SAME_CLOSE if self.same_close else f"close_t_decision_fill_close_t_plus_{self.lag}/v1"

    def execution_day(self, decision_day: int) -> int:
        return decision_day + self.lag

    def first_return_day(self, decision_day: int) -> int:
        return decision_day + self.lag + 1

    def as_dict(self) -> dict:
        return {"lag": self.lag, "same_close": self.same_close, "label": self.label}
