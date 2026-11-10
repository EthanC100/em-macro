# Configuration and operations changes

Dated notes on changes to how the project is run (workflow, schedule, data sources, dependencies). Strategy
changes are not made here; the frozen design is recorded in `v1.0_freeze.md`.

Configuration changes to the paper-trading set-up. These are not trials: they do not change any signal, rule,
parameter or result of a frozen strategy, and they do not get a row in `trials.csv`.

| # | date recorded | effective from | change | reason | effect on frozen results |
|---|---|---|---|---|---|
| C01 | 2026-11-03 | the 3 December 2026 rebalance | Paper capital raised from US$100,000 to US$10,000,000. | Contract-size granularity for the planned commodity futures: at US$100,000 the smallest tradeable position in a standard futures contract is a large fraction of capital, so positions could not be sized to the model's weights. | None. v1.0 sizes positions by weights (per cent of capital), and all of its performance is reported in percentages, so its frozen results (`results/systematic/test/`, `docs/v1.0_freeze.md`) are unaffected. |
| C02 | 2026-11-04 | the 3 December 2026 rebalance (positions effective 2026-12) | **v1.1 added**, run live in parallel with v1.0: v1.1 = frozen v1.0 + exactly the T18 rule (risk-unit no-trade band 0.1 × the position's risk budget and partial rebalancing w + 0.5 (w* − w), replacing v1.0's 25% relative band). v1.0 remains the frozen control. | T18 passed its pre-registered rule (4 of 4 criteria at 1x costs; `results/T16-T19_risk_batch.md`). | None. No v1.0 file, parameter, input snapshot or result changed; `python -m em_macro.verify_v1` reproduces v1.0 exactly. v1.1 has its own code, outputs and freeze record (`docs/v1.1_freeze.md`). |
| C03 | 2026-11-06 | the 3 December 2026 rebalance (positions effective 2026-12) | Paper capital for the algorithm (v1.0 and v1.1) set to US$500,000,000, replacing C01's US$10,000,000. Recorded before any live month is booked (no live month has been booked yet; November 2026 is booked on 3 December). | Capacity: to see the strategy at an institutional size, with capacity checks and a market-impact estimate shown beside the official P&L (diagnostic only). | None. All results stay in percentages of capital; only notional amounts change. `python -m em_macro.verify_v1` and `python -m em_macro.systematic_v11 verify` reproduce v1.0 and v1.1 byte for byte (2026-11-06). |
| C04 | 2026-11-06 | the fund's start (the first date both members are live: 30 November 2026, v1.1's index start) | **Horizons fund view added**: a combined view of Algorithm v1.1 (risk share 90%; 80% from the 2026-11-07 amendment) and Janus (10%; 20% from the 2026-11-07 amendment), combined by risk (risk share ÷ trailing volatility, capital shares until 6 months of data). Janus's share changes only by the rule in `docs/fund/allocation.md`: 20% after 30 resolved calls with positive net P&L and a better Brier score than the market on those calls (amended 2026-11-06: every Janus position must record a market probability, 50 where none exists); 5% while its drawdown exceeds 10%. Amended 2026-11-07, before the fund starts and before any Janus call resolved: Janus starts at 20%; after 30 resolved calls, 30% with positive net P&L and a better Brier score than the market, 10% with negative net P&L or a worse Brier score; 5% while its drawdown exceeds 10%, overriding. My decisions stay outside. | To see the books as one fund without changing any of them. | None. The fund is read-only (`ledger/fund.py`): no book's record, P&L, rule or result changes, and no fund figure is written into any book. |
| C05 | 2026-11-09 | the next Janus daily review (9 November 2026) | **Janus mandate**: (a) research is required: every daily review researches the main drivers across its universe (central banks, data, geopolitics, positioning) on the web before deciding and records what it read in `sources_read`; a review with empty `sources_read` is rejected and counts as failed, and the quick check flags it. (b) Risk budget: normally 2-6 positions and 3-10% of the account at risk, best ideas even at modest conviction (e.g. 55%), size scaled with conviction and edge over the market probability (a small edge: 0.25-0.5% at risk); below 3% only with a specific written reason tied to an identifiable event or condition; weekend and holiday reviews may defer entries but must research and name the ideas. Set blind: no Janus position had ever been opened. | The first four reviews (6-8 November) opened nothing with general "no edge" reasoning, three of them with no recorded research. | None. Janus is a separate paper book: no algorithm, frozen result or other book changes. All existing Janus limits stay (2% per position, 10% total, 8 open, capacity, costs, The Opposition, `market_probability`). |
| C06 | 2026-11-10 | the 10 November 2026 daily review (23:07 UTC) | **Janus: hard 2-position minimum, dated event reasons, failed-review records**: (1) at least 2 open positions at all times; a dated `below_budget` reason may only let total risk fall below 3%, never the book below 2 positions; fewer than 2 only for a named data failure (which mark, how stale), and only for the instruments affected. (2) An event-based reason cites the event's date from an official calendar URL listed in `sources_read`, and expires at the end of the next trading day after the event. (3) The CLI rejects a review that breaks (1) or (2), and a rejected daily review writes a failed-review record (closes Q004). Approved by Ethan on 2026-11-10. | The 9 and 10 November reviews held no position under a `below_budget` reason, and the 10 November review dated US CPI to 12 Nov when BLS lists 10 Nov 2026, 08:30 ET (correction K004). A rejected review left no record (Q004). | None. Janus is a separate paper book: no algorithm, frozen result, fund allocation rule or other book changes. Nothing else in C05 changes. |

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

