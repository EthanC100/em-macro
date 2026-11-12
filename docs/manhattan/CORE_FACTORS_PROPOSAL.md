# Manhattan core factors: a proposal for Ethan (not adopted)

Written 2026-11-12 by session "5M Manhattan C" as part of milestone E. **Nothing here is in force.** The core
factors decide what "core-hedged" means for every Manhattan family (PROTOCOL §2.2), so their definitions are
Ethan's to approve and are frozen before the first batch ([ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 10). This
file says what they could be, built from what the repository already holds, and lists the choices that are his.

## 1. What a core factor has to be

PROTOCOL §2.2 hedges every executable against `C_t`: "the vector of core factor returns in period `t` for the
executable's asset class: carry, trend, value and buy-and-hold". So a core factor must be:

1. **daily**: one return per trading day, because the hedge and every test are daily;
2. **tradable**: the return of positions fixed from earlier information, after costs, so that the hedged return
   is itself the return of a portfolio someone could hold;
3. **defined per asset class**, the same four names in each;
4. **frozen** before the first batch, with its code hashed in the batch manifest.

The repository has no daily factor today (AUDIT §1.2: the v1.0 sleeves are monthly and cover currencies and
bonds; the commodity sleeves are monthly and need licensed data; there is no commodity value factor and no
buy-and-hold series).

## 2. The proposal in one sentence

**Do not design new signals. Take each sleeve the repository has already frozen, keep its monthly decision rule
exactly, and let the Manhattan engine mark the resulting positions every day.** The engine was built for this:
decisions on a schedule (here, month ends) from point-in-time data, daily accounting in between
(`manhattan/engine/backtest.py`). A daily core factor is then the daily net return of a monthly-rebalanced
sleeve whose signal Ethan has already accepted once.

Milestone E checked that this works for two of them on public data: the engine reproduces the frozen carry
benchmark and the frozen T01 trend signal on six currencies to 2019
(`results/manhattan_engine/REPRODUCTION.md`).

## 3. Proposed definitions

Each factor is scaled to 10% annual volatility by the rule its source already uses, rebalanced at month ends,
decided from data available at the decision (publication lags from the data layer), executed at the next
available price, with the cost model of `results/cost_audit/cost_estimates.csv`.

| asset class | factor | definition (source, frozen) | data | can be built now? |
|---|---|---|---|---|
| Currencies (v1.0's 10) | carry | long the top third, short the bottom third by the cross-sectional z-score of the interest differential, inverse-volatility weights (`em_macro.systematic.signals`, `book_weights`, `use=["carry"]`) | public | yes, in a session (exploration dates only) |
| | trend | T01's signal: the mean over 1, 3, 6 and 12 months of the clipped volatility-scaled return, sized by inverse volatility (`em_macro.tstrend`) | public | yes |
| | value | v1.0's value z-score, same book rule (`use=["value"]`) | public; uses latest-vintage inflation, so it needs a declared publication lag | yes, once the lag is fixed |
| | buy-and-hold | equal weight in every currency's deposit against dollar cash (`em_macro.carry`, the equal-weight basket) | public | yes (reproduced) |
| Ten-year bonds (v1.0's 13) | carry, trend, value | the same three rules on v1.0's bond book | public; for several countries only monthly yields exist (AUDIT §1.3) | **partly**: only the bonds with a daily yield |
| | buy-and-hold | equal weight in every bond, duration-matched, financed at the local short rate | as above | partly |
| Commodity futures (24) | carry | the T20 carry sleeve (front against deferred) | licensed (Norgate) | only on the iMac or with em-macro-data |
| | trend | the T22 diversified trend sleeve restricted to commodities | licensed | as above |
| | value | **none exists.** Candidate: minus the five-year return (the measure Asness, Moskowitz and Pedersen 2013 use; to be checked against the paper before any code); it would be a new definition and needs Ethan's decision | licensed | as above |
| | buy-and-hold | equal weight in every market's excess-return index | licensed | as above |
| Financial futures (5 currency, 5 bond) | carry, trend, buy-and-hold | the T22 sleeve's rules on those ten markets | licensed | as above |
| | value | none proposed; hedge on three factors | - | - |

## 4. Choices that are Ethan's

1. **Adopt the principle of section 2, or not.** The alternative is new daily signals, which would be a research
   project of its own and would need its own evidence.
2. **Which asset classes get a core hedge at the first batch.** Currencies can be done from public data.
   Bonds need daily marks for the countries that have only monthly yields. Commodities and financial futures need the
   licensed history, which ends about 5 May 2027 unless renewed (item 8).
3. **Commodity value**: adopt minus the five-year return, or hedge commodities on three factors.
4. **The hedge's own constants** stay those of PROTOCOL §2.2 (`L_β = 756`, `κ`); nothing here changes them.
5. **Where the factor series live.** Currency factors can be recomputed by anyone from the public panel. Any
   series built from Norgate or Databento prices is licensed data row by row and stays out of this repository
   (hard rule 7): it would be built by the runner on the iMac, with only its hash public.
6. **Dates.** Building a factor through 2020 to 2026 reads dates no session may read today (`reserve.enabled:
   false`); it is not a confirmatory test, but it is still Ethan's to allow, and it belongs with the fence
   (item 1).

## 5. What a session can do next without any decision

Build the four currency factors through 2019-12-31 with the engine and check each against its frozen source,
as milestone E did for two of them. That is all exploration-role work on public data.
