"""Write the report of the parts SIM_PREREG_v2 changed, from the replication records on file.

    python -m manhattan.sim.report_v2                                  # results/manhattan_sim/v2/REPORT.md
    python -m manhattan.sim.report_v2 --name PILOT_RERUN_REPORT.md     # the same report under another name

It covers D11 and its hedged twins (the SPA test with the hedge re-estimated in every resample, beside the 3.0
test and an oracle on the same resamples) and every HB scenario (the analytic hierarchical model). Every metric
is given with its estimate, its 95% interval, the threshold and the verdict; a run below its replication count
is a **pilot** and its verdicts read "pilot: not decided". Version 1's report (``manhattan.sim.report``) covers
everything else and is not changed by this one.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from manhattan import prereg_v2

from . import criteria as cr
from . import criteria_v2 as cr2
from . import hb_v2, metrics, metrics_v2, pipeline_v2, run, runlog, seeds, world
from .report import fmt, table

READINGS = (
    ("Seeds and worlds", "Version 1's master seed and stream keys, so D11 and the HB scenarios are the worlds "
                         "version 1 drew. A twin draws from its version 1 scenario's streams: its true hedged "
                         "returns are those of that scenario's version 1 run, and its oracle column reproduces that "
                         "run's SPA counts replication by replication."),
    ("D11 and the twins: the hedge layer", "One core factor for the whole programme (daily volatility 1, annualised "
        "Sharpe ratio 0.6); one β path per hypothesis, a random walk from 0.5 with annual standard deviation 0.3; "
        "hedge cost 0; no hedge in a family's first 252 days. The unhedged returns are rebuilt from the same random "
        "streams the world used; a test checks that hedging them reproduces the family's returns exactly."),
    ("Hedge-aware SPA (Protocol 3.1 §5.1)", "The pseudo-series of a resample is the 756 actual days before the "
        "reserve window followed by the resampled window. Each family's three tests (hedge-aware, 3.0 on the "
        "estimated hedge, 3.0 on the true hedged returns) start from the same generator state, so they see the same "
        "block draws; the number of resamples (999, then 9,999 when p ≤ 0.10) is decided by each test's own p-value."),
    ("Twins", "The three SPA tests and Romano-Wolf at 0.05 only: no screening, no forward test (those belong to the "
              "version 1 scenario). D09a and D09b have no twin."),
    ("HB: estimates", "Annualised sample Sharpe ratios of the family portfolio on the reserve window and on the "
                      "forward record (63 forward days at least). Standard errors from a joint stationary bootstrap "
                      "per batch (199 resamples)."),
    ("HB: the common share r", "For every pair of families with a forward estimate, the sample correlation of the "
        "two forward return series over common dates times the number of common dates over the geometric mean of the "
        "two lengths; r is the average over pairs, floored at 0. It is the only dependence between families the model "
        "is given."),
    ("HB: mechanism classes", "Three classes assigned at random at freeze (the truth has none)."),
    ("HB: when a fit is used", "At most 1% of the posterior mass of μ_A on the two end nodes of its grid; a review "
                               "needs all six fits. There is no sampler and no convergence diagnostic."),
    ("HB: dormancy forecast", "Version 1's normal-update approximation (no refit), fed with 200 draws of θ_f per "
                              "family and model from the closed-form posterior; not evaluated at the last date."),
    ("HB: dormancy rule", "Protocol 3.1 §9.1 (the forward-record rule, a pre-adoption change): dormant when the "
                          "forecast PP^max and the one-sided p-value p^F of the family's own forward record against an "
                          "edge of θ_min are both below 0.05 at two consecutive reviews (p^F is 1 until the "
                          "family has 252 forward days); reactivated when either is at least 0.15. p^F is computed "
                          "from the forward Sharpe estimate and standard error handed to the model. At the last review "
                          "there is no forecast, so no family becomes dormant there; a dormant family is reactivated "
                          "there if p^F ≥ 0.15. A review is \"written\" for every family that is not dormant both "
                          "before and after the review."),
    ("HB: who reaches Statistically supported", "A family counts from the first review at which it holds the "
        "tier, whether or not it leaves later. Its true Sharpe ratio is that of the family portfolio over its "
        "forward life (SIM_PREREG section 2.4). The table reads the state at years 2, 4, 7 and 10."),
    ("HB: review dates", "Every 63 trading days, 40 reviews (SIM_PREREG_v2 amendment 1: the cadence production "
                         "uses, in place of version 1's four dates). M7 and M9 are read at years 2, 4, 7 and 10; "
                         "M12 is counted over all 40 reviews; M8 is the state after the last. Consecutive reviews "
                         "are a quarter apart. Records made with any other step are refused."),
    ("HB: naive estimate (M9)", "Version 1's: the largest sample Sharpe ratio among the family's variants, each over "
                                "all its data up to the evaluation date."),
    ("Timing", "Seconds are wall-clock per replication inside a worker and are inflated whenever more jobs than "
               "cores run at once."),
)


def v2_plan() -> list[tuple[str, str]]:
    return [(s, z) for s, z in run.development_plan("v2") if run.route(s, z, "v2") == "v2"]


def collect(out: Path = run.OUT) -> dict:
    """{(scenario, size): records} for every version 2 run on file: the records made by the code now checked
    out, or, when there are none (a report built on another checkout), by the most common code. Records of
    different code are never pooled; how many were left out is kept."""
    found = {}
    for scenario, size in v2_plan():
        path = run.reps_path(scenario, size, seeds.DEVELOPMENT, out, "v2")
        rows = []
        for p_, opener in ((path, open), (path.with_suffix(".jsonl.gz"), gzip.open)):
            if p_.exists():
                with opener(p_, "rt", encoding="utf-8") as f:
                    rows += [json.loads(line) for line in f if line.strip()]
        if not rows:
            continue
        n_all = len(rows)
        if size == "HB":            # another review calendar answers another question: never pooled, never reported here
            rows = [r for r in rows if r.get("review_step") == hb_v2.REVIEW_STEP]
            if not rows:
                continue
        codes = Counter(r["code"] for r in rows)
        now = run.code_hash(size, version="v2")
        code = now if now in codes else codes.most_common(1)[0][0]
        reps = [r for r in run.load_reps(scenario, size, seeds.DEVELOPMENT, out, code, "v2")
                if size != "HB" or r.get("review_step") == hb_v2.REVIEW_STEP]
        if size == "HB":
            hb_v2.require_review_step(reps, f"{scenario} at HB")
        found[(scenario, size)] = {"reps": reps, "code": code, "other_code_reps": n_all - codes[code]}
    return found


def _secs(reps: list[dict]) -> float:
    return sum(r["seconds"] for r in reps) / len(reps)


def cost_table(found: dict, out: Path) -> tuple[list[str], dict]:
    """Remaining CPU-hours of the whole development programme under version 2, from the seconds on file:
    version 1's unchanged runs from version 1's pilot records, the changed runs from this report's records."""
    rows, tot = [], {}
    groups = (("version 1 code: STD and LONG scenarios other than D11", "v1"),
              ("version 2 code: D11, full pipeline with the hedge-aware SPA test", "D11"),
              ("version 2 code: nine hedged twins, SPA only", "twin"),
              ("version 2 code: HB scenarios, analytic model", "HB"))
    for label, key in groups:
        left = hours = runs = timed = 0
        for scenario, size in run.development_plan("v2"):
            route = run.route(scenario, size, "v2")
            kind = "v1" if route == "v1" else ("twin" if cr2.is_twin(scenario) else ("HB" if size == "HB" else "D11"))
            if kind != key:
                continue
            reps = run.load_reps(scenario, size, seeds.DEVELOPMENT, out, version=route) if route == "v1" \
                else found.get((scenario, size), {"reps": []})["reps"]
            need = cr2.replications(scenario, size)
            runs += 1
            left += max(0, need - len(reps))
            if reps:
                timed += 1
                hours += max(0, need - len(reps)) * _secs(reps) / 3600
        rows.append(f"| {label} | {runs} | {left} | {timed} of {runs} | {hours:.0f} |")
        tot[key] = {"runs": runs, "replications_left": left, "timed_runs": timed, "cpu_hours": hours}
    total = sum(v["cpu_hours"] for v in tot.values())
    rows.append(f"| **all development runs** | {sum(v['runs'] for v in tot.values())} | "
                f"{sum(v['replications_left'] for v in tot.values())} | | **{total:.0f}** |")
    tot["total_cpu_hours"] = total
    return rows, tot


