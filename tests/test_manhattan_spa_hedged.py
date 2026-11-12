"""The hedge-aware SPA test of Protocol v3.1 section 5.1 (manhattan/stats/spa_hedged.py). Synthetic data only.

What is checked: the linear form of the resampled hedged means against the slow reference that builds every
pseudo-series and hedges it; that the test is the 3.0 test, bit for bit, where there is nothing to hedge
(SIM_PREREG_v2 criterion V13); the centre; and that on a hedge that leaks a factor's mean the 3.0 test rejects
too often while this one does not.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from manhattan.stats import bootstrap, hedge, spa, spa_hedged


def world(K=1, pre=300, n=400, m=4, seed=1, factor_mean=0.05, beta=None):
    rng = np.random.default_rng(seed)
    C = factor_mean + rng.standard_normal((K, pre + n))
    b = rng.standard_normal((m, K)) if beta is None else np.full((m, K), beta)
    return b @ C + rng.standard_normal((m, pre + n)), C, pre, n


# ------------------------------------------------------------------ the resampled means

@pytest.mark.parametrize("K", [1, 3])
@pytest.mark.parametrize("pre", [300, 20, 0])
def test_resample_weights_equal_hedging_every_pseudo_series(K, pre):
    r, C, _, n = world(K=K, pre=300)
    r, C = r[:, 300 - pre :], C[:, 300 - pre :]                    # a long history, a short one (below the minimum), none
    idx = bootstrap.indices(bootstrap.draw_blocks(np.random.default_rng(2), n, 0.1, 9))
    W = spa_hedged.resample_weights(C, idx, pre, L=200, min_obs=50)
    ref = spa_hedged.direct_means(r, C, idx, pre, L=200, min_obs=50)
    assert W.shape == (9, pre + n) and np.allclose(W @ r.T, ref, rtol=0, atol=1e-12)


@pytest.mark.parametrize("K", [1, 2])
def test_the_identity_sequence_gives_the_live_hedged_mean(K):
    r, C, pre, n = world(K=K)
    W = spa_hedged.resample_weights(C, np.arange(n)[None, :], pre, L=200, min_obs=50)
    live, _ = hedge.hedged(r, C, L=200, min_obs=50)
    assert np.allclose(W @ r.T, live[:, pre:].mean(axis=1), rtol=0, atol=1e-13)


def test_a_window_longer_than_the_data_before_it_uses_what_exists():
    r, C, pre, n = world(pre=120, n=150)
    idx = bootstrap.indices(bootstrap.draw_blocks(np.random.default_rng(3), n, 0.2, 5))
    for L in (100, 500):                                            # shorter and longer than the whole pseudo-series
        W = spa_hedged.resample_weights(C, idx, pre, L=L, min_obs=40)
        assert np.allclose(W @ r.T, spa_hedged.direct_means(r, C, idx, pre, L=L, min_obs=40), rtol=0, atol=1e-12)


def test_the_centre_is_the_least_squares_intercept_over_the_window():
    r, C, pre, n = world(K=2)
    a = spa_hedged.window_alpha_weights(C[:, pre:])
    X = np.vstack([np.ones(n), C[:, pre:]]).T
    want = np.linalg.lstsq(X, r[:, pre:].T, rcond=None)[0][0]
    assert np.allclose(r[:, pre:] @ a, want, rtol=0, atol=1e-13)


# ------------------------------------------------------------------ the test

def test_with_nothing_to_hedge_it_is_the_30_test_bit_for_bit():
    """SIM_PREREG_v2 criterion V13."""
    rng = np.random.default_rng(4)
    for shift in (0.0, 0.12):                                       # the second continues to 9,999 resamples
        d = shift + rng.standard_normal((5, 600))
        a = spa.spa_test(d, np.random.default_rng(9))
        b = spa_hedged.spa_test(d, np.random.default_rng(9))
        assert (a.p_c, a.p_l, a.p_u, a.T, a.B, a.L) == (b.p_c, b.p_l, b.p_u, b.T, b.B, b.L)
        assert np.array_equal(a.tstar, b.tstar) and np.array_equal(a.tstat, b.tstat)
        for level in (0.05, 0.2):
            assert np.array_equal(spa.romano_wolf(a.tstat, a.tstar, level), spa.romano_wolf(b.tstat, b.tstar, level))
    assert a.B == 9999


def test_the_statistic_is_the_live_one_and_the_resamples_are_centred_at_alpha():
    r, C, pre, n = world(m=3, factor_mean=0.1, beta=1.0)
    res = spa_hedged.spa_test(r, np.random.default_rng(5), factors=C, window=(pre, n), L=8.0, b_steps=(999,),
                              L_beta=200, min_obs=50)
    live, _ = hedge.hedged(r, C, L=200, min_obs=50)
    d = live[:, pre:]
    omega = np.sqrt(bootstrap.long_run_var(d, 1 / 8.0))
    assert np.allclose(res.dbar, d.mean(axis=1)) and np.allclose(res.omega, omega)
    assert res.T == pytest.approx(max(0.0, (math.sqrt(n) * d.mean(axis=1) / omega).max()))
    assert res.p_l <= res.p_c <= res.p_u and res.B == 999 and res.n == n
    # the same block draws, by hand
    idx = bootstrap.indices(bootstrap.draw_blocks(np.random.default_rng(5), n, 1 / 8.0, 999))
    means = spa_hedged.direct_means(r, C, idx, pre, L=200, min_obs=50)
    alpha = r[:, pre:] @ spa_hedged.window_alpha_weights(C[:, pre:])
    assert np.allclose(res.tstar, math.sqrt(n) * (means - alpha) / omega, atol=2e-5)        # stored as float32
    # the resampled statistic keeps what the shrunken hedge lets through: its mean is above zero, as the live one's is
    assert res.tstar.mean() > 0.1 and (math.sqrt(n) * (d.mean(axis=1) - alpha) / omega).mean() > 0.1


def test_it_consumes_the_random_stream_exactly_as_the_30_test_does():
    r, C, pre, n = world()
    live, _ = hedge.hedged(r, C, L=200, min_obs=50)
    g1, g2 = np.random.default_rng(6), np.random.default_rng(6)
    spa.spa_test(live[:, pre:], g1, L=10.0, b_steps=(999,))
    spa_hedged.spa_test(r, g2, factors=C, window=(pre, n), L=10.0, b_steps=(999,), L_beta=200, min_obs=50)
    assert g1.random() == g2.random()


def test_a_hedge_cost_is_charged_in_every_resample():
    r, C, pre, n = world(m=2, n=200)
    kw = dict(factors=C, window=(pre, n), L=6.0, b_steps=(99,), L_beta=150, min_obs=40)
    free = spa_hedged.spa_test(r, np.random.default_rng(7), **kw)
    paid = spa_hedged.spa_test(r, np.random.default_rng(7), cost=0.05, **kw)
    idx = bootstrap.indices(bootstrap.draw_blocks(np.random.default_rng(7), n, 1 / 6.0, 99))
    means = spa_hedged.direct_means(r, C, idx, pre, cost=0.05, L=150, min_obs=40)
    alpha = r[:, pre:] @ spa_hedged.window_alpha_weights(C[:, pre:])
    assert np.allclose(paid.tstar, math.sqrt(n) * (means - alpha) / paid.omega, atol=2e-5)
    assert np.all(paid.dbar < free.dbar) and np.all(paid.tstar.mean(axis=0) < free.tstar.mean(axis=0))


def test_inputs_are_checked():
    r, C, pre, n = world()
    with pytest.raises(ValueError, match="window"):
        spa_hedged.spa_test(r, np.random.default_rng(0), factors=C)
    with pytest.raises(ValueError, match="same periods"):
        spa_hedged.spa_test(r, np.random.default_rng(0), factors=C[:, :-1], window=(pre, n))
    with pytest.raises(ValueError, match="inside"):
        spa_hedged.spa_test(r, np.random.default_rng(0), factors=C, window=(pre, n + 1))


def test_size_when_the_hedge_leaks_a_factors_mean():
    """Returns with no edge of their own, a constant exposure of 1 to a factor with a large mean, and the ridge
    hedge of section 2.2, which keeps about 9% of it. The 3.0 test on the hedged returns rejects far too often;
    the test that re-estimates the hedge does not."""
    trials, pre, n, m, L = 240, 150, 400, 3, 6.0
    rng = np.random.default_rng(20261112)
    v30 = v31 = 0
    for t in range(trials):
        C = 0.30 + rng.standard_normal((1, pre + n))
        r = C + rng.standard_normal((m, pre + n))
        live, _ = hedge.hedged(r, C, L=120, min_obs=40)
        v30 += spa.spa_test(live[:, pre:], np.random.default_rng([1, t]), L=L, b_steps=(499,)).p_c <= 0.05
        v31 += spa_hedged.spa_test(r, np.random.default_rng([1, t]), factors=C, window=(pre, n), L=L, b_steps=(499,),
                                   L_beta=120, min_obs=40).p_c <= 0.05
    # nominal 0.05: two standard errors of a rate of 0.05 over 240 trials is 0.028
    assert v31 / trials <= 0.05 + 0.03
    assert v30 / trials >= 0.12 and v30 / trials - v31 / trials >= 0.06
