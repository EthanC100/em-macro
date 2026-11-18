# Technology equities research programme: design report

Version 0.2, 2026-11-18, branch `claude/phase4-tech-equities-i44jdx` (Project Manhattan, session 5; revised in the
S8 correction round, see [CORRECTIONS.md](CORRECTIONS.md)). Status: **research infrastructure on synthetic data
only.** Equity research on real data and every promotion are disabled (section 5). Nothing here reads market data, runs a strategy search, produces evidence,
or changes Manhattan's protocol, pre-registrations, ledger, PIT reader, operational store, attempt reconciler,
statistics or simulation. Companion documents:

- [HYPOTHESIS_CATALOGUE.md](HYPOTHESIS_CATALOGUE.md): 39 hypothesis families (generated from
  `manhattan/equities/catalogue.yaml`).
- [DATA_ACQUISITION.md](DATA_ACQUISITION.md): what data the programme needs, what a budget of about S$500 a month
  can and cannot buy, and the verification each candidate source needs first.
- [PROTOCOL_EXTENSION_PROPOSAL.md](PROTOCOL_EXTENSION_PROPOSAL.md): why Protocol v3.1 does not cover single equities
  and what a future version would need, for Ethan's review.
- [CORRECTIONS.md](CORRECTIONS.md): the S8 audit findings, what changed, and the counterexamples before and after.

Code: `manhattan/equities/` (23 modules and `catalogue.yaml`). Tests: `tests/test_manhattan_equities_*.py` (6 files).

## 1. Objectives

Manhattan's third research programme, after rates and commodities, beside the existing FX macro universe. Its job
is to make it *possible* to test thousands of technology-equity hypotheses later without breaking Manhattan's rules
of evidence: write it down before looking, record every look, history is a filter and the future is the test
(ARCHITECTURE §1). This phase builds the point-in-time foundations and the candidate-generation prototypes; it tests
no hypothesis.

Two approaches, kept apart in data, risk, performance and statistical accounting:

| | A. Long/short relative value | B. Directional stock selection |
|---|---|---|
| question | is a stock mispriced **relative to** economically related stocks? | does a stock have better prospective risk-adjusted return than others? |
| typical families | pairs and baskets, residual momentum, relative revisions, valuation residuals, supply-chain lead-lag (catalogue A, parts of C, D, E, F) | analogues, revisions, diffusion, quality and value (catalogue B, most of C, D, E) |
| exposures to remove | market, industry, factor, financing; borrow | market and sector beta are the *point* of a long book; factors are baselines |
| risk report | `risk.long_short_report` (gross, net, beta, industry, factor, borrow, squeeze, events, corporate actions) | `risk.directional_report` (beta, concentration, rate sensitivity, turnover) |
| catalogue field | `approach: relative_value` (21 families) | `approach: directional` (18 families) |

A family belongs to exactly one approach; a long/short and a long-only expression of one mechanism are two
families with `parent_family` links (ARCHITECTURE §3), never one family scored twice.

## 2. Architecture

Layers, each of which only reads the layer below and none of which writes to an existing Manhattan component:

```
 raw records          identity · prices + actions · fundamentals · estimates · events · classifications · borrow · graph
   (bitemporal)       each record: what it says, the period it describes, when it became public, when we captured it
        │
 contracts            sources.DataContract: provenance, licence, timestamp semantics, revision behaviour, verified
        │             coverage, permitted roles (signal / universe / risk / descriptive / evaluation_outcome)
        ▼
 point-in-time views  sessions.usable_close · FundamentalStore.value(as_of) · EstimateBook.consensus(at)
                      · UniverseBuilder.snapshot(day) · RelationshipGraph.edges(as_of) · BorrowBook.status(day)
        │
 derived features     features (exposures vs candidate signals; verified neutralisation) · macro sensitivities
        │
 candidate generation pairs.PairDiscovery (inside a Boundary) · analogues.match (descriptive / training)
        │             → research candidates, evidential weight 0, provenance hashes
        ▼
 hypothesis specs     catalogue.family_draft → manhattan.spec (draft only; freezing is Ethan's)
        │
 evaluation           manhattan.engine (existing; via pit_bridge → PitStore → Reader → Window) — not run here
        │
 statistical decision Protocol v3.1 + manhattan.stats + manhattan.ops.promotion — not reached: evidence.promote refuses
```

