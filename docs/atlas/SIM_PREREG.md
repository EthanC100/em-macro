# Atlas simulation pre-registration

Version 1.0, written 2026-11-12, before any simulation code exists.

**What this file is.** The rules by which the statistical methods of [PROTOCOL_v3.md](PROTOCOL_v3.md) will be tested
on **synthetic** data before any of them is allowed to produce a claim. It fixes the scenarios, the metrics, the
numeric thresholds, the number of replications and the rule that chooses between the two screening candidates.

**What it is not.** It is not a pre-registration of a trial on market data. It adds nothing to `trials.csv` or
`docs/prereg/`, and no market result may enter any decision described here.

**Frozen.** The SHA-256 of this file is recorded in `docs/atlas/sim_prereg.sha256` in the same commit, and a test
(`tests/test_atlas_prereg.py`, added in the commit that follows) checks it. This file is never edited. Additions go in a separate append-only file
(section 8.4). At the commit that adds this file, the repository contains no simulation code: no `atlas/sim/`
directory and no data-generating code for these scenarios.

**Method under test.** PROTOCOL_v3.md version 3.0.0, SHA-256
`60653417d3e9ce9934ba14c05975d0de4021bb2b22260106c7508bb7454668d5` (commit `b2f2fa5`, the commit before this one). A
later version tested under this pre-registration is named, with its SHA-256, in the report of the run that tested
it.

---

## 1. Claims to be tested

| id | claim of Protocol v3 | section there |
|---|---|---|
| C1 | each screening candidate keeps the false discovery rate at or below 20% at every batch end | §4.3, §4.4 |
| C2 | the SPA p-value has the right size; Romano-Wolf keeps the family-wise error rate; the Benjamini-Bogomolov link keeps the average error over selected families | §5 |
| C3 | a null component's betting wealth reaches `1/a` with probability at most `a`; e-LOND keeps the forward false discovery rate at or below 5% at every time | §6 |
| C4 | what is lost by truncation is measured, and the guard limits it where the data can show it | §6.3 |
| C5 | posterior probabilities from the hierarchical model are calibrated well enough for the tier rules, when the truth does not come from the model's priors | §7 |
| C6 | the dormancy rule rarely abandons a family that has an edge | §9 |
| C7 | the Sharpe ratio reported for a family in a tier is not biased upwards by selection | §7, §8 |
| C8 | the chosen methods have non-trivial power | §4, §6 |

---

## 2. The simulated world

### 2.1 Time

A period is one trading day; 252 days a year; 5 days a week. Each family has an exploration window of 1,260 days,
then a reserve window of 1,750 days, both ending at its batch's freeze; forward days follow the freeze. Batches are
frozen at equal intervals over 10 years (2,520 days) and the programme ends at day 2,520 (`T_end`).

### 2.2 Programme sizes

| size | batches `B` | blind families per batch `n_b` | hypotheses per family | variants per hypothesis | screening schedule `N` | forward schedule `N_F` |
|---|---|---|---|---|---|---|
| STD | 40 | uniform on 8..16 | 2 | 6 | 48 | 120 |
| LONG | 100 | uniform on 4..8 | 2 | 4 | 120 | 300 |
| HB | 24 | 10 | 2 | 4 | 29 | 60 |

The schedule is `γ(j; N)` of Protocol v3 §4.2. STD and HB scale `N` to 1.2 times their number of batches so that the
procedures are tested at the load they were designed for; LONG uses the production values. `n_b` is drawn before any
return is simulated and never depends on results.

### 2.3 Returns

The simulation generates core-hedged net returns of executables directly (one executable per variant), except in
scenario D11, which generates unhedged returns and core factors and runs the hedge of Protocol v3 §2.2.

