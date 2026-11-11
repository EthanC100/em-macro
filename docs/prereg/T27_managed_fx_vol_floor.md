# Pre-registration — trial T27: volatility floor for managed currencies

| item | value |
|---|---|
| trial | **T27**, managed-currency volatility floor. Ledger id `T27` in `trials.csv` (free id; the last ledger row is T26), new trial group `G22_managed_fx_vol_floor`. It is a different idea from T19 (G18), which replaced the volatility estimator of every instrument; T27 floors the estimate of currencies under a managed IMF de facto regime only. |
| family | **One trial, one specification.** No variant is computed (§4). One confirmatory test; no Holm correction. The deflated Sharpe counts T27 as one new trial (§6). |
| branch | `claude/youthful-ptolemy-gkuorr` |
| baseline | v1.0, tag `v1.0-frozen` = commit `7886867` (`em_macro/systematic.py` SHA-256 `1eb4cf6b…50be66`, `results/systematic/fit/frozen_design.json` SHA-256 `f0cce4c9…983858`). v1.0 stays the live baseline; **no v1.0 or v1.1 file is modified**. New code goes in new modules only (`em_macro/t27_floor.py`, `em_macro/t27_report.py`). v1.1 is not tested with the floor. |
| written | 2026-11-11, approved by the owner in this session, before any T27 code was written or run and before any IMF classification was looked up. Committed on its own before any T27 computation. The ledger row follows in a second commit. |
| spec | `docs/research/algorithm_spec_2026-11.md` §0.3 (four-stage test; risk-only rule), §0.4 (honest reporting), §7 (volatility targeting and the volatility floor), §13 (pre-registration, ledger). |
| what has been seen | v1.0's committed results and diagnostics (`results/diagnostics_v1.md`, `results/cost_audit_v1.md`); the T01, T02, T16–T19, T20–T26 pre-registrations and their ledger rows. **No T27 return, weight, floored volatility or classification has been computed or looked up.** **Disclosure:** the idea was prompted by TRY's current managed path and its known devaluations of 2018 and 2021. 2021 lies inside the confirmatory window (2020-01..2026-09), so a pass is weaker evidence than a clean out-of-sample result. The report repeats this caveat next to the pass/fail table. |

v1.0's figures stay labelled "OOS for v1.0 only". T27's figures are reported separately and never merged with
v1.0's track record (spec §0.4).

## 1. Hypothesis and evidence (spec §0.3(a))

This is a **risk trial** (spec §0.3, risk-only changes): drawdown is the primary metric, provided the Sharpe ratio
falls by no more than 0.05.

**Hypothesis.** Flooring the volatility estimate of currencies under a managed IMF de facto regime (§3.2) at the
cross-sectional median volatility of v1.0's emerging-market currencies, then rescaling to the 10% target with
v1.0's own rule, **reduces drawdowns from sudden devaluations at little or no cost in Sharpe.**

**Mechanism.** Trailing realised volatility understates the risk of a managed currency, because the authorities
suppress day-to-day moves until the regime breaks. Inverse-volatility sizing then gives such a currency an oversized
weight just before the jump; the floor caps that weight.

**Published evidence** (sample and asset class to be checked against each paper and recorded in the report):
- Calvo and Reinhart (2002, QJE), "Fear of Floating": many declared floaters manage their exchange rates, so measured
  exchange-rate volatility is low relative to reserve and interest-rate volatility (39 countries, 1970–1999).
- Reinhart and Rogoff (2004, QJE); Ilzetzki, Reinhart and Rogoff (2019, QJE): de facto regimes differ from de jure
  regimes; managed regimes end in large discrete moves.
- Klein and Shambaugh (2008, JIE): pegs are fragile and many end within a few years.
- Brunnermeier, Nagel and Pedersen (2008, NBER Macro Annual; 1986–2006, FX): carry returns are negatively skewed and
  crash after calm periods.
- Habermeier, Kokenyne, Veyrune and Anderson (2009, IMF WP/09/211): the 2009 revision of the IMF de facto
  classification, which defines the categories used here.
- Spec §7 [J]: floor volatility estimates, because carry crashes follow calm periods.

**Prior.** A small effect, concentrated in the few currency-months in which the floor binds.

## 2. Common framework (fixed)

All machinery not named in §3 is v1.0's, imported from the frozen `em_macro/systematic.py` without changes: inputs
(`build_inputs`), returns, signals, thirds selection, the 36-month volatility, the 10% book and total targets, the
50/50 book mix, the 6× gross-leverage cap, the 25% no-trade band, execution lags (FX t+1, bonds t+2) and the
per-instrument cost model.

