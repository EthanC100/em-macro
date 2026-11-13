"""Time a representative slice of the simulation on this machine (session 6M). Timing only: it writes no
replication record and no run-log record, so nothing it computes can be pooled into a result.

    python -m manhattan.sim.benchmark --out results/manhattan_sim/v2/benchmark.json          # about 40 minutes on 4 cores
    python -m manhattan.sim.benchmark --quick --out /tmp/bench.json                           # two jobs, about 5 minutes

The slice is one replication of each kind of run the full development programme is made of:

    D02 STD, D08 STD, D02 LONG     version 1's pipeline (the 17 STD and LONG runs)
    D11 STD                        version 2: the whole pipeline with the hedge re-estimated in every resample
    D05h STD                       version 2: a hedged twin, three SPA tests only
    D08 HB                         version 2: the analytic model, tiers, dormancy (the dearest HB scenario)

**Phase A** runs each job alone, one after the other, in a fresh process: seconds of wall-clock and of CPU time, and
the process's peak memory. **Phase B** runs the same jobs for ``workers`` replications each with ``workers``
processes at once, every core busy, and times each job inside its worker. Parallel efficiency is the time of a job
alone divided by the mean time of the same kind of job when every core is busy: 1 is perfect; a machine whose
"cores" are two threads of one core gives well under 1.

Every worker runs numpy on one thread (as ``scripts/manhattan_sim_run.sh`` does), so a worker is a core.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import sys
import time
from pathlib import Path

SLICE = (("D02", "STD", "v1"), ("D08", "STD", "v1"), ("D02", "LONG", "v1"), ("D11", "STD", "v2"),
         ("D05h", "STD", "v2"), ("D08", "HB", "v2"))
QUICK = (("D02", "STD", "v1"), ("D08", "HB", "v2"))
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")


def _job(args) -> dict:
    """One replication in this (fresh) process; nothing is written anywhere."""
    import resource

    from . import run, seeds
    scenario, size, version, rep = args
    w0, c0 = time.time(), time.process_time()
    run._one((scenario, size, rep, seeds.DEVELOPMENT, seeds.prereg_hash(), version))
    ru = resource.getrusage(resource.RUSAGE_SELF)
    rss = ru.ru_maxrss / (1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0)        # MB: bytes on macOS, KB on Linux
    return {"scenario": scenario, "size": size, "version": version, "rep": rep, "wall": round(time.time() - w0, 2),
            "cpu": round(time.process_time() - c0, 2), "peak_rss_mb": round(rss, 1)}


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def _setup(workers: int | None) -> tuple[int, object]:
    for v in THREAD_VARS:
        os.environ[v] = "1"
    return workers or os.cpu_count() or 1, mp.get_context("spawn")


def run_alone(jobs=SLICE, workers: int | None = None) -> dict:
    """Phase A: each job alone, one after the other, each in a fresh process."""
    workers, ctx = _setup(workers)
    out = {"machine": {"cpu": cpu_model(), "logical_cores": os.cpu_count(), "platform": platform.platform(),
                       "python": platform.python_version()}, "workers": workers, "jobs": [list(j) for j in jobs]}
    t0 = time.time()
    with ctx.Pool(1, maxtasksperchild=1) as pool:
        out["alone"] = [pool.apply(_job, ((s, z, v, 0),)) for s, z, v in jobs]
    out["alone_wall_total"] = round(time.time() - t0, 1)
    return out


def run_busy(out: dict) -> dict:
    """Phase B, added to the result of phase A: the same jobs for ``workers`` replications, every core busy."""
    workers, ctx = _setup(out["workers"])
    t1 = time.time()
    batch = [(s, z, v, r) for r in range(workers) for s, z, v in out["jobs"]]
    with ctx.Pool(workers, maxtasksperchild=1) as pool:
        out["busy"] = pool.map(_job, batch, chunksize=1)
    out["busy_wall_total"] = round(time.time() - t1, 1)
    return summarise(out)


def run_benchmark(jobs=SLICE, workers: int | None = None) -> dict:
    return run_busy(run_alone(jobs, workers))


def summarise(out: dict) -> dict:
    kinds = {}
    for a in out["alone"]:
        k = f"{a['scenario']} {a['size']}"
        busy = [b for b in out["busy"] if (b["scenario"], b["size"]) == (a["scenario"], a["size"])]
        mean_busy = sum(b["wall"] for b in busy) / len(busy)
        same = next(b["wall"] for b in busy if b["rep"] == a["rep"])
        kinds[k] = {"version": a["version"], "alone_wall": a["wall"], "alone_cpu": a["cpu"], "busy_wall_mean": round(mean_busy, 2),
                    "busy_wall_same_replication": same, "efficiency": round(a["wall"] / mean_busy, 3),
                    "efficiency_same_replication": round(a["wall"] / same, 3),
                    "peak_rss_mb": max([a["peak_rss_mb"]] + [b["peak_rss_mb"] for b in busy])}
    out["kinds"] = kinds
    sum_alone = sum(v["alone_wall"] for v in kinds.values())
    out["efficiency"] = round(sum_alone / sum(v["busy_wall_mean"] for v in kinds.values()), 3)
    out["efficiency_same_replication"] = round(sum_alone / sum(v["busy_wall_same_replication"] for v in kinds.values()), 3)
    cpu_busy = sum(b["cpu"] for b in out["busy"])
    out["busy_cpu_hours"] = round(cpu_busy / 3600, 4)
    out["busy_cpu_share_of_cores"] = round(cpu_busy / (out["busy_wall_total"] * out["workers"]), 3)
    out["peak_rss_mb_per_worker"] = max(v["peak_rss_mb"] for v in kinds.values())
    out["peak_rss_mb_all_workers"] = round(out["workers"] * out["peak_rss_mb_per_worker"], 1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.benchmark", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--quick", action="store_true", help="two jobs only: enough to compare one machine with another")
    ap.add_argument("--phase", choices=["all", "alone", "busy"], default="all",
                    help="alone: phase A only, written to --out; busy: phase B added to the phase A already in --out "
                         "(so that an interruption between the two loses only one of them)")
    a = ap.parse_args(argv)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    save = lambda r: a.out.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if a.phase == "busy":
        res = run_busy(json.loads(a.out.read_text(encoding="utf-8")))
    else:
        res = run_alone(QUICK if a.quick else SLICE, a.workers)
        save(res)
        if a.phase == "alone":
            print(f"phase A written to {a.out}: " + ", ".join(f"{x['scenario']} {x['size']} {x['wall']:.0f} s" for x in res["alone"]))
            return 0
        res = run_busy(res)
    save(res)
    for k, v in res["kinds"].items():
        print(f"{k:10s} alone {v['alone_wall']:7.1f} s   every core busy {v['busy_wall_mean']:7.1f} s   efficiency {v['efficiency']:.2f}"
              f"   peak memory {v['peak_rss_mb']:.0f} MB")
    print(f"parallel efficiency with {res['workers']} workers: {res['efficiency']:.2f}; peak memory {res['peak_rss_mb_all_workers']:.0f} MB in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