```
X_{v,t} = σ_{f,t} · ( μ_{v,t} + ε_{v,t} )
ε_{v,t} = √w_c · ℓ_f · c_t  +  √w_g · g_{f,t}  +  √w_u · u_{h,t}  +  √w_e · e_{v,t},      w_c + w_g + w_u + w_e = 1
μ_{v,t} = θ_{v}(t) / √252
```

`c_t` is common to all families, `g_{f,t}` to a family, `u_{h,t}` to a hypothesis, `e_{v,t}` to a variant; they are
independent, with mean 0 and variance 1, from distribution `D`. `ℓ_f` is +1 or −1. `σ_{f,t}` is a volatility
process with unconditional mean square 1. `θ_v(t)` is the variant's true annualised edge at time `t`.

**Defaults** (used unless a scenario says otherwise):

| item | default |
|---|---|
| weights `(w_c, w_g, w_u, w_e)` | (0.05, 0.25, 0.30, 0.40): correlation 0.60 between variants of a hypothesis, 0.30 between hypotheses of a family, 0.05 between families |
| `ℓ_f`, `σ_{f,t}`, `D` | +1; 1; standard normal |
| share of families with an edge, `π_1` | 0.05 |
| a family with an edge | with probability 0.5 both hypotheses have it, otherwise one |
| hypothesis edge `θ_h` | 0.5, 1.0 or 1.5 with probabilities 0.5, 0.3, 0.2 |
| variant edge | `θ_h · q_v`, `q_v` uniform on (0.5, 1.0) |
| a variant with no edge | mean exactly 0 (the least favourable null) |
| history versus forward | the same edge on exploration, reserve and forward (no decay) |
| generator | each family is one draw from the pool (no selection) |
| channels | blind only |
| data | complete, never revised; every family cheap (Protocol v3 §9.2) |

**The truth is never drawn from the model's own priors.** Edges are discrete or bounded, retention (where used) is
two-point or uniform, and group structure differs from the model's. No scenario may draw a parameter from the
distributions written in Protocol v3 §7.1.

### 2.4 Truth labels

- **Reserve-null family:** every variant's mean over the reserve window is at most 0.
- **Forward-null family:** for every component (each hypothesis portfolio and the family portfolio), the mean of the
  untruncated return over the family's forward life after enrolment is at most 0. This is the practical truth; it
  is deliberately the stated null of Protocol v3 §6.1 in its unconditional form, not the truncated one.
- **Family with an edge of at least `θ_min`:** the time-averaged true Sharpe ratio of the family portfolio over its
  forward life is at least 0.25.

### 2.5 The pipeline under test

Protocol v3 as written, with four declared reductions for cost: (a) the bootstrap stops at 9,999 resamples; (b) in
STD and LONG runs the hierarchical model is not fitted, and enrolment in the forward test is by the screening route
only; (c) in HB runs the model and the tiers are evaluated at years 2, 4, 7 and 10 instead of quarterly, with the
"two consecutive reviews" conditions applied to consecutive evaluation dates; (d) scenario runs marked `E-ALL`
enrol every family at its freeze, to load e-LOND without depending on screening, with `N_F` set to 1.2 times the
expected number of families (576 for STD).

Every STD and LONG scenario is run once with each screening candidate. Forward metrics are computed for both; the
forward criteria must hold for the candidate that is selected (section 7) and are reported for the other.

---

## 3. Scenarios

Two groups. **Development** scenarios may be run as often as needed while the code is written and the methods are
revised. **Held-out** scenarios are run only in a confirmation run (section 8). Every item of the required list
appears in one group; the last column says where.

### 3.1 Development scenarios (parameters fixed here)

