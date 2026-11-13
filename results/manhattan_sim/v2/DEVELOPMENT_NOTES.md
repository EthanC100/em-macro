# Manhattan simulation: development experiments behind Protocol v3.1 (session 5M, 2026-11-12)

**Synthetic data only. Development scenarios only (seed branch 0). No held-out scenario was coded or run.**

These are the experiments made **outside the runner** while the two methods were being revised, as SIM_PREREG
section 3 allows on development scenarios. Each is recorded as a note in `results/manhattan_sim/runs.jsonl`. They
are not pilots of record and decide nothing; the logged pilot rerun is `PILOT_RERUN_REPORT.md` in this folder.
They are kept because they are the reasons for two choices in PROTOCOL_v3.1.md, and because a choice made on
evidence should show the evidence, including the variants that were tried and dropped.

## 1. Where to centre the resamples (D11, replications 0 to 39)

Question: the brief fixed **what** to do (re-estimate the core hedge inside every bootstrap resample, by the live
rule). It left open what the resampled means are compared with. Four candidates were computed from the **same**
999 resamples of every family (so differences between them are not resampling noise), with Hansen's consistent
recentring, at a fixed 999 resamples:

| test | hedge in the resamples | resampled mean is centred at | size at 0.05 | size at 0.20 | minus the oracle, at 0.05 |
|---|---|---|---|---|---|
| 3.0 (the pilot's) | as estimated once, live | the live mean `d̄_k` | 0.0727 (0.0634 to 0.0820) | 0.2550 (0.2336 to 0.2765) | +0.0177 ± 0.0056 |
| A | re-estimated | the live mean `d̄_k` | 0.0700 (0.0611 to 0.0788) | 0.2416 (0.2213 to 0.2618) | +0.0150 ± 0.0057 |
| C | re-estimated | the resamples' own mean | 0.0664 (0.0574 to 0.0753) | 0.2436 (0.2226 to 0.2647) | +0.0113 ± 0.0054 |
| **B (adopted in 3.1)** | re-estimated | **the window's least-squares intercept `α̂_k`** | **0.0466 (0.0404 to 0.0529)** | **0.1983 (0.1803 to 0.2162)** | −0.0084 ± 0.0024 |
| E (a different statistic) | none: the window's least-squares intercept is itself the statistic, pairs bootstrap | its own estimate | 0.0534 (0.0462 to 0.0605) | 0.2100 (0.1907 to 0.2292) | −0.0016 ± 0.0023 |
| oracle | none needed: the true hedged returns | their mean | 0.0550 (0.0478 to 0.0622) | 0.2109 (0.1913 to 0.2305) | 0 |

40 replications, about 470 families with no edge in each; intervals are `mean ± 1.96 sd/√40` over replications;
the last column is the paired difference, replication by replication.

What it shows:

1. **Re-estimating the hedge is not enough by itself** (A and C): the size barely moves. The 3.0 test is wrong
   because its statistic contains what the hedge lets through and its null distribution does not; re-estimating
   and then subtracting the live mean, or the resamples' own mean, removes it from the null distribution again.
2. **Centring at the window's intercept repairs it** (B). The intercept is the mean of the perfectly hedged
   return in the world the resamples are drawn from, so what is left after subtracting it is what the live rule
   does around a known truth. B is the direct reading of the brief with the one centre that makes it work, so it
   is what PROTOCOL_v3.1.md §5.1 specifies.
3. **B is a little conservative**: about 0.008 below the oracle at 0.05 and 0.013 at 0.20. The resamples begin
   from the actual history before the window, as the live hedge did, and the exposure in that history differs
   from the window's average, which adds variance to the resampled means. That costs a little power and no
   validity.
4. **E** is the other honest way to do it (test the in-window intercept itself). It is closest to the oracle and
   does not depend on the hedge rule at all, but it changes the statistic of §5.1 from the mean of the live
   hedged return to a regression intercept, which the brief did not ask for. It is recorded here as an
   alternative for Ethan; it is not in 3.1.
5. The oracle's own size in these 40 replications is 0.055: D11's world is a little above nominal even with a
   perfect hedge, as several scenarios of version 1's pilot were (D01: 0.062 on 12 replications).

The mean of what the live hedge lets through, in units of the test statistic: 0.065, with standard deviation
0.29 across families. The mean is the ridge's shrinkage (about 9% of an exposure of 0.5 to a factor with
annualised Sharpe ratio 0.6); the spread is the three-year window running behind an exposure that wanders.

