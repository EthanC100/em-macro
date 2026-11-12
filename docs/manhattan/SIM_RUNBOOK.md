# Manhattan simulation: how to run it

For the full pre-registered run of [SIM_PREREG.md](SIM_PREREG.md) on the iMac (or any machine with Python 3.11+).
Everything is synthetic: no licensed data, no market data, no secret, no network after the install.
State of the work and what the pilot showed: [MANHATTAN_PROGRESS.md](MANHATTAN_PROGRESS.md), "Milestone C: state".

## 1. What is ready to run, and what is not

| part | ready? | size of the job |
|---|---|---|
| Development scenarios at **STD and LONG** (18 runs × 2,000 replications): screening candidates, SPA, Romano-Wolf, forward e-LOND | **yes** | about 60-150 seconds per replication on one core; about **1,000 CPU-hours** in all (about 5 days on 8 cores). The pilot report gives the measured seconds per run |
| Development scenarios at **HB** (5 runs × 400 replications): the hierarchical model, tiers, dormancy | code runs; **cost is out of reach as specified**, see section 6 | hours per replication |
| Held-out scenarios (H01-H11) and the confirmation run | **no**: their worlds are not coded, and they may run only from a tagged commit after the development criteria are met | - |

## 2. Set up once

```bash
git clone https://github.com/EthanC100/em-macro && cd em-macro
git checkout main                              # or the branch that holds manhattan/sim
python3 -m venv ~/.venvs/manhattan && . ~/.venvs/manhattan/bin/activate
pip install -r requirements.txt                # STD and LONG need nothing else
pip install -r requirements-manhattan.txt      # only for HB (the sampler)
python -m manhattan.prereg verify              # must print: pre-registrations ok
python -m pytest -q tests/test_manhattan_stats.py tests/test_manhattan_sim_world.py tests/test_manhattan_sim_pipeline.py
```

## 3. Run

```bash
MANHATTAN_VENV=~/.venvs/manhattan scripts/manhattan_sim_run.sh         # STD and LONG, all cores but one
```

- **It can be stopped at any time** (Ctrl-C, sleep, power cut) and started again with the same command. Every
  finished replication is already in `results/manhattan_sim/reps/`; a restart runs only what is missing. A
  replication count is never lowered and a run is never cut (SIM_PREREG §6).
- One instance at a time: a second start exits with code 75 while the first is alive.
- On macOS it runs under `caffeinate -i`, so the Mac does not sleep while it works.
- Options, as environment variables: `WORKERS=6`, `SIZES=STD` (or `LONG`, `HB`), `OUT=/some/dir`.
- To let it restart by itself after a crash or a reboot, install the launchd job:
  `scripts/com.horizons.manhattan.sim.plist.template` (instructions inside). It stops being restarted once the run
  has finished.

## 4. Watch

```bash
python -m manhattan.sim.run --status           # table of replications on file; exit code 1 if the heartbeat is stale
tail -f results/manhattan_sim/logs/run_*.log
```

The heartbeat (`results/manhattan_sim/heartbeat.json`) is rewritten after every replication. `--status` calls it
stale after 90 minutes without one (`--stale-minutes` changes that). A cron line such as
`*/30 * * * * cd ~/em-macro && python -m manhattan.sim.run --status || osascript -e 'display notification "Manhattan simulation is silent"'`
is a sufficient watchdog for this job; the full runner package with a remote watchdog is milestone H.

## 5. When it finishes

The script then checks criterion V10(a), gzips the completed replication files and writes
`results/manhattan_sim/REPORT.md` and `summary.json`: every metric with its interval, its threshold and pass or
fail.

1. Read the report. A **FAIL** on a required criterion means the method is revised (a new protocol version) and
   tested again; a threshold is never changed to make it pass (SIM_PREREG §8.1).
2. Commit `results/manhattan_sim/` on a branch and open a pull request (synthetic numbers; safe in a public
   repository). Never push to main.
3. Tell the next Manhattan session. It writes the held-out worlds and prepares confirmation run 1; you tag the
   commit `manhattan-sim-confirm-1`. Until that tag exists the runner refuses every held-out scenario and logs the
   refusal.

## 6. The HB runs: read before starting

One fit of the hierarchical model at HB size (240 families) takes tens of minutes of one core, a review needs
six fits, and a replication has four reviews. At the pre-registered 400 replications per scenario that is tens of
thousands of CPU-hours for the development scenarios alone. The measured numbers and the options are in
[ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 15. Until that is decided, run `SIZES=STD,LONG` only. To see the HB
pipeline work on a small budget (a pilot that decides nothing):

```bash
MANHATTAN_SIM_SAMPLER=150,150 SIZES=HB REPS_HB=1 LABEL=pilot scripts/manhattan_sim_run.sh
```

## 7. What every run records

`results/manhattan_sim/runs.jsonl` gets a start record and an end record for every call, with the commit, the
protocol hash, the pre-registration hash, the scenario, the size, the replications, the seeds and the status. A
start with no end is a run that died. Each replication record carries the hash of the simulation code that made
it; replications made by different code are never pooled, so after any change to `manhattan/stats/` or
`manhattan/sim/world.py`, `pipeline.py` or `seeds.py` the counts in `--status` start again from zero.
