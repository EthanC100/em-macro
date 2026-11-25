"""Audit a private-ledger snapshot against an anchor held elsewhere (PAPER_RUNNER_READINESS.md section 4).

    python -m manhattan.ops.audit --remote URL_OR_PATH --anchor ANCHOR.json [--mirror URL_OR_PATH] [--json OUT]
    python -m manhattan.ops.audit --remote URL_OR_PATH --print-anchor

Clones the ledger into a temporary directory (the only copy it reads; never the runner's working clone), recomputes
the hash chain, checks it reaches the supplied anchor ``{"records": n, "head": hash}``, optionally compares the
mirror record by record, and runs the attempt reconciler (``manhattan.attempts.reconcile``) up to the anchor.

Output: status words, counts, hashes and violation codes with sequence numbers. **Never a payload value**: an
auditor who is not eligible to see unpublished forward performance can run it. ``--print-anchor`` prints the current
``{records, head}`` so the anchor's custodian can retain it (the custodian must not be the ledger's writer: D-7).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from manhattan import attempts
from . import store as ST

COUNTS = ("registered_executions", "distinct_specifications", "completed", "failed", "aborted", "unfinished",
          "repeated_observations", "completed_evaluation_keys", "independent_statistical_tests")


def audit(remote: str, anchor: dict | None, mirror: str | None = None, workdir: Path | None = None) -> dict:
    tmp = Path(workdir or tempfile.mkdtemp(prefix="ledger-audit-"))
    try:
        s = ST.Store(workdir=tmp / "clone", remote=remote).open()      # raises if the chain does not verify
        out = {"chain_ok": True, "records": len(s.records), "head": s.head}
        if anchor is None:
            return out
        n = int(anchor["records"])
        out["anchor"] = {"records": n, "head": anchor["head"]}
        out["records_after_anchor"] = len(s.records) - n
        if mirror:
            m = ST.Store(workdir=tmp / "mirror", remote=mirror).open()
            out["mirror"] = ST.verify_pair(s.records, m.records)["status"]
        rep = attempts.reconcile(store_chain=s.workdir / ST.CHAIN, store_anchor=out["anchor"])
        out["access_reconciled"] = rep["access_reconciled"]
        out["counts"] = {k: rep.get(k) for k in COUNTS if k in rep}
        out["violations"] = [{"code": v.get("code"), "seq": v.get("seq")} for v in rep["violations"]]
        out["certification"] = "checked_against_supplied_anchor"        # never independently certified (D-7)
        out["integrity_ok"] = True
        return out
    finally:
        if workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.ops.audit")
    ap.add_argument("--remote", required=True)
    ap.add_argument("--anchor")
    ap.add_argument("--mirror")
    ap.add_argument("--print-anchor", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if not a.print_anchor and not a.anchor:
        ap.error("--anchor is required unless --print-anchor")
    try:
        anchor = None if a.print_anchor else json.loads(Path(a.anchor).read_text())
        out = audit(a.remote, anchor, a.mirror)
    except Exception as e:                                              # noqa: BLE001 - class only, never text
        out = {"integrity_ok": False, "error_class": type(e).__name__}   # broken chain, anchor not reached, ...
    text = json.dumps(out if not a.print_anchor else {k: out.get(k) for k in ("records", "head")}, sort_keys=True)
    if a.json:
        Path(a.json).write_text(text + "\n")
    print(text)
    return 0 if out.get("integrity_ok", out.get("chain_ok")) and out.get("access_reconciled", True) else 1


if __name__ == "__main__":
    sys.exit(main())