## 2. A harder hedge (D11's world with factor Sharpe 0.8 and exposure drift 0.4 a year, replications 0 to 11)

Question: does the adopted test hold where the hedge leaks more? This is the top corner of the ranges
SIM_PREREG_v2 gives held-out scenario H12 for one factor (not H12 itself: no held-out world exists).

| test | size at 0.05 | size at 0.20 | minus the oracle, at 0.05 |
|---|---|---|---|
| 3.0 | 0.0969 (0.0758 to 0.1181) | 0.3034 (0.2650 to 0.3418) | +0.0364 ± 0.0169 |
| A | 0.0908 (0.0704 to 0.1112) | 0.2875 (0.2504 to 0.3246) | +0.0302 ± 0.0178 |
| C | 0.0825 (0.0634 to 0.1016) | 0.2849 (0.2472 to 0.3226) | +0.0219 ± 0.0162 |
| **B (3.1)** | **0.0493 (0.0371 to 0.0615)** | **0.2123 (0.1824 to 0.2422)** | −0.0113 ± 0.0052 |
| E | 0.0596 (0.0470 to 0.0723) | 0.2247 (0.1920 to 0.2575) | −0.0010 ± 0.0059 |
| oracle | 0.0606 (0.0478 to 0.0734) | 0.2338 (0.1966 to 0.2710) | 0 |

12 replications. The 3.0 test gets worse (0.097), the 3.1 test does not (0.049). Not tried: several factors at
once, which H12 has and which only unit tests of the arithmetic cover so far.

## 3. The analytic model without a common shock (HB, replications 0 to 3 of D01, D02, D05, D08, D10)

The first version of the analytic model treated families as independent given its hyperparameters, with no
term for luck shared between them. Four replications of each HB development scenario:

- It computed every review (20 replications, 80 reviews, none refused by the grid gate), at about 1.3 seconds
  for the six fits of a review of 240 families on an idle core.
- **It failed on shared luck.** In D05 (fat tails), replication 1, year 10, a market-wide shock had lifted the
  reserve estimates of late batches and the forward estimates of early ones together. The model read the common
  level as a common edge: posterior mean of `μ_A` 0.27, retention 0.90 to 0.93, and **188 of the 240 families
  were given a central posterior probability between 0.3 and 0.6** (over the four replications, fewer than 2%
  of the families in those bins had an edge). Over the four replications the central model's expected
  calibration error at year 10, taken over all ten bins, was 0.123 (the bound, on bins of at least 200
  observations, is 0.10).
- **The repair, now in PROTOCOL_v3.1.md §7.1**: one shock common to every forward estimate, carrying the share
  `r` of its sampling variance that the families' returns show to be common (measured, about 0.05 to 0.07 in
  that replication). On the same replication the model then infers a shock of +2.3 standard deviations and
  219 of the 240 families are below 0.2. Cost: the six fits take about 6 seconds instead of 1.3.

This is a change made on a development scenario, on a mechanism the first draft had already listed as a known
loss ("no sampling covariance between families"). What it does not repair is said in §7.2(g) of the protocol.

## 4. Smaller things run by hand

- One HB replication each of D02 and D05 with per-family printouts, to read the model's answers family by
  family (how the pessimistic-retention, inflated-standard-error and decay models bind; see
  MANHATTAN_PROGRESS.md).
- Runner smoke tests on programmes of a few batches (the sizes patched in memory, results in a temporary
  directory, nothing kept).
- A stopped run: the first logged HB pilot was stopped part-way through D05 because the model's code was
  about to change; its start record in the run log has no end record, and a note beside it says so. Its D01 and
  D02 replications were made by code that is no longer checked out and are not counted in any report.

## 5. Session 6M: the dormancy rule, D08's calibration, yearly reviews

The experiments behind the pre-adoption change of Protocol 3.1 §9.1 (its change 5) and the limitation stated in
§7.2(d) are in [DORMANCY_DIAGNOSIS.md](DORMANCY_DIAGNOSIS.md): the replay of the pilot's 48 HB replications
with per-family values, every variant of the rule that was scored on them, three posteriors on D08's estimates,
and the same worlds with yearly reviews. Notes `note-6M-01` to `note-6M-04` in the run log.
