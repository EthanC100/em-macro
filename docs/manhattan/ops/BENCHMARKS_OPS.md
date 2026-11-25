# Manhattan ops: per-stage benchmark on synthetic data

Measured 2026-11-25 by a build session. **Synthetic data only; no network; no real market data.** Raw summary:
[bench_ops_results.json](bench_ops_results.json). Script: `scripts/manhattan_ops_bench.py` (the full per-night JSON
it writes is not committed). Sections 1-3 are **measurements**. Section 4 is a **projection** and section 5 holds
**cost estimates**; both are labelled and rest on stated assumptions.

**Machine.** Claude Code cloud container, `nproc` = 4 (Intel Xeon @ 2.10GHz), Python 3.13.18, NumPy 2.5.3,
git 2.43.0, Linux 6.18. The host is shared, so timings carry ordinary noise (a repeat of the ops runs differed by
up to 6%).

**Reporting rules.** Families, unique executable configurations (distinct spec hashes) and attempts are separate
columns everywhere. Historical screening (exploration role, weight 0) and forward confirmation (forward observation
attempts) are reported in separate tables and never summed.

## 1. Ops path (`scripts/manhattan_ops_bench.py --families 10 20 50 --nights 5`)

The same flow as `tests/test_manhattan_ops_e2e.py`: mock generation, mechanical critic, compile, historical
screening on synthetic data 2015-01-02..2019-12-31, `freeze_pr.prepare` (plus a commit to a public stand-in), a
capture-only night before registration (Thursday 2026-11-12), registration (merged Friday 15:00, witnessed 16:30),
then five forward nights (Monday 2026-11-16 to Friday 2026-11-20; Friday 13th is recorded as a missed run, as in
the e2e test), and a final mirror verification. Local bare repositories stand in for the private ledger and its
mirror (no network time). Every forward run's commit identity is the repository HEAD, because `runner.run_fence`
verifies `config/manhattan.yaml` at that commit. Stage times inside a night come from wrapping the runner's
collaborators in the benchmark process (outermost call only, so nothing is double counted; the rest is `other`).

The mock generator's grids give **27 executables per 10 families**: families, hypotheses and executables grow
together, so the three sizes differ in executables by the same factor as in families. Each registered prediction is
one executable, observed once per night (one forward attempt per prediction per night).

### 1.1 Sizes

| families | hypotheses | unique executable configs | predictions registered | screening attempts | forward attempts per night | forward attempts, 5 nights |
|---|---|---|---|---|---|---|
| 10 | 14 | 27 | 27 | 27 | 27 | 135 |
| 20 | 27 | 54 | 54 | 54 | 54 | 270 |
| 50 | 67 | 134 | 134 | 134 | 134 | 670 |

### 1.2 One-off pipeline stages (wall seconds)

| stage | 10 families | 20 families | 50 families |
|---|---|---|---|
| mock generation | 0.001 | 0.002 | 0.048 |
| mechanical critic | 0.004 | 0.005 | 0.013 |
| compile | 0.002 | 0.004 | 0.010 |
| `freeze_pr.prepare` + public commit | 0.10 | 0.18 | 0.21 |
| registration (one ledger write, 6 commits) | 0.62 | 0.94 | 1.03 |
| final mirror verification | 0.14 | 0.20 | 0.40 |

**Historical screening (exploration role; separate from forward confirmation)**

| families | unique executable configs | attempts | wall s | attempts/s | private-ledger commits |
|---|---|---|---|---|---|
| 10 | 27 | 27 | 4.99 | 5.4 | 6 |
| 20 | 54 | 54 | 10.18 | 5.3 | 6 |
| 50 | 134 | 134 | 25.27 | 5.3 | 6 |

About 0.19 s per executable for five years of daily synthetic data through `engine` (one attempt each).

### 1.3 Forward confirmation, per night

