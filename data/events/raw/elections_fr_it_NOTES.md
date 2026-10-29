# elections_fr_it.csv and govt_events_fr_it.csv: method notes

These files cover France and Italy from 2005-01-01 to 2026-10-29 and were compiled on 2026-10-29. Every row cites a URL fetched in that session. Wikipedia was read as raw wikitext (current revision). Official sources used:

- assemblee-nationale.fr: Art. 49 tables and the open-data vote dumps for the 16th and 17th legislatures
- senat.fr: legislative files for every finance bill (PLF)
- conoscere.camera.it: Italian no-confidence motion lists
- governo.it: Council of Ministers communiqués
- dt.mef.gov.it: DEF/NADEF PDFs, whose cover says "Deliberato dal Consiglio dei Ministri il ..."
- economy-finance.ec.europa.eu: EDP and DBP pages

Legifrance and vie-publique.fr sit behind bot checks and were not used.

## elections_fr_it.csv (32 rows: FRA 20, ITA 12)

Same schema and conventions as `elections_br_mx_pl.csv`.

- **France, presidential.** Polls are the mean of the last published poll per pollster with fieldwork ending in the final 7 days. France bans publication from Saturday 00:00, so a Saturday poll that was never published (e.g. TNS 20-21 Apr 2007) is excluded. Shares are as published, so first-round shares sum to less than 100.
- **France, legislative.**
  - **Round 1** compares national first-round shares of the two leading blocs, summed over the parties that each poll grouped. `notes` lists the bloc composition.
  - **Round 2** is treated as a seat contest, because run-offs happen only in some constituencies. Its pct fields are blank, and `notes` gives the seat outcome and the final seat projections. 2022 (lost majority) and 2024 (NFP first) were seat surprises.
- **Italy.** Polls cannot be published in the 15 days before a vote. The poll figure is the mean of the last poll per pollster before that blackout, using Chamber coalition shares. 2022 uses the Supermedia YouTrend/Agi aggregate instead.
  - For two-day votes, `vote_date` is the second day.
  - 2006 has `results_known` = 11 Apr, the day Prodi declared victory.
  - 2008: the poll basis is PdL+LN vs PD+IdV, so `actual_a` excludes MpA. The full coalition share is in `notes`.
  - 2018: cand_b is M5S, a single list, because it came second.
- **Referendums.** The 2011 and 2025 abrogative votes are included. Their key uncertainty was the turnout quorum, and `notes` explains why each is relevant or not. The 2026 justice-reform constitutional referendum (22-23 Mar 2026) was added even though it was not on the task list.
- **European elections** (`type=european`):
  - France 2024 is included because the dissolution was announced that night.
  - Italy 2019 compares Lega with M5S, the two coalition partners, and M5S polled second. Its market relevance is a judgment; no press source on the market reaction was verified.
- **Odds.** Filled only for FR 2022 round 2 (Betfair Exchange 92.6%, via Reuters/Cyprus Mail) and IT 2016 (Betfair No at 1.34, about 74.6%, single-sided, via diritto.it). The 2017 Betfair prices were seen only in search snippets because the source pages returned 403, so they are not used.
- **market_preferred.** Filled only where a fetched press source supports it:
  - "a" for Sarkozy in 2007 and Macron in 2017 and 2022 (both rounds of each), and for IBC in 2013
  - "b" for Yes in FR 2005 (ex-post euro fall) and in IT 2016
  - blank for all other rows, with the reason given in `market_preferred_note`

## govt_events_fr_it.csv (386 rows)

### government_collapse

Every resignation, fall or dismissal of a PM or cabinet, plus a `new_government` row for each appointment or swearing-in, so the sequence is complete. Routine post-election resignations are marked as such in `notes`. Snap dissolutions (`president_dissolves`) are France on 9 Jun 2024 and Italy on 6 Feb 2008, 22 Dec 2012 and 21 Jul 2022. Two further Italian rows are included:

- 27 May 2018 `formation_failed`, the Savona veto
- `coalition_exit` rows for 8 Nov 2011, 8 Aug 2019 and 13 Jan 2021

### confidence_vote rule

**France.** Every censure motion that went to a vote in the Assemblée nationale, under Art. 49.2 or 49.3, has outcome, votes for and required majority. `notes` flags each motion that answered a 49.3 on a budget text (PLF, PLFSS or LPFP). A 49.3 that drew no motion (e.g. Valls, 9 Jul 2015 and 5 and 20 Jul 2016) has no row. Every Art. 49.1 vote is included, among them 8 Sep 2025, which was lost.

