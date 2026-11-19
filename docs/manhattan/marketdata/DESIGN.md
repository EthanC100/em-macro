# Manhattan market data: schema, validation, adapters and point-in-time availability

Version 0.1, 2026-11-19, session S12. Code: `manhattan/marketdata/`. Tests: `tests/test_manhattan_marketdata.py`
(56 tests, synthetic fixtures only). Nothing here fetches data, holds a credential, reads a licensed file, touches a
protected path or changes what any writer, runner or routine does. Nothing is switched on: no code outside the new
package and its test imports it.

## 1. What existed, and what this adds

Read before designing (all reused, none edited):

| existing interface | what it already does | how this layer uses it |
|---|---|---|
| `manhattan/roles.py` | the fence: exploration / reserve / forward / embargo per date and domain; `check_read`, `RunnerToken` | applied at **parse time** (`fence.py`) and again by the engine's `Reader` |
| `manhattan/engine/pit.py` | `PitStore` (period + availability day, revisions, data hash), `Reader` -> `Window`, the only door to data | `VintageSet.pit_store()` / `.reader()` hand the history over unchanged in shape |
| `manhattan/availability.py` | source publication contracts (`daily_lag`, `release_dates`, `conservative` with owner approval) | every `SourceDescriptor` converts to a contract this module accepts |
| `manhattan/ops/data.py` | first-seen capture of FRED / synthetic CSVs into the private ledger; backfill and late rules | same availability rules (seen / nominal / backfill / late), extended to timestamps and vendor receipt times |
| `manhattan/ops/timing.py` | session calendars and publication times for registration timing | not duplicated; exchange calendars can be passed to validation |
| `scripts/norgate_export.py`, `docs/infra/norgate_pipeline.md` | the Norgate export layout and manifests in em-macro-data | `NorgateExportAdapter` reads exactly that layout and verifies its hashes |
| `em_macro/commod_databento.py`, `ledger/settlements.py` | Databento GLBX.MDP3 `statistics`: final settlement = stat_type 3 with flag bit 0; cost guard, US$1 cap | `DatabentoStatisticsAdapter` reads the same records; it never fetches |
| `em_macro/commod_data.py` | Norgate snapshot reader for T20-T22 (licensed, private) | not imported; its notes on last trade dates are carried into the adapter notes |

What was missing for real historical futures, currencies, bonds and commodities: one canonical row schema across
vendors, a validator, timestamp-level (not day-level) availability, vendor revisions (preliminary vs final, snapshot
vs snapshot), immutable dataset identities, a fence applied before vendor values are read, and continuous futures
built as of a date. Drafts #84-#89 (execution, HTE, equities, evidence, simulation, accounting) do not cover this;
the package name `manhattan/marketdata/` does not collide with any of them.

## 2. Canonical schema (`schema.py`)

### 2.1 Instrument

| field | meaning |
|---|---|
| `instrument_id` | stable id (`[A-Za-z0-9_.:-]{1,64}`) |
| `asset_class` | `future`, `fx_spot`, `fx_forward`, `bond_cash`, `commodity_spot`, `index` |
| `domain` | the `manhattan.roles` fence domain its observations belong to (`futures_daily`, `fx_daily`, ...) |
| `exchange_tz`, `session_close` | IANA zone and local settlement/close time (DST handled by `close_utc`) |
| `currency`, `exchange` | quote currency; venue |
| futures | `root`, `multiplier`, `tick` (required) |
| currencies | `base`, `quote` (required; `currency == quote`) |
| cash bonds | `maturity`, `coupon`, `price_basis` in `clean`/`dirty`/`percent_of_par`/`rate` |

### 2.2 Contract

