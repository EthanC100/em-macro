# rate_decisions_tr_id.csv: notes on sources and methods

Scope: every policy-rate decision announcement for Turkey (CBRT) and Indonesia (BI) from 2005-01-01 to 2026-10-29. The file has 511 rows: Turkey 251, Indonesia 260.
Change sign: `change_bp = (rate_after - rate_before) * 100`. `rate_before` is the previous row's `rate_after`.

## Turkey (CBRT)

**Sources.**
- Every row except one cites the CBRT English press release it was read from ("Press Release on Interest Rates" / "Decision of the MPC"). These were found in the yearly listings at `tcmb.gov.tr/.../Announcements/Press+Releases/<year>` for 2005-2026.
- Meeting dates were checked against the CBRT per-year MPC schedule pages (`.../Monetary+Policy+Committee/<year>`). Every listed meeting has a row.
- 2008-03-19: the English PDF (ANO2008-06) returned HTTP 404, so the row cites the Turkish release DUY2008-11.

**Policy rate name.**
- Until 2010-05-17 the policy rate is the overnight borrowing rate.
- From 2010-05-18 it is the one-week repo rate.
  - The 2010-05-18 row is the "technical rate adjustment" that switched to the one-week repo rate. It is coded `hold`, `change_bp = 0`, with `rate_before = 6.50` (the O/N borrowing rate). The two levels are not comparable.
- 2018-05-28 (operational-framework release, effective 2018-06-01): the one-week repo became the sole policy and funding rate at 16.50%.
  - This row is coded `hike`, +850bp, scheduled = N. The notes say the change was technical: the effective marginal funding rate was already 16.5% through the late liquidity window (LLW) after the 2018-05-23 unscheduled meeting.

**Corridor era (2010-2018 and later).** Meetings where the one-week repo rate was unchanged but the corridor moved are coded `hold`. The notes record the O/N lending (marginal funding rate) and borrowing rates and the LLW moves.
- Additional monetary tightening (AMT) announcements (2011-2014) and liquidity-management releases (repo-auction suspensions in 2019, 2025 and 2026; the August 2020 "backdoor tightening") are not separate rows. They are mentioned in the notes of the nearest decision.
- The 2006-06-28 technical corridor change is included as a row: `hold`, scheduled = N. It was not an MPC meeting.

**Unscheduled decisions (scheduled = N):**
- 2006-06-07 and 2006-06-25 (interim meetings)
- 2006-06-28 (technical corridor change)
- 2011-08-04 (interim meeting)
- 2014-01-28 (interim meeting, announced at 24:00)
- 2018-05-23 (unscheduled meeting)
- 2018-05-28 (operational-framework release)
- 2020-03-17 (meeting brought forward from 19 Mar)
- 2025-03-20 (interim meeting)

**Dates and times.**
- 2005: decisions were published at 09:00 the day after the Monetary Policy Board met. Source: CBRT "General Framework of Inflation Targeting Regime ... for 2006" (ANO2005-45).
- 2006: English PDFs are often dated the day after the meeting. The Turkish release dates in the 2006 Turkish listing equal the meeting dates, so those dates are used. "Monetary and Exchange Rate Policy for 2007" says that from 2007 the English text is published on the same day.
- 2007 onward: the policy document said the decision would be released "before 7:00 pm" on the meeting day. The exact time is left blank.
- 14:00 is filled only for scheduled decisions from 2019 onward. The CBRT Monetary Policy pages state that decisions are announced at 2:00 p.m. on the meeting day, and Reuters-sourced items for 2019-2020 give 1100 GMT. The time for 2010-2018 was not checked, so it is blank.
- 2011-08-04: 12:00, stated in ANO2011-25.
- 2014-01-28: "24:00 hours", i.e. midnight 28/29 Jan, stated in ANO2014-03.

## Indonesia (BI)

