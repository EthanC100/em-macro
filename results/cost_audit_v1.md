# Cost audit of the frozen v1.0 systematic strategy

Diagnostic only. No trading logic was changed, no v1.0 file was modified and no new strategy variant was run.
Every number comes from the frozen code (`em_macro/systematic.py`, SHA-256 `1eb4cf6b1c537c17…`, tag
`v1.0-frozen` = `7886867`), called from `em_macro/cost_audit.py`.

- **Why changing costs is not a new variant.** v1.0's costs never feed back into its positions. Selection, sizing,
  volatility targeting, the leverage cap and the no-trade band are all cost-free. Re-running the frozen `run()`
  with a different cost vector leaves every weight unchanged (asserted in the code) and changes only the cost line
  of the P&L.
- **Reproduction.** The inputs were rebuilt in this session. Frozen `evaluate()` on 2020-01..2026-09 reproduces all
  14 rows of `results/systematic/test/performance_2020_on.csv` exactly (maximum absolute difference 0.0 at the file's
  4 decimals). pandas 3.0.5, numpy 2.5.3.
- **Period.** 2020-01 to 2026-09 (81 months), v1.0's test period. Turnover and costs are dated like v1.0's cost
  line: by the month in which the traded position starts earning.
- **Units.** Turnover is one-way notional traded per year, in multiples of capital. Cost drag is in % of capital a
  year (arithmetic). bp = basis points of notional.

Tables: `results/cost_audit/*.csv`. Code: `em_macro/cost_audit.py` (`model`, `sensitivity`, `turnover` stages).

## Step 1 — The cost model v1.0 actually uses

### Where the costs and funding are set

| item | location | what it does |
|---|---|---|
| cost parameters | `em_macro/systematic.py:58-59` (`DESIGN["costs"]`); also `results/systematic/fit/frozen_design.json` | `major` 0.001 (10bp), `high_cost` 0.003 (30bp), `high_cost_countries` TR ID CO CL, `spread_legs` 2 |
| per-instrument map | `em_macro/systematic.py:153-158` (`build_inputs`) | 30bp if the country is TR, ID, CO or CL, else 10bp; spreads over the Bund × 2 legs |
| charge | `em_macro/systematic.py:264-265` (`run`) | cost = \|w_t − w_{t−1}\| × one-way cost, on the weights after the no-trade band, charged in the month the new weight starts earning (t+1 for FX, t+2 for bonds) |
| FX return and funding | `em_macro/systematic.py:118-125` | r = S_{t−1}/S_t × (1 + i_local × τ) − (1 + i_US × τ): local BIS policy rate and US fed funds (FRED DFF), monthly averages of the prior month |
| bond return and funding | `em_macro/systematic.py:131-142` | r = (y − f)/12 − D·Δy + ½·C·Δy²; f = local policy rate (EM 10y), euro-area policy rate (Bund), 0 (spreads over the Bund) |
| net return | `em_macro/systematic.py:266-270` | net = gross − cost; nothing else is added |

### Per-instrument assumptions

**What v1.0 does and does not charge.**
- **Rolls:** none. A position held unchanged pays nothing, although a 1-month forward or NDF has to be rolled every
  month and a bond future every quarter.
- **Bid-ask on forward points:** none. The forward is implied from policy rates, so v1.0 also ignores the NDF–onshore
  basis and the cross-currency basis.
- **Repo:** no repo spread on bond funding.
- **Volatility:** costs do not vary with market volatility.

**Instrument types.** The v1.0 code does not name an execution instrument. The types in the table are the spec §8
mapping (NDF for BRL, COP, CLP and IDR; deliverable forwards for MXN, ZAR, TRY and PLN; G10 forwards for GBP and EUR;
cash bonds or futures for the bonds). They are used only to choose comparable published evidence in Step 2.

