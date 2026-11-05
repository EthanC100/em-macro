# Pre-registration — trials T20–T22: commodity carry, basis-momentum and diversified futures trend against frozen v1.1

| item | value |
|---|---|
| trials | **T20** commodity carry (de-seasonalised 12-month carry, cross-sectional, monthly); **T21** basis-momentum (cross-sectional, monthly); **T22** time-series trend following across a diversified futures universe (commodities plus v1.0's currencies and bonds where futures exist). Ledger ids `T20`–`T22` in `trials.csv` (free ids; the last ledger row is T19), trial groups `G19_commodity_carry`, `G20_basis_momentum`, `G21_diversified_futures_trend`. |
| family | The three trials are **one family** for multiple testing (§5): Holm correction of the three bootstrap p-values, deflated Sharpe at N = 16. Each trial is **v1.1 plus one sleeve**, tested separately against v1.1. **No combination of sleeves is tested**; the carry + basis-momentum composite (commodities spec §11, Build 3) and any T22 combination are future pre-registered trials. |
| branch | `prereg/commodity-trials` (this document and the ledger rows). Build 0, the trial code and the runs go on a later branch, `trial/T20-T22-commodity`. |
| baseline | **v1.1** (`docs/v1.1_freeze.md`): frozen v1.0 (tag `v1.0-frozen` = `7886867`, `em_macro/systematic.py` SHA-256 `1eb4cf6b…50be66`) plus exactly the T18 rule (`em_macro/systematic_v11.py` SHA-256 `b3c4404e…885952`, `em_macro/t18_rebal.py` SHA-256 `dda6456d…0f96c43`). v1.0 remains the frozen control and v1.1 the live comparison; **no v1.0 or v1.1 file is modified**. New code goes in new modules only (`em_macro/commod_data.py`, `commod_sleeves.py`, `t2022.py`, `t2022_report.py`, or similar names under `em_macro/`). |
| written | 2026-11-04, **before any commodity data exists in this repository**. The session that wrote it downloaded, opened and computed nothing from commodity prices. Committed on its own; the ledger rows follow in a second commit. |
| spec | `docs/research/commodities_spec_2026-11.md` ("the commodities spec"): §1 universe, §2 continuous series and rolling, §3 signals, §6 integration, §7 risk, §8 costs, §9 data, §11 build plan. `docs/research/algorithm_spec_2026-11.md` ("the algorithm spec"): §0.2 statistics, **§0.3 four-stage test and pass rule**, §0.4 honest reporting, §2.2 trend criterion, §13 pre-registration. |
| what has been seen | v1.0's and v1.1's committed results, the T01, T02 and T16–T19 reports, the two specs and the literature they summarise. **No commodity return, curve, carry, basis-momentum, trend signal, correlation or sleeve statistic has been computed.** |
| gate | Nothing in §3 or §4 is run until every Build 0 acceptance test in §6 has passed and the Build 0 report is committed. |

v1.0's figures stay labelled "OOS for v1.0 only" and v1.1's "T18's single test, OOS for v1.1 only". Each trial's figures
are reported separately and never merged with either track record (algorithm spec §0.4).

## 1. Hypotheses and evidence (algorithm spec §0.3(a))

| trial | hypothesis | published evidence recorded (sample, asset class) | spec prior |
|---|---|---|---|
| T20 commodity carry | Adding a cross-sectional, monthly-rebalanced sleeve that is long high-carry and short low-carry commodity futures, with carry measured over the 12-month curve to remove seasonality, at a 25% risk budget, improves v1.1's risk-adjusted return after costs out of sample. | Koijen, Moskowitz, Pedersen and Vrugt (2018, JFE; commodities 1980s–2012, IS): commodity carry Sharpe 0.60 against 0.08 for the equal-weight long portfolio; carry1–12 about 0.65 (NBER version). Gorton, Hayashi and Rouwenhorst (2013, RoF; 31 commodities 1969–2006): the basis is a declining, convex function of inventories and high-basis portfolios earn more. Erb and Harvey (2006); Gorton and Rouwenhorst (2006). Ilmanen et al. (2021): carry robust out of sample across asset classes. Geczy and Samonov: basis exists in 1877–1959, smaller, with an early −83% drawdown. | Commodities spec §3.2, §11 row 1: net Sharpe 0.25–0.35 after a roughly 50% haircut. Algorithm spec §17.1 #15: ΔSR +0.05 to +0.1, evidence B. |
| T21 basis-momentum | Adding a cross-sectional, monthly sleeve that is long commodities whose first-nearby contract has outperformed its second-nearby over the past 12 months and short the reverse, at a 25% risk budget, improves v1.1's risk-adjusted return after costs out of sample. | Boons and Porras Prado (2019, JF; commodities ~1959–2014, IS; author-maintained OOS to December 2025, not independently verified): basis-momentum outperforms basis and momentum in the time series and the cross-section, is priced, and survives controls for basis, momentum and volatility. Jiang and Liu: factor Sharpe 0.43 from 1985. Factor-structure literature (commodities spec §3.4): basis-momentum among four latent priced factors. | Commodities spec §11 row 2: Sharpe 0.2–0.35 net; correlation with carry 0.2–0.4. |
| T22 diversified futures trend | Adding a time-series momentum sleeve in the Moskowitz–Ooi–Pedersen / Hurst–Ooi–Pedersen form across a diversified futures universe (24 commodity, 5 currency and 5 bond futures), at a 25% risk budget, improves v1.1's risk-adjusted return after costs out of sample, and is negatively correlated with v1.0's carry sleeve in carry's worst months. | Moskowitz, Ooi and Pedersen (2012, JFE; 58 futures and forwards including 24 commodities, 1965–2009, IS): time-series momentum significant in every instrument, 12-month lookback, positions scaled to 40% ex-ante volatility, equal-weighted across instruments. Hurst, Ooi and Pedersen (2017, JPM; 67 markets, 29 commodities, 1880–2016): equal-weighted 1-, 3- and 12-month trend, positive in every decade, Sharpe 0.77 net of estimated costs, positive in 8 of the 10 largest 60/40 drawdowns. Harvey et al. (2018): volatility scaling has a negligible Sharpe effect but thins the tails. | Commodities spec §3.3 [J]: because the programme's FX/bond trend tests failed, **do not add commodity trend as a standalone sleeve**; test it as a pre-registered secondary trial. Algorithm spec §17.1 #6: TS trend ΔSR +0.05; #15 commodity carry and trend +0.05 to +0.1. The prior for T22 is therefore the lowest of the three. |

**Expected size of the gain, before any data (commodities spec §6.2).** For two sleeves with Sharpe S1 and S2 and
correlation ρ, S_comb² = (S1² + S2² − 2ρS1S2)/(1 − ρ²), and adding sleeve 2 helps only if S2 > ρ·S1. With v1.1 at
S1 = 0.92 (its 2020-01..2026-09 test), a haircut sleeve at S2 = 0.30 and ρ = 0.1, S_comb ≈ 0.94: an improvement of
about +0.03, and the optimal risk share at those values (w2/w1 = (S2 − ρS1)/(S1 − ρS2)) is about 19%, so the 25%
budget is slightly above the optimum. **Honest statement of power:**
over 81 months a ΔSR of that size cannot be distinguished from zero by the block bootstrap (T01's ΔSR of +0.15 had
p = 0.26), so the most likely outcome under the spec's own priors is that the sleeves fail criterion 1 even if
the published effects are real. The rule is kept as the task fixes it; the sleeve-level criteria (§4.2) record
whether the effect itself reproduces, independently of the combined test.

### 1.1 Why T22 is a different hypothesis from the programme's failed trend tests

**What failed.** v1.0's cross-sectional trend signal (average of 12- and 3-month return z-scores, ranked within
the FX and bond books) had a Shapley contribution of −6.5% a year in 2005–2019 and −0.1% a year in 2020-01..2026-09
(`results/diagnostics_v1.md`). The pre-registered T01 (`docs/prereg/T01_ts_trend.md`, `results/T01_ts_trend.md`;
ledger T12) replaced it with a time-series trend sleeve on v1.0's **23 FX and bond instruments** — the algorithm
spec's §2.2 continuous blend (clipped k-month return over σ√(k/12), k ∈ {1, 3, 6, 12}) at 20% of risk — and
**failed 3 of 5 criteria**: ΔSR +0.15 with bootstrap p 0.26; holdout ΔSR −0.09; and a correlation of **+0.54** with
the carry sleeve in carry's worst eight months, where the spec required a negative one. The trend sleeve on its own
had Sharpe 0.03 in 2020-01..2026-09 and −0.19 in 2006–2019.

**Why T22 is not the same test.**
1. **Different universe, where the evidence is.** T01's instruments were 10 currencies (7 of them emerging) and 13
   bond and spread positions built from monthly-average yields, 9 of them without daily prices. The published
   time-series momentum evidence is for exchange-traded futures across asset classes, with commodities the largest
   block (24 of MOP's 58 instruments, 29 of HOP's 67). T22 trades that kind of universe: 24 commodity futures and
   10 financial futures with daily settlement prices, true futures excess returns and real roll costs.
