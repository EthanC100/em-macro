# The dormancy rule: a second, independent look, the diagnostics the pilot's records do not hold, and an alternative

Written by `dev_6M_b/second_look.py` (session "6M Manhattan C: dormancy fix and statistical checks", 2026-11-13). **Synthetic data only. Development scenarios only (seed branch 0). No held-out scenario was coded or run. Development experiments outside the runner (`note-6Mb-01` and `note-6Mb-02` in the run log): they decide nothing.**

**Why this file exists.** Two sessions were given the dormancy problem on the same branch. The first, "6M Manhattan C: dormancy fix before adoption", diagnosed it, revised Protocol 3.1 §9.1 and pushed (`DORMANCY_DIAGNOSIS.md`, `PILOT_RERUN2_REPORT.md`). This session reached the same diagnosis separately, on its own instrumented runs, and had chosen a different second condition for the rule before it found the other's work. **The rule on the branch is the first session's and this session changed nothing in it**: no protocol text, no hash, no pipeline code. This file adds three things: the diagnosis seen from a second set of experiments (section 1); the diagnostics the brief asked for and the pilot's records do not hold (section 2); and the other rule, measured beside the branch's on the same fits, for Ethan to choose between before he adopts (section 3; ETHAN_ACTIONS item 22).

**How it was made.** `paths.py` runs the branch's HB pipeline unchanged (same seeds, worlds, fits and forecast stream) and steps the tier state machine four ways on the same fits: the rule on the branch, the rule of 3.0, the alternative, and no dormancy. 48 replications at the four pre-registered review dates (years 2, 4, 7 and 10) and 48 with a review every year. Candidate (i)'s tiers.

**Check that these are the pilot's own replications.** The "branch" path gives the pilot of record's counts (families retired, families with an edge, families dormant at the end, reviews written) in **48 of 48** replications, and the "3.0" path gives session 5M's pilot in **48 of 48**.

## 1. The same diagnosis, from a second set of experiments

`trace_hb.py` re-ran session 5M's 48 pilot replications under the rule of 3.0 keeping every family's numbers; all 48 reproduce the recorded counts (7 of 42, 25 of 140, 102 of 944, 18 of 123 retired). `who.txt` and `replay_table.txt` in `dev_6M_b/` have the full output. It agrees with `DORMANCY_DIAGNOSIS.md` on every point, and adds two.

| what | D02 | D05 | D08 | D10 |
|---|---|---|---|---|
| families with an edge retired by the rule of 3.0 | 7 of 42 | 25 of 140 | 102 of 944 | 18 of 123 |
| their true Sharpe ratio, 10th / 50th / 90th percentile | 0.38 / 0.73 / 0.85 | 0.27 / 0.56 / 0.99 | 0.27 / 0.72 / 1.06 | 0.29 / 0.32 / 0.67 |
| forward years on record when retired | 3.6 / 4.5 / 6.3 | 3.2 / 4.1 / 6.4 | 3.2 / 4.9 / 6.6 | 3.0 / 3.8 / 6.7 |
| their forward Sharpe estimate | 0.24 / 0.44 / 0.67 | −0.04 / 0.51 / 0.89 | 0.08 / 0.58 / 1.12 | −0.34 / 0.28 / 0.65 |
| posterior mean of their edge, central model | 0.00 / 0.02 / 0.08 | −0.01 / 0.08 / 0.32 | 0.08 / 0.33 / 0.58 | −0.12 / 0.00 / 0.16 |
| `Π^max` | 0.06 / 0.09 / 0.21 | 0.05 / 0.16 / 0.62 | 0.20 / 0.65 / 0.95 | 0.04 / 0.18 / 0.48 |
| forecast `PP^max` | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| **forecast with the family's true edge in place of the posterior draws** | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| **one-sided p-value of the family's own forward record against an edge of 0.25** | 0.50 / 0.67 / 0.79 | 0.28 / 0.72 / 0.91 | 0.34 / 0.75 / 0.98 | 0.13 / 0.52 / 0.82 |
| share with that p-value below 0.05 | 0.00 | 0.04 | 0.00 | 0.06 |

