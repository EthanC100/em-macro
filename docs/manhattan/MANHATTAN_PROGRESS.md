# Manhattan progress

Updated 2026-11-12 (session "4M Manhattan C: simulation lab", branch `build/manhattan`). A new session starts here:
read this file, then the document for the milestone it is about to work on. Earlier sessions: "2M Manhattan A-B"
(audit, architecture, Protocol v3, simulation pre-registration) and "3M Manhattan rename + PR #45 fixes".

## Milestones

From session 4M on, the milestone letters are the ones in Ethan's standing brief (the table below). Phases D-I of
the first version of this file were cut differently; the last column maps them. A milestone is **done** only when
its acceptance criteria are written here first and its tests then pass, run as hard rule 15 requires.

| milestone | what | status | where | was (old phase) |
|---|---|---|---|---|
| **A** | Audit of what exists | **done** | [AUDIT.md](AUDIT.md) | A |
| **B** | Architecture, Protocol v3, simulation pre-registration | **done** (PR #48 merged 2026-11-12) | [ARCHITECTURE.md](ARCHITECTURE.md), [PROTOCOL_v3.md](PROTOCOL_v3.md) 3.0.0, [SIM_PREREG.md](SIM_PREREG.md) 1.0 | B |
| **C** | Simulation lab: both screening candidates, SPA, forward e-process, hierarchical model, dormancy; the pre-registered experiments, with confidence intervals | **in progress: see "Milestone C" below** | `manhattan/stats/`, `manhattan/sim/`, `results/manhattan_sim/` | C, and the reference half of old H |
| **D** | Registry, freezing workflow, generator templates, critic, ledger | not started | `manhattan/spec.py`, `ledger.py`, `roles.py`, `generate/`, `freeze.py` | old D and F |
| **E** | Point-in-time data layer and daily/event backtester; reproduce time-series momentum and cross-asset carry before anything new | not started; core factors need ETHAN_ACTIONS item 10 | `manhattan/engine/`, `factors/` | old E |
| **F** | Historical screening and forward evaluation, wired only to methods that passed C | not started; needs a passed C and items 1, 2 | production wiring of `manhattan/stats/` | old H |
| **G** | Reports with full denominators and labels | not started | report pages | new |
| **H** | iMac runner package (launchd, checkpoints, heartbeat, watchdog, recovery) | not started; needs item 4 to install | `manhattan/runner/` | old G |
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
| C-01 | **Entry criteria** met and recorded above | |
| C-02 | **Seeds and log.** The master seed is the first 8 bytes of SIM_PREREG.md's SHA-256; every stream is a `SeedSequence` child keyed by (branch, scenario, size, replication, stream); the same key gives identical arrays and a different replication different ones. Every run, including failed and abandoned ones, appends a record to `results/manhattan_sim/runs.jsonl` with time, commit, protocol hash, pre-registration hash, scenario, size, held-out set, replications, seeds and status. A held-out scenario is **refused** unless a confirmation flag is given and the commit carries a `manhattan-sim-confirm-<k>` tag; a refusal is itself logged | |
| C-03 | **Schedule.** `γ(j; 120)` reproduces Protocol §4.2 (`Σ = 16.5945`, `γ_1 = 0.01715`, `γ_50 = 0.00706`, `γ_100 = 0.00519`, `γ_120 = 0.00478`), `γ(·; 300)` reproduces §6.8, and the sequence sums to 1 | |
| C-04 | **Simulated world** (SIM_PREREG §2). Weights sum to 1; a null variant's mean is 0 within Monte Carlo error; the three correlations are 0.60, 0.30 and 0.05 under the defaults (and each scenario's stated ones); every noise distribution has variance 1; D06's volatility has mean square 1; D07's AR(1) terms have variance 1 and the stated coefficient; programme sizes, windows and freeze dates are as §2.1-2.2; truth labels follow §2.4; no parameter is drawn from the model's priors | |
| C-05 | **Block length.** The flat-top window and `m̂` rule follow Politis-White p. 58-59; the estimator recovers the six theoretical values of the corrected Table 1 on long AR(1) series; the protocol's `L = min(max(Q90, H_f, L_min), L_max)` | |
| C-06 | **SPA.** `κ(n,i)` is Hansen's; `ω̂²` equals the variance of the stationary-bootstrap mean (checked against a brute-force bootstrap); the block-sum bootstrap gives the same means as gathering every index; `p_l ≤ p_c ≤ p_u`; a variant below `−ω̂√(2 ln ln n / n)` is not recentred and the others are; `T = 0` gives `p = 1`; the p-value is `(1 + #{T* ≥ T})/(B+1)` with the 999 → 9,999 rule on one stream; under an i.i.d. null the rejection rate at 0.05 and 0.20 is within Monte Carlo error of nominal | |
| C-07 | **Romano-Wolf.** Step 1's critical value is the stated order statistic of the maximum; a variant with a large mean is named; with all nulls the family-wise rate at 0.05 is within Monte Carlo error; later steps use only the remaining set | |
| C-08 | **Li-Ji.** Reproduces the paper's Table 1 (5.99 and 4.01); identity matrix gives `M`; identical tests give 1 | |
| C-09 | **Screening candidate (i).** One batch equals Benjamini-Hochberg at `α_S γ_1`; `α_b` follows §4.3 with the cap; the paper's running estimate `Σ α_s n_s/(n_s + R_{<s})` never exceeds `α_S`; a hand-worked example | |
| C-10 | **Screening candidate (ii).** One family per batch equals e-LOND; one batch with `γ = 1` equals e-BH; exactly `k_b` families meet the final threshold; a hand-worked example; the Benjamini-Bogomolov admission levels of §5.5 for both candidates | |
| C-11 | **Betting process.** `Λ` is §6.4's grid; `Y = max(Z, −c)`; wealth is the equal-weight mean of six fixed-fraction products and is never negative; scale, bet and variance-ratio decision for a week are unchanged when that week or any later data are altered; `VR̂` matches a hand calculation and a week with `VR̂ > 1.25` leaves wealth unchanged; the guard matches a hand calculation of §6.3 and needs 52 weeks; tail count and tail debt; under a fair-coin null the share of paths ever reaching 20 is at most 0.05 within Monte Carlo error | |
| C-12 | **Forward e-LOND.** A single family is rejected exactly when `W ≥ 1/(α_F γ_1)`; a rejection lowers every other bar at once (`k_t` step-up); rejections are permanent; a failed guard blocks; family numbers follow enrolment order | |
| C-13 | **Hierarchical model.** The six models differ only as §7.2(e) says; on data drawn from a stated truth with many families the posterior of the retention centre and of `μ_A` covers the truth; `Π_f` rises with a family's forward evidence and falls with a contradicting one; a fit that fails `R̂ ≤ 1.01`, effective sample size ≥ 400 or has divergences is reported "model not converged" and changes no tier | |
| C-14 | **Tiers and dormancy.** Entry, exit and the two-consecutive-reviews rules of §8.1-8.2 on scripted sequences; dormant only after `PP^max < 0.05` twice; reactivated at `≥ 0.15`; never dormant when `T_end` is unset; a dormant cheap family keeps recording and its data stay in the model | |
| C-15 | **Metrics and intervals.** M1-M11 on hand-made replications; `mean ± 1.96 sd/√R`; the 2,000-resample bootstrap over whole replications for ratios; the fewer-than-200-observations rule; every threshold of §5 read from one table that a test compares with SIM_PREREG.md's text | |
| C-16 | **V10(a).** In D09a and D09b the designated blind p-values and e-values are bit-for-bit identical with and without the adaptive channel | |
| C-17 | **Experiments.** Every development scenario is run at every size §3.1 lists, with both screening candidates, at the pre-registered replication count; **or** as a pilot labelled as such, with the shortfall recorded and the full run packaged for the iMac. The report gives every metric with its interval, the threshold and pass, fail or "pilot: not decided", every deviation from SIM_PREREG.md and the list of earlier runs. No held-out scenario is run before a tagged confirmation run | |
| C-18 | **Hygiene.** SIM_PREREG.md, its hash record, PROTOCOL_v3.md, `manhattan/prereg.py`, `tests/test_manhattan_prereg.py` and `config/manhattan.yaml` are unchanged (`python -m nightshift.protected` on the changed paths, and `python -m manhattan.prereg verify`); `claims.enabled` stays false; the full suite passes with the runner's own exit code read | |

