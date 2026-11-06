# T25-T26 pre-registration: outcome probabilities (docs/prereg/T25-T26_live_shadows.md §5.4). Synthetic data only.
# Run from the repository root: python results/T25-T26/power_mc.py
import numpy as np
from math import sqrt, erf
rng = np.random.default_rng(20261106)
Phi = np.vectorize(lambda x: 0.5 * (1 + erf(x / sqrt(2))))
SR_PRED = {"T25": 0.4346 * sqrt(11 / 20), "T26": 0.4998 * sqrt(18 / 30)}
SR_V11 = 0.709
C = np.array([[1, 0.08, 0.05], [0.08, 1, 0.20], [0.05, 0.20, 1]])
L = np.linalg.cholesky(C)
vm = 0.10 / sqrt(12)

def maxdd(x):
    idx = np.cumprod(1 + x, axis=1)
    return (idx / np.maximum.accumulate(idx, axis=1) - 1).min(1)

def holm_decay(p, active):
    # p: dict k -> array of one-sided p; active: dict k -> bool array; Holm across active sleeves per path, level 0.05
    keys = list(p)
    n = sum(active[k].astype(int) for k in keys)
    lo = np.where(p[keys[0]] <= p[keys[1]], keys[0], keys[1])
    out = {}
    for k in keys:
        other = keys[1] if k == keys[0] else keys[0]
        both = active[k] & active[other]
        is_lo = (p[k] <= p[other])
        p_lo = np.minimum(p[k], p[other])
        adj_lo = np.minimum(1, 2 * p_lo)
        adj = np.where(both, np.where(is_lo, adj_lo, np.maximum(adj_lo, p[k])), p[k])
        out[k] = active[k] & (adj < 0.05)
    return out

def evaluate(r, T, active):
    v = r[:, :T, 0]
    res = {}
    p, conf = {}, {}
    for j, k in ((1, "T25"), (2, "T26")):
        s = r[:, :T, j]
        m, sd = s.mean(1), s.std(1, ddof=1)
        m0 = SR_PRED[k] / sqrt(12) * sd
        t = (m - m0) / (sd / sqrt(T))
        p[k] = Phi(t)
        mix = 0.75 * v + 0.25 * s
        mix = mix * (v.std(1, ddof=1) / mix.std(1, ddof=1))[:, None]
        dsr = (mix.mean(1) / mix.std(1, ddof=1) - v.mean(1) / v.std(1, ddof=1)) * sqrt(12)
        conf[k] = (m > 0) & (dsr >= -0.05) & (np.abs(maxdd(mix)) <= 1.10 * np.abs(maxdd(v)))
    dec = holm_decay(p, active)
    for k in ("T25", "T26"):
        res[k] = (dec[k], active[k] & ~dec[k] & conf[k], active[k] & ~dec[k] & ~conf[k])
    return res

def run(scale, n=8000, T1=60, T2=96):
    mu = np.array([SR_V11, scale * SR_PRED["T25"], scale * SR_PRED["T26"]]) / sqrt(12) * vm
    r = mu + vm * (rng.standard_normal((n, T2, 3)) @ L.T)
    act = {k: np.ones(n, bool) for k in ("T25", "T26")}
    first = evaluate(r, T1, act)
    act2 = {k: first[k][2] for k in first}
    second = evaluate(r, T2, act2)
    out = {}
    for k in ("T25", "T26"):
        d1, c1, i1 = first[k]
        d2, c2, i2 = second[k]
        out[k] = {"at 5y: decayed": d1.mean(), "at 5y: confirmed": c1.mean(), "at 5y: inconclusive": i1.mean(),
                  "final: decayed": (d1 | d2 | i2).mean(), "final: confirmed": (c1 | c2).mean(),
                  "of which at 8y": c2.mean(), "inconclusive->decayed at 8y": i2.mean()}
    return out

for name, sc in (("real (breadth-adjusted backtest)", 1.0), ("half", 0.5), ("zero", 0.0)):
    o = run(sc)
    print(name)
    for k, v in o.items():
        print(" ", k, {kk: round(float(vv), 3) for kk, vv in v.items()})
print(SR_PRED)