| instrument | type (spec §8, assumed) | one-way cost, bp of notional | rule in code | roll cost | funding treatment |
|---|---|---|---|---|---|
| BRL | NDF (1m) | 10 | major | 0 | earns BR policy rate, pays fed funds; no forward points, NDF basis or cross-currency basis |
| MXN | deliverable forward (1m) | 10 | major | 0 | same, MX policy rate |
| ZAR | deliverable forward (1m) | 10 | major | 0 | same, ZA policy rate |
| TRY | deliverable forward (1m) | 30 | high_cost | 0 | same, TR policy rate |
| IDR | NDF (1m) | 30 | high_cost | 0 | same, ID policy rate |
| PLN | deliverable forward (1m) | 10 | major | 0 | same, PL policy rate |
| GBP | G10 forward (1m) | 10 | major | 0 | same, BoE rate |
| COP | NDF (1m) | 30 | high_cost | 0 | same, CO policy rate |
| CLP | NDF (1m) | 30 | high_cost | 0 | same, CL policy rate |
| EUR | G10 forward (1m) | 10 | major | 0 | same, euro-area policy rate |
| BR10Y | EM local 10y bond | 10 | major | 0 | excess over BR policy rate; no repo spread; local-currency return (implicitly FX-hedged) |
| MX10Y | EM local 10y bond | 10 | major | 0 | excess over MX policy rate; as above |
| ZA10Y | EM local 10y bond | 10 | major | 0 | excess over ZA policy rate; as above |
| TR10Y | EM local 10y bond | 30 | high_cost | 0 | excess over TR policy rate; as above |
| ID10Y | EM local 10y bond | 30 | high_cost | 0 | excess over ID policy rate; as above |
| CO10Y | EM local 10y bond | 30 | high_cost | 0 | excess over CO policy rate; as above |
| CL10Y | EM local 10y bond | 30 | high_cost | 0 | excess over CL policy rate; as above |
| FR-DE | 10y spread over Bund (2 legs) | 20 | major × 2 legs | 0 | no funding leg: return = spread/12 − D·Δspread; no repo |
| IT-DE | 10y spread over Bund (2 legs) | 20 | major × 2 legs | 0 | as above |
| ES-DE | 10y spread over Bund (2 legs) | 20 | major × 2 legs | 0 | as above |
| GB-DE | 10y spread over Bund (2 legs) | 20 | major × 2 legs | 0 | as above (the gilt leg's currency is not modelled) |
| PL-DE | 10y spread over Bund (2 legs) | 20 | major × 2 legs | 0 | as above (the Polish bond leg's currency is not modelled) |
| DE10Y | 10y Bund | 10 | major | 0 | excess over the euro-area policy rate; no repo spread |

### Interest on cash collateral

**v1.0's reported returns exclude interest earned on cash collateral.**
- **Excess returns only.** Every instrument return is an excess return: FX over US fed funds, EM bonds over the local
  policy rate, the Bund over the euro-area policy rate. Spreads have no funding leg.
- **Net is gross minus costs.** No T-bill or other cash return is added (`systematic.py:266-270`).
- **What a fully funded account would show.** The spec's paper-return convention (§7) is "instrument excess return +
  T-bill rate on cash". An account would earn that cash rate on top of the reported +6.0% a year.

### Turnover and cost drag by instrument, 2020-01..2026-09

Average gross position is the mean |weight| in the months the position earns.

| instrument | book | average gross position, × capital | turnover, ×/yr | share of turnover % | cost drag, %/yr | share of cost % |
|---|---|---|---|---|---|---|
| FR-DE | bonds | 0.81 | 3.21 | 16.8 | 0.642 | 17.2 |
| ES-DE | bonds | 0.68 | 2.90 | 15.2 | 0.579 | 15.5 |
| GB-DE | bonds | 0.29 | 1.48 | 7.7 | 0.296 | 7.9 |
| IDR | FX | 0.10 | 0.96 | 5.0 | 0.288 | 7.7 |
| IT-DE | bonds | 0.15 | 1.29 | 6.8 | 0.258 | 6.9 |
| COP | FX | 0.10 | 0.77 | 4.1 | 0.232 | 6.2 |
| CLP | FX | 0.06 | 0.69 | 3.6 | 0.208 | 5.6 |
| CL10Y | bonds | 0.15 | 0.66 | 3.4 | 0.197 | 5.3 |
| ID10Y | bonds | 0.19 | 0.50 | 2.6 | 0.150 | 4.0 |
| CO10Y | bonds | 0.19 | 0.49 | 2.6 | 0.147 | 3.9 |
| DE10Y | bonds | 0.46 | 1.12 | 5.9 | 0.112 | 3.0 |
| TR10Y | bonds | 0.08 | 0.31 | 1.6 | 0.092 | 2.5 |
| GBP | FX | 0.29 | 0.74 | 3.9 | 0.074 | 2.0 |
| MX10Y | bonds | 0.15 | 0.71 | 3.7 | 0.071 | 1.9 |
| ZAR | FX | 0.09 | 0.65 | 3.4 | 0.065 | 1.7 |
| PL-DE | bonds | 0.24 | 0.30 | 1.6 | 0.061 | 1.6 |
| EUR | FX | 0.30 | 0.52 | 2.7 | 0.052 | 1.4 |
| BR10Y | bonds | 0.21 | 0.52 | 2.7 | 0.051 | 1.4 |
| TRY | FX | 0.15 | 0.16 | 0.8 | 0.047 | 1.3 |
| PLN | FX | 0.21 | 0.40 | 2.1 | 0.040 | 1.1 |
| MXN | FX | 0.10 | 0.38 | 2.0 | 0.038 | 1.0 |
| BRL | FX | 0.13 | 0.20 | 1.1 | 0.021 | 0.5 |
| ZA10Y | bonds | 0.35 | 0.13 | 0.7 | 0.013 | 0.4 |
| **total** | | 5.48 | 19.09 | 100.0 | 3.734 | 100.0 |

**Totals.**

| measure | FX book | bond book | total |
|---|---|---|---|
| turnover, ×/yr | 5.47 | 13.61 | 19.09 |
| cost drag, %/yr | 1.06 | 2.67 | 3.73 |

**What the totals mean.**
- **Gross and net.** Gross P&L is +9.98% a year (arithmetic) and net +6.25%. Costs take 37% of gross P&L.
- **Average cost.** The average cost per unit traded is 19.6bp.
- **Concentration.** The four European spreads over the Bund (FR, ES, GB, IT) are 46.5% of turnover and 47.5% of
  costs. FR-DE and ES-DE alone are 32% of turnover and 33% of costs.
- **Totals match v1.0.** The per-instrument costs add up exactly to v1.0's cost line: 3.734%/yr, the
  `cost_drag_%_pa` of the committed test table.

## Step 2 — Assumed costs compared with published evidence

### Method

**Definitions.**
- **One-way cost** is half the bid-ask spread (plus impact where the source measures it), in bp of notional.
- **Bonds quoted in yield** are converted as ½ × yield spread × modified duration. Durations used: Bund, OAT, Bono
  and gilt 8.5; BTP 8; Poland 7.5; Mbono, R-series and Indonesia 7; TES 6.5; Chile 8; NTN-F 5.5; Turkey 4.5.
- **Spread trades** sum the country leg and the Bund leg per unit of notional, as v1.0 does.

**How the estimates were set.**
- **Central:** roughly an institutional ticket of about $10m.
- **Low:** an interdealer or best-execution floor.
- **High:** a $25m sweep, or the widest normal-market published level.
- Crisis spikes are listed separately and are not in the high column.

**Evidence quality.**
- A: recent per-instrument data.
- B: indirect or older data, or one source.
- C: only pre-2009 data or a chart reading.
- D: no verified level; inference from comparable markets.

The literature search was delegated to a research sub-task. The key FX tables (MPW Tables 1–2, G&H Table 6) were
checked against the source PDFs.

### Per-instrument estimates (one-way, bp of notional)

| instrument | v1.0 | spec §8 range | low | central | high | quality | v1.0 vs central | main sources |
|---|---|---|---|---|---|---|---|---|
| EUR | 10 | 1–2 | 0.5 | 1.0 | 2.5 | A | above (10×) | MPW T1: EBS half-spread $1m / $10m / $25m 0.47 / 0.80 / 1.29 (2014–18); MRW effective 0.31; G&H forward half-spread 1.15 |
| GBP | 10 | 1–2 | 0.8 | 1.5 | 3.0 | A | above | MPW T1: 0.90 / 1.49 / 2.51; MRW effective 0.81; G&H 1.25 |
| MXN | 10 | 3–6 | 2.5 | 5.0 | 10.0 | A | above | MPW T2: 2.30 / 5.20 / 10.53; G&H 2.75 |
| ZAR | 10 | 3–6 | 5.0 | 9.0 | 20.0 | A | above (by 1bp) | MPW T2: 4.92 / 10.38 / 21.55; G&H 8.3 |
| TRY | 30 | not listed (flagged) | 5.0 | 12.0 | 30.0 | B | above; equal to high | MPW T2: 3.14 / 6.90 / 14.22 (2014–18); G&H 18.6 (2004–08); raised for post-2018 conditions (BIS TRY turnover $71bn in 2019, $27bn in 2022, $55bn in 2025) |
| PLN | 10 | 3–6 | 4.0 | 7.0 | 14.0 | A | above | MPW T2: 3.80 / 7.32 / 13.96 (against EUR) |
| BRL (NDF) | 10 | 5–15 | 5.0 | 10.0 | 20.0 | C | **equal** | G&H 9.65 (WM/R 2004–08) only; range scaled by MPW EM size ratios |
| IDR (NDF) | 30 | 5–15 | 5.0 | 10.0 | 20.0 | C | above | G&H 7.3 (2007–08); G&H say WM/R is too low for IDR |
| COP (NDF) | 30 | 5–15 | 6.0 | 12.0 | 25.0 | C | above | G&H 10.05; G&H say WM/R is too low for COP |
| CLP (NDF) | 30 | 5–15 | 4.0 | 7.0 | 15.0 | C | above | G&H 4.55; G&H say WM/R is too low for CLP |
| BR10Y | 10 | 10–30 | 5.0 | 12.0 | 25.0 | B | **below** | IMF–WB G20 note (2020) Fig. 1: about 5bp yield (2018), i.e. about 14 one-way; CGFS 28: 2.0 (2005) |
| MX10Y | 10 | 10–30 | 4.0 | 7.0 | 15.0 | A | above | IMF WP/20/141 T3: 10y Mbono interdealer 1.4bp yield (2013–20), i.e. about 4.9; G20 chart about 3bp yield, i.e. about 10.5 |
| ZA10Y | 10 | 10–30 | 5.0 | 10.0 | 20.0 | C | **equal** | G20 chart "SA" about 3bp yield, i.e. about 10.5 (the label may mean Saudi Arabia); SARB WP/22/03 (March 2020) |
| TR10Y | 30 | 10–30 | 15.0 | 30.0 | 60.0 | B | **equal** | G20 chart: about 13bp yield (2018), the widest of 13 EMs, i.e. about 29; single source |
| ID10Y | 30 | 10–30 | 10.0 | 15.0 | 30.0 | A | above | ADB AsianBondsOnline surveys: on-the-run 4.1bp yield (2019), i.e. about 14; 30.2 cents of price (2016), i.e. about 15 |
| CO10Y | 30 | 10–30 | 8.0 | 15.0 | 30.0 | D | above | no verified TES level (BanRep reports not reachable); inferred |
| CL10Y | 30 | 10–30 | 8.0 | 15.0 | 30.0 | D | above | CGFS 28: 2.0 (2005) only; thin secondary trading; inferred |
| FR-DE | 20 | 2–4 | 0.9 | 2.0 | 5.0 | B | above (10×) | OAT leg 0.5 / 1.2 / 3 plus Bund leg 0.4 / 0.8 / 2 (Eurex tick 0.01, i.e. about 0.4bp half-tick; Tradeweb 2025) |
| IT-DE | 20 | 2–4 | 0.9 | 2.3 | 7.0 | B | above | BTP leg 0.5 / 1.5 / 5 (ECB FSR Nov-2018 Box 3: MTS 10y spread normally <0.1% of price) plus Bund leg |
| ES-DE | 20 | 2–4 | 0.9 | 2.3 | 6.0 | C | above | Bono leg inferred from OAT and BTP, plus Bund leg |
| GB-DE | 20 | 2–4 | 0.9 | 2.3 | 6.0 | B | above | gilt leg 0.5 / 1.5 / 4 (ICE tick about 1bp; Benos–Zikes 2008–11 effective 6.5bp one-way as upper bound) plus Bund leg; GBP/EUR hedge excluded |
| PL-DE | 20 | 11–32 | 4.4 | 8.8 | 17.0 | B | above | Polish leg 4 / 8 / 15 (G20 chart about 3bp yield, i.e. about 11; CGFS 28: 2.5 in 2005) plus Bund leg |
| DE10Y | 10 | 1–2 | 0.4 | 0.8 | 2.0 | A | above | Eurex FGBL half-tick about 0.4; Tradeweb 10y Bund 0.2bp yield, 0.6 in a sell-off |

**Spec §8 ranges used.**

| instrument group | spec §8 one-way range |
|---|---|
| EUR, GBP (G10 forwards) | 1–2 |
| MXN, ZAR, PLN | 3–6 |
| BRL, COP, CLP, IDR (NDFs) | 5–15 |
| EM local bonds | 10–30 |
| Bund (DM bond futures) | 1–2 |
| spreads over the Bund | country leg plus Bund leg (2–4; PL-DE 11–32) |

The spec gives no TRY figure; it lists TRY with the deliverable forwards and flags it.

**Flags: v1.0's assumption below the central estimate.**

| instrument | v1.0 | central | high | quality | cost share in v1.0 |
|---|---|---|---|---|---|
| BR10Y | 10 | 12 | 25 | B | 1.4% |

**At the central estimate (not below):** BRL (10), ZA10Y (10) and TR10Y (30).

**Below the high estimate:**
- BRL, ZAR, BR10Y, MX10Y, ZA10Y and TR10Y.
- IDR and CLP at 30 are above their highs; COP's high is 25.
- Every EM local bond's high is at least v1.0's figure.

The other 18 instruments are assumed at more than the central estimate. The largest gaps are in the instruments
that dominate v1.0's turnover:
- **Spreads over the Bund:** v1.0 assumes 20bp against a central of 2.0–2.3bp.
- **Bund:** 10 against 0.8.
- **EUR and GBP:** 10 against 1.0–1.5.

**Weighted by turnover (2020-01..2026-09 positions; cost drag ÷ 19.09×/yr turnover).**

| cost vector | average one-way cost per unit traded | cost drag |
|---|---|---|
| v1.0 | 19.6bp | 3.73%/yr |
| literature low | 2.9bp | 0.55%/yr |
| literature central | 5.7bp | 1.09%/yr |
| literature high | 12.4bp | 2.36%/yr |

### Costs v1.0 does not charge at all

**Rolls.**
- **FX forwards and NDFs** must be rolled monthly on the whole position. G&H Table 6 gives annualised 1-month roll
  costs for 2004–08 (WM/R), equal to these monthly amounts in bp:
  - EUR 0.07, GBP 0.09, MXN 0.38, ZAR 0.63, PLN 0.31
  - CLP 1.1, IDR 2.3, TRY 3.5, BRL 4.5, COP 5.8
- G&H say these are too low for IDR, COP and CLP.
- The spec's convention is 0.5 × the one-way cost per roll. Step 3 applies it monthly to FX and quarterly to bond
  positions. At the central estimates this matches or exceeds the G&H levels: for example BRL 5.0 against 4.5 and
  COP 6.0 against 5.8 bp a month.

**Forward points, NDF–onshore basis, cross-currency basis and repo spreads.** v1.0 builds forwards from policy rates,
so none of these are in its returns. They are not costed here: no per-instrument published estimates for 2020–26
were found.

**Stress.** v1.0's costs are constant through time. Published stress episodes:

| episode | what happened | source |
|---|---|---|
| Oct 2008, AUD/USD | top-of-book spread went from 2.64 to 54.03bp | MRW |
| Oct 2008, AUD | effective cost went from 0.9 to 4.1bp | KRS |
| Mar 2020, Mexico | the Mbono market's largest liquidity shock of 2013–20, driven by the bid-ask spread | IMF WP/20/141 |
| Mar 2020, Bund | spread more than doubled | SAFE |
| 29 May 2018, BTP | spread to mid went from <0.1% to >5% of price intraday | ECB FSR |
| 2008–09, gilts | costs about doubled | Benos–Zikes |

### Caveats

- **Interdealer data.** Most recent data are interdealer (EBS/Reuters, MTS, broker quotes). Dealer-to-client
  costs are higher, and the low column is a floor.
- **Units not stated.** Several bond sources do not state units (yield or price): CGFS 28, the G20 chart and
  Tradeweb. The conversions assume yield.
- **NDF currencies.** BRL, IDR, COP and CLP rest on 2004–08 WM/R data, which G&H themselves call too low for three
  of the four.
- **Colombian and Chilean bonds.** These have no verified level (quality D).
- **Sources not reached.** Menkhoff et al. (2012) directly (the 50%-of-quoted haircut is confirmed only through
  MPW's footnote 8), Hasbrouck–Levich per-currency levels, Fleming, Pelizzon et al., Jeanneau–Tovar, and Su and
  Tokmakcioglu (2021) on Turkish bonds.

### References

- **MPW20:** Melvin, Pan and Wikstrom (2020), "Retaining Alpha: The Effect of Trade Size and Rebalancing Frequency
  on FX Strategy Returns", CESifo WP 8143. Tables 1–2: EBS/Reuters sweep-to-fill half-spreads, 2014-01..2018-03.
  https://www.ifo.de/DocDL/cesifo1_wp8143.pdf
- **GH11:** Gilmore and Hayashi (2011), "Emerging Market Currency Excess Returns", AEJ: Macroeconomics 3(4).
  Working version FS-2011-E-002, Table 6: WM/R bid/offer and roll costs, 2004-03..2008-06.
  https://www.sba.hub.hit-u.ac.jp/assets/files/research/fs_wp/FS-2011-E-002.pdf
- **MRW13:** Mancini, Ranaldo and Wrampelmeyer (2013), "Liquidity in the Foreign Exchange Market", JF 68(5).
  Table I (EBS 2007–09).
- **KRS15:** Karnaukh, Ranaldo and Söderlind (2015), "Understanding FX Liquidity", RFS 28(11). Table 1 of the 2013
  draft (EBS 2007–12).
- **BIS Triennial Survey 2025:** statistical annex, Table 25.2.
  https://www.bis.org/publications/commentary-otc-derivatives/statistics-rpfx25-fx-annex.pdf
- **IMF–World Bank (2020):** G20 IFAWG staff note, "Recent Developments on Local Currency Bond Markets in Emerging
  Economies", Figure 1. Average bid-offer on 10-year benchmarks, 2018; values read off the chart.
- **IMF WP/20/141:** Hoyos, Liu, Miao and Saborowski (2020), Table 3. Mbono spreads, 2013-01..2020-03.
- **ADB AsianBondsOnline:** bond market liquidity surveys, Nov 2016 and Nov 2019, Table 8 (Indonesia).
- **CGFS 28:** BIS CGFS Papers No 28 (2007), "Financial stability and local currency bond markets", annex table 10.
- **ECB FSR:** ECB Financial Stability Review, Nov 2018, Box 3 (MTS BTP spreads).
- **SAFE:** Moench, Pelizzon and Schneider, SAFE Finance Blog (2020), "Market liquidity of European sovereign bonds
  during the COVID-19 crisis".
- **Tradeweb via fi-desk:** Barnes (2025), fi-desk. Tradeweb Bund and BTP spreads; trade press.
- **Benos–Zikes:** Benos and Zikes (2014 draft), "Liquidity and Dealer Activity in the UK Gilt Market During the
  Financial Crisis". Quoted and effective spreads, 2008–11.
- **SARB WP/22/03:** Havemann et al. (2022).
- **GFXC (2020):** "Overview of market conditions".
- **Exchange specifications:** Eurex FGBL / FOAT / FBTP / FBON, and ICE Long Gilt.

Table: `results/cost_audit/cost_estimates.csv`.

## Step 3 — v1.0's 2020-01..2026-09 performance under different costs

**How the runs were done.**
- **Frozen code, same positions.** Every row is the frozen `systematic.run()` on the same positions, with only the
  per-instrument cost vector changed (asserted: the weights are identical in every run).
- **Linear in costs.** Net = gross − m × cost. The rows match that identity to 1e-17. Break-even multiples are found
  by root-finding on it.
- **Statistic definitions** are those of `systematic.stats`: Sharpe = mean/SD × √12 of monthly net returns; return
  compounded; max drawdown on the compounded monthly index.
- **"+ roll costs"** adds, outside the frozen code, the spec §8 roll convention: 0.5 × the one-way cost on the whole
  position, monthly for FX and quarterly for bonds. It is charged on v1.0's positions.

### Cost sensitivity, 2020-01..2026-09 (81 months)

| scenario | Sharpe | return %/yr | max drawdown % | vol %/yr | cost drag %/yr |
|---|---|---|---|---|---|
| 0× (gross) | 1.04 | 9.96 | -16.7 | 9.62 | 0.00 |
| 0.5× v1.0 costs | 0.85 | 7.94 | -17.4 | 9.58 | 1.87 |
| **1× v1.0 costs (reported)** | **0.65** | **5.96** | **-18.5** | 9.56 | 3.73 |
| 1.5× v1.0 costs | 0.46 | 4.01 | -20.3 | 9.57 | 5.60 |
| 2× v1.0 costs | 0.26 | 2.08 | -22.1 | 9.59 | 7.47 |
| 2.5× v1.0 costs | 0.07 | 0.19 | -23.9 | 9.63 | 9.34 |
| 3× v1.0 costs | -0.13 | -1.67 | -25.7 | 9.70 | 11.20 |
| literature low (per instrument) | 0.98 | 9.36 | -17.0 | 9.62 | 0.55 |
| literature central (per instrument) | 0.92 | 8.77 | -17.3 | 9.62 | 1.09 |
| literature high (per instrument) | 0.79 | 7.41 | -18.0 | 9.62 | 2.36 |
| literature low + roll costs | 0.93 | 8.79 | -17.2 | 9.61 | 1.08 |
| literature central + roll costs | 0.82 | 7.65 | -17.7 | 9.61 | 2.14 |
| literature high + roll costs | 0.56 | 5.04 | -20.4 | 9.60 | 4.60 |

### Break-even cost multiples

| period | Sharpe at 0× | Sharpe at 1× | multiple of v1.0 costs for Sharpe = 0 | for Sharpe = 0.3 | multiple of literature central for Sharpe = 0 | for Sharpe = 0.3 | multiple of central + rolls for Sharpe = 0 | for Sharpe = 0.3 |
|---|---|---|---|---|---|---|---|---|
| **2020-01..2026-09** | 1.04 | 0.65 | **2.67×** | **1.90×** | 9.1× | 6.5× | 4.7× | 3.3× |
| 2005-2019 (design, context) | 0.93 | 0.40 | 1.75× | 1.18× | 5.9× | 4.0× | 3.5× | 2.4× |

**The same break-evens as an average cost per unit traded (turnover-weighted).**

| Sharpe target | average one-way cost, 2020-01..2026-09 | average one-way cost, 2005-2019 |
|---|---|---|
| 0 | 52bp | 34bp |
| 0.3 | 37bp | 23bp |

v1.0's own vector averages 19.6bp.

### Finer grid, multiples of v1.0's costs, 2020-01..2026-09

| multiple | Sharpe | return %/yr | max drawdown % |
|---|---|---|---|
| 0.00 | 1.038 | 9.96 | -16.7 |
| 0.25 | 0.943 | 8.95 | -17.1 |
| 0.50 | 0.847 | 7.94 | -17.4 |
| 0.75 | 0.751 | 6.95 | -17.8 |
| 1.00 | 0.654 | 5.96 | -18.5 |
| 1.25 | 0.556 | 4.98 | -19.4 |
| 1.50 | 0.458 | 4.01 | -20.3 |
| 1.75 | 0.360 | 3.04 | -21.2 |
| 2.00 | 0.262 | 2.08 | -22.1 |
| 2.25 | 0.165 | 1.13 | -23.0 |
| 2.50 | 0.067 | 0.19 | -23.9 |
| 2.75 | -0.029 | -0.74 | -24.8 |
| 3.00 | -0.126 | -1.67 | -25.7 |

### Design sample, 2005-2019 (context only; v1.0 was designed on it)

| scenario | Sharpe | return %/yr | max drawdown % | cost drag %/yr |
|---|---|---|---|---|
| 0× (gross) | 0.93 | 9.23 | -11.6 | 0.00 |
| 0.5× | 0.66 | 6.36 | -12.4 | 2.67 |
| 1× | 0.40 | 3.56 | -13.8 | 5.35 |
| 1.5× | 0.13 | 0.82 | -19.7 | 8.02 |
| 2× | -0.13 | -1.85 | -28.3 | 10.69 |
| 3× | -0.63 | -7.01 | -64.3 | 16.04 |
| literature low | 0.85 | 8.37 | -11.9 | 0.79 |
| literature central | 0.77 | 7.51 | -12.2 | 1.60 |
| literature high | 0.58 | 5.53 | -12.9 | 3.46 |
| literature central + roll costs | 0.67 | 6.39 | -12.7 | 2.65 |
| literature high + roll costs | 0.36 | 3.17 | -15.1 | 5.72 |

**Consistency with earlier reports.** The 1× and 2× rows match `results/T01_ts_trend.md`: Sharpe 0.65 and 0.26 in
2020-01..2026-09, and 0.40 and −0.13 in 2005–2019.

**Scope of these figures.** They exclude interest on cash collateral (Step 1). They also exclude the uncosted items
in Step 2: forward-point spreads beyond the roll convention, the NDF and cross-currency bases, repo spreads and
stress widening.

Tables: `results/cost_audit/step3_sensitivity.csv`, `step3_grid.csv`, `step3_breakeven.json`.

## Step 4 — Where v1.0's turnover comes from

### Method

The method is an accounting of v1.0's executed trades. It uses the frozen functions; no alternative rule is run.

**How v1.0 sizes a position.** In v1.0 a signal decides only whether an instrument is long, short or flat (top
third, bottom third). Size is set by volatility:

target_i = sign × (1/σ_i) × book vol scaler × ½ × portfolio vol scaler × leverage-cap factor.

**Rebuilding the components.** Each component is rebuilt from the frozen code and checked to reproduce v1.0's
weights exactly:
- `systematic._vol`, `book_weights`;
- `run(band=0)` for the pre-band targets, which is the identical code path up to the band;
- `_apply_band` for the executed weights.

**How each trade is classified.** Every executed trade (a change in the post-band weight) is one of two kinds:
- **Selection change (signal):** entry, exit or sign flip. The whole trade is attributed to the signal.
  - These trades are further split by which signal's z-score moved: each signal's absolute change in its share of
    the composite, z_k/K, between t−1 and t.
  - This is approximate, because ranks are cross-sectional and other instruments' moves also matter.
- **Resize (volatility rescaling):** same sign, size changed enough to clear the 25% band. It is split exactly by a
  log-mean Divisia (LMDI) decomposition into four components, measured from the position's last trade:
  - instrument volatility;
  - book vol scaler;
  - portfolio vol scaler;
  - leverage cap.
  - These shares are signed and sum to the trade.

**No-trade band.** Its effect is the difference between the turnover of the pre-band targets and the executed
turnover. Dating is as in Step 1, and totals reconcile exactly to 19.09×/yr.

### Executed turnover by source, 2020-01..2026-09

| source | turnover ×/yr | share % |
|---|---|---|
| **signal: selection changes** (entries, exits, flips) | **17.44** | **91.4** |
| volatility rescaling: instrument vol (1/σ_i) | 0.43 | 2.2 |
| volatility rescaling: book vol scaler | 0.67 | 3.5 |
| volatility rescaling: portfolio vol scaler | 0.13 | 0.7 |
| volatility rescaling: 6× leverage cap | 0.42 | 2.2 |
| **total executed** | **19.09** | 100 |

| trade type | trades | turnover ×/yr | share % |
|---|---|---|---|
| entry | 138 | 8.73 | 45.8 |
| exit | 138 | 8.69 | 45.5 |
| sign flip | 1 | 0.03 | 0.1 |
| resize | 92 | 1.64 | 8.6 |

**By book (×/yr).**

| book | selection | instrument vol | book scaler | portfolio scaler | leverage cap | total |
|---|---|---|---|---|---|---|
| FX | 4.87 | 0.11 | 0.11 | -0.07 | 0.46 | 5.47 |
| bonds | 12.58 | 0.32 | 0.56 | 0.20 | -0.04 | 13.61 |

**Selection turnover by which signal moved (approximate, ×/yr).**

| book | carry | trend | value | total selection |
|---|---|---|---|---|
| FX | 0.45 | 2.99 | 1.43 | 4.87 |
| bonds | 2.47 | 6.91 | 3.13 | 12.58 |
| **total** | **2.92 (17%)** | **9.90 (57%)** | **4.56 (26%)** | 17.44 |

0.06×/yr of bond selection turnover could not be attributed: no signal change was recorded at the decision date.

### The no-trade band

| path | selection ×/yr | resize ×/yr | total ×/yr |
|---|---|---|---|
| pre-band targets (all target changes traded) | 17.38 | 4.46 | 21.84 |
| executed (25% band) | 17.44 | 1.64 | 19.09 |
| difference | +0.07 | −2.82 | **−2.76 (−12.6%)** |

**What the band does.**
- **Turnover.** Exits and sign changes always trade, so the band acts only on resizes. It removes 63% of
  resize turnover and 12.6% of total turnover.
- **Selection turnover.** This is slightly higher with the band, because exits close positions that the band had
  left at stale sizes.
- **Leverage cap.** The 6× cap binds in 42 of the 81 decision months.

### Turnover by instrument, 2020-01..2026-09

| instrument | turnover ×/yr | share % | average gross position × | turnover per unit held | trades | selection trades/yr | from selection % | months held inside band | band-suppressed ×/yr |
|---|---|---|---|---|---|---|---|---|---|
| FR-DE | 3.21 | 16.8 | 0.81 | 4.0 | 15 | 1.6 | 92 | 33 | 0.19 |
| ES-DE | 2.90 | 15.2 | 0.68 | 4.3 | 18 | 2.4 | 96 | 38 | 0.36 |
| GB-DE | 1.48 | 7.7 | 0.29 | 5.1 | 16 | 2.2 | 99 | 25 | 0.05 |
| IT-DE | 1.29 | 6.8 | 0.15 | 8.5 | 18 | 2.2 | 95 | 17 | 0.03 |
| DE10Y | 1.12 | 5.9 | 0.46 | 2.4 | 18 | 2.1 | 89 | 52 | 0.21 |
| IDR | 0.96 | 5.0 | 0.10 | 9.3 | 22 | 2.8 | 95 | 11 | 0.04 |
| COP | 0.77 | 4.1 | 0.10 | 7.6 | 26 | 3.6 | 97 | 24 | 0.07 |
| GBP | 0.74 | 3.9 | 0.29 | 2.6 | 18 | 1.9 | 87 | 56 | 0.24 |
| MX10Y | 0.71 | 3.7 | 0.15 | 4.7 | 12 | 1.8 | 100 | 24 | 0.10 |
| CLP | 0.69 | 3.6 | 0.06 | 11.2 | 24 | 3.4 | 98 | 12 | 0.01 |
| CL10Y | 0.66 | 3.4 | 0.15 | 4.3 | 14 | 1.8 | 95 | 29 | 0.08 |
| ZAR | 0.65 | 3.4 | 0.09 | 7.2 | 21 | 3.0 | 99 | 25 | 0.06 |
| EUR | 0.52 | 2.7 | 0.30 | 1.7 | 13 | 1.2 | 82 | 54 | 0.22 |
| BR10Y | 0.52 | 2.7 | 0.21 | 2.5 | 21 | 1.9 | 81 | 51 | 0.08 |
| ID10Y | 0.50 | 2.6 | 0.19 | 2.7 | 9 | 1.0 | 94 | 38 | 0.11 |
| CO10Y | 0.49 | 2.6 | 0.19 | 2.6 | 15 | 1.8 | 94 | 50 | 0.11 |
| PLN | 0.40 | 2.1 | 0.21 | 1.9 | 15 | 1.2 | 78 | 61 | 0.14 |
| MXN | 0.38 | 2.0 | 0.10 | 3.8 | 14 | 1.3 | 85 | 21 | 0.03 |
| TR10Y | 0.31 | 1.6 | 0.08 | 3.7 | 20 | 2.4 | 93 | 53 | 0.03 |
| PL-DE | 0.30 | 1.6 | 0.24 | 1.3 | 9 | 0.3 | 62 | 44 | 0.12 |
| BRL | 0.20 | 1.1 | 0.13 | 1.5 | 12 | 0.9 | 67 | 48 | 0.13 |
| TRY | 0.16 | 0.8 | 0.15 | 1.1 | 12 | 0.3 | 29 | 63 | 0.12 |
| ZA10Y | 0.13 | 0.7 | 0.35 | 0.4 | 7 | 0.0 | 0 | 74 | 0.21 |

**Column definitions.**
- **Turnover per unit held** = turnover ÷ average |position|.
- **Selection trades per year** counts entries, exits and flips.
- **Months held inside band** counts months in which the held position differed from a same-sign target.

### Turnover by year (×/yr; 2026 annualised from January–September)

| year | selection | instrument vol | book scaler | portfolio scaler | leverage cap | total |
|---|---|---|---|---|---|---|
| 2020 | 11.58 | 0.59 | 0.15 | 0.12 | 0.20 | 12.64 |
| 2021 | 13.63 | 0.32 | 0.65 | 0.60 | 0.30 | 15.50 |
| 2022 | 14.07 | 0.43 | 0.40 | 0.38 | 0.04 | 15.33 |
| 2023 | 23.40 | 0.80 | 0.07 | 0.37 | 0.00 | 24.64 |
| 2024 | 24.16 | 0.18 | 1.34 | 0.14 | -0.12 | 25.70 |
| 2025 | 28.74 | 0.31 | 1.27 | -0.54 | 2.17 | 31.96 |
| 2026 | 17.19 | 0.79 | 1.22 | -0.01 | 0.42 | 19.62 |

Tables: `results/cost_audit/step4_*.csv`, `step4_meta.json`.

## Summary (factual; no recommendations)

- **Cost model.**
  - v1.0 charges a flat one-way cost on traded notional: 10bp, or 30bp for TR, ID, CO and CL; spreads over the
    Bund pay two legs (20bp). The parameters are set in `systematic.py:58-59` and `:153-158`, and charged at
    `:264-265`.
  - It charges no roll costs and no forward-point, NDF-basis or repo spreads, and costs do not vary with volatility.
- **Cash collateral.** Reported returns exclude interest on cash collateral. All returns are excess returns over
  the funding rate, and net = gross − costs.
- **Turnover and cost drag, 2020-01..2026-09.**
  - Turnover is 19.1× capital a year (FX 5.5×, bonds 13.6×) and cost drag is 3.73% a year, 37% of the gross
    P&L of 9.98% a year (arithmetic).
  - The spreads over the Bund for FR, ES, GB and IT are 47% of turnover and 48% of costs; FR-DE and ES-DE alone are
    33% of costs.
- **Against published evidence.**
  - Of 23 instruments, only BR10Y is assumed below the central estimate (10bp against 12bp; 1.4% of v1.0's costs).
    BRL, ZA10Y and TR10Y equal it.
  - v1.0's assumptions are 5–25× the central estimates for the G10 currencies, the Bund and the spreads over the
    Bund, which account for most of v1.0's turnover.
  - The NDF currencies (BRL, IDR, COP, CLP) and the Colombian, Chilean and Turkish bonds rest on old or indirect
    evidence (quality C–D).
  - Turnover-weighted average cost per unit traded: v1.0 19.6bp; literature low 2.9bp, central 5.7bp, high 12.4bp.
- **Sensitivity, 2020-01..2026-09.**

  | costs | Sharpe | return %/yr |
  |---|---|---|
  | 0.5× | 0.85 | 7.9 |
  | 1× | 0.65 | 6.0 |
  | 1.5× | 0.46 | 4.0 |
  | 2× | 0.26 | 2.1 |
  | 3× | −0.13 | −1.7 |
  | literature central | 0.92 | 8.8 |
  | literature central with rolls | 0.82 | 7.6 |
  | literature high with rolls | 0.56 | 5.0 |

  - Max drawdown ranges from −17.0% (literature low) to −25.7% (3×).
- **Break-even.**
  - The Sharpe reaches zero at **2.67×** v1.0's costs (about 52bp average one-way) and falls below 0.3 at
    **1.90×** (about 37bp).
  - In the 2005–2019 design sample the multiples are 1.75× and 1.18×.
- **Turnover sources.**
  - 91% of executed turnover is entries and exits of positions as signal ranks change. Volatility rescaling is 9%:
    instrument vol 2.2%, book scaler 3.5%, portfolio scaler 0.7% and leverage cap 2.2%.
  - The trend z-score is the largest mover behind selection trades (57%), then value (26%) and carry (17%).
  - The 25% band removes 2.8×/yr (12.6%) of target turnover, all of it in resizes.
  - Turnover rose from 12.6×/yr in 2020 to 32.0×/yr in 2025.
  - Per unit held, CLP, IDR, IT-DE, COP and ZAR trade most (7–11× their average position a year).
