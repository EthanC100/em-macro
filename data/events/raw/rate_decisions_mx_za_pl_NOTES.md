# rate_decisions_mx_za_pl.csv: notes

Policy-rate decision announcements for Mexico (Banxico), South Africa (SARB) and Poland (NBP/RPP), from 2005-01-01 to 2026-10-29. The file has 563 rows: MEX 197, ZAF 135, POL 231. Compiled on 2026-10-29. Every row cites the URLs it was built from. The downloads and build scripts are in `/tmp/claude-0/rates_mxzapl/`; the build script is `scripts/build.py`.

## Sources per country

**Mexico.** All rows come from Banxico's "Anuncios de las decisiones de política monetaria" list. The full list is on one page, back to 2000. Each row's `source` is the press-release PDF that was fetched.
- **2005-01-28 to 2008-01-18, corto regime.** Banxico had no rate target. Decisions changed the "corto" (a borrowed-reserves amount) or the "condiciones monetarias".
  - "Corto se aumenta" is coded as a hike, with `change_bp` blank.
  - "Relajamiento … no mayor a N pb" is coded as a cut of −N bp. This is the maximum easing allowed, not a confirmed move.
  - "Se restringen en 25 pb las condiciones monetarias" is coded as +25 bp.
  - Rate columns are blank. The notes give the BIS bank-funding rate the day before and a week after.
- **From 2008-01-21.** The policy rate is the overnight interbank rate target. Hold statements give the level. Hike and cut statements give only the size of the change, so `rate_after` is the previous level plus that change. Every level was cross-checked against BIS.
- **Unscheduled decisions.**
  - 2016-02-17: the statement says "reunión extraordinaria".
  - 2020-03-20: the statement says the decision was brought forward from 26 March.
  - 2020-04-21: unscheduled according to BBVA Research.
- **Announcement time.** 13:00 for 2025–26 only. Banxico's 2026 calendar footnote says decisions are published on Thursdays at 13:00, "como en el 2025". Earlier times are blank.

**South Africa.** The SARB MPC statements list is filled by the site's search API. All 175 entries were paged and every statement from 2004 on was fetched. For 2011–2024, much of the text is only in the statement PDFs, so those PDFs were fetched and parsed.
- **Dates.** Dates come from the title date (pre-2013 entries), otherwise from the publish date. All 54 BIS repo changes fall 0–2 days after a statement date.
- **Levels.** Each row's decision text was compared with BIS levels. There are no mismatches.
- **Unscheduled decision.** 2020-04-14: the May meeting was brought forward (BusinessTech, Daily Maverick).
- **2009 meetings.** These do not match the calendar published with the 11-Dec-2008 statement. SARB said it met "more frequently" in 2009. They are marked Y but flagged as doubtful.
- **Announcement time.** 15:00 only for May, July and September 2026, from Trading Economics' 13:00 GMT. Elsewhere it is blank.
- **Rate name.** 2026 pages call the rate "SARB Policy Rate (SPR)".

**Poland.** nbp.pl, including the communiqué PDFs, and web.archive.org were both blocked by bot protection or connection resets. Bot checks were not bypassed. Other sources were used instead:
- **Rate levels and change dates.** Official XML `https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml`. It contains changes up to 2026-03-05 even though its header says `data_publikacji="2015-03-04"`. `rate_before` is the level in force on the decision day and `rate_after` the level the next day. In every sourced case, NBP rates took effect the day after the decision.
- **Meeting dates, 2010–2025.** These come from NBP's annual "Sprawozdanie z wykonania założeń polityki pieniężnej", published in Monitor Polski and fetched through the Sejm ELI API (`https://api.sejm.gov.pl/eli/acts/MP/<year>/<pos>/text.pdf`).
  - The 2010–2019 reports contain a "Opis dyskusji na posiedzeniu decyzyjnym … w dniu D" heading for each decision meeting.
  - The 2020–2025 reports contain voting records on rate motions plus footnotes listing meeting dates.
  - The 2010 report (MP/2011/452) uses a shifted font encoding, which was decoded.
