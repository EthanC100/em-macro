# elections_co_cl.csv and govt_events_co_cl.csv: method notes

Scope: Colombia and Chile, 2005-01-01 to 2026-10-29. Compiled 2026-10-29. Every row cites a URL that was fetched in the compiling session (Wikipedia pages were read as raw wikitext via `index.php?action=raw`, current revision). Raw downloads are in /tmp/claude-0/events_cocl/ (not committed).

Important limitation: the shared web-search budget ran out part-way through the session. After that, only pages reachable by direct URL could be used (Wikipedia, IMF, DIPRES, Colombian Senate law database, Polymarket API, Valora Analitik, some news sites). This is why `market_preferred` is blank everywhere and why several budget dates are missing (see gaps below).

## elections_co_cl.csv (42 rows: COL 19, CHL 23)

### Conventions (differences from elections_br_mx_pl.csv)
- **Chile parliamentary rows are separate rows** (`type=legislative`) that share `vote_date` with presidential round 1. De-duplicate on date if needed. Presidential round 1 is `type=presidential`, not `general`. The legislative actual shares are coalition shares of the Chamber of Deputies vote, summed from the parties in each coalition in the Wikipedia results template (SERVEL).
- **Colombia legislative rows** use national Senate list-vote shares, computed from Wikipedia vote counts. The 2006 template may leave out blank votes.
- **Colombian presidential actuals** are shares of valid votes *including* the blank vote (voto en blanco counts as valid in Colombia), computed from Registraduría counts on Wikipedia. As a result, a+b < 100 even in run-offs.
- **Constitutional Convention 2021 and Council 2023** use `type=other_national`. Convention 2021 voting ran over 15-16 May. `vote_date` is the second day.
- `results_known` = `vote_date` for all rows: preliminary counts (Registraduría preconteo, Servel) are released on election night.

### Poll method
- Mean of the last poll by each pollster published before the legal blackout, using fieldwork ending within about 2 weeks of the blackout. Older and thinner windows are used where that was all that existed, as stated in `poll_basis`.
- Candidate shares are as published (undecided included in the base). Yes/no plebiscites are renormalised to two-option shares, except where Wikipedia already lists two-option shares (CL 2022).
- `cand_a` is the poll leader. Where no poll was found, a/b follow the actual top two, and `notes` says so.
- **Blackouts:**
  - **Colombia:** no voting-intention polls may be published in the week (8 days) before an election (Bloomberg Línea, 2026). Ley 2494 de 2025 changed polling rules in 2025-26 and was partly struck down (C-168/26). The Consejo de Estado suspended the CNE power to halt publications in June 2026.
  - **Chile:** 15-day blackout since Ley 20.900 (2016), so it first applied in 2017 (CNN Chile). Earlier rules were looser: Wikipedia lists 2009 polls published 4 days before the vote.
- **Sources:** poll tables come from en/es Wikipedia (including the *Opinion polling for…* and *Anexo: Sondeos/Encuestas…* pages).

### Odds (6 rows)
- **Polymarket**, via the gamma API and CLOB `prices-history` (hourly), taking the vote-day 09:00 UTC price, before polls opened:
  - **CO 2026 R1:** "1st round winner" market. Cepeda was the favourite (0.765/0.245), but de la Espriella led the actual count.
  - **CO 2026 R2:** overall winner market.
  - **CL 2025 R1:** "1st round winner" market (multi-outcome, not normalised).
  - **CL 2025 R2:** overall winner market.
- **CL 2005 R1/R2:** the "Bolsa Electoral" (Universidad de Chile / University of Chicago student play-money market), quoted on es Wikipedia.
- No verifiable pre-vote prices were found for CO 2022 or earlier years.

### Columns left blank on purpose
- **`market_preferred`:** blank in all rows. No fetched press source on market preference could be verified once search was exhausted, so nothing was coded from memory. Obvious candidates for a follow-up coding pass: CO 2018/2022/2026 (right-of-centre candidate), CO 2016 (Yes), CL 2017/2021/2025 (Piñera/Kast), CL 2022 (Rechazo).
- **No polls:**
  - CO 2006 presidential: no poll table on Wikipedia.
  - CO legislative 2006/2010/2022/2026: no polls, or only one early ambiguous poll.
  - CO 2018 anti-corruption consultation.
  - All Chile parliamentary rows.
  - CL Convention 2021.

