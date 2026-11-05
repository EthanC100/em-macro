# Build 0 — commodity data acceptance tests for trials T20–T22

| item | value |
|---|---|
| pre-registration | `docs/prereg/T20-T22_commodity_trials.md` §6 (A1–A11), as amended in `023c829` (Amendment 1: 20-market cross-sectional universe) and `6ac4616` (Amendment 2: C2 only, no Build 0 change). The pre-registration is not modified. |
| branch | `build/commodity-build0`. The pre-registration names `results/T20-T22/build0.md` for this report; it is written to `results/build0_commodity_data.md` as the task asked. |
| code | `em_macro/commod_data.py` (data layer: contract tables, calendars, 35-day roll rule, F1/F2/F13, chained same-contract index), `em_macro/commod_build0.py` (A1–A4, A6, A7, A9–A11 and the extra checks), `em_macro/commod_databento.py` (A5), `tests/test_commod_data.py` (A6, A9, A11 as tests; synthetic tests always run, data-backed tests skip without the private data) |
| primary source | Norgate snapshot `2026-11_futures` (as of 2026-11-05, latest bar 2026-11-04) in the private repo `EthanC100/em-macro-data`, `norgate/2026-11_futures/` (9,473 contract files; SHA-256 per file in its `manifest.csv`). Read in this session's container from a clone of the data repo; the AWS server was not needed and was not started. |
| benchmarks | AQR data library, downloaded 2026-11-05: *Commodities for the Long Run* (monthly, to 2025-05) and *Century of Factor Premia* (monthly, to 2026-02). Kept outside this repository. |
| cross-check | Databento GLBX.MDP3, schema `statistics` (settlement prices), 2010-06-07 to 2026-10 |
| licence | This repository holds code, this report and aggregate statistics only. Contract tables, roll tables, return series, the A3/A4 series, the Databento settlements and every per-day comparison are in `em-macro-data/norgate/derived/build0/` (private). |
| blindness | No T20, T21 or T22 sleeve return, Sharpe ratio, drawdown or pass criterion was computed. Nothing was combined with v1.0 or v1.1. A3 and A4 build the two benchmark-comparison series the tests define; only their correlations are reported (A8). |

## 1. Result

| test | threshold (pre-registered) | measured | result |
|---|---|---|---|
| A1 assembly | every one of 34 markets has a contract table and FND/LTD metadata, or is recorded as unavailable | 24 commodity markets: contract tables 1990-01 (RB 2005-10) to 2026-10, 7,047 designated contracts (expiring 1990-01 or later and listed by 2026-10, including live ones). 3 financial futures recorded as unavailable (6L, 6Z, FBON: not in Norgate). **7 financial futures (6E, 6B, 6M, FGBL, FOAT, FBTP, Long Gilt) are in Norgate but not in the export**, so they have no contract table. FND is from exchange rules, not from Norgate (not exported). | **NOT COMPLETE** (cannot be finished as written without a new Norgate export) |
| A2 F1/F2 coverage, 20-market universe | ≥ 18 markets with coverage ≥ 95% since 2000-01 | **20 of 20** markets at 100.0% (RB from its entry, 2006-12) | **PASS** |
| A3 equal-weight index vs AQR *Commodities for the Long Run* | Pearson ≥ 0.90 | **0.975** (424 months, 1990-02..2025-05; 22–24 markets per month); 0.978 from 2000-01 | **PASS** |
| A4 KMPV-style carry portfolio vs AQR commodity carry factor | Pearson ≥ 0.70 | **0.503** (433 months, 1990-02..2026-02; ≥ 21 markets per month); 0.524 from 2000-01 | **FAIL** |
| A5 Databento cross-check, CME-group markets from 2010-06-06 | within one tick on ≥ 99% of days, per market | 18 of 18 markets pass: 14 at 100.000%, PA and HE at 99.976% (8,166–8,178 days each; KE 6,436 days, from Dec 2013) | **PASS** |
| A6 roll-rule look-ahead tests | all assertions hold on the full history | April 2020 → **CLM20** (holds); notice(F1) > execution + 35 days on every rebalance (holds); no LME series (holds). **First settlement on or before the decision date fails for 35 F2 picks** (PL 13, PA 22 months, all 2000–2009). **"Never inside the last 10 trading days" fails for F1 in 5 markets**: 2000-01..2026-09 violations B 192, G 312, HE 213, GF 8, CL 3 of 321 rebalances | **FAIL** |
| A7 Option A availability (T20), 20 markets | the assignment table is in the report, computed from availability only | §3: Option A for 14 markets, Option B for 6 | **PASS** |
| A8 no peeking | no return, Sharpe, drawdown or P&L of any sleeve or signal in the report | reviewed before the commit: the report and `results/build0_commodity_data*.json` contain counts, shares, correlations, dates and tick-agreement rates only | **PASS** |
| A9 data quality | no unresolved > 5-day held-contract gap or fully reversing 8-MAD spike; limit-locked days flagged | held F1: 0 gaps > 5 days in any market. 16 F2 gaps > 5 days, all in PL and PA, whose F2 series no trial holds (T21 excludes them). 14 reversing spikes, all confirmed by the adjacent contract on the same day (genuine market moves). 203 limit-lock flags in grains and livestock (flagged, not failed) | **PASS** |
| A10 T22 financial futures coverage | each market ≥ 95% or dropped and recorded | 6L, 6Z, FBON dropped (not in the primary source). 6E, 6B, 6M, FGBL, FOAT, FBTP, Long Gilt: **not run** (no export) | **NOT COMPLETE** |
| A11 F2 and F13 listed on every date used | assertion holds | 0 violations in 24 markets (F2/F13 counted as used when they settle on the decision date) | **PASS** |