## C03 — paper capital US$10,000,000 → US$500,000,000 (algorithm, v1.0 and v1.1)

The request that set this change called it "C02". That number was already used for v1.1 (recorded 2026-11-04), so
it is recorded as C03 and the existing record is not renumbered.

- **What changes:** the notional capital against which v1.0 and v1.1 positions are expressed in currency units. From
  the 3 December 2026 rebalance (positions effective 2026-12), both versions are sized against US$500,000,000. This
  replaces C01's US$10,000,000 at the same rebalance. C01's figure is never used for a booked month: the October and
  November 2026 months stay on the US$100,000 basis, and December 2026 onward is on US$500,000,000.
- **Recorded before any live month is booked:** v1.0's live record starts with November 2026, which is booked by the
  3 December run. v1.1's live record starts with December 2026.
- **What does not change:**
  - every frozen file: v1.0's design, code and results; v1.1's code (`em_macro/systematic_v11.py`) and freeze record;
  - the signals, sizing rules, volatility targets, leverage cap, no-trade bands and cost models;
  - `positions.csv` (in % of capital) and `paper_pnl.csv` (decimal returns). Neither depends on the capital level.
- **Reproduction check (2026-11-06, branch `build/ledger-v2`):**
  - `python -m em_macro.verify_v1`: "v1.0 REPRODUCED EXACTLY". Both result tables are IDENTICAL byte for byte
    (`performance_2005_2019.csv` 00bae5baaa1bf053…, `performance_2020_on.csv` 1f8828109a6ab741…).
  - `python -m em_macro.systematic_v11 verify`: "v1.1 REPRODUCES T18 EXACTLY". Every table is IDENTICAL; Sharpe
    0.9163 against v1.0's 0.6536, max drawdown −15.422%, turnover 11.60x a year. The verify step rewrites the
    timestamp in `results/systematic_v1.1/freeze/reproduction.json`, so that file was restored from git
    afterwards and left unmodified.
  - The only code changes are in the Ledger app (`ledger/build.py`: `USD_SWITCH_CAPITAL` and the note) and the new
    diagnostic `ledger/capacity.py`. No file under `em_macro/` or `results/` changed.
- **Capacity diagnostics added with it (never change positions):** `ledger/capacity.py` and
  `data/ledger/capacity_reference.csv`. For each position the Algorithm page shows:
  - notional at US$500m against average daily volume (BIS Triennial 2022 for FX; Borsa Istanbul's bulletin for
    Turkish bonds, computed; documented estimates, marked as such, elsewhere);
  - exchange position limits for futures (CFTC federal spot-month limits);
  - a square-root impact estimate (Y × daily vol × √(notional/ADV), Y = 1).

  It flags any position above 10% of ADV or at 80% or more of a position limit. An "estimated P&L with impact"
  line sits beside the official P&L, which keeps the frozen cost model. At the 3 Nov 2026 positions and US$500m,
  TR10Y (1,238% of the exchange-only ADV, a lower bound) and MX10Y (63%) are flagged.
