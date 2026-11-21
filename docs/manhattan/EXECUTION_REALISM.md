# Execution realism: from HTE's same-close benchmark to defensible historical execution

Version 0.1, 2026-11-19 (Project Manhattan, S14). Code: `manhattan/execution_realism/`. Tests:
`tests/test_manhattan_execution_realism.py`. Demo: `python -m manhattan.execution_realism.demo` (prints only).

**What this is.** An isolated, pure-function execution adapter, plus the rules for what its output may be called.
It takes target weights or contracts on a contract-aware daily panel and applies:

- a configurable execution lag (default 1);
- whole-contract sizing, multipliers and tick-adverse fills;
- commissions, exchange fees, spread, slippage and square-root impact;
- a liquidity cap;
- rolls with both legs costed;
- FX conversion;
- missing-price policies;
- a provenance on every cost number.

It reproduces PR #85's daily accounting to 1e-8 on a common plan, and HTE's stage-3 arithmetic bit for bit at lag 0.

**What this is not.** It is not calibrated, and no output is called "realistic". It places no order and has no
broker or network connection. It reads no file and no environment variable. Nothing imports it, and it writes no
record. It changes neither PR #85 nor PR #89, nor any engine, ops, Ledger, protocol or protected file
(`config/manhattan.yaml` is unchanged by a run; tested).

## 1. The two reviewed heads and their execution conventions

| | PR #89 HTE @ `232d0d6` | PR #85 execution @ `3f6b213` | main engine (Protocol v3.1 §2.1) |
|---|---|---|---|
| **fill time** | row `t` (data through close `t`) traded **at close `t`** | settlement of the `lag`-th close **strictly after** `decided_at` | close `D_{j+lag}` |
| **lag** | none (`EXECUTION_TIMING = same_close_fill_next_day_return/v1`) | `lag >= 1` enforced | default 1, `0` allowed |
| **first return** | day `t+1` | day `t+lag+1` | day `j+lag+1` |
| **time base** | integer row of a synthetic weekday calendar; no timestamps | tz-aware `close_at`; every input has `known_at` | union calendar of all instruments |
| **unit** | weight per unit notional on continuous returns | signed whole contracts on settlements | weights (fractions of capital) |
| **costs** | `c·Σ\|ΔW\| + k·Σ\|ΔW\|^1.5`, fixed per domain | ticks of spread + slippage, sqrt impact in points, fees per contract per side, adverse tick rounding | one-way proportional per instrument |
| **cost booked** | in the period the position **earns** (day after the trade) | on the execution day | on the trade day |
| **rolls** | none (continuous returns, no roll cost) | paired calendar roll, both legs costed; delivery boundary fails closed | none (excess-return index) |
| **liquidity** | none | cap `floor(p × ADV)`; `raise`/`clip`; ADV known at decision | none |
| **missing prices** | complete synthetic panel | `raise` / `hold` | held mark, P&L on return |
| **FX** | returns already in base | day's fix; `rate_as_of` for decisions | per series |
| **cost provenance** | constants labelled synthetic | `synthetic` / `caller-supplied`; `calibrated` refused | a number per instrument |
| **identity** | timing in `evaluation_spec` | policy (incl. lag) in `result_hash` | `code_version`, `data_hash` |

### Incompatibilities (what breaks if one is read as the other)

