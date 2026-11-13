"""The two-group candidate for D08 (``manhattan/stats/hier_spike.py``): a development file, adopted nowhere.

With the edge share fixed at 1 it must be the analytic model of Protocol v3.1 section 7 itself; with a share to
learn it must behave as a mixture; and no run of record may use it. Synthetic numbers only.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from manhattan.sim import run
from manhattan.stats import hier_analytic as ha
from manhattan.stats import hier_spike as hs


@pytest.fixture
def coarse(monkeypatch):
    monkeypatch.setattr(ha, "MU_A_GRID", ha.MU_A_GRID[::4])            # these tests are about the algebra, not the grid
    return ha


def synthetic(n=60, share=0.4, seed=5, rho=0.6, r_F=0.1, forward=True) -> tuple[ha.Data, np.ndarray]:
    """Families from the two-group model itself: a slab with retention ``rho`` and a spike at zero."""
    rng = np.random.default_rng(seed)
    a = 0.6 + 0.3 * rng.standard_normal(n)
    slab = rng.random(n) < share
    theta = np.where(slab, rho * a, 0.0) + 0.02 * rng.standard_normal(n)
    s_H = np.full(n, 0.38)
    years = rng.uniform(0.5, 9.0, n)
    s_F = 1.0 / np.sqrt(years)
    y_F = theta + s_F * rng.standard_normal(n)
    if not forward:
        y_F = np.full(n, np.nan)
    else:
        y_F[:5] = np.nan                                               # a few families with no forward record yet
    data = ha.Data(y_H=a + s_H * rng.standard_normal(n), s_H=s_H, y_F=y_F, s_F=s_F, mech=rng.integers(0, 3, n),
                   age=years, r_F=r_F)
    return data, slab


def test_a_share_fixed_at_1_is_the_analytic_model_number_for_number(coarse):
    """All six models, with a common shock, missing forward records and an adaptive-channel family."""
    data, _ = synthetic()
    data.channel[7] = "adaptive"
    one = hs.fit_many(data, share_grid=[1.0])
    ref = ha.fit_many(data)
    for a, b in zip(one, ref):
        assert a.spec == b.spec and a.ok == b.ok and a.grid_points == b.grid_points
        assert a.log_evidence == pytest.approx(b.log_evidence, rel=0, abs=1e-9)
        for name in ("pi", "mean", "sd", "conflict"):
            np.testing.assert_allclose(getattr(a, name), getattr(b, name), rtol=1e-10, atol=1e-12, err_msg=f"{a.spec} {name}")
        assert a.edge_mass == pytest.approx(b.edge_mass, abs=1e-12)
        for k, v in b.hyper.items():
            assert a.hyper[k] == pytest.approx(v, abs=1e-10), (a.spec, k)
        assert a.slab == pytest.approx(np.ones(data.n_f), abs=1e-12) and a.hyper["share"] == pytest.approx(1.0)
        assert a.share_post == pytest.approx([1.0])
    # and with no common shock and no forward record at all
    for kw in ({"r_F": 0.0}, {"forward": False}):
        d2, _ = synthetic(**kw)
        a, b = hs.fit(d2, share_grid=[1.0]), ha.fit(d2)
        np.testing.assert_allclose(a.pi, b.pi, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(a.mean, b.mean, rtol=1e-10, atol=1e-12)


def test_the_share_has_a_uniform_prior_on_ten_nodes_and_the_spike_adds_no_constant():
    assert hs.SHARE_GRID.tolist() == pytest.approx([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95])
    with pytest.raises(ValueError):
        hs.fit(synthetic(8)[0], share_grid=[0.0, 0.5])
    # the spike is the slab's own formula at retention 0, narrow η: mean 0, variance 0.02² before the forward record
    d = ha.Data(y_H=[0.9], s_H=[0.3], y_F=[np.nan], s_F=[1.0], mech=[0], age=[0.0])
    ll, m, c = hs._spike_components(d, np.arange(1), 0.3, 0.2, 1.0, 0.0, np.ones(1), np.ones(1))
    assert np.allclose(m, 0.0) and np.allclose(c, ha.ETA_SD**2)
    want = [norm.logpdf(0.9, 0.3, np.sqrt(v + 0.3**2)) for v in (0.2**2, ha.S_ROBUST**2)]       # the reserve term alone
    assert np.allclose(ll[0], want)
    # with a forward record: the estimate is centred at 0 with variance 0.02² + its own sampling variance
    d = ha.Data(y_H=[0.9], s_H=[0.3], y_F=[0.4], s_F=[0.5], mech=[0], age=[4.0])
    ll, m, c = hs._spike_components(d, np.arange(1), 0.3, 0.2, 1.0, 0.0, np.ones(1), np.ones(1))
    assert np.allclose(ll[0] - want, norm.logpdf(0.4, 0.0, np.sqrt(ha.ETA_SD**2 + 0.25)))
    assert np.all(np.abs(m) < 0.001) and np.all(c < ha.ETA_SD**2)


def test_with_no_forward_record_the_data_say_nothing_about_the_share(coarse):
    """Both groups have the same reserve term, so the share's posterior is its prior and every family's slab
    probability is the prior mean of the share."""
    data, _ = synthetic(40, forward=False)
    f = hs.fit(data)
    assert f.share_post == pytest.approx(np.full(10, 0.1), abs=1e-9)
    assert np.ptp(f.share_loglik) < 1e-8 and f.slab == pytest.approx(np.full(40, 0.5), abs=1e-9)


def test_a_family_with_a_clear_forward_edge_is_put_in_the_slab_and_a_flat_one_in_the_spike(coarse):
    n = 80
    rng = np.random.default_rng(11)
    slab = np.arange(n) < 30
    y_F = np.where(slab, 0.9, 0.0) + 0.1 * rng.standard_normal(n)       # long, clean forward records
    data = ha.Data(y_H=0.9 + 0.2 * rng.standard_normal(n), s_H=np.full(n, 0.2), y_F=y_F, s_F=np.full(n, 0.1),
                   mech=np.zeros(n, int), age=np.full(n, 8.0))
    f = hs.fit(data)
    assert f.slab[slab].min() > 0.95 and f.slab[~slab].max() < 0.05
    assert f.pi[slab].min() > 0.95 and f.pi[~slab].max() < 0.05
    assert abs(f.share_mean - 30 / 80) < 0.08 and f.share_sd < 0.08     # here the data do identify the share
    one = ha.fit(data)                                                  # the one-hump model spreads the spike families out
    assert f.sd[~slab].mean() < one.sd[~slab].mean()


def test_no_run_of_record_uses_the_candidate():
    lists = run.CODE_FILES + run.CODE_FILES_HB + run.CODE_FILES_V2 + run.CODE_FILES_V2_HB
    assert "manhattan/stats/hier_spike.py" not in lists
    src = (run.prereg.ROOT / "manhattan/sim/hb_v2.py").read_text(encoding="utf-8")
    assert "hier_spike" not in src
