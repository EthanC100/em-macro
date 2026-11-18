# Synthetic futures execution, cost and roll model

Version 0.1, 2026-11-18 (Project Manhattan, session 4). Code: `manhattan/execution/`. Tests:
`tests/test_manhattan_execution.py`.

**What this is.** A deterministic, pure-function model of how a futures position plan turns into gross and net P&L:
contract months, ticks, multipliers, fees, spread, slippage, impact, liquidity caps, rolls, FX, margin funding,
turnover and exposure. It is research infrastructure for synthetic inputs.

**What this is not.** It is not calibrated: every cost number is caller-supplied and labelled `synthetic` or
`caller-supplied`, and the model refuses the label "calibrated". It places no order, connects to no broker or
exchange, reads no file, environment variable or network, and holds no market data. Nothing imports it: not the
engine (`manhattan/engine/`), the operational runner and Store (`manhattan/ops/`), the Ledger, Janus or the night
shift. It writes no ledger record, so nothing it computes is an attempt, evidence, a screening result, a claim or a
trade. It changes no statistical rule, threshold, attempt-accounting rule, reserve switch or protected file
(`config/manhattan.yaml` keeps `forward.real_money: false`, `claims.enabled: false`, `reserve.enabled: false`; a
test checks that running the model leaves that file byte-for-byte unchanged).

## 0. What exists already, and where this sits

| existing | what it models | relation |
|---|---|---|
| `manhattan/engine/accounting.py`, `backtest.py` | weights in, daily net return out; one-way **proportional** cost per instrument; marks are excess-return indexes | unchanged. This model works one level below it, in contracts and settlement prices; section 16 is the interface |
| `ledger/janus_fut.py` | Janus's live paper futures: cost per side = 2 × (US$3 + one tick); notice-date roll with 35/10-day buffers; P&L on held contracts | production; not imported. The roll rule here is the same rule, with the buffers caller-supplied |
| `ledger/settlements.py` `CONTRACTS` | twelve real contract specifications (tick, multiplier) | production metadata; not imported. Section 16 shows how it could be mapped onto `ContractSpec` |
| `ledger/capacity.py` | square-root impact `Y σ_daily sqrt(Q/ADV)` as a fraction of notional, ADV cap 10% | the same functional form, here in **price points** (so it works at zero or negative prices) and with every coefficient caller-supplied |
| `em_macro/commod_data.py`, commodities spec §2.3 | chained same-contract excess-return index, no back-adjustment; notice-based roll | `adjust.build(..., "chained")` reproduces the convention for comparison |

## 1. Contract identifiers and metadata

`ContractSpec` (frozen dataclass), one per listed contract month:

| field | unit | rule |
|---|---|---|
| `contract_id` | `<ROOT><month code><YYYY>`, e.g. `SYNAH2027` | must equal `contract_id(root, delivery_month)`; two-digit years are refused (`CLH7` is ambiguous) |
| `root`, `exchange` | text | non-empty; root upper-case alphanumeric |
| `delivery_month` | `YYYY-MM` | |
| `currency` | ISO-4217-style code | three upper-case letters; `usd`, `US$`, `USc` are refused |
| `tick_size` | price units | > 0 |
| `tick_value` | currency per tick per contract | must equal `tick_size × multiplier × price_unit_value` (relative tolerance 1e-9) |
| `multiplier` | underlying units per contract | > 0 |
| `price_unit_value` | currency per price unit per underlying unit | 1.0 for a dollar quote, 0.01 for a cents quote |
| `first_trade`, `last_trade` | dates | the contract's trading life |
| `settlement_type` | `physical` / `cash` | a physical contract must give `first_notice` |
| `first_notice` | date or None | |
| `initial_margin` | currency per contract, or None | caller-supplied; required only when margin is reported or funded |

`point_value = multiplier × price_unit_value`; `notice = min(first_notice, last_trade)`.

## 2. Tick size, tick value, currency and multiplier

