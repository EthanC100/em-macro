"""Run simulation scenarios: parallel, resumable, and logged.

    python -m manhattan.sim.run --scenario D01 --size STD --reps 2000
    python -m manhattan.sim.run --plan development --reps-std 16 --reps-hb 4 --label pilot
    python -m manhattan.sim.run --scenario H01 --size STD --reps 2000 --confirm 1     # needs the tag

Every replication's record is appended to ``results/manhattan_sim/reps/<scenario>_<size>_<branch>.jsonl`` as soon
as it finishes, with the hash of the simulation code that produced it. A later call **continues** from the
replications already there for the same code (SIM_PREREG section 6: a run is continued, not cut); replications
made by different code are never pooled. Every call adds a start and an end record to ``runs.jsonl``.

``--reps`` is the total wanted. Fewer than the pre-registered count (2,000 at STD and LONG, 400 at HB) is a
pilot and is labelled as one everywhere.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from manhattan import prereg

from . import criteria, runlog, seeds, world

OUT = prereg.ROOT / "results/manhattan_sim"
CODE_FILES = ("manhattan/stats/schedule.py", "manhattan/stats/blocklen.py", "manhattan/stats/bootstrap.py",
              "manhattan/stats/spa.py", "manhattan/stats/screening.py", "manhattan/stats/eprocess.py",
              "manhattan/stats/elond.py", "manhattan/stats/hedge.py", "manhattan/sim/seeds.py",
              "manhattan/sim/world.py", "manhattan/sim/pipeline.py")
CODE_FILES_HB = CODE_FILES + ("manhattan/stats/hier.py", "manhattan/stats/tiers.py", "manhattan/sim/hb.py")


def code_hash(size: str = "STD", root: Path = prereg.ROOT) -> str:
    """SHA-256 over the source files that determine a run's numbers (path and bytes), so that every result
    names the code that made it. Files that only report or log are not part of it."""
    h = hashlib.sha256()
    for rel in (CODE_FILES_HB if size == "HB" else CODE_FILES):
        p = root / rel
        h.update(rel.encode())
        h.update(p.read_bytes() if p.exists() else b"")
    return h.hexdigest()[:16]


def reps_path(scenario: str, size: str, branch: int, out: Path = OUT) -> Path:
    return out / "reps" / f"{scenario}_{size}_b{branch}.jsonl"


def load_reps(scenario: str, size: str, branch: int = seeds.DEVELOPMENT, out: Path = OUT,
              code: str | None = None) -> list[dict]:
    """Replication records on file (plain or gzipped), optionally only those made by one code hash; one per
    replication number, in order."""
    path = reps_path(scenario, size, branch, out)
    rows = []
    for p, opener in ((path, open), (path.with_suffix(".jsonl.gz"), gzip.open)):
        if p.exists():
            with opener(p, "rt", encoding="utf-8") as f:
                rows += [json.loads(line) for line in f if line.strip()]
    if code is not None:
        rows = [r for r in rows if r.get("code") == code]
    seen = {}
    for r in rows:
        seen.setdefault(r["rep"], r)
    return [seen[k] for k in sorted(seen)]


def _one(args):
    scenario, size, rep, branch, sha = args
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if size == "HB":
        from . import hb
        return hb.run_replication(scenario, rep, branch=branch, sha=sha)
    from . import pipeline
    return pipeline.run_replication(scenario, size, rep, branch=branch, sha=sha)


def run_scenario(scenario: str, size: str, reps: int, *, label: str | None = None, confirm: int | None = None,
                 workers: int = 1, out: Path = OUT, log: Path | None = None, quiet: bool = False,
                 pooled_rerun: bool = False) -> list[dict]:
    """Bring a scenario run up to ``reps`` replications. Returns all of this code's replication records."""
    if scenario not in world.SCENARIOS and not world.is_heldout(scenario):
        raise SystemExit(f"unknown scenario {scenario}")
    held = world.is_heldout(scenario)
    if not held and size not in world.SCENARIOS[scenario].sizes:
        raise SystemExit(f"{scenario} is not pre-registered at size {size} (SIM_PREREG section 3.1)")
    branch = seeds.confirmation_branch(confirm, pooled_rerun) if confirm is not None else seeds.DEVELOPMENT
    need = criteria.REPLICATIONS[size]
    label = label or ("pilot" if reps < need else ("confirmation" if confirm else "full"))
    if reps < need and label not in ("pilot", "test"):
        raise SystemExit(f"{reps} replications is fewer than the pre-registered {need}: label it pilot")
    code = code_hash(size)
    log = log or out / "runs.jsonl"
    done = load_reps(scenario, size, branch, out, code)
    todo = [r for r in range(reps) if r not in {d["rep"] for d in done}]
    rec = runlog.start(scenario=scenario, size=size, is_heldout=held, confirm=confirm, label=label,
                       reps=range(todo[0] if todo else reps, reps), branch=branch,
                       options={"code": code, "already_on_file": len(done), "to_run": len(todo), "workers": workers,
                                "required_replications": need}, path=log)
    if held:
        runlog.finish(rec, "failed", 0, path=log, extra={"reason": "held-out worlds are not built yet"})
        raise SystemExit("held-out worlds are not built yet (MANHATTAN_PROGRESS.md, milestone C, remaining)")
    path = reps_path(scenario, size, branch, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = seeds.prereg_hash()
    completed, status, t0 = 0, "completed", time.time()
    try:
        with path.open("a", encoding="utf-8") as f:
            def save(r):
                nonlocal completed
                r["code"], r["commit"], r["run_id"] = code, rec["commit"], rec["run_id"]
                f.write(json.dumps(r, sort_keys=True, separators=(",", ":"), default=float) + "\n")
                f.flush()
                done.append(r)
                completed += 1
                if not quiet:
                    print(f"{scenario} {size} rep {r['rep']} done ({len(done)}/{reps}, {time.time() - t0:.0f}s)", flush=True)
            jobs = [(scenario, size, r, branch, sha) for r in todo]
            if workers <= 1:
                for j in jobs:
                    save(_one(j))
            else:
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    for fut in as_completed([pool.submit(_one, j) for j in jobs]):
                        save(fut.result())
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception as e:                                   # logged, then raised: a failed run stays on record
        status = f"failed"
        runlog.finish(rec, "failed", completed, path=log, extra={"reason": repr(e)[:300]})
        raise
    finally:
        if status != "failed":
            runlog.finish(rec, status, completed, path=log,
                          extra={"seconds": round(time.time() - t0, 1), "on_file": len(done)})
    return sorted(done, key=lambda r: r["rep"])


def development_plan() -> list[tuple[str, str]]:
    """Every (scenario, size) of SIM_PREREG section 3.1, STD and LONG first."""
    order = {"STD": 0, "LONG": 1, "HB": 2}
    plan = [(s.id, z) for s in world.SCENARIOS.values() for z in s.sizes]
    return sorted(plan, key=lambda p: order[p[1]])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.run", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario")
    ap.add_argument("--size", choices=list(world.SIZES))
    ap.add_argument("--reps", type=int)
    ap.add_argument("--plan", choices=["development"])
    ap.add_argument("--sizes", default="STD,LONG,HB", help="with --plan: which sizes to run")
    ap.add_argument("--only", default="", help="with --plan: comma-separated scenario ids")
    ap.add_argument("--reps-std", type=int, default=criteria.REPLICATIONS["STD"])
    ap.add_argument("--reps-long", type=int, default=None, help="default: the STD count")
    ap.add_argument("--reps-hb", type=int, default=criteria.REPLICATIONS["HB"])
    ap.add_argument("--label")
    ap.add_argument("--confirm", type=int, choices=[1, 2, 3], help="held-out set of a tagged confirmation run")
    ap.add_argument("--pooled-rerun", action="store_true", help="the one extension SIM_PREREG section 8.3 allows")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 0))
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    try:
        if a.plan:
            sizes, only = a.sizes.split(","), [s for s in a.only.split(",") if s]
            count = {"STD": a.reps_std, "LONG": a.reps_long or a.reps_std, "HB": a.reps_hb}
            for scenario, size in development_plan():
                if size in sizes and (not only or scenario in only):
                    run_scenario(scenario, size, count[size], label=a.label, workers=a.workers, out=a.out)
            return 0
        if not (a.scenario and a.size and a.reps):
            ap.error("give --scenario, --size and --reps, or --plan")
        run_scenario(a.scenario, a.size, a.reps, label=a.label, confirm=a.confirm, workers=a.workers, out=a.out,
                     pooled_rerun=a.pooled_rerun)
        return 0
    except runlog.HeldOutRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
