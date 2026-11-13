"""The analytic hierarchical model of Protocol v3.1 section 7 (manhattan/stats/hier_analytic.py). Synthetic data
only; no sampler is needed or imported.

What is checked: the six models and the grid against the protocol's text; the closed form of one family against
brute-force integration; a whole fit against an independent sum over the same grid; that nothing in a fit is
random; that the model answers evidence the way section 7.2 says (shrinkage, the wide components, the common
shock, the grid gate); and that it recovers a retention and a mean apparent edge that were not drawn from its
priors (criterion C-13 of MANHATTAN_PROGRESS, which the sampled model was too slow to test).
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from scipy.special import logsumexp
from scipy.stats import norm

from manhattan.stats import hier_analytic as ha
from manhattan.testing import reads_hand_edited_file

ROOT = Path(__file__).resolve().parents[1]


def make(n_f=60, seed=0, edge=0.9, n_edge=8, forward=1.0, s_H=0.3, s_F=0.3, age=4.0, **kw) -> ha.Data:
    """Families 0..n_edge−1 have an apparent edge; their forward record shows ``forward`` times it."""
    rng = np.random.default_rng(seed)
    a = np.where(np.arange(n_f) < n_edge, edge, 0.0)
    return ha.Data(y_H=a + s_H * rng.standard_normal(n_f), s_H=np.full(n_f, s_H),
                   y_F=forward * a + s_F * rng.standard_normal(n_f), s_F=np.full(n_f, s_F),
                   mech=np.arange(n_f) % 3, age=np.full(n_f, age), **kw)


# ------------------------------------------------------------------ definition

def test_the_six_models_differ_only_as_section_7_2e_says():
    s = {x.name: x for x in ha.SPECS}
    assert list(s) == ["S0", "S1", "S2", "S3", "S4", "S5"]
    base = s["S0"]
    assert (base.mu_rho, base.w, base.psi_fixed, base.decay) == (0.35, 0.10, None, False)
    assert s["S1"] == replace(base, name="S1", mu_rho=0.15) and s["S2"] == replace(base, name="S2", mu_rho=0.60)
    assert s["S3"] == replace(base, name="S3", w=0.25) and s["S4"] == replace(base, name="S4", psi_fixed=1.5)
    assert s["S5"] == replace(base, name="S5", decay=True)
    assert (ha.THETA_MIN, ha.W_ROBUST, ha.S_ROBUST, ha.ETA_SD, ha.HALF_LIFE_S5) == (0.25, 0.10, 1.5, 0.02, 3.0)
    assert ha.PRIORS == {"mu_rho_sd": 1.0, "sigma_rho": 1.0, "mu_A": (0.3, 0.3), "tau_A": 0.5, "psi_excess": 0.25}
    assert ha.EDGE_MASS_MAX == 0.01


def test_the_grid_is_fixed_and_is_that_of_appendix_b():
    assert ha.MU_A_GRID.size == 121 and ha.MU_A_GRID[0] == pytest.approx(-0.9) and ha.MU_A_GRID[-1] == pytest.approx(1.5)
    assert np.allclose(np.diff(ha.MU_A_GRID), 0.02)
    assert ha.TAU_A_GRID.size == 10 and np.allclose(ha.TAU_A_GRID, 0.5 * norm.ppf(0.5 + (np.arange(10) + 0.5) / 20))
    assert np.allclose(ha.PSI_GRID, 1 + 0.25 * norm.ppf(0.5 + np.array([1, 3, 5]) / 12))
    assert np.allclose(ha.RHO_GRID, 0.025 + 0.05 * np.arange(20))
    assert ha.MU_RHO_Z.size == 9 and ha.SIGMA_RHO_GRID.size == 5 and ha.NU_GRID.size == 7
    assert np.exp(ha.NU_LOGW).sum() == pytest.approx(1.0) and np.exp(ha.NU_LOGW) @ ha.NU_GRID**2 == pytest.approx(1.0)
    lq, lph = ha.rho_prior(0.35)                                    # each node's prior over the 20 cells sums to one
    assert lq.shape == (45, 20) and np.allclose(np.exp(lq).sum(axis=1), 1.0) and np.exp(lph).sum() == pytest.approx(1.0)
    mid = np.exp(lq[np.argmin(np.abs(ha.SIGMA_RHO_GRID[np.arange(45) % 5] - ha.SIGMA_RHO_GRID[2]) + np.abs(np.arange(45) // 5 - 4))])
    assert ha.RHO_GRID[np.argmax(mid)] == pytest.approx(0.325)      # the central node peaks at the cell holding 0.35


@reads_hand_edited_file
def test_the_protocol_states_the_grid_and_the_constants_the_code_uses():
    text = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    appendix = text[text.index("The grid on which section 7 integrates the hyperparameters"):]
    for needle in ("121: from −0.9 to 1.5 in steps of 0.02", f"({ha.TAU_A_GRID[0]:.3f} to {ha.TAU_A_GRID[-1]:.3f})",
                   "(" + ", ".join(f"{x:.3f}" for x in ha.PSI_GRID) + ")", "S4: the single value 1.5",
                   "20: the midpoints 0.025, 0.075, ..., 0.975", "9: the quantiles of its prior",
                   "5: the quantiles of half-Normal(1)",
                   "7: the Gauss-Hermite nodes 0, " + ", ".join(f"±{x:.3f}" for x in ha.NU_GRID[4:]),
                   "at most 1% of the posterior mass of `μ_A`", "`e^−18`", "`10^−10`", "200 per family and model"):
        assert needle in appendix, needle
    assert (ha.PRUNE_LOG, ha.CELL_MIN) == (18.0, 1e-10)
    section = text[text.index("### 7.1 The model"):text.index("### 7.2 The design decisions")]
    for needle in ("Normal(logit 0.35, 1)", "half-Normal(1)", "Normal(0.3, 0.3²)", "half-Normal(0.5)",
                   "1 + half-Normal(0.25)", "0.10, 1.5 (constants)", "Normal(0, 0.02²)", "θ_min = 0.25"):
        assert needle in section, needle


def test_decay_factors_for_s5():
    avg, now = ha.decay_factors(np.array([0.0, 3.0, 6.0]))
    assert now == pytest.approx([1.0, 0.5, 0.25])
    assert avg[0] == 1.0 and avg[1] == pytest.approx(0.5 / math.log(2)) and avg[2] == pytest.approx(0.75 / (2 * math.log(2)))


# ------------------------------------------------------------------ the closed form

@pytest.mark.parametrize("case", [dict(y_H=0.9, s_H=0.4, y_F=0.5, s_F=0.5), dict(y_H=1.4, s_H=0.3, y_F=-0.2, s_F=0.25),
                                  dict(y_H=None, s_H=None, y_F=0.8, s_F=0.4), dict(y_H=0.7, s_H=0.35, y_F=None, s_F=None)])
def test_one_family_against_brute_force_integration(case):
    """Draw (a, η) from the prior, weight by the likelihood of the family's two estimates, and compare with the
    four-component formula: the likelihood, the mean of θ and Pr(θ ≥ 0.25)."""
    hyp = dict(mu_A=0.1, tau_A=0.2, psi=1.1, rho=0.6, w=0.10, nu=0.7, r_F=0.2)
    got = ha.family_posterior(**case, **hyp)
    rng = np.random.default_rng(11)
    n = 2_000_000
    a = hyp["mu_A"] + np.where(rng.random(n) < hyp["w"], ha.S_ROBUST, hyp["tau_A"]) * rng.standard_normal(n)
    theta = hyp["rho"] * a + np.where(rng.random(n) < hyp["w"], ha.S_ROBUST, ha.ETA_SD) * rng.standard_normal(n)
    logw = np.zeros(n)
    if case["y_H"] is not None:
        logw += norm.logpdf(case["y_H"], a, hyp["psi"] * case["s_H"])
    if case["y_F"] is not None:
        se = hyp["psi"] * case["s_F"]
        logw += norm.logpdf(case["y_F"] - math.sqrt(hyp["r_F"]) * se * hyp["nu"], theta, math.sqrt(1 - hyp["r_F"]) * se)
    wts = np.exp(logw - logw.max())
    assert got["log_lik"] == pytest.approx(logw.max() + math.log(wts.mean()), abs=0.02)
    assert (got["weights"] * got["mean"]).sum() == pytest.approx(wts @ theta / wts.sum(), abs=0.01)
    assert got["pi"] == pytest.approx(wts @ (theta >= ha.THETA_MIN) / wts.sum(), abs=0.01)
    assert got["weights"].sum() == pytest.approx(1.0) and got["weights"].shape == (2, 2)


def test_a_family_with_no_data_is_its_prior():
    got = ha.family_posterior(None, None, None, None, mu_A=0.3, tau_A=0.2, psi=1.0, rho=0.5)
    assert np.allclose(got["weights"], [[0.81, 0.09], [0.09, 0.01]]) and got["log_lik"] == pytest.approx(0.0)
    assert np.allclose(got["mean"], 0.15)                                             # ρ μ_A in every component
    assert got["sd"][0, 0] == pytest.approx(math.sqrt(0.25 * 0.04 + 0.02**2))
    assert got["sd"][1, 1] == pytest.approx(math.sqrt(0.25 * 2.25 + 2.25))


def brute_force(d: ha.Data, spec: ha.Spec):
    """The model of section 7.1 summed over the whole grid, written from the formulas with scipy's normal
    density, without pruning and without the module's own component code."""
    mu, tau, psi = (x.ravel() for x in np.meshgrid(ha.MU_A_GRID, ha.TAU_A_GRID, ha.PSI_GRID, indexing="ij"))
    nu, lnu = (ha.NU_GRID, ha.NU_LOGW) if d.r_F > 0 else (np.zeros(1), np.zeros(1))
    N, G, V, F = mu.size, ha.RHO_GRID.size, nu.size, d.n_f
    lw_a = np.log([1 - spec.w, spec.w])
    L = np.zeros((F, N, G, V))
    pi = np.zeros((F, N, G, V))
    mean = np.zeros((F, N, G, V))
    for f in range(F):
        comp_l, comp_pi, comp_m = [], [], []
        for i, va in enumerate((tau**2, np.full(N, ha.S_ROBUST**2))):
            if d.reserve_weight[f]:
                e = (psi * d.s_H[f]) ** 2
                l_res = norm.logpdf(d.y_H[f], mu, np.sqrt(va + e))
                m_a, c_a = mu + va / (va + e) * (d.y_H[f] - mu), va * e / (va + e)
            else:
                l_res, m_a, c_a = np.zeros(N), mu, va
            for j, u in enumerate((ha.ETA_SD**2, ha.S_ROBUST**2)):
                m0 = ha.RHO_GRID[None, :, None] * m_a[:, None, None] * np.ones((1, 1, V))
                c0 = (ha.RHO_GRID[None, :, None] ** 2 * c_a[:, None, None] + u) * np.ones((1, 1, V))
                lik = l_res[:, None, None] + lw_a[i] + lw_a[j] + np.zeros((N, G, V))
                if d.has_forward[f]:
                    se = (psi * d.s_F[f])[:, None, None]
                    y = d.y_F[f] - math.sqrt(d.r_F) * se * nu[None, None, :]
                    e = (1 - d.r_F) * se**2
                    lik = lik + norm.logpdf(y, m0, np.sqrt(c0 + e))
                    m1, c1 = m0 + c0 / (c0 + e) * (y - m0), c0 * e / (c0 + e)
                else:
                    m1, c1 = m0, c0
                comp_l.append(lik); comp_pi.append(norm.sf((ha.THETA_MIN - m1) / np.sqrt(c1))); comp_m.append(m1)
        comp_l = np.array(comp_l)
        L[f] = logsumexp(comp_l, axis=0)
        post = np.exp(comp_l - L[f])
        pi[f], mean[f] = (post * comp_pi).sum(axis=0), (post * comp_m).sum(axis=0)
    lq, lph = ha.rho_prior(spec.mu_rho)
    classes = np.unique(d.mech)
    Lm = np.array([L[d.mech == c].sum(axis=0) for c in classes])                       # (M, N, G, V)
    A = logsumexp(lq[None, None, :, :, None] + Lm[:, :, None, :, :], axis=3)           # (M, N, H, V)
    T = norm.logpdf(mu, *ha.PRIORS["mu_A"])[:, None, None] + lph[None, :, None] + lnu[None, None, :] + A.sum(axis=0)
    logZ = logsumexp(T)
    out_pi, out_mean = np.zeros(F), np.zeros(F)
    for k, c in enumerate(classes):
        W = np.exp(logsumexp((T - logZ)[:, :, None, :] - A[k][:, :, None, :] + lq[None, :, :, None], axis=1) + Lm[k])
        for f in np.flatnonzero(d.mech == c):
            out_pi[f], out_mean[f] = (W * pi[f]).sum(), (W * mean[f]).sum()
    return out_pi, out_mean, logZ


