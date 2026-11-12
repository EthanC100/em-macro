"""Write the simulation report from the replication records on file.

    python -m manhattan.sim.report                 # results/manhattan_sim/REPORT.md and summary.json

For every scenario run it gives every metric with its estimate, its 95% interval, the threshold and the verdict,
with nothing left out (SIM_PREREG section 9). A run with fewer replications than pre-registered is a **pilot**:
its rows read "pilot: not decided", and the report says so at the top. The selection rule of section 7 is shown
with its numbers but is applied only after a confirmation run.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import criteria as cr
from . import metrics, run, runlog, seeds, world

DEVIATIONS = (
    ("Replications", "Pilot runs use fewer replications than section 6 fixes (2,000 at STD and LONG, 400 at HB). "
                     "No criterion is decided on them. The shortfall per run is in the table below."),
    ("Held-out scenarios", "None was run. Their worlds (H01-H11) are not coded yet; the runner refuses them outside "
                           "a tagged confirmation run and logs the refusal."),
    ("Freeze dates (§2.1)", "Batch b (from 0) is frozen on day 5·⌊504·b/B⌋: equal intervals to the week, first batch "
                            "on day 0, so that weeks line up across families and the last batch has a forward life."),
    ("Reviews and enrolment (§2.5)", "Quarterly reviews are every 63 days from day 63. A family that passed screening "
                                     "is enrolled at the first review on or after its freeze and its test starts "
                                     "with the first week beginning on or after that review. E-ALL enrols at the freeze."),
    ("Settlement lag", "A week's return enters the forward process one week after the week ends (Protocol v3 §6.6), "
                       "so a rejection is dated two weeks after the start of the week that produced it; a rejection "
                       "that would be known only after day 2,520 is not counted."),
    ("Scale (Protocol §2.4)", "Every executable's declared volatility target is 1 a day (the simulated unit), so the "
                              "daily scale floor is 0.5. The EWMA standard deviation is taken about zero with weights "
                              "renormalised over the days available. The weekly scale is √5 times the daily scale on "
                              "the week's first day (which uses earlier days only)."),
    ("SPA sensitivity", "p-values at L/2 and 2L are not computed (Protocol §5.2 says they decide nothing)."),
    ("Edges (§2.3)", "θ_h is drawn independently for each hypothesis that has the edge. Under D06 a family's true "
                     "Sharpe ratio uses the realised mean of σ over its forward days."),
    ("D08", "Each of the 20 pool draws is a full default draw (5% have an edge), so selection also concentrates real "
            "edges; the score is the family portfolio's sample Sharpe ratio on the 1,260 exploration days."),
    ("D09", "An adaptive copy has the copied variant's true edge and correlation 0.9 with its noise; 'best so far' is "
            "by sample Sharpe ratio on the window the channel sees, among the hypothesis's frozen and adaptive "
            "variants. M11's truth label requires the adaptive variants to be null as well."),
    ("D10", "Retention multiplies positive edges only; variants with no edge keep a mean of −0.2 forward."),
    ("D11", "One core factor for the whole programme with daily volatility 1 and Sharpe ratio 0.6; one β path per "
            "hypothesis, started at 0.5; hedge trading cost 0 (returns are net by assumption, §10.6); no hedge in a "
            "family's first 252 days."),
    ("M3 Romano-Wolf", "The family-wise rate is the share of families with at least one no-edge variant in which the "
                       "step-down at 0.05 names a no-edge variant."),
    ("M5", "A component's wealth is its tracking wealth from the freeze over its whole forward life, for every "
           "family (enrolled or not)."),
    ("M6", "Years to formal support are counted from the freeze. Forward power's denominator is every family that is "
           "not forward-null and was frozen before day 630, enrolled or not."),
    ("HB: estimates and covariances (Protocol §7.1)", "Standard errors from a joint stationary bootstrap per batch "
        "(199 resamples). Correlations are the sample correlation of returns over common dates times the share of "
        "common dates, shrunk half-way to zero: one joint bootstrap across batches is not possible, their windows "
        "differ. A hypothesis has a forward estimate once its family has 63 forward days."),
    ("HB: mechanism classes", "Three classes assigned at random at freeze (the truth has none, §2.3)."),
    ("HB: sampling coordinates", "δ_h, A_f and ρ_f are sampled through exact changes of variable (quantile tables for "
        "the two mixtures; a standardised logit for retention) because the model does not mix in its original "
        "coordinates. The priors are unchanged up to the tables' interpolation error."),
    ("HB: a review needs all six fits", "If any of S0-S5 fails the gate (R̂ ≤ 1.01 for every parameter, effective "
        "sample size ≥ 400, no divergence) the review is 'model not converged' and changes no tier."),
    ("HB: dormancy forecast (Protocol §9.1)", "PP_f is computed by a normal update of each model's current posterior "
        "with simulated future records, not by refitting the model on each simulated future; not evaluated at the "
        "last date."),
    ("HB: naive estimate (M9)", "The largest sample Sharpe ratio among the family's variants, each over all its data "
                                "up to the evaluation date."),
    ("Unlogged debug runs", "Before the runner existed, replication 0 of D01 and of P3 at STD was run once each on "
                            "uncommitted code; this is recorded as a note in runs.jsonl."),
)


def fmt(x, digits=4) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "-"
    return f"{x:.{digits}f}"


def table(rows: list[metrics.Row]) -> str:
    out = ["| metric | what | estimate | 95% interval | n | threshold | required here | verdict |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ci = f"{fmt(r.lo)} to {fmt(r.hi)}" if r.lo is not None and r.lo == r.lo else "-"
        out.append(f"| {r.metric} | {r.what} | {fmt(r.estimate)} | {ci} | {r.n} | {r.threshold or '-'} | "
                   f"{'yes' if r.required else 'no'} | {r.verdict} |")
    return "\n".join(out)


def collect(out: Path = run.OUT) -> dict:
    """{(scenario, size): [replication records]} for every development run on file, most common code only."""
    found = {}
    for scenario, size in run.development_plan():
        reps = run.load_reps(scenario, size, seeds.DEVELOPMENT, out)
        if not reps:
            continue
        codes = Counter(r["code"] for r in reps)
        code = codes.most_common(1)[0][0]
        found[(scenario, size)] = {"reps": [r for r in reps if r["code"] == code], "code": code,
                                   "other_code_reps": len(reps) - codes[code]}
    return found


def build(out: Path = run.OUT) -> tuple[str, dict]:
    found = collect(out)
    log = runlog.read(out / "runs.jsonl")
    sha = seeds.prereg_hash()
    summary = {"prereg_sha256": sha, "protocol_sha256": runlog.protocol_hash(), "runs": {}}
    pilot = any(len(v["reps"]) < cr.REPLICATIONS[size] for (_, size), v in found.items()) or \
        len(found) < len(run.development_plan())
    L = []
    L.append("# Manhattan simulation: " + ("PILOT report (nothing here is decided)" if pilot else "development report"))
    L.append("")
    L.append(f"Written {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `python -m manhattan.sim.report`. "
             "**Synthetic data only: nothing in this file is market evidence.**")
    L.append("")
    L.append(f"- Pre-registration: `docs/manhattan/SIM_PREREG.md`, SHA-256 `{sha}` (never edited).")
    L.append(f"- Method under test: `docs/manhattan/PROTOCOL_v3.md` 3.0.0, SHA-256 `{summary['protocol_sha256']}` "
             "(the pre-rename hash named in SIM_PREREG.md is the same text before the project was renamed).")
    L.append(f"- Development scenarios only (seed branch 0). Held-out scenarios run: **none**.")
    if pilot:
        L.append("- **This is a pilot.** Replication counts are below those pre-registered, so every verdict below "
                 "reads \"pilot: not decided\". \"within\" or \"outside\" only says where the interval sits so far. "
                 "No method is selected, no claim is enabled, and `claims.enabled` stays false.")
    L.append("")
    L.append("## Runs and shortfall")
    L.append("")
    L.append("| scenario | size | replications run | pre-registered | shortfall | code | seconds per replication |")
    L.append("|---|---|---|---|---|---|---|")
    for scenario, size in run.development_plan():
        need = cr.REPLICATIONS[size]
        v = found.get((scenario, size))
        if v is None:
            L.append(f"| {scenario} | {size} | 0 | {need} | {need} | - | - |")
            continue
        n = len(v["reps"])
        secs = sum(r["seconds"] for r in v["reps"]) / n
        L.append(f"| {scenario} | {size} | {n} | {need} | {max(0, need - n)} | `{v['code']}` | {secs:.0f} |")
    L.append("")
    total = sum(max(0, cr.REPLICATIONS[size] - len(found.get((s, size), {"reps": []})["reps"]))
                * (sum(r["seconds"] for r in found[(s, size)]["reps"]) / len(found[(s, size)]["reps"]) if (s, size) in found else 0)
                for s, size in run.development_plan())
    L.append(f"Remaining cost of the development runs that have a timing above: about **{total / 3600:.0f} CPU-hours** "
             "(one core; divide by the number of cores). Held-out scenarios are extra.")
    L.append("")
    L.append("## Results by scenario")
    for (scenario, size), v in found.items():
        scn = world.SCENARIOS[scenario]
        rows = metrics.summarise_hb(v["reps"], scenario) if size == "HB" else metrics.summarise(v["reps"], scenario, size)
        L.append("")
        L.append(f"### {scenario} at {size}: {scn.title} ({len(v['reps'])} of {cr.REPLICATIONS[size]} replications)")
        L.append("")
        L.append(table(rows))
        summary["runs"][f"{scenario}_{size}"] = {"replications": len(v["reps"]), "code": v["code"],
                                                 "rows": [r.as_dict() for r in rows]}
    have = {s: found[(s, "STD")]["reps"] for s in cr.POWER_SCENARIOS if (s, "STD") in found}
    L.append("")
    L.append("## Selection rule (SIM_PREREG section 7): numbers only")
    L.append("")
    if len(have) == len(cr.POWER_SCENARIOS):
        d = metrics.power_difference(have)
        summary["selection_numbers"] = d
        L.append("| scenario | screening power, candidate (i) | candidate (ii) |")
        L.append("|---|---|---|")
        for sid, p in d["by_scenario"].items():
            L.append(f"| {sid} | {p['i']:.3f} | {p['ii']:.3f} |")
        L.append(f"| **average** | **{d['power_i']:.3f}** | **{d['power_ii']:.3f}** |")
        L.append("")
        L.append(f"Difference (i) − (ii): {d['difference']:+.3f}, 95% bootstrap interval {d['lo']:+.3f} to {d['hi']:+.3f}. "
                 f"The rule chooses (i) only if both are eligible, the difference is at least {cr.SELECTION_MARGIN} and "
                 "the interval excludes zero; otherwise (ii). **The choice is made once, after the first confirmation "
                 "run with an eligible candidate; it is not made here.**")
    else:
        L.append("Not all of P1-P4 have been run.")
    L.append("")
    L.append("## Criterion V10(a): blind statistics with and without the adaptive channel")
    L.append("")
    v10 = out / "v10a.json"
    if v10.exists():
        res = json.loads(v10.read_text(encoding="utf-8"))
        summary["v10a"] = res
        for sid, v in res["scenarios"].items():
            L.append(f"- {sid}: designated blind p-values and e-values of {v['families_compared']} families "
                     f"(first {res['batches']} batches of {res['replications']} replications at STD) are "
                     f"**{'bit-for-bit identical' if v['identical'] else 'NOT identical'}** with and without the "
                     "adaptive channel.")
        L.append("")
        L.append("This is a property of the code (the adaptive channel has its own random stream and never touches "
                 "the frozen grid), so a few batches show it as well as 2,000 replications would; "
                 "`tests/test_manhattan_sim_pipeline.py` checks it on every test run.")
    else:
        L.append("Not checked yet (`python -m manhattan.sim.run --v10a`).")
    L.append("")
    L.append("## Deviations from, and readings of, SIM_PREREG.md")
    L.append("")
    L.append("Every place where the code had to fix a detail the pre-registration leaves open, or departs from it.")
    L.append("")
    for name, text in DEVIATIONS:
        L.append(f"- **{name}.** {text}")
    L.append("")
    L.append("## Every run on record")
    L.append("")
    L.append("From `results/manhattan_sim/runs.jsonl` (start and end records; a start with no end is an abandoned run).")
    L.append("")
    L.append("| time (UTC) | run | event | scenario | size | label | held-out set | replications | status | commit |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in log:
        reps = r.get("replications", {})
        L.append(f"| {r.get('time_utc', '')} | {r.get('run_id', '')} | {r.get('event', '')} | {r.get('scenario', '')} | "
                 f"{r.get('size', '')} | {r.get('label', '')} | {r.get('heldout_set') or '-'} | "
                 f"{reps.get('completed', '-')}/{reps.get('requested', '-')} | {r.get('status', '')} | "
                 f"`{str(r.get('commit', ''))[:7]}`{' (dirty)' if r.get('dirty') else ''} |")
    refused = [r for r in log if r.get("status") == "refused"]
    L.append("")
    L.append(f"Held-out runs refused: {len(refused)}. Held-out runs made: 0.")
    L.append("")
    return "\n".join(L), summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.report")
    ap.add_argument("--out", type=Path, default=run.OUT)
    ap.add_argument("--name", default="REPORT.md")
    a = ap.parse_args(argv)
    text, summary = build(a.out)
    (a.out / a.name).write_text(text, encoding="utf-8")
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    print(f"wrote {a.out / a.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
