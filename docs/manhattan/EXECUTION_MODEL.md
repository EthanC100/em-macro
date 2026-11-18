# Synthetic futures execution, cost and roll model

Version 0.3, 2026-11-18 (Project Manhattan, session 4; 0.2 and 0.3 answer the S6 reviews: section 19). Code: `manhattan/execution/`. Tests:
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

**Fractional ticks cost whole ticks (a deliberate, conservative convention).** A fill must be a price on the tick
grid, so a cost scenario of half a tick of half-spread and no slippage fills one full tick away: the spread line
shows the nominal 0.5 tick and the `rounding` line shows the other 0.5 tick. Read a scenario's cost from
`spread + slippage + impact + rounding`, not from the nominal ticks. The model does not average fractional ticks
across fills (as a mid-quote fill half the time would); that would be a different economic convention and is not
made here. Any change to it would be a new cost-model version, not an edit.

Per fill: `execution cost = (fill − reference) × q × point_value = spread + slippage + impact + rounding`, all ≥ 0
for longs and shorts alike. The four parts add up exactly to the price difference; a test checks this.

## 6. Order sizing and liquidity constraints

Orders are signed whole contracts (`int`; floats, including `2.0`, and booleans are refused). At most
`floor(max_participation × adv_contracts)` contracts per contract per day. Policies:

* `on_liquidity_shortfall = "raise"` (default): an order above the cap stops the run (`LiquidityError`).
* `"clip"`: the cap is filled, the remainder is recorded as `Unfilled` and worked on the next trading day (reason
  `carry`) until the target is reached or replaced by a new decision.

**Labels.** Each `Fill` has a `reason` and a `roll_quantity` (the signed contracts of the fill that are a roll leg):
`decision` (an outright trade on the day a decision executes), `carry` (an outright trade on a later day, working
toward a target the cap or a missing price held back), `roll` (a pure roll leg), `roll+decision` / `roll+carry` (one
contract's fill that is partly a roll leg and partly an outright trade: one fill per contract per day, so impact
and rounding are charged on the whole size once). Each `Unfilled` says what the order was (`reason`) and why it
was short (`why`): `no settlement`, `liquidity` (its own cap) or `paired leg` (the roll's other leg could not trade).

ADV = 0 allows nothing (`raise` refuses; `clip` fills zero and charges nothing). A very large ADV drives impact to
zero; spread, slippage, rounding and fees remain.

## 7. Futures expiry and contract rolls

Decisions name a **root** and a signed target in contracts; the roll rule picks the month, from metadata only:

* **Open** in the earliest listed contract whose notice date is more than `buffer_days` after the trade day.
* **Roll** at the settlement of the first trading day on which the held contract is `roll_before_notice_days` or
  fewer calendar days from its notice. `buffer_days > roll_before_notice_days` is enforced.

**Each day, for each root, the trades are split in two** (`account._plan_root`), whether or not a decision arrived:

1. **The month to hold** (`primary`): a held month that need not exit today (`RollPolicy.must_exit`: roll window,
   delivery boundary, last trade), else the roll rule's choice. A roll is needed whenever some held month is not the
   primary; that is decided from the holdings alone.
2. **The roll** `K`: the part of the old months' position that the target keeps, moved into the primary as a calendar
   spread. `K = sign(T − p) × min(|old|, |T − p|)` when the old position and the needed change `T − p` have the same
   sign (`T` the target, `p` the primary's holding, `old` the other months' total), else 0.
3. **The net change**: everything else, outright: the rest of the old months is closed, and the primary gets
   `T − p − K`. Roll plus net takes the holdings exactly to `{primary: T}`.

**Reversals close first (S6 N1).** When the target is on the other side of a held position (long to short or
short to long, in any month, including during an unfinished roll), every position on the wrong side is closed
**before** anything is opened on the new side. Closing may be partial (capacity or a missing price); while any
wrong-side contract is still open, nothing is opened in the target's direction that day (the blocked opening is an
`Unfilled` with `why = "reversal: old side not closed"`) and the closing continues on later days (`carry`). Only
positions already on the target's side may still be rolled, exposure-neutrally. A reversal is never a roll: its
trades are outright (`decision` / `carry`, `roll_quantity = 0`) and it records no `RollEvent`. So a root never holds
both sides at a close, and its gross contracts never exceed the larger of the previous close's and the target's.

**Order of a day's trades in a root** (each contract's capacity is shared in this order):

1. closes of wrong-side positions (reversals, above);
2. **risk-reducing** net trades: closing the part of a month's position the target no longer needs (S6 N3);
3. the **roll**, paired: it moves `n = min(|K|, what the new month can trade, what the old months can trade)`
   contracts, so under `clip` or a missing price the position neither lapses nor doubles;
4. **risk-adding** net trades (an increase of the target in the month to hold), with what capacity is left.

