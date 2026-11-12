# Manhattan: what only Ethan can do

Recorded 2026-11-12; updated the same day by session "4M Manhattan C: simulation lab" (items 5 and 13 closed,
items 14 to 18 added) and by session "5M Manhattan C: protocol 3.1 and prereg v2" (item 19 added; items 14 and 15
answered by the draft of Protocol v3.1, which item 19 adopts; item 16 re-estimated; item 20 added and item 10
updated by milestone E). Each item is something no
agent may decide or do under the CLAUDE.md hard rules, or cannot do from a cloud session. For each: the
conservative default now in force, what it blocks, and what to do. Nothing in this list was created, changed,
bought or switched on by a session.

**Order of urgency now:** item 19 (read and adopt Protocol v3.1 and version 2 of the simulation pre-registration:
one paste into CODEOWNERS), then item 16 (start the simulation on the iMac: it now includes the model-fitting
half), then items 2, 3 and 7 (they unblock the first real batch). Items 10 and 20 decide how far milestone E
can go. Item 8 has a date (about 5 May 2027).

| # | decision or action | default in force | blocks |
|---|---|---|---|
| 1 | the reserve-window fence | no reserve (`reserve.enabled: false`) | all historical screening |
| 2 | authority for Manhattan batch freezes under rule 4 | Ethan only (`freeze.authority: ethan_only`) | any freeze |
| 3 | a separate repository and environment for the blind generator | none exists; nothing is called blind | the blind channel |
| 4 | iMac setup | no runner | licensed-data evaluations, signed freezes |
| 5 | protect the frozen Manhattan files | **done** (the six lines are in CODEOWNERS on main, `892bd8b`) | - |
| 6 | confirm the rulesets on main | unknown | nothing; a risk |
| 7 | critic and generator definitions, routines | none added | the critic's "never sees outcomes" rule |
| 8 | data licences and spending | no spending | futures history after May 2027; a tool-less generator |
| 9 | programme parameters | conservative values | dormancy, live tier |
| 10 | core factor definitions | none approved; **a proposal is written** (CORE_FACTORS_PROPOSAL.md) | every hedged return |
| 11 | Manhattan tests inside the writers' workflows | skip there, fail elsewhere | nothing |
| 12 | Manhattan and the trial ledger | separate | nothing |
| 13 | merge the first PR; go-ahead for the simulation | **done** (PR #48 merged; session 4M was the go-ahead) | - |
| 14 | two wording fixes in PROTOCOL_v3.md | **made in the draft PROTOCOL_v3.1.md** (item 19); 3.0.0 left as it is | nothing; clarity |
| 15 | the model-fitting half of the simulation cannot be run as pre-registered | **answered by the draft of Protocol v3.1** (an analytic model: item 19); posterior tiers and dormancy stay off until it passes | "Statistically supported", dormancy, calibration claims |
| 16 | run the simulation on the iMac | pilot only | choosing the screening method; every claim |
| 17 | the simulation's sampler in requirements | separate file; no longer needed by the simulation | nothing |
| 18 | housekeeping: the pre-rename branch | left in place | nothing |
| 19 | adopt Protocol v3.1 and SIM_PREREG_v2 | drafts, unprotected, not in force; version 1 and Protocol 3.0.0 untouched | the full run of D11 and of the model-fitting half |
| 20 | access to em-macro-data for the futures half of milestone E | none in a build session: the attach was refused | reproducing time-series momentum and carry on futures; every futures core factor |

---

## 1. The reserve-window fence

**Why Ethan.** Hard rule 4: an agent never runs a confirmatory 2020-2026 test. A screening-reserve evaluation on
those dates is one.

**Decide, per domain** (for example `fx_daily`, `commodity_futures_daily`): the first and last date of the reserve;
`reserve.mode` (`shared_window`, the default, or `disjoint_slices`); and whether the reserve applies at all to a
domain whose history is already spent (AUDIT §3.1).

**What the audit found.** For FX, bonds and commodity futures there is no window that no trial has used; 2020-01 to
2026-09 has had ten confirmatory looks on the FX and bond panel and three on futures. A reserve there is Grade 2: a
filter. The natural fence, if you want one, is exploration to 2019-12-31 (the cap the night shift already enforces)
and reserve 2020-01-01 to 2026-09-30, the dates rule 4 already protects.

**Do.** Edit `config/manhattan.yaml` on main: `reserve.windows`, then `reserve.enabled: true`. `python -m manhattan.config
check` must pass. Until then every runner refuses a reserve evaluation.

## 2. Authority for Manhattan batch freezes under rule 4

**Why Ethan.** A batch freeze is a pre-registration of 50-100 hypotheses; rule 4 reserves pre-registration to you.

**Options.** (a) Keep it yours (default): agents prepare a batch on a branch (specs, hashes, critic reviews,
manifest); you review, merge, sign the tag and timestamp it. (b) Delegate the mechanical freeze of **blind-channel**
batches to the runner, keeping the signed tag yours. That needs a sentence added to CLAUDE.md rule 4 (for example:
"An Manhattan batch freeze prepared under docs/manhattan/ and signed by Ethan is not a trial pre-registration") and
`freeze.authority: delegated`.

**Recommendation.** (a) for the first batches; revisit after three.

## 3. A separate repository and environment for the blind generator

**Why Ethan.** Creating a repository and a cloud environment, and their network settings, are settings changes
(rule 11). A cloud session cannot make itself blind: em-macro is public and holds results (ARCHITECTURE §8).

**Do one of:**

- **A tool-less model call (strongest).** A script on the iMac sends the fixed template to the model through the
  API with no tools and stores the reply. The model can read nothing. This needs an API key, which is spending
  (item 8) and reverses the earlier choice to run without one (`docs/todo.md`).
- **A separate cloud environment.** A new private repository (suggested name `manhattan-blind`) holding only the
  template and the spec schema; a new environment with that repository only, network access set to none, no
  connectors, and the Claude GitHub App not given em-macro or em-macro-data in that environment. Check from inside
  it that `git clone https://github.com/EthanC100/em-macro` fails; if a public repository can still be fetched
  through the session's git proxy, this option is not blind and the first one is needed.

Either way the model still knows market history up to its training cutoff. Nothing fixes that; Protocol v3 is built
around it.

## 4. iMac setup

**Why Ethan.** It is your machine, your keys and your tokens.

1. Clone em-macro and em-macro-data; create a pinned Python environment from `requirements.txt`.
2. A fine-grained GitHub token limited to those two repositories (contents: read and write), stored in the
   Keychain, never in a file.
3. A signing key for tags (SSH or GPG), registered on GitHub; `git config tag.gpgSign true`. Signed tags are what
   make a freeze yours (ARCHITECTURE §5.4).
4. An external timestamp client (OpenTimestamps is the default in the design; any RFC 3161 service would do).
5. Decide where the **reserve data** and the **full ledger** live: on the iMac only (default, `reserve.store:
   imac_only`; back them up), or in em-macro-data (convenient, but readable by any session that attaches that
   repository, so not runner-only).
6. Power: `pmset repeat wakeorpoweron` shortly before the scheduled run, or leave the Mac awake.
7. Install the LaunchAgent when Phase G delivers it (`~/Library/LaunchAgents/com.horizons.manhattan.runner.plist`), and
   allow the heartbeat branch `manhattan-heartbeat`.

Nothing needs doing before Phase C unless you want the simulation to run on the iMac (item 13).

## 5. Protect the frozen Manhattan files

**Done.** The six lines below are in `.github/CODEOWNERS` on main (commit `892bd8b`), and
`python -m nightshift.protected docs/manhattan/SIM_PREREG.md` now prints `PROTECTED`. The text is kept for the record.

**Why Ethan.** `.github/CODEOWNERS` is protected (hard rule 2), so no session edits it. Add these lines to
`.github/CODEOWNERS` on main, **inside** the protected block: paste them on the line just above
`# protected:end`, after the `/docs/rulesets/ @EthanC100` line. Copy them exactly:

```
# Manhattan: the frozen simulation pre-registration, its recorded hash, the protocol it tests, the code and the
# test that check the hash, and Manhattan's switches (docs/manhattan/ETHAN_ACTIONS.md item 5)
/docs/manhattan/SIM_PREREG.md @EthanC100
/docs/manhattan/sim_prereg.sha256 @EthanC100
/docs/manhattan/PROTOCOL_v3.md @EthanC100
/manhattan/prereg.py @EthanC100
/tests/test_manhattan_prereg.py @EthanC100
/config/manhattan.yaml @EthanC100
```

What each line does:

- `SIM_PREREG.md` and `sim_prereg.sha256`: the frozen file and its hash. Protecting only one would let a session
  edit the other.
- `PROTOCOL_v3.md`: the method under test. Changes go through a new version and need your review.
- `manhattan/prereg.py` and `tests/test_manhattan_prereg.py`: the verifier and the test that also holds the
  pre-rename hashes. Without these lines a session could weaken the check instead of the file.
- `config/manhattan.yaml`: your switches (reserve fence, freeze authority, claims), like `config/night.yaml`.

`SIM_PREREG_AMENDMENTS.md` is left out on purpose: it is append-only and is written during Phase C. Add the batch
manifests and the public ledger index when they exist. Afterwards, `python -m nightshift.protected
docs/manhattan/SIM_PREREG.md` prints `PROTECTED: docs/manhattan/SIM_PREREG.md` and exits 1 (checked on a copy of
CODEOWNERS with these lines added: all six paths match; `SIM_PREREG_AMENDMENTS.md` and `manhattan/sim/` do not), and the night shift's promotion check will refuse
any dev -> main change to these paths.

Until then, only the hash test guards the pre-registration. A session that edited the file, the hash record and
the test together would pass, though git history would still show the change.

## 6. Confirm the rulesets on main

`docs/rulesets/main.json` and `frozen-tags.json` were designed on 2026-11-09 for you to apply. Whether they are
applied cannot be seen from a session. If they are not, only convention keeps any session off main.

## 7. Critic and generator definitions, routines

**Why Ethan.** `.claude/` is protected, and creating scheduled tasks is a settings change.

- A critic definition that reads **specs only** (suggested `.claude/agents/manhattan-critic.md`: tools Read only, with
  the batch folder as its only input, no WebSearch). The Opposition as defined reads exploration results and the
  whole repository (AUDIT §1.1).
- Later: generator definitions and any Manhattan routine. No Manhattan schedule exists, and none will be a Janus schedule
  (rule 14).

## 8. Data licences and spending

- **Norgate** (Personal Use; no redistribution) ends about 5 May 2027, and `docs/shadows/operation.md` says the
  snapshot is deleted then. Decide before that date whether to renew for Manhattan. Without it, futures history for
  screening is Databento only (CME group, from June 2010, paid per request).
- **Databento**: any purchase of history for Manhattan beyond the shared US$1 daily cap.
- **An API key** for a tool-less blind generator (item 3).

No spending was made or assumed.

## 9. Programme parameters

| parameter | default | effect |
|---|---|---|
| `programme.end` | unset | until set, no family is ever made dormant |
| `forward.loss_cap_usd` | 0 | the Live-experiment tier is closed |
| `θ_min` (smallest edge that matters) | 0.25 hedged net Sharpe | tier thresholds; changing it is a protocol version |
| risk aversion `γ_R` | 4 | Scale-eligible tier |
| "cheap" family | at most US$1 a month and one CPU-minute a day | which families are always recorded |

Protocol v3 §6.9 shows what the 5% forward level costs: formal forward-only support takes about 15 years for a
hedged Sharpe ratio of 1 and about 5 years for 2. If that is not what you want from the top tier, say so before the
simulation runs; changing it afterwards needs a new protocol version and a new pass.

## 10. Core factor definitions

Daily carry, trend, value and buy-and-hold returns per asset class do not exist (AUDIT §1.2). Phase E will propose
definitions built from the frozen v1.0 signals and the T20-T22 sleeves. They decide what "core-hedged" means for
every family, so they are yours to approve and are frozen before the first batch.

**Status (session 5M, milestone E).** The proposal is written: [CORE_FACTORS_PROPOSAL.md](CORE_FACTORS_PROPOSAL.md).
In one sentence: keep each frozen sleeve's monthly decision rule and let the new engine mark its positions
daily, instead of designing new signals. It lists six choices that are yours (section 4), the first being
whether to adopt that principle. Nothing in it is adopted. The engine already reproduces two of the currency
factors against their frozen sources on public data to 2019 (`results/manhattan_engine/REPRODUCTION.md`).

## 11. Manhattan tests inside the writers' workflows

`systematic-monthly` runs the whole test suite before it commits the rebalance. The Manhattan checks of hand-edited
files (the pre-registration hash, `config/manhattan.yaml`) **skip with a message there** and fail everywhere else,
following the repository's own convention, so an Manhattan document can never stop the rebalance or the 4 December
shadow go-live. If you would rather a changed pre-registration stopped everything, add `MANHATTAN_STRICT: "1"` to the
workflow's environment (a workflow change, so yours).

## 12. Manhattan and the trial ledger

Default: Manhattan evaluations are not rows of `trials.csv`, do not change the spec's multiple-testing count (N = 21
after T27), and no Manhattan result is called a trial result. If you want Manhattan screening counted there, say how.