- **Classification:** configuration change, not a trial. Not counted in N.

## 2026-11-06: Janus, an AI discretionary paper book (branch `build/ledger-v2`)

- **What:** a third, separate paper book next to my decisions and the algorithm. It has its own US$500,000,000
  account (reported in %), weekly runs (Mondays 06:00 UTC, `janus-weekly`) through the Anthropic API (`claude-opus-5-5`,
  with web search), The Opposition, and an append-only hash-chained record in `data/janus/` (see its README).
  Daily fills, stops and horizon closes run in `ledger-daily`.
- **Separation:** Janus never feeds the algorithm. No file under `em_macro/` or `results/` reads `data/janus/`, and
  v1.0/v1.1 are unchanged. It is not a trial and has no row in `trials.csv`. No edge is claimed.
- **Data:** free public daily sources only. Never Norgate or em-macro-data (licence). Dropped: Italy's spread,
  metals, grains. Energy is marked on official spot prices as an estimate.
- **New registry rows (`data/ledger/instruments.csv`, book `janus`):** US10Y, JP10Y, JPY, CHF, AUD, CAD, WTI,
  BRENT, NATGAS, HEATOIL and RBOB, plus USDCASH (3-month T-bill, the cash benchmark).
- **Marks:** each daily run now stores every recent observation a source returns (up to 31 days), not only the
  latest, so a missed run leaves no gap. A fallback is never used when it is older than the previous first-hand
  daily mark.
- **First run (2026-11-06, run 42163218263 on `build/ledger-v2`):** the API key was accepted; `claude-opus-5-5`
  made 12 web searches. It opened nothing and logged a `no_trade` record with its reasoning (records 1-3 of
  `data/janus/records.jsonl`). It said it ran out of searches before checking the BoE, payrolls, the BoJ and the
  ECB, so the search budget was raised from 12 to 25 (8 for The Opposition) for the next runs. The run was not
  repeated the same day: asking again until it trades would bias the record.

## 2026-11-06: correction K001, D001's entry level rebased to the marks' source

- **What:** D001's `entry_level` changed from 159bp to **165.74bp**. 159bp was the 30 Oct 2026 closing spread
  "by convention" (OAT 4.93%, Bund 3.34%, a different source and close). 165.74bp is the Riksbank SWEA 30 Oct close
  (FRGVB10Y 4.984% minus DEGVB10Y 3.3266%), the source and close of every FR-DE mark since the Part A fix. (The
  request said 165.7bp; 165.74bp is the exact stored mark, so the entry equals the mark on the entry date.) The stop
  (115bp) and every other field are unchanged.
- **Why:** entry and marks now come from the same source. Measured against Riksbank marks, the 159bp entry booked
  about +0.15% of account on the entry day from a source mismatch, not a market move.
- **How it is recorded:** a new mechanism, `python -m ledger.audit correct`. It changes one logged field and appends
  a hash-chained `correction` record to `data/ledger/seals.jsonl` (K001, seal 15). The record holds the old and new
  value, the reason, and the entry's digest before and after. Verification accepts a changed entry only through such
  a record, and checks that the record changed that field and nothing else. Any other edit still shows "record check
  failed". D001's page shows the correction under "Corrections" and marks the entry "corrected".
- **Effect:** D001's live P&L at the 4 Nov mark (150.23bp) is −0.31% of account (it was −0.20% from 159bp).
  The Me index starts at exactly 100 on 30 Oct. Because the stop stays at 115bp, the distance from entry to stop
  widens from 44bp to 50.74bp. The loss at the stop is still the 1% size, but each basis point is now worth
  1/50.74% of account instead of 1/44%.

## 2026-11-09: correction K002, D003's entry at the 6 Nov close (a private settlement)

