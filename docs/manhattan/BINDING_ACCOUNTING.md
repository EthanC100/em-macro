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

What this phase can enforce is bounded by ARCHITECTURE §8. **The intended guarantee is correct behaviour through the
supported Manhattan APIs.** It is not a sandbox. Stated plainly:

- **PIT window authorization is not a general-purpose data-access sandbox.** It controls how Manhattan code turns a
  `PitStore` into values a strategy sees. It does not control the store's own memory, the raw capture files
  (`raw/<sha256>.bin` in the private Store clone), the public FRED source, the em-macro-data clone, or any code that
  reads those directly. Raw captures and the Store's files have their own access controls (who holds the private
  repository and its deploy key), which this phase neither changes nor certifies.
- **Deliberate hostile Python code is outside the structural boundary.** Code in the same process can import private
  names (`pit._open_window`, `pit._GRANTS`, `pit._SEAL_KEY`, `access._PROOF_KEY`), edit module state, or write files
  directly. An AST scan test pins which Manhattan modules may touch the private access names, so a bypass inside
  Manhattan must be explicit and reviewable. A writer holding a store's credential (the Ledger file, the Store's
  deploy key) can write any hash-valid record; only the reconciler can detect what such a writer does, and only
  as far as the records are internally inconsistent.
- **A caller-supplied `synthetic=True` does not prove provenance.** `PitStore(synthetic=True)` is a declaration by the
  code that builds the store. It confines `diagnostic_window` to stores so declared and keeps diagnostic windows out
  of every evaluation and observation path; it does not make a store synthetic.
- **Public Store and Ledger APIs** refuse evidence and attempt records unless they come through `manhattan.access`
  (sealed writes, completion proofs), but they are not an authentication boundary against a holder of the credential.

| claim, through supported APIs | how it holds | where it stops |
|---|---|---|
| No reserve or forward window is opened without a durable, active registered attempt | a `Window` is minted only inside `pit` (seal over every field), for an `AttemptContext` whose start is durable; reserve tokens are bound to batch, specification and window | private names, as above |
| A protected window reads only while its attempt is registered and active | every read re-checks the attempt (liveness on the shared read meter), the store version, and that the object is the one minted here, unchanged, in this process; copies, deep copies, pickling, `object.__setattr__` widening and fork inheritance are refused | the liveness check sees the attempt's own `Ledger`/`Store` object in this process; another process's terminal is enforced at write time (Store lock compare-and-swap; single-writer Ledger) and by reconciliation |
| A terminal's `data_read` is true whenever a value was read | reads are counted before any value leaves, and refused after the terminal | as above |
| Every protected statistical evaluation has a start, an identity and exactly one terminal | registration before exposure; protected completions need a one-use completion proof (Ledger) or a sealed, linkage-checked commit (Store) | a process that never runs Manhattan code leaves no record (ARCHITECTURE §8 item 3) |
| A recorded result's computed values are those of the attempt's own computation | Ledger: the completion proof is minted by `engine.evaluate` for the result hash of the backtest it ran. Store (S7 N2): `access.run_bound` runs the strategy over the attempt's own window and binds the result; `completion` refuses any observation whose `net`, `gross`, `cost`, `turnover` or `exposure` differ from that result at its date, and any screening record whose `result_hash` or `summary` differ | **narrow:** an observation's provenance fields (`reconstructed`, and through it the weight) are derived by runner code from first-seen captures and are **not** bound to the capture records here; eligibility, registration status and weight are re-checked against the registration by the reconciler. Activation gate G-1 (section 18) |
| Deletion or alteration of either store's history is detected | chains re-verified from immutable snapshots against a supplied anchor `{records, head}` | a supplied anchor is not independent custody (D-7, section 10) |

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

**A failure (not a crash) while the results are being written** (S7 N8): `access.commit_results` first settles
that write before any other terminal may be written for those attempts. It resets the clone to the remote,
dropping any half-applied local state.
- If the results entry reached the remote journal, it is finished now, or by the next run's journal recovery, which
  runs under the lock before attempt recovery. Its completions are then those attempts' only terminals: no failed
  terminal is written for them in this process.
- Only if the entry provably never left the process are the attempts closed as `failed: execution_error`, with
  nothing of that evaluation written.
- If the state cannot be determined, nothing is written and the next run's journal recovery and attempt recovery
  decide.

The same path serves the nightly forward observations and screening.

Terminal records use one key per attempt (`("attempt_terminal", id)`), so the Store's own idempotency rule makes a
second, different terminal a `conflict` record instead of a second terminal (and, since the S7 correction, the
public `Store.write` refuses an unsealed terminal outright, while any conflict on an evidence or attempt record makes
the history unreconciled). Result idempotency is the existing
key rule: a re-execution that reproduces an existing observation is a `duplicate` (no new evidence); a different value
is a `conflict` and the first record stands. The terminal lists each linked result key, its content hash and its
disposition (`new`, `duplicate`, `conflict`), so the reconciler can check the linkage.

## 8. Recovery