| id | scenario | change from the defaults | sizes |
|---|---|---|---|
| D01 | **no edges** | `π_1 = 0` | STD, LONG, HB; also STD with `E-ALL` |
| D02 | **rare edges** | `π_1 = 0.02` | STD, LONG, HB |
| D03 | **correlated variants** | weights (0.02, 0.08, 0.85, 0.05), so variants of a hypothesis correlate 0.95; 20 variants per hypothesis | STD |
| D04 | **correlated families** | weights (0.40, 0.20, 0.20, 0.20), all `ℓ_f = +1` | STD; also STD with `E-ALL` |
| D05 | **fat tails** | `D` = Student-t with 3 degrees of freedom, scaled to variance 1 | STD, HB |
| D06 | **volatility clustering** | `σ²_{f,t} = 0.5 s²_{mkt,t} + 0.5 s²_{f,t}`, each `s²_t = 0.02 + 0.10 · s²_{t−1} z²_{t−1} + 0.88 · s²_{t−1}` (unconditional mean 1), with `z = c` for the market term and `z = g_f` for the family term; `D` = Student-t with 5 degrees of freedom, scaled to variance 1 | STD |
| D07a, D07b | **serial correlation** | `g` and `u` are AR(1) with coefficient +0.2 (D07a) or −0.2 (D07b), rescaled to variance 1 | STD; D07a also with `E-ALL` |
| D08 | **historical selection bias** | each submitted family is the best of 20 pool draws by the family portfolio's realised Sharpe ratio on the **exploration** window | STD, HB |
| D09a, D09b | **adaptive variant generation** | an adaptive channel adds to every hypothesis 3 rounds of 6 variants; each round's variants are noisy copies (correlation 0.9) of the best variant so far on the exploration window (D09a) or on the reserve window, with `reserve.evaluate_adaptive: true` (D09b) | STD |
| D10 | **misspecified priors** | `π_1 = 0.15`; `θ_h` is 0.3 (probability 0.7) or 2.0 (0.3); null variants have mean −0.2; forward edge = retention × historical edge with retention 0 or 1, each with probability 0.5 | HB |
| D11 | hedge estimation | unhedged return = `β_t · C_t + X_t`; one core factor with annualised Sharpe ratio 0.6; `β_t` a random walk around 0.5 with annual standard deviation 0.3 | STD |
| P1-P4 | power | `π_1 = 0.05`; every family with an edge has both hypotheses at `θ_h` = 0.5 (P1), 1.0 (P2), 1.5 (P3), 2.5 (P4) | STD |

### 3.2 Held-out scenario families (parameter ranges fixed here; values drawn per set, section 8.2)

