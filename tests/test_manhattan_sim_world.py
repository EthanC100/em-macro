"""The simulated world, its seeds and the run log (manhattan/sim/): criteria C-02 and C-04 of
docs/manhattan/MANHATTAN_PROGRESS.md, against docs/manhattan/SIM_PREREG.md sections 2, 3.1, 8 and 9.
Synthetic data only.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from manhattan import prereg
from manhattan.sim import pipeline, runlog, seeds, world

SHA = seeds.prereg_hash()


def streams(scenario="D01", size="STD", rep=0, branch=0):
    return seeds.Streams(SHA, branch, scenario, size, rep)


# ------------------------------------------------------------------ C-02 seeds

def test_master_seed_is_the_first_eight_bytes_of_the_preregistration_hash():
    assert SHA == prereg.read_record(prereg.RECORDS[0])[0][0]
    assert seeds.master_seed(SHA) == int(SHA[:16], 16)
    assert seeds.master_seed("00000000000000ff" + "0" * 48) == 255


def test_streams_are_reproducible_and_distinct():
    a = streams().rng(seeds.COMMON).standard_normal(5)
    assert np.array_equal(a, streams().rng(seeds.COMMON).standard_normal(5))
    others = [streams(rep=1), streams(scenario="D02"), streams(size="LONG"), streams(branch=1)]
    for o in others:
        assert not np.array_equal(a, o.rng(seeds.COMMON).standard_normal(5))
    assert not np.array_equal(a, streams().rng(seeds.FAMILY_NOISE, 0, 0).standard_normal(5))
    assert seeds.scenario_key("D01") != seeds.scenario_key("D02")
    assert seeds.confirmation_branch(2) == 2 and seeds.confirmation_branch(2, pooled_rerun=True) == 12
    with pytest.raises(ValueError):
        seeds.confirmation_branch(4)


def test_heldout_generator_is_seeded_from_the_stated_text():
    import hashlib
    want = np.random.default_rng(np.random.SeedSequence(int.from_bytes(
        hashlib.sha256(f"manhattan-sim-heldout-2-{SHA}".encode()).digest(), "big"))).random(3)
    assert np.array_equal(seeds.heldout_rng(2, SHA).random(3), want)
    assert not np.array_equal(seeds.heldout_rng(1, SHA).random(3), want)


def test_a_changed_preregistration_stops_the_seeds(tmp_path):
    d = tmp_path / "docs/manhattan"
    d.mkdir(parents=True)
    (d / "SIM_PREREG.md").write_text("edited\n", encoding="utf-8")
    (d / "sim_prereg.sha256").write_text(f"{SHA}  docs/manhattan/SIM_PREREG.md\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not match"):
        seeds.prereg_hash(tmp_path)


# ------------------------------------------------------------------ C-02 run log and the held-out fence

GIT = {"commit": "c0ffee", "dirty": False, "tags": []}


def test_every_run_is_logged_with_the_required_fields(tmp_path):
    log = tmp_path / "runs.jsonl"
    rec = runlog.start(scenario="D01", size="STD", is_heldout=False, confirm=None, label="pilot", reps=range(0, 4),
                       branch=0, path=log, git=GIT)
    runlog.finish(rec, "completed", 4, path=log)
    rows = runlog.read(log)
    assert [r["event"] for r in rows] == ["start", "end"] and rows[1]["status"] == "completed"
    for r in rows:
        for k in runlog.FIELDS:
            assert k in r, k
        assert r["prereg_sha256"] == SHA and r["protocol_sha256"] == runlog.protocol_hash()
        assert r["seeds"]["master"] == seeds.master_seed(SHA) and r["scenario"] == "D01" and r["size"] == "STD"
    assert rows[1]["replications"] == {"first": 0, "requested": 4, "completed": 4}
    bad = runlog.start(scenario="D02", size="STD", is_heldout=False, confirm=None, label="pilot", reps=range(2),
                       branch=0, path=log, git=GIT)
    runlog.finish(bad, "failed", 1, path=log, extra={"reason": "boom"})
    runlog.start(scenario="D03", size="STD", is_heldout=False, confirm=None, label="pilot", reps=range(2),
                 branch=0, path=log, git=GIT)                     # abandoned: a start with no end stays visible
    rows = runlog.read(log)
    assert [r["status"] for r in rows] == ["started", "completed", "started", "failed", "started"]
    with pytest.raises(ValueError):
        runlog.finish(rec, "weakened", 0, path=log)


def test_heldout_is_refused_outside_a_tagged_confirmation_run_and_the_refusal_is_logged(tmp_path):
    log = tmp_path / "runs.jsonl"
    kw = dict(scenario="H01", size="STD", is_heldout=True, label="confirmation", reps=range(3), branch=1, path=log)
    with pytest.raises(runlog.HeldOutRefused, match="only in a confirmation run"):
        runlog.start(confirm=None, git=GIT, **kw)
    with pytest.raises(runlog.HeldOutRefused, match="does not carry the tag"):
        runlog.start(confirm=1, git=GIT, **kw)
    with pytest.raises(runlog.HeldOutRefused, match="does not carry the tag"):
        runlog.start(confirm=1, git={**GIT, "tags": ["manhattan-sim-confirm-2"]}, **kw)
    with pytest.raises(runlog.HeldOutRefused, match="clean working tree"):
        runlog.start(confirm=1, git={"commit": "c0ffee", "dirty": True, "tags": ["manhattan-sim-confirm-1"]}, **kw)
    rows = runlog.read(log)
    assert len(rows) == 4 and all(r["status"] == "refused" and r["reason"] for r in rows)
    ok = runlog.start(confirm=1, git={**GIT, "tags": ["manhattan-sim-confirm-1"]}, **kw)
    assert ok["status"] == "started" and ok["heldout_set"] == 1
    assert world.is_heldout("H08x") and not world.is_heldout("D01")
    assert set(world.HELD_OUT).isdisjoint(world.SCENARIOS)


def test_the_runner_refuses_heldout_and_unregistered_sizes(tmp_path):
    from manhattan.sim import run
    assert run.main(["--scenario", "H03", "--size", "STD", "--reps", "2", "--label", "pilot", "--out", str(tmp_path)]) == 3
    rows = runlog.read(tmp_path / "runs.jsonl")
    assert len(rows) == 1 and rows[0]["status"] == "refused" and rows[0]["scenario"] == "H03"
    with pytest.raises(SystemExit, match="not pre-registered at size"):
        run.run_scenario("D03", "LONG", 2, label="pilot", out=tmp_path)
    with pytest.raises(SystemExit, match="label it pilot"):
        run.run_scenario("D01", "STD", 2, label="full", out=tmp_path)


# ------------------------------------------------------------------ C-04 the world

def test_programme_sizes_windows_and_freeze_days():
    s = world.SIZES
    assert (s["STD"].B, s["STD"].nb_lo, s["STD"].nb_hi, s["STD"].H, s["STD"].m, s["STD"].N, s["STD"].N_F) == (40, 8, 16, 2, 6, 48, 120)
    assert (s["LONG"].B, s["LONG"].nb_lo, s["LONG"].nb_hi, s["LONG"].m, s["LONG"].N, s["LONG"].N_F) == (100, 4, 8, 4, 120, 300)
    assert (s["HB"].B, s["HB"].nb_lo, s["HB"].nb_hi, s["HB"].m, s["HB"].N, s["HB"].N_F) == (24, 10, 10, 4, 29, 60)
    assert s["STD"].N_F_all == 576                                   # 1.2 × the expected number of families
    assert round(1.2 * s["STD"].B) == s["STD"].N and round(1.2 * s["HB"].B) == s["HB"].N
    assert (world.EXPLORE, world.RESERVE, world.T_END, world.YEAR, world.WEEK) == (1260, 1750, 2520, 252, 5)
    for B in (40, 100, 24):
        fz = world.freeze_days(B)
        assert fz[0] == 0 and fz[-1] < world.T_END and np.all(fz % 5 == 0) and np.all(np.diff(fz) > 0)
        assert np.ptp(np.diff(fz)) <= 5                             # equal intervals, to the week
    n_b = world.programme(world.SCENARIOS["D01"], s["STD"], streams())
    assert n_b.shape == (40,) and n_b.min() >= 8 and n_b.max() <= 16
    assert np.all(world.programme(world.SCENARIOS["D01"], s["HB"], streams(size="HB")) == 10)


def test_weights_sum_to_one_and_scenarios_are_as_preregistered():
    sc = world.SCENARIOS
    for s in sc.values():
        assert sum(s.weights) == pytest.approx(1.0), s.id
        assert s.group == "development"
    assert sc["D01"].pi1 == 0 and sc["D02"].pi1 == 0.02 and sc["D10"].pi1 == 0.15
    assert sc["D03"].weights == (0.02, 0.08, 0.85, 0.05) and sc["D03"].m == 20
    assert sc["D04"].weights == (0.40, 0.20, 0.20, 0.20)
    assert sc["D05"].dist == "t3" and sc["D06"].dist == "t5" and sc["D06"].garch
    assert sc["D07a"].ar == 0.2 and sc["D07b"].ar == -0.2
    assert sc["D08"].select_k == 20 and sc["D08"].select_days == world.EXPLORE
    assert sc["D09a"].adaptive == "exploration" and sc["D09b"].adaptive == "reserve"
    assert sc["D10"].theta == ((0.3, 0.7), (2.0, 0.3)) and sc["D10"].null_mean == -0.2
    assert sc["D10"].retention == ((0.0, 0.5), (1.0, 0.5)) and sc["D11"].hedge
    assert [sc[f"P{i}"].theta[0][0] for i in (1, 2, 3, 4)] == [0.5, 1.0, 1.5, 2.5]
    assert all(sc[f"P{i}"].both == 1.0 and sc[f"P{i}"].pi1 == 0.05 for i in (1, 2, 3, 4))
    sizes = {k: v.sizes for k, v in sc.items()}
    assert sizes["D01"] == sizes["D02"] == ("STD", "LONG", "HB") and sizes["D10"] == ("HB",)
    assert sizes["D05"] == sizes["D08"] == ("STD", "HB")
    assert {k for k, v in sc.items() if v.e_all} == {"D01", "D04", "D07a"}
    # the correlations each set of weights implies
    wc, wg, wu, we = world.DEFAULT_WEIGHTS
    assert (wc + wg + wu, wc + wg, wc) == pytest.approx((0.60, 0.30, 0.05))
    assert sum(sc["D03"].weights[:3]) == pytest.approx(0.95)


@pytest.mark.parametrize("dist", ["normal", "t3", "t5"])
def test_noise_has_mean_zero_and_variance_one(dist):
    x = world.noise(np.random.default_rng(1), 400_000, dist)
    assert abs(x.mean()) < 0.02
    if dist == "t3":                                               # infinite fourth moment: check the scaling itself
        raw = np.random.default_rng(1).standard_t(3, 400_000)
        assert np.allclose(x, raw * math.sqrt(1 / 3))
        assert np.median(np.abs(x)) == pytest.approx(0.7649 * math.sqrt(1 / 3), rel=0.02)
    else:
        assert x.var() == pytest.approx(1.0, rel=0.03)


def test_ar1_has_variance_one_and_the_stated_coefficient():
    z = np.random.default_rng(2).standard_normal((4, 200_000))
    for phi in (0.2, -0.2):
        x = world.ar1(z, phi)
        assert x.var() == pytest.approx(1.0, rel=0.02)
        assert np.mean(x[:, 1:] * x[:, :-1]) == pytest.approx(phi, abs=0.01)
        assert np.array_equal(x[:, 0], z[:, 0])
        assert x[0, 1] == pytest.approx(phi * z[0, 0] + math.sqrt(1 - phi**2) * z[0, 1])
    assert world.ar1(z, 0.0) is z


def test_garch_variance_follows_its_recursion_and_has_mean_one():
    z = np.random.default_rng(3).standard_normal((3, 200_000))
    s2 = world.garch_variance(z)
    assert np.all(s2[:, 0] == 1.0)
    t = 1234
    assert np.allclose(s2[:, t], 0.02 + 0.10 * s2[:, t - 1] * z[:, t - 1] ** 2 + 0.88 * s2[:, t - 1])
    assert s2.mean() == pytest.approx(1.0, rel=0.03) and s2.min() > 0 and np.isfinite(s2).all()
    assert np.allclose(world.garch_variance(z[0]), s2[0])             # the one-series path is the same recursion
    f = one_batch("D06")[0]
    assert np.isfinite(f.X).all() and 0.6 < f.mean_sigma < 1.6        # one path's average σ; E[σ²] = 1


def one_batch(scenario, size="STD", rep=0, batches=1, scn=None):
    scn, sz = scn or world.SCENARIOS[scenario], world.SIZES[size]
    out = []
    for b, fz, fams in world.batches(scn, sz, streams(scenario, size, rep)):
        out += fams
        if b + 1 >= batches:
            break
    return out


def first_batches(scenario, reps=3, scn=None):
    """The first batch of several replications: within one batch every family has the same days."""
    return [one_batch(scenario, rep=r, scn=scn) for r in range(reps)]


def pooled_corr(fams):
    """Average correlation between variants of a hypothesis, between hypotheses, and between families."""
    same_h, same_f, other = [], [], []
    for f in fams:
        H, m, _ = f.X.shape
        c = np.corrcoef(f.X.reshape(H * m, -1))
        hyp = np.repeat(np.arange(H), m)
        off = ~np.eye(H * m, dtype=bool)
        same_h.append(c[(hyp[:, None] == hyp[None, :]) & off].mean())
        same_f.append(c[hyp[:, None] != hyp[None, :]].mean())
    for a, b in zip(fams[:-1], fams[1:]):
        other.append(np.corrcoef(a.X.reshape(-1, a.X.shape[2]), b.X.reshape(-1, b.X.shape[2]))[: H * m, H * m :].mean())
    return np.mean(same_h), np.mean(same_f), np.mean(other)


def test_default_correlations_are_060_030_005_and_nulls_have_mean_zero():
    groups = first_batches("D01", reps=4)
    fams = [f for g in groups for f in g]
    assert len(fams) >= 32 and fams[0].X.shape == (2, 6, world.HISTORY + world.T_END)
    cs = np.array([pooled_corr(g) for g in groups]).mean(axis=0)
    assert cs[0] == pytest.approx(0.60, abs=0.015) and cs[1] == pytest.approx(0.30, abs=0.02)
    assert cs[2] == pytest.approx(0.05, abs=0.015)
    X = np.concatenate([f.X.reshape(12, -1) for f in fams])
    assert X.std() == pytest.approx(1.0, rel=0.01)
    # mean 0 within Monte Carlo error: per day, the common term (0.05), the family term and the rest
    se = math.sqrt((0.05 / len(groups) + 0.95 / len(fams)) / X.shape[1])
    assert abs(X.mean()) < 4 * se
    assert all(f.reserve_null and f.forward_null and not f.has_edge and f.true_sharpe_f == 0 for f in fams)
    assert np.all(fams[0].theta == 0) and fams[1].freeze == fams[0].freeze == 0
    later = one_batch("D01", batches=2)[-1]
    assert later.freeze == 60 and later.X.shape[2] == world.HISTORY + world.T_END - 60 and later.n_forward == 2460


@pytest.mark.parametrize("scenario,want", [("D03", (0.95, 0.10, 0.02)), ("D04", (0.80, 0.60, 0.40))])
def test_scenario_correlations(scenario, want):
    ch, cf, co = np.array([pooled_corr(g) for g in first_batches(scenario, reps=3)]).mean(axis=0)
    assert ch == pytest.approx(want[0], abs=0.02) and cf == pytest.approx(want[1], abs=0.03)
    assert co == pytest.approx(want[2], abs=0.03)


def test_edges_follow_the_defaults():
    rng = np.random.default_rng(4)
    scn = world.SCENARIOS["P2"]
    n, has_n, both_n = 4000, 0, 0
    base = world.SCENARIOS["D02"]
    for _ in range(n):
        th, fwd, has = world.draw_edges(rng, base, 2, 6)
        assert np.array_equal(th, fwd)
        if has:
            has_n += 1
            hyp = (th > 0).all(axis=1)
            assert hyp.any() and np.all((th > 0).any(axis=1) == hyp)
            both_n += hyp.all()
            top = th.max(axis=1)[hyp]
            assert np.all(top <= 1.5) and np.all(th[hyp] >= 0.25)       # θ_h · q_v with q_v in (0.5, 1)
        else:
            assert np.all(th == 0)
    assert has_n / n == pytest.approx(0.02, abs=0.008) and 0.2 < both_n / has_n < 0.8
    th, _, has = world.draw_edges(np.random.default_rng(5), world.SCENARIOS["D01"], 2, 6)
    assert not has and np.all(th == 0)
    for _ in range(200):
        th, fwd, has = world.draw_edges(rng, scn, 2, 6)
        if has:
            assert np.all(th >= 0.5) and np.all(th <= 1.0)             # both hypotheses at θ_h = 1.0
    d10 = world.SCENARIOS["D10"]
    seen = set()
    for _ in range(300):
        th, fwd, has = world.draw_edges(rng, d10, 2, 4)
        assert np.all(th[th <= 0] == -0.2) and np.all(fwd[th <= 0] == -0.2)      # nulls keep −0.2 forward
        if has:
            ratio = fwd[th > 0] / th[th > 0]
            assert np.all(ratio == ratio[0]) and ratio[0] in (0.0, 1.0)
            seen.add(float(ratio[0]))
            assert set(np.round(th.max(axis=1)[th.max(axis=1) > 0] / 1.0, 6)) <= set(np.round(th.max(axis=1), 6))
    assert seen == {0.0, 1.0}


def test_truth_labels_follow_section_2_4():
    f = one_batch("P4")[0]
    fam = world.Family(idx=0, batch=0, freeze=0, X=f.X, theta=np.array([[1.0, 0.5], [0.0, 0.0]]),
                       theta_fwd=np.array([[0.0, 0.0], [0.0, 0.0]]), has_edge=True, noise_sd_h=0.8, noise_sd_f=0.7)
    assert not fam.reserve_null and fam.forward_null and fam.true_sharpe_f == 0.0
    fam.theta_fwd = np.array([[1.0, 0.5], [-0.2, -0.2]])
    assert not fam.forward_null                                       # one component with a positive mean is enough
    assert list(fam.component_edges) == pytest.approx([0.75, -0.2, 0.275])
    assert fam.true_sharpe_f == pytest.approx(0.275 / 0.7)
    wc, wg, wu, we = world.DEFAULT_WEIGHTS
    assert f.noise_sd_h == pytest.approx(math.sqrt(wc + wg + wu + we / 6))
    assert f.noise_sd_f == pytest.approx(math.sqrt(wc + wg + wu / 2 + we / 12))
    P = pipeline.components(f.X - f.X.mean(axis=2, keepdims=True))
    assert P[:2].std(axis=1) == pytest.approx([f.noise_sd_h] * 2, rel=0.05) and P[2].std() == pytest.approx(f.noise_sd_f, rel=0.05)


def test_edge_families_have_the_stated_mean():
    fams = [f for f in one_batch("P4", batches=40) if f.has_edge]
    assert fams
    for f in fams[:3]:
        got = f.X.mean(axis=2) * math.sqrt(world.YEAR)                # annualised mean, noise sd 1
        assert np.all(np.abs(got - f.theta) < 4 * math.sqrt(world.YEAR / f.X.shape[2]))
        assert np.all(f.theta >= 1.25) and np.all(f.theta <= 2.5)


def test_selection_picks_the_best_of_twenty_on_the_exploration_window_only():
    """With no true edges anywhere, the best of 20 looks good where it was picked and ordinary everywhere else.
    (In D08 itself 5% of pool draws have an edge, so selection also concentrates real edges: checked last.)"""
    from dataclasses import replace
    no_edge = replace(world.SCENARIOS["D08"], pi1=0.0)

    def sharpe(f, a, b):
        p = pipeline.components(f.X)[2][a:b]
        return float(p.mean() / p.std() * math.sqrt(world.YEAR))

    fams = [f for g in first_batches("D08", reps=12, scn=no_edge) for f in g]
    n = len(fams)
    expl = np.mean([sharpe(f, 0, world.EXPLORE) for f in fams])
    resv = np.mean([sharpe(f, world.EXPLORE, world.HISTORY) for f in fams])
    fwd = np.mean([sharpe(f, world.HISTORY, f.X.shape[2]) for f in fams])
    # E[max of 20 standard normals] is about 1.87; a 5-year Sharpe ratio has standard error about 1/sqrt(5)
    assert expl == pytest.approx(1.87 / math.sqrt(5), abs=0.15)
    for value, years in ((resv, world.RESERVE / world.YEAR), (fwd, 10.0)):
        assert abs(value) < 4 * math.sqrt((0.10 / 12 + 0.90 / n) / years)       # families of a batch share c
    plain = [f for g in first_batches("D01", reps=12) for f in g]
    assert abs(np.mean([sharpe(f, 0, world.EXPLORE) for f in plain])) < 0.2
    picked = [f for g in first_batches("D08", reps=12) for f in g]
    assert np.mean([f.has_edge for f in picked]) > 0.3                  # far above the pool's 5%


def test_adaptive_variants_copy_the_best_and_leave_the_frozen_grid_alone():
    scn = world.SCENARIOS["D09b"]
    with_ad = one_batch("D09b")
    st = streams("D09b")
    without = []
    for b, fz, fams in world.batches(world.without_adaptive(scn), world.SIZES["STD"], st):
        without = fams
        break
    for a, b in zip(with_ad, without):
        assert np.array_equal(a.X, b.X) and b.X_adaptive is None      # bit for bit
        assert a.X_adaptive.shape == (2, 18, a.X.shape[2]) and a.theta_adaptive.shape == (2, 18)
    f = with_ad[0]
    lo, hi = world.EXPLORE, world.HISTORY
    frozen_best = int(np.argmax([x[lo:hi].mean() / x[lo:hi].std() for x in f.X[0]]))
    c = np.corrcoef(f.X[0, frozen_best], f.X_adaptive[0, 0])[0, 1]
    assert c == pytest.approx(0.9, abs=0.02)                          # round 1 copies the best frozen variant
    assert f.X_adaptive.std() == pytest.approx(1.0, rel=0.03)


def test_hedged_world_removes_most_of_the_factor():
    f = one_batch("D11")[0]
    true, got = f.extra["true_X"], f.X
    resid = got[:, :, world.EXPLORE:] - true[:, :, world.EXPLORE:]
    # a three-year window lags a hedge ratio that wanders 0.3 a year: the hedge error is real but well below
    # the unhedged exposure (about 0.5 of a factor with unit daily volatility)
    assert resid.std() < 0.45 and f.extra["beta_error"] < 0.45
    assert np.corrcoef(got[0, 0, world.EXPLORE:], true[0, 0, world.EXPLORE:])[0, 1] > 0.9
    assert np.array_equal(got[:, :, :252], true[:, :, :252] + (got - true)[:, :, :252])
    burn = (got - true)[:, :, :252]                                   # no hedge before 252 days of history
    assert burn.std() > resid.std()
