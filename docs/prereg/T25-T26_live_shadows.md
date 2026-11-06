# Pre-registration — trials T25–T26: zero-size live shadows of the T21 basis-momentum and T22 diversified trend sleeves

| item | value |
|---|---|
| trials | **T25**: a zero-size live shadow of the **T21 basis-momentum** sleeve (the sleeve that passed T23). **T26**: a zero-size live shadow of the **T22 diversified futures trend** sleeve (the sleeve that passed T24). Ledger ids `T25` and `T26` in `trials.csv`, the next free ids (the last row is T24). Trial groups: **`G20_basis_momentum`** (T25) and **`G21_diversified_futures_trend`** (T26). They are the same hypotheses and rules as T21/T23 and T22/T24, tested on a new sample (live data), so they share those groups. |
| why | T23–T24 §1: "A pass of T23 or T24 supports a **separate, later pre-registration of a zero-size live shadow** of that sleeve: positions logged monthly, at no capital." Both passed (`results/T23-T24_pre2000.md`). This is that pre-registration. |
| what this is | A **prospective out-of-sample test** on live data. Each sleeve's positions and paper P&L are recorded monthly at zero capital. The test is evaluated **once**, on a date fixed here (§5.1). |
| family | T25 and T26 are **one family**. The Holm adjustment across the two is in §5.3. |
| rules | T21 and T22 **exactly as run at `a160bfd`**: `docs/prereg/T20-T22_commodity_trials.md` with Amendments 1–4, the Build 0 report and the trial code. That means the same signals, roll rule (35-day buffer, Amendment 3 guard, Amendment 4.4 missing months), volatility estimators, rank weights, 10% single-market risk cap, 10% sleeve target with the 36-month pro-forma scaler, v1.1's T18 band, and **decisive costs (2 × c_raw)**. **No parameter changes of any kind.** The deliberate differences from the backtests are listed in §2.2; none is a parameter. |
| code | The code at `a160bfd`, unchanged. SHA-256: `em_macro/t2022.py` `d54cdc75…3345528a`, `em_macro/commod_data.py` `e5ffe76b…8f49cb25`, `em_macro/commod_build0.py` `2c58f7e2…6e1951c`, `em_macro/t18_rebal.py` `dda6456d…0f96c43`, `em_macro/systematic.py` `1eb4cf6b…50be66`, `em_macro/systematic_v11.py` `b3c4404e…885952`, `em_macro/t01.py` `bc52b3e0…2432b2b` (identical at `a160bfd`, at T23–T24's run and at this branch's base `9a05493`). New code is limited to the data adapter, the live operation and the reporting (§8). |
| data | **Warm-up:** the Norgate 2026-11 snapshots the a160bfd run used (private repo `EthanC100/em-macro-data`, `norgate/2026-11_futures/` manifest `1d6657e6…0f5e60`, `2026-11_financials/` `91d1d9e2…5aa5129`, `2026-11_metadata/metadata.csv` `2efd5eaa…cad9d`). **Live:** Databento GLBX.MDP3 final daily settlements (`ledger/settlements.py`), for dates after the snapshot's last settlement date. All prices are stored only in em-macro-data. |
| branch | `prereg/shadows`: this document, the availability check (§3.2) and its output, and the pending ledger rows. Phase 2 (the build, §8) goes on `trial/T25-T26-shadows`, branched from this commit, **only after the owner replies "approved"**. |
| written | 2026-11-06. **No return, signal, position, sleeve or statistic of the restricted (CME-group) universe was computed in writing it, for any period.** The only data step was the availability check of §3.2: counts of final-settlement days per contract, and no price was summarised, printed or kept. |
| changes nothing else | No v1.0, v1.1, T20–T22 or T23–T24 file is modified (pre-registrations, Build 0 report, results, trial code). v1.0 and v1.1 run as before. |

## 1. Hypotheses, and what the result means