def build(out: Path = run.OUT) -> tuple[str, dict]:
    found = collect(out)
    log = runlog.read(out / "runs.jsonl")
    sha1, sha2, sha31 = seeds.prereg_hash(), prereg_v2.prereg_v2_hash(), prereg_v2.protocol_v31_hash()
    summary = {"prereg_sha256": sha1, "prereg_v2_sha256": sha2, "protocol_v31_sha256": sha31,
               "protocol_sha256": runlog.protocol_hash(), "runs": {}}
    plan = v2_plan()
    pilot = len(found) < len(plan) or any(len(v["reps"]) < cr2.replications(s, z) for (s, z), v in found.items())
    L = ["# Manhattan simulation, the parts changed by Protocol v3.1: "
         + ("PILOT report (nothing here is decided)" if pilot else "development report"), ""]
    L.append(f"Written {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `python -m manhattan.sim.report_v2`. "
             "**Synthetic data only: nothing in this file is market evidence.**")
    L.append("")
    L.append(f"- Pre-registration, version 2 (the changed parts): `docs/manhattan/SIM_PREREG_v2.md`, SHA-256 `{sha2}`.")
    L.append(f"- Pre-registration, version 1 (everything else, and the seeds): `docs/manhattan/SIM_PREREG.md`, SHA-256 `{sha1}` (never edited).")
    L.append(f"- Method under test here: `docs/manhattan/PROTOCOL_v3.1.md` 3.1.0, SHA-256 `{sha31}`. Both v2 files are drafts "
             "until Ethan adopts them.")
    L.append("- Development scenarios only (seed branch 0). Held-out scenarios run: **none**.")
    stale = sorted({(r["options"].get("prereg_v2_sha256"), r["options"].get("protocol_v31_sha256")) for r in log
                    if r.get("options", {}).get("prereg_version") == "v2"} - {(sha2, sha31)})
    if stale:
        L.append("- **Some runs below were made under an earlier draft of the version 2 files** (hashes "
                 + "; ".join(f"`{a[:12]}` / `{b[:12]}`" for a, b in stale)
                 + "): the text changed after them. Their replication records carry the hash of the code that made "
                   "them, and only records of the code now checked out are counted.")
    if pilot:
        L.append("- **This is a pilot.** Replication counts are below those pre-registered, so every verdict below "
                 "reads \"pilot: not decided\". \"within\" or \"outside\" only says where the interval sits so far. "
                 "No method is selected, no claim is enabled, and `claims.enabled` stays false.")
    L += ["", "## Runs and shortfall", "",
          "| scenario | size | what | replications run | pre-registered | shortfall | code | seconds per replication |",
          "|---|---|---|---|---|---|---|---|"]
    for scenario, size in plan:
        need = cr2.replications(scenario, size)
        what = "three SPA tests only" if cr2.is_twin(scenario) else ("analytic model, tiers, dormancy" if size == "HB"
                                                                     else "full pipeline, hedge-aware SPA")
        v = found.get((scenario, size))
        if v is None:
            L.append(f"| {scenario} | {size} | {what} | 0 | {need} | {need} | - | - |")
            continue
        n = len(v["reps"])
        L.append(f"| {scenario} | {size} | {what} | {n} | {need} | {max(0, need - n)} | `{v['code']}` | {_secs(v['reps']):.0f} |")
    stale_reps = sum(v["other_code_reps"] for v in found.values())
    if stale_reps:
        L += ["", f"{stale_reps} replication records on file were made by earlier code (the model, then the "
                  "dormancy rule, then the review dates changed while the draft was revised) and are **not counted** "
                  "anywhere in this report: records of different code, or of another review calendar, are never pooled."]
    # ---------------------------------------------------------------- 1. the SPA test with an estimated hedge
    L += ["", "## 1. The SPA test where the hedge is estimated", "",
          "Share of families with no edge rejected at the 0.05 level (the bound on the upper end is 0.06), by three "
          "tests on the **same** resamples: the 3.0 test on the hedged returns as given, the 3.1 test that "
          "re-estimates the hedge in every resample, and the 3.0 test on the true hedged returns, which no real "
          "analysis has. The last column is version 1's own run of the scenario on file (for D11: the 3.0 test on "
          "the estimated hedge; for a twin: its version 1 scenario, whose returns need no hedge).", "",
          "| scenario | replications | 3.0 test, estimated hedge | **3.1 test, hedge re-estimated** | oracle | 3.1 minus oracle (paired) | version 1 run on file |",
          "|---|---|---|---|---|---|---|"]
    spa_rows = {}
    for scenario, size in plan:
        if size == "HB" or (scenario, size) not in found:
            continue
        reps = found[(scenario, size)]["reps"]
        rows = metrics_v2.summarise_spa(reps, scenario)
        spa_rows[scenario] = rows
        pick = lambda text: next(r for r in rows if r.what == text)
        cell = lambda r: f"{fmt(r.estimate)} ({fmt(r.lo)} to {fmt(r.hi)})"
        base = pipeline_v2.stream_id(scenario)
        v1 = run.load_reps(base, "STD", seeds.DEVELOPMENT, out)
        v1cell = "-"
        if v1:
            e, lo, hi = metrics.mean_ci(metrics.per_rep_share(v1, "m3_p0.05_num", "n_reserve_null"))
            v1cell = f"{fmt(e)} ({fmt(lo)} to {fmt(hi)}), {len(v1)} replications"
        L.append(f"| {scenario} | {len(reps)} | {cell(pick(metrics_v2.NAME['v30'] + ': SPA size at 0.05'))} | "
                 f"**{cell(pick(metrics_v2.NAME['v31'] + ': SPA size at 0.05'))}** | "
                 f"{cell(pick(metrics_v2.NAME['oracle'] + ': SPA size at 0.05'))} | "
                 f"{cell(pick('paired difference at 0.05: ' + metrics_v2.NAME['v31'] + ' minus the oracle'))} | {v1cell} |")
    for scenario, rows in spa_rows.items():
        v = found[(scenario, "STD")]
        scn = pipeline_v2.scenario(scenario)
        L += ["", f"### {scenario} at STD: {scn.title} ({len(v['reps'])} of {cr2.replications(scenario, 'STD')} replications)", ""]
        summary["runs"][f"{scenario}_STD"] = {"replications": len(v["reps"]), "code": v["code"], "rows": [r.as_dict() for r in rows]}
        if not cr2.is_twin(scenario):
            full = metrics.summarise(v["reps"], scenario, "STD")
            summary["runs"][f"{scenario}_STD"]["pipeline_rows"] = [r.as_dict() for r in full]
            L += ["The three SPA tests side by side:", "", table(rows), "",
                  "Every metric of the pipeline, with the hedge-aware p-values as the p-values of record:", "", table(full)]
        else:
            L.append(table(rows))
    # ---------------------------------------------------------------- 2. the analytic model
    L += ["", "## 2. The analytic hierarchical model (HB scenarios)"]
    for scenario, size in plan:
        if size != "HB" or (scenario, size) not in found:
            continue
        v = found[(scenario, size)]
        rows = metrics_v2.summarise_hb(v["reps"], scenario)
        summary["runs"][f"{scenario}_HB"] = {"replications": len(v["reps"]), "code": v["code"], "rows": [r.as_dict() for r in rows]}
        L += ["", f"### {scenario} at HB: {world.SCENARIOS[scenario].title} ({len(v['reps'])} of {cr.REPLICATIONS['HB']} replications)",
              "", table(rows)]
    # ---------------------------------------------------------------- 2b, 2c: dormancy and the tier, side by side
    hb_runs = [(s_, v) for (s_, z), v in found.items() if z == "HB"]
    cell = lambda e, d=3: f"{fmt(e[0], d)} ({fmt(max(e[1], 0.0), d)} to {fmt(e[2], d)})"       # shares and counts: never below 0
    att = {s_: metrics_v2.attention(v["reps"]) for s_, v in hb_runs}
    if any(att.values()):
        L += ["", "### Dormancy under Protocol 3.1 §9.1: what it retires and what it leaves to review (candidate (i))", "",
              "Premature elimination is M8 (bound 0.10 on the upper end of the interval). The other columns have no "
              "threshold: they are the attention the rule saves. A review is written for every family that is not "
              "dormant both before and after a review.", "",
              "| scenario | replications | premature elimination (M8) | families with a true edge dormant at the end | "
              "families with no edge dormant at the end | families dormant at the end, of 240 | reviews written per "
              "replication | family-reviews per replication |", "|---|---|---|---|---|---|---|---|"]
        summary["dormancy"] = {}
        for s_, v in hb_runs:
            a = att[s_]
            if not a:
                continue
            m8 = metrics.ratio_ci(metrics.col(v["reps"], "m8_num_i"), metrics.col(v["reps"], "m8_den_i"))
            n_edge = int(metrics.col(v["reps"], "m8_den_i").sum())
            summary["dormancy"][s_] = {"m8": m8, "n_edge": n_edge, **a}
            L.append(f"| {s_} | {len(v['reps'])} | {cell(m8) if n_edge else '- (no family has an edge)'} | "
                     f"{cell(a['edge_dormant_share']) if n_edge else '-'} | {cell(a['null_dormant_share'])} | "
                     f"{cell(a['dormant_end'], 1)} | {cell(a['written'], 1)} | {a['family_reviews']:.0f} |")
    power = {s_: metrics_v2.tier_power(v["reps"]) for s_, v in hb_runs}
    if any(power.values()):
        L += ["", "### Who reaches Statistically supported, by true Sharpe ratio (candidate (i); reported, no threshold)", "",
              "Among the families with a true edge that were frozen before the date, the share that held the tier at "
              "that date or an earlier one. The Sharpe ratio is the true one of the family portfolio, hedged and net. "
              "Entry needs Π^min ≥ 0.80 (the most cautious of six models), a positive forward mean, 504 forward days "
              "(252 if Romano-Wolf named a variant on the reserve) and the tier Promising. A dormant family is not "
              "evaluated. Each cell: the share, its 95% interval over replications, and the number of families it "
              "rests on; a cell with few families says little.", ""]
        summary["tier_power"] = {}
        for s_, v in hb_runs:
            pw = power[s_]
            if not pw:
                continue
            years = [int(y) for y in v["reps"][0]["eval_years"]]
            summary["tier_power"][s_] = {b: {str(y): c for y, c in row.items()} for b, row in pw.items()}
            if not any(c[3] for row in pw.values() for c in row.values()):
                L += [f"**{s_}: {world.SCENARIOS[s_].title}** ({len(v['reps'])} replications): no family has an edge.", ""]
                continue
            L += [f"**{s_}: {world.SCENARIOS[s_].title}** ({len(v['reps'])} replications)", "",
                  "| true Sharpe ratio | " + " | ".join(f"by year {y}" for y in years) + " |", "|---|" + "---|" * len(years)]
            for b, row in pw.items():
                cells = [f"{fmt(row[y][0], 2)} ({fmt(row[y][1], 2)} to {fmt(row[y][2], 2)}), {row[y][3]}" if row[y][3]
                         else "-" for y in years]
                L.append(f"| {b} | " + " | ".join(cells) + " |")
            L.append("")
    # ---------------------------------------------------------------- 3. cost
    rows, tot = cost_table(found, out)
    summary["cost"] = tot
    L += ["", "## 3. Cost of the whole development programme under version 2", "",
          "Replications still to run times the seconds per replication on file (one core). Seconds measured while "
          "more jobs than cores were running are too high; the runbook gives timings on an idle core.", "",
          "| part | runs | replications still to run | runs with a timing | CPU-hours |", "|---|---|---|---|---|"] + rows
    hb = [v for (s, z), v in found.items() if z == "HB"]
    if hb:
        fits = [x for v in hb for r in v["reps"] for x in (r["quarterly"]["six_fits_seconds"] if "quarterly" in r
                                                       else [y["six_fits_seconds"] for y in r["reviews"].values()])]
        model = [r["model_seconds"] for v in hb for r in v["reps"]]
        summary["cost"]["six_fits_seconds_mean"] = sum(fits) / len(fits)
        L += ["", f"The six fits of one review took {sum(fits) / len(fits):.1f} seconds on average over {len(fits)} reviews "
                  f"(so {sum(fits) / len(fits) / 6:.2f} seconds a fit), and the model's share of a replication "
                  f"{sum(model) / len(model):.0f} seconds. The sampled model of 3.0 did not finish one replication in "
                  "2 hours 31 minutes of CPU time at a fifth of its budget."]
    # ---------------------------------------------------------------- 4. the adaptive channel
    L += ["", "## 4. The adaptive channel on the reserve: the evidence on file", ""]
    s1 = out / "summary.json"
    m11 = None
    if s1.exists():
        v1sum = json.loads(s1.read_text(encoding="utf-8"))
        m11 = next((r for r in v1sum.get("runs", {}).get("D09b_STD", {}).get("rows", []) if r["metric"] == "M11"), None)
    if m11:
        summary["d09b_m11"] = {k: m11[k] for k in ("estimate", "lo", "hi", "n")}
        L.append(f"Version 1's pilot of D09b ({m11['n']} replications): the SPA test recomputed on the full set after "
                 f"three adaptive rounds on the reserve rejects **{fmt(m11['estimate'])} ({fmt(m11['lo'])} to {fmt(m11['hi'])})** "
                 "of families with no edge at the 0.05 level. This is the evidence Protocol 3.1 §5.3 cites for the rule "
                 "that adaptive-channel families carry zero evidential weight on the reserve. The rule is enforced by "
                 "`tests/test_manhattan_adaptive_weight.py` (criterion V14); D09b itself is unchanged by version 2 and "
                 "is decided, with V10(b), on the full run.")
    else:
        L.append("Version 1's summary is not on file.")
    # ---------------------------------------------------------------- readings and runs
    L += ["", "## Readings of SIM_PREREG_v2.md", "", "Every place where the code had to fix a detail the text leaves open.", ""]
    L += [f"- **{name}.** {text}" for name, text in READINGS]
    L += ["", "## Runs of the changed parts on record", "",
          "From `results/manhattan_sim/runs.jsonl`: every run made with `--prereg v2`, and every note written during "
          "this revision (a start with no end is an abandoned run).", "",
          "| time (UTC) | run | event | scenario | size | label | replications | status | commit | v2 hash |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in log:
        opt = r.get("options", {})
        if opt.get("prereg_version") != "v2" and not (r.get("event") == "note" and r.get("prereg_version") == "v2"):
            continue
        reps = r.get("replications", {})
        L.append(f"| {r.get('time_utc', '')} | {r.get('run_id', '')} | {r.get('event', '')} | {r.get('scenario', '')} | "
                 f"{r.get('size', '')} | {r.get('label', '')} | {reps.get('completed', '-')}/{reps.get('requested', '-')} | "
                 f"{r.get('status', '')} | `{str(r.get('commit', ''))[:7]}`{' (dirty)' if r.get('dirty') else ''} | "
                 f"`{str(opt.get('prereg_v2_sha256', r.get('prereg_v2_sha256', '')))[:8]}` |")
    notes = [r for r in log if r.get("event") == "note" and r.get("prereg_version") == "v2"]
    if notes:
        L += ["", "Notes:", ""] + [f"- `{r['run_id']}` ({r['scenario']}, {r['size']}): {r['note']}" for r in notes]
    refused = [r for r in log if r.get("status") == "refused"]
    L += ["", f"Held-out runs refused: {len(refused)}. Held-out runs made: 0.", ""]
    return "\n".join(L), summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.report_v2")
    ap.add_argument("--out", type=Path, default=run.OUT)
    ap.add_argument("--name", default="REPORT.md")
    a = ap.parse_args(argv)
    text, summary = build(a.out)
    (a.out / "v2").mkdir(parents=True, exist_ok=True)
    (a.out / "v2" / a.name).write_text(text, encoding="utf-8")
    (a.out / "v2" / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    print(f"wrote {a.out / 'v2' / a.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
