"""Registration, scheduling, liveness, cancellation, recovery and retries.

The supervisor works one **tick** at a time (``tick``), so that it can run from a timer (cron, launchd, systemd) as
well as in a loop (``serve``). A tick holds the supervisor lock (one supervisor per root) and the journal lock while
it decides, and does, in order:

1. record the effective limits and the state of the Manhattan switches when either changed;
2. **supervise** every open invocation: adopt one whose start a crash left unrecorded, import its ``exit.json`` when
   the process has finished, classify a process that died without one (from its marker files: memory cap, output
   cap, deadline, cancellation; otherwise ``lost``), clean up any of its processes left in its group, deliver a
   cancellation (SIGTERM to the invocation process, SIGKILL to its group after the grace period) and enforce the
   wall-clock deadline as a second line behind the invocation's own monitor;
3. **decide** what follows each ended invocation (``decide``): completed, a retry after a back-off, ``incomplete``
   at the invocation cap, ``failed`` on an integrity violation, a refusal or the consecutive-error cap,
   ``blocked`` when the code or the numerical environment changed;
4. **start** eligible jobs by priority, then registration order, within the job-slot, worker, monthly vCPU-hour,
   spend and disk limits, unless the root is paused or the Manhattan switches are closed.

Every action is journaled **before** it is taken (``invocation_intent`` before the process is spawned,
``cancel_requested`` before a signal), so a crash at any point leaves a journal from which the next tick recovers.
Invocation processes run in their own session and survive the supervisor; a restarted supervisor adopts them.

**No silent duplicates.** A job's identity is the hash of its kind, normalised parameters and look number; a second
registration of the same identity is refused and journaled. A job has at most one open invocation, which holds the
job lock; a new invocation starts only when the previous one has ended *and* the lock is free; the invocation
process itself refuses to run while another holds the lock; and the HTE engine holds its own workspace lock.

**Nothing is lost.** Failed, interrupted and cancelled invocations stay in the journal with their outcome; the job's
work directory is never deleted or rewritten by the orchestrator; the engines' own logs keep every attempt.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import SCHEMA
from . import kinds as K
from . import limits as L
from . import manifest as M
from . import safety
from . import procs
from .journal import FileLock, Journal, atomic_write_json, full_hash, is_held_elsewhere, read_json
from .state import ACTIVE, TERMINAL, fold, month_of

CHILD_MARK = "manhattan.orchestra.child"
RETRYABLE = ("unfinished", "timeout", "interrupted")
ERROR_LIKE = ("error", "memory_exceeded", "memory_unmeasurable", "log_limit_exceeded", "lost", "lost_before_start", "spawn_failed",
              "no_progress")


class SupervisorError(RuntimeError):
    pass


def decide(job: dict, outcome: str, limits: L.Limits, now: float, *, reason: str | None = None) -> dict:
    """What follows an ended invocation: ``{"next_status", "reason", "consecutive_errors", "not_before_epoch"}``.
    ``job`` is the folded job *before* this invocation ended; its ``n_invocations`` already counts it."""
    errors = job["consecutive_errors"]
    out = {"consecutive_errors": 0, "not_before_epoch": 0.0, "reason": reason}
    if outcome == "done":
        return dict(out, next_status="completed", reason=None)
    if outcome == "cancelled":
        return dict(out, next_status="cancelled", reason=(job.get("cancel") or {}).get("reason") or reason)
    if outcome == "integrity":
        return dict(out, next_status="failed", reason=f"integrity: {reason}" if reason else "integrity")
    if outcome == "refused":
        return dict(out, next_status="failed", reason=f"refused: {reason}" if reason else "refused")
    if outcome == "duplicate_refused":
        return dict(out, next_status="blocked", reason="duplicate_invocation_detected")
    if outcome in ("blocked", "foreign_host"):
        return dict(out, next_status="blocked", reason=reason or outcome)
    if outcome in ERROR_LIKE:
        errors += 1
        if errors >= limits.max_consecutive_errors:
            return dict(out, next_status="failed", consecutive_errors=errors,
                        reason=f"{errors} consecutive errors (last: {outcome}{': ' + reason if reason else ''})")
        out.update(consecutive_errors=errors, not_before_epoch=now + L.backoff_seconds(limits, errors))
    if job["n_invocations"] >= job["max_invocations"]:
        return dict(out, next_status="incomplete",
                    reason=f"invocation cap reached ({job['max_invocations']}); last outcome {outcome}")
    return dict(out, next_status="retry_wait", reason=reason or outcome)


def _members(pgid: int, inv_dir: Path) -> list[int]:
    """The processes of this invocation that are still in its process group:

    * the invocation process and its forks, whose command line ends with this invocation's directory as its last
      argument (``python -m manhattan.orchestra.child <inv_dir>``), matched exactly, not as a substring;
    * any other member the invocation recorded in ``members.json`` (pid *and* start time): workers started by spawn
      (the default on macOS), resource trackers and other helpers, whose command lines do not name the invocation.

    A reused process-group id or pid, or another invocation, never matches, so nothing unrelated is killed. If the
    process table cannot be read, nothing matches this time; kills are retried at every tick."""
    try:
        group = procs.group(pgid)
    except procs.ProcsUnavailable:
        return []
    tail = " " + str(inv_dir)
    try:
        recorded = {(int(a), str(b)) for a, b in read_json(inv_dir / "members.json")}
    except (OSError, ValueError, TypeError):
        recorded = set()
    return [p.pid for p in group if (CHILD_MARK in p.cmd and p.cmd.endswith(tail)) or (p.pid, p.start) in recorded]


def _kill(pids: list[int], sig: int) -> int:
    n = 0
    for pid in pids:
        try:
            os.kill(pid, sig)
            n += 1
        except (ProcessLookupError, PermissionError):
            pass
    return n


class Supervisor:
    def __init__(self, root: Path, *, limits: L.Limits | None = None, repo: Path = M.REPO,
                 python: str = sys.executable, clock=time.time, check_switches: bool = True,
                 base_env: dict | None = None):
        self.repo = Path(repo)
        self.root = safety.check_root(Path(root), self.repo)
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal = Journal(self.root / "journal.jsonl")
        self._base_limits = limits if limits is not None else L.DEFAULT
        try:                                                   # re-read at every tick (tighten-only)
            self.limits, self.limits_error = L.load(self.root, self._base_limits), None
        except Exception as e:                                 # supervision still works; starts and new
            self.limits = self._base_limits                    # registrations wait until the file is fixed
            self.limits_error = str(e) if isinstance(e, L.LimitsError) else f"limits.json: {type(e).__name__}"
        self.python = python
        self.clock = clock
        self.check_switches = check_switches
        self.base_env = base_env
        self.host = socket.gethostname()
        self.machine = procs.machine_id()
        self._procs: dict[int, subprocess.Popen] = {}
        with self.journal.locked():
            if not any(r["type"] == "root_initialized" for r in self.journal.records()):
                self.journal.append("root_initialized", {"schema": SCHEMA, "host": self.host, "machine_id": self.machine,
                                                         "boot_id": procs.boot_id(),
                                                         "created_epoch": self.clock()})

    # -- reading ----------------------------------------------------------------------------------------------
    def state(self) -> dict:
        return fold(self.journal.records())

    def job_dir(self, job_id: str) -> Path:
        return self.root / "jobs" / job_id

    # -- commands ---------------------------------------------------------------------------------------------
    def register(self, kind: str, params: dict, *, priority: int = 0, look: int = 0,
                 max_invocations: int | None = None) -> dict:
        if self.limits_error:
            raise L.LimitsError(f"registration waits until limits.json is fixed: {self.limits_error}")
        k = K.get(kind)
        p = k.normalise(params)
        workers = k.workers(p)
        if workers > self.limits.max_workers_per_job:
            raise K.ParamError(f"workers={workers} exceeds max_workers_per_job={self.limits.max_workers_per_job}")
        if not isinstance(look, int) or look < 0:
            raise K.ParamError("look must be a non-negative integer")
        cap = self.limits.max_invocations_per_job
        mi = cap if max_invocations is None else max(1, min(int(max_invocations), cap))
        job_spec = {"kind": kind, "params": p, "look": look}
        job_id = "OJ-" + full_hash(job_spec)[:16]
        man = M.build(job_spec, self.repo)
        if self.limits.require_clean_tree and man["code"]["dirty"]:
            raise safety.Refused("the code paths differ from the checked-out commit (require_clean_tree): commit "
                                 "first, so the manifest names exactly the code that runs")
        with self.journal.locked():
            st = self.state()
            if job_id in st["jobs"]:
                self.journal.append("duplicate_registration", {"job_id": job_id,
                                                               "identity_sha256": man["identity_sha256"]})
                j = st["jobs"][job_id]
                return {"job_id": job_id, "duplicate": True, "status": j["status"]}
            d = self.job_dir(job_id)
            (d / "work").mkdir(parents=True, exist_ok=True)
            msha = atomic_write_json(d / "manifest.json", man)
            atomic_write_json(d / "job.json", job_spec)
            self.journal.append("job_registered", {
                "job_id": job_id, "kind": kind, "params": p, "look": look, "priority": int(priority),
                "label": k.label(p), "workers": workers, "max_invocations": mi, "identity": man["identity"],
                "identity_sha256": man["identity_sha256"], "manifest_sha256": msha,
                "commit": man["code"]["commit"], "dirty": man["code"]["dirty"],
                "strict_environment": k.strict_environment})
        return {"job_id": job_id, "duplicate": False, "status": "queued"}

    def cancel(self, job_id: str, reason: str = "operator") -> dict:
        with self.journal.locked():
            j = self._job(job_id)
            if j["status"] in TERMINAL:
                return {"job_id": job_id, "status": j["status"], "changed": False}
            if j["cancel"] is None:
                self.journal.append("cancel_requested", {"job_id": job_id, "reason": reason})
            if j["status"] not in ACTIVE:
                self.journal.append("job_cancelled", {"job_id": job_id, "reason": reason})
            return {"job_id": job_id, "status": self._job(job_id)["status"], "changed": True}

    def requeue(self, job_id: str, reason: str = "operator", extra_invocations: int = 0) -> dict:
        """Continue a job that stopped unfinished. Refused for integrity failures and refusals (those need a
        person to look, then a new registration) and for identity changes (a new look)."""
        if not 0 <= extra_invocations <= self.limits.max_invocations_per_job:
            raise K.ParamError("extra_invocations out of range")
        with self.journal.locked():
            j = self._job(job_id)
            ok = (j["status"] in ("incomplete", "cancelled")
                  or (j["status"] == "failed" and "consecutive errors" in (j["reason"] or ""))
                  or (j["status"] == "blocked" and j["reason"] in ("foreign_host", "duplicate_invocation_detected")))
            if not ok:
                raise SupervisorError(f"{job_id} is {j['status']} ({j['reason']}): not requeueable")
            if j["n_invocations"] >= j["max_invocations"] + extra_invocations:
                raise SupervisorError(f"{job_id} has used all {j['max_invocations']} invocations: pass "
                                      "extra_invocations")
            self.journal.append("job_requeued", {"job_id": job_id, "reason": reason,
                                                 "extra_invocations": int(extra_invocations)})
        return {"job_id": job_id, "status": "queued"}

    def audit(self, job_id: str) -> dict:
        """Re-reconcile a job's persisted files against the anchor journaled after its last invocation, without
        running anything (run it periodically on completed jobs: tampering or disk damage after completion shows
        up here). The result is journaled as ``job_audited``; a corrupted audit puts the job on the attention
        list."""
        j = self._job(job_id)
        if j["status"] in ACTIVE:
            raise SupervisorError(f"{job_id} is {j['status']}: audit it when no invocation is open")
        k = K.get(j["kind"])
        try:
            rec = k.reconcile(j["params"], self.job_dir(job_id) / "work", j["anchor"])
        except Exception as e:
            rec = {"state": "corrupted", "violations": [{"code": "audit_failed", "error_class": type(e).__name__}]}
        with self.journal.locked():
            self.journal.append("job_audited", {"job_id": job_id, "state": rec.get("state"),
                                                "violations": _bounded(rec).get("violations", [])})
        return rec

    def pause(self, reason: str = "operator") -> None:
        with self.journal.locked():
            self.journal.append("paused", {"reason": reason})

    def unpause(self) -> None:
        with self.journal.locked():
            self.journal.append("unpaused", {})

    def _job(self, job_id: str) -> dict:
        st = self.state()
        if job_id not in st["jobs"]:
            raise SupervisorError(f"no job {job_id}")
        return st["jobs"][job_id]

    # -- the tick ---------------------------------------------------------------------------------------------
    def tick(self) -> dict:
        lk = FileLock(self.root / ".supervisor.lock")
        if not lk.acquire(timeout=0.0):
            return {"skipped": "another supervisor holds this root"}
        try:
            for pid, p in list(self._procs.items()):           # reap finished children of this process
                if p.poll() is not None:
                    del self._procs[pid]
            summary = {"ended": [], "started": [], "signalled": [], "deferred": []}
            with self.journal.locked():
                st = self.state()
                limits_ok = True
                try:
                    self.limits, self.limits_error = L.load(self.root, self._base_limits), None
                except Exception as e:                         # keep supervising under the last good limits,
                    limits_ok = False                          # start nothing until the file is fixed
                    msg = str(e) if isinstance(e, L.LimitsError) else f"limits.json: {type(e).__name__}"
                    self.limits_error = msg
                    if st["limits_error"] != msg:
                        self.journal.append("limits_invalid", {"error": msg})
                if limits_ok and (st["limits_hash"] != self.limits.hash() or st["limits_error"]):
                    self.journal.append("limits_effective", {"hash": self.limits.hash(),
                                                             "limits": self.limits.as_dict()})
                reasons = safety.manhattan_switches(self.repo) if self.check_switches else []
                if reasons != st["switches"]:
                    if reasons:
                        self.journal.append("switches_closed", {"reasons": reasons})
                    else:
                        self.journal.append("switches_open", {})
                for jid in st["order"]:
                    j = st["jobs"][jid]
                    if j["open_invocation"] is not None:
                        self._supervise(j, j["open_invocation"], summary)
                st = self.state()
                paused = st["paused"] or (self.root / "PAUSE").exists()
                if not paused and not reasons and limits_ok:
                    self._start_eligible(st, summary)
            from . import status as S
            now = self.clock()
            snap = S.snapshot(self.root, self.limits, now=now)
            snap["supervisor"] = {"last_tick_utc": snap["generated_utc"], "age_s": 0.0, "stale": False}
            atomic_write_json(self.root / "status.json", snap)
            summary["counts"] = snap["counts"]
            summary["paused"] = paused
            summary["switches_closed"] = reasons
            summary["limits_ok"] = limits_ok
            return summary
        finally:
            lk.release()

    def serve(self, interval: float = 30.0, max_ticks: int | None = None) -> None:
        stop = {"flag": False}

        def on_term(signum, frame):
            stop["flag"] = True
        signal.signal(signal.SIGTERM, on_term)
        signal.signal(signal.SIGINT, on_term)
        n = 0
        while not stop["flag"]:
            try:
                self.tick()
            except Exception:                                  # a bad tick must not end supervision
                import traceback
                traceback.print_exc()
            n += 1
            if max_ticks is not None and n >= max_ticks:
                break
            end = time.monotonic() + interval
            while not stop["flag"] and time.monotonic() < end:
                time.sleep(min(0.5, interval))

    # -- supervision ------------------------------------------------------------------------------------------
    def _supervise(self, job: dict, inv: dict, summary: dict) -> None:
        now = self.clock()
        jid = job["job_id"]
        inv_dir = self.root / inv["inv_dir"]
        pidf, exitf = inv_dir / "pid.json", inv_dir / "exit.json"
        # pid.json first, then the lock: a child writes pid.json only while holding the lock, so "pid.json and a
        # free lock" can then only mean that the process has ended
        pid_info = read_json(pidf) if pidf.exists() else None
        held = is_held_elsewhere(self.job_dir(jid) / ".run.lock")
        if inv["started"] is None and pid_info:
            self._adopt(jid, inv, pid_info)
        if exitf.exists():
            # the invocation process wrote its outcome; it only releases its lock after that. A lock still held here
            # belongs to another process (the case ``duplicate_refused`` reports), never to this invocation's work
            self._end(job, inv, read_json(exitf), now, summary)
            return
        if held:                                               # alive on this machine (flock is local)
            pid = (pid_info or inv["started"] or {}).get("pid")
            pgid = (pid_info or inv["started"] or {}).get("pgid") or pid
            if job["cancel"] and pid:
                sig = inv["signalled"]
                if sig is None:
                    atomic_write_json(inv_dir / "cancel", {"epoch": now, "reason": job["cancel"]["reason"]})
                    self.journal.append("cancel_signalled", {"job_id": jid, "n": inv["n"], "signal": "TERM",
                                                             "epoch": now})
                    # only to the invocation process itself, verified by its command line (never a reused pid)
                    _kill([p for p in _members(pgid, inv_dir) if p == pid], signal.SIGTERM)
                    summary["signalled"].append(jid)
                elif sig["signal"] == "TERM" and now - sig["epoch"] > self.limits.cancel_grace_s:
                    self.journal.append("cancel_signalled", {"job_id": jid, "n": inv["n"], "signal": "KILL",
                                                             "epoch": now})
                    _kill(_members(pgid, inv_dir), signal.SIGKILL)
            if pgid and now > inv["deadline_epoch"] + self.limits.cancel_grace_s + 60:
                if not (inv["signalled"] and inv["signalled"]["signal"] == "KILL"):
                    self.journal.append("cancel_signalled", {"job_id": jid, "n": inv["n"], "signal": "KILL",
                                                             "epoch": now, "reason": "deadline"})
                    atomic_write_json(inv_dir / "deadline_killed", {"epoch": now, "by": "supervisor"})
                    _kill(_members(pgid, inv_dir), signal.SIGKILL)
            if pgid and inv["signalled"] and inv["signalled"]["signal"] == "KILL":
                _kill(_members(pgid, inv_dir), signal.SIGKILL)  # a KILL is repeated at every tick, never one-shot
            return
        # the lock is free and there is no exit.json: the process died, or has not taken the lock yet
        if pid_info is None and now - inv["intent_epoch"] <= self.limits.launch_grace_s:
            return                                             # still launching
        theirs = (pid_info or {}).get("machine_id")
        if theirs is not None and self.machine is not None and theirs != self.machine:
            # the root moved to another machine (a restored copy): this machine cannot know whether it is alive
            self._end(job, inv, {"outcome": "foreign_host", "reason": f"invocation ran on {pid_info.get('host')}"},
                      now, summary)
            return
        then, cur = (pid_info or {}).get("boot_id"), procs.boot_id()
        same_boot = then is None or cur is None or then == cur      # unknown: the command-line match still guards
        pgid = (pid_info or inv["started"] or {}).get("pgid")
        if pgid and same_boot:
            _kill(_members(pgid, inv_dir), signal.SIGKILL)     # forks left behind by a dead invocation process
        if pid_info:
            for marker, outcome in (("memory_exceeded", "memory_exceeded"), ("log_limit_exceeded",
                                                                              "log_limit_exceeded"),
                                    ("memory_unmeasurable", "memory_unmeasurable"),
                                    ("deadline_killed", "timeout"), ("deadline", "timeout")):
                if (inv_dir / marker).exists():
                    break
            else:
                outcome = "cancelled" if (inv_dir / "cancel").exists() else "lost"
            self._end(job, inv, {"outcome": outcome, "reason": "the invocation process ended without exit.json"},
                      now, summary)
            return
        self._end(job, inv, {"outcome": "lost_before_start", "reason": "no process took the job lock within the "
                             "launch grace"}, now, summary)

    def _adopt(self, jid: str, inv: dict, pid_info: dict) -> None:
        self.journal.append("invocation_started", {"job_id": jid, "n": inv["n"], "pid": pid_info["pid"],
                                                   "pgid": pid_info["pgid"], "host": pid_info.get("host"),
                                                   "machine_id": pid_info.get("machine_id"),
                                                   "boot_id": pid_info.get("boot_id"), "adopted": True,
                                                   "started_epoch": pid_info["started_epoch"]})

    def _end(self, job: dict, inv: dict, info: dict, now: float, summary: dict) -> None:
        jid = job["job_id"]
        outcome = info.get("outcome", "lost")
        rec = info.get("reconcile")
        if rec and rec.get("state") == "corrupted":
            outcome = "integrity"
        elif outcome == "done" and (not rec or rec.get("state") != "closed"):
            outcome = "unfinished"
        k = K.get(job["kind"])
        anchor = info.get("anchor")
        if anchor is None and "exit_code" not in info:
            try:
                anchor = k.anchor(job["params"], self.job_dir(jid) / "work")
            except Exception:
                anchor = None
        if outcome in ("unfinished", "timeout") and anchor == job["anchor"]:
            outcome = "no_progress"            # nothing new in the kind's log (or still no log at all): do not loop
        if job["cancel"] and outcome in RETRYABLE + ERROR_LIKE + ("cancelled",):
            outcome = "cancelled"              # last, after every reclassification; never hides integrity,
                                               # refusals or blocks
        started = info.get("started_epoch") or (inv["started"] or {}).get("started_epoch") or inv["intent_epoch"]
        ended = info.get("ended_epoch") or self._last_seen(inv) or now
        wall = max(0.0, ended - started)
        reserved = max(1, inv["workers"]) * wall / 3600.0
        j = dict(job, n_invocations=len(job["invocations"]))
        d = decide(j, outcome, self.limits, now, reason=info.get("reason"))
        payload = {"job_id": jid, "n": inv["n"], "outcome": outcome, "exit_code": info.get("exit_code"),
                   "wall_s": round(wall, 3), "cpu_s": info.get("cpu_s"), "reserved_vcpu_h": round(reserved, 6),
                   "peak_rss_mb": info.get("peak_rss_mb"), "ended_epoch": ended, "anchor": anchor,
                   "reconcile": _bounded(rec), "error_class": info.get("error_class"), **d}
        self.journal.append("invocation_ended", payload)
        summary["ended"].append({"job_id": jid, "n": inv["n"], "outcome": outcome, "next": d["next_status"]})

    def _last_seen(self, inv: dict) -> float | None:
        p = self.root / inv["inv_dir"] / "progress.json"
        try:
            return float(read_json(p)["epoch"])
        except (OSError, ValueError, KeyError):
            return None

    # -- starting ---------------------------------------------------------------------------------------------
    def _start_eligible(self, st: dict, summary: dict) -> None:
        now = self.clock()
        lim = self.limits
        jobs = st["jobs"]
        active = [j for j in jobs.values() if j["status"] in ACTIVE]
        slots = lim.max_running_jobs - len(active)
        cpu_cap = min(lim.max_total_workers, os.cpu_count() or 1)
        used_workers = sum(max(1, j["open_invocation"]["workers"]) for j in active if j["open_invocation"])
        month = month_of(now)
        committed = st["usage"].get(month, 0.0) + sum(reserved_window(j["open_invocation"]) for j in active
                                                       if j["open_invocation"])
        free_mb = shutil.disk_usage(self.root).free / 2**20
        queue = sorted((j for j in jobs.values() if j["status"] in ("queued", "retry_wait")),
                       key=lambda j: (-j["priority"], j["registered_seq"]))
        for j in queue:
            if j["cancel"]:                                    # a cancel that arrived around an ending invocation
                self.journal.append("job_cancelled", {"job_id": j["job_id"], "reason": j["cancel"]["reason"]})
                continue
            if slots <= 0:
                break
            if j["not_before"] > now:
                continue
            w = max(1, j["workers"])
            worst = w * lim.max_wall_minutes_per_invocation / 60.0
            why = None
            left = self._leftovers(j)
            if left:
                _kill(left, signal.SIGKILL)                    # again, and wait: never two generations at once
                why = f"{len(left)} process(es) of the previous invocation still alive"
            elif is_held_elsewhere(self.job_dir(j["job_id"]) / ".run.lock"):
                why = "the job lock is held by another process"
            elif free_mb < lim.min_free_disk_mb:
                why = f"free disk {free_mb:.0f} MB below the {lim.min_free_disk_mb} MB floor"
            elif w > cpu_cap:
                why = f"needs {w} workers; the cap on this machine is {cpu_cap}"
            elif used_workers + w > cpu_cap:
                why = "waiting for workers"
            elif committed + worst > lim.monthly_vcpu_hours:
                why = f"monthly vCPU-hour budget: {committed:.1f} used or committed of {lim.monthly_vcpu_hours}"
            elif lim.price_sgd_per_vcpu_hour and (committed + worst) * lim.price_sgd_per_vcpu_hour > lim.monthly_budget_sgd:
                why = f"monthly spend cap S${lim.monthly_budget_sgd:.0f}"
            if why:
                if j["deferred"] != why:
                    self.journal.append("start_deferred", {"job_id": j["job_id"], "reason": why})
                summary["deferred"].append({"job_id": j["job_id"], "reason": why})
                if why == "waiting for workers" or why.startswith("free disk"):
                    break                                       # head of line: no starvation of large jobs
                continue
            self._start(j, now)
            summary["started"].append(j["job_id"])
            slots -= 1
            used_workers += w
            committed += worst

    def _leftovers(self, job: dict) -> list[int]:
        """Processes of the job's last invocation still alive in its process group (same boot only)."""
        if not job["invocations"]:
            return []
        last = job["invocations"][-1]
        pgid = (last["started"] or {}).get("pgid")
        then = (last["started"] or {}).get("boot_id")
        cur = procs.boot_id()
        if not pgid or (then and cur and then != cur):
            return []
        return _members(pgid, self.root / last["inv_dir"])

    def _start(self, job: dict, now: float) -> None:
        jid = job["job_id"]
        n = len(job["invocations"]) + 1
        rel = f"jobs/{jid}/inv-{n:04d}"
        inv_dir = self.root / rel
        if inv_dir.exists():
            # left by a crash between mkdir and the intent record: keep it, under another name, and say so
            k = 0
            while inv_dir.with_name(f"inv-{n:04d}.orphan-{k}").exists():
                k += 1
            dst = inv_dir.with_name(f"inv-{n:04d}.orphan-{k}")
            os.replace(inv_dir, dst)
            self.journal.append("orphan_invocation_dir", {"job_id": jid, "n": n, "renamed_to": dst.name})
        inv_dir.mkdir(parents=True)
        deadline = now + self.limits.max_wall_minutes_per_invocation * 60
        spec = {"job_id": jid, "kind": job["kind"], "params": job["params"], "n": n,
                "job_dir": str(self.job_dir(jid)), "identity": job["identity"],
                "job_spec": {"kind": job["kind"], "params": job["params"], "look": job["look"]},
                "anchor_in": job["anchor"], "deadline_epoch": deadline, "limits": self.limits.as_dict()}
        atomic_write_json(inv_dir / "invocation.json", spec)
        self.journal.append("invocation_intent", {"job_id": jid, "n": n, "inv_dir": rel, "workers": job["workers"],
                                                  "intent_epoch": now, "deadline_epoch": deadline,
                                                  "anchor_in": job["anchor"]})
        env, dropped = safety.child_env(self.base_env)
        try:
            with open(inv_dir / "output.log", "ab") as out:
                p = subprocess.Popen([self.python, "-m", "manhattan.orchestra.child", str(inv_dir)], cwd=self.repo,
                                     env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                     start_new_session=True, close_fds=True)
        except OSError as e:
            j = self._job(jid)
            self._end(j, j["open_invocation"], {"outcome": "spawn_failed", "reason": type(e).__name__}, now,
                      {"ended": []})
            return
        self._procs[p.pid] = p
        self.journal.append("invocation_started", {"job_id": jid, "n": n, "pid": p.pid, "pgid": p.pid,
                                                   "host": self.host, "machine_id": self.machine,
                                                   "boot_id": procs.boot_id(), "adopted": False,
                                                   "started_epoch": now, "env_dropped": dropped})


def reserved_window(inv: dict) -> float:
    """The vCPU-hours an open invocation holds against the budget: its whole window, from intent to deadline
    (time already used included), until it ends and its actual use is booked."""
    return max(1, inv["workers"]) * max(0.0, inv["deadline_epoch"] - inv["intent_epoch"]) / 3600.0


def _bounded(rec: dict | None, max_violations: int = 50) -> dict | None:
    """A reconciliation summary small enough for the journal."""
    if rec is None:
        return None
    out = dict(rec)
    v = out.get("violations") or []
    if len(v) > max_violations:
        out["violations"] = v[:max_violations]
        out["violations_truncated"] = len(v)
    return out
