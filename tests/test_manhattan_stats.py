"""Manhattan statistics (manhattan/stats/): every method against a known case.

Acceptance criteria C-03 and C-05 to C-12 of docs/manhattan/MANHATTAN_PROGRESS.md. The formulas are those of
docs/manhattan/PROTOCOL_v3.md, checked against the primary papers (pages in MANHATTAN_PROGRESS.md). Synthetic
numbers only; nothing here is market evidence.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from manhattan.stats import blocklen, bootstrap, elond, eprocess, meff, schedule, screening, spa


# ------------------------------------------------------------------ C-03 schedule

def test_schedule_reproduces_protocol_values():
    assert sum((i + 9) ** -0.5 for i in range(1, 121)) == pytest.approx(16.5945, abs=5e-5)
    for j, want in ((1, 0.01715), (50, 0.00706), (100, 0.00519), (120, 0.00478)):
        assert schedule.gamma(j, 120) == pytest.approx(want, abs=5e-6)
    for j, want in ((1, 0.00981), (100, 0.00297), (300, 0.00176)):
        assert schedule.gamma(j, 300) == pytest.approx(want, abs=5e-6)


@pytest.mark.parametrize("N", [29, 48, 60, 120, 300, 576])
def test_schedule_sums_to_one_and_decreases(N):
    g = schedule.gamma(np.arange(1, N + 1), N)
    assert g.sum() == pytest.approx(0.9)
    assert np.all(np.diff(g) < 0)
    tail = schedule.gamma(np.arange(N + 1, N + 2_000_001), N)
    assert g.sum() + tail.sum() == pytest.approx(1.0, abs=1e-6)
    assert schedule.gamma(N + 1, N) == pytest.approx(0.1 * 6 / math.pi**2)


def test_schedule_refuses_bad_arguments():
    with pytest.raises(ValueError):
        schedule.gamma(0, 120)
    with pytest.raises(ValueError):
        schedule.gamma(1, 0)


# ------------------------------------------------------------------ C-05 block length

def test_flat_top_window_is_politis_white_p58():
    assert list(blocklen.flat_top([0, 0.25, 0.5, 0.75, 1.0, 1.5, -0.75])) == [1, 1, 1, 0.5, 0, 0, 0.5]


@pytest.mark.parametrize("rho,n,want", [(0.7, 200, 11.47), (0.7, 800, 18.20), (0.1, 200, 2.01), (0.1, 800, 3.20),
                                         (-0.4, 200, 5.66), (-0.4, 800, 8.99)])
def test_theoretical_block_length_matches_corrected_table_1(rho, n, want):
    """Patton, Politis and White (2009), Table 1, p. 374: with D_SB = 2 g(0)^2."""
    assert blocklen.theoretical_ar1(rho, n) == pytest.approx(want, abs=0.006)


def test_m_hat_is_the_first_lag_followed_by_five_small_autocorrelations():
    n = 1000
    crit = 2 * math.sqrt(math.log10(n) / n)
    rho = np.zeros(40)
    rho[0], rho[1], rho[2], rho[3] = 1, 0.5, 0.3, crit * 1.01
    assert blocklen.k_n(n) == 5
    assert blocklen.m_hat(rho, n) == 3
    rho[3] = crit * 0.99
    assert blocklen.m_hat(rho, n) == 2
    assert blocklen.m_hat(np.r_[1.0, np.zeros(39)], n) == 1          # white noise: the smallest positive integer
    assert blocklen.m_hat(np.r_[1.0, np.full(39, 0.9)], n) == 39      # never small: the largest significant lag


def test_block_length_by_hand_for_m_equal_two():
    """M = 2 m̂ = 2: Ĝ = 2 R̂(1) (λ(1/2) = 1, λ(1) = 0), ĝ(0) = R̂(0) + 2 R̂(1), b̂ = (Ĝ²/ĝ(0)²)^(1/3) N^(1/3)."""
    rng = np.random.default_rng(11)
    x = rng.standard_normal(2000)
    acv = blocklen.autocov(x, 2)[0]
    assert blocklen.m_hat(blocklen.autocov(x, 60)[0] / acv[0], 2000) == 1
    want = ((2 * acv[1]) ** 2 / (acv[0] + 2 * acv[1]) ** 2) ** (1 / 3) * 2000 ** (1 / 3)
    assert blocklen.pw_block_length(x)[0] == pytest.approx(want)


@pytest.mark.parametrize("rho", [0.7, -0.4])
def test_estimator_recovers_the_theoretical_block_length_on_long_ar1(rho):
    rng = np.random.default_rng(5)
    n, reps = 6400, 40
    e = rng.standard_normal((reps, n + 200))
    x = np.empty_like(e)
    x[:, 0] = e[:, 0]
    for t in range(1, n + 200):
        x[:, t] = rho * x[:, t - 1] + e[:, t]
    ratio = blocklen.pw_block_length(x[:, 200:]) / blocklen.theoretical_ar1(rho, n)
    assert 0.85 < ratio.mean() < 1.15


def test_protocol_block_length_floor_cap_and_holding_period():
    rng = np.random.default_rng(3)
    d = rng.standard_normal((6, 1750))
    assert blocklen.protocol_block_length(d) == 5.0                   # L_min binds for white noise
    assert blocklen.protocol_block_length(d, holding=21) == 21.0      # H_f binds
    assert blocklen.l_max(1750) == math.ceil(3 * math.sqrt(1750)) == 126
    assert blocklen.l_max(60) == 20
    walk = np.cumsum(rng.standard_normal((3, 400)), axis=1)
    assert blocklen.protocol_block_length(walk) <= blocklen.l_max(400)
    assert blocklen.protocol_block_length(d, l_min=2) < 5.0


# ------------------------------------------------------------------ C-08 Li-Ji

def test_li_ji_reproduces_the_papers_table_1():
    assert meff.li_ji_from_eigenvalues([3.63, 1.79, 1.13, 0.47, 0.37, 0.25, 0.18, 0.17]) == pytest.approx(5.99)
    assert meff.li_ji_from_eigenvalues([7.84, 1.60, 0.24, 0.21, 0.08, 0.03, 0.01, 0, 0, 0]) == pytest.approx(4.01)


def test_li_ji_extremes():
    assert meff.li_ji(np.eye(7)) == pytest.approx(7.0)
    assert meff.li_ji(np.ones((7, 7))) == pytest.approx(1.0)
    block = np.kron(np.eye(3), np.ones((4, 4)))                        # 3 groups of 4 identical tests
    assert meff.li_ji(block) == pytest.approx(3.0)


# ------------------------------------------------------------------ C-06 bootstrap and SPA

def test_block_means_equal_means_over_the_explicit_indices():
    rng = np.random.default_rng(7)
    d = rng.standard_normal((4, 120)) + np.arange(4)[:, None]
    for q in (1.0, 0.5, 0.2, 0.05):
        bl = bootstrap.draw_blocks(rng, 120, q, 300)
        idx = bootstrap.indices(bl)
        assert idx.shape == (300, 120) and idx.min() >= 0 and idx.max() < 120
        assert np.allclose(bootstrap.counts(bl).sum(axis=1), 120)
        assert np.allclose(bootstrap.block_means(d, bl), d[:, idx].mean(axis=2).T, atol=1e-12)


def test_index_rule_follows_or_restarts_with_probability_q():
    rng = np.random.default_rng(8)
    n, q = 200, 0.2
    idx = bootstrap.indices(bootstrap.draw_blocks(rng, n, q, 2000))
    follows = (idx[:, 1:] == (idx[:, :-1] + 1) % n)
    # a restart lands on the next index by chance with probability 1/n
    assert follows.mean() == pytest.approx(1 - q + q / n, abs=0.005)
    assert np.bincount(idx.ravel(), minlength=n).std() / (idx.size / n) < 0.05     # every day equally likely
    assert (idx[:, -1] == n - 1).sum() > 0 and ((idx[:, :-1] == n - 1) & (idx[:, 1:] == 0)).sum() > 0   # wraps


def test_kernel_is_hansens():
    n, q = 50, 0.2
    k = bootstrap.sb_kernel(n, q)
    assert k[0] == 1.0
    for i in (1, 7, 49):
        assert k[i] == pytest.approx((n - i) / n * (1 - q) ** i + i / n * (1 - q) ** (n - i))
    assert np.allclose(bootstrap.sb_kernel(n, 1.0), np.r_[1.0, np.zeros(n - 1)])


def test_long_run_variance_is_the_variance_of_the_bootstrap_mean():
    rng = np.random.default_rng(9)
    n = 150
    e = rng.standard_normal((2, n + 1))
    d = e[:, 1:] + 0.6 * e[:, :-1]                                     # MA(1)
    for q in (1.0, 0.25):
        omega2 = bootstrap.long_run_var(d, q)
        means = bootstrap.block_means(d, bootstrap.draw_blocks(rng, n, q, 40_000))
        brute = n * means.var(axis=0)
        assert np.allclose(omega2, brute, rtol=0.04)
    x = d - d.mean(axis=1, keepdims=True)
    assert np.allclose(bootstrap.long_run_var(d, 1.0), (x * x).mean(axis=1))


def test_spa_p_value_convention_and_order_of_the_three():
    assert spa.p_value(np.array([0.0, 1.0, 2.0, 3.0]), 2.0) == pytest.approx(3 / 5)    # ties count, plus one
    rng = np.random.default_rng(10)
    d = rng.standard_normal((8, 400)) - np.linspace(0, 0.5, 8)[:, None]
    r = spa.spa_test(d, np.random.default_rng(1))
    assert r.p_l <= r.p_c <= r.p_u
    assert r.tstar.shape == (r.B, 8) and r.L == 5.0 and r.n == 400


def test_spa_recentring_threshold_and_mask():
    rng = np.random.default_rng(12)
    n = 400
    d = rng.standard_normal((3, n))
    d -= d.mean(axis=1, keepdims=True)
    omega = np.sqrt(bootstrap.long_run_var(d, 0.2))
    thr = omega * math.sqrt(2 * math.log(math.log(n)) / n)
    assert np.allclose(spa.recentring_threshold(omega, n), thr)
    d[0] += -1.01 * thr[0]          # just below the threshold: left at its own mean
    d[1] += -0.99 * thr[1]          # just above: centred at zero
    d[2] += 0.05
    r = spa.spa_test(d, np.random.default_rng(2), L=5.0)
    assert list(r.recentred) == [False, True, True]


def test_spa_with_no_positive_mean_has_p_one():
    rng = np.random.default_rng(13)
    d = rng.standard_normal((5, 300))
    d = d - d.mean(axis=1, keepdims=True) - 0.01
    r = spa.spa_test(d, np.random.default_rng(3))
    assert r.T == 0.0 and r.p_c == 1.0 and r.p_l == 1.0 and r.p_u == 1.0 and r.B == 999


def test_spa_resample_count_rule_uses_one_stream():
    rng = np.random.default_rng(14)
    d = rng.standard_normal((4, 500))
    strong = d + 0.25
    r = spa.spa_test(strong, np.random.default_rng(4))
    assert r.B == 9_999 and r.p_c == pytest.approx(1 / 10_000)
    short = spa.spa_test(strong, np.random.default_rng(4), b_steps=(999,))
    assert short.B == 999 and np.array_equal(short.tstar, r.tstar[:999])         # the same stream, continued
    weak = spa.spa_test(d - d.mean(axis=1, keepdims=True), np.random.default_rng(4))
    assert weak.B == 999 and weak.p_c > 0.10
    full = spa.spa_test(strong, np.random.default_rng(4), b_steps=(99, 199, 399), continue_at=(0.10, 0.01))
    assert full.B == 399


def test_spa_size_under_an_iid_null_is_near_nominal():
    rng = np.random.default_rng(15)
    reps, n, m = 600, 250, 6
    p = np.empty(reps)
    for i in range(reps):
        common = rng.standard_normal(n)
        d = math.sqrt(0.5) * common + math.sqrt(0.5) * rng.standard_normal((m, n))
        p[i] = spa.spa_test(d, rng, b_steps=(199,)).p_c
    for a in (0.05, 0.20):
        rate, se = (p <= a).mean(), math.sqrt(a * (1 - a) / reps)
        assert a - 4 * se < rate < a + 4 * se, (a, rate)


# ------------------------------------------------------------------ C-07 Romano-Wolf

def test_romano_wolf_critical_value_is_the_stated_order_statistic():
    x = np.arange(1.0, 1000.0)                                         # B = 999
    assert spa.rw_critical(x, 0.05) == 950.0                           # the ⌈0.95 · 1000⌉-th smallest
    assert spa.rw_critical(x, 0.001) == 999.0
    assert spa.rw_critical(x, 0.0005) == math.inf                      # B too small for that level


def test_romano_wolf_steps_down_on_the_remaining_set():
    tstat = np.array([5.0, 2.0, 0.0])
    tstar = np.zeros((999, 3))
    tstar[:, 0] = np.linspace(-4, 4, 999)       # variant 0 alone sets a high bar at step 1
    tstar[:, 1] = np.linspace(-1.5, 1.5, 999)
    tstar[:, 2] = np.linspace(-1, 1, 999)
    step1 = spa.rw_critical(tstar.max(axis=1), 0.05)
    assert 2.0 < step1 < 5.0
    out = spa.romano_wolf(tstat, tstar, 0.05)
    assert list(out) == [True, True, False]     # variant 1 passes only once variant 0 has been set aside
    assert not spa.romano_wolf(np.array([1.0, 1.0, 0.0]), tstar, 0.05).any()


def test_romano_wolf_names_a_strong_variant_and_keeps_the_familywise_rate():
    rng = np.random.default_rng(16)
    reps, n, m = 400, 250, 6
    any_null, strong = 0, 0
    for _ in range(reps):
        d = rng.standard_normal((m, n))
        d[0] += 0.4
        r = spa.spa_test(d, rng, b_steps=(199,))
        rej = spa.romano_wolf(r.tstat, r.tstar, 0.05)
        strong += rej[0]
        any_null += rej[1:].any()
    assert strong / reps > 0.95
    assert any_null / reps < 0.05 + 4 * math.sqrt(0.05 * 0.95 / reps)


# ------------------------------------------------------------------ C-09 screening candidate (i)

def bh(p, level):
    p = np.asarray(p)
    order = np.argsort(p)
    ok = p[order] <= np.arange(1, p.size + 1) * level / p.size
    k = ok.nonzero()[0].max() + 1 if ok.any() else 0
    out = np.zeros(p.size, bool)
    out[order[:k]] = True
    return out


def test_candidate_i_first_batch_is_bh_at_alpha_gamma_1():
    rng = np.random.default_rng(17)
    p = np.r_[rng.uniform(0, 1, 10), 1e-5, 2e-4]
    proc = screening.BatchBH(N=120)
    d = proc.step(p)
    assert d.level == pytest.approx(0.20 * schedule.gamma(1, 120))
    assert np.array_equal(d.rejected, bh(p, d.level))
    assert d.k == 2 and d.admission == pytest.approx(2 * d.level / 12)


def test_candidate_i_level_grows_with_earlier_discoveries_and_is_capped():
    proc = screening.BatchBH(N=120)
    proc.step([1e-9] * 4 + [0.9] * 6)                                 # 4 discoveries in batch 1
    d2 = proc.step([0.5] * 8)
    assert d2.level == pytest.approx(0.20 * schedule.gamma(2, 120) * (8 + 4) / 8)
    assert d2.k == 0 and d2.admission == 0.0
    proc.R = 10_000                                                   # an absurd count: the cap at α_S holds
    assert proc.step([0.5] * 8).level == 0.20


def test_candidate_i_running_estimate_never_exceeds_alpha():
    """Zrnic et al.: Σ_s α_s n_s / (n_s + R_{<s}) ≤ α. Here it equals α Σ γ_s without the cap, less with it."""
    rng = np.random.default_rng(18)
    proc = screening.BatchBH(N=48)
    for _ in range(300):
        n = int(rng.integers(1, 17))
        proc.step(np.where(rng.random(n) < 0.3, rng.uniform(0, 1e-4, n), rng.uniform(0, 1, n)))
        assert proc.wealth_estimate <= 0.20 + 1e-12
    assert proc.R > 0


def test_candidate_i_worked_example():
    """Batch 1, n = 4, level 0.01 for the arithmetic: thresholds 0.0025, 0.005, 0.0075, 0.01."""
    proc = screening.BatchBH(N=120, alpha=0.01 / schedule.gamma(1, 120))
    d = proc.step([0.006, 0.004, 0.02, 0.0001])
    assert d.level == pytest.approx(0.01)
    assert list(d.rejected) == [True, True, False, True] and d.k == 3     # 0.006 ≤ 0.0075 carries the first three


# ------------------------------------------------------------------ C-10 screening candidate (ii)

def test_candidate_ii_one_family_per_batch_is_elond():
    proc = screening.EbhElond(N=120)
    R = 0
    rng = np.random.default_rng(19)
    for b in range(1, 60):
        e = float(rng.choice([0.5, 50.0, 5000.0, 50_000.0]))
        want = e >= 1.0 / (0.20 * schedule.gamma(b, 120) * (R + 1))
        d = proc.step([e])
        assert bool(d.rejected[0]) == want
        R += want
    assert R > 0 and proc.R == R


def test_candidate_ii_single_batch_with_gamma_one_is_ebh(monkeypatch):
    monkeypatch.setattr(screening, "gamma", lambda j, N: 1.0)
    e = np.array([100.0, 30.0, 9.0, 1.0, 0.2])
    d = screening.EbhElond(N=1, alpha=0.20).step(e)
    # e-BH: reject the k largest when the k-th largest is at least n/(α k): 25, 12.5, 8.33, 6.25, 5
    assert d.k == 3 and list(d.rejected) == [True, True, True, False, False]


def test_candidate_ii_rejects_exactly_k_and_worked_example():
    g1 = schedule.gamma(1, 120)
    n = 15
    assert n / (0.20 * g1) == pytest.approx(4373, abs=1)               # the protocol's own example
    proc = screening.EbhElond(N=120)
    bar1, bar2 = n / (0.20 * g1 * 1), n / (0.20 * g1 * 2)
    e = np.r_[bar2 * 1.01, bar2 * 1.01, np.ones(n - 2)]                 # neither clears the bar for one alone
    d = proc.step(e)
    assert bar2 * 1.01 < bar1 and d.k == 2 and d.rejected.sum() == 2
    assert d.admission == pytest.approx(0.20 * g1 * 2 / n) == pytest.approx(1 / bar2)
    d = proc.step(np.r_[n / (0.20 * schedule.gamma(2, 120) * 3) * 1.001, np.ones(n - 1)])
    assert d.k == 1 and proc.R == 3                                    # earlier discoveries lowered the bar
    rng = np.random.default_rng(20)
    for _ in range(200):
        e = np.exp(rng.normal(0, 4, int(rng.integers(1, 17))))
        d = proc.step(e)
        assert d.rejected.sum() == d.k


def test_empty_batches_are_harmless():
    for proc in (screening.BatchBH(N=10), screening.EbhElond(N=10)):
        d = proc.step([])
        assert d.k == 0 and d.rejected.size == 0 and proc.b == 1


# ------------------------------------------------------------------ C-11 betting process

def test_lambda_grid_is_section_6_4():
    assert np.allclose(eprocess.lambdas(), [0.15, 0.075, 0.0375, 0.01875, 0.009375, 0.0046875])
    assert np.allclose(eprocess.lambdas(4.0)[0], 0.225)


def test_scale_and_decisions_use_only_the_past():
    rng = np.random.default_rng(21)
    P = rng.standard_normal((2, 900))
    first, weeks = 300, 100
    base = eprocess.weekly_inputs(P, first, weeks, floor=0.5)
    w = 40
    day = first + 5 * w
    changed = P.copy()
    changed[:, day:] = rng.standard_normal((2, 900 - day)) * 9         # rewrite week w and everything after
    again = eprocess.weekly_inputs(changed, first, weeks, floor=0.5)
    for key in ("s", "bet", "vr"):
        assert np.array_equal(base[key][:, : w + 1], again[key][:, : w + 1]), key    # week w's own inputs too
    assert np.array_equal(base["Z"][:, :w], again["Z"][:, :w])
    assert not np.array_equal(base["Z"][:, w], again["Z"][:, w])
    s = eprocess.daily_scale(P, floor=0.0)
    assert s[0, 0] == 0.0 and s[0, 1] == pytest.approx(abs(P[0, 0]))
    a = 0.5 ** (1 / 60)
    wts = a ** np.arange(9, -1, -1)
    assert s[0, 10] == pytest.approx(math.sqrt((wts * P[0, :10] ** 2).sum() / wts.sum()))
    assert eprocess.daily_scale(P * 1e-6, floor=0.5).min() == 0.5


def test_weekly_scale_and_truncation():
    P = np.full((1, 400), 0.01)
    P[0, 300:305] = -3.0                                              # a week 5 × 300 times the usual size
    w = eprocess.weekly_inputs(P, 300, 10, floor=0.5)
    assert w["s"][0, 0] == pytest.approx(math.sqrt(5) * 0.5)           # floor binds: s_d = 0.5
    assert w["Z"][0, 0] == pytest.approx(-15.0 / (math.sqrt(5) * 0.5))
    assert w["Y"][0, 0] == -6.0 and w["Y"][0, 0] > w["Z"][0, 0]
    n_trunc, debt = eprocess.tail_record(w["Z"], w["Y"])
    assert n_trunc[0] == 1 and debt[0] == pytest.approx(-6.0 - w["Z"][0, 0])


def test_variance_ratio_by_hand_and_vectorised():
    rng = np.random.default_rng(22)
    z = rng.standard_normal(252)
    x = z - z.mean()
    rho = [np.sum(x[j:] * x[:-j]) / np.sum(x * x) for j in (1, 2, 3, 4)]
    want = 1 + 2 * (0.8 * rho[0] + 0.6 * rho[1] + 0.4 * rho[2] + 0.2 * rho[3])
    assert eprocess.variance_ratio(z) == pytest.approx(want)
    Z = rng.standard_normal((3, 700))
    got = eprocess.weekly_variance_ratio(Z, 250, 80)
    assert np.all(got[:, 0] == 1.0)                                    # 250 earlier days: the rule cannot fire
    for k in range(3):
        for w in (1, 17, 79):
            d0 = 250 + 5 * w
            assert got[k, w] == pytest.approx(eprocess.variance_ratio(Z[k, d0 - 252 : d0]))


def test_no_bet_when_the_variance_ratio_is_high():
    rng = np.random.default_rng(23)
    e = rng.standard_normal(1500)
    ar = np.empty(1500)
    ar[0] = e[0]
    for t in range(1, 1500):
        ar[t] = 0.6 * ar[t - 1] + e[t]                                 # strongly positively autocorrelated
    w = eprocess.weekly_inputs(ar[None, :], 500, 200, floor=0.1)
    assert w["vr"].mean() > 1.25 and not w["bet"].all()
    inc = eprocess.log_increments(w["Y"], w["bet"])
    assert np.all(inc[:, :, ~w["bet"][0]] == 0.0)
    W = eprocess.wealth_paths(eprocess.cumulative_log(inc))
    still = np.flatnonzero(~w["bet"][0])
    assert np.all(W[0, still + 1] == W[0, still])                      # wealth does not move in a no-bet week


def test_wealth_is_the_mean_of_six_products_and_never_negative():
    rng = np.random.default_rng(24)
    Y = np.maximum(rng.standard_normal((2, 300)) * 2, -6.0)
    Y[0, 10:30] = -6.0                                                 # twenty worst-case weeks in a row
    bet = np.ones_like(Y, dtype=bool)
    cum = eprocess.cumulative_log(eprocess.log_increments(Y, bet))
    W = eprocess.wealth_paths(cum)
    want = np.mean([np.cumprod(1 + lam * Y, axis=1) for lam in eprocess.lambdas()], axis=0)
    assert np.allclose(W[:, 1:], want) and np.all(W[:, 0] == 1.0)
    assert W.min() > 0.0
    later = eprocess.wealth_paths(cum, start=100)
    want_later = np.mean([np.cumprod(1 + lam * Y[:, 100:], axis=1) for lam in eprocess.lambdas()], axis=0)
    assert np.allclose(later[:, 1:], want_later)                       # a process started at 1 at week 100
    assert np.allclose(eprocess.family_wealth(W), W.mean(axis=0))


def test_guard_by_hand_and_needs_52_weeks():
    rng = np.random.default_rng(25)
    Z = rng.standard_normal((1, 120)) + 0.6
    low = eprocess.guard_lower(Z)
    assert np.all(np.isneginf(low[0, :51])) and np.isfinite(low[0, 51])
    t = 100
    z = Z[0, :t]
    mu, var = z.mean(), (z * z).mean() - z.mean() ** 2
    zm = Z[0, :52]
    var_m = (zm * zm).mean() - zm.mean() ** 2
    la = -2 * math.log(0.05)
    rho2 = (la + math.log(la) + 1) / (var_m * 52 * math.log(52))
    width = math.sqrt(2 * (t * var * rho2 + 1) / (t * t * rho2) * math.log(1 + math.sqrt(t * var * rho2 + 1) / (2 * 0.05)))
    assert low[0, t - 1] == pytest.approx(mu - width)
    assert np.all(np.isneginf(eprocess.guard_lower(Z[:, :51])))
    # the family guard reads the leading component
    Zf = np.vstack([Z[0], -Z[0]])
    Wc = np.vstack([np.full(121, 2.0), np.full(121, 1.0)])
    g = eprocess.family_guard(Wc, Zf)
    assert g.shape == (120,) and not g[:51].any() and g[-1]
    assert not eprocess.family_guard(Wc[::-1], Zf)[-1]                 # leading component has a negative mean


def test_null_wealth_rarely_reaches_twenty():
    """Ville: for a fair bet the chance of ever reaching 1/a is at most a (here a = 0.05)."""
    rng = np.random.default_rng(26)
    paths, weeks = 4000, 520
    Y = rng.choice([-1.0, 1.0], size=(paths, weeks))
    W = eprocess.wealth_paths(eprocess.cumulative_log(eprocess.log_increments(Y, np.ones_like(Y, bool))))
    hit = (W.max(axis=1) >= 20).mean()
    assert hit <= 0.05 + 3 * math.sqrt(0.05 * 0.95 / paths)
    drift = rng.choice([-1.0, 1.0], p=[0.42, 0.58], size=(paths, weeks))     # an edge: wealth grows
    Wd = eprocess.wealth_paths(eprocess.cumulative_log(eprocess.log_increments(drift, np.ones_like(drift, bool))))
    assert (Wd.max(axis=1) >= 20).mean() > 0.5


# ------------------------------------------------------------------ C-12 forward e-LOND

def test_single_family_is_rejected_exactly_at_its_bar():
    bar = 1 / (0.05 * schedule.gamma(1, 300))
    assert bar == pytest.approx(2039, abs=1)
    w = np.array([[1.0, bar * 0.999, bar, 5.0]])
    out = elond.run(w, np.ones_like(w, bool), np.array([0]), N_F=300)
    assert out["reject_at"][0] == 2 and list(out["R"]) == [0, 0, 1, 1]


def test_a_rejection_lowers_every_other_bar_at_once():
    g = schedule.gamma(np.arange(1, 4), 300)
    bars_alone = 1 / (0.05 * g)
    w = np.ones((3, 3))
    w[:, 1] = bars_alone / 2 * 1.01            # none clears its own bar alone; two together do, three do
    out = elond.run(w, np.ones_like(w, bool), np.zeros(3, int), N_F=300)
    assert list(out["reject_at"]) == [1, 1, 1]
    w2 = np.ones((3, 3))
    w2[0, 1] = bars_alone[0] * 1.01            # family 0 clears alone...
    w2[1, 1] = bars_alone[1] / 2 * 1.01        # ...which is enough for family 1 in the same period
    w2[2, 2] = bars_alone[2] / 3 * 1.01        # and family 2 next period at the bar for R = 2 already
    out = elond.run(w2, np.ones_like(w2, bool), np.zeros(3, int), N_F=300)
    assert list(out["reject_at"]) == [1, 1, 2] and list(out["R"]) == [0, 2, 3]


def test_rejections_are_permanent_guard_blocks_and_start_is_respected():
    bar = 1 / (0.05 * schedule.gamma(1, 300))
    w = np.array([[bar * 2, 0.1, 0.1, 0.1]])
    out = elond.run(w, np.ones_like(w, bool), np.array([0]), N_F=300)
    assert out["reject_at"][0] == 0 and list(out["R"]) == [1, 1, 1, 1]         # wealth falling later changes nothing
    guard = np.array([[False, False, True, True]])
    w = np.full((1, 4), bar * 2)
    assert elond.run(w, guard, np.array([0]), N_F=300)["reject_at"][0] == 2
    assert elond.run(w, np.ones_like(w, bool), np.array([3]), N_F=300)["reject_at"][0] == 3
    assert elond.run(w * 0 + 1, np.ones_like(w, bool), np.array([0]), N_F=300)["reject_at"][0] == -1


def test_enrolment_order_sets_the_share_and_components_are_named_at_the_stricter_bar():
    out = elond.run(np.ones((4, 2)), np.ones((4, 2), bool), np.zeros(4, int), N_F=300)
    assert np.allclose(out["gamma"], schedule.gamma(np.arange(1, 5), 300))
    g1 = schedule.gamma(1, 300)
    bar = 3 / (0.05 * g1 * 2)                                           # H + 1 = 3 components, R = 2
    assert list(elond.component_named(np.array([bar * 1.01, bar * 0.99, 1.0]), g1, R=2)) == [True, False, False]
    assert not elond.component_named(np.array([1e9, 1.0, 1.0]), g1, R=0).any()
