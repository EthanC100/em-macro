import numpy as np
import pytest

from em_macro.diagnostics import ledoit_wolf, risk_decomposition


def test_ledoit_wolf_matches_direct_formula():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, 5)) @ rng.normal(size=(5, 5))
    Sig, a = ledoit_wolf(X)
    Xc = X - X.mean(0)
    n, p = Xc.shape
    S = Xc.T @ Xc / n
    mu = np.trace(S) / p
    d2 = np.linalg.norm(S - mu * np.eye(p), "fro") ** 2 / p
    b2 = sum(np.linalg.norm(np.outer(x, x) - S, "fro") ** 2 for x in Xc) / n ** 2 / p
    shrink = min(b2, d2) / d2
    assert a == pytest.approx(shrink)
    assert np.allclose(Sig, shrink * mu * np.eye(p) + (1 - shrink) * S)
    assert np.all(np.linalg.eigvalsh(Sig) > 0)


def test_risk_contributions_sum_to_one_and_factor_share_of_pure_factor_bet():
    rng = np.random.default_rng(1)
    f = rng.normal(size=(500, 2)) * 0.01
    R = np.column_stack([f[:, 0], f[:, 1], rng.normal(size=500) * 0.01])
    w = np.array([1.0, 0.0, 0.0])
    sp, rc, fs, _ = risk_decomposition(w, R, f, 12)
    assert rc.sum() == pytest.approx(1.0)
    # ~1, not exactly 1: sigma_p^2 uses the Ledoit-Wolf-shrunk covariance, the factor
    # covariance (spec formula) does not, so shrinkage moves the share slightly
    assert fs[0] == pytest.approx(1.0, abs=0.1) and abs(fs[1]) < 0.05
    w2 = np.array([0.0, 0.0, 1.0])
    _, _, fs2, _ = risk_decomposition(w2, R, f, 12)
    assert abs(fs2.sum()) < 0.05                                            # idiosyncratic position