| families | unique executable configs | attempts per night | night wall s, nights 1..5 | mean wall s | mean CPU s | forward-attempt phase s (mean) | attempts/s, forward phase | attempts/s, whole night | capture-only night s |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 27 | 27 | 5.1, 5.9, 6.5, 7.7, 9.0 | 6.85 | 6.28 | 2.84 | 9.9 | 4.1 | 2.29 |
| 20 | 54 | 54 | 6.2, 7.1, 8.7, 9.7, 11.5 | 8.64 | 8.04 | 3.84 | 14.6 | 6.5 | 2.40 |
| 50 | 134 | 134 | 9.1, 10.6, 11.9, 14.9, 17.4 | 12.80 | 12.12 | 6.59 | 21.1 | 11.0 | 3.25 |

**Mean wall seconds per stage, per forward night**

| stage | 10 families | 20 families | 50 families |
|---|---|---|---|
| open: clone and verify the chain | 0.18 | 0.23 | 0.26 |
| journal reconcile + attempt recovery | 0.01 | 0.01 | 0.03 |
| lock / unlock | 0.12 / 0.08 | 0.17 / 0.10 | 0.16 / 0.17 |
| missed runs | 0.06 | 0.05 | 0.06 |
| capture: parse and hash | 0.24 | 0.28 | 0.25 |
| capture: ledger write (raw file + record) | 0.57 | 0.68 | 0.95 |
| first-seen rebuild from all captures | 1.28 | 1.36 | 1.21 |
| point-in-time store build | 0.19 | 0.20 | 0.19 |
| fence verification at the commit | 0.01 | 0.01 | 0.01 |
| **forward: register attempts** | 0.31 | 0.45 | 0.88 |
| **forward: read (declared window)** | 0.32 | 0.62 | 1.50 |
| **forward: compute (`run_bound`)** | 0.34 | 0.66 | 1.53 |
| **forward: plan** | 0.01 | 0.01 | 0.03 |
| **forward: completion (plan recomputed from captures)** | 1.52 | 1.50 | 1.56 |
| **forward: commit results + terminals** | 0.35 | 0.59 | 1.09 |
| heartbeat | 0.31 | 0.44 | 0.77 |
| private log commit | 0.05 | 0.05 | 0.05 |
| mirror push / mirror verify | 0.47 / 0.25 | 0.71 / 0.31 | 1.29 / 0.53 |
| other (not wrapped) | 0.18 | 0.20 | 0.26 |

**Git writes and storage per forward night**

| families | private-ledger commits per night | mirror commits per night | chain.jsonl bytes/night | journal.jsonl bytes/night | raw/ bytes/night | logs/ bytes/night | bare repository growth/night (loose objects) |
|---|---|---|---|---|---|---|---|
| 10 | 18, then 15 | 18, then 15 | 127,490 | 134,088 | 2,707,915 | 0 | 2.34 MB |
| 20 | 18, then 15 | 18, then 15 | 251,777 | 263,911 | 2,707,915 | 0 | 3.63 MB |
| 50 | 18, then 15 | 18, then 15 | 620,516 | 649,235 | 2,707,915 | 0 | 7.40 MB |

| families | final ledger records | final commits | working tree (chain + journal + raw) | bare repository | **bare repository after `git gc`** |
|---|---|---|---|---|---|
| 10 | 541 | 102 | 17.7 MB | 13.1 MB | **1.28 MB** |
| 20 | 1,054 | 102 | 19.2 MB | 20.0 MB | **1.64 MB** |
| 50 | 2,574 | 102 | 23.5 MB | 40.2 MB | **2.68 MB** |

**Failures:** none in any run. Every night's status was `ok`, the chain verified, the mirror was `equal`, no
`conflict`, no `capture_failed`, every attempt completed (screening 27/54/134, forward 135/270/670).

### 1.4 What the ops numbers show

1. **Commits per night are constant (15; 18 on the first forward night)**, independent of the number of families:
   all results and terminals are one journalled write. Per family the git cost falls (1.56, 0.78, 0.31 commits).
2. **The marginal cost is about 0.052 s of wall time per forward attempt per night** (20 to 50 families), of which
   about 0.034 s is the forward-attempt phase; the fixed cost of a night is about 5-6 s at these sizes.