**Can T20–T22 proceed? No.** §6 requires every test to pass before any trial runs, and "a failure stops the trials".
A4 and A6 fail, and A1 and A10 cannot be completed from the current export. What each failure needs is in §6
below. None of it was changed here: the roll rule, the buffer and the A4 definition are pre-registered, and changing
them is a pre-registration amendment for the owner, not a data fix.

**Markets dropped mechanically**
- **PA (palladium)** fails the coverage gate of §2.1 rule 1 (93.15%, 299 of 321 decision dates, below 95%) and is
  dropped from every trial. Since Amendment 1 it was only in T22.
- **6L, 6Z, FBON** are not in Norgate's futures list, so they are recorded as unavailable (A1) and dropped from T22 (A10).

PL passes the gate at 95.95% (308 of 321) and stays in T22.

## 2. A1 — contract tables and metadata

| market | Norgate | designated contracts 1990–2026 (live) | notice(T) | LTD rule vs Norgate final bar, expired contracts 2000–2026: exact / within 2 business days (n) | data notes |
|---|---|---|---|---|---|
| CL | CL | 565 (123) | LTD | 98.4% / 100.0% (322) |  |
| B | BRN | 590 (147) | LTD | 36.2% / 40.2% (323) | pre-2016 contracts under the old LTD rule |
| RB | RB | 289 (38) | LTD | 100.0% / 100.0% (251) | RBOB only, from 2005-10 |
| HO | HO | 480 (38) | LTD | 100.0% / 100.0% (322) | vendor splice heating oil → ULSD (May 2013) |
| NG | NG | 568 (119) | LTD | 98.1% / 100.0% (322) | 11 stray far quotes (2036X–2037U) flagged |
| G | GAS | 516 (74) | LTD | 99.4% / 100.0% (322) | vendor splice gasoil → 10 ppm (Feb 2015) |
| HG | HG | 210 (26) | min(FND, LTD) | 100.0% / 100.0% (134) |  |
| GC | GC | 241 (20) | min(FND, LTD) | 98.8% / 100.0% (161) |  |
| SI | SI | 200 (16) | min(FND, LTD) | 99.3% / 100.0% (134) |  |
| PL | PL | 160 (12) | min(FND, LTD) | 81.5% / 100.0% (108) | far months unlisted in 2000–05 (A6) |
| PA | PA | 159 (12) | min(FND, LTD) | 80.4% / 99.1% (107) | far months unlisted in 2000–09 (A6); coverage 93.15% → dropped |
| ZC | ZC | 197 (13) | min(FND, LTD) | 95.5% / 100.0% (134) |  |
| ZS | ZS | 275 (17) | min(FND, LTD) | 94.1% / 100.0% (188) |  |
| ZW | ZW | 198 (14) | min(FND, LTD) | 94.8% / 100.0% (134) |  |
| KE | KE | 198 (14) | min(FND, LTD) | 82.8% / 82.8% (134) | KCBT rules before 2013 |
| ZM | ZM | 315 (17) | min(FND, LTD) | 94.4% / 100.0% (215) | 2029N/V/Z stopped quoting 2026-09-29, flagged |
| ZL | ZL | 315 (17) | min(FND, LTD) | 94.4% / 100.0% (215) | 2029N/V/Z stopped quoting 2026-09-29, flagged |
| SB | SB | 159 (11) | LTD | 99.1% / 100.0% (108) |  |
| KC | KC | 191 (7) | min(FND, LTD) | 95.5% / 99.3% (134) |  |
| CC | CC | 194 (10) | min(FND, LTD) | 92.5% / 99.3% (134) |  |
| CT | CT | 198 (14) | min(FND, LTD) | 96.3% / 99.3% (134) |  |
| LE | LE | 231 (10) | min(FND, LTD) | 100.0% / 100.0% (161) |  |
| GF | GF | 304 (9) | LTD | 65.6% / 84.7% (215) | Nov/holiday LTD exceptions |
| HE | HE | 294 (11) | LTD | 99.5% / 100.0% (213) | 92 final-settlement rows corrected; May not listed before 2002 |
| 6E | 6E | — | — | — | in Norgate (6E) but not exported → no table |
| 6B | 6B | — | — | — | in Norgate (6B) but not exported → no table |
| 6M | 6M | — | — | — | in Norgate (6M) but not exported → no table |
| 6L | — | — | — | — | not in Norgate → unavailable, dropped from T22 |
| 6Z | — | — | — | — | not in Norgate → unavailable, dropped from T22 |
| FGBL | FGBL | — | — | — | in Norgate (FGBL) but not exported → no table |
| FOAT | FOAT | — | — | — | in Norgate (FOAT) but not exported → no table |
| FBTP | FBTP | — | — | — | in Norgate (FBTP) but not exported → no table |
| FBON | — | — | — | — | not in Norgate → unavailable, dropped from T22 |
| R | LLG | — | — | — | in Norgate (LLG) but not exported → no table |

