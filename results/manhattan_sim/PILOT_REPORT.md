# Manhattan simulation: PILOT report (nothing here is decided)

Written 2026-11-12 12:21 UTC by `python -m manhattan.sim.report`. **Synthetic data only: nothing in this file is market evidence.**

- Pre-registration: `docs/manhattan/SIM_PREREG.md`, SHA-256 `e4bbcc44bebbc601b8bccc0e609131ad5185982f3047108dfaaf2fe2908c21e6` (never edited).
- Method under test: `docs/manhattan/PROTOCOL_v3.md` 3.0.0, SHA-256 `4fbb5c72ad7214710aea7417fbf2fe131edb56f4eb83bffccac97478472f3a9f` (the pre-rename hash named in SIM_PREREG.md is the same text before the project was renamed).
- Development scenarios only (seed branch 0). Held-out scenarios run: **none**.
- **This is a pilot.** Replication counts are below those pre-registered, so every verdict below reads "pilot: not decided". "within" or "outside" only says where the interval sits so far. No method is selected, no claim is enabled, and `claims.enabled` stays false.

## Runs and shortfall

| scenario | size | replications run | pre-registered | shortfall | code | seconds per replication |
|---|---|---|---|---|---|---|
| D01 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 128 |
| D02 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 135 |
| D03 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 152 |
| D04 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 202 |
| D05 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 209 |
| D06 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 67 |
| D07a | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 103 |
| D07b | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 111 |
| D08 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 119 |
| D09a | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 71 |
| D09b | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 355 |
| D11 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 127 |
| P1 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 102 |
| P2 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 103 |
| P3 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 71 |
| P4 | STD | 12 | 2000 | 1988 | `da641c096d17bbf4` | 69 |
| D01 | LONG | 6 | 2000 | 1994 | `da641c096d17bbf4` | 77 |
| D02 | LONG | 6 | 2000 | 1994 | `da641c096d17bbf4` | 80 |
| D01 | HB | 0 | 400 | 400 | - | - |
| D02 | HB | 0 | 400 | 400 | - | - |
| D05 | HB | 0 | 400 | 400 | - | - |
| D08 | HB | 0 | 400 | 400 | - | - |
| D10 | HB | 0 | 400 | 400 | - | - |

Remaining cost of the development runs that have a timing above: about **1259 CPU-hours** (one core; divide by the number of cores). Held-out scenarios are extra. Seconds are wall-clock per replication inside a worker and are inflated whenever more jobs than cores run at once; on an idle core a STD replication of a default scenario took about 60 seconds.

## Results by scenario

### D01 at STD: no edges (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0833 | -0.0800 to 0.2467 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.2500 | -0.0059 to 0.5059 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2332 | 0.1927 to 0.2737 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0616 | 0.0425 to 0.0808 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0017 | 0.0003 to 0.0037 | 5735 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0615 | 0.0423 to 0.0807 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0677 | 0.0480 to 0.0874 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0615 | 0.0423 to 0.0807 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (3 families passed) | 0.2500 | -0.0059 to 0.5059 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0037 | 0.0020 to 0.0053 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0005 | 0.0001 to 0.0009 | 12 | upper bound ≤ 0.015 | yes | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | screening power, candidate (ii) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by E-ALL | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | median years from freeze to formal support, enrolment by E-ALL | - | - | 0 | - | no | reported |
| cost | seconds per replication | 128.3975 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2088.9454 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9685 | - | 12 | - | no | reported |
| info | families per replication | 477.9167 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | 477.9 / 0.2 / 0.0 |

### D02 at STD: rare edges (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.1864 | 0.1589 to 0.2140 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05 | 0.0456 | 0.0322 to 0.0589 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0009 | 0.0004 to 0.0014 | 5657 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0455 | 0.0322 to 0.0587 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0505 | 0.0371 to 0.0639 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0456 | 0.0322 to 0.0589 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (27 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0020 | 0.0014 to 0.0026 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0001 | -0.0001 to 0.0002 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2288 | 0.1626 to 0.2946 | 118 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 118 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0652 | 0.0000 to 0.1364 | 46 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 6.5080 | - | 3 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 46 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 134.7533 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 1938.5278 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9685 | - | 12 | - | no | reported |
| info | families per replication | 481.2500 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 2.2 / 0.0 |

