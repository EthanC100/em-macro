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
| H2 | a training-eligible analogue whose outcome was missing was silently dropped (survivorship); the grace rule here is superseded by R1, section 5 | `MissingOutcomeError` when an outcome should be observable (window end + `outcome_grace_days` ≤ T); not-yet-due outcomes excluded as `not_yet_observable`; outcome windows must match the horizon; baselines share the rule | `test_s8_h2_*` (analogues) |
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
| catalogue | overlapping families (superseded by R3, section 5: 10 groups; tiers 13 / 2 / 24) | 25 entries marked as members of 8 shared hypothesis families (`shared_family`), ids kept; data tier per family (`catalogue.data_tier`): 12 on prices and EDGAR, 2 also needing EDGAR text, 25 needing unavailable history | `test_s8_catalogue_*` |

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

## 5. Final review round (reviewed head `f85f90c`)

S8's final review returned REQUEST CHANGES with exact counterexamples, including the low-severity findings the first
round did not have. Section 3's self-audit lows stand; the items below are S8's own.

| id | finding (S8's counterexample) | fix | regression test |
|---|---|---|---|
| R1 case 1 | failures' outcomes recorded but published after the survivors': excluded as `outcome_unobservable`; forecast +0.10 instead of −0.45 | selection by the calendar only: an observation is settled when `as_of + horizon + grace <= T` for every company; a settled observation must have a published outcome or `MissingOutcomeError`; an outcome published beyond the grace is refused when added (`LateOutcomeError`); provisional values (`assumed=True`) are reported by `forecast` | `test_s8_r1_case1_*`, `test_s8_r1_training_*` |
| R1 case 2 | `outcome_grace_days=4000` turned missing failure outcomes into `not_yet_observable` | the grace is a pool-level `OutcomePolicy(grace_days, provenance)`, bounded by `MAX_OUTCOME_GRACE_DAYS = 90`; the per-call argument is gone; training without a policy is refused | `test_s8_r1_case2_*` |
| L1 | split and dividend on one day: −1.00% instead of 0.00% | `r = (h·P_t + c)/P_last − 1` with shares held `h` and cash `c = Σ amount × shares held on its ex-date`; same-day actions in the order splits then cash, so the amount is per post-split share: `k(P + D)` | `test_s8_l1_*` (dividend, split, both, reverse split, reverse split with dividend) |
| L2 | suspension spanning the window start: +4% instead of +6%, `multi_session=False` | returns run from the last traded close, applying every action dated after it (including on non-session days); `multi_session` when any session lies between the two closes | `test_s8_l2_*` |
| L3 | annual report vs fourth quarter | facts keyed by (period end, kind), so an annual and a Q4 ending the same day coexist; `ttm_detail` uses a reported Q4, else derives Q4 = annual − Q1..Q3 (flagged `derived_q4`), never adds an annual to quarters, and reports a Q4/annual disagreement; a kind-less query refuses a tie that differs | `test_s8_l3_*` |
| L4 | EPS consensus near zero: a 1e12 surprise | `abs_floor` (no default, in the metric's units): below it the surprise is undefined (NaN, `defined: False`, with the reason); defined values clipped to `±max_abs` and flagged; the reported value must be a finite number | `test_s8_l4_*` |
| L6 | β = −0.77 built a long/short position from |β| | a non-positive hedge ratio is a formation reason; `position_from_z` refuses it | `test_s8_l6_*` |
| L7 | a second outcome silently replaced the first | a conflicting duplicate raises; an identical one is a no-op | `test_s8_l7_*` |
| M2 | Friday-to-Monday passed a one-session embargo | the embargo is counted on an exchange `calendar` (required by `PairDiscovery` and `out_of_sample`), and every observation day must be a session | `test_s8_m2_friday_*` |
| R2 | contracts pinned to old heads; structure presented as integration | pinned #86 `5aa643f`, #84 `1e86b33` (branch now `e1882be`, same interfaces); added `run_bound`, `verified_fence`, `authorization(config_sha256)`, `issued`, the `manhattan.evidence/3` schema constant and the `attempt={id, store}` metadata shape; results are `structural_match`; `SEMANTIC_REQUIREMENTS` lists what structure cannot show (designated reserve attempts, verified fence, run binding, issued classifications, trusted authorities); `runtime_integration()` is False | `test_s8_r2_*`, `test_s8_m9_*` |
| R3 | catalogue priorities and overlaps | priority led by the affordable data tier; F01's estimates moved to `optional_data` (only the forecast-based variant uses them), so F01 is `prices_and_edgar`; E07/F02 → `SF-FINANCING`, B03/F04 → `SF-SEMI-CYCLE`; shared families documented as declared, not enforced (`shared_family_enforced: False`); all 39 ids and the full denominator kept | `test_s8_r3_*` |
| R4 | estimates without capture times were used as if verified | `Consensus.reconstructed` and `evidence_eligible`; `EstimateBook.reconstructed`; surprises carry the flag | `test_s8_r4_*` |
| R5 / M10 | cost limitations | withholding tax, Reg SHO Rule 201, borrow quantity and recall timing listed as not modelled (costs module and DESIGN §7) | documentation |
| L9 | misleading timestamp docstrings; corporate-action capture | `CorporateAction.captured`; an action applies from max(announced, captured); returns' `known` include it; actions without capture make returns and exports reconstructed; the `date_only` and `known_from` docstrings now say what the code does | `test_s8_l9_*` |
| L10 | runner-lock dependencies | documented (DESIGN §7): scipy, statsmodels and PyYAML are not in the runner lock; the lock is not edited | documentation |
| (found here) | merged with #86 `5aa643f`, #86's own `test_private_access_paths_are_used_only_where_allowed` failed: the equities package named `run_bound` (as a pinned interface) and used an attribute called `_index` | `run_bound` and `forward_window` are no longer pinned or referenced by equities code (#86 restricts them to its runner path; the requirement is documented in prose); `sessions._index` renamed; a local test mirrors #86's private-name list | `test_equities_never_references_86s_private_access_paths`; the combined trees below |

Cross-PR check for this round (scratch worktrees only; nothing merged into this branch): `origin/main` + #86 `5aa643f`
+ #84 `1e86b33` with this package overlaid: 13 structural checks `structural_match`, `runtime_integration()` False,
equities + #86 binding-access + #84 evidence + PIT tests **761 passed**; the same with #84's later head `e1882be`:
**802 passed**.

## 6. Targeted re-review (reviewed head `e6ae852`)

S8's targeted re-review found every earlier defect fixed or failing closed, with one merge blocker (N1) and one
activation blocker (N2).

| id | finding | fix | test |
|---|---|---|---|
| N1 (merge blocker) | the checker pinned #86 `5aa643f`; at #86 `bab1a4d` `authorization` takes `config` (`{"sha256", "commit"}` or None) instead of `config_sha256`, and `verified_fence` returns a `VerifiedFence` capability; in a scratch merge with #86 the equities suite had 1 failure, 204 passes | pins refreshed to #86 `bab1a4d` and #84 `e1882be`; `authorization` pinned with `config`; new structural checks for `verified_fence`'s declared return (`VerifiedFence`) and the capability's public members (`fence`, `config_sha256`, `commit`, `valid()`, `record()`); semantic requirements rewritten (a forward attempt needs the `VerifiedFence`, a plain fence or hash is refused; `authorization` records `config=VerifiedFence.record()`; the reconciler re-verifies it). The checker was not loosened: the old `config_sha256` shape is a test-asserted mismatch. The local mirror of #86's private-name list was refreshed to `bab1a4d` (`_tag`, `_fence_key`, `_FS_CACHE`, ...); no equities module references any of them | `test_s8_n1_*`, `test_equities_never_references_86s_private_access_paths` |
| N2 (activation blocker) | one company's annual and Q4 share counts for the same period end disagree: `fundamentals.value` fails closed for it, and the exception halted the whole universe snapshot | `universe.split_adjusted_shares` and the `required_metrics` check turn that failure into an exclusion of that one security, with the error as its reason; the rest of the universe is still assessed (a trivial, independently tested change at the two call sites) | `test_s8_n2_*` |

**Still open after N2 (documented, not changed in this narrow patch):** `features.valuation_exposure` queries its
numerator metric with `fundamentals.value` directly, so the same kind of conflict in that metric raises for the whole
cross-section instead of giving NaN for one security. It fails closed (no wrong value), and it is an activation
blocker for real data: before any real fundamentals are used, every feature that reads fundamentals should map a
per-security failure to a missing value with a reason, as the universe now does.
