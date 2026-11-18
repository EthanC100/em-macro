"""Stage 1-3 kernels and their plain reference implementations.

Alignment (``align``): with warm-up ``W`` and fence ``F``, the evaluation has ``n = F - W`` periods. Position row
``W - 1 + i`` (set at the close of day ``W - 1 + i`` from data through that close) earns the return of day
``W + i``; it is traded at that close, from the previous row (zero before the window). Costs of a trade are charged
to the period the position earns. No row at or past the fence is read.

**Stage 1** (``screen``; outcome-sign-blind): degenerate (no position in the window), the behavioural fingerprint
(SHA-256 of the windowed positions and the domain and cost binding) and the exact Hölder bound

    gross mean = (1/n) Σ_t Σ_a P[t,a] R[t,a]  <=  H = (1/n) Σ_t Σ_a |P[t,a]| |R[t,a]|

so the stage-2 net mean (gross minus the linear cost ``C``) is at most ``H - C``. ``dominated`` is
``H (1 + 1e-9) < C``; the relative margin is far above the floating-point error of either sum (``n·A·u`` with
``u = 2^-53``: about ``4e-12`` for the largest workloads here), so a dominated candidate's computed stage-2 net mean
is non-positive (property-tested). The bound reads ``|R|`` only: changing the sign of any evaluated return cannot
change a stage-1 decision.

**Stage 2** (also ``screen``): gross and net (linear-cost) mean, net standard deviation, t-statistic, annualised
Sharpe ratio, turnover, gross exposure, active fraction and hit rate. Screening statistics, never evidence.

**Stage 3** (``stage3_series``, ``stage3_stats``, ``stage3_boot``): strategy-level volatility targeting on a lagged
EWMA of the candidate's own unscaled returns (updated on active days only; leverage-capped), linear plus
``|trade|^1.5`` impact costs, the net series' SHA-256, summary statistics, a one-sided stationary-bootstrap p-value
for a positive mean (recentred; descriptive), and the per-family *partial maxima* of Hansen's SPA statistics.

**Streaming SPA.** With one bootstrap index set for every candidate (``boot_counts``: the same draws for all
variants, as the Protocol's joint bootstrap requires), the SPA statistics of a family are maxima over its variants of
per-variant quantities. Maxima combine exactly (floating-point ``max`` is associative and commutative), so partial
maxima from any chunking give bit-identical family statistics. A variant whose series is identically zero
contributes exactly 0 to ``T`` and to every ``T*_b``, which the ``max(0, ·)`` floor already gives, so excluding
degenerate variants is exact. ``spa_test`` in ``manhattan.stats.spa`` is the reference (tested).

Reproducibility: every per-candidate number except the bootstrap means is computed with elementwise operations and
reductions along a candidate's own rows, so it does not depend on which other candidates share a batch. Bootstrap
means use one matrix product per fixed, aligned group of 64 selected candidates (``stage3_boot``). Results are
bit-for-bit identical across batch sizes and worker counts on one platform (tested).
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from manhattan.stats import bootstrap

# per-unit-notional costs per domain: (linear spread, impact coefficient on |trade|^1.5); synthetic, uncalibrated
COSTS = {"commodity": (4e-4, 2e-3), "rates": (1e-4, 5e-4), "fx": (1.5e-4, 8e-4)}
DOMINANCE_MARGIN = 1e-9

# per-candidate stage 2 statistic columns
S2_COLS = ("gross_mean", "net_mean", "net_std", "t_stat", "sharpe_ann", "turnover", "exposure", "active_frac",
           "hit_rate", "holder_bound", "lin_cost")
# per-candidate stage 3 statistic columns
S3_COLS = ("mean", "std", "t_stat", "sharpe_ann", "max_drawdown", "turnover", "avg_scale", "p_boot", "omega",
           "spa_t")


def align(P: np.ndarray, R: np.ndarray, warmup: int, fence: int) -> tuple[np.ndarray, np.ndarray]:
    if P.shape[0] < fence or R.shape[0] < fence:
        raise ValueError("arrays shorter than the fence")
    return P[warmup - 1: fence - 1], R[warmup:fence]


def cost_coefficients(domain: str, multiplier: float) -> tuple[float, float]:
    c, k = COSTS[domain]
    return c * multiplier, k * multiplier


def _trades(P: np.ndarray) -> np.ndarray:
    d = np.empty_like(P)
    d[0] = P[0]
    d[1:] = P[1:] - P[:-1]
    return d


def fingerprint(Pw: np.ndarray, domain: str, cost_model: str) -> bytes:
    h = hashlib.sha256(np.ascontiguousarray(Pw).tobytes())
    h.update(b"\0" + domain.encode() + b"\0" + cost_model.encode())
    return h.digest()


def screen(Pw: np.ndarray, Rw: np.ndarray, c: float, *, stage2: bool = True, absR: np.ndarray | None = None) -> dict:
    """Stages 1 and 2 for one candidate's windowed positions ``Pw`` and returns ``Rw`` (both ``(n, A)``).
    ``absR`` may pass a precomputed ``|Rw|`` (shared by every candidate of a domain)."""
    n = Pw.shape[0]
    degenerate = not Pw.any()
    absP = np.abs(Pw)
    H = float((absP * (np.abs(Rw) if absR is None else absR)).sum()) / n
    turn = np.abs(_trades(Pw))
    lin_cost_t = c * turn.sum(axis=1)
    C = float(lin_cost_t.sum()) / n
    out = {"degenerate": degenerate, "dominated": (not degenerate) and H * (1.0 + DOMINANCE_MARGIN) < C,
           "holder_bound": H, "lin_cost": C}
    if not stage2:
        return out
    gross_t = (Pw * Rw).sum(axis=1)
    net_t = gross_t - lin_cost_t
    gm = float(gross_t.mean())
    nm = float(net_t.mean())
    sd = float(net_t.std(ddof=1)) if n > 1 else 0.0
    active = absP.sum(axis=1) > 0
    na = int(active.sum())
    out.update({
        "gross_mean": gm, "net_mean": nm, "net_std": sd,
        "t_stat": nm / sd * math.sqrt(n) if sd > 0 else 0.0,
        "sharpe_ann": nm / sd * math.sqrt(252.0) if sd > 0 else 0.0,
        "turnover": float(turn.sum()) / n, "exposure": float(absP.sum(axis=1).mean()),
        "active_frac": na / n, "hit_rate": float((net_t[active] > 0).sum()) / na if na else 0.0,
    })
    return out


def boot_counts(n: int, B: int, L: int, seed: int) -> np.ndarray:
    """``(B, n)`` stationary-bootstrap day counts, shared by every candidate of a run (joint bootstrap)."""
    rng = np.random.default_rng(seed)
    return bootstrap.counts(bootstrap.draw_blocks(rng, n, 1.0 / L, B))


def _scales(g: np.ndarray, active: np.ndarray, hl: int, min_obs: int, target: float, cap: float) -> np.ndarray:
    """Vol-target scale per period, vectorised over rows. s[:, t] uses g[:, :t] only.

    The EWMA state (``ev``, ``wv``, ``nobs``) does not depend on the scale, so the only sequential loop carries the
    state, time-major, with masked coefficients precomputed (an inactive day multiplies by exactly 1 and adds
    exactly 0, so it leaves the state bit-for-bit unchanged); the scales are then one vectorised expression over the
    state history. ``ref_stage3_series`` performs the same floating-point operations in the same order."""
    m, n = g.shape
    lam = 0.5 ** (1.0 / hl)
    gt = np.ascontiguousarray(g.T)
    at = np.ascontiguousarray(active.T)
    mul = np.where(at, lam, 1.0)
    add_ev = np.where(at, (1.0 - lam) * (gt * gt), 0.0)
    add_wv = np.where(at, 1.0 - lam, 0.0)
    ev_hist = np.empty((n, m))
    wv_hist = np.empty((n, m))
    ev = np.zeros(m)
    wv = np.zeros(m)
    for t in range(n):
        ev_hist[t] = ev                       # state before period t's own return
        wv_hist[t] = wv
        ev *= mul[t]
        ev += add_ev[t]
        wv *= mul[t]
        wv += add_wv[t]
    nobs = np.cumsum(at, axis=0) - at        # active days strictly before t
    with np.errstate(invalid="ignore", divide="ignore"):
        sd = np.sqrt(ev_hist / wv_hist)
        s = np.where((nobs >= min_obs) & (sd > 0), np.minimum(cap, target / sd), 1.0)
    return np.ascontiguousarray(s.T)


BOOT_GROUP = 64       # bootstrap means are computed for aligned groups of 64 selected candidates (see stage3_boot)


def stage3_series(Ps: list, Rs: list, cs: list, ks: list, policy) -> dict:
    """Stage 3 net series for ``m`` candidates. ``Ps[i]`` and ``Rs[i]`` are the candidate's windowed ``(n, A)``
    positions and returns, ``cs[i]``/``ks[i]`` its linear and impact cost coefficients (scalars per domain).

    Per-candidate work is done one candidate at a time on cache-resident arrays; only the vol-target recursion is
    batched across candidates (``_scales``: elementwise, so a row's result does not depend on the other rows)."""
    m = len(Ps)
    n = Ps[0].shape[0]
    g = np.empty((m, n))
    active = np.empty((m, n), bool)
    for i in range(m):
        g[i] = (Ps[i] * Rs[i]).sum(axis=1)
        active[i] = (Ps[i] != 0.0).any(axis=1)
    target = policy.vol_target_ann / math.sqrt(252.0)
    s = _scales(g, active, policy.vol_halflife, policy.vol_min_obs, target, policy.leverage_cap)
    net = np.empty((m, n))
    turnover = np.empty(m)
    for i in range(m):
        W = s[i][:, None] * Ps[i]
        dW = np.empty_like(W)
        dW[0] = W[0]
        np.subtract(W[1:], W[:-1], out=dW[1:])
        adW = np.abs(dW, out=dW)
        lin = adW.sum(axis=1)
        imp = (adW * np.sqrt(adW)).sum(axis=1)
        net[i] = s[i] * g[i] - (cs[i] * lin + ks[i] * imp)
        turnover[i] = lin.sum() / n
    return {"net": net, "scale": s, "turnover": turnover}


def stage3_stats(net: np.ndarray, scale: np.ndarray, turnover: np.ndarray, policy) -> np.ndarray:
    """Per-candidate statistics except the bootstrap columns (filled by ``stage3_boot``)."""
    m, n = net.shape
    mean = net.mean(axis=1)
    std = net.std(axis=1, ddof=1)
    cum = np.cumsum(net, axis=1)
    peak = np.maximum.accumulate(np.maximum(cum, 0.0), axis=1)
    maxdd = (peak - cum).max(axis=1)
    q = 1.0 / policy.bootstrap_L
    # one row at a time: long_run_var ends in a matrix-vector product whose per-row bits depend on the number of
    # rows (measured), and a candidate's statistics must not depend on its batch
    lrv = np.array([bootstrap.long_run_var(net[i:i + 1], q)[0] for i in range(m)])
    with np.errstate(invalid="ignore", divide="ignore"):
        omega = np.sqrt(np.maximum(lrv, 0.0))
        rootn = math.sqrt(n)
        out = np.zeros((m, len(S3_COLS)))
        out[:, 0] = mean
        out[:, 1] = std
        out[:, 2] = np.where(std > 0, mean / std * rootn, 0.0)
        out[:, 3] = np.where(std > 0, mean / std * math.sqrt(252.0), 0.0)
        out[:, 4] = maxdd
        out[:, 5] = turnover
        out[:, 6] = scale.mean(axis=1)
        out[:, 7] = np.nan                                   # p_boot: stage3_boot
        out[:, 8] = omega
        out[:, 9] = np.where(omega > 0, rootn * mean / omega, 0.0)
    return out


def stage3_boot(C: np.ndarray, net: np.ndarray, mean: np.ndarray, omega: np.ndarray) -> tuple:
    """Bootstrap for one aligned group of at most ``BOOT_GROUP`` candidates: resampled means by one matrix
    product (BLAS-3; about 8x faster than one matrix-vector product per candidate, which is memory-bound on ``C``).

    A matrix product's per-column bits can depend on the other columns (measured: they do). Groups are therefore
    fixed by position in the selected list (positions ``[64j, 64j + 64)``), never by chunk or worker, so the same
    group is always the same product: results are bit-identical for any chunk size and worker count on one
    platform (tested). Across BLAS builds or CPUs, results agree to rounding (not bit-for-bit), as for any BLAS.

    Returns the one-sided bootstrap p-value of a positive mean (recentred) and the SPA ``z`` rows."""
    n = net.shape[1]
    mb = (C @ net.T).T / n                                   # (g, B)
    B = C.shape[0]
    p = (1.0 + np.count_nonzero(mb - mean[:, None] >= mean[:, None], axis=1)) / (B + 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(omega[:, None] > 0, math.sqrt(n) * (mb - mean[:, None]) / omega[:, None], 0.0)
    return p, z


def spa_shifts(mean: np.ndarray, omega: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Hansen's consistent and lower shifts per variant (as ``manhattan.stats.spa``)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(omega > 0, math.sqrt(n) * mean / omega, 0.0)
    thr = omega * math.sqrt(2.0 * math.log(math.log(n)) / n)
    recentred = mean >= -thr
    return np.where(recentred, 0.0, t), np.minimum(t, 0.0)


def spa_partial(z: np.ndarray, mean: np.ndarray, omega: np.ndarray, n: int, groups: np.ndarray) -> dict:
    """Per-group partial maxima. Rows with ``omega == 0`` (identically zero series) are excluded (exact; see the
    module docstring). Returns ``{group: (T_partial, max_c (B,), max_l (B,), max_u (B,), count)}``."""
    shift_c, shift_l = spa_shifts(mean, omega, n)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(omega > 0, math.sqrt(n) * mean / omega, 0.0)
    out = {}
    for gval in np.unique(groups):
        sel = (groups == gval) & (omega > 0)
        if not sel.any():
            continue
        zs = z[sel]
        out[int(gval)] = (float(t[sel].max()), (zs + shift_c[sel, None]).max(axis=0),
                          (zs + shift_l[sel, None]).max(axis=0), zs.max(axis=0), int(sel.sum()))
    return out


def spa_combine(parts: list) -> dict:
    """Combine partial maxima (any order, any chunking) and return Hansen's three p-values."""
    T = max(p[0] for p in parts)
    mc = np.maximum.reduce([p[1] for p in parts])
    ml = np.maximum.reduce([p[2] for p in parts])
    mu = np.maximum.reduce([p[3] for p in parts])
    T = max(0.0, T)
    B = mc.size

    def pv(x):
        return float((1.0 + np.count_nonzero(np.maximum(x, 0.0) >= T)) / (B + 1.0))

    return {"T": T, "p_c": pv(mc), "p_l": pv(ml), "p_u": pv(mu), "B": int(B),
            "variants": int(sum(p[4] for p in parts))}


# -- reference implementations (plain loops; used only by tests) --------------------------------------------

def ref_screen(Pw, Rw, c) -> dict:
    n, A = Pw.shape
    H = C = 0.0
    gross = [0.0] * n
    net = [0.0] * n
    prev = [0.0] * A
    turn_total = expo = 0.0
    active = [False] * n
    for t in range(n):
        g = tsum = e = 0.0
        for a in range(A):
            p = float(Pw[t, a])
            r = float(Rw[t, a])
            H += abs(p) * abs(r)
            tr = abs(p - prev[a])
            tsum += tr
            turn_total += tr
            g += p * r
            e += abs(p)
            prev[a] = p
        lc = c * tsum
        gross[t] = g
        net[t] = g - lc
        C += lc
        expo += e
        active[t] = e > 0
    H /= n
    C /= n
    nm = sum(net) / n
    sd = math.sqrt(sum((x - nm) ** 2 for x in net) / (n - 1))
    na = sum(active)
    degenerate = not any(Pw.ravel())
    return {"degenerate": degenerate, "dominated": (not degenerate) and H * (1 + DOMINANCE_MARGIN) < C,
            "holder_bound": H, "lin_cost": C, "gross_mean": sum(gross) / n, "net_mean": nm, "net_std": sd,
            "t_stat": nm / sd * math.sqrt(n) if sd > 0 else 0.0,
            "sharpe_ann": nm / sd * math.sqrt(252.0) if sd > 0 else 0.0,
            "turnover": turn_total / n, "exposure": expo / n, "active_frac": na / n,
            "hit_rate": sum(1 for t in range(n) if active[t] and net[t] > 0) / na if na else 0.0}


def ref_stage3_series(P, Rw, c, k, policy) -> np.ndarray:
    """One candidate's stage 3 net series by explicit loops."""
    n, A = P.shape
    lam = 0.5 ** (1.0 / policy.vol_halflife)
    target = policy.vol_target_ann / math.sqrt(252.0)
    ev = wv = 0.0
    nobs = 0
    prevW = [0.0] * A
    out = np.zeros(n)
    for t in range(n):
        sd = math.sqrt(ev / wv) if wv > 0 else 0.0
        s = min(policy.leverage_cap, target / sd) if (nobs >= policy.vol_min_obs and sd > 0) else 1.0
        g = 0.0
        lin = imp = 0.0
        act = False
        for a in range(A):
            p = float(P[t, a])
            g += p * float(Rw[t, a])
            w = s * p
            d = abs(w - prevW[a])
            lin += d
            imp += d * math.sqrt(d)
            prevW[a] = w
            act = act or p != 0.0
        out[t] = s * g - (c * lin + k * imp)
        if act:
            ev = ev * lam + (1 - lam) * (g * g)
            wv = wv * lam + (1 - lam)
            nobs += 1
    return out
