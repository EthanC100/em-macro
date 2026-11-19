"""Print how execution assumptions change performance on the synthetic fixtures (stdout only; writes nothing).

    python -m manhattan.execution_realism.demo
"""
from __future__ import annotations

import numpy as np

from . import fixtures as F
from . import sensitivity as S
from .adapter import ExecutionPolicy, Shocks

CAPITAL = 10_000_000.0


def tables() -> dict:
    panel = F.world()
    costs = F.synthetic_costs()
    pol = ExecutionPolicy(capital=CAPITAL, on_liquidity_shortfall="clip")
    out = {}
    n, A = panel.shape
    stress = Shocks("stress: spread x3, slippage x3, ADV x0.2 on days 300-399",
                    spread=np.where((np.arange(n) >= 300)[:, None] & (np.arange(n) < 400)[:, None], 3.0, 1.0)
                    * np.ones((n, A)),
                    slippage=np.where((np.arange(n) >= 300)[:, None] & (np.arange(n) < 400)[:, None], 3.0, 1.0)
                    * np.ones((n, A)),
                    adv=np.where((np.arange(n) >= 300)[:, None] & (np.arange(n) < 400)[:, None], 0.2, 1.0)
                    * np.ones((n, A)))
    for name, W in (("reversal (MA(1), same-close only)", F.reversal_weights(panel)),
                    ("trend (slow, lag-robust)", F.trend_weights(panel))):
        rows = S.grid(panel, costs, pol, weights=W, lags=(0, 1, 2), multiples=(0.0, 1.0, 2.0, 4.0),
                      shocks=(None, stress))
        out[name] = {"rows": rows, "break_even_lag1": S.break_even_multiple(panel, costs, pol, weights=W)}
    return out


def main() -> None:
    for name, t in tables().items():
        print(f"\n{name}   break-even cost multiple at lag 1: {t['break_even_lag1']:.3f}")
        print(f"{'lag':>3} {'cost x':>6} {'shock':<8} {'label':<16} {'ann net %':>9} {'sharpe':>7} "
              f"{'cost drag %':>11} {'unfilled':>8}")
        for r in t["rows"]:
            print(f"{r['lag']:>3} {r['cost_multiple']:>6g} {('stress' if r['shock'] != 'none' else 'none'):<8} "
                  f"{r['label']:<16} {100 * r['ann_net_return']:>9.2f} {r['sharpe']:>7.2f} "
                  f"{100 * r['ann_cost_drag']:>11.2f} {r['n_unfilled']:>8}")


if __name__ == "__main__":
    main()
