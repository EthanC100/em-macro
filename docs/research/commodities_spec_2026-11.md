# Commodity Futures Sleeve and Commodity Forecasting: Implementation Specification for a Systematic Global Macro Programme

The commodity sleeve worth building is a small, cross-sectional, monthly-rebalanced portfolio of about 20 to 24 liquid futures, driven first by carry (roll yield) and second by basis-momentum, with value and smoothed hedging pressure as candidate add-ons; almost none of the "forecasting" methods in Section 4 (macro regressions, curve models, regime switching, machine learning, seasonality, option-implied signals) clears the bar of robust, post-publication, after-cost out-of-sample evidence, so they should be used for risk sizing or not at all. Expect a modest combined-portfolio gain (Sharpe from 0.65 to about 0.69–0.71 on realistic assumptions), not a transformation, and treat the first build as a data-feasibility test because free full-curve history is the binding constraint.

## TL;DR

- **Build carry first, basis-momentum second, and treat everything else as a hypothesis.** Commodity carry earned a Sharpe ratio of 0.60 in Koijen, Moskowitz, Pedersen and Vrugt (JFE 2018), against 0.08 for an equal-weight long portfolio; basis-momentum (Boons and Porras Prado, JF 2019) is the strongest later signal and its authors report it kept working out of sample through December 2025 except in the pandemic. Haircut both by about half for decay, costs and a small universe.
- **Forecasting methods mostly fail the evidence bar.** Gargano and Timmermann (IJF 2014) used Reuters/Jefferies-CRB spot indices from January 1947 to December 2010. Monthly out-of-sample R² with the return spread was 4.3% for industrials and 4.5% for metals, and ridge and subset models reached about 10%, 8% and 4–5% for industrials, metals and the broad index. They also report "many negative R² values due to parameter estimation error" and much stronger predictability in recessions. Harvey, Hoyle, Korgaonkar, Rattray, Sargaison and Van Hemert (Man AHL, JPM 2018) find that for commodities "the impact of volatility targeting on the Sharpe ratio is negligible", although it "reduces the likelihood of extreme returns". Machine-learning studies are mixed and often show LASSO beating trees and neural nets. Use these for sizing and as pre-registered trials, not as alpha.
- **Data is the critical path.** Nasdaq Data Link's CHRIS continuous-futures database is deprecated, Yahoo returns nothing for expired contract months, and CME's free settlement page has no archive. The realistic route to full-curve history is a low-cost vendor, plus free CFTC, EIA and USDA data. The options are Norgate's Futures Package (US$270 for 12 months or US$148.50 for 6, about 100 markets from 11 exchanges, history back to around 1980 or the first trading day), Pinnacle Deep History (US$149 one-off), or Databento's US$125 free credit for CME data from June 2010. Run the data-feasibility build before any signal research.

## 1. The commodity universe

### 1.1 Recommended universe

Sourced facts: academic studies of commodity factors use roughly 20–35 contracts (Gorton, Hayashi and Rouwenhorst use 31 commodities, 1969–2006; Hurst, Ooi and Pedersen use 29 commodities in their 1880–2016 trend study; Levine et al. use 35 commodities, 1877–2015). Judgement: for a US$100,000 account, contract size, not theory, sets the universe. The table lists a core set of 22 markets; the "trade via" column gives the smallest liquid contract. Contract sizes are from exchange specifications as commonly published and must be re-verified against current CME/ICE specification pages before coding.

| Sector | Market | Exchange | Full contract | Smaller contract (verify spec) | Carry curve notes |
|---|---|---|---|---|---|
| Energy | WTI crude | NYMEX | CL, 1,000 bbl | MCL micro, 100 bbl; QM e-mini 500 bbl | Monthly listings; clean F1/F2 |
| Energy | Brent crude | ICE Europe | B, 1,000 bbl | none liquid for retail | Monthly; cash-settled |
| Energy | RBOB gasoline | NYMEX | RB, 42,000 gal | none liquid | Strong seasonal curve (summer grade) |
| Energy | Heating oil / ULSD | NYMEX | HO, 42,000 gal | none liquid | Seasonal (winter) |
| Energy | Natural gas | NYMEX | NG, 10,000 MMBtu | MNG micro 1,000 MMBtu; QG e-mini | Very strong seasonal curve |
| Energy | Gasoil | ICE Europe | G, 100 t | none | Seasonal |
| Industrial metals | Copper | COMEX | HG, 25,000 lb | MHG micro 2,500 lb | Monthly, mildly seasonal |
| Industrial metals | Aluminium, zinc, nickel, lead | LME | 25 t (Ni 6 t) | COMEX aluminium is thin | Daily prompt dates; not standard monthly futures |
| Precious | Gold | COMEX | GC, 100 oz | MGC micro 10 oz | Carry ≈ financing; near-zero information |
| Precious | Silver | COMEX | SI, 5,000 oz | SIL 1,000 oz | Same |
| Precious | Platinum, palladium | NYMEX | PL 50 oz, PA 100 oz | none | Thin deferreds |
| Grains | Corn, soybeans, wheat (SRW), KC wheat | CBOT | 5,000 bu | XC/XK/XW mini 1,000 bu; micro grains | Crop-year gaps (Mar/May/Jul/Sep/Dec for corn) |
| Grains | Soybean meal, soybean oil | CBOT | 100 short t / 60,000 lb | none | Crop-year structure |
| Softs | Sugar No.11, coffee C, cocoa, cotton | ICE US | 112,000 lb / 37,500 lb / 10 t / 50,000 lb | none | Irregular delivery months |
| Livestock | Live cattle, feeder cattle, lean hogs | CME | 40,000 / 50,000 / 40,000 lb | none | Non-storable; strongly seasonal curves |

Judgement on breadth: diversification gains in cross-sectional commodity strategies come from low pairwise correlations between sectors, not from adding more contracts within a sector (WTI, Brent, heating oil and gasoil are close to one bet). A sleeve of 18–24 markets spanning 5 sectors captures most of the available diversification; below about 12 markets, quintile/tercile sorts become noisy and a single market can dominate a leg. If account size forces a smaller set, keep sector balance (at least 2 energy, 2 metals, 3 grains, 2 softs, 1 livestock) rather than dropping whole sectors.

