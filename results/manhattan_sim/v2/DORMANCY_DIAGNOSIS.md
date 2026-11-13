# Manhattan simulation: the dormancy rule, D08's calibration and who reaches the supported tier (session 6M, 2026-11-12)

**Synthetic data only. Development scenarios only (seed branch 0). No held-out scenario was coded or run. Nothing
here is decided: every number is from 12 replications a scenario, against 400 pre-registered.**

This file is the evidence behind one change made to the draft of Protocol v3.1 before its adoption (its change 5,
the dormancy rule of §9.1), behind one limitation it now states (§7.2(d), calibration in D08), and behind a table
Ethan asked for (who reaches Statistically supported, by true Sharpe ratio). The pilot of record under the
revised rule is `PILOT_RERUN2_REPORT.md` in this folder; the pilot that motivated the change is
`PILOT_RERUN_REPORT.md` (session 5M), kept as it was.

**How it was made.** The run records of the pilot hold counts per replication, not families. So the pilot's 48
replications of D02, D05, D08 and D10 at HB were replayed with the pilot's own code (`c22815235975c486`), keeping
for every family and review its true Sharpe ratio, its estimates, the six models' `Π`, the forecast `PP` under
each model and its tier. A replay draws the same world from the same seeds, and each of the 48 was checked
against its run record: the counts behind M8 are identical in all 48. Variants of the rule were then replayed on
those stored fits, so differences between variants are differences of rule, not of luck. These are development
experiments outside the runner; each is a note in `results/manhattan_sim/runs.jsonl` (`note-6M-01` to
`note-6M-04`).

---

## 1. Why the dormancy rule retired families that have an edge

The rule under test (Protocol 3.0 §9.1, unchanged in the 3.1 draft until now): a family becomes dormant when
`PP^max < 0.05` at two consecutive reviews, where `PP` is the probability, under one of six models, that the
family enters Statistically supported before the programme ends, and `PP^max` is the largest of the six.

The pilot's result (M8: families with a true edge of at least 0.25 that are dormant at the end, or dormant for
more than half their forward life; the bound is 0.10 on the upper end of the interval):

| | D02 rare edges | D05 fat tails | D08 selection on history | D10 misspecified priors |
|---|---|---|---|---|
| premature elimination | 0.167 (0.045 to 0.261) | 0.179 (0.138 to 0.216) | 0.108 (0.081 to 0.138) | 0.146 (0.092 to 0.197) |
| families with a true edge | 42 | 140 | 944 | 123 |

### 1.1 The rate understates what the rule does to the families it can reach

With the simulation's four review dates (years 2, 4, 7 and 10; no forecast at year 10) the rule needs two
forecast reviews, so it can only reach families frozen before year 4: 100 of the 240 in a replication.

| | D02 | D05 | D08 | D10 |
|---|---|---|---|---|
| families with a true edge | 42 | 140 | 944 | 123 |
| of them, frozen before year 4 (the rule can reach them) | 18 | 51 | 379 | 55 |
| of those, dormant at the end | 7 | 25 | 102 | 18 |
| **share of the reachable families with an edge that were retired** | **0.39** | **0.49** | **0.27** | **0.33** |
| share of the reachable families with no edge that were retired | 0.86 | 0.88 | 0.80 | 0.91 |

Every family with an edge that was dormant at year 7 was still dormant at year 10: the only way back was a
forecast of at least 0.15, and the last date has no forecast.

### 1.2 Who was retired

The families with a true edge that the rule retired, at the review that retired them:

| | D02 | D05 | D08 | D10 |
|---|---|---|---|---|
| true Sharpe ratio, median (quartiles) | 0.73 (0.49 to 0.79) | 0.56 (0.31 to 0.81) | 0.72 (0.49 to 0.85) | 0.32 (0.30 to 0.35) |
| forward years, median (range) | 4.5 (3.6 to 6.6) | 4.1 (2.8 to 7.0) | 4.9 (2.8 to 7.0) | 3.8 (2.8 to 7.0) |
| share with a positive forward Sharpe estimate | 1.00 | 0.88 | 0.92 | 0.56 |
| forward t-statistic, median (quartiles) | 1.10 (0.91 to 1.18) | 1.15 (0.60 to 1.48) | 1.26 (0.52 to 2.08) | 0.56 (-0.26 to 0.97) |
| **share whose `PP^max` was exactly 0** (no draw of 200, under any of six models) | **1.00** | **0.84** | **0.92** | **0.94** |
| `Π` under the central model, median (quartiles) | 0.03 (0.02 to 0.05) | 0.08 (0.03 to 0.17) | **0.61** (0.30 to 0.83) | 0.09 (0.04 to 0.11) |
| `Π^max`, median (quartiles) | 0.09 (0.06 to 0.11) | 0.16 (0.07 to 0.32) | 0.65 (0.39 to 0.85) | 0.18 (0.09 to 0.24) |
| `Π^min`, median (quartiles) | 0.02 (0.02 to 0.02) | 0.04 (0.02 to 0.07) | 0.06 (0.03 to 0.12) | 0.03 (0.01 to 0.06) |
| share with `Π^max` of at least 0.05 | 1.00 | 0.92 | 0.96 | 0.89 |
| at year 10: share with central `Π` of at least 0.5 | 0.29 | 0.32 | 0.73 | 0.17 |
| **at year 10: share with `Π^min` of at least 0.80** (would have reached the tier) | **0.00** | **0.00** | **0.00** | **0.00** |
| the same share among reachable families with an edge that were not retired | 0.00 | 0.12 | 0.08 | 0.24 |

