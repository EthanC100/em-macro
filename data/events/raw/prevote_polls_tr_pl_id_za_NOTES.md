# prevote_polls_tr_pl_id_za.csv: method notes

This file holds poll-level pre-vote polling for Turkey, Poland, Indonesia and South Africa. There is one row per poll per contest, 1,320 rows in total. It was compiled on 2026-10-29.

All numbers were parsed from Wikipedia wikitext. Each page was fetched once through the MediaWiki API (`action=parse&prop=wikitext`), and the exact revision is in `source_url` (`?oldid=`). No value was typed in by hand or filled from memory. The downloads and parser live outside the repo; the parser handles rowspan/colspan, `{{N/A}}`-style cells and multi-line templates.

## Window and contests
- **Window.** A poll is kept if its `field_end` falls in the 183 days before the vote: `vote_date - 183 <= field_end < vote_date`.
- **Excluded rows.** Election-day exit polls, late polls and quick counts are excluded, as are result rows and event rows.
- **Contest values:**
  - `single`: legislative elections, referendums, and Indonesian presidential elections, which were decided in one round.
  - `round1`: first-round polls in two-round presidential systems (Turkey, Poland).
  - `runoff`: run-off polls. `field_start` is after round 1 and `field_end` is before the run-off. `vote_date` is the run-off date.
  - `runoff_simulation`: head-to-head polls of cand_a vs cand_b with `field_end` in the 183 days before round 1. Two cases:
    - Where a run-off took place (Poland 2010/2015/2020/2025, Turkey 2023), `vote_date` is the run-off date.
    - Where no run-off was held (Turkey 2018 Erdoğan v İnce, Indonesia 2024 Prabowo v Anies), `vote_date` is the round-1 date, and `notes` says the run-off is hypothetical. Drop these rows if you only want real contests.
- **Candidates.** `cand_a` and `cand_b` are copied from `elections.csv` for the row's `vote_date`. Run-off and run-off-simulation rows therefore use the run-off row's ordering, which is swapped versus round 1 for Poland 2015 and Turkey 2023. Values were mapped to candidates by column header name, not by position.

## Basis (read this before comparing levels)
`a_pct` and `b_pct` are exactly as published. Wikipedia tables mix polls on different bases within one election: some pollsters report shares including undecided voters, others report shares of decided voters. Re-scaling would break the "as published" rule, so it is not possible to force one basis per election.

Instead, `basis` is assigned **per row by one fixed arithmetic rule**, applied the same way in every election:
- **`total`**: the row publishes a positive undecided/don't-know share, and the shares plus undecided sum to about 100 (±2.5). A row is also `total` when the race lists the full candidate field and the shares sum to less than 97.5, so the remainder is unreported undecided/none.
- **`decided`**: candidate/party shares (including "others") sum to about 100 (±2.5). Some of these rows also report an undecided share separately; `notes` says so.
- **`unclear`**: the basis cannot be determined. This happens mainly when the source merges "Others/Undecided" into one column (Polish parliamentary tables for 2011, 2015 and 2019, and part of 2023), or when a party table omits minor parties (Turkey 2011).

A note beginning `basis:` explains the cases that are not obvious. `undecided_pct` is filled only from an explicit undecided/don't-know column or text. Abstain/would-not-vote figures are reported in `notes`, not in `undecided_pct`. **For level comparisons, use a two-party share a/(a+b), which does not depend on basis.**

Predominant basis by election:
- Turkey legislative 2015 (both) and presidential 2018/2023: `decided`. Turkish pollsters report shares of decided voters.
- Poland presidential, Indonesia, Turkey 2017 referendum, South Africa 2014/2019: mostly `total`.
- South Africa 2024: `decided`.
- Polish parliamentary 2011/2015/2019: `unclear`.

