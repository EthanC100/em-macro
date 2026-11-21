# Non-technology equities: the fourth research track (issue #102)

Status: **dormant, synthetic-only research infrastructure.** Nothing here reads real data or registers, freezes or
promotes anything. Nothing runs a strategy search, enables forward testing, the reserve, live trading or unattended
orchestration, or changes a protected path or switch. Every result is infrastructure validation on invented data
(`evidential_weight: 0`, `scientifically_validated: False`).

Code:

- `manhattan/tracks.py`: the four-track registry.
- `manhattan/equities/sectors.py`: the taxonomy.
- `manhattan/equities/universe.py`: `track_rules` and `track_snapshots`.
- `manhattan/equities/sector_synthetic.py`: the synthetic world.
- `manhattan/equities/track_compare.py`: the portfolio comparison and volatility measurement.
- `manhattan/equities/catalogue_nontech.yaml` with `catalogue.py`: the hypothesis catalogue and its cross-track
  counting.
- `manhattan/equities/registration.py`: the hypothesis-first gate (§5a). A draft family never becomes an
  executable experiment without a pre-registered, immutable specification.

Tests: `tests/test_manhattan_tracks.py`, `tests/test_manhattan_equities_nontech.py` and
`tests/test_manhattan_equities_registration.py`. Generated catalogue:
[HYPOTHESIS_CATALOGUE_NONTECH.md](HYPOTHESIS_CATALOGUE_NONTECH.md).

## 1. Audit: what exists and what is planned (main at `a3fb970`)

