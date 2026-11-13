"""Session 6M: time and cost of the full pre-registered simulation on three kinds of machine (COMPUTE_OPTIONS.md).
Estimates only: nothing is bought, nothing is dispatched.

    python compute_options.py BENCHMARK.json OUT.md
"""
import json, sys
import numpy as np
from manhattan.sim import criteria_v2, run, seeds

bench = json.load(open(sys.argv[1]))
out_path = sys.argv[2]
K = bench["kinds"]
EFF = bench["efficiency_same_replication"]
W = bench["workers"]

# ---- seconds per replication on file (pilots, measured under load), and their ratio to an idle core here
def family(scenario, size, version):
    if version == "v1":
        return "v1 LONG" if size == "LONG" else "v1 STD"
    return "twin" if criteria_v2.is_twin(scenario) else ("HB" if size == "HB" else "D11")

rows = []
for scenario, size in run.development_plan("v2"):
    v = run.route(scenario, size, "v2")
    reps = run.load_reps(scenario, size, seeds.DEVELOPMENT, version=v, code=run.code_hash(size, version=v))
    need = criteria_v2.replications(scenario, size)
    rows.append(dict(scenario=scenario, size=size, version=v, fam=family(scenario, size, v), need=need, on_file=len(reps),
                     pilot_sec=float(np.mean([r["seconds"] for r in reps])) if reps else None))
ratio = {}
for k, b in K.items():
    s, z = k.split()
    r = next(x for x in rows if x["scenario"] == s and x["size"] == z)
    ratio.setdefault(r["fam"], []).append(b["alone_wall"] / r["pilot_sec"])
ratio = {f: float(np.mean(v)) for f, v in ratio.items()}
for r in rows:
    key = f"{r['scenario']} {r['size']}"
    r["idle_sec"] = K[key]["alone_wall"] if key in K else r["pilot_sec"] * ratio[r["fam"]]
    r["cpu_h_all"] = r["need"] * r["idle_sec"] / 3600
    r["cpu_h_left"] = max(0, r["need"] - r["on_file"]) * r["idle_sec"] / 3600

FAMS = (("v1 STD", "version 1's code: 15 runs at STD"), ("v1 LONG", "version 1's code: 2 runs at LONG"),
        ("D11", "D11 with the hedge-aware test"), ("twin", "nine hedged twins, SPA only"), ("HB", "five HB scenarios: analytic model, tiers, dormancy"))
tot_all = sum(r["cpu_h_all"] for r in rows)
tot_left = sum(r["cpu_h_left"] for r in rows)
sec = lambda f: [r["idle_sec"] for r in rows if r["fam"] == f]

# ---- the held-out confirmation run: not coded, so extrapolated from the development runs of the same size
mean_std = float(np.mean(sec("v1 STD"))); mean_long = float(np.mean(sec("v1 LONG"))); mean_hb = float(np.mean(sec("HB"))); d11 = sec("D11")[0]
held = [("13 held-out runs at STD (H01, H02a, H02b, H02c, H03, H04, H05, H06, H08m, H08x, H10, H11 by version 1's pipeline; H12 at D11's cost)",
         (12 * mean_std + d11) * 2000 / 3600),
        ("1 held-out run at LONG (H11)", mean_long * 2000 / 3600),
        ("7 held-out runs at HB (H03, H05, H06, H07, H09, H10, H11)", 7 * mean_hb * 400 / 3600)]
held_tot = sum(h for _, h in held)

L = ["# Running the full pre-registered simulation: time and cost on three kinds of machine", "",
     "Written by `dev_6M_b/compute_options.py` (session 6M, 2026-11-13). **Estimates only. Nothing was bought, no "
     "workflow was added or dispatched, and no run of record was made for this file.**", "",
     "## 1. What was measured here", "",
     f"`python -m manhattan.sim.benchmark` on this session's machine: {bench['machine']['cpu']}, {bench['machine']['logical_cores']} "
     f"cores, {bench['machine']['platform']}, Python {bench['machine']['python']}. One replication of each kind of run, first alone on an "
     f"otherwise idle machine, then with {W} workers at once, every core busy. numpy runs on one thread in every worker, as in "
     "`scripts/manhattan_sim_run.sh`. Timing only: no record was written.", "",
     f"| run | code | alone: seconds of wall-clock | alone: seconds of CPU | the same replication with every core busy: seconds | parallel efficiency | mean of the {W} replications run busy: seconds | peak memory of a worker (MB) |",
     "|---|---|---|---|---|---|---|---|"]
for k, b in K.items():
    L.append(f"| {k} | {b['version']} | {b['alone_wall']:.0f} | {b['alone_cpu']:.0f} | {b['busy_wall_same_replication']:.0f} | {b['efficiency_same_replication']:.2f} | {b['busy_wall_mean']:.0f} | {b['peak_rss_mb']:.0f} |")
