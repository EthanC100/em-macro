"""Effective number of tests (Protocol v3 section 5.6). Descriptive only: no level or decision uses it.

Li and Ji (2005), Heredity 95(3), eq. (5), p. 222:  ``M_eff = Σ_i f(|λ_i|)``, ``f(x) = 1{x ≥ 1} + (x − ⌊x⌋)``,
with ``λ_i`` the eigenvalues of the tests' correlation matrix.
"""
from __future__ import annotations

import numpy as np


def li_ji_from_eigenvalues(eig) -> float:
    a = np.abs(np.asarray(eig, dtype=float))
    return float(np.sum((a >= 1.0) + (a - np.floor(a))))


def li_ji(corr: np.ndarray) -> float:
    """``M_eff`` of a correlation matrix. Eigenvalues within 1e-9 of an integer are snapped to it first, so that
    floating-point noise (0.9999999 for 1) does not add a spurious whole test."""
    eig = np.linalg.eigvalsh(np.asarray(corr, dtype=float))
    near = np.round(eig)
    eig = np.where(np.abs(eig - near) < 1e-9, near, eig)
    return li_ji_from_eigenvalues(eig)
