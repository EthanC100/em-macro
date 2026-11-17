# Phase 3: point-in-time integrity audit

Engineering verification with synthetic fixtures only. No real dataset is
certified PIT-safe by this audit; no hypothesis, signal or screening rule is
created or evaluated.

## Scope and verified source state

Branch `codex/manhattan-pit-integrity`, based on latest main
`e7f6272b2acd5ffdcc01e37a7a27cb221f9077ca`, the owner's merge of PR #74.
PR #72 and #74 are merged; neither merged PR is edited. Read the complete
`CLAUDE.md`, CODEOWNERS and protection checker before edits, plus the relevant
parts of `ARCHITECTURE.md`, `AUDIT.md`, ops `DESIGN.md`, `RUNNER.md`,
`BLIND_GENERATOR.md`, the Cloud handoff, and the actual data/engine source/tests.
Code, tests and declared interfaces take precedence over historical status prose.

Changed implementation: `manhattan/engine/pit.py`, `manhattan/ops/data.py`, and
a narrow legacy-recapture compatibility guard in `manhattan/ops/runner.py`.
All new cases live in `tests/test_manhattan_pit_integrity.py` and use fabricated
values, at most a few dozen rows/queries, eight fixed arrival permutations and
temporary local storage. No new strategy, generator, collector service or data
download is introduced. Existing strategy/compiler/statistical code is untouched.

## Existing safeguards retained

| Component | Existing behavior verified/reused |
|---|---|
| `engine/pit.py` | Observation period and availability date are separate; one explicit availability or lag is required; availability before period and missing dates are refused; as-of queries select the latest vintage available by the cutoff; window-end clipping prevents later reads |
| `roles.py` / `Reader` | Role fences, embargo, default-disabled reserve, runner-only forward access, blind-generator/critic exclusion and maximum read span. Python APIs are not an OS isolation boundary against arbitrary code; the ops warm-up adapter remains explicitly documented |
| `ops/data.py` | Raw bytes hashed at capture and rehashed before replay; capture written before evaluation; retrieval UTC recorded; first-captured values retained and later differing captures counted as revisions; late/backfilled observations marked reconstructed |
| `ops/store.py` | Immutable keyed records, hash-chain verification, journal/recovery, nonce/provenance records, non-fast-forward retries and complete committed-tree mirror checking. Phase 2 concurrency safeguards remain unchanged |
| Existing tests | Hand-computed vintage/lag examples, role fences, future-input perturbation checks, reconstructed observations, capture ordering, immutable reruns and public-channel leak canaries. These functioning mechanisms were not replaced |

Two modes must not be confused: the engine supports **latest known vintage at a
supplied availability date**, while the ops runner deliberately preserves the
**first captured value** for its forward-recording workflow. First captured is
not proof of first released: startup data may already be revised.

## Confirmed gaps and focused corrections

The first synthetic regression run produced 27 failures and 11 passes against
the original implementation. Passing cases included the existing raw-hash guard
and ordinary revision/as-of behavior. Additional boundary and compatibility
cases were added before the final validation run.

| Gap | Correction and regression |
|---|---|
| Same period/availability with different values was arrival-order dependent; the sorted content hash could describe different as-of answers | Reject conflicting float64 vintages atomically, including signed-zero bit conflicts; exact duplicate vintages are idempotent. Later availability dates remain valid revisions |
| Daily NumPy conversion silently discarded time-of-day; `None`/NaT queries could reach later values through search bounds | Require explicit daily dates for storage/queries and reject missing query dates and unhandled intraday/time-zone inputs. Naive-midnight/date-label arrays remain compatible. Mapping release instants to availability days must be explicit, outside this daily API |
| Simple-path query results exposed mutable views of stored history | Return independent arrays; mutating returned periods, values or availability cannot change the stored content hash or later reads |
| Spec lags were truncated/coerced with `int`, and duplicate source definitions could silently overwrite a lag | Require nonnegative whole-number lags and reject contradictory lag definitions; zero-length queries now return empty and invalid query lengths are refused |
| Capture observation time could be naive and interpreted through the host time zone | Require a zoned datetime at ingestion. Existing zoned-time validation remains in replay. Winter/summer and at-close mappings are exercised synthetically |
| A single capture could contain contradictory same-observation rows or nonfinite values and be treated as complete/revised data | Reject conflicting rows and nonfinite captures before recording. Explicit FRED missing markers still represent gaps; absent data is not invented or forward-filled |
| Raw integrity alone did not check capture/source identity, coverage metadata or current replay configuration | Bind new captures to a versioned declared source/calendar definition; check source/key/provenance consistency, hash shape, byte count, row count and coverage metadata before replay. Configuration drift fails closed |
| First capture at/after close could backdate its current-day value via the warm-up branch | Current-day availability advances to the observed availability day. Existing reconstructed/backfill flags and monitoring-start/evidence treatment remain conservative; older warm-up history is not relabeled as verified PIT history |
| Additive metadata could create a spurious conflict when recapturing identical legacy bytes | Preserve an identical existing legacy capture without rewriting or enriching it; the absence of source-definition provenance remains explicit and unverified |