| id | scenario | definition and ranges | sizes |
|---|---|---|---|
| H01 | **negative dependence** | half the families have `ℓ_f = −1`, with `w_c` in [0.3, 0.6]; in addition a share in [0.2, 0.5] of families form mirror pairs inside a batch whose family components correlate −`r`, `r` in [0.6, 0.9] | STD; also `E-ALL` |
| H02a | **overlapping holding periods**, fresh marks | each variant's return is the sum of `H` overlapping one-day positions, `H` in 5..21, marked to market daily | STD |
| H02b | overlapping multi-day returns or stale marks | each reported return is the average of the last `H` true daily returns, `H` in 2..21 | STD with `E-ALL` |
| H02c | mild staleness | reported return = `(1−k) x_t + k x_{t−1}`, with `k` chosen so that first-order autocorrelation is in [0.03, 0.10] | STD with `E-ALL` |
| H03 | **regime changes** | a two-state Markov chain (expected stay 500-1,500 days calm, 60-250 days stress); in stress, volatility is 2-3 times higher and edges are zero; separately, 30% of families with an edge lose it for good at a uniform date in their reserve window | STD, HB |
| H04 | **stress correlation spikes** | 1-3 episodes per decade of 20-60 days in which `w_c` rises to [0.7, 0.9] and volatility is 2-4 times higher; a share in [0.5, 1.0] of families have `ℓ_f = +1` | STD; also `E-ALL` |
| H05 | **generator contaminated by knowledge of past winners** | each submitted family is the best of `K` pool draws by realised Sharpe ratio over exploration **and reserve**; `K` in {10, 30, 100}; `π_1` in [0.01, 0.05] | STD, HB |
| H06 | **decay after discovery, heterogeneous by mechanism** | three mechanism classes; forward edge = retention × historical edge, with retention 1 (class A), 0.3 or 0.7 (class B), 0 with probability 0.6 else 0.5 (class C); the forward edge then halves every `h` years, `h` infinite (A), in [3, 6] (B), in [1, 2] (C) | STD, HB |
| H07 | misspecified priors, second form | `θ_h` log-uniform on [0.2, 3]; null variants have mean uniform on [−0.4, 0]; `π_1` falls linearly from 0.10 in the first batch to 0.01 in the last | HB |
| H08m | **rare-event strategies**, moderate | a share in [0.05, 0.20] of null families earn a steady premium and lose `J` daily standard deviations on a crash day, with zero mean overall; `J` in [15, 40]; crash probability set so that at least 2 crashes are expected in the family's forward life | STD with `E-ALL` |
| H08x | rare-event strategies, extreme | as H08m with `J` in [100, 400] and fewer than 1 crash expected in the forward life | STD with `E-ALL` |
| H09 | **dormancy then reactivation** | a share in [0.2, 0.4] of families with an edge have none for the first 2-5 years after freeze and the full edge afterwards; an equal share lose their edge after 2-5 years; 20% of families are not cheap | HB |
| H10 | **missing observations and revisions** | 1-5% of days missing at random at their due time; a day with a standardised return beyond 3 in absolute value is 10 times as likely to be missing; gaps of 1-5 days; 2-5% of observations are revised after the 7-day lag by noise of 0.5 standard deviations plus 0.1 in the strategy's favour; 1-3% of executables stop for good with a final loss of 5-20 standard deviations | STD with `E-ALL`, HB |
| H11 | composite | Student-t with 4 degrees of freedom, D06's volatility, H01's dependence, H05 with `K = 10`, H06's decay and H10's missing data together | STD, LONG, HB |

**Split.** Development holds the scenarios needed to build and debug each component in isolation. Held-out holds the
structurally different dependence, non-stationarity and data-quality cases, which are the ones most likely to break
a method that was tuned on the development group.

| required item | where | required item | where |
|---|---|---|---|
| no edges | D01 | stress correlation spikes | H04 |
| rare edges | D02 | historical selection bias | D08 |
| correlated variants | D03 | contaminated generator | H05 |
| correlated families | D04 | adaptive variant generation | D09a, D09b |
| negative dependence | H01 | decay after discovery, by mechanism | H06 |
| fat tails | D05 | misspecified priors | D10, H07 (and section 2.3 for all) |
| volatility clustering | D06 | rare-event strategies | H08m, H08x |
| serial correlation | D07a, D07b | dormancy then reactivation | H09 |
| overlapping holding periods | H02a, H02b, H02c | missing observations and revisions | H10 |
| regime changes | H03 | | |

---

## 4. Metrics

All metrics are computed per replication and summarised over replications. A replication is one whole simulated
programme.