L += ["", f"- **Parallel efficiency: {EFF:.2f}** with {W} workers on {W} cores: the time of a replication alone divided by the time of the very same "
      f"replication when every core is busy, summed over the slice. (Against the mean of the {W} replications of each kind it is {bench['efficiency']:.2f}; "
      "replications of one scenario differ in length, the twins' most of all, so the first is the cleaner number.) The busy phase "
      f"ends with a tail in which fewer than {W} jobs are left, which flatters the machine a little: its workers used {bench['busy_cpu_share_of_cores']:.0%} of the cores' time.",
      f"- **CPU time of the busy phase: {bench['busy_cpu_hours']:.2f} CPU-hours** for {len(bench['busy'])} replications in {bench['busy_wall_total'] / 60:.0f} minutes of wall-clock.",
      f"- **Peak memory: about {min(v['peak_rss_mb'] for v in K.values()) / 1024:.1f} to {sorted(v['peak_rss_mb'] for v in K.values())[-2] / 1024:.1f} GB a worker for version 1's runs, D11 and the twins, and "
      f"{bench['peak_rss_mb_per_worker'] / 1024:.1f} GB a worker for the dearest HB scenario (D08).** So {W} workers need at most "
      f"{bench['peak_rss_mb_all_workers'] / 1024:.1f} GB and seven at most {7 * bench['peak_rss_mb_per_worker'] / 1024:.1f} GB, and that only while "
      "all of them are on an HB scenario. On a machine with 16 GB that leaves little room: run the HB scenarios with four or five "
      "workers there (`WORKERS=4 SIZES=HB scripts/manhattan_sim_run.sh`, after `SIZES=STD,LONG` with seven). A GitHub runner has 16 GB for 4 workers.", "",
      "## 2. The whole development programme, in hours of one idle core of this machine", "",
      "Replications times seconds per replication. For a run in the slice the seconds are the benchmark's; for the others, "
      "the seconds on file from the pilots (measured while every core was busy) times the ratio the benchmark found for "
      "that kind of run (" + ", ".join(f"{f}: {v:.2f}" for f, v in ratio.items()) + ").", "",
      "| part | runs | replications pre-registered | seconds per replication, idle core (range) | CPU-hours, all | CPU-hours still to run (pilot replications on file count) |",
      "|---|---|---|---|---|---|"]
for f, label in FAMS:
    rs = [r for r in rows if r["fam"] == f]
    L.append(f"| {label} | {len(rs)} | {sum(r['need'] for r in rs):,} | {min(r['idle_sec'] for r in rs):.0f} to {max(r['idle_sec'] for r in rs):.0f} | "
             f"{sum(r['cpu_h_all'] for r in rs):,.0f} | {sum(r['cpu_h_left'] for r in rs):,.0f} |")
L.append(f"| **all 32 development runs** | {len(rows)} | {sum(r['need'] for r in rows):,} | | **{tot_all:,.0f}** | **{tot_left:,.0f}** |")
L += ["", "**The confirmation run on the held-out scenarios is not in that total, and cannot be measured: its worlds are not coded.** "
      "Extrapolated from the development runs of the same size (so a guess with the right order of magnitude):", "",
      "| part | CPU-hours of one idle core here |", "|---|---|"]
L += [f"| {a} | {h:,.0f} |" for a, h in held] + [f"| **one confirmation run** | **{held_tot:,.0f}** |",
      f"| **development programme and one confirmation run** | **{tot_left + held_tot:,.0f}** |"]
full = tot_left + held_tot

def days(cpu_h, speed, workers, eff):
    return cpu_h / (speed * workers * eff) / 24

L += ["", "## 3. The three options", "",
      "`speed` is how fast one core of the machine is against one core of this session's machine (1 = the same). It is the "
      "one number this session could not measure for a machine it does not have. **To measure it: run `python -m "
      "manhattan.sim.benchmark --quick --out bench.json` on the machine (about five minutes) and divide the two \"alone\" "
      f"times above (D02 STD {K['D02 STD']['alone_wall']:.0f} s, D08 HB {K['D08 HB']['alone_wall']:.0f} s) by its own.**", "",
      "### (a) The iMac", "",
      "Seven workers on eight cores, as `scripts/manhattan_sim_run.sh` runs it. Which iMac it is is not recorded in the "
      "repository, so three cases:", "",
      "| the iMac's cores against this machine's | parallel efficiency assumed | development programme | with one confirmation run | cost |", "|---|---|---|---|---|"]
for label, speed, eff in (("the same (speed 1.0)", 1.0, EFF), ("a recent Intel desktop (speed about 1.5)", 1.5, EFF),
                          ("Apple silicon performance cores (speed about 2.5; an M-series iMac has 4 of them and 4 slower ones, so 7 workers are worth about 5.5)", 2.5 * 5.5 / 7, 1.0)):
    L.append(f"| {label} | {eff:.2f} | {days(tot_left, speed, 7, eff):.1f} days | {days(full, speed, 7, eff):.1f} days | electricity; the machine is busy for that long |")