**Why reductions come before the roll (S6 N3, a deliberate change of allocation priority in 0.3).** A cut and a roll
leg both use the old month's capacity. With the roll first, a cut on a roll day waited behind the roll: +5 cut to +2
with the old month able to trade 2 a day ran gross 5, 3, 2 over three days (the roll opened 2 in the new month
while 3 stayed open in the old). With the cut first it runs 3, 2, 2. The old month empties at the same speed (every
contract it trades is either a cut or a roll leg, so its capacity is fully used either way; a test checks this),
the costs are the same contracts at the same prices, and the roll stays paired. What changes: the new month is
opened later, so for a few days more of the position can sit in the old month; it still must be flat before the
delivery or expiry boundary, or the run stops. Increases are unaffected: the roll keeps priority over adding. Under `raise`, any shortfall or missing price on a needed leg stops the run. A decision
on the roll day is therefore a roll plus a net change; examples at the roll from H to J holding +5:

| new target | H trade | J trade | RollEvent |
|---|---|---|---|
| 5 (unchanged) | −5 `roll` | +5 `roll` | 5 contracts |
| 8 (increase) | −5 `roll` | +8 `roll+decision` (5 of them roll) | 5 |
| 2 (decrease) | −5 `roll+decision` (2 of them roll) | +2 `roll` | 2 |
| −3 (reversal) | −5 `decision` | −3 `decision`, only once H is fully closed | none: a reversal is never a roll |
| 0 (flat) | −5 `decision` | — | none |

Each roll leg pays spread, slippage, impact and fees once; a `RollEvent` is recorded for every day a roll moves
contracts, with or without a decision. A day on which no listed contract can be held past the next trading day is an
`InvalidContractError`.

**Delivery boundary (owner decision, S6 M4).** This synthetic model has no delivery management, so it fails closed:

* **No contract** may be carried past its `last_trade` date (S6 N2): there is no market to close in afterwards and
  final settlement is not modelled. This holds for physical contracts too, also when their first notice falls after
  the last trading day.
* A **physically settled** contract may not be carried into its `first_notice` date either: a position must be flat
  by the close of the last trading day before the **earlier** of `first_notice` and the day after `last_trade`. The exit rule rolls on that day at the latest, even with
  `roll_before_notice_days = 0`; a position still open at that close (for example because the cap or a missing
  price kept the roll from finishing) stops the run with `InvalidContractError`. No trade at all is made in a physical
  contract on or after its first notice date (`ContractSpec.require_model_tradable`).
* A **cash-settled** contract: flat by the close of its last trade day.
* An unfinished roll fails closed: the run stops at the close at which the position would cross the boundary, with
  an `InvalidContractError` naming the boundary (`delivery boundary` or `expiry`), the contract and the dates.
* Dates are calendar dates of the contract's exchange as the caller gives them; "the next trading day" is the next
  day of the caller's calendar (the day after, past its end). Where an exchange assigns delivery on positions held
  earlier (a first position or intention day), give that earlier date as `first_notice`.

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

**Point in time.** `difference` and `ratio` series are revised at every later roll: the value of a past day read
from a series built over the whole window is not the value anyone saw on that day. `adjust.build(..., as_of=d)`
builds the series from the days up to `d` only; a signal that reads back-adjusted levels must use a series built as
of its decision. `spliced` and `chained` are not revised by later rolls (a test checks both). The hold schedule uses
the accounting's exit rule, so the series roll on the same days the accounting does.

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
once per side; a roll counts both legs), `gross_exposure = Σ |q| × |S| × point_value × FX` and
`net_exposure = Σ sign(q) × |q| × |S| × point_value × FX` after the close, and the positions by contract.

**Negative and zero prices.** Exposure is the size of the position at the absolute price, signed by the position:
a long stays a positive exposure when the price is negative (with `q × S` it would flip sign and a long would look
short). P&L is unaffected: it is always `q × ΔS × point_value`. At a price of zero the notional is zero, though the
P&L per point is not; notional exposure is a size measure, not a risk measure. With `capital` given,
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
zero amount.

**Valuation versus decisions (S6 L4).** The model uses FX in two different ways, with different time rules:

* **Valuation** of day `d`'s P&L, costs, exposure and margin uses day `d`'s fix. By default this is **ex-post**
  research accounting: the fix is used whenever it was published, because the amounts of day `d` are being valued,
  not traded on, and nothing in the model decides anything from them (`Result.meta["fx_valuation"] = "ex_post"`).
  For **contemporaneous** valuation (what a desk could report that evening), set
  `ExecutionPolicy.fx_valuation_cutoff`: every rate used for day `d` must then have been published by `d`'s close
  plus that cut-off, or the run stops with `LookAheadError`.
