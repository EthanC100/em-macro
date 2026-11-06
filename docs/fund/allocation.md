# Horizons fund: allocation rule

Recorded 2026-11-06 (config change C04 in `docs/config_changes.md`). Code: `ledger/fund.py`. Tests:
`tests/test_fund.py`. Any change to this rule is a new config change, recorded before it takes effect.

## What the fund is

A combined view built from two of the separate books. The books keep their own records and P&L unchanged.

- The fund reads their published daily indices on every app build.
- It never writes a figure into any book: not into the algorithm's results, Janus's records, or my decisions.
- My own decisions (Me) are outside the fund.

| member | initial risk share |
|---|---|
| Algorithm v1.1 (v1.0 + T18, mechanical) | 90% |
| Janus (AI book) | 10% |

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

Evaluated at each month start, on data to the previous month end. The rules are checked in this order:

1. **5%** while Janus's drawdown exceeds **10%**. Drawdown is the fall of its equity index from its peak to date.
2. **20%** once Janus has **at least 30 resolved calls**, and on those same calls:
   - total net P&L after costs is **positive**, and
   - Janus's **Brier score is lower than the market's**. A call is "right" when its gross P&L is positive. Janus's
     Brier uses its stated probability; the market's uses the market probability recorded with the call.
3. Otherwise **10%**.

The algorithm takes the rest (90%, 80% or 95%). The share moves back as soon as the condition that moved it no
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
