# The nightly runner (public-data families)

Code: `manhattan/ops/runner.py`, `data.py`, `compiler.py`. Workflow: `.github/workflows/manhattan-ops-runner.yml`.
Tests: `tests/test_manhattan_ops_runner.py`, `tests/test_manhattan_ops_workflow.py`, `tests/test_manhattan_ops_e2e.py`.

**State: committed with its schedule disabled.** It runs only when started by hand from main
(`workflow_dispatch`). No session starts it (CLAUDE.md rule 16). Enabling it is Ethan's:
[ETHAN_OPS_ACTIONS.md](ETHAN_OPS_ACTIONS.md) step 9.

## One run

```
open       clone manhattan-ledger with the deploy key; recompute the hash chain (stop if broken)
reconcile  finish every journal entry a crash left unfinished
lock       append and push a lock record; a live lock elsewhere stops the run (status "locked")
missed     every weekday since the last heartbeat with no completed run -> missed_run
capture    fetch each source; store the raw bytes and a capture record BEFORE evaluating
evaluate   rebuild point-in-time data from first-seen captures; for each registered prediction, run its executable
           over warm-up + forward days; record each new complete day (or missed_observation past the grace period)
heartbeat  a heartbeat record with the day's counts
unlock, private log, mirror, mirror verification, then one public health record
```

Each step is idempotent: a second run on the same day adds nothing. A failure is reported publicly by stage and
exception class; the run releases its lock and mirrors what it has. A source that fails is recorded
(`capture_failed`) and the run is `partial`.

**First seen.** A value's availability is the day the runner first saw it (moved to the next day if seen after the
close), or its nominal publication day for history that existed before monitoring began. A later different value
for the same period is a revision: counted, never used. Observations whose marks (or whose base day's marks) were
captured after the grace period are `reconstructed`, weight 0.

**Warm-up.** A forward strategy needs history (a 120-day momentum needs 120 days). `manhattan.roles.check_read`
allows one role per read and has no "signal input" role, so the runner opens its window through an adapter
(`data.forward_window`, request R-1 in OPS_PROGRESS.md). Returns on or before a prediction's first observation are
computed in memory and never recorded.

**Sources.** FRED H.10 (`DEXBZUS`, `DEXMXUS`, `DEXSFUS`: BRL, MXN, ZAR, spot only, grace 10 days because FRED posts
the dailies weekly) and the synthetic source used by tests. The FRED fetcher was written but **not run** from this
session; the first real run is its first test.

**The workflow.** Dispatch only, main only, concurrency group `manhattan-ops-ledger` (no cancellation),
`contents: read` and `issues: write`, secrets held in the environment `manhattan-ledger` whose deployment branches are
`main` only (so a branch copy of the workflow cannot receive them), checkout without persisted credentials, deploy keys written to files with mode
600 under `$RUNNER_TEMP/private` with GitHub's host key pinned, no artifact, pip cache only, everything private
removed at the end. On failure it opens or comments on `[ALERT] Manhattan ops runner failed` with the health record.
It does not run `nightshift.guard`: it never writes em-macro, so it cannot collide with em-macro's writers.

**Not built.** A watchdog for a runner that never starts (the next run records the gap as `missed_run`); the iMac
runner; a public anchor file.
