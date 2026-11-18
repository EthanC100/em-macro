# Manhattan HTE: high-throughput hypothesis-evaluation engine

Status: **research infrastructure, synthetic data only, not in force.** Branch `claude/manhattan-hypothesis-engine-jypgud`
(session S9, 2026-11-18). Code: `manhattan/hte/`. Tests: `tests/test_manhattan_hte_core.py` and
`tests/test_manhattan_hte_funnel.py`. Measured throughput: [BENCHMARKS.md](BENCHMARKS.md). Limitations and blockers:
[LIMITATIONS.md](LIMITATIONS.md).

Nothing here changes a protected path, a frozen protocol (PROTOCOL_v3/v3.1, SIM_PREREG/v2), `config/manhattan.yaml`,
`trials.csv` or any research threshold. The engine never reads real, licensed, reserve or forward data. It writes no
Manhattan Ledger or Store record, and it does not import the PR #86 access layer.

## 1. What it is for

Manhattan's ARCHITECTURE.md allows up to 250,000 executables. This work asks a narrower question: can a cheap,
reproducible and fully accounted pipeline *process* about 10^6 registered candidates? "Process" means validate,
screen, simulate and package them. Each candidate is a parameter combination; it is not an independent hypothesis.
The answer is measured in BENCHMARKS.md. This document describes the machine.

The engine has the following properties:

- **Complete accounting.** Every registered candidate has a terminal status at every stage it reached. Every
  attempt has exactly one terminal record, or it is reported as unfinished. Failed and interrupted work is never
  deleted.
- **Determinism.** The results are bit-identical whatever the submission order, chunk size or worker count. They
  are also bit-identical after any interruption and resume, on one platform.
- **No unrecorded selection.** Nothing that decides what gets computed can see the sign of an outcome, unless it is a
  recorded, hashed, benchmark-only policy. That policy is disclosed in every package it touches.

## 2. Counting levels (never equated)

| level | identity | what it is | where it is counted |
|---|---|---|---|
| hypothesis family | `HF-` + 16 hex of the full SHA-256 | a mechanism with a predicted sign | `registry_frozen.counts.families`; one package each |
| registered hypothesis | `HH-` | the family in one domain (commodity, rates, FX) | `counts.hypotheses` |
| strategy specification | `HS-` | a template with a declared, bounded grid and its bindings | `counts.strategy_specs` |
| parameter variant | `HV-` | one grid point | `counts.variants` |
| candidate | `HC-` | a variant bound to a cost model and a sizing rule, under methodology `hte-eval/1` | `counts.candidates` |
| behavioural class | positions fingerprint | candidates whose windowed positions and cost binding are bit-identical | package `behavioural_classes`; `alias` status |
| screening attempt | attempt ID = hash of its `attempt_started` record | one chunk of pass A (stages 1+2) | `reconcile().attempts`; `history()` per candidate |
| full evaluation attempt | same | one chunk of pass B (stage 3) | same |
| run | `HR-` | registry root × data hash × code digest × policy hash × window | `run_started`; packages count `runs_on_this_registry` |
| independent statistical tests | **not computed** | `null`, with a reason, everywhere | owner decision D-1 of PR #86 |

Each child record holds its parent's full hash, so a link cannot change without changing the child's identity
(the same rule as `manhattan/spec.py`). The canonical form is `manhattan.spec.canonical_bytes`, reused as is.
Under that form `5` and `5.0`, and `0.5` and `0.50`, are the same value. Key order does not matter.

Code identity and data identity are attributes of an **attempt**, not of a candidate. The same registered candidate
can be evaluated with several code versions or synthetic datasets, and each such evaluation is a separate counted
look. This matches PR #86's attempt identity, which keeps `spec_hash`, `data_hash` and `code_version` as separate
fields.

The one deviation from ARCHITECTURE §3 is that a Manhattan executable (`AX-`) folds the code version into the
spec. `adapters.to_pr86_identity` maps HTE's candidate plus engine digest onto PR #86's `executable` field (§7).

## 3. Registry (stage 0)

`registry.Registry.submit(bundles)` validates whole strategy specs (`registry.validate_bundle`). It checks the
following:

- record levels and parent hashes;
- the domain and the template version;
- every grid value against the template's schema (type, range, choices);
- duplicate grid values, which would register duplicate candidates;
- that each point's look-back fits the warm-up;
- the template's **PIT probe** (§6.4), run once per template version and logged as `pit_probe`.

Invalid specs register nothing and are logged as `submission_rejected` with their reasons.