1. **I1 Timing.** HTE trades at the close it decided from. That price was published after the close
   (PR #85 requires `known_at >= close_at`), so it was never tradable once seen. HTE is one day earlier than
   PR #85 `lag=1`. It also breaks Protocol v3.1 §2.1 ("positions fixed with `𝓕_{t-1}`, executed at the next
   available price").
2. **I2 The bias is not one-sided.** Same-close is **not** an optimistic bound. Its error has the sign of the
   strategy's exposure to lag-1 autocorrelation. On the fixtures (§6), a fade-yesterday strategy gains 6.9 Sharpe
   points from same-close. A trend strategy *loses* 0.8, because the planted lag-1 reversal works against momentum
   at the same close. A same-close number cannot even be used to bound the delayed result.
3. **I3 Lag units.** PR #85 counts trading days of one caller calendar, strictly after a timestamp. The engine
   counts periods of the union calendar of all instruments. HTE has no calendar. For roots on different exchanges,
   "lag 1" can mean different days. The adapter counts the panel's trading days. A missing price never shortens the
   lag: the order waits (tested).
4. **I4 Cost form.** HTE's impact `k·|ΔW|^1.5` has the square-root law's shape. Mapped from PR #85
   (`costs.hte_equivalent_coefficients`):

   ```
   k = coef × (σ_points / |P|) × sqrt(capital / (|P| × point_value × ADV))
   ```

   So HTE's fixed `k` silently fixes a **capital-to-ADV ratio** that its run identity does not state. HTE's linear
   `c` also ignores the floor that whole ticks and per-contract fees put on small trades. Fractional ticks cost
   whole ticks in PR #85.
5. **I5 Cost booking day.** HTE books a trade's cost one day later than PR #85 and the engine. Totals agree, but
   the daily series differ by a day, which matters for vol targeting, drawdowns and the bootstrap.
6. **I6 Rolls, liquidity, missing data, FX.** HTE has none of them. PR #85 has all of them, with fail-closed
   defaults.
7. **I7 Vol targeting under a lag.** HTE scales period `i` with its own returns `g[:i]`. If the positions are
   shifted by `L` and that rule is kept, a decision reads `L` days it never saw. The scale must move with the
   decision: `g[:i−L]` (`screening.lagged_scales`; a test shows the naive rule reads the future).
8. **I8 Contracts versus weights.** At small capital, rounding to whole contracts changes the strategy itself. At
   large capital, the participation cap does (§6.3). HTE sees neither effect.

## 2. The adapter design

```
weights (n, A) ──size──▶ contracts decided at close t (price, multiplier, FX known at t)
                         │ lag L (default 1; 0 only with allow_same_close, labelled throughput_only)
                         ▼
SettlementPanel ───────▶ execute(): per day, per root (PR #85's order)
 level, exit_level,       1. mark the held month at its own settlement (hold: stale mark; raise: stop)
 roll, adv, vol,          2. trade toward the target, cap floor(p × ADV); liquidity known at the decision,
 fx, data_kind               or at the previous close for carries and rolls
                          3. roll: close old month at exit_level, open new at level; both legs costed;
                             fails closed when a leg is unpriced or the cap cannot complete it
                          4. FX at the day's fix; exposure at the last mark
                         ▼
ExecutionResult ──────▶ realism.assess() → label (throughput_only / screening_net / exploratory_grade)
 gross, 7 cost parts,     summary() renames same-close stats "same_close_optimistic_*"
 fills, rolls, unfilled,  present_trading_return() is the only un-prefixed figure, and it needs
 stale marks, hashes      exploratory_grade + historical data + the R9 sensitivity rows
```

| module | role |
|---|---|
| `timing` | `ExecutionTiming(lag=1)`; lag 0 refused unless `allow_same_close=True`; the three conventions as data |
| `instruments` | multiplier, tick size, tick value identity (refuses the cents/dollars factor-100 error); PR #85's decimal tick rounding |
| `provenance` | `Source(kind, reference, valid_from, valid_to)`; known / estimated / scenario (§3) |
| `costs` | `RootCosts` with a `CostValue(value, source)` per term; `fill()` is PR #85's `fill_order` term for term plus spread and slippage shocks; `hte_equivalent_coefficients`, `one_way_cost_fraction` |
| `panel` | `SettlementPanel`: tradable settlements of the held month (`level`), the old month's on roll days (`exit_level`), `roll`, `adv`, `vol_points` known at each close, FX; read-only arrays; `digest()`; refuses back-adjusted, ratio-adjusted, spliced and continuous series and off-tick prices |
| `adapter` | `size`, `execute`, `ExecutionPolicy`, `Shocks` (spread, slippage and ADV multipliers per day: adverse scenarios) |
| `realism` | requirements R1-R9, `assess`, `present_trading_return` |
| `sensitivity` | `grid` (lag × cost multiple × shock), `optimism_gap`, `break_even_multiple` |
| `screening` | HTE-shaped tier: `align_lagged`, `lagged_scales`, `series` (HTE stage-3 arithmetic with a lag) |
| `fixtures` | synthetic world (`SYNA` USD, `SYNR` USD 1/64 tick, `SYNE` EUR) with planted effects; causal strategies |

**Lag default 1, as PR #85.** A decision at close `t` executes at the settlement of `t + lag` and first earns day
`t + lag + 1` (tested for lags 0-3). Every result carries its timing label in `policy`, in `result_hash` and in
`summary()`.

**Sizing and rounding.** The target is `contracts = W × capital / (|level_t| × point_value × fx_t)`, using the
decision day's level and FX. It is rounded `nearest` (half to even, as PR #85 §16) or `toward_zero` (never more risk
than the weight). Fills are rounded to the tick grid against the trader, and the rounding is its own cost line.
A zero price cannot be sized. A negative price is marked by sign, and a long stays a positive exposure.

