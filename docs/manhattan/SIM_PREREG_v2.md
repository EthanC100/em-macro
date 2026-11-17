# Manhattan simulation pre-registration, version 2: the parts changed by Protocol v3.1

Version 2.0, written 2026-11-12 by session "5M Manhattan C", **after** the pilot on development scenarios and
**before** any full run, any held-out world is coded and any confirmation run. A draft for Ethan to adopt
([ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 19). Revised before adoption, and before any full or held-out run, by
sessions "6M Manhattan C" (2026-11-12) and "10M Manhattan C" (2026-11-13, on Ethan's decisions) to follow one more
change of the protocol under test, its dormancy rule (section 1, row 4): for that change **no threshold, metric,
scenario or replication count was touched**, only the description of the method. Session 10M also made
**amendment 1** (section 11): the HB runs are reviewed every quarter, as production reviews, in place of version
1.0's four dates. It tightens the test and loosens nothing. The same session added row 5 of section 1 and
criterion V15 (the tail-risk check of the protocol's new section 6.11 changes no test) and one paragraph of
section 9 (a run made in pieces).

**What this file is.** [SIM_PREREG.md](SIM_PREREG.md) (version 1.0) fixed how the methods of Protocol v3.0 are
tested on synthetic data. The pilot on its development scenarios showed two things that must be repaired before a
full run (section 1). [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md) repairs them. This file says how the **changed** methods
are tested. It covers only what changed.

**What stays.** Version 1.0 is not edited, its recorded hash still verifies, and it stays in force for everything
this file does not name: the simulated world, every scenario, every metric, **every threshold**, the replication
counts, the selection rule, the held-out sets, the failure rules and the seeds. One of its declared reductions
for cost, (c) of its section 2.5, is withdrawn for the HB runs by amendment 1 (section 11). Results obtained under version 1.0
for runs this file does not change are kept and are continued, not restarted.

**Frozen.** The SHA-256 of this file and of PROTOCOL_v3.1.md are recorded in `docs/manhattan/sim_prereg_v2.sha256`,
and `python -m manhattan.prereg_v2 verify` checks them together with version 1.0's record. A run of a changed part
refuses to start if either file no longer matches.

**Method under test.** For the changed parts: PROTOCOL_v3.1.md version 3.1.0, whose SHA-256 is the second line of
`docs/manhattan/sim_prereg_v2.sha256`, so that one check pins the two files together. For everything else:
PROTOCOL_v3.md version 3.0.0, as version 1.0 says. Sections 4, 6.1 to 6.10, 8.1 and 8.2 of the protocol, and
sections 9.2 and 9.3, are identical in the two versions. Section 9.1 keeps its thresholds (0.05 at two
consecutive reviews, 0.15) and gains a second condition in 3.1 (section 1, row 4). Section 6.11 is new in 3.1 and
sections 8.3, 8.4 and 8.5 name it (section 1, row 5): it adds a condition after the forward test and changes
nothing the simulation counts.

**Why a version 2 and not an amendment.** Version 1.0's section 8.4 lets an amendment add scenarios and tighten
thresholds, and its header lets a later protocol version be tested under it. Both happen here. But the changed
parts also need new readings of version 1.0's text (what a "fit" is when nothing is sampled; what the model's
estimates are), and those are easier to audit in one file with its own hash than scattered. Nothing here does
what section 8.4 forbids: no threshold is loosened, no replication count is lowered, no scenario or required
criterion is removed, and the selection rule is unchanged. No pass is voided, because no criterion has been
evaluated: every run so far is a pilot.

---

## 1. What the pilot showed, and what changes

`results/manhattan_sim/PILOT_REPORT.md`, 2026-11-12: 18 runs at STD and LONG with 12 and 6 replications against
2,000, deciding nothing. Development scenarios only. No held-out scenario has been coded or run.

| # | pilot result | change of method (PROTOCOL_v3.1.md) | tested here by |
|---|---|---|---|
| 1 | **D11**, the only scenario in which the core hedge is estimated: the SPA test rejects 0.077 (0.061 to 0.094) of families with no edge at the 0.05 level (bound 0.06), 0.269 (0.234 to 0.303) at 0.20 (bound 0.22); Romano-Wolf family-wise rate 0.077 (0.061 to 0.093) (bound 0.06) | §5.1: the hedge is re-estimated in every bootstrap resample by the live rule, and resampled means are centred at the window's least-squares intercept on the core factors | D11 again; nine hedged twins of the other development scenarios; a new held-out scenario H12 (sections 3 and 5) |
| 2 | **The model-fitting half produced no result.** One replication of D10 at HB, with the sampler at a fifth of its budget, was stopped unfinished after 2 hours 31 minutes of CPU time: of the order of 50,000 CPU-hours for the pre-registered runs | §7: an analytic normal-normal hierarchical model with closed-form posteriors on a fixed grid | every HB scenario, development and held-out, at the unchanged 400 replications (sections 2 and 5) |
| 3 | **D09b**: after adaptive search on the reserve, the SPA test on the full set rejects 0.344 (0.307 to 0.380) of families with no edge at 0.05 | none: the rule that adaptive-channel families carry zero evidential weight on the reserve was already in v3.0. It now cites this evidence and is enforced in code | a required code property (V14, section 5); V10 stands |
| 4 | **The pilot rerun of the 3.1 draft** (`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`, 12 replications a scenario, the first measurement of the dormancy rule): under 3.0's rule, families with a true edge that end dormant (M8) are 0.167 (0.045 to 0.261) in D02, 0.179 (0.138 to 0.216) in D05, 0.108 (0.081 to 0.138) in D08 and 0.146 (0.092 to 0.197) in D10, against a bound of **0.10** on the upper end | §9.1: a family becomes dormant only if the forecast `PP^max` and the one-sided p-value `p^F` of its own forward record against an edge of `θ_min` are both below 0.05 at two consecutive reviews (`p^F` needs 252 forward days); it is reactivated when either is at or above 0.15. Before, the forecast alone decided. (Until Ethan's decision of 2026-11-13 the draft held the model's `Π^max` in place of `p^F`; `results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md` has the two side by side) | V7 as it stands (M8 and its bound of 0.10 are version 1.0's, unchanged), in every scenario run at HB (sections 2 and 5) |
| 5 | **Not a pilot: a study of the forward test's estimand** (`results/manhattan_sim/v2/ESTIMAND_AND_TAIL_RISK.md`; synthetic single series, no programme, no pipeline, no pre-registered metric): for a strategy with rare large losses the truncated mean the test bets on can be positive while the mean is not (up to 0.45 of a Sharpe ratio hidden on the grid simulated) | §6.11: a tail-risk check required for Live-experiment eligible, Scale eligible, the label "Formally supported" and any profitability claim. It is applied after the test: an e-LOND rejection is still recorded and counted, and only the label is withheld | a required code property (V15, section 5). No scenario and no metric changes: M2, M6 and M10 count e-LOND rejections, as before, whether or not a label would be withheld; H08m and H08x (V9) stay the measure of what truncation lets through |

**Why this is not tuning to held-out results.** Version 1.0, section 3: development scenarios "may be run as often
as needed while the code is written and the methods are revised". D11, D09b and D10 are development scenarios. The
held-out scenarios of its section 3.2 have not been coded; the runner refuses them and its log shows no held-out
run. The three held-out parameter sets are untouched and none is burned. D02, D05 and D08, on which row 4 also rests,
are development scenarios too, and row 4's rerun was a pilot of the draft, made before adoption. Row 4 moves no
number: M8, its bound and the rule's own thresholds are as they were.

---

## 2. The pipeline under test: additions to version 1.0's section 2.5

The declared reductions (a), (b) and (d) of version 1.0 stand. Reduction (c) (the HB runs evaluated at four
dates instead of quarterly) is withdrawn by amendment 1 (section 11). Added:

**(e) The SPA test where a hedge is estimated.** In D11, its twins and H12 the designated SPA test and the
Romano-Wolf step-down are those of PROTOCOL_v3.1.md §5.1 and §5.4: one index sequence per resample for the
unhedged returns of every variant and for the core factor; the pseudo-series is the 756 actual days before the
reserve window followed by the resampled window; the ridge hedge of §2.2 is recomputed on it (756-day window,
252-day minimum, `κ = 0.1 · trace(C'C)/K`, ratios from earlier days only); the centre is the least-squares
intercept of each variant's unhedged return on the factor over the reserve window. The block length, the
999 → 9,999 rule, the seed of each family's bootstrap and the p-value are version 1.0's. Where returns are hedged
by construction the test is version 1.0's, by the same code as before (criterion V13).

**(f) The model at HB.** The six models of PROTOCOL_v3.1.md §7.2(e) are fitted by the closed form of its §7.1 on
the grid of its Appendix B. Readings fixed here:

- **Estimates.** `y^H_f` and `y^F_f` are annualised sample Sharpe ratios of the **family portfolio** `P_f` on the
  reserve window and on the forward record. A family has a forward estimate once it has 63 forward days.
- **Standard errors.** From the joint stationary bootstrap (199 resamples, one index sequence for the families
  of a batch, which share their dates), block length by Protocol §5.2.
- **The common share `r`.** For every pair of families with a forward estimate: the sample correlation of
  their two forward return series over their common dates, times the number of common dates divided by the
  geometric mean of the two record lengths (version 1.0's estimate of the correlation between two estimates,
  without its shrinkage half-way to zero). `r` is the average over all pairs, floored at 0 and capped at 0.9.
  It is the only information about dependence between families the model receives.
- **Mechanism classes.** Three, assigned at random at freeze, as in version 1.0's runs (H06 has real ones).
- **When a fit may be used.** At most 1% of the posterior mass of `μ_A` on the two end nodes of its grid.
  Otherwise the review is "model not computed" and changes no tier. A review needs all six fits.
- **Review dates (amendment 1).** Every 63 trading days: 40 reviews, at programme days 63, 126, ..., 2,520. At
  each one the six models are fitted to every family frozen so far, the forecast is made, and the tiers and the
  dormancy rule are stepped once. M7 and M9 are read at years 2, 4, 7 and 10 (reviews 8, 16, 28 and 40).
- **Dormancy forecast.** Version 1.0's (`manhattan.stats.tiers.support_probability`: a normal update of each
  model's posterior with simulated future records, not a refit), fed with 200 draws of `θ_f` per family and
  model from the closed-form posterior and with the quarterly reviews still to come. Not evaluated at the
  programme's last date.
- **Dormancy rule.** PROTOCOL_v3.1.md §9.1 (`manhattan.stats.dormancy`), stepped at every review, so that "two
  consecutive reviews" are a quarter apart: a family becomes dormant when `PP^max < 0.05` and `p^F < 0.05` at two
  consecutive dates, and is reactivated when either is at least 0.15. `p^F = Φ((y^F_f − θ_min)/s^F_f)` is
  computed from the `y^F_f` and `s^F_f` of this section for a family with at least 252 forward days, and is 1
  before that. At the last date there is no forecast: no family becomes dormant there, and a dormant family is
  reactivated there if `p^F ≥ 0.15`. The tiers are stepped by version 1.0's code, unchanged.
- **Truth.** A family has an edge of at least `θ_min` as version 1.0's section 2.4 says: the true forward Sharpe
  ratio of the family portfolio. `θ_f` in the model is now the same quantity.
- **Channels.** Every family of the HB scenarios is a blind family with a designated evaluation.

The sampled model of v3.0 is not run in any scenario of this pre-registration. It may be run beside a real
review as a check that decides nothing (PROTOCOL_v3.1.md §7.4).

---

## 3. Scenarios

### 3.1 Development scenarios run by version 2's code

| id | scenario | definition | size | what is run |
|---|---|---|---|---|
| D11 | hedge estimation | as version 1.0 (unhedged return = `β_t · C_t + X_t`; one core factor with annualised Sharpe ratio 0.6 and daily volatility 1; `β_t` a random walk from 0.5 with annual standard deviation 0.3, one path per hypothesis; hedge cost 0); the same seeds, so the same worlds | STD | the full pipeline of version 1.0, with the p-values of (e) as the p-values of record. The v3.0 test on the same hedged returns, and on the true hedged returns `X` (an oracle), are computed from the same block draws and reported beside it |
| D01h, D02h, D03h, D04h, D05h, D06h, D07ah, D07bh, D08h | **hedged twins** | the version 1.0 scenario of the same name without the `h`, drawn from **that scenario's seeds** (so its true hedged returns are those of the version 1.0 run), with D11's hedge layer on top: the same factor, the same kind of `β` path, the hedge estimated by the live rule | STD | **the three SPA tests and Romano-Wolf only** (the hedge-aware test, the v3.0 test on the estimated hedge, the oracle). No screening and no forward test: those are the version 1.0 scenario's |
| D01, D02, D05, D08, D10 | as version 1.0 | unchanged worlds and seeds | HB | (f) in place of the sampled model, reviewed every quarter (amendment 1, section 11); everything else as version 1.0 |

Every other development run (D01 to D10 and P1 to P4 at STD, D01 and D02 at LONG) is version 1.0's, by version
1.0's code, whose hash is unchanged; the 204 pilot replications on file continue to count towards it.

A twin exists for every development scenario in which version 1.0 requires V3, because in production every
return is hedged by an estimated hedge: a test that keeps its size only on returns hedged by construction has
not been tested. D09a and D09b have no twin (V3 is not required there, and their adaptive variants are not
hedged in the simulated world).

### 3.2 Held-out scenario added (parameter ranges fixed here; values drawn per set)

| id | scenario | definition and ranges | sizes |
|---|---|---|---|
| H12 | **hedge estimation, several factors** | unhedged return = `β'_t C_t + X_t` with `K` core factors, `K` in {1, 2, 3, 4}; each factor has daily volatility 1 and an annualised Sharpe ratio in [0, 0.8]; pairwise factor correlation in [0, 0.5]; each hypothesis has one `β` path per factor, a random walk started uniformly in [−1, 1] with annual standard deviation in [0.05, 0.4]; a share in [0, 0.5] of hypotheses have constant `β`; `X` as the defaults of version 1.0 except that `D` is Student-t with 4 degrees of freedom scaled to variance 1; hedge cost 0 | STD |

Version 1.0 has no held-out scenario with an estimated hedge, so without H12 the revised test would be judged
only by the scenario it was revised on. H12's values for held-out set `k` are drawn from a generator seeded with
the SHA-256 of the text `manhattan-sim-heldout-<k>-` followed by **this file's** SHA-256, so they do not disturb
the draws of version 1.0's scenarios. H12 is run only in a confirmation run, like every held-out scenario. It is
not coded.

Version 1.0's held-out scenarios are unchanged. Those at HB (H03, H05, H06, H07, H09, H10, H11) are run with (f).

---

## 4. Metrics

Version 1.0's, with these readings and additions.

| id | metric | under version 2 |
|---|---|---|
| M3 | SPA size; Romano-Wolf FWER | in D11, the twins and H12: on the **hedge-aware** p-values and step-down. The same shares for the v3.0 test on the estimated hedge and for the oracle are reported beside them, with the paired difference from the oracle |
| M1, M2, M4, M6 | screening and forward metrics | in D11 and H12: computed with the hedge-aware p-values as candidate (i)'s inputs and Romano-Wolf's. Not computed for a twin |
| M7, M8, M9 | calibration, premature elimination, selection bias | from the analytic model; definitions unchanged. M9 compares the posterior mean of `θ_f` with the true forward Sharpe ratio of the family portfolio. M7 and M9 are read at years 2, 4, 7 and 10, as in version 1.0; M8 is the state after the last of the 40 reviews (amendment 1) |
| M12 | **reviews not computed** | at HB: the number of reviews at which any of the six fits fails the grid gate of (f), **counted over all 40 reviews** of a replication (amendment 1) |
| cost | running time | seconds per replication; at HB also seconds for the six fits of a review, and the share of a replication spent on the model |
| cost | attention | at HB: the reviews written (a family that is dormant before and after a date needs none) and the families dormant after each date, with and without a true edge |
| info | power of the tier | at HB: the share of families with a true edge that have been Statistically supported by each date, by true Sharpe ratio of the family portfolio |

Confidence intervals are version 1.0's.

---

## 5. Acceptance thresholds

**Every threshold of version 1.0 stands, with its number.** None is loosened. The table lists only what is added
or re-read.

| id | criterion | threshold | required in |
|---|---|---|---|
| V3 | SPA size (M3) | version 1.0's numbers: upper bound ≤ **0.22** at 0.20; ≤ **0.06** at 0.05; ≤ **0.0015** at 0.001; Romano-Wolf FWER upper bound ≤ **0.06** | where version 1.0 requires it, **and** D01h, D02h, D03h, D04h, D05h, D06h, D07ah, D07bh, D08h, H12. In D11, the twins and H12 it is the hedge-aware test that must meet it |
| V1, V2, V4 | screening FDR, forward FDR, linked error | version 1.0's numbers | as version 1.0 (so also H12, which is run at STD). Not evaluated for a twin |
| V6, V7, V8 | calibration, premature elimination, selection bias | version 1.0's numbers: **0.70** and **0.30**; **0.10**; **0.01** in D01; **0.10** (**0.25** late-starting, H09); **+0.10** and **−0.25** | every scenario run at HB, on the analytic model |
| V12 | reviews not computed (M12) | **0** | every scenario run at HB, over all 40 reviews of every replication (amendment 1). Version 1.0 let a review whose sampler had not converged drop out of M7 and M9; a closed form has no such excuse |
| V13 | the 3.1 test is the 3.0 test where no hedge is estimated | **bit-for-bit identical** p-values (consistent, lower, upper) and Romano-Wolf decisions | a property of the code: a test in the suite |
| V14 | zero evidential weight of the adaptive channel on the reserve | **no** output of the model (no `Π_f`, mean, standard deviation, hyperparameter or draw, of any family) changes when a reserve number of an adaptive-channel family changes | a property of the code: a test in the suite |
| V15 | the tail-risk check of PROTOCOL_v3.1.md §6.11 withholds a label and nothing else | **no** e-LOND rejection, bar or count changes with the outcome of the check; the check is the formula of §6.11 (95%, floor 12) on hand-made records | a property of the code: a test in the suite |

The small-groups rule, the resolution statement and the list of what is reported without a threshold are version
1.0's. Reported without a threshold, added: the v3.0 test's size on the estimated hedge; the oracle's size; the
paired differences; every cost; the reviews written and the families dormant; the power of the tier by true
Sharpe ratio.

**Consequences, fixed in advance.** If the hedge-aware test fails V3 in D11 or in a twin at its replication
count, the test is revised again (a new protocol version) and retested: the threshold does not move. If the
analytic model fails V6, V7, V8 or V12 in a development scenario, the component that depends on the failing
criterion is not switched on (version 1.0, section 8.1, rule 2): without V6 and V8 there are no posterior-based
tiers; without V7 there is no dormancy.

---

## 6. Replication counts

Version 1.0's counts stand: **2,000** for D11 and H12 (STD), **400** for every HB scenario. None is lowered.

**Hedged twins: 400, then as many more as the precision target needs.** A twin measures one thing, the SPA
test's size, as a share over the roughly 450 families with no edge of a replication. Version 1.0's precision
target (its section 6) is a 95% half-width of at most 0.02 at the 0.20 level and 0.01 at the 0.05 level; its
2,000 came from the worst case of a per-replication value that is 0 or 1, which a share over 450 families is
not. A twin is run to 400 replications; if either half-width is then above its target, the run is continued in
steps of 400 until both are met. The 0.001-level check pools all families with no edge of all replications, as
in version 1.0. A twin's verdict is "not decided" until both conditions hold.

---

## 7. Method-selection rule

Version 1.0's, unchanged. Its step 1 makes candidate (i) eligible only if it meets V3; V3 now includes D11, the
twins and H12 under the hedge-aware test.

---

## 8. Failure, revision and retest

Version 1.0's section 8 applies to the changed parts as it stands: thresholds are never weakened; development
scenarios may be run freely and every run is logged; held-out scenarios run only in a tagged confirmation run
after all required criteria are met on the development scenarios, **including** D11, the twins and the HB
development scenarios under this file; the three held-out sets and the one pooled re-run are as written.

Additions go to `docs/manhattan/SIM_PREREG_AMENDMENTS.md` under version 1.0's section 8.4, which binds this file
too.

---

## 9. Records and reporting

- **Seeds.** Version 1.0's: the master seed is the first 8 bytes of **version 1.0's** SHA-256, and every stream
  is keyed as before. The worlds of the changed runs are therefore the worlds version 1.0 would have drawn. A
  twin uses the streams of its version 1.0 scenario; its factor and its `β` paths use the factor stream, which
  no other draw of that scenario uses.
- **Run log.** Every run of a changed part appends its records to `results/manhattan_sim/runs.jsonl`, as version
  1.0 requires, with three more fields: the pre-registration version, this file's SHA-256 and PROTOCOL_v3.1.md's
  SHA-256.
- **A run made in pieces.** A run, of version 1.0's code or of this file's, may be made as ranges of replication
  numbers on several machines (`python -m manhattan.sim.run --first a --reps b --label part`). Seeds depend on
  the replication number alone, so the pieces are the replications one machine would have made. A collector
  (`python -m manhattan.sim.collect`) puts them together and refuses, writing nothing, a piece that holds a
  record of other code, of another review step (section 11), of a replication outside the pre-registered count,
  or one that differs from another record of the same replication in anything but its timings. A run is
  complete, and its criteria are decided, only when every replication of its count is on file.
- **Replication records** of the changed parts are kept in `results/manhattan_sim/v2/reps/`, apart from version
  1.0's. Each carries the hash of the code that made it; records of different code are never pooled. Version
  1.0's code files are byte-for-byte unchanged, so its records keep their hash.
- **Reports.** `results/manhattan_sim/v2/` holds the report of the changed parts: every metric with its
  estimate, its interval, the threshold and the verdict, every reading of this file, and the runs. The pilot
  record of D11 under version 1.0 (0.077) is kept and shown beside the rerun.
- **Development experiments** made outside the runner while a method is being revised are recorded as notes in
  the run log, with what was run and on which replications.

---

## 10. What the changed parts do not show

Version 1.0's section 10, and:

1. That the hedge-aware test holds its size outside the ranges of D11 and H12. A hedge that runs behind a
   fast-moving exposure to a factor with a large mean leaves a real mean in the hedged return (PROTOCOL_v3.1.md
   §2.2 and §5.1, "How it fails"); no resampling of days repairs that.
2. That the simulated hedge resembles a real one. The simulation has one factor (up to four in H12) with
   independent, identically distributed returns; real core factors have regimes and cost money to trade.
3. That the analytic model and the sampled model of v3.0 agree. They are different models (PROTOCOL_v3.1.md
   §7.2(g)) and the sampled one has never been run to completion at full size.
4. That the model's independence between families is harmless. Version 1.0's H11, with strong dependence, is the
   held-out measure of it.
5. How often the tail-risk check of PROTOCOL_v3.1.md §6.11 is wrong. Its pass rates come from the estimand study
   (synthetic single series, one level and one floor), which is not a run of this pre-registration; V15 checks
   only that it changes no test. With the tail undeclared it is defeated, as every check on returns is.
6. That dormancy is worth having. The rule of PROTOCOL_v3.1.md §9.1 is held to V7 (it must not retire families
   that have an edge); how much attention it saves is reported and is not a criterion. On the pilot's fits it
   saves little.

---

## 11. Amendment 1, made before adoption (2026-11-13): the HB runs are reviewed at production's cadence

**What is amended.** Reduction (c) of version 1.0's section 2.5: "in HB runs the model and the tiers are evaluated
at years 2, 4, 7 and 10 instead of quarterly, with the 'two consecutive reviews' conditions applied to
consecutive evaluation dates". It was declared for cost: the sampled model could not be fitted more often. The
analytic model can. For every HB run of this file, development and held-out, the reduction is withdrawn:

1. **Reviews every 63 trading days** (a quarter of the 252-day year): **40 reviews**, at programme days 63, 126,
   ..., 2,520. At each one the six models are fitted, the dormancy forecast is made for the quarterly reviews
   still to come, and the tiers and the dormancy rule are stepped once. "Two consecutive reviews" are a quarter
   apart, as PROTOCOL_v3.1.md §8 and §9.1 write them.
2. **M7 and M9 are read at years 2, 4, 7 and 10**, the dates version 1.0 read them at, and V6 and V8 are decided
   at years 4 and 10 as before.
3. **M8** keeps its definition (a family with a true edge that is dormant at the programme's end, or was dormant
   for more than half its forward life). The rule it measures now has 39 chances to retire a family, not 3. In
   H09, "the second evaluation date after [the edge] began" keeps version 1.0's meaning: the second of the dates
   years 2, 4, 7 and 10 after it began.
4. **M12 is counted over all 40 reviews** of every replication, and V12 stays "exactly 0".
5. **The review step is written into every replication record.** A record made with any other step is refused by
   the report and by the collector of a run made in pieces; records of different review calendars are never
   pooled.

**What it does not touch.** `manhattan/sim/hb.py` and `manhattan/stats/tiers.py` (version 1.0's code: their hash
is the one on its records), every scenario, world and seed, every replication count, every metric's definition,
every threshold.

**Why it tightens and never loosens.** It removes a declared reduction and adds no freedom. V12 must hold over
ten times as many reviews, the first of them with ten families and one quarter of forward record. V7 is measured
on the rule as production applies it: on the development experiment with a review every year
(`results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`) every rule retired more families with an edge than at four
dates, and none retired fewer. V6 reads the same probabilities at the same dates: a fit uses the data up to its
date and not the reviews before it (the bootstrap draws behind the standard errors differ, because the stream is
now consumed at 40 dates). One reading is not ordered either way and is stated as such: V8's groups ("Promising
or higher", "Statistically supported or higher") are the tier states at years 2, 4, 7 and 10, and those states
now come from quarterly stepping; they are the groups production would have. No threshold moves.

**What it costs.** Ten times as many fits and forecasts. The measured cost is in the pilot report of the changed
parts and in `results/manhattan_sim/v2/COMPUTE_OPTIONS.md`; no replication count is lowered to pay for it.

**Why it is in this file.** Version 1.0's section 8.4 puts amendments in an append-only file once a
pre-registration is frozen. This file is still a draft, so the amendment is made in it, before adoption and
before any full or held-out run; it is covered by this file's recorded hash, and sections 2(f), 4 and 5 above
were edited to agree with it. After adoption, amendments go to `docs/manhattan/SIM_PREREG_AMENDMENTS.md`.
