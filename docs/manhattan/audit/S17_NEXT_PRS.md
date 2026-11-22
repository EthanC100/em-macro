# S17: the next three PRs, lane coordination and the D-1 investigation

S17, 2026-11-22. Builds on [S17_REMEDIATION_PLAN.md](S17_REMEDIATION_PLAN.md), which the owner approved as a planning
baseline on 2026-11-22 (not as authorization to activate research or to implement unresolved scientific decisions).

**Standing constraints (owner, 2026-11-22):**

- PRs #104 and #105 are with Codex for final independent review and possible merge; nothing here duplicates that
  work.
- Every protected research and trading switch stays disabled.
- No merge, deployment, real-data experiment or owner-only decision without explicit approval.
- θ_M3 and the economic duplicate-detection fields are not chosen without a pre-registered justification.
- The HB simulation rerun is deferred until the ledger changes and the code-hash policy are settled (plan §1, K1).

## 1. The next three PRs

Priority order follows the owner's list: ledger integrity, persistent holdout enforcement, genuine freeze
verification, end-to-end synthetic reproducibility. Each PR is a draft into main, opened from its own branch by its
lane's agent, reviewed by an independent reviewer, and merged only by the owner.

### PR-1. Ledger integrity II: canonical lines (C4), a writer lock (C6), durable appends on macOS

| | |
|---|---|
| lane / agent | A: S11 (owner of `ledger.py`) |
| depends on | **#104 merged** (Codex). The canonical form is `ledger.record_line`; starting before #104 lands would conflict in the same file |
| files | `manhattan/ledger.py`, `tests/test_manhattan_ledger_integrity.py` (new). Nothing in `manhattan/stats/` or `manhattan/sim/` |
| complexity | M (about 3-4 agent-days with review) |
| side effect to record | changes the code identity of the HB v2 runs (`CODE_FILES_V2_HB` lists `ledger.py`). Acceptable, because the HB rerun is deferred until after this PR (K1). The PR description must say so |
| out of scope | the external anchor (designed in S17_ANCHOR_DESIGN.md; needs the owner's repository); the ops `Store` (R2, lane D) |

**Changes:**

1. **On read** (`verify_snapshot`, `iter_verified`, `Ledger()`, `PublicIndex()`):
   - every record's key set equals `FIELDS ∪ {"hash"}`;
   - every stored line equals `record_line(record)` byte for byte;
   - a duplicate JSON key is refused (`object_pairs_hook`).
2. **On append:**
   - take an exclusive `fcntl.flock` on a sidecar lock file;
   - re-read the file's last line and refuse if its hash is not the in-memory head (a stale handle);
   - write and `fsync`, and on macOS also `fcntl(F_FULLFSYNC)`;
   - release the lock.
   - Directory `fsync` when the file is first created.
3. **A failed partial write** in the same process makes the handle unusable (no further appends after torn bytes;
   S17 C1-report finding 7).

**Acceptance criteria:**

| id | test | pass |
|---|---|---|
| P1-a | the S17 reproduction: `p_value` and `summary` added to record 2 of a `PublicIndex`, plus a duplicate `"payload"` key at the front of line 3 | `verify` returns a violation for both lines; `Ledger()` and `PublicIndex()` raise; the test fails on main |
| P1-b | non-canonical whitespace or key order in an otherwise valid line | refused |
| P1-c | every committed ledger fixture and every ledger written by the existing suites | still verifies (the canonical check introduces no false positive); PR #100's byte-identical differential test still passes |
| P1-d | two processes appending 1,000 interleaved records to one ledger | linear chain, `seq` 1..2,000, 0 forks, reopen OK; fails on main (the S17 fork reproduction) |
| P1-e | a stale handle (the file advanced by another handle) | `append` raises `LedgerError`, writes nothing |
| P1-f | a simulated partial write (`write` raises mid-line) | the handle refuses further appends; `recover_torn_tail` restores a verifiable file |
| P1-g | macOS | the lock and append tests run in the `orchestra-macos` job as well (paths filter extended to `manhattan/ledger.py`), or an equivalent macOS step in `tests.yml` |
| P1-h | the full suite | green in the `tests` workflow on the PR's merge commit; no edit to `CODE_FILES*` files (hash test) |

### PR-2. Genuine freeze verification (C2) and a persistent single-look holdout (C1)

| | |
|---|---|
| lane / agent | B: S16 (author of the equities gate); `freeze.py` coordinated with `ops/freeze_pr.py` |
| depends on | **PR-1 merged** (the persistent single look relies on the writer lock for its two-process guarantee); #105 merged (the fence it routes through) |
| files | `manhattan/freeze.py`, `manhattan/equities/registration.py`, `manhattan/equities/synthetic.py`, `manhattan/equities/track_compare.py` (gate the direct path), tests (new `tests/test_manhattan_freeze_verification.py`; extend `tests/test_manhattan_equities_registration.py`). Not `access.py`, `ledger.py` or `roles.py` (lane A) |
| complexity | L (about 1-2 weeks with review) |
| owner input | the owner's signing-key fingerprint. **Until it is given, the production pin is `None` and every real freeze is refused (fail closed)**; tests use a fixture key |

**Changes:**

1. **`verify_frozen`:**
   - verifies the OpenTimestamps proof against the manifest hash (an `.ots` that does not verify is refused, not
     merely present);
   - verifies the batch tag's signature against a **pinned owner fingerprint** (`ALLOWED_FREEZE_SIGNERS`, empty by
     default) rather than any trusted key.
   - `tag_is_signed` and the timestamp verifier stop being public keyword arguments; tests reach them through a
     test-only seam that production code cannot import (a static test pins this).
