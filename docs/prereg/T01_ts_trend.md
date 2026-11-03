# Pre-registration — trial T01: time-series trend sleeve

| item | value |
|---|---|
| trial | T01 (pre-registered trial series). **Ledger id `T12`** in `trials.csv`, because `T01` is already the ledger id of v1.0 itself; the ledger row's name says "T01". |
| branch | `trial/T01-ts-trend` |
| baseline | v1.0, tag `v1.0-frozen` = commit `7886867` (`em_macro/systematic.py` SHA-256 `1eb4cf6b…50be66`, `results/systematic/fit/frozen_design.json` SHA-256 `f0cce4c9…983858`). v1.0 stays the live baseline; no v1.0 file is modified. |
| written | 2026-11-03, before any T01 code was written or run. Committed on its own before any T01 backtest. |
| spec | `docs/research/algorithm_spec_2026-11.md` §0.3 (four-stage test and pass rule), §0.4 (honest reporting), §2 (trend), §13 (pre-registration, trial ledger) |

## 1. Hypothesis and evidence (spec §0.3(a))

**Hypothesis.** Replacing v1.0's cross-sectional trend signal with a separate time-series trend (TSMOM) sleeve
improves the strategy.

**Published evidence (spec §2.1).**
- Moskowitz, Ooi and Pedersen (2012, JFE): time-series momentum significant in all 58 futures, 1985–2009 (IS).
- Hurst, Ooi and Pedersen (AQR 2014/2017): a century of trend, 1880–2013, Sharpe 0.77 net of estimated costs
  (out of sample backwards in time).
- Asness, Moskowitz and Pedersen (2013): cross-sectional FX momentum Sharpe 0.32 (10 currencies, 1979–2011);
  cross-sectional bond momentum 0.06–0.17, "not statistically reliable".
- Baz, Granger, Harvey, Le Roux and Rattray (2015): momentum "works well in time series, but poorly in the cross
  section" (87 instruments, 1990–2015).

**Own diagnostics** (`results/diagnostics_v1.md`, Step 1): the cross-sectional trend signal's Shapley contribution
was −6.50% a year in 2005–2019 and −0.10% a year in 2020-01 to 2026-09.

**Disclosure of what is already known.** The diagnostics already report the 2020-01..2026-09 mean net return of
v1.0 run with carry and value only (the "carry+value" Shapley subset: 6.93% a year, against 6.25% for v1.0). That
is the core sleeve of T01 standing alone. The trend sleeve, the 80/20 combination and every T01 statistic below
have not been computed. The spec (§2.2) warns that dropping trend because of 2020–2026 would be in-sample
selection; T01 keeps a trend sleeve, redefined from the published evidence, and its parameters are the spec's.

## 2. Specification (fixed; no parameter is chosen from any backtest result)

All machinery not mentioned here is v1.0's, imported from the frozen `em_macro/systematic.py` without changes
(inputs, returns, execution lags, costs, the vol rule and the no-trade band). New code goes in new modules only.

### 2.1 Instruments, returns, timing

- **Instruments:** v1.0's 23 — 10 currencies (BRL MXN ZAR TRY IDR PLN GBP COP CLP EUR) and 13 bond positions
  (BR10Y MX10Y ZA10Y TR10Y ID10Y CO10Y CL10Y, FR-DE IT-DE ES-DE GB-DE PL-DE, DE10Y).
- **Returns:** v1.0's monthly excess returns from `systematic.build_inputs()` (FX forward-implied excess return;
  bonds from monthly-average yields).
- **Timing:** v1.0's. Weights decided at the end of month t earn month t+1 for currencies and t+2 for bonds.

### 2.2 Core sleeve (carry + value)

Identical to v1.0 except that the composite is the equal-weight mean of the **carry and value** z-scores only
(trend removed). Same cross-sectional z-scores per book, long top third / short bottom third of each book,
inverse 36-month volatility sizing, each book scaled to 10% (trailing 36-month pro-forma), books mixed 50/50, total
rescaled to 10%. These are v1.0's `book_weights` and the scaling steps of v1.0's `run`. The core sleeve's target
weights are taken **after** v1.0's 10% total rescaling and **before** the leverage cap and the no-trade band, which
are applied once to the combined book (§2.4).

### 2.3 Trend sleeve (spec §2.2 TSMOM blend)

For each instrument i and decision month t:

```
TSMOM_k = clip( sum of the last k monthly excess returns (months t-k+1..t) / (sigma_i,t * sqrt(k/12)), -2, 2 ) / 2
TREND   = mean over k in {1, 3, 6, 12} of TSMOM_k          (fixed equal weights; all four k required)
w_raw_i = TREND_i * 0.10 / sigma_i,t / n_active,t
```

