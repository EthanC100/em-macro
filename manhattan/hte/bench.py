"""Benchmark harness: synthetic workloads at 10^4, 10^5 and 10^6 candidates. **Synthetic data only.**

    python -m manhattan.hte.bench --target 100000 --workers 4 --chunk 512 --out results/manhattan_hte/bench_100k.json
    python -m manhattan.hte.bench --target 1000000 --stages 1 ...         # stage 1 only (cheap screen)
    python -m manhattan.hte.bench --existing-engine 20                     # the existing one-at-a-time backtester

Every number written is *measured* on the machine that ran it (wall clock, process CPU time from ``getrusage``,
peak resident memory of the parent and of the largest worker, bytes on disk). Cloud prices are not measured: they
are assumptions applied in docs/manhattan/hte/BENCHMARKS.md, never here.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import tempfile
import time
from pathlib import Path


def _hardware() -> dict:
    import numpy as np
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem = round(int(line.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    blas = None
    try:
        cfg = np.show_config(mode="dicts")
        b = cfg.get("Build Dependencies", {}).get("blas", {})
        blas = f"{b.get('name')} {b.get('version')}"
    except Exception:
        pass
    flags = ""
    try:
        txt = Path("/proc/cpuinfo").read_text()
        flags = ",".join(f for f in ("avx2", "avx512f", "fma") if f" {f}" in txt)
    except OSError:
        pass
    return {"cpu": cpu, "logical_cpus": os.cpu_count(), "mem_gib": mem, "cpu_flags": flags,
            "python": platform.python_version(), "numpy": np.__version__, "blas": blas,
            "os": platform.platform(), "blas_threads_env": os.environ.get("OPENBLAS_NUM_THREADS")}


def _usage() -> dict:
    s = resource.getrusage(resource.RUSAGE_SELF)
    c = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"cpu_s": s.ru_utime + s.ru_stime + c.ru_utime + c.ru_stime,
            "maxrss_self_mib": s.ru_maxrss / 1024, "maxrss_child_mib": c.ru_maxrss / 1024}


def _du(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def run_bench(target: int, workers: int, chunk: int, stages: tuple, root: Path, cache: bool = True,
              keep: bool = False, seed: int = 20261118) -> dict:
    from . import data as D
    from . import workload as W
    from .policy import Policy
    from .runner import Runner, Workspace, reconcile

    ws_root = root / f"ws-{target}-{workers}-{'-'.join(map(str, stages))}"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    from .kernels import EXECUTION_TIMING
    out: dict = {"target": target, "workers": workers, "chunk": chunk, "stages": list(stages),
                 "feature_cache": cache, "hardware": _hardware(), "synthetic": True,
                 "execution_timing": EXECUTION_TIMING,
                 "use_restriction": "throughput measurement on synthetic data with same-close execution; "
                                    "no return figure here is realistic or evidence"}
    u0, t0 = _usage(), time.perf_counter()
    bundles, scale = W.build(target)
    ws = Workspace(ws_root)
    reg = ws.registry()
    rep = reg.submit(bundles)
    fr = reg.freeze()
    t_reg = time.perf_counter() - t0
    u1 = _usage()
    out["registration"] = {"seconds": t_reg, "cpu_s": u1["cpu_s"] - u0["cpu_s"], "report": rep,
                           "counts": fr["counts"], "scale": scale,
                           "candidates_per_s": fr["n_candidates"] / t_reg}
    panel = D.generate(D.PanelParams(seed=seed))
    out["panel"] = {"data_hash": panel.data_hash, "evaluated_days": panel.fence - Policy().warmup,
                    "assets": {d: panel.n_assets(d) for d in panel.domains()}}
    r = Runner(ws, panel, Policy(), chunk_size=chunk, workers=workers, cache_enabled=cache, stages=stages)
    t1 = time.perf_counter()
    res = r.run()
    wall = time.perf_counter() - t1
    u2 = _usage()
    n = fr["n_candidates"]
    tm = res.get("timings", r.timings)
    out["run"] = {"run_id": r.run_id, "wall_s": wall, "cpu_s": u2["cpu_s"] - u1["cpu_s"],
                  "cpu_utilisation": (u2["cpu_s"] - u1["cpu_s"]) / (wall * workers) if wall else None,
                  "timings": tm, "closed": res.get("closed", True), "result_root": res.get("result_root")}
    a = tm.get("pass_A_s")
    b = tm.get("pass_B_s")
    sel = [x["payload"] for x in r.log.of_type("selection") if x["payload"]["run_id"] == r.run_id]
    n_b = sum(v for k, v in sel[-1]["counts"].items() if k == "computed") if sel else 0
    out["throughput"] = {
        "pass_A_candidates_per_s": n / a if a else None,
        "pass_A_label": "stage 1 only (cheap screen)" if stages == (1,) else "stages 1+2 (screen + screening stats)",
        "pass_B_candidates_per_s": n_b / b if b else None, "pass_B_computed": n_b,
        "run_candidates_per_s": n / wall,
        "end_to_end_including_registration_s": wall + t_reg,
        "end_to_end_including_registration_candidates_per_s": n / (wall + t_reg),
    }
    planned = sel[-1]["counts"] if sel else {}
    out["stage3_accounting"] = {"computed_simulations": int(planned.get("computed", 0)),
                                "exact_aliases_not_simulated": int(planned.get("alias", 0)),
                                "degenerate_not_simulated": int(planned.get("skipped_degenerate", 0)),
                                "dominated_not_simulated": int(planned.get("skipped_dominated", 0))}
    out["memory"] = {"peak_rss_parent_mib": u2["maxrss_self_mib"], "peak_rss_largest_child_mib":
                     u2["maxrss_child_mib"]}
    out["cache"] = res.get("cache", dict(r.cache.stats))
    out["selection_counts"] = sel[-1]["counts"] if sel else None
    out["storage_bytes"] = {
        "registry": _du(ws_root / "registry"), "attempt_log": ws.log_path.stat().st_size,
        "pass_A": _du(r.dir / "A"), "pass_B": _du(r.dir / "B"), "packages": _du(r.dir / "packages"),
        "results": _du(r.dir / "results.bin"), "feature_cache": _du(ws_root / "cache"),
        "total": _du(ws_root)}
    out["storage_bytes"]["per_candidate_excluding_cache"] = (out["storage_bytes"]["total"] -
                                                            out["storage_bytes"]["feature_cache"]) / n
    rec = reconcile(ws, r.run_id)
    out["reconciliation"] = {k: rec[k] for k in ("registered", "attempts", "violations", "final_status")}
    recs = r.log.refresh().records()
    out["log"] = {"records_total": len(recs),
                  "records_this_run": sum(1 for x in recs if x["payload"].get("run_id") == r.run_id),
                  "attempts_started": rec["attempts"]["started"],
                  "attempt_records": sum(1 for x in recs if x["payload"].get("run_id") == r.run_id and x["type"] in
                                         ("attempt_started", "attempt_completed", "attempt_failed",
                                          "attempt_interrupted"))}
    out["cpu_hours"] = {"note": "process CPU time (user+system, parent and workers); not billed time",
                        "per_1k": out["run"]["cpu_s"] / n * 1e3 / 3600, "per_100k": out["run"]["cpu_s"] / n * 1e5
                        / 3600, "per_1m_linear_extrapolation": out["run"]["cpu_s"] / n * 1e6 / 3600}
    vcpus = os.cpu_count() or 1
    out["vcpu_hours_reserved"] = {
        "note": "wall time (registration included) x the machine's vCPUs: what an instance of this size bills, "
                "whatever the CPU utilisation",
        "vcpus": vcpus, "this_run": (wall + t_reg) * vcpus / 3600}
    if not keep:
        shutil.rmtree(ws_root, ignore_errors=True)
    return out


def existing_engine(n_strategies: int = 10, seed: int = 20261118) -> dict:
    """Throughput of the existing daily backtester (manhattan.engine.backtest: one strategy at a time, a Python
    signal callback per decision day) on the same synthetic FX panel, with a 60-day trend signal and volatility
    targeting. This is the status quo the vectorised stage 3 is compared with; it is not the same model."""
    from datetime import date

    import numpy as np

    from manhattan import roles
    from manhattan.engine import backtest, pit
    from manhattan.engine.backtest import Instrument, Strategy

    from . import data as D

    panel = D.generate(D.PanelParams(seed=seed))
    r = panel.returns("fx")
    store = pit.PitStore()
    dates = panel.dates[: panel.fence]
    names = [f"FX{i}" for i in range(r.shape[1])]
    for i, nm in enumerate(names):
        store.add(nm, dates, np.cumprod(1.0 + r[:, i]) * 100.0, lag_days=0)
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
    lo, hi = dates[0].astype(object), dates[-1].astype(object)
    w = pit.Reader(store, caller="session", domain="hte_bench_daily", fence=fence).window(lo, hi)

    def make(L):
        def sig(v):
            out = {}
            for nm in names:
                _, p = v.get(nm, L + 1)
                out[nm] = float(np.sign(p[-1] / p[0] - 1.0)) / len(names) if p.size > L else 0.0
            return out
        return sig

    t0 = time.perf_counter()
    for k in range(n_strategies):
        st = Strategy(tuple(Instrument(nm, nm, cost=1.5e-4) for nm in names), make(20 + 5 * k), vol_target=0.1)
        backtest.run(w, st)
    dt = time.perf_counter() - t0
    return {"strategies": n_strategies, "seconds": dt, "seconds_per_strategy": dt / n_strategies,
            "days": int(dates.size), "assets": len(names), "hardware": _hardware()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=int, default=10_000)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=512)
    ap.add_argument("--stages", default="1,2,3,4")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--root", default=None)
    ap.add_argument("--existing-engine", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.existing_engine:
        res = existing_engine(a.existing_engine)
    else:
        root = Path(a.root) if a.root else Path(tempfile.mkdtemp(prefix="hte-bench-"))
        stages = tuple(int(s) for s in a.stages.split(","))
        res = run_bench(a.target, a.workers, a.chunk, stages, root, cache=not a.no_cache, keep=a.keep)
    txt = json.dumps(res, indent=1, sort_keys=True, default=float)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(txt + "\n")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
