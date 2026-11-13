# Manhattan Protocol v3.1: rules of evidence

Version **3.1.0**, 2026-11-12, written by session "5M Manhattan C" for Ethan to adopt, and revised before
adoption by sessions "6M Manhattan C" (2026-11-12) and "10M Manhattan C" (2026-11-13, on Ethan's decisions): the
pre-adoption changes are marked as such below. It is the whole protocol:
[PROTOCOL_v3.md](PROTOCOL_v3.md) (3.0.0) with the changes listed below. Version 3.0.0 stays in the repository,
unchanged and protected. Structure and data roles are in [ARCHITECTURE.md](ARCHITECTURE.md); the state of the work
is in [MANHATTAN_PROGRESS.md](MANHATTAN_PROGRESS.md).

**Status: a draft, not adopted and not in force.** It becomes the protocol under test when Ethan adopts it
([ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 19). No rule below produces a claim until the simulation of
[SIM_PREREG.md](SIM_PREREG.md), as revised for the changed parts by [SIM_PREREG_v2.md](SIM_PREREG_v2.md), has passed
(`claims.enabled: false` in `config/manhattan.yaml`). Where this document says "fixed in v3.0" for a number, the
number is an assumed parameter: it was fixed before any simulation or market result, and the simulation checks
whether the rules work with it. No such number is changed in 3.1.

**How to read it.** Each rule is given three ways: the formula, a plain-English reading, and a box with the problem
it solves, what it assumes and how it fails. Every symbol is in section 1.

## What changed from 3.0.0, and why

Changes 1 to 4 come from the **pilot on development scenarios** (`results/manhattan_sim/PILOT_REPORT.md`,
2026-11-12: 12 replications a run, deciding nothing). Change 5 comes from the **pilot rerun of this draft**
(`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`), the first run in which the dormancy rule could be measured
at all. It is a **pre-adoption change**: it was made to the draft before Ethan adopted it, so no adopted text
was changed. It was made twice: session 6M added one second condition to the rule (the model's `Π_f^max`), a
second session measured another beside it on the same fits (the family's own forward record), and on 2026-11-13
Ethan chose the second (ETHAN_ACTIONS item 22). Row 5 describes the rule as it now stands and says what it
replaced. SIM_PREREG.md gives development scenarios
exactly this use: they "may be run as often as needed while the code is written and the methods are revised"
(its section 3). The held-out scenarios, which run only in a confirmation run from a tagged commit (its section
8.1), judge the final methods.

| # | section | what changed | the pilot result that motivated it | why it is not tuning to held-out results |
|---|---|---|---|---|
| 1 | §5.1, §5.2, §5.4 (and a note in §2.2) | **The SPA test re-estimates the core hedge in every resample.** The index sequence is applied to the unhedged returns and the core factors together, the hedge is recomputed on each resampled series by the live rule (same window, same minimum history, same ridge penalty, past data only), and resampled means are centred at the window's least-squares intercept on the core factors, which is the truth in the world the resamples are drawn from. The statistic, the recentring rule, the block length, the number of resamples and the p-value are unchanged. Where a return needs no hedge the test is exactly that of 3.0.0 | **D11** (the only scenario with an estimated hedge): 0.077 (0.061 to 0.094) of families with no edge rejected at the 0.05 level, against a bound of 0.06; 0.269 (0.234 to 0.303) at 0.20; Romano-Wolf family-wise rate 0.077 (0.061 to 0.093). In every scenario where returns are hedged by construction the size was near nominal | D11 is a development scenario (SIM_PREREG §3.1). No held-out scenario has been coded or run: the run log records none, and the runner refuses them. The change was specified from the mechanism the pilot report named (a shrunken, lagging hedge leaks a core factor's mean), not from a search over variants on held-out data. It is judged by held-out scenarios it has never seen: H12, added by SIM_PREREG_v2 because version 1 has no held-out scenario with an estimated hedge, and H01, H02a, H03, H04, where the test is that of 3.0.0 |
| 2 | §7, §9.1, Appendix B | **An analytic normal-normal hierarchical model replaces the sampled one.** Closed-form posteriors on a fixed grid of hyperparameters; the same single retention parameter; selection still handled once; wide normal components for prior-data conflict; family portfolios only (no hypothesis level); one common forward shock in place of the full sampling covariance; a grid check replaces the sampler's convergence gate. The sampled model of 3.0.0 stays as an optional robustness check that decides nothing (§7.4) | The model-fitting half of the pilot produced **no result**: one replication of D10, with the sampler at a fifth of its budget, was stopped unfinished after 2 hours 31 minutes of CPU time; at the pre-registered count that is of the order of 50,000 CPU-hours. Sampled as written, the model also did not mix (`R̂` about 3.5) and had to be re-expressed | No calibration result exists for any scenario, development or held-out, under either model: there was nothing to tune to. The priors and constants that survive are those fixed in 3.0 (`w`, `s_R`, 0.02, `θ_min`, every prior centre and scale). The model is judged by the held-out scenarios run at HB size (H03, H05, H06, H07, H09, H10, H11), none of which has been coded |
| 3 | §5.3, §7.3 | **The rule that adaptive-channel families carry zero evidential weight on the reserve now cites its evidence and is enforced in code.** The rule itself is that of 3.0.0 | **D09b**: with three adaptive rounds proposed after looking at the reserve window, the SPA test recomputed on the full set rejects 0.344 (0.307 to 0.380) of families with no edge at the 0.05 level | The rule was written in 3.0.0 before any simulation; the pilot agrees with it. Nothing was changed to fit a result |
| 4 | §5.1, Appendix C | **Two wording fixes** (ETHAN_ACTIONS item 14) and the stale sentence in Appendix C: what is Hansen's and what is the protocol's own in the p-value; what `g(x) = x` is. **Wording only; no rule changed** | none: found when the formulas were checked against the papers (MANHATTAN_PROGRESS, "Phase C entry criteria") | not a change of method |
| 5 | §9.1, Appendix B (and one sentence of §7.2(e)) | **Pre-adoption change (Ethan's decision of 2026-11-13). A family becomes dormant only if its own forward record also speaks against it.** Beside the forecast `PP_f^max < 0.05` of 3.0, a one-sided test of the family's **own forward record** against an edge of `θ_min = 0.25` must reject at the same two consecutive reviews: `p^F_f = Φ((y^F_f − θ_min)/s^F_f) < 0.05`, defined once the family has 252 forward days. A dormant family is reactivated when either number is at or above 0.15. The thresholds are those of 3.0 (0.05 twice, 0.15), the edge tested against is the `θ_min` the protocol already had, and the forecast is computed as before. **What it replaces:** in 3.0.0 the forecast alone decided; between 2026-11-12 and this decision the draft held `Π_f^max < 0.05` (the most hopeful of the six models' probabilities of an edge) as the second condition (session 6M) | **The pilot rerun of this draft**, 12 replications a scenario: under 3.0's rule the families with a true edge of at least `θ_min` that ended dormant were 0.167 (0.045 to 0.261) in **D02**, 0.179 (0.138 to 0.216) in **D05**, 0.108 (0.081 to 0.138) in **D08** and 0.146 (0.092 to 0.197) in **D10**, against a bound of 0.10 on the upper end (V7). Of the 152 families with an edge that it retired, the forecast was exactly 0.00 for 139, and it stays 0.00 when the family's **true** edge replaces the posterior draws; their own forward records were not against them (the p-value above had a median of 0.52 to 0.75 and was below 0.05 for 2 of the 152); none would have reached the tier by year 10 (`results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md`). **The two second conditions, measured side by side on the same fits** (`results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`, section 3; D02 / D05 / D08 / D10): with `Π^max` the rule retired 0 of 42, 2 of 140, 2 of 944 and 1 of 123 families with an edge at the simulation's four review dates, and 2, 10, 5 and 7 with a review every year, where two of the four upper ends were above 0.10; with the family's own forward record it retired none at four dates and 0, 0, 0 and 2 with yearly reviews | D02, D05, D08 and D10 are development scenarios (SIM_PREREG §3.1); no held-out scenario has been coded or run. The metric (M8), its bound of 0.10 (0.25 for late starters in H09), the scenarios and every threshold of SIM_PREREG and SIM_PREREG_v2 are unchanged, and no threshold of the rule moved. The second condition was not found by a search over levels: it is the one statistic whose error is controlled **for a family that has an edge**, whatever the other families are, which is what the criterion measures; its level is the 0.05 the rule already had and the edge it tests against is the `θ_min` the protocol already had. It is judged by the held-out scenarios run at HB size, above all H09 (dormancy then reactivation), none of which has been coded |

What 3.1.0 does **not** change: the screening candidates (§4), the forward e-process and e-LOND (§6), the tiers (§8),
the dormancy levels 0.05 and 0.15 and the forecast they were written for (§9.1: change 5 adds a second quantity
they apply to), the cost and reactivation rules (§9.2, §9.3), every level and every constant of Appendix B that
3.0 fixed. The pilot gave no reason to touch them, and none of its other observations (candidate (ii)'s low
power, slow formal support, the variance-ratio rule's cost under serial correlation, how seldom "Statistically
supported" is reached) is a failure of a rule.

The pilot rerun that tests changes 1 and 2 on the development scenarios is reported in
`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`; it is also the evidence for change 5. The rerun of the HB
scenarios in `results/manhattan_sim/v2/PILOT_RERUN2_REPORT.md` was made under the second condition the draft
held first (`Π_f^max`), not under the rule as it now stands. All are pilots and decide nothing.

---

## 1. Symbols

| symbol | meaning |
|---|---|
| `t` | a period. Returns are recorded per trading day by default; an event strategy is on the daily grid with return 0 when it holds nothing. In sections 4.5 and 6 `t` is a **test period**: one calendar week of trading days (section 6.1) |
| `f`, `h`, `v`, `x` | a family, a hypothesis, a variant, an executable (ARCHITECTURE §3) |
| `b`, `n_b` | a batch (numbered 1, 2, ... in freeze order); the number of blind-channel families in batch `b` |
| `H_f`, `m_h` | number of hypotheses in family `f`; number of variants in the frozen grid of hypothesis `h` |
| `x*(v)` | the primary executable of variant `v`, declared at freeze |
| `𝓕_t` | the information available when period `t` has ended (section 6.1) |
| `r_{x,t}` | net return of executable `x` in period `t`: gross return minus trading and financing costs, as a fraction of its notional capital, in excess of cash |
| `C_t` | the vector of core factor returns in period `t` for the executable's asset class: carry, trend, value and buy-and-hold |
| `β_{x,t-1}` | hedge ratios of `x` on `C`, estimated only from periods before `t` (section 2.2) |
| `X_{x,t}` | core-hedged net return: `r_{x,t} − β'_{x,t-1} C_t − hedge cost` |
| `P_{h,t}` | return of hypothesis `h`'s portfolio: the equal-weight mean of `X_{x*(v),t}` over its frozen variants |
| `P_{f,t}` | return of family `f`'s portfolio: the equal-weight mean of `P_{h,t}` over its hypotheses |
| `s_t` | ex-ante scale of a portfolio return: a volatility forecast made from data before `t`, with a floor (section 2.4) |
| `Z_t`, `Y_t` | standardised return `P_t / s_t`; truncated standardised return `max(Z_t, −c)` |
| `c` | truncation point in ex-ante standard deviations of a test period (6 weekly, 4 monthly) |
| `λ` | a betting fraction; `Λ` the fixed grid of betting fractions |
| `W_t` | wealth of a betting process at `t`, starting at 1 |
| `E_f` | an e-value for family `f`: a non-negative statistic whose expectation is at most 1 if the family's null is true |
| `p_f` | a p-value for family `f` |
| `α_S`, `α_F` | the screening false discovery rate level (0.20) and the forward level (0.05) |
| `γ_j` | a fixed sequence of non-negative numbers summing to 1 that splits a level across batches or families (section 4.2) |
| `R` | a running count of rejections (discoveries), defined where used |
| `FDR` | false discovery rate: the expected share of discoveries that are false, taken as 0 when there are none |
| `FWER` | family-wise error rate: the probability of at least one false rejection in a set of tests |
| `n`, `B`, `L` | number of periods in a window; number of bootstrap resamples; mean block length of the bootstrap |
| `α̂_k` | the intercept of the least-squares regression of variant `k`'s unhedged return on the core factors over a window (section 5.1) |
| `a_f` | apparent historical edge of a family's portfolio, in annualised Sharpe-ratio units (section 7) |
| `ρ_m` | retention of mechanism class `m`: the share of the apparent historical edge that persists forward (section 7) |
| `θ_f` | true forward edge of a family's portfolio, in annualised Sharpe-ratio units |
| `y^H_f`, `y^F_f`, `s^H_f`, `s^F_f` | sample Sharpe ratio of `P_f` on the reserve window and on the forward record, and their standard errors (section 7) |
| `θ_min` | the smallest edge that matters (0.25) |
| `Π_f` | posterior probability that `θ_f ≥ θ_min` |
| `T_end` | the programme's end date |

"Edge" always means the annualised Sharpe ratio of a core-hedged net return. "Null" means "no edge" in the precise
sense given in each section.

---

## 2. Returns

### 2.1 Net return

`r_{x,t}` is computed from positions fixed with information `𝓕_{t-1}` and executed at the next available price, less
the executable's cost model (spread, commission, roll, financing). Futures returns are excess returns already; cash
instruments are financed at the local short rate.

### 2.2 Core hedge

```
β_{x,t-1} = argmin over β of   Σ_{u = t−L_β}^{t−1} ( r_{x,u} − a − β' C_u )²  +  κ ‖β‖²
X_{x,t}   = r_{x,t} − β'_{x,t-1} C_t − Σ_k |β_{k,t-1} − β_{k,t-2}| · cost_k
```

`L_β = 756` periods (three years of days), at least 252; `κ = 0.1 · trace(C'C) / K`, with `K` the number of core
factors; `a` is an intercept; `cost_k` is the one-way cost of trading core factor `k`. An executable needs 252
periods of exploration-role returns before its first reserve or forward period; otherwise its first 252 periods
are a burn-in with no evidential weight.

> **In plain English.** Before each day we estimate, from the past only, how much of the strategy is just carry,
> trend, value or holding the market. We subtract that part, and the cost of holding the hedge. What is left is what
> the strategy adds.
>
> **Problem it solves.** A new strategy that is 80% carry would look good because carry was good. Evidence must be
> about what is new.
>
> **Assumes.** The core factors are defined, daily, tradable and frozen before the first batch (not yet built: AUDIT
> §1.2). Betas move slowly compared with three years.
>
> **How it fails.** (1) If the true exposure moves quickly (an options-like strategy), the estimated hedge lags and
> factor returns leak into `X`. The forward test stays valid, because `X` is still the return of a tradable
> portfolio fixed in advance, but a rejection then means "this hedged portfolio made money", not "this is a new
> mechanism". (2) Omitted factors (for example liquidity) are not removed. (3) With few observations the ridge
> estimate is close to zero and the strategy is barely hedged. (4) **Even a constant exposure leaks a little.**
> With `κ = 0.1 · trace(C'C)/K` the ridge shrinks every hedge ratio by about 9%, so a strategy with exposure `β`
> to a core factor whose mean is `μ` keeps about `0.09 · β · μ` of it in `X`. A test on the reserve that treats
> `X` as given data then rejects too often (pilot scenario D11); section 5.1 re-estimates the hedge inside the
> test for that reason. The forward test's validity is unaffected, for the reason given in (1).

### 2.3 Portfolios

```
P_{h,t} = (1 / m_h) Σ_{v in the frozen grid of h} X_{x*(v),t}
P_{f,t} = (1 / H_f) Σ_{h in f} P_{h,t}
```

Every primary executable is sized to the volatility target its hypothesis declared at freeze, so the means are of
comparable series. Variants added later by the adaptive channel are **not** in `P_h`.

> **In plain English.** A hypothesis is judged on the average of all its declared settings, not on its best one.
>
> **Problem it solves.** Picking the best of twenty settings and reporting it is the most common way to fool
> oneself. Averaging over the whole declared grid leaves nothing to pick.
>
> **Assumes.** The grid was declared before freezing and is not padded with settings known to be bad.
>
> **How it fails.** If only one setting works, its edge is diluted by the others and the hypothesis may never be
> found. That loss of power is accepted; the single best variant can still be claimed through section 5.4.

### 2.4 Scale

```
s_t = max( EWMA standard deviation of P over periods up to t−1, half-life 60 periods ,  s_floor )
Z_t = P_t / s_t
```

`s_floor` is half of the declared per-period target volatility. `s_t` depends only on `𝓕_{t-1}`.

> **In plain English.** Each day's return is measured in units of how volatile we expected that day to be.
>
> **Problem it solves.** Volatility clusters. A fixed-size bet on raw returns would bet most heavily, in risk terms,
> exactly when markets are wildest.
>
> **Assumes.** Nothing for validity: dividing by a positive number known in advance does not change the sign of a
> conditional mean.
>
> **How it fails.** A bad forecast costs power, and moves the truncation point of section 6.3 in return terms.

---

## 3. Map of claims

| claim | data | method | level | what the level means |
|---|---|---|---|---|
| "family `f` passes screening" | reserve, blind channel, one designated evaluation | section 4 (one of two candidates, chosen by simulation) | FDR 20% | a **filter** on history the model may know; not a guarantee about the future |
| "variant `v` of a screened family has positive mean on the reserve" | reserve | Hansen SPA with the hedge re-estimated in every resample, Romano-Wolf, linked by Benjamini-Bogomolov (section 5) | the family's own admission level | error control within the family, conditional on the same caveat |
| "family `f` is formally supported by forward-only evidence" | forward only | betting e-process, combined by e-LOND (section 6) | FDR 5% | holds at every time, under any dependence between families, for the null stated in section 6.3 |
| "the probability that `f` has an edge of at least `θ_min` is `Π_f`" | reserve and forward | one analytic hierarchical Bayesian model (section 7) | none | a posterior probability under a stated model; **never an error rate** |
| tier labels | all of the above | section 8 | none | operating labels with entry and exit rules |

A raw e-value, a raw p-value, a Sharpe ratio, a PSR, a DSR or a posterior probability is never called a discovery.
Only two things are: a screening rejection (always with the word "screening") and an e-LOND rejection.

---

## 4. Across-family screening

### 4.1 Set-up

The unit is a **blind-channel family in its batch**. Batch `b` holds `n_b` such families; each has one designated
evaluation on its reserve window (ARCHITECTURE §6.2). The screening null of family `f` is

```
H^S_f :  no variant of f has a positive mean core-hedged net return on the reserve window.
```

The target is `FDR ≤ α_S = 0.20` over all families screened so far, at the end of every batch. Two complete
candidates follow. **Exactly one will be in force**, chosen by the rule in SIM_PREREG.md §7 from simulation results
only; market results play no part. The designated evaluation computes the statistics of both; the one not chosen is
recorded as descriptive.

### 4.2 The schedule `γ`

```
γ(j; N) = 0.9 · (j + 9)^(−1/2) / Σ_{i=1}^{N} (i + 9)^(−1/2)        for j = 1, ..., N
γ(j; N) = 0.1 · (6/π²) · (j − N)^(−2)                               for j > N
```

For screening `j` is the batch number and `N = N_S = 120`. Then `Σ_{i=1}^{120} (i+9)^(−1/2) = 16.5945`,
`γ_1 = 0.01715`, `γ_50 = 0.00706`, `γ_100 = 0.00519`, `γ_120 = 0.00478`, and all the `γ_j` sum to 1.

> **In plain English.** The 20% allowance is split in advance across about 100 batches, with 20% spare: early
> batches get a little over three times the share of late ones, and a small remainder is kept in case the programme
> runs past 120 batches.
>
> **Problem it solves.** An online procedure must decide each batch without knowing how many will follow. If the
> whole allowance were available to every batch, the error rate over 100 batches would not be controlled.
>
> **Assumes.** About 100 batches. The schedule is fixed here and never depends on a result.
>
> **How it fails.** If far fewer batches are run, most of the allowance is never used and power was given away. If
> far more are run, batches after 120 have almost no power. Either is a loss of power, not of validity. The
> first rejection in batch 1 with 15 families needs a p-value near `0.2 × 0.01715 / 15 = 0.00023`: screening is
> strict early on, which is the price of controlling the rate at every batch end.

### 4.3 Candidate (i): batch online FDR with p-values

Procedure `Batch-BH^PRDS` of Zrnic, Jiang, Ramdas and Jordan (2020, section 5 and its algorithm).

Inputs: for each family in batch `b`, the p-value `p_f` of section 5.1. Let `R_{<b}` be the number of screening
rejections in batches `1, ..., b−1`.

```
level of batch b:       α_b = min( α_S ,  α_S · γ_b · (n_b + R_{<b}) / n_b )          (α_1 = α_S γ_1)
within batch b:         sort the p-values  p_(1) ≤ ... ≤ p_(n_b)
                        k_b = max{ k : p_(k) ≤ k · α_b / n_b }      (0 if no such k)
                        reject the k_b families with the smallest p-values
```

This is the Benjamini-Hochberg procedure run on each batch at a level that grows with earlier discoveries. The
update is the paper's `α_{t+1} = α (γ_{t+1} / n_{t+1}) (n_{t+1} + Σ_{s≤t} R_s)`; it keeps the paper's estimate
`Σ_{s≤t} α_s n_s / (n_s + Σ_{r<s} R_r)` at or below `α` for every `t`. The cap at `α_S` is ours and only lowers
levels.

**Dependence condition** (the paper's theorem for this procedure): the p-values **within each batch are positively
dependent (PRDS)**, and each null p-value is **independent of the p-values of all other batches**. Then
`FDR ≤ α_S` at the end of every batch.

> **In plain English.** Within a batch, the families with the smallest p-values pass if they are small enough for
> their rank. Each earlier discovery makes the test a little easier for later batches.
>
> **Problem it solves.** It keeps the power of testing a whole batch at once while controlling the error rate over
> an open-ended sequence of batches.
>
> **Assumes.** PRDS within a batch; independence across batches; valid p-values.
>
> **How it fails.** (1) **Manhattan does not meet the across-batch condition as designed.** With one shared reserve
> window per domain (ARCHITECTURE §6.2), p-values of different batches come from the same dates and are dependent.
> The theorem then does not apply, and the candidate rests on the simulation alone. It applies as stated only with
> `reserve.mode: disjoint_slices`. (2) Families that bet against each other give negatively dependent p-values,
> which is not PRDS. (3) The p-values come from a bootstrap and are valid only approximately (section 5.2). The
> paper's other procedure (`Batch-BH`, with levels that reuse unspent allowance) needs full independence, also
> within a batch, which a shared window rules out; it is therefore not the candidate.

### 4.4 Candidate (ii): e-BH within the batch, e-LOND across batches

Inputs: for each family in batch `b`, an e-value `E_f` (section 4.5). `R_{<b}` as above.

```
within batch b:   k_b = max{ k ≥ 1 : at least k families of the batch have
                                      E_f ≥ n_b / ( α_S · γ_b · (R_{<b} + k) ) }       (0 if no such k)
                  reject every family of the batch with  E_f ≥ n_b / ( α_S · γ_b · (R_{<b} + k_b) )
```

Exactly `k_b` families meet the last line. With one family per batch this is e-LOND (Xu and Ramdas 2024): reject
when `E ≥ 1 / (α γ_b (R_{<b} + 1))`. With a single batch and `γ_1 = 1` it is e-BH (Wang and Ramdas 2022): reject
the `k` largest when the `k`-th largest is at least `n / (α k)`.

**Validity.** If every null family's e-value has expectation at most 1, then `FDR ≤ α_S` at the end of every
batch, **whatever the dependence** among e-values within and across batches. The proof is three lines (Appendix
A.1). It is the proofs of e-BH and e-LOND put together; it is derived here, not quoted from a published theorem,
and the simulation checks it. The rule rejects at least as much as e-LOND applied to the batch's families in any
order with `γ_b` split equally, which is the published fallback.

Conditions on the batch: `n_b` and `γ_b` must not depend on any reserve result. `γ_b` is fixed in section 4.2;
`n_b` is fixed at freeze by the blind template (ARCHITECTURE §5.1).

> **In plain English.** Each family brings a score that is, on average, at most 1 if the family has no edge. A
> family passes when its score is large enough; "large enough" gets easier with every discovery made so far,
> including those in the same batch.
>
> **Problem it solves.** The reserve window is shared, strategies overlap and some bet against each other. This
> candidate needs no assumption about any of that.
>
> **Assumes.** Each null family's e-value has expectation at most 1 (section 4.5), and the batch conditions above.
>
> **How it fails.** (1) Lower power than (i) when (i)'s conditions do hold: the first rejection in batch 1 with 15
> families needs `E_f ≥ 15 / (0.2 × 0.01715) ≈ 4,373`. (2) If the e-values themselves are not valid (section 4.5)
> the guarantee is void, whatever the dependence.

### 4.5 How historical e-values are built

`E_f` is the final wealth of the family's betting process of section 6, run in date order through the reserve
window, starting at 1 on the window's first day and read once, on its last day:

```
E_f = W_f( last period of the reserve window )
```

with the same weekly test periods, truncation `c`, grid `Λ`, components, variance-ratio rule, hedge and scale as
in section 6, all computed from data before each period (the exploration window supplies the start-up history).

> **In plain English.** We replay the reserve window one day at a time as if it were live, betting play money on
> the family by a rule fixed in advance. The play-money balance at the end is the score.
>
> **Problem it solves.** An e-value could also be made by converting the p-value of section 5.1 (a "calibrator",
> Vovk and Wang 2021), but that conversion is very wasteful: reaching a score of several thousand needs a p-value
> of the order of one in a million. The betting construction is far less wasteful, needs no bootstrap, and is the
> same object as the forward test.
>
> **Assumes.** For a family with no edge, the truncated conditional mean of each period's return given the past is
> at most zero (the null of section 6.3) **on the reserve window**.
>
> **How it fails.** That assumption is about a hypothesis fixed before the data. Here the hypothesis was written
> after the data existed, by a model that may know them, on a window other trials have used (AUDIT §3.1). A family
> with no forward edge can then show a positive mean on the reserve simply because it was chosen for that, and its
> score is not a valid e-value. No method repairs this. It is why the screening level is a filter, why section 7
> estimates the size of the effect, and why section 6 uses only forward data.

### 4.6 What a screening rejection is called

"Family `f` passed screening in batch `b` at a 20% false discovery rate on its reserve window." It is never called
confirmed, significant at 5%, or supported.

---

## 5. Within a family

### 5.1 Hansen's SPA test against core-hedged returns, with the hedge re-estimated in every resample

For family `f`, a window with `n` periods, and the set `V` of variants defined in section 5.3 (`m = |V|`), let
`r_{k,t}` be the net return of variant `k` **before** the hedge, `C_t` the core factor returns, and
`d_{k,t} = X_{x*(k),t}` its core-hedged net return under the live hedge of section 2.2; the benchmark is zero.

```
mean:            d̄_k = (1/n) Σ_t d_{k,t}
long-run sd:     ω̂_k² = γ̂_{k,0} + 2 Σ_{i=1}^{n−1} κ(n,i) γ̂_{k,i}
                 γ̂_{k,i} = (1/n) Σ_{t=1}^{n−i} (d_{k,t} − d̄_k)(d_{k,t+i} − d̄_k)
                 κ(n,i)  = ((n−i)/n) (1−q)^i + (i/n) (1−q)^(n−i),      q = 1/L
statistic:       T = max( 0 ,  max_k  √n · d̄_k / ω̂_k )
resample b:      draw one index sequence τ_b(1), ..., τ_b(n) by the stationary bootstrap (section 5.2) and use it
                 for every variant and for the core factors. The pseudo-series of resample b is the actual
                 periods before the window (the last L_β of them, in their own order), followed by
                 ( r_{k,τ_b(t)} , C_{τ_b(t)} ) for t = 1, ..., n
re-estimate:     β*_{k,b,t−1} = the hedge of section 2.2 computed on the pseudo-series: the same ridge regression
                 on the L_β pseudo-periods before t (at least 252), the same κ, ratios from earlier periods only
                 d*_{k,b,t} = r_{k,τ_b(t)} − β*'_{k,b,t−1} C_{τ_b(t)} − the hedge cost of section 2.2 on β*
centre:          α̂_k = r̄_k − b̂'_k C̄ ,   b̂_k = the least-squares slope of r_k on C over the window (with an
                 intercept),  r̄_k and C̄ the window means
recentre:        Z̄*_{k,b} = mean_t( d*_{k,b,t} ) − g(α̂_k),     g(x) = x · 1{ x ≥ −ω̂_k √(2 ln ln n / n) }
                 T*_b = max( 0 ,  max_k  √n · Z̄*_{k,b} / ω̂_k )
p-value:         p_f = ( 1 + #{ b : T*_b ≥ T } ) / ( B + 1 )
```

`d̄_k`, `ω̂_k` and `T` are computed on the live hedged returns, exactly as in 3.0.0. **With no core factor to
hedge** (a return that is hedged by construction) `d*_{k,b,t} = d_{k,τ_b(t)}` and `α̂_k = d̄_k`, and every line
above is that of 3.0.0.

The recentring is that of Hansen's "consistent" test (2005); the p-value counts ties and adds one, which can only
make it larger than Hansen's `#{T*_b > T} / B`. The "lower" and "upper" p-values (`g(x) = max(x, 0)` and
`g(x) = x`, the least-favourable null of White's reality check applied to the studentised statistic) are computed
and reported beside it. The null is `max_k E[d_k] ≤ 0` with the core factors perfectly removed: no variant beats
zero after hedging and costs.

> **In plain English.** We ask whether the best variant of the family is better than zero by more than luck would
> give the best of `m` variants. Variants that are clearly bad are set aside when we work out what luck looks like,
> so adding hopeless variants does not make the test easier or much harder. And because the hedge is itself an
> estimate, every replay of the window re-does the hedge the way it was done live, so that "luck" includes what
> an imperfect hedge lets through.
>
> **Problem it solves.** The best of many variants always looks good. The test prices that in, using the actual
> correlation between the variants. Version 3.0 replayed the window with the hedge already applied, as if the
> hedge ratios had been known. They are estimated, and the estimate lets a little of each core factor through
> (section 2.2, (4)). A core factor with a positive mean then gives a variant with no edge of its own a small
> positive mean, the same in every replay of the already hedged series, which the test read as the variant's.
>
> **Why the centre is `α̂_k`.** The resamples are drawn from the window. In the world they are drawn from, the
> relation between a variant and the core factors is the window's own least-squares fit, so the mean of the
> perfectly hedged return there is `α̂_k`, a known number. `mean(d*) − α̂_k` is therefore what the live hedging
> rule does around a known truth: what the shrunken hedge ratio lets through, what a hedge that starts from the
> history before the window lets through while it catches up, and the noise of estimating the ratios. The
> statistic `d̄_k` contains the same three things around the unknown truth. Version 3.0 centred at `d̄_k`,
> which compares a statistic that contains the leak with a null distribution that does not. Re-estimating the
> hedge **without** changing the centre does not repair this: centred at `d̄_k`, or at the resamples' own mean,
> the null distribution is again centred near zero while the statistic keeps the leak.
>
> **Assumes.** The returns are stationary and weakly dependent over the window, with enough moments for a central
> limit theorem; `n` is large; the variant set was not chosen by looking at this window; the exposure to the core
> factors moves slowly compared with the window (as section 2.2 assumes).
>
> **How it fails.** (1) The p-value is asymptotic. With fat tails or a few hundred observations it can be too
> small. (2) A structural break inside the window breaks stationarity. (3) It tests the best variant: a family
> can pass on one lucky setting. (4) Variants proposed after looking at the window (adaptive search) make the set
> depend on the data, which the bootstrap does not replay; see section 5.3. (5) **A drifting exposure is only
> partly replayed.** Resampling reorders the window's days, so a resample cannot reproduce a hedge that runs
> steadily behind an exposure that drifts through the window. When a core factor has a large mean and the
> exposure moves quickly, the hedged return has a real mean of its own that this test, like that of 3.0.0,
> counts as the variant's. This is failure (1) of section 2.2 and it is a failure of the hedge, not of the
> resampling. The range over which the test must hold its size is fixed in SIM_PREREG_v2 (scenarios D11 and
> H12). (6) Cost: each resample needs the factor moments of every pseudo-period, several times the work of
> 3.0.0's test (the measured cost is in the pilot rerun report).

### 5.2 The joint stationary bootstrap and its block length

**Bootstrap** (Politis and Romano 1994). `τ(1)` is uniform on `1..n`. For `t ≥ 1`, with probability `1 − q`,
`τ(t+1) = τ(t) + 1` (wrapping from `n` to 1); with probability `q = 1/L`, `τ(t+1)` is uniform on `1..n`. Blocks
therefore have a geometric length with mean `L`. **One index sequence is applied to all variants of the family at
once, and to the core factors**, so every resample keeps the variants' correlation on each day and each day's
unhedged returns stay with that day's factor returns. The hedge is then re-estimated on the resampled series
(section 5.1).

**Block-length rule.**

```
b̂_k  = the automatic block length of Politis and White (2004), with the correction of Patton, Politis and
        White (2009), for the stationary bootstrap, computed on the live hedged series d_{k,·}
L    = min( max( Q90_k(b̂_k) ,  H_f ,  L_min ) ,  L_max )
```

`Q90_k` is the 90th percentile over the family's variants; `H_f` is the longest holding period, in periods, declared
by any hypothesis of the family; `L_min = 5` for daily data (2 for monthly); `L_max = ⌈min(3√n, n/3)⌉`. The
p-values at `L/2` and `2L` are reported as sensitivity and decide nothing.

**Number of resamples.** `B = 999`; if `p_f ≤ 0.10`, continue the same stream to `B = 9,999`; if then
`p_f ≤ 0.01`, to `B = 99,999`. The seed is derived from the batch manifest hash, the family ID and the window ID.

> **In plain English.** To see what luck looks like, we rebuild the window many times from runs of consecutive
> days of the real one. Runs keep the day-to-day memory of returns; using the same days for every variant keeps
> their correlation. The typical run is long enough to cover the memory we measure in the data and the longest
> holding period.
>
> **Problem it solves.** Returns of overlapping positions are autocorrelated, and variants of one idea are highly
> correlated. Shuffling days one at a time, or variants one at a time, would understate luck.
>
> **Assumes.** Dependence dies out within a few block lengths. The 90th percentile and the holding-period floor
> lean towards longer blocks, because blocks that are too short understate luck while blocks that are too long
> only add noise.
>
> **How it fails.** (1) Long memory or slow regimes need blocks longer than `L_max`. (2) The automatic rule looks
> at the autocorrelation of returns, not of squared returns, so volatility clustering is handled only as far as
> the blocks happen to cover it. (3) With `B = 999` the smallest possible p-value is 0.001, which is why the count
> grows for small p-values; the small p-values that candidate (i) needs are in the bootstrap's far tail, where it
> is least accurate.

### 5.3 Which variants are in the bootstrap

`V` = **every variant of the family that has ever been evaluated on that window**, read from the ledger: the
frozen grid, and every variant the adaptive channel added, kept or not.

- The **designated** screening p-value is computed once, at the designated evaluation, on the set as it stands
  then. With the default `reserve.evaluate_adaptive: false`, that set is the frozen grid. It is the p-value of
  record and is never recomputed.
- Any **later** statement about the family on that window (exploration, a retired reserve, or the forward window)
  recomputes the test on the full set at that time.

> **In plain English.** If thirty variants were tried on a window, the test is told thirty, whoever proposed them
> and whether or not they were kept.
>
> **Problem it solves.** Quietly dropping the variants that failed.
>
> **Assumes.** The ledger is complete (every evaluation by Manhattan code is recorded).
>
> **How it fails.** The bootstrap recomputes the maximum over the final set; it does not replay how that set was
> found. When later variants were proposed after seeing earlier results on the same window, the true chance of a
> large maximum is higher than the test says. For that reason adaptive-channel results on the reserve carry no
> evidential weight, and SPA p-values on windows that hold adaptive variants are labelled descriptive unless the
> simulation shows otherwise (SIM_PREREG.md §5, V10).

**The rule, and its evidence.** *An adaptive-channel family, and every adaptive-channel variant, carries zero
evidential weight on the reserve* (ARCHITECTURE §6.3): its reserve results enter no screening statistic, no
within-family claim and no term of the model of section 7. The evidence is pilot scenario **D09b**, in which an
adaptive channel adds to every hypothesis three rounds of six variants, each round copying the best variant so
far **on the reserve window**: the SPA test recomputed on the full set then rejects **0.344 (0.307 to 0.380)**
of families with no edge at the 0.05 level (12 replications; `results/manhattan_sim/PILOT_REPORT.md`, metric
M11). The test is told about all the variants and still rejects about seven times as often as its level says,
because it cannot replay how they were found. D09b is a pilot and the pre-registered consequence V10(b) is decided only on the full run;
the rule does not wait for it, because it was fixed in 3.0.0 before any simulation and the pilot only agrees
with it. The designated blind statistics are untouched by the adaptive channel (V10(a): bit-for-bit identical
with and without it). The rule is enforced in code, not by convention: the weight is computed from the channel
by one function (`manhattan.ledger.evidential_weight`), the model of section 7 takes the channel and not a
weight, and `tests/test_manhattan_adaptive_weight.py` fails if any reserve number of an adaptive-channel family
can change any output.

### 5.4 Romano-Wolf step-down for within-family claims

To say **which** variants have a positive mean, with the family-wise error rate controlled at level `a` within the
family:

```
t_k        = √n · d̄_k / ω̂_k
t*_{k,b}   = √n · ( mean_t d*_{k,b,t} − α̂_k ) / ω̂_k           (same resamples and centre as section 5.1)
step 1:    S_1 = V
step j:    c_j = the ⌈(1 − a)(B + 1)⌉-th smallest of { max_{k in S_j} t*_{k,b} : b = 1..B }
           reject every k in S_j with t_k > c_j ;  S_{j+1} = S_j without them
stop when a step rejects nothing.
```

A hypothesis is "individually supported on the reserve" when at least one variant of its frozen grid is rejected.

> **In plain English.** Take the best variant and ask if it beats what luck gives the best of all of them. If it
> does, set it aside and ask the same of the next best against the best of the rest, and so on until one fails.
>
> **Problem it solves.** Naming individual variants without the error rate growing with the number of variants,
> while using their correlation (so it is less strict than Bonferroni).
>
> **Assumes.** As section 5.1, plus that the bootstrap reproduces the joint distribution of the `t_k` under any
> subset of true nulls.
>
> **How it fails.** As section 5.1. It can also reject nothing in a family that the SPA test passed, because its
> first step centres every variant at zero, which is stricter than the SPA recentring.

### 5.5 Linking the levels: Benjamini-Bogomolov

A within-family claim is made only in a family that passed screening, at that family's own admission level:

```
candidate (i):    a_f = k_b · α_b / n_b                         (the BH threshold its batch was tested at)
candidate (ii):   a_f = α_S · γ_b · (R_{<b} + k_b) / n_b        (the reciprocal of its e-value threshold)
```

This is the selection-adjusted procedure of Benjamini and Bogomolov (2014): with `R` families selected out of `m`
at level `q`, test inside each selected family at level `R q / m`. Its target is the expected **average** error
over the selected families, at most `q`.

> **In plain English.** Having picked the promising families by looking at the data, we may not then test inside
> each at the full level as if it had been the only one. The more selective the picking, the stricter the test
> inside.
>
> **Problem it solves.** Looking only inside the winners and reporting what is found there at an unadjusted level.
>
> **Assumes.** The published theorem needs either independence between families with a simple selection rule, or
> positive dependence (PRDS) of all p-values with Bonferroni or BH inside each family.
>
> **How it fails.** **Neither condition is met here**: families share dates, and Romano-Wolf is used inside. The
> link is therefore a rule whose error rate is measured in simulation (SIM_PREREG.md §5, V4), not a proved
> guarantee. For forward claims the e-value analogue is proved under any dependence (section 6.10, Appendix A.3).

### 5.6 Effective number of tests

`M_eff = Σ_i f(|λ_i|)`, with `λ_i` the eigenvalues of the correlation matrix of the family's variant returns and
`f(u) = 1{u ≥ 1} + (u − ⌊u⌋)` (Li and Ji 2005). It is printed in reports as "about `M_eff` independent variants".
**It is descriptive only**: no level, threshold or decision uses it. PSR, DSR and minimum track record length from
`em_macro.mtstats` have the same status.

---

## 6. Forward e-process

### 6.1 Null, filtration and what a bet is

```
𝓕_{t-1} = everything recorded with an availability time before the decision cut-off of period t:
          all market data, every family's earlier returns, every ledger record, the frozen specs.
H0 (the stated null):     E[ X_t | 𝓕_{t-1} ] ≤ 0   for every forward period t,
```

where `X_t` is the period-`t` net return of the core-hedged strategy, with hedge ratios estimated only from data
before `t` and costs deducted (section 2). Positions, hedge ratios, scales and bets for period `t` are functions of
`𝓕_{t-1}`. The filtration is the **shared** one: it contains every family's past, not only the family's own. That
is needed in section 6.8, where one family's threshold moves when another family is rejected.

**Test period.** Returns are recorded daily, but the test bets on **weekly** returns: a test period is one
calendar week, `P_t` is the sum of the portfolio's daily returns in that week, and its scale is
`s_t = max( √(trading days in the week) × the daily scale of section 2.4 on the last day before the week , the
weekly floor )`. A hypothesis whose data are monthly uses calendar months. Section 6.7 gives the reason: daily
returns are more often serially correlated than weekly ones, and serial correlation is the one thing this test
cannot tolerate.

A betting process stakes a fraction `λ_t`, chosen from `𝓕_{t-1}`, on the next outcome:

```
W_t = W_{t-1} · ( 1 + λ_t · Y_t ),      W_0 = 1,      λ_t ≥ 0  and  𝓕_{t-1}-measurable.
```

If `E[Y_t | 𝓕_{t-1}] ≤ 0` and `1 + λ_t Y_t ≥ 0` always, then `W` is a non-negative supermartingale: its expected
value never rises. By Ville's inequality the probability that it **ever** reaches `1/a` is at most `a`. That is why
it can be watched every day without inflating the error rate.

### 6.2 The non-negative-wealth condition, and why `X_t` has no guaranteed lower bound

`1 + λ_t Y_t ≥ 0` for every possible outcome requires a number `ℓ_t`, known at `t − 1`, with `Y_t ≥ −ℓ_t`
**with certainty**, and then `λ_t ≤ 1/ℓ_t`. For `Y_t = X_t` we looked for such a bound and did not find one:

| position | why no bound is guaranteed |
|---|---|
| short cash position | the price can rise without limit; the loss is unbounded |
| futures, long or short | daily price limits exist for some contracts only, are changed by the exchange, widen during the day for some products and do not apply in some delivery months; a locked-limit market cannot be left; the price itself can be negative (WTI, April 2020), so even a long position can lose more than its notional |
| levered position | the loss is the unlevered loss times the leverage |
| the hedge leg | `−β' C_t` is itself a set of long-short factor portfolios with unbounded short legs |
| stop-loss order | prices gap through stops; a stop is an intention, not a bound |
| **gross-exposure cap `G`** | bounds the loss by `G` times the worst adverse move of any held instrument, and **that move is itself unbounded** for a short or a futures position. A cap alone guarantees nothing |

A guaranteed bound would need every position to be long, unlevered and in cash instruments, or to hold bought
options against every leg. Manhattan families are not restricted in that way. There is also a general obstacle
(Bahadur and Savage 1956): over all distributions with a finite mean and unbounded support, no test of the mean
has more power than its size. Something must be assumed or changed.

### 6.3 The alternative: a bounded transform with its own null, plus an asymptotic guard

**Transform.** With `Z_t = P_t / s_t` (section 2.4):

```
Y_t = max( Z_t , −c ),       c = 6 (weekly test periods),  4 (monthly)        [fixed in v3.0]
H0^c (the tested null):      E[ Y_t | 𝓕_{t-1} ] ≤ 0   for every forward period t.
```

`Y_t ≥ −c` with certainty, so any `λ_t ≤ 1/c` keeps wealth non-negative. `Y_t` is unbounded above; that is
harmless, because `E[1 + λY | 𝓕]` needs only the conditional mean.

**Exactly which guarantee is lost.** `Y_t ≥ Z_t`, so `H0^c` is a smaller set than `H0`: a strategy can satisfy `H0`
(no edge) and violate `H0^c`, if its losses beyond `c` ex-ante standard deviations are what bring its mean down to
zero. For such a strategy the test of `H0^c` gives **no protection**. A rejection therefore establishes

> "at some times the conditional mean of the return, **with each period's loss beyond `c` ex-ante standard
> deviations ignored**, was positive",

and not "the mean return was positive". The gap is exactly the expected size of losses beyond the truncation point.
Strategies that earn a small premium and occasionally lose very much (short volatility, pegs, crowded carry) are
the ones that fall into it.

**Guard (asymptotic confidence sequence).** A family is rejected only if, in addition, the lower end of a one-sided
asymptotic confidence sequence for the running mean of the **untruncated** `Z` of its leading component is above
zero (Waudby-Smith, Arbour, Sinha, Kennedy and Ramdas 2024, the one-sided martingale form):

```
μ̂_t = (1/t) Σ_{u≤t} Z_u ,      σ̂_t² = (1/t) Σ_{u≤t} Z_u² − μ̂_t²
low_t = μ̂_t − sqrt(  [ 2 (t σ̂_t² ρ² + 1) / (t² ρ²) ] · ln( 1 + sqrt(t σ̂_t² ρ² + 1) / (2 α_G) )  )
ρ² = ( −2 ln α_G + ln(−2 ln α_G) + 1 ) / ( σ̂_m² · m · ln m ),      m = 52 weeks,   α_G = 0.05
guard holds at t  ⇔  t ≥ 52  and  low_t > 0
```

The leading component is the one with the largest wealth among the family's components (section 6.5). The guard's
assumptions are those of the paper's time-varying result: the cumulative conditional variance grows without bound;
a Lindeberg-type condition, implied by uniformly bounded conditional moments of order above 2; and a variance
estimate that converges at a polynomial rate. **The guard's guarantee is asymptotic only**: its coverage approaches
95% as the start `m` grows, and it says nothing exact at any finite sample. It does not enter the 5% accounting.
Its job is to stop a rejection when the truncated and untruncated records disagree.

**Tail record.** For every component the ledger keeps `N_trunc` (the number of truncated periods) and the tail debt
`D_t = Σ_{u≤t} (Y_u − Z_u) ≥ 0`. Every statement of formal support carries them: "formally supported, ignoring
weekly losses beyond 6 ex-ante standard deviations (`N_trunc` such weeks, tail debt `D`)".

> **In plain English.** We cannot promise that a strategy will never lose more than some amount in a week, so we
> test a slightly different thing: its record with each catastrophic week capped at six times a normal week's
> swing. That test is exact. Because capping flatters strategies that live off rare disasters, we also require
> that the uncapped record points the same way, and we print how many weeks were capped and by how much.
>
> **Problem it solves.** An exact test that can be watched every day needs wealth that cannot go below zero, and
> real returns have no floor.
>
> **Assumes.** For the exact part: nothing beyond `H0^c` and that positions, scales and bets were fixed before
> each period. For the guard: finite moments a little above the second, and enough data.
>
> **How it fails.** (1) A null strategy whose disaster has not yet happened in the sample passes both the capped
> test and the guard. No test on returns alone can prevent this; the defence is the family spec's declared tail
> exposure, the critic and the tier rules. The simulation measures how often it happens (SIM_PREREG.md §5, V9).
> (2) A smaller `c` hides more of the tail; a larger `c` forces smaller bets and slower evidence. (3) The choice
> of `c` and `s_floor` is fixed here and may suit some families badly.

Two alternatives were considered and not chosen. A **tail charge** (subtract from `Y_t` an upper bound on the
expected truncated loss, so that `H0` again implies the tested null) needs a bound on the tail; using only a
variance bound, the charge is so large that no realistic edge survives it, and a sharper bound is itself an
unverifiable assumption. A **sign test** (`Y_t = sign(X_t)`) is exact and bounded but tests the median, which is
positive for exactly the disaster-prone strategies described above.

### 6.4 The predictable betting rule

```
Λ = { λ_max · 2^(−j) : j = 0, ..., 5 },      λ_max = 0.9 / c            [fixed in v3.0]
component wealth:    W_t = (1/6) Σ_{λ in Λ}  Π_{u ≤ t} ( 1 + λ · Y_u )
```

For weekly test periods `Λ = {0.15, 0.075, 0.0375, 0.0188, 0.0094, 0.0047}`. An average of betting processes with
fixed
fractions is itself a betting process: it equals betting, each period, the wealth-weighted average of the grid,
which depends only on the past. Every term has `1 + λ Y_u ≥ 1 − 0.9 = 0.1 > 0`.

> **In plain English.** Six fixed bet sizes run side by side, each with a sixth of the stake. The total follows
> whichever size suits the strategy, without anyone choosing a size after the fact.
>
> **Problem it solves.** The best bet size depends on the edge, which is unknown. Tuning it on the data would
> break the test.
>
> **Assumes.** Nothing beyond section 6.3.
>
> **How it fails.** It can lose power only: at most `ln 6 ≈ 1.8` units of log-wealth against the best grid size,
> and more if the edge is so large that even the largest size is too small (annualised Sharpe ratio above about
> 1.1 with weekly test periods; section 6.9 includes this loss).

### 6.5 Components and the family process

A family has `H_f + 1` components: one per hypothesis (on `P_{h,t}`) and one for the family portfolio (on
`P_{f,t}`). Each has its own scale, truncated return and wealth as above.

```
W_{f,t} = ( 1 / (H_f + 1) ) · ( Σ_{h in f} W_{h,t} + W_{portfolio,t} )
family null H0_f :  H0^c holds for every component of f.
```

An average of e-processes is an e-process for the null under which all of them are null.

> **In plain English.** The family's score is the average of the scores of its domains and of the family as a
> whole. If one domain works, its score carries the average; if all work a little, the whole-family component
> does.
>
> **Problem it solves.** A mechanism may hold in one market only, or weakly in all. We do not know which in
> advance and may not choose afterwards.
>
> **Assumes.** The weights are fixed at freeze (equal).
>
> **How it fails.** The family is rejected when at least one component has an edge; the rejection does not say
> which (section 6.10 does). Averaging costs up to `ln(H_f + 1)` in log-wealth.

### 6.6 Timing, gaps and revisions

- **Fixed lag.** Test period `t` enters the process 7 calendar days after it ends, using the values stored then
  (final settlements; the same 7 days as the settlement re-request). Bets for `t` use only periods before `t`.
- **No observation is ever dropped.** If prices are missing when a test period is due, the period stays open: the
  position's return over the whole gap is taken from the prices on either side when data return, and enters as
  one period covering `k` weeks with scale `s_t √k`. An instrument that stops trading enters at its final value.
  Whether a period is "missing" is decided by a rule on data availability that does not look at the return.
- **Revisions never rewrite the process.** A later vendor revision is recorded and feeds section 7; the wealth path
  is not recomputed.
- **Enrolment.** A family's test process starts at 1 on the first period after it is enrolled (section 6.8). A
  tracking wealth from its freeze date is also recorded for every family, labelled "tracking, not a test".

> **Problem it solves.** If a day could be skipped when its data were late, and data tend to be late on chaotic
> days, losses would be skipped more often than gains. Closing every gap from prices on both sides leaves nothing
> to skip.
>
> **How it fails.** If a price never returns and the final value is unknown, the loss must be imputed; the rule is
> the worst case (`Y = −c`), which is conservative but can stall a sound family.

### 6.7 What the martingale null covers and what it does not

**Covered (validity holds under any of these).** Volatility clustering and any dependence in the conditional
variance or higher moments; fat upper tails; regimes; any dependence between families; any stopping rule;
time-varying betas. The null constrains the conditional **mean** only.

**Not covered, or changes the meaning of a rejection.**

- **Serial dependence in the mean.** `H0` says that the conditional mean is at most zero at **every** time. A
  strategy with a zero long-run mean whose returns are positively autocorrelated has a positive conditional mean
  after gains, so it is **not in the null**, and the wealth process is no longer a supermartingale. The size of
  the effect is known: write `VR` for the variance ratio (the long-run variance of summed returns divided by the
  one-period variance; 1 with no serial correlation). Under a Gaussian approximation, the probability that a
  fixed-fraction wealth ever reaches `1/a` rises from `a` to about `a^(1/VR)`. For the first enrolled family
  (`a = 1/2,039`) and `VR = 1.5` (daily returns with first-order autocorrelation 0.2) that is 0.006 instead of
  0.0005. Negative serial correlation (`VR < 1`) makes the test conservative. Two rules, both decided from past
  data only, limit the damage:
  1. **Weekly test periods** (section 6.1). Short memory in daily returns is mostly inside the week.
  2. **Variance-ratio rule.** Before each week, from the component's daily standardised returns over the previous
     252 trading days, `VR̂ = 1 + 2 Σ_{j=1}^{4} (1 − j/5) ρ̂_j` with `ρ̂_j` the lag-`j` autocorrelation. If
     `VR̂ > 1.25` the component bets nothing that week (its wealth does not move). For monthly test periods the
     rule is `ρ̂_1 > 0.20` over the previous 60 months.

  What remains uncovered is serial correlation at horizons longer than a week that the rule does not see. And a
  rejection always means "at some times this strategy had a positive expected return given the past": it does
  not mean "its long-run mean is positive", and it does not mean the edge still exists. An edge that existed and
  then decayed is validly rejected.
- **Stale or smoothed prices.** Marks that lag (illiquid instruments, monthly-average yields) create positive
  serial correlation mechanically, with the effect just described and for a reason that is not an edge. Forward
  executables must use first-hand daily marks (as `ledger.marks.mark_can_act` requires for the Lab) or be tested at
  a frequency at which marks are fresh; the variance-ratio rule is the backstop.
- **Overlapping holding periods** are harmless when every period is marked to market at fresh prices: the null is
  about one-period returns of the whole book. They matter only through stale marks.
- **Losses beyond the truncation point** (section 6.3).
- **Costs that are assumed, not measured.** A paper process deducts modelled costs. If real costs are higher, the
  null about real net returns may hold while the paper process rejects. Tiers above "Statistically supported"
  require measured costs (section 8).

### 6.8 Combining across families: e-LOND at 5%

**Enrolment.** A family is enrolled once, at the first quarterly review at which it holds the tier Promising or
higher (section 8). Enrolled families are numbered `i = 1, 2, ...` in enrolment order (ties by family ID). Family
`i` receives `γ^F_i = γ(i; N_F)` with `N_F = 300` (`γ^F_1 = 0.00981`, `γ^F_100 = 0.00297`, `γ^F_300 = 0.00176`),
and its test process starts at 1.

**Rule.** At each period `t`, let `R(t−)` be the number of families already rejected, and call a family eligible
if it is enrolled, not yet rejected, and its guard holds at `t`.

```
k_t = max{ k ≥ 1 : at least k eligible families have  W_{i,t} ≥ 1 / ( α_F · γ^F_i · (R(t−) + k) ) }    (0 if none)
reject every eligible family with  W_{i,t} ≥ 1 / ( α_F · γ^F_i · (R(t−) + k_t) ),       α_F = 0.05
```

A rejection is permanent. The wealth used is the current wealth, not its past maximum.

**Validity.** `FDR ≤ 0.05` over all enrolled families, at every time, under any dependence between families,
provided each null family's process is a non-negative supermartingale for the shared filtration (section 6.1). The
proof is Appendix A.2. It is e-LOND (Xu and Ramdas 2024) in the "doubly sequential" setting the authors describe,
with thresholds that use the number of rejections made so far by any family; the three-line proof is theirs with
that count substituted. Enrolment by history or by posterior probability does not harm validity, because each test
process starts after enrolment and uses only later data.

> **In plain English.** Each enrolled family holds a small share of the 5%. A family is declared when its
> play-money balance, built only from days after it was enrolled, passes a bar set by its share. Every declaration
> lowers the bar for all the others.
>
> **Problem it solves.** Hundreds of families are watched every day for years, they overlap and their number is not
> known in advance. Any one of them watched alone at 5% would not give 5% overall.
>
> **Assumes.** Section 6.3 for each family; the shared filtration; `γ^F` fixed here.
>
> **How it fails.** Not by false discoveries beyond 5% (for the truncated null), but by **power**. The first
> enrolled family must multiply its stake by `1 / (0.05 × 0.00981) ≈ 2,039`, the hundredth by about 6,733 if
> nothing has been rejected. Section 6.9 turns that into years.

### 6.9 How long formal support takes

Expected growth of log-wealth per year at the best fixed bet is about `SR² / 2`, less when the best bet exceeds
`λ_max`, where `SR` is the component's true annualised Sharpe ratio after hedging and costs. Years needed, in
expectation, with weekly test periods, before the mixture cost of at most 1.8:

| true hedged net Sharpe ratio | log-wealth per year | years to 2,039 (first enrolled) | years to 6,733 (hundredth, no rejections yet) |
|---|---|---|---|
| 0.5 | 0.13 | 61 | 70 |
| 1.0 | 0.50 | 15 | 18 |
| 1.5 | 1.04 | 7.3 | 8.5 |
| 2.0 | 1.58 | 4.8 | 5.6 |
| 3.0 | 2.66 | 2.9 | 3.3 |

**Formal forward-only support at 5% across hundreds of families is out of reach within ten years for a hedged
Sharpe ratio below about 1.3.** This is arithmetic, not a defect to be tuned away; it is the price of a claim that
uses no history and holds under any dependence. It is why the tiers of section 8 exist, why enrolment is limited to
Promising families (enrolling all families at freeze would raise every bar several-fold), and why the family
portfolio component matters: several weakly correlated domains can lift a family's Sharpe ratio well above that of
any one of them.

### 6.10 Within a formally supported family

Component `j` of a rejected family `i` (a hypothesis, or the family portfolio) is individually formally supported
at time `t` when

```
W_{j,t} ≥ (H_i + 1) / ( α_F · γ^F_i · R(t) ),        R(t) = number of families rejected so far.
```

Then the expected share of formally supported families in which at least one null component is so named is at most
0.05, under any dependence (Appendix A.3). This is the e-value form of the Benjamini-Bogomolov link.

---

## 7. One hierarchical model for history and forward data

### 7.1 The model

All quantities are annualised Sharpe ratios of the core-hedged net return of the **family portfolio** `P_f`.
`m(f)` is the family's mechanism class, declared at freeze.

```
Class m:        logit(ρ_m) ~ Normal(μ_ρ, σ_ρ²)                                   retention of the class, between 0 and 1

Family f:       a_f ~ (1 − w) · Normal(μ_A, τ_A²)  +  w · Normal(μ_A, s_R²)      apparent historical edge
                θ_f = ρ_{m(f)} · a_f + η_f                                        true forward edge
                η_f ~ (1 − w) · Normal(0, 0.02²)  +  w · Normal(0, s_R²)

Data:           y^H_f = a_f + ψ · s^H_f · ε^H_f                              reserve estimate: blind channel, designated only
                y^F_f = θ_f + ψ · s^F_f · ( √r · ν + √(1 − r) · ε^F_f )      forward estimate: every family with a forward record
                ε^H_f, ε^F_f, ν ~ Normal(0, 1), independent;   ν is one shock, common to every family

Reported:       Π_f = Pr( θ_f ≥ θ_min | all data ),     θ_min = 0.25
```

`y^H_f` and `y^F_f` are the sample Sharpe ratios of `P_f` on the reserve window and on the forward record; `s^H_f`
and `s^F_f` are their standard errors from the joint stationary bootstrap of section 5.2 (one index sequence for
the families that share dates). A family of the adaptive channel has no reserve term (section 7.3).

`r` is **the share of a forward estimate's sampling variance that is common to all families**: the average,
over all pairs of families with a forward record, of the sampling correlation between their two forward
estimates (the sample correlation of the two return series over their common dates, times the number of common
dates divided by the geometric mean of the two record lengths), floored at zero. It is measured from the returns,
not learned by the model.

Priors, fixed in v3.0 for every parameter that survives:

| parameter | prior | reading |
|---|---|---|
| `μ_ρ` | Normal(logit 0.35, 1) | on average about a third of an apparent historical edge survives; wide |
| `σ_ρ` | half-Normal(1) | mechanisms may differ a lot |
| `μ_A` | Normal(0.3, 0.3²) | generated families look good on history, on average |
| `τ_A` | half-Normal(0.5) | spread of apparent edges between families |
| `ψ` | 1 + half-Normal(0.25) | standard errors may be understated, never overstated |
| `w`, `s_R` | 0.10, 1.5 (constants) | weight and scale of the wide components |
| spread of `η_f`, narrow component | 0.02 (constant) | a family's forward edge is `ρ` times its apparent edge, almost exactly, unless it is in the wide component |

Gone from 3.0.0, with what they described: `φ` (how alike the retentions of one class's families are; the wide
component of `η_f` now carries every family-level departure) and `σ_dom` (the spread between the domains of one
family; the model no longer has a hypothesis level). `ψ_H` and `ψ_F` are one `ψ`.

**The closed form.** Fix the hyperparameters `(μ_A, τ_A, ψ, ρ)` and the common shock `ν`, and say which component
`a_f` and `η_f` came from: `i` and `j` are each "narrow" or "wide", with variances `v_i` in `{τ_A², s_R²}` and `u_j`
in `{0.02², s_R²}`. Write `ỹ^F_f = y^F_f − ψ s^F_f √r ν` for the forward estimate less the common shock and
`e_F = (1 − r) ψ² (s^F_f)²` for the variance that is the family's own. Then everything about family `f` is normal:

```
reserve step:    y^H_f ~ Normal( μ_A ,  v_i + ψ² (s^H_f)² )
                 a_f | y^H_f ~ Normal( m_a , c_a )
                     m_a = μ_A + v_i · (y^H_f − μ_A) / ( v_i + ψ² (s^H_f)² )
                     c_a = v_i · ψ² (s^H_f)² / ( v_i + ψ² (s^H_f)² )
                 (a family with no reserve term:  m_a = μ_A ,  c_a = v_i , and no density)
forward step:    θ_f | y^H_f ~ Normal( m_0 , c_0 ),        m_0 = ρ · m_a ,     c_0 = ρ² · c_a + u_j
                 ỹ^F_f | y^H_f ~ Normal( m_0 ,  c_0 + e_F )
                 θ_f | y^H_f, y^F_f ~ Normal( m_1 , c_1 )
                     m_1 = m_0 + c_0 · (ỹ^F_f − m_0) / ( c_0 + e_F )
                     c_1 = c_0 · e_F / ( c_0 + e_F )
                 (a family with no forward record:  m_1 = m_0 ,  c_1 = c_0 , and no density)
weights:         π_ij ∝ (prior weight of i) · (prior weight of j) · (the reserve density) · (the forward density)
family:          L_f(μ_A, τ_A, ψ, ρ, ν) = Σ_ij of the unnormalised weights        the family's likelihood
                 Pr( θ_f ≥ θ_min | hyperparameters, ν, data ) = Σ_ij π_ij · Φ( (m_1 − θ_min) / √c_1 )
```

Families are independent given the hyperparameters and `ν`, so their joint likelihood is the product of the
`L_f`. The hyperparameters and `ν` are then **integrated, not estimated**: every sum above is evaluated on the
fixed grid of Appendix B, each node weighted by its prior and by the likelihood, with the `ρ_m` of different
classes tied through `(μ_ρ, σ_ρ)`, which are on the grid as well. `Π_f` is the weighted sum of the last line. The
posterior of `θ_f` is therefore a finite mixture of normals whose weights, means and variances are all written
above: no sampler, no random number, the same answer every time.

> **Why the common shock is there.** Forward records of different families cover the same calendar days. A
> market-wide move lifts or lowers all their estimates at once, and with hundreds of families the model would
> otherwise take the **average** forward level as known almost exactly and explain a lucky level the only way
> it could: by a high retention, that is, by an edge shared by everyone. On the development scenario with fat
> tails this gave nearly every family of one simulated programme a posterior probability near 0.45 when none
> of them had an edge. With `ν`, the average level is only as certain as the common luck allows.
>
> **How it fails.** One shock with one share `r` is a summary: it treats a family frozen last month and one
> frozen eight years ago as sharing the same luck. Reserve estimates get no common shock: a level shared by
> all reserve estimates is read as apparent edge (`μ_A`), which is what "apparent" means, and it reaches `θ_f`
> only through `ρ`. Families that move **against** each other cancel in `r`.

### 7.2 The design decisions in it

**(a) One combined decay and contamination parameter.** `ρ` is the only link from history to the future, one
number per mechanism class. It absorbs, without separating them: decay after discovery or publication, the
generator's knowledge of past winners, earlier use of the window, and ordinary overfitting. `ρ = 0` means the
historical edge was entirely an artefact; `ρ = 1` means it persists in full.

> **Problem it solves.** Stacking a decay haircut on a data-mining haircut on a selection haircut counts the same
> doubt several times, and no one can say what the product means. One parameter is learned from the one comparison
> that identifies it: forward results against historical results, across families.
>
> **Assumes.** Retention is the same for the families of one mechanism class, up to the wide component of `η_f`,
> and constant over a family's forward life.
>
> **How it fails.** Before many families have forward data, `ρ` is its prior. If decay continues during the forward
> period, a constant `ρ` overstates the future (hence model S5 below).

**(b) Selection handled once.** Every blind family's designated reserve result enters, good or bad; every
recorded forward result enters, dormant families included. Nothing is filtered on its outcome. Shrinkage towards
the group is then the adjustment for having looked at many. **No further haircut is applied**: no deflated Sharpe
ratio, no Bonferroni-adjusted Sharpe ratio, no extra discount.

> **Assumes.** Exchangeability within a mechanism class, and a complete ledger.
>
> **How it fails.** If generator quality drifts across batches, or results are missing from the ledger, the group
> the model shrinks towards is the wrong one.

**(c) Closed form on a fixed grid, hyperparameters integrated.** No hyperparameter is estimated once and plugged
in: each is summed over its grid with its prior, and so is the common shock. A fit is used only if at most **1%** of the posterior mass of
`μ_A` sits on the two end nodes of its grid (the data then lie inside the range the grid covers); otherwise the
review states "model not computed" and no tier changes. This check replaces the sampler's convergence gate of
3.0.0 (`R̂`, effective sample size, divergences), which has nothing to measure here.

> **Problem it solves.** Two things. Plug-in empirical Bayes treats the estimated spread between families as
> known; with few families that understates uncertainty and overstates `Π_f`, which is why 3.0.0 sampled every
> hyperparameter. And the sampled model could not be afforded or trusted: it did not mix as written, and the
> simulation that must test it needed of the order of 50,000 CPU-hours. Summing over a grid keeps the first
> property and removes the second problem: a fit of all six models for 240 families takes seconds (the measured
> cost is in the pilot rerun report).
>
> **Assumes.** The grid is fine enough and wide enough. Its nodes are fixed in Appendix B and never depend on
> data, except that nodes the reserve data rule out by a factor of `e^18` are skipped.
>
> **How it fails.** (1) A posterior much narrower than the grid's step (0.02 in `μ_A`) would be badly summed;
> that needs several thousand families. (2) The gate checks `μ_A` only.

**(d) Robust mixture components.** A tenth of the prior mass of `a_f` and of `η_f` sits in a wide normal
component (standard deviation `s_R = 1.5`). The posterior weight of the wide component of `η_f` is reported for
every family as its "conflict" weight.

> **Problem it solves.** Prior-data conflict. A family whose data sit far from where the group says it should be
> is otherwise dragged to the group; a family whose forward record contradicts its history is otherwise forced to
> fit both. The wide component lets the data win when the conflict is large.
>
> **How it fails.** It also lets a lucky outlier keep more of its luck: a family with no edge whose forward
> estimate is three standard errors above zero is given a posterior probability near one half by the central
> model until its record lengthens. The tier rules use the most cautious of six models for that reason. The wide
> component is a normal, not the Student-t of 3.0.0, so its tails are lighter; that is the price of the closed
> form.
>
> **A known limitation: two groups described by one hump.** Where a large share of families has an edge and the
> rest have none, the narrow component has to stretch over both groups (the wide one has a tenth of the mass
> and a scale of 1.5, which fits neither), and in the middle of the scale the central model says too much. In
> pilot scenario D08, where selection on history leaves a third of the families with an edge and two thirds at
> exactly zero, families given a probability near 0.45 at year 10 had an edge 0.18 of the time, and those given
> 0.55, 0.29; the expected calibration error was 0.101 (0.034 to 0.136) against a bound of 0.10. Given the same
> estimates and standard errors, a plain normal prior with the population's own mean and variance makes the
> same error (0.102), and a prior with the population's true two-group shape does not (0.009): the cause is
> the shape of the prior, not the estimates, their standard errors, the retention, the common shock or the
> grid (`results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md`, part 2). The ends of the scale, where the tier
> rules decide, are right there: 0.97 stated against 0.99 observed, and 112 of the 113 families with
> `Π_f^min ≥ 0.80` had an edge. Where edges are rare the wide component does the work of a second group and
> the error is small (0.004 to 0.019 in the other pilot scenarios). **Not repaired in 3.1.** The repair is a
> prior in two groups whose share and scale are learned, which is another model: it turns two constants fixed
> in 3.0 (`w`, `s_R`) into learned quantities, and built on these scenarios it would be fitted to their
> convention that a family with no edge has a mean of exactly zero. If the full run confirms the error, V6
> fails in D08 and the posterior-based tiers stay off (SIM_PREREG_v2 §5) until a later version changes the
> prior.

**(e) Required sensitivity analysis.** Every review fits six models:

| model | change from the central model |
|---|---|
| S0 | none (central) |
| S1 | pessimistic retention: `μ_ρ ~ Normal(logit 0.15, 1)` |
| S2 | optimistic retention: `μ_ρ ~ Normal(logit 0.60, 1)` |
| S3 | more robust mass: `w = 0.25` |
| S4 | standard errors understated by half: `ψ = 1.5`, fixed |
| S5 | forward decay: `θ_f` at forward age `u` years is `θ_f · 2^(−u/3)` |

`Π_f^min` is the smallest `Π_f` over the six and `Π_f^max` the largest. **Tier entry uses `Π_f^min`; dormancy uses
the forecast of the most hopeful model, `PP_f^max`, and the family's own forward record** (so that promotion does
not rest on one prior, and abandonment on none: section 9.1). Reports show the range. S4 was "no
cross-correlation and `ψ_H = ψ_F = 1.5`" in 3.0.0; no model uses a full correlation matrix any more ((g) below), and
S4 keeps the common shock like the others, so what remains of it is the inflated standard error. Under S5 the forward estimate of a record of `u` years has mean
`θ_f` times the average of `2^(−t/3)` over the record, and `Π_f` is about the edge at the family's current age.

**(f) Wording.** `Π_f` is "the posterior probability, under the stated model, that the family's forward edge is at
least 0.25". It is **never** described as a p-value, a significance level, a false discovery rate, an error rate
or a confidence level, and `1 − Π_f` is never called a probability of a false positive. It depends on the priors
above; the sensitivity range is always shown with it.

**(g) What the closed form gave up.** Stated so that nobody has to find it out:

1. **No hypothesis level.** The model speaks about family portfolios. Which hypothesis of a family carries its
   edge is said by Romano-Wolf on the reserve (section 5.4) and by the forward test's components (section 6.10),
   not by the model.
2. **One number for the dependence between families, not a covariance matrix.** 3.0.0 gave the model the full
   sampling covariance of all estimates. 3.1 gives it `r` and one common forward shock. That covers luck shared
   by all families; it does not cover groups of families that move together or against each other, or luck
   shared between one family's reserve window and another's forward record when the two overlap in calendar
   time. Three things limit what is left: the narrow component of `η_f` is fixed, not learned, so dispersion
   that is really shared luck cannot widen it; `ψ` is learned and grows when forward estimates scatter more than
   their standard errors say; and S4 inflates every standard error by half. How much is lost is measured in the
   held-out scenarios with strong dependence (SIM_PREREG H11).
3. **Wide normals instead of Student-t components**, as in (d).
4. **Family-level retention has no spread of its own** (3.0.0's Beta distribution): a family that keeps more or
   less of its edge than its class is described by the wide component of `η_f`.

> **In plain English (the whole section).** History and live results are read together by one model that knows
> three things: families of the same kind resemble each other; what looked good on old data usually keeps only
> part of its edge; and its own assumptions may be wrong, so it is run six ways and the cautious answer is used.
> In 3.1 the model is simple enough to be worked out exactly with pencil-and-paper formulas, instead of by a
> long random search.

### 7.3 What the model does not see

Exploration-window results (they were available when hypotheses were written); **reserve results of the adaptive
channel**; any non-designated reserve evaluation.

For the adaptive channel this is the rule of section 5.3, with its evidence (pilot scenario D09b). In the model
it is not a setting: a family's reserve term exists only if `manhattan.ledger.evidential_weight` gives its
channel and its evaluation weight 1, which it never does for the adaptive channel. An adaptive-channel family
still enters through its forward record, which is dated after its freeze and counts in full.

### 7.4 The sampled model of 3.0.0: an optional robustness check

The model of PROTOCOL_v3.md section 7 (`manhattan/stats/hier.py`: every hyperparameter sampled, Student-t
components, a hypothesis level, the full sampling covariance) is kept in the repository. It may be run on the
data of a real review, outside the review itself, to see whether the two models tell the same story about a
family. **It decides nothing**: no tier, no dormancy and no report figure comes from it, it is not part of the
simulation's main loop, and a disagreement between the two is a note for Ethan, not a change of tier.

---

## 8. Tiers

Tiers are evaluated only at **quarterly reviews** (the first business day on or after the 15th of January, April,
July and October), except the immediate exits marked below. "Forward days" are recorded forward periods since the
family's freeze. "Two consecutive reviews" gives every threshold hysteresis in time, and entry and exit thresholds
differ.

### 8.1 Promising

| | rule |
|---|---|
| **Enter** | (a) a blind-channel family that passed screening (section 4) in its designated evaluation; **or** (b) at a review: `Π_f^min ≥ 0.40`, at least 126 forward days, and forward data coverage of at least 90% |
| **Exit** | `Π_f^min ≤ 0.20` at two consecutive reviews, with at least 252 forward days |
| **Effect** | enrolment in the forward test (section 6.8); adaptive variants may be proposed |

### 8.2 Statistically supported

| | rule |
|---|---|
| **Enter** (all) | Promising; `Π_f^min ≥ 0.80`; the forward sample mean of `P_f` is positive; at least 252 forward days for a blind-channel family in which Romano-Wolf rejected at least one variant on the reserve at level `a_f` (section 5.5), otherwise at least 504 forward days; no open integrity flag |
| **Exit** | `Π_f^min < 0.60` at two consecutive reviews; **or immediately** if `Π_f^min < 0.40` at any review, or on a `nondeterminism` or data-integrity record |

### 8.3 Live-experiment eligible (fixed loss cap, tiny size)

| | rule |
|---|---|
| **Enter** (all) | Statistically supported at two consecutive reviews; every instrument is one Ethan can trade; paper costs measured from recorded quotes over at least 3 months are at most 1.5 times the modelled costs; estimated capacity is at least 20 times the experiment's size; a critic review of operational and tail risk is logged; `forward.loss_cap_usd > 0`; **Ethan's approval is recorded in the ledger** |
| **Size and cap** | the experiment is sized so that a loss of `c` ex-ante standard deviations in one period costs at most one tenth of the loss cap; the cap is a fixed amount of money per experiment and is not raised |
| **Exit** | **immediately and for good, for that experiment,** when cumulative loss reaches the cap; when the family leaves Statistically supported; when live returns differ from paper returns by more than twice the expected tracking error for two consecutive reviews |

**No real-money execution is built.** This tier is a label saying an experiment could be approved. With the
defaults (`forward.loss_cap_usd: 0`, `forward.real_money: false`) no family can enter it.

### 8.4 Scale eligible

For a proposed scale `q` (a fraction of capital):

```
ΔCE(q) = q · ( μ_net − impact(q) ) − (γ_R / 2) · q² · σ² − q · p_tail · L_tail
```

`μ_net`: forward mean after **measured** costs from the live experiment; `impact(q)`: market impact at that size
from `ledger.capacity`; `σ²`: forward variance; `γ_R`: risk aversion (4, fixed in v3.0); `p_tail · L_tail`: a tail
charge, the larger of the tail debt per year recorded in section 6.3 and three times the worst recorded loss per
year. `ΔCE` is a certainty-equivalent gain per year from holding the family at scale `q`.

| | rule |
|---|---|
| **Enter** (all) | at least 12 months as a live experiment; posterior mean of `ΔCE(q) > 0` under **every** model S0-S5; posterior probability that `ΔCE(q) > 0` at least 0.80 under S0 and S1 (a posterior probability, not an error rate); `q` at most the capacity estimate |
| **Exit** | posterior mean of `ΔCE(q) < 0` under S0 at two consecutive reviews; measured costs above 1.5 times those used at entry; `q` above the capacity estimate; the family leaves Statistically supported |

### 8.5 Formally supported by forward-only evidence

| | rule |
|---|---|
| **Enter** | an e-LOND rejection (section 6.8), which includes the guard |
| **Exit** | never: the rejection is a statement about evidence up to its date, and removing it would break the 5% accounting. A separate status, "decayed since", is set when the family leaves Promising |

This tier can be reached from Promising without passing through the live tiers.

> **In plain English.** Promising: worth watching. Statistically supported: history and live results agree under
> cautious assumptions. Live-experiment eligible: Ethan may try it with a small, capped amount. Scale eligible: it
> is worth more capital after real costs, tail losses and capacity. Formally supported: live results alone prove
> it at 5%.
>
> **Problem the hysteresis solves.** A family near a threshold would otherwise flip in and out with noise, and
> each flip would invite a story.
>
> **How the tiers fail.** The middle tiers rest on the model of section 7, and so on its priors. The loss cap
> limits the cost of being wrong in the live tier; it does not make the tier right.

---

## 9. Dormancy

### 9.1 The rule

At each review, for each family below Statistically supported, two numbers:

```
PP_f = Pr( f enters Statistically supported at some review on or before T_end | data so far )
p^F_f = Φ( (y^F_f − θ_min) / s^F_f )
```

`PP_f` is the **forecast**. It is computed by simulating the family's future forward record from the posterior to
`T_end` and applying section 8.2, under each of S0-S5. `PP_f^max` is the largest of the six. The draws come from
the closed-form posterior of section 7.1 (a grid node, then a component, then a normal).

`p^F_f` is the **family's own forward record**: the one-sided p-value of the hypothesis "the edge of `f` is at
least `θ_min`", that is, a one-sided test of the record against an edge of 0.25. `y^F_f` and `s^F_f` are the
forward sample Sharpe ratio of `P_f` and its standard error (section 7.1) and `Φ` is the standard normal
distribution function. It uses the family's forward returns and nothing else: no prior, no other family, no
reserve result. It is defined once the family has at least 252 forward days; before that it is 1.

| | rule |
|---|---|
| **Become dormant** | `PP_f^max < 0.05` **and** `p^F_f < 0.05`, both at two consecutive reviews |
| **Reactivate** | `PP_f^max ≥ 0.15` **or** `p^F_f ≥ 0.15` at any review, or on Ethan's recorded request |
| **While dormant** | no review write-up, no adaptive variants, no tier evaluation other than the reactivation check. The family's data **stay in the model** of section 7 |

With `programme.end` unset (the default), `T_end` is undefined and no family becomes dormant. At a review with no
forecast (no later review before `T_end`, or a review at which the model is "not computed", section 7.2(c)) no
family becomes dormant either, and the count of consecutive reviews is left as it is; a dormant family can still
be reactivated there by its forward record.

> **In plain English.** A family is put aside only when two things are true at two reviews running. The model
> sees almost no chance that it will reach the supported tier in the time left. And its own live record, read
> with nothing else, is too poor for a family whose edge is `θ_min`: a record that poor would turn up less than
> one time in twenty. If either stops being true by a clear margin, the family comes back.
>
> **Problem the second condition solves** (a pre-adoption change; change 5 at the top). In 3.0 the forecast
> decided alone. In the pilot of this draft that retired 11% to 18% of the families that **had** an edge (the
> bound is 10%). The run records showed why. The forecast asks whether the family will reach a tier, not
> whether it has an edge, and for most families with a real edge the answer is no: the tier needs the most
> cautious of six models to say 0.80, one of which asks about an edge that has been halving every three years.
> And the forecast is drawn from a posterior that leans on the other families: where edges are rare the model
> is rightly almost sure that any one family has none, and the few that have are forecast with the rest. Of the
> 152 families with an edge that the rule retired, nine in ten had a forecast of exactly 0.00, and it stayed
> 0.00 when their true edge was put in place of the posterior draws; their own forward estimates had a median
> of 0.28 to 0.58 and were below `θ_min` at the 0.05 level for 0% to 6% of them. "Cannot reach the tier in
> time" and "the model expects nothing of it" are reasons to stop writing about a family; neither is evidence
> that it has no edge.
>
> **What the second condition guarantees.** The criterion the rule must meet is stated for a family that has an
> edge (SIM_PREREG V7), so the rule needs an error that is controlled for such a family, whatever the other
> families are. `p^F_f` is that: if the edge of `f` is exactly `θ_min`, then `p^F_f < 0.05` at a given review
> with probability 0.05, and less with a larger edge. Dormancy also needs the forecast and a second review, so
> it is rarer still. The same number is the posterior probability of `θ_f ≥ θ_min` under a flat prior on the
> family's own forward record: the rule asks the model that pools every family and the reading that pools
> none, and puts a family aside only when both agree.
>
> **Why not the model's own probability of an edge.** Until Ethan's decision of 2026-11-13 this draft held
> `Π_f^max < 0.05` as the second condition: the most hopeful of the six models' probabilities of an edge. It
> retires more families, so it saves more attention, and at the simulation's four review dates it was inside
> the bound. But `Π_f` is calibrated over **all** families: among families given 0.05, about 5% have an edge.
> That bounds the share of edges among the retired, not the share of the edges that are retired, and the second
> is the first divided by how rare edges are. With a review every year, on the same fits, it retired 2 of 42,
> 10 of 140, 5 of 944 and 7 of 123 families with an edge (two of the four upper ends above 0.10), where the
> forward record retired 0, 0, 0 and 2 (`results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`, section 3).
> Production reviews every quarter.
>
> **Assumes.** For `p^F_f`: that the standard error of the forward Sharpe ratio is right (the bootstrap of
> section 5.2) and that a year of forward days is enough for a normal approximation. For the forecast: the
> model of section 7 and a declared approximation (each model's posterior is updated by the simulated future
> record as a normal observation, not refitted), which makes the forecast too low for a family the model has
> shrunk hard. Under this rule that error can only let the first condition hold more often; it cannot make a
> family dormant, because the second condition does not use the model.
>
> **How it fails.** (1) **It retires few families, and that is arithmetic.** An edge of 0 and an edge of
> `θ_min = 0.25` differ by a quarter of a Sharpe ratio, and the standard error of a forward Sharpe ratio after
> `T` years is about `1/√T`. A family with no edge has `p^F < 0.05` with probability about 0.10 after two
> years, 0.13 after four and 0.20 after ten, so most families with no edge are never dormant and the attention
> dormancy saves is small: on the pilot's fits 1% to 5% of the families with no edge were dormant at the end
> and 97% to 99% of the reviews were still written at four review dates, 6% to 20% and 88% to 97% with yearly
> reviews. Ten years of returns cannot tell an edge of 0 from an edge of 0.25; a rule that retires more does it
> on the model's word about the other families, and retires real edges with the rest, which is what 3.0's rule
> did. (2) **The 0.05 is per review, not per life.** Over many reviews a family whose edge is exactly `θ_min`
> is dormant at some time more often than one time in twenty. Reactivation limits the harm, and the criterion
> counts a family dormant at the end or for more than half its forward life. (3) A family whose edge appears
> late has a poor early record and can be put aside on it; it comes back only when its whole record has
> recovered (section 9.3). How soon that is has not been measured: it is what held-out scenario H09 is for.
> (4) Fat tails and serial correlation make the standard error, and so `p^F`, less exact; the simulation
> measures it. (5) **The more reviews, the more chances to be retired.** "Two consecutive reviews" are three
> months with quarterly reviews and two to three years at the simulation's four dates (SIM_PREREG §2.5(c)).
> The simulation therefore tests a more patient rule than production applies, for this rule as for 3.0's.

### 9.2 The cost of continued evaluation, stated explicitly

Each quarter the ledger records, per family: compute (CPU-hours), data spend (US dollars), and attention (minutes
of review by a person or an agent). Continuing costs **no statistical allowance**: a family's share `γ^F_i` was set
at enrolment, and a family that is never rejected takes nothing from the others.

A family is **cheap** if recording it costs at most US$1 a month in data, at most one CPU-minute a day, and needs
no minute-frequency or newly purchased data.

- **Cheap families: forward recording never stops**, dormant or not. Their test process keeps running.
- Other families may stop being recorded while dormant. The decision is written to the ledger before the first
  unrecorded period. Their test process is frozen: it bets nothing during the gap.

### 9.3 Reactivation

- **The evidence clock is never reset.** The test process continues from the wealth it had, which may be below 1.
  The enrolment number `i` and share `γ^F_i` do not change.
- If recording had stopped, the gap is reconstructed where possible and shown, flagged "reconstructed, no
  evidential weight"; the process bets from the first period after reactivation.
- **Nothing is reported "since reactivation".** Every figure for a family covers its whole life from freeze,
  including the dormant period.

> **In plain English.** When the chance that a family will ever make it becomes very small, we stop spending
> attention on it, but keep recording it if that is nearly free. If it wakes up, its old record comes with it.
>
> **Problem it solves.** Attention is the scarce resource; and a family revived only after a good run, and
> reported from the revival, would be a selected record.
>
> **Assumes.** The model's forecast of a family's future (section 7), which is why the most optimistic of six
> models must also say "below 5%".
>
> **How it fails.** A family whose edge appears late (a regime change) is forecast as hopeless and loses
> attention. For cheap families nothing is lost but time; for costly ones the gap carries no evidence. A betting
> process frozen during a gap and resumed is still valid, since stopping and resuming were decided before the
> periods concerned.

---

## 10. Governance

1. **Versioning.** This file has a semantic version. Every batch manifest records the SHA-256 of the protocol
   version in force at its freeze.
2. **Changes apply only to batches frozen afterwards.** A batch is judged, to the end, by the version it was frozen
   under. A change is a new version with an entry in the change log below; it never edits the meaning of an
   existing batch's records.
3. **Annual re-estimation by pre-registered estimators.** Once a year, on the January review, these are
   re-estimated by the estimators written here, and the new values take effect for batches frozen afterwards:

   | quantity | estimator |
   |---|---|
   | cost model per instrument | median of recorded half-spreads and fees over the previous 12 months |
   | prior centre of `μ_ρ` | posterior median of `μ_ρ` under S0, using only families frozen at least 2 years earlier; the prior standard deviation stays 1 |
   | prior centre of `μ_A` | posterior median of `μ_A` under S0, same families |
   | `s_floor` convention, `c`, `Λ`, `γ` schedules, `α_S`, `α_F`, `θ_min` | **not re-estimated**; a change is a new major version and needs a new simulation pass |

4. **Simulation gate.** No screening rejection, within-family claim, tier or formal support is produced until the
   methods have passed SIM_PREREG.md, with SIM_PREREG_v2.md for the parts 3.1 changed. A method that fails is
   revised (a new version here) and retested; a threshold there is never weakened. If nothing passes, no
   confirmation claim is implemented.
5. **Authority.** Freezing a batch, setting the reserve fence, approving a live experiment, changing a level and
   changing this file are Ethan's (hard rule 4; ETHAN_ACTIONS.md).
6. **Corrections** to recorded results are ledger `correction` records that keep the old value and the reason.

> **Problem it solves.** Rules that can be adjusted after results are seen are not rules.
>
> **How it fails.** The annual estimators themselves were chosen today, with no Manhattan data; they may prove poor.
> They can be replaced only for later batches.

### Change log

| version | date | change |
|---|---|---|
| 3.0.0 | 2026-11-12 | first committed version (PROTOCOL_v3.md, unchanged) |
| 3.1.0 | 2026-11-12 | after the pilot on development scenarios, before any full or held-out run: (1) §5.1, §5.2, §5.4: the SPA test re-estimates the core hedge in every resample and centres at the window's least-squares intercept (pilot D11: size 0.077 at 0.05); (2) §7, §9.1, Appendix B: an analytic normal-normal hierarchical model on a fixed grid replaces the sampled model, which stays as an optional check that decides nothing (the sampled model could not be run: of the order of 50,000 CPU-hours); (3) §5.3, §7.3: the zero evidential weight of the adaptive channel on the reserve cites pilot D09b and is enforced in code; (4) §5.1, Appendix C: wording only, no rule changed (ETHAN_ACTIONS item 14). Details and the reasons this is not tuning to held-out results: "What changed from 3.0.0, and why" at the top |
| 3.1.0, revised before adoption | 2026-11-12 | a pre-adoption change of the draft, after its pilot rerun and before any full or held-out run, **superseded by the next row before adoption**: (5, first form) §9.1: a family becomes dormant when `PP_f^max < 0.05` **and** `Π_f^max < 0.05` at two consecutive reviews with at least 252 forward days each, and is reactivated when either reaches 0.15; before, the forecast `PP_f^max` alone decided. Motivated by the pilot rerun (`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`): premature elimination 0.167 (0.045 to 0.261) in D02, 0.179 (0.138 to 0.216) in D05, 0.108 (0.081 to 0.138) in D08 and 0.146 (0.092 to 0.197) in D10, against the pre-registered bound of 0.10. Diagnosis: `results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md`; the rerun under that form: `results/manhattan_sim/v2/PILOT_RERUN2_REPORT.md` |
| 3.1.0, pre-adoption change | 2026-11-13 | made to the draft before Ethan adopted it, and before any full or held-out run, on Ethan's decision (ETHAN_ACTIONS item 22): (5, final form) §9.1, Appendix B (and one sentence of §7.2(e)): a family becomes dormant only if, at the same two consecutive reviews, the forecast `PP_f^max` is below 0.05 **and** a one-sided test of its own forward record against an edge of `θ_min = 0.25` rejects at 0.05 (`p^F_f < 0.05`, with at least 252 forward days); it is reactivated when either is at or above 0.15. The second condition replaces the `Π_f^max` of the row above; §9.2 and §9.3 are 3.0's word for word again. The two were measured side by side on the same fits (`results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`). No threshold, metric or scenario of the simulation pre-registration is changed: M8, its bound of 0.10 and the HB scenarios are as they were |

---

## Appendix A. Proofs

Throughout, a null unit's e-value `E` satisfies `E[E] ≤ 1`, `R_T` is the total number of rejections at time `T`, and
`1/0` terms are read as zero when there are no rejections.

**A.1 Screening candidate (ii).** If family `f` of batch `b` is rejected, then
`E_f ≥ n_b / (α γ_b (R_{<b} + k_b))`, that is `1 ≤ α γ_b (R_{<b} + k_b) E_f / n_b`. Also
`R_{<b} + k_b = R_{≤b} ≤ R_T` for every `T ≥ b`. Hence

```
FDP_T = Σ_b Σ_{null f in b} 1{f rejected} / R_T  ≤  Σ_b Σ_{null f in b} α γ_b E_f / n_b
FDR_T = E[FDP_T]  ≤  α Σ_b γ_b · ( number of nulls in b ) / n_b  ≤  α Σ_b γ_b  ≤  α.
```

Only `E[E_f] ≤ 1` for nulls was used, so any dependence is allowed. `γ_b` and `n_b` must be fixed without reference
to the e-values (or, more generally, each null e-value must have conditional expectation at most 1 given the
information that fixed them).

**A.2 Forward e-LOND with thresholds that use all rejections so far.** Let null family `i` be rejected at time
`τ_i`. By the rule, `1 ≤ α γ_i (R(τ_i−) + k_{τ_i}) W_{i,τ_i}`, and `R(τ_i−) + k_{τ_i} = R(τ_i) ≤ R_T`. So
`1{i rejected by T} / R_T ≤ α γ_i W_{i, τ_i ∧ T}`. `τ_i` is a stopping time for the shared filtration, because the
rule at `t` uses only wealths and guards known at `t`. For a non-negative supermartingale started at 1,
`E[W_{i, τ_i ∧ T}] ≤ 1` (optional stopping). A family's enrolment number, and so its `γ_i`, is known at
enrolment, before its test process starts, so `γ_i` can be taken outside the expectation conditional on that time;
distinct families have distinct numbers, so their `γ_i` sum to at most 1. Summing over nulls,
`FDR_T ≤ α Σ_i γ_i ≤ α`. The guard only changes which stopping time `τ_i` is.

**A.3 Naming components inside rejected families.** Let `S` be the set of rejected families, `R = |S|`, and let
`V_i = 1` if some null component of family `i` is named. A named null component `j` of family `i` has
`1 ≤ α γ_i R(t) W_j / (H_i + 1)` at its naming time, and `R(t) ≤ R`. So

```
(1/R) Σ_{i in S} V_i  ≤  Σ_i Σ_{null j in i} α γ_i W_j / (H_i + 1),     with expectation  ≤  α Σ_i γ_i  ≤  α.
```

## Appendix B. Constants fixed in v3.0, and the grid fixed in v3.1

| constant | value | where |
|---|---|---|
| `α_S`, `α_F`, `α_G` | 0.20, 0.05, 0.05 | §4, §6.8, §6.3 |
| `N_S`, `N_F` | 120 batches, 300 enrolments | §4.2, §6.8 |
| `L_β`, minimum history, `κ` | 756, 252, `0.1 · trace(C'C)/K` | §2.2 |
| scale half-life, `s_floor` | 60 periods, half the declared target volatility | §2.4 |
| test period; `c` | one calendar week (a month for monthly data); 6 weekly, 4 monthly | §6.1, §6.3 |
| variance-ratio rule | `VR̂ > 1.25` over 252 days (monthly: `ρ̂_1 > 0.20` over 60 months): no bet | §6.7 |
| guard start `m` | 52 weeks | §6.3 |
| `Λ` | `0.9/c · 2^(−j)`, `j = 0..5`, equal weights | §6.4 |
| settlement lag | 7 calendar days | §6.6 |
| `B` | 999, then 9,999 if `p ≤ 0.10`, then 99,999 if `p ≤ 0.01` | §5.2 |
| `L_min`, `L_max` | 5 daily (2 monthly); `⌈min(3√n, n/3)⌉` | §5.2 |
| `θ_min`, `w`, `s_R`, `γ_R` | 0.25, 0.10, 1.5, 4 | §7, §8.4 |
| spread of the narrow component of `η_f` | 0.02 (3.0.0's narrow component of `δ_h`) | §7.1 |
| tier thresholds | 0.40 / 0.20; 0.80 / 0.60 / 0.40; 126, 252, 504 days | §8 |
| dormancy thresholds | 0.05 (twice) / 0.15 | §9 |

The grid on which section 7 integrates the hyperparameters, fixed in v3.1 (no node depends on data):

| hyperparameter | nodes | weight of a node |
|---|---|---|
| `μ_A` | 121: from −0.9 to 1.5 in steps of 0.02 (the prior mean ± 4 prior standard deviations) | its prior density |
| `τ_A` | 10: the quantiles of half-Normal(0.5) at 0.05, 0.15, ..., 0.95 (0.031 to 0.980) | equal |
| `ψ` | 3: the quantiles of 1 + half-Normal(0.25) at 1/6, 1/2, 5/6 (1.053, 1.169, 1.346); S4: the single value 1.5 | equal |
| `ρ_m` | 20: the midpoints 0.025, 0.075, ..., 0.975 of cells of width 0.05 | the prior mass of the cell, given `(μ_ρ, σ_ρ)` |
| `μ_ρ` | 9: the quantiles of its prior at 1/18, 3/18, ..., 17/18 | equal |
| `σ_ρ` | 5: the quantiles of half-Normal(1) at 0.1, 0.3, ..., 0.9 | equal |
| `ν` | 7: the Gauss-Hermite nodes 0, ±1.154, ±2.367, ±3.750 (one node, 0, when `r = 0`) | the Gauss-Hermite weights |

| constant | value | where |
|---|---|---|
| grid gate | at most 1% of the posterior mass of `μ_A` on its two end nodes | §7.2(c) |
| pruning | a `(μ_A, τ_A, ψ)` node whose reserve-only posterior is below `e^−18` of the largest is skipped; a family's posterior is summed over the grid cells that hold at least `10^−10` of the posterior weight in some class | §7.2(c) |
| `r` | measured, not fixed: at most 0.9 | §7.1 |
| draws for the dormancy forecast | 200 per family and model | §9.1 |
| dormancy: the family's own forward record | `p^F_f = Φ((y^F_f − θ_min)/s^F_f)` below 0.05 at the same two reviews as the forecast; reactivation at 0.15 (the thresholds of 3.0, applied to both numbers); at least 252 forward days | §9.1 |

## Appendix C. References

- Bahadur, R. R. and Savage, L. J. (1956). The nonexistence of certain statistical procedures in nonparametric
  problems. *Annals of Mathematical Statistics* 27.
- Benjamini, Y. and Bogomolov, M. (2014). Selective inference on multiple families of hypotheses. *JRSS B* 76.
- Hansen, P. R. (2005). A test for superior predictive ability. *Journal of Business and Economic Statistics* 23.
- Li, J. and Ji, L. (2005). Adjusting multiple testing in multilocus analyses using the eigenvalues of a
  correlation matrix. *Heredity* 95.
- Patton, A., Politis, D. N. and White, H. (2009). Correction to "Automatic block-length selection for the
  dependent bootstrap". *Econometric Reviews* 28.
- Politis, D. N. and Romano, J. P. (1994). The stationary bootstrap. *JASA* 89.
- Politis, D. N. and White, H. (2004). Automatic block-length selection for the dependent bootstrap. *Econometric
  Reviews* 23.
- Romano, J. P. and Wolf, M. (2005). Stepwise multiple testing as formalized data snooping. *Econometrica* 73.
- Vovk, V. and Wang, R. (2021). E-values: calibration, combination and applications. *Annals of Statistics* 49.
- Wang, R. and Ramdas, A. (2022). False discovery rate control with e-values. *JRSS B* 84.
- Waudby-Smith, I., Arbour, D., Sinha, R., Kennedy, E. H. and Ramdas, A. (2024). Time-uniform central limit theory
  and asymptotic confidence sequences. *Annals of Statistics* 52.
- Waudby-Smith, I. and Ramdas, A. (2024). Estimating means of bounded random variables by betting. *JRSS B* 86.
- White, H. (2000). A reality check for data snooping. *Econometrica* 68.
- Xu, Z. and Ramdas, A. (2024). Online multiple testing with e-values. *AISTATS*.
- Zrnic, T., Jiang, D., Ramdas, A. and Jordan, M. (2020). The power of batching in multiple hypothesis testing.
  *AISTATS*.

The update equations of §4.3, the e-LOND levels of §4.4 and §6.8, the selection-adjusted procedure of §5.5 and the
confidence sequence of §6.3 were checked against the papers' arXiv sources (1910.04968, 2311.06412, 1106.3670,
2103.06476) on 2026-11-12. Hansen's recentring and variance estimate (Hansen 2005, §2.1 p. 368 and §3 p. 371-372),
the Politis-White rule (Politis and White 2004, eq. (8)-(9) p. 58, footnote c p. 59; Patton, Politis and White
2009, p. 373, Table 1 p. 374) and the Li-Ji formula (Li and Ji 2005, eq. (5) p. 222) were checked against the
published articles on 2026-11-12, before they were coded; the table of what was read is in MANHATTAN_PROGRESS.md,
"Phase C entry criteria". No formula differed.

The hedge re-estimation of §5.1 and the closed form of §7.1 are derived here, not quoted from a paper. The
closed form is the normal-normal conjugate update applied twice. The simulation is what tests both.