**What "done" means for C.** C is done when C-01 to C-18 hold **and** the confirmation run of SIM_PREREG §8 has been
made at the full replication counts. A pilot does not finish C and enables no claim.

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

## What this session did

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
| baseline, `main` at `a2e24fa`, before any change | 705 passed, 127 skipped, exit code 0 |
| this branch, full suite, before the push | 720 passed, 127 skipped, exit code 0 |
| rename branch `build/manhattan`, full suite, before the push | 724 passed, 127 skipped, exit code 0 (the 4 new rename tests included) |
| `tests/test_manhattan_prereg.py` alone | 19 passed (15 before the rename); on a copy with one threshold edited: fails in a session and under `NIGHT_SHIFT_STRICT=1`, skips with a message under `GITHUB_ACTIONS=true` |

Command, as hard rule 15 requires (no pipe, exit code read directly):
`python -m pytest -q -p no:cacheprovider -rs tests > <log> 2>&1; echo "exit=$?"`.

## Decisions taken in this session

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

## Unverified

- Protocol v3 was checked against four of its sources (batch online FDR, e-LOND, the selection-adjusted procedure,
  the asymptotic confidence sequence). **Hansen's recentring constant and the Politis-White block-length rule are
  from memory**, and the Li-Ji formula was matched only to a secondary description; all three must be checked
  against the papers in Phase C before they are coded.
