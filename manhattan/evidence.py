"""Evidence classification: where data came from, and what (if anything) they may count as. Pure and fail-closed.

Six separate axes, each decided on its own and never inferred from another:

    provenance      synthetic | historical_public | historical_licensed | captured_forward | unverified
    reconstruction  the explicit reasons a value was not genuinely seen as it happened (backfilled, late,
                    conservative availability assumption); empty only for a genuine first-seen capture
    availability    how the day each value became usable is known (the publication contract of
                    ``manhattan.availability``): per-vintage release dates, a declared daily lag, first-seen
                    capture, a conservative assumption, or generated (synthetic)
    role            exploration | reserve | forward | embargo, **computed** from the fence and the spec's freeze
                    (``manhattan.roles.role_of`` for every day of the span), never taken from a label
    authorization   what lets the observations be read in that role: open exploration, a verified designated
                    reserve token, a verified batch freeze; otherwise unauthorised
    eligibility     none | infrastructure_validation | descriptive | reserve_screening_candidate | forward_candidate

A *candidate* is only "not disqualified by provenance". It is never a grant: ``forward_elond_eligible`` and
``screening_eligible`` are False in every result this module can produce, because the gates they depend on
(Protocol v3.1 sections 6.8 and 8, an adopted protocol, ``claims.enabled``, enrolment, and a binding of each
observation to a registered attempt) are not implemented or not satisfied. ``promotion_authorized`` is False
always: classification authorises nothing (``manhattan.ops.promotion`` is the only door, and it is shut).

``weight_ceiling`` is the most the existing table (``manhattan.ledger.evidential_weight``, ARCHITECTURE 6.3)
could give such evidence; ``cap_weight`` only ever lowers a recorded weight to it, never raises one.

**Authentication.** The module reads a closed metadata schema and the results of the repository's existing
verifiers (``VERIFIERS``), each bound to the SHA-256 of the canonical metadata (``subject_digest``). It checks that
every verifier the claimed provenance needs is present and bound to exactly this metadata, and that the metadata
are internally consistent. It cannot itself authenticate anything: a verification is only as good as the code
that minted it, and minting them is the integration's job (docs/manhattan/ops/EVIDENCE_CLASSIFICATION.md).
Filenames, timestamps alone, recent dates and labels never decide a class. Anything unknown, missing or
contradictory gives ``provenance = unverified`` and ``eligibility = none``, with the problems listed.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Mapping

import numpy as np

from manhattan import roles
from manhattan.availability import AvailabilityError, validate_source
from manhattan.ledger import evidential_weight
from manhattan.ops import promotion

SCHEMA = "manhattan.evidence/1"

SYNTHETIC, HISTORICAL_PUBLIC, HISTORICAL_LICENSED = "synthetic", "historical_public", "historical_licensed"
CAPTURED_FORWARD, UNVERIFIED = "captured_forward", "unverified"
PROVENANCES = (SYNTHETIC, HISTORICAL_PUBLIC, HISTORICAL_LICENSED, CAPTURED_FORWARD, UNVERIFIED)

BACKFILLED, LATE, CONSERVATIVE, UNKNOWN = "backfilled", "late", "conservative_assumption", "unknown"

AVAIL_PER_VINTAGE, AVAIL_DECLARED_LAG = "per_vintage_release", "declared_daily_lag"
AVAIL_FIRST_SEEN, AVAIL_CONSERVATIVE = "first_seen_capture", "conservative_assumption"
AVAIL_GENERATED, AVAIL_UNKNOWN = "generated", "unknown"

AUTH_OPEN, AUTH_RESERVE, AUTH_FREEZE = "exploration_open", "reserve_designated_verified", "forward_freeze_verified"
AUTH_NONE = "unauthorized"

E_NONE, E_INFRA, E_DESCRIPTIVE = "none", "infrastructure_validation", "descriptive"
E_RESERVE, E_FORWARD = "reserve_screening_candidate", "forward_candidate"

# The existing verifiers a verification must come from (the integration mints them; see the contract document).
VERIFIERS = {
    "synthetic_generator": "the generator definition and seed that produced the values (e.g. ops.data synthetic)",
    "publication_contract": "manhattan.availability.validate_source on the recorded source definition",
    "public_archive": "SHA-256 of the archived public snapshot the values were read from",
    "licensed_snapshot": "SHA-256 manifest of the private licensed snapshot (iMac only; never in this repository)",
    "capture_replay": "manhattan.ops.data.first_seen replay: raw hashes, byte counts, schema-v2 source definition",
    "store_anchor": "manhattan.ops.store.verify_chain against an independently retained head anchor",
    "batch_freeze": "manhattan.freeze.verify_frozen: signed tag, manifest hash, external timestamp",
    "runner_token": "a verified manhattan.roles.RunnerToken naming this (domain, window) as unused and designated",
}
REQUIRED = {
    SYNTHETIC: {"synthetic_generator"},
    HISTORICAL_PUBLIC: {"publication_contract", "public_archive"},
    HISTORICAL_LICENSED: {"publication_contract", "licensed_snapshot"},
    CAPTURED_FORWARD: {"publication_contract", "capture_replay", "store_anchor"},
}

# Gates that forward e-LOND eligibility needs and that no code implements yet. Each stays a blocker until the
# protected protocol is adopted and the gate exists in code; this module can never clear them.
UNIMPLEMENTED_GATES = (
    "enrolment gate (Protocol v3.1 section 6.8: enrolled at the first review as Promising or higher) not implemented",
    "attempt binding (each observation tied to a registered, anchored attempt; Session 1 interface) not integrated",
    "guard and test-period construction (Protocol v3.1 sections 6.1-6.7) not wired to classified evidence",
)

_SHA = re.compile(r"[0-9a-f]{64}")
_TOP = {"schema", "source", "domain", "span", "vintage", "capture", "spec", "designated", "claimed_role",
        "claimed_provenance"}
_SOURCE = {"id", "kind", "publication_contract"}
_VINTAGE = {"kind", "id", "as_of"}
_CAPTURE = {"capture_id", "schema_version", "monitoring_start", "first_retrieved_utc", "reconstructed"}
_RECON = {"backfill", "late"}
_SPEC = {"spec_hash", "channel", "freeze"}
_MAX_SPAN_DAYS = roles.MAX_READ_DAYS


@dataclass(frozen=True)
class Classification:
    provenance: str
    licensed: bool
    reconstruction: frozenset
    availability: str
    role: str | None
    authorization: str
    eligibility: str
    weight_ceiling: int
    forward_elond_eligible: bool
    screening_eligible: bool
    promotion_authorized: bool
    blockers: tuple
    problems: tuple
    subject: str | None

    @property
    def genuine_capture(self) -> bool:
        """Captured forward and seen as it happened: no backfill, no late marks, no assumed availability."""
        return self.provenance == CAPTURED_FORWARD and not self.reconstruction and self.availability == AVAIL_FIRST_SEEN


class _Reject(Exception):
    pass


def canonical(metadata: Mapping) -> bytes:
    try:
        return json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _Reject(f"metadata is not canonical JSON: {exc}") from None


def subject_digest(metadata: Mapping) -> str:
    """The SHA-256 every verification must be bound to."""
    return hashlib.sha256(canonical(metadata)).hexdigest()


def _unverified(problems, subject=None, role=None) -> Classification:
    return Classification(UNVERIFIED, False, frozenset({UNKNOWN}), AVAIL_UNKNOWN, role, AUTH_NONE, E_NONE, 0,
                          False, False, False, ("provenance unverified",), tuple(problems), subject)


def _fail(msg):
    raise _Reject(msg)


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _date(v, what) -> date:
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        _fail(f"{what} must be an ISO date string")
    try:
        return date.fromisoformat(v)
    except ValueError:
        _fail(f"{what} is not a valid date")


def _keys(obj, allowed, required, what):
    if not isinstance(obj, Mapping):
        _fail(f"{what} must be an object")
    unknown = set(obj) - allowed
    if unknown:
        _fail(f"{what} has unknown fields {sorted(unknown)} (closed schema)")
    missing = required - set(obj)
    if missing:
        _fail(f"{what} is missing {sorted(missing)}")


def _computed_role(domain, start, end, fence, freeze, holding=0) -> str:
    days = np.arange(np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"))
    found = {roles.role_of(d.astype(object), domain, fence, freeze, holding) for d in days}
    if len(found) != 1:
        _fail(f"the span covers several roles {sorted(found)}: one span, one role")
    return found.pop()


def classify(metadata: Mapping, verifications: Mapping[str, str] | None, *, fence: roles.Fence,
             config: Mapping | None = None, protocol_hash: str | None = None) -> Classification:
    """Classify one homogeneous body of evidence. Never raises on bad input: it fails closed instead."""
    try:
        subject = subject_digest(metadata) if isinstance(metadata, Mapping) else None
    except _Reject as exc:
        return _unverified([str(exc)])
    try:
        return _classify(metadata, verifications, fence, config or {}, protocol_hash, subject)
    except _Reject as exc:
        return _unverified([str(exc)], subject)


def _classify(md, verifications, fence, config, protocol_hash, subject) -> Classification:
    _keys(md, _TOP, {"schema", "source", "domain", "span", "vintage", "designated"}, "metadata")
    if md["schema"] != SCHEMA:
        _fail(f"unknown metadata schema {md['schema']!r}")
    if not _text(md["domain"]):
        _fail("domain is required")
    if type(md["designated"]) is not bool:
        _fail("designated must be a boolean")

    # source and publication contract
    src = md["source"]
    _keys(src, _SOURCE, _SOURCE, "source")
    if not _text(src["id"]) or src["kind"] not in ("synthetic", "public", "licensed"):
        _fail("source needs an id and a kind of synthetic, public or licensed")
    contract = src["publication_contract"]
    try:
        validate_source(contract)
    except AvailabilityError as exc:
        _fail(f"invalid publication contract: {exc}")
    if contract["name"] != src["id"]:
        _fail("publication contract names a different source")
    akind = contract["availability"]["kind"]

    # span and vintage
    span = md["span"]
    _keys(span, {"start", "end"}, {"start", "end"}, "span")
    start, end = _date(span["start"], "span.start"), _date(span["end"], "span.end")
    if end < start:
        _fail("span ends before it starts")
    if (end - start).days > _MAX_SPAN_DAYS:
        _fail("span is too long")
    vin = md["vintage"]
    _keys(vin, _VINTAGE, _VINTAGE, "vintage")
    if vin["kind"] not in ("generated", "snapshot", "first_seen_capture"):
        _fail("vintage kind must be generated, snapshot or first_seen_capture")
    if not isinstance(vin["id"], str) or not _SHA.fullmatch(vin["id"]):
        _fail("vintage id must be one SHA-256 (an ambiguous or missing vintage fails closed)")
    as_of = _date(vin["as_of"], "vintage.as_of")
    if as_of < end:
        _fail("vintage as_of precedes the end of the span it holds")

    # spec (who the evidence would be about), and the computed role
    spec = md.get("spec")
    freeze = channel = None
    if spec is not None:
        _keys(spec, _SPEC, _SPEC, "spec")
        if not isinstance(spec["spec_hash"], str) or not _SHA.fullmatch(spec["spec_hash"]):
            _fail("spec_hash must be a SHA-256")
        if spec["channel"] not in ("blind", "adaptive"):
            _fail("spec channel must be blind or adaptive")
        channel, freeze = spec["channel"], _date(spec["freeze"], "spec.freeze")
    role = _computed_role(md["domain"], start, end, fence, freeze)
    if "claimed_role" in md and md["claimed_role"] != role:
        _fail(f"claimed role {md['claimed_role']!r} contradicts the computed role {role!r}")
    if md["designated"] and role != roles.RESERVE:
        _fail("only a reserve evaluation can be designated")

    # provenance from the closed schema: never from dates, names or labels
    kind = src["kind"]
    capture = md.get("capture")
    if kind == "synthetic":
        if vin["kind"] != "generated" or capture is not None:
            _fail("synthetic values must come from a generated vintage with no capture")
        provenance = SYNTHETIC
    elif vin["kind"] == "first_seen_capture" or capture is not None:
        if vin["kind"] != "first_seen_capture" or capture is None:
            _fail("a capture block and a first-seen vintage must come together")
        provenance = CAPTURED_FORWARD
    elif vin["kind"] == "snapshot":
        provenance = HISTORICAL_LICENSED if kind == "licensed" else HISTORICAL_PUBLIC
    else:
        _fail("a market source cannot have a generated vintage")
    if "claimed_provenance" in md and md["claimed_provenance"] != provenance:
        _fail(f"claimed provenance {md['claimed_provenance']!r} contradicts the derived {provenance!r}")

    # verifications: each required one present and bound to exactly this metadata
    if verifications is None or not isinstance(verifications, Mapping):
        _fail("no verifications supplied")
    unknown = set(verifications) - set(VERIFIERS)
    if unknown:
        _fail(f"unknown verifiers {sorted(unknown)}")
    need = set(REQUIRED[provenance])
    if role == roles.FORWARD:
        need.add("batch_freeze")
    if role == roles.RESERVE and md["designated"]:
        need.add("runner_token")
    missing = sorted(v for v in need if verifications.get(v) != subject)
    if missing:
        _fail(f"verifications missing or not bound to this metadata: {missing}")

    # reconstruction and availability, each explicit
    recon: set = set()
    if akind == "conservative":
        recon.add(CONSERVATIVE)
    if provenance == SYNTHETIC:
        availability = AVAIL_GENERATED
    elif provenance == CAPTURED_FORWARD:
        recon |= _capture_reconstruction(capture, vin, start, end, as_of)
        availability = AVAIL_CONSERVATIVE if akind == "conservative" else AVAIL_FIRST_SEEN
    else:
        availability = {"release_dates": AVAIL_PER_VINTAGE, "release_calendar": AVAIL_PER_VINTAGE,
                        "daily_lag": AVAIL_DECLARED_LAG, "conservative": AVAIL_CONSERVATIVE}[akind]

    # authorization (what lets these dates be read in this role)
    reserve_cfg = (config.get("reserve") or {}) if isinstance(config, Mapping) else {}
    if role == roles.EXPLORATION:
        authorization = AUTH_OPEN
    elif role == roles.RESERVE and md["designated"] and reserve_cfg.get("enabled") is True and fence.enabled:
        authorization = AUTH_RESERVE
    elif role == roles.FORWARD:
        authorization = AUTH_FREEZE           # batch_freeze was required above
    else:
        authorization = AUTH_NONE

    # eligibility: provenance can only disqualify
    reconstructed = bool(recon)
    blockers: list[str] = []
    licensed = kind == "licensed"
    if provenance == SYNTHETIC:
        eligibility = E_INFRA
        blockers.append("synthetic evidence validates infrastructure, never market performance")
    elif role in (roles.EMBARGO,) or authorization == AUTH_NONE:
        eligibility = E_NONE
        blockers.append(f"{role} dates without an authorisation carry no evidence")
    elif role == roles.EXPLORATION:
        eligibility = E_DESCRIPTIVE
        blockers.append("exploration data carry no evidential weight (ARCHITECTURE 6.3)")
    elif role == roles.RESERVE:
        if provenance == CAPTURED_FORWARD or reconstructed or availability != AVAIL_PER_VINTAGE \
                or channel != "blind":
            eligibility = E_DESCRIPTIVE
            blockers.append("a reserve screening candidate needs blind-channel, per-vintage historical data "
                            "with no reconstruction")
        else:
            eligibility = E_RESERVE
            blockers.append("a reserve result is screening evidence at most, never independent forward confirmation")
    else:  # forward dates
        if provenance != CAPTURED_FORWARD:
            eligibility = E_DESCRIPTIVE
            blockers.append("post-freeze dates read from a historical snapshot are not captured forward evidence")
        elif reconstructed or availability != AVAIL_FIRST_SEEN:
            eligibility = E_DESCRIPTIVE
            blockers.append(f"reconstructed forward observations carry weight 0: {sorted(recon)}")
        elif start <= freeze:
            _fail("forward span starts on or before the freeze")
        else:
            eligibility = E_FORWARD
            blockers.append("captured-forward provenance is necessary, not sufficient, for forward e-LOND")

    if eligibility in (E_RESERVE, E_FORWARD):
        ceiling = evidential_weight(channel, role, md["designated"], reconstructed)
    else:
        ceiling = 0
    enabled, reason = promotion.status(protocol_hash, config if isinstance(config, Mapping) else None)
    if not enabled:
        blockers.append(f"promotion disabled: {reason}")
    if eligibility == E_FORWARD:
        blockers.extend(UNIMPLEMENTED_GATES)
    if eligibility == E_RESERVE:
        blockers.append("screening is not implemented and is out of scope for classification")
    return Classification(provenance, licensed, frozenset(recon), availability, role, authorization, eligibility,
                          ceiling, False, False, False, tuple(blockers), (), subject)


def _capture_reconstruction(capture, vin, start: date, end: date, as_of: date) -> set:
    _keys(capture, _CAPTURE, _CAPTURE, "capture")
    if not isinstance(capture["capture_id"], str) or not _SHA.fullmatch(capture["capture_id"]):
        _fail("capture identity must be a SHA-256")
    if capture["capture_id"] != vin["id"]:
        _fail("capture identity differs from the vintage it claims to be")
    if type(capture["schema_version"]) is not int or capture["schema_version"] != 2:
        _fail("capture source definition must be schema version 2")
    monitoring = _date(capture["monitoring_start"], "capture.monitoring_start")
    raw = capture["first_retrieved_utc"]
    try:
        retrieved = datetime.fromisoformat(raw) if isinstance(raw, str) else None
    except ValueError:
        retrieved = None
    if retrieved is None or retrieved.tzinfo is None or retrieved.utcoffset() is None:
        _fail("first retrieval time must be an ISO timestamp with a time zone")
    if abs((retrieved.astimezone(timezone.utc).date() - monitoring).days) > 1:
        _fail("monitoring start is inconsistent with the first retrieval time")
    if monitoring > as_of:
        _fail("monitoring starts after the vintage it produced")
    counts = capture["reconstructed"]
    _keys(counts, _RECON, _RECON, "capture.reconstructed")
    if any(type(counts[k]) is not int or counts[k] < 0 for k in _RECON):
        _fail("reconstructed counts must be whole numbers, 0 or more")
    recon = set()
    if counts["backfill"]:
        recon.add(BACKFILLED)
    if counts["late"]:
        recon.add(LATE)
    if start < monitoring and not counts["backfill"]:
        _fail("span starts before monitoring began but reports no backfill (reconstructed data posing as captured)")
    if start < monitoring:
        recon.add(BACKFILLED)
    return recon


def cap_weight(c: Classification, recorded_weight: int) -> int:
    """A recorded evidential weight, lowered to the classification's ceiling. Never raises a weight."""
    if type(recorded_weight) is not int or recorded_weight not in (0, 1):
        return 0
    return min(recorded_weight, c.weight_ceiling)


