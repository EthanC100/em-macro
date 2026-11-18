"""Synthetic benchmark workloads: families x domains x horizons x parameter grids. **Synthetic only.**

Five template families (dense trend, cross-sectional momentum and carry; sparse mean reversion and breakout) in three
domains (commodity, rates, FX) give 15 hypotheses. Each hypothesis has two strategy specs, one per horizon (short:
look-backs up to 60 days; long: 61-260 days), so time horizons are separate specs rather than one giant grid.
Every spec binds two cost models and two sizing rules.

Grids are dense in correlated directions on purpose (adjacent look-backs, nearby thresholds), and several axes are
irrelevant for some points (``vol_halflife`` when ``shape == "sign"``; ``quantile`` steps finer than one asset), so
behavioural aliases occur as they would in a real grid search. ``build(target)`` scales every scalable axis until
the candidate count is as close to ``target`` as the integer axes allow and reports the exact count.
"""
from __future__ import annotations

import math

import numpy as np

from . import data as D
from . import registry as R
from . import templates as TP

HORIZONS = {"short": (5, 60), "long": (61, 260)}


def _ints(lo: int, hi: int, n: int) -> list[int]:
    return sorted({int(round(x)) for x in np.linspace(lo, hi, max(1, n))})


def _floats(lo: float, hi: float, n: int) -> list[float]:
    return [float(round(x, 6)) for x in np.linspace(lo, hi, max(1, n))] if n > 1 else [float(round((lo + hi) / 2, 6))]


def _axis(base: int, m: float, d: int, cap: int) -> int:
    return int(min(cap, max(1, round(base * m ** (1.0 / d)))))


def grids(m: float) -> dict:
    """Template -> horizon -> grid at scale m (m = 1 is about 40 points per spec)."""
    out = {}
    for hz, (lo, hi) in HORIZONS.items():
        cap_l = hi - lo + 1
        out.setdefault("trend", {})[hz] = {
            "lookback": _ints(lo, hi, _axis(5, m, 3, min(cap_l, 120))), "shape": ["sign", "linear"],
            "vol_halflife": _ints(10, 120, _axis(2, m, 3, 60)), "rebalance": _ints(1, 21, _axis(2, m, 3, 21))}
        out.setdefault("xsmom", {})[hz] = {
            "lookback": _ints(max(lo, 10), hi, _axis(5, m, 4, min(cap_l, 120))),
            "skip": _ints(0, 21, _axis(2, m, 4, 22)), "quantile": _floats(0.1, 0.5, _axis(2, m, 4, 40)),
            "rebalance": _ints(1, 21, _axis(2, m, 4, 21))}
        out.setdefault("meanrev", {})[hz] = {
            "lookback": _ints(lo, hi, _axis(5, m, 3, min(cap_l, 120))),
            "entry": _floats(0.75, 3.0, _axis(4, m, 3, 200)), "hold": _ints(1, 21, _axis(2, m, 3, 21))}
        out.setdefault("breakout", {})[hz] = {
            "lookback": _ints(lo, min(hi, TP.MAX_LOOKBACK - 1), _axis(5, m, 2, min(cap_l, 120))),
            "hold": _ints(1, 21, _axis(8, m, 2, 21))}
        out.setdefault("carry", {})[hz] = {
            "smooth": _ints(max(lo, 1) if hz == "long" else 1, min(hi, TP.MAX_LOOKBACK - 1),
                            _axis(5, m, 3, min(cap_l, 120))),
            "mode": ["ts", "xs"], "quantile": _floats(0.1, 0.5, _axis(2, m, 3, 40)),
            "rebalance": _ints(1, 21, _axis(2, m, 3, 21))}
    return out


def bundles_at(m: float, domains=D.DOMAINS, cost_models=("c1", "c2"), sizings=TP.SIZINGS) -> list[R.Bundle]:
    out = []
    g = grids(m)
    for tname in TP.PRODUCTION_TEMPLATES:
        t = TP.TEMPLATES[tname]
        fam = R.family(t.family["name"], t.family["mechanism"], t.family["sign"], t.family["density"])
        for dom in domains:
            hyp = R.hypothesis(fam, dom)
            for hz in HORIZONS:
                spec = R.strategy_spec(hyp, tname, g[tname][hz], cost_models=cost_models, sizings=sizings)
                out.append(R.Bundle(fam, hyp, spec))
    return out


def count(bundles) -> int:
    return sum(R.grid_size(b.spec) for b in bundles)


def build(target: int, **kw) -> tuple[list[R.Bundle], float]:
    """Bundles whose candidate count is as close to ``target`` as the axes allow; returns (bundles, scale)."""
    best = None
    lo, hi = 0.01, 1e6
    for _ in range(60):
        m = math.sqrt(lo * hi)
        b = bundles_at(m, **kw)
        n = count(b)
        if best is None or abs(n - target) < abs(best[0] - target):
            best = (n, m, b)
        if n < target:
            lo = m
        else:
            hi = m
        if hi / lo < 1.0005:
            break
    return best[2], best[1]
