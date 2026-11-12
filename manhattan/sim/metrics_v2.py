"""Metrics of the parts SIM_PREREG_v2 changed: the three SPA tests side by side (D11 and its hedged twins), and
the HB runs of the analytic model. Intervals and verdict rules are version 1's (``manhattan/sim/metrics.py``),
called, not copied.
"""
from __future__ import annotations

import copy
import math

import numpy as np

from . import criteria as cr
from . import criteria_v2 as cr2
from . import metrics, pipeline_v2
from .metrics import Row, col, mean_ci, per_rep_share, ratio_ci

NAME = {"v31": "hedge-aware test (3.1)", "v30": "3.0 test on the estimated hedge",
        "oracle": "3.0 test on the true hedged returns (oracle)"}


def half_width(reps: list[dict], key: str) -> float:
    e, lo, hi = mean_ci(per_rep_share(reps, key, "n_reserve_null"))
    return (hi - lo) / 2 if hi == hi else math.nan


def spa_pilot(reps: list[dict], scenario: str) -> bool:
    """Whether a run of the three tests is still a pilot: below its replication count, or (a twin) not yet at
    version 1's precision target."""
    if len(reps) < cr2.replications(scenario, "STD"):
        return True
    if not cr2.is_twin(scenario):
        return False
    return any(not half_width(reps, f"v31_p{a}_num") <= limit for a, limit in cr2.TWIN_HALF_WIDTH_MAX.items())


def summarise_spa(reps: list[dict], scenario: str) -> list[Row]:
    """M3 for the hedge-aware test (with its thresholds) and, beside it, for the 3.0 test on the estimated hedge
    and for the oracle; then the paired differences from the oracle, replication by replication."""
    rows: list[Row] = []
    R = len(reps)
    pilot = spa_pilot(reps, scenario)
    null = col(reps, "n_reserve_null")
    for k in pipeline_v2.METHODS:
        judged = k == "v31"

        def add(what, est, kind, n, limit=None):
            e, lo, hi = est
            thr, verdict = "", "reported"
            if judged and limit is not None:
                thr = f"upper bound ≤ {limit:g}"
                verdict = metrics._verdict(hi, limit, True, True, pilot)
            rows.append(Row("M3", f"{NAME[k]}: {what}", e, lo, hi, n, kind, "V3" if thr else "", thr, bool(thr), verdict))

        for a in (0.20, 0.05):
            add(f"SPA size at {a}", mean_ci(per_rep_share(reps, f"{k}_p{a}_num", "n_reserve_null")), "mean", R,
                cr2.V3_SIZE_MAX[a])
        add("SPA size at 0.001 (pooled)", ratio_ci(col(reps, f"{k}_p0.001_num"), null), "ratio", int(null.sum()),
            cr2.V3_SIZE_MAX[0.001])
        add("Romano-Wolf FWER at 0.05", mean_ci(per_rep_share(reps, f"{k}_rw_num", "m3_rw_den")), "mean", R,
            cr2.V3_FWER_MAX)
        add("SPA size at 0.05, lower p-value", mean_ci(per_rep_share(reps, f"{k}_pl05_num", "n_reserve_null")), "mean", R)
        add("SPA size at 0.05, upper p-value", mean_ci(per_rep_share(reps, f"{k}_pu05_num", "n_reserve_null")), "mean", R)
    ok = null > 0
    for a in (0.20, 0.05):
        for k in ("v31", "v30"):
            diff = (col(reps, f"{k}_p{a}_num") - col(reps, f"oracle_p{a}_num"))[ok] / null[ok]
            e, lo, hi = mean_ci(diff)
            rows.append(Row("M3", f"paired difference at {a}: {NAME[k]} minus the oracle", e, lo, hi, R, "mean"))
        diff = (col(reps, f"v31_p{a}_num") - col(reps, f"v30_p{a}_num"))[ok] / null[ok]
        e, lo, hi = mean_ci(diff)
        rows.append(Row("M3", f"paired difference at {a}: hedge-aware test minus the 3.0 test on the estimated hedge",
                        e, lo, hi, R, "mean"))
    if cr2.is_twin(scenario):
        for a, limit in cr2.TWIN_HALF_WIDTH_MAX.items():
            hw = half_width(reps, f"v31_p{a}_num")
            rows.append(Row("precision", f"95% half-width of the hedge-aware size at {a}", hw, None, None, R, "mean",
                            threshold=f"at most {limit:g} (SIM_PREREG_v2 section 6)",
                            verdict=("met" if hw <= limit else "not met: continue the run")
                            if R >= cr2.REPLICATIONS_TWIN else "pilot"))
    rows.append(Row("cost", "seconds per replication", float(col(reps, "seconds").mean()), None, None, R, "mean"))
    for k in pipeline_v2.METHODS:
        rows.append(Row("cost", f"mean bootstrap resamples per family, {NAME[k]}", float(col(reps, f"{k}_mean_B").mean()),
                        None, None, R, "mean"))
    rows.append(Row("info", "families per replication", float(col(reps, "n_families").mean()), None, None, R, "mean"))
    return rows


