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
