# Horizons Global Macro: Implementation Specification for Redesigning and Hardening a Cross-Country Carry/Trend/Value Strategy in FX and Government Bonds

*Note on process:* the enrichment pass never ran, because every version of the draft exceeded the 50,000-character limit of the enrichment tool. The hedged and secondary-sourced claims below are therefore flagged as they stand.

**Bottom line.** Better risk control is likely to help more than new alpha. Five changes have the strongest evidence:
1. Attribute and decompose the current book.
2. Size positions using the covariance matrix and factor exposures, with explicit caps on dollar and EM risk.
3. Add a pooled, point-in-time carry-crash filter.
4. Redefine trend as time-series momentum and value as real-yield/REER value.
5. Adopt an election event-risk protocol.

None of these should be adopted until it passes walk-forward, cross-sectional-holdout and frozen live tests. Once the current Sharpe of 0.65 over 6.75 years is deflated for about seven trials, it cannot be distinguished from luck.

## TL;DR

- **The current result is fragile.**
  - A Sharpe of 0.65 over 81 months gives t ≈ 1.69 (two-sided p ≈ 0.09).
  - A Bonferroni haircut for 7 trials (Harvey-Liu) takes it to about 0.18, a 72% cut.
  - The deflated Sharpe ratio is about 0.61 against a noise-only null, below the 0.95 required.
  - With carry-like skew and kurtosis, separating SR 0.65 from zero needs about 4.6 years of track record at 90% confidence and 7.6 years at 95%.
- **The literature matches the user's own diagnostics.**
  - Carry is the most robust premium: Koijen, Moskowitz, Pedersen and Vrugt (2018) report a currency-carry Sharpe of 0.68 and 1.20 for diversified carry.
  - Cross-sectional FX momentum is weak: Sharpe 0.32 over 1979–2011 (Asness, Moskowitz and Pedersen 2013). Baz et al. (2015) find momentum "works well in time series, but poorly in the cross section".
  - Bond value built on the 5-year yield change earned Sharpe 0.07, against 0.73 for real-yield value.
- **Build order.**
  - First: (1) P&L attribution, (2) a risk audit, (3) a ledger of every variant tried, with multiple-testing statistics, (4) a carry-crash filter.
  - Then: factor-capped sizing, redefined trend and value, value as a conditioner on carry, economic momentum, and the election protocol.
  - Judge each change only on years after its calibration window, on the held-out half of countries, and in frozen live paper trading from November 2026.

---

## 0. Conventions, decay evidence and validation protocol

**Labels.**
- [F] sourced fact
- [J] judgement
- [A] assumed parameter; must be pre-registered and tested for sensitivity

**Abbreviations.** IS = in-sample. OOS = out-of-sample. Post-pub = after publication. Returns are monthly USD excess returns.

**Sample caveat.** Most canonical FX and bond factor samples end between 2009 and 2015.

### 0.1 Decay evidence (applies to every signal)

| Finding | Source | Sample | Type | Effect |
|---|---|---|---|---|
| Factor Sharpes fall out of sample | Ilmanen, Israel, Lee, Moskowitz, Thapar (2021, JOIM) | 1926–2020; 13 govt bond markets, 20 currencies | OOS | Value −49% (p=0.000); momentum ≈−23% (p=0.094); carry ≈−25% (p=0.243); multifactor −18% |
| FX carry after the original sample | Ilmanen et al. (2021) | same | OOS | "For currencies… the post-sample carry performance is larger than the original sample performance" |
| FX value after the original sample | Ilmanen et al. (2021) | same | OOS | "the post-sample performance of value is as large as the original sample" |
| Factor timing | Ilmanen et al. (2021) | same | OOS | "significant profitability eludes a host of timing strategies once proper data lags and transactions costs are accounted for" |
| 13 published carry strategies | Hsu, Li, Taylor, Wang (2025, J. Empirical Finance 83) | various | Post-pub | Pass data-snooping tests before publication, but "profitability has declined since their publication years" (size of the decline not in the accessible text) |
| Carry strategies chosen in-sample | Hsu, Taylor, Wang (2024, JIMF 143) | 48 currencies, 1983–2015 | OOS | Carry "generally ha[s] no persistent profitability" |
| FX carry, momentum and value | Hutchinson, Kyziropoulos, O'Brien, O'Reilly, Sharma (2022, IRFA 83) | pre/post publication | Post-pub | "Subsequent to publication… investment performance disappears" |
| Equity benchmark | McLean and Pontiff (2016), via Chen and Zimmermann (arXiv 2209.13623) | US equities | Post-pub | About 50% lower after publication; about 12 points of that is publication bias |

[J] The evidence on carry conflicts: Ilmanen et al. find it robust, while Hsu et al. and Hutchinson et al. find decay. Value and momentum decay more. Shrink the prior Sharpe of any new signal by 25–50% from its published in-sample figure.

### 0.2 Multiple-testing arithmetic for the current result

**Inputs.**
- SR_ann = 0.65; T = 81 months; SR_m = 0.65/sqrt(12) = 0.18764; N = 7 trials.
- Moment scenarios:
  - S1 (normal): skew γ3 = 0, raw kurtosis γ4 = 3.
  - S2 (carry-like): γ3 = −0.7, γ4 = 5. Koijen et al. (2018) report currency-carry skew of −0.68 and kurtosis of 4.46 over Nov 1983–Feb 2011.
  - S3 (severe): γ3 = −1.0, γ4 = 6, close to Koijen et al.'s −0.96 and 6.08 for carry1-12.

**(a) Naive test.**
- t = 0.65 × sqrt(6.75) = 1.689. Two-sided p = 0.091; one-sided p = 0.046.
- SE(SR) ≈ sqrt((1 + 0.5×0.65²)/6.75) = 0.42, which matches the user's ±0.4.

**(b) Probabilistic Sharpe ratio (Bailey and López de Prado 2012).**

```
sigma_SR = sqrt((1 - γ3*SR_m + ((γ4-1)/4)*SR_m^2) / (T-1))
PSR = Φ((SR_m - SR*) / sigma_SR)
```

With SR* = 0, PSR = 0.952 under S1 and 0.940 under S2.

**(c) Deflated Sharpe ratio (Bailey and López de Prado 2014).**

```
SR0 = sd(SR_n) * ((1-γe)*Φ^-1(1-1/N) + γe*Φ^-1(1-1/(N*e))),  γe = 0.5772
```

- For N = 7 the bracket is 0.42279×1.0676 + 0.57722×1.6211 = 1.3871.
- **Noise-only null** (sd = 1/sqrt(80) = 0.1118 per month): SR0 = 0.155 monthly (0.537 annualised), so DSR = Φ(0.289) ≈ 0.61.
- **Dispersed trials** (trial-Sharpe SD of 0.20 annualised): SR0 = 0.28 annualised, so DSR ≈ 0.83.
- Both are below the 0.95 threshold.

**(d) Harvey-Liu (2015) haircut, M = 7.**
- Bonferroni (equal to Holm for the top-ranked test): p_adj = min(1, 7×0.0912) = 0.638, so SR_adj = 0.471/2.598 = 0.18 (72% haircut).
- Šidák: p_adj = 1 − 0.9088⁷ = 0.488, so SR_adj = 0.27 (59% haircut).
- BHY (c(M) = 2.593): p_adj ≥ 1, a haircut of about 100% unless the other tests were strong.
- The Harvey, Liu and Zhu (2016) bar of t > 3 would need (3/0.65)² = 21.3 years.

**(e) Minimum track record length.**

```
MinTRL = 1 + (1 - γ3*SR_m + ((γ4-1)/4)*SR_m^2) * (z/(SR_m - SR*))^2   [months]
```

