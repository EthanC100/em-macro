"""Evidence classification: where data came from, and what (if anything) they may count as. Pure and fail-closed.

Six separate axes, each decided on its own and never inferred from another:

    provenance      synthetic | historical_public | historical_licensed | captured_forward | unverified
    reconstruction  the explicit reasons a value was not genuinely seen as it happened (backfilled, late,
                    conservative availability assumption); empty only for a genuine first-seen capture
    availability    how the day each value became usable is known (the publication contract of
                    ``manhattan.availability``): per-vintage release dates, a declared daily lag, first-seen
                    capture, a conservative assumption, or generated (synthetic)
    role            exploration | reserve | forward | embargo, **computed** with ``manhattan.roles.role_of`` for every
                    day of the span, from the fence, the freeze and the spec's holding period; never a label
    authorization   what lets the observations be read in that role: open exploration, a verified designated
                    reserve token, a verified batch freeze; otherwise unauthorised
    eligibility     none | infrastructure_validation | descriptive | reserve_screening_candidate | forward_candidate

A *candidate* is only "not disqualified". It is never a grant: ``forward_elond_eligible`` and ``screening_eligible``
are False in every result this module can produce, because the gates they depend on (Protocol v3.1 sections 6.8 and
8, an adopted protocol, ``claims.enabled``, enrolment, and a binding of each observation to a registered attempt)
are not implemented or not satisfied. ``promotion_authorized`` is False always.

``weight_ceiling`` is the most the existing table (``manhattan.ledger.evidential_weight``, ARCHITECTURE 6.3)
could give such evidence; ``cap_weight`` only ever lowers a recorded weight to it, never raises one.

**Digests are not authentication.** Two different checks are made and kept apart:

* *integrity*: every ``VerifierResult`` names ``subject_digest(metadata)``, the SHA-256 of the canonical metadata.
  Anyone holding the metadata can compute it; it proves only that the result is about exactly these bytes.
* *authority*: the facts a classification rests on (spec identity, holding period, freeze, batch, observed span,
  window identity and boundaries, capture identity, monitoring start, attempt identity and status, anchor
  assurance) are taken only from ``VerifierResult.facts`` whose ``authority`` is in ``TRUSTED_AUTHORITIES``, and are
  checked against the metadata field by field. Metadata alone never establish a fact.

``TRUSTED_AUTHORITIES`` is **empty**: no integration boundary that could mint verifier results exists yet. Every
classification is therefore ``unverified`` today. Adding an authority is a reviewed code change. Even then this is a
gate, not cryptography: any code in the process can forge an in-process Python object, so authority must be
established at the boundary that builds the results (docs/manhattan/ops/EVIDENCE_CLASSIFICATION.md).

**Issued classifications.** ``cap_weight`` and ``combine`` accept only ``Classification`` objects this module
returned, unchanged (an identity-keyed registry of weak references with a fingerprint taken at issue). A
caller-built, copied, ``replace``-d or mutated object gets weight 0 and cannot be combined. This guards against
accidental or naive forgery only; it is bookkeeping, not a security boundary, and it never changes what
``classify`` returns for given inputs.

Anything unknown, missing, malformed or contradictory gives ``provenance = unverified``, ``eligibility = none`` and
weight 0, with the problems listed. ``classify`` and ``combine`` never raise.
"""
from __future__ import annotations

import hashlib
import json
import re
import weakref
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Mapping

import numpy as np

from manhattan import roles
from manhattan.availability import AvailabilityError, validate_source
from manhattan.ledger import evidential_weight
from manhattan.ops import promotion

SCHEMA = "manhattan.evidence/3"

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

# Authorities whose verifier results are accepted. Empty: nothing can be authenticated yet (see module docstring).
TRUSTED_AUTHORITIES: frozenset[str] = frozenset()

