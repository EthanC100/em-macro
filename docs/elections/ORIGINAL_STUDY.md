# The original election-surprise study: exact definitions

Written 2026-11-03 for the election tracker (`em_macro/election_tracker/`). Everything below is read from this
repository. Nothing is re-estimated, and no v1.0 or frozen file is changed.

> **Continuation is not established.** This study supports, weakly, one claim: the signed poll surprise predicts
> the **day-1** currency move. It does not show that the move continues after day 1, which is what the spec 4.10
> rule trades (§7). The election tracker exists to test continuation. It runs as pre-registered trial T15, paper and
> observation only: every implied position is logged with size 0.

## Where it is

| What | File |
|---|---|
| Write-up | `README.md` §3 (event calendar), §4 (method), §5 (fit-sample findings), §6 (hold-out), §12 (limitations) |
| Event calendar (167 rows, 13 countries; the study uses the 6 EM ones) | `data/events/elections.csv`, built from `data/events/raw/elections_*.csv` |
| Poll and coding rules | `data/events/raw/elections_br_mx_pl_NOTES.md`, `data/events/raw/elections_za_tr_id_NOTES.md` |
| Surprise construction | `em_macro/events.py`, `to_event_table()` |
| Event windows, FX return, abnormal move | `em_macro/event_study.py` (`asset_levels`, `window_dates`, `event_moves`) |
| Regressions and out-of-sample test | `em_macro/run.py` (`election_regressions`, `stage_test`) |
| Frozen coefficients (fit 2005–2021, committed before the test, commit `08c4f07`) | `results/fit/frozen_params.json`, `results/fit/election_surprise_regressions.csv`, `results/fit/factor_betas.csv` |
| Out-of-sample result (0.72, 8 of 9) | `results/test/oos_surprise_predictions.csv`, `results/test/event_moves.csv` |
| Chart | `results/fig_election_surprise.png` |
| Trial ledger | `trials.csv`: **T14** is this study (fit and hold-out results as in §6; "inconclusive", not a trading rule). **T15** is the spec 4.10 continuation rule as a pre-registered prospective trial (observation, zero size). T09 is the drift rule built on the same events (rejected). T07 is the pre-election repricing study (null). |

## 1. Market-relevant quantity

The **vote margin between the two leading options**, in percentage points:

- `cand_a` = the leader in the final pre-vote polls, `cand_b` = the runner-up (`elections.csv`).
- `margin = share(cand_a) − share(cand_b)`.
- Presidential races and run-offs: candidates. Same-day general elections (Turkey 2018/2023, Indonesia 2019/2024): the
  presidential candidates. Legislative races: parties (Mexico midterms: **individual parties, not coalitions**, on the
  effective vote). Referendums: the two options.
- Actual result: official shares of valid votes (Wikipedia citing the election authority).

The README is explicit that this misses coalition and seat-majority stakes: Mexico 2024 (Morena's supermajority) and
South Africa 2024 (ANC below 50%) were left uncoded for exactly this reason.

## 2. Poll average and surprise

**Poll margin.** "The final pre-election poll margin, from a poll average where one exists, otherwise the mean of
each pollster's last poll, with the basis recorded" (README §3). In practice the rule differed by country file:

| File | Rule as written |
|---|---|
| Brazil, Mexico, Poland | Reputable vote-share aggregator where one exists (Economist, Poll+Trend, Oraculus, ewybory.eu). Brazil other years: mean of final Datafolha and Ibope, valid votes. **Poland without an aggregator: mean of the last poll by each pollster whose fieldwork ended in the 7 days before the vote; extended to 10 days when fewer than 2 polls qualified.** Round-1 and parliamentary polls as published; run-off and yes/no polls renormalised to two-option shares. |
| South Africa, Turkey, Indonesia | Last poll from each pollster whose fieldwork ended in **roughly the final 3 weeks**, equal weight. Party-commissioned polls excluded. Candidate races rescaled so the listed candidates sum to 100. Party races and referendums as published, divided by (1 − undecided) where an undecided share is reported. |

**Poll error** = actual margin − final poll margin (pp; + = the poll leader beat its polls).

**Signed surprise** (`surprise_mp_pp`) = poll error × orientation, where orientation = +1 if `market_preferred` is
`a` and −1 if it is `b`. So **+ means the market-preferred side beat its polls**. Rows without a coding are excluded.

## 3. Market-sign convention

`market_preferred` ∈ {`a`, `b`, blank} is a **judgment code**: the side that "financial press called
market-friendly, with a citation" (`market_preferred_note`). Blank when the framing was not clear-cut (e.g. Brazil
2006 and 2010, Mexico midterms 2009 and 2015, Mexico 2024, all referendums except Turkey 2010 and 2017).