**Access problem.** bi.go.id gives an empty reply to scripted access (curl). Its BI-Rate table and press-release archives page only through ASP.NET postbacks, so through WebFetch only the 10 most recent decisions (Feb-Oct 2026) can be seen. Bot checks were not worked around. Instead:
- **2026-02 to 2026-10:** the BI official BI-Rate table plus the BI press-release URLs it links to. The 9 Jun 2026 release (No. 28/119/DKom) and the 18 Sep 2024 release (No. 26/201/DKom) were also fetched.
- **2016-11 to 2026-01:** the Kontan data centre meeting-level table (https://pusatdata.kontan.co.id/makroekonomi/bi_rate). Kontan is a reputable Indonesian financial daily. Every rate change matches BIS.
  - One date was corrected: 2020-07-17 in Kontan becomes 2020-07-16, following Kontan news and BIS.
- **2005-07 to 2016-10:** meeting dates and levels come from decision-day news reports, cited row by row.
  - Kontan (search pages crawled back to Oct 2008) and Detik Finance (month-filtered search, 2005-2016).
  - Indonesia Investments for 2015-11-17.
  - Where no article was found, the BIS series is the source: 2006-05-09, 2006-08-08, 2006-11-07, 2006-12-07, 2007-05-08, 2008-05-06 and 2008-06-05. All of these are rate changes.
- The notes of each such row say that the source is secondary.

**Policy rate name.**
- The BI Rate was introduced on 2005-07-05 (first row). Its `rate_before` and `change_bp` are blank and it is coded `hold`, because there was no earlier policy rate. Before July 2005 BI had no policy rate, so Indonesia has no rows before then.
- The BI 7-Day (Reverse) Repo Rate applies from 2016-08-19. That row is coded `hold`, `change_bp = 0`, with `rate_before = 6.50` (the old BI Rate). BIS itself notes that the 6.5 to 5.25 step is not a cut.
- The rate was renamed BI-Rate from **2023-12-21** (BI's BI-Rate page), not in 2024.

**Unscheduled (scheduled = N):**
- 2005-08-30: +75bp to 9.5%, governor's press conference.
- 2013-08-29: additional Board meeting.
- 2014-11-18: additional Board meeting after the fuel-price hike.
- 2018-05-30: second decision in May 2018.
- 2026-06-09: weekly-meeting decision outside the monthly cycle, per the BI release.

**Known gap.** The March 2011 Board meeting (a hold at 6.75% is implied by the February and April levels) could not be dated from any fetched source. It is omitted rather than guessed.

**Times.** `announce_time_local` is blank for Indonesia. News timestamps (decision articles usually appear 12:00-15:00 WIB before 2016 and 14:00-17:00 WIB after) are publication times, not announcement times. Some are quoted in the notes.

## BIS cross-check

The cross-check used `WS_CBPOL/D.TR` and `D.ID`, downloaded on 2026-10-29. A BIS change counts as matched when the BIS date falls 0-4 days after a row's announcement date and the level is equal.

**Turkey.**
- All 92 BIS changes since 2005 match a hike or cut row. This includes the 2010-05-20 switch, which matches the 2010-05-18 row, and the 2018-06-01 step, which matches the 2018-05-28 row.
- BIS dates are usually effective dates, the day after the announcement.
- One row has no BIS change: the 2026-10-22 cut to 36%. The BIS series ends on 2026-10-16, so this is lag, not a conflict.

**Indonesia.**
- All BIS changes match a row except two. BIS shows 7.75 → 7.50 on 2014-11-25 and back to 7.75 on 2014-12-01. No BI decision corresponds to this, so it is very likely a BIS data error.
- One row is not in BIS: the 2005-08-30 hike to 9.5%. BIS goes straight from 8.75 to 10 on 2005-09-06. A Detik article quoting the BI governor's press conference confirms the hike.

## Expectation columns

These were filled only where a pre-decision consensus, or an explicit post-decision statement of what had been expected, was actually read in a fetched article. 43 rows are filled: Turkey 21, Indonesia 22.

**Turkey.** Mostly the Anadolu Agency (AA / AA Finans) economist surveys, 2019-2026. They were read on aa.com.tr directly or as reported by Hurriyet Daily News, Capital.com.tr, Azernews and Qatar Tribune. Other sources: Reuters and Bloomberg HT polls as reported by Qatar Tribune, and TR Monitor.
- The value is the survey median. Where only an average or "most economists" was reported, that figure is used and `expectation_basis` says so.

**Indonesia.** Reuters polls as reported by Kontan English (2019-2025), Bloomberg surveys as reported by Kontan (2010, 2026), and Kontan's own reporting.
- Some Kontan reports only say "sesuai ekspektasi" or "di luar dugaan" (in line with / contrary to expectations). For these, `expected_change_bp` is 0 for "unexpected" moves and equal to the actual move for "as expected" ones. The basis column says no poll size was given. Treat these as weaker than numeric polls.

**Not covered.** Most meetings before 2019 for Turkey and before 2024 for Indonesia have no expectation value. A systematic source (Reuters/Bloomberg survey archives, or AA Finans by date) would be needed to fill them.

## Reproducibility

Scratch downloads and build scripts are in `/tmp/claude-0/rates_trid/` (not in the repo):
- `tr/` holds the CBRT documents.
- `id/` holds the Kontan and Detik crawls.
- `bis/` holds the BIS series.
- `build/` holds the row tables, `build.py`, `expect.py` and `bischeck.py`.
