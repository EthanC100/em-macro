# Phase 4B: binding attempt accounting, authorization and crash integrity

Status: **architecture and trust boundary** (written and committed before the implementation, as the brief
required). The implementation, the coverage matrix and the test evidence are appended in later sections of this
file once they exist; nothing below claims more than the code and its adversarial tests establish.

Starting point: main at `f5f8045` (PR #80 merged). Phase 4A-1a (`ATTEMPT_ACCOUNTING.md`) added an opt-in lifecycle
to the Manhattan `Ledger` (`evaluation_started`, linked completions, `attempt_failed`/`attempt_aborted`, retries by
`supersedes`) and a lifecycle-only reconciler that always answers `access_reconciled: false`. It did not touch data
access. This phase makes the lifecycle **binding** for protected data and extends accounting to the operational
`Store`.

No scientific rule changes here: no threshold, no protocol version, no decision rule, no evidential-weight rule, no
change to `looks()`, and no edit of a protected path (`.github/CODEOWNERS`) or of `config/manhattan.yaml`.

## 1. Trust boundary

What this phase can enforce is bounded by ARCHITECTURE §8. Stated plainly:

| claim | how it holds | where it stops |
|---|---|---|
| No Manhattan code path opens a reserve or forward window without a durable, active registered attempt | `Window` can be created only with a seal minted inside `manhattan.engine.pit`; protected seals are minted only for an `AttemptContext` whose start record is already durable in its authoritative store | In-process Python is not a security boundary against code that deliberately imports private names (`pit._open_window`, `pit._SEAL_KEY`). A static scan test pins the modules allowed to touch them, so a bypass must be explicit and reviewable |
| The window read is the window authorized | the seal binds store object, store version, dates, role, domain, caller, purpose, attempt ID and window ID; `dataclasses.replace` or direct construction fails; a store mutated after authorization refuses protected reads | reads of a `PitStore`'s private arrays (`_period`, `_value`, `_as_of`) from outside `pit`/`lookahead` are excluded by the same static scan, not by the language |
| Every protected statistical evaluation has a start, an identity and exactly one terminal | registration before exposure; terminals written by the context; the reconciler re-derives the lifecycle from the persisted, anchored records | a process that never runs Manhattan code (e.g. a notebook reading FRED directly) leaves no record: ARCHITECTURE §8 item 3 |
| Deletion or alteration of either store's history is detected | both hash chains are re-verified from immutable snapshots against **independently retained** anchors (record count + head hash) | an anchor that was not retained independently (or was retained by the same writer that can rewrite the chain) authenticates nothing; anchor custody is an owner decision (D-7) |

The exploration role stays open (ARCHITECTURE §6.1): exploration windows need no registration and exploratory reads
are not logged. Registration is optional for exploration evaluations; when present it binds them the same way.

## 2. Taxonomy: what is an attempt

Five kinds of action touch dated data. They are recorded differently and are never counted as one another.

| action | definition | recorded as | protected? |
|---|---|---|---|
| **Statistical attempt** | one execution of a fixed executable on one declared evaluation window, whose result is recorded as evidence or as a screening result | an attempt: start, identity, authorized windows, one terminal | yes for reserve/forward roles; optional for exploration |
| **Exploratory access** | a read of exploration-role dates for building, debugging or descriptive work | nothing (open by design) | no |
| **Operational diagnostic** | a run whose output is not a result: capacity/timing benchmarks, look-ahead perturbation tests, compiler checks | nothing; synthetic stores only (`PitStore(synthetic=True)`) when a protected role label is needed | refused for real data |
| **Retry** | a new execution of an attempt whose previous execution ended without a completion (crash, interruption) | a new attempt that names its predecessor (`supersedes` in the Ledger, `retry_of` in the Store); the predecessor is never erased | inherits |
| **Incremental forward observation** | the nightly runner's recomputation of a registered prediction over its forward window, emitting one record per new observation date | one **registered execution** per prediction per night; its per-date `observation` records are **repeated observations** linked to that execution | yes |

Counting units the reconciler reports, kept separate:

- **registered executions**: start records (each retry is one more);
- **distinct specifications**: distinct `spec_hash` among registered executions;
- **completed evaluation keys**: distinct `(spec_hash, data_hash, window id)` among completions, which is the existing
  `Ledger.looks()` definition, unchanged;
- **repeated observations**: forward `observation` records linked to completed executions;
- **independent statistical tests**: **not defined here**. Which unit (if any) enters a multiple-testing
  denominator is a scientific decision (D-1); the reconciler reports `independent_statistical_tests: null`.

A nightly forward execution is an access event and an accounting unit, not a hypothesis test: it does not change
`looks()`, any e-process, or any threshold.

## 3. Boundaries

**Registration boundary.** An attempt is registered when its start record is durable in its authoritative store:
for the `Ledger`, appended, flushed and `fsync`ed; for the `Store`, written through the journal and verified on the
remote (`Store.write` returns only after the `verified` journal line is pushed). Registration validates the whole
identity and every declared window **before** writing; an invalid declaration writes nothing.

**Execution boundary.** Protected exposure begins when a sealed `Window` is minted for a protected role. Minting
requires an `AttemptContext` that (a) is bound to a durable start, (b) is still active (no terminal, not
superseded), (c) declares the window, and (d) re-validates the window against the fence, data identity and role at
the moment of opening. Loading a `PitStore` or hashing it is not exposure: no value reaches a strategy except
through a `Window`.

## 4. Attempt identity

Mandatory for every new registered attempt (`attempt_schema: 2`):

| field | rule |
|---|---|
| `executable`, `variant`, `hypothesis`, `family`, `batch` | non-empty strings (spec IDs; `batch` is the frozen batch, or `pre-freeze` for screening) |
| `role` | `exploration`, `reserve` or `forward`; equals the role of the declared evaluation window |
| `channel` | `blind` or `adaptive` |
| `designated` | boolean |
| `spec_hash`, `data_hash` | lowercase 64-hex SHA-256; `data_hash` equals the declared windows' data identity |
| `window` | `{id, start, end, frequency}`; equals the declared evaluation window |
| `code_version` | the existing retry code-identity contract, now required for every new attempt: a full Git commit (40/64 hex, not all zeros) **and** a content digest (`tree` or `engine_sha256`). When the engine evaluates, the running engine's `code_version()` must equal the registered one |

Attempt ID: in the `Ledger`, the start record's hash (as in 4A-1a). In the `Store`, the SHA-256 of the canonical start
payload, which carries a 128-bit nonce and the run identity; the reconciler recomputes it, so an ID cannot be
re-pointed at another identity.

**Role escalation is impossible by construction:** the completion must equal the start on every identity field
(including `role`, `designated`, `channel`, `window`, `data_hash`, `code_version`); a context opens only its declared
windows; and a declared window's role is re-derived from the fence when opened. Legacy starts (no
`attempt_schema`) stay readable and keep their old behaviour, and are never certified.