Timestamp and value bytes in the engine content hash use explicit little-endian
encoding. For valid existing little-endian inputs this preserves the hash layout;
it is not a change to a frozen protocol or a scientific threshold.

## Synthetic coverage matrix

| Requirement | Verification |
|---|---|
| Publication versus observation | Different period/availability dates; observed UTC and market close/DST boundaries; refusal of silent intraday truncation |
| First release versus revision | Hand-specified first vintage and later vintage appear only at their supplied availability dates; ops first-capture policy remains distinct |
| Delayed availability | A delayed row remains invisible before availability; late/reconstructed flags and delayed visibility are checked |
| As-of correctness | Every date in a bounded synthetic timeline is checked against an independent data-only latest-vintage oracle; zero/invalid query lengths and window-end clipping are covered |
| Replay reproducibility | Eight fixed insertion permutations yield identical dataset hashes and query histories; rebuilding the captured-byte fixture yields the same PIT content hash |
| Missing/conflicting timestamps | Missing periods/availability/query dates and missing/naive observed UTC fail; contradictory same-vintage values/source lags fail without partial mutation |
| Version/provenance integrity | Future releases change the dataset version while preserving earlier answers; corrupt raw bytes, inconsistent metadata and source/calendar configuration drift fail; legacy records are not upgraded |
| Future-data leakage | No returned row has availability or period after the cutoff; future revisions do not alter prior answers; missing cutoffs cannot expose the window's later contents. Existing engine perturbation tests remain intact |

These are data queries and integrity checks, not tests of an investment hypothesis.
The broader suite continues to use its existing synthetic engine fixtures; no
designated research evaluation or opt-in real-data reproduction is enabled.

## Limits and real-data integration requirements

1. **No release history was verified.** Official publication instant, observation
   period, vendor vintage, first receipt and ingestion time are different facts.
   A fixed lag on a latest-vintage dataset cannot recover first-release history.
   Existing source adapters and the public factor panel are not certified here.
2. **Daily resolution only.** Subday or timezone-bearing instants require an
   approved calendar/session mapping before entering `PitStore`. It is unsafe to
   strip time-of-day from commodity events, bond auctions or currency fixes.
   Minute/event precision would require a separately reviewed interface/design,
   not a silent conversion in this one.
3. **Backfill remains modeled warm-up history.** Older values may be assigned a
   nominal availability before monitoring began, with reconstructed/backfill flags.
   That does not prove the values were available then. Preserve those labels;
   historical evidence needs independently verified vintages and release times.
4. **Source-definition binding is limited.** New records bind declared source
   parameters and calendar names/time-zone/close/publication settings. They do
   not authenticate the provider, the truth of an asserted timestamp, holiday
   function code or the time-zone database. Pin approved code, source definitions,
   calendar rules and timezone data in an integration manifest. Legacy records
   lacking the new binding remain readable for compatibility, never automatically
   certified or rewritten. Owner review is needed before relying on them.
5. **Hashes prove consistency, not truth.** The PIT content hash identifies
   normalized values/dates, not provider identity or a signed release attestation.
   Capture hashes and ledger provenance complement it. Archive the exact raw
   versions and authenticated manifests, and tie replay to approved code/inputs.
   A complete current archive may have a different hash after future releases
   while earlier as-of answers remain unchanged. This is not a frozen historical
   dataset without a pinned archival version.
6. **Accounting is a separate integration decision.** Existing `Window.final`
   and accounting use marks known at the window end. A vendor revision can
   therefore change a historical return even when signal queries are correctly
   as-of; this is already recorded as R-6 in `OPS_PROGRESS.md`. The ops first-seen
   adapter mitigates this for its own inputs. A future historical integration
   must approve its mark/revision policy; this phase does not change accounting.
7. **No new evidence gate is adopted.** The stated eventual p <= 0.01 screening
   objective, multiple-testing correction and independent confirmation are
   scientific/governance work outside this data-integrity phase. No p-values,
   thresholds, hypothesis families, protocol amendments or performance claims
   are computed/adopted here. Ordinary-session Genesis proposals remain adaptive;
   verified data timing alone cannot make a generating session blind.

Before integration, the owner/Claude must deliver the finalized universe and
data dictionary, contract identifiers/units/roll mappings, official release
history and vintage access, timestamp/time-zone/calendar conventions, missing
and corrected-data policies, authenticated source/version manifests and licence
permissions. Providers advertising data is not proof of that history. Review
the proposed provenance against the existing F01–F10 readiness inventory rather
than filling missing scientific definitions by inference. Private/licensed data,
owner evidence access and live activation require separate authorization.

