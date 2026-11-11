# Horizons fund: allocation rule

Recorded 2026-11-06 (config change C04 in `docs/config_changes.md`), amended 2026-11-07 before the fund starts
(see the amendment at the end). Code: `ledger/fund.py`. Tests: `tests/test_fund.py`. Any change to this rule is a
new config change, recorded before it takes effect.

## What the fund is

A combined view built from two of the separate books. The books keep their own records and P&L unchanged.

- The fund reads their published daily indices on every app build.
- It never writes a figure into any book: not into the algorithm's results, Janus's records, or my decisions.
- My own decisions (Me) are outside the fund.

| member | initial risk share |
|---|---|
| Algorithm v1.1 (v1.0 + T18, mechanical) | 80% |
| Janus (AI book) | 20% |

The fund starts at 100 on the first date every member is live. v1.1's live record starts with the 3 December 2026
rebalance, with index 100 on 30 November 2026. Before then the fund shows "not started" and the allocation the
rule gives today.

## Combining by risk

- **When:** at each month start (and at the fund's start), using data up to the previous month end.
- **Trailing volatility:** for each member, the standard deviation of its completed monthly returns over up to the
  last 12 months, annualised with √12.
- **Weights:** each member's weight = its risk share ÷ its trailing volatility, normalised so the weights sum to 1.
  The fund is not levered.
- **Fallback:** until every member has at least 6 completed months of live data, the weights are the risk shares
  themselves (capital shares).
- **Daily return:** weights are held fixed through the month, and the fund's daily return is Σ weight × the
  member's daily return. Each member's index is carried forward on days it has no point. The algorithm books its
  official P&L at month ends and shows an estimate within the month.

## Janus's risk share

Evaluated at each month start, on data to the previous month end. Janus starts at **20%**. The rules are checked
in this order:

1. **5%** while Janus's drawdown exceeds **10%**, overriding the others. Drawdown is the fall of its equity index
   from its peak to date.
2. **20%** (the starting share) until Janus has **at least 30 resolved calls**.
3. Then, on those same calls:
   - **30%** if total net P&L after costs is **positive** and Janus's **Brier score is lower (better) than the
     market's**;
   - **10%** if total net P&L after costs is **negative**, or Janus's **Brier score is higher (worse) than the
     market's**.

   A call is "right" when its gross P&L is positive. Janus's Brier uses its stated probability; the market's uses
   the market probability recorded with the call. **From config changes C08 and C09 (11 November 2026) a resolved
   call is one call per correlation cluster of forced forecasts, defined in "Resolved calls under C08 and C09"
   below.**
4. Otherwise **20%**. This covers an exact tie: net P&L of exactly zero, or a Brier score equal to the market's,
   with no failure on the other measure.

The algorithm takes the rest (80%, 70%, 90% or 95%). The share moves as soon as the condition that moved it no
longer holds at a month start. The risk share only changes the fund's weights. Janus's own book, limits and
records are unaffected.

## The market's probability (required on every Janus position)

Every new Janus position records the market's probability that the view is right (`market_probability`, in %
like `probability`), with `market_source` and `market_basis`. The CLI rejects a position without them. Use the best
market-implied figure available:
- **options:** the risk-neutral probability implied by option prices or by the futures/option curve at the
  position's levels;
- **prediction market:** for example a Kalshi or Polymarket contract on the event the thesis turns on;
- **futures:** for example the probability of a rate move implied by fed funds or SOFR futures;
- **other market:** another market-implied measure, named in the source.

Where no market-implied probability exists, record **50** (0.50) with `market_basis: "none"` and a source that says
so. The comparison on that call is then against a coin flip. Calls recorded before this requirement would count
only if they recorded a market probability, but there are none: Janus had opened no position when it was added.

## Correlation

The correlation of completed monthly returns between Algorithm v1.1, Janus and Me (Me for information only). It is
shown for a pair once the two books share at least 6 completed months.

## Amendment, 2026-11-07: starting share 20%, then 30% or 10% (C04)

Decided by the owner before the fund starts (30 November 2026) and before any Janus call resolved: Janus had no
closed position, so the change was made without seeing any Janus result.