# Anchor assurance levels, as PR #86's reconciler reports them. Only independent anchoring supports a candidate;
# PR #86 never reports it (no independent custody is configured), so no candidate can be reached through it today.
SUPPLIED_ANCHOR, INDEPENDENT_ANCHOR = "checked_against_supplied_anchor", "independently_anchored"
ATTEMPT_STORES = ("ledger", "store")
# PR #86: engine evaluations are registered in the Ledger (id = start record hash); screening and forward
# observations in the Store (id = SHA-256 of the canonical start payload with a nonce). An id is meaningful only
# together with its store.
STORE_OF_KIND = {"engine_evaluation": "ledger", "screening": "store", "forward_observation": "store"}
ATTEMPT_KINDS = {roles.EXPLORATION: ("engine_evaluation", "screening"),
                 roles.RESERVE: ("engine_evaluation",),
                 roles.FORWARD: ("engine_evaluation", "forward_observation")}

_OBSERVED = {"observed_start", "observed_end"}
# Each verifier, the existing code that must produce its result, and the facts it must state.
VERIFIERS = {
    "spec_registry": ("the frozen spec in the registry: identity, channel, domain, holding period",
                      {"spec_hash", "channel", "domain", "holding_periods"}),
    "batch_freeze": ("manhattan.freeze.verify_frozen: signed tag, manifest hash, external timestamp",
                     {"spec_hash", "batch", "freeze", "manifest_hash"}),
    "synthetic_generator": ("the generator definition and seed that produced the values", {"vintage_id"} | _OBSERVED),
    "publication_contract": ("manhattan.availability.validate_source on the recorded source definition",
                             {"source_id", "contract_sha256"}),
    "public_archive": ("SHA-256 of the archived public snapshot, and the dates it holds for this span",
                       {"vintage_id", "as_of"} | _OBSERVED),
    "licensed_snapshot": ("SHA-256 manifest of the private licensed snapshot (never in this repository)",
                          {"vintage_id", "as_of"} | _OBSERVED),
    "capture_replay": ("manhattan.ops.data.first_seen: raw hashes, byte counts, schema-v2 definition, counts",
                       {"source_id", "capture_id", "monitoring_start", "backfill", "late"} | _OBSERVED),
    "store_anchor": ("manhattan.ops.store.verify_chain against an anchor, with its assurance level",
                     {"capture_id", "anchor", "assurance"}),
    "runner_token": ("a verified RunnerToken (PR #86 contract: batch, manifest hash, spec in the manifest) naming "
                     "this (domain, window) as unused and designated",
                     {"domain", "window_id", "batch", "manifest_hash", "spec_hash"}),
    "attempt_binding": ("the registered attempt the observations belong to (PR #86), read from an anchored history",
                        {"attempt_id", "store", "kind", "spec_hash", "batch", "role", "designated", "window_id",
                         "window_start", "window_end", "freeze", "holding", "terminal", "superseded", "assurance"}),
}
REQUIRED = {
    SYNTHETIC: {"spec_registry", "synthetic_generator"},
    HISTORICAL_PUBLIC: {"spec_registry", "publication_contract", "public_archive"},
    HISTORICAL_LICENSED: {"spec_registry", "publication_contract", "licensed_snapshot"},
    CAPTURED_FORWARD: {"spec_registry", "publication_contract", "capture_replay", "store_anchor"},
}

# Gates that forward e-LOND eligibility needs and that no code implements yet. Each stays a blocker until the
# protected protocol is adopted and the gate exists in code; this module can never clear them.
UNIMPLEMENTED_GATES = (
    "enrolment gate (Protocol v3.1 section 6.8: enrolled at the first review as Promising or higher) not implemented",
    "attempt binding (each observation tied to a registered, anchored attempt; PR #86) not integrated",
    "guard and test-period construction (Protocol v3.1 sections 6.1-6.7) not wired to classified evidence",
)

_SHA = re.compile(r"[0-9a-f]{64}")
_TOP = {"schema", "source", "domain", "span", "vintage", "capture", "spec", "window", "attempt", "designated",
        "claimed_role", "claimed_provenance"}
