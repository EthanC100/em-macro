# Manhattan audit: what exists, what can be reused, what conflicts

Recorded 2026-11-12 on branch `build/manhattan`, from `main` at `a2e24fa`. Phase A of
[MANHATTAN_PROGRESS.md](MANHATTAN_PROGRESS.md).

**What this audit read, and what it did not.** It read code, documentation, workflow files, `trials.csv` (every
column except `result` and `notes`) and the pre-registrations in `docs/prereg/` (by search for windows, samples and
headings). It opened no file under `results/` except the header of `results/exploration/log.csv` (which has no
rows), ran no backtest, and read no return series. Some pre-registrations quote summary statistics of earlier trials
in their disclosure sections (for example a pooled Sharpe ratio in T25-T26 §5.2); a few such lines were displayed by
the search. No return dated 2010 or later was read.

Words used below: **reuse** = import and call unchanged; **pattern** = the design is copied into `manhattan/` because
the existing code is tied to its own files; **protected** = in the CODEOWNERS block or `nightshift/protected.py`
`ALWAYS` (never edited by this work; importing is allowed).

---

## 1. Reusable components

### 1.1 The five components named in the brief

| component | what it does today | how Manhattan uses it | limits found |
|---|---|---|---|
| `lab/book.py` | One YAML per sleeve; `sha256(path)` of the file bytes appended to `lab/registry.csv` (`id, launched, sha256, file`); `check_frozen` refuses a file whose hash changed. | **Reuse** `sha256`, `registry`, `check_frozen` and the registry row format for Manhattan spec files. | It hashes raw file bytes, not a canonical form, so two YAML files with the same content and different key order have different hashes. Its validator accepts only ids `L\d{3}`, `kind: static`, one public daily-marked instrument and at most 12 months. Manhattan therefore adds its own canonical form and validator in `manhattan/` and keeps `lab.book` for the Lab. `lab/registry.csv` has a header and no rows: no sleeve has been launched. |
| `nightshift/logs.py` and `results/exploration/log.csv` | `log_variant` appends one row per variant (`logged_on, hypothesis_id, variant_id, description, data_start, data_end, n_obs, metric, value, params, code_ref, nominated, notes`); refuses a duplicate `variant_id` and any `data_end` after `config/night.yaml` `explorer.data_end` (2019-12-31). `log_opposition` appends to `results/opposition/calibration.csv`. | **Reuse** `log_variant` for every exploration-role variant (hard rule 6) and `log_opposition` (target type `idea`) for the critic's probability. | (a) The 2019-12-31 cap means reserve and forward evaluations cannot be logged there: they go to the Manhattan ledger only. (b) Each append re-reads the whole CSV, so cost grows with the square of the row count; it suits thousands of variants, not 250,000 executables. Variants are logged there; executables are logged in the Manhattan ledger. (c) The log has 0 rows today: the explorer has not yet produced a variant. |
| The Opposition (`.claude/agents/opposition.md`) | Read-only critic (tools: Read, Grep, Glob, WebSearch, WebFetch; Opus 5.5, high). Returns a JSON case against a PR, queue item, idea or sleeve with `p_works` 0-100; may block only for reasons (a)-(e). | **Reuse** as the pre-freeze critic. | Its "Read first" list includes "the hypothesis and its exploration log rows", and it can read the whole repository, which holds results. The Manhattan rule "the critic never sees outcomes" is therefore not enforced by the agent definition. `.claude/` is protected, so a restricted critic definition is Ethan's to add ([ETHAN_ACTIONS.md](ETHAN_ACTIONS.md) item 7). Until then the restriction is an instruction in the caller's prompt, not a mechanism. |
| `em_macro/mtstats.py` | `sr_sigma`, `psr` (probabilistic Sharpe ratio), `sr0` (expected maximum of N independent trials), `dsr` (deflated Sharpe ratio), `min_trl` (minimum track record length), Harvey-Liu haircuts. Per-period (monthly in the spec) Sharpe; `g4` is raw kurtosis. Not protected. Tests: `tests/test_mtstats.py`. | **Reuse** for descriptive columns in reports. | `dsr` assumes N independent trials; with correlated variants it is descriptive only. Protocol v3 makes no decision from PSR, DSR or minTRL. Callers must convert daily Sharpe ratios consistently (`sr` is per period, `T` is the number of periods). |
| `nightshift/guard.py`, `nightshift/protected.py` | `guard check <routine>` exits 4 while a busy workflow is queued or running (public Actions API), inside a busy window, or when main's `config/night.yaml` cannot be fetched. `protected <paths>` exits 1 for a protected path. | **Reuse** both from every Manhattan runner and build session. | `guard.check` applies the night window and run cap only to the three night routine names. For any other name (for example `manhattan-runner`) it checks busy workflows and busy windows only, which is what a runner needs. Manhattan compute caps therefore need their own config (`config/manhattan.yaml`); agents may not add them to `config/night.yaml`. |

