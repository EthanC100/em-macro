"""Errors of the synthetic execution model. Every one is a ``ValueError``: the model refuses, it never guesses."""
from __future__ import annotations


class ExecutionModelError(ValueError):
    """Base class: an input the model cannot account for honestly."""


class UnitError(ExecutionModelError):
    """A unit that is missing, ambiguous or inconsistent (currency codes, tick value against multiplier, whole
    contracts)."""


class TimestampError(ExecutionModelError):
    """A time that is naive, out of order, or inconsistent with when the market could have published it."""


class LookAheadError(ExecutionModelError):
    """An input that was not yet known at the moment it is used (a decision, a liquidity figure, a price)."""


class MissingInputError(ExecutionModelError):
    """A required input is absent: contract metadata, a settlement, an FX rate, liquidity, a cost term or margin."""


class InvalidContractError(ExecutionModelError):
    """A contract that cannot be traded or held on that day (not listed yet, expired, no eligible contract)."""


class LiquidityError(ExecutionModelError):
    """An order larger than the liquidity cap allows, under the ``raise`` shortfall policy."""
