# Pre-registration — trials T23–T24: T21 (basis-momentum) and T22 (diversified futures trend) on 1979–1999

| item | value |
|---|---|
| trials | **T23**: the T21 basis-momentum sleeve, rules unchanged, on **1979-05..1999-12**. **T24**: the T22 diversified futures trend sleeve, rules unchanged, on **1979-04..1999-12**. Ledger ids `T23` and `T24` in `trials.csv` (the next free ids; the last row is T22). Trial groups: **`G20_basis_momentum`** (T23) and **`G21_diversified_futures_trend`** (T24). These are the same hypotheses and rules as T21 and T22, tested on a new sample, so they share T21's and T22's groups (as T05 and T06 share G05). |
| what this is | A **backward out-of-sample test** on the years before T20–T22's design sample (2000-01..2019-12). It covers only the sleeve-level gates, because v1.0 and v1.1 do not exist before 2005. |
| family | T23 and T24 are **one family**. The Holm adjustment across the two trials is defined in §4.3. |
| rules | T21 and T22 **exactly as run at `a160bfd`**: the T20–T22 pre-registration (`docs/prereg/T20-T22_commodity_trials.md`) with Amendments 1–4, the Build 0 report (`results/T20-T22/build0.md`) and the trial code. Same signals, roll rule (35-day buffer, Amendment 3 guard, Amendment 4.4 missing months), volatility estimators, rank weights, 10% single-market risk cap, 10% sleeve target with the 36-month pro-forma scaler, v1.1's T18 band, and "decisive" costs (2 × c_raw). **No parameter changes of any kind.** |
| code | Run with the code at `a160bfd`, unchanged. SHA-256: `em_macro/t2022.py` `d54cdc75…3345528a`, `em_macro/commod_data.py` `e5ffe76b…8f49cb25`, `em_macro/commod_build0.py` `2c58f7e2…6e1951c`, `em_macro/t18_rebal.py` `dda6456d…0f96c43`, `em_macro/systematic.py` `1eb4cf6b…50be66`, `em_macro/t01.py` `bc52b3e0…2432b2b` (identical at `7405e5f`, where T20–T22 ran, and at `906e5d5`, the base of this branch). New code is limited to the window and the reporting (§6). |
| data | Norgate, private repo `EthanC100/em-macro-data`: `norgate/2026-11_futures/` (manifest SHA-256 `1d6657e6…0f5e60`), `norgate/2026-11_financials/` (`91d1d9e2…5aa5129`), `norgate/2026-11_metadata/metadata.csv` (`2efd5eaa…cad9d`). These are the inputs T20–T22 used; their hashes were re-checked in this session. Nothing new is exported. |
| branch | `prereg/T23-T24-pre2000`: this document, the Phase 1 availability check and its output, and the pending ledger rows. The run goes on `trial/T23-T24-pre2000`, branched from this commit, **only after the owner replies "approved"**. |
| written | 2026-11-06. **No return, signal, sleeve or statistic over 1978–1999 was computed in writing it.** The only data step was the Phase 1 availability check (§2): it uses whether a settlement exists on a date and the contract calendar, and prints counts and dates only. |
| changes nothing else | No v1.0 or v1.1 file, no T20–T22 file (pre-registration, Build 0 report, results, trial code) is modified. |

## 1. Hypotheses, and what the result means

| trial | hypothesis (restated from T21 and T22, without the v1.1 combination) | prior evidence |
|---|---|---|
| T23 | A cross-sectional, monthly sleeve that is long commodities whose first-nearby contract outperformed its second-nearby over the past 12 months, and short the reverse, earns a positive return after decisive costs. It also has positive alpha against the commodity carry sleeve. | Boons and Porras Prado (2019, JF; ~1959–2014). T21 on 2000-01..2026-09: Newey–West t of the mean net return 2.05; alpha against T20's sleeve 3.4% a year (t 1.89); break-even cost multiple 5.5. T21 failed only the combined criteria C1 and C2 against v1.1. |
| T24 | A time-series trend sleeve of the Moskowitz–Ooi–Pedersen / Hurst–Ooi–Pedersen form, across commodity, currency and bond futures, has a net Sharpe ratio above 0.20 after decisive costs. | MOP (2012; 1965–2009), HOP (2017; 1880–2016). T22: net Sharpe 0.40 on 2000-01..2019-12 and 0.24 on 2020-01..2026-09; break-even 6.6. T22 failed only C1 and C2. |