### 1.2 Engine modules

| module | reusable part | status |
|---|---|---|
| `em_macro/systematic.py` | `signals` (carry, trend, value z-scores), `book_weights`, `run(inp, use=[...])` (a carry-only, trend-only or value-only run is a core factor sleeve), `stats`. 10 currencies and 13 ten-year bonds, **monthly**. | protected (frozen v1.0); import only |
| `em_macro/carry.py` | `carry_returns`: the EM carry benchmark. | protected |
| `em_macro/tstrend.py` | `ewma_vol`, `tsmom`, `scale_to_vol`, `with_costs`, `subset`. | protected (frozen v1.1) |
| `em_macro/t01.py` | `sharpe`, `max_drawdown`, `expected_shortfall`, `turnover`, `circular_block_indices`, `bootstrap_delta_sharpe` (paired circular block bootstrap, block 6, B = 10,000). | protected |
| `em_macro/holdout.py` | seeded, stratified cross-sectional split. | protected |
| `em_macro/cost_audit.py`, `results/cost_audit/cost_estimates.csv` | per-instrument cost estimates and cost sensitivity. | protected |
| `em_macro/commod_data.py`, `em_macro/t2022.py` | contract tables, roll rule with the 35-day buffer, F1/F2/F13, chained excess-return index; carry, basis-momentum and trend sleeves over 24 commodity, 5 currency and 5 bond futures. | not in CODEOWNERS, but pinned by SHA-256 in the T23-T26 pre-registrations and checked by `tests/test_t2526.py`: treat as frozen, import only |
| `em_macro/archive_raw.py` | deterministic `.tar.gz` (sorted members, fixed owner, modes, times), per-file manifest, `sha256_file`, `check`. | reuse for input-data hashes (the "data hash" of an evaluation) |
| `em_macro/events.py`, `calendar.py`, `event_study.py`, `data/events/calendar_13.csv` | 2,755 dated events with source URLs; event-window study code. | reuse for event-frequency hypotheses |
| `ledger/marks.py`, `ledger/pricing.py`, `data/ledger/instruments.csv` | 41 registered instruments with daily or monthly public marks; `mark_can_act` (first-hand daily marks only); `position_return` by instrument kind. | reuse for forward recording of public-data executables; `data/ledger/` is never hand-edited |
| `ledger/settlements.py` | Databento final settlements for CME-group futures, quoted before every request, shared US$1 daily cap, stored only in em-macro-data. | reuse read-only; hard rule 9 (`REFETCH_DAYS`) untouched |
| `ledger/audit.py` | hash chain (`prev_hash`, `hash`, genesis of 64 zeros), `verify`, correction records. | **pattern**: tied to `data/ledger/seals.jsonl`; the Manhattan ledger copies the chain and correction design in its own file |
| `ledger/commitments.py` | salted SHA-256 commitments; salts only in the private store. | protected; import only (used if an outcome must be committed publicly before it is disclosed) |
| `ledger/capacity.py`, `data/ledger/capacity_reference.csv` | capacity against daily volume. | reuse for the Scale-eligible tier |