The tick-value consistency check is the unit guard: a cents-quoted contract described with `price_unit_value = 1.0`
(a factor-of-100 error) fails at construction. Settlements must lie on the tick grid (tolerance 1e-9 ticks for
binary floating point); an off-tick settlement is refused as a probable unit error. Tick arithmetic is done in
`Decimal` on `repr` of the floats, so `70.23` stays `70.23`. Negative prices are allowed (they have happened); every
price-based quantity is computed in points, so nothing divides by a price except the optional fraction-of-notional
outputs, which use `|price|`.

## 3. Explicit commissions and exchange fees

`CostTerms.commission_per_contract` and `exchange_fee_per_contract`, both in `fee_currency` per contract **per side**.
A round trip pays them twice; a roll pays them on both legs. Fees are charged on contracts actually filled, never on
an unfilled remainder. They are reported separately from the price-moving costs.

## 4. Bid-ask spread

`half_spread_ticks`: the distance from the reference price (the settlement) to the touch, in ticks of the contract.
A buy pays `+half_spread_ticks × tick_size`, a sell `−`. Using ticks makes one scenario meaningful across contracts
with different tick sizes; nothing converts a spread in basis points into ticks (that would hide a price-level
assumption).

## 5. Slippage and market impact

* `slippage_ticks`: a further fixed number of ticks beyond the touch.
* Impact: `impact_coefficient × daily_vol_points × sqrt(|q| / adv_contracts)`, in price points, where
  `daily_vol_points` and `adv_contracts` come from the caller's `Liquidity` estimate known at the decision. The
  functional form is the square-root law already used in `ledger/capacity.py`; the coefficient has no default.
* The sum is rounded to the tick grid **against the trader** (buy up, sell down); the rounding is its own cost line.

Per fill: `execution cost = (fill − reference) × q × point_value = spread + slippage + impact + rounding`, all ≥ 0
for longs and shorts alike. The four parts add up exactly to the price difference; a test checks this.

## 6. Order sizing and liquidity constraints

Orders are signed whole contracts (`int`; floats, including `2.0`, and booleans are refused). At most
`floor(max_participation × adv_contracts)` contracts per contract per day. Policies:

* `on_liquidity_shortfall = "raise"` (default): an order above the cap stops the run (`LiquidityError`).
* `"clip"`: the cap is filled, the remainder is recorded as `Unfilled` and worked on the next trading day (reason
  `carry`) until the target is reached or replaced by a new decision.

ADV = 0 allows nothing (`raise` refuses; `clip` fills zero and charges nothing). A very large ADV drives impact to
zero; spread, slippage, rounding and fees remain.

## 7. Futures expiry and contract rolls

Decisions name a **root** and a signed target in contracts; the roll rule picks the month, from metadata only:

* **Open** in the earliest listed contract whose notice date is more than `buffer_days` after the trade day.
* **Roll** at the settlement of the first trading day on which the held contract is `roll_before_notice_days` or
  fewer calendar days from its notice. `buffer_days > roll_before_notice_days` is enforced.

A roll is two orders, each paying spread, slippage, impact and fees once. It is treated as a calendar spread: the
old month is never closed faster than the new month can absorb (under `clip`), and the new month is never opened
beyond what was closed, so exposure neither lapses nor doubles; a roll whose new month has no settlement waits. A
contract still held after its last trading day stops the run (`InvalidContractError`); so does a day on which no
listed contract qualifies.

## 8. Continuous-price-series limitations

**A continuous adjusted price is never tradable here.** `manhattan.execution.adjust` builds four continuous series
for comparison only (`spliced`, `difference`, `ratio`, `chained`), as `AdjustedSeries` / `AdjustedPoint` objects with
`tradable = False`. `MarketData` and `fill_order` accept only `Settlement` objects and raise `TypeError` for an
adjusted value. What each gets wrong, checked in tests:

| series | point changes | percentage changes | level |
|---|---|---|---|
| spliced (unadjusted) | wrong on roll days (books the calendar gap) | wrong on roll days | the held month's real price |
| difference back-adjusted | equal to the held contract's | wrong | not a price; drifts, can go negative |
| ratio back-adjusted | wrong | equal to the held contract's | not a price |
| chained return index | n/a | equal to the held contract's | an index, not a price |

The accounting never uses any of them: it marks each held contract to its own settlement.

## 9. Roll yield versus artificial price adjustments