`contract_id = <ROOT>-<YYYY><month code>` (Norgate's own form), `last_trade`, `first_notice` (optional),
`first_trade` (optional); `notice = min(first_notice, last_trade)`.

### 2.3 Observation (one value)

| field | meaning |
|---|---|
| `instrument_id`, `contract_id` | contract only for futures |
| `session_date` | the trading day the value is about: the period the fence reads |
| `field` | `open high low close settle volume open_interest bid ask mid yield fixing` |
| `value` | finite float; a missing value is **no row**, never NaN |
| `settlement_status` | `final`, `preliminary`, `not_applicable` |
| `adjustment` | always `none` when stored (validation refuses anything else) |
| `observed_at_utc` | when the market produced it, if the source says (else the declared close stands in) |
| `published_at_utc` | the vendor's receipt/publication time, if the source has one |
| `first_seen_utc` | when this project captured the raw bytes holding it (the delivery's retrieval time) |
| `source_id` | the `SourceDescriptor` |

Key = (instrument, contract, session, field). Two values for one key are a revision (different publication or
vintage) or a conflict (same vintage, same publication: an error).

### 2.4 Adjustments and continuous series

Prices are stored **unadjusted, per contract, in exchange units**. `AdjustmentEvent` records a roll, a multiplier,
tick or price-unit change, or a redenomination, with `effective_date`, `factor`/`offset`, a `reference` and the
time it was **announced**. `continuous.build(window, ..., t)` builds a stitched (`none`), Panama (`difference`) or
`ratio` series **as of day t**: roll schedule from contract reference data only (hold the earliest contract whose
notice is more than `roll_sessions` weekdays away), prices as known at t's close through a fenced `Window`,
adjustment events only if announced by t's decision time, and a roll whose two roll-day prices are not both known is
an error, never filled. A back-adjusted history computed once over the full sample is look-ahead by construction;
this API cannot produce one.

## 3. Validation (`validate.py`)

Errors stop ingestion; warnings are stored with the dataset. Issue details name dates, fields and counts, never a
value, so reports of licensed data can be read anywhere.

| family | codes |
|---|---|
| reference data | `unknown_instrument`, `unknown_contract`, `contract_root_mismatch`, `future_without_contract`, `contract_on_non_future` |
| duplicates | `duplicate_conflict` (error), `duplicate_exact` (warning, kept once) |
| timestamps | `missing_publication_time`, `unexpected_publication_time`, `source_mismatch`, `published_before_observed`, `seen_before_published`, `observed_date_mismatch`, `non_session_date`, `before_first_trade`, `after_last_trade` |
| look-ahead | `lookahead_future_session` (session closes after retrieval), `lookahead_published_after_retrieval`, `lookahead_seen_after_retrieval`, `adjusted_price_stored` |
| values | `ohlc_inconsistent`, `nonpositive_price` (error for currencies/bonds; warning for futures, which can settle negative), `negative_count` |
| missing | `missing_session` (warning per gap against a calendar; weekdays by default, or an exchange calendar per instrument), `missing_fraction` (error above `max_missing_fraction`, default 5%) |
| stale | `stale_run` (warning: `stale_run` or more sessions unchanged, default 5) |

## 4. Adapters (`adapters/`)

Every adapter parses bytes it is handed (never a path it chose, never the network), asks the fence about each row
**before converting its values**, stamps the caller's retrieval time as `first_seen_utc`, and refuses what it cannot
map without guessing. `fetch()` raises `NotAuthorized` on all of them.

| adapter | input | timing semantics | licence |
|---|---|---|---|
| `FixtureAdapter` | canonical fixture CSV | synthetic `declared_delay` (60 min) or `vendor_receipt` | synthetic |
| `NorgateExportAdapter` | `scripts/norgate_export.py` snapshot: `manifest.csv/json`, `contracts/<MARKET>/<CONTRACT>.csv`, optional `metadata.csv` | `declared_delay`, **delay not declared** (see 9.1) | licensed, no redistribution |
| `DatabentoStatisticsAdapter` | `statistics` records as CSV (`ts_recv, ts_ref, stat_type, stat_flags, price, quantity, symbol`, ...) | `vendor_receipt` (`ts_recv`) | licensed (CME terms) |

Norgate checks before any value is read: every contract file listed in `manifest.csv` with matching bytes and
SHA-256 (a CRLF->LF conversion is caught), `close_is: settlement price`, `adjustment: none`, `generated_utc` not
after retrieval, markets mapped explicitly. `close` is stored as `settle` (`final`). Contracts come from
`metadata.csv` with last trade = Norgate's last quoted date (flagged in the notes; `em_macro/commod_data.py` lists the
exceptions).

Databento: stat 3 -> `settle` (`final` if `stat_flags & 1`, else `preliminary`), 6 -> `volume`, 9 ->
`open_interest`; session = UTC date of `ts_ref`; publication = `ts_recv`; `ts_event` is not taken as the
observation time (a final settlement is sent after midnight). Raw symbols map only through the planned request's
`symbol_map` (`plan_request`, pure). Preliminary then final is a revision with real timestamps.

Synthetic vendor-layout generators (`synthetic_norgate_export`, `synthetic_databento_statistics`) produce the real
layouts for fictitious roots `XA`/`XB` from SHA-256-derived numbers, so the real adapters are tested without a
licensed byte.

## 5. Observation, publication and research availability (`timing.py`)

| semantics | publication | research availability | basis | reconstructed |
|---|---|---|---|---|
| `vendor_receipt` | the row's `published_at_utc` | = publication | `vendor_timestamp` | no |
| `declared_delay`, first seen by nominal + grace | close + declared delay | max(nominal, first seen) | `first_seen` | no |
| `declared_delay`, nominal before the **series'** first capture | same | nominal | `backfill` | **yes** |
| `declared_delay`, seen later than nominal + grace | same | first seen | `late` | **yes** |
| revision (any later differing value) | its own | vendor: its publication; declared: max(nominal, first seen); never before the value it revises | | inherits |

The `ResearchClock(tz, decision_time)` maps an availability time to a **day**: usable at that day's decision time
if available by it, else the next day. That day becomes `PitStore`'s `available`. Reconstructed rows taint the
store (`PitStore.require_historical_evidence` refuses), matching ARCHITECTURE section 6.3: backfilled history is
exploration material with evidential weight 0. A Norgate snapshot is all backfill by construction.

Monitoring starts **per series** (source, instrument, contract, field): the first delivery holding any row of it.
A value that a later snapshot delivers for a series already monitored (a gap the vendor filled, a late correction)
is `late`, available when seen, never backdated to its nominal publication.

## 6. Immutable dataset identities (`provenance.py`, `store.py`)

Manifest = source descriptor, adapter name and version, request, retrieval time (given, never the wall clock), each
raw file's name/bytes/SHA-256, SHA-256 of the canonical rows, of the reference data and of the validation report,
row count, coverage dates, the fence decision, adapter notes, provenance gaps. **Dataset id = `MD-` + first 16 hex
of the SHA-256 of the manifest's canonical bytes** (`manhattan.spec.canonical_bytes`). Same inputs in any order on any
machine give the same id and the same bytes.

Store: `datasets/<id>/{manifest.json, rows.csv, reference.json, validation.json}` written once via rename, made
read-only, re-hashed on every load; `raw/<sha256>.bin` only when the fence admitted every row; `registry.jsonl`
append-only and hash-chained (`verify`). A store that accepts licensed data cannot be created inside this repository
(`LicenceError`, hard rule 7), and licensed sources cannot be put in a store that does not accept them.

Provenance is never invented: a source descriptor that lacks a declared delay, its reference or the owner's approval
records each as a gap; such a dataset can be stored and inspected, but `VintageSet` refuses it.

## 7. The fence (`fence.py`)

`FenceGate` applies `manhattan.roles` to every row's (instrument domain, session date) before parsing its values.
Exploration: admitted. Reserve: runner only, with a verified `RunnerToken` naming the (domain, window), while
`reserve.enabled`. Forward (after a freeze): runner only. Embargo (no role, the disabled reserve, fence margins):
never. Policy `refuse` (default) stops the ingestion; `exclude` skips and counts (count and first/last session
only). When anything was excluded the raw files hold protected dates and are not copied. A dataset that admitted
reserve or forward rows can be loaded only by the runner. With main's `config/manhattan.yaml` (no reserve,
exploration to 2019-12-31) no session can ingest or read a row dated after 2019-12-31.