| module | responsibility | reuses |
|---|---|---|
| `sessions` | explicit exchange sessions (closures, half days); timezone-aware timestamp → first usable close | — |
| `sources` | data contracts; fail-closed role permissions; licensing | `manhattan.availability.validate_source` |
| `identity` | company vs security; ticker intervals; lifecycle events; duplicate and overlap refusal | — |
| `prices` | raw closes; split/dividend/delisting returns as of a date; missing-split detection; currency checks | — |
| `fundamentals` | bitemporal facts (original/restated); availability = max(public, capture) | — |
| `estimates` | broker estimates; consensus rebuilt at a moment; revisions; coverage | — |
| `events` | release timing (scheduled ≠ released); label consistency; pre-release surprise | — |
| `universe` | technology taxonomy; classification history; PIT eligibility with reasons | — |
| `graph` | relationships with validity, disclosure and recording dates; lagged propagation | — |
| `features` | normalisation; neutralisation with verification; momentum family; fundamental exposures | — |
| `pairs` | discovery inside a boundary; hedge ratios; spread diagnostics; shorting feasibility | `statsmodels` (ADF, Engle–Granger) |
| `analogues` | eligibility (descriptive vs training); robust normalisation; distances; explanations; baselines | — |
| `macro` | PIT macro reads; sensitivities; incremental-information diagnostic | `manhattan.engine.pit.Window` |
| `costs` | trade and holding costs; borrow availability and fees; recall | — |
| `risk` | long/short and directional reports; effective bets (long-only); hedged-book risk; cross-book factor aggregation | — |
| `evidence` | candidate/evidence boundary; research gate; promotion gate (both local to this package) | `manhattan.ops.promotion` |
| `provenance` | content hash of research outputs | `manhattan.spec.spec_hash` |
| `pit_bridge` | export to the existing PIT store | `manhattan.engine.pit.PitStore` |
| `catalogue` | catalogue validation, ranking, rendering, family drafts | `manhattan.spec` |
| `research` | the authorized entry points: research gate, `Reader`-opened windows, reads as of the boundary | `manhattan.engine.pit.Reader` |
| `integration` | exact signatures of PR #86 and #84 interfaces, pinned to the inspected heads; a checker | — |
| `synthetic` | deterministic fixtures | — |

**What was deliberately not built.** A second backtester (the existing `manhattan.engine.backtest` takes a `Window`;
`pit_bridge` feeds it), a second statistical engine (no test, threshold or tier is implemented here), a portfolio
optimiser, execution or brokerage code, data downloaders.

## 3. Point-in-time architecture

### 3.1 Two clocks, and a third for vendors