| id | metric | definition |
|---|---|---|
| M1 | realised screening FDR | per replication, the share of screening rejections that are reserve-null (0 if none); mean over replications; at batches 10, 20, 40 (LONG: 25, 50, 100) |
| M2 | realised forward FDR | per replication, the share of e-LOND rejections that are forward-null; at years 3, 5 and 10 |
| M3 | SPA size; Romano-Wolf FWER | share of reserve-null families with `p_f ≤ a` for `a` = 0.20, 0.05, 0.001; share of families in which Romano-Wolf at level 0.05 rejects at least one variant with no edge |
| M4 | linked average error | per replication, among families that passed screening, the share in which Romano-Wolf at the family's admission level names at least one variant with no edge |
| M5 | crossing probability | share of components with no edge whose wealth ever reaches 20, and 100, within the programme |
| M6 | power | screening: share of families that are not reserve-null and are rejected; forward: share of families that are not forward-null, frozen in the first quarter of the programme, and formally supported by `T_end`; median years to formal support |
| M7 | calibration of posterior probabilities | from HB runs: for families with `Π^min ≥ 0.80`, and with `Π^min ≥ 0.40`, the share whose true edge is at least `θ_min`; for the central model, the reliability curve in ten equal bins and its expected calibration error (the count-weighted mean absolute gap between stated and observed frequency, over bins with at least 200 family observations) |
| M8 | premature-elimination rate | among families with a true edge of at least `θ_min`, the share dormant at `T_end` or dormant for more than half their forward life; in H09, among late-starting families, the share dormant when their edge began and not reactivated by the second evaluation date after it began |
| M9 | selection bias in reported Sharpe | for families in tier Promising or higher (and separately Statistically supported or higher), the mean of (posterior mean of `θ_f` under the central model − true `θ_f`); beside it, the same for the naive estimate (best variant's sample Sharpe ratio over all its data) |
| M10 | tail-blind certification | in H08m and H08x, the share of rare-event null families formally supported by `T_end` |
| M11 | adaptive SPA size | in D09b, the share of reserve-null families with `p ≤ 0.05` when the test is recomputed on the full ledger set after the adaptive rounds |

**Confidence intervals.** For a mean of per-replication values, a two-sided 95% interval `mean ± 1.96 · sd / √R`.
For a ratio whose denominator varies by replication (M6-M9), a percentile interval from 2,000 bootstrap resamples of
whole replications. "Upper bound" and "lower bound" below mean the ends of these intervals (so each is a one-sided
97.5% bound).

---

## 5. Acceptance thresholds

A criterion is **required** in the scenarios listed for it. Every threshold is a number fixed here.

| id | criterion | threshold | required in |
|---|---|---|---|
| V1 | screening FDR (M1), each checkpoint | upper bound ≤ **0.22** | every development and held-out scenario run at STD or LONG, **except** H05 and H11, where the reserve is contaminated by construction, and H08x, where the disaster is usually absent from the reserve; there M1 is reported only |
| V2 | forward FDR (M2), each checkpoint | upper bound ≤ **0.06** | every scenario run at STD or LONG, including H05 and H11; **except** H08x (reported only) |
| V3 | SPA size (M3) | upper bound ≤ **0.22** at 0.20; ≤ **0.06** at 0.05; ≤ **0.0015** at 0.001; Romano-Wolf FWER upper bound ≤ **0.06** | D01-D08, D11, H01, H02a, H03, H04 |
| V4 | linked average error (M4) | upper bound ≤ **0.22** | as V1 |
| V5 | crossing probability (M5) | upper bound ≤ **0.06** for 20; ≤ **0.015** for 100 | D01, D05, D06, D07b, H01, H04 |
| V6 | calibration (M7), at years 4 and 10 | for `Π^min ≥ 0.80`: lower bound of the true share ≥ **0.70**; for `Π^min ≥ 0.40`: lower bound ≥ **0.30**; central model's expected calibration error: upper bound ≤ **0.10**; in D01, the share of all family evaluations with `Π^min ≥ 0.80`: upper bound ≤ **0.01** | every scenario run at HB |
| V7 | premature elimination (M8) | upper bound ≤ **0.10**; in H09, for late-starting families, ≤ **0.25** | every scenario run at HB |
| V8 | selection bias (M9), at years 4 and 10 | upper bound of the bias ≤ **+0.10**; lower bound ≥ **−0.25** (annualised Sharpe units), for both tier groups | every scenario run at HB |
| V9 | rare events | H08m is subject to V2 with the practical truth of section 2.4; H08x: M10 is reported with no threshold, as the measured size of the guarantee lost in Protocol v3 §6.3 | H08m, H08x |
| V10 | adaptive variants | (a) the designated blind p-values and e-values of record are bit-for-bit identical with and without the adaptive channel: **required**; (b) if the upper bound of M11 exceeds **0.06**, SPA p-values on windows holding adaptive variants are labelled "descriptive, not error-controlled" in every Atlas report. (b) is a consequence fixed in advance, not a failure | D09a, D09b |
| V11 | power floors (M6), scenario P4 | screening power of the selected candidate: lower bound ≥ **0.50**; forward power by `T_end`: lower bound ≥ **0.50** | P4 |

**Small groups.** If a group defined by a condition (for example `Π^min ≥ 0.80`, or "passed screening") holds fewer
than 200 family observations over all replications of a scenario, the criterion on that group is not evaluated
there, and the count is reported.

**What the thresholds can and cannot tell apart.** With the replication counts of section 6, a method whose true
rate is at or below the nominal level passes each V1-V5 check with probability at least 97.5%, and a method whose
true rate exceeds the nominal level by twice the tolerance (0.24 for a 0.20 level, 0.07 for 0.05) fails with
probability at least 97.5%. A method whose true rate lies between the nominal level and the threshold may pass:
that band is the stated resolution of this test.

**Reported without a threshold:** every metric in every scenario where it is not required; M1 in H05, H11 and H08x;
M10 in H08x;
power in P1-P3 and elsewhere; the naive estimate's bias; running time.

---

## 6. Replication counts

**Precision target.** The 95% interval of an estimated error rate must have half-width at most 0.02 when the
nominal level is 0.20 and at most 0.01 when it is 0.05; for calibration shares and elimination rates, at most 0.05.

**Derivation.** A per-replication value in [0, 1] with mean `a` has variance at most `a(1 − a)`. The half-width is
`1.96 · √(a(1−a)/R)`.

| quantity | worst-case standard deviation | target half-width | replications needed | used |
|---|---|---|---|---|
| rate at level 0.20 (V1, V4) | √(0.20 × 0.80) = 0.400 | 0.02 | (1.96 × 0.400 / 0.02)² = 1,537 | **2,000** |
| rate at level 0.05 (V2, V3, V5) | √(0.05 × 0.95) = 0.218 | 0.01 | (1.96 × 0.218 / 0.01)² = 1,825 | **2,000** |
| share or rate from HB runs (V6, V7) | 0.5 (a share near one half, families within a replication fully dependent) | 0.05 | (1.96 × 0.5 / 0.05)² = 385 | **400** |

So: **2,000 replications** for every scenario at STD or LONG, and **400 replications** for every scenario at HB.
With 2,000 the half-widths are at most 0.0175 and 0.0096. The 0.001-level check in V3 pools all reserve-null
families of all replications (about a million tests in a STD scenario); its interval is the bootstrap over
replications.

A replication count is never lowered. If a run cannot finish in the time available it is continued, not cut.

---

## 7. Method-selection rule

The two screening candidates of Protocol v3 §4.3 and §4.4 are each run on every scenario. The choice is made once,
after the first confirmation run in which at least one candidate is eligible, by these steps:

1. **Eligibility.** A candidate is eligible if it meets V1 and V4 in every scenario where they are required
   (development and held-out), V10(a), and V11 for screening. Candidate (i) must also meet V3, because its inputs
   are SPA p-values.
2. **Both eligible.** Compute each candidate's screening power (M6) at the final checkpoint in P1, P2, P3 and P4 and
   average the four. Choose **candidate (i) only if** its average exceeds candidate (ii)'s by at least 0.05 and the
   95% bootstrap interval of the difference excludes zero. **Otherwise choose candidate (ii)**, whose guarantee does
   not depend on the dependence between families.
3. **One eligible.** Choose it.
4. **None eligible.** No screening route exists: section 8 applies.
5. The choice, the numbers behind it and the commit of the code that produced them are written to the selection
   report. **No market result, from any window, enters the choice.** After it is made, changing the screening
   method requires a new major version of the protocol and a new pass.

The other components (within-family tests, the forward e-process and e-LOND, the hierarchical model, tiers and
dormancy) have no alternative candidate. Each is implemented only if it meets its required criteria.

---

## 8. Failure, revision and retest

### 8.1 Rules

1. **A threshold is never weakened to pass a method.** A method that fails is revised (a new version of
   PROTOCOL_v3.md with a change-log entry) and tested again.
2. **If nothing passes, no confirmation claim is implemented.** Concretely: a component whose required criteria
   are not met is not switched on (`claims.enabled` stays false for it), and everything that depends on it stays
   off: without a passing forward test there is no "Formally supported" tier; without a passing hierarchical model
   there are no posterior-based tiers and no dormancy; without a passing screening method there is no screening
   route to Promising.
3. Development scenarios may be run freely. Every run, including failed and abandoned ones, is logged (section 9).
4. Held-out scenarios are run **only** in a confirmation run, from a tagged commit, after all required criteria are
   met on the development scenarios.

### 8.2 Held-out sets

There are three held-out parameter sets, `k = 1, 2, 3`. Set `k` fixes every range of section 3.2 by draws from a
random generator seeded with the SHA-256 of the text `atlas-sim-heldout-<k>-` followed by this file's SHA-256.
Confirmation run 1 uses set 1. If a required criterion fails there for a component that has no passing alternative,
set 1 is **burned**: it becomes development material, the method is revised, the development scenarios are re-run,
and confirmation run 2 uses set 2; likewise set 3. If set 3 fails, this pre-registration is exhausted: nothing
further is implemented until a new pre-registration (version 2), written before any new simulation code and
stating what was learned, is committed with its own hash.

### 8.3 One pooled re-run

If a rate criterion fails with a point estimate above its nominal level but at or below its threshold (for example
0.205 against a level of 0.20 and a threshold of 0.22), that scenario may be extended **once** by three times the
original number of replications with new seeds; the decision is then made on all replications pooled. Nothing is
discarded. No other re-run of a confirmation scenario is allowed.

### 8.4 Amendments

This file is frozen. An append-only file `docs/atlas/SIM_PREREG_AMENDMENTS.md` may: correct an error in a scenario's
description, stating the error; add scenarios, metrics or held-out sets; raise a replication count; tighten a
threshold. It may **not** loosen a threshold, lower a replication count, remove a scenario or a required criterion,
or change the selection rule. Any of those needs version 2 of this pre-registration, and voids earlier passes.

---

## 9. Records and reporting

- Every simulation run appends one record to `results/atlas_sim/runs.jsonl`: time, commit, protocol hash, this
  file's hash, scenario, size, held-out set if any, replications, seeds, status. A held-out run before a tagged
  confirmation run is a breach and is reported as one.
- A confirmation report gives, for every scenario and metric, the estimate, its interval, the threshold and
  pass/fail, with nothing omitted; the selection steps of section 7; every deviation from this file, however
  small; and the list of earlier runs.
- **Seeds.** The master seed is the first 8 bytes of this file's SHA-256, read as an integer. Each (scenario, size,
  replication) stream is spawned from it with `numpy.random.SeedSequence`, with a separate branch for development
  runs and for each confirmation run.

---

## 10. What this simulation does not show

1. That real returns resemble any scenario. A pass means the methods work in the worlds written here.
2. That historical screening is valid on real history. In H05 the generator knows the reserve; V1 is not required
   there, because no method can meet it. The real case is somewhere between D08 and H05 and cannot be measured.
3. Anything about a truncated-away tail that has not yet happened (H08x).
4. That error rates hold beyond the simulated length. LONG runs 100 batches; the production schedule allows 120
   and a tail.
5. That the hierarchical model's priors are right. V6-V8 show only that the tier rules tolerate the misspecified
   truths of sections 2.3, D10 and H07.
6. Anything about execution, capacity or costs: returns here are net by assumption.