The currency is assumed to **fear the side that is not market-preferred**: a positive surprise should lift the
currency. Caveat recorded in the NOTES and README §12: several codings in Turkey, Indonesia and South Africa rely on
coverage of how markets reacted **after** the vote, which is look-ahead. The tracker therefore requires the sign to
be written down before the vote (spec 4.10).

## 4. Currency return

- Level: `x = −100 · ln(local currency per USD)`, so a move is the % change in the local currency's USD value
  (+ = appreciation, log-percent).
- Sources: FRED H.10 noon New York for BRL, MXN and ZAR; Yahoo Finance daily close for TRY, IDR and PLN.
- Window, for vote date *d*: base = last weekday strictly before *d*; day *h* = the *h*-th weekday strictly after
  *d*. A move at *h* is `x(day h) − x(base)`. Levels are the last observation on or before the date, at most 7
  calendar days stale, and the end must be a fresh print after the base. For a Sunday vote, day 1 = Friday close to
  Monday close.
- **The regressions use the abnormal move**: `ab_h = raw_h − [α·(h+1) + b_DXY·ΔDXY + b_US10·ΔUS10y + b_VIX·ΔlnVIX]`,
  with ΔDXY and ΔVIX in 100·log units and ΔUS10y in bp, and betas fitted on non-overlapping 5-day changes over
  2005–2021 (`results/fit/factor_betas.csv`).

## 5. Event universe

- Countries: **Brazil, Mexico, South Africa, Turkey, Indonesia, Poland**.
- Votes: national presidential, legislative and general elections (each round a separate row), national
  referendums, Turkey's nationwide local elections and the 2019 Istanbul re-run, Mexico's 2021–22 popular
  consultations and 2025 judicial election. One event per country-day (a same-day referendum is dropped).
- Fit sample: events whose 20-day window closes by 2021-12-31. Hold-out: 2022 onward.
- Regression sample: only rows with both a poll margin and a market-preferred code, and a day-1 FX move: **26
  fit-sample elections** (h = 1).

## 6. Fitted coefficients (frozen, `results/fit/frozen_params.json`)

Day-1 abnormal FX move (%) = **0.03679 + 0.05955 × surprise_mp_pp**, OLS with HC1 standard errors.

| Asset, horizon | n | const | slope per pp | t | p | R² |
|---|---|---|---|---|---|---|
| FX, day 1 | 26 | +0.0368 | **+0.0596** | 1.28 | 0.20 | 0.070 |
| FX, day 5 | 27 | +0.5568 | +0.0578 | 1.13 | 0.26 | 0.051 |
| FX, day 20 | 27 | +0.5363 | −0.0116 | −0.19 | 0.85 | 0.001 |
| 10y yield, day 1 (bp) | 17 | −16.51 | −2.41 | −1.99 | 0.047 | 0.307 |

A 10pp surprise in the market-preferred side's favour therefore predicts about +0.63% on day 1.

**Out of sample** (`results/test/oos_surprise_predictions.csv`, 9 hold-out elections: Poland 2023, Poland 2025 both
rounds, Turkey 2023 both rounds, Brazil 2022 both rounds, Brazil 2026 round 1, Indonesia 2024):

