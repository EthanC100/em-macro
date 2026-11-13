# Manhattan simulation: how to run it

For the full pre-registered run of the **development scenarios** on the iMac (or any machine with Python 3.11+).
Everything is synthetic: no licensed data, no market data, no secret, no network after the install.
State of the work and what the pilots showed: [MANHATTAN_PROGRESS.md](MANHATTAN_PROGRESS.md), "Milestone C: state".

Two pre-registrations are in play. [SIM_PREREG.md](SIM_PREREG.md) (version 1) is frozen and governs everything it
always did, except the two parts the pilot showed must be repaired first. [SIM_PREREG_v2.md](SIM_PREREG_v2.md)
(version 2) governs those two parts, tested with [PROTOCOL_v3.1.md](PROTOCOL_v3.1.md): the SPA test where the
core hedge is estimated, and the hierarchical model. **Version 2 and Protocol v3.1 are drafts until Ethan adopts
them** ([ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 19). The script runs both by default.

## 1. What is ready to run, and what is not

| part | pre-registration | ready? | size of the job |
|---|---|---|---|
| Development scenarios at **STD and LONG**, except D11 (17 runs × 2,000 replications): screening candidates, SPA, Romano-Wolf, forward e-LOND | version 1, by its unchanged code; the 192 pilot replications on file count | **yes** | 60 to 150 seconds per replication on one idle core (the pilot's 67 to 355 were measured on a busy machine); about **950 to 1,190 CPU-hours** |
| **D11** (1 run × 2,000): the same pipeline with the hedge re-estimated in every bootstrap resample | version 2 | **yes**, after item 19 | about 370 seconds per replication (the pipeline plus three SPA tests on the same resamples); about **200 CPU-hours** |
| **Hedged twins** D01h to D08h (9 runs × 400): the SPA test only | version 2 | **yes**, after item 19 | 210 to 600 seconds per replication (measured: 290, 260, 304, 207, 291, 251, 305, 246 and 599); about **300 CPU-hours** |
| Development scenarios at **HB** (5 runs × 400): the analytic hierarchical model, tiers, dormancy | version 2 | **yes**, after item 19 | 70 to 150 seconds per replication, 16 seconds for the six fits of a review; about **50 CPU-hours** |
| Held-out scenarios (H01 to H12) and the confirmation run | both | **no**: their worlds are not coded, and they may run only from a tagged commit after the development criteria are met | - |

In all: about **1,500 to 1,750 CPU-hours**: roughly **9 to 10.5 days on 8 cores** with seven workers (the script's default leaves one core free). The measured figures are from pilots on a 4-core machine with four workers, and version 1's share is the uncertain one: its pilot ran on a busier machine. Before Protocol v3.1 the STD and LONG half alone was about 5 days and the HB half could not be run at all.

## 2. Set up once

```bash
git clone https://github.com/EthanC100/em-macro && cd em-macro
git checkout main                              # after the pull request with Protocol v3.1 is merged
python3 -m venv ~/.venvs/manhattan && . ~/.venvs/manhattan/bin/activate
pip install -r requirements.txt                # all the simulation needs: numpy, scipy
python -m manhattan.prereg_v2 verify           # must print: pre-registrations ok (v1 and v2)
python -m pytest -q tests/test_manhattan_stats.py tests/test_manhattan_spa_hedged.py \
    tests/test_manhattan_hier_analytic.py tests/test_manhattan_sim_pipeline.py tests/test_manhattan_v2.py
```

`requirements-manhattan.txt` (the sampler) is **not** needed any more: the model is fitted in closed form.

## 3. Run

```bash
MANHATTAN_VENV=~/.venvs/manhattan scripts/manhattan_sim_run.sh         # everything, all cores but one
```

- **It can be stopped at any time** (Ctrl-C, sleep, power cut) and started again with the same command. Every
  finished replication is already on disk (`results/manhattan_sim/reps/` for version 1's runs,
  `results/manhattan_sim/v2/reps/` for version 2's); a restart runs only what is missing. A replication count is
  never lowered and a run is never cut (SIM_PREREG §6).
- One instance at a time: a second start exits with code 75 while the first is alive.
- On macOS it runs under `caffeinate -i`, so the Mac does not sleep while it works.
- Options, as environment variables: `WORKERS=6`; `SIZES=STD,LONG` (leave the HB scenarios out), `SIZES=HB`;
  `OUT=/some/dir`; `PREREG=v1` (version 1 alone, as before this revision: D11 with the 3.0 test, no twins, and an
  HB half that needs the sampler and cannot be afforded).
- Order: the STD runs (D11 among them), the LONG runs, the twins, then the HB runs.
- To let it restart by itself after a crash or a reboot, install the launchd job:
  `scripts/com.horizons.manhattan.sim.plist.template` (instructions inside). It stops being restarted once the run
  has finished.

## 4. Watch

```bash
python -m manhattan.sim.run --status --prereg v2    # replications on file per run, and which code runs it; exit 1 if the heartbeat is stale
tail -f results/manhattan_sim/logs/run_*.log
```

The heartbeat (`results/manhattan_sim/heartbeat.json`) is rewritten after every replication. `--status` calls it
stale after 90 minutes without one (`--stale-minutes` changes that). A cron line such as
`*/30 * * * * cd ~/em-macro && python -m manhattan.sim.run --status --prereg v2 || osascript -e 'display notification "Manhattan simulation is silent"'`
is a sufficient watchdog for this job; the full runner package with a remote watchdog is milestone H.

## 5. When it finishes

The script then checks criterion V10(a), gzips the completed replication files and writes two reports, each with
every metric, its interval, its threshold and pass or fail:

- `results/manhattan_sim/REPORT.md`: version 1's runs (everything at STD and LONG except D11);
- `results/manhattan_sim/v2/REPORT.md`: D11, the twins and the HB scenarios under version 2.

1. Read both. A **FAIL** on a required criterion means the method is revised (a new protocol version) and tested
   again; a threshold is never changed to make it pass (SIM_PREREG §8.1).
2. **Twins.** A twin's row "95% half-width of the hedge-aware size" must read "met". If one reads "not met:
   continue the run", run the script again with `REPS_TWIN=800` (then 1,200, and so on): it continues, it does not
   restart (SIM_PREREG_v2 §6).
3. Commit `results/manhattan_sim/` on a branch and open a pull request (synthetic numbers; safe in a public
   repository). Never push to main.
4. Tell the next Manhattan session. It writes the held-out worlds and prepares confirmation run 1; you tag the
   commit `manhattan-sim-confirm-1`. Until that tag exists the runner refuses every held-out scenario and logs the
   refusal.

## 6. The model-fitting (HB) runs

Under version 2 they are ordinary runs: a replication is one simulated programme of 240 families, **reviewed
every 63 trading days, 40 times** (SIM_PREREG_v2 amendment 1: production's cadence, in place of version 1's four
dates), with six closed-form fits at every review. That is ten times the fits of the four-date pilots, which
took 68 to 149 seconds a replication. One replication of the dearest scenario (D08) with quarterly reviews took
20 minutes on one core of the session's machine while other jobs ran (1,201 seconds, 1,148 of them the model;
18 to 40 seconds for the six fits of a review; 31 seconds for all the forecasts) and **3.3 GB of memory at its
peak**: the first reviews are the dearest, because the grid is widest where there are fewest families to narrow
it. On a 16 GB machine run the HB scenarios with three or four workers (`WORKERS=3 SIZES=HB`), after
`SIZES=STD,LONG` with seven.

The sampled model of Protocol 3.0 (`manhattan/stats/hier.py`, `manhattan/sim/hb.py`) is still in the repository
and is **not** part of this run. It cost well over 10 CPU-hours a replication (of the order of 50,000 CPU-hours
for the pre-registered runs), which is why Protocol v3.1 replaced it. It can be tried on one replication as a
check that decides nothing:

```bash
pip install -r requirements-manhattan.txt
MANHATTAN_SIM_SAMPLER=100,100 PREREG=v1 SIZES=HB REPS_HB=1 LABEL=pilot scripts/manhattan_sim_run.sh     # hours
```

## 7. What every run records

`results/manhattan_sim/runs.jsonl` gets a start record and an end record for every call, with the commit, the
protocol hash, the pre-registration hash, the scenario, the size, the replications, the seeds and the status; a
run of a part version 2 changed also names version 2's hash and Protocol v3.1's. A start with no end is a run
that died. Each replication record carries the hash of the simulation code that made it; replications made by
different code are never pooled. Version 1's code files (`manhattan/stats/` as it was, `manhattan/sim/world.py`,
`pipeline.py`, `seeds.py`) are untouched by version 2, so version 1's records keep counting; a change to any of
them, or to version 2's files (`spa_hedged.py`, `pipeline_v2.py`, `hier_analytic.py`, `hb_v2.py`), starts the
counts of the runs that use it again from zero.

## 8. On GitHub's runners instead of the iMac

`.github/workflows/manhattan-sim.yml` makes the same development run on GitHub's public runners (4 cores and 16
GB each, free for a public repository, six hours a job), in **pieces**: one scenario and a range of replication
numbers per job. It was written by session 10M and **has never been started**: no session dispatches it. It is
started by hand only, has no schedule, reads no repository secret, writes nothing to the repository, and every
job is guarded to `main`. **GitHub offers the "Run workflow" button only for a workflow file that is on the
default branch, so the pull request that adds the file must be merged to main first.** Item 19 of
ETHAN_ACTIONS.md (adoption) comes before it, as for the iMac.

**Start it** (after the merge):

1. GitHub, the repository's **Actions** tab, **manhattan-sim** in the list on the left, **Run workflow**, branch
   **main**, leave the three inputs as they are, **Run workflow**. (From a terminal:
   `gh workflow run manhattan-sim.yml --ref main`.)
2. The **plan** job (a few minutes) checks both pre-registrations against their hashes and cuts what is missing
   into pieces: every replication of the pre-registered counts that is not on file for the code of that commit.
   The pilot replications already in the repository count and are not run again. Its summary says how many
   pieces and how many core-hours it expects.
3. The **piece** jobs run, 20 at a time. A piece stops starting replications after 285 minutes, finishes those in
   progress and uploads its records, whatever happened, as the artifact `manhattan-sim-piece-<scenario>-<size>-<first>-<last>`.
4. The **collect** job puts every piece together with `python -m manhattan.sim.collect merge` (it refuses records
   of other code, of another review step, of a replication outside the count, or that disagree with another
   record of the same replication), writes a table of what is still missing to the run's summary, and uploads
   the record files as the artifact `manhattan-sim-results`. It is red while anything is missing.

**If pieces are red** (ran out of time on a slow runner, or failed): on the run's page, **Re-run failed jobs**.
Each piece first downloads its own earlier artifact and continues from it; then the collect job runs again.

**If the plan said "N pieces left for a later run"** (a workflow run holds at most 256 jobs), or to continue on
another day: start the workflow again with the input **earlier_runs** set to the id of the earlier run (the
number in its URL; several ids separated by commas). It downloads those runs' pieces, counts them, and plans
only what is still missing. Artifacts are kept for 90 days.

**Bring the records home** when the collect job is green. On a checkout of the same commit of main:

```bash
gh run download <run id> --pattern 'manhattan-sim-piece-*' --dir /tmp/manhattan-pieces
python scripts/manhattan_sim_collect.py merge /tmp/manhattan-pieces     # checks every record again; appends to results/manhattan_sim
python scripts/manhattan_sim_collect.py status                          # must print: Every run is at its pre-registered count.
python -m manhattan.sim.run --v10a
python -m manhattan.sim.run --compact --prereg v2
python -m manhattan.sim.report --prereg v2 && python -m manhattan.sim.report_v2
```

(With several runs, download each run's pieces into its own directory under `/tmp/manhattan-pieces`; a later
run's `manhattan-sim-piece-earlier-runs` artifact already holds the earlier ones.) Then section 5 above: commit
`results/manhattan_sim/` on a branch and open a pull request. The workflow itself commits nothing.

**Size.** With the timings on file the plan is a little over 256 pieces and of the order of 800 runner-hours, so
about two days at 20 jobs at once, and probably a second run for the last pieces. Those are estimates from this
repository's pilot timings, most of them measured on a busy machine, and from an assumed runner speed; the plan
job's summary gives the figure for the commit it runs from. A piece is sized to 60% of what its job could do at
the timings' speed, so a slower runner still finishes most pieces, and one that does not is continued by
"Re-run failed jobs". HB pieces use three workers, not four: an HB replication with quarterly reviews peaks at
3.3 GB.

**The same thing on any machine.** A piece is one command, and pieces made anywhere can be merged:

```bash
python -m manhattan.sim.run --prereg v2 --scenario D05 --size HB --first 100 --reps 150 --label part \
    --workers 3 --time-budget-minutes 285 --out /tmp/piece-D05-HB-100      # exit code 75: out of time, run it again
python -m manhattan.sim.collect plan          # the pieces still missing, as JSON
```

What the workflow does not do: it runs no held-out scenario (none is coded, and the runner refuses them outside a
tagged confirmation run), it does not run `--v10a`, and it builds no report.
