# Janus — AI discretionary paper book

Janus is an experiment in AI judgement. Its results never feed the algorithm: v1.0 and v1.1 are mechanical rules
and never read this folder. No edge is claimed. Code: `ledger/janus.py`.

**How Janus runs (from 2026-11-06):** entirely in Claude Code sessions on the account's plan. No Anthropic API
call is made from GitHub Actions.
- **Quick check** (`docs/janus/quick_check.md`): every 30 minutes, as two hourly Claude Code scheduled tasks at :15
  and :45 past the hour.
- **Daily review** (`docs/janus/daily_review.md`): weekdays at 18:07 New York time, after the US close.

A session never edits this folder. It reads `python -m ledger.janus context`, then writes through
`scripts/janus_commit.sh` with the CLI (`propose`, `check`, `postmortem write`), which enforces every rule in code
and pushes to `main`. Fills at the next official daily mark, stops and horizon closes are applied by
`python -m ledger.janus mark`, which the script runs on every write and `ledger-daily` runs each morning.

- **Account:** US$500,000,000 paper, reported in % (index 100 at its start).
- **The Opposition:** for every new position, a separate subagent in the daily review writes the strongest case
  against it; the CLI refuses a new position without one.
- **Records 1-3** come from the first run (6 Nov 2026), made through the API before the switch to sessions.

## `records.jsonl` — append-only, hash-chained

One JSON object per line. `seq` counts from 1; `prev_hash` is the previous record's `hash` (64 zeros for the first);
`hash` = SHA-256 of `prev_hash` followed by the record's canonical JSON (sorted keys, no spaces) without `hash`. All writers go through `scripts/janus_commit.sh`, which re-applies a
command on the new `main` when a push is rejected, so concurrent sessions never break the chain.
`python -m ledger.janus verify` recomputes the chain, as does every app build (the header badge). Nothing is
edited. A fill, a stop change, a close or a review is a new record.

| type | written by | meaning |
|---|---|---|
| `account_open` | first run | account size, rules, universe |
| `run` | session | session (daily_review / quick_check), model, timestamp, market summary, session URL, sources read |
| `open` | daily review | new position: instrument, direction, % of account at risk, stop, horizon, probability its view is right, thesis, what would change its mind, sources, model, timestamp. The entry is not yet filled |
| `opposition` | daily review | The Opposition's case against an `open` |
| `fill` | `mark` | entry at the first first-hand daily mark dated on or after the decision date: notional, contracts, costs, capacity check, roll contract |
| `cancel` | `mark` / session | the entry mark was already through the stop, or Janus withdrew the order before the fill |
| `review` | session | hold / close / tighten_stop for an open position, with reasoning |
| `stop_change` | session | a tightened stop (widening is rejected in code) |
| `close_request` | session | Janus decided to close; filled at the next daily mark |
| `roll` | daily | commodity roll to the next contract (cost charged as two trades) |
| `close` | `mark` | exit on stop, horizon or close decision: gross and net P&L (% of the starting account), outcome |
| `postmortem` | daily review | the automatic post-mortem of a closed position |
| `no_trade` | daily review | nothing opened, with the reasoning |
| `check` | quick check | nothing changed: time, positions checked, one-line result |

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
