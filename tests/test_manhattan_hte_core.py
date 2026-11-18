"""Manhattan HTE core: identity, registry, log, store, synthetic data and fence, PIT probe, kernels against their
reference implementations, stage-1 safety properties and the streaming SPA. Synthetic data only."""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from manhattan.hte import data as D
from manhattan.hte import features as F
from manhattan.hte import fixtures as X
from manhattan.hte import ids, kernels, log as L, pit, registry as R, store
from manhattan.hte import templates as TP
from manhattan.hte.policy import Policy
from manhattan.stats import bootstrap, spa as SPA

U = 2.0 ** -53


@pytest.fixture(scope="module")
def panel():
    return D.generate(X.SMALL_PANEL)


def _reg(tmp_path):
    lg = L.AttemptLog(tmp_path / "attempts.jsonl")
    return R.Registry(tmp_path / "registry", lg), lg


# -- a test-only leaky template (reads the next day's return) -------------------------------------------------

def _leaky(cache, dom, p):
    r = cache.panel.returns(dom)
    s = np.zeros_like(r)
    s[:-1] = np.sign(r[1:])                     # position at t uses r[t+1]: look-ahead
    return s


LEAKY = TP.TEMPLATES.setdefault("leaky_test", TP.Template(
    "leaky_test", 1, {"name": "test-leaky", "mechanism": "TEST ONLY", "sign": "+", "density": "dense"},
    {"lookback": ("int", 5, 10)}, lambda p: p["lookback"], _leaky, test_only=True))


# -- identity ---------------------------------------------------------------------------------------------------

def test_canonical_identity_ignores_representation_but_not_content():
    a = R.variant_record("ab" * 32, {"lookback": 5, "entry": 0.5})
    b = R.variant_record("ab" * 32, {"entry": 0.50, "lookback": 5.0})
    c = R.variant_record("ab" * 32, {"entry": 0.5, "lookback": 6})
    assert ids.full_hash(a) == ids.full_hash(b) != ids.full_hash(c)


def test_merkle_array_matches_hex_version():
    rng = np.random.default_rng(0)
    for n in (0, 1, 2, 3, 7, 16):
        d = rng.integers(0, 256, (n, 32), dtype=np.uint8)
        assert ids.merkle_root_array(d) == ids.merkle_root([bytes(r).hex() for r in d])


def test_code_identity_has_engine_digest():
    c = ids.code_identity()
    assert len(c["engine_sha256"]) == 64 and c["numpy"]


# -- registry ---------------------------------------------------------------------------------------------------

def test_registry_counts_levels_and_freezes(tmp_path):
    reg, lg = _reg(tmp_path)
    rep = reg.submit(X.small_bundles())
    assert rep == {"submitted": 10, "registered_specs": 10, "registered_candidates": 120,
                   "duplicate_submissions": 0, "rejected": 0}
    fr = reg.freeze()
    assert fr["counts"]["families"] == 5 and fr["counts"]["hypotheses"] == 10
    assert fr["counts"]["strategy_specs"] == 10 and fr["counts"]["candidates"] == 120
    assert fr["counts"]["variants"] == 60                 # two cost models per variant: never equated
    view = reg.frozen()
    for i in (0, 17, 119):
        assert ids.full_hash(view.canonical_config(i)) == view.candidate_hash(i)


def test_registry_order_independent_of_submission_order(tmp_path):
    b = X.small_bundles()
    r1, _ = _reg(tmp_path / "a")
    r1.submit(b)
    r2, _ = _reg(tmp_path / "b")
    rng = np.random.default_rng(3)
    perm = rng.permutation(len(b))
    r2.submit([b[i] for i in perm[:4]])
    r2.submit([b[i] for i in perm[4:]])
    f1, f2 = r1.freeze(), r2.freeze()
    assert f1["root"] == f2["root"]
    assert np.array_equal(r1.frozen().cand, r2.frozen().cand)


