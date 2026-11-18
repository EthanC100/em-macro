"""Data-source contracts for technology-equity research: provenance, publication timing, revision behaviour and the
research roles a source may play. Unknown or contradictory declarations fail closed.

Every dataset the programme may use is one of ``DATASET_KINDS``. A ``DataContract`` declares, for one source of one
kind:

    provenance       vendor, licence, a reference (where the data and its terms are documented)
    timestamps       what the source's time stamp means (``TIMESTAMP_SEMANTICS``)
    revisions        how the source treats later corrections (``REVISION_BEHAVIOURS``)
    coverage         whether its historical coverage and timestamps have been **verified** (not assumed)
    roles            which ``ROLES`` it is declared for

``permits(role)`` decides whether the source may be used in that role. The rules (``_ROLE_RULES``) are deliberately
strict:

* a ``signal`` (an input to a prediction at a historical date) needs a real publication time (an event time with a
  zone, a filing acceptance time or a vendor capture time), a revision behaviour of ``immutable`` or ``vintaged``,
  and verified historical coverage. A source that **overwrites** history (only the latest restated value is kept)
  can never be a signal: its history is a look-ahead;
* ``universe`` (membership and eligibility) needs the same timing guarantees;
* ``descriptive`` (comparison, visualisation, after-the-fact study) is always allowed, and is never evidence;
* ``evaluation_outcome`` (returns used to score a forecast) needs an immutable or vintaged source and verified
  coverage, and must include delisting outcomes when the kind is a price.

Alternative datasets (patents, hiring, developer adoption ...) are declared by ``alternative_contract`` with
coverage **unverified**, so they are descriptive-only until someone verifies their timestamps and revision history.

**Licensing** (CLAUDE.md hard rule 7): a ``licensed`` source's rows never enter the public repository.
``assert_publishable`` refuses it. Synthetic fixtures are ``licence="synthetic"``.

For daily observation-date sources the publication part is also checked by the existing
``manhattan.availability.validate_source`` (``as_availability_source``), so equity sources and Manhattan's PIT store
speak the same contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from manhattan.availability import AvailabilityError, validate_source

from .errors import ContractError

DATASET_KINDS = (
    # core market and reference data
    "security_master", "prices_daily", "corporate_actions", "delisting_returns", "market_calendar",
    "classification_history", "index_membership", "fx_rates",
    # fundamentals and expectations
    "fundamentals_pit", "segment_reporting", "analyst_estimates_pit", "earnings_events", "guidance_events",
    # shorting and positioning
    "borrow_availability", "short_interest", "options_implied_vol",
    # relationships and macro
    "relationship_graph", "macro_pit",
    # alternative (optional; unverified until shown otherwise)
    "patents", "product_releases", "developer_adoption", "cloud_capex", "semiconductor_supply_chain", "hiring",
    "customer_concentration", "regulatory_filings_text", "earnings_call_text", "product_adoption",
)
ALTERNATIVE_KINDS = frozenset(DATASET_KINDS[DATASET_KINDS.index("patents"):])
LICENCES = ("public", "licensed", "synthetic", "unknown")
TIMESTAMP_SEMANTICS = (
    "event_time_tz",            # the time the information became public, with a zone (press release, filing)
    "filing_acceptance_time",   # a regulator's acceptance time stamp (e.g. an EDGAR acceptance datetime)
    "vendor_capture_time",      # the time the vendor first recorded the value (known only for captured history)
    "date_only",                # a calendar date with no time of day. Nothing here converts it: the caller maps it to
    #                             a timezone-aware time after that day's close (as events.usable_close does for an
    #                             unknown time of day), so it is first usable at the next session's close
    "unknown",                  # nothing is known about when the value became public
)
REVISION_BEHAVIOURS = (
    "immutable",                # a value is never changed after publication
    "vintaged",                 # each correction is a new record with its own time stamp; old values are kept
    "overwritten",              # corrections replace history; only the latest value survives
    "unknown",
)
ROLES = ("signal", "universe", "risk", "descriptive", "evaluation_outcome")
_TIMED = ("event_time_tz", "filing_acceptance_time", "vendor_capture_time", "date_only")
_HISTORY_SAFE = ("immutable", "vintaged")


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


@dataclass(frozen=True)
class DataContract:
    name: str
    kind: str
    vendor: str
    licence: str
    reference: str
    timestamp_semantics: str
    revision_behaviour: str
    coverage_verified: bool
    roles: tuple
    coverage_note: str = ""
    includes_delisted: bool | None = None       # price-like kinds: does history include delisted securities?
    notes: tuple = field(default_factory=tuple)
    coverage_evidence: str = ""                  # where the verification is recorded; required when verified

    def __post_init__(self):
        if not _text(self.name):
            raise ContractError("a data contract needs a name")
        if self.kind not in DATASET_KINDS:
            raise ContractError(f"{self.name}: unknown dataset kind {self.kind!r}")
        if not _text(self.vendor) or not _text(self.reference):
            raise ContractError(f"{self.name}: provenance needs a vendor and a reference")
        if self.licence not in LICENCES:
            raise ContractError(f"{self.name}: licence must be one of {LICENCES}")
        if self.timestamp_semantics not in TIMESTAMP_SEMANTICS:
            raise ContractError(f"{self.name}: timestamp semantics must be one of {TIMESTAMP_SEMANTICS}")
        if self.revision_behaviour not in REVISION_BEHAVIOURS:
            raise ContractError(f"{self.name}: revision behaviour must be one of {REVISION_BEHAVIOURS}")
        if not isinstance(self.coverage_verified, bool):
            raise ContractError(f"{self.name}: coverage_verified must be a boolean")
        if self.coverage_verified and not _text(self.coverage_evidence):
            raise ContractError(f"{self.name}: coverage_verified needs coverage_evidence (where the checks of "
                                "DATA_ACQUISITION.md section 4 are recorded); a bare claim is not verification")
        roles = tuple(self.roles)
        if not roles or any(r not in ROLES for r in roles) or len(set(roles)) != len(roles):
            raise ContractError(f"{self.name}: roles must be distinct values from {ROLES}")
        object.__setattr__(self, "roles", roles)
        # a declaration that contradicts itself is refused at construction, not at first use
        for r in roles:
            why = self._refusal(r)
            if why:
                raise ContractError(f"{self.name}: declared for role {r!r} but {why}")

    def _refusal(self, role: str) -> str | None:
        if role == "descriptive":
            return None
        if self.licence == "unknown":
            return "its licence is unknown"
        if not self.coverage_verified:
            return "its historical coverage and timestamps are not verified"
        if role in ("signal", "universe", "risk"):
            if self.timestamp_semantics not in _TIMED:
                return "its publication timing is unknown"
            if self.revision_behaviour not in _HISTORY_SAFE:
                return f"its revision behaviour is {self.revision_behaviour!r} (history may contain later corrections)"
        if role == "evaluation_outcome":
            if self.revision_behaviour not in _HISTORY_SAFE:
                return f"its revision behaviour is {self.revision_behaviour!r}"
            if self.kind == "prices_daily" and self.includes_delisted is not True:
                return "a price source used for outcomes must include delisted securities and their final returns"
        return None

    def permits(self, role: str) -> bool:
        if role not in ROLES:
            raise ContractError(f"unknown role {role!r}")
        return role in self.roles and self._refusal(role) is None

    def require(self, role: str) -> None:
        """``ContractError`` unless the source may be used in ``role``."""
        if role not in ROLES:
            raise ContractError(f"unknown role {role!r}")
        if role not in self.roles:
            raise ContractError(f"{self.name}: not declared for role {role!r} (declared: {self.roles})")
        why = self._refusal(role)
        if why:
            raise ContractError(f"{self.name}: cannot be used as {role!r}: {why}")

    def assert_publishable(self) -> None:
        """Rows of this source may be committed to the public repository (hard rule 7)."""
        if self.licence not in ("public", "synthetic"):
            raise ContractError(f"{self.name}: {self.licence} data (and row-level data derived from it) never enter "
                                "the public repository")

    def as_availability_source(self, *, publication_lag_days: int = 0) -> dict:
        """This contract as a ``manhattan.availability`` daily source, validated by ``validate_source``. Only for
        daily, observation-dated sources whose timing is known; anything else needs per-vintage availability."""
        if self.timestamp_semantics not in _TIMED:
            raise ContractError(f"{self.name}: unknown timing cannot be expressed as a daily lag")
        src = {"name": self.name, "frequency": "daily", "period_label": "observation_date",
               "publication_lag_days": publication_lag_days,
               "availability": {"kind": "daily_lag", "reference": self.reference,
                                "day_mapping": f"{self.timestamp_semantics} mapped to the next usable session close "
                                               "(manhattan.equities.sessions, policy next_open)"}}
        try:
            validate_source(src)
        except AvailabilityError as exc:
            raise ContractError(f"{self.name}: {exc}") from None
        return src


def alternative_contract(name: str, kind: str, vendor: str, reference: str, *, licence: str = "unknown",
                         timestamp_semantics: str = "unknown", revision_behaviour: str = "unknown",
                         coverage_note: str = "historical timestamps not verified") -> DataContract:
    """An optional alternative dataset, declared descriptive-only until its coverage is verified."""
    if kind not in ALTERNATIVE_KINDS:
        raise ContractError(f"{kind!r} is not an alternative dataset kind")
    return DataContract(name=name, kind=kind, vendor=vendor, licence=licence, reference=reference,
                        timestamp_semantics=timestamp_semantics, revision_behaviour=revision_behaviour,
                        coverage_verified=False, roles=("descriptive",), coverage_note=coverage_note)


def synthetic_contract(kind: str, roles=("signal", "universe", "risk", "descriptive", "evaluation_outcome"),
                       **over) -> DataContract:
    """A contract for a deterministic synthetic fixture (tests only): fully timed, vintaged and verified."""
    base = dict(name=f"synthetic_{kind}", kind=kind, vendor="synthetic", licence="synthetic",
                reference="manhattan.equities.synthetic", timestamp_semantics="event_time_tz",
                revision_behaviour="vintaged", coverage_verified=True, roles=tuple(roles),
                coverage_evidence="synthetic fixture: generated, so its coverage is known by construction",
                includes_delisted=True if kind == "prices_daily" else None)
    base.update(over)
    return DataContract(**base)


class ContractRegistry:
    """The contracts a piece of research declares. A dataset kind without a contract cannot be used at all."""

    def __init__(self, contracts=()):
        self._by_kind: dict[str, DataContract] = {}
        for c in contracts:
            self.add(c)

    def add(self, c: DataContract) -> None:
        if c.kind in self._by_kind and self._by_kind[c.kind] != c:
            raise ContractError(f"two different contracts declared for {c.kind!r}: choose one source per kind")
        self._by_kind[c.kind] = c

    def contract(self, kind: str) -> DataContract:
        if kind not in DATASET_KINDS:
            raise ContractError(f"unknown dataset kind {kind!r}")
        try:
            return self._by_kind[kind]
        except KeyError:
            raise ContractError(f"no contract declared for {kind!r}: undeclared data cannot be used") from None

    def require(self, kind: str, role: str) -> DataContract:
        c = self.contract(kind)
        c.require(role)
        return c

    def kinds(self) -> tuple:
        return tuple(sorted(self._by_kind))
