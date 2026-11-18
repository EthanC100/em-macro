# Evidence classification: module, integration contract and limits

Module: `manhattan/evidence.py` (metadata schema `manhattan.evidence/2`). Tests: `tests/test_manhattan_evidence.py`
(synthetic fixtures only). Status: **a pure classifier, not wired into any runner, ledger or attempt path, and
unable to authenticate anything today** (`TRUSTED_AUTHORITIES` is empty, so every classification is `unverified`).
It changes no scientific rule, threshold, pre-registration, e-process or e-LOND code, and adds no statistical test.

## What it decides

Six axes, each decided separately and never inferred from another:

| axis | values | decided from |
|---|---|---|
| provenance | `synthetic`, `historical_public`, `historical_licensed`, `captured_forward`, `unverified` | the closed metadata schema (source kind, vintage kind, capture block), with every required verifier result from a trusted authority and its facts equal to the metadata |
| reconstruction | set of `backfilled`, `late`, `conservative_assumption` (`unknown` when unverified) | capture counts, monitoring start vs span, the publication contract's availability kind |
| availability | `per_vintage_release`, `declared_daily_lag`, `first_seen_capture`, `conservative_assumption`, `generated`, `unknown` | the publication contract (`manhattan.availability.validate_source`) |
| role | `exploration`, `reserve`, `forward`, `embargo` | **computed** with `manhattan.roles.role_of` on every day of the span, from the fence, the spec's freeze **and the spec's holding period**; a supplied label may only agree |
| authorization | `exploration_open`, `reserve_designated_verified`, `forward_freeze_verified`, `unauthorized` | role, designation, `reserve.enabled` and the authoritative `runner_token` / `batch_freeze` results |
| eligibility | `none`, `infrastructure_validation`, `descriptive`, `reserve_screening_candidate`, `forward_candidate` | the axes above; provenance can only disqualify |

Every result has `forward_elond_eligible = False`, `screening_eligible = False` and `promotion_authorized = False`;
no input changes them. A *candidate* means only "not disqualified". `weight_ceiling` is the value of the unchanged
`manhattan.ledger.evidential_weight` table (ARCHITECTURE 6.3) for a candidate and 0 otherwise; `cap_weight` lowers
a recorded weight to it and never raises one. A forward candidate additionally needs an authoritative attempt
binding (verified window and attempt identity); a reserve candidate needs an authoritative runner token.

## Digests versus verified facts (S6 finding H2)

Two checks are made and kept apart:

- **Integrity (a digest).** Every `VerifierResult.subject` must equal `subject_digest(metadata)`, the SHA-256 of the
  canonical metadata. Anyone holding the metadata can compute it. It shows only that a result is about exactly
  these bytes, so an edit after verification is detected. It establishes no fact, and a mapping of digests is not
  accepted as a verification at all.
- **Authority (verified facts).** Facts are read only from `VerifierResult.facts` whose `authority` is in
  `TRUSTED_AUTHORITIES`. Each verifier must state exactly its fact set, and every fact must equal the metadata
  (same type and value), or the classification fails closed. Metadata alone never establish a fact.