**What the result means (fixed now).**
- **A pass of T23 or T24** supports a **separate, later pre-registration of a zero-size live shadow** of that sleeve: positions logged monthly, at no capital. It does not adopt anything. It does not start the 12-month paper stage of the T20–T22 pre-registration (§4.4), because neither T21 nor T22 passed.
- **A fail of both closes the commodity line.** No further commodity sleeve (carry, basis-momentum, trend, or a composite of them) is pre-registered in this programme. If one passes and the other fails, the failing sleeve is closed, and only the passing one may go on to a shadow pre-registration.
- **Neither outcome changes v1.0 or v1.1.** Neither re-opens the failed combination tests of T20–T22: their outcomes in `trials.csv` stand as recorded.

## 2. Phase 1: data availability, 1978-01..1999-12 (done; counts and dates only)

`python -m em_macro.t2324_avail run` (this commit) ran the a160bfd data code unchanged. The only change was to start the rebalance schedule and the contract loading earlier (`em_macro/t2324_window.py`), inside the process. The full output is in `results/T23-T24/availability.md`, `availability.json` and `availability_counts.csv`.

For every market of T21 (20 commodities), T22 (the 30 instruments of the a160bfd run) and the T20 carry control, the check applied:
- **Build 0 coverage gate** (§2.1 rule 1): F1 and F2 both settle on the decision date on at least 95% of decision dates. The period runs from the later of 1978-01 and the market's entry to 1999-12.
- **Roll-rule checks**: A6 (notice > execution + 35 days; no held F1 or F2 inside its last 10 trading days, with the Amendment 3 guard; every used contract settles on or before t; Amendment 4.4 missing months) and A11 (F2/F13 listed when used).
- **§2.1 rule 4**: no held contract has a gap of more than 5 consecutive market days. This covers F1 for all markets, and also F2 for the T21 and T20 markets.
- **Entry**: the entry month under §2.1 rule 2.
- **Per month**: whether the market would be active. That means it has entered, is not missing under Amendment 4.4, and has the trial's look-back available: 12 holding months of the F1 and F2 series for T21; 12 months of the F1 index for T22; F13 (Option A) or 3 of 5 prior same-month carries (Option B) for T20.

**Result.**