Three things stand out.

1. **These were not thin records.** The retired families had 2.8 to 7 years of forward data, almost all with a
   positive forward Sharpe ratio, typically one standard error above zero.
2. **The forecast was not close to its cut-off. It was zero.** In 84% to 100% of them not one simulated future,
   under any of the six models, reached the tier.
3. **The forecast was right.** None of them would have reached Statistically supported by year 10 had it stayed
   under review. And yet in D08 the central model gave them a median probability of 0.61 of having an edge.

So the rule did what it says. What it says is the problem: `PP` answers "will this family reach Statistically
supported in time?", and that tier needs `Π^min ≥ 0.80`, the smallest of six models that include one in which
the edge halves every three years and one with standard errors inflated by half. On the pilot only 0% to 17% of
the families with an edge held the tier at year 10. "It will not reach the tier in time" is true of most
families that have an edge, so a rule that retires on it retires them. Taking the largest of six forecasts does
not help, because every one of the six is a forecast of the same event, and the event is decided by the most
cautious model.

### 1.3 Which part of the rule

Each candidate cause, changed alone, with everything else as in the pilot (replayed on the same fits; candidate
(i); the first row reproduces the pilot):

| variant | D02 | D05 | D08 | D10 | no-edge families dormant at the end (share: D02 / D05 / D08 / D10) | reviews written per replication, of 560 |
|---|---|---|---|---|---|---|
| the pilot's rule: `PP^max < 0.05` at two consecutive reviews | 0.167 (0.037 to 0.267) | 0.179 (0.134 to 0.218) | 0.108 (0.080 to 0.138) | 0.146 (0.091 to 0.193) | 0.36 / 0.37 / 0.34 / 0.38 | 438 / 437 / 474 / 432 |
| **cut-off** 0.02 | 0.143 (0.034 to 0.250) | 0.157 (0.100 to 0.208) | 0.074 (0.054 to 0.096) | 0.130 (0.075 to 0.178) | 0.32 / 0.33 / 0.29 / 0.34 | 457 / 457 / 492 / 450 |
| cut-off 0.01 | 0.119 (0.000 to 0.233) | 0.121 (0.081 to 0.158) | 0.057 (0.042 to 0.072) | 0.098 (0.038 to 0.157) | 0.29 / 0.30 / 0.25 / 0.31 | 470 / 472 / 505 / 464 |
| cut-off: `PP^max` exactly 0 | 0.119 (0.000 to 0.233) | 0.086 (0.046 to 0.128) | 0.044 (0.031 to 0.058) | 0.081 (0.035 to 0.127) | 0.25 / 0.26 / 0.21 / 0.28 | 486 / 487 / 516 / 479 |
| reactivate at 0.05 instead of 0.15 | 0.167 (0.037 to 0.267) | 0.179 (0.134 to 0.218) | 0.108 (0.080 to 0.138) | 0.146 (0.091 to 0.193) | 0.36 / 0.37 / 0.34 / 0.38 | 438 / 437 / 474 / 433 |
| **minimum forward evidence**: 1 year at each low review | 0.167 (0.037 to 0.267) | 0.164 (0.110 to 0.213) | 0.106 (0.078 to 0.135) | 0.114 (0.056 to 0.169) | 0.31 / 0.32 / 0.31 / 0.32 | 461 / 461 / 484 / 460 |
| 2 years | 0.095 (0.000 to 0.171) | 0.121 (0.071 to 0.171) | 0.074 (0.057 to 0.089) | 0.089 (0.042 to 0.131) | 0.20 / 0.20 / 0.21 / 0.20 | 504 / 504 / 514 / 504 |
| 3 years | 0.095 (0.000 to 0.171) | 0.093 (0.060 to 0.125) | 0.046 (0.035 to 0.057) | 0.065 (0.029 to 0.101) | 0.12 / 0.12 / 0.12 / 0.12 | 531 / 531 / 536 / 532 |
| **number of reviews**: three consecutive instead of two | 0.048 (0.000 to 0.133) | 0.071 (0.045 to 0.102) | 0.023 (0.014 to 0.033) | 0.057 (0.024 to 0.086) | 0.15 / 0.16 / 0.13 / 0.17 | 524 / 524 / 536 / 521 |
| **assumption set**: forecast under the central model only | 0.190 (0.077 to 0.283) | 0.200 (0.162 to 0.233) | 0.131 (0.099 to 0.165) | 0.146 (0.091 to 0.193) | 0.38 / 0.39 / 0.36 / 0.39 | 427 / 427 / 462 / 424 |
| assumption set: each model judges its own future (`Π` of that model at least 0.80) | 0.119 (0.000 to 0.233) | 0.071 (0.032 to 0.115) | 0.029 (0.015 to 0.044) | 0.098 (0.054 to 0.142) | 0.30 / 0.30 / 0.23 / 0.33 | - |
| assumption set: the event is Promising (`Π^min ≥ 0.40`), not Statistically supported | 0.119 (0.000 to 0.233) | 0.086 (0.048 to 0.124) | 0.030 (0.016 to 0.044) | 0.081 (0.035 to 0.127) | 0.27 / 0.28 / 0.21 / 0.31 | - |
| **and the probability of an edge**: `Π^max < 0.05` as well, 252 forward days, reactivate also at `Π^max ≥ 0.15` (**adopted**) | **0.000 (0.000 to 0.000)** | **0.014 (0.000 to 0.031)** | **0.002 (0.000 to 0.007)** | **0.008 (0.000 to 0.028)** | 0.14 / 0.14 / 0.03 / 0.20 | 518 / 520 / 554 / 501 |
| the same without the 252 days | 0.000 (0.000 to 0.000) | 0.014 (0.000 to 0.031) | 0.002 (0.000 to 0.007) | 0.016 (0.000 to 0.040) | 0.15 / 0.15 / 0.03 / 0.22 | 513 / 514 / 554 / 492 |
| the same with 504 days | 0.000 (0.000 to 0.000) | 0.014 (0.000 to 0.031) | 0.001 (0.000 to 0.003) | 0.008 (0.000 to 0.028) | 0.09 / 0.10 / 0.02 / 0.13 | 535 / 535 / 556 / 524 |
| the same with `Π^max < 0.10` | 0.024 (0.000 to 0.073) | 0.043 (0.019 to 0.066) | 0.003 (0.000 to 0.009) | 0.016 (0.000 to 0.041) | 0.23 / 0.23 / 0.06 / 0.26 | 486 / 491 / 545 / 478 |
| the same with `Π^max < 0.20`, reactivate at 0.40 (the Promising levels) | 0.143 (0.034 to 0.250) | 0.079 (0.038 to 0.121) | 0.007 (0.000 to 0.020) | 0.065 (0.019 to 0.115) | 0.29 / 0.30 / 0.15 / 0.30 | 465 / 468 / 522 / 465 |

