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
    tail += dormancy_rows(reps)
    tail.append(Row("cost", "seconds per replication spent on the model (estimates, six fits at four dates, forecasts)",
                    float(col(reps, "model_seconds").mean()), None, None, R, "mean"))
    tail.append(Row("info", "model", None, None, None, R, "text", verdict=", ".join(sorted({r["model"] for r in reps}))))
    return head + rows + tail


RULE_NAME = {"v31": "rule of 3.1 (forecast and own forward record)", "v30": "rule of 3.0 (forecast alone), shadow",
             "none": "no dormancy, shadow"}


def dormancy_rows(reps: list[dict], cand: str = "i") -> list[Row]:
    """Diagnostics of the dormancy rule, reported without a threshold (candidate (i)'s tiers; the two candidates
    differ only in which families start as Promising). The rule of record is Protocol 3.1 section 9.1; the rule
    of 3.0 and "no dormancy" are stepped on the same fits as shadows and decide nothing."""
    if not reps or "diag" not in reps[0]:
        return []
    R = len(reps)
    d = {rule: [r["diag"][cand][rule] for r in reps] for rule in ("v31", "v30", "none")}
    g = lambda rule, k: np.array([x[k] for x in d[rule]], dtype=float)
    cat = lambda rule, k: np.array([v for x in d[rule] for v in x[k]], dtype=float)
    rows = []

    def ratio(what, num, den):
        e, lo, hi = ratio_ci(num, den)
        rows.append(Row("diag", what, e, lo, hi, int(den.sum()), "ratio"))

    def text(what, verdict, n=R):
        rows.append(Row("diag", what, None, None, None, int(n), "text", verdict=verdict))

    for rule in ("v31", "v30"):
        name = RULE_NAME[rule]
        den, nul = g(rule, "m8_den"), g(rule, "n_null")
        if rule == "v30":
            ratio(f"{name}: premature elimination (M8) on the same fits", g(rule, "m8_num"), den)
        ratio(f"{name}: share of families with a true edge ever made dormant", g(rule, "edge_ever_dormant"), den)
        ratio(f"{name}: share of families with a true edge dormant at the end", g(rule, "edge_end_dormant"), den)
        ratio(f"{name}: premature elimination had nothing been able to wake at the last date", g(rule, "m8_num_no_last_wake"), den)
        ratio(f"{name}: share of families with no edge ever made dormant", g(rule, "null_ever_dormant"), nul)
        ratio(f"{name}: share of families with no edge dormant at the end", g(rule, "null_end_dormant"), nul)
        ratio(f"{name}: share of family-reviews with a write-up (attention spent; 1 with no dormancy)",
              g(rule, "reviews_written"), g(rule, "reviews_possible"))
        sh = cat(rule, "edge_dormant_share")
        text(f"{name}: dormant share of forward life, families with a true edge ever dormant: mean / median / largest",
             " / ".join(f"{x:.2f}" for x in (sh.mean(), np.median(sh), sh.max())) if sh.size else "none was dormant", sh.size)
        n_null = g(rule, "null_ever_dormant").sum()
        text(f"{name}: dormant share of forward life, families with no edge ever dormant: mean",
             f"{g(rule, 'null_dormant_share_sum').sum() / n_null:.2f}" if n_null else "none was dormant", n_null)
        woke = int(g(rule, "edge_woken").sum())
        text(f"{name}: reactivation, families with a true edge: woken / of those dormant again at the end / Statistically "
             "supported at the end", f"{woke} / {int(g(rule, 'edge_woken_end_dormant').sum())} / {int(g(rule, 'edge_woken_supported').sum())}", woke)
        nwoke = int(g(rule, "null_woken").sum())
        text(f"{name}: reactivation, families with no edge: woken / of those dormant again at the end",
             f"{nwoke} / {int(g(rule, 'null_woken_end_dormant').sum())}", nwoke)
        delay = cat(rule, "edge_entry_delay_years")
        late = delay[delay > 0]
        text(f"{name}: tier entry of families with a true edge: enter Statistically supported with no dormancy / never "
             "enter because dormant / enter later because dormant (mean delay in years)",
             f"{int(g(rule, 'edge_entry_without_dormancy').sum())} / {int(g(rule, 'edge_entry_lost').sum())} / "
             f"{late.size}" + (f" ({late.mean():.1f})" if late.size else ""), int(g(rule, "edge_entry_without_dormancy").sum()))
    gate = np.sum([x["gate"] for x in d["v31"]], axis=0)
    if gate.sum():
        text("rule of 3.1: at reviews with a forecast, families not yet supported: forecast and forward record both below "
             "0.05 / forecast only / forward record only / neither (shares)",
             " / ".join(f"{x / gate.sum():.3f}" for x in gate), int(gate.sum()))
    years = cat("none", "edge_entry_years")
    text("no dormancy, shadow: years from freeze to Statistically supported, families with a true edge that enter: "
         "median / 10th / 90th percentile", " / ".join(f"{x:.1f}" for x in np.percentile(years, [50, 10, 90])) if years.size
         else "none entered", years.size)
    if "forecast_seconds" in reps[0]:
        rows.append(Row("cost", "seconds per replication spent on the dormancy forecast (both rules, both candidates)",
                        float(col(reps, "forecast_seconds").mean()), None, None, R, "mean"))
    return rows


SHARPE_BINS = ((0.25, 0.40), (0.40, 0.70), (0.70, 1.00), (1.00, 1.40), (1.40, math.inf))


def tier_entry_table(reps: list[dict], years: tuple, *, cand: str = "i", rule: str = "v31", by: str = "programme") -> list[dict]:
    """Share of families with a true edge that have entered "Statistically supported", by true hedged Sharpe ratio
    of the family portfolio. Reported for Ethan's decision on the tier's bar; no criterion reads it.

    ``by="programme"``: among families frozen before programme year ``Y``, the share that entered at a review on
    or before year ``Y`` (their forward records are between 0 and ``Y`` years long). ``by="age"``: among families
    with at least ``Y`` years of forward life in the programme, the share that entered within ``Y`` years of
    their freeze. ``rule`` is ``"v31"`` (the rule of record) or ``"none"`` (the same fits with no dormancy).
    Intervals are percentile intervals from resampling whole replications."""
    col_i = 2 if rule == "v31" else 3
    out = []
    for lo, hi in SHARPE_BINS:
        row = {"sharpe_lo": lo, "sharpe_hi": hi, "years": {}}
        true_all = []
        for y in years:
            num, den = [], []
            for r in reps:
                n = d = 0
                for true, freeze, *entries in r["diag"][cand]["v31"]["edge_families"]:
                    if not lo <= true < hi:
                        continue
                    entry = entries[col_i - 2]
                    if by == "programme":
                        if freeze >= y * 252:
                            continue
                        d += 1
                        n += int(0 <= entry <= y * 252)
                    else:
                        if freeze + y * 252 > 2520:
                            continue
                        d += 1
                        n += int(0 <= entry <= freeze + y * 252)
                    true_all.append(true)
                num.append(n)
                den.append(d)
            e, a, b = ratio_ci(num, den) if sum(den) else (math.nan, math.nan, math.nan)
            row["years"][y] = {"share": e, "lo": a, "hi": b, "n": int(sum(den)), "entered": int(sum(num))}
        row["mean_true_sharpe"] = float(np.mean(true_all)) if true_all else math.nan
        out.append(row)
    return out
