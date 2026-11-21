"""Synthetic fixtures: a small contract-aware futures world and two planted effects. **Synthetic only.**

Three made-up roots on a made-up exchange (no number describes a market):

| root | currency | tick | multiplier | tick value | start level | daily vol | calendar spread per quarter |
|---|---|---|---|---|---|---|---|
| ``SYNA`` | USD | 0.01 | 1,000 | 10 | 60 | 1.5% | +0.40 (contango) |
| ``SYNR`` | USD | 1/64 | 1,000 | 15.625 | 110 | 0.4% | −0.25 (backwardation) |
| ``SYNE`` | EUR | 0.5 | 10 | 5 | 3,000 | 1.0% | +5.0 |

Each root holds one quarterly month at a time and rolls every 63 trading days into the next, whose settlement sits
one calendar spread away. Settlements are whole ticks. Log returns of the underlying are

    r_t = σ (e_t − θ e_{t−1}) + κ σ sign(m_{t−1}),      m = the sum of the last 60 returns

* ``θ`` (``reversal``) plants an **MA(1) reversal**: yesterday's move predicts today's with the opposite sign, and
  nothing beyond. A same-close strategy that fades day ``t``'s move earns day ``t + 1``'s reversal; with a one-day
  lag it trades day ``t + 2``, where there is nothing to earn. It is the textbook case of an effect that exists only
  under same-close fills.
* ``κ`` (``trend``) plants a **slow trend** that survives a one-day lag but not unlimited costs.

``world`` returns a ``SettlementPanel``; ``reversal_weights`` and ``trend_weights`` are causal strategies (row ``t``
reads data through the close of ``t`` only). ``synthetic_costs`` gives ``synthetic``-labelled cost terms;
``fixture_sourced_costs`` gives the same numbers with non-scenario labels whose references say plainly that they
are test fixtures, so that the realism gate's other branches can be exercised.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .costs import CostModel, CostValue, RootCosts, synthetic
from .instruments import Instrument
from .panel import SettlementPanel
from .provenance import Source

ROOTS = {
    # root: (instrument, start level, daily vol, spread per quarter in ticks, ADV contracts)
    "SYNA": (Instrument("SYNA", "USD", 0.01, 10.0, 1000.0), 60.0, 0.015, 40, 20000.0),
    "SYNR": (Instrument("SYNR", "USD", 0.015625, 15.625, 1000.0), 110.0, 0.004, -16, 60000.0),
    "SYNE": (Instrument("SYNE", "EUR", 0.5, 5.0, 10.0), 3000.0, 0.010, 10, 5000.0),
}
ROLL_EVERY = 63


def weekdays(start: date, n: int) -> list:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def world(n: int = 756, *, seed: int = 20261119, reversal: float = 0.3, trend: float = 0.06,
          roots=("SYNA", "SYNR", "SYNE"), missing=(), adv_scale: float = 1.0, start: date = date(2001, 1, 2),
          data_kind: str = "synthetic") -> SettlementPanel:
    """``missing``: ``(day index, root)`` pairs with no settlement for any month of that root."""
    rng = np.random.default_rng(seed)
    days = weekdays(start, n)
    insts, prices, held, adv, vol = [], {}, {}, np.zeros((n, len(roots))), np.zeros((n, len(roots)))
    miss = set(missing)
    for a, root in enumerate(roots):
        inst, p0, sig, gap, adv0 = ROOTS[root]
        e = rng.standard_normal(n + 1)
        r = np.zeros(n)
        logp = np.zeros(n)
        lp = np.log(p0)
        for t in range(n):
            m = r[max(0, t - 60):t].sum() if t else 0.0
            r[t] = sig * (e[t + 1] - reversal * e[t]) + trend * sig * np.sign(m)
            lp += r[t]
            logp[t] = lp
        base_ticks = np.round(np.exp(logp) / inst.tick_size)
        n_q = n // ROLL_EVERY + 2
        book = {}
        for k in range(n_q):
            ticks = base_ticks + k * gap
            px = np.round(ticks * inst.tick_size, 10)
            for t in range(n):
                if (t, root) in miss:
                    px[t] = np.nan
            book[f"{root}Q{k:03d}"] = px
        prices[root] = book
        held[root] = [f"{root}Q{t // ROLL_EVERY:03d}" for t in range(n)]
        insts.append(inst)
        adv[:, a] = adv0 * adv_scale
        vol[:, a] = sig * np.exp(logp)                 # a model estimate known at each close: σ × level
    fx = {}
    if any(ROOTS[r][0].currency == "EUR" for r in roots):
        fx["EUR"] = np.round(1.10 * np.exp(np.cumsum(0.005 * rng.standard_normal(n))), 6)
    return SettlementPanel.from_contracts(days=days, instruments=insts, prices=prices, held=held, adv=adv,
                                          vol_points=vol, base_currency="USD", fx=fx, data_kind=data_kind)


def same_contract_changes(panel: SettlementPanel) -> np.ndarray:
    """``(n, A)`` relative same-contract change of day ``t`` (row 0 and missing days: 0). Known at close ``t``."""
    n, A = panel.shape
    out = np.zeros((n, A))
    for a in range(A):
        last = np.nan
        for t in range(n):
            ex = panel.exit_level[t, a]
            if np.isfinite(ex) and np.isfinite(last) and last != 0:
                out[t, a] = (ex - last) / abs(last)
            lv = panel.level[t, a]
            if np.isfinite(lv):
                last = lv
    return out


def _risk_weights(panel: SettlementPanel, ann_vol: float) -> np.ndarray:
    sig = np.array([ROOTS[r][2] for r in panel.roots])
    return (ann_vol / np.sqrt(252.0)) / sig / len(sig)


def reversal_weights(panel: SettlementPanel, ann_vol: float = 0.10) -> np.ndarray:
    """Fade day ``t``'s move: weight ``−sign(change_t) × risk weight``; no decision on day 0."""
    ch = same_contract_changes(panel)
    W = -np.sign(ch) * _risk_weights(panel, ann_vol)
    W[0] = np.nan
    return W