| | before | from this amendment |
|---|---|---|
| Janus's starting risk share (algorithm v1.1) | 10% (90%) | **20% (80%)** |
| at least 30 resolved calls, net P&L > 0 and Brier better than the market | 20% | **30%** |
| at least 30 resolved calls, net P&L < 0 or Brier worse than the market | 10% (the base share) | **10%** |
| drawdown above 10% | 5%, overriding | 5%, overriding (unchanged) |

Unchanged: the members, combining by risk (risk share ÷ trailing 12-month volatility, capital shares until 6
completed months), evaluation at each month start on data to the previous month end, the 30-call threshold, the
Brier and P&L definitions, the required market probability, and the correlation display.

## Resolved calls under C08 and C09 (config changes C08 and C09, 2026-11-11)

From the 11 November 2026 daily review, Janus no longer chooses positions. Every daily review gives a probability
for every instrument on its watchlist (`janus/watchlist.yaml`), and the CLI sets the book from those forecasts
(`docs/config_changes.md` C08). Every forecast is logged and resolved with a Brier score. Two kinds of overlap would
make a count of forecasts overstate the evidence:
- **In time:** a forecast made today and one made tomorrow cover almost the same 20 trading days.
- **Across instruments:** the G10 yields move together, and so do the dollar's G10 crosses.

So the rule counts calls as follows. C09 set this before any C08 forecast was made, and before the fund starts. It
replaces C08's first wording, one forecast per instrument per window, which never applied.

- **A resolved call is one call per correlation cluster per non-overlapping 20-trading-day window.** The clusters
  are defined in the watchlist, and every instrument is in exactly one:

  | cluster | instruments |
  |---|---|
  | G10 yields | US10Y, GB10Y, DE10Y, JP10Y |
  | USD vs G10 FX | EUR, GBP, JPY, AUD |
  | EM FX | BRL, MXN |
  | gold | none yet: no free, republishable daily gold mark exists |

  Each forecast records its cluster when it is made.
- **A cluster call** is that cluster's forecasts from one daily review. Its window runs from the earliest base mark
  to the latest end mark among them.
- **Which calls count.** For each cluster, in the order of the reviews:
  - the first C08 review's call counts;
  - the next one counted is the first whose earliest base mark is dated on or after the end of the last one
    counted.

  The windows follow each other without overlapping. Which call counts depends only on dates, never on outcomes, so
  no call can be picked after the fact.
- **When it resolves.** Each forecast's window runs from its base mark (the first first-hand daily mark dated on or
  after the forecast's date) to its end mark (the first first-hand daily mark dated on or after the 20th weekday
  after the base mark). A cluster call resolves when all its forecasts have resolved. It counts toward the rule at
  a month start when its window ends on or before the previous month end.
- **Scoring.** A forecast is right when the question resolves the way it leaned: YES with `p_final` above 50, or NO
  with `p_final` below 50. Each forecast's Brier score uses the outcome itself (1 for YES, 0 for NO):
  - Janus's uses `p_final`, its probability after The Opposition;
  - the market's uses the `market_probability` recorded with the forecast, which is 50 with basis `none` when no
    market-implied probability was given.

  A cluster call scores the mean of its forecasts' Brier scores, for Janus and for the market. The rule compares
  Janus's mean over the resolved calls with the market's.
- **P&L.** Positions are now set mechanically from all the forecasts together, so no position belongs to a single
  call. "Total net P&L after costs on those calls" is therefore Janus's net P&L after costs from the end of
  10 November 2026 (the last day before C08) to the evaluation date: the change in its equity index, in % of the
  starting account. It includes closing J001 and J002, which was C08's first action.
- **Earlier positions.** Positions opened before C08 (J001, J002) are not resolved calls under this definition.
- **Rate.** Three clusters have instruments, so about three calls resolve every 20 trading days. The 30-call
  threshold is therefore reached roughly ten months after the first C08 forecasts.

Unchanged: the members, the starting 20% share, 30% and 10% after at least 30 resolved calls, the 5% drawdown
override, the evaluation at each month start on data to the previous month end, combining by risk, and the
correlation display. Code: `fund_calls` in `ledger/janus.py` (in Janus's summary) and `janus_record_c08` in
`ledger/fund.py`. Changing the clusters is a new config change.
