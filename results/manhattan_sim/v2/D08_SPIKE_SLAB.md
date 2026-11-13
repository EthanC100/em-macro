# D08 and a two-group ("spike and slab") prior: the edge share is not identified, and the candidate is not adopted

Written by `results/manhattan_sim/v2/dev_10M/spike_identification.py report` (session "10M Manhattan C: final pre-adoption changes", 2026-11-13). **Synthetic data only. Development scenario D08 only (seed branch 0). No held-out scenario was coded or run. A development experiment outside the runner (note `note-10M-01` in the run log): it decides nothing, and no run of record uses the candidate.**

## 1. What was tried, and the test fixed before it was run

Protocol 3.1 §7.2(d) states a limitation: where a large share of families has an edge of exactly zero and the rest have clear ones (D08), the central model's one hump says too much in the middle of the scale (calibration error 0.101 at year 10 against a bound of 0.10). Ethan asked for one repair to be tried (`manhattan/stats/hier_spike.py`):

- **slab** (probability `π`): the model as it is, `θ_f = ρ a_f + η_f`;
- **spike** (probability `1 − π`): the slab at retention 0 with the existing 0.02 innovation, `θ_f = η_f`, `η_f ~ Normal(0, 0.02²)`. No new constant;
- **the edge share `π`**: uniform on ten grid nodes, 0.05, 0.15, ..., 0.95, one share for the programme.

