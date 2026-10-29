# elections_br_mx_pl.csv: method notes

Scope: national votes in Brazil, Mexico and Poland from 2005-01-01 to 2026-10-29. There is one row per voting day per contest, 41 rows in all (BRA 13, MEX 10, POL 18). Compiled 2026-10-29.

## Inclusions beyond the minimum list
- **Brazil:** the 2005 firearms referendum (23 Oct 2005) and the 2026 general election. Both rounds of 2026 were held (4 and 25 Oct 2026).
- **Mexico:** the 2021 consultation on prosecuting former presidents (1 Aug 2021), the 2022 recall referendum and the 2025 judicial election.
- **Poland:** the 2015 referendum (6 Sep). The 2023 referendum is included as a separate row because it is a separate contest. It shares its vote_date with the 2023 parliamentary election, so de-duplicate on date if needed.
- **Excluded:** Poland's 10 May 2020 presidential date, which was cancelled and never held. Also excluded are local/state elections, European Parliament elections, and the Mexican midterm due in 2027.

## Poll method
- **Aggregators:** used where a reputable one exists on a vote-share basis:
  - Brazil 2022: The Economist.
  - Brazil 2026: Poll+Trend.
  - Mexico 2018 and 2024: Oraculus.
  - Mexico 2006: Wikipedia's average of the last 10 polls.
  - Poland 2025: ewybory.eu.
- **Brazil, other years:** mean of the final Datafolha and Ibope polls, on valid votes. Where the source gave only total-vote shares (2010, 2014 R1), I converted them as share / (100 - blank/null/undecided).
- **Poland, no aggregator:** mean of the last poll by each pollster whose fieldwork ended in the 7 days before the vote. The window was extended to 10 days when fewer than 2 polls qualified.
  - Round-1 and parliamentary polls are "as published". Some pollsters include don't-knows, so levels sit a little low.
  - Runoff and yes/no polls are renormalised to two-option shares, which is comparable to valid-vote results.
- **Mexico midterms:** polls are party-level (effective vote), so cand_a and cand_b are parties, not coalitions. Coalition totals are given in notes.

## Sparse columns
- **odds_*** (6 of 41 rows). Verifiable pre-vote prices were found only for:
  - BR 2022 R2: Betfair, via BNLData.
  - BR 2026 R1 and R2: Polymarket, via a Rio Times live blog.
  - MX 2024: Polymarket, via MNI.
  - PL 2020 R2: Polish bookmakers, via Radio Kraków (approximate).
  - PL 2025 R2: William Hill, via gambling.com.

  For older elections, archived Betfair or PredictIt prices were not found.
- **market_preferred** (23 of 41 rows). It is left blank when the press framing was not clear-cut: Brazil 2006 and 2010, Mexico midterms 2009 and 2015, Mexico 2024 (the concern was the supermajority), Poland 2005 presidential, 2019 and 2020, and all referendums.
  - Several notes cite a source seen only through a search-engine snippet, because a direct fetch was blocked (403/404). These are flagged "[search snippet]". No numbers were taken from snippets.

## Rows to treat with care
- **BR 2026:** a very recent event. The Wikipedia page is still being edited. Results were cross-checked against MercoPress and Rio Times.
- **PL 2005 R2:** the poll figures are approximate ("around 52/48", PBS and OBOP as reported by RTE).
- **PL 2010 R2, MX 2022 recall, BR 2005 referendum:** each poll figure rests on a single poll, 3 to 30 days out.
- **PL 2015 R2, PL 2020 R2, PL 2025 R2, BR 2026 R2:** the final-poll leader is within about 1pp, so the a/b ordering is fragile.
- **MX 2012:** poll_date is blank. The source dates the final polls only as "June 2012".
- **BR 2006 R1:** this uses the 28 Sep releases. The 29-30 Sep finals were not located.
- **MX 2021 consultation, PL 2023 referendum:** there were no pre-vote polls, so a/b are ordered by the result.

Raw downloads used to build the file are in /tmp/claude-0/elections_brmxpl/. They were not committed.