Every record carries the period it describes and the moment it became public; vendor records also carry the moment
the vendor captured them. The usable moment is `max(public, capture)` when capture is known (a backfilled history is
not usable before it existed in the vendor's database); the usable **close** is `sessions.usable_close(t)`:

| public at | usable at the close of | why |
|---|---|---|
| before the open (e.g. 07:00 New York) | that session | known before any trade that day |
| during the session | the next session | conservative: intraday prices already partly reflect it, and the exact minute is often wrong |
| after the close, weekend, holiday, closure | the next session | |
| date only, time unknown | the next session after that date | treated as after the close |

The Manhattan engine then trades a decision at the next close (`lag = 1`), so an after-market release is traded two
closes later. Naive timestamps are refused everywhere (`TemporalError`).

### 3.2 Identity

`company_id` (issuer) and `security_id` (one share class on one listing) are permanent and never reused. A ticker
is an interval `[start, end]` with a `known_from` date; `SecurityMaster.resolve(ticker, on, as_known_at)` fails on
zero or several matches. Lifecycle events (IPO, delisting with reason, merger, acquisition with counterparty,
spin-off, bankruptcy, exchange change, ticker change, share-class creation) must agree with the listing dates.
Duplicate listings of the same share class are refused. Tested: ticker change, ticker reuse by another issuer, a
change announced in advance, duplicates, overlaps.

### 3.3 Prices

Raw unadjusted closes are the record. Total returns are computed as of a date from actions known by then
(`r_t = (P_t·k_t + D_t)/P_{t−1} − 1`); split-adjusted history is computed as of a date, so a later split cannot leak
into an earlier back-adjusted series. A close ratio matching a common split ratio with no known split, or an extreme
unconfirmed move, raises. Missing or suspended sessions produce a multi-session return flagged as such. Bars on
closed days are refused. A security that stops trading needs a delisting return from data, or an explicit,
referenced assumption per delisting reason, flagged in the output; dropping it is refused as survivorship bias.

### 3.4 Fundamentals

`Fact(company, metric, period_end, kind, value, currency, public_time, capture_time, vintage)`. A quarter is not
known because it ended: it is known from the close after its filing. Restatements are new vintages; `as_of` returns
the latest vintage known at the date (or the original). TTM requires four consecutive quarters known at the date;
growth compares two periods from one knowledge state. Currencies travel with values and mixing raises. Segment
reporting, share counts and accounting-basis changes are metrics with their own facts and flags (`basis`); their
comparability across companies is a research question recorded in each family's availability risks.

### 3.5 Analyst estimates

Each broker estimate is a vintage. Consensus at a moment is rebuilt from per-broker latest live estimates (dropped
coverage leaves; stale estimates expire), using effective time `max(published, captured)`. The common hazard —
vendor consensus histories recomputed after the fact, with late-captured revisions dated at their publication — is
caught by the capture time, or refused (`require_capture=True`) when capture times are absent.

### 3.6 Universe

Candidates on a day are the securities the master shows listed and known on that day; eligibility (category,
security type, currency, price, trailing dollar volume, market capitalisation from known shares, trading history,
corporate-action completeness, fundamental coverage, borrow) is evaluated from data known at that close, and every
exclusion has a reason. The snapshot's `membership_hash` binds every feature and neutralisation to that day's
universe (`assert_snapshot_for`). Tested: a company delisted later is a member before; an IPO is absent before
listing; tampering with every bar after the day, adding a late reclassification and a later issuer changes nothing.

**Initial scope: US-listed common stocks and ADRs.** US listings have the longest public filing history with
machine-readable timestamps (EDGAR acceptance times), one regulator, one calendar family and the deepest
borrow/short-interest disclosure. ADRs bring most large non-US technology issuers in, at the price of
foreign-filer reporting lags (20-F annual reporting) that the fundamentals contract must declare. International
extension adds calendars, currencies (explicit FX conversion; mixing currencies already raises) and contracts for
local filings; the identity, universe and PIT layers are already currency- and calendar-aware.

### 3.7 Relationships

Each edge has `valid_from/valid_to` (economic truth), `public_from` (disclosure) and `recorded_from` (entered in our
data). Usable at `t` only if all three permit. A relationship researched today and back-dated is usable only from
the day it was recorded; the retrospective view exists for description and is labelled.

### 3.8 Alternative data

Patents, product releases, developer adoption, cloud capex, supply-chain links, hiring, customer concentration,
regulatory text, call transcripts and adoption indicators each have a dataset kind and are declared by
`sources.alternative_contract`: descriptive-only until someone verifies their historical timestamps and revision
behaviour. No family that depends on them can be evaluated until then (their catalogue rankings say so).

## 4. Research families and implemented primitives

| catalogue family | implemented here | not implemented (needs data or an owner decision) |
|---|---|---|
| A relative value | `pairs`: boundary-enforced discovery (economic link, correlation, two-sided Engle–Granger, half-life, sub-window stability), static / rolling / beta-neutral hedge ratios, factor-residual spreads, out-of-sample break diagnostics, borrow and residual-beta feasibility | basket construction, a trading rule, any parameter choice on data |
| B analogues | `analogues`: observation/outcome separation, descriptive vs training eligibility, overlap thinning, robust normalisation on eligible candidates, standardised / Mahalanobis (shrunk) / trajectory distance, missing-data overlap, industry / stage / regime constraints, explanations, sector-mean and ridge baselines on the same training set | the incremental-value test (a frozen hypothesis under Protocol v3.1) |
| C earnings | `events` (timing, labels, pre-release surprise), `estimates` (consensus, revisions, breadth, dispersion, coverage) | guidance parsing, call text |
| D diffusion | `graph` (dated edges, lagged confidence-weighted propagation) | any real relationship dataset |
| E factors | `features` (momentum, industry-relative, residual momentum, reversal, beta, fundamental ratios, growth, valuation yields; verified neutralisation; exposures vs candidate signals) | equity core-factor definitions for the protocol's core hedge (an owner decision: PROTOCOL_EXTENSION_PROPOSAL §2) |
| F macro | `macro` (PIT reads through the existing `Window`, past-only sensitivities, incremental-information diagnostic), `risk.aggregate_factor_exposure` (one factor counted once across books) | macro series themselves (the existing macro infrastructure, unchanged) |

**Retrospective break classification on one synthetic generator** (tests, 20 fixed seeds). `out_of_sample` is a
*retrospective* diagnostic: it looks at a whole evaluation window after it has ended, so it is never a forecast or a
signal inside that window (`StabilityReport.kind == "retrospective"`, `usable_from` = the window's end). On the
synthetic generator of `manhattan.equities.synthetic` (an AR(1) residual with φ = 0.9 around a random-walk leg):
at least 85% of stable pairs that pass formation are classified stable; at least 90% of breaks at the evaluation
start and at least 85% of breaks two-fifths of the way in are flagged; breaks inside formation, gaps, missing
legs and a leg that stops trading are flagged; slow but genuine reversion (φ = 0.97, 0.99) is almost always rejected
at formation (low power, accepted). **These numbers describe the code on that generator. They are not predictive
performance, not error rates for real relationships, and not evidence that pair trading works.** The `PairRules`
parameters were set by looking at these synthetic cases only; on real data they are a grid to be frozen, never tuned
on an evaluation window. Every pair looked at is counted (`PairDiscovery.attempts`), including those without an
economic link and those rejected, so the number of candidates can be read against the number tried.

## 5. Scientific integration

1. **Specs.** A catalogue entry becomes a family spec by `catalogue.family_draft`, validated by
   `manhattan.spec.validate_family`, marked `status: draft`, never registered or frozen here. Hypotheses would add
   domain (`us_tech_equities_daily`, proposed), data sources with publication contracts, the signal, the bounded
   grid (`PairRules`, analogue `k`/method/constraints, feature look-backs) and the primary binding.
2. **PIT.** `pit_bridge` exports equity data to the existing `PitStore` with knowledge-day availability, and the
   authorized entry points (`manhattan.equities.research`) read them only through `pit.Reader(...).window(...)`, so
   `manhattan.roles.check_read` and the exploration cap (2019-12-31) apply. Nothing **forces** other code to use
   that path: the numerical primitives (`pairs`, `analogues`, `features`, ...) take whatever arrays a caller gives
   them, and say so. No equities code or test constructs a `Window` directly (a test checks this; under PR #86 it
   would raise).
3. **Attempts.** No reserve or forward evaluation may begin until binding attempt accounting (PR #86) is merged and
   approved. `integration.EXPECTED` pins its exact interface (`access.register_evaluation(ledger, *, identity,
   windows, caller, fence, freeze, holding, token, supersedes)` → `AttemptContext`); the adapter is written after it
   merges.
4. **Multiple testing.** Families, not variants, are the unit (ARCHITECTURE §3). Grids are bounded
   (`manhattan.spec.MAX_GRID`); overlapping catalogue entries are marked as members of a shared hypothesis family
   (`shared_family`) and would be frozen as one family; pair discovery counts every pair it looks at.
   Pair and analogue *candidates* are not tests; a family built on them is one hypothesis whatever the number of
   candidate pairs it trades.
5. **Forward e-process, e-LOND, tiers, dormancy.** Used as they are, once a protocol version covers equities; not
   re-implemented. **What is enforced, and where.** `evidence.promote` refuses every promotion (Manhattan's
   `manhattan.ops.promotion` gate, called, and the empty `EQUITY_COVERING_PROTOCOLS`), and the research entry
   points refuse non-synthetic sources while `EQUITY_RESEARCH_APPROVED` is False. Both gates are local to this
   package: they are **not integrated into Manhattan's protected pipeline**. `manhattan.ops.promotion.promote`,
   `manhattan.engine.evaluate` and the runner do not know about asset classes; an equity family pushed through them
   would meet only their own gates (no adopted protocol, `claims.enabled: false`, attempt registration after #86).
   Making the protected pipeline refuse out-of-scope domains is an owner decision
   ([PROTOCOL_EXTENSION_PROPOSAL.md](PROTOCOL_EXTENSION_PROPOSAL.md) section 3) and is not claimed here.
6. **Audit.** Every research output can carry a provenance record (`provenance.record`): input hashes, parameters,
   boundary, code version, contracts; no values, so it may be committed even when inputs are licensed.

The existing pre-registrations (SIM_PREREG, SIM_PREREG_v2) and Protocol v3/v3.1 are **not** taken to cover a new
asset class: see [PROTOCOL_EXTENSION_PROPOSAL.md](PROTOCOL_EXTENSION_PROPOSAL.md).

## 6. Risk architecture

Long/short books: gross, net, beta-weighted net, industry net, factor exposures, single-name concentration (max,
HHI, effective names), borrow cost (a missing fee raises: an omission is not zero), short-squeeze names (days to
cover), earnings-event and corporate-action gross, liquidity (days to exit at a participation rate). Directional
books: beta, sector concentration, factor exposures (growth, value), rate sensitivity, liquidity, one-way turnover,
drawdown description. For **long-only** books `effective_bets` (squared diversification ratio) shows that ten
technology names on one factor are about one bet. It is refused for books with shorts: in a hedged pair the
denominator is the small residual variance and the ratio would report hundreds of "bets" for one spread (S8 M8).
Hedged books use `hedged_book_risk` (book volatility, leg volatility without netting, the share netting removed, and
the share of variance in the largest principal component). `aggregate_factor_exposure` adds exposures across books
and lists factors carried by more than one, so a rate or growth exposure is not counted as several independent
sources. No existing portfolio or execution system is touched; a future portfolio interface is not specified until
one exists.

## 7. Costs

`costs.EquityCostModel`: half-spread, commission, square-root impact on daily volatility and participation, borrow fee
from a point-in-time `BorrowBook` (no record = not shortable), recall probability × buy-in cost, short and leverage
financing spreads. These are assumptions: **every parameter must be stated, with a `reference` for where it came
from**; none has a default (S8 M10), because a default spread or impact makes a strategy look cheap by omission.
Protocol v3.1 §10.3 re-estimates cost models from
recorded spreads; nothing here replaces that. Shorting costs are typically the binding constraint for
relative-value families in small and mid-cap technology names, and historical borrow data are the hardest data to
obtain (DATA_ACQUISITION §3).

## 8. Known limitations

- **No real data has been seen.** Every behaviour is tested on synthetic fixtures; real data will expose formats,
  gaps and conventions the contracts do not yet name.
- **Daily resolution.** Intraday reaction windows are reduced to closes; the conservative mapping costs some power
  around releases.
- **Pair and analogue filters are heuristics** with declared parameters, not tests; their synthetic hit rates
  (section 4) are retrospective classifications on one generator and do not transfer to markets.
- **Slow mean reversion is rarely accepted** by the pair filter (low power, by design conservative).
- **Effective bets and cost models are approximations.** The diversification ratio depends on the covariance
  estimate and is defined for long-only books only; cost parameters must be supplied and referenced.
- **Unresolved split-like moves are holds.** Without share counts, a −50% day cannot be told from a missing 2:1
  split; such securities are excluded with a stated reason and listed in `Snapshot.holds` for review, which biases
  the universe until they are resolved.
- **Gates are local.** The research and promotion gates bind this package's code; the protected pipeline does not yet
  know about asset classes (section 5).
- **The universe builder is O(securities × history)** per snapshot; fine for research sizes, not optimised.
- **Classification history** depends on a vendor's archived assignments; most vendors publish only current codes.
- **ADR and foreign-filer timing** is declared per contract but not exercised by a fixture.
- **Equity core factors are undefined**, so Protocol v3.1's core hedge cannot be applied to equities yet.

## 9. Milestones

| milestone | content | gate |
|---|---|---|
| E1 (this PR) | PIT contracts, identity, prices, fundamentals, estimates, events, universe, graph, features, pairs and analogue prototypes, risk, costs, evidence gate, catalogue | review |
| E2 | data acquisition decisions; contracts filled for chosen sources; licence review; private storage path (em-macro-data or the iMac) | Ethan (budget, licences) |
| E3 | ingest adapters writing to the private store only; data-quality reports (split detection, delisting coverage, timestamp audits) | E2 |
| E4 | equity core factors defined, daily, PIT; protocol extension drafted; simulation scenarios for long/short books, borrow and delistings | Ethan (protocol) |
| E5 | first batch of family specs (from the top of the priority list) prepared for Ethan's freeze; exploration-role runs ≤ 2019-12-31 only | E3, E4, attempt accounting approved |
| E6 | forward recording of frozen families | adopted protocol covering equities |