## 13. Merge, and the go-ahead for Phase C

**Done.** PR #48 is merged and the simulation code exists (milestone C). What follows from it is in items 15 to 17.

- Merging this PR puts the pre-registration on main. From then on the simulation code may be written.
- Phase C's confirmation run is about 2,000 replications of about 40 scenario runs plus 400 replications of about
  12 model-fitting runs. Decide where it runs: GitHub Actions (public repository, so results and logs are public,
  which is fine for synthetic data) or the iMac. The hierarchical model needs a sampler (for example `numpyro` or
  `pymc`) that is not in `requirements.txt`; adding it there changes what every existing workflow installs, so the
  design default is a separate `requirements-manhattan.txt`.

## 14. Two wording fixes in PROTOCOL_v3.md

**Why Ethan.** The file is protected, and any change is a new version.

Checking the formulas against the papers (MANHATTAN_PROGRESS.md, "Phase C entry criteria") found **no formula
error**. Two sentences in §5.1 say slightly more than is true, and Appendix C still says the three formulas are
"written from memory":

1. "This is the 'consistent' p-value of Hansen (2005)." The recentring is Hansen's; the finite-`B` form
   `(1 + #{T*_b ≥ T})/(B + 1)` is the protocol's own and is never smaller than Hansen's `#{T*_b > T}/B`.
   Suggested: "The recentring is that of Hansen's 'consistent' test; the p-value counts ties and adds one, which
   can only make it larger than Hansen's."
