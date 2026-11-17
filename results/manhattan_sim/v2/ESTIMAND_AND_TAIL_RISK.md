# The forward e-process: what a rejection proves, what truncation hides, a tail-risk check, and week-skipping

Written by `python -m manhattan.sim.estimand_study --report` (session 6M, 2026-11-13). **Synthetic series only.
Nothing here is adopted: Protocol section 6 is word for word what it was, and the check of section 3 is a proposal
for Ethan (ETHAN_ACTIONS item 23).**

The simulation behind sections 2 to 4 is `manhattan/sim/estimand_study.py`: single return series, 2,000
paths of ten years for each process, run through the protocol's own code for the ex-ante scale, the weekly sums,
the truncation at 6 and the variance-ratio rule (`manhattan.stats.eprocess`). **It is not a held-out scenario**: no
programme, no screening, no e-LOND and no metric of the pre-registration is computed, nothing is drawn from the
held-out generator, its random streams are its own, and no method was changed after seeing it.

## 1. What a rejection proves, exactly

**The objects.** For each component `j` of family `f` (each hypothesis portfolio and the family portfolio) and each
test week `t` after the family's enrolment:

- `P_(j,t)`: the week's sum of the component's daily **core-hedged, net** returns. Hedge ratios come from data
  before each day (Protocol §2.2); costs are the modelled ones.
- `s_(j,t)`: the weekly scale, fixed before the week from earlier days.
- `Y_(j,t) = max( P_(j,t) / s_(j,t) , −6 )`: the standardised return with any loss beyond six scales counted as
  six.
- `b_(j,t)`: 1 if the component bets that week, 0 if the variance-ratio rule, looking at the 252 days before the
  week, says not to (§6.7).
- Wealth `W_j` is the equal-weight mean, over six fixed fractions `λ`, of `Π_t ( 1 + λ · b_(j,t) · Y_(j,t) )`, and
  `W_f` is the mean of the components' wealth (§6.4, §6.5).

**The null that is tested.**

```
H0_f :  for every component j of f and every week t after enrolment in which j bets,
        E[ max( P_(j,t) / s_(j,t) , −6 )  |  everything recorded before the week ]  ≤  0
```

Under `H0_f` every factor `1 + λ b Y` has conditional expectation at most 1 and is at least 0.1, so `W_f` is a
non-negative supermartingale started at 1. e-LOND rejects when `W_f` reaches the family's bar and keeps the false
discovery rate over all enrolled families at or below 5% at every time, under any dependence (§6.8, Appendix
A.2).

**So "family `f` is formally supported" proves this and no more**, with that error rate:

> For at least one component of `f`, in at least one week in which it bet, the conditional mean, given the past,
> of the week's **core-hedged net** return **with any loss beyond six ex-ante weekly standard deviations counted
> as a loss of exactly six** was positive.

Because `s_(j,t)` is positive and known before the week, the standardisation changes nothing in that sentence:
`E[max(P/s, −6) | past] > 0` is the same event as `E[max(P, −6s) | past] > 0`.

Word by word:

| word | what it means | what it does not mean |
|---|---|---|
| truncated | each week's loss is capped at six ex-ante weekly standard deviations before the mean is taken | the mean of the return itself is positive. `Y ≥ Z` always, so the truncated mean is the larger one; the gap is the expected loss beyond the cap (section 2) |
| core-hedged | the return left after the **estimated** hedge of §2.2, with what that hedge lets through | a new mechanism. A hedge that lags leaves part of a core factor's premium in it (§2.2) |
| net | after the cost model | after real costs. Tiers above Statistically supported need measured costs (§8) |
| at least one component | a hypothesis portfolio or the family portfolio | which one (§6.10 names components at a stricter bar), or all of them |
| at least one week | the conditional mean was positive at some time | at every time, on average over time, or today. An edge that existed and decayed is validly rejected, and so is a strategy with zero mean overall whose mean is positive in spells the past reveals (section 4, last rows) |
| in which it bet | weeks the variance-ratio rule allowed | the weeks it skipped. Those are not tested at all (section 4) |
| given the past | the shared record of every family | given the family's own past only |

