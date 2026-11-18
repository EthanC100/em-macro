"""Small synthetic workloads for tests and examples (synthetic only)."""
from __future__ import annotations

from . import data as D
from . import registry as R
from . import templates as TP

SMALL_PANEL = D.PanelParams(seed=7, n_days=760, protected_days=100)     # 360 evaluated days


def small_grids() -> dict:
    return {
        "trend": {"lookback": [10, 40, 120], "shape": ["sign", "linear"], "vol_halflife": [20], "rebalance": [1, 5]},
        "xsmom": {"lookback": [20, 120], "skip": [0, 5], "quantile": [0.25, 0.3], "rebalance": [5]},
        "meanrev": {"lookback": [10, 60], "entry": [1.0, 2.0], "hold": [3]},
        "breakout": {"lookback": [20, 100], "hold": [5]},
        "carry": {"smooth": [5, 60], "mode": ["ts", "xs"], "quantile": [0.25], "rebalance": [5]},
    }


def small_bundles(domains=("fx", "rates"), templates=TP.PRODUCTION_TEMPLATES, cost_models=("c1", "c2"),
                  sizings=("unit_risk",), grids: dict | None = None) -> list[R.Bundle]:
    g = grids or small_grids()
    out = []
    for tname in templates:
        t = TP.TEMPLATES[tname]
        fam = R.family(t.family["name"], t.family["mechanism"], t.family["sign"], t.family["density"])
        for dom in domains:
            hyp = R.hypothesis(fam, dom)
            out.append(R.Bundle(fam, hyp, R.strategy_spec(hyp, tname, g[tname], cost_models=cost_models,
                                                          sizings=sizings, label=f"{tname}/{dom}")))
    return out