3. **Night time grows with the ledger's age, not only its size.** At 50 families the night went from 9.1 to 17.4 s
   over five nights: the first-seen rebuild re-reads every capture, completion recomputes the plan from the captures,
   and each commit writes the whole `chain.jsonl`. Over months this growth, not the number of families, would dominate.
4. **Storage is dominated by two effects of the design, both visible here:** (a) each night stores a new full-history
   raw capture when the source's bytes change (2.7 MB for the synthetic source, which appends a day every night);
   (b) each of the 15 commits stores a new blob of the whole chain file, so the bare repository grows by 2.3-7.4 MB a
   night until it is repacked; `git gc` reduces it by a factor of 10-15 (1.3-2.7 MB after five nights).
5. Private logs are empty on successful runs (0 bytes); they fill only on failure.

## 2. High-throughput engine (`manhattan/hte`), rerun at modest sizes

`OPENBLAS_NUM_THREADS=1 python -m manhattan.hte.bench --target N --workers 4 --chunk 512`, same machine. HTE
attempts are chunks of work, not executables.

| target | families | hypotheses | strategy specs | unique executable configs (candidates) | computed simulations | exact aliases | HTE attempts (chunks) | registration s | run wall s | **total incl. registration s** | candidates/s incl. registration | CPU s | storage | bytes/candidate excl. cache | peak RSS parent / worker MiB | violations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10^4 | 5 | 15 | 30 | 10,344 | 8,528 | 1,744 | 38 | 1.5 | 12.6 | **14.2** | 729 | 32.0 | 53.6 MB | 677 | 152 / 271 | 0 |
| 10^5 | 5 | 15 | 30 | 99,552 | 75,468 | 23,628 | 343 | 3.7 | 69.4 | **73.1** | 1,363 | 200.8 | 191.9 MB | 650 | 321 / 386 | 0 |

These are 15-30% slower than the 2026-11-18 figures in [../hte/BENCHMARKS.md](../hte/BENCHMARKS.md) (10.1 s and
58.1 s), on a different host kernel.

**Attempt accounting bridge** (`python scripts/hte_accounting_bench.py --target 10000 --workers 4`): 10,344
candidates (5 families) become 10,344 per-candidate attempts; accounting 23.5 s against an 11.1 s HTE run
(2.27 ms per candidate, 2.1x the run), 36.8 MB of ledger (3,556 bytes per candidate), 0 violations.

## 3. Comparison of the two paths per executable (measured)

| path | unit | time per unit | ledger bytes per unit |
|---|---|---|---|
| ops historical screening (`engine`, one attempt per executable) | executable, 5 years daily | ~0.19 s wall | ~6.7 kB (chain + journal) |
| ops forward observation | attempt (one prediction, one night) | ~0.052 s wall marginal (+5-6 s fixed per night) | ~9.5 kB (chain + journal) before repacking |
| HTE screening, 10^5 | candidate (unique executable config) | ~0.73 ms wall incl. registration (4 workers) | ~650 B excl. cache |
| HTE with per-candidate attempt accounting | candidate | +2.27 ms | +3.56 kB |

## 4. PROJECTION to a 1,000,000-executable campaign (not measured)

**Assumptions.** Linear scaling from the largest size measured here (10^5 for HTE; 20→50 families for the ops
path); the same 4-vCPU machine; synthetic-shaped workloads (5 families, 30 strategy specs for HTE); local git (no
network time); no failures or retries; the night-to-night growth of section 1.4(3) ignored, which makes the ops
figures optimistic. A real campaign's family and hypothesis counts are not set by this projection.

