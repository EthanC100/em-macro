"""Programme-scale synthetic worlds for the across-family layer (S13 methodology, priority 6).

A **class** is one scientific claim (one family with one sign). A **unit** is one registered family that the
screening procedure is shown: a class appears as one unit, or as several when the generator duplicates it. Every
unit has ``m`` variants observed over ``W`` weekly test periods of a reserve window. In standardised weekly units
(variance 1), variant ``k`` of unit ``u`` is

    x_{u,k,w} = μ_{u,k} + √a c_{s,w} + √b g_{u,w} + √(1−a−b) e_{u,k,w}

    c_{s,w}    common to every unit on window slice s: one slice for the whole programme ("shared", the default of
               ARCHITECTURE §6.2) or one per batch ("disjoint", reserve.mode: disjoint_slices)
    g_{u,w}    the unit's family factor, common to its variants
    e          idiosyncratic;  μ_{u,k} = θ_{u,k} / √52 with θ the annualised Sharpe ratio of the variant

So variants of one unit are equicorrelated with ``ρ_in = a + b`` and units on one slice share ``a``. A unit's two
statistics are those the two screening candidates take:

    p   the oracle SPA p-value of max_k √W x̄_{u,k} (``maxnull.family_p``; exact here, bootstrap in production)
    E   the betting e-value of Protocol §4.5 on the unit's equal-weight portfolio, standardised by its true scale,
        truncated at −c, with the Protocol's grid Λ (``manhattan.stats.eprocess.lambdas``), read at the window end

Only sufficient statistics are drawn for variants (their sums); the portfolio's weekly path is drawn conditionally
on those sums, so ``p`` and ``E`` are jointly exact. Effects follow ``manhattan.sim.world``'s development
defaults (θ in {0.5, 1.0, 1.5} with probabilities 0.5/0.3/0.2, variant share uniform on (0.5, 1)).

Duplication. A duplicated class gets ``dup_k − 1`` extra units: **exact** copies (same data, so the same
statistics), **near** copies (data correlated ``dup_rho`` with the original's family and idiosyncratic parts,
same window), or, under disjoint slices with a copy placed in a later batch, a **fresh** evaluation of the same
claim on that batch's slice. Mirroring adds, for a null class, a distinct class that bets the opposite sign on the
same data (negatively dependent statistics). Duplication and mirroring never depend on any outcome.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from manhattan.stats import eprocess

from . import maxnull

WEEKS_PER_YEAR = 52
ORIG, EXACT, NEAR, MIRROR, FRESH = 0, 1, 2, 3, 4
DEV_THETA = ((0.5, 0.5), (1.0, 0.3), (1.5, 0.2))


@dataclass(frozen=True)
class Programme:
    B: int = 100                    # batches
    n_b: int = 15                   # classes per batch before duplication
    m: int = 6                      # variants per unit
    weeks: int = 350                # reserve window: 1,750 trading days, as in SIM_PREREG
    a: float = 0.05                 # share common to every unit on a slice
    b: float = 0.45                 # share common to a unit's variants
    pi1: float = 0.0                # share of classes with an edge
    theta: tuple = DEV_THETA
    q_lo: float = 0.5
    sparse: bool = False            # True: only variant 0 of a class with an edge carries it
    window: str = "shared"          # or "disjoint"
    dup_k: int = 1                  # units per duplicated class
    dup_rho: float = 1.0            # 1: exact copies
    dup_where: str = "same"         # "same" batch or "later" (uniform on this and later batches)
    dup_target: str = "all"         # which classes are duplicated: "all", "null" or "true"
    mirror: float = 0.0             # share of null classes that get an opposite-sign twin class
    c: float = eprocess.C_WEEKLY

    def __post_init__(self):
        if self.window not in ("shared", "disjoint") or self.dup_where not in ("same", "later") \
                or self.dup_target not in ("all", "null", "true"):
            raise ValueError("unknown option")
        if not (0 <= self.a and 0 <= self.b and self.a + self.b < 1):
            raise ValueError("a + b must be in [0, 1)")
        if self.dup_rho < 1.0 and self.dup_where != "same":
            raise ValueError("near copies are placed in their class's batch")

    @property
    def rho_in(self) -> float:
        return self.a + self.b

    @property
    def portfolio_sd(self) -> float:
        return math.sqrt(self.a + self.b + (1.0 - self.a - self.b) / self.m)


@dataclass
class Draw:
    """One replication. Unit arrays are in batch order; class arrays are indexed by class id."""
    unit_class: np.ndarray
    unit_batch: np.ndarray
    unit_kind: np.ndarray
    p: np.ndarray
    E: np.ndarray
    zmax: np.ndarray
    class_true: np.ndarray
    class_theta: np.ndarray
    portfolio_sharpe: np.ndarray    # true annualised Sharpe ratio of each unit's portfolio


def _thetas(rng, prog: Programme, n: int) -> np.ndarray:
    vals = np.array([t for t, _ in prog.theta])
    probs = np.array([q for _, q in prog.theta])
    return vals[rng.choice(len(vals), size=n, p=probs / probs.sum())]


def _layout(rng, prog: Programme):
    C = prog.B * prog.n_b
    cls_batch = np.repeat(np.arange(prog.B), prog.n_b)
    true = rng.random(C) < prog.pi1
    theta = np.where(true, _thetas(rng, prog, C), 0.0)
    eff = np.zeros((C, prog.m))
    if prog.sparse:
        eff[:, 0] = theta
    else:
        eff = theta[:, None] * rng.uniform(prog.q_lo, 1.0, size=(C, prog.m))
    eff[~true] = 0.0
    units = []                                       # (class, batch, kind, source unit index or -1)
    first = np.empty(C, dtype=np.int64)
    for c in range(C):
        b = int(cls_batch[c])
        src = first[c] = len(units)
        units.append((c, b, ORIG, -1))
        dup = prog.dup_k > 1 and (prog.dup_target == "all" or (prog.dup_target == "true") == bool(true[c]))
        for _ in range(prog.dup_k - 1 if dup else 0):
            bb = b if prog.dup_where == "same" else int(rng.integers(b, prog.B))
            if prog.window == "disjoint" and bb != b:
                kind = FRESH
            else:
                kind = EXACT if prog.dup_rho >= 1.0 else NEAR
            units.append((c, bb, kind, src))
    extra_true, extra_eff = [], []
    if prog.mirror > 0:
        for c in np.flatnonzero(~true):
            if rng.random() < prog.mirror:
                cid = C + len(extra_true)
                units.append((cid, int(cls_batch[c]), MIRROR, int(first[c])))
                extra_true.append(False)
                extra_eff.append(np.zeros(prog.m))
    true = np.concatenate([true, np.array(extra_true, dtype=bool)])
    theta = np.concatenate([theta, np.zeros(len(extra_true))])
    if extra_eff:
        eff = np.vstack([eff, np.array(extra_eff)])
    u = np.array(units, dtype=np.int64)
    order = np.lexsort((np.arange(len(u)), u[:, 1]))          # batch order, stable
    remap = np.empty(len(u), dtype=np.int64)
    remap[order] = np.arange(len(u))
    u = u[order]
    u[:, 3] = np.where(u[:, 3] >= 0, remap[np.maximum(u[:, 3], 0)], -1)
    return u, true, theta, eff


def _evalue(P: np.ndarray, sd: float, c: float) -> np.ndarray:
    Y = np.maximum(P / sd, -c)
    lam = eprocess.lambdas(c)
    logw = np.stack([np.log1p(l * Y).sum(axis=1) for l in lam], axis=1)
    return np.exp(logw).mean(axis=1)


def draw(prog: Programme, rng: np.random.Generator) -> Draw:
    u, true, theta, eff = _layout(rng, prog)
    W, m = prog.weeks, prog.m
    sa, sb, se = math.sqrt(prog.a), math.sqrt(prog.b), math.sqrt(1.0 - prog.a - prog.b)
    rootW = math.sqrt(W)
    n = len(u)
    p, E, zmax = np.empty(n), np.empty(n), np.empty(n)
    shared = rng.standard_normal(W) if prog.window == "shared" else None
    for b in range(prog.B):
        idx = np.flatnonzero(u[:, 1] == b)
        if idx.size == 0:
            continue
        cpath = shared if shared is not None else rng.standard_normal(W)
        csum = cpath.sum() / rootW
        k = idx.size
        G = rng.standard_normal((k, W))
        Ev = rng.standard_normal((k, m))
        V = rng.standard_normal((k, W)) / math.sqrt(m)
        kind = u[idx, 2]
        local = {int(g): i for i, g in enumerate(idx)}
        src_local = np.array([local.get(int(s), -1) for s in u[idx, 3]])
        near = kind == NEAR
        if near.any():
            r = prog.dup_rho
            s = src_local[near]
            G[near] = math.sqrt(r) * G[s] + math.sqrt(1 - r) * G[near]
            Ev[near] = math.sqrt(r) * Ev[s] + math.sqrt(1 - r) * Ev[near]
            V[near] = math.sqrt(r) * V[s] + math.sqrt(1 - r) * V[near]
        mu = eff[u[idx, 0]] / math.sqrt(WEEKS_PER_YEAR)
        z = rootW * mu + sa * csum + sb * (G.sum(axis=1, keepdims=True) / rootW) + se * Ev
        Uid = V - V.mean(axis=1, keepdims=True) + (rootW * Ev.mean(axis=1, keepdims=True)) / W
        P = mu.mean(axis=1, keepdims=True) + sa * cpath[None, :] + sb * G + se * Uid
        mir = kind == MIRROR
        if mir.any():
            z[mir] = -z[src_local[mir]]
            P[mir] = -P[src_local[mir]]
        zm = z.max(axis=1)
        pv = maxnull.family_p(zm, m, prog.rho_in)
        ev = _evalue(P, prog.portfolio_sd, prog.c)
        ex = kind == EXACT
        if ex.any():
            same = src_local[ex] >= 0
            tgt = np.flatnonzero(ex)
            loc = tgt[same]
            pv[loc], ev[loc], zm[loc] = pv[src_local[loc]], ev[src_local[loc]], zm[src_local[loc]]
            far = idx[tgt[~same]]                      # copies of a unit in an earlier batch (shared window)
            pv_far, ev_far, zm_far = p[u[far, 3]], E[u[far, 3]], zmax[u[far, 3]]
            pv[tgt[~same]], ev[tgt[~same]], zm[tgt[~same]] = pv_far, ev_far, zm_far
        p[idx], E[idx], zmax[idx] = pv, ev, zm
    port_sharpe = eff[u[:, 0]].mean(axis=1) / prog.portfolio_sd
    port_sharpe = np.where(u[:, 2] == MIRROR, -port_sharpe, port_sharpe)
    return Draw(unit_class=u[:, 0], unit_batch=u[:, 1], unit_kind=u[:, 2], p=p, E=E, zmax=zmax,
                class_true=true, class_theta=theta, portfolio_sharpe=port_sharpe)
