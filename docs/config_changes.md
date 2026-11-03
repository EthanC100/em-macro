# Configuration change log

Configuration changes to the paper-trading set-up. These are not trials: they do not change any signal, rule,
parameter or result of a frozen strategy, and they do not get a row in `trials.csv`.

| # | date recorded | effective from | change | reason | effect on frozen results |
|---|---|---|---|---|---|
| C01 | 2026-11-03 | the 3 December 2026 rebalance | Paper capital raised from US$100,000 to US$10,000,000. | Contract-size granularity for the planned commodity futures: at US$100,000 the smallest tradeable position in a standard futures contract is a large fraction of capital, so positions could not be sized to the model's weights. | None. v1.0 sizes positions by weights (per cent of capital), and all of its performance is reported in percentages, so its frozen results (`results/systematic/test/`, `docs/v1.0_freeze.md`) are unaffected. |

## C01 — paper capital US$100,000 → US$10,000,000

- **What changes:** the notional capital against which paper positions are expressed in currency units. From the
  3 December 2026 rebalance, paper positions are sized against US$10,000,000 instead of US$100,000.
- **What does not change:** v1.0's frozen design (`results/systematic/fit/frozen_design.json`), its code
  (`em_macro/systematic.py`), its signals, sizing rule, volatility target, leverage cap, no-trade band and cost
  model. `results/systematic/positions.csv` sizes positions in per cent of capital and `results/systematic/paper_pnl.csv`
  records returns in decimal fractions; neither file depends on the capital level.
- **Reporting convention:** all performance, in every period (design 2005–2019, test 2020-01..2026-09, live paper
  trading from October 2026), is reported in percentages of capital. A change in the capital level therefore
  changes no reported figure.
- **Classification:** configuration change, not a trial. It is not counted in N (the multiple-testing trial count in
  `trials.csv`) and does not open a new trial group.
- **Live paper record:** the October and November 2026 paper months are on the US$100,000 basis; December 2026
  onward on the US$10,000,000 basis. Because both are reported in percentages, the series is continuous.