_SOURCE = {"id", "kind", "publication_contract"}
_VINTAGE = {"kind", "id", "as_of"}
_CAPTURE = {"capture_id", "schema_version", "monitoring_start", "first_retrieved_utc", "reconstructed"}
_RECON = {"backfill", "late"}
_SPEC = {"spec_hash", "channel", "freeze", "holding_periods"}
_MAX_SPAN_DAYS = roles.MAX_READ_DAYS
_MAX_HOLDING = 2_520                       # ten years of weekdays: a sanity bound, not a rule
_SCALARS = (str, int, bool, type(None))


@dataclass(frozen=True)
class VerifierResult:
    """What a verifier established about one metadata subject. ``subject`` is a digest (integrity only); ``facts``
    count only when ``authority`` is trusted. Constructing one proves nothing: see the module docstring.

    ``facts`` is copied at construction into a read-only mapping of scalars (text, whole numbers, booleans,
    None); later changes to the caller's mapping do not reach it. Any other shape is stored as ``None`` and fails
    closed when classified."""
    verifier: str
    authority: str
    subject: str
    facts: Mapping

    def __post_init__(self):
        f = self.facts
        ok = isinstance(f, Mapping) and all(isinstance(k, str) for k in f) \
            and all(type(v) in _SCALARS for v in f.values())
        object.__setattr__(self, "facts", MappingProxyType(dict(f)) if ok else None)


@dataclass(frozen=True)
class Identity:
    spec_hash: str
    channel: str
    domain: str
    freeze: str | None
    holding_periods: int
    window_id: str
    start: str
    end: str
    attempt_id: str | None
    attempt_store: str | None = None
    window_verified: bool = False      # window identity and boundaries stated by an authoritative attempt binding
    batch: str | None = None           # the frozen batch, from batch_freeze or the attempt binding (never metadata)
    designated: bool = False


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
    identity: Identity | None = None
    authenticated: bool = False
    parts: tuple = field(default_factory=tuple)

    @property
    def genuine_capture(self) -> bool:
        """Captured forward and seen as it happened: no backfill, no late marks, no assumed availability."""
        return self.provenance == CAPTURED_FORWARD and not self.reconstruction and self.availability == AVAIL_FIRST_SEEN

    @property
    def subjects(self) -> tuple:
        return tuple(p.subject for p in self.parts) if self.parts else (self.subject,)


# ---------------------------------------------------------------- issued-object registry (N4)

_ISSUED: dict = {}


def _fingerprint(c: Classification) -> str:
    return repr(c)


def _issue(c: Classification) -> Classification:
    key = id(c)
    _ISSUED[key] = (weakref.ref(c, lambda _ref, k=key: _ISSUED.pop(k, None)), _fingerprint(c))
    return c


def issued(c) -> bool:
    """True only for a Classification this module returned and that is unchanged since."""
    if type(c) is not Classification:
        return False
    entry = _ISSUED.get(id(c))
    return entry is not None and entry[0]() is c and entry[1] == _fingerprint(c)


class EvidenceError(ValueError):
    """Raised only by the public helpers ``subject_digest`` and ``contract_digest`` on non-JSON input."""


_Reject = EvidenceError


def canonical(obj) -> bytes:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise _Reject(f"not canonical JSON: {type(exc).__name__}") from None


def subject_digest(metadata: Mapping) -> str:
    """The SHA-256 every verifier result must name. A digest: anyone can compute it; it authenticates nothing."""
    return hashlib.sha256(canonical(metadata)).hexdigest()


def contract_digest(contract: Mapping) -> str:
    return hashlib.sha256(canonical(contract)).hexdigest()


def _unverified(problems, subject=None, role=None) -> Classification:
    return _issue(Classification(UNVERIFIED, False, frozenset({UNKNOWN}), AVAIL_UNKNOWN, role, AUTH_NONE, E_NONE, 0,
                                 False, False, False, ("provenance unverified",), tuple(problems), subject))


def _fail(msg):
    raise _Reject(msg)


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _sha(v, what) -> str:
    if not isinstance(v, str) or not _SHA.fullmatch(v):
        _fail(f"{what} must be a SHA-256")
    return v


