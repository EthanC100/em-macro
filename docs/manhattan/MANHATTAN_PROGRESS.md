# Manhattan progress

Updated 2026-11-12 (session "5M Manhattan C: protocol 3.1 and prereg v2 (hedge-aware SPA, analytic hierarchical
model)", branch `build/manhattan`). A new session starts here:
read this file, then the document for the milestone it is about to work on. Earlier sessions: "2M Manhattan A-B"
(audit, architecture, Protocol v3, simulation pre-registration), "3M Manhattan rename + PR #45 fixes" and "4M
Manhattan C: simulation lab" (which also did milestone D).

**Two protocol versions exist.** [PROTOCOL_v3.md](PROTOCOL_v3.md) 3.0.0 and [SIM_PREREG.md](SIM_PREREG.md) 1.0 are
frozen and protected. [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md) 3.1.0 and [SIM_PREREG_v2.md](SIM_PREREG_v2.md) 2.0 are
**drafts written by session 5M for Ethan to adopt** (ETHAN_ACTIONS item 19): they repair the two things the pilot
showed must be repaired before a full run. Until he adopts them they are in force for nothing.

## Milestones

From session 4M on, the milestone letters are the ones in Ethan's standing brief (the table below). Phases D-I of
the first version of this file were cut differently; the last column maps them. A milestone is **done** only when
its acceptance criteria are written here first and its tests then pass, run as hard rule 15 requires.