2. **Equities holdout:**
   - `run_holdout` registers a **designated** exploration-to-reserve-style attempt through
     `access.register_evaluation` in the persistent ledger, keyed by (batch, spec, holdout window).
   - A second look in any process finds the designated start in the ledger and is refused.
   - The in-memory `_ISSUED`/`_HOLDOUT_READ` sets are removed.
   - The holdout window must lie in a configured reserve window and pass the main fence. Today the reserve is off
     and its windows are empty, so **every real holdout is refused**, as it should be.
3. **`SelectionLock`:**
   - the locked lookback must be in the declared grid;
   - a lock records the variants actually tried, checked against the census;
   - `_issue` and `mark_synthetic` become non-public, and the synthetic marker is checked by provenance hash, not
     a settable flag.
4. **The direct path:** `track_compare.run_sleeve` refuses windows outside the selection window unless called by the
   gate.

**Acceptance criteria:**

| id | test | pass |
|---|---|---|
| P2-a | the S17 self-certified batch: `b"not a proof"` as `.ots`, `tag_is_signed=lambda t, r: True` | refused (`FreezeError`); fails on main |
| P2-b | a tag signed by a trusted key that is not pinned | refused |
| P2-c | the fixture owner key plus a valid fixture OTS proof | admitted |
| P2-d | the S17 two-process reproduction (`AB-0777`, two separate processes each calling `run_holdout`) | exactly one read; the second process raises; the ledger shows one designated start; fails on main |
| P2-e | `_HOLDOUT_READ.clear()`, a module reload, a new process | the second look is still refused (the state is in the ledger) |
| P2-f | a forged `SelectionLock(spec, 126, 0, "{}")` whose lookback is not in the grid, or whose variant count disagrees with the census | refused |
| P2-g | a holdout of 2023-01-03..2026-09-30 with main's configuration | refused by the main fence |
| P2-h | `run_sleeve` on a holdout window outside the gate | refused |
| P2-i | the existing equities, non-tech and track suites, and the S16 acceptance gate | green; NT-track synthetic results unchanged (`NON_TECH_TRACK.md` §6 table) |

### PR-3. First Light: the data-access cap and an end-to-end synthetic reproducibility harness

| | |
|---|---|
| lane / agent | F: S12 (data path) with S17's prepared cap; the reviewer checks the cap independently |
| depends on | the cap: nothing; it is **prepared** on `claude/manhattan-comprehensive-audit-i7a2ov` (`manhattan/firstlight/cap.py`, `tests/test_manhattan_firstlight_cap.py`, 46 tests, 6 of 6 mutations caught) and can be cherry-picked into a fresh branch. The harness's ledger leg: #104 merged (Codex), and PR-1 for the canonical-line check (FL-4). The harness's freeze leg: PR-2 (FL-1), with a fixture key until the owner key exists |
| files | `manhattan/firstlight/` (cap plus a new `harness.py`), tests. No existing file is changed |
| complexity | M for the harness; the cap is done |
| data | **synthetic only.** A seeded synthetic futures-like dataset under a synthetic `DataContract`; no real market data, no em-macro-data, no licensed source |

