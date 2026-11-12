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
| `fill` | `mark` | entry at the first first-hand daily mark dated on or after the decision date (for an order from a C08 review, from config change C11: strictly after the review's UTC date): notional, contracts, costs, capacity check, roll contract |
| `cancel` | `mark` / session | the entry mark was already through the stop, or Janus withdrew the order before the fill |
| `review` | session | hold / close / tighten_stop for an open position, with reasoning |
| `stop_change` | session | a tightened stop (widening is rejected in code) |
| `close_request` | session | Janus decided to close; filled at the next daily mark |
| `roll` | daily | commodity roll to the next contract (cost charged as two trades) |
| `close` | `mark` | exit on stop, horizon or close decision: gross and net P&L (% of the starting account), outcome |
| `postmortem` | daily review | the automatic post-mortem of a closed position |
| `no_trade` | daily review | nothing opened, with the reasoning |
| `check` | quick check | nothing changed: time, positions checked, one-line result |
| `forecast` | daily review (C08) | a forced forecast: instrument, question, YES direction, 20-trading-day horizon, resolution source, `p_initial` (before The Opposition), `p_final`, market probability, reasoning, The Opposition's case (`JF0001`, ...) |
| `forecast_resolution` | `mark` (C08) | a forecast resolved: base and end marks, answer (YES/NO), Brier scores for `p_final`, `p_initial` and the market |

**From config change C08 (11 November 2026):** Janus forecasts every instrument of `janus/watchlist.yaml` at each
daily review, and the CLI sets the book. Its `open` records carry `c08: true`, `forecast_id`, the mechanical
`stop_rule`, and `replaces` (a resize) or `flips` (a side flip). Its `open`, `review` and `close_request` records are set
by the CLI (`set_by` "CLI (C08)"; a close carries its `close_reason`). A resize fills at one mark: the `close` of the old position and
the `fill` of the new one record the notional carried over (`carried_notional_frac`), and costs are charged only on
the notional traded.

## Universe and data sources

| code | market | daily mark |
|---|---|---|
| WTI, BRENT, NATGAS, HEATOIL, RBOB | NYMEX CL, BZ (proxy for ICE Brent), NG, HO, RB, by contract month | Final exchange settlement of the held contract, Databento GLBX.MDP3, **stored privately** in em-macro-data |
| GOLD, SILVER, COPPER | COMEX GC, SI, HG, by contract month | as above |
| CORN, SOYBEANS, WHEAT | CBOT ZC, ZS, ZW, by contract month (US cents per bushel) | as above |
| US10Y | US 10y Treasury | US Treasury daily par yield curve, 10-year CMT (from C09; the series FRED republishes as DGS10 a business day later); fallback FRED DGS10 |
| DE10Y | German 10y Bund | Bundesbank daily (Svensson 10y) |
| GB10Y | UK 10y gilt | Riksbank SWEA GBGVB10Y, benchmark 10y gilt (from C09; before it, Bank of England IUDMNPY, published two to three business days late) |
| JP10Y | Japan 10y JGB | Japan Ministry of Finance JGB curve CSV; fallback Riksbank JPGVB10Y |
| FR-DE | France 10y over the Bund | Riksbank SWEA FRGVB10Y − DEGVB10Y |
| EUR, GBP, JPY, CHF, AUD, CAD | major FX | ECB euro reference rates crossed with EUR/USD (GBP from C10; before it, Bank of England XUDLUSS) |
| BRL, MXN | EM FX (from C09) | BCB PTAX sell rate (SGS 1); Banxico FIX (SIE SF43718) |

**Futures and options (from 2026-11-06; code `ledger/janus_fut.py`, settlements `ledger/settlements.py`).**
- The spot-price estimates (EIA via FRED) are gone. Each position holds a real contract month, filled at the
  first final settlement dated on or after the decision date.
- Roll rule: hold the earliest listed contract whose notice date is more than 35 days after the trade date. Roll
  at that day's settlements within 10 days of its notice date, keeping the notional. P&L includes roll yield, and
  each roll is charged as two trades.
- Stops are prices of the contract held when they were set. They act on the position's cumulative return, so a
  roll does not move them.
- Options: defined risk only (long calls and puts, debit and credit verticals). Valued with Black-76 at the
  implied volatility Janus states at entry, with its source or "estimate" (a model estimate), and at intrinsic
  value from expiry. The % at risk is the maximum loss.
- **Licence:** settlements are licensed (CME terms, passed on by Databento).
  - Records and public files never hold a settlement, fill or exit price, model value, notional or contract count.
  - A fill, roll or close records its date, contract, % at risk, costs and P&L in %, and `entry_digest` /
    `exit_digest` (SHA-256 of "code|date|price"). Anyone holding the private data can check the price used.
  - Daily P&L in % is in `futures_pnl.csv`.
- Fetching is in `ledger-daily` (one quoted Databento request a day, refused above US$1 of daily spend, shared
  with my decisions' marks).
- Janus sessions read the settlements through a **read-only** clone of em-macro-data (sparse, `ledger/` only). The
  CLI makes it through the environment's own GitHub access (the Claude Code git proxy: em-macro-data must be one
  of the session's repositories), with `DATA_REPO_READ_TOKEN` as a fallback where there is no such proxy. The
  Janus CLI refuses to write to the store. Only ledger-daily writes settlements.
- **Every position records the market's probability** (`market_probability`, `market_source`, `market_basis`):
  the best market-implied figure, or 50 with basis `none` where no market price exists
  (docs/fund/allocation.md).

**Dropped (listed, not substituted):** the Italy 10y spread (no free daily source); platinum, palladium, KC wheat,
soybean products, livestock and softs (not added); Norgate (licence).

**Bond P&L:** −duration × yield change (a 10-year par bond's modified duration at the entry yield).
**Costs:** the algorithm's model (10bp one way for major FX and developed bonds, 20bp for the FR-DE spread). Futures
and options use the T20-T22 model, 2 × (US$3 + 1 tick) per contract per side and leg. The square-root impact
estimate is added on every futures trade.
**Limits (enforced in code):** at most 2% at risk per position, 10% in total, 8 open (positions decided before C08;
a C08 book has no position-count cap and is kept in 3-10% in total, config change C13). Notional at most 10% of ADV and
below 80% of any exchange position limit (`ledger/capacity.py`), otherwise the size is cut.
