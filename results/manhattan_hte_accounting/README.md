# HTE → PR #86 accounting bridge: benchmark

Synthetic infrastructure measurement only (PR #84: `E_INFRA`). These are not results and not evidence. They were made
by `scripts/hte_accounting_bench.py` (`--workers 4 --chunk 512`, `OPENBLAS_NUM_THREADS=1`) on the integration of PRs
#84–#87, #89, #90 and this branch. The run used a temporary PR #86 ledger outside the repository, the synthetic panel
(`manhattan.hte.data.PanelParams()`, exploration window only) and a completion writer supplied by the script (owner
decision A-1). Hardware: 4 logical CPUs (Xeon 2.3 GHz, AVX-512), 15.7 GiB RAM, Python 3.13, NumPy 2.5, OpenBLAS.

| file | candidates | HTE run s | begin s | complete s | cross-check s | of which bridge s | of which PR #86 reconciler s | accounting / HTE run | ms per candidate | ledger MiB | ledger B per candidate | ledger records | outcome batches | peak RSS MiB | consistent |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `bench_2k_w4.json` | 1,800 | 2.4 | 4.4 | 1.2 | 4.3 | – | – | 4.1× | 5.5 | 6.1 | 3,555 | 3,600 | 4 | 147 | yes |
| `bench_10k_w4.json` | 10,344 | 8.1 | 30.4 | 15.1 | 24.6 | 2.2 | 22.2 | 8.7× | 6.8 | 35.1 | 3,556 | 20,688 | 21 | 438 | yes |
| `bench_100k_w4.json` | 99,552 | 44.0 | 258.4 | 1,083.7 | 226.6 | 21.4 | 203.4 | 35.6× | 15.8 | 337.8 | 3,558 | 199,104 | 195 | 3,538 | yes |

All three runs have every attempt completed as a PR #86 `evaluation`, no reconciler violations, outcome batches of at
most 512 rows, and the units kept apart. At 100k there are 343 HTE chunk attempts and 99,552 PR #86 attempts and looks,
over 24,888 variants, 15 hypotheses and 5 families.

Reading:

- **Linear parts.** Registration (`begin`) costs about 2.6 ms per candidate at every size. Most of it is PR #86's
  `access.check_declaration`, which runs over the 8.8-year window for each attempt. The bridge's own cross-check
  checks cost about 0.2 ms per candidate. Outcome batches and the registration file add about 0.5 kB per
  candidate, beside 3.56 kB per candidate of PR #86 ledger.
- **Quadratic part.** `complete` grows from 15 s at 10k to 1,084 s at 100k (×72 for ×9.6 candidates). Each
  `Ledger.record_evaluation` scans every earlier evaluation for its `data_changed` rule; this is PR #86 code, found by
  profiling. That is owner decision A-2: one ledger per run, sharding by `spec_hash` prefix, or an index in PR #86.
- **Memory.** Peak RSS at 100k is 3.5 GiB, mostly PR #86 ledger records held in memory, and it grows with the ledger.
- **A first 100k run is superseded.** Its cross-check took 4,197 s because two sets were rebuilt inside loops in the
  bridge's own cross-check (fixed in commit 9ddb701). Its other steps and its consistency matched this run.