| trial | markets passing the window checks | first month with ≥ 6 active (§2.1 rule 3) | months below 6 after it |
|---|---|---|---|
| T21 → **T23** | 19 of 20: CL B HO NG G HG ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE | **1979-05** | 0 |
| T22 → **T24** | 24 of 30: CL B HO NG G HG GC SI PL ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE 6B 6M | **1979-04** | 0 |
| T20 (control for T23's S2 only) | 19 of 20 (as T21) | 1981-05 | 5 (1981-07, 1981-09, 1981-11, 1981-12, 1982-02) |

Markets out of the window, mechanically:
- **RB**: no contract before 2005. RBOB starts in 2005, and unleaded gasoline is not in Norgate.
- **6E, FGBL**: entry 2000-03.
- **FOAT, FBTP**: no contract before 2000.
- **R (Long Gilt)**: fails the coverage gate in the window, 70.5%. Its F2 contracts have no settlements for 38 decision months, with 35 F2 gaps of more than 5 days.
- PA, 6L, 6Z and FBON were already out of every trial (Build 0).

Every passing market has 0 A6 and 0 A11 violations in the window, and no held-contract gap of more than 5 days. Brent has one Amendment 4.4 missing month (1989-08, its entry month, F2 without a settlement). Every market whose notice date precedes its LTD has a Norgate first notice date for every contract used in the window, so no exchange-rule fallback is needed. The A2 analogue (F1/F2 coverage ≥ 95% in the window) holds for 19 of the 20 cross-sectional markets: RB is the one without data, and Build 0's threshold is 18.

Active markets: T21 has 6–9 from 1979-05 to 1979-12, 11–15 in 1980–1983, 16–17 in 1984–1989, and 18–19 from 1990. T22 has 6–9 from 1979-04 to 1979-10, 14–19 in 1980–1983, 20–22 in 1984–1990, and 23–24 from 1991. Year-by-year detail is in `availability.md`.

## 3. The test windows (fixed from Phase 1)

| trial | window | months | rule |
|---|---|---|---|
| **T23** | **1979-05 .. 1999-12** | 248 | first month with ≥ 6 active T21 markets (§2.1 rule 3 of T20–T22) to 1999-12 |
| **T24** | **1979-04 .. 1999-12** | 249 | first month with ≥ 6 active T22 instruments to 1999-12 |

- The minimum of 6 is the only per-month minimum the T20–T22 pre-registration sets (§2.1 rule 3, decision 18). Its whole-sample data gate, A2 (≥ 18 of 20 markets with coverage ≥ 95%), holds for the window at 19 of 20.
- **Positions start flat in each window's first month.** The sleeve's first rebalance month is the window's first month, as the a160bfd run's sleeves started flat in 1991-01. This also applies rule 3 to T24 before its window: the a160bfd code enforces the minimum of 6 for T20 and T21 only, and the window start makes that difference moot.
- Data after 1999-12 is used only where the unchanged code needs it: the contract calendar for the roll rule, and the exit of December 1999's positions at the 2000-01 execution, which falls outside the window.
- **Sub-windows reported as context (not decisive):**
  - (a) the window's start to **1991-01**: never computed by any earlier run (§5);
  - (b) **1991-02..1999-12**: computed, but not reported, by the a160bfd run (§5).

## 4. Pass rule (decisive costs; everything else reported, not decisive)

### 4.1 Which gates can run

Only the sleeve-level gates of §4.2 of the T20–T22 pre-registration can run.
- **C1–C4** need v1.1. v1.1 does not exist before 2005, so they are not part of T23 or T24.
- **T22's S2** (correlation with **v1.0's** carry sleeve in carry's worst 8 months of 2020–2026) has the same problem: v1.0's carry sleeve does not exist before 2005. So S2 cannot be applied unchanged and is not a gate for T24. As context only, T24 reports the correlation with the T20 control sleeve in the T20 control's worst 10% of window months.

Every remaining gate is applied **unchanged** to the trial's window, at decisive costs (the sleeve's monthly net return with 2 × c_raw, `Sleeve.monthly(2.0)`), full window universe.

### 4.2 Gates

| trial | # | gate (from T20–T22 §4.2, Amendments 1–4) | passes if |
|---|---|---|---|
| T23 | S1 | mean monthly net return of the stand-alone sleeve, Newey–West (6 lags) t-statistic, over 1979-05..1999-12 | **t > 2 and the Holm-adjusted one-sided p < 0.0228** (§4.3) |
| T23 | S2 | incremental alpha against the **T20 carry sleeve** (the control, §4.4): OLS of the T21 sleeve's monthly net return on the T20 sleeve's, both stand-alone at 10%, decisive costs, Newey–West (6 lags) | annualised intercept > 0 **and** NW t > 1.5 |
| T23 | S3 | break-even cost multiple m* = annualised mean gross return / annualised cost drag at 1 × c_raw, over the window | m* ≥ 2 |
| T24 | S1 | net Sharpe ratio of the stand-alone sleeve (mean/SD × √12, ddof 1) over 1979-04..1999-12 | **SR > 0.20** |
| T24 | S3 | break-even cost multiple over the window | m* ≥ 2 |

**One window instead of two (T24 S1).** T22's S1 asked for SR > 0.20 in **both** of its windows (2000–2019 and 2020–2026). The new sample is one window. The gate becomes SR > 0.20 over that window, with the 0.20 floor unchanged. Sub-windows (a) and (b) are reported as context only.