2. "...and `g(x) = x`, the latter being White's reality check". Suggested: "...and `g(x) = x`, the
   least-favourable null of White's reality check applied to the studentised statistic".
3. Appendix C, last paragraph: replace "are written from memory ... must be checked" with the sources and pages
   now recorded in MANHATTAN_PROGRESS.md.

**Do** (optional, any time before the first batch): make the three edits as version 3.0.1 with a change-log entry
"wording only; no rule changed". The simulation's results carry over: the code follows the formulas, which do
not change. Until then the text stands and the code follows it.

**Status (session 5M).** The three edits are made in the draft `PROTOCOL_v3.1.md` (§5.1 and Appendix C), with
the change-log entry "wording only; no rule changed". PROTOCOL_v3.md itself is not edited. Adopting 3.1 (item 19)
closes this item; nothing else is needed.

## 15. The model-fitting half of the simulation cannot be run as pre-registered

**Why Ethan.** The ways out are spending, a new pre-registration version or a new protocol version. Each is yours.

**What was found (session 4M, measured).**

- **The model as written does not mix.** Sampled directly, the spike-and-slab term `δ_h` gives `R̂` about 3.5
  and an effective sample size near 1. The code now samples the same model in other coordinates (exact changes of
  variable), which fixes that. This is a change of sampling coordinates, not of the model.