A valid new spec is enumerated. Its candidates go into an atomic, hash-verified segment file. The family,
hypothesis and spec records go into a hash-verified records file. The log record `registry_segment` names both
SHA-256s, the candidate count and the Merkle root.

The registry is append-only. A spec that is submitted again registers nothing and logs `duplicate_submission`.

A strategy spec is canonical. Every grid axis and binding list is sorted (`registry.strategy_spec`), and an unsorted
or extra-field spec is refused. There is no free-text label, so the same grid written in another order, or under
another name, is the same spec, and resubmitting it is a duplicate. Specs that overlap inside one hypothesis, for
example two horizons sharing a look-back, stay registered: each is a distinct, declared spec. Their repeated
economics are counted as `semantic_duplicates` in the frozen counts.

`freeze()` fixes a canonical order: by strategy-spec hash, then grid index. The order does not depend on submission
order, and it keeps candidates that share features adjacent. `freeze()` logs `registry_frozen` with the Merkle root
of the candidates' full hashes in that order. A run evaluates exactly one frozen version. Earlier versions stay
verifiable (tested).

For 10^6 candidates, the registry stores four arrays: spec index, grid index, the 32-byte candidate hash and the
32-byte variant hash. It does not store 10^6 JSON configurations. `FrozenView.canonical_config(i)` rebuilds a
candidate's canonical configuration exactly, and its hash is the candidate's identity (tested).

## 4. The funnel

```
stage 0  submit + freeze        validation, identity, dedup, PIT probe               no data read
pass A   stages 1 and 2         per chunk of the canonical order                      logged attempts
           stage 1  degenerate? fingerprint, exact Hölder bound (sign-blind)
           stage 2  gross/net mean, std, t, Sharpe, turnover, exposure, activity, hit rate (screening statistics)
selection                       pure function of all pass-A results + policy          logged, file hash-verified
pass B   stage 3                per chunk of the selected list (whole bootstrap groups)  logged attempts
           vol-targeted net series with linear + |trade|^1.5 costs, series SHA-256, stats,
           bootstrap p-value (descriptive), streaming family-SPA partial maxima
stage 4  packages               per family: denominators, looks, post-look specs, descriptive stats, SPA, M_eff
stage 5  protected evaluation   DISABLED (protected.py): always raises
```

### 4.1 Stage 1: what "cheap screening with bounds" means here

Stage 1 makes three decisions. None of them can see whether a position made or lost money.

1. **Degenerate.** The candidate holds no position in the window. There is no series to test.
2. **Behavioural alias.** The candidate's windowed positions, domain and cost model are bit-identical to those of a
   candidate earlier in canonical order. Its results are identical by construction, so it is computed once and
   reported for every member. Aliases stay in every denominator.
3. **Dominated.** The engine uses the exact Hölder bound
   `gross mean = (1/n) Σ P·R ≤ H = (1/n) Σ |P|·|R|`.
   A candidate is dominated when `H·(1 + 1e-9) < C`, where `C` is its linear cost, so its stage-2 net mean is
   provably ≤ 0. This is property-tested on adversarial returns.

`H` reads only `|R|`. Flipping the sign of any evaluated return cannot change a stage-1 decision (tested). `H` is also
the **tightest possible** sign-blind bound: it is attained when every return has its position's sign (tested). So
any screen that prunes more than this must use the sign of outcomes. That makes it a performance screen, which
needs a recorded selection policy (§4.3).

The measured consequence is in BENCHMARKS.md. On these synthetic cost assumptions the bound almost never fires.
Pruning comes from degenerate candidates and behavioural aliases, not from the bound. This is reported as found, not
tuned away.

Stages 1 and 2 share one pass, because they share the expensive part: building positions. Stage 2 is computed for
every non-degenerate candidate, dominated or not, so the screening denominators are complete. A stage-1-only mode
(`stages=(1,)`) exists for measuring the cheap screen alone. It is a distinct run identity.

### 4.2 Stage 3

Stage 3 is a daily simulation:

- strategy-level volatility targeting from a lagged EWMA of the candidate's own unscaled returns (updated on active
  days only, leverage-capped);
- linear plus `|trade|^1.5` costs;
- the net series' SHA-256 and summary statistics;
- a one-sided stationary-bootstrap p-value for a positive mean (descriptive).

It also computes, per family, **partial maxima of Hansen's SPA statistics**. Every candidate in a run shares one
bootstrap index set. That is the Protocol's joint bootstrap, from `manhattan.stats.bootstrap`. Because of that
shared set, a family's SPA statistics are maxima over its variants. Floating-point `max` is exact, associative and
commutative, so partial maxima from any chunking combine to the bit-identical family statistic. The result equals
`manhattan.stats.spa.spa_test` on the same draws (tested).

