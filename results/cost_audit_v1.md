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