| trial | hypothesis (restated from T21/T23 and T22/T24) | prior evidence |
|---|---|---|
| T25 | The T21 basis-momentum sleeve earns a positive net return after decisive costs out of sample. Adding it to v1.1 at the 25% risk budget does not harm v1.1's Sharpe ratio or drawdown. | Boons and Porras Prado (2019). T21, 2000-01..2026-09: Newey–West t 2.05, net Sharpe 0.40, break-even 5.5. It failed only C1 and C2 against v1.1. T23, 1979-05..1999-12: NW t 2.29, Sharpe 0.49, break-even 4.6, all gates passed. |
| T26 | The T22 diversified trend sleeve earns a positive net return after decisive costs out of sample, and adding it to v1.1 at the 25% risk budget does not harm v1.1's Sharpe or drawdown. | MOP (2012), HOP (2017). T22: net Sharpe 0.40 (2000–2019) and 0.24 (2020-01..2026-09), break-even 6.6. It failed only C1 and C2. T24, 1979-05..1999-12: Sharpe 0.68, break-even 7.1, all gates passed. |

**What the result means (fixed now).**
- **A pass of T25 or T26 leads only to a separate, later pre-registration of v1.2.** That would be a candidate version, v1.1 plus that sleeve (or sleeves), under the programme's process. A pass does **not** adopt anything, add the sleeve to v1.1, or change any capital.
- **A fail closes that sleeve.** No further variant of it is pre-registered in this programme: no other parameters, universe, horizon, data source or evaluation date. If one passes and the other fails, only the passing one may go on to the v1.2 pre-registration.
- **"Not evaluable" (§7.6)** also closes the sleeve for this programme. A new attempt would need a new pre-registration with a new trial id, stating that this one was not evaluable.
- **Neither outcome changes v1.0 or v1.1, or re-opens any earlier trial.** The outcomes of T20–T24 in `trials.csv` stand as recorded. The 12-month paper stage of the T20–T22 pre-registration (§4.4) is not started, because neither T21 nor T22 passed it. This shadow is not that stage: it has zero capital and no integer contracts.

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
| D1 | **Universe restricted to markets with Databento GLBX.MDP3 daily settlements** (CME, CBOT, NYMEX, COMEX, CME FX). **Excluded:** the ICE markets (Brent B, gasoil G, sugar SB, coffee KC, cocoa CC, cotton CT), all non-CME bonds (Euro-Bund FGBL, Euro-OAT FOAT, Euro-BTP FBTP on Eurex; Long Gilt R on ICE). | The live marks come from the one licensed source the programme has for daily settlements, with a quoted cost and a daily cap. The ICE and Eurex data would need separate licences. | T21's cross-section shrinks from 20 to 14 markets, and T22's universe from 30 to 20 instruments (§3.2). Breadth falls: at equal per-market quality the expected Sharpe falls by about √(N/N₀) (§5.4). The sector mix changes: T21 loses all softs and two of its five energy markets; T22 loses its bonds entirely. |
| D2 | **Data:** warm-up history from the a160bfd Norgate snapshot; live dates from Databento final settlements (stat_type 3, final flag). | Norgate is not updated live in this programme. Databento agrees with Norgate within one tick on ≥ 99.97% of days in every CME-group market (Build 0 A5). | One splice per market at the snapshot's last date, checked before go-live (§8, P2). |
| D3 | **Both sleeves start flat** in the first live month: `build_targets` is called with `months` = the live months only. | So no sleeve return, position or T18 band path is ever computed for the restricted universe before live data exist. | The first month's trades are full entries, charged at decisive costs, as in the backtests' first months (T23–T24 §3). |
| D4 | **Zero capital: fractional weights**, with no integer contracts and no live rounding rule (T20–T22 §4.4). | Zero size, as T23–T24 §1 specifies. | None on returns: the backtests' decisive runs used fractional weights. |
| D5 | **Gates.** T21's S2 (alpha against the T20 carry sleeve) is not a gate: T20 failed and runs nowhere live. T22's S2 (carry-crisis correlation) is reported, not gated (§5.5). Combination gates replace C1–C4 (§5.2). | §5. | §5. |

## 3. Universe

### 3.1 Rule (fixed before the check ran)

