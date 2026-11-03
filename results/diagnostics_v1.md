# Diagnostics of the frozen v1.0 systematic strategy

Spec: `docs/research/algorithm_spec_2026-11.md` (Builds 1–3, §17.2).
Freeze record: `docs/v1.0_freeze.md` (tag `v1.0-frozen` → commit 7886867). No trading logic was changed; every number here comes from re-running the frozen code.
Tables: `results/diagnostics/*.csv`. Code: `em_macro/diagnostics.py`, `em_macro/mtstats.py`.

## Step 1 — Attribution (spec Build 1)

**How it was computed.**
- **Re-run:** the frozen v1.0 (tag `v1.0-frozen`) was re-run without changes. Each instrument's monthly P&L is `w × r − cost`: currency weights decided at month t earn month t+1; bond weights earn t+2 because of the execution lag. The per-instrument P&L adds up exactly to v1.0's monthly net return.
- **Units:** P&L is in % of capital a year, as the **arithmetic** mean of monthly net returns × 12. That is +4.0% a year for 2005–2019 and +6.25% for 2020-01 to 2026-09. The headline +6.0% is the geometric (compounded) rate.
- **Shares:** shares are of total net P&L, so they can exceed 100% when other parts lose money.

### Summary and flags

| period | total net, % a year (arithmetic) | top3_countries | top-3 share | BRL+MXN share | FLAG: BRL+MXN > 50% | Brazil+Mexico, all instruments, share |
|---|---|---|---|---|---|---|
| 2005-2019 | 4.01 | Brazil, Italy, United Kingdom | 143.6% | 42.6% | False | 67.5% |
| 2020-01 to 2026-09 | 6.25 | Germany, Turkey, South Africa | 107.8% | 18.4% | False | 14.7% |

### By country, 2005-2019 (% a year)

| country | fx_%pa | bonds_%pa | total_%pa | share_of_total |
|---|---|---|---|---|
| Brazil | 1.01 | 1.20 | 2.21 | 55.3% |
| Italy | 0.00 | 1.91 | 1.91 | 47.6% |
| United Kingdom | 0.75 | 0.88 | 1.63 | 40.6% |
| South Africa | 0.18 | 0.51 | 0.69 | 17.3% |
| Mexico | 0.70 | -0.21 | 0.49 | 12.2% |
| euro area | 0.45 | 0.00 | 0.45 | 11.1% |
| Indonesia | 0.01 | 0.42 | 0.43 | 10.8% |
| Poland | -0.27 | 0.67 | 0.39 | 9.8% |
| Colombia | -0.15 | 0.26 | 0.10 | 2.6% |
| Turkey | 0.22 | -0.13 | 0.09 | 2.2% |
| Spain | 0.00 | -0.15 | -0.15 | -3.8% |
| Germany | 0.00 | -0.39 | -0.39 | -9.8% |
| France | 0.00 | -1.02 | -1.02 | -25.5% |
| Chile | -1.48 | -1.35 | -2.83 | -70.7% |

### By country, 2020-01 to 2026-09 (% a year)

| country | fx_%pa | bonds_%pa | total_%pa | share_of_total |
|---|---|---|---|---|
| Germany | 0.00 | 2.35 | 2.35 | 37.7% |
| Turkey | -0.11 | 2.32 | 2.22 | 35.4% |
| South Africa | 0.58 | 1.58 | 2.17 | 34.7% |
| Brazil | 1.62 | 0.30 | 1.93 | 30.9% |
| Poland | -0.00 | 1.40 | 1.40 | 22.4% |
| euro area | 0.64 | 0.00 | 0.64 | 10.3% |
| Indonesia | -0.28 | 0.22 | -0.06 | -1.0% |
| Italy | 0.00 | -0.17 | -0.17 | -2.8% |
| Chile | 0.21 | -0.45 | -0.24 | -3.8% |
| United Kingdom | -0.62 | 0.21 | -0.41 | -6.5% |
| France | 0.00 | -0.48 | -0.48 | -7.7% |
| Colombia | 0.18 | -0.97 | -0.78 | -12.5% |
| Mexico | -0.47 | -0.54 | -1.01 | -16.2% |
| Spain | 0.00 | -1.30 | -1.30 | -20.8% |

### By asset class (% a year)

