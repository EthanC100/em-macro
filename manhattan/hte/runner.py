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
from .log import AttemptLog, LogError, locked, recover_torn_tail
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
        """Read access. A torn final line is tolerated when reading; it is quarantined only by a writer holding
        the workspace lock (``Runner.run``, ``Registry.submit``/``freeze``)."""
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


def signed_positions(cache, d) -> np.ndarray:
    """A template's positions in the direction its family predicts (S10 F5). Templates are written for the "+"
    direction; a "-" family holds exactly the negated positions (negation is exact in floating point, so every
    statistic of a "-" candidate is the bit-exact mirror of its "+" counterpart where the statistic is odd in the
    positions). The only place positions enter an evaluation."""
    P = TP.positions(cache, d["template"], d["domain"], d["params"], d["sizing"])
    sign = d.get("sign")
    if sign == "-":
        P = -P + 0.0                                  # + 0.0: no negative zeros in fingerprints
    elif sign != "+":
        raise RunError(f"family sign {sign!r} is not '+' or '-'")
    return P


def _positions_window(cache, d, policy, fence):
    P = signed_positions(cache, d)
    R = cache.panel.returns(d["domain"])
    return kernels.align(P, R, policy.warmup, fence)


def _task_A(task: dict) -> dict:
    """Stages 1 and 2 for canonical indices [lo, hi)."""
    ctx = _CTX
    if task.get("raise"):
        raise RuntimeError("injected worker failure")
    if task.get("die"):
        os._exit(78)                                 # injected: the worker process disappears
    if task.get("hang"):
        time.sleep(3600)                             # injected: a slow chunk (tests kill the parent meanwhile)
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
    """Stage 3 for the canonical indices ``task['idx']``: positions ``[lo, hi)`` of the pass-B order (family-major,
    ``selection.b_order``). ``task['groups']`` are the offsets of the bootstrap groups inside the task: whole
    groups of at most ``kernels.BOOT_GROUP`` candidates of one family, fixed by the selection, never by chunk."""
    ctx = _CTX
    if task.get("raise"):
        raise RuntimeError("injected worker failure")
    groups = list(task["groups"])
    if not groups or groups[0] != 0:
        raise RunError("pass-B chunk does not start at a bootstrap group")
    view, policy, cache = ctx["view"], ctx["policy"], ctx["cache"]
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
    # bootstrap and SPA partial maxima per fixed group (one family per group, that family's own draws)
    partials: list[tuple] = []
    mcol, ocol, pcol = (kernels.S3_COLS.index(c) for c in ("mean", "omega", "p_boot"))
    bounds = groups + [m]
    for g0, g1 in zip(bounds[:-1], bounds[1:]):
        fams = set(fam[g0:g1].tolist())
        if len(fams) != 1:
            raise RunError("a bootstrap group spans more than one family")
        rows = [j for j in range(g0, g1) if ok[j]]
        if not rows:
            continue
        C = _family_counts(ctx, ctx["families"][int(fam[g0])])
        p, z = kernels.stage3_boot(C, net[rows], stats[rows, mcol], stats[rows, ocol])
        stats[rows, pcol] = p
        for j in rows:
            status[j] = S3["computed"]
        for gval, parts in kernels.spa_partial(z, stats[rows, mcol], stats[rows, ocol], n, fam[rows]).items():
            partials.append((gval, parts))
    fam_ids = sorted({g for g, _ in partials})
    B = policy.bootstrap_B
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


def die_with_parent() -> None:
    """Make a forked worker exit when its parent dies (S10 F2): Linux ``PR_SET_PDEATHSIG`` where available, and a
    watchdog thread that exits as soon as the parent process id changes (re-parenting) as a portable fallback."""
    ppid = os.getppid()
    try:
        import ctypes
        import signal
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGKILL)                  # PR_SET_PDEATHSIG = 1
    except Exception:
        pass
    if os.getppid() != ppid:
        os._exit(1)

    def watch():
        while True:
            time.sleep(0.5)
            if os.getppid() != ppid:
                os._exit(1)

    import threading
    threading.Thread(target=watch, daemon=True, name="hte-parent-watchdog").start()