With the share fixed at 1 the candidate is the analytic model number for number (`tests/test_manhattan_hier_spike.py`: all six models, with a common shock, missing forward records and an adaptive-channel family; log evidence to 1e-9, every family's `Π`, mean and standard deviation to 1e-10).

An earlier attempt at a two-group prior had put the share near 0.9 where the truth was 0.35, so the share was checked **first**, before the candidate was wired into any pipeline. The criterion was written into the script before its first run:

> The share is identified if, in D08 at HB on the pilot's 12 replications, at year 4 **and** at year 10 (the dates at which V6 is decided), under the central model: (1) the posterior standard deviation of the share is at most half the prior's (0.287 / 2 = 0.144) on average, and (2) the posterior mean is within 0.10 of the true share of families with an edge, on average. Otherwise it is not identified, the candidate is not adopted, and D08 stays a documented limitation.

## 2. Result on D08 (the test that counts)

The inputs are the pilot of record's own: the HB pipeline's functions and random streams, the same estimates and standard errors (the one-group fit below reproduces the pilot's calibration counts at year 10 bin for bin). Central model (S0).

| date | replications | families at the review | true share with an edge of at least 0.25 (mean; range) | **posterior mean of the share** (mean; range) | posterior sd (mean) | mean absolute error | most probable node | log likelihood, best node minus worst (mean) | criterion (1): sd ≤ 0.144 | criterion (2): error ≤ 0.10 |
|---|---|---|---|---|---|---|---|---|---|---|
| year 4 | 12 | 100 | 0.316 (0.180 to 0.390) | **0.777** (0.499 to 0.885) | 0.163 | 0.461 | 0.55, 0.85, 0.95 | 6.8 | **not met** | **not met** |
| year 10 | 12 | 240 | 0.328 (0.237 to 0.404) | **0.896** (0.839 to 0.936) | 0.068 | 0.569 | 0.85, 0.95 | 37.6 | met | **not met** |

**Verdict: the share is not identified.** Neither date meets the criterion. At year 10 the posterior is narrow and in the wrong place: 0.90 where 0.33 of the families have an edge, the figure the earlier attempt had found. More data do not help it; they make it surer (the log likelihood of the best node is 20 to 50 above the worst at year 10). At year 4 it is wider and no nearer.

Replication by replication:

| replication | year 4: true share / posterior mean / sd | year 10: true share / posterior mean / sd | year 10: posterior probability of the slab, families with an edge / families with none | year 10: retention of the three classes, one group / two groups |
|---|---|---|---|---|
| 0 | 0.390 / 0.885 / 0.096 | 0.350 / 0.928 / 0.047 | 0.96 / 0.92 | 0.81, 0.87, 0.84 / 0.81, 0.87, 0.84 |
| 1 | 0.350 / 0.808 / 0.143 | 0.338 / 0.917 / 0.057 | 0.96 / 0.90 | 0.88, 0.90, 0.91 / 0.89, 0.91, 0.91 |
| 2 | 0.220 / 0.785 / 0.170 | 0.250 / 0.919 / 0.058 | 0.94 / 0.92 | 0.81, 0.81, 0.81 / 0.82, 0.81, 0.81 |
| 3 | 0.250 / 0.668 / 0.215 | 0.329 / 0.839 / 0.094 | 0.92 / 0.81 | 0.85, 0.69, 0.80 / 0.87, 0.74, 0.83 |
| 4 | 0.380 / 0.875 / 0.101 | 0.367 / 0.936 / 0.038 | 0.97 / 0.92 | 0.87, 0.89, 0.83 / 0.86, 0.88, 0.82 |
| 5 | 0.390 / 0.852 / 0.114 | 0.404 / 0.908 / 0.066 | 0.95 / 0.88 | 0.83, 0.86, 0.73 / 0.85, 0.87, 0.75 |
| 6 | 0.350 / 0.826 / 0.149 | 0.333 / 0.916 / 0.059 | 0.96 / 0.90 | 0.86, 0.86, 0.86 / 0.86, 0.86, 0.86 |
| 7 | 0.350 / 0.772 / 0.194 | 0.317 / 0.874 / 0.084 | 0.93 / 0.85 | 0.82, 0.75, 0.86 / 0.85, 0.78, 0.88 |
| 8 | 0.290 / 0.788 / 0.163 | 0.296 / 0.846 / 0.098 | 0.92 / 0.82 | 0.78, 0.65, 0.84 / 0.82, 0.69, 0.86 |
| 9 | 0.340 / 0.842 / 0.129 | 0.379 / 0.933 / 0.041 | 0.96 / 0.93 | 0.80, 0.76, 0.84 / 0.81, 0.77, 0.86 |
| 10 | 0.180 / 0.721 / 0.201 | 0.237 / 0.854 / 0.098 | 0.92 / 0.84 | 0.73, 0.78, 0.73 / 0.76, 0.79, 0.75 |
| 11 | 0.300 / 0.499 / 0.277 | 0.333 / 0.886 / 0.080 | 0.93 / 0.87 | 0.78, 0.71, 0.75 / 0.81, 0.74, 0.77 |

## 3. Why: the two groups of D08 are not where this spike is

The candidate gives a family with **no** edge a probability of 0.88 of being in the slab at year 10, against 0.94 for a family with one: it cannot tell them apart, and it does not need to. The spike says "this family's forward edge has nothing to do with its apparent edge". In D08 a family is the best of 20 by its **exploration** window; the reserve estimate the model reads comes from the window after it and is not selected on. So a family with no edge has an apparent edge near zero as well, and the slab already describes it: `θ = ρ · a` with `a` near zero is near zero. The retention the model learns is 0.65 to 0.91 with one group or with two (last column above), which is right for D08: an edge that is there stays. What the share measures is therefore the share of families whose forward edge follows their apparent edge, and in D08 that is nearly all of them. **D08's two groups are in the apparent edge `a_f` itself** (two thirds at zero, one third at 0.5 to 1.5), which is the prior of `a_f`, one hump with a learned centre and spread; a spike in the retention does not change that prior.

Checked on the worlds themselves (`apparent`, no model): the family portfolio's sample Sharpe ratio, mean over families.

| replication | families with no edge / with one | no edge: exploration window (selected on) | **no edge: reserve window (what the model reads)** | with an edge: exploration window | with an edge: reserve window | with an edge: true Sharpe ratio |
|---|---|---|---|---|---|---|
| 0 | 156 / 84 | 0.70 | **-0.06** (sd 0.36) | 1.05 | 0.93 | 0.91 |
| 1 | 159 / 81 | 0.69 | **-0.04** (sd 0.36) | 1.04 | 0.86 | 0.87 |
| 2 | 180 / 60 | 0.79 | **-0.15** (sd 0.36) | 1.15 | 0.64 | 0.85 |

Selection inflates the exploration window (0.7 for a family with nothing) and leaves the reserve window alone (about zero, with the spread sampling error gives): on the reserve the two groups are already apart.

## 4. The same check on data drawn from the candidate itself

To see whether the failure is in the algebra or in the fit to D08: families drawn from the two-group model (share 0.35; apparent edges Normal(1.0, 0.35²), so that a spike family has a high apparent edge and nothing forward; retention 0.7; reserve window 1,750 days; forward records of a quarter to `horizon` years; 12 draws a row).

| families | forward records up to | posterior mean of the share (true 0.35) | posterior sd | mean absolute error | log likelihood, best node minus worst | identified by the criterion |
|---|---|---|---|---|---|---|
| 96 | 4 years | 0.546 | 0.207 | 0.189 | 4.1 | no |
| 240 | 10 years | 0.375 | 0.083 | 0.041 | 16.9 | yes |
| 960 | 10 years | 0.351 | 0.035 | 0.019 | 64.1 | yes |
| 2400 | 10 years | 0.351 | 0.015 | 0.013 | 165.0 | yes |

Where the world is the candidate's own, 240 families with up to ten forward years recover the share, and the 96 families a programme has at year 4 do not (the posterior stays near the prior's 0.5). So the algebra is right, the share can be learned when the two groups differ in retention and the records are long, and even then V6's first decision date comes too early for it.

## 5. Calibration, for the record

The candidate was not to be adopted unless D08's calibration improved and no other scenario worsened beyond its bound. The first test failed, so the other scenarios were not run. D08's own figures, by the pipeline's estimator (`metrics.ece_ci`: bins with at least 200 observations, percentile interval over replications):

| date | one group (the model of Protocol 3.1) | two groups (the candidate) | bound on the upper end |
|---|---|---|---|
| year 4 | 0.034 (0.004 to 0.067) | 0.007 (0.003 to 0.057) | 0.10 |
| year 10 | 0.101 (0.034 to 0.136) | 0.096 (0.037 to 0.128) | 0.10 |

Year 10, one group: stated probability / observed share with an edge / families, by bin: 0.05 / 0.02 / 600; 0.15 / 0.04 / 419; 0.25 / 0.07 / 349; 0.35 / 0.12 / 209; 0.45 / 0.18 / 216; 0.55 / 0.29 / 167; 0.65 / 0.47 / 125; 0.75 / 0.57 / 126; 0.85 / 0.90 / 155; 0.97 / 0.99 / 514.

Year 10, two groups: stated probability / observed share with an edge / families, by bin: 0.05 / 0.02 / 664; 0.15 / 0.04 / 476; 0.25 / 0.09 / 319; 0.35 / 0.15 / 229; 0.45 / 0.23 / 206; 0.55 / 0.39 / 138; 0.65 / 0.56 / 134; 0.75 / 0.77 / 123; 0.85 / 0.93 / 158; 0.97 / 1.00 / 433.

At year 10, where the limitation is, the error is all but unchanged (the middle of the scale still says too much: families given about 0.45 have an edge about a fifth of the time under either model) and the interval's upper end stays above the bound. At year 4 the candidate is better, and D08 was already inside its bound there.

## 6. What was done with it

- **Stopped, as the brief said.** The candidate is in no code list of `manhattan/sim/run.py`, the HB pipeline does not import it, it has no posterior draws for the dormancy forecast, and no pilot was run with it.
- **D08 stays a documented limitation** (Protocol 3.1 §7.2(d), which now cites this file). If the full run confirms the error, V6 fails in D08 and the posterior-based tiers stay off (SIM_PREREG_v2 §5).
- **Kept:** `manhattan/stats/hier_spike.py`, its five tests and this script, so the check can be repeated.
- **What a repair would have to be**, from section 3: two groups in the apparent edge `a_f` (a share of families at zero on the reserve window as well as forward), not in the retention. `DORMANCY_DIAGNOSIS.md` part 2 measured a prior of that shape given the truth (calibration error 0.009), and the second session of 2026-11-13 measured a crude fitted one (0.013 in D08, but 0.034 against 0.014 in D02, where edges are rare). It is another model, it would be built on the scenarios' convention that a family with no edge has a mean of exactly zero, and it is Ethan's to ask for (ETHAN_ACTIONS item 21(b)).

## 7. What this file does not show

1. Anything at the pre-registered count: 12 replications of one scenario.
2. The candidate under the other five models (S1 to S5): the central model only.
3. The candidate in D01, D02, D05 or D10: not run, because the first test failed.
4. That no two-group prior can be identified: only that this one, a spike in the retention, is not what D08 needs.
