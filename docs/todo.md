# To do

Three lists, one item per line, ticked when done. The Ledger app renders this file under More, To do.
Edit it by hand; the next build picks it up.

## Technical

- [ ] Monthly rebalance fallback unproven on a real failure (the stale-copy fallback and the retries were added after the November 2026 runs; no source has failed since)
- [ ] Frozen-code guard blocks `stage_test` (`frozen_design.json` records the pre-label code hash; `evaluate()` has to be called directly to reproduce the test)
- [ ] October 2026 labelled "test" in `systematic.py` (the paper P&L sample label; the file is hashed in `docs/v1.0_freeze.md`, so it stays until v1.1)
- [ ] Raw data not kept (downloads live in the Actions cache and are refreshed monthly; only BondSpot, Borsa Istanbul and the IMF WEO files are committed)
- [ ] 9 of 23 instruments lack daily prices and bond returns use monthly-average yields (the Ledger registry now marks 21 of 28 instruments daily, but the algorithm's inputs are unchanged; the French and Italian 10-year yields and the Indonesian, Colombian and Chilean 10-year yields still have no free daily source)
- [ ] T02 data gaps (Chile CPI after 2023; stale euro-area, Mexican and South African series)
- [ ] Capital change only on the T02 branch
- [ ] Election tracker unmerged (`build/election-tracker`; `data/elections/` does not exist on main, the app falls back to `data/events/`)
- [ ] Background file overstates the election edge
- [ ] Turkey's lira is crawl-like (eligibility review under Algorithm)
- [ ] No commodity data

## Automation

- [x] Resolving decisions and forecasts (`ledger/resolve.py`, daily at 05:52 UTC: stop and horizon closes; mechanical forecasts from official data; event forecasts through the API; [RESOLVE?] issues otherwise)
- [x] Marking open positions (`ledger/marks.py` and `data/ledger/instruments.csv`; live P&L in the app)
- [x] Risk Manager (`ledger/risk.py`, on every Decision form; posted as a comment on the issue)
- [x] Screener (`ledger/screener.py`, after each monthly rebalance; report and app page)
- [ ] Anthropic API key (add the `ANTHROPIC_API_KEY` repository secret; until then event forecasts get a [RESOLVE?] issue)
- [ ] Election-tracker jobs inactive until merged
- [ ] The Opposition and daily briefings (done in the Claude app, not automated)

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
