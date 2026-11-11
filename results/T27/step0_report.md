# T27 Step 0: applicability check (no returns computed)

Run 2026-11-11 under `docs/prereg/T27_managed_fx_vol_floor.md` §3.3 (`python -m em_macro.t27_floor step0`).
Outputs: `STEP0.json`, `step0_managed_matrix.csv`, `step0_managed_months.csv`. Inputs: `data/kept/T27/`
(classification, editions, Annual Report cross-check, and the manifest of the source PDFs; the PDFs themselves are
in `T27_imf_areaer_raw_2026-11-11.tar.gz` in the private repository `EthanC100/em-macro-data`, `kept/T27/`).
v1.0 reproduced byte for byte on its frozen input snapshots before the count. No T27 weight or return was computed.
The counts use v1.0's own 36-month σ and FX selections.

**Disclosure (pre-registration header):** the idea was prompted by TRY's managed path and its 2018 and 2021
devaluations. 2021 is inside the confirmatory window, so a pass would be weaker evidence than a clean out-of-sample
result.

## Sources obtained

| AREAER edition (as of 30 April) | obtained | publication date used | first decision month |
|---|---|---|---|
| 2003–2011 | **no** (IMF eLibrary refuses this session, 403; no other copy reachable) | 2003-09-03 … 2011-11-01 | — |
| 2012 | yes | 2012-10-31 (imf.org 14 Sep 2012; footer October 2012) | 2012-11 |
| 2013 | yes, corrected online version | 2014-05-22 (errata: Table 1 corrected May 2014) | 2014-06 |
| 2014 | yes | 2014-10-17 | 2014-11 |
| 2015 | yes | 2015-10-01 | 2015-11 |
| 2016 | yes | 2016-11-11 | 2016-12 |
| 2017 | yes | 2018-09-30 (sources disagree, from April to September 2018; the latest is used) | 2018-10 |
| 2018 | yes | 2019-04-24 | 2019-05 |
| 2019 | yes | 2020-08-10 | 2020-09 |
| 2020, 2021 | **no** (no PDF on imf.org; eLibrary 403) | 2021-08-25, 2022-07-19 | — |
| 2022 | yes | 2023-07-26 | 2023-08 |
| 2023 | yes; **the latest edition** (no 2024 or 2025 edition published yet) | 2024-12-19 | 2025-01 |

Where sources disagree on a publication date, the latest documented date is used (no look-ahead). This choice
changes no managed month for the ten currencies, except that the 2013 edition (IDR crawl-like) starts in 2014-06
instead of 2014-01; IDR's σ was above q_t in those months, so the binding count does not change.

## TRY's classification, editions from 2017 on

| source | as of | TRY | managed? | in force for decisions |
|---|---|---|---|---|
| AREAER 2017 | 2017-04-30 | Floating | no | 2018-10 .. 2019-04 |
| AREAER 2018 | 2018-04-30 | Floating | no | 2019-05 .. 2020-08 |
| AREAER 2019 | 2019-04-30 | Floating | no | 2020-09 .. 2021-08 |
| AREAER 2020 | 2020-04-30 | not obtained (IMF Annual Report 2020 appendix: Floating) | unknown | 2021-09 .. 2022-07 |
| AREAER 2021 | 2021-04-30 | not obtained (IMF Annual Report 2021 appendix: Floating) | unknown | 2022-08 .. 2023-07 |
| AREAER 2022 | 2022-04-30 | Floating | no | 2023-08 .. 2024-12 |
| AREAER 2023 | 2023-04-30 | **Crawl-like arrangement** (reclassified from floating effective 28 July 2022) | **yes** | 2025-01 .. 2026-09 |
| IMF Annual Report 2024 / 2025 / 2026 (not AREAER) | 2024 / 2025 / 2026-04-30 | Crawl-like arrangement | context only | — |

Under the pre-registered timing, TRY counts as managed only from 2025-01: 30 months after the IMF dated the change
(July 2022) and after both the 2018 and 2021 devaluations. The 2018 and 2021 episodes were classified as floating
in every edition in force at the time.

The other managed spells among the ten currencies are both IDR:
- **2013 edition** (crawl-like): in force 2014-06..2014-10.
- **2018 edition** (stabilised from 12 January 2017): in force 2019-05..2020-08. The 2019 edition reversed this
  retroactively, to floating from 1 January 2018, but the rule uses each edition as printed.

Every other currency is floating or free floating in every obtained edition.

## Counts (currency-months)

| window | managed | managed and selected | **floor binds** | binding months | classification unknown |
|---|---|---|---|---|---|
| 2005-01..2019-12 | 13 (IDR) | 4 (IDR) | **0** | — | 2005-01..2012-10 (94 months; 282 selected currency-months with σ below q_t) |
| 2020-01..2026-09 | 29 (TRY 21, IDR 8) | 23 (TRY 21, IDR 2) | **6** (IDR 2, TRY 4) | IDR 2020-05, 2020-06; TRY 2026-06..2026-09 | 2021-09..2023-07 (23 months; 84 selected currency-months with σ below q_t: COP, EUR, GBP, IDR, MXN, PLN) |

From 2025-01 to 2026-05, TRY is managed and selected, but its 36-month σ (13.7–15.2%) is above the EM median
(10.1–13.0%), so the floor does not bind. In 2026-06, TRY's σ falls to 5.1%, then to 4.1% by 2026-09, while q_t is
about 9.2–9.6%, and the floor binds. This coincides with June 2023, the month of the lira's large fall, leaving the 36-month window.

**Not degenerate:** the floor binds in 6 currency-months of the confirmatory window, so the trial is not "not run"
under §3.3.

## Open: the editions that could not be obtained (needs the owner)

1. **2020 and 2021 editions (confirmatory window, decisions 2021-09..2023-07).** These months are unknown under the
   strict rule. Two sources point the same way:
   - The IMF Annual Report appendices (same AREAER database, as of April 2020 and April 2021) list all ten currencies
     as floating or free floating.
   - The 2022 edition's reclassification table (May 2021–April 2022) lists none of the ten, so the 2021 edition
     matches the 2022 edition for them: none managed.

   If the two editions match these sources, the binding count stays 6. Option: obtain the two PDFs (the IMF eLibrary
   works from a normal browser), or approve the Annual Report appendices as stand-ins, with the AREAER publication
   dates kept.
2. **2003–2011 editions (exploration window, decisions 2005-01..2012-10).** They are needed for the exploration gate.
   The 2012 edition's change table shows IDR leaving a stabilised arrangement on 14 February 2011, so earlier
   editions probably classify IDR as managed for part of 2009–2011. Options:
   - (a) obtain the PDFs;
   - (b) use the IMF's pre-2009 website tables (release dates documented, as of June 2003 to April 2008), plus
     whatever covers 2009–2011;
   - (c) restrict the exploration window to 2012-11..2019-12, where the floor never binds, so the gate passes
     trivially.

   Any of these is an amendment to §3.2 or §4, to be decided before the exploration step.
