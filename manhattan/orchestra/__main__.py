"""Command line: ``python -m manhattan.orchestra --root DIR <command> ...``

    init                                    create the root and its journal
    register KIND --params JSON|@FILE [--priority N] [--look N] [--max-invocations N]
    cancel JOB [--reason TEXT]
    requeue JOB [--reason TEXT] [--extra-invocations N]
    audit JOB                               re-verify a finished job's files against its journaled anchor
    pause [--reason TEXT] | unpause
    tick                                    one supervision step (for cron, launchd or a systemd timer)
    serve [--interval S] [--max-ticks N]    supervise in a loop
    status [--json]                         the snapshot (from the journal; takes no lock)
    health                                  one line; exit 0 fine, 1 attention, 2 supervisor silent
    http [--port P]                         read-only status over HTTP on 127.0.0.1 only
    verify [--anchor JSON]                  verify the journal's hash chain (against an anchor kept elsewhere)
    manifest                                the execution manifest this checkout would record
    cost [--vcpu-hours H]                   budget table for a monthly workload

The root defaults to ``$MANHATTAN_ORCHESTRA_ROOT``. It must be outside the repository checkout, on a local disk.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import cost as C
from . import kinds as K
from . import manifest as M
from . import safety
from . import status as S
from .journal import Journal, JournalError
from .limits import LimitsError
from .supervisor import Supervisor, SupervisorError


def _params(v: str) -> dict:
    if v.startswith("@"):
        return json.loads(Path(v[1:]).read_text(encoding="utf-8"))
    return json.loads(v)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.orchestra", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.environ.get("MANHATTAN_ORCHESTRA_ROOT"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    r = sub.add_parser("register")
    r.add_argument("kind", choices=sorted(K.KINDS))
    r.add_argument("--params", default="{}")
    r.add_argument("--priority", type=int, default=0)
    r.add_argument("--look", type=int, default=0)
    r.add_argument("--max-invocations", type=int)
    c = sub.add_parser("cancel")
    c.add_argument("job")
    c.add_argument("--reason", default="operator")
    q = sub.add_parser("requeue")
    q.add_argument("job")
    q.add_argument("--reason", default="operator")
    q.add_argument("--extra-invocations", type=int, default=0)
    au = sub.add_parser("audit")
    au.add_argument("job")
    p = sub.add_parser("pause")
    p.add_argument("--reason", default="operator")
    sub.add_parser("unpause")
    sub.add_parser("tick")
    s = sub.add_parser("serve")
    s.add_argument("--interval", type=float, default=30.0)
    s.add_argument("--max-ticks", type=int)
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    sub.add_parser("health")
    h = sub.add_parser("http")
    h.add_argument("--port", type=int, default=8765)
    v = sub.add_parser("verify")
    v.add_argument("--anchor")
    sub.add_parser("manifest")
    co = sub.add_parser("cost")
    co.add_argument("--vcpu-hours", type=float, default=C.WORKLOADS["sim_development_programme"]["vcpu_h"])
    a = ap.parse_args(argv)

    if a.cmd == "manifest":
        print(json.dumps(M.build({"kind": None}), indent=1))
        return 0
    if a.cmd == "cost":
        print(json.dumps({"vcpu_h": a.vcpu_hours, "options": C.table(a.vcpu_hours),
                          "assumptions": {"USD_SGD": C.USD_SGD, "EUR_SGD": C.EUR_SGD}}, indent=1))
        return 0
    if not a.root:
        ap.error("give --root or set MANHATTAN_ORCHESTRA_ROOT")
    root = Path(a.root).expanduser().absolute()
    try:
        if a.cmd in ("status", "health", "http", "verify"):
            safety.check_root(root)
            if a.cmd == "status":
                snap = S.snapshot(root)
                print(json.dumps(snap, indent=1) if a.json else S.render(snap), end="" if not a.json else "\n")
                return 0
            if a.cmd == "health":
                line, rc = S.health(S.snapshot(root))
                print(line)
                return rc
            if a.cmd == "http":
                S.serve_http(root, port=a.port)
                return 0
            head = Journal(root / "journal.jsonl").verify(json.loads(a.anchor) if a.anchor else None)
            print(json.dumps(head))
            return 0
        sup = Supervisor(root)
        if a.cmd == "init":
            print(json.dumps({"root": str(sup.root), "journal": sup.journal.head()}))
        elif a.cmd == "register":
            print(json.dumps(sup.register(a.kind, _params(a.params), priority=a.priority, look=a.look,
                                          max_invocations=a.max_invocations)))
        elif a.cmd == "cancel":
            print(json.dumps(sup.cancel(a.job, a.reason)))
        elif a.cmd == "requeue":
            print(json.dumps(sup.requeue(a.job, a.reason, a.extra_invocations)))
        elif a.cmd == "audit":
            rec = sup.audit(a.job)
            print(json.dumps(rec))
            return 0 if rec.get("state") == "closed" else 1
        elif a.cmd == "pause":
            sup.pause(a.reason)
        elif a.cmd == "unpause":
            sup.unpause()
        elif a.cmd == "tick":
            print(json.dumps(sup.tick()))
        elif a.cmd == "serve":
            sup.serve(a.interval, a.max_ticks)
        return 0
    except (K.ParamError, safety.Refused, SupervisorError, LimitsError, JournalError, OSError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