- **Instruments:** v1.0's 23 (10 currencies BRL MXN ZAR TRY IDR PLN GBP COP CLP EUR; 13 bond positions BR10Y MX10Y
  ZA10Y TR10Y ID10Y CO10Y CL10Y, FR-DE IT-DE ES-DE GB-DE PL-DE, DE10Y). The floor applies to **currency positions
  only**; bond positions are unchanged.
- **EM currencies (for the median):** BRL MXN ZAR TRY IDR PLN COP CLP (v1.0's 8 non-G10 currencies; T17's EM set).
- **Periods:** **exploration 2005-01..2019-12** (v1.0's design sample; §4). **Confirmatory 2020-01..2026-09**
  (81 months), run **once**. Each year 2020–2026 (2026 = January–September) is reported separately.
- **Holdout (spec §0.3(c)):** T01's split, `em_macro/holdout.py`, seed 20261103. Half B = BRL COP ZAR TRY GBP; BR10Y
  CO10Y ZA10Y TR10Y GB-DE FR-DE IT-DE, run as a stand-alone strategy via `tstrend.subset` (no v1.0 code changed).
  Half A (MXN CLP PLN IDR EUR; MX10Y CL10Y PL-DE ID10Y ES-DE DE10Y) is context. In both halves q_t (§3.1) is the
  **same global EM8 series** as in the full run (as T17 used global factor series).
- **Costs:** 1x (v1.0's cost model) is decisive. Every run is repeated at 2x (`tstrend.with_costs`), for v1.0 and
  T27 alike.
- **Data:** v1.0's input snapshots and cached raw downloads, plus the IMF classification tables of §3.2 (public IMF
  data, committed under `data/kept/T27/`).
- **Reproduction check first:** before any T27 return is computed, `python -m em_macro.verify_v1` must report that
  v1.0's committed tables reproduce byte for byte. If it does not, nothing is run.
- **No parameters are estimated from returns**: every number is fixed below, so the year-by-year walk-forward equals
  one causal run.

### 2.1 Statistics

Monthly net returns over the window, as in T16–T19 §2.1 (`em_macro/t01.py`). **SR** = mean/SD × √12 (ddof 1).
**Return** compounded, annualised. **Vol** = SD × √12. **MaxDD** = maximum drawdown of the compounded monthly index.
**Worst month** = lowest monthly net return. **ES(97.5%)** = Acerbi–Tasche historical expected shortfall
(`t01.expected_shortfall`), reported. **Turnover** as `t01.turnover`. **Correlation** = Pearson correlation of
monthly net returns of T27 and v1.0, reported only.

**Sharpe non-inferiority, margin 0.05.** ΔSR = SR(T27) − SR(v1.0). The pass rule requires the point estimate
ΔSR_hat ≥ −0.05. The bootstrap p-value of H1: ΔSR > −0.05 against H0: ΔSR ≤ −0.05 is **reported, not required**:
paired circular block bootstrap of the 81 (T27, v1.0) monthly return pairs, block length 6 months, B = 10,000,
`numpy.random.default_rng(20261103)`;

```
p = (1 + #{b : ΔSR*_b − ΔSR_hat ≥ ΔSR_hat + 0.05}) / (B + 1)
```

The bootstrap mean, SD and 5%–95% range of ΔSR* are reported.

**Deflated Sharpe.** PSR and DSR as in spec §0.2(c) via `em_macro/mtstats.py`, from each strategy's realised
2020-01..2026-09 monthly SR, sample skewness and raw kurtosis, T = 81, noise-only null (trial-Sharpe SD = 1/√(T−1)
per month), N as in §6.

## 3. Specification (fixed; no parameter is chosen from any backtest result)

### 3.1 The volatility floor and the rescaling

Notation: σ_{i,t} = v1.0's volatility, the trailing 36-month standard deviation × √12 of monthly excess returns
(min 12 months; `systematic._vol`). M_{i,t} = 1 if currency i is classified as managed at decision month t (§3.2),
else 0.

```
q_t      = median( { σ_{j,t} : j in EM8, σ_{j,t} defined } )      needs at least 4 values, else no floor at t
σ*_{i,t} = max(σ_{i,t}, q_t)   if M_{i,t} = 1 and q_t is defined
         = σ_{i,t}             otherwise
```

The managed currency itself is included in the median when it is one of the EM8.

**Where σ\* is used (the one change):** only in the FX book's inverse-volatility raw weights in `book_weights`,
raw_i = ±1/σ*_{i,t}. Everything else is v1.0's:
1. **Selection is unchanged**: eligibility still needs σ_{i,t} defined; the thirds come from v1.0's signals.
2. **Rescaling to 10%** uses v1.0's own rule unchanged: the FX book is rescaled with the trailing 36-month pro-forma
   standard deviation of the floored raw weights (target 10%); then the 50/50 mix, the total rescaling to 10%, the
   6× cap, the 25% band and costs.
3. A floored managed currency therefore gets a smaller share of the FX book's risk, and the rescaling hands that
   risk back to the other positions.

The bond book is not touched (v1.0's bond returns are local-currency excess returns over the local policy rate,
sized on their own volatility).

### 3.2 IMF de facto classification: sourcing, by year, without look-ahead

**Source.** The IMF *Annual Report on Exchange Arrangements and Exchange Restrictions* (AREAER), table "De Facto
Classification of Exchange Rate Arrangements", **as printed in each annual edition**. Later revisions, the AREAER
Online back-series and retroactive effective dates are not used: a classification counts only from the date it
became public. One row per (edition, country) goes in `data/kept/T27/imf_areaer_classification.csv`; the editions
table `data/kept/T27/imf_areaer_editions.csv` records each edition's as-of date, publication date and source (URL,
page).