**The guard adds one thing, and it is not in the 5% accounting.** At the moment of rejection the running mean of
the **untruncated** standardised return of the leading component, over **all** weeks since enrolment (skipped
ones included), has an asymptotic 95% lower confidence bound above zero (§6.3). That stops a rejection when the
truncated and untruncated **records** disagree. It cannot see a loss that has not happened yet.

**A profitability claim needs more than a rejection.** "This family makes money" is a statement about the mean
of the untruncated return, over all weeks, after real costs, from now on. A rejection gives none of the four.
Section 2 measures the first gap; section 3 proposes a check for it.

## 2. How often the truncated and the untruncated mean differ in sign

**Population.** The scale is fixed before the week, so the sign of `E[Z]` is the sign of the true Sharpe ratio,
exactly. `E[Y] = E[Z] + gap`, where `gap = E[(−6 − Z)⁺]` is the expected loss beyond the cap. The two means
have opposite signs exactly when the true Sharpe ratio is zero or negative and the gap is larger than `|E[Z]|`:
in annualised Sharpe units, when the true Sharpe ratio lies in `(−gap, 0]`. Processes with a true Sharpe ratio of
zero (the gap barely moves with the mean):

| process | a crash in ex-ante weekly standard deviations | weeks truncated per decade | truncated mean minus untruncated mean, in annualised Sharpe units | true Sharpe ratios for which the two means have opposite signs |
|---|---|---|---|---|
| normal | 0.0 | 0.0 | 0.000 | none |
| Student-t, 3 df | 0.0 | 0.3 | 0.013 | (-0.013, 0] |
| Student-t, 5 df, GARCH | 0.0 | 0.1 | 0.003 | (-0.003, 0] |
| two-sided jumps of 20, 5 a decade | 8.9 | 1.9 | 0.057 | (-0.057, 0] |
| crash of 10, 0.5 a decade | 4.5 | 0.0 | 0.000 | none |
| crash of 10, 1 a decade | 4.5 | 0.1 | 0.000 | none |
| crash of 10, 2 a decade | 4.5 | 0.1 | 0.001 | (-0.001, 0] |
| crash of 10, 5 a decade | 4.5 | 0.3 | 0.002 | (-0.002, 0] |
| crash of 20, 0.5 a decade | 8.9 | 0.5 | 0.020 | (-0.020, 0] |
| crash of 20, 1 a decade | 8.9 | 1.0 | 0.037 | (-0.037, 0] |
| crash of 20, 2 a decade | 8.9 | 1.8 | 0.064 | (-0.064, 0] |
| crash of 20, 5 a decade | 8.9 | 3.9 | 0.113 | (-0.113, 0] |
| crash of 40, 0.5 a decade | 17.9 | 0.5 | 0.070 | (-0.070, 0] |
| crash of 40, 1 a decade | 17.9 | 1.0 | 0.125 | (-0.125, 0] |
| crash of 40, 2 a decade | 17.9 | 1.9 | 0.205 | (-0.205, 0] |
| crash of 40, 5 a decade | 17.9 | 4.3 | 0.319 | (-0.319, 0] |
| crash of 100, 0.5 a decade | 44.7 | 0.5 | 0.159 | (-0.159, 0] |
| crash of 100, 1 a decade | 44.7 | 1.0 | 0.233 | (-0.233, 0] |
| crash of 100, 2 a decade | 44.7 | 2.0 | 0.331 | (-0.331, 0] |
| crash of 100, 5 a decade | 44.7 | 4.4 | 0.454 | (-0.454, 0] |

A crash is one day's loss of the stated number of daily standard deviations; the mean outside crashes is set so
that the Sharpe ratio of the whole return, crashes included, is the stated one.

- **Fat tails without a direction do almost nothing.** Student-t with 3 degrees of freedom, and Student-t with 5
  and volatility clustering: the gap is 0.003 to 0.013 of a Sharpe ratio. The signs differ only
  for a strategy whose true Sharpe ratio is within about a hundredth below zero.
- **Jumps are what matter, and only when they are beyond the cap.** A crash of 10 daily standard deviations is
  4.5 weekly ones: inside the cap, nothing is hidden (gap 0.00 to 0.00). A crash of 20 (8.9
  weekly) hides 0.02 to 0.11 of a Sharpe ratio, of 40 (17.9 weekly) 0.07 to 0.32, of
  100 (44.7 weekly) 0.16 to 0.45, rising with how often it happens (0.5 to 5 times a decade).
