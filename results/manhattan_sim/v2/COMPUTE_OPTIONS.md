# Running the full pre-registered simulation: time and cost on three kinds of machine

Written by `dev_6M_b/compute_options.py` (session 6M, 2026-11-13). **Estimates only. Nothing was bought, no workflow was added or dispatched, and no run of record was made for this file.**

## 1. What was measured here

`python -m manhattan.sim.benchmark` on this session's machine: Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, Linux-6.18.44-fc-v445-x86_64-with-glibc2.39, Python 3.13.18. One replication of each kind of run, first alone on an otherwise idle machine, then with 4 workers at once, every core busy. numpy runs on one thread in every worker, as in `scripts/manhattan_sim_run.sh`. Timing only: no record was written.

| run | code | alone: seconds of wall-clock | alone: seconds of CPU | the same replication with every core busy: seconds | parallel efficiency | mean of the 4 replications run busy: seconds | peak memory of a worker (MB) |
|---|---|---|---|---|---|---|---|
| D02 LONG | v1 | 69 | 67 | 72 | 0.97 | 68 | 284 |
| D02 STD | v1 | 50 | 49 | 53 | 0.94 | 48 | 281 |
| D05h STD | v2 | 225 | 221 | 256 | 0.88 | 317 | 354 |
| D08 HB | v2 | 169 | 166 | 179 | 0.95 | 167 | 1822 |
| D08 STD | v1 | 103 | 100 | 108 | 0.95 | 113 | 288 |
| D11 STD | v2 | 380 | 373 | 418 | 0.91 | 380 | 371 |

