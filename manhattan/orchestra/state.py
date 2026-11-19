"""The job lifecycle: a pure fold of the journal into job states.

Nothing outside the journal holds state. A job's status is recomputed from its records every time, so a crash of the
supervisor or of the CLI can never leave a status file that disagrees with the history.

    status        category    meaning
    queued        queued      registered or requeued; waiting for a slot, the budget or the disk
    retry_wait    queued      the last invocation ended unfinished; the next may start after ``not_before``
    launching     active      intent recorded; the invocation process has not been confirmed yet
    running       active      the invocation process holds the job lock
    cancelling    active      cancellation signalled; waiting for the process to stop
    blocked       blocked     cannot continue without a person: identity changed, foreign host (reason given)
    completed     completed   the last invocation succeeded and reconciliation found the run closed and clean
    incomplete    incomplete  stopped unfinished: the invocation cap was reached (work so far is kept and counted)
    failed        failed      an integrity violation, a refusal, or the consecutive-error cap
    cancelled     cancelled   cancelled by a person; work so far is kept and counted

Record types (payloads always carry ``job_id`` where a job is concerned):

    job_registered, duplicate_registration, invocation_intent, invocation_started, cancel_requested,
    cancel_signalled, invocation_ended, job_cancelled, job_requeued, job_blocked, start_deferred, job_audited,
    paused, unpaused, limits_effective, switches_closed, switches_open, root_initialized, journal_torn_tail
"""
from __future__ import annotations

from datetime import datetime, timezone

ACTIVE = ("launching", "running", "cancelling")
TERMINAL = ("completed", "incomplete", "failed", "cancelled")
CATEGORY = {"queued": "queued", "retry_wait": "queued", "launching": "active", "running": "active",
            "cancelling": "active", "blocked": "blocked", "completed": "completed", "incomplete": "incomplete",
            "failed": "failed", "cancelled": "cancelled"}
CATEGORIES = ("active", "queued", "blocked", "failed", "incomplete", "completed", "cancelled")


def month_of(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m")


def fold(records: list[dict]) -> dict:
    """``{"jobs": {job_id: job}, "order": [...], "paused": bool, "switches": [...], "limits_hash": str|None,
    "usage": {month: reserved vCPU-hours}}``."""
    jobs: dict[str, dict] = {}
    order: list[str] = []
    out = {"jobs": jobs, "order": order, "paused": False, "pause_reason": None, "switches": [], "limits_hash": None,
           "usage": {}, "root": None}
    for r in records:
        t, p = r["type"], r["payload"]
        j = jobs.get(p.get("job_id")) if "job_id" in p else None
        if t == "root_initialized":
            out["root"] = p
        elif t == "job_registered":
            jobs[p["job_id"]] = {
                "job_id": p["job_id"], "kind": p["kind"], "label": p.get("label"), "params": p["params"],
                "priority": p.get("priority", 0), "look": p.get("look", 0), "identity": p["identity"],
                "identity_sha256": p["identity_sha256"], "registered_seq": r["seq"], "registered_utc": r.get("ts_utc"),
                "max_invocations": p["max_invocations"], "status": "queued", "reason": None, "invocations": [],
                "cancel": None, "not_before": 0.0, "consecutive_errors": 0, "anchor": None, "reconcile": None,
                "reserved_vcpu_h": 0.0, "cpu_s": 0.0, "deferred": None, "workers": p["workers"], "audit": None,
                "strict_environment": p.get("strict_environment", True)}
            order.append(p["job_id"])
        elif j is None:
            if t == "paused":
                out["paused"], out["pause_reason"] = True, p.get("reason")
            elif t == "unpaused":
                out["paused"], out["pause_reason"] = False, None
            elif t == "limits_effective":
                out["limits_hash"] = p["hash"]
            elif t == "switches_closed":
                out["switches"] = p["reasons"]
            elif t == "switches_open":
                out["switches"] = []
            continue
        elif t == "invocation_intent":
            j["invocations"].append({"n": p["n"], "intent_seq": r["seq"], "intent_utc": r.get("ts_utc"),
                                     "intent_epoch": p["intent_epoch"], "deadline_epoch": p["deadline_epoch"],
                                     "workers": p["workers"], "inv_dir": p["inv_dir"], "started": None,
                                     "ended": None, "signalled": None})
            j["status"], j["deferred"] = "launching", None
        elif t == "invocation_started":
            inv = _inv(j, p["n"])
            inv["started"] = {k: p.get(k) for k in ("pid", "pgid", "host", "boot_id", "adopted", "started_epoch")}
            if j["status"] == "launching":
                j["status"] = "running"
        elif t == "cancel_requested":
            j["cancel"] = {"reason": p.get("reason"), "seq": r["seq"]}
            if j["status"] in ("launching", "running"):
                j["status"] = "cancelling"
        elif t == "cancel_signalled":
            _inv(j, p["n"])["signalled"] = {"signal": p["signal"], "epoch": p["epoch"]}
        elif t == "invocation_ended":
            inv = _inv(j, p["n"])
            inv["ended"] = {k: p.get(k) for k in ("outcome", "exit_code", "wall_s", "cpu_s", "reserved_vcpu_h",
                                                 "peak_rss_mb", "ended_epoch", "reason")}
            j["reserved_vcpu_h"] += p.get("reserved_vcpu_h") or 0.0
            j["cpu_s"] += p.get("cpu_s") or 0.0
            m = month_of(p["ended_epoch"])
            out["usage"][m] = out["usage"].get(m, 0.0) + (p.get("reserved_vcpu_h") or 0.0)
            if p.get("anchor") is not None:
                j["anchor"] = p["anchor"]
            if p.get("reconcile") is not None:
                j["reconcile"] = p["reconcile"]
            j["consecutive_errors"] = p["consecutive_errors"]
            j["status"] = p["next_status"]
            j["reason"] = p.get("reason")
            j["not_before"] = p.get("not_before_epoch", 0.0)
        elif t == "job_cancelled":
            j["status"], j["reason"] = "cancelled", p.get("reason")
        elif t == "job_requeued":
            j["status"], j["reason"], j["cancel"] = "queued", p.get("reason"), None
            j["max_invocations"] += p.get("extra_invocations", 0)
            j["consecutive_errors"], j["not_before"] = 0, 0.0
        elif t == "job_blocked":
            j["status"], j["reason"] = "blocked", p["reason"]
        elif t == "start_deferred":
            j["deferred"] = p["reason"]
        elif t == "job_audited":
            j["audit"] = {"state": p["state"], "violations": len(p.get("violations") or []), "seq": r["seq"]}
    for j in jobs.values():
        j["category"] = CATEGORY[j["status"]]
        j["n_invocations"] = len(j["invocations"])
        j["open_invocation"] = next((i for i in j["invocations"] if i["ended"] is None), None)
    return out


def _inv(job: dict, n: int) -> dict:
    for i in job["invocations"]:
        if i["n"] == n:
            return i
    raise KeyError(f"{job['job_id']}: no invocation {n}")