2. **The literature's own specification, not a variant.** T22 uses MOP's sign-of-past-return positions scaled to
   equal ex-ante volatility with a 60-day EWMA, HOP's equal blend of 1-, 3- and 12-month horizons, and MOP's equal
   weighting across instruments. T01 used the algorithm spec's continuous clipped blend with a 6-month horizon
   added and a monthly EWMA approximation forced by the lack of daily data. No parameter of T22 is taken from T01.
3. **The economic claim is breadth, not FX or bond trend.** T22 does not assume that trend works in EM currencies
   or local bonds on their own; the hypothesis is that a diversified trend portfolio, whose return comes mostly
   from commodity futures and from low correlations across three asset classes, adds to v1.1. The FX and bond
   futures are kept because the literature's diversified portfolio includes them and because the task fixes the
   universe as "commodities plus v1.0's currencies and bonds where futures exist".
4. **The same crisis criterion that T01 failed is kept.** T22 must have a correlation below zero with v1.0's carry
   sleeve in carry's worst 10% of months (§4.2). T22 cannot pass by the route T01 failed.

**What is not claimed.** T01's result lowers the prior for T22's currency and bond legs, and the commodities spec's
judgement (§3.3) is against standalone commodity trend. T22 is the "pre-registered secondary trial" that spec asks
for, run once, with its outcome recorded whatever it is.

## 2. Common framework (fixed)

### 2.1 Universe

**Commodity markets (24).** The exchange-traded, monthly-listed markets of the commodities spec's table (§1.1),
i.e. all of its rows except the four LME metals (daily prompt dates, not standard monthly futures; paid history; LME
nickel excluded outright by §7). Contract sizes and tick values are from exchange specifications as commonly
published and are **re-verified against the current CME and ICE specification pages in Build 0**; a correction to a
multiplier, tick, roll calendar or notice date is a data fact, not a trial change, and is logged in the Build 0 report.

| # | market | symbol | exchange | sector (holdout stratum) | designated contract months (roll calendar) | full contract | tick (USD per contract) | slippage ticks per side |
|---|---|---|---|---|---|---|---|---|
| 1 | WTI crude | CL | NYMEX | energy | all 12 | 1,000 bbl | 0.01 = 10 | 1 |
| 2 | Brent crude | B | ICE Europe | energy | all 12 | 1,000 bbl | 0.01 = 10 | 1 |
| 3 | RBOB gasoline | RB | NYMEX | energy | all 12 | 42,000 gal | 0.0001 = 4.20 | 1 |
| 4 | Heating oil / ULSD | HO | NYMEX | energy | all 12 | 42,000 gal | 0.0001 = 4.20 | 1 |
| 5 | Natural gas | NG | NYMEX | energy | all 12 | 10,000 MMBtu | 0.001 = 10 | 1 |
| 6 | Gasoil | G | ICE Europe | energy | all 12 | 100 t | 0.25 = 25 | 1 |
| 7 | Copper | HG | COMEX | industrial metals | H K N U Z | 25,000 lb | 0.0005 = 12.50 | 1 |
| 8 | Gold | GC | COMEX | precious metals | G J M Q V Z | 100 oz | 0.10 = 10 | 1 |
| 9 | Silver | SI | COMEX | precious metals | H K N U Z | 5,000 oz | 0.005 = 25 | 1 |
| 10 | Platinum | PL | NYMEX | precious metals | F J N V | 50 oz | 0.10 = 5 | 1 |
| 11 | Palladium | PA | NYMEX | precious metals | H M U Z | 100 oz | 0.10 = 10 | 1 |
| 12 | Corn | ZC | CBOT | grains and oilseeds | H K N U Z | 5,000 bu | 0.25c = 12.50 | 1 |
| 13 | Soybeans | ZS | CBOT | grains and oilseeds | F H K N Q U X | 5,000 bu | 0.25c = 12.50 | 1 |
| 14 | Wheat (SRW) | ZW | CBOT | grains and oilseeds | H K N U Z | 5,000 bu | 0.25c = 12.50 | 1 |
| 15 | KC wheat (HRW) | KE | CBOT | grains and oilseeds | H K N U Z | 5,000 bu | 0.25c = 12.50 | 1 |
| 16 | Soybean meal | ZM | CBOT | grains and oilseeds | F H K N Q U V Z | 100 short t | 0.10 = 10 | 1 |
| 17 | Soybean oil | ZL | CBOT | grains and oilseeds | F H K N Q U V Z | 60,000 lb | 0.0001 = 6 | 1 |
| 18 | Sugar No. 11 | SB | ICE US | softs | H K N V | 112,000 lb | 0.0001 = 11.20 | 2 |
| 19 | Coffee C | KC | ICE US | softs | H K N U Z | 37,500 lb | 0.0005 = 18.75 | 2 |
| 20 | Cocoa | CC | ICE US | softs | H K N U Z | 10 t | 1 = 10 | 2 |
| 21 | Cotton No. 2 | CT | ICE US | softs | H K N V Z | 50,000 lb | 0.0001 = 5 | 2 |
| 22 | Live cattle | LE | CME | livestock | G J M Q V Z | 40,000 lb | 0.00025 = 10 | 2 |
| 23 | Feeder cattle | GF | CME | livestock | F H J K Q U V X | 50,000 lb | 0.00025 = 12.50 | 2 |
| 24 | Lean hogs | HE | CME | livestock | G J K M N Q V Z | 40,000 lb | 0.00025 = 10 | 2 |

- **Cross-sectional sleeve universe (T20, T21): the 22 markets above excluding gold and silver** (commodities
  spec §5 item 1: their curves price financing and lease rates and carry no scarcity information; the task fixes
  the exclusion as gold and silver). This is the spec's "22 markets" (28 table rows − 4 LME − gold − silver).
  Platinum and palladium stay in, subject only to the data rules below (decision 3, §8).
- **T22 commodity block: all 24**, gold and silver included (trend is a price signal, not a curve signal).
- Within-sector breadth is deliberately not expanded (spec §1.1: diversification comes from sectors, not from more
  contracts within one).

**T22 financial futures (10).** v1.0's currencies and bond instruments "where futures exist", read with the
algorithm spec's §8 instrument table (CME futures for BRL, MXN, ZAR and the G10; exchange-traded futures for
DE/FR/IT/ES and UK bonds; none for TRY, IDR, PLN, COP, CLP or any EM local bond):

| # | v1.0 instrument | future | exchange | designated months | contract | tick | slippage ticks |
|---|---|---|---|---|---|---|---|
| 25 | EUR | 6E euro FX | CME | H M U Z | EUR 125,000 | 0.00005 = 6.25 | 1 |
| 26 | GBP | 6B British pound | CME | H M U Z | GBP 62,500 | 0.0001 = 6.25 | 1 |
| 27 | MXN | 6M Mexican peso | CME | H M U Z | MXN 500,000 | 0.00001 = 5 | 1 |
| 28 | BRL | 6L Brazilian real | CME | all listed months | BRL 100,000 | 0.00005 = 5 | 2 |
| 29 | ZAR | 6Z South African rand | CME | H M U Z | ZAR 500,000 | per exchange spec | 2 |
| 30 | DE10Y | FGBL Euro-Bund | Eurex | H M U Z | EUR 100,000 | 0.01 = EUR 10 | 1 |
| 31 | FR-DE (outright leg) | FOAT Euro-OAT | Eurex | H M U Z | EUR 100,000 | 0.01 = EUR 10 | 1 |
| 32 | IT-DE (outright leg) | FBTP Euro-BTP | Eurex | H M U Z | EUR 100,000 | 0.01 = EUR 10 | 1 |
| 33 | ES-DE (outright leg) | FBON Euro-Bono | Eurex | H M U Z | EUR 100,000 | 0.01 = EUR 10 | 1 |
| 34 | GB-DE (outright leg) | R Long Gilt | ICE Europe | H M U Z | GBP 100,000 | 0.01 = GBP 10 | 1 |

T22's bond legs are the **outright** 10-year futures, not v1.0's spreads over the Bund: MOP and HOP trade outright
futures, and no spread future exists (decision 11). The lean "where futures exist" test is: a listed, exchange-traded
future on the same underlying, in the vendor's database, with at least 12 months of daily settlements before a
decision date (entry rule below). Non-USD contracts are converted to USD at the day's exchange rate (the vendor's or
FRED's series) for notional, P&L and costs.

**Entry, dropping and missing-data rules (fixed now).**
1. **Coverage gate (per market, decided once in Build 0).** F1/F2 coverage = the share of monthly decision dates
   from the later of 2000-01 and the market's entry date to 2026-09 on which both the F1 and the F2 contract chosen
   by the roll rule (§2.3) have a settlement price on the decision date. A market with coverage **below 95%** is
   **dropped from every trial** and listed in the Build 0 report. This is the rule for "insufficient data".
