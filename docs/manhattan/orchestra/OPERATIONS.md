# Manhattan orchestra: unattended operation of synthetic research jobs

Status: **research infrastructure, synthetic jobs only, not in force.** Session S15, 2026-11-19. Code:
`manhattan/orchestra/`. Tests: `tests/test_manhattan_orchestra.py` (unit and guards) and
`tests/test_manhattan_orchestra_failures.py` (real processes, failure injection).

The orchestrator queues, runs, watches, stops and recovers long-running **synthetic** jobs: the HTE engine
(PR #89), the Manhattan simulation's development scenarios (`manhattan.sim.run`), and a toy job used by the tests. It
sits *above* those engines and drives them only through their public entry points. It changes nothing in them, in
any protected path, in `config/manhattan.yaml`, `trials.csv`, a ledger or a writer's data.

It adds what the engines do not have: a queue, a supervisor that survives its own crashes, bounded retries,
cancellation, wall-clock, memory, output and budget limits, an external anchor for the engines' logs, a run
manifest, and a status surface.

## 1. What each layer guarantees

| layer | owns | guarantees |
|---|---|---|
| engine (HTE, sim) | attempts inside one run | intent before work, atomic result files, interrupted attempts marked on resume, results bit-identical after any resume (HTE ARCHITECTURE §5; SIM_PREREG §6) |
| **orchestrator** | jobs and invocations | one open invocation per job, intent before every action, every invocation ended with an outcome, bounded retries, limits, an anchor of the engine's log after every invocation, manifests, status |
| person | decisions | registering a new *look* after a code or environment change, requeueing a failed or blocked job, raising a limit (code review), every activation |

## 2. Job lifecycle

```
                register ─────────────► queued ◄──────────────── requeue (incomplete, cancelled,
                (duplicate refused)       │  ▲                     error-capped failure, some blocks)
                                          │  │ not_before passed
                      slot, workers,      ▼  │
                      budget, disk ──► launching ──► running ──► invocation ended ──► decide()
                      switches open        │            │                                │
                                           └─ cancel ──►cancelling ──────────────────────┤
                                                                                          ▼
   completed │ retry_wait (back-off) │ incomplete (invocation cap) │ failed │ blocked │ cancelled
```

| status | category | meaning |
|---|---|---|
| `queued`, `retry_wait` | **queued** | waiting for a slot, workers, the budget, disk or its back-off |
| `launching`, `running`, `cancelling` | **active** | an invocation is open |
| `completed` | **completed** | the last invocation succeeded and reconciliation found the run closed and clean |
| `incomplete` | **incomplete** | the invocation cap was reached; all work so far is kept and counted |
| `failed` | **failed** | an integrity violation, a refusal, or `max_consecutive_errors` errors in a row |
| `blocked` | blocked | needs a person: code, environment or packages changed since registration (a new look), a root moved to another machine, or a second invocation detected |
| `cancelled` | cancelled | cancelled by a person; work so far is kept |

**Registration.** A job is a kind (`smoke`, `hte`, `sim`), its normalised parameters, and a look number. Its id is
`OJ-` followed by the first 16 hex digits of the hash of those three. The supervisor refuses a second registration of
the same id and journals the refusal as `duplicate_registration`. Running the same parameters again needs
`--look N`, which makes the repeat explicit and counted. Registration records the execution manifest's identity, and
by default refuses a tree whose code paths differ from the commit (`require_clean_tree`).

**Invocation.** One process (`python -m manhattan.orchestra.child`) runs one bounded piece of a job:

- it holds the job lock throughout;
- it recomputes the manifest and refuses to run if the identity changed;
- it verifies the engine's log against the anchor journaled after the previous invocation;
- it runs the engine, which resumes from its own log;
- it reconciles from persisted files and writes `exit.json`.

**Outcomes and what follows** (`supervisor.decide`):

| outcome | how it is known | next |
|---|---|---|
| `done` | exit 0 *and* reconciliation `closed`, no violations | completed |
| `unfinished` | exit 75, or exit 0 without a closed run | retry at once |
| `timeout` | deadline marker: the invocation's monitor stopped it at its wall-clock limit | retry at once (the engine continues) |
| `interrupted` | SIGTERM not from the orchestrator (shutdown) | retry at once |
| `cancelled` | a cancellation was requested | cancelled |
| `error`, `lost`, `lost_before_start`, `memory_exceeded`, `log_limit_exceeded`, `spawn_failed`, `no_progress` | exit code, markers, or a free lock with no `exit.json` | retry after exponential back-off; `failed` after `max_consecutive_errors` in a row |
| `integrity` | the anchor does not match, or reconciliation reports `corrupted` | failed (never retried; a person looks) |
| `refused` | an engine or kind refusal (exit 78) | failed |
| `blocked`, `duplicate_refused`, `foreign_host` | identity changed, or another process holds the job lock, or the invocation ran on another machine (machine id, not hostname) | blocked |

After any retryable outcome, a job that has used `max_invocations` becomes `incomplete`, not looping. An
`unfinished` or `timeout` invocation that added nothing to the engine's log (HTE, toy job) or replication files (sim)
counts as `no_progress`, an error, so a job that cannot advance stops after three tries.

A cancellation requested while an invocation runs turns only retryable and error outcomes into `cancelled`. An
integrity failure, a refusal or a block reported by that invocation is kept, so it stays on the attention list and
is not requeueable.

## 3. Restarts cannot duplicate or lose scientific attempts

| risk | guard | test |
|---|---|---|
| the same job queued twice | job id = hash(kind, normalised params, look); duplicate refused and journaled | `test_duplicate_registration_is_refused…` |
| two invocations of one job at once | supervisor starts only with no open invocation **and** a free job lock; the child refuses if the lock is held (`duplicate_refused` → blocked); HTE's workspace lock is a third guard | `test_a_second_supervisor_and_a_second_invocation_are_both_refused` |
| two supervisors on one root | supervisor `flock`; a second tick returns `skipped` | same test |
| supervisor crash between intent and spawn | `invocation_intent` is journaled first; without a process holding the lock after `launch_grace_s` → `lost_before_start` | `test_intent_without_a_process…` |
| supervisor crash between the invocation directory and the intent | the stray directory is renamed `inv-NNNN.orphan-k` (kept) and journaled; the root is never wedged | `test_a_directory_left_by_a_crash…` |
| supervisor crash after spawn | the child writes `pid.json` under the lock; the next supervisor adopts it (`adopted: true`), so there is no second spawn | `test_supervisor_crash_after_spawn_is_adopted_not_duplicated` |
| invocation killed (SIGKILL, OOM, power) | `pid.json` read before the lock is probed, then a free lock with no `exit.json` → `lost`; leftover processes of its group are killed only if their command line names this invocation's directory and the boot is the same; the engine marks the cut attempts `attempt_interrupted` on resume and names them in `supersedes` | `test_hard_crash_is_retried…`, HTE test, §8 |
| failed evaluations lost | nothing is deleted: the engines keep `attempt_failed`/`attempt_interrupted`; the journal keeps every invocation's outcome; work directories are never rewritten | `test_repeated_errors_fail_the_job_and_every_failed_attempt_stays_recorded` |
| an engine log truncated or replaced between invocations | the orchestrator journals the engine log's anchor `{records, head}` after every invocation (HTE keeps none of its own, ARCHITECTURE §5); the next invocation verifies it first; a mismatch fails the job on integrity | `test_log_truncated_between_invocations…` |
| results tampered after completion | `audit JOB` re-reconciles against the anchor; a corrupted audit is on the attention list | `test_audit_detects_tampering_after_completion` |
| resume under other code or numerics | manifest identity compared at every invocation → `blocked: code_changed / environment_changed / packages_changed`; HTE also refuses itself (S10 F9) | `test_code_change_between_invocations_blocks_the_job` |
| the orchestrator's own journal damaged | hash chain; torn tail quarantined with its hash; `verify --anchor` against a copy of `status.json`'s `journal` field kept elsewhere | `test_journal_*` |

## 4. Resources, concurrency and cancellation

Limits are in `manhattan/orchestra/limits.py`. The code defaults are ceilings. `<root>/limits.json` can only
**tighten** them: a loosening value is refused, not clipped, and a cap of 0 is refused because 0 would switch a check
off. Raising a ceiling is a reviewed change to that file. The file is re-read at every tick, so tightening takes
effect within one tick. An invalid file stops new starts until it is fixed; running jobs stay supervised under the
last good limits, and the problem is journaled and shown by `health`.

| limit | default | enforced by |
|---|---|---|
| `max_running_jobs` | 2 | supervisor (job slots) |
| `max_total_workers` | 8 (and at most the CPU count) | supervisor; head-of-line wait, so large jobs are not starved |
| `max_workers_per_job` | 8 | registration |
| `max_memory_mb_per_job` | 12,000 MB aggregate RSS of the process group | the invocation's monitor (1 s poll) kills the group, `memory_exceeded` |
| `max_wall_minutes_per_invocation` | 360 | monitor: SIGTERM at the deadline, SIGKILL after `cancel_grace_s`; supervisor as a second line |
| `max_log_mb_per_invocation` | 200 MB of output | monitor, `log_limit_exceeded` |
| `max_invocations_per_job` | 50 | decide → `incomplete` |
| `max_consecutive_errors` | 3 | decide → `failed` |
| `monthly_vcpu_hours` | 3,000 reserved vCPU-hours per UTC month | supervisor: an invocation starts only if its worst case (workers × wall limit) fits beside the month's booked use and the *whole* window of every open invocation; an invocation's use is booked to the month it ends in |
| `monthly_budget_sgd`, `price_sgd_per_vcpu_hour` | S$500, S$0 (owned hardware) | supervisor: spend cap when a price is set |
| `min_free_disk_mb` | 2,048 | supervisor; HTE's own disk preflight as well |
| back-off | 60 s doubling to 3,600 s | decide |

Every child runs BLAS and OpenMP single-threaded (the workers are the parallelism, and the thread count is part of
the numerical identity).

**Cancellation** (`cancel JOB`) is journaled first. A queued job is cancelled at once and never runs. For a running
job, the next tick writes a `cancel` marker and sends SIGTERM to the invocation process only. The child turns that
into `KeyboardInterrupt` in its main thread:

- the toy job records its cut attempt as `attempt_interrupted` (reason `cancelled`);
- HTE logs `run_failed` and drains its in-flight chunks;
- the simulation finishes the replications in flight and logs `interrupted`.

After `cancel_grace_s` the tick sends SIGKILL to the group. Every attempt the engine had started is recorded. A
cancelled job can be `requeue`d, and the engine continues from its log.

**Hosts.** Process facts come from `procs.py`:

- **Linux:** `/proc`.
- **macOS:** `/bin/ps`, `/sbin/mount`, `/usr/sbin/sysctl` and `/usr/sbin/ioreg`. They are called by absolute path
  with a fixed `PATH` and `LC_ALL=C`, because cron's and launchd's default `PATH` (`/usr/bin:/bin`) leaves out
  `/usr/sbin` and `/sbin`.

These facts cover group memory, leftover-process cleanup, the network-file-system check, and boot and machine
identity:

- **Boot identity:** `kern.bootsessionuuid`, falling back to the seconds of `kern.boottime`, never its local-time text.
- **Machine identity:** `IOPlatformUUID` or `/etc/machine-id`. When either identity is unknown it is `None`. A `None`
  never makes an invocation `foreign_host` and never blocks cleanup, because the command-line match guards cleanup.

Liveness rests on the job lock (local `flock`), never on the hostname, which macOS changes with the network.

A run root whose file-system type is network, automounted or user-space, or cannot be read at all, is refused (fail
closed). That covers `smbfs`, `afpfs`, `webdav`, `nfs`, `autofs`, `macfuse`/`osxfuse`, every `fuse.*`, and Linux's
network types. The macOS parsing is tested with recorded `ps`, `mount`, `ioreg` and `sysctl` output (§13). It has not
yet been run on a Mac (§13 lists what only a Mac can settle).

**Pausing.** `pause` (journaled) or `touch <root>/PAUSE` (a kill switch that needs no lock) stops new starts.
Running invocations continue; cancel them separately if needed.

## 5. Status and monitoring

`status.json` is rewritten by every tick. `python -m manhattan.orchestra status --json` builds the same snapshot from
the journal without a lock. Schema `manhattan-orchestra/1` (`status.py` docstring). It holds:

- counts by category (`active, queued, blocked, failed, incomplete, completed, cancelled`);
- per job: status, reason, invocations, last outcome, live progress from the invocation's monitor (for HTE: pass-A
  and pass-B candidates done, of the total; for sim: replications on file, of the target), the reconciliation state
  and counts, reserved vCPU-hours and CPU seconds;