**Gap that matters most:** there are no **daily** core factor returns. v1.0's carry, trend and value sleeves are
monthly and cover FX and bonds; the commodity carry and trend sleeves are monthly and need licensed data; no value
factor exists for commodities; no buy-and-hold series is defined per asset class. Protocol v3 tests daily returns
hedged against core factors, so a daily core-factor library is new work (Phase E) and its definitions need Ethan's
approval before the first batch is frozen (ETHAN_ACTIONS item 10).

### 1.3 Data sources: availability timing, revision policy, licence limits

| source | used for | available | revision policy in this repository | licence limit |
|---|---|---|---|---|
| FRED (H.10 FX, `DGS10`, `VIXCLS`, `DFF`) | spot FX (BRL, MXN, ZAR, EUR, GBP), US rates, VIX | daily, noon New York fixes; published next business day | latest values downloaded; raw cache gitignored; revisions not tracked | public |
| Yahoo Finance | TRY, IDR, PLN, DXY | daily close | latest values; isolated bad ticks removed by rule; no vintage | public; Yahoo's terms of use apply (not reviewed in this audit) |
| BIS `WS_CBPOL`, BIS CPI | policy rates, inflation | daily / monthly, with publication lag | latest vintage | public |
| National sources (Tesouro, Banxico SIE, SARB, BondSpot, Borsa Istanbul, BCB, BanRep, BCCh) | 10-year yields, short rates, official fixings | daily; Turkey from July 2018 only; no free daily source for Indonesia, Italy, Colombia or Chile 10-year yields | BondSpot, Borsa Istanbul scrapes and IMF WEO files are committed; the rest is refreshed | public |
| OECD MEI, ECB | monthly yields, euro-area yields | monthly averages, about one month late | latest vintage | public |
| IMF WEO, WGI, V-Dem, CBIE, WDI | fiscal, governance | annual | **latest vintage, not real time**; the risk model applies a 12-month lag instead | public |
| OECD revisions database, ECB RTD, ALFRED | T02 macro vintages | first-release vintages | **vintage data**; archived in `data/kept/T02/` | public |
| Ledger marks (`data/ledger/marks.csv`) | daily public marks for 41 instruments | written by ledger-daily (dispatched at 06:07 and 22:07 UTC; its own crons start hours late) | append-only marks with source fallbacks; first-hand marks flagged | public sources |
| Norgate Futures | 24 commodity and 10 financial futures markets, per contract, from 1977-1990 by market | exported on the AWS Windows server; snapshots `2026-11_*` in em-macro-data | fixed snapshots with per-file SHA-256 manifests | **Personal Use; no redistribution; 6-month subscription bought November 2026, ending about 5 May 2027.** `docs/shadows/operation.md` says the snapshot is deleted when the subscription ends. No row-level data in the public repository (hard rule 7). |
| Databento GLBX.MDP3 | final settlements of CME-group futures | history from 2010-06-06; a day's final settlement usually by 09:00 UTC next day | every fetch re-requests the last 7 days (late finals; hard rule 9) | **passes on CME terms; stored only in em-macro-data; paid per request (shared US$1 daily cap; T25-T26 history cap US$20).** Any Manhattan purchase of history is spending (hard rule 11). |
| AQR data sets | commodity benchmark checks | monthly, public download | fixed files with SHA-256, kept privately by practice | public, kept privately |

Consequences for Manhattan. (1) Public macro data in the monthly panel are latest-vintage: any hypothesis using them
must declare a publication lag or a vintage source, and the critic checks it. (2) Licensed futures history has a
hard end date unless the subscription is renewed, and Databento history starts in June 2010 and costs money
(ETHAN_ACTIONS item 8). (3) Raw data used by a designated evaluation is archived and hashed with
`em_macro.archive_raw`, which gives the data hash the ledger needs.

