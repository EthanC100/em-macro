# Pre-registration — trials T16–T19: risk-side batch against frozen v1.0

| item | value |
|---|---|
| trials | **T16** carry-crash filter; **T17** factor-capped sizing; **T18** turnover reduction; **T19** volatility forecasting for sizing. Ledger ids `T16`–`T19` in `trials.csv` (free ids; the last ledger row is T15), trial groups `G15_carry_crash_filter`, `G16_factor_capped_sizing`, `G17_turnover_reduction`, `G18_vol_forecast_sizing`. |
| family | The four trials are **one family** for multiple testing (§5). Each is a single change to v1.0, tested separately against v1.0. **No combination is tested in this session.** |
| branch | `trial/T16-T19-risk-batch` |
| baseline | v1.0, tag `v1.0-frozen` = commit `7886867` (`em_macro/systematic.py` SHA-256 `1eb4cf6b…50be66`, `results/systematic/fit/frozen_design.json` SHA-256 `f0cce4c9…983858`). v1.0 stays the live baseline; **no v1.0 file is modified**. New code goes in new modules only (`em_macro/t16_crash.py`, `t17_factorcap.py`, `t18_rebal.py`, `t19_vol.py`, `t1619.py`, `t1619_report.py`). |
| written | 2026-11-04, before any T16–T19 code was written or run. Committed on its own before any T16–T19 computation. The ledger rows follow in a second commit. |
| spec | `docs/research/algorithm_spec_2026-11.md` §0.3 (four-stage test, pass rule; risk-only rule), §0.4 (honest reporting), §6.2 (crash filter), §7 (portfolio construction, factor caps, volatility targeting and the volatility floor), §8 (rebalancing), §13 (pre-registration, ledger), §17.2 Builds 4 and 5. Diagnostics: `results/diagnostics_v1.md`, `results/cost_audit_v1.md`. |
| what has been seen | v1.0's committed results and the diagnostics listed above (attribution, risk audit, cost audit, turnover decomposition), and the T01 and T02 reports. **No T16–T19 return, weight, crash probability, factor share, band decision or volatility estimate has been computed.** |

v1.0's figures stay labelled "OOS for v1.0 only". Each trial's figures are reported separately and never merged with
v1.0's track record (spec §0.4).

## 1. Hypotheses and evidence (spec §0.3(a))

These are **risk trials**. The spec (§0.3, risk-only changes) makes ES or drawdown the primary metric, provided the
Sharpe ratio falls by no more than 0.05. The hypotheses are therefore "risk reduction without giving up return".

