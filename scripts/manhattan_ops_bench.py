"""Per-stage benchmark of the Manhattan ops path on SYNTHETIC data only (no network, no real market data).

    python scripts/manhattan_ops_bench.py --families 10 20 50 --nights 5 --out /tmp/bench_ops.json

For each size it runs, in a fresh temporary directory, the path ``tests/test_manhattan_ops_e2e.py`` proves:

    mock generation -> mechanical critic -> compile -> historical screening (exploration role, synthetic to
    2019-12-31) -> freeze_pr.prepare (+ commit to a public stand-in) -> capture-only night -> registration ->
    N forward nights (open, recovery, lock, missed runs, capture, forward-observation attempts: register, read,
    compute, plan, completion, commit results+terminals; heartbeat, unlock, private log, mirror, verify) ->
    a final mirror verification

with local bare git repositories standing in for the private ledger and its mirror. The commit identity of every
forward run is the repository's HEAD, because ``runner.run_fence`` verifies ``config/manhattan.yaml`` at that commit
(as ``tests/manhattan_attempt_fixtures.HEAD``).

Per-stage times inside a night are measured by wrapping the runner's collaborators **in this process only**
(nothing in ``manhattan/`` is changed); only the outermost wrapped call is timed, so stage times never double count,
and what no wrapper covers is reported as ``other``. Families, unique executable configurations (distinct spec
hashes) and attempts are reported separately everywhere; historical screening and forward confirmation are reported
separately and never summed into one figure except in ``attempts_all_kinds``, which says so.

Output: one JSON file (default: a temporary directory). Measurements only; no projection is made here.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import io
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manhattan import access as A                         # noqa: E402
from manhattan import config as MC                        # noqa: E402
from manhattan import roles                               # noqa: E402
from manhattan import spec as S                           # noqa: E402
from manhattan.engine.pit import PitStore                 # noqa: E402
from manhattan.generate import parse_reply                # noqa: E402
from manhattan.ops import compiler as CP                  # noqa: E402
from manhattan.ops import critic_rules                    # noqa: E402
from manhattan.ops import data as D                       # noqa: E402
from manhattan.ops import forward as FW                   # noqa: E402
from manhattan.ops import freeze_pr, mockgen              # noqa: E402
from manhattan.ops import runner as R                     # noqa: E402
from manhattan.ops import store as ST                     # noqa: E402
from manhattan.ops import timing as TM                    # noqa: E402

SCHEMA = 1
SCREEN = (date(2015, 1, 2), date(2019, 12, 31))           # as the e2e test
NIGHT0 = date(2026, 11, 12)                                # capture-only night before registration (Thursday)
MERGED = "2026-11-13T15:00:00Z"
WITNESSED = "2026-11-13T16:30:00Z"
FIRST_FORWARD = date(2026, 11, 16)                         # Monday after the Friday registration


def head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def git(*a, cwd) -> str:
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


def cpu() -> float:
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def nbytes(p: Path) -> int:
    p = Path(p)
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def commits(bare: Path) -> int:
    r = subprocess.run(["git", "--git-dir", str(bare), "rev-list", "--count", "main"], capture_output=True, text=True)
    return int(r.stdout.strip()) if r.returncode == 0 else 0


def gc_bytes(bare: Path, scratch: Path) -> int:
    """Size of a copy of a bare repository after ``git gc`` (delta-compressed packs), as a host that repacks would
    store it. Every chain commit rewrites ``chain.jsonl`` whole, so before a repack each commit adds a full blob."""
    shutil.copytree(bare, scratch)
    subprocess.run(["git", "--git-dir", str(scratch), "gc", "-q", "--prune=now"], check=True, capture_output=True)
    return nbytes(scratch)


def machine() -> dict:
    cpu_name = "unknown"
    with contextlib.suppress(OSError):
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_name = line.split(":", 1)[1].strip()
                break
    nproc = subprocess.run(["nproc"], capture_output=True, text=True).stdout.strip()
    gitv = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    import numpy as np
    return {"nproc": int(nproc) if nproc.isdigit() else os.cpu_count(), "cpu": cpu_name,
            "python": platform.python_version(), "numpy": np.__version__, "git": gitv, "os": platform.platform()}


class Clock:
    """The runner's injected clock (record timestamps), as in the e2e test. Wall time is measured separately."""

    def __init__(self):
        self.t = None

    def at(self, s):
        self.t = TM.parse_time(s)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