@pytest.mark.parametrize("spec, r_F", [(ha.SPECS[0], 0.0), (ha.SPECS[0], 0.3), (ha.SPECS[3], 0.3)])
def test_a_fit_is_the_sum_of_the_closed_form_over_the_grid(spec, r_F, monkeypatch):
    monkeypatch.setattr(ha, "MU_A_GRID", ha.MU_A_GRID[::4])                            # a coarser grid keeps this quick
    d = ha.Data(y_H=[0.9, -0.1, 0.3, 1.6, 0.0, 0.5, 0.2], s_H=[0.3, 0.35, 0.4, 0.3, 0.3, 0.35, 0.4],
                y_F=[0.8, 0.1, np.nan, -0.2, 0.3, 0.9, 0.0], s_F=[0.4, 0.5, 1.0, 0.3, 0.6, 0.5, 0.7],
                mech=[0, 0, 1, 1, 0, 1, 0], age=[4, 3, 0, 5, 2, 3, 1],
                channel=["blind"] * 6 + ["adaptive"], r_F=r_F)
    fit = ha.fit(d, spec)
    want_pi, want_mean, logZ = brute_force(d, spec)
    # the fit skips grid nodes and cells that hold almost no posterior weight; with seven families that is the
    # whole difference, and it is far below anything a report shows
    assert np.allclose(fit.pi, want_pi, rtol=0, atol=2e-6)
    assert np.allclose(fit.mean, want_mean, rtol=0, atol=2e-6)
    assert fit.log_evidence == pytest.approx(logZ, abs=1e-6)


