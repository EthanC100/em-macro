# Manhattan: what only Ethan can do

Recorded 2026-11-12. Each item is something no agent may decide or do under the CLAUDE.md hard rules, or cannot do
from a cloud session. For each: the conservative default now in force, what it blocks, and what to do. Nothing in
this list was created, changed, bought or switched on by this session.

Order of urgency: items 13 and 3-4 unblock the next phases; item 8 has a date (about 5 May 2027); the rest can wait
until the phase that needs them.

| # | decision or action | default in force | blocks |
|---|---|---|---|
| 1 | the reserve-window fence | no reserve (`reserve.enabled: false`) | all historical screening |
| 2 | authority for Manhattan batch freezes under rule 4 | Ethan only (`freeze.authority: ethan_only`) | any freeze |
| 3 | a separate repository and environment for the blind generator | none exists; nothing is called blind | the blind channel |
| 4 | iMac setup | no runner | licensed-data evaluations, signed freezes |
| 5 | protect the frozen Manhattan files | not protected | nothing; a risk |
| 6 | confirm the rulesets on main | unknown | nothing; a risk |
| 7 | critic and generator definitions, routines | none added | the critic's "never sees outcomes" rule |
| 8 | data licences and spending | no spending | futures history after May 2027; a tool-less generator |
| 9 | programme parameters | conservative values | dormancy, live tier |
| 10 | core factor definitions | none approved | every hedged return |
| 11 | Manhattan tests inside the writers' workflows | skip there, fail elsewhere | nothing |
| 12 | Manhattan and the trial ledger | separate | nothing |
| 13 | merge this PR; go-ahead and compute for the simulation | not merged | Phase C |

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

- Merging this PR puts the pre-registration on main. From then on the simulation code may be written.
- Phase C's confirmation run is about 2,000 replications of about 40 scenario runs plus 400 replications of about
  12 model-fitting runs. Decide where it runs: GitHub Actions (public repository, so results and logs are public,
  which is fine for synthetic data) or the iMac. The hierarchical model needs a sampler (for example `numpyro` or
  `pymc`) that is not in `requirements.txt`; adding it there changes what every existing workflow installs, so the
  design default is a separate `requirements-manhattan.txt`.