- **Cost.** After that fix and a seven-fold speed-up of the likelihood, one gradient at HB size (240 families)
  costs about 0.8 ms and an iteration uses at least the sampler's 127 steps. From that, one fit at the default
  budget (4 chains, 1,000 warm-up, 1,000 kept draws) should take about 14 CPU-minutes and a replication (four
  reviews of six fits) about 4.5 CPU-hours. **The measured run was worse:** one pilot replication of D10 with
  the sampler at a fifth of the default budget (200 and 200) was stopped unfinished after 2 hours 31 minutes of
  CPU time. At the default budget a replication therefore costs well over 10 CPU-hours. SIM_PREREG fixes 400
  replications for each of 12 HB scenario runs (5 development, 7 held-out): **of the order of 50,000 CPU-hours
  or more**, most of a year of an 8-core iMac running day and night. A replication count may not be lowered by
  amendment (SIM_PREREG §8.4).
- **The convergence gate.** Protocol §7.2(c) asks `R̂ ≤ 1.01` for **every** parameter (about 1,500 at HB size)
  and an effective sample size of at least 400. On small test problems with short chains the gate fails, as it
  should; whether the default budget meets it at full size is **not known**, because no full-size fit at the
  default budget was completed.

**Default in force.** Nothing that rests on the model is switched on: no posterior-based tier ("Promising" by
route (b), "Statistically supported"), no dormancy, no calibration claim (SIM_PREREG §8.1 rule 2). The screening
route and the forward test do not depend on it and can go ahead (item 16).