The two rows on the forecast's event redraw the forecast with this session's random numbers (which is why their
D08 and D10 figures for the unchanged event, 0.104 and 0.138, differ slightly from the record's 0.108 and
0.146).

**Verdict on each candidate.**

- **The PPoS cut-offs: not the cause.** The forecast of a retired family is exactly zero in 84% to 100% of
  cases. Even the strictest cut-off possible with 200 draws leaves D02 at 0.119 and D05 at 0.086, with upper
  ends of 0.233 and 0.128. Reactivating sooner changes nothing: a forecast that is zero does not come back.
- **Minimum forward evidence: not the cause.** Families were retired on 2.8 to 7 years of forward data.
  Requiring one to three years lowers the rate mainly by leaving fewer families the rule can reach, and three
  years still leaves upper ends of 0.171, 0.125 and 0.101.
- **Review frequency: not the cause, and more reviews make it worse.** With four dates the rule reaches 42% of
  families. Requiring a third consecutive review lowers the rate only because it then reaches the families
  frozen before year 2 and no others. With
  yearly reviews (part 3) the same rule retires 43% to 71% of the families with an edge.
- **The assumption set used for the forecast: yes, this is the cause**, in one specific sense: not which model
  simulates the future, but which event the future is scored against. Using the central model alone is worse.
  Letting each model judge its own future, or forecasting the Promising tier, helps (0.03 to 0.12) but leaves
  upper ends above 0.10 in three scenarios, because the event is still a tier and still has a deadline.
- **The model's early estimates: a contributor where edges are rare, not the cause.** In D02, D05 and D10 the
  central model itself gave the retired families a low probability of an edge (medians 0.03 to 0.09): with
  1.5% to 5% of families having an edge, a record one standard error above zero moves the model little. But the
  most hopeful model gave 89% to 100% of them at least 0.05, and in D08 the model was on their side (0.61).

### 1.4 The revision, and why this one

**Protocol 3.1 §9.1, as revised.** Become dormant: `PP^max < 0.05` **and** `Π^max < 0.05`, at two consecutive
reviews, each with at least 252 forward days. Reactivate: `PP^max ≥ 0.15` **or** `Π^max ≥ 0.15`, or on Ethan's
request. `Π^max` is the largest of the six models' probabilities that the family's edge is at least `θ_min`.

Why it is a matter of principle and not of fit:

1. **It asks the question dormancy is about.** C6 of the pre-registration is "the dormancy rule rarely abandons
   a family that has an edge". `Π` is the probability of an edge. `PP` is the probability of clearing a much
   higher bar by a date.
2. **It is what the protocol already said.** §7.2(e) of 3.0: "Tier entry uses `Π^min`; dormancy uses `Π^max` (so
   that neither promotion nor abandonment rests on one prior)." §9.1 used `PP^max` instead, which looks like the
   same thing and is not: it is the most hopeful forecast of an event decided by the most cautious model.
