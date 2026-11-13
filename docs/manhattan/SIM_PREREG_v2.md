# Manhattan simulation pre-registration, version 2: the parts changed by Protocol v3.1

Version 2.0, written 2026-11-12 by session "5M Manhattan C", **after** the pilot on development scenarios and
**before** any full run, any held-out world is coded and any confirmation run. A draft for Ethan to adopt
([ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 19). Revised before adoption by session "6M Manhattan C" to follow
one more change of the protocol under test, its dormancy rule (section 1, row 4): **no threshold, metric,
scenario or replication count was touched**, only the description of the method.

**What this file is.** [SIM_PREREG.md](SIM_PREREG.md) (version 1.0) fixed how the methods of Protocol v3.0 are
tested on synthetic data. The pilot on its development scenarios showed two things that must be repaired before a
full run (section 1). [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md) repairs them. This file says how the **changed** methods
are tested. It covers only what changed.

**What stays.** Version 1.0 is not edited, its recorded hash still verifies, and it stays in force for everything
this file does not name: the simulated world, every scenario, every metric, **every threshold**, the replication
counts, the selection rule, the held-out sets, the failure rules and the seeds. Results obtained under version 1.0
for runs this file does not change are kept and are continued, not restarted.

**Frozen.** The SHA-256 of this file and of PROTOCOL_v3.1.md are recorded in `docs/manhattan/sim_prereg_v2.sha256`,
and `python -m manhattan.prereg_v2 verify` checks them together with version 1.0's record. A run of a changed part
refuses to start if either file no longer matches.

**Method under test.** For the changed parts: PROTOCOL_v3.1.md version 3.1.0, whose SHA-256 is the second line of
`docs/manhattan/sim_prereg_v2.sha256`, so that one check pins the two files together. For everything else:
PROTOCOL_v3.md version 3.0.0, as version 1.0 says. Sections 4, 6 and 8 of the protocol and the thresholds of
section 9 are identical in the two versions; the dormancy rule of section 9.1 has one more condition in 3.1
(section 1, row 4).

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
| 4 | **The pilot rerun of the 3.1 draft** (`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`, 12 replications a scenario, the first measurement of the dormancy rule): families with a true edge that end dormant (M8) are 0.167 (0.045 to 0.261) in D02, 0.179 (0.138 to 0.216) in D05, 0.108 (0.081 to 0.138) in D08 and 0.146 (0.092 to 0.197) in D10, against a bound of 0.10 on the upper end | §9.1: a family becomes dormant when both the forecast `PP^max` and the probability of an edge `Π^max` are below 0.05 at two consecutive reviews with at least 252 forward days each, and is reactivated when either is at least 0.15. Before, the forecast alone decided | V7 as it stands (M8 and its bound of 0.10 are version 1.0's, unchanged), in every scenario run at HB (sections 2 and 5) |

**Why this is not tuning to held-out results.** Version 1.0, section 3: development scenarios "may be run as often
as needed while the code is written and the methods are revised". D11, D09b and D10 are development scenarios. The
held-out scenarios of its section 3.2 have not been coded; the runner refuses them and its log shows no held-out
run. The three held-out parameter sets are untouched and none is burned. D02, D05 and D08, on which row 4 also rests,
are development scenarios too, and row 4's rerun was a pilot of the draft, made before adoption.

---

## 2. The pipeline under test: additions to version 1.0's section 2.5

The four declared reductions (a) to (d) of version 1.0 stand. Added:

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
- **Dormancy forecast.** Version 1.0's (`manhattan.stats.tiers.support_probability`: a normal update of each
  model's posterior with simulated future records, not a refit), fed with 200 draws of `θ_f` per family and
  model from the closed-form posterior. Not evaluated at the programme's last date.
- **Dormancy rule.** PROTOCOL_v3.1.md §9.1 (`manhattan.stats.dormancy`), with version 1.0's evaluation dates
  standing for consecutive reviews: a family becomes dormant when `PP^max < 0.05` and `Π^max < 0.05` at two
  consecutive dates with at least 252 forward days at each, and is reactivated when either is at least 0.15.
  `Π^max` is the largest of the six fits' `Π_f`. At the last date there is no forecast: no family becomes
  dormant there, and a dormant family is reactivated there if `Π^max ≥ 0.15`. The tiers are stepped by version
  1.0's code, unchanged.
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
| D01, D02, D05, D08, D10 | as version 1.0 | unchanged worlds and seeds | HB | (f) in place of the sampled model; everything else as version 1.0 |

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
| M7, M8, M9 | calibration, premature elimination, selection bias | from the analytic model; definitions unchanged. M9 compares the posterior mean of `θ_f` with the true forward Sharpe ratio of the family portfolio |
| M12 | **reviews not computed** | at HB: the number of reviews at which any of the six fits fails the grid gate of (f) |
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
| V12 | reviews not computed (M12) | **0** | every scenario run at HB. Version 1.0 let a review whose sampler had not converged drop out of M7 and M9; a closed form has no such excuse |
| V13 | the 3.1 test is the 3.0 test where no hedge is estimated | **bit-for-bit identical** p-values (consistent, lower, upper) and Romano-Wolf decisions | a property of the code: a test in the suite |
| V14 | zero evidential weight of the adaptive channel on the reserve | **no** output of the model (no `Π_f`, mean, standard deviation, hyperparameter or draw, of any family) changes when a reserve number of an adaptive-channel family changes | a property of the code: a test in the suite |

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
