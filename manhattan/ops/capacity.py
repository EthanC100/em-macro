"""Capacity harness (criterion O-36): measured runtime and peak memory for N executables.

    python -m manhattan.ops.capacity --n 1000 --mode full --workers 4 --out results/manhattan_ops/capacity/full_1000.json
    python -m manhattan.ops.capacity --n 1000 --mode daily --workers 4 --out ...

Two modes, measured separately:

    full    every executable is compiled and backtested over the exploration window 2005-01-03 to 2019-12-31
            (synthetic data, six instruments, about 3,900 sessions), as screening would
    ledger  the private-ledger write of one nightly increment: N observation records through the journal, and a
            fresh clone's open-and-verify (a local bare repository; network time is not included)
    daily   one nightly increment: every executable is compiled and run over its forward window (its warm-up plus
            one new session), as ``runner.observation_intents`` does, and its new day's observation payload is built

Executables cycle through every signal kind at its natural frequency, with distinct parameters, both sizing rules and
two cost models, so each is a distinct spec. Synthetic data only. Each measurement runs in a fresh process; the
report gives wall time, CPU time (parent and workers) and the peak resident memory of the largest process.
Measurements only: nothing is extrapolated.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import time
from datetime import date, timedelta
from multiprocessing import get_context
from pathlib import Path

from manhattan import spec as S

from . import compiler as CP
from . import data as D

KINDS = [("tsmom", "D", "lookback", range(5, 505)), ("tsmom", "W", "lookback", range(5, 505)),
         ("xs_momentum", "W", "lookback", range(5, 505)), ("reversal", "D", "lookback", range(1, 61)),
         ("carry", "M", "threshold", [round(0.0005 * i, 4) for i in range(1000)]),
         ("calendar", "D", "start_day", range(1, 29)), ("event", "event", "hold", range(1, 61)),
         ("buy_hold", "M", "scale", [round(0.1 + 0.0009 * i, 4) for i in range(1000)])]
FIXED = {"xs_momentum": {"n_long": 2}, "calendar": {"end_day": 28}}
TIMING = {"calendar": "synthetic", "horizon_sessions": 1, "execution_lag": {"minutes": 0, "sessions": 0},
          "data_cutoff": "2019-12-31"}
FULL = (date(2005, 1, 3), date(2019, 12, 31))
FORWARD_START = date(2019, 6, 3)


_FAM = None


def executable_at(i: int) -> CP.Executable:
    """The ``i``-th capacity executable: one hypothesis with a single-point grid, distinct for every ``i``."""
    global _FAM
    if _FAM is None:
        _FAM = S.family(mechanism="SYNTHETIC capacity family", mechanism_class="other", sign="+",
                        counterparty="synthetic", kill_condition="synthetic", tail_exposure="none declared")
    kind, freq, param, values = KINDS[i % len(KINDS)]
    k = i // len(KINDS)
    vals = list(values)
    v = vals[k % len(vals)]
    sizing = "VT10" if (k // len(vals)) % 2 else "EW"
    cost = "C2BP" if (k // (2 * len(vals))) % 2 else "C5BP"
    rep = k // (4 * len(vals))
    h = S.hypothesis(_FAM, domain="syn_daily", data_sources=[{"name": "synthetic", "publication_lag_days": 0}],
                     signal={"kind": kind, "description": f"capacity {rep}", **FIXED.get(kind, {})},
                     frequency=freq, grid={param: [v]}, timing=TIMING,
                     primary_binding={"universe_id": "U_SYN6", "cost_model_id": cost, "sizing_id": sizing})
    return next(CP.iter_executables(_FAM, h, "c" * 40))


def executables(n: int):
    """``n`` distinct executables, streamed."""
    return (executable_at(i) for i in range(n))


_PIT = None


def _init():
    global _PIT
    from manhattan.engine.pit import PitStore
    st = PitStore()
    by = {}
    for s, p, v in D.synthetic_rows(date(2019, 12, 31)):
        by.setdefault(s, ([], []))
        by[s][0].append(p)
        by[s][1].append(v)
    for s, (ps, vs) in sorted(by.items()):
        st.add(s, ps, vs, lag_days=0)
    _PIT = st


def _work(args):
    mode, idx = args
    from manhattan.engine import backtest
    out = 0
    for x in _slice(*idx):
        if mode == "full":
            w = D.forward_window(_PIT, "syn_daily", *FULL)
            res = backtest.run(w, x.strategy())
            out += len(res.result_hash())
        else:
            start = FORWARD_START - timedelta(days=x.warmup_days)
            w = D.forward_window(_PIT, "syn_daily", start, FORWARD_START + timedelta(days=1))
            res = backtest.run(w, x.strategy())
            i = res.dates.size - 1
            payload = {"executable": x.id, "date": str(res.dates[i]), "net": round(float(res.net[i]), 12),
                       "exposure": [round(float(e), 12) for e in res.exposure[i]]}
            out += len(S.canonical_bytes(payload))
    return out


def _slice(start, stop):
    return (executable_at(i) for i in range(start, stop))


def measure(n: int, mode: str, workers: int, chunk: int = 250) -> dict:
    t0, c0 = time.perf_counter(), time.process_time()
    chunks = [(mode, (a, min(a + chunk, n))) for a in range(0, n, chunk)]
    if workers <= 1:
        _init()
        total = sum(_work(c) for c in chunks)
    else:
        with get_context("fork").Pool(workers, initializer=_init) as pool:
            total = sum(pool.imap_unordered(_work, chunks))
    wall = time.perf_counter() - t0
    me, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"n_executables": n, "mode": mode, "workers": workers, "wall_seconds": round(wall, 2),
            "cpu_seconds": round(me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime, 2),
            "parent_cpu_seconds": round(time.process_time() - c0, 2),
            "peak_rss_mib_largest_process": round(max(me.ru_maxrss, kids.ru_maxrss) / 1024, 1),
            "peak_rss_mib_parent": round(me.ru_maxrss / 1024, 1), "check": total,
            "machine": {"cpus": os.cpu_count(), "python": platform.python_version(), "platform": platform.platform()},
            "data": "synthetic, 6 instruments, sessions 2005-01-03 to 2019-12-31"}


def measure_ledger(n: int) -> dict:
    """The private-ledger half of a nightly increment: ``n`` observation records written through the journal to a
    local bare repository (pending, committed, verified pushes), then a fresh clone opened and its chain verified."""
    import subprocess
    import tempfile

    import numpy as np

    from . import store as ST

    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as tmp:
        remote = Path(tmp) / "ledger.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
        intents = [ST.Intent("observation", ("observation", f"AP-{i:016x}", "2026-11-16"),
                             {"net": round(float(rng.normal(0, 0.01)), 12),
                              "exposure": [round(float(e), 12) for e in rng.normal(0, 0.2, 6)], "evidential_weight": 1})
                   for i in range(n)]
        t0 = time.perf_counter()
        s = ST.Store(workdir=Path(tmp) / "a", remote=str(remote)).open()
        s.write(intents, "capacity")
        t_write = time.perf_counter() - t0
        t1 = time.perf_counter()
        fresh = ST.Store(workdir=Path(tmp) / "b", remote=str(remote)).open()
        t_open = time.perf_counter() - t1
        size = (Path(tmp) / "b" / ST.CHAIN).stat().st_size
        assert len(fresh.records) == n
    me, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"n_records": n, "mode": "ledger", "write_seconds": round(t_write, 2), "open_and_verify_seconds": round(t_open, 2),
            "chain_bytes": size, "cpu_seconds": round(me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime, 2),
            "peak_rss_mib_largest_process": round(max(me.ru_maxrss, kids.ru_maxrss) / 1024, 1),
            "machine": {"cpus": os.cpu_count(), "python": platform.python_version()},
            "note": "local bare repository; a real push adds network time"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.ops.capacity")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--mode", choices=("full", "daily", "ledger"), required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--chunk", type=int, default=250)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    r = measure_ledger(a.n) if a.mode == "ledger" else measure(a.n, a.mode, a.workers, a.chunk)
    print(json.dumps(r))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