- the attention list;
- the month's budget use;
- the journal's own anchor and every job's engine-log anchor;
- `evidence: null`.

It holds no research statistic, no parameter value beyond the job label, and no environment variable.

Ways to check it remotely, none of which publishes anything:

1. **`health`**: one line, with exit code 0 (fine), 1 (attention) or 2 (supervisor silent for 10 minutes while
   work is queued). Suits cron mail, a phone notification script, or a launchd job.
2. **Loopback HTTP**: `python -m manhattan.orchestra --root R http --port 8765` serves `GET /`, `/status.json`
   and `/health` (503 when unhealthy) on 127.0.0.1 only; other addresses are refused. From a laptop or phone, use
   `ssh -L 8765:127.0.0.1:8765 host`, or a private overlay network bound to loopback.
3. **Copy the file**: `status.json` is small, so `rsync`/`scp` it from the host. Keep the copies: their `journal` and
   `anchors` fields are the off-host anchors that make truncation of the journal or an engine log detectable.

## 6. Reproducible execution manifests

Each invocation writes `inv-NNNN/manifest.json`. Registration writes `jobs/<id>/manifest.json`. A manifest records:

- **code**: commit, dirty flag, and the SHA-256 of the working-tree content of every file under `manhattan/` and the
  requirement files (tracked and untracked-not-ignored), so an uncommitted edit changes it;
