"""Synthetic futures execution, cost and roll model: research infrastructure only.

Design and limitations: docs/manhattan/EXECUTION_MODEL.md.

    manhattan.execution.contracts   contract ids, metadata (tick, multiplier, currency), tick rounding, roll rule
    manhattan.execution.market      caller-supplied calendar, settlements, liquidity and FX, stamped with known-at times
    manhattan.execution.costs       cost scenarios (synthetic or caller-supplied, never calibrated) and one fill
    manhattan.execution.account     daily gross/net accounting, rolls, turnover, exposure, scenario sensitivity
    manhattan.execution.adjust      continuous series for comparison; never tradable

**What this is not.** It places no order, connects to no broker or exchange, reads no file, no environment variable
and no network, and holds no market data or calibrated cost. It is not imported by the engine
(``manhattan.engine``), the operational runner (``manhattan.ops``), the Ledger or the night shift, and it writes
no ledger record: nothing it computes is evidence, a claim, an attempt, a screening result or a trade.
"""
from .account import Decision, ExecutionPolicy, Result, run, run_scenarios, sensitivity_table
from .contracts import ContractSpec, RollPolicy, adverse_round, contract_id, round_to_tick
from .costs import CostScenario, CostTerms, Fill, fill_order, one_way_cost_fraction
from .market import FxRate, Liquidity, MarketData, Settlement, TradingDay

RESEARCH_ONLY = True
CALIBRATED = False

__all__ = ["CALIBRATED", "RESEARCH_ONLY", "ContractSpec", "CostScenario", "CostTerms", "Decision", "ExecutionPolicy",
           "Fill", "FxRate", "Liquidity", "MarketData", "Result", "RollPolicy", "Settlement", "TradingDay",
           "adverse_round", "contract_id", "fill_order", "one_way_cost_fraction", "round_to_tick", "run",
           "run_scenarios", "sensitivity_table"]
