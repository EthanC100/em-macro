# HTE execution bridge (dormant)

Version 0.1, 2026-11-19 (Project Manhattan, S14 phase 2). Code: `manhattan/hte_execution_bridge/`. Tests:
`tests/test_manhattan_hte_execution_bridge.py`. It builds on the execution-realism adapter
(`manhattan/execution_realism/`, PR #93; design `docs/manhattan/EXECUTION_REALISM.md`).

**What this is.** A dormant, pure-function bridge. It translates one HTE candidate (PR #89 at `232d0d6`) into the
#93 adapter's inputs under PR #85's timing (at `3f6b213`), runs it, and identifies the run with its execution
assumptions. It also produces a labelled comparison of HTE's throughput-only result against delayed contract
execution.

**What this is not.** It is not enabled (`ENABLED = False`), and it accepts only inputs with synthetic provenance.
The hook a connected HTE would call (`HteExecutionStage`) refuses construction and lists the connection
requirements (section 8). It imports neither HTE nor PR #85; a caller passes HTE's functions in. It reads no file
or environment variable, has no broker or network connection, and writes no record. Nothing imports it. No result
is verified profitability, evidence or a trading return.

## 1. The translation

`F` is the fence, `W` the warm-up (HTE `Policy.warmup`, 300) and `L` the lag (default 1).

| HTE (PR #89) | bridge | adapter / PR #85 |
|---|---|---|
| `runner.signed_positions(cache, view.describe(i))[t]`: weight held from close `t`, from data through close `t` | `CandidateInput.positions` (cut at `F`) | |
| no timestamp | `decided_at = close_t + decision_delay`; `inputs_known_at = close_t + settlement_publication` (`clock.py`) | `Decision(root, contracts, decided_at, inputs_known_at)` (`pr85_decision_records`) |
| fill **at** close `t` (`same_close_fill_next_day_return/v1`) | execution row `t + L`, checked against PR #85's rule | settlement of the `L`-th close strictly after `decided_at` |
| stage-3 vol scale `s[i]` from `g[:i]` | decision-time scale from `g[:i − L]` (`scaling.py`) | |
| weight `s × P[t]` | `weights[t]` on decision rows `[W − 1 − L, F − 1 − L)`, `NaN` elsewhere | whole contracts from `S_t`, multiplier and `fx_t` at row `t` |
| `panel.returns(domain)` `(F, A)` | `market.contractise`: synthetic tick-grid settlements, held month, rolls every 63 rows, ADV, vol known at close, EUR roots with a EURUSD fix | `SettlementPanel` |
| `kernels.COSTS[domain] × COST_MODELS[cost_model]` = `(c, k)` per unit notional | `market.hte_matched_costs`: per-contract terms with `scenario` provenance | `CostModel` with sources |
| `evaluation_spec["execution"]` = the same-close string | `identity.executable_spec`: replaced by the execution block | |
| `data_hash` | kept | plus `market_digest` (`SettlementPanel.digest()`) |

Only decision rows `[W − 1 − L, F − 1 − L)` carry decisions, so positions earn exactly HTE's evaluation window
`[W, F)`. The window's net series adds the entry day's costs (day `W − 1`) to its first day: HTE books a trade's
cost in the period it earns (#93 I5). The panel ends at the fence; nothing past it exists to be read.

**Clock.** `0 < settlement_publication <= decision_delay`, and every decision must come before the next close
(otherwise the bridge refuses). Under those conditions PR #85's `execution_index` gives exactly row `t + L`. A
cross-check runs PR #85's own function on the bridge's timestamps.

**Contractisation (synthetic stand-in for a real panel builder).** For each asset:

- the level path `S_t = anchor × Π(1 + r_s)` is put on the tick grid;
- month `k` of the root sits `k × calendar_spread_ticks` away;
- same-contract changes carry the P&L, and the calendar gap is never P&L;
- volatility in points known at close `t` is an EWMA of returns through `t`, times `S_t`;
- ADV comes from the template, with an optional per-day scale (droughts).

The roots are `HC00`… (commodity), `HR00`… (rates) and `HF00`… (FX). By default `HR01`, `HR03`, `HR05` and `HR07`
are EUR-quoted.

| domain | tick | multiplier | anchor | nominal daily vol | ADV | spread per roll |
|---|---|---|---|---|---|---|
| commodity | 0.01 | 1,000 | 60 | 1.5% | 20,000 | +40 ticks |
| rates | 1/64 | 1,000 | 110 | 0.4% | 60,000 | −16 ticks |
| fx | 0.00005 | 125,000 | 1.10 | 0.6% | 40,000 | +6 ticks |

**Matched costs.** The per-contract terms reproduce HTE's continuous `c·|ΔW| + k·|ΔW|^1.5` exactly at the
template's anchor price, nominal volatility and ADV, and the run's capital (tested to 1e-9):

- commission 1.0 and exchange fee 0.5 per side;
- `(c − fees/(P·pv))·P/tick` ticks, split half-spread / slippage;
- impact coefficient `k / (σ·sqrt(capital/(P·pv·ADV)))`;
- participation cap 10%;
- FX conversion 1 bp on EUR roots.

The match point comes from the contract map, not the data, so costs are the same for every lag (a first version
matched at row 0; the one-observation volatility there inflated impact about 70×, which the comparison exposed).
Every term's source is `scenario`, and its reference states the derivation. Away from the match point the
contract model differs by design: whole ticks, whole contracts, rolls and the participation cap.

## 2. Timing: next available price, never same close

`BridgeSettings().lag == 1`. `lag = 0` raises `OptimisticExecutionError` unless `allow_same_close=True`. That
switch exists only for the comparison's same-close column, which is always labelled `throughput_only`. The first
fill of a default run is on decision row + 1, with the liquidity estimate of the decision row (tested).

## 3. Volatility scaling at decision time

The scale of a position decided at close `t` is an EWMA of the candidate's own unscaled returns realised
**through close `t`** (`g[:i − L]` in HTE's window frame). It reuses #93's `screening.lagged_scales`. The tests
check this three ways:

- **Perturbation:** every return after row `t` is changed (scaled ×3, one asset negated), and the weights up to
  row `t` stay bit-identical while later ones change.
- **The trap:** HTE's lag-0 rule kept after shifting positions reads the changed return.
- **Lag 0 against HTE:** the bridge's weights equal HTE's scale times its positions, bit for bit with HTE's
  reference loop.

Against HTE's vectorised kernel the agreement is within a few ulps: HTE's vectorised `stage3_series` and its own
`ref_stage3_series` differ by up to 3.2e-16 relative in the scale, because numpy sums each row pairwise. That is a
finding about PR #89, not a bridge defect.

## 4. Provenance and readiness

The adapter's labels pass through unchanged. With synthetic panels and `scenario` costs, every delayed column is
`screening_net`:

- R4 is unmet (weakest cost class `scenario`);
- the "synthetic data" warning is raised;
- `present_trading_return` refuses.

Each cost term's `Source` (with its derivation text) is in the result and in the identity.

## 5. Identity

`identity.executable_spec` takes HTE's evaluation spec (`candidate`, `domain` and whatever `adapters.evaluation_spec`
holds). It replaces `"execution": "same_close_fill_next_day_return/v1"` with this block:

```
{replaces, timing {lag, same_close, label}, clock {closes_utc, settlement_publication_s, decision_delay_s},
 vol_scaling {rule: decision_time_ewma/v1, lag, target_ann, halflife, min_obs, leverage_cap},
 sizing {capital, rounding, unit: whole_contracts}, policy {on_missing_price, on_liquidity_shortfall},
 window {warmup}, contract_map <sha256>, costs {model_id, sources per root and term}, shocks <hashes>, adapter}
```

It adds `"bridge": "hte-execution-bridge/1"`. `executable_identity` returns:

- `spec_hash`;
- `execution_hash`;
- `executable` (the spec hash bound to the bridge and adapter versions);
- `data_hash` (HTE's);
- `market_digest` (the contract panel's);
- `result_hash` (the adapter's).

The tests check:

- each of 11 settings changes, and a shock, gives a different `spec_hash`: lag, capital, rounding, missing policy,
  shortfall policy, vol half-life, leverage cap, commission, clock, roll cycle, and same-close;
- injected missing settlements change `market_digest`;
- an unknown HTE execution string is refused;
- reruns give identical identities, result hashes, window series and decision records.

## 6. Tests

`python -m pytest -q tests/test_manhattan_hte_execution_bridge.py`: **21 passed, 2 skipped** (the cross-checks).
With `EXEC_REALISM_HTE_CHECKOUT` = PR #89 at `232d0d6` and `EXEC_REALISM_PR85_CHECKOUT` = PR #85 at `3f6b213`:
**23 passed**.

| area | tests |
|---|---|
| dormant | `ENABLED` false; the stage refuses and lists C1-C10; non-synthetic provenance refused; imports only `execution_realism`, numpy and the standard library; no I/O, clock, network, broker or token names; nothing imports it (AST) |
| timing | lag 1 by default; lag 0 refused without the allowance; first fill on decision row + 1 with decision-row liquidity; clock refusals |
| vol scaling | perturbation, the naive-rule leak, lag-0 equality with HTE's scaled positions |
| contracts | whole contracts, tick-grid fills, outright and both roll legs, every cost part non-zero, `net = gross − costs`; EUR roots converted with an FX conversion cost; matched costs equal HTE's per-notional cost at the match point; fees above `c` refused |
| provenance | `screening_net`, `scenario` sources with derivation, R4 unmet, presentation refused |
| identity | section 5 |
| planted effects | a same-close effect disappears after the lag; a lag-robust effect disappears after costs (section 7) |
| adverse | missing settlements under `raise` (stops) and `hold` (stale marks exactly the injected ones); a roll blocked by a missing settlement and by capacity fails closed (`RollError`, or `LiquidityError` under `raise`); clipping leaves targets unmet and is reported, and stops under `raise` |
| comparison | four labelled columns, `verified_profitability: false`, no p-values, the disclaimer in the Markdown |
| HTE cross-check | real `generate(SMALL_PANEL)` panels, real templates (`trend` on FX, `meanrev` on rates) through `from_hte`; `kernels.cost_coefficients` equals the fixture's copy; the throughput column equals `kernels.ref_stage3_series` **bit for bit**; lag-0 weights as in section 3 |
| PR #85 cross-check | on bridge output (two rates roots, one EUR, no roll): PR #85's `execution_index` on the bridge's `decided_at` equals the bridge's execution row for every decision; PR #85's `run` on `pr85_decision_records` matches daily gross, costs and positions (1e-6) |

**Mutations.** Each of these made the intended test fail, then was reverted:

- scaling with HTE's lag-0 rule under lag 1 (the leak);
- dropping the clock from the execution block;
- the impact coefficient without its square root.

## 7. HTE throughput-only versus delayed execution

> Synthetic and descriptive only. No column is verified profitability, evidence or a trading return.
> `throughput_only` columns fill at the close the decision read. Delayed columns use scenario-class costs derived
> from HTE's synthetic coefficients on a synthetic panel. No p-value is computed.

The four columns, for the same decisions and window:

- `hte_throughput`: HTE stage 3 arithmetic (same close, proportional `c, k`);
- `hte_lagged`: lag 1 with decision-time scales, proportional;
- `contract_same_close`: the adapter at lag 0;
- `contract_delayed`: the adapter at lag 1.

### 7.1 Bridge fixtures (planted effects; `fixtures.py`, 1,300 rows, 1,000 evaluated days)

| candidate | column | label | ann. mean % | ann. vol % | mean/vol | rolls |
|---|---|---|---|---|---|---|
| reversal (MA(1), θ 0.3) | hte_throughput | throughput_only | 26.39 | 9.43 | 2.80 | |
| | hte_lagged | screening_net | −36.31 | 10.13 | −3.59 | |
| | contract_same_close | throughput_only | 17.43 | 7.75 | 2.25 | |
| | contract_delayed | screening_net | −39.93 | 9.51 | −4.20 | 22 |
| fast_edge, costs ×0 | hte_throughput | throughput_only | 19.76 | 10.09 | 1.96 | |
| | hte_lagged | screening_net | 8.13 | 10.13 | 0.80 | |
| | contract_delayed | screening_net | 7.86 | 9.54 | 0.82 | 42 |
| fast_edge, matched costs | hte_throughput | throughput_only | −1.05 | 10.14 | −0.10 | |
| | hte_lagged | screening_net | −12.90 | 10.22 | −1.26 | |
| | contract_delayed | screening_net | −9.64 | 9.64 | −1.00 | 42 |
| null (20-day trend) | hte_throughput | throughput_only | −4.66 | 10.18 | −0.46 | |
| | contract_delayed | screening_net | −6.30 | 9.39 | −0.67 | 59 |

What the fixtures show:

- **Reversal:** the planted same-close effect disappears after one day of lag; the timing effect is 6.4 in
  mean/vol.
- **fast_edge:** survives the lag gross (0.82), and the costs remove it (−1.00).

### 7.2 HTE's own synthetic panels and templates (PR #89 `generate(PanelParams(...))`, 2,220 evaluated days)

Run from a #89 checkout. The script is not committed; it is the cross-check's code at full size.

| candidate | world | hte_throughput | hte_lagged | contract_same_close | contract_delayed (rolls) |
|---|---|---|---|---|---|
| trend 120 sign, commodity | planted 0.05 | 0.18 | 0.15 | 0.05 | **0.02** (413) |
| trend 10 sign daily, fx | planted 0.05 | −0.32 | −0.46 | −0.63 | −0.78 (295) |
| meanrev 10, rates | planted 0.05 | −1.57 | −1.48 | −1.91 | −1.80 (202) |
| carry ts 60, rates | planted 0.05 | −1.03 | −0.99 | −1.35 | −1.31 (280) |
| trend 120 sign, commodity | null | −0.65 | −0.59 | −0.74 | −0.70 (411) |
| trend 10 sign daily, fx | null | −0.78 | −0.84 | −1.03 | −1.11 (295) |
| meanrev 10, rates | null | −1.28 | −1.21 | −1.56 | −1.48 (200) |
| carry ts 60, rates | null | −0.92 | −0.88 | −1.22 | −1.19 (280) |

(mean/vol of the daily net series over capital; every `contract_delayed` cell is `screening_net`, every
`*_throughput`/`*_same_close` cell is `throughput_only`.)

**Where contract execution costs more than HTE's model, with HTE's own cost level** (planted world, lag 1):

| | HTE proportional cost | contract costs, rolls every 63 days | contract costs, no rolls |
|---|---|---|---|
| carry ts 60, rates | 1.25 %/yr | 5.21 %/yr (roll legs 2.96) | 1.71 %/yr |
| trend 120, commodity | 1.96 %/yr | 2.99 %/yr (roll legs 1.09) | 2.53 %/yr |

The largest gap is **rolls**: HTE trades none, while each roll trades the whole position twice, with impact on
both legs. Next are whole-tick rounding (rates' matched spread is 0.6 tick, so rounding nearly doubles it) and the
whole-contract floor on small daily rebalances. HTE's planted commodity trend goes from 0.18 to 0.02 on these
assumptions. None of these numbers is a market estimate.

**Runtime** (one delayed evaluation, 2,220 days, 8-12 roots, this container): 0.6-0.9 s; a four-column
`compare`: 1.3-2.1 s. At HTE's 10^6-candidate scale (617,584 computed stage-3 simulations), one delayed
evaluation per representative would be about 120-150 CPU-hours (C11).

## 8. Connection requirements (all must hold before `ENABLED` or `HteExecutionStage` changes)

| id | requirement | owner |
|---|---|---|
| C1 | PR #85 and PR #93 merged; #93's conformance tests made permanent (no checkout skip), or the adapter's fill delegated to `manhattan.execution.fill_order` | design |
| C2 | PR #89 merged. HTE gains a policy field `lag` (default 1) and a contract-execution stage that calls this bridge only on stage-3 representatives (aliases copy results). HTE's stage-3 vol scale is replaced by the decision-time scale. `kernels.EXECUTION_TIMING` in `run_identity` and `evaluation_spec` is replaced by `identity.executable_spec` | HTE owner |
| C3 | PR #86 attempt accounting merged, with D-1, D-10 and B4 decided. The attempt's `spec_hash` is the bridge's, and both `data_hash` and `market_digest` are recorded (PR #85 design section 16 item 6) | Ethan |
| C4 | A deterministic, private panel builder from em-macro-data settlements with `known_at` times, contract metadata history and roll dates from PR #85's `RollPolicy`, replacing `contractise`. Only digests and aggregates are public (hard rule 7). The same `data_hash` must always give the same `market_digest` | Ethan / data |
| C5 | Cost terms with `recorded` / `published_schedule` sources valid for the window (Protocol v3.1 section 10), replacing `hte_matched_costs`. Until then every result is `screening_net` | Ethan |
| C6 | Point-in-time ADV and volatility per contract month | data |
| C7 | Per-exchange close times and publication delays from availability records (`manhattan/availability.py`), replacing `DecisionClock` defaults; decisions still precede the next close | data |
| C8 | Roll-binding and opening-month cases (#93 D1, D2) routed to PR #85's `run` or accepted as fail-closed and counted | design |
| C9 | The execution methodology (lag, clock, vol rule, cost sources, sensitivity rows) pre-registered before any use on exploration data | Ethan (hard rule 4) |
| C10 | The synthetic-only guard lifted only by a change Ethan approves; `config/manhattan.yaml` switches unchanged | Ethan |
| C11 | A compute budget. About 0.8 s per delayed evaluation means 120-150 CPU-hours per 10^6-candidate HTE run if every representative is executed. Either a vectorised contract stage (validated against this bridge) or a recorded, outcome-blind subset rule is required | design |

The code holds C1-C10 as `bridge.CONNECTION_REQUIREMENTS`, and `HteExecutionStage` prints them. C11 is
documentation (a budget, not a switch).

## 9. Limitations

- Contractisation is synthetic: one held month at a time, a fixed roll cycle, a constant calendar spread and
  template ADV. It stands in for C4 and describes no market.
- Matched costs equal HTE's only at the match point. Elsewhere the contract model differs by design.
- FX: HTE's returns are excess returns in the base currency, but EUR roots here also carry the synthetic EURUSD
  translation of their P&L.
- The adapter's divergences D1-D6 from PR #85 apply (#93 design section 2). The PR #85 cross-check covers a window
  without rolls.