**Options.**

| option | what it means | cost |
|---|---|---|
| (a) buy compute | run the HB scenarios as pre-registered on rented machines (of the order of 50,000 CPU-hours or more) | spending: not priced; at that many core-hours it is likely thousands of US dollars; price it before deciding; your call (item 8) |
| (b) pre-registration version 2 for the HB part | fewer replications or fewer review dates for V6-V8, written before any HB confirmation run. No HB criterion has been evaluated, so no pass is voided; the STD and LONG part is untouched | none; lower precision than 1.0 promised |
| (c) protocol 3.1: a cheaper model | for example one fit per review with the sensitivity versions by importance re-weighting, or a gate on the quantities actually used (`θ_f` and the hyperparameters). A new version, then the simulation on it | none; more design work first |
| (d) wait | run STD and LONG now (item 16); decide after seeing whether the screening and forward routes alone give you what you want | none |

**Recommendation.** (d) now, then (b) with (c)'s gate change if the middle tiers still matter to you. The first
batches can run on the screening route and the forward test alone.

**Status (session 5M): option (c) is drafted, in a stronger form than a cheaper sampler.** `PROTOCOL_v3.1.md` §7
replaces the sampled model by an analytic normal-normal hierarchical model: closed-form posteriors summed over a
fixed grid of hyperparameters, no sampler and so no convergence gate. The cost numbers are in section 16 below.
No replication count is lowered and no threshold is changed (`SIM_PREREG_v2.md`). The sampled model stays in the
repository as an optional check beside a real review that decides nothing. Adopting it is item 19. **What the
model-fitting pilot then showed about the tier and dormancy rules is new and is yours to weigh**: see
MANHATTAN_PROGRESS.md, "Milestone C: state (session 5M)".

## 16. Run the simulation on the iMac

**Why Ethan.** It is your machine, and the full run is far more than a cloud session can do.

**What exists.** Two pilots, both labelled as such and deciding nothing: version 1's
(`results/manhattan_sim/PILOT_REPORT.md`) and the rerun of the parts Protocol v3.1 changed
(`results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`). The full run is packaged, and after item 19 it covers
**everything**, the model-fitting half included:

```bash
MANHATTAN_VENV=~/.venvs/manhattan scripts/manhattan_sim_run.sh      # resumable
python -m manhattan.sim.run --status --prereg v2                     # progress and heartbeat
```

