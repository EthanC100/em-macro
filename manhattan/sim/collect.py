"""A run made in pieces: plan the pieces, put their records together, and say what is missing.

    python -m manhattan.sim.collect plan   [--out results/manhattan_sim] [--sizes STD,LONG,HB] [--only D01,D05h]
    python -m manhattan.sim.collect merge  PIECES_DIR [--out results/manhattan_sim]
    python -m manhattan.sim.collect status [--out results/manhattan_sim]          # exit 1 while anything is missing

The full pre-registered development programme is about 1,700 hours of one core. On machines that give a job a
few hours (GitHub's runners: ``.github/workflows/manhattan-sim.yml``) it is made in **pieces**: each piece is one
call of ``python -m manhattan.sim.run --first a --reps b --label part --out <its own directory>``, that is, the
replications ``a`` to ``b − 1`` of one scenario. Seeds depend on the replication number alone, so the pieces
are exactly the replications one machine would have made.

``plan`` lists the pieces still to run: for every run of the development plan, the replications of the
pre-registered count that are not on file for the code now checked out, cut into ranges that one job can finish
(the seconds per replication come from the records on file, else from the table below). Replications already on
file are never run again: the pilots count (SIM_PREREG section 6: a run is continued, not cut).

``merge`` reads every piece under a directory (one sub-directory per piece, as downloaded artifacts are) and
appends its records to the record files under ``--out``. **It refuses, and writes nothing, if any record**

- was made by other code than the code now checked out (records of different code are never pooled),
- is of a scenario, size or replication number outside the development plan and its pre-registered counts,
- is of a held-out or confirmation branch (those need a tagged confirmation run, not this script),
- is an HB record reviewed at any other step than every 63 days (SIM_PREREG_v2, amendment 1), or
- differs from another record of the same replication in anything but its timings (the same seeds must give the
  same numbers: a difference is a fault to look at, not a duplicate to drop).

The pieces' run-log records are appended to ``runs.jsonl`` once each. Nothing here decides anything: it moves
records and counts them. Synthetic data only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from . import criteria_v2, hb_v2, run, runlog, seeds

MAX_JOBS = 256                      # GitHub: matrix jobs in one workflow run
JOB_MINUTES = 285                   # the time budget a piece is given (the job's own limit is 6 hours)
JOB_WORKERS = 4                     # cores of a standard runner
HB_WORKERS = 3                      # an HB replication peaks at several GB (the first reviews use the whole grid): three fit in 16 GB
FILL = 0.6                          # a piece is sized to this share of what a job could do if every core were as fast as
#                                     the timings' machine and never idle: a slower runner then still finishes it
# seconds of one core per replication where no record of the run is on file yet (the session's machine, idle:
# results/manhattan_sim/v2/COMPUTE_OPTIONS.md; HB with quarterly reviews: the pilot of session 10M)
DEFAULT_SECONDS = {"v1-STD": 110.0, "v1-LONG": 70.0, "D11": 380.0, "twin": 320.0, "HB": 1500.0}
TIMING_KEYS = ("seconds",)          # any key containing one of these is a timing, not a result
IDENTITY_KEYS = ("run_id", "commit")


class Refused(RuntimeError):
    """A piece holds a record that may not be pooled with the records on file. Nothing was written."""


def kind(scenario: str, size: str, prereg_version: str = "v2") -> str:
    if run.route(scenario, size, prereg_version) == "v1":
        return f"v1-{size}"
    return "twin" if criteria_v2.is_twin(scenario) else ("HB" if size == "HB" else "D11")


def missing(out: Path = run.OUT, prereg_version: str = "v2") -> dict:
    """``{(scenario, size): replication numbers of the pre-registered count not on file for the current code}``,
    for every run of the development plan, in the plan's order."""
    left = {}
    for scenario, size in run.development_plan(prereg_version):
        version = run.route(scenario, size, prereg_version)
        have = {r["rep"] for r in run.load_reps(scenario, size, seeds.DEVELOPMENT, out, run.code_hash(size, version=version), version)}
        left[(scenario, size)] = [r for r in range(criteria_v2.replications(scenario, size)) if r not in have]
    return left


def seconds_per_replication(scenario: str, size: str, out: Path = run.OUT, prereg_version: str = "v2") -> tuple[float, str]:
    """Seconds of one core per replication, and where the number comes from: this code's records on file when
    there are at least three, otherwise the table."""
    version = run.route(scenario, size, prereg_version)
    reps = run.load_reps(scenario, size, seeds.DEVELOPMENT, out, run.code_hash(size, version=version), version)
    if len(reps) >= 3:
        return float(sum(r["seconds"] for r in reps) / len(reps)), f"{len(reps)} records on file"
    return DEFAULT_SECONDS[kind(scenario, size, prereg_version)], "table"


