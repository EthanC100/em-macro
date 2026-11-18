"""The staged funnel: scheduling, workers, attempt accounting, crash recovery, resume and reconciliation.

Execution model (docs/manhattan/hte/ARCHITECTURE.md section 4):

    stage 0   registry.submit / freeze                         (static validation, identity, dedup, PIT probe)
    pass A    stages 1 + 2 per chunk of the canonical order     (positions, Hölder screen, fingerprint, screening stats)
    selection deterministic function of every pass-A result   (aliases, dominance, policy) -> logged, hash-verified
    pass B    stage 3 per chunk of the selected list            (full simulation, bootstrap, streaming SPA maxima)
    stage 4   packages per family                               (package.py; descriptive, never confirmatory)
    stage 5   protected evaluation                              (protected.py; always refuses)

**Attempt protocol.** Before a chunk is computed the parent appends an fsynced ``attempt_started`` record (the
*intent*; its record hash is the attempt ID). The worker writes its result file atomically and returns its SHA-256;
only then does the parent append ``attempt_completed`` naming the file and hash. A crash at any point leaves either
an ``attempt_started`` without a terminal (marked ``attempt_interrupted`` on resume and still counted), or an orphan
file that no record names (never read). An exception in a worker that prevents a result file gives
``attempt_failed``; its candidates are retried by the next invocation with ``supersedes`` naming every failed or
interrupted attempt that covered them. Nothing is deleted.

Per-candidate computation failures inside a chunk (an exception or a non-finite statistic) do not fail the chunk:
the candidate gets status ``failed`` with a reason class, and stays in every denominator.

**Determinism.** The canonical order, the chunking of pending work, the per-candidate kernels and the bootstrap
seed are deterministic. Results (``results.bin`` and its hash, the run's ``result_root``) are bit-identical for any
input order, chunk size and worker count, and after any interruption and resume (tested). The attempt log records
what actually happened, so its *contents* differ between an interrupted and a clean run, by design.

**Repeated runs.** A run is identified by its registry root, data hash, code digest, policy hash and window. A second
invocation of a closed run reuses its results and logs ``run_reused``; with ``verify_rerun=True`` it recomputes every
chunk as a *verification* attempt and compares each candidate's results bit-for-bit with the results of record:
identical gives ``attempt_completed`` with ``verification: identical``; any difference logs ``nondeterminism`` and
raises. A verification never replaces the result of record. Changing the policy, code or data is a *new* run of the
same candidates, logged and counted by the packages.

Fault injection for tests: the environment variable ``HTE_FAULT`` (``kind:k``) makes the parent exit hard at a chosen
point: ``exit_after_start``, ``exit_after_file``, ``torn_completion``; ``worker_raise:k`` makes the k-th task raise.
Faults never change results; they exist so that crash and resume can be tested in a subprocess.
"""
from __future__ import annotations

import fcntl
import hashlib
import multiprocessing as mp
import os
import shutil
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import METHODOLOGY
from . import data as D
from . import features as F
from . import ids, kernels, store
from . import templates as TP
from .log import AttemptLog, recover_torn_tail
from .policy import Policy
from .registry import Registry

# status codes
S1 = {"not_run": 0, "pass": 1, "degenerate": 2, "dominated": 3, "failed": 9}
S2 = {"not_run": 0, "computed": 1, "failed": 9}
S3 = {"not_run": 0, "computed": 1, "alias": 2, "skipped_degenerate": 3, "skipped_dominated": 4,
      "skipped_not_selected": 5, "skipped_failed_upstream": 6, "failed": 9}
REASONS = {"none": 0, "execution_error": 1, "non_finite": 2}
STAGE3_SUBBATCH = 256         # memory bound only: results do not depend on it


class RunError(RuntimeError):
    pass


@dataclass
class Workspace:
    root: Path

    def __post_init__(self):
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        return self.root / "attempts.jsonl"

    def log(self) -> AttemptLog:
        if self.log_path.exists():
            recover_torn_tail(self.log_path)
        return AttemptLog(self.log_path)

    def registry(self, log: AttemptLog | None = None) -> Registry:
        return Registry(self.root / "registry", log or self.log())

    def run_dir(self, run_id: str) -> Path:
        return self.root / "runs" / run_id


# -- worker side ----------------------------------------------------------------------------------------------

_CTX: dict = {}


def _fault(kind: str) -> int | None:
    f = os.environ.get("HTE_FAULT", "")
    if f.startswith(kind + ":"):
        return int(f.split(":", 1)[1])
    return None


def _positions_window(cache, d, policy, fence):
    P = TP.positions(cache, d["template"], d["domain"], d["params"], d["sizing"])
    R = cache.panel.returns(d["domain"])
    return kernels.align(P, R, policy.warmup, fence)