### D03 at STD: correlated variants (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0417 | -0.0400 to 0.1233 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0972 | -0.0050 to 0.1994 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0724 | -0.0024 to 0.1472 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2060 | 0.1840 to 0.2280 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0504 | 0.0411 to 0.0598 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0015 | 0.0007 to 0.0024 | 5481 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0492 | 0.0399 to 0.0585 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0570 | 0.0468 to 0.0671 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0503 | 0.0409 to 0.0596 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (63 families passed) | 0.0724 | -0.0024 to 0.1472 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (1 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0041 | 0.0024 to 0.0058 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0005 | 0.0001 to 0.0010 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.1960 | 0.1463 to 0.2530 | 301 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0033 | 0.0000 to 0.0109 | 301 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0441 | 0.0000 to 0.1228 | 68 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 7.3410 | - | 3 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 68 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 152.2567 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2206.8187 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9682 | - | 12 | - | no | reported |
| info | families per replication | 481.8333 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 5.2 / 0.1 |

### D04 at STD: correlated families (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0648 | -0.0622 to 0.1919 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0583 | -0.0560 to 0.1727 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0702 | -0.0444 to 0.1848 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.1397 | 0.0724 to 0.2070 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05 | 0.0362 | 0.0080 to 0.0643 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0013 | 0.0000 to 0.0035 | 5524 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0364 | 0.0084 to 0.0644 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0363 | 0.0083 to 0.0644 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0362 | 0.0080 to 0.0643 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (43 families passed) | 0.0786 | -0.0521 to 0.2092 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (1 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0022 | 0.0004 to 0.0041 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0001 | -0.0001 to 0.0004 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.1346 | 0.0775 to 0.1993 | 260 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0038 | 0.0000 to 0.0123 | 260 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0000 | 0.0000 to 0.0000 | 64 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 64 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by E-ALL | 0.0156 | 0.0000 to 0.0462 | 64 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by E-ALL | 9.1870 | - | 1 | - | no | reported |
| cost | seconds per replication | 201.5625 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 1829.0661 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9692 | - | 12 | - | no | reported |
| info | families per replication | 482.0000 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | 482.0 / 3.6 / 0.1 |

### D05 at STD: fat tails (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0208 | -0.0200 to 0.0617 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0167 | -0.0160 to 0.0493 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0238 | -0.0229 to 0.0705 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2139 | 0.1784 to 0.2493 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0495 | 0.0380 to 0.0609 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0019 | 5510 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0491 | 0.0376 to 0.0606 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0549 | 0.0428 to 0.0670 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0495 | 0.0380 to 0.0609 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (75 families passed) | 0.0238 | -0.0229 to 0.0705 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (10 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0037 | 0.0020 to 0.0054 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0003 | -0.0000 to 0.0006 | 12 | upper bound ≤ 0.015 | yes | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2589 | 0.1956 to 0.3346 | 282 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0355 | 0.0073 to 0.0684 | 282 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0469 | 0.0130 to 0.1017 | 64 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 7.6190 | - | 3 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 64 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 208.9458 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2207.3251 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9715 | - | 12 | - | no | reported |
| info | families per replication | 482.6667 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 6.2 / 0.8 |

### D06 at STD: volatility clustering (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.1755 | 0.1475 to 0.2034 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05 | 0.0391 | 0.0280 to 0.0503 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0015 | 5503 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0397 | 0.0286 to 0.0508 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0433 | 0.0314 to 0.0553 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0391 | 0.0280 to 0.0503 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (52 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (6 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0029 | 0.0016 to 0.0043 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0002 | -0.0000 to 0.0004 | 12 | upper bound ≤ 0.015 | yes | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.1640 | 0.1265 to 0.2049 | 317 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0189 | 0.0031 to 0.0400 | 317 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0658 | 0.0238 to 0.1212 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 6.5280 | - | 5 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0132 | 0.0000 to 0.0448 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 6.2300 | - | 1 | - | no | reported |
| cost | seconds per replication | 66.9217 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2014.3098 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9504 | - | 12 | - | no | reported |
| info | families per replication | 485.0000 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 4.3 / 0.5 |

### D07a at STD: serial correlation +0.2 (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.1111 | -0.0563 to 0.2785 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by E-ALL, year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2246 | 0.1892 to 0.2600 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0595 | 0.0435 to 0.0755 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0013 | 0.0004 to 0.0024 | 5486 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0587 | 0.0430 to 0.0745 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0634 | 0.0470 to 0.0797 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0595 | 0.0435 to 0.0755 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (39 families passed) | 0.1111 | -0.0563 to 0.2785 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0024 | 0.0012 to 0.0037 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0002 | 0.0000 to 0.0005 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.1294 | 0.0935 to 0.1655 | 286 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 286 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0000 | 0.0000 to 0.0000 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by E-ALL | 0.0000 | 0.0000 to 0.0000 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by E-ALL | - | - | 0 | - | no | reported |
| cost | seconds per replication | 102.6583 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2288.2635 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.4349 | - | 12 | - | no | reported |
| info | families per replication | 481.0000 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | 481.0 / 3.2 / 0.0 |

