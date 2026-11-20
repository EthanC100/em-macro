"""Execution realism: the bridge from HTE's same-close throughput benchmark to delayed, costed, contract-level
execution for historical exploratory research. **Research infrastructure only.**

Design, comparison of PR #85 and PR #89, minimum requirements and blockers: docs/manhattan/EXECUTION_REALISM.md.

    timing        the lag convention (default 1, as PR #85); lag 0 only to measure same-close optimism
    instruments   multiplier, tick size, tick value, adverse tick rounding (PR #85's decimal arithmetic)
    provenance    known / estimated / scenario cost sources; "calibrated" refused
    costs         per-root cost terms with sources; one fill (PR #85's fill arithmetic, conformance-tested)
    panel         contract-aware daily settlements, rolls, liquidity and FX; adjusted series refused
    adapter       weights or contracts in, delayed fills, rolls, missing prices, FX, daily gross and net out
    realism       minimum requirements R1-R9, labels, and the only gate to a presentable return figure
    sensitivity   cost x lag x shock grids, the same-close optimism gap, break-even cost multiples
    screening     HTE-shaped (n, A) matrices with a lag: the reference for HTE's own next step
    fixtures      synthetic world with planted same-close-only and lag-robust effects

**What this is not.** It places no order and has no broker, exchange or network connection; it reads no file and
no environment variable, and holds no market data or calibrated cost. Nothing imports it (not the engine, the ops
runner, the Ledger, Janus, HTE or the night shift), and it writes no record: nothing it computes is evidence, an
attempt, a claim or a trade. ``CALIBRATED`` is ``False`` and no output says "realistic".
"""
from .adapter import ExecutionPolicy, ExecutionResult, Shocks, execute, size
from .costs import CostModel, CostValue, RootCosts, hte_equivalent_coefficients, one_way_cost_fraction
from .instruments import Instrument
from .panel import SettlementPanel
from .provenance import Source
from .realism import LABELS, REQUIREMENTS, assess, present_trading_return
from .timing import CONVENTIONS, DEFAULT_LAG, ExecutionTiming

RESEARCH_ONLY = True
CALIBRATED = False

__all__ = ["CALIBRATED", "CONVENTIONS", "DEFAULT_LAG", "LABELS", "REQUIREMENTS", "RESEARCH_ONLY", "CostModel",
           "CostValue", "ExecutionPolicy", "ExecutionResult", "ExecutionTiming", "Instrument", "RootCosts",
           "SettlementPanel", "Shocks", "Source", "assess", "execute", "hte_equivalent_coefficients",
           "one_way_cost_fraction", "present_trading_return", "size"]