- **A strategy that loses money can have a positive truncated mean.** With a true Sharpe ratio of −0.25 the
  truncated mean is positive for: crash of 40, 5 a decade, crash of 100, 2 a decade, crash of 100, 5 a decade. For those the tested null is false
  although the strategy has no edge, and the test offers no protection, as §6.3 says. The table gives the size
  of that hole: up to 0.45 of a Sharpe ratio on this grid.

**Samples.** How often a record of 2, 5 and 10 years shows a positive truncated mean while its untruncated mean
is zero or negative (the only way the two can disagree), for true Sharpe ratios of 0 and −0.25:

| process | true Sharpe | truncated mean positive while the untruncated mean is not, after 2 / 5 / 10 years | no week truncated yet, after 2 / 5 / 10 years |
|---|---|---|---|
| normal | -0.25 | 0.000 / 0.000 / 0.000 | 1.000 / 1.000 / 1.000 |
| Student-t, 3 df | -0.25 | 0.005 / 0.007 / 0.011 | 0.930 / 0.840 / 0.711 |
| Student-t, 5 df, GARCH | -0.25 | 0.001 / 0.001 / 0.001 | 0.959 / 0.913 / 0.844 |
| two-sided jumps of 20, 5 a decade | -0.25 | 0.015 / 0.037 / 0.043 | 0.643 / 0.346 / 0.118 |
| normal | +0.00 | 0.000 / 0.000 / 0.000 | 1.000 / 1.000 / 1.000 |
| Student-t, 3 df | +0.00 | 0.006 / 0.011 / 0.019 | 0.929 / 0.833 / 0.711 |
| Student-t, 5 df, GARCH | +0.00 | 0.001 / 0.002 / 0.003 | 0.963 / 0.927 / 0.865 |
| two-sided jumps of 20, 5 a decade | +0.00 | 0.021 / 0.043 / 0.069 | 0.682 / 0.343 / 0.129 |
| crash of 10, 0.5 a decade | -0.25 | 0.000 / 0.001 / 0.001 | 0.993 / 0.977 / 0.956 |
| crash of 10, 0.5 a decade | +0.00 | 0.001 / 0.000 / 0.000 | 0.993 / 0.985 / 0.970 |
| crash of 10, 1 a decade | -0.25 | 0.000 / 0.001 / 0.000 | 0.985 / 0.965 / 0.925 |
| crash of 10, 1 a decade | +0.00 | 0.000 / 0.001 / 0.001 | 0.979 / 0.964 / 0.929 |
| crash of 10, 2 a decade | -0.25 | 0.001 / 0.002 / 0.000 | 0.980 / 0.933 / 0.871 |
| crash of 10, 2 a decade | +0.00 | 0.000 / 0.001 / 0.002 | 0.977 / 0.940 / 0.892 |
| crash of 10, 5 a decade | -0.25 | 0.001 / 0.001 / 0.001 | 0.950 / 0.879 / 0.776 |
| crash of 10, 5 a decade | +0.00 | 0.002 / 0.003 / 0.004 | 0.951 / 0.882 / 0.776 |
| crash of 20, 0.5 a decade | -0.25 | 0.006 / 0.009 / 0.017 | 0.905 / 0.757 / 0.583 |
| crash of 20, 0.5 a decade | +0.00 | 0.012 / 0.020 / 0.019 | 0.904 / 0.779 / 0.617 |
| crash of 20, 1 a decade | -0.25 | 0.018 / 0.016 / 0.032 | 0.811 / 0.606 / 0.370 |
| crash of 20, 1 a decade | +0.00 | 0.017 / 0.034 / 0.037 | 0.817 / 0.612 / 0.370 |
| crash of 20, 2 a decade | -0.25 | 0.028 / 0.038 / 0.054 | 0.651 / 0.346 / 0.136 |
| crash of 20, 2 a decade | +0.00 | 0.035 / 0.057 / 0.078 | 0.665 / 0.361 / 0.142 |
| crash of 20, 5 a decade | -0.25 | 0.053 / 0.081 / 0.113 | 0.390 / 0.075 / 0.004 |
| crash of 20, 5 a decade | +0.00 | 0.073 / 0.116 / 0.172 | 0.383 / 0.084 / 0.005 |
| crash of 40, 0.5 a decade | -0.25 | 0.016 / 0.035 / 0.045 | 0.886 / 0.758 / 0.597 |
| crash of 40, 0.5 a decade | +0.00 | 0.018 / 0.048 / 0.077 | 0.900 / 0.789 / 0.619 |
| crash of 40, 1 a decade | -0.25 | 0.035 / 0.069 / 0.101 | 0.818 / 0.613 / 0.382 |
| crash of 40, 1 a decade | +0.00 | 0.051 / 0.109 / 0.172 | 0.826 / 0.590 / 0.370 |
| crash of 40, 2 a decade | -0.25 | 0.059 / 0.150 / 0.223 | 0.668 / 0.348 / 0.132 |
| crash of 40, 2 a decade | +0.00 | 0.116 / 0.216 / 0.298 | 0.657 / 0.347 / 0.129 |
| crash of 40, 5 a decade | -0.25 | 0.197 / 0.311 / 0.447 | 0.344 / 0.062 / 0.005 |
| crash of 40, 5 a decade | +0.00 | 0.237 / 0.367 / 0.425 | 0.356 / 0.078 / 0.006 |
| crash of 100, 0.5 a decade | -0.25 | 0.016 / 0.049 / 0.089 | 0.887 / 0.763 / 0.601 |
| crash of 100, 0.5 a decade | +0.00 | 0.033 / 0.128 / 0.252 | 0.904 / 0.778 / 0.605 |
| crash of 100, 1 a decade | -0.25 | 0.042 / 0.135 / 0.237 | 0.806 / 0.584 / 0.352 |
| crash of 100, 1 a decade | +0.00 | 0.073 / 0.295 / 0.419 | 0.820 / 0.594 / 0.370 |
| crash of 100, 2 a decade | -0.25 | 0.105 / 0.350 / 0.530 | 0.667 / 0.368 / 0.143 |
| crash of 100, 2 a decade | +0.00 | 0.183 / 0.478 / 0.496 | 0.665 / 0.357 / 0.126 |
| crash of 100, 5 a decade | -0.25 | 0.382 / 0.570 / 0.715 | 0.371 / 0.075 / 0.007 |
| crash of 100, 5 a decade | +0.00 | 0.446 / 0.496 / 0.534 | 0.369 / 0.070 / 0.009 |