Not enforceable here (ARCHITECTURE section 8, unchanged): code outside Manhattan opening raw files; a session
constructing a `RunnerToken` that claims verification. The layer makes every Manhattan path fail closed and records
what each ingestion admitted.

## 8. Pipeline (`ingest.py`) and command line

`ingest(adapter, files, request=, retrieved_utc=, instruments=, store=, fence=, caller=, policy=)`: licence check ->
fence-gated parse -> contract merge (conflicts refused) -> validation (errors stop) -> identity -> immutable store ->
registry. Then `VintageSet(store, ids, instruments, sources, clock)` -> `as_of(series, t)` at a time, or
`.reader(caller=, domain=, fence=)` -> `Window` for the engine, and `continuous.build`.

    python -m manhattan.marketdata demo [--out DIR]          # end to end on synthetic fixtures
    python -m manhattan.marketdata verify --store DIR
    python -m manhattan.marketdata ingest-norgate --snapshot DIR --store DIR --instruments FILE --retrieved ISO ...

## 9. Remaining data-provider requirements

### 9.1 Norgate Futures EOD (snapshots exist in em-macro-data; licence ends about 5 May 2027)

1. **Publication-delay assumption and its approval (Ethan).** Norgate's export carries no per-row release time.
   Someone must state when a session's settlement is assumed available (for example "the next exchange-local morning")
   and who accepts it; until then Norgate datasets are stored but not point-in-time. The value must not be guessed by a
   session.
