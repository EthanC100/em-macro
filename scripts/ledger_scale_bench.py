"""Scaling of the Manhattan ledger (PR #86) under an HTE-like attempt workload. Benchmark only; synthetic.

Each phase is measured on its own, in this order, for ``--n`` candidates:

    register    one ``access.register_evaluation`` per candidate (exploration role, one 8.8-year declared window,
                the identity shape of ``manhattan.hte.adapters.to_pr86_identity``)
    complete    one ``Ledger.record_evaluation`` per attempt, except a fixed share closed by ``end_attempt``
                (failed) and a fixed share re-registered and completed again (reruns), so every lifecycle path runs
    reopen      ``Ledger(path)``: verification of the chain and the rebuild of the indexes
    reconcile   ``attempts.reconcile`` (the strict audit) against the final head
    memory      resident memory held by the opened ledger(s), measured in a fresh process (RSS after opening, less
                RSS before), and the peak RSS of the benchmark process

``--layout`` compares ledger layouts: ``single`` (one ledger), ``per_run:K`` (a new ledger every K candidates, as
one ledger per HTE run; re-evaluations land in the latest run's ledger) and ``shard:S`` (S ledgers by the first
hex digits of ``spec_hash``). For each it reports ``looks`` summed over the ledgers beside the true number of
distinct evaluation keys: a layout that splits a key's history across ledgers counts a rerun as a new look and can
no longer see a conflicting result.

The ledgers are temporary files outside the repository. Nothing here is evidence. ``--impl-root`` names the
checkout whose ``manhattan`` package is measured, so the same script measures a ledger before and after a change.

    python scripts/ledger_scale_bench.py --n 100000 --out results/manhattan_ledger_scaling/after_100k.json
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

FAIL_EVERY, RERUN_EVERY = 97, 53          # one candidate in 97 fails; one in 53 is evaluated a second time
WINDOW = {"id": "hte-synthetic:2000-01-03:2008-10-31", "start": "2000-01-03", "end": "2008-10-31",
          "frequency": "daily"}


def _h(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def identity(i: int, run: str = "bench") -> dict:
    exe = _h("executable", run, i)
    return {"executable": exe, "variant": f"v{i // 4}", "hypothesis": f"h{i % 15}", "family": f"f{i % 5}",
            "batch": f"hte-{run}", "role": "exploration", "channel": "blind", "designated": False,
            "spec_hash": exe, "data_hash": _h("data"), "window": dict(WINDOW),
            "code_version": {"commit": _h("commit")[:40], "engine_sha256": _h("engine"),
                             "numeric_environment_sha256": _h("environment")}}


def result_hash(i: int) -> str:
    return _h("result", i)


def _usage() -> float:
    a = resource.getrusage(resource.RUSAGE_SELF)
    return a.ru_utime + a.ru_stime


_MEMORY = """
import gc, json, os, sys
sys.path.insert(0, sys.argv[1])
from manhattan import ledger as L
def rss():
    with open("/proc/self/statm") as f:
        return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