- `sigma_i,t` is an annualised EWMA volatility with a **centre of mass of 60 trading days**.
  - **Implementation note, fixed in advance:** daily prices exist for only 14 of the 23 instruments, and v1.0's
    bond returns are built from monthly-average yields, so a daily EWMA would measure a different return series
    from the one traded.
  - σ is therefore computed on each instrument's own monthly excess-return series, with the 60-trading-day centre
    of mass converted to months at 21 trading days a month: com = 60/21 = 2.857 months (decay λ = com/(1+com) =
    0.7407).
  - It is pandas `ewm(com=60/21, min_periods=12).std()`, the demeaned, bias-corrected EWMA standard deviation,
    annualised by √12. It uses returns up to and including month t.
- An instrument is **active** at t when TREND and σ are both available (at least 12 monthly returns), with σ > 0.
  `n_active,t` is the number of active instruments across all 23. Inactive instruments get weight 0.
- **Sleeve target vol 10%:** the raw sleeve is scaled to 10% ex-ante volatility with v1.0's rule (trailing
  36-month pro-forma standard deviation of the current weights, at least 12 months). The 0.10 in `w_raw` is
  therefore immaterial for scale; it fixes only the relative positions.
- No lookback, speed or weight is selected. The four horizons and their equal weights are the spec's.

### 2.4 Combination, scaling, leverage, band, costs

```
W_core  = core sleeve at 10% (§2.2)          W_trend = trend sleeve at 10% (§2.3)
W_mix   = 0.80 * W_core + 0.20 * W_trend      (risk budget fixed in advance; spec assumption, not tuned)
W_tot   = W_mix * 0.10 / pro-forma vol(W_mix)  (v1.0 rule: trailing 36 months, min 12)
W_cap   = W_tot * min(1, 6 / gross(W_tot))     (v1.0's 6x gross-leverage cap)
W_held  = v1.0 25% no-trade band applied to W_cap, per instrument (net of both sleeves)
```

- **P&L and costs:** v1.0's per-instrument cost model, charged on |ΔW_held| in the month the new weight starts
  earning: 0.1% of notional, 0.3% for TR, ID, CO and CL, and twice for spread trades.
- **Before the trend sleeve is active:** before its first valid position, W_trend = 0, so W_tot = the core sleeve
  rescaled to 10%.
- **Stand-alone sleeves:** the trend sleeve and the core sleeve are also run on their own through the same final
  steps (10% rescale, 6x cap, band, costs), for reporting and criterion (5).

### 2.5 Cost sensitivity

Every run is repeated at **2x costs**: each instrument's cost per unit traded doubled, for both v1.0 and T01. The
pass rule is decided at **1x costs**, v1.0's cost model. The 2x results are reported, not decisive.

## 3. Samples and the holdout split

**Periods.**
- **Test (decisive):** 2020-01 to 2026-09 (81 months).
- **Context only:** 2005–2019, from the first live month to 2019-12. It is reported as in-sample, because v1.0 was
  designed on it, and **cannot affect the decision**.
- **Walk-forward:** T01 estimates no parameters (every number above is fixed), so the spec's year-by-year
  walk-forward (§0.3(b)) is identical to one causal run. All volatility estimates are trailing. Results are
  reported for each year 2020–2026 (2026 = January to September) and pooled.

**Holdout split (spec §0.3(c)).** Fixed now, before any T01 result exists.
- **Units:** the 23 instruments are grouped into 14 country units. Each unit holds its currency, its bond or
  spread, or both. `EUR` is its own unit, "euro area"; `DE10Y` belongs to Germany.
- **Strata:** units are stratified by region and developed/emerging: EM Latin America (BR MX CO CL); EM Europe,
  Middle East and Africa (ZA TR PL); EM Asia (ID); DM Europe (GB FR IT ES DE, euro area).
- **Procedure:** `numpy.random.default_rng(20261103)`, **seed 20261103**. Strata are taken in the order above;
  within each stratum the sorted units are shuffled, then dealt one by one to the half with fewer units, with a
  coin flip from the same generator when the halves are level.
- **Code:** `em_macro/holdout.py`, committed with the ledger entry right after this document.

| half | units | currencies | bonds |
|---|---|---|---|
| A | MX, CL, PL, ID, ES, DE, euro area | MXN CLP PLN IDR EUR | MX10Y CL10Y PL-DE ID10Y ES-DE DE10Y |
| **B (holdout)** | BR, CO, ZA, TR, GB, FR, IT | BRL COP ZAR TRY GBP | BR10Y CO10Y ZA10Y TR10Y GB-DE FR-DE IT-DE |

**How the holdout is run.**
- v1.0 (frozen code) and T01 are each run on the half-B universe as a stand-alone strategy. z-scores, thirds,
  n_active and all scaling are computed within half B only, by passing the half-B subset of v1.0's inputs; no
  v1.0 code is changed.
- T01 was "developed" on half A only in the sense that it was specified without looking at any result; nothing
  was fitted.
- The decisive holdout window is **2020-01..2026-09**. Half B over 2005–2019 and half A are reported as context.
- **Reason for the window:** the spec's table lists the holdout as 2005–2026, but this pre-registration's rule is
  that 2005–2019 cannot affect the decision.

## 4. Pass rule (spec §0.3; all five must hold, at 1x costs)

