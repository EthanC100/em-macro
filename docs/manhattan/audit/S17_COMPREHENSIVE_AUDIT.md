# S17: comprehensive audit of Project Manhattan, research readiness and next-phase roadmap

Session S17, 2026-11-21 (night). Branch `claude/manhattan-comprehensive-audit-i7a2ov`, from main at `2577f25`.

**Status: an audit and a set of recommendations. Nothing here is in force and nothing was changed.** No code,
configuration, protected path, ledger, queue file, workflow, branch, issue or pull request was modified. No workflow
was dispatched, no real, licensed, reserve or forward data was read, nothing was bought, and no owner decision was
taken. The only artefact is this file. Every reproduction used synthetic data in a scratch clone outside the
repository.

Labels used throughout:

- **Confirmed**: reproduced on synthetic data, or unambiguous in the code at a cited line.
- **Likely**: strongly suggested by the code, but not reproduced end to end.
- **Possible**: plausible from the code; needs a targeted check.
- **Unverified**: could not be checked from this session; what would settle it is stated.

Seven states are kept apart: **implemented, tested, reviewed, merged, enabled, operational, scientifically
validated.** Nothing in Manhattan is in the last three states.

---

## Deliverable A: executive assessment

### Where Project Manhattan stands

Manhattan is a large body of careful, fail-closed, synthetic-only research infrastructure: about 38,600 lines in
`manhattan/`, 65 `test_manhattan_*` files plus 6 acceptance test files, and CI of 3,937 passed and 166 skipped on the last merge (PR #98, run
`44931299836`). Its defaults are conservative and they work: `reserve.enabled: false`, `claims.enabled: false`,
`real_money: false`, every bridge `ENABLED = False`, and every undecided owner decision raises.

**It cannot yet run one credible historical experiment end to end.** The main reasons:

1. **The components are islands.** None of `marketdata`, `equities`, `execution`, `execution_realism`,
   `hte_accounting`, `hte_execution_bridge`, `factors`, `orchestra` or `tracks` is imported by any other production
   module (import-graph scan, §C.0). They meet only in tests.
2. **The S16 acceptance gate on main says NOT_READY**: 78 PASS, 25 BLOCKED, 0 FAIL. I ran it on `2577f25`.
3. **No validated screening method exists.** The pre-registered simulation run `43467828524` failed (D04h was 32
   replications short). PR #83's analysis of it reads candidate (i) as FAIL (V3 in D07a), candidate (ii) as NOT
   EVALUATED, and "NO SELECTION". `claims.screening_method` is `null`. PR #83 is an unmerged draft, and I did not
   re-derive its numbers.
4. **No data path.** Manhattan has no licensed data it can read: Norgate and Databento adapters are dormant and
   em-macro-data access is ETHAN_ACTIONS item 20. The Norgate licence ends about 5 May 2027.
5. **Evidence-integrity defects in the ledger the whole design rests on** (§C): records can become unopenable;
   unhashed fields, including outcome keys, can be injected after the fact and still verify; there is no
   production anchor and no writer lock; and the equities holdout's "one look" only holds within one process.

### Achieved, verified in code and tests

- **The statistical toolkit is implemented and unit-tested against primary sources**, with page references in
  MANHATTAN_PROGRESS.md: Hansen SPA, Politis-White block length, Li-Ji, Romano-Wolf, BH/e-LOND screening, the betting
  e-process, tiers and dormancy.
- **PR #86 binding attempt accounting** with a hash-chained ledger, scaled by PR #100.
- **The PIT engine.** It reproduced carry and TSMOM against the frozen v1.0 code on public FX, on the exploration
  window only (`results/manhattan_engine/REPRODUCTION.md`, correlation > 0.9998).
