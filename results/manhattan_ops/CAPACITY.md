# Manhattan ops: capacity measurements

Measured by `python -m manhattan.ops.capacity` (session 7M). Synthetic data: six instruments, sessions
2005-01-03 to 2019-12-31. Each line is one fresh process. **Measurements only; nothing is extrapolated.**

Machine: 4 CPUs, Python 3.13.18, Linux-6.18.44-fc-v445-x86_64-with-glibc2.39

## Full backtest and nightly increment (engine)

| mode | executables | workers | wall (s) | CPU (s) | CPU per executable (ms) | peak RSS, largest process (MiB) |
|---|---|---|---|---|---|---|
| full | 1,000 | 4 | 57.22 | 202.82 | 202.8 | 47.0 |
| full | 10,000 | 4 | 582.2 | 2,211.38 | 221.1 | 47.1 |
| full | 100,000 | 4 | 6,127.94 | 23,821.7 | 238.2 | 48.2 |
| daily | 1,000 | 4 | 1.87 | 5.33 | 5.3 | 44.2 |
| daily | 10,000 | 4 | 25.99 | 98.88 | 9.9 | 44.3 |
| daily | 100,000 | 4 | 264.86 | 1,018.86 | 10.2 | 45.5 |

## Private-ledger write of one nightly increment

| observation records | write through the journal (s) | fresh clone, open and verify (s) | chain size (MB) | peak RSS (MiB) |
|---|---|---|---|---|
| 1,000 | 0.43 | 0.08 | 0.6 | 45.8 |
| 10,000 | 2.47 | 0.4 | 6.2 | 131.7 |
| 100,000 | 26.02 | 3.9 | 61.9 | 951.4 |

Definitions: **full** compiles each executable and backtests it over the whole window, as screening
would. **daily** compiles each executable and runs it over its forward window (warm-up plus one new
session), as the runner does each night, and builds the new day's payload. **ledger** writes that many
observation records to a local bare repository through the write-ahead journal and then opens and
verifies a fresh clone; a real push adds network time. Executables cycle through every signal kind at
its natural frequency (daily, weekly, monthly, event) with distinct parameters, both sizing rules and two
cost models.