By default the script runs version 1 for everything version 1 still governs (15 runs at STD and 2 at LONG, by
version 1's unchanged code, continuing the pilot replications already on file) and version 2 for what Protocol
v3.1 changed: D11 with the hedge re-estimated in every bootstrap resample, its nine hedged twins, and the five
HB scenarios with the analytic model. `SIZES=STD,LONG` leaves the HB scenarios out; `PREREG=v1` runs version 1
alone.

**How long.** About **1,500 to 1,750 CPU-hours: roughly 9 to 10.5 days on 8 cores** (seven workers), from the
seconds per replication the pilots measured:

| part | runs × replications | seconds per replication | CPU-hours |
|---|---|---|---|
| version 1's code: STD and LONG except D11 | 17 × 2,000 | 60 to 150 on an idle core (pilot: 67 to 355 on a busy one) | 950 to 1,190 |
| D11 with the hedge-aware test | 1 × 2,000 | about 370 | about 200 |
| nine hedged twins, SPA only | 9 × 400 | 210 to 600 | about 300 |
| five HB scenarios, analytic model | 5 × 400 | 70 to 150 | about 50 |

Before Protocol v3.1 the estimate was about 5 days for the STD and LONG half and of the order of 50,000
CPU-hours for the HB half, which could not be run. The new work adds about 450 CPU-hours (D11's re-estimation
and the twins) and the HB half now costs about 50. If the twins' cost matters: they are 400 replications each
by SIM_PREREG_v2 §6, a number that is yours to change before adopting (200 would still meet the precision
target many times over, and a twin could run the hedge-aware test alone, which is about two thirds of its
cost).

[SIM_RUNBOOK.md](SIM_RUNBOOK.md) has the set-up, the launchd job and what to do when it finishes. It never runs
a held-out scenario.

**Do.** Item 19 first. Then run it, commit `results/manhattan_sim/` on a branch and open a pull request. The
next session then codes the held-out worlds (H01 to H12) and prepares confirmation run 1 (you tag the commit
`manhattan-sim-confirm-1`).

**If you would rather not use the iMac:** GitHub Actions is possible in principle (synthetic data, public
results), but at 6 hours per job it needs a few hundred jobs; a workflow is yours to add.

## 17. The simulation's sampler in requirements

`numpyro` and `jax` are in a separate `requirements-manhattan.txt`, so no existing workflow installs anything
new, and the tests of the sampled model skip where they are absent. Under Protocol v3.1 the simulation no longer
needs them: the analytic model uses numpy and scipy only, and its tests always run. If you want those tests to run in CI, add
`-r requirements-manhattan.txt` to the pull-request test workflow (a workflow change, so yours). The six-model
end-to-end test is opt-in (`MANHATTAN_SLOW_TESTS=1`) because it compiles twelve models.

## 18. Housekeeping: the pre-rename branch

The branch the project lived on before it was renamed (its name is in MANHATTAN_PROGRESS.md, "Rename"; it was
superseded by `build/manhattan` and PR #48) is still on the remote. Agents do not delete branches (hard rule 11).
Delete it on GitHub's Branches page when convenient.

## 19. Adopt Protocol v3.1 and version 2 of the simulation pre-registration

**Why Ethan.** Changing the protocol is yours (PROTOCOL §10.5), and the files that would hold the change are
protected, so a session wrote **new** files beside them and edited none of the protected ones.

**What was written (session 5M, pull request from `build/manhattan`).**

| new file | what it is |
|---|---|
| `docs/manhattan/PROTOCOL_v3.1.md` | the whole protocol, version 3.1.0: 3.0.0 with four changes, listed at its top with the pilot result behind each and why none is tuning to held-out results |
| `docs/manhattan/SIM_PREREG_v2.md` | how the changed methods are tested. Only the changed parts; version 1 stays in force for the rest. No threshold loosened, no replication count lowered |
| `docs/manhattan/sim_prereg_v2.sha256` | the SHA-256 of the two files above (two lines of `sha256sum` output) |
| `manhattan/prereg_v2.py`, `tests/test_manhattan_prereg_v2.py` | the check of that record (`python -m manhattan.prereg_v2 verify`, which also runs version 1's check) and its test |

**Protected files: what you must do to each.**

| protected file | action |
|---|---|
| `docs/manhattan/PROTOCOL_v3.md` | **none.** It stays 3.0.0, byte for byte (a test checks its hash) |
| `docs/manhattan/SIM_PREREG.md`, `docs/manhattan/sim_prereg.sha256` | **none.** Version 1 stays frozen and in force for everything version 2 does not name; `python -m manhattan.prereg verify` still passes |
| `config/manhattan.yaml` | **none.** `claims.enabled` stays `false`; no switch refers to a protocol version |
| `manhattan/prereg.py`, `tests/test_manhattan_prereg.py` | **none.** The version 2 record is checked by the new module beside them |
| `.github/CODEOWNERS` | **add five lines** (step 3 below). This is the only edit of a protected file |

Nothing has to be copied or moved: the new files are already at their final paths.

**Steps, in order.**

1. **Read** the table at the top of `PROTOCOL_v3.1.md` ("What changed from 3.0.0, and why"), then
   `SIM_PREREG_v2.md` (it is short), then `results/manhattan_sim/v2/PILOT_RERUN_REPORT.md`.
2. **Merge the pull request** if you accept them. To change anything first, edit the draft on the branch and
   then **re-hash** (the hash record must be rewritten whenever either file changes, even by a comma):

   ```bash
   sha256sum docs/manhattan/SIM_PREREG_v2.md docs/manhattan/PROTOCOL_v3.1.md > docs/manhattan/sim_prereg_v2.sha256
   python -m manhattan.prereg_v2 verify          # must print: pre-registrations ok (v1 and v2)
   ```

   A pilot run made before such an edit names the old hash; the report says so in its header. Pilots decide
   nothing, so nothing is lost.
3. **Protect the adopted files.** On main, add these lines to `.github/CODEOWNERS`, **inside** the protected
   block: paste them on the line just above `# protected:end`, after the `/config/manhattan.yaml @EthanC100`
   line. Copy them exactly:

```
# Manhattan, version 2 of the simulation pre-registration and Protocol v3.1 (docs/manhattan/ETHAN_ACTIONS.md
# item 19): the two frozen files, their recorded hashes, and the code and the test that check them
/docs/manhattan/PROTOCOL_v3.1.md @EthanC100
/docs/manhattan/SIM_PREREG_v2.md @EthanC100
/docs/manhattan/sim_prereg_v2.sha256 @EthanC100
/manhattan/prereg_v2.py @EthanC100
/tests/test_manhattan_prereg_v2.py @EthanC100
```

4. **Check.**

   ```bash
   python -m manhattan.prereg_v2 verify                                   # pre-registrations ok (v1 and v2)
   python -m nightshift.protected docs/manhattan/PROTOCOL_v3.1.md docs/manhattan/SIM_PREREG_v2.md \
       docs/manhattan/sim_prereg_v2.sha256 manhattan/prereg_v2.py tests/test_manhattan_prereg_v2.py
   # prints PROTECTED: for each of the five and exits 1
   ```

   The second command was checked on a copy of CODEOWNERS with the lines added
   (`tests/test_manhattan_prereg_v2.py`): the five paths match, and no other file of this revision does.
5. **Run** the simulation (item 16).

**What adopting does and does not do.** It makes 3.1.0 the protocol under test and lets the full run include D11
and the model-fitting half. It enables no claim: `claims.enabled` stays `false` until a confirmation run passes.
From the first batch frozen afterwards, manifests record the hash of PROTOCOL_v3.1.md (PROTOCOL §10.1-10.2); no
batch exists yet, so nothing is judged under two versions.

**If you do not adopt.** Version 1 and Protocol 3.0.0 stand as they are. D11 then goes to the full run with a
test the pilot shows to be oversized, and the model-fitting half stays out of reach (item 15).

## 20. Access to em-macro-data for the futures half of milestone E

**Why Ethan.** Which repositories a session may attach is a permission setting (hard rule 11), and the data are
licensed (hard rule 7; Norgate Personal Use).

**What happened (session 5M).** Milestone E's reproduction step asks for time-series momentum and carry to be
reproduced on exploration dates before anything new is evaluated. On **public** data that is done: the engine
reproduces the frozen carry benchmark and the frozen T01 trend signal on six currencies, 2005 to 2019
(`results/manhattan_engine/REPRODUCTION.md`). The **published** results, and the repository's own futures
sleeves (trials T20 to T22), are about dozens of futures markets, whose history is the Norgate snapshot in
em-macro-data. The session asked to attach em-macro-data read-only; the environment reported the repository as
attachable, and the attach itself was **refused by the session's permission settings**. The session did not
look for another way in, and stopped there, as its brief said.

**What it blocks.** The futures half of the reproduction (criterion E-08 is met for currencies only), and every
commodity and financial-futures core factor of [CORE_FACTORS_PROPOSAL.md](CORE_FACTORS_PROPOSAL.md).

**Options.**

| option | what it means |
|---|---|
| (a) allow a build session to attach em-macro-data read-only | a permission rule for `add_repo` in the session's settings (the night-shift tasks already have em-macro-data read). The session would read the Norgate snapshot up to 2019-12-31 only, write nothing to em-macro-data, and keep every per-market series out of this repository |
| (b) run the futures reproduction on the iMac | where the licensed data already live (item 4); the engine and the reproduction module run there unchanged once a futures loader is written |
| (c) leave it | Manhattan's first families are then limited to currencies, the one asset class whose core factors can be built from public data |

**Recommendation.** (a) for the reproduction (it reads history up to 2019 only, which any session may read), (b)
for anything on the reserve or forward. Either way a futures loader must be written first: it reads each contract
file from the top and stops at the cut-off, as `manhattan/factors/public_fx.py` does for the public panel.