Sources for the French votes:

- 2022 onwards: vote dates and counts come from the AN open-data dump (`Scrutins.json.zip`, scrutin number given in `source`), which runs to 28 Oct 2026. Where the AN summary tables disagree, the open-data figures win (e.g. 29 Nov 2023: 145 not 149; 25 Feb 2026 not 26 Feb), and `notes` records the difference.
- 2005-2020: from the AN summary tables.

**Italy.**

- Investiture votes for each government in both chambers.
- Every individual or whole-government no-confidence motion that was voted. These come from the official Camera lists for the 16th to 19th legislatures (through Mar 2025) and from it.wikipedia for 2005.
- A confidence question only when it was lost or tied to a government crisis: Feb-Mar 2007, 24 Jan 2008, 14 Dec 2010, 14 Oct 2011, 2 Oct 2013, 18-19 Jan 2021, and 14 and 20 Jul 2022.

Routine fiducia votes on bills are excluded.

### budget

**France**

- `plf_presented`: the PLF filing date at the AN, from the senat.fr file. By convention this is the same day as the Council of Ministers.
- `budget_final_approval` and `budget_promulgated` (law date) for every year 2006-2026. The PLF 2027 was filed on 1 Oct 2026 and has not yet been adopted.
- `plf_rejected_first_reading` for 2024 and 2025.
- Loi spéciale filing and promulgation for Dec 2024 and Dec 2025.
- EDP steps from the Commission page. The 2003 EDP closed in 2007; the others ran 2009-2018 and 2024 onwards.

**Italy**

- **April document:** DEF (2011-2024) or DFP (2025-2026).
- **Autumn document:** NADEF (2011-2023), PSB (2024) or DPFP (2025-2026). Dates are taken from the PDF covers or from governo.it communiqués.
- **DBP submissions** (2014-2027): dates as listed on the Commission's DBP pages, which may be the publication date. Also included are the 2018 DBP rejection and the revised and updated DBPs.
- **Budget bill / DBP Council of Ministers rows:** for 2022, 2023, 2025 and 2026 only (see gaps).
- **Budget law promulgation** (law date) for 2006-2026.
- **EDP steps:** 2005-2008, 2009-2013 and 2024 onwards, plus the 2018-2019 debt-rule episodes.

## Known gaps and rows to treat with care

- **Italy budget.**
  - No source located for: DEF 2020, 2021 and 2022, NADEF 2021, the revised NADEF of Nov 2022, and the DPEF of 2005-2010. The PDF covers are images, and governo.it search only indexes the Meloni era.
  - Budget-bill cabinet approval dates exist only for 2022, 2023 and 2026, plus the DBP being presented to cabinet on 14 Oct 2025.
  - Final parliamentary votes on the budget law were not collected; only the promulgation date is given.
- **Italy confidence and collapse rows.**
  - Speranza no-confidence date: the Camera page says 28 May 2021 (its text says 2020), while it.wikipedia says 28 Apr 2021. The it.wikipedia date is used.
  - 2007-02-28 Senate and 2010-12-14 Senate confidence votes have no vote counts.
  - The 2011 accounts-bill defeat (10 or 11 Oct) has no row.
  - Monti's 6-7 Dec 2012 PdL abstentions have no row.
  - Berlusconi III end date (2 May 2006) comes from the infobox only.
- **France.**
  - The Borne post-election resignation of about 21 Jun 2022 was not verified and has no row.
  - The Valls announcement of 5 Dec 2016 was not verified; the 6 Dec 2016 formal date is used.
  - No `time_local` for most votes. It is filled only where a fetched source gives a time: the dissolution at 21:00, Lecornu at 22:00, Renzi's midnight press conference and CdM start times.
- **Elections.**
  - FR 2005 rests on a single Ipsos poll.
  - IT 2016: polls from 10-18 Nov are missing from the source table.
  - IT 2006 referendum and 2011: no polls.
  - IT 2025: turnout polls only.
  - 2026 rows rely on recently edited Wikipedia pages.
- `em_macro/config.py` ISO3 does not list FRA or ITA, so `events.to_event_table` would map them to NaN country codes until the config is extended.

Raw downloads are in /tmp/claude-0/events_frit/ and were not committed.
