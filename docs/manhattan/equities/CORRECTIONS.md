# Technology equities: S8 audit correction round

2026-11-18. Audited head `477ba18` (PR #87); S8 issued REQUEST CHANGES. This file records each finding, what changed,
and the counterexample before and after. **Source of the findings:** the audit's item list as relayed to this session
(H1–H4, M1–M10, L8 and the named catalogue review). S8's full text was not available in the repository or on the PR,
so items L1–L7 and L9–L10, whose wording this session did not have, are addressed by a self-audit of comparable
low-severity defects (section 3); they may not match S8's own list item for item.

Nothing here changes a protected path, a protocol, a pre-registration, a statistical threshold, a promotion control or
a workflow. Equity research on real data and every promotion remain disabled.

## 1. Findings and fixes

| id | finding | fix | regression test |
|---|---|---|---|
| H1 | `pit_bridge.prices_to_pit` made a delisting return available on the session after the last trade, before the proceeds were known | `ReturnSeries.known` (knowledge day per return; `DelistingReturn.known_from` for the delisting return); the bridge sets availability to the running maximum of `known`; an assumed delisting value marks the store `reconstructed` | `test_s8_h1_*` (pit): intermediate reads on 2006-07-03, -10 and -19 end at the last traded close; the −35% appears on 2006-07-20 |
| H2 | a training-eligible analogue whose outcome was missing was silently dropped (survivorship) | `MissingOutcomeError` when an outcome should be observable (window end + `outcome_grace_days` ≤ T); not-yet-due outcomes excluded as `not_yet_observable`; outcome windows must match the horizon; baselines share the rule | `test_s8_h2_*` (analogues) |
| H3 | documents claimed the equity scope gate was integrated into Manhattan's pipeline | wording corrected everywhere: the research and promotion gates are local to this package; `scope_status` reports `enforced_in_protected_pipeline: False`; pipeline enforcement is recorded as an owner decision (PROTOCOL_EXTENSION_PROPOSAL §3); new `EQUITY_RESEARCH_APPROVED = False` refuses non-synthetic research | `test_s8_h3_*` (governance) |
| H4 | tests built `pit.Window(...)` directly, which PR #86 forbids; no line between primitives and data access | every read goes through `pit.Reader(...).window(...)`; new `research` module holds the only entry points that read dated data (gate, Reader, reads as of the boundary); primitives documented as array-in functions | `test_s8_h4_*` (an AST check that no equities module or test constructs a `Window`; an entry-point test including a refused reserve read) |
| M1 | a pair whose leg stopped trading was reported stable on the remaining observations | `missing_profile`; formation: `insufficient_data` above `max_missing_frac` or `max_gap_sessions`; evaluation: flags for a leg that stops trading, missing sessions and discontinuities | `test_s8_m1_*` (pairs) |
| M2 | the declared one-session embargo was not enforced | `PairRules.embargo_sessions ≥ 1`; `PairDiscovery` and `out_of_sample` count sessions strictly between the windows and refuse otherwise | `test_s8_m2_*` |
| M3 | break classification read as predictive performance | `StabilityReport.kind = "retrospective"`, `usable_from` = window end; docs restate the synthetic rates as retrospective classifications on one generator | `test_s8_m3_*` |
| L8 | pairs attempted were not counted | `PairDiscovery.attempts` and `attempt_log` (considered, no link, insufficient data, rejected, passed) | `test_s8_l8_*` |
| — | adversarial cases requested | delayed breaks (segment checks, `n_eval_segments`), slower mean reversion, missing observations, delisting legs | `test_s8_adversarial_*`, `test_s8_m1_*` |
| M4 | knowledge-time defaults (security, ticker, classification `known_from` defaulted to the effective date); capture provenance lost | `known_from` required (no default) for `Security`, `TickerInterval` (plus `end_known_from` for an ended ticker) and `Classification`; facts without capture times mark the PIT export `reconstructed`; `coverage_verified` needs `coverage_evidence` | `test_s8_m4_*` |
| M5 | a relationship's end was applied before its termination was disclosed | `Relationship.termination_known_from` (required with `valid_to`); an end not yet known is not applied | `test_s8_m5_*` |
| M6 | market cap used share counts not adjusted for later splits | `PriceBook.add_share_count`, `shares_outstanding`, `split_factor`; `universe.split_adjusted_shares` adjusts reported counts for splits after publication and refuses a split between period end and filing (ambiguous under ASC 260); used by the universe and valuation exposures | `test_s8_m6_*` |
| M7 | a genuine −50% crash was refused as a missing split, removing crashed stocks | share-count evidence: unchanged shares → genuine move (kept, `genuine_moves`); shares changed by the ratio → missing split; no evidence → `SuspectedSplitError`, which the universe reports as a data hold (`Snapshot.holds`) instead of a silent drop | `test_s8_m7_*` |
| M8 | effective bets of a hedged pair reported ≈200 | `effective_bets` refused for books with shorts; `hedged_book_risk` (book vs legs volatility, netted share, top-component share) | `test_s8_m8_*` |
| M9 | integration Protocols matched any object with methods of the right names, and matched neither #86 nor #84 | `integration.EXPECTED`: exact signatures from the inspected heads (#86 `8615c69`, #84 `178c5bd`), checked by parameter names and kinds; `absent` on main, `match` required once merged | `test_s8_m9_*` |
| M10 | optimistic cost defaults; unsupported coverage claims | `EquityCostModel` has no defaults and needs a `reference`; DATA_ACQUISITION wording marks every vendor and EDGAR coverage statement as unverified | `test_s8_m10_*`, `test_s8_m4_*` |
| catalogue | overlapping families | 25 entries marked as members of 8 shared hypothesis families (`shared_family`), ids kept; data tier per family (`catalogue.data_tier`): 12 on prices and EDGAR, 2 also needing EDGAR text, 25 needing unavailable history | `test_s8_catalogue_*` |

## 2. Counterexamples, before (`477ba18`) and after

Produced by one script run against both trees (the "before" run used the audited code).

| id | before | after |
|---|---|---|
| H1 | read on 2006-07-10 shows period 2006-07-03 with −0.350 (proceeds known 2006-07-20) | read on 2006-07-10 ends at 2006-06-30; the −0.350 appears from 2006-07-20 |
| H2 | C5 (no outcome, observable since 2009) silently dropped; training set empty | `MissingOutcomeError` naming C5 |
| H3 | DESIGN said the gate was "twice gated" in the pipeline | the claim is gone; the docs say the gates are local and not integrated |
| H4 | 3 direct `Window(...)` constructions in tests | 0 (AST test) |
| M1 | leg Y stops after observation 620: `stable=True`, `flags=()` | `stable=False`: leg stops trading, 130 sessions missing, discontinuity |
| M2 | zero-session embargo accepted | `TemporalError` |
| M3 | report had no retrospective label | `kind="retrospective"`, `usable_from` = window end |
| L8 | no attempt count | `{'considered': 3, 'rejected': 1, 'passed': 2, ...}` |
| M4 | `known_from` defaulted to the listing date; fact without capture exported as non-reconstructed | `TypeError` (required); export marked reconstructed |
| M5 | edge ended 2006-06-30 (end disclosed 2007-01-15) absent from the 2006-09-01 view | present until 2007-01-15 |
| M6 | market cap 626m → 314m across the 2:1 split | 626m → 628m |
| M7 | genuine −50% raises "matches a split" | with unchanged share counts: a −50% return (`genuine_moves`); without share evidence: `SuspectedSplitError` and a universe hold, not a silent drop |
| M8 | hedged pair: 200.6 "effective bets" | refused; `hedged_book_risk` reports one spread |
| M9 | a start/finish fake accepted as attempt accounting | exact check: mismatch against #86's `register_evaluation` |
| M10 | `EquityCostModel()` gave 5 bp spread, 0.1 impact; unsupported `coverage_verified=True` accepted | `TypeError` (no defaults); `ContractError` without `coverage_evidence` |

## 3. Self-audit lows (in place of L1–L7, L9–L10, whose text was not available)

- **Time zones.** Without a tz database `sessions._zone` silently used a fixed EST offset (an hour off in summer):
  now `TemporalError`.
- **Provenance.** `code_version` accepted free text; now a 7–40 character git commit. `ResearchRecord.ref` must be a
  SHA-256.
- **Catalogue performance filter.** Also catches information ratios, t-statistics and "earned N".
- **Ticker end disclosure.** An ended ticker interval needs `end_known_from`; `resolve` applies the end only once it
  was public (the same hazard as M5, for identity).

## 4. Remaining owner decisions and limits

- Scope enforcement in the protected pipeline (promotion, evaluation, runner) for out-of-scope domains.
- Approval of an equities protocol extension (`EQUITY_RESEARCH_APPROVED`, `EQUITY_COVERING_PROTOCOLS`).
- Data purchases; the families that need unavailable history (25) wait for forward collection or a data decision.
- Adapters to #86 and #84 are written after they merge; the pinned interfaces are checked then.
- The pair filter has low power for slow reversion; unresolved split-like moves bias the universe until reviewed.
