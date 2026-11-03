# Trial T01: time-series trend sleeve — results

| item | value |
|---|---|
| pre-registration | `docs/prereg/T01_ts_trend.md`, committed in `dc71998` before any T01 code or run |
| ledger | `trials.csv` id **T12** (named T01; `T01` is v1.0's ledger id), group `G11_ts_trend_sleeve` |
| code at run | `62524ff` (branch `trial/T01-ts-trend`); `em_macro/tstrend.py`, `em_macro/t01.py`, `em_macro/holdout.py` |
| run | 2026-11-03T10:36:42+00:00 to 2026-11-03T10:37:46+00:00 UTC; pandas 3.0.5, numpy 2.5.3; data through 2026-09 |
| v1.0 reproduction | frozen `systematic.evaluate` on this run's inputs vs the committed tables: test 2020-01..2026-09 max abs diff 0.0000 (14 rows), design 2005-2019 max abs diff 0.0000 (14 rows), at the files' 4 decimals |
| v1.0 baseline | tag `v1.0-frozen` = `7886867`; `em_macro/systematic.py` SHA-256 `1eb4cf6b1c537c17…` (unchanged) |
| decision basis | 1x costs (v1.0's cost model), 2020-01..2026-09; 2x costs and 2005-2019 reported, not decisive |

v1.0's figures remain "OOS for v1.0 only". T01's figures are reported separately and are not merged with v1.0's track record.

## 1. Pre-registered pass/fail table

**1x costs (decisive).**

| # | criterion | T01 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10 | SR 0.801 | SR 0.654 | dSR +0.148, p = 0.2632 | FAIL |
| 2 | holdout half B, 2020-01..2026-09: dSR > 0 and \|MaxDD\| not worse | SR 0.633, MaxDD -14.95% | SR 0.721, MaxDD -22.53% | dSR -0.088; \|DD\| ratio 0.664 | FAIL |
| 3 | 2020-01..2026-09: \|MaxDD\| and ES97.5 each <= 1.10 x v1.0 | MaxDD -14.00%, ES 5.40% | MaxDD -18.48%, ES 5.57% | DD ratio 0.758; ES ratio 0.970 | PASS |
| 4 | DSR (noise-only null) of T01 at N = 8 >= DSR of v1.0 at N = 7 | DSR 0.731 (N 8) | DSR 0.619 (N 7) | difference +0.112 | PASS |
| 5 | corr(trend sleeve, carry sleeve) < 0 in carry's worst 10% of months, 2020-01..2026-09 | corr +0.542 (n 8) | n/a | worst months: 2020-03 2020-07 2021-10 2022-03 2023-04 2023-11 2023-12 2024-08 | FAIL |

**Overall (all five required): FAIL** — criteria passed: 2 of 5 (3, 4); failed: 1, 2, 5.

Bootstrap (criterion 1): paired circular block bootstrap, block 6 months, B = 10,000, seed 20261103; bootstrap dSR mean +0.161, SD 0.221, 5%–95% range -0.192 to +0.536.

**2x costs (sensitivity, not decisive).**

| # | criterion | T01 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10 | SR 0.423 | SR 0.262 | dSR +0.161, p = 0.2530 | FAIL |
| 2 | holdout half B, 2020-01..2026-09: dSR > 0 and \|MaxDD\| not worse | SR 0.217, MaxDD -20.78% | SR 0.456, MaxDD -26.29% | dSR -0.239; \|DD\| ratio 0.790 | FAIL |
| 3 | 2020-01..2026-09: \|MaxDD\| and ES97.5 each <= 1.10 x v1.0 | MaxDD -17.89%, ES 5.75% | MaxDD -22.14%, ES 5.78% | DD ratio 0.808; ES ratio 0.996 | PASS |
| 4 | DSR (noise-only null) of T01 at N = 8 >= DSR of v1.0 at N = 7 | DSR 0.356 (N 8) | DSR 0.237 (N 7) | difference +0.119 | PASS |
| 5 | corr(trend sleeve, carry sleeve) < 0 in carry's worst 10% of months, 2020-01..2026-09 | corr +0.471 (n 8) | n/a | worst months: 2020-03 2020-07 2021-10 2023-04 2023-11 2023-12 2024-08 2025-03 | FAIL |

Overall at 2x costs: FAIL.

## 2. Annual returns, 2020–2026 (2026 = January–September), all instruments

| year | v1.0 1x % | T01 1x % | T01 − v1.0 1x (pp) | v1.0 2x % | T01 2x % | trend sleeve 1x % |
|---|---|---|---|---|---|---|
| 2020 | -13.90 | -9.64 | 4.26 | -16.12 | -13.88 | -16.36 |
| 2021 | -4.39 | -2.58 | 1.81 | -6.66 | -4.03 | -5.71 |
| 2022 | 20.67 | 23.93 | 3.26 | 17.28 | 18.97 | 8.52 |
| 2023 | 22.44 | 17.77 | -4.67 | 18.05 | 13.13 | -4.70 |
| 2024 | 13.81 | 15.11 | 1.31 | 8.33 | 10.20 | -0.51 |
| 2025 | -0.99 | 5.41 | 6.41 | -6.91 | 2.45 | 10.70 |
| 2026 | 7.85 | 3.33 | -4.52 | 5.16 | 1.01 | 10.09 |

T01 estimates no parameters, so the spec's year-by-year walk-forward equals this single causal run; the years above are its walk-forward years.

## 3. Side-by-side statistics

Sharpe = mean/SD × √12 of monthly net returns; return = compounded; MaxDD on the compounded monthly index; ES97.5 = historical expected shortfall of monthly net returns (Acerbi-Tasche), as a loss; turnover = one-way notional traded per year, in multiples of capital.

**Test, 2020-01..2026-09, all 23 instruments.**

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.65 | 5.96 | 9.56 | -18.48 | 5.57 | 19.09 | 3.73 | 5.49 |
| 1x | T01 | 2020-01 | 81 | 0.80 | 7.32 | 9.38 | -14.00 | 5.40 | 17.75 | 3.56 | 5.73 |
| 2x | v1.0 | 2020-01 | 81 | 0.26 | 2.08 | 9.59 | -22.14 | 5.78 | 19.09 | 7.47 | 5.49 |
| 2x | T01 | 2020-01 | 81 | 0.42 | 3.59 | 9.35 | -17.89 | 5.75 | 17.75 | 7.11 | 5.73 |

**Holdout, half B (BR, CO, ZA, TR, GB, FR, IT; 12 instruments), 2020-01..2026-09.** Each strategy run as a stand-alone universe of half B.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.72 | 7.54 | 10.95 | -22.53 | 8.05 | 14.41 | 2.81 | 3.88 |
| 1x | T01 | 2020-01 | 81 | 0.63 | 5.55 | 9.22 | -14.95 | 5.49 | 19.39 | 3.84 | 4.27 |
| 2x | v1.0 | 2020-01 | 81 | 0.46 | 4.56 | 11.14 | -26.29 | 8.12 | 14.41 | 5.61 | 3.88 |
| 2x | T01 | 2020-01 | 81 | 0.22 | 1.59 | 9.20 | -20.78 | 5.54 | 19.39 | 7.67 | 4.27 |

**In-sample context, 2005-2019 (cannot affect the decision).** v1.0 was designed on this period.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2006-02 | 167 | 0.40 | 3.56 | 10.10 | -13.82 | 6.15 | 27.87 | 5.35 | 5.66 |
| 1x | T01 | 2006-02 | 167 | 0.65 | 6.37 | 10.28 | -15.95 | 6.97 | 25.08 | 4.82 | 5.68 |
| 2x | v1.0 | 2006-02 | 167 | -0.13 | -1.85 | 10.31 | -28.33 | 6.53 | 27.87 | 10.69 | 5.66 |
| 2x | T01 | 2006-02 | 167 | 0.18 | 1.36 | 10.40 | -24.67 | 7.15 | 25.08 | 9.64 | 5.68 |

**Context: half B 2005-2019, and half A (MX, CL, PL, ID, ES, DE, euro area) in both periods.**

| universe | period | strategy | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) |
|---|---|---|---|---|---|---|---|---|
| half B | 2005-2019 (in-sample, context) | v1.0 | 167 | 0.52 | 5.47 | 11.52 | -28.82 | 6.50 |
| half B | 2005-2019 (in-sample, context) | T01 | 167 | 0.54 | 5.14 | 10.38 | -17.98 | 7.56 |
| half A | 2020-01..2026-09 (test) | v1.0 | 81 | 0.69 | 6.77 | 10.30 | -16.82 | 6.18 |
| half A | 2005-2019 (in-sample, context) | v1.0 | 167 | 0.06 | 0.01 | 12.63 | -31.12 | 10.27 |
| half A | 2020-01..2026-09 (test) | T01 | 81 | 0.63 | 6.11 | 10.33 | -12.01 | 6.11 |
| half A | 2005-2019 (in-sample, context) | T01 | 167 | 0.38 | 3.91 | 11.93 | -25.97 | 8.15 |

## 4. The trend sleeve on its own

The stand-alone TSMOM sleeve (spec §2.2 blend, k ∈ {1, 3, 6, 12}, all 23 instruments) at 10% target volatility, with v1.0's 6x cap, no-trade band and costs. The carry sleeve is frozen v1.0 run with carry only.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | trend sleeve (T01) | 2020-01 | 81 | 0.03 | -0.17 | 9.93 | -26.83 | 7.62 | 29.71 | 5.66 | 3.81 |
| 1x | carry sleeve (v1.0 carry only) | 2020-01 | 81 | 0.96 | 10.13 | 10.70 | -16.91 | 7.23 | 9.90 | 1.96 | 5.31 |
| 2x | trend sleeve (T01) | 2020-01 | 81 | -0.53 | -5.69 | 10.09 | -43.12 | 8.24 | 29.71 | 11.32 | 3.81 |
| 2x | carry sleeve (v1.0 carry only) | 2020-01 | 81 | 0.77 | 8.01 | 10.76 | -19.03 | 7.24 | 9.90 | 3.91 | 5.31 |

In-sample context, 2005-2019:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | trend sleeve (T01) | 2006-02 | 167 | -0.19 | -2.44 | 10.32 | -36.95 | 8.40 | 29.03 | 5.51 | 3.80 |
| 1x | carry sleeve (v1.0 carry only) | 2006-02 | 167 | 0.38 | 3.50 | 10.35 | -13.81 | 6.86 | 14.72 | 2.77 | 5.45 |

**Correlation with the carry sleeve (1x costs).** Carry's worst 10% of months = the round(10% × months) months with the lowest carry-sleeve net return in each window.

| window | months | corr, all months | n worst | corr in carry's worst 10% | carry mean in those months % | trend mean in those months % |
|---|---|---|---|---|---|---|
| 2020-01..2026-09 (test) — decisive (criterion 5) | 81 | 0.161 | 8 | 0.542 | -4.552 | -1.638 |
| 2005-2019 (in-sample, context) | 167 | -0.105 | 17 | -0.406 | -4.956 | 0.789 |
| 2006-2026 (all months) | 248 | -0.016 | 25 | -0.075 | -4.854 | -0.135 |

Carry's worst months, 2020-01..2026-09: 2020-03 2020-07 2021-10 2022-03 2023-04 2023-11 2023-12 2024-08.

## 5. Deflated-Sharpe update

PSR and DSR (spec §0.2; `em_macro/mtstats.py`) from each strategy's realised 2020-01..2026-09 monthly Sharpe, skewness and raw kurtosis, T = 81. Noise-only null: trial-Sharpe SD = 1/√80 per month (decisive, spec N). Dispersed: SD 0.20 annualised. Adding T01 increments N by one: spec convention 7 → 8, ledger convention 10 → 11.

| strategy | convention | N | SR_ann | skew | kurtosis | PSR(SR*=0) | SR0 noise (ann.) | DSR noise | SR0 dispersed (ann.) | DSR dispersed |
|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 | spec | 7 | 0.654 | 0.185 | 2.903 | 0.956 | 0.537 | 0.619 | 0.277 | 0.837 |
| T01 | spec | 8 | 0.801 | 0.228 | 3.363 | 0.982 | 0.565 | 0.731 | 0.292 | 0.908 |
| v1.0 | ledger | 10 | 0.654 | 0.185 | 2.903 | 0.956 | 0.610 | 0.545 | 0.315 | 0.811 |
| T01 | ledger | 11 | 0.801 | 0.228 | 3.363 | 0.982 | 0.628 | 0.674 | 0.324 | 0.893 |

## 6. Diagnostic only — core sleeve alone (carry + value, no trend). CANNOT BE ADOPTED

This is frozen v1.0 run with the trend signal removed (identical to the T01 core sleeve before the trend sleeve is added). It was not a pre-registered candidate. Choosing it after seeing these results would be in-sample selection on 2020-2026, and its 2020-2026 mean return was already known from the v1.0 Shapley diagnostics. Shown for attribution only.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.65 | 5.96 | 9.56 | -18.48 | 5.57 | 19.09 | 3.73 | 5.49 |
| 1x | core sleeve alone (diagnostic) | 2020-01 | 81 | 0.74 | 6.70 | 9.43 | -12.57 | 4.78 | 15.09 | 3.03 | 5.65 |
| 1x | T01 | 2020-01 | 81 | 0.80 | 7.32 | 9.38 | -14.00 | 5.40 | 17.75 | 3.56 | 5.73 |
| 2x | v1.0 | 2020-01 | 81 | 0.26 | 2.08 | 9.59 | -22.14 | 5.78 | 19.09 | 7.47 | 5.49 |
| 2x | core sleeve alone (diagnostic) | 2020-01 | 81 | 0.42 | 3.53 | 9.40 | -15.85 | 5.03 | 15.09 | 6.05 | 5.65 |
| 2x | T01 | 2020-01 | 81 | 0.42 | 3.59 | 9.35 | -17.89 | 5.75 | 17.75 | 7.11 | 5.73 |

Half B, 2020-01..2026-09:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.72 | 7.54 | 10.95 | -22.53 | 8.05 | 14.41 | 2.81 | 3.88 |
| 1x | core sleeve alone (diagnostic) | 2020-01 | 81 | 0.47 | 4.07 | 9.42 | -14.81 | 5.35 | 17.12 | 3.41 | 4.07 |
| 1x | T01 | 2020-01 | 81 | 0.63 | 5.55 | 9.22 | -14.95 | 5.49 | 19.39 | 3.84 | 4.27 |

In-sample context, 2005-2019:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2006-02 | 167 | 0.40 | 3.56 | 10.10 | -13.82 | 6.15 | 27.87 | 5.35 | 5.66 |
| 1x | core sleeve alone (diagnostic) | 2006-02 | 167 | 0.67 | 6.66 | 10.47 | -15.99 | 7.30 | 22.97 | 4.39 | 5.59 |
| 1x | T01 | 2006-02 | 167 | 0.65 | 6.37 | 10.28 | -15.95 | 6.97 | 25.08 | 4.82 | 5.68 |

## 7. Notes

- **Ledger id.** The trial is called T01 in the pre-registration, branch and this report. Its `trials.csv` id is T12, because T01 is v1.0's ledger id.
- **EWMA volatility.** As pre-registered (§2.3), σ is an EWMA on each instrument's monthly excess-return series, with the 60-trading-day centre of mass converted to 60/21 months. Daily prices exist for only 14 of the 23 instruments, and v1.0's bond returns come from monthly-average yields.
- **Runs.** The first invocation of the run crashed in the criteria step: pandas 3 propagated a DataFrame held in `attrs`. All strategy runs had finished by then, and three tables had been written (`performance.csv`, `monthly_net.csv`, `annual_2020_2026.csv`). Those files were deleted without being opened. No result was printed or read. The fix (`62524ff`) strips `attrs` from the net-return series and changes no calculation. The same code then ran once, end to end, and its output is reported here.
- **v1.0 inputs.** Cached raw downloads (FRED, Yahoo, BIS and others) were re-downloaded in this session. The frozen v1.0 still reproduces both of its committed result tables exactly (see the header).
- **Moments and DSR.** Skewness is the pandas bias-corrected skewness; kurtosis is raw (normal = 3).

## 8. Files

- `results/T01/performance.csv`: every strategy × universe (all, half A, half B) × costs × period.
- `results/T01/monthly_net.csv`: monthly net returns of every run.
- `results/T01/annual_2020_2026.csv`, `results/T01/pass_fail_1x.csv`, `results/T01/pass_fail_2x.csv`, `results/T01/criteria.json` (bootstrap, DSR, carry-worst-month details).
- `results/T01/holdout_split.csv`: the half A / half B assignment (seed 20261103).
- `results/T01/RUN.json`: run time, code commit, SHA-256 of code, pre-registration and input files, and the v1.0 reproduction check.
- Code: `em_macro/tstrend.py` (sleeves and combination), `em_macro/t01.py` (runner and statistics), `em_macro/holdout.py`, `em_macro/t01_report.py`. Tests: `tests/test_tstrend.py`.
