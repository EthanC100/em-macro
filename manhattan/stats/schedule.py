"""The schedule ``γ(j; N)`` of Protocol v3 section 4.2: a fixed sequence that sums to 1.

    γ(j; N) = 0.9 · (j + 9)^(−1/2) / Σ_{i=1}^{N} (i + 9)^(−1/2)        for j = 1, ..., N
    γ(j; N) = 0.1 · (6/π²) · (j − N)^(−2)                               for j > N

Screening uses ``N = 120`` batches, the forward test ``N = 300`` enrolments (SIM_PREREG section 2.2 scales both).
"""
from __future__ import annotations

import numpy as np

HEAD_MASS, TAIL_MASS = 0.9, 0.1


def gamma(j, N: int):
    """``γ(j; N)`` for an integer ``j ≥ 1`` or an array of them."""
    if N < 1:
        raise ValueError("N must be at least 1")
    j = np.asarray(j)
    if np.any(j < 1):
        raise ValueError("j starts at 1")
    norm = np.sum((np.arange(1, N + 1) + 9.0) ** -0.5)
    jf = j.astype(float)
    head = HEAD_MASS * (jf + 9.0) ** -0.5 / norm
    tail = TAIL_MASS * (6.0 / np.pi**2) / np.where(jf > N, jf - N, 1.0) ** 2
    out = np.where(jf <= N, head, tail)
    return float(out) if out.ndim == 0 else out