| period | asset_class | pnl_%pa | share_of_total |
|---|---|---|---|
| 2005-2019 | FX | 1.41 | 35.1% |
| 2005-2019 | bonds | 2.60 | 64.9% |
| 2020-01 to 2026-09 | FX | 1.76 | 28.1% |
| 2020-01 to 2026-09 | bonds | 4.49 | 71.9% |

### By signal (% a year)

Two methods are shown:
- **Proportional (spec):** each position's monthly P&L is split by `share_k = (z_k/K)/S` if |S| > 0.1, else 1/K. K is the number of signals available at the decision date and S is their mean (v1.0's composite).
- **Shapley:** exact Shapley values over the 2³ signal subsets. Each subset is run through the same frozen machinery (selection, sizing, 10% vol target, costs). The value of a subset is its annualised mean net return.

| period | signal | method | pnl_%pa | share_of_total |
|---|---|---|---|---|
| 2005-2019 | carry | proportional | 4.93 | 123.1% |
| 2005-2019 | trend | proportional | -7.39 | -184.5% |
| 2005-2019 | value | proportional | 6.46 | 161.4% |
| 2005-2019 | unattributed (position held by the no-trade band, no signal at decision) | proportional | 0.00 | 0.0% |
| 2020-01 to 2026-09 | carry | proportional | 4.52 | 72.4% |
| 2020-01 to 2026-09 | trend | proportional | 3.13 | 50.1% |
| 2020-01 to 2026-09 | value | proportional | -1.38 | -22.1% |
| 2020-01 to 2026-09 | unattributed (position held by the no-trade band, no signal at decision) | proportional | -0.02 | -0.3% |
| 2005-2019 | carry | Shapley | 4.30 | 107.3% |
| 2005-2019 | trend | Shapley | -6.50 | -162.3% |
| 2005-2019 | value | Shapley | 6.21 | 155.0% |
| 2020-01 to 2026-09 | carry | Shapley | 8.72 | 139.5% |
| 2020-01 to 2026-09 | trend | Shapley | -0.10 | -1.6% |
| 2020-01 to 2026-09 | value | Shapley | -2.37 | -37.9% |

Subset values used for the Shapley decomposition (% a year):

| period | subset | ann_mean_net_% |
|---|---|---|
| 2005-2019 | (none) | 0.00 |
| 2005-2019 | carry | 3.97 |
| 2005-2019 | trend | -11.12 |
| 2005-2019 | value | 5.24 |
| 2005-2019 | carry+trend | -2.04 |
| 2005-2019 | carry+value | 7.01 |
| 2005-2019 | trend+value | 0.51 |
| 2005-2019 | carry+trend+value | 4.01 |
| 2020-01 to 2026-09 | (none) | 0.00 |
| 2020-01 to 2026-09 | carry | 10.25 |
| 2020-01 to 2026-09 | trend | 0.14 |
| 2020-01 to 2026-09 | value | -1.90 |
| 2020-01 to 2026-09 | carry+trend | 9.42 |
| 2020-01 to 2026-09 | carry+value | 6.93 |
| 2020-01 to 2026-09 | trend+value | -0.60 |
| 2020-01 to 2026-09 | carry+trend+value | 6.25 |

### By factor exposure

OLS of monthly net returns (%) on:
- the dollar-index log change (Yahoo DX-Y.NYB);
- changes in the US 2-year and 10-year yields (FRED DGS2, DGS10; bp);
- the MSCI World return (Yahoo ^990100-USD-STRD, price index);
- the IMF all-commodity index log change (FRED PALLFNFINDEXM, monthly average). A Bloomberg commodity index is not freely available;
- an equal-weight EM FX basket spot return (BRL, MXN, ZAR, TRY, IDR, PLN, COP, CLP vs USD; + = EM up);
- the change in the VIX.

Standard errors are HAC with 3 lags. Contribution = coefficient × factor mean × 12. The dollar index and the EM basket are strongly negatively correlated, so their individual coefficients are not separately well identified.

**2005-2019** (R² 0.27, n = 166):

