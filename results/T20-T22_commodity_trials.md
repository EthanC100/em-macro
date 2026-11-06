# Trials T20–T22: commodity carry, basis-momentum and diversified futures trend against frozen v1.1 — results

**A4 and Amendment 4.** The Build 0 carry benchmark test A4 measured a correlation of 0.498 with AQR's commodity carry factor, against a threshold of 0.70. The A4 diagnostic found that AQR's own documented construction on these data correlates 0.679 (`results/T20-T22/build0_a4_diagnostic.md`). Under Amendment 4 (decided after those results), A4 is reported and does not gate the trials. In exchange, T20 and T21 must meet C1 at a Holm-adjusted p < 0.05 instead of 0.10.

| item | value |
|---|---|
| pre-registration | `docs/prereg/T20-T22_commodity_trials.md` with Amendments 1–4 |
| Build 0 | `results/T20-T22/build0.md` (committed before this run) |
| run | 2026-11-06T06:26:44+00:00 to 2026-11-06T06:33:27+00:00 UTC, commit `7405e5f`, pandas 3.0.5, numpy 2.5.3 |
| reproduction | v1.0 tables identical: True; v1.1 reproduces T18: True |
| markets dropped (Build 0) | 6L, 6Z, FBON, PA |
| T22 universe | 30 instruments: CL B RB HO NG G HG GC SI PL ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE 6E 6B 6M FGBL FOAT FBTP R |
| T20 Option A/B | A: CL RB HO NG HG ZC ZS ZW ZM ZL SB KC CC CT; B: B G KE LE GF HE |

Each trial's figures are reported separately and are never merged with v1.0's or v1.1's track record. v1.1's figures are "T18's single test, OOS for v1.1 only".

## 1. Pass/fail (decisive costs)

| trial | overall | C1 | C2 | C3 | C4 | S1 | S2 | S3 |
|---|---|---|---|---|---|---|---|---|
| T20 commodity carry | **FAIL** | FAIL | FAIL | FAIL | pass | FAIL | FAIL | pass |
| T21 basis-momentum | **FAIL** | FAIL | FAIL | pass | pass | pass | pass | pass |
| T22 diversified futures trend | **FAIL** | FAIL | FAIL | pass | pass | pass | pass | pass |

### T20 — commodity carry

| # | criterion | measured | result |
|---|---|---|---|
| C1 | non-inferiority dSR >= -0.05 and Holm p < 0.05 | dSR +0.0619; p raw 0.2761, Holm 0.3964 | **FAIL** |
| C2 | half B: dSR >= -0.05 and |MaxDD| <= v1.1's | dSR -0.0494; MaxDD -16.50% vs -15.42% | **FAIL** |
| C3 | |MaxDD| and ES97.5 <= 1.10 x v1.1's | MaxDD -18.21% vs -15.42%; ES 7.39% vs 5.93% | **FAIL** |
| C4 | DSR(N=16) >= DSR(v1.1, N=13), noise-only null | 0.7444 vs 0.7393 | pass |
| S1 | net SR > 0.20 in 2000-01..2019-12 and 2020-01..2026-09 | 0.1255 / 0.4639 | **FAIL** |
| S2 | Clark-West one-sided p < 0.05, 2010-01..2026-09 | t -0.359, p 0.6403 | **FAIL** |
| S3 | break-even cost multiple >= 2 | 4.24 | pass |

### T21 — basis-momentum

| # | criterion | measured | result |
|---|---|---|---|
| C1 | non-inferiority dSR >= -0.05 and Holm p < 0.05 | dSR +0.1729; p raw 0.0502, Holm 0.1506 | **FAIL** |
| C2 | half B: dSR >= -0.05 and |MaxDD| <= v1.1's | dSR +0.0247; MaxDD -16.30% vs -15.42% | **FAIL** |
| C3 | |MaxDD| and ES97.5 <= 1.10 x v1.1's | MaxDD -15.89% vs -15.42%; ES 5.60% vs 5.93% | pass |
| C4 | DSR(N=16) >= DSR(v1.1, N=13), noise-only null | 0.8402 vs 0.7393 | pass |
| S1 | NW (6) t of mean net return > 2, 2000-01..2026-09 | t 2.049 | pass |
| S2 | alpha vs T20 sleeve > 0 and NW t > 1.5 | alpha 3.42%/yr, t 1.893 | pass |
| S3 | break-even cost multiple >= 2 | 5.47 | pass |

