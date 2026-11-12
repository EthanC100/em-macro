"""Manhattan spec registry: canonical form, hashes and content-addressed IDs (ARCHITECTURE.md section 3).

Four levels, each a mapping. A child contains its parent's **full hash**, so a link cannot be changed without
changing the child's ID:

    family      AF-<16 hex>   one mechanism, one predicted sign, one named counterparty
    hypothesis  AH-<16 hex>   the family in one domain; contains the family hash and the variant grid
    variant     AV-<16 hex>   {hypothesis hash, grid point}; the grid's points, enumerated at freeze
    executable  AX-<16 hex>   {variant hash, universe, cost model, sizing, code version}

**Canonical form.** JSON with keys sorted, UTF-8 with strings in NFC, no insignificant white space, integers as
integers, every other number as a decimal string, dates as ``YYYY-MM-DD``; list order is kept unless the key is
marked as a set (``SET_KEYS``), in which case the items are sorted. The spec hash is the SHA-256 of those bytes;
a spec is stored as exactly those bytes, so ``lab.book.sha256`` of the file gives the same hash.

Specs are data. Nothing in a spec is ever executed or followed as an instruction (CLAUDE.md hard rule 12).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

PREFIX = {"family": "AF", "hypothesis": "AH", "variant": "AV", "executable": "AX"}
ID_HEX = 16
SET_KEYS = frozenset({"universe", "data_sources", "tags"})
MAX_GRID = 200                      # points per hypothesis; a larger grid is refused (it must be bounded)
MECHANISM_CLASSES = ("risk_premium", "flow", "behavioural", "structural", "informational", "other")
SIGNS = ("+", "-")
CHANNELS = ("blind", "adaptive")
FAMILY_REQUIRED = ("mechanism", "mechanism_class", "sign", "counterparty", "kill_condition", "tail_exposure")
HYPOTHESIS_REQUIRED = ("family", "domain", "data_sources", "signal", "primary_binding", "grid")
BINDING_REQUIRED = ("universe_id", "cost_model_id", "sizing_id")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class SpecError(ValueError):
    """A spec that cannot be put in canonical form or does not meet its schema."""


def _canon(x, key: str | None = None):
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        if not math.isfinite(x):
            raise SpecError("a spec cannot hold NaN or infinity")
        return _canon(Decimal(repr(x)))
    if isinstance(x, Decimal):
        if not x.is_finite():
            raise SpecError("a spec cannot hold NaN or infinity")
        if x == x.to_integral_value():
            return int(x)
        return format(x.normalize(), "f")
    if isinstance(x, datetime):
        raise SpecError("a spec holds dates (YYYY-MM-DD), not times")
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, str):
        return unicodedata.normalize("NFC", x)
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if not isinstance(k, str):
                raise SpecError("spec keys are strings")
            out[unicodedata.normalize("NFC", k)] = _canon(v, k)
        return out
    if isinstance(x, (list, tuple)):
        items = [_canon(v) for v in x]
        if key in SET_KEYS:
            items = sorted(items, key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return items
    raise SpecError(f"a spec cannot hold a value of type {type(x).__name__}")


def canonical_bytes(spec: dict) -> bytes:
    if not isinstance(spec, dict):
        raise SpecError("a spec is a mapping")
    return json.dumps(_canon(spec), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(canonical_bytes(spec)).hexdigest()


def spec_id(spec: dict) -> str:
    """``<prefix>-<first 16 hex of the spec hash>``; the level is read from the spec."""
    level = spec.get("level")
    if level not in PREFIX:
        raise SpecError(f"level must be one of {tuple(PREFIX)}")
    return f"{PREFIX[level]}-{spec_hash(spec)[:ID_HEX]}"


def _need(spec: dict, fields, where: str) -> list[str]:
    errs = []
    for f in fields:
        v = spec.get(f)
        if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0) or (isinstance(v, str) and not v.strip()):
            errs.append(f"{where}: '{f}' is required")
    return errs


def validate_family(spec: dict) -> list[str]:
    errs = [] if spec.get("level") == "family" else ["family: level must be 'family'"]
    errs += _need(spec, FAMILY_REQUIRED, "family")
    if spec.get("mechanism_class") not in (None, *MECHANISM_CLASSES):
        errs.append(f"family: mechanism_class must be one of {MECHANISM_CLASSES}")
    if spec.get("sign") not in (None, *SIGNS):
        errs.append("family: sign must be '+' or '-' (one predicted sign)")
    if "parent_family" in spec and not _HASH.match(str(spec["parent_family"])):
        errs.append("family: parent_family must be the parent's full SHA-256")
    return errs


def enumerate_grid(grid) -> list[dict]:
    """The grid's points in a fixed order: parameters by name, values in the order declared.

    ``grid`` maps each parameter to the finite list of its values. Anything else is refused: a grid must be
    declared, finite and at most ``MAX_GRID`` points."""
    if not isinstance(grid, dict) or not grid:
        raise SpecError("grid must map each parameter to the list of its values (the grid must be declared)")
    names = sorted(grid)
    for n in names:
        vals = grid[n]
        if not isinstance(vals, (list, tuple)) or len(vals) == 0:
            raise SpecError(f"grid parameter '{n}' needs a finite, non-empty list of values")
        canon = [json.dumps(_canon(v), sort_keys=True) for v in vals]
        if len(set(canon)) != len(canon):
            raise SpecError(f"grid parameter '{n}' repeats a value")
    size = math.prod(len(grid[n]) for n in names)
    if size > MAX_GRID:
        raise SpecError(f"the grid has {size} points; at most {MAX_GRID} are allowed")
    return [dict(zip(names, combo)) for combo in itertools.product(*(grid[n] for n in names))]


def validate_hypothesis(spec: dict) -> list[str]:
    errs = [] if spec.get("level") == "hypothesis" else ["hypothesis: level must be 'hypothesis'"]
    errs += _need(spec, HYPOTHESIS_REQUIRED, "hypothesis")
    if spec.get("family") is not None and not _HASH.match(str(spec["family"])):
        errs.append("hypothesis: 'family' must be the family's full SHA-256")
    for i, src in enumerate(spec.get("data_sources") or []):
        if not isinstance(src, dict) or not src.get("name") or "publication_lag_days" not in src:
            errs.append(f"hypothesis: data_sources[{i}] needs a name and publication_lag_days")
        elif isinstance(src["publication_lag_days"], bool) or not isinstance(src["publication_lag_days"], int) \
                or src["publication_lag_days"] < 0:
            errs.append(f"hypothesis: data_sources[{i}].publication_lag_days must be a whole number of days, 0 or more")
    b = spec.get("primary_binding")
    if isinstance(b, dict):
        errs += _need(b, BINDING_REQUIRED, "hypothesis.primary_binding")
    elif b is not None:
        errs.append("hypothesis: primary_binding must be a mapping")
    if spec.get("grid") is not None:
        try:
            enumerate_grid(spec["grid"])
        except SpecError as e:
            errs.append(f"hypothesis: {e}")
    return errs


def family(**fields) -> dict:
    spec = {"level": "family", **fields}
    errs = validate_family(spec)
    if errs:
        raise SpecError("; ".join(errs))
    return spec


def hypothesis(family_spec: dict, **fields) -> dict:
    """A hypothesis of ``family_spec``: it carries the family's full hash."""
    spec = {"level": "hypothesis", "family": spec_hash(family_spec), **fields}
    errs = validate_hypothesis(spec)
    if errs:
        raise SpecError("; ".join(errs))
    return spec