| campaign part | families | unique executable configs | attempts | projected wall time | projected storage |
|---|---|---|---|---|---|
| **historical screening on HTE** (linear from 10^5: 73.1 s × 10.3) | as designed (5 in the synthetic workload) | ~1,024,000 candidates | ~3,500 HTE chunk attempts | **~12.5 min** on 4 vCPU (~0.56 CPU-hours); the earlier genuine 1M run measured 7.4 min (BENCHMARKS.md, 2026-11-18) | ~0.7 GB results + ~0.3 GB feature cache (~1 GB; 936 MB measured earlier) |
| + per-candidate attempt accounting (bridge, if the owner adopts it; decisions A-1, B4, D-10 open) | same | same | ~1,024,000 attempts | **+~39 min** (2.27 ms × 1.024M) | **+~3.6 GB** ledger |
| historical screening on the ops `engine` path instead | same | ~1,000,000 | ~1,000,000 | ~52 hours single process (0.19 s each) | ~6.7 GB of chain + journal |
| **forward confirmation of 1,000,000 predictions nightly on the ops runner** | – | 1,000,000 | 1,000,000 per night | **~14.5 hours per night** single process (0.052 s each) | **~9.5 GB per night** before repacking |

**Reading of the projection.** One million executables is feasible as **historical screening** on the HTE (minutes
of compute, ~1 GB; ~4.6 GB with per-attempt accounting). It is **not** feasible as nightly **forward confirmation**
on the ops runner as built: a night would exceed a GitHub Actions job's 6-hour limit, and the private ledger is a
git repository whose `Store` loads every record into memory (the capacity harness measured 951 MiB RSS for 100,000
records, `results/manhattan_ops/CAPACITY.md`). The forward set must therefore be the small number of executables
that the owner freezes after screening, and the real-data pilot ([REAL_DATA_PILOT_PLAN.md](REAL_DATA_PILOT_PLAN.md))
should measure the forward per-attempt cost and its growth with ledger age before any larger forward size is set.

## 5. Cost ESTIMATES

**Assumptions** (not quotes; check current GitHub pricing before relying on them):

- em-macro is a **public** repository: standard GitHub-hosted runners are free for public repositories, so the ops
  runner's minutes there cost nothing. The estimates below apply only if the work ran in a private repository or on
  larger runners.
- Assumed list price US$0.008 per minute for a 2-vCPU Linux runner and US$0.016 per minute for a 4-vCPU Linux
  runner; minutes are rounded up per job; ~2 minutes of job set-up (checkout, Python, hash-locked dependencies) per run.
- The private ledger lives in a private GitHub repository (storage included in the plan up to GitHub's repository
  size guidance; no Git LFS).

| item | estimate |
|---|---|
| nightly ops run, 50 families (13-17 s of work + set-up, plus network clone and push time not measured here) | ~3 billed minutes a night, ~65 minutes a month (22 weekdays): **free in the public repository**; ~US$0.50 a month at the assumed 2-vCPU price |
| 1M-candidate HTE screening run on a 4-vCPU runner | ~15 billed minutes: **~US$0.24 per run** at the assumed price (free on a public repository's standard runner, which since 2024 has 4 vCPUs) |
| the same with per-candidate attempt accounting | ~55 billed minutes: **~US$0.90 per run** |
| private ledger growth, 50 forward predictions-scale (134 attempts/night), after repacking | ~0.3-0.5 MB a night, ~10 MB a month, plus raw captures |
| raw captures for FRED H.10 (three full-history CSVs; size estimated from the series' lengths, not fetched) | ~0.7 MB per capture set when the bytes change; FRED posts H.10 dailies weekly, so roughly 1 changed set a week: ~35 MB a year before compression |
| per-candidate accounting ledger for one 1M screening campaign | ~3.6 GB: too large for a git-hosted ledger; it would need the owner's decision on A-1/B4/D-10 and a different store |

## 6. How to reproduce

```bash
python scripts/manhattan_ops_bench.py --families 10 20 50 --nights 5 --out /tmp/bench_ops.json   # ~3.5 min
OPENBLAS_NUM_THREADS=1 python -m manhattan.hte.bench --target 100000 --workers 4 --chunk 512 --out /tmp/hte_100k.json
python scripts/hte_accounting_bench.py --target 10000 --workers 4 --out /tmp/acct_10k.json
python -m pytest tests/test_manhattan_ops_bench.py -q   # smallest size, < 30 s
```
