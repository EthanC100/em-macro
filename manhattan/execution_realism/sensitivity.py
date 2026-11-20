"""Cost and lag sensitivity on the same decisions, the optimism gap of same-close fills, and break-even costs.

* ``grid`` runs one plan under every (lag, cost multiple, shock) combination and returns one row each, labelled.
  The decisions are fixed: a weight row is re-sized only from data known at its own decision, whatever the lag.
* ``optimism_gap`` compares a same-close run with a delayed run of the same decisions.
* ``break_even_multiple`` finds the cost multiple at which the total net P&L is zero. Net P&L does not increase
  with the multiple (every price-moving cost grows, adverse tick rounding never shrinks, fees are linear, and the
  participation cap is not scaled), so a bisection is exact up to its tolerance.
"""
from __future__ import annotations

import math
from dataclasses import replace

from . import realism
from .adapter import ExecutionPolicy, Shocks, execute
from .costs import CostModel
from .timing import ExecutionTiming

DEFAULT_MULTIPLES = (0.0, 1.0, 2.0)


def _policy(policy: ExecutionPolicy, lag: int) -> ExecutionPolicy:
    return replace(policy, timing=ExecutionTiming(lag, allow_same_close=(lag == 0)))


def grid(panel, costs: CostModel, policy: ExecutionPolicy, *, weights=None, contracts=None,
         lags=None, multiples=DEFAULT_MULTIPLES, shocks=(None,)) -> list[dict]:
    lags = tuple(lags) if lags is not None else (policy.lag, policy.lag + 1)
    rows = []
    for lag in lags:
        for k in multiples:
            cm = costs if k == 1 else costs.scaled(k)
            for sh in shocks:
                r = execute(panel, cm, _policy(policy, lag), weights=weights, contracts=contracts, shocks=sh)
                a = realism.assess(r)
                st = r.stats()
                tot = r.totals()
                rows.append({"lag": lag, "cost_multiple": float(k), "shock": (sh or Shocks()).name,
                             "label": a.label, "cost_class": a.cost_class, "gross": tot["gross"],
                             "costs": tot["costs"], "net": tot["net"], "ann_net_return": st["ann_net_return"],
                             "sharpe": st["sharpe"], "ann_cost_drag": st["ann_cost_drag"],
                             "ann_turnover": st["ann_turnover"], "n_unfilled": tot["n_unfilled"],
                             "n_stale_marks": tot["n_stale_marks"], "result_hash": r.result_hash()})
    return rows


def optimism_gap(panel, costs: CostModel, policy: ExecutionPolicy, *, weights=None, contracts=None,
                 lag: int = 1) -> dict:
    """Same decisions, same costs: same-close (lag 0) against ``lag``. The gap is what HTE's convention adds."""
    r0 = execute(panel, costs, _policy(policy, 0), weights=weights, contracts=contracts)
    r1 = execute(panel, costs, _policy(policy, lag), weights=weights, contracts=contracts)
    s0, s1 = r0.stats(), r1.stats()
    return {"lag": lag, "same_close_ann_net_return": s0["ann_net_return"], "delayed_ann_net_return":
            s1["ann_net_return"], "gap_ann_net_return": s0["ann_net_return"] - s1["ann_net_return"],
            "same_close_sharpe": s0["sharpe"], "delayed_sharpe": s1["sharpe"],
            "gap_sharpe": s0["sharpe"] - s1["sharpe"], "same_close_label": realism.assess(r0).label,
            "delayed_label": realism.assess(r1).label}


def break_even_multiple(panel, costs: CostModel, policy: ExecutionPolicy, *, weights=None, contracts=None,
                        hi: float = 64.0, tol: float = 1e-3) -> float:
    """The smallest cost multiple at which total net P&L is at most zero: ``0.0`` when the gross is not positive,
    ``inf`` when even ``hi`` leaves it positive."""
    def net(k):
        return execute(panel, costs.scaled(k), policy, weights=weights, contracts=contracts).totals()["net"]
    if net(0.0) <= 0:
        return 0.0
    if net(hi) > 0:
        return math.inf
    lo_k, hi_k = 0.0, hi
    while hi_k - lo_k > tol:
        mid = 0.5 * (lo_k + hi_k)
        if net(mid) > 0:
            lo_k = mid
        else:
            hi_k = mid
    return hi_k