### 1.2 Sizing feasibility at US$100,000 and 10% target volatility

With inverse-volatility sizing and a sleeve risk budget of, say, 30% of portfolio risk (Section 6), each of 20 markets receives a tiny risk allocation. Contract notional risk per market = annual vol × price × multiplier. Example (illustrative): one full CL contract at US$80 and 35% vol carries about US$28,000 of annual risk, far above a per-market budget of about US$1,000–2,000. Only micro and mini contracts (MCL ≈ US$2,800 annual risk, MGC, MHG, SIL, mini grains) are sizable at this account level; full-size softs, livestock and LME metals cannot be traded at target weight. Consequences for the specification:

- The paper account must round to integer contracts and record rounding error as a tracking cost; a pre-registered rule should drop a market if rounding error exceeds 50% of its target risk.
- Research should be done on the full theoretical universe (to measure the signal) and execution on the tradeable subset (to measure realised performance); both results are reported.

(Programme note, Nov 2026: paper capital is raised to US$10,000,000 from the 3 Dec 2026 rebalance, which makes full-size contracts sizable; see docs/config_changes.md.)

### 1.3 Exchange and trading-hour differences

CME Globex energy/metals trade nearly 23 hours (Sunday–Friday); CBOT grains have a shorter day session with a mid-session break; ICE US softs trade a short US day; LME metals trade on a daily prompt-date structure with a 3-month benchmark and official prices set in the ring. Settlement times differ (e.g., COMEX gold settles mid-day New York, grains early afternoon Chicago). Rule: compute all signals from official settlement prices on the same calendar date and never mix a London close with a Chicago close in one return; for rebalancing on the 3rd, use settlements of the prior business day.

## 2. Continuous series and rolling

### 2.1 Definitions (copyable)

```
F[i,T,t]   = settlement price at date t of commodity i, contract expiring T
F1[i,t]    = nearest eligible contract (after roll rule), F2 = next listed contract
r_ex[i,t]  = F[i,T,t] / F[i,T,t-1] - 1         # excess return: same contract both days
r_tr[i,t]  = r_ex[i,t] + rf[t-1] * dt           # total return on fully collateralised position
r_spot     = S[t]/S[t-1] - 1                    # spot return (often unobservable; F1 proxy)
roll_yield = r_ex - r_spot_proxy                # not a separate cash flow; a decomposition
```

The strategy already reports excess returns over a funding rate, so the commodity sleeve should be built on r_ex (the futures return is already an excess return because a futures position requires no capital beyond margin). Do not add T-bill interest to commodity returns, and do not subtract it.

### 2.2 Roll schedules

Sourced fact: the Bloomberg Commodity Index rolls from the lead to the next designated contract over the 6th to 10th business days of each month, at 20% per day, using a fixed contract calendar per commodity. The S&P GSCI rolls over the 5th to 9th business days (also 20% per day). Gorton, Hayashi and Rouwenhorst construct monthly excess returns by holding, at each month-end, the nearest contract that will not expire during the next month.

Recommended rule for this programme (monthly rebalance on the 3rd):

```
def choose_contract(i, t, calendar):
    # eligible = listed contracts in the commodity's designated roll calendar
    # (e.g., corn: H,K,N,U,Z; cattle: G,J,M,Q,V,Z; CL: all months)
    for T in sorted(eligible_contracts(i, calendar)):
        if first_notice_or_last_trade(T) > t + 35 calendar days:  # survive the holding month
            return T
```

Hold the chosen contract until the next rebalance. Use a 35-day buffer so the position never enters first-notice periods (physically delivered markets: CL, NG, grains, metals) and never holds a contract in its thin expiry week. Liquidity-based rolling (roll when open interest of F2 exceeds F1) is an acceptable alternative, but it uses volume/OI data that must itself be available at t; pre-register one rule and do not switch.

### 2.3 Constructing excess-return series without look-ahead

Never use back-adjusted continuous prices for signals that depend on price levels (value) or on the curve (carry); back-adjustment rewrites history. Build the return index by chaining same-contract daily returns:

```
idx[i,0] = 1
for t in days:
    T = held_contract[i,t-1]          # decided at the previous rebalance with info at that date
    idx[i,t] = idx[i,t-1] * (F[i,T,t] / F[i,T,t-1])
```

Look-ahead traps to test explicitly: (a) choosing the roll date with volume data from after the roll; (b) using contract calendars that include months later delisted; (c) using LME 3-month "rolling" series as if they were tradable futures; (d) using a settlement price that was revised the next morning (CME publishes preliminary and final bulletins).

### 2.4 Contract-month gaps and seasonal curves

For commodities with irregular listing (corn H,K,N,U,Z; hogs G,J,K,M,N,Q,V,Z), F1 and F2 may be 1 to 4 months apart. Always annualise:

```
carry_ann[i,t] = (ln F1 - ln F2) * 365 / (D2 - D1)     # D = days to expiry
```

This is the Gorton–Hayashi–Rouwenhorst basis definition in log form; their paper uses (F1/F2 - 1) * 365/(D2 - D1).

## 3. Signals with published evidence (ranked)

### 3.1 Evidence table

