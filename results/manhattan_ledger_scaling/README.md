# Manhattan ledger scaling: benchmarks

These are synthetic infrastructure measurements, not evidence. They were produced by
`scripts/ledger_scale_bench.py`, with temporary ledgers outside the repository, on the HTE-shaped workload:
- one schema-2 attempt per candidate on an 8.8-year exploration window;
- 1 candidate in 97 failed;
- 1 in 53 evaluated a second time (a rerun).

"Before" is main at 5e4765e. "After" is this branch at b10790d. Runs were one at a time on otherwise idle hardware:
4 logical CPUs (Xeon 2.3 GHz, AVX-512), 15.7 GiB RAM, Python 3.13.
- **Ledger memory** is the resident memory of the opened ledger(s), measured in a fresh process.
- **Accounting total** is register + complete + reconcile.
- **Looks** summed over the ledgers should equal the distinct evaluation keys. A larger sum means reruns were counted
  as new looks.

## Ledger alone

| implementation | candidates | register s | complete s | reopen s | reconcile s | accounting total s | µs per candidate | ledger memory MiB (B per candidate) | peak RSS MiB | looks summed / distinct keys | reconciler violations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| main (before) | 10,000 | 26.0 | 12.7 | 1.0 | 22.0 | 60.6 | 6,059 | 150.3 (15,758) | 237 | 9,896 / 9,896 | 0 |
| indexed (after) | 10,000 | 4.0 | 3.4 | 0.8 | 1.4 | 8.9 | 887 | 42.8 (4,486) | 98 | 9,896 / 9,896 | 0 |
| main (before) | 100,000 | 258.1 | 1,007.3 | 11.9 | 216.5 | 1,481.9 | 14,819 | 1,498.7 (15,715) | 1,782 | 98,969 / 98,969 | 0 |
| indexed (after) | 100,000 | 43.4 | 35.1 | 6.6 | 11.6 | 90.1 | 901 | 432.5 (4,536) | 713 | 98,969 / 98,969 | 0 |
| main, one ledger per 10k-candidate run | 100,000 | 252.1 | 131.6 | 11.7 | 217.6 | 601.3 | 6,013 | 1,304.4 (13,677) | 1,318 | 100,650 / 98,969 | 0 |
| main, 16 spec_hash shards | 100,000 | 261.2 | 263.1 | 10.5 | 212.6 | 736.9 | 7,369 | 1,283.4 (13,457) | 1,314 | 98,969 / 98,969 | 0 |
| indexed (after) | 1,000,000 | 394.2 | 334.6 | 69.3 | 115.8 | 844.5 | 845 | 4,263.8 (4,471) | 6,776 | 989,690 / 989,690 | 0 |

- **Linear after the change.** The cost per candidate is 887, 901 and 845 µs at 10k, 100k and 1M. On main it grows
  with size (6,059 → 14,819 µs from 10k to 100k), because completion is quadratic (12.7 s → 1,007 s).
- **At 100k:** accounting time falls 16× (1,482 s → 90 s), completion 29×, registration 6×, the reconciler 19×.
  Ledger memory falls 3.5× (15.7 → 4.5 kB per candidate) and peak RSS 2.5×.
- **At 1M:** accounting takes 845 s (14 min). Ledger memory is 4.2 GiB; peak RSS is 6.6 GiB, which includes the
  reconciler's snapshot of the 2.9 GB file. Main was not run at 1M. Its completion is quadratic (about 100 × 1,007 s,
  roughly 28 hours), and its ledger would need about 15 GiB of memory, all of this machine's RAM.
- **One ledger per run (main, 10k-candidate runs):** about 2.5× faster than one main ledger, because completion is
  quadratic only within each run. But it **counts 1,681 reruns as new looks** (100,650 against 98,969 keys), and the
  per-ledger reconcilers report nothing wrong, because each ledger is consistent on its own.
- **16 spec_hash shards (main):** the looks are correct, but it is still 8× slower than the indexed ledger.
  Completion improves only 4×, and registration and the reconciler not at all. D-6 and the anchors would also
  have to span 16 files.

## End to end: PR #98's bridge at 100k candidates

`bridge_100k_indexed.json` is `scripts/hte_accounting_bench.py` (PR #98) run on this branch merged with PR #98. The
"before" row is PR #98's own result on the old ledger (`results/manhattan_hte_accounting/bench_100k_w4.json` there).

| ledger | candidates | HTE run s | begin s | complete s | cross-check s (of which PR #86 reconciler) | accounting s | accounting / HTE run | peak RSS MiB | consistent |
|---|---|---|---|---|---|---|---|---|---|
| main (PR #98 as published) | 99,552 | 44.0 | 258.4 | 1,083.7 | 226.6 (203.4) | 1,568.7 | 35.6× | 3,538 | yes |
| indexed (this branch + PR #98) | 99,552 | 47.2 | 51.2 | 51.1 | 39.7 (12.3) | 142.1 | 3.0× | 2,760 | yes |

The remaining 24 s of the cross-check are PR #98's own checks. Every attempt completed as an `evaluation`, with no
reconciler violations.
