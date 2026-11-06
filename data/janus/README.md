# Janus — AI discretionary paper book

Janus is an experiment in AI judgement. Its results never feed the algorithm: v1.0 and v1.1 are mechanical rules
and never read this folder. No edge is claimed. Code: `ledger/janus.py`; schedule: `.github/workflows/janus-weekly.yml`
(Mondays 06:00 UTC, and by hand); daily fills, stops and closes run in `ledger-daily`.

- **Account:** US$500,000,000 paper, reported in % (index 100 at its start).
- **Model:** `janus_model` in `ledger/automation.json` (the current Claude Opus, `claude-opus-5-5`), with web search.
  The Opposition (the strongest case against each new position) is a second, independent call with the same model.

## `records.jsonl` — append-only, hash-chained

One JSON object per line. `seq` counts from 1; `prev_hash` is the previous record's `hash` (64 zeros for the first);
`hash` = SHA-256 of `prev_hash` followed by the record's canonical JSON (sorted keys, no spaces) without `hash`.
`python -m ledger.janus verify` recomputes the chain, as does every app build (the header badge). Nothing is
edited. A fill, a stop change, a close or a review is a new record.

| type | written by | meaning |
|---|---|---|
| `account_open` | first run | account size, rules, universe |
| `run` | weekly run | model, timestamp, market summary, token use, rule notes, the URLs web search returned |
| `open` | weekly run | new position: instrument, direction, % of account at risk, stop, horizon, probability its view is right, thesis, what would change its mind, sources, model, timestamp. The entry is not yet filled |
| `opposition` | weekly run | The Opposition's case against an `open` |
| `fill` | daily / weekly | entry at the first first-hand daily mark dated on or after the decision date: notional, contracts, costs, capacity check, roll contract |
| `cancel` | daily / weekly | the entry mark was already through the stop, or Janus withdrew the order before the fill |
| `review` | weekly run | hold / close / tighten_stop for an open position, with reasoning |
| `stop_change` | weekly run | a tightened stop (widening is rejected in code) |
| `close_request` | weekly run | Janus decided to close; filled at the next daily mark |
| `roll` | daily | commodity roll to the next contract (cost charged as two trades) |
| `close` | daily / weekly | exit on stop, horizon or close decision: gross and net P&L (% of the starting account), outcome |
| `postmortem` | daily | the automatic post-mortem of a closed position |
| `no_trade` | weekly run | nothing opened this week, with the reasoning |

## Universe and data sources (free public daily data only)

| code | market | daily mark |
|---|---|---|
| WTI, BRENT, NATGAS, HEATOIL, RBOB | NYMEX CL, ICE B, NYMEX NG, HO, RB front month | **estimate:** official spot prices (EIA via FRED: DCOILWTICO, DCOILBRENTEU, DHHNGSP, DHOILNYH, DGASNYH). EIA stopped publishing NYMEX futures in April 2024 |
| US10Y | US 10y Treasury | FRED DGS10 (Fed H.15); fallback Riksbank USGVB10Y |
| DE10Y | German 10y Bund | Bundesbank daily (Svensson 10y) |
| GB10Y | UK 10y gilt | Bank of England IUDMNPY |
| JP10Y | Japan 10y JGB | Japan Ministry of Finance JGB curve CSV; fallback Riksbank JPGVB10Y |
| FR-DE | France 10y over the Bund | Riksbank SWEA FRGVB10Y − DEGVB10Y |
| EUR, GBP, JPY, CHF, AUD, CAD | major FX | ECB euro reference rates crossed with EUR/USD (GBP: Bank of England) |

**Dropped (listed, not substituted):** the Italy 10y spread (no free daily source); metals (gold, silver, copper,
platinum, palladium: no free daily price); grains (no free daily futures settlement); Norgate and em-macro-data
(licence).

**Bond P&L:** −duration × yield change (a 10-year par bond's modified duration at the entry yield).
**Commodity roll rule:** hold the earliest contract whose notice date is more than 35 days after the trade date.
Roll when within 10 days of its notice date (approximate notice dates per market in `NOTICE_RULES`). P&L is on the spot
proxy, so roll yield is not captured, but each roll is charged as two trades.
**Costs:** the algorithm's model (10bp one way for major FX and developed bonds, 20bp for the FR-DE spread). Commodities
use the T20-T22 model, 2 × (US$3 + 1 tick) per contract per side. The square-root impact estimate is added on every
trade.
**Limits (enforced in code):** at most 2% at risk per position, 10% in total, 8 open. Notional at most 10% of ADV and
below 80% of any exchange position limit (`ledger/capacity.py`), otherwise the size is cut.