| Rank | Signal | Source | Sample | IS/OOS | Published Sharpe (long-short) | Effect size | Post-publication |
|---|---|---|---|---|---|---|---|
| 1 | Carry (F1 vs F2) | Koijen, Moskowitz, Pedersen, Vrugt (JFE 2018) | Commodities 1980s–2012 | IS (carry concept extended from FX) | 0.60 (EW passive 0.08); carry2–13 0.58 | Mean 11.2% p.a., vol 18.8% | AQR "Century of Factor Premia" (Ilmanen et al. 2021) finds carry robust out of sample across assets |
| 1 | Basis / backwardation | Erb and Harvey (2006); Gorton and Rouwenhorst (2006); Gorton, Hayashi, Rouwenhorst (RoF 2013) | 1959–2004; 1969–2006 | IS | High-basis minus low-basis significant | Basis is declining, convex in inventories | Geczy and Samonov: basis exists in 1877–1959 pre-sample but smaller; early max drawdown −83% |
| 2 | Basis-momentum | Boons and Porras Prado (JF 2019) | Commodities ~1959–2014 | IS; author-maintained OOS to Dec 2025 | Outperforms basis and momentum; Jiang and Liu report factor Sharpe 0.43 from 1985 | Robust to controls for basis and momentum | Author-reported: large returns through Dec 2025 except the pandemic (not independently verified) |
| 3 | Cross-sectional momentum (12m) | Erb and Harvey (2006); Miffre and Rallis (JBF 2007); Asness, Moskowitz, Pedersen (JF 2013) | 1979–2004 (Miffre–Rallis) | IS | Positive, significant | Bakshi, Gao, Rossi: momentum factor mean ~16% p.a., corr with carry 0.27 | Pre-sample (1877–1959) weaker (Geczy–Samonov) |
| 3 | Time-series momentum | Moskowitz, Ooi, Pedersen (JFE 2012); Hurst, Ooi, Pedersen (JPM 2017) | 1965–2009; 1880–2016 | IS + long pre-sample | Positive in every decade since 1880 (diversified, all asset classes) | 8 of 10 largest 60/40 crises positive | Weaker 2009–2019 for the industry; your own TSMOM test failed |
| 4 | Value (5-year reversal) | Asness, Moskowitz, Pedersen (JF 2013) | 1972–2011 | IS | Commodity value alone weak; strong negative corr with momentum | Long-term reversal also in Levine et al. 1877–2015 | Geczy–Samonov: value strongest in 1877–1959 |
| 5 | Hedging pressure (CFTC) | de Roon, Nijman, Veld (JF 2000); Basu and Miffre (JBF 2013); Kang, Rouwenhorst, Tang (JF 2020) | 1986–2016 approx | IS | Basu–Miffre long-short significant | KRT: long-run hedging component and short-run speculator flows have opposite signs | Gorton et al. reject hedging pressure as a determinant; Maréchal (JFM 2023) re-examines KRT |
| 6 | Skewness | Fernandez-Perez, Frijns, Fuertes, Miffre (JBF 2018) | ~1987–2014 | IS | 0.78 (8.01% p.a., NW t = 3.83) | Low-skew long, high-skew short | No independent post-publication record found |
| 6 | Inventories | Gorton, Hayashi, Rouwenhorst (2013) | 1969–2006 | IS | Low-inventory portfolios earn more | Mostly captured by basis and momentum | Price signals subsume most of it |

### 3.2 Carry

Formula (KMPV define carry as the futures return if spot stays unchanged; for commodities, approximated from the curve):

```
carry[i,t] = (F1[i,t] - F2[i,t]) / F2[i,t] * 12 / months_between(F1,F2)   # KMPV-style
carry_log[i,t] = (ln F1 - ln F2) * 365 / (D2 - D1)                         # preferred
```

Seasonality adjustment (essential for NG, RBOB, HO, livestock, grains): a raw F1/F2 spread in natural gas mostly reflects the winter premium, not scarcity. Two pre-registrable options:

```
# Option A: 12-month carry (KMPV "carry1-12"): compare F1 with the contract ~12 months later
carry12[i,t] = (ln F1 - ln F13) * 365 / (D13 - D1)
# Option B: de-seasonalise: subtract the trailing 5-year average carry for the same calendar month
carry_ds[i,t] = carry_log[i,t] - mean(carry_log[i, same_month, t-5y : t-1y])
```

KMPV report carry1–12 Sharpe of about 0.65 for commodities (NBER version), comparable to current carry, so 12-month carry costs little and removes seasonal noise. Requirement: deferred contracts at least 12 months out, which is the hardest data item (Section 9).

Portfolio construction (matches the existing programme):

```
s[i,t]   = rank(carry_ds[i,t]) over i, demeaned and scaled so sum|w| = 2
w_raw    = s[i,t] / sigma_hat[i,t]            # inverse vol
w_sleeve = w_raw * (target_sleeve_vol / predicted_vol(w_raw, Sigma_hat))
```

Gold and silver have carry ≈ −(financing rate − lease rate), which contains almost no cross-sectional information; exclude precious metals from the carry ranking (Section 5).

Expected effect after haircut (judgement): published 0.60 → plan for 0.25–0.35 net, given post-publication decay of the order McLean and Pontiff document for equities (−58% post-publication on average), costs, and a 20-market universe.

### 3.3 Trend and momentum

Formulas:

```
xs_mom[i,t]   = ln(idx[i,t-1m]) - ln(idx[i,t-12m])          # 12-1 month, cross-sectional rank
tsmom[i,t]    = sign(ln idx[i,t] - ln idx[i,t-12m]) * (sigma_target / sigma_hat[i,t])   # MOP 2012
```

Evidence: Miffre and Rallis (2007) found profitable momentum strategies on 31 commodity futures over 1979–2004; MOP (2012) use 58 instruments 1965–2009 and a 12-month lookback; Hurst, Ooi and Pedersen extend to 1880–2016 and report positive returns in every decade. Programme-specific fact: cross-sectional trend lost money in your FX/bond universe in both 2005–2019 and 2020–2026, and a pre-registered TSMOM sleeve failed. Judgement: commodity momentum is a separate hypothesis (Bakshi, Gao and Rossi show a momentum factor is needed alongside carry in commodities, with carry–momentum correlation 0.27), but because your prior trend tests failed and TSMOM correlated with carry in carry's worst months, do not add commodity trend as a standalone sleeve. Test it only as a component inside basis-momentum (which differences out the common price trend) and as a pre-registered secondary trial.

### 3.4 Basis-momentum and slope changes

