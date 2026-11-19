# S13: research methodology for very large hypothesis populations

Session S13, 2026-11-19, branch `claude/keen-goodall-r3089c`, from main at `9b24bd7`. Written independently of S6,
S11, S12, S14 and S15.

**Status: an assessment and a set of synthetic tests. Nothing here is in force.** No protected path, frozen protocol,
pre-registration, trial definition, evidence classification, reserve control, threshold or configuration was
changed (`python -m nightshift.protected` passes on every changed path). No workflow was dispatched. No real, licensed,
reserve or forward data was read. **Every number below describes a synthetic generator. A synthetic "discovery" is a
check of a procedure and never a trading signal.**

Code: `manhattan/methodology/` (outside every simulation code hash; a test checks this). Tests:
`tests/test_manhattan_methodology.py` (25 tests, about 6 seconds). Results: `results/manhattan_methodology/E*.json`,
each stamped with the commit, a clean-tree flag and the master seed. Reproduce with
`OPENBLAS_NUM_THREADS=1 python -m manhattan.methodology.experiments --out <dir>` (about one hour on 4 cores).

---

## 0. Summary for the owner

1. **The procedures Manhattan has are sound for the programme they were designed for. They have not been tested at
   the scale now being built.** The pre-registered simulation covers 24 to 100 batches of 4 to 16 families (at most
   about 600 families a programme) and 4 to 20 variants a hypothesis. The engine on PR #89 processes 10^6 candidates, which in its workload are
   5 families with about 51,000 variants each. Nothing between those two scales had been measured.
2. **Grid size is the first scientific constraint, not compute.** The bar the best of `m` variants must clear grows
   like `√(2 ln m)`. A single real variant needs a true Sharpe ratio of 0.94 to be found 80% of the time over the
   6.9-year reserve at 5% when it is alone, 1.53 among 200 variants (the `manhattan.spec.MAX_GRID` cap) and 1.92
   among 51,214 (E1b, `ρ = 0.5`). At the bar the screening schedule actually applies to a first rejection
   (`p ≤ 0.00023`) these become 1.65, 2.10 and 2.45. Dense effects (every variant has the edge) are found by the
   family portfolio whatever `m` is (E1).
3. **Duplicated candidates break the scientific meaning of the error rate while the theorem still holds.** BH-type
   procedures control the error rate over the units they are shown. When true claims are registered several times,
   the share of *scientific* discoveries that are false rises far above the level: offline BH at 20% gives 0.13 over
   units and **0.55 over scientific classes** with tenfold copies of true families; candidate (i) goes from 0.015 to
   0.057, and the chance of at least one false class from 0.14 to 0.61 (E4). Null duplicates instead halve power
   (0.13 to 0.07). **Showing the procedure one unit per scientific class restores class-level control in every case
   tested.** This answers PR #86's open decision D-1 (section 2.3).