| verifier | facts it must state | existing code that must produce it |
|---|---|---|
| `spec_registry` | `spec_hash`, `channel`, `domain`, `holding_periods` | the frozen spec in the registry |
| `batch_freeze` | `spec_hash`, `freeze`, `manifest_hash` | `manhattan.freeze.verify_frozen` (signed tag, manifest hash, external timestamp) |
| `runner_token` | `domain`, `window_id`, `manifest_hash` | a verified `roles.RunnerToken` naming this (domain, window) as unused and designated |
| `attempt_binding` | `attempt_id`, `spec_hash`, `window_id` | the registered, anchored attempt (Phase 4B, PR #86) |
| `capture_replay` | `source_id`, `capture_id`, `monitoring_start`, `backfill`, `late` | `manhattan.ops.data.first_seen` replay |
| `store_anchor` | `capture_id`, `anchor` | `manhattan.ops.store.verify_chain` against an independently retained anchor |
| `publication_contract` | `source_id`, `contract_sha256` | `validate_source` on the recorded source definition |
| `public_archive` / `licensed_snapshot` | `vintage_id`, `as_of` | the snapshot's SHA-256 (licensed: computed on the iMac, never in this repository) |
| `synthetic_generator` | `vintage_id` | the generator definition and seed |

Required: `spec_registry` always, plus `synthetic_generator` (synthetic); `publication_contract` and
`public_archive` / `licensed_snapshot` (historical); `publication_contract`, `capture_replay` and `store_anchor`
(captured forward). Forward-role spans also need `batch_freeze`, designated reserve spans `runner_token`, and
metadata naming an `attempt_id` `attempt_binding`. Results must be exactly this set: missing, extra, duplicate,
unknown or untrusted results fail closed.

**A forged freeze date no longer helps.** A forward role is computed from `spec.freeze`, and that date must equal
the authoritative `batch_freeze.freeze`. Metadata relabelled with an earlier freeze contradicts the verified fact
and fail closed (`test_forged_freeze_date_cannot_make_a_forward_candidate`).

## Holding-period embargo (S6 finding M1)

`spec.holding_periods` (whole number, 0 to 2,520) is required and must equal the authoritative
`spec_registry.holding_periods`. It is passed unchanged to `roles.role_of`, so the embargo is exactly that
function's: the last `holding + 1` business days before the reserve starts (`<=`) and before it ends (`<`). There
is no default. A missing, malformed or contradictory holding period fails closed. Tests compare the computed role
with `roles.role_of` at reserve-start and reserve-end edges for holding periods 0, 5 and 20, and pin the regression:
a span ending 10 business days before the reserve end is a reserve candidate for a 0-period spec and fails closed
(span crosses into the embargo) for a 20-period spec.

## Malformed inputs (S6 finding M2)

`config` must be `None` or a mapping; `config.reserve` and `config.claims`, when present, must be mappings whose
`enabled`, when present, is a boolean. `protocol_hash` must be `None` or a lowercase SHA-256. `fence` must be a
`roles.Fence` with a date `exploration_end`, boolean `enabled` and well-formed reserve windows. Anything else gives
`unverified`, weight 0. `classify` and `combine` never raise: an unforeseen exception inside also yields
`unverified` with only its type named. Seeded fuzz tests cover malformed configuration, promotion settings and
metadata mutations.

## Combining parts (S6 finding M3)

`Classification.identity` carries spec hash, channel, domain, freeze, holding period, window id, span and attempt
id (when given), and whether the window identity is verified. `combine` accepts only authenticated parts of **one**
spec (same spec hash, channel, domain, freeze, holding period) with the same provenance, role, licence,
availability and authorization. It rejects duplicates (same subject, same window, same attempt), overlapping spans,
and attempt identities present on some parts only. It keeps every part (`parts`, `subjects`) and takes the weakest
part's eligibility and ceiling. It never invents an attempt identity: absent attempt ids stay absent.

## Integration contract (for after PR #86 lands)

1. **Build `metadata` from persisted, anchored records only**:
   - the Store's capture record (source, SHA-256, schema-v2 definition, retrieval time);
   - the `FirstSeen` replay (monitoring start, backfill and late counts for exactly the observations in the span);
   - the spec registry (spec hash, channel, holding period);
   - the verified batch manifest (freeze);
   - the attempt start record (attempt id, declared evaluation window id).

   Never build it from file names, paths, environment variables, generator output or labels.
2. **Build each `VerifierResult` at the integration boundary**, only after the named verifier has succeeded on these
   records, with `subject = subject_digest(metadata)` and the facts read from the verifier's own output.
3. **Add an authority to `TRUSTED_AUTHORITIES` only in a reviewed change**, once that boundary exists.
   `manhattan/evidence.py` should then be added to the protected block of `.github/CODEOWNERS` (Ethan's edit; this
   PR cannot touch that file).
4. **Treat every `unverified`, every `none` and every `blockers` entry as refusal.** Record `cap_weight(c, w)`, never
   `w` alone. Never read `eligibility` as authorization.

**PR #86 compatibility requirements.** Checked against its head `060d4e3`. With this module and its tests copied
onto that head, `test_manhattan_evidence.py`, `test_manhattan_binding_access.py` and `test_manhattan_ops_attempts.py`
gave 338 passed, exit 0. `git merge-tree` showed no textual conflict. The integration needs from PR #86:

- `roles.role_of(day, domain, fence, freeze, holding)` keeps its signature and embargo semantics;
  `ledger.evidential_weight`, `availability.validate_source` and `ops.promotion.status` stay unchanged.
- The attempt start record's authorization (`freeze`, `holding`, declared window ids, fence snapshot) and identity
  (`spec_hash`, `channel`, `window`, `role`) are the source of `batch_freeze.freeze`, `spec_registry.holding_periods`
  and `attempt_binding.window_id`. A mismatch between that record and the frozen spec must fail closed, not be
  repaired.
- The attempt ID is the start record hash (64 lowercase hex). `attempt_binding` is minted only for an active or
  completed, non-superseded attempt in an anchored history (PR #86's `attempts.reconcile`).
- A forward-observation attempt is one night. Combining nights uses `combine` with one attempt per part, disjoint
  spans and distinct window ids.

**Gates that remain blockers in every forward candidate** (`UNIMPLEMENTED_GATES`), plus `promotion.status`:

- enrolment (Protocol v3.1 section 6.8);
- attempt binding wired to classified evidence;
- guard and test-period construction (sections 6.1-6.7);
- an adopted protocol hash and `claims.enabled: true` (both Ethan's).

This module has no switch for forward e-LOND eligibility.

## Limitations

- **Nothing is authenticated.** `TRUSTED_AUTHORITIES` is empty, so no result is accepted. Even after an authority
  is added, the `authority` field is a string in an ordinary Python object: any code in the same process can build
  one. The set is a code-review gate, not cryptography. Real authentication must come from the boundary that mints
  results: anchored stores, signed tags, the iMac's private snapshot manifests. The tests run under a **simulated**
  authority. They show the logic is right given authentic results, and nothing about whether any result is authentic.
- The integrity digest detects edits after verification, not lies at verification time.
- One call classifies one homogeneous span in one role. Signal warm-up history before a forward window (R-1) is not
  classified separately.
- Per-observation reconstruction is summarised by counts, which are trusted only as the `capture_replay` facts.
- The monitoring-start check allows one day either side of the first retrieval's UTC date (market-zone close).
- Session 1's files (`ledger.py`, `attempts.py`, `engine/pit.py`, `engine/evaluate.py`, `ops/runner.py`,
  `ops/store.py`, `ops/data.py`) are not modified. This module only imports `roles`, `availability`,
  `ledger.evidential_weight` and `ops.promotion`, read-only.
