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
| C05 | 2026-11-09 | the next Janus daily review (9 November 2026) | **Janus mandate**: (a) research is required: every daily review researches the main drivers across its universe (central banks, data, geopolitics, positioning) on the web before deciding and records what it read in `sources_read`; a review with empty `sources_read` is rejected and counts as failed, and the quick check flags it. (b) Risk budget: normally 2-6 positions and 3-10% of the account at risk, best ideas even at modest conviction (e.g. 55%), size scaled with conviction and edge over the market probability (a small edge: 0.25-0.5% at risk); below 3% only with a specific written reason tied to an identifiable event or condition; weekend and holiday reviews may defer entries but must research and name the ideas. Set blind: no Janus position had ever been opened. *(b) superseded by C08 from 11 Nov 2026, except the 3-10% band and the limits.* | The first four reviews (6-8 November) opened nothing with general "no edge" reasoning, three of them with no recorded research. | None. Janus is a separate paper book: no algorithm, frozen result or other book changes. All existing Janus limits stay (2% per position, 10% total, 8 open, capacity, costs, The Opposition, `market_probability`). |
| C06 | 2026-11-10 | the 10 November 2026 daily review (23:07 UTC) | **Janus: hard 2-position minimum, dated event reasons, failed-review records**: (1) at least 2 open positions at all times; a dated `below_budget` reason may only let total risk fall below 3%, never the book below 2 positions; fewer than 2 only for a named data failure (which mark, how stale), and only for the instruments affected. (2) An event-based reason cites the event's date from an official calendar URL listed in `sources_read`, and expires at the end of the next trading day after the event. (3) The CLI rejects a review that breaks (1) or (2), and a rejected daily review writes a failed-review record (closes Q004). Approved by Ethan on 2026-11-10. *Rules 1-2 superseded by C08 from 11 Nov 2026; rule 3 kept.* | The 9 and 10 November reviews held no position under a `below_budget` reason, and the 10 November review dated US CPI to 12 Nov when BLS lists 10 Nov 2026, 08:30 ET (correction K004). A rejected review left no record (Q004). | None. Janus is a separate paper book: no algorithm, frozen result, fund allocation rule or other book changes. Nothing else in C05 changes. |
| C07 | 2026-11-10 | the first Janus daily review after it was recorded (10 November 2026, 23:07 UTC) | **Janus: no 50% calls, a wider search under the minimum, a time anchor, deferrals only where the market is closed**: (1) no opened position may state a probability of 50%; the CLI rejects a proposal containing one. (2) When the C06 two-position minimum binds, the review lists at least 5 candidates across at least 2 asset classes; a candidate it dropped after The Opposition may be reopened only if it states why no other candidate is better. (3) Every review records its current UTC time and, for each event cited in a reason or thesis, whether it had already occurred; an event dated in the future cannot be described as released. (4) A deferred idea counts toward the minimum only if its market is closed on the review date, and must open at the next session. Approved by Ethan on 2026-11-10. *Rules 1, 2 and 4 superseded by C08 from 11 Nov 2026; rule 3 kept.* | The 10 November 10:30 UTC review met C06's minimum with two 0.25% rates longs (J001, J002) at a stated probability of 50%, opened anyway after The Opposition put each near 43-44% to work, with no other asset class considered; and it described October CPI as "released at 08:30 ET on 10 Nov" at 10:30 UTC, three hours before the 13:30 UTC release. | None. Janus is a separate paper book: no algorithm, frozen result, fund allocation rule or other book changes. Nothing in C05 or C06 changes except what C07 adds. |
| C08 | 2026-11-11 | the 11 November 2026 daily review (23:07 UTC) | **Janus: forced forecasts and a mechanical book, replacing discretionary position selection**: (1) a watchlist, `janus/watchlist.yaml`: US10Y, GB10Y, DE10Y, JP10Y, EUR, GBP, JPY and AUD, each with a precise question (direction, 20 trading days, resolution source); (2) every daily review gives every instrument a probability, a whole number from 1 to 99 and never 50, before and after The Opposition; every forecast is logged and resolved automatically with Brier scores; (3) the CLI sets the book: each instrument on the side of its final forecast, risk proportional to \|p − 50\| inside C05's 3-10% band, rebalanced at each daily review with a 25% no-trade band; only a named data failure excludes an instrument; (4) The Opposition is advisory; (5) J001 and J002 are closed by the first C08 review; (6) a fund resolved call is one forecast per instrument per non-overlapping 20-trading-day window. Approved by Ethan on 2026-11-11. | The 10 November 23:07 UTC review (run record seq 238) held only J001 and J002, two rates longs stated at 50%, 0.5% at risk, under a `below_budget` reason tied to the FOMC a month away (9 Dec). Its other candidates sat at 48-50% with "no edge", and the one fresh idea (short US10Y) was dropped after The Opposition. Discretionary selection kept the book at the minimum, and it yields too few scored calls to judge Janus. | None on any other book: no algorithm, frozen result or other book changes. The fund allocation rule's thresholds and shares are unchanged; only what counts as a Janus resolved call is defined (`docs/fund/allocation.md`). The rules of C05, C06 and C07 that C08 supersedes are marked in their sections. |
| C09 | 2026-11-11 | the same first C08 review (11 November 2026, 23:07 UTC); the mark sources from the next ledger-daily run | **Janus watchlist widened, faster rate marks, clustered fund calls** (amends C08 before any C08 forecast was made): (1) US10Y marked from US Treasury's daily par yield curve (the series FRED republishes as DGS10 a business day later; FRED kept as fallback) and GB10Y from the Riksbank's benchmark gilt yield (GBGVB10Y) instead of the Bank of England's IUDMNPY; (2) BRL (BCB PTAX) and MXN (Banxico FIX) added to `janus/watchlist.yaml`, 10 instruments; gold not added, as no free, republishable daily gold mark exists; (3) the fund rule counts one call per correlation cluster (G10 yields, USD vs G10 FX, EM FX, gold; defined in the watchlist) per non-overlapping 20-trading-day window. Approved by Ethan on 2026-11-11. | US10Y and GB10Y marks were two to three business days behind when ledger-daily ran: FRED and the BoE had not yet published the later days, and the BoE database refuses cloud clients. The C08 watchlist was two correlated bets (global yields, the dollar), so counting each forecast as a call overstated the evidence. | None on any other book. The GB-DE display spread now uses the Riksbank gilt leg. The fund rule's thresholds and shares are unchanged; only how Janus's calls are counted changes. |
| C10 | 2026-11-11 | the next ledger-daily run (11 November 2026), before C08's first daily review (23:07 UTC) | **GBP marked on the ECB cross**: US dollars per pound = the ECB's US dollars per euro divided by its pounds per euro (as JPY and AUD), replacing the Bank of England's XUDLUSS; the watchlist's GBP question resolves on it. Approved by Ethan on 2026-11-11. | The Bank of England's XUDLUSS arrived one business day late on every run, and its database refused at least one run from GitHub's servers (6 Nov 03:57 UTC: "no observations", FRED fallback) and refuses cloud sessions outright. The ECB reference rates are published the same day (16:00 CET). | None on any other book: no decision, forecast or position uses GBP. |

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