| term | coef | t | contribution_%pa |
|---|---|---|---|
| alpha (% a year) | 8.423 | 3.14 | 8.42 |
| DXY_% | 0.525 | 4.37 | 0.26 |
| dUS2y_bp | 0.013 | 1.03 | -0.30 |
| dUS10y_bp | -0.008 | -0.67 | 0.15 |
| MSCI_World_% | -0.205 | -1.82 | -1.11 |
| Commodities_% | -0.080 | -1.50 | -0.07 |
| EM_FX_basket_% | 0.768 | 7.10 | -3.40 |
| dVIX_pts | -0.028 | -0.29 | -0.00 |

**2020-01 to 2026-09** (R² 0.31, n = 81):

| term | coef | t | contribution_%pa |
|---|---|---|---|
| alpha (% a year) | 13.101 | 4.01 | 13.10 |
| DXY_% | 0.924 | 4.58 | 0.70 |
| dUS2y_bp | 0.021 | 0.93 | 1.01 |
| dUS10y_bp | -0.022 | -0.95 | -1.09 |
| MSCI_World_% | -0.152 | -1.64 | -1.86 |
| Commodities_% | -0.091 | -1.77 | -0.84 |
| EM_FX_basket_% | 0.855 | 5.87 | -4.79 |
| dVIX_pts | 0.026 | 0.46 | 0.01 |

## Step 2 — Risk audit (spec Build 2)

**Positions:** each month-end, the positions that earn the next month under v1.0's accounting: currencies decided that month, bonds decided the month before.

**Risk contributions:** RC_i = w_i(Σw)_i/σ_p, shown as shares of σ_p (they sum to 100%).

**Factor shares (spec §7):** `β_f(Ωβ)_f/σ_p²`, where:
- β = B'w;
- B holds each instrument's OLS betas on two factors over the same window: the USD factor (dollar-index log return) and the EM factor (equal-weight EM FX basket return);
- Ω is the factor covariance.

Cross terms are split between the two factors by this formula, so a single factor's share can be negative or above 100%.

**Shrinkage effect.** σ_p² uses the Ledoit-Wolf-shrunk covariance; the spec formula's factor covariance is not shrunk. In the unit test, a pure single-factor position therefore reads about 93% instead of 100%, so factor shares are slightly understated.

Two versions are reported:
- **A — spec version: Ledoit-Wolf on non-overlapping 3-day returns**, trailing 252 business days (84 observations). Daily prices exist only for the 10 currencies and the Brazilian, Mexican, South African and Turkish 10-year bonds, so version A covers those 14 instruments. Its coverage of v1.0's gross notional is reported.
- **B — full book: Ledoit-Wolf on trailing 60 monthly returns**, all 23 instruments (bond returns from monthly-average yields).

### Summary, 2005–2026

| version | measure | average | max | month of max | current book | months |
|---|---|---|---|---|---|---|
| A | USD factor share | 14.6% | 75.0% | 2026-01 | 29.5% | 248 |
| A | EM factor share | 14.2% | 70.3% | 2014-07 | 4.2% | 248 |
| A | USD + EM combined | 28.8% | 74.8% | 2013-12 | 33.7% | 248 |
| A | ex-ante vol, % | 8.5 | 18.0 | 2009-06 | 5.5 | 248 |
| A | largest single-position risk share | 25.5% | 47.2% | 2006-03 | 19.7% | 248 |
| A | coverage of v1.0 gross notional | 41.9% | 67.7% | 2024-01 | 42.9% | 248 |
| B | USD factor share | 11.3% | 43.1% | 2015-04 | 2.9% | 225 |
| B | EM factor share | 8.7% | 51.2% | 2023-04 | 3.8% | 225 |
| B | USD + EM combined | 20.0% | 55.2% | 2022-05 | 6.8% | 225 |
| B | ex-ante vol, % | 12.0 | 17.7 | 2009-01 | 13.7 | 225 |
| B | largest single-position risk share | 29.0% | 83.0% | 2008-02 | 31.1% | 225 |

### Flag

| version | average USD+EM share | FLAG: average above 60% |
|---|---|---|
| A | 28.8% | no |
| B | 20.0% | no |

### Current book (2026-09 month-end, held in 2026-10), version A

| instrument | weight | risk_share |
|---|---|---|
| PLN | -0.238 | 19.7% |
| GBP | -0.316 | 19.3% |
| BR10Y | -0.270 | 19.2% |
| EUR | -0.327 | 19.0% |
| TR10Y | -0.095 | 9.7% |
| TRY | 0.462 | 5.5% |
| MX10Y | 0.328 | 4.5% |
| IDR | 0.347 | 3.7% |
| BRL | 0.226 | -0.4% |