### D07b at STD: serial correlation -0.2 (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0167 | -0.0160 to 0.0493 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0563 | -0.0060 to 0.1187 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0377 | -0.0062 to 0.0815 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.1939 | 0.1596 to 0.2281 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0510 | 0.0360 to 0.0660 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0007 | 0.0002 to 0.0015 | 5457 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0500 | 0.0350 to 0.0649 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0559 | 0.0410 to 0.0709 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0510 | 0.0360 to 0.0660 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (91 families passed) | 0.0377 | -0.0062 to 0.0815 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (5 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0011 | -0.0001 to 0.0023 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0001 | -0.0001 to 0.0004 | 12 | upper bound ≤ 0.015 | yes | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2767 | 0.2110 to 0.3378 | 318 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0157 | 0.0000 to 0.0361 | 318 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.1190 | 0.0541 to 0.1765 | 84 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 7.8675 | - | 10 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0119 | 0.0000 to 0.0417 | 84 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 8.8490 | - | 1 | - | no | reported |
| cost | seconds per replication | 111.0775 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2172.1816 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9999 | - | 12 | - | no | reported |
| info | families per replication | 481.2500 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 7.6 / 0.4 |

### D08 at STD: historical selection bias (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0046 | -0.0044 to 0.0137 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0227 | 0.0111 to 0.0343 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0264 | 0.0139 to 0.0389 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2060 | 0.1729 to 0.2391 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0486 | 0.0345 to 0.0627 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0019 | 0.0008 to 0.0030 | 3766 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0496 | 0.0348 to 0.0645 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0547 | 0.0398 to 0.0697 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0486 | 0.0345 to 0.0627 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (1070 families passed) | 0.0295 | 0.0144 to 0.0445 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M4 | linked average error, candidate (ii) (266 families passed) | 0.0060 | -0.0002 to 0.0122 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 20 | 0.0049 | 0.0013 to 0.0086 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0004 | 0.0000 to 0.0008 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.5290 | 0.4679 to 0.5888 | 1964 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.1354 | 0.0860 to 0.1847 | 1964 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.1890 | 0.1140 to 0.2638 | 455 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 7.0735 | - | 86 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0330 | 0.0159 to 0.0493 | 455 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 6.7260 | - | 15 | - | no | reported |
| cost | seconds per replication | 119.2875 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 4235.8778 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9688 | - | 12 | - | no | reported |
| info | families per replication | 477.5000 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 89.2 / 22.2 |

### D09a at STD: adaptive variants from the exploration window (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0083 | -0.0080 to 0.0247 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2221 | 0.1869 to 0.2572 | 12 | upper bound ≤ 0.22 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0620 | 0.0451 to 0.0788 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0009 | 0.0000 to 0.0022 | 5457 | upper bound ≤ 0.0015 | no | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0614 | 0.0448 to 0.0780 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0682 | 0.0514 to 0.0850 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0620 | 0.0451 to 0.0788 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (73 families passed) | 0.0083 | -0.0080 to 0.0247 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (7 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0038 | 0.0023 to 0.0053 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0003 | 0.0000 to 0.0006 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2590 | 0.1954 to 0.3180 | 278 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0252 | 0.0038 to 0.0565 | 278 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0658 | 0.0137 to 0.1344 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 8.0750 | - | 5 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0132 | 0.0000 to 0.0421 | 76 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 6.0120 | - | 1 | - | no | reported |
| cost | seconds per replication | 70.5317 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2294.4422 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9682 | - | 12 | - | no | reported |
| info | families per replication | 477.9167 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 6.1 / 0.6 |

