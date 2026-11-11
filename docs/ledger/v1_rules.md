# v1.0 cut and stop rules (decision D004)

Decision **D004** (logged 11 Nov 2026 with the Ledger clerk, `data/ledger/decisions.csv`): no trade, v1.0 runs
unchanged (frozen, tag `v1.0-frozen`, commit 7886867), with pre-committed cut and stop rules for the whole v1.0
book. Probability 65% that v1.0 earns a positive live Sharpe after costs over its first 24 live months. Horizon
1 Nov 2028.

## The rules

Measured on the official month-end v1.0 index from the 1 Nov 2026 live start.

| # | Rule | Trigger | Action (Ethan's, at the next rebalance) |
|---|---|---|---|
| 1 | Halve | index 20% or more below its live peak | halve gross exposure; restore full exposure once the drawdown is back within 10% |
| 2 | Stop | index 27% or more below its live peak | close v1.0 entirely; restart only as a new pre-registered version |
| 3 | Time | live Sharpe after costs below zero at 24 months | stop v1.0 |
| 4 | Instrument | capital controls, a closed market, or a managed peg or crawl in a held currency | drop that instrument. **Superseded by D005**: no drop; a managed currency's volatility is floored and the book rescaled ([d005_vol_floor.md](d005_vol_floor.md)) |
| 5 | Carry-spread review | long-minus-short carry spread below its 2005-2019 10th percentile (3.176pp) at two consecutive month-ends | a written review within 7 days; no automatic cut |

## The monitor (flags only)

`python -m ledger.v1_rules monitor` runs in `.github/workflows/v1-rules-monitor.yml` after every successful
`systematic-monthly` run. It reads what that run committed and writes only:

- `data/ledger/v1_rules.json`: the latest month-end evaluation (index, live peak, drawdown, live Sharpe, carry
  spread against the threshold, each rule's status) and `flags`, one line per triggered rule;
- `data/ledger/v1_rules_history.csv`: one row per month-end (a re-run of the same month replaces its row).

The Ledger app shows the flags on Home and the full table on the Algorithm page. The night shift's morning report
(`nightshift/morning.py`) has a "v1.0 rules (D004)" section and puts every flag first under "Needs Ethan".

**It never changes exposure**, never edits frozen v1.0 code, configs, results or tags, and does not modify the
`systematic-monthly` workflow. Ethan acts on the flags. A flag stays in the latest evaluation as long as its
condition holds (rule 2 stays flagged for good once hit; rule 1 flags the month it halves and the month it
restores, and shows "in force" in between).

`python -m ledger.v1_rules monitor --dry-run` prints the evaluation without writing; `show` prints the stored one.

## Definitions

- **Official month-end v1.0 index:** 100 on 31 Oct 2026, then times (1 + net) for each booked live month
  (2026-11 onward) of `results/systematic/paper_pnl.csv`, net = `final_net` (else `net`). The same series as the
  app's v1.0 index. Month M is booked by the run on the 3rd of M+1, so the first value is the Nov 2026 month-end,
  booked on 3 Dec 2026.
- **Drawdown:** index / live peak - 1, the live peak including the 100 start. Rule 1 halves at <= -20% and restores
  at >= -10%; it is measured on the official index (the frozen book at full exposure).
- **Live Sharpe after costs:** `ledger.build.perf_stats` on the live monthly nets (mean x 12 / (sd x sqrt 12)), the
  app's figure; the net is after the frozen cost model and is an excess-of-cash return. Rule 3 is evaluated once,
  on the first 24 live months (2026-11 to 2028-10, booked on 3 Nov 2028).
- **Carry spread:** at each month-end, the equal-weighted mean carry of v1.0's long positions minus that of its
  short positions, FX and bonds together, in percentage points a year. Carry as the algorithm defines it
  (`em_macro.systematic.build_inputs`): FX = local policy rate minus fed funds; EM bonds = 10y yield minus the local
  policy rate; euro spreads = the spread; DE10Y = yield minus the policy rate; the latest available month when the
  current one is missing. Live values come from that month's screener file
  (`results/screener/screener_<as_of>.csv`), written by the same monthly run from the same inputs. Month-ends are
  counted from the 2026-10 positions (held at the live start).
- **Rule-5 threshold:** **3.176pp**, the 10th percentile over v1.0's 168 month-ends 2006-01..2019-12. Computed once
  on 11 Nov 2026 (`python -m ledger.v1_rules freeze`, which refuses to run again) from the frozen code, read only;
  the reproduced 2006-2019 net P&L matches the official paper P&L to within 5e-7. Stored with its method, source
  and distribution in `results/v1_rules/carry_spread_threshold.json` (monthly values in
  `carry_spread_2005_2019.csv`); `ledger/v1_rules.py` pins the file's SHA-256 and flags any change.
- **Rule 4 (superseded by D005, 11 Nov 2026):** the monitor no longer reads `config/v1_rules_rule4.csv` and never
  flags rule 4. It reports rule 4 as "superseded" with D005's managed list (`config/v1_managed_fx.csv`: currency,
  IMF de facto classification, source, date, and whether v1.0 holds it). The text below is D004's original rule.
- **Rule 4 (D004, original):** no free source flags capital controls, closed markets or managed pegs and crawls reliably, so the
  monitor reads Ethan's list, `config/v1_rules_rule4.csv` (`instrument` or `currency`, `event`, `start`, `end`,
  `source`, `note`). A listed currency covers its FX instrument and its country's bond or spread. A held instrument
  listed with a start on or before the month-end, and no end, triggers rule 4.