### 1.4 Tests

48 test files in `tests/`. Baseline on `a2e24fa` in this session: **705 passed, 127 skipped** in 3 minutes 25 seconds
(`python -m pytest -q -p no:cacheprovider tests`, exit code 0, output not piped), without the private data store
attached (the skips are tests that need the private Norgate snapshot, the v1.0 commit that a shallow clone lacks,
or an opt-in download). Two properties bind Manhattan tests:

1. **Tests gate existing writers.** `systematic-monthly` runs `python -m pytest -q tests` before it commits the
   rebalance, and ledger-daily runs four test files before it commits marks. A new test that fails on main would
   block the 3 December rebalance. The repository's convention (`.claude/agents/implementer.md`, "Tests gate existing
   writers") is to skip with a message in the writers' workflows and keep strict checks where `NIGHT_SHIFT_STRICT=1`
   (pr-review and promote). The Manhattan tests follow it: they fail in every Claude Code session and under
   `NIGHT_SHIFT_STRICT=1` or `MANHATTAN_STRICT=1`, and skip with a message inside a GitHub Actions workflow that sets
   neither (ETHAN_ACTIONS item 11).
2. **No test runs on a pull request.** No workflow is triggered by `pull_request`. A PR into main is tested only by
   the session that opens it (hard rule 15) and, for dev, by pr-review and promote.

### 1.5 Workflows, routines and other writers

Inventory: `docs/agent-system.md` section 1, re-checked against `.github/workflows/` (11 files:
elections-daily, elections-weekly, ledger-daily, ledger-intake, ledger-pages, ledger-screener, ledger-watchdog,
private-commitments, shadows-setup, systematic, v1-rules-monitor). Claude Code scheduled tasks: Janus Quick Check
(two tasks, every 30 minutes), Janus Daily Review (23:07 UTC), ledger-daily kick (06:07 and 22:07 UTC), the seven
night-shift routines, and three briefing tasks that write no git commit.

Reusable patterns: the `ledger-writers` concurrency group; `scripts/ledger_commit.sh` and
`scripts/night_commit.sh` (fetch, run, refuse changes outside an allowed path list, commit, push, retry from the new
head); `ledger-watchdog` (read-only, opens an alert issue); the "kick" task that dispatches a workflow because
GitHub starts this repository's scheduled runs 5.5-10.5 hours late (Q018).

There is **no iMac, launchd or macOS runner** anywhere in the repository. The only machine outside GitHub Actions is
the AWS Windows server that exports Norgate data (`docs/infra/`). The iMac runner is new (ETHAN_ACTIONS item 4).

### 1.6 Night-shift interactions

| night-shift element | effect on Manhattan |
|---|---|
| Explorer: at most one hypothesis per run, three per night, public data only, data to 2019-12-31, scratch code in `/tmp` | The explorer cannot generate a 50-100 hypothesis batch, and it reads `trials.csv`, `docs/prereg/` and the exploration log, so it is an **adaptive** generator by construction. The blind channel cannot be the explorer. |
| `scripts/night_commit.sh` path list | It commits only night-shift paths. `manhattan/`, `docs/manhattan/`, `config/manhattan.yaml` and any Manhattan data path are outside it, so the night shift cannot write Manhattan files except through a worker PR into dev. That is the conservative state and is left unchanged. |
| Promotion check (a) | Runs the full suite with `NIGHT_SHIFT_STRICT=1` on main merged with dev: Manhattan tests are strict there, so a changed SIM_PREREG without a matching hash blocks promotion. |
| Promotion check (c) | Refuses a dev that changes a protected path. Manhattan files are not protected today; ETHAN_ACTIONS item 5 proposes adding the frozen ones. |
| Safe mode | `config/night.yaml` has `safe_mode.enabled: true` on main today (run cap 4, explorer on Sonnet). Manhattan adds no night-shift load in this phase. |
| The Lab | Paper sleeves on public daily marks, 0.5% risk each. Manhattan tiers are separate: an Manhattan "Live-experiment eligible" family is not a Lab sleeve, and nothing in Manhattan writes `lab/`. |
| Guard windows | Manhattan runners call `python -m nightshift.guard check manhattan-runner` and do not start while ledger-daily, the Janus daily review or the monthly rebalance is running (hard rule 14). |

