# T20–T22 Build 0: diagnostic plan for the A4 failure (fixed before the diagnostic is run)

| item | value |
|---|---|
| written | 2026-11-05, after Build 0 (`results/T20-T22/build0.md`, commit `a2c85ae`) recorded A4 = 0.503 against the pre-registered threshold of 0.70, and **before any step below is run**. Committed on its own. |
| scope | Build 0 test A4 only (`docs/prereg/T20-T22_commodity_trials.md` §6). This plan amends nothing in the pre-registration. It does not change A4's definition or threshold, and it runs no trial. |
| blindness | No T20, T21 or T22 sleeve return, Sharpe ratio, drawdown or pass criterion is computed. The only statistics reported are correlations with AQR's factor, counts and error checks. Every series built here stays in the private data repo (`norgate/derived/build0/`). |
| result file | `results/T20-T22/build0_a4_diagnostic.md` |

## Steps, in this order

### (a) Errors in the A4 construction or its inputs

These checks verify that A4 was computed as pre-registered. None of them changes the definition.

1. **Contract pairing.** In every market-month used:
   - F2 is the designated contract immediately after F1.
   - Both have a Norgate settlement on the decision date t.
   - D2 > D1, where D is calendar days from t to the contract's LTD.

   Count every violation, and every month in which D2 − D1 falls outside 15–400 days.
2. **Sign and units of carry_log.**
   - carry_log = (ln F1 − ln F2) × 365/(D2 − D1) must be positive when F1 > F2 (backwardation).
   - Rank weights must be largest for the highest carry_log, sum to 0 and have Σ|w| = 2 every month.
   - The price unit of F1 and F2 must be the same contract unit. Check this by flagging any market-month in which
     |ln(F1/F2)| > 0.5.

   List every |carry_log| > 5 (500% a year) with its cause, as dates and markets only.
3. **Month alignment.** Check by date arithmetic that our label m (positions from the execution date near the 3rd of
   m to the next execution date) corresponds to AQR's row dated at the end of month m, and that AQR's dates are
   month-ends. No re-labelled variant is computed.
4. **Per-market sanity against Norgate.** Re-read every F1 and F2 settlement used by A4 directly from the raw Norgate
   CSV files, independently of `commod_data`, and compare it with the value A4 used. Recompute each market's F1
   holding return over each execution-to-execution period from the raw CSV of that one contract, carrying forward
   the last settlement for missing days, and compare. Count mismatches at a tolerance of 1e-9 relative.

**Definition of a data error.** A data error is any of the following:
- a violation in 1;
- a wrong sign, wrong unit or broken weight constraint in 2;
- a label off by a month in 3;
- any mismatch in 4.

A carry outlier with a genuine cause, such as a near-expiry contract or a negative price, is reported but is not an
error.

### (b) AQR's documented construction

Read the *Century of Factor Premia* workbook's own "Definition" and "Data Sources" tabs, and the paper it cites
(Ilmanen, Israel, Moskowitz, Thapar and Wang, "How Do Factor Premia Vary Over Time? A Century of Evidence"), together
with any construction document they refer to for commodity carry. List every difference between AQR's commodity carry
factor and the pre-registered KMPV-style A4 portfolio, under these headings:
- universe (including any LME metals and markets we do not have);
- the carry measure (which contracts, log or simple, annualisation, any seasonal adjustment);
- weighting (rank, signal-proportional, or quantile; equal-risk or notional);
- volatility scaling of positions and of the factor;
- rebalancing and timing;
- excess-return definition.

### (c) AQR's documented construction, computed once on our data

1. **Write the specification first.** The exact specification is written into the result file and **committed
   before it is computed**. It follows (b), using only markets we have, and every ambiguity in AQR's documentation
   is resolved by the simplest reading, stated in that commit.
2. **Compute it once** on the same Norgate contract data and roll machinery as A4, wherever AQR's documentation does
   not specify otherwise.
3. **Report one number:** its Pearson correlation with AQR's "Commodities Carry" over all overlapping months.

**No other variant is computed.** That includes A4 with different alignment, a different universe, different
weights or different scaling, and any sub-sample used to choose between constructions.

## What each outcome means (fixed now)

| outcome | meaning and action |
|---|---|
| **A data error is found in (a)** | It is corrected as a data fix: a correction to the inputs or to code that did not implement the pre-registered A4. Under §6 of the pre-registration, a data fix is not a trial. **A4 is then re-run once, exactly as pre-registered**, and that correlation, against 0.70, is the A4 result. (b) and (c) are still run, (c) on the corrected data. |
| **No data error, and (c) correlates ≥ 0.90 with AQR's factor** | Our data reproduce AQR's factor when AQR's construction is applied. The data are validated, and A4 compared unlike constructions: the KMPV-style portfolio of the pre-registration against AQR's differently built factor. **A4 as written still records FAIL.** Replacing A4 by the (c) comparison, or changing its threshold, is a pre-registration amendment for the owner, and not part of this diagnostic. |
| **Neither: no data error, and (c) < 0.90** | A4 stands as a fail. The data are not validated against AQR's carry factor, and the trials remain blocked on A4. |

When both happen (a data error is found and fixed, and (c) on the corrected data is ≥ 0.90), the re-run A4 decides
A4. The (c) result is reported as validation, with the same rule as the second row if the re-run A4 is still below
0.70.