2. **Instrument reference file** (public contract specifications, not licensed): exchange zone, settlement time,
   multiplier, tick and fence domain for each market. A session can draft it from `ledger/settlements.CONTRACTS`,
   `em_macro/commod_data.MARKETS` and exchange specs; Ethan reviews.
3. **Read access to the snapshot** on the machine that ingests: the iMac, or a session with em-macro-data attached
   read-only (ETHAN_ACTIONS, data-access option (a)).
4. **A private store location** outside this repository (iMac directory or a private repository). Not em-macro-data
   by default: sessions and the night shift do not write there.
5. **Retrieval time per snapshot**: the em-macro-data commit time that added it (`git log -1 --format=%cI --
   norgate/<snapshot>`), never later than reality and never earlier than `manifest.json`'s `generated_utc`.
6. Exchange holiday calendars per market (optional; weekdays are used otherwise and holidays appear as
   `missing_session` warnings).

### 9.2 Databento (genuine receipt timestamps; history from 2010-06-06; paid)

1. **Spending authorisation (Ethan; hard rule 11, ETHAN_ACTIONS item 8)**: budget and scope of any history purchase.
2. An authorised fetch path that reuses `ledger.settlements`' quote-first cost guard and spend log and the shared
   US$1 daily cap (or a separate cap Ethan sets), and resolves one- vs two-digit symbols as
   `em_macro.commod_databento.resolve_symbols` does. Not built here: `fetch()` refuses.
3. `DATABENTO_API_KEY` from the environment of that path only; output to a private store only (CME terms).

### 9.3 Currencies, bonds, commodities spot

No licensed daily source is in the project for cash bonds or commodity spot; the schema supports them, no adapter
exists. Spot FX: public FRED H.10 capture already exists in `manhattan/ops/data.py`; a thin adapter to this schema is
a follow-up. Bond exposure today is via Norgate bond futures (Bund, OAT, BTP, Long Gilt).

## 10. Shortest path to an authenticated historical-data experiment

Exploration only (to 2019-12-31), reconstructed, evidential weight 0, which is all a backfilled snapshot can be:

1. Ethan approves the Norgate delay assumption (9.1.1) and a session drafts the instrument file (9.1.2) for the
   markets wanted.
2. On a machine with the em-macro-data clone:
   `python -m manhattan.marketdata ingest-norgate --snapshot ../em-macro-data/norgate/2026-11_futures --store
   <private dir> --instruments <file> --retrieved <commit time> --delay-minutes N --delay-reference "..."
   --owner-approval "..."`. It prints counts only.
3. `VintageSet(...).reader(caller="session", domain="futures_daily", fence=default_fence())` -> `Window` ->
   `continuous.build` / `manhattan.engine` on dates to 2019-12-31; every variant logged with
   `python -m nightshift.logs variant` (hard rule 6).
4. For point-in-time-genuine history and anything confirmatory: Databento statistics with `ts_recv` (9.2) on the
   runner, or forward capture from the freeze (ARCHITECTURE section 6.3).

## 11. Tests

`python -m pytest -q -p no:cacheprovider tests/test_manhattan_marketdata.py` (56 tests, about 20 s): schema and
provenance; deterministic and idempotent ingestion across file orders and stores; tamper detection of rows,
manifests and the registry; licence refusal inside the repository; every validation code; Norgate manifest, hash and
mapping checks; Databento mapping and symbol refusal; the fence (default refusal after 2019, exclusion without
parsing, reserve only for a runner with a verified designated token, forward only after a freeze, runner-only
loading, the engine `Reader` still fenced); the three times and the research clock; preliminary-to-final and
snapshot revisions and later-filled gaps never backdated; PIT availability days; continuous series as of t unchanged by any later data,
re-based only by rolls known at t, adjustment events only once announced; missing data never filled; the CLI.