def test_duplicate_submission_registers_nothing_and_is_logged(tmp_path):
    reg, lg = _reg(tmp_path)
    b = X.small_bundles()
    reg.submit(b)
    rep = reg.submit(b[:3] + b[:1])
    assert rep["duplicate_submissions"] == 4 and rep["registered_candidates"] == 0
    assert len(reg) == 120 and len(lg.of_type("duplicate_submission")) == 4


@pytest.mark.parametrize("mutate,expect", [
    (lambda s: s["grid"].update(lookback=[10, 10]), "duplicate values"),
    (lambda s: s["grid"].update(lookback=[1]), "outside"),
    (lambda s: s["grid"].update(lookback=[400]), "outside"),
    (lambda s: s["grid"].update(bogus=[1]), "grid keys"),
    (lambda s: s["grid"].update(shape=["cubic"]), "not one of"),
    (lambda s: s["grid"].update(lookback=[]), "non-empty"),
    (lambda s: s["bindings"].update(cost_model=["c9"]), "bindings.cost_model"),
    (lambda s: s.update(hypothesis="0" * 64), "full hash"),
    (lambda s: s.update(template_version=2), "template version"),
])
def test_invalid_specs_are_rejected_and_logged(tmp_path, mutate, expect):
    reg, lg = _reg(tmp_path)
    b = X.small_bundles(domains=("fx",), templates=("trend",))[0]
    spec = json.loads(json.dumps(b.spec))
    mutate(spec)
    rep = reg.submit([R.Bundle(b.family, b.hypothesis, spec)])
    assert rep["rejected"] == 1 and len(reg) == 0
    rec = lg.of_type("submission_rejected")[-1]["payload"]
    assert any(expect in r for r in rec["reasons"]), rec


def test_registry_is_append_only_and_old_versions_still_verify(tmp_path):
    reg, lg = _reg(tmp_path)
    b = X.small_bundles()
    reg.submit(b[:5])
    v0 = reg.freeze()
    reg.submit(b[5:])
    v1 = reg.freeze()
    assert v1["n_candidates"] > v0["n_candidates"]
    old = reg.frozen(0)
    new = reg.frozen()
    assert old.root == v0["root"] and new.root == v1["root"]
    # every candidate of version 0 is still registered in version 1
    s_old = {bytes(r) for r in old.cand}
    s_new = {bytes(r) for r in new.cand}
    assert s_old <= s_new
    # reload from disk reproduces both
    reg2 = R.Registry(tmp_path / "registry", L.AttemptLog(tmp_path / "attempts.jsonl"))
    assert reg2.frozen(0).root == v0["root"] and reg2.frozen().root == v1["root"]


def test_tampered_registry_segment_is_refused(tmp_path):
    reg, lg = _reg(tmp_path)
    reg.submit(X.small_bundles())
    reg.freeze()
    seg = tmp_path / "registry" / "segment-00000.bin"
    raw = bytearray(seg.read_bytes())
    raw[-5] ^= 0xFF
    seg.write_bytes(bytes(raw))
    reg2 = R.Registry(tmp_path / "registry", L.AttemptLog(tmp_path / "attempts.jsonl"))
    with pytest.raises(store.CorruptFile):
        reg2.frozen()


# -- log and store ----------------------------------------------------------------------------------------------

def test_log_detects_edit_and_suffix_deletion(tmp_path):
    p = tmp_path / "l.jsonl"
    lg = L.AttemptLog(p)
    for i in range(5):
        lg.append("x", {"i": i, "v": 0.1})
    anchor = lg.head()
    L.verify(p, anchor)
    lines = p.read_text().splitlines(keepends=True)
    p.write_text("".join(lines[:3]))
    with pytest.raises(L.LogError, match="suffix"):
        L.verify(p, anchor)
    p.write_text("".join(lines).replace('"i":2', '"i":9'))
    with pytest.raises(L.LogError, match="edited|chain"):
        L.verify(p)


