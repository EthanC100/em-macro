# Exposure audit: FRED H.10 daily FX (BRL, MXN, ZAR)

Written 2026-11-25 by a build session for Project Manhattan (paper-only research). Machine-readable twin:
[exposure_audit_fred_h10.json](exposure_audit_fred_h10.json).

**What this is.** The first real dataset the Manhattan operational runner would read is the Federal Reserve's H.10
noon buying rates served by FRED: `DEXBZUS` (BRL per USD), `DEXMXUS` (MXN per USD) and `DEXSFUS` (ZAR per USD)
(`manhattan/ops/data.py` `SOURCES`, universe `U_FX_H10` in `manhattan/ops/compiler.py`, default `--sources` of
`manhattan/ops/runner.py`). This audit lists, from the repository and the git history available to this session,
every place where that history, or closely substitutable history for the same three currencies, was read, computed
on, or had results reported, and proposes a designation per segment.

**How it was done.** Text search of the working tree (`DEXBZUS`, `DEXMXUS`, `DEXSFUS`, `fred`, `FX_BR`, `FX_MX`,
`FX_ZA`, `BRL`, `MXN`, `ZAR`, carry, trend), `git log --all -S` for each series identifier and for `fred`/`fred_DEX`,
and reading the documents and committed result files that the search found. **No market data was fetched or read**:
no network request to FRED or any other source, and `data/processed/daily_panel.csv` (the committed panel that holds
the series) was not opened; its date range is taken from `README.md`, `results/coverage_report.md` and
`data/processed/coverage.csv` (coverage metadata only).

**Limitation of the git evidence.** This clone is shallow: 90 commits, the oldest `b10790d` (2026-11-19), whose
graft makes every file look "introduced" there, so `git log -S` cannot date the first appearance of any series
before 2026-11-19. The session did not unshallow (that is a network fetch of history containing the committed panel).
Earlier commits are cited from the documents that name them (`trials.csv`, `results/*/RUN.json`, result pages). To
complete the git part, the owner can run, in a full clone: `git log --all -S DEXBZUS --format='%h %ad %an %s'`
(likewise `DEXMXUS`, `DEXSFUS`, `FX_BR`, `daily_panel.csv`).

## 1. Summary

**Designation (default kept): the whole H.10 history of BRL, MXN and ZAR up to today is PREVIOUSLY EXAMINED.** The
evidence is stronger than the default needs:

- The series are the primary spot rates of the repository's core research since its start: the committed daily panel
  (`data/processed/daily_panel.csv`, 2005-01-03 to 2026-10-29/30, `em_macro/config.py` `FX_PRIMARY`).
- **Carry, time-series trend (TSMOM) and value** signals on these currencies were computed and their **2020-01 to
  2026-09 out-of-sample results** reported and seen (v1.0 frozen strategy, trial T01 = trials.csv T12, T02 = T13,
  T16-T19, T27; the README's carry table splits 2005-2021 and 2022 onward).
- Manhattan itself already ran **carry and TSMOM on BR, MX, ZA** (with TR, ID, PL) through its engine on 2005-01-03
  to 2019-12-31, with Sharpe ratios committed (`results/manhattan_engine/`).
- After the panel's last refresh, **substitute daily spot fixings for the same three currencies** (BCB PTAX, Banxico
  FIX with H.10 `DEXMXUS` as fallback, SARB) are marked every weekday by ledger-daily into `data/ledger/marks.csv`
  (from 2026-10-06 to 2026-11-24 at the time of writing), positions in BRL and MXN are held by the v1.0/v1.1 paper
  books monthly, and Janus forecasts BRL and MXN daily (from 2026-11-11).

**No historical segment qualifies as unexamined.** There is no gap between the panel's end (2026-10-30) and the
present in which these currencies were not observed by a session or the owner through a closely substitutable
fixing. Section 4 sets out the only stronger designation the evidence supports, as a **proposal for the owner**.

Model pretraining adds a further, unremovable exposure (section 3).

## 2. Evidence table

"Visible to" means who could see the results: *owner* (Ethan, who merges and reads results pages), *sessions* (any
Claude Code session with the public repository, including the night shift), *public* (the repository is public).