3. **No number is new.** 0.05 and 0.15 are 3.0's dormancy levels. 252 forward days and "two consecutive
   reviews" are those of the Promising exit (§8.1), of which this rule is the stricter sibling: the most hopeful
   model instead of the most cautious, 0.05 instead of 0.20.
4. **It only ever removes retirements.** The forecast condition stays, so every family the revised rule retires
   the old rule retires too, no later (a test checks this on random sequences). A family that could still make
   the tier is never retired, and with no programme end nothing is.
5. **It was not the best-scoring variant.** `Π^max < 0.10` also sits inside the bound on these replications and
   retires more families with no edge; three consecutive reviews, or three forward years, on the forecast alone
   do nearly as well in some scenarios. They were not chosen because nothing but the result recommends them.

What was **not** changed: the metric M8, its bound of 0.10, the scenarios, the replication counts, every
threshold of SIM_PREREG and SIM_PREREG_v2, the forecast and its 200 draws, the tiers.

### 1.5 The rerun under the revised rule

The pilot of record: `PILOT_RERUN2_REPORT.md`. The five HB scenarios, 12 replications each, through the runner
from a clean checkout of commit `9b1f068` (code `630059032fd6e5b8`), on the same worlds as the first rerun.
Intervals are the pre-registered ones (percentiles over 2,000 resamples of whole replications).

| scenario | families with a true edge | premature elimination, 3.0's rule (first rerun) | **revised rule** | retired | bound on the upper end |
|---|---|---|---|---|---|
| D02 rare edges | 42 | 0.167 (0.045 to 0.261) | **0.000 (0.000 to 0.000)** | 0 of 42 | 0.10 |
| D05 fat tails | 140 | 0.179 (0.138 to 0.216) | **0.014 (0.000 to 0.032)** | 2 of 140 | 0.10 |
| D08 selection on history | 944 | 0.108 (0.081 to 0.138) | **0.002 (0.000 to 0.007)** | 2 of 944 | 0.10 |
| D10 misspecified priors | 123 | 0.146 (0.092 to 0.197) | **0.008 (0.000 to 0.029)** | 1 of 123 | 0.10 |
| D01 no edges | 0 | - | - | - | 0.10 |

Candidate (ii) gives the same four figures. All four intervals are inside the bound; the verdict of each is
still "pilot: not decided", because 12 replications are 12. Two cautions on reading them:

- **"0.000 (0.000 to 0.000)" in D02 means that none of 42 families was retired, not that the rate is zero.** A
  true rate of 7% would still give no case in 42 one time in twenty. The full run has about 1,400 such families.
- **The runner agrees with the replay.** The four figures are those the replay predicted (the adopted row of
  the table in 1.3), family for family.

Nothing else in the report moved, because the model is the same: every calibration figure, every count behind
the `Π^min` groups and the share of families with an edge that hold Statistically supported at each date are
identical to the first rerun (no retired family would have reached the tier). The only other differences are
the families dormant at the end and, in the second decimal, the composition of the Promising group: a dormant
family is not evaluated, so under the old rule a few dormant families kept a Promising label they would have
lost.

### 1.6 What the revision costs

**Attention.** A replication is 240 families and 560 family-reviews at four dates. A review is counted as
written for every family that is not dormant both before and after the date. Candidate (i):

| | D01 | D02 | D05 | D08 | D10 |
|---|---|---|---|---|---|
| families dormant at the end, 3.0's rule (first rerun) | 87.1 | 85.6 | 86.7 | 62.9 | 88.3 |
| families dormant at the end, revised rule | 33.8 (29.2 to 38.4) | 32.6 (28.6 to 36.6) | 31.9 (25.4 to 38.5) | 4.3 (0.0 to 9.7) | 45.3 (42.2 to 48.5) |
| share of the families with no edge dormant at the end, 3.0's rule | 0.36 | 0.36 | 0.37 | 0.34 | 0.38 |
| the same, revised rule | 0.141 (0.123 to 0.159) | 0.138 (0.122 to 0.153) | 0.139 (0.111 to 0.163) | 0.026 (0.005 to 0.058) | 0.197 (0.185 to 0.209) |
| reviews written per replication, 3.0's rule (replay) | not replayed | 438 | 437 | 474 | 432 |
| reviews written per replication, revised rule | 517.8 (511.4 to 524.1) | 518.2 (512.4 to 524.1) | 520.0 (511.7 to 528.3) | 554.2 (547.0 to 561.4) | 501.3 (497.0 to 505.7) |
| more reviews written | - | +18% | +19% | +17% | +16% |

In words: the old rule left a little over a third of all families dormant at the end; the revised rule leaves
about one in seven (one in fifty in D08, where a third of the families have an edge and the most hopeful model
seldom says "below 5%"). That is about 80 more reviews per replication over ten years, a sixth more. What is
bought with them: 7, 25, 102 and 18 families with a true edge retired under the old rule; 0, 2, 2 and 1 under
the revised one.

