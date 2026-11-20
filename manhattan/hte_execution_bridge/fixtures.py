"""HTE-shaped synthetic candidates with planted effects. **Synthetic only.**

Each fixture is what HTE would hand the bridge: a ``(days, assets)`` return panel on a weekday calendar starting
3 January 2000 (HTE's), signed positions whose row ``t`` reads data through close ``t``, a data hash and synthetic
provenance. ``domain`` selects the instrument template (default ``commodity``: daily vol 1.5%, HTE's commodity
costs ``c = 4e-4``, ``k = 2e-3``, copied from ``manhattan/hte/kernels.py`` at 232d0d6 and cross-checked when an HTE
checkout is given).

| kind | returns | positions | what should happen |
|---|---|---|---|
| ``reversal`` | MA(1): ``r_t = σ(e_t − θ e_{t−1})`` | fade day ``t``'s move | strong at the same close; nothing after a 1-day lag; negative net |
| ``fast_edge`` | ``r_t = σ(e_t + β x_{t−1})``, ``x`` AR(1) with ``φ`` | ``sign(x_t)`` (high turnover) | survives a 1-day lag gross; costs remove it |
| ``null`` | ``r_t = σ e_t`` | 20-day trend sign | nothing, before or after |
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

import numpy as np

from .bridge import CandidateInput

GENERATOR = "hte_bridge.fixtures/1"
HTE_COSTS = {"commodity": (4e-4, 2e-3), "rates": (1e-4, 5e-4), "fx": (1.5e-4, 8e-4)}   # HTE kernels.COSTS
VOL = {"commodity": 0.015, "rates": 0.004, "fx": 0.006}
KINDS = ("reversal", "fast_edge", "null")


def weekdays(n: int, start: date = date(2000, 1, 3)) -> tuple:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return tuple(out)


def candidate(kind: str, *, n: int = 1300, assets: int = 4, seed: int = 7, domain: str = "commodity",
              theta: float = 0.3, beta: float = 0.06, phi: float = 0.6, cost_multiplier: float = 1.0) -> CandidateInput:
    if kind not in KINDS:
        raise ValueError(f"kind is one of {KINDS}")
    rng = np.random.default_rng([seed, KINDS.index(kind), assets, n])
    sig = VOL[domain]
    e = rng.standard_normal((n + 1, assets))
    u = 0.10 / np.sqrt(252.0) / sig / assets                    # unit-risk weight per asset
    if kind == "reversal":
        R = sig * (e[1:] - theta * e[:-1])
        P = -np.sign(R) * u
    elif kind == "fast_edge":
        x = np.zeros((n, assets))
        z = rng.standard_normal((n, assets))
        for t in range(1, n):
            x[t] = phi * x[t - 1] + np.sqrt(1 - phi * phi) * z[t]
        R = sig * e[1:]
        R[1:] += sig * beta * x[:-1]
        P = np.sign(x) * u
    else:
        R = sig * e[1:]
        cs = np.cumsum(R, axis=0)
        P = np.zeros_like(R)
        P[20:] = np.sign(cs[20:] - cs[:-20]) * u
    P = P + 0.0
    params = {"generator": GENERATOR, "kind": kind, "n": n, "assets": assets, "seed": seed, "domain": domain,
              "theta": theta, "beta": beta, "phi": phi}
    h = hashlib.sha256(json.dumps(params, sort_keys=True).encode())
    h.update(np.ascontiguousarray(R).tobytes())
    h.update(np.ascontiguousarray(P).tobytes())
    c, k = HTE_COSTS[domain]
    return CandidateInput(f"fixture-{kind}-{seed}", domain, P, R, weekdays(n), h.hexdigest(),
                          {"synthetic": True, "generator": GENERATOR, "params": params},
                          (c * cost_multiplier, k * cost_multiplier))