| # | path | commit (as cited) | what was read or computed | currencies | date range | signals / use | results visible to |
|---|---|---|---|---|---|---|---|
| E1 | `em_macro/config.py` (`FX_PRIMARY`), `em_macro/build_data.py`, `data/processed/daily_panel.csv`, `README.md` §1, `results/coverage_report.md`, `data/processed/coverage.csv` | panel in repository since the project's start (pre-shallow root); README "one row per weekday from 2005-01-03 to 2026-10-29" | FRED H.10 `DEXBZUS`/`DEXMXUS`/`DEXSFUS` downloaded and committed as row-level daily panel columns `FX_BR`, `FX_MX`, `FX_ZA`; cross-checked against BCB PTAX, Banxico FIX, SARB (5-day return correlations 0.97, 0.98, 0.88) | BRL, MXN, ZAR | 2005-01-03 to 2026-10-30 (5,470 observations each) | the raw history itself | owner, sessions, public |
| E2 | `README.md` §2, `em_macro/carry.py`, `data/processed/carry_monthly_returns.csv`, `results/carry_benchmark.csv`, `results/fig_carry_basket.png` | pre-shallow root | monthly carry excess returns per currency and basket | BRL, MXN, ZAR (+TRY, IDR, PLN) | 2005-2021 (fit) and **2022 onward (hold-out)** | carry | owner, sessions, public (Sharpe, return, drawdown per currency and split) |
| E3 | `trials.csv` T01; `results/systematic/` (fit 2005-2019, test 2020 on, `paper_pnl.csv`, `positions.csv`); tag `v1.0-frozen` = `7886867` | `7886867` (design frozen at `2dbfeb1`) | v1.0 systematic macro: cross-country carry, trend and value z-scores in 10 currencies (incl. BRL, MXN, ZAR) and bonds | BRL, MXN, ZAR among 10 | design 2005-01..2019-12; **test 2020-01..2026-09**; live paper positions monthly to 2026-11 | carry, trend, value | owner, sessions, public ("Sharpe 0.65, +6.0%/yr" out of sample) |
| E4 | `results/systematic_v1.1/` (`positions.csv`, `paper_pnl.csv`, `freeze/`); tag `v1.1-frozen` | as tagged | v1.1 paper book; BRL long in the 2026-11 positions | BRL (and others) | test 2020-01..2026-09; pre-live 2026-10 | carry, trend, value | owner, sessions, public |
| E5 | `results/T01_ts_trend.md`, `results/T01/` (`RUN.json`: run 2026-11-03, code `62524ff`) | `62524ff`, prereg `dc71998` | trial T01 (trials.csv T12): time-series trend sleeve on the six currencies | BRL, MXN, ZAR (+3) | 2005-2019 context; **2020-01..2026-09 decisive**; data through 2026-09 | TSMOM | owner, sessions, public (FAIL, SR 0.801 vs 0.654) |
| E6 | `results/T02_econ_momentum.md`, `results/T02/` | run 2026-11-04 | trial T02 (T13): economic momentum as a fourth currency signal | the six currencies | 2005-2019 context; 2020-01..2026-09 decisive | economic momentum + v1.0 signals | owner, sessions, public |
| E7 | `results/T16-T19_risk_batch.md`, `results/T16-T19/` | run 2026-11-04; inputs at `7886867` | carry-crash filter (T16), factor-capped sizing (T17), volatility forecasting (T19) on v1.0's currency positions | v1.0's currencies (incl. BRL, MXN, ZAR) | 2005-2019 context; 2020-01..2026-09 decisive | carry, risk overlays | owner, sessions, public |
| E8 | `trials.csv` T07, T09, T14, T15; `results/repricing/`, `results/fit/`, `results/test/` | pre-shallow root | election studies: day-1 and drift FX moves around elections | BRL, MXN, ZAR among EM | 2005-01..2021-12 fit; 2022-01..2026-10 hold-out; T15 prospective after 2026-11-04 | event moves | owner, sessions, public |
| E9 | `results/T27/`, `trials.csv` T27 | run 2026-11 | managed-currency volatility floor; withdrawn at step 0 before any weight or return | managed currencies (step-0 matrix) | 2005-2019 / 2020-2026-09 planned | volatility | owner, sessions, public (no return computed) |
| E10 | `config/exploration_manifest.json`, `docs/exploration_data.md`; em-macro-data `exploration/v1/extract.csv` | extract commit `043ff30` (em-macro-data) | night-shift explorer extract of 26 public daily series incl. `FX_BR`, `FX_MX`, `FX_ZA` | BRL, MXN, ZAR | 2005-01-03..2019-12-31 (capped by `explorer.data_end`) | available to the explorer; `results/exploration/log.csv` holds **no variant rows** (header only) | sessions (night shift), owner |
| E11 | `manhattan/factors/public_fx.py`, `manhattan/factors/reproduce.py`, `results/manhattan_engine/REPRODUCTION.md`, `reproduction.json`, `exploration_ledger.jsonl`, `exploration_log.csv`; `docs/manhattan/MANHATTAN_PROGRESS.md` Milestone E (E-08) | session 5M, 2026-11-12 | Manhattan engine reproduction of the frozen carry benchmark and the T01 trend sleeve, via `roles.check_read` (exploration role) | BR, MX, ZA (+TR, ID, PL) | 2005-01-03..2019-12-31 | carry, TSMOM | owner, sessions, public (Sharpe per currency, e.g. carry BR 0.522, MX 0.137, ZA 0.066; trend sleeve 0.190) |
| E12 | `data/ledger/instruments.csv`, `data/ledger/marks.csv` (ledger-daily) | daily bot commits, e.g. `f99c245` (2026-11-23) | daily spot marks: BRL from BCB SGS 1 (PTAX), MXN from Banxico SF43718 with **H.10 `DEXMXUS` as fallback**, ZAR from SARB EXCX135D | BRL, MXN, ZAR | 2026-10-06..2026-11-24 (growing daily) | marks for forecasts and paper books | owner, sessions, public |
| E13 | `janus/watchlist.yaml`, `data/janus/records.jsonl`, `docs/janus/daily_review.md` | daily Janus commits, e.g. `77a6205` (2026-11-24) | daily directional forecasts and a paper book on BRL and MXN (config change C09), marks from PTAX and Banxico FIX | BRL, MXN | 2026-11-11..2026-11-24 (growing daily) | discretionary forecasts | owner, sessions, public |
| E14 | `results/T23-T24_pre2000.md`, `trials.csv` T20-T24 | `633e983`, `7405e5f` | futures trend and carry sleeves; the window includes CME Mexican peso futures (6M) | MXN (futures) | 1979-05..1999-12 (T23-T24); 2000-2026-09 (T20-T22) | trend, carry, basis momentum | owner, sessions (aggregate results public; licensed rows not in the repository) |
| E15 | `manhattan/ops/data.py`, `compiler.py` (`U_FX_H10`), `runner.py`, `docs/manhattan/ops/RUNNER.md`, `docs/manhattan/OPS_PROGRESS.md`, `.github/workflows/manhattan-ops-runner.yml` | `b10790d` and earlier | the operational FRED fetcher and universe: **written, never run against FRED** (OPS_PROGRESS: "the FRED fetcher has never run against FRED"; the workflow is dispatch-only with its schedule commented out) | BRL, MXN, ZAR | none read | none | no data, no results |
| E16 | `tests/test_manhattan_pit_integrity.py`, `tests/test_automation.py`, `tests/test_q021_marks_never_downgrade.py` | in tree | fabricated FRED-format fixtures (a few hand-written values such as 5.40, 18.71) | n/a | fabricated | parser tests | not market data |

