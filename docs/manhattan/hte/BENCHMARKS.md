# Manhattan HTE benchmarks (synthetic data only)

Every number in sections 1–5 was **measured**. Section 6 adds cloud prices, which are **assumptions** and are
labelled as such.

- **Code:** engine commit `6282d75`. Later commits change documentation and one trailing newline in `pit.py`; the
  engine's numerical code is unchanged. Raw records: `results/manhattan_hte/*.json`.
- **Command:** `OPENBLAS_NUM_THREADS=1 python -m manhattan.hte.bench --target N --workers W --chunk C [--stages 1]
  [--no-cache]`.
- **Data:** every workload is synthetic (`manhattan.hte.data`, seed 20261118: 2,772 business days, 252 of them fenced
  off as the protected stand-in, and 2,220 evaluated days after a 300-day warm-up). Commodity has 12 assets, rates 8
  and FX 10.

## 0. Hardware and software

| item | value |
|---|---|
| machine | Claude Code cloud container: 4 vCPU "Intel Xeon Processor @ 2.10GHz" (AVX2, AVX-512F, FMA), 1 thread per core, 15.7 GiB RAM, no swap |
| software | Linux 6.18, Python 3.13.18, numpy 2.5.3, scipy-openblas 0.3.34 (BLAS single-threaded via `OPENBLAS_NUM_THREADS=1`) |
| parallelism | `concurrent.futures.ProcessPoolExecutor` (fork), 1 or 4 worker processes |
| scaling check | a pure-numpy kernel ran 4 copies in parallel at 1.00x the single-copy time, so the 4 vCPUs scale linearly |

The container shares its host, so timings carry ordinary noise. Repeated 10k runs differed by about 5-10%.

## 1. Workloads

`manhattan.hte.workload.build(target)` produces the following:

- **families:** 5, from 5 templates;
- **hypotheses:** 15 (5 families × 3 domains);
- **strategy specs:** 30 (each hypothesis has 2 specs: a short horizon with look-backs ≤ 60 days and a long horizon,
  61–260);
- **bindings:** 2 cost models × 2 sizing rules per spec;
- **grids:** dense, with correlated neighbouring values.

| target | candidates | variants | strategy specs | hypotheses | families |
|---|---|---|---|---|---|
| 10^4 | 10,344 | 2,586 | 30 | 15 | 5 |
| 10^5 | 99,552 | 24,888 | 30 | 15 | 5 |
| 10^6 | **1,024,272** | 256,068 | 30 | 15 | 5 |

At 10^6 these are 1,024,272 candidates. They are **not** 10^6 hypotheses: there are 15 hypotheses, and the funnel
found 618,000 distinct behaviours among them (section 3).

## 2. Time and throughput

| run | candidates | registration s | warm s | pass A s | pass B s | stage 4 s | run wall s | CPU s | CPU util |
|---|---|---|---|---|---|---|---|---|---|
| 10k, 1 worker | 10,344 | 1.3 | 1.7 | 8.1 | 11.1 | 9.1 | 30.1 | 29 | 0.96 |
| 10k, 4 workers | 10,344 | 1.2 | 1.7 | 2.3 | 2.9 | 2.6 | 9.6 | 30 | 0.78 |
| 10k, 4 workers, cache off | 10,344 | 1.5 | 0.0 | 41.5 | 37.7 | 35.2 | 114.5 | 412 | 0.90 |
| 100k, 4 workers | 99,552 | 3.7 | 5.3 | 24.1 | 28.3 | 6.7 | 64.9 | 224 | 0.86 |
| **1M, 4 workers (genuine full run)** | 1,024,272 | 27.3 | 13.2 | 245.9 | 204.9 | 12.0 | **482.0** | 1,769 | 0.92 |
| 100k, stage 1 only | 99,552 | 3.6 | 4.7 | 16.5 | – | 0.1 | 21.5 | 67 | 0.78 |
| **1M, stage 1 only (genuine)** | 1,024,272 | 26.8 | 14.4 | 187.4 | – | 1.0 | **204.4** | 735 | 0.90 |

| run | pass A cand/s | pass B cand/s (computed) | end-to-end cand/s | CPU ms per candidate |
|---|---|---|---|---|
| 10k, 1 worker | 1,272 | 768 (8,528) | 344 | 2.79 |
| 10k, 4 workers | 4,468 | 2,929 (8,528) | 1,081 | 2.90 |
| 10k, 4 workers, cache off | 249 | 226 (8,528) | 90 | 39.85 |
| 100k, 4 workers | 4,134 | 2,669 (75,468) | 1,535 | 2.25 |
| 1M, 4 workers | 4,165 | 3,014 (617,584) | **2,125** | 1.73 |
| 100k, stage 1 only | 6,033 | – | 4,626 | 0.68 |
| 1M, stage 1 only | **5,467** | – | 5,011 | 0.72 |

Definitions:

- **Pass A** is stages 1 and 2 for every candidate. In stage-1-only mode it is the cheap screen alone.
- **Pass B** is stage 3 (full simulation) for the representatives selected after deduplication.
- **Run wall** covers warm-up, passes, selection, stage 4 and reconciliation. It excludes registration, which is
  listed separately.