---

## 2. Conflicts with CLAUDE.md rules

| rule | conflict or contact point | how this design resolves it (default) |
|---|---|---|
| 1 Never push to main | Manhattan code reaches main only through a PR merged by Ethan. | This session opens one PR and does not merge it. |
| 2 Protected paths | The critic and generator definitions and any Manhattan routine live under `.claude/` (protected). `trials.csv` is protected. | No `.claude/` file is touched. Manhattan families are not rows of `trials.csv`. Whether Manhattan evaluations count in the trial ledger's N is Ethan's decision (item 12); default: they do not, and no Manhattan result is called a trial result. |
| 3 Writer-owned data | Manhattan needs a ledger directory. | A new directory owned by one writer (`python -m manhattan.ledger`, Phase D), never hand-edited, added to the inventory when built. No existing data path or workflow is changed. |
| 4 **Never pre-register a trial or run a confirmatory 2020-2026 test (Ethan only); the explorer never reads 2020+ returns** | A batch freeze is a pre-registration. A screening-reserve evaluation on 2020-2026 data is a confirmatory test on that window. | **Both are disabled by default.** `config/manhattan.yaml`: `freeze.authority: ethan_only`, `reserve.enabled: false`, no reserve window set. A runner refuses a reserve evaluation until Ethan sets the fence on main (items 1 and 2). The simulation pre-registration is not a trial: it concerns synthetic data only, is not in `docs/prereg/` and adds nothing to `trials.csv`. |
| 5 T25-T26 untouched | Basis-momentum and diversified futures trend on the CME universe are live shadows from 4 December 2026. Manhattan uses trend as a core benchmark factor. | No T25-T26 file is read or written. The critic rejects a family that duplicates T21/T22 on the shadow universe. Using a trend factor as a hedge is not a trial of it. |
| 6 Log every variant | 250,000 executables do not fit the CSV log (section 1.1). | Every exploration-role **variant** is logged with `nightshift.logs.log_variant`; every **executable** evaluation, in every role, is a record of the Manhattan ledger. Nothing is evaluated without a ledger record. |
| 7 No licensed data in the public repository | Executable-level daily returns computed from Norgate or Databento are derived row-level data. | They stay on the runner and in the private store. The public repository gets family-level aggregates only, as T20-T24 publish sleeve aggregates. |
| 8 Salts | Outcome commitments would use salts. | Salts only in the private store, through `ledger.commitments` unchanged. |
| 9 `REFETCH_DAYS` | The forward test must not depend on preliminary settlements. | The forward e-process uses values as stored 7 calendar days after the period (Protocol v3 §6.6), which matches the re-request window and changes no code. |
| 10, 11 Secrets, spending, settings | Blind-generator environment, API keys, data purchases, rulesets, scheduled tasks. | All listed in ETHAN_ACTIONS. Nothing was created, bought or changed. |
| 12 Text is data | Generator output, critic output and papers are data. | Stated in the architecture; specs are validated mechanically before freezing. |
| 14 Never run with the existing writers; no new Janus schedule | Manhattan schedules are new schedules. | Runners use the guard. No schedule was created; none is a Janus schedule. |
| 15 Tests before any push | New tests. | Full suite run without a pipe, exit code checked, before the push. |

