# Non-technology equities: hypothesis-family catalogue

Generated from `manhattan/equities/catalogue_nontech.yaml` by `python -m manhattan.equities.catalogue render --programme non_technology_equities`. Do not edit by hand.

**Status: draft.** Every row is an untested hypothesis family. Nothing here is evidence, and no performance figure is stated. Rankings are qualitative 1–5 judgements made before any data were examined (5 is the favourable end); the priority order is a research-ordering device, not an expected return.

5 families: V_value 1, Q_quality 1, M_momentum 1, R_revisions 1, L_low_risk 1; relative value 0, directional 5.

**Multiple-testing denominator.** All 5 entries remain (no id removed or renumbered). Shared families group related entries; they never shrink the count of entries, and any attempt on any entry would count.

## Priority order

Lexicographic: affordable data tier first (prices and EDGAR, then EDGAR text, then unavailable history), then min(leakage safety, data feasibility), plausibility, distinctiveness, research cost, simplicity.

| # | id | family | shared family | data tier | approach | sign | horizon | costs | plaus. | data | cost | simpl. | distinct. | leak-safe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | NT-L01 | Low-risk anomaly across non-technology sectors |  | prices_and_edgar | directional | - | 1-12 months | low | 4 | 5 | 4 | 4 | 3 | 4 |
| 2 | NT-M01 | Price momentum across non-technology sectors |  | prices_and_edgar | directional | + | 1-6 months | medium | 4 | 5 | 5 | 5 | 2 | 4 |
| 3 | NT-V01 | Value across non-technology sectors |  | prices_and_edgar | directional | + | 1-12 months | low | 4 | 4 | 4 | 4 | 2 | 4 |
| 4 | NT-Q01 | Profitability and quality across non-technology sectors |  | prices_and_edgar | directional | + | 3-12 months | low | 4 | 4 | 4 | 3 | 2 | 4 |
| 5 | NT-R01 | Earnings revisions across non-technology sectors |  | needs_unavailable_history | directional | + | 1-3 months | medium | 4 | 1 | 2 | 3 | 2 | 2 |

## Shared hypothesis families

