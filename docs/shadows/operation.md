# T25–T26 shadows: operation and implementation readings

Rules: [docs/prereg/T25-T26_live_shadows.md](../prereg/T25-T26_live_shadows.md) with Amendment 1. This note
records how Phase 2 implements them. It changes no rule, prediction, margin or date.

## Code

| file | what it does |
|---|---|
| `em_macro/t2526_data.py` | Databento history (one-off, cap US$20), the check against the Norgate snapshot (prices, chain, P1), the daily update under the shared US$1 cap. |
| `em_macro/t2526.py` | Go-live, the daily rebuild of both shadows from M1, the public and private files, and the evaluation (§5.3, §7.6). |
| `ledger/build.py` `build_shadows` | The "Shadows" section of the Algorithm page (public files only). |
| `tests/test_t2526.py` | Synthetic tests only. |

The a160bfd files are called unchanged. P0 checks their SHA-256 at go-live, and `tests/test_t2526.py` checks them on
every run. The adapter redirects `commod_data` inside the process only (`databento_layout`): the snapshot folder,
Norgate's metadata (none, so exchange rules give every date) and the last schedule month.

## Running it

1. **Set-up, once, before the 3 December 2026 rebalance** (and in any case before 5 May 2027): run the
   `shadows-setup` workflow (Actions → shadows-setup → Run workflow). It needs the `EM_MACRO_DATA_TOKEN`
   (read/write on em-macro-data) and `DATABENTO_API_KEY` secrets, and the Norgate snapshot folders of the 18
   markets in em-macro-data. It fetches the history, runs the check, writes the go-live record, and commits
   `results/shadows/prelive.json` and `results/shadows/GO_LIVE.json`.
   - **The history step** splits each market into calendar-year pieces (2023 … 2026) and downloads them in
     parallel (8 at a time). Each piece is logged as sent before it goes out (`databento/shadows/
     history_spend.jsonl`, private). It is committed and pushed to em-macro-data as soon as it is stored.
   - **A rerun never pays twice:** it skips stored pieces, and markets stored whole by run #1.
   - **The US$20 cap** counts everything already spent:
     - run #1, recorded in `UNLOGGED_SPEND` in `em_macro/t2526_data.py`: US$2.34;
     - every request sent since, interrupted ones and retries included.
   - **Run #1 (7 November 2026)** was cancelled by the 60-minute job timeout. It had stored CL, RB, HO, NG, HG,
     GC, SI and PL, which were pushed by the cleanup step, and was in the middle of ZC. Its output was buffered,
     so its log showed only warnings. The job now has 240 minutes and output is unbuffered.
2. **Daily:** the `ledger-daily` step "Shadows T25-T26" fetches new settlements, rebuilds both paths from M1 and
   commits `results/shadows/`. At M1's rebalance it runs P3 and P4 and marks the go-live record confirmed. If P4
   finds fewer than 6 active markets in either sleeve, M1 moves to the next rebalance, with both evaluation dates.
3. **Evaluation:** `python -m em_macro.t2526 evaluate --date <date>` on the dates in the go-live record only.
4. **After the check:** delete the Norgate snapshot when the subscription ends. Nothing reads it after the check.

## Implementation readings (where the document leaves a detail open)

1. **When a month is computed (§4.2, §7.2).** A month is computed on the first run on or after the 3rd at which
   every universe market's rebalance exists in the a160bfd schedule and is not flagged missing. Otherwise it waits
   until after the 10th, and the markets still missing then are missing for that month. The computed month and
   its missing markets are fixed in `status.json` (`rebalances`). A settlement that arrives later does not change
   that month. The unchanged schedule lists a month only once the market's execution-date settlement exists, so
   positions normally appear on the run after the execution date. They take effect at the execution settlement
   either way (§7.8).
2. **Missing on a decision date.** The a160bfd code (Amendment 4.4) flags a market-month missing when F1 *or F2*
   has no settlement on the decision date, for both sleeves. That code is used as it is, so T22 follows the same
   flag (§7.2's wording names F2 for T21 only).
3. **Daily P&L before a pending rebalance.** P&L from the first execution date of a month not yet computed is
   published once that month is computed.
4. **Drops (§7.4).** A held contract with no final settlement for more than 20 consecutive trading days is counted
   on the union of the universe markets' settlement days. The market is dropped from the first rebalance after the
   21st such day and leaves the cross-section from that month. Its held weight goes to 0 in full, not by T18's
   partial step. The exit is at its last settlement and costs 3× the one-way cost at the cost multiplier in use:
   the a160bfd closing trade charges 1×, and 2× is added. If the market has no settlement at all at that rebalance,
   the full 3× is charged on the book's first day on or after the rebalance.
5. **Active markets.** "Active" means eligible under `build_targets`' own condition: in the schedule, past entry,
   not missing, with σ and a signal. It is not the count of non-zero weights, because T21's middle rank weighs 0.
   P4, `status.json` and §7.6 all use this count.
6. **§7.6 interruption.** A month counts as interrupted if it was not computed, or was computed with every market
   missing. More than 3 such months in a row makes a shadow not evaluable.
7. **P1 (§8).** P1 is recomputed from the stored Databento history, so no extra request is made. It uses the same
   contracts and rule as `em_macro/t2526_avail.py`. The window runs from 2026-08-03 to the day before the plan's
   first rebalance (3 December 2026), as in the §3.2 check.
8. **First history month.** A contract whose delivery month is January 2023 or earlier is not written to the
   contract files. Its exchange-rule notice date falls before the history's calendar, and the roll rule never
   holds it at a rebalance with a decision date in the history.
9. **Price units.** The unit factor (Norgate ÷ Databento) is the power of ten nearest the median ratio on common
   days. It is recorded per market in em-macro-data `databento/shadows/factors.json`. `prelive.json` holds only
   the factor, counts and shares.