- For fat tails without a direction the disagreement is at most a few records in a hundred.
- For crash processes it reaches 0.71 on this grid. It grows with the length of the record, because a
  record must contain a crash before the two means can differ: the last column is the share of records in which
  no week has been truncated yet, where the truncated and untruncated records are the same record and both look
  fine. That case, the disaster that has not happened, is the one no test on returns can see.

## 3. A tail-risk check before any profitability claim (proposed, not adopted)

**The rule proposed.** Before a family is described as profitable, as having a positive mean return, or is made
Live-experiment eligible (§8.3), its leading component's forward record of `n` weeks must satisfy

```
Σ Y_t  −  U( N_trunc ) · ( L − 6 )  >  0          and          Σ Z_t  >  0
```

- `Σ Y_t`: the truncated record's total gain, in ex-ante weekly standard deviations (it is what the e-process
  bets on).
- `N_trunc`: the number of weeks truncated so far (already recorded, §6.3).
- `U(N)`: the one-sided 95% upper confidence bound for the mean of a Poisson count after `N` events: 3.00 after
  none (the rule of three), 4.74 after one, 6.30 after two.
- `L`: the stress loss of one week, in ex-ante weekly standard deviations: the largest of the loss the family
  spec declares under "tail exposure", the worst week on the family's whole record, and a floor of 12 (twice the
  cap).

**In plain English.** The record has gone `n` weeks with `N` weeks beyond the cap. That is compatible, at 95%,
with as many as `U(N)` such weeks in a stretch of this length. Charge the record for that many, each at the
declared stress loss less the six already counted. If what the capped record earned does not cover the charge,
the profit could be the premium for a crash that has merely not arrived, and no claim of profit is made. With no
truncated week and the floor, the capped record must have earned 18 weekly standard deviations in total.