| Scenario | 90% (z=1.2816) | 95% (z=1.6449) |
|---|---|---|
| S1 normal | 48.5 mo (4.0 y) | 79.2 mo (6.6 y) |
| S2 carry-like | 55.4 mo (4.6 y) | 90.6 mo (7.6 y) |
| S3 severe | 58.5 mo (4.9 y) | 95.7 mo (8.0 y) |

Measured against SR* = 0.537 instead of zero, MinTRL is more than 200 years.

**Interpretation [J].**
- The 2020–2026 run was a single test of a frozen design, which is the strongest kind of evidence available here.
- The seven-trial deflation applies fully only if this strategy was picked from those seven. Most of the rejected ideas were separate strategies, so the honest DSR range is 0.61–0.95.
- Every future modification adds trials, so the trial counter must persist.

### 0.3 Four-stage test for every modification

**(a) Evidence.** At least one peer-reviewed, central-bank, BIS or IMF source, with its sample and asset class recorded.

**(b) Walk-forward.**
- For each year Y from 2020 to 2026: estimate on data up to Dec(Y−1), then trade Y with parameters frozen.
- Use an expanding window starting in 2005 or earlier.
- Report each year separately and pooled.

**(c) Cross-sectional holdout.**
- Before any development, split the countries in half, stratified by region and by developed/emerging, using a committed random seed.
- Develop on half A and validate once on half B.
- New entrants are assigned by a hash of their ISO code.

**(d) Live.**
- Tag the frozen version in git and publish a timestamped SHA-256 hash of its config before the 3 November 2026 rebalance.
- Make no changes for 12 months except logged bug fixes.

**Pass rule [J].** Keep a change only if all of these hold:
- Walk-forward ΔSR > 0, with block-bootstrap (6-month blocks) one-sided p < 0.10.
- Holdout ΔSR > 0, and drawdown moves in the same direction.
- Combined maximum drawdown and ES(97.5%) worsen by no more than 10%.
- The new DSR, with N incremented, is at least the old one.

For risk-only changes, the primary metric is ES or drawdown, provided Sharpe falls by no more than 0.05.

### 0.4 Honest reporting

v1.0's +6.0% a year at SR 0.65 stays labelled "OOS for v1.0 only". Report v2 results separately and never merge them with v1.0's.

| Version | Period | Type | Calibration | Countries | Return | Vol | SR | MaxDD | Skew | N | DSR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 | 2005–2019 | In-sample | 2005–2019 | all | | | | | | | |
| v1.0 | 2020-01–2026-09 | Single OOS | 2005–2019 | all | +6.0% | | 0.65 | −18% | | 7 | |
| v2.x | 2020–2026 | Walk-forward | ≤ Y−1 | all | | | | | | | |
| v2.x | 2005–2026 | Holdout | half A | half B | | | | | | | |
| v2.x | 2026-11 → | Live frozen | ≤ 2026-10 | all | | | | | | | |

---

## 1. Carry

### 1.1 Evidence

| Method | Source | Sample | IS/OOS | Effect | After publication |
|---|---|---|---|---|---|
| Cross-sectional FX carry | Koijen, Moskowitz, Pedersen, Vrugt (2018, JFE) | Nov 1983–Feb 2011 | IS | SR 0.68; mean 5.29%, vol 7.80%, skew −0.68 | Ilmanen et al.: FX carry stronger after the original sample |
| Carry1-12 | Koijen et al. (2018) | same | IS | SR 0.55, skew −0.96 | — |
| Global carry across asset classes | Koijen et al. (2018) | varies | IS | SR 1.20; passive long 0.40 | — |
| Carry and global FX volatility | Menkhoff, Sarno, Schmeling, Schrimpf (2012, JF) | 1983–2009 | IS | Global FX volatility innovations explain more than 90% of the spread across five carry portfolios | Consistent with the 2024 unwind |
| Dollar carry | Lustig, Roussanov, Verdelhan (2014, JFE) | 1983–2010 | IS | SR "in excess of 0.50"; roughly zero correlation with high-minus-low carry | — |
| Dollar-neutral vs dollar carry | Daniel, Hodrick, Lu (2017, CFR) | G10 | IS | USD-based carry SR 0.78 (SE 0.19). The dollar-neutral part has insignificant alpha and strong negative skew; the dollar part has significant alpha and little skew | — |
| Crash risk | Brunnermeier, Nagel, Pedersen (2008) | 1986–2006 | IS | Negative skew; "a higher risk reversal predicts a lower future skewness" | Repeated in 2008 and 2024 |

[F] In the user's results, the equal-weight high-yield basket returned −0.5% a year, while cross-sectional carry returned +10.1%.

[J] Daniel-Hodrick-Lu imply that dollar exposure is a separate, time-varying bet. Measure it and cap it explicitly.

### 1.2 Currency carry definitions

```
carry_fwd = (S - F)/F * 12/m        # S,F USD per FC; m tenor months; ≈ i* - i_US under CIP
carry_rate = y3m_i - y3m_US         # fallback
carry_pol  = p_i - p_US             # weakest proxy
carry_real = carry_fwd - (π^e_i - π^e_US)
carry_va   = carry_fwd / σ_i         # σ = EWMA vol, half-life 60 days [A]
dcarry     = carry_t - carry_{t-3}   # carry momentum; low prior
```

**Forward-implied carry** is what a forward position actually earns. It differs from rate differentials because of deviations from covered interest parity (CIP).

**NDF currencies** (BRL, COP, CLP, INR, KRW, IDR, PHP, TWD, ARS):
- Use NDF-implied (offshore) carry. Offshore and onshore rates diverge when capital controls bind.
- If only onshore rates are available, apply a haircut h_ndf = 0.75 [A] and flag the data as quality C.
- Synthetic return: r = (S_{t+1} − F_t)/F_t, with F_t = S_t (1 + i_US τ)/(1 + i_off τ).
- None of these currencies is deliverable to a retail paper account. Proxies are CME BRL and INR futures, or synthetic forwards for research only.

**Real carry.** Jordà and Taylor (2012, JIE, 1986–2008) show that fundamentals-augmented carry reduces crash risk. A secondary source (Macrosynergy; 26 currencies, 2000–2022) reports a real-carry Sharpe of only 0.23. Test real carry rather than assume it helps.

**Dollar construction [J].**
- Make the core dollar-neutral: w_DN = w − mean(w).
- Add a separate dollar sleeve that is long the foreign basket when the average forward discount is positive (Lustig-Roussanov-Verdelhan). Cap it at 20% of risk.

### 1.3 Bond carry

```
carry_bond = (y_n - r_f) + D_mod * (y_n - y_{n-Δ})/Δ       # term spread + roll-down (Koijen et al.: return if curve unchanged)
slope proxy: y_{n-Δ} ≈ y10 - (y10 - y2)/8 * Δ
carry_hedged_USD = carry_bond_local + (r_US - r_i)
```

**By instrument.**
- Cash bonds: coupon plus pull-to-par minus repo. Use the 3-month rate as the repo proxy [A].
- Futures: funding is already netted out.
- Receiver swaps: fixed minus float plus roll. This is the cleanest instrument but is not available to retail.

[J] **Change.** Rank bond carry on term spread plus roll-down, never on the yield level. Ranking on the level duplicates FX carry and concentrates the book in high-yield EM.

[F] Asness, Moskowitz and Pedersen (AMP, 2013) find a Sharpe of 0.55–0.65 for bond term-spread value over 1982–2011. This overlaps with carry, so check collinearity.