gc.collect(); r0 = rss()
books = [L.Ledger(p, writer="m", protocol="f" * 64) for p in sys.argv[2:]]
gc.collect(); print(json.dumps({"bytes": rss() - r0, "records": sum(len(b) for b in books)}))
"""


def _layout(spec: str):
    kind, _, arg = spec.partition(":")
    if kind == "single":
        return lambda i, rerun, n: 0
    if kind == "per_run":
        k = int(arg)
        return lambda i, rerun, n: (n - 1) // k if rerun else i // k
    if kind == "shard":
        s = int(arg)
        return lambda i, rerun, n: int(identity(i)["spec_hash"][:8], 16) % s
    raise SystemExit(f"unknown layout {spec}")


def run(n: int, root: Path, impl_root: Path | None, layout: str = "single") -> dict:
    if impl_root is not None:
        sys.path.insert(0, str(impl_root))
    from manhattan import access as A, attempts as AT, ledger as L, roles
    out: dict = {"n": n, "impl": str(impl_root or "this checkout"), "layout": layout, "synthetic": True,
                 "evidence": "none: synthetic infrastructure measurement"}
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
    win = A.DeclaredWindow(WINDOW["id"], "hte-synthetic:bench", date(2000, 1, 3), date(2008, 10, 31),
                           "exploration", "evaluation", _h("data"))
    route = _layout(layout)
    books: dict = {}

    def book_for(i: int, rerun: bool = False):
        j = route(i, rerun, n)
        if j not in books:
            books[j] = L.Ledger(root / f"ledger_{j:05d}.jsonl", writer="ledger-scale-bench", protocol="f" * 64)
        return books[j]

    def phase(name, fn):
        gc.collect()
        c0, t0 = _usage(), time.perf_counter()
        res = fn()
        wall = time.perf_counter() - t0
        out[name] = {"wall_s": round(wall, 3), "cpu_s": round(_usage() - c0, 3),
                     "us_per_candidate": round(1e6 * wall / n, 1)}
        return res

    def register():
        return [A.register_evaluation(book_for(i), identity=identity(i), windows=[win], caller="session",
                                      fence=fence).attempt_id for i in range(n)]
    aids = phase("register", register)

    def complete():
        reruns = []
        for i, a in enumerate(aids):
            book = book_for(i)
            if i % FAIL_EVERY == 0:
                book.end_attempt(a, status="failed", reason="execution_error", data_read=True)
                continue
            book.record_evaluation(**identity(i), result_hash=result_hash(i), n_obs=2000,
                                   summary={"row": i}, seed=i, attempt_id=a)
            if i % RERUN_EVERY == 0:
                reruns.append(i)
        for i in reruns:                       # a second evaluation of the same key: a rerun, one look
            book = book_for(i, rerun=True)
            a = A.register_evaluation(book, identity=identity(i), windows=[win], caller="session",
                                      fence=fence).attempt_id
            book.record_evaluation(**identity(i), result_hash=result_hash(i), n_obs=2000,
                                   summary={"row": i}, seed=i, attempt_id=a)
        return len(reruns)
    out["reruns"] = phase("complete", complete)
    completed = sum(1 for i in range(n) if i % FAIL_EVERY)
    out["ledgers"] = len(books)
    out["records"] = sum(len(b) for b in books.values())
    out["looks"] = {"summed_over_ledgers": sum(b.looks() for b in books.values()),
                    "distinct_evaluation_keys": completed}
    heads = {j: {"records": len(b), "head": b.head} for j, b in books.items()}
    paths = {j: b.path for j, b in books.items()}
    out["ledger_bytes"] = sum(p.stat().st_size for p in paths.values())
    out["peak_rss_mib_write"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    del books, aids
    gc.collect()
    phase("reopen", lambda: [L.Ledger(p, writer="ledger-scale-bench", protocol="f" * 64) for p in paths.values()])
    gc.collect()
    m = json.loads(subprocess.run([sys.executable, "-c", _MEMORY, str(impl_root), *map(str, paths.values())],
                                  capture_output=True, text=True, check=True).stdout)
    out["memory"] = {"ledger_resident_mib": round(m["bytes"] / 2 ** 20, 1),
                     "bytes_per_record": round(m["bytes"] / m["records"], 1),
                     "bytes_per_candidate": round(m["bytes"] / n, 1)}
    reps = phase("reconcile", lambda: [AT.reconcile(ledger_path=paths[j], ledger_anchor=heads[j]) for j in paths])
    out["reconcile_report"] = {k: sum(r[k] for r in reps) for k in ("registered_executions", "completed", "failed",
                                                                      "unfinished", "completed_evaluation_keys")}
    out["reconcile_violations"] = sum(len(r["violations"]) for r in reps)
    out["peak_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--impl-root", default=None, help="checkout whose manhattan package is measured")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--layout", default="single", help="single | per_run:K | shard:S")
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    impl = Path(a.impl_root).resolve() if a.impl_root else repo
    root = Path(a.workdir or tempfile.mkdtemp(prefix="ledger-scale-"))
    if repo in root.resolve().parents or impl in root.resolve().parents:
        raise SystemExit("the benchmark ledger must be outside the repository")
    try:
        out = run(a.n, root, impl, a.layout)
    finally:
        if not a.workdir:
            shutil.rmtree(root, ignore_errors=True)
    text = json.dumps(out, indent=1, sort_keys=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0 if out["reconcile_violations"] == 0 and out["reconcile_report"].get("unfinished") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