| Horizon | correlation (pred, actual) | right sign | OOS R² vs zero |
|---|---|---|---|
| day 1 | **0.72** | **8 of 9** (Indonesia 2024 missed) | 0.15 |
| day 5 | 0.61 | 4 of 9 | 0.13 |
| day 20 | −0.58 | 2 of 9 | −0.06 |

## 7. What the study does and does not show (read before trading on it)

1. **The fitted slope is not significant in-sample** (t = 1.3, p = 0.20, in-sample correlation 0.27). The 0.72 is on
   9 hold-out events. The README calls it "consistent evidence, not proof". Clopper–Pearson 95% interval for 8/9 is
   52–99%.
2. **"The move continues" is not established.** The spec 4.10 facts list states it as a finding; this study does
   not support that. In the fit sample, election FX moves **reversed** after day 1 (raw
   drift slope −0.55, t = −2.0); the pre-registered rule built on that (fade the day-1 move, T09) **lost money** in
   the hold-out because hold-out moves continued (slope +0.46, t = 1.7, n = 14, not significant).
3. **The spec 4.10 trade (enter at the day-1 close in the direction of the surprise, hold 5 days) was never tested
   by the study.** From the study's own event files, the post-day-1 move `postraw_5` (day 1 → day 5) signed by the
   surprise is: fit sample mean −0.21%, right direction 12 of 26; hold-out mean +0.77%, right direction 5 of 9 (the
   mean is driven by Turkey 2023 round 2 and Brazil 2022 round 2). Day 1 → day 20: fit −1.24% (10 of 26), hold-out
   +3.08% (4 of 9). This is a post-hoc look at already-spent data, recorded here only so nobody mistakes the
   day-1 result for evidence on the continuation trade.
4. The spec's sizing input "p from Beta(9,2) ≈ 0.82" is the day-1 sign hit rate. It is not the hit rate of the
   trade the rule actually places (day 1 → day 6).

**So continuation is an open question, and the tracker exists to answer it.** It is trial T15 in `trials.csv`,
pre-registered with this pass rule: after at least 15 new scored elections,
- the post-day-1 move (day-1 close to exit close, no stop) goes the surprise's way in at least 65% of events; and
- the mean trade return (5-day hold, close-based stop) is positive with one-sided p < 0.10 (one-sample t-test).

While T15 runs, the tracker is paper and observation only: positions are logged with size 0.

## 8. How the tracker uses this

- **Paper, observation only.** Every implied position is logged with size 0 and labelled "paper, observation
  only" in the results-night issue and in `data/elections/signals.csv`. What the spec 4.10 rule would have done
  (direction, risk, stop, notional, and the 5-day paper trade return) is still computed, so T15 can be scored.

- Quantity, orientation, poll window and FX return are coded exactly as above (`em_macro/election_tracker/rule.py`).
- The aggregator option is dropped because it cannot be reproduced point-in-time; the tracker uses the mechanical
  fallback the study itself used where no aggregator existed: the mean of each pollster's last poll with fieldwork
  ending in the final 7 days, widened to 10 days (Poland rule) and then 21 days (South Africa / Turkey / Indonesia
  rule) when fewer than 2 pollsters qualify. Normalisation follows the table in §2 and is set per election
  (`exclude_from_base` in `data/elections/tracker.yaml`): Poland as published (don't-knows kept), Mexico midterms
  on the effective vote, other party races with an explicit undecided share removed. Rows that are poll averages
  (e.g. ewybory.eu) or earlier results are dropped; a firm polling for several clients counts once.
- **Validation:** applied to the last Wikipedia revision of the Poland 2023 polling page saved before the vote
  (rev 1180142234, 14 Oct 2023 19:54 UTC), the rule reproduces the study's row exactly: PiS 34.31 vs KO 27.71,
  margin 6.60, 13 pollsters, 7-day window (`tests/test_election_tracker.py`).
- Expected day-1 move = 0.03679 + 0.05955 × surprise (abnormal %, local currency vs USD).
- The spec 4.10 rule says `result_share − final 7-day poll average`. The tracker keeps the study's **margin**
  (≈ 2 × the share error in a two-way race) because the frozen slope is per pp of margin.
