# Manhattan engine: reproduction of carry and time-series momentum (exploration dates only)

Written by `python -m manhattan.factors.reproduce`. **Public data only** (the repository's daily panel: six emerging-market currencies). Window 2005-01-03 to 2019-12-31, role `exploration`: the read was allowed by `manhattan.roles.check_read`, and no row dated after the window was read from any file. Nothing here is evidence: these are two factors the repository already holds, run through the new engine to see that it gives the numbers the old code gives.

Data hash `00105344d6c7660eedbb9139c4bb0e5ddce7a57fe387ec668ff75212edc6b7b8`.

## 1. Carry: each currency's deposit against dollar cash, and the equal-weight basket

Monthly returns of the engine (daily accounting, monthly rebalancing, no cost) against the frozen benchmark `em_macro.carry` with its flat 0.10% monthly cost added back: (a) the frozen code run on the same rows, (b) the committed file `data/processed/carry_monthly_returns.csv` up to 2019-12.

| series | months | correlation with (a) | mean abs. difference | largest abs. difference (month) | mean a year: engine | (a) | Sharpe: engine | (a) | largest difference between (a) and (b) |
|---|---|---|---|---|---|---|---|---|---|
| BR | 179 | 0.999957 | 0.00031 | 0.00124 (2010-06) | 0.0818 | 0.0818 | 0.522 | 0.522 | 5.0e-07 |
| MX | 179 | 0.999978 | 0.00015 | 0.00097 (2008-10) | 0.0150 | 0.0151 | 0.137 | 0.138 | 5.0e-07 |
| ZA | 179 | 0.999933 | 0.00023 | 0.00622 (2019-12) | 0.0105 | 0.0108 | 0.066 | 0.068 | 5.0e-07 |
| TR | 179 | 0.999892 | 0.00032 | 0.00692 (2018-06) | 0.0075 | 0.0070 | 0.048 | 0.045 | 5.2e-07 |
| ID | 173 | 0.999958 | 0.00021 | 0.00247 (2019-12) | 0.0411 | 0.0413 | 0.325 | 0.327 | 2.7e-06 |
| PL | 179 | 0.999972 | 0.00013 | 0.00335 (2019-12) | 0.0139 | 0.0144 | 0.102 | 0.105 | 5.2e-07 |
| EW | 179 | 0.999952 | 0.00020 | 0.00211 (2019-12) | 0.0285 | 0.0286 | 0.267 | 0.267 | 5.1e-07 |

The committed file is the frozen code's output to its six decimals; where the last column is above 5e-7 the daily panel has been refreshed since the file was written (a few parts in a million).

The differences between the engine and the benchmark are conventions, not errors: the benchmark accrues one month of simple interest at the month-start rate over the month's calendar days; the engine accrues day by day at the rate in force, over the days actually between fixings, and compounds. The last fixing of the window (31 December 2019) is published on 1 January 2020, after the window ends, so the engine's last month stops one day earlier.

## 2. Time-series momentum: the trend sleeve of trial T01 on the six currencies

The engine computes the signal at each month end from its point-in-time view (code in `manhattan/factors/reproduce.py`); the frozen `em_macro.tstrend.trend_raw_weights` is run on the same monthly returns. For this comparison the data are stamped available on the day they describe, because the frozen signal uses the month's own last fixing.

| what | value |
|---|---|
| months with a decision compared | 179 (168 with a position) |
| largest absolute difference between a weight of the engine and of the frozen code | 3.33e-16 |
| monthly sleeve return, engine against frozen weights times next month's returns: months | 178 |
| correlation | 0.999807 |
| mean absolute difference | 0.000028 |
| largest absolute difference | 0.002726 (2010-06) |
| Sharpe ratio (gross, 2005 to 2019): engine / frozen | 0.190 / 0.183 |

The return differences come from the engine holding positions that drift within the month and compounding daily, where the reference multiplies month-start weights by monthly returns.

## 3. Verdict against the tolerances fixed in the code before the first run

| check | tolerance | result |
|---|---|---|
| carry: correlation with the frozen benchmark, every series, both references | at least 0.999 | **reproduced** |
| carry: mean absolute monthly difference | at most 0.001 | (same row) |
| trend: every weight | within 1e-09 of the frozen code | **reproduced** |
| trend: sleeve return correlation / mean absolute difference | at least 0.999 / at most 0.0005 | (same row) |

## 4. What is not reproduced here

The **published** results (time-series momentum: Moskowitz, Ooi and Pedersen 2012; carry across asset classes: Koijen, Moskowitz, Pedersen and Vrugt 2018) are for dozens of futures markets from the 1980s on. Six currencies from 2005 are not that universe, and no number above should be read against those papers. The repository's own futures sleeves (trials T20 to T22) are built from licensed data that is not in this repository. See docs/manhattan/ETHAN_ACTIONS.md item 20.

## 5. Records

Each engine run above is an `evaluation` record in `results/manhattan_engine/exploration_ledger.jsonl` (a hash chain; exploration role, evidential weight 0) and one row of `results/manhattan_engine/exploration_log.csv`, written by `nightshift.logs.log_variant`, which refuses a window after 2019-12-31. A second run of this module adds `rerun` records and no rows.

- carry BR: record 1 (evaluation), `e9992c89164fda29`
- carry MX: record 2 (evaluation), `3f23661bddefa65a`
- carry ZA: record 3 (evaluation), `e987818adeae18ae`
- carry TR: record 4 (evaluation), `42977069c278ff2a`
- carry ID: record 5 (evaluation), `ac5b6ae462d2a453`
- carry PL: record 6 (evaluation), `fdd24d02a5fa3dd8`
- carry EW: record 7 (evaluation), `01fd7bd48bd9dbf6`
- trend sleeve: record 8 (evaluation), `6bdb908bc0f696f6`