- **numerical environment**: Python, NumPy, SciPy, the BLAS/LAPACK build and configuration, SIMD baseline and
  dispatch, machine, CPU model, and the fixed thread settings;
- **packages**: every installed distribution and its version;
- **job spec**: kind, normalised parameters and look.

`identity` (these four hashes) must match at every invocation. HTE and the toy job compare all four. The simulation
compares code and spec only, because its replications pool by code hash and its seeds depend on the replication
number alone (SIM_RUNBOOK: pieces from different machines are the replications one machine would make).

For HTE, the engine's own run identity additionally includes the OpenBLAS kernel chosen at run time.

## 7. Cost against a S$500/month budget

**Measured workloads:**

| workload | compute | source |
|---|---|---|
| HTE, 10^6 candidates, full funnel | 0.49 reserved vCPU-h (7.4 min on 4 vCPU) | `docs/manhattan/hte/BENCHMARKS.md` §6 |
| HTE, two 10^5-candidate jobs side by side through the orchestrator (2 workers each, one killed and resumed) | 91 s wall in all (§8) | this session |
| Simulation: the whole pre-registered development programme | about 2,000–2,200 CPU-h | `docs/manhattan/SIM_RUNBOOK.md` §1 |

**Prices are assumptions**, read on 2026-11-19 from third-party trackers and provider pages, and are not quotes.
Rates: 1 USD ≈ 1.29 SGD and 1 EUR ≈ 1.42 SGD. `python -m manhattan.orchestra cost` recomputes the table.