> **Superseded by C08 from the 11 November 2026 daily review**, except the 3-10% band (now met by the CLI's
> mechanical book) and the existing limits: discretionary choice of positions, "normally 2-6 positions", the sizing
> table, `below_budget` and weekend or holiday `deferred_ideas`. See C08.

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

> **C06 under C08 (from the 11 November 2026 daily review):** rules 1 and 2 are **superseded** (the CLI's mechanical
> book replaces the two-position minimum, and `below_budget` reasons, event-based or not, are gone); the
> `data_failure` format and its check survive as C08's only exclusion. Rule 3 (failed-review records, exit 3) is
> **kept**. See C08.

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

## C07 — Janus: no 50% calls, a wider search under the minimum, a time anchor, deferrals (2026-11-10)

Approved by Ethan on 2026-11-10 and effective from the first daily review after it was recorded (the 10 November
review at 23:07 UTC). It adds to C05 and C06; nothing in either changes except where stated below.

**Why.** The 10 November review at 10:30 UTC (run record seq 208) opened J001 (long US 10y) and J002 (long UK 10y),
0.25% at risk each, to meet C06's two-position minimum:
- both at a stated probability of **50%**, against a market probability of 50: no call at all;
- both were opened anyway after The Opposition put each near 43-44% to work ("C06 requires two positions"), and the
  review recorded no other candidate or asset class (both are rates);