```
bm[i,t] = sum_{k=t-11}^{t} r_ex(F1)[i,k] - sum_{k=t-11}^{t} r_ex(F2)[i,k]
```

where r_ex(F1) is the monthly return on the first-nearby and r_ex(F2) the return on the second-nearby (each held as a separate rolled position). Boons and Porras Prado show this strongly outperforms basis and momentum in both the time series and the cross-section, is priced, and survives controls for basis, momentum and volatility; they interpret it as compensation for imbalances when speculators' and intermediaries' market-clearing capacity is impaired. A 2025 AEA paper on "relative basis" reports correlation of 0.20 between relative basis and basis-momentum, and the factor-structure literature (e.g., a 2026 Journal of Banking & Finance paper on commodity risk premia) finds basis-momentum among four latent priced factors. Why it matters here: it is a curve-shape signal, not a level trend, so it should be much less correlated with your FX/bond carry drawdowns than TSMOM. Data requirement: two parallel rolled series (F1 and F2), which is the same data as carry.

### 3.5 Value

```
value[i,t] = ln( mean(F1_price[i, t-66m : t-54m]) ) - ln( F1_price[i,t] )   # AMP 2013: 5-year reversal
```

Use spot-proxy prices (unadjusted front prices), not the excess-return index, because the economic idea is price-level mean reversion. Evidence: AMP (2013) find commodity value weak alone but valuable because of its −0.4 to −0.6 correlation with momentum; Levine et al. (1877–2015) use the negative 48-month return lagged 12 months. Judgement: value adds diversification to momentum, but because you are not running commodity momentum, its marginal value is lower; rank 4.

### 3.6 Hedging pressure and positioning

```
HP[i,w]   = (CommShort - CommLong) / (CommShort + CommLong)     # commercial net short share
SHP[i,t]  = mean(HP[i, w-51 : w])                                # KRT: 52-week smoothed
dSpec[i,t]= NonCommNet[i,w] - NonCommNet[i,w-1]   # short-run component (opposite sign per KRT)
```

Timing: COT positions are as of Tuesday and published Friday 15:30 ET; on the 3rd of the month, use only reports published by the 2nd. Evidence: de Roon, Nijman and Veld (2000) and Basu and Miffre (2013) find hedging pressure predicts returns; Kang, Rouwenhorst and Tang (2020) show short-term position changes reflect speculators' liquidity demand and long-term variation reflects hedging demand, with opposite-signed effects on expected returns; but Gorton, Hayashi and Rouwenhorst reject the Keynesian hedging-pressure hypothesis as an important determinant. Evidence status: mixed. Rank 5; the only free signal that is not price-derived, so a candidate for orthogonal information.

### 3.7 Inventories and fundamentals

Gorton, Hayashi and Rouwenhorst (31 commodities, 1969–2006) show the basis is a declining, non-linear function of inventories and that low-inventory portfolios earn higher returns, but price-based signals (basis, prior returns, spot volatility) already reflect the inventory state. Judgement: do not build a separate inventory signal; inventories are useful mainly to validate that the carry signal behaves as the theory of storage predicts (e.g., EIA crude stocks vs CL carry).

### 3.8 Skewness and other factors

```
skew[i,t] = sample skewness of daily r_ex over the past 12 months; long lowest quintile, short highest
```

Fernandez-Perez et al. (2018) report 8.01% a year, Sharpe 0.78 and NW t = 3.83 for the long-short skewness portfolio. Status: single-study, no independent post-publication confirmation found; low-skew commodities tend to be backwardated, so overlap with carry is likely. Do not build; list as an open question.

### 3.9 Correlation and incremental information

Sourced: Bakshi, Gao and Rossi find average, carry and momentum factors are jointly needed to price the commodity cross-section (carry–momentum correlation 0.27); Boons and Porras Prado show basis-momentum survives basis and momentum controls; relative basis has correlation 0.20 with basis-momentum. Judgement (expected correlation matrix to verify in Build 1):

| | Carry | Basis-mom | XS momentum | Value | SHP | Skew |
|---|---|---|---|---|---|---|
| Carry | 1 | 0.2–0.4 | 0.2–0.35 | −0.1 to −0.3 | 0.1–0.3 | 0.3–0.5 |
| Basis-mom | | 1 | 0.3–0.5 | −0.2 | ~0 | ~0.2 |
| XS momentum | | | 1 | −0.4 to −0.6 | ~0.1 | ~0.3 |

## 4. Quantitative and statistical forecasting methods

### 4.1 Evaluation standard (applies to every method)

```
R2_OS = 1 - sum_t (r[t] - rhat_model[t])^2 / sum_t (r[t] - rbar_hist[t])^2       # Campbell-Thompson 2008
# Clark-West (2007) adjusted MSPE for nested models:
f[t]  = (r - rbar)^2 - [ (r - rhat)^2 - (rbar - rhat)^2 ];   t-stat of mean(f) with HAC SE; one-sided
# Diebold-Mariano (1995) for non-nested: d[t] = L(e1[t]) - L(e2[t]); DM = mean(d)/HAC_se(d)
# Economic value: mean-variance investor, gamma = 3 (Campbell-Thompson; Rapach-Strauss-Zhou)
w[t] = (1/gamma) * rhat[t] / sigma2_hat[t],  clipped to [-1.5, 1.5]
CER  = mean(Rp) - 0.5*gamma*var(Rp);   gain = CER_model - CER_benchmark (annualised, after costs)
```

Benchmark for commodity futures: the prevailing historical mean of excess returns (close to zero for many markets) and, for cross-sectional models, the carry-only portfolio. A method "passes" only if R2_OS > 0 with Clark-West p < 0.05 AND the CER or Sharpe gain is positive after costs in a holdout not used for design.

### 4.2 Evidence table and ranking