- **Store:** `nightly` runs `open → journal reconcile → lock → attempt recovery → …`. After the lock is held no
  other run is live (a live lock stops the run; an expired one is broken), and this process has not registered
  anything yet, so every unfinished forward-observation attempt is a dead process's (whatever run identity it
  carries: a local rerun can reuse one) and is closed with `attempt_aborted: interrupted` (`data_read` unknown) in
  one write. A later execution with an identical identity names it in `retry_of`. Nothing is erased; journal
  recovery and idempotency are unchanged. Screening takes no lock, so interrupted screening attempts are closed by
  an operator (`access.recover_interrupted(store, kinds=("screening",))`) while no screening runs.
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
- result linkage mismatches (linked key missing, wrong content hash, `new` result not written by the same writer
  as its terminal, i.e. in the same journal entry, result outside the start..terminal span);
- evidential-weight inconsistencies, recomputed with `ledger.evidential_weight` and the runner's existing
  eligibility gate (factored into one function, rules unchanged);
- attempt IDs registered in both stores (cross-store collision).

**What `access_reconciled: true` means, exactly.** For the stores supplied (`stores_covered`) and the boundary each
anchor marks: both chains verified; each reached the supplied anchor; the audit found no violation of any code above
(including conflicts on evidence or attempt records, results outside their attempt's identity or window, reused
designations); no attempt is unfinished; no legacy protected record (pre-schema-2 start, unlinked or pre-epoch
protected result) is in the boundary; and every protected result is linked to the completion of a registered
attempt. It is a statement about the records' internal consistency **checked against the supplied anchors**. It
does not say the anchors were independently held (`assurance.independently_anchored` is always false until custody is
configured, D-7), that the records' writer was honest beyond what consistency shows, or anything about reads
outside Manhattan code. `independent_statistical_tests` stays `null` until it is scientifically defined (D-1).

Three assurance levels are reported separately and never conflated:

| level | meaning | where |
|---|---|---|
| internally consistent | the hash chain verifies | `ledger.verify`, `ST.verify_chain`, `assurance.internally_consistent` |
| checked against a supplied anchor | the chain reaches `{records, head}` given by the caller | `assurance.checked_against_supplied_anchor` |
| independently anchored and certified | the anchor's custody is independent of the stores' writing credential | **not configured**: `assurance.independently_anchored` and `independently_certified` are always `false` |

The pass is linear in the number of records (dictionaries keyed by attempt ID and record key). The `Ledger`'s
in-memory lifecycle queries, which 4A-1a computed by rescanning (quadratic over a run), are indexed.

## 10. Scientific and owner decisions

Work affected by an open decision is stopped or kept fail-closed. Decisions taken by the owner in the S1 correction
round (after the S7 audit) are marked **decided**.

| # | decision | status and what the code does |
|---|---|---|
| D-1 | Which counting unit (registered executions, distinct specifications, completed keys) enters any multiple-testing denominator, and how retries and failed-after-read attempts count | open: all units reported separately; `independent_statistical_tests: null`; `looks()` unchanged |
| D-2 | Confirm that a nightly forward execution is an accounting unit, not a test | open: implemented that way; no statistical consumer changed |
| D-3 | May a forward strategy's signal warm-up read dates inside (or in the embargo margin of) a configured reserve window? | open: refused (fail closed); no reserve window is configured today |
| D-4 | Disposition of legacy records: may certification start at an accounting epoch? | open: readable, counted, never certified; their presence keeps `access_reconciled` false |
| D-5 | Must protected completions require a registered attempt and a completion path that establishes authorization and accounting? | **decided (yes)**: `Ledger.record_evaluation` writes a reserve/forward completion only with the attempt's one-use completion proof (minted by `engine.evaluate` after a read); `Ledger.append` refuses lifecycle types; `Store.write` refuses evidence and attempt types unless sealed by `manhattan.access`, whose results commit checks linkage. Historical records stay readable and are never certified |
| D-6 | One designated reserve evaluation per (batch, domain) | **decided (enforce conservatively)**: a reserve attempt is always the designated evaluation of its (batch, domain); non-designated reserve attempts are refused at registration (S7 N1). A second reserve registration of any kind for a (batch, domain) is refused unless it retries (`supersedes`) the one unfinished earlier attempt. The reconciler reports any non-designated reserve attempt (`non_designated_reserve_attempt`) and any second reserve attempt or completion (`designated_reserve_reused`), forged histories included |
| D-12 | Configuration of the hash-locked runner | **decided (adopt a hash-pinned PyYAML)**: `pyyaml==6.0.3` is added to `requirements-manhattan-runner.lock` with the SHA-256 of its CPython 3.12 manylinux wheel; the hash was checked against PyPI's published digest and against two independent downloads. The fence comes only from `config/manhattan.yaml`, read with `yaml.safe_load` and verified against its pinned identity: byte-identical to the file at the attempt's registered commit, and to an explicit SHA-256 pin when one is given (`--config-sha256` / `MANHATTAN_CONFIG_SHA256`). A caller can no longer inject a fence into the runner. A missing, unparseable or mismatched configuration fails closed before any attempt is registered. Forward attempts record the configuration's SHA-256, which the reconciler requires |
| D-13 | Designation consumption | **decided (never released)**: a designated reserve attempt consumes its (batch, domain) designation however it ends, **even if it failed or was aborted before any protected read**; the designation is never released or recycled |
| D-7 | Custody of anchors | **decided (no false certification)**: an anchor held by the same writing credential is not independent. No independent custody is configured, so the reconciler reports `checked_against_supplied_anchor` only and never `independently_certified`. No external service is implemented |

