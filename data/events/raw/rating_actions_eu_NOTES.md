# rating_actions_eu.csv: notes

This file holds sovereign credit-rating histories from S&P, Moody's and Fitch for France, Italy, Spain, the United Kingdom, Germany and Poland. It was compiled on 2026-10-29 and has 255 rows. The emerging-market countries are in a separate file.

Each country-agency pair starts with an `initial_state` row dated 2005-01-01. After that comes every rating, outlook or watch change found from then to 2026-10-29, plus every affirmation found that could be sourced. Every row cites at least one URL that was fetched. The downloads and helper scripts are in `/tmp/claude-0/ratings_eu/`: `rows/*.jsonl` holds the rows, `scripts/build.py` builds the CSV, and `cal/` holds the MNI calendars.

## Conventions

- **Rating.** Ratings are in each agency's own scale:
  - S&P: long-term foreign-currency sovereign credit rating.
  - Moody's: long-term issuer / government bond rating.
  - Fitch: long-term foreign-currency IDR.
- **Outlook and watch status.** Both go in the `outlook_*` columns. The outlook values are `stable`, `positive` and `negative`. The watch values use each agency's own term:
  - S&P: `watch negative` (CreditWatch).
  - Moody's: `review for downgrade`.
  - Fitch: `rating watch negative`.
- **Action when a review resolves.** If a review ends in a downgrade, the action is `downgrade`. `watch_off` is used only when the rating is left unchanged.
- **Date.** The date is the announcement date. EU sovereign actions usually come out on Friday evenings after the market close. When the report time is known, it is given in `notes`.
  - Aggregators sometimes give such releases the next day's date. Trading Economics gives Italy's S&P upgrade as 2025-04-12 and France's S&P affirmation as 2024-11-30. Where that happens, the Friday date is used and the difference is noted.
- **Moody's periodic reviews.** Moody's sometimes publishes a "completion of periodic review" instead of a rating action. These rows are coded as `affirmation`, and the notes say so (Poland 2024-09-20, 2025-03-21 and 2026-03-20). If Moody's published nothing on a calendar date, there is no row. Examples: Poland 2019-10-11; Italy May 2023, which was postponed.
- **Affirmations before 2014.** These are not covered systematically. The few included are ones that turned up in the sources.
- **Scheduled calendar date.** This is noted wherever an MNI calendar covers the date: the 2025 and 2026 PDFs at media.marketnews.com, parsed by word position.

## Source anchors by pair

**S&P, all countries.**
- **Changes.** The backbone is the Trading Economics S&P history (`tradingeconomics.com/<country>/rating`), which mirrors S&P's change history. It was cross-checked as follows:
  - Germany: S&P's own "Sovereign Credit Ratings History" in its October 2026 report, hosted by Finanzagentur.
  - Poland: alacrastore abstracts of S&P research updates (2005–2010), plus money.pl.
  - Spain: La Moncloa (2019).
  - Italy: Il Sole 24 Ore and MilanoFinanza (2025–2026).
  - France: AWP/AFP via allnews.ch, BBC, NBC, Börsen-Zeitung.
  - Dec 2011 CreditWatch: S&P's full text on creditwritedowns.
- **Affirmations.**
  - Poland: complete from 2019 via Polish MoF communiqués (`gov.pl/web/finance/...`).
  - Germany: 2025-06 and 2026-04, from the S&P research update PDFs hosted by Finanzagentur.
  - France, Italy and the UK: only a few.

**Moody's.**
- **Changes.** The backbone is countryeconomy.com, which was cross-checked as follows:
  - Germany: Mondo Visione reprint (2012) and The Local (2014).
  - UK: BBC (2013, 2023).
  - Spain: Enagás CNMV filing (2012), Bolsamania and Tesoro (2025).
  - Italy: ANSA, Il Sole and MilanoFinanza (2025).
  - France: allnews and ANSA (2024–2026).
  - Poland: money.pl and Polish MoF communiqués.
- **Doubtful rows.** Several Moody's "affirmations" are dates that appear only in countryeconomy. They are flagged DOUBTFUL because they may be periodic-review dates.

**Fitch.**
- **Up to Oct 2011.** The anchor is Fitch's own sovereign history table as of 3 Oct 2011, reproduced at `creditwritedowns.com/?p=33504`.
- **After Oct 2011.** The sources are countryeconomy (until about 2021) and news:
  - Mondo Visione, Al Jazeera, NPR, CBS, BBC, Kitco/Reuters, allnews, MNI, France24, Il Sole 24 Ore, LaPresse, Bolsamania.
- **Germany.** Review dates from April 2021 to February 2025 come from the "Recent Rating Derivation History" table in the Fitch rating report of July 2025. The May 2026 rating action commentary PDF is also used. Both are on Finanzagentur.
- **Poland.** Complete from 2019 via MoF communiqués.

## Coverage and gaps

- **Poland.**
  - S&P: complete for changes; affirmations complete from 2019.
  - Fitch: complete for changes. The 2005-03-23 positive outlook is doubtful; see below. Affirmations from 2019, missing mid-2023.
  - Moody's: complete for changes; affirmations from 2019.
  - Missing everywhere: affirmations from 2014 to 2018. The MoF archive (mf-arch2) and PAP Biznes are behind Incapsula bot checks and were not bypassed.