**A trial passes only if all of its gates hold.** T23: S1 (with Holm), S2, S3. T24: S1, S3.

### 4.3 Holm adjustment across the two trials

Holm needs a p-value for each member of the family.
- **T23's S1** is a significance test. t > 2 corresponds to a one-sided p < 1 − Φ(2) = 0.0228.
- **T24's S1** is a point-estimate floor (SR > 0.20) with no p-value. Its other gate (break-even) has none either.

To apply the Holm adjustment without changing T24's gates, each trial contributes the p-value that matches its S1 claim, that the sleeve earns a positive net return:

```
p_k = 1 − Φ(t_k),   t_k = Newey–West (6 lags) t-statistic of trial k's mean monthly net return over its window
Holm (m = 2): order p_(1) ≤ p_(2);  p_adj,(1) = min(1, 2 p_(1));  p_adj,(2) = max(p_adj,(1), p_(2))
```

- **T23 S1** passes only if t > 2 **and** p_adj(T23) < 0.0228. If T23 has the smaller p, this needs t > 2.28; if T24's p is smaller and itself below 0.0114, it needs t > 2; if T24's p is smaller but not below 0.0114, T23's S1 fails.
- **T24 S1** stays as pre-registered (SR > 0.20). Its raw and Holm-adjusted p are computed and reported but **do not gate T24**, because T22's pre-registered gates contain no significance level that could be adjusted.
- **T23's S2** (alpha t > 1.5) and **both S3** gates are not adjusted, as T20–T22 §5 left the sleeve-level gates unadjusted.

**Honest statement of power** (before any data):
- **T23.** If T21's 2000–2026 performance (NW t 2.05 over 321 months, a net Sharpe of about 0.4) were the true value, the expected t over 248 months would be about 1.8. The chance of t > 2 is then roughly 40%, and of t > 2.28 roughly 30%.
- **T24.** At a true Sharpe of 0.40, the chance that SR > 0.20 over 249 months is roughly 80%.
- So a T23 fail is the more likely outcome even if the effect is real at its 2000–2026 size. A T24 pass is weak evidence on its own.

### 4.4 The T20 carry control (T23 S2)

- **What it is.** T20 exactly as run at a160bfd: de-seasonalised carry, with the Option A/B assignment of Build 0 (A7) **unchanged**. That assignment was decided from 2000–2019 F13 availability; it was decided once and is never changed. Universe: the same 19 window markets as T23. The control is built over T23's window.
- **Where it holds nothing.** It has fewer than 6 active markets before 1981-05 and in the 5 months listed in §2. In those months it holds no positions (rule 3, enforced by the a160bfd code).
- **Regression span.** The S2 regression runs from **the first month in which the T20 control holds a non-zero weight** to 1999-12. Phase 1 puts this at about 1981-05; the run fixes it from the held weights. Months inside that span in which the control holds nothing are kept, with the return the code produces.
- **It is not a trial.** Its own statistics are reported as context, labelled "control, not a test of T20". T20 stays failed whatever they show.

### 4.5 Reported, not decisive

- the 2× cost sensitivity (4 × c_raw);
- sub-windows (a) and (b) (§3);
- the half-A and half-B market universes (T20–T22 §2.7 split, restricted to the window markets; a half with fewer than 6 active markets holds nothing that month);
- by-decade and by-year returns;
- T24's P&L by asset class;
- the correlations of the T21, T22 and T20-control sleeves;
- the months with 6–9 active markets (§7 item 7);
- T24's T20-control crisis correlation (§4.1).

None of these can change a decision.

## 5. Disclosure: what earlier work touched in 1978–1999, and what the literature used

