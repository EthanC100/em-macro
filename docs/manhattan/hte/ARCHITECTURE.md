# Manhattan HTE: high-throughput hypothesis-evaluation engine

Status: **research infrastructure, synthetic data only, not in force.** Branch `claude/manhattan-hypothesis-engine-jypgud`
(session S9, 2026-11-18; S10 corrections 2026-11-19, §9). Validation on this branch at `4355fa1`:

- HTE tests: 178 passed, 1 skipped (after the CI-robustness fix of the F2 lock test). The skipped test runs PR #86's validator from a scratch checkout of `bab1a4d`; it
  passed locally.
- Full repository suite: 2,147 passed, 133 skipped, and 1 error, the known local Q019 E2BIG, which also fails on clean
  main (1,970 passed, 132 skipped, the same error).
- `nightshift.protected` passes on every changed path. Code: `manhattan/hte/`. Tests: `tests/test_manhattan_hte_core.py` and
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
| run | `HR-` | registry root × data hash × code digest × policy hash × window × stages × execution timing × numerical environment | `run_started`; packages count `runs_on_this_registry` |
| independent statistical tests | **not computed** | `null`, with a reason, everywhere | owner decision D-1 of PR #86 |

Each child record holds its parent's full hash, so a link cannot change without changing the child's identity
(the same rule as `manhattan/spec.py`). The canonical form is `manhattan.spec.canonical_bytes`, reused as is.
Under that form `5` and `5.0`, and `0.5` and `0.50`, are the same value. Key order does not matter.

Code identity and data identity are attributes of an **attempt**, not of a candidate. The same registered candidate
can be evaluated with several code versions or synthetic datasets, and each such evaluation is a separate counted
look. This matches PR #86's attempt identity, which keeps `spec_hash`, `data_hash` and `code_version` as separate
fields.

A Manhattan executable (`AX-`) folds the code version into its spec, and PR #86 decides evaluation, rerun or
nondeterminism by `(spec_hash, data_hash, window id)` alone. The adapter therefore maps an HTE evaluation to PR #86
at two levels (S11, §7): the code-free **binding** (the scientific evaluation) and the **executable** (binding +
engine digest + numerical environment), whose hash is PR #86's `spec_hash`. A new engine or environment is a new
executable of the same binding, as a bug-fixed code version is a new executable of the same Manhattan variant.

## 3. Registry (stage 0)

`registry.Registry.submit(bundles)` validates whole strategy specs (`registry.validate_bundle`). It checks the
following:

- record levels and parent hashes;
- the domain and the template version;
- every grid value against the template's schema (type, range, choices);
- duplicate grid values, which would register duplicate candidates;
- that each point's look-back fits the warm-up;
- the template's **PIT probe** (§6.4), logged as `pit_probe` with its probe panel and coverage. A stored result is
  reused only for the same template version, template and feature code, and probe panel, and only if it had full
  coverage. The canonical probe always runs; a caller's `probe_panel` can add a probe, never replace it;
- templates marked `test_only`, which are refused unless `submit(..., allow_test_templates=True)` is passed. The
  allowance is recorded in the segment (S10 F1).

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