### Current book (2026-09 month-end, held in 2026-10), version B

| instrument | weight | risk_share |
|---|---|---|
| ES-DE | -1.618 | 31.1% |
| TRY | 0.462 | 24.6% |
| GB-DE | 0.752 | 13.6% |
| PL-DE | 0.500 | 11.3% |
| BR10Y | -0.270 | 3.8% |
| DE10Y | -0.413 | 3.4% |
| GBP | -0.316 | 3.2% |
| PLN | -0.238 | 3.2% |
| IDR | 0.347 | 2.7% |
| EUR | -0.327 | 2.6% |
| MX10Y | 0.328 | 2.2% |
| CO10Y | 0.184 | 0.9% |
| BRL | 0.226 | -0.8% |
| TR10Y | -0.095 | -1.8% |

### Average risk share by position (months when held)

| version | instrument | average | max | months held |
|---|---|---|---|---|
| A (3-day, daily-priced) | ZA10Y | 16.0% | 44.5% | 216 |
| A (3-day, daily-priced) | MX10Y | 14.5% | 32.4% | 116 |
| A (3-day, daily-priced) | EUR | 13.6% | 31.8% | 216 |
| A (3-day, daily-priced) | GBP | 13.6% | 28.3% | 167 |
| A (3-day, daily-priced) | MXN | 12.7% | 38.6% | 126 |
| A (3-day, daily-priced) | BR10Y | 12.6% | 47.2% | 180 |
| A (3-day, daily-priced) | PLN | 11.1% | 32.2% | 143 |
| A (3-day, daily-priced) | IDR | 11.1% | 45.0% | 90 |
| A (3-day, daily-priced) | CLP | 10.1% | 25.8% | 101 |
| A (3-day, daily-priced) | BRL | 10.1% | 36.7% | 202 |
| A (3-day, daily-priced) | ZAR | 9.8% | 31.3% | 139 |
| A (3-day, daily-priced) | COP | 9.7% | 25.2% | 116 |
| A (3-day, daily-priced) | TRY | 9.7% | 33.4% | 188 |
| A (3-day, daily-priced) | TR10Y | 9.0% | 23.3% | 70 |
| B (monthly, full book) | FR-DE | 26.6% | 74.6% | 145 |
| B (monthly, full book) | ES-DE | 16.5% | 83.0% | 122 |
| B (monthly, full book) | GB-DE | 13.3% | 28.0% | 114 |
| B (monthly, full book) | IT-DE | 10.6% | 57.3% | 124 |
| B (monthly, full book) | IDR | 8.9% | 31.8% | 80 |
| B (monthly, full book) | DE10Y | 7.6% | 19.2% | 130 |
| B (monthly, full book) | GBP | 7.2% | 23.3% | 158 |
| B (monthly, full book) | PL-DE | 7.2% | 17.9% | 140 |
| B (monthly, full book) | TRY | 6.5% | 24.6% | 165 |
| B (monthly, full book) | EUR | 6.4% | 16.4% | 197 |
| B (monthly, full book) | ZA10Y | 6.2% | 15.0% | 193 |
| B (monthly, full book) | CL10Y | 5.8% | 13.2% | 107 |
| B (monthly, full book) | BRL | 5.6% | 18.4% | 179 |
| B (monthly, full book) | MX10Y | 5.5% | 16.4% | 109 |
| B (monthly, full book) | MXN | 4.5% | 14.0% | 117 |
| B (monthly, full book) | ZAR | 4.4% | 17.1% | 123 |
| B (monthly, full book) | PLN | 4.3% | 12.1% | 137 |
| B (monthly, full book) | COP | 4.3% | 13.3% | 108 |
| B (monthly, full book) | BR10Y | 4.2% | 33.0% | 161 |
| B (monthly, full book) | CO10Y | 4.0% | 13.3% | 155 |
| B (monthly, full book) | CLP | 3.6% | 16.5% | 86 |
| B (monthly, full book) | ID10Y | 3.5% | 15.5% | 108 |
| B (monthly, full book) | TR10Y | 1.5% | 10.4% | 70 |

