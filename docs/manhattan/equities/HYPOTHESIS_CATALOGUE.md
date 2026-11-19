# Technology equities: hypothesis-family catalogue

Generated from `manhattan/equities/catalogue.yaml` by `python -m manhattan.equities.catalogue render`. Do not edit by hand.

**Status: draft.** Every row is an untested hypothesis family. Nothing here is evidence, and no performance figure is stated. Rankings are qualitative 1–5 judgements made before any data were examined (5 is the favourable end); the priority order is a research-ordering device, not an expected return.

39 families: A_relative_value 8, B_analogues 5, C_earnings 7, D_diffusion 6, E_factor 7, F_macro 6; relative value 21, directional 18.

**Multiple-testing denominator.** All 39 entries remain (no id removed or renumbered). Shared families group related entries; they never shrink the count of entries, and any attempt on any entry would count.

## Priority order

Lexicographic: affordable data tier first (prices and EDGAR, then EDGAR text, then unavailable history), then min(leakage safety, data feasibility), plausibility, distinctiveness, research cost, simplicity.

| # | id | family | shared family | data tier | approach | sign | horizon | costs | plaus. | data | cost | simpl. | distinct. | leak-safe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TE-E03 | Short-term reversal | SF-REVERSAL | prices_and_edgar | relative_value | - | 5-20 trading days | high | 4 | 4 | 4 | 4 | 1 | 4 |
| 2 | TE-E01 | Price momentum within technology | SF-MOMENTUM | prices_and_edgar | directional | + | 20-120 trading days | medium | 3 | 4 | 5 | 5 | 1 | 4 |
| 3 | TE-E02 | Technology sub-industry momentum | SF-MOMENTUM | prices_and_edgar | directional | + | 20-120 trading days | low | 3 | 4 | 4 | 4 | 1 | 4 |
| 4 | TE-E05 | Investment, issuance and stock-compensation dilution |  | prices_and_edgar | relative_value | - | 60-250 trading days | low | 4 | 3 | 4 | 4 | 2 | 3 |
| 5 | TE-E04 | Profitability and earnings quality |  | prices_and_edgar | directional | + | 60-250 trading days | low | 4 | 3 | 4 | 4 | 1 | 3 |
| 6 | TE-E07 | Cash runway and balance-sheet strength | SF-FINANCING | prices_and_edgar | directional | + | 60-250 trading days | medium | 3 | 3 | 4 | 4 | 2 | 3 |
| 7 | TE-A01 | Peer-spread reversion within technology sub-industries | SF-REVERSAL | prices_and_edgar | relative_value | - | 3-20 trading days | high | 3 | 4 | 4 | 3 | 2 | 3 |
| 8 | TE-A07 | Residual (idiosyncratic) momentum | SF-MOMENTUM | prices_and_edgar | relative_value | + | 20-120 trading days | medium | 3 | 3 | 4 | 3 | 2 | 4 |
| 9 | TE-E06 | Intangible-adjusted value | SF-VALUATION | prices_and_edgar | directional | + | 120-500 trading days | low | 3 | 3 | 3 | 3 | 2 | 3 |
| 10 | TE-A08 | Index reconstitution flow in technology stocks |  | prices_and_edgar | relative_value | + | 5-30 trading days | medium | 4 | 2 | 3 | 2 | 3 | 3 |
| 11 | TE-F01 | Discount-rate shocks and equity duration |  | prices_and_edgar | relative_value | - | 5-60 trading days | medium | 4 | 4 | 3 | 3 | 2 | 2 |
| 12 | TE-F02 | Credit conditions and financing-dependent technology | SF-FINANCING | prices_and_edgar | relative_value | - | 20-120 trading days | medium | 3 | 4 | 3 | 3 | 2 | 2 |
| 13 | TE-B01 | Growth-stage trajectory analogues | SF-ANALOGUES | prices_and_edgar | directional | + | 120-500 trading days | low | 2 | 2 | 2 | 2 | 4 | 1 |
| 14 | TE-F03 | Energy costs and data-centre-intensive firms |  | prices_and_edgar_text | relative_value | - | 20-120 trading days | medium | 2 | 3 | 3 | 3 | 3 | 2 |
| 15 | TE-B05 | Thematic episode analogues | SF-ANALOGUES | prices_and_edgar_text | directional | - | 60-500 trading days | low | 2 | 3 | 2 | 2 | 4 | 1 |
| 16 | TE-C01 | Post-earnings-announcement drift | SF-EARNINGS-SURPRISE | needs_unavailable_history | relative_value | + | 5-60 trading days | medium | 4 | 3 | 4 | 4 | 1 | 3 |
| 17 | TE-A06 | Parent-subsidiary and carve-out stub mispricing |  | needs_unavailable_history | relative_value | + | 60-500 trading days | medium | 4 | 2 | 2 | 2 | 4 | 3 |
| 18 | TE-D01 | Foundry and chipmaker capex diffusion to equipment suppliers | SF-SUPPLY-CHAIN | needs_unavailable_history | directional | + | 60-250 trading days | low | 4 | 2 | 2 | 2 | 4 | 2 |
| 19 | TE-A02 | Short-sale-constrained overpricing in technology stocks | SF-SHORT-CONSTRAINTS | needs_unavailable_history | relative_value | - | 20-60 trading days | high | 4 | 2 | 3 | 3 | 3 | 2 |
| 20 | TE-A05 | Customer-to-supplier price lead-lag | SF-SUPPLY-CHAIN | needs_unavailable_history | relative_value | + | 5-40 trading days | medium | 4 | 2 | 2 | 2 | 3 | 2 |
| 21 | TE-C02 | Revenue surprise in technology firms | SF-EARNINGS-SURPRISE | needs_unavailable_history | directional | + | 5-60 trading days | medium | 4 | 2 | 3 | 4 | 2 | 3 |
| 22 | TE-A03 | Peer-relative consensus revisions | SF-REVISIONS | needs_unavailable_history | relative_value | + | 20-60 trading days | medium | 4 | 2 | 3 | 3 | 2 | 2 |
| 23 | TE-D04 | Customer-industry conditions and vertical software vendors |  | needs_unavailable_history | relative_value | + | 20-120 trading days | medium | 3 | 2 | 2 | 2 | 4 | 2 |
| 24 | TE-B02 | Implied growth versus historical base rates | SF-VALUATION | needs_unavailable_history | relative_value | - | 120-500 trading days | low | 3 | 2 | 3 | 3 | 3 | 2 |
| 25 | TE-B03 | Inventory and margin cycle analogues | SF-SEMI-CYCLE | needs_unavailable_history | relative_value | - | 60-250 trading days | low | 3 | 3 | 3 | 3 | 3 | 2 |
| 26 | TE-F05 | Currency moves and international revenue exposure |  | needs_unavailable_history | relative_value | - | 20-120 trading days | medium | 3 | 2 | 3 | 3 | 3 | 3 |
| 27 | TE-F06 | Volatility regimes and crowding unwinds |  | needs_unavailable_history | directional | - | 5-60 trading days | medium | 3 | 2 | 2 | 2 | 3 | 2 |
| 28 | TE-C04 | Analyst revision breadth | SF-REVISIONS | needs_unavailable_history | directional | + | 20-60 trading days | medium | 3 | 2 | 3 | 4 | 2 | 2 |
| 29 | TE-C05 | Analyst disagreement under short-sale constraints | SF-SHORT-CONSTRAINTS | needs_unavailable_history | relative_value | - | 20-120 trading days | medium | 3 | 2 | 3 | 4 | 2 | 2 |
| 30 | TE-A04 | Fundamentals-implied valuation residual within peers | SF-VALUATION | needs_unavailable_history | relative_value | + | 60-250 trading days | low | 3 | 2 | 3 | 3 | 2 | 3 |
| 31 | TE-F04 | Semiconductor and industrial cycle rotation | SF-SEMI-CYCLE | needs_unavailable_history | relative_value | + | 60-250 trading days | low | 3 | 3 | 3 | 3 | 2 | 2 |
| 32 | TE-D02 | Cloud and AI compute demand diffusion to infrastructure suppliers | SF-SUPPLY-CHAIN | needs_unavailable_history | directional | + | 60-250 trading days | low | 4 | 1 | 2 | 2 | 4 | 1 |
| 33 | TE-C03 | Management guidance surprise | SF-EARNINGS-SURPRISE | needs_unavailable_history | directional | + | 5-60 trading days | medium | 4 | 1 | 2 | 3 | 3 | 2 |
| 34 | TE-B04 | Business-model transition analogues | SF-ANALOGUES | needs_unavailable_history | directional | + | 120-500 trading days | low | 3 | 1 | 2 | 2 | 4 | 1 |
| 35 | TE-D05 | Data-centre build-out diffusion to power and thermal suppliers | SF-SUPPLY-CHAIN | needs_unavailable_history | directional | + | 60-250 trading days | low | 3 | 1 | 2 | 2 | 4 | 1 |
| 36 | TE-C06 | Forward margin revisions | SF-REVISIONS | needs_unavailable_history | directional | + | 20-120 trading days | medium | 3 | 1 | 2 | 3 | 3 | 2 |
| 37 | TE-D06 | End-device product cycles and component suppliers | SF-SUPPLY-CHAIN | needs_unavailable_history | relative_value | + | 20-120 trading days | medium | 3 | 1 | 2 | 2 | 3 | 1 |
| 38 | TE-C07 | Earnings-call language |  | needs_unavailable_history | directional | + | 5-60 trading days | medium | 3 | 1 | 1 | 2 | 3 | 1 |
| 39 | TE-D03 | Security-incident diffusion to cybersecurity vendors |  | needs_unavailable_history | directional | + | 60-250 trading days | low | 2 | 1 | 2 | 2 | 4 | 1 |

## Shared hypothesis families