---

# Implementation (appended after the architecture commit)

## 11. What was built

| module | change |
|---|---|
| `manhattan/engine/pit.py` | `Window` sealed (HMAC over every field, store identity and version, attempt and purpose, with a per-process key); `AccessError`; `Reader(attempt=...)` refuses reserve/forward reads without an attempt even when `check_read` allows them; protected windows refuse reads after the store changes; `PitStore(synthetic=True)` and `diagnostic_window` for diagnostics; a read meter per authorization |
| `manhattan/access.py` (new) | `AttemptContext`, `DeclaredWindow`, declaration checks (identity, windows, fence, D-3), `register_evaluation` (Ledger), `register_store_attempts`, `completion`, `terminal_intent`, `recover_interrupted` (Store), `check_recorded` (the reconciler's re-validation from the recorded fence snapshot) |
| `manhattan/ledger.py` | `IDENTITY_FIELDS`, `validate_attempt_identity`, `require_code_identity` (old name kept), `same_identity`; schema-2 starts keep `kind` and `authorization`; terminals of schema-2 attempts state `data_read`; implicit completion of a schema-2 start refused; appends `fsync`ed; lifecycle indexes (no rescans); `recover_torn_tail`; `forward_observation_weight` (the runner's existing rule, moved, unchanged) |
| `manhattan/engine/evaluate.py` | `attempt=`; protected or attempt-bound windows need the matching attempt; identity and running code checked before computing; classified terminals on refusal, error or interruption; diagnostic windows refused |
| `manhattan/ops/runner.py` | after the lock: recovery of interrupted forward attempts and the accounting epoch record; one forward-observation attempt per prediction per night, verified on the remote before any window opens; observations and terminals in one journalled write; failures close attempts with a reason class only; `screen` registers screening attempts the same way; `code_identity` fails closed |
| `manhattan/ops/data.py` | `forward_window(attempt, pit)`: the R-1 adapter opens only for a registered forward-observation attempt |
| `manhattan/ops/capacity.py` | synthetic diagnostic windows instead of the forward adapter |
| `manhattan/ops/blinding.py` | two public health counts: `attempts_registered`, `attempts_recovered` (integers only) |
| `manhattan/attempts.py` | `reconcile` over both stores; `reconcile_lifecycle` accepts schema-2 records (its legacy behaviour is unchanged) |

Behaviour that changed for existing callers (each is the binding rule, not a side effect):

- A reserve or forward `Window` cannot be built directly; three existing tests that did so now open it through a
  registered attempt, with the same assertions (`test_manhattan_pit_phase3b.py`, `test_manhattan_pit_phase3c.py`).
- A nightly run with predictions to observe needs a known code identity: the CLI passes `GITHUB_SHA`; the runner
  test fixture now passes a fabricated valid-format commit, as the end-to-end fixtures already did. The all-zero
  default fails closed before any window opens.
- A same-day rerun adds no evidence but is a second registered execution; `test_rerun_on_the_same_day_adds_nothing`
  now checks exactly that, and that every result of the rerun is a `duplicate`. The end-to-end recovery test compares
  evidence excluding attempt records (IDs carry a nonce; a crashed cycle has more executions) and reconciles both
  histories.

## 12. Data-access coverage matrix

| access path | roles | before 4B | after 4B | adversarial test(s) |
|---|---|---|---|---|
| `pit.Reader.window` without attempt | exploration | `check_read` | `check_read`; reserve/forward refused even when the fence allows | `test_reserve_read_needs_a_registered_attempt_even_with_a_valid_token`, `test_forward_read_needs_a_registered_attempt`, `test_existing_role_fences_still_refuse_first` |
| `pit.Reader.window(attempt=)` | any | n/a | `check_read`, then the attempt's declared window, caller, fence, freeze, holding and token | `test_an_exploration_attempt_cannot_open_reserve_or_forward_dates` |
| `AttemptContext.window` | engine: any; screening: exploration | n/a | active attempt, data identity, role re-derived from the fence | `test_data_identity_is_checked_when_opening_and_while_reading`, `test_reserve_designated_evaluation_and_its_report` |
| `data.forward_window` / `AttemptContext.forward_window` (R-1, warm-up) | forward | unchecked adapter | registered forward-observation attempt; strengthened R-1; warm-up never in a configured reserve (D-3) | `test_forward_adapter_needs_a_forward_observation_attempt`, `test_observations_need_an_active_forward_attempt`, `test_warmup_overlapping_a_configured_reserve_is_refused` |
| `Window(...)`, `dataclasses.replace`, forged seal | any | allowed | refused | `test_windows_cannot_be_constructed_or_copied` |
| `copy.copy`, `copy.deepcopy`, `pickle`, `object.__setattr__`, a forked child, spawn | any | allowed (S7 H3) | refused at copy/serialize time, or at the next read | `test_windows_cannot_be_copied_serialized_or_altered`, `test_a_forked_child_cannot_read_an_inherited_window` |
| reading a window after its attempt ended (abort, failure, completion, retry, recovery) | reserve, forward, attempt-bound exploration | allowed (S7 H2) | refused at every read | `test_no_read_after_abort_and_data_read_stays_true`, `test_no_read_after_any_ending`, `test_store_window_reads_only_while_its_attempt_is_active` |
| `Ledger.append` of lifecycle types | any | allowed (S7 M4/M5) | refused | `test_storage_api_refuses_escalated_or_implicit_completion` |
| `Store.write` of evidence or attempt types | any | allowed (S7 M2/M5) | refused unless sealed by `manhattan.access` | `test_evidence_and_attempt_records_need_access_sealing`, `test_contradictions_through_the_public_api_are_refused` |
| `pit.diagnostic_window` (`ops/capacity.py`) | any label | used the forward adapter | synthetic stores only; never evidence | `test_diagnostic_windows_are_synthetic_only_and_never_evidence`, capacity tests |
| `lookahead.tampered_after` / `shifted` | copies of a store | unchanged | unchanged; a copy's data identity differs, so it cannot be opened under an attempt | `test_a_tampered_lookahead_copy_cannot_be_opened_under_the_attempt`, existing look-ahead tests |
| `engine.evaluate` | any | recorded only | protected needs its attempt, identity and running code; classified terminals | `test_completion_cannot_escalate_designation_or_identity`, `test_wrong_ledger_or_running_code_is_refused`, `test_failures_are_classified_and_never_completed` |
| `runner.observation_intents` | forward | adapter | attempt required | `test_forward_night_registers_before_reading_and_reconciles`, `test_observations_need_an_active_forward_attempt` |
| `runner.screen` | exploration | Reader | registered screening attempts, linked results | `test_screening_is_registered_and_linked`, end-to-end |
| `factors/reproduce.py` | exploration | Reader + evaluate | unchanged (open exploration, unregistered by design) | `test_manhattan_factors.py`, `test_exploration_stays_open_and_unregistered_exploration_is_not_a_violation` |
| `Ledger.record_evaluation` called directly | reserve, forward | allowed (S7 M5) | refused without the attempt's one-use completion proof (D-5) | `test_storage_api_refuses_escalated_or_implicit_completion`, `test_completion_proofs_are_single_use_bound_and_require_a_read` |
| `Ledger.record_evaluation` called directly | exploration | allowed | allowed; implicit completion of a registered attempt refused | `test_storage_api_refuses_escalated_or_implicit_completion` |
| private names (`_open_window`, `_SEAL_KEY`, `_as_of`, `_store`, `_value`, `_period`, `_CTX_KEY`, `Window(`) | any | convention | pinned to named modules by an AST scan | `test_private_access_paths_are_used_only_where_allowed` |
| code outside Manhattan (em_macro, nightshift explorer, notebooks) | n/a | out of scope | out of scope (ARCHITECTURE §8 item 3); the Q019 loader and sandbox are untouched | Q019 suites |

## 13. Crash and recovery guarantees

| store | crash point | state left | recovery | evidence of it |
|---|---|---|---|---|
| Ledger | after the start append returned | start durable (fsync), unfinished | retry with `supersedes`; the old start stays counted | `test_crash_after_registration_then_retry` |
| Ledger | inside the completion append | torn final line; `Ledger` refuses to open | `recover_torn_tail` quarantines only one partial record (never a complete or mid-file record); retry | `test_crash_during_result_commit_is_recovered_without_losing_the_start`, `test_torn_tail_recovery_never_removes_a_complete_or_mid_file_record` |
| Ledger | refusal, error, interruption while computing | `attempt_failed` / `attempt_aborted` with a reason class and `data_read` | none needed | `test_failures_are_classified_and_never_completed` |
| Store | after the starts' write, before results | starts verified on the remote, unfinished | next run (lock held): `aborted: interrupted`, then `retry_of` | `test_crash_after_registration_is_recovered_then_retried`, `test_a_rerun_with_the_same_run_identity_still_recovers` |
| Store | inside the starts' write (`mid_chain_write`) | pending journal entry | journal reconcile finishes it, then attempt recovery | end-to-end `test_recovery_is_exact` |
| Store | inside the results-and-terminals write: `after_journal_local`, `after_journal_push`, `mid_chain_write`, `after_chain_commit_local`, `after_chain_push` | pending or partial entry | journal reconcile writes results and terminals together, or neither and attempt recovery closes the starts | `test_crash_during_result_commit_keeps_results_and_terminals_together` (5 stages) |
| Store | handled failure while observing | `attempt_failed: execution_error`, no results, no exception text | none needed; if that write fails, recovery | `test_handled_failure_closes_attempts_without_private_text` |
| Store | a second, different terminal | refused by the public API; if written by a credential holder, a `conflict` record that makes the history unreconciled | the first terminal stands | `test_contradictions_through_the_public_api_are_refused`, `test_hash_valid_store_forgeries_are_reported[second_terminal]` |
| Store | a run still alive after its lock expired and was broken (the 75-minute case) | its later writes are refused (`Locked`); its attempts were aborted by the new run's recovery | none needed | `test_a_run_whose_lock_was_broken_cannot_write_its_results` |
| Store | a results entry pushed under the lock, then the run died | the next run finishes that entry under its own lock **before** recovery, so the attempts complete | none needed | `test_a_pending_entry_pushed_under_the_lock_is_finished_before_recovery` |

Not changed: the Store's journal, lock, mirror and idempotency (their existing crash tests still pass). A record
finished by a later run's journal recovery carries that run's provenance; the reconciler links results to the writer
of their terminal (the same journal entry), and binds each start to its own run through the attempt ID.

## 14. Reconciliation guarantees and explicit limitations

Established by adversarial tests, both stores, hash-valid forgeries by a credential holder included:
- unregistered protected evaluations (Ledger and Store);
- attempt IDs that do not recompute; malformed identities;
- authorizations inconsistent with their own recorded fence or token (role relabelling, another batch's or
  specification's token);
- completion identity or designation escalation; designated reserve reuse;
- forward attempts inconsistent with their prediction's registration (specification, executable, batch, channel,
  first observation, freeze);
- results outside their attempt's subject, executable, data identity or declared window;
- missing, duplicate or contradictory terminals, and conflicts on evidence or attempt records;
- invalid retries; result-linkage mismatches;
- every completion, linked or not, legacy or new, validated for structure, role, provenance and evidential weight
  (recomputed with the canonical function);
- deleted, altered, truncated or replaced history against the supplied anchor; malformed or wrong anchors.

`access_reconciled` is true in the tests only for clean, complete, schema-2 histories.

Limitations (also returned in every report's `limitations`):

1. Manhattan code paths only; a read outside Manhattan code leaves no record (ARCHITECTURE §8 item 3).
2. Not a sandbox: hostile code in the process, or a holder of a store's credential, is outside the structural
   boundary (section 1). The AST scan makes a bypass inside Manhattan visible in review, not impossible.
3. Anchors are checked, not independently held (D-7): no independent certification is claimed.
4. The reserve token is recorded with its binding (batch, manifest hash, specification) but its signature or tag is
   not re-verified by the reconciler.
5. The ops code identity's content digest covers `manhattan/engine` only (the existing `engine_sha256` contract);
   the runner's own modules are covered by the commit alone (D-9).
6. Exploratory (open) reads are not logged, by design; unregistered exploration evaluations are counted, not flagged.
7. Legacy records are never certified, so a store with legacy protected records never reconciles (D-4).
8. Cross-store reconciliation checks attempt-ID disjointness and combines counts; no scientific rule links the two
   stores' evidence, and none is invented here.
9. A window's liveness check sees its attempt's own `Ledger` or `Store` object. A terminal written by another
   process (or another object on the same file) is enforced when that process tries to write (the Store lock
   compare-and-swap; the Ledger is single-writer) and by reconciliation, not on the in-memory read.
10. Registration records (`registration`, from the merge time and witness) are written by the existing registration
    path; this phase checks attempts against them but does not re-authenticate them.
11. Store computation binding is narrow (S7 N2): computed values are bound to the attempt's own computation;
    the `reconstructed` provenance flag is not bound to the capture records, and a selectively omitted observation
    is not detected in the run (the next run records it, since its key is still absent). Gate G-1.
12. A missing `config_sha256` (a caller-supplied fence; engine attempts in tests) is recorded as such. No
    production engine reserve or forward caller exists; gate G-3 covers one.

## 15. Remaining integration decisions

D-1 to D-4 (section 10) stay open; D-5, D-6, D-7, D-12 and D-13 are decided (section 10). Found during
implementation and still open:

| # | decision | meanwhile |
|---|---|---|
| D-8 | Screening takes no lock, so its interrupted attempts are not recovered automatically | an operator runs `access.commit_recovery(store, kinds=("screening",), require_lock=False)` while no screening runs |
| D-9 | Extend the code-identity contract with a digest of `manhattan/ops` (a new key the contract does not yet know) | `engine_sha256` plus the commit; a dirty runner checkout is not detected by the digest |
| D-10 | Whether `factors/reproduce.py` and other exploration evaluations should register attempts | unchanged: open exploration |
| D-11 | Whether `attempts_registered` and `attempts_recovered` may appear in the public health record | added as integer counts (like `observations_new`); remove them from `HEALTH_SCHEMA` if not wanted |

## 16. Test evidence

Local runs are on Python 3.13 unless stated; remote CI runs CPython 3.12.16. **Local and remote results are reported
separately, and a nonzero exit code is never described as green.**

**Round 1 (PR head `060d4e3`).**

| run | result | exit |
|---|---|---|
| local full suite | 2,065 passed, 131 skipped, 1 error (Q019 `E2BIG`, below) | 1 |
| remote CI | 2,064 passed, 132 skipped, **1 failed**: `test_hash_locked_runner_in_clean_environment`, `ModuleNotFoundError: yaml` | 1 |

That CI failure was a **genuine regression** (S7 H1), separate from the local Q019 error.

**S1 correction round (`fea1d6c`).**

| run | command | result | exit |
|---|---|---|---|
| S7 counterexamples, before | scratch reproduction script at `060d4e3` | 11 of 11 engine/Ledger cases vulnerable (the Store cases M1/M2 are reproduced by regression tests) | n/a |
| new regression tests on the old code | the new tests copied into a `060d4e3` worktree | every S7 regression test fails (33 + 4 M4 cases + the Store sealing test at collection); the 7 round-1 forgery cases pass there, as before | 1 |
| S7 counterexamples, after | the same script | every case blocked (table in section 17) | n/a |
| Phase 4B tests, original and new | `pytest tests/test_manhattan_binding_access.py tests/test_manhattan_ops_attempts.py` | 129 collected, all passed (inside the next run) | 0 |
| targeted and integration | the two files above plus `ops_e2e`, `ops_runner`, `ops_store`, `pit_phase3b`, `pit_phase3c`, `pit_integrity`, `engine`, `factors`, `registry`, `attempts`, `ops_capacity`, `ops_blinding`, `ops_hardening_patch`, `ops_compiler`, `capture_v2` | 608 passed | 0 |
| exact locked-runner test, CPython 3.12.3 | `python3.12 -m pytest tests/test_manhattan_ops_lock_install.py` with `MANHATTAN_RUNNER_WHEELHOUSE` built from the unchanged lock | before the fix: 1 failed (`yaml`); after: 1 passed | 1 → 0 |
| local full suite | `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -rs -p no:cacheprovider` | 2,108 passed, 131 skipped, **1 error**, 1,464 s | **1** |
| remote CI (`pytest` workflow, PR #86) | `python -m pytest -q -p no:cacheprovider` under `bash -eo pipefail` | 2,108 passed, 132 skipped, 0 failed; conclusion **success** | 0 |

**The local error is pre-existing, environmental and local-only.** The test is
`test_q019_collect_refuses_late_dated_oversized_or_binary_tables[big.csv-...]`, which fails at setup with
`OSError: [Errno 7] Argument list too long: 'git'`. Its 2.2 MB parameter is part of the test ID, which pytest exports
as `PYTEST_CURRENT_TEST`, so the fixture's `git` subprocess exceeds this machine's exec limit. Unmodified main
(`f5f8045`) gives the same result here: 85 passed, 1 error. Remote CI passes it. Because of this error, the local
full suite is not green.

Skips are the existing environment-gated ones: no private Norgate snapshot or `EM_MACRO_DATA`; a shallow clone
without the pinned commits; `MANHATTAN_SLOW_TESTS`; `EM_MACRO_VERIFY_V1`; `Q009_FULL_SWEEP`; and locally, the
CPython 3.12-only lock test, which was run separately under 3.12 as shown above.

Checks:
- `python -m nightshift.protected <every changed path>`: exit 0.
- `git diff --check`: exit 0.
- `SIM_PREREG.md` and `SIM_PREREG_v2.md` match their recorded SHA-256 files.
- Not changed: protected paths, `config/manhattan.yaml`, workflows, the lockfile, thresholds, protocol versions,
  promotion rules, live controls, held-out construction and simulation workflows.

## 17. S1 correction round after the independent S7 audit

S7 (read-only, independent) reproduced the defects below on PR #86 at `060d4e3`. Each was reproduced again in this
session before any fix (a scratch script; every case **vulnerable**); each now has a regression test that **fails
on `060d4e3`** (run there in a scratch worktree with the new tests copied in) and passes on the corrected code.

| S7 | defect | fix | regression tests |
|---|---|---|---|
| H1 | `runner.py` imported `manhattan.config` (PyYAML) at module level; the hash-locked runner environment has no PyYAML; remote CI failed `test_hash_locked_runner_in_clean_environment` | the fence is injected (`RunConfig.fence`) or read lazily by `run_fence` only when predictions must be observed; the lock is unchanged and the probe still asserts PyYAML is absent (D-12) | `test_runner_imports_without_pyyaml`; the exact CPython 3.12 locked test |
| H2 | a protected window stayed readable after its attempt was aborted, failed or completed; `data_read` could stay false after a read; reconciliation then said true | every read re-checks the attempt's liveness, store version and grant; reads are counted before any value leaves; a read after a terminal raises | `test_no_read_after_abort_and_data_read_stays_true`, `test_no_read_after_any_ending` (identity failure, execution failure, completion, superseding retry), `test_store_window_reads_only_while_its_attempt_is_active` (fail, complete, recover) |
| H3 | `copy.deepcopy` and pickle produced readable protected windows outside the read counter; `object.__setattr__` widened an exploration window to forward dates | windows refuse `copy`, `deepcopy` and serialization; a per-process grant registry admits a read only through the minted object, unchanged, in the minting process (so altered, unpickled and fork-inherited windows fail) | `test_windows_cannot_be_copied_serialized_or_altered`, `test_a_forked_child_cannot_read_an_inherited_window` |
| M1 | a Store observation outside its attempt's window, or of another executable or specification, reconciled true | the reconciler checks every forward attempt against its prediction's registration (specification, executable, batch, channel, first observation, freeze) and every linked result against its attempt (subject, executable, data, date inside the declared window); `access.completion` refuses such results at write time | `test_hash_valid_store_forgeries_are_reported[outside_window, wrong_executable, registration_mismatch]`, `test_store_completions_need_a_read_and_cover_exactly_their_results` |
| M2 | a second terminal and a conflicting observation value existed as `conflict` records while the history reconciled true; an old runner alive after lock expiry could still write | any conflict on an evidence or attempt record is a violation; the public API refuses such writes; runner writes carry `require_lock`, checked inside the journal transaction (git fast-forward compare-and-swap), and the next run finishes pushed entries before recovery | `test_hash_valid_store_forgeries_are_reported[conflicting_observation, second_terminal]`, `test_contradictions_through_the_public_api_are_refused`, `test_a_run_whose_lock_was_broken_cannot_write_its_results`, `test_a_pending_entry_pushed_under_the_lock_is_finished_before_recovery`; the round-1 test that expected a second terminal to reconcile is corrected |
| M3 | `evaluate` used `version or code_version()`, so a fabricated matching version completed and reconciled | for attempt-bound evaluations the running identity is always computed; a supplied version must equal it | `test_fabricated_matching_version_is_refused` |
| M4 | unlinked completions with an invalid role or a wrong weight were counted as exploration and reconciled | every completion, linked or not, is validated (structure, role, provenance, weight, rerun linkage); an invalid one is a violation and is never counted as open exploration | `test_invalid_unlinked_completions_never_reconcile` (4 cases) |
| M5 (D-5) | a public API could manufacture a weight-1 protected completion from an attempt ID | `Ledger.record_evaluation` needs a one-use `CompletionProof` for reserve/forward (minted only after a read, bound to attempt, result and ledger); `Ledger.append` refuses lifecycle types; `Store.write` refuses evidence and attempt types unless `manhattan.access` sealed the batch, and `access.commit_results` checks every result is linked, with its exact content, by a minted completion | `test_completion_proofs_are_single_use_bound_and_require_a_read`, `test_storage_api_refuses_escalated_or_implicit_completion`, `test_evidence_and_attempt_records_need_access_sealing`, `test_store_completions_need_a_read_and_cover_exactly_their_results` |
| M6 | a reserve token for another batch registered silently | the token must be verified and name the attempt's batch, a manifest hash, the specification (`RunnerToken.specs`, new) and the (domain, window); the recorded binding is re-checked by the reconciler | `test_reserve_token_must_match_the_attempt` (6 cases), `test_a_recorded_token_for_another_batch_or_spec_is_a_violation` |
| D-6 | a second designated reserve evaluation for a (batch, domain) succeeded | refused at registration (except a retry of the unfinished one); reuse reported by the reconciler | `test_one_designated_reserve_evaluation_per_batch_and_domain`, `test_a_forged_second_designated_reserve_attempt_is_a_violation` |
| D-7 | an anchor from the same writer could read as certification | the report separates internally consistent / checked against a supplied anchor / independently anchored, and never claims the last | `test_reconciliation_never_claims_independent_certification` |

**Before and after** (the reproduction script, same cases; "before" at `060d4e3`):

| counterexample | before | after |
|---|---|---|
| read a forward window after `abort` (recorded `data_read: false`), then reconcile | returns forward data; reconciles true | `AccessError` at the read |
| read after the evaluation failed identity validation | returns forward data | `AccessError` |
| `copy.deepcopy(window)` | readable, original counter unchanged | `AccessError` (copy refused) |
| pickle round trip | readable | `AccessError` (serialization refused) |
| `object.__setattr__(window, "end", ...)` on an exploration window | forward dates returned | `AccessError` at the read |
| fabricated matching `version` | completes, reconciles true | `AccessError`; attempt failed |
| unlinked completion with role `admin` / exploration with weight 1 | reconciles true | violations; not reconciled |
| weight-1 forward completion from an attempt ID, no read | written, reconciles true | `LedgerError` (no completion proof) |
| unlinked weight-1 reserve completion through the storage API | written | `LedgerError` (no registered attempt) |
| reserve token of another batch | registers | `AccessError` |
| second designated reserve evaluation, same batch and domain | both complete, reconcile true | `AccessError` (D-6) |
| Store: observation outside the window / another executable / another specification | reconciles true | violations (regression tests above) |
| Store: second terminal / conflicting observation | conflict records, reconciles true | refused by the public API; violations when forced |
| CPython 3.12 locked runner | `ModuleNotFoundError: yaml` | passes |

Existing tests changed in this round, each because the old expectation encoded a defect or the old storage API:
- The 4A lifecycle tests (`test_manhattan_attempts.py`, `test_manhattan_registry.py`) now use the exploration role.
  Their rerun, nondeterminism and retry mechanics are role-independent, and D-5 forbids the old reserve writes.
  Their file-level forgeries use `forge`.
- The registry test asserts that the old reserve write is refused.
- The phase 3B reconstructed-weight test asserts that the storage API refuses a protected reconstructed record.
- The Store mechanics tests use a neutral record type.
- The end-to-end overwrite attempt is now refused instead of recorded as a conflict.
- The round-1 test expecting a second terminal to reconcile is corrected.
- The capacity harness's ledger benchmark writes a neutral record type.

## 18. S1 correction round after the S7 re-review (head `8615c69`)

S7 confirmed that the 11 original counterexamples were fixed, and reported two new High defects (N8, N1) and three
smaller findings (N2–N4). The owner also decided D-12 and D-13. Every defect test below fails on `8615c69` and passes
on the corrected code (checked in a scratch worktree). N3's scan self-test and the restored N4 tests pass on both,
because they add coverage rather than reproduce a defect.

| item | defect / decision | fix | tests |
|---|---|---|---|
| **N8** | A failure (not a crash) after the results entry was journalled but before it was applied made the runner write failed terminals; the later journal recovery then wrote the completions, creating permanent conflicts | `commit_results` settles a failed write first (section 7): reset to the remote; a pushed entry is finished now or by the next run's journal recovery, and no failed terminal is written for its attempts; only an entry that provably never left the process lets those attempts be closed as failed. Nightly forward processing and screening share the path | `test_failure_while_applying_results_never_contradicts_them` (transient; until restart), `test_an_uncommitted_results_entry_never_becomes_a_success`, `test_screening_failure_while_applying_results_never_contradicts_them` |
| **N1** | Five non-designated reserve attempts read protected data and were cancelled, then a designated evaluation completed at weight 1 and reconciled | registration refuses any non-designated reserve attempt, and any second reserve attempt of the (batch, domain), designated or not; the reconciler reports `non_designated_reserve_attempt` and `designated_reserve_reused` in forged histories | `test_non_designated_reserve_attempts_are_refused`, `test_forged_non_designated_reserve_history_never_reconciles` (0, 1, 5 forged probes) |
| **N2** | A fabricated observation was accepted after a legitimate read | narrow fail-closed binding: `access.run_bound` computes over the attempt's own window and binds the result; `completion` refuses values that are not the bound result's, and refuses completion without a bound computation. The provenance flag `reconstructed` is not bound: gate G-1 | `test_a_fabricated_observation_after_a_legitimate_read_is_refused` (net, exposure, turnover, an unbound raw backtest), `test_a_fabricated_screening_result_is_refused`, `test_the_bound_computation_is_the_attempts_own_window` |
| **N3** | The static scan did not cover the new private access-control names | the scan covers every private capability and raw writer (pit grants and seals; access proofs, seals, bindings, settlement; Ledger `_append`/`_index`; Store `_append_local`/`_commit`/`_push`/`_transact`/`_apply`), including definitions, `from … import`, and exact string constants such as `getattr(m, "_GRANTS")` | `test_private_access_paths_are_used_only_where_allowed`, `test_the_scan_detects_prohibited_references` (10 synthetic violations) |
| **N4** | Weight tests had moved to exploration records, whose weight is always 0 | through registered forward attempts: first valid evaluation weight 1; rerun, nondeterministic result and changed data weight 0 (family suspended, result of record kept); reserve: weight 1 once, and no protected rerun can even be registered | `test_protected_weights_through_the_real_path`, `test_reserve_weight_1_once_and_no_protected_rerun` |
| **D-12** | Configuration of the locked runner | hash-pinned PyYAML in the lock; `safe_load`; the configuration is verified against the file at the registered commit and an optional explicit SHA-256 pin; no injected fence; fail closed (section 10) | `test_the_runner_fence_is_verified_against_its_pinned_identity` (7 cases), `test_runner_imports_without_pyyaml`, the exact CPython 3.12 locked-runner test (its probe now checks the verified fence and a wrong pin) |
| **D-13** | Designation consumption | never released, even when no protected read was recorded | `test_a_designation_is_consumed_even_without_a_read` |

**Before and after.**

| counterexample | before (`8615c69`) | after |
|---|---|---|
| N8: an exception while applying the journalled results, then restart | 8 `attempt_failed` terminals written while the completions were pending; journal recovery then conflicts | no failed terminal for those attempts; the entry is finished (in the run, or on restart); no conflict; a second restart changes nothing; `access_reconciled` true |
| N8: the results entry never reached the remote | the unpushed local journal commit rode along with the failed-terminal write, and journal recovery then applied the uncommitted evaluation: 8 terminal conflicts (a success fabricated from an uncommitted evaluation) | the clone is reset first; attempts closed as failed with `data_read: true`; no observation or completion of that evaluation is ever written; the restart computes its own |
| N1: five non-designated reserve reads, then a designated weight-1 evaluation | registered, read, reconciled true | refused at the first registration, before any read; forged equivalents are violations |
| N2: a fabricated observation after a legitimate read | accepted | refused (`values are not those of the attempt's bound computation`) |

**Activation gates.** None of these is lifted by this PR.

| gate | before forward or reserve results may count as evidence |
|---|---|
| G-1 | Bind the observations' `reconstructed` provenance to the Store's capture records. For example, the reconciler could re-derive first-seen availability from the Store clone's captures and raw files. Until then, forward observations must not count as evidence (S7 N2). |
| G-2 | Independent custody of anchors (D-7). Without it, nothing is independently certified. |
| G-3 | Any production engine reserve or forward caller registers with the verified configuration (`fence=None`). Caller-supplied fences are reported as `protected_attempts_with_unpinned_fence`. |
| G-4 | A workflow adopts the candidate lock (owner). The live workflow is unchanged and installs `requirements.txt`. |
| G-5 | Reserve stays disabled (`config/manhattan.yaml`). No reserve workflow is authorized, and this PR enables none. |
| G-6 | D-1: the counting unit of any multiple-testing denominator. `independent_statistical_tests` stays `null`. |