A market is in a shadow's universe if all of the following hold:
1. **It is in that sleeve's a160bfd universe:** T21's 20 markets, or the 30 instruments of the a160bfd T22 run. Build 0's drops (PA, 6L, 6Z, FBON) stand. No market is added, so 6L and 6Z, which do trade on Globex, stay out.
2. **Its exchange is on Databento GLBX.MDP3:** CME, CBOT, NYMEX or COMEX, including CME FX.
3. **It passes the counts-only availability check (§3.2):** every contract the roll rule would hold at the twelve rebalances December 2026..November 2027 resolves on Databento and has a final settlement on ≥ 95% of the market's settlement days in the check window. "Every contract" means F1 and F2 for T21, which needs both nearby series, and F1 for T22. The 95% is Build 0's coverage threshold (T20–T22 §2.1 rule 1).

### 3.2 Availability check (run 2026-11-06; counts and dates only)

`python -m em_macro.t2526_avail run` (this commit):
- **Contracts:** it lists F1 and F2 at each of the twelve rebalances December 2026..November 2027 under the a160bfd roll rule, using `commod_data`'s exchange LTD/FND rules on a weekday calendar without US holidays or Good Friday.
- **Request:** it resolves each contract's Globex symbol and requests the `statistics` schema over 2026-08-03 to the dataset's available end. The request was quoted first and refused above US$0.50.
- **Counts:** it counts, per contract, the days with a **final** settlement.
- **No prices:** settlement values were read only to test that a final settlement exists. None was kept, printed or written.

The full output is in `results/T25-T26/availability.md`, `availability_counts.csv` and `availability.json`.

AVAILABILITY_RESULT

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
   - the evaluation date with the gates, labelled "evaluated once on <date>; nothing before then is a result";
   - "zero size, paper; not part of v1.0, v1.1 or the fund".

   The shadows are not part of the Horizons fund and never feed any book.
7. **No early stop, no interim decision.** The live record is visible as it accrues. No interim look stops a shadow early, for success or failure, or changes any gate, date or rule. The only decision is at the evaluation date (§5).

## 5. Evaluation (once, at a date fixed now)

### 5.1 Window and date

- **Window:** the first **60 live months**, M1..M60. If M1 = 2026-12, that is **2026-12 .. 2031-11**.
- **Evaluation date:** **15 December 2031** (with M1 = 2026-12). By then v1.1's November 2031 month is booked (3 December) and the shadows' November settlements are stored. If M1 is later, the window is the 60 months from M1, and the evaluation is on the 15th of the month after M60. Both are written in the go-live record (§8) at the first live rebalance, and never changed.
- **Why 60 months** (before any live data):
  - **The programme's convention.** The Ledger's evidence page judges a mechanical strategy's live record against
    a 90%-confidence track-record length: 55 months for v1.0, at its backtest Sharpe ratio of 0.65. 60 months is
    that convention rounded up to whole years. It is the same order of evidence the programme already asks of its
    live algorithm.
  - **The power table (§5.4) shows what it buys.** If the breadth-adjusted backtest effect is real, each shadow
    has about a 1 in 4 chance of passing at 60 months (23% and 25%), about 1 in 5 at 4 years, and about 1 in 3 at
    10 years. With no effect, about 5%. No horizon up to 10 years makes this test decisive. Waiting five more
    years would add only about 10 percentage points.
  - The date is fixed now and never moved.

### 5.2 Gates (decisive costs; the full shadow universe; months M1..M60)

