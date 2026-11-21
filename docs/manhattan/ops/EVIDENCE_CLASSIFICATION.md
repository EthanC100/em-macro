# Evidence classification: module, integration contract and limits

Module: `manhattan/evidence.py` (metadata schema `manhattan.evidence/3`). Tests: `tests/test_manhattan_evidence.py`
(synthetic fixtures only). Status: **a pure classifier, not wired into any runner, ledger or attempt path, and
unable to authenticate anything today.** `TRUSTED_AUTHORITIES` is empty, so every classification is `unverified`. A
clean-subprocess test pins that shipped value. The module changes no scientific rule, threshold, pre-registration,
e-process or e-LOND code, and adds no statistical test.

## What it decides

Six axes, each decided separately and never inferred from another:

| axis | values | decided from |
|---|---|---|
| provenance | `synthetic`, `historical_public`, `historical_licensed`, `captured_forward`, `unverified` | the closed metadata schema (source kind, vintage kind, capture block); every required verifier result must come from a trusted authority, with facts equal to the metadata |
| reconstruction | set of `backfilled`, `late`, `conservative_assumption` (`unknown` when unverified) | capture counts, monitoring start vs span, the publication contract's availability kind |
| availability | `per_vintage_release`, `declared_daily_lag`, `first_seen_capture`, `conservative_assumption`, `generated`, `unknown` | the publication contract (`manhattan.availability.validate_source`) |
| role | `exploration`, `reserve`, `forward`, `embargo` | **computed** with `manhattan.roles.role_of` on every day of the span, from the fence, the freeze and the spec's holding period; a supplied label may only agree |
| authorization | `exploration_open`, `reserve_designated_verified`, `forward_freeze_verified`, `unauthorized` | role, designation, `reserve.enabled` and the authoritative token, freeze and attempt results |
| eligibility | `none`, `infrastructure_validation`, `descriptive`, `reserve_screening_candidate`, `forward_candidate` | the axes above; provenance and anchoring can only disqualify |

**Fixed outputs.** Every result has `forward_elond_eligible = False`, `screening_eligible = False` and
`promotion_authorized = False`; no input changes them. A *candidate* means only "not disqualified".

**Weights.** `weight_ceiling` is the value of the unchanged `manhattan.ledger.evidential_weight` table (ARCHITECTURE
6.3) for a candidate, and 0 otherwise.

**Requirements for a candidate:**
- an authoritative binding to a completed, non-superseded attempt;
- the observed span inside that attempt's verified window;
- anchors reported as **independently** anchored, which PR #86 never reports today, so no candidate is reachable
  through it.

## Digests versus verified facts

**Integrity.** `VerifierResult.subject` must equal `subject_digest(metadata)`. Anyone can compute that digest. It
detects edits made after verification and establishes no fact; a mapping of digests is refused.

**Authority.** Facts are read only from results whose `authority` is in `TRUSTED_AUTHORITIES`. Each verifier must
state exactly its fact set, as scalars (N5: copied at construction into a read-only mapping). Every fact must equal
the metadata in type and value. Results must be exactly the required set: missing, extra, duplicate, unknown or
untrusted results fail closed.