## Rows per election (polls/week = rows / 26.1 weeks; run-off: rows / weeks between rounds)
| iso3 | vote_date | contest | rows | first field_end | last field_end | polls/week | basis total/decided/unclear |
|---|---|---|---:|---|---|---:|---|
| IDN | 2014-07-09 | single | 19 | 2014-02-14 | 2014-07-07 | 0.73 | 15/4/0 |
| IDN | 2019-04-17 | single | 42 | 2018-11-16 | 2019-04-10 | 1.61 | 38/4/0 |
| IDN | 2024-02-14 | single | 61 | 2023-08-20 | 2024-02-08 | 2.33 | 58/3/0 |
| IDN | 2024-02-14 | runoff_simulation | 8 | 2023-10-08 | 2023-11-05 | 0.31 | 8/0/0 |
| POL | 2010-06-20 | round1 | 23 | 2010-05-06 | 2010-06-18 | 0.88 | 16/4/3 |
| POL | 2010-07-04 | runoff | 4 | 2010-07-01 | 2010-07-02 | 2.00 | 4/0/0 |
| POL | 2010-07-04 | runoff_simulation | 10 | 2010-05-07 | 2010-06-18 | 0.38 | 7/3/0 |
| POL | 2011-10-09 | single | 33 | 2011-04-11 | 2011-10-07 | 1.26 | 0/0/33 |
| POL | 2015-05-10 | round1 | 67 | 2014-12-04 | 2015-05-08 | 2.56 | 44/21/2 |
| POL | 2015-05-24 | runoff | 13 | 2015-05-14 | 2015-05-22 | 6.50 | 9/4/0 |
| POL | 2015-05-24 | runoff_simulation | 10 | 2015-02-11 | 2015-05-07 | 0.38 | 8/2/0 |
| POL | 2015-10-25 | single | 103 | 2015-04-25 | 2015-10-23 | 3.94 | 0/3/100 |
| POL | 2019-10-13 | single | 55 | 2019-07-24 | 2019-10-11 | 2.10 | 0/10/45 |
| POL | 2020-06-28 | round1 | 54 | 2020-05-15 | 2020-06-26 | 2.07 | 27/26/1 |
| POL | 2020-07-12 | runoff | 23 | 2020-06-30 | 2020-07-10 | 11.50 | 17/6/0 |
| POL | 2020-07-12 | runoff_simulation | 41 | 2020-05-15 | 2020-06-27 | 1.57 | 26/15/0 |
| POL | 2023-10-15 | single | 158 | 2023-04-15 | 2023-10-13 | 6.04 | 31/25/102 |
| POL | 2025-05-18 | round1 | 90 | 2024-11-24 | 2025-05-16 | 3.44 | 73/17/0 |
| POL | 2025-06-01 | runoff | 22 | 2025-05-21 | 2025-05-30 | 11.00 | 17/5/0 |
| POL | 2025-06-01 | runoff_simulation | 62 | 2024-11-23 | 2025-05-16 | 2.37 | 51/11/0 |
| TUR | 2011-06-12 | single | 25 | 2010-12-31 | 2011-05-31 | 0.96 | 0/7/18 |
| TUR | 2015-06-07 | single | 63 | 2014-12-08 | 2015-06-02 | 2.41 | 0/63/0 |
| TUR | 2015-11-01 | single | 56 | 2015-06-08 | 2015-10-29 | 2.14 | 0/56/0 |
| TUR | 2017-04-16 | single | 51 | 2016-10-16 | 2017-04-13 | 1.95 | 39/12/0 |
| TUR | 2018-06-24 | round1 | 27 | 2018-04-25 | 2018-06-23 | 1.03 | 0/27/0 |
| TUR | 2018-06-24 | runoff_simulation | 4 | 2018-04-25 | 2018-06-03 | 0.15 | 0/4/0 |
| TUR | 2023-05-14 | round1 | 92 | 2023-02-27 | 2023-05-13 | 3.52 | 6/86/0 |
| TUR | 2023-05-28 | runoff | 10 | 2023-05-21 | 2023-05-26 | 5.00 | 0/10/0 |
| TUR | 2023-05-28 | runoff_simulation | 66 | 2022-11-20 | 2023-05-10 | 2.52 | 26/40/0 |
| ZAF | 2014-05-07 | single | 7 | 2013-11-30 | 2014-04-30 | 0.27 | 3/4/0 |
| ZAF | 2019-05-08 | single | 7 | 2018-12-04 | 2019-04-25 | 0.27 | 6/1/0 |
| ZAF | 2024-05-29 | single | 14 | 2023-12-01 | 2024-05-28 | 0.54 | 0/14/0 |

All requested elections have poll-level tables, so none was skipped. The Turkey 2017 referendum is included. Its national table only was used; the overseas table was excluded.

## Sources and choices per election
- **Turkey**
  - **2011.** "Opinion polling for the 2011 Turkish general election": the main table plus the Andy-Ar and Konsensus tables. In the last two, the pollster comes from the section title.
    - Dates are mostly month-only.
    - The table lists only six parties, so shares sum to less than 100 and most rows are `unclear`.
    - One Konsensus poll appears in both the main table and the Konsensus table under different months. It was kept once, and its note records the other listing.
  - **June/Nov 2015.** The vote-share tables. Seat predictions, diaspora polls and polls on other issues are excluded.
    - Polls fielded before 7 June 2015 are assigned only to the June vote, so the Nov 2015 window effectively starts on 8 June 2015.
  - **2017 referendum.** Uses the "considering undecided vote" columns (Yes, No, Undecided), as published.
  - **2018.**
    - Presidential round 1 uses the "Following candidate selection" table.
    - From the "Prior to candidate selection" table, only rows whose cells are explicitly annotated (Erdoğan)/(İnce) are kept; there is one such row.
    - Abroad polls, alliance votes and seat projections are excluded.
  - **2023.**
    - Round 1 uses the "Official campaign polling" table plus pre-campaign rows in the window. Pre-campaign rows are flagged `pre_nomination` in `notes`.
    - Run-off rows come from the second-round "Official campaign polling" table.
    - Simulations come from the second-round "Pre-campaign polling" tables for 2023 and 2022.
    - Aggregator tables are excluded.
