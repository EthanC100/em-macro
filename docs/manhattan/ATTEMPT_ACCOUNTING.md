# Phase 4A-1a: partial implementation and architecture gate

Starting main: `5781bca521577381e150814eceb308003685ccee`.
This is a lifecycle foundation, not complete research-access accounting. No scientific
rule, decision threshold, protected file, production control or schedule changes.

## Architecture gate and caller audit

1. Existing evaluation-start record hashes can identify individual executions without
   a new ID allocator. Existing completion types retain same-key rerun detection.
2. The existing hash chain supports terminal records. Its existing `verify` plus an
   independently retained anchor detects deletion (including suffix deletion) and edits.
   No second hashing implementation is needed.
3. Reader currently knows caller/domain/fence, but neither ledger nor specification.
   Window is directly constructible. Making only Reader require IDs would not close
   the evaluation boundary. Logging reads must not turn them into statistical tests.
4. Engine `evaluate` writes `Ledger` evaluations, but operational `screen` writes
   `Store` screening intents and `observation_intents` writes daily forward observations.
   Store has its own transaction/recovery/idempotency semantics. Neither calls
   `start_evaluation` or `record_evaluation`. A parallel JSONL ledger would create
   non-atomic cross-store writes and ambiguous interruption recovery.
5. Lifecycle checking can reuse `verify`. Complete access reconciliation additionally
   needs persisted access provenance in the operational transaction and an anchored
   batch boundary. This PR deliberately does not certify access completeness.

Production callers and their meanings:

| Caller | Access and evaluation path | Treatment here |
|---|---|---|
| `factors/reproduce.py`: `_window`, `reproduce`, variant loop | Exploration Reader windows, then engine `evaluate`; some windows used for diagnostics/backtests | unchanged |
| `ops/runner.py`: `screen` | Exploration Reader then backtest and private Store screening records | unchanged |
| `ops/runner.py`: `observation_intents` | `ops/data.forward_window`, backtest, per-date observation/missed-observation intents | unchanged |
| `engine/evaluate.py`: `evaluate` | Takes already-open Window; calls `record_evaluation` | unchanged; legacy unlinked records remain readable but fail strict lifecycle audit |
| `ledger.py`: `start_evaluation` | Previously used only by registry tests, not runtime callers | extended compatibly |

`forward_window` is the documented OPS_PROGRESS R-1 adapter: its history includes
pre-freeze signal warm-up that ordinary one-role Reader access refuses. Replacing it
with mandatory Reader calls would break nightly forward evidence or alter its fence
semantics. It must retain per-observation provenance and reconstruction rules.
Reserve Reader authorization remains RunnerToken/check_read; no production reserve
engine caller was found. Tests use direct Window construction for synthetic PIT,
compiler, engine and reconstructed-evidence checks; these are not all hypothesis tests.
The PIT integrity, phase3b/3c and engine tests exercise legitimate diagnostic access.
Registry tests directly exercise legacy completion and rerun APIs.

## Implemented lifecycle

The start record hash is the attempt ID. Starts retain executable/family/batch/spec/data/
window and supplied variant/hypothesis/role/channel/code identities. Completion accepts
an explicit attempt ID, or links the unique matching active start for compatibility.
An ambiguous start requires an explicit ID. Legacy calls without starts remain supported;
the strict audit refuses to certify them rather than inventing retrospective starts.

`end_attempt` accepts only failed/aborted status and a fixed reason classification;
there is no free-form exception or performance payload. A retry names `supersedes`,
must match all recorded identity fields (including code version), and can only target
an unfinished, not already superseded attempt. The old start stays unfinished, cannot
later complete, and remains counted. Completed unfavorable results cannot be superseded.
A separate later execution still passes through unchanged rerun/nondeterminism rules.

`reconcile_lifecycle(path, anchor=...)` audits persisted records, not cached objects.
It rejects unregistered/duplicate terminals, contradictory identities, invalid retries,
and chain damage. At close, registered = completed + failed + aborted + unfinished.
Retries are a subset of registered executions; distinct specifications are counted
separately. Neither count changes `looks()` or constitutes a multiple-testing rule.
The return value always says `access_reconciled: false`. It writes no batch-close
record and exposes no performance values. Existing historic key-based `unfinished`
compatibility is retained; strict audit requires explicit completion linkage.
Ledger remains a single-writer API; this adds no concurrent transaction guarantees.

## Capture v2

New definitions declare integer schema version 2. Recorded missing/malformed/other
versions fail before replay with recorded and expected versions. Same-version publication
configuration mismatches retain their existing error. An absent definition retains
existing unverified replay behavior: no migration or authentication is performed.
Existing version-1 captures will fail replay; an owner must decide their disposition.

## Blocked requirements and owner decisions

Reader access logs, mandatory reserve/forward attempt authorization, exploration access
logs, access-gap detection and full batch reconciliation are NOT implemented. No passing
access-accounting tests are claimed. User adversarial cases 1–3, 6, 13–14 remain blocked
as new accounting features (existing non-evaluation/PIT compatibility tests still run).
Cases 4–5, 7–12 and 16 are covered for the lifecycle/schema subset; case 15 uses existing
PIT tests. Full cross-path coverage of these cases remains outstanding.

Smallest proposed next integration: store attempt/access/terminal intents within the
existing operational Store transaction, with prediction/spec/batch and run-attempt IDs;
use a dedicated audited signal-history authorization tied to registration for forward
warm-up. Bind engine evaluation windows to active Ledger starts separately. Retain
check_read and per-observation provenance, and anchor both stores at close. Owner review
must settle the execution boundary for incremental daily evidence versus recorded
statistical evaluations before implementing the cross-store reconciliation contract.
This is not a request to change any scientific threshold or protected protocol.

## Continuation recovery

The interrupted session's six uncommitted files and validation logs were recovered
on `codex/manhattan-phase4a-1a`; no PR existed for that branch. Current main at
continuation was `cb3ec77b9af1f9b6a9a9b1c97dd6a2a06e63a524`, two Janus-record commits
after the starting main. The branch is preserved without a rebase.

Continuation review fixed a lifecycle compatibility edge case: a legacy unlinked
rerun after a linked retry must not hide the original superseded attempt from
`unfinished()`. The strict audit still refuses to certify that unregistered rerun.
The additional regression exercises that exact sequence.

## Local validation

- Continuation targeted lifecycle/schema/registry run: 57 passed, exit 0 (24 new
  regression cases plus 33 existing registry cases).
- Final full suite on the final code: 1,864 passed, 131 skipped, 248 warnings,
  exit 0, 672.38 seconds. Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
  MANHATTAN_RUNNER_WHEELHOUSE=/tmp/manhattan-wheelhouse python -m pytest -q`.
  The wheelhouse was downloaded with the existing lock's required hashes.
- Recovered Q019 targeted run: 86 passed, exit 0; Q019 also runs in the final suite.
- Recovered PIT/engine/operations/Q019 run: 490 passed, 1 failed, exit 1. The exact
  failure was `test_hash_locked_runner_in_clean_environment`: pip reported
  `ProxyError`, `Operation not permitted`, fetching `/simple/certifi/`. That test
  passed with network access (1 passed, exit 0) and in the final offline suite.
- Recovered initial full-suite log: 1,862 passed, 131 skipped, the same 1 failed.
  Its process exit status was not retained after interruption; the log records
  failure. It is superseded by the final verified exit-0 run above.
- Protected-path checks on all six paths and `git diff --check`: exit 0.

These are local results. Remote CI status is reported separately on the draft PR.