| trial | hypothesis | published evidence recorded (sample, asset class) | spec prior |
|---|---|---|---|
| T16 carry-crash filter | Scaling down long currency positions when a pooled, point-in-time logistic crash model gives a high crash probability lowers v1.0's maximum drawdown or ES(97.5%) by at least 10% without lowering its Sharpe by more than 0.05. | Brunnermeier, Nagel and Pedersen (2008, NBER Macro Annual; 1986–2006, FX): carry crashes, risk reversals and past carry gains predict crash risk. Jordà and Taylor (2012, JIE; 1986–2008, FX, IS and OOS): fundamentals-augmented carry reduces crash losses. Menkhoff, Sarno, Schmeling and Schrimpf (2012, JF; 1983–2009, 48 currencies): global FX volatility innovations explain carry returns. Della Corte, Riddiough and Sarno (2016, RFS; 1983–2014): debtor currencies fall in bad times. | §17.1 #4: ΔSR 0 to +0.1, ES −20 to −30%, evidence B. |
| T17 factor-capped sizing | Capping the share of ex-ante portfolio risk coming from the USD factor (≤ 25%) and the EM FX factor (≤ 40%), then re-scaling to the 10% target, lowers v1.0's drawdown or ES by at least 10% without lowering its Sharpe by more than 0.05. | Daniel, Hodrick and Lu (2017, CFR; G10): the dollar exposure of carry is a separate, time-varying bet. Lustig, Roussanov and Verdelhan (2014, JFE; 1983–2010): the dollar factor. Menkhoff et al. (2012) and BIS Bulletin 90 (2024): EM high-yielders share one risk factor. Ledoit and Wolf (2004) shrinkage. Own risk audit: the USD factor share of version-A risk reached 75.0% in 2026-01 and the combined USD+EM share 74.8% in 2013-12 (`results/diagnostics_v1.md`). | §17.1 #5: ΔSR +0.05 to +0.15, drawdown −15%, evidence B. |
| T18 turnover reduction | Replacing v1.0's 25% relative no-trade band by the spec's risk-unit band and partial rebalancing cuts turnover by at least 25% and lowers drawdown or ES by at least 10% without lowering Sharpe by more than 0.05. | Spec §8 rebalancing rules [J]; Melvin, Pan and Wikstrom (2020, CESifo WP 8143; FX 2014–18): trade size and rebalancing frequency drive FX strategy net returns; Ilmanen et al. (2021): costs matter for factor OOS performance. Own cost audit: turnover 19.09×/yr, 91% from entries and exits, costs 3.73%/yr = 37% of gross P&L. | §17.1 #14 (costs; honest). The spec gives no ΔSR for rebalancing. |
| T19 volatility forecasting | Replacing v1.0's 36-month trailing standard deviation by the spec's EWMA estimate with a long-run floor, σ_est = max(σ_EWMA60, 0.8·σ_EWMA250), at every point where v1.0 uses its volatility estimate, lowers drawdown or ES by at least 10% without lowering Sharpe by more than 0.05. | Harvey, Hoyle, Korgaonkar, Rattray, Sargaison and Van Hemert (2018, JPM; 60+ assets from 1926): volatility targeting has a negligible Sharpe effect in FX and bonds but fewer extreme returns. Cederburg, O'Doherty, Wang and Yan (2020, JFE): volatility-managed portfolios do not systematically outperform. Moskowitz, Ooi and Pedersen (2012, JFE): EWMA volatility with a 60-day centre of mass. Spec §7 [J]: floor the estimate because carry crashes follow calm periods. | §17.1 #13: ΔSR 0, thinner tails, evidence B. |

## 2. Common framework (fixed)

All machinery not mentioned in §3 is v1.0's, imported from the frozen `em_macro/systematic.py` without changes:
inputs (`build_inputs`), returns, signals, thirds selection, inverse-vol sizing, 10% book and total targets, 50/50
book mix, 6× gross-leverage cap, 25% no-trade band, execution lags (FX t+1, bonds t+2) and the per-instrument cost
model. Each trial changes exactly one thing, named in §3.

- **Instruments:** v1.0's 23 (10 currencies BRL MXN ZAR TRY IDR PLN GBP COP CLP EUR; 13 bond positions BR10Y
  MX10Y ZA10Y TR10Y ID10Y CO10Y CL10Y, FR-DE IT-DE ES-DE GB-DE PL-DE, DE10Y).
- **v1.0 baseline:** frozen `systematic.run(inp, ["carry", "trend", "value"])` on the same inputs, same universe and
  same costs as the trial being compared.
- **Periods:** **test (decisive) 2020-01..2026-09** (81 months). **Context only:** 2005–2019 (v1.0's design
  sample; cannot affect any decision). Each year 2020–2026 (2026 = January–September) is reported separately.
- **Walk-forward (spec §0.3(b)):** T17, T18 and T19 estimate no parameters from returns (every number is fixed
  below), so the year-by-year walk-forward is identical to one causal run. T16 estimates a logistic model and is run
  as a true walk-forward (§3.1).
- **Holdout (spec §0.3(c)):** T01's split, `em_macro/holdout.py`, seed 20261103. Half A = MX, CL, PL, ID, ES, DE,
  euro area (MXN CLP PLN IDR EUR; MX10Y CL10Y PL-DE ID10Y ES-DE DE10Y). **Half B (holdout) = BR, CO, ZA, TR, GB,
  FR, IT** (BRL COP ZAR TRY GBP; BR10Y CO10Y ZA10Y TR10Y GB-DE FR-DE IT-DE). v1.0 and each trial are run on the
  half-B universe as a stand-alone strategy (z-scores, thirds and scaling within half B, via `tstrend.subset`; no
  v1.0 code changed), decisive window 2020-01..2026-09. Half A and half B over 2005–2019 are context.