def _task_A(task: dict) -> dict:
    """Stages 1 and 2 for canonical indices [lo, hi)."""
    ctx = _CTX
    if task.get("raise"):
        raise RuntimeError("injected worker failure")
    if task.get("die"):
        os._exit(78)                                 # injected: the worker process disappears
    view, policy, cache = ctx["view"], ctx["policy"], ctx["cache"]
    fence = cache.panel.fence
    idx = np.arange(task["lo"], task["hi"], dtype=np.int64)
    m = idx.size
    s1 = np.zeros(m, np.uint8)
    s2 = np.zeros(m, np.uint8)
    reason = np.zeros(m, np.uint8)
    stats = np.full((m, len(kernels.S2_COLS)), np.nan)
    fp = np.zeros((m, 32), np.uint8)
    stage2 = task["stage2"]
    errors: dict[str, int] = {}
    cache.events = []
    before = dict(cache.stats)
    for j, i in enumerate(idx):
        try:
            d = view.describe(int(i))
            with np.errstate(all="ignore"):
                Pw, Rw = _positions_window(cache, d, policy, fence)
            c, _ = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
            absR = cache.get(d["domain"], "absret")[policy.warmup: fence]
            with np.errstate(all="ignore"):              # a non-finite result is a recorded failure below
                r = kernels.screen(Pw, Rw, c, stage2=stage2, absR=absR)
            vals = [r.get(k, np.nan) for k in kernels.S2_COLS]
            if not np.all(np.isfinite([r["holder_bound"], r["lin_cost"]])) or \
                    (stage2 and not np.all(np.isfinite(vals))):
                s1[j] = S1["failed"]
                s2[j] = S2["failed"] if stage2 else 0
                reason[j] = REASONS["non_finite"]
                continue
            fp[j] = np.frombuffer(kernels.fingerprint(Pw, d["domain"], d["cost_model"]), np.uint8)
            stats[j] = vals
            s1[j] = S1["degenerate"] if r["degenerate"] else S1["dominated"] if r["dominated"] else S1["pass"]
            if stage2:
                s2[j] = S2["computed"]
        except Exception as e:                     # isolated: the candidate fails, the chunk does not
            s1[j] = S1["failed"]
            s2[j] = S2["failed"] if stage2 else 0
            reason[j] = REASONS["execution_error"]
            errors[type(e).__name__] = errors.get(type(e).__name__, 0) + 1
    arrays = {"idx": idx, "s1": s1, "s2": s2, "reason": reason, "stats2": stats, "fingerprint": fp}
    sha = store.write_arrays(Path(task["path"]), arrays)
    return {"sha256": sha, "errors": errors, "cache_events": list(cache.events), "cache_delta": _delta(cache, before),
            "counts": {"s1_" + k: int((s1 == v).sum()) for k, v in S1.items() if (s1 == v).any()}}


def _task_B(task: dict) -> dict:
    """Stage 3 for the canonical indices ``task['idx']``: positions ``[lo, hi)`` of the selected list, with
    ``lo`` a multiple of ``kernels.BOOT_GROUP`` (bootstrap groups are fixed by list position, never by chunk)."""
    ctx = _CTX
    if task.get("raise"):
        raise RuntimeError("injected worker failure")
    G = kernels.BOOT_GROUP
    if task["lo"] % G or (task["hi"] % G and task["hi"] != task["total"]):
        raise RunError("pass-B chunk is not aligned to bootstrap groups")
    view, policy, cache = ctx["view"], ctx["policy"], ctx["cache"]
    if "boot" not in ctx:
        ctx["boot"] = kernels.boot_counts(cache.panel.fence - policy.warmup, policy.bootstrap_B,
                                          policy.bootstrap_L, ctx["boot_seed"])
    C = ctx["boot"]
    fence = cache.panel.fence
    n = fence - policy.warmup
    idx = np.asarray(task["idx"], dtype=np.int64)
    m = idx.size
    status = np.zeros(m, np.uint8)
    reason = np.zeros(m, np.uint8)
    stats = np.full((m, len(kernels.S3_COLS)), np.nan)
    hashes = np.zeros((m, 32), np.uint8)
    fam = ctx["fam_of_spec"][view.spec_index[idx]]
    errors: dict[str, int] = {}
    cache.events = []
    before = dict(cache.stats)
    net = np.zeros((m, n))
    ok = np.zeros(m, bool)
    for s0 in range(0, m, STAGE3_SUBBATCH):
        rows = list(range(s0, min(m, s0 + STAGE3_SUBBATCH)))
        inputs = {}
        for j in rows:
            try:
                d = view.describe(int(idx[j]))
                Pw, Rw = _positions_window(cache, d, policy, fence)
                c, k = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
                inputs[j] = (Pw, Rw, c, k)
            except Exception as e:
                errors[type(e).__name__] = errors.get(type(e).__name__, 0) + 1
                status[j], reason[j] = S3["failed"], REASONS["execution_error"]
        js = sorted(inputs)
        if not js:
            continue
        try:
            out = _series(policy, [inputs[j] for j in js])
            done = list(zip(js, range(len(js))))
        except Exception:
            # isolate: one candidate at a time (rows are independent, so isolation cannot change a result)
            done, outs = [], []
            for j in js:
                try:
                    outs.append(_series(policy, [inputs[j]]))
                    done.append((j, len(outs) - 1))
                except Exception as e:
                    errors[type(e).__name__] = errors.get(type(e).__name__, 0) + 1
                    status[j], reason[j] = S3["failed"], REASONS["execution_error"]
            if outs:
                out = {k: np.concatenate([o[k] for o in outs]) for k in outs[0]}
        for j, r in done:
            st = out["stats"][r]
            if not np.all(np.isfinite(np.delete(st, kernels.S3_COLS.index("p_boot")))) or \
                    not np.all(np.isfinite(out["net"][r])):
                status[j], reason[j] = S3["failed"], REASONS["non_finite"]
                continue
            stats[j] = st
            net[j] = out["net"][r]
            hashes[j] = np.frombuffer(hashlib.sha256(np.ascontiguousarray(out["net"][r]).tobytes()).digest(),
                                      np.uint8)
            ok[j] = True
    # bootstrap and SPA partial maxima per fixed group of list positions
    partials: list[tuple] = []
    mcol, ocol, pcol = (kernels.S3_COLS.index(c) for c in ("mean", "omega", "p_boot"))
    for g0 in range(0, m, G):
        rows = [j for j in range(g0, min(m, g0 + G)) if ok[j]]
        if not rows:
            continue
        p, z = kernels.stage3_boot(C, net[rows], stats[rows, mcol], stats[rows, ocol])
        stats[rows, pcol] = p
        for j in rows:
            status[j] = S3["computed"]
        for gval, parts in kernels.spa_partial(z, stats[rows, mcol], stats[rows, ocol], n, fam[rows]).items():
            partials.append((gval, parts))
    fam_ids = sorted({g for g, _ in partials})
    B = C.shape[0]
    spaT = np.zeros(len(fam_ids))
    spa = np.zeros((len(fam_ids), 3, B))
    spa_n = np.zeros(len(fam_ids), np.int64)
    for r, g in enumerate(fam_ids):
        ps = [p for gg, p in partials if gg == g]
        spaT[r] = max(p[0] for p in ps)
        spa[r, 0] = np.maximum.reduce([p[1] for p in ps])
        spa[r, 1] = np.maximum.reduce([p[2] for p in ps])
        spa[r, 2] = np.maximum.reduce([p[3] for p in ps])
        spa_n[r] = sum(p[4] for p in ps)
    arrays = {"idx": idx, "s3": status, "reason": reason, "stats3": stats, "series_sha256": hashes,
              "spa_family": np.array(fam_ids, np.int64), "spa_T": spaT, "spa_max": spa, "spa_n": spa_n}
    sha = store.write_arrays(Path(task["path"]), arrays)
    return {"sha256": sha, "errors": errors, "cache_events": list(cache.events), "cache_delta": _delta(cache, before),
            "counts": {"s3_computed": int((status == S3["computed"]).sum()),
                       "s3_failed": int((status == S3["failed"]).sum())}}