4. **Registering a candidate after looking at the window it is tested on invalidates the test completely**: mining
   1,000 null families on a window and testing the best 50 on the same window gives a false discovery rate of 1.00;
   testing them on a fresh window gives the nominal 0.20 (E6). Effect estimates on the selection window are about
   twice the truth (winner's curse) and unbiased on a fresh window.
5. **Rerun shopping matters for data and code, not for bootstrap seeds.** Keeping the best of 10 reruns with a new
   data vintage or code version (correlation 0.9) raises the 5% size to about 0.12, and to 0.25 at correlation 0.5;
   keeping the best of 20 bootstrap seeds of the real SPA raises it only to 0.055 (E6).
6. **The realistic funnel ends with very few defensible strategies.** On the protocol-scale planted world (1,500
   families, 5% with edges of Sharpe 0.5 to 1.5), candidate (i) passes about 10 families at screening, almost all
   true. If half of a historical edge survives forward, **0.3 families on average reach formal 5% forward support
   within 10 years, and 0.015 within 5** (E7). Candidate (ii) passes about 1.8 and reaches 0.07. This is the
   arithmetic of Protocol §6.9, now measured end to end.
7. **No existing benchmark supports a statistical claim at scale** (section 8). HTE's benchmarks support throughput,
   determinism and accounting claims on synthetic data. The development simulation supports per-family and
   across-family operating characteristics at its own scale on development scenarios only.

The prioritised blockers are in section 10; the measurable acceptance criteria for moving from synthetic throughput
testing to historical exploratory research are in section 9.

---

## 1. What exists, and what it already settles

Inspected before anything was designed (all read on 2026-11-19):

| component | where | settles | does not settle |
|---|---|---|---|
| Protocol v3.1 (draft, not adopted) | `docs/manhattan/PROTOCOL_v3.1.md` | evidence levels; screening candidates (i) Batch-BH^PRDS and (ii) e-BH/e-LOND; SPA with the hedge re-estimated; Romano-Wolf; Benjamini-Bogomolov; forward e-process, e-LOND at 5%; tail-risk check; analytic hierarchical model; tiers; dormancy | what the counting unit is when candidates are duplicated; grid sizes beyond ~20; programmes beyond ~120 batches or ~600 families |
| Architecture | `docs/manhattan/ARCHITECTURE.md` | four levels with content-addressed IDs; data roles; one designated evaluation per (batch, domain); evidential-weight table; rerun detection | the executable ID folds in the code version (section 3) |
| Statistics | `manhattan/stats/` | every method above, checked against the papers by three audits (PR #83) | nothing about scale |
| Simulation | `manhattan/sim/`, SIM_PREREG v1 and v2 | per-family SPA size; screening FDR and power; selection (D08), adaptive variants (D09a/b), correlated families (D04), hedge (D11) at STD/LONG/HB sizes | grids beyond 20 variants, more than ~600 families, duplicated candidates, opposite-sign families, rerun shopping; no held-out scenario is built (PR #83) |
| Attempt accounting | PR #80 (merged), PR #86 (open) | attempt lifecycle; registered = completed + failed + aborted + unfinished; retries; anchored reconciliation | **D-1: the counting unit of any multiple-testing denominator** (open); D-10 exploration registration (open) |
| Evidence classification | PR #84 (open) | provenance, role, authorization and eligibility axes; every output non-eligible today | nothing statistical |
| HTE (hypothesis-testing engine) | PR #89 (open) | throughput (10^6 candidates in 7.4 minutes on 4 vCPU); determinism; crash-safe accounting; behavioural aliases; semantic duplicates reported | any statistic's validity; `independent_statistical_tests: null` by design |

---

## 2. Scientific-family membership and accounting (priority 1)

### 2.1 Definitions

| term | definition | identity |
|---|---|---|
| **family** | one mechanism, one predicted sign, one named counterparty (ARCHITECTURE §3) | `AF-` (HTE `HF-`) |
| **hypothesis** | the family in one domain, with its frozen grid | `AH-` |
| **variant** | one point of a frozen grid | `AV-` |
| **scientific class** | the set of registered families that make the same claim on the same data. Built by merging families that share any equivalence key, transitively (`identity.merge_classes`) | smallest family ID in the class |
| **look** | one scientific object, bound to a universe, cost and sizing, under one methodology, on one window in one role | `identity.look_key` |
| **computation** | one look with a given data hash, code version and numerical environment | `identity.computation_key` |
| **attempt** | one scheduled execution covering one or more computations | the start record's hash (PR #80) |

### 2.2 Membership rules (proposed; outcome-blind)

Two families belong to the same class when any of these holds:

- **M1, declared economics.** Same semantic digest of the declared economics: signal definition, universe, data
  sources, sign. Family and hypothesis prose are excluded. HTE already computes this digest and reports overlaps as
  `semantic_duplicates`; it does not merge them.
- **M2, behaviour.** Bit-identical family-portfolio positions on the exploration window (HTE's behavioural
  fingerprint, applied at family level).
- **M3, near-duplicates.** Correlation of family-portfolio **positions** (never P&L) of at least a threshold on the
  exploration window. The threshold is Ethan's; 0.9 was used in E4 to show what is at stake.

Two families with opposite signs on the same signal are **different classes**, and the critic should flag them as a
mirror pair (section 4.5). A mechanism taken to a new domain is a new family with `parent_family` (ARCHITECTURE §3);
it is a new class unless M1 to M3 apply.

### 2.3 What counts, where (a proposed answer to PR #86 D-1)

| quantity | counted in | role |
|---|---|---|
| attempts, retries, interruptions | the census only | scheduling; **never** a denominator. Every attempt has one terminal (PR #80, PR #86) |
| computations | rerun detection | same result: one look; different result: nondeterminism, the class is suspended (ARCHITECTURE §4.2) |
| looks per (class, window, role) | the designated-look rule | at most one designated look; any other look on that window has weight 0 (ARCHITECTURE §6.2). A changed data hash or code version on the same look is a **repeated look**, not a new object |
| variants of a family on a window | the SPA test's `m` | every variant ever evaluated there, including adaptive and failed-after-read ones (Protocol §5.3). Exact behavioural aliases inside a family change nothing (the maximum over duplicated columns is the same) and are harmless |
| **families per batch, `n_b`** | the screening procedure | **one unit per scientific class**: the first unit of a class (in freeze order) is tested; later units of the class inherit its decision, enter no denominator and earn no reward. This is the remedy measured in E4 |
| rejections, `R` | the online reward and every report | counted per class |

**Failures.** A family whose designated computation failed after reading data stays in `n_b` with `p = 1` (or
`E = 0`): both are valid null statistics, so the bound holds, and dropping the family would make the denominator
depend on what happened. A failed-after-read variant must be retried under the same identity before the family's
designated statistic is computed; if it cannot be, the family's statistic is descriptive. Nothing is deleted.

The census (`identity.census`) computes every row of this table from layered records and lists the violations that
make a statistic descriptive (multiple designated looks per class and window, nondeterminism, repeated looks,
unfinished attempts). It is a specification in code and is not wired to PR #86's Ledger or HTE's log; wiring it is
an owner decision (D-1, D-10).

---

## 3. Separating hypothesis identity, evaluation identity and scheduling (priority 2)

| layer | what it identifies | fields | invariance required |
|---|---|---|---|
| scientific | the claim | family, hypothesis, variant (content hashes) | independent of code, data, schedule |
| evaluation: look | one look at evidence | + binding (universe, cost, sizing), methodology, window, role | independent of code version, data hash, schedule |
| evaluation: computation | one execution of that look | + data hash, code version, numerical environment | independent of schedule |
| scheduling | how work was done | attempt, chunk, worker, order, retry | must change no result and no count |

`identity.scientific_key` refuses code, data or scheduling fields; `look_key` refuses scheduling fields; the census
is unchanged when chunks, workers and order change (tested).

**One divergence from the current architecture.** ARCHITECTURE §3 defines the executable `AX-` as
`{variant, universe, cost model, sizing, code version}` and says a bug-fixed code version is a new executable of the
same variant. Read literally, a re-execution after a code change is a *new object* and could receive a new designated
evaluation on a window it has already been evaluated on. Under the layering above it is a **repeated look** of the
same object. PR #86 and HTE already keep `code_version` as a separate field of an attempt, so the fix is a rule, not
new machinery: the designated-look key must exclude the code version. Recommended for Ethan's review; ARCHITECTURE.md
was not edited here.

HTE's identities map cleanly: `HF/HH/HS/HV` are scientific, `HC` (candidate = variant + cost + sizing) is the look's
binding, and HTE's run identity combines look fields (policy, window, stages, execution timing) with computation
fields (data hash, code digest, numerical environment); splitting the two is what the designated-look rule needs. HTE's chunk attempts are scheduling. HTE's family-scoped behavioural dedup is M2 inside a family; across
families it only reports, which is where E4 applies.

---

## 4. Multiple testing at scale (priority 3)

### 4.1 Within a family: grid size and SPA (E1, E1b)

**Analytic (E1b).** The bar the best of `m` equicorrelated variants must clear, and the smallest true Sharpe ratio
of a *single* real variant found with 80% power over the 6.9-year reserve window (1,750 days). `ρ` is the
correlation between variants. The last column uses the bar candidate (i) applies to the first rejection of a
programme (`0.20 × γ(1; 120) / 15 = 0.00023`).

| variants `m` | 5% bar (`ρ` 0 / 0.5 / 0.9) | Sharpe found at 5%, `ρ` 0.5 | at the first screening bar, `ρ` 0.5 |
|---|---|---|---|
| 1 | 1.64 / 1.64 / 1.64 | 0.94 | 1.65 |
| 6 (one SIM_PREREG STD hypothesis) | 2.39 / 2.29 / 2.00 | 1.19 | 1.82 |
| 200 (`MAX_GRID`) | 3.47 / 3.20 / 2.45 | 1.53 | 2.10 |
| 10,000 | 4.41 / 3.94 / 2.81 | 1.82 | 2.35 |
| 51,214 (HTE 10^6 workload, per family) | 4.75 / 4.21 / 2.93 | 1.92 | 2.45 |
| 1,000,000 | 5.32 / 4.64 / 3.14 | 2.08 | 2.60 |
| 10,000,000 | 5.73 / 4.94 / 3.28 | 2.20 | 2.71 |

**Bootstrap SPA against the oracle (E1).** Rejection rates at the 5% level of the real test (`manhattan.stats.spa`,
unchanged: estimated block length, `B` extended to 9,999), the oracle and the one-sided test of the equal-weight
family portfolio. Daily Gaussian returns, 1,750 days; "sparse": one variant at Sharpe 1.5; "dense": every variant at
0.5. 200 replications (100 at `m = 3,000`; a 95% half-width is about ±0.03 near 0.05 and ±0.07 near 0.5).

| `m` | `ρ` | null: SPA / oracle / portfolio | sparse 1.5: SPA / oracle / portfolio | dense 0.5: SPA / oracle / portfolio |
|---|---|---|---|---|
| 6 | 0.5 | 0.030 / 0.020 / 0.050 | **0.94** / 0.93 / 0.23 | 0.45 / 0.45 / 0.56 |
| 60 | 0.5 | 0.055 / 0.040 / 0.055 | 0.85 / 0.86 / 0.07 | 0.55 / 0.52 / 0.60 |
| 600 | 0.5 | 0.040 / 0.040 / 0.030 | 0.73 / 0.73 / 0.05 | 0.54 / 0.50 / 0.58 |
| 3,000 | 0.5 | 0.090 / 0.070 / 0.050 | **0.60** / 0.61 / 0.04 | 0.55 / 0.50 / 0.61 |
| 6 | 0.9 | 0.065 / 0.060 / 0.055 | 0.95 / 0.94 / 0.15 | 0.38 / 0.38 / 0.40 |
| 3,000 | 0.9 | 0.060 / 0.030 / 0.020 | 0.89 / 0.87 / 0.07 | 0.40 / 0.41 / 0.40 |

1. **The bootstrap SPA tracks the exact null at every grid size tried**, within sampling error, up to 3,000 variants
   (the null rate at `m = 3,000`, `ρ = 0.5` is 0.09 ± 0.06 against the oracle's 0.07). Scale does not break the test;
   it removes its power.
2. **Sparse effects are lost as the grid grows** (0.94 to 0.60 from 6 to 3,000 variants at `ρ = 0.5`), less so when
   variants are highly correlated (0.95 to 0.89 at `ρ = 0.9`), because correlated grids hold fewer independent
   chances.
3. **Dense effects do not depend on `m`**, and the portfolio test finds them as well as SPA does. The portfolio test is
   useless for sparse effects (0.04 to 0.23). This is the trade the Protocol already makes (§2.3: a hypothesis is
   judged on its whole grid); a large grid makes it sharper.
4. Consequence: **a bounded grid is a scientific requirement**. 51,214 variants per family (HTE's workload) needs a
   single-variant Sharpe ratio of about 1.9 to 2.5 to be found; a search that wide should be declared as many
   families with small grids, or as dense hypotheses tested on their portfolio.

### 4.2 Across families: null calibration at scale (E2)

Complete null (no class has an edge), so every FDR is the probability of at least one false screening. Scales:
"protocol" 100 batches × 15 (1,500 families), "large" 120 × 100 (12,000), "huge" 120 × 1,000 (120,000). `a` is the
share of each family's return common to every family on the window. Replications 400 / 200 / 50; ± is a 95%
half-width.

| scale | window | `a` | (i) Batch-BH^PRDS | (ii) e-BH/e-LOND | offline BH | offline BH: mean false discoveries per programme |
|---|---|---|---|---|---|---|
| protocol | shared | 0.05 | 0.147 ± 0.035 | 0 | 0.177 ± 0.037 | 1.1 |
| protocol | shared | 0.30 | 0.087 ± 0.028 | 0 | 0.115 ± 0.031 | **31.8** |
| protocol | disjoint | 0.05 | 0.163 ± 0.036 | 0 | 0.210 ± 0.040 | 0.3 |
| protocol | disjoint | 0.30 | 0.142 ± 0.034 | 0 | 0.193 ± 0.039 | 0.3 |
| large | shared | 0.05 | 0.140 ± 0.048 | 0 | 0.155 ± 0.050 | 0.6 |
| large | shared | 0.30 | 0.045 ± 0.029 | 0 | 0.080 ± 0.038 | **169.0** |
| large | disjoint | 0.05 | 0.215 ± 0.057 | 0 | 0.245 ± 0.060 | 0.3 |
| large | disjoint | 0.30 | 0.115 ± 0.044 | 0 | 0.145 ± 0.049 | 0.3 |
| huge | shared | 0.05 / 0.30 | 0.12 / 0.14 (± 0.10) | 0 | 0.12 / 0.14 | 62 / 81 |
| huge | disjoint | 0.05 / 0.30 | 0.10 / 0.20 (± 0.11) | 0 | 0.16 / 0.22 | 0.3 / 3.3 |

1. **No bound is shown to fail at any scale.** Candidate (i) keeps its 0.20 level even with one shared window, where
   its theorem does not apply (Protocol §4.3, failure mode 1); every interval contains or lies below 0.20.
2. **A shared window makes errors arrive together.** The rate is an average; with a strong common factor, a programme
   on one shared window either makes no false screening or makes dozens at once (169 per failing programme at 12,000
   families). The average is controlled; the outcome of the one programme Manhattan will actually run is close to
   all-or-nothing. Disjoint slices remove the clustering (0.3 per programme). This is an argument for
   `reserve.mode: disjoint_slices` that the error rate alone does not show.
3. Candidate (ii) made no false screening in any null programme: it is valid and, at these sizes, nearly inert.

### 4.3 Across families: power at scale (E3)

5% of classes have an edge (variant Sharpe ratios 0.5 / 1.0 / 1.5 times a share uniform on (0.5, 1)), shared window,
`a = 0.05`. "dense": every variant of a class carries the edge; "sparse": one of six does.

| scale (true classes) | effect | (i) FDR | (i) power | (i) discoveries | (ii) power | offline BH FDR / power |
|---|---|---|---|---|---|---|
| protocol (75) | dense | 0.016 | **0.133** | 10.2 | 0.022 | 0.169 / 0.314 |
| protocol (75) | sparse | 0.015 | 0.102 | 7.9 | 0.000 | 0.155 / 0.228 |
| large (600) | dense | 0.005 | 0.081 | 48.8 | 0.012 | 0.188 / 0.328 |
| large (600) | sparse | 0.004 | 0.063 | 38.2 | 0.000 | 0.172 / 0.235 |
| huge (6,000) | dense | 0.002 | **0.051** | 304.5 | 0.002 | 0.168 / 0.314 |
| huge (6,000) | sparse | 0.003 | 0.042 | 251.2 | 0.000 | 0.176 / 0.239 |

1. **Per-family power falls as the programme grows**, because the 20% budget is split over a fixed schedule of about
   120 batches: candidate (i) finds 13% of real edges at 1,500 families and 5% at 120,000. Its realised FDR falls in
   step (0.016 to 0.002): the budget is not lost to errors, it is left unspent.
2. **Candidate (ii) finds almost nothing** (2% of edges at protocol scale, none when one variant in six carries the
   edge, because the family portfolio dilutes it). It is the candidate whose validity does not depend on the shared
   window; its price at this size is power.
3. Offline BH shows what the online schedule costs: about 31% of edges at every scale. It is not admissible (the
   programme's size is unknown in advance), but the gap (0.31 against 0.05 to 0.13) is the cost of the guarantee at
   every batch end.
4. Absolute discovery counts still grow with scale (10 to 305). More families give more true discoveries in total
   at a lower rate each, provided the families are distinct classes (section 4.4).

### 4.4 Duplication (E4)

Protocol-scale programme (100 batches of 15 classes, 5% with edges, shared window), 200 replications. "unit" is the
error rate over registered families (what the theorems bound); "class" counts each scientific class once (what a
reader means). Offline BH (once over everything, at 20%) is a reference, not an admissible procedure.

| scenario | procedure | FDR unit | FDR class | P(any false class) | power (classes) | discoveries: units / classes |
|---|---|---|---|---|---|---|
| no duplicates | (i) | 0.015 | 0.015 | 0.14 | 0.138 | 10.5 / 10.5 |
| | (ii) | 0.000 | 0.000 | 0.00 | 0.024 | 1.8 / 1.8 |
| | offline BH | 0.181 | 0.181 | 0.84 | 0.333 | 33.7 / 33.7 |
| every class ×10, same batch, exact | (i) | 0.022 | 0.022 | 0.19 | 0.142 | 108.5 / 10.8 |
| | offline BH | 0.194 | 0.194 | 0.87 | 0.342 | 350.9 / 35.1 |
| true classes ×10, same batch, exact | (i) | 0.006 | **0.057** | **0.61** | 0.279 | 214.3 / 22.9 |
| | (ii) | 0.000 | 0.002 | 0.02 | 0.075 | 57.0 / 5.7 |
| | offline BH | 0.128 | **0.553** | 0.995 | 0.572 | 509.0 / 117.1 |
| true classes ×10, later batches, exact | (i) | 0.004 | 0.031 | 0.40 | 0.224 | 142.5 / 17.8 |
| | offline BH | 0.129 | **0.550** | 1.00 | 0.582 | 513.9 / 119.2 |
| same, 20% of classes with edges | (i) | 0.002 | 0.020 | 0.59 | 0.286 | 753.7 / 88.6 |
| | offline BH | 0.057 | **0.358** | 1.00 | 0.696 | 2,231.9 / 346.6 |
| null classes ×10, later batches | (i) | 0.015 | 0.004 | 0.04 | **0.074** | 5.9 / 5.7 |
| every class ×10, near copies (ρ 0.9) | (i) | 0.008 | 0.017 | 0.20 | 0.139 | 84.2 / 10.7 |
| | offline BH | 0.190 | **0.326** | 0.94 | 0.443 | 341.5 / 61.0 |
| every class ×10, later batches, **disjoint slices** (fresh data) | (i) | 0.006 | 0.012 | 0.22 | 0.270 | 50.2 / 20.7 |
| | offline BH | 0.189 | **0.481** | 1.00 | 0.728 | 297.5 / 108.3 |
| **any of the above, dedup-first** | (i), (ii), offline BH | = FDR class | ≤ the no-duplicate value + noise (largest 0.025 ± 0.007 for (i), 0.19 ± 0.02 for offline BH) | | 0.13 to 0.18 for (i) | units = classes |

What this shows:

1. **The theorems are not violated; their units are wrong.** Unit-level FDR stays at or below its level in every row.
   Class-level FDR does not: copies of true claims fill the denominator with correlated true "discoveries", so more
   false classes fit under the same rate. Offline BH reaches 0.55 at a 0.20 level.
2. **Online procedures are protected mainly by being very strict at this scale.** Candidate (i)'s class FDR rises
   3.8-fold (0.015 to 0.057) and its chance of at least one false class from 0.14 to 0.61, but stays below 0.20.
   That margin is not a design property: it disappears as the schedule loosens with discoveries, or if levels are
   ever raised.
3. **Duplicates of null claims cost power.** They inflate `n_b`, so every BH bar tightens: power falls from 0.13 to
   0.074.
4. **Re-testing a claim on fresh data is legitimate replication, but claiming the class when *any* copy passes is a
   multiplicity inside the class** (offline BH: 0.48 class FDR under disjoint slices). A replication must be a
   declared test of the same class, not a new unit.
5. **Dedup-first restores class-level control in every case**, at the cost of the "power" that duplicates of true
   claims appeared to add, which was never real evidence.

### 4.5 Negative dependence: opposite-sign twins (E5)

Same programme, a share of the null classes accompanied by a twin class that bets the opposite sign on the same
data, 300 replications.

| world | share mirrored | common share `a` | (i) FDR | (ii) FDR | offline BH FDR |
|---|---|---|---|---|---|
| complete null | 0 | 0.05 | 0.097 ± 0.033 | 0 | 0.140 ± 0.039 |
| | 0.5 | 0.05 | **0.173 ± 0.043** | 0 | **0.240 ± 0.048** |
| | 1.0 | 0.05 | 0.153 ± 0.041 | 0 | 0.197 ± 0.045 |
| | 0 / 0.5 / 1.0 | 0.30 | 0.063 / 0.083 / 0.053 | 0 | 0.090 / 0.117 / 0.113 |
| 5% edges | 0 / 0.5 / 1.0 | 0.05 | 0.018 / 0.023 / 0.024 | 0 | 0.171 / 0.191 / 0.200 |

Opposite-sign twins violate PRDS, the condition of candidate (i)'s theorem (Protocol §4.3, failure mode 2). Under the
complete null they move candidate (i)'s error from about 0.10 towards the 0.20 bound and offline BH to or above it
(0.24 ± 0.05). No row demonstrates a violation of candidate (i)'s bound at this replication count. Candidate (ii) is
unaffected, as its proof says. Recommendation: the critic flags mirror pairs; a mirror pair is tested as **one
two-sided class** (one unit, the larger of the two statistics, with the two-sided null), or the candidate in force is
(ii).

### 4.6 Selection, registration after a look, and reruns (E6)

**(a) Registration after a look.** A generator mines 1,000 candidate families on window A and registers the 50
with the best portfolio Sharpe ratio on A. They are then tested with BH at 20% (oracle p-values), on A itself or on a
fresh window B with the same true effects. 400 replications.

| world | tested on | FDR | P(any false) | mean true Sharpe of the 50 | estimate on A | estimate on B |
|---|---|---|---|---|---|---|
| no edges | same window A | **1.00** | 1.00 | 0 | 0.79 | 0.00 |
| no edges | fresh window B | 0.20 | 0.20 | 0 | | |
| 5% with edges | same window A | **0.48** | 1.00 | 0.55 | **1.08** | 0.55 |
| 5% with edges | fresh window B | 0.10 | 0.89 | | | |

Selecting and testing on the same window is not a weaker test; it is no test (every null rejection is false, every
replication). On a fresh window the same procedure is exact. Effect sizes read off the selection window are twice the
truth (1.08 against 0.55); on a fresh window they are unbiased (0.55). This is D08 and D09b of the pre-registered
simulation taken to its limit, and it is the reason for rules E-2 and E-4.

**(b) Rerun shopping.** A null family is recomputed `k` times (new data vintage, new code version) and the best
p-value is kept. Size of that best-of-`k` at the 5% level (oracle; 100,000 replications):

| correlation between reruns | k = 1 | 2 | 5 | 10 | 20 |
|---|---|---|---|---|---|
| 0.5 | 0.050 | 0.082 | 0.160 | 0.251 | 0.362 |
| 0.9 | 0.050 | 0.065 | 0.095 | **0.122** | 0.150 |
| 0.99 | 0.049 | 0.054 | 0.062 | 0.068 | 0.073 |

**(c) Bootstrap-seed shopping with the real SPA test** (`manhattan.stats.spa`, unchanged; 200 null families, 20
seeds each): size at 5% is 0.050 with one seed and **0.055 with the best of 20**; the standard deviation of `p_c`
across seeds is 0.010. The Protocol's extension of `B` to 9,999 below `p_c = 0.10` makes seed choice nearly
irrelevant. HTE already binds its bootstrap seed to the family's identity (S10 F6), which removes even this.

So the material risk is not the seed but the **data vintage and the code version**: a repeated look with changed data
or code is a new chance to pass. The designated-look rule of ARCHITECTURE §6.2 handles it, provided the look key
excludes the code version (section 3) and every later look carries weight 0.

---

## 5. Exploratory, confirmatory and forward evidence (priority 4)

These rules restate Protocol v3.1 and ARCHITECTURE §6 for a large population, and add what the experiments above
require. None of them activates a stage: `reserve.enabled`, `claims.enabled` and `freeze.authority` stay as they are,
and every confirmatory step stays Ethan's (CLAUDE.md hard rule 4).

| stage | data | who | weight | may claim | gate (unchanged) |
|---|---|---|---|---|---|
| synthetic throughput (now) | generated | any session | 0 | engineering properties; operating characteristics of procedures on stated generators | none |
| historical exploration (next) | exploration role, data to 2019-12-31, through `nightshift.explore_data` only | explorer, sessions | 0 | descriptive statistics with the full census; candidates nominated for registration | section 9 criteria; Ethan pre-registers the exploratory methodology |
| historical screening | reserve, one designated look per (batch, domain), blind channel | runner only | 1 at 20% | "passed screening at a 20% FDR on its reserve window" | `reserve.enabled` (Ethan) |
| confirmatory trials | as pre-registered in `docs/prereg/` and `trials.csv` | Ethan | per trial | per pre-registration | Ethan only |
| forward | data after each spec's freeze | runner records; anyone reads | 1 at 5% | "formally supported", with the tail-risk check | `claims.enabled` (Ethan), simulation passed |

Rules added for scale:

- **E-1. Units.** Every count reported at any stage states its unit (attempt, computation, look, variant, family,
  class). Only classes enter an across-family denominator; only variants enter a within-family one.
- **E-2. Registration precedes the look it is judged on.** A candidate nominated from exploration results is judged
  only on a window disjoint from every window its selection used, with the Protocol's embargo between them (E6).
- **E-3. Exploration is never evidence, however it is corrected.** Multiple-testing adjustments on exploration data
  may rank candidates; their outputs are never called discoveries.
- **E-4. Effect sizes come from windows that played no part in selection** (E6: the selection window overstates by
  about two).
- **E-5. One designated look per class and window**, keyed without the code version (section 3).
- **E-6. Bounded grids.** A hypothesis's grid is declared and bounded (`MAX_GRID = 200`), whatever the engine can
  process (E1b).

---

## 6. A realistic research funnel (priority 5)

The funnel below is measured, not assumed, on the protocol-scale planted world (E3, E7: 1,500 families, 5% with an
edge), with the stages Protocol v3.1 already defines. Numbers are means per programme over 200 replications.

| stage | unit | candidate (i) | candidate (ii) |
|---|---|---|---|
| candidates generated and processed | candidate (HTE) | any number: 10^6 costs minutes (PR #89) | same |
| scientific classes registered | class (section 2) | 1,500 | 1,500 |
| classes with a real historical edge | class | ~75 | ~75 |
| passed screening at 20% FDR | class | **9.8** (0.2 false) | **1.9** (0 false) |
| formally supported forward, 5%, by year 5 (retention 1 / 0.5) | class | 0.59 / **0.015** | 0.085 / 0 |
| formally supported forward, 5%, by year 10 (retention 1 / 0.5) | class | 6.7 / **0.33** | 1.3 / 0.07 |

Retention is the share of the historical edge that persists forward (Protocol §7). 0.5 is roughly in line with published
estimates of anomaly decay (McLean and Pontiff 2016: returns about 26% lower out of sample and 58% lower after
publication); here it is an assumption, not a measurement.

Forward support for a single enrolled family depends almost entirely on its forward Sharpe ratio and on how the 5%
budget is spread (E7, share of enrolled families formally supported, all families equally strong):

| enrolled | schedule `N_F` | Sharpe 0.5 (year 5 / 10) | 1.0 (year 5 / 10) | 1.5 (year 5 / 10) | 2.0 (year 5 / 10) |
|---|---|---|---|---|---|
| 10 | 10 | 0.002 / 0.042 | 0.056 / 0.55 | 0.48 / 0.98 | 0.92 / 1.00 |
| 10 | 300 (Protocol) | 0 / 0.002 | 0 / 0.16 | 0.05 / 0.87 | 0.58 / 0.99 |
| 50 | 300 | 0 / 0.002 | 0.002 / 0.30 | 0.13 / 0.92 | 0.79 / 1.00 |
| 300 | 300 | 0 / 0.001 | 0.001 / 0.51 | 0.46 / 0.97 | 0.91 / 1.00 |

(When many enrolled families are real, each rejection lowers the next bar, which is why 300 strong families do better
each than 10.) These forward figures are optimistic: every family is enrolled in week 0, its scale is known, and the
guard and the variance-ratio rule are off. Protocol §6.9's expected-time table agrees with them.

**What a realistic funnel looks like.** From any number of generated candidates, the defensible output in five years
is **zero to a handful of families that passed historical screening and are building a forward record**, and in ten
years **a few formally supported families, only if their forward Sharpe ratio after hedging and costs is at least
about 1.3**. The stages in between (Promising, Statistically supported) are posterior statements under a model and
are where most of the programme's information will sit. Three levers move the funnel; none changes validity:

1. **Distinct, strong, diversified families** (several weakly correlated domains raise a family portfolio's Sharpe
   ratio; Protocol §6.9). More candidates do not help; more *classes* help only in absolute count.
2. **A forward schedule sized to realistic enrolment.** With `N_F = 10` instead of 300, a Sharpe-1.0 family is
   formally supported by year 10 in 55% of records instead of 16%. `N_F` is a protocol constant; changing it is
   Ethan's decision, before any enrolment.
3. **Disjoint reserve slices** (section 4.2): they make the across-batch condition of candidate (i) true and remove
   error clustering.

---

## 7. What was tested, and how (priorities 6 and 7)

| experiment | world | metric | replications |
|---|---|---|---|
| E1 | one family, daily Gaussian returns, 1,750 days, `m` 6 to 3,000, `ρ` 0.5 or 0.9; null, one variant at Sharpe 1.5, every variant at 0.5 | rejection rate of the real SPA (`manhattan.stats.spa`, unchanged), the oracle and the portfolio test | 200 (100 at `m = 3,000`) |
| E1b | analytic, `m` 1 to 10^7 | 5% bar; single-variant effect found with 80% power | exact |
| E2 | complete null, 1,500 / 12,000 / 120,000 families, shared or disjoint windows, common share 0.05 or 0.30 | FDR (= probability of any rejection) | 400 / 200 / 50 |
| E3 | 5% of classes with edges, same scales, dense or sparse effects | FDR, power | 200 / 100 / 25 |
| E4 | section 4.4 | unit and class FDR, power, inflation | 200 |
| E5 | section 4.5 | FDR | 300 |
| E6 | selection after a look; correlated reruns; bootstrap-seed shopping with the real SPA | FDR, size | 400; 100,000; 200 families × 20 seeds |
| E7 | forward e-LOND on known Sharpe ratios; the end-to-end funnel | share formally supported by year | 50 to 200 |

The world (`manhattan/methodology/worlds.py`): each family has `m` equicorrelated variants observed over 350 weekly
test periods; a common factor shared by every family on a window slice (one slice for the whole programme, as the
shared reserve of ARCHITECTURE §6.2, or one per batch), a family factor and idiosyncratic noise. Candidate (i) gets an
**oracle** SPA p-value (the exact null of the best of `m` equicorrelated normals, `maxnull.family_p`); candidate (ii)
gets the Protocol §4.5 betting e-value of the family portfolio with the Protocol's grid and truncation, with the scale
known. Effects follow the development scenarios (Sharpe 0.5, 1.0, 1.5 with probabilities 0.5, 0.3, 0.2). The oracle
isolates the across-family layer from bootstrap error, which SIM_PREREG already measures; E1 compares the two.

**What this world leaves out**: fat tails, volatility clustering, serial correlation, estimated scale and hedge,
the variance-ratio rule, and costs. Each is a SIM_PREREG development scenario already. Results here are the best case
for those.

---

## 8. Which scientific claims existing benchmarks support (priority 8)

| benchmark | supports | does not support |
|---|---|---|
| HTE `BENCHMARKS.md` (PR #89): 10^4, 10^5, 10^6 candidates | throughput (2,311 candidates/s including registration on 4 vCPU); bit-identical determinism across chunking, workers, resume; complete attempt accounting (0 violations at 10^6); cost (about US$0.02 per 10^6 run) | **any statement about evidence.** The 10^6 run is 5 families, 15 hypotheses and 51,214 variants per family: one million candidates are five scientific claims. 39% are exact aliases. Same-close execution. Net-of-cost nulls make its null share "far below 5%" by construction, so it says nothing about calibration. Fixed block length 20, `B = 999`, no extension. No across-family procedure is run |
| `manhattan/ops/capacity.py`, `manhattan/sim/benchmark.py` | runtime and memory per executable or replication | nothing statistical (both say so) |
| Development simulation run `43467828524` (PR #83's audit) | per-family SPA size and screening FDR/power on 16 development scenarios at STD/LONG; hedge-aware SPA on twins; V3 fails in D07a (0.0594 against 0.06) | held-out scenarios (none built); HB records (stale code hash); any programme larger than ~1,500 families or grid larger than 20 |
| Pilot reports (`results/manhattan_sim/`) | motivated the 3.1 changes | decide nothing (they say so) |
| S13 experiments (this document) | operating characteristics of the unchanged procedures, in idealised Gaussian worlds, at scales up to 120,000 families and 3,000 (analytically 10^7) variants; the effect of duplication, mirroring, selection and reruns | anything about real markets; bootstrap error at scale beyond E1; fat tails and dependence beyond what SIM_PREREG covers |

The single sentence the benchmarks together support: **Manhattan can process 10^6 synthetic candidates cheaply and
account for every one; it cannot yet say what a rejection among them would mean.**

---

## 9. Acceptance criteria: synthetic throughput to historical exploratory research (priority 9)

Each criterion is measurable on synthetic data before any historical number is computed. Passing them all permits
**exploration** (weight 0, data to 2019-12-31) only; it changes no reserve, forward or claims switch.

| # | criterion | measured by | pass |
|---|---|---|---|
| A1 | D-1 decided: the counting unit is the scientific class per (window, role) | owner decision recorded | written decision |
| A2 | class merging (M1, M2, and M3 with Ethan's threshold) runs before any procedure, outcome-blind | a planted-duplicate synthetic workload with known classes | ≥ 99% of exact and semantic duplicates merged; 0 merges across opposite signs; dedup-first class FDR within the no-duplicate value + 2 standard errors in every E4 scenario |
| A3 | grids bounded | registration refuses a hypothesis grid above `MAX_GRID` | 0 accepted above the cap; HTE workloads re-specified within it |
| A4 | the engine's family statistic is calibrated | HTE stage-3 SPA against `manhattan.stats.spa` on a **zero-cost** null world, protocol block length, `B` extension | size at 0.05 within [0.04, 0.06] and at 0.20 within [0.18, 0.22] (95% intervals) for `m` up to the cap |
| A5 | realistic execution | HTE execution lag ≥ 1 and PR #85's cost model | merged and re-benchmarked |
| A6 | planted effects recovered and nothing else | a planted world with the exploration window's length, the real grids and both signs | power curve reported; 0 recoveries in the wrong sign; selection study (E6) reproduced on the engine: fresh-window FDR within level + 2 SE |
| A7 | complete census | `identity.census` (or its PR #86 equivalent) over a full synthetic exploratory run | balanced; 0 unexplained violations; class-level denominators reported per window |
| A8 | logging that hard rule 6 can carry | an owner decision on how 10^5 to 10^6 variants a run are logged (`nightshift.logs` writes one row per variant) | written decision, implemented |
| A9 | anchoring | HTE log head anchored outside the workspace at each run close | implemented, tested |
| A10 | the exploratory methodology pre-registered | Ethan files it (the explorer may only draft) | filed |
| A11 | independent review | a reviewer other than S13 reruns `tests/test_manhattan_methodology.py` and one experiment from its seed | bit-identical numbers |

---

## 10. Prioritised scientific blockers

| # | blocker | evidence | proposed resolution | owner |
|---|---|---|---|---|
| 1 | **The counting unit is undecided (PR #86 D-1)**, so no denominator can be computed at scale | E4 | scientific class per (window, role); dedup-first (section 2.3) | Ethan |
| 2 | **No class merging before screening.** HTE reports cross-family duplicates but the procedures would see every unit | E4: class FDR 0.55 (offline BH), 0.057 and P(any false) 0.61 for (i); power halved by null copies | M1 to M3 merge rules, outcome-blind; test A2 | design; Ethan sets M3 |
| 3 | **Grid size.** HTE's workload has ~51,000 variants a family against `MAX_GRID = 200` | E1b: single-variant 80%-power Sharpe 1.92 (5%) to 2.45 (first screening bar) | enforce the cap in every engine; large searches become many declared families or dense (portfolio) hypotheses | design |
| 4 | **The funnel yields almost nothing formally supported within 10 years unless forward Sharpe ≥ ~1.3** | E7, Protocol §6.9 | plan on the "Statistically supported" tier and forward records; enrol few, strong, diversified families; never enlarge enrolment to raise counts | Ethan (programme design) |
| 5 | **Screening power is low and falls with scale** | E3 | accept that historical screening finds only strong effects; do not scale family counts without re-deriving the schedule | Ethan |
| 6 | **Registration after a look invalidates screening** | E6: FDR 1.00 same window, 0.20 fresh | rule E-2; reserve stays runner-only and unseen by generators (ARCHITECTURE §8 lists why this cannot be enforced today) | design; Ethan (blind generator, item 3) |
| 7 | **Rerun shopping** across data vintages and code versions | E6 | rule E-5; look key without code version | design |
| 8 | **Opposite-sign twins break PRDS** for candidate (i) | E5 | flag mirror pairs; one two-sided class, or candidate (ii) | design |
| 9 | **The pre-registered simulation does not cover this scale** and held-out scenarios are not built | PR #83 | add scale, duplication and mirror scenarios to a future SIM_PREREG version (Ethan's to write) | Ethan |
| 10 | **Hard rule 6 cannot log 10^6 variants a run** | `nightshift.logs` writes one row per variant | owner decision (A8) | Ethan |
| 11 | This work uses oracle p-values and known scales | section 7 | SIM_PREREG's scenarios cover the rest; A4 checks the engine | — |

---

## 11. Reproduction and limits of this work

```
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/test_manhattan_methodology.py
OPENBLAS_NUM_THREADS=1 python -m manhattan.methodology.experiments --out results/manhattan_methodology            # all
OPENBLAS_NUM_THREADS=1 python -m manhattan.methodology.experiments --only E4 --out /tmp/s13                         # one
```

Each cell's random stream is `SeedSequence([20261119, crc32(cell name)])`, so a cell reproduces alone and whatever the
worker count, in one numerical environment. The JSON files record the commit and whether `manhattan/` was clean:
every file was written from a clean tree, E1b at `7aa3ee2` and the others at `3f56acd` (the only change between
them adds E1b's last column). As a check, E4 and E5 were rerun at
`7aa3ee2` with 2 workers instead of 4: every number was identical to the stored files.

Limits: one author; no independent review yet (criterion A11). Idealised worlds (section 7). The census is a
specification in code, not wired to any store. The membership rules M1 to M3 are proposals; M3's threshold is not
calibrated.