| Rank | Method | Key sources | Sample | OOS result | Economic value after costs | Verdict |
|---|---|---|---|---|---|---|
| 1 | Volatility forecasting (EWMA/HAR) for sizing | Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert (JPM 2018) | 60+ assets, daily data from as early as 1926 | Vol is persistent and forecastable | Sharpe effect negligible for commodities (US equity Sharpe rose from 0.40 to 0.48–0.51); fewer extreme returns | Use for sizing only |
| 2 | Forecast combination of characteristics (equal-weight) | Rapach, Strauss, Zhou (RFS 2010) for equities; commodity studies (e.g., a 2025 cross-sectional vs time-series comparison on 37 commodities) | Varies | Combination yields positive cross-sectional R2_OS in recent studies | Reported utility gains; not independently replicated | Use equal-weight composite of signals; no estimated weights |
| 3 | Predictive regressions on macro/financial variables | Gargano and Timmermann (IJF 2014) | CRB spot indices 1947m1–2010m12 | Monthly R2_OS 4.3% (industrials) and 4.5% (metals) with the return spread; ridge/subset about 10%/8%/4–5% (industrials/metals/broad); many negative R2 from estimation error; much stronger in recessions | Not shown after costs for futures | Do not trade; research only |
| 4 | Shrinkage (ridge, LASSO, elastic net) | Gargano–Timmermann ridge; Han and Kong (LASSO lead-lag) | Various | LASSO lead-lag forecasts produce OOS gains; trees and neural nets did worse than LASSO | Reported, single study | Open question |
| 5 | Machine learning (RF, GBM, NN) | Wang and Zhang (JFM 2024, 22 commodities): LightGBM best; Chinese commodity XGBoost study 2013–2021 | Short samples | Lower OOS errors for most contracts in-paper | Rarely net of costs; short OOS windows | Do not trade |
| 6 | Term-structure models (Schwartz–Smith, Nelson–Siegel, PCA, Kalman) | Schwartz (1997); Schwartz and Smith (2000); Gibson and Schwartz (1990) | Pricing/hedging studies | Designed for pricing, not return prediction; curve slope ≈ carry | Nothing beyond carry demonstrated | Use only to interpolate missing maturities |
| 7 | Regime models (Markov switching, contango regimes) | Crespo Cuaresma et al. (JoF 2024) regime-dependent commodity dynamics; various | Various | Mixed; regime identification ex post | Not shown | Do not trade |
| 8 | Relative value (crack, crush, gold–silver, Brent–WTI) | Various; mostly practitioner | Various | Spreads mean-revert but structural breaks (e.g., WTI export ban 2015) | Thin after costs at retail scale | Do not trade |
| 9 | Seasonality in prices | Various | Various | Curves already price predictable seasonality | Not shown | Do not trade; use only to de-seasonalise carry |
| 10 | Option-implied (IV, skew, risk reversals) | Aka et al. (JFM 2025) on delta-hedged option returns | 7 commodities | Option-return predictability, not futures direction | Requires option data you do not have | Do not trade |
| 11 | Fundamental nowcasting (EIA, USDA, freight) | GHR 2013 (inventories) | 1969–2006 | Releases are priced quickly; price signals subsume inventories | Not shown | Use as diagnostics |

### 4.3 Method specifications

**Volatility forecasting (adopt for sizing).**

```
EWMA:  sigma2[t] = lam*sigma2[t-1] + (1-lam)*r[t-1]^2,  lam = 0.94 (RiskMetrics daily)
HAR:   RV_d[t+1] = b0 + b1*RV_d[t] + b2*RV_w[t] + b3*RV_m[t] + e     # Corsi 2009; RV_w = 5-day mean, RV_m = 22-day mean
blend: sigma_hat = 0.5*sigma_EWMA_short(lam=0.94) + 0.5*sigma_long(1-year)   # reduces turnover
```

Harvey et al. (2018) cover more than 60 assets with daily data from as early as 1926. They conclude that "for bonds, currencies, and commodities the impact of volatility targeting on the Sharpe ratio is negligible", although "it reduces the likelihood of extreme returns, across all asset classes". That is the reason to use it: risk control, not alpha. Pre-registered test: compare realised sleeve volatility error |realised − 10%| and the 1% tail loss under EWMA vs HAR; adopt HAR only if it reduces tail loss with no Sharpe deterioration.

**Predictive regressions and shrinkage (research only).**

```
r[i,t+1] = a_i + b' x[t] + e,  x = {carry_ds, bm, SHP, dDXY, d(10y TIPS), IP growth, ISM PMI, BDI change, VIX}
# recursive estimation, expanding window from 10 years; ridge lambda chosen by time-series CV inside the training window only
```

Gargano and Timmermann used Reuters/Jefferies-CRB spot indices from January 1947 to December 2010. With the return spread, monthly out-of-sample R² was 4.3% for industrials and 4.5% for metals, and ridge and subset models reached about 10% (industrials), 8% (metals) and 4–5% (broad index). They also found "many negative R² values due to parameter estimation error" and "significantly stronger predictability during recessions". These are spot indices, not futures excess returns, so the result does not transfer directly to a tradeable strategy.

**Term-structure models.** Schwartz–Smith two-factor log spot = chi (short-term mean-reverting) + xi (long-run random walk); estimated by Kalman filter on log futures across maturities:

```
ln F(t,T) = exp(-kappa*(T-t))*chi_t + xi_t + A(T-t)
state: chi_{t+1} = exp(-kappa*dt)*chi_t + eta1 ; xi_{t+1} = xi_t + mu_xi*dt + eta2
```

The short-term factor is essentially the de-seasonalised slope, which is carry. No published study found here shows curve-factor models forecasting futures returns beyond carry; use the model only to interpolate a constant-maturity (e.g., 12-month) point when listed months are sparse.

**Relative value.** Half-life of an Ornstein–Uhlenbeck spread:

```
dS[t] = a + b*S[t-1] + e   ->  half_life = -ln(2)/ln(1+b)
```

Trade only if a cointegration test (Engle–Granger/Johansen) passes on a training window and half-life < 3 months; at a US$100,000 account, legs must be micro contracts (e.g., MGC/SIL for gold–silver), and exchange spread margins are generally lower. Judgement: not recommended; edge is thin and regime breaks are frequent.

