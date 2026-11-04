# Trial T02: economic momentum as a fourth currency signal — results

| item | value |
|---|---|
| pre-registration | `docs/prereg/T02_econ_momentum.md`, committed in `0b40b2a` before any T02 run |
| ledger | `trials.csv` id **T13** (named T02; `T02` is the gold event trades' ledger id), group `G12_econ_momentum` |
| code at run | `6b43beb` (branch `trial/T02-econ-momentum`); `em_macro/econmom.py`, `em_macro/t02.py`; re-uses `em_macro/t01.py` (statistics), `em_macro/tstrend.py` (cost and subset helpers), `em_macro/holdout.py` |
| run | 2026-11-04T08:58:09+00:00 to 2026-11-04T09:02:09+00:00 UTC; pandas 3.0.5, numpy 2.5.3; data through 2026-09 |
| v1.0 reproduction | frozen `systematic.evaluate` on this run's inputs vs the committed tables: test 2020-01..2026-09 max abs diff 0.0000 (14 rows), design 2005-2019 max abs diff 0.0000 (14 rows), at the files' 4 decimals; checked before T02 was run |
| v1.0 baseline | tag `v1.0-frozen` = `7886867`; `em_macro/systematic.py` SHA-256 `1eb4cf6b1c537c17…` (unchanged) |
| macro data | raw vintages re-downloaded 2026-11-04 and verified against `results/T02/raw_data_manifest.csv`: every first-release vintage file identical; the five OECD KEI revised-fallback files changed hash (same size and shape) and were used as re-downloaded, decided before any computation (`results/T02/raw_data_verification.md`); the raw set as used is kept in `data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz` |
| decision basis | 1x costs (v1.0's cost model), 2020-01..2026-09; 2x costs, 2005-2019, half A and the robustness checks reported, not decisive |

v1.0's figures remain "OOS for v1.0 only". T02's figures are reported separately and are not merged with v1.0's track record.

## 1. Pre-registered pass/fail table

**1x costs (decisive).**

| # | criterion | T02 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10 | SR 0.774 | SR 0.654 | dSR +0.121, p = 0.2759 | FAIL |
| 2 | holdout half B, 2020-01..2026-09: dSR > 0 and \|MaxDD\| not worse | SR 0.716, MaxDD -23.53% | SR 0.721, MaxDD -22.53% | dSR -0.005; \|DD\| ratio 1.045 | FAIL |
| 3 | 2020-01..2026-09: \|MaxDD\| and ES97.5 each <= 1.10 x v1.0 | MaxDD -16.96%, ES 5.87% | MaxDD -18.48%, ES 5.57% | DD ratio 0.918; ES ratio 1.054 | PASS |
| 4 | DSR (noise-only null) of T02 at N = 9 >= DSR of v1.0 at N = 7 (0.619, T01 report) | DSR 0.681 (N 9) | DSR 0.619 (N 7; recomputed 0.619) | difference +0.062 | PASS |
| 5 | econ-momentum sleeve alpha vs v1.0 carry/trend/value sleeves, 2020-01..2026-09: alpha > 0 and NW(3) t > 1.5 | alpha -6.30%/yr, t -1.66 (n 81) | n/a | betas carry +0.73, trend +0.02, value -0.49; R2 0.53 | FAIL |

**Overall (all five required): FAIL** — criteria passed: 2 of 5 (3, 4); failed: 1, 2, 5.

Bootstrap (criterion 1): paired circular block bootstrap, block 6 months, B = 10,000, seed 20261103; bootstrap dSR mean +0.136, SD 0.185, 5%–95% range -0.166 to +0.444.

Criterion 4 compares with v1.0's DSR at N = 7 as recorded in T01's report (0.619), as pre-registered; the value recomputed on this run's v1.0 returns is shown in brackets.

**2x costs (sensitivity, not decisive).**

| # | criterion | T02 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10 | SR 0.377 | SR 0.262 | dSR +0.115, p = 0.2942 | FAIL |
| 2 | holdout half B, 2020-01..2026-09: dSR > 0 and \|MaxDD\| not worse | SR 0.476, MaxDD -28.03% | SR 0.456, MaxDD -26.29% | dSR +0.020; \|DD\| ratio 1.066 | FAIL |
| 3 | 2020-01..2026-09: \|MaxDD\| and ES97.5 each <= 1.10 x v1.0 | MaxDD -19.05%, ES 6.06% | MaxDD -22.14%, ES 5.78% | DD ratio 0.860; ES ratio 1.049 | PASS |
| 4 | DSR (noise-only null) of T02 at N = 9 >= DSR of v1.0 at N = 7 (v1.0 at the same costs) | DSR 0.293 (N 9) | DSR 0.237 (N 7; recomputed 0.237) | difference +0.055 | PASS |
| 5 | econ-momentum sleeve alpha vs v1.0 carry/trend/value sleeves, 2020-01..2026-09: alpha > 0 and NW(3) t > 1.5 | alpha -8.47%/yr, t -1.83 (n 81) | n/a | betas carry +0.73, trend +0.03, value -0.47; R2 0.52 | FAIL |

Overall at 2x costs: FAIL. (At 2x costs criterion 4 compares T02's 2x DSR with v1.0's 2x DSR at N = 7, as in T01's 2x table.)

## 2. v1.0 and T02 side by side

Sharpe = mean/SD × √12 of monthly net returns; return = compounded; MaxDD on the compounded monthly index; ES97.5 = historical expected shortfall of monthly net returns (Acerbi-Tasche), as a loss; turnover = one-way notional traded per year, in multiples of capital; costs = cost drag per year.

**Test, 2020-01..2026-09, all 23 instruments (decisive).**

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.65 | 5.96 | 9.56 | -18.48 | 5.57 | 19.09 | 3.73 | 5.49 |
| 1x | T02 | 2020-01 | 81 | 0.77 | 6.94 | 9.22 | -16.96 | 5.87 | 18.68 | 3.64 | 5.51 |
| 2x | v1.0 | 2020-01 | 81 | 0.26 | 2.08 | 9.59 | -22.14 | 5.78 | 19.09 | 7.47 | 5.49 |
| 2x | T02 | 2020-01 | 81 | 0.38 | 3.12 | 9.30 | -19.05 | 6.06 | 18.68 | 7.27 | 5.51 |

**Holdout, half B (BR, CO, ZA, TR, GB, FR, IT; 12 instruments, 5 currencies), 2020-01..2026-09.** Each strategy run as a stand-alone universe of half B; ECONMOM ranks over the half-B currencies.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.72 | 7.54 | 10.95 | -22.53 | 8.05 | 14.41 | 2.81 | 3.88 |
| 1x | T02 | 2020-01 | 81 | 0.72 | 7.34 | 10.72 | -23.53 | 7.17 | 12.31 | 2.51 | 3.84 |
| 2x | v1.0 | 2020-01 | 81 | 0.46 | 4.56 | 11.14 | -26.29 | 8.12 | 14.41 | 5.61 | 3.88 |
| 2x | T02 | 2020-01 | 81 | 0.48 | 4.68 | 10.86 | -28.03 | 7.28 | 12.31 | 5.01 | 3.84 |

**In-sample context, 2005-2019 (cannot affect the decision).** v1.0 was designed on this period.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2006-02 | 167 | 0.40 | 3.56 | 10.10 | -13.82 | 6.15 | 27.87 | 5.35 | 5.66 |
| 1x | T02 | 2006-02 | 167 | 0.45 | 4.10 | 9.96 | -16.65 | 6.33 | 26.55 | 5.17 | 5.57 |
| 2x | v1.0 | 2006-02 | 167 | -0.13 | -1.85 | 10.31 | -28.33 | 6.53 | 27.87 | 10.69 | 5.66 |
| 2x | T02 | 2006-02 | 167 | -0.06 | -1.17 | 10.21 | -27.91 | 6.75 | 26.55 | 10.34 | 5.57 |

**Context: half B 2005-2019, and half A (MX, CL, PL, ID, ES, DE, euro area) in both periods, 1x.**

| universe | period | strategy | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr |
|---|---|---|---|---|---|---|---|---|---|
| half B | 2005-2019 (in-sample, context) | v1.0 | 167 | 0.52 | 5.47 | 11.52 | -28.82 | 6.50 | 21.12 |
| half B | 2005-2019 (in-sample, context) | T02 | 167 | 0.47 | 4.84 | 11.59 | -29.42 | 6.90 | 21.01 |
| half A | 2020-01..2026-09 (test) | v1.0 | 81 | 0.69 | 6.77 | 10.30 | -16.82 | 6.18 | 16.48 |
| half A | 2005-2019 (in-sample, context) | v1.0 | 167 | 0.06 | 0.01 | 12.63 | -31.12 | 10.27 | 21.87 |
| half A | 2020-01..2026-09 (test) | T02 | 81 | 0.71 | 6.88 | 10.16 | -14.83 | 6.80 | 15.64 |
| half A | 2005-2019 (in-sample, context) | T02 | 167 | 0.10 | 0.46 | 12.99 | -30.87 | 9.83 | 19.51 |

**By year, 2020–2026 (2026 = January–September), all instruments.** Return compounded within the year; MaxDD within the year from the start-of-year level; turnover = notional traded in the year.

*1x costs*

| year | v1.0 return % | T02 return % | T02 − v1.0 (pp) | v1.0 vol % | T02 vol % | v1.0 Sharpe | T02 Sharpe | v1.0 MaxDD % | T02 MaxDD % | v1.0 turnover x | T02 turnover x |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2020 | -13.90 | -14.57 | -0.67 | 9.40 | 10.22 | -1.54 | -1.48 | -18.33 | -18.09 | 12.64 | 13.02 |
| 2021 | -4.39 | -1.16 | 3.23 | 6.71 | 6.46 | -0.64 | -0.15 | -7.79 | -6.55 | 12.92 | 11.60 |
| 2022 | 20.67 | 18.93 | -1.74 | 12.12 | 11.34 | 1.62 | 1.59 | -4.77 | -6.44 | 14.05 | 10.88 |
| 2023 | 22.44 | 17.64 | -4.81 | 12.25 | 9.57 | 1.72 | 1.75 | -6.75 | -5.85 | 18.48 | 19.45 |
| 2024 | 13.81 | 12.48 | -1.33 | 6.26 | 4.06 | 2.11 | 2.93 | -2.04 | -1.34 | 25.70 | 29.31 |
| 2025 | -0.99 | 0.76 | 1.75 | 6.61 | 8.32 | -0.12 | 0.13 | -6.69 | -8.98 | 31.96 | 31.18 |
| 2026 | 7.85 | 17.45 | 9.60 | 8.81 | 10.20 | 1.19 | 2.17 | -4.35 | -1.33 | 13.08 | 10.66 |

*2x costs*

| year | v1.0 return % | T02 return % | T02 − v1.0 (pp) | v1.0 vol % | T02 vol % | v1.0 Sharpe | T02 Sharpe | v1.0 MaxDD % | T02 MaxDD % | v1.0 turnover x | T02 turnover x |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2020 | -16.12 | -16.85 | -0.72 | 9.54 | 10.22 | -1.78 | -1.74 | -20.05 | -19.84 | 12.64 | 13.02 |
| 2021 | -6.66 | -3.19 | 3.47 | 6.87 | 6.51 | -0.97 | -0.47 | -8.87 | -7.25 | 12.92 | 11.60 |
| 2022 | 17.28 | 16.47 | -0.81 | 12.23 | 11.41 | 1.37 | 1.40 | -5.41 | -6.74 | 14.05 | 10.88 |
| 2023 | 18.05 | 13.23 | -4.81 | 11.94 | 9.36 | 1.45 | 1.38 | -6.76 | -6.12 | 18.48 | 19.45 |
| 2024 | 8.33 | 6.40 | -1.93 | 6.64 | 4.62 | 1.24 | 1.37 | -3.89 | -2.42 | 25.70 | 29.31 |
| 2025 | -6.91 | -5.43 | 1.48 | 6.71 | 8.68 | -1.03 | -0.60 | -8.22 | -10.91 | 31.96 | 31.18 |
| 2026 | 5.16 | 15.20 | 10.05 | 8.80 | 10.19 | 0.80 | 1.91 | -5.18 | -1.53 | 13.08 | 10.66 |

T02 estimates no parameters, so the spec's year-by-year walk-forward equals this single causal run; the years above are its walk-forward years.

## 3. The economic-momentum sleeve on its own

The FX book run through v1.0's frozen machinery with ECONMOM as its only signal (thirds, inverse-vol sizing, 10% book and total volatility, 6x cap, 25% band, v1.0 costs). The carry, trend and value sleeves are frozen v1.0 run with that one signal in both books.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | econ momentum sleeve | 2020-01 | 81 | 0.18 | 1.41 | 11.78 | -30.78 | 12.62 | 12.87 | 2.05 | 2.96 |
| 1x | carry sleeve (v1.0 carry only) | 2020-01 | 81 | 0.96 | 10.13 | 10.70 | -16.91 | 7.23 | 9.90 | 1.96 | 5.31 |
| 1x | trend sleeve (v1.0 trend only) | 2020-01 | 81 | 0.01 | -0.38 | 10.23 | -34.82 | 9.42 | 38.55 | 7.29 | 5.08 |
| 1x | value sleeve (v1.0 value only) | 2020-01 | 81 | -0.20 | -2.33 | 9.57 | -27.16 | 6.17 | 20.10 | 3.96 | 5.77 |
| 2x | econ momentum sleeve | 2020-01 | 81 | 0.01 | -0.65 | 11.81 | -34.24 | 12.83 | 12.87 | 4.10 | 2.96 |
| 2x | carry sleeve (v1.0 carry only) | 2020-01 | 81 | 0.77 | 8.01 | 10.76 | -19.03 | 7.24 | 9.90 | 3.91 | 5.31 |
| 2x | trend sleeve (v1.0 trend only) | 2020-01 | 81 | -0.67 | -7.44 | 10.60 | -44.25 | 10.10 | 38.55 | 14.57 | 5.08 |
| 2x | value sleeve (v1.0 value only) | 2020-01 | 81 | -0.61 | -6.13 | 9.54 | -42.31 | 6.75 | 20.10 | 7.91 | 5.77 |

In-sample context, 2005-2019:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | econ momentum sleeve | 2006-02 | 167 | 0.15 | 1.10 | 12.34 | -33.34 | 11.64 | 10.33 | 1.86 | 2.73 |
| 1x | carry sleeve (v1.0 carry only) | 2006-02 | 167 | 0.38 | 3.50 | 10.35 | -13.81 | 6.86 | 14.72 | 2.77 | 5.45 |
| 1x | trend sleeve (v1.0 trend only) | 2006-03 | 166 | -1.08 | -11.04 | 10.26 | -80.98 | 7.23 | 43.04 | 8.05 | 4.93 |
| 1x | value sleeve (v1.0 value only) | 2006-02 | 167 | 0.48 | 4.76 | 10.88 | -20.44 | 6.94 | 25.07 | 4.88 | 5.26 |

**Alpha regression (criterion 5).** Sleeve net monthly returns on the net returns of the carry-, trend- and value-only runs, OLS with intercept, Newey-West standard errors with 3 lags.

| costs | window | n | alpha %/yr | t(alpha) | beta carry | t | beta trend | t  | beta value | t   | R2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | 2020-01..2026-09 (test) — decisive | 81 | -6.305 | -1.661 | 0.731 | 6.813 | 0.018 | 0.123 | -0.488 | -3.664 | 0.526 |
| 1x | 2005-2019 (in-sample, context) | 166 | -1.130 | -0.405 | 0.723 | 6.921 | -0.016 | -0.116 | -0.069 | -0.730 | 0.351 |
| 2x | 2020-01..2026-09 (test) | 81 | -8.474 | -1.826 | 0.726 | 6.828 | 0.033 | 0.243 | -0.471 | -3.520 | 0.523 |
| 2x | 2005-2019 (in-sample, context) | 166 | -1.580 | -0.478 | 0.686 | 6.897 | -0.027 | -0.204 | -0.066 | -0.743 | 0.332 |

**Correlations of the sleeve's net monthly returns (1x) with the carry, trend and value sleeves and with v1.0.**

| period | months | carry | trend | value | v1.0 |
|---|---|---|---|---|---|
| 2020-01..2026-09 (test) | 81 | 0.606 | 0.319 | -0.302 | 0.316 |
| 2005-2019 (in-sample, context) | 166 | 0.590 | -0.009 | 0.147 | 0.479 |
| 2006-2026 (all months) | 247 | 0.593 | 0.095 | 0.016 | 0.429 |

**Signal-level correlations** of the ECONMOM z-score with v1.0's FX carry, trend and value z-scores (pooled over currency-months, and the mean of the monthly cross-sectional correlations).

| period | with | pooled corr | mean monthly XS corr | n |
|---|---|---|---|---|
| 2020-01..2026-09 (test) | carry | 0.647 | 0.647 | 810 |
| 2020-01..2026-09 (test) | trend | 0.083 | 0.087 | 810 |
| 2020-01..2026-09 (test) | value | -0.003 | -0.003 | 800 |
| 2005-2019 (in-sample, context) | carry | 0.684 | 0.685 | 1794 |
| 2005-2019 (in-sample, context) | trend | 0.127 | 0.134 | 1664 |
| 2005-2019 (in-sample, context) | value | -0.039 | -0.039 | 1440 |

## 4. Deflated-Sharpe update

PSR and DSR (spec §0.2; `em_macro/mtstats.py`) from each strategy's realised 2020-01..2026-09 monthly Sharpe, skewness and raw kurtosis, T = 81. Noise-only null: trial-Sharpe SD = 1/√80 per month (decisive). Dispersed: SD 0.20 annualised. Adding T02 increments N by one: spec convention 8 → 9 (T02 at 9 compared with v1.0 at 7, the stricter comparison; v1.0 at 8 shown), ledger convention 11 → 12.

*1x costs*

| strategy | convention | N | SR_ann | skew | kurtosis | PSR(SR*=0) | SR0 noise (ann.) | DSR noise | SR0 dispersed (ann.) | DSR dispersed |
|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 | spec | 7 | 0.654 | 0.185 | 2.903 | 0.956 | 0.537 | 0.619 | 0.277 | 0.837 |
| v1.0 | spec | 8 | 0.654 | 0.185 | 2.903 | 0.956 | 0.565 | 0.591 | 0.292 | 0.827 |
| T02 | spec | 9 | 0.774 | -0.035 | 3.671 | 0.975 | 0.589 | 0.681 | 0.304 | 0.883 |
| v1.0 | ledger | 11 | 0.654 | 0.185 | 2.903 | 0.956 | 0.628 | 0.526 | 0.324 | 0.804 |
| T02 | ledger | 12 | 0.774 | -0.035 | 3.671 | 0.975 | 0.645 | 0.629 | 0.333 | 0.868 |

*2x costs*

| strategy | convention | N | SR_ann | skew | kurtosis | PSR(SR*=0) | SR0 noise (ann.) | DSR noise | SR0 dispersed (ann.) | DSR dispersed |
|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 | spec | 7 | 0.262 | 0.238 | 2.890 | 0.753 | 0.537 | 0.237 | 0.277 | 0.484 |
| v1.0 | spec | 8 | 0.262 | 0.238 | 2.890 | 0.753 | 0.565 | 0.215 | 0.292 | 0.469 |
| T02 | spec | 9 | 0.377 | 0.014 | 3.625 | 0.834 | 0.589 | 0.293 | 0.304 | 0.574 |
| v1.0 | ledger | 11 | 0.262 | 0.238 | 2.890 | 0.753 | 0.628 | 0.171 | 0.324 | 0.436 |
| T02 | ledger | 12 | 0.377 | 0.014 | 3.625 | 0.834 | 0.645 | 0.245 | 0.333 | 0.545 |

## 5. Robustness (a): every macro input delayed three more months

Not a pass criterion. The ECONMOM score used at the end of month t is the one built from the vintages in force at the end of month t−3 (equivalently, every macro input, first-release or fallback, enters three months after its vintage date; the fallbacks are then lagged six months). Everything else is T02 unchanged. The same five statistics are computed for comparison.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.65 | 5.96 | 9.56 | -18.48 | 5.57 | 19.09 | 3.73 | 5.49 |
| 1x | T02 | 2020-01 | 81 | 0.77 | 6.94 | 9.22 | -16.96 | 5.87 | 18.68 | 3.64 | 5.51 |
| 1x | T02 (macro inputs delayed 3m, robustness) | 2020-01 | 81 | 0.73 | 6.54 | 9.30 | -17.44 | 5.96 | 19.04 | 3.77 | 5.51 |
| 2x | v1.0 | 2020-01 | 81 | 0.26 | 2.08 | 9.59 | -22.14 | 5.78 | 19.09 | 7.47 | 5.49 |
| 2x | T02 | 2020-01 | 81 | 0.38 | 3.12 | 9.30 | -19.05 | 6.06 | 18.68 | 7.27 | 5.51 |
| 2x | T02 (macro inputs delayed 3m, robustness) | 2020-01 | 81 | 0.32 | 2.60 | 9.38 | -19.28 | 6.14 | 19.04 | 7.55 | 5.51 |

Half B, 2020-01..2026-09:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.72 | 7.54 | 10.95 | -22.53 | 8.05 | 14.41 | 2.81 | 3.88 |
| 1x | T02 | 2020-01 | 81 | 0.72 | 7.34 | 10.72 | -23.53 | 7.17 | 12.31 | 2.51 | 3.84 |
| 1x | T02 (macro inputs delayed 3m, robustness) | 2020-01 | 81 | 0.67 | 6.90 | 10.86 | -23.81 | 7.66 | 12.28 | 2.51 | 3.84 |

In-sample context, 2005-2019:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2006-02 | 167 | 0.40 | 3.56 | 10.10 | -13.82 | 6.15 | 27.87 | 5.35 | 5.66 |
| 1x | T02 | 2006-02 | 167 | 0.45 | 4.10 | 9.96 | -16.65 | 6.33 | 26.55 | 5.17 | 5.57 |
| 1x | T02 (macro inputs delayed 3m, robustness) | 2006-02 | 167 | 0.36 | 3.13 | 9.76 | -16.43 | 6.46 | 26.16 | 5.06 | 5.57 |

The sleeve with delayed inputs:

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | econ momentum sleeve | 2020-01 | 81 | 0.18 | 1.41 | 11.78 | -30.78 | 12.62 | 12.87 | 2.05 | 2.96 |
| 1x | econ momentum sleeve (delayed 3m) | 2020-01 | 81 | 0.19 | 1.52 | 11.08 | -22.97 | 10.02 | 14.25 | 2.41 | 2.92 |

The five statistics of the pass rule for the delayed version (1x; reported, not decisive):

| # | criterion | T02 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10 | SR 0.728 | SR 0.654 | dSR +0.075, p = 0.3761 | FAIL |
| 2 | holdout half B, 2020-01..2026-09: dSR > 0 and \|MaxDD\| not worse | SR 0.670, MaxDD -23.81% | SR 0.721, MaxDD -22.53% | dSR -0.051; \|DD\| ratio 1.057 | FAIL |
| 3 | 2020-01..2026-09: \|MaxDD\| and ES97.5 each <= 1.10 x v1.0 | MaxDD -17.44%, ES 5.96% | MaxDD -18.48%, ES 5.57% | DD ratio 0.944; ES ratio 1.069 | PASS |
| 4 | DSR (noise-only null) of T02 at N = 9 >= DSR of v1.0 at N = 7 (0.619, T01 report) | DSR 0.637 (N 9) | DSR 0.619 (N 7; recomputed 0.619) | difference +0.018 | PASS |
| 5 | econ-momentum sleeve alpha vs v1.0 carry/trend/value sleeves, 2020-01..2026-09: alpha > 0 and NW(3) t > 1.5 | alpha -4.38%/yr, t -1.06 (n 81) | n/a | betas carry +0.58, trend +0.06, value -0.30; R2 0.36 | FAIL |

Delayed version, all five statistics met: no (1x); no (2x).

By year, 2020–2026, 1x:

| year | v1.0 % | T02 % | T02 delayed 3m % |
|---|---|---|---|
| 2020 | -13.90 | -14.57 | -16.31 |
| 2021 | -4.39 | -1.16 | 0.89 |
| 2022 | 20.67 | 18.93 | 14.41 |
| 2023 | 22.44 | 17.64 | 15.54 |
| 2024 | 13.81 | 12.48 | 12.28 |
| 2025 | -0.99 | 0.76 | 6.07 |
| 2026 | 7.85 | 17.45 | 15.33 |

## 6. Robustness (b): signal observations using revised or stale data

A signal observation is one (currency, month) ECONMOM score. **Revised** = at least one component came from a revised fallback series (pre-registration §2.4, lagged three months) instead of a first-release vintage. **Stale** = the economic-activity or inflation index ended more than six months before the decision month, so its sub-signals used the last published values (point-in-time; the series had stopped updating). Component-level shares count (currency, component, month) inputs that exist.

| period | score obs | score obs revised | share revised % | score obs stale | share stale % | score obs revised or stale | share revised or stale % | component months available | share component months revised % | share component months stale % | share component months revised or stale % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2020-01..2026-09 (test) | 810 | 148 | 18.27 | 66 | 8.15 | 161 | 19.88 | 2997 | 5.04 | 8.64 | 11.91 |
| 2005-2019 (in-sample, context) | 1800 | 489 | 27.17 | 0 | 0.00 | 489 | 27.17 | 6595 | 15.78 | 1.38 | 17.16 |

By currency, 2020-01..2026-09 (months with a score):

| currency | score months | months revised | months stale | months revised or stale |
|---|---|---|---|---|
| BRL | 81 | 0 | 1 | 1 |
| MXN | 81 | 6 | 18 | 18 |
| ZAR | 81 | 14 | 14 | 14 |
| TRY | 81 | 30 | 3 | 30 |
| IDR | 81 | 64 | 0 | 64 |
| PLN | 81 | 3 | 3 | 3 |
| GBP | 81 | 0 | 0 | 0 |
| COP | 81 | 4 | 0 | 4 |
| CLP | 81 | 27 | 27 | 27 |
| EUR | 81 | 0 | 0 | 0 |

**Every gap and fallback case, 2020-01..2026-09** (runs of decision months; any input not from an up-to-date first-release vintage). "> 6 months old, index continues" = that component's last observation is more than six months old, and the index keeps being extended by its other components; "stale, index not updated" = no component of that index is updated, and its last value is used.

| currency | component | from | to | months | case | source | last obs range | max age months |
|---|---|---|---|---|---|---|---|---|
| BRL | IP | 2022-12 | 2022-12 | 1 | first-release, stale, index not updated (last value kept) | OECD editions | 2022-05..2022-05 | 7 |
| BRL | RS | 2022-11 | 2022-11 | 1 | first-release, > 6 months old, index continues on other components | OECD editions | 2022-04..2022-04 | 7 |
| BRL | RS | 2022-12 | 2022-12 | 1 | first-release, stale, index not updated (last value kept) | OECD editions | 2022-04..2022-04 | 8 |
| BRL | U | 2020-01 | 2026-09 | 81 | omitted (no source) | omitted |  |  |
| CLP | CPI | 2024-07 | 2026-09 | 27 | revised fallback (lag 3), stale, index not updated (last value kept) | revised lag3 (OECD KEI CHL CP _Z) | 2023-12..2023-12 | 33 |
| CLP | RS | 2020-01 | 2026-09 | 81 | first-release, > 6 months old, index continues on other components | OECD editions | 2018-12..2018-12 | 93 |
| COP | IP | 2020-05 | 2021-10 | 18 | first-release, > 6 months old, index continues on other components | OECD editions | 2018-12..2018-12 | 34 |
| COP | IP | 2022-07 | 2022-08 | 2 | first-release, > 6 months old, index continues on other components | OECD editions | 2021-12..2021-12 | 8 |
| COP | RS | 2020-01 | 2020-04 | 4 | first-release, > 6 months old, index continues on other components | ALFRED COLSLRTTO01IXOBSAM | 2018-12..2018-12 | 16 |
| COP | RS | 2020-05 | 2020-10 | 6 | first-release, > 6 months old, index continues on other components | OECD editions | 2018-12..2018-12 | 22 |
| COP | RS | 2021-03 | 2021-03 | 1 | first-release, > 6 months old, index continues on other components | OECD editions | 2020-08..2020-08 | 7 |
| COP | RS | 2022-07 | 2022-08 | 2 | first-release, > 6 months old, index continues on other components | OECD editions | 2021-12..2021-12 | 8 |
| COP | RS | 2025-12 | 2026-01 | 2 | first-release, > 6 months old, index continues on other components | OECD editions | 2025-05..2025-05 | 8 |
| COP | U | 2020-01 | 2020-04 | 4 | revised fallback (lag 3) | revised lag3 (OECD KEI COL UNEMP _T) | 2019-10..2020-01 | 3 |
| EUR | IP | 2026-03 | 2026-09 | 7 | first-release, > 6 months old, index continues on other components | ECB RTD | 2025-08..2025-08 | 13 |
| EUR | RS | 2026-03 | 2026-09 | 7 | first-release, > 6 months old, index continues on other components | ECB RTD | 2025-08..2025-08 | 13 |
| EUR | U | 2024-08 | 2025-06 | 11 | first-release, > 6 months old, index continues on other components | ECB RTD | 2024-01..2024-01 | 17 |
| IDR | IP | 2020-01 | 2023-02 | 38 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2019-10..2022-11 | 3 |
| IDR | IP | 2023-04 | 2023-08 | 5 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2023-01..2023-05 | 3 |
| IDR | IP | 2023-10 | 2024-12 | 15 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2023-07..2024-09 | 3 |
| IDR | IP | 2025-04 | 2025-04 | 1 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2025-01..2025-01 | 3 |
| IDR | IP | 2025-10 | 2025-12 | 3 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2025-07..2025-09 | 3 |
| IDR | IP | 2026-04 | 2026-04 | 1 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2026-01..2026-01 | 3 |
| IDR | IP | 2026-07 | 2026-07 | 1 | revised fallback (lag 3) | revised lag3 (OECD revisions latest editions IDN PRVM) | 2026-04..2026-04 | 3 |
| IDR | RS | 2020-01 | 2026-09 | 81 | omitted (no source) | omitted |  |  |
| IDR | U | 2020-01 | 2026-09 | 81 | omitted (no source) | omitted |  |  |
| MXN | CPI | 2025-02 | 2026-01 | 12 | first-release, stale, index not updated (last value kept) | OECD editions | 2024-07..2024-07 | 18 |
| MXN | CPI | 2026-04 | 2026-09 | 6 | revised fallback (lag 3), stale, index not updated (last value kept) | revised lag3 (OECD KEI MEX CP _Z) | 2024-07..2024-07 | 26 |
| MXN | RS | 2020-01 | 2020-07 | 7 | first-release, > 6 months old, index continues on other components | OECD editions | 2018-12..2018-12 | 19 |
| MXN | RS | 2023-10 | 2023-10 | 1 | first-release, > 6 months old, index continues on other components | OECD editions | 2023-03..2023-03 | 7 |
| PLN | CPI | 2026-07 | 2026-09 | 3 | revised fallback (lag 3), stale, index not updated (last value kept) | revised lag3 (OECD KEI POL CP _Z) | 2025-12..2025-12 | 9 |
| TRY | CPI | 2026-07 | 2026-09 | 3 | revised fallback (lag 3), stale, index not updated (last value kept) | revised lag3 (OECD KEI TUR CP _Z) | 2025-12..2025-12 | 9 |
| TRY | RS | 2020-01 | 2021-10 | 22 | first-release, > 6 months old, index continues on other components | ALFRED TURSLRTTO01IXOBSAM | 2018-07..2018-07 | 39 |
| TRY | RS | 2024-04 | 2026-09 | 30 | revised fallback (lag 3) | revised lag3 (OECD KEI TUR TOVM G47) | 2024-01..2026-06 | 3 |
| ZAR | CPI | 2025-08 | 2026-09 | 14 | revised fallback (lag 3), stale, index not updated (last value kept) | revised lag3 (OECD KEI ZAF CP _Z) | 2025-01..2025-01 | 20 |
| ZAR | IP | 2025-05 | 2025-05 | 1 | first-release, > 6 months old, index continues on other components | OECD editions | 2024-10..2024-10 | 7 |
| ZAR | RS | 2025-05 | 2025-05 | 1 | first-release, > 6 months old, index continues on other components | OECD editions | 2024-10..2024-10 | 7 |
| ZAR | U | 2020-01 | 2020-02 | 2 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2019-06..2019-06 | 8 |
| ZAR | U | 2020-10 | 2020-10 | 1 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2020-03..2020-03 | 7 |
| ZAR | U | 2022-04 | 2022-07 | 4 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2021-09..2021-09 | 10 |
| ZAR | U | 2022-10 | 2022-10 | 1 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2022-03..2022-03 | 7 |
| ZAR | U | 2023-01 | 2023-02 | 2 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2022-06..2022-06 | 8 |
| ZAR | U | 2023-04 | 2023-07 | 4 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2022-09..2022-09 | 10 |
| ZAR | U | 2023-10 | 2023-10 | 1 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2023-03..2023-03 | 7 |
| ZAR | U | 2024-01 | 2024-03 | 3 | first-release, > 6 months old, index continues on other components | ALFRED LRUNTTTTZAQ156S | 2023-06..2023-06 | 9 |

**First-release vs latest data (diagnostic, spec §13).** The same score rebuilt with each first-release input replaced by the latest vintage of the same source, truncated at the same last observation (revisions only; fallback inputs unchanged).

| period | n | pooled corr | mean monthly rank corr | same sign share % |
|---|---|---|---|---|
| 2020-01..2026-09 (test) | 810 | 0.986 | 0.958 | 95.556 |
| 2005-2019 (in-sample, context) | 1800 | 0.946 | 0.910 | 89.056 |

## 7. Implementation notes

- **Integration.** ECONMOM is injected into the FX book's signal dictionary; frozen `book_weights` and `run` are called with `["carry", "trend", "value", "econmom"]`. The bond book receives an all-missing ECONMOM frame, so its composite stays the mean of carry, trend and value; the run asserts that the bond-book weights equal v1.0's exactly in every universe and cost setting.
- **Source segments.** The pre-registration's §2.4 table is encoded in `econmom.SOURCE_PLAN`; its dates are read as decision months (for example Turkish retail sales: ALFRED vintages for decisions 2018-07..2024-03, the revised series lagged three months from 2024-04).
- **Revised series.** The OECD KEI series of the same measure and activity. The KEI has no total industry ex construction for Indonesia and no retail series for Chile; there the latest print of the OECD revisions database (edition 2026-10) is used as the revised series, under the same rule (truncated at t−3, flagged).
- **Stale series** keep their last published value (point-in-time): the index's last month T(c,t) is the last month published in the vintage. This applies, in the test window, to the CPI of Mexico, South Africa, Chile, Turkey and Poland once the OECD stopped updating them, and to euro-area industrial production and retail sales after the ECB RTD's last vintage of those series (2025-10-29); see §6.
- **Chile CPI after 2023-12** is omitted: the pre-registered extension ("FRED/BCCh CPI") was not among the downloaded files, so Chile's CPI ends with the KEI series in 2023-12, and its inflation index keeps that last value.
- **Indonesia IP "gaps"**: an OECD edition is used unless its last observation is more than six months old, in which case the revised series (lag 3, flagged) is used.
- **Quarterly South African unemployment** is carried to the three months of each quarter within each vintage.
- **Chain breaks.** A month in which no component of an index has a growth rate breaks the chain; the index is the unbroken run ending at its last month.
- **ECB RTD**: euro-area IP `RTD.M.S0.Y.I_XCONS.X`, retail `RTD.M.S0.Y.O_RTXMOTVD.X`, unemployment rate `RTD.M.S0.S.L_UNETO.F`, HICP `RTD.M.S0.N.P_C_OV.X`; VALID_FROM compared by calendar date.
- **Moments and DSR.** Skewness is the pandas bias-corrected skewness; kurtosis is raw (normal = 3).
- **Runs.** The pre-registered run was made once at `da7fc20` and its outputs committed. Its 2x sensitivity table compared T02's 2x DSR with v1.0's 1x value (0.619), which mixes cost settings. The runner was changed (`6b43beb`) so that the 2x table compares with v1.0's 2x DSR, as T01's 2x table did. The 1x decisive comparison is unchanged at the pre-registered 0.619. The same deterministic pipeline was then run again. Every output file is byte-identical to the first run except the 2x criterion-4 row (and the same row of the delayed robustness check) and the run times in `RUN.json`. The 2x row changed from FAIL (0.293 vs 0.619) to PASS (0.293 vs 0.237); the 2x overall result is FAIL either way.
- **Packages.** statsmodels 0.15.0, yfinance 1.8.0 and pytest were installed in this session (listed in `requirements.txt`, absent from the container); pandas and numpy are the versions T01 used.

## 8. Not tested here: macro momentum in bonds

The bond version of macro momentum, trends in growth and inflation applied across bond markets (Brooks 2017, "A Half Century of Macro Momentum", AQR Capital Management), is a candidate future trial. It was not tested in T02, which applies economic momentum to the 10 currencies only (pre-registration §2.1). If run, it needs its own pre-registration and ledger row.

## 9. Files

- `results/T02/performance.csv`: every strategy × universe (all, half A, half B) × costs × period.
- `results/T02/monthly_net.csv`: monthly net returns of every run; `results/T02/by_year_2020_2026.csv`.
- `results/T02/pass_fail_1x.csv`, `results/T02/pass_fail_2x.csv`, `results/T02/criteria.json` (bootstrap, DSR, alpha regressions, and the same statistics for the delayed version).
- `results/T02/econmom_score_{all,halfB,halfA}.csv`: the ECONMOM scores; `econmom_score_latest_data.csv`; `econmom_n_subsignals.csv`; `econmom_fallback_flags.csv`.
- `results/T02/econmom_component_sources.csv` (source, flag, last observation of every input, every month), `econmom_index_age.csv`, `fallback_share.csv`, `fallback_by_currency_2020_2026.csv`, `gap_and_fallback_cases_2020_2026.csv`, `first_release_vs_latest.csv`.
- `results/T02/sleeve_correlations.csv`, `results/T02/signal_correlations.csv`.
- `results/T02/RUN.json`: run time, code commit, SHA-256 of code, pre-registration and input files, and the v1.0 reproduction check.
- Code: `em_macro/econmom.py` (signal), `em_macro/t02.py` (runner), `em_macro/t02_report.py`, `em_macro/t02_verify.py`. Tests: `tests/test_econmom.py`.