- The forecast was exactly 0.00 for 139 of the 152 retired families and never above 0.045, so no cut-off is near them: the same finding.
- **Added: the forecast stays at zero when the true edge replaces the posterior draws.** So it is not only that the tier's bar is high. The forecast updates each model's present posterior as if it were a normal prior and does not refit (a declared approximation, Protocol §9.1 and SIM_PREREG_v2 §2(f)). A posterior of standard deviation 0.13 to 0.22 then weighs as much as 20 to 60 years of forward data, and no simulated future can move it. That is why relaxing the tier's bar and the horizon together still left 0.07 to 0.12 where edges are rare (`replay_table.txt`).
- **Added: the retired families' own forward records were not against them.** The one-sided p-value of "the edge is at least 0.25" on a family's own forward record had a median of 0.52 to 0.75; it was below 0.05 for 2 of the 152. That observation is what the alternative of section 3 is built on.

## 2. Diagnostics of the rule on the branch

Reported as diagnostics only: no criterion reads them. "Ever dormant" counts a family dormant at any review; M8 counts it only if it ends dormant or was dormant for more than half its forward life.

### At the four pre-registered review dates (the pilot of record's replications)

| | D02 | D05 | D08 | D10 |
|---|---|---|---|---|
| replications | 12 | 12 | 12 | 12 |
| families with a true edge | 42 | 140 | 944 | 123 |
| **premature elimination (M8)**: estimate (pre-registered interval; interval with the replication as the cluster) | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 42 | 0.014 (0.000 to 0.032; clustered 0.000 to 0.034); 2 of 140 | 0.002 (0.000 to 0.007; clustered 0.000 to 0.007); 2 of 944 | 0.008 (0.000 to 0.029; clustered 0.000 to 0.026); 1 of 123 |
| the same under the rule of 3.0, on the same fits | 0.167 (0.045 to 0.261; clustered 0.031 to 0.302); 7 of 42 | 0.179 (0.138 to 0.216; clustered 0.130 to 0.227); 25 of 140 | 0.108 (0.081 to 0.138; clustered 0.073 to 0.143); 102 of 944 | 0.146 (0.092 to 0.197; clustered 0.084 to 0.209); 18 of 123 |
| **share of families with a true edge ever made dormant** | 0.000 (0) | 0.014 (2) | 0.002 (2) | 0.008 (1) |
| under the rule of 3.0 | 0.167 (7) | 0.179 (25) | 0.108 (102) | 0.146 (18) |
| true Sharpe ratio of those ever dormant: 10th / 50th / 90th percentile | none | 0.30 / 0.41 / 0.52 | 0.26 / 0.26 / 0.26 | 0.34 / 0.34 / 0.34 |
| **how long they were dormant**, years: mean / median / longest | none | 3.0 / 3.0 / 3.0 | 3.0 / 3.0 / 3.0 | 3.0 / 3.0 / 3.0 |
| as a share of their forward life: mean | none | 0.31 | 0.37 | 0.34 |
| **reactivation**, families with a true edge: woken / of those dormant again at the end / Promising at the end / Statistically supported at the end | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| premature elimination had nothing ever been reactivated (every family ever dormant counted) | 0.000 | 0.014 | 0.002 | 0.008 |
| premature elimination had nothing been able to wake at the last date | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 42 | 0.014 (0.000 to 0.032; clustered 0.000 to 0.034); 2 of 140 | 0.002 (0.000 to 0.007; clustered 0.000 to 0.007); 2 of 944 | 0.008 (0.000 to 0.029; clustered 0.000 to 0.026); 1 of 123 |
| **delay to tier entry**: families with a true edge that enter Statistically supported with no dormancy / never enter because dormant / enter later because dormant | 0 / 0 / 0 | 10 / 0 / 0 | 126 / 0 / 0 | 23 / 0 / 0 |
| the same under the rule of 3.0 | 0 / 0 / 0 | 10 / 0 / 0 | 126 / 0 / 0 | 23 / 0 / 0 |
| families with no edge: ever dormant / dormant at the end (shares) | 0.140 / 0.138 | 0.139 / 0.139 | 0.027 / 0.026 | 0.197 / 0.197 |
| under the rule of 3.0 | 0.359 / 0.359 | 0.370 / 0.370 | 0.337 / 0.337 | 0.378 / 0.378 |
| families with no edge: reactivated / of those dormant again at the end | 6 / 0 | 1 / 0 | 2 / 0 | 0 / 0 |
| **attention**: share of family-reviews written (1 with no dormancy) | 0.925 | 0.929 | 0.990 | 0.895 |
| under the rule of 3.0 | 0.783 | 0.780 | 0.846 | 0.772 |