- **2020 June–December.** Dates come from money.pl decision-day reports and Deutsche Bank Polska dailies (`country.db.com/.../dailyYYMMDDpol.pdf`).
- **2026.** Dates come from money.pl, Alior Bank "Raport rynkowy", strefainwestorow, finwire, DB Polska dailies and Trading Economics. The June 2026 meeting was moved to 1–2 June, and September to 8–9 September.
- **2006-11 to 2009.** Dates come from mBank/BRE "Daily" PDFs (`mbank.pl/pobierz/serwis-ekonomiczny/komentarz-dzienny/`) and money.pl RPP-tag decision-day reports.
- **Gap: January 2005 to October 2006.** No accessible source listed the meetings. Only the 7 rate changes are included, from the XML, with `announce_date` inferred as the day before the effective date. These rows are flagged "DOUBTFUL date". About 14–15 hold meetings from this period are missing.
- **Unscheduled or extraordinary meetings.**
  - 2008-10-08: an extraordinary evening meeting with a communiqué and no rate change. Flagged as doubtful to include.
  - 2020-03-17: a one-day working meeting at which a cut was decided.

## Expectation columns

**Coverage (rows with a basis / rows with a numeric `expected_change_bp`):**

| Country | Rows with basis | Rows with numeric value | Coverage of rate changes | Coverage of rate changes since 2015 |
|---|---|---|---|---|
| POL | 121 | 114 | 38 of 59 | 17 of 24 |
| MEX | 32 | 30 | 15 of 84 | 13 of 57 |
| ZAF | 37 | 35 | 18 of 54 | 16 of 31 |

**Systematic source for Poland, 2019 onwards.** Deutsche Bank Polska's daily on decision day has an indicator table, "prognoza DB / Aktualny / Konsensus", sourced from Bloomberg. Where the "Decyzja RPP" row has two values, the second (Konsensus) is used, and the expected change is consensus level minus the current level. This covers 56 meetings.

**Other sources:**
- money.pl and mBank (2006–2012) give qualitative statements such as "zgodnie z oczekiwaniami" or "analitycy zgodni".
- CentralBankNews.info (2011–2019) gives "as expected" or "surprise".
- Mexico News Daily, El Financiero, Bloomberg Línea (Encuesta Citi/Citibanamex), BusinessTech (Bloomberg and Reuters polls) and Trading Economics consensus (2026) cover a few more meetings.

**Coding rules:**
- "As expected" or "in line" means expected = actual.
- A "surprise" move with no stated alternative means expected = 0.
- If only the direction or a split is known, `expected_change_bp` is blank and the basis explains why.

**Not used.** No systematic Citi-survey archive for Mexico was reachable. The per-meeting expected decision in the Encuesta Citi exists, but only as scattered news articles. It is used for 2022-06, 2025-02, 2025-09 and 2026-05. The 2026-05 entry is doubtful because that survey was taken a month before the meeting.

## BIS cross-check

Source: BIS WS_CBPOL daily series D.MX, D.ZA and D.PL, fetched 2026-10-29.

- **Mexico, from 2008-01-22.** BIS shows 71 changes and the file has 71 hike/cut rows with levels. They match one-to-one in date and level. BIS before 2008-01-21 is the daily bank funding rate, so it cannot be compared with decisions.
- **South Africa.** BIS shows 54 changes and the file has 54 rows. All match.
- **Poland.** BIS shows 59 changes and the file has 59 rows. All match, each effective the day after the decision.
- **Holds.** No hold row has a BIS level change within 4 days.
- **Result.** No mismatches.

## Doubtful rows, collected

- POL: the 7 rate changes in 2005–06 have inferred dates.
- POL 2009-05-27: only a preview article was found; the hold comes from the XML.
- POL 2026-04-09 and 2026-05-06: the decision day is assumed to be the second day of the meeting.
- POL 2008-10-08: inclusion is doubtful (extraordinary meeting, no rate vote).
- ZAF 2009 (6 meetings): the scheduled flag is doubtful.
- MEX 2005–07: the hike/cut coding is an interpretation of the corto and monetary-conditions announcements.
- POL 2008-02-27: the expectation sources conflict. money.pl's survey showed 7:3 for a hold, but mBank said the hike was expected. The file uses 0.