| option | the 2,200 CPU-h programme | monthly cost | notes |
|---|---|---|---|
| owned hardware (iMac, 8 cores) | about 12–13 days | S$0 marginal | the default; `price_sgd_per_vcpu_hour = 0` |
| GitHub public runners (manhattan-sim.yml) | about 1.5 days at 20 jobs | S$0 | already exists, started by Ethan from main; logs public; synthetic only |
| Hetzner AX42 dedicated (8 cores/16 threads) | about 6 days | about S$138/month + S$70 setup, excl. VAT | flat rent paid whether used or not (EUR 97.30 after the June 2026 adjustment) |
| AWS c7a.2xlarge on demand (8 vCPU) | about 11.5 days on one instance | about S$145 for the programme | US$0.41/h; storage and egress extra |
| AWS c7a.2xlarge spot | as above | about S$57–67 | US$0.16–0.19/h; an interruption is an ordinary `lost` → resume; pin the instance type (HTE refuses a resume in another numerical environment) |

**Conclusions:**

1. HTE is negligible at any scale considered: 100 runs of 10^6 candidates a month is about 50 vCPU-hours.
2. The simulation programme is the only material compute. It fits the budget on any option, and it costs nothing on
   owned hardware or GitHub's public runners.
3. The cheapest unattended path is the iMac under this orchestrator, with the default `price_sgd_per_vcpu_hour = 0`,
   `monthly_vcpu_hours = 3000` as a runaway brake, and `max_total_workers` at cores − 1.
4. If a rented machine is ever approved, set `price_sgd_per_vcpu_hour` (it can only go up) so that the S$500 spend cap
   binds, and set `monthly_vcpu_hours` below `500 / price`.

Renting anything is Ethan's decision; this session rented nothing and spent nothing.

## 8. Test results (this session)

Run on 2026-11-19 in the session container (Python 3.13.18, NumPy 2.5.3):

| run | result |
|---|---|
| orchestra tests on Linux after the second re-review (§14) | **90 passed, 3 skipped**: the 3 skips are the real-macOS tests, which run only on a Mac |
| orchestra tests on macOS (CI job `orchestra-macos`, GitHub-hosted Mac) | see §14 and the PR's checks |
| full repository suite on this branch | see the PR description and its `tests / pytest` check |

Failure injection covered:

- hard crash mid-attempt;
- repeated exceptions up to the error cap;
- the invocation cap, then requeue;
- a hung attempt stopped by the deadline;
- cancellation of a running job, then requeue;
- cancellation of a queued job;
- the memory cap;
- a supervisor crash after spawn (adoption);
- an intent with no process;
- a second supervisor and a second invocation;
- an engine log truncated between invocations;
- tampering after completion (audit);
- a code change between invocations;
- the budget, spend, disk, pause and switch holds;
- secrets absent from the child's environment, read from `/proc/<pid>/environ`.

**HTE end to end, through the orchestrator, on the PR #89 engine.** Two identical 10^5-candidate jobs (looks 0 and
1, 2 workers each) ran side by side. The second job's whole process group was killed with SIGKILL at 24,320 of
99,552 candidates in pass A:

| job | invocations | attempts (completed / interrupted) | result_root | violations |
|---|---|---|---|---|
| look 0, clean | `done` | 685 / 0 | `3c26657bd405b3ed…` | none |
| look 1, SIGKILL mid-run | `lost`, `done` | 685 / 4 (kept, superseded) | `3c26657bd405b3ed…` | none |