- its `below_budget.reasoning` said "The October CPI released at 08:30 ET on 10 Nov drives every rates idea" at
  10:30 UTC, three hours before the release (08:30 ET is 13:30 UTC).

> **C07 under C08 (from the 11 November 2026 daily review):** rules 1, 2 and 4 are **superseded** (rule 1 by C08's
> forecasts, never 50; rule 2's candidates and rule 4's deferrals have nothing to select once the CLI sets the book).
> Rule 3, the time anchor, is **kept** and now also covers each forecast's reasoning; so is the withholding of futures
> details from failed-review records. See C08.

**1. No 50% calls.** No opened position may state `probability` 50 (no view). The CLI rejects a proposal containing
one. Deferred ideas are held to the same rule, because they must open at the next session (rule 4). A candidate that
is not opened may be 50.

**2. Wider search when the minimum binds.**
- The minimum *binds* when the book held fewer than 2 positions before the review (after its closes) and the review
  brings it to exactly 2 (counting deferred ideas that count under rule 4).
- The review then lists `candidates`: at least **5** distinct instruments across at least **2** asset classes (rates,
  FX, commodities), each with `instrument`, `direction`, `probability`, `market_probability`, `outcome` (`opened`,
  `deferred` or `not_opened`), `opposition` (`kept`, `dropped` or `none`) and `reason`. Every opened position and every
  deferred idea is among them, and every candidate marked opened or deferred is in the proposal.
- A candidate the review dropped after The Opposition (`opposition: dropped`) may be reopened (opened or deferred)
  only with a `reopen_reason` stating why no other candidate is better; it must name every candidate not opened. This
  applies whenever `candidates` are listed.

