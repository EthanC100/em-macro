# D005: volatility floor for managed currencies on the v1.0 book

Decision **D005** supersedes **D004 rule 4** ("capital controls, a closed market, or a managed peg or crawl in a held
currency -> drop that instrument"). D004 itself is unchanged in `data/ledger/decisions.csv`; rules 1, 2, 3 and 5 stay
in force ([v1_rules.md](v1_rules.md)).

## The rule

A managed currency's realised volatility understates its risk: the central bank holds the rate on a crawl, so the
trailing volatility estimate is low, and v1.0's inverse-volatility sizing gives the leg a very large weight. At the
2026-10 month-end v1.0 estimated TRY's volatility at 3.85% a year (the median of its eight emerging-market currencies
was 9.19%) and held TRY long at 95.78% of capital.

Each month, after v1.0 computes its positions and before they are booked:

1. **Floor.** For each currency on the managed list that v1.0 holds, its volatility estimate (v1.0's own: 36-month
   annualised standard deviation of the monthly excess return, at least 12 months) is floored at the **median of that
   month's volatility estimates of v1.0's emerging-market currencies** (BRL, MXN, ZAR, TRY, IDR, PLN, COP, CLP; GBP
   and EUR are not emerging-market).
2. **Recompute the leg.** The leg's inverse-volatility weight is recomputed with the floored volatility: v1.0 weight x
   (own volatility / floor). Every other factor in v1.0's weight (book scale, 50/50 mix, portfolio scale) is common
   to the book, so this is v1.0's weight with 1/floor in place of 1/vol.
3. **Rescale.** The whole book (FX and bonds) is rescaled to v1.0's **10% volatility target** on v1.0's own measure
   (the pro-forma standard deviation of the trailing 36 months of monthly returns, annualised), then held to v1.0's
   6x gross leverage cap.

If no listed currency is held, or its volatility is at or above the floor, the book is v1.0's, unchanged. Only the
FX leg of a managed currency is floored; its country's bond (TR10Y) is v1.0's, rescaled with the book. Sides never
change.

## The managed list

`config/v1_managed_fx.csv`: one row per currency, with `currency`, `imf_classification`, `source`, `date` and
`evidence`. It is based on the IMF's de facto classification of exchange-rate arrangements (AREAER): crawl-like,
stabilised, crawling peg and conventional peg count as managed. A currency Ethan lists is floored even if the IMF does
not class it as managed. In that case its `evidence` records why. Only v1.0's currencies can be listed. The override
refuses to run on an invalid row.

At 11 Nov 2026 the IMF table "De Facto Classification of Exchange Rate Arrangements, as of April 30, 2026" (IMF Annual
Report 2026, Appendix II.9) classes Türkiye as **crawl-like** (de facto US dollar anchor). It classes Brazil, Chile,
Colombia, Indonesia and South Africa as floating, and Mexico, Poland, the United Kingdom and the euro area as free
floating. The list therefore holds **TRY** only.

The list and the override code (`em_macro/d005.py`, `em_macro/d005_fallback.py`) are protected paths (`.github/CODEOWNERS`, `nightshift/protected.py`). Changing them
needs Ethan's review.

## Where it runs and what it writes

`python -m em_macro.d005 update` is a step of the `systematic-monthly` workflow, after the political-risk overlay and
manual overrides (`em_macro.overlay update`) and before the screener, v1.1, tests and commit.

**Fail-safe.** The step is `continue-on-error`. If D005 errors, v1.0 still rebalances and the month is committed
**as v1.0, unadjusted**, and the run opens the `[ALERT] systematic-monthly failed <date>` issue naming the D005 step:

- `em_macro.d005 update` computes everything before it writes anything, and writes each file atomically. On any
  error it drops this month's D005 rows (so the month is v1.0's everywhere, including the Ledger's positions), keeps
  the D005 P&L of months already booked (recomputed from `weights.csv`, or carried forward from the committed
  `paper_pnl.csv` if that also fails), writes `results/systematic/d005/status.json` with `"status": "failed"` and the
  errors, and exits 1.