## Step 3 — Trial ledger and multiple-testing statistics (spec Build 3)

`trials.csv` has 11 rows in 10 distinct trial groups. 8 rows in 7 groups are the spec's N = 7. The sovereign fair-value v1 and its post-hoc v2 share one group, as in the spec. The rest come from this repository's history and are reported as a second N ("ledger N").
Full hypotheses, samples, results and sources are in `trials.csv`.

| trial_id | trial_group | date_tested | name | result | decision | counted_in_spec_N7 |
|---|---|---|---|---|---|---|
| T01 | G01_v1_systematic | 2026-10-29 | v1.0 systematic macro strategy (carry/trend/value; FX and bonds; 10% vol target) | 2020-01..2026-09: +6.0%/yr compounded, Sharpe 0.65, max drawdown -18.5%, S&P 500 correlation -0.17 (design sample Sharpe 0.40) | kept; frozen as v1.0 | True |
| T02 | G02_gold_event_trades | 2026-10-28 | Gold event trades (geopolitical/macro events; rules a-c) | In-sample Sharpe: a (buy if net 5d > +1%) 0.05 hand / -0.06 mechanical; b (sell if < -1%) -0.06 / -0.25; c (buy after any event) -0.09 / 0.25 vs buy-and-hold gold 0.51. No rule beats gold's own drift after costs; with the 5 best trades removed all rules are negative | rejected as a trading rule; frozen v1 kept as an explanatory model only | True |
| T03 | G03_fed_decision_model | 2026-10-29 | Fed decision model (v1; v1.1 political-pressure features; v1.2 SEP path and speech tone) | 5-class Brier, 1 day: v1 0.452 / v1.1 0.512 / v1.2 0.466 vs futures 0.162 (n 125); 2 weeks: v1 0.384 / v1.1 0.437 / v1.2 0.391 vs futures 0.181 (n 67). Every version is worse than futures at every horizon with a futures benchmark | rejected (futures dominate) | True |
| T04 | G04_tension_index | 2026-10-29 | Tension index / geopolitical-risk gold rule (rule d) | Index correlation with daily GPR 0.77. Rule d (buy gold if weekly GPR change > 1 SD): 59 trades, hit rate 56%, +0.16% per trade after cost (t 0.3), Sharpe 0.06 vs buy-and-hold 0.51 | rejected as a trading rule; index kept as a data series | True |
| T05 | G05_sovereign_fair_value | 2026-10-29 | Sovereign risk / spread fair-value model v1 (ridge + Driscoll-Kraay; spread forecast = -kappa x gap) | Pooled RMSE ratio 1.00 (3m) / 0.98 (6m); 0.98 edge disappears without the 5 largest moves; France 1.59 / 2.34 (much worse) | rejected (does not beat no change) | True |
| T06 | G05_sovereign_fair_value | 2026-10-29 | Sovereign fair-value model v2 (post-hoc; separate spread equations over Bunds / USTs) | Pooled RMSE ratio 1.00 (3m) / 0.98 (6m); France 1.08 / 1.18. Not an independent test | not adopted as a forecast; shown on the dashboard labelled post-hoc | True |
| T07 | G06_preelection_repricing | 2026-10-29 | Pre-election daily repricing (polls and Polymarket odds vs FX and 10y yields) | Same-day FX response significant in 0 of 21 elections (polls) and 0 of 6 (odds); pooled polls +0.017% per pp (t 0.9). Only significant same-day coefficient: South Africa 2024 10y (thin market) | null; not traded | True |
| T08 | G07_euro_spread_elections | 2026-11-02 | Euro-area election spread study (populist-vote surprise vs 10y spread over Bunds) | Primary FAIL: Pearson r = 0.060 (n 40) vs > 0.5 required; right sign 64.7% vs 70% required; ex-Greece r = 0.111 (n 34). Hand-coded robustness r = 0.031 | rejected (failed pre-registered criteria); Spain 2026 forecast only | True |
| T09 | G08_election_drift_rule | 2026-10-29 | Event-study election drift rule (fade the day-1 FX move; hold to day 5 or day 20) | Hold-out: day-5 hold -3.3%/yr, Sharpe -1.00 (14 trades, hit rate 29%); day-20 hold -4.8%/yr, Sharpe -0.53; carry basket +2.6%/yr, Sharpe 0.46 | rejected | False |
| T10 | G09_v1_no_trade_band_alternative | 2026-10-29 | v1 design alternative: no no-trade band (vs 25% band) | 2005-2019 combined Sharpe 0.37 without band vs 0.40 with band; costs 5.9% vs 5.3%/yr; band kept | band kept in v1.0; no-band config not adopted | False |
| T11 | G10_political_risk_overlay | 2026-10-30 | Political-risk overlay rules (a) cut to zero and (b) halve positions from 5 days before to 1 day after scheduled political events | 2005-2019: (a) Sharpe 0.25, (b) 0.33, (c) no change 0.40, so (c) frozen. 2020-26: cut 0.53, halve 0.60, no change 0.65 | rejected (frozen rule is no change) | False |