**Why this form.** The gap of section 2 is `(crashes per week) × (loss beyond the cap)`. Returns cannot bound
either factor from a record without crashes (Protocol §6.2: Bahadur and Savage). The check takes the frequency
from the record itself, at the upper end of what the record allows, and the size from outside the record: the
spec's declared tail exposure, which the protocol already requires and the critic already reviews. Protocol
§6.3 rejected a tail charge **inside** the e-process, because with only a variance bound the charge kills every
edge. Here it is a separate, later gate with a declared size, and the test's exactness is untouched.

**What it costs an honest strategy** (share of records that pass, after 2 / 5 / 10 years):
Sharpe 0.5: normal 0.15 / 0.51 / 0.78, Student-t 3 0.17 / 0.51 / 0.74;
Sharpe 1.0: normal 0.39 / 0.88 / 0.99, Student-t 3 0.41 / 0.86 / 0.98. A formal rejection
takes far longer than that (§6.9: 15 years at a Sharpe ratio of 1), so for the top tier the check would rarely
be the binding condition; for claims built on the posterior tiers after two to five years it would.

**What it stops** (all processes; the bold column is the proposal):

| process | true Sharpe | declared stress loss (weekly standard deviations) | truncated record positive, 2 / 5 / 10 years | **check passed with the stress loss declared**, 2 / 5 / 10 years | check passed with only the floor of 12 declared |
|---|---|---|---|---|---|
| normal | -0.25 | 12.0 | 0.342 / 0.272 / 0.208 | **0.015 / 0.038 / 0.052** | 0.015 / 0.038 / 0.052 |
| Student-t, 3 df | -0.25 | 12.0 | 0.373 / 0.290 / 0.232 | **0.026 / 0.059 / 0.064** | 0.026 / 0.059 / 0.064 |
| Student-t, 5 df, GARCH | -0.25 | 12.0 | 0.343 / 0.262 / 0.197 | **0.018 / 0.049 / 0.048** | 0.018 / 0.049 / 0.048 |
| two-sided jumps of 20, 5 a decade | -0.25 | 12.0 | 0.396 / 0.340 / 0.276 | **0.030 / 0.065 / 0.048** | 0.030 / 0.065 / 0.048 |
| normal | +0.00 | 12.0 | 0.501 / 0.492 / 0.493 | **0.038 / 0.124 / 0.212** | 0.038 / 0.124 / 0.212 |
| Student-t, 3 df | +0.00 | 12.0 | 0.511 / 0.492 / 0.517 | **0.043 / 0.144 / 0.212** | 0.043 / 0.144 / 0.212 |
| Student-t, 5 df, GARCH | +0.00 | 12.0 | 0.483 / 0.492 / 0.495 | **0.037 / 0.146 / 0.217** | 0.037 / 0.146 / 0.217 |
| two-sided jumps of 20, 5 a decade | +0.00 | 12.0 | 0.530 / 0.539 / 0.552 | **0.072 / 0.138 / 0.159** | 0.072 / 0.138 / 0.159 |
| normal | +0.50 | 12.0 | 0.755 / 0.876 / 0.942 | **0.153 / 0.509 / 0.776** | 0.153 / 0.509 / 0.776 |
| Student-t, 3 df | +0.50 | 12.0 | 0.761 / 0.876 / 0.945 | **0.169 / 0.506 / 0.740** | 0.169 / 0.506 / 0.740 |
| Student-t, 5 df, GARCH | +0.50 | 12.0 | 0.800 / 0.908 / 0.967 | **0.178 / 0.589 / 0.833** | 0.178 / 0.589 / 0.833 |
| two-sided jumps of 20, 5 a decade | +0.50 | 12.0 | 0.782 / 0.904 / 0.972 | **0.212 / 0.415 / 0.609** | 0.212 / 0.415 / 0.609 |
| normal | +1.00 | 12.0 | 0.918 / 0.989 / 1.000 | **0.389 / 0.879 / 0.990** | 0.389 / 0.879 / 0.990 |
| Student-t, 3 df | +1.00 | 12.0 | 0.933 / 0.987 / 0.999 | **0.415 / 0.865 / 0.977** | 0.415 / 0.865 / 0.977 |
| Student-t, 5 df, GARCH | +1.00 | 12.0 | 0.947 / 0.995 / 1.000 | **0.509 / 0.920 / 0.994** | 0.509 / 0.920 / 0.994 |
| two-sided jumps of 20, 5 a decade | +1.00 | 12.0 | 0.943 / 0.993 / 1.000 | **0.411 / 0.769 / 0.928** | 0.411 / 0.769 / 0.928 |
| crash of 10, 0.5 a decade | -0.25 | 12.0 | 0.358 / 0.290 / 0.211 | **0.015 / 0.052 / 0.052** | 0.015 / 0.052 / 0.052 |
| crash of 10, 0.5 a decade | +0.00 | 12.0 | 0.505 / 0.515 / 0.497 | **0.041 / 0.132 / 0.212** | 0.041 / 0.132 / 0.212 |
| crash of 10, 1 a decade | -0.25 | 12.0 | 0.344 / 0.276 / 0.216 | **0.021 / 0.043 / 0.053** | 0.021 / 0.043 / 0.053 |
| crash of 10, 1 a decade | +0.00 | 12.0 | 0.481 / 0.475 / 0.499 | **0.044 / 0.124 / 0.199** | 0.044 / 0.124 / 0.199 |
| crash of 10, 2 a decade | -0.25 | 12.0 | 0.361 / 0.280 / 0.220 | **0.025 / 0.044 / 0.051** | 0.025 / 0.044 / 0.051 |
| crash of 10, 2 a decade | +0.00 | 12.0 | 0.507 / 0.499 / 0.510 | **0.045 / 0.132 / 0.214** | 0.045 / 0.132 / 0.214 |
| crash of 10, 5 a decade | -0.25 | 12.0 | 0.377 / 0.285 / 0.227 | **0.019 / 0.047 / 0.053** | 0.019 / 0.047 / 0.053 |
| crash of 10, 5 a decade | +0.00 | 12.0 | 0.489 / 0.503 / 0.504 | **0.050 / 0.129 / 0.200** | 0.050 / 0.129 / 0.200 |
| crash of 20, 0.5 a decade | -0.25 | 12.0 | 0.357 / 0.301 / 0.229 | **0.019 / 0.053 / 0.056** | 0.019 / 0.053 / 0.056 |
| crash of 20, 0.5 a decade | +0.00 | 12.0 | 0.508 / 0.516 / 0.526 | **0.045 / 0.123 / 0.196** | 0.045 / 0.123 / 0.196 |
| crash of 20, 1 a decade | -0.25 | 12.0 | 0.371 / 0.294 / 0.230 | **0.016 / 0.046 / 0.043** | 0.016 / 0.046 / 0.043 |
| crash of 20, 1 a decade | +0.00 | 12.0 | 0.519 / 0.534 / 0.549 | **0.045 / 0.137 / 0.174** | 0.045 / 0.137 / 0.174 |
| crash of 20, 2 a decade | -0.25 | 12.0 | 0.376 / 0.317 / 0.268 | **0.025 / 0.043 / 0.044** | 0.025 / 0.043 / 0.044 |
| crash of 20, 2 a decade | +0.00 | 12.0 | 0.514 / 0.552 / 0.584 | **0.047 / 0.123 / 0.139** | 0.047 / 0.123 / 0.139 |
| crash of 20, 5 a decade | -0.25 | 12.0 | 0.418 / 0.357 / 0.304 | **0.031 / 0.035 / 0.021** | 0.031 / 0.035 / 0.021 |
| crash of 20, 5 a decade | +0.00 | 12.0 | 0.556 / 0.604 / 0.667 | **0.065 / 0.087 / 0.093** | 0.065 / 0.087 / 0.093 |
| crash of 40, 0.5 a decade | -0.25 | 17.9 | 0.371 / 0.305 / 0.253 | **0.000 / 0.002 / 0.013** | 0.019 / 0.057 / 0.053 |
| crash of 40, 0.5 a decade | +0.00 | 17.9 | 0.536 / 0.565 / 0.584 | **0.000 / 0.025 / 0.074** | 0.064 / 0.170 / 0.220 |
| crash of 40, 1 a decade | -0.25 | 17.9 | 0.412 / 0.372 / 0.319 | **0.000 / 0.008 / 0.013** | 0.021 / 0.069 / 0.059 |
| crash of 40, 1 a decade | +0.00 | 17.9 | 0.571 / 0.611 / 0.681 | **0.002 / 0.030 / 0.085** | 0.060 / 0.169 / 0.184 |
| crash of 40, 2 a decade | -0.25 | 17.9 | 0.458 / 0.432 / 0.441 | **0.000 / 0.006 / 0.014** | 0.034 / 0.068 / 0.048 |
| crash of 40, 2 a decade | +0.00 | 17.9 | 0.644 / 0.723 / 0.804 | **0.001 / 0.056 / 0.087** | 0.105 / 0.175 / 0.134 |
| crash of 40, 5 a decade | -0.25 | 17.9 | 0.536 / 0.563 / 0.635 | **0.002 / 0.019 / 0.010** | 0.057 / 0.043 / 0.012 |
| crash of 40, 5 a decade | +0.00 | 17.9 | 0.722 / 0.843 / 0.922 | **0.013 / 0.066 / 0.064** | 0.162 / 0.100 / 0.072 |
| crash of 100, 0.5 a decade | -0.25 | 44.7 | 0.403 / 0.340 / 0.308 | **0.000 / 0.000 / 0.000** | 0.020 / 0.056 / 0.068 |
| crash of 100, 0.5 a decade | +0.00 | 44.7 | 0.633 / 0.714 / 0.786 | **0.000 / 0.000 / 0.000** | 0.077 / 0.244 / 0.340 |
| crash of 100, 1 a decade | -0.25 | 44.7 | 0.495 / 0.472 / 0.477 | **0.000 / 0.000 / 0.000** | 0.036 / 0.105 / 0.110 |
| crash of 100, 1 a decade | +0.00 | 44.7 | 0.737 / 0.848 / 0.933 | **0.000 / 0.000 / 0.001** | 0.145 / 0.354 / 0.318 |
| crash of 100, 2 a decade | -0.25 | 44.7 | 0.603 / 0.691 / 0.754 | **0.000 / 0.000 / 0.000** | 0.076 / 0.184 / 0.118 |
| crash of 100, 2 a decade | +0.00 | 44.7 | 0.828 / 0.947 / 0.985 | **0.000 / 0.000 / 0.011** | 0.293 / 0.342 / 0.129 |
| crash of 100, 5 a decade | -0.25 | 44.7 | 0.767 / 0.867 / 0.940 | **0.000 / 0.000 / 0.005** | 0.264 / 0.085 / 0.011 |
| crash of 100, 5 a decade | +0.00 | 44.7 | 0.853 / 0.959 / 0.990 | **0.000 / 0.021 / 0.025** | 0.340 / 0.084 / 0.033 |