```python
def bond_carry(y10, y2, rf, Dmod): return (y10 - rf) + Dmod * (y10 - y2) / 8.0
```

**Failure modes.**
- Stale NDF forward points.
- CIP-basis spikes (2008, March 2020).
- Pegged or crawling currencies with huge "carry" (ARS, TRY).

**Test.** Each definition is a frozen variant (N += 4). Select on pre-2020 data and confirm on the walk-forward and holdout.

---

## 2. Trend and momentum

### 2.1 Evidence

| Method | Source | Sample | IS/OOS | Effect |
|---|---|---|---|---|
| Time-series momentum (TSMOM) | Moskowitz, Ooi, Pedersen (2012, JFE) | 58 futures, 1985–2009 | IS | Significant in all 58 instruments; strongest in extreme markets |
| Century of trend | Hurst, Ooi, Pedersen (AQR 2014/2017) | 1880–2013 | OOS, backwards in time | SR 0.77 net of estimated costs (11.2% net, 9.7% vol) |
| Cross-sectional FX momentum | AMP (2013) | 10 currencies, 1979–2011 | IS | SR 0.32; correlation with value −0.42 |
| Currency momentum | Menkhoff, Sarno, Schmeling, Schrimpf (2012, JFE) | 48 currencies, 1976–2010 | IS | Up to 10% a year; "partially explained by transaction costs" |
| Cross-sectional bond momentum | AMP (2013) | 10 bond markets, 1982–2011 | IS | SR 0.06–0.17; bonds "do not produce statistically reliable premia" |
| Time series vs cross-section | Baz, Granger, Harvey, Le Roux, Rattray (2015) | 87 instruments, 1990–2015 | IS | Momentum works in time series, not cross-section; value is the reverse; carry works in both |
| Is trend decaying? | Man AHL, Korgaonkar (2025) | SG Trend, 2000–Apr 2025 | Practitioner | Drawdown "not unexpected"; correlation between fund flows and performance −0.1 |
| Volatility targeting | Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert (2018, JPM) | 60+ assets from 1926 | IS | Sharpe effect "negligible" for bonds, FX and commodities; fewer extreme returns |

### 2.2 Diagnosis and specification [J]

The current trend sleeve is cross-sectional, which is the weakest construction for momentum. A −0.4% a year result over 6.75 years is within noise for a true Sharpe of 0.2–0.3. Dropping trend because of 2020–2026 would be in-sample selection. The fix is to redefine trend as time-series, justified by the published evidence rather than the recent backtest.

```
TSMOM_cont_k = clip(Σ_{last k months} r / (σ * sqrt(k/12)), -2, 2) / 2,   k ∈ {1,3,6,12}
TREND = mean_k(TSMOM_cont_k)                         # fixed equal-weight blend
EWMAC(f,s) = (EMA_f(P) - EMA_s(P)) / σ_price,  (f,s) ∈ {(16,64),(32,128),(64,256)} days [A]
pos = TREND * σ_target_sleeve / σ_i / n_active,  σ = EWMA, centre of mass 60 days (per MOP 2012)
```

- **No lookback selection.** Do not choose a lookback on 2020–2026 data; any selection counts as a trial.
- **Speed.** Faster trend helps in sudden crises but turns over more. Slower trend held up better in 2022.
- **Why trend struggled in the 2020s.** Either a regime effect (Man AHL 2025 cites "on/off US policy dynamics") or structural decay (Ilmanen et al. 2021 find momentum ≈−23% OOS, not significant; Hutchinson et al. 2022). Six years of data cannot tell them apart.
- **Sizing.** Keep about 20% of risk in time-series trend for its crisis convexity, and monitor it (§14).
- **Bond trend.** This is mostly a duration bet. Also run it on spreads against Germany and the US, and cap net duration.

**Test.** There are no parameters to estimate. Pass if the combined Sharpe does not fall and the sleeve's correlation with carry, in carry's worst 10% of months, is below zero.

---

## 3. Value

### 3.1 Evidence

| Method | Source | Sample | Effect |
|---|---|---|---|
| FX value (5-year PPP change) | AMP (2013) | 1979–2011 | SR 0.44 (rank-weighted factor), 0.34 (top third minus bottom third, P3–P1); 0.69 combined with momentum |
| Bond value (5-year yield change) | AMP (2013) | 1982–2011 | SR 0.07 (factor), 0.18 (P3–P1) |
| Bond real-yield value | AMP (2013) | same | SR 0.70–0.73 |
| Bond composite value | AMP (2013) | same | SR 1.10 (factor), 0.91 (P3–P1) |
| FEER conditioning of carry | Jordà and Taylor (2012, JIE) | 1986–2008, IS and OOS | In 2008 "a 30%+ loss on the carry signal… was offset by a 10% gain on the PPP signal" |
| Switching from carry to PPP in turbulence | Amundi working paper, "Revenge of Fundamentals" | 28 currency pairs | Worst month −3.8% vs −6.75% for pure carry (practitioner) |
| BEER-boosted carry | Open Economies Review (2024) | — | Earlier Sharpe claims of up to 0.75 are inflated by longer, broader samples |

### 3.2 Definitions

```
q = s + p_US - p_i                                   # log real exchange rate
VAL_ppp5 = -(q_t - q_{t-60m})
VAL_reer = -(log REER_t - mean(log REER, t-120m..t-1))  # BIS broad REER
VAL_bs   = residual of q_i on log(GDP per capita PPP)    # Balassa-Samuelson
VAL_realyld = y10 - π^e;  VAL_ngdp = y10 - g^e_nominal;  VAL_policy = y10 - p
VAL_bond_comp = mean_z(VAL_realyld, VAL_ngdp)
```

[F] The consensus PPP half-life is 3–5 years (Rogoff 1996; not re-verified). Value should not be expected to pay off within 6.75 years.

[J] **Recommendations.**
- Replace price-change value with VAL_reer, and test VAL_bs as a variant.
- For bonds, use real-yield or composite value, with breakeven inflation as π^e where inflation-linked bonds exist.
- Pair EM real yields with fiscal risk, because a high real yield may reflect default risk rather than cheapness.

**Why value lost money.** High-carry EM currencies stayed "expensive" while carry paid, so the value sleeve was short what carry was long. This, together with Jordà-Taylor, supports using value as a conditioner on carry (§5).

---

## 4. Additional signals ranked by strength of evidence

| Rank | Signal | Source | Sample | Published effect | Adds information after carry, trend, value? | Prior [J] |
|---|---|---|---|---|---|---|
| 1 | Economic momentum | Dahlquist and Hasseltoft (2020, JFE) | G10 + EM, ~33 currencies for macro data | SR "about one" (SSRN abstract); a secondary source says 0.70 (conflict) | Yes. Significant alpha; subsumes the carry alpha; less than half explained by carry, momentum and value | High |
| 2 | Global imbalances (net foreign assets, NFA) | Della Corte, Riddiough, Sarno (2016, RFS) | Oct 1983–Jun 2014 | SR 0.59 (major currencies) | Yes (risk factor) | Medium-high, as a conditioner |
| 3 | Risk reversals | Brunnermeier, Nagel, Pedersen (2008) | 1986–2006 | Predict skewness | For crash risk | Medium (data hard to obtain) |
| 4 | Global FX volatility | Menkhoff et al. (2012) | 1983–2009 | Explains more than 90% of the carry cross-section | Contemporaneous factor | Medium, as a regime input |
| 5 | Dollar factor | Lustig, Roussanov, Verdelhan (2014) | 1983–2010 | SR above 0.5 | Yes | Medium |
| 6 | Election premium in options | Kelly, Pástor, Veronesi (2016, JF) | 20 countries | Options spanning elections ≈5% dearer at the money; ≈16% dearer for 10% out-of-the-money puts | For sizing | Medium |
| 7 | CFTC positioning | BIS Bulletin 90 (2024) | 2024 | Crowded yen shorts preceded the unwind | Not proven as a predictor | Low-medium |
| 8 | Fiscal and ratings | User's own study (France +37bp, BRL/MXN +10bp per notch, IS) | — | — | Unknown | Low; risk use only |