2. **Entry.** A market enters at the first rebalance on or after which it has **12 months of daily settlements**
   for the F1 series (needed by every volatility estimate and 12-month lookback); no backfill; its history before
   entry is not used for any signal (algorithm spec §9 rule 5). A contract series replaced by a successor (unleaded
   gasoline → RBOB in 2005–06, heating oil → ULSD in 2013, gasoil → low-sulphur gasoil in 2015) is treated as one
   market where the vendor's metadata splices the series; otherwise the market re-enters 12 months after the
   successor's first settlement. Which applies is recorded in Build 0.
3. **Monthly missing values.** If on a decision date a market's signal, F13 (T20 Option A) or σ is missing, its
   weight is 0 that month and the cross-sectional rank is taken over the markets that have a value. If fewer than
   **6 markets** are active, the sleeve holds no positions that month (the half-universe holdouts have 11 markets).
4. **Daily gaps.** A missing settlement for a held contract carries the last settlement forward (zero return that
   day) and is flagged; the gap's return is realised on the next available settlement. More than 5 consecutive
   missing days for a held contract is a Build 0 data-quality failure for that market (§6).
5. **Exit.** Only on delisting, at the last available settlement, with 3× the one-way cost (algorithm spec §9).

### 2.2 Data

| role | source | use |
|---|---|---|
| primary, all markets | **Norgate Data Futures package** (individual contracts including expired ones, close = settlement, FND/LTD metadata, ~1980 or first trading day to date) | every settlement series, contract calendar and notice date used by the trials |
| cross-check from 2010-06-06 | **Databento** (CME Globex MDP 3.0 daily OHLCV: CME, CBOT, NYMEX, COMEX contracts) | Build 0 test A5: F1/F2 settlements must agree with the primary source; ICE and Eurex markets are cross-checked against Databento's ICE/Eurex datasets where the free credit covers them, else by Barchart spot checks (at least 12 dates per market) |
| external benchmarks | AQR data library: *Commodities for the Long Run* index data; *Century of Factor Premia* monthly commodity factors | Build 0 tests A3 and A4 (correlations only) |
| funding, FX, VIX, S&P 500 | the programme's existing loaders (FRED) | USD conversion of non-USD contracts; the §7 correlation diagnostics; no commodity signal uses them |
| v1.1's inputs | v1.0's `data/processed` snapshots at the freeze commit `7886867` plus the raw cache kept in `data/kept/T16-T19/` (the inputs on which v1.1 reproduces T18 exactly) | the baseline and the combined book |

- **Spec note and fallback (decision 12).** The commodities spec's programme note (§9) chose Pinnacle Deep History
  plus Databento because Norgate's updater is Windows-only. The task names Norgate as primary; this document follows
  the task. If the Norgate package cannot be obtained or run for the trial, **Pinnacle Deep History** takes the
  primary role with the identical acceptance tests, and the substitution is recorded in the Build 0 report before any
  signal is computed. It is not a trial.
- **Downloads happen in Build 0 only**, and Build 0 computes no strategy statistic (§6, A8). The raw files used are
  archived with a manifest under the raw-data rule (`docs/raw_data_archive.md`); because vendor licences forbid
  redistribution, the archive itself is stored privately and only the manifest and SHA-256 hashes are committed
  (decision 13).

### 2.3 Continuous series, roll rule, returns and timing (commodities spec §2)

**Rebalance timing.** Positions are rebalanced monthly on the **3rd** of each month (the programme's rebalance
date). For market i, the **execution date** is i's first settlement date on or after the 3rd, and the **decision
date** t is i's last settlement date before the execution date (spec §1.3: "use settlements of the prior business
day"; never mix a London close with a Chicago close). All signals use settlements up to and including t; positions
are entered at the execution date's settlement and held to the next execution date.

**Roll rule (spec §2.2, the 35-day buffer; one rule, never switched).** At each decision date, with
`notice(T)` = the earlier of contract T's first notice date and last trade date (last trade date only for
cash-settled contracts: Brent, feeder cattle, lean hogs):

```
F1(i, t) = the earliest contract T in i's designated calendar (table above) such that
           notice(T) > execution_date + 35 calendar days
F2(i, t) = the next contract after F1 in the designated calendar
```

The chosen contract is held until the next execution date. Because the holding period is at most 31 days plus the
execution lag, a held contract is never inside its last 10 trading days (spec §7) and never enters a notice period.
A late rebalance (the actual date later than the scheduled 3rd, as in November 2026) measures the 35 days from the
actual execution date. Unit test fixed now: on the April 2020 decision date the rule must select CLM20, not CLK20
(whose last trade date was 21 April 2020 and which settled at −US$37.63 on 20 April).

**Returns.** Positions are sized in contracts at the execution settlement F_ref:
contracts_i = w_i × capital / (F_ref × multiplier × fx), and daily P&L = contracts × multiplier × (F_d − F_{d−1}) × fx,
so returns are **arithmetic on notional** and negative prices are handled (spec §7). The per-market daily excess
return r_ex[i, d] = (F[i, T, d] − F[i, T, d−1]) / F[i, T, d−1] of the **same contract on both days** (spec §2.1)
is used for volatility estimates and for the chained index idx[i, d] = idx[i, d−1] × (1 + r_ex[i, d]) with T = the
contract held on d−1 (spec §2.3). **No back-adjusted continuous prices** are used anywhere; the T-bill rate is
neither added nor subtracted (futures returns are already excess returns).

**Monthly series.** A market's monthly excess return is the compounded daily r_ex over the calendar month; a
sleeve's monthly net return is its daily net return compounded over the calendar month, so it aligns with v1.1's
calendar-month returns in the combined book (§2.6).

### 2.4 Volatility estimates and sleeve construction conventions

- **σ_i,t (T20, T21): the commodities spec's §4.3 blend**, from the market's daily r_ex up to t:
  σ = 0.5 × σ_EWMA + 0.5 × σ_1y, with σ²_EWMA[t] = 0.94 σ²[t−1] + 0.06 r[t−1]² (RiskMetrics daily, zero mean)
  and σ_1y = the sample standard deviation of the last 252 daily returns; both annualised by √252; at least 252
  daily returns (the entry rule).
- **σ_i,t (T22): MOP's EWMA**, centre of mass 60 trading days (δ = 60/61) on daily r_ex, annualised; at least 252
  daily returns. The literature's estimator is kept for the literature's strategy (decision 7).
- **Rank weights (T20, T21; spec §3.2, AMP 2013 rank weighting):** over the n active markets,
  s_i = rank(signal_i) − (n + 1)/2, scaled so Σ|s_i| = 2; w_raw,i = s_i / σ_i,t.
- **Single-market cap (spec §7):** no market may contribute more than **10% of the sleeve's risk**, measured as
  |w_i| σ_i / Σ_j |w_j| σ_j; a breaching market is capped at 10% and the excess redistributed proportionally over the
  others, iterated until no breach (at most 10 iterations).
- **Sleeve target 10%:** the sleeve is scaled to 10% ex-ante volatility with v1.0's rule (the trailing 36-month
  pro-forma standard deviation of the current weights on the markets' monthly excess returns, at least 12 months),
  the same rule v1.0, v1.1, T01 and T16–T19 use. This is the spec's `predicted_vol(w_raw, Sigma_hat)` with Σ̂ the
  36-month sample covariance.
- **Rebalancing rule:** the sleeve applies **v1.1's T18 rule** to its own targets, with T18's values and
  definitions (`docs/v1.1_freeze.md`): trade only if |Δw_i| σ_i > 0.1 × the position's risk budget, applied to the
  proposed half-trade w + 0.5 (w* − w); the risk budget = the mean of |w*_j| σ_j over the sleeve's active positions;
  the residual of an exited position is closed once inside the band. A contract roll is not a rebalancing decision:
  the held notional moves to the new contract whether or not the band allows a size change (decision 9).
- **No drawdown stop.** The spec's example halving rule at −15% sleeve drawdown (§7) is a separate risk variant
  (algorithm spec §6.4) and is **not** part of T20–T22 (decision 10).
- **Research weights, paper contracts.** The decisive runs use fractional weights (spec §1.2: measure the signal
  on the theoretical universe). The integer-contract rounding at US$10,000,000 of paper capital (C01) is reported as
  a diagnostic: rounding error as a share of each market's target risk, and the months in which a market would be
  dropped under the spec's live rule (rounding error above 50% of its target risk). That live rule applies only in the
  live stage (§4.4).

### 2.5 Costs (commodities spec §8, plus the 2× sensitivity)

