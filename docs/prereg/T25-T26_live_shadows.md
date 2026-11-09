# Pre-registration — trials T25–T26: zero-size live shadows of the T21 basis-momentum and T22 diversified trend sleeves

| item | value |
|---|---|
| trials | **T25**: a zero-size live shadow of the **T21 basis-momentum** sleeve (the sleeve that passed T23). **T26**: a zero-size live shadow of the **T22 diversified futures trend** sleeve (the sleeve that passed T24). Ledger ids `T25` and `T26` in `trials.csv`, the next free ids (the last row is T24). Trial groups: **`G20_basis_momentum`** (T25) and **`G21_diversified_futures_trend`** (T26). They are the same hypotheses and rules as T21/T23 and T22/T24, tested on a new sample (live data), so they share those groups. |
| why | T23–T24 §1: "A pass of T23 or T24 supports a **separate, later pre-registration of a zero-size live shadow** of that sleeve: positions logged monthly, at no capital." Both passed (`results/T23-T24_pre2000.md`). This is that pre-registration. |
| what this is | A **prospective out-of-sample test** on live data. Each sleeve's positions and paper P&L are recorded monthly at zero capital. It is evaluated on a date fixed here (§5.1), with **three pre-registered outcomes** (decayed, confirmed, inconclusive). An inconclusive sleeve gets **one** further fixed period, after which only decayed or confirmed is allowed (§5). |
| family | T25 and T26 are **one family**. The Holm adjustment across the two is in §5.3. |
| rules | T21 and T22 **exactly as run at `a160bfd`**: `docs/prereg/T20-T22_commodity_trials.md` with Amendments 1–4, the Build 0 report and the trial code. That means the same signals, roll rule (35-day buffer, Amendment 3 guard, Amendment 4.4 missing months), volatility estimators, rank weights, 10% single-market risk cap, 10% sleeve target with the 36-month pro-forma scaler, v1.1's T18 band, and **decisive costs (2 × c_raw)**. **No parameter changes of any kind.** The deliberate differences from the backtests are listed in §2.2; none is a parameter. |
| code | The code at `a160bfd`, unchanged. SHA-256: `em_macro/t2022.py` `d54cdc75…3345528a`, `em_macro/commod_data.py` `e5ffe76b…8f49cb25`, `em_macro/commod_build0.py` `2c58f7e2…6e1951c`, `em_macro/t18_rebal.py` `dda6456d…0f96c43`, `em_macro/systematic.py` `1eb4cf6b…50be66`, `em_macro/systematic_v11.py` `b3c4404e…885952`, `em_macro/t01.py` `bc52b3e0…2432b2b` (identical at `a160bfd`, at T23–T24's run and at this branch's base `9a05493`). New code is limited to the data adapter, the live operation and the reporting (§8). |
| data | **Warm-up:** the Norgate 2026-11 snapshots the a160bfd run used (private repo `EthanC100/em-macro-data`, `norgate/2026-11_futures/` manifest `1d6657e6…0f5e60`, `2026-11_financials/` `91d1d9e2…5aa5129`, `2026-11_metadata/metadata.csv` `2efd5eaa…cad9d`). **Live:** Databento GLBX.MDP3 final daily settlements (`ledger/settlements.py`), for dates after the snapshot's last settlement date. All prices are stored only in em-macro-data. |
| branch | `prereg/shadows`: this document, the availability check (§3.2) and its output, and the pending ledger rows. Phase 2 (the build, §8) goes on `trial/T25-T26-shadows`, branched from this commit, **only after the owner replies "approved"**. |
| written | 2026-11-06. **No return, signal, position, sleeve or statistic of the restricted (CME-group) universe was computed in writing it, for any period.** The only data step was the availability check of §3.2: counts of final-settlement days per contract, and no price was summarised, printed or kept. |
| changes nothing else | No v1.0, v1.1, T20–T22 or T23–T24 file is modified (pre-registrations, Build 0 report, results, trial code). v1.0 and v1.1 run as before. |

## 1. Hypotheses, and what each outcome means

| trial | hypothesis (restated from T21/T23 and T22/T24) | prior evidence |
|---|---|---|
| T25 | The T21 basis-momentum sleeve's live net return after decisive costs is not below what its backtests predict (breadth-adjusted), it is positive, and adding the sleeve to v1.1 at the 25% risk budget does not worsen v1.1's live Sharpe ratio or drawdown beyond the T20–T22 non-inferiority margins. | Boons and Porras Prado (2019). T21, 2000-01..2026-09: Newey–West t 2.05, net Sharpe 0.40, break-even 5.5. It failed only C1 and C2 against v1.1. T23, 1979-05..1999-12: NW t 2.29, Sharpe 0.49, break-even 4.6, all gates passed. |
| T26 | The same claim for the T22 diversified trend sleeve: live net return after decisive costs not below its breadth-adjusted backtest prediction and positive, and no damage to v1.1 beyond the non-inferiority margins. | MOP (2012), HOP (2017). T22: net Sharpe 0.40 (2000–2019) and 0.24 (2020-01..2026-09), break-even 6.6. It failed only C1 and C2. T24, 1979-05..1999-12: Sharpe 0.68, break-even 7.1, all gates passed. |

**What each outcome means (fixed now; §5 defines them).**
- **Decayed:** the live mean return is significantly below what the backtest predicts. **The sleeve is closed.** No
  further variant of it is pre-registered in this programme: no other parameters, universe, horizon, data source or
  evaluation date.