**Earlier work in this repository** (from the commit history and the committed and private outputs; this session read only dates and counts):
1. **The T20–T22 trial run (`7405e5f`, results committed in `03f9d54`) computed sleeve returns for 1991–1999.**
   - **Coverage.** Its sleeves started flat in 1991-01. `results/T20-T22/monthly_net.csv` (public) has monthly sleeve series from 1983-02, with zeros until 1991-01. The **first non-zero month is 1991-02**: 107 non-zero months to 1999-12 (92 for T20 half A, from 1992-04).
   - **Content.** The series are net at decisive and 2× costs, gross, and the 1× cost drag, for T20, T21 and T22, on the full, half-A and half-B universes.
   - **Private outputs.** `em-macro-data/norgate/derived/trials/` holds per-market held weights, daily gross P&L, trades and signals over the same span.
   - **Never reported.** No table, criterion or statistic in `results/T20-T22_commodity_trials.md`, `criteria.json`, `performance.csv` or `diagnostics.json` covers any month before 2000-01.
   - **What this session saw.** Only the file's dates and the count of non-zero months per column. Whether anyone has looked at the 1991–1999 values is not recorded and cannot be ruled out.
   - **Consequence.** **1991-02..1999-12 (107 of T23's 248 months, 107 of T24's 249) is not untouched.** The T23–T24 run will closely reproduce those months. Differences come only from the earlier start (T18 band path, volatility warm-up), the window's coverage gate (Long Gilt out) and the window universe. **1979-04/05..1991-01 has never been computed** by any run. The decisive window is the one the task fixes (§3). Sub-windows (a) and (b) are reported separately so the never-computed part can be read on its own.
2. **Build 0 (`89ee314`) and the A4 diagnostic computed index and carry-portfolio returns from 1990.**
   - **A3**: the equal-weight F1 index and per-market F1 monthly excess returns from 1990-02 (private `derived/build0/A3_*.csv`). Only the correlation with AQR's *Commodities for the Long Run* was reported: 0.975 over 1990-02..2025-05, 0.979 from 2000.
   - **A4**: a KMPV-style carry portfolio's gross returns from 1990-01 (private `A4_carry_portfolio_returns.csv`). Only its correlation with AQR's carry factor was reported: 0.498 over 1990-01..2026-02, 0.522 from 2000.
   - **A4 diagnostic**: AQR's construction on these data from 1990-01, correlation 0.679 only.
   - **Data checks**: A1, A6, A9 and A11 counts and flags, from 1990.
3. **Phase 1 of this pre-registration**: availability counts and dates, 1978–1999 (§2).
4. **The author's knowledge.** The author of this document knows T21's and T22's 2000–2026 results, all T20–T22 reports and the published literature.

**The literature used this period.**
- Boons and Porras Prado's basis-momentum results use commodity futures data from about 1959 to 2014, which **includes 1979–1999**. The same holds for Jiang and Liu (from 1985), Koijen–Moskowitz–Pedersen–Vrugt (1980s–2012), Gorton–Hayashi–Rouwenhorst (1969–2006), Moskowitz–Ooi–Pedersen (1965–2009) and Hurst–Ooi–Pedersen (1880–2016).
- The window is therefore **out of sample for this build** (its construction, roll rule, costs and band were fixed from 2000-on work), but **in sample for the published hypotheses**.
- A pass shows that this build reproduces the published effect on years the build has not been fitted to. It is not independent evidence for the effect itself in the way 2020–2026 was.

## 6. Phase 2 procedure (only after the owner replies "approved")

1. **Branch** `trial/T23-T24-pre2000` from this pre-registration's commit.
2. **New code, window and reporting only**:
   - `em_macro/t2324.py`, which:
     - applies `t2324_window`;
     - builds the markets with `t2022.Mkt`;
     - computes signals with `t2022.signal_t21`, `signal_t22` and `signal_t20`;
     - builds targets and sleeves with `t2022.build_targets` and `t2022.Sleeve`, with `months` = the trial's window (control: T23's window);
     - computes the statistics with `t2022.nw_tstat`, `nw_regression`, `sr`, `stats` and `holm`, and the gates of §4;
     - writes the report.
   - `tests/test_t2324.py`. **Tested on synthetic data first** (no real data), including checks that:
     - the window and start month are applied;
     - the gates and the Holm rule of §4.3 decide correctly at their boundaries;
     - the T20-control regression span starts at the control's first held weight;
     - the reused t2022 functions are called unchanged.
   - No t2022/commod_* function is edited or reimplemented.
