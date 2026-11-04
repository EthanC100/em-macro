# Trials T16–T19: risk batch against frozen v1.0 — results

| item | value |
|---|---|
| pre-registration | `docs/prereg/T16-T19_risk_batch.md`, committed in `4c10856` before any T16–T19 code or computation; ledger rows (pending) in `293799b` |
| ledger | `trials.csv` ids **T16, T17, T18, T19**, groups `G15_carry_crash_filter`, `G16_factor_capped_sizing`, `G17_turnover_reduction`, `G18_vol_forecast_sizing` |
| code at run | `898bc21` (branch `trial/T16-T19-risk-batch`); `em_macro/t16_crash.py`, `t17_factorcap.py`, `t18_rebal.py`, `t19_vol.py`, `t1619.py`; re-uses `em_macro/t01.py` (statistics), `em_macro/tstrend.py` (v1.0 machinery helpers), `em_macro/holdout.py` |
| run | 2026-11-04T13:59:58+00:00 to 2026-11-04T14:01:24+00:00 UTC; pandas 3.0.5, numpy 2.5.3; data through 2026-09; one run per trial, universe and cost setting |
| inputs | v1.0's `data/processed` snapshots at the freeze commit `7886867` (SHA-256 as in `docs/v1.0_freeze.md`), plus the cached raw downloads of 2026-11-04 (`data/kept/T16-T19/`); see decision 15 in §7 |
| v1.0 reproduction | `python -m em_macro.verify_v1`: both committed tables byte-identical (run before the batch); frozen `systematic.evaluate` on this run's inputs vs the committed tables: test 2020-01..2026-09 max abs diff 0.0000 (14 rows), design 2005-2019 max abs diff 0.0000 (14 rows), at the files' 4 decimals |
| v1.0 baseline | tag `v1.0-frozen` = `7886867`; `em_macro/systematic.py` SHA-256 `1eb4cf6b1c537c17…` (unchanged) |
| decision basis | 1x costs (v1.0's cost model), 2020-01..2026-09, all 23 instruments, with the half-B holdout and the deflated Sharpe; 2x costs, 2005-2019 and half A reported, not decisive |
| family | the four trials are one family: Holm correction of the four bootstrap p-values; DSR at N = 13 |

v1.0's figures remain "OOS for v1.0 only". Each trial's figures are reported separately and are not merged with v1.0's track record. Each trial is a single change to v1.0 tested on its own; no combination was run.

## 1. Pre-registered pass/fail tables

### 1x costs (decisive)

| trial | criteria passed | overall |
|---|---|---|
| T16 carry-crash filter | 0 of 3 | FAIL |
| T17 factor-capped sizing | 0 of 3 | FAIL |
| T18 turnover reduction | 4 of 4 | PASS |
| T19 volatility forecasting | 0 of 3 | FAIL |

**T16 carry-crash filter** — overall: **FAIL** (0 of 3 criteria).

| # | criterion | T16 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.659, MaxDD -16.82%, ES 4.92% | SR 0.654, MaxDD -18.48%, ES 5.57% | DD ratio 0.910; ES ratio 0.883; dSR +0.005; p raw 0.1137, Holm 0.2274 | FAIL |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.644, MaxDD -23.21%, ES 8.05% | SR 0.721, MaxDD -22.53%, ES 8.05% | DD ratio 1.031; ES ratio 1.000; dSR -0.077; metric(s) from (1): ES97.5 | FAIL |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.499 (N 13) | DSR 0.619 (N 7) | difference -0.120 | FAIL |

**T17 factor-capped sizing** — overall: **FAIL** (0 of 3 criteria).

| # | criterion | T17 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.645, MaxDD -18.55%, ES 5.57% | SR 0.654, MaxDD -18.48%, ES 5.57% | DD ratio 1.004; ES ratio 0.999; dSR -0.009; p raw 0.0001, Holm 0.0004 | FAIL |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.721, MaxDD -22.53%, ES 8.05% | SR 0.721, MaxDD -22.53%, ES 8.05% | DD ratio 1.000; ES ratio 1.000; dSR +0.000; metric(s) from (1): none | FAIL |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.485 (N 13) | DSR 0.619 (N 7) | difference -0.134 | FAIL |

**T18 turnover reduction** — overall: **PASS** (4 of 4 criteria).

| # | criterion | T18 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.916, MaxDD -15.42%, ES 5.93% | SR 0.654, MaxDD -18.48%, ES 5.57% | DD ratio 0.835; ES ratio 1.064; dSR +0.263; p raw 0.0031, Holm 0.0093 | PASS |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.769, MaxDD -20.08%, ES 7.90% | SR 0.721, MaxDD -22.53%, ES 8.05% | DD ratio 0.891; ES ratio 0.982; dSR +0.048; metric(s) from (1): MaxDD | PASS |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.739 (N 13) | DSR 0.619 (N 7) | difference +0.120 | PASS |
| 4 | T18 only: turnover <= 0.75 x v1.0's (2020-01..2026-09, all instruments) | 11.60x/yr | 19.09x/yr | ratio 0.608 | PASS |

**T19 volatility forecasting** — overall: **FAIL** (0 of 3 criteria).

| # | criterion | T19 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.574, MaxDD -22.78%, ES 7.34% | SR 0.654, MaxDD -18.48%, ES 5.57% | DD ratio 1.233; ES ratio 1.316; dSR -0.079; p raw 0.6239, Holm 0.6239 | FAIL |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.684, MaxDD -22.33%, ES 6.78% | SR 0.721, MaxDD -22.53%, ES 8.05% | DD ratio 0.991; ES ratio 0.843; dSR -0.037; metric(s) from (1): none | FAIL |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.414 (N 13) | DSR 0.619 (N 7) | difference -0.205 | FAIL |

**Holm correction (1x).** Paired circular block bootstrap, block 6 months, B = 10,000, seed 20261103; the null is centred at dSR = -0.05 (Sharpe non-inferiority with margin 0.05). The four p-values are one family.

| trial | p raw (one-sided, H1: dSR > -0.05) | p Holm-adjusted | dSR point | bootstrap SD of dSR |
|---|---|---|---|---|
| T16 carry-crash filter | 0.1137 | 0.2274 | +0.005 | 0.049 |
| T17 factor-capped sizing | 0.0001 | 0.0004 | -0.009 | 0.010 |
| T18 turnover reduction | 0.0031 | 0.0093 | +0.263 | 0.091 |
| T19 volatility forecasting | 0.6239 | 0.6239 | -0.079 | 0.155 |

| trial | dSR | boot mean | boot SD | 5% | 95% | p (margin 0.05) | p (margin 0, spec rule, context) |
|---|---|---|---|---|---|---|---|
| T16 | +0.005 | -0.001 | 0.049 | -0.077 | +0.082 | 0.1137 | 0.4028 |
| T17 | -0.009 | -0.008 | 0.010 | -0.025 | +0.007 | 0.0001 | 0.8295 |
| T18 | +0.263 | +0.279 | 0.091 | +0.142 | +0.439 | 0.0031 | 0.0086 |
| T19 | -0.079 | -0.056 | 0.155 | -0.308 | +0.201 | 0.6239 | 0.7375 |

### 2x costs (sensitivity, not decisive)

| trial | criteria passed | overall |
|---|---|---|
| T16 carry-crash filter | 0 of 3 | FAIL |
| T17 factor-capped sizing | 0 of 3 | FAIL |
| T18 turnover reduction | 4 of 4 | PASS |
| T19 volatility forecasting | 0 of 3 | FAIL |

**T16 carry-crash filter** — overall: **FAIL** (0 of 3 criteria).

| # | criterion | T16 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.274, MaxDD -20.57%, ES 5.12% | SR 0.262, MaxDD -22.14%, ES 5.78% | DD ratio 0.929; ES ratio 0.886; dSR +0.011; p raw 0.0756, Holm 0.1512 | FAIL |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.378, MaxDD -27.04%, ES 8.12% | SR 0.456, MaxDD -26.29%, ES 8.12% | DD ratio 1.029; ES ratio 1.000; dSR -0.078; metric(s) from (1): ES97.5 | FAIL |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.156 (N 13) | DSR 0.237 (N 7) | difference -0.082 | FAIL |

**T17 factor-capped sizing** — overall: **FAIL** (0 of 3 criteria).

| # | criterion | T17 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.250, MaxDD -22.22%, ES 5.78% | SR 0.262, MaxDD -22.14%, ES 5.78% | DD ratio 1.004; ES ratio 0.999; dSR -0.012; p raw 0.0001, Holm 0.0004 | FAIL |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.456, MaxDD -26.29%, ES 8.12% | SR 0.456, MaxDD -26.29%, ES 8.12% | DD ratio 1.000; ES ratio 1.000; dSR +0.000; metric(s) from (1): none | FAIL |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.144 (N 13) | DSR 0.237 (N 7) | difference -0.094 | FAIL |

**T18 turnover reduction** — overall: **PASS** (4 of 4 criteria).

| # | criterion | T18 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.656, MaxDD -16.44%, ES 6.09% | SR 0.262, MaxDD -22.14%, ES 5.78% | DD ratio 0.742; ES ratio 1.054; dSR +0.394; p raw 0.0012, Holm 0.0036 | PASS |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.587, MaxDD -22.34%, ES 7.99% | SR 0.456, MaxDD -26.29%, ES 8.12% | DD ratio 0.850; ES ratio 0.983; dSR +0.131; metric(s) from (1): MaxDD | PASS |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.497 (N 13) | DSR 0.237 (N 7) | difference +0.259 | PASS |
| 4 | T18 only: turnover <= 0.75 x v1.0's (2020-01..2026-09, all instruments) | 11.60x/yr | 19.09x/yr | ratio 0.608 | PASS |

**T19 volatility forecasting** — overall: **FAIL** (0 of 3 criteria).

| # | criterion | T19 | v1.0 | statistic | result |
|---|---|---|---|---|---|
| 1 | 2020-01..2026-09: \|MaxDD\| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10 | SR 0.127, MaxDD -24.39%, ES 7.47% | SR 0.262, MaxDD -22.14%, ES 5.78% | DD ratio 1.101; ES ratio 1.293; dSR -0.135; p raw 0.7550, Holm 0.7550 | FAIL |
| 2 | holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05 | SR 0.365, MaxDD -26.58%, ES 6.93% | SR 0.456, MaxDD -26.29%, ES 8.12% | DD ratio 1.011; ES ratio 0.854; dSR -0.091; metric(s) from (1): none | FAIL |
| 3 | DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7 | DSR 0.085 (N 13) | DSR 0.237 (N 7) | difference -0.152 | FAIL |

**Holm correction (2x).** Paired circular block bootstrap, block 6 months, B = 10,000, seed 20261103; the null is centred at dSR = -0.05 (Sharpe non-inferiority with margin 0.05). The four p-values are one family.

| trial | p raw (one-sided, H1: dSR > -0.05) | p Holm-adjusted | dSR point | bootstrap SD of dSR |
|---|---|---|---|---|
| T16 carry-crash filter | 0.0756 | 0.1512 | +0.011 | 0.045 |
| T17 factor-capped sizing | 0.0001 | 0.0004 | -0.012 | 0.012 |
| T18 turnover reduction | 0.0012 | 0.0036 | +0.394 | 0.104 |
| T19 volatility forecasting | 0.7550 | 0.7550 | -0.135 | 0.151 |

| trial | dSR | boot mean | boot SD | 5% | 95% | p (margin 0.05) | p (margin 0, spec rule, context) |
|---|---|---|---|---|---|---|---|
| T16 | +0.011 | +0.005 | 0.045 | -0.065 | +0.082 | 0.0756 | 0.3420 |
| T17 | -0.012 | -0.011 | 0.012 | -0.031 | +0.007 | 0.0001 | 0.8636 |
| T18 | +0.394 | +0.413 | 0.104 | +0.258 | +0.597 | 0.0012 | 0.0023 |
| T19 | -0.135 | -0.114 | 0.151 | -0.360 | +0.135 | 0.7550 | 0.8434 |

## 2. v1.0 and each trial side by side

Sharpe = mean/SD × √12 of monthly net returns; return = compounded; MaxDD on the compounded monthly index; ES97.5 = historical expected shortfall of monthly net returns (Acerbi-Tasche), as a loss; turnover = one-way notional traded per year, in multiples of capital; costs = cost drag per year.

**Test, 2020-01..2026-09, all 23 instruments (decisive).**

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.65 | 5.96 | 9.56 | -18.48 | 5.57 | 19.09 | 3.73 | 5.49 |
| 1x | T16 | 2020-01 | 81 | 0.66 | 6.13 | 9.75 | -16.82 | 4.92 | 19.21 | 3.75 | 5.46 |
| 1x | T17 | 2020-01 | 81 | 0.65 | 5.83 | 9.48 | -18.55 | 5.57 | 19.09 | 3.74 | 5.48 |
| 1x | T18 | 2020-01 | 81 | 0.92 | 7.96 | 8.80 | -15.42 | 5.93 | 11.60 | 2.28 | 5.25 |
| 1x | T19 | 2020-01 | 81 | 0.57 | 4.98 | 9.20 | -22.78 | 7.34 | 21.23 | 4.12 | 5.30 |
| 2x | v1.0 | 2020-01 | 81 | 0.26 | 2.08 | 9.59 | -22.14 | 5.78 | 19.09 | 7.47 | 5.49 |
| 2x | T16 | 2020-01 | 81 | 0.27 | 2.23 | 9.79 | -20.57 | 5.12 | 19.21 | 7.50 | 5.46 |
| 2x | T17 | 2020-01 | 81 | 0.25 | 1.95 | 9.51 | -22.22 | 5.78 | 19.09 | 7.48 | 5.48 |
| 2x | T18 | 2020-01 | 81 | 0.66 | 5.54 | 8.81 | -16.44 | 6.09 | 11.60 | 4.55 | 5.25 |
| 2x | T19 | 2020-01 | 81 | 0.13 | 0.75 | 9.14 | -24.39 | 7.47 | 21.23 | 8.25 | 5.30 |

**Holdout, half B (BR, CO, ZA, TR, GB, FR, IT; 12 instruments), 2020-01..2026-09.** Each strategy run as a stand-alone universe of half B; T16's crash model trained on half A only.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.72 | 7.54 | 10.95 | -22.53 | 8.05 | 14.41 | 2.81 | 3.88 |
| 1x | T16 | 2020-01 | 81 | 0.64 | 6.61 | 10.88 | -23.21 | 8.05 | 14.46 | 2.82 | 3.83 |
| 1x | T17 | 2020-01 | 81 | 0.72 | 7.54 | 10.95 | -22.53 | 8.05 | 14.41 | 2.81 | 3.88 |
| 1x | T18 | 2020-01 | 81 | 0.77 | 7.45 | 10.02 | -20.08 | 7.90 | 9.12 | 1.80 | 3.73 |
| 1x | T19 | 2020-01 | 81 | 0.68 | 6.86 | 10.52 | -22.33 | 6.78 | 17.17 | 3.26 | 3.74 |
| 2x | v1.0 | 2020-01 | 81 | 0.46 | 4.56 | 11.14 | -26.29 | 8.12 | 14.41 | 5.61 | 3.88 |
| 2x | T16 | 2020-01 | 81 | 0.38 | 3.63 | 11.07 | -27.04 | 8.12 | 14.46 | 5.64 | 3.83 |
| 2x | T17 | 2020-01 | 81 | 0.46 | 4.56 | 11.14 | -26.29 | 8.12 | 14.41 | 5.61 | 3.88 |
| 2x | T18 | 2020-01 | 81 | 0.59 | 5.54 | 10.06 | -22.34 | 7.99 | 9.12 | 3.61 | 3.73 |
| 2x | T19 | 2020-01 | 81 | 0.37 | 3.42 | 10.79 | -26.58 | 6.93 | 17.17 | 6.51 | 3.74 |

**In-sample context, 2005-2019 (cannot affect the decision).** v1.0 was designed on this period; T16's filter is active from 2010 (walk-forward) and off before.

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2006-02 | 167 | 0.40 | 3.56 | 10.10 | -13.82 | 6.15 | 27.87 | 5.35 | 5.66 |
| 1x | T16 | 2006-02 | 167 | 0.39 | 3.48 | 10.08 | -13.66 | 6.34 | 27.93 | 5.35 | 5.63 |
| 1x | T17 | 2006-02 | 167 | 0.39 | 3.55 | 10.19 | -13.96 | 6.16 | 27.94 | 5.36 | 5.66 |
| 1x | T18 | 2006-02 | 167 | 0.61 | 5.37 | 9.25 | -13.95 | 6.03 | 16.65 | 3.19 | 5.43 |
| 1x | T19 | 2006-02 | 167 | 0.26 | 2.12 | 9.73 | -20.22 | 6.99 | 29.27 | 5.50 | 5.57 |
| 2x | v1.0 | 2006-02 | 167 | -0.13 | -1.85 | 10.31 | -28.33 | 6.53 | 27.87 | 10.69 | 5.66 |
| 2x | T16 | 2006-02 | 167 | -0.14 | -1.93 | 10.29 | -28.33 | 6.65 | 27.93 | 10.69 | 5.63 |
| 2x | T17 | 2006-02 | 167 | -0.13 | -1.88 | 10.40 | -28.47 | 6.54 | 27.94 | 10.71 | 5.66 |
| 2x | T18 | 2006-02 | 167 | 0.27 | 2.07 | 9.33 | -17.47 | 6.29 | 16.65 | 6.37 | 5.43 |
| 2x | T19 | 2006-02 | 167 | -0.30 | -3.37 | 9.91 | -39.61 | 7.37 | 29.27 | 11.00 | 5.57 |

**Context: half A (MX, CL, PL, ID, ES, DE, euro area), 2020-01..2026-09, and half B 2005-2019, 1x costs.**

| universe | period | strategy | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr |
|---|---|---|---|---|---|---|---|---|---|
| half A | 2020-01..2026-09 (test) | v1.0 | 81 | 0.69 | 6.77 | 10.30 | -16.82 | 6.18 | 16.48 |
| half A | 2020-01..2026-09 (test) | T16 | 81 | 0.66 | 6.85 | 11.03 | -18.12 | 6.24 | 17.62 |
| half A | 2020-01..2026-09 (test) | T17 | 81 | 0.68 | 6.73 | 10.30 | -16.82 | 6.19 | 16.47 |
| half A | 2020-01..2026-09 (test) | T18 | 81 | 0.71 | 6.91 | 10.22 | -18.04 | 6.35 | 10.55 |
| half A | 2020-01..2026-09 (test) | T19 | 81 | 0.70 | 6.91 | 10.30 | -15.77 | 6.98 | 19.85 |
| half B | 2005-2019 (in-sample, context) | v1.0 | 167 | 0.52 | 5.47 | 11.52 | -28.82 | 6.50 | 21.12 |
| half B | 2005-2019 (in-sample, context) | T16 | 167 | 0.50 | 5.27 | 11.63 | -28.82 | 6.77 | 21.04 |
| half B | 2005-2019 (in-sample, context) | T17 | 167 | 0.52 | 5.47 | 11.52 | -28.82 | 6.50 | 21.12 |
| half B | 2005-2019 (in-sample, context) | T18 | 167 | 0.65 | 6.63 | 10.86 | -23.52 | 6.84 | 12.96 |
| half B | 2005-2019 (in-sample, context) | T19 | 167 | 0.52 | 5.51 | 11.72 | -30.17 | 6.53 | 22.45 |
| half A | 2005-2019 (in-sample, context) | v1.0 | 167 | 0.06 | 0.01 | 12.63 | -31.12 | 10.27 | 21.87 |
| half A | 2005-2019 (in-sample, context) | T16 | 167 | 0.07 | 0.10 | 12.56 | -31.12 | 9.76 | 21.98 |
| half A | 2005-2019 (in-sample, context) | T17 | 167 | 0.02 | -0.64 | 13.28 | -37.21 | 11.81 | 22.13 |
| half A | 2005-2019 (in-sample, context) | T18 | 167 | 0.14 | 0.99 | 11.14 | -25.18 | 8.40 | 13.54 |
| half A | 2005-2019 (in-sample, context) | T19 | 167 | 0.14 | 1.03 | 12.49 | -31.25 | 9.02 | 25.76 |

**v1.0 with no band at all (context for T18, all instruments).**

| costs | strategy | start | months | Sharpe | return %/yr | vol % | MaxDD % | ES97.5 % (monthly) | turnover x/yr | costs %/yr | avg gross lev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | v1.0 | 2020-01 | 81 | 0.65 | 5.96 | 9.56 | -18.48 | 5.57 | 19.09 | 3.73 | 5.49 |
| 1x | v1.0 no band (context) | 2020-01 | 81 | 0.64 | 5.92 | 9.70 | -18.80 | 5.79 | 21.84 | 4.20 | 5.48 |
| 1x | T18 | 2020-01 | 81 | 0.92 | 7.96 | 8.80 | -15.42 | 5.93 | 11.60 | 2.28 | 5.25 |
| 2x | v1.0 | 2020-01 | 81 | 0.26 | 2.08 | 9.59 | -22.14 | 5.78 | 19.09 | 7.47 | 5.49 |
| 2x | v1.0 no band (context) | 2020-01 | 81 | 0.21 | 1.57 | 9.74 | -22.14 | 6.00 | 21.84 | 8.40 | 5.48 |
| 2x | T18 | 2020-01 | 81 | 0.66 | 5.54 | 8.81 | -16.44 | 6.09 | 11.60 | 4.55 | 5.25 |

## 3. By year, 2020–2026 (2026 = January–September), all instruments

Return compounded within the year; MaxDD within the year from the start-of-year level; turnover = notional traded in the year. The trials estimate nothing on returns except T16's walk-forward crash model (fitted each year on data to September of the year before), so each year is a walk-forward year.

*1x costs*

| year | v1.0 return % | T16 return % | T17 return % | T18 return % | T19 return % |
|---|---|---|---|---|---|
| 2020 | -13.90 | -12.11 | -13.96 | -10.06 | -18.66 |
| 2021 | -4.39 | -4.28 | -4.43 | -0.76 | 0.07 |
| 2022 | 20.67 | 21.91 | 19.54 | 20.64 | 14.59 |
| 2023 | 22.44 | 21.71 | 22.48 | 20.36 | 22.13 |
| 2024 | 13.81 | 13.22 | 13.99 | 15.57 | 9.85 |
| 2025 | -0.99 | -1.95 | -0.98 | 0.79 | 1.26 |
| 2026 | 7.85 | 7.82 | 7.85 | 11.07 | 9.54 |

| year | v1.0 Sharpe | T16 Sharpe | T17 Sharpe | T18 Sharpe | T19 Sharpe |
|---|---|---|---|---|---|
| 2020 | -1.54 | -1.43 | -1.55 | -0.96 | -1.79 |
| 2021 | -0.64 | -0.62 | -0.65 | -0.10 | 0.04 |
| 2022 | 1.62 | 1.56 | 1.59 | 1.71 | 1.35 |
| 2023 | 1.72 | 1.66 | 1.72 | 1.76 | 1.96 |
| 2024 | 2.11 | 2.03 | 2.14 | 3.32 | 1.82 |
| 2025 | -0.12 | -0.26 | -0.12 | 0.16 | 0.23 |
| 2026 | 1.19 | 1.10 | 1.19 | 1.83 | 1.49 |

| year | v1.0 MaxDD % | T16 MaxDD % | T17 MaxDD % | T18 MaxDD % | T19 MaxDD % |
|---|---|---|---|---|---|
| 2020 | -18.23 | -16.51 | -18.25 | -15.42 | -22.78 |
| 2021 | -7.79 | -7.83 | -7.79 | -5.47 | -6.14 |
| 2022 | -4.77 | -5.98 | -4.77 | -4.95 | -3.63 |
| 2023 | -6.75 | -7.16 | -6.75 | -6.74 | -3.90 |
| 2024 | -2.04 | -2.17 | -1.97 | -0.45 | -2.32 |
| 2025 | -6.69 | -7.20 | -6.69 | -5.77 | -5.30 |
| 2026 | -4.35 | -4.87 | -4.35 | -1.96 | -3.11 |

| year | v1.0 vol % | T16 vol % | T17 vol % | T18 vol % | T19 vol % |
|---|---|---|---|---|---|
| 2020 | 9.40 | 8.70 | 9.39 | 10.47 | 11.13 |
| 2021 | 6.71 | 6.69 | 6.69 | 5.79 | 7.53 |
| 2022 | 12.12 | 13.29 | 11.72 | 11.42 | 10.49 |
| 2023 | 12.25 | 12.38 | 12.30 | 10.93 | 10.55 |
| 2024 | 6.26 | 6.24 | 6.23 | 4.41 | 5.25 |
| 2025 | 6.61 | 6.77 | 6.61 | 5.93 | 6.35 |
| 2026 | 8.81 | 9.54 | 8.81 | 7.84 | 8.40 |

| year | v1.0 turnover x | T16 turnover x | T17 turnover x | T18 turnover x | T19 turnover x |
|---|---|---|---|---|---|
| 2020 | 12.64 | 12.64 | 12.70 | 7.63 | 13.91 |
| 2021 | 12.92 | 13.06 | 12.92 | 7.64 | 15.92 |
| 2022 | 14.05 | 14.22 | 13.83 | 9.01 | 21.27 |
| 2023 | 18.48 | 18.67 | 18.66 | 11.74 | 22.02 |
| 2024 | 25.70 | 25.76 | 25.68 | 15.87 | 25.83 |
| 2025 | 31.96 | 32.06 | 31.97 | 19.40 | 31.32 |
| 2026 | 13.08 | 13.25 | 13.08 | 7.01 | 13.02 |

*2x costs*

| year | v1.0 return % | T16 return % | T17 return % | T18 return % | T19 return % |
|---|---|---|---|---|---|
| 2020 | -16.12 | -14.37 | -16.18 | -11.44 | -20.74 |
| 2021 | -6.66 | -6.58 | -6.69 | -2.15 | -2.91 |
| 2022 | 17.28 | 18.55 | 16.21 | 18.43 | 9.75 |
| 2023 | 18.05 | 17.28 | 18.03 | 17.63 | 16.94 |
| 2024 | 8.33 | 7.75 | 8.50 | 12.14 | 4.55 |
| 2025 | -6.91 | -7.85 | -6.90 | -2.95 | -4.77 |
| 2026 | 5.16 | 5.09 | 5.16 | 9.53 | 6.95 |

| year | v1.0 Sharpe | T16 Sharpe | T17 Sharpe | T18 Sharpe | T19 Sharpe |
|---|---|---|---|---|---|
| 2020 | -1.78 | -1.70 | -1.80 | -1.09 | -2.01 |
| 2021 | -0.97 | -0.96 | -0.98 | -0.35 | -0.35 |
| 2022 | 1.37 | 1.34 | 1.33 | 1.54 | 0.94 |
| 2023 | 1.45 | 1.38 | 1.44 | 1.56 | 1.61 |
| 2024 | 1.24 | 1.16 | 1.27 | 2.54 | 0.83 |
| 2025 | -1.03 | -1.16 | -1.03 | -0.47 | -0.72 |
| 2026 | 0.80 | 0.74 | 0.80 | 1.59 | 1.11 |

| year | v1.0 MaxDD % | T16 MaxDD % | T17 MaxDD % | T18 MaxDD % | T19 MaxDD % |
|---|---|---|---|---|---|
| 2020 | -19.78 | -18.08 | -19.81 | -16.44 | -24.24 |
| 2021 | -8.87 | -8.92 | -8.87 | -5.99 | -7.52 |
| 2022 | -5.41 | -6.60 | -5.42 | -5.39 | -4.26 |
| 2023 | -6.76 | -7.21 | -6.75 | -6.94 | -3.99 |
| 2024 | -3.89 | -4.08 | -3.80 | -1.53 | -4.17 |
| 2025 | -8.22 | -8.72 | -8.22 | -6.80 | -6.97 |
| 2026 | -5.18 | -5.73 | -5.18 | -2.45 | -3.96 |

| year | v1.0 vol % | T16 vol % | T17 vol % | T18 vol % | T19 vol % |
|---|---|---|---|---|---|
| 2020 | 9.54 | 8.84 | 9.52 | 10.58 | 11.19 |
| 2021 | 6.87 | 6.83 | 6.84 | 5.82 | 7.68 |
| 2022 | 12.23 | 13.41 | 11.82 | 11.46 | 10.42 |
| 2023 | 11.94 | 12.08 | 12.03 | 10.80 | 10.09 |
| 2024 | 6.64 | 6.63 | 6.61 | 4.57 | 5.57 |
| 2025 | 6.71 | 6.85 | 6.71 | 5.97 | 6.53 |
| 2026 | 8.80 | 9.54 | 8.80 | 7.86 | 8.36 |

| year | v1.0 turnover x | T16 turnover x | T17 turnover x | T18 turnover x | T19 turnover x |
|---|---|---|---|---|---|
| 2020 | 12.64 | 12.64 | 12.70 | 7.63 | 13.91 |
| 2021 | 12.92 | 13.06 | 12.92 | 7.64 | 15.92 |
| 2022 | 14.05 | 14.22 | 13.83 | 9.01 | 21.27 |
| 2023 | 18.48 | 18.67 | 18.66 | 11.74 | 22.02 |
| 2024 | 25.70 | 25.76 | 25.68 | 15.87 | 25.83 |
| 2025 | 31.96 | 32.06 | 31.97 | 19.40 | 31.32 |
| 2026 | 13.08 | 13.25 | 13.08 | 7.01 | 13.02 |

## 4. v1.0's five worst months, 2020-01..2026-09 (net return, %)

The five lowest monthly net returns of v1.0 at 1x costs, with each trial's net return in the same months.

| month | v1.0 1x % | T16 1x % | T17 1x % | T18 1x % | T19 1x % |
|---|---|---|---|---|---|
| 2020-03 | -6.12 | -4.76 | -6.14 | -6.79 | -6.99 |
| 2020-07 | -5.07 | -5.10 | -5.05 | -5.13 | -7.77 |
| 2020-06 | -3.78 | -3.76 | -3.79 | -3.22 | -3.21 |
| 2022-10 | -3.71 | -4.22 | -3.70 | -3.40 | -3.63 |
| 2025-04 | -3.63 | -3.87 | -3.63 | -3.58 | -2.83 |

| month | v1.0 2x % | T16 2x % | T17 2x % | T18 2x % | T19 2x % |
|---|---|---|---|---|---|
| 2020-03 | -6.30 | -4.93 | -6.31 | -6.91 | -7.10 |
| 2020-07 | -5.30 | -5.33 | -5.28 | -5.33 | -7.93 |
| 2020-06 | -4.28 | -4.26 | -4.30 | -3.54 | -3.65 |
| 2022-10 | -3.80 | -4.32 | -3.79 | -3.54 | -3.83 |
| 2025-04 | -3.79 | -4.00 | -3.79 | -3.83 | -3.10 |

Sum over the five months: v1.0 1x -22.31%; T16 1x -21.71%; T17 1x -22.31%; T18 1x -22.12%; T19 1x -24.43%; v1.0 2x -23.46%; T16 2x -22.84%; T17 2x -23.46%; T18 2x -23.15%; T19 2x -25.62%.

## 5. Deflated-Sharpe update

PSR and DSR (spec §0.2; `em_macro/mtstats.py`) from each strategy's realised 2020-01..2026-09 monthly Sharpe, skewness and raw kurtosis, T = 81. Noise-only null: trial-Sharpe SD = 1/√80 per month (decisive). Dispersed: SD 0.20 annualised. N incremented for the whole family: spec convention 7 → 13 (each trial at 13 against v1.0 at 7); ledger convention 14 → 18 (context).

*1x costs*

| strategy | convention | N | SR_ann | skew | kurtosis_raw | PSR(SR*=0) | SR0_noise_ann | DSR_noise | SR0_dispersed_ann | DSR_dispersed |
|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 | spec | 7 | 0.654 | 0.185 | 2.903 | 0.956 | 0.537 | 0.619 | 0.277 | 0.837 |
| T16 | spec | 13 | 0.659 | 0.362 | 2.999 | 0.960 | 0.660 | 0.499 | 0.341 | 0.801 |
| T17 | spec | 13 | 0.645 | 0.158 | 2.867 | 0.953 | 0.660 | 0.485 | 0.341 | 0.786 |
| T18 | spec | 13 | 0.916 | -0.096 | 3.438 | 0.989 | 0.660 | 0.739 | 0.341 | 0.925 |
| T19 | spec | 13 | 0.574 | -0.125 | 4.105 | 0.927 | 0.660 | 0.414 | 0.341 | 0.723 |
| v1.0 | ledger | 14 | 0.654 | 0.185 | 2.903 | 0.956 | 0.673 | 0.480 | 0.348 | 0.787 |
| T16 | ledger | 18 | 0.659 | 0.362 | 2.999 | 0.960 | 0.718 | 0.438 | 0.371 | 0.778 |
| T17 | ledger | 18 | 0.645 | 0.158 | 2.867 | 0.953 | 0.718 | 0.425 | 0.371 | 0.762 |
| T18 | ledger | 18 | 0.916 | -0.096 | 3.438 | 0.989 | 0.718 | 0.690 | 0.371 | 0.914 |
| T19 | ledger | 18 | 0.574 | -0.125 | 4.105 | 0.927 | 0.718 | 0.358 | 0.371 | 0.697 |

*2x costs*

| strategy | convention | N | SR_ann | skew | kurtosis_raw | PSR(SR*=0) | SR0_noise_ann | DSR_noise | SR0_dispersed_ann | DSR_dispersed |
|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 | spec | 7 | 0.262 | 0.238 | 2.890 | 0.753 | 0.537 | 0.237 | 0.277 | 0.484 |
| T16 | spec | 13 | 0.274 | 0.416 | 3.018 | 0.763 | 0.660 | 0.156 | 0.341 | 0.430 |
| T17 | spec | 13 | 0.250 | 0.214 | 2.858 | 0.742 | 0.660 | 0.144 | 0.341 | 0.407 |
| T18 | spec | 13 | 0.656 | -0.066 | 3.434 | 0.952 | 0.660 | 0.497 | 0.341 | 0.789 |
| T19 | spec | 13 | 0.127 | -0.106 | 3.880 | 0.628 | 0.660 | 0.085 | 0.341 | 0.291 |
| v1.0 | ledger | 14 | 0.262 | 0.238 | 2.890 | 0.753 | 0.673 | 0.142 | 0.348 | 0.412 |
| T16 | ledger | 18 | 0.274 | 0.416 | 3.018 | 0.763 | 0.718 | 0.122 | 0.371 | 0.399 |
| T17 | ledger | 18 | 0.250 | 0.214 | 2.858 | 0.742 | 0.718 | 0.112 | 0.371 | 0.377 |
| T18 | ledger | 18 | 0.656 | -0.066 | 3.434 | 0.952 | 0.718 | 0.438 | 0.371 | 0.766 |
| T19 | ledger | 18 | 0.127 | -0.106 | 3.880 | 0.628 | 0.718 | 0.064 | 0.371 | 0.265 |

## 6. Trial diagnostics (context; not pass criteria)

### T16 carry-crash filter

| universe (model trained on) | labelled obs | crash rate (all labels) | test obs | test crash rate | AUC test | Brier skill test | AUC 2010-19 | Brier skill 2010-19 | share of currency-months scaled < 1 (test) | share scaled to 0 (test) | mean scale (test) | imputed feature cells |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (all) | 2454 | 0.048 | 780 | 0.026 | 0.567 | -0.014 | 0.405 | -0.196 | 0.364 | 0.000 | 0.935 | 896 |
| half B (half A) | 1230 | 0.054 | 390 | 0.031 | 0.360 | -0.096 | 0.262 | -0.236 | 0.205 | 0.047 | 0.895 | 442 |
| half A (half A) | 1224 | 0.042 | 390 | 0.021 | 0.637 | -0.195 | 0.544 | -0.130 | 0.254 | 0.062 | 0.876 | 454 |

The spec's own filter checks (§6.2: walk-forward AUC > 0.60, Brier skill > 0 on half B) are shown for information; the pre-registered pass rule is §4 of the pre-registration.

Walk-forward fits on all 10 currencies (standardised coefficients; C by time-blocked CV):

| year | train obs | C chosen | p_base | coef carry_z | coef value | coef ca_gdp | coef res_imp | coef vol_ratio | coef d3_vix | coef d3_usd | coef d3_us2y | coef own12 | coef election |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2010 | 444 | 0.1 | 0.113 | -0.23 | -0.65 | -0.07 | -0.06 | +0.09 | -0.01 | +1.09 | +0.40 | +0.40 | +0.04 |
| 2011 | 564 | 0.01 | 0.089 | -0.05 | -0.15 | -0.05 | -0.03 | +0.12 | +0.12 | +0.26 | +0.11 | +0.05 | -0.04 |
| 2012 | 684 | 0.01 | 0.076 | -0.06 | -0.13 | -0.04 | -0.05 | +0.12 | +0.11 | +0.28 | +0.10 | +0.06 | -0.05 |
| 2013 | 804 | 0.01 | 0.065 | -0.06 | -0.15 | -0.02 | -0.07 | +0.13 | +0.14 | +0.26 | +0.09 | +0.09 | -0.04 |
| 2014 | 924 | 0.01 | 0.060 | -0.03 | -0.17 | -0.01 | -0.07 | +0.16 | +0.15 | +0.26 | +0.09 | +0.09 | -0.04 |
| 2015 | 1044 | 0.01 | 0.056 | -0.02 | -0.19 | -0.00 | -0.07 | +0.20 | +0.15 | +0.27 | +0.09 | +0.10 | -0.05 |
| 2016 | 1164 | 0.01 | 0.063 | -0.01 | -0.11 | -0.00 | -0.01 | +0.22 | +0.14 | +0.23 | +0.11 | +0.06 | -0.09 |
| 2017 | 1284 | 0.01 | 0.064 | -0.02 | -0.11 | -0.02 | -0.04 | +0.22 | +0.14 | +0.21 | +0.11 | +0.06 | -0.05 |
| 2018 | 1404 | 0.01 | 0.060 | -0.02 | -0.13 | -0.03 | -0.06 | +0.22 | +0.14 | +0.22 | +0.10 | +0.05 | -0.06 |
| 2019 | 1524 | 0.01 | 0.059 | +0.05 | -0.10 | -0.05 | -0.09 | +0.23 | +0.14 | +0.22 | +0.09 | +0.02 | -0.03 |
| 2020 | 1644 | 0.01 | 0.056 | +0.05 | -0.11 | -0.06 | -0.10 | +0.24 | +0.14 | +0.22 | +0.10 | +0.03 | -0.03 |
| 2021 | 1764 | 0.01 | 0.061 | +0.05 | -0.12 | -0.08 | -0.04 | +0.20 | +0.17 | +0.19 | +0.09 | +0.02 | -0.06 |
| 2022 | 1884 | 0.01 | 0.058 | +0.08 | -0.11 | -0.10 | -0.07 | +0.20 | +0.18 | +0.20 | +0.09 | +0.02 | -0.06 |
| 2023 | 2004 | 0.01 | 0.056 | +0.09 | -0.11 | -0.11 | -0.08 | +0.20 | +0.16 | +0.18 | +0.02 | +0.03 | -0.06 |
| 2024 | 2124 | 0.01 | 0.054 | +0.08 | -0.11 | -0.12 | -0.08 | +0.16 | +0.16 | +0.19 | -0.02 | +0.01 | -0.03 |
| 2025 | 2244 | 0.01 | 0.053 | +0.08 | -0.12 | -0.11 | -0.09 | +0.15 | +0.16 | +0.19 | -0.01 | +0.01 | -0.01 |
| 2026 | 2364 | 0.01 | 0.050 | +0.08 | -0.11 | -0.13 | -0.09 | +0.15 | +0.17 | +0.19 | -0.01 | +0.01 | -0.01 |

### T17 factor-capped sizing

| item | value |
|---|---|
| decision months modelled, 2020-01..2026-09 | 81 |
| months in which a cap bound (adjusted) | 9 (USD cap breached 6, EM cap breached 3; fallback used 0) |
| max USD / EM share of v1.0's targets before capping (test) | 29.6% / 53.3% |
| when adjusted: mean \|\|w - w0\|\|, mean positions opened in unselected instruments, their mean gross | 0.018; 9.0; 0.027 |
| months adjusted, all months 2005-2026 | 24 of 225 |
| held positions, version-B USD share, test: v1.0 mean / max | 10.7% / 27.3% |
| held positions, version-B USD share, test: T17 mean / max | 10.6% / 27.5% |
| held positions, version-B EM share, test: v1.0 mean / max | 11.8% / 51.2% |
| held positions, version-B EM share, test: T17 mean / max | 11.8% / 46.1% |
| held positions, USD+EM combined, test: v1.0 mean / max; T17 mean / max | 22.6% / 55.2%; 22.5% / 56.6% |

The held-position shares differ from the target shares because the 6× cap, the band and the one-month bond lag act after the cap. The 75% USD share in the risk audit was the daily-priced version A (14 instruments); version B (full book, monthly) is the measure T17 caps.

### T18 turnover reduction

| item | value |
|---|---|
| turnover x/yr, FX book: v1.0 / T18 | 5.47 / 3.38 |
| turnover x/yr, bond book: v1.0 / T18 | 13.61 / 8.22 |
| proposed trades 2020-2026 (target differs from held) | 1511; suppressed by the band 793 (52.5%); residual closes 73 |
| mean gross held / gross target (test) | 0.962 |
| average gross leverage (test): v1.0 / T18 | 5.49 / 5.25 |

### T19 volatility forecasting

| item | value |
|---|---|
| share of instrument-months in which the floor 0.8·σ_EWMA250 sets the estimate (test) | 29.7% |
| mean ratio of T19's instrument vol estimate to v1.0's 36-month vol (test) | 0.972 |
| average gross leverage (test): v1.0 / T19 | 5.49 / 5.30 |
| realised vol by year, % (v1.0 / T19) | 2020: 9.4 / 11.1; 2021: 6.7 / 7.5; 2022: 12.1 / 10.5; 2023: 12.2 / 10.6; 2024: 6.3 / 5.2; 2025: 6.6 / 6.3; 2026: 8.8 / 8.4 |

## 7. Decisions taken under the task's rules

All were fixed in the pre-registration (§7 there) before any computation; none was changed afterwards.

1. **T16 horizon h = 3 months:** the spec gives h ∈ {1, 3, 6}; the central value was used.
2. **T16 features and proxies:** NFA/GDP and the CFTC positioning z-score omitted (no data among the inputs; no proxy measures the same thing). Reserves/short-term debt proxied by reserves in months of imports (World Bank, in the panel). VAL_reer proxied by v1.0's real-exchange-rate value (BIS REER not among the inputs). WEO current account from the single latest vintage (October 2026), the value of year Y−1 used throughout year Y: revised data, a flagged look-ahead risk. Euro-area external features = mean of DE, FR, IT, ES. Election feature from `data/events/elections.csv` (snap elections a small look-ahead).
3. **T16 penalty:** C chosen by 5-block time-blocked cross-validation over {0.01, 0.1, 1, 10, 100} with a 3-month purge; ties → C = 1.0 (the spec code's default). Missing features imputed at the training mean.
4. **T16 walk-forward start:** expanding window from 2005 (inputs start then; the spec's 1995 is not available). Decisive years 2020–2026; context years 2010–2019; no filter before 2010.
5. **T16 placement:** the scale multiplies long currency positions after v1.0's 10% total rescaling and before the 6× cap and the band. The holdout model is trained on half A only and applied to half B.
6. **T17 risk measure:** the risk audit's version B (monthly returns, Ledoit-Wolf, 60 months, all 23 instruments) rather than the spec's 3-day version A, which covers only 14 instruments. Caps USD 25% and EM 40% (the spec's [A] values); the country, LatAm and duration caps were excluded as not part of the single change. Adjustment by SLSQP with a projection fallback, support unrestricted as the spec's QP is written; re-scaled to 10% after the cap with v1.0's own rule (spec Build 5 order).
7. **T18 rules:** both of the spec's rebalancing rules with the spec's values (band 0.1 of the position's risk budget, applied to the proposed trade; partial factor 0.5). The position's risk budget is the equal risk v1.0 gives each selected position of a book. The residual of an exited position is closed once its half-trade falls inside the band.
8. **T19 estimator:** the spec's floor formula max(σ_EWMA60, 0.8·σ_EWMA250) with half-lives converted to months at 21 trading days (2.857 and 11.905), a zero-mean EWMA of squared monthly returns (spec §7 recursion), min 12 months; applied at all three points where v1.0 uses its 36-month volatility (instrument vol, book scaler, total scaler).
9. **Sharpe criterion:** a non-inferiority test with margin 0.05 (H1: ΔSR > −0.05), one-sided 6-month block-bootstrap p, Holm-adjusted across the four trials, level 0.10 (the spec's); the point estimate must also be ≥ −0.05.
10. **Risk criterion:** "at least 10% better" = the trial's |MaxDD| or ES97.5 at most 0.90 × v1.0's; the same metric must meet the bar in half B.
11. **Deflated Sharpe:** spec convention N = 7 → 13 (7 + T01 + T02 + the four of this family), every trial compared with v1.0 at N = 7; ledger convention 14 → 18 reported as context.
12. **2x costs:** the trial rules applied identically with every cost doubled; reported only.
13. **Raw data:** one archive of the raw downloads used (FRED, Yahoo, BIS, BanRep, BCCh/mindicador) under `data/kept/T16-T19/`, recorded in `docs/raw_data_archive.md` for the four trials.
14. **Merge conflicts with `main`:** none arose (the branch was cut from `main` at `360f816`); the rule was to keep both sides.
15. **Input snapshots (taken at run time, before any result was computed):** the working tree's three `data/processed` snapshots had been rebuilt by the November 2026 monthly workflow (`bd236f9`) after v1.0's freeze, and on them frozen v1.0's test table differs from the committed one at the 4th decimal (max 0.0001, the runner's guard). The batch therefore read the snapshots at the freeze commit `7886867` (`verify_v1.extract_snapshots`, SHA-256 as in `docs/v1.0_freeze.md`; recorded in `RUN.json`), on which v1.0 reproduces exactly; the pre-registration's wording "working-tree versions" was written before the refreshed snapshots were found. The crash filter's panel features (current account, reserves) and the dollar index come from the same snapshots; the election calendar and the raw caches are the working tree's.

## 8. Note on combining passing trials (not tested here)

One trial passed at 1x (T18 turnover reduction); there is nothing to combine it with from this family. Any future combination with a trial from another family would be a new pre-registered trial.

## 9. Notes

- **Identity checks run before the comparison:** each trial's code reproduces frozen v1.0 exactly when its one change is switched off (T18 with v1.0's band through the T18 P&L path; T19 with v1.0's 36-month estimator; T17 with caps that never bind; T16 with scale 1), on this run's inputs (asserted in the runner) and on synthetic inputs (`tests/test_t1619.py`).
- **Moments and DSR.** Skewness is the pandas bias-corrected skewness; kurtosis is raw (normal = 3).
- **T16 look-ahead caveats.** Two features use the latest WEO/WDI vintage (lagged one year) and the election calendar as recorded now; the model is otherwise point-in-time (walk-forward fits, labels purged). Daily spot for the volatility ratio comes from the same sources as v1.0's month-end spot.
- **Runs.** Every table in `results/T16-T19/` comes from one invocation of `python -m em_macro.t1619 run`; no trial was re-run or re-parameterised.

## 10. Files

- `results/T16-T19/performance.csv`: every strategy × universe (all, half A, half B) × costs × period; `monthly_net.csv`: monthly net returns of every run; `by_year_2020_2026.csv`; `worst_months.csv`.
- `results/T16-T19/pass_fail_<trial>_{1x,2x}.csv`, `holm_{1x,2x}.csv`, `criteria.json` (bootstrap, DSR, every criterion statistic).
- `results/T16-T19/diagnostics.json`, `t16_model.json`, `t16_{features,prob,scale}_<universe>.csv`, `t17_caplog_*.csv`, `t17_shares_{v1,T17}.csv`, `t18_tradelog_*.csv`.
- `results/T16-T19/RUN.json`: run time, code commit, SHA-256 of code, pre-registration and input files, the v1.0 reproduction check.
- Code: `em_macro/t16_crash.py`, `t17_factorcap.py`, `t18_rebal.py`, `t19_vol.py` (one module per trial), `em_macro/t1619.py` (runner and statistics), `em_macro/t1619_report.py`. Tests: `tests/test_t1619.py`.
- Raw data: `data/kept/T16-T19/` (see `docs/raw_data_archive.md`).