- **Confirmed:** the live mean is positive and not significantly below the backtest's prediction, and adding the
  sleeve to v1.1 stays within the non-inferiority margins. **The sleeve becomes eligible for a separate, later
  pre-registration of v1.2** (a candidate version: v1.1 plus that sleeve, or both). Confirmation does **not** adopt
  anything, add the sleeve to v1.1, or change any capital. It is weak evidence on its own: with no true effect a
  sleeve is confirmed about 46–48% of the time (§5.4). The v1.2 pre-registration must carry its own test.
- **Inconclusive** (first evaluation only): neither. **The shadow continues for one further fixed period of 36
  months** (§5.1). At the second evaluation only decayed or confirmed is possible: inconclusive then **counts as
  decayed**, and the sleeve is closed.
- **"Not evaluable" (§7.6)** also closes the sleeve for this programme. A new attempt would need a new
  pre-registration with a new trial id, stating that this one was not evaluable.
- **No outcome changes v1.0 or v1.1, or re-opens any earlier trial.** The outcomes of T20–T24 in `trials.csv` stand
  as recorded. The 12-month paper stage of the T20–T22 pre-registration (§4.4) is not started, because neither T21
  nor T22 passed it. This shadow is not that stage: it has zero capital and no integer contracts.

## 2. Rules

### 2.1 Exactly as run at a160bfd