### D09b at STD: adaptive variants from the reserve window (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0208 | -0.0200 to 0.0617 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0208 | -0.0200 to 0.0617 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2198 | 0.1817 to 0.2580 | 12 | upper bound ≤ 0.22 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0566 | 0.0426 to 0.0706 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0009 | 0.0002 to 0.0021 | 5402 | upper bound ≤ 0.0015 | no | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0564 | 0.0423 to 0.0705 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0629 | 0.0481 to 0.0778 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0566 | 0.0426 to 0.0706 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (58 families passed) | 0.0208 | -0.0200 to 0.0617 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (8 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0048 | 0.0019 to 0.0077 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0004 | -0.0004 to 0.0013 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2090 | 0.1673 to 0.2465 | 268 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0299 | 0.0081 to 0.0520 | 268 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0725 | 0.0000 to 0.1622 | 69 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 8.6510 | - | 5 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0145 | 0.0000 to 0.0441 | 69 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 8.7500 | - | 1 | - | no | reported |
| M11 | adaptive SPA size at 0.05 on the full set | 0.3435 | 0.3075 to 0.3796 | 12 | if upper bound > 0.06: label | yes | pilot: not decided |
| cost | seconds per replication | 355.1783 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2260.7269 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9684 | - | 12 | - | no | reported |
| info | families per replication | 472.5000 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 4.8 / 0.7 |

### D11 at STD: hedge estimation (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0722 | -0.0040 to 0.1484 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0772 | 0.0084 to 0.1460 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0718 | 0.0068 to 0.1368 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2686 | 0.2340 to 0.3031 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0774 | 0.0611 to 0.0937 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0030 | 0.0013 to 0.0053 | 5358 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0768 | 0.0606 to 0.0930 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0845 | 0.0679 to 0.1012 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0772 | 0.0611 to 0.0934 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (79 families passed) | 0.0718 | 0.0068 to 0.1368 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (4 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0075 | 0.0052 to 0.0099 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0008 | 0.0001 to 0.0016 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2326 | 0.1875 to 0.2832 | 301 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0133 | 0.0000 to 0.0296 | 301 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0370 | 0.0000 to 0.0746 | 81 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 8.7500 | - | 3 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 81 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 126.7483 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2567.2623 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9694 | - | 12 | - | no | reported |
| info | families per replication | 471.5833 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 6.6 / 0.3 |

### P1 at STD: power, both hypotheses at 0.5 (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0833 | -0.0800 to 0.2467 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.1667 | -0.0536 to 0.3869 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.2083 | -0.0160 to 0.4327 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2211 | 0.1782 to 0.2639 | 12 | upper bound ≤ 0.22 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0622 | 0.0448 to 0.0797 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0009 | 0.0002 to 0.0018 | 5525 | upper bound ≤ 0.0015 | no | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0622 | 0.0448 to 0.0797 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0692 | 0.0524 to 0.0859 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0622 | 0.0448 to 0.0797 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (8 families passed) | 0.2083 | -0.0160 to 0.4327 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0034 | 0.0017 to 0.0051 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0004 | -0.0001 to 0.0008 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.0178 | 0.0034 to 0.0352 | 281 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 281 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0000 | 0.0000 to 0.0000 | 58 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 58 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 101.5808 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2177.5599 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9688 | - | 12 | - | no | reported |
| info | families per replication | 483.8333 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 0.7 / 0.0 |

### P2 at STD: power, both hypotheses at 1.0 (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0625 | -0.0254 to 0.1504 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0884 | -0.0004 to 0.1772 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.1955 | 0.1722 to 0.2189 | 12 | upper bound ≤ 0.22 | no | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05 | 0.0483 | 0.0380 to 0.0586 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0009 | 0.0004 to 0.0015 | 5414 | upper bound ≤ 0.0015 | no | pilot: not decided (within threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0483 | 0.0380 to 0.0586 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0544 | 0.0444 to 0.0644 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0483 | 0.0380 to 0.0586 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (49 families passed) | 0.0884 | -0.0004 to 0.1772 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0020 | 0.0007 to 0.0034 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0001 | -0.0001 to 0.0002 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.1692 | 0.1193 to 0.2222 | 266 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 266 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0161 | 0.0000 to 0.0508 | 62 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 8.3930 | - | 1 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 62 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 103.1233 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2196.2633 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9679 | - | 12 | - | no | reported |
| info | families per replication | 473.3333 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 4.1 / 0.0 |

### P3 at STD: power, both hypotheses at 1.5 (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0778 | 0.0067 to 0.1488 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0389 | 0.0037 to 0.0742 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0314 | 0.0058 to 0.0569 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2025 | 0.1545 to 0.2506 | 12 | upper bound ≤ 0.22 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0562 | 0.0385 to 0.0738 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0011 | 0.0002 to 0.0022 | 5481 | upper bound ≤ 0.0015 | no | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0560 | 0.0384 to 0.0736 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0613 | 0.0424 to 0.0802 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0560 | 0.0384 to 0.0736 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (213 families passed) | 0.0314 | 0.0058 to 0.0569 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M4 | linked average error, candidate (ii) (85 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0044 | 0.0028 to 0.0060 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0002 | -0.0000 to 0.0005 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.7203 | 0.6198 to 0.8155 | 286 | lower bound ≥ 0.5 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (ii) | 0.2972 | 0.1702 to 0.4180 | 286 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.6230 | 0.4627 to 0.7581 | 61 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 6.0120 | - | 38 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.1803 | 0.0645 to 0.2969 | 61 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 5.2380 | - | 11 | - | no | reported |
| cost | seconds per replication | 70.7483 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2384.6981 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9689 | - | 12 | - | no | reported |
| info | families per replication | 480.5833 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 17.8 / 7.1 |

