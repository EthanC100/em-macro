"""Accounting overhead of the HTE -> PR #86 attempt bridge on a synthetic workload. Benchmark only.

Runs, in a temporary directory: the HTE registration of a ``manhattan.hte.workload`` of about ``--target``
candidates, ``Bridge.begin`` (one PR #86 attempt per candidate), the HTE run, ``Bridge.complete`` and the
cross-check (which includes PR #86's strict reconciler). It reports wall time, CPU time and bytes for each step.

It switches the dormant bridge on **in this process only** and supplies the completion writer that calls
``Ledger.record_evaluation`` (owner decision A-1). That is why it lives outside ``manhattan/``: PR #86's capability
scan covers ``manhattan/``. The ledger is a temporary file outside the repository; nothing is evidence.

    python scripts/hte_accounting_bench.py --target 100000 --workers 4 --out results/manhattan_hte_accounting/x.json
"""
from __future__ import annotations

import argparse
import json
import resource
import shutil
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _usage() -> float:
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def _bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size


def _step(out: dict, name: str, fn):
    c0, t0 = _usage(), time.perf_counter()
    res = fn()
    out[name] = {"wall_s": round(time.perf_counter() - t0, 3), "cpu_s": round(_usage() - c0, 3)}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=int, default=10_000)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=512)
    ap.add_argument("--out", default=None)
    ap.add_argument("--root", default=None)
    a = ap.parse_args(argv)
    from manhattan import ledger as L, roles
    from manhattan.hte import data as D, workload as W
    from manhattan.hte.bench import _hardware
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner, Workspace
    from manhattan.hte_accounting import BridgePolicy, bridge as B
    from manhattan.hte_accounting.crosscheck import crosscheck

    root = Path(a.root or tempfile.mkdtemp(prefix="hte-acct-bench-"))
    if ROOT in root.resolve().parents:
        raise SystemExit("the benchmark workspace must be outside the repository")
    B.ENABLED = True                                       # this process only; the constant in source stays False
    out: dict = {"target": a.target, "workers": a.workers, "chunk": a.chunk, "hardware": _hardware(),
                 "synthetic": True, "evidence": "none: synthetic infrastructure measurement",
                 "completion_writer": "Ledger.record_evaluation, supplied by this script (owner decision A-1)"}
    try:
        def register():
            bundles, _ = W.build(a.target)
            ws = Workspace(root / "ws")
            reg = ws.registry()
            reg.submit(bundles)
            reg.freeze()
            return ws
        ws = _step(out, "hte_registration", register)
        panel = D.generate(D.PanelParams())
        book = L.Ledger(root / "ledger.jsonl", writer="hte-accounting-bench", protocol="f" * 64)
        br = B.Bridge(book, BridgePolicy("register_every_evaluation", None, "per_candidate_attempts",
                                         "benchmark fixture, not an approval"),
                      fence=roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False))
        r = Runner(ws, panel, Policy(), chunk_size=a.chunk, workers=a.workers)
        n = len(r.view)
        out["candidates"] = n
        reg = _step(out, "bridge_begin", lambda: br.begin(r))
        out["ledger_bytes_after_begin"] = _bytes(book.path)
        run = _step(out, "hte_run", lambda: r.run())
        comp = _step(out, "bridge_complete", lambda: br.complete(
            r, completion_writer=lambda bk, **kw: bk.record_evaluation(**kw)))
        rep = _step(out, "crosscheck", lambda: crosscheck(r, book))
        pr86 = r.dir / "pr86"
        out.update({
            "hte_chunk_attempts": rep["hte"]["chunk_attempts"]["started"],
            "pr86_attempts": reg["attempts"], "terminals": comp["terminals"],
            "outcome_batches": len(comp["batches"]),
            "max_batch_rows": max(b["hi"] - b["lo"] for b in comp["batches"]),
            "bytes": {"ledger": _bytes(book.path), "ledger_per_candidate": round(_bytes(book.path) / n, 1),
                      "ledger_records": len(book),
                      "outcome_batches": sum(_bytes(pr86 / b["file"]) for b in comp["batches"]),
                      "registration_file": _bytes(pr86 / reg["registration_file"]),
                      "hte_results_bin": _bytes(r.dir / run["results_file"])},
            "consistent": rep["consistent"], "violations": rep["violations"][:5], "units": rep["units"],
            "pr86_reconciler_violations": rep["pr86"]["reconciler_violations"],
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)})
        acct = sum(out[k]["wall_s"] for k in ("bridge_begin", "bridge_complete", "crosscheck"))
        out["overhead"] = {"accounting_wall_s": round(acct, 3), "hte_run_wall_s": out["hte_run"]["wall_s"],
                           "ratio_to_hte_run": round(acct / out["hte_run"]["wall_s"], 2),
                           "per_candidate_ms": round(1000 * acct / n, 3)}
    finally:
        if not a.root:
            shutil.rmtree(root, ignore_errors=True)
    text = json.dumps(out, indent=1, sort_keys=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0 if out.get("consistent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