Functions: `em_macro/mtstats.py`; tests: `tests/test_mtstats.py`, which reproduce every §0.2 number.
- Inputs, as in the spec: SR 0.65, T = 81 months, monthly SR = 0.65/√12 = 0.1876. The actual test Sharpe is 0.654.
- **Noise-only null:** trial-Sharpe SD = 1/√(T−1) per month.
- **Dispersed trials:** SD 0.20 annualised.
- **Moments:** kurtosis is raw (normal = 3).

Moments of the actual v1.0 monthly net returns:

| sample | months | SR_ann_actual | skew | kurtosis_raw |
|---|---|---|---|---|
| 2020-01..2026-09 (test) | 81 | 0.65 | 0.19 | 2.90 |
| 2006-02..2019-12 (design) | 167 | 0.40 | 0.34 | 3.73 |

### Statistics table

| scenario | trials | skew | kurtosis | t | p_two_sided | PSR(SR*=0) | SR0_noise_ann | DSR_noise | SR0_dispersed_ann | DSR_dispersed | MinTRL_90%_years | MinTRL_95%_years | MinTRL_90%_vs_SR0_years | HL_Bonferroni_SR | HL_Sidak_SR | HL_BHY_SR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 normal (spec) | spec N=7 | 0.00 | 3.00 | 1.689 | 0.091 | 0.952 | 0.54 | 0.614 | 0.28 | 0.830 | 4.04 | 6.60 | 131.19 | 0.18 | 0.27 | 0.00 |
| S1 normal (spec) | ledger N=10 | 0.00 | 3.00 | 1.689 | 0.091 | 0.952 | 0.61 | 0.541 | 0.31 | 0.804 | 4.04 | 6.60 | 1036.30 | 0.04 | 0.19 | 0.00 |
| S2 carry-like (spec) | spec N=7 | -0.70 | 5.00 | 1.689 | 0.091 | 0.940 | 0.54 | 0.606 | 0.28 | 0.813 | 4.62 | 7.55 | 150.38 | 0.18 | 0.27 | 0.00 |
| S2 carry-like (spec) | ledger N=10 | -0.70 | 5.00 | 1.689 | 0.091 | 0.940 | 0.61 | 0.538 | 0.31 | 0.788 | 4.62 | 7.55 | 1187.97 | 0.04 | 0.19 | 0.00 |
| S3 severe (spec) | spec N=7 | -1.00 | 6.00 | 1.689 | 0.091 | 0.935 | 0.54 | 0.604 | 0.28 | 0.807 | 4.87 | 7.97 | 158.77 | 0.18 | 0.27 | 0.00 |
| S3 severe (spec) | ledger N=10 | -1.00 | 6.00 | 1.689 | 0.091 | 0.935 | 0.61 | 0.537 | 0.31 | 0.782 | 4.87 | 7.97 | 1254.25 | 0.04 | 0.19 | 0.00 |
| actual v1 2020-01..2026-09 (skew 0.19, kurt 2.90) | spec N=7 | 0.19 | 2.90 | 1.689 | 0.091 | 0.955 | 0.54 | 0.616 | 0.28 | 0.834 | 3.90 | 6.37 | 126.61 | 0.18 | 0.27 | 0.00 |
| actual v1 2020-01..2026-09 (skew 0.19, kurt 2.90) | ledger N=10 | 0.19 | 2.90 | 1.689 | 0.091 | 0.955 | 0.61 | 0.542 | 0.31 | 0.809 | 3.90 | 6.37 | 1000.08 | 0.04 | 0.19 | 0.00 |