How the metadata was built (decision 2 in §7):
- **LTD.** For an expired contract, LTD = Norgate's final settlement. Per `docs/infra/norgate_pipeline.md`, this is what
  Norgate's `last_quoted_date` returns for expired contracts. There are two corrections:
  - **Lean hogs.** Norgate adds a cash final-settlement row two business days after the last trading day, with a
    missing day in between. For these 92 contracts in 2000–2026, LTD = the bar before the gap.
  - **Contracts that stopped quoting more than 30 days before their scheduled LTD** (NG 2036X–2037U, ZM and ZL
    2029N/V/Z) keep the exchange-rule LTD and are flagged. None was ever used as F1, F2 or F13.

  For a live contract, LTD = the exchange rule.
- **FND.** The exchange rule, on the market's own trading calendar (the union of its settlement dates; weekdays
  without US federal holidays and Good Friday after 2026-11-04). The rules used:
  - **Last business day of the prior month:** metals and grains.
  - **ICE softs:** KC 7 business days before the first business day of the delivery month; CC 10 business days
    before its sixth business day; CT 5 business days before its first business day.
  - **LE:** first business day of the contract month. CME's rulebook has no pre-LTD FND for live cattle. Any date
    from the 1st to the 6th selects the same contracts, because execution + 35 days always falls after the 7th.
  - **All other markets:** notice = LTD.
- **Lower agreement for B, PL, PA, KE and GF means old rules, not bad data.** Agreement between the exchange rule and
  Norgate's final bar is lower in these markets because their old contracts expired under earlier rules:
  - **B:** the pre-2016 Brent rule (15 days before the delivery month). Among contracts from 2016 on, the current
    rule matches the final bar exactly for 117 and is one business day off for 13 (holiday-adjacent expiries).
  - **KE:** KCBT rules before the CBOT move.
  - **PL/PA:** 4th-last against 3rd-last business day.
  - **GF:** November and holiday exceptions.

  Using the final bar for expired contracts means the roll rule always sees the date each contract actually expired.
- **Gaps in the designated calendar** are all contracts that are not yet listed or were never listed:
  - GC, SI, ZC, ZS, ZM and ZL months in 2029–2032, not listed yet.
  - HE May contracts before 2002, not listed then.