def trend_weights(panel: SettlementPanel, ann_vol: float = 0.10, lookback: int = 60) -> np.ndarray:
    ch = same_contract_changes(panel)
    W = np.full(ch.shape, np.nan)
    rw = _risk_weights(panel, ann_vol)
    for t in range(lookback, ch.shape[0]):
        W[t] = np.sign(ch[t - lookback + 1: t + 1].sum(axis=0)) * rw
    return W


def _terms(fee_ccy: str, mk, fxc=None) -> RootCosts:
    return RootCosts(fee_ccy, mk("commission", 1.0), mk("exchange_fee", 0.5), mk("half_spread_ticks", 0.5),
                     mk("slippage_ticks", 0.5), mk("impact_coefficient", 0.1), mk("max_participation", 0.1),
                     None if fxc is None else mk("fx_conversion_bps", fxc))


def synthetic_costs(roots=("SYNA", "SYNR", "SYNE"), name: str = "synthetic base") -> CostModel:
    def mk(_c, v):
        return synthetic(v)
    return CostModel(name, tuple((r, _terms("EUR" if r == "SYNE" else "USD", mk, 1.0 if r == "SYNE" else None))
                                 for r in roots))


FIXTURE_REF = "TEST FIXTURE ONLY: not a real source; exercises the provenance gate"


def fixture_sourced_costs(roots=("SYNA", "SYNR", "SYNE"), *, known_from: date = date(2001, 1, 1),
                          known_to: date = date(2010, 12, 31)) -> CostModel:
    """The same numbers as ``synthetic_costs``, labelled known (fees) and estimated (the rest). The references say
    they are fixtures: the labels test the gate's logic, they describe nothing real."""
    def mk(c, v):
        if c in ("commission", "exchange_fee"):
            return CostValue(v, Source("published_schedule", FIXTURE_REF, known_from, known_to))
        if c == "impact_coefficient":
            return CostValue(v, Source("model_estimate", FIXTURE_REF))
        return CostValue(v, Source("literature_estimate", FIXTURE_REF))
    return CostModel("fixture-sourced", tuple((r, _terms("EUR" if r == "SYNE" else "USD", mk,
                                                         1.0 if r == "SYNE" else None)) for r in roots))
