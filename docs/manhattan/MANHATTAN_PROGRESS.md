# Manhattan progress

Updated 2026-11-12 (session "6M Manhattan C: dormancy fix before adoption", branch `build/manhattan`, pull
request #56) and 2026-11-13 (session "6M Manhattan C: dormancy fix and statistical checks", the same branch an
hour later: it changed neither draft and added the statistical checks of "Milestone C: statistical checks"; then
session "10M Manhattan C: final pre-adoption changes", which made the changes Ethan decided on and is described
in "Milestone C: final pre-adoption changes (session 10M)").
A new session starts here:
read this file, then the document for the milestone it is about to work on. Earlier sessions: "2M Manhattan A-B"
(audit, architecture, Protocol v3, simulation pre-registration), "3M Manhattan rename + PR #45 fixes", "4M
Manhattan C: simulation lab" (which also did milestone D) and "5M Manhattan C: protocol 3.1 and prereg v2
(hedge-aware SPA, analytic hierarchical model)" (which also did milestone E).

**Two protocol versions exist.** [PROTOCOL_v3.md](PROTOCOL_v3.md) 3.0.0 and [SIM_PREREG.md](SIM_PREREG.md) 1.0 are
frozen and protected. [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md) 3.1.0 and [SIM_PREREG_v2.md](SIM_PREREG_v2.md) 2.0 are
**drafts written by session 5M for Ethan to adopt** (ETHAN_ACTIONS item 19): they repair the two things the pilot
showed must be repaired before a full run. **Sessions 6M and 10M revised both drafts before adoption**: the pilot
of the draft itself showed that the dormancy rule retired too many families that have an edge. Session 6M added
a low probability of an edge under the most hopeful model as a second condition; on 2026-11-13 Ethan chose the
other candidate, a test of the family's own forward record, and session 10M put it in ("Milestone C: final
pre-adoption changes (session 10M)", which lists every pre-adoption change of that session). Until Ethan adopts
them the drafts are in force for nothing.

## Milestones

From session 4M on, the milestone letters are the ones in Ethan's standing brief (the table below). Phases D-I of
the first version of this file were cut differently; the last column maps them. A milestone is **done** only when
its acceptance criteria are written here first and its tests then pass, run as hard rule 15 requires.