### T22 — diversified futures trend

| # | criterion | measured | result |
|---|---|---|---|
| C1 | non-inferiority dSR >= -0.05 and Holm p < 0.10 | dSR +0.0409; p raw 0.1982, Holm 0.3964 | **FAIL** |
| C2 | half B: dSR >= -0.05 and |MaxDD| <= v1.1's | dSR +0.0153; MaxDD -16.37% vs -15.42% | **FAIL** |
| C3 | |MaxDD| and ES97.5 <= 1.10 x v1.1's | MaxDD -16.50% vs -15.42%; ES 5.24% vs 5.93% | pass |
| C4 | DSR(N=16) >= DSR(v1.1, N=13), noise-only null | 0.7450 vs 0.7393 | pass |
| S1 | net SR > 0.20 in 2000-01..2019-12 and 2020-01..2026-09 | 0.4020 / 0.2419 | pass |
| S2 | corr(T22 sleeve, v1.0 carry sleeve) < 0 in carry's worst 8 months, 2020-01..2026-09 | -0.2230 (2020-03 2020-07 2021-10 2022-03 2023-04 2023-11 2023-12 2024-08) | pass |
| S3 | break-even cost multiple >= 2 | 6.57 | pass |

## 2. Non-inferiority bootstrap and Holm correction (C1)

| trial | ΔSR | p (non-inferiority, raw) | Holm | threshold | superiority p (context) | bootstrap mean | SD | 5%–95% | 2x costs: Holm p |
|---|---|---|---|---|---|---|---|---|---|
| T20 | +0.0619 | 0.2761 | 0.3964 | < 0.05 | 0.3875 | +0.0839 | 0.1602 | -0.170 to +0.355 | 0.6789 |
| T21 | +0.1729 | 0.0502 | 0.1506 | < 0.05 | 0.1006 | +0.1754 | 0.1329 | -0.041 to +0.396 | 0.3054 |
| T22 | +0.0409 | 0.1982 | 0.3964 | < 0.10 | 0.3431 | +0.0409 | 0.1069 | -0.130 to +0.220 | 0.6789 |

## 3. v1.1 and the combined books, 2020-01..2026-09

| book | Sharpe | return %/yr | vol %/yr | MaxDD % | ES97.5 % | turnover x/yr |
|---|---|---|---|---|---|---|
| v1.1|decisive | 0.916 | 7.96 | 8.80 | -15.42 | 5.93 | 11.60 |
| v1.1+T20|full|decisive | 0.978 | 9.61 | 9.91 | -18.21 | 7.39 | 13.99 |
| v1.1+T21|full|decisive | 1.089 | 10.67 | 9.77 | -15.89 | 5.60 | 14.42 |
| v1.1+T22|full|decisive | 0.957 | 8.63 | 9.11 | -16.50 | 5.24 | 16.30 |

**Half B (holdout, C2)**, 2020-01..2026-09, against the full v1.1:

| book | Sharpe | return %/yr | vol %/yr | MaxDD % | ES97.5 % | turnover x/yr |
|---|---|---|---|---|---|---|
| v1.1|decisive | 0.916 | 7.96 | 8.80 | -15.42 | 5.93 | 11.60 |
| v1.1+T20|half B|decisive | 0.867 | 7.77 | 9.13 | -16.50 | 5.97 | 13.95 |
| v1.1+T21|half B|decisive | 0.941 | 8.85 | 9.52 | -16.30 | 5.59 | 14.46 |
| v1.1+T22|half B|decisive | 0.932 | 8.48 | 9.21 | -16.37 | 5.31 | 16.07 |

**2x costs** (reported, not decisive):

| book | Sharpe | return %/yr | vol %/yr | MaxDD % | ES97.5 % | turnover x/yr |
|---|---|---|---|---|---|---|
| v1.1|2x | 0.656 | 5.54 | 8.81 | -16.44 | 6.09 | 11.60 |
| v1.1+T20|full|2x | 0.685 | 6.48 | 9.90 | -19.61 | 7.61 | 13.99 |
| v1.1+T21|full|2x | 0.777 | 7.37 | 9.79 | -17.34 | 5.81 | 14.42 |
| v1.1+T22|full|2x | 0.647 | 5.62 | 9.10 | -17.77 | 5.43 | 16.30 |

