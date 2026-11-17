"""Engineering evidence inventory; never downloads data or evaluates a signal.

Evidence is metadata only. A provider advertisement is not evidence of a usable
point-in-time extract. A validated inventory is not a research approval.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from .inputs import read_json

STATUSES = {"verified_available", "likely_available", "unavailable", "unverified"}
FIELDS = {"id", "dataset", "provider", "availability", "status", "release_timestamps",
          "vintages", "coverage_start", "coverage_end", "instrument_ids", "contract_mapping",
          "publication_delay", "licensing", "missing_data", "project_support", "evidence", "claude_decisions"}
TEXT_FIELDS = FIELDS - {"status", "evidence", "claude_decisions", "coverage_start", "coverage_end"}
UNRESOLVED = {"", "unverified", "unknown", "pending"}


def validate(document: dict) -> dict:
    if not isinstance(document, dict) or set(document) != {"schema_version", "families"} \
            or type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("unsupported inventory schema")
    families = document["families"]
    if not isinstance(families, list) or len(families) != 10:
        raise ValueError("exactly ten family inventories required")
    seen = set()
    counts = {s: 0 for s in sorted(STATUSES)}
    for family in families:
        if set(family) != {"id", "specification", "requirements"}:
            raise ValueError("invalid family fields")
        fid = family["id"]
        if fid not in {f"F{i:02d}" for i in range(1, 11)} or fid in seen:
            raise ValueError("invalid or duplicate family")
        seen.add(fid)
        if family["specification"] not in ("missing", "delivered_needs_claude_review"):
            raise ValueError("inventory cannot approve specifications")
        requirements = family["requirements"]
        if not isinstance(requirements, list) or not 1 <= len(requirements) <= 50:
            raise ValueError("invalid requirements")
        ids = set()
        for req in requirements:
            if set(req) != FIELDS or req["status"] not in STATUSES:
                raise ValueError("invalid dataset requirement")
            if any(not isinstance(req[k], str) or not req[k].strip() for k in TEXT_FIELDS):
                raise ValueError("required metadata missing")
            if req["id"] in ids or not re.fullmatch(r"[a-z0-9_]+", req["id"]):
                raise ValueError("duplicate or invalid dataset id")
            ids.add(req["id"])
            if req["availability"] not in ("public", "licensed", "mixed", "unverified"):
                raise ValueError("invalid availability classification")
            if not isinstance(req["claude_decisions"], list) or not all(
                    isinstance(x, str) and x.strip() for x in req["claude_decisions"]):
                raise ValueError("invalid Claude decisions")
            if not isinstance(req["evidence"], list):
                raise ValueError("invalid evidence")
            for item in req["evidence"]:
                if set(item) != {"reference", "sha256", "verified_on"} \
                        or not isinstance(item["reference"], str) or not item["reference"].strip() \
                        or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
                    raise ValueError("invalid evidence reference")
                date.fromisoformat(item["verified_on"])
            start, end = req["coverage_start"], req["coverage_end"]
            if (start is None) != (end is None):
                raise ValueError("coverage requires both endpoints")
            if start is not None and date.fromisoformat(start) > date.fromisoformat(end):
                raise ValueError("reversed coverage")
            if req["status"] == "verified_available":
                if not req["evidence"] or start is None or req["claude_decisions"] \
                        or req["availability"] == "unverified" \
                        or any(req[k].strip().lower() in UNRESOLVED for k in TEXT_FIELDS - {"id"}):
                    raise ValueError("verified availability requires complete evidence metadata")
            counts[req["status"]] += 1
    return {"schema_version": 1, "families": len(seen), "datasets": counts,
            "research_execution_authorized": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate(read_json(args.inventory, max_bytes=1_000_000))
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        print('{"status":"invalid_inventory"}')
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