- **What:** D003's entry is now the **6 Nov 2026 close**: the NYMEX BZ March 2027 (BZH7) final settlement, the source
  and close of every D003 mark. The 94.00 underlying and 3.00 premium were placeholders pending the real settlement.
  - The premium is repriced by the ledger's Black-76 at that close, with the record's own implied-volatility
    estimate (56.4%), rate (4.03%) and expiry (26 Jan 2027).
  - For this debit spread, the maximum loss per unit is that premium.
  - The spread count is recomputed at the same 2% at risk of the record's US$10m book: **69** spreads (was 65), the
    most whose premium stays within US$200,000.
  - Size (2%), legs, expiry, stop, horizon and every other field are unchanged.
- **The 6 Nov entry row (P&L 0) is kept**, so P&L on the entry day is 0. The first settlement-based mark is 9 Nov.
- **Licence:** a settlement is a licensed price, and a premium repriced from it with public inputs would reveal it.
  The public record therefore names the values instead of stating them:
  - `entry_underlying` = "settlement 2026-11-06 (private)";
  - `entry_premium` = "Black-76 at the entry settlement (private)";
  - `risk_per_unit` = "the entry premium (private)";
  - the decision's `entry_level` = the same reference in words.

  `ledger/derivs.py` (`resolve_terms`) resolves them at run time from the settlement in em-macro-data. Until the
  6 Nov settlement is in the private store, D003 keeps its entry row only.
- **Superseded, 2026-11-09:** the correction's reason also published unsalted SHA-256 digests of the two private
  numbers. They can be brute-forced: see the next note.
- **How it is recorded:** one correction, K002, appended to `data/ledger/seals.jsonl` as two records: the
  derivative terms (four fields) and the decision (`entry_level`).
  - `python -m ledger.audit correct-file` (`correct_many`) is new: one correction may change several fields.
    Verification checks that it changed exactly those fields and nothing else.
  - D003's page lists each corrected field under "Corrections".
  - Readers of `entry_level` (`schema.entry_number`) treat a private entry as having no public number.

## 2026-11-09: salted commitments for private values (K002's digests superseded by K003)

- **Problem:** K002's reason published plain SHA-256 digests of D003's entry settlement and repriced premium. A
  settlement to 0.01 has only about 20,000 plausible values, so hashing each candidate recovers it. Those digests
  are in K002's record in the append-only audit chain, and in this repository's git history. **Treat them as having
  disclosed both values.** Editing the record would break the chain, and removing them from git history would mean
  rewriting `main`; neither is done here.
- **Convention from now on** (`ledger/commitments.py`):
  - every private value is committed as **SHA-256(salt || value)**, with its own random 32-byte salt
    (`secrets.token_bytes`);
  - the value is the canonical string `"<PRODUCT> <YYYY-MM>|<date>|<what>|<number %.10g>"`;
  - the salt and the value are stored **only** in em-macro-data `ledger/commitments.jsonl`;
  - only the commitment is published, inside the field it commits to, e.g. `settlement 2026-11-06 (private; salted
    commitment <hex>)`, so the audit chain covers it;
  - `python -m ledger.commitments verify` recomputes each commitment from the private salt and value. Where the
    store holds the settlement, it also checks that the value equals what the ledger derives from it. It never
    prints a salt or a value.
  - The unsalted digest helper is removed. Any future private-entry commitment goes through `ledger.commitments`.
- **K003 (applied by the `private-commitments` workflow, run by hand):**
  1. fetches the entry settlement into em-macro-data;
  2. generates the salts and pushes them there first;
  3. appends correction K003, which changes D003's `entry_underlying` and `entry_premium` texts to carry the salted
     commitments;
  4. verifies, then pushes `main`.

  The values, P&L and every other field are unchanged. The salts are generated in GitHub Actions because only the
  workflows hold write access to em-macro-data.
- **What salting does not hide:** what this repository already publishes by design (P&L in %, the 69-spread count)
  still narrows the private values. That is inherent to publishing P&L in %.

## 2026-11-06: Janus moves to Claude Code sessions; no Anthropic API calls for Janus from GitHub Actions

- **Removed:** the `janus-weekly` workflow and the API call in `ledger/janus.py` (`run`). Post-mortems are no longer
  written by `ledger-daily` and `systematic-monthly` through the API; the daily review session writes them.