- **Parallel efficiency: 0.92** with 4 workers on 4 cores: the time of a replication alone divided by the time of the very same replication when every core is busy, summed over the slice. (Against the mean of the 4 replications of each kind it is 0.91; replications of one scenario differ in length, the twins' most of all, so the first is the cleaner number.) The busy phase ends with a tail in which fewer than 4 jobs are left, which flatters the machine a little: its workers used 86% of the cores' time.
- **CPU time of the busy phase: 1.19 CPU-hours** for 24 replications in 21 minutes of wall-clock.
- **Peak memory: about 0.3 to 0.4 GB a worker for version 1's runs, D11 and the twins, and 1.8 GB a worker for the dearest HB scenario (D08).** So 4 workers need at most 7.1 GB and seven at most 12.5 GB, and that only while all of them are on an HB scenario. On a machine with 16 GB that leaves little room: run the HB scenarios with four or five workers there (`WORKERS=4 SIZES=HB scripts/manhattan_sim_run.sh`, after `SIZES=STD,LONG` with seven). A GitHub runner has 16 GB for 4 workers.

## 2. The whole development programme, in hours of one idle core of this machine

Replications times seconds per replication. For a run in the slice the seconds are the benchmark's; for the others, the seconds on file from the pilots (measured while every core was busy) times the ratio the benchmark found for that kind of run (v1 LONG: 0.87, v1 STD: 0.62, twin: 0.77, HB: 1.18, D11: 1.02).

| part | runs | replications pre-registered | seconds per replication, idle core (range) | CPU-hours, all | CPU-hours still to run (pilot replications on file count) |
|---|---|---|---|---|---|
| version 1's code: 15 runs at STD | 15 | 30,000 | 42 to 220 | 686 | 681 |
| version 1's code: 2 runs at LONG | 2 | 4,000 | 67 to 69 | 76 | 75 |
| D11 with the hedge-aware test | 1 | 2,000 | 380 to 380 | 211 | 207 |
| nine hedged twins, SPA only | 9 | 3,600 | 160 to 464 | 237 | 233 |
| five HB scenarios: analytic model, tiers, dormancy | 5 | 2,000 | 77 to 169 | 57 | 55 |
| **all 32 development runs** | 32 | 41,600 | | **1,266** | **1,252** |

**The confirmation run on the held-out scenarios is not in that total, and cannot be measured: its worlds are not coded.** Extrapolated from the development runs of the same size (so a guess with the right order of magnitude):

| part | CPU-hours of one idle core here |
|---|---|
| 13 held-out runs at STD (H01, H02a, H02b, H02c, H03, H04, H05, H06, H08m, H08x, H10, H11 by version 1's pipeline; H12 at D11's cost) | 759 |
| 1 held-out run at LONG (H11) | 38 |
| 7 held-out runs at HB (H03, H05, H06, H07, H09, H10, H11) | 80 |
| **one confirmation run** | **877** |
| **development programme and one confirmation run** | **2,129** |

## 3. The three options

`speed` is how fast one core of the machine is against one core of this session's machine (1 = the same). It is the one number this session could not measure for a machine it does not have. **To measure it: run `python -m manhattan.sim.benchmark --quick --out bench.json` on the machine (about five minutes) and divide the two "alone" times above (D02 STD 50 s, D08 HB 169 s) by its own.**

### (a) The iMac

Seven workers on eight cores, as `scripts/manhattan_sim_run.sh` runs it. Which iMac it is is not recorded in the repository, so three cases:

| the iMac's cores against this machine's | parallel efficiency assumed | development programme | with one confirmation run | cost |
|---|---|---|---|---|
| the same (speed 1.0) | 0.92 | 8.1 days | 13.8 days | electricity; the machine is busy for that long |
| a recent Intel desktop (speed about 1.5) | 0.92 | 5.4 days | 9.2 days | electricity; the machine is busy for that long |
| Apple silicon performance cores (speed about 2.5; an M-series iMac has 4 of them and 4 slower ones, so 7 workers are worth about 5.5) | 1.00 | 3.8 days | 6.5 days | electricity; the machine is busy for that long |

Session 5M's estimate was 1,500 to 1,750 CPU-hours, 9 to 10.5 days. The benchmark's number for the same programme is 1,252 CPU-hours of an idle core here. The run is resumable and can be stopped and restarted at any replication.

### (b) GitHub Actions runners on this public repository

Facts, from GitHub's documentation on 2026-11-13: a standard Linux runner for a **public** repository has 4 cores and 16 GB of memory, and its use is **free and unlimited**; a job may run 6 hours; a workflow run may hold 256 matrix jobs; the Free plan runs 20 standard jobs at once (40 on Pro).

Assuming a runner's core is as fast as this machine's and the measured efficiency of 0.92 with four workers:

| | development programme | with one confirmation run |
|---|---|---|
| runner-hours | 341 | 580 |
| jobs of 5 hours (inside the 6-hour limit) | 69 | 116 |
| wall-clock with 20 jobs at once | 17 hours | 29 hours |
| cost | US$0 | US$0 |

What it would take, none of it done: a new workflow, which is Ethan's to add (`.github/workflows/` belongs to the existing writers, hard rule 3) and to start (no session dispatches workflows that write, hard rule 16); a matrix that gives each job a scenario and a range of replication numbers (the runner already continues from the records on file, and seeds depend only on the replication number); and a way to bring the records back, as artifacts that Ethan commits, not as a job that pushes. Logs and artifacts of a public repository are public, which is fine for synthetic data. Free use is subject to GitHub's terms; a few hundred runner-hours of a project's own test simulation is ordinary use, but it is his account. A confirmation run needs a tagged commit and a clean tree, which a checkout of the tag satisfies.

### (c) Rented cloud CPUs

Prices for AWS compute-optimised instances whose every virtual CPU is a whole core (c7a), us-east-1, as listed by a price aggregator on 2026-11-13: **US$0.051 per core-hour on demand** (c7a.16xlarge, 64 cores, US$3.28 an hour) and about **US$0.016 per core-hour on spot** (US$1.03 an hour, varying by zone and hour). They are third-party snapshots: check AWS's own page before spending. The run is resumable, so a spot interruption costs at most the replications in progress.

| speed of a rented core against this machine's | | development programme | with one confirmation run |
|---|---|---|---|
| 1.0 | core-hours rented | 1,252 | 2,129 |
| 1.0 | cost on demand | US$64 | US$109 |
| 1.0 | cost on spot | US$20 | US$34 |
| 1.0 | wall-clock on one 64-core machine | 20 hours | 33 hours |
| 1.0 | wall-clock on one 192-core machine | 7 hours | 11 hours |
| 1.5 | core-hours rented | 835 | 1,420 |
| 1.5 | cost on demand | US$43 | US$73 |
| 1.5 | cost on spot | US$13 | US$23 |
| 1.5 | wall-clock on one 64-core machine | 13 hours | 22 hours |
| 1.5 | wall-clock on one 192-core machine | 4 hours | 7 hours |

A machine with whole cores should lose little to parallelism (each worker is one single-threaded process and they share nothing), so no efficiency factor is applied; with hyper-threaded virtual CPUs (c7i and most other families) count two virtual CPUs as one core. Other providers were looked at and not priced: Hetzner's dedicated-core prices changed in June 2026 and the figures found disagree with each other.

**Spending is Ethan's alone (ETHAN_ACTIONS item 8). Nothing here was bought.**

## 4. What the numbers say

- The development programme is about 1,252 hours of one core like this session's; a confirmation run about 877 more.
- On the iMac that is four to eight days of a machine doing nothing else for the development programme, and one to two weeks with a confirmation run, depending on which iMac it is. On GitHub's free runners it is under a day of wall-clock for the development programme and a workflow to write. On rented cores it is tens of dollars and a day.
- The model-fitting half (HB) is small on every option. The bulk is version 1's STD runs and the hedge-aware bootstrap (D11 and the twins).
