# Technology equities: data acquisition plan

Version 0.1, 2026-11-18. Budget assumed: about **S$500 a month**. Nothing has been bought, subscribed to or
downloaded, and no paid API was called. **No vendor's coverage, timestamps or licence was verified in this session:**
every source below is a candidate, and section 4 lists what must be checked before any money is spent. Prices are
deliberately not quoted: they change, and an unverified number would anchor a decision.

## 1. What the programme needs, in order of dependency

| priority | dataset kind (`sources.DATASET_KINDS`) | why it comes first | point-in-time requirement |
|---|---|---|---|
| 1 | `security_master`, `prices_daily`, `corporate_actions`, `delisting_returns` | every family; survivorship | includes delisted securities and their final returns; raw closes with actions, not only adjusted series |
| 2 | `classification_history`, `index_membership` | universe and peers | historical assignments with dates, not today's codes back-filled |
| 3 | `fundamentals_pit` | families A04, B, E04–E07 | filing acceptance time per value; original and restated values kept |
| 4 | `earnings_events` | families C | actual release time stamps, not only dates |
| 5 | `borrow_availability`, `short_interest` | all relative-value families | availability and fee history; short interest with publication dates |
| 6 | `analyst_estimates_pit` | families A03, C04–C06 | per-broker estimate history with publication (and capture) times |
| 7 | `macro_pit`, `fx_rates` | families F | vintaged (existing macro infrastructure; ALFRED-style vintages) |
| 8 | alternative kinds | families D, C07 | verified historical timestamps; descriptive-only until then |

## 2. A practical plan within about S$500 a month

**Tier 0: free and public (start here).**

- **SEC EDGAR filings and XBRL financial data**: filings carry an acceptance date-time, a candidate publication
  time stamp for US filers (a press release can precede its filing, so the acceptance time is a conservative,
  later bound for earnings); XBRL financial data are reported by filing, which may let originals and later
  amendments be separated. Machine-readable financial data are believed to start around 2009–2011 (phased XBRL
  adoption) — **unverified here**; earlier history needs another source. Licence: believed to be US government
  data, to be confirmed. To verify: how
  amendments and restatements appear in the facts; tag consistency across companies (revenue tags changed with
  ASC 606).
- **FINRA / exchange short-interest publications**: bimonthly short interest with publication dates. To verify:
  archive depth and the exact publication lag per period.
- **Exchange daily short-sale volume files**: not short interest; a flow measure. Archive depth to verify.
- **ALFRED (St. Louis Fed)**: vintaged macro series; the existing macro infrastructure already uses FRED-family data.
- **Kenneth French data library**: factor and industry returns for **descriptive** comparison and baselines; not
  point-in-time for a single stock and not a data source for signals.

**Tier 1: one paid price-and-fundamentals source (most of the budget).** The single most valuable purchase is a
US equity price history **including delisted securities, with corporate actions and delisting outcomes**, plus
point-in-time index membership. Candidates to evaluate (none verified):

- **Norgate Data** (US stocks package): the repository already uses Norgate for futures (`docs/manhattan/AUDIT.md`
  notes the private snapshot was not opened for equities). To verify: delisted coverage depth, whether delisting
  returns or final prices are provided, historical index constituents, and whether the existing licence covers
  equities.
- **Sharadar (via Nasdaq Data Link)** price and fundamentals tables: described by others as survivorship-free;
  **not verified here**.
  To verify: whether fundamentals carry the filing date per value and keep original versus restated values, how
  delisted tickers are identified, and redistribution terms.
- Other retail-priced vendors (e.g. EOD-style price APIs) usually lack delisted histories or delisting returns; use
  only if they demonstrably include them.

**Tier 2: not affordable at this budget (acknowledge, do not pretend).** CRSP and Compustat point-in-time (through
WRDS or directly), I/B/E/S detail history, institutional borrow histories (securities-lending data vendors), and
vendor relationship graphs are typically far above S$500 a month or restricted to academic licences. Families that
need them (A02, A03, C03–C06, D01–D06) stay at the bottom of the priority list until a cheaper verified source exists,
or are recorded **forward only**:

- **Forward collection** is the honest substitute for unaffordable history: from the day collection starts, a
  scheduled job could capture broker-published borrow availability and fees, earnings calendars with release times,
  and estimate snapshots, each with a capture time. Such data are point in time by construction and can feed the
  forward e-process directly. (No such job is created here: hard rule 16 forbids sessions creating writer workflows,
  and any new writer is Ethan's decision.)

## 3. Licensing and storage

- **No licensed rows in the public repository** (hard rule 7). Licensed data and anything derived from it row by
  row live in em-macro-data or on the iMac; `sources.DataContract.assert_publishable` and
  `pit_bridge(private_store=False)` refuse licensed sources by default.
- Provenance records (`manhattan.equities.provenance`) hold hashes only and may be committed.
- Before purchase, read each licence for: redistribution of derived data (aggregates in reports), use in automated
  research, retention after cancellation (a cancelled subscription that requires deleting history would break the
  audit trail: prefer licences that permit keeping purchased snapshots).

## 4. Verification checklist for any candidate source (do before paying)

1. Delisted securities included? Count by year; compare with a public count of delistings.
2. Delisting outcome: a delisting return, a final price, or nothing?
3. Corporate actions: raw prices plus actions, or only adjusted series? Split ratios and ex-dates present?
4. Identifiers: a permanent security id independent of ticker? Ticker history?
5. Fundamentals: a publication (filing) date per value? Original values kept after restatement?
6. Capture history: was the history recorded as it happened, or rebuilt later (backfill)? Ask the vendor in writing.
7. Classification: historical assignments with dates, or current codes only?
8. Licence: storage, derived-data publication, automated use, retention after cancellation.
9. A sample download into the private store, checked by the package's own tools: `PriceBook.total_returns` (split
   detection, delisting returns), `FundamentalStore` (timestamp sanity), `UniverseBuilder` (coverage by date).

Record each answer in the source's `DataContract`: `coverage_verified=True` is accepted only with
`coverage_evidence` naming where the answers to 1–7 are recorded (S8 M10: a bare claim is refused).

## 5. What can run on prices and EDGAR alone

`catalogue.data_tier` sorts the 39 families by what they need (HYPOTHESIS_CATALOGUE.md, "Data feasibility"): 12
families need only a survivorship-free price source, EDGAR structured data and free public series; 2 also need
EDGAR text parsed point in time; 25 need a history that is not affordable or not verifiably point in time (analyst
estimate histories, borrow, implied volatility, call transcripts, relationship graphs, alternative data). The last
group can be researched only through forward collection or after a data decision. Relative-value families in the
first two groups still need borrow assumptions, flagged as such, for their short legs.