At 10^4 candidates, both looks gave result root `79d00a98…`, the value BENCHMARKS.md records for that workload.

## 9. Operating it

```bash
export MANHATTAN_ORCHESTRA_ROOT=~/manhattan-orchestra          # outside the checkout, on a local disk
python -m manhattan.orchestra init
echo '{"max_total_workers": 7, "max_running_jobs": 2}' > "$MANHATTAN_ORCHESTRA_ROOT/limits.json"   # tighten only
python -m manhattan.orchestra register hte --params '{"target": 1000000, "workers": 4}'   # once PR #89 is merged
python -m manhattan.orchestra register sim --params '{"scenario": "D05", "size": "STD", "reps": 2000, "workers": 3}'
python -m manhattan.orchestra serve --interval 30          # or: tick from a timer, below
python -m manhattan.orchestra status                       # table; --json for the snapshot
python -m manhattan.orchestra health                       # one line, exit 0/1/2
python -m manhattan.orchestra cancel OJ-…   |   requeue OJ-… [--extra-invocations N]   |   audit OJ-…
python -m manhattan.orchestra pause --reason "maintenance"  |  unpause  |  touch "$MANHATTAN_ORCHESTRA_ROOT/PAUSE"
python -m manhattan.orchestra verify --anchor '{"records": N, "head": "…"}'   # from an off-host status copy
```

**Unattended.** Pick one. They are examples, and this session installed none of them.

- cron: `* * * * * cd ~/em-macro && python -m manhattan.orchestra tick >> ~/manhattan-orchestra/tick.log 2>&1`
  plus `*/30 * * * * … health || <notify>`.
- launchd (macOS): a `KeepAlive` job running `python -m manhattan.orchestra serve`, in the style of
  `scripts/com.horizons.manhattan.sim.plist.template`, under `caffeinate -i`.
- systemd (Linux): a user service running `serve`. For a hard memory ceiling on all jobs together, run it under
  `systemd-run --user --scope -p MemoryMax=14G -p CPUQuota=700%`. The orchestrator's own memory cap is a 1-second
  RSS poll, not a kernel limit.

The supervisor can be stopped and restarted at any time. Invocations run in their own sessions, keep running, and
are adopted by the next tick.

**Working directory layout** (under the root):

```
journal.jsonl  status.json  limits.json  PAUSE
jobs/<OJ-id>/job.json, manifest.json, .run.lock
            work/                       the engine's workspace (HTE: work/hte; sim: work/sim_out; smoke: attempts.jsonl)
            inv-0001/invocation.json manifest.json pid.json progress.json exit.json output.log [markers]
```

Nothing is ever deleted by the orchestrator. Cleaning a finished job's work directory is a person's decision. The
journal keeps its manifest hash and anchors either way.

## 10. Boundaries (what it cannot do)

- **Kinds are an allowlist** (`kinds.KINDS`), and every parameter is validated strictly. Unknown keys are refused.
- **HTE:** stage 5, test templates, policy overrides, performance gates, `allow_new_environment` and `registry_root`
  are not reachable from a job.
- **Simulation:** held-out scenarios (`H*`), `--confirm`, `--pooled-rerun` and `--plan` are refused. Its output goes
  to the job's own directory, never to `results/manhattan_sim/`.
- **Manhattan switches:** `config/manhattan.yaml` is read, never written. No invocation starts while it fails
  validation, or while any switch is out of its conservative position (`safety.ALL_OFF`):
  - `freeze.authority` must be `ethan_only`;
  - `reserve.enabled` and `reserve.evaluate_adaptive` must be `false`;
  - `forward.real_money` must be `false` and `forward.loss_cap_usd` must be `0`;
  - `claims.enabled` and `trial_ledger.count_in_trials_csv` must be `false`.

  The orchestrator was reviewed for that state only. Any activation is Ethan's, by hand; a queued job never
  performs one.
- **No promotion, freeze, ledger or access layer:** a test checks that the package imports nothing from
  `manhattan.ops`, `manhattan.ledger`, `manhattan.freeze`, `ledger`, `nightshift`, the HTE access/protected
  adapters, or any network client. It runs no git command but `ls-files`, `rev-parse` and `status`, and no process
  but its own child.
- **Child environment:** an allowlist (PATH, HOME, locale, TMPDIR, PYTHONPATH, VIRTUAL_ENV, …). No token or key passes
  (rule 10). The private store points at a path that does not exist (rule 7), and proxies point at a closed local
  port. This blocks a library that honours proxies; it is not a network sandbox.
- **Run root:** absolute, outside the repository checkout, and not on a network file system. Jobs cannot write
  tracked files, writers' data or protected paths (rules 2 and 3).
- **No writer workflow, no dispatch, no schedule** (rule 16): nothing here touches `.github/workflows/`.

## 11. Independent review

