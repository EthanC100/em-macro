"""Errors of the technology-equities research package. Every one of them means "fail closed": the caller gets no
value rather than a value that might carry information from the future, a wrong identity or an unpriced risk."""
from __future__ import annotations


class EquityDataError(ValueError):
    """Base class: data that cannot be used point in time."""


class TemporalError(EquityDataError):
    """A timestamp that is missing, naive, contradictory or later than the information boundary allows."""


class IdentityError(EquityDataError):
    """A security or company identity that is unknown, ambiguous or duplicated."""


class ContractError(EquityDataError):
    """A data source whose provenance, timing, revision behaviour or permitted role is missing or contradictory."""


class CorporateActionError(EquityDataError):
    """A price history whose corporate actions, currency or delisting outcome are incomplete or inconsistent."""


class CurrencyError(CorporateActionError):
    """Values in different currencies combined without an explicit conversion."""


class BorrowError(EquityDataError):
    """A short position without known borrow availability, or a cost model that omits the borrow fee."""


class NeutralizationError(EquityDataError):
    """A signal that is claimed to be neutral to an exposure and is not, or cannot be neutralised."""


class EvidenceError(PermissionError):
    """An attempt to treat a research candidate, a synthetic test or a historical fit as validated evidence."""