def test_nothing_in_a_fit_is_random_and_the_draws_follow_the_closed_form():
    d = make(r_F=0.05)
    a, b = ha.fit_many(d, draws=400, seed=3), ha.fit_many(d, draws=400, seed=3)
    for x, y in zip(a, b):
        assert np.array_equal(x.pi, y.pi) and np.array_equal(x.mean, y.mean) and np.array_equal(x.draws, y.draws)
        assert x.hyper == y.hyper and x.log_evidence == y.log_evidence
    other = ha.fit_many(d, draws=400, seed=4)
    assert np.array_equal(other[0].pi, a[0].pi) and not np.array_equal(other[0].draws, a[0].draws)   # only the draws move
    f = a[0]
    assert f.draws.shape == (400, d.n_f) and f.ok and f.converged and f.edge_mass < 1e-6
    se = np.maximum(f.sd, 0.01) / math.sqrt(400)
    assert np.all(np.abs(f.draws.mean(axis=0) - f.mean) < 4.5 * se)
    assert np.all(np.abs((f.draws >= ha.THETA_MIN).mean(axis=0) - f.pi) < 4.5 * np.sqrt(np.maximum(f.pi * (1 - f.pi), 1e-3) / 400))
    alone = ha.fit(d, ha.SPECS[0])                                    # a model's numbers do not depend on its companions
    assert np.array_equal(alone.pi, f.pi) and np.array_equal(alone.mean, f.mean) and alone.hyper == f.hyper