A separate reviewer read the code without my conclusions and reported nine findings. All nine were real; each is
fixed with a regression test, and the HTE calls it checked match PR #89's API.

| # | finding | fix |
|---|---|---|
| 1 | a crash between creating `inv-NNNN/` and its intent wedged every later tick (`FileExistsError`) | stray directory renamed `.orphan-k`, journaled; `serve` survives a failing tick |
| 2 | the budget counted only the *remaining* time of running invocations | an open invocation holds its whole window (`reserved_window`) |
| 3 | on macOS (no `/proc`) the memory cap, group kills and network-file-system check did nothing; a hostname change marked live work `foreign_host` | `procs.py` with `ps`/`mount`/`sysctl`/`ioreg`; machine id instead of hostname; liveness by lock first |
| 4 | `max_memory_mb_per_job: 0` passed as "tighter" but disabled the cap | caps must stay positive |
| 5 | a pending cancel overwrote integrity, refusal and block outcomes | only retryable and error outcomes become `cancelled` |
| 6 | `forward.loss_cap_usd > 0` and `reserve.evaluate_adaptive` did not stop starts | every switch must be in its conservative position |
| 7 | the group cleanup could kill another invocation after process-group reuse | match this invocation's directory in the command line, and the boot id |
| 8 | lock probed before `pid.json` was read: a microsecond race could kill a healthy child | `pid.json` first |
| 9 | `serve` never re-read `limits.json` | re-read every tick; an invalid file stops starts |
| minor | a timeout that made no progress was retried up to 50 times; sim had no progress anchor; requeue at the cap ran one invocation past it | `no_progress` covers timeouts; sim anchor over its replication files; requeue at the cap needs `extra_invocations` |

Neither this review nor my own tests replace a human review. The fixes were re-reviewed independently in §13.

## 12. Remaining requirements for unattended operation

These are decisions or actions for Ethan; none was taken here.

1. **HTE API.** PR #89 is merged, and the HTE test now runs on every CI run of this branch. The `hte` kind depends
   only on HTE's public API (`Runner`, `reconcile`, `Registry.submit`/`freeze`, the log format). A change there must
   change `kinds.Hte` in the same PR.
2. **Choose the host and install a timer.** For the iMac, use a launchd `KeepAlive` job running `serve` under
   `caffeinate -i`. Before relying on it, run the acceptance check of §13 there once.
3. **Off-host anchors.** Copy `status.json` somewhere the host cannot rewrite (for example the private ledger
   repository or a personal machine) on a schedule. Without that copy, someone with write access to the host could
   delete a suffix of the journal and of the engine logs together, and nothing would detect it.
4. **Notification.** Wire `health` (exit 1 or 2) to a notifier: cron mail, `osascript` or a phone push. Nothing here
   sends anything.
5. **Protect the limits.** Consider adding `/manhattan/orchestra/limits.py` and `/manhattan/orchestra/safety.py` to
   the protected block of `.github/CODEOWNERS`, so that the ceilings and the switch check change only under Ethan's
   review. Sessions cannot edit that file (rule 2).
6. **Kernel-level ceilings.** For a hard memory and CPU ceiling on all jobs together, run `serve` under a cgroup
   (systemd) or a dedicated user with resource limits. The built-in memory cap is a 1-second poll.
