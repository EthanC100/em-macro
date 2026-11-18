# To do

Three lists, one item per line, ticked when done. The Ledger app renders this file under More, To do.
Edit it by hand; the next build picks it up.

## Technical

- [ ] Monthly rebalance fallback unproven on a real failure (the stale-copy fallback and the retries were added after the November 2026 runs; no source has failed since)
- [ ] Frozen-code guard blocks `stage_test` (`frozen_design.json` records the pre-label code hash; `evaluate()` has to be called directly to reproduce the test)
- [ ] October 2026 labelled "test" in `systematic.py` (the paper P&L sample label; the file is hashed in `docs/v1.0_freeze.md`, so it stays until v1.1)
- [ ] Raw data not kept (downloads live in the Actions cache and are refreshed monthly; only BondSpot, Borsa Istanbul and the IMF WEO files are committed)
- [ ] 9 of 23 instruments lack daily prices and bond returns use monthly-average yields (the Ledger registry now marks 19 of 23 tradeable instruments daily (24 of 29 with the yield legs), but the algorithm's inputs are unchanged; France is marked daily from the Riksbank since 6 Nov 2026; the Italian, Indonesian, Colombian and Chilean 10-year yields still have no free daily source)
- [ ] T02 data gaps (Chile CPI after 2023; stale euro-area, Mexican and South African series)
- [x] Paper capital US$500m from the 3 Dec 2026 rebalance (C03; capacity checks on the Algorithm page)
- [x] Election tracker merged (`data/elections/` is on main; the app reads `data/elections/calendar.csv` and falls back to `data/events/` only if it is missing)
- [ ] Background file overstates the election edge
- [ ] Turkey's lira is crawl-like (eligibility review under Algorithm)
- [ ] No commodity data for the algorithm (Janus marks five energy markets on official spot prices, an estimate; no free daily futures settlements, metals or grains)
- [ ] Turkish and Mexican 10y bonds exceed 10% of daily volume at US$500m (capacity diagnostic; the frozen algorithm is unchanged)

## Automation

- [x] Resolving decisions and forecasts (`ledger/resolve.py`, daily at 05:52 UTC: stop and horizon closes; mechanical forecasts from official data; event forecasts through the API; [RESOLVE?] issues otherwise)
- [x] Marking open positions (`ledger/marks.py` and `data/ledger/instruments.csv`; live P&L in the app)
- [x] Risk Manager (`ledger/risk.py`, on every Decision form; posted as a comment on the issue)
- [x] Screener (`ledger/screener.py`, after each monthly rebalance; report and app page)
- [x] No Anthropic API key needed (Janus, the forecast resolver, post-mortems and the letters' narrative run in Claude Code sessions)
- [x] Election-tracker jobs active (`elections-daily` every day at 06:41 UTC and `elections-weekly` on Mondays, both from main)
- [x] The Opposition (automated for every new Janus position; daily briefings still in the Claude app)
- [x] Janus in Claude Code sessions (quick check hourly at :15 as a scheduled task, daily review after the US close; post-mortems in the daily review)
- [x] Create the Janus quick-check scheduled task at :15 (hourly; its checks are in the Janus records from 17 Nov 2026)
- [x] Create the Janus daily-review scheduled task (about 23:07 UTC, after the US close; its runs are in the Janus records from 6 Nov 2026)
- [ ] Create the remaining scheduled tasks (Janus quick check at :45, Ledger forecast resolver, Ledger monthly letters)
- [ ] Delete the `ANTHROPIC_API_KEY` repository secret once the sessions-only branch is merged
- [x] Stale-marks alert (`ledger-watchdog` and ledger-daily open "[ALERT] Ledger marks stale" after 2 days)

## Algorithm

- [ ] Economic momentum (T02)
- [ ] Commodity sleeve (carry, then basis-momentum)
- [ ] Carry-crash filter
- [ ] Factor-capped sizing
- [ ] Turnover reduction
- [ ] Daily bond and forward-price data
- [ ] Bond macro momentum (Brooks 2017)
- [ ] Volatility forecasting for sizing
- [ ] Turkey eligibility review