| milestone | what | status | where | was (old phase) |
|---|---|---|---|---|
| **A** | Audit of what exists | **done** | [AUDIT.md](AUDIT.md) | A |
| **B** | Architecture, Protocol v3, simulation pre-registration | **done** (PR #48 merged 2026-11-12). Drafts of the next versions, for Ethan to adopt: Protocol 3.1.0 and pre-registration version 2 (session 5M) | [ARCHITECTURE.md](ARCHITECTURE.md), [PROTOCOL_v3.md](PROTOCOL_v3.md) 3.0.0, [SIM_PREREG.md](SIM_PREREG.md) 1.0; drafts [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md), [SIM_PREREG_v2.md](SIM_PREREG_v2.md) | B |
| **C** | Simulation lab: both screening candidates, SPA, forward e-process, hierarchical model, dormancy; the pre-registered experiments, with confidence intervals | **code and tests done; pilot run, rerun for the two repaired methods, and rerun again for the dormancy rule revised before adoption; NOT passed** (full run packaged for the iMac and now includes the model-fitting half; needs ETHAN_ACTIONS item 19; held-out worlds not coded): see "Milestone C: state (session 6M)" and "(session 5M)" | `manhattan/stats/`, `manhattan/sim/`, `results/manhattan_sim/` | C, and the reference half of old H |
| **D** | Registry, freezing workflow, generator templates, critic, ledger | **done against its criteria** (33 tests); not yet usable for a real batch: needs ETHAN_ACTIONS items 2, 3, 7 and a timestamp client: see "Milestone D: state" | `manhattan/spec.py`, `ledger.py`, `roles.py`, `generate/`, `freeze.py` | old D and F |
| **E** | Point-in-time data layer and daily/event backtester; reproduce time-series momentum and cross-asset carry before anything new | **engine done and tested; reproduction done on public currency data; the futures half is blocked** (ETHAN_ACTIONS item 20); core factors proposed, not adopted (item 10): see "Milestone E: state" | `manhattan/engine/`, `manhattan/factors/`, `results/manhattan_engine/` | old E |
| **F** | Historical screening and forward evaluation, wired only to methods that passed C | not started; needs a passed C and items 1, 2 | production wiring of `manhattan/stats/` | old H |
| **G** | Reports with full denominators and labels | not started | report pages | new |
| **H** | iMac runner package (launchd, checkpoints, heartbeat, watchdog, recovery) | not started; needs item 4 to install. The simulation's own run script (lock, checkpoints, heartbeat, status check, launchd template) exists and is a first piece: [SIM_RUNBOOK.md](SIM_RUNBOOK.md) | `manhattan/runner/` | old G |
| **I** | End-to-end synthetic cycle proving no outcome leaks to the generator | not started | end-to-end test on synthetic specs | old I |

## Phase C entry criteria

Phase C code is not started until each of these holds, and each is recorded here (or in the Phase C report) with
what was checked:

1. `python -m manhattan.prereg verify` passes on the branch the work starts from.
2. **Formulas verified against the primary papers before they are coded**, each recorded with the paper, the
   equation or section number **and the page**:
   - Hansen's SPA recentring constant (the threshold that decides which benchmark-relative means are recentred):
     Hansen (2005), "A Test for Superior Predictive Ability", *Journal of Business & Economic Statistics* 23(4).
   - The Politis-White automatic block-length rule: Politis and White (2004), *Econometric Reviews* 23(1), with the
     correction in Patton, Politis and White (2009), *Econometric Reviews* 28(4).
   - The Li-Ji effective number of tests: Li and Ji (2005), *Heredity* 95(3).

   A secondary source, a textbook summary or memory does not count. If a formula differs from PROTOCOL_v3.md, the
   protocol is corrected as a new version with a change-log entry **before** any code uses it.
3. ETHAN_ACTIONS item 13 is done (this PR merged, and the go-ahead and place to run given).

**Status on 2026-11-12 (session 4M): all three hold.** (1) `python -m manhattan.prereg verify` printed
`pre-registrations ok` (exit 0) on `build/manhattan` at `892bd8b` (main fast-forwarded in; no protected path
touched), and the full suite gave 804 passed, 127 skipped, exit 0 before any change. (2) The table below. (3) PR #48
is merged and Ethan's brief for session 4M is the go-ahead: this session runs what it can and packages the rest for
the iMac.

Each formula was read in the published article itself (the publisher's typeset pages), not in a summary.

| formula | primary source read | equation / section | page | matches PROTOCOL_v3.md? | date |
|---|---|---|---|---|---|
| Hansen SPA recentring | Hansen (2005), *JBES* 23(4), 365-380, DOI 10.1198/073500105000000063 | §2.1 recommendation 2: `μ̂ᶜ_k = d̄_k · 1{ n^(1/2) d̄_k / ω̂_k ≤ −√(2 log log n) }`; §3: `Z*_{k,b,t} = d*_{k,b,t} − g_i(d̄_k)`, `g_l(x) = max(0,x)`, `g_c(x) = x · 1{ x ≥ −√((ω̂²_k/n) 2 log log n) }`, `g_u(x) = x`; `T* = max{0, max_k n^(1/2) Z̄*_{k,b}/ω̂_k}` | §2.1: p. 368; §3: p. 372 (pages counted from the article's first page, 365: the copy read carries no printed folio) | **yes** (§5.1: the threshold, the three `g`, the statistic and the resampled statistic are identical) | 2026-11-12 |
| Hansen's variance estimate and kernel | same | §3: `ω̂²_k = γ̂_{0,k} + 2 Σ_{i=1}^{n−1} κ(n,i) γ̂_{i,k}`, `γ̂_{i,k} = n⁻¹ Σ_{j=1}^{n−i} (d_{k,j} − d̄_k)(d_{k,j+i} − d̄_k)`, `κ(n,i) = ((n−i)/n)(1−q)^i + (i/n)(1−q)^(n−i)`; index rule `τ_{b,1} = ⌈n u⌉`, new uniform draw with probability `q`, else the next index, wrapping `n → 1` | p. 371-372 | **yes** (§5.1, §5.2) | 2026-11-12 |
| Politis-White block length | Politis and White (2004), *Econometric Reviews* 23(1), 53-70 | flat-top window `λ(t)` = 1 on [0, 1/2], `2(1−|t|)` on [1/2, 1], 0 beyond; eq. (8): `Ĝ = Σ_{k=−M}^{M} λ(k/M) |k| R̂(k)`, `R̂(k) = N⁻¹ Σ_{i=1}^{N−|k|} (X_i − X̄)(X_{i+|k|} − X̄)`, `ĝ(0) = Σ_{k=−M}^{M} λ(k/M) R̂(k)`; eq. (9): `b̂_opt,SB = (2Ĝ²/D̂_SB)^(1/3) N^(1/3)`; footnote c: `m̂` = the smallest positive integer with `|ρ̂(m̂+k)| < c √(log₁₀N / N)` for `k = 1..K_N`, `c = 2`, `K_N = max(5, √log₁₀N)`; `M = 2m̂` | eq. (8)-(9): p. 58; footnote c and `M = 2m̂`: p. 59; the algorithm: p. 62 | **yes** (§5.2 cites the rule and does not restate it) | 2026-11-12 |
| the 2009 correction | Patton, Politis and White (2009), *Econometric Reviews* 28(4), 372-375, DOI 10.1080/07474930802459016 | corrections 1 and 4: `D_SB = 2g²(0)`, `D̂_SB = 2ĝ²(0)` (replacing eq. (8)'s `4ĝ²(0) + (2/π)∫(1+cos w)ĝ²(w)dw`); correction 5: eq. (9) then stands. Corrected Table 1 (p. 374) gives the theoretical `b_opt,SB` for an AR(1): 11.47 and 18.20 (ρ = 0.7, N = 200 and 800), 2.01 and 3.20 (ρ = 0.1), 5.66 and 8.99 (ρ = −0.4) | p. 373; Table 1: p. 374 | **yes**; the six table values are reproduced by `(2ρ/(1−ρ²))^(2/3) N^(1/3)` and are used as a unit test | 2026-11-12 |
| Li-Ji effective number of tests | Li and Ji (2005), *Heredity* 95(3), 221-227, DOI 10.1038/sj.hdy.6800717 | eq. (5): `M_eff = Σ_{i=1}^{M} f(|λ_i|)`, `f(x) = I(x ≥ 1) + (x − ⌊x⌋)`, `x ≥ 0` | p. 222 (worked values in Table 1, p. 223: 5.99 and 4.01, used as a unit test) | **yes** (§5.6, identical) | 2026-11-12 |

**No formula differs from the protocol, so no new protocol version was needed.** Four things the check turned up,
none a formula error, recorded so that nobody rediscovers them:

1. **The p-value's finite-`B` convention is the protocol's, not Hansen's.** Hansen (p. 372) writes
   `p̂ = Σ_b 1{T*_b > T} / B`. Protocol §5.1 writes `(1 + #{T*_b ≥ T}) / (B + 1)`. The protocol's is never smaller
   (it counts ties and adds one), so it can only make the test more cautious; the code follows the protocol. The
   sentence in §5.1 "This is the 'consistent' p-value of Hansen (2005)" is true of the recentring, not of that
   convention (ETHAN_ACTIONS item 14: a wording fix for a future 3.0.1, Ethan's because the file is protected).
2. **"the latter being White's reality check" (§5.1) is loose.** `g_u(x) = x` gives the least-favourable null of
   the reality check, but applied to Hansen's studentised statistic (his `SPA_u`), not White's unstudentised one
   (his `RC_u`). Same item 14.
3. **`L_max = ⌈min(3√n, n/3)⌉` is not in either paper.** It is the cap used in Patton's reference code, which the
   2009 correction points to; in Manhattan it is the protocol's own constant (§5.2, Appendix B). Likewise the papers
   do not say what to do when no `m̂` exists within the lags examined; the code's convention is written in
   `manhattan/stats/blocklen.py`.
4. **Logarithms.** Hansen's `2 log log n` is the law of the iterated logarithm, so natural logarithms (protocol:
   `ln ln n`). Politis and White's `log N` in footnote c is base 10, stated there.

## Milestone C: acceptance criteria

Written on 2026-11-12 **before** any test or simulation code of milestone C (commit order shows it). The status
column is filled in as the tests pass; "Milestone C: state" below says what was run.

**Layout decision.** The statistical methods live once, in `manhattan/stats/` (pure functions of arrays, no market
data, no file access). `manhattan/sim/` holds the simulated world, the pipeline, the metrics, the run log and the
reports, and imports the methods. The simulation therefore tests the code that production (milestone F) will call,
not a copy of it.

| id | criterion (each is a test or a recorded run) | status |
|---|---|---|
| C-01 | **Entry criteria** met and recorded above | **met** (table above) |
| C-02 | **Seeds and log.** The master seed is the first 8 bytes of SIM_PREREG.md's SHA-256; every stream is a `SeedSequence` child keyed by (branch, scenario, size, replication, stream); the same key gives identical arrays and a different replication different ones. Every run, including failed and abandoned ones, appends a record to `results/manhattan_sim/runs.jsonl` with time, commit, protocol hash, pre-registration hash, scenario, size, held-out set, replications, seeds and status. A held-out scenario is **refused** unless a confirmation flag is given and the commit carries a `manhattan-sim-confirm-<k>` tag; a refusal is itself logged | **met**: `tests/test_manhattan_sim_world.py` (seeds, log, refusal), `test_manhattan_sim_pipeline.py` (runner) |
| C-03 | **Schedule.** `γ(j; 120)` reproduces Protocol §4.2 (`Σ = 16.5945`, `γ_1 = 0.01715`, `γ_50 = 0.00706`, `γ_100 = 0.00519`, `γ_120 = 0.00478`), `γ(·; 300)` reproduces §6.8, and the sequence sums to 1 | **met**: `tests/test_manhattan_stats.py` |
| C-04 | **Simulated world** (SIM_PREREG §2). Weights sum to 1; a null variant's mean is 0 within Monte Carlo error; the three correlations are 0.60, 0.30 and 0.05 under the defaults (and each scenario's stated ones); every noise distribution has variance 1; D06's volatility has mean square 1; D07's AR(1) terms have variance 1 and the stated coefficient; programme sizes, windows and freeze dates are as §2.1-2.2; truth labels follow §2.4; no parameter is drawn from the model's priors | **met** for the development scenarios: `tests/test_manhattan_sim_world.py`. Held-out worlds are not coded |
| C-05 | **Block length.** The flat-top window and `m̂` rule follow Politis-White p. 58-59; the estimator recovers the six theoretical values of the corrected Table 1 on long AR(1) series; the protocol's `L = min(max(Q90, H_f, L_min), L_max)` | **met**: `tests/test_manhattan_stats.py` |
| C-06 | **SPA.** `κ(n,i)` is Hansen's; `ω̂²` equals the variance of the stationary-bootstrap mean (checked against a brute-force bootstrap); the block-sum bootstrap gives the same means as gathering every index; `p_l ≤ p_c ≤ p_u`; a variant below `−ω̂√(2 ln ln n / n)` is not recentred and the others are; `T = 0` gives `p = 1`; the p-value is `(1 + #{T* ≥ T})/(B+1)` with the 999 → 9,999 rule on one stream; under an i.i.d. null the rejection rate at 0.05 and 0.20 is within Monte Carlo error of nominal | **met**: `tests/test_manhattan_stats.py` |
| C-07 | **Romano-Wolf.** Step 1's critical value is the stated order statistic of the maximum; a variant with a large mean is named; with all nulls the family-wise rate at 0.05 is within Monte Carlo error; later steps use only the remaining set | **met**: `tests/test_manhattan_stats.py` |
| C-08 | **Li-Ji.** Reproduces the paper's Table 1 (5.99 and 4.01); identity matrix gives `M`; identical tests give 1 | **met**: `tests/test_manhattan_stats.py` |
| C-09 | **Screening candidate (i).** One batch equals Benjamini-Hochberg at `α_S γ_1`; `α_b` follows §4.3 with the cap; the paper's running estimate `Σ α_s n_s/(n_s + R_{<s})` never exceeds `α_S`; a hand-worked example | **met**: `tests/test_manhattan_stats.py` |
| C-10 | **Screening candidate (ii).** One family per batch equals e-LOND; one batch with `γ = 1` equals e-BH; exactly `k_b` families meet the final threshold; a hand-worked example; the Benjamini-Bogomolov admission levels of §5.5 for both candidates | **met**: `tests/test_manhattan_stats.py` |
| C-11 | **Betting process.** `Λ` is §6.4's grid; `Y = max(Z, −c)`; wealth is the equal-weight mean of six fixed-fraction products and is never negative; scale, bet and variance-ratio decision for a week are unchanged when that week or any later data are altered; `VR̂` matches a hand calculation and a week with `VR̂ > 1.25` leaves wealth unchanged; the guard matches a hand calculation of §6.3 and needs 52 weeks; tail count and tail debt; under a fair-coin null the share of paths ever reaching 20 is at most 0.05 within Monte Carlo error | **met**: `tests/test_manhattan_stats.py` (weekly test periods only; monthly periods and the gap rule of §6.6 are not coded) |
| C-12 | **Forward e-LOND.** A single family is rejected exactly when `W ≥ 1/(α_F γ_1)`; a rejection lowers every other bar at once (`k_t` step-up); rejections are permanent; a failed guard blocks; family numbers follow enrolment order | **met**: `tests/test_manhattan_stats.py` |
| C-13 | **Hierarchical model.** The six models differ only as §7.2(e) says; on data drawn from a stated truth with many families the posterior of the retention centre and of `μ_A` covers the truth; `Π_f` rises with a family's forward evidence and falls with a contradicting one; a fit that fails `R̂ ≤ 1.01`, effective sample size ≥ 400 or has divergences is reported "model not converged" and changes no tier | **partly met for the sampled model of 3.0**: the six models, the sampling coordinates, the response of `Π_f` to forward evidence and the convergence gate are tested (`tests/test_manhattan_hier.py`); recovery on a large synthetic set was not tested (cost), and at HB size it is too expensive to run (ETHAN_ACTIONS item 15). **Met for the analytic model of the 3.1 draft** (C-20): recovery of three class retentions and of `μ_A` on 600 families is a test |
| C-14 | **Tiers and dormancy.** Entry, exit and the two-consecutive-reviews rules of §8.1-8.2 on scripted sequences; dormant only after `PP^max < 0.05` twice; reactivated at `≥ 0.15`; never dormant when `T_end` is unset; a dormant cheap family keeps recording and its data stay in the model | **met**: `tests/test_manhattan_tiers.py` |
| C-15 | **Metrics and intervals.** M1-M11 on hand-made replications; `mean ± 1.96 sd/√R`; the 2,000-resample bootstrap over whole replications for ratios; the fewer-than-200-observations rule; every threshold of §5 read from one table that a test compares with SIM_PREREG.md's text | **met** for M1-M9 and M11: `tests/test_manhattan_sim_pipeline.py`, `tests/test_manhattan_hier.py`. M10 belongs to held-out scenario H08 and is not coded |
| C-16 | **V10(a).** In D09a and D09b the designated blind p-values and e-values are bit-for-bit identical with and without the adaptive channel | **met**: bit-for-bit identical in the tests and on 154 families at STD (`results/manhattan_sim/v10a.json`) |
| C-17 | **Experiments.** Every development scenario is run at every size §3.1 lists, with both screening candidates, at the pre-registered replication count; **or** as a pilot labelled as such, with the shortfall recorded and the full run packaged for the iMac. The report gives every metric with its interval, the threshold and pass, fail or "pilot: not decided", every deviation from SIM_PREREG.md and the list of earlier runs. No held-out scenario is run before a tagged confirmation run | **pilot only**: every STD and LONG development run was made as a labelled pilot (12 and 6 replications against 2,000); session 5M reran D11 and piloted the nine hedged twins and the five HB scenarios under the 3.1 draft (`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`). The full run, HB included, is packaged for the iMac. **Not met** until that run is made |
| C-18 | **Hygiene** (session 4M; rechecked by session 5M: the same six files are unchanged, `python -m nightshift.protected` on every path changed against main prints nothing, `python -m manhattan.prereg verify` and `python -m manhattan.prereg_v2 verify` pass, `claims.enabled` is false). SIM_PREREG.md, its hash record, PROTOCOL_v3.md, `manhattan/prereg.py`, `tests/test_manhattan_prereg.py` and `config/manhattan.yaml` are unchanged (`python -m nightshift.protected` on the changed paths, and `python -m manhattan.prereg verify`); `claims.enabled` stays false; the full suite passes with the runner's own exit code read | **met**: `python -m nightshift.protected` on every path changed against main printed nothing and exited 0; no file of `em_macro`, `ledger`, `lab`, `nightshift`, `janus`, `.claude`, `.github` or `config` is changed; `python -m manhattan.prereg verify` prints `pre-registrations ok`; `claims.enabled` is false; full suite 953 passed, 128 skipped, exit 0 |

| C-19 | **Hedge-aware SPA (Protocol 3.1 §5.1).** The resampled hedged means equal those obtained by building each pseudo-series and hedging it with `manhattan.stats.hedge` (one and several factors; long, short and no history; with a hedge cost); the identity sequence gives the live hedged mean; the centre is the window's least-squares intercept; the statistic and `ω̂` are the live ones; the random stream is consumed as by the 3.0 test; **with nothing to hedge the result is the 3.0 test's, bit for bit** (V13); on a hedge that leaks a factor's mean the 3.0 test over-rejects and this one does not | **met**: `tests/test_manhattan_spa_hedged.py` (16) |
| C-20 | **Analytic hierarchical model (Protocol 3.1 §7).** The six models and the grid are those of §7.2(e) and Appendix B (code against the protocol's text); one family's closed form equals brute-force integration (likelihood, mean, `Π`); a whole fit equals an independent sum over the grid written from the formulas; nothing in a fit is random and a model's numbers do not depend on which others are fitted with it; `Π_f` follows forward evidence; shrinkage is the only adjustment for selection; the wide component lets a conflicting family keep its data; a level shared by all forward estimates is not read as an edge when luck is shared; the grid gate refuses data outside the grid; three class retentions and `μ_A` are recovered on 600 families not drawn from the priors, with intervals that cover | **met**: `tests/test_manhattan_hier_analytic.py` (21) |
| C-21 | **Zero evidential weight of the adaptive channel on the reserve (Protocol 3.1 §5.3, §7.3; V14).** The weight comes from `manhattan.ledger.evidential_weight` and cannot be passed to the model; no reserve number of an adaptive-channel family changes any output of any of the six models, to the last bit, while the same change to a blind family does; an adaptive family equals a family with no reserve term; its forward record counts; the protocol quotes the D09b number that is on file | **met**: `tests/test_manhattan_adaptive_weight.py` (7) |
| C-22 | **Version 2 beside version 1.** PROTOCOL_v3.md, SIM_PREREG.md and its record are byte for byte what they were; the version 2 record pins SIM_PREREG_v2.md and PROTOCOL_v3.1.md and a one-character change to either fails; version 1's code files and code hash are unchanged, so its pilot records still count; only D11, the twins and the HB scenarios go to the new code, and only with `--prereg v2`; version 2's records are kept apart and its runs log both hashes; every threshold of version 1 is the object version 2 uses; the numbers in SIM_PREREG_v2.md are the code's; 3.1 keeps every constant and every untouched section of 3.0 word for word and makes the two wording fixes; the CODEOWNERS lines of ETHAN_ACTIONS item 19 protect exactly the five new files | **met**: `tests/test_manhattan_prereg_v2.py` (3), `tests/test_manhattan_v2.py` (15) |
| C-23 | **Pilot rerun.** D11 and a hedged twin of every other development scenario in which V3 is required, and the five HB scenarios, run as labelled pilots through the runner from a clean checkout of one commit, with every metric, interval and threshold reported and every development experiment noted in the run log. No held-out scenario run | **met as a pilot**: `results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`, `DEVELOPMENT_NOTES.md` |

| C-24 | **Dormancy under Protocol 3.1 §9.1 (the forward-record rule; rewritten by session 10M when Ethan chose it, ETHAN_ACTIONS item 22).** `p^F` is the one-sided p-value of the forward record against an edge of 0.25, and 1 with no estimate, no standard error or fewer than 252 forward days; dormant only when both the forecast `PP^max` and `p^F` are below 0.05 at two consecutive reviews; a hopeless forecast alone, or a poor record alone, is not enough; reactivated when either reaches 0.15, or by Ethan, and a reactivated family needs two more reviews; a review with no forecast retires nobody, leaves the count as it is and can still wake a family; while dormant only the reactivation check and formal support; never while Statistically supported; a review the model did not compute changes no tier and no count; the tiers are 3.0's whatever the record says, and with a record that always speaks against the family the rule is exactly 3.0's; a family whose edge is exactly `θ_min` ends dormant less than 5% of the time whatever the forecast says; no number is new; version 1's `tiers.py` is not edited and its code hashes are those on its records; every HB record carries the rule's id; the protocol's text is the rule the code applies | **met**: `tests/test_manhattan_dormancy.py` (11, brought from branch `claude/epic-mayer-kfhpsh` at `1124fe7` with the module), `tests/test_manhattan_v2.py` (the code lists, the text of §9.1 against 3.0's, §9.2 and §9.3 word for word 3.0's, SIM_PREREG_v2's description). Until session 10M this row described the rule with `Π^max` (10 tests), which the draft held from 2026-11-12 to 2026-11-13 |
| C-25 | **Diagnosis before the change.** The pilot's replications of the four scenarios replayed with the pilot's code, every replay equal to its run record on the counts behind M8; each candidate cause changed alone on the same fits; the result recorded with the variants that were tried and not chosen, and noted in the run log | **met**: `results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md`; notes `note-6M-01` to `note-6M-04` in `results/manhattan_sim/runs.jsonl` |
| C-26 | **Pilot rerun under the revised rule.** The five HB scenarios through the runner from a clean checkout of one commit, 12 replications each, every metric with its interval and threshold; premature elimination, the reviews written and the families dormant reported; who reaches Statistically supported by true Sharpe ratio reported from the records. No held-out scenario run; no threshold, metric or scenario of the pre-registration changed | **met as a pilot**: `results/manhattan_sim/v2/PILOT_RERUN2_REPORT.md` (the first rerun, `PILOT_RERUN_REPORT.md`, and its summary are kept as they were) |
| C-27 | **Intervals with the replication as the unit.** For every interval in the pilot reports: the same estimate, the delete-one-replication jackknife standard error of the same estimator, a Student-t quantile on `R − 1` degrees of freedom; where no replication had an event, the exact bound over replications. For a mean of per-replication values the jackknife is `sd/√R` exactly and the interval is wider by exactly `t/1.96`; for a pooled ratio it is the linearised cluster-robust error; thresholds and the small-groups rule are those of the reports; the estimate is never touched | **met**: `tests/test_manhattan_cluster_ci.py` (5); `results/manhattan_sim/v2/CLUSTERED_INTERVALS.md` |
| C-28 | **The forward test's estimand.** The simulated processes have the Sharpe ratio they are given, crashes included; the weekly inputs are `manhattan.stats.eprocess`'s own; the proposed tail check on hand-made records; skipping by a rule that looks back keeps null wealth inside Ville's bound and dropping weeks after the fact breaks it. No held-out scenario, no pipeline, no pre-registered metric | **met**: `tests/test_manhattan_estimand_study.py` (4); `results/manhattan_sim/v2/ESTIMAND_AND_TAIL_RISK.md` |
| C-29 | **Timing.** A slice with one run of each kind of code (version 1 at STD and LONG, D11, a twin, HB), each alone and then with every core busy; wall-clock, CPU time and peak memory per job; it writes no replication record and no run-log record | **met**: `tests/test_manhattan_benchmark.py` (2); `results/manhattan_sim/v2/benchmark.json`, `COMPUTE_OPTIONS.md` |
| C-30 | **A second look at the dormancy rule that edits nothing.** The branch's HB pipeline imported unchanged and stepped four ways on the same fits; the branch's path equal to the pilot of record, and the 3.0 path to session 5M's pilot, replication by replication; the alternative rule outside the package | **met as development experiments**: 48 of 48 and 48 of 48 (`results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`); the yearly replay gives the first session's yearly figures to the family |

C-19 to C-23 were written by session 5M with the work they describe, not before it: the session's brief fixed what
was to be built, and these rows record what the tests then had to show. C-24 to C-26 were written by session 6M
in the same way, and C-27 to C-30 by the second session of 2026-11-13; the dormancy tests were written before the protocol's text was changed, and the one that reads
the text failed until it was.

**What "done" means for C.** C is done when C-01 to C-23 hold **and** the confirmation run of SIM_PREREG §8 has been
made at the full replication counts. A pilot does not finish C and enables no claim.

## Milestone D: acceptance criteria

Written on 2026-11-12 before any code or test of milestone D. Sources: ARCHITECTURE.md sections 3 to 6.

| id | criterion (each is a test) | status |
|---|---|---|
| D-01 | **Canonical form and IDs** (`manhattan/spec.py`). Canonical bytes are JSON with sorted keys, UTF-8 in NFC, no insignificant white space, integers as integers, every other number as a decimal string, dates as `YYYY-MM-DD`, list order kept unless the schema marks the list as a set. The spec hash is the SHA-256 of those bytes and equals `lab.book.sha256` of the stored file. IDs are `AF-`, `AH-`, `AV-`, `AX-` plus the first 16 hex characters; the full hash is stored beside each. Key order, white space and equivalent number spellings do not change a hash; any change of content does | **met**: `tests/test_manhattan_registry.py` |
| D-02 | **Immutable links.** A hypothesis spec contains its family's full hash, a variant its hypothesis's, an executable its variant's: changing a parent changes every descendant's ID. Variants are the grid's points, enumerated in a fixed order at freeze; a grid that is not declared, not finite or above the cap is refused. Two different specs with the same 16-character ID are detected through the full hash | **met**: `tests/test_manhattan_registry.py` |
| D-03 | **Schema.** A family needs mechanism text, mechanism class, predicted sign, counterparty, kill condition and tail exposure; a hypothesis needs domain, data sources with publication lags, signal definition, the primary executable binding and the grid. A missing or empty field is refused with the field named. A later domain is a new family that names its `parent_family`; an adaptive variant is a new variant record with `channel: adaptive` | **met**: `tests/test_manhattan_registry.py` |
| D-04 | **Ledger chain** (`manhattan/ledger.py`). Records carry `seq`, `ts_utc`, `type`, `writer`, `protocol`, `payload`, `prev_hash`, `hash`; the first `prev_hash` is 64 zeros. Verification fails on an edited, deleted, inserted or reordered line and names the first bad record; replacing the whole file is caught by comparing the head hash with an anchor kept elsewhere. Nothing is ever edited: a mistake is a `correction` record that names the record, the fields and the reason | **met**: `tests/test_manhattan_registry.py` |
| D-05 | **Rerun detection.** Key `(spec_hash, data_hash, window id)`: unseen gives `evaluation` (one look); seen with the same result gives `rerun` (the same look, counted once); seen with a different result gives `nondeterminism` and suspends the family from tier changes; the same spec on changed data is a new `evaluation` flagged `data_changed`, and the first designated result stays the result of record. An `evaluation_started` with no finish is reported. Evidential weight follows ARCHITECTURE section 6.3 | **met**: `tests/test_manhattan_registry.py` |
| D-06 | **Public index.** The index record of a run carries the Merkle root, the record count and the head hash of the full ledger and **no outcome field**; writing a summary, return or p-value into the public index is refused | **met**: `tests/test_manhattan_registry.py` |
| D-07 | **Data roles** (`manhattan/roles.py`). A date is exploration, reserve, forward or embargo from the fence in `config/manhattan.yaml`; a read of reserve dates is refused for every caller except the runner holding a verified frozen batch and its designated evaluation, and refused for everyone while `reserve.enabled` is false; forward means dated after the spec's own freeze; the embargo is the longest holding period plus one period | **met**: `tests/test_manhattan_registry.py` |
| D-08 | **Freezing workflow** (`manhattan/freeze.py`). The manifest holds the batch number, channel, template hash, generator model, every spec hash, their Merkle root, the protocol hash, the fence in force, the designated evaluations and the critic record hashes. An agent can prepare a batch (validate, hash, enumerate, manifest); it cannot freeze one while `freeze.authority` is `ethan_only`. The runner's check refuses a batch whose tag is missing or unsigned, whose manifest or any spec no longer matches its hash, or whose timestamp proof is missing | **met**: `tests/test_manhattan_registry.py` (the timestamp proof's presence is checked, not its validity: no timestamp client is installed) |
| D-09 | **Generator templates** (`manhattan/generate/`). The blind template is a versioned file with a recorded SHA-256; the blind request is built from the template and the schema only, and the builder cannot be handed results, ledger records or repository paths; generator output is parsed as data, validated against the schema, and text that looks like an instruction changes nothing. The adaptive request is built from summaries and the public index only, and everything it returns is marked `channel: adaptive` | **met**: `tests/test_manhattan_registry.py` (requests are built and replies parsed; no model is called) |
| D-10 | **Critic.** Its input is specs only: a spec bundle that carries any outcome field is refused before the critic sees it. Its output is The Opposition's JSON, validated; it can block only for look-ahead, a duplicate of T25-T26, a licensed-data leak or an undeclared grid; "weak economics" cannot block; its probability is logged | **met**: `tests/test_manhattan_registry.py` (input built and reviews checked; no critic agent exists yet) |
| D-11 | **Hygiene.** No protected path changed; nothing existing is edited (`lab`, `ledger`, `nightshift`, `em_macro` are imported only); the full suite passes with the runner's own exit code read | **met**: `python -m nightshift.protected` on every path changed against main printed nothing and exited 0; no file of `em_macro`, `ledger`, `lab`, `nightshift`, `janus`, `.claude`, `.github` or `config` is changed; `python -m manhattan.prereg verify` prints `pre-registrations ok`; `claims.enabled` is false; full suite 953 passed, 128 skipped, exit 0 |

## Milestone E: acceptance criteria

Written on 2026-11-12 by session 5M **before** any code or test of milestone E (the commit that adds this table
adds nothing else). Sources: "Exact next step" of the previous version of this file; ARCHITECTURE sections 2, 4
and 6; PROTOCOL section 2.1. Order of work, as the session's brief fixed it: the parts that need no licensed data
first (the engine, the accounting, synthetic known-answer tests), then the reproduction.

| id | criterion (each is a test or a recorded run) | status |
|---|---|---|
| E-01 | **Point-in-time store** (`manhattan/engine/pit.py`). Every value carries the period it describes and the day it became available. A read as of day `T` returns, for each period, the latest value whose availability is on or before `T`, and nothing that became available later. A revision is a second value for the same period with a later availability; it never shows before that day and never erases the earlier value. Availability is an explicit date or the period plus the source's publication lag in days (the hypothesis spec's `data_sources[*].publication_lag_days`); a source with neither is refused. The store has a SHA-256 over its content (the ledger's data hash) that changes with any value, period or availability and does not depend on insertion order | **met**: `tests/test_manhattan_engine.py` (4 tests of the store) |
| E-02 | **Every read of dated data goes through `manhattan.roles.check_read`.** The store hands out data only through a reader bound to a caller, a domain and the fence of `config/manhattan.yaml`; the engine takes a reader, never a store. A read that touches reserve, embargo or forward dates is refused for a session, so with the default configuration nothing dated after 2019-12-31 can be read | **met**: `tests/test_manhattan_engine.py` (the store has no public way to its data; the reader calls `check_read`; 2020 is refused with the repository's configuration) |
| E-03 | **Accounting** (`manhattan/engine/accounting.py`), each against a hand calculation: buy and hold reproduces the instrument's return; weights drift between trades; turnover is the absolute move from drifted to target weights; a proportional cost is charged on turnover in the period of the trade; a cash instrument is financed at its short rate for the calendar days held and an excess-return instrument is not; a missing price leaves the position at its last mark and the whole gap's return arrives when the price returns (no period is dropped); `net = gross − financing − cost` to rounding; all returns are per unit of capital | **met**: `tests/test_manhattan_engine.py` (5 hand-worked accounts) |
| E-04 | **Daily backtester** (`manhattan/engine/backtest.py`). Positions for a period are a function of what was available at the decision cut-off only: the signal is handed a view as of that day and has no other access to data. Execution lag in periods, default 1 (the next available price; Protocol §2.1). Rebalancing daily, weekly or monthly. Volatility-target sizing from returns known at the decision only. A constant signal equals buy and hold; a momentum rule on a hand-made price path gives the hand-computed positions and returns; the same inputs give the same result hash | **met**: `tests/test_manhattan_engine.py` |
| E-05 | **Event backtester** (`manhattan/engine/events.py`). One position per event, opened at the next available price after the event becomes known, held a fixed number of periods; zero return on days with no position (Protocol §1); overlapping events add; an event known late is traded late, never early; a hand-worked example | **met**: `tests/test_manhattan_engine.py` |
| E-06 | **Look-ahead test** (`manhattan/engine/lookahead.py`). For a strategy, changing every value that becomes available after a cut-off changes no position and no return decided on or before it, bit for bit, at several cut-offs. The check **fails** when any one input is shifted forward (tomorrow's value stamped as available today), for each input in turn | **met**: `tests/test_manhattan_engine.py`: clean strategies pass at four cut-offs (daily, weekly, lagged, volatility-targeted, events); the check fails for each of five inputs shifted forward one observation |
| E-07 | **Records.** An evaluation writes an `evaluation` record to a Manhattan ledger with the role `check_read` returned, the data hash, the result hash and the code version; an identical second run is a `rerun`, a different result a `nondeterminism`. An exploration-role evaluation also writes one row with `nightshift.logs.log_variant`, whose `code_ref` is the ledger record's hash, and which refuses a window ending after 2019-12-31 | **met**: `tests/test_manhattan_engine.py`, `tests/test_manhattan_factors.py`. The variant rows go to Manhattan's own log file, not to `results/exploration/log.csv` (decision 33) |
| E-08 | **Reproduction, exploration dates only** (to 2019-12-31), from data already in the repository: time-series momentum and carry, compared with published numbers and with the repository's own frozen results. Nothing new is evaluated until both reproduce. If the reproduction needs em-macro-data and the environment has no access, that is recorded in ETHAN_ACTIONS.md and the work stops there | **met for currencies; not met for futures.** On the public daily panel (six currencies, 2005 to 2019) the engine reproduces the frozen carry benchmark and the frozen T01 trend signal within tolerances fixed before the first run (`results/manhattan_engine/REPRODUCTION.md`). The published results and the repository's futures sleeves need em-macro-data; the attach was refused by the session's permissions, which is recorded as ETHAN_ACTIONS item 20, and the work stopped there |
| E-09 | **Core factors.** Daily carry, trend, value and buy-and-hold definitions are proposed for Ethan (ETHAN_ACTIONS item 10); none is adopted | **met**: [CORE_FACTORS_PROPOSAL.md](CORE_FACTORS_PROPOSAL.md); nothing adopted |
| E-10 | **Hygiene.** No protected path changed; nothing existing is edited (`em_macro`, `ledger`, `lab`, `nightshift` are imported only); no licensed data and no row derived from it in the repository; the full suite passes with the runner's own exit code read | **met**: `python -m nightshift.protected` on every path changed against main prints nothing; `em_macro`, `ledger`, `lab`, `nightshift` and `config` are untouched (two frozen modules are imported by the reproduction); the only data read are the repository's public panel and carry file, up to 2019-12-31; full suite: 1186 passed, 131 skipped, exit code 0 |

## Rename (2026-11-12)

On 2026-11-12 the project was renamed from Atlas to Manhattan (session "Manhattan rename + PR #45 fixes", branch
`build/manhattan`; it supersedes PR #45 from `build/atlas`). Directories, files, the Python package, the CLI
(`python -m manhattan.prereg`, `python -m manhattan.config`), the config file, the test file, the environment
variable (`MANHATTAN_STRICT`) and every mention in the text were renamed. The former name is kept only in this note
and in the rename test.

**SIM_PREREG.md: the only change was the name.** It was made before any simulation code existed (no
`manhattan/sim/`, no data-generating code, no simulation run, no seed drawn). Its SHA-256 was re-recorded in
`sim_prereg.sha256` in the same commit:

| file | SHA-256 before the rename | SHA-256 after the rename |
|---|---|---|
| SIM_PREREG.md | `07fb6ca2a22d01b5d18789a739c33ecea298dbe040d07108ce16df5ca035d715` (`4ea29a4`) | `e4bbcc44bebbc601b8bccc0e609131ad5185982f3047108dfaaf2fe2908c21e6` |
| PROTOCOL_v3.md (3.0.0) | `60653417d3e9ce9934ba14c05975d0de4021bb2b22260106c7508bb7454668d5` (`b2f2fa5`) | `4fbb5c72ad7214710aea7417fbf2fe131edb56f4eb83bffccac97478472f3a9f` |

- **Evidence.** `tests/test_manhattan_prereg.py::test_rename_changed_only_the_name` undoes the substitution on each
  file as it is now and checks the result against the pre-rename hash. Both match, so no other byte changed.
- **The protocol hash pinned in SIM_PREREG.md** (§ "Method under test") is the pre-rename hash, because that line
  was not edited. It names the same version 3.0.0 with identical content; the test above links the two hashes.
  PROTOCOL_v3.md keeps version 3.0.0 with no change-log entry, because only the name changed.
- **Seeds.** SIM_PREREG §9 derives the master seed and the held-out sets from "this file's SHA-256" (and the
  held-out prefix is now `manhattan-sim-heldout-`). That is the post-rename hash `e4bbcc44…`. No seed had been
  drawn under the old hash.

## Milestone C: state (session 4M, 2026-11-12)

**Implemented** (new code only; nothing existing was edited):

| where | what |
|---|---|
| `manhattan/stats/schedule.py`, `blocklen.py`, `bootstrap.py`, `spa.py`, `meff.py` | the `γ` schedule; the Politis-White block length with the 2009 correction; the joint stationary bootstrap; Hansen's SPA test (lower, consistent, upper) with the 999 → 9,999 → 99,999 rule; Romano-Wolf; Li-Ji |
| `manhattan/stats/screening.py` | **both screening candidates**: `Batch-BH^PRDS` and e-BH inside the batch at e-LOND's level, with the Benjamini-Bogomolov admission levels |
| `manhattan/stats/eprocess.py`, `elond.py` | the **forward e-process**: ex-ante scale, weekly test periods, truncation at 6, the variance-ratio rule, the six-fraction wealth, the guard, the tail record; forward e-LOND and the within-family rule |
| `manhattan/stats/hier.py`, `tiers.py` | the **hierarchical model** (six versions, NUTS, the convergence gate); Promising, Statistically supported, formal support and the **dormancy policy** with its forecast |
| `manhattan/stats/hedge.py` | the ridge core hedge of Protocol §2.2 |
| `manhattan/sim/` | the simulated world (D01-D11, P1-P4), seeds, the run log with the held-out fence, the STD/LONG pipeline, the HB pipeline, metrics M1-M9 and M11 with both kinds of interval, the resumable runner, the report |
| `scripts/manhattan_sim_run.sh`, `scripts/com.horizons.manhattan.sim.plist.template`, [SIM_RUNBOOK.md](SIM_RUNBOOK.md) | the full run, packaged for the iMac: resumable, locked, heartbeat, status check, launchd restart |

**Tested.** 150 new tests, all passing: `tests/test_manhattan_stats.py` (54: every method against a known case), `test_manhattan_sim_world.py` (24: the world, seeds, the log and the held-out refusal), `test_manhattan_sim_pipeline.py` (17: pipeline, runner, intervals, thresholds read back from SIM_PREREG.md, the run package), `test_manhattan_tiers.py` (10), `test_manhattan_hier.py` (12: 11 run by default where the sampler is installed, 1 opt-in), `test_manhattan_registry.py` (33, milestone D). Tests that depend on a hand-edited file skip inside a writer's workflow and fail everywhere else (`manhattan/testing.py`), so they cannot stop `systematic-monthly`.

**The pilot** (`results/manhattan_sim/PILOT_REPORT.md`, every metric with its interval; `runs.jsonl`). It is a
pilot: 18 STD and LONG runs, 204 replications in all against 2,000 per run. **No criterion is
decided, no method is selected, `claims.enabled` stays false.** Estimates with their 95% intervals:

| scenario (size, replications) | SPA size at 0.05 | screening FDR, (i), last batch | screening FDR, (ii) | screening power (i) | screening power (ii) | forward FDR, year 10, (i) | null wealth ever reaches 20 |
|---|---|---|---|---|---|---|---|
| D01 (STD, 12) | 0.062 (0.042 to 0.081) | 0.250 (-0.006 to 0.506) | 0.000 (0.000 to 0.000) | - | - | 0.000 (0.000 to 0.000) | 0.0037 (0.0020 to 0.0053) |
| D02 (STD, 12) | 0.046 (0.032 to 0.059) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 0.229 (0.163 to 0.295) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 0.0020 (0.0014 to 0.0026) |
| D03 (STD, 12) | 0.050 (0.041 to 0.060) | 0.072 (-0.002 to 0.147) | 0.000 (0.000 to 0.000) | 0.196 (0.146 to 0.253) | 0.003 (0.000 to 0.011) | 0.000 (0.000 to 0.000) | 0.0041 (0.0024 to 0.0058) |
| D04 (STD, 12) | 0.036 (0.008 to 0.064) | 0.070 (-0.044 to 0.185) | 0.000 (0.000 to 0.000) | 0.135 (0.077 to 0.199) | 0.004 (0.000 to 0.012) | 0.000 (0.000 to 0.000) | 0.0022 (0.0004 to 0.0041) |
| D05 (STD, 12) | 0.049 (0.038 to 0.061) | 0.024 (-0.023 to 0.070) | 0.000 (0.000 to 0.000) | 0.259 (0.196 to 0.335) | 0.035 (0.007 to 0.068) | 0.000 (0.000 to 0.000) | 0.0037 (0.0020 to 0.0054) |
| D06 (STD, 12) | 0.039 (0.028 to 0.050) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 0.164 (0.126 to 0.205) | 0.019 (0.003 to 0.040) | 0.000 (0.000 to 0.000) | 0.0029 (0.0016 to 0.0043) |
| D07a (STD, 12) | 0.060 (0.044 to 0.076) | 0.111 (-0.056 to 0.279) | 0.000 (0.000 to 0.000) | 0.129 (0.094 to 0.165) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 0.0024 (0.0012 to 0.0037) |
| D07b (STD, 12) | 0.051 (0.036 to 0.066) | 0.038 (-0.006 to 0.082) | 0.000 (0.000 to 0.000) | 0.277 (0.211 to 0.338) | 0.016 (0.000 to 0.036) | 0.000 (0.000 to 0.000) | 0.0011 (-0.0001 to 0.0023) |
| D08 (STD, 12) | 0.049 (0.035 to 0.063) | 0.026 (0.014 to 0.039) | 0.000 (0.000 to 0.000) | 0.529 (0.468 to 0.589) | 0.135 (0.086 to 0.185) | 0.000 (0.000 to 0.000) | 0.0049 (0.0013 to 0.0086) |
| D09a (STD, 12) | 0.062 (0.045 to 0.079) | 0.008 (-0.008 to 0.025) | 0.000 (0.000 to 0.000) | 0.259 (0.195 to 0.318) | 0.025 (0.004 to 0.057) | 0.000 (0.000 to 0.000) | 0.0038 (0.0023 to 0.0053) |
| D09b (STD, 12) | 0.057 (0.043 to 0.071) | 0.021 (-0.020 to 0.062) | 0.000 (0.000 to 0.000) | 0.209 (0.167 to 0.247) | 0.030 (0.008 to 0.052) | 0.000 (0.000 to 0.000) | 0.0048 (0.0019 to 0.0077) |
| D11 (STD, 12) | 0.077 (0.061 to 0.094) | 0.072 (0.007 to 0.137) | 0.000 (0.000 to 0.000) | 0.233 (0.187 to 0.283) | 0.013 (0.000 to 0.030) | 0.000 (0.000 to 0.000) | 0.0075 (0.0052 to 0.0099) |
| P1 (STD, 12) | 0.062 (0.045 to 0.080) | 0.208 (-0.016 to 0.433) | 0.000 (0.000 to 0.000) | 0.018 (0.003 to 0.035) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 0.0034 (0.0017 to 0.0051) |
| P2 (STD, 12) | 0.048 (0.038 to 0.059) | 0.088 (-0.000 to 0.177) | 0.000 (0.000 to 0.000) | 0.169 (0.119 to 0.222) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 0.0020 (0.0007 to 0.0034) |
| P3 (STD, 12) | 0.056 (0.039 to 0.074) | 0.031 (0.006 to 0.057) | 0.000 (0.000 to 0.000) | 0.720 (0.620 to 0.816) | 0.297 (0.170 to 0.418) | 0.000 (0.000 to 0.000) | 0.0044 (0.0028 to 0.0060) |
| P4 (STD, 12) | 0.048 (0.035 to 0.060) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | 1.000 (1.000 to 1.000) | 0.989 (0.978 to 1.000) | 0.000 (0.000 to 0.000) | 0.0028 (0.0014 to 0.0041) |
| D01 (LONG, 6) | 0.055 (0.039 to 0.070) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) | - | - | 0.000 (0.000 to 0.000) | 0.0040 (0.0021 to 0.0059) |
| D02 (LONG, 6) | 0.064 (0.050 to 0.078) | 0.057 (-0.015 to 0.129) | 0.000 (0.000 to 0.000) | 0.222 (0.145 to 0.312) | 0.025 (0.000 to 0.054) | 0.000 (0.000 to 0.000) | 0.0055 (0.0039 to 0.0072) |

What the pilot suggests, and no more than suggests:

- **The SPA test's size is close to nominal** in every scenario run but D11 (below), fat tails, volatility
  clustering and serial correlation included. Intervals of 12 replications are wide (the pre-registered
  tolerance needs 2,000).
- **Candidate (ii) almost never rejects** at these edge sizes, as Protocol §4.4 warned (its first bar is an
  e-value of several thousand). Screening power in the power scenarios, candidate (i) against (ii):
  P1 0.018 (0.003 to 0.035) against 0.000 (0.000 to 0.000); P2 0.169 (0.119 to 0.222) against 0.000 (0.000 to 0.000);
  P3 0.720 (0.620 to 0.816) against 0.297 (0.170 to 0.418); P4 1.000 (1.000 to 1.000) against 0.989 (0.978 to 1.000).
  If both candidates turn out eligible, the selection rule would choose (i) on a gap like that; it is not
  applied on a pilot.
- **Forward formal support is slow**, as §6.9 computed. Share of first-quarter families with an edge formally
  supported by year 10 (enrolment by candidate (i)), and median years to support: P2 0.016 (0.000 to 0.051)
  (8.4 years); P3 0.623 (0.463 to 0.758) (6.0 years); P4 1.000 (1.000 to 1.000)
  (3.7 years). The floor for P4 is 0.50 (V11).
- **Adaptive search on the reserve breaks the SPA test**, as §5.3 expected: in D09b the test recomputed on the
  full set rejects 0.344 (0.307 to 0.380) of null families at 0.05. If the full run confirms it, SPA p-values on windows
  holding adaptive variants are labelled "descriptive, not error-controlled" (V10(b), fixed in advance).
- **Serial correlation of +0.2 switches the forward test off more than half the time** (D07a: a bet in
  0.43 of weeks). That is the variance-ratio rule working; it costs power there.
- **False forward discoveries: none in any pilot replication.** Null wealth reached 20 in well under 1% of
  components (the bound is 5%).
- **Two things to watch in the full run.** (1) *The estimated hedge leaks a little* (D11): SPA size at 0.05 is
  0.077 (0.061 to 0.094), against a bound of 0.06. The ridge hedge shrinks the hedge ratio and lags a beta that
  wanders, so a core factor with a positive mean leaks into the hedged return: the failure Protocol §2.2 names.
  If 2,000 replications confirm it, V3 fails in D11 and the hedge is revised as a new protocol version.
  (2) *Candidate (i) where true edges are absent or weak*: realised screening FDR 0.250 (-0.006 to 0.506) in D01
  and 0.208 (-0.016 to 0.433) in P1. With no true discovery one false rejection makes the realised rate 1, so twelve
  replications cannot tell 0.18 from 0.25; the bound to meet is 0.22 on the interval's upper end.

**The model-fitting half (HB).** One pilot replication of D10 at HB was started with the sampler at a fifth of the default budget (200 warm-up and 200 kept draws per chain) and **stopped unfinished** after 106 minutes and 2 hours 31 minutes of CPU time; it produced no value for M7-M9. It is in the run log as a start with no end, with a note. From the cost of one gradient (about 0.8 ms with 240 families,
at least 127 steps per iteration) a replication at the default budget should cost about 4.5 CPU-hours; the
stopped run shows the truth is well over 10. For the 12 HB scenario runs that is of the order of 50,000
CPU-hours or more. **That half cannot be run as pre-registered on the iMac** (ETHAN_ACTIONS item 15).

**Failed or not met.**

1. **C is not passed.** No criterion of SIM_PREREG §5 has been evaluated at its replication count. Nothing may
   be claimed from the pilot.
2. **The hierarchical model as written does not mix** (the spike-and-slab `δ_h`: `R̂` about 3.5). Fixed by exact
   changes of sampling coordinates; the model is unchanged, but this was not foreseen by the protocol and is
   worth Ethan's eye (ETHAN_ACTIONS item 15).
3. **The model's cost and the convergence gate** (item 15): the one HB replication started was stopped
   unfinished, so M7-M9 have no value at all yet, and whether the gate is met at full size is not known.
4. **Test failures along the way, all fixed, none hidden.** (a) The first full-suite run of this session had one
   failure: a fixed 0.3 bound on one family's posterior probability, hit at 0.31; the bound was replaced by a
   comparison with the confirmed case. (b) The opt-in six-model test failed twice: a cached sampler could not
   be reused once its compiled code had been evicted (numpyro wraps the kernel again at every initialisation),
   and one run of that test then aborted inside the compiler while five heavy jobs shared four cores. The
   sampler cache was removed: every fit now builds its own sampler and releases its compiled code, and memory
   stays flat over repeated fits (measured: about 0.9 GB over 14 fits). The six-model test then passed (1 passed in 14 minutes with `MANHATTAN_SLOW_TESTS=1`).
5. **Six world tests failed on their first run** and showed two real faults before any pilot was started: the
   volatility recursion overflowed on long series (rewritten as a plain loop), and two test assumptions were
   wrong (selection in D08 also concentrates real edges; a three-year hedge window lags a wandering beta).
6. **The pilot was interrupted once** (restarted with one thread per worker); the interrupted run is in the log
   as a start with no end, and no replication was lost or repeated.

**Remaining for C, in order.**

1. Ethan: run `scripts/manhattan_sim_run.sh` on the iMac (ETHAN_ACTIONS item 16), about 5 days on 8 cores.
2. Ethan: decide item 15 (the HB half).
3. Code the held-out worlds H01-H11 from SIM_PREREG §3.2 (their parameters come from `seeds.heldout_rng(k)`),
   the gap and revision rules of Protocol §6.6 that H10 needs, and metric M10. Unit-test each world as D01-D11
   are tested. **Do not run them through the pipeline**: that is a confirmation run.
4. When every required criterion passes on the development scenarios at full count: tag
   `manhattan-sim-confirm-1` (Ethan), run the held-out set, write the confirmation report and the selection
   report (SIM_PREREG §7-9).
5. Smaller gaps: monthly test periods (`c = 4`) are not coded; sensitivity p-values at `L/2` and `2L` are not
   computed; a coverage test of the model's hyperparameters on a large synthetic set.

## Milestone C: state (session 5M, 2026-11-12)

**What this session was for.** The pilot of session 4M showed two things that had to be repaired before a full
run: the SPA test rejects too often when the core hedge is estimated (D11), and the hierarchical model cannot
be afforded. Both are repaired in **drafts** that Ethan adopts or not (ETHAN_ACTIONS item 19):
[PROTOCOL_v3.1.md](PROTOCOL_v3.1.md) and [SIM_PREREG_v2.md](SIM_PREREG_v2.md). No protected file was edited.

**Implemented** (new files beside the old; version 1's code files are byte for byte unchanged):

| where | what |
|---|---|
| `manhattan/stats/spa_hedged.py` | the SPA test with the core hedge re-estimated in every bootstrap resample by the live rule, centred at the window's least-squares intercept on the core factors (Protocol 3.1 §5.1). With nothing to hedge it returns the 3.0 test's result itself |
| `manhattan/stats/hier_analytic.py` | the analytic normal-normal hierarchical model (Protocol 3.1 §7): closed-form posteriors summed over a fixed grid, one retention parameter per mechanism class, wide normal components, one common forward shock, six sensitivity models, a grid gate in place of the convergence gate, the reserve weight computed from the channel |
| `manhattan/sim/pipeline_v2.py`, `hb_v2.py`, `criteria_v2.py`, `metrics_v2.py`, `report_v2.py` | D11 and nine hedged twins with three SPA tests side by side on the same resamples; the HB pipeline with the analytic model; version 2's additions as data; their metrics and report |
| `manhattan/sim/run.py` (edited: not a code file of any run) | `--prereg v2` sends D11, the twins and the HB scenarios to the new code and writes their records to `results/manhattan_sim/v2/`; everything else is version 1's as before |
| `manhattan/prereg_v2.py`, `docs/manhattan/sim_prereg_v2.sha256` | the hash record of the two drafts and its check |
| `scripts/manhattan_sim_run.sh`, the launchd template, [SIM_RUNBOOK.md](SIM_RUNBOOK.md) | the iMac run uses version 2 for the changed parts and now includes the HB half |

**Tested.** 62 new tests, all passing: `tests/test_manhattan_spa_hedged.py` (16), `test_manhattan_hier_analytic.py`
(21), `test_manhattan_adaptive_weight.py` (7), `test_manhattan_prereg_v2.py` (3), `test_manhattan_v2.py` (15).
The sampled model's tests are untouched and still skip where the sampler is not installed.

**The pilot rerun** (`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`, every metric with its interval; run
through the runner from clean checkouts of commits `d046e2a` (D11, twins) and `8ba5b3a` (HB)). It is a pilot:
**no criterion is decided, no method is selected, `claims.enabled` stays false.**

*The SPA test where the hedge is estimated.* Share of families with no edge rejected at the 0.05 level (the bound
on the interval's upper end is 0.06). The three tests of a row see the same resamples. A twin is a version 1
scenario with D11's hedge layer on top, drawn from that scenario's seeds.

| scenario (replications) | 3.0 test on the estimated hedge, size at 0.05 | **3.1 test (hedge re-estimated)** | oracle (true hedged returns) | 3.1 minus oracle, paired | 3.1 at 0.20 (bound 0.22) | 3.1 Romano-Wolf FWER (bound 0.06) |
|---|---|---|---|---|---|---|
| D11 (36) | 0.073 (0.063 to 0.083) | **0.047 (0.040 to 0.054)** | 0.054 (0.046 to 0.062) | -0.0071 (-0.0100 to -0.0041) | 0.196 (0.177 to 0.216) | 0.047 (0.040 to 0.054) |
| D01h (6) | 0.113 (0.070 to 0.156) | **0.062 (0.042 to 0.082)** | 0.067 (0.046 to 0.088) | -0.0049 (-0.0119 to 0.0021) | 0.242 (0.191 to 0.293) | 0.062 (0.042 to 0.081) |
| D02h (6) | 0.061 (0.046 to 0.075) | **0.040 (0.025 to 0.055)** | 0.045 (0.024 to 0.067) | -0.0050 (-0.0127 to 0.0026) | 0.168 (0.133 to 0.204) | 0.040 (0.025 to 0.054) |
| D03h (6) | 0.073 (0.057 to 0.089) | **0.047 (0.037 to 0.058)** | 0.052 (0.038 to 0.066) | -0.0047 (-0.0131 to 0.0038) | 0.202 (0.171 to 0.234) | 0.046 (0.036 to 0.056) |
| D04h (6) | 0.037 (0.002 to 0.071) | **0.025 (-0.004 to 0.054)** | 0.034 (-0.002 to 0.070) | -0.0090 (-0.0163 to -0.0017) | 0.104 (0.031 to 0.177) | 0.026 (-0.004 to 0.055) |
| D05h (6) | 0.065 (0.033 to 0.096) | **0.042 (0.026 to 0.057)** | 0.050 (0.029 to 0.071) | -0.0083 (-0.0175 to 0.0009) | 0.196 (0.147 to 0.245) | 0.042 (0.026 to 0.058) |
| D06h (6) | 0.055 (0.041 to 0.069) | **0.027 (0.022 to 0.032)** | 0.034 (0.026 to 0.041) | -0.0066 (-0.0143 to 0.0010) | 0.159 (0.139 to 0.179) | 0.027 (0.022 to 0.032) |
| D07ah (6) | 0.089 (0.048 to 0.130) | **0.054 (0.028 to 0.080)** | 0.057 (0.035 to 0.079) | -0.0034 (-0.0133 to 0.0066) | 0.216 (0.167 to 0.265) | 0.053 (0.027 to 0.079) |
| D07bh (6) | 0.063 (0.043 to 0.084) | **0.033 (0.026 to 0.041)** | 0.042 (0.032 to 0.051) | -0.0082 (-0.0125 to -0.0039) | 0.173 (0.144 to 0.202) | 0.032 (0.024 to 0.040) |
| D08h (6) | 0.091 (0.063 to 0.119) | **0.050 (0.034 to 0.065)** | 0.060 (0.041 to 0.079) | -0.0104 (-0.0183 to -0.0025) | 0.212 (0.170 to 0.253) | 0.050 (0.036 to 0.065) |

- **D11: 0.073 before, 0.047 after**, on 36 replications that include version 1's 12 (where the 3.0 test gave
  0.077, as recorded). The hedge-aware interval's upper end, 0.054, is inside the bound of 0.06; the 3.0 test's
  lower end, 0.063, is outside it.
- **In every one of the nine twins the 3.0 test is above the oracle and the 3.1 test is at or below it** (paired
  differences −0.003 to −0.010). The 3.1 test is a little conservative: it gives up some power, not validity.
- Twins have 6 replications each: their intervals are wide and several upper ends are above 0.06 for the oracle
  itself (D01h: 0.067 with the true hedged returns). That is the pilot's size, as in version 1's pilot of D01.
- The size at 0.001 (pooled) is 0.0010 (0.0004 to 0.0016) in D11 against a bound of 0.0015 on the upper end:
  not distinguishable from nominal or from the bound at this count.
- Cost: about 370 seconds a replication for D11 (the whole pipeline with three tests) and 210 to 600 for a twin.

*The analytic model.* 12 replications of each HB scenario (400 are pre-registered).

| scenario (replications) | reviews not computed | central model's calibration error, year 4 / year 10 (bound 0.10) | families with Π^min ≥ 0.80, year 10: true / all | with Π^min ≥ 0.40, year 10: true / all | premature elimination, candidate (i) (bound 0.10) | bias of the model's Sharpe ratio, Promising or higher, year 10 | of the naive estimate | seconds per replication (model part) |
|---|---|---|---|---|---|---|---|---|
| D01 (12) | 0 of 48 | 0.029 (0.026 to 0.033) / 0.019 (0.018 to 0.020) | 0 / 0 | 0 / 2 | - (0 families) | 1.35 (0.09 to 2.00) (3 obs.) | 0.53 (0.36 to 0.80) | 68 (46) |
| D02 (12) | 0 of 48 | 0.022 (0.013 to 0.029) / 0.014 (0.010 to 0.018) | 0 / 0 | 5 / 5 | 0.167 (0.045 to 0.261) (42 families) | -0.26 (-0.58 to 0.00) (11 obs.) | 0.39 (0.14 to 0.59) | 75 (51) |
| D05 (12) | 0 of 48 | 0.013 (0.005 to 0.022) / 0.005 (0.000 to 0.023) | 8 / 8 | 20 / 20 | 0.179 (0.138 to 0.216) (140 families) | -0.12 (-0.36 to 0.04) (38 obs.) | 0.41 (0.28 to 0.52) | 85 (60) |
| D08 (12) | 0 of 48 | 0.034 (0.004 to 0.067) / 0.101 (0.034 to 0.136) | 112 / 113 | 392 / 435 | 0.108 (0.081 to 0.138) (944 families) | -0.15 (-0.23 to -0.08) (659 obs.) | 0.39 (0.34 to 0.43) | 149 (105) |
| D10 (12) | 0 of 48 | 0.009 (0.001 to 0.016) / 0.004 (0.000 to 0.008) | 17 / 24 | 43 / 57 | 0.146 (0.092 to 0.197) (123 families) | 0.08 (-0.01 to 0.17) (115 obs.) | 0.97 (0.92 to 1.03) | 85 (67) |

- **It runs.** 240 reviews, 1,440 fits, none refused by the grid gate. A replication takes 68 to 149 seconds, of
  which the model (estimates, six fits at four dates, forecasts) 46 to 105; the six fits of a review take 16
  seconds on average. The sampled model did not finish one replication in 2 hours 31 minutes of CPU time.
- **Calibration of the central model: inside the bound of 0.10 everywhere except D08 at year 10**, 0.101 (0.034
  to 0.136). In D08 (each family the best of 20) about a third of families have an edge, the model's narrow
  component has to stretch to hold them, and in the middle of the scale it says too much: families given about
  0.45 have an edge 0.18 of the time, those given about 0.55, 0.29 (its top bin, 0.97, is right 0.99 of the
  time). The cause is the shape of the prior fixed in 3.0 (a tenth of the mass in a component that is too
  wide), not the closed form. If the full run confirms it, V6 fails in D08 and the posterior-based tiers stay
  off. In D10, where a family keeps all of its edge or none, the central model's top bin (0.98) is right 0.79
  of the time: one retention per class cannot say "all or nothing".
- **The cautious tier rule holds up where it can be counted.** Families with `Π^min ≥ 0.80` at year 10: 112 of
  113 have an edge in D08, 8 of 8 in D05, 17 of 24 in D10 (retention 0 or 1). Groups are below the 200
  observations a verdict needs in every scenario but D08's `Π^min ≥ 0.40` group (392 of 435).
- **In D01 (no edges) no family evaluation reached `Π^min ≥ 0.80`.**
- **The model's Sharpe ratio is not inflated by selection; the naive one is.** Bias for families Promising or
  higher at year 10: −0.15 (−0.23 to −0.08) in D08 against +0.39 for the best variant's sample Sharpe ratio;
  +0.08 (−0.01 to +0.17) in D10 against +0.97. D10's upper end is above the +0.10 bound, on 115 observations.

**Three findings to weigh before the full run.**

1. **The dormancy rule retires too many families that have an edge** (V7, bound 0.10 on the upper end): 0.167
   (0.045 to 0.261) in D02, 0.179 (0.138 to 0.216) in D05, 0.108 (0.081 to 0.138) in D08, 0.146 (0.092 to
   0.197) in D10. This is the first time the rule could be measured at all. It is not the closed form: a family
   becomes dormant when even the most hopeful of six models gives it less than a 5% chance of ever being
   Statistically supported, and that tier is nearly out of reach by construction (next point). If the full run
   confirms it, dormancy is not switched on (SIM_PREREG §8.1 rule 2); nothing else depends on it.
2. **"Statistically supported" is rare for families with a real edge**: by year 10, none in D02, 7% in D05, 13%
   in D08, 17% in D10. Entry needs `Π^min ≥ 0.80`, the smallest of six. For families with an edge the smallest
   is the decay model S5 in 43 to 67% of cases at year 10 and the inflated-standard-error model S4 in 33 to
   44%; their mean `Π^min` is 0.14 to 0.36 while the central model gives them 0.38 to 0.81. S5 says the edge
   halves every three years and asks about the edge **now**, so a family nine years old needs an edge eight
   times `θ_min` at freeze to pass. That reading of §7.2(e) is session 4M's (in `hier.py`) and is kept. Whether
   the top posterior tier should be this hard to reach is Ethan's question, and a different answer is a new
   protocol version.
3. **Shared luck needed a term of its own.** The first analytic model treated families as independent. On one
   fat-tailed development replication a market-wide shock was read as an edge shared by all 240 families
   (`results/manhattan_sim/v2/DEVELOPMENT_NOTES.md` §3). Protocol 3.1 §7.1 therefore has one common forward
   shock, sized by the measured average correlation between families' forward estimates. It is less than the
   full covariance matrix 3.0 gave its model, and §7.2(g) says what it does not cover; held-out H11 measures it.

**Development experiments** (outside the runner, each noted in the run log; numbers in `DEVELOPMENT_NOTES.md`):
where to centre the resamples (40 replications of D11: re-estimating the hedge without changing the centre
leaves the size at 0.066 to 0.070; the adopted centre gives 0.047; testing the in-window intercept itself gives
0.053); a harder hedge (factor Sharpe 0.8, exposure drift 0.4 a year: 0.097 for the 3.0 test, 0.049 for 3.1);
the model without a common shock.

**Failed or not met.**

1. **C is still not passed.** Every number above is a pilot number. D11's twins, H12 and the analytic model have
   been seen at 6 to 36 replications against 400 to 2,000.
2. **V7 and one V6 check are outside their bounds so far** (findings 1 and above). No threshold was changed.
3. **The hedge-aware test was only run with one core factor.** Several factors are covered by unit tests of the
   arithmetic (against hedging every pseudo-series directly), not by a scenario; H12 has up to four.
4. **Test failures on the way, none hidden.** First runs: 6 of 21 model tests failed (5 were wrong expected
   numbers; 1 showed that a model's result moved in the seventh decimal with the models fitted beside it, which
   was fixed: each model is now computed independently); 6 of 7 adaptive-weight tests (two mistakes in the
   tests); 1 of 16 v2 tests (the test); and one existing test (`test_heartbeat_status_and_compaction`) failed
   because version 2's replication table was a copy of version 1's instead of the same object, which was a real
   fault and was fixed. The first full-suite run of the session before a push: 1,148 passed, 131 skipped.
5. **One logged run was stopped** (HB, D05, after 8 of 12 replications) because the model's code was about to
   change; its start record has no end record and a note says why. Thirty-two HB replications of that earlier
   code stay on file and are counted in no report.
6. **A scratch script shadowed a standard-library module** and stopped one step of the session; nothing was
   written wrongly.

**Remaining for C, in order.**

1. Ethan: read and adopt the two drafts (ETHAN_ACTIONS item 19), then run `scripts/manhattan_sim_run.sh` on the
   iMac (item 16).
2. Code the held-out worlds H01 to H12 (H12 is defined in SIM_PREREG_v2 §3.2), the gap and revision rules of
   Protocol §6.6 that H10 needs, and metric M10. Unit-test each world. **Do not run them through the pipeline.**
3. When every required criterion passes on the development scenarios at full count: tag
   `manhattan-sim-confirm-1` (Ethan), run the held-out set, write the confirmation and selection reports.
4. If V7 or V6 fails at full count: the component stays off, and whether to revise the tier rules is Ethan's.
5. Smaller gaps left from session 4M: monthly test periods; sensitivity p-values at `L/2` and `2L`. The
   quarterly review cadence, which version 1 reduced to four dates for the sampler's cost, is now affordable
   and could be restored by amendment.

## Milestone C: state (session 6M, 2026-11-12)

**What this session was for.** The pilot rerun of the 3.1 draft (session 5M) left three things outside or beside
their marks: the dormancy rule retired too many families that have an edge (V7), D08's calibration error sat on
its bound (V6), and Statistically supported was rarely reached. This session's brief: diagnose and repair the
first on principled grounds before the draft is adopted, without touching the metric, its bound, the scenarios
or any threshold; diagnose the second and repair it only if the repair is general; report the third for Ethan's
decision, changing nothing. Main was merged into the branch first.

**The dormancy rule (Protocol 3.1 §9.1, change 5 at the top of the protocol).**

- *Diagnosis* (`results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md`, part 1). The pilot's 48 replications of D02,
  D05, D08 and D10 were replayed with the pilot's code, keeping every family; all 48 equal their run records on
  the counts behind M8. Among the families the rule could reach it retired 27% to 49% of those with an edge.
  For 84% to 100% of them the forecast `PP^max` was exactly zero, after 2.8 to 7 forward years, with a positive
  forward record in 56% to 100% of cases; in D08 the central model gave them a median probability of an edge of
  0.61. None would have reached the tier by year 10. **The forecast was right about the tier and the wrong
  reason to retire a family**: Statistically supported needs `Π^min ≥ 0.80`, the most cautious of six models,
  so "will not reach the tier in time" is true of most families that have an edge. Of the five candidate causes
  in the brief: the cut-offs, the minimum forward evidence and the review frequency are not the cause (changed
  alone, none brings all four scenarios inside the bound); the model's early estimates contribute where edges
  are rare; the cause is the assumption set of the forecast, in the sense of the event it is scored against.
- *Revision.* Become dormant: `PP^max < 0.05` **and** `Π^max < 0.05` at two consecutive reviews, each with at
  least 252 forward days. Reactivate: `PP^max ≥ 0.15` **or** `Π^max ≥ 0.15`, or Ethan. It is what §7.2(e)
  already said ("dormancy uses `Π^max`") and §9.1 did not carry out. No number is new (0.05, 0.15, 252 days and
  two reviews are all in 3.0), the forecast stays as a condition, and the revised rule never retires a family
  the old rule keeps. `manhattan/stats/dormancy.py` (new; `tiers.py`, a code file of version 1's records, is
  untouched).
- *Not changed:* M8's definition, its bound of 0.10, the scenarios, the replication counts, every threshold of
  SIM_PREREG and SIM_PREREG_v2, the forecast, the tiers.

**The rerun under the revised rule** (`results/manhattan_sim/v2/PILOT_RERUN2_REPORT.md`: the five HB scenarios,
12 replications each, through the runner from a clean checkout of commit `9b1f068`, code `630059032fd6e5b8`; the
first rerun's report and summary are kept as they were). It is a pilot: **no criterion is decided.**

| scenario | families with a true edge | premature elimination, 3.0's rule (first rerun) | **revised rule** (bound 0.10 on the upper end) | families dormant at the end, of 240: before / after | no-edge families dormant at the end: before / after | reviews written per replication, of 560: before / after |
|---|---|---|---|---|---|---|
| D01 | 0 | - | - | 87.1 / 33.8 | 0.36 / 0.14 | not replayed / 518 |
| D02 | 42 | 0.167 (0.045 to 0.261) | **0.000 (0.000 to 0.000)**, 0 of 42 | 85.6 / 32.6 | 0.36 / 0.14 | 438 / 518 |
| D05 | 140 | 0.179 (0.138 to 0.216) | **0.014 (0.000 to 0.032)**, 2 of 140 | 86.7 / 31.9 | 0.37 / 0.14 | 437 / 520 |
| D08 | 944 | 0.108 (0.081 to 0.138) | **0.002 (0.000 to 0.007)**, 2 of 944 | 62.9 / 4.3 | 0.34 / 0.03 | 474 / 554 |
| D10 | 123 | 0.146 (0.092 to 0.197) | **0.008 (0.000 to 0.029)**, 1 of 123 | 88.3 / 45.3 | 0.38 / 0.20 | 432 / 501 |

- All four are inside the bound so far. "0.000 (0.000 to 0.000)" in D02 is none of 42 families, not a rate of
  zero.
- **What it costs.** Attention: about a sixth more reviews (16% to 19%), because one family in seven is dormant
  at the end instead of one in three (one in fifty in D08). Compute: nothing measurable (65 to 143 seconds a
  replication against 68 to 149; the forecast was already made for every family). The iMac estimate is
  unchanged: about 1,740 CPU-hours for the whole development run, of which the HB scenarios about 47.
- Nothing else in the report moved: the model is the same, and no retired family would have reached the tier.

**A caution: the four review dates flatter every rule** (diagnosis part 3; a development experiment, not the
pre-registered pipeline). Production reviews quarterly; the simulation steps the tiers at years 2, 4, 7 and 10.
The same 48 worlds with **yearly** reviews:

| rule, yearly reviews | D02 | D05 | D08 | D10 | no-edge families dormant at the end |
|---|---|---|---|---|---|
| 3.0's rule (the forecast alone) | 0.714 (0.595 to 0.841) | 0.579 (0.488 to 0.659) | 0.453 (0.406 to 0.503) | 0.431 (0.375 to 0.491) | 0.78 to 0.81 |
| **the revised rule** | **0.048 (0.000 to 0.129)**, 2 of 42 | **0.071 (0.038 to 0.106)**, 10 of 140 | **0.005 (0.000 to 0.015)**, 5 of 944 | **0.057 (0.020 to 0.098)**, 7 of 123 | 0.40 to 0.52 (0.06 in D08) |
| revised, with `Π^max < 0.02` (not adopted) | 0.024 (0.000 to 0.065) | 0.021 (0.000 to 0.043) | 0.001 (0.000 to 0.003) | 0.008 (0.000 to 0.026) | 0.20 to 0.34 (0.02 in D08) |

More reviews do not repair 3.0's rule: they let it reach every family, and it then retires about half of those
with an edge. The revised rule cuts that about tenfold, **but with yearly reviews it is near the bound, not far
inside it**: two of the four upper ends are above 0.10. The 24 families it retires have a small true edge (three
quarters between 0.26 and 0.49) and an unlucky start (a forward estimate about one and a half standard errors
below the truth); nothing in their record separates them from the families with no edge. V7 as pre-registered
is measured at four dates and is what the pilot of record reports; whether to test it at the cadence production
uses is ETHAN_ACTIONS item 21.

**D08's calibration error (diagnosis part 2): documented as a known limitation, model not changed.** The error
(0.101 (0.034 to 0.136) at year 10, bound 0.10) is in the middle of the scale: families given about 0.45 had an
edge 18% of the time. From the same estimates and standard errors, a plain one-hump normal prior with the
population's own mean and variance makes the same error (0.102), and a prior with the population's true
two-group shape does not (0.009). So the cause is the shape of the prior (D08 has a third of its families with
an edge and two thirds at exactly zero), not the estimates, their standard errors, the retention, the common
shock or the grid. The repair would be a prior in two groups with a learned share: another model, which turns
two constants fixed in 3.0 into learned ones and, built on these scenarios, would be fitted to their convention
that a family with no edge has a mean of exactly zero. Stated in Protocol 3.1 §7.2(d). **If the full run
confirms it, V6 fails in D08 and the posterior-based tiers stay off** until a later version changes the prior
(ETHAN_ACTIONS item 21).

**Who reaches Statistically supported (for Ethan's decision on the tier's bar; nothing changed).**

Share of the families with a true edge, frozen before the date, that hold or have held the tier, by **true
hedged Sharpe ratio** of the family portfolio. Years 4, 6 and 10 need a review at year 6, which the
pre-registered pipeline does not have, so this table is from the yearly-review experiment (all four scenarios
pooled; 95% interval; families). The pilot of record's own table (years 2, 4, 7, 10, by scenario) is in
`PILOT_RERUN2_REPORT.md`; diagnosis part 4 has both, by scenario and by years of forward record.

| true hedged Sharpe ratio | by year 4 | by year 6 | by year 10 |
|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 76 | 0.00 (0.00 to 0.00), 117 | 0.01 (0.00 to 0.03), 193 |
| 0.5 to 0.75 | 0.00 (0.00 to 0.00), 88 | 0.01 (0.00 to 0.03), 149 | 0.02 (0.00 to 0.05), 250 |
| 0.75 to 1 | 0.00 (0.00 to 0.00), 150 | 0.01 (0.00 to 0.04), 222 | 0.07 (0.02 to 0.13), 351 |
| 1 to 1.5 | 0.09 (0.04 to 0.13), 167 | 0.16 (0.09 to 0.22), 244 | 0.29 (0.20 to 0.37), 403 |
| 1.5 and above | 0.27 (0.12 to 0.44), 22 | 0.58 (0.39 to 0.79), 31 | 0.71 (0.54 to 0.90), 52 |
| all with a true edge | 0.04 (0.02 to 0.06), 503 | 0.08 (0.05 to 0.11), 763 | 0.15 (0.10 to 0.20), 1,249 |

Below a true Sharpe ratio of 0.75 the tier is not reached in ten years; between 1 and 1.5, three families in
ten; at 1.5 and above, seven in ten. Where edges are rare (D02) none of 42 families reaches it, the seven above
1 included. At the four pre-registered dates the figures are a few points lower (D08 by year 10: 0.13 overall;
0.24 and 0.58 in the top two bands). 944 of the 1,249 families are D08's.

**The hash record (`docs/manhattan/sim_prereg_v2.sha256`), re-recorded because both drafts were edited.**

| file | SHA-256 before (session 5M's draft) | SHA-256 now (as revised before adoption) |
|---|---|---|
| `docs/manhattan/SIM_PREREG_v2.md` | `677073309c0914ded0a6d39cc7ee0b8dcbcca855b2de21022a88639a522d7161` | `77496b2f4cb785cb8d49258701fdd6f66f4164d3f2394d6af29af92e31754ca4` |
| `docs/manhattan/PROTOCOL_v3.1.md` | `40ad6532b2929a9acdcec0da98dcb0186cd6e0e477a2307e93ac1b5088e9f2dd` | `9fdc8b07838c94f139b6dd686eb5189fb250e2de58da7b67ac1f45f19a1f0046` |

- `python -m manhattan.prereg_v2 verify` prints `pre-registrations ok (v1 and v2)` on the new record. Version
  1's record and PROTOCOL_v3.md are byte for byte what they were.
- What changed in SIM_PREREG_v2.md: its header, the sentence on which protocol sections are identical, row 4 of
  the table in section 1, the reading "Dormancy rule" in section 2(f), two reported-only rows in section 4 and
  one clause in section 5. No threshold, metric, scenario or replication count.
- Runs made before the edit name the old hashes: session 5M's pilots of D11, the twins and the HB scenarios.
  The reports say so in their headers. D11's and the twins' records still count (their code is unchanged);
  the HB records of the old rule are on file and counted in no current report.
- Held-out scenario H12's values are drawn from SIM_PREREG_v2.md's hash, so they are different values now. None
  had been drawn: H12 is not coded.

**Development experiments** (outside the runner; notes `note-6M-01` to `note-6M-04` in the run log; numbers in
`DORMANCY_DIAGNOSIS.md`): the replay of the pilot's 48 replications with per-family values and the variants of
the rule scored on them; other definitions of the forecast's event; three posteriors on D08's estimates; the
same worlds with yearly reviews.

**Failed or not met.**

1. **C is still not passed.** Every number above is from 12 replications against 400.
2. **D08's calibration check is still outside its bound** and was not repaired (above).
3. **The revised rule was measured at the simulation's four review dates**, where "two consecutive reviews" are
   two to three years apart. Production reviews quarterly. With yearly reviews (a development experiment) its
   rate is 0.5% to 7%, with two upper ends above 0.10; quarterly reviews were not run.
4. **Test failures on the way, none pushed.** The first run of the new dormancy tests had one failure by
   design (the test that reads §9.1 was written before the text). The first full-suite run after the code
   change had one failure, in this session's own addition to `test_the_runner_keeps_v2_records_apart_and_logs_the_hashes`:
   the report had been changed to print one line for a scenario in which no family has an edge and no longer
   kept that scenario in its summary; the summary entry was restored. 1345 passed, 132 skipped, exit code 1 on
   that run; the cause was found before anything was pushed.
5. **The first nine replications of the yearly experiment ran while the working tree held uncommitted edits**
   (the code they used is the code of commit `9b1f068`); the experiment was stopped once to give the pilot of
   record the machine and resumed afterwards. No replication was lost or counted twice.
6. **The background command that ran the first full-suite check ended with `tail`**, so its own exit status was
   0 while the suite's was 1. The suite's exit code was written to the log by `echo "exit=$?"` on the line after
   pytest and read from there, as hard rule 15 requires; the wrapper's status was never used.

**Remaining for C, in order.**

1. Ethan: read and adopt the drafts (ETHAN_ACTIONS item 19), weigh item 21, then run
   `scripts/manhattan_sim_run.sh` on the iMac (item 16).
2. Code the held-out worlds H01 to H12, the gap and revision rules of Protocol §6.6 that H10 needs, and metric
   M10. Unit-test each world. **Do not run them through the pipeline.**
3. When every required criterion passes on the development scenarios at full count: tag
   `manhattan-sim-confirm-1` (Ethan), run the held-out set, write the confirmation and selection reports.
4. If V6 fails in D08 at full count: the posterior-based tiers stay off; a prior in two groups is the candidate
   for a later version.
5. Smaller gaps left from sessions 4M and 5M: monthly test periods; sensitivity p-values at `L/2` and `2L`; the
   review dates of the HB runs (item 21).

## Milestone C: statistical checks (second session of 2026-11-13: "6M Manhattan C: dormancy fix and statistical checks")

**Two sessions, one branch.** This session was started about an hour after "6M Manhattan C: dormancy fix before
adoption" with a brief that repeated that session's three items (the dormancy rule, D08's calibration, who
reaches the supported tier) and added four (intervals with the replication as the unit, the forward test's
estimand, the cost of the full run, the hash log). It found the other's commits when its own first push was
refused. **It then kept the first session's revision as the branch's and pushed nothing over it**: it did not
edit PROTOCOL_v3.1.md, SIM_PREREG_v2.md, the hash record, `manhattan/stats/dormancy.py`, the HB pipeline, the
first session's tests, reports or replication records. Everything below is added beside them. What it had done
on the three shared items before finding the overlap is kept where it adds something (a second diagnosis that
agrees; an alternative rule; diagnostics the first session's records do not hold) and is otherwise on the branch
`claude/epic-mayer-kfhpsh` (commit `1124fe7`: a complete alternative revision of §9.1 with its code, tests and
re-hash, full suite passed, merged nowhere).

**The hash record: unchanged by this session.** `docs/manhattan/sim_prereg_v2.sha256` is the first session's
(table above: `77496b2f…` for SIM_PREREG_v2.md and `9fdc8b07…` for PROTOCOL_v3.1.md, from `67707330…` and
`40ad6532…`). This session edited neither draft on `build/manhattan`, so there is no third pair of hashes on the
branch; `python -m manhattan.prereg_v2 verify` prints `pre-registrations ok (v1 and v2)`. (On
`claude/epic-mayer-kfhpsh` the alternative revision has its own record, `925d7a5b71745df137226829b67196f06000c165fc59134667e04783e85b33aa`
and `43f60398e25355ea0b972abc8f4c624beb80c888c87dd449cc5557bfba6f2474`; it is in force nowhere.)

**1. The dormancy rule: a second diagnosis that agrees, the diagnostics, and an alternative
(`results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md`).**

- *The same cause, found separately.* This session traced session 5M's 48 pilot replications on its own
  instrumented runs (all 48 reproduce the recorded counts). Of the 152 families with an edge that the rule of 3.0
  retired, the forecast was exactly 0.00 for 139 and never above 0.045; the cut-offs, the minimum forward record
  and the wake-up level are not the cause. Two things it adds to `DORMANCY_DIAGNOSIS.md`: the forecast stays at
  zero when the family's **true** edge replaces the posterior draws (the forecast updates each model's present
  posterior as a normal prior without refitting, and a posterior of standard deviation 0.13 to 0.22 weighs as
  much as 20 to 60 years of forward data); and the retired families' **own forward records were not against
  them** (the one-sided p-value of "the edge is at least 0.25" had a median of 0.52 to 0.75 and was below 0.05
  for 2 of the 152).
- *The diagnostics the brief asked for, for the rule on the branch*, at the four pre-registered dates and with
  yearly reviews. The four-date replay reproduces the pilot of record's counts in 48 of 48 replications (and
  session 5M's pilot, for 3.0's rule, in 48 of 48); the yearly replay gives the first session's yearly figures
  to the family (2 of 42, 10 of 140, 5 of 944, 7 of 123):

| the draft's rule | D02, four dates | D05, four dates | D08, four dates | D10, four dates | D02, yearly | D05, yearly | D08, yearly | D10, yearly |
|---|---|---|---|---|---|---|---|---|
| families with a true edge | 42 | 140 | 944 | 123 | 42 | 140 | 944 | 123 |
| premature elimination (M8) | 0.000 (0.000 to 0.000) | 0.014 (0.000 to 0.032) | 0.002 (0.000 to 0.007) | 0.008 (0.000 to 0.029) | 0.048 (0.000 to 0.129) | 0.071 (0.040 to 0.106) | 0.005 (0.000 to 0.015) | 0.057 (0.018 to 0.097) |
| share ever made dormant | 0.000 | 0.014 | 0.002 | 0.008 | 0.048 | 0.079 | 0.006 | 0.065 |
| years dormant, of those ever dormant: mean / longest | - | 3.0 / 3 | 3.0 / 3 | 3.0 / 3 | 2.0 / 3 | 3.4 / 7 | 3.3 / 5 | 3.5 / 6 |
| reactivated / dormant again at the end | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 0 | 1 / 0 | 1 / 0 |
| enter the tier with no dormancy / kept out by dormancy / delayed by it | 0 / 0 / 0 | 10 / 0 / 0 | 126 / 0 / 0 | 23 / 0 / 0 | 0 / 0 / 0 | 10 / 0 / 0 | 152 / 0 / 0 | 22 / 0 / 0 |
| the same under 3.0's rule | 0 / 0 / 0 | 10 / 0 / 0 | 126 / 0 / 0 | 23 / 0 / 0 | 0 / 0 / 0 | 10 / 0 / 0 | 152 / 1 / 0 | 22 / 0 / 0 |
| families with no edge dormant at the end (3.0's rule) | 0.14 (0.36) | 0.14 (0.37) | 0.03 (0.34) | 0.20 (0.38) | 0.45 (0.80) | 0.40 (0.81) | 0.06 (0.78) | 0.52 (0.81) |
| share of family-reviews written (3.0's rule) | 0.93 (0.78) | 0.93 (0.78) | 0.99 (0.85) | 0.90 (0.77) | 0.72 (0.42) | 0.75 (0.43) | 0.96 (0.55) | 0.66 (0.42) |

  Ever dormant and retired are nearly the same families: a family with an edge that is put aside almost never
  comes back (none of 5 at the four dates, 3 of 27 with yearly reviews), so reactivation does little and what
  protects such a family is not being put aside. No family that would enter Statistically supported is kept out
  or delayed by the branch's rule at either calendar; even 3.0's rule kept out one, with yearly reviews. What a
  premature elimination costs is the attention the family stops getting, not a tier entry. Dormancy saves no
  computing under any rule (every family's data stay in the model and the forecast is made for every family).
- *An alternative second condition, measured beside the branch's on the same fits, not adopted*: the one-sided
  p-value of the family's own forward record against an edge of `θ_min`, below 0.05 at the same two reviews, wake
  at 0.15 (`dev_6M_b/own_record.py`). Its error for a family with an edge does not depend on the other families;
  its price is that it retires almost nobody.

| review dates | rule | premature elimination (95% interval) | families retired, of those with an edge | families with no edge dormant at the end | share of family-reviews written |
|---|---|---|---|---|---|
| years 2, 4, 7, 10 (pre-registered) | 3.0's rule (the forecast alone) | 0.167 (0.045 to 0.261) / 0.179 (0.138 to 0.216) / 0.108 (0.081 to 0.138) / 0.146 (0.092 to 0.197) | 7 of 42 / 25 of 140 / 102 of 944 / 18 of 123 | 0.36 / 0.37 / 0.34 / 0.38 | 0.78 / 0.78 / 0.85 / 0.77 |
| years 2, 4, 7, 10 (pre-registered) | **the draft's rule** (forecast and `Π^max`) | 0.000 (0.000 to 0.000) / 0.014 (0.000 to 0.032) / 0.002 (0.000 to 0.007) / 0.008 (0.000 to 0.029) | 0 of 42 / 2 of 140 / 2 of 944 / 1 of 123 | 0.14 / 0.14 / 0.03 / 0.20 | 0.93 / 0.93 / 0.99 / 0.90 |
| years 2, 4, 7, 10 (pre-registered) | the family's own forward record (forecast and `p^F`) | 0.000 (0.000 to 0.000) / 0.000 (0.000 to 0.000) / 0.000 (0.000 to 0.000) / 0.000 (0.000 to 0.000) | 0 of 42 / 0 of 140 / 0 of 944 / 0 of 123 | 0.01 / 0.02 / 0.02 / 0.05 | 0.99 / 0.99 / 0.99 / 0.97 |
| every year (development experiment) | 3.0's rule (the forecast alone) | 0.714 (0.595 to 0.842) / 0.579 (0.489 to 0.662) / 0.453 (0.407 to 0.502) / 0.431 (0.375 to 0.492) | 30 of 42 / 81 of 140 / 428 of 944 / 53 of 123 | 0.80 / 0.81 / 0.78 / 0.81 | 0.42 / 0.43 / 0.55 / 0.42 |
| every year (development experiment) | **the draft's rule** (forecast and `Π^max`) | 0.048 (0.000 to 0.129) / 0.071 (0.040 to 0.106) / 0.005 (0.000 to 0.015) / 0.057 (0.018 to 0.097) | 2 of 42 / 10 of 140 / 5 of 944 / 7 of 123 | 0.45 / 0.40 / 0.06 / 0.52 | 0.72 / 0.75 / 0.96 / 0.66 |
| every year (development experiment) | the family's own forward record (forecast and `p^F`) | 0.000 (0.000 to 0.000) / 0.000 (0.000 to 0.000) / 0.000 (0.000 to 0.000) / 0.016 (0.000 to 0.039) | 0 of 42 / 0 of 140 / 0 of 944 / 2 of 123 | 0.06 / 0.07 / 0.08 / 0.20 | 0.96 / 0.96 / 0.97 / 0.88 |

  Which of the two the draft should hold is Ethan's (ETHAN_ACTIONS item 22). The draft holds the first session's.

**2. D08's calibration error: the same verdict.** This session's check agrees with the first's: a known
limitation, model not changed. Between 69% and 96% of the families in the bins from 0.1 to 0.6 at year 10 have
an edge of exactly zero; the fitted bell is centred at 0.26 with spread 0.39. A point mass at zero and one bell,
fitted to each replication on the same estimates, has a calibration error of 0.013 (0.006 to 0.031) in D08
against 0.101; the first session's version of the check gave 0.009. One thing to add for whoever designs the
repair: the same crude two-group fit is **worse** than the present model in D02 (0.034 against 0.014), where
edges are rare and the wide component already does the second group's work (`dev_6M_b/calib.txt`). With the
replication as the unit the interval of D08's 0.101 is too wide to place (the statistic jumps when a bin crosses
200 observations): 12 replications do not say whether V6 fails there.

**3. Who reaches Statistically supported: nothing to add to the first session's table** (part 4 of
`DORMANCY_DIAGNOSIS.md`; ETHAN_ACTIONS item 21(a)), except which model it is that says no
(`DORMANCY_SECOND_LOOK.md` section 4, year 10, families with a true edge and two forward years):

| true hedged Sharpe ratio | families | mean forward years | `Π^min ≥ 0.80` (the rule) | central model alone `≥ 0.80` | smallest of S0 to S3 (without S4 and S5) | smallest of S0 to S4 (without the decay model S5) | the most cautious model is S4 / S5 |
|---|---|---|---|---|---|---|---|
| 0.25 to 0.5 | 160 | 5.9 | 0.01 | 0.13 | 0.09 | 0.03 | 0.15 / 0.82 |
| 0.5 to 0.75 | 210 | 5.6 | 0.01 | 0.36 | 0.27 | 0.07 | 0.16 / 0.82 |
| 0.75 to 1 | 294 | 6.2 | 0.03 | 0.67 | 0.59 | 0.17 | 0.22 / 0.77 |
| 1 to 1.5 | 317 | 6.2 | 0.21 | 0.92 | 0.86 | 0.47 | 0.32 / 0.68 |
| 1.5 and above | 46 | 5.9 | 0.54 | 1.00 | 0.98 | 0.85 | 0.46 / 0.52 |

**4. Every simulation interval with the replication as the unit of clustering
(`results/manhattan_sim/v2/CLUSTERED_INTERVALS.md`; `python -m manhattan.sim.cluster_ci`).**

- *What was wrong and what was not.* The pre-registered intervals already take whole replications as the unit
  (`mean ± 1.96 sd/√R` over per-replication values; a percentile bootstrap of whole replications for ratios), so
  no interval treated the tests inside a replication as independent. What they do not allow for is how few
  replications a pilot has: a normal quantile where a Student-t on `R − 1` degrees of freedom is due (2.57 for 6
  replications, 2.20 for 12, 2.03 for 36), a percentile bootstrap that is too narrow with so few clusters, and
  "0.000 to 0.000" where no replication had an event.
- *The corrected interval*: the same estimate, the delete-one-replication jackknife standard error of the same
  estimator, a Student-t quantile; where no replication had an event, the exact bound over replications,
  `1 − 0.025^(1/R)` (0.26 for 12 replications, 0.46 for 6, 0.10 for 36).
- *Result*: 1,070 intervals in 38 runs (version 1's 18 pilots, D11 and the nine twins, the five HB scenarios
  under each dormancy rule). The corrected interval is 1.30 times as wide on average. 510 have a threshold and
  enough observations to be placed; **219 change side, all from "within so far" to "outside so far"**:
  - **204 are intervals that were printed as 0.000 to 0.000**: forward FDR (123), screening FDR (73), four
    D01 calibration shares, two linked-error rows and the two candidates' rows of D02's premature elimination
    under the revised rule. None of them was evidence of a rate of zero: with 12 replications and no event the
    upper end is 0.26, above every bound.
  - **15 are SPA sizes that sat just inside their bound**: version 1's D02 (0.0456, upper end 0.0589 to
    0.0606), D03, D06, P2 and P4, and the hedged twins D01h, D03h, D04h and D05h (6 replications each). Of the
    nine twins, the hedge-aware test's size at 0.05 is within its bound in 3 instead of 6.
  - **No headline changes**: D11 under the hedge-aware test stays within (0.0468; 0.0399 to 0.0538 becomes
    0.0396 to 0.0540) and under the 3.0 test stays outside (0.0774; 0.0611 to 0.0937 becomes 0.0591 to 0.0957);
    premature elimination under the rule of 3.0 stays outside in all four scenarios (0.167: 0.031 to 0.302;
    0.179: 0.130 to 0.227; 0.108: 0.073 to 0.143; 0.146: 0.084 to 0.209) and under the revised rule stays
    within in D05, D08 and D10 (upper ends 0.034, 0.007, 0.026) and is not shown in D02 (none of 42 families in
    12 replications); D08's calibration error stays outside; D09b's 0.344 is 0.303 to 0.384.
- All of these are pilots: "verdict" means on which side of its threshold the judged end of the interval sits
  so far. At the pre-registered counts (400 and 2,000) the correction is under 1% of the width.

**5. The forward e-process: what a rejection proves, what truncation hides, a tail-risk check, week-skipping
(`results/manhattan_sim/v2/ESTIMAND_AND_TAIL_RISK.md`; `manhattan/sim/estimand_study.py`).** Protocol §6 is
unchanged.

- *What a rejection proves.* For at least one component of the family, in at least one week in which it bet,
  the conditional mean, given the past, of the week's core-hedged net return with any loss beyond six ex-ante
  weekly standard deviations counted as six, was positive. Not the mean of the return itself, not an average
  over time, not the weeks skipped, not after real costs.
- *Truncated against untruncated mean* (single series, 2,000 paths of ten years a process, the protocol's own
  transforms; not a held-out scenario: no programme, no pipeline, no metric of the pre-registration). Fat tails
  without a direction: 0.003 to 0.013 of a Sharpe ratio apart; a record shows opposite signs at most 2 times in
  100. Crashes: nothing hidden at 10 daily standard deviations (inside the cap); 0.02 to 0.11 of a Sharpe ratio
  at 20, 0.07 to 0.32 at 40, 0.16 to 0.45 at 100. A strategy with a true Sharpe ratio of −0.25 has a positive
  truncated mean with five crashes of 40 or two of 100 a decade. Ten-year records show a positive truncated mean
  beside a non-positive untruncated one up to 72 times in 100.
- *A tail-risk check, proposed and not adopted* (ETHAN_ACTIONS item 23): the truncated record's total gain must
  cover the tail losses the record cannot rule out at 95%, each at the declared stress loss, and the
  untruncated record must be positive.
- *Week-skipping*: **confirmed valid**, with the argument and a check; what it changes is which weeks are
  tested. One wording gap in §6.6 and §6.7 for production (item 23).

**6. Time and cost of the full run (`results/manhattan_sim/v2/COMPUTE_OPTIONS.md`;
`python -m manhattan.sim.benchmark`).**

- *Measured* (one replication of each kind of run: D02 STD, D08 STD, D02 LONG, D11 STD, D05h STD, D08 HB; each
  alone on the idle machine, then four of each with four workers; Xeon at 2.1 GHz, 4 cores; timing only, no
  record written): 50, 103, 69, 380, 225 and 169 seconds alone; **parallel efficiency 0.92** with four workers
  (the same replication alone against busy; 0.88 to 0.97 by kind); 1.19 CPU-hours for the 24 busy replications;
  **peak memory 0.3 to 0.4 GB a worker, and 1.8 GB for D08 at HB**. Seven workers that are all on an HB scenario
  need 12.5 GB: on a 16 GB machine run the HB scenarios with four or five.
- *The whole development programme*: 1,266 hours of one idle core of that machine, 1,252 still to run (version
  1's STD runs 681, LONG 75, D11 207, the twins 233, the HB scenarios 55). Session 5M's 1,500 to 1,750 came from
  pilot timings on a busy machine. *One confirmation run*, extrapolated from the development runs of the same
  size because its worlds are not coded: about 877 more.
- *Three ways to run it* (estimates only; nothing bought, no workflow added or started):

| | development programme (32 runs, 41,600 replications; the pilot replications on file count) | with one confirmation run (extrapolated: its worlds are not coded) |
|---|---|---|
| hours of one idle core of the session's machine | **1,252** | **2,129** |
| (a) the iMac, seven workers: cores like the session's / a recent Intel desktop (1.5 times as fast) / Apple silicon | 8.1 / 5.4 / 3.8 days | 13.8 / 9.2 / 6.5 days |
| (b) GitHub's runners, 4 cores each, assumed as fast as the session's: runner-hours; jobs of 5 hours; wall-clock with 20 jobs at once; cost | 341; 69; 17 hours; US$0 | 580; 116; 29 hours; US$0 |
| (c) rented whole cores (AWS c7a, assumed as fast as the session's): on demand / on spot; wall-clock on one 64-core machine | US$64 / US$20; 20 hours | US$109 / US$34; 33 hours |

  The iMac's and the runners' speeds are assumptions; `python -m manhattan.sim.benchmark --quick --out bench.json`
  on the machine itself (five minutes) replaces them. GitHub's figures are from its documentation on 2026-11-13
  (standard runners free and unlimited for a public repository, 4 cores and 16 GB, 6 hours a job, 20 jobs at
  once on the Free plan); the cloud prices are from a price aggregator the same day. A workflow for (b) is
  Ethan's to add and to start (hard rules 3 and 16).

**Implemented by this session** (new files only; no file of the pipeline, of version 1 or of the first session
is edited, and no code hash moves):

| where | what |
|---|---|
| `manhattan/sim/cluster_ci.py`, `tests/test_manhattan_cluster_ci.py` (5) | every interval again with the delete-one-replication jackknife and a Student-t quantile; the report and its JSON |
| `manhattan/sim/estimand_study.py`, `tests/test_manhattan_estimand_study.py` (4) | the study of the forward test's estimand and the document it writes |
| `manhattan/sim/benchmark.py`, `tests/test_manhattan_benchmark.py` (2) | the timing slice (alone, then every core busy); it writes no record |
| `results/manhattan_sim/v2/dev_6M_b/` | the development scripts and their outputs: traces, replays, the four-path runs, the alternative rule (outside the package) |
| `results/manhattan_sim/v2/` | `DORMANCY_SECOND_LOOK.md`, `CLUSTERED_INTERVALS.md` (and `.json`), `ESTIMAND_AND_TAIL_RISK.md` (and `estimand_study.json`), `COMPUTE_OPTIONS.md` (and `benchmark.json`) |

**Failed or not met.**

1. **C is still not passed.** Everything above is from pilots.
2. **Two sessions did the same three items.** About two hours of this session's work on the dormancy rule, D08
   and the tier table duplicated the first session's before the overlap was found (at the first push, which was
   refused because the branch had moved). Nothing of the first session's was overwritten. The duplicated work is
   kept on `claude/epic-mayer-kfhpsh` and is used here only as a second opinion.
3. **A pilot of the alternative rule through the runner was stopped part-way** (36 replications of D02, 18 of
   D10, from a clean checkout of `1c1f648` on the other branch): first by a restart of the session's machine,
   then for good when the overlap was found. Its records are not on `build/manhattan` and are counted in no
   report; they retired 2 of 143 families with an edge in D02 and none of 190 in D10.
4. **The session's machine restarted twice.** At 00:22 UTC, killing that pilot and yearly runs then in progress,
   and between about 02:21 and 03:57 UTC, killing the first benchmark part-way. Files were intact both times and
   nothing was lost; the benchmark was run again in two phases that each save their result
   (`--phase alone`, `--phase busy`).
5. **Test failures on the way, none pushed to `build/manhattan`.** First runs of this session's new test
   files: one test used an unhashable object as a dictionary key (the test's mistake); one hand count in a test
   was wrong (the code was right: 4 and 6, not 5 and 7); one comparison needed a tolerance of one unit in the
   last place, and the interval module was changed to treat a jackknife of 1e-17 as zero; the report listed rows
   with no data, which are now left out; one bound in the estimand study's small-size test was tighter than 300
   paths support (0.097 against 0.10) and was set to the bound that matters. Full suites: see "Tests".
6. **Not done:** quarterly reviews for either dormancy rule; any run at the pre-registered count; the held-out
   worlds (still not coded); the benchmark on the iMac or on a GitHub runner (their speeds are assumptions).

## Milestone C: final pre-adoption changes (session 10M, 2026-11-13)

Session "10M Manhattan C: final pre-adoption changes", branch `build/manhattan` (main merged in first: `31bc66a`),
pull request #56, still a draft. Its brief was six numbered items, each committed and pushed on its own once the
full suite passed. `manhattan/ops/` and `docs/manhattan/ops/` were not touched. No protected file was edited.
Both drafts were edited, so the hash record was rewritten at each item that touched them; every pair of hashes
is in the table under item 6.

**Item 1. The dormancy rule is the forward-record rule (Ethan's decision on ETHAN_ACTIONS item 22).**

- *The rule.* A family becomes dormant only if, at two consecutive reviews, the forecast `PP^max` is below 0.05
  **and** a one-sided test of its own forward record against an edge of 0.25 rejects at 0.05
  (`p^F = Φ((y^F − θ_min)/s^F) < 0.05`, defined with 252 forward days, otherwise 1). It is reactivated when either
  is at or above 0.15, or by Ethan. This replaces the second condition session 6M had put in the draft
  (`Π^max < 0.05`).
- *The code.* `manhattan/stats/dormancy.py` is the file of branch `claude/epic-mayer-kfhpsh` at commit `1124fe7`,
  byte for byte, plus one line: `RULE = "protocol-3.1-section-9.1-forward-record"`, the id written into every HB
  replication record. `manhattan/sim/hb_v2.py` computes `p^F` from the forward Sharpe estimate and standard error
  it hands the model (`dormancy.forward_p`) and no longer computes `Π^max` for the rule.
  `manhattan/stats/tiers.py` and `manhattan/sim/hb.py` are untouched.
- *The tests.* The 11 tests of the rule from that commit, in `tests/test_manhattan_dormancy.py` (the one that
  reads the protocol reads this branch's text). **Not brought over:** that branch's shadow paths in the HB
  pipeline (`hb_v2.Track`: the same fits stepped under three rules) and their test and report rows;
  `results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md` already holds that comparison.
- *The text.* Protocol 3.1 §9.1 is rewritten (the two numbers, the table, a box that says what the second
  condition guarantees, why the model's own probability was not kept, and how the rule fails); one sentence of
  §7.2(e); Appendix B's row; the change log, where session 6M's revision is kept and marked superseded; row 5 of
  the table at the top, marked as a pre-adoption change with what it replaces. **§9.2 and §9.3 are 3.0's word
  for word again** (session 6M had reworded two paragraphs of §9.3's box for its rule). SIM_PREREG_v2: its
  header, the sentence on which protocol sections are identical, row 4 of section 1, the reading "Dormancy rule"
  in section 2(f), one line in section 10.
- *Unchanged:* M8's definition, its bound of 0.10 (0.25 for late starters in H09), the scenarios, the
  replication counts, every threshold of SIM_PREREG and SIM_PREREG_v2, the forecast, the tiers, the rule's own
  levels (0.05 twice, 0.15).
- *What is known about the rule so far* is session 6M-b's measurement on the pilot's fits, outside the runner
  (`DORMANCY_SECOND_LOOK.md` section 3): no family with an edge retired at the four pre-registered dates (0 of
  42, 140, 944 and 123), 2 of 123 in D10 with yearly reviews; 1% to 5% of the families with no edge dormant at
  the end (6% to 20% with yearly reviews). Its pilot through the runner is item 6.

**Item 2. The HB runs are reviewed quarterly (amendment 1 of SIM_PREREG_v2; Ethan's decision on item 21(c)).**

- *What changed.* `manhattan/sim/hb_v2.py` fits the six models, makes the forecast and steps the tiers and the
  dormancy rule **every 63 trading days: 40 reviews**, at days 63 to 2,520, in place of version 1's four dates
  (its declared reduction (c), made for the sampler's cost). **M7 and M9 are read at years 2, 4, 7 and 10** as
  before (the record's `reviews` block holds those four reviews in full); **M12 is counted over all 40** (the
  record's `quarterly` block: `ok`, the largest end-of-grid mass, families, seconds, reviews written and families
  dormant at every review); M8 is the state after the last review. "Two consecutive reviews" are a quarter
  apart. `manhattan/sim/hb.py` and `manhattan/stats/tiers.py` are untouched (version 1's HB code hash is still
  `0b8dd1af6db62c9f`).
- *The step is in every record* (`review_step: 63`, with `review_days`). `hb_v2.require_review_step` refuses
  records of any other step; the report counts only records made at this step, and the collector of a run made
  in pieces (item 5) refuses a piece that holds any other.
- *The text.* SIM_PREREG_v2 section 11, "Amendment 1, made before adoption": what is amended, what is not, why
  it tightens and never loosens, what it costs, and why it is in the draft itself and not in the amendments
  file. Sections 2(f), 4 and 5 agree with it. In H09 "the second evaluation date after the edge began" keeps
  version 1's meaning (the second of years 2, 4, 7, 10). Protocol 3.1 §9.1 "How it fails (5)" now says the
  simulation reviews quarterly.
- *Stricter where it has a direction; one reading has none.* V12 must hold over ten times as many reviews, the
  first with ten families and a quarter of forward record. V7's rule gets 39 chances to retire a family, not 3.
  V6 reads the same probabilities at the same dates. V8's groups (the tier states at the four reading dates)
  now come from quarterly stepping: the groups production would have, neither larger nor smaller by
  construction. That is written in the amendment.
- *Cost, measured on one replication* (D08, the dearest; one core of the session's machine while other jobs
  ran): 1,201 seconds against 143 at four dates; the model 1,148 of them; the six fits of a review 18 to 40
  seconds, dearest at the first reviews (few families, the whole grid); all 78 forecasts 31 seconds; **peak
  memory 3.3 GB** (1.8 GB at four dates). In it: no review "not computed" in 40; none of 84 families with an edge
  retired; 16 of 156 families with no edge dormant at the end; 4,885 of 5,080 family-reviews written.
- *Tests.* `tests/test_manhattan_v2.py`: the 40 dates, the step and the two blocks in a real (tiny) replication;
  M12 over 2,400 reviews of 60 replications, and one uncomputed review between two reading dates failing V12;
  records of another step refused; the amendment's text against the code. The tiny world's grid was coarsened
  further so that the tests that run a whole HB replication stay at a few minutes.

**Item 3. D08 and a two-group ("spike and slab") prior: the share is not identified; not adopted
(`results/manhattan_sim/v2/D08_SPIKE_SLAB.md`).**

- *The candidate* (`manhattan/stats/hier_spike.py`, a development file in no code list): slab = the model as it
  is; spike = the slab at retention 0 with the existing 0.02 innovation; edge share uniform on ten grid nodes.
  **With the share fixed at 1 it reproduces `hier_analytic`** for all six models (log evidence to 1e-9; every
  family's `Π`, mean and standard deviation to 1e-10; `tests/test_manhattan_hier_spike.py`, 5 tests).
- *Identification, checked first, against a criterion written into the script before its first run*: in D08 at
  years 4 and 10 on the pilot's 12 replications, the share's posterior standard deviation at most half the
  prior's (0.144) and its posterior mean within 0.10 of the true share, on average.

| D08, central model | families | true share with an edge | posterior mean of the share (range over replications) | posterior sd | mean absolute error | verdict |
|---|---|---|---|---|---|---|
| year 4 | 100 | 0.316 | **0.777** (0.499 to 0.885) | 0.163 | 0.461 | not identified (both conditions fail) |
| year 10 | 240 | 0.328 | **0.896** (0.839 to 0.936) | 0.068 | 0.569 | not identified (narrow, and in the wrong place) |

- *It is the earlier attempt's result again* (0.9 against 0.35), now with its cause. A family with no edge in
  D08 has no apparent edge on the reserve window either: the best-of-20 selection is on the exploration window
  (where such a family averages 0.7) and its reserve estimate averages about zero (−0.04 to −0.15 on three
  replications, with the spread sampling error gives). `θ = ρ a` with `a` near zero already describes it, so the
  spike has nothing to explain: the model gives a family with no edge a probability of 0.88 of being in the
  slab, against 0.94 for a family with one, and learns the same retention (0.65 to 0.91) with one group or two.
  **D08's two groups are in the apparent edge `a_f`, not in the retention.**
- *On data drawn from the candidate itself* (share 0.35; spike families with a high apparent edge and nothing
  forward) 240 families with up to ten forward years recover the share (0.375, sd 0.083) and the 96 families of
  year 4 do not (0.546, sd 0.207). So the algebra is right, and even where the candidate is true V6's first
  decision date comes too early for it.
- *Calibration, for the record* (the pipeline's estimator; the one-group fit reproduces the pilot of record's
  bin counts exactly): year 10, 0.101 (0.034 to 0.136) with one group and 0.096 (0.037 to 0.128) with two; year
  4, 0.034 and 0.007.
- *Stopped there, as the brief said.* The other four HB scenarios were not run with the candidate, it has no
  posterior draws for the forecast, and no pipeline imports it. **D08 stays a documented limitation** (Protocol
  3.1 §7.2(d), which now records the attempt). A repair would be two groups in the prior of `a_f`: another
  model, not built (ETHAN_ACTIONS item 21(b)).
- Development experiment outside the runner: note `note-10M-01` in the run log; script and outputs in
  `results/manhattan_sim/v2/dev_10M/`.

## Milestone D: state (session 4M, 2026-11-12)

**Implemented and tested against D-01 to D-11** (33 tests in `tests/test_manhattan_registry.py`):
`manhattan/spec.py` (canonical form, hashes, IDs, schema, grid enumeration, registry), `manhattan/ledger.py`
(hash chain, corrections, rerun and nondeterminism detection, evidential weights, Merkle root, public index),
`manhattan/roles.py` (the fence, role of a date, the read check), `manhattan/freeze.py` (prepare, manifest,
authority, the runner's check), `manhattan/generate/` and `manhattan/templates/blind_v1.md` (blind and adaptive
requests, reply parsing), `manhattan/critic.py` (specs-only input, validated reviews, the four reasons to block).

**Not done, and why it cannot be yet.**

- **No model is called and nothing is frozen.** There is no blind environment (item 3), no critic definition
  (item 7) and no authority to freeze (item 2). The code builds requests, parses replies, prepares batches and
  refuses unsigned ones; a real batch needs those three items.
- **The timestamp proof is only checked for presence.** No OpenTimestamps client is installed; verifying the
  proof belongs with the iMac runner (milestone H).
- **Not wired to the existing logs**: exploration variants are not yet also written with
  `nightshift.logs.log_variant`, nor the critic's probability with `log_opposition` (ARCHITECTURE §4.3). That
  wiring belongs with the first code that evaluates anything (milestone E/F).
- **No public index file exists** (`data/manhattan/ledger/index.jsonl`): nothing has been recorded.
- The blind template is version 1 and has not been reviewed by Ethan; it is a draft until he accepts it.

## Milestone E: state (session 5M, 2026-11-12)

Done after the Protocol v3.1 work was finished and pushed, in separate commits, in the order the brief fixed: the
parts that need no licensed data first.

**Implemented** (new code only; nothing existing is edited):

| where | what |
|---|---|
| `manhattan/engine/pit.py` | the point-in-time store (a period and an availability day for every value; revisions; publication lags from the spec; a data hash) and the reader, the only way to data, which puts every window to `manhattan.roles.check_read` |
| `manhattan/engine/accounting.py` | daily accounts per unit of capital in excess of cash: drift, turnover, proportional costs, financing of cash instruments for the calendar days held, gaps booked when the price returns |
| `manhattan/engine/backtest.py` | the daily backtester: decisions from a view as of the decision day, execution lag (default 1), daily, weekly or monthly rebalancing, volatility target from returns known at the decision, a result hash |
| `manhattan/engine/events.py` | the event backtester: one position per event, entered when it is known, held a fixed number of days, zero elsewhere |
| `manhattan/engine/lookahead.py` | the look-ahead test: replace everything that became available after a cut-off and compare what was fixed by it, bit for bit; a helper that shifts one input forward, which the test must catch |
| `manhattan/engine/evaluate.py` | one evaluation on record: a ledger record (role, data hash, result hash, code version) and, for the exploration role, a variant row |
| `manhattan/factors/public_fx.py`, `reproduce.py` | six currency deposits from the public daily panel, read line by line up to the cut-off; the reproduction of carry and of the T01 trend signal against the frozen code |
| `docs/manhattan/CORE_FACTORS_PROPOSAL.md` | the proposal for Ethan (item 10); nothing adopted |

**Tested.** 38 new tests, all passing: `tests/test_manhattan_engine.py` (31: every expected number a hand
calculation written beside it) and `tests/test_manhattan_factors.py` (7).

**The reproduction** (`results/manhattan_engine/REPRODUCTION.md`; exploration role, window 2005-01-03 to
2019-12-31, public data, tolerances fixed in the code before the first run):

| what | against | result |
|---|---|---|
| carry: each of six currencies and the equal-weight basket, monthly returns | `em_macro.carry.carry_returns` run on the same rows, and the committed `carry_monthly_returns.csv` up to 2019-12 | reproduced: correlation 0.99989 to 0.99998 over 173 to 179 months; mean absolute difference 1.3 to 3.2 basis points a month (largest single month 69 basis points, TR 2018-06); Sharpe ratios within 0.003. The differences are day-count and compounding conventions |
| time-series momentum: T01's trend weights, month by month | `em_macro.tstrend.trend_raw_weights` on the same monthly returns | reproduced: largest difference between a weight of the engine and of the frozen code 3.3e-16, over 179 months |
| the trend sleeve's monthly gross return | frozen weights times next month's returns | reproduced: correlation 0.99981, mean absolute difference 0.28 basis points a month (largest 27, 2010-06); Sharpe 0.190 against 0.183 |

Both reproduced on the first run. These are two factors the repository already holds, run through new code to
see that it gives the old numbers; neither result is evidence for anything, and both evaluations are recorded
with evidential weight 0.

**Failed or not met.**

1. **The futures half of the reproduction was not done.** The published results (Moskowitz, Ooi and Pedersen
   2012; Koijen, Moskowitz, Pedersen and Vrugt 2018) and the repository's futures sleeves (T20 to T22) need the
   Norgate history in em-macro-data. The environment reported that repository as attachable; the attach was
   refused by the session's permission settings. Recorded as ETHAN_ACTIONS item 20; the session stopped there
   and looked for no other way in. Six currencies from 2005 cannot stand in for those papers, and the report
   says so.
2. **Test failures on the way, none hidden.** The first run of the engine tests had seven failures: one was a
   real fault (weekly decisions were cut on Thursdays, because numpy's weeks start on the day its calendar
   starts; fixed, and a test now checks that weekly decisions are on Fridays), six were wrong hand
   calculations in the tests (a short position drifts and is traded back each day; a value published after the
   window ends is not in the window; a decision executes one day later than the test assumed; the ledger stores
   decimals as strings; two thresholds). The first run of the factor tests had one failure: the committed carry
   file differs from the frozen code's output by a few parts in a million for one currency in late 2019,
   because the daily panel has been refreshed since the file was written; the test now states that tolerance.
3. **Two public files were looked at beyond the cut-off, by hand.** Before the loader existed, the session
   printed the last two lines of `data/processed/daily_panel.csv` and the last three of
   `carry_monthly_returns.csv` (dates in 2026) to see their format, and loaded the panel once with pandas to
   count rows up to 2019. No value dated after 2019-12-31 entered any computation, any test or any file. From
   then on every read went through `read_panel`, which stops at the cut-off, and `check_read`.
4. **The variant rows are not in the shared exploration log.** `results/exploration/log.csv` is appended to by
   the night shift on `dev`; rows added on a branch that goes to main would make the two conflict. The
   reproduction's rows are in `results/manhattan_engine/exploration_log.csv`, written by the same
   `nightshift.logs.log_variant` with the same cut-off check. Whether Manhattan's exploration variants should
   go to the shared log is a question for Ethan (it touches hard rule 6 and the night shift's files).
5. **Not built:** the wiring from the engine's net returns to the core hedge of Protocol §2.2 (there are no
   core factors yet); a futures loader; exchange calendars (the calendar is the days on which any instrument has
   a price); intraday data.

**Remaining for E.** Ethan: item 20 (access), item 10 (the proposal). Then a session: the futures loader and the
futures reproduction on dates up to 2019-12-31; the four currency factors of the proposal through 2019, each
checked against its frozen source.

## What sessions 2M and 3M did (milestones A and B)

1. Read the repository without opening any result series (AUDIT.md header says exactly what was read).
2. Wrote AUDIT.md, ARCHITECTURE.md and PROTOCOL_v3.md and committed them (`b2f2fa5`).
3. Wrote SIM_PREREG.md and committed it with its SHA-256 (`4ea29a4`) **before any simulation code or `manhattan/`
   package existed**. SHA-256: `07fb6ca2a22d01b5d18789a739c33ecea298dbe040d07108ce16df5ca035d715`. It names the
   protocol under test: 3.0.0, SHA-256 `60653417d3e9ce9934ba14c05975d0de4021bb2b22260106c7508bb7454668d5`.
   (Both are the pre-rename hashes; see "Rename" above for the hashes now in force.)
4. Added the hash check (`python -m manhattan.prereg verify`), a validated config with conservative defaults
   (`python -m manhattan.config check`) and their tests.
5. Wrote ETHAN_ACTIONS.md and this file.

## Tests

| run | result |
|---|---|
| session 2M: baseline, `main` at `a2e24fa`, before any change | 705 passed, 127 skipped, exit code 0 |
| session 2M: its branch, full suite, before the push | 720 passed, 127 skipped, exit code 0 |
| session 3M: rename branch `build/manhattan`, full suite, before the push | 724 passed, 127 skipped, exit code 0 (the 4 new rename tests included) |
| `tests/test_manhattan_prereg.py` alone | 19 passed (15 before the rename); on a copy with one threshold edited: fails in a session and under `NIGHT_SHIFT_STRICT=1`, skips with a message under `GITHUB_ACTIONS=true` |
| session 4M, `build/manhattan` at `892bd8b` (main merged in), before any change | 804 passed, 127 skipped, exit code 0 |
| session 4M, first full-suite run (`5192577`) | **1 failed**, 918 passed, 128 skipped, exit code 1: `test_posterior_probability_follows_the_forward_evidence` (0.31 against a fixed 0.3). Not pushed; fixed in `7656ad9` |
| session 4M, opt-in six-model test (`MANHATTAN_SLOW_TESTS=1`) | failed twice (sampler reuse; then an abort inside the compiler under load), then **1 passed** after the sampler cache was removed (`ce4c5d6`) |
| session 4M, full suite at `ce08acf`, before the first push | **953 passed, 128 skipped, exit code 0** (12 minutes) |
| session 4M, the commits after `ce08acf` (documents, the stopped HB run's note, a docstring) | a second full run before the last push; its numbers are in the pull request's description |
| session 5M, `build/manhattan` at `b0ec9c3` (main fast-forwarded in), before any change | **1086 passed, 131 skipped, exit code 0** (this container has no sampler: the sampled model's fits skip) |
| session 5M, first runs of the new test files | `test_manhattan_hier_analytic.py`: 6 of 21 failed; `test_manhattan_adaptive_weight.py`: 6 of 7; `test_manhattan_v2.py`: 1 of 16; one existing test failed after the runner change. Causes and fixes: "Milestone C: state (session 5M)", failed or not met, 4. None pushed |
| session 5M, full suite at `121a34c`, before the first push | **1148 passed, 131 skipped, exit code 0** (16 minutes, while pilots ran) |
| session 5M, full suite before the push of the pilot rerun and the final documents | **1148 passed, 131 skipped, exit code 0** (13 minutes) |
| session 5M, milestone E, first runs of its test files | `test_manhattan_engine.py`: 7 of 31 failed (one real fault, six wrong hand calculations); `test_manhattan_factors.py`: 1 of 7 (a tolerance). "Milestone E: state", failed or not met, 2. None pushed |
| session 5M, milestone E, full suite before its push | **1186 passed, 131 skipped, exit code 0** (13 minutes) |
| session 6M, `build/manhattan` with main merged in (`b5e64c3`), before any change | **1335 passed, 132 skipped, exit code 0** (14 minutes) |
| session 6M, first run of `tests/test_manhattan_dormancy.py` | 1 of 10 failed, by design: the test that reads §9.1 was written before the text was changed. 10 passed after it |
| session 6M, first full suite after the code change (uncommitted report and documents on top of `9b1f068`) | **1 failed**, 1345 passed, 132 skipped, exit code 1: `test_the_runner_keeps_v2_records_apart_and_logs_the_hashes` (this session's own assertion on the report's summary; "Milestone C: state (session 6M)", failed or not met, 4). Not pushed; fixed, and the file then passed (16 passed) |
| session 6M, full suite on the tree that was pushed (the rerun, the reports and the documents on top of `9b1f068`) | run after this file was last edited, so that the tree tested is the tree pushed; its numbers and exit code are in the commit message and in the pull request's description |
| second session of 2026-11-13 ("6M Manhattan C: dormancy fix and statistical checks"), `build/manhattan` with main merged in, before any change | **1335 passed, 132 skipped, exit code 0** (12 minutes) |
| the same session, first runs of its new test files | five failures, each in a new test or in the new report code, none pushed: an unhashable object used as a dictionary key; a wrong hand count (4 and 6, not 5 and 7); a floating-point comparison one unit in the last place off; rows with no data listed by the interval report; a bound tighter than 300 simulated paths support. "Milestone C: statistical checks", failed or not met, 5 |
| the same session, full suite on its alternative revision of §9.1 (branch `claude/epic-mayer-kfhpsh`, commit `1124fe7`; not on `build/manhattan`) | **1356 passed, 132 skipped, exit code 0** (15 minutes, while a pilot ran) |
| the same session, full suite on its first push to `build/manhattan` (`50b0198`: the statistical checks beside the first session's revision) | **1357 passed, 132 skipped, exit code 0** (14 minutes) |
| the same session, full suite on the tree of its last push (the benchmark, the compute options and these documents on top of `50b0198`) | run after this file was last edited, so that the tree tested is the tree pushed; its numbers and exit code are in the commit message and in the pull request's description |

| session 10M, `build/manhattan` with main merged in (`31bc66a`), before any change | 1 failed, 1487 passed, 132 skipped, exit code 1 (15 minutes): `test_the_runner_keeps_v2_records_apart_and_logs_the_hashes`. **Caused by the session, not by the branch**: it replaced `manhattan/stats/dormancy.py` while the baseline was still running, so the HB code hash moved between the test's run and its status check. The same test on an untouched checkout of `31bc66a` in a separate work tree: 1 passed. The baseline is therefore 1488 passed, 132 skipped |
| session 10M, item 1, first run of the ported dormancy tests with the v2 text tests | 40 passed (`test_manhattan_dormancy.py` 11, `test_manhattan_v2.py`, `test_manhattan_prereg_v2.py`, `test_manhattan_tiers.py`) |

| session 10M, item 1, full suite on a clean checkout of its commit (`380a516`), before the push | **1489 passed, 132 skipped, exit code 0** (16 minutes) |
| session 10M, item 2, first run of `tests/test_manhattan_v2.py` after the change | 17 passed (4 minutes) |

| session 10M, item 3, first runs of `tests/test_manhattan_hier_spike.py` | 1 of 5 failed once: the test compared a sum of weights with exactly 1.0 (it is 1 to rounding); the model's numbers were right. 5 passed after it |

Command, as hard rule 15 requires (no pipe, exit code read directly):
`python -m pytest -q -p no:cacheprovider -rs tests > <log> 2>&1; echo "exit=$?"`.

## Decisions taken (sessions 2M to 6M)

Each is written where it applies, with its reason. Those that are Ethan's were made configurable with the
conservative default and are in ETHAN_ACTIONS.md.

| # | decision | where |
|---|---|---|
| 1 | The screening unit is a blind-channel family in its batch; a family is registered in one batch; a new domain later is a new family that names its parent. | ARCHITECTURE §3 |
| 2 | "Once per batch, retired after use" means one designated evaluation per (batch, domain) on a shared reserve window; disjoint slices are an option for Ethan. | ARCHITECTURE §6.2 |
| 3 | The full ledger (with outcomes) is private; the public repository holds a hash-chained index. | ARCHITECTURE §4.1 |
| 4 | Screening candidate (i) is the paper's positive-dependence procedure (`Batch-BH^PRDS`), not its independence procedure, because families in a batch share dates. | PROTOCOL §4.3 |
| 5 | Screening candidate (ii) is e-BH inside the batch at e-LOND's level; derived here with a proof; historical e-values are the forward betting process replayed through the reserve. | PROTOCOL §4.4, §4.5, Appendix A.1 |
| 6 | No lower bound on returns can be guaranteed. The forward test bets on weekly returns truncated at 6 ex-ante standard deviations, tests the truncated null exactly, and adds an asymptotic guard on the untruncated record. | PROTOCOL §6.2-6.3 |
| 7 | Weekly test periods and a variance-ratio rule, because positive serial correlation breaks the test. | PROTOCOL §6.1, §6.7 |
| 8 | A family enters the forward 5% accounting when it becomes Promising, not at freeze. | PROTOCOL §6.8 |
| 9 | One retention parameter links history to the future; six pre-registered models; tiers use the most cautious, dormancy the most optimistic. | PROTOCOL §7, §9 |
| 10 | Simulation: 2,000 replications (400 for model fits), three held-out parameter sets, candidate (ii) preferred unless (i) is better by 0.05 in power. | SIM_PREREG §6-8 |
| 11 | Manhattan tests of hand-edited files skip inside the existing writers' workflows and fail everywhere else. | `tests/test_manhattan_prereg.py`; ETHAN_ACTIONS item 11 |

| 12 | The statistical methods live once, in `manhattan/stats/`; the simulation calls them, so it tests the code production will run. | "Milestone C: acceptance criteria" |
| 13 | The p-value's finite-`B` form is the protocol's (ties counted, plus one), not Hansen's; never smaller. | entry criteria, note 1 |
| 14 | Conventions the pre-registration leaves open (freeze days on week boundaries, reviews every 63 days, one-week settlement lag, scale floor 0.5, D08-D11 details) are fixed in code and listed in every report. | `manhattan/sim/report.py` `DEVIATIONS` |
| 15 | Replication records carry the hash of the code that made them; records of different code are never pooled. | `manhattan/sim/run.py` |
| 16 | The model is sampled through exact changes of variable (quantile tables, standardised logit) and a whitened likelihood: same model, tractable sampler. | `manhattan/stats/hier.py` |
| 17 | A review needs all six model fits to pass the gate; otherwise it is "model not converged" and changes no tier. | `manhattan/sim/hb.py` |
| 18 | The dormancy forecast updates each model's posterior with simulated future records as a normal observation; it does not refit the model. | `manhattan/stats/tiers.py` |
| 19 | The sampler is a separate requirement; model tests skip where it is missing. | `requirements-manhattan.txt`; ETHAN_ACTIONS item 17 |
| 20 | Milestone letters follow Ethan's standing brief from session 4M. | "Milestones" |
| 21 | A blind variant's hash covers its hypothesis and grid point only; an adaptive variant is a separate record marked as such. Periods in the embargo are weekdays until the data layer brings exchange calendars. | `manhattan/spec.py`, `manhattan/roles.py` |
| 22 | Protected files are never edited: the next versions are new files beside them (PROTOCOL_v3.1.md, SIM_PREREG_v2.md, their hash record, a second verifier). Version 2 covers only what changed; version 1 stays in force for the rest and its results are kept. | ETHAN_ACTIONS item 19; SIM_PREREG_v2 header |
| 23 | The SPA resamples are centred at the window's least-squares intercept on the core factors. Re-estimating the hedge without that centre was measured and does almost nothing; a test of the in-window intercept itself was measured too and is left to Ethan as an alternative. | PROTOCOL 3.1 §5.1; `results/manhattan_sim/v2/DEVELOPMENT_NOTES.md` §1 |
| 24 | A resample starts from the actual history before the window, as the live hedge did, then moves to resampled days. | PROTOCOL 3.1 §5.1; `manhattan/stats/spa_hedged.py` |
| 25 | Every development scenario in which V3 is required gets a hedged twin (SPA only, 400 replications, extended until version 1's precision target is met), and a held-out hedge scenario H12 is added: without them the revised test would be judged only on the scenario it was revised on. | SIM_PREREG_v2 §3, §6 |
| 26 | The analytic model is about family portfolios (no hypothesis level), keeps every prior and constant of 3.0 that survives, and replaces the Student-t components by wide normals. | PROTOCOL 3.1 §7.1, §7.2(g) |
| 27 | Hyperparameters are integrated on a fixed grid, not plugged in; a grid check replaces the convergence gate; a review needs all six fits and none may be "not computed" (V12). | PROTOCOL 3.1 §7.2(c), Appendix B; SIM_PREREG_v2 §5 |
| 28 | Dependence between families enters the model as one measured number: the share of forward sampling variance that is common, with one common shock. Added after a development replication showed shared luck read as a shared edge. | PROTOCOL 3.1 §7.1; DEVELOPMENT_NOTES §3 |
| 29 | Seeds and worlds of the changed runs are version 1's; a twin draws from its base scenario's streams, so its oracle column reproduces version 1's own run. Version 1's code files are not touched, so its pilot records keep their code hash. | SIM_PREREG_v2 §9; `manhattan/sim/run.py` |
| 30 | Pilots of record are run through the runner from a clean checkout of one commit, so a file edited during the run cannot reach it. | "Milestone C: state (session 5M)" |
| 31 | In the engine a value has two dates (the period it describes, the day it became available), availability is at day resolution, and a window never shows a value that became available after its end, so the last fixing of a window with a publication lag is not in it. | `manhattan/engine/pit.py` |
| 32 | A decision is taken at a day's close and executed one day later by default (the next available price); the accounting books a gap's whole return on the day the price is back and never drops a day; targets are fractions of capital after the trade's cost. | `manhattan/engine/backtest.py`, `accounting.py` |
| 33 | Manhattan's exploration variant rows go to its own file (`results/manhattan_engine/exploration_log.csv`), written by `nightshift.logs.log_variant` with its cut-off check, not to the night shift's `results/exploration/log.csv`, which is appended to on `dev`. Whether they should be merged is Ethan's question. | "Milestone E: state" |
| 34 | "Reproduced" has numeric tolerances, written in the code before the first run (`manhattan/factors/reproduce.py`, `TOL`). | `results/manhattan_engine/REPRODUCTION.md` |
| 35 | Core factors: proposed as the frozen sleeves' monthly rules marked daily by the engine, not as new signals. Proposed only. | [CORE_FACTORS_PROPOSAL.md](CORE_FACTORS_PROPOSAL.md) |
| 36 | **Superseded by decision 45 (2026-11-13).** Dormancy needs both a low forecast of reaching the tier and a low probability of an edge under the most hopeful model (`PP^max < 0.05` and `Π^max < 0.05`, twice, with 252 forward days); either at 0.15 reactivates. Chosen because it is the question the criterion asks and what §7.2(e) already said, with numbers the protocol already had; not because it scored best among the variants measured. | PROTOCOL 3.1 §9.1; `results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md` §1.4 |
| 37 | A change to a draft before adoption is made in the draft itself, marked as a pre-adoption change in its table of changes and its change log, with the hash record rewritten and both hashes logged. The version number stays 3.1.0: nothing adopted was changed. | PROTOCOL 3.1, top and §10; "Milestone C: state (session 6M)" |
| 38 | The revised rule is a new code file; `manhattan/stats/tiers.py` is not edited, because it is a code file of version 1's records. The HB records of the old rule stay on file and are counted in no current report; the first rerun's report and summary are kept under their own names. | `manhattan/stats/dormancy.py`; `manhattan/sim/run.py` `CODE_FILES_V2_HB` |
| 39 | A calibration error whose cause is the shape of the prior is stated as a limitation, not repaired by a new prior inside a draft that is about to be adopted: the repair is another model and would be fitted to the development scenarios' convention of exact zeros. | PROTOCOL 3.1 §7.2(d); `DORMANCY_DIAGNOSIS.md` part 2 |
| 40 | Experiments that change the pipeline's declared reductions (yearly reviews in place of four dates) are development experiments outside the runner, noted in the run log; they decide nothing and are not pooled with any run of record. | `DORMANCY_DIAGNOSIS.md` parts 3 and 4 |
| 41 | When a second session finds that a first has already revised a draft on the same branch, the first's revision stands: the second edits neither draft, adds its work beside it, and puts what it would have chosen before Ethan as an alternative with the evidence. Its own version stays on its own branch. | "Milestone C: statistical checks"; ETHAN_ACTIONS item 22 |
| 42 | A corrected interval is reported beside the pre-registered one and replaces nothing: the pre-registered interval is part of a frozen file. The correction is the delete-one-replication jackknife with a Student-t quantile, and the exact bound over replications where no replication had an event. | `manhattan/sim/cluster_ci.py` |
| 43 | A study of what a test's null means (single series, a grid of parameters written in the code, no programme, no pipeline, no pre-registered metric, its own random streams) is not a run of a held-out scenario, even where its processes resemble one; it changes no method and is not used to choose one. | `manhattan/sim/estimand_study.py` |
| 44 | Timing is measured by a module that writes no replication record and no run-log record, so that nothing it computes can be pooled into a result. | `manhattan/sim/benchmark.py` |
| 45 | **Ethan's (2026-11-13, ETHAN_ACTIONS item 22):** the second condition of the dormancy rule is a one-sided test of the family's own forward record against an edge of 0.25, not the model's `Π^max`. The session took the code and its tests as they stood on the branch where they were written and did not bring that branch's shadow paths. | PROTOCOL 3.1 §9.1; `manhattan/stats/dormancy.py`; `results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md` |
| 46 | **Ethan's (2026-11-13, ETHAN_ACTIONS item 21(c)):** the HB runs are reviewed every quarter, as production reviews. Made as amendment 1 inside the unadopted SIM_PREREG_v2, with the review step written into every record and other steps refused. M7 and M9 keep their four reading dates; M12 is counted over every review. | SIM_PREREG_v2 §11; `manhattan/sim/hb_v2.py` |
| 47 | A candidate model is checked for identification before it is wired into a pipeline, against a criterion written before the check is run; when the check fails the work stops there and the evidence is recorded. The candidate's code is kept, outside every code list, so the check can be repeated. | `results/manhattan_sim/v2/D08_SPIKE_SLAB.md`; `manhattan/stats/hier_spike.py` |

## Findings to keep in view

- **Formal forward-only support is slow**: about 15 years at a hedged Sharpe ratio of 1, about 5 at 2
  (PROTOCOL §6.9). It will be rare. The middle tiers carry most of the practical weight, and they rest on the
  hierarchical model.
- **Candidate (i) has no theorem behind it on a shared reserve window** (its across-batch independence condition
  fails). It can still win, but only on the simulation's evidence.
- **The Benjamini-Bogomolov link is not covered by its theorem here** (families are dependent; Romano-Wolf inside).
  It is a rule checked by simulation. The forward analogue with e-values is proved.
- **No historical reserve is clean** for the asset classes already traded (AUDIT §3.1), and none is clean with
  respect to the model's knowledge.
- **The middle tiers are the expensive part.** They rest on the hierarchical model, and that model costs hours
  per simulated programme (ETHAN_ACTIONS item 15). The screening route and the forward test are cheap.
- **Candidate (ii) has a proof and, on the pilot, almost no power; candidate (i) has power and no proof here.**
  The full run decides; the pilot only shows the size of the gap.
- **An estimated hedge leaks, and a test must know it.** The ridge keeps about 9% of any exposure to a core
  factor; with a factor that pays, a variant with no edge shows a mean. Re-estimating the hedge inside the
  bootstrap repairs the test only if the resamples are centred at the truth of the world they are drawn from
  (the window's least-squares intercept). A hedge that runs behind a fast-moving exposure still leaves a real
  mean that no resampling of days removes.
- **The middle tiers are now cheap to compute and, on the pilot, hard to reach.** With the six-model minimum,
  7 to 17% of families with an edge are Statistically supported after ten years, and the dormancy rule of 3.0
  retired 11 to 18% of them. The pilot could not have shown this before the model could be run.
- **A forecast of reaching a tier is not a reason to retire a family.** The tier needs the most cautious of six
  models, so the forecast is zero for most families that have an edge. Dormancy now also needs the most hopeful
  model to say the family very probably has no edge. What no rule removes: with edges this small and this rare,
  a family with a real edge and an unlucky or flat record looks like a family with none, and ten years separate
  an edge of 0.25 from zero by less than one standard error.
- **The simulation's four review dates make every "two consecutive reviews" rule look more patient than it is
  in production.** More reviews mean more chances to be retired (or to leave a tier).
- **Two honest second conditions for dormancy exist, and they trade attention against a guarantee.** The model's
  `Π^max` (in the draft) still retires families and so still saves attention, but its error for a family with
  an edge depends on how rare edges are and grows with the number of reviews. The family's own forward record
  has an error that depends on neither, and retires almost nobody. Ten years of one family's returns cannot
  tell an edge of 0 from one of 0.25: any rule that retires many families does it on the model's word about
  families in general.
- **"0.000 (0.000 to 0.000)" in a pilot report is not a rate of zero.** With the replication as the unit and no
  event in 12 replications the upper end is 0.26; in 6, 0.46. Nearly every false-discovery row of the pilots is
  of that kind.
- **A forward rejection is about the truncated mean, in weeks that were bet on.** For fat tails without a
  direction that is the mean, to a hundredth of a Sharpe ratio. For a strategy with rare large losses it can
  differ by 0.45 and have the opposite sign.
- **A model that treats families as independent reads shared luck as shared edge.** One common forward shock
  repairs the case found; it is not the full covariance.

## Unverified

- **Every number from the simulation is a pilot number** (12 replications a run). None meets the precision
  SIM_PREREG §6 fixes.
- The three formulas listed here before (Hansen's recentring, the Politis-White rule, Li-Ji) **are now verified**
  against the published papers (entry criteria above). The other four sources were checked in session 2M.
- The proofs in PROTOCOL Appendix A are short and were checked by hand only. A.1 and A.2 extend published results;
  neither extension has been reviewed by anyone else. The pilot has seen no violation, which proves nothing at 12
  replications.
- Whether the **sampled** model of 3.0 passes its own convergence gate at full size. It is no longer in the main
  loop, and it has never been compared with the analytic model on the same data.
- Whether the analytic model's posterior probabilities are calibrated (V6), whether dormancy abandons good
  families (V7) and whether its Sharpe ratios are unbiased (V8): seen at 12 replications of 400. Under the
  dormancy rule as revised before adoption V7 sits inside its bound so far; one V6 check (D08, year 10) sits
  outside it and is a stated limitation.
- The revised dormancy rule at quarterly reviews, which is what production does: the simulation has four dates,
  and a development experiment has ten.
- How soon a family retired by the revised rule comes back when its edge appears late (held-out H09).
- The hedge-aware test with several core factors, with a hedge cost, and under held-out dependence: unit tests
  of the arithmetic only.
- The closed form of Protocol 3.1 §7.1 and the centre of §5.1 are derived in this repository, not taken from a
  paper, and have been reviewed by nobody else. The closed form is checked against brute-force integration; the
  centre is checked only by simulation.
- The grid of Appendix B: fine enough for the numbers seen (the fit equals a brute-force sum to 2e-6 on a small
  case), not studied for thousands of families.
- The dormancy forecast is an approximation (no refit); its error against a full refit was not measured.
- Whether the rulesets on main are applied; whether a cloud session's git proxy serves public repositories when
  the network is closed; what the private Norgate snapshot contains beyond the 34 exported markets.
- The blind template's wording has not been tried on a model.

- **Either dormancy rule with quarterly reviews**, which is what production uses. Yearly is as far as the two
  sessions of 2026-11-13 went.
- **The alternative dormancy rule's standard error** (the bootstrap standard error of a forward Sharpe ratio)
  under serial correlation or tails heavier than the four HB scenarios contain. Its guarantee is as good as
  that standard error.
- **The speed of the iMac and of GitHub's runners against the session's machine.** COMPUTE_OPTIONS.md states
  them as assumptions; `python -m manhattan.sim.benchmark --quick` on the machine itself measures it.
- **The held-out confirmation run's cost.** Extrapolated from the development runs of the same size; its worlds
  are not coded.
- **The proposed tail-risk check** anywhere but on the study's own grid of processes, and with a stress loss
  that is declared wrongly by less than "not at all".
- **Cloud prices** in COMPUTE_OPTIONS.md are from a price aggregator on 2026-11-13, not from the provider.

## Exact next step

**For Ethan** (ETHAN_ACTIONS.md): item 19 (read and adopt Protocol v3.1 and SIM_PREREG_v2, now with the
dormancy rule revised before adoption: one paste into CODEOWNERS), then item 16 (start the simulation on the
iMac; it includes the model-fitting half), then items 2, 3 and 7 for the first batch. Item 21 holds the three
decisions the model-fitting pilots leave with him (the bar of Statistically supported, D08's calibration, the
review dates of the HB runs); none has to be made before the full run starts. Item 22 is the choice between
the draft's dormancy rule and the one a second session measured beside it; item 23 a proposed tail-risk check.
Item 16 now has the time and cost of three ways to run the simulation.

**For Ethan, milestone E:** item 20 (em-macro-data for the futures half of the reproduction) and item 10 (the
core-factor proposal).

**For the next session:** see "Milestone E: state" for where milestone E stands (engine done; reproduction done
on public currency data; futures blocked on item 20). If the iMac run has finished
and its results are on a branch: build both reports (`python -m manhattan.sim.report --prereg v2` and
`python -m manhattan.sim.report_v2`), then code the held-out worlds H01 to H12 ("Milestone C: state (session
5M)", remaining, step 2) before anything else. Merge main into `build/manhattan` first if it is behind, and run
`python -m manhattan.prereg_v2 verify`.