| component | exists | planned or missing |
|---|---|---|
| equity identity, tickers, lifecycle (`identity`) | yes (PR #87): permanent ids, ticker intervals with publication dates, IPOs, delistings, acquisitions, ticker reuse | nothing for this issue |
| prices, corporate actions, total and delisting returns (`prices`) | yes: splits, cash/special/stock dividends, return of capital, delisting returns with known-from dates, survivorship guard | nothing |
| fundamentals, estimates, events | yes: bitemporal, restatements as vintages | financial-sector and REIT statement items are not modelled specifically (§3) |
| universe and eligibility (`universe`) | yes: PIT listing, liquidity, price, history, market cap from split-adjusted shares, action completeness, borrow | **before #102:** one catch-all category `non_technology`, so no non-technology universe could be formed. **Added:** ten sectors, `track_rules`, `track_snapshots` |
| costs and risk (`costs`, `risk`) | yes: caller-stated cost model (no defaults), borrow, drawdown, exposure reports | per-sector cost calibration (§7) |
| hypothesis catalogue | yes: 39 technology families, draft | **added:** 5 non-technology families and cross-track links |
| market data (#92) | asset classes `future`, `fx_spot`, `fx_forward`, `bond_cash`, `commodity_spot`, `index`; Norgate/Databento adapters dormant | no equity and no fund (ETF) class; Treasury and commodity futures are both `future`, with no sector field (§2) |
| execution (#85, #93) | futures execution, lag ≥ 1, contract costs | equities use `equities.costs` (proportional plus impact), not the futures model |
| HTE (#89, #90) | synthetic domains `commodity`, `rates`, `fx` | no equity domain (acceptance GAP-04) |
| acceptance gate (#91) | S16 gates and integration-gap probes | no track-level gate yet (§6) |
| a "research track" concept | **none before #102** | **added:** `manhattan.tracks` |

## 2. Four research tracks

| track | instrument | universe | shared pipeline |
|---|---|---|---|
| `commodities` | commodity futures | declared futures roots | market data, futures execution, HTE `commodity` |
| `technology_equities` | US common stocks and ADRs | PIT technology categories | `manhattan.equities` |
| `non_technology_equities` | US common stocks, ADRs and REITs | PIT categories of ten non-technology sectors | `manhattan.equities`, the same code |
| `rates` | **Treasury futures only** | declared futures roots | market data, futures execution, HTE `rates` |

**Separately identifiable and measurable.**

- Every research item names exactly one track. `tracks.tally` refuses an item with no track, an unknown track or
  several tracks, and always reports all four tracks.
- The combined equity portfolio is a **combination**, reported next to its parts. It is never a fifth track, and
  its components stay counted in their own tracks.
- The two equity tracks share one pipeline and differ only in the categories they admit. `track_snapshots` checks,
  on every day, that they are disjoint and that every member's category, as known that day, is inside its track.

**Treasury futures, cash bonds and bond ETFs are different instruments.**

| kind | market-data class | track | why it is not interchangeable |
|---|---|---|---|
| Treasury future | `future` (root declared as `treasury_future`) | `rates` | deliverable basket, cheapest-to-deliver bond, conversion factor, roll, exchange settlement price |
| cash bond | `bond_cash` | **none** (NT-4) | OTC, clean and dirty prices, accrued interest, repo financing, no settlement price |
| bond ETF | none (the schema has no fund class) | **none** (NT-5) | a listed fund: NAV premium or discount, expense ratio, tracking error; never an operating company, so it is in no equity track |

A Treasury future and a commodity future are both `future`. `tracks.rates_instrument_kind` therefore requires a
caller-owned root declaration, refuses undeclared roots and never guesses. No real roots are written in code (NT-6).

## 3. Point-in-time controls for non-technology equities

All of these are the shared pipeline's. #102 adds no second engine.

| control | how | tested by |
|---|---|---|
| sector membership | `ClassificationHistory` with `known_from`. A reclassification changes the track only from its publication date; a vendor backfill is never applied retroactively | `test_a_reclassification_moves_track_only_from_its_publication` (one move announced in advance, one backfilled 19 months late) |
| symbol mapping | permanent security ids; ticker intervals with `known_from` and `end_known_from`; ticker reuse | shared `identity` tests |
| delistings | members before they leave; delisting returns required in outcomes (`DelistingPolicy.require`); refused before they are known | `test_survivorship_delistings_ipo_and_liquidity`, `test_outcomes_carry_delisting_returns_and_then_cash` |
| corporate actions | splits, dividends and return of capital applied as known; raw prices drop and total returns do not | `test_corporate_actions_change_raw_prices_not_total_returns` |
| liquidity and investability | price, 63-session median dollar volume, market cap from split-adjusted known shares, history, action completeness; every exclusion has a reason | survivorship and universe tests |
| security types | non-technology admits `common`, `adr` and `reit` (NT-2); funds, preferreds, warrants, rights and units never enter an equity track | `test_funds_and_unassigned_companies_are_in_no_equity_track` |
| transaction costs | `EquityCostModel` with a stated reference and no defaults; costs on the change from drifted weights to targets; ADV and volatility as known at the decision | `test_costs_lower_net_returns_and_vanish_with_zero_costs` |
| timestamps and availability | signals read `total_returns(as_of=t)`; fills at the close `lag ≥ 1` sessions later; `lag = 0` refused | `test_same_close_execution_and_missing_costs_are_refused` |

**Sector-specific cautions for real data (later):**

- Bank, insurer and REIT statements are not comparable with industrial ones (book value, NAV, funds from
  operations). Families must use sector-appropriate measures or exclude those sectors, as NT-Q01 does.
- Utilities are rate-regulated, and energy and materials carry commodity exposure, so families must control for
  them.

## 4. Classification policy (NT-1)

- **Own taxonomy, ten sectors.** The sectors are healthcare, financials, industrials, utilities, consumer staples,
  consumer discretionary, materials, energy, real estate and communication services. Each has the package's own
  sub-industry categories (`sectors.NON_TECH_SECTORS`, 43 categories).
- **Vendor codes are mapped, not adopted.** GICS, ICB or EDGAR SIC codes are mapped through a source contract into
  dated `Classification` records.
- **Boundaries.** `consumer_internet`, `digital_advertising` and `ecommerce` stay technology, where a vendor may file
  them under communication services or consumer discretionary. `payments` is financials. Telecom carriers and
  traditional media are communication services.
- **One category per company per day,** so a company is in at most one equity track on any day.
- **The legacy catch-all `non_technology` stays valid but is in no track.** A non-technology company must carry a
  sector category to enter the universe (fail closed).
- **Volatility is measured, never assumed.** In the synthetic world, energy (0.40), materials (0.34) and healthcare
  (0.34) sector indices are more volatile than technology (0.27), while utilities (0.12) and staples (0.13) are
  calmer (`sector_volatility`; the test requires a non-technology sector more volatile than technology).

## 5. Hypothesis families and cross-sector validation

There are five families, one per mechanism the issue names. Each has its technology counterpart:

| id | mechanism | technology counterpart | data tier |
|---|---|---|---|
| NT-V01 | value | TE-E06 (SF-VALUATION) | prices + EDGAR |
| NT-Q01 | profitability and quality (excluding financials and real estate) | TE-E04 | prices + EDGAR |
| NT-M01 | price momentum | TE-E01 (SF-MOMENTUM) | prices + EDGAR |
| NT-R01 | earnings revisions | TE-C04 (SF-REVISIONS) | needs unavailable history (PIT estimates) |
| NT-L01 | low-risk anomaly | none (new mechanism) | prices + EDGAR |

**Controls against inflation, cherry-picking, leakage and double counting** (validated by `catalogue.validate` and
`cross_track_report`):

- **Sector-neutral is a variant, not a family (NT-3).** Every family must list the sector-neutral expression among
  its grouped variants. Raw and sector-neutral are one family and one multiple-testing unit.
- **Leave-one-sector-out validation is required of every family.** An effect that lives in one sector is reported
  as that sector's effect.
- **Cross-track links never shrink a denominator.** All 44 families (39 technology and 5 non-technology) stay in the
  combined count. A linked pair is **dependent**: a result in one track is never independent confirmation of the
  other unless the link was designated a replication before either was tested (`role: designated_replication`,
  NT-7). Today every link is `related_not_designated`.
- **One family per mechanism per track.** No performance figures, tickers or company names; the validator refuses
  them.

## 5a. Hypothesis first: draft families are not experiments (review of #103)

| | draft family | pre-registered experiment |
|---|---|---|
| where | `catalogue_nontech.yaml` (and `catalogue.yaml`) | a Manhattan hypothesis spec frozen in a batch with its family |
| holds | mechanism, sign, counterparty, data, risks, ranking | everything needed to run and judge one test (below) |
| status | `draft`, untested, unregistered | listed in a manifest that `manhattan.freeze.verify_frozen` accepts |
| can run | **never** | only through `registration.admit`, and today only on a synthetic world |
| who | anyone drafts | the freeze is Ethan's (hard rule 4); agents prepare nothing for it here |

**The specification** (`registration.experiment_spec`; every field in `REQUIRED` is mandatory) is a Manhattan
hypothesis spec. Its family is exactly `catalogue.family_draft(entry)`. It states:

- the economic mechanism and the predicted direction, which must equal the family's;
- the track, the universe (that track's point-in-time eligibility-rules hash) and the data kinds (within the
  family's);
- the signal construction and the declared, finite parameter grid;
- the benchmark (the track's own costed equal-weight universe);
- the full transaction-cost model with its reference, and the execution lag (at least 1);
- the windows: selection up to `selection_end`, then an untouched holdout `[holdout_start, holdout_end]`;
- the selection rule and machine-checkable rejection criteria;
- the attempt-accounting identity: batch, `exploration`, `blind`, not designated, in the ledger.
  `attempt_identity` derives each variant's PR #86 schema-2 identity from the frozen family, hypothesis, variant
  and primary-executable specs.

**The gate, `registration.admit`, fails closed when:**

- there is no batch, no timestamp proof or no signed tag, or the manifest hash differs (`verify_frozen`);
- the catalogue family as drafted now is not in the manifest (the family was edited after registration);
- the spec is not in the manifest (it was modified after registration, or never registered);
- the spec is incomplete or inconsistent with its family;
- the batch named for attempt accounting is not the batch that froze the spec;
- a declared variant or its primary executable for this engine identity is not frozen (the grid or the engine
  changed).

**After admission:**

- An `ExperimentHandle` keeps a canonical copy of the spec. Runs refuse handles this module did not issue, copies,
  edited handles and a cost model other than the registered one.
- `run_selection` runs every declared variant and no other, chooses by the declared rule, and reads nothing dated
  after `selection_end`. A test instruments the price book to fail on any later read.
- `run_holdout` needs that selection's lock. It runs only the locked variant on the holdout, once per registration,
  and evaluates the rejection criteria there only.
- `count_registered` counts admitted experiments per track and combined, never twice and never in two tracks:
  - duplicates and the same experiment under another family in the same track are refused;
  - the same experiment in the other track, and catalogue-linked mechanisms, are reported as dependent;
  - `independent_confirmations` is 0, and `denominator` is `None` (NT-8 and D-1 stay open).

**Dormant.**

- `EXECUTION_ON_REAL_DATA` is a constant `False`.
- `run_selection` and `run_holdout` run only on synthetic worlds (`synthetic.is_synthetic`).
- `track_compare` itself runs only on synthetic worlds, so no performance-based selection is possible on this track
  outside the gate.
- The one-look holdout guard lives in the process. Making it persistent requires the holdout read to be an attempt
  in PR #86's ledger, which depends on D-10 and B4 (§7).

**Adversarial tests** (`tests/test_manhattan_equities_registration.py`, 44):

- missing registrations: no batch, a batch that froze another experiment, no signed tag, a wrong manifest hash, no
  timestamp;
- modified specifications: grid, costs, holdout, rejection criteria, signal and lag changed after freezing; a spec
  file edited in the batch; the catalogue family edited; copied and edited handles; another engine identity; another
  track;
- incomplete specifications: every required field, sign flips, data outside the family, lag 0, overlapping windows,
  empty or unknown criteria;
- holdout leakage:
  - an effect planted only in the holdout is invisible to selection and found in the holdout;
  - no price after the cutoff is read;
  - no lock means no holdout, and another experiment's lock is refused;
  - one look only;
- cross-track double counting: duplicates, the same experiment under another family, linked and same-content
  pairs across tracks;
- PR #86 identities validate with `ledger.validate_attempt_identity`;
- dormancy: unmarked worlds are refused by the gate, `compare` and `sector_volatility`.

**Gate mutation check.** I planted 14 defects:

- the spec or family not checked against the manifest;
- the signed tag bypassed;
- selection reading past its cutoff;
- the holdout run without a lock, or read twice;
- duplicates or same-track content double counted;
- a sign flip allowed;
- the real-data guard removed;
- the cost model, issued handles or frozen executables not checked;
- the admitted spec not re-hashed.

13 were caught. The one that survives is the re-hash of an admitted handle's canonical copy. It is defence in
depth: through any public path, editing a handle first breaks its issue fingerprint, and that refusal is tested.

## 6. Fixtures, tests and acceptance criteria

**The synthetic world** (`sector_world`) holds:

- 29 operating securities across all eleven sectors, plus a bond ETF;
- three delistings: an energy bankruptcy with a delisting return known three weeks later, a bank acquired for cash
  announced in advance, and a technology failure;
- an IPO, and an illiquid stock;
- a 3:1 split and quarterly utility dividends;
- a REIT;
- two cross-track reclassifications;
- an optional causal momentum effect planted in one track.

**Comparison** (`track_compare.compare`): technology-only, non-technology-only and the combined costed book.

- Monthly decisions, with fills at the next close.
- Each sleeve's lookback is chosen on in-sample net Sharpe up to a fixed `is_end`, and every variant tried is
  reported.
- Out of sample, the report gives costs, drawdown, volatility, turnover and the correlation between the two
  sleeves, plus the excess over each track's own costed equal-weight universe.

**Synthetic results** (out of sample 2007–2008, 520 sessions; they describe the generator, not a market):

| world | sleeve | return | vol | Sharpe | max DD | cost drag | excess Sharpe vs own universe |
|---|---|---|---|---|---|---|---|
| null | technology | 0.254 | 0.305 | 0.83 | −0.25 | 0.009 | 0.46 |
| null | non-technology | 0.078 | 0.196 | 0.40 | −0.32 | 0.010 | −0.75 |
| null | combined | 0.164 | 0.222 | 0.74 | −0.24 | 0.008 | — |
| planted in non-technology | technology | **identical to null** | | | | | 0.46 |
| planted in non-technology | non-technology | 1.074 | 0.203 | 5.28 | −0.12 | 0.009 | 2.40 |

In the null world the two sleeves are correlated at 0.54. Long-only sleeves earn their universe's market return,
which is why the excess over the track's own universe is reported.

**Acceptance criteria (infrastructure PASS):**

1. Taxonomy and policy: ten sectors, disjoint categories, fail-closed legacy label.
2. Tracks disjoint every day; their union equals one shared universe.
3. A reclassification is used only from its publication date.
4. Delisted, acquired and failed companies are members before they leave, and delisting returns are in outcomes.
5. Corporate actions are correct in total returns.
6. Funds are in no equity track, and REITs are in non-technology.
7. Volatility is measured.
8. Lag ≥ 1, costs required, and excess reported over the track's own universe.
9. In-sample results do not depend on data after the cutoff.
10. A planted effect is found only in its own track.
11. The catalogue validates and its cross-track links resolve.
12. **Hypothesis first** (§5a): no draft family runs, and only a pre-registered, unmodified, complete experiment
    spec is admitted. Selection reads nothing after its cutoff, the holdout is read once with the locked variant,
    and no registration is counted twice or as independent across tracks.

A mutation check, which planted a defect for each criterion and ran the tests (retroactive classification,
same-close fill, dropped delisting returns, ignored costs, missing category guard, dropped REITs, selection on
out-of-sample data, missing benchmark, mis-filed payments), caught every defect.

## 7. Dependencies for later real-data validation

**Infrastructure PASS is not evidence.** Nothing in §6 says anything about markets. Scientifically validated
trading evidence needs, at least:

1. **Data** (DATA_ACQUISITION.md applies unchanged), owner decisions:
   - a survivorship-free US price source with delisting returns covering all sectors;
   - a classification history with publication dates (EDGAR SIC as a proxy, or a licensed vendor history);
   - point-in-time fundamentals, including bank, insurer and REIT items;
   - PIT analyst estimates for NT-R01, which are unavailable today.
2. **Costs** calibrated by sector and size from recorded spreads. Today's cost models are stated assumptions.
3. **The protocol.** Protocol v3.1 does not cover single equities (PROTOCOL_EXTENSION_PROPOSAL.md); it needs an
   extension covering both equity tracks.
4. **Freezes and pre-registrations**, Ethan only, including any designated cross-track replication. The gate
   (§5a) admits only a verified freeze. Its real-data execution (`EXECUTION_ON_REAL_DATA`) is off, and turning it on
   is a reviewed change.
5. **One-look holdout across processes**: each holdout read registered as a PR #86 attempt, which depends on D-10
   and B4. Today the guard lives in one process.
6. **Reserve windows** per equity domain in `config/manhattan.yaml`, which stays untouched here.
7. **Integration:**
   - an HTE equity domain (acceptance GAP-04);
   - attempt accounting for equity evaluations (#86/#98);
   - evidence classification (GAP-03, GAP-06).
8. **A track-level acceptance gate in the S16 suite**, once the above exist.

## 8. Owner decisions requested

| id | decision | default here |
|---|---|---|
| NT-1 | classification policy and the boundary cases (§4) | package taxonomy as above |
| NT-2 | REITs (equity and mortgage) in the non-technology track | included |
| NT-3 | sector-neutral as a variant of every family rather than a sixth family | variant |
| NT-4 | cash Treasuries in the rates track | excluded (no track) |
| NT-5 | bond ETFs in any track | excluded (no track) |
| NT-6 | which Treasury and commodity futures roots each futures track declares | caller-declared; none in code |
| NT-7 | designating any non-technology family as a replication of a technology family | none designated |
| NT-8 | multiple-testing counting across tracks (per-track or combined family-wise), together with D-1 | combined count reported; no decision made |
| NT-9 | data sources for the non-technology sectors (§7) | none |

## 9. Coordination with PR #98

#98 (HTE → PR #86 attempt-accounting bridge) touches only `manhattan/hte_accounting/`, its tests, a benchmark
script and results. This work shares no file with it and does not use the bridge. When equity evaluations are
accounted, they use the same owner decisions (D-1, D-10, B4), and the track of each evaluation would be one more
identity field. That is a follow-up for after #98 and the decisions.
