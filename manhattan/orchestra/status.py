"""Status: a machine-readable snapshot, a one-line health summary and a loopback-only HTTP view.

``snapshot(root)`` is a pure read of the journal and of the progress files of open invocations. It never takes a
lock and never writes, so it can run while the supervisor works, from another process, or against a copy of the
root fetched from elsewhere. Schema ``manhattan-orchestra/1``:

    schema, generated_utc, generated_epoch, root, host
    supervisor   {last_tick_utc, age_s, stale}           from status.json's own timestamp when read back
    paused, pause_reason, switches_closed
    limits       the effective limits and their hash
    budget       {month, reserved_vcpu_h_used, committed_vcpu_h, cap_vcpu_h, est_spend_sgd, cap_sgd}
    counts       {active, queued, blocked, failed, incomplete, completed, cancelled}
    jobs         one entry per job: id, kind, label, status, category, reason, invocations, last outcome,
                 progress (open invocation), reconciliation state and counts, reserved vCPU-hours, CPU seconds
    attention    the jobs a person must look at (blocked, failed, incomplete), with reasons
    journal      {records, head}: an anchor for the journal itself; keep a copy elsewhere to detect truncation
    anchors      the latest kind-log anchor of every job
    evidence     null: nothing here is evidence

The snapshot holds statuses, counts, hashes and reasons only: no parameter values beyond what identifies a job, no
research statistic, no environment variable.

``serve_http`` binds 127.0.0.1 only (a non-loopback address is refused): reach it remotely through an SSH tunnel or
a private overlay network. It answers ``GET /status.json``, ``GET /health`` and ``GET /`` (plain text), read-only.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import EVIDENCE, SCHEMA
from . import limits as L
from .journal import Journal, read_json
from .state import ACTIVE, CATEGORIES, fold, month_of

STALE_AFTER_S = 600


def _utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot(root: Path, limits: L.Limits | None = None, *, now: float | None = None) -> dict:
    root = Path(root)
    now = time.time() if now is None else now
    limits = limits or L.load(root)
    j = Journal(root / "journal.jsonl")
    recs = j.records()
    st = fold(recs)
    month = month_of(now)
    used = st["usage"].get(month, 0.0)
    committed = used + sum(max(1, x["open_invocation"]["workers"]) *
                           max(0.0, x["open_invocation"]["deadline_epoch"] - now) / 3600
                           for x in st["jobs"].values() if x["status"] in ACTIVE and x["open_invocation"])
    counts = {c: 0 for c in CATEGORIES}
    jobs, attention, anchors = [], [], {}
    for jid in st["order"]:
        x = st["jobs"][jid]
        counts[x["category"]] += 1
        last = next((i for i in reversed(x["invocations"]) if i["ended"]), None)
        prog = None
        if x["open_invocation"]:
            pf = root / x["open_invocation"]["inv_dir"] / "progress.json"
            try:
                p = read_json(pf)
                prog = dict(p.get("progress") or {}, updated_age_s=round(now - p["epoch"], 1),
                            elapsed_s=round(p.get("elapsed_s", 0), 1), group_rss_mb=p.get("group_rss_mb"))
            except (OSError, ValueError, KeyError):
                prog = None
        rec = x["reconcile"] or {}
        entry = {"job_id": jid, "kind": x["kind"], "label": x["label"], "priority": x["priority"], "look": x["look"],
                 "status": x["status"], "category": x["category"], "reason": x["reason"],
                 "invocations": x["n_invocations"], "max_invocations": x["max_invocations"],
                 "consecutive_errors": x["consecutive_errors"],
                 "last_outcome": last["ended"]["outcome"] if last else None,
                 "deferred": x["deferred"] if x["status"] in ("queued", "retry_wait") else None,
                 "not_before_utc": _utc(x["not_before"]) if x["not_before"] > now else None,
                 "progress": prog, "reconcile_state": rec.get("state"),
                 "reconcile_counts": rec.get("counts"), "violations": len(rec.get("violations") or []),
                 "reserved_vcpu_h": round(x["reserved_vcpu_h"], 4), "cpu_s": round(x["cpu_s"], 1),
                 "registered_utc": x["registered_utc"], "identity_sha256": x["identity_sha256"]}
        jobs.append(entry)
        entry["audit"] = x["audit"]
        if x["category"] in ("blocked", "failed", "incomplete"):
            attention.append({"job_id": jid, "status": x["status"], "reason": x["reason"]})
        elif x["audit"] and x["audit"]["state"] == "corrupted":
            attention.append({"job_id": jid, "status": x["status"], "reason": "audit found the files corrupted"})
        if x["anchor"]:
            anchors[jid] = x["anchor"]
    tick = None
    sp = root / "status.json"
    if sp.exists():
        try:
            tick = float(read_json(sp)["generated_epoch"])
        except (OSError, ValueError, KeyError):
            tick = None
    return {"schema": SCHEMA, "generated_utc": _utc(now), "generated_epoch": now, "root": str(root),
            "host": socket.gethostname(),
            "supervisor": {"last_tick_utc": _utc(tick) if tick else None,
                           "age_s": round(now - tick, 1) if tick else None,
                           "stale": tick is None or now - tick > STALE_AFTER_S},
            "paused": st["paused"] or (root / "PAUSE").exists(), "pause_reason": st["pause_reason"],
            "switches_closed": st["switches"],
            "limits": dict(limits.as_dict(), hash=limits.hash()),
            "budget": {"month": month, "reserved_vcpu_h_used": round(used, 3),
                       "committed_vcpu_h": round(committed, 3), "cap_vcpu_h": limits.monthly_vcpu_hours,
                       "price_sgd_per_vcpu_h": limits.price_sgd_per_vcpu_hour,
                       "est_spend_sgd": round(used * limits.price_sgd_per_vcpu_hour, 2),
                       "cap_sgd": limits.monthly_budget_sgd},
            "counts": counts, "jobs": jobs, "attention": attention,
            "journal": {"records": len(recs), "head": recs[-1]["hash"] if recs else None},
            "anchors": anchors, "evidence": EVIDENCE}


def health(snap: dict) -> tuple[str, int]:
    """One line for a phone or a cron mail, and an exit code: 0 fine, 1 needs a person, 2 supervisor silent."""
    c = snap["counts"]
    b = snap["budget"]
    line = (f"orchestra {snap['generated_utc']}: active {c['active']}, queued {c['queued']}, completed "
            f"{c['completed']}, failed {c['failed']}, incomplete {c['incomplete']}, blocked {c['blocked']}, "
            f"cancelled {c['cancelled']}; vCPU-h {b['reserved_vcpu_h_used']:.1f}/{b['cap_vcpu_h']:.0f} in {b['month']}")
    if snap["paused"]:
        line += "; PAUSED"
    if snap["switches_closed"]:
        line += "; SWITCHES CLOSED"
    if snap["supervisor"]["stale"] and (c["active"] or c["queued"]):
        return line + "; SUPERVISOR SILENT", 2
    if snap["attention"]:
        return line + f"; {len(snap['attention'])} need attention", 1
    return line, 0


def render(snap: dict) -> str:
    out = [health(snap)[0], ""]
    out.append(f"{'job':<20} {'kind':<5} {'status':<11} {'inv':>7} {'last':<18} {'progress':<26} label / reason")
    for j in snap["jobs"]:
        p = j["progress"] or {}
        if "done" in p and p.get("total"):
            prog = f"{p['done']}/{p['total']} {p.get('unit', '')}".strip()
        elif p:
            prog = ", ".join(f"{k}={v}" for k, v in p.items() if k.startswith("pass_") or k == "phase")[:26]
        else:
            prog = "-"
        tail = j["label"] + (f" | {j['reason']}" if j["reason"] else "") + (f" | {j['deferred']}" if j["deferred"]
                                                                              else "")
        out.append(f"{j['job_id']:<20} {j['kind']:<5} {j['status']:<11} {j['invocations']:>3}/{j['max_invocations']:<3} "
                   f"{(j['last_outcome'] or '-'):<18} {prog:<26} {tail}")
    return "\n".join(out) + "\n"


def serve_http(root: Path, host: str = "127.0.0.1", port: int = 8765, *, max_requests: int | None = None) -> None:
    if not ipaddress.ip_address(host).is_loopback:
        raise PermissionError("the status server binds a loopback address only; use an SSH tunnel to reach it")
    root = Path(root)

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            snap = snapshot(root)
            if self.path == "/status.json":
                body, ctype, code = json.dumps(snap, indent=1).encode(), "application/json", 200
            elif self.path == "/health":
                line, rc = health(snap)
                body, ctype, code = (line + "\n").encode(), "text/plain; charset=utf-8", 200 if rc == 0 else 503
            elif self.path == "/":
                body, ctype, code = render(snap).encode(), "text/plain; charset=utf-8", 200
            else:
                body, ctype, code = b"not found\n", "text/plain", 404
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.send_response(405)
            self.end_headers()

        do_PUT = do_DELETE = do_PATCH = do_POST

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer((host, port), H)
    try:
        if max_requests is None:
            srv.serve_forever()
        else:
            for _ in range(max_requests):
                srv.handle_request()
    finally:
        srv.server_close()
