"""One invocation of one job: ``python -m manhattan.orchestra.child <invocation directory>``.

Started by the supervisor in its own session (process group), with the allowlisted environment of
``safety.child_env``. In order:

1. read ``invocation.json``;
2. take the job lock (``<job>/.run.lock``) for the whole invocation; if another process holds it, write an
   ``exit.json`` with outcome ``duplicate_refused`` and stop: two invocations of one job can never run at once;
3. write ``pid.json``;
4. recompute the execution manifest and write it; refuse (outcome ``blocked``) if its identity differs from the one
   recorded at registration;
5. verify the kind's own log against the anchor the orchestrator journaled after the previous invocation
   (``integrity`` if it does not match);
6. run the kind, with a monitor thread that rewrites ``progress.json``, enforces the wall-clock deadline (SIGTERM to
   itself, so the job stops between units of work, then SIGKILL of the group after the grace period), the memory cap
   on the aggregate RSS of the process group and the output-size cap (marker file, then SIGKILL of the group);
7. reconcile the kind's accounting from persisted files and write ``exit.json`` atomically.

SIGTERM is turned into ``KeyboardInterrupt`` in the main thread (once), which every kind treats as "stop starting
work, record what is in flight". A process that dies without ``exit.json`` is classified by the supervisor from
its markers and its lock.
"""
from __future__ import annotations

import json
import os
import resource
import signal
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

from . import kinds as K
from . import manifest as M
from . import procs
from .journal import FileLock, atomic_write_json, read_json

def group_rss_mb(pgid: int) -> float:
    """Aggregate resident memory of every process in a process group (/proc on Linux, ``ps`` on macOS)."""
    return sum(rss for _, rss, _ in procs.group(pgid)) / 2**20


class _Stop(KeyboardInterrupt):
    pass


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    inv_dir = Path(argv[0]).resolve()
    spec = read_json(inv_dir / "invocation.json")
    job_dir = Path(spec["job_dir"])
    work = job_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    kind = K.get(spec["kind"])
    params = spec["params"]
    t0 = time.time()
    exit_path = inv_dir / "exit.json"

    def finish(outcome: str, code: int, **extra) -> int:
        ru_s, ru_c = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        atomic_write_json(exit_path, {
            "outcome": outcome, "exit_code": code, "started_epoch": t0, "ended_epoch": time.time(),
            "cpu_s": ru_s.ru_utime + ru_s.ru_stime + ru_c.ru_utime + ru_c.ru_stime,
            "peak_rss_mb": max(ru_s.ru_maxrss, ru_c.ru_maxrss) / 1024.0, **extra})
        return code

    lock = FileLock(job_dir / ".run.lock")
    if not lock.acquire(timeout=10.0):
        return finish("duplicate_refused", K.EXIT_REFUSED, reason="another invocation of this job holds its lock")
    pgid = os.getpgid(0)
    atomic_write_json(inv_dir / "pid.json", {"pid": os.getpid(), "pgid": pgid, "host": socket.gethostname(),
                                             "machine_id": procs.machine_id(), "boot_id": procs.boot_id(),
                                             "started_epoch": t0})
    stop = threading.Event()
    state = {"term": 0, "why": None}

    def on_term(signum, frame):
        state["term"] += 1
        if state["term"] == 1:
            if state["why"] is None:
                state["why"] = "cancelled" if (inv_dir / "cancel").exists() else "signal"
            raise _Stop()

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    limits = spec["limits"]
    deadline = float(spec["deadline_epoch"])
    grace = float(limits["cancel_grace_s"])
    mem_cap = float(limits["max_memory_mb_per_job"])
    log_cap = float(limits["max_log_mb_per_invocation"]) * 2**20
    interval = float(limits["progress_interval_s"])

    def kill_group(marker: str, **info) -> None:
        atomic_write_json(inv_dir / marker, dict(info, epoch=time.time()))
        os.killpg(pgid, signal.SIGKILL)

    def monitor():
        last_progress = 0.0
        termed_at = None
        while not stop.wait(1.0):
            now = time.time()
            rss = group_rss_mb(pgid)
            if rss > mem_cap:
                kill_group("memory_exceeded", rss_mb=rss, cap_mb=mem_cap)
            try:
                if (inv_dir / "output.log").stat().st_size > log_cap:
                    kill_group("log_limit_exceeded", cap_bytes=log_cap)
            except OSError:
                pass
            if now >= deadline and termed_at is None:
                state["why"] = "deadline"
                atomic_write_json(inv_dir / "deadline", {"epoch": now})
                termed_at = now
                os.kill(os.getpid(), signal.SIGTERM)
            if termed_at is not None and now - termed_at > grace:
                kill_group("deadline_killed", grace_s=grace)
            if now - last_progress >= interval:
                last_progress = now
                try:
                    prog = kind.progress(params, work)
                except Exception as e:
                    prog = {"error_class": type(e).__name__}
                try:
                    atomic_write_json(inv_dir / "progress.json", {"epoch": now, "elapsed_s": now - t0,
                                                                  "group_rss_mb": round(rss, 1), "progress": prog})
                except OSError:
                    pass

    th = threading.Thread(target=monitor, daemon=True, name="orchestra-monitor")
    th.start()
    try:
        try:
            man = M.build(spec["job_spec"], M.REPO)
            atomic_write_json(inv_dir / "manifest.json", man)
            why = M.compare(spec["identity"], man["identity"], strict_environment=kind.strict_environment)
            if why:
                return finish("blocked", K.EXIT_REFUSED, reason=why, manifest_identity=man["identity"])
            try:
                kind.verify_anchor(params, work, spec.get("anchor_in"))
            except K.IntegrityError as e:
                return finish("integrity", K.EXIT_INTEGRITY, reason=str(e))
            ctx = {"invocation": spec["n"], "deadline": deadline, "now": time.time(), "job_id": spec["job_id"]}
            code = kind.run(params, work, ctx)
        except KeyboardInterrupt:
            code = K.EXIT_CANCELLED
        except K.ParamError as e:
            return finish("refused", K.EXIT_REFUSED, reason=str(e))
        except K.IntegrityError as e:
            return finish("integrity", K.EXIT_INTEGRITY, reason=str(e))
        except Exception as e:
            traceback.print_exc()
            code = K.EXIT_ERROR
            state["error_class"] = type(e).__name__
        # reconcile from persisted files; signals now only stop the reconciliation, never the record
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            rec = kind.reconcile(params, work, spec.get("anchor_in"))
        except Exception as e:
            rec = {"state": "unknown", "violations": [{"code": "reconcile_failed", "error_class": type(e).__name__}]}
        try:
            anchor = kind.anchor(params, work)
        except Exception:
            anchor = None
        if code == K.EXIT_CANCELLED:
            outcome = {"cancelled": "cancelled", "deadline": "timeout"}.get(state["why"], "interrupted")
        else:
            outcome = {K.EXIT_OK: "done", K.EXIT_RETRY: "unfinished", K.EXIT_REFUSED: "refused",
                       K.EXIT_INTEGRITY: "integrity"}.get(code, "error")
        return finish(outcome, code, reconcile=rec, anchor=anchor, error_class=state.get("error_class"))
    finally:
        stop.set()
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
