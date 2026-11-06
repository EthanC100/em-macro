# Configuration and operations changes

Dated notes on changes to how the project is run (workflow, schedule, data sources, dependencies). Strategy
changes are not made here; the frozen design is recorded in `v1.0_freeze.md`.

Configuration changes to the paper-trading set-up. These are not trials: they do not change any signal, rule,
parameter or result of a frozen strategy, and they do not get a row in `trials.csv`.

| # | date recorded | effective from | change | reason | effect on frozen results |
|---|---|---|---|---|---|
| C01 | 2026-11-03 | the 3 December 2026 rebalance | Paper capital raised from US$100,000 to US$10,000,000. | Contract-size granularity for the planned commodity futures: at US$100,000 the smallest tradeable position in a standard futures contract is a large fraction of capital, so positions could not be sized to the model's weights. | None. v1.0 sizes positions by weights (per cent of capital), and all of its performance is reported in percentages, so its frozen results (`results/systematic/test/`, `docs/v1.0_freeze.md`) are unaffected. |
| C02 | 2026-11-04 | the 3 December 2026 rebalance (positions effective 2026-12) | **v1.1 added**, run live in parallel with v1.0: v1.1 = frozen v1.0 + exactly the T18 rule (risk-unit no-trade band 0.1 × the position's risk budget and partial rebalancing w + 0.5 (w* − w), replacing v1.0's 25% relative band). v1.0 remains the frozen control. | T18 passed its pre-registered rule (4 of 4 criteria at 1x costs; `results/T16-T19_risk_batch.md`). | None. No v1.0 file, parameter, input snapshot or result changed; `python -m em_macro.verify_v1` reproduces v1.0 exactly. v1.1 has its own code, outputs and freeze record (`docs/v1.1_freeze.md`). |

## C01 — paper capital US$100,000 → US$10,000,000

- **What changes:** the notional capital against which paper positions are expressed in currency units. From the
  3 December 2026 rebalance, paper positions are sized against US$10,000,000 instead of US$100,000.
- **What does not change:** v1.0's frozen design (`results/systematic/fit/frozen_design.json`), its code
  (`em_macro/systematic.py`), its signals, sizing rule, volatility target, leverage cap, no-trade band and cost
  model. `results/systematic/positions.csv` sizes positions in per cent of capital and `results/systematic/paper_pnl.csv`
  records returns in decimal fractions; neither file depends on the capital level.
- **Reporting convention:** all performance, in every period (design 2005–2019, test 2020-01..2026-09, live paper
  trading from November 2026 (October 2026 is pre-live)), is reported in percentages of capital. A change in the capital level therefore
  changes no reported figure.
- **Classification:** configuration change, not a trial. It is not counted in N (the multiple-testing trial count in
  `trials.csv`) and does not open a new trial group.
- **Live paper record:** the October and November 2026 paper months are on the US$100,000 basis; December 2026
  onward on the US$10,000,000 basis. Because both are reported in percentages, the series is continuous.

**2026-11-04 correction to C01:** the reporting-convention line above originally read "live paper trading from
October 2026". It now reads "from November 2026 (October 2026 is pre-live)" because the live record starts with
the first rebalance after the 3 Nov 2026 freeze (positions effective November 2026; the live-record start rule
recorded below on 2026-11-04 and `LIVE_START_MONTH` in `ledger/build.py`); October 2026, after the 2020-01..2026-09
test and before the freeze, is a pre-live gap month, not a live month. Nothing else in C01 changed.

## C02 — v1.1 (v1.0 + T18) added, live in parallel with v1.0