**Machine learning and validation.** If any ML trial is run, it must use: combinatorial purged cross-validation with embargo ≥ the label horizon (López de Prado 2018); the probability of backtest overfitting (Bailey, Borwein, López de Prado and Zhu 2017) < 0.2; and the deflated Sharpe ratio (Bailey and López de Prado 2014) with the full count of trials. With about 20 commodities × 240 months of usable data (≈ 4,800 noisy observations), monthly ML has very little room; Han and Kong's finding that trees and neural nets underperformed LASSO is the expected outcome.

```
DSR = Phi( (SR_hat - SR0) * sqrt(T-1) / sqrt(1 - g3*SR_hat + (g4-1)/4*SR_hat^2) )
SR0 = sqrt(V[SR_trials]) * ( (1-euler_gamma)*Phi^-1(1-1/N) + euler_gamma*Phi^-1(1-1/(N*e)) )
```

**Ensemble design.** Combine standardised signal ranks with fixed equal weights (or inverse of signal tracking-error) decided before testing; do not estimate weights by in-sample regression. Rationale: Rapach, Strauss and Zhou show equal-weighted combination beats individual predictors and estimated combinations out of sample in equities; the estimation-error argument is stronger with 20 commodities.

```
z_k[i,t] = rank-standardised signal k (cross-section mean 0, sd 1), winsorised at ±2
composite[i,t] = sum_k z_k[i,t] / K
```

## 5. Gold

Sourced facts: Erb and Harvey (The Golden Dilemma, 2013) report a −0.82 correlation between 10-year TIPS real yields and the real gold price over roughly 1997–2012, but warn it may be spurious and that it falls to −0.31 in another sample; they also find inflation did not predict gold returns and that a high real gold price has historically preceded low subsequent real returns. Programme facts: your model gives about −4% per +1 point of real yield and −0.85% per +1% dollar, with an unexplained drift that tripled since 2022 (likely central-bank buying), and event trades had no edge.

Specification:

1. **Exclude gold and silver from the carry and basis-momentum rankings.** Their curves price financing and lease rates, carrying no scarcity information.
2. **Do not run a directional gold forecast.** Your own real-yield/dollar model is contemporaneous (it explains, it does not predict), and none of the Section 4 methods has robust out-of-sample evidence for gold direction. The Erb–Harvey valuation signal (real price vs history) is a 10-year-horizon idea with very few independent observations.
3. **If gold is held, hold it as a separate macro/diversifier position** with a fixed small risk budget (e.g., 5% of portfolio risk, long-only, MGC micro), justified by crisis diversification, and pre-register that it is not an alpha claim. Evaluate it only on its contribution to drawdowns in carry's worst months.

## 6. Integration into the multi-asset fund

### 6.1 Expected correlations (judgement, to be measured)

KMPV report low correlations between carry strategies across asset classes, which is why their diversified carry factor reached Sharpe 1.1–1.2 versus about 0.7–0.8 for single asset classes. Judgement on crisis behaviour: in 2008 long-only commodities fell with equities, but long-short carry was hedged in direction; 2014–15 oil collapse: contango deepened, so carry shorts in energy profited; 2020: WTI went negative, carry was short front crude in super-contango; 2022: backwardation across energy, carry long energy profited while bonds fell. Expected correlation of a long-short commodity carry/basis-momentum sleeve with FX carry 0.0–0.2, with bond carry −0.1–0.1, with S&P 500 0.0–0.15. These are to be measured in Build 1, not assumed.

### 6.2 Risk budget and combined Sharpe

For two sleeves with Sharpe S1, S2 and correlation rho, the maximum Sharpe of an optimal combination is:

```
S_comb^2 = (S1^2 + S2^2 - 2*rho*S1*S2) / (1 - rho^2)
# adding sleeve 2 helps only if S2 > rho * S1
# optimal risk weights (proportional): w2/w1 = (S2 - rho*S1) / (S1 - rho*S2)
```

Worked example: S1 = 0.65 (frozen baseline), S2 = 0.30 (haircut commodity sleeve), rho = 0.1 → S_comb = sqrt(0.4735/0.99) = 0.69; with S2 = 0.40 and rho = 0.2 → 0.71. Optimal risk share for S2 = 0.30, rho = 0.1 is about 31%. Recommendation: start with a 25% risk budget (sleeve vol ≈ 2.5% of the 10% target when uncorrelated) and do not raise it until 24 months of live data.

Covariance-aware sizing across sleeves:

```
Sigma = shrink(sample_cov(daily sleeve returns, 1y half-life), Ledoit-Wolf)
w_sleeves = solve min w' Sigma w s.t. risk contributions = budgets (equal-risk-contribution with budgets b)
scale total to 10% vol; enforce 6x gross leverage cap; apply 25% no-trade band per instrument
```

## 7. Risk

| Risk | Documented case | Control with evidence or logic |
|---|---|---|
| Negative prices / expiry squeeze | WTI May 2020 contract settled −US$37.63 on 20 April 2020 | 35-day roll buffer; never hold a contract into its last 10 trading days; model must accept negative prices (use arithmetic returns on notional, not log) |
| Short squeeze / exchange intervention | LME nickel, 8 March 2022: price more than doubled to US$101,365/t intraday; LME suspended trading at 08:15 and cancelled trades from midnight to 08:15. In its November 2022 High Court filing the LME said that had the trades stood, the market "would have faced a margin call of $19.75-billion, ten times higher than the previous record level"; its Independent Review says members actually paid nearly US$16bn in margin calls over the episode. The High Court later upheld the LME | Cap any single market at 10% of sleeve risk; exclude LME nickel; stress test with a 3× daily vol shock in the largest short |
| Limit moves | Grains and livestock have daily price limits | Model inability to exit for 2 days in stress tests |
| Contango/backwardation regimes | Carry signal persistent; drawdowns long (Geczy–Samonov basis −83% early sample) | Pre-registered max-drawdown stop on the sleeve (e.g., halve at −15% sleeve drawdown), tested historically |
| Position limits | CFTC federal spot-month limits | Irrelevant at this size |

