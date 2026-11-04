# T02 — economic momentum: data feasibility (Step 2)

Written 2026-11-03 on branch `trial/T02-econ-momentum`, after Step 1 (`T02_econ_momentum_literature.md`) and before
the pre-registration. **No currency or bond return was read, and no signal was computed.** Everything here is about
the availability, dates and publication lags of macro series and their real-time vintages.

Code: `em_macro/t02_data.py` (`download`, `coverage`). Tables: `results/T02/data_coverage_*.csv`. Raw files:
`data/raw/econ_momentum/` (gitignored like every other raw download in this repository; 441 MB; never modified).
Their SHA-256 hashes and sizes are committed in `results/T02/raw_data_manifest.csv`, and `download` recreates them.

## 1. Sources checked

| source | type | what it holds | reachability | used |
|---|---|---|---|---|
| **OECD short-term economic statistics revisions database** (`OECD.SDD.STES/DSD_STES_REVISIONS@DF_STES_REVISIONS`, SDMX API; the successor of the MEI "Original Release Data and Revisions" database) | point-in-time **editions** (one per monthly MEI issue, 1999-02 to 2026-10, 333 editions) | industrial production (`PRVM`), retail trade volume (`TOVM`), consumer prices (`CP`), unemployment rate (`UNEMP`); also GDP components, CLI, trade, M3. **No producer prices.** 60 areas incl. all ten economies | yes, no key; rate-limited (HTTP 403 after bursts of metadata calls; paced data calls fine) | **primary** for nine economies |
| **ECB Real Time Database** (`RTD` dataflow, ECB Data Portal API, `includeHistory=true`) | every published value with a `VALID_FROM` timestamp, from 2001-01-03 | euro-area IP (total, and excl. construction), retail trade (deflated), HICP, standardised unemployment, PPI; "moving concept" euro-area aggregate | yes, no key; needs a browser User-Agent | **primary** for the euro area |
| **ALFRED** (St. Louis Fed) | vintages of FRED series, one request per vintage date (`alfredgraph.csv?id=&vintage_date=`); the multi-vintage form download does not work without a browser | OECD-MEI-sourced series for the OECD economies; FRED stopped updating most of them in 2024-03 and lists vintages only from 2011 (FRED added the OECD series then) | yes, no key; throttled after a burst of parallel requests | **gap filler** (Colombia before 2020, Brazil unemployment 2012–2015, South Africa unemployment, Turkey retail) |
| OECD key short-term economic indicators (`DSD_KEI@DF_KEI`) | latest, **revised** series only | the same four measures plus PPI (PPI ends 2022-12) | yes | **fallback**, flagged as look-ahead |
| OECD prices dataflow (`DSD_PRICES@DF_PRICES_ALL`) | revised | CPI only | yes | not needed |
| national statistics offices and central banks (IBGE/BCB, INEGI/Banxico, Stats SA/SARB, TurkStat/CBRT, BPS/Bank Indonesia, GUS/NBP, ONS/BoE, DANE/BanRep, INE/BCCh) | current, revised series; none of them publishes a machine-readable real-time vintage archive for these series (the ONS revision triangles and the Bundesbank/ECB real-time databases are the only European ones, and only the ECB one covers the euro-area aggregate) | | partly reachable (the repository already has BCB, Banxico, SARB, BanRep and BCCh loaders) | not used in T02; named only where the pre-registration needs a revised fallback that the OECD lacks |
| FRED API with key, SSRN full texts | | | no key in this environment; SSRN blocks downloads | — |

Edition semantics (OECD): an edition `YYYYMM` is the data as published in that month's MEI issue, compiled in the
first half of the month. In the latest edition (2026-10) the last observation is typically 2026-07 or 2026-08, i.e.
a publication lag of 2–3 months, consistent with the national release calendars plus the OECD compilation lag.
Using edition t at the end of month t is therefore conservative: everything in it had been published by then.

## 2. Coverage by country and variable (first-release vintages)

Legend: **V** = point-in-time vintages exist for the period; **(V)** = vintages exist but the series is not updated in
recent editions ("stale from" the edition shown, after which the fallback applies); **R** = only revised data;
**—** = no series at all. "from" is the first vintage/edition; "obs" is the first observation available in the latest
edition; "lag" is the median months between an edition and its last observation.