Entries that test overlapping mechanisms or near-identical signals. Their ids are kept (drafts). **This grouping is declared, not enforced:** nothing in freezing or attempt accounting reads it today. If frozen, each group should be registered as one Manhattan family (or linked by `parent_family`) and counted together for multiple testing; that enforcement is part of a future freeze (Ethan's).

| shared family | members |
|---|---|
| SF-ANALOGUES | TE-B01, TE-B04, TE-B05 |
| SF-EARNINGS-SURPRISE | TE-C01, TE-C02, TE-C03 |
| SF-FINANCING | TE-E07, TE-F02 |
| SF-MOMENTUM | TE-A07, TE-E01, TE-E02 |
| SF-REVERSAL | TE-A01, TE-E03 |
| SF-REVISIONS | TE-A03, TE-C04, TE-C06 |
| SF-SEMI-CYCLE | TE-B03, TE-F04 |
| SF-SHORT-CONSTRAINTS | TE-A02, TE-C05 |
| SF-SUPPLY-CHAIN | TE-A05, TE-D01, TE-D02, TE-D05, TE-D06 |
| SF-VALUATION | TE-A04, TE-B02, TE-E06 |

## Data feasibility

Computed from each family's required data (`catalogue.data_tier`); unverified until the checks of DATA_ACQUISITION.md section 4 are done.

- **prices_and_edgar**: one survivorship-free price source, EDGAR structured data and free public series.
- **prices_and_edgar_text**: also EDGAR text parsed point in time.
- **needs_unavailable_history**: a history that is unaffordable or not verifiably point in time; forward collection or a data decision first.

Caveat: relative-value families in the first two tiers do not list borrow history among their data, but their short legs need it. Without an affordable borrow history they can be studied only with explicit, flagged borrow assumptions (a `costs.BorrowBook` with no record refuses the short), and any such result says so.

| tier | families | blocked by |
|---|---|---|
| prices_and_edgar | 13: TE-A01, TE-A07, TE-A08, TE-B01, TE-E01, TE-E02, TE-E03, TE-E04, TE-E05, TE-E06, TE-E07, TE-F01, TE-F02 |  |
| prices_and_edgar_text | 2: TE-B05, TE-F03 |  |
| needs_unavailable_history | 24: TE-A02, TE-A03, TE-A04, TE-A05, TE-A06, TE-B02, TE-B03, TE-B04, TE-C01, TE-C02, TE-C03, TE-C04, TE-C05, TE-C06, TE-C07, TE-D01, TE-D02, TE-D03, TE-D04, TE-D05, TE-D06, TE-F04, TE-F05, TE-F06 | analyst_estimates_pit, borrow_availability, cloud_capex, developer_adoption, earnings_call_text, options_implied_vol, product_adoption, product_releases, relationship_graph, semiconductor_supply_chain |

## Families

### TE-A01 Peer-spread reversion within technology sub-industries

*A_relative_value, relative_value, mechanism class flow, sign -, horizon 3-20 trading days, implementation medium; data tier prices_and_edgar; shared family SF-REVERSAL.*

**Rationale.** Close economic substitutes (firms with the same products, customers and cost structure) should share most of their non-idiosyncratic return. When the price spread between a stock and its closest peers widens without a matching change in fundamentals, part of the move is temporary price pressure from liquidity-demanding trades. Liquidity providers who bet on convergence are paid for absorbing it.

**Counterparty.** Investors who need immediacy (fund redemptions, single-name hedges, thematic basket flows) and accept a price concession to trade now rather than wait for natural offsetting interest.

**Universe.** US-listed technology companies (semiconductors, hardware, software, IT services) passing PIT liquidity and price filters, grouped by PIT sub-industry classification

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, earnings_events

**Availability risks.** (1) Peer groups formed with today's classification inherit look-ahead; classification_history must be point in time. (2) Pair or basket selection on the full sample (cointegration found ex post) leaks the evaluation window into formation. (3) Delisted and acquired names must stay in the universe; merger arbitrage spreads can masquerade as divergence.

**Signal concept.** Standardised deviation of a stock's cumulative return from a peer-basket or paired-stock fitted relation, estimated only on data available at formation, excluding windows that contain the stock's own earnings announcement or a corporate event.

**Baselines.** one-month short-term reversal (market-wide); industry-demeaned short-term reversal; market beta and sub-industry exposure

**Confounders.** generic short-term reversal (TE-E03); bid-ask bounce and stale prices in less liquid names; announcement-driven information that should not revert; pending mergers and tender offers

**Costs (high).** Short holding periods imply high turnover on both legs, and the short leg needs borrow that may be costly or recalled exactly when the spread is widest.

**Validation requirements.** (1) Pairs or baskets selected only from data before each formation date (rolling formation, never full-sample). (2) Evaluation windows follow Manhattan data roles; no parameter is chosen on an evaluation window. (3) Results reported net of spread, impact and borrow assumptions, with one-day implementation lag. (4) Multiple-testing correction across the grouped variants (distance, cointegration, basket regression). (5) Separate results for event-free and event-containing divergences.

**Failure conditions.** (1) No reversion beyond what market-wide short-term reversal already captures. (2) Profits disappear after a one-day lag or realistic costs. (3) Divergences predominantly reflect information (they continue rather than revert).

**Kill condition.** Peer-spread reversion adds nothing net of costs to industry-demeaned short-term reversal on the held-out windows.

**Tail exposure.** Losses concentrate when a divergence marks a permanent re-rating (a lost design win, a takeover), and in deleveraging events where crowded statistical-arbitrage books unwind together.

**Grouped variants.** Distance-based pairs, cointegration-based pairs, regression residual against a sub-industry basket, formation and trigger thresholds, look-back lengths and stop rules; all are one liquidity-provision mechanism.

### TE-A02 Short-sale-constrained overpricing in technology stocks

*A_relative_value, relative_value, mechanism class structural, sign -, horizon 20-60 trading days, implementation medium; data tier needs_unavailable_history (blocked by borrow_availability); shared family SF-SHORT-CONSTRAINTS.*

**Rationale.** When short selling is costly or constrained, prices reflect the views of the most optimistic holders. Technology stocks with contested narratives often carry high short interest and high borrow fees, so pessimistic information enters prices slowly. High and rising shorting demand relative to lendable supply should precede negative hedged returns.

**Counterparty.** Optimistic long holders and retail momentum buyers who keep prices above the level a frictionless market would set, because the investors who disagree cannot easily sell short.

**Universe.** US-listed technology companies passing PIT liquidity filters, with short interest and borrow data available at formation

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, short_interest, borrow_availability, classification_history

**Availability risks.** (1) Short interest is published with a dissemination lag; using the settlement date instead of the publication date is look-ahead. (2) Borrow-fee and utilisation histories are vendor products with uncertain historical coverage and backfill. (3) Small, hard-to-borrow names may drop out of vendor coverage, creating survivorship in the signal.

**Signal concept.** Shorting pressure measured as short interest relative to float or volume (days to cover), or borrow utilisation and fee, compared with sub-industry peers and lagged to its publication date.

**Baselines.** size and liquidity; idiosyncratic volatility; 12-1 momentum and short-term reversal

**Confounders.** idiosyncratic volatility and lottery-like demand; small-cap and low-price effects; analyst forecast dispersion (TE-C05)

**Costs (high).** The signal lives in the names that are hardest and most expensive to short, so the short leg's borrow cost and recall risk may consume the predicted return.

**Validation requirements.** (1) Short-interest values aligned to publication timestamps, not settlement dates. (2) Returns measured net of the borrow fee actually observable at the time, not a flat assumption. (3) Results shown with and without the smallest and hardest-to-borrow names. (4) Control for idiosyncratic volatility, size and dispersion before attributing to shorting pressure.

**Failure conditions.** (1) Predictive power vanishes after realistic borrow fees. (2) Effect is fully explained by size, volatility or dispersion. (3) Effect exists only in names that cannot be borrowed at all.

**Kill condition.** Shorting pressure does not predict negative peer-relative returns after borrow costs and controls for size, volatility and dispersion.

**Tail exposure.** Short squeezes in heavily shorted technology names can produce extreme, fast losses on the short leg, often clustered in speculative episodes.

**Grouped variants.** Short interest to float, days to cover, change in short interest, utilisation, borrow fee and their peer-relative versions; formation frequency.

### TE-A03 Peer-relative consensus revisions

*A_relative_value, relative_value, mechanism class informational, sign +, horizon 20-60 trading days, implementation medium; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-REVISIONS.*

**Rationale.** Analysts revise forecasts gradually and herd towards each other, so revisions are autocorrelated and prices adjust to the cumulative change with a lag. Comparing a firm's revisions with those of its sub-industry peers removes common sector news and isolates firm-specific information that is likely to be underweighted.

**Counterparty.** Investors anchored on prior estimates and those trading sector baskets, who price firm-specific revision news slowly.

**Universe.** US-listed technology companies with sufficient analyst coverage at formation, grouped by PIT sub-industry

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, analyst_estimates_pit, earnings_events

**Availability risks.** (1) Consensus histories are prone to backfill and to the removal of analysts or brokers after the fact. (2) Estimate timestamps may reflect vendor processing date rather than publication date. (3) Coverage changes (initiations, drops) are themselves informative and can bias peer comparisons.

**Signal concept.** Change in consensus forward earnings (or revenue) over a recent window, scaled by price or by cross-sectional dispersion, minus the same quantity for sub-industry peers.

**Baselines.** industry-relative 12-1 momentum; earnings surprise drift (TE-C01); market beta

**Confounders.** price momentum (revisions follow prices); post-announcement drift when revisions cluster after earnings; revision breadth (TE-C04)

**Costs (medium).** Monthly rebalancing with moderate turnover; the short leg is mostly in covered, liquid names.

**Validation requirements.** (1) Consensus snapshots taken as they stood on each formation date, from a source that records as-of timestamps. (2) Orthogonalise against price momentum and earnings drift before claiming incremental content. (3) Check sensitivity to coverage thresholds and to excluding announcement windows.

**Failure conditions.** (1) No incremental prediction after controlling for price momentum and earnings drift. (2) Effect depends on a vendor's backfilled history and disappears in live-captured snapshots.

**Kill condition.** Peer-relative revisions add no hedged return beyond momentum and earnings drift on properly as-of consensus data.

**Tail exposure.** Revision momentum and price momentum are crowded together and can reverse sharply in growth-to-value rotations.

**Grouped variants.** Earnings versus revenue revisions, look-back window, scaling by price or by dispersion, fiscal-year versus forward-twelve-month estimates, peer definition (sub-industry or custom peer set).

### TE-A04 Fundamentals-implied valuation residual within peers

*A_relative_value, relative_value, mechanism class behavioural, sign +, horizon 60-250 trading days, implementation medium; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-VALUATION.*

**Rationale.** Within a sub-industry, valuation multiples should be explained by observable growth, margins and reinvestment. A stock trading below the multiple implied by its own fundamentals, relative to peers, may be mispriced because investors overweight narratives and recent price moves. As fundamentals are reported the residual should partly close.

**Counterparty.** Narrative-driven investors who pay up for popular stories and neglect peers with comparable fundamentals but less attention.

**Universe.** US-listed technology companies with positive revenue and PIT fundamentals, grouped by sub-industry

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, fundamentals_pit, analyst_estimates_pit

**Availability risks.** (1) Restated fundamentals overwrite originally reported values; the model must use as-first-reported figures. (2) Filing dates vary; using fiscal period end instead of filing date is look-ahead. (3) Forward estimates used as inputs carry consensus backfill risk.

**Signal concept.** Residual from a cross-sectional fit of an enterprise-value multiple on growth, margin and reinvestment variables within each sub-industry and date, using only data available at that date.

**Baselines.** book-to-market and earnings yield; intangible-adjusted value (TE-E06); profitability (TE-E04)

**Confounders.** quality and profitability exposure; distress risk in firms that look cheap for good reason; accounting differences in stock-based compensation and capitalised costs

**Costs (low).** Slow signal with low turnover; costs are dominated by borrow on expensive short-leg names.

**Validation requirements.** (1) All fundamentals as first reported and lagged to filing date. (2) Fit coefficients re-estimated each date from that date's cross-section only. (3) Show incremental content over standard value, profitability and growth factors.

**Failure conditions.** (1) Residual is explained by standard value and quality factors. (2) Residual persists for years without converging (structural mispricing or missing variable).

**Kill condition.** The valuation residual does not predict hedged returns once value, profitability and growth exposures are controlled.

**Tail exposure.** Prolonged narrative-driven rallies push expensive names further from fundamentals and can impose long drawdowns on the short leg.

**Grouped variants.** Choice of multiple (EV to sales, EV to gross profit, EV to forward earnings), explanatory variable set, sub-industry versus custom peers, winsorisation choices.

### TE-A05 Customer-to-supplier price lead-lag

*A_relative_value, relative_value, mechanism class informational, sign +, horizon 5-40 trading days, implementation high; data tier needs_unavailable_history (blocked by relationship_graph); shared family SF-SUPPLY-CHAIN.*

**Rationale.** Investors with limited attention price news about a firm's major customers into the customer's stock quickly but into its suppliers' stocks slowly. In technology, supplier revenue is often concentrated in a few large customers, so the customers' recent returns should predict suppliers' subsequent hedged returns.

**Counterparty.** Investors who follow suppliers in isolation and do not map news about large customers into the supplier's revenue outlook.

**Universe.** US-listed technology suppliers with disclosed major customers, both legs passing PIT liquidity filters

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, relationship_graph, customer_concentration, regulatory_filings_text

**Availability risks.** (1) Relationship graphs assembled today encode relationships discovered ex post; links must be dated to their first public disclosure. (2) Major-customer disclosures are often anonymous or appear only in annual filings, so the graph is sparse and lagged. (3) Vendor relationship databases may backfill links, inflating historical coverage.

**Signal concept.** Weighted average recent return of a supplier's disclosed customers (weights by disclosed revenue share when known), minus the supplier's own return or its sub-industry return, using only links disclosed before formation.

**Baselines.** own-stock and industry momentum; industry lead-lag (large caps lead small caps); market beta

**Confounders.** industry momentum (TE-E02); size-based lead-lag; common exposure to the same sub-industry shock

**Costs (medium).** Monthly or faster rebalancing on smaller supplier names with moderate turnover and possible borrow constraints.

**Validation requirements.** (1) Every link dated by its first public disclosure; test with links available at formation only. (2) Control for size lead-lag and industry momentum. (3) Placebo test with randomly reassigned same-industry customers.

**Failure conditions.** (1) Effect disappears when links are restricted to those disclosed before formation. (2) Placebo customers predict as well as true customers.

**Kill condition.** Customer returns do not predict supplier hedged returns beyond industry and size lead-lag using as-disclosed links.

**Tail exposure.** Loss of a major customer produces large single-name gaps that the signal cannot anticipate.

**Grouped variants.** Weighting by revenue share or equal weighting, customer-return window, inclusion of second-order links, relative to sub-industry or to market.

### TE-A06 Parent-subsidiary and carve-out stub mispricing

*A_relative_value, relative_value, mechanism class structural, sign +, horizon 60-500 trading days, implementation high; data tier needs_unavailable_history (blocked by borrow_availability).*

**Rationale.** When a listed technology parent holds a large stake in a listed subsidiary or a recent carve-out, the market value of the stake can exceed or approach the parent's own value, implying a stub value that is implausibly low or negative. Short-sale constraints on the subsidiary and benchmark frictions slow convergence, but corporate actions and the eventual distribution of shares tend to force it.

**Counterparty.** Enthusiastic buyers of the subsidiary who cannot be arbitraged against because its shares are hard to borrow, and parent holders who ignore the embedded stake.

**Universe.** US-listed technology parents with a listed subsidiary or recent carve-out where the stake is material relative to the parent's market value

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit, regulatory_filings_text, borrow_availability

**Availability risks.** (1) Stake sizes change; ownership must be taken from filings dated before formation. (2) Episodes are identified by searching history, which risks selecting famous cases known to have converged. (3) Few episodes; each is a distinct situation with idiosyncratic outcomes.

**Signal concept.** Implied stub value (parent market value minus market value of listed stakes, adjusted for net debt and tax on gains), relative to the parent's own operating fundamentals.

**Baselines.** parent stand-alone value factor exposure; subsidiary short-term reversal; market beta of the combined position

**Confounders.** tax leakage on stake disposal; governance or control discounts; lock-up expiries at carve-outs

**Costs (medium).** Low turnover but the subsidiary short leg is often hard to borrow and expensive for long periods.

**Validation requirements.** (1) Episode list built by a rule applied to PIT data, not by recall of known cases. (2) Event-time analysis with small-sample inference (bootstrap or permutation over episodes). (3) Report the share of episodes with infeasible borrow.

**Failure conditions.** (1) Most episodes are not executable because the subsidiary cannot be borrowed. (2) Stubs remain negative until resolution with no convergence premium after costs.

**Kill condition.** Rule-identified stub episodes show no hedged convergence return after borrow costs.

**Tail exposure.** The stub can widen further in speculative manias, forcing the short leg out before convergence.

**Grouped variants.** Listed subsidiaries, carve-outs pending spin-off, tracking-stock structures; tax-adjusted versus unadjusted stubs; entry thresholds.

### TE-A07 Residual (idiosyncratic) momentum

*A_relative_value, relative_value, mechanism class behavioural, sign +, horizon 20-120 trading days, implementation medium; data tier prices_and_edgar; shared family SF-MOMENTUM.*

**Rationale.** Total-return momentum mixes firm-specific underreaction with time-varying factor exposure, which causes its crashes. Momentum in returns after removing market, industry and style factors isolates gradual incorporation of firm-specific news and should be steadier. Technology stocks carry large factor loadings, so the separation should matter more here than elsewhere.

**Counterparty.** Investors anchored on prior valuations who underreact to firm-specific news, and contrarian rebalancers.

**Universe.** US-listed technology companies passing PIT liquidity filters

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, fundamentals_pit

**Availability risks.** (1) Factor loadings estimated on the full sample leak future information; estimate them on rolling past windows. (2) Survivorship in the universe inflates momentum profits; delisting returns are required.

**Signal concept.** Cumulative residual return over an intermediate look-back from a rolling factor model (market, industry, size, value, profitability), skipping the most recent month, scaled by residual volatility.

**Baselines.** 12-1 price momentum (TE-E01); sub-industry-neutral 12-1 momentum; industry momentum (TE-E02)

**Confounders.** total-return momentum; earnings drift (TE-C01); choice of factor model

**Costs (medium).** Monthly rebalancing with turnover similar to standard momentum; both legs mostly liquid.

**Validation requirements.** (1) Factor model fitted only on data before each formation date. (2) Show incremental content over 12-1 momentum and over sub-industry-neutral momentum. (3) Compare drawdowns in known momentum-crash regimes without tuning to them.

**Failure conditions.** (1) No improvement over sub-industry-neutral momentum. (2) Results depend on one specific factor-model choice.

**Kill condition.** Residual momentum does not beat sub-industry-neutral 12-1 momentum on held-out windows after costs.

**Tail exposure.** Sharp momentum reversals after market rebounds and growth-to-value rotations still hit the strategy, though less than total-return momentum if the mechanism holds.

**Grouped variants.** Sub-industry-demeaned momentum, factor-model residual momentum, look-back and skip lengths, volatility scaling, factor set.

### TE-A08 Index reconstitution flow in technology stocks

*A_relative_value, relative_value, mechanism class flow, sign +, horizon 5-30 trading days, implementation high; data tier prices_and_edgar.*

**Rationale.** Index funds must buy additions and sell deletions at or near the effective date regardless of price. Technology stocks migrate across size and style indices often because of large price moves, so predictable reconstitution demand is frequent. Stocks predicted to be added should outperform peers into the effective date and partly reverse after it.

**Counterparty.** Passive funds that trade at the close of the effective date to minimise tracking error, and accept the price impact as the cost of tracking.

**Universe.** US-listed technology companies near size or style index boundaries at PIT reconstitution dates

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, index_membership, fundamentals_pit

**Availability risks.** (1) Index membership histories must include announcement dates, not only effective dates. (2) Predicting membership with today's methodology rules ignores past rule changes. (3) Free-float data used for eligibility may be revised after the fact.

**Signal concept.** Predicted probability of addition or deletion from published index rules and PIT market capitalisation, combined with the expected passive demand relative to average volume.

**Baselines.** size and liquidity; short-term reversal; 12-1 momentum (additions tend to be recent winners)

**Confounders.** momentum of recent winners crossing size thresholds; pre-positioning by other arbitrageurs, which changes the timing of the effect

**Costs (medium).** Event-driven turnover around a few dates a year; impact costs are high near effective dates when liquidity is contested.

**Validation requirements.** (1) Membership predicted with the methodology in force at each date. (2) Separate pre-announcement, announcement-to-effective and post-effective windows. (3) Test for decay over time as the trade became crowded.

**Failure conditions.** (1) Pre-positioning removes the return before it is executable. (2) Effect is explained by momentum of the added names.

**Kill condition.** Predicted reconstitution demand does not produce hedged returns after costs in the pre-effective window.

**Tail exposure.** Crowded pre-positioning can unwind violently if a predicted addition does not occur.

**Grouped variants.** Size-index migrations, style-index migrations, thematic technology index rebalances; entry timing relative to announcement; exit before or after the effective date.

### TE-B01 Growth-stage trajectory analogues

*B_analogues, directional, mechanism class behavioural, sign +, horizon 120-500 trading days, implementation high; data tier prices_and_edgar; shared family SF-ANALOGUES.*

**Rationale.** Investors tend to extrapolate a firm's recent growth rather than use the historical distribution of outcomes for firms at the same stage. Matching a firm's revenue growth, margin and reinvestment path to past firms at the same stage gives an outside-view forecast of future fundamentals. Where the analogue forecast is better than the market-implied path, returns should be higher.

**Counterparty.** Extrapolating investors who price recent growth as if it were persistent, without reference to base rates of similar firms.

**Universe.** US-listed technology companies with at least several years of PIT fundamentals history

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit, segment_reporting, classification_history

**Availability risks.** (1) The analogue library must contain only firms whose subsequent path was already observable at formation. (2) Restated and reclassified fundamentals alter historical trajectories; use as-first-reported values. (3) Survivorship in the analogue library (failed firms missing) biases forecasts upward. (4) Matching choices (features, distance, number of neighbours) create a very large hidden search space.

**Signal concept.** Difference between the analogue-implied forward fundamental path (from nearest past trajectories) and a market-implied or consensus path, ranked within the universe.

**Baselines.** consensus growth forecasts; simple mean-reversion of growth towards sub-industry median; value and profitability factors

**Confounders.** generic growth mean reversion; value exposure; sub-industry cycles

**Costs (low).** Slow, low-turnover signal; costs matter little compared with research and leakage risk.

**Validation requirements.** (1) Analogue library built strictly from outcomes known before formation (expanding window). (2) Matching specification frozen before evaluation; every attempted specification logged. (3) Must beat a simple growth mean-reversion baseline, not only zero. (4) Strong multiple-testing adjustment for the matching search space.

**Failure conditions.** (1) No improvement over simple growth mean reversion. (2) Results change sign across reasonable matching specifications.

**Kill condition.** Analogue-implied forecasts add no return prediction beyond simple growth mean reversion with a frozen matching specification.

**Tail exposure.** Structural breaks (new platform eras) make historical analogues systematically wrong at the same time for many firms.

**Grouped variants.** Feature sets (growth, margins, reinvestment, age since listing), distance metrics, number of neighbours, horizon of the analogue path, post-listing lifecycle variants.

### TE-B02 Implied growth versus historical base rates

*B_analogues, relative_value, mechanism class behavioural, sign -, horizon 120-500 trading days, implementation medium; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-VALUATION.*

**Rationale.** Valuations imply a path of future growth. Historical base rates show how rarely firms of a given size sustain very high growth for many years. Firms whose implied growth requires an outcome that is rare in the base-rate distribution should, on average, disappoint and underperform.

**Counterparty.** Investors who overweight vivid success stories and neglect the base rate of growth decay.

**Universe.** US-listed technology companies with positive revenue and analyst coverage

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit, analyst_estimates_pit

**Availability risks.** (1) Base-rate distributions must be computed from data available at formation, including failed firms. (2) Implied-growth calculation needs discount-rate assumptions that can be tuned after the fact. (3) Consensus inputs carry backfill risk.

**Signal concept.** Percentile of the market-implied multi-year revenue growth within the PIT historical distribution of realised growth for firms of similar size and sub-industry.

**Baselines.** book-to-market and sales-to-price; growth-adjusted value; market beta

**Confounders.** value factor; duration exposure (TE-F01); quality

**Costs (low).** Low turnover; short leg sits in large, liquid expensive names but borrow can be costly in speculative ones.

**Validation requirements.** (1) Base rates rebuilt at each formation date from past data only. (2) Implied-growth model and discount-rate rule frozen before evaluation. (3) Show content beyond simple value measures.

**Failure conditions.** (1) Signal is a relabelled value factor. (2) Base-rate percentile is unstable to reasonable discount-rate assumptions.

**Kill condition.** Base-rate-implausible implied growth does not predict underperformance beyond value and duration.

**Tail exposure.** Speculative growth rallies inflict long drawdowns on the short side.

**Grouped variants.** Revenue versus earnings growth, implied-growth horizon, size and sub-industry conditioning of the reference class, discount-rate rule.

### TE-B03 Inventory and margin cycle analogues

*B_analogues, relative_value, mechanism class behavioural, sign -, horizon 60-250 trading days, implementation medium; data tier needs_unavailable_history (blocked by semiconductor_supply_chain); shared family SF-SEMI-CYCLE.*

**Rationale.** Hardware and semiconductor firms go through inventory build-ups that precede margin compression. Investors focusing on current revenue growth tend to miss the pattern. A firm whose inventory, receivables and gross-margin trajectory resembles past pre-downturn trajectories should underperform peers.

**Counterparty.** Investors who extrapolate current revenue momentum and do not read balance-sheet build-ups as a leading signal of margin pressure.

**Universe.** US-listed semiconductor, hardware and component companies with PIT quarterly balance-sheet data

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit, classification_history, semiconductor_supply_chain

**Availability risks.** (1) Quarterly balance-sheet items are restated; use as-first-reported values lagged to filing date. (2) Downturn episodes are labelled with hindsight; labels must be defined by a rule applied to PIT data. (3) Few independent cycles in history, so effective sample size is small.

**Signal concept.** Similarity of a firm's recent inventory-to-sales, receivables-to-sales and gross-margin path to rule-labelled pre-downturn paths, relative to sub-industry peers.

**Baselines.** change in inventory-to-sales (simple accrual signal); accruals factor; industry momentum

**Confounders.** accruals anomaly; semiconductor cycle exposure (TE-F04)

**Costs (low).** Quarterly signal with low turnover; short leg in mid- and large-cap hardware names.

**Validation requirements.** (1) Downturn labels from a frozen rule, not from judgement. (2) Must beat the simple change-in-inventory signal. (3) Inference that accounts for the small number of independent cycles.

**Failure conditions.** (1) No incremental content over the simple inventory or accrual signal. (2) Results driven by a single cycle.

**Kill condition.** Analogue similarity adds nothing to the simple change-in-inventory signal across more than one cycle.

**Tail exposure.** Supply shortages invert the usual inventory signal and can create sudden, sector-wide losses.

**Grouped variants.** Feature set, similarity metric, labelling rule for downturns, sub-industry scope.

### TE-B04 Business-model transition analogues

*B_analogues, directional, mechanism class behavioural, sign +, horizon 120-500 trading days, implementation high; data tier needs_unavailable_history (blocked by earnings_call_text); shared family SF-ANALOGUES.*

**Rationale.** Software and hardware firms moving from licences or one-off sales to subscriptions show a predictable dip in reported revenue and margins before recurring revenue builds. Investors focused on reported figures may over-penalise the dip. Firms whose transition path matches past successful-transition analogues should outperform once recurring revenue becomes visible.

**Counterparty.** Investors who mechanically weight reported growth and margins and sell during the transition dip.

**Universe.** US-listed software and hardware companies with disclosed recurring-revenue or subscription segments

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit, segment_reporting, earnings_call_text

**Availability risks.** (1) Transition start dates are identified with hindsight unless taken from dated disclosures. (2) Segment definitions change; historical segment data may be restated. (3) Very few episodes; famous successes dominate memory and risk selection bias.

**Signal concept.** Position of a transitioning firm on the typical transition path (recurring share of revenue, reported margin dip) compared with analogues identified from earlier dated disclosures.

**Baselines.** growth and profitability factors; revenue surprise drift (TE-C02)

**Confounders.** sector-wide re-rating of recurring revenue models; general growth-to-value rotations

**Costs (low).** Very low turnover; small number of positions makes idiosyncratic risk the main cost.

**Validation requirements.** (1) Episodes identified by a rule on dated disclosures, including failed transitions. (2) Event-time inference that respects the small number of episodes. (3) Every attempted matching rule logged as a variant.

**Failure conditions.** (1) Rule-identified episodes show no drift relative to peers. (2) Too few episodes to distinguish from noise.

**Kill condition.** Rule-identified transition episodes show no hedged outperformance relative to non-transitioning peers.

**Tail exposure.** Failed transitions lead to large permanent losses; the strategy is long a few concentrated situations.

**Grouped variants.** Subscription transitions, on-premise to cloud migrations, hardware-to-services shifts; stage at entry; analogue matching rule.

### TE-B05 Thematic episode analogues

*B_analogues, directional, mechanism class behavioural, sign -, horizon 60-500 trading days, implementation high; data tier prices_and_edgar_text; shared family SF-ANALOGUES.*

**Rationale.** Technology themes go through episodes of rapid valuation expansion, heavy issuance and rising valuation dispersion, sometimes followed by sharp reversals. If a current theme's valuation, issuance and breadth pattern resembles past theme peaks, subsequent returns of the theme's constituents may be lower.

**Counterparty.** Late-cycle thematic buyers and issuers' early holders, who sell into demand at elevated prices.

**Universe.** Technology stocks grouped into themes by a PIT rule (classification or text-based exposure)

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, fundamentals_pit, regulatory_filings_text

**Availability risks.** (1) Themes are defined with hindsight; theme membership must come from dated text or classification. (2) Very few independent past episodes, so analogues are fitted to a handful of famous cases. (3) Issuance data must be dated to the offering date, not the reporting date.

**Signal concept.** Similarity of a theme's current valuation level, valuation dispersion, issuance and breadth pattern to rule-labelled past theme peaks; used to underweight the theme within a long-biased portfolio.

**Baselines.** industry momentum (TE-E02); aggregate valuation level of the sector; net issuance factor (TE-E05)

**Confounders.** momentum and its crash regimes; discount-rate shocks (TE-F01)

**Costs (low).** Low turnover at theme level; implementation through underweighting rather than shorting keeps costs low.

**Validation requirements.** (1) Theme membership and peak labels from frozen rules on PIT data. (2) Inference treats each episode as one observation; report the episode count. (3) Pre-specify the similarity metric; log every attempt.

**Failure conditions.** (1) Fewer independent episodes than needed for any inference. (2) Signal fires in many non-peak periods with no subsequent underperformance.

**Kill condition.** Peak similarity does not separate subsequent theme underperformance from non-peak periods across the available independent episodes.

**Tail exposure.** Underweighting a theme that keeps rising produces long, painful tracking error in speculative episodes.

**Grouped variants.** Theme definition (classification or text), choice of similarity features, analogue weighting, look-back.

### TE-C01 Post-earnings-announcement drift

*C_earnings, relative_value, mechanism class behavioural, sign +, horizon 5-60 trading days, implementation low; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-EARNINGS-SURPRISE.*

**Rationale.** Prices underreact to earnings news, so stocks with positive surprises continue to drift up and those with negative surprises drift down for weeks after the announcement. Limited attention and anchoring are the usual explanations; technology stocks have heavy announcement-day volume but also many small-cap names with thin coverage.

**Counterparty.** Investors who anchor on prior expectations and trade against the announcement move, and those with limited attention who do not process the news.

**Universe.** US-listed technology companies with dated earnings announcements, passing PIT liquidity filters

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, earnings_events, fundamentals_pit, analyst_estimates_pit

**Availability risks.** (1) Announcement timestamps must distinguish before-open and after-close releases. (2) Consensus estimates used for surprises are subject to backfill; time-series surprises avoid this but are noisier. (3) Restated earnings must not replace the originally announced figure.

**Signal concept.** Standardised unexpected earnings (versus consensus or a seasonal random walk) and announcement-window abnormal return, measured from the first tradable session after the release.

**Baselines.** market beta and sub-industry exposure; price momentum; announcement-window return alone

**Confounders.** revenue surprise (TE-C02); guidance (TE-C03); momentum

**Costs (medium).** Event-driven turnover concentrated in earnings seasons; small-cap names carry high spreads.

**Validation requirements.** (1) Entry no earlier than the first full session after the release timestamp. (2) Results split by size and coverage, since drift is known to be concentrated in small names. (3) Check decay over time given the anomaly's publicity.

**Failure conditions.** (1) Drift confined to names too small or illiquid to trade. (2) No drift beyond what momentum explains in the technology universe.

**Kill condition.** Earnings surprises do not predict hedged drift after costs in the tradable part of the universe.

**Tail exposure.** Crowded event-driven positioning can reverse quickly in market-wide deleveraging.

**Grouped variants.** Consensus-based versus time-series surprise, announcement-return surprise, scaling choices, holding window, size filters.

### TE-C02 Revenue surprise in technology firms

*C_earnings, directional, mechanism class informational, sign +, horizon 5-60 trading days, implementation low; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-EARNINGS-SURPRISE.*

**Rationale.** For growth-oriented technology firms, revenue is harder to manage than earnings and carries more information about demand. Investors focus on headline earnings and may underreact to the revenue component. Revenue surprises, especially when they diverge from earnings surprises, should predict subsequent returns.

**Counterparty.** Investors and screens keyed to headline earnings who underweight revenue-quality information.

**Universe.** US-listed technology companies with revenue consensus and dated announcements

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, earnings_events, analyst_estimates_pit, fundamentals_pit

**Availability risks.** (1) Revenue consensus histories are thinner and more prone to backfill than earnings consensus. (2) Revenue recognition standard changes alter comparability across years.

**Signal concept.** Standardised revenue surprise versus consensus, and its divergence from the earnings surprise, measured at the announcement.

**Baselines.** earnings surprise drift (TE-C01); announcement-window return

**Confounders.** earnings surprise; guidance changes released with results

**Costs (medium).** Same turnover pattern as earnings drift; long-only implementation avoids borrow but carries market risk.

**Validation requirements.** (1) Show incremental content over earnings surprise in the same regression. (2) Control for revenue-recognition regime changes.

**Failure conditions.** (1) Revenue surprise adds nothing to earnings surprise. (2) Effect exists only where consensus coverage is backfilled.

**Kill condition.** Revenue surprise has no incremental predictive content over earnings surprise on as-of consensus data.

**Tail exposure.** Same crowded-unwind exposure as other earnings-drift strategies.

**Grouped variants.** Revenue-only surprise, revenue minus earnings surprise, segment-level revenue surprise, scaling choices.

### TE-C03 Management guidance surprise

*C_earnings, directional, mechanism class informational, sign +, horizon 5-60 trading days, implementation medium; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-EARNINGS-SURPRISE.*

**Rationale.** Management forward guidance conveys private information about pipeline and bookings. Guidance raised or lowered relative to consensus is news that analysts take time to absorb into their own forecasts, so prices may adjust gradually. In technology, guidance often matters more than the reported quarter.

**Counterparty.** Investors who wait for analyst revisions before acting and those focused on the reported quarter.

**Universe.** US-listed technology companies that issue quantitative guidance

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, guidance_events, analyst_estimates_pit, earnings_events

**Availability risks.** (1) Guidance databases record ranges and midpoints with inconsistent timestamps. (2) Firms stop or start guiding; selection into guidance is itself informative. (3) Consensus at the time of guidance must be captured as-of, not from later snapshots.

**Signal concept.** Guidance midpoint minus prevailing consensus, scaled, measured at the release timestamp; separately for revenue and earnings guidance.

**Baselines.** earnings surprise drift (TE-C01); revenue surprise (TE-C02)

**Confounders.** reported-quarter surprise released at the same time; selection of firms that guide

**Costs (medium).** Event-driven turnover around earnings seasons with moderate spreads.

**Validation requirements.** (1) Guidance and consensus aligned at the same timestamp. (2) Show incremental content over the same-day earnings and revenue surprise. (3) Treat firms that stop guiding as a separate observable event.

**Failure conditions.** (1) Guidance surprise is fully absorbed on announcement day. (2) Effect disappears once same-day surprises are controlled.

**Kill condition.** Guidance surprise does not predict drift beyond same-day earnings and revenue surprises.

**Tail exposure.** Guidance cuts cluster in downturns, producing correlated gaps across the portfolio.

**Grouped variants.** Revenue versus earnings guidance, midpoint versus range-width signals, initiations and withdrawals of guidance.

### TE-C04 Analyst revision breadth

*C_earnings, directional, mechanism class informational, sign +, horizon 20-60 trading days, implementation low; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-REVISIONS.*

**Rationale.** The share of analysts revising up versus down captures how widely new information has spread among forecasters, independent of the size of any one revision. Broad, one-sided revisions indicate a shift in fundamentals that prices may not yet fully reflect.

**Counterparty.** Investors who react to the consensus level rather than to the direction and breadth of individual revisions.

**Universe.** US-listed technology companies with several covering analysts at formation

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, analyst_estimates_pit, earnings_events

**Availability risks.** (1) Individual-analyst revision histories are the most backfill-prone estimate data. (2) Stale estimates inflate the denominator; vendors differ on stale-estimate filters.

**Signal concept.** Net share of upward minus downward revisions to forward estimates over a recent window, among active estimates.

**Baselines.** peer-relative revisions (TE-A03); price momentum

**Confounders.** revision magnitude; earnings drift around announcements

**Costs (medium).** Monthly rebalancing with moderate turnover in covered, mostly liquid names.

**Validation requirements.** (1) Individual estimates captured as of each formation date with a stale-estimate rule fixed in advance. (2) Show incremental content over revision magnitude (TE-A03) and momentum.

**Failure conditions.** (1) Breadth is redundant with revision magnitude. (2) Results depend on stale-estimate filtering choices.

**Kill condition.** Revision breadth adds nothing beyond revision magnitude and price momentum.

**Tail exposure.** Shares the crowding and rotation risk of revision-momentum strategies.

**Grouped variants.** Earnings versus revenue breadth, window length, fiscal-year versus forward-twelve-month estimates, stale-estimate rules.

### TE-C05 Analyst disagreement under short-sale constraints

*C_earnings, relative_value, mechanism class behavioural, sign -, horizon 20-120 trading days, implementation low; data tier needs_unavailable_history (blocked by analyst_estimates_pit, borrow_availability); shared family SF-SHORT-CONSTRAINTS.*

**Rationale.** When opinions diverge and short selling is costly, prices reflect optimists' valuations. High dispersion of analyst forecasts is a proxy for divergence of opinion and should precede lower returns as uncertainty resolves. Technology firms with uncertain product outcomes often show wide dispersion.

**Counterparty.** Optimistic investors whose views set the price because pessimists face short-sale costs.

**Universe.** US-listed technology companies with at least a few covering analysts

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, analyst_estimates_pit, borrow_availability

**Availability risks.** (1) Dispersion needs individual estimates as of each date; backfill alters it. (2) Coverage thresholds change the sample composition over time.

**Signal concept.** Cross-analyst standard deviation of forward earnings forecasts scaled by price or by absolute mean, relative to sub-industry peers.

**Baselines.** idiosyncratic volatility; short-sale constraint signal (TE-A02); size

**Confounders.** idiosyncratic volatility; distress; small coverage counts

**Costs (medium).** Monthly rebalancing; the short leg is in high-uncertainty names that may be costly to borrow.

**Validation requirements.** (1) Dispersion computed from as-of individual estimates. (2) Control for idiosyncratic volatility and short interest. (3) Test whether the effect is stronger where borrow is costly, as the mechanism requires.

**Failure conditions.** (1) Effect explained by volatility or distress. (2) No interaction with borrow constraints.

**Kill condition.** Dispersion does not predict negative hedged returns after volatility controls, or the effect does not strengthen with borrow constraints.

**Tail exposure.** Short leg is exposed to squeezes in uncertain, story-driven names.

**Grouped variants.** Earnings versus revenue dispersion, scaling choice, horizon of the forecast, coverage threshold.

### TE-C06 Forward margin revisions

*C_earnings, directional, mechanism class informational, sign +, horizon 20-120 trading days, implementation medium; data tier needs_unavailable_history (blocked by analyst_estimates_pit); shared family SF-REVISIONS.*

**Rationale.** Technology firms have high operating leverage: small revenue changes produce large margin changes. Consensus revisions can be decomposed into revenue-driven and margin-driven parts. Investors may treat margin-driven upgrades as less durable than they are, so revisions to forward operating margin should predict returns beyond revenue revisions.

**Counterparty.** Investors who treat margin improvements as transitory and anchor valuation on revenue multiples.

**Universe.** US-listed technology companies with consensus for both revenue and operating income

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, analyst_estimates_pit, fundamentals_pit, earnings_events

**Availability risks.** (1) Operating-margin consensus is sparse historically and subject to definitional changes (adjusted versus reported). (2) Backfilled consensus can create spurious decompositions.

**Signal concept.** Change in consensus forward operating margin over a recent window, net of the part implied by revenue revisions and fixed-cost leverage.

**Baselines.** earnings revisions (TE-A03); profitability (TE-E04)

**Confounders.** earnings revisions; changes in adjusted-earnings definitions

**Costs (medium).** Monthly rebalancing; long-only ranking avoids borrow.

**Validation requirements.** (1) Margin consensus as-of, with a fixed definition across time. (2) Show incremental content over total earnings revisions.

**Failure conditions.** (1) Margin revisions are redundant with earnings revisions. (2) Historical coverage too sparse for inference.

**Kill condition.** Margin-driven revisions add no prediction beyond total earnings revisions.

**Tail exposure.** Margin expectations collapse together in demand downturns.

**Grouped variants.** Gross versus operating margin, adjusted versus reported basis, decomposition method, window length.

### TE-C07 Earnings-call language

*C_earnings, directional, mechanism class informational, sign +, horizon 5-60 trading days, implementation high; data tier needs_unavailable_history (blocked by earnings_call_text).*

**Rationale.** Management tone, specificity and evasiveness in the question-and-answer part of earnings calls carry information about future results that is not in the numbers. Processing long transcripts is costly, so the information may enter prices slowly.

**Counterparty.** Investors who trade only on quantitative releases and do not process call content.

**Universe.** US-listed technology companies with dated earnings-call transcripts

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, earnings_call_text, earnings_events

**Availability risks.** (1) Transcript availability timestamps are often later than the call and vary by provider. (2) Historical transcript coverage is incomplete and biased towards larger firms. (3) Language models trained on recent text embed knowledge of later outcomes; scoring must avoid models trained after formation.

**Signal concept.** Text-derived measures of tone, uncertainty and non-answer frequency, relative to the firm's own history and to peers, available only after the transcript timestamp.

**Baselines.** earnings surprise drift (TE-C01); guidance surprise (TE-C03)

**Confounders.** same-day quantitative surprises; industry-wide tone shifts

**Costs (medium).** Event-driven turnover in earnings seasons, similar to other earnings strategies.

**Validation requirements.** (1) Text scoring with dictionaries or models fixed before the evaluation window and not trained on later text. (2) Signal timed from the transcript's availability timestamp. (3) Show incremental content over quantitative surprises.

**Failure conditions.** (1) Tone is fully explained by same-day surprises. (2) Results depend on a text model that has seen the evaluation period.

**Kill condition.** Call-language measures add nothing beyond same-day earnings, revenue and guidance surprises.

**Tail exposure.** Moderate; mainly shares the crowding risk of earnings-event strategies.

**Grouped variants.** Dictionary versus model-based tone, prepared remarks versus Q&A, evasiveness measures, change versus level.

### TE-D01 Foundry and chipmaker capex diffusion to equipment suppliers

*D_diffusion, directional, mechanism class informational, sign +, horizon 60-250 trading days, implementation high; data tier needs_unavailable_history (blocked by relationship_graph, semiconductor_supply_chain); shared family SF-SUPPLY-CHAIN.*

**Rationale.** Capital-expenditure plans announced by chipmakers and foundries are orders for equipment and materials suppliers several quarters later. Investors in suppliers may not fully map customer capex guidance into supplier revenue paths, especially for smaller suppliers with concentrated customer bases.

**Counterparty.** Supplier investors who wait for supplier-reported orders rather than reading customers' capex disclosures.

**Universe.** US-listed semiconductor equipment and materials suppliers

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, semiconductor_supply_chain, relationship_graph, guidance_events, customer_concentration

**Availability risks.** (1) Supplier-customer links must be dated to first disclosure; vendor graphs encode ex-post discovery. (2) Capex guidance is announced in calls and filings with inconsistent timestamps. (3) Semiconductor supply-chain datasets have short, uneven history.

**Signal concept.** Exposure-weighted change in announced customer capex guidance mapped to each supplier through dated links, relative to the supplier's consensus revenue path.

**Baselines.** industry momentum (TE-E02); supplier's own revisions (TE-A03); semiconductor cycle indicators (TE-F04)

**Confounders.** semiconductor cycle; common price response of customers and suppliers on the same day

**Costs (low).** Quarterly signal in mostly liquid mid- and large-cap suppliers; low turnover.

**Validation requirements.** (1) All links and capex announcements dated as first public. (2) Show incremental content over supplier consensus revisions and industry momentum. (3) Inference that respects the few independent capex cycles.

**Failure conditions.** (1) Supplier prices react fully on the customer's announcement day. (2) Signal is redundant with the semiconductor cycle.

**Kill condition.** Customer capex changes do not predict supplier returns beyond supplier revisions and the cycle.

**Tail exposure.** Export controls or abrupt capex cancellations hit the whole supplier group at once.

**Grouped variants.** Capex measure (guidance, reported capex, equipment orders), link weights, lag structure, materials versus equipment sub-groups.

### TE-D02 Cloud and AI compute demand diffusion to infrastructure suppliers

*D_diffusion, directional, mechanism class informational, sign +, horizon 60-250 trading days, implementation high; data tier needs_unavailable_history (blocked by cloud_capex, developer_adoption, product_releases, relationship_graph); shared family SF-SUPPLY-CHAIN.*

**Rationale.** Hyperscale cloud operators and AI model providers buy accelerators, memory, networking, storage and servers. Their capex plans and adoption signals propagate to infrastructure suppliers over quarters. Investors may price the most visible suppliers quickly but second-tier component and networking suppliers slowly.

**Counterparty.** Investors who concentrate on the most visible beneficiaries and underweight less-followed second-tier suppliers exposed to the same demand.

**Universe.** US-listed accelerator, memory, networking, storage, server and interconnect suppliers

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, cloud_capex, relationship_graph, developer_adoption, product_releases, customer_concentration

**Availability risks.** (1) Supplier exposure to cloud and AI demand is mapped with hindsight unless taken from dated disclosures. (2) Developer-adoption and product-release data have short histories and unknown timestamping. (3) The AI demand episode is short and unique, so very few independent observations exist.

**Signal concept.** Exposure-weighted change in cloud capex guidance or AI adoption measures mapped to suppliers through dated links, relative to supplier consensus.

**Baselines.** industry momentum (TE-E02); supplier revisions (TE-A03); size

**Confounders.** single-theme momentum and crowding; discount-rate shocks (TE-F01)

**Costs (low).** Low turnover; long-only ranking but concentrated in a crowded theme.

**Validation requirements.** (1) Links dated as first disclosed; exposure weights from PIT segment or customer disclosures. (2) Results by sub-period; not dominated by a single demand episode. (3) Adoption data used only from the date the vendor began capturing it live.

**Failure conditions.** (1) Effect exists only in one recent episode. (2) Second-tier suppliers react as fast as first-tier.

**Kill condition.** Mapped compute demand changes do not predict supplier returns beyond momentum and revisions outside a single episode.

**Tail exposure.** Thematic crowding unwinds can cause large simultaneous drawdowns across all suppliers.

**Grouped variants.** Cloud capex versus AI adoption signals, accelerator versus memory versus networking sub-groups, link weighting, lag structure.

### TE-D03 Security-incident diffusion to cybersecurity vendors

*D_diffusion, directional, mechanism class informational, sign +, horizon 60-250 trading days, implementation high; data tier needs_unavailable_history (blocked by relationship_graph).*

**Rationale.** Disclosed security incidents and new disclosure rules in a customer industry raise security budgets in that industry with a lag. Vendors with revenue concentrated in affected industries should see higher demand, which investors may not map from incident news to vendor revenue.

**Counterparty.** Investors who treat security incidents as news about the victim, not as demand news for vendors.

**Universe.** US-listed cybersecurity software and services companies

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, regulatory_filings_text, segment_reporting, relationship_graph

**Availability risks.** (1) Incident disclosures before mandated reporting are inconsistent and dated unevenly. (2) Vendor exposure to customer industries is rarely disclosed and may be inferred ex post. (3) Small universe of listed security vendors with a short history.

**Signal concept.** Count or severity of dated incident disclosures in customer industries, weighted by each vendor's disclosed industry exposure.

**Baselines.** software sub-industry momentum; vendor revisions (TE-A03)

**Confounders.** general software spending cycle; regulatory announcements affecting all vendors

**Costs (low).** Low turnover in a small set of mostly liquid software names.

**Validation requirements.** (1) Incidents and exposure weights dated as first public. (2) Placebo using non-security software vendors.

**Failure conditions.** (1) Too few vendors or incidents for inference. (2) Placebo vendors respond equally.

**Kill condition.** Exposure-weighted incident signals do not predict vendor returns beyond software momentum.

**Tail exposure.** Sector-wide software derating hits all vendors regardless of demand.

**Grouped variants.** Incident counts versus severity, rule-change events, exposure weighting, lag.

### TE-D04 Customer-industry conditions and vertical software vendors

*D_diffusion, relative_value, mechanism class informational, sign +, horizon 20-120 trading days, implementation high; data tier needs_unavailable_history (blocked by relationship_graph).*

**Rationale.** Software vendors serving specific customer industries (vertical software) depend on those industries' budgets. Customer-industry earnings and returns lead vendor bookings with a lag. Investors who analyse vendors as generic software may underreact to customer-industry conditions.

**Counterparty.** Generalist software investors who do not track customer-industry fundamentals.

**Universe.** US-listed application software companies with identifiable customer-industry concentration

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, segment_reporting, customer_concentration, relationship_graph, fundamentals_pit

**Availability risks.** (1) Customer-industry exposures are often inferred from text or vendor data built after the fact. (2) Segment disclosures change definitions across years.

**Signal concept.** Exposure-weighted recent returns or earnings revisions of a vendor's customer industries, relative to the vendor's sub-industry peers.

**Baselines.** customer-to-supplier lead-lag (TE-A05); industry momentum

**Confounders.** broad economic cycle; software sector factor

**Costs (medium).** Monthly rebalancing in mid-cap software names; moderate borrow needs.

**Validation requirements.** (1) Exposures from dated disclosures only. (2) Show content beyond TE-A05 and industry momentum.

**Failure conditions.** (1) Redundant with customer-to-supplier lead-lag. (2) Exposure mapping too noisy to rank vendors.

**Kill condition.** Customer-industry signals do not predict vendor hedged returns beyond lead-lag and industry momentum.

**Tail exposure.** Sector-wide software rotations dominate idiosyncratic customer-industry effects.

**Grouped variants.** Return-based versus revision-based customer signals, exposure weighting, lag.

### TE-D05 Data-centre build-out diffusion to power and thermal suppliers

*D_diffusion, directional, mechanism class informational, sign +, horizon 60-250 trading days, implementation high; data tier needs_unavailable_history (blocked by cloud_capex, relationship_graph); shared family SF-SUPPLY-CHAIN.*

**Rationale.** Data-centre construction requires power distribution, cooling and electrical equipment, and grid interconnection is a binding constraint. Announced data-centre capacity and power-procurement filings lead supplier revenue. Investors focused on compute suppliers may underreact for power and thermal equipment suppliers within or adjacent to the technology sector.

**Counterparty.** Investors who classify these suppliers as industrials and do not connect them to data-centre demand.

**Universe.** US-listed technology-hardware and adjacent electrical and thermal equipment suppliers with disclosed data-centre exposure

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, cloud_capex, regulatory_filings_text, relationship_graph, macro_pit

**Availability risks.** (1) Data-centre exposure is identified with hindsight unless taken from dated disclosures. (2) Interconnection queue and procurement filings have uneven historical timestamps. (3) Very short history of the current build-out episode.

**Signal concept.** Exposure-weighted change in announced data-centre capacity or power procurement, mapped to suppliers by dated disclosures.

**Baselines.** cloud capex diffusion (TE-D02); industrial cycle (TE-F04)

**Confounders.** general industrial cycle; energy-price shocks (TE-F03)

**Costs (low).** Low turnover in mostly liquid names; classification boundary issues complicate universe definition.

**Validation requirements.** (1) Universe defined by a PIT rule, not by today's recognition of data-centre exposure. (2) Show content beyond cloud capex and industrial cycle.

**Failure conditions.** (1) Effect confined to one episode. (2) Redundant with cloud capex diffusion.

**Kill condition.** Data-centre power signals do not predict supplier returns beyond cloud capex and the industrial cycle.

**Tail exposure.** A slowdown in data-centre spending would hit all exposed suppliers simultaneously.

**Grouped variants.** Capacity announcements versus power procurement, supplier sub-groups, lag structure.

### TE-D06 End-device product cycles and component suppliers

*D_diffusion, relative_value, mechanism class informational, sign +, horizon 20-120 trading days, implementation high; data tier needs_unavailable_history (blocked by product_adoption, product_releases, relationship_graph); shared family SF-SUPPLY-CHAIN.*

**Rationale.** Launches and adoption of new end devices change demand for specific components (sensors, displays, radio-frequency parts, memory). Product-adoption signals reach component suppliers' revenue with a lag and component investors may not map device adoption to their holdings.

**Counterparty.** Component investors who wait for reported results rather than tracking end-device adoption.

**Universe.** US-listed electronic component and semiconductor suppliers to consumer and enterprise devices

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, product_releases, product_adoption, relationship_graph, customer_concentration

**Availability risks.** (1) Product-adoption data from third parties has unknown historical timestamping and survivorship. (2) Component content per device is often known only after teardown reports, later than launch. (3) Supplier links discovered ex post.

**Signal concept.** Adoption momentum of end devices, mapped to component suppliers by dated content and customer links, relative to sub-industry peers.

**Baselines.** customer-to-supplier lead-lag (TE-A05); industry momentum

**Confounders.** customer price lead-lag; semiconductor cycle

**Costs (medium).** Monthly rebalancing with moderate turnover; some small-cap suppliers have wide spreads.

**Validation requirements.** (1) Content and links dated to first public availability. (2) Show content beyond customer price lead-lag.

**Failure conditions.** (1) Redundant with customer return lead-lag. (2) Adoption data history too short.

**Kill condition.** Device adoption signals do not predict supplier hedged returns beyond customer lead-lag.

**Tail exposure.** Loss of a socket in a major device produces large idiosyncratic gaps.

**Grouped variants.** Adoption measures, component categories, link weights, lag.

### TE-E01 Price momentum within technology

*E_factor, directional, mechanism class behavioural, sign +, horizon 20-120 trading days, implementation low; data tier prices_and_edgar; shared family SF-MOMENTUM.*

**Rationale.** Stocks with high returns over the past year, skipping the most recent month, tend to continue outperforming over the following months, usually attributed to underreaction and later overreaction. This family is the reference point every other technology signal must beat, not a novel idea.

**Counterparty.** Investors who underreact to news and contrarian rebalancers who sell winners early.

**Universe.** US-listed technology companies passing PIT liquidity filters

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history

**Availability risks.** (1) Survivorship without delisting returns inflates momentum profits, especially among failed small-cap technology firms. (2) Corporate actions must be applied as known at the time.

**Signal concept.** Cumulative total return over an intermediate look-back, skipping the most recent month, ranked within the technology universe.

**Baselines.** market beta; equal-weighted technology universe

**Confounders.** industry momentum (TE-E02); growth-versus-value cycles

**Costs (medium).** Monthly turnover typical of momentum; long-only ranking avoids borrow.

**Validation requirements.** (1) Delisting returns included. (2) Results by sub-period, including known momentum-crash regimes, without tuning to them.

**Failure conditions.** (1) No outperformance within technology after costs.

**Kill condition.** Technology-universe momentum ranking does not beat the equal-weighted universe after costs.

**Tail exposure.** Momentum crashes after sharp market rebounds and growth-to-value rotations.

**Grouped variants.** Look-back and skip lengths, volatility scaling, weighting scheme.

### TE-E02 Technology sub-industry momentum

*E_factor, directional, mechanism class behavioural, sign +, horizon 20-120 trading days, implementation low; data tier prices_and_edgar; shared family SF-MOMENTUM.*

**Rationale.** Industry-wide news diffuses slowly across firms in a sub-industry, so sub-industries that have performed well continue to do so. This is a between-industry effect, distinct from firm-specific momentum.

**Counterparty.** Investors who analyse firms individually and miss the common sub-industry component of news.

**Universe.** US-listed technology companies grouped by PIT sub-industry

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history

**Availability risks.** (1) Sub-industry classification must be point in time; today's classification embeds later reclassifications. (2) Few sub-industries means few independent bets.

**Signal concept.** Past return of each sub-industry over an intermediate look-back, used to tilt holdings across sub-industries.

**Baselines.** price momentum (TE-E01); market beta

**Confounders.** firm-level momentum; macro exposures (TE-F01, TE-F04)

**Costs (low).** Low turnover at sub-industry level; liquid names.

**Validation requirements.** (1) PIT classification. (2) Inference that accounts for the small number of sub-industries.

**Failure conditions.** (1) Redundant with firm-level momentum. (2) Too few sub-industries for reliable inference.

**Kill condition.** Sub-industry momentum adds nothing to firm-level momentum within technology.

**Tail exposure.** Concentrated sub-industry bets suffer in sharp sector rotations.

**Grouped variants.** Look-back lengths, classification depth, weighting.

### TE-E03 Short-term reversal

*E_factor, relative_value, mechanism class flow, sign -, horizon 5-20 trading days, implementation medium; data tier prices_and_edgar; shared family SF-REVERSAL.*

**Rationale.** Stocks with extreme returns over the past week or month tend to partly reverse because those returns include temporary price pressure from liquidity demand. Liquidity providers are paid for absorbing it.

**Counterparty.** Investors demanding immediacy who pay a temporary price concession.

**Universe.** US-listed technology companies passing PIT liquidity filters

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, earnings_events

**Availability risks.** (1) Stale closing prices and bid-ask bounce create spurious reversal. (2) Survivorship and delisting returns matter for extreme losers.

**Signal concept.** Past-week or past-month return, ranked, excluding announcement-driven moves.

**Baselines.** market beta; industry exposure

**Confounders.** bid-ask bounce; peer-spread reversion (TE-A01)

**Costs (high).** Very high turnover; costs may consume most of the predicted return.

**Validation requirements.** (1) Skip one day between signal and entry. (2) Costs from realistic spread models by size.

**Failure conditions.** (1) Profits do not survive a one-day skip and costs.

**Kill condition.** Reversal returns do not survive a one-day implementation lag and realistic costs.

**Tail exposure.** Losses in trending markets and in liquidity crises.

**Grouped variants.** Weekly versus monthly reversal, industry-adjusted versus raw, exclusion of event days.

### TE-E04 Profitability and earnings quality

*E_factor, directional, mechanism class behavioural, sign +, horizon 60-250 trading days, implementation low; data tier prices_and_edgar.*

**Rationale.** More profitable firms with cash-backed earnings tend to earn higher subsequent returns than less profitable firms, which investors may undervalue relative to growth stories. In technology, profitability measures must deal with stock-based compensation and capitalised development costs.

**Counterparty.** Investors who favour growth narratives over current profitability.

**Universe.** US-listed technology companies with PIT fundamentals

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit

**Availability risks.** (1) Restatements overwrite originally reported fundamentals. (2) Filing-date lags must be respected.

**Signal concept.** Gross profit or cash-based operating profit scaled by assets, adjusted for stock-based compensation, with an accruals component.

**Baselines.** market beta; value factor

**Confounders.** value; size; stock-based compensation accounting

**Costs (low).** Low turnover; liquid names.

**Validation requirements.** (1) As-first-reported fundamentals with filing-date lag. (2) Compare with and without stock-based compensation adjustments, pre-specified.

**Failure conditions.** (1) No outperformance within technology.

**Kill condition.** Profitability ranking does not beat the technology universe after costs.

**Tail exposure.** Underperforms in speculative growth rallies.

**Grouped variants.** Gross versus operating profitability, accruals, stock-based compensation treatment, scaling.

### TE-E05 Investment, issuance and stock-compensation dilution

*E_factor, relative_value, mechanism class behavioural, sign -, horizon 60-250 trading days, implementation low; data tier prices_and_edgar.*

**Rationale.** Firms that grow assets quickly or issue equity (including through stock-based compensation) tend to underperform, consistent with managers timing issuance when shares are overvalued and investors underweighting dilution. Technology firms dilute heavily through compensation, which may be underweighted relative to headline issuance.

**Counterparty.** Investors who buy newly issued shares and ignore ongoing dilution.

**Universe.** US-listed technology companies with PIT fundamentals and share counts

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit

**Availability risks.** (1) Share counts must be as of filing dates; vendor histories may use later figures. (2) Restated asset values change historical growth.

**Signal concept.** Asset growth and net share issuance including dilution from compensation, relative to peers.

**Baselines.** investment factor; value factor

**Confounders.** value; profitability

**Costs (low).** Low turnover; short leg may include recently listed names with limited borrow.

**Validation requirements.** (1) Share counts and assets as first reported. (2) Show whether the compensation component adds beyond standard issuance.

**Failure conditions.** (1) Compensation dilution adds nothing to standard issuance and investment.

**Kill condition.** Dilution-inclusive issuance does not predict hedged returns beyond the standard investment factor.

**Tail exposure.** Short leg exposed to growth rallies in issuing firms.

**Grouped variants.** Asset growth, net issuance, compensation dilution, buyback adjustments.

### TE-E06 Intangible-adjusted value

*E_factor, directional, mechanism class risk_premium, sign +, horizon 120-500 trading days, implementation medium; data tier prices_and_edgar; shared family SF-VALUATION.*

**Rationale.** Book value understates the capital of technology firms because research and development and much of selling expense are expensed. Capitalising these expenditures gives a value measure that is more comparable across firms, so cheap firms on an intangible-adjusted basis may earn a value premium.

**Counterparty.** Investors who pay for growth without adjusting for the capital already embedded in the firm.

**Universe.** US-listed technology companies with PIT fundamentals

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit

**Availability risks.** (1) Capitalisation needs long expense histories; early-life firms have short histories. (2) Restatements affect the stock of intangibles.

**Signal concept.** Book value plus capitalised research and selling expenses (with depreciation), relative to market value; variants adjust for expected growth.

**Baselines.** book-to-market; earnings yield

**Confounders.** standard value factor; profitability; duration exposure (TE-F01)

**Costs (low).** Very low turnover; liquid names.

**Validation requirements.** (1) Capitalisation rates fixed in advance. (2) Show content beyond standard value factors.

**Failure conditions.** (1) Redundant with standard value.

**Kill condition.** Intangible-adjusted value adds nothing to standard value within technology.

**Tail exposure.** Long periods of underperformance during growth rallies.

**Grouped variants.** Capitalisation and depreciation rates, growth adjustments, value ratios.

### TE-E07 Cash runway and balance-sheet strength

*E_factor, directional, mechanism class behavioural, sign +, horizon 60-250 trading days, implementation low; data tier prices_and_edgar; shared family SF-FINANCING.*

**Rationale.** Cash-burning technology firms with short runway face dilution or distress, and investors may underweight these costs. Longer runway and stronger balance sheets should predict higher returns relative to firms that will need to raise capital soon.

**Counterparty.** Investors drawn to growth or lottery-like payoffs who underweight dilution and distress costs.

**Universe.** US-listed technology companies with PIT fundamentals

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fundamentals_pit

**Availability risks.** (1) Delisting returns essential; distressed firms often delist. (2) Cash burn measured from restated statements misleads.

**Signal concept.** Months of cash runway given recent operating and investing cash flows, combined with leverage and liquidity ratios.

**Baselines.** distress risk factor; profitability (TE-E04)

**Confounders.** profitability; size

**Costs (medium).** Low turnover, but weak-balance-sheet names are often small and illiquid.

**Validation requirements.** (1) Delisting returns included. (2) Content beyond profitability and size.

**Failure conditions.** (1) Redundant with profitability and size.

**Kill condition.** Runway does not predict returns beyond profitability, size and distress measures.

**Tail exposure.** Speculative rallies in cash-burning firms.

**Grouped variants.** Runway definitions, leverage ratios, distress measures.

### TE-F01 Discount-rate shocks and equity duration

*F_macro, relative_value, mechanism class behavioural, sign -, horizon 5-60 trading days, implementation medium; data tier prices_and_edgar.*

**Rationale.** Long-duration technology equities, whose cash flows lie far in the future, are more sensitive to real yields and policy-rate expectations. If benchmark-constrained investors adjust slowly, real-yield and policy-path shocks may be reflected gradually in the relative prices of long- versus short-duration firms.

**Counterparty.** Benchmark-constrained and slow-moving investors who rebalance duration exposure gradually.

**Universe.** US-listed technology companies sorted by an equity-duration proxy

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, macro_pit, fundamentals_pit

**Availability risks.** (1) Duration proxies built from forecast cash flows inherit consensus backfill. (2) Policy-expectation series must be taken as observed in markets at the time, not from revised data. (3) Few independent rate regimes; strong multiple-testing risk across macro conditioning variables.

**Signal concept.** Recent change in real yields or market-implied policy path, interacted with each firm's duration proxy.

**Optional data (variants only; not in the tier).** analyst_estimates_pit

**Baselines.** same-day response to rate changes; value and growth factors

**Confounders.** value factor; profitability

**Costs (medium).** Moderate turnover; both legs mostly liquid.

**Validation requirements.** (1) Macro data as observed at the time. (2) Distinguish predictive lag from contemporaneous response. (3) Inference that accounts for few independent rate regimes.

**Failure conditions.** (1) Response is entirely contemporaneous. (2) Effect confined to one rate regime.

**Kill condition.** Discount-rate shocks predict no subsequent relative return of long- versus short-duration technology stocks across regimes.

**Tail exposure.** Abrupt policy reversals produce large losses in duration-tilted books.

**Grouped variants.** Real-yield changes, policy-path surprises around scheduled announcements, duration proxies, look-back.

### TE-F02 Credit conditions and financing-dependent technology

*F_macro, relative_value, mechanism class risk_premium, sign -, horizon 20-120 trading days, implementation medium; data tier prices_and_edgar; shared family SF-FINANCING.*

**Rationale.** Unprofitable, cash-burning technology firms depend on equity and convertible issuance to fund operations. When credit spreads widen or lending standards tighten, their cost of external finance rises and the probability of dilutive or distressed raises increases. If investors price this funding channel slowly, financing-dependent firms should underperform self-funding peers after credit tightening.

**Counterparty.** Holders of speculative growth stocks who price product optionality but not refinancing risk, and who sell only once a dilutive raise is announced.

**Universe.** US-listed technology companies sorted by PIT external-financing dependence (cash burn relative to cash and market value)

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, macro_pit, fundamentals_pit

**Availability risks.** (1) Credit-spread series must be as observed at the time; lending-standards surveys must use first-release dates. (2) Financing dependence uses as-first-reported cash-flow statements lagged to filing date. (3) Few independent credit cycles, so macro conditioning invites overfitting. (4) Distressed firms delist often; delisting returns are essential.

**Signal concept.** Recent change in credit conditions (high-yield or convertible spreads, lending standards) interacted with each firm's financing-dependence proxy, used to tilt from dependent towards self-funding firms.

**Baselines.** profitability (TE-E04); cash runway (TE-E07), unconditional; market beta

**Confounders.** discount-rate shocks (TE-F01), which move with credit; size and idiosyncratic volatility; unconditional distress effect

**Costs (medium).** Moderate turnover driven by macro changes; the short leg sits in speculative names with costly or unavailable borrow.

**Validation requirements.** (1) Macro inputs at first release or as observed in markets on the date. (2) Must show conditional content beyond the unconditional runway and profitability signals. (3) Control for contemporaneous real-yield changes. (4) Inference that treats each credit cycle as a small number of observations.

**Failure conditions.** (1) Conditioning on credit adds nothing to unconditional cash runway. (2) Effect is a relabelled discount-rate response. (3) Effect confined to one tightening episode.

**Kill condition.** Credit tightening does not predict relative underperformance of financing-dependent technology firms beyond discount-rate shocks and unconditional balance-sheet signals.

**Tail exposure.** Liquidity-driven rallies in speculative names after policy easing can squeeze the short leg hard.

**Grouped variants.** Credit measure (high-yield spreads, convertible spreads, lending standards), financing-dependence proxy, look-back of the credit change.

### TE-F03 Energy costs and data-centre-intensive firms

*F_macro, relative_value, mechanism class structural, sign -, horizon 20-120 trading days, implementation medium; data tier prices_and_edgar_text.*

**Rationale.** Electricity is a large operating cost for data-centre operators, hosting providers and semiconductor fabrication. Power contracts reprice with a lag, so an energy-price shock reaches reported margins one or more quarters later. If investors wait for reported margins, energy-intensive technology firms should underperform less energy-intensive peers after energy-price increases.

**Counterparty.** Investors who model technology firms on revenue growth and treat energy as a minor input, updating only when margin pressure is reported.

**Universe.** US-listed technology companies sorted by PIT energy intensity (data-centre operators, hosting, fabs versus asset-light software)

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, macro_pit, fundamentals_pit, segment_reporting, regulatory_filings_text

**Availability risks.** (1) Energy intensity is estimated from disclosures with lags and changing definitions; today's estimates embed later knowledge. (2) Regional power-price series may not have been available as of the date in the form used. (3) Contract structures (fixed versus floating power) are rarely disclosed, adding unobservable heterogeneity.

**Signal concept.** Recent change in relevant wholesale power or fuel prices interacted with each firm's dated energy-intensity proxy.

**Baselines.** market beta and sub-industry exposure; data-centre build-out diffusion (TE-D05)

**Confounders.** inflation and real-yield changes (TE-F01); industrial cycle; demand growth for data-centre capacity that offsets costs

**Costs (medium).** Moderate turnover in a narrow universe; some energy-intensive names are mid-cap with moderate borrow costs.

**Validation requirements.** (1) Energy intensity from dated disclosures with a frozen proxy rule. (2) Control for rates, inflation and the industrial cycle. (3) Test whether subsequent margin surprises move in the predicted direction, not only returns.

**Failure conditions.** (1) Energy intensity cannot be measured well enough to sort firms. (2) Returns respond only contemporaneously to energy prices. (3) Demand growth dominates cost effects throughout.

**Kill condition.** Energy-price shocks do not predict relative returns or margin surprises of energy-intensive technology firms after rate, inflation and cycle controls.

**Tail exposure.** Energy shocks coincide with broad market stress, so the relative position can be dominated by market-wide deleveraging.

**Grouped variants.** Energy series (power, gas), regional weighting, intensity proxies, look-back of the price change.

### TE-F04 Semiconductor and industrial cycle rotation

*F_macro, relative_value, mechanism class informational, sign +, horizon 60-250 trading days, implementation low; data tier needs_unavailable_history (blocked by semiconductor_supply_chain); shared family SF-SEMI-CYCLE.*

**Rationale.** Semiconductor demand is cyclical, driven by inventory swings at customers and tied to the broader industrial cycle, while software revenue is more recurring. Public leading indicators (manufacturing new orders, inventory-to-shipment ratios, semiconductor billings) turn before semiconductor earnings. If investors extrapolate recent sector earnings, improving indicators should predict semiconductors outperforming software.

**Counterparty.** Investors who extrapolate recent sector earnings trends and rotate only after reported results turn.

**Universe.** US-listed semiconductor and software companies, grouped by PIT classification

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, macro_pit, semiconductor_supply_chain, classification_history

**Availability risks.** (1) Industrial indicators are revised; first-release vintages and release dates are required. (2) Industry billings data are published with lags and occasionally restated. (3) Only a handful of independent semiconductor cycles exist in the available history.

**Signal concept.** Direction and change of a pre-specified composite of first-release cycle indicators, used to tilt between semiconductors and software.

**Baselines.** sub-industry momentum (TE-E02); semiconductor-versus-software price momentum

**Confounders.** discount-rate shocks (TE-F01), since software is longer duration; inventory cycle analogues (TE-B03)

**Costs (low).** Low turnover between two liquid groups; implementable with liquid baskets.

**Validation requirements.** (1) First-release vintages aligned to release dates. (2) Composite fixed before evaluation; every attempted indicator logged. (3) Inference that respects the small number of cycles (block bootstrap over cycles).

**Failure conditions.** (1) Indicators add nothing to relative price momentum. (2) Effect relies on revised rather than first-release data.

**Kill condition.** First-release cycle indicators do not predict the semiconductor-versus-software spread beyond its own momentum.

**Tail exposure.** Supply shocks and policy interventions (export controls, subsidies) can break the usual cycle relation abruptly.

**Grouped variants.** Indicator choice and composite weights, level versus change, look-back, tilt rule.

### TE-F05 Currency moves and international revenue exposure

*F_macro, relative_value, mechanism class informational, sign -, horizon 20-120 trading days, implementation medium; data tier needs_unavailable_history (blocked by analyst_estimates_pit).*

**Rationale.** Many technology firms earn a large share of revenue abroad. A stronger home currency reduces translated revenue and earnings, but analysts often update forecasts only when companies report or guide on the translation effect. If prices follow analysts, firms with high foreign revenue share should underperform domestically focused peers after currency appreciation.

**Counterparty.** Analysts and investors who wait for reported translation effects instead of applying observed currency moves to disclosed revenue mix.

**Universe.** US-listed technology companies with PIT geographic revenue disclosure

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, fx_rates, segment_reporting, analyst_estimates_pit, guidance_events

**Availability risks.** (1) Geographic segments are restated and defined inconsistently across firms and years. (2) Hedging programmes are disclosed unevenly, so true exposure is unobserved. (3) Consensus histories used to check the revision channel carry backfill risk.

**Signal concept.** Recent change in a revenue-weighted trade-weighted currency index interacted with each firm's dated foreign revenue share.

**Baselines.** market beta and size; peer-relative revisions (TE-A03)

**Confounders.** global growth shocks that move currencies and foreign demand together; hedging programmes; discount-rate shocks

**Costs (medium).** Moderate turnover in mostly liquid large and mid caps; borrow rarely binding.

**Validation requirements.** (1) Segment data as first reported and lagged to filing date. (2) Check the revision channel directly (subsequent consensus changes), not only returns. (3) Control for global growth proxies.

**Failure conditions.** (1) Currency effects are fully priced at the time of the move. (2) Exposure measurement too noisy to sort firms.

**Kill condition.** Currency moves interacted with foreign revenue share predict neither subsequent relative returns nor consensus revisions.

**Tail exposure.** Abrupt currency reversals and global growth shocks can swamp the translation effect.

**Grouped variants.** Currency basket weighting, exposure measure (revenue share, segment mix), look-back, revision-based versus return-based outcome.

### TE-F06 Volatility regimes and crowding unwinds

*F_macro, directional, mechanism class flow, sign -, horizon 5-60 trading days, implementation high; data tier needs_unavailable_history (blocked by options_implied_vol).*

**Rationale.** Technology stocks are frequently held in common by leveraged and risk-targeting investors. When market volatility rises, risk limits force these investors to cut exposure at the same time, so crowded names fall more than fundamentals justify. A crowding measure combined with rising implied volatility should predict underperformance of crowded names, which a long-only ranking can avoid.

**Counterparty.** Leveraged and volatility-targeting investors forced to deleverage, who sell regardless of price.

**Universe.** US-listed technology companies with PIT crowding proxies

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, options_implied_vol, short_interest, regulatory_filings_text

**Availability risks.** (1) Crowding measures from institutional holdings filings are published with long lags and must be dated to filing. (2) Single-name implied-volatility histories are vendor products with uneven coverage. (3) Crowding proxies are easy to tune after the fact around known unwind episodes.

**Signal concept.** Crowding score (holdings concentration among leveraged investors, short interest on the other side, return co-movement) interacted with the level or change of market implied volatility, used to underweight crowded names.

**Baselines.** price momentum (TE-E01); market beta; low-volatility tilt

**Confounders.** momentum crashes; market beta in high-volatility periods; discount-rate shocks

**Costs (medium).** Turnover rises exactly when spreads widen in volatile regimes, raising effective costs.

**Validation requirements.** (1) Holdings data lagged to publication dates. (2) Crowding proxy frozen before evaluation; episodes not hand-picked. (3) Show content beyond momentum and beta in high-volatility periods.

**Failure conditions.** (1) Redundant with momentum or beta. (2) Data lags make the signal arrive after the unwind.

**Kill condition.** Crowding interacted with volatility does not predict underperformance beyond momentum and beta.

**Tail exposure.** The signal may fail in the fastest unwinds if crowding data lag the event, leaving the portfolio fully exposed.

**Grouped variants.** Crowding measures (holdings, co-movement, short interest), volatility measures (level, change, term structure), regime definitions.