## 5. Declared windows and their validation

Each attempt declares its windows: `{id, domain, start, end, role, purpose, data_hash}` with `purpose`
`evaluation` (exactly one, equal to the identity's window) or `signal_warmup` (forward observation only, at most
one, ending the day before the evaluation window and in the same domain and data identity). Validation:

- **exploration / reserve evaluation windows:** the declared role must equal `roles.check_read(caller, domain, start,
  end, fence, freeze, holding, token, window_id)`, the existing fence check, unchanged and never relaxed (reserve
  still needs the runner, an enabled reserve, a verified token naming this designated `(domain, window)`).
- **forward evaluation windows of the engine:** `check_read` must return `forward` (runner, after the freeze).
- **forward-observation windows of the ops runner (the R-1 adapter):** `check_read` cannot be used (one role per
  read; dates between the exploration cut-off and the freeze are embargo). The adapter keeps its R-1 semantics and is
  strengthened: the evaluation segment must lie after the exploration cut-off and, unless after the freeze, outside
  every configured reserve window and its embargo margin; the warm-up segment must not overlap any configured reserve
  window or margin (fail closed, D-3). No current configuration has a reserve window, so no current run changes.
- **data identity:** at registration the declared `data_hash` is the hash of the store that will be read; at opening
  the store's hash must still match, and protected windows refuse reads once the store has been mutated.
- **PIT restrictions** stay where they are: reserve evaluation still requires historical (non-reconstructed)
  evidence, forward engine evaluation still refuses store-wide reconstruction, ops observations keep per-observation
  provenance and their existing weight rule.

## 6. Lifecycle

```
            register (durable)            open declared window(s)          completion (+ result, atomically)
 (none) ─────────────────────▶ ACTIVE ───────────────────────────▶ ACTIVE ─────────────────────────────▶ COMPLETED
                                 │  └── failed / aborted (classified reason, data_read flag) ──────────▶ FAILED / ABORTED
                                 └── process dies ──▶ UNFINISHED ── recovery ──▶ (Ledger) superseded by a retry, stays unfinished
                                                                              └▶ (Store) aborted: interrupted, then retried with retry_of
```