def test_torn_tail_is_quarantined_not_repaired(tmp_path):
    p = tmp_path / "l.jsonl"
    lg = L.AttemptLog(p)
    lg.append("x", {"i": 1})
    with open(p, "ab") as f:
        f.write(b'{"seq":2,"type":"x","pay')
    with pytest.raises(L.LogError, match="torn"):
        L.read(p)
    rec = L.recover_torn_tail(p)
    assert rec["type"] == "torn_tail_quarantined" and rec["payload"]["bytes"] == 24
    assert (tmp_path / "l.jsonl.torn-0").read_bytes().startswith(b'{"seq":2')
    assert len(L.read(p)) == 2


def test_store_round_trip_is_deterministic_and_verified(tmp_path):
    a = {"x": np.arange(6.0).reshape(2, 3), "h": np.zeros((2, 32), np.uint8), "e": np.zeros(0, np.int64)}
    s1 = store.write_arrays(tmp_path / "a.bin", a)
    s2 = store.write_arrays(tmp_path / "b.bin", dict(reversed(list(a.items()))))
    assert s1 == s2
    back = store.read_arrays(tmp_path / "a.bin", s1)
    assert all(np.array_equal(back[k], a[k]) for k in a)
    raw = bytearray((tmp_path / "a.bin").read_bytes())
    raw[-1] ^= 1
    (tmp_path / "a.bin").write_bytes(bytes(raw))
    with pytest.raises(store.CorruptFile):
        store.read_arrays(tmp_path / "a.bin", s1)


# -- synthetic data and the fence ---------------------------------------------------------------------------------

def test_panel_is_deterministic_and_fenced(panel):
    again = D.generate(X.SMALL_PANEL)
    assert again.data_hash == panel.data_hash
    assert D.verify_synthetic(panel) == panel.data_hash
    assert panel.returns("fx").shape[0] == panel.fence == 660
    with pytest.raises(D.ProtectedDataRefused):
        panel.window(0, panel.fence + 1)
    with pytest.raises(D.ProtectedDataRefused):
        panel.protected_tail("fx")
    with pytest.raises(ValueError):
        panel.returns("fx")[0, 0] = 1.0            # read-only


def test_non_synthetic_or_altered_panels_are_refused(panel):
    fake = D.FencedPanel(params=panel.params, data_hash=panel.data_hash, fence=panel.fence, dates=panel.dates,
                         _returns={d: np.array(panel._returns[d]) for d in panel.domains()},
                         _carry=dict(panel._carry), provenance=dict(panel.provenance))
    fake._returns["fx"][5, 0] += 1e-9               # "real data" swapped in under a synthetic label
    with pytest.raises(D.NotSynthetic):
        D.verify_synthetic(fake)
    with pytest.raises(D.NotSynthetic):
        D.verify_synthetic(object())
    other = D.FencedPanel(params=panel.params, data_hash=panel.data_hash, fence=panel.fence, dates=panel.dates,
                          _returns=panel._returns, _carry=panel._carry, provenance={"synthetic": False})
    with pytest.raises(D.NotSynthetic):
        D.verify_synthetic(other)


# -- PIT --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("template", TP.PRODUCTION_TEMPLATES)
def test_production_templates_pass_the_pit_probe(template):
    res = pit.probe(template)
    assert res["passed"], res["failures"]
    assert res["checks"] > 0


def test_leaky_template_fails_probe_and_cannot_register(tmp_path):
    assert not pit.probe("leaky_test")["passed"]
    reg, lg = _reg(tmp_path)
    fam = R.family("leak", "TEST", "+", "dense")
    hyp = R.hypothesis(fam, "fx")
    spec = R.strategy_spec(hyp, "leaky_test", {"lookback": [5, 6]})
    rep = reg.submit([R.Bundle(fam, hyp, spec)])
    assert rep["rejected"] == 1 and len(reg) == 0
    assert lg.of_type("pit_probe")[-1]["payload"]["passed"] is False
    assert "PIT probe" in lg.of_type("submission_rejected")[-1]["payload"]["reasons"][0]


