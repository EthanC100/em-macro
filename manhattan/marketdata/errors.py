"""Exceptions of the market-data layer. Every refusal is a subclass of ``MarketDataError``."""
from __future__ import annotations


class MarketDataError(ValueError):
    """Data that cannot be represented, ingested or read point in time."""


class SchemaError(MarketDataError):
    """A record that does not fit the canonical schema."""


class ProvenanceError(MarketDataError):
    """Provenance that is missing, conflicting or would have to be invented."""


class ValidationFailed(MarketDataError):
    """Validation found at least one error; ``report`` holds every issue."""

    def __init__(self, report):
        self.report = report
        errors = [i for i in report.issues if i.severity == "error"]
        head = "; ".join(f"{i.code}: {i.detail}" for i in errors[:5])
        super().__init__(f"{len(errors)} validation error(s): {head}")


class FenceRefused(PermissionError):
    """Ingesting or reading observations in a reserve, forward or embargoed role without authorisation."""


class NotAuthorized(PermissionError):
    """A fetch from a licensed or paid provider without the owner's recorded authorisation."""


class LicenceError(PermissionError):
    """Licensed data (or rows derived from it) would be written inside the public repository."""


class ImmutableError(MarketDataError):
    """An attempt to change a dataset or registry record that already exists."""