| verifier | facts | existing code that must produce it |
|---|---|---|
| `spec_registry` | `spec_hash`, `channel`, `domain`, `holding_periods` | the frozen spec |
| `batch_freeze` | `spec_hash`, `batch`, `freeze`, `manifest_hash` | `manhattan.freeze.verify_frozen` |
| `runner_token` | `domain`, `window_id`, `batch`, `manifest_hash`, `spec_hash` | a verified `roles.RunnerToken` (PR #86 snapshot: batch, manifest hash, spec in `token.specs`) naming this designated (domain, window) |
| `attempt_binding` | `attempt_id`, `store`, `kind`, `spec_hash`, `batch`, `role`, `designated`, `window_id`, `window_start`, `window_end`, `freeze`, `holding`, `terminal`, `superseded`, `assurance` | PR #86's anchored attempt history (start record, its `authorization`, its terminal, reconciliation assurance) |
| `capture_replay` | `source_id`, `capture_id`, `monitoring_start`, `backfill`, `late`, `observed_start`, `observed_end` | `manhattan.ops.data.first_seen` |
| `store_anchor` | `capture_id`, `anchor`, `assurance` | `manhattan.ops.store.verify_chain` and the reconciler's assurance level |
| `publication_contract` | `source_id`, `contract_sha256` | `validate_source` on the recorded source definition |
| `public_archive` / `licensed_snapshot` | `vintage_id`, `as_of`, `observed_start`, `observed_end` | the snapshot's SHA-256 (licensed: computed on the iMac, never in this repository) |
| `synthetic_generator` | `vintage_id`, `observed_start`, `observed_end` | the generator definition and seed |

**Required verifiers:**
- `spec_registry`, always;
- by provenance: synthetic needs `synthetic_generator`; historical needs `publication_contract` plus `public_archive` or
  `licensed_snapshot`; captured forward needs `publication_contract`, `capture_replay` and `store_anchor`;
- forward-role spans: `batch_freeze`;
- designated reserve spans: `runner_token`, `batch_freeze` and `attempt_binding` (and the metadata must name the
  attempt);
- any metadata `attempt`: `attempt_binding`.

## Re-review corrections (head after `178c5bd`)

**N1: shipped authority.**
- `test_shipped_module_trusts_no_authority` imports the module file in a fresh `python -I` subprocess, where no
  pytest fixture can patch it, and requires `TRUSTED_AUTHORITIES` to be an empty `frozenset` after the whole module
  has run.
- `test_shipped_authority_check_fails_on_a_non_empty_shipped_value` appends four mutations to a copy of the module and
  shows the same check fails on each: a plain reassignment (S6's), `|=`, `globals()[...]` and a non-frozen set.
- Done by hand as S6 did it, inserting a plain assignment into the real module: that test fails and the other 299 pass.

**N2: observed span.**
- Every provenance verifier states `observed_start` and `observed_end`, which must equal the classified span.
- `attempt_binding` states the attempt's verified window, and the span must lie inside it.
- A cumulative forward window (PR #86: first observation to `asof` + 7 days) that contains the span is accepted.

**N3: reserve token.**
- `runner_token` follows PR #86's token snapshot (batch, manifest hash, spec hash) plus domain and window.
- Its batch and manifest must equal the authoritative `batch_freeze`, and its spec the classified spec.
- A designated reserve span also needs an `engine_evaluation` attempt binding from the Ledger, with role `reserve`
  and `designated: true`.

**N4: forged classifications.**
- `cap_weight` and `combine` accept only objects `classify` or `combine` returned, unchanged. They are checked by
  object identity against a weak-reference registry, with a fingerprint taken at issue.
- Caller-built objects, `dataclasses.replace` and `copy` copies, and objects mutated with `object.__setattr__` get
  weight 0 and cannot be combined.
- The registry is bookkeeping, not a security boundary: it never changes what `classify` returns.

**N5: verifier facts.**
- `VerifierResult.facts` is copied at construction into a `MappingProxyType`.
- Non-scalar values or a non-mapping become `None`, which fails closed.
- Later changes to the caller's dict have no effect, and the proxy refuses assignment.

## Final hardening (after `1e86b33`)

**A1: batch identity.**
- `attempt_binding` states the attempt's `batch` (PR #86 identity field).
- When a `batch_freeze` result is required (forward spans, designated reserve), the attempt batch must equal the
  frozen batch. Otherwise it must be non-empty text.
- `Identity.batch` comes from verified facts only. `combine` rejects parts of different batches, and any two
  designated reserve evaluations of one (batch, domain), whatever their windows, spans or attempt ids (ARCHITECTURE
  6.2; PR #86 D-6).
- Following PR #86 D-13, an attempt binding for a non-designated reserve attempt is refused.

**A2: static check on `TRUSTED_AUTHORITIES`.**
- `test_no_production_module_touches_trusted_authorities` parses every tracked `*.py` outside `tests/`.
- Outside `manhattan/evidence.py`, any of these is a finding:
  - a store, delete or augmented assignment of the name, or of an attribute of that name;
  - `global` or `nonlocal` of it;
  - an import of it;
  - a keyword argument of that name (`__dict__.update(TRUSTED_AUTHORITIES=...)`);
  - any non-docstring string containing it (`setattr`, `object.__setattr__`, `vars(m)[...]`, `m.__dict__[...]`,
    `globals()[...]`, `sys.modules[...]`, `mock.patch(...)`, `mock.patch.object(...)`).
- Inside `manhattan/evidence.py`, only loads, docstrings and the one module-level
  `TRUSTED_AUTHORITIES: frozenset[str] = frozenset()` are allowed. The allowance is matched by AST node, so a second
  assignment on the same line is still caught.
- 21 positive-control snippets, 5 owner-module mutations, the same-line case and a non-empty shipped value are all
  shown to be caught.

**Limits of the static check.**
- It sees source text only. A name built at run time (`"TRUSTED_" + "AUTHORITIES"`, decoded bytes) is invisible to
  it; `test_static_check_limitation_constructed_names_are_not_seen` records that explicitly.
- It does not see:
  - `importlib` reloads of a modified file;
  - C extensions;
  - debuggers;
  - `gc.get_referents` tricks;
  - code outside the repository;
  - anything executed from data.
- Hostile code running in the same process can always replace the value. The controls against that are code review
  (CODEOWNERS, an owner action), the clean-subprocess check of the shipped value (N1), and, at activation, an
  authentication boundary outside the process.
- Tests are excluded from the scan by design: they patch the set to exercise the logic under a simulated authority.

Earlier fixes kept:
- **M1:** the spec's holding period, never defaulted, passed to `role_of`, with boundary tests for 0, 5 and 20.
- **M2:** malformed config, protocol hash and fence fail closed; seeded fuzz tests cover them.
- **H2:** digests are integrity only, and facts must come from a trusted authority.
- **M3:** `combine` checks identity, duplicates and overlaps.

## PR #86 integration contracts (checked against head `5aa643f`)

Re-checked at `5aa643f`:
- `roles`, `availability` and `ops.promotion` are unchanged since `8615c69`, and `ledger.evidential_weight` is
  unchanged.
- The attempt `authorization` now also records `config_sha256`. This module reads no field that changed.
- D-13 is new: a reserve attempt is always the designated evaluation. It is mirrored here (A1).
- `register_evaluation` and `StoreAttempt` still default `holding` to 0, so contract 1 still stands.

1. **Authoritative holding periods.**
   - At `5aa643f` PR #86 still takes `holding` as a caller argument that defaults to 0; its forward-observation
     attempts pass none.
   - The classifier requires `attempt_binding.holding == spec_registry.holding_periods == spec.holding_periods`. A
     default-0 registration of a spec with a longer holding period fails closed
     (`test_attempt_holding_must_be_the_specs_never_a_default`).
   - Required of the integration: registration takes the holding period from the frozen spec, never a default.
2. **Manifest freeze versus forward registration date.**
   - PR #86 records a forward attempt's `freeze` as the prediction's `registration_utc` date. The batch manifest's
     freeze (`batch_freeze.freeze`) is a different date.
   - The classifier requires the registration date to be on or after the manifest freeze, and recomputes the role with
     the registration date. A span that starts on or before it fails closed. `Identity.freeze` records the effective
     (later) date.
   - Neither date is taken from metadata alone.
3. **Verified observation spans versus cumulative forward windows.**
   - A forward-observation attempt declares a cumulative window from the first observation to `asof` + 7 days, while
     it records only new days.
   - The classified span must be the observed dates (`observed_start`/`observed_end` from `capture_replay`), and only
     has to lie inside the window.
   - Nightly parts combine only with disjoint spans, distinct window ids (`forward:<prediction>:<asof>`) and distinct
     attempts.
4. **Ledger versus Store attempt identifiers.**
   - Ledger ids are start-record hashes (engine evaluations). Store ids are the SHA-256 of a canonical start payload
     with a nonce (screening and forward observations).
   - Metadata name `attempt: {id, store}`. The binding must state the same store, and the kind must belong to that
     store (`STORE_OF_KIND`).
   - `combine` rejects one id appearing twice, even across stores.
5. **Completed, non-superseded attempts.** `attempt_binding.terminal` must be `"completed"` and `superseded` must be
   `false`. Failed, aborted, unfinished and superseded attempts fail closed: PR #86's `supersedes` (Ledger) and
   `retry_of` (Store) chains decide `superseded`.
6. **Supplied-anchor checks versus independent certification.**
   - PR #86 reports `checked_against_supplied_anchor` and never `independently_anchored` (D-7: no independent custody
     configured).
   - `store_anchor.assurance` and `attempt_binding.assurance` must name one of those two levels. Anything else fails
     closed.
   - A supplied-anchor check keeps evidence `descriptive` with weight 0. Only independent anchoring can support a
     candidate, so no candidate is reachable while D-7 stands.

Also required from PR #86:
- `roles.role_of` keeps its signature and embargo semantics. PR #86 adds `RunnerToken.specs` and changes nothing
  else in `roles` (still true at `5aa643f`).
- The attempt identity's `batch` is the frozen batch for reserve and forward attempts, and D-6/D-13 (one designated
  reserve attempt per (batch, domain)) stay enforced at registration.
- `ledger.evidential_weight`, `availability.validate_source` and `ops.promotion.status` stay unchanged.

## Remaining activation blockers

1. **No trusted authority.** It must be added by a reviewed change, once a boundary exists that mints results from
   anchored records, signed tags and the iMac's snapshot manifests.
2. **No independent anchor custody.** PR #86's D-7 is open, so every candidate is downgraded to `descriptive`.
3. **PR #86 is not merged and not wired.** The holding period from the spec (contract 1) and a minting boundary for
   `attempt_binding` and `runner_token` are still needed.
4. **The `UNIMPLEMENTED_GATES` and `promotion.status`:** enrolment (§6.8), guard and test-period construction
   (§§6.1-6.7), an adopted protocol hash, and `claims.enabled: true` (Ethan's).
5. **CODEOWNERS (owner action, not done here).** Ethan should add `/manhattan/evidence.py` to the protected block of
   `.github/CODEOWNERS`, so that `TRUSTED_AUTHORITIES` cannot change without his review. Sessions must not edit that
   file (hard rule 2).

## Limitations

- **Authentication.**
  - `authority` is a string in an ordinary in-process Python object, so any code in the process can build one. The set
    of trusted authorities is a code-review gate, not cryptography.
  - The issued-object registry and the read-only facts likewise stop accidental or naive forgery, not hostile code in
    the same process.
  - The tests run under a **simulated** authority. They show the logic is right given authentic results, and nothing
    about whether any result is authentic.
- **Integrity digest.** It detects edits after verification, not a lie at verification time.
- **Warm-up history.** Signal warm-up before a forward window (R-1) is not classified separately.
- **Per-observation reconstruction** is summarised by counts, trusted only as `capture_replay` facts.
- **Monitoring-start check.** It allows one day either side of the first retrieval's UTC date (market-zone close).
- **Session 1's files are not modified**: `ledger.py`, `attempts.py`, `engine/pit.py`, `engine/evaluate.py`,
  `ops/runner.py`, `ops/store.py`, `ops/data.py`, and `access.py` on PR #86. This module only imports `roles`,
  `availability`, `ledger.evidential_weight` and `ops.promotion`, read-only.