- **Poland**
  - **2010.** Taken from the "Opinion polls" section of the English article.
    - Round-1 polls from before 10 April 2010 have no Jarosław Kaczyński column: Lech Kaczyński was the PiS candidate until his death, then Jarosław entered on 26 April. Three in-window CBOS polls are therefore skipped, so round-1 coverage effectively starts in May 2010.
  - **2015 presidential.**
    - **Primary source: Polish Wikipedia** ("Wybory prezydenckie w Polsce w 2015 roku"). It lists more polls than English Wikipedia, and its shares consistently include undecided voters, whereas English Wikipedia mixes bases. For example, IBRiS on 8 May is shown as 36.3/28.3 with 7.5 undecided on pl, but 39/31 on en.
    - English rows were added only where no poll from the same pollster had a `field_end` within one day on the pl page. This added 11 rows: 9 in round 1 (Dec 2014 polls, PPW, Pressmix and others) and 2 in the second-round table. These rows are flagged "added from secondary page".
    - Three pl rows dated "bd." (no date) were skipped.
  - **2020.** "Opinion polling for the 2020 Polish presidential election".
    - Round 1 comes only from the table with Trzaskowski. The earlier Kidawa-Błońska table has no cand_b column, so coverage starts on 15 May 2020, after the postponed election and the change of candidate.
    - Run-off and simulation rows come from the "Duda v. Trzaskowski" table.
    - Some rows are campaign-internal polls. This is flagged in `notes` from the page's footnotes.
  - **2025.**
    - Round 1 uses the main table plus the "Hypothetical polling" table, which is flagged as a scenario poll in `notes`. Two hypothetical rows were skipped because the PiS value is one merged "generic PiS candidate" cell rather than Nawrocki's.
    - Run-off and simulation rows come from the "Nawrocki v. Trzaskowski" table.
  - **Parliamentary.**
    - 2011 and 2015 use PO and PiS columns.
    - 2019 uses only the "Electoral alliances" table (United Right vs Civic Coalition), which starts in late July 2019. The earlier "Parties" table lists PO separately, not KO, so it was not used.
    - 2023 uses the "Electoral alliances" and "2023" tables.
    - "Alternative scenarios" tables and seat projections are excluded.
    - Where a cell spans several party columns (a joint list, e.g. United Right + Kukiz'15, or KO + AGROunia), the joint value is used and `notes` says so.
- **Indonesia**
  - **2014.** Indonesian Wikipedia, "Hasil survei pemilihan umum Presiden Indonesia 2014". This table has free-text result cells, and Jokowi, Prabowo and "Tidak tahu" (don't know) were parsed from that text.
    - The text is quoted in `notes`. Pre-nomination open-list rows are flagged.
    - The SPIN poll was skipped because it does not list Jokowi.
  - **2019.** Indonesian Wikipedia, "Hasil survei pemilihan umum Presiden Indonesia 2019", national table. One row was added from the English article, a Median poll from November 2018 with no match on the id page.
    - Regional tables are excluded.
    - "Lainnya" (others/remainder) is treated as the undecided/other remainder of a two-way race.
  - **2024.** English "Opinion polling for the 2024 Indonesian presidential election": the national tables (after nomination, and 2023).
    - Simulations come from "Prabowo-Gibran vs. Anies-Muhaimin" and "Prabowo vs. Anies".
    - Provincial and open-question tables are excluded.
- **South Africa.** The "Opinion polling" sections of the English 2014, 2019 and 2024 general-election articles, using the national ballot only.
  - 2014 lists several Ipsos variants of the same fieldwork, such as turnout scenarios and undecided allocated or not. All are kept, with Wikipedia's footnote copied into `notes`.
  - In 2019, Intellidex's "investor poll" was excluded because it is not a voter poll.

## Other conventions
- **Month-only dates.** Where only month(s) are given, such as "May 2011" or "Oct/Nov 2013", `field_start` and `field_end` are set to the month bounds, and `notes` says "month precision". This applies to 68 rows, mostly Turkey 2011 and South Africa 2014. A single fieldwork date is used for both start and end.
- **Blank columns.**
  - `published` is blank throughout because none of the tables gives a publication date.
  - `sample_size` is blank where the table does not give it (483 rows).
- **Duplicates.** Exact duplicates within an election were removed: same pollster, dates and values (4 rows in Poland 2023).
- **Footnote flags.** Wikipedia footnotes attached to the date or pollster cell are copied as `source footnote:`. Examples are internal campaign polls, pollster affiliations, and "determined voters only". Rows whose source link is labelled "sonda uliczna" (street poll) are flagged.
- **Unnamed pollsters.** Rows whose pollster is unnamed in the source are kept, and `notes` says so.