* **Decisions** never read FX inside this model: orders are in whole contracts and the liquidity cap is in
  contracts. A caller that sizes in money (section 16) uses `MarketData.rate_as_of(frm, to, t)`, which returns the
  latest rate published at or before the decision time `t` and refuses a later one, whatever day it is for.

No universal rule ties `known_at` to the rate's own day (fixes are published at different times of day around the
world; a fix may be published before a contract's close or long after it): the two rules above are where the
timing matters. Daily P&L is converted at the day's rate and assumed swept into the base currency, so the futures carry
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
change the output.

* `Result.result_hash()`: SHA-256 of a canonical JSON form of the run: the policy (`ExecutionPolicy.describe()`:
  base currency, roll rule, lag, missing-price and shortfall policies, capital, margin reporting, FX valuation rule),
  the scenario id, and every output (days, fills, rolls, unfilled orders, unexecuted decisions), amounts rounded to
  8 decimals of the base currency. Two runs under different rules never share a hash, even when their numbers agree.
  The market data are **not** hashed: a caller who needs them in the identity hashes them alongside, as the engine's
  `data_hash` does. Differences below 1e-8 of a currency unit do not change the hash.
* `CostScenario.scenario_id()`: a content address (`AC-` + 16 hex of the `manhattan.spec` canonical hash) of the
  scenario's economics: its provenance and every root's terms. The name is a label and is left out, so renaming a
  scenario keeps its id. Suitable as an executable's `cost_model_id`. `run_scenarios` runs one plan under several scenarios; `sensitivity_table` gives
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
  order book, and a roll's legs are costed as two outright orders (paired in quantity, not priced as a spread).
* **No delivery.** A position that cannot be rolled before its delivery boundary stops the run; there is no
  delivery, no exchange-for-physical and no forced liquidation model.
* **Hold leaves targets unmet.** Under `hold`, a day without a price in a needed month leaves the position where it
  was (not at the target) until the price returns.
* **Exchange calendars are not built in.** The caller supplies trading days, close times and contract dates; holidays
  and early closes are whatever the calendar says.
* **Margin is static.** Initial margin per contract as given; no maintenance margin, no margin calls, no variation
  margin cash flows, no collateral interest.
* **FX sweep.** Daily P&L is converted at the day's rate; intraday FX and settlement-currency balances are not
  modelled. No cross rates.
* **Fixed capital.** Fractions of capital use a fixed capital, with no compounding.
* **Options, spreads as single instruments, and exchange-specific fee schedules** (tiers, caps, rebates) are out of
  scope.

## 19. S6 review (version 0.2)

| finding | decision | change |
|---|---|---|
| H1 a decision on the roll day bypassed the paired roll (S6: target 5 ended at 2, 8 and 10; no February RollEvent) | defect | trades split into a paired roll and a net change from the holdings alone (section 7); regression tests reproduce all three cases and cover increase, decrease, reversal, flat, zero liquidity and missing prices, checking positions, P&L, fees, turnover, exposure and roll counts |
| M4 physical delivery | owner decision: fail closed | delivery boundary (section 7): flat by the close of the last trading day before first notice; no trade in the delivery period; cash-settled contracts flat by the last trade day |
| M5 fractional-tick costs | convention kept | documented (section 5); the rounding line stays separate; a test shows 0.5 tick of half-spread costing a full tick |
| L4 FX availability | defect for decision use; convention for valuation | `rate_as_of` for decisions; ex-post valuation by default, a contemporaneous cut-off on request (section 13) |
| negative-price exposure | defect | net exposure signed by the position (section 11) |
| deferred-order labels | defect | `roll_quantity`, combined reasons, `Unfilled.reason` (section 6) |
| scenario and result hashes | defect | scenario id without the name; result hash covers the policy (section 15) |
| back-adjusted series and point in time | limitation | `as_of` builds; documented as revised by later rolls (section 8) |
| **N1** (re-review) a roll-day reversal opened the new side while the old side was still open (S6: +5 to −4 left H +3 / J −4, gross 7, under `clip`; H +5 / J −4, gross 9, under `hold`) | defect | reversals close first; partial closes allowed; nothing opened on the new side until the old side is flat; never a roll (section 7). Tests: `clip`, `hold`, missing old settlement, zero liquidity in either month, both directions, several days, mid-roll, off the roll day, conservation; 400 seeded fuzz cases |
| **N3** (re-review) a cut on a roll day waited behind the roll for the old month's capacity | allocation priority changed (separate commit) | reductions before the roll, additions after it (section 7); tests show the gross path 3, 2, 2 instead of 5, 3, 2, an unchanged exit speed from the old month, and unchanged increases |
| **N2** (re-review) a physical contract whose first notice falls after its last trading day could be carried past the last trading day | defect | `may_hold_into` enforces both boundaries; the restored last-trading-day test and the first-notice tests both pass (section 7) |