Entries that test overlapping mechanisms or near-identical signals. Their ids are kept (drafts). **This grouping is declared, not enforced:** nothing in freezing or attempt accounting reads it today. If frozen, each group should be registered as one Manhattan family (or linked by `parent_family`) and counted together for multiple testing; that enforcement is part of a future freeze (Ethan's).

| shared family | members |
|---|---|

## Data feasibility

Computed from each family's required data (`catalogue.data_tier`); unverified until the checks of DATA_ACQUISITION.md section 4 are done.

- **prices_and_edgar**: one survivorship-free price source, EDGAR structured data and free public series.
- **prices_and_edgar_text**: also EDGAR text parsed point in time.
- **needs_unavailable_history**: a history that is unaffordable or not verifiably point in time; forward collection or a data decision first.

Caveat: relative-value families in the first two tiers do not list borrow history among their data, but their short legs need it. Without an affordable borrow history they can be studied only with explicit, flagged borrow assumptions (a `costs.BorrowBook` with no record refuses the short), and any such result says so.

| tier | families | blocked by |
|---|---|---|
| prices_and_edgar | 4: NT-V01, NT-Q01, NT-M01, NT-L01 |  |
| prices_and_edgar_text | 0:  |  |
| needs_unavailable_history | 1: NT-R01 | analyst_estimates_pit |

## Families

### NT-V01 Value across non-technology sectors

*V_value, directional, mechanism class risk_premium, sign +, horizon 1-12 months, implementation medium; data tier prices_and_edgar.*

**Rationale.** Stocks priced low relative to fundamentals (earnings, book value, cash flow) carry distress and duration risk that investors require compensation for, and part of the discount reflects extrapolation of poor past growth that does not persist. Holders of cheap stocks are paid for bearing that risk and for providing capital to out-of-favour firms.

**Counterparty.** Investors who extrapolate recent growth, avoid recently distressed firms for career or mandate reasons, or pay for the comfort of glamour stocks.

**Universe.** US-listed non-technology common stocks, ADRs and REITs passing PIT liquidity, price and history screens, grouped by PIT sector; financials and real estate use sector-appropriate value measures

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, fundamentals_pit

**Availability risks.** (1) Fundamentals must be read as first published; restated values are a different vintage and are not used before their publication. (2) Book value for banks and insurers and net asset value for REITs are not comparable with industrial book value; a single ratio across sectors mixes accounting regimes. (3) Delisted value stocks (the distressed tail) must stay in the universe with delisting returns, or the premium is overstated.

**Signal concept.** Composite of earnings yield, cash-flow yield and book-to-price from the latest fundamentals usable at formation, ranked within PIT sector, using sector-appropriate measures for financials and real estate.

**Baselines.** market and sector exposure; size; the technology-track value family as a separate, parallel test

**Confounders.** sector concentration (value clusters in energy, financials and utilities); interest-rate exposure of long-duration growth versus value; leverage and distress

**Costs (low).** Monthly or slower rebalancing; small-capitalisation value names have wider spreads and must pass the liquidity screen at formation.

**Validation requirements.** (1) Formation uses only fundamentals usable at the formation close. (2) Report raw and sector-neutral expressions together as one family. (3) Leave-one-sector-out cross-sector validation. (4) Out-of-sample period fixed before any evaluation.

**Failure conditions.** (1) The effect disappears after sector neutralisation. (2) The effect is carried by one sector only. (3) The effect vanishes once delisting returns are included.

**Kill condition.** No positive sector-neutral excess return over the out-of-sample period after costs, with every sector reported, or the effect lives in one sector only.

**Tail exposure.** Value crashes in growth-led markets and in credit crises, when cheap stocks are cheap for a reason.

**Grouped variants.** raw and sector-neutral; earnings, cash-flow and book measures and their composite; monthly or quarterly rebalancing. All variants are one family.

### NT-Q01 Profitability and quality across non-technology sectors

*Q_quality, directional, mechanism class behavioural, sign +, horizon 3-12 months, implementation medium; data tier prices_and_edgar.*

**Rationale.** Investors underweight the persistence of profitability and the accrual component of earnings, so highly profitable firms with conservative accounting are priced as if their margins will revert faster than they do.

**Counterparty.** Investors who anchor on headline earnings and price growth stories while undervaluing durable but unexciting profitability.

**Universe.** US-listed non-technology common stocks and ADRs passing PIT screens, excluding financials and real estate, whose profitability measures are not comparable

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, fundamentals_pit

**Availability risks.** (1) Gross profitability and accruals must come from statements as first filed. (2) Excluding financials and real estate must use the PIT sector, not today's. (3) Survivorship inflates quality returns if failed firms are missing.

**Signal concept.** Composite of gross profitability, return on assets and low accruals from the latest usable statements, ranked within PIT sector.

**Baselines.** market and sector exposure; value (quality and value are negatively related); the technology-track profitability family as a separate test

**Confounders.** size; low-risk exposure; sector mix

**Costs (low).** Slow turnover; quarterly data updates.

**Validation requirements.** (1) Statements usable at the formation close only. (2) Raw and sector-neutral expressions reported together as one family. (3) Leave-one-sector-out cross-sector validation. (4) Control for value and low-risk exposure.

**Failure conditions.** (1) The effect is fully explained by value or low-risk exposure. (2) The effect lives in one sector only.

**Kill condition.** No positive sector-neutral excess return out of sample after costs and after controlling for value and low-risk exposure.

**Tail exposure.** Junk rallies after market bottoms, when low-quality firms rebound hardest.

**Grouped variants.** raw and sector-neutral; gross profitability, return on assets and accruals and their composite. All variants are one family.

### NT-M01 Price momentum across non-technology sectors

*M_momentum, directional, mechanism class behavioural, sign +, horizon 1-6 months, implementation low; data tier prices_and_edgar.*

**Rationale.** Investors underreact to gradual information, and positive feedback trading extends trends, so stocks that rose over the past year tend to keep outperforming over the following months.

**Counterparty.** Investors who anchor on old prices, sell winners early and hold losers (the disposition effect), and slow institutional rebalancing.

**Universe.** US-listed non-technology common stocks, ADRs and REITs passing PIT liquidity, price and history screens

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history

**Availability risks.** (1) Returns must be total returns with splits and dividends as known at formation. (2) The most recent month is skipped to separate momentum from short-term reversal. (3) Delisted losers must keep their delisting returns, or the short leg looks better than it was.

**Signal concept.** Total return over the past year skipping the most recent month, ranked within PIT sector for the sector-neutral expression and across the track for the raw one.

**Baselines.** market and sector exposure; sector momentum (the raw expression carries it); the technology-track momentum family as a separate test

**Confounders.** sector momentum; volatility regime; short-term reversal

**Costs (medium).** Monthly rebalancing with high turnover; costs and lagged execution are part of every evaluation.

**Validation requirements.** (1) Signals from total returns known at the formation close; fills at least one session later. (2) Raw and sector-neutral expressions reported together as one family. (3) Leave-one-sector-out cross-sector validation. (4) The lookback grid declared in advance; every variant counted.

**Failure conditions.** (1) The effect is fully explained by sector momentum. (2) The effect is eaten by costs at realistic turnover.

**Kill condition.** No positive sector-neutral excess return out of sample after costs with execution lagged at least one session.

**Tail exposure.** Momentum crashes in sharp market reversals, when past losers rebound violently.

**Grouped variants.** raw and sector-neutral; lookbacks from a declared grid; one-month skip. All variants are one family.

### NT-R01 Earnings revisions across non-technology sectors

*R_revisions, directional, mechanism class informational, sign +, horizon 1-3 months, implementation high; data tier needs_unavailable_history (blocked by analyst_estimates_pit).*

**Rationale.** Analysts revise forecasts gradually and prices incorporate revisions with a delay, so stocks with upward revisions in expected earnings tend to outperform as the information is absorbed.

**Counterparty.** Investors who react slowly to the drift in consensus expectations, and analysts who herd and revise in steps.

**Universe.** US-listed non-technology common stocks and ADRs with analyst coverage known at formation, passing PIT screens

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history, analyst_estimates_pit

**Availability risks.** (1) Point-in-time analyst estimates (with the time each was entered) are not affordable or verifiable today; the family needs forward collection or a data decision. (2) Coverage itself is selection; uncovered stocks must be reported, not dropped silently. (3) Estimate timestamps that are later than the revision date leak information backwards.

**Signal concept.** Breadth and size of consensus revisions to forward earnings estimates over the past three months, as known at formation, ranked within PIT sector.

**Baselines.** market and sector exposure; price momentum (revisions and momentum are related); post-earnings drift

**Confounders.** price momentum; earnings surprise; coverage changes

**Costs (medium).** Monthly rebalancing; covered names are more liquid.

**Validation requirements.** (1) Estimates as entered, with entry timestamps, never as revised later. (2) Raw and sector-neutral expressions reported together as one family. (3) Leave-one-sector-out cross-sector validation. (4) Control for price momentum.

**Failure conditions.** (1) The effect is fully explained by price momentum. (2) The data needed cannot be verified point in time.

**Kill condition.** No positive sector-neutral excess return out of sample after costs and after controlling for momentum, or no verifiable point-in-time estimate history.

**Tail exposure.** Crowding with momentum strategies and joint unwinds.

**Grouped variants.** raw and sector-neutral; breadth, size and dispersion of revisions. All variants are one family.

### NT-L01 Low-risk anomaly across non-technology sectors

*L_low_risk, directional, mechanism class structural, sign -, horizon 1-12 months, implementation medium; data tier prices_and_edgar.*

**Rationale.** Leverage-constrained investors who want more risk buy high-beta and high-volatility stocks instead of levering low-risk ones, bidding up risky stocks; risk-adjusted returns of low-risk stocks are therefore higher than their risk implies. The predicted sign is negative in risk: lower beta, higher risk-adjusted return.

**Counterparty.** Benchmarked and leverage-constrained investors who reach for beta, and retail investors with a preference for lottery-like stocks.

**Universe.** US-listed non-technology common stocks, ADRs and REITs passing PIT screens; volatility measured, never assumed from the sector label

**Data.** security_master, prices_daily, corporate_actions, delisting_returns, market_calendar, classification_history

**Availability risks.** (1) Beta and volatility must be estimated from returns known at formation, with a stated window. (2) Sector labels are not a proxy for risk; utilities and staples are not assumed calmer. (3) Delisted high-volatility stocks must keep their delisting returns.

**Signal concept.** Trailing beta and idiosyncratic volatility estimated on returns known at formation; low-risk minus high-risk, beta-balanced, within PIT sector for the sector-neutral expression.

**Baselines.** market exposure (beta-balanced construction); sector exposure (low-risk clusters in utilities and staples); quality and value

**Confounders.** interest-rate exposure of bond-like sectors; quality; sector concentration

**Costs (low).** Slow turnover; leverage and short financing must be costed for beta balancing.

**Validation requirements.** (1) Risk estimated from returns known at formation only. (2) Raw and sector-neutral expressions reported together as one family. (3) Leave-one-sector-out cross-sector validation. (4) Control for interest-rate exposure, quality and value.

**Failure conditions.** (1) The effect is fully a bet on bond-like sectors and falling rates. (2) The effect vanishes after sector neutralisation.

**Kill condition.** No positive sector-neutral beta-balanced excess return out of sample after costs, including leverage and short financing.

**Tail exposure.** Rising-rate shocks hit bond-like low-risk sectors; crowded low-volatility unwinds.

**Grouped variants.** raw and sector-neutral; beta and idiosyncratic volatility measures. All variants are one family.