class Profiler:
    """Outermost-only timing of wrapped callables: a nested wrapped call is part of its caller's stage."""

    def __init__(self):
        self.depth = 0
        self.wall = defaultdict(float)
        self.calls = Counter()

    def wrap(self, fn, label):
        prof = self

        @functools.wraps(fn)
        def inner(*a, **k):
            if prof.depth:
                return fn(*a, **k)
            lab = label(a, k) if callable(label) else label
            prof.depth += 1
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                prof.wall[lab] += time.perf_counter() - t0
                prof.calls[lab] += 1
                prof.depth -= 1
        return inner

    def reset(self):
        self.wall.clear()
        self.calls.clear()


def _write_label(a, k):
    label = a[2] if len(a) > 2 else k.get("label", "")
    word = str(label).split(" ")[0] if label else "other"
    return {"capture": "capture_write", "heartbeat": "heartbeat", "missed": "missed_runs"}.get(word, f"write:{word}")


PATCHES = [  # (owner, attribute, stage label)
    (ST.Store, "open", "open_clone_verify"),
    (ST.Store, "reconcile", "journal_reconcile"),
    (ST.Store, "acquire", "lock"),
    (ST.Store, "release", "unlock"),
    (ST.Store, "write", _write_label),
    (ST.Store, "put_files", "private_log_commit"),
    (ST.Store, "mirror", "mirror_push"),
    (ST.Store, "verify_mirror", "mirror_verify"),
    (A, "commit_recovery", "attempt_recovery"),
    (A, "register_store_attempts", "fwd_register_attempts"),
    (A, "run_bound", "fwd_compute"),
    (A, "completion", "fwd_completion"),
    (A, "commit_results", "fwd_commit_results_terminals"),
    (D, "capture_intent", "capture_parse_hash"),
    (D, "first_seen", "pit_first_seen"),
    (D.FirstSeen, "pit_store", "pit_build"),
    (D, "forward_window", "fwd_read_window"),
    (FW, "plan", "fwd_plan"),
    (R, "load_batch", "load_batches"),
    (R, "run_fence", "fence_verify_at_commit"),
    (R, "missed_run_intents", "missed_runs"),
    (R, "registrations", "registrations_index"),
]


@contextlib.contextmanager
def instrumented(prof: Profiler):
    saved = []
    for owner, attr, label in PATCHES:
        orig = getattr(owner, attr)
        saved.append((owner, attr, orig))
        setattr(owner, attr, prof.wrap(orig, label))
    try:
        yield prof
    finally:
        for owner, attr, orig in reversed(saved):
            setattr(owner, attr, orig)


