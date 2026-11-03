## Flags

| check | threshold | result | flag |
|---|---|---|---|
| BRL + MXN share of total P&L, 2005–2019 | > 50% | 42.6% | no |
| BRL + MXN share of total P&L, 2020-01 to 2026-09 | > 50% | 18.4% | no |
| USD + EM factor share of portfolio risk, average 2005–2026, version A (3-day, spec) | > 60% | 28.8% | no |
| USD + EM factor share of portfolio risk, average 2005–2026, version B (monthly, full book) | > 60% | 20.0% | no |

## Summary (factual; no trading recommendations)

- **Freeze.** The 2020-01 to 2026-09 result (+6.0% a year compounded, Sharpe 0.65, maximum drawdown −18.5%) is
  reproduced exactly from commit 7886867. None of the strategy files changed after that commit
  (`docs/v1.0_freeze.md`).
- **Countries.**
  - 2005–2019: the top three countries (Brazil, Italy, the United Kingdom) account for 144% of total net P&L.
  - 2020-01 to 2026-09: the top three (Germany, Turkey, South Africa) account for 108%.
  - BRL and MXN together are 43% and 18% of the total, below the 50% flag. Counting all Brazilian and Mexican
    instruments (currency and bond), the shares are 67% and 15%.
- **Asset class.** Bonds earn about two-thirds of net P&L in both periods: 65% in 2005–2019 and 72% in 2020–2026.
- **Signals.**
  - Both methods agree that carry is the largest positive contributor in 2020–2026 and value is negative.
  - Proportional method, 2020–2026: carry +4.5% a year, trend +3.1%, value −1.4%.
  - Shapley method, 2020–2026: carry +8.7%, trend −0.1%, value −2.4%. Carry alone earns 10.3% a year in the subset
    runs, more than the full composite (6.25%).
  - In 2005–2019 both methods give trend a large negative contribution (−7.4% proportional, −6.5% Shapley), and
    value and carry positive contributions.
- **Factors.**
  - The seven factors explain 27% (2005–2019) and 31% (2020–2026) of the variance of monthly returns.
  - The returns load positively and significantly on both the dollar index and the EM FX basket (t of 4–7), two
    factors that are strongly negatively correlated with each other.
  - The intercept is positive and significant in both periods (t 3.1 and 4.0).
- **Risk.**
  - The combined USD + EM factor share of ex-ante risk averages 28.8% (version A) and 20.0% (version B), with
    maxima of 74.8% (December 2013) and 55.2% (May 2022). Current values: 33.7% and 6.8%.
  - Version A covers on average 42% of the book's gross notional: the instruments with daily prices.
  - The largest single position averages 25% of portfolio risk in version A.
- **Multiple testing.**
  - The ledger (`trials.csv`) has 11 rows in 10 trial groups. Seven groups are the spec's N = 7. Three more come
    from this repository's history: the election drift rule, the no-trade-band alternative and the political-risk
    overlay.
  - Every §0.2 number reproduces, including the naive t, PSR, DSR, the Harvey-Liu haircuts and MinTRL. The one
    exception is the spec's ">200 years" MinTRL against SR0, which holds only at 95% confidence.
  - With the actual skew (0.185) and kurtosis (2.90) of v1.0's 2020–2026 monthly returns, which are close to normal:
    - PSR is 0.955.
    - DSR is 0.62 under the noise-only null and 0.83 with dispersed trials, at N = 7.
    - At N = 10, DSR is 0.54 under the noise-only null and 0.81 with dispersed trials.
    - MinTRL at 90% / 95% confidence against SR* = 0 is 3.9 / 6.4 years. The track record so far is 6.75 years.
    - The Bonferroni-haircut Sharpe is 0.18 at N = 7 and 0.04 at N = 10.