Terms-of-trade evidence was not verified in this session: it fits well contemporaneously but predicts weakly month to month. No credible source was found for seasonality alpha.

**4.1 Economic momentum.**
- [F] Past trends in industrial production, retail sales, unemployment and inflation predict currency returns "up to a horizon of 12 months". Past inflation predicts returns positively, through the policy response.

```
trend_v = v_{t-lag} - mean(v_{t-lag-60..t-lag-1})  for v in {IP_yoy, RS_yoy, -U, CPI_yoy}
ECONMOM = mean of cross-sectional z-scores
```

- Use OECD Main Economic Indicators first-release vintages (ALFRED, the OECD revisions database).
- The signal is collinear with carry. Test it both as a replacement for carry and as an orthogonalised addition. Do not search parameters on 2020–2026.

**4.2 Policy path.** The user's Fed model was beaten by futures, which is consistent with near-term policy being efficiently priced. Do not re-propose it. Use the real policy rate (p − π^e) only as a crash-filter feature.

**4.3 External vulnerability.**
- [F] Della Corte, Riddiough and Sarno (2016) find that debtor currencies with foreign-currency liabilities "depreciate in bad times".
- Crash-filter features:
  - current account / GDP (4-quarter sum) and basic balance
  - NFA / GDP
  - reserves / short-term debt (Greenspan-Guidotti rule: below 1 is vulnerable)
  - the IMF ARA metric

**4.4 Fiscal.**

```
Δd = (r_eff - g)/(1+g) * d_{t-1} - pb
```

[J] Use fiscal variables to describe risk, not to predict returns; the user's fair-value model failed.

**4.5 Terms of trade.**

```
ToT_mom = Σ_c ω_c Δ3m log P_c      # IMF commodity ToT indices
```

Relevant for AUD, NZD, CAD, NOK, CLP, BRL, COP, MXN and ZAR. Crash-filter feature only.

**4.6 Positioning.**
- CFTC Commitments of Traders: weekly (Tuesday positions, released Friday).
- [F] In August 2024 the Mexican peso "was hit hardest, followed by the Brazilian real and South African rand" (BIS Bulletin 90).
- [J] Use a 3-year z-score of net speculative positioning as a crash feature.

**4.7 Options.**

```
RR25 = σ(25Δ call) - σ(25Δ put);  VRP = σ_impl_1m - σ_real_1m
```

Free history is essentially unavailable, so use realised-volatility proxies.

**4.8 Cross-asset [J].** Build a risk-appetite composite from VIX level and change, the change in high-yield spreads (FRED), and 3-month EM equity momentum. Use it only as a crash and regime input.

**4.9 Calendar [J].** Avoid month-end fixings. Keep rebalancing on the 3rd.

### 4.10 Formalising the EM election continuation rule

**Facts.**
- [F] User's own work: poll surprise correlates 0.72 with the day-1 currency move; 8 of 9 OOS cases had the right sign; the move continues. The euro-area version failed (r = 0.06, 40 events).
- [F] Kelly, Pástor and Veronesi (2016): political uncertainty is priced, including in FX options.

**Rule [J, pre-registered].**

```
Universe: national elections/referendums, EM currencies in universe.
surprise = (result_share - final 7-day poll average) * market_sign   # market_sign classified BEFORE vote from published analyst notes; ambiguous excluded
Day-1 move = evidence, not a trade. Entry: close of first full trading day after result; position = sign(surprise)
Hold H = 5 trading days [A] (H ∈ {5,10} = 2 trials)
Size = min(0.5 * 0.25 * Kelly(p, b), 2% risk);  p from Beta(9,2) posterior ≈ 0.82
Stop = 1.5 * σ_daily * sqrt(H)
```

The Clopper-Pearson 95% interval for 8/9 is about 52–99%, so the small sample is the main risk. Reconstruct EM elections since 2000 using pre-event poll averages, only where archive dates prove the polls were available before the vote. Keep adding events from live trading.

---

## 5. Signal combination and model architecture

```
EW: S = mean_k z_k;   IV: weights ∝ 1/σ²_k (36-month factor vol)
Ridge: β̂ = argmin Σ (r - z'β)² + λ||β - β_EW||²   (λ only inside the walk-forward)
Rank weighting (AMP 2013): w_i = c_t (rank_i - (n+1)/2), Σ|w| = 2
```

[F] Factor timing fails after costs (Ilmanen et al. 2021). Equal weighting (1/N) is hard to beat in short samples (DeMiguel, Garlappi and Uppal 2009; not re-verified).

**Recommendations [J].**
- **Separate sleeves, not z-score averaging.** Averaging lets one signal veto another and hides attribution. Fixed risk budgets [A]: carry 0.40, value 0.15, trend 0.20, economic momentum 0.25.
- **Rank weighting, not top/bottom thirds.** AMP report 0.44 vs 0.34 for FX value. Rank weighting uses all countries and handles entry and exit smoothly. It counts as one trial.
- **Condition carry on value and vulnerability** (Jordà-Taylor; Della Corte et al.):

```
carry_cond = carry * g,   g = 0.5 if VAL_reer < -1σ (overvalued) or VULN > 1σ, else 1   [A]
```

**Machine learning.**
- [F] Fan (2025, Financial Review) searched 24,336 optimisation approaches. [J] That is the multiple-testing problem this specification is built to avoid.
- [F] Hsu, Taylor and Wang (2024) show that carry strategies selected in-sample fail OOS.
- [J] With about 30 countries × 250 months:
  - Allowed: ridge or elastic net on 4–8 pre-specified features.
  - Allowed as a challenger only: gradient boosting with depth ≤ 2, validated by combinatorial purged cross-validation (López de Prado 2018), reporting the probability of backtest overfitting (Bailey, Borwein, López de Prado, Zhu 2017).

---

## 6. Regime detection and crash-risk controls

### 6.1 Predictors with evidence

| Predictor | Source | Note |
|---|---|---|
| Global FX volatility innovations | Menkhoff et al. (2012) | Contemporaneous risk factor |
| Risk reversals; past carry gains | Brunnermeier, Nagel, Pedersen (2008) | "Carry-trade losses reduce future crash risk, but increase the price of crash risk" |
| Real overvaluation | Jordà and Taylor (2012) | Conditioning reduces crash losses |
| NFA and foreign-currency liabilities | Della Corte, Riddiough, Sarno (2016) | Debtor currencies fall in bad times |
| Positioning and leverage | BIS Bulletin 90; BIS Quarterly Review, September 2024 | Leveraged carry "had grown rapidly"; moves were "large but not outsize compared with past carry trade crashes" |
| Reserves, current account | Kaminsky-Lizondo-Reinhart 1998; Frankel-Rose 1996 (not re-verified) | Modest OOS power |

### 6.2 Crash filter (first build #4)

**Crash label [A].**

```
CR_{i,t,h} = 1 if min cumulative FX excess return over τ ≤ h is ≤ -2.0 * σ_{i,t} * sqrt(h/12),  h ∈ {1,3,6}
Secondary: ≤ -7% within 3 months
```