### With a review every year (a development experiment; the same worlds)

| | D02 | D05 | D08 | D10 |
|---|---|---|---|---|
| replications | 12 | 12 | 12 | 12 |
| families with a true edge | 42 | 140 | 944 | 123 |
| **premature elimination (M8)**: estimate (pre-registered interval; interval with the replication as the cluster) | 0.048 (0.000 to 0.129; clustered 0.000 to 0.153); 2 of 42 | 0.071 (0.040 to 0.106; clustered 0.032 to 0.111); 10 of 140 | 0.005 (0.000 to 0.015; clustered 0.000 to 0.015); 5 of 944 | 0.057 (0.018 to 0.097; clustered 0.010 to 0.104); 7 of 123 |
| the same under the rule of 3.0, on the same fits | 0.714 (0.595 to 0.842; clustered 0.558 to 0.871); 30 of 42 | 0.579 (0.489 to 0.662; clustered 0.476 to 0.681); 81 of 140 | 0.453 (0.407 to 0.502; clustered 0.395 to 0.512); 428 of 944 | 0.431 (0.375 to 0.492; clustered 0.364 to 0.498); 53 of 123 |
| **share of families with a true edge ever made dormant** | 0.048 (2) | 0.079 (11) | 0.006 (6) | 0.065 (8) |
| under the rule of 3.0 | 0.738 (31) | 0.579 (81) | 0.459 (433) | 0.439 (54) |
| true Sharpe ratio of those ever dormant: 10th / 50th / 90th percentile | 0.31 / 0.44 / 0.57 | 0.26 / 0.28 / 0.73 | 0.26 / 0.28 / 0.68 | 0.30 / 0.32 / 0.34 |
| **how long they were dormant**, years: mean / median / longest | 2.0 / 2.0 / 3.0 | 3.4 / 2.0 / 7.0 | 3.3 / 3.5 / 5.0 | 3.5 / 3.5 / 6.0 |
| as a share of their forward life: mean | 0.34 | 0.48 | 0.47 | 0.48 |
| **reactivation**, families with a true edge: woken / of those dormant again at the end / Promising at the end / Statistically supported at the end | 0 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 |
| premature elimination had nothing ever been reactivated (every family ever dormant counted) | 0.048 | 0.079 | 0.006 | 0.065 |
| premature elimination had nothing been able to wake at the last date | 0.048 (0.000 to 0.129; clustered 0.000 to 0.153); 2 of 42 | 0.079 (0.048 to 0.109; clustered 0.043 to 0.114); 11 of 140 | 0.005 (0.000 to 0.015; clustered 0.000 to 0.015); 5 of 944 | 0.057 (0.018 to 0.097; clustered 0.010 to 0.104); 7 of 123 |
| **delay to tier entry**: families with a true edge that enter Statistically supported with no dormancy / never enter because dormant / enter later because dormant | 0 / 0 / 0 | 10 / 0 / 0 | 152 / 0 / 0 | 22 / 0 / 0 |
| the same under the rule of 3.0 | 0 / 0 / 0 | 10 / 0 / 0 | 152 / 1 / 0 | 22 / 0 / 0 |
| families with no edge: ever dormant / dormant at the end (shares) | 0.457 / 0.452 | 0.407 / 0.402 | 0.074 / 0.064 | 0.523 / 0.518 |
| under the rule of 3.0 | 0.804 / 0.804 | 0.806 / 0.805 | 0.783 / 0.783 | 0.813 / 0.812 |
| families with no edge: reactivated / of those dormant again at the end | 15 / 0 | 15 / 0 | 19 / 0 | 13 / 0 |
| **attention**: share of family-reviews written (1 with no dormancy) | 0.720 | 0.747 | 0.964 | 0.664 |
| under the rule of 3.0 | 0.421 | 0.425 | 0.549 | 0.416 |

