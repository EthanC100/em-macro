# Manhattan HTE benchmarks (synthetic data only)

Every number in sections 1–5 was **measured**. Section 6 adds cloud prices, which are **assumptions** and are
labelled as such.

- **Code:** commit `4355fa1`, the final code after the S10 corrections. No code changed while these benchmarks ran.
- **Raw records:** `results/manhattan_hte/*.json`.
- **Command:** `OPENBLAS_NUM_THREADS=1 python -m manhattan.hte.bench --target N --workers W --chunk C [--stages 1]
  [--no-cache]`.
- **Data:** every workload is synthetic (`manhattan.hte.data`, seed 20261118: 2,772 business days, 252 of them fenced
  off as the protected stand-in, and 2,220 evaluated days after a 300-day warm-up). Commodity has 12 assets, rates 8
  and FX 10.
- **Execution timing:** same-close fills (`kernels.EXECUTION_TIMING`). These records measure throughput; no return
  figure in them is realistic (S10 F8).

Earlier figures (4b42331, before S10) differed by about 5–15%: the container moved to another host kernel, and
S10 F6 changed stage-3 grouping. Section 7 lists the corrections to the previous report.

## 0. Hardware and software

| item | value |
|---|---|
| machine | Claude Code cloud container: 4 vCPU "Intel Xeon Processor @ 2.10GHz" (AVX2, AVX-512F, FMA), 1 thread per core, 15.7 GiB RAM, no swap; Linux 6.18 |
| software | Python 3.13.18, NumPy 2.5.3, scipy-openblas 0.3.34 (DYNAMIC_ARCH; run-time kernel SkylakeX; single-threaded via `OPENBLAS_NUM_THREADS=1`). This numerical environment is part of every run identity (S10 F9) |
| parallelism | `concurrent.futures.ProcessPoolExecutor` (fork), 1 or 4 worker processes |

The container shares its host, so timings carry ordinary noise.

## 1. Workloads

`manhattan.hte.workload.build(target)` produces the following:

- **families:** 5, all with sign `+`;
- **hypotheses:** 15 (5 families × 3 domains);
- **strategy specs:** 30, two horizons per hypothesis;
- **bindings:** 2 cost models × 2 sizing rules per spec.

| target | candidates | variants | strategy specs | hypotheses | families |
|---|---|---|---|---|---|
| 10^4 | 10,344 | 2,586 | 30 | 15 | 5 |
| 10^5 | 99,552 | 24,888 | 30 | 15 | 5 |
| 10^6 | **1,024,272** | 256,068 | 30 | 15 | 5 |

These are candidates (parameter combinations bound to costs and sizing), not hypotheses.

## 2. Time and throughput

**Total** below includes registration (stage 0). The earlier report quoted run time without registration as
"end to end" (S10 F10).

| run | candidates | registration s | run wall s | **total incl. registration s** | warm | pass A | pass B | stage 4 | CPU s | CPU util |
|---|---|---|---|---|---|---|---|---|---|---|
| 10k, 1 worker | 10,344 | 1.3 | 27.7 | **29.0** | 1.5 | 7.8 | 9.6 | 8.7 | 27 | 0.98 |
| 10k, 4 workers | 10,344 | 1.2 | 8.9 | **10.1** | 1.4 | 2.1 | 2.7 | 2.6 | 29 | 0.80 |
| 10k, 4 workers, cache off | 10,344 | 1.3 | 92.4 | **93.7** | 0.0 | 34.1 | 28.5 | 29.8 | 340 | 0.92 |
| 100k, 4 workers | 99,552 | 3.3 | 54.8 | **58.1** | 4.4 | 21.2 | 22.5 | 6.0 | 192 | 0.88 |
| **1M, 4 workers (genuine full run)** | 1,024,272 | 26.0 | 417.1 | **443.1** | 12.6 | 210.6 | 176.4 | 11.1 | 1,559 | 0.93 |
| 100k, stage 1 only | 99,552 | 3.2 | 19.0 | **22.2** | 4.4 | 14.3 | – | 0.1 | 60 | 0.79 |
| **1M, stage 1 only (genuine)** | 1,024,272 | 24.3 | 171.6 | **195.9** | 13.3 | 155.0 | – | 1.0 | 621 | 0.90 |