Notation:
- **Returns:** monthly net returns over 2020-01..2026-09 (81 months).
- **SR:** mean/std × √12, sample std (ddof 1), as v1.0's `stats`.
- **MaxDD:** maximum drawdown of the compounded monthly net return index.
- **ES(97.5%):** historical expected shortfall of monthly net returns (Acerbi-Tasche), with α = 0.025 and
  m = αT = 2.025: ES = −(1/m)·[r(1) + r(2) + (m − 2)·r(3)], where r(1) ≤ r(2) ≤ … are the sorted returns.
- **Baseline:** v1.0 = frozen `systematic.run(inp, ["carry","trend","value"])` on the same inputs.

| # | criterion | passes if |
|---|---|---|
| 1 | Walk-forward 2020–2026 vs v1.0, 6-month block bootstrap | ΔSR = SR(T01) − SR(v1.0) > 0 **and** one-sided p < 0.10. Bootstrap: paired circular block bootstrap of the 81 (T01, v1.0) monthly return pairs, block length 6, B = 10,000, `numpy.random.default_rng(20261103)`. p = (1 + #{b : ΔSR*_b − ΔSR ≥ ΔSR}) / (B + 1), i.e. the bootstrap distribution centred on the null ΔSR = 0. |
| 2 | Holdout, half B, 2020-01..2026-09 | ΔSR(half B) > 0 **and** \|MaxDD(T01, half B)\| ≤ \|MaxDD(v1.0, half B)\| |
| 3 | Tail risk, 2020-01..2026-09 | \|MaxDD(T01)\| ≤ 1.10 × \|MaxDD(v1.0)\| **and** ES97.5(T01) ≤ 1.10 × ES97.5(v1.0) (ES as a positive loss) |
| 4 | Deflated Sharpe, N incremented by one | DSR(T01; N = 8) ≥ DSR(v1.0; N = 7) (details below) |
| 5 | Trend-specific (spec §2.2) | corr(trend sleeve, carry sleeve) < 0 over carry's worst 10% of months, 2020-01..2026-09 (details below) |

**Criterion 4 details.**
- DSR = PSR against SR0 (spec §0.2(c)), via `em_macro/mtstats.py`. Inputs: monthly SR, T = 81, and each
  strategy's own sample skewness and raw kurtosis (pandas skew, kurt + 3) over 2020-01..2026-09.
- **Decisive null:** noise-only, trial-Sharpe SD = 1/√(T−1) per month.
- **N convention:** the spec's: v1.0 at N = 7, T01 at N = 8.
- **Reported, not decisive:** the dispersed-trials null (SD 0.20 annualised) and the ledger convention
  (N = 10 → 11).
- v1.0's DSR is recomputed from its realised SR (0.654), not the rounded 0.65.

**Criterion 5 details.**
- **Carry sleeve:** v1.0's frozen carry-only strategy, `systematic.run(inp, ["carry"])`, net returns.
- **Trend sleeve:** the stand-alone T01 trend sleeve (§2.4), net returns.
- **Carry's worst 10% of months:** the round(0.10 × 81) = 8 months with the lowest carry-sleeve net return in
  2020-01..2026-09.
- **Statistic:** the Pearson correlation of the two series over those 8 months must be < 0.
- **Context only:** the trend sleeve's mean return in those months, the overall correlation, and the same
  statistics over 2005–2019 and 2006–2026.

**Decision.**
- T01 **passes only if all five criteria hold**. Any failure means T01 is not adopted, and v1.0 stays live
  unchanged.
- No criterion, threshold, parameter or sample may be changed after results are seen. Any variant run after
  this (other risk budgets, lookbacks, σ definitions) is a new trial and gets a new ledger row.

## 5. Reporting (spec §0.4)

`results/T01_ts_trend.md` will report:
- the pass/fail table, criterion by criterion;
- annual returns of v1.0 and T01 for 2020–2026, side by side;
- for both strategies: Sharpe, return, volatility, MaxDD, ES(97.5%) and turnover, over 2020-01..2026-09 (test),
  2005–2019 (in-sample context) and half B (holdout), at 1x and 2x costs;
- the trend sleeve's own performance, and its correlation with carry overall and in carry's worst months;
- the deflated-Sharpe update.

It will also report the core sleeve alone (carry + value, no trend), labelled as a diagnostic that cannot be
adopted: choosing it after seeing results would be in-sample selection.

Rules for the report:
- v1.0's numbers stay labelled "OOS for v1.0 only".
- T01's numbers are reported separately and never merged with v1.0's.
- No recommendation about adopting T01 beyond the mechanical pass/fail.

**Reproduction check.** v1.0's own results must reproduce unchanged from the frozen code. Before T01 is run, the
frozen `systematic.evaluate` on the current inputs is compared with the committed
`results/systematic/test/performance_2020_on.csv`. If re-downloaded inputs (FRED, Yahoo, BIS and others, which
are not in git) make it differ, the difference is reported. The T01-vs-v1.0 comparison is then made like-for-like
on the same inputs.

**Ledger.** `trials.csv` gets the T01 row (ledger id T12, new trial group `G11_ts_trend_sleeve`) before the run,
marked pending. It is updated with the outcome after the run.