- **Specification check.** Multipliers, ticks, listed months and LTD/FND rules were checked against the ICE and Eurex
  specification pages, and against official CME rulebook and fact-card text. cmegroup.com refused direct fetches, so
  official text was read through search snippets. All multipliers, tick values and designated calendars match the
  pre-registered table, except these data facts (to be logged, not trial changes):
  - **PA:** the outright tick has been **0.50 = US$50** since 7 Dec 2020 (SER-8668R); 0.10 = US$10 now applies only to
    spreads and settlements. This affects T22's PA cost line, but PA is dropped (above).
  - **6Z:** the tick is **0.000025 = US$12.50**. The pre-registration had "per exchange spec".
  - **6E** was 0.0001 = US$12.50 until 11 Jan 2016. **6M** was US$12.50 until 14 Jul 2014. The pre-registered ticks
    are today's.
  - **Brent** is EFP-deliverable with an option to cash settle. The pre-registration already treats it as cash
    (notice = LTD).
  - **CC FND** is "ten business days prior to the sixth business day of the delivery month". It was used as such.
  - Ticks are applied in Norgate's quoting units: US cents for copper, silver, grains, softs and livestock.
- **Vendor splices (§2.1 rule 2).**
  - **HO:** Norgate's HO series runs from 1978 under one symbol ("NY Harbor ULSD"). No. 2 heating oil to the Apr-2013
    contract, ULSD from May 2013 (SER-6198). Treated as one market.
  - **G:** Norgate's GAS series runs from 1988. 0.1% gasoil to the Jan-2015 contract, 10 ppm from Feb 2015. Treated
    as one market.
  - **RB:** Norgate has RBOB only, from 2005-10-03. Unleaded gasoline is not in its list, so RB enters 12 months
    after its first F1 settlement, at the **2006-12** rebalance.
- **Financial futures.** Norgate's futures list has 6E (131 contracts), 6B (207), 6M (146), FGBL (114), FOAT (61),
  FBTP (71) and Long Gilt (LLG, 156). The `2026-11_futures` export covered only the 24 commodity targets of
  `scripts/norgate_export.py`. 6L, 6Z and FBON are not in Norgate.

## 3. A7 — Option A/B assignment for T20 (computed from availability only, before any carry return)

Share of design-sample decision dates (2000-01..2019-12, after entry) with an eligible F13 settlement. The rule is
Option A if the share is ≥ 90%, otherwise Option B for the whole sample.

| market | share | option | market | share | option |
|---|---|---|---|---|---|
| CL | 100.0% (240/240) | A | B | 82.9% (199/240) | B |
| RB | 98.1% (154/157) | A | HO | 98.8% (237/240) | A |
| NG | 100.0% (240/240) | A | G | 71.7% (172/240) | B |
| HG | 100.0% (240/240) | A | ZC | 99.6% (239/240) | A |
| ZS | 91.2% (219/240) | A | ZW | 90.0% (216/240) | A |
| KE | 84.6% (203/240) | B | ZM | 95.8% (230/240) | A |
| ZL | 96.7% (232/240) | A | SB | 100.0% (240/240) | A |
| KC | 100.0% (240/240) | A | CC | 100.0% (240/240) | A |
| CT | 100.0% (240/240) | A | LE | 61.3% (147/240) | B |
| GF | 0.0% (0/240) | B | HE | 75.0% (180/240) | B |

The result is **Option A for 14 markets and Option B for 6** (B, G, KE, LE, GF, HE).
- ZW is exactly at the threshold: 216 of 240 dates, 90.0%, so Option A because the rule is ≥.
- GF's 0% follows from CME listing feeder cattle only about 12 months ahead, so no contract 10.5–13.5 months after F1
  has a settlement on the decision date.

## 4. A5 — Databento cross-check (CME-group commodity markets)