Workflow pins/lock and the independent baseline remain unadopted candidates.
Schedules, owner switches, protected protocols and live workflows remain unchanged.
No private evidence, licensed dataset, Mac, paid API or live source was accessed.
Validation commands and results are recorded in `CLOUD_VALIDATION.md`.

## Phase 3B correction (2026-11-17)

Fresh branch `codex/manhattan-phase3b-pit` starts at main
`718c1ab371f4d2b957c4a407e99030e8258f13b0` (merged PR #76; #72/#74
are ancestors). This section supersedes the earlier claims about accepted NumPy
precision, lag-only compilation and reconstruction enforcement. Protected
protocols, source datasets, workflow definitions, blinding rules, statistical
methods, schedules and activation switches are unchanged.

### Date precision

`_days` now rejects NumPy Y/M/W/generic units before conversion, including empty
generic arrays, object arrays and mixed-precision scalar lists. It also rejects
multi-day strides such as `datetime64[2D]` and `datetime64[48h]`. Day and finer
units remain valid only at midnight; existing timezone/intraday restrictions
remain. This applies to observation periods, availability and query cutoffs.
Once a caller has already cast away precision before the API call, this API
cannot recover the original precision; adapters must preserve it until validation.

### Source publication contract

`manhattan.availability` supplies one validator used by the ops compiler,
`lags_from_spec` and the source-aware `PitStore.add_source` interface. Every
compiled source needs its own `frequency`, `period_label` and `availability`.
Source observation frequency is independent of strategy rebalance frequency.

- Frequencies: `daily`, `weekly`, `monthly`, `quarterly`, `annual`, `irregular`.
- Labels: `observation_date`, `period_start`, `period_end`, `publication_date`.
  Monthly/quarterly/annual observation labels must explicitly say start or end
  (or declare actual publication-date indexing). No label is itself release proof.
- Every availability declaration needs `kind`, `reference` and `day_mapping`.
  `release_dates` and `release_calendar` require one explicit availability day per
  vintage at ingestion, resolved from the referenced release history/calendar.
  Never use the first release date for a later revision. A publication-date label
  still requires explicit availability and release-to-session mapping.
- `daily_lag` alone permits `publication_lag_days`, only with daily observation
  dates. It documents a timing model, not first-release provenance. The low-level
  `add(..., lag_days=...)` API remains available for existing synthetic/model
  code; it does not validate or certify real source timing.
- `conservative` requires documented `assumption`, `owner_approval` (a reference
  to the approval record), and `release_history_unavailable` (why verified history
  or a release calendar cannot be used). It still requires explicit per-vintage
  availability days. These observations are marked reconstructed. There is no
  automatic month/quarter-start-plus-N calculation or fallback from missing
  release dates to a nominal lag. Verify the referenced owner approval externally
  before supplying real data; arbitrary strings are not authenticated approvals.
- `lags_from_spec` rejects any source that cannot be represented by an explicit
  daily lag contract. Conflicting duplicate definitions and fixed-lag/per-vintage
  mixtures fail closed. Non-daily ingestion must use the explicit-availability
  interface, including under an approved conservative assumption.

Legacy specs remain hashable/readable, with unchanged canonical bytes. The
registry's legacy structural validation is not a PIT certification; executable
compilation/rebuild and `lags_from_spec` reject missing publication contracts.
Only existing **synthetic** mock/capacity fixtures were given new declarations.
No real source, existing frozen batch or generator template was upgraded by
inference. Legacy generator output may consequently fail compilation until its
source contract is supplied through the normal reviewed process.

A fabricated contract (not an approved source or an investment hypothesis):

```json
{
  "name": "fabricated_monthly_observation",
  "frequency": "monthly",
  "period_label": "period_start",
  "availability": {
    "kind": "release_calendar",
    "reference": "synthetic per-vintage calendar fixture",
    "day_mapping": "fixture dates are first usable end-of-day cutoffs"
  }
}
```

Compilation validates declarations; it does not fetch a calendar, verify its
truth, authenticate a provider, or wire new sources into the daily ops source
registry. A real adapter must resolve actual first-release and revision timestamps,
map them to approved session dates and pass them to `add_source`. Current FRED
first-capture and public-panel adapters remain **unqualified for authentic
historical PIT evidence**. Existing daily H.10 replay rules are unchanged.

### Reconstruction at the evidence boundary

