# Linux zombie-worker recovery

An overnight full-suite run of the First Light draft found a pre-existing
orchestra recovery failure. The spawn-helper crash test timed out in
`retry_wait`: its helpers had exited but remained as zombies under the
container's PID 1. Linux `/proc` membership included their recorded PID/start
identities, so every retry was deferred as though live workers still existed.
SIGKILL cannot remove an already exited zombie; its parent must reap it.

The same existing test failed alone on untouched main `52bd8c9` (98.56 s) and
on the First Light branch (90.44 s). This is a reproduced production-code
liveness bug exposed by the host, not evidence that those helpers kept running.

## Correction and boundaries

The Linux process-table reader excludes an entry only when every task is explicitly `Z` and the task-id set is stable across the read. A `Z` leader alone can have live worker threads. Missing, empty, unreadable or malformed task information keeps the recorded process in the group. Live,
sleeping, stopped, uninterruptible and idle workers remain members. Existing
PID/start-time matching, unrelated-process protection, process-table refusal,
retry accounting and resource controls are unchanged. No invocation is marked
successful by this change. The macOS reader is unchanged; this focused fix
makes no new claim about zombie classification on macOS.

Five deterministic synthetic `/proc` fixtures reproduce recorded zombie helpers
alongside each retained worker state. All five fail on unmodified main. They
verify both process enumeration and supervisor membership, including the
all-zombie case. No test needs a timing race or an actual zombie to reproduce
the defect. The original real-process crash regression remains in the suite.

## Validation

- Orchestra suites: 95 passed, 3 skipped, 1 warning, exit 0 (54.59 s).
- New fixtures on unmodified main: 5 failed, exit 1.
- Protected-path and whitespace checks: exit 0.
- Full-suite and remote CI results are reported separately in the draft PR.

No protected paths, workflows, schedules, scientific rules, signing keys,
research switches or trading controls change. Only synthetic fixtures and
disposable smoke jobs are used. This draft requires independent review and
must not be merged by the overnight session.

## S17 correction

The original leader-only rule was unsafe: `pthread_exit` can leave a zombie leader
with a live worker. New synthetic fixtures cover that case, unknown task state,
and stable all-zombie groups. The PID/start identity still authorizes targeting.

Governance remains an explicit blocker: retargeting this published history to
`dev` currently exposes 22 files including unrelated writer data and accounting
changes. Rewriting history or silently reverting those paths is not permitted.
The focused correction remains draft pending explicit owner day-session adoption
or an owner-approved integration route into dev. Nothing is merged here.
