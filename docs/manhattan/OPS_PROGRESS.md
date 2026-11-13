# Manhattan operations: progress (session 7M, "7M Manhattan ops: first research cycle")

Branch `build/manhattan-ops`. New code is under `manhattan/ops/`, new documents under `docs/manhattan/ops/`, tests in
`tests/test_manhattan_ops_*.py`, measurements in `results/manhattan_ops/`. Nothing in `manhattan/stats/`,
`manhattan/sim/`, `PROTOCOL_*`, `SIM_PREREG*`, `MANHATTAN_PROGRESS.md` or any protected path is edited. Shared engine and
registry code (`manhattan/spec.py`, `ledger.py`, `roles.py`, `critic.py`, `freeze.py`, `generate/`, `engine/`) is
imported only; where it needs a change, the change is listed under "Requests to the shared code" below and an
adapter in `manhattan/ops/` does the job meanwhile.

## Baseline

| item | value |
|---|---|
| created from | `origin/build/manhattan` at **`0e52bdb4343f5daeeec989dfbb69f4840e8589c1`** (2026-11-12 18:42 UTC, "Manhattan E: carry and time-series momentum reproduced on public data, core-factor proposal, session state") |
| milestone D present | yes: the merge of PR #54 (`b0ec9c3`) is an ancestor; `manhattan/spec.py`, `ledger.py`, `roles.py`, `critic.py`, `freeze.py`, `generate/` exist |
| milestone E present | yes: commits `49c9082`, `e134ebd` and `0e52bdb` (PR #56, unmerged); `manhattan/engine/pit.py`, `accounting.py`, `backtest.py`, `events.py`, `lookahead.py`, `evaluate.py` and `manhattan/factors/` exist |
| main at the time | `8aa6520` (D merged; E not on main) |
| read first | `CLAUDE.md` (rules 15 and 16), `docs/manhattan/ARCHITECTURE.md`, `docs/manhattan/PROTOCOL_v3.md`, `docs/manhattan/ETHAN_ACTIONS.md` |

## Ground rules for this session

No protected path, no real batch, no real hypothesis, no schedule enabled, no spending, no private or licensed data in
this repository, no workflow dispatched (and no session asked to dispatch one). The new workflow is committed with
its schedule disabled (`workflow_dispatch` only). The full suite runs with `set -o pipefail` and its exit code is
read before every push (rule 15).

## Acceptance criteria

Written before each component's tests. "Met" means a named test asserts it.

### Component 1: outcome blinding by access control (`manhattan/ops/blinding.py`, `promotion.py`, `leakscan.py`)

| id | criterion |
|---|---|
| O-01 | Forward and screening performance is written only to the private ledger (a separate private repository, `manhattan-ledger`, written by the runner's deploy key). The only thing the runner may emit on a public channel (stdout, stderr, the step summary, an issue body, an exit message) is a **health record**: a mapping whose keys come from a fixed allow-list and whose values are integers, dates, ISO times, 64-hex hashes, short identifiers or enumerated status words. A float anywhere in it, or an unknown key, is refused before anything is printed |
| O-02 | While the runner works, file descriptors 1 and 2 are redirected to a private log inside the private clone, so that print statements, warnings, library output and tracebacks cannot reach the public log. An exception is reported publicly as stage name and exception class only; the message and traceback go to the private log |
| O-03 | Every private record carries a 128-bit random nonce, so a published chain-head hash cannot be used to confirm a guessed outcome by brute force |
| O-04 | Promotion to any tier is refused in code: `promotion.promote` raises unless the protocol hash is in `ADOPTED_PROTOCOLS` (empty in this branch; adopting is Ethan's edit of a file he protects) **and** `claims.enabled` is true in `config/manhattan.yaml` |
| O-05 | Adversarial test: a synthetic run with fingerprinted performance values (a successful run and a run forced to fail with values in its exception message) is followed by a search of every output channel (the public repository's tree, every blob in its git history, captured stdout and stderr, the step summary, the failure-issue body, the runner's temporary directory outside the private clone, and an artifacts directory) for those values in every common rendering (repr, 4 to 17 significant digits, fixed decimals, percent, basis points). The test fails if any is found. The scanner is shown to catch a canary planted in each channel |
| O-05b | The runner workflow uploads no artifact, saves no cache other than pip's download cache, and checks out em-macro without persisted credentials; a test reads the YAML and asserts it |

### Component 2: freeze validity separate from authorisation (`manhattan/ops/timing.py`)

| id | criterion |
|---|---|
| O-06 | For every prediction the registration record holds: specification hash, registration time, its sources (GitHub merge time from the API's `merged_at`, external witness time), data cutoff, prediction horizon, execution lag, declared first observation (if any), the computed first eligible observation, eligibility and the reason |
| O-07 | The registration time is the **later** of the GitHub merge time and a verified external witness time (OpenTimestamps or equivalent): the spec provably existed by then if either source is honest. A missing or unverified witness makes the record `provisional`; it is re-evaluated when the witness arrives and may become ineligible, recorded as a new record |
| O-08 | The first eligible observation is the first market observation (a session close on the family's calendar, in the market's own time zone) strictly after registration time plus execution lag, then moved forward by any lag in sessions. A prediction is prospective only if, at registration, its outcome window had not begun (the first observation's close is after registration) and no value inside the outcome window had been published (publication time after registration, for data published after the close) |
| O-09 | Eligibility is enforced automatically: a declared first observation earlier than the first eligible one, a data cutoff at or after registration, a data cutoff inside the outcome window, or a witness later than the declared window start makes the prediction ineligible with a named reason. Ineligible predictions are recorded and tracked with evidential weight 0; none is dropped |
| O-10 | Tested edge cases: a merge on a Saturday; the day before a market holiday (US Thanksgiving, Good Friday on an exchange calendar but not on the Federal Reserve calendar); a merge one minute before and one minute after the close; the same UTC time on either side of a daylight-saving change; a value published after the close (the close passed but the value is unpublished: still ineligible); a late merge after the declared window began; a lag that pushes the first observation over a weekend; a witness that arrives after the declared start |

### Component 3: generator isolation test kit and blind template (`manhattan/ops/isolation_kit.py`, `docs/manhattan/ops/BLIND_GENERATOR.md`)

| id | criterion |
|---|---|
| O-11 | One standard-library-only script, run inside a candidate generator environment, checks and reports on each channel: network access; clone access to em-macro, em-macro-data and manhattan-ledger; readable files and mounts outside its repository and in the home directory; leftover local artifacts and caches; environment variables and credential helpers (git, gh, tokens, SSH keys, netrc), reporting names only, never values; the tools and MCP servers available (configuration files, binaries, and a tool list the operator declares); inherited context (CLAUDE.md anywhere up the tree or in the home directory, past-conversation and memory stores, project `.claude/` files); indirect channels (package caches, temporary directories, shell history, the repository's own git remotes and history) |
| O-12 | It prints `PASS` only if every forbidden channel is closed; otherwise `FAIL` (a channel open) or `INCOMPLETE` (a channel that needs the operator's declaration was not declared), with a per-channel report and exit codes 0, 1 and 2. Tested: in a synthetic clean sandbox it prints PASS; each channel opened in turn makes it FAIL; run in this session it fails (recorded) |
| O-13 | The blind-generator template exists (prompt v2 with the variant-justification and timing fields, its SHA-256 record, the repository layout and run procedure for a separate environment) and says plainly that model pretraining cannot be removed by isolation: blind-channel hypotheses are blind to Manhattan's results, not to history the model has read. No real hypothesis is generated |

### Component 4: durable, recoverable ledger (`manhattan/ops/store.py`)

| id | criterion |
|---|---|
| O-14 | Authoritative store: append-only, hash-chained records in a git repository (the private ledger; a local bare repository stands in for it in tests). Every record carries provenance: data source, retrieval time, runner run id and attempt, em-macro commit |
| O-15 | Concurrency: the workflow has a concurrency group with `cancel-in-progress: false`, and each run appends a lock record and pushes it before any other write; an unexpired lock held by another run stops the run; an expired lock is broken by a `lock_broken` record naming it; a lost push race on the lock stops the run |
| O-16 | Idempotency: the key of an observation is `(prediction id, observation date)` and every record type has a key. Appending a key already present with the same content is a no-op; with different content it is refused and a `conflict` record is written; the earlier record is never overwritten |
| O-17 | Atomic writes: a non-fast-forward push is retried by fetching, resetting the local clone to the remote, and re-appending the intended records (duplicates fall away by key). The code never force-pushes; a test checks the source for `--force` and `+refs` |
| O-18 | Write-ahead journal: each batch of records goes through `pending` (journal line pushed before the records), `committed` (records and journal line pushed together) and `verified` (re-read from a fresh fetch). Each run starts by reconciling every unfinished entry: records missing from the chain are appended, records present are checked, then the entry is marked verified |
| O-19 | Backup: after each run the ledger is pushed to a mirror (any git remote; options for Ethan in `docs/manhattan/ops/LEDGER.md`), by fast-forward only. Verification recomputes the hash chain of both copies and compares heads; a mirror that is not a prefix of the primary is reported as tampering |
| O-20 | Missed days are recorded as `missed_run` (a weekday with no completed run) or `missed_observation` (data not available by the grace deadline), never as success. Data that arrive after a gap are recorded flagged `reconstructed` with evidential weight 0 |
| O-21 | Crash test: a run is crashed at every stage (after the lock, after the local journal write, after the journal push, half-way through writing the chain file, after the local commit, after the push, after verification, half-way through the mirror push, before the unlock). After each crash a fresh run recovers, and the final set of records (keys and outcome content) equals that of a run that never crashed: nothing duplicated, nothing missing, every earlier record byte-identical, the chain and the mirror verify |
| O-22 | The documentation states that private repositories may need GitHub Pro for branch protection, and that tamper evidence then comes from the hash chain, external timestamps of the head, the published head hash and the mirror |

### Component 5: evidence-aware variant limits (`manhattan/ops/justify.py`, `critic_rules.py`)

| id | criterion |
|---|---|
| O-23 | Every grid parameter with more than one value must carry, in the hypothesis's `grid_justification`, the economic reason it varies and the range the mechanism implies (numeric `[low, high]` or the list of admissible values). The mechanical critic rejects a dimension with no reason, a reason that is only a generic phrase, or a value outside the stated range |
| O-24 | The compiler reports for each grid: raw variant count, an effective count (Li-Ji on the correlation of the variants' returns on exploration data, from `manhattan.stats.meff`, or the raw count when no data are given), and the expected loss of power of a max-type test from searching it (single test against the Šidák critical value for the effective count, at θ_min over a stated window length), labelled an approximation |
| O-25 | Above a default budget (16 raw variants per hypothesis, an ops default for Ethan to change) a hypothesis must carry a recorded `budget_justification`; without it the critic blocks. Every variant is counted in the manifest's counts either way |
| O-26 | Interfaces stream: variants and executables are produced by iterators and counted without being materialised, so nothing in the interfaces stops at 1,000,000 executables. No scaling work is done beyond the first cycle's needs |

### Component 6: compiler, runner, critic draft, freeze tooling

| id | criterion |
|---|---|
| O-27 | Compiler: a hypothesis spec with a structured `signal` (`kind` and parameters), a `frequency` (`D`, `W`, `M` or `event`) and a primary binding compiles each variant into an engine `Strategy` at that natural frequency, with the family's sign applied, the universe's instruments, the cost model and the sizing rule. Compilation is deterministic, refuses unknown kinds, universes, cost models and sizing rules, and refuses parameters outside each kind's schema |
| O-28 | A compiled executable run through the engine on a hand-made price path gives hand-checked positions (one test per signal kind), and passes the engine's look-ahead check |
| O-29 | Forward windows: the runner reads warm-up history before the first eligible observation as signal input only; no return dated on or before the first eligible observation is recorded |
| O-30 | Nightly runner (`python -m manhattan.ops.runner nightly`): reconcile, lock, missed-run detection, **first-seen capture before evaluation** (raw bytes stored with SHA-256 and retrieval time before any value is used; revisions never change a first-seen value), evaluation of registered public-data predictions, journalled idempotent writes, checkpoints, heartbeat record, unlock, mirror, verification, health record. A second run on the same day adds nothing |
| O-31 | Workflow `.github/workflows/manhattan-ops-runner.yml`: `workflow_dispatch` only (the schedule is present as a comment), every job guarded to `refs/heads/main`, concurrency group with `cancel-in-progress: false`, read-only `contents` permission on em-macro, `issues: write` for the failure issue only, deploy key from a secret written to a file with mode 600 and a pinned host key, no artifact, no output cache. A failure opens or comments on one issue whose body is the health record only |
| O-32 | Draft critic agent at `docs/manhattan/ops/drafts/manhattan-critic.md` (tools: Read only, reads the batch's critic input only, returns The Opposition's JSON with the allowed block reasons and the unjustified-dimension check) for Ethan to install under `.claude/agents/` |
| O-33 | Freeze tooling (`python -m manhattan.ops.freeze_pr`): runs the mechanical critic, refuses a blocked batch, builds the manifest with `manhattan.freeze.prepare`, adds an ops manifest (timing declarations, variant report, template hash), writes the batch folder and a pull-request body that says merging authorises the freeze but does not certify timing. It commits nothing and pushes nothing |

### Component 7: end-to-end proof (`tests/test_manhattan_ops_e2e.py`)

| id | criterion |
|---|---|
| O-34 | A synthetic batch of 10 families (labelled SYNTHETIC, generated by a mock generator from the blind request, no model) goes through critic, compile, freeze, screening on labelled exploration data (synthetic, to 2019-12-31, recorded only in the private stand-in), registration with eligibility checks (including deliberately late predictions, recorded as ineligible) and two nightly cycles, the second crashed half-way through writing and then recovered |
| O-35 | Records are immutable (every record of cycle 1 is byte-identical after cycle 2 and the recovery; an attempt to overwrite one is refused and recorded as a conflict); recovery is exact (the crashed-and-recovered ledger has the same keys and outcome content as an uncrashed reference); nothing leaks to the public stand-in (the O-05 scan over all channels) or to the generator (the blind request after the cycles is byte-identical to the one before, and the generator's sandbox holds no ledger value) |

### Component 8: capacity (`manhattan/ops/capacity.py`, `results/manhattan_ops/CAPACITY.md`)

| id | criterion |
|---|---|
| O-36 | Measured wall time, CPU time and peak resident memory for 1,000, 10,000 and 100,000 executables, for a full backtest and for one nightly increment separately, on synthetic data, with the machine and worker count stated. Measurements only: no extrapolation is reported as a measurement |

## Requests to the shared code (not edited here)

Each has an adapter in `manhattan/ops/` meanwhile. None was edited by this session.

| id | shared code | request | adapter |
|---|---|---|---|
| R-1 | `manhattan/roles.py` | a "signal input" read for the runner: forward strategies need history before their first observation, but `check_read` allows one role per read and, with the default fence, the dates between the exploration cut-off and a freeze are embargoed | `data.forward_window` opens the window as the runner, labelled forward; returns on or before the first observation are never recorded |
| R-2 | `manhattan/critic.py` | add `unjustified_dimension` (and the mechanical reasons `budget_exceeded_without_justification`, `missing_timing`, `not_compilable`) to `BLOCK_REASONS` | `critic_rules.OPS_BLOCK_REASONS`; the critic draft lists `unjustified_dimension` |
| R-3 | `manhattan/generate/`, `manhattan/templates/` | template v2 (variant justification, timing, structured signal) beside v1, and `blind_request` for it | `mockgen.blind_request` with `manhattan/ops/templates/blind_v2.md` and its own hash file |
| R-4 | `manhattan/freeze.py` | a freeze authorised by Ethan's merge, with timing certified by the API merge time and a witness, as an alternative to the signed tag (which a cloud session cannot check) | `runner.load_batch` checks canonical form, every spec hash and the Merkle root; `timing.assess` certifies timing |
| R-5 | `manhattan/ledger.py`, ARCHITECTURE §4.1 | the public index may hold `screening_decision` and `tier_change` records, and ARCHITECTURE suggests the full ledger could live in em-macro-data (readable by any session that attaches it, the Janus sessions included). Under this session's blinding, em-macro holds health only and the full ledger lives in `manhattan-ledger`. The two designs should be reconciled before a screening decision is ever published | the ops store is separate; `PublicIndex` is not used |
| R-6 | `manhattan/engine/backtest.py` | marks are read at the window's end, so a vendor revision would change a past return; an option to mark with first-seen values only | the runner builds its store from first-seen values only; a recomputed day that differs is a `conflict`, the first record stands |
| R-7 | `manhattan/engine/evaluate.py`, decision 33 | exploration evaluations write their Sharpe ratio to `results/manhattan_engine/exploration_log.csv` in this public repository. Exploration results are open by ARCHITECTURE §6, but if "screening performance never in em-macro" is meant to cover exploration screening too, that log should move to the private ledger | `runner.screen` records privately and does not call `log_variant` (hard rule 6 binds the explorer, which does not run this) |

## Decisions taken in this session

| # | decision | why |
|---|---|---|
| O1 | Development on `build/manhattan-ops`, as asked, not on the session's default `claude/...` branch | the brief named the branch |
| O2 | The public channel accepts no float at all (not just "no outcome key") | an allow-list of kinds is checkable; a deny-list of keys is not |
| O3 | Registration time is the **later** of merge time and witness time | the spec provably existed by then if either source is honest; a late witness can only make a prediction ineligible |
| O4 | A provisional registration (no verified witness) has evidential weight 0 | conservative until the second source arrives |
| O5 | Availability of a first-seen value is the retrieval day, moved to the next day when retrieved after the close | a value seen after the close cannot have informed that close's decision |
| O6 | An observation is reconstructed when its own marks or its base day's marks were captured after the grace period | a return depends on both ends |
| O7 | Each private record carries a 128-bit nonce | the head hash is published; without a nonce a small outcome space could be brute-forced |
| O8 | The deploy keys live in a GitHub Environment restricted to `main` | repository secrets reach a dispatched run on any branch |
| O9 | Default variant budget 16 per hypothesis | small enough that a typical one- or two-parameter grid fits, large enough not to force justification of every grid; Ethan's to change |
| O10 | The runner does not call `nightshift.guard` | it never writes em-macro, so it cannot collide with em-macro's writers; the guard's window and cap are the night shift's |
| O11 | `ETHAN_ACTIONS.md` is not edited; the ops steps are in `docs/manhattan/ops/ETHAN_OPS_ACTIONS.md` | the parallel 6M session works on that file |

Queue: no change to `docs/queue.md` (not touched; night-shift files are dev's).

## Status

Session 7M, 2026-11-13. Nothing is in force: no batch, no real hypothesis, no schedule, no dispatch, promotion
disabled in code.

| id | status | evidence |
|---|---|---|
| O-01, O-02, O-03 | **met** | `tests/test_manhattan_ops_blinding.py` (health record refuses floats, free text, unknown keys; fd-level redirect catches print, stderr, `os.write` and a child process; failure is stage and class only; 128-bit nonce) |
| O-04 | **met** | `test_every_promotion_is_refused_in_this_branch`, `test_promotion_needs_both_the_adopted_hash_and_claims_enabled` |
| O-05 | **met** | `tests/test_manhattan_ops_e2e.py::test_no_performance_value_in_any_public_channel` (repo tree, every git object, log, step summary, issue body, runner temp outside `private/`, artifacts; a failing run with values in its message) and `test_the_scanner_would_have_caught_a_leak_in_each_channel` |
| O-05b | **met** | `tests/test_manhattan_ops_workflow.py` |
| O-06 to O-10 | **met** | `tests/test_manhattan_ops_timing.py` (12 first-observation edge cases and the ineligibility reasons) |
| O-11, O-12 | **met** | `tests/test_manhattan_ops_isolation.py` (clean sandbox PASS; each of 8 channels opened in turn FAILs; undeclared tools INCOMPLETE). Run in this build session it prints **FAIL on all 8 channels**, as it must (network through the proxy, `git ls-remote` of em-macro succeeds, tokens in the environment, CLAUDE.md and `.claude/`, a past-conversation transcript, tools beyond the allowed set) |
| O-13 | **met** | `manhattan/ops/templates/blind_v2.md` and its hash; `docs/manhattan/ops/BLIND_GENERATOR.md` |
| O-14 to O-21 | **met** | `tests/test_manhattan_ops_store.py` (provenance, idempotency and conflicts, chain and tamper detection, journal states, non-fast-forward retry, no force push, locks, mirror; a crash at each of 9 stages with exact recovery) |
| O-22 | **met** | `docs/manhattan/ops/LEDGER.md` |
| O-23 to O-26 | **met** | `tests/test_manhattan_ops_compiler.py` (justification, budget, effective count, power loss, streaming) |
| O-27 to O-29 | **met** | `tests/test_manhattan_ops_compiler.py` (one hand check per kind, sign flip, look-ahead check passes for four kinds, refusals); `tests/test_manhattan_ops_runner.py` (no return on or before the first observation) |
| O-30 | **met** | `tests/test_manhattan_ops_runner.py` (rerun adds nothing, capture before observation, revision never replaces first-seen, missed then reconstructed, source failure partial, lock, failure releases lock) |
| O-31 | **met** | `.github/workflows/manhattan-ops-runner.yml`, `tests/test_manhattan_ops_workflow.py`. Not run: it is never dispatched |
| O-32 | **met** | `docs/manhattan/ops/drafts/manhattan-critic.md` (not installed) |
| O-33 | **met** | `test_freeze_tooling_prepares_and_refuses` |
| O-34, O-35 | **met** | `tests/test_manhattan_ops_e2e.py`: 10 SYNTHETIC families, 14 hypotheses, 27 executables; 23 eligible and 4 deliberately late (recorded, weight 0); a missed Friday run; cycle 2 crashed half-way through the chain write and recovered to the same content as an uncrashed reference; cycle-1 records byte-identical afterwards; an overwrite refused as a conflict |
| O-36 | **met** | `results/manhattan_ops/CAPACITY.md` |

**Capacity (measured, 4 CPUs, 4 workers, synthetic data).** Full backtest over 2005-2019: 1,000 executables 57 s
wall (203 CPU-s); 10,000 in 582 s (2,211 CPU-s); 100,000 in 6,128 s (23,822 CPU-s); peak RSS 47-48 MiB per
process. Nightly increment: 1,000 in 1.9 s; 10,000 in 26 s; 100,000 in 265 s (1,019 CPU-s); 44-46 MiB. Ledger write
of one night: 1,000 records 0.4 s; 10,000 in 2.5 s; 100,000 in 26 s with 951 MiB peak (the whole chain is held in
memory; fine for the first cycle, the first thing to change before a six-figure night).

**What did not work first time (fixed before any push).** The crash test never fired at first (the torn-write
point counted duplicates, which write no line); an event strategy crashed when an instrument had no events; the
generic-reason check ran after the length check; justification failed on the canonical form's decimal strings;
the isolation kit merged the host environment into its git check; the mirror lagged after a failed run. Test-side
mistakes: a data cutoff after the registration dates, a stage expectation for the mirror crash, a canary too small to
render with five significant digits, conflict hashes that legitimately differ by nonce.

**Not done.** No real batch, hypothesis or dispatch (by design); the FRED fetcher has never run against FRED; no
watchdog for a runner that never starts; no OTS stamping of the head; the iMac runner. Full suite after merging `origin/build/manhattan` at `c914421`: **1477 passed, 132 skipped, pytest exit code 0** (run with `set -o pipefail`, exit code read from `${PIPESTATUS[0]}`); the run before the merge had one failure, a stale e2e assertion about the mirror, fixed before any push.

**Exact next step.** Ethan: steps 1 to 4 of `docs/manhattan/ops/ETHAN_OPS_ACTIONS.md` (repository, deploy key in a
main-only environment, App access, mirror), then merge this pull request after `build/manhattan` (it contains
milestone E), then step 9's single manual run.