**Features.** All point-in-time, each lagged by its publication delay:
- carry z-score; VAL_reer
- current account / GDP; reserves / short-term debt; NFA / GDP
- log(σ_1m / σ_12m)
- 3-month changes in VIX, the dollar and the US 2-year yield
- the currency's own 12-month carry return
- CFTC z-score, with a missing-data indicator
- election within h months (0/1)

**Model.** Pooled logistic regression with an L2 penalty and no country fixed effects, so it applies to new entrants.

**Validation.**
- Expanding window from 1995. Purge any label whose window runs past the end of the training data.
- Choose λ by time-blocked cross-validation inside the training window.
- Metrics: AUC, Brier skill, reliability curve.
- Holdout: train on half A, test on half B.

**Decision rule [A].**

```
scale = clip(1 - (p - p_base)/(2 p_base), 0, 1)     # long high-yielders only
```

**Pass.** Walk-forward AUC > 0.60; Brier skill > 0 on half B; carry-sleeve ES down at least 15%; carry Sharpe down no more than 0.10.

**Failure modes.**
- Few crash events to learn from.
- Revised macro data.
- Lagging volatility features: the filter can de-risk after the crash and miss the rebound.

```python
def crash_wf(panel, years, X, h=3, C=1.0):
    out = {}
    for Y in years:
        tr = panel[panel.date <= pd.Timestamp(f"{Y}-01-01") - pd.DateOffset(months=h)].dropna(subset=["y"])
        m = LogisticRegression(penalty="l2", C=C).fit(std(tr[X]), tr.y)
        te = panel[panel.date.dt.year == Y]
        out[Y] = m.predict_proba(std(te[X], ref=tr))[:, 1]
    return out
```

### 6.3 Regimes

- **FX-volatility regime.** When global FX volatility is above the 80th percentile of its expanding history, multiply the carry budget by 0.5 [A].
- **Markov switching.** Unstable out of sample; use only as a diagnostic.
- **Growth/inflation quadrants.** [F] Ilmanen et al. find "little reliable relation" between factor premia and macro risks. Low prior.

### 6.4 Drawdown control

[F] Hsu, Taylor and Wang (2024) find OOS carry unreliable even "allowing for learning and stop-loss strategies".

[J] Use a portfolio-level governor rather than position stops: halve gross risk when the drawdown exceeds 1.5× the 95th-percentile expected drawdown. Test it as one variant.

### 6.5 Event protocol [J]

- **Elections and referendums while long carry:** cap the position at 50% of risk from T−5 to T+1, then apply the continuation rule.
- **EU rating reviews (pre-announced calendar):** no new additions from T−2 to T+1.
- **Central-bank decisions:** no de-risking, because futures price them efficiently.

As an illustration only, this would have halved the 8% BRL loss in 2026.

---

## 7. Portfolio construction and risk management

```
EWMA: Σ_t = λΣ_{t-1} + (1-λ) r r',  λ = 0.5^(1/HL);  HL 60d vols, 250d correlations [A]
Ledoit-Wolf: Σ = δF + (1-δ)S;  factor model Σ = BΩB' + D (USD, ΔUS10y, MSCI World, BCOM, EM FX basket, EUR rates)
Non-synchronous closes: 3-day returns, or Σ = Σ_0 + Σ_1 + Σ_1'
ERC: w_i(Σw)_i equal;  HRP: d = sqrt(0.5(1-ρ)), cluster, recursive bisection (López de Prado 2016)
Risk: σ_p = sqrt(w'Σw); RC_i = w_i(Σw)_i/σ_p; factor share_f = β_f(Ωβ)_f/σ_p², β = B'w
Caps [A]: country ≤ 15%, LatAm ≤ 35%, USD factor ≤ 25%, EM factor ≤ 40%, net-duration cap; enforce by QP min ||w - w0||²
```

[J] Inverse-volatility weighting treats BRL, MXN, ZAR, COP and CLP as independent bets, but they share one EM factor. Use equal risk contribution (ERC) or factor-capped weights, and avoid full mean-variance optimisation.

**Volatility targeting.**
- [F] Cederburg, O'Doherty, Wang and Yan (2020, JFE, 103 strategies): volatility-managed portfolios "do not systematically outperform", owing to "structural instability in the underlying spanning regressions".
- [F] Harvey et al. (2018): negligible Sharpe effect in FX, bonds and commodities, but fewer extreme returns.
- [F] DeMiguel, Martín-Utrera and Uppal (2024, JF): multifactor volatility management survives OOS net of costs.
- [J] Keep the 10% target but put a floor under the volatility estimate, because carry crashes follow calm periods:

```
σ_est = max(σ_EWMA60, 0.8·σ_EWMA250);  gross leverage ≤ 6× [A]
```

**Tail risk.**
- VaR and ES by historical and filtered historical simulation.
- Replay these windows on current weights:
  - GFC (Sep–Oct 2008)
  - taper tantrum (22 May–24 Jun 2013)
  - CNY devaluation (10–25 Aug 2015)
  - Covid (20 Feb–23 Mar 2020)
  - 2022 hiking cycle (Jan–Oct)
  - yen unwind (24 Jul–5 Aug 2024; TOPIX −12% on 5 August, per BIS)
  - Brazil 2026 election day
- Hypothetical scenarios: USD +10% with VIX +20; US 10-year yield +150bp; EM FX −15% with correlations of 0.9; France spread +100bp.
- Limits [A]: worst replay loss ≤ 12% of NAV; daily ES(97.5%) ≤ 2.5%.

**Liquidity, margin and funding [J].**
- Set liquidity limits from BIS Triennial Survey turnover shares.
- Forwards and NDFs carry variation margin only; futures use SPAN initial margin; swaps are cleared; cash bonds are funded at repo.
- Paper return = instrument excess return + T-bill rate on cash. Keep initial margin ≤ 40% of NAV.

---

## 8. Instruments, execution and costs

| Market | Institutional instrument | Paper/retail access | Proxy |
|---|---|---|---|
| BRL | NDF; DI1 futures | CME BRL futures | 6L |
| MXN | Forwards; TIIE swaps; Mbonos | CME 6M | 6M; EM local-bond ETF |
| COP, CLP, PEN, INR, KRW, IDR, PHP, TWD, THB | NDF or restricted | No (small CME INR contract only) | Synthetic, research only |
| ARS | Capital controls | No | Exclude |
| ZAR, PLN, HUF, CZK, TRY | Deliverable forwards | CME ZAR; spot/CFD | Synthetic; flag TRY |
| G10 FX; DE/FR/IT/ES, UK, US, JP, AU, CA bonds | Forwards, futures | Yes (futures) | Futures |
| PT, GR, PL, HU, CZ, ZA, ID, IN, PH, TH bonds | Cash bonds / swaps | No | Synthetic from central-bank yields |
| Gold | COMEX GC/MGC | Yes | MGC |

**Costs [A].** These are unverified. Test at 0.5×, 1×, 2× and 3×, with 2× as the headline.

| Instrument | One-way cost | Stress multiplier |
|---|---|---|
| G10 forwards | 1–2bp | 3× |
| MXN, ZAR, PLN | 3–6bp | 4× |
| NDFs | 5–15bp | 5× |
| DM bond futures | 1–2bp | 2× |
| EM local bonds | 10–30bp | 4× |

Rolls cost 0.5× the one-way cost. Scale costs with volatility: cost_t = cost_normal × (1 + 2·max(0, σ_t/σ_med − 1)).

**Rebalancing [J].**
- Replace the 25% relative band with a band in risk units: trade only if |Δw_i|·σ_i > 0.1 × the position's risk budget.
- Trade partially for slow signals: w_new = w + 0.5(w* − w).
- Stagger rebalancing, one quarter of the book per week.
- Keep turnover costs to ≤ 0.5% of NAV a year.

