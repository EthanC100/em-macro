"""Technology equities, research family B: historical fundamental analogues. Temporal integrity on synthetic data.
Nothing here measures whether analogues predict anything."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from manhattan.equities import analogues as A
from manhattan.equities.errors import EvidenceError, TemporalError

FEATS = ("rev_growth", "gross_margin", "op_margin", "rd_intensity")
T = date(2010, 6, 30)
H = 365


def obs(cid, d, vals, *, lag=40, category="enterprise_software", in_universe=True, regime="calm"):
    f = dict(zip(FEATS, vals))
    known = {k: d - timedelta(days=lag) for k in f}
    return A.Observation(cid, d, f, known, category=category,
                         stage=A.growth_stage(f.get("rev_growth", np.nan), f.get("op_margin", np.nan)),
                         regime=regime, in_universe=in_universe)


def pool_fixture(seed=0):
    rng = np.random.default_rng(seed)
    p = A.AnaloguePool()
    for i in range(30):
        cid = f"C{i:02d}"
        base = rng.normal([0.25, 0.65, 0.05, 0.15], [0.15, 0.1, 0.1, 0.05])
        for d in [date(y, m, dd) for y in range(2004, 2010) for m, dd in ((3, 31), (9, 30))]:   # half-yearly
            o = obs(cid, d, base + rng.normal(0, 0.02, 4), category="enterprise_software" if i % 3 else "cybersecurity",
                    in_universe=not (i == 29))
            p.add(o)
            p.add_outcome(A.Outcome(cid, d, d + timedelta(days=H), float(rng.normal()), d + timedelta(days=H + 3)))
    return p


def target(vals=(0.3, 0.7, 0.04, 0.16), cid="TGT", d=T):
    return obs(cid, d, vals)


def test_features_must_be_known_at_observation_date():
    with pytest.raises(TemporalError, match="known only"):
        A.Observation("C1", date(2010, 3, 31), {"rev_growth": 0.2}, {"rev_growth": date(2010, 5, 2)})
    with pytest.raises(TemporalError, match="availability"):
        A.Observation("C1", date(2010, 3, 31), {"rev_growth": 0.2}, {})


def test_outcome_like_features_are_refused():
    with pytest.raises(EvidenceError):
        A.Observation("C1", T, {"fwd_return_12m": 0.1}, {"fwd_return_12m": T})
    p = pool_fixture()
    with pytest.raises(EvidenceError):
        A.match(p, target(), T, features=["rev_growth", "next_year_revenue"])


def test_no_candidate_after_T_and_target_never_matches_itself():
    p = pool_fixture()
    p.add(obs("TGT", date(2008, 3, 31), (0.3, 0.7, 0.04, 0.16)))           # the target's own past
    p.add(obs("C00", date(2011, 3, 31), (0.3, 0.7, 0.04, 0.16)))           # after T
    res = A.match(p, target(), T, k=200)
    assert all(m.as_of <= T for m in res.matches)
    assert all(m.company_id != "TGT" for m in res.matches)
    assert res.excluded["future"] == 1 and res.excluded["self"] == 1
    with pytest.raises(TemporalError):
        A.match(p, target(d=date(2010, 7, 30)), T)


def test_training_requires_outcomes_observable_by_T_and_thins_overlaps():
    p = pool_fixture()
    res_d = A.match(p, target(), T, k=1000, purpose="descriptive")
    res_t = A.match(p, target(), T, k=1000, purpose="training", horizon_days=H)
    # 2009-03-31 outcomes end 2010-03-31 and are known 2010-04-03 <= T: eligible; nothing ends after T
    for m in res_t.matches:
        o = p.outcome(m.company_id, m.as_of, T)
        assert o is not None and o.known_from <= T and o.end <= T
    # yearly observations with a 365-day horizon overlap a little: at most one per company per horizon
    by_company = {}
    for m in res_t.matches:
        by_company.setdefault(m.company_id, []).append(m.as_of)
    for ds in by_company.values():
        ds.sort()
        assert all((b - a).days >= H for a, b in zip(ds, ds[1:]))
    assert len(res_t.matches) < len(res_d.matches)
    assert res_t.excluded["overlapping_horizon"] > 0 and res_t.excluded["outcome_unobservable"] > 0
    # an outcome that is fully observable only after T is excluded
    p.add(obs("LATE", date(2009, 9, 30), (0.3, 0.7, 0.04, 0.16)))
    p.add_outcome(A.Outcome("LATE", date(2009, 9, 30), date(2010, 9, 30), 9.9, date(2010, 10, 5)))
    res2 = A.match(p, target(), T, k=1000, purpose="training", horizon_days=H)
    assert "LATE" not in {m.company_id for m in res2.matches}
    assert "LATE" in {m.company_id for m in A.match(p, target(), T, k=1000).matches}


def test_descriptive_analogues_cannot_train_a_forecast():
    p = pool_fixture()
    with pytest.raises(EvidenceError):
        A.forecast(p, A.match(p, target(), T, k=5))
    fc = A.forecast(p, A.match(p, target(), T, k=5, purpose="training", horizon_days=H))
    assert fc["n"] == 5 and fc["evidential_weight"] == 0


def test_matching_is_blind_to_outcomes():
    p = pool_fixture()
    a = A.match(p, target(), T, k=10, purpose="training", horizon_days=H)
    for key, o in list(p._out.items()):                       # rewrite every outcome value (selection by outcome)
        p._out[key] = A.Outcome(o.company_id, o.start, o.end, -o.value * 100, o.known_from)
    b = A.match(p, target(), T, k=10, purpose="training", horizon_days=H)
    assert [(m.company_id, m.as_of, m.distance) for m in a.matches] == \
        [(m.company_id, m.as_of, m.distance) for m in b.matches]


def test_candidates_outside_the_pit_universe_are_excluded():
    p = pool_fixture()
    res = A.match(p, target(), T, k=1000)
    assert "C29" not in {m.company_id for m in res.matches}
    assert res.excluded["not_in_universe"] == 12


def test_normalisation_uses_only_eligible_candidates():
    p = pool_fixture()
    r1 = A.match(p, target(), T, k=5)
    p.add(obs("FUT", date(2012, 3, 31), (50.0, 50.0, 50.0, 50.0)))       # an extreme future observation
    r2 = A.match(p, target(), T, k=5)
    assert r1.centre == r2.centre and r1.scale == r2.scale


def test_missing_features_are_handled_and_overlap_enforced():
    p = A.AnaloguePool()
    full = obs("A", date(2008, 3, 31), (0.3, 0.7, 0.04, 0.16))
    p.add(full)
    p.add(A.Observation("B", date(2008, 3, 31), {"rev_growth": 0.35, "gross_margin": 0.6},
                        {"rev_growth": date(2008, 2, 1), "gross_margin": date(2008, 2, 1)}))
    for i in range(10):
        p.add(obs(f"N{i}", date(2007, 3, 31), (0.1 * i, 0.5 + 0.02 * i, 0.01 * i, 0.1)))
    res = A.match(p, target(), T, k=20, min_overlap=3)
    ids = {m.company_id for m in res.matches}
    assert "A" in ids and "B" not in ids                    # B shares only two features
    res2 = A.match(p, target(), T, k=20, min_overlap=2)
    mb = next(m for m in res2.matches if m.company_id == "B")
    assert mb.n_features == 2 and set(mb.contributions) == {"gross_margin", "rev_growth"}
    assert sum(mb.contributions.values()) == pytest.approx(1.0)


def test_constraints_methods_and_explanations():
    p = pool_fixture()
    t = target()
    r = A.match(p, t, T, k=10, category=True)
    assert all(next(o for o in p.observations() if o.company_id == m.company_id and o.as_of == m.as_of).category
               == t.category for m in r.matches)
    for method in ("standardized", "mahalanobis"):
        res = A.match(p, t, T, k=5, method=method)
        assert len(res.matches) == 5
        assert all(abs(sum(m.contributions.values()) - 1) < 1e-9 for m in res.matches if m.distance > 0)
    p.add(obs("TGT", date(2007, 6, 30), (0.3, 0.7, 0.04, 0.16)))
    p.add(obs("TGT", date(2008, 6, 30), (0.3, 0.7, 0.04, 0.16)))
    p.add(obs("TGT", date(2009, 6, 30), (0.3, 0.7, 0.04, 0.16)))
    p.add(t)
    tr = A.match(p, t, T, k=5, method="trajectory", trajectory_len=3)
    assert tr.matches and all(m.as_of <= T for m in tr.matches)


def test_identical_analogue_is_nearest():
    p = pool_fixture()
    p.add(obs("TWIN", date(2009, 6, 30), (0.3, 0.7, 0.04, 0.16)))
    assert A.match(p, target(), T, k=1).matches[0].company_id == "TWIN"


def test_baselines_use_the_same_training_information():
    p = pool_fixture()
    t = target()
    sm = A.sector_mean_baseline(p, t, T, H)
    lin = A.linear_baseline(p, t, T, H, FEATS)
    assert np.isfinite(sm) and np.isfinite(lin)
    p.add(obs("FUT", date(2011, 3, 31), (0.3, 0.7, 0.04, 0.16)))
    p.add_outcome(A.Outcome("FUT", date(2011, 3, 31), date(2012, 3, 31), 1e6, date(2012, 4, 2)))
    assert A.sector_mean_baseline(p, t, T, H) == sm and A.linear_baseline(p, t, T, H, FEATS) == lin


def test_growth_stage_labels():
    assert A.growth_stage(0.4, -0.1) == "hypergrowth_unprofitable"
    assert A.growth_stage(0.05, 0.2) == "mature"
    assert A.growth_stage(float("nan"), 0.1) == "unknown"


# ----------------------------------------------------------------------------- S8 correction round: regressions
def _h2_pool(record_c5: bool):
    p = A.AnaloguePool()
    for i in range(6):
        cid = f"C{i}"
        p.add(obs(cid, date(2008, 3, 31), (0.1 * i, 0.5, 0.1, 0.1)))
        if i != 5 or record_c5:
            p.add_outcome(A.Outcome(cid, date(2008, 3, 31), date(2009, 3, 31), -0.9 if i == 5 else 0.1,
                                    date(2009, 4, 2)))
    return p


def test_s8_h2_missing_observable_outcome_fails_closed():
    """S8 H2: C5 (failed and delisted; outcome never recorded) was silently dropped from the training set."""
    with pytest.raises(A.MissingOutcomeError, match="C5"):
        A.match(_h2_pool(False), target(), T, k=10, purpose="training", horizon_days=H)
    with pytest.raises(A.MissingOutcomeError):
        A.sector_mean_baseline(_h2_pool(False), target(), T, H)
    res = A.match(_h2_pool(True), target(), T, k=10, purpose="training", horizon_days=H)
    assert "C5" in {m.company_id for m in res.matches}
    # descriptive matching does not need outcomes
    assert "C5" in {m.company_id for m in A.match(_h2_pool(False), target(), T, k=10).matches}


def test_s8_h2_outcomes_not_yet_due_are_excluded_not_errors():
    p = A.AnaloguePool()
    p.add(obs("NEW", date(2009, 9, 30), (0.3, 0.7, 0.04, 0.16)))     # window ends 2010-09-30, after T
    for i in range(4):
        p.add(obs(f"OLD{i}", date(2008, 3, 31), (0.3 + 0.05 * i, 0.6 + 0.03 * i, 0.04 + 0.01 * i, 0.1 + 0.02 * i)))
        p.add_outcome(A.Outcome(f"OLD{i}", date(2008, 3, 31), date(2009, 3, 31), 0.1, date(2009, 4, 2)))
    res = A.match(p, target(), T, k=10, purpose="training", horizon_days=H)
    assert {m.company_id for m in res.matches} == {"OLD0", "OLD1", "OLD2", "OLD3"}
    assert res.excluded["not_yet_observable"] == 1
    # within the grace period after the window ends, a missing outcome is not yet an error
    p2 = A.AnaloguePool()
    p2.add(obs("RECENT", date(2009, 6, 15), (0.3, 0.7, 0.04, 0.16)))  # ends 2010-06-15; due 2010-07-15 > T
    assert A.match(p2, target(), T, k=10, purpose="training", horizon_days=H).excluded["not_yet_observable"] == 1
    with pytest.raises(A.MissingOutcomeError):
        A.match(p2, target(), T, k=10, purpose="training", horizon_days=H, outcome_grace_days=0)


def test_s8_h2_outcome_window_must_match_the_horizon():
    p = A.AnaloguePool()
    p.add(obs("X", date(2008, 3, 31), (0.3, 0.7, 0.04, 0.16)))
    p.add_outcome(A.Outcome("X", date(2008, 3, 31), date(2008, 6, 30), 0.1, date(2008, 7, 2)))
    with pytest.raises(Exception, match="horizon"):
        A.match(p, target(), T, k=10, purpose="training", horizon_days=H)