Search hits that are not exposures: `docs/queue.md` and `tests/fixtures/live/` (copies of a ledger fallback message),
`tests/test_manhattan_ops_blinding.py` (a source id in a health record).

## 3. What isolation cannot exclude: model pretraining

[BLIND_GENERATOR.md](BLIND_GENERATOR.md): "Model pretraining cannot be removed by isolation." Any model that writes
Manhattan hypotheses has read market history and papers up to its training cutoff, possibly including this public
repository, whose README and result pages report carry, trend and value performance on exactly these currencies. A
blind-channel hypothesis is blind to Manhattan's results, not to that history. So:

- every H.10 observation dated **before the generating model's training cutoff** must be treated as potentially
  known to the generator, whatever the repository shows;
- this public repository's own reported results on BRL/MXN/ZAR (E2-E8, E11) are plausible training data for later
  models;
- historical screening on this history is therefore a filter only (Protocol v3 §4), and any claim rests on forward
  observations dated after the freeze.

## 4. Designation per segment

| segment | designation | basis |
|---|---|---|
| H.10 BRL/MXN/ZAR before 2005-01-03 | **previously examined** (by substitution and pretraining) | not in the panel, but MXN futures were examined 1979-1999 (E14); pretraining covers it; Manhattan's fence makes nothing before 2020 forward-eligible anyway |
| 2005-01-03 .. 2019-12-31 | **previously examined** | row-level panel (E1); carry, trend, value computed and reported (E2-E8, E11); explorer extract (E10) |
| 2020-01-01 .. 2026-09-30 | **previously examined** (the repository's "evaluated once" confirmatory window) | v1.0 test, T01, T02, T16-T19 decisive results reported (E3-E7); carry hold-out 2022 onward (E2); election hold-outs (E8) |
| 2026-10-01 .. 2026-10-30 | **previously examined** | in the committed panel (E1); v1.1 pre-live month (E4); ledger marks from 2026-10-06 (E12) |
| 2026-10-31 .. today (2026-11-25) | **previously examined** (by close substitutes) | H.10 values not in the repository, but PTAX, Banxico FIX (with `DEXMXUS` fallback) and SARB fixings marked daily (E12); Janus BRL/MXN forecasts (E13); v1.0/v1.1 positions (E3-E4) |
| observation dates after a family's freeze and registration (`registration_utc`) | **not a historical segment**: forward data | eligible only as forward observations under `manhattan.ops.timing`; never "unexamined history" |

**Proposal for the owner (not a decision).** The evidence supports no "unexamined after date X" segment for this
dataset, because the same currencies are observed daily through substitutes. The strongest designation it supports
is narrower and procedural: *"H.10 observations dated after the freeze of a family and its witnessed registration
are forward data for that family; everything earlier is previously examined."* That is what `manhattan.ops.timing`
already enforces per prediction. If Ethan wants an unexamined historical segment, it would need a dataset these
sessions have not touched (not BRL/MXN/ZAR spot), which is outside this audit.

**Owner-facing consequences** (no threshold, protocol or configuration is changed here):

1. Historical screening on H.10 is exploration only (evidential weight 0), as it already is.
2. Families intended for this dataset should be treated as written with knowledge of carry/trend/value results on
   these three currencies (E2-E7, E11). A carry family is in any case not computable on `U_FX_H10` (spot only, no
   carry series).
3. The daily ledger marks and Janus forecasts on BRL and MXN continue during any pilot; they do not change a forward
   observation's eligibility, which rests on the freeze and registration times.
