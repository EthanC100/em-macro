"""Stage 4: one package per family for independent scientific review. Descriptive, synthetic, never confirmatory.

A package states every denominator separately (hypotheses, strategy specs, variants, candidates, behavioural
classes, aliases, failures, skips), how many runs and attempts looked at the family, which specs were registered
after a run had already looked at it (``post_look``), descriptive screening statistics, the streaming SPA when the
family's variant set is complete, and a descriptive ``M_eff`` per hypothesis.

What a package never contains: a claim, a confirmatory flag set to true, a count of "discoveries", or a number of
independent tests (``independent_statistical_tests`` is null: which unit enters a multiple-testing denominator is
owner decision D-1 of PR #86, not this engine's). The best statistic of a family is always printed with the number
of variants it is the best of.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from manhattan.stats import meff

from . import CONFIRMATORY, EVIDENCE_CLASS
from . import ids, kernels, store
from . import templates as TP

SCHEMA = "manhattan.hte.package/1"
QS = (0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0)


def _q(x: np.ndarray) -> dict | None:
    x = x[np.isfinite(x)]
    if not x.size:
        return None
    return {f"q{int(q * 100):02d}": float(np.quantile(x, q)) for q in QS} | {"n": int(x.size)}


def _looks(runner) -> tuple[set, dict]:
    """(post-look spec hashes, family hash -> run ids that looked at it).

    A run *looks at* every family of the frozen version it evaluates, whatever that version's root. A spec is
    *post-look* when its registry segment was logged after a run had looked at (a) its own family, or (b) any
    candidate with the same economics (domain, template, parameters, binding: the registry's semantic digest),
    so that re-registering a looked-at rule under a new family name is flagged too."""
    log, reg = runner.log, runner.reg
    frozen = {r["payload"]["root"]: r["payload"]["segments"] for r in log.of_type("registry_frozen")}
    segs = log.of_type("registry_segment")
    fam_of = {h: reg.records[reg.records[h]["hypothesis"]]["family"] for h in reg.spec_hashes}
    sem = reg._arrays()["semantic"]
    bounds = np.cumsum([0] + [r["payload"]["n_candidates"] for r in segs])
    runs = [(r["seq"], r["payload"]["run_id"], frozen.get(r["payload"]["identity"]["registry_root"], 0))
            for r in log.of_type("run_started")]
    looked_runs: dict[str, set] = {}
    first_look: dict[str, int] = {}
    for seq, rid, k in runs:
        for r in segs[:k]:
            for sh in r["payload"]["new_specs"]:
                f = fam_of[sh]
                looked_runs.setdefault(f, set()).add(rid)
                first_look[f] = min(first_look.get(f, seq), seq)
    post = set()
    for j, r in enumerate(segs):
        seq = r["seq"]
        for sh in r["payload"]["new_specs"]:
            if fam_of[sh] in first_look and seq > first_look[fam_of[sh]]:
                post.add(sh)
        earlier = [k for (rs, _, k) in runs if rs < seq]
        k = min(max(earlier), j) if earlier else 0
        if k == 0:
            continue
        seen = {bytes(x) for x in sem[: bounds[k]]}           # economics looked at before this segment
        mine = sem[bounds[j]: bounds[j + 1]]
        spec_idx = reg._arrays()["spec_index"][bounds[j]: bounds[j + 1]]
        for row, si in zip(mine, spec_idx):
            if bytes(row) in seen:
                post.add(reg.spec_hashes[int(si)])
    return post, looked_runs


def _cross_family(keys: np.ndarray, fam: np.ndarray) -> np.ndarray:
    """Per row: does the same key (32 bytes) occur in another family?"""
    if not keys.shape[0]:
        return np.zeros(0, bool)
    _, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.ravel()
    pairs = np.unique(np.stack([inv, fam]), axis=1)
    nfam = np.bincount(pairs[0], minlength=inv.max() + 1)
    return nfam[inv] > 1


def _meff(runner, table, idx_h: np.ndarray) -> dict:
    """M_eff (Li-Ji, descriptive) of the stage-3 net series of at most ``meff_cap`` representatives, chosen by
    an outcome-blind stride over the canonical order. Each recomputed series is checked against its recorded
    SHA-256, so the package cannot describe series other than those of record."""
    pol = runner.policy
    comp = idx_h[table["s3"][idx_h] == 1]
    if comp.size < 2:
        return {"value": None, "reason": "fewer than two computed series"}
    if comp.size > pol.meff_cap:
        comp = comp[np.linspace(0, comp.size - 1, pol.meff_cap).astype(np.int64)]
    from .runner import _positions_window
    cache, view, fence = runner.cache, runner.view, runner.panel.fence
    from .runner import _series
    series = []
    for s in range(0, comp.size, 64):
        sub = comp[s: s + 64]
        inputs = []
        for i in sub:
            d = view.describe(int(i))
            Pw, Rw = _positions_window(cache, d, pol, fence)
            c, k = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
            inputs.append((Pw, Rw, c, k))
        out = _series(pol, inputs)
        for r, i in enumerate(sub):
            h = np.frombuffer(hashlib.sha256(np.ascontiguousarray(out["net"][r]).tobytes()).digest(), np.uint8)
            if not np.array_equal(h, table["series_sha256"][i]):
                raise RuntimeError(f"stage-4 recomputation of candidate {int(i)} does not match its recorded "
                                   "stage-3 series hash (nondeterminism)")
            series.append(out["net"][r])
    X = np.stack(series)
    X = X[X.std(axis=1) > 0]
    if X.shape[0] < 2:
        return {"value": None, "reason": "fewer than two non-constant series"}
    corr = np.corrcoef(X)
    return {"value": round(float(meff.li_ji(corr)), 6), "series_used": int(X.shape[0]), "of_computed": int(
        (table["s3"][idx_h] == 1).sum()), "selection": "outcome-blind stride over canonical order"}


def build(runner, table: dict, spa_parts) -> dict:
    view, reg = runner.view, runner.reg
    out_dir = runner.dir / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    fos = runner.fam_of_spec
    fam_idx = fos[view.spec_index]
    post, looked_runs = _looks(runner)
    cross_sem = _cross_family(view.semantic, fam_idx)
    root = view.root
    runs_on_root = [r for r in runner.log.of_type("run_started")
                    if r["payload"]["identity"]["registry_root"] == root]
    run_ids = sorted({r["payload"]["run_id"] for r in runs_on_root})
    files = {}
    pkgs: dict = {}
    meff_jobs: list = []

    def name_of(fh):
        return f"{ids.short_id('family', fh)}.json"

    s2c = {k: i for i, k in enumerate(kernels.S2_COLS)}
    s3c = {k: i for i, k in enumerate(kernels.S3_COLS)}
    from .runner import S1, S3
    for f, fh in enumerate(runner.families):
        idx = np.flatnonzero(fam_idx == f)
        fam = reg.records[fh]
        specs = sorted({int(s) for s in view.spec_index[idx]})
        spec_hashes = [reg.spec_hashes[s] for s in specs]
        hyps = sorted({reg.records[h]["hypothesis"] for h in spec_hashes})
        s1 = table["s1"][idx]
        live = (s1 == S1["pass"]) | (s1 == S1["dominated"])
        pkg = {
            "schema": SCHEMA, "evidence_class": EVIDENCE_CLASS, "confirmatory": CONFIRMATORY, "synthetic": True,
            "family": {"hash": fh, "id": ids.short_id("family", fh), "name": fam["name"],
                       "mechanism": fam["mechanism"], "sign": fam["sign"], "density": fam["density"]},
            "run": {"run_id": runner.run_id, "identity": runner.ident, "policy": runner.policy.as_dict(),
                    "performance_gate": runner.policy.performance_gate},
            "denominators": {
                "hypotheses": len(hyps), "strategy_specs": len(specs),
                "variants": int(np.unique(view.variant[idx], axis=0).shape[0]), "candidates": int(idx.size),
                "cross_family_semantic_duplicates": int(cross_sem[idx].sum()),
                "cross_family_behavioural_duplicates": int(table["cross_family_behaviour"][idx].sum())
                if "cross_family_behaviour" in table else None,
                "behavioural_classes": int(np.unique(table["fingerprint"][idx][live], axis=0).shape[0])
                if live.any() else 0,
                "stage1": {k: int((s1 == v).sum()) for k, v in S1.items() if k != "not_run"},
            },
            "looks": {"runs_on_this_registry": len(run_ids), "run_ids": run_ids,
                      "invocations_on_this_registry": len(runs_on_root),
                      "runs_on_any_registry_version": len(looked_runs.get(fh, ())),
                      "post_look_specs": sorted(h for h in spec_hashes if h in post)},
            "independent_statistical_tests": None,
            "independent_statistical_tests_reason": "the counting unit for a multiple-testing denominator is an "
                                                    "owner decision (PR #86 D-1); M_eff below is descriptive only",
            "warnings": ["SYNTHETIC DATA: no statement here is about any market",
                         "screening and descriptive statistics only; nothing here is evidence"]
            + (["some candidates repeat the economics or the positions of another family's candidates: the "
                "families are not independent"] if cross_sem[idx].any() or (
                    "cross_family_behaviour" in table and table["cross_family_behaviour"][idx].any()) else []),
        }
        st2 = table["stats2"][idx]
        ok2 = table["s2"][idx] == 1
        tt = st2[ok2, s2c["t_stat"]]
        pkg["stage2"] = {"t_stat": _q(tt), "net_sharpe_ann": _q(st2[ok2, s2c["sharpe_ann"]]),
                         "max_t_stat": float(tt.max()) if tt.size else None,
                         "max_is_over_candidates": int(tt.size)}
        if "s3" in table:
            s3 = table["s3"][idx]
            pkg["denominators"]["stage3"] = {k: int((s3 == v).sum()) for k, v in S3.items() if k != "not_run"}
            ok3 = (s3 == S3["computed"]) | (s3 == S3["alias"])
            st3 = table["stats3"][idx]
            pb = st3[ok3, s3c["p_boot"]]
            pkg["stage3"] = {"sharpe_ann": _q(st3[ok3, s3c["sharpe_ann"]]), "p_boot": _q(pb),
                             "share_p_boot_le_0.05": float((pb <= 0.05).mean()) if pb.size else None,
                             "share_note": "about 0.05 is expected when no variant has an edge; a share is not "
                                           "a count of discoveries and variants are correlated"}
            incomplete = int(((s3 == S3["skipped_dominated"]) | (s3 == S3["skipped_not_selected"]) |
                              (s3 == S3["skipped_failed_upstream"]) | (s3 == S3["failed"])).sum())
            if runner.policy.performance_gate:
                pkg["stage3"]["selection_warning"] = ("stage-3 statistics are conditional on a recorded, "
                                                      "performance-ranked selection and are not adjusted for it")
            if incomplete:
                pkg["spa"] = {"computed": False,
                              "reason": f"{incomplete} non-degenerate candidates have no stage-3 series "
                                        "(skipped or failed): an SPA over an incomplete variant set is refused"}
            else:
                parts = [(T, mc, ml, mu, n) for (g, T, mc, ml, mu, n) in spa_parts if g == f]
                if parts:
                    res = kernels.spa_combine(parts)
                    pkg["spa"] = {"computed": True, **res, "L": runner.policy.bootstrap_L,
                                  "note": "Hansen SPA over every non-degenerate variant (aliases enter once; "
                                          "identical series do not change a maximum); fixed block length; "
                                          "descriptive on synthetic data"}
                else:
                    pkg["spa"] = {"computed": False, "reason": "no non-degenerate variant"}
            pkg["m_eff"] = {}
            for h in hyps:
                sp = [s for s in specs if reg.records[reg.spec_hashes[s]]["hypothesis"] == h]
                idx_h = idx[np.isin(view.spec_index[idx], sp)]
                reps = idx_h[table["alias_of"][idx_h] < 0]
                meff_jobs.append((name_of(fh), ids.short_id("hypothesis", h), reps))
        pkgs[name_of(fh)] = pkg
    if meff_jobs:
        vals = _run_meff(runner, table, meff_jobs)
        for (name, hid, _), v in zip(meff_jobs, vals):
            pkgs[name]["m_eff"][hid] = v
    for name, pkg in pkgs.items():
        raw = json.dumps(pkg, sort_keys=True, indent=1, default=float).encode()
        files[name] = store.atomic_write_bytes(out_dir / name, raw)
    return {"files": files}


_MEFF_CTX: dict = {}


def _meff_job(i: int):
    runner, table, jobs = _MEFF_CTX["runner"], _MEFF_CTX["table"], _MEFF_CTX["jobs"]
    return _meff(runner, table, jobs[i][2])


def _run_meff(runner, table, jobs) -> list:
    """M_eff per hypothesis, in parallel when the run has workers (each value is a pure function of its
    hypothesis's recorded series, so the order of computation cannot change it)."""
    _MEFF_CTX.update(runner=runner, table=table, jobs=jobs)
    try:
        if runner.workers > 1 and len(jobs) > 1:
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor
            # an executor, not multiprocessing.Pool: a lost worker raises instead of hanging
            with ProcessPoolExecutor(min(runner.workers, len(jobs)), mp_context=mp.get_context("fork")) as ex:
                return list(ex.map(_meff_job, range(len(jobs))))
        return [_meff_job(i) for i in range(len(jobs))]
    finally:
        _MEFF_CTX.clear()


def load(run_dir: Path, name: str) -> dict:
    return json.loads((Path(run_dir) / "packages" / name).read_text())