7. **Rented compute** (optional, Ethan's decision): set `price_sgd_per_vcpu_hour` so that the S$500 cap binds, pin
   the instance type, and keep the root on the instance's local disk.
8. **Retention.** Decide when finished jobs' work directories may be archived. The orchestrator never deletes them.

## 13. Independent re-review after merging main (PR #89, PR #99)

After merging `main`, a second reviewer re-read the nine fixes, again given the code and not my verdicts. It also
fed recorded macOS `mount`, `ioreg` and `sysctl` output through the non-`/proc` path. Its verdicts were:

- items 2, 6, 7 and 8 were fixed;
- items 1, 3, 4 and 9 were only partly fixed;
- item 5 still had a residual bug from before the fix.

The fix for item 9 had also introduced a new failure. Each was confirmed, then fixed with a regression test. **12 of
the new tests fail on the previous code and pass now.** The startup-race test (item 8) fails if the read order is
reverted.

| # | what the re-review found | fix |
|---|---|---|
| 1 | the orphan name used a count, so a gap (an orphan deleted by hand) made the rename fail on every tick; `serve`'s survival of a failed tick was untested | the next unused name; tests for the gap and for `serve` surviving a failed tick |
| 3 | cron's `PATH` lacks `/usr/sbin` and `/sbin`, so `ioreg`, `sysctl` and `mount` were not found: the machine id fell back to the hostname, boot was "unknown" and every root passed the file-system check. `afpfs`, `webdav`, `macfuse`, `osxfuse` and `autofs` were not refused. The boot id held local-time text. `ru_maxrss` was read as KiB on macOS, where it is bytes | absolute tool paths with a fixed `PATH`; unknown identity is `None` and never mismatches; macOS network types and every FUSE type refused; an unknown type refused; `kern.bootsessionuuid` (or boot seconds); `maxrss_mb` per platform. Tests use recorded macOS output |
| 4 | `0.5` was truncated to 0; `NaN` was accepted and then broke hashing; infinity raised `OverflowError` | finite, non-negative, whole numbers where the limit is an integer; `NaN` and `Infinity` refused while parsing; nothing of a refused key is applied |
| 5 | a cancel combined with exit 0 on an unclosed run became `unfinished` *after* the cancel check, and the job restarted | the cancel is applied after every reclassification; a queued job with a cancel on record is cancelled, never started |
| 6 | `loss_cap_usd: 0.0` (a float) needlessly stopped starts | numbers compare by value; `true` is still refused |
| 7 | the cancel SIGTERM went to the recorded pid without the command-line check | SIGTERM only to a verified member of this invocation |
| 9 | **new:** a `NaN` or `1e999` in `limits.json` raised outside the handled error, *before* supervision, so no exit was imported and no cancel or deadline kill was delivered | any error reading the file stops starts only; supervision continues under the last good limits (tested with a running job) |
| minor | a timeout before the first log record never counted as `no_progress` | an unchanged anchor, including "still none", is `no_progress` |

**macOS limitations that remain** (code cannot settle them; they need a Mac or an operating-system facility):

1. **Memory is measured, not enforced by the kernel.** The cap polls `ps` RSS once a second.
   - On macOS, RSS leaves out compressed and swapped pages, so under memory pressure the cap reads low.
   - On both platforms, copy-on-write pages shared by forked workers are counted once per process, so the sum reads
     high.
   - macOS has no cgroups. A hard ceiling needs a separate user with `launchctl` limits or a smaller `max_workers`.
     The footprint figure (`proc_pid_rusage`) is not used.
2. **Network-volume locks.** `flock` on smbfs, afpfs, webdav and macFUSE is unsupported or local-only. Those roots
   are refused, but a volume whose `mount` line reports a local type while being remote (some FUSE or vendor drivers)
   would pass.
3. **Process cleanup relies on `ps` showing the full command line.** `ps` does so when its output is not a terminal.
   A run-root path with unusual or non-ASCII bytes may be escaped by `ps`; it would then not match, and leftover
   forks would survive (cleanup fails safe). Keep the root path ASCII.
4. **Python launchers.** A framework or Homebrew `python` stub that re-executes the interpreter keeps the pid and
   argv on current macOS. This was not verified on the iMac's own install.
5. **Fork safety.** The child forks pool workers while its monitor thread runs. NumPy with Accelerate, or any
   Objective-C library, is not guaranteed fork-safe on macOS. HTE and the simulation already fork on Linux; on a Mac
   this is untested.
6. **Sleep.** Deadlines and the budget use wall-clock time, so time a Mac spends asleep counts against both. Run
   under `caffeinate -i`, as `scripts/manhattan_sim_run.sh` does.
7. **`kern.bootsessionuuid`** exists on current macOS releases. On older ones the fallback is the boot time in
   seconds, which a large clock step could move. Cleanup is then skipped, never misdirected.

**Acceptance check on the iMac** (once, by hand, nothing scheduled):

```
python -m manhattan.orchestra --root ~/orch-test init
python -m manhattan.orchestra --root ~/orch-test register smoke --params '{"units": 8, "faults": {"alloc_mb": 300, "hang_at_unit": 5}}'
echo '{"max_memory_mb_per_job": 150}' > ~/orch-test/limits.json
python -m manhattan.orchestra --root ~/orch-test serve --interval 2 --max-ticks 40
python -m manhattan.orchestra --root ~/orch-test status
```

The expected outcomes are `memory_exceeded`, then `done`. Running `ps -A -o pid,pgid,command | grep orchestra`
afterwards should show nothing left behind.

To check the run-root guard, run `init` on a mounted SMB volume; it must be refused. Then delete `~/orch-test`.

## 14. Second re-review (2026-11-20) and what is verified where

A third reviewer re-read the code after the merge of PRs #91 and #96 (and the earlier #89 and #99). As before, it
was given the code, not my verdicts, and it labelled every macOS claim by its evidence.

- **Fixed as claimed:** items 1, 2, 4, 5 and 8.
- **Still partial:** items 3, 6, 7 and 9.

Each finding below was confirmed and fixed with a regression test. **16 new tests fail on the previous code and pass
now.** The spawn-worker test was also run against the previous cleanup code alone: there the helper process survived
the dead invocation, which reproduces the finding.

| # | finding | fix |
|---|---|---|
| 3, 7 | the supervisor's kills matched processes by their command line only; **workers started by *spawn* (the default on macOS: the simulation's pool, resource trackers) never name the invocation** and survived a dead invocation's cleanup, still using CPU and memory while the next invocation started | each process is identified by pid *and* start time (`procs.Proc`). The invocation records every member of its group in `members.json` as it appears, and cleanup kills exactly the recorded members plus processes whose *last argument* is this invocation's directory (an exact match, no longer a substring). A new invocation of a job waits, killing again, while any member of its previous invocation is alive |
| 3 | if `ps` failed, memory read as 0 MB and the cap silently stopped working | an unreadable process table raises `ProcsUnavailable`; after 30 s the invocation stops with `memory_unmeasurable` (an error outcome) |
| 3 | the cancel and deadline KILLs were sent once; a failed `ps` at that moment left the job `cancelling` | a KILL is repeated at every tick while the invocation's lock is held |
| 6 | six switches did not stop starts: `exploration.data_end`, `reserve.store`, `reserve.windows`, `reserve.mode`, `programme.end`, `claims.screening_method` | every key of `config/manhattan.yaml` except `levels` must hold its conservative value (`safety.ALL_OFF`) |
| 7 | **new:** a child started by hand from a shell would `killpg` its caller's process group | the child leads its own process group before anything else |
| 9 | `Supervisor.__init__` and `status.snapshot` loaded `limits.json` unguarded, so with a bad file every CLI command, `tick` and `health` included, refused. Under cron that stopped supervision and cancels altogether | a bad file is reported (journal, `status.json`, `health` exit 1) and blocks starts and new registrations only; ticks, cancels and status keep working |
| 4 | an integer too large for a float raised `OverflowError` | refused as a limit |