### P4 at STD: power, both hypotheses at 2.5 (12 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2003 | 0.1615 to 0.2391 | 12 | upper bound ≤ 0.22 | no | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0476 | 0.0353 to 0.0599 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0002 | 0.0000 to 0.0005 | 5486 | upper bound ≤ 0.0015 | no | pilot: not decided (within threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0476 | 0.0353 to 0.0599 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0538 | 0.0409 to 0.0668 | 12 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0476 | 0.0353 to 0.0599 | 12 | - | no | reported |
| M4 | linked average error, candidate (i) (284 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M4 | linked average error, candidate (ii) (281 families passed) | 0.0000 | 0.0000 to 0.0000 | 12 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 20 | 0.0028 | 0.0014 to 0.0041 | 12 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0001 | -0.0000 to 0.0003 | 12 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 1.0000 | 1.0000 to 1.0000 | 284 | lower bound ≥ 0.5 | yes | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (ii) | 0.9894 | 0.9779 to 1.0000 | 284 | lower bound ≥ 0.5 | yes | pilot: not decided (within threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 1.0000 | 1.0000 to 1.0000 | 72 | lower bound ≥ 0.5 | yes | pilot: not decided (within threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 3.7400 | - | 72 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.9583 | 0.9153 to 1.0000 | 72 | lower bound ≥ 0.5 | yes | pilot: not decided (within threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | 3.7500 | - | 69 | - | no | reported |
| cost | seconds per replication | 68.8467 | - | 12 | - | no | reported |
| cost | mean bootstrap resamples per family | 2305.6369 | - | 12 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9689 | - | 12 | - | no | reported |
| info | families per replication | 480.8333 | - | 12 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 12 | - | no | - / 23.7 / 23.4 |

### D01 at LONG: no edges (6 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 25 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 50 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 100 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 25 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 50 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 100 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2082 | 0.1691 to 0.2472 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0547 | 0.0389 to 0.0704 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0014 | 0.0008 to 0.0017 | 3594 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0547 | 0.0389 to 0.0704 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0630 | 0.0473 to 0.0788 | 6 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0547 | 0.0389 to 0.0704 | 6 | - | no | reported |
| M4 | linked average error, candidate (i) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0040 | 0.0021 to 0.0059 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0004 | -0.0002 to 0.0009 | 6 | upper bound ≤ 0.015 | yes | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | screening power, candidate (ii) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | - | - | 0 | lower bound ≥ 0.5 | no | no data |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 76.6933 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family | 1995.1972 | - | 6 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9687 | - | 6 | - | no | reported |
| info | families per replication | 599.0000 | - | 6 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 6 | - | no | - / 0.0 / 0.0 |

### D02 at LONG: rare edges (6 of 2000 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 25 | 0.1667 | -0.1600 to 0.4933 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (i), batch 50 | 0.0833 | -0.0800 to 0.2467 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M1 | screening FDR, candidate (i), batch 100 | 0.0571 | -0.0152 to 0.1294 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 25 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 50 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 100 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.2219 | 0.1915 to 0.2523 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05 | 0.0640 | 0.0503 to 0.0776 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0014 | 0.0006 to 0.0023 | 3477 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0633 | 0.0497 to 0.0768 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0700 | 0.0551 to 0.0850 | 6 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0640 | 0.0503 to 0.0776 | 6 | - | no | reported |
| M4 | linked average error, candidate (i) (20 families passed) | 0.0571 | -0.0152 to 0.1294 | 6 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (2 families passed) | 0.0000 | 0.0000 to 0.0000 | 6 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0055 | 0.0039 to 0.0072 | 6 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0005 | 0.0001 to 0.0008 | 6 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.2222 | 0.1447 to 0.3125 | 81 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0247 | 0.0000 to 0.0541 | 81 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0000 | 0.0000 to 0.0000 | 21 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | - | - | 0 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 21 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 79.6017 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family | 2159.7419 | - | 6 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9677 | - | 6 | - | no | reported |
| info | families per replication | 593.0000 | - | 6 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 6 | - | no | - / 3.3 / 0.3 |

## Selection rule (SIM_PREREG section 7): numbers only

| scenario | screening power, candidate (i) | candidate (ii) |
|---|---|---|
| P1 | 0.018 | 0.000 |
| P2 | 0.169 | 0.000 |
| P3 | 0.720 | 0.297 |
| P4 | 1.000 | 0.989 |
| **average** | **0.477** | **0.322** |

Difference (i) − (ii): +0.155, 95% bootstrap interval +0.132 to +0.180. The rule chooses (i) only if both are eligible, the difference is at least 0.05 and the interval excludes zero; otherwise (ii). **The choice is made once, after the first confirmation run with an eligible candidate; it is not made here.**

## Criterion V10(a): blind statistics with and without the adaptive channel

- D09a: designated blind p-values and e-values of 80 families (first 3 batches of 2 replications at STD) are **bit-for-bit identical** with and without the adaptive channel.
- D09b: designated blind p-values and e-values of 74 families (first 3 batches of 2 replications at STD) are **bit-for-bit identical** with and without the adaptive channel.

This is a property of the code (the adaptive channel has its own random stream and never touches the frozen grid), so a few batches show it as well as 2,000 replications would; `tests/test_manhattan_sim_pipeline.py` checks it on every test run.

## Deviations from, and readings of, SIM_PREREG.md

Every place where the code had to fix a detail the pre-registration leaves open, or departs from it.

- **Replications.** Pilot runs use fewer replications than section 6 fixes (2,000 at STD and LONG, 400 at HB). No criterion is decided on them. The shortfall per run is in the table below.
- **Held-out scenarios.** None was run. Their worlds (H01-H11) are not coded yet; the runner refuses them outside a tagged confirmation run and logs the refusal.
- **Freeze dates (§2.1).** Batch b (from 0) is frozen on day 5·⌊504·b/B⌋: equal intervals to the week, first batch on day 0, so that weeks line up across families and the last batch has a forward life.
- **Reviews and enrolment (§2.5).** Quarterly reviews are every 63 days from day 63. A family that passed screening is enrolled at the first review on or after its freeze and its test starts with the first week beginning on or after that review. E-ALL enrols at the freeze.
- **Settlement lag.** A week's return enters the forward process one week after the week ends (Protocol v3 §6.6), so a rejection is dated two weeks after the start of the week that produced it; a rejection that would be known only after day 2,520 is not counted.
- **Scale (Protocol §2.4).** Every executable's declared volatility target is 1 a day (the simulated unit), so the daily scale floor is 0.5. The EWMA standard deviation is taken about zero with weights renormalised over the days available. The weekly scale is √5 times the daily scale on the week's first day (which uses earlier days only).
- **SPA sensitivity.** p-values at L/2 and 2L are not computed (Protocol §5.2 says they decide nothing).
- **Edges (§2.3).** θ_h is drawn independently for each hypothesis that has the edge. Under D06 a family's true Sharpe ratio uses the realised mean of σ over its forward days.
- **D08.** Each of the 20 pool draws is a full default draw (5% have an edge), so selection also concentrates real edges; the score is the family portfolio's sample Sharpe ratio on the 1,260 exploration days.
- **D09.** An adaptive copy has the copied variant's true edge and correlation 0.9 with its noise; 'best so far' is by sample Sharpe ratio on the window the channel sees, among the hypothesis's frozen and adaptive variants. M11's truth label requires the adaptive variants to be null as well.
- **D10.** Retention multiplies positive edges only; variants with no edge keep a mean of −0.2 forward.
- **D11.** One core factor for the whole programme with daily volatility 1 and Sharpe ratio 0.6; one β path per hypothesis, started at 0.5; hedge trading cost 0 (returns are net by assumption, §10.6); no hedge in a family's first 252 days.
- **M3 Romano-Wolf.** The family-wise rate is the share of families with at least one no-edge variant in which the step-down at 0.05 names a no-edge variant.
- **M5.** A component's wealth is its tracking wealth from the freeze over its whole forward life, for every family (enrolled or not).
- **M6.** Years to formal support are counted from the freeze. Forward power's denominator is every family that is not forward-null and was frozen before day 630, enrolled or not.
- **HB: estimates and covariances (Protocol §7.1).** Standard errors from a joint stationary bootstrap per batch (199 resamples). Correlations are the sample correlation of returns over common dates times the share of common dates, shrunk half-way to zero: one joint bootstrap across batches is not possible, their windows differ. A hypothesis has a forward estimate once its family has 63 forward days.
- **HB: mechanism classes.** Three classes assigned at random at freeze (the truth has none, §2.3).
- **HB: sampling coordinates.** δ_h, A_f and ρ_f are sampled through exact changes of variable (quantile tables for the two mixtures; a standardised logit for retention) because the model does not mix in its original coordinates. The priors are unchanged up to the tables' interpolation error.
- **HB: a review needs all six fits.** If any of S0-S5 fails the gate (R̂ ≤ 1.01 for every parameter, effective sample size ≥ 400, no divergence) the review is 'model not converged' and changes no tier.
- **HB: dormancy forecast (Protocol §9.1).** PP_f is computed by a normal update of each model's current posterior with simulated future records, not by refitting the model on each simulated future; not evaluated at the last date.
- **HB: naive estimate (M9).** The largest sample Sharpe ratio among the family's variants, each over all its data up to the evaluation date.
- **Unlogged debug runs.** Before the runner existed, replication 0 of D01 and of P3 at STD was run once each on uncommitted code; this is recorded as a note in runs.jsonl.

## Every run on record

From `results/manhattan_sim/runs.jsonl` (start and end records; a start with no end is an abandoned run).

| time (UTC) | run | event | scenario | size | label | held-out set | replications | status | commit |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-12T09:09:58Z | note-0001 | note | D01,P3 | STD | debug | - | 1/1 | note | `dfa29c0` |
| 2026-11-12T09:10:05Z | aed5033dd607 | start | D01 | STD | pilot | - | 0/12 | started | `d48ac6e` |
| 2026-11-12T09:18:56Z | aed5033dd607 | end | D01 | STD | pilot | - | 12/12 | completed | `d48ac6e` |
| 2026-11-12T09:18:56Z | 1968f93af49e | start | D02 | STD | pilot | - | 0/12 | started | `d48ac6e` (dirty) |
| 2026-11-12T09:28:26Z | 1968f93af49e | end | D02 | STD | pilot | - | 12/12 | completed | `d48ac6e` (dirty) |
| 2026-11-12T09:28:26Z | 54b8fca7220b | start | D03 | STD | pilot | - | 0/12 | started | `d48ac6e` (dirty) |
| 2026-11-12T09:39:02Z | 54b8fca7220b | end | D03 | STD | pilot | - | 12/12 | completed | `d48ac6e` (dirty) |
| 2026-11-12T09:39:02Z | 489222f085d4 | start | D04 | STD | pilot | - | 0/12 | started | `d48ac6e` (dirty) |
| 2026-11-12T09:52:50Z | 489222f085d4 | end | D04 | STD | pilot | - | 12/12 | completed | `d48ac6e` (dirty) |
| 2026-11-12T09:52:50Z | 98e9d5d6ea6b | start | D05 | STD | pilot | - | 0/12 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | 9ea84b59c243 | start | D01 | STD | pilot | - | 0/0 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | 9ea84b59c243 | end | D01 | STD | pilot | - | 0/0 | completed | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | d0714286f27f | start | D02 | STD | pilot | - | 0/0 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | d0714286f27f | end | D02 | STD | pilot | - | 0/0 | completed | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | 1208d6229ff4 | start | D03 | STD | pilot | - | 0/0 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | 1208d6229ff4 | end | D03 | STD | pilot | - | 0/0 | completed | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | 088d8129e676 | start | D04 | STD | pilot | - | 0/0 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | 088d8129e676 | end | D04 | STD | pilot | - | 0/0 | completed | `d48ac6e` (dirty) |
| 2026-11-12T10:08:05Z | be050d81cd69 | start | D05 | STD | pilot | - | 0/1 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:09:10Z | be050d81cd69 | end | D05 | STD | pilot | - | 1/1 | completed | `d48ac6e` (dirty) |
| 2026-11-12T10:09:10Z | c288852bc70f | start | D06 | STD | pilot | - | 0/12 | started | `d48ac6e` (dirty) |
| 2026-11-12T10:11:30Z | 2986b4f41989 | start | D09a | STD | v10a-check | - | 0/2 | started | `c0b68db` (dirty) |
| 2026-11-12T10:11:48Z | 2986b4f41989 | end | D09a | STD | v10a-check | - | 2/2 | completed | `c0b68db` (dirty) |
| 2026-11-12T10:11:48Z | a92904569a4d | start | D09b | STD | v10a-check | - | 0/2 | started | `c0b68db` (dirty) |
| 2026-11-12T10:12:05Z | a92904569a4d | end | D09b | STD | v10a-check | - | 2/2 | completed | `c0b68db` (dirty) |
| 2026-11-12T10:13:46Z | c288852bc70f | end | D06 | STD | pilot | - | 12/12 | completed | `d48ac6e` (dirty) |
| 2026-11-12T10:13:46Z | 48581af14f2f | start | D07a | STD | pilot | - | 0/12 | started | `c0b68db` (dirty) |
| 2026-11-12T10:21:06Z | 48581af14f2f | end | D07a | STD | pilot | - | 12/12 | completed | `c0b68db` (dirty) |
| 2026-11-12T10:21:06Z | 3d37a1b5a76b | start | D07b | STD | pilot | - | 0/12 | started | `419b3c1` |
| 2026-11-12T10:28:58Z | 3d37a1b5a76b | end | D07b | STD | pilot | - | 12/12 | completed | `419b3c1` |
| 2026-11-12T10:28:58Z | 8d91fdd33241 | start | D08 | STD | pilot | - | 0/12 | started | `9a1f527` (dirty) |
| 2026-11-12T10:34:39Z | bc0cc650c09e | start | D10 | HB | pilot | - | 0/1 | started | `7656ad9` |
| 2026-11-12T10:36:59Z | 8d91fdd33241 | end | D08 | STD | pilot | - | 12/12 | completed | `9a1f527` (dirty) |
| 2026-11-12T10:36:59Z | 850d1e57d52e | start | D09a | STD | pilot | - | 0/12 | started | `7656ad9` (dirty) |
| 2026-11-12T10:41:57Z | 850d1e57d52e | end | D09a | STD | pilot | - | 12/12 | completed | `7656ad9` (dirty) |
| 2026-11-12T10:41:57Z | 99da1e5c58f0 | start | D09b | STD | pilot | - | 0/12 | started | `7656ad9` (dirty) |
| 2026-11-12T11:06:30Z | 99da1e5c58f0 | end | D09b | STD | pilot | - | 12/12 | completed | `7656ad9` (dirty) |
| 2026-11-12T11:06:30Z | af014e7f4bf3 | start | D11 | STD | pilot | - | 0/12 | started | `7656ad9` (dirty) |
| 2026-11-12T11:15:06Z | af014e7f4bf3 | end | D11 | STD | pilot | - | 12/12 | completed | `7656ad9` (dirty) |
| 2026-11-12T11:15:06Z | 945a41c80668 | start | P1 | STD | pilot | - | 0/12 | started | `7656ad9` (dirty) |
| 2026-11-12T11:22:13Z | 945a41c80668 | end | P1 | STD | pilot | - | 12/12 | completed | `7656ad9` (dirty) |
| 2026-11-12T11:22:13Z | 2577918e9366 | start | P2 | STD | pilot | - | 0/12 | started | `ce4c5d6` |
| 2026-11-12T11:29:22Z | 2577918e9366 | end | P2 | STD | pilot | - | 12/12 | completed | `ce4c5d6` |
| 2026-11-12T11:29:22Z | 290c40ff8b4d | start | P3 | STD | pilot | - | 0/12 | started | `ce4c5d6` (dirty) |
| 2026-11-12T11:34:35Z | 290c40ff8b4d | end | P3 | STD | pilot | - | 12/12 | completed | `ce4c5d6` (dirty) |
| 2026-11-12T11:34:35Z | e42f54b994ac | start | P4 | STD | pilot | - | 0/12 | started | `ce4c5d6` (dirty) |
| 2026-11-12T11:39:21Z | e42f54b994ac | end | P4 | STD | pilot | - | 12/12 | completed | `ce4c5d6` (dirty) |
| 2026-11-12T11:39:21Z | a29f7f5b22a9 | start | D01 | LONG | pilot | - | 0/6 | started | `ce4c5d6` (dirty) |
| 2026-11-12T11:42:10Z | a29f7f5b22a9 | end | D01 | LONG | pilot | - | 6/6 | completed | `ce4c5d6` (dirty) |
| 2026-11-12T11:42:10Z | a31f35cd23e7 | start | D02 | LONG | pilot | - | 0/6 | started | `ce4c5d6` (dirty) |
| 2026-11-12T11:44:58Z | a31f35cd23e7 | end | D02 | LONG | pilot | - | 6/6 | completed | `ce4c5d6` (dirty) |
| 2026-11-12T12:20:57Z | bc0cc650c09e | note | D10 | HB | pilot | - | 0/1 | stopped | `7656ad9` |

Held-out runs refused: 0. Held-out runs made: 0.