def _whole(v, what, hi=None) -> int:
    if type(v) is not int or v < 0 or (hi is not None and v > hi):
        _fail(f"{what} must be a whole number, 0 or more" + (f" and at most {hi}" if hi is not None else ""))
    return v


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
    if not all(isinstance(k, str) for k in obj):
        _fail(f"{what} has non-text keys")
    unknown = set(obj) - allowed
    if unknown:
        _fail(f"{what} has unknown fields {sorted(unknown)} (closed schema)")
    missing = required - set(obj)
    if missing:
        _fail(f"{what} is missing {sorted(missing)}")


def _check_fence(fence) -> None:
    if type(fence) is not roles.Fence:
        _fail("fence must be a manhattan.roles.Fence")
    if not isinstance(fence.exploration_end, date) or type(fence.enabled) is not bool \
            or not isinstance(fence.reserve, Mapping):
        _fail("malformed fence")
    for dom, w in fence.reserve.items():
        if not isinstance(dom, str) or not isinstance(w, tuple) or len(w) != 2 \
                or not all(isinstance(d, date) for d in w) or w[1] < w[0]:
            _fail("malformed reserve window in fence")


def _check_config(config, protocol_hash) -> dict:
    """Only the shapes ``manhattan.config`` produces; anything else fails closed (never AttributeError)."""
    if config is None:
        config = {}
    if not isinstance(config, Mapping):
        _fail("config must be a mapping")
    for section in ("reserve", "claims"):
        if section in config:
            sub = config[section]
            if not isinstance(sub, Mapping):
                _fail(f"config.{section} must be a mapping")
            if "enabled" in sub and type(sub["enabled"]) is not bool:
                _fail(f"config.{section}.enabled must be a boolean")
    if protocol_hash is not None:
        _sha(protocol_hash, "protocol_hash")
    return {"reserve": dict(config.get("reserve") or {}), "claims": dict(config.get("claims") or {})}


