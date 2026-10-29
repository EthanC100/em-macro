# elections_es_gb_de.csv and govt_events_es_gb_de.csv: method notes

Scope: Spain, the United Kingdom and Germany (the benchmark), 2005-01-01 to 2026-10-29. Compiled on 2026-10-29. Every number and date was taken from a page fetched in that session, and the URL is in the row's `*_source`/`source` column. Wikipedia pages were read as raw wikitext (the current revision). Raw downloads are in /tmp/claude-0/events_esgbde/ and were not committed.

**Loader caveat.** `em_macro/config.py` `ISO3` has no ESP/GBR/DEU. `events.to_event_table` therefore maps `country` to NaN, and the per-country-day dedup collapses these rows. Add `ES/GB/DE` to `ISO3` before using them. `events.elections()` already picks up the new file through its `elections_*.csv` glob.

## elections_es_gb_de.csv (25 rows: ESP 10, GBR 9, DEU 6)
- **Contests included.**
  - Spain: general elections 2008, 2011, 2015, 2016, Apr 2019, Nov 2019 and 2023, plus three Catalan votes coded `type=regional`.
  - UK: general elections 2005, 2010, 2015, 2017, 2019 and 2024, plus the 2011 AV, 2014 Scottish and 2016 EU referendums.
  - Germany: federal elections 2005, 2009, 2013, 2017, 2021 and 2025.
- **Spain 2026.** The snap general election set for 29 Nov 2026 has not yet been held and is excluded. Its call and dissolution are in the govt file.
- **Catalan votes (type=regional).** I judged them market-relevant, because Spanish yields and the IBEX traded on secession risk (see `market_preferred_note`). They are the 2015 "plebiscitary" election, the 1 Oct 2017 referendum and the 21 Dec 2017 election held under Article 155.
  - For the elections, cand_a and cand_b are the two leading lists in the final polls. The market-relevant axis is the independence blocs, so `market_preferred` is coded on that axis: the unionist Cs is a/b as stated.
  - The 2017 referendum has no comparable poll. It was illegal and boycotted by unionists, so the poll columns are blank.
- **Poll windows.** Each row's `poll_basis` lists every poll used.
  - Spain and Catalonia: last poll by each pollster/commissioner with fieldwork ending in the final 10 days. Exit polls and polls flagged as after the legal ban are excluded, as are party-commissioned polls (Catalonia 2017: ERC, GAPS/JuntsxCat).
  - UK general elections: each pollster's final poll ending in the last 3 days (4 days in 2005). Polls are GB-wide; actual results are UK-wide (infobox, 1dp).
    - 2015: the unpublished Survation phone poll is excluded.
    - 2019: the final YouGov and FocalData calls were MRPs and are kept.
    - 2024: the Survation MRP is dropped because a standard Survation poll exists.
  - Germany 2013-2025: last poll by each institute ending in the 14 days before the vote, because some institutes publish their last poll 10 or more days out (e.g. Allensbach and Infratest dimap in 2017). The YouGov MRP is dropped in 2025. Germany 2005 and 2009 use the wahlrecht.de archive "Mittelwert", since English Wikipedia has no polling pages for those years.
  - Referendums:
    - EU 2016: What UK Thinks poll-of-polls 52/48. Other aggregates are listed in `poll_basis`.
    - Scotland 2014: final polls, each renormalised to Yes+No=100.
    - AV 2011: four final polls, which already exclude don't-knows.
- **Actual results.**
  - Spain and Catalonia: computed as votes / valid votes (including blank) from Wikipedia results tables. PP excludes UPN.
  - Germany: Zweitstimme shares.
- **results_known.**
  - Spain and Germany: equal to `vote_date`, because the Sunday-night count is decisive.
  - UK: the next day, because results are declared overnight.
  - 2017 Catalan referendum: 2 Oct.
  - AV 2011: 6 May. The declaration time is not verified.
- **Odds.** These are filled for two rows only.
  - EU referendum: Betfair Remain 86%, the vote-day peak per City AM. Single-sided and not normalised.
  - Scotland: Betfair No 81% on vote day.
  - No fetchable source was found for UK general-election prices (2015, 2017, 2019 were searched) or for Spain or Germany. The web-search budget ran out before more could be checked.
- **market_preferred** (12 coded rows). Each is coded only with a fetched press quote; all other rows are blank with a reason.
  - UK 2010 is coded "a" as moderate: the framing is anti-hung-parliament.
  - Spain 2015 and Apr 2019 are left blank: the press framed fragmentation or a "pro-European" result, not PP vs PSOE.