## 8. Costs and execution

Judgement (calibrate to broker statements): commissions plus fees about US$1–2.5 per micro contract per side and US$2–4 per full contract; slippage one tick per side for liquid energy/metals/grains, two ticks for softs and livestock. Roll costs: each roll is two trades (or one calendar-spread order, usually at a tighter quoted spread). Margin: CME publishes performance-bond requirements per contract; micro contracts require about one-tenth of the full contract. The paper account should hold margin in cash at the funding rate and track it, without adding it to returns.

Rule: replicate the programme's conservative-cost approach: assume 2× estimated costs in research and report the break-even cost multiple; reject any commodity signal with break-even below 2×.

## 9. Data

| Source | What | Cost | History | Cloud reachability / issues |
|---|---|---|---|---|
| Nasdaq Data Link CHRIS (Wiki continuous futures) | Continuous front/deferred series | Was free | To ~2021 | Deprecated; returns HTTP 410; Nasdaq says no replacement feed |
| Yahoo via yfinance | CL=F etc. continuous front; explicit months (e.g., CLZ26.NYM) | Free | Live contracts only | Expired contracts return no data, so no historical curve; useful only to collect forward-going curves |
| CME daily settlements page | All listed months: OHLC, settle, volume, OI | Free | Latest trade dates only, no archive | Must scrape daily; DataMine history is paid with no public price list |
| Databento (CME Globex MDP 3.0) | Every CME/CBOT/NYMEX/COMEX contract, daily OHLCV | US$125 free credit; usage-based per GB | From 6 June 2010 | API; best low-cost route for full CME curves |
| Norgate Data Futures | ~100 markets from 11 exchanges, individual contracts incl. expired, close = settlement | US$270 for 12 months (US$148.50 for 6) | ~1980 or first trading day | Windows desktop updater plus Python package; no hosted REST API |
| Pinnacle Data | CLC continuous US$99; Deep History individual contracts US$149 | One-off plus ~US$20/month updates | Some to 1969 | File download; no linking software |
| CSI Data (Unfair Advantage) | Individual contracts, 110+ exchanges | License plus subscription (old price list; verify) | Some to 1940s | Desktop software |
| Barchart | Expired contracts by symbol | Free 1 download/day; Premier ~US$25/month | Daily from 2000 | Download caps make full-curve builds slow; OnDemand API quoted |
| CFTC COT | Legacy, disaggregated, TFF | Free | Legacy from Jan 1986; disaggregated from June 2006 | Annual zip files plus Socrata API at publicreporting.cftc.gov; untokened, rate-limited |
| EIA API v2 | Weekly petroleum and natural-gas storage | Free key | Weekly crude stocks from 1980s | 5,000 rows per call; values returned as strings |
| USDA NASS Quick Stats / FAS PSD | Crop progress, condition, stocks; world balances | Free key | Decades | 50,000-record limit per NASS query |
| LME | Prices, stocks | Free for current year only | Paid history | Westmetall is an unofficial mirror |
| FRED | Real yields, dollar index, IP, rates | Free | Decades | Reliable API |
| AQR data library | Commodity factor and portfolio returns (Commodities for the Long Run to 1877; Century of Factor Premia) | Free | To 1877 | Factor returns only, not contracts; use as a benchmark to validate your build |

Recommended data stack: Norgate (or Pinnacle Deep History) for 1980–present individual contracts; Databento as a cross-check from 2010; a daily scraper of CME settlements and a yfinance logger for forward-going live data; CFTC, EIA, USDA and FRED via their APIs; AQR factor returns as the external benchmark. Manual investing.com exports should be limited to spot checks.

(Programme decision, Nov 2026: Pinnacle Deep History for history plus Databento for recent and ongoing data; Norgate not used because it requires Windows desktop software.)

## 10. What leading firms do (fact vs legend)

| Firm | Documented fact | Legend or unverifiable |
|---|---|---|
| AQR | Publishes commodity carry, momentum and value research (KMPV 2018; AMP 2013; Levine et al. 2018; Hurst, Ooi, Pedersen 2017) and free datasets; was among the claimants against the LME over cancelled nickel trades | Exact live weights and signal definitions |
| Man AHL | Published "The Impact of Volatility Targeting" (Harvey et al. 2018) and trend crisis-alpha research (Hamill, Rattray, Van Hemert 2016) | Proprietary signals |
| Gresham | Long-only commodity index manager (TAP) | Not a signal source |
| Bridgewater | All-weather framing (commodities as inflation hedge) | Little published on commodity signals |
| CTAs | Trend following dominates (SG CTA indices) | Claims of systematic commodity fundamentals edges are rarely documented |

Gorton and Rouwenhorst's affiliation with SummerHaven (a commodity manager using backwardation and momentum) is a documented example of academic signals becoming products.

## 11. Ranked build plan

| Order | Build | Specification | Data | Pre-registered pass/fail | Expected effect |
|---|---|---|---|---|---|
| 0 | Data-feasibility check | Assemble 22 markets, F1/F2/F13, 1990–2026; reconstruct an equal-weight excess-return index and a KMPV-style carry portfolio | Norgate or Pinnacle; Databento cross-check | Pass if: (a) ≥ 18 markets with F1/F2 coverage ≥ 95% of months since 2000; (b) equal-weight index correlation ≥ 0.9 with AQR's Commodities for the Long Run index over overlapping months; (c) carry portfolio correlation ≥ 0.7 with AQR commodity carry factor | Infrastructure |
| 1 | Carry (de-seasonalised, 12m) | Section 3.2 Option A, fallback B | F1, F13 | Walk-forward 2000–2019 and holdout 2020–2026; pass if net Sharpe > 0.2, Clark-West p < 0.05 vs zero, break-even cost ≥ 2× | Sharpe 0.25–0.35 net |
| 2 | Basis-momentum | Section 3.4 | F1, F2 | Pass if t > 2 on 2000–2026 net of costs, and incremental alpha vs carry > 0 (t > 1.5) | Sharpe 0.2–0.35; corr with carry 0.2–0.4 |
| 3 | Composite (equal weight carry + BM) | Section 4.3 ensemble | as above | Pass if composite Sharpe ≥ max single; added to baseline raises Sharpe and does not worsen max DD | Combined Sharpe 0.69–0.71 |
| 4 | Smoothed hedging pressure | Section 3.6 | CFTC disaggregated | Pass if alpha vs composite t > 2 | Small; mixed evidence |
| 5 | Value | Section 3.5 | F1 prices | Same | Small |
| 6 | Volatility model upgrade (HAR) | Section 4.3 | Daily returns | Lower tail loss, no Sharpe loss | Risk-control only |