L += ["", f"Session 5M's estimate was 1,500 to 1,750 CPU-hours, 9 to 10.5 days. The benchmark's number for the same programme is {tot_left:,.0f} "
      "CPU-hours of an idle core here. The run is resumable and can be stopped and restarted at any replication.", "",
      "### (b) GitHub Actions runners on this public repository", "",
      "Facts, from GitHub's documentation on 2026-11-13: a standard Linux runner for a **public** repository has 4 cores and "
      "16 GB of memory, and its use is **free and unlimited**; a job may run 6 hours; a workflow run may hold 256 matrix jobs; "
      "the Free plan runs 20 standard jobs at once (40 on Pro).", "",
      f"Assuming a runner's core is as fast as this machine's and the measured efficiency of {EFF:.2f} with four workers:", "",
      "| | development programme | with one confirmation run |", "|---|---|---|"]
rh = lambda c: c / (4 * EFF)
L += [f"| runner-hours | {rh(tot_left):,.0f} | {rh(full):,.0f} |",
      f"| jobs of 5 hours (inside the 6-hour limit) | {int(np.ceil(rh(tot_left) / 5))} | {int(np.ceil(rh(full) / 5))} |",
      f"| wall-clock with 20 jobs at once | {rh(tot_left) / 20:.0f} hours | {rh(full) / 20:.0f} hours |",
      "| cost | US$0 | US$0 |", "",
      "What it would take, none of it done: a new workflow, which is Ethan's to add (`.github/workflows/` belongs to the "
      "existing writers, hard rule 3) and to start (no session dispatches workflows that write, hard rule 16); a matrix that "
      "gives each job a scenario and a range of replication numbers (the runner already continues from the records on "
      "file, and seeds depend only on the replication number); and a way to bring the records back, as artifacts that "
      "Ethan commits, not as a job that pushes. Logs and artifacts of a public repository are public, which is fine for "
      "synthetic data. Free use is subject to GitHub's terms; a few hundred runner-hours of a project's own test "
      "simulation is ordinary use, but it is his account. A confirmation run needs a tagged commit and a clean tree, which "
      "a checkout of the tag satisfies.", "",
      "### (c) Rented cloud CPUs", "",
      "Prices for AWS compute-optimised instances whose every virtual CPU is a whole core (c7a), us-east-1, as listed by a "
      "price aggregator on 2026-11-13: **US$0.051 per core-hour on demand** (c7a.16xlarge, 64 cores, US$3.28 an hour) and "
      "about **US$0.016 per core-hour on spot** (US$1.03 an hour, varying by zone and hour). They are third-party "
      "snapshots: check AWS's own page before spending. The run is resumable, so a spot interruption costs at most the "
      "replications in progress.", "",
      "| speed of a rented core against this machine's | | development programme | with one confirmation run |", "|---|---|---|---|"]
for speed in (1.0, 1.5):
    for what, fn in (("core-hours rented", lambda c, s=speed: f"{c / s:,.0f}"),
                     ("cost on demand", lambda c, s=speed: f"US${c / s * 0.0513:,.0f}"),
                     ("cost on spot", lambda c, s=speed: f"US${c / s * 0.0161:,.0f}"),
                     ("wall-clock on one 64-core machine", lambda c, s=speed: f"{c / s / 64:.0f} hours"),
                     ("wall-clock on one 192-core machine", lambda c, s=speed: f"{c / s / 192:.0f} hours")):
        L.append(f"| {speed:.1f} | {what} | {fn(tot_left)} | {fn(full)} |")
L += ["", "A machine with whole cores should lose little to parallelism (each worker is one single-threaded process and "
      "they share nothing), so no efficiency factor is applied; with hyper-threaded virtual CPUs (c7i and most other "
      "families) count two virtual CPUs as one core. Other providers were looked at and not priced: Hetzner's dedicated-core "
      "prices changed in June 2026 and the figures found disagree with each other.", "",
      "**Spending is Ethan's alone (ETHAN_ACTIONS item 8). Nothing here was bought.**", "",
      "## 4. What the numbers say", "",
      f"- The development programme is about {tot_left:,.0f} hours of one core like this session's; a confirmation run about {held_tot:,.0f} more.",
      "- On the iMac that is four to eight days of a machine doing nothing else for the development programme, and one "
      "to two weeks with a confirmation run, depending on which iMac it is. On GitHub's free runners it is under a day "
      "of wall-clock for the development programme and a workflow to write. On rented cores it is tens of dollars and a day.",
      "- The model-fitting half (HB) is small on every option. The bulk is version 1's STD runs and the hedge-aware "
      "bootstrap (D11 and the twins).", ""]
open(out_path, "w", encoding="utf-8").write("\n".join(L))
print("wrote", out_path, round(tot_all), round(tot_left), round(held_tot))
