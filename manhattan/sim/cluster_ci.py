"""Every simulation interval recomputed with the replication as the unit of clustering (session 6M).

    python -m manhattan.sim.cluster_ci            # writes results/manhattan_sim/v2/CLUSTERED_INTERVALS.md and .json
    python -m manhattan.sim.cluster_ci --current-hb --name PILOT_RERUN3_INTERVALS
                                                  # only the HB runs of the code now checked out, under another name

**Why.** Tests inside one replication share their simulated paths (one common factor, one calendar, one
programme), so the only independent units are whole replications. The pre-registered intervals (SIM_PREREG.md
section 4) already respect that in form: a mean of per-replication values with ``± 1.96 · sd / √R``, and a
percentile bootstrap of whole replications for ratios. What they do not do is allow for **how few clusters a
pilot has**: with 6 to 36 replications a normal quantile and a percentile bootstrap are both too narrow, and an
interval is reported as "0.000 to 0.000" when no replication had an event.

**The corrected interval** (reported beside the old one; it replaces nothing and decides nothing; for the
expected calibration error, which jumps when a bin crosses 200 observations, it is rough):

- the estimate is the pre-registered one, unchanged;
- its standard error is the **delete-one-replication jackknife** of that same estimator: the metric is recomputed
  ``R`` times, each time without one replication, and ``se² = (R − 1)/R · Σ (θ_(−r) − mean θ_(−·))²``. For a
  mean of per-replication values this is exactly ``sd/√R``; for a pooled ratio it is the cluster-robust
  (linearised) standard error; for the calibration error it carries the dependence between bins;
- the interval is ``estimate ± t_{R−1, 0.975} · se``: a Student-t quantile with ``R − 1`` degrees of freedom
  (2.57 for 6 replications, 2.20 for 12, 2.03 for 36, 1.97 for 400);
- when every replication gives the same value (nothing happened in any of them), the jackknife is zero and says
  nothing. For an estimate of 0 the upper end is then the exact bound on the share of replications in which
  anything would happen, ``1 − 0.025^(1/R)`` (0.26 for 12 replications, 0.10 for 36): a rate inside a
  replication cannot exceed the chance that the replication has an event at all. For an estimate of 1 the
  lower end is ``0.025^(1/R)``.

The verdict column compares the same end of the interval with the same threshold as before.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import t as student_t

from . import criteria_v2 as cr2
from . import metrics, metrics_v2, pipeline_v2, run, seeds, world

RATE_METRICS = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M11")       # shares between 0 and 1
PILOT_5M_HB_CODE = "c22815235975c486"       # the HB pilot of record of session 5M (dormancy rule of 3.0): kept beside the rerun
PILOT_6M_HB_CODE = "630059032fd6e5b8"       # session 6M's rerun (a second condition on Π^max, four review dates): superseded
HB_SOURCES = {PILOT_5M_HB_CODE: "analytic model, dormancy rule of 3.0, four review dates (PILOT_RERUN_REPORT.md, superseded)",
              PILOT_6M_HB_CODE: "analytic model, forecast and Π^max, four review dates (PILOT_RERUN2_REPORT.md, superseded)"}
HB_CURRENT = "analytic model, dormancy rule of 3.1 §9.1 (forward record), quarterly reviews (PILOT_RERUN3_REPORT.md)"
_COUNT = re.compile(r"\s*\(\d+ [^)]*\)|, of \d+")


def key(row: metrics.Row) -> tuple[str, str]:
    """A row's identity without the counts written into its label (they change when a replication is left out)."""
    return row.metric, _COUNT.sub("", row.what)


def limits(threshold: str) -> list[tuple[str, float]]:
    """``[("upper", 0.06)]`` from "upper bound ≤ 0.06"; two entries for the bias criterion; [] for a text gate."""
    out = []
    for side, num in re.findall(r"(upper|lower) bound [≤≥] ([+\-−]?[0-9.]+)", threshold or ""):
        out.append((side, float(num.replace("−", "-"))))
    return out