| trial | # | gate | passes if |
|---|---|---|---|
| T25, T26 | S1 | mean monthly net return of the stand-alone shadow (`Sleeve.monthly(2.0)`), Newey–West (6 lags) t-statistic | mean > 0 **and** Holm-adjusted one-sided p < **0.10** (§5.3) |
| T25, T26 | S3 | break-even cost multiple m* = annualised mean gross return / annualised cost drag at 1 × c_raw | m* ≥ 2 |
| T25, T26 | C-SR | v1.1 + shadow at the 25% risk budget (`t2022.combine`: v1.1's held weights from its monthly run, its own cost model and lags; the shadow's legs at decisive costs), against v1.1's live record over M1..M60 | ΔSR = SR(v1.1 + shadow) − SR(v1.1) ≥ **−0.05** (point estimate; non-inferiority margin of T20–T22 Amendments 1–2) |
| T25, T26 | C-DD | the same combined book | \|MaxDD(v1.1 + shadow)\| ≤ **1.10 × \|MaxDD(v1.1)\|** (T20–T22 C3's margin) |

- **A trial passes only if all four gates hold**, with S1 after the Holm adjustment.
- S3 at decisive costs is nearly implied by S1, since m* ≥ 2 means the gross return at least covers 2 × c_raw. It is kept because the backtests had it.
- **v1.1's record** is its official live paper P&L (`results/systematic_v1.1/paper_pnl.csv`) over M1..M60. The combination is computed once, on the evaluation date, with v1.1's monthly run outputs and the `systematic` inputs of that date, as v1.1's own update computes them.

### 5.3 Multiple testing across the two

```
p_k = 1 − Φ(t_k),   t_k = NW (6 lags) t of shadow k's mean monthly net return over M1..M60
Holm (m = 2): order p_(1) ≤ p_(2);  p_adj,(1) = min(1, 2 p_(1));  p_adj,(2) = max(p_adj,(1), p_(2))
```

S1 passes for shadow k if mean_k > 0 and p_adj,k < 0.10, so the family-wise one-sided error is at most 10%. The other gates are point estimates and are not adjusted, as T20–T22 §5 left its non-bootstrap gates. Raw and adjusted p-values are both reported.

### 5.4 Honest power (computed before any live data)

**Method.** A Monte Carlo of 8,000 paths per case, seed 20261106 (script reproduced in Phase 2's report):
- monthly returns of v1.1 and the two shadows, normal, each at 10% annual volatility;
- correlations from the 2020-01..2026-09 backtest diagnostics: T21–v1.1 0.08, T22–v1.1 0.05, T21–T22 0.20;
- v1.1's Sharpe ratio at its 2006–2026 decisive value, 0.71;
- the shadows' Sharpe ratios at the **backtest effect, breadth-adjusted**: the pooled decisive Sharpe of each sleeve's two backtests (T21 1979–2026 ≈ 0.435; T22 ≈ 0.50) times √(N/N₀) for the restricted universe (T21 √(14/20), giving **0.36**; T22 √(20/30), giving **0.41**);
- the S1 Holm rule, ΔSR and MaxDD computed exactly as in §5.2 on the paths. A plain t-statistic stands in for NW on independent normal returns.

Monte Carlo error is about ±0.5 percentage points.

| true effect | horizon | T25: S1 | T25: C-SR and C-DD | **T25: all gates** | T26: S1 | T26: C-SR and C-DD | **T26: all gates** |
|---|---|---|---|---|---|---|---|
| backtest, breadth-adjusted | 3 years | 18% | 62% | 17% | 20% | 65% | 19% |
| backtest, breadth-adjusted | **5 years (decisive)** | 24% | 66% | **23%** | 26% | 70% | **25%** |
| backtest, breadth-adjusted | 8 years | 32% | 72% | 29% | 35% | 75% | 33% |
| backtest, breadth-adjusted | 10 years | 37% | 74% | 33% | 41% | 77% | 37% |
| backtest, no breadth haircut (0.435 / 0.50) | 5 years | 31% | 71% | 28% | 34% | 76% | 31% |
| half the breadth-adjusted effect | 5 years | 13% | 53% | 12% | 14% | 57% | 13% |
| **no effect** (Sharpe 0) | 5 years | 5% | 40% | **4.8%** | 6% | 42% | **5.3%** |

**What this means, stated plainly.**
- **If the backtest effect is real, each shadow is still more likely to fail than pass**: about a 1 in 4 chance of passing at 60 months, and about 1 in 3 at 10 years. A Sharpe ratio near 0.4 needs about 20 years of data for an expected t-statistic of 2.
- **A pass is meaningful evidence:** with no effect, a shadow passes about 5% of the time.
- **A fail is weak evidence against the effect.** But this programme fixes now that a fail closes the sleeve (§1). The owner accepts that a real but modest effect will most likely be closed by this test.
- The combination gates pass about 40% of the time even with no effect, so they guard against harm and do not discriminate. S1 does the discriminating.
- These figures assume normal, independent monthly returns. Fat tails and serial correlation in practice would lower the power further.

### 5.5 Reported, not decisive

None of these can change a decision:
- the 2× cost sensitivity (`monthly(4.0)`);
- by year;
- each shadow's P&L by sector (T26: commodities and currencies);
- the correlations between the two shadows, with v1.1 and with v1.0's live carry-only sleeve;
- T22's S2 analogue: the correlation with v1.0's carry-only sleeve (`systematic.run(inp, ["carry"])`, as T01 and T22) in carry's worst 6 live months (10% of 60);
- the monthly count of active markets;
- the outage log (§7);
- turnover;
- the superiority version of the combined test (ΔSR > 0), as context.

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
6. **Not evaluable.** At the evaluation date, a shadow is **not evaluable** if:
   - fewer than 54 of its 60 months (90%) had a computed rebalance with at least 6 active markets; or
   - its record was interrupted for more than 3 consecutive months.

   It is then neither passed nor failed, and §1 applies.
7. **Bugs.** A bug found before the evaluation date is fixed only if the fix restores what this document and the a160bfd code specify. The fix, its commit and the affected months are recorded. The whole live path is then recomputed from M1, as every run does, so the record stays consistent. No gate, date or rule changes.
8. **Late runs.** If the rebalance is computed after the 3rd (item 2, or a delayed run), the decision still uses only settlements up to t. The execution date is the market's first settlement on or after the 3rd, so a late computation never changes the positions.

## 8. Phase 2 (only after the owner replies "approved")

1. **Branch** `trial/T25-T26-shadows` from this commit.
2. **New code, data and operation only:**
   - `em_macro/t2526.py`, which:
     - presents the Norgate warm-up and the Databento live settlements to the unchanged `commod_data.MarketData` (one splice per contract at the snapshot's last date);
     - builds `t2022.Mkt`, the signals, `build_targets` with `months` = live months, and `Sleeve`;
     - writes the private and public files of §4.4;
     - evaluates once at the evaluation date.
   - The Ledger "Shadows" section, and the `ledger-daily` step.
   - `tests/test_t2526.py`, **tested on synthetic data only**: the splice, start-flat, the missing-data rules of §7, Holm at the boundaries, and no price in any public file.
3. **Pre-live checks before the first live rebalance.** Each is recorded in `results/shadows/GO_LIVE.json`. A failure moves go-live to the next rebalance.
   - **P0:** the SHA-256 of every a160bfd file listed above matches.
   - **P1:** the §3.2 counts, recomputed on the then-current window, still qualify every universe market. A market that no longer qualifies is excluded under §3.1, before go-live.
   - **P2: splice agreement.** For every universe market, the Databento final settlements of the held F1 (and F2 for T21) agree with the Norgate snapshot within one tick on ≥ 99% of their common days (Build 0 A5's tolerance), counts only. A failing market is excluded before go-live.
   - **P3:** every universe market has σ and a signal available at the first decision date. Otherwise §7.2 applies that month.
   - **P4:** a dry rebalance on the first decision date prints only the active count per sleeve, which must be ≥ 6, and no weight.
4. **Go-live record.** At the first live rebalance: M1, the evaluation date, the universe, the code commit and the hashes are recorded. This fixes every date of §5.1.

## 9. Ledger and multiple-testing record

- `trials.csv` gets rows **T25** (group `G20_basis_momentum`) and **T26** (group `G21_diversified_futures_trend`), marked **pending**, in this commit, with no other row changed. The ledger's row count rises from 24 to 26, and the distinct trial groups do not increase.
- `tests/test_ledger.py` is updated to expect the two rows as pending. The app's evidence page lists the shadows as pre-registered and pending.
- No deflated-Sharpe gate is part of T25–T26, so the spec-convention N (16) is not incremented. A later v1.2 pre-registration that uses a DSR will count T23, T24, T25 and T26.