def _init_worker(ctx):
    _CTX.clear()
    _CTX.update(ctx)


def _init_pool_worker(ctx):
    """Initializer of forked pool workers only (never the in-process path, which must not watch its parent)."""
    die_with_parent()
    _init_worker(ctx)


# -- parent side ----------------------------------------------------------------------------------------------

def run_identity(view, data_hash: str, policy: Policy, fence: int, code: dict, pass_a: str,
                 stages: tuple = (1, 2, 3, 4)) -> dict:
    return {"registry_root": view.root, "data_hash": data_hash, "engine_sha256": code["engine_sha256"],
            "policy_hash": policy.hash(), "warmup": policy.warmup, "fence": fence, "methodology": METHODOLOGY,
            "pass_a": pass_a, "stages": list(stages)}


def boot_seed(family_hash: str, data_hash: str, policy: Policy, fence: int) -> int:
    """A family's bootstrap seed (S10 F6): a function of the family's immutable identity and of the evaluation
    (data, window, B, L, methodology) only. No caller can choose it, and registering or freezing *other* specs
    cannot re-draw a family's bootstrap: re-drawing needs a different family identity, which is a new, flagged
    family (semantic duplicates, post-look by economics)."""
    h = ids.full_hash({"family": family_hash, "data_hash": data_hash, "warmup": policy.warmup, "fence": fence,
                       "B": policy.bootstrap_B, "L": policy.bootstrap_L, "methodology": METHODOLOGY})
    return int(h[:16], 16)


BOOT_CACHE_MAX = 4                    # count matrices (about 18 MB each at 2,220 days) kept per worker


def _family_counts(ctx: dict, family_hash: str) -> np.ndarray:
    cache = ctx.setdefault("boot", {})
    if family_hash not in cache:
        if len(cache) >= BOOT_CACHE_MAX:
            cache.pop(next(iter(cache)))
        pol, panel = ctx["policy"], ctx["cache"].panel
        cache[family_hash] = kernels.boot_counts(panel.fence - pol.warmup, pol.bootstrap_B, pol.bootstrap_L,
                                                 boot_seed(family_hash, panel.data_hash, pol, panel.fence))
    return cache[family_hash]


