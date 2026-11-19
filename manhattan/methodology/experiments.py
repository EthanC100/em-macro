"""The S13 experiments (docs/manhattan/methodology/S13_RESEARCH_METHODOLOGY.md, section 5), reproducible from seeds.

    python -m manhattan.methodology.experiments --out results/manhattan_methodology            # all, ~1 hour on 4 cores
    python -m manhattan.methodology.experiments --only E2 E4 --quick --out /tmp/s13            # a smoke run

    E1   within-family scale: bootstrap SPA (manhattan.stats.spa, unchanged) against the oracle and the
         equal-weight portfolio test, as the grid grows from 6 to 3,000 variants
    E1b  the same question analytically up to 10^7 variants: the bar for the best variant, and the smallest
         single-variant Sharpe ratio found with 80% power
    E2   across-family null calibration at programme scale (1,500 to 120,000 families), shared or disjoint windows
    E3   planted effects at the same scales: power and FDR of candidates (i), (ii) and an offline reference
    E4   candidate duplication: exact, near and fresh copies; which classes are copied; the dedup-first remedy
    E5   negative dependence: opposite-sign twin families on the same data
    E6   selection and reruns: registration after a look (same versus fresh window, winner's curse), correlated
         rerun shopping, bootstrap-seed shopping with the real SPA
    E7   the research funnel: screening, forward enrolment, e-LOND formal support after 3, 5 and 10 years

Every number describes a synthetic generator. A synthetic rejection is a check of a procedure, not a signal.
Seeds: one master seed; every cell's stream is ``SeedSequence([MASTER, crc32(cell name)])``, so a cell can be rerun
alone and gives the same numbers whatever else ran (single numerical environment; see the JSON's ``environment``).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
import zlib
from multiprocessing import get_context
from pathlib import Path

import numpy as np
from scipy.special import ndtri

from manhattan.stats import eprocess, elond, spa

from . import evaluate, maxnull, worlds

MASTER = 20261119
ALPHAS = (0.05, 0.20)
SCALES = {"protocol": (100, 15), "large": (120, 100), "huge": (120, 1000)}
DAYS_RESERVE = 1750
YEARS_RESERVE = DAYS_RESERVE / 252


def rng_for(cell: str) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([MASTER, zlib.crc32(cell.encode())]))


def _parallel(fn, items, workers: int) -> list:
    """``[fn(x) for x in items]``, in a fork pool when ``workers > 1``; order is kept, so results do not depend on
    the worker count (each item carries its own seed)."""
    items = list(items)
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with get_context("fork").Pool(min(workers, len(items))) as pool:
        return pool.map(fn, items, chunksize=1)


# ----------------------------------------------------------------------------------------------- E1, E1b

def _e1_cell(args) -> dict:
    m, rho, effect, sr, reps, cell = args
    rng = rng_for(cell)
    n = DAYS_RESERVE
    rej = {f"spa_{a}": 0 for a in ALPHAS} | {f"oracle_{a}": 0 for a in ALPHAS} | {f"portfolio_{a}": 0 for a in ALPHAS}
    crit = {a: maxnull.critical(a, m, rho) for a in ALPHAS}
    zport = {a: float(ndtri(1 - a)) for a in ALPHAS}
    sd_port = math.sqrt(rho + (1 - rho) / m)
    for _ in range(reps):
        mu = np.zeros(m)
        if effect == "sparse":
            mu[0] = sr / math.sqrt(252)
        elif effect == "dense":
            mu[:] = sr / math.sqrt(252)
        d = mu[:, None] + math.sqrt(rho) * rng.standard_normal((1, n)) + math.sqrt(1 - rho) * rng.standard_normal((m, n))
        res = spa.spa_test(d, rng)
        zmax = math.sqrt(n) * float(d.mean(axis=1).max())
        zp = math.sqrt(n) * float(d.mean(axis=0).mean()) / sd_port
        for a in ALPHAS:
            rej[f"spa_{a}"] += res.p_c <= a
            rej[f"oracle_{a}"] += zmax >= crit[a]
            rej[f"portfolio_{a}"] += zp >= zport[a]
    return {"m": m, "rho": rho, "effect": effect, "sharpe": sr, "reps": reps,
            **{k: v / reps for k, v in rej.items()}}


def e1(reps: int, workers: int, ms=(6, 60, 600, 3000), rhos=(0.5, 0.9)) -> dict:
    cells = []
    for m in ms:
        r = reps if m <= 600 else max(reps // 2, 4)
        for rho in rhos:
            for effect, sr in (("null", 0.0), ("sparse", 1.5), ("dense", 0.5)):
                cells.append((m, rho, effect, sr, r, f"E1|{m}|{rho}|{effect}"))
    rows = _parallel(_e1_cell, cells, workers)
    return {"rows": rows, "window_days": DAYS_RESERVE,
            "note": "daily iid normal returns, unit daily variance; variants equicorrelated rho; sparse: variant 0 "
                    "at the stated annual Sharpe ratio; dense: every variant at it. SPA is manhattan.stats.spa "
                    "unchanged (estimated block length, B 999 extended to 9,999 at p_c <= 0.10)."}


def e1b() -> dict:
    ms = (1, 6, 20, 200, 1_000, 10_000, 51_214, 100_000, 1_000_000, 10_000_000)
    rows = []
    for rho in (0.0, 0.5, 0.9):
        for m in ms:
            c = maxnull.critical(0.05, m, rho)
            d = maxnull.mde_single(0.05, 0.8, m, rho)
            rows.append({"m": m, "rho": rho, "critical_t_0.05": c, "mde_se_80": d,
                         "mde_sharpe_reserve_6.9y": maxnull.sharpe_from_se(d, YEARS_RESERVE),
                         "mde_sharpe_hte_8.8y": maxnull.sharpe_from_se(d, 2220 / 252)})
    return {"rows": rows, "note": "51,214 is the HTE 10^6 workload's variants per family (256,068 / 5); "
                                  "manhattan.spec.MAX_GRID is 200 points per hypothesis."}


# ----------------------------------------------------------------------------------------------- programme runs

def _programme_cell(args) -> dict:
    prog_kw, reps, cell, dedups = args
    prog = worlds.Programme(**prog_kw)
    rng = rng_for(cell)
    rows = {(p, dd): [] for p in evaluate.PROCEDURES for dd in dedups}
    for _ in range(reps):
        d = worlds.draw(prog, rng)
        for p in evaluate.PROCEDURES:
            for dd in dedups:
                rows[(p, dd)].append(evaluate.counts(d, evaluate.screen(d, p, B=prog.B, dedup=dd), prog.B))
    out = []
    for (p, dd), rs in rows.items():
        out.append({"cell": cell, "procedure": p, "dedup": dd, **evaluate.summarise(rs)})
    return {"cell": cell, "programme": prog_kw, "results": out}


def _run_cells(cells, workers):
    return _parallel(_programme_cell, cells, workers)


def e2(reps: int, workers: int) -> dict:
    cells = []
    for name, (B, nb) in SCALES.items():
        r = {"protocol": reps, "large": max(reps // 2, 4), "huge": max(reps // 8, 3)}[name]
        for window in ("shared", "disjoint"):
            for a in (0.05, 0.30):
                kw = dict(B=B, n_b=nb, pi1=0.0, window=window, a=a, b=0.75 - a if a > 0.05 else 0.45)
                cells.append((kw, r, f"E2|{name}|{window}|{a}", (False,)))
    return {"cells": _run_cells(cells, workers),
            "note": "complete null: every FDR equals the probability of at least one rejection"}


def e3(reps: int, workers: int) -> dict:
    cells = []
    for name, (B, nb) in SCALES.items():
        r = {"protocol": reps, "large": max(reps // 2, 4), "huge": max(reps // 8, 3)}[name]
        for sparse in (False, True):
            kw = dict(B=B, n_b=nb, pi1=0.05, sparse=sparse)
            cells.append((kw, r, f"E3|{name}|sparse={sparse}", (False,)))
    return {"cells": _run_cells(cells, workers)}


def e4(reps: int, workers: int) -> dict:
    base = dict(B=100, n_b=15, pi1=0.05)
    configs = {
        "k1": {},
        "exact_same_k3_all": dict(dup_k=3),
        "exact_same_k10_all": dict(dup_k=10),
        "exact_later_k10_all": dict(dup_k=10, dup_where="later"),
        "exact_later_k10_true": dict(dup_k=10, dup_where="later", dup_target="true"),
        "exact_later_k10_null": dict(dup_k=10, dup_where="later", dup_target="null"),
        "exact_same_k10_true": dict(dup_k=10, dup_target="true"),
        "near0.9_same_k10_all": dict(dup_k=10, dup_rho=0.9),
        "near0.9_same_k10_null": dict(dup_k=10, dup_rho=0.9, dup_target="null"),
        "fresh_disjoint_later_k10_all": dict(dup_k=10, dup_where="later", window="disjoint"),
        "exact_later_k10_true_pi0.20": dict(dup_k=10, dup_where="later", dup_target="true", pi1=0.20),
    }
    cells = [(base | kw, reps, f"E4|{name}", (False, True)) for name, kw in configs.items()]
    return {"cells": _run_cells(cells, workers)}


def e5(reps: int, workers: int) -> dict:
    cells = []
    for pi1 in (0.0, 0.05):
        for mirror in (0.0, 0.5, 1.0):
            for a in (0.05, 0.30):
                kw = dict(B=100, n_b=15, pi1=pi1, mirror=mirror, a=a, b=0.75 - a if a > 0.05 else 0.45)
                cells.append((kw, reps, f"E5|pi1={pi1}|mirror={mirror}|a={a}", (False,)))
    return {"cells": _run_cells(cells, workers)}


# ----------------------------------------------------------------------------------------------- E6

def _e6_seed_cell(args) -> dict:
    reps, k_max, cell = args
    rng = rng_for(cell)
    n, m, rho = DAYS_RESERVE, 6, 0.5
    minp = np.empty((reps, k_max))
    for i in range(reps):
        d = math.sqrt(rho) * rng.standard_normal((1, n)) + math.sqrt(1 - rho) * rng.standard_normal((m, n))
        for j in range(k_max):
            minp[i, j] = spa.spa_test(d, np.random.default_rng(rng.integers(2**63))).p_c
    run_min = np.minimum.accumulate(minp, axis=1)
    return {"reps": reps, "by_k": {int(k): {f"size_{a}": float((run_min[:, k - 1] <= a).mean()) for a in ALPHAS}
                                   for k in (1, 2, 5, 10, 20) if k <= k_max},
            "p_spread_sd_mean": float(minp.std(axis=1).mean())}


def selection_study(rng: np.random.Generator, reps: int, pi1: float, *, K: int = 1000, r: int = 50, m: int = 6,
                    rho: float = 0.5, W: int = 350, alpha: float = 0.20) -> dict:
    """Registration after a look. ``K`` candidate families are mined on window A; the ``r`` with the best portfolio
    Sharpe ratio on A are registered and tested with BH at ``alpha`` (oracle family p-values), either on window A
    itself or on a fresh window B with the same true effects. Also returns the winner's curse: the mean true and
    estimated portfolio Sharpe ratios of the registered families."""
    sd_p = math.sqrt(rho + (1 - rho) / m)
    scale = math.sqrt(W / 52)
    acc = {"same": [], "fresh": [], "same_any": [], "fresh_any": [], "true": [], "est_A": [], "est_B": []}
    for _ in range(reps):
        true = rng.random(K) < pi1
        theta = np.where(true, rng.choice([0.5, 1.0, 1.5], size=K, p=[0.5, 0.3, 0.2]), 0.0)
        q = rng.uniform(0.5, 1.0, size=(K, m))
        mu = theta[:, None] * q * scale
        zA, zB = (mu + math.sqrt(rho) * rng.standard_normal((K, 1)) + math.sqrt(1 - rho) * rng.standard_normal((K, m))
                  for _ in range(2))
        portA, portB = zA.mean(axis=1) / sd_p / scale, zB.mean(axis=1) / sd_p / scale
        top = np.argsort(-portA, kind="stable")[:r]
        for z, key in ((zA, "same"), (zB, "fresh")):
            rej = evaluate._bh(maxnull.family_p(z[top].max(axis=1), m, rho), alpha)
            V = int((rej & ~true[top]).sum())
            acc[key].append(V / max(int(rej.sum()), 1))
            acc[key + "_any"].append(V > 0)
        acc["true"].append(float((theta[top, None] * q[top]).mean(axis=1).mean() / sd_p))
        acc["est_A"].append(float(portA[top].mean()))
        acc["est_B"].append(float(portB[top].mean()))
    return {"K_mined": K, "r_registered": r, "reps": reps, "pi1": pi1,
            "fdr_same_window": float(np.mean(acc["same"])), "p_any_false_same_window": float(np.mean(acc["same_any"])),
            "fdr_fresh_window": float(np.mean(acc["fresh"])), "p_any_false_fresh_window": float(np.mean(acc["fresh_any"])),
            "mean_true_portfolio_sharpe_of_registered": float(np.mean(acc["true"])),
            "mean_estimate_on_selection_window": float(np.mean(acc["est_A"])),
            "mean_estimate_on_fresh_window": float(np.mean(acc["est_B"]))}


def rerun_shopping(rng: np.random.Generator, rerun_corr: float, n: int, *, m: int = 6, rho: float = 0.5,
                   ks=(1, 2, 5, 10, 20)) -> dict:
    """Null family looked at ``max(ks)`` times (data vintages, code versions), each look's statistics correlated
    ``rerun_corr`` with the first; the best p-value is kept. Returns the size of that best-of-k at each level."""
    k_max = max(ks)
    first = math.sqrt(rho) * rng.standard_normal((n, 1, 1)) + math.sqrt(1 - rho) * rng.standard_normal((n, 1, m))
    fresh = math.sqrt(rho) * rng.standard_normal((n, k_max, 1)) + math.sqrt(1 - rho) * rng.standard_normal((n, k_max, m))
    z = math.sqrt(rerun_corr) * first + math.sqrt(1 - rerun_corr) * fresh
    z[:, 0] = first[:, 0]
    pmin = np.minimum.accumulate(maxnull.family_p(z.max(axis=2), m, rho), axis=1)
    return {f"k={k}": {f"size_{a}": float((pmin[:, k - 1] <= a).mean()) for a in ALPHAS} for k in ks}


SEED_CHUNKS = 8


def e6(reps: int, workers: int) -> dict:
    out = {}
    for pi1 in (0.0, 0.05):
        out[f"registration_after_look|pi1={pi1}"] = selection_study(rng_for(f"E6|select|{pi1}"), reps, pi1)
    out["rerun_shopping_oracle"] = [{"rerun_corr": rr, **rerun_shopping(rng_for(f"E6|rerun|{rr}"), rr, 100_000)}
                                    for rr in (0.5, 0.9, 0.99)]
    # bootstrap seed shopping with the real SPA test: a fixed number of chunks, so results do not depend on workers
    n_seed = max(reps // 2, SEED_CHUNKS)
    chunks = [(n_seed // SEED_CHUNKS + (i < n_seed % SEED_CHUNKS), 20, f"E6|seed|{i}") for i in range(SEED_CHUNKS)]
    parts = _parallel(_e6_seed_cell, chunks, workers)
    tot = sum(p["reps"] for p in parts)
    out["seed_shopping_spa"] = {"families": tot, "by_k": {
        k: {f"size_{a}": sum(p["by_k"][k][f"size_{a}"] * p["reps"] for p in parts) / tot for a in ALPHAS}
        for k in parts[0]["by_k"]}, "mean_sd_of_p_c_across_seeds": float(
            sum(p["p_spread_sd_mean"] * p["reps"] for p in parts) / tot)}
    return out


# ----------------------------------------------------------------------------------------------- E7

def forward_support(sharpes: np.ndarray, years: int, rng: np.random.Generator, N_F: int, alpha: float = 0.05):
    """Weekly e-LOND forward test of families enrolled together, in the given order; returns rejection weeks."""
    weeks = years * 52
    K = sharpes.size
    Z = sharpes[:, None] / math.sqrt(52) + rng.standard_normal((K, weeks))
    Y = np.maximum(Z, -eprocess.C_WEEKLY)
    inc = eprocess.log_increments(Y, np.ones_like(Y, dtype=bool))
    wealth = eprocess.wealth_paths(eprocess.cumulative_log(inc))[:, 1:]
    res = elond.run(wealth, np.ones_like(wealth, dtype=bool), np.zeros(K, dtype=int), N_F, alpha)
    return res["reject_at"]


def e7(reps: int, workers: int) -> dict:
    out = {"single_sharpe": [], "funnel": []}
    rng = rng_for("E7|single")
    for K, N_F in ((10, 10), (10, 300), (50, 300), (300, 300)):
        for sr in (0.25, 0.5, 1.0, 1.5, 2.0):
            hits = {3: 0, 5: 0, 10: 0}
            tot = 0
            for _ in range(max(reps // 4, 5)):
                rej = forward_support(np.full(K, sr), 10, rng, N_F)
                tot += K
                for y in hits:
                    hits[y] += int(((rej >= 0) & (rej < y * 52)).sum())
            out["single_sharpe"].append({"enrolled": K, "N_F": N_F, "forward_sharpe": sr,
                                         **{f"share_supported_by_year_{y}": hits[y] / tot for y in hits}})
    # End-to-end funnel on the protocol-scale planted world.
    rng = rng_for("E7|funnel")
    for retention in (1.0, 0.5):
        for proc in ("bh_prds", "ebh_elond"):
            acc = {k: [] for k in ("classes", "true_classes", "screened", "screened_false", "fwd_true_3", "fwd_true_5",
                                   "fwd_true_10", "fwd_false_10")}
            prog = worlds.Programme(B=100, n_b=15, pi1=0.05)
            for _ in range(reps):
                d = worlds.draw(prog, rng)
                rej = evaluate.screen(d, proc, B=prog.B)
                idx = np.flatnonzero(rej)
                truth = d.class_true[d.unit_class[idx]]
                sr_fwd = np.where(truth, retention * d.portfolio_sharpe[idx], 0.0)
                acc["classes"].append(d.class_true.size)
                acc["true_classes"].append(int(d.class_true.sum()))
                acc["screened"].append(idx.size)
                acc["screened_false"].append(int((~truth).sum()))
                if idx.size:
                    at = forward_support(sr_fwd, 10, rng, N_F=300)
                    for y in (3, 5, 10):
                        acc[f"fwd_true_{y}"].append(int(((at >= 0) & (at < y * 52) & truth).sum()))
                    acc["fwd_false_10"].append(int(((at >= 0) & ~truth).sum()))
                else:
                    for y in (3, 5, 10):
                        acc[f"fwd_true_{y}"].append(0)
                    acc["fwd_false_10"].append(0)
            out["funnel"].append({"procedure": proc, "retention": retention, "reps": reps,
                                  **{f"mean_{k}": float(np.mean(v)) for k, v in acc.items()}})
    out["note"] = ("forward: weekly Gaussian returns at the stated true Sharpe ratio, scale known, no guard, every "
                   "family enrolled at week 0 in order (optimistic); e-LOND at 5% with gamma(i; N_F) of the "
                   "Protocol. Funnel: protocol-scale planted world (1,500 families, pi1 0.05), screened families "
                   "enrolled, forward Sharpe = retention x the family portfolio's true Sharpe.")
    return out


# ----------------------------------------------------------------------------------------------- CLI

EXPERIMENTS = {"E1": e1, "E1b": e1b, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6, "E7": e7}
FULL_REPS = {"E1": 200, "E2": 400, "E3": 200, "E4": 200, "E5": 300, "E6": 400, "E7": 200}
QUICK_REPS = {"E1": 4, "E2": 8, "E3": 6, "E4": 6, "E5": 6, "E6": 8, "E7": 6}


def environment() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "manhattan/"], capture_output=True, text=True,
                                    check=False).stdout.strip())
    except OSError:
        commit, dirty = None, None
    return {"commit": commit, "manhattan_tree_dirty": dirty, "python": sys.version.split()[0],
            "numpy": np.__version__, "machine": platform.machine(), "master_seed": MASTER}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", default=list(EXPERIMENTS))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in a.only:
        fn = EXPERIMENTS[name]
        t = time.time()
        if name == "E1b":
            res = fn()
        else:
            res = fn((QUICK_REPS if a.quick else FULL_REPS)[name], a.workers)
        res = {"experiment": name, "quick": a.quick, "seconds": round(time.time() - t, 1),
               "environment": environment(), **res}
        (out / f"{name}.json").write_text(json.dumps(res, indent=1, default=_json_default) + "\n")
        print(f"{name}: {res['seconds']} s", flush=True)
    return 0


def _json_default(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.bool_,)):
        return bool(x)
    raise TypeError(type(x))


if __name__ == "__main__":
    raise SystemExit(main())