### Rows to treat with care
- **CO 2026 (both rounds):** very recent; the Wikipedia pages are still being edited.
- **CO 2014 R1/R2, CO 2022 R2:** the poll leader is within about 0.5pp, so the a/b ordering is fragile. In CO 2022 R2, 4 of 6 pollsters had Hernández ahead.
- **CL 2005 R1/R2:** month-only or undated polls (`poll_date` blank).
- **Single or thin polls:** CL 2013 R2 and CO 2010 R2 rest on one poll each. CL 2009 R2 and CL 2017 R2 use 2 polls with mixed bases. CL 2023 Council uses 2 early polls with 40-60% undecided. CL 2023 plebiscite uses 2 polls, one about 4 weeks out.
- **CO 2016 plebiscite and CL 2017 R1:** large polling misses (real, not data errors).

## govt_events_co_cl.csv (110 rows: COL 60, CHL 50)

### event_type use for presidential systems
- **`government_collapse`:**
  - `new_government`: inaugurations, 12 rows.
  - `finance_minister_change`: 11 rows. Broad reshuffles that included Finance are coded here, with a note.
  - `cabinet_reshuffle`: 3 rows.
- **`confidence_vote`:**
  - Chile's constitutional accusations: one row per chamber vote. The filing date is in `description`. Subtypes are `constitutional_accusation_president`, `_interior` and `_finance`.
  - Colombian censure motion: 1 row.
  - Flagship reform votes and enactments: tax reforms, financing law, pension reform, pension withdrawals.
- **`budget`:** budget laws and presentations, fiscal rules and the fiscal council, and IMF arrangements.
  - IMF arrangements use subtype `imf_fcl`. Chile's 2022 Short-Term Liquidity Line uses `imf_sll`.

### Dates
- **Colombian budget rows** are the sanction / Diario Oficial date of each annual budget law (Senate law database). They are *not* the congressional approval date: plenaries must approve by 20 Oct.
- **Colombian tax-reform rows** are mostly sanction dates.
- **Chilean `budget_presented` rows** are the date on the signed Mensaje Presidencial. **`budget_law_published` rows** are the Diario Oficial publication dates, taken from DIPRES copies of the laws.
- **IMF rows** use the "Date of Arrangement" from the IMF lending-history tables. Amounts are in SDR.
- **Blank dates:** 5 rows have a blank date because the source gives only the month or no date:
  - CL 2014 tax reform (Sept 2014)
  - CL 2025 pension reform
  - CO 2020 fiscal-rule suspension
  - CL Ley 20.128 (Sept 2006)
  - CL Ley 21.148 creating the CFA (Feb 2019)
- **`time_local`:** filled only once (CO 2027 budget vote, 03:43).

### Coverage gaps
These were not verifiable once search was exhausted. minhacienda.gov.co is behind a bot manager, and camara.cl and bcn.cl block automated access; these were not bypassed.
- **Colombia budget cycle:**
  - Marco Fiscal de Mediano Plazo publication (June): all years.
  - PGN bill submission (July): all years.
  - Congressional approval date (Oct): all years except 2026.
  - The 2025 budget, issued by decree in 2024.
  - The 2026 budget law (2025).
- **Chile budget presentations:** missing for 2009-2019 and 2022-2026; several DIPRES Mensaje PDFs are image scans.
- **Chile budget-law publication:** missing for the 2006-2019 budgets.
- **Chile pension withdrawals and reform:**
  - 2nd (Dec 2020) and 3rd (Apr 2021) pension-fund withdrawal laws.
  - The rejected 4th withdrawal.
  - Exact dates of the 2025 pension reform.
- **Colombia censure motions:** only the 2019 Botero motion is included. The minister resigned before the vote. The other censure motions, including those against finance ministers, are missing.
- **Colombia reform votes:** the second financing law attempt (late 2025) and the congressional vote dates for the 2012/2016/2022 tax reforms.
- **Impeachment:** complaints against Colombian presidents (Comisión de Acusaciones) are not covered.
- **IMF:** the Colombia 2020 FCL drawing (SDR 3.75bn) has no verified date.
