# Binding attempt accounting, verified at the runner's real entry point

Session "Manhattan operational path", 2026-11-25, branch `claude/manhattan-operational-path-7zaf0s`. Paper-only,
synthetic data only. Tests: `tests/test_manhattan_ops_entrypoint.py` with its process harness
`tests/manhattan_runner_harness.py`.

## Question and answer

**Does the nightly runner use PR #86's binding attempt accounting end to end?** Yes, from its real entry point.
`python -m manhattan.ops.runner nightly` (what `.github/workflows/manhattan-ops-runner.yml` runs) goes
`main` → `_run_cli` → `nightly`, which, after the lock, recovers interrupted attempts (`access.commit_recovery`),
registers one forward-observation attempt per prediction in one journalled, remotely verified write
(`access.register_store_attempts`, with the `VerifiedFence` from `config/manhattan.yaml` at the run's commit), opens
windows only through those attempts (`data.forward_window` → `AttemptContext.forward_window`), computes once per
attempt from the registered specs (`access.run_bound`), and writes observations together with their terminals in one
journalled write (`access.commit_results`). A handled failure closes the attempts as `failed: execution_error`
(reason class only); a death leaves them unfinished, and the next run aborts them as `interrupted` with
`data_read: null`; the retry names its predecessor in `retry_of`.

**What was missing before this session:** every test drove `runner.nightly(...)` in-process. Nothing exercised the
CLI (argument parsing, `RunConfig` construction, the `GITHUB_SHA` commit default, the health file, exit codes)
in a separate process, and the CLI could not run on synthetic data at all: it built fetchers for FRED sources only,
so `--sources synthetic` silently became a `capture_failed`. A hard process death (no handler, no `finally`) had
never been tested; the in-process crash tests raise `SimulatedCrash`.

## What changed

| change | why |
|---|---|
| `runner.py`: `--rehearsal` and `--rehearsal-clock` on `nightly` and `register`; `rehearsal_guard` | lets the real entry point run on the synthetic source against a local bare repository, so the always-on runner can be rehearsed and tested in a separate process |
| `rehearsal_guard` refuses `synthetic` without `--rehearsal`, any non-synthetic source with it, any remote or mirror that is not an existing local bare repository, and `--rehearsal-clock` alone | fails closed before anything is opened: synthetic data can never enter the private ledger through the CLI, and a rehearsal can never reach it (`test_synthetic_data_and_real_ledgers_are_kept_apart_at_the_entry_point`) |
| `tests/manhattan_runner_harness.py` | runs `runner.main(argv)` in a fresh process; adds read probes and hard deaths (`os._exit(137)`) only |

The production workflow passes neither flag, so its behaviour is unchanged.

## Evidence (each run a separate process through `runner.main`)

| property | test | how it is shown |
|---|---|---|
| every attempt is registered, durable **on the remote**, before its first protected value is read | `test_entry_point_registers_every_attempt_before_its_first_protected_read` | at the first `Window._known` of each attempt (where the read meter counts a read before any value leaves) the harness clones the remote afresh and finds the start record; one probe per attempt, all `forward`, all durable; reconciler: `access_reconciled: true` |
| results and terminals are committed together | `test_results_and_their_terminals_are_one_remote_commit_and_one_journal_entry` | walking the remote's git history, each `attempt_completed` and every `new` result it links first appear in the same commit and the same journal entry; the start is in an earlier commit |
| hard death after a protected read, then restart | `test_hard_kill_after_a_protected_read_then_restart` | exit 137, no health file; starts on the remote, no terminal, no observation, reconciler false. The workflow-style re-run (same run id, attempt 2) breaks the dead attempt's lock, aborts each attempt as `interrupted` with `data_read: null`, registers retries naming them in `retry_of`, records the observations; exactly one terminal per attempt; reconciled; executions = 2 × predictions |
| hard death while committing results | `test_hard_kill_while_committing_results_keeps_results_and_terminals_together` (after the journal `pending` push; after the records push) | after the pending push: neither results nor terminals on the remote; after the records push: both. The restart's journal recovery finishes the entry; no crashed attempt is also aborted; the observation set equals an uninterrupted reference run's |
| duplicated work: same-day rerun | `test_same_day_rerun_is_a_second_execution_with_duplicate_results_only` | no new evidence record; the rerun is a second set of registered executions whose every linked result is `duplicate` |
| duplicated work: a concurrent second process | `test_a_second_process_during_a_live_run_is_locked_out_and_registers_nothing` | process A holds the lock (paused); process B exits 1 with `status: locked` and registers no attempt; A then completes; reconciled |
| public output | `test_public_output_of_the_entry_point_is_the_health_record_only`, `test_step_summary_and_failure_notification_carry_no_private_value` | stdout is one health line, stderr empty; the step summary, the health file and the failure-issue body (`runner issue-body`) contain no value of the private ledger, including when a failure's exception text carries one; the failure's terminals carry the reason class only; the value is in the private log |

**The tests can fail.** Each guarantee was broken in the code and the matching test failed (then the code was
restored):

| mutation | failing test |
|---|---|
| attempt starts appended locally instead of the journalled, pushed write | registration-before-read (the durability probe is false) |
| results and terminals written in two journal entries | one-commit/one-entry |
| no attempt recovery after the lock | hard-kill-then-restart |

## Limits (unchanged from BINDING_ACCOUNTING.md section 1)

- The guarantees hold through the supported APIs; hostile code in the process, or a holder of the ledger's deploy
  key who rewrites records consistently, is outside them.
- `screen` (historical screening) has no CLI or workflow; it is exercised in-process only
  (`test_screening_is_registered_and_linked`). Engine evaluations (`manhattan.engine.evaluate`, the Ledger path) have
  no production caller (gate G-3).
- Activation gates G-1..G-6 and blockers B-1..B-3 are not lifted: forward observations are recorded, they do not
  count as evidence.
