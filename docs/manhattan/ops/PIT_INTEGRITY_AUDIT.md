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