What they say:

- **Ever dormant and retired are nearly the same families.** At the four dates 5 families with an edge were ever dormant under the branch's rule and 5 count as retired; with yearly reviews 27 and 24. A family with an edge that is put aside almost never comes back: 0 were reactivated at the four dates and 3 with yearly reviews. To come back it needs `Π^max` or the forecast at 0.15, and a record that looked like no edge rarely improves that much in the years left. **Reactivation does little under this rule**; what protects a family with an edge is not being put aside in the first place.
- **Durations.** Those put aside were dormant for 3.0 years on average at the four dates (from year 7 to the end) and 3.3 years with yearly reviews (longest 7).
- **Delay to tier entry: none.** No family that enters Statistically supported when nothing is ever dormant is kept out or delayed by the branch's rule, at either calendar (159 and 184 entries). Even the rule of 3.0 kept out only 0 and 1: the families a dormancy rule retires are not the ones about to enter the tier. What premature elimination costs is the attention a family with a real edge stops getting, not a tier entry.
- **Families with no edge** are where the two calendars differ most: the share dormant at the end roughly triples with yearly reviews, and so does the attention saved.
- **Compute.** Dormancy saves no computing in either form: every family's data stay in the model, and the forecast is made for every family below the tier. The cost of a rule is in the reviews written.

## 3. An alternative second condition: the family's own forward record (not adopted)

**The two rules.** Both keep the forecast of 3.0 and its thresholds (0.05 at two consecutive reviews, 0.15 to wake) and add a second number that must also be below 0.05:

| | second number | what it uses |
|---|---|---|
| **on the branch** (Protocol 3.1 §9.1) | `Π^max`: the largest, over the six models, of the posterior probability that the family's edge is at least `θ_min` | the model: the family's reserve and forward results, and every other family through the priors it learns |
| **alternative** (`own_record.py`) | `p^F = Φ((y^F − θ_min)/s^F)`: the one-sided p-value of "the edge is at least `θ_min`" on the family's forward Sharpe estimate and its standard error; needs 252 forward days | the family's own forward returns and nothing else. It is also the posterior probability of an edge of `θ_min` under a flat prior on that record: the reading that pools nothing |

**Measured on the same fits, at the four pre-registered dates:**

| | rule | D02 | D05 | D08 | D10 |
|---|---|---|---|---|---|
| premature elimination (M8) | the rule of 3.0 (forecast alone) | 0.167 (0.045 to 0.261; clustered 0.031 to 0.302); 7 of 42 | 0.179 (0.138 to 0.216; clustered 0.130 to 0.227); 25 of 140 | 0.108 (0.081 to 0.138; clustered 0.073 to 0.143); 102 of 944 | 0.146 (0.092 to 0.197; clustered 0.084 to 0.209); 18 of 123 |
| premature elimination (M8) | the rule on the branch (forecast and `Π^max`) | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 42 | 0.014 (0.000 to 0.032; clustered 0.000 to 0.034); 2 of 140 | 0.002 (0.000 to 0.007; clustered 0.000 to 0.007); 2 of 944 | 0.008 (0.000 to 0.029; clustered 0.000 to 0.026); 1 of 123 |
| premature elimination (M8) | alternative (forecast and own forward record) | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 42 | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 140 | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 944 | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 123 |
| families with an edge ever dormant | the rule of 3.0 (forecast alone) | 0.167 | 0.179 | 0.108 | 0.146 |
| families with an edge ever dormant | the rule on the branch (forecast and `Π^max`) | 0.000 | 0.014 | 0.002 | 0.008 |
| families with an edge ever dormant | alternative (forecast and own forward record) | 0.000 | 0.007 | 0.000 | 0.000 |
| families with no edge dormant at the end | the rule of 3.0 (forecast alone) | 0.359 | 0.370 | 0.337 | 0.378 |
| families with no edge dormant at the end | the rule on the branch (forecast and `Π^max`) | 0.138 | 0.139 | 0.026 | 0.197 |
| families with no edge dormant at the end | alternative (forecast and own forward record) | 0.012 | 0.017 | 0.019 | 0.054 |
| family-reviews written | the rule of 3.0 (forecast alone) | 0.783 | 0.780 | 0.846 | 0.772 |
| family-reviews written | the rule on the branch (forecast and `Π^max`) | 0.925 | 0.929 | 0.990 | 0.895 |
| family-reviews written | alternative (forecast and own forward record) | 0.993 | 0.992 | 0.994 | 0.973 |