**Context: 2000-01..2019-12** (v1.1 exists from its first live month):

| book | Sharpe | return %/yr | vol %/yr | MaxDD % | ES97.5 % | turnover x/yr |
|---|---|---|---|---|---|---|
| v1.1|decisive | 0.613 | 5.37 | 9.25 | -13.95 | 6.03 | 16.65 |
| v1.1+T20|full|decisive | 0.624 | 5.61 | 9.49 | -11.68 | 5.95 | 18.84 |
| v1.1+T21|full|decisive | 0.634 | 5.90 | 9.82 | -13.00 | 6.69 | 18.50 |
| v1.1+T22|full|decisive | 0.646 | 5.72 | 9.28 | -13.70 | 5.99 | 20.49 |

**By year, 2020–2026** (%; 2026 = January–September):

| series | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| v1.1 | -10.06 | -0.76 | 20.64 | 20.36 | 15.57 | 0.79 | 11.07 |
| v1.1+T20 | -11.57 | 0.93 | 23.17 | 14.89 | 23.66 | 3.96 | 14.39 |
| v1.1+T21 | -8.37 | 0.48 | 28.62 | 18.37 | 17.31 | 1.10 | 19.22 |
| v1.1+T22 | -10.37 | 1.35 | 23.23 | 20.33 | 14.99 | 3.85 | 8.71 |
| T20 sleeve | -5.42 | 4.25 | 8.07 | -9.83 | 20.90 | 8.75 | 9.17 |
| T21 sleeve | 4.09 | 3.39 | 20.96 | -4.12 | 0.86 | 0.98 | 23.70 |
| T22 sleeve | -2.55 | 6.00 | 9.03 | -1.88 | -2.31 | 9.08 | -5.42 |

## 4. Stand-alone sleeves (10% target, decisive costs)


**T20**

| universe | period | Sharpe | return %/yr | vol %/yr | MaxDD % | turnover x/yr |
|---|---|---|---|---|---|---|
| full | 2000-01..2019-12 | 0.126 | 0.75 | 9.85 | -27.04 | 4.45 |
| full | 2020-01..2026-09 | 0.464 | 4.88 | 11.75 | -18.73 | 3.59 |
| full | 2000-01..2026-09 | 0.222 | 1.78 | 10.36 | -28.62 | 4.24 |
| half B | 2000-01..2019-12 | -0.122 | -1.49 | 8.99 | -36.13 | 3.46 |
| half B | 2020-01..2026-09 | 0.043 | -0.07 | 10.13 | -23.77 | 2.99 |
| half B | 2000-01..2026-09 | -0.077 | -1.14 | 9.27 | -47.82 | 3.34 |
| half A | 2000-01..2019-12 | 0.153 | 1.00 | 9.27 | -27.47 | 3.98 |
| half A | 2020-01..2026-09 | 0.531 | 5.39 | 11.04 | -14.28 | 3.46 |
| half A | 2000-01..2026-09 | 0.261 | 2.09 | 9.75 | -27.47 | 3.85 |

**T21**

| universe | period | Sharpe | return %/yr | vol %/yr | MaxDD % | turnover x/yr |
|---|---|---|---|---|---|---|
| full | 2000-01..2019-12 | 0.288 | 2.30 | 9.40 | -29.84 | 3.23 |
| full | 2020-01..2026-09 | 0.675 | 6.94 | 10.79 | -13.48 | 3.35 |
| full | 2000-01..2026-09 | 0.396 | 3.45 | 9.77 | -29.84 | 3.26 |
| half B | 2000-01..2019-12 | 0.011 | -0.37 | 9.82 | -46.60 | 2.75 |
| half B | 2020-01..2026-09 | 0.213 | 1.71 | 10.39 | -21.87 | 3.23 |
| half B | 2000-01..2026-09 | 0.065 | 0.15 | 9.96 | -46.60 | 2.87 |
| half A | 2000-01..2019-12 | 0.206 | 1.42 | 8.69 | -18.84 | 3.34 |
| half A | 2020-01..2026-09 | 0.943 | 7.91 | 8.47 | -8.35 | 3.37 |
| half A | 2000-01..2026-09 | 0.387 | 3.02 | 8.66 | -18.84 | 3.35 |

