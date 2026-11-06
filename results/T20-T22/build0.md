# Build 0 — commodity data acceptance tests for trials T20–T22

**Status (re-run 2026-11-06): every test A1–A11 passes under the pre-registration as amended.** A4 is reported but
no longer gates the trials (Amendment 4). A6 holds under the roll-rule guard of Amendment 3 and the missing-month rule
of Amendment 4.4. T20–T22 may proceed.

| item | value |
|---|---|
| pre-registration | `docs/prereg/T20-T22_commodity_trials.md` §6 (A1–A11), with Amendment 1 (`023c829`), Amendment 2 (`6ac4616`, no Build 0 change), Amendment 3 (`869c73e`: roll-rule guard for markets whose notice date is the last trade date) and Amendment 4 (`4ea2bfe`: A4 not gating; missing-month rule for vendor gaps). The pre-registration text above its amendments is not modified. |
| report path | the pre-registered `results/T20-T22/build0.md` (first committed as `results/build0_commodity_data.md`); aggregate statistics in `results/T20-T22/build0.json` and `build0_a5.json`; the A4 diagnostic in `build0_a4_diagnostic.md` |
| code | `em_macro/commod_data.py` (contract tables, calendars, the roll rule with Amendment 3, F1/F2/F13, chained same-contract index), `em_macro/commod_build0.py` (A1–A4, A6, A7, A9–A11, extra checks), `em_macro/commod_databento.py` (A5), `scripts/norgate_export.py` (exports), `tests/test_commod_data.py` (A6, A9 and A11 as tests: synthetic tests always run, data-backed ones need the private data) |
| primary source | Norgate, in the private repo `EthanC100/em-macro-data`: commodity contracts `norgate/2026-11_futures/` (as of 2026-11-05); T22 financial futures `norgate/2026-11_financials/` and per-contract metadata for all markets `norgate/2026-11_metadata/` (both exported 2026-11-06 on horizons-norgate, commit `bd24f9d`; first notice date, first/last quoted date, point value, tick size, currency) |
| benchmarks | AQR *Commodities for the Long Run* (to 2025-05) and *Century of Factor Premia* (to 2026-02), downloaded 2026-11-05, kept outside this repository |
| cross-check | Databento GLBX.MDP3 `statistics` (settlement prices), 2010-06-07 to 2026-10 |
| licence | This repository holds code, this report and aggregate statistics only. Contract and roll tables, return series, the A3/A4 series, Databento settlements and per-day comparisons are private (`em-macro-data/norgate/derived/build0/`). |
| blindness | No T20, T21 or T22 sleeve return, Sharpe ratio, drawdown or pass criterion was computed in Build 0. |

## 1. Result (re-run with Amendments 3 and 4 and the follow-up exports)