- **CPU s** is the user + system time of the parent and all workers.

At 10^6 the run is close to parallel-efficient (CPU utilisation 0.92). At 10^4 the serial overheads (feature
warm-up, stage 4) are a larger share. Stage 4 is bounded: M_eff uses at most 1,000 series per hypothesis, so it costs
about 12 s at any N.

**Measured per-candidate stage costs**, in CPU time on one core:

| stage | cost |
|---|---|
| stage 1 alone (positions, Hölder bound, fingerprint) | about 0.6-0.7 ms |
| stages 1+2 | about 0.9 ms |
| stage 3 per computed representative (positions again, vol-targeted series, costs, ω, grouped bootstrap with B = 999, SPA maxima) | about 1.3 ms (4 workers × 204.9 s / 617,584) |

**Status-quo comparison.** The existing `manhattan.engine.backtest.run` takes **0.78 s per strategy**. It runs one
strategy at a time, with a Python signal callback each day and volatility targeting, on the same synthetic FX panel
(10 assets, 2,520 days; `existing_engine.json`). That is about 600 times the HTE stage-3 cost per candidate. The two
are **different models**: the existing engine handles calendars, instruments and financing more generally. So this is
a statement about the architecture (vectorised, shared features) versus per-strategy callbacks. It is not a
like-for-like speed claim.

## 3. Funnel effect (the same at every scale, by construction)

| | 10^4 | 10^5 | 10^6 |
|---|---|---|---|
| degenerate (no position in window) | 72 | 456 | 3,328 |
| behavioural aliases (identical positions and binding within a family; stage 3 skipped, results copied, still counted) | 1,744 (16.9%) | 23,628 (23.7%) | **403,360 (39.4%)** |
| dominated by the Hölder bound | 0 | 0 | 0 |
| stage 3 computed | 8,528 | 75,468 | 617,584 |
| cross-family behavioural duplicates | 0 | 0 | 0 |

The **Hölder bound pruned nothing** on these cost assumptions. That is the honest result of an exact, sign-blind
bound: it is the tightest sign-blind bound possible (tested), and under realistic costs it is rarely tight enough to
prove a candidate non-positive. The savings came from behavioural deduplication instead. Dense grids create many
candidates whose positions are bit-identical: a `vol_halflife` that a sign rule ignores, or quantiles finer than one
asset. The alias share grows with grid density. Pruning beyond this would need the sign of outcomes, which makes it a
performance gate that must be recorded (ARCHITECTURE.md §4.3).

## 4. Memory, cache and storage

| run | peak RSS parent MiB | peak RSS largest worker MiB | feature cache hits / misses |
|---|---|---|---|
| 10k, 1 worker | 227 | 56 | 68,319 / 231 |
| 10k, 4 workers | 152 | 219 | 49,959 / 231 |
| 10k, 4 workers, cache off | 63 | 198 | 0 / 78,640 |
| 100k, 4 workers | 331 | 344 | 459,457 / 632 |
| 1M, 4 workers | 1,978 | 1,386 | 4,222,912 / 1,496 |
| 1M, stage 1 only | 1,395 | 672 | 2,970,244 / 1,496 |

The cache-off run uses the same code with `cache_enabled=False`.

**Cache effectiveness.** Turning the feature cache off made the 10k run cost **13.7x more CPU** (39.9 vs 2.9 ms per
candidate) and gave a **bit-identical** `result_root`, `93c8032d…`, identical across 1 worker, 4 workers and cache
off. The 1M run computed 1,496 distinct features and served 4.2 million reads from memory.

At 10^6 the parent's peak RSS (2.0 GB) comes mainly from loading every pass-A and pass-B result to build
`results.bin`. Workers peak at 1.4 GB, mostly copy-on-write pages of the 301 MB feature set and the registry arrays,
counted once per process by RSS.

| run | registry | attempt log | pass A files | pass B files | results.bin | feature cache | total | bytes/candidate excluding cache |
|---|---|---|---|---|---|---|---|---|
| 10k | 1.2 MB | 0.1 MB | 1.4 MB | 2.4 MB | 2.5 MB | 46.6 MB | 54.5 MB | 760 |
| 100k | 11.6 MB | 0.4 MB | 13.1 MB | 13.4 MB | 24.5 MB | 127.1 MB | 191.7 MB | 649 |
| 1M | 118.8 MB | 4.0 MB | 134.5 MB | 105.1 MB | 252.0 MB | 301.5 MB | 931.1 MB | 615 |
| 1M, stage 1 only | 118.8 MB | 2.4 MB | 134.5 MB | – | 126.0 MB | 301.5 MB | 683.2 MB | 373 |

A full 10^6 run needs about **0.93 GB** of disk, of which the feature cache is about 0.3 GB and can be deleted
afterwards.