| milestone | what | status | where | was (old phase) |
|---|---|---|---|---|
| **A** | Audit of what exists | **done** | [AUDIT.md](AUDIT.md) | A |
| **B** | Architecture, Protocol v3, simulation pre-registration | **done** (PR #48 merged 2026-11-12). Drafts of the next versions, for Ethan to adopt: Protocol 3.1.0 and pre-registration version 2 (session 5M) | [ARCHITECTURE.md](ARCHITECTURE.md), [PROTOCOL_v3.md](PROTOCOL_v3.md) 3.0.0, [SIM_PREREG.md](SIM_PREREG.md) 1.0; drafts [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md), [SIM_PREREG_v2.md](SIM_PREREG_v2.md) | B |
| **C** | Simulation lab: both screening candidates, SPA, forward e-process, hierarchical model, dormancy; the pre-registered experiments, with confidence intervals | **code and tests done; pilot run, and rerun for the two repaired methods; NOT passed** (full run packaged for the iMac and now includes the model-fitting half; needs ETHAN_ACTIONS item 19; held-out worlds not coded): see "Milestone C: state (session 5M)" | `manhattan/stats/`, `manhattan/sim/`, `results/manhattan_sim/` | C, and the reference half of old H |
| **D** | Registry, freezing workflow, generator templates, critic, ledger | **done against its criteria** (33 tests); not yet usable for a real batch: needs ETHAN_ACTIONS items 2, 3, 7 and a timestamp client: see "Milestone D: state" | `manhattan/spec.py`, `ledger.py`, `roles.py`, `generate/`, `freeze.py` | old D and F |
| **E** | Point-in-time data layer and daily/event backtester; reproduce time-series momentum and cross-asset carry before anything new | **next; not started**; core factors need ETHAN_ACTIONS item 10 | `manhattan/engine/`, `factors/` | old E |
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
| C-18 | **Hygiene.** SIM_PREREG.md, its hash record, PROTOCOL_v3.md, `manhattan/prereg.py`, `tests/test_manhattan_prereg.py` and `config/manhattan.yaml` are unchanged (`python -m nightshift.protected` on the changed paths, and `python -m manhattan.prereg verify`); `claims.enabled` stays false; the full suite passes with the runner's own exit code read | **met**: `python -m nightshift.protected` on every path changed against main printed nothing and exited 0; no file of `em_macro`, `ledger`, `lab`, `nightshift`, `janus`, `.claude`, `.github` or `config` is changed; `python -m manhattan.prereg verify` prints `pre-registrations ok`; `claims.enabled` is false; full suite 953 passed, 128 skipped, exit 0 |

| C-19 | **Hedge-aware SPA (Protocol 3.1 §5.1).** The resampled hedged means equal those obtained by building each pseudo-series and hedging it with `manhattan.stats.hedge` (one and several factors; long, short and no history; with a hedge cost); the identity sequence gives the live hedged mean; the centre is the window's least-squares intercept; the statistic and `ω̂` are the live ones; the random stream is consumed as by the 3.0 test; **with nothing to hedge the result is the 3.0 test's, bit for bit** (V13); on a hedge that leaks a factor's mean the 3.0 test over-rejects and this one does not | **met**: `tests/test_manhattan_spa_hedged.py` (16) |
| C-20 | **Analytic hierarchical model (Protocol 3.1 §7).** The six models and the grid are those of §7.2(e) and Appendix B (code against the protocol's text); one family's closed form equals brute-force integration (likelihood, mean, `Π`); a whole fit equals an independent sum over the grid written from the formulas; nothing in a fit is random and a model's numbers do not depend on which others are fitted with it; `Π_f` follows forward evidence; shrinkage is the only adjustment for selection; the wide component lets a conflicting family keep its data; a level shared by all forward estimates is not read as an edge when luck is shared; the grid gate refuses data outside the grid; three class retentions and `μ_A` are recovered on 600 families not drawn from the priors, with intervals that cover | **met**: `tests/test_manhattan_hier_analytic.py` (21) |
| C-21 | **Zero evidential weight of the adaptive channel on the reserve (Protocol 3.1 §5.3, §7.3; V14).** The weight comes from `manhattan.ledger.evidential_weight` and cannot be passed to the model; no reserve number of an adaptive-channel family changes any output of any of the six models, to the last bit, while the same change to a blind family does; an adaptive family equals a family with no reserve term; its forward record counts; the protocol quotes the D09b number that is on file | **met**: `tests/test_manhattan_adaptive_weight.py` (7) |
| C-22 | **Version 2 beside version 1.** PROTOCOL_v3.md, SIM_PREREG.md and its record are byte for byte what they were; the version 2 record pins SIM_PREREG_v2.md and PROTOCOL_v3.1.md and a one-character change to either fails; version 1's code files and code hash are unchanged, so its pilot records still count; only D11, the twins and the HB scenarios go to the new code, and only with `--prereg v2`; version 2's records are kept apart and its runs log both hashes; every threshold of version 1 is the object version 2 uses; the numbers in SIM_PREREG_v2.md are the code's; 3.1 keeps every constant and every untouched section of 3.0 word for word and makes the two wording fixes; the CODEOWNERS lines of ETHAN_ACTIONS item 19 protect exactly the five new files | **met**: `tests/test_manhattan_prereg_v2.py` (3), `tests/test_manhattan_v2.py` (15) |
| C-23 | **Pilot rerun.** D11 and a hedged twin of every other development scenario in which V3 is required, and the five HB scenarios, run as labelled pilots through the runner from a clean checkout of one commit, with every metric, interval and threshold reported and every development experiment noted in the run log. No held-out scenario run | **met as a pilot**: `results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`, `DEVELOPMENT_NOTES.md` |

C-19 to C-23 were written by session 5M with the work they describe, not before it: the session's brief fixed what
was to be built, and these rows record what the tests then had to show.

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

Command, as hard rule 15 requires (no pipe, exit code read directly):
`python -m pytest -q -p no:cacheprovider -rs tests > <log> 2>&1; echo "exit=$?"`.

## Decisions taken (sessions 2M to 4M)

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

## Unverified

- **Every number from the simulation is a pilot number** (12 replications a run). None meets the precision
  SIM_PREREG §6 fixes.
- The three formulas listed here before (Hansen's recentring, the Politis-White rule, Li-Ji) **are now verified**
  against the published papers (entry criteria above). The other four sources were checked in session 2M.
- The proofs in PROTOCOL Appendix A are short and were checked by hand only. A.1 and A.2 extend published results;
  neither extension has been reviewed by anyone else. The pilot has seen no violation, which proves nothing at 12
  replications.
- Whether the hierarchical model passes its own convergence gate at full size with the default budget; whether
  its posterior probabilities are calibrated (V6); whether dormancy abandons good families (V7). None could be
  measured.
- The dormancy forecast is an approximation (no refit); its error against a full refit was not measured.
- The cloud-cost guess in ETHAN_ACTIONS item 15 is not priced.
- Whether the rulesets on main are applied; whether a cloud session's git proxy serves public repositories when
  the network is closed; what the private Norgate snapshot contains beyond the 34 exported markets.
- The blind template's wording has not been tried on a model.

## Exact next step

**For Ethan** (ETHAN_ACTIONS.md): start the simulation on the iMac (item 16), decide the model-fitting half
(item 15), then items 2, 3 and 7 for the first batch.

**For the next session** (its name starts with the next free number, then "M Manhattan E: point-in-time data
layer and backtester", unless Ethan redirects):

1. Read this file, ARCHITECTURE.md sections 2 and 6, PROTOCOL_v3.md section 2 and AUDIT.md section 1.2. Merge
   main into `build/manhattan` first if it is behind. Run `python -m manhattan.prereg verify`.
2. Write milestone E's acceptance criteria here before any test: a point-in-time store in which every value has
   an availability time and a read "as of" a time never returns a later one; publication lags from the spec; a
   daily and an event backtester that turn an executable into a net return series with positions fixed from
   earlier information only; a look-ahead test that fails when any input is shifted forward; every read of
   dated data goes through `manhattan.roles.check_read`; every evaluation is a ledger record
   (`manhattan.ledger`) and, for exploration, also a `nightshift.logs.log_variant` row.
3. **Reproduce time-series momentum and cross-asset carry on exploration dates only** (to 2019-12-31, the cap
   `config/manhattan.yaml` and the night shift already enforce) from data already in the repository, and compare
   with the published numbers and with the repository's own frozen results (AUDIT §1.2 lists what exists).
   No date after 2019-12-31 is read: the reserve is disabled and `check_read` refuses it. Nothing new is
   evaluated until both reproduce.
4. Propose the daily core-factor definitions for Ethan (ETHAN_ACTIONS item 10); do not adopt them.
5. If the iMac run has finished and its results are on a branch: build the report
   (`python -m manhattan.sim.report`), then code the held-out worlds ("Milestone C: state", remaining, step 3)
   **before** milestone E.