**What the harness does** (one command, one test):

1. builds the synthetic dataset;
2. loads it through `CappedStore` (the cap refuses anything dated or published after 2019-12-31);
3. freezes a one-family, ≤ 200-variant spec (fixture key until PR-2 and the owner key);
4. runs each variant through `engine.evaluate` on exploration windows checked by `check_declared_windows`;
5. writes the ledger;
6. writes a local-file anchor stub that implements S17_ANCHOR_DESIGN.md §5's verification interface (no external
   repository);
7. builds a report from the ledger plus the anchor;
8. runs everything a second time in a fresh process and compares.

**Acceptance criteria:**

| id | test | pass |
|---|---|---|
| P3-a | the cap: reads ending after 2019-12-31 for every caller | `CapError` (prepared, passing) |
| P3-b | the cap: values dated **or published** after 2019-12-31 | refused at load, nothing added (prepared) |
| P3-c | the cap does not follow a widened `exploration.data_end`; a runner with a freeze cannot read 2020+ as forward | refused (prepared) |
| P3-d | the cap: datetimes, strings, minute-precision arrays | refused (prepared) |
| P3-e | the cap is dormant | nothing in `manhattan/` imports it (prepared) |
| P3-f | the harness, run twice in separate processes | identical `result_hash` for every computation; byte-identical report; identical census |
| P3-g | the census | registered = completed + failed + aborted; 0 unfinished; variants evaluated = grid size; a fault-injected kill mid-run leaves a visible `unfinished` that the retry supersedes |
| P3-h | the anchor stub, on a copy | truncation by 1 and a hash-valid prefix rewrite are detected |
| P3-i | the report | lists every variant's result including negatives; evidence class exploration, weight 0; 0 outcome keys in any public artefact |
| P3-j | the switches | `python -m manhattan.config check` passes with reserve, claims and real money all false; the harness refuses to run if any is true |

**Not in PR-3:**

- real data;
- the external anchors repository;
- registration of exploration attempts in a shared ledger (owner decision D-10: the harness uses a scratch ledger
  in a temporary directory).

### Dependency summary

```
Codex: #104 ──► PR-1 (S11) ──► PR-2 (S16) ──► (PR-3's freeze leg)
Codex: #105 ───────────────────► PR-2
PR-3 cap: ready now ──► PR-3 harness (S12) ◄── #104 (+ PR-1 for FL-4)
owner: signing key fingerprint ──► PR-2's production pin
owner: anchors repository (S17_ANCHOR_DESIGN.md) ──► real FL-4 (after these PRs)
HB rerun: after PR-1 and the code-hash policy (K1)
```

## 2. Lane coordination (until these PRs land)

| lane | agent | now | must not touch |
|---|---|---|---|
| A | S11 | prepare PR-1 on a branch from main; open it once #104 has merged | `freeze.py`, `equities/`, `stats/`, `sim/`; the #104 and #105 branches (Codex's) |
| B | S16 | prepare PR-2's freeze half now (independent of PR-1); hold the holdout half until PR-1 merges | `ledger.py`, `access.py`, `roles.py` |
| C | S14 | R12 (grid cap in the HTE registry), small and independent | as above |
| D | S15 | R2 (ops `Store` escaping) after #104; the macOS step for P1-g | `ledger.py` |
| E | S13 | **analysis only** (§3); no D-1 code | everything except a scratch directory |
| F | S12 | PR-3 harness against the prepared cap | existing files |
| review | independent reviewer | review each PR from the code alone; rerun its acceptance tests | — |

## 3. D-1: provisional investigation of Option A (no implementation)

Pending the independent S13-role review commissioned on 2026-11-22. Its result and S17's reading of it are recorded
below when it returns. Until then, nothing about D-1 is implemented or recorded, and θ_M3 and the M1 field list
stay unset.