**Unavailable prices.** `raise` (default) stops the run. `hold` keeps the last mark, books the gap's P&L when the
price returns, makes trades wait (listed in `unfilled`), and sizes from the last published level (listed in
`stale_sizing`). A missing FX rate or ADV always stops the run, even for a zero amount.

**Known divergences from PR #85** (each conservative or fail-closed):

| # | divergence | effect |
|---|---|---|
| D1 | the panel has one held month per root per day; a fresh position opens in it. PR #85 opens in the first month whose notice is more than `buffer_days` away, so in the ~25 days before the roll window it opens one month further out | the adapter may pay one extra roll for a position opened in that window (higher cost) |
| D2 | a roll that the cap cannot complete, or that has an unpriced leg, stops the run (`RollError`). PR #85 runs a paired, multi-day partial roll | fail closed; use PR #85 for capacity-bound rolls |
| D3 | one ADV and volatility per root and day, used for both roll legs | caller's estimate; PR #85 takes one per month |
| D4 | no contract dates: no delivery boundary or expiry check; the panel's roll schedule is the caller's | the panel builder must enforce them (PR #85 does) |
| D5 | no margin or margin funding | PR #85 has static margin |
| D6 | an optional `fx_conversion_bps` term on each day's net foreign-currency amount | extra cost line; PR #85 has none |

## 3. Known, estimated and scenario costs

Every cost term is a `CostValue(value, Source)`. There are no defaults; zero is allowed and still needs a source.

| class | kinds | requirement |
|---|---|---|
| **known** | `recorded` (measured from recorded quotes, fills or statements: Protocol v3.1 §10's estimator), `published_schedule` (a fee schedule or contract specification in force) | reference **and** `valid_from`/`valid_to`; outside those dates it becomes `extrapolated` |
| **estimated** | `literature_estimate` (as `results/cost_audit/cost_estimates.csv`), `model_estimate` (e.g. sqrt impact with an assumed coefficient), `extrapolated` | reference |
| **scenario** | `scenario` (sensitivity multiples, stress), `synthetic` (tests) | none for `synthetic`; reference for `scenario` |

The labels `calibrated`, `realistic`, `actual`, `measured` and `live` are refused. `CostModel.scaled(k)` turns
every scaled term into a `scenario` source that names its origin, so a 2× row can never pass as a base case. A run
reports its weakest class (`cost_class`), and each component's source as it applies to the run's window.

## 4. What a result may be called

| label | condition |
|---|---|
| `throughput_only` | `lag = 0`: same-close timing, whatever else holds |
| `screening_net` | `lag >= 1`, but some of R2-R8 unmet (proportional tier, synthetic or scenario costs, no FX conversion term) |
| `exploratory_grade` | R1-R8 met; R9 checked when presented |

No label says "realistic" or "evidence". Tiers above "Statistically supported" need costs **measured** from
recorded quotes (Protocol v3.1 §8), which nothing here has. `summary()` is always allowed, and at lag 0 it
prefixes every statistic `same_close_optimistic_`. `present_trading_return()` is the only un-prefixed figure. It
refuses:

- any label below `exploratory_grade`;
- a `synthetic` panel;
- a missing R9 sensitivity.

Even its output says `evidence: false` and `realistic_return_claims: false`.

## 5. Minimum execution-model requirements for historical exploratory research

| id | requirement |
|---|---|
| R1 | Execution at least one trading day after the close whose data the decision used (Protocol v3.1 §2.1; PR #85 `lag >= 1`). Same-close fills are a throughput convention only. |
| R2 | Fills and marks at tradable settlements of the month actually held; P&L from same-contract changes; no back-adjusted, ratio-adjusted or spliced series traded or marked. |
| R3 | Whole contracts sized from the multiplier, price and FX known at the decision; fills rounded to the tick grid against the trader. |
| R4 | Every cost component (commission, exchange fee, half-spread, slippage, impact coefficient, participation cap) with a non-scenario source and a reference; a `known` source only inside its dates. |
| R5 | A participation cap on every order with the liquidity estimate known at the decision (carries and rolls: the previous close's). |
| R6 | Missing settlements stop the run or are held with every stale mark reported; missing FX or liquidity stops the run. |
| R7 | Rolls cost both legs; a roll that cannot complete fails closed, never lapses or doubles. |
| R8 | Foreign-currency roots converted at the day's fix, with an FX conversion cost term stated (zero allowed, sourced). |
| R9 | Any presented figure carries the sensitivity: costs ×0, ×1, ×2 and lag + 1, on the same decisions. |

The code holds this table as `realism.REQUIREMENTS`, and `assess()` checks it.

## 6. How execution assumptions change performance (synthetic fixtures)

`python -m manhattan.execution_realism.demo`. The world is synthetic: three roots, 756 days, quarterly rolls, and
`synthetic` costs (commission 1.0 and exchange fee 0.5 per side, half a tick of half-spread, half a tick of
slippage, impact coefficient 0.1, 10% of ADV). There is an MA(1) reversal with θ = 0.3 and a slow trend
(κ = 0.06). Capital is 1e7, with `clip`. "stress" multiplies spread and slippage by 3 and ADV by 0.2 on days
300-399. These numbers describe the generator, not a market.

### 6.1 A same-close-only effect: fade yesterday's move

| lag | cost × | shock | label | ann. net % | Sharpe | cost drag % | unfilled |
|---|---|---|---|---|---|---|---|
| 0 | 0 | – | throughput_only | 37.41 | 6.42 | 0.00 | 0 |
| 0 | 1 | – | throughput_only | 29.35 | 5.18 | 8.07 | 0 |
| 0 | 1 | stress | throughput_only | 28.16 | 5.00 | 9.23 | 43 |
| 0 | 2 | – | throughput_only | 23.72 | 4.27 | 13.69 | 0 |
| **1** | 0 | – | screening_net | −3.01 | −0.49 | 0.00 | 0 |
| **1** | 1 | – | screening_net | −11.05 | −1.77 | 8.04 | 0 |
| **1** | 1 | stress | screening_net | −12.43 | −2.01 | 9.21 | 46 |
| **1** | 2 | – | screening_net | −16.66 | −2.66 | 13.65 | 0 |
| 2 | 1 | – | screening_net | −9.25 | −1.51 | 8.01 | 0 |

Same-close shows a Sharpe of 5.2 after costs. With one day of lag the gross is nothing, and the net loses 11% a
year to costs. The break-even cost multiple at lag 1 is 0. This is the case the label `throughput_only` exists for.

### 6.2 A lag-robust effect: slow trend

| lag | cost × | shock | label | ann. net % | Sharpe | cost drag % | unfilled |
|---|---|---|---|---|---|---|---|
| 0 | 0 | – | throughput_only | 3.43 | 0.60 | 0.00 | 0 |
| 0 | 1 | – | throughput_only | 2.56 | 0.44 | 0.87 | 0 |
| **1** | 0 | – | screening_net | 7.57 | 1.35 | 0.00 | 0 |
| **1** | 1 | – | screening_net | 6.70 | 1.20 | 0.87 | 0 |
| **1** | 1 | stress | screening_net | 6.50 | 1.16 | 1.07 | 3 |
| **1** | 2 | – | screening_net | 6.08 | 1.08 | 1.50 | 0 |
| 2 | 1 | – | screening_net | 6.73 | 1.18 | 0.87 | 0 |

Here same-close **understates** the delayed result (I2). The break-even cost multiple at lag 1 is 11.6.

### 6.3 Capital: whole contracts and the liquidity cap (trend, lag 1, costs ×1)

| capital | Sharpe | ann. net % | note |
|---|---|---|---|
| 2e5 | 0.42 | 2.19 | 657 decision rows round to zero contracts: whole contracts change the strategy |
| 1e6 | 1.16 | 6.51 | |
| 1e7 | 1.20 | 6.70 | impact is 19% of costs |
| 1e8 | – | – | `RollError`: the SYNE position (578 contracts) exceeds one day's cap (500) at a roll; the adapter stops rather than let the position lapse or double |

## 7. Tests and reproducibility

`python -m pytest -q tests/test_manhattan_execution_realism.py`: 53 tests (50, plus 3 cross-checks that skip
without a checkout). They cover:

- **timing:** lags 0-3, unexecuted decisions, a missing price never shortening the lag;
- **fills:** the tick identity, whole-tick rounding, fees per side, sizing with the decision-time FX, zero and
  negative prices, refused adjusted series;
- **liquidity:** `raise`/`clip`, the right liquidity day, no later estimate, zero ADV, single-month close-first;
- **rolls:** PR #85's §7 roll-day table (increase, decrease, reversal, flat), both legs costed, no calendar gap in
  P&L, fail-closed rolls;
- **missing data and FX:** `hold` gap accounting, missing FX/ADV, FX conversion, fee currency;
- **conservation:** `net = gross − costs` everywhere, the cash identity, hashes;
- **provenance and labels:** labels, renaming, the presentation guard;
- **effects:** the planted effects (§6), shock monotonicity, a liquidity drought, missing data on the fixture world;
- **HTE tier:** the HTE-tier alignment and the vol-target look-ahead trap;
- **isolation:** imports, no I/O, no network or broker names, nothing imports the package, config unchanged.

**Cross-checks against the exact reviewed heads** (run in this session; they need the unmerged branches):

```
git worktree add --detach <dir85> 3f6b213a6b4df40c1800e27b566c5e69ea1e1896
git worktree add --detach <dir89> 232d0d6b8e453f3b89adcabce1f56f3f59682551
EXEC_REALISM_PR85_CHECKOUT=<dir85> EXEC_REALISM_HTE_CHECKOUT=<dir89> python -m pytest -q tests/test_manhattan_execution_realism.py
```

- **PR #85** (lags 1 and 2). One plan exercises a roll, an increase on the roll day, reversals, three clipped
  orders, a held month with no settlement under `hold`, carries, and a EUR root with a moving fix and EUR fees.
  Daily gross, all six cost parts, turnover, gross exposure, positions per root, rolls, stale marks and unfilled
  counts agree to 1e-8 of a currency unit. Three deliberate mutations (capacity rounding, the carry liquidity day,
  the impact exponent) each make it fail.
- **PR #85, seeded fuzz.** 40 random plans × lags 1 and 2 (80 runs) inside the common ground of D1 and D2:
  - random targets on both roots;
  - zero and low ADV on early days;
  - random missing settlements of the held month under `hold`.

  All 80 agree on the same quantities. The test also asserts that the fuzz reaches clipping and stale marks.
- **HTE.** `align_lagged(lag=0)` equals `kernels.align`, and `screening.series(lag=0)` equals
  `kernels.ref_stage3_series` **bit for bit**. Python ≥ 3.12's compensated `sum()` first gave a 3.5e-18 difference;
  the tier accumulates with `+=` as HTE does. `EXECUTION_TIMING` equals the label here.

## 8. Remaining blockers

| # | blocker | owner |
|---|---|---|
| X1 | PR #85 and PR #89 are unmerged. The adapter restates PR #85's fill arithmetic (conformance-tested) instead of importing it. Once #85 merges, either call `manhattan.execution.fill_order` from `costs.fill` or keep the cross-check permanent by dropping its skip | design, after #85 |
| X2 | **No known (`recorded`) futures costs exist in the repository.** `cost_estimates.csv` holds FX and bond literature estimates for v1.0, and `ledger/janus_fut.py`'s `2 × (US$3 + one tick)` is an assumption. R4 can only be met with `estimated` sources until a recorded-cost dataset (Protocol v3.1 §10 estimator) exists | Ethan |
| X3 | No point-in-time ADV and volatility history per contract month. `data/ledger/capacity_reference.csv` is a static table, mostly `estimate`. R5 needs `known_at`-stamped liquidity | data |
| X4 | Settlement history is licensed and stays in em-macro-data (hard rule 7). A panel builder must run in the private context, and only `panel.digest()`, `result_hash` and aggregates may be public. Contract-specification history (tick, multiplier, fee-schedule changes) is also needed | Ethan / data |
| X5 | HTE has no lag. `screening.py` is the tested reference for HTE's own next step 3 (LIMITATIONS §4); changing HTE's kernels is the HTE owner's job, and must use `lagged_scales` (I7) | HTE owner |
| X6 | D1 (opening month) and D2 (capacity-bound rolls) need PR #85's month selection and paired roll for an exact treatment. The adapter is conservative or fails closed there | design |
| X7 | Fills at the settlement price are themselves an assumption: settlement is not guaranteed tradable at size. Whether trade-at-settlement or a closing auction is available differs per product. The `slippage_ticks` term carries this, and needs per-product evidence | research |
| X8 | Connecting any of this to the engine (PR #85 §16) or to attempt accounting is Ethan's decision. Nothing here is wired | Ethan |

No queue file is edited (CLAUDE.md: night-shift files are dev's). Suggested queue items are in the PR description.