def _delta(cache, before: dict) -> dict:
    return {k: cache.stats[k] - before.get(k, 0) for k in cache.stats}


def _series(policy, inputs: list) -> dict:
    Ps, Rs, cs, ks = zip(*inputs)
    with np.errstate(all="ignore"):
        o = kernels.stage3_series(list(Ps), list(Rs), list(cs), list(ks), policy)
        st = kernels.stage3_stats(o["net"], o["scale"], o["turnover"], policy)
    return {"net": o["net"], "stats": st}


def _init_worker(ctx):
    _CTX.clear()
    _CTX.update(ctx)


# -- parent side ----------------------------------------------------------------------------------------------

def run_identity(view, data_hash: str, policy: Policy, fence: int, code: dict, pass_a: str) -> dict:
    return {"registry_root": view.root, "data_hash": data_hash, "engine_sha256": code["engine_sha256"],
            "policy_hash": policy.hash(), "warmup": policy.warmup, "fence": fence, "methodology": METHODOLOGY,
            "pass_a": pass_a}


def boot_seed(view, data_hash: str, policy: Policy, fence: int) -> int:
    """The bootstrap seed is a function of registered identities only: no caller can choose it, so a bootstrap
    cannot be re-drawn until a p-value looks better without a new, logged run identity."""
    h = ids.full_hash({"registry_root": view.root, "data_hash": data_hash, "warmup": policy.warmup,
                       "fence": fence, "B": policy.bootstrap_B, "L": policy.bootstrap_L})
    return int(h[:16], 16)