def summarise_hb(reps: list[dict], scenario: str) -> list[Row]:
    """Every metric of an HB run of the analytic model. M7, M8 and M9 and their verdicts are computed by version
    1's ``metrics.summarise_hb`` on the same counts; the sampler's diagnostics, which do not exist here, are
    replaced by the grid gate (M12) and the cost of the closed form."""
    shim = copy.deepcopy(reps)
    for r in shim:
        r["sampler"] = [1000, 1000]                      # version 1 calls anything else a pilot; nothing is sampled here
        for v in r["reviews"].values():
            n = len(v["ok"])
            v.update(converged=v["ok"], rhat_max=[1.0] * n, ess_min=[math.inf] * n, divergences=[0] * n)
    rows = [r for r in metrics.summarise_hb(shim, scenario)
            if not (r.metric == "fit" or (r.metric == "info" and r.what.startswith("sampler"))
                    or (r.metric == "cost" and "seconds for the six fits" in r.what))]
    R = len(reps)
    pilot = R < cr.REPLICATIONS["HB"]
    years = [str(y) for y in reps[0]["eval_years"]]
    revs = [(y, r["reviews"][y]) for r in reps for y in years if y in r["reviews"]]
    bad = sum(1 for _, v in revs if not v["review_ok"])
    head = [Row("M12", f"reviews not computed (a fit fails the grid gate), of {len(revs)}", float(bad), None, None, len(revs),
                "count", "V12", f"exactly {cr2.V12_REVIEWS_NOT_COMPUTED_MAX}", True,
                ("pilot: not decided (" + ("none so far" if bad == 0 else f"{bad} so far") + ")") if pilot
                else ("pass" if bad <= cr2.V12_REVIEWS_NOT_COMPUTED_MAX else "FAIL")),
            Row("fit", "largest posterior mass on the ends of the grid of μ_A, any fit", max(max(v["edge_mass"]) for _, v in revs),
                None, None, len(revs), "max", threshold=f"gate: at most {cr2.EDGE_MASS_MAX:g}")]
    tail = []
    for y in years:
        v = [x for yy, x in revs if yy == y]
        if not v:
            continue
        tail.append(Row("cost", f"year {y}: seconds for the six fits of a review ({np.mean([x['n_live'] for x in v]):.0f} families)",
                        float(np.mean([x["six_fits_seconds"] for x in v])), None, None, len(v), "mean"))
        tail.append(Row("info", f"year {y}: common share r of the forward estimates' variance",
                        float(np.mean([x["r_F"] for x in v])), None, None, len(v), "mean"))
        done = [x for x in v if x.get("binding_edge")]
        n_edge = sum(x["n_edge"] for x in done)
        if n_edge:
            bind = np.sum([x["binding_edge"] for x in done], axis=0)
            pmin, p0, pmax = np.sum([x["pi_edge_sum"] for x in done], axis=0) / n_edge
            tail.append(Row("info", f"year {y}: families with a true edge ({n_edge} observations): mean Π^min / mean Π under "
                                    "S0 / mean Π^max", None, None, None, n_edge, "text",
                            verdict=f"{pmin:.3f} / {p0:.3f} / {pmax:.3f}"))
            tail.append(Row("info", f"year {y}: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 "
                                    "(shares)", None, None, None, n_edge, "text",
                            verdict=" / ".join(f"{b / n_edge:.2f}" for b in bind)))
            tail.append(Row("info", f"year {y}: families with a true edge: share Statistically supported / share dormant, "
                                    "candidate (i)", None, None, None, n_edge, "text",
                            verdict=f"{sum(x['edge_supported_i'] for x in done) / n_edge:.3f} / "
                                    f"{sum(x['edge_dormant_i'] for x in done) / n_edge:.3f}"))
        h = {k: float(np.mean([x["hyper"][k] for x in v])) for k in v[0]["hyper"]}
        rho = [h[k] for k in sorted(h) if k.startswith("rho_")]
        tail.append(Row("info", f"year {y}: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews)",
                        None, None, None, len(v), "text",
                        verdict=" / ".join([f"{h['mu_A']:.3f}", f"{h['tau_A']:.3f}", f"{h['psi']:.3f}",
                                            ", ".join(f"{x:.2f}" for x in rho)])))
    tail.append(Row("cost", "seconds per replication spent on the model (estimates, six fits at four dates, forecasts)",
                    float(col(reps, "model_seconds").mean()), None, None, R, "mean"))
    tail.append(Row("info", "model", None, None, None, R, "text", verdict=", ".join(sorted({r["model"] for r in reps}))))
    return head + rows + tail
