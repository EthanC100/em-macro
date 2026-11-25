"""Process harness for the Manhattan ops runner's real entry point (tests/test_manhattan_ops_entrypoint.py).

    python tests/manhattan_runner_harness.py EVIDENCE.jsonl -- nightly --rehearsal ...

Runs ``manhattan.ops.runner.main`` (the function ``python -m manhattan.ops.runner`` calls) in a fresh process and
exits with its return code. It changes nothing in the runner's logic. It adds, according to environment variables:

- ``HARNESS_PROBE=1``: the first time a protected value is about to leave a ``pit.Window`` for an attempt
  (``Window._known``, where the read meter counts the read before any value leaves), clone the ledger's remote
  afresh and record whether that attempt's start record is already durable there. One JSON line per attempt.
- ``HARNESS_FAULT``: a hard process death (``os._exit(137)``: no ``finally``, no handler, no cleanup) at
    ``kill_after_first_read``      just after the first protected value was read;
    ``kill_after_results_pending`` after the results write's journal ``pending`` entry was pushed;
    ``kill_after_results_commit``  after the results write's records were pushed, before verification;
    ``pause_after_lock``           not a death: after the lock is held, wait until the file ``HARNESS_GO`` exists.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from manhattan import access as A                     # noqa: E402
from manhattan.engine import pit                      # noqa: E402
from manhattan.ops import runner as R                 # noqa: E402
from manhattan.ops import store as ST                 # noqa: E402


def main() -> int:
    evidence, argv = Path(sys.argv[1]), sys.argv[sys.argv.index("--") + 1:]
    fault = os.environ.get("HARNESS_FAULT", "")
    remote = argv[argv.index("--remote") + 1]

    def note(**kw):
        with open(evidence, "a") as f:
            f.write(json.dumps(kw, sort_keys=True) + "\n")
        sys.__stderr__.flush()

    if os.environ.get("HARNESS_PROBE"):
        real_known, seen = pit.Window._known, set()

        def known(self, series, t):
            if self.attempt_id and self.attempt_id not in seen:
                seen.add(self.attempt_id)
                d = Path(tempfile.mkdtemp(prefix="probe-"))
                try:
                    fresh = ST.Store(workdir=d / "clone", remote=remote).open()
                    durable = fresh.get((A.STORE_START, self.attempt_id)) is not None
                finally:
                    shutil.rmtree(d, ignore_errors=True)
                note(event="first_protected_read", attempt=self.attempt_id, role=self.role,
                     start_durable_on_remote=durable)
            out = real_known(self, series, t)
            if fault == "kill_after_first_read":
                note(event="killed", at=fault)
                os._exit(137)
            return out

        pit.Window._known = known
    elif fault == "kill_after_first_read":
        real_known = pit.Window._known

        def known(self, series, t):
            out = real_known(self, series, t)
            if self.attempt_id:
                note(event="killed", at=fault)
                os._exit(137)
            return out

        pit.Window._known = known

    if fault in ("kill_after_results_pending", "kill_after_results_commit"):
        stage = {"kill_after_results_pending": "after_journal_push",
                 "kill_after_results_commit": "after_chain_push"}[fault]
        real_commit, real_crash = A.commit_results, ST.Store._crash

        def crash(self, s):
            if getattr(self, "_harness_arm", False) and s == stage:
                note(event="killed", at=fault)
                os._exit(137)
            return real_crash(self, s)

        def commit(store, *a, **k):
            store._harness_arm = True
            return real_commit(store, *a, **k)

        ST.Store._crash = crash
        A.commit_results = commit

    if fault == "raise_in_evaluate":
        # a handled failure whose exception text carries private values (HARNESS_SECRET): they must reach the
        # private log only, never stdout, the health record, the step summary or the failure issue
        secret = os.environ.get("HARNESS_SECRET", "0.012345678901")

        def broken(*a, **k):
            raise ValueError(f"synthetic failure: net return was {secret}, sharpe {secret}")

        R.observation_intents = broken

    if fault == "pause_after_lock":
        real_acquire, go = ST.Store.acquire, Path(os.environ["HARNESS_GO"])

        def acquire(self, *a, **k):
            out = real_acquire(self, *a, **k)
            note(event="holding_lock", status=out["status"])
            deadline = time.time() + 120
            while not go.exists() and time.time() < deadline:
                time.sleep(0.05)
            return out

        ST.Store.acquire = acquire

    return R.main(argv)


if __name__ == "__main__":
    sys.exit(main())
