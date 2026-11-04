# Pre-registration — trial T02: economic momentum as a fourth signal

| item | value |
|---|---|
| trial | T02 (pre-registered trial series). **Ledger id `T13`** in `trials.csv` (`T01`/`T02` are already ledger ids of v1.0 and the gold event trades; T01's ledger id is T12). The ledger row's name says "T02". |
| branch | `trial/T02-econ-momentum` |
| baseline | v1.0, tag `v1.0-frozen` = commit `7886867` (`em_macro/systematic.py` SHA-256 `1eb4cf6b…50be66`, `results/systematic/fit/frozen_design.json` SHA-256 `f0cce4c9…983858`). v1.0 stays the live baseline; no v1.0 file is modified. |
| written | 2026-11-03, before any T02 signal was computed and before any T02 code touching returns was written. Committed on its own before any T02 backtest. |
| inputs fixed before this document | `docs/research/T02_econ_momentum_literature.md` (Step 1: signal from the literature, ambiguities resolved), `docs/research/T02_data_feasibility.md` and `results/T02/data_coverage_*.csv` (Step 2: data availability, examined without any returns). |
| spec | `docs/research/algorithm_spec_2026-11.md` §0.3 (four-stage test and pass rule), §0.4 (honest reporting), §4.1 (economic momentum), §13 (pre-registration, trial ledger) |
| what has been seen | No T02 signal value, no T02 return, no correlation of any macro series with any currency or bond return. Only the raw macro vintages' coverage (dates, counts, lags). |

## 1. Hypothesis and evidence (spec §0.3(a))

**Hypothesis.** Adding economic momentum (Dahlquist and Hasseltoft 2020) as a fourth, equal-weight signal to v1.0's
currency book improves the strategy.

**Published evidence** (details in `docs/research/T02_econ_momentum_literature.md`):
- Dahlquist and Hasseltoft (2020, *JFE* 136, 152–167): past trends in economic activity and inflation predict currency
  returns; a long-short strategy on 33 currencies, 1976–2017, has Sharpe 0.70 and a significant alpha against carry,
  momentum and value; it subsumes the carry alpha.
- The 2015 working paper (20 currencies, 1976–2014): combo Sharpe 1.10, 0.85 without the interest-rate variables;
  net Sharpe 0.96 at a 15 bp spread.
- Replications used as benchmarks: Fan et al. (2025, *European Financial Management*) and an Aalto University
  thesis (2020). No peer-reviewed 2018–2026 evaluation exists (spec §17.4 open question).
- The spec's prior (§17.1 #9): ΔSR +0.05 to +0.15; evidence grade B.

**Disclosure of what is already known.** v1.0's attribution (`results/diagnostics_v1.md`) shows carry as the main
earner in 2020–2026 and the paper says the signal is collinear with carry. Nothing about economic momentum's own
behaviour on these 10 currencies has been computed.

## 2. Specification (fixed; no parameter is chosen from any backtest result)

All machinery not mentioned here is v1.0's, imported from the frozen `em_macro/systematic.py` without changes
(inputs, returns, execution lags, costs, the volatility rule and the no-trade band). New code goes in new modules only.

### 2.1 Scope: currencies only

- The economic-momentum signal is defined for v1.0's **10 currencies**: BRL MXN ZAR TRY IDR PLN GBP COP CLP EUR,
  using the macro data of Brazil, Mexico, South Africa, Turkey, Indonesia, Poland, the United Kingdom, Colombia,
  Chile and the **euro-area aggregate** (for EUR).
- **Bonds: not applied.** The paper is a currency paper and never applies the signal to bonds; the only bond
  application found is a master's thesis (not peer-reviewed) whose own abstract limits the effect to the inflation
  measure and unhedged returns, and whose economics imply the opposite sign for a local bond. Spec §0.3(a)
  requires a peer-reviewed, central-bank, BIS or IMF source; none exists for bonds and none at all for the spread
  trades over the Bund. v1.0's 13 bond positions therefore keep their carry/trend/value composite unchanged.

### 2.2 Macro inputs

Variables, per country, monthly:

| component | series | sign |
|---|---|---|
| IP | industrial production index, total industry excluding construction, seasonally adjusted (OECD `PRVM`/`BTE`; euro area: ECB RTD `I_XCONS`) | + |
| RS | retail trade volume index, seasonally adjusted (OECD `TOVM`/`G47`; euro area: ECB RTD `O_RTXMOTVD`) | + |
| U | unemployment rate, total, seasonally adjusted (OECD `UNEMP`; euro area: ECB RTD `L_UNETO`); enters as **1/U** | + (via 1/U) |
| CPI | consumer price index, all items, not seasonally adjusted (OECD `CP`; euro area: ECB RTD `P_C_OV`, HICP) | + |

Producer prices are **not** used (literature document, ambiguity A2): no first-release vintages exist for nine of the
ten economies, so the inflation index is CPI only, for every country.

### 2.3 Vintages and the information set (the central data rule)

- **Decision date:** the end of month t (v1.0's rebalance). The signal for month t uses only observations that were
  published on or before the last calendar day of month t, as they were published then.
- **OECD revisions database** (nine economies): the vintage used at the end of month t is the edition dated month t
  (`EDITION = YYYYMM` of t), which is the Main Economic Indicators issue compiled during month t. Within that
  edition, every observation is taken as printed there. If no edition exists for month t, the latest earlier edition
  is used.
- **ECB Real Time Database** (euro area): the vintage used at the end of month t consists of, for each reference
  period, the latest value whose `VALID_FROM` timestamp is on or before the last calendar day of month t.
- **ALFRED** (gap filler, see 2.4): the vintage with the latest `vintage_date` on or before the last calendar day of
  month t.
- Growth rates are computed **within one vintage only**; two vintages are never mixed in one difference.
- No fixed publication lag is added when vintages are used; the lag is whatever the vintage embodies.

### 2.4 Fallbacks and known look-ahead risks

Where no vintage exists for a (country, component, month), the rule is fixed as follows. Every fallback use is a
known look-ahead risk; the share of (currency, month) scores built with any fallback component is reported.

| country | component | vintage source and start | fallback (revised series, lagged 3 months as in the paper) |
|---|---|---|---|
| Brazil | IP, CPI | OECD editions from 2001-01 | none needed from 2005 |
| Brazil | RS | OECD editions from 2001-11 | none needed from 2005 |
| Brazil | U | OECD editions 2001-03 to 2012-05 (the old monthly survey, discontinued); ALFRED vintages of the OECD monthly rate `LRUNTTTTBRM156S` from 2013-06-03 (23 vintages) until the series ends in 2015-11 | 2012-06 to 2013-05: revised series (the ALFRED vintage of 2013-06-03), lagged 3 months, **flagged**; **from 2015-12: no vintage source**; the component is **omitted** for Brazil from then on (A4), rather than filled with revised data, because the revised PNAD Contínua series is a different survey |
| Mexico | IP, RS, U, CPI | OECD editions from 1999-02 | none needed; OECD CPI editions stale after 2026-03: revised OECD KEI CPI, flagged |
| South Africa | IP, RS, CPI | OECD editions from 2002-06 | none needed from 2005; CPI editions stale after 2025-07: revised OECD KEI CPI, flagged |
| South Africa | U | OECD revisions database has none; ALFRED vintages of the OECD quarterly rate `LRUNTTTTZAQ156S` from 2013-07-01 (50 vintages, to 2026-10) | before 2013-07: revised quarterly OECD rate (the ALFRED vintage of 2013-07-01), lagged 3 months, carried forward to monthly; **flagged** |
| Turkey | IP, CPI | OECD editions from 1999-02 | none needed; CPI editions stale after 2026-06: revised OECD KEI CPI, flagged |
| Turkey | U | OECD editions from 2006-04 | 2005-01 to 2006-03: revised OECD KEI rate, lagged 3 months, **flagged** |
| Turkey | RS | OECD revisions database has none; series starts 2010-01; ALFRED vintages of `TURSLRTTO01IXOBSAM` from 2018-07-17 (34 vintages; the FRED series ends 2024-03) | 2010-01 to 2018-06 and after 2024-03: revised OECD KEI series, lagged 3 months, **flagged**; before 2010 the component does not exist (omitted, A4) |
| Indonesia | CPI | OECD editions from 2001-10 | none needed |
| Indonesia | IP | OECD editions from 2005-07 (gap in 2024 editions) | before 2005-07 and in gaps: revised OECD KEI series, lagged 3 months, **flagged** |
| Indonesia | RS, U | no vintage source and no OECD series | **omitted** (A4): Indonesia's economic-activity index is IP only |
| Poland | IP, RS, CPI | OECD editions from 1999-02/1999-07 | none needed; CPI editions stale after 2026-06: revised OECD KEI CPI, flagged |
| Poland | U | OECD editions from 2003-02 | none needed from 2005 |
| United Kingdom | IP, RS, U, CPI | OECD editions from 1999-02 | none needed |
| Colombia | IP, RS, CPI | OECD editions from 2020-05; before that, ALFRED vintages from 2018-07-17 to 2020-04 of the OECD-sourced FRED series: manufacturing production `COLPRMNTO01IXOBSAM` (54 vintages; no total-industry id exists in FRED), retail `COLSLRTTO01IXOBSAM` (37) and `COLSLRTTO02IXOBSAM` (12, older series to 2018-12), CPI `COLCPALTT01IXOBM` (67) | before 2018-07: revised OECD KEI series, lagged 3 months, **flagged**; RS exists only from 2013-01 in the OECD database (omitted before, A4) |
| Colombia | U | OECD editions from 2020-05 only; no FRED/ALFRED series exists | 2007-01 to 2020-04: revised OECD KEI rate, lagged 3 months, **flagged**; before 2007-01 the series does not exist (omitted, A4) |
| Chile | IP, U | OECD editions from 2010-06/07 | 2005-01 to 2010-05: revised OECD KEI series, lagged 3 months, **flagged** |
| Chile | CPI | OECD editions 2010-06 to 2024-06 (stale after) | before 2010-06 and after 2024-06: revised series (OECD KEI to 2023-12, then FRED/BCCh CPI), lagged 3 months, **flagged** |
| Chile | RS | OECD editions 2010-06 to 2019-06 (series stops 2018-12 in the OECD database) | before 2010-06: revised OECD series lagged 3 months, **flagged**; after 2018-12 the component is **omitted** (A4) |
| euro area | IP, RS, U, CPI | ECB RTD vintages from 2001-01-03 | none needed |

The exact series ids, vintage counts and dates are in `results/T02/data_coverage_*.csv`; the raw files and their
SHA-256 hashes are listed in `results/T02/raw_data_manifest.csv`. If a fallback listed here turns out to be
unavailable when the trial is run, the component is omitted (A4) rather than replaced by a source not named here.

### 2.5 Signal construction (literature document §2.2–2.4, ambiguities A3–A6)

For each country c, vintage month t and index i ∈ {econ, infl}:

```
g_econ,t = mean over available components of { RS_t/RS_{t-1} − 1,  IP_t/IP_{t-1} − 1,  U_{t-1}/U_t − 1 }
g_infl,t = CPI_t/CPI_{t-1} − 1
FI_i,t   = (1 + g_i,t) · FI_i,t-1,  FI_i,first = 100              (chain-linked within the vintage)
z_{c,i,l,t} = ln FI_i,T(c,t) − ln FI_i,T(c,t)−l,   l = 1, …, 60       (T(c,t): last month published in the vintage)
```

- Quarterly observations are carried forward to months within the vintage. A component missing at t or t−1 is left
  out of that month's average; if no component is available, g is missing and the index is not extended.
- For each sub-signal (i, l), currencies with a value are **ranked** cross-sectionally (ties averaged) and the rank
  demeaned: `r_{c,i,l,t} = rank(z_{c,i,l,t}) − mean_c rank`. A sub-signal exists in month t only if at least 3
  currencies have it.
- **Score:** `ECONMOM_{c,t} = mean over the available (i, l) of r_{c,i,l,t}`, equal weights across the 2 indices
  and the 60 look-backs; defined only when at least 12 of the 120 sub-signals exist for c; otherwise missing.
- v1.0 then z-scores `ECONMOM` across the currency book (`_xs_z`, at least 3 currencies), like every other signal.
- No look-back, weight, lag or threshold above is chosen from any return; all follow the literature document.

### 2.6 Integration into v1.0

- Currency book composite: `mean(z_carry, z_trend, z_value, z_econmom)` over the available signals (v1.0's
  `signal_weights` rule, "mean of the available signal z-scores"). Bond book composite: unchanged
  (`carry, trend, value`).
- Everything else identical to v1.0: cross-sectional z-scores per book, long top third / short bottom third
  (n = floor(N/3)), inverse 36-month volatility sizing, each book scaled to 10% (trailing 36-month pro-forma,
  minimum 12 months), books mixed 50/50, total rescaled to 10%, 6× gross-leverage cap, 25% no-trade band,
  v1.0's cost model (10 bp; 30 bp for TR, ID, CO, CL; spreads twice), FX weights decided at t earn t+1, bonds t+2.
- Implementation: a new module computes the `ECONMOM` z-score frame and injects it into the FX book's signal
  dictionary; the frozen `book_weights`, `run` and `evaluate` are called unchanged with `use = ["carry", "trend",
  "value", "econmom"]` for the FX book. The bond book is run with v1.0's three signals.
- **Before the signal's first valid month** (data permitting from 2005; the vintage store starts 1999–2002 for most
  economies), a currency's composite is the mean of its available signals, exactly as v1.0 handles a missing value
  signal.

### 2.7 Cost sensitivity

Every run is repeated at **2x costs** (each instrument's cost per unit traded doubled, for v1.0 and T02). The pass
rule is decided at **1x costs**. The 2x results are reported, not decisive.

## 3. Samples and the holdout split

**Periods.**
- **Test (decisive):** 2020-01 to 2026-09 (81 months).
- **Context only:** 2005–2019 (from the first live month to 2019-12). Reported as in-sample for v1.0, and
  **cannot affect the decision**.
- **Walk-forward:** T02 estimates no parameters, so the spec's year-by-year walk-forward (§0.3(b)) equals one causal
  run; the vintage rule makes every input point-in-time. Results are reported per year 2020–2026 and pooled.

**Holdout split (spec §0.3(c)): T01's split is reused**, seed 20261103, `em_macro/holdout.py`, so the trials are
comparable.

| half | units | currencies | bonds |
|---|---|---|---|
| A | MX, CL, PL, ID, ES, DE, euro area | MXN CLP PLN IDR EUR | MX10Y CL10Y PL-DE ID10Y ES-DE DE10Y |
| **B (holdout)** | BR, CO, ZA, TR, GB, FR, IT | BRL COP ZAR TRY GBP | BR10Y CO10Y ZA10Y TR10Y GB-DE FR-DE IT-DE |

- v1.0 (frozen code) and T02 are each run on the half-B universe as a stand-alone strategy (z-scores, thirds,
  ranks and scaling within half B; 5 currencies, so one long and one short). The `ECONMOM` ranks in the holdout
  are computed over the half-B currencies only.
- T02 was "developed" on half A only in the sense that it was specified without looking at any result.
- Decisive holdout window: 2020-01..2026-09. Half B 2005–2019 and half A are context.

## 4. Pass rule (spec §0.3; all five must hold, at 1x costs)

Notation as in T01: monthly net returns 2020-01..2026-09; SR = mean/std × √12 (ddof 1); MaxDD on the compounded
index; ES(97.5%) = historical expected shortfall of monthly net returns (Acerbi-Tasche, α = 0.025, m = αT = 2.025);
baseline = frozen `systematic.run(inp, ["carry", "trend", "value"])` on the same inputs.

| # | criterion | passes if |
|---|---|---|
| 1 | 2020-01..2026-09 vs v1.0, 6-month block bootstrap | ΔSR = SR(T02) − SR(v1.0) > 0 **and** one-sided p < 0.10. Paired circular block bootstrap of the 81 (T02, v1.0) monthly pairs, block length 6, B = 10,000, `numpy.random.default_rng(20261103)`; p = (1 + #{b : ΔSR*_b − ΔSR ≥ ΔSR}) / (B + 1). |
| 2 | Holdout, half B, 2020-01..2026-09 | ΔSR(half B) > 0 **and** \|MaxDD(T02, half B)\| ≤ \|MaxDD(v1.0, half B)\| |
| 3 | Tail risk, 2020-01..2026-09 | \|MaxDD(T02)\| ≤ 1.10 × \|MaxDD(v1.0)\| **and** ES97.5(T02) ≤ 1.10 × ES97.5(v1.0) |
| 4 | Deflated Sharpe, N incremented by one | DSR(T02; N = 9) ≥ DSR(v1.0; N = 7) (details below) |
| 5 | Signal-specific alpha | the economic-momentum sleeve's net monthly returns, regressed on the net returns of v1.0's carry-only, trend-only and value-only runs with an intercept, 2020-01..2026-09: alpha > 0 **and** t(alpha) > 1.5 (details below) |

**Criterion 4 details.** DSR = PSR against SR0 (spec §0.2(c)) via `em_macro/mtstats.py`, inputs: monthly SR, T = 81,
each strategy's own sample skewness and raw kurtosis over 2020-01..2026-09. Decisive null: noise-only,
trial-Sharpe SD = 1/√(T−1) per month. **N:** the spec count is now 8 (7 at v1.0's freeze plus T01), so T02 is
evaluated at N = 9. It is compared with v1.0 at N = 7, v1.0's value as recorded in T01's report (0.619), which is
the stricter comparison; DSR(v1.0; N = 8) and the ledger convention (N = 12 vs 11) are reported, not decisive.

**Criterion 5 details.**
- **Economic-momentum sleeve:** the FX book run through v1.0's frozen machinery with the single signal
  `["econmom"]` (thirds, inverse-vol sizing, 10% book vol, 10% total rescale, 6× cap, band, costs), net returns.
- **Regressors:** v1.0's frozen `systematic.run(inp, [k])` for k in carry, trend, value (both books, as in
  v1.0's `evaluate` variants), net returns.
- **Statistic:** OLS with intercept over the 81 months; Newey-West (HAC) standard errors with 3 lags, as in
  `results/diagnostics_v1.md`. Pass if the intercept is positive and its t-statistic exceeds 1.5.
- Context only: the same regression over 2005–2019 and the sleeve's own Sharpe, turnover and costs.

**Decision.**
- T02 **passes only if all five criteria hold**. Any failure means T02 is not adopted and v1.0 stays live
  unchanged.
- No criterion, threshold, parameter, data rule or sample may be changed after results are seen. Any variant run
  after this (other weights, carry replacement, orthogonalised version, PPI, bonds, other lags) is a new trial with
  its own ledger row.

## 5. Reporting (spec §0.4)

`results/T02_econ_momentum.md` will report:
- the pass/fail table, criterion by criterion, at 1x and 2x costs;
- annual returns of v1.0 and T02 for 2020–2026 side by side;
- for both strategies: Sharpe, return, volatility, MaxDD, ES(97.5%), turnover and costs over 2020-01..2026-09
  (test), 2005–2019 (context) and half B (holdout);
- the economic-momentum sleeve on its own, its alpha regression, and its correlation with the carry sleeve;
- the share of (currency, month) scores that used any fallback (revised) component, and a first-release-vs-latest
  comparison of the signal (spec §13) as a diagnostic;
- the deflated-Sharpe update.

Rules: v1.0's numbers stay labelled "OOS for v1.0 only"; T02's numbers are reported separately and never merged
with v1.0's; 2005–2019 figures are context only and cannot affect the decision; no recommendation beyond the
mechanical pass/fail.

**Reproduction check.** Before T02 is run, the frozen `systematic.evaluate` on the current inputs is compared with
the committed `results/systematic/test/performance_2020_on.csv`; any difference from re-downloaded inputs is reported
and the comparison is made like-for-like on the same inputs.

**Ledger.** `trials.csv` gets the T02 row (ledger id T13, new trial group `G12_econ_momentum`) marked pending,
in the commit after this document; it is updated with the outcome after the run.