Multiple-testing correction: count every signal, variant and parameter tried; apply the Holm–Bonferroni correction across the 6 builds and report the deflated Sharpe of the final composite. Live validation: 12 months paper trading on the micro-contract subset before adding risk.

Open questions where evidence is too weak to act: skewness as a separate factor; ML methods for commodity returns; the regime and macro forecasting of commodity indices; gold valuation (real price) as a forecast; whether commodity trend adds value for a programme whose FX/bond trend failed; whether basis-momentum's post-2019 record survives independent replication.

## Caveats

Published Sharpe ratios are mostly in-sample and gross of realistic costs; the haircuts used here are judgement. Several data-vendor prices come from vendor pages or third-party summaries and may change. Correlation expectations in Sections 3.9 and 6.1 are judgement until measured. The Boons out-of-sample update is author-reported.

## Appendix A: Formula sheet

```
r_ex[i,t]      = F[i,T,t]/F[i,T,t-1] - 1
carry_log      = (ln F1 - ln F2) * 365/(D2 - D1)
carry12        = (ln F1 - ln F13) * 365/(D13 - D1)
carry_ds       = carry_log - mean_same_month_5y(carry_log)
bm             = sum12(r_ex F1) - sum12(r_ex F2)
xs_mom         = ln idx[t-1m] - ln idx[t-12m]
value          = ln mean(F1[t-66m:t-54m]) - ln F1[t]
HP             = (CS - CL)/(CS + CL);  SHP = mean_52w(HP)
skew           = skewness(daily r_ex, 252d)
sigma_EWMA     : s2[t] = 0.94 s2[t-1] + 0.06 r[t-1]^2
R2_OS          = 1 - SSE_model/SSE_histmean
S_comb^2       = (S1^2 + S2^2 - 2 rho S1 S2)/(1 - rho^2)
half_life      = -ln 2 / ln(1 + b)
```

## Appendix B: Data dictionary

| Field | Definition | Source | Frequency |
|---|---|---|---|
| settle[i,T,t] | Official settlement | Norgate/Pinnacle/Databento/CME | Daily |
| oi[i,T,t] | Open interest | Same | Daily |
| fnd[T], ltd[T] | First notice, last trade dates | Exchange calendars | Static |
| cot_comm_long/short[i,w] | Commercial positions | CFTC | Weekly (Tue, pub Fri) |
| eia_crude_stocks[w] | US commercial crude stocks | EIA API v2 | Weekly (Wed) |
| eia_ng_storage[w] | Working gas in storage | EIA API v2 | Weekly (Thu) |
| nass_condition[c,w] | Crop condition | USDA NASS | Weekly (season) |
| tips10[t], dxy[t] | Real yield, dollar | FRED | Daily |
| rf[t] | Funding rate | Existing programme | Daily |

## Appendix C: Reference list

Asness, Moskowitz, Pedersen (2013) Value and Momentum Everywhere, JF 68(3). Bailey, Borwein, López de Prado, Zhu (2017) Probability of Backtest Overfitting, J. Computational Finance. Bailey, López de Prado (2014) The Deflated Sharpe Ratio, JPM. Bakshi, Gao, Rossi (2019) Understanding the Sources of Risk Underlying the Cross Section of Commodity Returns, Management Science 65(2). Basu, Miffre (2013) Capturing the Risk Premium of Commodity Futures: The Role of Hedging Pressure, JBF 37(7). Boons, Porras Prado (2019) Basis-Momentum, JF 74(1). Campbell, Thompson (2008) RFS. Clark, West (2007) JoE. Corsi (2009) J. Financial Econometrics. de Roon, Nijman, Veld (2000) JF. Diebold, Mariano (1995) JBES. Erb, Harvey (2006) FAJ 62(2); Erb, Harvey (2013) The Golden Dilemma, FAJ. Fernandez-Perez, Frijns, Fuertes, Miffre (2018) JBF 86. Gargano, Timmermann (2014) IJF 30(3). Geczy, Samonov (2019) Two Centuries of Commodity Futures Premia. Gibson, Schwartz (1990) JF. Gorton, Rouwenhorst (2006) FAJ 62(2). Gorton, Hayashi, Rouwenhorst (2013) RoF 17(1). Han, Kong (SSRN) Lead-lag relations in commodity futures returns. Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert (2018) JPM 45(1). Hurst, Ooi, Pedersen (2017) JPM 44(1). Ilmanen, Israel, Moskowitz, Thapar, Lee (2021) How Do Factor Premia Vary Over Time? Kang, Rouwenhorst, Tang (2020) JF 75(1). Koijen, Moskowitz, Pedersen, Vrugt (2018) JFE 127(2). Levine, Ooi, Richardson, Sasseville (2018) FAJ 74(2). Maréchal (2023) JFM 43(5). McLean, Pontiff (2016) JF. Miffre, Rallis (2007) JBF 31(6). Moskowitz, Ooi, Pedersen (2012) JFE 104(2). Rapach, Strauss, Zhou (2010) RFS. Schwartz (1997) JF 52(3). Schwartz, Smith (2000) Management Science. Szymanowska, de Roon, Nijman, van den Goorbergh (2014) JF 69(1). Wang, Zhang (2024) JFM 44(2).
