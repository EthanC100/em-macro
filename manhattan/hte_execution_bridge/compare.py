"""HTE throughput-only results next to delayed contract execution, for the same candidate and window.

Four columns, each labelled by ``execution_realism.realism.assess``:

| column | timing | costs | label |
|---|---|---|---|
| ``hte_throughput`` | same close (HTE stage 3, bit for bit) | HTE per-notional ``c, k`` | ``throughput_only`` |
| ``hte_lagged`` | lag ``L`` (decision-time vol scale) | HTE per-notional ``c, k`` | ``screening_net`` |
| ``contract_same_close`` | same close | contract terms matched to ``c, k`` | ``throughput_only`` |
| ``contract_delayed`` | lag ``L`` | contract terms matched to ``c, k`` | ``screening_net`` here (scenario costs, synthetic data) |

``effects`` splits the change from ``hte_throughput`` to ``contract_delayed`` into timing (``hte_throughput −
hte_lagged``) and contract execution (``hte_lagged − contract_delayed``: whole contracts, whole ticks, rolls, caps,
FX). Statistics are descriptive: annualised mean and volatility of the daily net series over capital, their ratio
and the window total. **No column is verified profitability, evidence or a trading return**, and no p-value is
computed: the panels are synthetic and every cost is scenario-class.
"""
from __future__ import annotations

import math

import numpy as np

from manhattan.execution_realism import realism as RL
from manhattan.execution_realism import screening as SC

from .bridge import BridgeSettings, CandidateInput, evaluate, with_lag

DISCLAIMER = ("Synthetic and descriptive only. No column is verified profitability, evidence or a trading return. "
              "'throughput_only' columns fill at the close the decision read; delayed columns use scenario-class "
              "costs derived from HTE's synthetic coefficients on a synthetic panel.")
COLUMNS = ("hte_throughput", "hte_lagged", "contract_same_close", "contract_delayed")


def stats(x) -> dict:
    x = np.asarray(x, float)
    n = x.size
    m = float(x.mean()) if n else 0.0
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    return {"days": n, "ann_mean": m * 252.0, "ann_vol": sd * math.sqrt(252.0),
            "ratio": m / sd * math.sqrt(252.0) if sd > 0 else 0.0, "total": float(x.sum())}


def compare(inp: CandidateInput, settings: BridgeSettings = BridgeSettings(), **kw) -> dict:
    if settings.lag < 1:
        raise ValueError("the delayed column needs lag >= 1")
    c, k = inp.hte_costs
    common = dict(warmup=settings.warmup, fence=inp.fence, c=c, k=k, vol_target_ann=settings.vol_target_ann,
                  vol_halflife=settings.vol_halflife, vol_min_obs=settings.vol_min_obs,
                  leverage_cap=settings.leverage_cap, data_kind="synthetic")
    th = SC.series(inp.positions, inp.returns, lag=0, **common)
    lg = SC.series(inp.positions, inp.returns, lag=settings.lag, **common)
    c0 = evaluate(inp, with_lag(settings, 0), **kw)
    cl = evaluate(inp, settings, **kw)
    rows = {
        "hte_throughput": {"label": RL.assess(th).label, **stats(th.net)},
        "hte_lagged": {"label": RL.assess(lg).label, **stats(lg.net)},
        "contract_same_close": {"label": c0.label, **stats(c0.window_net)},
        "contract_delayed": {"label": cl.label, "cost_class": cl.assessment.cost_class, **stats(cl.window_net),
                             "unfilled": len(cl.result.unfilled), "rolls": len(cl.result.rolls),
                             "stale_marks": len(cl.result.stale_marks)},
    }
    eff = {f"timing_{q}": rows["hte_throughput"][q] - rows["hte_lagged"][q] for q in ("ann_mean", "ratio")}
    eff.update({f"contract_{q}": rows["hte_lagged"][q] - rows["contract_delayed"][q] for q in ("ann_mean", "ratio")})
    return {"candidate": inp.candidate_hash, "domain": inp.domain, "lag": settings.lag, "rows": rows,
            "effects": eff, "identity_delayed": cl.identity, "identity_same_close": c0.identity,
            "verified_profitability": False, "disclaimer": DISCLAIMER}


def render_markdown(comparisons: list, names: list | None = None) -> str:
    out = [f"> {DISCLAIMER}", "",
           "| candidate | column | label | ann. mean % | ann. vol % | mean/vol | unfilled | rolls |",
           "|---|---|---|---|---|---|---|---|"]
    for j, cmp_ in enumerate(comparisons):
        name = names[j] if names else cmp_["candidate"][:12]
        for col in COLUMNS:
            r = cmp_["rows"][col]
            out.append(f"| {name} | {col} | {r['label']} | {100 * r['ann_mean']:.2f} | {100 * r['ann_vol']:.2f} | "
                       f"{r['ratio']:.2f} | {r.get('unfilled', '')} | {r.get('rolls', '')} |")
    return "\n".join(out)