# ------------------------------------------------------------------ what the model does with evidence

def test_posterior_probability_follows_the_forward_evidence():
    kept, lost = ha.fit(make(forward=1.0)), ha.fit(make(forward=0.0))
    assert kept.pi[:8].mean() > 0.8 and kept.pi[:8].min() > 0.5 and kept.pi[8:].max() < 0.3
    assert lost.pi[:8].mean() < 0.25 and np.all(lost.pi[:8] < kept.pi[:8])           # the forward record contradicts the history
    assert kept.hyper["rho_0"] > 0.6 > 0.35 > lost.hyper["rho_0"]
    young = ha.fit(make(forward=1.0, s_F=1.5, age=0.3))               # the same families with almost no forward record
    assert np.all(young.pi[:8] < kept.pi[:8]) and young.sd[:8].mean() > kept.sd[:8].mean()


def test_the_six_models_order_as_their_priors_say():
    fits = {f.spec: f for f in ha.fit_many(make(n_f=45, n_edge=6, s_F=0.6, age=6.0))}
    edge = slice(0, 6)
    assert fits["S1"].pi[edge].mean() < fits["S0"].pi[edge].mean() < fits["S2"].pi[edge].mean()     # retention prior
    assert fits["S4"].pi[edge].mean() < fits["S0"].pi[edge].mean()                                  # wider standard errors
    assert fits["S5"].mean[edge].mean() < 0.5 * fits["S0"].mean[edge].mean()                        # the edge has halved twice
    assert fits["S4"].hyper["psi"] == pytest.approx(1.5) and 1.0 < fits["S0"].hyper["psi"] < 1.35