- **Added:**
  - **CLI** (`ledger/janus.py`):
    - `context` (read-only);
    - `propose --file` (validates against every rule, then appends; atomic: a proposal that breaks any rule is
      rejected whole);
    - `check` (a one-line record when nothing changed).
  - **Post-mortems** (`ledger/postmortem.py`): `due`, `show`, `write`.
  - **`scripts/janus_commit.sh`:** every write, from a session or from `ledger-daily`'s fills, runs on a fresh
    `origin/main` and retries from the new `main` when a push is rejected (tested with a simulated race).
  - **Runbooks:** `docs/janus/quick_check.md` and `docs/janus/daily_review.md`.
  - **`janus-fire`:** a workflow that POSTs to the quick-check task's API trigger every 30 minutes on weekdays,
    06:00-21:30 UTC (secrets `JANUS_FIRE_URL`, `JANUS_FIRE_TOKEN`).
- **Rule changes in code:**
  - A size above a limit is now rejected instead of cut, so the session resubmits a valid size.
  - New required fields: a 2-3 sentence thesis, at least one source URL, The Opposition on every new position, a
    reason on every review. A daily review must review every open position.
  - A quick check cannot open positions.
  - The only automatic cut left is at the fill, when the entry mark changes the capacity limit (logged).
- **Ledger:** the Janus page shows "last checked" and states that trades fill at the next official daily mark.
- **Still calling the API from Actions (not Janus):** the event-forecast resolver in `ledger-daily` and the
  investor letters' narrative in `systematic-monthly`, both via the `ANTHROPIC_API_KEY` secret.

## 2026-11-06: no Anthropic API call anywhere: the forecast resolver and the investor letters move to sessions

- **Event-forecast resolver:** its own short daily Claude Code task ("Ledger forecast resolver",
  `docs/ledger/forecast_resolver.md`), not a step of the Janus review. Reasons:
  - Janus must stay independent of my forecasts.
  - Forecasts resolve on weekends too, and the Janus review runs on weekdays only.
  - One task failing never blocks the other.

  How it works:
  - The session works **blind**: `python -m ledger.resolve events` gives question, resolution source and dates,
    never the probabilities.
  - It settles events with `python -m ledger.resolve settle-events --file` (atomic). Settling requires two
    independent sources (`ledger/independence.py`); an `unresolved` finding is logged.
  - `ledger-daily` still settles mechanical questions from official data. It opens an event's `[RESOLVE?]` issue
    only if no session has settled it `session_resolve_grace_days` (2) after its resolution date, quoting the
    session's last finding.
- **Investor letters:** `docs/letters/monthly_letters.md`, a scheduled task on the 3rd to the 6th.
  - `python -m ledger.letters figures` and `write` (no API).
  - Code inserts the figures verbatim and rejects any percentage in the narrative that matches no figure.
  - It refuses before the month is booked, and refuses a second letter.
- **Removed:** `ledger/llm.py` and `ledger/resolver_api.py`. From the workflows: the `ANTHROPIC_API_KEY` env, the
  `anthropic` install and ledger-daily's `skip_api` input. From `ledger/automation.json`: the API settings.
- **Seals:** `scripts/ledger_commit.sh` (formerly `janus_commit.sh`, which remains as a wrapper) now also seals,
  and is the only writer of `data/ledger/seals.jsonl`. `ledger-daily` and `ledger-intake` seal through it on a
  fresh `main`.
- **Test:** `tests/test_sessions.py` fails if any workflow uses `ANTHROPIC_API_KEY` or installs the SDK, or if any
  code imports `anthropic`.

## 2026-11-06: janus-fire removed

The Janus quick check runs as two hourly Claude Code scheduled tasks at :15 and :45 past the hour (a scheduled task
cannot run more often than hourly, so two tasks give the 30-minute cadence). The `janus-fire` workflow, which fired
the quick-check task's API trigger, is removed, and the `JANUS_FIRE_URL` / `JANUS_FIRE_TOKEN` secrets are not needed
(they were never added). The merged branches `build/ledger-v2` and `build/janus-sessions` were deleted.

## C04 — Horizons fund view (read only)