class Runner:
    def __init__(self, ws: Workspace, panel, policy: Policy = Policy(), *, chunk_size: int = 256,
                 workers: int = 1, cache_enabled: bool = True, disk_cache: bool = True,
                 stages: tuple = (1, 2, 3, 4)):
        if chunk_size < 1 or workers < 1:
            raise ValueError("chunk_size and workers must be positive")
        if 5 in stages:
            from .protected import ProtectedEvaluationDisabled
            raise ProtectedEvaluationDisabled("stage 5 (protected evaluation) is disabled")
        self.ws = ws
        self.panel = panel
        self.policy = policy
        self.chunk_size = chunk_size
        self.workers = workers
        self.stages = tuple(sorted(set(stages)))
        self.data_hash = D.verify_synthetic(panel)
        self.log = ws.log()
        self.reg = ws.registry(self.log)
        self.view = self.reg.frozen()
        self.code = ids.code_identity()
        self.pass_a = "stage1_only" if self.stages == (1,) else "stages_1_2"
        self.ident = run_identity(self.view, self.data_hash, policy, panel.fence, self.code, self.pass_a)
        self.run_hash = ids.full_hash(self.ident)
        self.run_id = "HR-" + self.run_hash[:16]
        self.dir = ws.run_dir(self.run_id)
        self.cache = F.FeatureCache(panel, ws.root / "cache" / "features" if disk_cache else None,
                                    enabled=cache_enabled)
        fos, self.families = self.view.family_of_spec()
        self.fam_of_spec = fos
        self.timings: dict[str, float] = {}
        self.worker_cache: dict[str, float] = {}
        self._starts_this_invocation = 0
        self._files_this_invocation = 0
        self._completions_this_invocation = 0
        self._tasks_dispatched = 0

    # -- log helpers --------------------------------------------------------------------------------------
    def _recs(self, *types):
        return [r for r in self.log.of_type(*types) if r["payload"].get("run_id") == self.run_id]

    def _terminal_ids(self) -> set:
        return {r["payload"]["attempt_id"] for r in self._recs("attempt_completed", "attempt_failed",
                                                                 "attempt_interrupted")}

    def _start(self, payload: dict) -> str:
        rec = self.log.append("attempt_started", dict(payload, run_id=self.run_id))
        self._starts_this_invocation += 1
        k = _fault("exit_after_start")
        if k is not None and self._starts_this_invocation >= k:
            os._exit(77)
        return rec["hash"]

    def _complete(self, attempt_id: str, payload: dict) -> None:
        self._completions_this_invocation += 1
        k = _fault("torn_completion")
        if k is not None and self._completions_this_invocation >= k:
            import json
            line = json.dumps({"seq": len(self.log.records()) + 1, "type": "attempt_completed",
                               "payload": dict(payload, attempt_id=attempt_id)})
            with open(self.log.path, "ab") as f:
                f.write(line[: len(line) // 2].encode())
                f.flush()
                os.fsync(f.fileno())
            os._exit(77)
        self.log.append("attempt_completed", dict(payload, attempt_id=attempt_id, run_id=self.run_id))

    # -- the run ------------------------------------------------------------------------------------------
    def run(self, *, verify_rerun: bool = False) -> dict:
        """One invocation. Holds an exclusive lock on the workspace for its whole duration (released by the OS if
        the process dies), so two runners can never interleave records in one log."""
        lock = open(self.ws.root / ".lock", "a+")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise RunError("another runner holds this workspace") from None
        try:
            return self._run(verify_rerun=verify_rerun)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    BYTES_PER_CANDIDATE = 2048       # preflight: about 3x the measured ~0.6 KB per candidate (BENCHMARKS.md)

    def _run(self, *, verify_rerun: bool) -> dict:
        t0 = time.perf_counter()
        closed = self._recs("run_closed")
        invocation = len(self._recs("run_started")) + 1
        self.log.append("run_started", {"run_id": self.run_id, "identity": self.ident, "invocation": invocation,
                                        "code": self.code, "stages": list(self.stages),
                                        "chunk_size": self.chunk_size, "workers": self.workers,
                                        "policy": self.policy.as_dict(), "verify_rerun": verify_rerun})
        self._recover()
        if closed and not verify_rerun:
            p = closed[-1]["payload"]
            self.log.append("run_reused", {"run_id": self.run_id, "result_root": p["result_root"]})
            return dict(p, reused=True)
        need = len(self.view) * self.BYTES_PER_CANDIDATE
        free = shutil.disk_usage(self.ws.root).free
        if free < need:
            self.log.append("run_refused", {"run_id": self.run_id, "reason": "insufficient_disk",
                                            "need_bytes": need, "free_bytes": free})
            raise RunError(f"preflight: about {need} bytes needed, {free} free")
        self._warm()
        self.timings["warm_s"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        self._pass("A", verify=verify_rerun)
        self.timings["pass_A_s"] = time.perf_counter() - t1
        incomplete = self._uncovered("A")
        if incomplete:
            return self._stop(f"{incomplete} candidates have no completed stage 1-2 attempt")
        if self.stages == (1,) or 3 not in self.stages:
            return self._close(stage3=False)
        t2 = time.perf_counter()
        self._select()
        self.timings["selection_s"] = time.perf_counter() - t2
        t3 = time.perf_counter()
        self._pass("B", verify=verify_rerun)
        self.timings["pass_B_s"] = time.perf_counter() - t3
        incomplete = self._uncovered("B")
        if incomplete:
            return self._stop(f"{incomplete} selected candidates have no completed stage 3 attempt")
        return self._close(stage3=True)

    def _stop(self, why: str) -> dict:
        p = {"run_id": self.run_id, "reason": why}
        self.log.append("run_incomplete", p)
        return dict(p, closed=False)

    def _recover(self) -> None:
        done = self._terminal_ids()
        for r in self._recs("attempt_started"):
            if r["hash"] not in done:
                self.log.append("attempt_interrupted", {"run_id": self.run_id, "attempt_id": r["hash"],
                                                        "pass": r["payload"]["pass"], "reason": "interrupted"})

    def _warm(self) -> None:
        """Compute every feature the registered candidates need, once, in the parent (workers share them)."""
        if not self.cache.enabled:
            return
        need = set()
        import json
        for si in np.unique(self.view.spec_index):
            spec = self.reg.spec(int(si))
            dom = self.reg.records[spec["hypothesis"]]["domain"]
            keys = sorted(spec["grid"])
            import itertools
            for vals in itertools.product(*(spec["grid"][k] for k in keys)):
                for sz in spec["bindings"]["sizing"]:
                    for name, prm in TP.features_needed(spec["template"], dict(zip(keys, vals)), sz):
                        need.add((dom, name, json.dumps(prm, sort_keys=True)))
        for dom, name, prm in sorted(need):
            self.cache.get(dom, name, **json.loads(prm))
        self._log_cache_events(self.cache.events)
        self.cache.events = []

    def _log_cache_events(self, events) -> None:
        for e in events:
            self.log.append("cache_corrupt", dict(e, run_id=self.run_id))

    # coverage ---------------------------------------------------------------------------------------------
    def _completed(self, pas: str) -> list[dict]:
        return [r["payload"] for r in self._recs("attempt_completed")
                if r["payload"]["pass"] == pas and not r["payload"].get("verification")]

    def _work_items(self, pas: str) -> np.ndarray:
        if pas == "A":
            return np.arange(len(self.view), dtype=np.int64)
        return self._selection()["selected"]

    def _covered(self, pas: str) -> np.ndarray:
        items = self._work_items(pas)
        cov = np.zeros(items.size, np.int64)
        for p in self._completed(pas):
            cov[p["lo"]: p["hi"]] += 1
        if (cov > 1).any():
            raise RunError(f"pass {pas}: a candidate is covered by more than one completed attempt")
        return cov.astype(bool)

    def _uncovered(self, pas: str) -> int:
        return int((~self._covered(pas)).sum())

    def _pass(self, pas: str, verify: bool) -> None:
        cov = self._covered(pas)
        if verify and cov.all():
            ranges = [(p["lo"], p["hi"]) for p in self._completed(pas)]
            ranges.sort()
            self._execute(pas, ranges, verification=True)
            return
        pending = np.flatnonzero(~cov)
        ranges = []
        cs = self.chunk_size
        if pas == "B":                                # pass-B chunks are whole bootstrap groups
            G = kernels.BOOT_GROUP
            cs = -(-cs // G) * G
        if pending.size:
            # contiguous runs of pending positions, cut into chunks
            breaks = np.flatnonzero(np.diff(pending) != 1) + 1
            for run in np.split(pending, breaks):
                for s in range(0, run.size, cs):
                    ranges.append((int(run[s]), int(run[min(s + cs, run.size) - 1]) + 1))
        self._execute(pas, ranges, verification=False)

    def _prior_failed(self, pas: str) -> list[tuple]:
        fails = {r["payload"]["attempt_id"] for r in self._recs("attempt_failed", "attempt_interrupted")}
        superseded = set()
        for r in self._recs("attempt_started"):
            superseded.update(r["payload"].get("supersedes", []))
        out = []
        for r in self._recs("attempt_started"):
            p = r["payload"]
            if p["pass"] == pas and r["hash"] in fails and r["hash"] not in superseded:
                out.append((p["lo"], p["hi"], r["hash"]))
        return out

    def _execute(self, pas: str, ranges: list, verification: bool) -> None:
        if not ranges:
            return
        rdir = self.dir / pas
        rdir.mkdir(parents=True, exist_ok=True)
        items = self._work_items(pas)
        sel_sha = self._selection_record()["sha256"] if pas == "B" else None
        prior = self._prior_failed(pas)
        inflight = max(1, 2 * self.workers)
        ctx = {"view": self.view, "policy": self.policy, "cache": self.cache, "fam_of_spec": self.fam_of_spec,
               "boot_seed": boot_seed(self.view, self.data_hash, self.policy, self.panel.fence)}
        pool = None
        if self.workers > 1:
            # ProcessPoolExecutor, not multiprocessing.Pool: when a worker dies (killed, out of memory) Pool loses
            # the task and waits for ever, while the executor raises BrokenProcessPool, which is logged below
            pool = ProcessPoolExecutor(self.workers, mp_context=mp.get_context("fork"), initializer=_init_worker,
                                       initargs=(ctx,))
        else:
            _init_worker(ctx)
        broken = False
        raise_at = _fault("worker_raise")
        die_at = _fault("worker_exit")
        fn = _task_A if pas == "A" else _task_B

        def dispatch(lo, hi):
            sup = [h for (plo, phi, h) in prior if plo < hi and lo < phi]
            payload = {"pass": pas, "lo": lo, "hi": hi, "n": hi - lo, "policy_hash": self.policy.hash(),
                       "data_hash": self.data_hash, "engine_sha256": self.code["engine_sha256"],
                       "registry_root": self.view.root, "verification": verification}
            if sup:
                payload["supersedes"] = sup
            if sel_sha:
                payload["selection_sha256"] = sel_sha
            aid = self._start(payload)                 # the intent is durable before the work is dispatched
            fname = f"{'verify-' if verification else ''}{aid[:20]}.bin"
            t = {"path": str(rdir / fname), "lo": lo, "hi": hi, "stage2": self.pass_a == "stages_1_2"}
            if pas == "B":
                t["idx"] = items[lo:hi]
                t["total"] = int(items.size)
            self._tasks_dispatched += 1
            if raise_at is not None and self._tasks_dispatched == raise_at:
                t["raise"] = True
            if die_at is not None and self._tasks_dispatched == die_at:
                t["die"] = True
            fut = None
            if pool is not None:
                try:
                    fut = pool.submit(fn, t)
                except BrokenProcessPool as e:      # the pool broke after the intent was written
                    fut = e
            return aid, fname, t, fut

        def finish(aid, fname, t, fut):
            nonlocal broken
            try:
                if isinstance(fut, Exception):
                    raise fut
                out = fut.result() if fut is not None else fn(t)
            except Exception as e:
                out = e
            if isinstance(out, Exception):
                lost = isinstance(out, BrokenProcessPool)
                broken = broken or lost
                self.log.append("attempt_failed", {"run_id": self.run_id, "attempt_id": aid, "pass": pas,
                                                   "reason": "worker_lost" if lost else "execution_error",
                                                   "error_class": type(out).__name__})
                return
            self._files_this_invocation += 1
            k = _fault("exit_after_file")
            if k is not None and self._files_this_invocation >= k:
                os._exit(77)
            self._log_cache_events(out["cache_events"])
            if pool is not None:                       # in-process tasks already count in self.cache.stats
                for k, v in out.get("cache_delta", {}).items():
                    self.worker_cache[k] = self.worker_cache.get(k, 0) + v
            payload = {"pass": pas, "lo": t["lo"], "hi": t["hi"], "file": f"{pas}/{fname}",
                       "sha256": out["sha256"], "counts": out["counts"], "errors": out["errors"]}
            if verification:
                payload["verification"] = self._verify(pas, t, out)
            self._complete(aid, payload)

        # sliding window: at most `inflight` chunks are started and unfinished; completions are logged in
        # dispatch order (deterministic log for a given chunking), while workers always have queued work
        from collections import deque
        window: deque = deque()
        try:
            for lo, hi in ranges:
                if len(window) >= inflight:
                    finish(*window.popleft())
                if broken:                             # a lost worker: stop dispatching; resume retries the rest
                    break
                window.append(dispatch(lo, hi))
            while window:
                finish(*window.popleft())
        finally:
            if pool is not None:
                pool.shutdown(wait=True, cancel_futures=True)

    def _verify(self, pas: str, t: dict, out: dict) -> str:
        new = store.read_arrays(Path(t["path"]), out["sha256"])
        old = self._load_pass(pas, restrict=(t["lo"], t["hi"]))
        for k in new:
            if k.startswith("spa_"):
                continue
            if not np.array_equal(new[k], old[k], equal_nan=True):
                self.log.append("nondeterminism", {"run_id": self.run_id, "pass": pas, "lo": t["lo"],
                                                   "hi": t["hi"], "field": k})
                raise RunError(f"nondeterminism in pass {pas} [{t['lo']}, {t['hi']}): field {k}")
        return "identical"

    # loading results of record ----------------------------------------------------------------------------
    def _load_pass(self, pas: str, restrict: tuple | None = None) -> dict:
        parts = []
        for p in sorted(self._completed(pas), key=lambda p: p["lo"]):
            if restrict and not (p["lo"] < restrict[1] and restrict[0] < p["hi"]):
                continue
            a = store.read_arrays(self.dir / p["file"], p["sha256"])
            a["_lo"] = p["lo"]
            parts.append(a)
        if not parts:
            raise RunError(f"no results for pass {pas}")
        keys = [k for k in parts[0] if not k.startswith("spa_") and k != "_lo"]
        out = {k: np.concatenate([a[k] for a in parts]) for k in keys}
        if restrict:
            pos = np.concatenate([np.arange(a["_lo"], a["_lo"] + a[keys[0]].shape[0]) for a in parts])
            sel = (pos >= restrict[0]) & (pos < restrict[1])
            out = {k: v[sel] for k, v in out.items()}
        if pas == "B":
            out["_spa"] = [(int(f), float(T), m[0], m[1], m[2], int(c)) for a in parts
                           for f, T, m, c in zip(a["spa_family"], a["spa_T"], a["spa_max"], a["spa_n"])]
        return out

    # selection --------------------------------------------------------------------------------------------
    def _selection_record(self) -> dict:
        recs = self._recs("selection")
        if not recs:
            raise RunError("no selection record")
        return recs[-1]["payload"]

    def _selection(self) -> dict:
        p = self._selection_record()
        return store.read_arrays(self.dir / p["file"], p["sha256"])

    def compute_selection(self) -> dict:
        """The selection as a pure function of the pass-A results of record and the policy."""
        A = self._load_pass("A")
        N = len(self.view)
        if not np.array_equal(A["idx"], np.arange(N)):
            raise RunError("pass A results do not cover the canonical order exactly once")
        s1 = A["s1"]
        alias_of = np.full(N, -1, np.int64)
        live = (s1 == S1["pass"]) | (s1 == S1["dominated"])
        if self.policy.dedup_behavioural and live.any():
            li = np.flatnonzero(live)
            fp = A["fingerprint"][li]
            _, first, inv = np.unique(fp, axis=0, return_index=True, return_inverse=True)
            rep = li[first][inv.ravel()]
            alias_of[li] = np.where(rep != li, rep, -1)
        planned = np.zeros(N, np.uint8)
        planned[s1 == S1["degenerate"]] = S3["skipped_degenerate"]
        planned[s1 == S1["failed"]] = S3["skipped_failed_upstream"]
        rep_mask = live & (alias_of < 0)
        dom_skip = rep_mask & (s1 == S1["dominated"]) & self.policy.skip_stage3_if_dominated
        planned[dom_skip] = S3["skipped_dominated"]
        eligible = rep_mask & ~dom_skip
        if self.policy.stage3_selection == "top_k_per_spec":
            t = A["stats2"][:, kernels.S2_COLS.index("t_stat")]
            keep = np.zeros(N, bool)
            for si in np.unique(self.view.spec_index):
                cand = np.flatnonzero(eligible & (self.view.spec_index == si))
                order = np.lexsort((cand, -t[cand]))         # t descending, then canonical index
                keep[cand[order[: self.policy.top_k]]] = True
            planned[eligible & ~keep] = S3["skipped_not_selected"]
            eligible &= keep
        planned[eligible] = S3["computed"]
        al = alias_of >= 0
        planned[al] = np.where(planned[alias_of[al]] == S3["computed"], S3["alias"], planned[alias_of[al]])
        # an alias of a dominated representative carries the representative's planned status
        return {"selected": np.flatnonzero(eligible).astype(np.int64), "alias_of": alias_of, "planned": planned}

    def _select(self) -> None:
        sel = self.compute_selection()
        existing = self._recs("selection")
        if existing:
            old = self._selection()
            for k in sel:
                if not np.array_equal(sel[k], old[k]):
                    self.log.append("nondeterminism", {"run_id": self.run_id, "pass": "selection", "field": k})
                    raise RunError("selection does not reproduce from the pass-A results of record")
            return
        fname = "selection.bin"
        sha = store.write_arrays(self.dir / fname, sel)
        inputs = [{"attempt_lo": p["lo"], "sha256": p["sha256"]} for p in
                  sorted(self._completed("A"), key=lambda p: p["lo"])]
        counts = {k: int((sel["planned"] == v).sum()) for k, v in S3.items() if (sel["planned"] == v).any()}
        self.log.append("selection", {"run_id": self.run_id, "file": fname, "sha256": sha,
                                      "policy_hash": self.policy.hash(),
                                      "performance_gate": self.policy.performance_gate,
                                      "inputs_root": ids.merkle_root([i["sha256"] for i in inputs]),
                                      "n_inputs": len(inputs), "counts": counts})

    # closing ----------------------------------------------------------------------------------------------
    def results_table(self, stage3: bool) -> dict:
        A = self._load_pass("A")
        N = len(self.view)
        table = {"s1": A["s1"], "s2": A["s2"], "reason1": A["reason"], "stats2": A["stats2"],
                 "fingerprint": A["fingerprint"]}
        if stage3:
            sel = self._selection()
            B = self._load_pass("B")
            s3 = sel["planned"].copy()
            stats3 = np.full((N, len(kernels.S3_COLS)), np.nan)
            h3 = np.zeros((N, 32), np.uint8)
            r3 = np.zeros(N, np.uint8)
            s3[B["idx"]] = B["s3"]
            stats3[B["idx"]] = B["stats3"]
            h3[B["idx"]] = B["series_sha256"]
            r3[B["idx"]] = B["reason"]
            al = sel["alias_of"] >= 0
            src = sel["alias_of"][al]
            copy = s3[src] == S3["computed"]
            ai = np.flatnonzero(al)[copy]
            stats3[ai] = stats3[sel["alias_of"][ai]]
            h3[ai] = h3[sel["alias_of"][ai]]
            # an alias whose representative failed in stage 3 fails with it
            fi = np.flatnonzero(al)[s3[src] == S3["failed"]]
            s3[fi] = S3["skipped_failed_upstream"]
            table.update({"s3": s3, "reason3": r3, "stats3": stats3, "series_sha256": h3,
                          "alias_of": sel["alias_of"]})
        return table

    def _close(self, stage3: bool) -> dict:
        from . import package as PK
        t0 = time.perf_counter()
        table = self.results_table(stage3)
        raw = store.arrays_to_bytes(table)
        result_root = ids.sha256_bytes(raw)
        sha = store.atomic_write_bytes(self.dir / "results.bin", raw)
        spa = None
        if stage3:
            spa = self._load_pass("B")["_spa"]
        pk = {}
        if 4 in self.stages:
            pk = PK.build(self, table, spa)
        self.timings["stage4_s"] = time.perf_counter() - t0
        rec = reconcile(self.ws, self.run_id)
        payload = {"run_id": self.run_id, "results_file": "results.bin", "results_sha256": sha,
                   "result_root": result_root, "packages": pk.get("files", {}),
                   "reconciliation": {k: rec[k] for k in ("registered", "attempts", "violations")},
                   "evidence_class": "synthetic_screening_descriptive", "confirmatory": False}
        self.log.append("run_closed", payload)
        cache = {k: self.cache.stats[k] + self.worker_cache.get(k, 0) for k in self.cache.stats}
        return dict(payload, reused=False, timings=self.timings, cache=cache)


# -- reconciliation (reads persisted records only) ----------------------------------------------------------

def reconcile(ws: Workspace, run_id: str, anchor: dict | None = None) -> dict:
    """Audit one run from the log and the files it names. Every registered candidate must have exactly one
    completed (non-verification) attempt per executed pass; every attempt must have exactly one terminal.
    Returns counts and violations; never certifies access completeness (``access_reconciled`` is False)."""
    from .log import verify
    verify(ws.log_path, anchor)
    log = AttemptLog(ws.log_path)
    recs = [r for r in log.records() if r["payload"].get("run_id") == run_id]
    starts = {r["hash"]: r["payload"] for r in recs if r["type"] == "attempt_started"}
    terms: dict[str, list] = {}
    for r in recs:
        if r["type"] in ("attempt_completed", "attempt_failed", "attempt_interrupted"):
            terms.setdefault(r["payload"]["attempt_id"], []).append(r["type"])
    violations = []
    for aid, ts in terms.items():
        if aid not in starts:
            violations.append({"code": "terminal_without_start", "attempt": aid[:16]})
        if len(ts) > 1:
            violations.append({"code": "multiple_terminals", "attempt": aid[:16]})
    unfinished = [a for a in starts if a not in terms]
    by = {"completed": 0, "failed": 0, "interrupted": 0, "unfinished": len(unfinished), "verification": 0}
    for aid, ts in terms.items():
        t = ts[0]
        if t == "attempt_completed":
            if starts.get(aid, {}).get("verification"):
                by["verification"] += 1
            else:
                by["completed"] += 1
        elif t == "attempt_failed":
            by["failed"] += 1
        else:
            by["interrupted"] += 1
    reg = Registry(ws.root / "registry", log)
    view = reg.frozen()
    N = len(view)
    started = [r for r in recs if r["type"] == "run_started"]
    passes = {}
    for pas in ("A", "B"):
        comp = [r["payload"] for r in recs if r["type"] == "attempt_completed" and r["payload"]["pass"] == pas
                and not starts.get(r["payload"]["attempt_id"], {}).get("verification")]
        if not comp:
            continue
        if pas == "A":
            size = N
        else:
            sel = [r["payload"] for r in recs if r["type"] == "selection"]
            size = int(store.read_arrays(ws.run_dir(run_id) / sel[-1]["file"], sel[-1]["sha256"])["selected"].size)
        cov = np.zeros(size, np.int64)
        for p in comp:
            store.read_verified(ws.run_dir(run_id) / p["file"], p["sha256"])
            cov[p["lo"]:p["hi"]] += 1
        if (cov > 1).any():
            violations.append({"code": "double_coverage", "pass": pas, "n": int((cov > 1).sum())})
        passes[pas] = {"items": size, "covered": int((cov == 1).sum()), "uncovered": int((cov == 0).sum())}
    # per-candidate attempt counts (every attempt that covered the candidate, any terminal or none)
    attempts_per = np.zeros(N, np.int64)
    for aid, p in starts.items():
        if p["pass"] == "A":
            attempts_per[p["lo"]:p["hi"]] += 1
    closed = [r for r in recs if r["type"] == "run_closed"]
    final = None
    if closed or (ws.run_dir(run_id) / "results.bin").exists():
        try:
            t = store.bytes_to_arrays((ws.run_dir(run_id) / "results.bin").read_bytes())
            final = {"s1": {k: int((t["s1"] == v).sum()) for k, v in S1.items()}}
            if "s3" in t:
                final["s3"] = {k: int((t["s3"] == v).sum()) for k, v in S3.items()}
            for st, codes in final.items():
                if sum(codes.values()) != N:
                    violations.append({"code": "status_total_mismatch", "stage": st})
            if final["s1"]["not_run"]:
                violations.append({"code": "candidate_without_stage1_status", "n": final["s1"]["not_run"]})
            if "s3" in final and final["s3"]["not_run"]:
                violations.append({"code": "candidate_without_stage3_status", "n": final["s3"]["not_run"]})
        except Exception as e:                           # a damaged results file is a violation, not a crash
            violations.append({"code": "results_unreadable", "error_class": type(e).__name__})
    return {"run_id": run_id, "registered": {"candidates": N, **view.payload["counts"]},
            "invocations": len(started), "attempts": {"started": len(starts), **by},
            "attempts_per_candidate_max": int(attempts_per.max()) if N else 0,
            "passes": passes, "final_status": final, "violations": violations,
            "access_reconciled": False, "independent_statistical_tests": None}


def history(ws: Workspace, run_id: str, canonical_index: int) -> list[dict]:
    """Every attempt that covered one candidate in one run, with its terminal (or ``unfinished``)."""
    log = AttemptLog(ws.log_path)
    recs = [r for r in log.records() if r["payload"].get("run_id") == run_id]
    term = {r["payload"]["attempt_id"]: r["type"] for r in recs
            if r["type"] in ("attempt_completed", "attempt_failed", "attempt_interrupted")}
    sel = None
    out = []
    for r in recs:
        if r["type"] != "attempt_started":
            continue
        p = r["payload"]
        if p["pass"] == "A":
            hit = p["lo"] <= canonical_index < p["hi"]
        else:
            if sel is None:
                s = [x["payload"] for x in recs if x["type"] == "selection"][-1]
                sel = store.read_arrays(ws.run_dir(run_id) / s["file"], s["sha256"])["selected"]
            hit = canonical_index in set(sel[p["lo"]:p["hi"]].tolist())
        if hit:
            out.append({"attempt_id": r["hash"], "pass": p["pass"], "seq": r["seq"],
                        "terminal": term.get(r["hash"], "unfinished"), "verification": p.get("verification"),
                        "supersedes": p.get("supersedes", [])})
    return out
