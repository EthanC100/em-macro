# Evidence classification: module, integration contract and limits

Module: `manhattan/evidence.py`. Tests: `tests/test_manhattan_evidence.py` (synthetic fixtures only).
Status: **a pure classifier, not wired into any runner, ledger or attempt path.** It changes no scientific rule,
threshold, pre-registration, e-process or e-LOND code, and it adds no statistical test.

## What it decides

Six axes, each decided separately and never inferred from another:

| axis | values | decided from |
|---|---|---|
| provenance | `synthetic`, `historical_public`, `historical_licensed`, `captured_forward`, `unverified` | the closed metadata schema (source kind, vintage kind, capture block), with every required verifier bound to the metadata |
| reconstruction | set of `backfilled`, `late`, `conservative_assumption` (`unknown` when unverified) | capture counts, monitoring start vs span, the publication contract's availability kind |
| availability | `per_vintage_release`, `declared_daily_lag`, `first_seen_capture`, `conservative_assumption`, `generated`, `unknown` | the publication contract (`manhattan.availability.validate_source`) |
| role | `exploration`, `reserve`, `forward`, `embargo` | **computed** with `manhattan.roles.role_of` on every day of the span, from the fence and the spec's freeze; a supplied label may only agree |
| authorization | `exploration_open`, `reserve_designated_verified`, `forward_freeze_verified`, `unauthorized` | role, designation, `reserve.enabled` and the bound `runner_token` / `batch_freeze` verifications |
| eligibility | `none`, `infrastructure_validation`, `descriptive`, `reserve_screening_candidate`, `forward_candidate` | the axes above; provenance can only disqualify |

Every result also carries `forward_elond_eligible = False`, `screening_eligible = False` and
`promotion_authorized = False`. No input can change them: a *candidate* means only "not disqualified by
provenance". `weight_ceiling` is the value of the existing `manhattan.ledger.evidential_weight` table
(ARCHITECTURE 6.3) for a candidate and 0 otherwise; `cap_weight` lowers a recorded weight to it and never raises
one. `evidential_weight` itself is unchanged (pinned by `test_existing_evidential_weight_table_unchanged`).

Rules the tests pin:

- Synthetic evidence validates infrastructure, never market performance, on any dates.
- Historical licensed data on post-freeze dates are `historical_licensed`, `descriptive`, weight 0: a recent date
  or a later vendor snapshot is not captured forward evidence.
- A designated blind reserve evaluation on per-vintage historical data is at most a screening candidate, never
  independent forward confirmation.
- Captured forward with any backfill, late mark or conservative availability is `descriptive`, weight 0, with the
  reason listed. A span that starts before monitoring began but reports no backfill fails closed.
- Captured forward, genuine, after a verified freeze is a `forward_candidate` carrying the blockers listed below,
  even with `claims.enabled: true` and a protocol hash supplied.
- Mixed provenance, mixed role or a failed part in `combine` fails closed; otherwise `combine` takes the weakest part.
- Unknown fields (including `evidential_weight`, `eligible`, `filename`, `provenance`, `tier`), missing fields,
  invalid publication contracts, inconsistent dates, non-SHA-256 or mismatched capture/vintage identities, wrong
  capture schema version, forged role or provenance labels, `designated` outside the reserve, missing, unbound or
  unknown verifications and non-JSON input all give `unverified` / `none` / weight 0 with the problem stated.

## Integration contract (for after Session 1's attempt accounting lands)

The classifier is called with `classify(metadata, verifications, fence=..., config=..., protocol_hash=...)`.

**Required authenticated inputs.** The integration, not the caller's data, must build both arguments:

1. `metadata` (schema `manhattan.evidence/1`) from persisted records only: the capture record's payload and
   provenance in the operational Store (source id, SHA-256, schema-v2 source definition, retrieval time), the
   `FirstSeen` replay (monitoring start, backfill and late counts for exactly the observations in the span), the
   spec registry (spec hash, channel) and the verified batch manifest (freeze date). Never from file names, paths,
   environment variables, generator output or a session's labels.
2. `verifications`: a mapping verifier name to `subject_digest(metadata)`, each entry added **only** after the
   named existing verifier has succeeded on that metadata in the same process:

   | verifier | existing code it must come from |
   |---|---|
   | `synthetic_generator` | the generator definition and seed (`manhattan.ops.data` synthetic source) |
   | `publication_contract` | `manhattan.availability.validate_source` on the recorded source definition |
   | `public_archive` | SHA-256 of the archived public snapshot |
   | `licensed_snapshot` | SHA-256 manifest of the private licensed snapshot, computed on the iMac; nothing licensed enters this repository |
   | `capture_replay` | `manhattan.ops.data.first_seen` (raw hash, byte count, schema-v2 definition checks) |
   | `store_anchor` | `manhattan.ops.store.verify_chain` against an independently retained head anchor |
   | `batch_freeze` | `manhattan.freeze.verify_frozen` (signed tag, manifest hash, external timestamp) |
   | `runner_token` | a verified `manhattan.roles.RunnerToken` naming this (domain, window) as unused and designated |

3. The attempt binding from Session 1's interface (when it exists): the attempt ID the observations belong to,
   verified against the anchored ledger, so that a classification cannot be applied to an unregistered or
   superseded attempt. The classifier does not take an attempt today; the binding must be added as a further
   required verifier and test, not inferred.

**Safe failure behaviour.** `classify` never raises on bad input; it returns `unverified` with `problems`.
Callers must treat `unverified`, `none` and every `blockers` entry as refusal, must record `cap_weight(c, w)` and
never `w` alone, and must never read `eligibility` as authorization. A classifier exception (a bug) must abort the
attempt as `validation_error`, not default to any class.

**Gates that remain blockers in every forward candidate** (`UNIMPLEMENTED_GATES`), plus `promotion.status`:

- enrolment (Protocol v3.1 section 6.8: enrolled at the first review as Promising or higher);
- attempt binding (each observation tied to a registered, anchored attempt);
- guard and test-period construction (Protocol v3.1 sections 6.1-6.7) wired to classified evidence;
- an adopted protocol hash in `manhattan/ops/promotion.py` and `claims.enabled: true` (both Ethan's).

Forward e-LOND eligibility may only be made reachable by a later, reviewed change that implements these gates,
after Ethan adopts the protocol; this module has no switch for it.

## Limitations

- **It does not authenticate.** It checks that the required verifications exist, are bound to exactly this
  metadata (any later edit breaks the binding) and are consistent. A caller can mint a binding without running the
  verifier; the module cannot detect that. The damage is bounded: no result grants eligibility, raises a weight or
  authorizes promotion.
- One call classifies one homogeneous span in one role. Signal warm-up history read before a forward window
  (`forward_window`, OPS_PROGRESS R-1) is not classified separately; reconstruction counts must cover the
  recorded observations, and warm-up provenance is the integration's to bind.
- Per-observation reconstruction is summarised by counts; the module trusts the replay's counts once bound.
- The monitoring-start check allows one day either side of the first retrieval's UTC date (market-zone close).
- Not wired into `manhattan/ledger.py`, `attempts.py`, `engine/pit.py`, `engine/evaluate.py` or `ops/runner.py`,
  `ops/store.py`, `ops/data.py` (Session 1's files); it only imports from them read-only where noted.