- **Costs:** 1x (v1.0's cost model) is decisive. Every run is repeated at **2x costs** (`tstrend.with_costs`), for
  v1.0 and the trial alike; reported, not decisive.
- **Data:** v1.0's input snapshots (`data/processed/daily_panel.csv`, `country_month_panel.csv`,
  `risk_model_input.csv`, working-tree versions) plus the cached raw downloads (FRED, Yahoo, BIS, BanRep, BCCh) that
  `build_inputs` reads. The extra series each trial needs are listed in §3. The raw downloads used are archived
  under `data/kept/T16-T19/` per the retention rule (`docs/raw_data_archive.md`), one archive for the four trials.
- **Reproduction check first:** before any trial runs, `python -m em_macro.verify_v1` must report that v1.0's two
  committed tables reproduce byte for byte. If it does not, nothing is run.
- **One run each.** Each trial is run once at 1x and once at 2x, on each universe (all, half B, half A). No variant,
  re-parameterisation or re-run after seeing results. If running a trial would require changing a parameter fixed
  here, the trial is marked "not run" with the reason.

### 2.1 Statistics

Monthly net returns over the window. **SR** = mean/SD × √12 (SD with ddof 1). **Return** compounded. **Vol** =
SD × √12. **MaxDD** = maximum drawdown of the compounded monthly index. **ES(97.5%)** = historical expected
shortfall of monthly net returns (Acerbi-Tasche, α = 0.025; T01's `t01.expected_shortfall`), as a positive loss.
**Turnover** = one-way notional traded per year in multiples of capital, dated as v1.0's costs
(`t01.turnover`). All as in T01 and T02 (`em_macro/t01.py`), so results are comparable across trials.

**Risk improvement of at least 10%** (used in criteria 1 and 2): |MaxDD(trial)| ≤ 0.90 × |MaxDD(v1.0)| **or**
ES97.5(trial) ≤ 0.90 × ES97.5(v1.0), on the same universe, costs and window. Both metrics are reported; the metric
that meets the 10% bar in the full universe is the one that must meet it again in half B ("the same risk
improvement").

**Sharpe non-inferiority, margin 0.05 (criterion 1).** ΔSR = SR(trial) − SR(v1.0) over 2020-01..2026-09, all 23
instruments, 1x costs. The hypothesis tested is H1: ΔSR > −0.05 against H0: ΔSR ≤ −0.05. Paired circular block
bootstrap of the 81 (trial, v1.0) monthly return pairs, block length 6 months, B = 10,000,
`numpy.random.default_rng(20261103)` (T01's `bootstrap_delta_sharpe` resampling). One-sided p-value from the
bootstrap distribution centred on the null boundary:

```
p_raw = (1 + #{b : ΔSR*_b − ΔSR_hat ≥ ΔSR_hat + 0.05}) / (B + 1)
```

The criterion requires ΔSR_hat ≥ −0.05 **and** the Holm-adjusted p (§5) < 0.10 (the spec's one-sided level).
The bootstrap mean, SD and 5%–95% range of ΔSR* are reported.

**Deflated Sharpe (criterion 3).** PSR and DSR as in spec §0.2(c) via `em_macro/mtstats.py`, from each strategy's
realised 2020-01..2026-09 monthly SR, sample skewness and raw kurtosis, T = 81. Decisive null: noise-only,
trial-Sharpe SD = 1/√(T−1) per month. **N convention (decisive):** the spec's count, incremented for the whole
family at once: v1.0 at N = 7; T01 and T02 took it to 9; the four trials take it to **N = 13**, and every trial is
evaluated at N = 13 against v1.0 at N = 7 (DSR 0.619 in the T01 and T02 reports; recomputed from v1.0's realised
returns on this run's inputs). Reported, not decisive: the dispersed-trials null (SD 0.20 annualised) and the ledger
convention (14 trial groups now, 18 after this family: v1.0 at N = 14, each trial at N = 18).

**Five worst months.** v1.0's five lowest monthly net returns in 2020-01..2026-09 at 1x costs; each trial's net
return in those months is reported next to v1.0's.

## 3. Specifications (fixed; no parameter is chosen from any backtest result)

Notation: W_tot = v1.0's target weights after the 10% total rescaling and before the 6× cap and the band (T01's
`tstrend.core_targets(inp, ["carry","trend","value"])`); W_cap = after the 6× cap; W_held = after the band.
σ_{i,t} = v1.0's trailing 36-month annualised standard deviation of instrument i's monthly excess returns (min 12).

### 3.1 T16 — carry-crash filter (spec §6.2, Build 4)

**The one change.** Each long currency position is multiplied by a scale in [0, 1] derived from a pooled logistic
crash probability. Nothing else changes.

**Crash label [A, spec central value].** Horizon **h = 3 months** (the central value of the spec's {1, 3, 6}).
For currency i and decision month t:

```
CR_{i,t} = 1 if min over τ in {1,2,3} of [ Π_{s=t+1..t+τ} (1 + r_{i,s}) − 1 ] ≤ −2.0 · σ_{i,t} · sqrt(3/12), else 0
```

r = v1.0's monthly FX excess returns (`inp["fx"]["ret"]`), σ_{i,t} = v1.0's 36-month vol. The label needs all
three forward months and σ_{i,t}; otherwise the observation is not labelled.

**Features** (decision month t; all from data available at the end of month t; the spec's list with the
substitutions and omissions below, every one decided here):

| # | spec feature | used here | source |
|---|---|---|---|
| 1 | carry z-score | v1.0's cross-sectional FX carry z-score at t (`systematic.signals(inp["fx"])["carry"]`) | v1.0 inputs |
| 2 | VAL_reer | **proxy:** v1.0's FX value signal (log real exchange rate against its 5-year mean, CPI lagged one month; + = cheap), raw, not z-scored; BIS REER is not among the inputs | v1.0 inputs |
| 3 | current account / GDP | WEO current-account balance, % of GDP, **for calendar year Y−1 used throughout year Y** (one-year lag to limit look-ahead). Single latest vintage (October 2026 WEO, as in `country_month_panel.csv`), so the values are revised, not first-release: a known look-ahead risk, flagged. EUR: unweighted mean of DE, FR, IT, ES | `country_month_panel.csv` `current_account_gdp` shifted 12 months |
| 4 | reserves / short-term debt | **proxy:** reserves in months of imports (World Bank WDI, in the panel), for year Y−1 used throughout year Y; same vintage caveat. EUR: mean of DE, FR, IT, ES | `country_month_panel.csv` `reserves_months_imports` shifted 12 months |
| 5 | NFA / GDP | **omitted**: no NFA series is among the inputs and no series in the panel measures it (government net debt is not NFA) | — |
| 6 | log(σ_1m / σ_12m) | log of the ratio of the standard deviation of daily log changes of the spot rate (local per USD) over the last 21 business days to that over the last 252 business days, at the last business day of month t (at least 15 and 200 observations) | spot sources of `overlay.daily_returns` (the same spot series v1.0 uses) |
| 7 | 3-month changes in VIX, the dollar, the US 2-year yield | VIX(t) − VIX(t−3) (month-end levels); log DXY(t) − log DXY(t−3); DGS2(t) − DGS2(t−3), percentage points | `daily_panel.csv` VIX, DXY; FRED DGS2 |
| 8 | own 12-month carry return | Π_{s=t−11..t}(1 + r_{i,s}) − 1 (all 12 months required) | v1.0 inputs |
| 9 | CFTC positioning z-score with missing indicator | **omitted**: no CFTC data among the inputs for any instrument, so the missing indicator would equal 1 for every observation and be absorbed by the intercept | — |
| 10 | election within h months | 1 if `data/events/elections.csv` lists a national election or referendum for the currency's country with `vote_date` in (last day of month t, last day of month t+3], else 0. EUR: DE, FR, IT or ES. The calendar is as recorded now; a snap election called at short notice is a small look-ahead, flagged | `data/events/elections.csv` |

Missing feature values (after the lags) are set to the training-window mean (0 in standardised units), in training
and in prediction; the number of imputed cells is reported.

**Model.** Pooled logistic regression with an L2 penalty, no country fixed effects (spec):
minimise Σ log-loss + ||β||² / (2C) over the training rows (intercept unpenalised), features standardised with the
training window's mean and SD (`std(te[X], ref=tr)` in the spec's code). Solver: L-BFGS-B (`scipy.optimize`),
deterministic. **C** is chosen inside each training window by **time-blocked cross-validation**: the training months
are cut into 5 contiguous blocks of equal length; for each C in {0.01, 0.1, 1, 10, 100} the model is fitted on four
blocks (purging training rows whose decision month lies within 3 months before the held-out block's first month or
within 3 months after its last month, so no label window overlaps the held-out block) and scored by the mean
out-of-fold log-likelihood; the C with the highest mean is kept; ties go to C = 1.0 (the spec's default).

**Walk-forward (spec §6.2 validation, §0.3(b)).** For each year Y from 2020 to 2026: training rows are all labelled
(i, t) with t ≤ September(Y−1), so every label window ends by December(Y−1) (purge); the model (and C) is fitted on
them and predicts p_{i,t} for every month t of year Y with parameters frozen. The expanding window starts at the
first month with a label (2005 data; the spec's "from 1995" is not possible with inputs starting in 2005).
Context only, 2005–2019: the same walk-forward for years 2010–2019 (first training window: labels with
t ≤ 2009-09); before 2010 the scale is 1 (no filter).

**Decision rule [A, spec].** p_base = the crash frequency in the training rows.

```
scale_{i,t} = clip(1 − (p_{i,t} − p_base) / (2 · p_base), 0, 1)        applied to long currency positions only
```

The scale multiplies W_tot,i,t for currencies with W_tot,i,t > 0 (the FX book's longs: the carry-exposed side);
short currency positions and all bond positions are unchanged. It is applied **after** v1.0's 10% total rescaling
and **before** the 6× cap and the 25% band, so the vol targeting does not undo it. A currency-month without a
prediction (missing features beyond imputation, or before 2010) has scale 1.

**Holdout.** For the half-B run the model is trained (walk-forward, same procedure, same C grid) on the **half-A
currencies only** (MXN CLP PLN IDR EUR) and applied to the half-B currencies (BRL COP ZAR TRY GBP) inside the half-B
stand-alone strategy. For the half-A context run it is trained on half A and applied to half A. For the all-instrument
run it is trained on all 10 currencies.

**Diagnostics reported (not pass criteria; the spec's own filter checks):** walk-forward AUC and Brier skill
(against p_base) of the 2020–2026 pooled predictions, for the all-currency model and for the half-A model on half
B; the crash base rate; the chosen C per year; the share of currency-months scaled below 1 and the mean scale.

### 3.2 T17 — factor-capped sizing (spec §7 caps, Build 5)

**The one change.** v1.0's target weights are adjusted, at each decision month, so that the USD factor's share of
ex-ante portfolio risk is at most **25%** and the EM FX factor's share at most **40%** (the spec's [A] caps), by the
minimum-distance adjustment the spec prescribes, and then re-scaled to the 10% target as in spec Build 5. The
spec's country (15%), LatAm (35%) and net-duration caps are **not** part of T17 (single change: the two factor caps).
Nothing else changes (thirds, inverse-vol sizing, book mix, 6× cap, band, costs).

**Risk measure (fixed).** The spec's formula, as implemented in the risk audit's **version B** (full book):
share_f = β_f (Ωβ)_f / σ_p², β = B'w. At decision month t: R = the universe's monthly excess returns over the
trailing 60 months ending at t (NaN → 0; at least 36 months with any data, else no cap that month, scale = 1);
Σ = Ledoit-Wolf shrinkage of R towards a scaled identity (`diagnostics.ledoit_wolf`) × 12; factors over the same
window: USD = month-end log change of the dollar index (`daily_panel.csv` DXY), EM = equal-weight mean of the 8
EM currencies' monthly excess returns (BRL MXN ZAR TRY IDR PLN COP CLP, from `inp["fx"]["ret"]`, also for the
half-B and half-A runs); B = OLS betas (with intercept) of each instrument on the two factors; Ω = sample covariance
of the factors × 12; σ_p² = w'Σw. Version B is used because daily prices exist for only 14 of the 23 instruments
(the spec's 3-day version A cannot size the whole book).

**Adjustment.** w0 = W_tot,t (v1.0's target after the 10% total rescaling). If share_USD(w0) ≤ 0.25 and
share_EM(w0) ≤ 0.40, w = w0. Otherwise

```
w = argmin ||w − w0||²   subject to   share_USD(w) ≤ 0.25,  share_EM(w) ≤ 0.40
```

solved by SLSQP (`scipy.optimize.minimize`, start w0, ftol 1e-12, maxiter 500). A solution is accepted if both
shares are within 1e-6 of their caps. If SLSQP returns no acceptable point, the fallback is the smallest λ on the
grid {0.001, 0.002, …, 1} for which w(λ) = w0 − λ·P w0 is acceptable, where P projects onto the span of the
breached factors' beta vectors (λ = 1 removes the exposure, share 0). The number of months adjusted, the number
using the fallback and the pre/post shares are reported.

**Re-scaling and the rest.** w is re-scaled to the 10% target with v1.0's own rule (trailing 36-month pro-forma
standard deviation of the adjusted weights, min 12 months; T01's `tstrend.scale_to_vol`), as spec Build 5
re-scales after enforcing caps; then v1.0's 6× cap, 25% band and costs. Risk shares are scale-invariant, so the
re-scaling keeps the caps satisfied.

**Holdout.** The half-B run computes Σ, B and the shares from the half-B instruments' returns, with the same global
factor series.

**Diagnostics reported:** the monthly USD and EM shares of v1.0 and T17 (version B), the months in which a cap bound,
and the average gross leverage.

### 3.3 T18 — turnover reduction (spec §8 rebalancing)

**The one change.** v1.0's 25% relative no-trade band (`_apply_band`) is replaced by the spec's two rebalancing
rules together, with the spec's values: a **no-trade band in risk units, 0.1 × the position's risk budget**, and
**partial rebalancing, w_new = w + 0.5 (w* − w)**. The targets w* are v1.0's W_cap (after the 10% rescaling and
the 6× cap), identical to v1.0's pre-band targets. Nothing else changes.

**Definitions.** σ_{i,t} = v1.0's 36-month vol. The **position's risk budget** at t is the risk v1.0 gives each
selected position of its book: b_{book,t} = mean over the book's instruments with W_cap,i,t ≠ 0 of
|W_cap,i,t| · σ_{i,t} (equal across a book's selected positions by construction, up to rounding). If a book has no
selected position at t, b_{book,t} is undefined and every position of that book trades to its target (zero).

**Rule, each instrument i and month t,** with w = the held weight after month t−1 (0 at the start):

```
gap   = W_cap,i,t − w
delta = 0.5 · gap                                           (partial rebalancing)
if |delta| · σ_{i,t} > 0.1 · b_{book,t}:   w_new = w + delta        (the trade clears the band)
elif W_cap,i,t == 0 and w != 0:            w_new = 0                (residual of an exited position: closed)
else:                                      w_new = w                (inside the band: no trade)
```

The band is applied to the proposed trade (the spec's "trade only if |Δw_i|·σ_i > 0.1 × budget"); the residual
rule closes a position whose target is zero once its remaining half-trades fall inside the band, so no dead
position is held without a signal. If σ_{i,t} is undefined for a held position, the trade is made. Costs are v1.0's,
on |w_new − w|, in the month the new weight starts earning.

**Turnover criterion (criterion 4):** T18's turnover over 2020-01..2026-09, all 23 instruments, 1x costs, must be
at most 0.75 × 19.09 = **14.32× capital a year** (v1.0's 19.09×/yr, `results/cost_audit_v1.md`, recomputed on this
run's inputs; the 25% is against the recomputed figure).

**Diagnostics reported:** turnover by year and by book, the share of trades suppressed by the band, the average
|held| / |target| ratio, and v1.0 run with no band (`run(..., band=0)`) as context for the band's own effect.

### 3.4 T19 — volatility forecasting for sizing (spec §7 volatility targeting)

**The one change.** v1.0's volatility estimate (trailing 36-month standard deviation × √12, min 12 months) is
replaced, at **every** point where v1.0 uses it, by the spec's floored EWMA:

```
σ_est = max( σ_EWMA(HL 60 days), 0.8 · σ_EWMA(HL 250 days) )
σ_EWMA(HL)_t = sqrt( 12 · EWM_mean(x²; halflife HL, adjust=True, min_periods=12)_t )     (zero-mean, spec §7 recursion)
```

x = the monthly return series in question. Half-lives in months: HL60 = 60/21 = 2.857, HL250 = 250/21 = 11.905
(21 trading days a month; T01's convention). The EWMA runs on monthly returns because daily prices exist for only
14 of the 23 instruments and v1.0's bond returns are built from monthly-average yields, so a daily estimator would
measure a different series from the one traded. Minimum 12 months, as v1.0's.

**Where it applies (all three places v1.0 uses `_vol` or the trailing pro-forma std):**
1. the instrument volatility σ_{i,t} in `book_weights` (inverse-vol sizing, and the "has a volatility" requirement
   for selection);
2. the book scaler: pv = σ_est of the book's pro-forma return series (hist @ raw, all months up to t, NaN → 0),
   target 10%;
3. the total scaler: pv = σ_est of the combined pro-forma series (allR up to t @ allW_t), target 10%.

Everything else is v1.0's: signals, thirds, 50/50 mix, 6× cap, 25% band, costs. The 0.8 floor factor, the two
half-lives and the 10% target are the spec's values; nothing is chosen.

**Diagnostics reported:** the time series of the total scaler under v1.0 and T19, the realised volatility by year,
and the share of months in which the floor (0.8·σ_EWMA250) binds.

## 4. Pass rule (each trial; 1x costs decisive; 2x reported)

| # | criterion | passes if |
|---|---|---|
| 1 | 2020-01..2026-09, all 23 instruments: risk improvement and Sharpe non-inferiority | (\|MaxDD\| ≤ 0.90 × v1.0's **or** ES97.5 ≤ 0.90 × v1.0's) **and** ΔSR_hat ≥ −0.05 **and** Holm-adjusted bootstrap p (§2.1, §5) < 0.10 |
| 2 | holdout, half B, 2020-01..2026-09 | the same risk metric that met the 10% bar in criterion 1 meets it in half B (≤ 0.90 × v1.0's half-B value) **and** SR(trial, half B) ≥ SR(v1.0, half B) − 0.05 |
| 3 | deflated Sharpe, N incremented for the whole family | DSR(trial; N = 13, noise-only null) ≥ DSR(v1.0; N = 7) |
| 4 | T18 only: turnover | turnover(T18) ≤ 0.75 × turnover(v1.0), 2020-01..2026-09, all instruments, 1x |

A trial **passes only if every applicable criterion holds after the Holm correction**. Any failure means the trial
is not adopted and v1.0 stays live unchanged. 2005–2019 results, half A, the 2x-cost tables and the diagnostics
are context and cannot affect the decision. No criterion, threshold, parameter or sample may be changed after
results are seen; any variant run later is a new trial with a new ledger row.

## 5. Multiple testing: the family

The four trials are one family. Their four raw one-sided bootstrap p-values (criterion 1, Sharpe non-inferiority)
are adjusted by the **Holm (1979) step-down** procedure: order p_(1) ≤ … ≤ p_(4); p_adj,(i) = max_{j ≤ i}
min(1, (4 − j + 1) · p_(j)). Raw and adjusted p-values are both reported; criterion 1 uses the adjusted value. The
deflated Sharpe (criterion 3) counts the family as four new trials at once (N = 13). The 2x-cost p-values are
Holm-adjusted the same way for the 2x table.

## 6. Reporting (spec §0.4)

`results/T16-T19_risk_batch.md` will report: a pass/fail table per trial and criterion (1x decisive, 2x reported);
v1.0 and each trial side by side (Sharpe, return, volatility, MaxDD, ES97.5, turnover) for 2020-01..2026-09, by
year 2020–2026, for half B, and for 2005–2019 as context; behaviour in v1.0's five worst months; the raw and
Holm-adjusted p-values; the deflated-Sharpe update; each trial's diagnostics (§3); every decision taken under the
rules in the task (parameter choices, proxies, omissions); and a note on which passing trials, if any, could be
combined in a future pre-registered trial (not tested here). No editorialising about adoption beyond the mechanical
pass/fail. Tables and monthly returns go to `results/T16-T19/`, with `RUN.json` (run time, commit, SHA-256 of code,
pre-registration and inputs, the v1.0 reproduction check).

**Ledger.** `trials.csv` gets rows T16–T19 (groups G15–G18), marked pending, in the commit after this document,
changing no other row; they are updated with the outcomes after the run.

## 7. Decisions taken under the task's rules (listed again in the report)

1. **T16 horizon h = 3 months**: the spec gives h ∈ {1, 3, 6}; the central value is used.
2. **T16 features:** NFA/GDP and the CFTC z-score are omitted (no data among the inputs; no proxy measures the same
   thing); reserves/short-term debt is proxied by reserves in months of imports; VAL_reer by v1.0's RER value; the
   WEO current account is the latest vintage lagged one year (revised data; look-ahead risk flagged); the euro area's
   external features are the mean of DE, FR, IT, ES; the election feature comes from `data/events/elections.csv`.
3. **T16 penalty:** C by time-blocked CV over {0.01, 0.1, 1, 10, 100} with a 3-month purge; ties → C = 1.0 (spec
   default). Missing features imputed at the training mean.
4. **T16 walk-forward start:** expanding window from 2005 (inputs start then), decisive years 2020–2026; context
   years 2010–2019, no filter before 2010.
5. **T16 placement:** scale applied to long currency positions, after the 10% total rescaling, before the 6× cap and
   the band. Holdout model trained on half A, applied to half B.
6. **T17 risk measure:** version B (monthly, Ledoit-Wolf, 60 months, full book) rather than the spec's 3-day version
   A, because A covers only 14 of 23 instruments. Caps USD 25% and EM 40% (spec [A] values); country, LatAm and
   duration caps excluded as not part of the single change. SLSQP with a projection fallback. Re-scaled to 10% after
   the cap with v1.0's own rule (spec Build 5 order).
7. **T18 rules:** both of the spec's rules with its values (band 0.1 of the position's risk budget on the proposed
   trade; partial factor 0.5); the position's risk budget is the equal risk v1.0 gives each selected position of a
   book; residuals of exited positions are closed once inside the band.
8. **T19 estimator:** the spec's floor formula with half-lives 60 and 250 trading days converted to months at 21
   days a month, zero-mean EWMA of squared monthly returns, min 12 months; applied at all three points where v1.0
   uses its 36-month volatility.
9. **Sharpe criterion:** a non-inferiority test with margin 0.05 (H1: ΔSR > −0.05), one-sided block-bootstrap p,
   Holm-adjusted across the four trials, level 0.10 (the spec's); the point estimate must also be ≥ −0.05.
10. **Risk criterion:** "at least 10% better" = the trial's |MaxDD| or ES97.5 at most 0.90 × v1.0's; the same
    metric must hold in half B.
11. **DSR N:** spec convention 7 → 13 (7 + T01 + T02 + four), every trial compared with v1.0 at N = 7; ledger
    convention 14 → 18 reported as context.
12. **Costs at 2x:** the trial rules are applied identically with every cost doubled; reported only.
13. **Raw data:** one archive of the raw downloads used, under `data/kept/T16-T19/`, recorded for all four trials.
14. **Merge conflicts with `main`**, if any, are resolved by keeping both sides.