- With the stress loss declared at its true size, a zero-mean strategy with crashes of 40 passes in at most
  0.09 of records and
  with crashes of 100 in at most 0.02,
  while its truncated record is positive in up to 0.99 of them.
- With only the floor declared the same strategies pass in up to
  0.35: **an undeclared
  tail defeats the check**, as it defeats everything else. The declaration is the control; the check makes it
  bind.
- It is not a test of the mean and must not be read as one: a strategy with no edge and no crash passes it in
  about a fifth of ten-year records. It is a condition **added to** a rejection or a tier, never a substitute.
- For crashes inside twice the cap (10 and 20 daily standard deviations) the floor is the stress loss and the
  check adds little; there the hidden part is at most 0.11 of a Sharpe ratio.

**What Ethan would decide** if he wants it: the level (95%), the floor (12), which claims it gates, and whether
a family that declares no tail exposure may make a profitability claim at all. Adopting it is a new protocol
version with its own simulation criterion; nothing in the repository applies it.

## 4. Does skipping weeks by a predictable rule preserve validity?

**Yes. Confirmed, with one condition and one consequence.**

**The argument.** Write the wealth of one fixed fraction as `W_t = W_(t−1) · ( 1 + λ · b_t · Y_t )`, with `b_t`
equal to 0 or 1. If `b_t` is a function of what was recorded before week `t`, then under the null