Capture replay retains its `late`/`backfill` sets. `FirstSeen.pit_store` now carries
those flags into a monotone, store-wide reconstruction marker. Appending later
rows cannot clear it. Approved conservative assumptions and altered look-ahead
copies also carry the marker. Store-wide scope deliberately includes warm-up
and other potential dependencies, even when the evaluation window excludes them.
It can reject a window that would be safe after a separately reviewed dependency
analysis; no such analysis is inferred here.

`Window.require_historical_evidence` / `PitStore.require_historical_evidence`
is the reusable necessary validation interface. The existing engine evaluator
calls it **before** any reserve backtest. Forward engine evaluations propagate
the marker to the ledger. The ledger records `reconstructed` explicitly and
assigns reconstructed reserve observations zero evidential weight as it already
did for forward observations. The ops forward runner's existing per-observation
late/backfill checks and zero-weight rule remain unchanged.

There is no authenticated real-data historical screening connector today.
`stats/screening.py` and the hierarchical methods consume numeric arrays, not
capture manifests, so they cannot infer provenance. A future connector MUST call
the validation interface before constructing evidence arrays, preserve the
reconstruction marker and ledger weight, and independently verify source/vintage,
calendar/session mapping, owner approvals and dependency provenance. Missing or
legacy provenance must fail that qualification; passing the reconstruction check
alone is **not** proof of authenticity. A direct ledger caller must pass the
reconstruction flag; this Python interface is not a sandbox against arbitrary code
or a caller that strips labels. PIT content hashes still identify values/dates,
not provenance; manifests and ledger records must accompany them. This phase
adds no screening pipeline, thresholds, research evaluation or real-data claim.

### Validation and CI skip correction

Exact commands/results and the independent shallow-history reproduction are in
[CLOUD_VALIDATION.md](CLOUD_VALIDATION.md#phase-3b-final-pit-corrections).
The new data-only tests cover monthly/quarterly irregular releases and revisions,
ambiguous source declarations, compiler/rebuild rejection, precision at all three
date boundaries, reconstruction propagation, ledger weighting and reserve rejection
before evaluation. Synthetic checks establish these code properties only.

## Phase 3C: forward attribution and capture contracts

The generic engine evaluator now rejects forward evaluations on a reconstructed
store before executing or recording anything: its store-wide marker cannot
reliably attribute individual observations. Historical/reserve restrictions and
monotone taint remain intact. The nightly runner continues to use first-seen
per-observation flags for both return endpoints; unrelated reconstructed warm-up
does not zero later genuine forward observations. Late/backfilled endpoints still
receive zero weight. No ledger, hash-chain or blinding rule changes.

Future milestone F MUST evaluate forward evidence using authenticated,
per-observation provenance, rather than applying a store-wide historical
reconstruction flag to unrelated forward observations. That pipeline is not
implemented here; declarations and hashes alone do not authenticate provenance.

Capture registry initialization and capture parsing now use the shared publication
contract validator. Daily synthetic and daily observation-labelled FRED H.10
sources explicitly declare frequency, label, availability kind, reference and day
mapping. Their existing lag and retrieval/close rules remain unchanged. Weekly,
monthly, quarterly and irregular sources cannot use these daily-lag adapters.
Current capture CSV adapters have no explicit per-vintage availability field;
non-daily integration fails closed until such an adapter is reviewed, rather than
treating period labels or fixed lags as release dates. Source declarations do not
prove release-calendar or vendor-timestamp authenticity. Existing bound captures
with older definitions fail configuration comparison; they are not silently
rewritten or upgraded. Legacy captures without definition bindings retain the
previous explicitly unverified compatibility behavior.

The unprotected read-only tests workflow now checks out full history, making
commits a5f9dd4 and 7886867 available to the unchanged historical integrity tests.
No workflow triggers, research schedules or operational activation were added.

Phase 3C validation (Linux x86_64, Python 3.12): targeted PIT/runner/history
suite: 184 passed, 1 skipped (opt-in v1 reproduction), exit 0. Dedicated Q019:
86 passed, exit 0. One complete `python -m pytest -q -rs -p no:cacheprovider`
run with private data paths disabled: 1,839 passed, 131 skipped, 1 failed,
248 warnings, exit 1 (758.03s). The sole failure was the unchanged clean-venv
lock-install test: sandbox network denial prevented downloading certifi.
Rerunning only `tests/test_manhattan_ops_lock_install.py` with package-index
access: 1 passed, exit 0 (8.39s). No unresolved test failures; the full suite
was not rerun. Skips: 125 unavailable private Norgate snapshots, 3 missing
optional numpyro, 1 opt-in slow hierarchical test, 1 opt-in Q009 sweep, 1 opt-in
v1 reproduction. Neither history-dependent test skipped. Warnings were dependency
deprecations and existing numerical/fixture warnings. No optional research
opt-ins were enabled. `pip check`, `git diff --check`, and protected-path
verification of all five changed files passed (exit 0).