def _computed_role(domain, start, end, fence, freeze, holding) -> str:
    days = np.arange(np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"))
    found = {roles.role_of(d.astype(object), domain, fence, freeze, holding) for d in days}
    if len(found) != 1:
        _fail(f"the span covers several roles {sorted(found)}: one span, one role")
    return found.pop()


def classify(metadata: Mapping, verifications=None, *, fence: roles.Fence, config: Mapping | None = None,
             protocol_hash: str | None = None) -> Classification:
    """Classify one homogeneous body of evidence. Never raises: it fails closed instead."""
    subject = None
    try:
        subject = subject_digest(metadata) if isinstance(metadata, Mapping) else None
        return _issue(_classify(metadata, verifications, fence, config, protocol_hash, subject))
    except _Reject as exc:
        return _unverified([str(exc)], subject)
    except Exception as exc:          # a bug or an unforeseen shape: fail closed, never a default class
        return _unverified([f"classifier refused malformed input ({type(exc).__name__})"], subject)


def _facts(verifications, subject, need) -> dict:
    """The facts of each needed verifier, from trusted authorities only, bound to this subject."""
    if verifications is None:
        _fail("no verifier results supplied")
    if isinstance(verifications, (str, bytes, Mapping)) or not isinstance(verifications, (list, tuple)):
        _fail("verifier results must be a list of VerifierResult")
    out: dict = {}
    for r in verifications:
        if type(r) is not VerifierResult:
            _fail("a verifier result is not a VerifierResult (a digest or label is not a verification)")
        if r.verifier not in VERIFIERS:
            _fail(f"unknown verifier {r.verifier!r}")
        if r.verifier in out:
            _fail(f"two results from verifier {r.verifier!r}")
        if r.subject != subject:
            _fail(f"{r.verifier} result is bound to other metadata (integrity check failed)")
        if not isinstance(r.authority, str) or r.authority not in TRUSTED_AUTHORITIES:
            _fail(f"{r.verifier} result is not from a trusted authority (none is configured: authentication "
                  "needs an integration boundary that does not exist yet)")
        expected = VERIFIERS[r.verifier][1]
        if type(r.facts) is not MappingProxyType or set(r.facts) != expected:
            _fail(f"{r.verifier} result must state exactly {sorted(expected)} as scalars")
        out[r.verifier] = dict(r.facts)          # a private snapshot: nothing outside can change it now
    missing, extra = sorted(need - set(out)), sorted(set(out) - need)
    if missing:
        _fail(f"required verifier results missing: {missing}")
    if extra:
        _fail(f"verifier results that do not apply to this evidence: {extra}")
    return out


def _agree(fact, value, what):
    if type(fact) is not type(value) or fact != value:
        _fail(f"verified {what} contradicts the metadata")


def _classify(md, verifications, fence, config, protocol_hash, subject) -> Classification:
    _check_fence(fence)
    config = _check_config(config, protocol_hash)
    _keys(md, _TOP, {"schema", "source", "domain", "span", "vintage", "spec", "window", "designated"}, "metadata")
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

    # span, vintage, window, attempt
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
    _sha(vin["id"], "vintage id (an ambiguous or missing vintage fails closed)")
    as_of = _date(vin["as_of"], "vintage.as_of")
    if as_of < end:
        _fail("vintage as_of precedes the end of the span it holds")
    win = md["window"]
    _keys(win, {"id"}, {"id"}, "window")
    if not _text(win["id"]):
        _fail("window id is required")
    attempt = md.get("attempt")
    if "attempt" in md:
        _keys(attempt, {"id", "store"}, {"id", "store"}, "attempt")
        _sha(attempt["id"], "attempt id")
        if attempt["store"] not in ATTEMPT_STORES:
            _fail("attempt store must be ledger or store (their attempt ids are derived differently)")

    # spec: identity, freeze and holding period (never defaulted)
    spec = md["spec"]
    _keys(spec, _SPEC, _SPEC, "spec")
    _sha(spec["spec_hash"], "spec_hash")
    if spec["channel"] not in ("blind", "adaptive"):
        _fail("spec channel must be blind or adaptive")
    channel = spec["channel"]
    freeze = None if spec["freeze"] is None else _date(spec["freeze"], "spec.freeze")
    holding = _whole(spec["holding_periods"], "spec.holding_periods", _MAX_HOLDING)

    role = _computed_role(md["domain"], start, end, fence, freeze, holding)
    if "claimed_role" in md and md["claimed_role"] != role:
        _fail(f"claimed role {md['claimed_role']!r} contradicts the computed role {role!r}")
    designated = md["designated"]
    if designated and role != roles.RESERVE:
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

    recon: set = set()
    if provenance == CAPTURED_FORWARD:
        recon |= _capture_reconstruction(capture, vin, start, as_of)

    # verifier results: integrity (bound to this subject) and authority (trusted), then facts == metadata
    need = set(REQUIRED[provenance])
    if role == roles.FORWARD:
        need.add("batch_freeze")
    if designated:                                   # role is reserve (checked above)
        if attempt is None:
            _fail("a designated reserve evaluation must name its registered attempt")
        need |= {"runner_token", "batch_freeze", "attempt_binding"}
    if attempt is not None:
        need.add("attempt_binding")
    facts = _facts(verifications, subject, need)
    f = facts["spec_registry"]
    _agree(f["spec_hash"], spec["spec_hash"], "spec identity")
    _agree(f["channel"], channel, "channel")
    _agree(f["domain"], md["domain"], "domain")
    _agree(f["holding_periods"], holding, "holding period")
    if "batch_freeze" in facts:
        f = facts["batch_freeze"]
        _agree(f["spec_hash"], spec["spec_hash"], "frozen spec identity")
        _agree(f["freeze"], spec["freeze"], "freeze date (the manifest's)")
        _sha(f["manifest_hash"], "verified manifest hash")
        if not _text(f["batch"]):
            _fail("verified batch is required")
    if "runner_token" in facts:
        f, frz = facts["runner_token"], facts["batch_freeze"]
        _agree(f["domain"], md["domain"], "token domain")
        _agree(f["window_id"], win["id"], "token window identity")
        _agree(f["spec_hash"], spec["spec_hash"], "token spec (the manifest must name this spec)")
        _agree(f["batch"], frz["batch"], "token batch (the frozen batch)")
        _agree(f["manifest_hash"], frz["manifest_hash"], "token manifest (the frozen manifest)")
    for v in ("synthetic_generator", "public_archive", "licensed_snapshot", "capture_replay"):
        if v in facts:                               # the observed dates are the classified span (N2)
            _agree(facts[v]["observed_start"], span["start"], "first observed date")
            _agree(facts[v]["observed_end"], span["end"], "last observed date")
    if "synthetic_generator" in facts:
        _agree(facts["synthetic_generator"]["vintage_id"], vin["id"], "generator vintage")
    for v in ("public_archive", "licensed_snapshot"):
        if v in facts:
            _agree(facts[v]["vintage_id"], vin["id"], "snapshot identity")
            _agree(facts[v]["as_of"], vin["as_of"], "snapshot date")
    if "publication_contract" in facts:
        _agree(facts["publication_contract"]["source_id"], src["id"], "source identity")
        _agree(facts["publication_contract"]["contract_sha256"], contract_digest(contract), "publication contract")
    if "capture_replay" in facts:
        f = facts["capture_replay"]
        _agree(f["source_id"], src["id"], "capture source")
        _agree(f["capture_id"], capture["capture_id"], "capture identity")
        _agree(f["monitoring_start"], capture["monitoring_start"], "monitoring start")
        _agree(f["backfill"], capture["reconstructed"]["backfill"], "backfill count")
        _agree(f["late"], capture["reconstructed"]["late"], "late count")
    anchors_independent = True
    if "store_anchor" in facts:
        f = facts["store_anchor"]
        _agree(f["capture_id"], capture["capture_id"], "anchored capture identity")
        _sha(f["anchor"], "store anchor")
        if f["assurance"] not in (SUPPLIED_ANCHOR, INDEPENDENT_ANCHOR):
            _fail("unknown store anchor assurance")
        anchors_independent &= f["assurance"] == INDEPENDENT_ANCHOR
    effective_freeze = freeze
    if "attempt_binding" in facts:
        f = facts["attempt_binding"]
        _agree(f["attempt_id"], attempt["id"], "attempt identity")
        _agree(f["store"], attempt["store"], "attempt store")
        _agree(f["spec_hash"], spec["spec_hash"], "attempt spec identity")
        _agree(f["window_id"], win["id"], "attempt window identity")
        _agree(f["role"], role, "attempt role")
        _agree(f["designated"], designated, "attempt designation")
        _agree(f["holding"], holding, "attempt holding period (must be the spec's, never a default)")
        if "batch_freeze" in facts:
            _agree(f["batch"], facts["batch_freeze"]["batch"], "attempt batch (must be the frozen batch)")
        elif not _text(f["batch"]):
            _fail("verified attempt batch is required")
        if role == roles.RESERVE and not designated:
            _fail("a reserve attempt is always its batch's designated evaluation of the domain (PR #86 D-13)")
        if f["kind"] not in ATTEMPT_KINDS.get(role, ()):
            _fail(f"an attempt of kind {f['kind']!r} cannot carry {role} evidence")
        if STORE_OF_KIND[f["kind"]] != attempt["store"]:
            _fail(f"a {f['kind']} attempt is registered in the {STORE_OF_KIND[f['kind']]}, not the {attempt['store']}")
        if f["terminal"] != "completed" or f["superseded"] is not False:
            _fail("only a completed, non-superseded attempt carries evidence")
        if f["assurance"] not in (SUPPLIED_ANCHOR, INDEPENDENT_ANCHOR):
            _fail("unknown attempt history assurance")
        anchors_independent &= f["assurance"] == INDEPENDENT_ANCHOR
        w0, w1 = _date(f["window_start"], "verified window start"), _date(f["window_end"], "verified window end")
        if not (w0 <= start and end <= w1):
            _fail("the observed span lies outside the attempt's verified window")
        if role == roles.FORWARD:
            # the attempt's own freeze (PR #86: the prediction's registration date) can only move the start later
            registered = _date(f["freeze"], "attempt freeze")
            if freeze is None or registered < freeze:
                _fail("the attempt's registration freeze precedes the manifest freeze")
            effective_freeze = registered
            try:
                after = _computed_role(md["domain"], start, end, fence, effective_freeze, holding) == roles.FORWARD
            except _Reject:
                after = False
            if not after:
                _fail("the observed span is not after the attempt's registration freeze")
        elif f["freeze"] is not None and f["freeze"] != spec["freeze"]:
            _fail("verified attempt freeze contradicts the metadata")

    # reconstruction and availability, each explicit
    if akind == "conservative":
        recon.add(CONSERVATIVE)
    if provenance == SYNTHETIC:
        availability = AVAIL_GENERATED
    elif provenance == CAPTURED_FORWARD:
        availability = AVAIL_CONSERVATIVE if akind == "conservative" else AVAIL_FIRST_SEEN
    else:
        availability = {"release_dates": AVAIL_PER_VINTAGE, "release_calendar": AVAIL_PER_VINTAGE,
                        "daily_lag": AVAIL_DECLARED_LAG, "conservative": AVAIL_CONSERVATIVE}[akind]

    # authorization (what lets these dates be read in this role)
    if role == roles.EXPLORATION:
        authorization = AUTH_OPEN
    elif role == roles.RESERVE and designated and config["reserve"].get("enabled") is True and fence.enabled:
        authorization = AUTH_RESERVE
    elif role == roles.FORWARD:
        authorization = AUTH_FREEZE           # an authoritative batch_freeze result was required above
    else:
        authorization = AUTH_NONE

    # eligibility: provenance can only disqualify
    reconstructed = bool(recon)
    bound = "attempt_binding" in facts
    blockers: list[str] = []
    if provenance == SYNTHETIC:
        eligibility = E_INFRA
        blockers.append("synthetic evidence validates infrastructure, never market performance")
    elif role == roles.EMBARGO or authorization == AUTH_NONE:
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
        elif not anchors_independent:
            eligibility = E_DESCRIPTIVE
            blockers.append("the attempt history is checked against a supplied anchor only, not independently "
                            "anchored")
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
        elif not bound:
            eligibility = E_DESCRIPTIVE
            blockers.append("forward observations without an authoritative attempt binding have no verified "
                            "window or attempt identity")
        elif not anchors_independent:
            eligibility = E_DESCRIPTIVE
            blockers.append("the capture or attempt history is checked against a supplied anchor only, not "
                            "independently anchored")
        else:
            eligibility = E_FORWARD
            blockers.append("captured-forward provenance is necessary, not sufficient, for forward e-LOND")

    ceiling = evidential_weight(channel, role, designated, reconstructed) \
        if eligibility in (E_RESERVE, E_FORWARD) else 0
    enabled, reason = promotion.status(protocol_hash, config)
    if not enabled:
        blockers.append(f"promotion disabled: {reason}")
    if eligibility == E_FORWARD:
        blockers.extend(UNIMPLEMENTED_GATES)
    if eligibility == E_RESERVE:
        blockers.append("screening is not implemented and is out of scope for classification")
    batch = facts["batch_freeze"]["batch"] if "batch_freeze" in facts else \
        facts["attempt_binding"]["batch"] if bound else None
    ident = Identity(spec["spec_hash"], channel, md["domain"],
                     None if effective_freeze is None else effective_freeze.isoformat(), holding, win["id"],
                     span["start"], span["end"], None if attempt is None else attempt["id"],
                     None if attempt is None else attempt["store"], bound, batch, designated)
    return Classification(provenance, kind == "licensed", frozenset(recon), availability, role, authorization,
                          eligibility, ceiling, False, False, False, tuple(blockers), (), subject, ident, True)


def _capture_reconstruction(capture, vin, start: date, as_of: date) -> set:
    _keys(capture, _CAPTURE, _CAPTURE, "capture")
    _sha(capture["capture_id"], "capture identity")
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
    backfill, late = _whole(counts["backfill"], "backfill count"), _whole(counts["late"], "late count")
    if start < monitoring and not backfill:
        _fail("span starts before monitoring began but reports no backfill (reconstructed data posing as captured)")
    recon = set()
    if backfill or start < monitoring:
        recon.add(BACKFILLED)
    if late:
        recon.add(LATE)
    return recon


def cap_weight(c: Classification, recorded_weight: int) -> int:
    """A recorded evidential weight, lowered to the classification's ceiling. Never raises a weight. A
    classification this module did not issue, or one changed since, gives 0."""
    if not issued(c) or type(recorded_weight) is not int or recorded_weight not in (0, 1) \
            or type(c.weight_ceiling) is not int:
        return 0
    return max(0, min(recorded_weight, c.weight_ceiling))


_RANK = {E_NONE: 0, E_INFRA: 1, E_DESCRIPTIVE: 2, E_RESERVE: 3, E_FORWARD: 3}


def combine(parts) -> Classification:
    """One result for evidence assembled from several classified parts of **one spec's** record.

    Fails closed on: a part this module did not issue (or that changed since); a failed or unauthenticated part; a
    part of another spec, channel, domain, freeze or holding period; mixed provenance, role, licence, availability
    or authorization; a duplicate (same subject, window or attempt); overlapping spans; or attempt identities
    present on some parts only. The result keeps every part (and so every subject and individual provenance) and
    takes the weakest part's eligibility. Freezes are compared after each part's attempt registration."""
    try:
        parts = tuple(parts)
    except Exception:
        return _unverified(["parts are not iterable"])
    if not parts or not all(issued(p) for p in parts):
        return _unverified(["nothing to combine, or a part this module did not issue (or that has changed)"])
    if any(p.provenance == UNVERIFIED or not p.authenticated or p.identity is None for p in parts):
        return _unverified(["a part is unverified"] + [q for p in parts for q in p.problems])
    ids = [p.identity for p in parts]
    same = {(i.spec_hash, i.channel, i.domain, i.freeze, i.holding_periods, i.batch) for i in ids}
    if len(same) != 1:
        return _unverified(["parts belong to different specs, channels, domains, freezes, holding periods or "
                            "batches"])
    designations = [(i.batch, i.domain) for i in ids if i.designated]
    if any(b is None for b, _ in designations) or len(set(designations)) != len(designations):
        # ARCHITECTURE 6.2 / PR #86 D-6: one designated reserve evaluation per (batch, domain), whatever the
        # windows or attempt ids
        return _unverified(["more than one designated reserve evaluation of one (batch, domain)"])
    keys = {(p.provenance, p.role, p.licensed, p.availability, p.authorization) for p in parts}
    if len(keys) > 1:
        return _unverified([f"mixed provenance or role: {sorted(map(str, keys))}"])
    for what, vals in (("subject", [p.subject for p in parts]), ("window", [i.window_id for i in ids])):
        if len(set(vals)) != len(vals):
            return _unverified([f"duplicate {what} among parts"])
    attempts = [(i.attempt_store, i.attempt_id) for i in ids]
    if any(a[1] is None for a in attempts) and any(a[1] is not None for a in attempts):
        return _unverified(["attempt identity present on some parts only"])
    present = [a for a in attempts if a[1] is not None]
    if len({a[1] for a in present}) != len(present):
        return _unverified(["duplicate attempt among parts (in either store)"])
    spans = sorted((i.start, i.end) for i in ids)
    if any(b[0] <= a[1] for a, b in zip(spans, spans[1:])):
        return _unverified(["evidence spans overlap"])
    first = parts[0]
    worst = min(parts, key=lambda p: (_RANK[p.eligibility], p.weight_ceiling))
    recon = frozenset().union(*(p.reconstruction for p in parts))
    return _issue(Classification(first.provenance, first.licensed, recon, first.availability, first.role,
                                 first.authorization, worst.eligibility, min(p.weight_ceiling for p in parts),
                                 False, False, False, tuple(dict.fromkeys(b for p in parts for b in p.blockers)),
                                 (), None, None, True, parts))
