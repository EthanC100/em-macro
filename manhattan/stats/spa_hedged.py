"""Hedge-aware SPA test (Protocol v3.1 sections 5.1 and 5.2): the core hedge is re-estimated in every resample.

Why. Protocol v3.0 resampled the **already hedged** returns. The hedge ratios are themselves estimates (a ridge
regression on the 756 periods before each day, section 2.2), so the hedged return of a variant with no edge of
its own still carries a little of the core factor: the ridge shrinks the hedge ratio, and a rolling window lags
an exposure that moves. When the core factor has a positive mean, that residue has a positive mean, and a test
that treats the hedged series as given data rejects too often (pilot scenario D11: 0.077 at the 0.05 level).

What changes. One index sequence is still drawn per resample and applied to every variant, but it is now applied
to the **unhedged** returns and the core factors together, and the hedge is re-estimated on the resampled series
by the live rule (same window ``L_β``, same minimum history, same ridge penalty, ratios from earlier periods
only):

    pseudo-series b    the actual periods before the window (up to L_β of them, in their own order), followed
                       by the window's periods in the resampled order τ_b(1..n)
    β*_{k,b,t−1}       the ridge hedge of section 2.2 computed on the pseudo-series from the L_β pseudo-periods
                       before t
    d*_{k,b,t}         r_{k,τ_b(t)} − β*'_{k,b,t−1} C_{τ_b(t)}                     (hedge cost as section 2.2)
    centre             α̂_k = r̄_k − b̂'_k C̄: the intercept of the least-squares regression of r_k on the core
                       factors over the window. It is the mean of the perfectly hedged return **in the world the
                       resamples are drawn from**, so  mean_t(d*_{k,b,t}) − α̂_k  is what the live rule's hedged
                       mean does around the truth when the truth is known.
    recentring         Z̄*_{k,b} = mean_t(d*_{k,b,t}) − g(α̂_k),   g as in section 5.1 with α̂_k in place of d̄_k

The statistic itself is unchanged: ``T = max(0, max_k √n d̄_k / ω̂_k)`` on the live hedged returns, with ``ω̂``
from the live hedged series. With no core factor (returns that are hedged by construction, as in every
simulated scenario but D11) the procedure is exactly section 5.1 of v3.0: ``spa_test`` then calls
``manhattan.stats.spa.spa_test`` and returns its result unchanged.

How the resampled means are computed. Given the factors and an index sequence, the hedged mean is **linear** in
the unhedged returns, so each resample is a weight vector over the actual periods and all variants' resampled
means are one matrix product. Writing ``p`` for a pseudo-period, ``g_p = A_p⁻¹ C̃_p`` with ``A_p`` the penalised
factor moment matrix of the window before ``p``:

    n · mean_t d*_t = Σ_u r̃_u · [ 1{u in window} − C̃'_u G_u + H_u ],
    G_u = Σ_{p=u+1}^{u+L_β} g_p,     H_u = Σ_{p=u+1}^{u+L_β} g'_p (Σ_{window before p} C̃) / (periods in it)

(sums over window pseudo-periods ``p`` only). ``direct_means`` does the same thing the slow way, by building
each pseudo-series and calling ``manhattan.stats.hedge.hedged``; a test compares the two. A non-zero hedge cost
is not linear (it takes absolute changes of the hedge ratio), so it uses the direct path.
"""
from __future__ import annotations

import math

import numpy as np

from . import blocklen, bootstrap, hedge, spa

CHUNK = 256            # resamples per block of work on the hedge-aware path (memory: CHUNK × periods × ~12 arrays)


def _slice(r: np.ndarray, C: np.ndarray, w0: int, n: int, L: int):
    """The periods that matter: up to ``L`` before the window, then the window. Returns ``(r, C, pre)``."""
    r = np.atleast_2d(np.asarray(r, dtype=float))
    C = np.atleast_2d(np.asarray(C, dtype=float))
    if r.shape[1] != C.shape[1]:
        raise ValueError("returns and factors must cover the same periods")
    if w0 < 0 or w0 + n > r.shape[1]:
        raise ValueError("the window is not inside the data")
    pre = min(w0, L)
    return r[:, w0 - pre : w0 + n], C[:, w0 - pre : w0 + n], pre


def window_alpha_weights(C: np.ndarray) -> np.ndarray:
    """Weights ``a`` with ``a @ r = α̂``: the intercept of the least-squares regression of ``r`` on the factors
    ``C`` (``(K, n)``) over these periods. ``α̂ = r̄ − C̄' S⁻¹ Σ_t (C_t − C̄) r_t``."""
    C = np.atleast_2d(np.asarray(C, dtype=float))
    n = C.shape[1]
    cbar = C.mean(axis=1)
    Cc = C - cbar[:, None]
    S = Cc @ Cc.T
    return np.full(n, 1.0 / n) - np.linalg.solve(S, cbar) @ Cc


