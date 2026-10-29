# prevote_polls_br_mx.csv: notes

This file has one row per poll per contest for the Brazilian and Mexican presidential elections. It was compiled on 2026-10-29 from Wikipedia tables. Each table was fetched through the MediaWiki API and parsed in Python. The data has 1,177 rows. The `source_url` of each row gives the exact page revision (`?oldid=`) that the row came from.

`cand_a` and `cand_b` are copied from `data/events/elections.csv` for the vote date in question. The run-off contests use the round-2 row. Brazil 2026 is a special case: for round 2, elections.csv lists Flávio Bolsonaro as `cand_a` and Lula as `cand_b`, the reverse of the round-1 order. The 2026 `runoff` and `runoff_simulation` rows therefore have Flávio in `a_pct`.

## Coverage

| Election | Contest | Rows | Polls | Field-end span | Polls/week | Source (revision) |
|---|---|---|---|---|---|---|
| BR 2010 | round1 | 69 | 68 | 2010-04-09 to 10-02 | 2.6 | en "Opinion polling for the 2010 Brazilian presidential election" (1373536970) |
| BR 2010 | runoff | 18 | 18 | 2010-10-08 to 10-30 | 4.7 | same page |
| BR 2014 | round1 | 40 | 40 | 2014-04-08 to 10-04 | 1.5 | pt template "Pesquisas de opinião da Eleição presidencial no Brasil em 2014 (1º turno)" (71928614) |
| BR 2014 | runoff | 15 | 15 | 2014-10-08 to 10-25 | 5.3 | en "2014 Brazilian general election", total-votes block (1381845583) |
| BR 2018 | round1 | 122 | 77 | 2018-04-13 to 10-06 | 2.9 (4.7 rows) | pt "Pesquisas de opinião para a eleição presidencial no Brasil em 2018" (73055947) |
| BR 2018 | runoff_simulation | 79 | 64 | 2018-04-13 to 10-06 | 2.4 | same page |
| BR 2018 | runoff | 25 | 25 | 2018-10-09 to 10-27 | 8.8 | same page |
| BR 2022 | round1 | 125 | 125 | 2022-04-03 to 10-01 | 4.8 | pt "... em 2022" (73271090) |
| BR 2022 | runoff_simulation | 112 | 112 | 2022-04-03 to 10-01 | 4.3 | same page |
| BR 2022 | runoff | 50 | 50 | 2022-10-04 to 10-29 | 13.0 | same page |
| BR 2026 | round1 | 142 | 142 | 2026-04-04 to 10-03 | 5.4 | pt "... em 2026" (73299227); 2 rows from en (1382146002), see Basis |
| BR 2026 | runoff_simulation | 137 | 137 | 2026-04-04 to 10-03 | 5.2 | pt; 1 row from en |
| BR 2026 | runoff | 60 | 60 | 2026-10-07 to 10-24 | 21.0 | pt; 10 rows from en |
| MX 2006 | round1 | 51 | 51 | published 2006-01-08 to 06-23 | 2.0 | en "2006 Mexican general election" (1382536201) |
| MX 2012 | round1 | 32 | 32 | Feb to Jun 2012 (month only) | 1.2 | en "2012 Mexican general election" (1379907173) |
| MX 2018 | round1 | 47 | 47 | 2018-01-09 to 06-25 | 1.8 | en "Opinion polling for the 2018 Mexican general election" (1306337786) |
| MX 2024 | round1 | 53 | 53 | 2023-12-05 to 2024-05-29 | 2.0 | en "Opinion polling for the 2024 Mexican general election" (1374086463) |

"Polls" counts distinct (pollster, field dates, sample) combinations. In 2018, one poll can have several scenario rows, as described below. For the round-1 and runoff_simulation contests, polls/week is computed over the 183-day window, which is 26.1 weeks. For the run-off contest, it is computed over the days strictly between the two rounds.

**Skipped: Brazil 2006.** Neither en nor pt Wikipedia has a poll-level table for it, and no "Opinion polling for the 2006 ..." page exists. The pt article "Eleição presidencial no Brasil em 2006" shows only six September 2006 polls, as timeline bar charts rather than a table: three round-1 polls from Datafolha and IBOPE, and three run-off simulations. Some of their labels do not match the bar lengths. These six polls were not used.

**Why pt.wikipedia for Brazil 2014 R1, 2018, 2022 and 2026.** The pt tables are a near-superset of the en tables, with roughly 15-45% more polls. Matched against the en tables, 600+ polls agree on a_pct and b_pct. Most remaining differences are field dates that are one or two days apart in the two languages, or a different scenario chosen as the main one. Only two en-listed polls have no pt counterpart: Idea Big Data, 8-10 Oct 2018 (run-off), and Ibope, 8-10 Sep 2018 (run-off simulation). They are not included.

## Windows

- **round1 and runoff_simulation:** the poll's field_end falls between vote_date − 183 days and the day before the round-1 vote. A poll whose fieldwork started before the window is included if it ended inside it. Exit polls and results rows are excluded.
- **runoff:** field_end falls strictly between the two rounds.
- **runoff_simulation:** these are the head-to-head cand_a vs cand_b rows listed in the run-off tables, fielded before round 1. `vote_date` is the run-off date, because that is the vote the simulation refers to; the window is relative to round 1. Matchups involving other candidates were dropped.
- **Mexico 2006:** the table gives publication dates only, so the window uses the publication date. `published` is filled, and `field_start` and `field_end` are blank.
- **Mexico 2012:** the table gives the month only. A row is kept if its whole month falls inside the window, or if its publication date is inside the window. `field_start` and `field_end` are blank unless the table's Remarks give fieldwork dates ("Carried out between ..."). `published` is filled where the Remarks give it ("Published on ...").
- **Mexico 2018:** five rows have month-only dates and blank field dates. Their notes give the date of the cited article.