3. **Run-time checks before any sleeve is computed** (each recorded in `RUN.json`; a failure stops the run and is reported, and no sleeve is computed):
   - **D0** the SHA-256 of every a160bfd file listed above matches.
   - **D1** the Phase 1 counts, recomputed, equal the committed `availability_counts.csv`.
   - **D2** Build 0's A9 on the window (§7 item 4) and the unit-break check. If D2 drops a market and that changes a window's first month or leaves a window month below 6, stop.
   - **D3** A3 on the window: the equal-weight F1 index of T24's 22 window commodity markets against AQR's *Commodities for the Long Run* equal-weight excess return. The AQR file is downloaded from aqr.com, kept privately like Build 0's, and its SHA-256 recorded. **Gate: Pearson ≥ 0.90** over the overlapping window months, as Build 0. This is the only accuracy check available before Databento's 2010 start. A fail means T23 and T24 are recorded as **not run**.
4. **One run each**, T23 and T24, with the T20 control. No variant, re-parameterisation or re-run after seeing results. **If a bug appears after results exist, the run stops and the bug is reported; it is not fixed and re-run** without a new instruction from the owner.
5. **Outputs.**
   - `results/T23-T24_pre2000.md`: pass/fail table first, then the §4.5 context.
   - `results/T23-T24/`: aggregate sleeve monthly returns for the window, `criteria.json`, `performance.csv`, `RUN.json` with commit, times and SHA-256 of code, pre-registration, availability and inputs.
   - `trials.csv`: rows T23 and T24 updated with the outcome; no other row changes.
   - **Private** (licensed data and per-market series, in `em-macro-data/norgate/derived/T23-T24/`, pushed via the server as before): per-market held weights, signals, trades, daily gross by market, the A3/A9 series and the AQR file.
   - `docs/raw_data_archive.md` gets the AQR file's hash.
   - The AWS instance is stopped if the run started it.

## 7. Data caveats for the early years, each with its mechanical rule

1. **Markets missing before 2000.** RB (unleaded gasoline is not in the primary source), 6E and FGBL (entry 2000-03), FOAT and FBTP (none). NG enters 1991-06, B 1989-08, G 1990-01, CL 1984-05, 6M 1996-06. *Rule:* a market enters at its entry month (§2.1 rule 2: 12 months of settlements). No backfill and no proxy: no unleaded gasoline for RB, no Deutsche mark future for EUR, no LIFFE Bund.
2. **Coverage and roll-rule failures in the window.** *Rule:* a market failing the coverage gate, A6, A11 or rule 4 in the window is dropped from that trial for the whole window (§2.1 rule 1, applied to the window). Phase 1 drops Long Gilt from T24. This is in addition to Build 0's drops (PA, 6L, 6Z, FBON), which stand.
3. **Contract-specification changes inside the vendor's history.** Examples: COMEX copper's move to the high-grade contract (late 1980s); feeder cattle's move from physical delivery to cash settlement (mid-1980s); live hogs becoming lean hogs (from the 1997 contracts); changes of contract size (e.g. the British pound future). *Rule:* the vendor splices each into one market, and it is treated as one market (§2.1 rule 2), with no data fix.
   - **T21 and T22 cannot be moved by a splice.** Every return they use is a same-contract daily return (§2.3), and T21's signal is the difference of two chained same-contract series. No return or signal crosses contracts.
   - **The T20 control can be affected.** Its carry compares two contracts, so a carry whose legs straddle a change of price basis (live → lean hogs) is distorted for those months, and for Option B also in the de-seasonalising mean of the next five years. Kept as run (T20 unchanged). In Phase 2, the T20–T22 Build 0 spec-change check (largest ±3-month change of ln(F2/F1)) is reported for these changes, and the number of straddling HE months is reported.
   - **Contract size** enters only the US$3 commission share of c_raw. Its slippage part is ticks × tick / price, independent of size.