def side(lo, hi, lims) -> str | None:
    """"within" or "outside" the thresholds, or None when there is no numeric threshold or no interval."""
    if not lims or lo is None or hi is None or any(isinstance(x, float) and math.isnan(x) for x in (lo, hi)):
        return None
    ok = all((hi <= v) if s == "upper" else (lo >= v) for s, v in lims)
    return "within" if ok else "outside"


def jackknife(rows_fn, reps: list[dict]) -> list[dict]:
    """The rows of ``rows_fn(reps)`` with their corrected intervals. ``rows_fn`` maps replication records to
    ``metrics.Row`` objects (one of the summarise functions)."""
    full = rows_fn(reps)
    R = len(reps)
    loo = [{key(r): r.estimate for r in rows_fn(reps[:i] + reps[i + 1:])} for i in range(R)] if R > 1 else []
    tq = float(student_t.ppf(0.975, R - 1)) if R > 1 else math.nan
    out = []
    for r in full:
        if r.estimate is None or r.kind in ("text", "median", "count", "max", "share") or r.metric in ("cost", "info", "fit", "precision"):
            continue
        if (r.lo is None and r.hi is None) or not math.isfinite(r.estimate):
            continue                                    # no interval was reported, or there is no data at all
        vals = np.array([d.get(key(r), np.nan) if d.get(key(r)) is not None else np.nan for d in loo], dtype=float)
        ok = np.isfinite(vals)
        d = {"metric": r.metric, "what": r.what, "n": r.n, "estimate": r.estimate, "old_lo": r.lo, "old_hi": r.hi,
             "threshold": r.threshold, "required": r.required, "old_verdict": r.verdict, "replications": R,
             "rule": "jackknife-t"}
        evaluated = not r.verdict.startswith("not evaluated")
        if R < 2 or ok.sum() < R:
            d.update(lo=None, hi=None, se=None, rule="not computable: the metric is undefined without some replication")
        else:
            se = math.sqrt((R - 1) / R * float(((vals - vals.mean()) ** 2).sum()))
            if se <= 1e-12 * max(1.0, abs(r.estimate)):
                se = 0.0                                # every replication gives the same value
            lo, hi = r.estimate - tq * se, r.estimate + tq * se
            if se == 0.0 and r.metric in RATE_METRICS and r.estimate == 0.0:
                hi, d["rule"] = 1.0 - 0.025 ** (1.0 / R), "no event in any replication: exact bound over replications"
            elif se == 0.0 and r.metric in RATE_METRICS and r.estimate == 1.0:
                lo, d["rule"] = 0.025 ** (1.0 / R), "an event in every replication: exact bound over replications"
            d.update(lo=lo, hi=hi, se=se)
        lims = limits(r.threshold)
        d["old_side"] = side(r.lo, r.hi, lims) if evaluated else None
        d["new_side"] = side(d["lo"], d["hi"], lims) if evaluated else None
        d["changed"] = bool(d["old_side"] and d["new_side"] and d["old_side"] != d["new_side"])
        out.append(d)
    return out


def _records(scenario: str, size: str, out: Path, version: str, code: str | None = None) -> tuple[list[dict], str]:
    """Records of one code on file: the code asked for, or the one now checked out, or the most common."""
    every = run.load_reps(scenario, size, seeds.DEVELOPMENT, out, version=version)
    if not every:
        return [], ""
    codes = Counter(r["code"] for r in every)
    now = run.code_hash(size, version=version)
    use = code if code in codes else (now if now in codes else codes.most_common(1)[0][0])
    return run.load_reps(scenario, size, seeds.DEVELOPMENT, out, use, version), use


def hb_codes(scenario: str, out: Path) -> list[str]:
    """Every code hash with HB records of the analytic model on file, oldest first."""
    seen = []
    path = run.reps_path(scenario, "HB", seeds.DEVELOPMENT, out, "v2")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)["code"]
                if c not in seen:
                    seen.append(c)
    return seen


