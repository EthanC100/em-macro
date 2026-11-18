"""Integration contracts with Manhattan components that are being built elsewhere, stated as protocols.

Four concurrent workstreams may change interfaces this programme will later need: binding attempt accounting
(session 1), evidence classification (session 2), simulation reporting and held-out readiness (session 3) and
futures execution modelling (session 4). This module does **not** import or assume their unfinished code. It states,
as ``typing.Protocol`` classes, the smallest interface the equities layer will call, so that an adapter can be
written once each piece lands. ``conforms`` checks an object against a contract at run time.

What the equities layer already uses, unchanged, from main:

    manhattan.spec              canonical form, hashes, family/hypothesis schema (catalogue.family_draft, provenance)
    manhattan.availability      source publication contracts (sources.DataContract.as_availability_source)
    manhattan.engine.pit        PitStore / Reader / Window, the one door to data (pit_bridge, macro)
    manhattan.ops.promotion     the promotion gate (evidence.scope_status)
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class AttemptAccounting(Protocol):
    """Session 1. Every evaluation of an equity executable must start and end as a recorded attempt before any
    reserve or forward data are read. The equities layer will call exactly these two operations."""

    def start(self, *, executable: str, family: str, batch: str, spec_hash: str, data_hash: str,
              window: dict, role: str) -> str: ...

    def finish(self, attempt_id: str, *, result_hash: str, status: str) -> None: ...


@runtime_checkable
class EvidenceClassifier(Protocol):
    """Session 2. Maps a ledger record to an evidence class; the equities layer only reads the class and never
    assigns one. Every output of this package must classify as non-evidence."""

    def classify(self, record: dict) -> str: ...


@runtime_checkable
class SimulationScenarioSource(Protocol):
    """Session 3. A future protocol extension for equities needs simulation scenarios with long/short books,
    borrow costs, delistings and earnings events; this is how the equities layer would hand them over."""

    def register_scenario(self, name: str, generator_spec: dict) -> str: ...


@runtime_checkable
class ExecutionCostModel(Protocol):
    """Session 4 (futures) and ``costs.EquityCostModel`` (equities) can share this shape: a cost per traded
    notional and a holding cost per day, both as fractions."""

    def trade_cost(self, traded_notional: float, adv_notional: float, daily_vol: float) -> float: ...

    def holding_cost_daily(self, weights: dict, day: date) -> float: ...


@runtime_checkable
class PortfolioSink(Protocol):
    """A future portfolio layer: receives target weights for a family's executable; the equities layer never
    trades or sizes real positions."""

    def submit_targets(self, executable: str, day: date, weights: dict) -> None: ...


CONTRACTS = {"attempts": AttemptAccounting, "evidence": EvidenceClassifier, "simulation": SimulationScenarioSource,
             "execution_costs": ExecutionCostModel, "portfolio": PortfolioSink}


def conforms(obj, contract: str) -> bool:
    return isinstance(obj, CONTRACTS[contract])