- **The HTE throughput engine**, synthetic only, with same-close fills.
- **Futures execution and cost models** (#85, #93).
- **Equity PIT infrastructure** (#87, #103), synthetic only.
- **Orchestration with real-process failure tests**, including on a GitHub macOS runner (#94).
- **The S13 methodology study**: the best quantitative reasoning in the repository.

### Unfinished

- **Simulation:** the full simulation is incomplete, and held-out scenarios H01-H12 are not built.
- **Owner decisions** open: D-1, D-10, B4, A-1 to A-3, D-7, NT-1 to NT-9, PR #83's D0-D8, and ETHAN_ACTIONS items
  1-4, 6-10, 20 and 21.
- **Adapters:** the integration adapters are unbound.
- **The research runner** (milestones F to I) is not started.
- **Hypotheses:** no Manhattan pre-registration exists, and the core factors are not adopted.

### Broken (confirmed defects; all dormant paths, none is exploitable on main today)

| defect | consequence | status of the fix |
|---|---|---|
| A ledger record containing U+2028, U+2029 or U+0085 makes the ledger unopenable | the ledger cannot be audited | fix in draft PR #104, unmerged |
| Unhashed fields and duplicate JSON keys pass `verify` | an outcome key such as `p_value` can be added to a committed public-index line undetected | **no PR** |
| `Fence.from_config` fails open on a quoted `"false"` | the reserve can be switched on by a typo | fix in draft PR #105, unmerged |
| The HTE bridge can leave attempts that can never be closed | a permanently inconsistent census after a concurrent or crashed `begin` | **no PR** |
| The equities holdout guard is in-process only | two processes each read the holdout | **no PR** |
| The equities freeze can be self-certified, and the executed signal need not match the registered family | the hypothesis-first gate can be satisfied without an owner freeze | **no PR** |
| The HTE registry does not enforce `spec.MAX_GRID = 200` | about 51,000 variants per family in the benchmark workload | **no PR** |

### Unverified

- macOS behaviour of the full suite: only the orchestra subset has ever run on a Mac.
- The hardware actually available.
- Whether rulesets are applied (GitHub reports `main` as `protected: false`).
- The real-data behaviour of every adapter.
- PR #83's simulation classifications.
- Vendor prices and coverage.

### Is the research infrastructure scientifically credible?

**As a design: largely yes.** The protocol, the fail-closed posture and the denominator discipline are
better than most institutional practice.

**As a system that could produce a credible result today: no.** The screening method has not passed its own
pre-registered validation. The evidence store has integrity holes at exactly the places an auditor would test. And
no hypothesis has been carried from registration to evaluation through the binding path on real data.

Passing tests show that the synthetic platform behaves as its authors specified. They show nothing about markets or
about statistical validity at scale.

### The single most important next milestone

**"First Light": one owner-pre-registered, exploration-window-only (data to 2019-12-31) experiment, carried end to
end through the binding path.** That means a frozen spec, a PR #86 attempt, PIT reads, an `engine.evaluate`
evaluation, a ledger with an external anchor, and a report with its full denominator. It should come **after** the
ledger-integrity fixes, use one small dataset, and claim nothing.

It turns islands into a pipeline and exposes integration defects while the stakes are zero. It needs owner
authorization for the data and the pre-registration. The reserve and screening claims stay closed until the
screening method passes, which is a separate track.

---

## Deliverable B: GitHub audit

### B.1 Repository state (checked 2026-11-21 ~19:00 UTC)

| item | value |
|---|---|
| working directory | `/home/user/em-macro`, single worktree, clean tree |
| remote | `origin` = `https://github.com/EthanC100/em-macro` |
| local branch | `claude/manhattan-comprehensive-audit-i7a2ov` at `2577f25`, equal to `origin/main` (no divergence) |
| local clone | **shallow** (history grafted at 2026-11-15). Local `git log` on older files is misleading; I used a separate blobless clone and the GitHub API for history |
| GitHub `main` HEAD | `2577f259999b8c6185f024c87a22384b50e930fb` ("Janus quick check 18:17 UTC: no change") |
| other agents' worktrees | none visible in this container; other sessions' branches are listed below |
| tags | `v1.0-frozen`, `v1.1-frozen` only. No `manhattan-sim-confirm-*` tag exists |
| branches | 104 on GitHub: 90 merged into main, 14 not merged |

### B.2 Recent milestones verified

| PR | merged | head → merge | CI | verified |
|---|---|---|---|---|
| #98 HTE → PR #86 attempt bridge | 2026-11-21 18:01Z | `d357b12` → `608ea8c` | run [44931299836](https://github.com/EthanC100/em-macro/actions/runs/44931299836): **3,937 passed, 166 skipped, 20 warnings, 0 failed** (Python 3.12.16, Ubuntu; job log read) | **Confirmed.** `ENABLED = False` (`manhattan/hte_accounting/bridge.py:58`). The PR description describes head `dacff44` and still opens "Draft. Do not merge until verified"; the final fix `d357b12` is not described in it, and I found no independent review of that commit. The only formal review is the owner's COMMENTED review 6005579883 on `59440b4` |
| #103 non-technology equities track | 2026-11-21 16:42Z | `9431592` → `905717a` | run 44923209554 success | **Confirmed** merged and dormant (`tracks.ENABLED = False`). Gate weaknesses in §C |
| #100 indexed ledger | 2026-11-21 13:35Z | `30e467b` | success | Confirmed merged. Rules unchanged as claimed; inherited defects in §C |
| #86 binding attempt accounting | 2026-11-19 | `bab1a4d` | | merged. `hte/LIMITATIONS.md` A2 and the S16 probe text still say "PR #86 not merged" (stale) |

**#98's CI included #103.** Run 44931299836 tested the merge with main at `b844320`, which already contained
`905717a`. Since then main has only Janus bookkeeping commits. My own full-suite run on `2577f25` is in §8.

### B.3 Open pull requests

| PR | state | age | what | assessment |
|---|---|---|---|---|
| [#105](https://github.com/EthanC100/em-macro/pull/105) | draft, CI green (run 44921438603) | 0 d | `Fence.from_config` fails closed (reserve keys and values, duplicate YAML keys) | **Needed.** Defect confirmed on main (§C, C7). 23 commits behind main, but merges cleanly. Independent review in **B.8**: merge-ready after updating to main and re-running CI; follow-up for the `data_end` cap |
| [#104](https://github.com/EthanC100/em-macro/pull/104) | draft, CI green (run 44918443798) | 0 d | ledger writes U+2028, U+2029 and U+0085 as escapes | **Needed.** Defect reproduced on main (§C, C3). 23 behind, but merges cleanly. Independent review in **B.8**: merge-ready after updating to main and re-running CI; the ops `Store` needs a separate fix |
| [#101](https://github.com/EthanC100/em-macro/pull/101) | open, into `dev` | 2 d | Q032: morning-report settlement-clone failures | the night shift's; not Manhattan |
| [#83](https://github.com/EthanC100/em-macro/pull/83) | draft | 3 d | simulation status, `dev_status`, held-out readiness, decisions D0-D8 | **The most important open PR scientifically.** It records that no screening method is selected. 230 commits behind; `docs/manhattan/phase4/` is not on main. Decide D0-D8 (§E) |
| [#77](https://github.com/EthanC100/em-macro/pull/77) | open | 4 d | C14: Janus quick checks hourly | **Stale record.** The schedule change is in effect, but `docs/config_changes.md` (protected) has no C14. The config log is 4 days behind reality |
| [#73](https://github.com/EthanC100/em-macro/pull/73) | open, dev → main | 5 d | night-shift promotion | **Refused** on 2026-11-20 (2 failed tests, missing `yaml` in the site build, ledger rebuild differs). `dev` is 63 ahead and 21 behind main. "Needs Ethan" in the morning report |

No open PR has unresolved review threads. #98, #103 and #104's reviews contain no line comments.

### B.4 Issues

| issue | state | assessment |
|---|---|---|
| [#102](https://github.com/EthanC100/em-macro/issues/102) | open | **Do not close as fully met** (§C, C1 and C10). Its items 1-7 are delivered as *dormant synthetic infrastructure*. Item 5 ("no leakage or double-counting") and NON_TECH_TRACK §6 criterion 12 (hypothesis first) are only partly met: self-certifiable admission, a process-local holdout guard, and an executed signal that can differ from the family. Recommend closing it as "infrastructure delivered" only together with a follow-up issue for those three defects. Owner's call |
| [#41](https://github.com/EthanC100/em-macro/issues/41) `[RESOLVE?] F004` | open since 2026-11-12 | a ledger forecast awaiting resolution; not Manhattan. 9 days old |

### B.5 Workflows (the 300 most recent runs, 2026-11-18 03:39Z to 2026-11-21 18:17Z)

- **Writers on main:** no failures (ledger-pages, ledger-daily, elections, watchdog, systematic, v1-rules-monitor).
- **`tests` on PRs:** 58 success, 5 failure, 9 cancelled.
  - The 5 failures are on `s14-execution-realism`, `cool-fermat` and `hypothesis-engine` (2026-11-19). Each was
    superseded by a green run before its merge.
  - The cancellations come from `cancel-in-progress`.
- **promote-merge:** 24 success, 49 skipped.
- **`manhattan-ops-runner`, `manhattan-sim`:** no run in the window. The last sim runs were `43467828524` (failure)
  and `43467884866` (cancelled), both on 2026-11-13.
- **Coverage gaps:**
  - `tests` runs only on pull requests to main; main itself is never tested after a merge.
  - Only the orchestra subset runs on macOS (`orchestra-macos.yml`).

### B.6 Unmerged branches (14)

| branch | ahead / behind main | assessment |
|---|---|---|
| `claude/ledger-line-separators-gesrcf`, `claude/roles-reserve-key-validation-gesrcf` | 1/23, 4/23 | PRs #104 and #105 |
| `claude/phase4-simulation-readiness` | 3/230 | PR #83 |
| `claude/sharp-sagan-03l39q` | 2/264 | PR #77 |
| `dev`, `night/Q012`, `Q023`, `Q028`, `Q031`, `Q032` | | the night shift's own flow; the Q branches are already reflected in dev or main except Q032 (#101) |
| `claude/epic-mayer-kfhpsh` | 3/423, last 2026-11-13 | "estimand and tail-risk document, benchmark module (work in progress)". **Possibly abandoned**; `test_manhattan_estimand_study.py` and `tailrisk` exist on main, so it is probably superseded. Owner may delete it after a diff check (deletion is the owner's) |
| `claude/systematic-only-if-due` | 2/628, 2026-11-12 | probably abandoned or superseded; check before deleting |
| `build/election-tracker` | 2/1130, 2026-11-04 | probably abandoned |
| `fix/marketdata-private-name-collision` | 3/133 | **squash-merged** as `08495ae` (#99); safe to delete |

The other 90 branches are merged into main. `build/*`, `codex/*`, `prereg/*`, `trial/*` and most `claude/*` are
historical; no action is needed beyond optional clean-up by the owner.

### B.7 Reported but unmerged fixes (task §15)

| fix | where it actually is |
|---|---|
| Unicode ledger escaping | **branch only** (PR #104, draft). The defect is live on main (C3) |
| Fail-closed YAML and role configuration | **branch only** (PR #105, draft). Live on main (C7) |
| Reserve configuration safety | same PR #105. Not on main |
| Owner decision documentation | **on main**: `docs/manhattan/hte_accounting/DECISIONS.md` (via #98). Two more decision sets are on main (`NON_TECH_TRACK.md` §8, `S13_RESEARCH_METHODOLOGY.md` §10). PR #83's D0-D8 are **branch only** |
| Ops `Store` separator defect | named in PR #104's description; **no branch**. **Confirmed (me) at the reader:** a line written as `store.py:319` writes it (`ensure_ascii=False`) holding U+2028 makes `ops.store.read_lines` (`:103`) raise `JSONDecodeError`. The same reader pattern is at `:412` and in `attempts.py:659` (the reconciler's store pass). Needs its own narrow fix; #104 does not cover it |

### B.8 Independent review of PR #104 and PR #105 (requested by the owner during this audit)

Method: both branches were fetched into a scratch clone (branches untouched). Each was merged onto main `2577f25`
alone and then together. I read the diffs line by line, ran the new tests against unpatched main, ran the
regression suites on the combined merge, and probed #105 adversarially. Nothing was pushed, commented or merged.

**Integration with current main.**

- Both branches start from `e194cb0`.
- No commit on main since then touches `manhattan/ledger.py`, `roles.py`, `config.py`, `access.py` or
  `tests/test_manhattan_ledger_scaling.py`.
- #104 alone, #105 alone, and #104 + #105 together all merge **without conflict**.
- The two PRs touch disjoint files.
- On the combined merge, 13 regression suites gave **714 passed, 0 failed** (exit 0):
  - the two new files;
  - `ledger_scaling`, `attempts`, `binding_access`, `ops_attempts`, `engine` and `registry`;
  - `hte_accounting` (#98, merged after the PRs' base);
  - `prereg` and `prereg_v2` (protected);
  - `marketdata` and `ops_e2e`.
- The full suite on the combined merge was **not** run. CI ran on each PR's own head against the older main.
  **Before merging, update each branch to current main and let the `tests` workflow run on it.**

**Regression coverage (fail before, pass after).**

| PR | new tests | on unpatched main | on the PR | PR's own claim |
|---|---|---|---|---|
| #104 | `tests/test_manhattan_ledger_line_separators.py`, 24 | **16 failed, 8 passed** | 24 passed | "15 of the 24 fail". A one-test difference; immaterial, but the description should be corrected |
| #105 | `tests/test_manhattan_fence_config.py`, 125 collected | **74 failed, 51 passed** | all passed (in the 714) | "126 passed". One fewer collected here; immaterial |

**#104 assessment: correct and narrowly scoped. Merge-ready after rebasing, with three non-blocking notes.**

- **Correctness.**
  - `record_line` escapes exactly the three characters that `str.splitlines()` treats as boundaries but JSON leaves
    raw. JSON already escapes the others (all below U+0020), and a test checks the table is complete.
  - It is used at both writer sites (`_index` and `_append`), which `PublicIndex` inherits.
  - The hashes are unchanged, because `record_hash` covers the parsed record.
  - Lines without these characters are byte-identical; PR #100's differential test still requires that.
- **Note 1: it does not fix the ops `Store`.** The same defect there is confirmed at the reader (B.7). Open a
  separate narrow fix; do not widen #104.
- **Note 2: it interacts with C4.** When the line-canonicality check proposed in C4 is added, it must compare
  against `record_line(rec)`, not plain `json.dumps`. Otherwise every escaped line would be flagged.
- **Note 3: it does not recover existing raw-separator ledgers.** They stay unreadable, as the PR intends; its
  option B is an owner-run repair. No tracked JSONL in this repository contains a raw separator (per the PR). The
  private ledgers are unscanned: **unverified**.

**#105 assessment: correct for what it targets. Merge-ready after rebasing.** One adjacent fail-open is not covered
and should be a follow-up, not a reason to hold the PR.

- **Correctness.** My probes on the PR's head:
  - a quoted `"false"` is **refused**;
  - a repeated `enabled:` is **refused** (`DuplicateKeyError`);
  - an integer domain key is **refused**;
  - merge keys still work;
  - `datetime` values and ISO week dates are refused;
  - `access._fence_of` still wraps every error as `AccessError`;
  - `validate` now calls `from_config`, so the two cannot disagree;
  - the protected `test_manhattan_prereg*.py` pass unchanged.
- **Typo domains are a usability problem, not a leak.** With a window only under `fx_dialy` and `enabled: true`,
  a 2021 read of `fx_daily` resolves to **`embargo`**: every date after `exploration.data_end` that no window
  covers is embargoed. So #105's "typos that are valid domain names" follow-up is about a reserve silently not
  existing, not about data leaking. The allowlist is still worth having.
- **Not covered, confirmed (me), pre-existing:** neither `validate` nor `from_config` caps `exploration.data_end`.
  - Changing it to `"2025-12-31"` passes `validate` with no error.
  - A 2021 `fx_daily` read then resolves to **`exploration`** instead of `embargo`.
  - Hard rule 4's 2019-12-31 boundary is enforced for Manhattan only by the value in `config/manhattan.yaml`.
    The file is owner-protected, so this is a defence-in-depth gap, not an agent-reachable path.
  - **Recommended follow-up** (owner's choice, since it touches the rule-4 boundary): refuse a `data_end` later than
    the cap in `config/night.yaml` or 2019-12-31, and refuse a reserve window that starts on or before `data_end`.
- **Other notes.**
  - `manhattan/hte/protected.py` still reads the file with plain `safe_load` (informational only, as the PR says).
  - `validate` imports `roles` inside the function. There is no cycle, but a module-level import would be clearer.

**Whether either needs changes before merging.**

- **Required:** rebase or merge each onto current main, re-run CI on the updated head, and correct the test counts
  in each description.
- **Recommended:** a reviewer other than the author signs off; this section is such a review of the diff, not of
  the authoring session.
- **Neither needs a code change to be merged.** The ops `Store` fix (for #104) and the `data_end` cap with the
  domain allowlist (for #105) belong in follow-ups.
- **Merging is the owner's decision; nothing was merged.**

### B.9 Process observations

1. **No merged Manhattan PR carries an approving review.** Every "independent verification" is an agent's report
   quoted in the PR body. The owner merges.
2. **#98 was merged with a description that was not updated for its final commit.**
3. **Two required-check settings are unconfirmed.**
   - The GitHub branches API reports `main` as `protected: false`.
   - Whether the ruleset in `docs/rulesets/main.json` is applied is ETHAN_ACTIONS item 6, still "unknown".
   - If it is not applied, "tests / pytest" is not a required check, and only convention keeps a red PR from being
     merged. **Unverified**: settle it in the repository settings.

---

## Deliverable C: architecture and security findings

### C.0 Architecture as built

**Status scale:** 1 not implemented, 2 design only, 3 partial, 4 synthetic-tested, 5 integration-tested,
6 historically validated, 7 operationally authorized.

| subsystem | code | status | evidence |
|---|---|---|---|
| hypothesis generation | `generate/`, `ops/mockgen.py`, catalogues (39 tech + 5 non-tech families) | 3 | templates exist; no blind generator (item 3); catalogue families are drafts |
| registration and freezing | `spec.py`, `freeze.py`, `ops/freeze_pr.py`, `equities/registration.py` | 4 | freeze integrity only; the owner signature is injectable (C2); no Manhattan batch has ever been frozen |
| pre-registration of the simulation | `prereg.py`, `prereg_v2.py` | 4, frozen | the hash checks pass (`python -m manhattan.prereg_v2 verify` gives ok) |
| market-data contracts and ingestion | `marketdata/` (S12) | 4 | Norgate and Databento adapters dormant; **imported by nothing** |
| provenance and versioning | `marketdata/vintages`, `equities/provenance`, data hashes | 4 | the public FX panel was refreshed after the reproduction was written (REPRODUCTION.md notes the drift): public data are mutable |
| universe and instrument metadata | `equities/universe.py`, `execution/contracts.py` | 4 | PIT membership, delistings, ticker reuse on synthetic worlds |
| point-in-time information | `engine/pit.py`, `availability.py` | **5 on public FX, exploration only** | the reproduction ran through the access path |
| corporate actions | `equities/prices.py` | 4 | splits, dividends and delisting returns; synthetic only |
| futures rolls and contracts | `execution/` (#85), `hte_execution_bridge/market.py` | 4 | synthetic held-month and roll model |
| selection and model fitting | `stats/`, `hte/` stage 3, `equities/registration.run_selection` | 4 | HTE stage 3 is descriptive; no grid cap (C11) |
| historical evaluation interface | `engine/evaluate.py`, `engine/backtest.py` | 4-5 | the only path that binds reads to attempts |
| holdout access | `roles.py`, `access.py` (persistent); `equities/registration.py` (in-memory) | 4 | **two inconsistent holdout mechanisms** (C1) |
| attempt accounting | `attempts.py`, `ledger.py` (#86, #100) | 4 | defects C3-C6 |
| multiple-testing accounting | `stats/`, `methodology/identity.py`, HTE census | 3 | the counting unit D-1 is undecided; no class merging (S13 blocker 2) |
| evidence storage | `ledger.py` PublicIndex, `ops/store.py`, HTE log | 4 | no external anchor (D-7) |
| audit and reconciliation | `attempts.reconcile`, `hte_accounting/crosscheck.py` | 4 | `independently_anchored: False` is a constant |
| strategy promotion | `ops/promotion.py`, `evidence.py` | 3, disabled | `TRUSTED_AUTHORITIES` is empty; `claims.enabled: false` |
| risk management | `equities/risk.py`, `execution/account.py` | 3 | per-track reports; mislabel C14; no portfolio risk layer |
| portfolio construction | `equities/track_compare.py` (toy sleeves) | 2-3 | no cross-track allocator |
| reserve and forward controls | `roles.py`, `stats/` e-process | 4, disabled | `reserve.enabled: false`; forward e-process tested on simulation only |
| operational monitoring | `orchestra/`, `ops/runner.py`, ledger-watchdog | 4 (orchestra 5 on macOS CI) | runner never run; iMac not installed (item 4) |
| research-agent permissions | CLAUDE.md hard rules, CODEOWNERS, `nightshift.protected` | 3 | the enforcement code itself is unprotected (C17); rule 16 omits two dispatchable workflows (G4) |

**Dependency graph** (production imports, not tests):

```
availability ← spec ← ledger ← attempts ← (nothing)
                 ↑        ↑
engine(pit, evaluate) ← access ← attempts
        ↑
factors(reproduce)   ← (nothing)     [the only real-data, public-FX, exploration path]
hte ← hte_accounting ← (nothing)     [dormant]
execution_realism ← hte_execution_bridge ← (nothing)   [dormant; does not import hte]
marketdata, equities, execution, tracks, orchestra, methodology ← (nothing)
```

Components that look complete in isolation but cannot yet work safely together:

- **HTE and the attempt ledger.** The bridge (#98) exists. But HTE reads its own in-memory panel, not a PR #86
  `PitStore` window (A-3), so the role fence never sees HTE reads.
- **HTE and execution.** HTE fills at the same close (F8). The lag-1 bridge (#97) is dormant and not connected.
- **Market data and the engine.** S12's adapters produce canonical datasets that nothing loads into a `PitStore`.
- **Equities and the attempt ledger.** The equities track has its own registration and holdout logic, which never
  touches `roles`, `access` or the ledger (C1).
- **Evidence classification.** Nothing produces evidence metadata, and `TRUSTED_AUTHORITIES` is empty.

### C.1 Confirmed defects, ranked

Severity is the impact **once the path is activated**. Today every path is dormant or synthetic-only, so none is
exploitable on main. Items marked **me** were reproduced or read by me; the others were reproduced by an S17
sub-review, and I re-read the cited code.

**C1. HIGH, confirmed (me): the equities holdout's "one look" is process-local, and the gate can be bypassed.**

- `_ISSUED` and `_HOLDOUT_READ` are module-level in-memory sets (`manhattan/equities/registration.py:190-191`).
- **Reproduction (me):** two separate Python processes on the same admitted batch each printed
  `holdout read; rejected = True excess_sharpe = -0.771`. Within one process a second look is refused, but
  `_HOLDOUT_READ.clear()` or a module reload resets the guard.
- Further bypasses (sub-review):
  - `R._issue(...)` mints a handle that `_require` accepts.
  - A forged `SelectionLock(spec_hash, 126, 0, "{}")` (zero variants tried) is accepted by `run_holdout`, which
    never checks that the locked lookback is in the declared grid (`registration.py:329`).
  - `track_compare.run_sleeve` runs any lookback on any window with no spec, lock or count.
  - The only guard is `is_synthetic`, and `synthetic.mark_synthetic` is public (`synthetic.py:27`).
- The equities holdout is not tied to the main fence. A 2023-01-03..2026-09-30 holdout was accepted although
  `exploration.data_end` is 2019-12-31 and `reserve.windows` is empty.
- **Consequence once real data are connected:** holdout reuse without trace, the exact failure the protocol exists
  to prevent. **Fix:** route equities experiments through `access.register_evaluation` with a designated reserve
  attempt in the persistent ledger, and delete the in-memory guard. Acknowledged in NON_TECH_TRACK §5a and §7.5 as
  a limitation; it is not yet tracked as a blocker.

**C2. HIGH by design (impact limited today), confirmed: a batch freeze can be self-certified.**

- `freeze.verify_frozen` checks internal consistency only (`freeze.py:126-157`). The timestamp "proof" is the mere
  existence of `manifest.json.ots` (`freeze.py:153`).
- `tag_is_signed` is a public keyword argument of `admit` (`registration.py:221`).
- The default `git verify-tag` accepts any trusted key, not specifically the owner's (`freeze.py:118-123`).
- Sub-review reproduction: `FZ.prepare` + `FZ.write`, `b"not a proof"` as the `.ots`, and `tag_is_signed=lambda
  t, r: True` printed `admitted self-certified batch: AB-0777`.
- The test fixture does the same (`tests/test_manhattan_equities_registration.py:45, 69-83`). **The tests encode
  the weakness.**
- **Fix before any real batch:** verify the OpenTimestamps proof, pin the owner's signing-key fingerprint, and make
  the signature check non-injectable outside tests.

**C3. HIGH, confirmed (me): U+2028, U+2029 and U+0085 make a ledger unopenable.**

- Cause: the writer uses `json.dumps(..., ensure_ascii=False)` (`ledger.py:463`); the readers split with
  `str.splitlines()` (`ledger.py:97, 119, 163`).
- **Reproduction (me):** three appends through `Ledger.append`, the second containing the character.
  - In-process `len` is 3.
  - `verify()` returns `['line 2: not JSON']`.
  - Reopening raises `LedgerError`; `read()` raises `JSONDecodeError`.
  - `recover_torn_tail` reports `clean`.
  - The same holds for `PublicIndex`, and for all three characters.
- **Consequence:** one free-text field (a correction reason, a summary) makes every later record unauditable. The
  writing process keeps appending to a file nobody can open.
- **Fix:** PR #104 (draft). The ops `Store` is likely affected the same way (not reproduced).

**C4. MEDIUM-HIGH, confirmed (me), new and not in any PR: the hash does not cover the line.**

- `record_hash` covers only `FIELDS` (`ledger.py:34, 56`), and nothing checks that a stored line is the canonical
  serialization of its record.
- **Reproduction (me)** on a `PublicIndex`, adding `"p_value": 0.001, "summary": {"sharpe": 2.5}` to record 2 and a
  duplicate `"payload":{"ledger_records":999}` at the front of line 3:
  - `verify` returned `[]`;
  - the reopened record 2 carries `p_value` and `summary`;
  - the raw line 3 shows 999.
- **Consequences:**
  - Outcome keys can be smuggled into the public index after the fact. `OUTCOME_KEYS` is checked only at append.
    This breaks the blinding the public index exists for.
  - Readers that parse the raw line differently see different data.
  - It contradicts the module's claim that editing any line breaks every later hash.
- **Fix:** on read, require `set(rec) == set(FIELDS) | {"hash"}` and `line == canonical(rec)`. Reject duplicate keys
  with `object_pairs_hook`. Small, testable, and safe to do now.

**C5. HIGH for evidence integrity, confirmed, known: no external anchor in production.**

- `Ledger.__init__` and `verify` default to `anchor=None` (`ledger.py:100, 313`).
- **Truncation:** dropping the last two of five records verifies clean without an anchor; with one, it is caught.
- **The HTE bridge:** cutting both the HTE log and the ledger back to before a second invocation hides 120
  attempts and a whole computing invocation. The crosscheck then reports `consistent: True`.
  - `crosscheck.py:87` calls `verify_hte_log` without an anchor.
  - `crosscheck.py:331` anchors to the file's own head.
- `BRIDGE.md:111`'s "each chain anchors the other" overstates this: ledger records never carry the HTE log head.
- `attempts.reconcile` reports `independently_anchored: False` as a constant (`attempts.py:673-677`).
- This is D-7 and G-2, documented as open. It is ranked here because **every denominator claim depends on it.**

**C6. MEDIUM, confirmed: no writer lock, and the "one designated reserve evaluation" rule is process-local.**

- `Ledger._append` takes `seq` and `prev_hash` from the in-memory index, with no file lock (`ledger.py:452-469`).
- Two handles appending fork the chain: `verify` reports `seq is 2, expected 3`, reopening fails, and
  `recover_torn_tail` says `clean`.
- `designated_reserve_starts` reads that in-memory index (`ledger.py:629`, `access.py:570`). Two runners could both
  pass `_one_designated` before either writes. The double write is **detected afterwards as corruption, not
  prevented.**
- The designation is per ledger file, so a new ledger path resets "one designated evaluation per (batch, domain)".
- The single-writer assumption is documented (ATTEMPT_ACCOUNTING.md:73, BINDING_ACCOUNTING.md:41) but not enforced.
- **Fix:** `fcntl.flock` around a re-read of the head plus the append, and one canonical ledger path per programme
  (owner, A-2).

**C7. MEDIUM, confirmed: the reserve fence fails open on malformed configuration.**

- `roles.py:44`: `enabled=bool(res.get("enabled"))`. A quoted `"false"` or `"no"` becomes `True`. With a window
  set, a runner's reserve read is **allowed**.
- `yaml.safe_load` keeps the last of two duplicate keys.
- `config.validate` would catch the quoted value, but the production path (`access.verified_fence` →
  `_fence_of` → `Fence.from_config`, `access.py:314-346`) never calls it, and no workflow runs
  `python -m manhattan.config check`.
- Main is safe today: `enabled: false`, `windows: {}`.
- **Fix:** PR #105 (draft). Also add a domain allowlist (owner decision; #105 lists it).

**C8. HIGH for activation, confirmed (me): the HTE bridge can strand attempts permanently.**

- `begin` registers every PR #86 attempt first and appends its `pr86_registered` HTE record last
  (`bridge.py:239-258`). If that last step fails, the ledger holds open attempts that no HTE record names.
- **Reproduction (me):** a second `begin` while the registered run was executing.
  - Output: `begin2 raised LogError another writer holds this workspace`, with 120 ledger records written by the
    failed call.
  - After the original run closed: `complete` and `abandon` raise `attempt has been superseded`, and `begin` raises
    `BridgeRefused ... never completed or abandoned`.
  - The crosscheck reports `consistent: False` (`finished_invocation_without_completion`, `foreign_attempt`,
    `pr86_reconciler`), with 120 open attempts.
  - **No API call can reach a valid state again.**
- Two variants (sub-review, not re-run by me):
  - Crash recovery after a torn HTE log tail. `begin` never calls `recover_torn_tail`. The recovered run ends
    `consistent: False` with 360 attempts recorded for 240 real ones.
  - A crash in the middle of `begin`. This leaves `foreign_attempt`.
- **Direction:** fail-closed (over-counting and inconsistency, nothing hidden), but unrecoverable.
- **No test covers these cases.** Eight crosscheck violation codes have no test at all: `terminal_mismatch`,
  `result_hash_mismatch`, `identity_mismatch`, `attempt_missing`, `registered_after_anchor`,
  `open_after_completion`, `duplicate_registered_attempt` and `registration_invocation_mismatch`.

**C9. MEDIUM, confirmed or likely: role gates rest on caller-asserted inputs.**

- `RunnerToken(verified=True)` can be constructed by any caller (`roles.py:69-75`).
- A caller-supplied `freeze` date turns 2020+ data into the `forward` role: `check_read("runner", "fx_daily",
  2021-01-04..2021-02-01, freeze=2019-12-31)` gives `forward`.
- `register_evaluation` accepts a caller-built `roles.Fence` (`access.py:660-663`). The reconciler only counts
  `protected_attempts_with_unpinned_fence` (`attempts.py:245-246`) and does not treat it as a violation (**likely**;
  not run end to end).
- `freeze.verify_frozen` is never called on the reserve path; its one caller is `equities/registration.py:227`.
- Mitigation in place: forward evaluation is refused on reconstructed windows (`evaluate.py:97`).

**C10. MEDIUM, confirmed: an admitted experiment need not execute what its family says.**

- Only one signal exists (`trailing_total_return/1`, `registration.py:71`). `run_sleeve` always goes long the top
  fraction (`track_compare.py:182-184`), ignoring `predicted_sign` and the free-text `construction`.
- `experiment_spec` accepts NT-V01 (value), NT-Q01, NT-R01 and NT-L01 (predicted sign `-`) with that momentum
  signal. An admitted "low-risk" experiment would run long momentum.
- NT-3's sector-neutral variant cannot be expressed: the grid holds only `lookback`.

**C11. MEDIUM-HIGH (scientific), confirmed (me): HTE does not enforce the grid cap.**

- `spec.MAX_GRID = 200` is enforced only by `spec.py:140`.
- `hte/registry.py` computes `grid_size` (`:75`) with no limit and imports `manhattan.spec` only for
  `canonical_bytes`.
- S13 E1b: with 51,214 variants a single real variant needs a true Sharpe ratio of about 1.92 to be found 80% of
  the time, against 0.94 alone.

**C12. Known, confirmed: HTE fills at the same close (S10 F8).** Every HTE return is optimistic and
non-evidential. The lag-1 path (#97) is dormant and not connected (S16 probe `adapter:hte->delayed-execution`).

**C13. LOW-MEDIUM, confirmed, documented: exploration looks can vanish.**

- Unbound evaluations write their record after `backtest.run` (`engine/evaluate.py:127`), and the rule-6 variant
  log after that (`:138`). A crash leaves no trace or a desynchronized pair.
- Bound (reserve and forward) attempts are written and fsynced before any read. That part is correct.

**C14. LOW-MEDIUM, confirmed (me): `technology_share` counts every non-technology sector as technology.**
`risk.py:152` treats every industry key other than the legacy `"non_technology"` as technology. A book of `banks` and
`electric_utilities` reports 1.0. No test covers it; #103 did not touch `risk.py`.

**C15. LOW-MEDIUM, confirmed or possible: macOS (the intended iMac runner).**

- **Confirmed (me):** `nightshift/explore_sandbox.py:198` resolves file paths with `os.readlink("/proc/self/fd/…")`,
  which does not exist on macOS. `_read_inside` then returns `None` for every file. It fails closed, but the
  explorer reads nothing on a Mac. This matches the "eight macOS `/proc/self/fd` failures" in
  `docs/manhattan/ops/CLOUD_VALIDATION.md:281`, which were recorded but not fixed. The macOS equivalent is
  `fcntl.F_GETPATH`.
- **Confirmed:** `manhattan/hte/ids.py:102` reads `/proc/self/maps` to identify the BLAS core, giving `"unknown"`
  on macOS. The numerical-environment digest is therefore less discriminating there.
- **Possible:** `os.fsync` without `F_FULLFSYNC` (no use anywhere in the repository) does not guarantee durability
  on macOS power loss.
- **Possible:** `data_hash` and `result_hash` hash raw float bytes (`pit.py:248`, `backtest.py:133`). The NaN sign
  differs between x86 and Apple Silicon, so a computed NaN would show up as false `nondeterminism` across the two.
- The full suite has **never run on macOS** in CI. The repository records no full-suite macOS-versus-Linux
  comparison.

**C16. LOW, confirmed:** passing a `datetime` instead of a `date` to `check_read` attempts a 644 GiB allocation
(MemoryError on Linux; possibly slower to fail on macOS).

**C17. LOW-MEDIUM governance, confirmed: the enforcement code is not owner-protected.**

- CODEOWNERS lines 71-94 protect the pre-registration files and `config/manhattan.yaml`.
- `manhattan/ledger.py`, `roles.py`, `access.py`, `attempts.py`, `freeze.py` and `evidence.py` are not protected.
- A session can weaken the checks rather than the files they check.

**C18. LOW, confirmed: `BridgePolicy.approval_ref` accepts any non-empty string** (`policy.py:83`; the test value
"test fixture, not an approval" passes). `ENABLED` is therefore the only real switch.
`scripts/hte_accounting_bench.py:64` sets `ENABLED = True` outside `manhattan/`, where PR #86's capability scan does
not look.

### C.2 Governance and process findings

- **G1. Adoption of Protocol v3.1 and SIM_PREREG_v2 is in force in practice but not recorded.** The owner added
  both to CODEOWNERS on 2026-11-13 (`1a7f653`), and the simulation was dispatched on that commit. ETHAN_ACTIONS item
  19 still reads "drafts". This is PR #83's D0.
- **G2. No screening method is validated.** See Deliverable A, point 3.
- **G3. Merges carry no approving review**, and #98's description is stale (B.9).
- **G4. Hard rule 16's writer list omits `manhattan-ops-runner.yml` and `manhattan-sim.yml`.** Both are
  `workflow_dispatch`. The first writes to the private `manhattan-ledger` repository; both are guarded to main.
  Recommend the owner adds them to the list.
- **G5. CI coverage gaps.** Tests run only on PRs to main, there is no macOS full suite, and the dependencies are
  unpinned.
  - `requirements.txt` uses `>=`, so CI resolves new versions on every run. My run resolved numpy 2.5.5, pandas
    3.1.1, scipy 1.18.1 and statsmodels 0.15.0.
  - A lock exists only for the ops runner (`requirements-manhattan-runner.lock`).
- **G6. Configuration log drift.** C14 is unrecorded (PR #77). The Janus daily review has been missing since
  2026-11-19 and C05 does not comply (dev morning report 2026-11-21). The 13-16 Nov usage-limit outage shows that
  Manhattan build sessions and Janus operations draw on one budget.
- **G7. The S16 acceptance gate does not bind the merged #98 bridge.** It still probes
  `hte.adapters.Pr86AccessAdapter`, which is disabled, so the gate cannot see #98's progress or regressions.
- **G8. Documentation drift.**
  - `hte/LIMITATIONS.md` A2 and the S16 probe text say PR #86 is unmerged.
  - `BRIDGE.md`'s "each chain anchors the other" overstates the anchoring (C5).

### C.3 Plausible risks not confirmed

- **Possible:** a reserve attempt with a self-built fence and token reconciles clean (C9).
- **Possible:** cross-platform hash drift (C15).
- **Unverified:** the ops `Store` separator defect.
- **Unverified:** that GitHub rulesets block direct pushes to main.
- **Possible:** correlated hypotheses counted as independent. There is no class merging; S13 E4 measured the class
  FDR rising to 0.55 under offline BH.
- **Unverified:** whether the futures PIT store, once connected, contains non-reconstructed 2020+ data that the
  forward-role path (C9) could reach.

### C.4 Not found

I found **no** activation path reachable from main's defaults. Every switch I checked (`reserve.enabled`,
`claims.enabled`, `real_money`, `loss_cap_usd`, the `ENABLED` constants of `hte_accounting`, `hte_execution_bridge`, `tracks` and `hte/protected.py` (stage 5), the ops
runner's schedule) is off. In the 300-run window, nothing dispatched a Manhattan writer.

---

## Deliverable D: research-readiness scorecard

**Scale:** Red = blocks the first credible experiment; Amber = workable with named fixes; Green = ready.

| dimension | rating | basis |
|---|---|---|
| **Infrastructure** | **Amber-Red** | Components are synthetic-tested (4) but disconnected (§C.0). S16 gate NOT_READY (78/25/0). Integrity defects C3-C6 sit in the ledger every claim depends on. The engine and access path did run once on public FX (exploration). The quality of individual modules is high. |
| **Data** | **Red** | Manhattan can read no licensed data (item 20). There is no equity data at all. The Norgate futures snapshot ends about May 2027 and is to be deleted then. Databento is CME-only from 2010-06 and paid per request. Public FX and the macro panel are mutable (vintage drift recorded). For the asset classes already traded, every historical window is spent at Grade 2 at best (AUDIT §3.1: ten confirmatory looks at 2020-01..2026-09 on FX and bonds, three on futures). |
| **Statistical methodology** | **Red** | The pre-registered simulation has not passed and no method is selected (G2). D-1 is open. There is no class merging (S13 blocker 2) and no grid cap in HTE (C11). Held-out scenarios are not built. The scale studied (about 600 families) is far below what HTE is built for. The methods themselves are correct against primary sources (C-01..C-15 met). |
| **Governance** | **Amber** | Excellent fail-closed defaults, hard rules and protected pre-registrations. But about 30 owner decisions are open. Adoption is unrecorded (G1), the enforcement code is unprotected (C17), rule 16 has gaps (G4), and protection of main is unverified. |
| **Operations** | **Amber-Red** | No iMac runner (item 4), signing key, timestamp client or anchor custody. The single-writer rule is unenforced (C6). There is no macOS full-suite evidence (C15). The orchestra itself is well tested, including on a real macOS runner. Agent-usage contention already stopped Janus once. |
| **Economic hypotheses** | **Amber-Red** | Draft catalogues (39 + 5 families) and a core-factor proposal that is not adopted. **No Manhattan hypothesis has been pre-registered.** In its favour: em-macro has 27 recorded trials, a working pre-registration practice (docs/prereg, trials.csv) and honest negative results (T02, T04). Against: the economically best-motivated futures families (carry, trend, basis momentum) are already spent or live in T20-T26. |

**Can Project Manhattan run a credible historical experiment today without violating its standards? No.** The
minimum conditions for the first real-data experiment, which is exploration only and carries zero evidential
weight:

1. Ledger integrity fixes merged: #104, C4, a writer lock (C6), and an external anchor at run close (C5/D-7).
2. Owner decisions: D-1 (the counting unit), D-10 (registration of exploration), and A-8 (how rule 6 logs variants).
3. One dataset under a verified `DataContract`, loaded into a `PitStore` (A-3 option (b)), with a licence that
   permits the use.
4. One owner-filed exploratory pre-registration, filed by Ethan under hard rule 4.
5. Grid at most 200, one scientific class, `engine.evaluate` path, lag ≥ 1 and the #85 or #93 cost model.
6. Owner authorization of the real-data run.

Before any **reserve** (screening) evaluation, add: a screening method that passed (PR #83 D3 and D8), reserve
windows decided (item 1), a persistent single-look guard for every track (C1), and non-injectable freeze
verification (C2).

---

## Deliverable E: owner decision memorandum

I decide nothing here. "What stays prohibited" is the conservative default that holds until the decision is made.

### E.1 D-1: which unit enters a multiple-testing denominator?

| | |
|---|---|
| **Question** | When a family is tested, what counts as one test: executions, candidates, variants, hypotheses, families or scientific classes? |
| **Why it matters** | Every p-value threshold and FDR level depends on it. Too small an *m* is anti-conservative; an arbitrary *m* (one that changes with retries or software versions) makes results irreproducible. |
| **Implementation** | The bridge and HTE report every level; `independent_statistical_tests` is `None`; `policy.denominator()` refuses (DECISIONS.md). |
| **Options** | (a) executions or attempts; (b) candidates or bindings; (c) S13's layered rule: variants per (family, window) = SPA's *m*, and one unit per scientific class per batch = *n_b*; (d) families only. |
| **Pros and cons** | (a) conservative but arbitrary. (b) inflated by aliases and duplicates. (c) matches the theory of SPA and BH, and S13 E4 shows it restores class-level FDR control. Its weakness is that class merging (M1-M3) must exist and be outcome-blind. (d) under-counts within-family search. |
| **Statistical implication** | Under (c), class-level FDR holds in every E4 scenario tested. Without merging, duplicated true families push the class FDR to 0.55 (offline BH). |
| **Operational implication** | (c) needs the merge rules and a class registry before screening. |
| **Failure modes** | A merge rule that looks at outcomes; classes defined after the fact; programme-wide counts that leave out em-macro's own trials on the same windows. |
| **Recommendation** | **(c)**, plus: (i) merges are decided from the spec alone and before any evaluation; (ii) the programme's census for a window includes the em-macro trials already evaluated on it (`trials.csv`, AUDIT §3) as context, even if Manhattan's own *n_b* does not count them. |
| **Prohibited until decided** | Any HTE or Manhattan statistic used to choose what to screen; any screening claim. |

### E.2 D-10: do HTE exploration evaluations register PR #86 attempts?

| | |
|---|---|
| **Options** | `unregistered` (status quo) / `register_every_evaluation` (implemented, dormant). `register_selected_only` is invalid and correctly not offered. |
| **Pros and cons** | Registering makes the selection history auditable, at about 3× HTE's compute time and about 3.6 kB per candidate. Unregistered costs nothing while HTE stays non-evidential (same close, synthetic). |
| **Failure modes of registering now** | C8 (stranded attempts), C5 (truncation hides an invocation), C6 (two writers fork the chain). **Registering into a ledger with these defects creates a false sense of completeness.** |
| **Recommendation** | **Register every evaluation, but switch it on only after C3-C6 and C8 are fixed and anchor custody (D-7) exists.** Until then keep HTE unregistered *and* prohibit using any HTE output to choose what gets screened or pre-registered. |
| **Prohibited until decided** | Activating the bridge; HTE on any non-synthetic panel. |

### E.3 B4: per-candidate or per-chunk attempts

**Recommendation: confirm per-candidate.** It is implemented and matches PR #86's contract. The indexed ledger
removed the cost argument for chunks, and per-chunk would need a redesign of PR #86. No statistical downside. This
is a formality: confirm it with an `approval_ref` pointing to a written record.

### E.3a DECISIONS.md on main: the exact choices, as the code encodes them

`docs/manhattan/hte_accounting/DECISIONS.md` (merged with #98) and `manhattan/hte_accounting/policy.py`:

| id | where the choice lives | exact values the code accepts | default | DECISIONS.md recommends | S17 recommends |
|---|---|---|---|---|---|
| **D-10** | `BridgePolicy.d10_registration` | `"unregistered"` (bridge writes nothing; raises `OwnerDecisionUnsupported`), `"register_every_evaluation"`. `"register_selected_only"` is accepted by the constructor but always refused | `None`, so `OwnerDecisionRequired` | register every evaluation, after A-1 and A-2 | the same, **and only after C3-C6, C8 and D-7** (E.2). Until then the de facto state is "unregistered", plus a ban on using HTE output to choose what is screened |
| **D-1** | `BridgePolicy.d1_counting_unit`, used only by `policy.denominator()` | one of `registered_executions`, `completed_evaluation_keys`, `executables`, `bindings`, `candidates`, `variants`, `hypotheses`, `families` | `None` | S13's **layered** rule: variants per (family, window) = *m*; one unit per scientific class per batch = *n_b* | the layered rule (E.1). **Gap (confirmed, me):** `D1_ALTERNATIVES` has no "scientific class" unit, and the field takes one unit, not a layered pair. The recommended decision **cannot be recorded in `BridgePolicy` as written**. Before D-1 is recorded, the code needs a class unit (after class merging, S13 M1-M3) and either two fields (`m_unit`, `nb_unit`) or a named `"layered_s13"` value. Do not approximate it with `families` |
| **B4** | `BridgePolicy.b4_cardinality` | `"per_candidate_attempts"` (implemented), `"per_chunk_attempt"` (raises `OwnerDecisionUnsupported`) | `None` | per candidate | per candidate (E.3) |
| **A-1** | **not a policy field.** Encoded as the `completion_writer` argument of `Bridge.complete`; `tests/test_manhattan_binding_access.py` `ALLOWED` lists the modules that may call `record_evaluation` | (a) add `manhattan/hte_accounting/bridge.py` to `ALLOWED`; (b) run HTE through `engine.evaluate` under an `AttemptContext`; (c) keep HTE completions out of the ledger | no writer, so `complete` refuses (`OwnerDecisionRequired: A-1`) | (a), exploration only, if D-10 = register | (a), with the proposed test that the bridge never imports or mints a `CompletionProof`, and with `ENABLED` remaining the switch |
| **A-2** | **not a policy field.** The ledger path the caller passes | (i) a dedicated persistent HTE exploration ledger with its own anchor; (ii) the main Manhattan ledger; (iii) one ledger per run | caller's choice; the bridge refuses ledgers inside the repository and the public index | (i) | (i), **plus** C6's writer lock and D-7's anchor; (iii) must be refused in code (it loses cross-run rerun detection: 1,681 false looks measured) |
| **A-3** | **not a policy field.** `hte.data.verify_synthetic` in the bridge | (a) hash binding, synthetic panels only (as now); (b) panels loaded into a synthetic `PitStore`, with reads through PR #86 windows | (a), enforced | (a) now, (b) before any real data | the same. (b) is S12's next task (Deliverable H) |

None of these is decided here, and the bridge stays dormant (`ENABLED = False`). Recording a decision means a
written owner record plus a `BridgePolicy` with an `approval_ref` naming it. Note C18: the code accepts any
non-empty `approval_ref`, so the record itself, not the string, is the control.

### E.4 A-1, A-2, A-3 and D-7: who writes, which ledger, data identity and anchor custody

- **A-1 (which module may call `record_evaluation`).** I agree with DECISIONS.md: allow
  `hte_accounting/bridge.py`, exploration only, and add the proposed test that it never mints a `CompletionProof`.
- **A-2 (which ledger).** One dedicated, persistent HTE exploration ledger. A per-run ledger loses cross-run rerun
  detection (1,681 false looks measured).
- **A-3 (data identity).** Hash binding for synthetic data only; `PitStore` windows before any real data.
- **D-7 (anchor custody): an addition from this audit.** The cheapest strong anchor is a **hash-only public
  commit**. At each run close, a writer appends `(ledger path id, record count, head hash, UTC time)` to an
  append-only file in a repository other than the ledger's, where GitHub's history timestamps it and an
  OpenTimestamps proof can be added. A hash reveals no outcome. Today's alternative ("the caller keeps it")
  protects nothing, which is C5.
- **Prohibited until decided:** treating any ledger as complete; any denominator claim.

### E.5 The screening method (PR #83 D0-D8): the decision that gates every claim

| | |
|---|---|
| **Question** | Run `43467828524` gives candidate (i) FAIL (V3 in D07a: SPA size 0.0594, upper end 0.0604, against 0.06) and candidate (ii) NOT EVALUATED on 4 small-group rows (D8). Which method, if any, may screen? |
| **Options for D3** | Revise the SPA test (a new protocol version; the threshold stays), or keep candidate (i) and within-family SPA claims off. |
| **Options for D8** | Never eligible on those scenarios / settle it by a larger or held-out run / a written reading of §5 against §7 step 1. |
| **Statistical view** | A written reading chosen *after* seeing which rows are short is the kind of post-hoc rule choice the programme forbids elsewhere. A larger pre-specified run is the clean route. |
| **Recommendation** | **D0:** record the adoption of v3.1 and SIM_PREREG_v2 as of `1a7f653` (2026-11-13). **D2:** complete D04h. **D8:** settle by a larger pre-specified run, never by a reading. **D3:** keep (i) off; do not revise the SPA test merely to pass V3. **D1** (stale HB code hash): rerun rather than grandfather, if the about 520 CPU-hours fit (they fit the owned hardware). Then build H01-H12 (D4) with a written draw protocol **before** any value is drawn. |
| **Prohibited until passed** | `claims.enabled`, `screening_method`, the reserve, the "Statistically supported" tier. |

### E.6 ETHAN_ACTIONS item 1: the reserve fence

**Recommendation: decide it after E.5, not before.** A reserve is useless without a validated screening method,
and setting windows early only invites use. When the time comes, use 2020-01-01..2026-09-30 per domain, labelled
**Grade 2**, in `disjoint_slices` mode (S13 §4.2: disjoint slices make candidate (i)'s across-batch condition true).
Grade 1 evidence exists only forward.

### E.7 NT-1 to NT-9 (non-technology track)

| id | recommendation |
|---|---|
| NT-1 classification | accept the package taxonomy for synthetic work. For real data, adopt a vendor's dated classification history, never today's codes back-filled |
| NT-2 REITs | include, flagged as a sub-universe. REIT payout rules distort value and quality measures, so the value family needs REIT-specific measures or must exclude REITs |
| NT-3 sector-neutral | as a variant, but **add a grid dimension** so it can be expressed (C10) |
| NT-4, NT-5 | keep cash Treasuries and bond ETFs out of every track |
| NT-6 futures roots | owner-declared list in a protected file, not caller-declared |
| NT-7 replication | designate nothing now. A designation is an owner act recorded before evaluation |
| NT-8 cross-track counting | follow D-1: one class-level census across all tracks per window |
| NT-9 data | see Deliverable F, data plan |

### E.8 Further decisions this audit adds

1. Add `manhattan-ops-runner.yml` and `manhattan-sim.yml` to hard rule 16's writer list (G4).
2. Add the enforcement code (`ledger.py`, `roles.py`, `access.py`, `attempts.py`, `freeze.py`, `evidence.py`) and
   its tests to the CODEOWNERS protected block (C17).
3. Require a persistent single-look guard in every track before any real data (C1).
4. A domain allowlist for reserve keys (#105's follow-up), and a cap on `exploration.data_end` at the rule-4 boundary in `validate` and `from_config` (B.8: today `"2025-12-31"` validates clean and turns 2021 reads into exploration).
5. Recovery policy for any ledger already holding a raw separator (#104 option B: an offline, owner-run re-escape).
6. Confirm the rulesets (item 6) and make "tests / pytest" a required check.
7. Record C14 (merge or replace PR #77).
8. Item 21(a)/(b), item 9 (`programme.end`, `θ_min`), item 10 (core factors), and A8 (how rule 6 logs 10^5 or more
   variants) remain open as documented.

---

## Deliverable F: first-year research roadmap

### F.1 Principles

- **Few, strong, economically motivated families.** S13 E7: on a protocol-scale world, candidate (i) passes about
  10 of 1,500 families at screening, and on average 0.3 families reach formal 5% forward support within 10 years.
  **The binding constraint is time and evidence, not compute.**
- **Do not duplicate T20-T26.** Commodity carry, basis-momentum and diversified trend are spent historically and
  live as shadows from 2026-12 (hard rule 5 protects them). Manhattan should add *different* mechanisms or
  *different* instruments.
- **Grids at most 200 per hypothesis**, sign pre-specified, one class per mechanism.

### F.2 Candidate hypothesis families (to evaluate, not assumed to work)

| # | family | rationale | instruments | data | falsifiable prediction | main confounders | why it might fail |
|---|---|---|---|---|---|---|---|
| 1 | **US Treasury futures carry and roll-down** (rates track) | term premium: roll-down plus carry predicts excess return (Koijen, Moskowitz, Pedersen and Vrugt) | ZT, ZF, ZN, ZB, UB | Norgate futures (in use; licence ends about May 2027) or Databento GLBX (2010+); FRED or ALFRED yields | sign of the carry-ranked spread > 0 net of costs | duration beta, the 1981-2020 secular bond rally | short history after 2010 if Databento only; the effect is mostly duration |
| 2 | **Commodity hedging pressure** (commodities track) | Keynesian normal backwardation; positioning by commercial hedgers (Basu and Miffre) | the T20-T22 commodity universe | **CFTC Commitments of Traders, free, with publication dates** (Tuesday positions released Friday) plus futures prices | a long-short sorted on hedging pressure earns > 0 net, **beyond** T20 carry and T21 basis-momentum | overlap with carry (backwardation) | spanned by T20 and T21: the test must be orthogonalized to them, pre-specified |
| 3 | **Equity cross-sectional momentum, sector-neutral** (both equity tracks) | under-reaction and slow diffusion | US common stocks | survivorship-free prices with delistings | 12-1 momentum, sector-neutral, > 0 net, with the tech and non-tech tracks reported separately | industry momentum, crash risk | costs and crashes; heavily published, so the LLM knows the answer (Grade 2 at best) |
| 4 | **Equity low-risk / betting-against-beta** | leverage constraints (Frazzini and Pedersen) | US common stocks | prices only | low-beta minus high-beta, beta-neutral, > 0 net | size and value exposure | depends on construction; turnover |
| 5 | **Quality / profitability, PIT** | under-pricing of profitable firms (Novy-Marx) | US common stocks | **SEC EDGAR XBRL**, free, with acceptance timestamps (from about 2009-2011, unverified) | gross profitability long-short > 0 net | value overlap; restatements | short PIT history; XBRL tag inconsistency |
| 6 | (year 2) **Value with PIT fundamentals** | risk or behavioural premium | US common stocks | EDGAR plus prices | book-to-market long-short | long drawdowns since 2007 | weak recent evidence |

**Defer:**

- Regime-conditional variants: at most one, with a single pre-specified macro state.
- Earnings-revision and analyst families: the data are unaffordable (DATA_ACQUISITION Tier 2). Use forward
  collection if ever.
- Anything needing borrow history.

**Per family, the pre-registration should contain:**

- the mechanism and predicted sign;
- the universe rule (PIT);
- the signal formula and bounded grid (≤ 200);
- lag ≥ 1 and the cost model;
- the baseline, which is the track's equal-weight costed universe, plus the core factors once adopted;
- the selection rule;
- the windows: exploration ≤ 2019, then the Grade 2 reserve later, then forward;
- the rejection criteria;
- robustness checks declared in advance;
- the class id for D-1.

**Validation design:**

1. Walk-forward inside the exploration window.
2. One designated look at the reserve, after the screening method passes.
3. The forward e-process.

### F.3 Statistical design

- **Multiplicity.**
  - Within a family: SPA over every variant ever evaluated on the window (*m*).
  - Across families: the screening procedure over one unit per class (*n_b*).
  - Effective tests: Li-Ji `M_eff` for **description** only, never to shrink *m* (it assumes Gaussian correlation
    structure).
- **Deflated and probabilistic Sharpe ratios:** report DSR and PSR as descriptive diagnostics, with skew, kurtosis
  and the number of trials taken from the census. They are not the decision rule, which is SPA with screening.
- **Non-normality and serial correlation:** stationary bootstrap with Politis-White blocks, already implemented.
- **Non-stationarity:** sub-period stability as a declared robustness check, not a re-selection step.
- **Economic significance:**
  - net-of-cost Sharpe of at least `θ_min = 0.25`;
  - turnover and capacity reported;
  - cost multiples (×2, ×3) as pre-declared stresses;
  - no claim on gross returns.
- **Portfolio level:** a candidate earns its place by its marginal contribution against the core factors and the
  live sleeves, not by its standalone Sharpe.
- **Why a search of 10^5 variants is counterproductive.**
  - The expected maximum of *m* null Sharpe estimates grows like `σ√(2 ln m)`.
  - S13 measured the 80%-power true Sharpe at 0.94 for one variant, 1.53 at *m* = 200 and 1.92 at *m* = 51,214.
    At the first screening bar these become 1.65, 2.10 and 2.45.
  - A large uncontrolled search therefore cannot find realistic edges (true Sharpe 0.3-0.8), and any "discovery"
    is very likely a selection artefact.
  - Registering after a look gave an FDR of 1.00 (S13 E6).
- **First-year volume:** **4-6 families, 8-15 pre-registered hypotheses, at most 200 variants each.** That is about
  1,000-3,000 variants evaluated in the year, all in the exploration role until the screening method passes.

### F.4 Data plan (nothing bought; prices unverified unless stated)

| need | candidate | depth | PIT and survivorship | licence notes | cost (unverified unless marked) |
|---|---|---|---|---|---|
| futures daily, contract level | **Norgate futures** (already licensed for em-macro) | 30+ years | settlement history; rolls built in-house (#85) | Personal Use, no redistribution; **ends about 5 May 2027**; snapshot to be deleted then | renewal price not found publicly; check Norgate's calculator. One aggregator lists US$630 a year for a US *stocks* Diamond tier (not futures) |
| futures, CME only | **Databento GLBX.MDP3** pay-as-you-go | from 2010-06 | exchange data; definitions included | per-request; current US$1 daily cap in the repository | official "historical from US$0.50/GB"; EOD bars are small. Use `metadata.get_cost` before any request |
| positioning | **CFTC COT** | 1986+ | release dates known | public | free |
| macro and yields | **FRED / ALFRED** | decades | ALFRED vintages | public | free |
| US equities with delistings | **Norgate US stocks** or **Sharadar (Nasdaq Data Link)** | Norgate about 1990+; Sharadar about 1998+ (unverified) | both described as survivorship-free; **verify** delisting returns and historical index membership (DATA_ACQUISITION §4) | personal licences; check derived-data publication and retention after cancellation | Sharadar Equity Prices personal: about US$399 a year for full history per one aggregator (**unverified**). Fundamentals cost extra |
| fundamentals, PIT | **SEC EDGAR XBRL** | about 2009+ | acceptance timestamps | public | free |
| factor baselines | Ken French library | 1926+ | not PIT; descriptive only | public | free |

**Minimum viable set for year 1:**

- Norgate futures (renew before May 2027, or Databento for the CME subset);
- CFTC COT, FRED and ALFRED, and EDGAR (all free);
- **one** survivorship-free US equity price source, after the checklist in DATA_ACQUISITION §4.

**Storage:**

- Daily futures, about 100 markets × 40 years at contract level: low single-digit GB.
- Daily US equities, about 20,000 securities × 25 years: about 125M rows, a few GB in Parquet.
- Both fit a 16 GB machine with chunked processing.
- Licensed rows stay in em-macro-data or on the iMac (hard rule 7).

### F.5 Budget and computing (target about S$500 a month)

- **Approval status of the budget.** The repository *assumes* S$500 a month (DATA_ACQUISITION.md;
  `monthly_budget_sgd` in the orchestra), but I found no owner-approved budget record.
- **Hardware.** The repository names only the iMac (8 cores, and "a 16 GB machine" in ETHAN_ACTIONS). It has no
  evidence of a MacBook Air or Mac mini. None of this can be verified from a cloud session: **unverified.**

| line | estimate | note |
|---|---|---|
| data | about S$60-200 a month | Norgate renewal plus one equity source, plus occasional Databento pulls. Unverified prices |
| compute | about S$0 marginal | owned hardware plus GitHub public runners. The full simulation is about 2,000-2,200 CPU-hours: about 12-13 days on the 8-core iMac (OPERATIONS.md), or about S$145 once on AWS c7a.2xlarge (US$0.41/h, unverified) |
| agent usage | the main variable cost | already hit its limit once (13-16 Nov). **Cap Manhattan build sessions so that Janus and ledger operations keep priority** |
| backup | about S$0-10 a month | an encrypted external drive plus the private repository; anchors on a public repository cost nothing |

**Machine roles, if the machines exist:**

- **iMac:** the runner, the reserve store (`imac_only`), the signing key and the timestamp client.
- **Mac mini:** a second runner for the simulation, or a cold backup.
- **MacBook:** development only, holding no reserve data.

**Memory:** HTE at 100k used 2.0-2.5 GiB; 7 HB workers need 12.5 GB, so run 4-5 on a 16 GB machine.

**Do not** enable any LaunchAgent, schedule or persistent service until the iMac acceptance check (OPERATIONS §13)
has been run by hand.

### F.6 Phases and gates (12 months)

| phase | months | deliverables | exit gate |
|---|---|---|---|
| **0. Integrity** | 1 | #104 and #105 merged; C4 fix; ledger lock (C6); anchor at run close (D-7 decided); C1, C2, C8 and C10 fixed or the paths fenced; CODEOWNERS for the enforcement code; rule 16 updated | all of §C's HIGH items closed with tests that fail before and pass after; S16 gate binds #98 |
| **1. Decisions and simulation** | 1-3 | D-1, D-10, B4, A-1 to A-3 recorded; PR #83's D0-D8 decided; D04h completed; HB rerun; H01-H12 built from a written draw protocol | a screening method selected by its pre-registered report, or a written decision that none is |
| **2. First Light** | 2-4 | one dataset under a `DataContract` → `PitStore`; one owner-filed exploratory pre-registration (family 1 or 2); run end to end on ≤ 2019 data via `engine.evaluate`, anchored, full denominator | reproducible bit-for-bit on a second machine; census balanced; anchors verify |
| **3. Exploration programme** | 4-8 | families 1-5 pre-registered and explored (≤ 2019), with class merging live (A2) and HTE at lag 1 with a grid cap if used | each family documented with its full denominator, including negative results |
| **4. Screening** | 7-10 | only if phase 1 selected a method: reserve windows (item 1), designated single looks, screening decisions | decisions logged before outcomes; e-LOND/BH bookkeeping reconciles |
| **5. Forward enrolment** | 9-12 | screened families enrolled in forward observation (paper, no execution) | forward e-process running; **no** live or paper trading without separate owner approvals |

**Not now:**

- more HTE throughput work (10^6 runs);
- new tracks;
- more catalogue families;
- portfolio construction beyond reporting;
- the ops-runner schedule, the reserve, claims, live or paper trading.

---

## Deliverable G: the next 30 days

### Start immediately (safe before any governance approval; code and tests only, synthetic)

1. **The C4 fix**: strict line canonicality and key-set checks on read, rejection of duplicate keys. Test: the
   injected `p_value` line is refused.
2. **Rebase #104 and #105 onto main and re-run CI.** Get an independent review of each, by someone other than
   their author.
3. **A ledger writer lock.** `flock` plus a re-read of the head inside `_append`, with a two-process test that
   must not fork.
4. **Bridge `begin` atomicity (C8).** Take the workspace lock for the whole of `begin`/`complete`/`abandon`, write
   an intent record first, call `recover_torn_tail` on resume, and test the three reproductions.
5. **Tests for the 8 uncovered crosscheck violation codes**, and for concurrency.
6. **Equities (C1, C2, C10).**
   - Persist the holdout guard (or route through `access`).
   - Make the signature and timestamp checks non-injectable.
   - Check the locked lookback against the grid.
   - Refuse a family whose signal or sign does not match its spec.
   - Make `mark_synthetic` private.
7. **The grid cap in HTE (C11).**
8. **macOS:** `F_GETPATH` in `explore_sandbox`; `F_FULLFSYNC` on darwin; canonicalize NaN before hashing.
9. **The S16 gate binds #98;** fix the stale probe and documentation text (G7, G8).
10. **`technology_share` (C14)** fix and test.

### Needs code review (owner or an independent reviewer)

- #104, #105, and every item above.
- PR #83 as a document, so that the decisions can be taken.

### Needs owner decisions

- E.1-E.5.
- Item 6 (rulesets, required check).
- CODEOWNERS additions (C17) and rule 16 (G4).
- Recording C14 (PR #77).
- Unblocking the night-shift promotion (#73).
- Whether to close #102.
- Item 4 (iMac setup: signing key, timestamp client) and item 20 (em-macro-data access).

### Needs real-data authorization

- The First Light experiment, its dataset and its pre-registration.
- Any Norgate, Databento or equity-vendor purchase or renewal.

### Stays blocked

- The reserve.
- `claims.enabled`.
- Bridge activation (D-10).
- HTE on real data (A-3).
- The ops-runner schedule.
- Forward enrolment.
- Any trading.

---

## Deliverable H: agent task allocation (a recommendation; nothing assigned or started)

Attribution is evidenced by commits, branches and document headers:

| session | evidenced work |
|---|---|
| S9/S10 | HTE (#89) |
| **S11** | HTE identity levels (#90; branch suffix `gesrcf`). The same branch suffix carries #100, #98, #104 and #105, so these are likely the same session, but **unverified** |
| **S12** | market data (#92, #99) |
| **S13** | methodology (#95) |
| **S14** | execution realism (#93), HTE execution bridge (#97) |
| **S15** | orchestra (#94) |
| **S16** | acceptance gate (#91, #96), non-tech track (#103; same branch `cool-fermat-y0xe7a` as #91) |

| agent | recommended next assignment | why |
|---|---|---|
| **S11** | finish ledger integrity: land #104 and #105 after review; C4; C6 lock; C8 atomicity; anchor-at-close implementation once D-7 is decided | owns the ledger and the bridge; fresh context |
| **S12** | A-3 option (b): load a `DataContract`'d synthetic dataset into a `PitStore` and serve HTE and engine reads through windows. Then, with authorization, the First Light dataset | connects marketdata to the engine, the largest island |
| **S13** | the PR #83 decisions as analysis (no selection); build H01-H12's draw-protocol draft; specify class-merge rules M1-M3 and acceptance test A2; A4 (calibration of HTE's SPA) | statistics owner |
| **S14** | bind HTE to lag-1 execution (#97) behind its switch; per-asset cost calibration plan | removes F8 |
| **S15** | single-writer enforcement at the orchestrator level; anchor-at-close job design; macOS fixes (C15) | operations and macOS owner |
| **S16** | C1, C2, C10, C14 in equities; bind #98 into the gate; add cross-process and concurrency acceptance tests | author of #103 and the gate |
| **new: independent reviewer** | review `d357b12`, #104, #105 and the fixes above, given the code only | no merged Manhattan PR has had a non-author review |
| **new: research designer** (later) | draft the pre-registrations for families 1-2 in `docs/prereg_drafts/` for Ethan to file | only after phase 0 |

**Avoid:**

- two agents on `ledger.py` at once (S11 and S16 both touch the accounting);
- any agent on `hte/` scale work;
- any agent creating workflows or schedules.

---

## Deliverable I: the ten highest-value actions

| # | action | why | who | approval | done when |
|---|---|---|---|---|---|
| 1 | Decide PR #83's D0, D2, D3 and D8, and record the adoption of v3.1 | no screening method means no claim is possible; everything downstream waits on this | Ethan (S13 prepares) | **owner** | a written decision; D04h completed; method selected or explicitly none |
| 2 | Fix ledger integrity: #104, C4, C6 lock | the census is the programme's core asset, and today it can be made unopenable, edited invisibly or forked | S11 + independent reviewer | review and merge | reproductions in §C fail closed under tests |
| 3 | Decide D-7 and implement an anchor at run close | without it truncation erases attempts undetected (C5), so no denominator is trustworthy | Ethan decides; S11 builds | **owner** | `independently_anchored: True` in reconcile on a synthetic run |
| 4 | Decide D-1 (S13's layered rule plus class merging) | every multiple-testing number depends on it | Ethan | **owner** | a recorded decision; A2 test spec written |
| 5 | Harden the equities gate (C1, C2, C10) before any real equity data | holdout reuse and self-certified freezes would invalidate the first equity result | S16 | review | two-process reproduction refused; forged lock refused; self-signed tag refused |
| 6 | Merge #105 and protect the enforcement code (C17) | a typo must not open the reserve; checks must not be weakened by a session | S11; Ethan for CODEOWNERS | **owner** for CODEOWNERS | `"false"` is refused; CODEOWNERS lists the six modules |
| 7 | Connect marketdata to `PitStore` (A-3(b)) on synthetic data | turns the largest island into the data path every real experiment needs | S12 | review | HTE and the engine read through metered windows in a test |
| 8 | Data decision before May 2027: Norgate renewal and one equity source after the §4 checklist | futures history vanishes when the licence ends; equities have no data at all | Ethan | **owner (spending)** | a written choice with verified coverage answers |
| 9 | First Light: one pre-registered exploration experiment end to end | proves the pipeline and exposes integration bugs at zero stakes | Ethan files; S12 and S13 run | **owner + real-data authorization** | reproducible on two machines, anchored, full denominator published |
| 10 | Governance hygiene: confirm rulesets and the required check, extend rule 16, record C14, unblock #73, Janus daily review | the guarantees assumed elsewhere may not be enforced; operations are drifting | Ethan | **owner (settings)** | settings confirmed; config log current; promotion green |

---

## §8. What was inspected, run and verified, and the limits

### Inspected

- **GitHub:** all open PRs (#73, #77, #83, #101, #104, #105) and #98, #100 and #103 in detail; open issues; 104
  branches (merged status computed in a blobless clone); the 300 most recent workflow runs; #98's CI job log; the
  CODEOWNERS history.
- **Code:** the import graph of `manhattan/`; `ledger.py`, `roles.py`, `access.py`, `attempts.py`, `freeze.py`,
  `spec.py`, `hte/registry.py`, `hte/ids.py`, `hte_accounting/`, `hte_execution_bridge/bridge.py`,
  `equities/registration.py`, `equities/risk.py`, `nightshift/explore_sandbox.py`, `config/manhattan.yaml`, and the
  workflows.
- **Documents:** ETHAN_ACTIONS, MANHATTAN_PROGRESS, AUDIT §3, S13, DECISIONS, BRIDGE, LEDGER_SCALING, NON_TECH_TRACK,
  DATA_ACQUISITION, OPERATIONS, LIMITATIONS, S16_ACCEPTANCE.
- **Sub-reviews:** three bounded, read-only sub-reviews (the bridge; #103 and the holdout; the ledger, access and
  config core).

### Run

All runs were synthetic, in a scratch clone of `2577f25`, with Python 3.12.3 venv, `EM_MACRO_DATA` pointing at a
non-existent path, and no tokens.

- **The S16 acceptance gate:** `python tests/acceptance/run.py --out …` gave **NOT_READY, 78 PASS, 25 BLOCKED,
  0 FAIL**, exit 0.
- **Reproductions I ran myself:**
  - C3 (separators, all three characters, Ledger and PublicIndex);
  - C4 (unhashed fields and duplicate key verify clean);
  - C8(a) (stranded bridge attempts);
  - C1 (two processes each read the holdout).
- **PR #104 and #105 review (B.8):** new tests against unpatched main (16/24 and 74/125 fail); 13 regression
  suites on main + #104 + #105 gave 714 passed, 0 failed; #105 probes; ops `Store` reader reproduction.
- **Reproductions by the sub-reviews and not re-run by me:** C5 truncation, C6 fork, C7 fence, C8(b)(c), C9, C10.
- **Targeted suites run by the sub-reviews:** `test_manhattan_hte_accounting.py` 60 passed; equities
  registration, non-tech and tracks 75 passed; the separator pins 4 passed.
- **The full suite:** the result is in the session report that accompanies this file. A first attempt under the
  container's Python 3.13 failed at collection because `scipy` and `statsmodels` were not installed. That was an
  environment gap, not a repository defect.

### Could not verify

- **macOS full-suite behaviour.** Only static evidence and the orchestra's own macOS CI record exist.
- **Hardware and the budget record.**
- **Applied rulesets.**
- **Vendor prices and coverage.**
- **PR #83's numbers.** I read its classification; I did not recompute it.
- **The ops `Store` separator defect.**
- **Whether the session suffix `gesrcf` is S11.**
- **The content of em-macro-data and the Norgate snapshot.** Not accessed, by rule.