- **Large poll misses worth knowing.**
  - DE 2005: Union +8.3pp in the polls vs +1.0pp actual.
  - UK 2015: tie vs Con +6.5pp.
  - UK 2017: Con +7.9pp vs +2.3pp.
  - ES 2016: PP +5.1pp vs +11.9pp. cand_b is Unidos Podemos (2nd in the polls), which finished 3rd behind PSOE.
  - ES 2023: PP +5.9pp vs +1.4pp.
  - Cat 2017: ERC polled 2nd but JuntsxCat finished 2nd.

## govt_events_es_gb_de.csv (204 rows)
- **event_type values.**
  - `government_collapse`: resignations and announcements of resignation, ousters, coalition and coalition-talk collapses, snap-election calls, early-election votes, dissolutions, and a `new_government` row for every new head of government or re-formed government.
  - `confidence_vote`: Spanish investiture ballots (each ballot), censure motions and the 13 Feb 2019 budget-totality vote; UK Commons confidence motions and Conservative leader confidence votes; German Vertrauensfragen and chancellor elections (each ballot in 2025).
  - `budget`: fiscal events and EU excessive-deficit-procedure (EDP) steps.
- **Recent events (2026).**
  - UK: Starmer announced his resignation on 22 Jun 2026; Burnham became PM on 20 Jul 2026; a Budget was delivered on 28 Oct 2026.
  - Spain: the housing-plan defeat (2 Oct 2026), the snap-election call (5 Oct) and the dissolution (6 Oct), for an election on 29 Nov 2026.
  - These come from Wikipedia pages still being edited and should be re-checked.
- **Dates.**
  - Spanish dissolutions use the BOE publication date; the decree date is in the notes.
  - Spain `pge_final_approval` uses the law (sanction) date, verified on boe.es for all 16 laws. Where es.wikipedia gives a different final parliamentary vote date, it is in the notes (2021, 2022, 2023, 2017).
  - `pge_rollover` rows are dated 1 Jan by convention. They are not news dates.
- **time_local.** Filled only where a source states it:
  - 18:28 for Müntefering's 2005 announcement (Bundestag Datenhandbuch);
  - "shortly before 24:00" for the end of the Jamaica talks;
  - 12:30 for the 2025 Spring Statement;
  - evening or afternoon for a few UK items.
  - UK Budgets are conventionally around 12:30 after PMQs, but this was not verified per event, so the field is left blank.
- **EDP rows.**
  - All are from the European Commission's country pages: Council decisions on opening/abrogation, notice, no/inadequate action and the Spain 2016 fine decision, plus the Commission reports and opinions that began each procedure.
  - Post-2020 Art. 126(3) reports are included only for ES 2024 and DE 2025 and 2026, where no EDP followed.
  - The dates of the UK 2008 opening (5.09.2008, after the 8.07.2008 recommendation) and DE 2026 (printed "03.06.206") are as printed on the EC page and should be verified.

## Coverage gaps (not filled, because they were unverifiable with the sources reachable)
- **Germany annual budgets.** Cabinet approval of the draft budget and the Bundestag's final adoption were not found for 2005-2025.
  - bundesfinanzministerium.de and bundeshaushalt.de returned 503.
  - The Bundestag DIP needs an API key, and that route was not pursued.
  - gesetze-im-internet.de hosts only the current Haushaltsgesetz, so only HG 2026 (signed 22 Dec 2025) is included. The debt brake (2009), the KTF ruling (15 Nov 2023) and the debt-brake reform (18/21 Mar 2025) are included.
- **Spain PGE presentations to the Cortes.** Only 2012 (30 Mar 2012) and 2021 (28 Oct 2020) are dated; congreso.es returned 403.
  - The 2019 PGE presentation date (Jan 2019) is missing. Its 13 Feb 2019 rejection is included.
  - Sánchez's April 2024 "reflection period" and Junts' withdrawal of support (Oct 2025) are missing, because no exact date was found on fetched pages.
- **UK spending reviews** (2010, 2013, 2019, 2020, 2025) are not included as separate rows. The 2015 and 2021 reviews were combined with an Autumn Statement and a Budget respectively.
- **UK post-election re-appointments** of a sitting PM (2005, 2015, 2017, 2019) have no `new_government` row, because no dated source was fetched. New PMs are all covered.