---

## 9. Universe design

**Inclusion rules [J, pre-registered].**
1. At least 36 months of point-in-time data.
2. Floating or managed float under the IMF AREAER classification. Exclude:
   - hard pegs and currency boards (HKD, SAR, AED, BGN, the DKK peg);
   - crawling or multiple exchange rates (ARS);
   - onshore CNY as a carry long.
3. Halve the risk budget if the NDF–onshore basis exceeds 300bp for more than a month.
4. The currency must be in the BIS Triennial top 35.
5. A country enters at the first rebalance after it qualifies, with no backfill; its z-scores use history from entry only. On exit, close at the last tradable price with 3× costs.

[J] Adding more EM high-yielders diversifies only partly, because they share one risk factor (Menkhoff et al. 2012; BIS 2024). The regional risk cap is the control.

**Free-data screener.**
- A monthly table per country with:
  - carry, real carry, VAL_reer and economic momentum
  - current account, reserves / short-term debt and NFA
  - crash probability
  - next election (IFES ElectionGuide), next rating review and recent rating actions
- Flag any z-score that moves more than 1.5 in a month.
- Log discretionary trades as trials, each with a written thesis, size ≤ 2% risk and an exit rule.

---

## 10. Bond-specific methods

```
P = Σ CF_k/(1+y/f)^{f t_k};  D_mac = Σ t_k PV_k / P;  D_mod = D_mac/(1+y/f);  DV01 = D_mod·P·1e-4
ΔP/P ≈ -D_mod Δy + 0.5 C Δy²;  monthly excess return ≈ (y_{t-1} - rf)/12 - D_mod Δy + 0.5 C Δy²
Futures DV01 ≈ DV01_CTD/CF_CTD;  duration-neutral spread: N_DE = N_FR · DV01_FR/DV01_DE
PCA of daily yield changes (2/5/10/30y) → level, slope, curvature; PC1-neutral hedge Σ w_k V_{k,1} DV01_k = 0
NSS: y(τ) = β0 + β1·L(τ,λ1) + β2·[L(τ,λ1) - e^{-τ/λ1}] + β3·[L(τ,λ2) - e^{-τ/λ2}],  L = (1-e^{-τ/λ})/(τ/λ); Diebold-Li λ1 = 0.0609 (months)
```

- **PCA.** [F, widely replicated, not re-verified] The level factor explains roughly 80–90% of variance; the first three components explain 95–99%.
- **Term premium.** For the US, ACM (New York Fed) and Kim-Wright (Federal Reserve Board) estimates are free and daily. Elsewhere, estimate a simplified ACM on central-bank curves. [J] Use the term premium as a value input, not as a standalone timing signal.
- **Sovereign spreads.** The user's fair-value model failed. Spreads are dominated by risk appetite and backstops such as OMT (2012) and TPI (2022). [J] Use spread drivers for sizing only, and size rating actions with the user's in-sample estimates.
- **Breakevens.** BEI = y_nom − y_real. Sources: FRED, BoE, AFT/Banque de France, Tesouro (NTN-B) and Banxico (Udibonos). These feed VAL_realyld.

---

## 11. Gold and commodities

**Gold.**
- [F] The user's model: −4% per +1 point of US real yield, −0.85% per +1% move in the dollar, plus geopolitics. A drift since 2022 is likely tied to central-bank buying (WGC and IMF quarterly data).

```
gold_resid = Δlog Gold - (β_ry ΔTIPS10 + β_usd Δlog DXY)   (36-month rolling)
gold_signal = 0.5·TREND(gold) + 0.5·z(CB purchases 4q)  [J]
```

- The rejected gold event trades and geopolitical index are not re-proposed.
- [J] The book is already short USD, and gold's dollar beta adds to that exposure rather than hedging it. Size gold under the USD factor cap.

**Commodities.**

```
carry_c = (F1 - F2)/F2 · 12/(m2 - m1)
```

- [F] Koijen et al. (2018) find commodity carry among the strongest carry results by asset class (13.5% mean in the NBER version).
- [J] A commodity carry-and-trend sleeve in micro futures diversifies the book more than adding more EM FX. Free data are scarce; use AQR datasets as a research proxy.

---

## 12. Options overlays

```
Garman-Kohlhagen: C = S e^{-r_f T} N(d1) - K e^{-r_d T} N(d2);  P = K e^{-r_d T} N(-d2) - S e^{-r_f T} N(-d1)
d1 = [ln(S/K) + (r_d - r_f + σ²/2)T]/(σ√T);  d2 = d1 - σ√T
```

- [F] Daniel, Hodrick and Lu: "Hedging with options reduces but does not eliminate abnormal returns".
- [F] Kelly, Pástor and Veronesi: options spanning elections cost about 5% more at the money and about 16% more for 10% out-of-the-money puts, so event protection is systematically expensive.
- [J] Cut delta before events instead of buying event options, unless data show the options are underpriced. That test requires commercial implied-volatility history.

For synthetic backtests (quality C):

```
σ_impl ≈ σ_real_1m × 1.10 [A]; event months × 1.05 (ATM) / × 1.16 (10% OTM put); bid-ask 0.5 vol points G10, 1.5 EM [A]
```

---

## 13. Backtest engineering

| Bias | Automated test |
|---|---|
| Look-ahead and revisions | Assert available_date ≤ decision_date for every input; store first releases (ALFRED, OECD); report Sharpe on first-release vs latest data |
| Survivorship | No returns before a country's entry_date |
| Time zones and holidays | Per-market calendars; a common FX snapshot (e.g., ECB 14:15 CET reference rates); warn if lag-1 cross-correlation > 0.2 |
| Stale prices and bad ticks | Fail on more than 3 identical closes; quarantine moves larger than 8 median absolute deviations that reverse |
| Label leakage | Purge and embargo h months (López de Prado 2018) |

**Reproducibility.**
- `trials.csv` records id, date, hypothesis, code SHA, config hash, data hash, IS/walk-forward/holdout metrics and the decision. Every run appends to it automatically, and N is the count of distinct configs.
- Commit a pre-registration document before each run.
- Unit tests:
  - forward-return identity
  - DV01 against finite differences
  - risk contributions summing to σ_p
  - z-scores skipped when fewer than 5 countries are available

---

## 14. Live monitoring and decay

```
μ̂ = walk-forward mean haircut 50%; σ̂ from walk-forward
Z_T = Σ(r - μ̂)/(σ̂√T): alert if < -2;  drawdown > 95th pct of block bootstrap: alert
Sleeve CUSUM: S_t = max(0, S_{t-1} - (r - μ̂ + 0.5σ̂)); alarm at 5σ̂ (Page 1954)
Monthly live PSR; Frobenius distance of correlations; USD factor share
```

**Rules [A].**
- Halve a sleeve when its 24-month live Sharpe is below −0.5 **and** its CUSUM alarms.
- Pause it when the 36-month PSR falls below 0.2.
- Retire a sleeve only through a new pre-registered test.
- No changes based on fewer than 12 months of data.

---

## 15. What leading firms do

