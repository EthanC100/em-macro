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
| 5 | Carry-spread review | book carry at constant risk below its 2005-2019 10th percentile (2.7299pp) at two consecutive month-ends | a written review within 7 days; no automatic cut |

## The monitor (flags only)

`python -m ledger.v1_rules monitor` runs in `.github/workflows/v1-rules-monitor.yml` after every `systematic-monthly`
run whose `update` job ran and succeeded (not after a run whose due gate skipped the update, nor after a
keep-cache run), and by hand. It reads what that run committed and writes only:

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
- **Book carry at constant risk (rule 5's "carry spread"):** at each month-end, the sum over v1.0's positions of
  signed weight x carry, FX and bonds together, **not** divided by gross exposure, in percentage points a year on
  capital. v1.0 is always scaled to its 10% volatility target, so this is the carry the book earns per year at
  constant risk. Weights are v1.0's **raw** month-end weights as a fraction of capital: live,
  `size_pct_of_capital / 100` in `results/systematic/positions.csv` (the frozen run's output, signed by `side`);
  history, the frozen run's weights. Neither side applies `results/systematic/position_adjustments.csv`,
  `overrides.yaml`, D005 or any later decision, so history and live are comparable. Carry as the algorithm defines
  it (`em_macro.systematic.build_inputs`): FX = local policy rate minus fed funds; EM bonds = 10y yield minus the
  local policy rate; euro spreads = the spread; DE10Y = yield minus the policy rate; the latest available month when
  the current one is missing. Live carry comes from that month's screener file
  (`results/screener/screener_<as_of>.csv`), written by the same monthly run from the same inputs. Month-ends are
  counted from the 2026-10 positions (held at the live start). Each holding's contribution (weight x carry) is
  stored in `data/ledger/v1_rules.json`.
- **Rule-5 threshold:** **2.7299pp**, the 10th percentile over v1.0's 168 month-ends 2006-01..2019-12 (median
  6.13pp, range 1.15-10.64pp). Computed once on 11 Nov 2026 (`python -m ledger.v1_rules freeze`, which refuses to
  run again) from the frozen code, read only; the reproduced 2006-2019 net P&L matches the official paper P&L to
  within 5e-7. Stored with its method, source and distribution in `results/v1_rules/carry_spread_threshold.json`
  (monthly values and weights in `carry_spread_2005_2019.csv`); `ledger/v1_rules.py` pins the file's SHA-256 and
  flags any change.
- **Definition changes (both 11 Nov 2026, before any live month was evaluated; the second is final):**
  1. The first threshold (3.176pp) used an equal-weighted long-minus-short spread, which TRY's carry (about 33pp)
     dominated whatever its size in the book. Replaced by a position-weighted spread per unit of gross exposure.
  2. That threshold (0.5202pp) was out of reach: dividing by gross exposure let large low-volatility euro positions
     (about 48% of gross in 2006-2019, carry under 1pp) drag the history down, while the live book holds none
     (8.14pp at the 2026-10 baseline). Replaced by book carry at constant risk, above.

  The threshold file records both changes, the reasons, the superseded values and files with their SHA-256, and
  that no live month had been evaluated (`live_months_evaluated: 0`). The superseded files are kept unchanged in
  `results/v1_rules/superseded/` (`*_equal_weight.*`, `*_per_gross.*`) and are never used. The 2026-10 baseline was
  re-run: 40.10pp against 2.73pp, of which TRY 31.67pp (79%).
- **Rule 4 (superseded by D005, 11 Nov 2026):** the monitor no longer reads `config/v1_rules_rule4.csv` and never
  flags rule 4. It reports rule 4 as "superseded" with D005's managed list (`config/v1_managed_fx.csv`: currency,
  IMF de facto classification, source, date, and whether v1.0 holds it). The text below is D004's original rule.
- **Rule 4 (D004, original):** no free source flags capital controls, closed markets or managed pegs and crawls reliably, so the
  monitor reads Ethan's list, `config/v1_rules_rule4.csv` (`instrument` or `currency`, `event`, `start`, `end`,
  `source`, `note`). A listed currency covers its FX instrument and its country's bond or spread. A held instrument
  listed with a start on or before the month-end, and no end, triggers rule 4.