It also computes, per family, **partial maxima of Hansen's SPA statistics**. Every variant of a family shares one
bootstrap index set (the Protocol's joint bootstrap, from `manhattan.stats.bootstrap`), drawn from a seed that is a
hash of the family's identity and the evaluation (data, window, B, L, methodology) only (`runner.boot_seed`). The
seed does not depend on the registry root, so registering or freezing other specs never re-draws a family's
bootstrap (S10 F6). Because of that shared set, a family's SPA statistics are maxima over its variants. Floating-point `max` is exact, associative and
commutative, so partial maxima from any chunking combine to the bit-identical family statistic. The result equals
`manhattan.stats.spa.spa_test` on the same draws (tested).

The stored series hashes let stage 4 recompute any series and prove that it describes the series of record.

**Family sign.** Templates are written for the `+` direction. A `-` family holds exactly the negated positions
(`runner.signed_positions`, the one place positions enter an evaluation), so a family is always evaluated in the
direction it predicts (S10 F5).

**Execution timing (S10 F8).** A position set from data through the close of day t is assumed traded *at* that close
and earns day t+1's return (`kernels.EXECUTION_TIMING`). PR #85 executes at the settlement of the lag-th close
strictly after a decision (lag >= 1), so HTE is optimistic by one day by construction. The convention is part of
every run identity and every package. Packages state that their use is restricted to synthetic throughput and
pipeline testing, with `realistic_return_claims: false`. The PR #85 boundary (`adapters.Pr85ExecutionAdapter`) is
disabled; §7 describes it.

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

**One writer per workspace.** Every writer holds an exclusive `flock` on `<workspace>/.lock` (`log.locked`) while
it writes. The writers are `Runner.run`, `Registry.submit` and `Registry.freeze`, and the operating system releases
the lock if the process dies. A second concurrent writer is refused.

Two further rules keep stale objects safe:

- A writer reloads from the log under the lock before writing.
- `AttemptLog.append` re-reads the file whenever its size changed since this object last read it, so an object
  built before another writer ran can never append a stale `seq` or `prev_hash`.

Reading tolerates a torn final line and never changes the file. Only a writer, under the lock, quarantines it. The
quarantine copy is fsynced before the cut, and a copy that a crash left unrecorded is logged on the next recovery
(`recovered_after_crash`). A disk preflight, at about 3x the
measured bytes per candidate, refuses a run that cannot fit and logs `run_refused`.

**Fail closed.** Stage 3 does not start while any candidate lacks a completed stage-1/2 attempt. The run logs
`run_incomplete` instead.

**Repeated runs.** A closed run invoked again logs `run_reused`. With `verify_rerun=True`, the engine recomputes every
chunk as a *verification* attempt and compares every field bit-for-bit with the attempt of record for the same
range, SPA partial maxima included. A difference gives the verification attempt its terminal (`attempt_failed`,
reason `nondeterminism`), logs `nondeterminism` and raises. A verification that completes must also rebuild the
closed `result_root`, and then logs `run_verified`. Results and packages of record are never rewritten.

**Run identity** is the registry root, data hash, engine digest, policy hash, window, requested stages, execution
timing and numerical environment. A stage-1-2 run and a full run of the same candidates are therefore two counted
looks.

**Numerical environment (S10 F9).** `ids.numeric_environment()` records:

- the NumPy and Python versions;
- the BLAS name, version and build configuration;
- for an OpenBLAS DYNAMIC_ARCH build, the kernel chosen at run time;
- NumPy's SIMD dispatch targets and the machine type.

Its hash is part of the run identity, so chunks computed in different environments are never mixed. If an unfinished
run of the same candidates, data, code, policy and stages exists under another environment, a new run is refused
(`environment_mismatch_refused`). The caller must resume it where it started, or explicitly start a separate run
(`allow_new_environment=True`, logged `environment_changed`). A run is bound to the frozen
version whose root is in its identity. `Runner(registry_root=...)` resumes an interrupted run after a newer freeze,
and `reconcile` and `history` always use the run's own version.

**Failures and snapshots (S10 F4).** Under the workspace lock, a runner reloads its registry from the log before any
work. It checks that its frozen version and its families are unchanged; the lock keeps other writers out until the
invocation ends. Any exception in an invocation logs `run_failed` with its phase and error class before it
propagates.

**Reconciliation.** `runner.reconcile(ws, run_id, anchor)` reads only persisted records and the files they name,
with hashes verified. The close record is the authority (S10 F3). A run is in one of three states:

- **`closed`:** `results.bin` carries the hash in `run_closed`, it rebuilds bit for bit from the hash-verified attempt
  files through the same `build_results_table` the runner uses, and every package matches its recorded hash.
- **`corrupted`:** a close record exists, but an artifact fails one of those checks. The integrity violations are
  named.
- **`incomplete`:** there is no close record. A results file found without one is never read as of record and is
  reported as `unrecorded_results_file`.

It also reports failed invocations. It checks the following and returns counts and violations:

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
| bootstrap means | a matrix product's per-column bits depend on the other columns (measured) | pass B runs in family-major order (`selection.b_order`). Products run on fixed groups of at most 64 candidates *of one family* (`kernels.BOOT_GROUP`), and pass-B chunks are whole groups. The same group is always the same product, and no family's groups depend on another family's candidates (S10 F6) |
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
| shared rolling features (momentum, EWMA vol, z-scores, rolling extremes, carry means, unit-risk scale, \|r\|), computed once per process | `features.FeatureCache` | 68,319 hits per 231 misses at 10^4 candidates (1 worker); 4.2 million per 1,496 at 10^6 |
| parent warm-up before forking: workers inherit features copy-on-write | `Runner._warm` | no feature is computed twice |
| disk cache keyed by data hash, feature, parameters and feature-code hash, verified on load | `FeatureCache` | corrupt entry: quarantined, recomputed, logged; never changes a result (tested) |
| behavioural dedup: alias candidates skip stage 3 | selection | 16.9% of the 10^4 workload, 39.4% of the 10^6 workload |
| vectorised vol-target recursion across a chunk (time-major, masked coefficients) | `kernels._scales` | the Python loop runs over days once per chunk, not once per candidate |
| grouped BLAS-3 bootstrap | `kernels.stage3_boot` | 0.09 ms vs 0.71 ms per candidate |
| sliding-window process pool (fork), intent before dispatch | `Runner._execute` | 3.3-3.4x on 4 workers |
| bounded stage 4: M_eff on at most `meff_cap` series per hypothesis (outcome-blind stride), parallel | `package._run_meff` | cost independent of N |
| positions recomputed in pass B rather than stored | design | storing would cost about 180 KB per candidate (2,220 days x ~10 assets x 8 B; about 180 GB at 10^6) |

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
   `designated=False`. The **binding** (`adapters.evaluation_binding_hash`) is the hash of
   `adapters.evaluation_spec`, which holds the candidate, the family sign, the template version, the resolved cost
   coefficients, the sizing constants, every policy field, the window, the stages, the execution timing and the
   methodology (S10 F7). `spec_hash` and `executable` are the hash of `adapters.executable_spec`: the binding plus
   `engine_sha256` and `numeric_environment_sha256` (S11), and `code_version` carries both digests. PR #86's key
   `(spec_hash, data_hash, window id)` therefore separates engines and environments: a new one is an `evaluation`,
   never a `rerun` of another engine's look nor a `nondeterminism` that suspends the family, while the same
   executable keeps PR #86's rerun and nondeterminism rules. `adapters.lineage` lists every level and
   `adapters.executable_accounting` counts completions, looks, executables and the scientific units (family,
   hypothesis, variant, candidate, binding) separately; families whose result changed across executables of one
   binding are held. Tests: `tests/test_manhattan_hte_identity_levels.py` (the PR #86 cases need PR #86 merged).

   Two evaluations that differ in any evaluation-affecting parameter never share an identity (tested field by
   field). The identities were checked against PR #86 at `bab1a4d` in a scratch checkout: its
   `validate_attempt_identity` accepts them and its `same_identity` distinguishes every variant
   (`test_f7_identities_validate_against_pr86_and_never_collide`, run with `HTE_PR86_CHECKOUT`; skipped in CI).
2. **Lifecycle mapping.**

   | HTE record | PR #86 equivalent |
   |---|---|
   | `attempt_started` | `register_*` start |
   | `attempt_completed` | `completion` / `commit_results` |
   | `attempt_failed` (reason class) | terminal `failed` with `execution_error` |
   | `attempt_interrupted` | terminal `aborted` with `interrupted` |
   | `supersedes` | `supersedes` / `retry_of` |

   Data read is always true for a completed or failed chunk.
3. **Evidence classification (PR #84).** An HTE result would classify as provenance `SYNTHETIC` and eligibility
   `E_INFRA` (synthetic provenance always gives `E_INFRA`, weight 0; never `E_DESCRIPTIVE`), with authorization
   `AUTH_OPEN` (exploration-role dates). `*_eligible` and `promotion_authorized` are false. An HTE package is not
   `classify` input today: its schema (`manhattan.hte.package/1`) is not `manhattan.evidence/3`, and it carries no
   frozen-spec block, verifier results or PR #86 attempt reference, so `classify` returns `unverified` / `none`.
   (S11 correction: this item previously said "at most `E_DESCRIPTIVE`" and `AUTH_NONE`.)

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

**PR #85 boundary (disabled, S10 F8).** `adapters.Pr85ExecutionAdapter` and `adapters.to_pr85_decisions` refuse. The
intended mapping:

- HTE position row t (data through close t) becomes a PR #85 `Decision(root, contracts, decided_at=close t,
  inputs_known_at=close t)`, with `ExecutionPolicy(lag >= 1)`;
- contracts come from target weight × capital / (price × point value), rounded by PR #85.

Blockers E1-E4:

| id | blocker |
|---|---|
| E1 | PR #85 is unmerged |
| E2 | the timing conventions differ |
| E3 | PR #85 evaluates one position plan at a time, so it would be a new, heavier stage 3 run only on representatives |
| E4 | PR #85 is uncalibrated, and HTE has no contract-level synthetic market |

HTE imports nothing from `manhattan.execution` (tested).

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
- **Pool broken at submit.** A new lost-worker test showed that the pool can break between completions, so
  `submit()` itself raises after the intent is written. That intent now gets a `worker_lost` terminal.

**Independent read (a separate reviewer agent given the code, not my conclusions).** It reported 12 findings. I
checked each against the code. All but #11 were real, and all were fixed with regression tests. #11 is documented
instead: parameters a template ignores create candidates with identical economics, which behavioural dedup catches
at stage 1, not stage 0.

| # | finding | fix |
|---|---|---|
| 1 | a runner or registry object built before another writer ran could append a stale `seq`/`prev_hash` and fork the chain; registry writes took no lock | shared lock; reload under the lock; `append` re-reads a changed file |
| 2 | runs and `reconcile` used the latest freeze, stranding interrupted runs after a new freeze | runs bound to their root; `registry_root=` resumes |
| 3 | `stages` was missing from the run identity, so a stage-1-2 run masked a later full run | added |
| 4 | family numbering came from every registered spec, not the run's frozen view | fixed |
| 5 | **behavioural aliases crossed families, shrinking a family's SPA variant set and so overstating evidence; a renamed family evaded the duplicate and post-look flags** | dedup is family-scoped; the semantic digest excludes family and hypothesis text; family and hypothesis records refuse extra fields; packages report cross-family semantic and behavioural duplicates with a "not independent" warning; post-look is detected by economics as well as by family |
| 6 | verification skipped the SPA fields and could "close" without completing; `reconcile` ignored nondeterminism | full-field comparison, `run_verified`/`verification_failed`, new violations |
| 7 | a verification rerun rewrote packages of record | it no longer closes; it verifies |
| 8 | PIT probe results were reused across template code changes | keyed by code hash |
| 9 | the fence was not bound to the panel identity | `verify_synthetic` checks it |
| 10 | `supersedes` could omit a failed attempt after a partial retry | names every overlapping failed or interrupted attempt |
| 12 | torn-tail recovery was not crash-atomic | fsynced copy before the cut; unrecorded copies logged later |

Neither review is a substitute for an independent human reviewer. Its findings are limited by my own model of the system.

## 9. Independent review S10: ten findings and their corrections

S10 reproduced the 10^6 benchmark and found five merge blockers (F1-F5), four activation and integration blockers
(F6-F9) and reporting inaccuracies (F10). Each defect was reproduced in this session before it was fixed, except F8
and F10, which are a convention and text. Each has a regression test whose name starts with `test_f<N>_`.

| # | finding | reproduction | correction |
|---|---|---|---|
| F1 | PIT look-ahead bypass: a short `probe_panel` gave a passing probe with **0 checks**, reused later | a leaky test template registered with `checks: 0, passed: true`, then registered again without a probe | full coverage required; probe results keyed by panel; canonical probe always runs; stored zero-check passes never reused; `test_only` needs an explicit, recorded allowance |
| F2 | orphaned workers kept the inherited `flock` after the parent was killed: resume refused for ever | `kill -9` of the parent left 2 workers; resume raised "another runner" | `os.register_at_fork` closes lock descriptors in every child; pool workers exit with the parent (`PR_SET_PDEATHSIG` plus a `getppid` watchdog); tested with SIGKILL |
| F3 | a rewritten `results.bin` passed reconciliation even with an anchor | stage-3 means inflated in a valid file: `violations: []` | close hash checked; table rebuilt from attempt files; packages checked; states `closed`/`corrupted`/`incomplete` |
| F4 | a runner built before another writer registered a spec crashed in stage 4, with nothing recorded | `KeyError` in stage 4; log ended at `attempt_completed` | registry snapshot under the lock; `run_failed` with phase for every failed invocation |
| F5 | negative-sign families evaluated in the positive direction | a `+` and a `-` family had identical gross means | `signed_positions`: exact negation; odd statistics mirror exactly; planted effect found only in the predicted direction |
| F6 | unrelated registrations re-drew every family's bootstrap (seed included the registry root) | carry `p_c` 0.643 → 0.617, trend 0.517 → 0.536 after adding one commodity spec | seed bound to family and evaluation identity; family-major bootstrap groups; old candidates bit-identical after an unrelated registration |
| F7 | PR #86 identity collision across policies or costs | two policies gave identical identities | `evaluation_spec`; validated against PR #86 `bab1a4d`. Residual (S11): engine and environment were outside PR #86's key; now in `spec_hash` via `executable_spec` |
| F8 | same-close execution, unlike PR #85's delayed execution | by design (timing convention) | convention in run identity and packages; use restricted to throughput testing; disabled PR #85 boundary |
| F9 | no numerical environment in the identity; cross-environment resume possible | identity held the engine digest only | environment (NumPy, BLAS build and run-time kernel, SIMD, machine) in the run identity; cross-environment resume refused |
| F10 | reporting: log records vs attempts, registration time, CPU vs billed vCPU-hours, computed vs aliased simulations, null calibration | as reported | BENCHMARKS.md rewritten from records that state each quantity separately; package null note corrected (the null share is far below 5% because returns are net of costs) |

The review also exposed a fault in my own F2 fix: the parent-death watchdog was installed in the main process when
`workers=1`. A fork-with-threads warning revealed it, and it was corrected before commit.

This round's corrections, like the earlier ones, have not been independently re-reviewed.