The stored series hashes let stage 4 recompute any series and prove that it describes the series of record.

### 4.3 Selection and policy

`policy.Policy` holds every rule that decides what is computed, and its hash is part of the run identity. The
default advances every non-degenerate, non-alias candidate to stage 3, and sets no performance threshold. The
switches are:

- `skip_stage3_if_dominated` (default true);
- `dedup_behavioural`;
- the stage-3 selection.

`top_k_per_spec` ranks candidates on stage-2 t-statistics. It is refused unless `benchmark_only=True`. Its runs are
flagged `performance_gate`, and every package states that its stage-3 statistics are conditional on a recorded
selection that is not adjusted for. That run's SPA is refused because its variant set is incomplete.

The selection itself is a file. It is a pure function of the pass-A results of record. Its inputs' Merkle root is
logged, and `Runner.compute_selection()` reproduces it (tested).

All numeric constants in `Policy` are engineering defaults of this synthetic engine. None of them comes from, or
overrides, a frozen protocol.

## 5. Attempt accounting, crash safety and resume

The **log** (`log.py`) is an append-only JSONL hash chain. Every record is fsynced, and there is a single writer, the
runner's parent process. Wall-clock time sits outside the hashed content, so identical histories give identical
chains.

`verify(anchor=...)` detects edits, suffix deletion and history replacement against an anchor that is kept
elsewhere. Nothing in HTE keeps that anchor (§8).

A torn final line, written without a newline, is quarantined. The quarantine is logged with the line's SHA-256 and
the line is never repaired. A damaged line that ends in a newline stops everything.

**Protocol per chunk:**

1. `attempt_started`: the intent, fsynced. Its record hash is the attempt ID.
2. The worker writes the result file atomically (temporary file, fsync, `os.replace`) and returns its SHA-256.
3. `attempt_completed` names the file and its hash.

A crash at any point leaves one of two things:

- a start without a terminal, which the next invocation marks `attempt_interrupted` and counts;
- an orphan file that no record names, which is never read.

An exception that prevents a result file gives `attempt_failed`. The next invocation retries the uncovered
candidates, with `supersedes` naming every failed or interrupted attempt that covered them. A per-candidate
exception or non-finite statistic does not fail its chunk: that candidate gets status `failed` with a reason class
(`execution_error` or `non_finite`). An exception class name is logged, but no message and no value.

**Lost workers.** Workers run in a `concurrent.futures.ProcessPoolExecutor` with `fork`. A worker that dies (killed,
or out of memory) raises `BrokenProcessPool` instead of hanging, as `multiprocessing.Pool` would. The attempt is
logged `attempt_failed` with reason `worker_lost`, dispatch stops, and the next invocation retries (tested with a
worker that calls `os._exit`).

**One runner per workspace.** `Runner.run` holds an exclusive `flock` on `<workspace>/.lock`, which the operating
system releases if the process dies. A second concurrent runner is refused. A disk preflight, at about 3x the
measured bytes per candidate, refuses a run that cannot fit and logs `run_refused`.

**Fail closed.** Stage 3 does not start while any candidate lacks a completed stage-1/2 attempt. The run logs
`run_incomplete` instead.

**Repeated runs.** A closed run invoked again logs `run_reused`. With `verify_rerun=True`, the engine recomputes every
chunk as a *verification* attempt and compares each field bit-for-bit with the result of record. Any difference logs
`nondeterminism` and raises. The result of record is never replaced.

**Reconciliation.** `runner.reconcile(ws, run_id, anchor)` reads only persisted records and the files they name,
with hashes verified. It checks the following and returns counts and violations:

- exactly one completed, non-verification attempt per candidate per pass;
- one terminal per attempt;
- status totals equal to the registered count.

Like PR #86, it always reports `access_reconciled: false` and `independent_statistical_tests: null`.
`runner.history()` lists every attempt that covered a candidate, with its terminal.

**Files written per run** (under `<workspace>/runs/<HR-id>/`):

| file | contents |
|---|---|
| `A/*.bin` | per pass-A attempt: statuses, stage-2 statistics, fingerprints |
| `selection.bin` | the selection |
| `B/*.bin` | per pass-B attempt: stage-3 statistics, series hashes, SPA partials |
| `results.bin` | the canonical per-candidate table; its SHA-256 is the run's `result_root` |
| `packages/*.json` | one package per family |

All of these use a deterministic array container. `.npz` was rejected because it embeds zip timestamps.

## 6. Reproducibility and computation reuse

