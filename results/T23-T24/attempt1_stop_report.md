# Trials T23–T24, first attempt (superseded by Amendment 2): run stopped before any gate was evaluated

**Status: NOT RUN (stopped by the pre-registered window rule).** No gate, sleeve return, Sharpe ratio, t-statistic or
other result of T23 or T24 has been evaluated, written or printed. The run is **not** re-run; the owner decides how to
proceed.

| item | value |
|---|---|
| pre-registration | `docs/prereg/T23-T24_pre2000_backtest.md` (`215b3c4`) with Amendment 1 (`648534b`) |
| runner | `em_macro/t2324.py` at `ab5306f` (window and reporting only; synthetic tests `tests/test_t2324.py` passed before the run) |
| run | 2026-11-06, one attempt; stop record `results/T23-T24/RUN.json` |
| rules and code | T21 and T22 as run at `a160bfd`, unchanged |

## 1. Checks before the sleeves (§6 step 3): all passed

| check | result |
|---|---|
| D0 SHA-256 of the a160bfd code | pass (all six files identical) |
| D1 Phase 1 availability counts recomputed | pass: identical to the committed `availability_counts.csv` (264 months) |
| D2 A9 and unit breaks on the held series in the window | pass: no market dropped. 15 A9 issues in the window, all curve-confirmed reversing spikes (0 unresolved); no held gap over 5 days; one non-reversing same-contract move above 30% (CL, 1991-01-17, CL-1991H), a market move, not a unit break |
| D3 A3: equal-weight F1 index of the 22 window commodities vs AQR *Commodities for the Long Run* | **0.962** over 249 months (1979-04..1999-12; 16–22 markets a month); 0.961 to 1990-01, 0.967 from 1990-02; threshold 0.90: pass |

## 2. What stopped the run

After D0–D3, the runner checked that the code's own count of active markets reproduces each pre-registered window: at
least 6 active in every window month (§2.1 rule 3 of T20–T22, the definition of the window in §3), and fewer than 6 in
the month before.

| sleeve | min active in window | active in the month before | result |
|---|---|---|---|
| T21 full (T23, from 1979-05) | 6 | 5 | reproduces the window |
| **T22 full (T24, from 1979-04)** | **5** | 5 | **does not: 1979-04 has 5 active instruments** |

Active T22 instruments by the code's definition (entered, not missing, σ and signal defined), against Phase 1 (counts
only, from `results/T23-T24/stop_diagnosis_counts.py`):

| month | 1979-03 | **1979-04** | 1979-05 | 1979-06 | 1979-07 | 1979-08 |
|---|---|---|---|---|---|---|
| code (t2022) | 5 | **5** | 8 | 8 | 9 | 9 |
| Phase 1 (pre-registered) | 5 | **6** | 8 | 8 | 9 | 9 |

**Cause: silver (SI) in 1979-04.**
- Phase 1 replicated the entry rule (§2.1 rule 2, `commod_build0.entry_month`). That rule counts daily-return rows: SI has 272 by the 1979-04 decision date, at least 252 are needed, so SI enters in 1979-04.
- T22's volatility estimate (`t2022.Mkt.sigma_mop`) requires 252 *non-missing* daily returns. SI has 234 by that date: 38 rows have no return because the held contract had no previous settlement.
- So SI has no σ and no signal in 1979-04, and becomes active in 1979-05 (255 non-missing returns).
- By the pre-registration's own definition, T24's first month with at least 6 active instruments is **1979-05**, not the pre-registered **1979-04**.

T23's window is unaffected (6 active in 1979-05, 5 in 1979-04, as pre-registered).

## 3. What was computed before the stop (disclosure)

The window check ran **after** the seven sleeves (T21 and T22 full and halves, the T20 control) had been built in
memory. That includes their held weights and daily P&L. This ordering was my mistake: the check should have run
before any sleeve.

The process stopped at the check and exited. **No sleeve series, gate, return or statistic was evaluated, written to
disk or printed.** The only files written were the D0–D3 records (`RUN.json`) and the private D3/D2 data-check series
(A3 window series, A9 issues).

## 4. Not done, pending the owner's decision

The run is not repeated. The possible ways forward change a pre-registered item, so they are the owner's:
- **(a)** Move T24's window to **1979-05..1999-12** (the first month the code has 6), by an amendment.
- **(b)** Keep 1979-04 and apply rule 3 to T24's first month (no positions in 1979-04).
- **(c)** Leave the trials not run.

Under (a) or (b) the run would be the first evaluation of any gate. Sub-window (a) of Amendment 1 would start in
1979-05 for both trials.

The AWS instance was started for the private push and stopped afterwards.
