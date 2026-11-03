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