Notes:
- **What varies:** the naive t-statistic and the Harvey-Liu haircuts do not depend on skew and kurtosis; they change only with N.
- **BHY = 0.00:** an adjusted p of at least 1 (a 100% haircut), with v1.0 treated as the top-ranked test.
- **One spec claim does not reproduce.** §0.2 says MinTRL against SR* = 0.537 is "more than 200 years". The formula gives 131 years (S1, 90%) to 262 years (S3, 95%); 90% values are in the table. It exceeds 200 years only at 95% confidence.

## Flags

| check | threshold | result | flag |
|---|---|---|---|
| BRL + MXN share of total P&L, 2005–2019 | > 50% | 42.6% | no |
| BRL + MXN share of total P&L, 2020-01 to 2026-09 | > 50% | 18.4% | no |
| USD + EM factor share of portfolio risk, average 2005–2026, version A (3-day, spec) | > 60% | 28.8% | no |
| USD + EM factor share of portfolio risk, average 2005–2026, version B (monthly, full book) | > 60% | 20.0% | no |

## Summary (factual; no trading recommendations)

- **Freeze.** The 2020-01 to 2026-09 result (+6.0% a year compounded, Sharpe 0.65, maximum drawdown −18.5%) is
  reproduced exactly from commit 7886867. None of the strategy files changed after that commit
  (`docs/v1.0_freeze.md`).
- **Countries.**
  - 2005–2019: the top three countries (Brazil, Italy, the United Kingdom) account for 144% of total net P&L.
  - 2020-01 to 2026-09: the top three (Germany, Turkey, South Africa) account for 108%.
  - BRL and MXN together are 43% and 18% of the total, below the 50% flag. Counting all Brazilian and Mexican
    instruments (currency and bond), the shares are 67% and 15%.
- **Asset class.** Bonds earn about two-thirds of net P&L in both periods: 65% in 2005–2019 and 72% in 2020–2026.
- **Signals.**
  - Both methods agree that carry is the largest positive contributor in 2020–2026 and value is negative.
  - Proportional method, 2020–2026: carry +4.5% a year, trend +3.1%, value −1.4%.
  - Shapley method, 2020–2026: carry +8.7%, trend −0.1%, value −2.4%. Carry alone earns 10.3% a year in the subset
    runs, more than the full composite (6.25%).
  - In 2005–2019 both methods give trend a large negative contribution (−7.4% proportional, −6.5% Shapley), and
    value and carry positive contributions.
- **Factors.**
  - The seven factors explain 27% (2005–2019) and 31% (2020–2026) of the variance of monthly returns.
  - The returns load positively and significantly on both the dollar index and the EM FX basket (t of 4–7), two
    factors that are strongly negatively correlated with each other.
  - The intercept is positive and significant in both periods (t 3.1 and 4.0).
- **Risk.**
  - The combined USD + EM factor share of ex-ante risk averages 28.8% (version A) and 20.0% (version B), with
    maxima of 74.8% (December 2013) and 55.2% (May 2022). Current values: 33.7% and 6.8%.
  - Version A covers on average 42% of the book's gross notional: the instruments with daily prices.
  - The largest single position averages 25% of portfolio risk in version A.
- **Multiple testing.**
  - The ledger (`trials.csv`) has 11 rows in 10 trial groups. Seven groups are the spec's N = 7. Three more come
    from this repository's history: the election drift rule, the no-trade-band alternative and the political-risk
    overlay.
  - Every §0.2 number reproduces, including the naive t, PSR, DSR, the Harvey-Liu haircuts and MinTRL. The one
    exception is the spec's ">200 years" MinTRL against SR0, which holds only at 95% confidence.
  - With the actual skew (0.185) and kurtosis (2.90) of v1.0's 2020–2026 monthly returns, which are close to normal:
    - PSR is 0.955.
    - DSR is 0.62 under the noise-only null and 0.83 with dispersed trials, at N = 7.
    - At N = 10, DSR is 0.54 under the noise-only null and 0.81 with dispersed trials.
    - MinTRL at 90% / 95% confidence against SR* = 0 is 3.9 / 6.4 years. The track record so far is 6.75 years.
    - The Bonferroni-haircut Sharpe is 0.18 at N = 7 and 0.04 at N = 10.