- **What is added:** `ledger/fund.py`, which writes the app's `fund.json`, and the Fund card, line, chart,
  allocation and correlations on Home. The rule is in `docs/fund/allocation.md`, recorded on 2026-11-06 before the
  fund starts.
- **What does not change:** v1.0, v1.1, Janus and my decisions. Their records, P&L, limits and results are exactly
  as before. The fund reads their published indices and never writes back.
- **Changing the rule** (members, shares, thresholds, volatility window) is a new config change, recorded before it
  takes effect.
- **Amendment, 2026-11-06 (before any Janus call resolved; Janus had opened no position).**
  - `market_probability` is now required on every new Janus position: the best available market-implied
    probability that the view is right (from option prices, a prediction market or futures pricing), with
    `market_source` and `market_basis`.
  - Where none exists, record 50 (0.50) with basis `none`, so that call is compared with a coin flip.
  - The CLI rejects a position without them (`ledger/janus.py` `_check_market`). The 20% condition is therefore
    measured on all resolved calls, not only on those that happened to record a market probability.
  - Nothing else in the rule changed.
- **Amendment, 2026-11-07 (before the fund starts and before any Janus call resolved; set blind).**
  - Janus's starting risk share is **20%** (algorithm v1.1 **80%**), replacing 10% (90%).
  - After at least 30 resolved calls: **30%** if its net P&L after costs on those calls is positive and its Brier
    score is better than the market's; **10%** if its net P&L is negative or its Brier score is worse than the
    market's; otherwise (an exact tie) it stays at 20%.
  - **5%** while Janus's drawdown exceeds 10%, overriding the others (unchanged).
  - Evaluated at each month start on data to the previous month end, as before. Nothing else changed: members,
    the risk combination, the volatility window, the 6-month fallback and the market-probability requirement.
    Rule text: `docs/fund/allocation.md`; code: `ledger/fund.py`.

## C05 — Janus mandate: research required, 3-10% risk budget (2026-11-09)

Recorded on 2026-11-09 and effective from the next daily review. It was set by the owner **blind**: Janus had never
opened a position, so no Janus result informed it.

**Why.** Janus's first four daily reviews (6, 6, 7 and 8 November) all opened nothing, each with a general "no
defensible edge" reason. Three of them recorded no `sources_read` at all.

**(a) Research is required.**
- Every daily review does web research on the main drivers across its universe before deciding: central banks,
  data, geopolitics and positioning. It records what it read in `sources_read`, with URLs.
- `ledger/janus.py` rejects a daily review with empty `sources_read`. Such a review counts as failed.
- Every quick check record carries the CLI's flags, added by the CLI itself: a failed review (empty
  `sources_read`), or no daily review since yesterday. The Janus page shows them with the last check.

**(b) Risk budget.**
- Janus normally holds 2-6 positions using 3-10% of the account at risk. It chooses its best ideas even at modest
  conviction (for example 55%).
- Size scales with conviction and with the edge over the market probability. A small edge gets a small position,
  0.25-0.5% at risk. The runbook gives a sizing table; only the 2% per-position limit is enforced in code.
- It may hold less than 3% at risk only with a specific written reason tied to an identifiable event or condition,
  in `below_budget`: `condition`, `until` (at most 30 days ahead) and `reasoning`. A general "no edge" is not a
  reason. The CLI rejects a review that leaves the account below 3% without one, and rejects a generic condition.
- Weekend and market-holiday reviews may defer new entries to the next trading day with `deferred_ideas`, but must
  still research and name the ideas.
- A quick check flags the account below 3% without a current reason.

**Unchanged.** Every existing limit: 2% at risk per position, 10% in total, 8 open positions, capacity, costs, The
Opposition and `market_probability`. Also unchanged: the fill rule (the next official daily mark), stops that only
tighten, and the append-only hash-chained record. Records made before this change are not edited. The 8 November
review, which recorded no `sources_read`, is shown as failed "before the research rule".

**Where:** `docs/janus/daily_review.md` (Mandate), `docs/janus/quick_check.md` (flags), `ledger/janus.py`
(`_check_mandate`, `review_status`, `budget_status`, `mandate_flags`) and `tests/test_janus.py`.

## C06 — Janus: hard 2-position minimum, dated event reasons, failed-review records (2026-11-10)