def test_selection_is_handled_once_by_shrinkage_towards_the_group():
    rng = np.random.default_rng(5)
    n = 200
    y = 0.4 * rng.standard_normal(n)                                 # two hundred families with no edge at all
    d = ha.Data(y_H=y, s_H=np.full(n, 0.4), y_F=np.full(n, np.nan), s_F=np.ones(n), mech=np.zeros(n, int), age=np.zeros(n))
    fit = ha.fit(d)
    best = int(np.argmax(y))
    assert y[best] > 0.9 and fit.mean[best] < 0.2 and fit.pi[best] < 0.3          # the luckiest of 200 is not believed
    # the same winners handed to the model alone look like a group that all has an edge: everything must enter
    top = np.argsort(-y)[:15]
    alone = ha.fit(ha.Data(y_H=y[top], s_H=np.full(15, 0.4), y_F=np.full(15, np.nan), s_F=np.ones(15),
                           mech=np.zeros(15, int), age=np.zeros(15)))
    assert alone.mean.mean() > 2 * fit.mean[top].mean() and alone.hyper["mu_A"] > 0.5 > 0.1 > abs(fit.hyper["mu_A"])


def test_the_wide_component_lets_a_conflicting_family_keep_its_own_data():
    d = make(n_f=80, n_edge=0, seed=2)
    d.y_H[0], d.y_F[0], d.s_F[0] = 0.0, 1.6, 0.2                      # no history, a long and very good forward record
    d.y_H[1], d.y_F[1], d.s_F[1] = 0.0, 0.5, 0.5                      # a mildly lucky one
    fit = ha.fit(d)
    assert fit.conflict[0] > 0.95 and fit.mean[0] > 1.3 and fit.pi[0] > 0.95
    assert fit.conflict[1] < 0.3 and fit.mean[1] < 0.2
    assert np.median(fit.conflict[2:]) < 0.12                         # the rest stay near the prior weight of 0.10