def test_look_ahead_would_be_visible_in_screening_statistics(panel):
    """Why the probe matters: a leaky position on a pure-null synthetic world shows an enormous t-statistic."""
    cache = F.FeatureCache(panel)
    P = TP.positions(cache, "leaky_test", "fx", {"lookback": 5}, "unit_risk")
    Pw, Rw = kernels.align(P, panel.returns("fx"), 300, panel.fence)
    # the leaky row t was built from r[t+1], which is exactly the return align pairs it with
    assert kernels.screen(Pw, Rw, 0.0)["t_stat"] > 20
    honest = TP.positions(cache, "trend", "fx", {"lookback": 20, "shape": "sign", "vol_halflife": 20,
                                                 "rebalance": 1}, "unit_risk")
    Hw, _ = kernels.align(honest, panel.returns("fx"), 300, panel.fence)
    assert abs(kernels.screen(Hw, Rw, 0.0)["t_stat"]) < 6


def test_align_never_reads_at_or_past_the_fence(panel):
    P = np.zeros((panel.fence, 3))
    R_ = np.zeros((panel.fence, 3))
    Pw, Rw = kernels.align(P, R_, 300, panel.fence)
    assert Pw.shape == Rw.shape == (panel.fence - 300, 3)
    with pytest.raises(ValueError):
        kernels.align(P[:-1], R_, 300, panel.fence)


# -- kernels against references -----------------------------------------------------------------------------------

def _gamma(n):
    return n * U / (1 - n * U)


def _random_positions(rng, n, A, kind):
    if kind == "dense":
        return rng.normal(0, 0.01, (n, A))
    if kind == "sparse":
        P = np.where(rng.random((n, A)) < 0.05, rng.choice([-0.01, 0.01], (n, A)), 0.0)
        return P
    if kind == "zero":
        return np.zeros((n, A))
    return np.round(rng.normal(0, 0.01, (n, A)), 3)          # "flicker": very high turnover


@pytest.mark.parametrize("seed", range(12))
def test_screen_matches_reference_within_summation_error(seed):
    rng = np.random.default_rng(seed)
    n, A = int(rng.integers(30, 200)), int(rng.integers(1, 13))
    kind = ["dense", "sparse", "zero", "flicker"][seed % 4]
    Pw = _random_positions(rng, n, A, kind)
    Rw = rng.standard_t(4, (n, A)) * 0.01
    c = float(rng.choice([0.0, 1e-4, 4e-3]))
    v = kernels.screen(Pw, Rw, c)
    r = kernels.ref_screen(Pw, Rw, c)
    for k in ("degenerate", "dominated"):
        assert v[k] == r[k]
    # every vectorised statistic is a sum of at most n*A terms evaluated in a different order: both are within
    # gamma_{nA} * sum|terms| of the exact value, so they differ by at most twice that (Higham, Thm 4.4). The
    # bound is applied with the magnitude of each statistic's terms; ratios inherit the relative error.
    g = 2 * _gamma(n * A + 2)
    scale = {"gross_mean": float((np.abs(Pw * Rw)).sum()) / n,
             "holder_bound": float((np.abs(Pw * Rw)).sum()) / n,
             "lin_cost": c * float(np.abs(np.diff(Pw, axis=0, prepend=0)).sum()) / n,
             "turnover": float(np.abs(np.diff(Pw, axis=0, prepend=0)).sum()) / n,
             "exposure": float(np.abs(Pw).sum()) / n}
    for k, s in scale.items():
        assert abs(v[k] - r[k]) <= g * s + 1e-300, k
    scale_net = scale["gross_mean"] + scale["lin_cost"]
    assert abs(v["net_mean"] - r["net_mean"]) <= 4 * g * scale_net + 1e-300
    for k in ("net_std", "t_stat", "sharpe_ann"):
        assert math.isclose(v[k], r[k], rel_tol=1e-9, abs_tol=1e-12), k
    assert v["active_frac"] == r["active_frac"] and v["hit_rate"] == pytest.approx(r["hit_rate"], abs=1e-12)