P&L is `Σ q × (S_t − S_{t−1}) × point_value` on the contract actually held over each period. Roll yield (the
convergence of a contract toward the spot along the curve) is therefore inside the gross; nothing is booked for the
price difference between two months at a roll. Each `RollEvent` reports that difference as `calendar_gap_points`:
it is the jump a spliced series would show, **not** P&L. A test checks that the gross on the roll day is the held
contract's own change and that a spliced series would have added the gap.

## 10. Trading calendars and timestamp conventions

* The calendar is a caller-supplied sequence of `TradingDay(day, close_at)`, strictly increasing in both.
* Every timestamp is a timezone-aware `datetime`, converted to UTC. A naive datetime, or a `date` where a time is
  needed, is refused (`TimestampError`).
* A `Settlement` must be stamped `known_at ≥` its day's `close_at`, must fall on a calendar day and inside the
  contract's life.
* A decision taken at `decided_at` executes at the settlement of the `lag`-th trading day (`lag ≥ 1`) whose close
  is **strictly after** `decided_at`. A decision exactly at a close executes the next day. So no decision ever
  trades at a price that was already printed when it was taken.
* `Decision.inputs_known_at` (optional) later than `decided_at` is a `LookAheadError`. Liquidity is the latest
  estimate with `known_at ≤ decided_at`; for rolls and carried remainders, `≤` the previous day's close. A later
  estimate is never used, even when it would make the order feasible (tested).
* The roll rule reads only contract dates fixed at listing, never volume, open interest or prices.
* Decisions that could only execute after the last calendar day are returned in `unexecuted`, not executed.

## 11. Portfolio turnover and exposure

Per day, in the base currency: `turnover = Σ |filled| × |reference| × point_value × FX` (each contract traded counts
once per side; a roll counts both legs), `gross_exposure = Σ |q × S × point_value × FX|` and
`net_exposure = Σ q × S × point_value × FX` after the close, and the positions by contract. With `capital` given,
totals are also reported as fractions of a fixed capital (no compounding).

## 12. Financing and margin

Futures need no financing of their notional; returns are excess of cash (Protocol 3.1 §2.1). Two optional, explicit
items:

* `margin` (base currency) after each close = `Σ |q| × initial_margin × FX`, reported when every held contract has
  an `initial_margin` (otherwise `None`, never zero) and required when `report_margin=True`.
* `margin_funding_bps_per_year` in the cost terms: `|q| × initial_margin × bp / 10,000 × calendar days / 365` on the
  margin held over each period, as its own cost line. Missing margin with a non-zero funding rate is an error.

Interest earned on collateral, variation-margin timing and margin calls are not modelled.

## 13. Currency conversion and FX exposure

`FxRate(base, quote, day, rate, known_at)`: `rate` units of `quote` per one `base`. Conversion uses that day's
direct pair or its inverse; it never crosses through a third currency and never borrows another day's rate. A
missing rate is an error whenever a foreign-currency amount (P&L, fee, exposure, margin) has to be converted, even a
zero amount. Daily P&L is converted at the day's rate and assumed swept into the base currency, so the futures carry
no FX exposure beyond the day's variation margin and any margin posted in a foreign currency; that sweep is an
assumption, stated here, not a measurement.

## 14. Missing data and invalid contracts

Conservative by default (`on_missing_price="raise"`): a held or traded contract with no settlement on a calendar day
stops the run. Under `"hold"`, a held contract keeps its last mark (`stale_marks` lists it), the whole gap's P&L is
booked when its price returns, and trades in it wait. Missing contract metadata, missing cost terms for a root,
missing liquidity, missing FX and missing margin (when needed) always stop the run. A contract traded before its
first trade day or after its last, or held past its last trade day, is an `InvalidContractError`.

## 15. Determinism, reproducibility and sensitivity

No randomness, no clock, no I/O. Inputs are sorted before use, so the order of decisions and of scenarios does not
change the output. `Result.result_hash()` is the SHA-256 of a canonical JSON form (amounts rounded to 8 decimals).
`CostScenario.scenario_id()` is a content address (`AC-` + 16 hex of the `manhattan.spec` canonical hash), suitable
as an executable's `cost_model_id`. `run_scenarios` runs one plan under several scenarios; `sensitivity_table` gives
one row of totals per scenario with its id and result hash. `CostScenario.scaled(k)` multiplies every price-moving
cost and fee by `k` (the participation cap is unchanged), for multiples such as the repository's usual 2× test.