| Firm | Documented | Uncertain |
|---|---|---|
| AQR | Carry, value, momentum and defensive across asset classes (Koijen et al.; AMP; Ilmanen et al.; Hurst-Ooi-Pedersen); public datasets; actual trading costs about one-sixth of the 1880–1992 estimates (etf.com summary) | Live returns by sleeve. Style Premia Alternative reportedly lost 12.3%, 8.1% and 21.9% in 2018–2020 (secondary source) |
| Man AHL | Trend-following since 1987; published research on volatility targeting, time-series vs cross-sectional signals, and trend drawdowns. AHL Trend Alternative −12.77% year to date at October 2024 (Hedgeweek) | Signal mix |
| Bridgewater | All Weather and growth/inflation quadrants, in its own publications | Pure Alpha methods |
| Winton, Millburn, Graham; Two Sigma, Renaissance | CTAs; data-driven (Medallion is short-horizon) | Mostly proprietary or legend |
| Multi-manager platforms; Soros, Duquesne, Tudor, Brevan Howard | Pods with tight stops for each portfolio manager (widely reported); the 1992 GBP trade is well documented | Specific levels and methods are anecdotal |

[J] What transfers is breadth, risk-budgeted sleeves, cost discipline and drawdown governance, not secret signals.

---

## 16. Data sources

| Input | Source | Frequency / history | Notes [J: verify reachability from the cloud] |
|---|---|---|---|
| Spot FX | FRED H.10, ECB, Banxico SIE, BCB SGS | Daily, 1971+ | Usually reachable |
| Forwards / NDF | Mostly commercial | — | Gap; synthetic, quality C |
| Rates, yields, curves | BIS; OECD MEI (monthly); Bundesbank, Banco de España, Banco de Portugal, NBB, BoE, US Treasury, Fed GSW, BoC, Banxico, Tesouro (daily) | Decades | ECB publishes no daily 10-year country yields |
| Macro | OECD MEI, IMF IFS, national statistics offices; ALFRED vintages | Monthly | Revised |
| REER | BIS | Monthly, 1994+ | Good |
| External accounts | IMF BOP/IIP/IFS; World Bank QEDS | Quarterly | 1–2 quarter lag |
| Forecasts | IMF WEO vintages | Semi-annual | Use vintage files |
| Positioning | CFTC COT | Weekly, 1986+ | Good |
| VIX, high yield, TIPS, broad USD, term premia | FRED; NY Fed ACM; Fed Board Kim-Wright | Daily | Good |
| Factor returns | AQR datasets; Kenneth French library | Monthly | Benchmarks for decay |
| Elections; gold | IFES; LBMA, WGC | Event; daily/quarterly | Manual |
| EM daily yields | investing.com exports | Daily | Blocked from the cloud; manual export; run quality checks |

---

## 17. Implementation roadmap

### 17.1 Ranked modifications

ΔSR is judgement. Evidence grades: A = multiple peer-reviewed sources; B = peer-reviewed, in-sample; C = practitioner or own data.

| # | Modification | ΔSR [J] | ΔDrawdown | Evidence | Cost |
|---|---|---|---|---|---|
| 1 | P&L attribution | diagnostic | — | — | Low |
| 2 | Risk-contribution audit | diagnostic | — | — | Low |
| 3 | Trial ledger with DSR and MinTRL | 0 | — | A | Low |
| 4 | Carry-crash filter | 0 to +0.1 | ES −20 to −30% | B | Medium |
| 5 | Factor/country caps with ERC/HRP sizing | +0.05 to +0.15 | −15% | B | Medium |
| 6 | Time-series trend blend | +0.05 | crisis convexity | A | Low |
| 7 | Real-yield bond value; term-spread bond carry | +0.05 to +0.1 | — | B | Low |
| 8 | REER value; value as carry conditioner | 0 to +0.05 | −10% | B | Low |
| 9 | Economic momentum | +0.05 to +0.15 | — | B | Medium |
| 10 | Dollar-neutral core plus dollar sleeve | 0 to +0.05 | −10% | B | Low |
| 11 | Risk-budgeted sleeves; rank weighting | 0 to +0.05 | — | B | Low |
| 12 | Election protocol | small | smaller event losses | C | Low |
| 13 | Volatility floor and leverage cap | 0 | thinner tails | B | Low |
| 14 | Regime-dependent costs, 2× headline | negative (honest) | — | C | Low |
| 15 | Commodity carry and trend | +0.05 to +0.1 | diversification | B | Medium |

### 17.2 First builds

**Build 1: attribution.**

```
P&L_{i,t} = w_{i,t-1} r_{i,t} - cost;  signal share_k = (z_k/K)/S if |S|>0.1 else 1/K;  exact: Shapley over 2^K sleeve subsets
Factor regression on DXY, ΔUS2y, ΔUS10y, MSCI World, BCOM, EM FX basket, ΔVIX
```

[J] If BRL and MXN together account for more than 50% of P&L, Build 5 becomes urgent.

**Build 2: risk audit.** Compute risk contributions RC_i and factor shares monthly for 2005–2026, using Ledoit-Wolf on 3-day returns. If the average combined USD and EM factor share is above 60%, the book is effectively one bet.

**Build 3: statistics.**

```python
def psr(sr, T, g3, g4, s0=0): return norm.cdf((sr-s0)/np.sqrt((1-g3*sr+(g4-1)/4*sr**2)/(T-1)))
def sr0(N, sd): g=0.5772156649; return sd*((1-g)*norm.ppf(1-1/N)+g*norm.ppf(1-1/(N*np.e)))
def min_trl(sr, g3, g4, c, s0=0): return 1+(1-g3*sr+(g4-1)/4*sr**2)*(norm.ppf(c)/(sr-s0))**2
def haircut_bonf(sr, yrs, M):
    p=2*(1-norm.cdf(sr*np.sqrt(yrs))); return norm.ppf(1-min(1,M*p)/2)/np.sqrt(yrs)
```

**Build 4: crash filter.** As specified in §6.2. [J] Expect a 20–30% cut in carry ES, based on Jordà-Taylor's 2008 offset and Amundi's −3.8% vs −6.75%. It overlaps with #8 and #13, so test #4 first and then #8 with #4 in place.

**Build 5: sizing.**

```python
def size(scores, Sigma, caps, tv=0.10, lev=6.0):
    w = enforce_caps(erc_weights(Sigma, np.sign(scores), np.abs(scores)), Sigma, caps)
    w *= tv/np.sqrt(w @ Sigma @ w)
    return w * min(1, lev/np.abs(w).sum())
```

Pass if ΔSR ≥ 0 and maximum drawdown falls by at least 10%.

**Builds 6–15** follow §§1–12. Each needs a pre-registration document, an increment to N, the 2020–2026 walk-forward, the half-B holdout and the §0.3 pass rule.

### 17.3 Architecture and order

```
data/      loaders (FRED, BIS, OECD, IMF, ECB, CBs, CFTC, manual CSV), vintage store, calendars, QA, universe table
signals/   carry_fx, carry_bond, value_fx, value_bond, trend_ts, econ_mom, crash_prob, event_calendar
combine/   sleeves (CS rank-weighted; TS trend), risk budgets, conditioning, dollar neutraliser + dollar sleeve
risk/      EWMA/LW covariance (sync-corrected), ERC/HRP, factor model, caps, vol floor, leverage cap, stress replay, ES limits, DD governor
execution/ instrument mapper, regime costs, risk-unit bands, staggered rebalancing, synthetic NDF/bond returns
monitor/   live vs expected, CUSUM, live PSR, factor shares, trial ledger, results table
```

**Build order.**
1. Data quality checks.
2. Builds 1–3.
3. Builds 4 and 5 (Build 5 first if the Build 2 alarm fires).
4. Builds 6–8.
5. Builds 10–11.
6. Build 9.
7. Builds 12–14.
8. Build 15.

If v2.0 is not frozen by 3 November 2026, run v1.0 frozen live and start v2 on a pre-announced date.

### 17.4 Open questions