Each shadow is built with the a160bfd functions, called unchanged:
- **markets:** `t2022.Mkt`;
- **signals:** `signal_t21`, or `signal_t22` with `Mkt.sigma_mop`;
- **σ:** `Mkt.sigma_blend` for T21;
- **targets:** `build_targets(..., kind, months)`, with the 6-active minimum, rank weights or MOP equal weights, and the 10% cap via `cap_risk`;
- **sleeve:** `Sleeve`, which applies `scale_to_target` (the 36-month pro-forma 10% scaler), `T18.apply_rules` (v1.1's band), and the daily same-contract P&L with c_raw costs and rolls as two trades;
- **monthly net returns:** `Sleeve.monthly(2.0)` at decisive costs and `monthly(4.0)` for the 2× sensitivity;
- **combination with v1.1:** `combine` (T20–T22 §2.6: 25% risk budget, the mix rescaled to 10%, the 6× cap);
- **statistics:** `nw_tstat`, `sr`, `stats` and `holm`.

No a160bfd function is edited or reimplemented.

### 2.2 Deliberate differences from the backtests (none is a parameter)

| # | difference | why | effect |
|---|---|---|---|
| D1 | **Universe restricted to markets with Databento GLBX.MDP3 daily settlements** (CME, CBOT, NYMEX, COMEX, CME FX). **Excluded:** the ICE markets (Brent B, gasoil G, sugar SB, coffee KC, cocoa CC, cotton CT), all non-CME bonds (Euro-Bund FGBL, Euro-OAT FOAT, Euro-BTP FBTP on Eurex; Long Gilt R on ICE). | The live marks come from the one licensed source the programme has for daily settlements, with a quoted cost and a daily cap. The ICE and Eurex data would need separate licences. | The exchange rule alone leaves 14 markets for T21 and 20 instruments for T22. With the availability rule (§3.2), which also drops livestock markets, the universes are **11** (T25) and **18** (T26). Breadth falls: at equal per-market quality the expected Sharpe falls by about √(N/N₀) (§5.2). The sector mix changes: T25 keeps four energy markets, copper and six grains and oilseeds, and has no softs and no livestock; T26 loses its bonds, all softs, Brent, gasoil, feeder cattle and lean hogs. |
| D2 | **Data:** warm-up history from the a160bfd Norgate snapshot; live dates from Databento final settlements (stat_type 3, final flag). | Norgate is not updated live in this programme. Databento agrees with Norgate within one tick on ≥ 99.97% of days in every CME-group market (Build 0 A5). | One splice per market at the snapshot's last date, checked before go-live (§8, P2). |
| D3 | **Both sleeves start flat** in the first live month: `build_targets` is called with `months` = the live months only. | So no sleeve return, position or T18 band path is ever computed for the restricted universe before live data exist. | The first month's trades are full entries, charged at decisive costs, as in the backtests' first months (T23–T24 §3). |
| D4 | **Zero capital: fractional weights**, with no integer contracts and no live rounding rule (T20–T22 §4.4). | Zero size, as T23–T24 §1 specifies. | None on returns: the backtests' decisive runs used fractional weights. |
| D5 | **Outcomes instead of gates.** The backtests' sleeve gates (S1–S3, A) are replaced by the three outcomes of §5, built from a decay test against the backtest's prediction and the non-inferiority margins against v1.1. T21's S2 (alpha against the T20 carry sleeve) is not used: T20 failed and runs nowhere live. T22's S2 (carry-crisis correlation) and the break-even multiple are reported, not decisive (§5.6). | §5. | §5. |

## 3. Universe

### 3.1 Rule (fixed before the check ran)

A market is in a shadow's universe if all of the following hold:
1. **It is in that sleeve's a160bfd universe:** T21's 20 markets, or the 30 instruments of the a160bfd T22 run. Build 0's drops (PA, 6L, 6Z, FBON) stand. No market is added, so 6L and 6Z, which do trade on Globex, stay out.
2. **Its exchange is on Databento GLBX.MDP3:** CME, CBOT, NYMEX or COMEX, including CME FX.
3. **It passes the counts-only availability check (§3.2):** every contract the roll rule would hold at the twelve rebalances December 2026..November 2027 resolves on Databento and has a final settlement on ≥ 95% of the market's settlement days in the check window. "Every contract" means F1 and F2 for T21, which needs both nearby series, and F1 for T22. The 95% is Build 0's coverage threshold (T20–T22 §2.1 rule 1).

### 3.2 Availability check (run 2026-11-06; counts and dates only)

`python -m em_macro.t2526_avail run` (this commit):
- **Contracts:** it lists F1 and F2 at each of the twelve rebalances December 2026..November 2027 under the a160bfd roll rule, using `commod_data`'s exchange LTD/FND rules on a weekday calendar without US holidays or Good Friday.
- **Request:** it resolves each contract's Globex symbol and requests the `statistics` schema over 2026-08-03 to the dataset's available end, one request per market. Every request is quoted first, and the check refuses to run if the quotes total more than US$0.50. A first attempt as a single request timed out after 10 minutes, having downloaded and recorded nothing.
- **Counts:** it counts, per contract, the days with a **final** settlement.
- **No prices:** settlement values were read only to test that a final settlement exists. None was kept, printed or written.

The full output is in `results/T25-T26/availability.md`, `availability_counts.csv` and `availability.json`.

Run 2026-11-06 22:27 UTC: 167 contracts over 2026-08-03 .. 2026-11-06 (68 settlement days), one request per
market, quoted at US$0.1371 in total.

| market | exchange | F1 / F2 at the Dec 2026 rebalance | lowest F1 share | lowest F2 share | T25 (T21) | T26 (T22) |
|---|---|---|---|---|---|---|
| CL RB HO NG | NYMEX | Feb / Mar 2027 | 100% | 100% | yes | yes |
| HG | COMEX | Mar / May 2027 | 100% | 100% | yes | yes |
| ZC ZS ZW KE ZM ZL | CBOT | Mar / May 2027 | 100% | 100% | yes | yes |
| LE | CME | Feb / Apr 2027 | 100% | 72.1% | **no** (F2 below 95%) | yes (needs F1 only) |
| GF | CME | Jan / Mar 2027 | 0% | 0% | **no** | **no** |
| HE | CME | Feb / Apr 2027 | 87.0% | 26.1% | **no** | **no** |
| GC SI PL | COMEX, NYMEX | GC Feb / Apr, SI Mar / May, PL Apr / Jul 2027 | 100% | 100% | — | yes |
| 6E 6B | CME | Mar / Jun 2027 | 100% | 100% | — | yes |
| 6M | CME | Mar / Jun 2027 | 100% | 86.8% | — | yes (needs F1 only) |
| B G SB KC CC CT | ICE | — | — | — | no (§3.1 rule 2) | no |
| FGBL FOAT FBTP / R | Eurex / ICE | — | — | — | — | no (§3.1 rule 2) |

The shares are the lowest over the F1 (or F2) contracts of all twelve rebalances.

**Universes (fixed by the rule above):**
- **T25: 11 markets:** CL RB HO NG HG ZC ZS ZW KE ZM ZL.
- **T26: 18 instruments:** CL RB HO NG HG ZC ZS ZW KE ZM ZL LE GC SI PL 6E 6B 6M.

**Read with care.**
- **Why the livestock shares are low is not diagnosed.** The check counts days only. LE's and HE's lowest shares
  are in their later contracts, which may simply have been listed during the window, so the shortfall may not be
  a data gap.
- **GF has no final settlement for any of its contracts**, and two of them (Jan and Mar 2028) did not resolve.
  The cause (symbology, or how Databento flags feeder cattle's settlements) was not investigated, because looking
  further could only lead to changing the rule after seeing the result.
- **The rule is applied as fixed.** All three livestock markets leave T25, and GF and HE leave T26. Under §3.3 they
  never re-enter.
- **What this costs:** the universes shrink further than §2.2 D1's exchange rule alone (14 and 20), and the
  breadth adjustment of §5.2 uses the actual counts, 11 and 18.

### 3.3 Universe changes after go-live

The universe is fixed at go-live and changes only mechanically, under §7. No market is added later.

## 4. Operation

1. **Schedule.** Computed monthly with the v1.0/v1.1 rebalance on the **3rd**, starting with **the first v1.0/v1.1 rebalance on or after the owner's approval at which the Phase 2 build and the pre-live checks (§8) have passed**. If that is the 3 December 2026 rebalance, the first live month is **2026-12**, the same as v1.1's live start.
   - **Execution and decision dates (T20–T22 §2.3):** for each market, the execution date is its first settlement on or after the 3rd, and the decision date t is its last settlement before that.
2. **When it runs.** The rebalance is computed on the first `ledger-daily` run on or after the 3rd at which every universe market's decision-date final settlement is stored.
   - Databento's historical data runs a few hours behind, so this is normally the 09:22 UTC run on the 3rd.
   - The code uses only settlements up to t for signals and targets, so computing later changes nothing.
   - Positions take effect at the execution-date settlement.
   - Every run then marks the shadows daily from the stored settlements, and the P&L is recomputed from the first live month on every run, as v1.0's update does.
3. **Zero capital.** Weights are fractions of a notional sleeve capital at the 10% target. Nothing is traded, and no fund, book or limit is affected.
4. **Where prices live.**
   - Every settlement (Norgate warm-up and Databento live), every per-market daily P&L, signal, σ and trade with a price is stored **only in em-macro-data** (`shadows/T25/`, `shadows/T26/`, and `ledger/futures_settlements.csv`).
   - This repository publishes, per shadow:
     - `results/shadows/<id>/positions.csv`: month, market, contract code, target and held weight;
     - `monthly.csv`: gross, 1× cost, and net at decisive and 2× costs, in %;
     - `index.csv`: daily cumulative net % at decisive costs;
     - `status.json`.
   - **No price, settlement, notional in currency or contract count is published.**
5. **Spend.** Databento requests go through `ledger/settlements.py`.
   - Every request is quoted first and refused if it would take the day's (UTC) spend above **US$1.00**. The cap is shared with my futures and options marks and Janus's.
   - The shadows' contract months (F1 and F2 for T21; F1 for T22; the next contracts at each roll) are added to the daily request.
   - A refused or failed request is an outage (§7.3).
6. **Ledger.** The Algorithm page gets a **"Shadows"** section. For each shadow it shows:
   - the live index (net, decisive costs), the months live out of 60, and the current held weights by market, with direction and contract;
   - the last rebalance, and outages and dropped markets;
   - the evaluation dates with the outcome rules, labelled "evaluated on <date> (and, if inconclusive, on <date>); nothing before then is a result";
   - "zero size, paper; not part of v1.0, v1.1 or the fund".

   The shadows are not part of the Horizons fund and never feed any book.
7. **No early stop, no interim decision** (§5.5).

## 5. Evaluation: three outcomes at a date fixed now, with one fixed extension

### 5.1 Windows and dates

- **First evaluation:** the first **60 live months**, M1..M60. If M1 = 2026-12, that is **2026-12 .. 2031-11**,
  evaluated on **15 December 2031**. By then v1.1's November 2031 month is booked (3 December) and the shadows'
  November settlements are stored.
- **Second evaluation (inconclusive sleeves only):** **36 further months**, so the whole record M1..M96. If M1 =
  2026-12, that is **2026-12 .. 2034-11**, evaluated on **15 December 2034**. The second evaluation uses all 96
  months, not the 36 alone.
- If M1 is later, both windows run from M1 and each evaluation is on the 15th of the month after its last month.
  M1 and both dates are written in the go-live record (§8) at the first live rebalance, and never changed.
- **Why 60 + 36 months** (before any live data):
  - 60 months is the programme's minimum live record for judging a mechanical strategy: the Ledger's
    90%-confidence track-record length is 55 months for v1.0 (`MIN_TRACK_RECORD_YEARS` = 4.6), rounded up to whole
    years.
  - **36 more months (8 years in all) is a judgement about how long the programme will wait, not a power optimum.**
    The length of the extension hardly changes how well the outcomes separate a real effect from none. A longer
    extension raises the final confirmation rate under the backtest effect and under zero effect almost equally
    (Monte Carlo as §5.4, 6,000 paths, `results/T25-T26/power_mc_extension.py`):

    | extension | total | final confirmed, backtest effect (T25 / T26) | final confirmed, zero effect (T25 / T26) |
    |---|---|---|---|
    | 24 months | 7 years | 72% / 76% | 46% / 46% |
    | **36 months** | **8 years** | **74% / 79%** | **46% / 48%** |
    | 60 months | 10 years | 78% / 82% | 49% / 50% |
    | 96 months | 13 years | 82% / 85% | 50% / 52% |

    36 months keeps the whole test within 8 years, and the programme can still act on the answer.

### 5.2 Quantities (decisive costs; the full shadow universe; months M1..M_T, T = 60 or 96)

| symbol | definition |
|---|---|
| r_t | the shadow's monthly net return at decisive costs, `Sleeve.monthly(2.0)` |
| m̂, ŝ | the sample mean and standard deviation (ddof 1) of r_t over the window |
| SR_pred | the **backtest prediction**, fixed now: the pooled decisive Sharpe ratio of the sleeve's two backtests, months-weighted (T21 2000-01..2026-09 and T23 1979-05..1999-12: **0.4346**; T22 2000-01..2019-12 and 2020-01..2026-09 with T24 1979-05..1999-12: **0.4998**), times **√(N / N₀)** for the restricted universe (N = the number of universe markets at go-live; N₀ = 20 for T21, 30 for T22). With the §3.2 universes (N = 11 and 18): **0.322** (T25) and **0.387** (T26). If P1 (§8) removes a market before go-live, N is the count at go-live, recorded in the go-live record. |
| m₀ | the predicted monthly mean at the shadow's own realised volatility: m₀ = SR_pred / √12 × ŝ. The shadow targets 10% volatility, as did the backtests, so the prediction is stated in Sharpe units and scaled by the realised volatility. |
| t_d | the decay statistic: t_d = (m̂ − m₀) / se_NW, with se_NW the Newey–West (6 lags) standard error of the mean (`t2022.nw_tstat`'s estimator) |
| p_d | one-sided decay p-value: p_d = Φ(t_d) (small when the live mean is far below the prediction) |
| ΔSR | SR(v1.1 + shadow) − SR(v1.1), the combined book from `t2022.combine` (v1.1's held weights from its monthly run, its own cost model and lags; the shadow's legs at decisive costs; 25% risk budget), against v1.1's live record over the same months |
| MaxDD | maximum drawdown of the compounded monthly index |

### 5.3 The three outcomes, and the correction across the two sleeves

At each evaluation, for the sleeves evaluated there (both at the first; the inconclusive ones at the second):

1. **Decayed** if the **Holm-adjusted** p_d < **0.05** (one-sided), adjusting across the sleeves evaluated at
   that date:

   ```
   two sleeves: order p_(1) ≤ p_(2);  p_adj,(1) = min(1, 2 p_(1));  p_adj,(2) = max(p_adj,(1), p_(2))
   one sleeve:  p_adj = p_d
   ```

2. **Confirmed** if not decayed **and** all of:
   - **positive:** m̂ > 0;
   - **Sharpe non-inferiority** (T20–T22 Amendments 1–2 margin): ΔSR ≥ −0.05, point estimate;
   - **drawdown non-inferiority** (T20–T22 C3 margin): |MaxDD(v1.1 + shadow)| ≤ 1.10 × |MaxDD(v1.1)|.

   "Consistent with the backtest" means the decay test does not reject.
3. **Inconclusive** otherwise, at the first evaluation only. At the second evaluation, a sleeve that is neither
   decayed nor confirmed **counts as decayed**.

Raw and Holm-adjusted p_d, t_d, m̂, m₀, ΔSR and both drawdowns are reported at each evaluation. The positive-mean and
non-inferiority conditions are point estimates and are not adjusted, as T20–T22 §5 left its point-estimate gates.

### 5.4 Probabilities of each outcome (Monte Carlo, before any live data)

**Method.** 8,000 paths per case, seed 20261106 (`results/T25-T26/power_mc.py`; the extension table of §5.1 from `power_mc_extension.py`):
- monthly returns of v1.1 and the two shadows, normal, each at 10% annual volatility, over 96 months;
- correlations from the 2020-01..2026-09 backtest diagnostics: T21–v1.1 0.08, T22–v1.1 0.05, T21–T22 0.20;
- v1.1's Sharpe ratio at its 2006–2026 decisive value, 0.71;
- the outcome rules applied exactly as in §5.3 at 60 months, and at 96 months to the paths inconclusive at 60, with
  Holm across the sleeves evaluated at each date. A plain standard error stands in for Newey–West on independent
  normal returns. The combined book is the 0.75/0.25 return mix rescaled to v1.1's volatility.

Three cases for the true Sharpe ratio: the **backtest effect** (SR_pred: 0.322 and 0.387), **half** of it, and
**zero**. Monte Carlo error is about ±0.5 percentage points.

| true effect | sleeve | at 5 years: decayed | confirmed | inconclusive | at 8 years: confirmed | inconclusive → decayed | **final: confirmed** | **final: decayed** |
|---|---|---|---|---|---|---|---|---|
| backtest effect | T25 | 2.6% | 62.0% | 35.3% | 13.0% | 19.7% | **75.0%** | **25.0%** |
| backtest effect | T26 | 2.4% | 66.7% | 31.0% | 12.7% | 15.6% | **79.4%** | **20.6%** |
| half | T25 | 6.5% | 47.8% | 45.7% | 12.9% | 27.6% | 60.6% | 39.4% |
| half | T26 | 6.6% | 52.3% | 41.0% | 13.1% | 22.3% | 65.4% | 34.6% |
| **zero** | T25 | 12.2% | 36.6% | 51.1% | 9.6% | 31.2% | **46.3%** | **53.7%** |
| **zero** | T26 | 15.7% | 37.1% | 47.2% | 10.8% | 24.8% | **47.9%** | **52.1%** |

"Final: decayed" includes decayed at either evaluation and inconclusive-then-decayed at 8 years.

**What this means, stated plainly.**
- **If the backtest effect is real**, each sleeve is confirmed about 75–79% of the time, and wrongly closed about
  21–25% of the time. Most of those wrong closures (16–20 points) come from "inconclusive at 8 years counts as
  decayed", not from the decay test, which rejects a real effect only about 2–3% of the time at 5 years.
- **If the true effect is zero**, each sleeve is still **confirmed about 46–48% of the time**. Confirmation asks
  only for a positive mean that is not significantly below the prediction. A sleeve with no edge has a positive
  mean about half the time, and the decay test has little power against a prediction of Sharpe 0.32–0.39. So
  **confirmation is weak evidence that the effect exists.** It means only "not shown to have decayed, positive,
  and harmless to v1.1", and it gives eligibility for a v1.2 pre-registration that must carry its own test.
- **A closure is also weak evidence that the effect is gone:** with no effect, a sleeve is closed about 52–54% of
  the time. Neither outcome is decisive at any horizon the programme can wait for. A Sharpe ratio near 0.4 needs
  about 20 years for an expected t-statistic of 2.
- These figures assume normal, independent monthly returns. Fat tails and serial correlation would make every test
  less decisive.

### 5.5 No early stop, no interim decision

The live record is visible as it accrues. No interim look stops a shadow, for success or failure, or changes any
outcome rule, prediction, date or margin. The only decisions are at the dates of §5.1.

### 5.6 Reported, not decisive

None of these can change an outcome:
- the 2× cost sensitivity (`monthly(4.0)`);
- the break-even cost multiple m*;
- the Newey–West t of the mean (the backtests' S1 statistic) and the live Sharpe ratio, with confidence intervals;
- by year;
- each shadow's P&L by sector;
- the correlations between the two shadows, with v1.1 and with v1.0's live carry-only sleeve;
- T22's S2 analogue: the correlation with v1.0's carry-only sleeve (`systematic.run(inp, ["carry"])`, as T01 and
  T22) in carry's worst 10% of live months;
- the superiority version of the combined test (ΔSR > 0);
- the monthly count of active markets, and the outage log (§7).

## 6. Disclosure: everything already known about these sleeves

1. **Results, public.**
   - T21 and T22 on their full a160bfd universes, 2000-01..2026-09: `results/T20-T22_commodity_trials.md`. Every sleeve statistic, the combined books with v1.1, the correlations, v1.1's worst months, and T22's P&L by asset class (2000–2026 gross: commodities 3.30%, bonds 0.98%, currencies 0.33% a year).
   - The same sleeves on 1979-05..1999-12: `results/T23-T24_pre2000.md`. All gates, sub-windows, half universes, by-year returns, and T22's P&L by asset class (commodities 7.83%, currencies 0.58% a year gross).
2. **Per-market outputs, private.** em-macro-data holds per-market held weights, signals, trades and daily gross P&L of both runs for their full universes (`norgate/derived/trials/`, `norgate/derived/T23-T24/`).
   - An approximate history for the restricted universe could be assembled from them. **It has not been, by this session or any recorded run**, and it would not equal the restricted-universe sleeve anyway, because T21's ranks and T22's equal weights depend on the whole universe.
   - Computing any restricted-universe history before the evaluation date is forbidden by this document. It would be a new trial.
3. **Data accuracy.** Build 0 A5: Databento GLBX.MDP3 agrees with Norgate within one tick on ≥ 99.97% of days in each of the 18 CME-group commodity markets, 2010-06..2026-10.
4. **Databento data seen in this programme.** Since 2026-11-06 the Ledger's private store holds final settlements for the front and next contracts of WTI, BZ, NG, HO, RB, GC, SI, HG, ZC, ZS and ZW from 2026-10-27. It feeds the Me book's futures and options marks and Janus's universe.
   - The author of this document saw, in passing, the BZ March 2027 final settlements for 2–5 November 2026, and one day of eleven contracts while checking price units.
   - No signal, σ, rank or sleeve was computed from any of them.
5. **This pre-registration's data step:** the counts of §3.2 only.
6. **Code history.** `em_macro/commod_databento.py` gained a `final_settlements` helper on 2026-11-06 (after a160bfd). It is not one of the hashed trial files, and the A5 code path is unchanged. `ledger/settlements.py` (2026-11-06) is the Ledger's settlement store, and it is reused here.
7. **The author's knowledge.** The author knows all of the above, the published literature, and current market conditions (late 2026). The shadows are mechanical. No discretion enters any position, and no rule depends on a market view.
8. **The literature** (T23–T24 §5) uses samples ending 2009–2016. Live data from December 2026 are out of sample for this build **and** for the published hypotheses.

## 7. Mechanical handling of missing data, contract changes and outages

1. **A missing settlement for a held contract** (Databento has no final for a trading day) carries the last settlement forward. That day's return is zero, the gap's return is realised on the next available settlement, and the day is flagged (T20–T22 §2.1 rule 4). This follows the a160bfd daily P&L code.
2. **A missing settlement on a decision date** (F1, or F2 for T21) makes that market **missing for the month** (Amendment 4.4): weight 0, with the cross-sectional rank over the other markets.
   - The rebalance waits for decision-date settlements until the 10th of the month. After that, any market still missing is treated this way.
   - If fewer than 6 markets are active, the sleeve holds nothing that month (§2.1 rule 3).
3. **Outages.** A day on which Databento cannot be reached, the spend cap refuses the request, or the store is unavailable is treated as missing settlements (items 1–2). The settlements are fetched on a later run and the P&L is recomputed, with nothing edited by hand.
4. **A held contract without a final settlement for more than 20 consecutive trading days:**
   - that market is dropped from the shadow from the next rebalance, exiting at its last settlement with 3× the one-way cost (§2.1 rule 5);
   - the drop is recorded in the outage log and in `status.json`;
   - it never re-enters.
5. **Contract changes.**
   - **A designated contract month that is not listed:** the roll rule takes the next listed designated contract, as the a160bfd code does.
   - **A change of tick size, multiplier, grade or delivery terms under the same Globex root:** treated as the same market (§2.1 rule 2). The cost model keeps the a160bfd tick and multiplier values, and the difference is logged as a data fact. Returns are same-contract, so a change cannot move them.
   - **A market delisted, or moved to a new root:** it exits at its last settlement with 3× the one-way cost (§2.1 rule 5), and the successor is not added.
   - **Notice and last-trade dates:**
     - for contracts in the Norgate metadata, Norgate's dates;
     - for contracts listed later, `commod_data`'s exchange rules, with the Amendment 3 guard for notice = LTD markets. If the exchange publishes a different date before the contract is held, the exchange's date applies and is logged.
6. **Not evaluable.** At an evaluation date, a shadow is **not evaluable** if:
   - fewer than 90% of the window's months (54 of 60; 87 of 96 at the second evaluation) had a computed rebalance
     with at least 6 active markets; or
   - its record was interrupted for more than 3 consecutive months.

   It is then neither decayed nor confirmed, and §1 applies.
7. **Bugs.** A bug found before the evaluation date is fixed only if the fix restores what this document and the a160bfd code specify. The fix, its commit and the affected months are recorded. The whole live path is then recomputed from M1, as every run does, so the record stays consistent. No outcome rule, prediction, margin or date changes.
8. **Late runs.** If the rebalance is computed after the 3rd (item 2, or a delayed run), the decision still uses only settlements up to t. The execution date is the market's first settlement on or after the 3rd, so a late computation never changes the positions.

## 8. Phase 2 (only after the owner replies "approved")

1. **Branch** `trial/T25-T26-shadows` from this commit.
2. **New code, data and operation only:**
   - `em_macro/t2526.py`, which:
     - presents the Norgate warm-up and the Databento live settlements to the unchanged `commod_data.MarketData` (one splice per contract at the snapshot's last date);
     - builds `t2022.Mkt`, the signals, `build_targets` with `months` = live months, and `Sleeve`;
     - writes the private and public files of §4.4;
     - evaluates at the dates of §5.1, applying §5.3 exactly.
   - The Ledger "Shadows" section, and the `ledger-daily` step.
   - `tests/test_t2526.py`, **tested on synthetic data only**: the splice, start-flat, the missing-data rules of §7, the three outcomes and Holm at their boundaries (one and two sleeves), inconclusive-to-decayed at the second evaluation, and no price in any public file.
3. **Pre-live checks before the first live rebalance.** Each is recorded in `results/shadows/GO_LIVE.json`. A failure moves go-live to the next rebalance.
   - **P0:** the SHA-256 of every a160bfd file listed above matches.
   - **P1:** the §3.2 counts, recomputed on the then-current window, still qualify every universe market. A market that no longer qualifies is excluded under §3.1, before go-live.
   - **P2: splice agreement.** For every universe market, the Databento final settlements of the held F1 (and F2 for T21) agree with the Norgate snapshot within one tick on ≥ 99% of their common days (Build 0 A5's tolerance), counts only. A failing market is excluded before go-live.
   - **P3:** every universe market has σ and a signal available at the first decision date. Otherwise §7.2 applies that month.
   - **P4:** a dry rebalance on the first decision date prints only the active count per sleeve, which must be ≥ 6, and no weight.
4. **Go-live record.** At the first live rebalance: M1, both evaluation dates, the universe, N for SR_pred (§5.2), the code commit and the hashes are recorded. This fixes every date and prediction of §5.

## 9. Ledger and multiple-testing record

- `trials.csv` gets rows **T25** (group `G20_basis_momentum`) and **T26** (group `G21_diversified_futures_trend`), marked **pending**, in this commit, with no other row changed. The ledger's row count rises from 24 to 26, and the distinct trial groups do not increase.
- `tests/test_ledger.py` is updated to expect the two rows as pending. The app's evidence page lists the shadows as pre-registered and pending.
- No deflated-Sharpe gate is part of T25–T26, so the spec-convention N (16) is not incremented. A later v1.2 pre-registration that uses a DSR will count T23, T24, T25 and T26.

## Amendment 1 — 2026-11-06, decided by the owner with the approval, before Phase 2

Recorded after the owner replied "approved" to this document (commit `208edd1`), and **before any Phase 2 code was
written or any shadow position, signal or return was computed**. The text above is left as written; where this
section and the text above differ, this section governs.

### A1.1 "Confirmed" adds nothing by itself

A confirmation (§1, §5.3) makes a sleeve eligible for a v1.2 pre-registration and nothing more.
- **The v1.2 pre-registration's combination test must be judged on live data after the evaluation date that
  produced the confirmation:** from the month after M60 (or after M96 for a sleeve confirmed at the second
  evaluation). It must not use the shadow period that produced the confirmation.
- So that such data exist, **a confirmed shadow keeps running at zero size, unchanged,** after its evaluation date.
  Its later months are recorded like the earlier ones. No new decision is taken from them under this document; the
  v1.2 pre-registration fixes its own window, test and dates before it uses them.
- A decayed sleeve stops at its evaluation date. Its positions are closed on paper at the next rebalance.

### A1.2 No result depends on Norgate data (licence ends about 5 May 2027)

All Norgate data must be deleted when the subscription ends, about 5 May 2027. The shadows therefore never depend
on Norgate:
1. **Warm-up from Databento, not Norgate.** §2.2 D2 and §8's splice are replaced. Before go-live, the history every
   universe market needs is fetched from **Databento GLBX.MDP3** (`statistics` schema, final settlements, as for
   the live data), for every designated contract of the market whose life overlaps the history window. The window
   starts on **1 January 2023**, at least 40 months before the first decision date. That covers the 36-month
   pro-forma scaler, T21's 12 holding months, the 252 daily returns of every σ, and the entry rule's 12 months of
   settlements. If go-live slips, the window still starts at least 40 months before M1's decision date.
   - The settlements are written in the per-contract layout the unchanged a160bfd code reads (`commod_data.
     MarketData`), in the price units Norgate used, so tick values and multipliers keep their a160bfd meaning. The
     unit factor of each market is the power of ten that the check below measures, recorded per market.
   - **Contract dates:** first notice and last trade dates come from `commod_data`'s exchange rules, with the
     Amendment 3 guard, not from Norgate's metadata.
2. **Cost:** the one-off history request is quoted first and refused above **US$20.00** in total. It does not
   count against the US$1 daily cap of the live fetches.
3. **Check against the Norgate snapshot, once, before go-live** (replacing §8 P2):
   - **Prices:** for each universe market, every contract present in both sources, on their common days
     2023-01-01 .. the snapshot's last date: the Databento final settlement, in Norgate units, equals the Norgate
     close within **one tick** on **at least 99%** of common days (Build 0 A5's tolerance). Counts only are
     reported.
   - **Contract chain:** the F1 and F2 chosen by the roll rule at every month of the history window, with the
     exchange-rule dates, equal those chosen with Norgate's dates. Otherwise the history would differ from what
     Norgate gives.
   - **A market that fails either check is excluded under §3.1 before go-live.** N, and so SR_pred (§5.2), is the
     count at go-live, as §5.2 already says.
4. **From go-live, the shadow code reads only the Databento history and the live Databento settlements.** The
   Norgate snapshot is opened only by the one-off check, which runs before go-live and, in any case, before
   5 May 2027. Its result (counts only) is committed in `results/shadows/prelive.json`.
5. **If the check cannot run before 5 May 2027**, no market can qualify. The shadows do not go live and are recorded
   as not evaluable (§7.6).

**Not changed.** Everything else: the rules and code of T21 and T22 at a160bfd, the universe rule and its check, the
three outcomes, the prediction, the margins, Holm, the dates, the operation and the disclosures. The ledger rows T25
and T26 are updated to reference this amendment, changing no other row.

## Amendment 2 — 2026-11-09, decided by the owner before go-live is confirmed

**The rule, fixed by the owner before the investigation.**
- If an exclusion's cause is an **implementation error** (the check not testing what A1.2 specifies, e.g. a date or
  listing-convention mismatch in the comparison code), the code is fixed, recorded here with the diagnosis, and the
  check is rerun **once** for all 18 markets. Whatever that single rerun says is final.
- If the chains genuinely differ, the exclusions stand.
- No threshold or definition of the check changes.

### Diagnosis (counts and dates only)

The first check (`results/shadows/prelive.json`, 9 Nov 2026) excluded CL, LE, 6E, 6B and 6M for "F1/F2 chain
differs". All five passed the price test: 100% of common days within one tick, unit factor 1.

**Common cause, in every market.**
- On a contract's last trading day, Databento GLBX.MDP3 carries only the *preliminary* settlement; the final flag
  is never set. Checked directly: CLH4 on 20 Feb 2024 and 6EM5 on 16 Jun 2025 each have one settlement record,
  with stat_flags 2 and no final bit.
- The history stores final settlements only, so every expired contract's Databento data ends **one trading day
  before** its exchange-rule last trade date. This holds in 45/45 CL, 23/23 LE, 15/15 each of 6E, 6B and 6M, and
  45/45 in RB, which passed.
- The unchanged a160bfd contract table dates an expired contract's last trade to its **last data row**.
- So on the Databento side, every expired contract's last trade date was one day early: neither the exchange rule
  nor Norgate's date. Norgate's last row equals the exchange-rule date in 100% of these contracts.
- A1.2 specifies the Databento-side chain **with the exchange-rule dates**. The check therefore compared the wrong
  dates: an implementation error.

**Per market.**

| market | months differing | diagnosis |
|---|---|---|
| CL | 2023-05, 2024-01, 2025-12 | **Implementation error.** For a market whose notice date is its last trade date, the Amendment 3 guard (more than 10 trading days from the next execution to the last trade date) failed by one day on the shortened dates. Example: 2024-01, CL-2024H, guard window 10 days instead of 11. That moved F1 one contract later. |
| 6E, 6B, 6M | 2023-11, 2024-02, 2024-05, 2025-02 (identical in all three) | **Implementation error,** the same guard effect: CME FX last trade dates fell one day early. Separately, Databento has no 6E final settlement for any contract on 17 Jun 2025, so its calendar dates 6EM5's exchange-rule last trade one day earlier than Norgate's (13 vs 16 Jun). By my reading of the roll rule this changes no chain. |
| LE | 2023-03, 2024-05, 2025-01 | **Genuine difference.** LE's notice date is its first notice date. The a160bfd exchange rule (first business day of the contract month, e.g. 3 Apr 2023) differs from Norgate's first notice date (e.g. 10 Apr 2023) in all 23 contracts. In the three months the 35-day buffer falls between the two dates. This is the a160bfd rule table, which is frozen (P0), not the comparison code. The one-day last-trade error also affects LE, but does not cause these months. |

### Fix (adapter only; no a160bfd file, threshold or definition changes)

- `em_macro/t2526_data.py` `databento_layout` now presents the Databento files through `_ExchangeRuleDates`.
- It is the a160bfd contract table, computed by its own code. For expired contracts, the last trade date is taken
  from the exchange rule (`ltd_rule`), as for live contracts already, and notice is recomputed as min(first
  notice, last trade). The 35-day rule, the Amendment 3 guard, the calendar and the first-notice rules are
  unchanged.
- The live sleeves use the same layout, so live roll dates follow the exchange rules as A1.2 item 1 already says.
- The missing last-day settlement never reaches P&L: F1 is always rolled well before its last trade date (35-day
  buffer and guard).

### The single rerun

- `python -m em_macro.t2526_data check --amendment-2`, run by the shadows-setup workflow in mode
  `amendment-2-rerun`.
- It checks all 18 markets again and writes `results/shadows/prelive_amendment2.json`. The code refuses a second
  rerun.
- `python -m em_macro.t2526 golive --amend` then gives the provisional go-live record the rerun's universe, N and
  SR_pred. M1 (2026-12) and both evaluation dates are kept, and the previous values are recorded in the record.
- Go-live is still confirmed only by P3 and P4 at M1's rebalance.
- The original `prelive.json` is kept unchanged.

### The rerun: shadows-setup run #3, 9 Nov 2026 03:59 UTC (final)

- **Run:** Actions run 42559206297, mode `amendment-2-rerun`, code at `67d33bf`. The check ran once for all 18
  markets, and its result is final.
- **Every market passed the price test:** 100% of common days within one tick. The unit factor is 1, except HG and
  SI at 100.
- **Chains:** every market agrees except **LE**, whose chain still differs (the first-notice rule, as diagnosed).
  LE is the only exclusion. P1 qualifies as before.
- **Final universe:**
  - **T25: 11 markets:** CL, RB, HO, NG, HG, ZC, ZS, ZW, KE, ZM, ZL.
  - **T26: 17 markets:** the T25 markets plus GC, SI, PL, 6E, 6B, 6M.
  - **SR_pred:** 0.3223 (T25) and 0.3762 (T26), from 0.3073 and 0.329.
  - M1 (2026-12) and both evaluation dates are unchanged.
- **The commit failed.** The run's last step stopped with git exit code 128 ("empty ident name"). In this mode the
  steps that set the bot's git identity in the em-macro-data checkout were skipped. Nothing from the run was
  committed: no public file, and no private contract file or unit factor.
- **How the result is recorded, without checking again:**
  - `results/shadows/GO_LIVE.json` is the amended record exactly as `golive --amend` printed it in the log.
  - `results/shadows/prelive_amendment2.json` holds what the log shows for each market: share, common days, factor,
    chain equal or differs, P1, pass or fail. It also holds the universe and the verbatim log lines, and lists the
    fields the run did not print.
  - The private contract files and unit factors are written from that record by `t2526_data apply-result`, which
    compares nothing. It runs in shadows-setup mode `amendment-2-record`.
- **The rerun is used.** `check --amendment-2` refuses once either record exists.
- **The workflow now sets the bot's git identity in the private checkout in every mode.**