**With a review every year:**

| | rule | D02 | D05 | D08 | D10 |
|---|---|---|---|---|---|
| premature elimination (M8) | the rule of 3.0 (forecast alone) | 0.714 (0.595 to 0.842; clustered 0.558 to 0.871); 30 of 42 | 0.579 (0.489 to 0.662; clustered 0.476 to 0.681); 81 of 140 | 0.453 (0.407 to 0.502; clustered 0.395 to 0.512); 428 of 944 | 0.431 (0.375 to 0.492; clustered 0.364 to 0.498); 53 of 123 |
| premature elimination (M8) | the rule on the branch (forecast and `Π^max`) | 0.048 (0.000 to 0.129; clustered 0.000 to 0.153); 2 of 42 | 0.071 (0.040 to 0.106; clustered 0.032 to 0.111); 10 of 140 | 0.005 (0.000 to 0.015; clustered 0.000 to 0.015); 5 of 944 | 0.057 (0.018 to 0.097; clustered 0.010 to 0.104); 7 of 123 |
| premature elimination (M8) | alternative (forecast and own forward record) | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 42 | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 140 | 0.000 (0.000 to 0.000; clustered 0.000 to 0.265); 0 of 944 | 0.016 (0.000 to 0.039; clustered 0.000 to 0.040); 2 of 123 |
| families with an edge ever dormant | the rule of 3.0 (forecast alone) | 0.738 | 0.579 | 0.459 | 0.439 |
| families with an edge ever dormant | the rule on the branch (forecast and `Π^max`) | 0.048 | 0.079 | 0.006 | 0.065 |
| families with an edge ever dormant | alternative (forecast and own forward record) | 0.000 | 0.007 | 0.003 | 0.024 |
| families with no edge dormant at the end | the rule of 3.0 (forecast alone) | 0.804 | 0.805 | 0.783 | 0.812 |
| families with no edge dormant at the end | the rule on the branch (forecast and `Π^max`) | 0.452 | 0.402 | 0.064 | 0.518 |
| families with no edge dormant at the end | alternative (forecast and own forward record) | 0.061 | 0.071 | 0.083 | 0.200 |
| family-reviews written | the rule of 3.0 (forecast alone) | 0.421 | 0.425 | 0.549 | 0.416 |
| family-reviews written | the rule on the branch (forecast and `Π^max`) | 0.720 | 0.747 | 0.964 | 0.664 |
| family-reviews written | alternative (forecast and own forward record) | 0.965 | 0.958 | 0.967 | 0.884 |

How often each condition holds, among reviews of families that are neither dormant nor supported and have a year of forward record (branch path): the forecast is below 0.05 in 0.95 (D02), 0.94 (D05), 0.78 (D08), 0.94 (D10) of them; the forecast and `Π^max` in 0.51, 0.47, 0.06, 0.62; the forecast and `p^F` in 0.08, 0.09, 0.07, 0.22. The forecast alone decides almost nothing under either rule: it is below 0.05 for most families at most reviews.

**The trade, in words.**