| test | threshold | measured | result |
|---|---|---|---|
| A1 assembly | all 34 markets have contract tables and FND/LTD metadata from the primary source, or are recorded unavailable | 31 markets with contract tables and Norgate metadata: 24 commodities and 7 financial futures (6E, 6B, 6M, FGBL, FOAT, FBTP, Long Gilt). 3 recorded unavailable (6L, 6Z, FBON: not in Norgate). FND from Norgate's `first_notice_date` wherever Norgate has one (metals, grains, KC, CC, CT, LE, Long Gilt); none exists for the other markets, whose notice date is the LTD. LTD from Norgate: final settlement for expired contracts, `last_quoted_date` (scheduled expiry) for live ones. | **PASS** |
| A2 F1/F2 coverage, 20-market universe | ≥ 18 markets ≥ 95% since 2000-01 | **20 of 20** at 100.0% | **PASS** |
| A3 equal-weight index vs AQR *Commodities for the Long Run* | ≥ 0.90 | **0.975** (424 months, 1990-02..2025-05) | **PASS** |
| A4 carry portfolio vs AQR carry factor | ≥ 0.70 (gating until Amendment 4) | **0.498** (434 months, 1990-01..2026-02); the A4 diagnostic: AQR's own construction on these data 0.679 | reported, **not gating** (Amendment 4) |
| A5 Databento cross-check, CME-group markets from 2010-06-06 | within one tick on ≥ 99% of days, per market | **21 of 21** pass: 18 commodities and 6E, 6B, 6M; 20 at 100.000%, PA 99.976% | **PASS** |
| A6 roll-rule tests | all assertions hold on the full history | April 2020 → CLM20; notice(F1) > execution + 35 days on every rebalance; **no held F1 or F2 inside its last 10 trading days in any of the 31 markets** (Amendment 3); first settlement on or before t for every contract used (Amendment 4.4: 13 platinum months and 22 palladium months in 2000–2009 whose F2 has no Norgate settlement are missing months); no LME series | **PASS** |
| A7 Option A availability (T20) | table in the report, from availability only | Option A for 14 markets, B for 6 (B, G, KE, LE, GF, HE): §3 | **PASS** |
| A8 no peeking | no return, Sharpe, drawdown or P&L of any sleeve or signal | reviewed before this commit: counts, shares, correlations, dates and tick-agreement rates only | **PASS** |
| A9 data quality | none unresolved | no held F1 contract has a gap over 5 days; 48 F2 gap runs over 5 days, all in series no trial holds (PL and PA F2 16; Long Gilt F2 32: T21 holds F2 only for its 20 commodities, T22 holds F1 only); 17 fully reversing 8-MAD spikes, all confirmed by the adjacent contract the same day; 204 limit-lock flags (flagged) | **PASS** |
| A10 T22 financial futures | each ≥ 95% or dropped and recorded | 6E, 6B, 6M, FGBL, FOAT, FBTP, Long Gilt **100%** each since the later of 2000-01 and entry; 6L, 6Z, FBON dropped (not in Norgate) | **PASS** |
| A11 F2 and F13 listed when used | holds | 0 violations in 31 markets | **PASS** |

**Markets dropped mechanically.** **PA** fails the coverage gate (§2.1 rule 1: 93.15%) and is out of every trial.
**6L, 6Z, FBON** are not in the primary source and are out of T22. Platinum stays in T22 (95.95%), and its 13
uncovered months are missing months under Amendment 4.4.

**T22 universe: 30 instruments.** These are 23 commodities (all 24 except PA) and 7 financial futures (6E, 6B, 6M,
FGBL, FOAT, FBTP, Long Gilt). **T20 and T21: 20 markets**, as amended.

## 2. Changes from the previous Build 0 run, each with its cause