def _ranges(numbers: list[int]) -> list[tuple[int, int]]:
    """Contiguous runs ``[first, end)`` of a sorted list of replication numbers."""
    out, start = [], None
    for i, n in enumerate(numbers):
        if start is None:
            start = n
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            out.append((start, n + 1))
            start = None
    return out


def plan(out: Path = run.OUT, prereg_version: str = "v2", *, sizes=("STD", "LONG", "HB"), only=(), job_minutes: float = JOB_MINUTES,
         workers: int = JOB_WORKERS, fill: float = FILL, max_jobs: int = MAX_JOBS) -> dict:
    """The pieces still to run, each small enough for one job. Returns ``{"include": [piece, ...], "left_out":
    pieces beyond ``max_jobs`` (run the workflow again when these are done), "cpu_hours": the estimate}``."""
    pieces, hours = [], 0.0
    for (scenario, size), left in missing(out, prereg_version).items():
        if size not in sizes or (only and scenario not in only) or not left:
            continue
        secs, _ = seconds_per_replication(scenario, size, out, prereg_version)
        w = min(workers, HB_WORKERS) if size == "HB" else workers
        per_piece = max(1, int(job_minutes * 60.0 * w * fill // secs))          # core-seconds a piece is sized to
        hours += len(left) * secs / 3600.0
        for a, b in _ranges(left):
            for first in range(a, b, per_piece):
                end = min(b, first + per_piece)
                pieces.append({"id": f"{scenario}-{size}-{first:04d}-{end - 1:04d}", "scenario": scenario, "size": size,
                               "first": first, "reps": end, "replications": end - first, "workers": w,
                               "cpu_hours": round((end - first) * secs / 3600.0, 2)})
    return {"include": pieces[:max_jobs], "left_out": len(pieces[max_jobs:]), "cpu_hours": round(hours, 1),
            "job_minutes": job_minutes, "workers": workers}


def _strip(x):
    """A record without its timings and without the identity of the run that wrote it."""
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if not any(t in k for t in TIMING_KEYS) and k not in IDENTITY_KEYS}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _same(a: dict, b: dict) -> bool:
    return json.dumps(_strip(a), sort_keys=True) == json.dumps(_strip(b), sort_keys=True)


def _read(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def find_pieces(root: Path) -> list[Path]:
    """Every directory under ``root`` (itself included) that holds a ``reps`` or ``v2/reps`` directory."""
    root = Path(root)
    found = {p.parent for p in root.rglob("reps") if p.is_dir() and p.parent.name != "v2"}
    found |= {p.parent.parent for p in root.rglob("v2/reps") if p.is_dir()}
    return sorted(found)


def merge(pieces_root: Path, out: Path = run.OUT, prereg_version: str = "v2", dry_run: bool = False) -> dict:
    """Append the records of every piece under ``pieces_root`` to the record files under ``out``. All or
    nothing: a record that may not be pooled raises ``Refused`` before anything is written."""
    out = Path(out)
    planned = set(run.development_plan(prereg_version))
    problems: list[str] = []
    new: dict = {}                                  # (scenario, size, version) -> {rep: record}
    logs: list[dict] = []
    pieces = find_pieces(pieces_root)
    for piece in pieces:
        for version, folder in (("v1", piece / "reps"), ("v2", piece / "v2" / "reps")):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.jsonl*")):
                stem = path.name.split(".jsonl")[0]
                try:
                    scenario, size, b = stem.rsplit("_", 2)
                    branch = int(b.lstrip("b"))
                except ValueError:
                    problems.append(f"{path}: not a replication file")
                    continue
                where = f"{piece.name}/{path.name}"
                if branch != seeds.DEVELOPMENT:
                    problems.append(f"{where}: seed branch {branch} is a confirmation branch, which this script never collects")
                    continue
                if (scenario, size) not in planned:
                    problems.append(f"{where}: {scenario} at {size} is not a run of the development plan")
                    continue
                if run.route(scenario, size, prereg_version) != version:
                    problems.append(f"{where}: {scenario} at {size} belongs to the other pre-registration version's folder")
                    continue
                code, need = run.code_hash(size, version=version), criteria_v2.replications(scenario, size)
                rows = _read(path)
                if size == "HB" and version == "v2":
                    try:
                        hb_v2.require_review_step(rows, where)
                    except ValueError as e:
                        problems.append(str(e))
                        continue
                for r in rows:
                    rep = r.get("rep")
                    if r.get("code") != code:
                        problems.append(f"{where}: replication {rep} was made by code {r.get('code')}, not {code} (the code now "
                                        "checked out): records of different code are never pooled")
                    elif not isinstance(rep, int) or not 0 <= rep < need:
                        problems.append(f"{where}: replication {rep} is outside 0 to {need - 1}")
                    elif r.get("scenario") != scenario or r.get("size") != size:
                        problems.append(f"{where}: replication {rep} says it is {r.get('scenario')} at {r.get('size')}")
                    else:
                        seen = new.setdefault((scenario, size, version), {})
                        if rep in seen and not _same(seen[rep], r):
                            problems.append(f"{where}: replication {rep} differs from the same replication in another piece")
                        seen.setdefault(rep, r)
        log = piece / "runs.jsonl"
        if log.exists():
            logs += runlog.read(log)
    summary = {"pieces": len(pieces), "added": {}, "already_on_file": {}}
    writes = []
    for (scenario, size, version), recs in sorted(new.items()):
        code = run.code_hash(size, version=version)
        on_file = {r["rep"]: r for r in run.load_reps(scenario, size, seeds.DEVELOPMENT, out, code, version)}
        add = []
        for rep in sorted(recs):
            if rep in on_file:
                if not _same(on_file[rep], recs[rep]):
                    problems.append(f"{scenario} at {size}: replication {rep} differs from the record already on file")
            else:
                add.append(recs[rep])
        summary["added"][f"{scenario}_{size}"] = len(add)
        summary["already_on_file"][f"{scenario}_{size}"] = len(recs) - len(add)
        if add:
            writes.append((run.reps_path(scenario, size, seeds.DEVELOPMENT, out, version), add))
    if problems:
        raise Refused("refused, nothing written:\n  " + "\n  ".join(problems))
    known = {(r.get("run_id"), r.get("event"), r.get("time_utc")) for r in runlog.read(out / "runs.jsonl")}
    fresh, seen_log = [], set()
    for r in sorted(logs, key=lambda r: r.get("time_utc", "")):
        key = (r.get("run_id"), r.get("event"), r.get("time_utc"))
        if key not in known and key not in seen_log:
            seen_log.add(key)
            fresh.append(r)
    summary["run_log_records"] = len(fresh)
    if not dry_run:
        for path, add in writes:
            if path.with_suffix(".jsonl.gz").exists() and not path.exists():
                raise Refused(f"{path.name} is already compacted (gzipped): this run was complete; nothing written")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                for r in add:
                    f.write(json.dumps(r, sort_keys=True, separators=(",", ":"), default=float) + "\n")
        for r in fresh:
            runlog.append(r, out / "runs.jsonl")
    return summary


def status(out: Path = run.OUT, prereg_version: str = "v2") -> tuple[str, int]:
    """A table of every run of the development plan (on file for the current code, pre-registered, missing
    ranges) and the number of replications still missing."""
    lines = ["| scenario | size | code | on file | pre-registered | missing |", "|---|---|---|---|---|---|"]
    total = 0
    for (scenario, size), left in missing(out, prereg_version).items():
        need = criteria_v2.replications(scenario, size)
        total += len(left)
        gaps = ", ".join(f"{a} to {b - 1}" if b - a > 1 else str(a) for a, b in _ranges(left)) or "none"
        lines.append(f"| {scenario} | {size} | {run.route(scenario, size, prereg_version)} | {need - len(left)} | {need} | {gaps} |")
    lines.append("")
    lines.append(f"Replications still to run: {total}." if total else "Every run is at its pre-registered count.")
    return "\n".join(lines), total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.collect", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["plan", "merge", "status"])
    ap.add_argument("pieces", nargs="?", type=Path, help="merge: the directory that holds the pieces")
    ap.add_argument("--out", type=Path, default=run.OUT)
    ap.add_argument("--prereg", choices=list(run.PREREGS), default="v2")
    ap.add_argument("--sizes", default="STD,LONG,HB", help="plan: which sizes")
    ap.add_argument("--only", default="", help="plan: comma-separated scenario ids")
    ap.add_argument("--job-minutes", type=float, default=JOB_MINUTES)
    ap.add_argument("--workers", type=int, default=JOB_WORKERS)
    ap.add_argument("--max-jobs", type=int, default=MAX_JOBS)
    ap.add_argument("--github-output", type=Path, help="plan: also write matrix=... and pieces=... to this file")
    ap.add_argument("--dry-run", action="store_true", help="merge: check everything, write nothing")
    a = ap.parse_args(argv)
    if a.action == "plan":
        p = plan(a.out, a.prereg, sizes=tuple(s for s in a.sizes.split(",") if s), only=tuple(s for s in a.only.split(",") if s),
                 job_minutes=a.job_minutes, workers=a.workers, max_jobs=a.max_jobs)
        if a.github_output:
            with a.github_output.open("a", encoding="utf-8") as f:
                f.write("matrix=" + json.dumps({"include": p["include"]}, separators=(",", ":")) + "\n")
                f.write(f"pieces={len(p['include'])}\n")
        print(json.dumps(p, indent=1))
        return 0
    if a.action == "merge":
        if a.pieces is None:
            ap.error("merge needs the directory that holds the pieces")
        try:
            s = merge(a.pieces, a.out, a.prereg, a.dry_run)
        except Refused as e:
            print(e, file=sys.stderr)
            return 2
        print(json.dumps(s, indent=1, sort_keys=True))
        return 0
    text, left = status(a.out, a.prereg)
    print(text)
    return 0 if left == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