### 6.1 Determinism

Every per-candidate quantity uses elementwise operations and reductions along that candidate's own rows. Three
places needed care, and each was found by measurement or a failing test:

| component | problem | fix |
|---|---|---|
| `long_run_var` (stats module) | ends in `acov @ w`, a BLAS matrix-vector product whose per-row bits depend on the number of rows (found by `test_stage3_rows_do_not_depend_on_the_batch`) | ω is computed one row at a time; `manhattan/stats` is not modified |
| bootstrap means | a matrix product's per-column bits depend on the other columns (measured) | products run on fixed groups of 64 positions in the selected list (`kernels.BOOT_GROUP`); pass-B chunks are whole groups, so the same group is always the same product |
| negative zero | `-0.0` would change a fingerprint | positions are normalised (`w += 0.0`) |

The same group being the same product is about 7.6× faster than one matrix-vector product per candidate, which is
memory-bound on the 18 MB count matrix.

**Tested bit-for-bit:**

- chunk sizes 5, 16, 24, 32, 40 and 1000;
- 1, 2 and 3 workers;
- permuted submission order;
- feature cache on and off;
- resume after four crash modes in subprocesses, with different chunking and workers on resume.

Across CPUs or BLAS builds, results agree to rounding but not bit-for-bit. The platform is part of `code_identity()`
(numpy version; extend with the BLAS build before relying on cross-platform reruns). The engine digest covers
`manhattan/hte/*.py` and the modules HTE results depend on (`ids.DEPENDENCIES`: `spec.py`, `availability.py`,
`stats/bootstrap.py`, `stats/meff.py`). A change to any of them is a new run identity (tested).

### 6.2 Computation reuse

| technique | where | measured effect (BENCHMARKS.md) |
|---|---|---|
| shared rolling features (momentum, EWMA vol, z-scores, rolling extremes, carry means, unit-risk scale, \|r\|), computed once per process | `features.FeatureCache` | about 58,000 hits per 225 misses at 10^4 candidates |
| parent warm-up before forking: workers inherit features copy-on-write | `Runner._warm` | no feature is computed twice |
| disk cache keyed by data hash, feature, parameters and feature-code hash, verified on load | `FeatureCache` | corrupt entry: quarantined, recomputed, logged; never changes a result (tested) |
| behavioural dedup: alias candidates skip stage 3 | selection | 17% of the 10^4 workload |
| vectorised vol-target recursion across a chunk (time-major, masked coefficients) | `kernels._scales` | the Python loop runs over days once per chunk, not once per candidate |
| grouped BLAS-3 bootstrap | `kernels.stage3_boot` | 0.09 ms vs 0.71 ms per candidate |
| sliding-window process pool (fork), intent before dispatch | `Runner._execute` | 3.3-3.4x on 4 workers |
| bounded stage 4: M_eff on at most `meff_cap` series per hypothesis (outcome-blind stride), parallel | `package._run_meff` | cost independent of N |
| positions recomputed in pass B rather than stored | design | storing would cost 237 KB per candidate (about 237 GB at 10^6) |

### 6.3 What was not done, and why

- **No numba, JAX or GPU.** The CI installs `requirements.txt` only, and the user's rule was "simple, testable
  improvements".
- **No float32.** It would break the equivalence tolerances and the fingerprints.
- **Positions are not stored.** See the storage figure above.
- **No incremental recomputation across data versions.** A new data hash is a new run by design. Incremental
  extension of a window would have to be a new, separately counted attempt, and it is listed in LIMITATIONS.md as
  future work.

### 6.4 PIT isolation

- **Templates** build row `t` from data through the close of `t`. `kernels.align` applies row `t` to day `t + 1`. No
  template can change that.
- **Probe.** `pit.probe` checks every template at its schema's corner points, in every domain and sizing. It replaces
  returns and carry after several days `τ` with independent draws, and rows `0..τ` must be bit-identical. A test-only
  template that reads `r[t+1]` fails the probe and cannot register (tested). On a null world the same template shows
  a t-statistic above 20, which is why the probe is mandatory.
- **Carry** is stored already lagged by one publication day.
- **The fence.** `FencedPanel` never hands out the last `protected_days`, which are a synthetic stand-in for a reserve
  window. `window()` past the fence and `protected_tail()` raise `ProtectedDataRefused`.
- **Synthetic only.** `data.verify_synthetic` regenerates the panel from its recorded parameters and checks the data
  hash before every run. Real data cannot pass under a synthetic label (tested).

## 7. Integration contract with Manhattan infrastructure (PR #86, PR #84)