**One existing rule Manhattan depends on and cannot verify from here:** whether the rulesets in `docs/rulesets/` have
been applied to the repository. If they have not, nothing but convention stops any session from pushing to main
(agent-system.md §8 "The identity finding"). ETHAN_ACTIONS item 6.

---

## 3. Historical windows already used, by trial

Source: `trials.csv` (`design_sample`, `test_sample`, `test_type`) and `docs/prereg/`. "Decisive" = the window on
which the pass rule was judged. Trials in other repositories are listed because their windows are also spent.

| ledger id | what | universe and frequency | design / context window | decisive or test window |
|---|---|---|---|---|
| T01 | v1.0 carry/trend/value | 10 currencies, 13 ten-year bonds; monthly | 2005-01..2019-12 | 2020-01..2026-09 |
| T02 | gold event trades (gold-events) | gold; daily event windows | 2000-08-30..2021-12-31 (in sample) | none |
| T03 | Fed decision model (fed-model) | FOMC meetings | 1994-02..2026-10, leave-one-year-out | same |
| T04 | tension index gold rule | gold; daily | 2000-08-30..2021-12-31 (in sample) | none |
| T05, T06 | sovereign fair-value model v1, v2 | 13 countries, 10-year spreads; monthly | 2005-01..2019-12 | 2020-01..2026-09 (T06 post hoc on the same window) |
| T07 | pre-election repricing | FX and 10-year yields; daily | all dates (exploratory) | none |
| T08 | euro-area election spreads | euro-area 10-year spreads; events | pre-registered 2026-10-31 | euro-area elections |
| T09 | election drift rule | 6 EM currencies; event windows | 2005-01..2021-12 | 2022-01..2026-09 |
| T10 | no-trade band alternative | v1.0 universe; monthly | 2005-01..2019-12 | none |
| T11 | political-risk overlay | v1.0 universe; monthly | 2005-01..2019-12 | 2020-01..2026-09 |
| T12 | time-series trend sleeve (prereg T01) | v1.0 universe; monthly | 2005-2019 context | 2020-01..2026-09 |
| T13 | economic momentum (prereg T02) | 10 currencies; monthly | 2005-2019 context | 2020-01..2026-09 |
| T14 | election-day surprise | 6 EM currencies; day 1 | 2005-01..2021-12 (26 elections) | 2022-01..2026-10 (9 elections) |
| T15 | election continuation rule | EM elections | none (rule fixed) | prospective, after 2026-11-04 |
| T16-T19 | risk batch | v1.0 universe; monthly | 2005-2019 context (T16 walk-forward from 2005) | 2020-01..2026-09 |
| T20-T22 | commodity carry, basis-momentum, diversified trend | 24 commodity, 5 currency, 5 bond futures; monthly | 2000-01..2019-12 (sleeve Sharpe floor; Build 0 checks from 1990) | 2020-01..2026-09; Clark-West for T20 on 2010-01..2026-09; cost multiple on 2000-01..2026-09 |
| T23, T24 | the T21 and T22 sleeves before 2000 | 19 commodity markets; 24 instruments | (1991-02..1999-12 had already been computed, unreported) | 1979-05..1999-12 |
| T25, T26 | live shadows of T21, T22 | CME-group universe | none | live 2026-12..2031-11, plus 36 months if inconclusive |
| T27 | managed-currency volatility floor | v1.0 universe; monthly | 2005-01..2019-12 exploration (planned) | 2020-01..2026-09 (withdrawn after Step 0; counts only, no return computed) |

Count of confirmatory looks at **2020-01..2026-09** on the 13-country FX and bond panel: T01, T05, T06, T11, T12, T13, T16, T17,
T18, T19 (ten), and on the futures universe T20, T21, T22 (three). T27 looked at counts only.

### 3.1 Remaining clean reserve per asset class

Two grades are used, because "clean" has two meanings.

