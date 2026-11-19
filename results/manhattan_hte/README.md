# Manhattan HTE benchmark records (synthetic only)

Each JSON file in this directory is the raw output of one invocation of `python -m manhattan.hte.bench`. All of them
were run on **synthetic data** from `manhattan.hte.data.generate`. They are engineering measurements: wall time, CPU
time, memory, storage, cache counts and funnel counts. They say nothing about any market, and none of them is
evidence.

They were recorded at commit `4355fa1`, after the S10 corrections. Every positions-based return in them uses
same-close execution, so they measure throughput only.

The commands, the hardware and the interpretation are in
[docs/manhattan/hte/BENCHMARKS.md](../../docs/manhattan/hte/BENCHMARKS.md).

| file | workload | workers | stages |
|---|---|---|---|
| `bench_10k_w1.json` | 10,344 candidates | 1 | 0-4 |
| `bench_10k_w4.json` | 10,344 | 4 | 0-4 |
| `bench_10k_w4_nocache.json` | 10,344, feature cache off | 4 | 0-4 |
| `bench_100k_w4.json` | 99,552 | 4 | 0-4 |
| `bench_100k_w4_stage1.json` | 99,552 | 4 | 0-1 (cheap screen only) |
| `bench_1m_w4_stage1.json` | 1,024,272 | 4 | 0-1 |
| `bench_1m_w4.json` | 1,024,272 | 4 | 0-4 (genuine full run) |
| `existing_engine.json` | `manhattan.engine.backtest`, 5 strategies | 1 | its own model (status-quo comparison) |

These files are not written by any workflow, and no workflow reads them.