| run | pass A cand/s | pass B cand/s (computed simulations) | run cand/s | **cand/s incl. registration** | CPU ms per candidate |
|---|---|---|---|---|---|
| 10k, 1 worker | 1,321 | 884 (8,528) | 373 | 357 | 2.62 |
| 10k, 4 workers | 5,015 | 3,131 (8,528) | 1,166 | 1,029 | 2.76 |
| 10k, 4 workers, cache off | 304 | 299 (8,528) | 112 | 110 | 32.83 |
| 100k, 4 workers | 4,685 | 3,347 (75,468) | 1,818 | 1,714 | 1.93 |
| 1M, 4 workers | 4,863 | 3,501 (617,584) | 2,455 | **2,311** | 1.52 |
| 100k, stage 1 only | 6,960 | – | 5,246 | 4,488 | 0.60 |
| 1M, stage 1 only | 6,610 | – | 5,969 | **5,228** | 0.61 |

Definitions:

- **Pass A** is stages 1+2 for every candidate (or stage 1 alone).
- **Pass B** is the stage-3 simulation, run only for the representatives that are actually simulated; its rate is
  per *computed simulation*.
- **CPU s** is user + system time of the parent and all workers, excluding registration.

**Per-candidate CPU cost on one core, measured:**

| stage | cost |
|---|---|
| stage 1 alone | about 0.6 ms |
| stages 1+2 | about 0.8 ms |
| stage 3 per computed simulation | about 1.1 ms (4 × 176.4 s / 617,584) |

**Status quo.** The existing `manhattan.engine.backtest.run` took **0.73 s per strategy** (`existing_engine.json`; 10
FX assets, 2,520 days). It is a different and richer per-strategy model, so this is not a like-for-like speedup.

## 3. What "one million" means here: candidates, simulations, aliases, attempts and log records

The S10 review asked for these quantities to be kept apart (F10). For the 1M full run:

| quantity | count | meaning |
|---|---|---|
| registered candidates | 1,024,272 | every one has a terminal status at every stage (reconciliation: 0 violations) |
| stage-3 **computed simulations** | **617,584** | series actually simulated |
| **exact aliases** (not simulated) | **403,360** | positions and binding bit-identical to a representative in the same family; results copied exactly, never re-simulated; counted in every denominator |
| degenerate (no position) | 3,328 | nothing to simulate |
| dominated by the Hölder bound | 0 | the bound pruned nothing on these costs |
| **attempts** | **3,208** | chunks of work: 2,001 in pass A (chunks of 512) and 1,207 in pass B (whole bootstrap groups) |
| attempt records | 6,416 | one `attempt_started` and one terminal per attempt |
| **log records**, this run | 6,419 | attempt records plus `run_started`, `selection` and `run_closed` |
| **log records**, whole file | **6,426** | plus the workspace's registry and probe records (5 `pit_probe`, `registry_segment`, `registry_frozen`) |