These are the figures at the simulation's four review dates, where the old rule could only reach families
frozen before year 4. Part 3 gives both rules with yearly reviews, where the old rule retires four in five of
the families with no edge and about half of those with one, and the difference in attention is much larger.

**Compute.** None that can be measured. A replication took 65, 70, 77, 143 and 80 seconds (D01, D02, D05, D08,
D10) against 68, 75, 85, 149 and 85 in the first rerun; the difference is the load on the machine, not the
rule. The revised rule adds one comparison per family and review. The forecast, the costly part of dormancy, was
already computed for every family at every date under the old rule, and the six fits use every family's data
whether it is dormant or not. The estimate for the whole development run on the iMac is unchanged: about 1,740
CPU-hours, of which the five HB scenarios about 47.

In production the saving from dormancy is the review itself and, for families that are not cheap to record,
their data (Protocol §9.2). The revised rule keeps more families under review and recording.

---

## 2. D08: the central model's calibration error at year 10

The pilot: expected calibration error 0.101 (0.034 to 0.136) at year 10, against a bound of 0.10 on the upper
end (V6). It is the one calibration check outside its bound; at year 4 the same scenario gives 0.034.

**Where the error is.** D08 is the scenario in which every submitted family is the best of 20 by its Sharpe
ratio on the exploration window. That leaves **a third of the families with a true edge** (0.328; true Sharpe
ratios from 0.29 to 1.48 for the middle nine tenths, median 0.86) **and two thirds at exactly zero** (99.2% of
the families with no edge). The central model's reliability curve at year 10, ten bins:

| stated probability of an edge | 0.05 | 0.15 | 0.25 | 0.35 | 0.45 | 0.55 | 0.65 | 0.75 | 0.85 | 0.97 |
|---|---|---|---|---|---|---|---|---|---|---|
| share that had one | 0.02 | 0.04 | 0.07 | 0.12 | 0.18 | 0.29 | 0.47 | 0.57 | 0.90 | 0.99 |
| family observations | 600 | 419 | 349 | 209 | 216 | 167 | 125 | 126 | 155 | 514 |

The two ends are right. The middle says too much: of the families given about 0.45, 18% had an edge. The error
grows with the forward record (0.008, 0.034, 0.069, 0.101 at years 2, 4, 7 and 10), as posteriors narrow and the
shape of the prior between zero and the first real edges starts to matter.

**The cause, tested.** Three posteriors of "this family has an edge of at least 0.25" were computed for every
family from the **same** reserve and forward estimates and the **same** standard errors the model was given:

| posterior | what it assumes about the population | calibration error, year 4 | year 10 |
|---|---|---|---|
| the central model (as run) | Protocol 3.1 §7.1: a narrow normal and a wide one (a tenth of the mass, scale 1.5) at the same centre; retention; common shock; the grid | 0.034 (0.004 to 0.067) | **0.101 (0.037 to 0.136)** |
| a plain normal prior | one normal with the population's own true mean and variance; no retention, no wide component, no shock, no grid | 0.024 (0.001 to 0.065) | **0.102 (0.089 to 0.149)** |
| the population's own shape | the true two groups: the families at zero and the true edges, in their true proportions | 0.008 (0.001 to 0.018) | **0.009 (0.004 to 0.019)** |

(Intervals from resampling the 12 replications; bins of at least 200 observations, as pre-registered. The first
row reproduces the pilot's figure.) A plain one-hump prior makes the same error with the same shape (given 0.45:
0.11 had an edge; given 0.55: 0.15). The true two-group shape, fed the same numbers, is calibrated (given 0.45:
0.42; given 0.55: 0.42; given 0.75: 0.74). So:

- **It is not the estimates or their standard errors**: the two-group posterior is calibrated with them.
- **It is not the retention, the common shock, the grid or the closed form**: a posterior with none of them
  makes the same error.
- **It is the shape of the prior.** One hump has to cover a spike at zero and a slab of real edges. It puts
  mass between 0 and 0.5 where the population has little, so a family whose estimates land near 0.25 is
  given even odds when it is, most of the time, a family at zero with a lucky record.

Where edges are rare the model's wide component does the work of the second group and the error is small
(year 10: 0.014 in D02, 0.005 in D05, 0.004 in D10, 0.019 in D01); there a plain normal prior is the one that
fails (0.064 in D05). In D08 a third of the families are in the second group, the wide component has a tenth of
the mass and a scale of 1.5, and neither fits.

**Verdict: documented as a known limitation, model not changed.** The repair is a prior in two groups whose
share and scale are learned. That is a general idea, but it is another model, not a correction of this one:

1. It turns two constants fixed in 3.0 (`w = 0.10`, `s_R = 1.5`) into learned quantities and adds at least two
   dimensions to the grid.
2. Built now, it would be built on these scenarios, whose families with no edge have a mean of **exactly zero**
   by the pre-registration's convention ("the least favourable null"). A spike at zero would be fitted to that
   convention. In D10 the families with no edge sit near −0.28, and SIM_PREREG §2.3 forbids drawing the truth
   from the model's priors for this reason.