- **Germany.**
  - Changes: complete for all three agencies; there were only Dec 2011–Jan 2012 (S&P) and 2012–2014 (Moody's).
  - Fitch affirmations: from 2021.
  - S&P and Moody's affirmations: sparse.
- **France.**
  - Changes: believed complete for all three agencies.
  - Affirmations: partial, 2018–2026.
  - Fitch: the outlook went negative on 2020-05-15 and was still negative at the April 2023 downgrade. A May 2021 negative-outlook affirmation is reported by journaldeleconomie (10 May 2021), but its exact date was not found, so it is not included.
- **Italy.**
  - Changes: believed complete for all three agencies.
  - Affirmations: partial; 2023–2026 is good.
- **Spain.**
  - S&P and Moody's changes: believed complete.
  - Fitch: no source was found for 2019-01 to 2024-11. The row for 2024-11-08 assumes a stable outlook before that date.
- **United Kingdom.** This is the weakest pair set.
  - S&P and Moody's changes: complete.
  - Fitch after 2016 is incomplete. Possible 2019 Rating Watch episodes and the 2020–2024 outlook path are not covered. The 2024-03-22 return to a stable outlook comes from Wikipedia only.
  - Affirmations: only a few.

**Scheduled reviews with no sourced outcome.** These dates come from the MNI 2025 and 2026 calendars, but no outcome was found, so they have no row:
- France: Fitch 2026-03-06; Moody's 2025-04-11; S&P 2025-05-30, 2025-11-28 and 2026-05-29.
  - 2025-11-28 was overtaken by the unscheduled 2025-10-17 downgrade.
  - 2026-05-29 was reported by Bloomberg as an A+ stable confirmation, but that report could not be fetched.
- Germany: Fitch 2026-01-09; Moody's 2025-11-07 and 2026-03-13; S&P 2025-01-31, 2025-12-05 and 2026-10-23.
- Italy: Moody's 2026-03-27 and 2026-09-25; S&P 2026-05-15.
- Poland: S&P 2025-05-09.
- Spain: Fitch 2025-04-11 and 2026-09-11; Moody's 2025-03-28, 2026-03-27 and 2026-07-17; S&P 2025-03-14, 2026-03-13 and 2026-09-11.
- UK: Fitch 2025-02-28, 2025-08-22, 2026-02-20 and 2026-08-14; Moody's 2025-05-23 and 2026-05-22; S&P 2025-04-11, 2025-10-10, 2026-04-10 and 2026-10-09.

**Upcoming reviews.** France S&P 2026-11-27, Germany Fitch 2026-11-13, Italy S&P 2026-11-13, Poland S&P 2026-11-06, UK Moody's 2026-11-20.

## Disagreements between sources

- **France S&P 2025-10-17.** Trading Economics and Börsen-Zeitung say the downgrade was from AA-; France24 says from AA. AA- is consistent with the 2024-05-31 downgrade.
- **France Fitch 2011-12-16.** countryeconomy gives 2011-12-20. The Fitch release reprint is dated the 16th.
- **France S&P 2014-10-10.** fr.wikipedia gives 12 Oct 2014.
- **Italy and Spain Fitch 2011-10-07.** countryeconomy gives 2011-10-12 for Italy.
- **Italy Fitch 2005.** The Fitch Oct-2011 table shows AA- for 2000 but AA with a negative outlook on 2005-06-29. The table appears to be internally inconsistent. AA/stable is used for 2005-01-01, following countryeconomy.
- **Italy Fitch 2013-03-08.** The AFP text says both 7 and 8 March.
- **UK Fitch 2013-04-19.** The date is from BBC; countryeconomy shows AA+ only from 2013-05-14.
- **Spain Fitch 2010-05-28.** This downgrade is missing from the Oct-2011 Fitch table but is confirmed by countryeconomy and Vozpópuli.
- **Poland Moody's 2016.** The outlook change is dated 2016-05-14 in all sources found; it was probably published late on Friday 13 May (US time).
- **Poland Fitch 2005-03-23.** The positive outlook appears in the money.pl/countryeconomy table but not in Fitch's Oct-2011 table.

## Access limits

- **Blocked sites.** The following blocked bot traffic or required a login, and none of these checks were bypassed:
  - spglobal.com (including the disclosure pages and the S&P "Sovereign Rating And Country T&C Assessment Histories" PDF).
  - fitchratings.com, AFT (Cloudflare), the tesoro.es WAF (only one page could be read, through WebFetch), and web.archive.org.
  - mf-arch2.mf.gov.pl and PAP Biznes (Incapsula), Reuters (HTTP 401), FXStreet, investing.com and CNBC.
- **Alacrastore.** An attempt to page through Alacrastore's research lists through its internal AJAX endpoint was refused by the session's permission classifier and was not pursued.
- **Search budget.** The shared web-search budget ran out partway through. Later verification used only pages already found or linked from fetched pages, including Wikipedia reference lists used as pointers.