@contextlib.contextmanager
def silenced(path: Path):
    """The runner prints its public health record; send fds 1 and 2 to a file during a run."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    with open(path, "a") as f:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


def timed(out: dict, name: str, fn):
    c0, t0 = cpu(), time.perf_counter()
    res = fn()
    out[name] = {"wall_s": round(time.perf_counter() - t0, 4), "cpu_s": round(cpu() - c0, 4)}
    return res


def ledger_bytes(workdir: Path) -> dict:
    w = Path(workdir)
    parts = {"chain_jsonl": nbytes(w / ST.CHAIN), "journal_jsonl": nbytes(w / ST.JOURNAL), "raw": nbytes(w / "raw"),
             "logs": nbytes(w / "logs")}
    parts["other_files"] = max(0, nbytes(w) - nbytes(w / ".git") - sum(parts.values()))
    parts["working_tree_total"] = sum(parts.values())
    return parts


def weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def attempt_counts(records: list[dict]) -> dict:
    started = Counter(r["payload"].get("kind", "?") for r in records if r["type"] == "attempt_started")
    terminals = Counter()
    for r in records:
        if r["type"].startswith("attempt_") and r["type"] != "attempt_started":
            terminals[r["payload"].get("status", r["type"])] += 1
    return {"started_by_kind": dict(started), "terminal_by_status": dict(terminals)}


def run_size(n_families: int, nights: int, base: Path, commit: str, max_hypotheses: int = 2) -> dict:
    root = base / f"f{n_families}"
    root.mkdir(parents=True)
    clock = Clock()
    pipe: dict = {}
    failures: list = []
    quiet = root / "runner_stdout.txt"

    # ---- generation (mock, no model)
    def gen():
        req = mockgen.blind_request(n_families=n_families, max_hypotheses=max_hypotheses, domains=("syn_daily",))
        reply = mockgen.mock_reply(req, n=n_families)
        fams, hyps = parse_reply(reply, "blind")
        return req, fams, hyps
    req, fams, hyps = timed(pipe, "generate_mock", gen)

    # ---- mechanical critic
    mech = timed(pipe, "critic_mechanical", lambda: critic_rules.review(fams, hyps))
    blocked = [r["target_id"] for r in mech if r["block"]]
    if blocked:
        failures.append({"stage": "critic", "blocked": len(blocked)})

    # ---- compile
    exes = timed(pipe, "compile", lambda: list(CP.iter_batch(fams, hyps, commit)))
    spec_hashes = {x.spec_hash for x in exes}
    variants = {S.spec_hash(x.variant) for x in exes}

    remote, mirror = root / "ledger.git", root / "mirror.git"
    for b in (remote, mirror):
        git("init", "-q", "--bare", "-b", "main", str(b), cwd=root)

    # ---- historical screening (exploration role, synthetic data to 2019-12-31): a filter, never evidence
    clock.at("2026-11-12T12:00:00Z")

    def screening():
        st_ = PitStore()
        by: dict = {}
        for s_, p_, v_ in D.synthetic_rows(SCREEN[1]):
            by.setdefault(s_, ([], []))
            by[s_][0].append(p_)
            by[s_][1].append(v_)
        for s_, (ps, vs) in by.items():
            st_.add(s_, ps, vs, lag_days=0 if "px" in s_ or "evt" in s_ else 1)
        fence = roles.Fence.from_config(MC.load())
        sc = ST.Store(workdir=root / "rt-screen/ledger", remote=str(remote), run_id="900", commit=commit,
                      clock=clock).open()
        with silenced(quiet):
            ret = R.screen(sc, exes, st_, fence, *SCREEN)
        return ret
    c_before = commits(remote)
    returns = timed(pipe, "historical_screening", screening)
    screen_git = commits(remote) - c_before
    after_screen = ST.Store(workdir=root / "peek-screen", remote=str(remote)).open()
    screen_bytes = ledger_bytes(after_screen.workdir)
    screen_attempts = attempt_counts(after_screen.records)

    # ---- freeze tooling into a public stand-in, then "the owner merges"
    public = root / "public"
    public.mkdir()
    git("init", "-q", "-b", "main", cwd=public)
    git("config", "user.email", "bench@example.invalid", cwd=public)
    git("config", "user.name", "bench", cwd=public)

    def prep_fn():
        p = freeze_pr.prepare(1, fams, hyps, out_root=public / "data/manhattan/batches", code_version=commit,
                              protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock-no-model",
                              template_hash=req.template_hash, fence={}, screening_returns=returns)
        git("add", "-A", cwd=public)
        git("commit", "-qm", "batch AB-0001 manifest (synthetic benchmark)", cwd=public)
        return p
    prep = timed(pipe, "freeze_pr_prepare_and_commit", prep_fn)
    batches = public / "data/manhattan/batches"
    public_bytes = nbytes(batches)

    def cfg(asof, run, attempt=1):
        return R.RunConfig(ledger_dir=root / f"rt{run}.{attempt}/private/ledger", remote=str(remote),
                           batches_dir=batches, asof=asof, sources=("synthetic",), mirror=str(mirror),
                           run_id=str(run), run_attempt=attempt, commit=commit,
                           private_dir=root / f"rt{run}.{attempt}/private", run_calendar="synthetic")

    def fetch(a):
        return {"synthetic": (lambda: D.synthetic_csv(a))}

    prof = Profiler()
    night_rows = []

    def one_night(asof: date, run: int, kind: str) -> dict:
        c = cfg(asof, run)
        r0, m0, bare0 = commits(remote), commits(mirror), nbytes(remote)
        prof.reset()
        clock.at(f"{asof.isoformat()}T23:30:00Z")
        c0, t0 = cpu(), time.perf_counter()
        with instrumented(prof), silenced(quiet):
            h = R.nightly(c, fetch(asof), clock=clock)
        wall = time.perf_counter() - t0
        cpu_s = cpu() - c0
        stages = {k: round(v, 4) for k, v in sorted(prof.wall.items())}
        stages["other"] = round(max(0.0, wall - sum(prof.wall.values())), 4)
        fwd = sum(v for k, v in prof.wall.items() if k.startswith("fwd_"))
        attempts = int(h.get("attempts_registered", 0))
        lb = ledger_bytes(c.ledger_dir)
        row = {"asof": asof.isoformat(), "kind": kind, "status": h.get("status"), "wall_s": round(wall, 4),
               "cpu_s": round(cpu_s, 4), "stages_wall_s": stages, "stage_calls": dict(prof.calls),
               "attempts": attempts, "forward_attempt_phase_wall_s": round(fwd, 4),
               "attempts_per_s_forward_phase": round(attempts / fwd, 2) if attempts and fwd else None,
               "attempts_per_s_whole_night": round(attempts / wall, 2) if attempts else None,
               "observations_new": int(h.get("observations_new", 0)),
               "missed_observations": int(h.get("missed_observations", 0)),
               "captures_new": int(h.get("captures_new", 0)),
               "git_commits_private_ledger": commits(remote) - r0, "git_commits_mirror": commits(mirror) - m0,
               "ledger_working_tree_bytes_after": lb,
               "bare_remote_bytes_delta": nbytes(remote) - bare0,
               "sources_failed": list(h.get("sources_failed", [])), "conflicts": int(h.get("conflicts", 0)),
               "mirror_ok": h.get("mirror_ok")}
        if h.get("status") != "ok":
            failures.append({"stage": f"night {asof}", "status": h.get("status"), "error_class": h.get("error_class"),
                             "failed_stage": h.get("stage")})
        return row

    # night 0: capture only, before anything is registered
    night_rows.append(one_night(NIGHT0, 101, "capture_only_before_registration"))

    # registration
    c_before = commits(remote)

    def reg():
        clock.at("2026-11-13T16:45:00Z")
        pr = {"merged": True, "merged_at": MERGED, "merge_commit_sha": "d" * 40}
        w = TM.Witness("opentimestamps", prep["manifest_hash"], TM.parse_time(WITNESSED), True)
        with silenced(quiet):
            return R.register(cfg(date(2026, 11, 13), 102), 1, pr, w, clock=clock)
    hreg = timed(pipe, "registration", reg)
    reg_git = commits(remote) - c_before
    if hreg.get("status") != "ok":
        failures.append({"stage": "registration", "status": hreg.get("status")})

    prev_lb = None
    for i, d in enumerate(weekdays(FIRST_FORWARD, nights)):
        row = one_night(d, 103 + i, "forward")
        lb = row["ledger_working_tree_bytes_after"]
        base_lb = prev_lb or night_rows[0]["ledger_working_tree_bytes_after"]
        row["ledger_bytes_delta"] = {k: lb[k] - base_lb.get(k, 0) for k in lb}
        prev_lb = lb
        night_rows.append(row)

    final = ST.Store(workdir=root / "final", remote=str(remote)).open()
    v = timed(pipe, "mirror_verify_final", lambda: final.verify_mirror(str(mirror), root / "mirror-check-final"))
    if v.get("status") != "equal":
        failures.append({"stage": "mirror_verify_final", "status": v.get("status")})
    chain_problems = ST.verify_chain(final.records)
    if chain_problems:
        failures.append({"stage": "verify_chain", "problems": len(chain_problems)})
    types = Counter(r["type"] for r in final.records)
    acc = attempt_counts(final.records)
    fwd_attempts = acc["started_by_kind"].get("forward_observation", 0)
    scr_attempts = acc["started_by_kind"].get("screening", 0)
    fwd = [r for r in night_rows if r["kind"] == "forward"]

    def mean(key):
        vals = [r[key] for r in fwd if r[key] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    stage_names = sorted({k for r in fwd for k in r["stages_wall_s"]})
    out = {
        "families": n_families,
        "hypotheses": len(hyps),
        "variants": len(variants),
        "unique_executable_configs": len(spec_hashes),
        "executables_compiled": len(exes),
        "predictions_registered": int(hreg.get("predictions_registered", 0)),
        "predictions_eligible": int(hreg.get("predictions_eligible", 0)),
        "pipeline_wall_cpu_s": pipe,
        "historical_screening": {
            "label": "exploration role, synthetic data 2015-01-02..2019-12-31; a filter, evidential weight 0",
            "families": n_families, "unique_executable_configs": len(spec_hashes),
            "attempts": scr_attempts, "attempt_records": screen_attempts,
            "wall_s": pipe["historical_screening"]["wall_s"],
            "attempts_per_s": round(scr_attempts / pipe["historical_screening"]["wall_s"], 2),
            "git_commits_private_ledger": screen_git, "ledger_working_tree_bytes": screen_bytes},
        "registration": {"git_commits_private_ledger": reg_git, "status": hreg.get("status")},
        "public_batch_bytes": public_bytes,
        "forward_confirmation": {
            "label": "forward observation attempts on synthetic captures dated after registration; no real data",
            "families": n_families, "unique_executable_configs": len(spec_hashes),
            "nights_run": len(fwd), "attempts_total": fwd_attempts,
            "nights": night_rows,
            "per_forward_night_mean": {
                "wall_s": mean("wall_s"), "cpu_s": mean("cpu_s"), "attempts": mean("attempts"),
                "attempts_per_s_forward_phase": mean("attempts_per_s_forward_phase"),
                "attempts_per_s_whole_night": mean("attempts_per_s_whole_night"),
                "git_commits_private_ledger": mean("git_commits_private_ledger"),
                "git_commits_mirror": mean("git_commits_mirror"),
                "bare_remote_bytes_delta": mean("bare_remote_bytes_delta"),
                "observations_new": mean("observations_new"),
                "stages_wall_s": {k: round(sum(r["stages_wall_s"].get(k, 0) for r in fwd) / len(fwd), 4)
                                  for k in stage_names} if fwd else {},
                "ledger_bytes_delta": {k: round(sum(r["ledger_bytes_delta"][k] for r in fwd) / len(fwd))
                                       for k in fwd[0]["ledger_bytes_delta"]} if fwd else {},
            },
            "per_family_per_forward_night": {
                "wall_s": round(mean("wall_s") / n_families, 5) if fwd else None,
                "git_commits_private_ledger": round(mean("git_commits_private_ledger") / n_families, 4) if fwd else None,
                "ledger_bytes_delta_excl_raw": round((sum(r["ledger_bytes_delta"]["working_tree_total"]
                                                          - r["ledger_bytes_delta"]["raw"] for r in fwd) / len(fwd))
                                                     / n_families) if fwd else None},
        },
        "attempts_all_kinds": {"note": "screening and forward attempts are different things; listed side by side, "
                                       "not a combined measure of evidence",
                               "screening": scr_attempts, "forward_observation": fwd_attempts,
                               "by_kind": acc["started_by_kind"], "terminals": acc["terminal_by_status"]},
        "final_ledger": {"records": len(final.records), "records_by_type": dict(types),
                         "working_tree_bytes": ledger_bytes(final.workdir), "bare_remote_bytes": nbytes(remote),
                         "bare_remote_bytes_after_gc": gc_bytes(remote, root / "gc-copy.git"),
                         "mirror_bare_bytes": nbytes(mirror), "git_commits_private_ledger": commits(remote),
                         "chain_ok": not chain_problems, "mirror_status": v.get("status")},
        "failures": failures,
    }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/manhattan_ops_bench.py")
    ap.add_argument("--families", type=int, nargs="+", default=[10])
    ap.add_argument("--nights", type=int, default=3, help="forward nights after registration")
    ap.add_argument("--max-hypotheses", type=int, default=2)
    ap.add_argument("--out", default=None, help="JSON path (default: a temporary directory)")
    ap.add_argument("--keep", action="store_true", help="keep the temporary ledgers")
    a = ap.parse_args(argv)
    out_path = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="manhattan-ops-bench-")) / "bench_ops.json"
    commit = head()
    base = Path(tempfile.mkdtemp(prefix="manhattan-ops-bench-work-"))
    res = {"schema": SCHEMA, "synthetic_only": True, "network": "none", "real_market_data": "none",
           "commit": commit, "machine": machine(),
           "started_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "nights_per_size": a.nights, "runs": []}
    try:
        for n in a.families:
            t0 = time.perf_counter()
            r = run_size(n, a.nights, base, commit, a.max_hypotheses)
            r["size_total_wall_s"] = round(time.perf_counter() - t0, 3)
            res["runs"].append(r)
            print(f"families={n} configs={r['unique_executable_configs']} "
                  f"fwd_attempts={r['forward_confirmation']['attempts_total']} "
                  f"night_mean_s={r['forward_confirmation']['per_forward_night_mean']['wall_s']} "
                  f"failures={len(r['failures'])} total_s={r['size_total_wall_s']}", file=sys.stderr)
    finally:
        if not a.keep:
            shutil.rmtree(base, ignore_errors=True)
    res["peak_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, sort_keys=True))
    print(str(out_path))
    return 0 if all(not r["failures"] for r in res["runs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