3. It cannot be validated at pilot scale in one session: every calibration, tier and dormancy number of all
   five HB scenarios would move.

What it means for the full run: if 400 replications confirm an error near 0.10, **V6 fails in D08 and the
posterior-based tiers stay off** (SIM_PREREG_v2 §5) until a later protocol version changes the prior. The part
of the scale the tier rules use is sound in the pilot: 112 of the 113 families with `Π^min ≥ 0.80` at year 10
had an edge, and 392 of the 435 with `Π^min ≥ 0.40`. The limitation is stated in Protocol 3.1 §7.2(d).

---

## 3. Yearly reviews: a development experiment, and a caution

**Why.** The simulation steps the tiers at four dates (SIM_PREREG §2.5(c), a reduction made when the model had
to be sampled). Production reviews every quarter. "Two consecutive reviews" are then three months, not two to
three years, and every family has many more chances to be retired. So the pilot's 48 worlds were run again with
reviews at years 1 to 10 (a forecast at years 1 to 9), under the revised rule; 3.0's rule and variants were
replayed on the stored fits. **This is not the pre-registered pipeline. It decides nothing** and is pooled with
no run of record (`note-6M-04`).

Premature elimination (M8) with yearly reviews, 12 replications a scenario; in brackets, families retired of
families with a true edge:

| rule | D02 | D05 | D08 | D10 | no-edge families dormant at the end (share: D02 / D05 / D08 / D10) | reviews written per replication, of 1,360 |
|---|---|---|---|---|---|---|
| 3.0's rule: the forecast alone | 0.714 (0.595 to 0.841) [30/42] | 0.579 (0.488 to 0.659) [81/140] | 0.453 (0.406 to 0.503) [428/944] | 0.431 (0.375 to 0.491) [53/123] | 0.80 / 0.81 / 0.78 / 0.81 | 572 / 579 / 747 / 565 |
| **the revised rule (Protocol 3.1 §9.1)** | **0.048 (0.000 to 0.129) [2/42]** | **0.071 (0.038 to 0.106) [10/140]** | **0.005 (0.000 to 0.015) [5/944]** | **0.057 (0.020 to 0.098) [7/123]** | 0.45 / 0.40 / 0.06 / 0.52 | 979 / 1,016 / 1,311 / 903 |
| revised, with `Π^max < 0.02` | 0.024 (0.000 to 0.065) [1/42] | 0.021 (0.000 to 0.043) [3/140] | 0.001 (0.000 to 0.003) [1/944] | 0.008 (0.000 to 0.026) [1/123] | 0.21 / 0.20 / 0.02 / 0.34 | 1,215 / 1,210 / 1,344 / 1,098 |
| revised, with `Π^max < 0.01` | 0.000 [0/42] | 0.000 [0/140] | 0.000 [0/944] | 0.000 [0/123] | 0.07 / 0.08 / 0.01 / 0.19 | 1,319 / 1,310 / 1,355 / 1,226 |
| revised, three consecutive reviews | 0.024 (0.000 to 0.065) [1/42] | 0.050 (0.022 to 0.080) [7/140] | 0.004 (0.000 to 0.012) [4/944] | 0.041 (0.016 to 0.069) [5/123] | 0.35 / 0.31 / 0.05 / 0.42 | 1,111 / 1,128 / 1,330 / 1,040 |
| revised, at least 756 forward days | 0.048 (0.000 to 0.129) [2/42] | 0.043 (0.021 to 0.063) [6/140] | 0.003 (0.000 to 0.009) [3/944] | 0.057 (0.020 to 0.098) [7/123] | 0.36 / 0.33 / 0.05 / 0.42 | 1,118 / 1,138 / 1,330 / 1,075 |

The run itself, through `manhattan.stats.dormancy.step`, gives the second row exactly (2/42, 10/140, 5/944,
7/123): the replay and the code agree at this cadence too.

**What it shows.**

1. **More reviews do not repair 3.0's rule. They expose it.** With yearly reviews it reaches every family, and
   as the end of the programme nears no family can still reach the tier in time, so it retires 43% to 71% of
   the families with an edge and four in five of those without. The four-date figures (0.11 to 0.18) were the
   rule held back by a design that let it reach 42% of families.
2. **The revised rule cuts that by about ten times, to 0.5% to 7%, but it is no longer far inside the bound.**
   Its four-date figures are 0% to 1.4%. With yearly reviews the estimates are 4.8%, 7.1%, 0.5% and 5.7%, and
   **the upper ends of two intervals are above 0.10** (0.129 in D02 on 2 of 42 families; 0.106 in D05), with a
   third at 0.098. On this evidence the revised rule would probably meet V7 at yearly reviews with 400
   replications, and it is not certain. Quarterly reviews were not run.
3. **Who the revised rule still retires.** The 24 families (of 1,249 with a true edge): three quarters have a
   true Sharpe ratio between 0.26 and 0.49 and none above 0.74. They were retired after 2 to 7 forward years
   (median 2.8) on a forward Sharpe estimate that was negative in four cases of five (median −0.38), about one
   and a half standard errors below their true value. The most hopeful model gave them a median probability of
   0.026. All 24 were still dormant at year 10, by when their forward estimates had come back to about zero.
   These are families with a small real edge and an unlucky start. Nothing in their record separates them from
   the hundreds of families with no edge that were retired beside them, and that is the limit stated in
   Protocol 3.1 §9.1 ("How it fails", 1): an edge of 0.25 and no edge are less than one standard error apart
   after ten years.