Approved by Ethan on 2026-11-10 and effective from that day's daily review (23:07 UTC). It amends C05 (b) only
where stated below; nothing else in C05 changes.

**Why.** Under C05 the 9 and 10 November reviews held no position, each with a `below_budget` reason tied to US CPI
"on 12 Nov". The Bureau of Labor Statistics lists the October 2026 CPI for **10 November 2026, 08:30 ET**
(<https://www.bls.gov/schedule/news_release/cpi.htm>), so the reason rested on a wrong date (correction K004). And a
rejected review left no record, so the quick check could not flag it the same day (queue item Q004).

**1. The minimum of 2 open positions is hard.**
- C05's "normally 2-6 positions": the lower bound of 2 now holds at all times.
- A dated `below_budget` reason may only let total risk fall below 3% (for example two positions of 0.25% at risk).
  It can never take the book below 2 positions.
- Fewer than 2 is allowed only for a **named data failure**, in `data_failure`: one entry per instrument affected,
  each with `instrument`, `mark` (which mark failed: its source and series) and `last_mark` (the date of its latest
  mark, or `none`). The CLI checks each entry against the marks (the private settlements for futures): `last_mark`
  must match, and the mark must be stale, meaning at least 2 weekdays without a mark (or no mark at all).
- Only for the instruments affected: while at least as many other instruments as the shortfall have current marks,
  the minimum stands and the review must open positions there.
- On a weekend or market holiday, named `deferred_ideas` count toward the minimum, as they already count toward
  the 3% budget under C05.

**2. Event-based reasons cite an official calendar and expire.**
- A `below_budget` reason tied to an event (`type` `event`, or a condition naming a release, decision, meeting,
  vote or date) gives `event_date` (YYYY-MM-DD) and `calendar_url`: the official calendar that dates the event
  (the statistics office, central bank or official body; the list is `OFFICIAL_CALENDAR_HOSTS` in
  `ledger/janus.py`), which must also be listed in `sources_read`.
- A date written in the condition must be the official one.
- The reason expires at the **end of the next trading day after the event** (the next weekday): `until` may be no
  later. The quick check flags the account below 3% once the reason has expired.

**3. The CLI enforces 1 and 2, and records rejections.**
- `python -m ledger.janus propose` rejects a daily review that breaks rule 1 or rule 2, as it rejects any other
  broken rule.
- A rejected daily review appends one **failed-review record** to Janus's chain (`type` `run`, `status` `failed`,
  with the errors, the `sources_read` and the proposal's SHA-256) and nothing else, and the CLI exits 3.
  `scripts/ledger_commit.sh` commits and pushes that record and still exits 3, so the session fixes the proposal
  and proposes again. Errors about futures are recorded without their details, which can derive from licensed
  settlements. `--dry-run` writes nothing.
- The quick check flags the failed review the same day ("rejected by the CLI") until a review passes. This closes
  Q004.

**The 10 November review.** Its record (seq 199) is not edited. Correction K004 in the corrections log
(`data/ledger/seals.jsonl`) notes that it dated US CPI to 12 Nov when BLS lists 10 Nov 2026, 08:30 ET, and that under
C06 its `below_budget` entry expires at the end of 11 Nov (not 13 Nov). The quick check applies that expiry
(`BELOW_BUDGET_EXPIRY_CORRECTIONS` in `ledger/janus.py`).

**Unchanged.** Everything else in C05: research in `sources_read`, the 3-10% budget, sizing, the 30-day limit on
`until`, weekend and holiday deferrals. Every existing limit (2% per position, 10% in total, 8 open, capacity,
costs, The Opposition, `market_probability`), the fund allocation rules (`docs/fund/allocation.md`) and the T25-T26
shadow files. Records made before C06 are not edited.

**Where:** `ledger/janus.py` (`_check_min_positions`, `_check_event_reason`, `apply_proposal`, `review_status`,
`budget_status`), `scripts/ledger_commit.sh` (exit 3), `ledger/audit.py` (`correct_janus`, Janus corrections in
`verify_seals`), `docs/janus/daily_review.md`, `docs/janus/quick_check.md`, `tests/test_janus_c06.py`.
