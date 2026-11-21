# Manhattan Phase 4, session 3: simulation status, development reporting and held-out readiness

Written 2026-11-18 on branch `claude/phase4-simulation-readiness` from main at `f5f8045` (PR #80 merged). An
independent audit. **No simulation, development run or confirmation run was executed, no workflow was dispatched or
re-run, no held-out value was drawn, and no screening method is selected.** No protected path and no workflow file
was edited (checked with `python -m nightshift.protected`).

Synthetic data only throughout.

---

## Summary for the owner

1. **The full development programme has been run once, but nothing from it is on main and it is not complete.**
   Workflow run `43467828524` (dispatched by the owner on main at commit `1a7f653`, 2026-11-13) finished 224 of 225
   pieces. 41,226 replications were made: every STD and LONG development run at 2,000, D11 at 2,000, eight of the
   nine hedged twins at 400, and all five HB runs at 400. **D04h is short by 32 replications (172 to 203)**: its
   piece reached its time budget. The collect job is red only because of that gap. Run `43467884866` was cancelled
   before it started any job.
2. **The HB records of that run no longer count on main.** The HB code hash covers the whole of
   `manhattan/ledger.py`. Three later operational commits (`436b9fd`, `135a035`, `2e54231`, the last one inside PR #80)
   edited that file. So main now computes `c864e57955126c37`, while the 2,000 HB records carry `4252b971831004e3`, and
   `collect merge` refuses them. The one change that touches the function the model calls
   (`evidential_weight` gained `and not reconstructed` on the reserve branch) cannot change the model's output,
   because the model never passes `reconstructed`. A deterministic test records this
   (`tests/test_manhattan_sim_readiness.py`). Whether those records may still be counted is a decision for you (D1
   below). It is not repaired here.
3. **Read on development scenarios only, these records show a candidate (i) failure and model failures.** Nothing
   is decided until the runs are complete for current code and you rule on D1; the details are in section 2.
   - **V3 fails in D07a** (serial correlation +0.2). SPA size at 0.05 is 0.0594 (0.0584 to **0.0604**) against an
     upper bound of 0.06. The pooled size at 0.001 is 0.00171 (0.0016 to **0.0018**) against 0.0015. This is
     version 1's code, which current main still computes, so it is a development FAIL for current code.
     Consequences:
     - Candidate (i) cannot be eligible (SIM_PREREG §7, step 1).
     - The within-family SPA component fails a required development criterion (§8.1).
   - **On the HB records (other code; computed, not decided):**
     - **V6 fails in D08** at year 10: the central model's calibration error is 0.114 (0.106 to **0.122**) against
       0.10. This is the known D08 concern (ETHAN_ACTIONS item 21(b)), now at full count.
     - **V8 fails**:
       - D05: candidate (i), in the "Promising" group at year 4 and the "Statistically supported" group at year 10.
       - D08: candidate (i) at year 4.
       - D10: candidate (ii) at year 10.
     - **V7 and V12 pass** in all five HB scenarios.
4. **The held-out confirmation cannot be built without someone using discretion.** The frozen text fixes the
   ranges, but for H01–H12 it does not say:
   - how a value is drawn from a range;
   - the order in which the generator is consumed;
   - whether each value is fixed per set or redrawn per replication, family or hypothesis.

   It also leaves scenario-level questions open, for every scenario. Construction is therefore stopped for your
   review. The ranges are encoded as data and tied verbatim to the frozen text (`manhattan/sim/heldout_spec.py`);
   nothing is drawn.
5. **The code implements the frozen procedures.** Three independent audits found no protocol-level mismatch and no
   implementation bug in SPA, the hedge-aware SPA, Romano-Wolf, Benjamini-Bogomolov, both screening candidates, the
   e-process, e-LOND, the tail-risk check, the analytic hierarchical model, tiers or dormancy. They list several
   readings of ambiguous text (section 4).

---

## Revision after the independent S6 review (2026-11-18)

| item | change |
|---|---|
| M6, small groups | Owner decision: **not evaluated does not mean passed.** Gates now read PASS, FAIL, NOT EVALUATED or NOT DECIDED, never merged. Candidate (ii) reads NOT EVALUATED, OWNER DECISION REQUIRED (D8). Candidate (i)'s FAIL is kept and selects nothing for (ii). No new rule was written, and every number is unchanged: section 2 of the snapshot and its file digests are byte-identical to the first version. |
| L1 | HB records read at non-default evaluation years are listed separately from otherwise valid old-code records, each with a `reason`. Only old-code records with the pre-registered calendar can be shown with `--include-stale`. |
| L2 | The "pilot only" state in the module documentation did not exist; the docstring now lists exactly the five states the code returns (checked by a test). |
| L3 | Held-out runs are counted as distinct run ids (started, completed, refused), not as start/end log events. |
| D08 | The 0.114 against 0.10 is explained separately: [D08_CALIBRATION_NOTE.md](D08_CALIBRATION_NOTE.md). |
| hash | The current hash is checked against what the code imports, and a narrower scheme is proposed for future runs only: [CODE_HASH_PROPOSAL.md](CODE_HASH_PROPOSAL.md). |

---

## 1. Workstream A: verified run status and artifact inventory

Source: the GitHub Actions API, read-only. No run was dispatched, re-run or cancelled.

### 1.1 Runs of `manhattan-sim.yml` (workflow id 417514128)

There are exactly two runs (`total_count: 2`).

| run | attempt | dispatched by | ref / commit | created (UTC) | status | conclusion |
|---|---|---|---|---|---|---|
| `43467828524` | 1 | EthanC100 (workflow_dispatch) | main / `1a7f6531b66d19116b8def8946a4a4ca46bd645a` | 2026-11-13 16:56:57 | completed (updated 2026-11-14 13:57:48) | **failure** |
| `43467884866` | 1 | EthanC100 (workflow_dispatch) | main / `1a7f653…` | 2026-11-13 16:57:18 | completed (updated 16:59:06) | **cancelled**: 0 jobs, 0 artifacts (it waited in the `manhattan-sim` concurrency group) |

**Jobs of run `43467828524` (227):**

- `plan`: success.
- 225 `piece` jobs: 224 success, 1 failure.
- `collect`: failure, at its step "Is anything still missing?". Every earlier step passed.

The failed piece is `D04h-STD-0006-0203` (job `132032036387`). It ran from 02:56 to 07:47 UTC. Its run-log record is
`end / interrupted / completed 166 of 198`, which is consistent with the 285-minute time budget (exit 75). The exit
code itself was not read from the job log: the tail retrieved shows only the upload, which succeeded.

**Code and pre-registration at that commit.** These were verified from the run-log records inside the artifact:

| item | value |
|---|---|
| commit, every one of the 450 records of the run | `1a7f653`, `dirty: false` |
| SIM_PREREG | `e4bbcc44…` |
| PROTOCOL_v3 | `4fbb5c72…` |
| SIM_PREREG_v2 | `65c19e68…` |
| PROTOCOL_v3.1 | `c4ce79d2…` |

All four equal the hashes recorded on main today (`python -m manhattan.prereg_v2 verify`: ok). Between `1a7f653` and
main nothing changed in `manhattan/sim/`, `manhattan/stats/`, the pre-registrations, the protocols, the workflow,
`requirements.txt` or the collector. The one exception is `manhattan/ledger.py` (section 1.4).

**Seeds.** Master seed `16481991856922281473`, which is the first 8 bytes of SIM_PREREG's SHA-256. The seed branch is
0 (development) on every record. Scenario keys are as in `manhattan/sim/seeds.py`. **No held-out or confirmation
branch appears anywhere: 0 held-out runs and 0 refusals are on record.**

### 1.2 Artifacts

Run `43467828524` has 226 artifacts: 225 pieces plus `manhattan-sim-results`. All are unexpired, all come from
`1a7f653`, and all expire 2027-02-11T16:56:57Z. The 225 piece artifacts were listed (names, sizes, digests) but
**not downloaded**. Their contents are covered by the merged artifact, which the collect job built with
`collect merge` (the same checks as at home).

| artifact | id | bytes | SHA-256 (GitHub digest) | downloaded and checked |
|---|---|---|---|---|
| `manhattan-sim-results` | 14116817108 | 7,062,106 | `a81b137cac29f964a9febcbd5fe74605628204916e09e9d574bc154886fe35e1` | **yes**: the local zip's SHA-256 equals the digest; 34 files, no links |
| `manhattan-sim-piece-D04h-STD-0006-0203` (the failed piece) | 14104389491 | 18,524 | `db761abb…6cb6a6c` | no (the job log confirms this digest at upload) |

### 1.3 Completeness, against the pre-registered counts and the code each record names

Counted from the downloaded records: unique replication numbers per file, the code hash on each record, and the
review step for HB.

| runs | records | code on the records | current main code | countable on main today |
|---|---|---|---|---|
| 16 STD runs of version 1 (D01–D09b, P1–P4) and D01, D02 at LONG | 2,000 each (0–1999), no duplicates | `da641c096d17bbf4` | `da641c096d17bbf4` | **yes, complete** |
| D11 at STD (version 2 code) | 2,000 | `9d1b680ff7e19ca7` | `9d1b680ff7e19ca7` | **yes, complete** |
| 8 twins (D01h, D02h, D03h, D05h, D06h, D07ah, D07bh, D08h) | 400 each | `9d1b680ff7e19ca7` | same | **yes**; precision target met for every one (half-widths 0.0038–0.0063 at 0.20 and 0.0015–0.0022 at 0.05, against 0.02 and 0.01) |
| D04h | **368 of 400**; missing 172–203 | `9d1b680ff7e19ca7` | same | **incomplete** |
| 5 HB runs (D01, D02, D05, D08, D10) | 400 each at review step 63 (plus older pilot records of other code) | `4252b971831004e3` | `c864e57955126c37` | **no**: other code (section 1.4) |

**What main holds.** It has only the pilots: 12 STD replications per run (6 for LONG and the twins, 36 for D11), and
no HB record of the current code. The full records were never committed. To reproduce the on-main state, run
`python -m manhattan.sim.dev_status`. To reproduce the artifact read, download the artifact and run
`python -m manhattan.sim.dev_status --out <dir> --include-stale`.

### 1.4 Why the HB records stopped counting

| ref | HB code hash (`run.code_hash("HB", version="v2")`) |
|---|---|
| `1a7f653` | `4252b971831004e3` |
| `origin/main` (`f5f8045`) | `c864e57955126c37` |

`manhattan/ledger.py` is one of the files `CODE_FILES_V2_HB` hashes (`manhattan/sim/run.py:62`). The model imports
one function from it, `evidential_weight` (`manhattan/stats/hier_analytic.py:61,178`). That file has changed since
the run in `436b9fd` (Phase 3B), `135a035` (capture v2) and `2e54231` (PR #80). The only change to
`evidential_weight` is on the reserve branch:

- before: `1 if (channel == "blind" and designated) else 0`
- after: `1 if (channel == "blind" and designated and not reconstructed) else 0`

The model calls it as `evidential_weight(str(c), "reserve", bool(d))`, so `reconstructed` is always False. Its output
is therefore identical. Both tests in `tests/test_manhattan_sim_readiness.py` pass:

- `test_the_model_reads_evidential_weight_with_its_default_reconstructed_flag` checks that the output is unchanged;
- `test_hb_code_hash_covers_the_whole_ledger_module` records that the hash covers the whole module.

**The rule is SIM_PREREG_v2 §9: "records of different code are never pooled". Whether an inert change to a hashed
file counts as "different code" is not a reading this session may make.** See D1.

---

## 2. Workstream B: development reporting

### 2.1 What the existing reporting path does, and the gaps

`manhattan/sim/report.py` and `report_v2.py` give every metric with its interval, threshold and verdict. A run below
its count is labelled "pilot: not decided", and the selection rule is shown with its numbers but explicitly "not
made". These gaps were found, and none is repaired in those files (they are the reports of record):

1. **Other code is reported as if it were current.** `report_v2.collect` falls back to "the most common code" when
   no record of the current code exists. `report.collect` always takes the most common code. Built on main today,
   with the run's records, `report_v2` would therefore print **pass/FAIL verdicts for the HB runs from records that
   `collect merge` refuses**. Only the code column would show the mismatch.
2. **Forward criteria are shown as required for both candidates and for E-ALL.** SIM_PREREG §2.5 says they "must
   hold for the candidate that is selected … and are reported for the other". `metrics.summarise` marks the M2 rows
   of (i), (ii) and E-ALL as required, so a non-selected candidate's row could read FAIL. The same holds for V8 per
   candidate.
3. **No status view separates the categories the owner needs:**
   - complete versus incomplete versus other code;
   - development versus held-out;
   - eligibility gates versus statistical failures.

   `cr.SELECTION_MARGIN` is never used in any computation. The selection rule is not implemented in code, which is
   correct at this stage.
4. **V8 hides which side of the bound a pilot is on** (H1 in section 4.3), and **nothing checks the years at which
   HB records are read** (H2).

### 2.2 What was added: `python -m manhattan.sim.dev_status` (read-only)

`manhattan/sim/dev_status.py` builds its verdicts only from the existing metric functions; it adds no new metric.

- **What it reads.** Only the record files under `--out`. It writes nothing unless `--md` or `--json` is given.
- **What it reports.** It sorts:
  - every run of the development plan into complete, incomplete, other code only, or nothing on file;
  - every required criterion into pass, FAIL, not decided, not evaluated (small group), or reported;
  - every gate into **PASS, FAIL, NOT EVALUATED or NOT DECIDED**, four states that are never merged. **Not evaluated
    does not mean passed** (owner decision, 2026-11-18, S6 review M6): a gate with a small-group row is NOT
    EVALUATED, never PASS.
- **Other code.** Records of other code are never given a verdict. With `--include-stale`, their numbers are shown,
  every verdict reads "not decided: records of other code (…)", and what the metric code would have said appears in
  a separate column marked "not a verdict".
- **Screening candidates.** It shows the development half of §7 step 1 per candidate: V1 and V4 where required, V3
  for (i) only, V10(a), and V11 for screening.
  - It never prints "eligible". It prints "not determined" with the reason, or **OWNER DECISION REQUIRED** where
    the frozen text does not settle the question (a required row not evaluated for a small group), and always
    "held-out half: not evaluated".
  - It prints "NO SELECTION": a development failure of one candidate selects nothing for the other.
  - It never computes the step-2 power comparison.
- **Components.** It shows the component gates of §8.1 rule 2: within-family tests, forward test, model tiers and
  dormancy.
- **Held-out and gaps.** It lists the held-out scenarios (coded? distinct runs started, completed and refused, by
  run id) and every missing or unverified
  item.
- **Integrity.** It prints the SHA-256 of every record file it read. Its output is deterministic: there is no clock,
  and the bootstrap seeds are those of `metrics`.

The snapshot from run `43467828524`'s artifact is [DEV_STATUS_RUN_43467828524.md](DEV_STATUS_RUN_43467828524.md).

### 2.3 What the development records say (read-only; nothing selected, nothing switched on)

| category | content |
|---|---|
| **Development, decided for current code** | 16 STD runs and the 2 LONG runs of version 1, D11, and 8 twins. |
| - statistical failures | **D07a V3**, as in the summary. V3 at 0.20 (upper 0.2184) and the Romano-Wolf rate (upper 0.0598) pass there. Every other required row passes: V1, V2, V4, V5, V11, V3 in D01–D06, D07b and D08, the hedge-aware V3 in D11 and all eight complete twins, and V10(a). |
| - not evaluated (small groups) | V4 for candidate (ii) in D01 (STD, LONG), D07a and P1: fewer than 200 families passed screening. |
| - fixed consequence, not a failure | V10(b): the D09b adaptive size is 0.335, so SPA p-values on windows with adaptive variants carry the label "descriptive, not error-controlled". |
| **Development, incomplete** | D04h: 368 of 400. |
| **Development, other code (not decided)** | the five HB runs, as in the summary. |
| **Held-out confirmation** | none coded, none run, nothing drawn. |
| **Pilot artifacts** | the 12/6/36-replication pilots on main and the earlier pilot reports in `results/manhattan_sim/`. They are labelled pilot by the existing reports. |
| **Method eligibility** | Candidate (i): **FAIL** on development (V3 in D07a, both rows kept as computed). Under §7 step 1 as written, it cannot become eligible in the current protocol version. Candidate (ii): **NOT EVALUATED, OWNER DECISION REQUIRED**. 70 required rows pass, but 4 V4 rows were not evaluated (D01 STD 0, D01 LONG 0, P1 3 and D07a 30 families passed, against 200). §5 says such a criterion "is not evaluated there"; §7 step 1 asks that a candidate "meets" V4 "in every scenario where they are required". The text does not say which governs, and not evaluated is not passed. Its held-out half has not run either. **Neither is called eligible, and no method is selected (D8).** |
| **Missing or unverified** | listed in section 1 and in the snapshot's section 6. |

The development records alone **do not** select a method. Under SIM_PREREG §7, a candidate becomes eligible only
after a confirmation run, and the choice is made once. Under §8.1 rule 1, a failure leads to a revised method in a
new protocol version; the threshold never moves. Whether to revise the SPA test for positively autocorrelated
returns is decision D3. Candidate (i)'s failure **does not** make candidate (ii) the choice: (ii) has unresolved
small-group rows (D8) and no held-out half.

---

## 3. Workstream C: held-out readiness

### 3.1 The frozen requirements

- **SIM_PREREG §3.2** defines H01–H11 by parameter ranges.
- **§8.2** says set `k` "fixes every range of section 3.2 by draws from a random generator seeded with the SHA-256
  of the text `manhattan-sim-heldout-<k>-` followed by this file's SHA-256".
- **SIM_PREREG_v2 §3.2** adds H12, seeded the same way from v2's hash.
- **The seed derivation** (`seeds.heldout_rng`) and the confirmation streams (branch `k`, or `10 + k` for the
  pooled re-run) are in `manhattan/sim/seeds.py`, which is version 1's hashed code.
- **No code calls `heldout_rng`.** A test now enforces this.

### 3.2 Determination: not implementable without researcher discretion

Four questions are open for every scenario (`heldout_spec.GENERAL`):

- **G1, distribution.** The distribution of a value drawn from a range is not stated (uniform, log-uniform,
  integers).
- **G2, order.** The order in which set `k`'s generator is consumed is not stated, so two faithful implementations
  draw different sets.
- **G3, level.** For each range, the text does not say whether it is fixed once per set or redrawn per replication,
  family or hypothesis. Several ranges only make sense below set level: a date per family, a β path per hypothesis.
- **G4, world streams.** Which random-stream ids a held-out world uses is not fixed, and version 1's stream ids are
  inside its hashed code.

Each scenario also has its own open questions; the full list is in `manhattan/sim/heldout_spec.py`. Examples:

| scenario | open question |
|---|---|
| H01 | how the other weights move when `w_c` is drawn |
| H02a, H02b | whether the overlapped returns are rescaled |
| H02c | which root `k` takes |
| H03, H04 | whether volatility "2-3 times" means σ or σ² |
| H05, H12 | the probabilities of the listed choices |
| H06 | class shares |
| H08m, H08x | crash frequency is given as a bound ("at least 2", "fewer than 1"), not a value |
| H09 | "not cheap" has no implementation in the HB pipeline |
| H10 | how the missingness rules combine, and the pipeline has no missing-data path |
| H11 | the order of the five layers |
| H12 | one correlation or one per pair; and H12 is outside the runner's logged held-out fence (`world.HELD_OUT` is hashed version-1 code), so `run --scenario H12` stops as an unknown scenario |

**Every component is therefore stopped for owner review (D4).** Nothing that could be used to draw a set was
written.

### 3.3 What was implemented, because the frozen text permits it

- **`manhattan/sim/heldout_spec.py`.** The ranges and fixed values of H01–H12 as data, each with the exact words of
  the frozen file, and the open questions per scenario. It has no random generator, no seeds and no world.
  `construction_allowed` is False for every scenario while anything is open.
- **Tests (`tests/test_manhattan_sim_readiness.py`):**
  - every quote occurs verbatim in its scenario's table row of the frozen file;
  - every number appears in its quote;
  - the module imports nothing that can draw;
  - no module calls `heldout_rng`;
  - the runner's held-out fence refuses without the tag, with a dirty tree, and for H12;
  - no held-out world is coded.

**Confirmation execution stays disabled, for three independent reasons:**

1. there is no `manhattan-sim-confirm-<k>` tag;
2. `run_scenario` refuses held-out worlds as "not built", even after the tag check;
3. no world exists.

---

## 4. Workstream D: scientific audit

Three independent read-only audits compared the code with PROTOCOL_v3.1, SIM_PREREG and SIM_PREREG_v2. Each check
was a small deterministic computation on hand-made inputs, compared with the formula worked by hand.

### 4.1 Verified as matching

- **Hedge** (§2.2): ridge κ = 0.1·trace(C′C)/K, a 756-day window, no hedge before 252 days, and the cost term.
  Hand value 0.473273158685859; the code agrees to 16 digits.
- **SPA** (§5.1–5.2):
  - Hansen's statistic and ω̂, the recentring threshold, p = (1 + #{T* ≥ T})/(B + 1), and the 999 → 9,999 rule;
  - the Politis-White block length with the Patton-Politis-White correction, L_max(1750) = 126 and L_min = 5.
- **Hedge-aware SPA**: one index sequence; the pseudo-series of 756 real days followed by the resampled window; the
  centre at the least-squares intercept (equal to 14 digits); the fast path equal to a direct re-hedge to 1e-16.
- **V13**: with no factor the hedge-aware test is exactly `spa.spa_test`.
- **Romano-Wolf**: uncentred t*, the ⌈(1−a)(B+1)⌉-th order statistic, step-down. M4 runs at the family's admission
  level.
- **Screening** (§4): γ(j; N) and its normalisation; candidate (i) (Batch-BH^PRDS levels, BH within the batch,
  admission level k·α_b/n); candidate (ii) (e-BH bars, for example 4,373.04 for n = 15, as the protocol says).
- **e-process** (§6):
  - Λ, the truncation at −6, component and family wealth, the guard (low_52 = −0.0975203 by hand and in code);
  - the variance-ratio rule, predictability (a perturbation after day t changes nothing before it), and the
    one-week settlement lag (a rejection reported at day 455 by hand and by code).
- **e-LOND** (§6.8):
  - the bar 1/(α γ_i (R + k)); exactly k rejections per period;
  - γ indexed by enrolment order; anytime validity argued from the supermartingale property.
- **Constants and labels**: E-ALL N_F (576 STD, 720 LONG), the truth labels, and M2, M5 and M6.
- **Tail-risk check** (§6.11, V15): U = 2.9957 / 4.7439 / 6.2958 and the floor of 12; no forward-test code imports
  it.
- **`criteria.required`**: matches the "required in" columns of SIM_PREREG §5.

The hierarchical model, tiers and dormancy are in section 4.3.

### 4.2 Readings of ambiguous text (documented, not changed)

| # | where | text | code | effect |
|---|---|---|---|---|
| R1 | SIM_PREREG §4 M4 | "per replication, among families that passed screening, the share …" (no "0 if none", unlike M1) | 0 for a replication where nothing passed, averaged over all (`pipeline.py:165,187`, `metrics.py:126`) | lowers M4 against the "exclude" reading; agrees with Benjamini-Bogomolov's definition |
| R2 | SIM_PREREG §2.5 | forward criteria hold for the **selected** candidate | M2 rows of both candidates and E-ALL marked required (`metrics.py:111-114`) | a non-selected candidate's row may read FAIL; `dev_status` notes this |
| R3 | SIM_PREREG_v2 §5 | twins: V3 only, V1/V2/V4 "not evaluated for a twin" | `criteria.required("V1", "D01h", "STD")` is True; harmless, because twins only go through `summarise_spa` | `dev_status.cr_required` encodes the twin rule |
| R4 | PROTOCOL §5.2 | "90th percentile" | `np.quantile` with linear interpolation | negligible |
| R5 | PROTOCOL §6.1, §2.4 | the scale "on the last day before the week", with s_t from data to t−1 | s at the week's first day, which includes the last day before it (`eprocess.py:95`) | still predictable |
| R6 | PROTOCOL §2.4 | "EWMA standard deviation" | root mean square about zero (stated in the docstring) | a drifting series has a larger scale |
| R7 | PROTOCOL §6.6 | 7-day lag; "bets for t use only periods before t" | lag applied to the reported rejection day only | equivalent while nothing is revised; matters for H10 |
| R8 | SIM_PREREG §4 M5 | "wealth" | the tracking wealth from the freeze for every component | stated in the report's deviations |
| R9 | PROTOCOL §6.11 | "worst week on the family's whole record" | the leading component's own Z by default (`tailrisk.py:327`) | V15 unaffected |
| R10 | SIM_PREREG §2.4, D11 | forward-null label | taken from the pre-hedge X; drift from hedge error is not in the label | not measured |

### 4.3 Hierarchical model, tiers and dormancy

**Verified as matching:**

- **Closed form and grid.** The closed form of §7.1 and the six models S0–S5 of §7.2(e) are implemented as
  written. The grid matches Appendix B: μ_A has 121 nodes from −0.9 to 1.5; τ_A, ψ, ν, μ_ρ, σ_ρ and ρ are as
  written, with pruning at e^18 and a cell cut at 1e-10.
- **The common share r.** It is floored at 0 and capped at 0.9: identical series give 0.9, opposite series give 0,
  and `Data(r_F=0.95)` raises.
- **The grid gate.** It is "≤ 1% mass on the end nodes of μ_A", and a review needs all six fits. Extreme data gave
  mass 0.0458 and failed the gate; ordinary data gave 0 and passed.
- **M12** counts all 40 reviews. A failure at a review that is not a read date gives FAIL at 400 replications.
- **Dormancy** (§9.1, `dormancy.py`). Inputs (0, 0.5, 0.25) give p^F = (0.0062, 0.9938, 0.5), and p^F is 1 before
  252 forward days. That is a correct one-sided p-value for "θ ≥ θ_min". Also checked:
  - the two-consecutive-reviews streak, and its reset;
  - a review that is "model not computed" changes nothing;
  - at the last date there is no forecast, and the family is reactivated at p^F = 0.15 but not at 0.149;
  - 200 forecast draws.
- **Tiers.** Π^min is the element-wise minimum over the six models. The §8.2 entry checks behave as written:
  Π^min 0.7999 refused; 503 forward days refused, 504 allowed; with Romano-Wolf, 251 refused and 252 allowed;
  a non-positive forward mean refused; the integrity flag refused.
- **V14**: the reserve weight comes only through `ledger.evidential_weight`.
- **Constants**: every threshold and count matches the frozen text, and V6 and V8 are decided only at years 4
  and 10.

**Findings, documented and not repaired:**

| # | severity | finding | evidence |
|---|---|---|---|
| H1 | reporting | Below its count, V8 prints only "pilot: not decided" (`metrics.py:269`); every other criterion adds "(within/outside threshold so far)". The pilot of record had D08 year 4, Promising, candidate (i) **outside** (−0.288, −0.415 to −0.198), and the progress prose cites only year 10. Run `43467828524`'s HB records show the same row at −0.274 (−0.295 to −0.254), outside at full count. | deterministic check: synthetic records with bias −0.3 read "pilot: not decided" at R = 12 and FAIL at R = 400 |
| H2 | robustness | `MANHATTAN_SIM_EVAL_YEARS` (`hb.py:58`) can change the years a record is read at. The metric code does not check them: 400 records read at (2, 7) produce no V6 or V8 row at all, and records with mixed years would be pooled. Every record of run `43467828524` has (2, 4, 7, 10). | `dev_status` now treats such records as other records: `test_hb_records_read_at_other_years_do_not_count` |
| H3 | reading | **r**: "sample correlation … over their common dates". The code standardises each series by its own full-record mean and standard deviation (version 1's estimate, which SIM_PREREG_v2 names). | two series overlapping on 200 days: 0.5351 in code, 0.4965 for the literal reading |
| H4 | documentation | The figures in PROTOCOL_v3.1 §7.2(d) for D08 (ECE 0.101 and 112 of 113) are from the earlier pilot; the quarterly pilot shows 0.0998 and 116 of 117. The conclusion is unchanged. | `MANHATTAN_PROGRESS.md:1085` |
| H5 | reading | The small-groups rule is applied to the Π^min and tier groups and to the ECE bins, not to M8's denominator. | `SIM_PREREG.md:222` |

**The known hierarchical calibration concern (D08).**

- **Not weakened anywhere.** The ECE bound is version 1's 0.10, there is no D08 exception in criteria, metrics or
  report code, the untried two-group prior (`hier_spike.py`) is imported by nothing, and the estimator matches
  M7's definition.
- **The pilot was at the bound.** Its value was 0.0998 (0.0357 to 0.1356), and the diagnosis is structural: one
  hump cannot fit two groups.
- **At 400 replications it is over the bound.** The HB records of run `43467828524` (other code, not decided) give
  **0.114 (0.106 to 0.122)**. The consequence is fixed in advance: no posterior-based tiers (SIM_PREREG_v2 §5).
- **D5 is the owner's decision.** Whether to ask for a two-group prior in a new protocol version (ETHAN_ACTIONS
  21(b), option (ii)) or to keep the tiers off (option (iii)).

**Not confirmed:** the accuracy of the S5 forecast approximation in `support_probability`, declared in §9.1; and
`cluster_ci.py` and `hier.py` (§7.4), which decide nothing and were not reviewed in depth.

### 4.4 Screening-method selection gates

The selection rule exists only as text and as the numbers `report.py` prints. No function applies it, which is
correct: it may be applied only after a confirmation run. `dev_status` evaluates only the development half of step 1
and never step 2.

V3 is required in D07a, and that row currently fails. So, as the frozen §7 is written for the current protocol
version, candidate (i) cannot become eligible, whatever the held-out results.

**This does not select candidate (ii).** Step 3 ("one eligible: choose it") needs a candidate that *is* eligible,
and candidate (ii) is not. Four of its required V4 rows were not evaluated because fewer than 200 families passed
screening. Not evaluated is not passed, and whether such a row can ever count as "met" is the owner's to decide
(D8). It is not settled by a rule made here. Its held-out half has not run. **No selection.**

---

## 5. Validation

See the PR description for the exact commands, counts and exit codes. In short:

- `tests/test_manhattan_sim_readiness.py` (new): all pass.
- The full repository suite: run with its exit code checked (`-p no:cacheprovider`, no pipe).
- `python -m manhattan.prereg verify` and `python -m manhattan.prereg_v2 verify`: both ok.
- `python -m nightshift.protected` on every changed path: none protected.
- `dev_status` run twice on the same records gives byte-identical Markdown and JSON.

Not run, by instruction: any Monte Carlo experiment, development simulation, benchmark, `--v10a`, or held-out or
confirmation run.

---

## 6. Owner decisions needed before any confirmation

| id | decision | why it is yours |
|---|---|---|
| **D0** | Confirm in writing that Protocol v3.1 and SIM_PREREG_v2 are **adopted**. ETHAN_ACTIONS item 19 still reads "drafts … not in force", but CODEOWNERS (`1a7f653`, item 19 step 4) protects them and you dispatched the run under v2. | adoption is the owner's act; `ADOPTED_PROTOCOLS` in ops is empty |
| **D1** | May HB records made by code `4252b971831004e3` count under SIM_PREREG_v2 §9, given that the only difference is the inert `evidential_weight` change? If not, the five HB runs (about 520 CPU-hours) must be re-run for the current code. Separately, for future runs only: the narrower "code scheme 2" of [CODE_HASH_PROPOSAL.md](CODE_HASH_PROPOSAL.md), which hashes shared modules by function from a manifest and adds a closure test, because the current hash is both too broad (all of `ledger.py`) and too narrow (`spec.py`, `availability.py`, `stats/hier.py` and `prereg.py` are imported but not hashed). It never recomputes old identities and does not validate the old records. | "different code" is a reading of a frozen rule |
| **D2** | Complete D04h (replications 172–203) with a run that has `earlier_runs=43467828524`, from main, then bring the records home (SIM_RUNBOOK §8). | runs are dispatched by you only |
| **D3** | D07a V3 fails on development. Choose between revising the SPA test (a new protocol version, then a retest; the threshold does not move: §8.1 rule 1) and accepting that candidate (i) and the within-family SPA claims stay off. Under §7 this also decides whether the comparison of step 2 can ever arise. | a protocol-level consequence; must not be repaired silently |
| **D4** | Fix the held-out draw protocol (G1–G4) and answer the per-scenario questions of `heldout_spec.py` **before** any held-out value is drawn: an addition to `SIM_PREREG_AMENDMENTS.md` (§8.4: correcting a scenario's description) or a new pre-registration version. Also decide whether the missing-data path (H10), "not cheap" (H09) and the multi-factor hedge layer (H12) are built as pipeline code under a new code hash. | every answer is researcher discretion |
| **D5** | The hierarchical results on the HB records, if D1 lets them count: V6 in D08, 0.114 (0.106 to 0.122) against 0.10, explained separately in [D08_CALIBRATION_NOTE.md](D08_CALIBRATION_NOTE.md) (item 21(b), option (ii): a two-group prior in a new protocol version, or (iii): the posterior tiers stay off); and V8 in D05, D08 and D10. | a failing component is not switched on (§8.1 rule 2); revising the model is a new version |
| **D6** | Whether forward criteria (M2) and V8 rows should be marked "reported" for the non-selected candidate in the report of record (reading R2), and whether M4's "0 if none" reading (R1) stands. Whether to fix the report-of-record gaps of section 2.1 and H1/H2: those files' code is not hashed, but they are the reports of record. | readings of frozen text |
| **D7** | Tag `manhattan-sim-confirm-1` only after D0–D5 and D8 are settled and every required development criterion is met (§8.1 rule 4). | the tag is the confirmation switch |
| **D8** | **Small groups and eligibility.** The owner has ruled that not evaluated is not passed, so a small-group row stays unresolved. Still open: what happens to a candidate whose only open rows are small groups, as candidate (ii) is now (V4 in D01 STD, D01 LONG, P1, D07a)? Options: it can never become eligible on those scenarios; the rows are settled in the held-out run or a larger run; or a written reading of §5 against §7 step 1 (an amendment under §8.4 or a new version). The reporter shows OWNER DECISION REQUIRED until then. | the frozen text does not settle it |