| market | days compared | Databento has no settlement | scale | within 1 tick | days outside | result |
|---|---|---|---|---|---|---|
| CL | 8,172 | 10 | ×1 | 100.000% | 0 | PASS |
| RB | 8,172 | 10 | ×1 | 100.000% | 0 | PASS |
| HO | 8,172 | 10 | ×1 | 100.000% | 0 | PASS |
| NG | 8,172 | 10 | ×1 | 100.000% | 0 | PASS |
| HG | 8,174 | 8 | ×100 | 100.000% | 0 | PASS |
| GC | 8,172 | 10 | ×1 | 100.000% | 0 | PASS |
| SI | 8,172 | 10 | ×100 | 100.000% | 0 | PASS |
| PL | 8,174 | 8 | ×1 | 100.000% | 0 | PASS |
| PA | 8,174 | 8 | ×1 | 99.976% | 2 | PASS |
| ZC | 8,178 | 4 | ×1 | 100.000% | 0 | PASS |
| ZS | 8,178 | 4 | ×1 | 100.000% | 0 | PASS |
| ZW | 8,178 | 4 | ×1 | 100.000% | 0 | PASS |
| KE | 6,436 | 1,746 | ×1 | 100.000% | 0 | PASS |
| ZM | 8,178 | 4 | ×1 | 100.000% | 0 | PASS |
| ZL | 8,178 | 4 | ×1 | 100.000% | 0 | PASS |
| LE | 8,166 | 16 | ×1 | 100.000% | 0 | PASS |
| GF | 8,166 | 16 | ×1 | 100.000% | 0 | PASS |
| HE | 8,166 | 16 | ×1 | 99.976% | 2 | PASS |

The comparison window is 2010-06-07 to the 2026-10 decision date. Each market has 8,182 F1/F2 contract-days
(F1 and F2 on every market day from each month's decision date to the next). **All 18 CME-group commodity markets
pass. 14 agree on every compared day, and PA and HE agree on 99.976%.** That is ≥ 99.9% for every market, against
a threshold of 99%.
- **HE, 2 days** (HE-2012N on 2012-06-19, HE-2012Q on 2012-07-17). Databento's last settlement record for the
  contract that day has a price of exactly 0. Norgate's series is continuous through both days (ordinary
  day-to-day moves), and F2 agrees on the same days. These are Databento artefacts, not Norgate errors.
- **PA, 2 days** (2020-12-04, 2022-09-22). 2 ticks (0.20) apart, after the Dec-2020 tick change. Small and not
  investigated further.
- **Days with no Databento settlement.** There are 4–16 such days in most markets, for example a GLBX gap in LE/GF/HE
  in February 2012 and some days Databento flags as degraded in June 2014. KE has 1,746: KC HRW wheat was a KCBT
  product until the CBOT transfer (December 2013), and its 2010–2013 contracts do not resolve in GLBX.MDP3. **KE is
  therefore cross-checked from December 2013 only** (6,436 days). Norgate has a settlement on every planned day.
- **Not cross-checked.** The CME FX futures (6E, 6B, 6M) are not in the Norgate export, so there is nothing to
  compare. ICE markets (B, G, SB, KC, CC, CT) are outside A5, as instructed.

## 5. A6, A9, A11 and A2 detail

**A6, notice and look-ahead.** The rule always selects a contract whose notice(T) is after execution + 35 days. On the
April 2020 decision date (decision 2020-04-02, execution 2020-04-03) it selects **CL-2020M**, not CL-2020K, whose
last trade was 2020-04-21. No contract from an LME market or series exists anywhere in the data layer.

**A6, first settlement.** The assertion fails for 35 F2 picks:
- PL: 13 months in 2000–2005.
- PA: 22 months in 2000–2009.

The rule picks the next designated month by calendar, and in these months Norgate has no bar for it yet: the far
platinum and palladium months had no settlements before roughly a quarter before expiry in that period. No price is
used before it exists, because a missing F2 settlement makes the market-month uncovered. That is why PA fails the
coverage gate. Still, the assertion as written does not hold.

**A6, "never inside the last 10 trading days" (spec §7).** This was checked on every held day from the entry
settlement to the exit settlement inclusive, counting trading days from that day to the contract's LTD inclusive.
Violations, F1, 2000-01..2026-09 (321 rebalances):

| market | notice(T) | violations | of which 2016–2026 | fewest trading days left at exit | violations if the exit day is excluded (full history) |
|---|---|---|---|---|---|
| G gasoil | LTD = 2 business days before the 14th of the delivery month | 312 | 125 | 4 | 429 of 442 |
| HE lean hogs | LTD = 10th business day of the contract month | 213 | 87 | 7 | 201 of 442 |
| B Brent | LTD (pre-2016 rule ~15 days before the month; current rule end of the 2nd month before) | 192 | 0 | 7 | 194 of 442 |
| GF feeder cattle | LTD = last Thursday of the contract month | 8 | 3 | 9 | 4 of 442 |
| CL WTI | LTD = 3 business days before the 25th of the prior month | 3 | 0 | 10 | 0 of 442 |
| other 19 markets | | 0 | 0 | ≥ 11 | 0 |

