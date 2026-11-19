"""S13 research methodology (manhattan/methodology): synthetic only.

Three kinds of test: the utilities are correct (oracle null against Monte Carlo, identity layers, census counts,
world construction, error counting); the existing procedures are called unchanged; and the S13 findings that the
methodology document relies on reproduce from fixed seeds at small size. A synthetic rejection is a check of a
procedure, never a trading signal.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.special import ndtri

from manhattan.methodology import evaluate, experiments, identity, maxnull, worlds
from manhattan.stats import screening


# ------------------------------------------------------------------------------------------------ maxnull

@pytest.mark.parametrize("m,rho", [(1, 0.3), (6, 0.5), (50, 0.9), (200, 0.0), (1000, 0.3)])
def test_max_sf_matches_monte_carlo(m, rho):
    rng = np.random.default_rng(11)
    n = 60_000
    z = math.sqrt(rho) * rng.standard_normal((n, 1)) + math.sqrt(1 - rho) * rng.standard_normal((n, m))
    mx = z.max(axis=1)
    for t in (1.0, 2.0, 3.0):
        mc = (mx >= t).mean()
        assert abs(float(maxnull.max_sf(t, m, rho)) - mc) < 4 * math.sqrt(mc * (1 - mc) / n) + 1e-3


def test_critical_values_limits_and_monotonicity():
    assert maxnull.critical(0.05, 1, 0.5) == pytest.approx(float(ndtri(0.95)), abs=1e-7)
    assert maxnull.critical(0.05, 1000, 1.0) == pytest.approx(float(ndtri(0.95)), abs=1e-7)
    cs = [maxnull.critical(0.05, m, 0.5) for m in (1, 10, 100, 10_000, 1_000_000)]
    assert all(a < b for a, b in zip(cs, cs[1:]))
    assert maxnull.critical(0.05, 1000, 0.9) < maxnull.critical(0.05, 1000, 0.5) < maxnull.critical(0.05, 1000, 0.0)
    # independent case is closed form
    assert maxnull.critical(0.05, 100, 0.0) == pytest.approx(float(ndtri(0.95 ** (1 / 100))), abs=1e-6)


def test_tail_precision_for_huge_grids():
    p = float(maxnull.max_sf(8.0, 10_000_000, 0.0))
    assert p == pytest.approx(-math.expm1(1e7 * math.log1p(-0.5 * math.erfc(8 / math.sqrt(2)))), rel=1e-6)
    assert p > 0


def test_power_and_mde_are_consistent():
    d = maxnull.mde_single(0.05, 0.8, 200, 0.5)
    assert maxnull.power_single(d, 0.05, 200, 0.5) == pytest.approx(0.8, abs=1e-6)
    assert maxnull.mde_single(0.05, 0.8, 1, 0.0) == pytest.approx(float(ndtri(0.95) + ndtri(0.8)), abs=1e-5)
    assert maxnull.mde_single(0.05, 0.8, 51_214, 0.5) > maxnull.mde_single(0.05, 0.8, 200, 0.5) + 0.8


# ------------------------------------------------------------------------------------------------ identity

def _rec(att, *, fam="F1", var="V1", window="R1", role="reserve", data="d1", code="c1", status="completed",
         result="r1", designated=False, worker=0, chunk=0, data_read=True, supersedes=()):
    return {"scientific": {"family": fam, "hypothesis": fam + "H", "variant": var},
            "evaluation": {"binding": "U1/C1/S1", "methodology": "m1", "window": window, "role": role,
                           "data_hash": data, "code": code, "env": "e1"},
            "schedule": {"attempt": att, "status": status, "result_hash": result, "worker": worker, "chunk": chunk,
                         "data_read": data_read, "supersedes": list(supersedes)},
            "designated": designated}


def test_layers_refuse_foreign_fields():
    with pytest.raises(identity.LayerError):
        identity.scientific_key({"family": "F", "hypothesis": "H", "variant": "V", "code": "abc"})
    with pytest.raises(identity.LayerError):
        identity.scientific_key({"family": "F", "hypothesis": "H", "variant": "V", "worker": 3})
    with pytest.raises(identity.LayerError):
        identity.look_key({"family": "F", "hypothesis": "H", "variant": "V"},
                          {"binding": "b", "methodology": "m", "window": "w", "role": "r", "chunk": 1})


def test_look_is_invariant_to_computation_and_schedule_but_computation_is_not():
    r1, r2 = _rec("a1"), _rec("a2", data="d2", code="c2", worker=3, chunk=9)
    assert identity.look_key(r1["scientific"], r1["evaluation"]) == identity.look_key(r2["scientific"], r2["evaluation"])
    assert identity.computation_key(r1["scientific"], r1["evaluation"]) != \
        identity.computation_key(r2["scientific"], r2["evaluation"])


def test_census_scheduling_does_not_change_counts():
    recs = [_rec("a1"), _rec("a2", var="V2"), _rec("a3", fam="F2")]
    moved = [_rec("x9", worker=2, chunk=5), _rec("x8", var="V2", worker=1, chunk=7), _rec("x7", fam="F2", chunk=1)]
    c1, c2 = identity.census(recs), identity.census(list(reversed(moved)))
    for key in ("scientific", "looks", "computations", "multiplicity_units"):
        assert c1[key] == c2[key]
    assert c1["violations"] == c2["violations"] == []


def test_census_counts_failures_reruns_and_flags_violations():
    recs = [
        _rec("a1"),
        _rec("a2", result="r1"),                              # same computation, same result: a rerun, one look
        _rec("a3", fam="F2", status="failed", result=None),   # failed after reading data: still a look
        _rec("a4", fam="F3", status="aborted", data_read=False),
        _rec("a5", fam="F4", status="unfinished"),            # never closed, never superseded
        _rec("a6", fam="F5", status="unfinished"),
        _rec("a7", fam="F5", supersedes=["a6"]),              # retry of a6
    ]
    c = identity.census(recs)
    att = c["attempts"]
    assert att["registered"] == 7 and att["balanced"]
    assert (att["completed"], att["failed"], att["aborted"], att["unfinished"]) == (3, 1, 1, 2)
    assert c["scientific"]["family"] == 5
    assert c["multiplicity_units"] == {"R1|reserve": 4}        # F1, F2, F4, F5; F3 never read data
    kinds = [v["kind"] for v in c["violations"]]
    assert kinds == ["unfinished_attempt"]                      # a5 only; a6 was superseded


def test_census_flags_nondeterminism_repeated_looks_and_double_designation():
    recs = [_rec("a1", designated=True), _rec("a2", result="DIFFERENT"),
            _rec("a3", data="d2"),                                  # vendor revision: a repeated look
            _rec("b1", fam="G1", designated=True), _rec("b2", fam="G2", designated=True)]
    classes = identity.merge_classes(["F1", "G1", "G2"], {"G1": ["sem:x"], "G2": ["sem:x"]})
    c = identity.census(recs, classes)
    kinds = sorted(v["kind"] for v in c["violations"])
    assert kinds == ["multiple_designated_looks", "nondeterminism", "repeated_look"]
    assert c["scientific"]["classes"] == 2 and c["scientific"]["families_merged_into_other_classes"] == 1
    assert c["multiplicity_units"] == {"R1|reserve": 2}


def test_merge_classes_is_transitive_and_order_free():
    keys = {"A": ["s1"], "B": ["s1", "b7"], "C": ["b7"], "D": ["s9"]}
    m1 = identity.merge_classes(["D", "C", "B", "A"], keys)
    m2 = identity.merge_classes(["A", "B", "C", "D"], dict(reversed(list(keys.items()))))
    assert m1 == m2 == {"A": "A", "B": "A", "C": "A", "D": "D"}


# ------------------------------------------------------------------------------------------------ worlds

def test_null_world_is_calibrated():
    rng = np.random.default_rng(5)
    p, e = [], []
    for _ in range(8):
        d = worlds.draw(worlds.Programme(B=10, n_b=200, pi1=0.0, window="disjoint"), rng)
        p.append(d.p)
        e.append(d.E)
    p, e = np.concatenate(p), np.concatenate(e)
    assert abs(p.mean() - 0.5) < 0.015
    assert abs((p <= 0.05).mean() - 0.05) < 0.01
    assert abs(np.median(e) - 1) < 1 and abs(e.mean() - 1) < 0.15


def test_draw_is_deterministic_and_in_batch_order():
    prog = worlds.Programme(B=6, n_b=5, pi1=0.3, dup_k=3, dup_where="later", mirror=0.5)
    d1, d2 = worlds.draw(prog, np.random.default_rng(3)), worlds.draw(prog, np.random.default_rng(3))
    assert np.array_equal(d1.p, d2.p) and np.array_equal(d1.E, d2.E)
    assert np.all(np.diff(d1.unit_batch) >= 0)


def test_exact_copies_share_statistics_and_fresh_copies_do_not():
    rng = np.random.default_rng(4)
    d = worlds.draw(worlds.Programme(B=5, n_b=10, pi1=0.2, dup_k=4, dup_where="later"), rng)
    for c in np.unique(d.unit_class):
        u = d.unit_class == c
        assert np.unique(d.p[u]).size == 1 and np.unique(d.E[u]).size == 1
    d = worlds.draw(worlds.Programme(B=5, n_b=10, pi1=0.2, dup_k=4, dup_where="later", window="disjoint"), rng)
    fresh = d.unit_kind == worlds.FRESH
    assert fresh.any()
    for c in np.unique(d.unit_class[fresh]):
        assert np.unique(d.p[d.unit_class == c]).size > 1


def test_mirrors_are_distinct_null_classes_with_negative_dependence():
    rng = np.random.default_rng(6)
    d = worlds.draw(worlds.Programme(B=4, n_b=500, pi1=0.0, mirror=1.0, m=1), rng)
    mir = d.unit_kind == worlds.MIRROR
    assert mir.sum() == 2000 and not d.class_true.any()
    assert np.unique(d.unit_class).size == d.unit_class.size          # every unit is its own class
    # with one variant the mirror's statistic is exactly minus the original's
    orig_of = {}
    for i in np.flatnonzero(~mir):
        orig_of[(d.unit_batch[i], round(float(d.zmax[i]), 12))] = i
    assert all((d.unit_batch[i], round(-float(d.zmax[i]), 12)) in orig_of for i in np.flatnonzero(mir))


# ------------------------------------------------------------------------------------------------ evaluate

def test_screen_calls_the_protocol_procedures_unchanged():
    rng = np.random.default_rng(7)
    prog = worlds.Programme(B=8, n_b=20, pi1=0.2)
    d = worlds.draw(prog, rng)
    for name, cls, stat in (("bh_prds", screening.BatchBH, d.p), ("ebh_elond", screening.EbhElond, d.E)):
        proc, want = cls(120), np.zeros(d.p.size, dtype=bool)
        for b in range(prog.B):
            idx = np.flatnonzero(d.unit_batch == b)
            want[idx] = proc.step(stat[idx]).rejected
        assert np.array_equal(evaluate.screen(d, name, B=prog.B), want)


def test_counts_unit_and_class_level_by_hand():
    d = worlds.Draw(unit_class=np.array([0, 0, 1, 2, 2, 3]), unit_batch=np.array([0, 0, 0, 1, 1, 1]),
                    unit_kind=np.zeros(6, dtype=int), p=np.zeros(6), E=np.zeros(6), zmax=np.zeros(6),
                    class_true=np.array([True, False, False, True]), class_theta=np.zeros(4),
                    portfolio_sharpe=np.zeros(6))
    rej = np.array([True, True, True, True, False, False])
    c = evaluate.counts(d, rej, B=2)
    # classes 0 and 3 have an edge; units 2 and 3 belong to null classes 1 and 2
    assert (c["R_unit"], c["V_unit"], c["R_class"], c["V_class"]) == (4, 2, 3, 2)
    assert c["fdp_unit"] == 0.5 and c["fdp_class"] == pytest.approx(2 / 3) and c["power_class"] == 0.5
    assert list(c["fdp_class_path"]) == [0.5, pytest.approx(2 / 3)]
    assert np.array_equal(evaluate.tested_mask(d, True), [True, False, True, True, False, True])


# ------------------------------------------------------------------------------------------------ findings

def _offline(prog, reps, seed, dedup):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(reps):
        d = worlds.draw(prog, rng)
        rows.append(evaluate.counts(d, evaluate.screen(d, "offline_bh", B=prog.B, dedup=dedup), prog.B))
    return evaluate.summarise(rows)


def test_finding_duplicated_true_classes_inflate_class_fdr_and_dedup_restores_it():
    prog = worlds.Programme(B=5, n_b=100, pi1=0.10, dup_k=10, dup_target="true")
    raw, ded = _offline(prog, 40, 8, False), _offline(prog, 40, 8, True)
    assert raw["fdr_unit"] <= 0.25                     # the theorem's units: controlled
    assert raw["fdr_class"] > 0.35                     # the scientific reader's units: not
    assert ded["fdr_class"] <= 0.25
    assert raw["R_unit"] > 5 * raw["R_class"]          # discoveries counted many times over


def test_finding_selection_on_the_test_window_invalidates_and_a_fresh_window_does_not():
    out = experiments.selection_study(np.random.default_rng(9), 40, 0.0)
    assert out["fdr_same_window"] > 0.9 and out["fdr_fresh_window"] < 0.35
    cur = experiments.selection_study(np.random.default_rng(9), 40, 0.05)
    assert cur["mean_estimate_on_selection_window"] > 1.5 * cur["mean_true_portfolio_sharpe_of_registered"]
    assert abs(cur["mean_estimate_on_fresh_window"] - cur["mean_true_portfolio_sharpe_of_registered"]) < 0.1


def test_finding_rerun_shopping_inflates_size():
    out = experiments.rerun_shopping(np.random.default_rng(10), 0.9, 20_000)
    assert abs(out["k=1"]["size_0.05"] - 0.05) < 0.01
    assert out["k=10"]["size_0.05"] > 0.09


def test_finding_forward_support_is_slow_for_modest_sharpes():
    rng = np.random.default_rng(12)
    slow = experiments.forward_support(np.full(20, 0.5), 10, rng, N_F=300)
    fast = experiments.forward_support(np.full(20, 3.0), 10, rng, N_F=300)
    assert (slow >= 0).mean() < 0.25 and (fast >= 0).mean() > 0.75


def test_methodology_is_outside_every_simulation_code_hash():
    from manhattan.sim import run
    files = set(run.CODE_FILES) | set(run.CODE_FILES_HB) | set(run.CODE_FILES_V2) | set(run.CODE_FILES_V2_HB)
    assert not any(f.startswith("manhattan/methodology/") for f in files)
