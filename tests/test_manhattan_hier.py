"""The hierarchical model (manhattan/stats/hier.py) and the HB pipeline (manhattan/sim/hb.py): criterion C-13 of
docs/manhattan/MANHATTAN_PROGRESS.md, against docs/manhattan/PROTOCOL_v3.md section 7. Synthetic data only.

The fits need numpyro (requirements-manhattan.txt). Where it is not installed (the existing workflows install
requirements.txt only) those tests skip; the tests of the model's definition still run.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pytest
from scipy import stats as st

from manhattan.sim import criteria, hb, metrics, pipeline, world
from manhattan.stats import hier

from manhattan.testing import prereg_or_skip

os.environ.setdefault("XLA_FLAGS", "--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1")
SHA = prereg_or_skip()          # the HB pipeline's seeds descend from the frozen pre-registration


# ------------------------------------------------------------------ the model's definition (no sampler needed)

def test_the_six_models_differ_only_as_section_7_2e_says():
    s = {x.name: x for x in hier.SPECS}
    assert list(s) == ["S0", "S1", "S2", "S3", "S4", "S5"]
    base = s["S0"]
    assert (base.mu_rho, base.w, base.diagonal, base.psi_fixed, base.decay) == (0.35, 0.10, False, None, False)
    from dataclasses import replace
    assert s["S1"] == replace(base, name="S1", mu_rho=0.15)
    assert s["S2"] == replace(base, name="S2", mu_rho=0.60)
    assert s["S3"] == replace(base, name="S3", w=0.25)
    assert s["S4"] == replace(base, name="S4", diagonal=True, psi_fixed=1.5)
    assert s["S5"] == replace(base, name="S5", decay=True)
    assert (hier.THETA_MIN, hier.W_ROBUST, hier.S_ROBUST, hier.DELTA_SD) == (0.25, 0.10, 1.5, 0.02)
    assert (hier.RHAT_MAX, hier.ESS_MIN, hier.HALF_LIFE_S5) == (1.01, 400, 3.0)
    assert hier.PRIORS == {"mu_rho_sd": 1.0, "sigma_rho": 1.0, "phi": (2.0, 0.1), "mu_A": (0.3, 0.3), "tau_A": 0.5,
                           "sigma_dom": 0.3, "psi_excess": 0.25}


def test_decay_factors_for_s5():
    avg, now = hier.decay_factors(np.array([0.0, 3.0, 6.0]))
    assert now == pytest.approx([1.0, 0.5, 0.25])
    assert avg[0] == 1.0 and avg[1] == pytest.approx(0.5 / math.log(2)) and avg[2] == pytest.approx(0.75 / (2 * math.log(2)))
    t = np.linspace(0, 3, 30001)
    assert avg[1] == pytest.approx(np.mean(2 ** (-t / 3)), rel=1e-4)       # the average of 2^(−t/3) over the record


@pytest.mark.parametrize("w", [0.10, 0.25])
def test_quantile_tables_are_the_mixtures_of_section_7_1(w):
    z = np.array([-3.0, -1.9, -1.0, -0.2, 0.0, 0.7, 1.7, 2.5])
    q = hier.mixture_quantile(z, hier.DELTA_SD, w)
    assert np.allclose(hier.mixture_cdf(q, hier.DELTA_SD, w), st.norm.cdf(z), atol=1e-12)     # Q inverts the mixture CDF
    assert np.allclose(q, -hier.mixture_quantile(-z, hier.DELTA_SD, w))
    assert np.allclose(hier.delta_from_z(z, w), q, rtol=2e-3, atol=1e-5)                     # the table interpolates it
    for tau in (0.05, 0.31, 1.2):
        qa = hier.mixture_quantile(z, tau, w)
        assert np.allclose(hier.mixture_cdf(qa, tau, w), st.norm.cdf(z), atol=1e-12)
        assert np.allclose(hier.a_from_z(z, tau, w), qa, rtol=5e-3, atol=2e-4)
    # draws made through the table have the mixture's distribution
    rng = np.random.default_rng(0)
    n = 300_000
    d = hier.delta_from_z(rng.standard_normal(n), w)
    slab = rng.random(n) < w
    ref = np.where(slab, hier.S_ROBUST * rng.standard_t(3, n), rng.normal(0, hier.DELTA_SD, n))
    assert st.ks_2samp(d, ref).pvalue > 0.001
    assert np.mean(np.abs(d) > 0.1) == pytest.approx(np.mean(np.abs(ref) > 0.1), abs=0.004)


def test_retention_coordinates_are_the_beta_prior():
    """logit ρ = loc + scale·z with density al·log σ(x) + be·log σ(−x) − log B: the Beta density with its Jacobian."""
    from scipy.special import betaln, digamma, expit, log_expit, polygamma
    for al, be in ((0.7, 1.3), (7.0, 13.0), (0.2, 0.2)):
        x = np.linspace(-12, 12, 2001)
        rho = expit(x)
        want = st.beta.logpdf(rho, al, be) + np.log(rho) + np.log1p(-rho)          # density of x = logit ρ
        got = al * log_expit(x) + be * log_expit(-x) - betaln(al, be)
        assert np.allclose(got, want, atol=1e-8)
        loc, scale = digamma(al) - digamma(be), math.sqrt(polygamma(1, al) + polygamma(1, be))
        if al < 0.5:
            continue                                   # draws this close to 0 and 1 round to them in floating point
        r = st.beta.rvs(al, be, size=200_000, random_state=1)
        zs = (np.log(r) - np.log1p(-r) - loc) / scale
        assert abs(zs.mean()) < 0.02 and zs.std() == pytest.approx(1.0, abs=0.02)   # z is standardised under the prior


# ------------------------------------------------------------------ estimates and covariances (no sampler needed)

def test_sharpe_and_its_bootstrap_standard_error():
    rng = np.random.default_rng(2)
    x = rng.standard_normal((6, 1750)) + 0.05
    s = hb.sharpe(x)
    assert s[0] == pytest.approx(x[0].mean() / x[0].std() * math.sqrt(252))
    se = hb.sharpe_se(x, np.random.default_rng(3))
    assert np.allclose(se, math.sqrt(252 / 1750), rtol=0.25)             # close to the i.i.d. value 1/sqrt(years)


def test_overlap_correlation_scales_with_common_dates_and_shrinks_half_way():
    rng = np.random.default_rng(4)
    n = 4000
    base = rng.standard_normal(n + 2000)
    a = base[:n] + 0.0
    b = 0.8 * base[:n] + 0.6 * rng.standard_normal(n)                    # correlation 0.8, same dates
    c = 0.8 * base[2000 : 2000 + n] + 0.6 * rng.standard_normal(n)       # correlation 0.8 on the common half
    d = rng.standard_normal(n)
    C = hb.overlap_correlation([a, b, c, d], [0, 0, 2000, 6000], 10_000)
    assert np.allclose(np.diag(C), 1.0) and np.allclose(C, C.T)
    assert C[0, 1] == pytest.approx(0.5 * 0.8, abs=0.02)                 # full overlap: 0.8, shrunk half-way
    assert C[0, 2] == pytest.approx(0.5 * 0.8 * 0.5, abs=0.02)           # half the dates in common
    assert C[0, 3] == 0.0 and C[2, 3] == 0.0                             # no common dates
    assert np.linalg.eigvalsh(C).min() > 0.4


def test_hb_metrics_from_made_up_replications(monkeypatch):
    def review(ok=True):
        r = {"converged": [ok] * 6, "rhat_max": [1.004] * 6, "ess_min": [900.0] * 6, "divergences": [0] * 6,
             "fit_seconds": [10.0] * 6, "n_live": 100, "review_ok": ok}
        if ok:
            r.update({"n_eval": 100, "n_edge": 10, "pimin80_n": 5, "pimin80_true": 4, "pimin40_n": 12, "pimin40_true": 6,
                      "cal_n": [80, 5, 3, 2, 2, 2, 1, 1, 2, 2], "cal_true": [2, 1, 1, 1, 1, 1, 1, 1, 2, 2],
                      "cal_p": [4.0, 0.75, 0.75, 0.7, 0.9, 1.1, 0.65, 0.75, 1.7, 1.9]})
            for c in ("i", "ii"):
                for g in ("prom", "supp"):
                    r.update({f"m9_{g}_{c}_n": 6, f"m9_{g}_{c}_model": -0.3, f"m9_{g}_{c}_naive": 3.0})
        return r

    def rep(ok=True):
        r = {"sampler": [1000, 1000], "eval_years": [2, 4, 7, 10], "seconds": 100.0,
             "reviews": {str(y): review(ok) for y in (2, 4, 7, 10)}}
        for c in ("i", "ii"):
            r.update({f"m8_den_{c}": 10, f"m8_num_{c}": 1, f"screened_{c}": 2, f"end_promising_{c}": 3,
                      f"end_supported_{c}": 1, f"end_dormant_{c}": 50})
        return r

    reps = [rep() for _ in range(50)] + [rep(ok=False) for _ in range(10)]
    rows = {r.what: r for r in metrics.summarise_hb(reps, "D01")}
    conv = rows["year 4: reviews with all six fits converged"]
    assert conv.estimate == pytest.approx(50 / 60) and "50 of 60" in conv.verdict
    share = rows["year 4: share with a true edge among families with Π^min ≥ 0.8 (250 family observations)"]
    assert share.estimate == pytest.approx(0.8) and share.criterion == "V6" and share.threshold == "lower bound ≥ 0.7"
    assert share.verdict.startswith("pilot: not decided")                 # 60 replications is not 400
    y2 = rows["year 2: share with a true edge among families with Π^min ≥ 0.8 (250 family observations)"]
    assert y2.criterion == "" and y2.verdict == "reported"                # V6 is at years 4 and 10
    ece = rows["year 10: expected calibration error of the central model"]
    n = np.array([80, 5, 3, 2, 2, 2, 1, 1, 2, 2]) * 50
    assert list(n >= 200) == [True, True] + [False] * 8                   # only two bins have 200 observations
    assert ece.estimate == pytest.approx((abs(4.0 - 2) + abs(0.75 - 1)) * 50 / (4000 + 250))
    high = rows["year 4: share of family evaluations with Π^min ≥ 0.80 (no edges exist)"]
    assert high.estimate == pytest.approx(0.05) and high.threshold == "upper bound ≤ 0.01"
    bias = rows["year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (300 obs.)"]
    assert bias.estimate == pytest.approx(-0.05) and bias.criterion == "V8"
    assert rows["year 4: bias of the naive estimate, Promising or higher, candidate (i)"].estimate == pytest.approx(0.5)
    elim = rows["premature elimination: families with a true edge that end dormant, candidate (i)"]
    assert elim.estimate == pytest.approx(0.1) and elim.threshold == "upper bound ≤ 0.1"
    monkeypatch.setitem(criteria.REPLICATIONS, "HB", 60)
    full = {r.what: r for r in metrics.summarise_hb(reps, "D01")}
    assert full[share.what].verdict == "pass"                              # lower bound 0.8 ≥ 0.7
    assert full[high.what].verdict == "FAIL"                               # 5% of evaluations above 0.80 where no edge exists
    reduced = [dict(rep(), sampler=[100, 100]) for _ in range(60)]
    row = [r for r in metrics.summarise_hb(reduced, "D01") if r.what.startswith("year 4: share with a true edge")][0]
    assert row.verdict.startswith("pilot")                                 # a smaller sampler setting is a pilot


# ------------------------------------------------------------------ fits (need numpyro)

def toy(n_f=18, seed=0, forward=1.0, se_H=0.15, se_F=0.2):
    """Families 0..5 have a historical edge of 1.2; their forward record shows ``forward`` times that edge."""
    rng = np.random.default_rng(seed)
    H = 2
    fam = np.repeat(np.arange(n_f), H)
    A = np.where(np.arange(n_f) < 6, 1.2, 0.0)
    a_hat = A[fam] + se_H * rng.standard_normal(n_f * H)
    th_hat = forward * A[fam] + se_F * rng.standard_normal(n_f * H)
    return hier.Data(a_hat=a_hat, cov_H=np.eye(n_f * H) * se_H**2, fam=fam, mech=np.arange(n_f) % 3,
                     fwd=np.arange(n_f * H), theta_hat=th_hat, cov_F=np.eye(n_f * H) * se_F**2, age=np.full(n_f, 3.0))


@pytest.fixture(scope="module")
def fits():
    pytest.importorskip("numpyro")
    kw = dict(warmup=200, samples=200)
    return {"kept": hier.fit(toy(forward=1.0), hier.SPECS[0], 1, keep_draws=50, **kw),
            "lost": hier.fit(toy(forward=0.0), hier.SPECS[0], 1, **kw),
            "decay": hier.fit(toy(forward=1.0), hier.SPECS[5], 1, **kw)}


def test_posterior_probability_follows_the_forward_evidence(fits):
    kept, lost = fits["kept"], fits["lost"]
    assert kept.pi.shape == (18,) and kept.mean.shape == (18,) and kept.draws.shape == (50, 18)
    assert kept.pi[:6].min() > 0.9                    # history and forward record agree on an edge of 1.2
    assert kept.pi[6:].max() < 0.1                    # nothing in either
    # the forward record contradicts the history: Π falls for every one of them, and is low on average
    assert np.all(lost.pi[:6] < kept.pi[:6] - 0.3) and lost.pi[:6].mean() < 0.25 and lost.pi[:6].max() < 0.6
    assert np.all(kept.mean[:6] > 0.7) and np.all(np.abs(kept.mean[6:]) < 0.2)
    assert kept.hyper["mu_A"] < 0.9 and 0.0 < kept.hyper["tau_A"]
    # Π under forward decay is about the edge now (three years in, half of it is gone), so it is lower
    assert fits["decay"].mean[:6].mean() < kept.mean[:6].mean() - 0.2


def test_convergence_gate(fits):
    pytest.importorskip("numpyro")
    kept = fits["kept"]
    assert kept.divergences >= 0 and kept.rhat_max > 0.9 and kept.ess_min > 0
    assert kept.converged == (kept.rhat_max <= 1.01 and kept.ess_min >= 400 and kept.divergences == 0)
    short = hier.fit(toy(), hier.SPECS[0], 2, warmup=20, samples=20)
    assert not short.converged                         # 80 draws cannot give an effective sample size of 400


def tiny_hb(monkeypatch, specs):
    monkeypatch.setitem(world.SIZES, "HB", world.Size("HB", 3, 3, 3, 2, 3, 4, 6))
    monkeypatch.setenv("MANHATTAN_SIM_SAMPLER", "25,25")
    monkeypatch.setenv("MANHATTAN_SIM_EVAL_YEARS", "4,10" if len(specs) == 6 else "10")
    monkeypatch.setattr(hier, "SPECS", specs)
    r = hb.run_replication("D10", 0)
    years = {"4", "10"} if len(specs) == 6 else {"10"}
    assert r["n_families"] == 9 and r["sampler"] == [25, 25] and set(r["reviews"]) == years
    for rev in r["reviews"].values():
        assert len(rev["converged"]) == len(specs) and rev["n_live"] >= 3 and not rev["review_ok"]
        assert "pimin80_n" not in rev                   # a review that is not converged reports no Π
    for c in pipeline.CANDIDATES:
        # nothing converged, so no family was promoted by the model and none was made dormant
        assert r[f"end_supported_{c}"] == 0 and r[f"end_dormant_{c}"] == 0
        assert r[f"end_promising_{c}"] == r[f"screened_{c}"] and r[f"m8_num_{c}"] == 0
    again = hb.run_replication("D10", 0)
    assert again["reviews"]["10"]["rhat_max"] == r["reviews"]["10"]["rhat_max"]     # reproducible, cache or not


def test_hb_replication_end_to_end_with_a_tiny_programme(monkeypatch):
    """The whole HB pipeline on a 9-family programme, with two of the six models to keep compilation short."""
    pytest.importorskip("numpyro")
    tiny_hb(monkeypatch, (hier.SPECS[0], hier.SPECS[5]))


@pytest.mark.skipif(os.environ.get("MANHATTAN_SLOW_TESTS") != "1", reason="slow (compiles all six models twice): set MANHATTAN_SLOW_TESTS=1")
def test_hb_replication_end_to_end_with_all_six_models(monkeypatch):
    pytest.importorskip("numpyro")
    tiny_hb(monkeypatch, hier.SPECS)