def collect_hb(out: Path = run.OUT, current_only: bool = False) -> list[dict]:
    """The HB runs of the analytic model, once per code that was the subject of a report (records of different
    code are never pooled); with ``current_only``, the code now checked out alone."""
    runs = []
    now = run.code_hash("HB", version="v2")
    for scenario, size in run.development_plan("v1"):
        if size != "HB":
            continue
        for code in hb_codes(scenario, out):
            if code != now and (current_only or code not in HB_SOURCES):
                continue                                 # records of abandoned code were never in a report
            reps = run.load_reps(scenario, "HB", seeds.DEVELOPMENT, out, code, "v2")
            if not reps:
                continue
            runs.append({"run": f"{scenario} HB", "source": HB_CURRENT if code == now else HB_SOURCES[code], "code": code,
                         "rows": jackknife(lambda x, s=scenario: metrics_v2.summarise_hb(x, s), reps)})
    return runs


def collect(out: Path = run.OUT) -> list[dict]:
    """Every run with intervals on file: version 1's STD and LONG pilots, D11 and the hedged twins, and the HB
    runs of the analytic model, once per code that made them (records of different code are never pooled)."""
    runs = []
    for scenario, size in run.development_plan("v1"):
        if size == "HB":
            continue
        reps, code = _records(scenario, size, out, "v1")
        if reps:
            runs.append({"run": f"{scenario} {size}", "source": "version 1 pilot (PILOT_REPORT.md)", "code": code,
                         "rows": jackknife(lambda x, s=scenario, z=size: metrics.summarise(x, s, z), reps)})
    for scenario in list(cr2.HEDGED_FULL) + list(cr2.TWINS):
        reps, code = _records(scenario, "STD", out, "v2")
        if not reps:
            continue
        rows = jackknife(lambda x, s=scenario: metrics_v2.summarise_spa(x, s), reps)
        if not cr2.is_twin(scenario):
            seen = {(r["metric"], r["what"]) for r in rows}
            rows += [r for r in jackknife(lambda x, s=scenario: metrics.summarise(x, s, "STD"), reps)
                     if (r["metric"], r["what"]) not in seen and r["metric"] != "M3"]
        runs.append({"run": f"{scenario} STD", "source": "version 2 pilot (PILOT_RERUN_REPORT.md)", "code": code, "rows": rows})
    return runs + collect_hb(out)


def _f(x) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4f}"