- **What is added:** a second live paper strategy, v1.1 (`em_macro/systematic_v11.py`, freeze record
  `docs/v1.1_freeze.md`, branch `release/v1.1`). v1.1 is v1.0's frozen code, imported unchanged, with exactly the
  T18 rule as pre-registered (`docs/prereg/T16-T19_risk_batch.md` §3.3) and applied by T18's own code
  (`em_macro/t18_rebal.py`): the 25% relative no-trade band is replaced by a no-trade band in risk units
  (0.1 × the position's risk budget, on the proposed trade) and partial rebalancing (w + 0.5 (w* − w)). Nothing else
  differs.
- **Why:** T18 passed its pre-registered pass rule, 4 of 4 criteria at 1x costs. On 2020-01..2026-09 it had Sharpe
  0.92 against 0.65, max drawdown −15.4% against −18.5%, and turnover 11.6× against 19.1× a year; on the half-B
  holdout, Sharpe 0.77 against 0.72; DSR 0.739 at N = 13 against 0.619 at N = 7. v1.1 reproduces T18's committed
  results exactly (`results/systematic_v1.1/freeze/reproduction.json`).
- **What does not change:**
  - v1.0 is untouched: its design (`results/systematic/fit/frozen_design.json`), code (`em_macro/systematic.py`),
    results (`results/systematic/test/`), monthly outputs (`results/systematic/positions.csv`, `paper_pnl.csv`,
    `rebalance_log.csv`), overlay and overrides, and the workflow steps that write them.
  - v1.0 remains the frozen control, and its live record, `LIVE_START_MONTH = "2026-11"`, is unchanged.
  - `python -m em_macro.verify_v1` still reproduces v1.0 byte for byte.
- **Live record:** v1.1's starts with the 3 December 2026 rebalance (positions effective 2026-12). Its October and
  November 2026 months are pre-live, not counted (`V11_LIVE_START_MONTH` in `ledger/build.py`,
  `LIVE_START_MONTH` in `em_macro/systematic_v11.py`). The two records are kept separate and never merged.
- **Workflow:** `systematic-monthly` gained two steps after v1.0's update, rebalance log and overlay:
  - `python -m em_macro.systematic_v11 update`, which writes `results/systematic_v1.1/positions.csv`,
    `paper_pnl.csv` and `results/live_compare/turnover.csv`;
  - `python -m em_macro.systematic_v11 rebalance`, which writes `results/systematic_v1.1/rebalance_log.csv`.

  Both steps are `continue-on-error`, so a v1.1 failure cannot stop v1.0's rebalance from being committed. They
  still open or comment on the alert issue, and the success step does not close an alert while a v1.1 step failed.
- **Ledger:**
  - The Algorithm page has a "v1.0 and v1.1 side by side" section: live P&L, Sharpe, drawdown, turnover and months
    live, over each version's own record and over the common window, plus the 2020-01..2026-09 backtest of each.
    It also has a "v1.1 positions" table.
  - The Evidence page lists T18 under passed trials (marked "live as v1.1"), and v1.1 under "Live and under test"
    next to v1.0.
- **Classification:**
  - This adds a version and is not a new trial. It has no new row in `trials.csv` and does not change N: T18 is
    already counted in its family, with DSR at N = 13.
  - Paper capital (C01) applies to both versions from the same rebalance. Both report in percentages of capital.
- **Diagnostic recorded with it (not a decision):** v1.0 and v1.1 at 0.5x, 1x and 2x v1.0's costs and at the cost
  audit's central estimates (`docs/v1.1_freeze.md`, last section). v1.1's Sharpe advantage is +0.17 at the central
  estimates, +0.26 at 1x and +0.39 at 2x; it is +0.14 before costs.

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

## 2026-11-06: D001 marked at a stale monthly average; FR-DE now daily (branch `build/ledger-v2`)

- **Symptom:** the app showed D001 (short OAT / long Bund, entered 30 Oct 2026 at 159bp, stop 115bp) at
  **96.7bp, dated 30 Sep 2026, monthly**, while the French 10y OAT-Bund spread traded at about 150-166bp.
- **Wrong source:** `data/ledger/instruments.csv` row `FR-DE` was marked from `panel_monthly
  spread_vs_de_bp:FRA`. That column of `data/processed/country_month_panel.csv` is the ECB IRS (EMU convergence)
  10-year yield of France minus Germany's, as a **monthly average**. The mark took the September 2026 average
  (FR 4.44% minus DE 3.473% = 96.7bp) and dated it at the month end. The figure is correct as a September average:
  the Riksbank's daily benchmarks average 98.5bp over September. But it is not a price, and it was five weeks old.
  The spread widened from about 100bp in late September to 143bp on 1 Oct and 166bp on 30 Oct. No free daily
  French yield was reachable when the registry was built: Banque de France Webstat refused connections, its daily
  ECOFI series is archived (2025-03), Eurostat's daily convergence yields are no longer disseminated, and the
  ECB and OECD publish monthly only.
- **Fix:** `FR10Y` and `FR-DE` are now daily. `FR10Y` uses the Sveriges Riksbank SWEA API, series `FRGVB10Y`
  (benchmark 10-year OAT, keyless, one value per business day). `FR-DE` is `FRGVB10Y` minus a new leg `DE10YBM`
  (`DEGVB10Y`, the benchmark Bund from the same source and close). Neither falls back to a monthly average: if
  the Riksbank is down, the previous daily mark is carried and flagged. Daily history from 30 Oct was backfilled
  (`python -m ledger.marks --backfill 2026-10-30 --only FR-DE,FR10Y,DE10YBM`): 30 Oct 165.7bp, 2 Nov 161.4bp,
  3 Nov 161.5bp, 4 Nov 150.2bp.
- **Did anything act on the wrong mark? No.** `ledger/resolve.py` only lets marks dated on or after the
  decision date close a position (`mark_is_current`), and the 30 Sep mark predates D001's 30 Oct entry. Both
  ledger-daily runs (4 and 5 Nov) logged "0 decision(s) closed". `decisions.csv` has not changed since D001's
  entry level was added (b227651). The Risk Manager reads no mark values.
- **Could it act later? Not any more.** Once October's panel average (about 148bp, dated 31 Oct) arrived with the
  3 Dec refresh, it would have passed that date check. New rule (`mark_can_act` in `ledger/marks.py`): only a
  first-hand **daily** mark can trigger a stop or a horizon close. A monthly average, a monthly fallback, a mark
  flagged stale when fetched, or a carried-forward mark never acts. A horizon that passes with only such marks
  opens a `[RESOLVE?]` issue instead. Monthly-only instruments (IT-DE, IT10Y, ID10Y, CO10Y, CL10Y) are shown
  carried at their last mark and flagged. Tests: `test_monthly_or_carried_marks_never_stop_or_close_a_position`,
  `test_riksbank_and_jgb_parsers`.
- **IT-DE stays monthly:** the Riksbank publishes no Italian series, and no keyless daily BTP yield was found.
  Italy is therefore excluded from Janus's universe (see the Janus section).

## 2026-11-06: ledger-daily ran but committed no marks

- **Symptom:** marks were last fetched on 4 Nov 2026 at 10:10 UTC by the build session. ledger-daily showed green
  on 4 Nov (manual run, 12:42 UTC) and on 5 Nov (scheduled 05:52, started 13:31 UTC), but neither run committed.
- **Cause:** the commit step ran `git add data/ledger/marks.csv ... data/ledger/automation_log.csv
  data/ledger/api_log.csv ... 2>/dev/null || true`. The two log files are created only when the resolver first
  acts or calls the API, so neither existed. Git rejects the whole `add` when any pathspec matches nothing
  (`fatal: pathspec ... did not match any files`, exit 128), so `marks.csv` was not staged either.
  `2>/dev/null || true` hid the error, and the step printed "nothing to commit" after the marks step had
  logged "20 new or changed marks written". A failed push after four attempts would also have passed silently.
  Separately, GitHub started the 5 Nov scheduled run 7.5 hours late; scheduled runs can be delayed or dropped.
- **Fix:**
  - The commit step stages only paths that exist and fails if a changed ledger file is left unstaged or the push
    fails.
  - The two log files are committed with their headers.
  - A 09:22 UTC backup schedule was added (re-running is idempotent: marks merge per instrument and date).
  - `ledger/watchdog.py` opens **"[ALERT] Ledger marks stale"** when the newest mark is more than 2 days old and
    closes it once fresh marks are committed. It runs at the end of every ledger-daily run and from its own
    `ledger-watchdog` workflow (12:17 UTC daily), so it fires even if ledger-daily never starts.