**Timing.** An edition published in calendar month m is first used for the decision at the end of month m + 1, and
stays in use until a later edition replaces it. If an edition's publication date cannot be documented, it is assumed
published on 31 December of the year after its as-of date. A currency-month not covered by any edition published by
then is "not managed". The editions needed run from the latest one published before 2005-01 to the latest one
published before 2026-09.

**Euro and GBP:** EUR takes the euro area's classification, GBP the United Kingdom's.

**Category mapping (fixed before any classification was looked up):**

| scheme | managed (M = 1) | not managed (M = 0) |
|---|---|---|
| 2009 revision onward | crawl-like arrangement; stabilised arrangement; crawling peg; conventional peg; **other managed arrangement** | no separate legal tender; currency board; pegged exchange rate within horizontal bands; floating; free floating |
| 1999–2008 scheme | conventional fixed peg (single currency or composite); crawling peg; crawling band (treated as crawl-like) | no separate legal tender; currency board; pegged within horizontal bands; managed floating with no predetermined path; independently floating |

Before any return is computed, the classification table, the editions table and the list of managed currency-months
are committed.

### 3.3 Step 0: applicability check (before any return)

The currency-months in which the floor binds (M = 1, σ_{i,t} < q_t, and the currency selected, i.e. a non-zero raw
weight in v1.0) are counted for 2005-01..2019-12 and 2020-01..2026-09. The count uses v1.0's own volatilities and
selections and the classification table only; no T27 return is computed. **If the count for 2020-01..2026-09 is
zero, T27 is identical to v1.0 in the confirmatory window:** the trial is recorded "not run (degenerate: the floor
never binds)", no confirmatory statistic is computed, and the ledger row says so.

## 4. Exploration 2005–2019 (one specification)

The specification of §3 is run on 2005-01..2019-12, all 23 instruments, at 1x and 2x costs. **No variant is
computed** (no other floor level, category set, lag or volatility estimator); the holdout halves and the 2x-cost runs
apply the same rule to a different universe or cost level and are not variants. Any variant would be a new trial
with a new ledger row.

**Exploration gate (2005–2019, all instruments, 1x).** ΔSR(T27 − v1.0) ≥ −0.05 **and** |MaxDD(T27)| ≤
|MaxDD(v1.0)|. If the gate fails, the confirmatory test is not run and T27 is recorded "failed at exploration". If
the floor never binds in 2005–2019, the gate passes trivially.

## 5. Confirmatory test and pass rule (2020-01..2026-09; 1x decisive, 2x reported)

Baseline: frozen `systematic.run(inp, ["carry","trend","value"])` on the same inputs, universe and costs.

| # | criterion | passes if |
|---|---|---|
| 1 | Risk improvement and Sharpe non-inferiority, all 23 instruments | \|MaxDD(T27)\| ≤ 0.90 × \|MaxDD(v1.0)\| **and** ΔSR_hat ≥ −0.05 (bootstrap p of §2.1 reported, not required) |
| 2 | Holdout, half B | \|MaxDD(T27, half B)\| ≤ 0.90 × \|MaxDD(v1.0, half B)\| **and** SR(T27, half B) ≥ SR(v1.0, half B) − 0.05 |
| 3 | Worst-month loss | worst monthly net return(T27) ≥ worst monthly net return(v1.0) |
| 4 | Cost-adjusted return | compounded annual net return(T27) ≥ v1.0's, at 1x costs **and** at 2x costs |
| 5 | Deflated Sharpe | DSR(T27; N = 21) ≥ DSR(v1.0; N = 7) |

