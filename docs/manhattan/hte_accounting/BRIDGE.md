# HTE → PR #86 attempt accounting bridge (dormant)

`manhattan/hte_accounting/` connects the high-throughput engine (PR #89, with the #90 identity fix) to PR #86's
attempt accounting. It is **dormant**: `bridge.ENABLED` is a constant `False`, and every owner decision it needs is an
explicit policy field with no default. It runs on synthetic panels in the exploration role only. Nothing it produces is
evidence; under PR #84 it is synthetic infrastructure validation (`E_INFRA`).

The package sits outside `manhattan/hte/`, so HTE itself still imports nothing from PR #86 (#89's
`test_hte_does_not_import_pr86_private_names`). It imports PR #86 modules only when a bridge is constructed, and it
uses PR #86's public API only: `access.register_evaluation`, `access.DeclaredWindow`, `Ledger.end_attempt`, the
`Ledger` read methods and `attempts.reconcile`.

## 1. Units, kept apart

| unit | what it is | where it is recorded |
|---|---|---|
| **scientific evaluation** | a *binding* (#90: candidate + every evaluation-affecting parameter, no code or environment) on one data set and window | `adapters.lineage` |
| **executable evaluation** (a *look*) | binding + engine digest + numerical environment, on data and window = PR #86's key `(spec_hash, data_hash, window id)` | PR #86 `Ledger.looks()` |
| **chunk** | HTE's own unit of computation: up to 512 candidates of one pass | HTE log `attempt_started` / `attempt_completed` |
| **attempt** | one PR #86 registration of one candidate executable | PR #86 `evaluation_started` (attempt schema 2) |
| **retry** | an attempt that supersedes an interrupted one (same identity) | PR #86 `supersedes` |
| **rerun** | a completed attempt whose PR #86 key was already completed with the same result | PR #86 `rerun` |

A chunk is never an attempt, and an attempt is never a test. Counts at every level are reported side by side by
`crosscheck`. `independent_statistical_tests` stays `None` (D-1).

## 2. Lifecycle

```
begin(runner)            one PR #86 attempt per candidate (or a retry of its interrupted attempt);
                         registration file (attempt + executable digests, SHA-256);
                         HTE log: pr86_registered {PR #86 ledger head, file hash, Merkle root of attempt IDs}
runner.run()             HTE computes (chunks); run_closed / run_verified
complete(runner, writer) results of record -> per-candidate result_hash + cohort_hash -> outcome batches (<= 512 rows)
                         -> per attempt: completion (writer) or end_attempt(failed, execution_error, data_read=True);
                         HTE log: pr86_completed {PR #86 ledger head, batches, Merkle roots}
crosscheck(runner, ledger)   read-only: HTE log against PR #86 ledger (section 5)
```

- **Interruption.** An invocation that dies leaves its attempts open. `complete` refuses ("incomplete: the attempts
  stay open"). The next `begin` retries each open attempt with `supersedes`, and PR #86 keeps the superseded start
  visible. Resuming without a new `begin` is refused by `complete` and flagged by `crosscheck`
  (`unregistered_computation`). `abandon(runner, why)` closes the attempts of a run that will not resume as
  `aborted: interrupted` with `data_read` true.
- **Crash during completion.** `complete` is resumable. A second call checks that every attempt already closed was
  closed by this completion (same result hash or failure), then finishes the rest.
- **Duplicates.** A plain invocation of a closed run computes nothing (HTE `run_reused`), so `begin` refuses it. A
  `verify_rerun` invocation recomputes, gets new attempts, and its completions are PR #86 `rerun`s: one look, two
  attempts.
- **Corruption.** If the HTE run does not reconcile (`corrupted`, a verification failure or a nondeterminism), every
  open attempt is closed `failed: validation_error` and nothing is completed (`pr86_failed`).
- **Failed candidates** are failed attempts (`execution_error`, `data_read` true) and stay in every count.
- **Engine or environment change.** This is a new HTE run (both are in its run identity) and a new executable for
  every candidate (#90). Its completions are new looks, never reruns of another engine's look, and never a false
  nondeterminism.

## 3. Per-candidate result hashes

`outcomes.py` splits each candidate's row of the results of record into two parts:

- **intrinsic** (`result_hash`), a function of the executable, data and window alone: stage-1/2 statuses and
  statistics, fingerprint, stage-3 statistics without the bootstrap p-value, and the return-series hash. An alias
  takes its representative's stage-3 status, because its values are bit-identical copies.
- **cohort-dependent** (`cohort_hash`): computed-vs-alias disposition, alias representative (as a candidate digest,
  not an index), cross-family flag, and the bootstrap p-value. `kernels.stage3_boot` documents that the BLAS product's
  per-column bits depend on the other columns of the 64-candidate group.

PR #86 compares `result_hash`, so registering unrelated candidates (a new freeze) gives `rerun`s with identical
results, not a nondeterminism that would suspend the family (tested). `cohort_hash` is stored in the batch and in the
completion's summary, so nothing in the row escapes hashing.

Hashes are SHA-256 over a domain tag, a schema digest (column names, little-endian dtypes, widths), the candidate
digest and the row's bytes. They are deterministic across processes and chunkings, and any single changed value
changes exactly that candidate's hash (tested).

**Outcome batches** hold at most 512 candidates in canonical order (`manhattan.hte.store` container, atomic write,
SHA-256 in the record). Each row holds every column, both hashes, and the candidate, executable and attempt digests,
plus its terminal. A completion's summary names `{outcome_batch, row, batch_root, cohort_hash, hte_run}`, so any one
outcome can be fetched and verified alone.

## 4. Owner decisions (fail closed)

| id | question | alternatives | bridge behaviour |
|---|---|---|---|
| **D-10** | do exploration evaluations register PR #86 attempts? | `unregistered` (PR #86 today); `register_every_evaluation`; rejected: `register_selected_only` (the registered set would depend on outcomes) | `None` → `OwnerDecisionRequired`; `unregistered` → refuses (writes nothing) |
| **D-1** | which unit enters a multiple-testing denominator? | `registered_executions`, `completed_evaluation_keys`, `executables`, `bindings`, `candidates`, `variants`, `hypotheses`, `families` | never needed by the bridge; `denominator()` refuses without it and an approval reference |
| **B4** | HTE work → PR #86 attempts cardinality | `per_candidate_attempts` (implemented: PR #86's attempt is one executable); `per_chunk_attempt` (needs a new PR #86 attempt kind) | `None` → required; `per_chunk_attempt` → unsupported |
| **A-1** (new) | may HTE completions be written to the Manhattan ledger, and by which module? PR #86 lets only `ledger.py` and `engine/evaluate.py` call `Ledger.record_evaluation` (`tests/test_manhattan_binding_access.py` `ALLOWED`; "adding a module here is a reviewable decision") | (a) add `manhattan/hte_accounting/bridge.py` to that allowlist; (b) run HTE computations through `engine.evaluate` under an `AttemptContext` (a redesign of HTE's vectorised stages); (c) keep HTE completions out of the ledger (consistent with D-10 = `unregistered`) | the bridge never calls `record_evaluation`. `complete` refuses (`OwnerDecisionRequired: A-1`) unless the caller supplies a completion writer, and nothing is written. Only the tests and the benchmark script, outside `manhattan/`, supply one. |
| **A-2** (new) | ledger scaling. PR #86's `record_evaluation` scans every earlier evaluation for each new one (its `data_changed` rule), so completions grow quadratically in one ledger; registration and the strict reconciler re-check every declaration over the whole window (about 2 ms per attempt for HTE's 8.8-year windows) | (a) accept one ledger per HTE run (measured, section 6); (b) shard ledgers by `spec_hash` prefix (every PR #86 key rule stays inside one shard; needs an anchor per shard); (c) index the `data_changed` lookup in PR #86 (a PR #86 change) | single ledger only; costs are reported |
| **A-3** (new) | data identity. A registered HTE attempt binds the synthetic panel's `data_hash` (verified by `verify_synthetic`) and declares exploration windows, but HTE reads its own panel, not a PR #86 `PitStore(synthetic=True)` window, so PR #86 records no window read | (a) accept identity binding for synthetic panels; (b) load the panel into a synthetic `PitStore` and compute inside the attempt's windows (a redesign) | (a), stated here and in every report |

Each policy also names `approval_ref`, where the owner recorded the decisions. A policy without one is refused. The
test fixture's reference says "test fixture, not an approval".

## 5. Cross-check (`crosscheck.py`)

Checks HTE's native log against the PR #86 ledger. Each failure is a violation code:

| code | meaning |
|---|---|
| `unregistered_computation` | a computing invocation without its own registration before it in HTE's chain |
| `registration_file_corrupt` | registration file missing, or not matching its SHA-256 or Merkle root |
| `ledger_anchor_mismatch` | an HTE record names a ledger head the ledger does not have |
| `registered_after_anchor` | an attempt registered after the head its HTE record anchored |
| `attempt_missing`, `identity_mismatch`, `foreign_attempt` | registration and ledger disagree |
| `outcome_batch_corrupt`, `result_hash_mismatch` | batch file or row hashes wrong, or not the results of record |
| `terminal_mismatch`, `open_after_completion` | PR #86 terminal disagrees with the outcome, or is missing |
| `hte_run_corrupted` | HTE's own reconciliation |
| `ledger_does_not_verify`, `pr86_reconciler` | PR #86's chain and its strict audit (`attempts.reconcile`) |

Each chain anchors the other: HTE records hold PR #86 ledger heads, and PR #86 completions hold outcome-batch hashes
whose rows hold the attempt IDs.

## 6. Benchmark

`scripts/hte_accounting_bench.py` measures this (outside `manhattan/`, because it supplies the A-1 writer). The
results are in `results/manhattan_hte_accounting/` and summarised in the PR description.

## 7. Limitations

- Dormant: nothing calls the bridge, and no production ledger, workflow or configuration is touched.
- The PR #86 completion path (A-1) is exercised only with a test-supplied writer.
- One PR #86 ledger per run (A-2); costs grow as measured.
- HTE computations are not executed inside PR #86 attempt windows (A-3).
- Same-close execution (#89 F8) still restricts every HTE number to throughput testing.
