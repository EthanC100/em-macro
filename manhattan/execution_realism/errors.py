"""Errors of the execution-realism adapter. Every refusal is an exception: nothing fails silently."""
from __future__ import annotations


class ExecutionRealismError(Exception):
    """Base class."""


class UnitError(ExecutionRealismError, ValueError):
    """A quantity, currency, tick or shape that does not make sense."""


class MissingInputError(ExecutionRealismError):
    """A price, FX rate, liquidity estimate or cost term needed by the run is absent."""


class LiquidityError(ExecutionRealismError):
    """An order exceeds the participation cap under ``on_liquidity_shortfall = "raise"``."""


class RollError(ExecutionRealismError):
    """A roll that the panel adapter cannot complete. It fails closed; PR #85 is the reference for partial rolls."""


class LookAheadError(ExecutionRealismError):
    """An input that was not known at the decision would be used."""


class ProvenanceError(ExecutionRealismError):
    """A cost label this package refuses (for example "calibrated"), or a known-cost label without its source."""


class OptimisticExecutionError(ExecutionRealismError):
    """A same-close or otherwise under-specified result asked to be presented as a trading-return estimate."""
