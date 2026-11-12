"""Hansen's SPA test against zero and the Romano-Wolf step-down (Protocol v3 sections 5.1, 5.2, 5.4).

Hansen (2005), JBES 23(4): the estimator ``μ̂ᶜ`` on p. 368; the bootstrap implementation, the three ``g``
functions, ``ω̂²`` and ``κ(n, i)`` on p. 371-372. Romano and Wolf (2005), Econometrica 73.

    T          = max( 0, max_k √n d̄_k / ω̂_k )
    Z*_{k,b,t} = d*_{k,b,t} − g(d̄_k)
                 lower:       g_l(x) = max(0, x)
                 consistent:  g_c(x) = x · 1{ x ≥ −ω̂_k √(2 ln ln n / n) }
                 upper:       g_u(x) = x
    T*_b       = max( 0, max_k √n mean_t(Z*_{k,b,t}) / ω̂_k )
    p          = ( 1 + #{b : T*_b ≥ T} ) / ( B + 1 )

The p-value's finite-``B`` form is Protocol v3's (Hansen writes ``#{T*_b > T} / B``); it is never smaller.
``B`` starts at 999 and continues on the same random stream to 9,999 when ``p_c ≤ 0.10`` (and, outside the
simulation's declared cap, to 99,999 when ``p_c ≤ 0.01``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import blocklen, bootstrap

B_STEPS = (999, 9_999, 99_999)
B_CONTINUE_AT = (0.10, 0.01)
CHUNK = 3_000


@dataclass
class SpaResult:
    p_c: float
    p_l: float
    p_u: float
    T: float
    B: int
    L: float
    n: int
    dbar: np.ndarray
    omega: np.ndarray
    tstat: np.ndarray                     # √n d̄_k / ω̂_k
    recentred: np.ndarray                 # True where the consistent test centres the variant at zero
    tstar: np.ndarray = field(repr=False, default=None)   # √n (mean*_{k,b} − d̄_k) / ω̂_k, shape (B, m)


def recentring_threshold(omega: np.ndarray, n: int) -> np.ndarray:
    """``ω̂_k √(2 ln ln n / n)``: a variant with ``d̄_k`` below minus this is left at its own (negative) mean."""
    return omega * math.sqrt(2.0 * math.log(math.log(n)) / n)


def p_value(t_star: np.ndarray, t: float) -> float:
    return (1.0 + np.count_nonzero(t_star >= t)) / (t_star.size + 1.0)


def spa_test(d: np.ndarray, rng: np.random.Generator, *, L: float | None = None, holding: int = 1,
             l_min: int = blocklen.L_MIN_DAILY, b_steps=B_STEPS[:2], continue_at=B_CONTINUE_AT) -> SpaResult:
    """SPA test of ``max_k E[d_k] ≤ 0`` on the rows of ``d`` (variants by periods).

    ``b_steps[:2]`` is the simulation's declared cap of 9,999 resamples (SIM_PREREG section 2.5(a)); production
    passes ``B_STEPS``. The resampled statistics are kept in ``tstar`` for the Romano-Wolf step-down.
    """
    d = np.atleast_2d(np.asarray(d, dtype=float))
    m, n = d.shape
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
    recentred = dbar >= -recentring_threshold(omega, n)
    shift_c = np.where(recentred, 0.0, tstat)        # √n (d̄_k − g_c(d̄_k)) / ω̂_k
    shift_l = np.minimum(tstat, 0.0)                 # √n (d̄_k − g_l(d̄_k)) / ω̂_k
    parts: list[np.ndarray] = []
    done = 0

    def extend(to: int) -> None:
        nonlocal done
        while done < to:
            b = min(CHUNK, to - done)
            means = bootstrap.block_means(d, bootstrap.draw_blocks(rng, n, q, b))
            parts.append((rootn * (means - dbar) / omega).astype(np.float32))
            done += b

    def pvals() -> tuple[float, float, float]:
        base = np.concatenate(parts) if len(parts) > 1 else parts[0]
        out = []
        for shift in (shift_c, shift_l, None):
            s = base if shift is None else base + shift.astype(np.float32)
            out.append(p_value(np.maximum(s.max(axis=1), 0.0), T))
        return tuple(out)

    extend(b_steps[0])
    p_c, p_l, p_u = pvals()
    for nxt, gate in zip(b_steps[1:], continue_at):
        if p_c > gate:
            break
        extend(nxt)
        p_c, p_l, p_u = pvals()
    tstar = np.concatenate(parts) if len(parts) > 1 else parts[0]
    return SpaResult(p_c=p_c, p_l=p_l, p_u=p_u, T=T, B=done, L=float(L), n=n, dbar=dbar, omega=omega,
                     tstat=tstat, recentred=recentred, tstar=tstar)


def rw_critical(max_star: np.ndarray, a: float) -> float:
    """The ``⌈(1 − a)(B + 1)⌉``-th smallest of the resampled maxima; infinite when ``B`` is too small for ``a``."""
    B = max_star.size
    rank = math.ceil((1.0 - a) * (B + 1) - 1e-9)
    if rank > B:
        return math.inf
    return float(np.partition(max_star, rank - 1)[rank - 1])


def romano_wolf(tstat: np.ndarray, tstar: np.ndarray, a: float) -> np.ndarray:
    """Step-down of Protocol v3 section 5.4 at family-wise level ``a``: a boolean mask of rejected variants."""
    tstat = np.asarray(tstat, dtype=float)
    active = np.ones(tstat.size, dtype=bool)
    rejected = np.zeros(tstat.size, dtype=bool)
    while active.any():
        c = rw_critical(tstar[:, active].max(axis=1), a)
        new = active & (tstat > c)
        if not new.any():
            break
        rejected |= new
        active &= ~new
    return rejected