def resample_weights(C: np.ndarray, idx: np.ndarray, pre: int, *, L: int = hedge.L_BETA,
                     min_obs: int = hedge.MIN_OBS, kappa: float = hedge.KAPPA) -> np.ndarray:
    """Weights ``W`` (``(B, pre + n)``) with ``W[b] @ r_k`` = the mean over the window of variant ``k``'s hedged
    return in resample ``b``, the hedge being re-estimated on the pseudo-series by the rule of section 2.2.

    ``C`` is ``(K, pre + n)``: the factors over the ``pre`` actual periods before the window and the window.
    ``idx`` is ``(B, n)``: each resample's 0-based positions inside the window. The identity sequence gives the
    live hedged mean.
    """
    C = np.atleast_2d(np.asarray(C, dtype=float))
    K, P = C.shape
    B, n = idx.shape
    if pre + n != P:
        raise ValueError("factors must cover the periods before the window and the window")
    Ct = np.empty((B, K, P))
    Ct[:, :, :pre] = C[None, :, :pre]
    Ct[:, :, pre:] = C[:, pre + idx].transpose(1, 0, 2)
    p = np.arange(P)
    cnt = np.minimum(p, L).astype(float)                      # pseudo-periods in the window before p
    use = (p >= pre) & (cnt >= min_obs)                       # window pseudo-periods with enough history

    def rolling(x):                                           # sum over the L pseudo-periods before each p
        c = np.cumsum(x, axis=-1)
        out = np.empty_like(c)
        out[..., 0] = 0.0
        out[..., 1 : L + 1] = c[..., : min(L, P - 1)]
        if P > L + 1:
            out[..., L + 1 :] = c[..., L : P - 1] - c[..., : P - L - 1]
        return out

    def ahead(x):                                             # sum over p' = u+1 .. min(u+L, P−1)
        c = np.cumsum(x, axis=-1)
        out = c[..., -1:] - c
        if P > L + 1:
            out[..., : P - L - 1] = c[..., L : P - 1] - c[..., : P - L - 1]
        return out

    sc = rolling(Ct)                                          # (B, K, P)
    safe = np.where(cnt > 0, cnt, 1.0)
    if K == 1:
        c0 = Ct[:, 0]
        scc = rolling(c0 * c0)                                # (B, P)
        A = (1.0 + kappa) * scc - sc[:, 0] * sc[:, 0] / safe
        g = np.zeros((B, 1, P))
        g[:, 0, use] = c0[:, use] / A[:, use]
    else:
        scc = rolling(Ct[:, :, None, :] * Ct[:, None, :, :])                             # (B, K, K, P)
        pen = kappa * np.einsum("bkkp->bp", scc) / K
        A = scc - sc[:, :, None, :] * sc[:, None, :, :] / safe + pen[:, None, None, :] * np.eye(K)[None, :, :, None]
        A = np.moveaxis(A, 3, 1)[:, use]                                                 # (B, P_use, K, K)
        g = np.zeros((B, K, P))
        g[:, :, use] = np.moveaxis(np.linalg.solve(A, np.moveaxis(Ct, 2, 1)[:, use][..., None])[..., 0], 1, 2)
    h = np.einsum("bkp,bkp->bp", g, sc) / safe                # g'_p (Σ C̃ before p) / (periods before p)
    w = (ahead(h) - np.einsum("bkp,bkp->bp", Ct, ahead(g)) + (p >= pre)) / n            # weights on pseudo-periods
    W = np.empty((B, P))
    W[:, :pre] = w[:, :pre]
    flat = (np.arange(B)[:, None] * n + idx).ravel()
    W[:, pre:] = np.bincount(flat, weights=w[:, pre:].ravel(), minlength=B * n).reshape(B, n)
    return W


def direct_means(r: np.ndarray, C: np.ndarray, idx: np.ndarray, pre: int, *, cost=0.0, L: int = hedge.L_BETA,
                 min_obs: int = hedge.MIN_OBS, kappa: float = hedge.KAPPA) -> np.ndarray:
    """The same resampled hedged means as ``resample_weights(...) @ r.T``, computed by building each
    pseudo-series and hedging it with ``manhattan.stats.hedge``. Slow; it is the reference, and the path used
    when the hedge has a trading cost. Shape ``(B, m)``."""
    r = np.atleast_2d(np.asarray(r, dtype=float))
    C = np.atleast_2d(np.asarray(C, dtype=float))
    out = np.empty((idx.shape[0], r.shape[0]))
    for b, tau in enumerate(idx):
        order = np.concatenate([np.arange(pre), pre + tau])
        X, _ = hedge.hedged(r[:, order], C[:, order], cost=cost, L=L, min_obs=min_obs, kappa=kappa)
        out[b] = X[:, pre:].mean(axis=1)
    return out