The previous report said "3,208 hash-chained records". That number is the attempts; the log holds about twice as many
records. (S10's run counted 6,427 records; one more workspace-level record explains the difference.)

**Funnel at each scale:**

| | 10^4 | 10^5 | 10^6 |
|---|---|---|---|
| computed simulations | 8,528 | 75,468 | 617,584 |
| exact aliases | 1,744 (16.9%) | 23,628 (23.7%) | 403,360 (39.4%) |
| degenerate | 72 | 456 | 3,328 |

## 4. Memory, cache and storage

| run | peak RSS parent MiB | peak RSS largest worker MiB | feature cache hits / misses |
|---|---|---|---|
| 10k, 1 worker | 276 | 56 | 68,319 / 231 |
| 10k, 4 workers | 152 | 264 | 49,958 / 232 |
| 10k, 4 workers, cache off | 60 | 235 | 0 / 78,640 |
| 100k, 4 workers | 321 | 386 | 459,458 / 631 |
| 1M, 4 workers | 1,779 | 1,380 | 4,222,912 / 1,496 |
| 1M, stage 1 only | 1,266 | 673 | 2,970,246 / 1,494 |

**Cache effectiveness.** With the cache off, the 10k run used 11.9x more CPU (32.8 vs 2.8 ms per candidate). The
`result_root` was bit-identical (`79d00a98…`) for 1 worker, 4 workers and cache off.

| run | registry | attempt log | pass A files | pass B files | results.bin | feature cache | total | bytes/candidate excl. cache |
|---|---|---|---|---|---|---|---|---|
| 10k | 1.2 MB | 0.1 MB | 1.4 MB | 1.9 MB | 2.5 MB | 46.6 MB | 54.0 MB | 717 |
| 100k | 11.6 MB | 0.4 MB | 13.1 MB | 12.9 MB | 24.5 MB | 127.1 MB | 191.9 MB | 650 |
| 1M | 118.8 MB | 4.0 MB | 134.5 MB | 104.7 MB | 252.0 MB | 301.5 MB | 936.2 MB | 620 |
| 1M, stage 1 only | 118.8 MB | 2.4 MB | 134.5 MB | – | 126.0 MB | 301.5 MB | 683.2 MB | 373 |

## 5. Answers to the measurement questions

| question | measured answer |
|---|---|
| candidate evaluations per second | 1M full run: **2,311 candidates/s including registration** (2,455/s excluding it) on 4 vCPUs. Stages 1+2: 4,863/s. Stage 3: 3,501 computed simulations/s. Cheap screen alone: 6,610/s, or 5,228/s including registration |
| one million cheap screens | **measured 3.3 minutes including registration** (195.9 s; 621 CPU-s) |
| one million candidates through the full funnel | **measured 7.4 minutes including registration** (443.1 s; 1,559 CPU-s). Of the 1,024,272 candidates, **617,584 were simulated** and **403,360 are exact aliases** whose results were copied, not simulated |
| one million *computed* simulations | **estimate, not measured:** about 1.1 CPU-ms × 10^6 ≈ 1,140 CPU-s of stage 3, so about 9 minutes total on 4 vCPUs (pass A and overheads as measured). The existing per-strategy engine would take 0.73 s × 10^6 ≈ 204 CPU-hours, also an estimate |
| dominant bottlenecks | 1. Building positions, which happens in both passes (storing them would need about 180 GB at 10^6). 2. Elementwise stage-3 arithmetic. 3. The B = 999 bootstrap. 4. Serial warm-up and stage 4 at small N. 5. About 1.8 GB parent RSS at 10^6 while the result table is built |

## 6. Cost estimates (prices are assumptions, not quotes)

Two different quantities are measured here; the earlier report used the first where the second applies (S10 F10).

- **CPU time:** process user + system time, excluding registration. For the 1M full run this is **0.433 CPU-hours**
  (1,559 s). It measures work done.
- **Reserved vCPU-hours:** wall time including registration × the machine's 4 vCPUs. For the 1M full run this is
  **0.492 vCPU-hours** (443.1 s × 4). This is what an instance of this size bills, whatever its utilisation. Billing
  granularity, start-up and idle time come on top.

**Assumed prices.** These are point-in-time figures from third-party trackers, checked 2026-11-18 and not verified
with the providers:

- AWS c7i.xlarge (4 vCPU) in us-east-1: about US$0.18/hour on demand, so about US$0.045 per vCPU-hour.
- The same instance on spot: about US$0.05/hour, with an interruption rate listed above 20%.
- Exchange rate: 1 USD ≈ 1.30 SGD, also an assumption.

| option | per 1M full run (0.492 reserved vCPU-h; 443 s on 4 vCPU) | notes |
|---|---|---|
| existing local hardware | no incremental cost | 7.4 min on 4 cores |
| small cloud instance, on demand | about US$0.022 for 443 s, or US$0.18 if billed by the whole hour | billing granularity dominates |
| spot instance | about US$0.006 (S$0.01) for 443 s | an interruption is a tested resume; results are bit-identical in the same numerical environment, and resuming in a different environment is refused (S10 F9) |
| batch scheduler or cluster | no benefit at this scale | – |

**Against the S$500/month budget, this layer is negligible.** One hundred 1M runs a month would reserve about 49
vCPU-hours, roughly US$2.2 on demand or US$0.6 on spot.

## 7. Corrections to the previous report (S10 F10)

1. **"3,208 hash-chained records" was wrong.** The 1M run has 3,208 attempts, 6,416 attempt records and 6,426 log
   records in the file (§3).
2. **"End to end" excluded registration.** All totals now include it (§2).
3. **CPU time was conflated with billed vCPU-hours.** They are now reported separately, and costs use reserved
   vCPU-hours (§6).
4. **"One million full simulations" overstated the work done.** 617,584 series were simulated; 403,360 are exact
   aliases whose results were copied (§3, §5).
5. **The null-calibration statement was wrong.** The packages said that about 5% of p_boot ≤ 0.05 is expected when no
   variant has an edge. On the null synthetic world, stage-3 returns are net of costs, so their true mean is negative
   and the share is expected far below 5%; every family of the 120-candidate test fixture is below 5%. Even at exactly zero mean the
   recentred stationary-bootstrap p-value is only approximately uniform, and variants are strongly correlated. The
   share is therefore not a calibrated rate. The package note is corrected and tested
   (`test_f10_null_world_share_is_below_nominal_and_the_note_says_why`).

## 8. What these numbers are not

- They are throughput measurements on synthetic data with same-close execution.
- No return figure is realistic or evidence.
- Nothing was measured on other CPUs, BLAS builds or core counts.