- **What the branch's rule has and the alternative lacks: it still retires families.** It leaves a real share of the families with no edge dormant, more with more reviews, and so saves attention, which is what dormancy is for. It also uses the reserve record, which the alternative ignores.
- **What the alternative has and the branch's rule lacks: an error that does not depend on the other families.** V7 is a statement about families that have an edge. `Π^max` is calibrated over all families: among families given 0.05, about 5% have an edge. That bounds the share of edges among the retired, not the share of the edges that are retired, and the second is the first divided by how rare edges are. `p^F` is below 0.05 with probability 0.05 for a family whose edge is exactly `θ_min`, at each review, whatever the rest of the programme is, and less often for a larger edge. The difference shows with yearly reviews: more looks give `Π^max` more chances to retire a family with a small edge and an unlucky start, while a record that is not against a family stays not against it.
- **What the alternative costs: almost all of dormancy.** An edge of 0 and an edge of 0.25 are a quarter of a Sharpe ratio apart and the standard error of a forward Sharpe ratio after `T` years is about `1/√T`: a family with no edge has `p^F < 0.05` with probability about 0.10 after two years, 0.13 after four and 0.20 after ten. Ten years of a family's own returns cannot tell 0 from 0.25. A rule that retires more does so on the model's word about families in general. `DORMANCY_DIAGNOSIS.md` says the same of its own rule ("it rests on the model twice").
- **Neither is wrong.** The branch's rule passes V7 as pre-registered (four dates) on the pilot. The question for Ethan is whether dormancy should be allowed to rest on the model's reading of a family when production reviews quarterly, or only on the family's own record at the price of retiring nearly nobody. A middle course the first session measured is its own rule with a stricter level (`Π^max < 0.02`).

**If Ethan prefers the alternative.** A complete version of it (the text of §9.1 with its box, the code as `manhattan/stats/dormancy.py`, 12 tests, the SIM_PREREG_v2 reading, a re-hashed record) is on the branch `claude/epic-mayer-kfhpsh` at commit `1124fe7`, written before this session found the first session's push; the full suite passed on it. It is not merged anywhere. Taking it means replacing §9.1 and `dormancy.py` on `build/manhattan`, re-hashing, and rerunning the HB pilot. A partial pilot of it through the runner (36 replications of D02, 18 of D10, stopped when the overlap was found) retired 2 of 143 families with an edge in D02 and none of 190 in D10.

## 4. Which of the six models keeps a family out of "Statistically supported" (a supplement for the tier's bar)

`DORMANCY_DIAGNOSIS.md` part 4 has the table Ethan asked for: who reaches the tier by years 4, 6 and 10, by true Sharpe ratio. This adds one view of why, from the traced pilot replications at year 10 (families with a true edge and at least two forward years; the same bands). It is not a proposal and nothing was rerun: the six posterior probabilities the pilot computed, read four ways. The first column is the tier's own condition on `Π` (the tier also needs a positive forward mean and enough forward days, which these columns ignore).

| true hedged Sharpe ratio | families | mean forward years | `Π^min ≥ 0.80` (the rule) | central model alone `≥ 0.80` | smallest of S0 to S3 (without S4 and S5) | smallest of S0 to S4 (without the decay model S5) | the most cautious model is S4 / S5 |
|---|---|---|---|---|---|---|---|
| 0.25 to 0.5 | 160 | 5.9 | 0.01 | 0.13 | 0.09 | 0.03 | 0.15 / 0.82 |
| 0.5 to 0.75 | 210 | 5.6 | 0.01 | 0.36 | 0.27 | 0.07 | 0.16 / 0.82 |
| 0.75 to 1 | 294 | 6.2 | 0.03 | 0.67 | 0.59 | 0.17 | 0.22 / 0.77 |
| 1 to 1.5 | 317 | 6.2 | 0.21 | 0.92 | 0.86 | 0.47 | 0.32 / 0.68 |
| 1.5 and above | 46 | 5.9 | 0.54 | 1.00 | 0.98 | 0.85 | 0.46 / 0.52 |

S4 inflates every standard error by half. S5 says the forward edge halves every three years and asks about the edge now: a family nine years old needs an edge eight times `θ_min` at its freeze to pass it. For a family with a true Sharpe ratio between 1 and 1.5 the central model says 0.80 or more nine times in ten and the most cautious of six about one time in five; the difference is almost all S5 and S4.

## 5. What this file does not show

1. Anything at the pre-registered count: 12 replications a scenario against 400.
2. Quarterly reviews, which is what production uses. Yearly is as far as either session went.
3. Either rule on a held-out scenario. H09 (dormancy then reactivation) is the pre-registered test of late-starting edges and is not coded.
4. That the alternative's standard error is right under fat tails or serial correlation beyond what these four scenarios contain (D05 has Student-t noise with 3 degrees of freedom).
