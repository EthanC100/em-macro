"""Signal templates: synthetic hypothesis families and their vectorised position builders.

A template turns cached features into positions ``(T, A)``: row ``t`` is the position held from the close of day
``t``, built only from rows ``<= t`` of the features. The kernels apply row ``t`` to the return of day ``t + 1``;
no template can change that lag (it is applied by the kernel, not here).

The five templates are deliberately generic, textbook signal shapes so that benchmarks exercise dense and sparse
signals, short and long horizons and cross-sectional and time-series logic. Their mechanism texts are synthetic
labels for workloads, not research claims.

    trend      time-series momentum                  dense   look-backs 5-260 days
    xsmom      cross-sectional momentum (rank, skip)  dense
    meanrev    z-score reversal with a holding period sparse
    breakout   new L-day high/low with a holding period  sparse
    carry      carry (time-series sign or cross-sectional rank) dense, slow

Every template declares a parameter schema; ``validate_params`` is stage 0's static check. Unknown parameters,
values out of range, wrong types and look-backs that do not fit inside the warm-up are refused.

``positions`` is pure: the same cache, domain and parameters give bit-identical output.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

MAX_LOOKBACK = 260                       # every feature must be defined by the evaluation warm-up (policy.warmup)
SIZINGS = ("unit_risk", "equal")
COST_MODELS = {"c1": 1.0, "c2": 2.0}     # multiplier on the domain's base costs (kernels.COSTS)
ANN_RISK = 0.10


@dataclass(frozen=True)
class Template:
    name: str
    version: int
    family: dict                                         # {"name", "mechanism", "sign", "density"}
    schema: dict                                         # param -> ("int", lo, hi) | ("float", lo, hi) | ("choice", (..))
    lookback: Callable[[dict], int]
    build: Callable                                      # (cache, dom, params) -> raw signal (T, A) in [-1, 1]
    feats: Callable[[dict], list] = lambda p: []          # (feature, params) pairs the build reads (cache warm-up)
    test_only: bool = False
    extra: dict = field(default_factory=dict)


def _hold(sig: np.ndarray, k: int) -> np.ndarray:
    """Rebalance every k days: the position on day t is the signal of the last rebalance day <= t."""
    if k <= 1:
        return sig
    idx = (np.arange(sig.shape[0]) // k) * k
    return sig[idx]


def _rolling_hold(entries: np.ndarray, h: int) -> np.ndarray:
    """Hold each entry for h days (including the entry day): clip of the trailing h-day sum of entries."""
    cs = np.cumsum(entries, axis=0)
    out = cs.copy()
    out[h:] = cs[h:] - cs[:-h]
    return np.clip(out, -1.0, 1.0)


def _xs_long_short(x: np.ndarray, q: float) -> np.ndarray:
    """+1 for the top fraction q of assets each day, -1 for the bottom q (ties broken by asset order, stable);
    rows with any NaN are flat."""
    T, A = x.shape
    k = max(1, int(math.floor(q * A + 1e-9)))
    out = np.zeros_like(x)
    ok = ~np.isnan(x).any(axis=1)
    if not ok.any():
        return out
    order = np.argsort(x[ok], axis=1, kind="stable")
    rows = np.flatnonzero(ok)
    sub = np.zeros((rows.size, A))
    np.put_along_axis(sub, order[:, :k], -1.0, axis=1)
    np.put_along_axis(sub, order[:, A - k:], 1.0, axis=1)
    out[rows] = sub
    return out


# -- builders ------------------------------------------------------------------------------------------------

def _trend(cache, dom, p):
    mom = cache.get(dom, "mom", L=p["lookback"])
    if p["shape"] == "sign":
        s = np.sign(mom)
    else:
        vol = cache.get(dom, "ewvol", hl=p["vol_halflife"])
        with np.errstate(invalid="ignore", divide="ignore"):
            s = np.clip(mom / (vol * math.sqrt(p["lookback"])) / 2.0, -1.0, 1.0)
    return _hold(np.nan_to_num(s, nan=0.0), p["rebalance"])


def _xsmom(cache, dom, p):
    L, S = p["lookback"], p["skip"]
    mom = cache.get(dom, "mom", L=L)
    if S:
        mom = mom - cache.get(dom, "mom", L=S)          # return from t-L to t-S
    return _hold(_xs_long_short(mom, p["quantile"]), p["rebalance"])


def _meanrev(cache, dom, p):
    z = cache.get(dom, "zscore", L=p["lookback"])
    e = p["entry"]
    entries = np.where(np.isnan(z), 0.0, -np.sign(z) * (np.abs(z) > e))
    return _rolling_hold(entries, p["hold"])


def _breakout(cache, dom, p):
    L = p["lookback"]
    cum = cache.get(dom, "cum")
    hi = cache.get(dom, "hi", L=L)
    lo = cache.get(dom, "lo", L=L)
    prev_hi = np.full_like(hi, np.nan)
    prev_lo = np.full_like(lo, np.nan)
    prev_hi[1:] = hi[:-1]
    prev_lo[1:] = lo[:-1]
    with np.errstate(invalid="ignore"):
        entries = (cum > prev_hi).astype(float) - (cum < prev_lo).astype(float)
    return _rolling_hold(entries, p["hold"])


def _carry(cache, dom, p):
    c = cache.get(dom, "carry", L=p["smooth"])
    if p["mode"] == "ts":
        s = np.nan_to_num(np.sign(c), nan=0.0)
    else:
        s = _xs_long_short(c, p["quantile"])
    return _hold(s, p["rebalance"])


TEMPLATES: dict[str, Template] = {}


def register(t: Template) -> Template:
    if t.name in TEMPLATES and TEMPLATES[t.name] is not t:
        raise ValueError(f"template {t.name!r} already registered")
    TEMPLATES[t.name] = t
    return t


register(Template(
    "trend", 1,
    {"name": "synthetic-trend", "mechanism": "SYNTHETIC LABEL: slow-moving information diffuses gradually",
     "sign": "+", "density": "dense"},
    {"lookback": ("int", 5, MAX_LOOKBACK), "shape": ("choice", ("sign", "linear")),
     "vol_halflife": ("int", 5, 120), "rebalance": ("int", 1, 21)},
    lambda p: p["lookback"], _trend,
    lambda p: [("mom", {"L": p["lookback"]})] + ([("ewvol", {"hl": p["vol_halflife"]})] if p["shape"] != "sign" else [])))
register(Template(
    "xsmom", 1,
    {"name": "synthetic-xs-momentum", "mechanism": "SYNTHETIC LABEL: relative winners keep winning",
     "sign": "+", "density": "dense"},
    {"lookback": ("int", 10, MAX_LOOKBACK), "skip": ("int", 0, 21), "quantile": ("float", 0.1, 0.5),
     "rebalance": ("int", 1, 21)},
    lambda p: p["lookback"], _xsmom,
    lambda p: [("mom", {"L": p["lookback"]})] + ([("mom", {"L": p["skip"]})] if p["skip"] else [])))
register(Template(
    "meanrev", 1,
    {"name": "synthetic-mean-reversion", "mechanism": "SYNTHETIC LABEL: liquidity providers are paid to absorb flow",
     "sign": "+", "density": "sparse"},
    {"lookback": ("int", 5, MAX_LOOKBACK), "entry": ("float", 0.5, 4.0), "hold": ("int", 1, 21)},
    lambda p: p["lookback"], _meanrev, lambda p: [("zscore", {"L": p["lookback"]})]))
register(Template(
    "breakout", 1,
    {"name": "synthetic-breakout", "mechanism": "SYNTHETIC LABEL: stops cluster beyond recent extremes",
     "sign": "+", "density": "sparse"},
    {"lookback": ("int", 5, MAX_LOOKBACK - 1), "hold": ("int", 1, 21)},
    lambda p: p["lookback"] + 1, _breakout,
    lambda p: [("cum", {}), ("hi", {"L": p["lookback"]}), ("lo", {"L": p["lookback"]})]))
register(Template(
    "carry", 1,
    {"name": "synthetic-carry", "mechanism": "SYNTHETIC LABEL: hedgers pay a premium to holders of risk",
     "sign": "+", "density": "dense"},
    {"smooth": ("int", 1, MAX_LOOKBACK), "mode": ("choice", ("ts", "xs")), "quantile": ("float", 0.1, 0.5),
     "rebalance": ("int", 1, 21)},
    lambda p: p["smooth"] + 1, _carry, lambda p: [("carry", {"L": p["smooth"]})]))

PRODUCTION_TEMPLATES = tuple(TEMPLATES)


def validate_params(template: str, params: dict) -> list[str]:
    """Stage 0 static validation of one parameter point. Returns the problems (empty when valid)."""
    t = TEMPLATES.get(template)
    if t is None:
        return [f"unknown template {template!r}"]
    probs = []
    if set(params) != set(t.schema):
        missing = sorted(set(t.schema) - set(params))
        unknown = sorted(set(params) - set(t.schema))
        if missing:
            probs.append(f"missing parameters {missing}")
        if unknown:
            probs.append(f"unknown parameters {unknown}")
        return probs
    for k, (kind, *rng) in t.schema.items():
        v = params[k]
        if kind == "int":
            if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
                if isinstance(v, float) and v.is_integer():
                    pass
                else:
                    probs.append(f"{k}: integer expected, got {v!r}")
                    continue
            if not rng[0] <= v <= rng[1]:
                probs.append(f"{k}: {v} outside [{rng[0]}, {rng[1]}]")
        elif kind == "float":
            if isinstance(v, bool) or not isinstance(v, (int, float, np.floating, np.integer)) or \
                    not math.isfinite(float(v)):
                probs.append(f"{k}: finite number expected, got {v!r}")
                continue
            if not rng[0] <= float(v) <= rng[1]:
                probs.append(f"{k}: {v} outside [{rng[0]}, {rng[1]}]")
        else:
            if v not in rng[0]:
                probs.append(f"{k}: {v!r} not one of {rng[0]}")
    if not probs and t.lookback(normalise(template, params)) > MAX_LOOKBACK:
        probs.append(f"look-back {t.lookback(params)} exceeds the warm-up limit {MAX_LOOKBACK}")
    return probs


def normalise(template: str, params: dict) -> dict:
    """Integers as int, floats as float (so 5.0 and 5 build the same positions as they hash the same)."""
    t = TEMPLATES[template]
    out = {}
    for k, (kind, *_) in t.schema.items():
        v = params[k]
        out[k] = int(v) if kind == "int" else float(v) if kind == "float" else v
    return out


def features_needed(template: str, params: dict, sizing: str) -> list:
    out = list(TEMPLATES[template].feats(normalise(template, params)))
    if sizing == "unit_risk":
        out.append(("unit_risk", {"hl": 60, "ann": ANN_RISK}))
    return out


def size(cache, dom: str, sig: np.ndarray, sizing: str) -> np.ndarray:
    A = sig.shape[1]
    if sizing == "equal":
        return sig / A
    if sizing == "unit_risk":
        return sig * cache.get(dom, "unit_risk", hl=60, ann=ANN_RISK)
    raise ValueError(f"unknown sizing {sizing!r}")


def positions(cache, template: str, dom: str, params: dict, sizing: str) -> np.ndarray:
    t = TEMPLATES[template]
    sig = t.build(cache, dom, normalise(template, params))
    w = size(cache, dom, sig, sizing)
    w += 0.0                                  # -0.0 + 0.0 == +0.0: fingerprints must not depend on the sign of 0
    return w