| country (currency) | IP | retail sales | unemployment | CPI |
|---|---|---|---|---|
| Brazil (BRL) | **V** OECD editions from 2001-01; obs 1990-01; lag 3 | **V** OECD from 2001-11; obs 2000-01; lag 3 | **V** OECD 2001-03 to 2012-05 (old monthly survey; obs 1990-01; lag 2); **R** 2012-06 to 2013-05; ALFRED vintages of `LRUNTTTTBRM156S` from 2013-06-03 (23 vintages) until the series ends in 2015-11; **— after 2015-11** (PNAD Contínua has no vintage source) | **V** OECD from 2001-01; obs 1990-01; lag 2 |
| Mexico (MXN) | **V** OECD from 1999-02; obs 1990-01; lag 3 | **V** OECD from 1999-02; obs 1990-01; lag 3 | **V** OECD from 1999-02; obs 1990-01; lag 2 | **(V)** OECD from 1999-02; stale from edition 2026-04 (last obs 2024-07); lag 2 |
| South Africa (ZAR) | **V** OECD from 2002-06; obs 1990-01; lag 3 | **V** OECD from 2002-06; obs 1990-01; lag 3 | **R** OECD revisions database has none; ALFRED vintages of the quarterly `LRUNTTTTZAQ156S` (obs 2000-07, updated to 2026-04) from 2013-07-01 (50 vintages, to 2026-10); **R** before 2013-07 | **(V)** OECD from 2002-06; stale from 2025-08 (last obs 2025-01); lag 2 |
| Turkey (TRY) | **V** OECD from 1999-02; obs 1990-01; lag 3 | **—** before 2010; **R** 2010-01 to 2018-06 (OECD KEI, obs 2010-01); ALFRED vintages of `TURSLRTTO01IXOBSAM` from 2018-07-17 (34 vintages, to 2025-11; series ends 2024-03); **R** after 2024-03 | **V** OECD from 2006-04; obs 2005-01; lag 4 | **(V)** OECD from 1999-02; stale from 2026-07 (last obs 2025-12); lag 1 |
| Indonesia (IDR) | **V** OECD from 2005-07; obs 1993-01; lag 4; editions missing in 2024 (74 stale editions) | **—** | **—** | **V** OECD from 2001-10; obs 1990-01; lag 1 |
| Poland (PLN) | **V** OECD from 1999-02; obs 1990-01; lag 2 | **V** OECD from 1999-07; obs 1991-01; lag 2 | **V** OECD from 2003-02; obs 1997-01; lag 2 | **(V)** OECD from 1999-02; stale from 2026-07 (last obs 2025-12); lag 2 |
| United Kingdom (GBP) | **V** OECD from 1999-02; obs 1990-01; lag 3 | **V** OECD from 1999-02; obs 1990-01; lag 2 | **V** OECD from 1999-02; obs 1990-01; lag 4 | **V** OECD from 1999-02; obs 1990-01; lag 2 |
| Colombia (COP) | **V** OECD from 2020-05 (obs 1990-01; lag 3; 20 stale editions); ALFRED vintages of manufacturing production `COLPRMNTO01IXOBSAM` from 2018-07-17 (54 vintages); **R** before 2018-07 | **V** OECD from 2020-05 (obs 2013-01); ALFRED vintages of `COLSLRTTO01IXOBSAM` (37) and `COLSLRTTO02IXOBSAM` (12) from 2018-07-17; **R** 2013-01 to 2018-06; **—** before 2013 | **V** OECD from 2020-05 (obs 2007-01); **R** 2007-01 to 2020-04 (no FRED series); **—** before 2007 | **V** OECD from 2020-05 (obs 1990-01); ALFRED vintages of `COLCPALTT01IXOBM` from 2018-07-17 (67 vintages); **R** before 2018-07 |
| Chile (CLP) | **V** OECD from 2010-07; obs 1991-04; lag 2; **R** 2005–2010-06 | **(V)** OECD 2010-06 to 2019-06 (series ends 2018-12; obs 2005-01); **R** before 2010-06; **—** after 2018-12 | **V** OECD from 2010-06; obs 1990-01; lag 3; **R** 2005–2010-05 | **(V)** OECD from 2010-06, stale from 2024-07 (last obs 2023-12); **R** before 2010-06 and after 2023-12 |
| euro area (EUR) | **V** ECB RTD from 2001-01-03 (`I_XCONS`, obs 1980-01, 253 vintage dates; also `I_INDTO`); OECD EA19 editions 2015-02 to 2023-03 and EA20 from 2023-04 as a cross-check | **V** ECB RTD from 2001-01-03 (`O_RTXMOTVD`, obs 1994-01, 248 vintage dates) | **V** ECB RTD from 2001-01-03 (`L_UNETO`, obs 1990-07, 237 vintage dates) | **V** ECB RTD from 2001-01-03 (`P_C_OV`, obs 1990-01, 258 vintage dates) |

Producer prices: first-release vintages exist only for the euro area (ECB RTD `P_P_XCONS_DS`, from 2001). The OECD
revisions database has no PPI; the OECD KEI PPI (revised) covers CHL, COL, EA20, GBR, POL, TUR to 2022-12 only;
FRED's OECD PPI series end in 2022-12. PPI is therefore not usable as a first-release input and is excluded from
the signal (literature document, A2).

**Summary of vintage coverage for the T02 sample (2005-01 to 2026-09).**
- Full first-release coverage of all four components from 2005: **Mexico, Poland, United Kingdom, euro area**
  (CPI editions for Mexico and Poland go stale in 2026, where the revised CPI is substituted; CPI is essentially
  never revised, so the look-ahead risk is nil in practice).