4. **At this cadence the revised rule saves real attention.** It retires 40% to 52% of the families with no
   edge (6% in D08) and about a quarter to a third of the reviews are not written (979 to 1,016 of 1,360; 903
   in D10; 1,311 in D08). 3.0's rule saved more (565 to 747 written) by retiring half the families that have
   an edge.
5. **The level trades the two off.** With `Π^max < 0.02` the rate is 0.1% to 2.4% and a fifth to a third of
   the families with no edge are retired; with `Π^max < 0.01` no family with an edge is retired in these 48
   replications and 7% to 19% of the others are. **Neither is adopted.** 0.05 is the level the protocol already
   had; a different one would be a number chosen on a development experiment at a cadence that is not the
   pre-registered one. It is put to Ethan with these figures (ETHAN_ACTIONS item 21).

**The caution, plainly.** V7 as pre-registered is measured at four review dates, and at four dates the revised
rule passes easily. That is a statement about a programme reviewed four times in ten years. For a programme
reviewed quarterly the yearly figures are the better guide, and they say "about 5% to 7% where edges are rare,
close to the bound". Dormancy is off by default (`programme.end` is unset), so nothing depends on this until
Ethan sets an end date.

**Cost of running the HB scenarios with yearly reviews.** Roughly two to three times the four-date cost: a
replication took about 3 to 4 minutes on a busy core here, not timed cleanly, against 65 to 143 seconds. That
is of the order of 100 to 150 CPU-hours for the five scenarios at 400 replications, against 47.

---

## 4. Who reaches Statistically supported, by true Sharpe ratio

Reported for Ethan's decision on the tier's bar. **Nothing was changed**: the tier is that of Protocol 3.0 §8.2
(Promising; `Π^min ≥ 0.80`, the smallest of six models; a positive forward mean; 504 forward days, or 252 if
Romano-Wolf named a variant on the reserve). A family counts from the first review at which it holds the tier.
The Sharpe ratio is the **true** one of the family portfolio, core-hedged and net, over its forward life.
Candidate (i); candidate (ii) is close (in D08's pilot of record, 9.3 families hold the tier at the end
against 10.0).

### 4.1 By years 4, 6 and 10 of the programme (yearly reviews: the development experiment of part 3)

The pre-registered pipeline has no review at year 6, so this table comes from the yearly experiment. Among the
families with a true edge that were frozen before the date, the share that hold or have held the tier; then the
95% interval over replications; then the number of families the cell rests on.