- If the process dies before writing (an import error, say), the next step, `python -m em_macro.d005_fallback`
  (standard library only, run only when the D005 step failed), does the same from the committed `paper_pnl.csv`.
- The alert is not closed by a later step while D005 is failing. The Ledger's D005 section shows the failure.
  Re-running the workflow after the fix books the month with D005.

- It imports the frozen v1.0 code (`em_macro/systematic.py`) read-only and checks the frozen design. It never edits
  frozen code, configs, results or tags.
- **v1.0's own files are unchanged**: `results/systematic/positions.csv`, `rebalance_log.csv`,
  `position_adjustments.csv` and `overrides_log.csv` are v1.0's output as before.
- `results/systematic/d005/positions.csv`: the current book, with every leg's v1.0 size, D005 size, change,
  volatility estimate, the floor, the volatility used and the book scale.
- `results/systematic/d005/status.json`: the month's result (`ok` or `failed`, with errors, the floor, the book
  scale and the floored currencies).
- `results/systematic/d005/weights.csv`: the booked record, one row per (as_of, instrument), append-only (a re-run of
  the same month replaces that month). D005's P&L is computed from it, so booked months never change.
- `results/systematic/paper_pnl.csv`: adds `d005_adj` (the D005 book's net return minus v1.0's, with v1.0's timing
  and cost model: FX earns the next month, bonds the month after, and the trade into and out of D005 is charged)
  and `net_before_d005` (= `model_net` + `override_pnl`, v1.0 without D005). It sets `final_net` = `net_before_d005`
  + `d005_adj` and recomputes `cumulative_final`. `net` and `model_net` stay v1.0's, unadjusted. The step is
  idempotent.

The first D005 book is the one set on **3 December 2026** (positions as of 2026-11, effective 2026-12). The
November 2026 positions were booked by v1.0 on 4 November and are not changed. The first non-zero `d005_adj` is
December 2026, booked on 3 January 2027.

`python -m em_macro.d005 dry-run [--as-of YYYY-MM]` prints v1.0's and D005's weights for a month and writes nothing.

## In the Ledger

- **The booked line** is the v1.0 index on `final_net`, as before. It now includes D005.
- **The comparison line** is v1.0 unadjusted (`net_before_d005`). It is shown dashed on the v1.0 chart once D005
  has been applied, and in the "Volatility floor (D005)" section of the Algorithm page with the effect of D005
  (booked / unadjusted - 1). The v1.0 / v1.1 side-by-side still uses `model_net`, the pure strategy.
- The Algorithm page's v1.0 positions show the booked (D005) sizes once a D005 book exists for the current
  positions. The v1.0 size is kept beside them (`v10_size_pct_of_capital`).
- The D004 monitor reports rule 4 as "superseded" with the managed list and never flags it. Rules 1, 2, 3 and 5 are
  measured on the official index (`final_net`), which is the booked book and so includes D005.

## Dry run on the November 2026 positions (11 Nov 2026)

Positions as of 2026-10 (effective 2026-11), `python -m em_macro.d005 dry-run --as-of 2026-10`. Floor 9.19% (median
EM FX volatility). Book scale 1.0186. Pro-forma volatility 10.00% before and after. Gross 4.93x -> 4.45x. Nothing
was booked.

| Instrument | Side | Vol used | v1.0 | D005 | Change |
|---|---|---|---|---|---|
| TRY | long | 3.85% -> 9.19% (floored) | +95.78% | +40.88% | -54.90 |
| IDR | long | 6.55% | +56.31% | +57.36% | +1.05 |
| BRL | long | 10.60% | +34.81% | +35.46% | +0.65 |
| MXN | short | 9.76% | -37.78% | -38.48% | -0.70 |
| PLN | short | 8.31% | -44.38% | -45.21% | -0.83 |
| EUR | short | 7.04% | -52.41% | -53.39% | -0.98 |
| MX10Y | long | 5.59% | +125.85% | +128.19% | +2.35 |
| TR10Y | short | 15.51% | -45.32% | -46.16% | -0.84 |