```
E[ W_t | past ]  =  W_(t−1) · ( 1 + λ · b_t · E[ Y_t | past ] )  ≤  W_(t−1),
```

because `λ b_t ≥ 0` is known and `E[Y_t | past] ≤ 0`. Each factor is at least `1 − 0.15 × 6 = 0.1`, so `W` is a
non-negative supermartingale and Ville's inequality holds: the probability of ever reaching `1/a` is at most
`a`. Skipping is betting the fraction zero, and a bet may be any non-negative number chosen from the past. The
mean over six fractions and over components keeps the property. Nothing about the rule matters except that it
looks only backwards: not its threshold, not whether it is a good rule.

**The condition.** `b_t` must be computable from the record as it stood before week `t`. In the code it is
(`eprocess.weekly_variance_ratio` reads the 252 days before the week's first day; a test alters the week and
everything after it and checks that the decision does not move). One sentence of the protocol leaves a gap for
production: §6.6 enters a week 7 days after it ends "using the values stored then", and §6.7 computes the
variance ratio from "the previous 252 trading days". If the final settlements of the last days before a week
arrive after that week has begun, a variance ratio computed from them is not a function of the past as §6.1
defines it. With complete, unrevised data, as in every simulation here, the two coincide. **Recommended wording
for a later version** (not made here; §6 is unchanged): "the variance ratio for week `t` uses the values on
record at the decision cut-off of week `t`".