- The proofs in PROTOCOL Appendix A are short and were checked by hand only. A.1 and A.2 extend published results;
  neither extension has been reviewed by anyone else.
- No number in Protocol v3 has been tested: every threshold, schedule and prior is an assumed parameter until
  Phase C. The evidence-time table is arithmetic under a Gaussian approximation.
- Whether the rulesets on main are applied; whether a cloud session's git proxy serves public repositories when
  the network is closed; what the private Norgate snapshot contains beyond the 34 exported markets.
- The hierarchical model has not been fitted to anything; whether it converges at the simulated sizes is unknown.

## Exact next step

**After this PR is merged** (ETHAN_ACTIONS item 13; nothing else is needed to start):

1. New branch from main. Run `python -m manhattan.prereg verify` and stop if it fails.
2. Meet the Phase C entry criteria above: check the three formulas listed under "Unverified" against Hansen
   (2005), Politis and White (2004) with Patton, Politis and White (2009), and Li and Ji (2005). Record the source
   and page of each in the entry-criteria table. If any differs from PROTOCOL_v3.md, correct the protocol as
   version 3.0.1 with a change-log entry **before** writing code that uses it.
3. Create `manhattan/sim/dgp.py`: the return model of SIM_PREREG §2.3 with the defaults and scenario D01 only, seeded as
   in SIM_PREREG §9, with tests (weights sum to 1; null variants have mean 0 within Monte Carlo error; the three
   correlations are 0.60, 0.30 and 0.05).
4. Create `results/manhattan_sim/runs.jsonl` logging from the very first run, held-out sets refused unless a
   confirmation flag and a tagged commit are present.
5. Then, in this order: the betting process and e-LOND (the simplest exact claims, C3), the SPA and Romano-Wolf
   (C2), the two screening candidates (C1), the hierarchical model (C5-C7). Development scenarios only until every
   required criterion passes on them.