- Three components with vintages from 2005, one missing: **Brazil** (unemployment vintages end in 2015),
  **Turkey** (no retail series before 2010; revised-only after), **South Africa** (unemployment revised-only
  before the first ALFRED vintage; quarterly).
- **Indonesia:** IP (vintages from 2005-07) and CPI only; no retail-sales or unemployment series in any source.
- **Chile:** vintages only from 2010-06; the first 5.5 years of the context sample use revised data, and retail
  sales disappear from the OECD database after 2018-12.
- **Colombia:** OECD vintages only from 2020-05; ALFRED vintages (from 2018-07) cover IP, retail and CPI but not
  unemployment; 2005 to 2018-06 is revised-only. ALFRED's OECD-sourced vintages generally begin in 2013 (Brazil,
  South Africa) or 2018 (Colombia, Turkey), not 2011 as the ALFRED series pages suggest for other series.
- Hence the **decisive window 2020-01..2026-09 is covered by first-release vintages for every component that
  exists**, with these exceptions: Colombia unemployment 2020-01..2020-04 (revised), Chile retail (absent),
  Brazil unemployment (absent), Indonesia retail and unemployment (absent), and the CPI series that went stale in
  the OECD database (Mexico from 2024-08, South Africa from 2025-02, Chile from 2024-01, Turkey and Poland from
  2026-01: revised CPI substituted). The 2005–2019 context period relies on revised data for Chile (to 2010),
  Colombia (to the first ALFRED vintage) and South Africa unemployment.

## 3. Publication lags (first-release editions, months from edition to last observation)

| measure | BRA | MEX | ZAF | TUR | IDN | POL | GBR | COL | CHL | EA (ECB RTD) |
|---|---|---|---|---|---|---|---|---|---|---|
| IP | 3 | 3 | 3 | 3 | 4 | 2 | 3 | 3 | 2 | 3 |
| retail | 3 | 3 | 3 | — | — | 2 | 2 | 3 | 3 | 2 |
| unemployment | 2 | 2 | — | 4 | — | 2 | 4 | 2 | 3 | 2 |
| CPI | 2 | 2 | 2 | 1 | 1 | 2 | 2 | 2 | 2 | 1 |

OECD figures are medians over all editions (edition month minus the month of the last observation); the full
distribution, including the stale tails, is in `results/T02/data_coverage_oecd_revisions.csv`. ECB figures are the
median, since 2010, of the month of the first `VALID_FROM` of each reference period minus that period. The ECB RTD
snapshots series at the ECB's own vintage dates (its bulletin cut-offs, roughly monthly), which fall 2–4 weeks
after Eurostat's release, so the ECB lags above overstate the public lag by up to a month: using them is
conservative.

## 4. Files downloaded (raw, never modified)

| folder | files | content |
|---|---|---|
| `data/raw/econ_momentum/oecd_stes_revisions/` | 43 CSV (one per area × measure; SDMX-CSV, `startPeriod=1990-01`, all editions) + log | 11 areas (incl. EA19 and EA20) × 4 measures, minus the four absent combinations (ZAF UNEMP, TUR TOVM, IDN TOVM, IDN UNEMP) |
| `data/raw/econ_momentum/ecb_rtd/` | 7 CSV (`includeHistory=true`) | euro-area IP ×2, retail ×2, HICP, unemployment, PPI, with `VALID_FROM` per value |
| `data/raw/econ_momentum/oecd_kei_latest/` | 5 CSV + log | revised fallback series, 10 areas, 5 measures |
| `data/raw/econ_momentum/alfred/<series>/` | one CSV per vintage date + the series' download page | 7 FRED series (see §2); vintage counts in `results/T02/data_coverage_alfred.csv` |

Manifest with sizes and SHA-256: `results/T02/raw_data_manifest.csv`.

## 5. What was not obtained, and why it matters

- **No real-time source** for: Brazil unemployment after 2015 (and 2012-06 to 2013-05), South Africa unemployment
  before 2013-07, Turkey retail sales before 2018-07, Indonesia retail sales and unemployment, Colombia
  unemployment before 2020-05, Chile before mid-2010, Colombia before 2018-07. The pre-registration fixes the fallback for each (omit
  the component, or use the revised series lagged three months, flagged).
- **Producer prices:** excluded from the signal.
- **Pre-2005 history for look-backs:** the 60-month look-back needs an index history from 2000 for a 2005
  signal; every vintage carries the full history back to 1990 (OECD) or 1980–1995 (ECB), so this is not a
  constraint; the constraint is the start of the vintages themselves.
- **FRED throttling:** parallel requests were cut off; the downloader is sequential with pauses.
- **Volume:** the raw folder is 441 MB and is gitignored; the manifest and the download code are committed.