4. **Data errors.** Build 0's A9 is run on the window's held series (F1 for all markets; F2 for T21's): gaps (none found in Phase 1), 8-MAD one-day moves that fully reverse, and limit-locked identical settlements. The unit-break check (same-contract one-day moves above 30% that do not reverse) runs too. *Rules:*
   - a reversing spike confirmed by an adjacent contract the same day (Build 0's `resolve_spikes`) is genuine and kept;
   - limit-locked settlements are flagged and kept;
   - **an unresolved spike or a unit break in a held series drops that market from the trial's window**. The data are not edited, and the D2 stop rule of §6 applies.
5. **Notice and last-trade dates.** All window contracts have expired. *Rules:*
   - LTD is the contract's final settlement in the primary source (Build 0 decision 1);
   - FND is Norgate's first notice date, which exists for every contract used in the window in every market whose notice precedes its LTD (§2);
   - markets without an FND use notice = LTD with the Amendment 3 guard. This includes feeder cattle before its move to cash settlement, so a physically delivered GF contract is treated as notice = LTD.
   - Designated calendars are the current ones (T20–T22 §2.1). Where a designated month was not listed (HE's May contract is absent throughout 1980–1999; HO's April, June and August 1979 contracts are absent), the roll rule takes the next listed designated contract, as the code does.
6. **Costs.** The cost model is the a160bfd one, unchanged: US$3 plus 1 or 2 ticks at the current tick values, doubled for the decisive model.
   - **Higher historical costs.** Commissions, spreads and some tick sizes were larger in the 1980s, so the decisive costs probably understate historical costs. *Rule:* no change. The break-even multiple (S3) states how far costs would have to rise to remove the gross return, and the 2× table is reported.
7. **Thin early months.** T23 has 6–9 active markets in 1979-05..1979-12 and T24 in 1979-04..1979-10. They are concentrated in grains and oilseeds and metals (ZS, ZC, ZW, ZM, ZL from 1979-01/03, HG, and for T24 also SI, GC, PL), with sugar and cotton from 1979-11.
   - **The cap.** With fewer than 10 markets, the 10% single-market risk cap is infeasible. On synthetic inputs, `t2022.cap_risk` then ends its 10 iterations with shares above 10% and near-equal risk per market.
   - *Rule:* unchanged code, run as is. Those months are listed in the report, and sub-window results are reported.
8. **FX conversion.** No window instrument needs it: 6B and 6M are quoted in USD per unit, and the Long Gilt is out.
9. **Price limits and thin trading** were more common in the early 1980s. *Rule:* the settlement as published is used, with limit-lock flags reported (item 4).

## 8. Ledger and multiple-testing record

- `trials.csv` gets rows **T23** (group `G20_basis_momentum`) and **T24** (group `G21_diversified_futures_trend`), marked **pending**, in the same commit as this document, with no other row changed. `tests/test_ledger.py`'s row counts are updated to expect them as pending.
- **Distinct trial groups do not increase**, because these are re-tests of T21's and T22's hypotheses on a new sample. The ledger's row count rises from 22 to 24.
- No deflated-Sharpe gate is part of T23 or T24 (C4 needed v1.1). The spec-convention N used by T20–T22 (N = 16) is not incremented. Should a later shadow pre-registration need a DSR, it will count T23 and T24 as two further trials.

## Amendment 1 — 2026-11-06, approved by the owner before the run

Recorded after the pre-registration commit `215b3c4` and the owner's approval, and **before any return, signal, sleeve
or statistic over 1978–1999 was computed** (Phase 2 has not started). The text above is left as written; where this
section and the text above differ, this section governs. Only the pass rule changes.

### A1.1 A gate on the never-computed sub-window (a)

**Reason.** §5 records that the a160bfd run computed, and committed without reporting, sleeve returns for
1991-02..1999-12: 107 of T23's 248 months and 107 of T24's 249. The months before 1991-02 have never been computed by
any run. The added gate requires each sleeve to show a positive return on the never-computed part on its own, so the
already-computed 1991–1999 months cannot decide the result by themselves.

**Change.** Each trial gets one more gate, at decisive costs (`Sleeve.monthly(2.0)`), full window universe:

| trial | # | gate | passes if |
|---|---|---|---|
| T23 | A | mean monthly net return of the stand-alone sleeve over sub-window (a), **1979-05..1991-01** (141 months) | mean > 0 |
| T24 | A | mean monthly net return of the stand-alone sleeve over sub-window (a), **1979-04..1991-01** (142 months) | mean > 0 |

- The gate is a point estimate (no test statistic) and is not part of the Holm family (§4.3), which is unchanged.
- **Decision rule, restated.** A trial passes only if all of its gates hold: **T23: S1 (with Holm), S2, S3 and A;
  T24: S1, S3 and A.**
- Sub-window (a) is the same sleeve run (one run per trial, §6), read over its first months; nothing is re-run.

**Not changed.** Everything else: the windows, S1–S3, the Holm rule and the decision that T24's p-value does not gate
T24 (§4.3), the T20 control, the treatment of T22's S2 (§4.1), the data rules (§7), the Phase 2 procedure (§6) and
the meaning of the result (§1). The ledger rows T23 and T24 are updated to reference this amendment, changing no
other row.

## Amendment 2 — 2026-11-06, decided by the owner after a stopped run, before any gate was evaluated

Recorded after Amendment 1 (`648534b`) and after the first Phase 2 attempt (trial branch, stop record `e9a5b6c`,
`results/T23-T24_pre2000.md` there). That attempt passed checks D0–D3 and then **stopped at the window check**. **No
gate, sleeve return or statistic of T23 or T24 was evaluated, written or printed.** The sleeves had been built in
memory before the check, which was an ordering error in the runner. The text above is left as written; where this
section and the text above differ, this section governs.

### A2.1 T24's window starts in 1979-05

**Reason.** §3 defines each window as running from the first month with at least 6 active instruments (§2.1 rule 3
of T20–T22) to 1999-12. Phase 1 counted a market as active by the entry rule (§2.1 rule 2, `commod_build0.entry_month`),
which counts daily-return rows. It did not apply T22's volatility requirement: `t2022.Mkt.sigma_mop` needs 252
non-missing daily returns.
- **Silver (SI) in 1979-04** has 272 return rows at the decision date but only 234 non-missing returns (38 rows have no
  return because the held contract had no previous settlement). So it has no σ and no T22 signal that month.
- Phase 1 therefore counted SI as active in 1979-04 by mistake. The code has **5** active T22 instruments in 1979-04 and
  **8** in 1979-05.
- **The pre-registered rule itself gives 1979-05.** This amendment corrects the Phase 1 count; it does not change the rule.

**Change.**

| trial | window | months |
|---|---|---|
| T23 | 1979-05 .. 1999-12 (unchanged) | 248 |
| **T24** | **1979-05 .. 1999-12** (was 1979-04 .. 1999-12) | **248** |

- **Sub-window (a)** of Amendment 1 runs from **1979-05 to 1991-01 for both trials** (141 months). Sub-window (b) is
  unchanged (1991-02..1999-12).
- T24's positions start flat in 1979-05.
- Check D3 (A3 against AQR) is evaluated over the overlapping months of T24's window, now 1979-05..1999-12.
- The committed Phase 1 files (`results/T23-T24/availability*`) are left as they were. Check D1 still compares against
  them; the 1979-04 T22 count there (6) is the overcount this amendment corrects.

### A2.2 The window check runs before any sleeve

Before any sleeve, position or P&L is computed, the runner builds each full sleeve's **targets only**
(`t2022.build_targets`, no `Sleeve`) for its window and the month before. It checks that the code's own active count is
at least 6 in every window month and below 6 in the month before. A failure stops the run and is reported, with
nothing further computed.

**Not changed.** Everything else: the rules and code of T21 and T22 at a160bfd, the gates (S1–S3 and A), the Holm rule
(§4.3), the T20 control (on T23's window, unchanged), checks D0–D3, the data rules, the reporting and the meaning of the
result. Phase 2 is run once from here.