**T22**

| universe | period | Sharpe | return %/yr | vol %/yr | MaxDD % | turnover x/yr |
|---|---|---|---|---|---|---|
| full | 2000-01..2019-12 | 0.402 | 3.29 | 9.07 | -20.99 | 8.90 |
| full | 2020-01..2026-09 | 0.242 | 1.61 | 7.85 | -11.81 | 9.30 |
| full | 2000-01..2026-09 | 0.365 | 2.86 | 8.77 | -27.08 | 9.00 |
| half B | 2000-01..2019-12 | 0.259 | 1.98 | 9.17 | -18.61 | 7.65 |
| half B | 2020-01..2026-09 | 0.185 | 1.18 | 8.10 | -15.22 | 8.32 |
| half B | 2000-01..2026-09 | 0.242 | 1.77 | 8.90 | -22.86 | 7.82 |
| half A | 2000-01..2019-12 | 0.407 | 3.22 | 8.73 | -23.32 | 7.89 |
| half A | 2020-01..2026-09 | 0.209 | 1.33 | 7.78 | -16.57 | 8.20 |
| half A | 2000-01..2026-09 | 0.361 | 2.74 | 8.50 | -29.27 | 7.96 |

## 5. Sleeve-level statistics

| statistic | value |
|---|---|
| T20 Clark–West, 2010-01..2026-09 | CW t -0.359, one-sided p 0.6403 (201 months) |
| T20 Clark–West, 2020-01..2026-09 | CW t 0.118, one-sided p 0.4531 (81 months) |
| T21 alpha vs the T20 sleeve, 2000-01..2026-09 | 3.42%/yr, NW t 1.893; beta 0.192 (321 months) |
| T21 mean net return, NW t | 2.049 |
| T20 break-even cost multiple (2000-01..2026-09) | 4.24 |
| T21 break-even cost multiple (2000-01..2026-09) | 5.47 |
| T22 break-even cost multiple (2000-01..2026-09) | 6.57 |
| carry's worst 8 months (v1.0 carry-only), 2020-01..2026-09 | 2020-03 2020-07 2021-10 2022-03 2023-04 2023-11 2023-12 2024-08 |

## 6. Deflated Sharpe (C4)

| book | N | SR | DSR (noise-only null) | DSR (dispersed, context) |
|---|---|---|---|---|
| v1.1 | 13 | 0.916 | 0.7393 | 0.9248 |
| v1.1 + T20 | 16 | 0.978 | 0.7444 | 0.9259 |
| v1.1 + T21 | 16 | 1.089 | 0.8402 | 0.9680 |
| v1.1 + T22 | 16 | 0.957 | 0.7450 | 0.9350 |

## 7. Diagnostics (section 3; not criteria)