The adapter is **disabled** (`adapters.Pr86AccessAdapter` raises `AdapterDisabled`).

**Stable HTE side.** These are the parts of HTE that integration would rely on:

1. **Identity.** `adapters.to_pr86_identity(view, i, run_id=, data_hash=, code=, window=)` returns exactly the field
   set of PR #86 `ledger.IDENTITY_FIELDS`: `executable, variant, hypothesis, family, batch, role, channel, designated,
   spec_hash, data_hash, window, code_version`. It uses `role="exploration"`, `channel="blind"` and
   `designated=False`. `spec_hash` is the candidate's full hash and `executable` is
   `sha256(candidate, engine digest, methodology)`. Shape is tested; PR #86's validator is not called (blocker B1).
2. **Lifecycle mapping.**

   | HTE record | PR #86 equivalent |
   |---|---|
   | `attempt_started` | `register_*` start |
   | `attempt_completed` | `completion` / `commit_results` |
   | `attempt_failed` (reason class) | terminal `failed` with `execution_error` |
   | `attempt_interrupted` | terminal `aborted` with `interrupted` |
   | `supersedes` | `supersedes` / `retry_of` |

   Data read is always true for a completed or failed chunk.
3. **Evidence classification (PR #84).** An HTE result would classify as provenance `SYNTHETIC`, eligibility
   `E_INFRA` or at most `E_DESCRIPTIVE`, and authorization `AUTH_NONE`. `*_eligible` and `promotion_authorized` are
   false.

**Blockers** (from `adapters.BLOCKERS`):

| id | blocker |
|---|---|
| B1 | PR #86 is not merged, and its API is not stable from this branch's point of view |
| B2 | exploration attempts are deliberately unregistered in PR #86 (owner decision D-10) |
| B3 | the counting unit is open (D-1) |
| B4 | one HTE chunk attempt covers up to 512 candidates, while one PR #86 attempt is one executable; one PR #86 attempt per candidate is about 2-3 records per candidate (2-3 × 10^6 for a 10^6 run), so the cardinality is an owner design decision |
| B5 | HTE is synthetic-only, and the reserve and forward roles must never be reachable from it |

The smallest next step after PR #86 merges is a test that feeds `to_pr86_identity` output to PR #86's
`validate_attempt_identity`. Nothing else should be wired before B2-B4 are decided.

## 8. Self-review: what was attacked, and what it found

Section 9 of the build brief asked for an adversarial pass. These are the defects it found and fixed. Each has a
regression test:

- **`long_run_var` batch dependence** broke determinism at stage 3.
- **Batch-synchronous scheduling** wasted about 40% of four cores.
- **Workload defect.** The bundled workload declared carry `smooth=260`, whose look-back is 261. Stage 0 rejected
  the specs and logged them; the workload was fixed.
- **Test bug.** My own test assumed that every corrupted cache entry would be re-read. Dependencies of cached
  features are not re-read, and the test now checks logged count equals detected count.

The attacks, with the tests that cover them:

| attack | tests |
|---|---|
| accounting holes | crash at intent, after file, mid-line, worker exception; per-candidate exception and non-finite |
| duplicate submission and coverage | duplicate specs, double-coverage check, verification attempts kept separate |
| identity collisions | full-hash collision check at registration; representation-invariant canonical form |
| cache poisoning | corrupt entries quarantined |
| tampering | result files, registry segments and log lines refused |
| PIT | leaky template |
| fence and real data | swapped "real" data refused |
| seed shopping | no seed parameter on `Runner` or `run`; the bootstrap seed is a function of registered identities |
| repeated looks | a changed policy, code or data each counted as a new run in packages |
| post-look registrations | flagged |
| performance gate | requires `benchmark_only` and is disclosed |
| stage 5 | always refuses; `config/manhattan.yaml` unchanged |

A second pass found five more problems, each fixed with a regression test:

- **Spec dedup hole.** A reordered grid, or a cosmetic label, created a new spec hash and so registered the same
  economics twice. Specs are now canonical and labels are refused.
- **Overlapping specs** were invisible. Their repeated economics are now counted as `semantic_duplicates`.
- **Hang risk.** `multiprocessing.Pool` would hang for ever if a worker died. The engine now uses
  `ProcessPoolExecutor` and logs `worker_lost`.
- **Narrow engine digest.** It ignored `manhattan/stats/bootstrap.py` and the other dependencies. A change there would
  have reused a closed run silently; the digest now covers them.
- **No guard on concurrent runners or disk.** Runs now take a workspace `flock` and run a disk preflight.

This self-review is not an independent review. Its findings are limited by my own model of the system.
