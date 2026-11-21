"""S16 end-to-end synthetic experiment (acceptance gate for the integrated synthetic research platform).

The experiment, in order:

    E2E-01  frozen hypothesis registration        HTE registry: submit, freeze, bind a run to the frozen root
    E2E-02  evaluation identity                    the run identity is a pure function of every input
    E2E-03  synthetic data                         only verified generator output is accepted
    E2E-04  authorized computation                 the run reads only the unprotected synthetic window
    E2E-05  attempt accounting                     every registered candidate has exactly one terminal status
    E2E-06  statistical testing                    SPA per family, denominators stated, planted effect found
    E2E-07  reconciliation                         the reconciler rebuilds the result from persisted records
    E2E-08  research-only output                   nothing reports confirmatory or verified evidence
    E2E-09  cross-PR identity                      HTE attempt identities are valid PR #86 schema-2 identities
    E2E-10  binding accounting                     a synthetic exploration attempt registers, reads, reconciles
    E2E-11  execution realism                      decisions fill at a later close, net = gross - costs
    E2E-12  equities synthetic PIT                 the synthetic equities world reads point in time
    E2E-13  cross-PR interface                     PR #87's recorded #84/#86 interface matches the merged code
    E2E-14  evidence classification of the run     HTE output classifies as synthetic at best, never promotable

Every computation is on generated data in temporary directories.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest


acc = pytest.mark.acceptance


# ----------------------------------------------------------------------------------------------- registration

@acc(id="E2E-01", area="registration", requires=("hte",))
def test_e2e01_frozen_hypotheses_bind_the_run(hte_null_experiment, tmp_path):
    from manhattan.hte import ids, registry as R, templates as TP
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    e = hte_null_experiment
    assert e["submit"]["rejected"] == 0 and e["submit"]["registered_candidates"] == 120
    fr = e["frozen"]
    c = fr["counts"]
    assert c["candidates"] == 120 and c["families"] >= 1 and c["hypotheses"] >= c["families"]
    view = e["runner"].view
    assert view.root == fr["root"] == e["runner"].ident["registry_root"]
    for i in (0, 59, 119):                    # every candidate's id is the hash of its canonical configuration
        assert ids.full_hash(view.canonical_config(i)) == view.candidate_hash(i)
    # a registration after the freeze cannot change a run bound to the earlier frozen root
    ws = e["ws"]
    fam = R.family(TP.TEMPLATES["trend"].family["name"], TP.TEMPLATES["trend"].family["mechanism"], "+", "dense")
    hyp = R.hypothesis(fam, "fx")
    spec = R.strategy_spec(hyp, "trend", {"lookback": [37], "shape": ["sign"], "vol_halflife": [20],
                                          "rebalance": [1]})
    late = tmp_path / "late"
    import shutil
    shutil.copytree(ws.root, late)
    from manhattan.hte.runner import Workspace
    ws2 = Workspace(late)
    reg2 = ws2.registry()
    assert reg2.submit([R.Bundle(fam, hyp, spec)])["registered_candidates"] == 1
    reg2.freeze()
    bound = Runner(ws2, e["panel"], Policy(), chunk_size=32, registry_root=fr["root"])
    assert len(bound.view) == 120 and bound.run_id == e["out"]["run_id"]
    newer = Runner(ws2, e["panel"], Policy(), chunk_size=32)
    assert len(newer.view) == 121 and newer.run_id != e["out"]["run_id"]


# ----------------------------------------------------------------------------------------------- identity

@acc(id="E2E-02", area="identity", requires=("hte",))
def test_e2e02_evaluation_identity_covers_every_input(hte_null_experiment):
    from manhattan.hte import data as D
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    e = hte_null_experiment
    ident = e["runner"].ident
    for k in ("registry_root", "data_hash", "engine_sha256", "policy_hash", "fence", "methodology", "stages",
              "execution", "numeric_environment_sha256"):
        assert ident.get(k) not in (None, "", []), k
    again = Runner(e["ws"], e["panel"], Policy(), chunk_size=7, workers=1)
    assert again.run_id == e["out"]["run_id"]                     # chunking is not part of the identity
    other_data = Runner(e["ws"], D.generate(D.PanelParams(seed=8, n_days=760, protected_days=100)), Policy())
    other_stages = Runner(e["ws"], e["panel"], Policy(), stages=(1, 2))
    ids_ = {e["out"]["run_id"], other_data.run_id, other_stages.run_id}
    assert len(ids_) == 3


# ----------------------------------------------------------------------------------------------- synthetic data

@acc(id="E2E-03", area="synthetic_data", requires=("hte",))
def test_e2e03_only_verified_synthetic_panels_run(hte_null_experiment):
    from manhattan.hte import data as D
    p = hte_null_experiment["panel"]
    assert p.provenance["synthetic"] is True and D.verify_synthetic(p) == p.data_hash
    assert hte_null_experiment["runner"].data_hash == p.data_hash
    r = p.returns("fx")
    assert not r.flags.writeable
    with pytest.raises(D.NotSynthetic):
        D.verify_synthetic({"returns": np.zeros((10, 2))})        # anything not from the generator


# ----------------------------------------------------------------------------------------------- authorization

@acc(id="E2E-04", area="authorization", requires=("hte",))
def test_e2e04_computation_reads_only_the_unprotected_window(hte_null_experiment):
    from manhattan.hte import data as D, protected
    p = hte_null_experiment["panel"]
    assert p.returns("fx").shape[0] == p.fence < p.params.n_days
    assert p.window(0, p.fence) == (0, p.fence)
    with pytest.raises(D.ProtectedDataRefused):
        p.window(0, p.fence + 1)
    with pytest.raises(D.ProtectedDataRefused):
        p.protected_tail("fx")
    assert protected.ENABLED is False and protected.status()["enabled"] is False
    assert 5 not in hte_null_experiment["runner"].stages


# ----------------------------------------------------------------------------------------------- accounting

@acc(id="E2E-05", area="accounting", requires=("hte",))
def test_e2e05_every_registered_candidate_is_accounted_for(hte_null_experiment):
    from manhattan.hte.runner import history, reconcile
    e = hte_null_experiment
    rec = reconcile(e["ws"], e["out"]["run_id"])
    assert rec["violations"] == []
    N = rec["registered"]["candidates"]
    assert N == 120
    for stage, counts in rec["final_status"].items():
        assert sum(counts.values()) == N and counts["not_run"] == 0, stage
    a = rec["attempts"]
    assert a["started"] == a["completed"] + a["failed"] + a["interrupted"] + a["unfinished"] + a["verification"]
    assert a["unfinished"] == 0 and a["failed"] == 0
    for i in (0, 77, 119):
        h = history(e["ws"], e["out"]["run_id"], i)
        assert h and all(x["terminal"] == "attempt_completed" for x in h)
        assert sorted({x["pass"] for x in h}) == ["A", "B"]


# ----------------------------------------------------------------------------------------------- statistics

def _packages(ws, run_id):
    return [json.loads(p.read_text()) for p in sorted((ws.run_dir(run_id) / "packages").glob("*.json"))]


@acc(id="E2E-06", area="statistics", requires=("hte",))
def test_e2e06_statistical_tests_state_denominators_and_find_a_planted_effect(hte_null_experiment,
                                                                             hte_planted_experiment):
    e = hte_null_experiment
    pk = _packages(e["ws"], e["out"]["run_id"])
    assert pk, "no family packages"
    assert sum(p["denominators"]["candidates"] for p in pk) == 120       # every candidate in exactly one family
    for p in pk:
        pc = p["spa"]["p_c"]
        assert pc is None or (0.0 <= pc <= 1.0 and math.isfinite(pc))
        d = p["denominators"]
        assert d["candidates"] >= d["variants"] >= d["strategy_specs"] >= d["hypotheses"] >= 1
    pl = hte_planted_experiment
    pk2 = {p["family"]["name"]: p for p in _packages(pl["ws"], pl["out"]["run_id"])}
    assert pk2["synthetic-trend"]["spa"]["p_c"] < 0.05                     # the pipeline can see a known effect
    assert pk2["synthetic-trend"]["confirmatory"] is False and pk2["synthetic-trend"]["synthetic"] is True


# ----------------------------------------------------------------------------------------------- reconciliation

@acc(id="E2E-07", area="reconciliation", requires=("hte",))
def test_e2e07_reconciler_rebuilds_the_result_from_persisted_records(hte_null_experiment):
    from manhattan.hte import ids
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner, reconcile
    e = hte_null_experiment
    out = e["out"]
    rec = reconcile(e["ws"], out["run_id"])
    assert rec["state"] == "closed" and rec["violations"] == []
    raw = (e["ws"].run_dir(out["run_id"]) / "results.bin").read_bytes()
    assert ids.sha256_bytes(raw) == out["results_sha256"] == out["result_root"]
    assert rec["access_reconciled"] is False                      # HTE never certifies access completeness
    assert rec["independent_statistical_tests"] is None
    v = Runner(e["ws"], e["panel"], Policy(), chunk_size=48).run(verify_rerun=True)
    assert v["result_root"] == out["result_root"]                  # an independent recomputation reproduces it
    assert reconcile(e["ws"], out["run_id"])["violations"] == []


# ----------------------------------------------------------------------------------------------- research only

_FORBIDDEN_TRUE = ("confirmatory", "verified", "scientifically_verified", "promotion_authorized", "significant",
                   "discovery", "evidence_eligible", "forward_elond_eligible", "screening_eligible")


def _true_claims(obj, path=""):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if any(f in str(k).lower() for f in _FORBIDDEN_TRUE) and v is True:
                out.append(p)
            out += _true_claims(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _true_claims(v, f"{path}[{i}]")
    return out


@acc(id="E2E-08", area="research_only", requires=("hte",))
def test_e2e08_outputs_are_research_only(hte_null_experiment):
    import manhattan.hte as HTE
    from manhattan.hte.log import AttemptLog
    e = hte_null_experiment
    assert HTE.CONFIRMATORY is False and HTE.EVIDENCE_CLASS == "synthetic_screening_descriptive"
    out = e["out"]
    assert out["confirmatory"] is False and out["evidence_class"] == "synthetic_screening_descriptive"
    for p in _packages(e["ws"], out["run_id"]):
        assert p["confirmatory"] is False and p["synthetic"] is True
        assert p["evidence_class"] == "synthetic_screening_descriptive"
        assert any("SYNTHETIC" in w for w in p["warnings"])
        assert _true_claims(p) == []
    for r in AttemptLog(e["ws"].log_path).records():
        assert _true_claims(r["payload"]) == [], r["type"]


# ----------------------------------------------------------------------------------------------- cross-PR identity

@acc(id="E2E-09", area="identity", requires=("hte", "access"))
def test_e2e09_hte_identities_are_valid_pr86_identities(hte_null_experiment):
    from manhattan import ledger as L
    from manhattan.hte import adapters
    e = hte_null_experiment
    r = e["runner"]
    window = {"id": "s16-synthetic", "start": str(e["panel"].dates[0]), "end": str(e["panel"].dates[e["panel"].fence - 1]),
              "frequency": "daily"}
    seen = set()
    for i in range(len(r.view)):
        ident = adapters.to_pr86_identity(r.view, i, run_id=r.run_id, data_hash=r.data_hash, code=r.code,
                                          window=window, policy=e["policy"], fence=e["panel"].fence)
        assert tuple(sorted(ident)) == tuple(sorted(L.IDENTITY_FIELDS))
        if i in (0, 60, 119):
            L.validate_attempt_identity(ident)                     # PR #86's own structural validator
        assert ident["role"] == "exploration" and ident["designated"] is False
        seen.add(ident["spec_hash"])
    assert len(seen) == len(r.view)                                 # no two evaluations share an identity


# ----------------------------------------------------------------------------------------------- binding accounting

@acc(id="E2E-10", area="accounting", requires=("access",))
def test_e2e10_synthetic_exploration_attempt_registers_reads_and_reconciles(tmp_path):
    from datetime import date
    from manhattan import attempts
    from manhattan.engine import evaluate, pit
    import s16_fixtures as F
    open_, _ = F.fences()
    book, st = F.ledger(tmp_path / "ledger.jsonl"), F.pit_store()
    ctx = F.register(book, st, start=date(2009, 11, 2), end=date(2009, 11, 30), role="exploration", fence=open_,
                     caller="session")
    w = pit.Reader(st, caller="session", domain=F.DOM, fence=open_, attempt=ctx).window(date(2009, 11, 2),
                                                                                       date(2009, 11, 30))
    _, rec = evaluate.evaluate(w, F.hold(), ledger=book, **F.spec_kwargs(), attempt=ctx,
                               log_path=tmp_path / "variants.csv")
    assert rec["payload"]["attempt_id"] == ctx.attempt_id and rec["payload"]["evidential_weight"] == 0
    assert ctx.data_read and not ctx.active()
    r = attempts.reconcile(ledger_path=book.path, ledger_anchor=F.anchor(book))
    assert r["access_reconciled"] and r["violations"] == [] and r["completed"] == 1
    assert r["assurance"]["independently_anchored"] is False and r["independently_certified"] is False
    assert r["independent_statistical_tests"] is None


# ----------------------------------------------------------------------------------------------- execution

@acc(id="E2E-11", area="execution", requires=("execution",))
def test_e2e11_decisions_fill_at_a_later_close_and_costs_reconcile():
    from datetime import datetime
    from manhattan import execution as X
    import s16_fixtures as F
    w = F.execution_world()
    assert X.RESEARCH_ONLY is True and X.CALIBRATED is False
    d0 = w["days"][0]
    t0 = datetime(d0.year, d0.month, d0.day, 20, 0, tzinfo=F.UTC)          # after day 0's close
    r = X.run(w["market"], [X.Decision("SYNA", 3, t0)], w["policy"], w["scenario"])
    assert r.fills[0].day == w["days"][1]                                  # never the decision's own close
    tot = r.totals()
    assert tot["net"] == pytest.approx(tot["gross"] - tot["costs"])
    assert tot["costs"] > 0
    again = X.run(w["market"], [X.Decision("SYNA", 3, t0)], w["policy"], w["scenario"])
    assert again.result_hash() == r.result_hash()                          # deterministic


# ----------------------------------------------------------------------------------------------- equities

@acc(id="E2E-12", area="equities", requires=("equities",))
def test_e2e12_synthetic_equities_world_reads_point_in_time():
    from datetime import date
    from manhattan import roles
    from manhattan.engine.pit import PitStore, Reader
    from manhattan.equities import integration, pit_bridge, sources, synthetic as syn
    w = syn.world()
    store = PitStore()
    pit_bridge.prices_to_pit(w.prices, store, sources.synthetic_contract("prices_daily"), ["S04"],
                             date(2006, 1, 3), date(2006, 12, 29))
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
    win = Reader(store, caller="session", domain="equities_test", fence=fence).window(date(2006, 1, 3),
                                                                                    date(2006, 12, 29))
    p, _ = win.as_of("eq.px.S04", date(2006, 7, 19))
    assert p[-1] == np.datetime64("2006-06-30")              # the delisting return is not yet known on 19 July
    assert integration.runtime_integration() is False


# ----------------------------------------------------------------------------------------------- cross-PR interface

@acc(id="E2E-13", area="integration", requires=("equities", "access", "evidence"))
def test_e2e13_equities_recorded_interfaces_match_the_merged_code():
    from manhattan.equities import integration
    res = integration.check_all()
    assert res, "no interface checks recorded"
    bad = {k: v for k, v in res.items() if v != "structural_match"}
    assert bad == {}, bad


# ----------------------------------------------------------------------------------------------- evidence

@acc(id="E2E-14", area="research_only", requires=("hte", "evidence"))
def test_e2e14_hte_output_is_never_promotable_evidence(hte_null_experiment, monkeypatch):
    from manhattan import config, evidence as E
    from manhattan.ops import promotion
    import s16_fixtures as F
    e = hte_null_experiment
    md = F.hte_evidence_metadata(e["panel"], e["out"]["run_id"])
    # shipped state: no trusted authority, so the honest description of the run is unverified
    c = E.classify(md, F.honest_synthetic_results(md, "s16-unregistered-authority"), fence=F.evidence_fence(),
                   config=config.load())
    assert c.provenance == E.UNVERIFIED and c.weight_ceiling == 0 and c.eligibility == E.E_NONE
    assert (c.forward_elond_eligible, c.screening_eligible, c.promotion_authorized) == (False, False, False)
    # even under a simulated trusted authority, synthetic output is never a candidate and never promotable
    monkeypatch.setattr(E, "TRUSTED_AUTHORITIES", frozenset({"s16-simulated-authority"}))
    c2 = E.classify(md, F.honest_synthetic_results(md, "s16-simulated-authority"), fence=F.evidence_fence(),
                    config=config.load())
    assert c2.provenance == E.SYNTHETIC, c2.problems
    assert c2.eligibility == E.E_INFRA and c2.weight_ceiling == 0     # infrastructure validation, never more
    assert (c2.forward_elond_eligible, c2.screening_eligible, c2.promotion_authorized) == (False, False, False)
    with pytest.raises(promotion.PromotionDisabled):
        promotion.promote("hte-" + e["out"]["run_id"], promotion.TIERS[-1], protocol_hash=None,
                          config=config.load())
