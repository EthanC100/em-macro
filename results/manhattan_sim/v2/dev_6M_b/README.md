# Development experiments of session "6M Manhattan C: dormancy fix and statistical checks" (2026-11-13)

**Synthetic data only. Development scenarios only (seed branch 0). No held-out scenario was coded or run.** These
scripts were run outside the runner, as SIM_PREREG section 3 allows; each experiment is a note in
`results/manhattan_sim/runs.jsonl` (`note-6Mb-01` to `note-6Mb-04`). They decide nothing, and none of them edits
the pipeline: they import it.

This is the second of two sessions that worked on the dormancy rule. The rule on the branch, its diagnosis and
its pilot are the first session's (`../DORMANCY_DIAGNOSIS.md`, `../PILOT_RERUN2_REPORT.md`). What is here is a
second, independent diagnosis, the extra diagnostics, and an alternative rule measured beside the branch's.

| file | what it does | output kept |
|---|---|---|
| `trace_hb.py` | one HB replication exactly as session 5M's pilot ran it (same seeds and streams, the dormancy rule of 3.0), keeping every family's six posterior probabilities, forecasts, forward estimate and tier state at every review, and the same forecast under other assumptions | the traces are not committed (48 files, 10 MB); `python trace_hb.py trace D02 0` recreates one in about a minute |
| `analyse_traces.py` | replays the tier state machine on the traces with one part of the rule of 3.0 changed at a time | `replay_table.txt` |
| `who.py` | which families with an edge the rule of 3.0 retired, and what it saw when it did | `who.txt` |
| `calib.py` | the central model's reliability curve by year, who is in each bin, and a two-group prior fitted to the same estimates as a check of the cause | `calib.txt` |
| `own_record.py` | the alternative dormancy rule (the forecast and the family's own forward record). **Not adopted; nothing in the package imports it** | - |
| `paths.py` | the branch's HB pipeline, imported unchanged, with the tiers stepped four ways on the same fits: the rule on the branch, the rule of 3.0, the alternative, no dormancy | `paths_4_dates.jsonl`, `paths_yearly.jsonl` (one record per replication) |
| `second_look.py` | `../DORMANCY_SECOND_LOOK.md` from those records and the traces | - |
| `compute_options.py` | `../COMPUTE_OPTIONS.md` from `../benchmark.json` and the seconds per replication on file | - |

The scripts expect the repository root on `PYTHONPATH`; `analyse_traces.py`, `who.py` and `calib.py` expect
`trace/` beside them. Checks that these are the pilots' own worlds and fits: the traces reproduce session 5M's
counts of retired families exactly (7 of 42, 25 of 140, 102 of 944, 18 of 123), and `paths.py`'s "branch" path
reproduces the pilot of record replication by replication (the count is printed in `../DORMANCY_SECOND_LOOK.md`).

`replay_table.txt`'s rows "and p^F < 0.05" are the alternative; its rows "and Pi^max < 0.05" are close to the
rule on the branch but not identical to it (the branch's rule also asks for 252 forward days at each review).