**3. Time anchor.** Every daily review gives `time_anchor`: `now_utc`, its current UTC time, and `events`, one entry per
event cited in any reason or thesis (and in the market summary): `event`, `time_utc` (or `date` when the event is not
on the review's own UTC date) and `occurred` (had it happened at `now_utc`). The CLI checks that:
- `now_utc` is UTC and is the time of the review (at most 3 hours before the CLI's clock, not after it);
- each `occurred` agrees with the event's time and `now_utc`, and no event dated after the CLI's clock is marked as
  occurred;
- every date and every scheduled event (CPI, PCE, PPI, HICP, payrolls, GDP, retail sales, PMI, ISM, FOMC, MPC, rate
  decisions, OPEC, WASDE, elections, referendums, auctions) named in a reason or thesis is in `events`;
- no reason or thesis describes an event dated in the future as released ("released", "published", "came in",
  "printed", "showed", ...), unless the wording keeps it in the future ("is due to be released", "has not been
  released"). This check reads the text, so it catches the plain cases; `occurred` is the review's own statement.

**4. Deferrals.**
- A deferred idea counts toward the two-position minimum only if **that instrument's market** is closed on the review
  date: every market on a weekend; FX only on 1 January and 25 December; any other market on a weekday only with
  `market_closed` {`holiday`, `calendar_url`}, an official or exchange holiday calendar (`OFFICIAL_CALENDAR_HOSTS`,
  `MARKET_CALENDAR_HOSTS` in `ledger/janus.py`) that is also listed in `sources_read`. C05's use of deferred ideas
  toward the 3% budget is unchanged.
- It must open at the next session: the first daily review after it whose date is a session for that market opens it
  (same instrument and direction, with The Opposition). While the market stays closed (a weekend or holiday review),
  the review carries it forward in `deferred_ideas`. Ideas deferred before C07 are not followed up.

**Rejections.** As under C06: a rejected daily review appends one failed-review record (now also carrying the
review's `now_utc`) and nothing else, and the CLI exits 3. Errors about futures are recorded without their details,
so no licensed settlement figure reaches public error text. `--dry-run` writes nothing.

**Records.** No record is edited: J001, J002 and the run record of 10 November (seq 208-212) stand as written and keep
their 50% probabilities. C07 judges reviews from its effective date only. The run record of each review now keeps its
`time_anchor` and `candidates`.

**Unchanged.** Everything else in C05 and C06: research in `sources_read`, the 3-10% budget, sizing, `below_budget`,
the two-position minimum, `data_failure`, event-based reasons and their expiry, failed-review records. Every existing
limit (2% per position, 10% in total, 8 open, capacity, costs, The Opposition, `market_probability`), the fund
allocation rules (`docs/fund/allocation.md`) and the T25-T26 shadow files.

**Where:** `ledger/janus.py` (`_check_c07`, `_check_no_coin_flips`, `_check_candidates`, `_check_time_anchor`,
`deferred_toward_minimum`, `market_closed`, `_check_deferred_followup`; the C07 counting in `_check_min_positions`),
`docs/janus/daily_review.md`, `docs/janus/quick_check.md`, `tests/test_janus_c07.py`.

## C08 — Janus: forced forecasts on a watchlist, a mechanical book (2026-11-11)

> **Amended by C09 (same day, before C08's first review):** the watchlist has 10 instruments (BRL and MXN added), US10Y and GB10Y are marked from faster public sources, and a fund resolved call is one call per correlation cluster per non-overlapping 20-trading-day window (rule 6 below as amended). See C09.

Approved by Ethan on 2026-11-11 and effective from that day's daily review (23:07 UTC; `C08_FROM` in
`ledger/janus.py`). It replaces discretionary position selection with forced forecasts and mechanical sizing. Rules of
C05, C06 and C07 that it supersedes are listed below and marked in their sections; the others are kept.

**Why.** The 10 November review at 23:07 UTC (run record seq 238):
- held only J001 and J002 (long US 10y, long UK 10y, each stated at 50%), 0.5% of the account at risk, under a
  `below_budget` reason tied to the FOMC on 9 December, a month away;
- listed its other candidates at 48-50% with "no edge";
- dropped its one fresh idea (short US10Y) after The Opposition.

Discretionary selection kept the book at the minimum, and it produces too few scored calls to judge Janus.

**1. Watchlist** (`janus/watchlist.yaml`): eight instruments that Janus already marks daily from free public sources:
US10Y, GB10Y, DE10Y, JP10Y (rates) and EUR, GBP, JPY, AUD (FX). Futures are left out because their settlements are
licensed (rule 7), so a resolution derived from them could not be published. Each instrument has a precise
question: does the mark move in the `yes_if` direction over 20 trading days (yields lower, EUR/USD and GBP/USD
higher, yen per dollar and Australian dollars per dollar lower), resolved on that instrument's registry mark (FRED
DGS10, BoE IUDMNPY, Bundesbank, MoF JGB, ECB and BoE reference rates). Every question resolves the same way:
- **base mark:** the first first-hand daily mark dated on or after the forecast's date;
- **target date:** the 20th weekday after the base mark's date;
- **end mark:** the first first-hand daily mark dated on or after the target date;
- **answer:** YES only if the end mark is strictly beyond the base mark in the `yes_if` direction (an unchanged
  mark is NO).

YES is the instrument's long side. Changing the file is a new config change.

**2. Forecasts.**
- Every daily review gives `forecasts`, one for every watchlist instrument, each with:
  - `p_initial`: its probability of YES before The Opposition;
  - `p_final`: its final probability;
  - `reasoning`, and The Opposition's `case_against`.
- Both probabilities are whole numbers from 1 to 99, never 50. The CLI rejects a review that misses an instrument
  or breaks the range.
- `market_probability` is optional per forecast: 50 with basis `none` unless a market-implied figure is given, as
  under C04.
- Every forecast is logged (record `forecast`, id `JF0001`, ...) with its question, resolution source and
  probabilities, whether or not a position results.
- `python -m ledger.janus mark` resolves each forecast once its end mark arrives (record `forecast_resolution`), on
  every ledger-daily run and every `scripts/ledger_commit.sh` write. Each resolution records the base and end
  marks, the answer, and Brier scores for `p_final`, `p_initial` and the market probability.

**3. Mechanical positions: the CLI, not Janus, sets the book.**
- **Side:** each instrument goes to the side of its final forecast (above 50 long, below 50 short).
- **Risk:** proportional to |p − 50|, at 0.1% of the account per point and at most 2% per position. When that total
  is outside C05's 3-10% band, it is scaled to the nearer edge; a position held at the 2% cap passes its excess to
  the others.
- **Stop:** the watchlist's mechanical stop, set from the latest mark on the losing side (about twice a typical
  20-trading-day move). It defines the % at risk as before.
- **Rebalancing:** at each daily review, against the 25% no-trade band.
  - A held position on the target side is kept while its target risk is within 25% of its current risk.
  - Otherwise it is resized: closed and replaced at the same next mark, with costs charged only on the notional
    actually traded.
  - It is flipped when the forecast changes side.
  - If keeping positions inside the band would leave the total outside 3-10%, everything trades to target.
- **Exclusions:** `below_budget` reasons, event-based or not, are removed. Only a named `data_failure` on an
  instrument (C06's format, verified against the marks: the mark must be stale) excludes it from the book. It is
  still forecast.
- **What the session may not send:** a daily review may not include `new_positions`, `reviews`, `below_budget`,
  `candidates` or `deferred_ideas`. A quick check may not close or tighten a C08 position.
- **Unchanged:** fills at the next official daily mark, the existing limits (2% per position, 10% in total, 8 open,
  capacity) and costs.
- **Post-mortems:** a resize continues the same view, as the algorithm's resizes do, so it needs none
  (`ledger/postmortem.py`). Side flips, stops, exclusions and rule 5's closes are real closes and get one.

**4. The Opposition stays, advisory.** It argues against each forecast before `p_final`. It can never veto one: the CLI
never compares its view with the probabilities and never drops a forecast or a position because of it.

**5. J001 and J002.** The first daily review under C08 closes them, and nothing in the proposal can stop it. Every
position not set under C08 gets:
- a `review` record with action `close` ("C08 rule 5: discretionary position closed");
- a `close_request` filled at the next official daily mark, or a `cancel` if the order is still unfilled.

No existing record is edited: J001, J002 and the runs of 10 November stand as written.

**6. Fund allocation rule** (`docs/fund/allocation.md`):
- **Resolved call:** one forecast per instrument per non-overlapping 20-trading-day window. Per instrument, the first
  C08 forecast counts. The next one counted is the first whose base mark is dated on or after the end mark of the
  last one counted. Which forecast counts depends only on dates, never on outcomes.
- **Brier scores:** Janus's uses `p_final`, the market's uses `market_probability`.
- **P&L:** with positions now set mechanically, "net P&L after costs on those calls" is Janus's net P&L from the end
  of 10 November 2026 to the evaluation date.
- **Unchanged:** the 30-call threshold, the shares and the drawdown override (`fund_calls` in Janus's summary;
  `ledger/fund.py`).

**7. Kept and superseded.**

| rule | under C08 |
|---|---|
| C05 (a) research in `sources_read`; a review without it fails | kept |
| C05 (b) 3-10% at risk | kept, met by the mechanical book; the quick check flags the account below 3% |
| C05 (b) discretionary best ideas, "normally 2-6 positions", the sizing table, `below_budget`, weekend and holiday `deferred_ideas` | superseded (rule 3) |
| existing limits: 2% per position, 10% in total, 8 open, capacity, costs, fills at the next daily mark | kept |
| The Opposition on every new position | superseded by The Opposition on every forecast, advisory (rule 4) |
| `market_probability` on every position | kept, on every forecast (default 50, basis `none`) |
| C06 rule 1, two-position minimum | superseded; its `data_failure` format is the only exclusion |
| C06 rule 2, dated event reasons and their expiry | superseded (`below_budget` removed) |
| C06 rule 3, failed-review records and exit 3 | kept |
| C07 rule 1, no 50% calls | superseded by rule 2 (no forecast at 50) |
| C07 rule 2, candidates when the minimum binds | superseded |
| C07 rule 3, time anchor | kept, and covers each forecast's reasoning |
| C07 rule 4, deferrals | superseded |
| no licensed data in public error text (futures errors withheld from failed-review records) | kept |
| a daily review reviews every open position; no-trade reasoning; a quick check may close or tighten | superseded for C08 positions (the CLI sets them) |

**Rejections.** As under C06, a rejected daily review appends one failed-review record (marked `c08`) and nothing
else, and the CLI exits 3. `--dry-run` writes nothing and shows the book the CLI would set.

**Records.** No record is edited. Earlier reviews are not re-judged. The 10 November 23:07 UTC review is replayed
under C08 in `tests/test_janus_c08.py` (see "Replay" below).

**Replay of the 10 November 23:07 UTC review** (`test_the_10_nov_2307_review_replayed_under_c08`):
- **As recorded, C08 rejects it:**
  - it gives no forecasts;
  - it sends `reviews`, `below_budget` and `candidates`, which C08 does not use;
  - its FOMC `below_budget` reason could not keep the book at 0.5%.
- **With its own stated views turned into forecasts:**
  - the views it stated: short US10Y at 45% is 55% YES, long JPY 48, short AUD 48 is 52% YES, long DE10Y 48;
  - GB10Y moved off its 50 to 51, because C08 forbids 50;
  - EUR, GBP and JP10Y, which it never considered, forced to a side.
- **The CLI's book:** it closes J001 and J002 (cancels, as both were still unfilled), places eight orders at
  3.00% of the account at risk (the 1.5% raw total scaled up to the band; US10Y long 1.00%), and logs eight
  forecasts that resolve 20 trading days after their base marks.

**Where:** `janus/watchlist.yaml`; `ledger/janus.py` (`C08_*`, `load_watchlist`, `validate_c08`, `_check_forecasts`,
`_check_c08_data_failures`, `c08_targets`, `c08_plan`, `_apply_c08`, `c08_rebalance_fills`, `resolve_forecasts`,
`forecast_outcome`, `fund_calls`, `forecast_summary`; the C08 branches of `apply_proposal`, `validate`, `process`,
`budget_status`, `summarize` and `context`); `ledger/fund.py` (`janus_record_c08`); `ledger/postmortem.py` (no
post-mortem for a resize); `docs/janus/daily_review.md`,
`docs/janus/quick_check.md`, `docs/fund/allocation.md`, `data/janus/README.md`; `tests/test_janus_c08.py`.

## C09 — Janus: faster US10Y and GB10Y marks, BRL and MXN, clustered fund calls (2026-11-11)

Approved by Ethan on 2026-11-11. Recorded before C08's first daily review (11 November, 23:07 UTC), so no C08
forecast was made under the earlier wording. It amends C08; everything else in C08 stands.

**1. Why US10Y and GB10Y marks stopped at 6 November, and the fix.** At 01:00 UTC on 11 November both instruments'
latest marks were dated 6 November, two weekdays old, which C06's test calls stale.
- **No run had fetched since.** ledger-daily last ran on 10 November at 17:14 UTC. It is scheduled for 05:52 and
  09:22 UTC but starts 7-11 hours late (`docs/agent-system.md`).
- **The sources had not published the later days when it ran.** The fetch log in `data/ledger/marks.csv` (latest
  date returned by each run) shows the same pattern every day. Each fetch succeeded, with no error and no fallback,
  and returned data ending two to three business days earlier:

  | ledger-daily run (UTC) | US10Y (FRED DGS10) | GB10Y (BoE IUDMNPY) | DE10Y (Bundesbank), for comparison |
  |---|---|---|---|
  | Sun 8 Nov 16:07 | - | Wed 4 Nov | Fri 6 Nov |
  | Mon 9 Nov 20:03 | Thu 5 Nov | Thu 5 Nov | Mon 9 Nov |
  | Tue 10 Nov 17:14 | Fri 6 Nov | Fri 6 Nov | Tue 10 Nov |

- **US10Y.** FRED's DGS10 is the Federal Reserve's H.15 copy of Treasury's 10-year constant-maturity yield,
  published a business day after Treasury's own daily par yield curve and after ledger-daily's usual run time. At
  02:40 UTC on 11 November:
  - FRED had 9 November (4.88);
  - Treasury's curve CSV already had 10 November (4.98);
  - Treasury's 6 and 9 November values (4.86, 4.88) equal the stored FRED marks: the same series.

  The source is now `ustreasury` (`ledger/marks.py` `fetch_ustreasury`, `ustreasury_history`), with FRED DGS10 as
  the fallback.
- **GB10Y.** The Bank of England publishes IUDMNPY two to three business days late (table above). Its database also
  answers "Access denied" to cloud clients, so a Janus session's `context --fetch` could not refresh it at all. The
  source is now the Riksbank's benchmark 10-year gilt yield, SWEA GBGVB10Y: keyless, one value per business day, the
  source already used for FR10Y and DE10YBM. It had 9 November at 02:45 UTC on 11 November. The fallback stays the
  monthly panel, which never acts.
  - The level differs from the BoE's par yield by a few basis points (6 Nov: 5.156 against 5.118).
  - A run adds the source's recent observations only for dates with no mark yet; existing rows are kept. GB10Y's
    marks are therefore Bank of England values up to 6 November and Riksbank values from 9 November. No C08
    forecast or position spans the switch: the first C08 forecasts are made on 11 November. (Corrected the same day:
    an earlier wording said each run would replace the last three weeks.)
  - No decision, forecast or filled position uses GB10Y. J002 is unfilled and is closed tonight under C08.
- **Effect.** At a ledger-daily run on review day, US10Y is marked at the previous business day (instead of two
  back), and GB10Y at the previous business day or the one before. Both pass C06's staleness test, so neither can be
  named as a data failure because of publication lag.

**2. Watchlist: BRL and MXN added; no gold** (`janus/watchlist.yaml`, now 10 instruments).
- **BRL:** will the Brazilian real be stronger, that is, the BCB PTAX sell rate (reais per US dollar, SGS series 1)
  lower after 20 trading days? Stop 8%.
- **MXN:** will the peso be stronger, that is, the Banxico FIX (pesos per US dollar, SIE SF43718) lower after 20
  trading days? Stop 7%.
- Both were already marked daily by ledger-daily. Both join Janus's universe at the algorithm's cost for major
  currencies (10bp one way); capacity references were already in `data/ledger/capacity_reference.csv`.
- **Gold: no free, republishable daily mark exists.**
  - The LBMA Gold Price is licensed by ICE Benchmark Administration; FRED removed it on 31 January 2022 at IBA's
    request.
  - COMEX settlements are CME-licensed (rule 7).
  - The gold cluster is defined and empty, reserved for a source that qualifies.

**3. Fund rule: one call per correlation cluster per non-overlapping 20-trading-day window.** The clusters are
defined in the watchlist. Every instrument is in exactly one, and each forecast records its cluster:

| cluster | instruments |
|---|---|
| G10 yields | US10Y, GB10Y, DE10Y, JP10Y |
| USD vs G10 FX | EUR, GBP, JPY, AUD |
| EM FX | BRL, MXN |
| gold | none yet |

- **A cluster call** is that cluster's forecasts from one daily review.
- **Its window** runs from their earliest base mark to their latest end mark.
- **Its score** is the mean of their Brier scores (Janus's `p_final`, and the market's).
- **Which calls count:** per cluster, the first review's call counts; the next one counted is the first whose
  earliest base mark is on or after the end of the last one counted. It depends only on dates.
- **When a call resolves:** when all its forecasts have resolved.
- **Rate:** three clusters with instruments give about three calls per 20 trading days. The 30-call threshold is
  therefore about ten months away, not four.
- **Unchanged:** every other part of the rule (P&L from 10 November 2026, the shares, the drawdown override).

Text: `docs/fund/allocation.md`. Code: `fund_calls` in `ledger/janus.py`, `janus_record_c08` in `ledger/fund.py`.

**Unchanged.** Everything else in C08: every forecast is still logged and Brier-scored on its own, and the book
still takes a position on every watchlist instrument, now 10. The mechanical sizing, the 3-10% band and the 25%
no-trade band are unchanged.

**Where:** `data/ledger/instruments.csv` (US10Y, GB10Y); `ledger/marks.py` (`ustreasury`); `janus/watchlist.yaml`;
`ledger/janus.py` (`UNIVERSE` BRL and MXN, `load_clusters`, `fund_calls`, the forecast record's `cluster`);
`ledger/fund.py`; `docs/fund/allocation.md`; `docs/janus/daily_review.md`; `data/janus/README.md`;
`tests/test_janus_c09.py` and `tests/test_janus_c08.py` (10 instruments, cluster calls).

## C10 — Janus: GBP marked on the ECB cross (2026-11-11)

Approved by Ethan on 2026-11-11. Recorded before C08's first daily review (23:07 UTC) and applied by a ledger-daily
run before it, so no forecast resolves on the Bank of England source.

**Why.**
- The Bank of England's XUDLUSS (spot US dollars per pound) arrived one business day late on every ledger-daily run
  since 4 November.
- Its database answered "no observations" to one run from GitHub's servers (6 November, 03:57 UTC; the run fell
  back to FRED's older DEXUSUK), and it refuses cloud sessions outright ("Access denied").
- GBP was not stale for tonight (latest mark 9 November), but the source can fail without warning.

**What changes.**
- **Source:** GBP (`data/ledger/instruments.csv`) is now `ecb_exr GBP/USD`: the ECB's US dollars per euro divided by
  its pounds per euro, on the dates both are published, rounded to 6 decimals. This is the same construction as JPY
  and AUD, inverted because GBP is quoted in dollars per pound. `ledger/marks.py` reads `CCY/USD` as that inverted
  cross (`_ecb_ident`, `fetch_ecb_exr`, `ecb_exr_history`).
- **Fallback:** FRED's DEXUSUK, unchanged (it is never used when older than the previous daily mark).
- **Watchlist:** GBP's question in `janus/watchlist.yaml` is unchanged; it now resolves on the ECB cross.
- **History:** a run adds the source's recent observations only for dates with no mark yet; existing rows are kept.
  GBP's marks are therefore Bank of England values up to 9 November and ECB values from 10 November (the first,
  1.34227, from ledger-daily run 42974261471). No forecast or position spans the switch. The two sources differ by
  about 0.1% because they fix at different times (9 November: BoE 1.3403, ECB 1.341604). (Corrected the same day:
  an earlier wording said recent rows would be replaced.)

**Unchanged.** Everything else in C08 and C09. No decision, forecast or position uses GBP.

**Where:** `data/ledger/instruments.csv`, `ledger/marks.py`, `janus/watchlist.yaml`, `data/janus/README.md`,
`tests/test_janus_c10.py`.