F2 is never inside its last 10 trading days in any market.

**Why the rule fails.** The pre-registration's argument ("the holding period is at most 31 days plus the execution
lag") does not hold for markets where notice(T) = LTD. The rule only guarantees LTD > execution + 35 days, while the
next execution date can be 31–35 days later. A contract can therefore be held until 2–10 trading days before its last
trade.
- **Gasoil** is the clearest case: at the November execution, the December contract (LTD around the 10th–12th of
  December) passes the 35-day test and is held to the December execution.
- **Brent's** failures are all from the pre-2016 rule.

This is a property of the pre-registered rule, not of the data. Correcting it means amending the rule, so it is
reported, not fixed. Two possible amendments, for the owner to choose:
- require notice(T) > next execution date + 10 trading days, or
- measure the buffer to the LTD for cash-settled and LTD-notice markets.

**A9.** The checks were run on the held F1 and F2 series from 1990.
- **Gaps.** No held F1 contract in any market has a gap of more than 5 consecutive market days. The F1 series has no
  filled days at all.
- **Reversing spikes.** A spike is a one-day move more than 8 rolling 252-day MADs from the rolling median (the MAD is
  floored at one tick), followed by a next-day move that reverses at least 90% of it. There are 14 (B 2020-03-18, GC
  1993-09-21, SI 2014-11-28 and 2025-12-30, ZM 1994-05-23, CC 2024-05-02/03, LE 2020-03-16, GF 2019-08-13). Each
  is matched on the same day by the adjacent designated contract, moving the same way by at least half as much and
  reversing too, so they are genuine curve-wide moves.
- **Limit-lock flags.** Unchanged settlement after a > 3-MAD move, in grains and livestock: ZC 39, ZS 19, ZW 8,
  KE 22, ZM 21, ZL 15, LE 29, GF 30, HE 20. These are flagged, not failed.
- **The 16 F2 gaps in PL and PA.** They are the not-yet-listed F2 periods described under A6. They are classed as
  "not held by any trial" because T22 holds F1 only and T21 excludes the precious metals.

**A11.** F2 and F13 are listed (first settlement ≤ t ≤ last settlement) on every decision date on which they have a
settlement, and no such contract stopped quoting early (all ended within two months before their contract month, or
are live). There are 0 violations.

**A2/A10 detail.** F1/F2 coverage from 2000-01 (RB from 2006-12) to 2026-09 is 100% for all 20 cross-sectional markets
and for GC and SI. It is 95.95% for PL and 93.15% for PA. The uncovered PL/PA months are the unlisted-F2 months above.

## 6. What blocks the trials, and what each blocker needs

