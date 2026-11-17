"""Metadata-only readiness checks: no downloads, market data or performance."""
import copy
import json
from pathlib import Path

import pytest

from manhattan.ops.readiness import validate

INVENTORY = Path(__file__).resolve().parents[1] / "docs/manhattan/ops/genesis_data_readiness.json"


def inventory():
    return json.loads(INVENTORY.read_text())


def test_all_ten_families_remain_unverified_without_original_specifications():
    result = validate(inventory())
    assert result["families"] == 10 and result["datasets"]["unverified"] == 20
    assert result["research_execution_authorized"] is False


@pytest.mark.parametrize("field,value", [("status", "verified_available"), ("coverage_start", "2020-01-01"),
                                        ("availability", "advertised"), ("release_timestamps", "")])
def test_insufficient_or_invalid_evidence_is_refused(field, value):
    doc = inventory()
    doc["families"][0]["requirements"][0][field] = value
    with pytest.raises(ValueError):
        validate(doc)


def test_evidence_metadata_can_be_verified_but_does_not_authorize_execution():
    doc = inventory()
    req = doc["families"][0]["requirements"][0]
    for key in ("release_timestamps", "vintages", "instrument_ids", "contract_mapping", "publication_delay",
                "licensing", "missing_data", "project_support"):
        req[key] = "Synthetic test evidence only"
    req.update(status="verified_available", coverage_start="2000-01-01", coverage_end="2000-12-31",
               claude_decisions=[], evidence=[{"reference": "synthetic-fixture", "sha256": "a" * 64,
                                               "verified_on": "2026-11-16"}])
    result = validate(doc)
    assert result["datasets"]["verified_available"] == 1
    assert result["research_execution_authorized"] is False
    req["coverage_end"] = "1999-01-01"
    with pytest.raises(ValueError):
        validate(doc)


def test_duplicates_missing_families_and_unknown_fields_are_rejected():
    for mutate in (lambda d: d["families"].pop(),
                   lambda d: d["families"].__setitem__(1, copy.deepcopy(d["families"][0])),
                   lambda d: d["families"][0].update(approved=True)):
        doc = inventory()
        mutate(doc)
        with pytest.raises(ValueError):
            validate(doc)


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_schema_version_has_an_exact_integer_type(version):
    doc = inventory()
    doc["schema_version"] = version
    with pytest.raises(ValueError):
        validate(doc)
