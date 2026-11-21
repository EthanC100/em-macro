# S13 methodology experiments (synthetic only)

Output of `python -m manhattan.methodology.experiments`, read in
[docs/manhattan/methodology/S13_RESEARCH_METHODOLOGY.md](../../docs/manhattan/methodology/S13_RESEARCH_METHODOLOGY.md).

| file | experiment |
|---|---|
| `E1.json` | within-family scale: bootstrap SPA against the oracle and the portfolio test, 6 to 3,000 variants |
| `E1b.json` | analytic bars and minimum detectable Sharpe ratios, 1 to 10^7 variants |
| `E2.json` | across-family null calibration, 1,500 to 120,000 families, shared or disjoint windows |
| `E3.json` | planted effects at the same scales: power and FDR |
| `E4.json` | candidate duplication and the dedup-first remedy |
| `E5.json` | opposite-sign twin families |
| `E6.json` | registration after a look, rerun shopping, bootstrap-seed shopping |
| `E7.json` | forward e-LOND support by year, and the end-to-end funnel |

E1 to E7 except E1b were written at commit `3f56acd`; E1b at `7aa3ee2`, the only later change to the code, which
added one column to E1b and touched no other experiment. Each file records the commit, whether `manhattan/` was clean when it was written, the Python and NumPy versions and
the master seed. **Every number describes a synthetic generator; none is evidence about a market, and a synthetic
rejection is never a trading signal.**
