"""The adapter interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..errors import NotAuthorized
from ..provenance import SourceDescriptor


@dataclass
class ParseResult:
    observations: list
    contracts: dict = field(default_factory=dict)       # contract_id -> Contract, when the delivery carries them
    adjustments: list = field(default_factory=list)
    notes: list = field(default_factory=list)            # facts about the delivery (no values), kept in the manifest


class Adapter:
    name: str = "adapter"
    version: str = "0"
    source: SourceDescriptor

    def parse(self, files: dict, request: dict, retrieved_utc: datetime, gate) -> ParseResult:  # pragma: no cover
        raise NotImplementedError

    def fetch(self, request: dict, **_) -> dict:
        raise NotAuthorized(f"{self.name} does not fetch. Raw files are delivered to it; see "
                            "docs/manhattan/marketdata/DESIGN.md section 9 for the authorised path.")
