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

## On the indexed ledger (PR #100), 21 November 2026

After PR #100 merged, this branch was merged with main (e194cb0). `_batch_state` and the cross-check now stream the
ledger with `Ledger.iter_records`. Everything below was measured in one container, one run at a time (4 logical
CPUs, slower than the machine used above). The first row is that machine's baseline: pre-#100 main with this
branch as first published.

| file | candidates | HTE run s | begin s | complete s | cross-check s | of which bridge s | of which PR #86 reconciler s | accounting / HTE run | ms per candidate | ledger MiB | ledger B per candidate | ledger records | outcome batches | peak RSS MiB | consistent |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `bench_10k_w4_before_pr100_same_machine.json` | 10,344 | 10.5 | 37.3 | 23.3 | 28.8 | 2.885 | 25.677 | 8.53× | 8.6 | 35.1 | 3,556 | 20,688 | 21 | 439 | yes |
| `bench_10k_w4_indexed.json` | 10,344 | 11.8 | 8.3 | 8.0 | 4.6 | 2.849 | 1.458 | 1.77× | 2.0 | 35.1 | 3,556 | 20,688 | 21 | 278 | yes |
| `bench_100k_w4_indexed.json` | 99,552 | 71.6 | 83.9 | 78.4 | 45.0 | 27.587 | 15.115 | 2.9× | 2.1 | 337.8 | 3,558 | 199,104 | 195 | 2,005 | yes |

| `bench_100k_w4_indexed_final.json` (head 393e3a6) | 99,552 | 60.5 | 83.4 | 74.2 | 58.5 | 38.265 | 17.044 | 3.57× | 2.2 | 337.8 | 3,558 | 199,104 | 195 | 2,468 | yes |

- **At 10k on the same machine:** accounting falls from 8.5× to 1.8× the HTE run (89.3 s to 20.9 s), and peak RSS from
  439 to 278 MiB.
- **At 100k:** accounting is 2.9× the HTE run (207 s), linear at about 2.1 ms per candidate, against 35.6× in the first
  published run above. Peak RSS falls from 3.5 to 2.0 GiB.
- Every run was consistent, with one PR #86 attempt per candidate, no reconciler violations and at most 512 rows per
  outcome batch.
- **Final head (393e3a6), after the fixes from the independent verification:** 216 s of accounting, 3.6× the HTE run.
  The cross-check now reads the ledger file instead of the caller's object, and every guard is re-checked on each
  operation. That adds about 13 s to the cross-check and 0.5 GiB to peak RSS (2.5 GiB): the cost of auditing the
  on-disk snapshot.