The first run (`a2c85ae`, then `4fe6e27` after the A4 diagnostic's data fix) used the pre-registered roll rule,
exchange-rule first-notice dates and no financial futures. Every value that moved is listed here with its cause.

| test | previous | now | cause |
|---|---|---|---|
| A1 | 24 commodity markets; FND from exchange rules; 7 financial futures not exported | 31 markets with tables; FND and live LTD from Norgate's metadata | follow-up exports (approved) |
| A2 | 20 of 20 at 100% | unchanged | — |
| A3 | 0.9746 | 0.9754 | Amendment 3 changes F1 in G (312 months), HE (213), B (192), GF (8), CL (3): 0.97541 with Amendment 3 alone; Norgate's LE first-notice dates change F1 in 12 LE months: −0.00003 |
| A4 | 0.503 (gating) | 0.498 (not gating) | Amendments 3 and 4; metadata (LE) |
| A5 | 18 of 18 pass; HE 99.976% (2 days with a Databento zero settlement record) | 21 of 21 pass; HE 100% | Amendment 3 moves HE's F1 away from the two contract-days with Databento's zero records; 6E, 6B, 6M added by the export. The other 17 markets are unchanged. |
| A6 | fails: last-10-days in G, HE, B, GF, CL; 35 PL/PA F2 picks before their first settlement | passes in 31 markets | Amendment 3 (guard; applied also to 6E, 6B, 6M, FGBL, FOAT, FBTP, whose Norgate metadata shows no first notice date before the LTD); Amendment 4.4 |
| A7 shares | B 82.9%, G 71.7%, HE 75.0%, LE 61.3% | B 82.5%, G 73.3%, HE 61.7%, LE 62.9% | B, G, HE: Amendment 3 (different F1, so a different F13 target). LE: Norgate's first-notice dates. **Option A/B assignment unchanged.** |
| A9 | 16 F2 gaps (PL, PA), 14 spikes, 203 limit-lock flags | 48 F2 gaps, 17 spikes, 204 flags | +32 Long Gilt F2 gaps and +3 6M spikes (curve-confirmed): the financial exports. Limit-lock flags move between markets with their contracts: GF F1 17→15 and HE F2 12→15 (Amendment 3), LE F1 14→16 and F2 15→13 (LE metadata). |
| A10 | not run | 7 of 7 at 100% | follow-up exports |
| A11 | 0 | 0 | — |

**Live cattle.** Norgate's LE first notice date is 1–6 business days after the first business day of the contract
month, around the 7th. The exchange-rule date used in the first run, the first business day, is superseded by the
primary source. **Cocoa.** Norgate's CC dates follow the pre-2016 ICE rule (five business days earlier) and the
current rule after 2016; no F1 changes. Norgate's dates agree exactly with the exchange rules for the metals,
grains and Long Gilt, and to within two business days for KC and CT.

## 3. A1 — contract tables and metadata

| market | Norgate | designated contracts (live) | notice(T) | FND source | Norgate FND vs exchange rule, expired 2000–2026: exact / within 2 bd (n) | LTD rule vs Norgate final bar: exact / within 2 bd | notes |
|---|---|---|---|---|---|---|---|
| CL | CL | 565 (123) | LTD | none (notice = LTD) | — | 98.4% / 100.0% |  |
| B | BRN | 590 (147) | LTD | none (notice = LTD) | — | 36.2% / 40.2% | pre-2016 contracts under the old LTD rule |
| RB | RB | 289 (38) | LTD | none (notice = LTD) | — | 100.0% / 100.0% | RBOB only, from 2005-10; entry 2006-12 |
| HO | HO | 480 (38) | LTD | none (notice = LTD) | — | 100.0% / 100.0% | vendor splice heating oil → ULSD (May 2013) |
| NG | NG | 568 (119) | LTD | none (notice = LTD) | — | 98.1% / 100.0% | 11 stray far quotes (2036X–2037U) flagged |
| G | GAS | 516 (74) | LTD | none (notice = LTD) | — | 99.4% / 100.0% | vendor splice gasoil → 10 ppm (Feb 2015) |
| HG | HG | 210 (26) | min(FND, LTD) | Norgate | 100.0% / 100.0% (160) | 100.0% / 100.0% |  |
| GC | GC | 241 (20) | min(FND, LTD) | Norgate | 100.0% / 100.0% (181) | 98.8% / 100.0% |  |
| SI | SI | 200 (16) | min(FND, LTD) | Norgate | 100.0% / 100.0% (150) | 99.3% / 100.0% |  |
| PL | PL | 160 (12) | min(FND, LTD) | Norgate | 100.0% / 100.0% (120) | 81.5% / 100.0% | far F2 months unlisted in Norgate 2000–05 (A6, Amendment 4.4) |
| PA | PA | 159 (12) | min(FND, LTD) | Norgate | 100.0% / 100.0% (119) | 80.4% / 99.1% | same, 2000–09; coverage 93.15% → dropped |
| ZC | ZC | 197 (13) | min(FND, LTD) | Norgate | 100.0% / 100.0% (147) | 95.5% / 100.0% |  |
| ZS | ZS | 275 (17) | min(FND, LTD) | Norgate | 100.0% / 100.0% (205) | 94.1% / 100.0% |  |
| ZW | ZW | 198 (14) | min(FND, LTD) | Norgate | 100.0% / 100.0% (148) | 94.8% / 100.0% |  |
| KE | KE | 198 (14) | min(FND, LTD) | Norgate | 100.0% / 100.0% (148) | 82.8% / 82.8% | KCBT rules before 2013 |
| ZM | ZM | 315 (17) | min(FND, LTD) | Norgate | 100.0% / 100.0% (235) | 94.4% / 100.0% | 2029N/V/Z stopped quoting 2026-09-29, flagged |
| ZL | ZL | 315 (17) | min(FND, LTD) | Norgate | 100.0% / 100.0% (235) | 94.4% / 100.0% | 2029N/V/Z stopped quoting 2026-09-29, flagged |
| SB | SB | 159 (11) | LTD | none (notice = LTD) | — | 99.1% / 100.0% |  |
| KC | KC | 191 (7) | min(FND, LTD) | Norgate | 93.6% / 100.0% (141) | 95.5% / 99.3% |  |
| CC | CC | 194 (10) | min(FND, LTD) | Norgate | 23.6% / 23.6% (144) | 92.5% / 99.3% | Norgate FND follows the pre-2016 ICE rule, then the current one |
| CT | CT | 198 (14) | min(FND, LTD) | Norgate | 98.0% / 100.0% (148) | 96.3% / 99.3% |  |
| LE | LE | 231 (10) | min(FND, LTD) | Norgate | 0.0% / 29.8% (171) | 100.0% / 100.0% | Norgate FND ≈ first business Monday (~7th); my rule (1st business day) superseded |
| GF | GF | 304 (9) | LTD | none (notice = LTD) | — | 65.6% / 84.7% | Nov/holiday LTD exceptions |
| HE | HE | 294 (11) | LTD | none (notice = LTD) | — | 99.5% / 100.0% | 92 final-settlement rows corrected; May not listed before 2002 |
| 6E | 6E | 131 (20) | LTD | none (notice = LTD) | — | 100.0% / 100.0% |  |
| 6B | 6B | 167 (20) | LTD | none (notice = LTD) | — | 100.0% / 100.0% |  |
| 6M | 6M | 146 (20) | LTD | none (notice = LTD) | — | 100.0% / 100.0% |  |
| FGBL | FGBL | 114 (3) | LTD | none (notice = LTD) | — | 100.0% / 100.0% |  |
| FOAT | FOAT | 61 (3) | LTD | none (notice = LTD) | — | 98.3% / 100.0% | listed 2012; entry 2013-06 |
| FBTP | FBTP | 71 (3) | LTD | none (notice = LTD) | — | 100.0% / 100.0% | listed 2009; entry 2010-11 |
| R | LLG | 150 (3) | min(FND, LTD) | Norgate | 100.0% / 100.0% (110) | 100.0% / 100.0% |  |
| 6L | — | — | — | — | — | — | not in Norgate → unavailable, dropped from T22 |
| 6Z | — | — | — | — | — | — | not in Norgate → unavailable, dropped from T22 |
| FBON | — | — | — | — | — | — | not in Norgate → unavailable, dropped from T22 |

## 4. A7 — Option A/B assignment for T20 (availability only)

Share of design-sample decision dates (2000-01..2019-12, after entry) with an eligible F13 settlement; Option A if
≥ 90%.

| market | share | option | market | share | option |
|---|---|---|---|---|---|
| CL | 100.0% (240/240) | A | B | 82.5% (198/240) | B |
| RB | 98.1% (154/157) | A | HO | 98.8% (237/240) | A |
| NG | 100.0% (240/240) | A | G | 73.3% (176/240) | B |
| HG | 100.0% (240/240) | A | ZC | 99.6% (239/240) | A |
| ZS | 91.2% (219/240) | A | ZW | 90.0% (216/240) | A |
| KE | 84.6% (203/240) | B | ZM | 95.8% (230/240) | A |
| ZL | 96.7% (232/240) | A | SB | 100.0% (240/240) | A |
| KC | 100.0% (240/240) | A | CC | 100.0% (240/240) | A |
| CT | 100.0% (240/240) | A | LE | 62.9% (151/240) | B |
| GF | 0.0% (0/240) | B | HE | 61.7% (148/240) | B |

## 5. A5 — Databento cross-check (CME-group markets)

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
| HE | 8,166 | 16 | ×1 | 100.000% | 0 | PASS |
| 6E | 8,180 | 8 | ×1 | 100.000% | 0 | PASS |
| 6B | 8,180 | 8 | ×1 | 100.000% | 0 | PASS |
| 6M | 8,178 | 10 | ×1 | 100.000% | 0 | PASS |

All 21 CME-group markets pass.
- **PA.** Two days are 2 ticks apart (2020-12-04, 2022-09-22).
- **KE.** Cross-checked from December 2013, when it moved to CBOT; its KCBT contracts are not in GLBX.MDP3.
- **Long Gilt and Eurex.** Not CME-group, so outside A5; the ICE commodities are likewise outside A5 by instruction.

## 6. A10 — T22 financial futures

| market | Norgate | first contract | entry | coverage since the later of 2000-01 and entry | result |
|---|---|---|---|---|---|
| 6E | 6E | 6E-1999H | 2000-03 | 100.0% (319/319, from 2000-03) | PASS |
| 6B | 6B | 6B-1990H | 1991-02 | 100.0% (321/321, from 2000-01) | PASS |
| 6M | 6M | 6M-1995M | 1996-06 | 100.0% (321/321, from 2000-01) | PASS |
| FGBL | FGBL | FGBL-1999H | 2000-03 | 100.0% (319/319, from 2000-03) | PASS |
| FOAT | FOAT | FOAT-2012M | 2013-06 | 100.0% (160/160, from 2013-06) | PASS |
| FBTP | FBTP | FBTP-2009Z | 2010-11 | 100.0% (191/191, from 2010-11) | PASS |
| R | LLG | LLG-1990H | 1991-02 | 100.0% (321/321, from 2000-01) | PASS |
| 6L | — | — | — | not in the primary source | dropped and recorded |
| 6Z | — | — | — | not in the primary source | dropped and recorded |
| FBON | — | — | — | not in the primary source | dropped and recorded |

## 7. A6 — roll rule under Amendments 3 and 4.4

| market | notice | F1 last-10 violations | F2 last-10 violations | fewest trading days left at exit | chosen contracts without a settlement on t (Amendment 4.4) |
|---|---|---|---|---|---|
| CL | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| B | LTD (Amendment 3 guard) | 0 | 0 | 18 | 0 |
| RB | LTD (Amendment 3 guard) | 0 | 0 | 17 | 0 |
| HO | LTD (Amendment 3 guard) | 0 | 0 | 16 | 0 |
| NG | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| G | LTD (Amendment 3 guard) | 0 | 0 | 24 | 0 |
| HG | min(FND, LTD) | 0 | 0 | 35 | 0 |
| GC | min(FND, LTD) | 0 | 0 | 35 | 0 |
| SI | min(FND, LTD) | 0 | 0 | 35 | 0 |
| PL | min(FND, LTD) | 0 | 0 | 35 | 13 |
| PA | min(FND, LTD) | 0 | 0 | 34 | 22 |
| ZC | min(FND, LTD) | 0 | 0 | 27 | 0 |
| ZS | min(FND, LTD) | 0 | 0 | 27 | 0 |
| ZW | min(FND, LTD) | 0 | 0 | 27 | 0 |
| KE | min(FND, LTD) | 0 | 0 | 27 | 0 |
| ZM | min(FND, LTD) | 0 | 0 | 26 | 0 |
| ZL | min(FND, LTD) | 0 | 0 | 26 | 0 |
| SB | LTD (Amendment 3 guard) | 0 | 0 | 17 | 0 |
| KC | min(FND, LTD) | 0 | 0 | 27 | 0 |
| CC | min(FND, LTD) | 0 | 0 | 25 | 0 |
| CT | min(FND, LTD) | 0 | 0 | 19 | 0 |
| LE | min(FND, LTD) | 0 | 0 | 14 | 0 |
| GF | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| HE | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| 6E | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| 6B | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| 6M | LTD (Amendment 3 guard) | 0 | 0 | 11 | 0 |
| FGBL | LTD (Amendment 3 guard) | 0 | 0 | 24 | 0 |
| FOAT | LTD (Amendment 3 guard) | 0 | 0 | 24 | 0 |
| FBTP | LTD (Amendment 3 guard) | 0 | 0 | 24 | 0 |
| R | min(FND, LTD) | 0 | 0 | 36 | 0 |

## 8. Decisions taken under the task's rules

1. **Primary-source metadata (A1).** FND is Norgate's `first_notice_date` where Norgate has one. LTD is Norgate's
   final settlement for expired contracts and Norgate's `last_quoted_date` (scheduled expiry) for live contracts.
   - **Lean hogs:** the final-settlement row is corrected, so LTD = the bar before the gap.
   - **Contracts that stopped quoting more than 30 days early** (NG 2036X–2037U, ZM and ZL 2029N/V/Z) keep the
     exchange-rule LTD and are flagged. None is ever used.
2. **Amendment 3 scope.** The guard applies to every market whose notice date equals its LTD in the metadata: CL, B,
   RB, HO, NG, G, SB, GF, HE, 6E, 6B, 6M, FGBL, FOAT, FBTP. This was approved, including financial futures the
   metadata reveals.
3. **A5 re-run.** The A5 comparison was re-planned on the amended roll tables. Contracts not already downloaded
   were requested from Databento, each quoted first; cached contract-years were reused.
4. **Unchanged from the first run** (`a2c85ae`, §7 there):
   - trading calendar = union of settlement dates; execution on the first settlement on or after the 3rd;
   - A3/A4 construction (A4 with the diagnostic's first-month fix);
   - A9 thresholds (8 rolling MADs; a reversal is a two-day move within 10% of the first day's);
   - A11 "used" = has a settlement on the decision date.

## 9. Extra checks (report only)

**Specification changes inside 2000–2026.** Each row shows the largest month-on-month change of ln(F2/F1) on
decision dates within ±3 months of the change, as a multiple of the market's median absolute change, and its rank.
Ranks differ from the first run because Amendment 3 changes some F1/F2 pairs.

| market | change (first affected month) | largest ±3-month curve change | month | rank |
|---|---|---|---|---|
| B | Brent last-trading-day rule changed from the Mar 2016 contract (2016-03) | 3.9× median | 2016-03 | 22 of 320 |
| RB | RBOB listed from Oct 2005 (Jan 2006 contract); unleaded gasoline not in Norgate (2006-01) | 5.4× median | 2006-01 | 37 of 250 |
| HO | No. 2 heating oil -> NY Harbor ULSD from the May 2013 contract (SER-6198) (2013-05) | 5.5× median | 2013-03 | 22 of 320 |
| G | ICE gasoil 0.1% sulphur -> 10 ppm low sulphur gasoil from the Feb 2015 contract (2015-02) | 5.6× median | 2014-11 | 18 of 320 |
| KE | KC HRW wheat moved from KCBT to CBOT (trade date 16 Dec 2013) (2013-12) | 3.7× median | 2014-02 | 31 of 320 |
| LE | steer weight ceiling raised from the Feb 2021 contract (2021-02) | 6.2× median | 2021-01 | 15 of 320 |
| LE | redelivery ban from the Feb 2022 contract (2022-02) | 5.6× median | 2022-01 | 20 of 320 |
| GF | Feeder Cattle Index weight band 650-849 lb -> 700-899 lb from the Nov 2016 contract (2016-11) | 3.9× median | 2017-01 | 36 of 320 |
| HE | CME Lean Hog Index redefined (negotiated formula purchases), effective 11 Oct 2016 (2016-10) | 5.3× median | 2016-09 | 14 of 320 |

Heating oil's switch to ULSD (May 2013) and gasoil's switch to 10 ppm (Feb 2015) both rank 22nd of 320, with no
outsized jump. The lean-hog index redefinition (Oct 2016) now ranks 14th: under Amendment 3, HE's F1/F2 pairs
differ, and in the first run it ranked 2nd. **No price-unit break.** The only non-reversing same-contract moves
above 30% are CL on 2020-04-21 (CLM20) and SI on 2026-01-30 (SI-2026H), both genuine.

**Data gaps from COVERAGE.md inside 2000–2026.** These are unchanged in substance from the first run (§8 there):
- 56 contracts, 2,299 contract-days, nearly all in contracts' far-deferred early life.
- Only F13 candidates are near a decision date (HO-2008G/H on 2007-01-02, GAS-2002N in July 2001).
- None affects F1 or F2.

The financial futures add Long Gilt F2 gaps, which no trial holds.

## 10. Server and Databento

- **Auto-logon on horizons-norgate** (approved 2026-11-06) now starts NDU at boot. The setup, its reboot test and
  how to undo it are in `docs/infra/aws_norgate_server.md`. The Administrator password was replaced by a random one
  stored only as SecureString `/horizons/windows/administrator-password`.
- **Databento spend:**
  - **2026-11-06:** US$0.55 over 62 requests, each quoted first, plus at most a few cents for a stream cut by a
    connection reset.
  - **Session ledger total:** US$5.69 over 365 requests (including the 2026-11-05 run).
  - **Earlier, outside the ledger:** a probe of US$0.0003 and one interrupted request of at most US$0.04.

  Both caps (US$40 per session, US$100 cumulative) are far away.