The 10^6 attempt log has **3,208 hash-chained records**, one intent and one terminal per chunk of 512, plus run and
registry records. It is 4 MB. The engine stores no daily return series. Each stage-3 series is kept as its SHA-256,
and stage 4 recomputes and verifies any series it needs. Storing the series would have cost about 18 KB per
candidate, roughly 11 GB for the 10^6 representatives.

## 5. Answers to the measurement questions

| question | measured answer |
|---|---|
| candidate evaluations per second actually measured | 1M full run: **2,125 candidates/s** end to end on 4 vCPUs. Stages 1+2: **4,165/s**. Stage 3: **3,014/s** per computed representative. Cheap screen alone: **5,467/s**. One core: 344/s end to end at 10k (pass A 1,272/s; stage 3 768/s) |
| one million cheap screens | **measured 3.4 minutes** (204 s wall, 735 CPU-s) on 4 vCPUs, plus 27 s registration |
| one million full simulations | **measured 8.0 minutes** (482 s wall, 1,769 CPU-s) for the genuine 1,024,272-candidate run, in which 617,584 representatives were simulated and 403,360 aliases inherited exact results. **Estimate** without deduplication, assuming the same stage-3 cost per candidate: about 1.3 CPU-ms × 10^6 = 1,330 CPU-s of stage 3, about 10 minutes wall on 4 vCPUs. **Estimate** with the existing per-strategy engine: 0.78 s × 10^6 ≈ 216 CPU-hours (about 2.3 days on 4 vCPUs) |
| dominant bottlenecks | 1. Building positions, which runs in both passes because storing positions would need about 180 GB at 10^6. 2. Elementwise stage-3 arithmetic on `(n days × assets)` arrays. 3. The stationary bootstrap (B = 999), already reduced about 8x by grouped BLAS-3. 4. At small N, serial warm-up and stage 4. 5. At 10^6, parent memory for the result table (2 GB) |

## 6. Cost estimates (prices are assumptions, not quotes)

**Measured resource use for one 10^6 full run:** 1,769 CPU-seconds, or 0.49 vCPU-hours; 8 minutes wall on 4 vCPUs;
2 GB peak RAM; 0.93 GB disk.

**Assumed prices.** These are point-in-time figures from third-party trackers, checked 2026-11-18 and not verified
with the providers:

- AWS c7i.xlarge (4 vCPU, the same CPU class as the test machine, an assumption) in us-east-1: about US$0.18/hour
  on demand, so about US$0.045 per vCPU-hour.
- The same instance on spot: about US$0.05/hour, so about US$0.013 per vCPU-hour, with an interruption rate listed
  above 20%.
- Hetzner CCX13 (2 dedicated vCPU): sources disagree, between about €17 and €43 per month.
- Exchange rate: 1 USD ≈ 1.30 SGD, also an assumption.

| option | compute cost per 10^6 full run (0.49 vCPU-h) | per 10^5 (224 CPU-s) | per 10^3 | notes |
|---|---|---|---|---|
| single local machine (existing hardware) | no incremental cost | – | – | 8 min on 4 cores; about 30 min single-core (estimated from 1-worker CPU time) |
| parallel local (4 workers) | no incremental cost | – | – | measured 3.2-3.4x on pass A/B |
| small cloud CPU, on demand | about US$0.022 (S$0.03), or US$0.18 for a whole instance-hour | about US$0.003 | below US$0.0001 | billing granularity dominates |
| spot / interruptible | about US$0.007 (S$0.01) | about US$0.001 | – | an interruption is a tested resume: intents are counted, completed chunks are kept, results bit-identical |
| batch scheduler (e.g. a cloud batch service) | no benefit at this scale | – | – | one 8-minute job does not need a cluster |
| cache persistence | saves the 1,496-feature warm-up (13 s) and, more importantly, 13.7x CPU versus no cache | – | – | the cache is keyed by data, parameters and code, and is safe to keep |
| incremental recomputation | not implemented by design | – | – | a new data hash is a new, counted run (LIMITATIONS.md §3) |

**Against the S$500/month programme budget**, this evaluation layer is negligible. One hundred 10^6-candidate runs a
month would use about 49 vCPU-hours, or about US$2.2 on demand and US$0.65 on spot, and could equally run on existing
hardware. The budget-relevant costs lie elsewhere:

- licensed data;
- a richer stage 3, such as contract-level execution: a 100-1000x heavier stage 3 would put a 10^6 run at about
  49-490 vCPU-hours, about US$2-22 on demand, still small;
- above all, human review of packages.

**Recommendation.** Run on existing hardware or one small spot instance, and keep the feature cache. Do not build a
cluster. Spend engineering time on the integration blockers (LIMITATIONS.md), not on throughput.

## 7. What these numbers are not

- **No discoveries.** Nothing here is a discovery, a p-value of record or evidence about a market.
- **The planted-effect test is a pipeline check.** The engine's one positive statistical result is its recovery of an
  effect the generator planted on purpose.
- **Extrapolation is labelled.** The 10^6 numbers are measured, not extrapolated. Only the "without deduplication"
  and "existing engine at 10^6" lines in §5 are estimates, and each states its assumption.
- **No load testing.** Throughput on other CPUs, BLAS builds or core counts was not measured.