`field_end` is therefore blank for 51 MX 2006 rows, 29 MX 2012 rows and 5 MX 2018 rows. Every Brazil row has a field_end.

## Basis

- **Brazil, all elections: `total`.** Shares are of all respondents, and `undecided_pct` is the table's "Abst./Undec.", "Blank/Null/Undec." or "Indecisos e Absentos" column.
  - BR 2014 R1 (pt) lists "Branco ou Nulo" and "NS ou NR" separately. Here `undecided_pct` is their sum, and the note on each row shows both parts.
  - BR 2014 R2 (en) lists every poll twice, once on valid votes and once on total votes. The total-votes block was used.
  - **BR 2026:** the pt tables mix bases. Some polls appear on a valid-vote basis, with no undecided share and shares summing to 100; this applies to PoderData, Veritá, Alfa, Ipespe, AtlasIntel and Futura near the end of the race. To keep 2026 on a total basis, the en.wikipedia row for the same poll was used whenever en had a total-basis version. This gives 13 rows with an en source_url and a note that records the pt valid-vote figures. Where no total-basis version exists, the row keeps `basis=valid`. That applies to 5 rows: Veritá 4-12 Sep R1, Veritá 26 Sep-2 Oct and 21-26 May simulations, DataTrends 9 Oct run-off and Ranking 16 Oct run-off.
  - One row, Veritá 26 Sep-2 Oct 2026 R1 (45/47), lists no other candidates and no undecided share. Its basis could not be confirmed and is labeled `total`, with a note saying so.
- **Mexico: the tables do not label the basis, so it was inferred.**
  - **2012:** the table footnote says "the share of the undefined vote has been excluded", so the rows are `valid`. Rows whose Remarks say "Gross preference" are `total`. Some `valid` rows sum to well under 100, and their notes flag this.
  - **2006, 2018 and 2024:** a row is `valid` if its listed candidate shares sum to at least the threshold, otherwise `total`. The threshold is 90 for 2006, where only three candidates are listed, and 95 for 2018 and 2024. Every row's note records the sum and the threshold.
    - The bases are mixed within each election: 2006 has 41 valid and 10 total rows, 2018 has 25 valid and 22 total, and 2024 has 18 valid and 35 total. Users should filter on `basis` or rescale.
  - For MX 2018 and 2024, `undecided_pct` is the table's combined "Other/None" or "Others/Undecided" column. The 2006 and 2012 tables have no such column.

## Scenarios

- When a pollster has several rows for the same field dates and sample, only one is kept: a row that includes both cand_a and cand_b and has the most candidates filled in. If two rows tie, the first one listed is kept. The note on the row records how many scenario rows there were.
- **Brazil 2018** follows the brief:
  - Rows with Lula in the PT slot are kept, with the note `scenario with Lula: b_pct is Lula (PT), not Haddad`. This covers 34 round-1 rows and 26 simulation rows. Such rows run up to 11 Sep 2018, because some pollsters kept testing Lula after the TSE ruling of 31 Aug.
  - Haddad rows are kept and marked `Haddad scenario` (30 rows). Rows with "Haddad, supported by Lula" are marked separately (17 rows).
  - Wagner rows and rows with no PT candidate are dropped.
  - Before about 1 Sep 2018, one poll can therefore appear as two or three rows.
- **Brazil 2014 R1:** the pt template lists one scenario per poll, with the actual line-up.
- **Brazil 2010 R1:** the en table lists two different Vox Populi rows for "12 Sep". Both are kept.

## Other parsing caveats

- Values are exactly as the tables print them. Comma decimals are converted to points, and a "<1%" value would be kept as "<1"; none occur in a_pct or b_pct.
- Pollster names are copied from the tables, including client prefixes such as "Globo e Folha/Datafolha" and typos such as "Mitofksy" and "Reforma%". The pt tables put TSE registration numbers next to pollster names; these were moved into `notes`.
- **Mexico 2006:**
  - Some rows look like table typos: Milenio Diario on 29 May (Madrazo 3%), El Universal on 26 Jan (Madrazo 2%), and "Reforma%". Their notes flag them.
  - The en table marks Arcop, Covarrubias/La Jornada and Milenio (8 Jan) as internal polls with an asterisk; the asterisk is kept in the pollster name.
- **Mexico 2012:** the table includes post-debate flash polls, such as Uno TV at 17.98/16.85/31.46. They are kept with their Remarks in `notes`. The es.wikipedia version of the table has more June 2012 polls, but it gives month-only publication dates and its values differ from the en table. It was not merged.
- **Mexico 2018 and 2024:** two rows sum to more than 100% once others/undecided are included. They are MEBA, 12-15 Jan 2024 (about 110%), and Focus Asesores, January 2018 (about 104%). Their notes flag this.
- **Missing sample sizes:** the BR 2010 en table, the BR 2014 R1 pt template and the MX 2006, 2012 and 2018 tables give no sample sizes, so `sample_size` is blank for those rows.
- **Brazil 2026 pages:** these are being edited heavily. The cited revisions are the versions fetched on 2026-10-29.