- **Grade 1:** no trial of this programme has evaluated any hypothesis on that asset class, frequency and window.
- **Grade 2:** the window has been evaluated, but only for other, recorded hypotheses. It can serve as a screening
  reserve for a new family, with two stated weaknesses: the earlier results are public (and known to any generator
  that can read this repository), and the new family may share factor exposure with the strategies already tested
  there.

Neither grade is clean with respect to **what the language model knows**: its training data cover market history up
to its cutoff. Only data dated after a batch is frozen are clean in that sense.

| asset class and frequency | Grade 1 remaining | Grade 2 | data limits |
|---|---|---|---|
| Spot FX, v1.0's 10 currencies, monthly | **none** in 2005-01..2026-09 | 2020-01..2026-09 has ten confirmatory looks, all on carry, trend, value and risk-rule variants | the panel starts 2005-01; nothing earlier is built |
| Spot FX, daily | none strictly: T07 used all dates for pre-election repricing; T09 and T14 used election windows 2005-2026 | non-event days 2005-01..2026-10 have never carried a trading rule | the daily panel covers the six original EM currencies only; Yahoo gaps (August 2008) |
| 10-year government bonds, 13 countries, monthly | **none** in 2005-01..2026-09 (same trials as FX; T05/T06 on spreads) | as FX | 9 of 23 instruments have no daily price; bond returns use monthly-average yields |
| 10-year bonds, daily | not usable as a reserve: no daily series for 4 countries, Turkey from July 2018 only | | |
| Commodity futures, 24 markets, monthly | **none** in 1979-05..2026-09 for carry, basis-momentum and trend | all of it, for other mechanisms | Norgate licence ends about 5 May 2027; Databento from 2010-06-06 only, CME-group only, paid |
| Commodity futures, daily | all history is Grade 1 for daily-frequency rules (every trial was monthly), but shares the data limits and factor exposure above | | as above |
| Currency futures (EUR, GBP, MXN, BRL, ZAR) and bond futures (Bund, OAT, BTP, Bono, Long Gilt) | none for trend, 2000-01..2026-09 (and GBP, MXN from 1979-05); Grade 1 for other mechanisms | | Norgate only |
| Gold | none for event rules in 2000-08-30..2021-12-31 (other repository) | | |
| Fed funds futures around FOMC meetings | none in 1994-02..2026-10 (other repository) | | |
| Euro-area sovereign spreads | none around elections; none for the fair-value model 2005-01..2026-09 | | |
| Equity index futures, single stocks, credit, short-term interest rates, volatility, crypto | **all history** (no trial has touched them) | | no pipeline in this repository; whether the Norgate snapshot holds them was not checked (the private store was not opened) |
| Any asset class, after a batch's freeze date | **all of it**, for that batch | | T25-T26 already occupy 2026-12..2031-11 for their two sleeves on the CME universe |

Reading of the table. For the asset classes this programme already trades, the only Grade 1 reserve is the future.
A historical screening reserve is therefore Grade 2 at best, which is why Protocol v3 treats historical screening
as a filter at a 20% false discovery rate and requires forward evidence for any claim at 5%. Where the fence goes
(which window is exploration and which is reserve, per domain) is Ethan's decision (ETHAN_ACTIONS item 1); the
default is no reserve at all.

---

## 4. Findings that change the brief's assumptions

1. **The Opposition, as defined, sees outcomes** (section 1.1). The "critic never sees outcomes" rule needs a
   restricted agent definition that only Ethan can add.
2. **The exploration log cannot hold executables or post-2019 windows** (section 1.1). The Manhattan ledger is the
   system of record; the log receives exploration-role variants.
3. **No daily core factors exist** (section 1.2).
4. **A new test can block the monthly rebalance** (section 1.4).
5. **Licensed futures history expires about 5 May 2027** (section 1.3).
6. **Nothing here is clean with respect to the model's own knowledge, and em-macro itself is public**
   ([ARCHITECTURE.md](ARCHITECTURE.md) §8).
