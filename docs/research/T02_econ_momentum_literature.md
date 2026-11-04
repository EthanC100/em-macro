# T02 — economic momentum: specification from the literature (Step 1)

Written 2026-11-03, before any T02 data were examined and before any T02 signal, return or backtest was computed.
Branch `trial/T02-econ-momentum`. Baseline v1.0 (tag `v1.0-frozen` = `7886867`) is not modified.

## 1. Sources read

| # | source | status | what it gave |
|---|---|---|---|
| S1 | Dahlquist, M. and Hasseltoft, H. (2020), "Economic momentum and currency returns", *Journal of Financial Economics* 136(1), 152–167. Abstract via IDEAS/RePEc and ScienceDirect (full text paywalled). | peer-reviewed | headline result: Sharpe 0.70, significant alpha vs carry, momentum and value; subsumes the carry alpha; past trends "linked to economic activity and inflation" |
| S2 | Dahlquist and Hasseltoft, working paper dated 27 March 2015, University of Zurich repository (ZORA), full text (30 pp. + tables). Same paper as SSRN 2579666 (posted March 2015, last revised 31 March 2019 as Swedish House of Finance Research Paper 16-14). | working paper, full text | the full construction: data, trend measures, rank weights, aggregation, benchmarks, Tables 1–2, turnover and cost results |
| S3 | Fan, Z. et al. (2025), "Understanding the performance of currency basis-momentum", *European Financial Management* (Queen's University Belfast repository), and its EFMA 2023 conference version "Decomposing basis-momentum in currency markets". | peer-reviewed; replicates the published signal as a benchmark | the published (2020) construction: two fundamental indices, log growth over 1–60 months, 120 sub-strategies, 33 currencies |
| S4 | Master's thesis, Aalto University (2020), "Macroeconomic momentum in the government bond market", which replicates the 2019 version in FX and extends it to bonds. | not peer-reviewed | the index equations (eqs 6–8), the 3-month lag, forward-filling of quarterly data, and the 2019 version's numbers (inflation-measure and combo Sharpe 0.66 and 0.71; alpha 1.36% a year) |
| S5 | Alpha Architect summary "Fundamental momentum, the carry trade, and currency returns" (search snippet only; the page blocks fetching). | practitioner summary | sample Jan 1976 – Mar 2017, 21 developed markets plus emerging markets; five macro variables |
| S6 | paperswithbacktest.com strategy page (third-party implementation). | not peer-reviewed | a post-publication G10 implementation reporting Sharpe about 0.20 since 2019 |
| S7 | Spec `docs/research/algorithm_spec_2026-11.md` §4.1, §5, §17.1 (#9), §17.4. | internal | the spec's own simplification of the signal and its prior |

Not obtained: the published JFE text and its online appendix; the SSRN 2019 PDF (blocked, HTTP 403). The construction below is therefore the 2015 working paper's, corrected to the published version where S3 and S4 (which cite the 2019/2020 text directly) differ from it.

## 2. The signal, as published

### 2.1 Data and variables

- **Currencies (S1, S3, S5):** 21 developed markets plus emerging markets, January 1976 to March 2017; spot and one-month forwards from Datastream; USD excess return via the forward. The economic-momentum portfolios use 33 currencies for which the macro data exist (S3, following the paper).
- **Macro variables (published version; S3 footnote, S4, S5):** five, all from the OECD database: industrial production, retail sales, unemployment, consumer prices and producer prices. Industrial production, retail sales and unemployment are seasonally adjusted; unemployment is the harmonised rate.
- **2015 version (S2):** eight variables: one-month interest rates (daily, from covered interest parity), yield spreads (short minus long), ten-year yields, inflation, trade balance ((X−M)/(X+M)), industrial production, retail sales and unemployment. The interest-rate variables and the trade balance were dropped in the published version. The 2015 text already notes that a trend combo "that excludes the interest-rate variables yields a Sharpe ratio of 0.85".
- **Sign convention (S2 §2.2):** every variable is defined so that an increase means strong economic conditions: positive growth in production and sales, positive inflation, and the **inverse** of unemployment.
- **Quarterly series** are brought to monthly frequency by carrying the latest quarterly observation forward (S4).

### 2.2 Fundamental indices (published version; S3 footnote, S4 eqs 6–8)

For each country c and month t, two chain-linked indices are built from the **equal-weighted average of the monthly growth rates** of their components (first observation set to 100):

```
g_econ,c,t = (1/3) [ RS_t/RS_{t-1} - 1  +  IP_t/IP_{t-1} - 1  +  (1/U_t)/(1/U_{t-1}) - 1 ]
FI_econ,c,t = (1 + g_econ,c,t) * FI_econ,c,t-1                      (economic-activity index)

g_infl,c,t = (1/2) [ CPI_t/CPI_{t-1} - 1  +  PPI_t/PPI_{t-1} - 1 ]
FI_infl,c,t = (1 + g_infl,c,t) * FI_infl,c,t-1                      (inflation index)
```

A third "combo" index (all five components) is reported in S4 as its own measure; S3 describes the published trend combo as the aggregation of the 120 sub-strategies of the two indices.

### 2.3 Trend measures

- **Published version (S3, S4):** log change over the look-back l: `z_{c,i,l,t} = ln FI_{i,c,t} − ln FI_{i,c,t−l}`, for l = 1, 2, …, 60 months and each index i. That gives 60 sub-signals per index, 120 in total.
- **2015 version (S2 §3):** two trend measures, (a) changes (log changes for CPI, IP, RS and unemployment; actual changes for the trade balance, spreads and yields; short-rate changes normalised by an EWMA volatility with decay 0.94) and (b) the Newey-West t-statistic of a linear time-trend regression over the look-back (24–60 months for monthly data). Table 2 of S2 shows the two measures perform alike (Sharpe about 1.0 each). The published version keeps only (a) (S3: "in line with Dahlquist and Hasseltoft (2020), we adopt the log growth rate to measure the trends").
- **Look-backs:** 1–60 months, "to measure various trend frequencies and avoid arbitrary lookback periods" (S2). The strongest contribution comes from long-term trends: short (1–12 m), medium (13–36 m) and long (37–60 m) combos have Sharpe 0.81, about 1.0 and 1.06 in the 2015 version (S2 Table 2), with lower turnover for long trends (70% a month against more than 100%).
- **Timing and publication lag (S2 footnote 8; S4):** all trend measures are computed at the end of each month, at rebalancing; non-interest-rate variables are **lagged three months** "to guarantee that investors had access to relevant macro information when rebalancing and to address the fact that macro data are often published with a lag". The authors add that "such information lagging has a small impact on the final results". The macro data are the OECD's current (revised) series, not real-time vintages.

### 2.4 Portfolio formation and aggregation (S2 §3.4; S4 eq 12)

- **Rank weights** (Asness, Moskowitz and Pedersen 2013; Koijen et al.): for each sub-signal (index i, look-back l) the weight of currency c is
  `w_{c,i,l,t} = a_t [ rank(z_{c,i,l,t}) − (1/C_t) Σ_c rank(z_{c,i,l,t}) ]`, with a_t scaling the long and the short side each to one dollar (dollar neutral). Quintile and quartile sorts give similar results (S2 footnote 9).
- **Sub-strategy return:** `R_{i,l,t+1} = Σ_c w_{c,i,l,t} R_{c,t+1}`.
- **Aggregation to the combo (S2):** each sub-strategy is weighted by the inverse of its own volatility over the past three years, weights normalised to sum to one, then the whole portfolio is scaled by 5% divided by its past realised volatility (volatility timing). S4's replication uses equal weights across the 60 look-backs instead.
- **Monthly rebalancing**, end of month.

### 2.5 Reported performance

**Published version (S1, S4 citing the 2019 text, S5):**

| statistic | value |
|---|---|
| sample | Jan 1976 – Mar 2017; 33 currencies with macro data (developed and emerging) |
| trend combo (economic activity + inflation) Sharpe | 0.70 (abstract); 0.71 (S4) |
| inflation-measure strategy | 3.28% a year excess return, Sharpe 0.66 (S4) |
| benchmarks in the same sample | carry 3.09% a year, Sharpe 0.57; price momentum 1.61%, 0.25; value 2.58%, 0.42 (S4) |
| alpha vs carry, momentum and value | 1.36% a year, significant; carry the only significant (positive) loading, momentum and value slightly negative and insignificant (S4) |
| alpha vs Menkhoff et al. (2012) factor-mimicking portfolios | 1.37% a year, significant (S4) |
| time-series version of the signal | Sharpe 0.59 with a significant alpha against time-series benchmarks (ScienceDirect highlights, via search) |
| predictability horizon | past trends predict excess returns and exchange-rate changes up to 12 months ahead; inflation predicts positively, through the policy response |
| carry | the trend combo drives out the carry portfolio's predictive power; the carry alpha becomes insignificant once trend strategies are included |

**2015 working-paper version (S2, 20 currencies, Jan 1976 – May 2014):**

| strategy | mean %/yr | vol % | Sharpe | hit ratio | worst drawdown % |
|---|---|---|---|---|---|
| short rate | 4.85 | 5.48 | 0.89 | 0.63 | 10.9 |
| yield spread | 4.56 | 5.70 | 0.80 | 0.60 | 13.0 |
| long rate | 3.06 | 5.62 | 0.54 | 0.58 | 16.6 |
| inflation | 4.47 | 5.87 | 0.76 | 0.61 | 20.5 |
| trade balance | 2.77 | 5.76 | 0.48 | 0.59 | 26.0 |
| industrial production | 2.32 | 5.48 | 0.42 | 0.53 | 17.5 |
| retail sales | 1.50 | 5.33 | 0.28 | 0.57 | 26.6 |
| unemployment | 2.60 | 6.95 | 0.37 | 0.54 | 25.3 |
| trend combo (all eight) | 6.15 | 5.60 | 1.10 | 0.68 | 12.4 |
| combo excluding interest-rate variables | | | 0.85 | | |

Other 2015 results: alpha of 3.22% a year (52% of the combo's mean return) against dollar-carry, long-only, cross-sectional carry, momentum and value; the combo's turnover is 85% of wealth a month; net Sharpe 0.96 assuming a 15 bp bid–ask spread (Table 10); worst months March 1995 (−6.6%), September 2008 (−4.4%), July 1999 (−4.3%); predictive panel coefficient 0.21% next-month return per one-standard-deviation of standardised weight; average pairwise correlation across the eight single-variable strategies about 0.2.

### 2.6 Out-of-sample and post-publication evidence

- **Within the paper:** the published sample ends in March 2017 and the working paper's in May 2014, so 2014-06 to 2017-03 is out of sample relative to the first draft; the Sharpe fell from "about one" (2015, eight variables) to 0.70 (2020, five variables, longer sample and more currencies). The two changes are confounded: the published combo without interest-rate variables had Sharpe 0.85 in the 2015 sample.
- **Independent replications:** S3 (33 currencies, published definition) reports the trend combo as a significant positive predictor of currency excess returns in panel regressions (coefficient 0.036, p < 0.01) and uses it as a benchmark; it does not report an isolated post-2017 Sharpe. S4 replicates the FX signal to 2019 for 27 countries as a comparison and extends it to bonds (below). S6 (non-peer-reviewed G10 implementation) reports a Sharpe of about 0.20 since publication and labels the strategy "faded since 2019"; its own 1990–2026 backtest has 2% volatility and a negative Sharpe, so its implementation is not comparable.
- **No peer-reviewed 2018–2026 evaluation was found.** The spec (§17.4) lists "what is the economic-momentum Sharpe?" as an open question and recommends rebuilding on OECD vintages and testing out of sample on 2018–2026. The spec's prior (§0.1) is to shrink a published Sharpe by 25–50%, which puts the expectation at 0.35–0.53 before costs for a stand-alone currency strategy.
- **Emerging markets:** the published sample includes emerging currencies (S3: 33 currencies), but no separate EM result is reported in the accessible texts.

### 2.7 Bonds

- The paper is a currency paper. It never applies the signal to bond returns.
- The only bond application found is S4, a master's thesis (not peer-reviewed): macro momentum in 27 government-bond markets 1989–2019, rank weights on the same indices. Its own abstract says the outperformance "is mainly limited to the inflation measure portfolio and currency-unhedged returns", and the economic reasoning (strong trends → tighter policy → higher yields) implies the **opposite sign** to the currency signal for a local-currency bond.
- Spec §0.3(a) requires at least one peer-reviewed, central-bank, BIS or IMF source for a modification. None exists for bonds, and none at all for the spread-over-Bund positions. **T02 therefore applies economic momentum to the 10 currencies only.** v1.0's 13 bond positions keep their carry/trend/value composite unchanged.

## 3. Ambiguities and how each is resolved (fixed now, before any data are examined)

| # | ambiguity | resolution for T02 |
|---|---|---|
| A1 | Two versions of the signal exist: 2015 (eight variables, two trend measures, 20 currencies) and 2020 (five variables, log changes only, 33 currencies). | The **published 2020 version**: five macro variables in two fundamental indices, log changes over 1–60 months. The interest-rate trends of the 2015 version overlap v1.0's carry signal, and the spec (§4.1) names only the macro variables. |
| A2 | The published inflation index averages CPI and PPI growth. No first-release PPI vintages exist for nine of the ten economies (the OECD revisions database has no PPI; ALFRED's OECD PPI vintages start in the 2010s and stop in 2024). | The inflation index uses **CPI only**, for every country, so the signal is homogeneous. This is a documented deviation from the paper; the spec's own definition (§4.1) also uses CPI only. PPI is not used even where vintages exist (euro area), to keep one definition. |
| A3 | How the index components are combined is stated only in replications (S3 footnote, S4 eqs 6–8), not in the accessible text of the paper. | Follow S3/S4 exactly: equal-weighted average of the components' monthly growth rates, chain-linked into an index; inverse unemployment enters as the growth of 1/U. |
| A4 | A country may lack one component (for example no retail-sales series) for part or all of the sample. | The index uses the components available that month (S4: "all available data is used at any point in time"). A component that is missing in a month is left out of that month's average; a component missing in both t and t−1 contributes nothing; a country with no component at all has no index that month. |
| A5 | Aggregation across the 120 sub-strategies: S2 weights sub-strategies by inverse trailing volatility of their returns; S4 uses equal weights. Either needs sub-strategy return histories, which would be a backtest. | Within v1.0's framework the signal must be one score per currency. The score is the **equal-weighted mean over the two indices and the 60 look-backs of the demeaned cross-sectional rank** of the trend (the paper's eq 4 without the scale factor a_t, which is common to all currencies in a month). v1.0 then z-scores it across the currency book like every other signal. Equal weighting follows S4 and avoids using returns in the signal. |
| A6 | Minimum data for a score. | A sub-signal (i, l) exists for a currency when its index has observations at t and t−l; its rank is taken over the currencies with that sub-signal, provided at least 3 have it. A currency's score exists when at least 12 of its 120 sub-signals exist. Otherwise the score is missing and v1.0's composite is, as in v1.0, the mean of the available signals. |
| A7 | Publication lag: the paper lags macro data three months and uses revised OECD data; the spec (§4.1, §13) asks for first-release vintages. | **Vintages replace the fixed lag.** At the decision date (end of month t) a country's index is built only from observations that had been published by the end of month t, taken from the vintage/edition in force on that date. For the OECD revisions database this is the edition dated month t (published during month t); for the ECB real-time database, observations with `VALID_FROM` on or before the last calendar day of month t. Where no vintage exists (fallback, §A8) the paper's fixed three-month lag applies to the revised series. |
| A8 | Some series have vintages only from a later date, or none. | Fallback: the latest available (revised) series, lagged three months as in the paper, spliced before the first vintage. Every such use is a known look-ahead risk and is listed in the data report and the pre-registration; the share of signal-months using the fallback is reported. |
| A9 | Seasonal adjustment and base years differ across sources and vintages. | Use the series as published in each vintage (seasonally adjusted IP, retail sales and unemployment where the source provides them; CPI not adjusted, as in the paper). Chain-linking of growth rates within a vintage makes base-year changes irrelevant; growth rates are never computed across two vintages. |
| A10 | Quarterly observations (some unemployment or retail series). | Carried forward to monthly within the vintage, as in the paper (S4). |
| A11 | Euro: the paper uses legacy currencies until 1998 and the euro after. v1.0 trades EUR once. | Euro-area aggregate series (changing composition, as published at the time), from the ECB real-time database, with the OECD euro-area editions as the cross-check. |
| A12 | Cross-section size: the paper averages 14 currencies; v1.0 has 10 (5 in the half-B holdout). | Ranks over whatever is available with at least 3 currencies, which is v1.0's z-score rule. |
| A13 | Currency excess return: the paper's is forward-implied. | v1.0's return definition (policy-rate-implied) stands; the integration rule is that nothing in v1.0 changes except the added signal. |
| A14 | The spec (§4.1) suggests testing economic momentum both as a carry replacement and as an orthogonalised addition. | The session's instruction fixes T02 as **one** pre-registered trial: a fourth equal-weight signal. Any other variant is a new trial with its own ledger row. |
| A15 | The spec's formula (§4.1: `v_{t−lag} − mean(v_{t−lag−60..t−lag−1})` on year-on-year rates) differs from the paper. | The paper's definition is used; the spec's formula is recorded here as a variant not tested. |
| A16 | Costs: the paper's turnover is 85% a month on a rank-weighted, volatility-scaled portfolio. | v1.0's cost model and no-trade band apply unchanged (integration rule); costs are reported at 1x and 2x. |

## 4. What this implies for the prior (spec §0.1, §4.1)

- Published Sharpe 0.70 for a 33-currency stand-alone strategy; shrunk by 25–50% for decay: 0.35–0.53.
- In v1.0 the signal is one of four equal-weight components of the currency book only, so the effect on the combined strategy is diluted; the spec's judgement (§17.1 #9) is ΔSR +0.05 to +0.15.
- The paper says the signal is collinear with carry (it subsumes the carry alpha). In v1.0 carry is the main earner; the pass rule's criterion (5), a positive alpha of the economic-momentum sleeve against the carry, trend and value sleeves, is the direct test of whether the signal adds anything beyond carry.