@pytest.mark.parametrize("seed", range(40))
def test_dominated_implies_non_positive_net_mean(seed):
    """Property: a stage-1 'dominated' candidate never has a positive stage-2 net mean, whatever the returns."""
    rng = np.random.default_rng(100 + seed)
    n, A = int(rng.integers(20, 300)), int(rng.integers(1, 8))
    Pw = _random_positions(rng, n, A, "flicker" if seed % 2 else "dense")
    Rw = rng.standard_t(3, (n, A)) * 0.01 + rng.normal(0, 0.005)        # including a strong drift
    H = float((np.abs(Pw) * np.abs(Rw)).sum()) / n
    T = float(np.abs(np.diff(Pw, axis=0, prepend=0)).sum()) / n
    for c in (H / T * f for f in (0.5, 0.999999, 1.000001, 1.5, 3.0)):
        r = kernels.screen(Pw, Rw, c)
        if r["dominated"]:
            assert r["net_mean"] <= 0.0
        # the bound itself: gross mean never exceeds H
        assert r["gross_mean"] <= r["holder_bound"] * (1 + 1e-12)


@pytest.mark.parametrize("seed", range(10))
def test_stage1_is_blind_to_the_sign_of_returns(seed):
    """Flipping the sign of any evaluated return cannot change a stage-1 decision or the bound."""
    rng = np.random.default_rng(seed)
    Pw = _random_positions(rng, 150, 6, ["dense", "sparse", "flicker"][seed % 3])
    Rw = rng.normal(0, 0.01, (150, 6))
    flips = np.where(rng.random(Rw.shape) < 0.5, -1.0, 1.0)
    for c in (0.0, 1e-4, 1e-2):
        a = kernels.screen(Pw, Rw, c, stage2=False)
        b = kernels.screen(Pw, Rw * flips, c, stage2=False)
        assert a == b
    fa = kernels.fingerprint(Pw, "fx", "c1")
    assert fa == kernels.fingerprint(Pw.copy(), "fx", "c1") != kernels.fingerprint(Pw, "fx", "c2")


def test_tightest_sign_blind_bound_is_attained():
    """H is attained when every return has the sign of its position: no sign-blind bound can be tighter."""
    rng = np.random.default_rng(5)
    Pw = rng.normal(0, 0.01, (80, 4))
    absR = np.abs(rng.normal(0, 0.01, (80, 4)))
    r = kernels.screen(Pw, np.sign(Pw) * absR, 0.0)
    assert r["gross_mean"] == pytest.approx(r["holder_bound"], rel=1e-12)


def _stage3_inputs(seed, m=5, n=240, A=4):
    rng = np.random.default_rng(seed)
    Ps = [_random_positions(rng, n, A, ["dense", "sparse", "flicker", "zero", "dense"][i % 5]) for i in range(m)]
    Rw = rng.standard_t(4, (n, A)) * 0.01
    return Ps, Rw


@pytest.mark.parametrize("seed", range(4))
def test_stage3_series_matches_reference(seed):
    pol = Policy()
    Ps, Rw = _stage3_inputs(seed)
    out = kernels.stage3_series(Ps, [Rw] * len(Ps), [2e-4] * len(Ps), [1e-3] * len(Ps), pol)
    for i, P in enumerate(Ps):
        ref = kernels.ref_stage3_series(P, Rw, 2e-4, 1e-3, pol)
        # same operations on the recursion; the asset sums (A terms) differ in order only, so each period differs
        # by a few ulps of its terms, propagated through the (Lipschitz) scale: 1e-9 relative is a wide margin
        scale = np.abs(ref).max() + 1e-300
        assert np.max(np.abs(out["net"][i] - ref)) <= 1e-9 * scale