## 16. Future integration with the research engine (not built)

Nothing here changes `manhattan/engine/` or `manhattan/ops/`; the engine's code hash (`evaluate.code_version`)
covers only `manhattan/engine/*.py` and is unchanged. When Ethan decides to connect them, the boundary would be:

1. **Binding.** An executable's `cost_model_id` names a `CostScenario.scenario_id()`; the scenario's JSON is stored
   with the batch specs like any other spec, so it is frozen by the batch hash.
2. **Inputs.** A research script builds `ContractSpec` rows from contract metadata (for the real twelve products,
   from `ledger/settlements.CONTRACTS` mapped field by field: `tick → tick_size`, `tick_value`, `multiplier`, and
   `price_unit_value = 1.0` for every product, because that table's `multiplier` is already US$ per price point:
   for the cents-quoted grains it is 50, not 5,000 bushels; `price_unit_value = 0.01` there would be the
   factor-of-100 error, and the tick-value check refuses it, as a test shows) and `Settlement`, `Liquidity` and `FxRate`
   objects from the private store, through the engine's point-in-time `Window` so every `known_at` comes from the
   availability record. Licensed settlement rows stay in the private store (hard rule 7).
3. **Signal.** The engine's signal produces weights; a sizing step outside this package converts them to whole
   contracts (`round(weight × capital / (S × point_value × FX))`), stamped with the decision time.
4. **Output.** `Result.days[k].net / capital` is a daily net return in excess of cash, the quantity Protocol 3.1
   §2.1 calls `r_{x,t}`; it could replace the engine's proportional-cost accounting for futures executables, or be
   compared with it. `one_way_cost_fraction` gives the proportional cost equivalent to one fill at one price and size,
   for comparison with `Instrument.cost`; it is exact only there.
5. **Records.** The engine, not this package, would write the ledger record, with the result hash of the engine's
   own series. This package would stay pure.

Each of these is a change to the engine, the ops runner or the protocol and is Ethan's to approve; none is made here.

## 17. Cost assumptions

There are none in the code. Every cost is an input. The tests use clearly synthetic terms on made-up roots (`SYNA`,
`SYNC`, `SYNE` on exchange `SYNX`): for example a commission of 1.0 and an exchange fee of 0.5 per contract per side,
half a tick of half-spread and half a tick of slippage, 10% of ADV. These numbers were chosen to make the arithmetic
easy to check by hand; they describe no market. Protocol 3.1 §10 already names the estimator a measured cost model
would need (median recorded half-spreads and fees over 12 months); this package does not implement or replace it.

## 18. Limitations

* **Not calibrated, not validated against fills.** No output is evidence that any cost level is realistic.
* **Daily settlement granularity.** Fills are at the execution day's settlement plus modelled costs; there is no
  intraday path, no queue position, no partial fills inside a day beyond the participation cap.
* **Impact is static and temporary.** The square-root form applies per day and contract; it has no decay, no
  permanent component, no cross-impact between contracts and no dependence on the order of trades in a day.
* **Liquidity is the caller's estimate.** ADV and volatility are whatever the caller supplies, as of when they
  supply them.
* **One rule for every roll.** The notice-date rule with fixed buffers; no open-interest-based roll, no spread
  order book, and a roll's legs are costed as two outright orders.
* **Exchange calendars are not built in.** The caller supplies trading days, close times and contract dates; holidays
  and early closes are whatever the calendar says.
* **Margin is static.** Initial margin per contract as given; no maintenance margin, no margin calls, no variation
  margin cash flows, no collateral interest.
* **FX sweep.** Daily P&L is converted at the day's rate; intraday FX and settlement-currency balances are not
  modelled. No cross rates.
* **Fixed capital.** Fractions of capital use a fixed capital, with no compounding.
* **Options, spreads as single instruments, and exchange-specific fee schedules** (tiers, caps, rebates) are out of
  scope.