class Runner:
    def __init__(self, ws: Workspace, panel, policy: Policy = Policy(), *, chunk_size: int = 256,
                 workers: int = 1, cache_enabled: bool = True, disk_cache: bool = True,
                 stages: tuple = (1, 2, 3, 4), registry_root: str | None = None):
        """``registry_root`` binds the run to one frozen registry version (default: the latest). Pass the root
        of an interrupted run to resume it after a newer freeze."""
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
        self.view = self.reg.frozen(root=registry_root) if registry_root else self.reg.frozen()
        self.code = ids.code_identity()
        self.pass_a = "stage1_only" if self.stages == (1,) else "stages_1_2"
        self.ident = run_identity(self.view, self.data_hash, policy, panel.fence, self.code, self.pass_a,
                                  self.stages)
        self.run_hash = ids.full_hash(self.ident)
        self.run_id = "HR-" + self.run_hash[:16]
        self.dir = ws.run_dir(self.run_id)
        self.cache = F.FeatureCache(panel, ws.root / "cache" / "features" if disk_cache else None,
                                    enabled=cache_enabled)
        fos, self.families = self.view.family_of_spec()
        self.fam_of_spec = fos
        self.timings: dict[str, float] = {}
        self._phase = "init"
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
        try:
            with locked(self.log.path):
                recover_torn_tail(self.log.path)
                self.log.refresh()                      # records written by any other writer since __init__
                self._snapshot()
                self._phase = "start"
                try:
                    return self._run(verify_rerun=verify_rerun)
                except BaseException as e:
                    # every failed invocation is recorded (S10 F4); an injected hard exit never reaches here
                    try:
                        self.log.append("run_failed", {"run_id": self.run_id, "phase": self._phase,
                                                       "error_class": type(e).__name__})
                    except Exception:
                        pass
                    raise
        except LogError as e:
            if "another writer" in str(e):
                raise RunError("another runner holds this workspace") from None
            raise

    BYTES_PER_CANDIDATE = 2048       # preflight: about 3x the measured ~0.6 KB per candidate (BENCHMARKS.md)

    def _snapshot(self) -> None:
        """Consistent registry snapshot (S10 F4): under the workspace lock, reload the registry from the log so
        that the registry, the log and the run agree for the whole invocation (the lock keeps other writers out
        until it ends). The run stays bound to its frozen root: an append-only registry cannot change it, and a
        frozen version that no longer reproduces is refused."""
        self.reg.records, self.reg.spec_hashes, self.reg.segments = {}, [], []
        self.reg._load()
        view = self.reg.frozen(root=self.view.root)
        if not (np.array_equal(view.cand, self.view.cand) and np.array_equal(view.spec_index, self.view.spec_index)):
            raise RunError("the run's frozen registry version changed on disk")
        self.view = view
        fos, fams = self.view.family_of_spec()
        if fams != self.families:
            raise RunError("the run's families changed on disk")
        self.fam_of_spec = fos

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
        self._phase = "warm"
        self._warm()
        self.timings["warm_s"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        self._phase = "pass_A"
        self._pass("A", verify=verify_rerun)
        self.timings["pass_A_s"] = time.perf_counter() - t1
        incomplete = self._uncovered("A")
        if incomplete:
            return self._stop(f"{incomplete} candidates have no completed stage 1-2 attempt")
        if self.stages == (1,) or 3 not in self.stages:
            if closed and verify_rerun:
                return self._verified(closed[-1]["payload"])
            return self._close(stage3=False)
        t2 = time.perf_counter()
        self._phase = "selection"
        self._select()
        self.timings["selection_s"] = time.perf_counter() - t2
        t3 = time.perf_counter()
        self._phase = "pass_B"
        self._pass("B", verify=verify_rerun)
        self.timings["pass_B_s"] = time.perf_counter() - t3
        incomplete = self._uncovered("B")
        if incomplete:
            return self._stop(f"{incomplete} selected candidates have no completed stage 3 attempt")
        if closed and verify_rerun:
            return self._verified(closed[-1]["payload"])
        return self._close(stage3=True)

    def _verified(self, closed: dict) -> dict:
        """End of a verification invocation: every chunk was recomputed and compared field by field; the result
        table rebuilt from the results of record must also reproduce the closed ``result_root``. Nothing of
        record (results, packages) is rewritten."""
        mine = [r for r in self.log.records() if r["payload"].get("run_id") == self.run_id]
        last = max(r["seq"] for r in mine if r["type"] == "run_started")
        ver = [r for r in mine if r["seq"] > last and r["type"] in ("attempt_completed", "attempt_failed")]
        bad = [r for r in ver if r["type"] == "attempt_failed" or r["payload"].get("verification") != "identical"]
        stage3 = 3 in self.stages
        root = ids.sha256_bytes(store.arrays_to_bytes(self.results_table(stage3)))
        if bad or root != closed["result_root"]:
            self.log.append("verification_failed", {"run_id": self.run_id, "failed_attempts": len(bad),
                                                    "result_root_reproduced": root == closed["result_root"]})
            raise RunError("verification did not complete or did not reproduce the result of record")
        self.log.append("run_verified", {"run_id": self.run_id, "result_root": root, "attempts": len(ver)})
        return dict(closed, reused=False, verified=True, timings=self.timings)

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
        return self._selection()["b_order"]

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
            self._execute(pas, self._group_ranges(cov), verification=False)
            return
        if pending.size:
            # contiguous runs of pending positions, cut into chunks
            breaks = np.flatnonzero(np.diff(pending) != 1) + 1
            for run in np.split(pending, breaks):
                for s in range(0, run.size, cs):
                    ranges.append((int(run[s]), int(run[min(s + cs, run.size) - 1]) + 1))
        self._execute(pas, ranges, verification=False)

    def _group_ranges(self, cov: np.ndarray) -> list[tuple]:
        """Pass-B chunks: consecutive uncovered bootstrap groups packed up to ``chunk_size`` (at least one group)."""
        starts = np.flatnonzero(self._selection()["b_group_start"]).tolist() + [cov.size]
        ranges, cur = [], None
        for g0, g1 in zip(starts[:-1], starts[1:]):
            done = cov[g0:g1]
            if done.any() and not done.all():
                raise RunError("a bootstrap group is partly covered")
            if done.all():
                if cur:
                    ranges.append(cur)
                cur = None
                continue
            if cur and g1 - cur[0] <= self.chunk_size:
                cur = (cur[0], g1)
            else:
                if cur:
                    ranges.append(cur)
                cur = (g0, g1)
        if cur:
            ranges.append(cur)
        return ranges

    def _prior_failed(self, pas: str) -> list[tuple]:
        """Every failed or interrupted attempt of this pass: a new attempt names each one whose range it overlaps,
        whether or not an earlier retry already named it (a retry can itself be interrupted part-way)."""
        fails = {r["payload"]["attempt_id"] for r in self._recs("attempt_failed", "attempt_interrupted")}
        out = []
        for r in self._recs("attempt_started"):
            p = r["payload"]
            if p["pass"] == pas and r["hash"] in fails:
                out.append((p["lo"], p["hi"], r["hash"]))
        return out

    def _execute(self, pas: str, ranges: list, verification: bool) -> None:
        if not ranges:
            return
        rdir = self.dir / pas
        rdir.mkdir(parents=True, exist_ok=True)
        items = self._work_items(pas)
        gstart = self._selection()["b_group_start"] if pas == "B" else None
        sel_sha = self._selection_record()["sha256"] if pas == "B" else None
        prior = self._prior_failed(pas)
        inflight = max(1, 2 * self.workers)
        ctx = {"view": self.view, "policy": self.policy, "cache": self.cache, "fam_of_spec": self.fam_of_spec,
               "families": self.families}
        pool = None
        if self.workers > 1:
            # ProcessPoolExecutor, not multiprocessing.Pool: when a worker dies (killed, out of memory) Pool loses
            # the task and waits for ever, while the executor raises BrokenProcessPool, which is logged below
            pool = ProcessPoolExecutor(self.workers, mp_context=mp.get_context("fork"),
                                       initializer=_init_pool_worker, initargs=(ctx,))
        else:
            _init_worker(ctx)
        broken = False
        raise_at = _fault("worker_raise")
        die_at = _fault("worker_exit")
        hang_at = _fault("worker_hang")
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
                t["groups"] = np.flatnonzero(gstart[lo:hi]).tolist()
            self._tasks_dispatched += 1
            if raise_at is not None and self._tasks_dispatched == raise_at:
                t["raise"] = True
            if die_at is not None and self._tasks_dispatched == die_at:
                t["die"] = True
            if hang_at is not None and self._tasks_dispatched >= hang_at:
                t["hang"] = True
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
                payload["verification"] = self._verify(pas, t, out, aid)
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

    def _verify(self, pas: str, t: dict, out: dict, aid: str) -> str:
        """Compare every field of a verification chunk (SPA partial maxima included) with the completed attempt
        of record for exactly the same range. A mismatch gives the verification attempt its terminal
        (``attempt_failed``, reason ``nondeterminism``), logs ``nondeterminism`` and raises."""
        new = store.read_arrays(Path(t["path"]), out["sha256"])
        rec = [p for p in self._completed(pas) if p["lo"] == t["lo"] and p["hi"] == t["hi"]]
        field = None
        if len(rec) != 1:
            field = "range"
        else:
            old = store.read_arrays(self.dir / rec[0]["file"], rec[0]["sha256"])
            for k in sorted(set(new) | set(old)):
                if k not in new or k not in old or not np.array_equal(new[k], old[k], equal_nan=True):
                    field = k
                    break
        if field is None:
            return "identical"
        self.log.append("attempt_failed", {"run_id": self.run_id, "attempt_id": aid, "pass": pas,
                                           "reason": "nondeterminism", "error_class": "Nondeterminism"})
        self.log.append("nondeterminism", {"run_id": self.run_id, "pass": pas, "lo": t["lo"], "hi": t["hi"],
                                           "field": field})
        raise RunError(f"nondeterminism in pass {pas} [{t['lo']}, {t['hi']}): field {field}")

    # loading results of record ----------------------------------------------------------------------------
    def _load_pass(self, pas: str, restrict: tuple | None = None) -> dict:
        return load_pass(self.dir, self._completed(pas), pas, restrict)

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
        fam = self.fam_of_spec[self.view.spec_index]
        if self.policy.dedup_behavioural and live.any():
            # aliases are resolved *within a family*: every family's SPA then holds each of its behavioural
            # classes once. An alias across families would silently shrink one family's variant set.
            li = np.flatnonzero(live)
            key = np.concatenate([A["fingerprint"][li], fam[li].astype(">i4").view(np.uint8).reshape(-1, 4)],
                                 axis=1)
            _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
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
        # behaviour shared across families (the same positions registered under another family): computed in
        # each family, and flagged, never merged
        cross = np.zeros(N, bool)
        if live.any():
            li = np.flatnonzero(live)
            fp = A["fingerprint"][li]
            _, inv = np.unique(fp, axis=0, return_inverse=True)
            inv = inv.ravel()
            fams_per = {}
            for g, f in zip(inv.tolist(), fam[li].tolist()):
                fams_per.setdefault(g, set()).add(f)
            multi = np.array([len(fams_per[g]) > 1 for g in inv.tolist()], bool)
            cross[li] = multi
        selected = np.flatnonzero(eligible).astype(np.int64)
        # pass-B order: family-major (families by hash), canonical order within a family; bootstrap groups are
        # consecutive blocks of BOOT_GROUP inside one family, so a family's groups and draws never depend on other
        # families' candidates (S10 F6)
        b_order = selected[np.lexsort((selected, fam[selected]))]
        b_group_start = np.zeros(b_order.size, bool)
        if b_order.size:
            fb = fam[b_order]
            first = np.r_[True, fb[1:] != fb[:-1]]
            rank = np.arange(b_order.size) - np.maximum.accumulate(np.where(first, np.arange(b_order.size), 0))
            b_group_start = (rank % kernels.BOOT_GROUP) == 0
        return {"selected": selected, "alias_of": alias_of, "planned": planned, "cross_family_behaviour": cross,
                "b_order": b_order.astype(np.int64), "b_group_start": b_group_start}

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
        counts["cross_family_behaviour"] = int(sel["cross_family_behaviour"].sum())
        self.log.append("selection", {"run_id": self.run_id, "file": fname, "sha256": sha,
                                      "policy_hash": self.policy.hash(),
                                      "performance_gate": self.policy.performance_gate,
                                      "inputs_root": ids.merkle_root([i["sha256"] for i in inputs]),
                                      "n_inputs": len(inputs), "counts": counts})

    # closing ----------------------------------------------------------------------------------------------
    def results_table(self, stage3: bool) -> dict:
        return build_results_table(self._load_pass("A"), self._load_pass("B") if stage3 else None,
                                   self._selection() if stage3 else None, len(self.view))

    def _close(self, stage3: bool) -> dict:
        from . import package as PK
        self._phase = "close"
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
            self._phase = "stage4"
            pk = PK.build(self, table, spa)
            self._phase = "close"
        self.timings["stage4_s"] = time.perf_counter() - t0
        rec = reconcile(self.ws, self.run_id)
        payload = {"run_id": self.run_id, "results_file": "results.bin", "results_sha256": sha,
                   "result_root": result_root, "packages": pk.get("files", {}),
                   "reconciliation": {k: rec[k] for k in ("registered", "attempts", "violations")},
                   "evidence_class": "synthetic_screening_descriptive", "confirmatory": False}
        self.log.append("run_closed", payload)
        cache = {k: self.cache.stats[k] + self.worker_cache.get(k, 0) for k in self.cache.stats}
        return dict(payload, reused=False, timings=self.timings, cache=cache)


# -- results of record: one implementation for the runner and the auditor ------------------------------------

def load_pass(run_dir: Path, completed: list, pas: str, restrict: tuple | None = None) -> dict:
    """Concatenate the hash-verified files of the completed (non-verification) attempts of one pass."""
    parts = []
    for p in sorted(completed, key=lambda p: p["lo"]):
        if restrict and not (p["lo"] < restrict[1] and restrict[0] < p["hi"]):
            continue
        a = store.read_arrays(Path(run_dir) / p["file"], p["sha256"])
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


def build_results_table(A: dict, B: dict | None, sel: dict | None, N: int) -> dict:
    """The canonical per-candidate table: a pure function of the pass-A files, the selection and the pass-B
    files of record. ``results.bin`` is exactly these bytes, which lets ``reconcile`` rebuild and compare it."""
    table = {"s1": A["s1"], "s2": A["s2"], "reason1": A["reason"], "stats2": A["stats2"],
             "fingerprint": A["fingerprint"]}
    if B is not None:
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
                      "alias_of": sel["alias_of"], "cross_family_behaviour": sel["cross_family_behaviour"]})
    return table