def test_a_level_shared_by_all_forward_estimates_is_not_read_as_an_edge_when_luck_is_shared():
    rng = np.random.default_rng(8)
    n = 150
    y_H = 0.3 + 0.35 * rng.standard_normal(n)                         # apparent edges at the prior's centre
    y_F = 0.27 + 0.25 * rng.standard_normal(n)                        # and every forward estimate lifted together
    base = dict(y_H=y_H, s_H=np.full(n, 0.35), y_F=y_F, s_F=np.full(n, 0.3), mech=np.arange(n) % 3, age=np.full(n, 3.0))
    alone, shared = ha.fit(ha.Data(**base)), ha.fit(ha.Data(**base, r_F=0.3))
    rho = lambda f: np.mean([f.hyper[f"rho_{k}"] for k in range(3)])
    assert rho(alone) > 0.7 and alone.pi.mean() > 0.4                 # independent families: a persistent common edge
    assert shared.hyper["nu"] > 0.5 and rho(shared) < rho(alone) - 0.15
    assert shared.pi.mean() < 0.75 * alone.pi.mean()
    assert alone.hyper["nu"] == 0.0


def test_the_grid_gate_refuses_data_outside_the_grid():
    n = 40
    d = ha.Data(y_H=np.full(n, 3.0), s_H=np.full(n, 0.2), y_F=np.full(n, np.nan), s_F=np.ones(n),
                mech=np.zeros(n, int), age=np.zeros(n))
    fit = ha.fit(d)
    assert fit.edge_mass > 0.3 and not fit.ok and not fit.converged
    inside = ha.fit(ha.Data(y_H=np.full(n, 0.9), s_H=np.full(n, 0.2), y_F=np.full(n, np.nan), s_F=np.ones(n),
                            mech=np.zeros(n, int), age=np.zeros(n)))
    assert inside.edge_mass < 1e-6 and inside.ok


def test_recovers_a_retention_and_a_mean_apparent_edge_not_drawn_from_its_priors():
    """Criterion C-13: apparent edges uniform on (−0.3, 0.9), three classes that keep 0.2, 0.5 and 0.9 of them."""
    rng = np.random.default_rng(13)
    n, rho = 600, np.array([0.2, 0.5, 0.9])
    mech = np.arange(n) % 3
    a = rng.uniform(-0.3, 0.9, n)
    d = ha.Data(y_H=a + 0.15 * rng.standard_normal(n), s_H=np.full(n, 0.15),
                y_F=rho[mech] * a + 0.15 * rng.standard_normal(n), s_F=np.full(n, 0.15), mech=mech, age=np.full(n, 5.0))
    fit = ha.fit(d)
    assert fit.ok and fit.hyper["mu_A"] == pytest.approx(0.3, abs=0.04)
    assert [fit.hyper[f"rho_{k}"] for k in range(3)] == pytest.approx(list(rho), abs=0.08)
    theta = rho[mech] * a
    assert np.mean(np.abs(fit.mean - theta)) < 0.08 and np.corrcoef(fit.mean, theta)[0, 1] > 0.9
    hit = np.abs(fit.mean - theta) <= 1.96 * fit.sd
    assert 0.88 <= hit.mean() <= 0.999                                # its 95% intervals cover the truth about that often


def test_inputs_are_checked():
    ok = dict(y_H=[0.1, 0.2], s_H=[0.3, 0.3], y_F=[0.1, np.nan], s_F=[0.4, 1.0], mech=[0, 0], age=[1.0, 0.0])
    ha.Data(**ok)
    with pytest.raises(ValueError, match="unknown channel"):
        ha.Data(**ok, channel=["blind", "open"])
    with pytest.raises(ValueError, match="r_F"):
        ha.Data(**ok, r_F=1.0)
    with pytest.raises(ValueError, match="one entry per family"):
        ha.Data(**{**ok, "s_H": [0.3]})
    with pytest.raises(ValueError, match="finite value and a positive standard error"):
        ha.Data(**{**ok, "y_H": [np.nan, 0.2]})
    with pytest.raises(ValueError, match="forward estimate needs"):
        ha.Data(**{**ok, "s_F": [0.0, 1.0]})
