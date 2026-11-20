"""Manhattan orchestra: unattended orchestration of long-running *synthetic* research jobs.

Research infrastructure only. It runs nothing that is not synthetic, produces no evidence, writes no Manhattan Ledger,
Store, trials.csv or configuration record, never activates a freeze, a promotion, a reserve or a forward evaluation,
and never pushes, dispatches or spends. Operating instructions: docs/manhattan/orchestra/OPERATIONS.md.

    journal     the orchestrator's append-only, hash-chained, fsynced journal and the file locks
    limits      resource, concurrency and budget limits (code defaults; a root's override file can only tighten)
    manifest    the reproducible execution manifest: code, configuration and numerical-environment identities
    safety      fail-closed guards: the child environment, the run root, the Manhattan switches, the kind allowlist
    kinds       the allowlisted job kinds (smoke, hte, sim) and their validation, execution and reconciliation
    smoke       a deterministic synthetic job with failure injection, for smoke and failure-injection tests
    state       the job lifecycle: a pure fold of the journal into job states
    supervisor  registration, scheduling, liveness, cancellation, recovery and retries (one tick at a time)
    child       the process that runs one invocation of one job (``python -m manhattan.orchestra.child``)
    status      machine-readable status snapshots, a one-line health summary and a loopback-only HTTP view
    cost        compute-cost estimates against the monthly research budget

Lifecycle (state.py): ``queued -> launching -> running -> {completed | retry_wait -> queued | failed | incomplete |
cancelled}``, with ``cancelling`` and ``blocked`` on the side. Every transition is a journal record written before the
action it describes, so a crash at any point is recovered from the journal and the files the invocation left.
"""

SCHEMA = "manhattan-orchestra/1"
EVIDENCE = None            # nothing here is evidence; status outputs carry this explicitly
SYNTHETIC_ONLY = True      # constant; tests fail if any job kind can read anything else