**All four scenarios pooled** (1,249 families with a true edge, of which 944 are D08's):

| true hedged Sharpe ratio | by year 4 | by year 6 | by year 10 |
|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 76 | 0.00 (0.00 to 0.00), 117 | 0.01 (0.00 to 0.03), 193 |
| 0.5 to 0.75 | 0.00 (0.00 to 0.00), 88 | 0.01 (0.00 to 0.03), 149 | 0.02 (0.00 to 0.05), 250 |
| 0.75 to 1 | 0.00 (0.00 to 0.00), 150 | 0.01 (0.00 to 0.04), 222 | 0.07 (0.02 to 0.13), 351 |
| 1 to 1.5 | 0.09 (0.04 to 0.13), 167 | 0.16 (0.09 to 0.22), 244 | 0.29 (0.20 to 0.37), 403 |
| 1.5 and above | 0.27 (0.12 to 0.44), 22 | 0.58 (0.39 to 0.79), 31 | 0.71 (0.54 to 0.90), 52 |
| **all with a true edge** | **0.04 (0.02 to 0.06), 503** | **0.08 (0.05 to 0.11), 763** | **0.15 (0.10 to 0.20), 1,249** |

**By scenario**, the same three dates (the world matters: the model learns how common edges are):

| true hedged Sharpe ratio | D02 rare edges | D05 fat tails | D08 selection on history | D10 misspecified priors |
|---|---|---|---|---|
| 0.25 to 0.5 | 0.00 / 0.00 / 0.00 (7) | 0.00 / 0.00 / 0.00 (33) | 0.00 / 0.00 / 0.02 (107) | 0.00 / 0.00 / 0.00 (46) |
| 0.5 to 0.75 | 0.00 / 0.00 / 0.00 (16) | 0.00 / 0.00 / 0.00 (48) | 0.00 / 0.02 / 0.03 (184) | 0.00 / 0.00 / 0.00 (2) |
| 0.75 to 1 | 0.00 / 0.00 / 0.00 (12) | 0.00 / 0.00 / 0.00 (32) | 0.00 / 0.02 / 0.08 (290) | 0.00 / 0.00 / 0.00 (17) |
| 1 to 1.5 | 0.00 / 0.00 / 0.00 (7) | 0.00 / 0.13 / 0.27 (22) | 0.10 / 0.15 / 0.30 (325) | 0.12 / 0.19 / 0.29 (49) |
| 1.5 and above | none | 0.00 / 1.00 / 0.80 (5) | 0.29 / 0.50 / 0.66 (38) | 0.25 / 0.80 / 0.89 (9) |
| all with a true edge | 0.00 / 0.00 / 0.00 (42) | 0.00 / 0.05 / 0.07 (140) | 0.04 / 0.08 / 0.16 (944) | 0.07 / 0.13 / 0.18 (123) |

(Each cell: by year 4 / by year 6 / by year 10; in brackets the families with a true edge frozen by year 10.
The 1.5-and-above share in D05 falls from year 6 to year 10 because families frozen later join the count.)

### 4.2 By years of forward record (the same experiment)

The table above mixes old and young families. For the tier's own power: among the families with at least that
many forward years by the end of the programme, the share that entered the tier within them. All four scenarios
pooled:

| true hedged Sharpe ratio | within 4 years of freeze | within 6 years of freeze | within 10 years of freeze |
|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 117 | 0.00 (0.00 to 0.00), 76 | 0.00 (0.00 to 0.00), 6 |
| 0.5 to 0.75 | 0.01 (0.00 to 0.03), 149 | 0.02 (0.00 to 0.05), 88 | 0.00 (0.00 to 0.00), 6 |
| 0.75 to 1 | 0.02 (0.00 to 0.05), 222 | 0.05 (0.01 to 0.10), 150 | 0.00 (0.00 to 0.00), 23 |
| 1 to 1.5 | 0.23 (0.14 to 0.31), 244 | 0.26 (0.19 to 0.34), 167 | 0.38 (0.08 to 0.69), 13 |
| 1.5 and above | 0.65 (0.48 to 0.82), 31 | 0.73 (0.53 to 0.92), 22 | 0.50 (0.00 to 1.00), 2 |
| all with a true edge | 0.11 (0.07 to 0.15), 763 | 0.14 (0.09 to 0.18), 503 | 0.12 (0.04 to 0.22), 50 |

Only the first batch has ten forward years, so the last column rests on very few families.

### 4.3 At the pre-registered four dates (the pilot of record)

`PILOT_RERUN2_REPORT.md` gives the same table for years 2, 4, 7 and 10 from the run records, scenario by
scenario. All families with a true edge, by year 4 / 7 / 10: D02 0.00 / 0.00 / 0.00; D05 0.02 / 0.04 / 0.07;
D08 0.04 / 0.08 / 0.13; D10 0.07 / 0.15 / 0.19. In D08 by year 10: 0.01, 0.03, 0.07, 0.24 and 0.58 for the five
bands. Yearly reviews give a few points more (a family can enter in any year, not at one of four dates).

### 4.4 What the tables say

- **Below a true Sharpe ratio of 0.75 the tier is not reached**: 0% to 3% in ten years, in every scenario.
- **Between 0.75 and 1: about 7% by year 10**, almost all in D08.
- **Between 1 and 1.5: about one family in ten by year 4, one in six by year 6, three in ten by year 10**; a
  quarter within four to six years of its own freeze.
- **At 1.5 and above: about a quarter by year 4, six in ten by year 6, seven in ten by year 10**, on few
  families (52).
- **Where edges are rare the tier is not reached at all**: in D02 (2% of families with an edge) none of 42, the
  seven with a Sharpe ratio above 1 included. The model has learned that edges are rare and holds every family
  to that.
- **Why.** Entry uses the smallest of six `Π`. For families with an edge the smallest is, at year 10, the decay
  model S5 in 43% to 67% of cases and the inflated-standard-error model S4 in 33% to 44% (first rerun). S5 asks
  about the edge the family has **now** if it halves every three years, so an old family needs a very large
  edge at freeze; S4 widens every standard error by half.
- **What it leaves to decide** (ETHAN_ACTIONS item 21): whether a tier that, in ten years, admits almost only
  families with a true hedged Sharpe ratio above 1 is the tier that was meant. Any other bar is a new protocol
  version, and V6's groups (`Π^min ≥ 0.80`) are defined on the present one.

---

## 5. What this file does not show

1. Anything at 400 replications. Twelve replications of 240 families give 42 to 944 families with a true edge
   a scenario; intervals are wide and several cells rest on a handful of families.
2. The revised rule at quarterly reviews, or in any held-out scenario. H09 (an edge that appears late) is the
   pre-registered test of reactivation and is not coded.
3. That the yearly experiment is the pre-registered pipeline. It is not, and no criterion may be read from it.
4. That the three posteriors of part 2 exhaust the causes of D08's error. They show that the shape of the prior
   is sufficient to produce all of it and that the estimates are not at fault.
5. The replays reuse the pilot's worlds, so the diagnosis, the revision and the rerun are all on the same 12
   replications a scenario. The rule was chosen for its reasons and not for its score, but it has not yet been
   seen on worlds it was not diagnosed on. The full run's other 388 replications a scenario are the first such
   worlds; the held-out scenarios are the test.

