"""The joint stationary bootstrap (Protocol v3 section 5.2; Politis and Romano 1994; Hansen 2005, p. 371-372).

Index rule: ``τ(1)`` is uniform on ``1..n``; then with probability ``1 − q`` the next index follows the last
(wrapping from ``n`` to 1), and with probability ``q = 1/L`` it is a new uniform draw. One index sequence is used
for every variant of a family, so each resample keeps the variants' correlation on each day.

A resample is therefore a list of blocks ``(start, length)``. ``counts`` turns the blocks into the number of times
each day is used in each resample (one addition per block end, then a running sum), and the resampled means of
all variants are one matrix product. ``indices`` expands the same blocks into the explicit index sequence; a test
checks that both give the same means.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Blocks:
    """``B`` resamples of length ``n``. Block ``j`` reads ``length[j]`` consecutive days from ``start[j]`` (0-based,
    wrapping); ``first[b]`` is the position in these arrays of resample ``b``'s first block."""

    n: int
    start: np.ndarray
    length: np.ndarray
    first: np.ndarray

    @property
    def B(self) -> int:
        return len(self.first)


def draw_blocks(rng: np.random.Generator, n: int, q: float, B: int) -> Blocks:
    """Draw ``B`` stationary-bootstrap resamples of ``1..n`` with restart probability ``q``."""
    if not 0.0 < q <= 1.0:
        raise ValueError("q must be in (0, 1]")
    new = rng.random((B, n), dtype=np.float32) < q
    new[:, 0] = True
    flat = np.flatnonzero(new)                       # row-major: by resample, then by day
    nxt = np.empty_like(flat)
    nxt[:-1] = flat[1:]
    nxt[-1] = B * n
    row_end = (flat // n + 1) * n
    length = np.minimum(nxt, row_end) - flat
    start = rng.integers(0, n, size=flat.size)
    first = np.flatnonzero(flat % n == 0)
    return Blocks(n=n, start=start, length=length, first=first)


def counts(blocks: Blocks) -> np.ndarray:
    """How many times each day enters each resample: shape ``(B, n)``, every row summing to ``n``."""
    n, B = blocks.n, blocks.B
    row = np.repeat(np.arange(B), np.diff(np.append(blocks.first, blocks.start.size)))
    base = row * (n + 1)
    end = blocks.start + blocks.length
    wrap = end > n
    add = np.bincount(base + blocks.start, minlength=B * (n + 1)).astype(np.float64)
    add += np.bincount(base[wrap], minlength=B * (n + 1))                 # a wrapped block restarts at day 0
    add -= np.bincount(base + np.where(wrap, end - n, end), minlength=B * (n + 1))
    return np.cumsum(add.reshape(B, n + 1)[:, :n], axis=1)


def block_means(d: np.ndarray, blocks: Blocks) -> np.ndarray:
    """Mean of every row of ``d`` (variants by days) over every resample: shape ``(B, m)``."""
    return counts(blocks) @ np.atleast_2d(d).T / blocks.n


def indices(blocks: Blocks) -> np.ndarray:
    """The explicit 0-based index sequences, shape ``(B, n)`` (for tests and small cases)."""
    n = blocks.n
    total = blocks.B * n
    pos = np.cumsum(blocks.length) - blocks.length            # position of each block's first day
    owner = np.repeat(np.arange(blocks.start.size), blocks.length)
    offset = np.arange(total) - pos[owner]
    return ((blocks.start[owner] + offset) % n).reshape(blocks.B, n)


def sb_kernel(n: int, q: float) -> np.ndarray:
    """Hansen (2005), p. 372: ``κ(n, i) = ((n−i)/n)(1−q)^i + (i/n)(1−q)^(n−i)`` for ``i = 0..n−1``."""
    i = np.arange(n, dtype=float)
    return (n - i) / n * (1.0 - q) ** i + i / n * (1.0 - q) ** (n - i)


def long_run_var(d: np.ndarray, q: float) -> np.ndarray:
    """``ω̂²_k = γ̂_{0,k} + 2 Σ_{i=1}^{n−1} κ(n,i) γ̂_{i,k}`` for each row of ``d`` (Hansen 2005, p. 372): the
    variance of ``√n`` times the stationary-bootstrap mean, taken over the bootstrap's own distribution."""
    d = np.atleast_2d(np.asarray(d, dtype=float))
    n = d.shape[1]
    x = d - d.mean(axis=1, keepdims=True)
    size = 1 << (2 * n - 1).bit_length()
    f = np.fft.rfft(x, size, axis=1)
    acov = np.fft.irfft(f * np.conj(f), size, axis=1)[:, :n] / n
    w = 2.0 * sb_kernel(n, q)
    w[0] = 1.0
    return acov @ w
