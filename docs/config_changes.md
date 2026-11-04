# Configuration and operations changes

Dated notes on changes to how the project is run (workflow, schedule, data sources, dependencies). Strategy
changes are not made here; the frozen design is recorded in `v1.0_freeze.md`.

## 2026-11-04: November 2026 rebalance ran late

- **Scheduled:** 3 Nov 2026, 07:23 UTC (the monthly `systematic-monthly` workflow; positions as of Oct 2026,
  effective Nov 2026).
- **Actual run:** 4 Nov 2026, 04:06 to 04:09 UTC, one day late
  ([run 4](https://github.com/EthanC100/em-macro/actions/runs/41771158747), a manual run of the workflow on
  branch `claude/refresh-external-downloads-js0m77` after the fixes below; commit `bd236f9`, "Monthly systematic
  update 2026-11-04"). `results/systematic/rebalance_log.csv` records it as `scheduled_date 2026-11-03,
  run_date 2026-11-04, LATE by 1 day`, and `positions.csv` carries the same two dates. Later rebalances are
  logged there the same way.
- **What went wrong, in order:**
  1. 3 Nov, scheduled run: the data refresh stopped when mindicador.cl (Chile dollar series) answered HTTP 502
     after four tries over 30 seconds.
  2. 4 Nov, re-run of the same workflow: the refresh succeeded but the overlay step stopped on
     `ModuleNotFoundError: No module named 'yaml'` (`pyyaml` was missing from `requirements.txt`).
  3. 4 Nov, first run of the fixed branch: BCB's SGS API answered 200 with a non-JSON body, which the downloader
     accepted. This opened alert issue #4 automatically.
  4. 4 Nov, second run of the fixed branch: api.imf.org answered 401 for a few minutes on one of the 91 WEO
     requests. The alert step commented on issue #4.
  5. 4 Nov, third run: succeeded; the workflow closed issue #4.
- **Fixes:** retries with backoff for connection errors, timeouts, 401/403/429, 5xx and bodies that fail a
  check; a per-host limit so a source that is down costs about a minute; a stale-copy fallback (raw downloads
  kept in the Actions cache, kept alive twice a week, and the IMF WEO files committed); `EM_MACRO_REFRESH=1` on
  the refresh step so every loader re-downloads first; `pyyaml` added; the hash test no longer pins files the
  workflow rewrites; the failure alert issue; the rebalance log. Details in `v1.0_freeze.md`, "Logged
  infrastructure fixes".

**2026-11-04, live-record start rule:** the v1.0 live record starts with the November 2026 rebalance (first rebalance after the 3 Nov 2026 freeze, positions effective 2026-11), so the Ledger counts live months, live Sharpe, live drawdown and track-record progress from 2026-11 only; October 2026 (after the 2020-01 to 2026-09 test, before the freeze) is a pre-live gap month, shown on charts as "pre-live (not counted)" and excluded from the live and backtest statistics (`LIVE_START_MONTH` in `ledger/build.py`).

## 2026-11-04: Ledger automation (branch `build/automation`)

- **New workflows:** `ledger-daily` (05:52 UTC daily: marks, auto-resolver, `[RESOLVE?]` issues; shares the
  `ledger-intake` concurrency group so the ledger files are edited by one job at a time) and `ledger-screener`
  (by hand). `systematic-monthly` gained a "Ledger screener" step after the overlay (continue-on-error) and
  commits `results/screener/` and `data/ledger/reports/`. `ledger-intake` posts the Risk Manager check as a
  comment and runs `tests/test_automation.py`.
- **Forms:** the Decision form has a required Position type (continuous position / event bet); the Forecast
  form a required Resolution source. `decisions.csv` gained `position_type`, `forecasts.csv`
  `resolution_source` (F001-F005: "AP race call").
- **New files:** `data/ledger/instruments.csv`, `marks.csv`, `automation_log.csv`, `api_log.csv`,
  `data/events/rating_calendar.csv`, `results/screener/`, `ledger/automation.json`, `docs/todo.md`.
- **API:** only the event-forecast resolver calls the Anthropic API (model `claude-sonnet-5-5` in
  `ledger/automation.json`, 10 calls a day, key from the `ANTHROPIC_API_KEY` secret; without it event forecasts
  get a `[RESOLVE?]` issue and nothing fails). The `anthropic` package is installed by `ledger-daily` only.
- **Data-source decisions (made under the brief's rules):** France and Italy 10y marked monthly (Banque de
  France's portal refused the build session's connections; the ECB publishes country yields monthly only; Banca
  d'Italia needs a session); Indonesia, Colombia and Chile 10y monthly from the panel (no keyless daily source;
  the BCCh API needs a login); Turkey and Indonesia FX from the ECB reference rates (the CBRT API needs a key,
  Bank Indonesia has no open API); Yahoo and Stooq not used (rate-limited or blocked). No strategy code,
  parameter or hashed file changed.