# -- reconciliation (reads persisted records only) ----------------------------------------------------------

INTEGRITY_CODES = frozenset({"results_missing", "results_tampered", "close_record_inconsistent",
                             "results_not_reproducible_from_attempts", "attempt_files_unreadable",
                             "attempt_file_corrupt", "package_tampered", "package_missing"})


def reconcile(ws: Workspace, run_id: str, anchor: dict | None = None) -> dict:
    """Audit one run from the log and the files it names. Every registered candidate must have exactly one
    completed (non-verification) attempt per executed pass; every attempt must have exactly one terminal.

    ``state`` is ``closed`` (a close record exists and every artifact matches it), ``corrupted`` (a close record
    exists but the results file, a package or an attempt file does not match its recorded hash, or the results
    do not rebuild from the attempt files), or ``incomplete`` (no close record; any results file present is not
    of record and is reported as ``unrecorded_results_file``). Returns counts and violations; never certifies
    access completeness (``access_reconciled`` is False)."""
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
    started = [r for r in recs if r["type"] == "run_started"]
    if not started:
        raise RunError(f"no run {run_id} in this workspace")
    view = reg.frozen(root=started[0]["payload"]["identity"]["registry_root"])      # the run's own version
    N = len(view)
    for r in recs:
        if r["type"] in ("nondeterminism", "verification_failed"):
            violations.append({"code": r["type"], "seq": r["seq"]})
    if unfinished and any(r["type"] == "run_closed" for r in recs):
        violations.append({"code": "unfinished_attempts_in_closed_run", "n": len(unfinished)})
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
            try:
                store.read_verified(ws.run_dir(run_id) / p["file"], p["sha256"])
            except (OSError, store.CorruptFile) as e:
                violations.append({"code": "attempt_file_corrupt", "pass": pas, "file": p["file"],
                                   "error_class": type(e).__name__})
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
    state = "incomplete"
    rdir = ws.run_dir(run_id)
    if closed:
        # the close record is the authority: the results file must carry the recorded hash, and the table rebuilt
        # from the hash-verified attempt files must reproduce it bit for bit (S10 F3)
        state = "closed"
        cp = closed[0]["payload"]
        raw = None
        try:
            raw = (rdir / cp["results_file"]).read_bytes()
        except OSError:
            violations.append({"code": "results_missing"})
        if raw is not None and ids.sha256_bytes(raw) != cp["results_sha256"]:
            violations.append({"code": "results_tampered", "file": cp["results_file"]})
        if cp["results_sha256"] != cp["result_root"]:
            violations.append({"code": "close_record_inconsistent"})
        try:
            comp = {pas: [r["payload"] for r in recs if r["type"] == "attempt_completed"
                          and r["payload"]["pass"] == pas
                          and not starts.get(r["payload"]["attempt_id"], {}).get("verification")]
                    for pas in ("A", "B")}
            selr = [r["payload"] for r in recs if r["type"] == "selection"]
            sel = store.read_arrays(rdir / selr[-1]["file"], selr[-1]["sha256"]) if selr and comp["B"] else None
            table = build_results_table(load_pass(rdir, comp["A"], "A"),
                                        load_pass(rdir, comp["B"], "B") if comp["B"] else None, sel, N)
            if ids.sha256_bytes(store.arrays_to_bytes(table)) != cp["result_root"]:
                violations.append({"code": "results_not_reproducible_from_attempts"})
            final = {"s1": {k: int((table["s1"] == v).sum()) for k, v in S1.items()}}
            if "s3" in table:
                final["s3"] = {k: int((table["s3"] == v).sum()) for k, v in S3.items()}
        except Exception as e:
            violations.append({"code": "attempt_files_unreadable", "error_class": type(e).__name__})
        for name, h in cp.get("packages", {}).items():
            try:
                if ids.sha256_bytes((rdir / "packages" / name).read_bytes()) != h:
                    violations.append({"code": "package_tampered", "file": name})
            except OSError:
                violations.append({"code": "package_missing", "file": name})
        if final:
            for st, codes in final.items():
                if sum(codes.values()) != N:
                    violations.append({"code": "status_total_mismatch", "stage": st})
            if final["s1"]["not_run"]:
                violations.append({"code": "candidate_without_stage1_status", "n": final["s1"]["not_run"]})
            if "s3" in final and final["s3"]["not_run"]:
                violations.append({"code": "candidate_without_stage3_status", "n": final["s3"]["not_run"]})
        if any(v["code"] in INTEGRITY_CODES for v in violations):
            state = "corrupted"
    elif any(r["type"] == "run_incomplete" for r in recs) or unfinished or by["failed"]:
        state = "incomplete"
    failed_inv = [{"seq": r["seq"], "phase": r["payload"]["phase"], "error_class": r["payload"]["error_class"]}
                  for r in recs if r["type"] == "run_failed"]
    unrecorded = (not closed) and (rdir / "results.bin").exists()
    return {"run_id": run_id, "registered": {"candidates": N, **view.payload["counts"]},
            "invocations": len(started), "attempts": {"started": len(starts), **by},
            "attempts_per_candidate_max": int(attempts_per.max()) if N else 0,
            "passes": passes, "final_status": final, "violations": violations, "state": state,
            "failed_invocations": failed_inv,
            "unrecorded_results_file": unrecorded,
            "access_reconciled": False, "independent_statistical_tests": None}


def history(ws: Workspace, run_id: str, canonical_index: int) -> list[dict]:
    """Every attempt that covered one candidate (an index in the run's own frozen order) in one run, with its
    terminal (or ``unfinished``)."""
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
                sel = store.read_arrays(ws.run_dir(run_id) / s["file"], s["sha256"])["b_order"]
            hit = canonical_index in set(sel[p["lo"]:p["hi"]].tolist())
        if hit:
            out.append({"attempt_id": r["hash"], "pass": p["pass"], "seq": r["seq"],
                        "terminal": term.get(r["hash"], "unfinished"), "verification": p.get("verification"),
                        "supersedes": p.get("supersedes", [])})
    return out
