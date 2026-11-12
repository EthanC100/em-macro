"""Metrics M1-M6 and M11 with their confidence intervals (SIM_PREREG section 4), and the checks of section 5.

Two kinds of interval, as pre-registered:

- a mean of per-replication values: ``mean ± 1.96 · sd / √R``;
- a ratio whose denominator varies by replication, and the pooled 0.001-level size: a percentile interval from
  2,000 bootstrap resamples of whole replications.

A criterion is decided only on the pre-registered number of replications. With fewer, the row is a **pilot**: the
estimate and interval are shown and the verdict reads "pilot: not decided".
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from . import criteria as cr
from . import pipeline, world

Z95 = 1.96


@dataclass
class Row:
    metric: str
    what: str
    estimate: float | None
    lo: float | None
    hi: float | None
    n: int                          # replications (mean) or pooled observations (ratio)
    kind: str                       # "mean" or "ratio"
    criterion: str = ""
    threshold: str = ""
    required: bool = False
    verdict: str = "reported"

    def as_dict(self) -> dict:
        return asdict(self)


def mean_ci(values) -> tuple[float, float, float]:
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return math.nan, math.nan, math.nan
    half = Z95 * v.std(ddof=1) / math.sqrt(v.size) if v.size > 1 else math.nan
    return float(v.mean()), float(v.mean() - half), float(v.mean() + half)


def ratio_ci(num, den, rng: np.random.Generator | None = None,
             resamples: int = cr.BOOTSTRAP_RESAMPLES) -> tuple[float, float, float]:
    """Pooled ratio ``Σ num / Σ den`` with a percentile interval from resampling whole replications."""
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    if den.sum() <= 0:
        return math.nan, math.nan, math.nan
    rng = rng or np.random.default_rng(20261112)
    idx = rng.integers(0, num.size, size=(resamples, num.size))
    d = den[idx].sum(axis=1)
    r = np.where(d > 0, num[idx].sum(axis=1) / np.where(d > 0, d, 1.0), np.nan)
    lo, hi = np.nanpercentile(r, [2.5, 97.5])
    return float(num.sum() / den.sum()), float(lo), float(hi)


def _verdict(bound: float, limit: float, upper: bool, required: bool, pilot: bool, evaluated: bool = True) -> str:
    if not evaluated:
        return "not evaluated: fewer than 200 observations"
    if bound is None or math.isnan(bound):
        return "no data"
    ok = bound <= limit if upper else bound >= limit
    if pilot:
        return "pilot: not decided (" + ("within" if ok else "outside") + " threshold so far)"
    if not required:
        return "reported (" + ("within" if ok else "outside") + ")"
    return "pass" if ok else "FAIL"


def col(reps: list[dict], key: str) -> np.ndarray:
    return np.array([r[key] for r in reps], dtype=float)


def per_rep_share(reps: list[dict], num: str, den: str) -> np.ndarray:
    n, d = col(reps, num), col(reps, den)
    return n[d > 0] / d[d > 0]


def summarise(reps: list[dict], scenario: str, size: str) -> list[Row]:
    """Every metric of a STD or LONG scenario run, with interval, threshold and verdict."""
    rows: list[Row] = []
    R = len(reps)
    pilot = R < cr.REPLICATIONS[size]
    sz = world.SIZES[size]
    checkpoints = sorted({max(1, sz.B // 4), sz.B // 2, sz.B})
    forward_keys = [k for k in ("i", "ii", "all") if f"fwd_enrolled_{k}" in reps[0]]
    name = {"i": "candidate (i)", "ii": "candidate (ii)", "all": "E-ALL"}

    def add(metric, what, est, kind, n, criterion="", limit=None, upper=True, evaluated=True, fmt="{:g}"):
        e, lo, hi = est
        req = bool(criterion) and cr.required(criterion, scenario, size)
        verdict = "reported"
        thr = ""
        if limit is not None:
            thr = ("upper bound ≤ " if upper else "lower bound ≥ ") + fmt.format(limit)
            verdict = _verdict(hi if upper else lo, limit, upper, req, pilot, evaluated)
        rows.append(Row(metric, what, e, lo, hi, n, kind, criterion if limit is not None else "", thr, req, verdict))

    for cand in pipeline.CANDIDATES:
        for k in checkpoints:
            add("M1", f"screening FDR, {name[cand]}, batch {k}", mean_ci(col(reps, f"m1_{cand}_b{k}")), "mean", R,
                "V1", cr.V1_FDR_MAX)
    for key in forward_keys:
        for y in pipeline.YEAR_CHECKPOINTS:
            add("M2", f"forward FDR, enrolment by {name[key]}, year {y}", mean_ci(col(reps, f"m2_{key}_y{y}")),
                "mean", R, "V2", cr.V2_FDR_MAX)
    for a in (0.20, 0.05):
        add("M3", f"SPA size at {a}", mean_ci(per_rep_share(reps, f"m3_p{a}_num", "n_reserve_null")), "mean", R,
            "V3", cr.V3_SIZE_MAX[a])
    add("M3", "SPA size at 0.001 (pooled)", ratio_ci(col(reps, "m3_p0.001_num"), col(reps, "n_reserve_null")),
        "ratio", int(col(reps, "n_reserve_null").sum()), "V3", cr.V3_SIZE_MAX[0.001])
    add("M3", "Romano-Wolf FWER at 0.05", mean_ci(per_rep_share(reps, "m3_rw_num", "m3_rw_den")), "mean", R,
        "V3", cr.V3_FWER_MAX)
    add("M3", "SPA size at 0.05, lower p-value (reported)", mean_ci(per_rep_share(reps, "m3_pl05_num", "n_reserve_null")), "mean", R)
    add("M3", "SPA size at 0.05, upper p-value (reported)", mean_ci(per_rep_share(reps, "m3_pu05_num", "n_reserve_null")), "mean", R)
    for cand in pipeline.CANDIDATES:
        n_pass = int(col(reps, f"m4_n_{cand}").sum())
        add("M4", f"linked average error, {name[cand]} ({n_pass} families passed)", mean_ci(col(reps, f"m4_{cand}")),
            "mean", R, "V4", cr.V4_LINK_MAX, evaluated=n_pass >= cr.SMALL_GROUP)
    for c in (20, 100):
        add("M5", f"null component wealth ever reaches {c}", mean_ci(per_rep_share(reps, f"m5_{c}_num", "m5_den")),
            "mean", R, "V5", cr.V5_CROSS_MAX[c])
    for cand in pipeline.CANDIDATES:
        add("M6", f"screening power, {name[cand]}", ratio_ci(col(reps, f"m6_scr_num_{cand}"), col(reps, "m6_scr_den")),
            "ratio", int(col(reps, "m6_scr_den").sum()), "V11", cr.V11_POWER_MIN, upper=False)
    for key in forward_keys:
        den = col(reps, f"m6_fwd_den_{key}")
        add("M6", f"forward power by the end (first-quarter families), enrolment by {name[key]}",
            ratio_ci(col(reps, f"m6_fwd_num_{key}"), den), "ratio", int(den.sum()), "V11", cr.V11_POWER_MIN, upper=False)
        years = [y for r in reps for y in r[f"m6_fwd_years_{key}"]]
        rows.append(Row("M6", f"median years from freeze to formal support, enrolment by {name[key]}",
                        float(np.median(years)) if years else None, None, None, len(years), "median"))
    if "m11_den" in reps[0]:
        est = mean_ci(per_rep_share(reps, "m11_num", "m11_den"))
        e, lo, hi = est
        note = "pilot: not decided" if pilot else ("label needed: descriptive, not error-controlled" if hi > cr.V10_M11_MAX
                                                   else "no label needed")
        rows.append(Row("M11", "adaptive SPA size at 0.05 on the full set", e, lo, hi, R, "mean", "V10(b)",
                        f"if upper bound > {cr.V10_M11_MAX}: label", True, note))
    rows.append(Row("cost", "seconds per replication", float(col(reps, "seconds").mean()), None, None, R, "mean"))
    rows.append(Row("cost", "mean bootstrap resamples per family", float(col(reps, "mean_B").mean()), None, None, R, "mean"))
    rows.append(Row("info", "share of weeks with a bet (variance-ratio rule)", float(col(reps, "bet_rate").mean()), None, None, R, "mean"))
    rows.append(Row("info", "families per replication", float(col(reps, "n_families").mean()), None, None, R, "mean"))
    rows.append(Row("info", "families enrolled, E-ALL / (i) / (ii)", None, None, None, R, "text",
                    verdict=" / ".join(f"{col(reps, f'fwd_enrolled_{k}').mean():.1f}" if f"fwd_enrolled_{k}" in reps[0]
                                       else "-" for k in ("all", "i", "ii"))))
    return rows


def power_difference(reps_by_scenario: dict[str, list[dict]]) -> dict:
    """Section 7 step 2: average screening power over P1-P4 for each candidate, and the bootstrap interval of the
    difference (i) − (ii). Scenarios are independent, so each is resampled on its own."""
    rng = np.random.default_rng(20261112)
    point = {"i": [], "ii": []}
    boots = []
    for sid in cr.POWER_SCENARIOS:
        reps = reps_by_scenario[sid]
        den = col(reps, "m6_scr_den")
        idx = rng.integers(0, den.size, size=(cr.BOOTSTRAP_RESAMPLES, den.size))
        b = []
        for cand in ("i", "ii"):
            num = col(reps, f"m6_scr_num_{cand}")
            point[cand].append(num.sum() / den.sum())
            b.append(num[idx].sum(axis=1) / den[idx].sum(axis=1))
        boots.append(b[0] - b[1])
    diff = np.mean(boots, axis=0)
    lo, hi = np.percentile(diff, [2.5, 97.5])
    return {"power_i": float(np.mean(point["i"])), "power_ii": float(np.mean(point["ii"])),
            "difference": float(np.mean(point["i"]) - np.mean(point["ii"])), "lo": float(lo), "hi": float(hi),
            "by_scenario": {sid: {"i": float(point["i"][j]), "ii": float(point["ii"][j])}
                            for j, sid in enumerate(cr.POWER_SCENARIOS)}}


# ------------------------------------------------------------------ size HB: M7, M8, M9 (SIM_PREREG V6-V8)

def _ece(n: np.ndarray, true: np.ndarray, p: np.ndarray) -> float:
    """Expected calibration error over bins with at least 200 observations: the count-weighted mean absolute gap
    between stated and observed frequency. NaN when no bin is large enough."""
    ok = n >= cr.SMALL_GROUP
    if not ok.any():
        return math.nan
    return float(np.sum(np.abs(p[ok] - true[ok])) / n[ok].sum())


def ece_ci(reps_bins: list[tuple], rng: np.random.Generator | None = None) -> tuple[float, float, float]:
    """ECE of the pooled reliability curve, with a percentile interval from resampling whole replications.
    ``reps_bins`` holds, per replication, (counts, true counts, sums of stated probability) by bin."""
    if not reps_bins:
        return math.nan, math.nan, math.nan
    arr = np.array(reps_bins, dtype=float)                           # (R, 3, bins)
    rng = rng or np.random.default_rng(20261112)
    est = _ece(*arr.sum(axis=0))
    idx = rng.integers(0, arr.shape[0], size=(cr.BOOTSTRAP_RESAMPLES, arr.shape[0]))
    boots = np.array([_ece(*arr[i].sum(axis=0)) for i in idx])
    if np.isnan(boots).all():
        return est, math.nan, math.nan
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return est, float(lo), float(hi)


def summarise_hb(reps: list[dict], scenario: str) -> list[Row]:
    """Every metric of an HB scenario run. Reviews at which the model did not converge carry no ``Π`` and are
    counted, not hidden."""
    rows: list[Row] = []
    R = len(reps)
    default_sampler = all(tuple(r.get("sampler", ())) == (1000, 1000) for r in reps)
    pilot = R < cr.REPLICATIONS["HB"] or not default_sampler
    years = [str(y) for y in reps[0]["eval_years"]]
    name = {"i": "candidate (i)", "ii": "candidate (ii)"}

    def add(metric, what, est, kind, n, criterion="", limit=None, upper=True, evaluated=True):
        e, lo, hi = est
        thr, verdict = "", "reported"
        if limit is not None:
            thr = ("upper bound ≤ " if upper else "lower bound ≥ ") + f"{limit:g}"
            verdict = _verdict(hi if upper else lo, limit, upper, True, pilot, evaluated)
        rows.append(Row(metric, what, e, lo, hi, n, kind, criterion if limit is not None else "", thr,
                        limit is not None, verdict))

    for y in years:
        revs = [r["reviews"][y] for r in reps if y in r["reviews"]]
        ok = [v for v in revs if v.get("review_ok")]
        rows.append(Row("fit", f"year {y}: reviews with all six fits converged", len(ok) / len(revs) if revs else None,
                        None, None, len(revs), "share",
                        verdict=f"{len(ok)} of {len(revs)} reviews; a review that is not converged changes no tier"))
        if revs:
            rows.append(Row("fit", f"year {y}: worst R-hat / smallest ESS / divergences (medians over reviews)", None,
                            None, None, len(revs), "text",
                            verdict=" / ".join([f"{np.median([max(v['rhat_max']) for v in revs]):.3f}",
                                                f"{np.median([min(v['ess_min']) for v in revs]):.0f}",
                                                f"{np.median([sum(v['divergences']) for v in revs]):.0f}"])))
            rows.append(Row("cost", f"year {y}: seconds for the six fits", float(np.mean([sum(v["fit_seconds"]) for v in revs])),
                            None, None, len(revs), "mean"))
        decided = y in ("4", "10")
        if not ok:
            continue
        g = lambda k: np.array([v[k] for v in ok], dtype=float)
        for cut, key in ((0.80, "pimin80"), (0.40, "pimin40")):
            n_obs = int(g(f"{key}_n").sum())
            add("M7", f"year {y}: share with a true edge among families with Π^min ≥ {cut} ({n_obs} family observations)",
                ratio_ci(g(f"{key}_true"), g(f"{key}_n")), "ratio", n_obs,
                "V6" if decided else "", cr.V6_SHARE_MIN[cut] if decided else None, upper=False,
                evaluated=n_obs >= cr.SMALL_GROUP)
        add("M7", f"year {y}: expected calibration error of the central model",
            ece_ci([(v["cal_n"], v["cal_true"], v["cal_p"]) for v in ok]), "ratio", int(g("n_eval").sum()),
            "V6" if decided else "", cr.V6_ECE_MAX if decided else None)
        if scenario == "D01":
            add("M7", f"year {y}: share of family evaluations with Π^min ≥ 0.80 (no edges exist)",
                ratio_ci(g("pimin80_n"), g("n_eval")), "ratio", int(g("n_eval").sum()),
                "V6" if decided else "", cr.V6_D01_HIGH_MAX if decided else None)
        for cand in ("i", "ii"):
            for grp, label in (("prom", "Promising or higher"), ("supp", "Statistically supported or higher")):
                n_obs = int(g(f"m9_{grp}_{cand}_n").sum())
                est = ratio_ci(g(f"m9_{grp}_{cand}_model"), g(f"m9_{grp}_{cand}_n"))
                e, lo, hi = est
                thr, verdict = "", "reported"
                if decided:
                    thr = f"upper bound ≤ +{cr.V8_BIAS_MAX:g} and lower bound ≥ {cr.V8_BIAS_MIN:g}"
                    if n_obs < cr.SMALL_GROUP:
                        verdict = "not evaluated: fewer than 200 observations"
                    elif pilot:
                        verdict = "pilot: not decided"
                    else:
                        verdict = "pass" if (hi <= cr.V8_BIAS_MAX and lo >= cr.V8_BIAS_MIN) else "FAIL"
                rows.append(Row("M9", f"year {y}: bias of the model's Sharpe ratio, {label}, {name[cand]} ({n_obs} obs.)",
                                e, lo, hi, n_obs, "ratio", "V8" if decided else "", thr, decided, verdict))
                add("M9", f"year {y}: bias of the naive estimate, {label}, {name[cand]}",
                    ratio_ci(g(f"m9_{grp}_{cand}_naive"), g(f"m9_{grp}_{cand}_n")), "ratio", n_obs)
    for cand in ("i", "ii"):
        den = col(reps, f"m8_den_{cand}")
        add("M8", f"premature elimination: families with a true edge that end dormant, {name[cand]}",
            ratio_ci(col(reps, f"m8_num_{cand}"), den), "ratio", int(den.sum()), "V7", cr.V7_ELIM_MAX)
        rows.append(Row("info", f"at the end, {name[cand]}: passed screening / Promising / supported / dormant (means)",
                        None, None, None, R, "text",
                        verdict=" / ".join(f"{col(reps, k + cand).mean():.1f}" for k in
                                           ("screened_", "end_promising_", "end_supported_", "end_dormant_"))))
    rows.append(Row("cost", "seconds per replication", float(col(reps, "seconds").mean()), None, None, R, "mean"))
    rows.append(Row("info", "sampler (warm-up, kept draws per chain; 4 chains)", None, None, None, R, "text",
                    verdict=", ".join(sorted({f"{r['sampler'][0]}/{r['sampler'][1]}" for r in reps}))))
    return rows