def test_stage3_rows_do_not_depend_on_the_batch():
    pol = Policy()
    Ps, Rw = _stage3_inputs(9, m=7)
    full = kernels.stage3_series(Ps, [Rw] * 7, [2e-4] * 7, [1e-3] * 7, pol)
    st_full = kernels.stage3_stats(full["net"], full["scale"], full["turnover"], pol)
    for i in range(7):
        one = kernels.stage3_series([Ps[i]], [Rw], [2e-4], [1e-3], pol)
        assert np.array_equal(one["net"][0], full["net"][i])
        st = kernels.stage3_stats(one["net"], one["scale"], one["turnover"], pol)
        assert np.array_equal(st[0], st_full[i], equal_nan=True)


def test_bootstrap_group_p_values_match_per_candidate_products():
    rng = np.random.default_rng(2)
    n, B = 300, 199
    C = kernels.boot_counts(n, B, 20, 11)
    net = rng.normal(0.0002, 0.01, (20, n))
    mean = net.mean(axis=1)
    om = np.sqrt(bootstrap.long_run_var(net, 0.05))
    p, z = kernels.stage3_boot(C, net, mean, om)
    for i in range(20):
        mb = np.dot(C, net[i]) / n
        diff = mb - mean[i] - mean[i]
        ties = int((np.abs(diff) < 1e-12).sum())
        p_ref = (1 + np.count_nonzero(diff >= 0)) / (B + 1)
        assert abs(p[i] - p_ref) <= ties / (B + 1)


def test_streaming_spa_matches_manhattan_spa_and_any_chunking():
    """The streaming family SPA equals manhattan.stats.spa.spa_test (same draws, fixed L) and is bit-identical
    under any split of the variants into partial maxima."""
    rng = np.random.default_rng(42)
    m, n = 9, 400
    common = rng.normal(0, 0.01, n)
    d = 0.6 * common + rng.normal(0, 0.008, (m, n)) + rng.normal(0, 0.0004, (m, 1))
    L_ = 20
    ref = SPA.spa_test(d, np.random.default_rng(7), L=L_, b_steps=(999,), continue_at=())
    C = bootstrap.counts(bootstrap.draw_blocks(np.random.default_rng(7), n, 1.0 / L_, 999))
    mean = d.mean(axis=1)
    om = np.sqrt(np.maximum(bootstrap.long_run_var(d, 1.0 / L_), 0.0))
    p, z = kernels.stage3_boot(C, d, mean, om)
    whole = kernels.spa_combine([kernels.spa_partial(z, mean, om, n, np.zeros(m, int))[0]])
    assert whole["T"] == pytest.approx(ref.T, rel=1e-12)
    # spa_test rounds the resampled statistics to float32; allow one resample of disagreement per p-value
    for k, rv in (("p_c", ref.p_c), ("p_l", ref.p_l), ("p_u", ref.p_u)):
        assert abs(whole[k] - rv) <= 2.0 / 1000, (k, whole[k], rv)
    for split_seed in range(5):
        groups = np.random.default_rng(split_seed).integers(0, 3, m)
        parts = []
        for gval in np.unique(groups):
            sel = groups == gval
            parts.append(kernels.spa_partial(z[sel], mean[sel], om[sel], n, np.zeros(sel.sum(), int))[0])
        res = kernels.spa_combine(parts[::-1])
        assert res == whole
    # an identically zero variant changes nothing (excluded exactly)
    z0 = np.vstack([z, np.zeros(z.shape[1])])
    with_zero = kernels.spa_combine([kernels.spa_partial(z0, np.append(mean, 0.0), np.append(om, 0.0), n,
                                                         np.zeros(m + 1, int))[0]])
    assert with_zero == whole
