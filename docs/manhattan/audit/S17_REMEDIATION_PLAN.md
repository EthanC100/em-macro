# S17: remediation plan, D-1 change specification and First Light acceptance criteria

Session S17, 2026-11-22. Baseline: [S17_COMPREHENSIVE_AUDIT.md](S17_COMPREHENSIVE_AUDIT.md) (main `2577f25`), and the
finding ids C1-C18 used there.

**Status: a plan. Nothing here is implemented, assigned, decided or activated.**

- Standing prohibitions until Ethan approves in writing:
  - historical-data testing;
  - reserve, claims and forward testing;
  - live or paper trading and autonomous orchestration;
  - protected settings and paths;
  - merges, purchases, and real-data experiments.
- "Owner" below means Ethan. "Agent" means a build session that would work on its own branch, open a draft PR into
  main and stop.

---

## 1. Two sequencing constraints found while planning

**K1. `manhattan/ledger.py` is inside the simulation's HB code hash.**

- `CODE_FILES_V2_HB` in `manhattan/sim/run.py:63` lists `manhattan/ledger.py`.
- Every ledger fix (#104, C4, C6) therefore changes the HB v2 code identity. HB records computed before the fix
  become "other code", the situation PR #83's D1 is about (about 520 CPU-hours to rerun).
- **Rule:** land every `ledger.py` change *before* the HB rerun. Alternatively, the owner adopts PR #83's "code
  scheme 2" (a function-level manifest) for future runs first.
- `manhattan/stats/screening.py`, `spa.py`, `elond.py` and the other files in `CODE_FILES` must **not** be edited by
  any fix below. A test pins their hashes (task D1-T7).

**K2. Protocol v3.1 defines the screening unit as "a blind-channel family in its batch".**

- `n_b` is "fixed at freeze by the blind template" (§4, lines 68, 207, 303). Counting scientific classes instead
  changes the protocol's unit.
- §3 therefore gives a design that is **compliant with v3.1 as written** (Option A: classes enforced at freeze),
  and the alternative that **needs a new protocol version** (Option B).

---

## 2. Remediation plan for C1-C18

### 2.1 Classification

| class | meaning | findings |
|---|---|---|
| **SV**: scientific-validity blocker | lets a result look valid when it is not | C1, C2, C10, C11, C12, C13 |
| **LI**: ledger-integrity blocker | the census or evidence record can be lost, edited or forked | C3, C4, C5, C6, C8, plus the ops `Store` separator (C3b) |
| **SEC**: security / fail-open | a guard can be opened by input, configuration or caller assertion | C7, C9, C17, C18, plus the `data_end` cap (C7b) |
| **NB**: non-blocking improvement | correctness or portability without validity impact | C14, C15, C16 |

### 2.2 Tasks

**Complexity:** S ≤ 1 agent-day, M 2-4 days, L 1-2 weeks, each including tests and an independent review.

**Gate:** what the task blocks. FL = First Light, RS = any reserve or screening use, ACT = any bridge or HTE
activation.

| id | finding | class | change | owner | depends on | complexity | gate | acceptance test (each must fail before the fix and pass after) |
|---|---|---|---|---|---|---|---|---|
| **R1** | C3 | LI | land PR #104 (rebase on main, CI on the new head) | S11; independent reviewer; **owner merges** | owner approval | S | FL | the 24 tests of `test_manhattan_ledger_line_separators.py`; full suite green |
| **R2** | C3b | LI | ops `Store` and the reconciler's store pass: write the 3 characters escaped (`store.py:319, 338`), with a shared helper from `ledger.record_line` | S15 | R1 | S | FL (if the ops store is used) | a `Store` chain with U+2028 in a payload reopens, verifies and reconciles (`attempts.py:659`) |
| **R3** | C4 | LI | on read: key set equals `FIELDS ∪ {hash}`; line equals `record_line(rec)`; duplicate JSON keys refused (`object_pairs_hook`) | S11 | R1 (the canonical form is `record_line`) | S | FL | the S17 reproduction (injected `p_value` plus duplicate `payload`) is refused by `verify`, `Ledger()` and `PublicIndex()`; every existing ledger fixture still verifies |
| **R4** | C6 | LI | `fcntl.flock` around re-reading the head plus the append in `Ledger._append`; refuse a stale in-memory head; one programme ledger path (A-2) | S11 | R3 (same file; serialize) | M | FL | a two-process append test leaves a linear chain with 0 forks over 1,000 interleaved appends; a stale handle raises instead of forking; macOS CI job (`flock` on APFS) |
| **R5** | C5 | LI | anchor at run close: `(ledger id, records, head, UTC)` written outside the ledger's custody; `reconcile` reports `independently_anchored: True` only when the external anchor verifies | S11 (library); S15 (run-close step) | **owner decision D-7** (where anchors live); R4 | M | FL, RS | truncating the last k records of a copy is detected for every k ≥ 1; a hash-valid rewrite is detected; a missing anchor gives `independently_anchored: False` and blocks screening |
| **R6** | C8 | LI | bridge `begin`/`complete`/`abandon` hold the workspace lock throughout; an intent record precedes the ledger writes; resume calls `recover_torn_tail`; orphans reconcile to an explicit terminal | S11 | R4 | M | ACT | the three S17 reproductions (concurrent `begin`; torn tail then resume; crash at the 7th registration) end `consistent: True` with the attempt count equal to the real attempts; plus tests for the 8 uncovered violation codes |
| **R7** | C7 | SEC | land PR #105 | S11; reviewer; **owner merges** | owner approval | S | RS | the 125 tests of `test_manhattan_fence_config.py`; full suite green |
| **R8** | C7b | SEC | `validate` and `from_config` refuse `exploration.data_end` later than 2019-12-31 (or main's `config/night.yaml` cap) and a reserve window starting on or before `data_end` | S11 | R7; **owner approval** (it touches the rule-4 boundary's encoding) | S | FL | `data_end: "2025-12-31"` is refused by both; main's config still validates |
| **R9** | C2 | SV | freeze verification: verify the OpenTimestamps proof (not file existence); pin the owner's signing-key fingerprint; `tag_is_signed` injectable only through a test-only seam | S16 (freeze.py is shared: coordinate with `ops/freeze_pr.py`) | owner provides the fingerprint (item 4) | M | FL, RS | a batch with `b"not a proof"` as `.ots` is refused; a tag signed by another trusted key is refused; the owner's key passes in a fixture |
| **R10** | C1 | SV | the equities holdout goes through `access.register_evaluation` with a designated reserve attempt in the persistent ledger; remove `_ISSUED`/`_HOLDOUT_READ`; check the locked lookback is in the grid; make `_issue` and `mark_synthetic` non-public | S16 | R4 (lock); R7 (fence) | L | RS (and FL if the experiment is an equity one) | the S17 two-process reproduction gets one read and one refusal; a forged `SelectionLock` (lookback not in the grid) is refused; a 2023-2026 holdout is refused by the main fence |
| **R11** | C10 | SV | `experiment_spec` refuses a family whose declared signal or sign has no matching executable signal; add the sector-neutral grid dimension (NT-3) | S16 | none | M | FL (equity), RS | NT-V01, NT-Q01, NT-R01 and NT-L01 with the momentum signal are refused; a sector-neutral variant is expressible and counted |
| **R12** | C11 | SV | HTE registry enforces `spec.MAX_GRID` per hypothesis; workloads re-specified as declared families | S14 | none | S | ACT | a 201-point grid is refused at registration; HTE benchmarks re-run within the cap |
| **R13** | C12 | SV | bind HTE stage 3 to the lag-1 execution bridge (#97) behind its switch | S14 | R12 | L | ACT | S16 probe `adapter:hte->delayed-execution` present; S10's F8 test shows no same-close fill; the planted effect is still recovered at lag 1 |
| **R14** | C13 | SV | exploration evaluations write a start before computing and the variant log in the same transaction, so a crash leaves a visible unfinished attempt | S11 | **owner decision D-10** (registering exploration changes PR #86's open-exploration contract); R4 | M | FL | kill the process between start and completion: `unfinished` is visible in the census; the variant log and ledger agree |
| **R15** | C9 | SEC | `RunnerToken` mintable only by the runner entry point (capability object); `register_evaluation` refuses an unpinned fence for protected roles; the reserve path calls `freeze.verify_frozen` | S11 | R9, R7 | M | RS | a caller-constructed token is refused; a self-built fence on a reserve attempt fails reconciliation; an unfrozen spec cannot start a reserve attempt |
| **R16** | C17 | SEC | add `ledger.py`, `roles.py`, `access.py`, `attempts.py`, `freeze.py`, `evidence.py` and their tests to the CODEOWNERS protected block and `nightshift/protected.py` | **owner** (protected file) | none | S | RS | `python -m nightshift.protected manhattan/ledger.py` prints PROTECTED |
| **R17** | C18 | SEC | `approval_ref` must name an existing owner record (issue or PR number, or a signed decision file); drop `ENABLED = True` from the bench script, or extend the capability scan to `scripts/` | S11 | none | S | ACT | `approval_ref="anything"` is refused; the scan flags `scripts/hte_accounting_bench.py` |
| **R18** | C14 | NB | `technology_share` is computed from the track taxonomy (`tracks`/`sectors`), not the legacy label | S16 | none | S | — | a banks plus utilities book reports 0.0; a mixed book reports its true share |
| **R19** | C15 | NB | macOS: `fcntl.F_GETPATH` in `explore_sandbox` (**protected path: owner merges**); `F_FULLFSYNC` on darwin in ledger appends (in R4); canonical NaN before hashing (`pit.py:248`, `backtest.py:133`); BLAS identity off `/proc` on darwin | S15 | R4 (fsync part) | M | FL (if First Light runs on the iMac) | the `orchestra-macos` job extended with the explorer-sandbox and hashing tests; a NaN from x86 and from arm64 hashes equal |
| **R20** | C16 | NB | `check_read` refuses `datetime` (only `date`) before any allocation | S11 | none | S | — | passing a `datetime` raises `TypeError` in < 1 s |
| **R21** | G7, G8 | NB | S16 gate binds the merged #98 bridge; stale probe and documentation text corrected | S16 | none | S | — | the gate reports #98's tests under an `ACC86` id; no probe says "PR #86 not merged" |

### 2.3 Dependency graph and parallel lanes

```
owner: approve #104/#105 ─┬─ R1 ── R3 ── R4 ──┬── R5 (needs D-7) ── FL
                          │          │        ├── R6 (bridge)
                          │          │        ├── R10 (equities holdout)
                          │          │        └── R14 (needs D-10) ── FL
                          │          └ R2 (ops store)
                          └─ R7 ── R8 (owner OK) ── FL
                                │
owner: signing key ── R9 ───────┴── R15 (reserve path) ── RS
R11, R12 → R13, R16 (owner), R17, R18, R19, R20, R21: independent
HB rerun (PR #83 D1) only AFTER R1, R3, R4 land (K1)
```

**Independent lanes** (no shared files; can run concurrently):

| lane | agent | tasks, in order | files |
|---|---|---|---|
| A: ledger core | **S11** | R1 → R3 → R4 → R5 → R14; then R6, R7 → R8, R15, R17, R20 | `ledger.py`, `attempts.py`, `access.py`, `roles.py`, `config.py`, `hte_accounting/` |
| B: equities and freeze | **S16** | R11, R18, R21 now; R9 once the fingerprint exists; R10 after R4 lands | `equities/`, `freeze.py`, `tests/acceptance/` |
| C: HTE | **S14** | R12 → R13 | `hte/registry.py`, `hte/kernels.py`, `hte_execution_bridge/` |
| D: ops and macOS | **S15** | R2 (after R1); R19; R5's run-close step | `ops/store.py`, `nightshift/explore_sandbox.py` (owner merges), `orchestra/` |
| E: D-1 classes | **S13** | §3 (D1-T1..T7), after the owner chooses A or B | new `manhattan/accounting/`; `freeze.py` touch coordinated with lane B |
| F: data path | **S12** | §4 FL-2 prerequisites: a synthetic `DataContract` → `PitStore` → HTE and engine windows (A-3(b)) | `marketdata/`, `engine/pit.py` read side |
| G: review | **new independent reviewer** | reviews every PR in lanes A-F given the code only; reproduces each acceptance test | none |

**Conflict rules:**

- Only lane A edits `ledger.py`, `access.py` and `roles.py`.
- `freeze.py` is lane B's. Lane E proposes its change to lane B.
- No lane edits `manhattan/stats/` or `manhattan/sim/` (K1, K2).

**Critical path to First Light:** owner approvals (#104, #105, D-7, D-10, R8, signing key) → R1 → R3 → R4 → R5
and R14. That is about 3-4 weeks of lane-A work, with lanes B, D, E and F in parallel.

---

## 3. D-1: the exact changes for a layered scientific-class denominator (specification only)

**Not implemented, not recorded.** The decision text, when the owner makes it, would read: "D-1: attempts,
retries and executions are census only; SPA's *m* is every variant ever evaluated on (family, window, role),
failed-after-read included; the screening unit is one scientific class per batch, built by outcome-blind merge
rules M1, M2 and M3 (threshold θ_M3) before freeze."

### 3.1 The choice the owner must make first

> **Correction (2026-11-22).** An independent S13-role review, which S17 reproduced, found that Option A is **not**
> cleanly compliant with v3.1 as written. It strains ARCH §5.1, §5.2 and §6.3 and v3.1 l.303 and l.1203. The two
> options are statistically identical given the same representative rule. The review recommends Option B with six
> anti-gaming rules; see [S17_NEXT_PRS.md](S17_NEXT_PRS.md) §3. The table below is kept as first written.

| | Option A: classes enforced at freeze (recommended) | Option B: count classes in the procedure |
|---|---|---|
| idea | the freeze refuses a batch that holds two families of one class. A family whose class already appeared in an earlier batch is registered **outside the blind channel**: recorded, weight 0, it inherits that class's decision. So "one blind-channel family per batch" in v3.1 *is* "one class" | families stay the unit in storage; a class-level vector of p- or e-values is built from the first unit of each class and fed to the procedure |
| protocol | **compliant with v3.1 as written** (§4: the unit is a blind-channel family; `n_b` fixed at freeze) | **needs Protocol 3.2** (the unit changes from family to class) and a SIM_PREREG amendment with duplication scenarios (S13 blocker 9) |
| simulation validity | the validated procedure is applied to exactly the unit it was validated on | the procedure's validation assumed family units; class units need new scenarios |
| cost | merge rules plus freeze checks | the same, plus protocol, pre-registration and simulation work |

### 3.2 Changes (Option A; the deltas for Option B are marked)

| # | file | change |
|---|---|---|
| D1-1 | **new** `manhattan/accounting/classes.py` (outside every `CODE_FILES*` hash) | `m1_key(family, hypotheses)`: digest of the declared economics (signal definition, universe, data sources, sign), with prose excluded. `m2_key(positions)`: hash of bit-identical family-portfolio positions on the exploration window. `m3_pairs(positions_by_family, theta)`: pairs with position correlation ≥ θ_M3. Signatures take **positions only, never returns**. Merging reuses `methodology.identity.merge_classes` (union-find; class id = smallest family id). **Never merges across opposite signs**: a mirror pair is flagged, two classes. `theta=None` raises `OwnerDecisionRequired` |
| D1-2 | `manhattan/freeze.py` (lane B applies it) | `prepare(..., classes=...)` writes `manifest["scientific_classes"] = {family_id: class_id}`, `class_keys`, `theta_m3`, `class_method_version`, and `inherits = {family_id: earlier_class_id}` for families joining a class from an earlier batch. All of it sits inside the hashed manifest. **Option A:** `prepare` refuses two blind-channel families with one class, and moves inheritors to channel `inherited` (outside the blind channel, weight 0). `verify_frozen` checks the class map reproduces from the stored keys |
| D1-3 | **new** `manhattan/accounting/denominator.py` | `layered(records, manifests, window, role)` returns `m_by_family` (distinct variants with a completed or failed-after-read look on the window, from the census), `n_b_by_batch` (blind-channel families, which under A equal classes), `inheritors`, `violations`. It refuses unless every family has a frozen class assignment, the census is balanced (0 unfinished), and, for screening only, `independently_anchored` is True (R5). Built on `methodology.identity.census` semantics |
| D1-4 | **new** `manhattan/accounting/screening_inputs.py` | `spa_columns(census, family, window)`: the variant set SPA must receive. `spa_test` is refused unless the columns match the census count. A failed-after-read variant is retried under the same identity first, otherwise the statistic is descriptive. `class_vector(batch, stats_by_family)`: the p-values or e-values in freeze order. Failed-after-read gives p = 1 or e = 0. **Option B only:** first unit per class, with inheritance applied after `step` |
| D1-5 | `manhattan/hte_accounting/policy.py` | `D1_ALTERNATIVES` gains `"layered_s13"`. `BridgePolicy` gains `theta_m3: float \| None`. `denominator(report, policy, classes=None)` returns `{"rule": "layered_s13", "m_unit": "variants", "nb_unit": "scientific_classes", "by_window_role": ...}` and refuses `layered_s13` without a class map. The single units stay for reporting |
| D1-6 | `manhattan/hte_accounting/crosscheck.py` | when given a class map, `units` adds `"scientific_classes"` and `"families_merged"` (reporting only) |
| D1-7 | `config/manhattan.yaml` + `config.py` validate (**protected: owner edits**) | `classes: {theta_m3: null, method_version: 1}`. `null` means screening is refused (fail closed) |
| D1-8 | `docs/manhattan/hte_accounting/DECISIONS.md`, `BINDING_ACCOUNTING.md` | after the decision: the D-1 row records the rule, option and `approval_ref` |
| **not changed** | `manhattan/stats/*`, `manhattan/sim/*`, `ledger.py` `IDENTITY_FIELDS` | the class is joined from frozen manifests at reconcile time, so the attempt identity and PR #86's contract stay unchanged. Every simulation code hash stays unchanged (K1, K2) |

### 3.3 Acceptance tests for D-1 (S13's A2, made concrete)

| test | pass |
|---|---|
| D1-T1, planted duplicates | ≥ 99% of exact (M1) and behavioural (M2) duplicates merged; 0 merges across opposite signs; class FDR within the no-duplicate value + 2 SE in every S13 E4 scenario (rerun from its seed) |
| D1-T2, outcome-blindness | the class map is identical when returns are permuted or sign-flipped with positions fixed; the functions have no parameter that accepts returns (signature test) |
| D1-T3, determinism and order | the same classes for any submission order and on two machines |
| D1-T4, frozen at freeze | editing `scientific_classes` after freeze fails `verify_frozen`; a class map that does not reproduce from the stored keys fails |
| D1-T5, cross-batch | under Option A, a later family of an existing class is channel `inherited`, outside `n_b`, and inherits the decision; under Option B, it enters no denominator and earns no reward |
| D1-T6, failures | a failed-after-read family stays in `n_b` with p = 1 (e = 0); a failed-after-read variant stays in *m* |
| D1-T7, hashes pinned | the SHA-256 of every file in `CODE_FILES`, `CODE_FILES_HB`, `CODE_FILES_V2` and `CODE_FILES_V2_HB` is unchanged by the D-1 work |

**Owner inputs:** Option A or B; θ_M3 (S13 used 0.9 for illustration); approval of the M1 key's field list.

---

## 4. First Light: measurable acceptance criteria

**Definition.** One owner-pre-registered experiment.

- **Data:** one dataset, every read on or before 2019-12-31, role `exploration`, weight 0.
- **Path:** run end to end through frozen spec → PR #86 attempt → PIT reads → `engine.evaluate` → anchored ledger
  → deterministic report.
- **Claim:** none.

**Preconditions (owner, in writing):**

- the pre-registration filed by Ethan (rule 4);
- data and licence authorization;
- the decisions D-7 and D-10;
- approval of R1, R7 and R8;
- the signing key and timestamp client (item 4) if R9 is used.

| id | criterion | measured by | pass |
|---|---|---|---|
| **FL-1, pre-registration first** | spec, grid (≤ 200), predicted sign, rejection rule, cost model, lag ≥ 1, windows, class id: frozen before any read | `freeze.verify_frozen` with R9 (a real OTS proof, the owner's pinned key); the ledger's `batch_freeze` timestamp; the OTS attestation time | OTS and tag verify; the freeze precedes the first `evaluation_started` by ≥ 1 record and in time; manifest hash = the hash in the filed pre-registration |
| **FL-2, data identity and fence** | the dataset is under a `DataContract` with `coverage_verified` and named evidence; content hash recorded; loaded into a `PitStore`; every read through `check_read` | the access log; a deliberate probe read of 2020-01-02 inside the run | 100% of reads metered; the probe raises `AccessError` and is logged; the data hash in every completion equals the contract's hash; no licensed row in the public repository (rule 7 scan) |
| **FL-3, complete attempt accounting** | every variant evaluation registered before computing (R14 or bound attempts) | `attempts.reconcile` (strict) plus `methodology.identity.census` | registered = completed + failed + aborted; 0 unfinished; 0 reconciler violations; distinct variants evaluated = grid size; failed-after-read retained; a fault-injected kill mid-run leaves a visible `unfinished` that the retry supersedes |
| **FL-4, ledger integrity** | R1, R3, R4 and R5 are merged | `verify` with the external anchor; tamper drills on a copy | `independently_anchored: True`; the anchor is written before any result is read or published; on the copy, truncation by 1, a record edit, an injected outcome key and a duplicate key are each detected; a two-writer drill leaves no fork |
| **FL-5, reproducibility** | a rerun from the git tag plus the dataset hash on a second machine or clean container | the result hash per computation; `rerun` records | 100% of `result_hash` identical on the same platform; across x86 and arm64 identical after R19, or the differences recorded as nondeterminism and the run marked descriptive; environment digests recorded |
| **FL-6, evidence path and report** | report generated from the ledger plus the anchor only | two report builds; outcome-key scan of the public index | the two builds are byte-identical; the report lists attempts, looks, variants and classes with every variant's result, including negatives; evidence class `exploration`/`E_DESCRIPTIVE`, weight 0; 0 outcome keys in any public artefact |
| **FL-7, nothing else switched on** | config and workflow state during and after | `python -m manhattan.config check`; the Actions run list | `reserve.enabled`, `claims.enabled` and `real_money` all false; 0 writer workflows dispatched by a session; S16 gate extended with FL-1..FL-6 tests, all passing |
| **FL-8, independent reproduction** | the reviewer reruns from the tag | the reviewer's report | bit-identical numbers (FL-5 rule) and identical census |
| **FL-9, failure handling** | any FL criterion fails | ledger and report | the failed run is kept and counted as a look; a re-run is a new attempt under the same identity; nothing is deleted |

**Suggested experiment** (owner's choice, not a recommendation to run): family 2 (commodity hedging pressure, CFTC
COT plus futures settlements to 2019) or family 1 (Treasury carry). Each uses one dataset, a small grid and
public positioning data.

---

## 5. Execution plan (weeks from the owner's go-ahead)

| week | owner | agents (lanes) | exit check |
|---|---|---|---|
| 1 | approve R1 and R7 merges; decide D-7 (anchor custody) and PR #83 D1 (code scheme, given K1); choose D-1 Option A or B; R16 CODEOWNERS | A: R1, R3. B: R11, R18, R21. C: R12. D: R19 (non-protected parts). E: D1-1 draft. F: synthetic `PitStore` loader. G: review #104, #105, R3 | #104 and #105 merged on green CI; R3 merged |
| 2 | decide D-10; approve R8; provide the signing-key fingerprint | A: R4, R8. B: R9. D: R2. E: D1-2..D1-4 with tests D1-T1..T7. F: windows for HTE and engine reads | two-process ledger test green on Linux and macOS CI |
| 3 | choose the First Light dataset and draft the pre-registration (S13 may draft in `docs/prereg_drafts/`) | A: R5, R14. B: R10. C: R13. E: D1-5..D1-6 | anchor drills pass; S16 gate binds #98 |
| 4 | file the pre-registration; authorize the data | A: R6, R15, R17, R20. G: FL dry run on synthetic data | FL-1..FL-9 pass on **synthetic** data |
| 5+ | authorize First Light on real exploration-window data | run First Light; G reproduces | FL-1..FL-9 pass on real data; the HB rerun can start (K1 satisfied) |

**Stays blocked throughout:**

- reserve, claims, forward;
- bridge activation (until R4, R5, R6 and D-10 are done);
- HTE on real data (until A-3(b) and R13);
- the ops-runner schedule;
- any trading.
