"""The core hedge of Protocol v3 section 2.2: ridge hedge ratios from the past only.

    β_{t−1} = argmin_β Σ_{u=t−L}^{t−1} ( r_u − a − β' C_u )² + κ ‖β‖²,     κ = 0.1 · trace(C'C) / K
    X_t     = r_t − β'_{t−1} C_t − Σ_k |β_{k,t−1} − β_{k,t−2}| · cost_k

``L = 756`` periods and at least 252: before 252 periods exist the hedge ratio is zero (a burn-in with no
evidential weight). ``trace(C'C)`` is taken over the same window, uncentred; the intercept ``a`` is not penalised.
"""
from __future__ import annotations

import numpy as np

L_BETA, MIN_OBS, KAPPA = 756, 252, 0.1


def _rolling_sum(x: np.ndarray, L: int) -> np.ndarray:
    """``out[..., t] = Σ x[..., max(0, t−L):t]`` (the sum over the ``L`` periods before ``t``)."""
    c = np.concatenate([np.zeros(x.shape[:-1] + (1,)), np.cumsum(x, axis=-1)], axis=-1)
    t = np.arange(x.shape[-1])
    return c[..., t] - c[..., np.maximum(t - L, 0)]


def rolling_beta(r: np.ndarray, C: np.ndarray, L: int = L_BETA, min_obs: int = MIN_OBS,
                 kappa: float = KAPPA) -> np.ndarray:
    """Hedge ratios ``β[s, k, t]`` of each series ``r[s]`` on factors ``C[k]`` for use **in** period ``t``:
    estimated from periods ``t−L .. t−1`` only. Zero while fewer than ``min_obs`` earlier periods exist."""
    r = np.atleast_2d(np.asarray(r, dtype=float))
    C = np.atleast_2d(np.asarray(C, dtype=float))
    S, n = r.shape
    K = C.shape[0]
    cnt = np.minimum(np.arange(n), L).astype(float)
    safe = np.where(cnt > 0, cnt, 1.0)
    sc = _rolling_sum(C, L)                                             # (K, n)
    sr = _rolling_sum(r, L)                                             # (S, n)
    scc = _rolling_sum(C[:, None, :] * C[None, :, :], L)                # (K, K, n)
    scr = _rolling_sum(C[None, :, :] * r[:, None, :], L)                # (S, K, n)
    cov_cc = scc - sc[:, None, :] * sc[None, :, :] / safe
    cov_cr = scr - sc[None, :, :] * sr[:, None, :] / safe
    pen = kappa * np.einsum("kkt->t", scc) / K
    A = np.moveaxis(cov_cc, 2, 0) + pen[:, None, None] * np.eye(K)      # (n, K, K)
    ok = cnt >= min_obs
    beta = np.zeros((S, K, n))
    if ok.any():
        rhs = np.moveaxis(cov_cr, 2, 0)[ok]                             # (n_ok, S, K)
        sol = np.linalg.solve(A[ok][:, None, :, :], rhs[..., None])[..., 0]
        beta[:, :, ok] = np.moveaxis(sol, 0, 2)
    return beta


def hedged(r: np.ndarray, C: np.ndarray, cost=0.0, **kw) -> tuple[np.ndarray, np.ndarray]:
    """Core-hedged returns ``X`` and the hedge ratios used. ``cost`` is the one-way cost per factor."""
    r = np.atleast_2d(np.asarray(r, dtype=float))
    C = np.atleast_2d(np.asarray(C, dtype=float))
    beta = rolling_beta(r, C, **kw)
    turn = np.abs(np.diff(beta, axis=2, prepend=beta[:, :, :1]))
    cost = np.broadcast_to(np.asarray(cost, dtype=float), (C.shape[0],))
    X = r - np.einsum("skt,kt->st", beta, C) - np.einsum("skt,k->st", turn, cost)
    return X, beta