| Question | Why the evidence is weak | What would resolve it |
|---|---|---|
| Has FX carry decayed? | Ilmanen et al. conflict with Hsu et al. and Hutchinson et al. | Compute the 2012–2026 FX carry Sharpe from AQR data and compare with 1983–2011 |
| What is the economic-momentum Sharpe? | "About one" vs 0.70; sample ends before 2018 | Rebuild on OECD vintages and test OOS on 2018–2026 |
| Are EM election options overpriced? | KPV show they are dearer, not that they are overpriced once outcomes are counted | Commercial implied-volatility history |
| Does the election rule hold? | Only 9 OOS events | Reconstruct 2000–2026 elections; collect at least 30 live |
| Is hedged EM local-bond carry real? | Sparse data; NDF basis | Synthetic returns compared with EM local-bond ETFs |
| What do NDFs really cost? | No verified free data | Log broker quotes during live trading |

---

## Caveats

- **Unchecked citations.** Results marked "not re-verified" (Rogoff 1996, DeMiguel et al. 2009, Moreira-Muir 2017, Du-Tepper-Verdelhan 2018, Erb-Harvey 2013, Litterman-Scheinkman, the early-warning papers) are cited from the literature without being checked in this session. Confirm them before pre-registering.
- **Assumptions.** All cost figures and most thresholds are [A] and need sensitivity tests.
- **No peer-reviewed 2020s data.** I found no peer-reviewed 2020–2026 Sharpe ratios for FX or bond factors. Practitioner sources (Mackenzie 2023, Bloomberg-based) say FX carry "has outperformed in the last two years" and that FX value was weak in 2022–2023, which fits the user's own result. Compute these from AQR data before relying on them.
- **Missing magnitudes.** The size of the post-publication decline in Hsu, Li, Taylor and Wang (2025) and the per-asset-class Sharpe ratios in Ilmanen et al. (2021, Table II) could not be extracted.

---

## Appendix A: Formula sheet

```
FX return: r = (S_{t+1} - F_t)/F_t;  carry = (S - F)/F · 12/m;  real carry = carry - (π^e_i - π^e_US)
Bond carry: (y_n - r_f) + D_mod (y_n - y_{n-Δ})/Δ;  hedged: + (r_US - r_i)
Bond return: (y_{t-1} - rf)/12 - D_mod Δy + 0.5 C Δy²;  DV01 = D_mod P 1e-4
TSMOM: sign(Σr) σ_target/σ;  EWMAC: (EMA_f - EMA_s)/σ_price
Value: -(q_t - q_{t-60}), q = s + p_US - p_i;  REER: -(log REER - rolling mean);  real yield: y10 - π^e
Debt: Δd = (r - g)/(1+g) d - pb;  crash label: min cum r^x ≤ -2σ√(h/12);  logit p = 1/(1 + e^{-(α + x'β)})
RC_i = w_i(Σw)_i/√(w'Σw);  EWMA λ = 0.5^(1/HL);  LW: δF + (1-δ)S;  VaR = -q_{1-α};  ES = -E[R | R ≤ -VaR]
Garman-Kohlhagen: C = S e^{-r_f T}N(d1) - K e^{-r_d T}N(d2)
PSR = Φ((SR - SR*)√(T-1)/√(1 - γ3 SR + (γ4-1)/4 SR²));  SR0 = sd(SR_n)[(1-γe)Φ^-1(1-1/N) + γe Φ^-1(1-1/(Ne))]
MinTRL = 1 + (1 - γ3 SR + (γ4-1)/4 SR²)(z/(SR - SR*))²;  Bonferroni: SR_adj = Φ^-1(1 - min(1,Mp)/2)/√T
Kelly: f* = p - (1-p)/b;  event size = 0.5 × 0.25 × f*
```

## Appendix B: Data dictionary

| Variable | Source | Frequency | Lag |
|---|---|---|---|
| S, F | FRED/ECB/central banks; synthetic | Daily | 0 |
| y3m, policy rate, y2, y10 | BIS/OECD/central banks/manual | Daily/monthly | 0 / 1 month |
| CPI, industrial production, retail sales, unemployment | OECD/IFS | Monthly | 1–2 months |
| π^e, fiscal variables | WEO vintages; breakevens | Semi-annual/daily | Vintage date |
| REER | BIS | Monthly | 1 month |
| Current account, NFA, reserves/short-term debt | IMF BOP/IIP/IFS; QEDS | Quarterly | 1–2 quarters |
| COT | CFTC | Weekly | 3 days |
| VIX, high yield, USD, TIPS10; ACM | FRED; NY Fed | Daily | 0; ~1 week |
| Gold; central-bank purchases | LBMA/CME; WGC | Daily; quarterly | 0; 1–2 months |
| Elections; ratings | IFES/archived polls; agencies | Event | Pre-event archive date; 0 |

## Appendix C: References

- Adrian, Crump, Moench (2013), JFE.
- Aquilina, Lombardi, Schrimpf, Sushko (2024), BIS Bulletin 90.
- Asness, Moskowitz, Pedersen (2013), JF 68(3).
- Bailey, López de Prado (2012), J. Risk; (2014), JPM 40(5).
- Bailey, Borwein, López de Prado, Zhu (2017), J. Computational Finance.
- Baz, Granger, Harvey, Le Roux, Rattray (2015), SSRN 2695101.
- BIS Quarterly Review (September 2024), "Carry off, carry on".
- Brunnermeier, Nagel, Pedersen (2008), NBER Macroeconomics Annual 23.
- Cederburg, O'Doherty, Wang, Yan (2020), JFE 138.
- Chen, Zimmermann (2022), arXiv 2209.13623.
- Dahlquist, Hasseltoft (2020), JFE 136(1).
- Daniel, Hodrick, Lu (2017), Critical Finance Review 6.
- Della Corte, Riddiough, Sarno (2016), RFS 29(8).
- DeMiguel, Garlappi, Uppal (2009), RFS.
- DeMiguel, Martín-Utrera, Uppal (2024), JF.
- Du, Tepper, Verdelhan (2018), JF.
- Erb, Harvey (2013), FAJ.
- Fan (2025), Financial Review.
- Garman, Kohlhagen (1983), JIMF.
- Harvey, Liu (2015), JPM.
- Harvey, Liu, Zhu (2016), RFS.
- Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert (2018), JPM 45(1).
- Hsu, Taylor, Wang (2024), JIMF 143.
- Hsu, Li, Taylor, Wang (2025), J. Empirical Finance 83.
- Hurst, Ooi, Pedersen (2017), AQR/JPM.
- Hutchinson, Kyziropoulos, O'Brien, O'Reilly, Sharma (2022), IRFA 83.
- Ilmanen, Israel, Lee, Moskowitz, Thapar (2021), JOIM.
- Jordà, Taylor (2012), JIE 88.
- Kelly, Pástor, Veronesi (2016), JF 71(5).
- Koijen, Moskowitz, Pedersen, Vrugt (2018), JFE 127.
- Korgaonkar (2025), Man Group.
- Ledoit, Wolf (2004), JPM.
- López de Prado (2016), JPM; (2018), Advances in Financial Machine Learning.
- Lustig, Roussanov, Verdelhan (2011), RFS; (2014), JFE.
- McLean, Pontiff (2016), JF.
- Menkhoff, Sarno, Schmeling, Schrimpf (2012), JF 67(2) and JFE 106(3).
- Moreira, Muir (2017), JF.
- Moskowitz, Ooi, Pedersen (2012), JFE 104(2).
- Nelson, Siegel (1987), J. Business.
- Rogoff (1996), JEL.
- Svensson (1994), NBER WP 4871.