def build(out: Path = run.OUT, current_hb: bool = False) -> tuple[str, dict]:
    runs = collect_hb(out, current_only=True) if current_hb else collect(out)
    rows = [dict(r, run=v["run"], source=v["source"], code=v["code"]) for v in runs for r in v["rows"]]
    judged = [r for r in rows if r["old_side"] is not None]
    changed = [r for r in judged if r["changed"]]
    widen = [(r["hi"] - r["lo"]) / (r["old_hi"] - r["old_lo"]) for r in rows
             if r["lo"] is not None and r["old_hi"] is not None and r["old_hi"] > r["old_lo"]] or [math.nan]
    L = ["# Manhattan simulation: every interval with the replication as the unit of clustering"
         + (": the HB runs of the code now checked out" if current_hb else ""), "",
         "Written by `python -m manhattan.sim.cluster_ci" + (" --current-hb" if current_hb else "") + "` (the method is "
         "that of session \"6M Manhattan C: dormancy fix and statistical checks\"). **Synthetic data only. Every run here is a "
         "pilot: nothing is decided, and this file changes no pre-registered interval, threshold or verdict rule.** "
         "It shows what the same numbers look like when the small number of replications is allowed for.", "",
         "## Method", "",
         "- **The old interval** is the pre-registered one (SIM_PREREG.md section 4): `mean ± 1.96 · sd/√R` over "
         "per-replication values, or a percentile interval from 2,000 bootstrap resamples of whole replications. "
         "Both already treat a replication as the unit; neither allows for how few there are in a pilot.",
         "- **The corrected interval** keeps the estimate and uses the delete-one-replication jackknife standard "
         "error of that same estimator with a Student-t quantile on `R − 1` degrees of freedom. Where no "
         "replication had an event (an interval printed as 0.000 to 0.000) it gives the exact bound over "
         "replications instead, `1 − 0.025^(1/R)`.",
         "- **One statistic for which the correction is rough.** The expected calibration error counts a bin only "
         "once it holds 200 observations, so leaving a replication out can drop a bin and move the number in a jump. "
         "Its corrected interval is wide for that reason and says only that so few replications do not locate it.",
         "- **Verdict** means the pilot's wording: is the judged end of the interval within or outside the "
         "threshold so far. Rows the small-groups rule leaves unevaluated (fewer than 200 observations) stay "
         "unevaluated.",
         f"- {len(rows)} intervals in {len(runs)} runs; {len(judged)} have a threshold and enough observations to be "
         f"placed; **{len(changed)} change side**. The corrected interval is on average "
         f"{np.mean(widen):.2f} times as wide as the old one (median {np.median(widen):.2f}).", ""]
    L += ["## Results whose verdict changes", ""]
    if changed:
        L += ["| run | records | metric | what | estimate | old interval | corrected interval | threshold | old | corrected | why |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in changed:
            why = "no event in any replication" if r["rule"].startswith("no event") else (
                "an event in every replication" if r["rule"].startswith("an event") else "wider with few replications")
            L.append(f"| {r['run']} | {r['source']} | {r['metric']} | {r['what']} | {_f(r['estimate'])} | {_f(r['old_lo'])} to {_f(r['old_hi'])} | "
                     f"{_f(r['lo'])} to {_f(r['hi'])} | {r['threshold']} | {r['old_side']} | **{r['new_side']}** | {why} |")
    else:
        L.append("None.")
    L += ["", "## Every result with a threshold", "",
          "| run | records | metric | what | R | estimate | old interval | corrected interval | threshold | old | corrected | changes |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if not r["threshold"] or not limits(r["threshold"]):
            continue
        L.append(f"| {r['run']} | {r['source']} | {r['metric']} | {r['what']} | {r['replications']} | {_f(r['estimate'])} | "
                 f"{_f(r['old_lo'])} to {_f(r['old_hi'])} | {_f(r['lo'])} to {_f(r['hi'])} | {r['threshold']} | "
                 f"{r['old_side'] or 'not evaluated'} | {r['new_side'] or 'not evaluated'} | {'**yes**' if r['changed'] else 'no'} |")
    L += ["", "## Every other interval (reported without a threshold)", "",
          "| run | records | metric | what | R | estimate | old interval | corrected interval |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["threshold"] and limits(r["threshold"]):
            continue
        L.append(f"| {r['run']} | {r['source']} | {r['metric']} | {r['what']} | {r['replications']} | {_f(r['estimate'])} | "
                 f"{_f(r['old_lo'])} to {_f(r['old_hi'])} | {_f(r['lo'])} to {_f(r['hi'])} |")
    L.append("")
    summary = {"intervals": len(rows), "runs": len(runs), "judged": len(judged), "changed": len(changed),
               "mean_width_ratio": float(np.mean(widen)), "median_width_ratio": float(np.median(widen)), "rows": rows}
    return "\n".join(L), summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.cluster_ci")
    ap.add_argument("--out", type=Path, default=run.OUT)
    ap.add_argument("--current-hb", action="store_true", help="only the HB runs of the code now checked out")
    ap.add_argument("--name", default="CLUSTERED_INTERVALS", help="base name of the two files written")
    a = ap.parse_args(argv)
    text, summary = build(a.out, a.current_hb)
    (a.out / "v2").mkdir(parents=True, exist_ok=True)
    (a.out / "v2" / f"{a.name}.md").write_text(text, encoding="utf-8")
    (a.out / "v2" / f"{a.name.lower()}.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n",
                                                         encoding="utf-8")
    print(f"wrote {a.out / 'v2' / (a.name + '.md')}: {summary['intervals']} intervals, {summary['changed']} change side")
    return 0


if __name__ == "__main__":
    sys.exit(main())