**Evidence levels.** Nothing has been run on Ethan's iMac. The column "macOS evidence" uses these levels:

- **R:** run on a real Mac, the GitHub-hosted `macos-15` runner of the `orchestra-macos` job. This takes effect once
  that job is green on this PR.
- **F:** fabricated macOS output fed to the parser on Linux.
- **D:** reasoned from documentation only.

| behaviour | Linux | macOS evidence |
|---|---|---|
| process table, group RSS and start time via `ps -o pid,pgid,rss,lstart,command` | run (also with `/proc` hidden) | **R**: `test_real_macos_ps_reports_full_command_lines_and_resident_memory` (200 MiB touched reads at least 180) |
| `ps` command column not truncated when piped (needed to match an invocation) | run | **R**: same test, with a 200-character path |
| spawn-mode workers recorded and killed after a dead invocation | run (spawn forced) | **R**: `test_spawn_workers_of_a_dead_invocation…` runs on the Mac job, where spawn is the default |
| memory cap kills the group (`memory_exceeded`) | run | **R**: `test_memory_cap_kills_the_process_group` |
| deadline, cancel, adoption, orphan directory, budget window, bad limits, leader-of-own-group | run | **R**: the end-to-end tests run on the Mac job (only the `/proc/<pid>/environ` secrets test is Linux-only) |
| `ru_maxrss` in bytes | n/a (KiB) | **R**: `test_real_macos_peak_rss_units` |
| tools by absolute path; `kern.bootsessionuuid`; `IOPlatformUUID` | n/a | **R**: `test_real_macos_tools_identity_and_file_system`; **F** for the fallbacks |
| `mount` type of the home folder and of temporary folders is `apfs` (firmlinks) | n/a | **R**: same test |
| SMB, AFP, WebDAV, NFS, autofs and macFUSE roots refused | n/a | **F** only: no network volume can be mounted on the runner |
| `flock` exclusion and release on death | run | **R** on APFS; **D** for network volumes (refused anyway) |
| HTE (forks with a monitor thread running; NumPy's BLAS on macOS) | run | **R** if the HTE test passes on the Mac job; it is the one place the fork-safety question is exercised |
| RSS excludes compressed and swapped memory, so the cap reads low under memory pressure | n/a | **D** |
| iMac-specific: its Python install (Homebrew or framework), sleep, launchd `PATH` | n/a | **D**: covered by the acceptance check (§13), not by CI |

**A GitHub-hosted Mac is not the iMac.** It is a clean, Apple-silicon macOS 15 virtual machine with `setup-python`'s
Python. What it verifies is how macOS itself behaves. It does not verify the iMac's Python install, its macOS version
or its network volumes. The iMac acceptance check in §13 is still needed once before unattended use.

**The `orchestra-macos` workflow** (`.github/workflows/orchestra-macos.yml`):

- It runs only on pull requests to `main` that touch the orchestra; there is no schedule and no dispatch.
- Its token is read-only, it uses no secret, and the private store points at a path that does not exist.
- It writes nothing.
- A GitHub-hosted Mac is free for a public repository.

It is a new workflow file in this PR, and Ethan can drop it before merging if he prefers. It is not one of the writer
workflows of hard rules 3 and 16.
