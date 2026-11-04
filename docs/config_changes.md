# Configuration and operations changes

Dated notes on changes to how the project is run (workflow, schedule, data sources, dependencies). Strategy
changes are not made here; the frozen design is recorded in `v1.0_freeze.md`.

## 2026-11-04: November 2026 rebalance ran late

- **Scheduled:** 3 Nov 2026, 07:23 UTC (the monthly `systematic-monthly` workflow, positions as of Oct 2026,
  effective Nov 2026).
- **What happened:** the scheduled run failed in the data refresh when mindicador.cl (Chile dollar series)
  answered HTTP 502 after four tries. A manual re-run on 4 Nov 2026 refreshed the data in 7 minutes but failed
  in the overlay step with `ModuleNotFoundError: No module named 'yaml'` (`pyyaml` was missing from
  `requirements.txt`). Neither run committed positions.
- **Actual run:** 4 Nov 2026, one day late, from a manual run of the workflow on branch
  `claude/refresh-external-downloads-js0m77` after the fixes below (see `results/systematic/rebalance_log.csv`,
  which records `scheduled_date` and `run_date` for this and every later rebalance).
- **Fixes:** retries with backoff and a stale-copy fallback for every download, the raw download cache kept
  between runs, `pyyaml` added, the hash test adjusted so it no longer pins files the workflow rewrites, a
  failure alert issue, and the rebalance log. Details in `v1.0_freeze.md`, "Logged infrastructure fixes".