_RANK = {E_NONE: 0, E_INFRA: 1, E_DESCRIPTIVE: 2, E_RESERVE: 3, E_FORWARD: 3}


def combine(parts) -> Classification:
    """One result for evidence assembled from several classified parts. Any mixture of provenance, role,
    licence or a failed part fails closed: mixed evidence never inherits the class of its best part."""
    parts = tuple(parts)
    if not parts or not all(isinstance(p, Classification) for p in parts):
        return _unverified(["nothing (or something unclassified) to combine"])
    if any(p.provenance == UNVERIFIED for p in parts):
        return _unverified(["a part is unverified"] + [q for p in parts for q in p.problems])
    keys = {(p.provenance, p.role, p.licensed, p.availability, p.authorization) for p in parts}
    if len(keys) > 1:
        return _unverified([f"mixed provenance or role: {sorted(map(str, keys))}"])
    first = parts[0]
    worst = min(parts, key=lambda p: (_RANK[p.eligibility], p.weight_ceiling))
    recon = frozenset().union(*(p.reconstruction for p in parts))
    return Classification(first.provenance, first.licensed, recon, first.availability, first.role,
                          first.authorization, worst.eligibility, min(p.weight_ceiling for p in parts),
                          False, False, False, tuple(dict.fromkeys(b for p in parts for b in p.blockers)), (), None)
