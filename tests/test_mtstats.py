"""Reproduce the spec's section 0.2 numbers (docs/research/algorithm_spec_2026-11.md)."""
import numpy as np
import pytest

from em_macro import mtstats as M

SR_ANN, T, N = 0.65, 81, 7
SR_M = SR_ANN / np.sqrt(12)          # 0.18764
YRS = T / 12


def test_naive():
    r = M.naive_test(SR_ANN, YRS)
    assert r["t"] == pytest.approx(1.689, abs=1e-3)
    assert r["p_two_sided"] == pytest.approx(0.091, abs=1e-3)
    assert r["p_one_sided"] == pytest.approx(0.046, abs=1e-3)
    assert r["se_sr_ann"] == pytest.approx(0.42, abs=5e-3)


def test_psr_scenarios():
    assert M.psr(SR_M, T, 0, 3) == pytest.approx(0.952, abs=1e-3)
    assert M.psr(SR_M, T, -0.7, 5) == pytest.approx(0.940, abs=1e-3)


def test_sr0_and_dsr():
    bracket = M.sr0(N, 1.0)
    assert bracket == pytest.approx(1.3871, abs=1e-3)
    s0 = M.sr0(N, 1 / np.sqrt(80))
    assert s0 == pytest.approx(0.155, abs=1e-3)
    assert s0 * np.sqrt(12) == pytest.approx(0.537, abs=1e-3)
    assert M.dsr(SR_M, T, N, 1 / np.sqrt(80)) == pytest.approx(0.61, abs=0.01)
    assert M.sr0(N, 0.20 / np.sqrt(12)) * np.sqrt(12) == pytest.approx(0.28, abs=0.01)
    assert M.dsr(SR_M, T, N, 0.20 / np.sqrt(12)) == pytest.approx(0.83, abs=0.01)


@pytest.mark.parametrize("g3,g4,m90,m95", [(0, 3, 48.5, 79.2), (-0.7, 5, 55.4, 90.6), (-1.0, 6, 58.5, 95.7)])
def test_min_trl(g3, g4, m90, m95):
    assert M.min_trl(SR_M, g3, g4, 0.90) == pytest.approx(m90, abs=0.1)
    assert M.min_trl(SR_M, g3, g4, 0.95) == pytest.approx(m95, abs=0.1)


def test_min_trl_against_deflated_benchmark():
    # spec §0.2 says "more than 200 years"; the formula gives 131 y (S1, 90%) to 315 y (S3, 95%)
    s0 = M.sr0(N, 1 / np.sqrt(80))
    assert M.min_trl(SR_M, 0, 3, 0.90, s0=s0) / 12 == pytest.approx(131.2, abs=0.1)
    assert M.min_trl(SR_M, -0.7, 5, 0.95, s0=s0) / 12 > 200


def test_haircuts():
    assert M.haircut_bonferroni(SR_ANN, YRS, N) == pytest.approx(0.18, abs=0.005)
    assert M.haircut_sidak(SR_ANN, YRS, N) == pytest.approx(0.27, abs=0.005)
    assert M.haircut_bhy(SR_ANN, YRS, N) == 0.0                     # p_adj >= 1: 100% haircut
    assert (3 / SR_ANN) ** 2 == pytest.approx(21.3, abs=0.05)        # years needed for t > 3


def test_psr_monotone_in_skew():
    assert M.psr(SR_M, T, -1.0, 6) < M.psr(SR_M, T, 0, 3)