**The numbers.** Series with conditional mean exactly zero, wealth watched every week for ten years
(4,000 paths each):

| series | rule | share of weeks with a bet | wealth ever reaches 20 (bound 0.05 under the null) | ever reaches 100 (bound 0.01) | mean of Y in the weeks bet on | mean of Y in all weeks |
|---|---|---|---|---|---|---|
| normal | always bet | 1.000 | 0.0103 | 0.0015 | -0.0001 | -0.0001 |
| normal | variance-ratio rule (past only) | 0.968 | 0.0103 | 0.0013 | -0.0002 | -0.0001 |
| normal | weeks dropped after the fact (Z < -2) | 0.977 | 0.1155 | 0.0280 | +0.0572 | -0.0001 |
| Student-t, 3 df | always bet | 1.000 | 0.0100 | 0.0008 | +0.0026 | +0.0026 |
| Student-t, 3 df | variance-ratio rule (past only) | 0.973 | 0.0097 | 0.0005 | +0.0023 | +0.0026 |
| Student-t, 3 df | weeks dropped after the fact (Z < -2) | 0.973 | 0.2268 | 0.0757 | +0.0809 | +0.0026 |
| Student-t, 5 df, GARCH | always bet | 1.000 | 0.0075 | 0.0008 | +0.0011 | +0.0011 |
| Student-t, 5 df, GARCH | variance-ratio rule (past only) | 0.938 | 0.0075 | 0.0013 | +0.0009 | +0.0011 |
| Student-t, 5 df, GARCH | weeks dropped after the fact (Z < -2) | 0.972 | 0.2432 | 0.0895 | +0.0796 | +0.0011 |
| zero mean overall; gains in quiet spells, losses in trending spells | always bet | 1.000 | 0.1260 | 0.0545 | +0.0008 | +0.0008 |
| zero mean overall; gains in quiet spells, losses in trending spells | variance-ratio rule (past only) | 0.539 | 0.1690 | 0.0675 | +0.0932 | +0.0008 |

- With the protocol's rule the wealth reaches 20 in 0.007 to 0.010 of null paths, the same
  as with no skipping, and well inside the bound of 0.05.
- The third rule of each series is not the protocol's: it drops a week **after seeing it** (a loss beyond two
  standard deviations is treated as a data problem). The wealth then reaches 20 in 0.12 to
  0.24 of null paths. What protects the test is that the rule cannot see the week, which is why
  §6.6's rule that no observation is ever dropped matters as much as the skipping rule.

**The consequence: skipping changes what is tested.** The last two rows are a strategy whose mean over all
weeks is zero: it gains in quiet spells and gives it back in trending spells, and the variance-ratio rule skips
most of the trending weeks. The mean of `Y` in the weeks bet on is +0.093 a week
against +0.001 in all weeks, and the wealth reaches 20 in
0.17 of paths (0.13 with no skipping, because the conditional mean
is positive in the quiet spells either way). Those rejections are **valid**: the null says the conditional mean
is never positive, and here it sometimes is. They are not evidence that holding the strategy every week makes
money. A claim about the strategy as held needs the record of all weeks, which is what the guard and the check
of section 3 look at.