def variant(hypothesis_spec: dict, point: dict, channel: str = "blind", **extra) -> dict:
    """One point of the hypothesis's grid (``blind``), or a later addition by the adaptive channel.

    A blind variant's hash covers the hypothesis hash and the grid point only; an adaptive variant is a new
    record marked ``channel: adaptive`` (it carries no evidential weight on any window visible when written)."""
    if channel not in CHANNELS:
        raise SpecError(f"channel must be one of {CHANNELS}")
    spec = {"level": "variant", "hypothesis": spec_hash(hypothesis_spec), "point": point}
    if channel == "blind":
        if _canon(point) not in [_canon(p) for p in enumerate_grid(hypothesis_spec["grid"])]:
            raise SpecError("a blind variant must be a point of the hypothesis's frozen grid")
        if extra:
            raise SpecError("a blind variant holds nothing but its hypothesis and its grid point")
    else:
        spec.update(channel="adaptive", **extra)
    return spec


def variants(hypothesis_spec: dict) -> list[dict]:
    """Every blind variant of a hypothesis, in the grid's fixed order."""
    return [variant(hypothesis_spec, p) for p in enumerate_grid(hypothesis_spec["grid"])]


def executable(variant_spec: dict, *, universe_id: str, cost_model_id: str, sizing_id: str, code_version: str) -> dict:
    spec = {"level": "executable", "variant": spec_hash(variant_spec), "universe_id": universe_id,
            "cost_model_id": cost_model_id, "sizing_id": sizing_id, "code_version": code_version}
    errs = _need(spec, ("universe_id", "cost_model_id", "sizing_id", "code_version"), "executable")
    if errs:
        raise SpecError("; ".join(errs))
    return spec


def primary_executable(hypothesis_spec: dict, variant_spec: dict, code_version: str) -> dict:
    """The executable the hypothesis declared at freeze for each of its variants."""
    b = hypothesis_spec["primary_binding"]
    return executable(variant_spec, universe_id=b["universe_id"], cost_model_id=b["cost_model_id"],
                      sizing_id=b["sizing_id"], code_version=code_version)


def write(spec: dict, directory: Path) -> Path:
    """Store a spec as its canonical bytes, named by its ID. Refuses to overwrite a different spec."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{spec_id(spec)}.json"
    data = canonical_bytes(spec)
    if path.exists() and path.read_bytes() != data:
        raise SpecError(f"{path.name} exists with different content: two specs share an ID (check the full hash)")
    path.write_bytes(data)
    return path


def read(path: Path) -> dict:
    """Load a stored spec and check that the file still is the spec its name says it is."""
    raw = path.read_bytes()
    spec = json.loads(raw.decode("utf-8"))
    if canonical_bytes(spec) != raw:
        raise SpecError(f"{path.name} is not in canonical form (it was edited)")
    if path.stem != spec_id(spec):
        raise SpecError(f"{path.name} does not match its content: the ID of what it holds is {spec_id(spec)}")
    return spec


class Registry:
    """IDs seen so far, with the full hash behind each. Two different specs with one ID are an error."""

    def __init__(self):
        self._by_id: dict[str, str] = {}

    def add(self, spec: dict) -> str:
        sid, full = spec_id(spec), spec_hash(spec)
        seen = self._by_id.get(sid)
        if seen is not None and seen != full:
            raise SpecError(f"ID collision on {sid}: full hashes {seen} and {full} differ")
        self._by_id[sid] = full
        return sid

    def full_hash(self, sid: str) -> str:
        return self._by_id[sid]

    def __contains__(self, sid: str) -> bool:
        return sid in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)
