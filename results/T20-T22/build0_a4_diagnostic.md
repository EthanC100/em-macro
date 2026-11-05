# Build 0, A4 diagnostic — results

Plan: `docs/prereg/T20-T22_A4_diagnostic.md`, committed in `d99edae` before any step was run. The steps were run in the
plan's order. Only correlations, counts and check results are reported. Every series is in the private data repo
(`norgate/derived/build0/`). No T20–T22 sleeve statistic was computed. The script is
`em_macro/commod_a4diag.py`, with step (c) in `em_macro/commod_a4aqr.py`, and the figures are in
`build0_a4_diagnostic.json`.

## (a) Errors in the A4 construction or its inputs

Checks over all 24 markets and 10,355 market-months in which A4 had a carry value:

| check (plan item) | result |
|---|---|
| 1. F2 is the designated contract right after F1; both settle on t; D2 > D1; 15 ≤ D2 − D1 ≤ 400 days | 0 violations |
| 2. carry_log formula, sign (positive in backwardation) and units, recomputed from raw settlements | 0 violations |
| 2. rank weights sum to 0, Σ\|w\| = 2 and are ordered by the signal, every month | 0 violations in 441 months |
| 2. \|ln(F1/F2)\| > 0.5 (unit mismatch) | 0 |
| 2. \|carry_log\| > 5 (500% a year) | 0 |
| 3. AQR rows are business month-ends, one per consecutive month; our label m is the execution month (execution on the 1st–7th of m) | holds |
| 4. every F1/F2 settlement used, re-read from the raw Norgate CSVs independently of `commod_data` | 0 mismatches |
| 4. every F1 holding return, recomputed from the one contract's raw CSV | **24 mismatches on the first run**, then 0 after the fix |

**Data error found.** The 24 mismatches are the first rebalance month of each market: 1990-01, or 1990-05 for NG
and 2005-11 for RB. A4's chained index began the day after the first execution, so the first month had no holding
return. A4 therefore left out 1990-01, which is an overlapping month with AQR. This is an error in code that did not
implement the pre-registered A4. It was fixed in `em_macro/commod_build0.py`: the index is 1 at the first execution
settlement.

**A4 re-run once, exactly as pre-registered: correlation 0.503** over 434 months (1990-01..2026-02). Before the fix
it was 0.503 over 433 months. From 2000-01 it is 0.524. **A4 = 0.503 < 0.70: FAIL.** Every other Build 0 result is
unchanged by the fix (`results/T20-T22/build0.json`, identical apart from A4).

## (b) AQR's documented construction, and every difference from A4

Source: the *Century of Factor Premia* workbook's Definition and Data Sources tabs. These hold page images from
Ilmanen, Israel, Lee, Moskowitz and Thapar (2021), "How Do Factor Premia Vary Over Time? A Century of Evidence",
section 2 and Appendix A. They are summarised here, not reproduced.

AQR's construction is documented as follows:
- **Carry:** "as in Koijen, Moskowitz, Pedersen and Vrugt (2018) … for commodity futures, carry is the return from
  holding a futures contract if there is no shift in the futures curve, measured by the percent difference in prices
  between the nearest and next-nearest-to-maturity contract."
- **Weights:** w_i,t = c_t (rank(S_i,t) − Σ_i rank(S_i,t)/N). c_t scales the portfolio to "zero-cost, one dollar long
  and short", and the return in month t is Σ_i w_i,t−1 r_i,t.
- **Commodity returns:** monthly. "At each month end … we hold the nearest of the contracts whose delivery month is at
  least two months away" (Brent: at least three). When that contract has no return, the next contract is used, up to
  the fifth, and otherwise the contract in front. Contiguous limit-day moves are moved into the first limit day.
- **Universe:** 30 commodities (energy, base metals, precious metals, agriculture, livestock). Prices come from CSI
  for 1951–2012 and Bloomberg after 2012. "For base metals and platinum, rolled return series from the S&P, Goldman
  Sachs, and Bloomberg are used."
- **Scaling:** none within the asset class. Inverse-volatility weights are applied only when asset classes are
  combined, which does not affect "Commodities Carry".

| heading | AQR "Commodities Carry" | pre-registered A4 |
|---|---|---|
| universe | 30 commodities, including the base metals (LME aluminium, copper, nickel, zinc, lead and tin, through index rolled return series) and platinum through an index series | our 24 exchange-traded markets: no LME metals; platinum and palladium from contract data |
| carry measure | percent difference, nearest against next-nearest-to-maturity contract, over **all listed months**, **not annualised** as documented | log difference of F1 and F2 from the **designated calendar after the 35-day roll rule**, **annualised** by 365/(D2 − D1) |
| contracts for returns | nearest contract with delivery at least 2 months away (Brent 3), across all listed months, with fallbacks | F1 of the 35-day rule on the designated calendar |
| weighting | demeaned ranks, $1 long and $1 short | the same: s = rank − (n+1)/2 scaled to Σ\|s\| = 2 |
| volatility scaling | none | none |
| rebalancing and timing | signal at month-end t−1; return over calendar month t, month-end to month-end | signal at the decision date (the business day before the first settlement on or after the 3rd); return from that execution to the next |
| excess return | futures return, month-end to month-end price change of the held contract; limit-day reassignment | same-contract daily returns chained between execution dates; no limit-day reassignment |
| data | CSI and Bloomberg; index series for base metals and platinum | Norgate settlements |

## (c) AQR's documented construction on our data — specification, fixed before computing

This specification was written and committed before (c) was computed. It is AQR's documented construction from (b),
applied to our 24 markets with Norgate contract data. Ambiguities are resolved by the simplest reading, as listed
below.

1. **Universe.** The 24 commodity markets in `em_macro/commod_data.py`, using every contract month Norgate lists, not
   only the designated calendar. There are no LME metals.
2. **Month-ends.** A market's month-end is its last trading day of the calendar month, the last date on which any of
   its contracts has a settlement.
3. **Carry at month-end t−1.** Among the market's contracts with a settlement on that day, the nearest is the one
   with the earliest contract month and the next-nearest is the second earliest. carry = (F_nearest − F_next) /
   F_next.
   - It is not annualised, which is the literal reading of "percent difference in prices".
   - The denominator is the next-nearest contract, KMPV's (F1 − F2)/F2 form.
   - Carry is missing if either price is ≤ 0.
4. **Return in month t.** The desired contract is the nearest contract whose delivery month is at least two
   calendar months after month t, or three for Brent.
   - For example, during February the market holds the April contract, chosen at the end of January.
   - A contract "has a return" in month t when it has a settlement on both month-end t−1 and month-end t. The return
     is F(end t)/F(end t−1) − 1.
   - When the desired contract has no return, the next contracts are tried in order, up to the fifth contract
     counting the desired one as the first. If none has a return, the contract in front of the desired one is used.
     If that also has none, the market has no return in month t.
5. **Weights.** At month-end t−1, over the markets with both a carry value and a return in month t:
   w = rank(carry) − mean rank, scaled to Σ\|w\| = 2 ($1 long and $1 short). The portfolio return in month t is
   Σ w_i r_i,t. At least 2 markets are required.
6. **Not replicated.**
   - AQR's limit-day reassignment needs exchange limit tables that are not in the data. Month-end settlements are
     used as they are.
   - The base metals are not available.
   - AQR's own data sources are not used.
7. **Window and statistic.** Months 1990-01 to 2026-02, the same window as A4, ending with AQR's last row. The one
   number reported is the Pearson correlation with AQR's "Commodities Carry" over the overlapping months.

It is computed once. No other variant is computed.

## (c) Result

C_RESULT