**Reported, not a criterion:** the correlation of T27's and v1.0's monthly net returns. The floor is meant to shrink
v1.0's largest position when it binds, so a large drop in correlation is expected and is not a failure.

T27 **passes only if all five criteria hold.** Any failure means T27 is not adopted and v1.0 (and v1.1) stay live
unchanged. The 2005–2019 results (beyond the gate of §4), half A, the 2x tables (other than criterion 4) and the
diagnostics cannot affect the decision. No criterion, threshold, parameter, mapping or sample may be changed after
the classification table is built or any result is seen.

## 6. Multiple testing

- **Spec N convention (decisive):** N = 16 after T20–T22 (T20–T22 §2.8). T23–T26 add 4 (T23–T24 §8 and T25–T26 §9:
  a later pre-registration that uses a DSR counts T23, T24, T25 and T26), and T27 adds 1: **N = 21**. As in T16–T19,
  T27 is compared with v1.0 at N = 7.
- **Reported, not decisive:** the dispersed-trials null (SD 0.20 annualised) and the ledger convention (rows
  T01–T27).
- One confirmatory test with one specification: no Holm adjustment.

## 7. Diagnostics reported (not criteria)

- The managed currency-months by currency and year, and the AREAER edition used for each.
- The months in which the floor binds; σ_{i,t} vs q_t; the FX weight of the floored currency under v1.0 and T27; the
  total scaler under both.
- Turnover under v1.0 and T27; v1.0's five worst months in 2020-01..2026-09 with T27's return next to each.
- Every devaluation episode in a managed currency (a monthly move of more than 2σ_{i,t} against USD), with v1.0's and
  T27's P&L in that currency in that month.
- The correlation of T27 with v1.0, overall and by year.

## 8. Reporting (spec §0.4)

`results/T27_managed_fx_floor.md` will report: the Step 0 count; the exploration table (T27 vs v1.0, 2005–2019, 1x
and 2x) and the gate outcome; if the confirmatory test runs, the pass/fail table per criterion (1x decisive, 2x
reported) **with the disclosure caveat of the header repeated next to it** (the idea was prompted by TRY's managed
path and its 2018 and 2021 devaluations; 2021 is inside the confirmatory window, so a pass is weaker evidence than a
clean out-of-sample result); v1.0 and T27 side by side (SR, return, vol, MaxDD, worst month, ES97.5, turnover,
correlation) for 2020-01..2026-09, by year, for half B, and for half A as context; the bootstrap ΔSR distribution and
p-value; the deflated-Sharpe update; the diagnostics of §7; and every decision in §9. No editorialising about
adoption beyond the mechanical pass/fail. Tables and monthly returns go to `results/T27/`, with `RUN.json` (run
time, commit, SHA-256 of code, pre-registration, classification tables and inputs, the v1.0 reproduction check).

**Ledger.** `trials.csv` gets row T27 (group G22), marked pre-registered and not run, in the commit after this
document, changing no other row. It is updated with the outcome after the run.

## 9. Decisions taken under the task's rules (listed again in the report)

1. **Floor:** the cross-sectional median of v1.0's own 36-month σ across the 8 EM currencies, at least 4 values; the
   managed currency is included in the median.
2. **Placement:** σ\* replaces σ only in the FX book's inverse-volatility raw weights. Rescaling to 10% uses v1.0's
   unchanged pro-forma book and total rules; selection and bonds are unchanged.
3. **Classification:** AREAER editions as printed, first used one month after publication (31 December of the
   following year if the publication date cannot be documented); unclassified = not managed; EUR = euro area, GBP =
   United Kingdom.
4. **Mapping:** 2009+ scheme: crawl-like, stabilised, crawling peg, conventional peg and other managed arrangement
   are managed. 1999–2008 scheme: conventional fixed peg, crawling peg and crawling band are managed; horizontal
   bands, managed floating with no predetermined path and independently floating are not.
5. **Variants:** none; one specification. N = 21 (spec convention), v1.0 at N = 7.
6. **Gates:** Step 0 degenerate check before any return; exploration gate on 2005–2019 (ΔSR ≥ −0.05, MaxDD no worse)
   before the confirmatory run.
7. **Pass rule:** the T16–T19 risk-trial form (MaxDD at least 10% lower, ΔSR ≥ −0.05, the same in half B), plus
   worst month, cost-adjusted return at 1x and 2x, and DSR. The bootstrap p and the correlation with v1.0 are
   reported only.
8. **Holdout:** q_t is the global EM8 series in both halves.
9. **Disclosure:** the TRY prompt and the 2021 devaluation inside the confirmatory window are stated in the header
   and repeated in the report.
