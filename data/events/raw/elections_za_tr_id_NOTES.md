# elections_za_tr_id.csv: method notes

Scope: South Africa, Turkey and Indonesia national votes from 2005-01-01 to 2026-10-29. The file has 26 rows: ZAF 4, TUR 16, IDN 6. There is one row per voting day. The Turkey 2023 run-off is round=2, and every other row is round=1.

The data was compiled on 2026-10-29. Every number comes from a page fetched in that session, and the URL is given in the matching `*_source` column. Wikipedia pages were read as raw wikitext (current revision). Many rows have a free-text `notes` column that holds the caveats specific to that row.

## Poll rules
- **Window.** Where Wikipedia has a poll table, I took the most recent poll from each pollster whose fieldwork ended in roughly the final 3 weeks before the vote. I averaged those polls with equal weight. `poll_basis` lists the pollsters and dates for each row.
  - Turkey has a 10-day publication ban before votes. Polls released after the ban, which Wikipedia flags, are included and noted.
- **Exclusions.** Polls commissioned by parties (CHP, IYI, AKP) are excluded, as are DA-internal polls and Intellidex's 2019 "investor poll".
- **Candidate races** (presidential polls, the Istanbul re-run, Indonesian presidential polls). Each poll is rescaled so that the listed candidates sum to 100. This removes undecided and non-voters.
- **Party races and referendums.** I used shares as published. Most Turkish tables already exclude undecided. Where a pollster reported an explicit undecided/don't-know share, the two shares are divided by (1 - undecided), and this is stated in `poll_basis`.
- **Aggregators.** A reputable aggregate was used only for Turkey 2023: the POLITICO Poll of Polls, which is integer-rounded.
- **Thin or missing polls.**
  - No usable poll was found for: Turkey 2007 referendum, Turkey 2024 local elections, Indonesia 2009 legislative. The poll columns are blank for these rows.
  - Only one or two polls, or old polls, were available for: ZAF 2009, TUR 2007 general, TUR 2009 local, TUR 2010 referendum, TUR 2019 local, IDN 2009 presidential, IDN 2014 legislative.
  - Where no verified poll exists, cand_a/cand_b are not poll-ranked; `notes` says how they were ordered.

## Actual results
- I used official shares of valid votes from Wikipedia (citing YSK, IEC and KPU). Shares are computed from vote counts where needed (referendums and the 2023 first round).
- **Turkish local elections:**
  - 2009 uses the provincial-assembly vote.
  - 2014, 2019 and 2024 use the municipal-councillor vote, which is Wikipedia's headline basis. In 2014 provincial assemblies were abolished in metropolitan provinces, so the two bases are not strictly comparable.
- **Same-day general elections** (Turkey 2018 and 2023 first round, Indonesia 2019 and 2024): cand_a/cand_b are the presidential candidates.

## results_known
- **Turkey and Indonesia:** results were known on the night of the vote (Indonesian quick counts come out the same afternoon), so `results_known` equals `vote_date`.
- **South Africa:** `results_known` is the date the IEC results board made the outcome clear, as reported in the press. The IEC's final declaration date is given in `notes`.
  - 2009: 23 Apr (final 25 Apr)
  - 2014: 8 May (final 10 May)
  - 2019: 10 May (final 11 May)
  - 2024: 31 May, ANC clearly below 50% (final 2 Jun)

## Odds
These columns are filled only for Turkey 2023, in both rounds. I searched for 2018 Turkey, Indonesia 2024 (a Polymarket market existed) and South Africa, but found no verifiable pre-vote price.
- Round 1 uses a single-sided Smarkets price, so it is not normalised.
- Round 2 uses two-sided decimal odds, normalised for overround.

## market_preferred coding
This column is a judgment call: "a" or "b" only where pre-vote or immediate financial-press coverage clearly framed one side as market-friendly. Otherwise it is blank. Sources are in `market_preferred_note`.
- **South Africa:**
  - 2019 is coded "a": a strong ANC/Ramaphosa mandate was wanted.
  - 2024 is blank on purpose. Markets cared about ANC < 50% and who its coalition partner would be (ANC-DA preferred over ANC-EFF/MK), which an ANC-vs-DA winner coding cannot express.
  - 2009 and 2014 are blank because the ANC win was never in doubt and I found no clear framing.
- **Turkey:**
  - AKP single-party majority is coded "a" for 2007, 2011, Jun 2015 and Nov 2015.
  - "Yes" is coded "a" for the 2010 and 2017 referendums.
  - 2023: Kilicdaroglu was market-preferred, which is "a" in round 1 and "b" in round 2.
  - 2014 presidential, 2018 and all local votes are blank.
- **Indonesia:** every row is coded "a" (SBY/PD, PDI-P/Jokowi, Jokowi, Prabowo). The 2024 coding is moderate because of fiscal caveats, and parts of 2019 rest on the market reaction after the vote.