| blocker | rule in the pre-registration | what would resolve it (owner's decision; nothing here was changed) |
|---|---|---|
| A4 = 0.503 < 0.70 | §6: a failure stops the trials. There is no fallback for A4 | Investigate why the KMPV-style F1/F2 carry portfolio and AQR's factor diverge, for example AQR's universe, weights or carry definition. Lead/lag checks rule out a timing error: the correlation is −0.01 at −1 month, 0.50 at 0, 0.10 at +1. Any change to the A4 definition or threshold is an amendment, made before T20's data are used. |
| A6 last-10-trading-days (G, HE, B, GF, CL) and F2 first-settlement (PL, PA) | §6: all assertions must hold. The roll rule is "one rule, never switched" | An amendment to the roll rule or to the A6 assertion, recorded before any signal is computed |
| A1/A10 for 6E, 6B, 6M, FGBL, FOAT, FBTP, Long Gilt; FND from the primary source | A1: contract table and FND/LTD metadata from the primary source for all 34 markets | A Norgate export run with NDU running (one RDP session), adding these 7 markets and the per-contract `first_notice_date`/`last_quoted_date` fields. The export script does not export them yet. |

## 7. Decisions taken under the task's rules

1. **Where the data work ran.** The data work ran in this session's container: `em-macro-data` cloned with
   `DATA_REPO_TOKEN`, which worked, so the server was not used and not started. The Databento key was stored as
   SecureString `/horizons/databento/api-key` (ap-southeast-2, `alias/aws/ssm`, version 1) for later server use. It
   was never printed.
2. **FND/LTD.** The Norgate export has no FND/LTD fields, so the metadata was built as described in §2: LTD from
   Norgate's final settlement for expired contracts (with the lean-hog and stopped-quoting corrections), the
   exchange rule for live contracts, and FND from exchange rules (the commodities spec's Appendix B lists "exchange
   calendars" as the source). The simplest reading consistent with A1; flagged in §6.
3. **Trading calendar.** A market's trading days are the dates on which any of its contracts has a settlement. The
   execution date is the first such date on or after the 3rd. The decision date is the one before it.
4. **The 35-day test** is `notice(T) > execution + 35 calendar days`, applied to the designated contracts present in
   Norgate. F2 is the next designated contract. F13 has the LTD closest to LTD(F1) + 365 days within ±45 days, with
   ties going to the later contract.
5. **A6 held days.** Every day from the entry settlement to the exit settlement inclusive. Excluding the exit day is
   also reported; it does not change the result.
6. **A2/A10 entry.** Entry is the first rebalance with ≥ 252 F1 daily returns and 12 months of F1 history. It is before
   2000 for every market except RB (2006-12).
7. **A3.** Each market's calendar-month return of its chained F1 index (§2.3), equally weighted over the markets with
   a full-month return. Compared with AQR's "Excess return of equal-weight commodities portfolio" over all
   overlapping months.
8. **A4.** carry_log = (ln F1 − ln F2) × 365/(D2 − D1) at the decision date, with D from the decision date to each LTD.
   Rank weights s = rank − (n+1)/2 scaled to Σ|s| = 2 over all markets with a value (24 less any missing). Each
   market's F1 holding return runs from this execution to the next, and the portfolio return is labelled with the
   rebalance month. Compared with AQR's "Commodities Carry" (*Century of Factor Premia*) over all overlapping months.
   Sub-period correlations are 1990s 0.44, 2000s 0.45, 2010s 0.61, 2020-01..2026-02 0.52.
9. **A5.** Settlements come from Databento's `statistics` schema (stat_type 3), taking the last record per contract and
   trading date. OHLCV-1d closes are last trades on a UTC day, not settlements. Days compared are those on which
   both sources have a settlement, for each month's F1 and F2 from that month's decision date up to the next one.
   Ticks are in Norgate units, and Databento prices are rescaled by the median ratio (×100 for HG and SI, quoted in
   US$ by Databento and in cents by Norgate). PA is compared at its 0.10 settlement tick. Only CME-group commodity
   markets were checked, as instructed. ICE markets were not cross-checked: Databento's ICE data was not used, and
   the pre-registration's Barchart spot checks are outside A5's pass rule and were not done.
10. **A9.** The MAD and median are rolling over the prior 252 days, with the MAD floored at one tick. "Fully reverses"
    means the two-day move is within 10% of the first day's. A spike is resolved when the adjacent designated
    contract confirms it. F2 gaps of markets outside T21 are "not held by any trial".
11. **A11.** A contract is "used" on a decision date when it has a settlement there. Otherwise the value is missing
    (§2.1 rule 3) and nothing is used. "Not delisted" means it did not stop quoting early (§2).
12. **A7 threshold.** The threshold is inclusive (≥ 90%), as written.

## 8. Extra checks (report only; not pre-registered, not pass/fail)

**Specification changes inside 2000–2026.** Same-contract returns never cross two contracts, so a respecified
contract cannot create a jump in r_ex or in the chained index. Its only possible effect is on the curve (F1 against
F2 or F13). For each change below, the largest month-on-month change of ln(F2/F1) on decision dates within ±3 months
is shown as a multiple of the market's median absolute change 2000–2026, with its rank among that market's 320
monthly changes. These are dates and multiples only, with no signal values.

| market | change (first affected month) | largest ±3-month curve change | month | rank of 320 |
|---|---|---|---|---|
| B | Brent last-trading-day rule changed from the Mar 2016 contract (2016-03) | 3.7× median | 2016-03 | 33 |
| RB | RBOB listed from Oct 2005 (Jan 2006 contract); unleaded gasoline not in Norgate (2006-01) | 5.4× median | 2006-01 | 37 |
| HO | No. 2 heating oil -> NY Harbor ULSD from the May 2013 contract (SER-6198) (2013-05) | 5.5× median | 2013-03 | 22 |
| G | ICE gasoil 0.1% sulphur -> 10 ppm low sulphur gasoil from the Feb 2015 contract (2015-02) | 4.2× median | 2014-12 | 22 |
| KE | KC HRW wheat moved from KCBT to CBOT (trade date 16 Dec 2013) (2013-12) | 3.7× median | 2014-02 | 31 |
| LE | steer weight ceiling raised from the Feb 2021 contract (2021-02) | 6.2× median | 2021-01 | 14 |
| LE | redelivery ban from the Feb 2022 contract (2022-02) | 5.6× median | 2022-01 | 19 |
| GF | Feeder Cattle Index weight band 650-849 lb -> 700-899 lb from the Nov 2016 contract (2016-11) | 3.9× median | 2017-01 | 35 |
| HE | CME Lean Hog Index redefined (negotiated formula purchases), effective 11 Oct 2016 (2016-10) | 5.8× median | 2016-10 | 2 |

- **HO around May 2013** (old heating oil Apr-2013 against the first ULSD May-2013 contract): the curve's largest
  change near the switch is 5.5× the median (2013-03), ranked 22nd of 320. HO's biggest curve moves are in 2003 and
  2026. There is no outsized jump at the ULSD switch.
- **Gasoil around Feb 2015**: 4.2× (2014-12), ranked 22nd. No outsized jump.
- **Lean hogs, October 2016 (index redefinition)**: 5.8× in 2016-10, **the second-largest curve change in HE's
  2000–2026 history**. This is the one change that coincides with a visible curve break. It matters for T20/T21,
  since HE is on Option B, which uses carry_log(F1, F2), and not for T22.
- **LE in 2021-01 and 2022-01** (around the weight-ceiling and redelivery rule changes): 6.2× (ranked 14th) and 5.6×
  (ranked 19th). Moderate.
- **B, KE and GF changes** rank 31st–35th, so they are unremarkable.
- **Unit breaks.** A unit break is a non-reversing same-contract daily move above 30%. There is one each in CL (21
  April 2020, CLM20 at the negative-price episode) and SI (SI-2026H on 2026-01-30). Both are genuine. No price-unit
  rescaling was found.

**Data gaps from COVERAGE.md inside 2000–2026.** 56 contracts and 2,299 contract-days have no row on a market day
inside their own range. They are in B, CL, CT, G, GC, HG, HO, KE, NG, PA, RB, SI, ZL, ZM and ZW. HE's apparent
one-day gaps are the final-settlement artefact in §2 and are not counted.
- **Large gaps.** The large ones (ZM-2007V 292 days, ZM-2019N/V/Z 216 each, NG-2036V 163, ZW-2007N 125, HG-2003N
  124, KE-2009K 64) all fall in the contracts' early, far-deferred life, more than a year before they could become
  F1 or F2.
- **Gaps that touch the roll rule's contracts.** Only three are near a decision date on which the contract had a
  role, all as F13 candidates: HO-2008G and HO-2008H on 2007-01-02, and GAS-2002N in July 2001. HO-2008H was F13 on
  the 2007-01 decision date with no settlement, so it counts as one missing F13 date in HO's A7 share (98.75%, Option
  A regardless).
- **None affects F1 or F2,** so none affects the roll rule or the A2 coverage.

## 9. Databento spend

| item | US$ |
|---|---|
| quoted total for the 306 planned requests (303 downloaded; KE 2010–2012 have no GLBX symbols) | 5.1383 |
| downloaded (sum of the quotes obtained immediately before each request) | 5.1383 |
| one probe request (4 contracts, 3 days) before the run | 0.0003 |
| one CL 2021 request interrupted when the run was restarted for parallel downloads (not in the ledger, at most its quote) | ≤ 0.04 |
| **this session, total** | **≤ 5.18** |

The session cap was US$40. Cumulative account spend cannot be read through Databento's API: it has cost quotes but no
billing endpoint. This repository records no earlier Databento use. The cumulative cap of US$100 is therefore
exceeded only if the account had already spent more than about US$94.8 before this session, which should be checked
in the Databento portal. Every request was quoted with `metadata.get_cost` first, and the per-request ledger is in
the private data repo (`norgate/derived/build0/databento/ledger.jsonl`).