def spa_test(r: np.ndarray, rng: np.random.Generator, *, factors: np.ndarray | None = None,
             window: tuple[int, int] | None = None, cost=0.0, L: float | None = None, holding: int = 1,
             l_min: int = blocklen.L_MIN_DAILY, b_steps=spa.B_STEPS[:2], continue_at=spa.B_CONTINUE_AT,
             L_beta: int = hedge.L_BETA, min_obs: int = hedge.MIN_OBS, kappa: float = hedge.KAPPA) -> spa.SpaResult:
    """SPA test of ``max_k E[d_k] ≤ 0`` with the hedge re-estimated in every resample (Protocol v3.1 section 5.1).

    ``r`` is ``(variants, periods)``. With ``factors=None`` the rows are returns that need no hedge and the
    result is ``manhattan.stats.spa.spa_test(r, rng, ...)`` itself. Otherwise ``r`` holds **unhedged** returns,
    ``factors`` is ``(K, periods)`` and ``window = (first period, number of periods)``; ``r`` and ``factors``
    must also hold the periods before the window that the live hedge used.

    The random stream is consumed exactly as by ``spa.spa_test`` (the same block draws in the same order), so
    with the same generator state the two tests differ only by the re-estimation and the centre.
    """
    if factors is None:
        return spa.spa_test(r, rng, L=L, holding=holding, l_min=l_min, b_steps=b_steps, continue_at=continue_at)
    if window is None:
        raise ValueError("a hedge-aware test needs the window: (first period, number of periods)")
    w0, n = window
    r, C, pre = _slice(r, factors, w0, n, L_beta)
    m = r.shape[0]
    live, _ = hedge.hedged(r, C, cost=cost, L=L_beta, min_obs=min_obs, kappa=kappa)
    d = live[:, pre:]
    if L is None:
        L = blocklen.protocol_block_length(d, holding=holding, l_min=l_min)
    q = 1.0 / L
    dbar = d.mean(axis=1)
    omega = np.sqrt(np.maximum(bootstrap.long_run_var(d, q), 0.0))
    if np.any(omega <= 0):
        raise ValueError("a variant has zero long-run variance on this window")
    rootn = math.sqrt(n)
    tstat = rootn * dbar / omega
    T = max(0.0, float(tstat.max()))
    alpha = r[:, pre:] @ window_alpha_weights(C[:, pre:])               # the resampling world's hedged mean
    talpha = rootn * alpha / omega
    recentred = alpha >= -spa.recentring_threshold(omega, n)
    shift_c = np.where(recentred, 0.0, talpha)                          # √n (α̂_k − g_c(α̂_k)) / ω̂_k
    shift_l = np.minimum(talpha, 0.0)
    linear = not np.any(np.asarray(cost, dtype=float))
    parts: list[np.ndarray] = []
    done = 0

    def means_of(blocks: bootstrap.Blocks) -> np.ndarray:
        idx = bootstrap.indices(blocks)
        if not linear:
            return direct_means(r, C, idx, pre, cost=cost, L=L_beta, min_obs=min_obs, kappa=kappa)
        out = np.empty((idx.shape[0], m))
        for s in range(0, idx.shape[0], CHUNK):
            W = resample_weights(C, idx[s : s + CHUNK], pre, L=L_beta, min_obs=min_obs, kappa=kappa)
            out[s : s + CHUNK] = W @ r.T
        return out

    def extend(to: int) -> None:
        nonlocal done
        while done < to:
            b = min(spa.CHUNK, to - done)
            means = means_of(bootstrap.draw_blocks(rng, n, q, b))
            parts.append((rootn * (means - alpha) / omega).astype(np.float32))
            done += b

    def pvals() -> tuple[float, float, float]:
        base = np.concatenate(parts) if len(parts) > 1 else parts[0]
        out = []
        for shift in (shift_c, shift_l, None):
            s = base if shift is None else base + shift.astype(np.float32)
            out.append(spa.p_value(np.maximum(s.max(axis=1), 0.0), T))
        return tuple(out)

    extend(b_steps[0])
    p_c, p_l, p_u = pvals()
    for nxt, gate in zip(b_steps[1:], continue_at):
        if p_c > gate:
            break
        extend(nxt)
        p_c, p_l, p_u = pvals()
    tstar = np.concatenate(parts) if len(parts) > 1 else parts[0]
    return spa.SpaResult(p_c=p_c, p_l=p_l, p_u=p_u, T=T, B=done, L=float(L), n=n, dbar=dbar, omega=omega,
                         tstat=tstat, recentred=recentred, tstar=tstar)