**Correlations, 2020-01..2026-09** (stand-alone sleeves at decisive costs, v1.1, v1.0's carry sleeve, S&P 500):

| | T20 | T21 | T22 | v1.1 | v1.0 carry | S&P 500 |
|---|---|---|---|---|---|---|
| T20 | 1.00 | 0.59 | 0.36 | 0.15 | 0.25 | 0.10 |
| T21 | 0.59 | 1.00 | 0.22 | 0.08 | 0.07 | -0.04 |
| T22 | 0.36 | 0.22 | 1.00 | 0.05 | 0.04 | -0.20 |
| v1.1 | 0.15 | 0.08 | 0.05 | 1.00 | 0.80 | -0.15 |
| v1.0 carry | 0.25 | 0.07 | 0.04 | 0.80 | 1.00 | -0.14 |
| S&P 500 | 0.10 | -0.04 | -0.20 | -0.15 | -0.14 | 1.00 |

**v1.1's five worst months, 2020-01..2026-09** (%):

| month | v1.1_% | T20_sleeve_% | T21_sleeve_% | T22_sleeve_% |
|---|---|---|---|---|
| 2020-03 | -6.79 | -9.99 | -1.39 | 3.89 |
| 2020-07 | -5.13 | -0.17 | 1.75 | -0.92 |
| 2022-10 | -3.40 | 1.55 | 4.88 | -1.36 |
| 2023-11 | -3.55 | -0.62 | -1.21 | -1.11 |
| 2025-04 | -3.58 | 1.95 | 1.84 | -1.37 |

| diagnostic | value |
|---|---|
| T20 share of markets on Option A | 0.70 |
| BM and carry signals, mean cross-sectional rank correlation | 0.192 |
| T20 and T21 sleeves, return correlation 2000-01..2026-09 | 0.204 |
| T22 gross P&L, bonds, %/yr 2000-01..2026-09 | 0.98 |
| T22 gross P&L, commodities, %/yr 2000-01..2026-09 | 3.30 |
| T22 gross P&L, currencies, %/yr 2000-01..2026-09 | 0.33 |
| T22 mean net currency-futures notional (long foreign currency), 2020-01..2026-09 | 0.068 |
| T22 mean net bond-futures notional, 2020-01..2026-09 | -0.069 |
| T20 integer contracts at US$10m: median rounding error / position; position-months > 50% | 0.072; 197 of 1620 |
| T21 integer contracts at US$10m: median rounding error / position; position-months > 50% | 0.060; 196 of 1620 |
| T22 integer contracts at US$10m: median rounding error / position; position-months > 50% | 0.147; 675 of 2430 |
| T20 mean net weight by sector, 2020-01..2026-09 | energy 0.086, grains and oilseeds -0.057, industrial metals -0.041, livestock -0.058, softs 0.006 |
| T21 mean net weight by sector, 2020-01..2026-09 | energy 0.029, grains and oilseeds 0.039, industrial metals -0.020, livestock -0.026, softs -0.079 |

## 8. Implementation readings (decisions taken under the simplest-reading rule)

1. T21: the 12 holding months are measured between consecutive decision dates (the twelve months to t, settlements up to and including t), from the chained F1 and F2 indices
2. The 10% single-market risk cap of section 2.4 (a sleeve-construction convention) is applied to all three sleeves, measured with each sleeve's own sigma
3. Combination timing: the scale s_t and the gross cap are set at month-end t from v1.1's held weights and the sleeve's weights held after its rebalance in month t; the sleeve leg earns kappa_t = 0.25 s_t (capped) times the sleeve's net return in month t+1 (positions decided at month-end earn next month, as v1.1's FX legs); a change of kappa is a trade of |dkappa| x the sleeve's held notional, charged at its cost rates
4. Clark-West: target = the market's F1 holding-period excess return from this execution to the next; the prevailing mean and the pooled slope use pairs with s < t as pre-registered (holding periods of earlier rebalance months, first forecast at the 2010-01 decision); beta_t = OLS slope of r on z with an intercept; z = cross-sectional ranks standardised to mean 0, SD 1, winsorised at +-2
5. Positions are held in the F1 contract in all three trials (T21's F2 series is used only for its signal). Between executions the number of contracts is constant: daily P&L = w x (F_d - F_d-1) x fx_d / (F_ref x fx_ref), with a missing settlement carried forward.
6. Costs are charged at the execution settlement, with c_raw recomputed for each trade from that contract's settlement and fx; a roll is two trades (old and new contract).
7. Volatility: both estimators are annualised with sqrt(252). For T22 only relative sizes matter, because the sleeve is rescaled to 10%. The RiskMetrics EWMA starts from the first squared return. MOP's EWMA is the demeaned pandas ewm with a centre of mass of 60.
8. Sleeve scaling: the pro-forma volatility uses the markets' calendar-month F1 excess returns over the 36 complete months before the rebalance month (at least 12).
9. Sleeve rebalancing: v1.1's T18 rule (t18_rebal.apply_rules) on the sleeve's own sigma, with one risk budget over the sleeve's active positions.
10. T22: S_t = the number of instruments with a signal that month. A market-month made missing by Amendment 4.4 (platinum, 13 months) has weight 0.
11. Non-USD futures (Eurex in EUR, Long Gilt in GBP) are converted with FRED DEXUSEU and DEXUSUK, read from the kept T16-T19 raw cache.
12. Diagnostics only: the rounding diagnostic sizes the combined sleeve leg (kappa x held weight) at US$10m. Combined turnover is dated in the decision month.

Not reported: T22's P&L attribution by horizon and its net duration. The sleeve holds one blended position per instrument after the T18 band, so a horizon split would itself require an allocation rule. Duration data for the bond futures are not in the inputs, so net bond notional is shown instead.

## 9. Combinations

No trial passed, so no combination is proposed. Any later variant is a new trial with its own pre-registration.