Terminals carry only a fixed reason class (`execution_error`, `data_unavailable`, `interrupted`, `cancelled`,
`validation_error`) and `data_read` (whether any value was read through the attempt's windows). No exception text and
no result value enters a terminal. A failed or aborted attempt is never counted as a completed evaluation, whether or
not its window was read; `data_read` separates "failed before exposure" from "failed after exposure".

## 7. Transactional semantics

**Ledger (engine).** One JSONL file, single writer. The completion record *is* the result (`evaluation`, `rerun` or
`nondeterminism` with `result_hash`, `summary`, `evidential_weight`), so terminal and result are one line and cannot
diverge. Appends are flushed and `fsync`ed. A crash mid-append leaves a torn final line; `Ledger` refuses to open
it (unchanged), and `recover_torn_tail` moves only an incomplete, unparseable, newline-less final fragment to a
side file, never a complete record. The interrupted attempt then shows as unfinished and is retried with
`supersedes`.

**Store (ops).** Every write already goes through the journal (`pending` pushed, then records + `committed`, then
`verified`). Attempt accounting uses that unchanged:

1. all starts of a run's executions in one journalled write, verified on the remote **before** any protected
   window is opened;
2. computation in memory;
3. all result records (`observation`, `missed_observation`, `screening`) **and** their attempts' terminals in one
   journalled write. A crash at any stage either leaves the pending entry, which `reconcile` finishes at the next
   run (results and terminals together), or leaves nothing, in which case the starts remain unfinished.

Terminal records use one key per attempt (`("attempt_terminal", id)`), so the Store's own idempotency rule makes a
second, different terminal a `conflict` record instead of a second terminal. Result idempotency is the existing
key rule: a re-execution that reproduces an existing observation is a `duplicate` (no new evidence); a different value
is a `conflict` and the first record stands. The terminal lists each linked result key, its content hash and its
disposition (`new`, `duplicate`, `conflict`), so the reconciler can check the linkage.

## 8. Recovery

- **Store:** `nightly` runs `open → journal reconcile → lock → attempt recovery → …`. After the lock is held no
  other run is live (a live lock stops the run; an expired one is broken), so every unfinished attempt of another
  `(run_id, run_attempt)` is stale and is closed with `attempt_aborted: interrupted` in one write. A later execution
  with an identical identity names it in `retry_of`. Nothing is erased; journal recovery and idempotency are
  unchanged.
- **Ledger:** unchanged 4A-1a semantics: a retry names the unfinished start in `supersedes`, must match its identity
  and code identity exactly, and the superseded start stays unfinished and counted.

## 9. Reconciliation

`attempts.reconcile(...)` audits immutable snapshots of either or both authoritative stores, each against an
independently retained anchor `{records, head}` that marks an **authenticated batch boundary**: only the prefix up to
the anchor is audited; records after it are counted as outside the boundary. Integrity failures (broken chain,
anchor mismatch, missing file) raise. Accounting failures are reported as violation codes with store and sequence
numbers only (no values). It detects:

- protected completions/observations with no registered attempt, or created before their attempt's start;
- missing or malformed identities, attempt IDs that do not recompute, contradictory identities;
- invalid role transitions (completion differs from start; declared window role inconsistent with the recorded fence
  snapshot; protected window without authorization);
- missing terminals (unfinished attempts at the boundary), duplicate or contradictory terminals;
- invalid retries (unknown, completed, non-interrupted or doubly-retried predecessor; identity mismatch);
- result linkage mismatches (linked key missing, wrong content hash, `new` result not written by the attempt's run,
  result outside the start..terminal span);
- evidential-weight inconsistencies, recomputed with `ledger.evidential_weight` and the runner's existing
  eligibility gate (factored into one function, rules unchanged);
- attempt IDs registered in both stores (cross-store collision).

`access_reconciled` is `true` only if: every supplied store verified against its anchor, there are no violations,
no unfinished attempts, no legacy (pre-schema-2 or pre-epoch) protected records in the boundary, and every protected
result is linked. It speaks only for the stores supplied (`stores_covered`) and for Manhattan code paths (section 1).

The pass is linear in the number of records (dictionaries keyed by attempt ID and record key). The `Ledger`'s
in-memory lifecycle queries, which 4A-1a computed by rescanning (quadratic over a run), are indexed.

## 10. Unresolved scientific and owner decisions

Work affected by each is stopped or kept fail-closed; nothing below is decided by this phase.

| # | decision needed | what this phase does meanwhile |
|---|---|---|
| D-1 | Which counting unit (registered executions, distinct specifications, completed keys) enters any multiple-testing denominator, and how retries and failed-after-read attempts count | reports all units separately; `independent_statistical_tests: null`; `looks()` unchanged |
| D-2 | Confirm that a nightly forward execution is an accounting unit, not a test, and that its observations are repeated observations of one registered prediction | implemented that way; no statistical consumer changed |
| D-3 | May a forward strategy's signal warm-up read dates inside (or in the embargo margin of) a configured reserve window? | refused (fail closed); no reserve window is configured today |
| D-4 | Disposition of legacy records (pre-schema-2 starts, unlinked completions, pre-epoch observations): may certification start at an accounting epoch? | readable, counted, never certified; their presence keeps `access_reconciled` false |
| D-5 | Should the low-level `Ledger.record_evaluation` refuse unlinked reserve/forward writes outright? (Existing fixtures and tests use it directly.) | the engine boundary (`evaluate`, `Window`) refuses; the storage API stays compatible; the reconciler flags any unlinked protected record |
| D-6 | ARCHITECTURE §6.2 "one designated evaluation per (batch, domain), then retired" is not enforced by any writer | not enforced (a scientific rule); the reconciler reports designated reserve completions per `(batch, domain)` without judging them |
| D-7 | Custody of anchors: which independent record (public `run_summary`, health `ledger_head`, external timestamp, mirror) authenticates each batch boundary | the reconciler requires an anchor argument and verifies it; it cannot know where the caller got it |