**Raw estimate per side, per contract (the spec's judgement, central values):** commission and fees **US$3** per
full-size contract per side (the midpoint of the spec's US$2–4) plus slippage of **1 tick** per side for energy,
metals, grains and the financial futures, **2 ticks** for softs, livestock, BRL and ZAR futures (table in §2.1).
In basis points of notional at the execution settlement: c_raw,i,t = (3 + ticks_i × tick_value_i) / (F_ref ×
multiplier × fx) × 10⁴, recomputed at every trade.

**Decisive cost model = 2 × c_raw** (the spec's rule: "assume 2× estimated costs in research"). Each trade is
charged c_i × |notional traded|. A roll is two trades: when the held contract changes at an execution date, the cost
is c_i × (|w_old| + |w_new|); otherwise c_i × |w_new − w_old| (calendar-spread orders, usually cheaper, are
conservatively ignored). Margin is held in cash at the funding rate and neither added to nor subtracted from returns.
No volatility scaling of costs (the algorithm spec's FX rule is not in the commodities spec; decision 14).

**2× sensitivity.** Every run is repeated with **every cost doubled** — the sleeve's (4 × c_raw) and v1.1's legs
(2 × v1.1's cost model) alike, as T01 and T16–T19 did. The pass rules are decided at the decisive model; the 2× tables
are reported, not decisive.

**Break-even cost multiple** (spec §8): m* = (annualised mean gross sleeve return) / (annualised cost drag at
1 × c_raw), over 2000-01..2026-09. The spec rejects any commodity signal with m* < 2 (§4.2).

### 2.6 Combination with v1.1 (commodities spec §6.2)

Risk budget **25% to the sleeve, 75% to v1.1**, the spec's recommended starting budget ("start with a 25% risk
budget … do not raise it until 24 months of live data"). It is applied as T01 applied its 80/20 budget:

```
W_v11,t   = v1.1's held weights at month-end t (frozen systematic_v11 / t18_rebal, unchanged), 10% target
W_s,t     = the sleeve's held weights (10% target, §2.4), as held after its rebalance in month t
W_mix     = 0.75 · W_v11 + 0.25 · W_s                  (fixed risk budget; nothing estimated)
s_t       = 0.10 / pro-forma vol(W_mix)                 (v1.0's rule: trailing 36 months of the mix's instruments, min 12)
W_tot     = s_t · W_mix,  then v1.0's 6× gross-leverage cap on the whole book
```

- v1.1's legs are v1.1's own held weights (its band already applied inside v1.1) times 0.75 s_t; the sleeve's legs
  are the sleeve's held weights times 0.25 s_t. The combined book is accounted at the weights level: P&L and costs on
  the actual traded weights, v1.1's legs at v1.1's cost model and execution lags (FX t+1, bonds t+2), the sleeve's
  legs daily at the §2.5 model. Trades caused by changes in s_t are charged like any other.
- **v1.1 baseline:** `systematic_v11` run on the frozen snapshots at `7886867` and the `data/kept/T16-T19/` raw
  cache (the inputs on which `python -m em_macro.systematic_v11 verify` reproduces T18 exactly); its 2020-01..2026-09
  monthly net returns, Sharpe 0.9163, MaxDD −15.42%, ES97.5 5.93%, half B Sharpe 0.7690, MaxDD −20.08%.
- **Reproduction check first:** before any trial runs, `python -m em_macro.verify_v1` and
  `python -m em_macro.systematic_v11 verify` must both report exact reproduction. If not, nothing is run.
- The covariance-aware equal-risk-contribution variant of spec §6.2 is not used (decision 8).

### 2.7 Periods and the holdout split (algorithm spec §0.3(b), (c))

**Periods.**
- **Design sample: 2000-01 to 2019-12.** No parameter is estimated on it (every number is fixed here). It serves
  the spec's "walk-forward 2000–2019" (§11 rows 1–2): the period on which the sleeve-level criteria check that
  the published effects reproduce in this build. Data before 2000 (from ~1980) are used only for the Build 0
  coverage table, the 5-year history Option B needs, and volatility warm-up.
- **Decisive test: 2020-01 to 2026-09** (81 months; v1.1's test window, so the combined comparison is
  like-for-like). It is fixed regardless of when the run happens; later months are reported as pre-live context.
- **Walk-forward:** nothing is fitted, so the year-by-year walk-forward is one causal run; each year 2020–2026
  (2026 = January–September) is reported separately and pooled.

**Market holdout (fixed now).** The 24 commodity markets are split in half, stratified by sector, with the
**same procedure and seed as the country split** (`em_macro/holdout.py`: `numpy.random.default_rng(20261103)`,
strata in the order energy, industrial metals, precious metals, grains and oilseeds, softs, livestock; within each
stratum the sorted symbols are shuffled and dealt one by one to the half with fewer markets, a coin flip from the same
generator deciding ties). The procedure depends only on the seed and the symbol list; it was run on the list and the
result is:

| half | energy | industrial metals | precious | grains and oilseeds | softs | livestock | T22 financial futures (by T01's country split) |
|---|---|---|---|---|---|---|---|
| A | B NG G | — | SI PL | ZC ZS ZW | KC CT | LE GF | 6M (MX), 6E (euro area), FGBL (DE), FBON (ES) |
| **B (holdout)** | CL RB HO | HG | GC PA | KE ZM ZL | SB CC | HE | 6L (BR), 6Z (ZA), 6B and Long Gilt (GB), FOAT (FR), FBTP (IT) |

- T20 and T21 holdout universe = half B without gold and silver: **CL RB HO HG PA KE ZM ZL SB CC HE** (11 markets).
  Half A for context: B NG G PL ZC ZS ZW KC CT LE GF (11).
- T22 holdout universe = half B (12 commodities) plus the six half-B financial futures (18); half A = 12 + 4.
- The sleeve is run on the holdout universe as a stand-alone sleeve (ranks, σ, cap and scaling within the half) and
  combined with **the full v1.1** exactly as in §2.6; the comparison is against the full v1.1. The change being
  tested is the added sleeve, so the holdout applies to the sleeve's markets (decision 15). Decisive holdout
  window 2020-01..2026-09; half A and 2000–2019 are context. The split is committed in this document; the code that
  reproduces it is committed with the trial code.

### 2.8 Statistics

Monthly net returns over the window. **SR** = mean/SD × √12 (SD with ddof 1). **Return** compounded. **MaxDD** =
maximum drawdown of the compounded monthly index. **ES(97.5%)** = historical expected shortfall of monthly net
returns (Acerbi–Tasche, α = 0.025; `t01.expected_shortfall`), as a positive loss. **Turnover** = one-way notional
traded per year in multiples of capital. All as in T01, T02 and T16–T19 (`em_macro/t01.py`).

**Block bootstrap (criterion 1).** ΔSR = SR(v1.1 + sleeve) − SR(v1.1) over 2020-01..2026-09, full universe,
decisive costs. Paired circular block bootstrap of the 81 monthly return pairs, block length 6 months, B = 10,000,
`numpy.random.default_rng(20261103)` (T01's `bootstrap_delta_sharpe`), null centred at ΔSR = 0:
p_raw = (1 + #{b : ΔSR*_b − ΔSR_hat ≥ ΔSR_hat}) / (B + 1), one-sided for H1: ΔSR > 0. Holm-adjusted across the
three trials (§5). The bootstrap mean, SD and 5%–95% range are reported.

**Deflated Sharpe (criterion 4).** PSR and DSR via `em_macro/mtstats.py` from each strategy's realised
2020-01..2026-09 monthly SR, sample skewness and raw kurtosis, T = 81; decisive null noise-only (trial-Sharpe SD
1/√(T−1) per month). **N convention (decisive):** the spec's count, incremented for the whole family at once:
v1.0 at N = 7, T01 and T02 took it to 9, T16–T19 to 13; the three trials take it to **N = 16**, and every trial is
evaluated at N = 16 against **v1.1 at N = 13** (DSR 0.739 in the T16–T19 report, recomputed from v1.1's realised
returns on this run's inputs). Reported, not decisive: the dispersed-trials null (SD 0.20 annualised) and the ledger
convention (18 completed rows now, 21 after this family: v1.1 at N = 18, each trial at N = 21).

**Newey–West t-statistics** (sleeve-level criteria) use 6 lags, the programme's 6-month block convention.

**Clark–West test (T20, commodities spec §4.1).** Pooled panel of the sleeve universe. For market i and decision
date t, the target is the market's holding-period excess return to the next execution date. Benchmark forecast
r̄_i,t = the expanding mean of i's past holding-period returns (the prevailing historical mean). Model forecast
r̂_i,t = r̄_i,t + β̂_t z_i,t, with z the cross-sectionally rank-standardised carry (mean 0, SD 1, winsorised at ±2;
spec §4.3) and β̂_t the pooled OLS slope on all (j, s) with s < t, expanding from 2000-01 with at least 120 months
(first forecast at the 2010-01 decision). f_i,t = (r − r̄)² − [(r − r̂)² − (r̄ − r̂)²]; f̄_t = the cross-sectional
mean each month; CW t = mean(f̄)/NW_se(f̄, 6 lags), one-sided. Window: 2010-01..2026-09 decisions (all forecasts);
also reported for 2020-01..2026-09 alone. β̂ is a test statistic, not a traded parameter.

## 3. Specifications (fixed; no parameter is chosen from any backtest result)

Everything in §2 applies to all three. Each sleeve is run on its own (for the sleeve-level criteria and the
diagnostics) and combined with v1.1 (§2.6) for the combined criteria; each on the full universe, half B and half A;
at the decisive and the 2× cost models. **One run each**; no variant, re-parameterisation or re-run after seeing
results. If running a trial would require changing a number fixed here, the trial is marked "not run" with the
reason.

### 3.1 T20 — commodity carry, de-seasonalised 12-month carry (commodities spec §3.2 Option A; Option B fallback)

**Universe:** the 22-market cross-sectional universe (§2.1). **Signal at decision date t, Option A:**

```
F1  = the roll rule's contract (§2.3);  D1 = calendar days from t to F1's last trade date
F13 = the contract in i's designated calendar whose last trade date is closest to (F1's last trade date + 365 days),
      eligible only if that distance is within ±45 days (10.5 to 13.5 months after F1); ties → the later contract
carry12[i,t] = (ln F1[t] − ln F13[t]) × 365 / (D13 − D1)          # KMPV "carry1-12", log form (spec §3.2, §2.4)
```

Positive carry (backwardation over the 12-month curve) ranks high and is bought. The log form needs positive prices;
if F1 or F13 is non-positive on t the signal is missing that month (§2.1 rule 3).

**Option A or B per market (mechanical, decided in Build 0 from coverage, not from returns).** A market uses
Option A if an eligible F13 has a settlement on at least **90% of its decision dates in the design sample**
(2000-01..2019-12, after entry); otherwise it uses **Option B for the whole sample**:

```
carry_log[i,t] = (ln F1 − ln F2) × 365 / (D2 − D1)                                   # spec §2.4
carry_ds[i,t]  = carry_log[i,t] − mean( carry_log[i, same decision month, t−12m, t−24m, …, t−60m] )   # at least 3 of 5
```

The per-market choice is recorded in the Build 0 report before any carry portfolio return is computed and is never
changed. Within an Option A market, a decision date without an eligible F13 settlement gets a missing signal
(weight 0), not Option B.

**Construction:** rank weights, inverse σ (spec §4.3 blend), 10% single-market cap, 10% sleeve target, the T18
rebalancing rule, §2.5 costs — all as §2.4.

**Diagnostics reported (not criteria):** the share of markets on Option A; the sleeve's sector exposures through
time; its correlation with v1.1, with v1.0's carry sleeve, with the S&P 500 and with the T21 and T22 sleeves (the
spec's §3.9 and §6.1 matrices, "to be measured in Build 1"); turnover by year; the rounding diagnostic.

### 3.2 T21 — basis-momentum (commodities spec §3.4; Boons and Porras Prado 2019)

**Universe:** the 22-market cross-sectional universe. **Two parallel rolled series per market:** the first-nearby
series holds F1 of the roll rule, the second-nearby series holds F2 (the next designated contract), each from one
execution date to the next, so their holding-month excess returns r_F1,m and r_F2,m are the chained same-contract
returns of the §2.3 machinery. **Signal at decision date t:**

```
BM[i,t] = Π_{m = t−11..t} (1 + r_F1[i,m]) − Π_{m = t−11..t} (1 + r_F2[i,m])      # 12 holding months, all required
```

the difference between the 12-month return of the first-nearby and of the second-nearby contract, Boons and Porras
Prado's definition; the spec's Appendix A writes it as a sum of monthly returns, which agrees to second order
(decision 5). High basis-momentum ranks high and is bought.

**Construction:** identical to T20 (rank weights, inverse σ, cap, 10% target, T18 rule, costs).

**Incremental alpha versus carry (spec §11 row 2):** the regression of the T21 sleeve's monthly net returns on the
T20 sleeve's (both stand-alone at 10%, full universe, decisive costs) over 2000-01..2026-09 from the first month both
exist; the annualised intercept and its Newey–West (6 lags) t-statistic.

**Diagnostics reported:** as T20, plus the correlation between the BM and carry signals (cross-sectional, averaged
over months) and between the two sleeves' returns (spec expectation 0.2–0.4).

### 3.3 T22 — time-series trend across a diversified futures universe (MOP 2012; HOP 2017)

**Universe:** the 24 commodities plus the 10 financial futures (§2.1), each entering under the entry rule.
**Signal at decision date t, for each active instrument i and horizon k ∈ {1, 3, 12} months:**

```
sgn_k[i,t]  = sign( idx[i,t] / idx[i, t − k months] − 1 )           # chained excess-return index (§2.3); 0 if exactly 0
pos_k[i,t]  = sgn_k[i,t] × 0.40 / σ_i,t                              # MOP: each position scaled to 40% ex-ante vol
TREND[i,t]  = ( pos_1 + pos_3 + pos_12 ) / 3                          # HOP: equal weight of the three horizons
w_raw[i,t]  = TREND[i,t] / S_t                                        # MOP: equal weight across the S_t active instruments
```

σ_i,t = MOP's 60-day-centre-of-mass EWMA (§2.4); idx at "t − k months" = the index on the same calendar day k
months earlier, or the last settlement before it. All three horizons must be available (12 months of history, the
entry rule). The sleeve is then scaled to 10% with the programme's pro-forma rule, so the 0.40 fixes only relative
sizes (equal ex-ante risk per instrument), and the T18 rebalancing rule and §2.5 costs apply. There is no asset-class
re-weighting: MOP's diversified portfolio is the equal-weighted average across instruments (decision 6). There is
no cap on net duration or on net dollar exposure (none in MOP or HOP); both exposures are reported.

**Carry-crisis statistic (algorithm spec §2.2; T01 criterion 5).** Carry sleeve = frozen v1.0 run with carry
only (`systematic.run(inp, ["carry"])`, net returns), exactly as in T01; carry's worst 10% of months = the
round(0.10 × 81) = 8 months with the lowest carry-sleeve net return in 2020-01..2026-09 (from T01's report: 2020-03,
2020-07, 2021-10, 2022-03, 2023-04, 2023-11, 2023-12, 2024-08; recomputed on this run's inputs). The statistic is
the Pearson correlation of the T22 sleeve's net returns with the carry sleeve's over those months.

**Diagnostics reported:** P&L contribution by asset class (commodities, currencies, bonds) and by horizon
(attribution of the one sleeve, not separate strategies); net dollar and net duration exposure; correlation with
v1.1, with the carry sleeve over all months, with T20 and T21, and with the S&P 500; the sleeve's return in v1.1's
five worst months; the sleeve by year.

## 4. Pass rules (decisive costs; 2× reported)

### 4.1 Combined criteria (every trial; algorithm spec §0.3 and the task)

| # | criterion | passes if |
|---|---|---|
| C1 | 2020-01..2026-09, full universe: Sharpe improvement versus v1.1 | ΔSR = SR(v1.1 + sleeve) − SR(v1.1) > 0 **and** Holm-adjusted one-sided block-bootstrap p (§2.8, §5) < 0.10 |
| C2 | holdout, half B, 2020-01..2026-09 | ΔSR(v1.1 + half-B sleeve, versus v1.1) > 0 **and** \|MaxDD(v1.1 + half-B sleeve)\| ≤ \|MaxDD(v1.1)\| |
| C3 | tail risk, 2020-01..2026-09, full universe | \|MaxDD(v1.1 + sleeve)\| ≤ 1.10 × \|MaxDD(v1.1)\| **and** ES97.5(v1.1 + sleeve) ≤ 1.10 × ES97.5(v1.1) |
| C4 | deflated Sharpe, N incremented for the family | DSR(v1.1 + sleeve; N = 16, noise-only null) ≥ DSR(v1.1; N = 13) |

### 4.2 Sleeve-level criteria (commodities spec §11 and §8; algorithm spec §2.2)

| trial | # | criterion | passes if |
|---|---|---|---|
| T20 | S1 | net Sharpe of the stand-alone sleeve, full universe | SR > 0.20 in **both** 2000-01..2019-12 and 2020-01..2026-09 |
| T20 | S2 | Clark–West (§2.8), carry signal against the prevailing mean | one-sided p < 0.05 over 2010-01..2026-09 |
| T20 | S3 | break-even cost multiple (§2.5), 2000-01..2026-09 | m* ≥ 2 |
| T21 | S1 | mean net return of the stand-alone sleeve, 2000-01..2026-09 | Newey–West (6 lags) t > 2 |
| T21 | S2 | incremental alpha versus the T20 carry sleeve (§3.2) | annualised intercept > 0 and NW t > 1.5 |
| T21 | S3 | break-even cost multiple, 2000-01..2026-09 | m* ≥ 2 |
| T22 | S1 | net Sharpe of the stand-alone sleeve, full universe | SR > 0.20 in **both** 2000-01..2019-12 and 2020-01..2026-09 |
| T22 | S2 | carry-crisis correlation (§3.3) | corr(T22 sleeve, carry sleeve) < 0 over carry's worst 8 months of 2020-01..2026-09 |
| T22 | S3 | break-even cost multiple, 2000-01..2026-09 | m* ≥ 2 |

The design-sample window in S1 does not make 2000–2019 a decision sample in the sense the earlier trials excluded
(v1.0 was designed on 2005–2019; nothing here is designed on 2000–2019). It is the spec's own walk-forward
requirement that the published effect reproduces in this build; the Sharpe floor of 0.20 is the spec's (§11 row 1),
below the haircut prior of 0.25–0.35.

### 4.3 Decision

A trial **passes only if all of C1–C4 and its three sleeve-level criteria hold**, with C1 after the Holm
correction. Any failure means the sleeve is not adopted and v1.1 (and v1.0) stay live unchanged. Half A, 2000–2019
combined results, the 2× tables and the diagnostics are context and cannot affect the decision. **No criterion,
threshold, parameter, universe, roll rule, cost or sample may be changed after results are seen**; any variant run
later (other budgets, horizons, de-seasonalisation windows, bands, universes, the carry + basis-momentum composite,
a drawdown stop) is a new trial with a new ledger row and a new pre-registration.

### 4.4 Live stage (algorithm spec §0.3(d); commodities spec §11)

A passing sleeve is not merged into v1.1. It is run in parallel as a paper sleeve (as v1.1 runs beside v1.0) for
**12 months** at the 25% budget, with positions logged monthly in integer contracts at US$10,000,000, the spec's
live rounding rule (drop a market for the month when rounding error exceeds 50% of its target risk) and realised
costs recorded; the risk budget is not raised before 24 months of live data (spec §6.2). Adoption into a version is
a separate decision under the spec's process, not taken by this document.

## 5. Multiple testing: the family

The three trials are one family. Their three raw one-sided bootstrap p-values (C1) are adjusted by the **Holm
(1979) step-down** procedure: order p_(1) ≤ p_(2) ≤ p_(3); p_adj,(i) = max_{j ≤ i} min(1, (3 − j + 1) p_(j)).
Raw and adjusted values are both reported; C1 uses the adjusted value at level 0.10. The deflated Sharpe (C4)
counts the family as three new trials at once (N = 16). The sleeve-level criteria are each trial's own gates and
are not adjusted (as T18's turnover criterion was not). The 2× p-values are Holm-adjusted the same way for the 2×
table. Every signal, variant or parameter tried later counts in N (commodities spec §11).

## 6. Build 0 — data-feasibility acceptance tests (commodities spec §11, row 0)

Build 0 assembles the data and runs the tests below. **All must pass before any trial in §3 runs.** A failure stops
the trials; the failure and any data fix are reported in `results/T20-T22/build0.md`, and a data fix (a corrected
multiplier, calendar, notice date, splice or vendor substitution) is not a trial. The report is committed before
the trial run. There is no reduced-universe fallback: if A2 fails, the trials are not run.

| # | test | passes if |
|---|---|---|
| A1 | assembly: for each of the 34 markets, every contract in the designated calendar with daily settlements, first notice and last trade dates, 1990-01 (or first listing) to 2026-10, from the primary source; multipliers, ticks and calendars verified against the exchange specification pages and recorded | every market has a contract table and metadata, or is recorded as unavailable |
| A2 | **spec (a)**: F1/F2 coverage (§2.1 rule 1) of the 22-market sleeve universe since 2000-01 | **at least 18 markets** with coverage ≥ 95% |
| A3 | **spec (b)**: the equal-weight monthly excess-return index of the available commodity markets (F1 rolled series, equal weights, rebalanced monthly) against AQR's *Commodities for the Long Run* equal-weight index over the overlapping months | Pearson correlation ≥ 0.90 |
| A4 | **spec (c)**: a KMPV-style carry portfolio (rank weights on carry_log(F1, F2), all 24 markets, no volatility scaling, monthly, gross) against AQR's commodity carry factor (*Century of Factor Premia*) over the overlapping months | Pearson correlation ≥ 0.70 |
| A5 | cross-check: for the CME-group markets from 2010-06-06, F1 and F2 settlements from Databento against the primary source | agreement within one tick on ≥ 99% of days per market; a market failing after investigation is dropped and recorded |
| A6 | roll-rule tests (spec §2.3 look-ahead traps): every chosen contract has its first settlement on or before the decision date; notice(F1) > execution date + 35 days on every rebalance; no held contract is ever within its last 10 trading days; the April 2020 test selects CLM20; no LME series anywhere | all assertions hold on the full history |
| A7 | Option A availability (T20): per market, the share of design-sample decision dates with an eligible F13 settlement; the Option A/B assignment (§3.1) | the assignment table is in the report; it is computed from availability only |
| A8 | **no peeking**: Build 0 prints coverage counts, the A3 and A4 correlations, data-quality flags and the A7 shares, and **no return, Sharpe, drawdown or P&L of any sleeve or signal** | the report contains no such statistic (checked by review before the commit) |
| A9 | data quality (algorithm spec §13): held-contract gaps of more than 5 consecutive days (§2.1 rule 4) and daily moves beyond 8 median absolute deviations that fully reverse the next day, per market | none unresolved; limit-locked identical settlements in grains and livestock are flagged, not failed |
| A10 | T22 financial futures: the same coverage test as A2 per market since the later of 2000-01 and entry | each market ≥ 95% or dropped and recorded |
| A11 | F2 and F13 are listed contracts on every date they are used (no month later delisted; spec §2.3 trap (b)) | assertion holds |

A6, A9 and A11 are implemented as unit tests (`tests/test_commod_data.py`) that stay in the suite.

## 7. Reporting (algorithm spec §0.4)

`results/T20-T22_commodity_trials.md` will report: the pass/fail table per trial and criterion (decisive costs;
2× reported); v1.1 and each combined book side by side (Sharpe, return, volatility, MaxDD, ES97.5, turnover) for
2020-01..2026-09, by year 2020–2026, for half B, and for 2000–2019 as context; each stand-alone sleeve over
2000–2019, 2020-01..2026-09, half A and half B; the raw and Holm-adjusted p-values; the deflated-Sharpe update; the
Clark–West, break-even, incremental-alpha and carry-crisis statistics; behaviour in v1.1's five worst months; the
§3 diagnostics; the correlation matrix of the three sleeves, v1.1, v1.0's carry sleeve and the S&P 500; every
decision taken under the task's rules; and a note on which passing sleeves, if any, could be combined in a future
pre-registered trial (not tested here). No editorialising about adoption beyond the mechanical pass/fail. Tables and
monthly returns go to `results/T20-T22/`, with `RUN.json` (run time, commit, SHA-256 of code, pre-registration,
Build 0 report and inputs, the v1.0 and v1.1 reproduction checks). Raw data per `docs/raw_data_archive.md` and
decision 13.

**Ledger.** `trials.csv` gets rows T20–T22 (groups G19–G21), marked pending, in the commit after this document,
changing no other row; they are updated with the outcomes after the run.

## 8. Decisions taken under the task's rules (listed again in the report)

Rules applied: where the spec gives a range, its central or recommended value; where the spec and the literature
disagree on **what is forecast** (signal definition, lookback, estimator the strategy is defined by), the
literature; the programme's sizing and risk conventions (inverse volatility, 10% targets, the 36-month pro-forma
scaler, the T18 band, the 6× cap) where the literature's portfolio is a reporting device rather than a risk
framework; where a choice depends on unseen data, a mechanical rule.

1. **Risk budget 25%** (spec §6.2 recommended starting value), as a fixed 0.75/0.25 mix of 10%-volatility books
   rescaled to 10% (T01's precedent), not the optimal share (the spec's "about 31%" is for a baseline Sharpe of 0.65;
   against v1.1's 0.92 it is about 19% for S2 = 0.30, ρ = 0.1).
2. **Universe 22 = 28 table rows − 4 LME − gold − silver**; T22 uses all 24 commodities. LME metals excluded as
   non-standard futures with paid-only history (and nickel by §7).
3. **Platinum and palladium stay in T20 and T21.** The spec's §3.2 says "exclude precious metals" and its §5
   and the task say "gold and silver"; the task's wording is followed. They are subject to the same data rules
   (Option B is likely for them under A7).
4. **Option A/B per market by F13 availability ≥ 90% of design-sample decision dates**, decided once in Build 0,
   with ±45 days as the F13 eligibility window and "at least 3 of 5 years" for Option B's seasonal mean.
5. **Basis-momentum as the difference of compounded 12-month returns** (the paper), not the spec's sum.
6. **T22 weighting equal across instruments** (MOP, peer-reviewed) rather than equal across asset classes; three
   horizons {1, 3, 12} equal-weighted (HOP); sign positions at 40%/σ (MOP). Not the algorithm spec's continuous
   clipped blend with k = 6 (T01's), so T22 is the literature's strategy, not a T01 variant.
7. **Volatility estimators:** the commodities spec's blend (0.5 EWMA λ = 0.94 + 0.5 one-year) for T20 and T21; MOP's
   60-day EWMA for T22; daily data for all, since every T22 instrument is a listed future with daily settlements.
8. **Sleeve scaling by the programme's 36-month pro-forma rule**, not the spec's Ledoit–Wolf equal-risk-contribution
   solve, so that every trial in the programme is scaled the same way.
9. **Rebalancing band = v1.1's T18 rule** on the sleeve's own targets (the live rule the sleeve would join), not the
   spec §6.2's 25% band (v1.0's, replaced by T18) and not the literature's full monthly rebalancing. Rolls are not
   banded.
10. **No drawdown stop** (spec §7's "e.g. halve at −15%" is a separate risk variant per algorithm spec §6.4).
11. **T22 bonds are outright 10-year futures** (Bund, OAT, BTP, Bono, Long Gilt), not v1.0's spreads; T22
    currencies are the five CME futures (EUR, GBP, MXN, BRL, ZAR); TRY, IDR, PLN, COP, CLP and all EM local bonds
    have no listed future and are out.
12. **Data: Norgate primary (the task), Pinnacle Deep History as the mechanical fallback** if Norgate cannot be run
    (the spec's programme note), Databento cross-check from 2010; the choice recorded in Build 0 before any signal.
13. **Raw-data archive stored privately** (vendor licences forbid redistribution), manifest and hashes committed —
    a deviation from the "committed or attached to the release" form of the retention rule, flagged for the owner.
14. **Costs:** commission US$3 (midpoint of US$2–4) + 1 tick (2 for softs, livestock, BRL and ZAR futures), doubled
    for the decisive model (spec §8 rule), doubled again for the sensitivity; rolls as two trades; no volatility
    scaling of costs; break-even measured against the raw estimate over 2000-01..2026-09.
15. **Holdout = the sleeve's markets** (sector-stratified seeded split, seed 20261103; T22's financial futures by
    T01's country split), combined with the full v1.1; decisive window 2020-01..2026-09.
16. **Design sample 2000-01..2019-12** (the spec's walk-forward window) used only for the sleeve-level Sharpe floor
    and the Clark–West estimation window; decisive combined window 2020-01..2026-09 fixed to v1.1's test.
17. **Clark–West window 2010-01..2026-09** (expanding estimation from 2000 with ≥ 120 months), cross-sectional mean
    of the loss differential per month, Newey–West 6 lags; benchmark = prevailing historical mean (spec §4.1).
18. **Minimum active markets 6**; a market's missing signal gives weight 0; coverage gate 95% from the later of
    2000-01 and entry; entry after 12 months of settlements, no backfill.
19. **DSR N:** spec convention 13 → 16, every trial against v1.1 at N = 13; ledger convention 18 → 21 as context.
20. **Timing:** decision on each market's last settlement before its first settlement on or after the 3rd;
    execution at that settlement; 35-day buffer from the execution date.
21. **Carry sleeve for T22's crisis criterion = frozen v1.0 carry-only** (T01's definition), so the statistic is
    comparable with T01's; the eight months are recomputed on this run's inputs.
22. **Merge conflicts with `main`**, if any, are resolved by keeping both sides.

Nothing in this document depends on commodity data; no trial was found to require a choice that only data could
make, so none is deferred.

## Amendment 1 — 2026-11-04, before any commodity data exists

Recorded after the pre-registration commit `ae8dfcb` and the ledger-row commit `bc07b65`, and **before any commodity
price was downloaded, opened or computed** in this repository (Build 0 has not been run). The text above is left as
written; where this section and the text above differ, this section governs. Nothing else changes.

### A1.1 Pass rule: criterion C1 becomes non-inferiority; the sleeve-level gates are the primary evidence

**Reason.** §1 of this document already shows that, at the spec's own priors (a haircut sleeve Sharpe of 0.30,
correlation 0.1 with v1.1 at 0.92), the fund-level gain is about +0.03 Sharpe, which an 81-month block bootstrap
cannot resolve (T01's ΔSR of +0.15 had p = 0.26). A superiority test at the fund level would therefore mostly
measure noise, and its outcome would say little about whether the published commodity effects reproduce. The
amendment follows the T16–T19 batch: the fund-level test asks that the sleeve **not hurt** v1.1, and the evidence
that the effect exists comes from each trial's sleeve-level gates (commodities spec §11), which were already listed
in §4.2 and are now the primary evidence. This decision was made before any data was seen.

**C1, replaced.** 2020-01..2026-09, full universe, decisive costs. ΔSR = SR(v1.1 + sleeve) − SR(v1.1). The
hypothesis tested is **H1: ΔSR > −0.05** against H0: ΔSR ≤ −0.05 (Sharpe non-inferiority, margin 0.05, as in
`docs/prereg/T16-T19_risk_batch.md` §2.1). Paired circular block bootstrap of the 81 monthly return pairs, block
length 6 months, B = 10,000, `numpy.random.default_rng(20261103)`, one-sided p from the bootstrap distribution
centred on the null boundary:

```
p_raw = (1 + #{b : ΔSR*_b − ΔSR_hat ≥ ΔSR_hat + 0.05}) / (B + 1)
```

C1 passes if **ΔSR_hat ≥ −0.05 and the Holm-adjusted p (§5, across T20–T22) < 0.10**. The bootstrap mean, SD and
5%–95% range of ΔSR* are reported, and the superiority p (margin 0, the original C1) is reported as context, not
decisive.

**C2, C3, C4: unchanged.** C2 stays as written in §4.1: on half B, ΔSR(v1.1 + half-B sleeve, versus v1.1) > 0 and
|MaxDD| not worse than v1.1's (the task's "holdout not worse" is read as that existing criterion, which is kept
unchanged as instructed; it remains a point-estimate requirement with no bootstrap). C3 (MaxDD and ES97.5 at most
1.10 × v1.1's) and C4 (DSR at N = 16 at least v1.1's at N = 13) are unchanged.

**Decision rule (§4.3, restated).** A trial passes only if **all of its sleeve-level gates (§4.2) and all of
C1–C4 hold**, C1 after the Holm correction. The sleeve-level gates are the primary evidence that the published
effect reproduces in this build (T20: Sharpe > 0.20 in both windows, Clark–West p < 0.05, break-even ≥ 2×; T21:
Newey–West t > 2, alpha versus carry t > 1.5, break-even ≥ 2×; T22: Sharpe > 0.20 in both windows, carry-crisis
correlation < 0, break-even ≥ 2×); C1–C4 establish that adding the sleeve at the 25% budget does not damage v1.1.
Everything else in §4 (decisive costs, 2× reported, no change after results, variants are new trials, the live
stage) stands. §5 applies the Holm correction to the three non-inferiority p-values.

### A1.2 Universe: platinum and palladium leave T20 and T21; all four precious metals stay in T22

**Reason.** Commodities spec §3.2 excludes precious metals from the carry ranking because their curves price
financing and lease rates and carry almost no cross-sectional scarcity information; the same reasoning applies to
basis-momentum, a curve-shape signal (§3.4), and §5 item 1 excludes gold and silver from both rankings. §2.1 and
decision 3 of this document kept platinum and palladium in on the task's wording; this amendment follows the spec.

**Change.**
- **T20 and T21 cross-sectional universe: 20 markets** = the 24 of §2.1 minus gold, silver, platinum and palladium
  (CL B RB HO NG G HG ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE). Decision 3 in §8 is superseded.
- **T22 is unchanged:** all 24 commodities, gold, silver, platinum and palladium included, plus the 10 financial
  futures.
- **Build 0 test A2** applies to the 20-market universe with the spec's absolute threshold kept: **at least 18 markets**
  with F1/F2 coverage ≥ 95% since 2000 (a stricter share than before, 18 of 20). A7 (Option A/B availability) is
  computed for the 20 markets only. The minimum of 6 active markets (§2.1 rule 3) is unchanged.
- **Holdout split.** The split in §2.7 is defined on the 24 commodity markets by the seeded procedure (seed
  20261103), and T22 still uses all 24, so the procedure's input and output are unchanged by this amendment; the
  T20 and T21 halves are derived from it by removing the four precious metals, as §2.7 derived them by removing two.
  The removal therefore does not change the split. The derived halves are now:

| half | T20 and T21 universe (10 markets each) |
|---|---|
| A | B NG G ZC ZS ZW KC CT LE GF |
| **B (holdout)** | CL RB HO HG KE ZM ZL SB CC HE |

  Each half keeps three energy, three grain-and-oilseed, two soft and at least one livestock market; copper (the one
  industrial metal) is in half B. The remark in §2.1 rule 3 that "the half-universe holdouts have 11 markets" now
  reads 10.

**Not changed by this amendment:** the roll rule, the data sources, the costs, the combination with v1.1, the
periods, the statistics, the T20 and T21 signal definitions, every T22 item, the Build 0 tests other than A2's
universe, and the reporting. The ledger rows T20–T22 are updated to reference this amendment's commit, changing no
other row.

## Amendment 2 — 2026-11-04, before any commodity data exists

Recorded after Amendment 1 (`023c829`) and its ledger-row commit (`1611f90`), and **before any commodity price was
downloaded, opened or computed** in this repository (Build 0 has not been run). The text above is left as written;
where this section and the text above differ, this section governs. Only criterion C2 changes.

### A2.1 Pass rule: criterion C2 becomes non-inferiority on the holdout

**Reason.** With an expected fund-level gain near +0.03 Sharpe (§1), requiring ΔSR > 0 on half the markets, as
C2 did, would be decided mostly by noise: the half-B sleeve has 10 (T20, T21) or 18 (T22) markets and the
comparison runs over 81 months, so the sign of a point estimate that small is close to a coin flip. Amendment 1 made
the full-universe test non-inferiority for the same reason and left C2 as a superiority requirement; this amendment
aligns C2 with it and with C2 of `docs/prereg/T16-T19_risk_batch.md` (holdout Sharpe not worse than the baseline's
by more than 0.05). This decision was made before any data was seen.

**C2, replaced.** Holdout, half B, 2020-01..2026-09, decisive costs. The half-B sleeve is run stand-alone on the
half-B universe (§2.7) and combined with the full v1.1 (§2.6); the comparison is against the full v1.1. C2 passes if

```
ΔSR(half B) = SR(v1.1 + half-B sleeve) − SR(v1.1)  ≥  −0.05
and  |MaxDD(v1.1 + half-B sleeve)|  ≤  |MaxDD(v1.1)|
```

both as **point estimates, with no bootstrap**, matching C2 of the T16–T19 batch. The half-B ΔSR, both Sharpe
ratios and both drawdowns are reported; half A and 2000–2019 remain context.

**C1, C3, C4 and the sleeve-level gates: unchanged** (C1 as amended in Amendment 1). The decision rule stands: a
trial passes only if all of its sleeve-level gates (§4.2) and all of C1–C4 hold, C1 after the Holm correction.
Nothing else in this document changes. The ledger rows T20–T22 are updated to reference this amendment's commit,
changing no other row.

## Amendment 3 — 2026-11-05, after Build 0 and before any sleeve return was computed

Recorded after the Build 0 report (`results/T20-T22/build0.md`), which found A6 failing. **No signal portfolio,
sleeve return, Sharpe ratio, drawdown or pass criterion of T20, T21 or T22 had been computed.** Build 0 had computed
only coverage counts, data-quality flags, availability shares, the A3/A4 benchmark correlations and the A5 tick
agreement. The text above is left as written. Where this section and the text above differ, this section governs.
Only the roll rule of §2.3 changes, and only for the markets named below.

### A3.1 Roll rule: guarantee the stated invariant for markets whose notice date is the last trade date

**Reason.** §2.3 states that "a held contract is never inside its last 10 trading days (spec §7)", and Build 0 test
A6 checks it. Build 0 showed that the 35-day buffer does not guarantee this when notice(T) = LTD:
- The rule only requires LTD > execution + 35 calendar days.
- The contract is held to the next execution date, 31–35 days later.
- It can therefore be held into its last 2–10 trading days.

On 2000-01..2026-09 this happened in 312 of 321 months for gasoil, 213 for lean hogs, 192 for Brent (all before its
2016 rule change), 8 for feeder cattle and 3 for WTI. The amendment restores the invariant the pre-registration
already states, using the simplest rule that guarantees it at the next rebalance. The rule was decided from the
contract calendar only.

**Change.** For every market whose notice(T) is its last trade date, F1 in §2.3 becomes:

```
F1(i, t) = the earliest contract T in i's designated calendar such that
           notice(T) > execution_date + 35 calendar days
           and   #trading days d of market i with  next_execution_date <= d <= LTD(T)  > 10
F2(i, t) = the next contract after F1 in the designated calendar (unchanged definition)
```

**Which markets.** Among the commodities these are CL, B, RB, HO, NG, G, SB, GF and HE. The same criterion applies
to any T22 financial future whose notice date is its last trade date, as determined in Build 0 from the vendor's
metadata.

**How the condition is evaluated.**
- `next_execution_date` is the execution date of the following rebalance as defined in §2.3: market i's first
  settlement on or after the 3rd of the next month. After a late rebalance it is the actual next execution date.
- Trading days are counted on the exchange's published trading calendar, which is known in advance, so no
  information after t is used.
- For markets with a first notice date before the LTD, the condition is already implied by the existing rule, since
  Build 0's minimum was 19 trading days left at exit. Those markets are unchanged.
- F2, F13 (T20 Option A), the first- and second-nearby series (T21) and the held contract (T22) all follow the new
  F1.
- The April 2020 unit test is unchanged: CLM20 has 12 trading days from the May 2020 execution to its LTD.

**Effect measured in Build 0, from the contract calendar only.**
- **Contracts that change.** F1 changes in 2000-01..2026-09 for G (312 months), HE (213), B (192), GF (8) and CL (3),
  and nowhere else.
- **A6.** The last-10-trading-days violations fall to 0 in every market.
- **Other Build 0 results.** A2 coverage stays 20 of 20 at 100%, A11 stays at 0 violations, and every Option A/B
  assignment (A7) is unchanged.

**Not changed.** The following stay as written:
- the 35-day buffer, the designated calendars, the coverage gate and entry;
- costs, signals, the combination with v1.1, periods, statistics and pass rules;
- the other Build 0 tests (A6 is re-run under this rule).

The ledger rows T20–T22 are updated to reference this amendment, changing no other row.

## Amendment 4 — 2026-11-05, decided after seeing A4 = 0.503 and the A4 diagnostic's 0.679

Recorded after Amendment 3, after the Build 0 report and after the A4 diagnostic
(`docs/prereg/T20-T22_A4_diagnostic.md`, results in `results/T20-T22/build0_a4_diagnostic.md`). **This amendment is
made with knowledge of the A4 results:**
- A4 = 0.503 after the diagnostic's data fix;
- AQR's documented construction on our data = 0.679 against AQR's factor.

No sleeve return, Sharpe ratio, drawdown or pass criterion of T20, T21 or T22 had been computed. The text above is
left as written; where this section and the text above differ, this section governs.

### A4.1 A4 no longer gates the trials

Build 0 test A4 (the KMPV-style carry portfolio against AQR's commodity carry factor, Pearson ≥ 0.70) is **reported,
not gating**. §6's "all must pass" now applies to A1–A3 and A5–A11.

The basis for this decision is data accuracy measured directly:
- **A5:** Databento settlements agree with Norgate within one tick on ≥ 99.97% of days in every one of the 18
  CME-group commodity markets (worst 99.976%). The six ICE markets (B, G, SB, KC, CC, CT) are not in A5; their
  accuracy rests on A3 only.
- **A3:** the equal-weight index correlates 0.975 with AQR's *Commodities for the Long Run*.

**What the A4 diagnostic established about the shortfall.**
- **No data error remains.** The diagnostic found one data error (the first month omitted) and no other, so the
  shortfall is not attributed to data errors.
- **Construction explains part of the gap.** Applying AQR's documented construction raised the correlation from
  0.503 to 0.679.
- **The rest is attributed, not tested.** The remaining gap is attributed to the universe and source differences
  the diagnostic listed but could not remove: AQR's base metals, AQR's data sources and its limit-day handling. The
  diagnostic did not test which of these accounts for it.

### A4.2 In exchange: a stricter C1 for T20 and T21

For **T20 and T21**, C1 (Amendment 1's Sharpe non-inferiority test) passes only if ΔSR_hat ≥ −0.05 **and the
Holm-adjusted one-sided block-bootstrap p < 0.05**, instead of < 0.10.
- These two trials use the carry construction that A4 checked.
- The Holm adjustment across T20–T22 (§5) is unchanged.
- **T22 is unchanged** (Holm-adjusted p < 0.10), since it does not use the carry construction.

### A4.3 Reporting

The A4 result (0.503, and the diagnostic's 0.679) and this amendment are stated at the top of the T20–T22 results
(`results/T20-T22_commodity_trials.md`) and of the Build 0 report.

### A4.4 Vendor history gaps: a roll-rule contract without a settlement

On a decision date where a contract chosen by the roll rule (F1 or F2) has no settlement in the primary source, that
market is treated as **missing that month under §2.1 rule 3** (weight 0; the cross-sectional rank uses the markets
that have values). This is recorded as a data fix for vendor history gaps.

**Where it applies.** Build 0 found 35 such market-months, all for F2 contracts whose Norgate history starts only
5–8 months before expiry:
- **platinum:** 13 months in 2000–2005;
- **palladium:** 22 months in 2000–2009 (palladium is already dropped by the coverage gate, §2.1 rule 1, so it is out
  of every trial regardless).

**Platinum stays in T22,** with weight 0 in those 13 months.

**How A6 changes.** A6's first-settlement assertion is evaluated on the contracts actually used, i.e. those with a
settlement on the decision date. The coverage gate itself is unchanged.

**Not changed.** Everything else, including Amendment 3's roll rule and the other Build 0 tests. The ledger rows
T20–T22 are updated to reference Amendments 3 and 4, changing no other row.
