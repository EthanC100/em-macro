"""S16 adversarial acceptance tests: look-ahead, duplicate evaluations, interrupted runs, corrupted artifacts,
evidence promotion, protected-data access, and failure observability.

Each test attacks the integrated synthetic platform from outside, through public APIs or by damaging persisted
files, and requires that the attack is refused or detected, that the failure is recorded where an auditor can see
it, and that no result derived from it is reported as a valid (let alone verified) result.
"""
from __future__ import annotations

import ast
import dataclasses
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

import s16_capabilities as CAP
from s16_helpers import fresh_hte_run, hte_subprocess

acc = pytest.mark.acceptance
ROOT = CAP.ROOT


# ================================================================================================ look-ahead

def _leaky_template():
    from manhattan.hte import templates as TP

    def leaky(cache, dom, p):
        r = cache.panel.returns(dom)
        s = np.zeros_like(r)
        s[:-1] = np.sign(r[1:])                     # the position at t uses the return of t+1
        return s

    return TP.TEMPLATES.setdefault("s16_leaky", TP.Template(
        "s16_leaky", 1, {"name": "s16-leaky", "mechanism": "S16 TEST ONLY", "sign": "+", "density": "dense"},
        {"lookback": ("int", 5, 10)}, lambda p: p["lookback"], leaky, test_only=True))


@acc(id="ADV-LA-01", area="lookahead", requires=("hte",))
def test_la01_a_template_that_reads_the_future_cannot_be_registered(tmp_path):
    from manhattan.hte import registry as R
    from manhattan.hte.runner import Workspace
    t = _leaky_template()
    fam = R.family(t.family["name"], t.family["mechanism"], t.family["sign"], t.family["density"])
    hyp = R.hypothesis(fam, "fx")
    spec = R.strategy_spec(hyp, "s16_leaky", {"lookback": [5, 6]})
    ws = Workspace(tmp_path)
    reg = ws.registry()
    rep = reg.submit([R.Bundle(fam, hyp, spec)], allow_test_templates=True)   # even with the test allowance
    assert rep["rejected"] == 1 and rep["registered_candidates"] == 0 and len(reg) == 0
    rej = ws.log().of_type("submission_rejected")[-1]["payload"]
    assert any("PIT probe" in r for r in rej["reasons"]), rej        # observable: the reason is logged
    probes = [r["payload"] for r in ws.log().of_type("pit_probe") if r["payload"]["template"] == "s16_leaky"]
    assert probes and probes[-1]["passed"] is False


@acc(id="ADV-LA-02", area="lookahead", requires=("hte",))
def test_la02_published_observables_carry_their_lag_and_the_fence_holds():
    from manhattan.hte import data as D, fixtures as X
    p = D.generate(X.SMALL_PANEL)
    c = p.carry("fx")
    assert np.isnan(c[0]).all()                         # carry[t] is the value published at t (one-day lag)
    with pytest.raises(D.ProtectedDataRefused):
        p.window(p.fence - 10, p.fence + 1)


@acc(id="ADV-LA-03", area="lookahead", requires=("execution",))
def test_la03_execution_refuses_prices_seen_before_the_decision():
    from manhattan import execution as X
    from manhattan.execution import errors as XE
    import s16_fixtures as F
    w = F.execution_world()
    d0 = w["days"][0]
    with pytest.raises(XE.LookAheadError):
        X.fill_order(w["spec"], w["px"][0], 1, w["liq"], w["terms"], decided_at=w["published"](d0))
    t0 = datetime(d0.year, d0.month, d0.day, 20, 0, tzinfo=F.UTC)
    with pytest.raises(XE.LookAheadError):
        X.Decision("SYNA", 1, t0, inputs_known_at=t0 + timedelta(seconds=1))
    with pytest.raises(XE.ExecutionModelError):
        X.ExecutionPolicy(base_currency="USD", roll=X.RollPolicy(buffer_days=35, roll_before_notice_days=10), lag=0)
    at_close = w["close"](d0)                                          # decided exactly at the close
    r = X.run(w["market"], [X.Decision("SYNA", 1, at_close)], w["policy"], w["scenario"])
    assert r.fills[0].day > d0


@acc(id="ADV-LA-04", area="lookahead", requires=("equities",))
def test_la04_equities_reads_never_reach_past_as_of():
    from manhattan.equities import synthetic as syn
    from manhattan.equities.errors import CorporateActionError, TemporalError
    w = syn.world()
    with pytest.raises(TemporalError):
        w.prices.total_returns("S01", date(2006, 1, 3), date(2006, 3, 31), as_of=date(2006, 3, 1))
    with pytest.raises(CorporateActionError, match="survivorship"):
        w.prices.total_returns("S04", date(2006, 1, 3), date(2006, 7, 10), as_of=date(2006, 7, 10))
    # a hand-made original and restatement of one quarter: neither is visible before it is public
    from zoneinfo import ZoneInfo
    from manhattan.equities.fundamentals import Fact, FundamentalStore
    ny = lambda d, h: datetime.combine(d, datetime.min.time().replace(hour=h), ZoneInfo("America/New_York"))  # noqa: E731
    fs = FundamentalStore(syn.calendar())
    q = date(2006, 3, 31)
    fs.add(Fact("C1", "revenue", q, "quarter", 100.0, "USD", ny(date(2006, 5, 2), 17)))
    fs.add(Fact("C1", "revenue", q, "quarter", 90.0, "USD", ny(date(2007, 2, 14), 17), vintage="restated"))
    assert fs.value("C1", "revenue", date(2006, 4, 3)) is None                # the quarter ended, nothing filed
    assert fs.value("C1", "revenue", date(2006, 5, 2)) is None                # filed after that day's close
    assert fs.value("C1", "revenue", date(2006, 12, 29)).value == 100.0       # restatement not yet public
    assert fs.value("C1", "revenue", date(2007, 3, 1)).value == 90.0          # and visible once it is


# ================================================================================================ duplicates

@acc(id="ADV-DUP-01", area="duplicates", requires=("hte",))
def test_dup01_duplicate_registration_adds_nothing_and_is_logged(hte_null_experiment, tmp_path):
    from manhattan.hte import fixtures as X
    from manhattan.hte.runner import Workspace
    ws = Workspace(tmp_path)
    reg = ws.registry()
    b = X.small_bundles()
    reg.submit(b)
    before = len(reg)
    rep = reg.submit(b[:2] + b[:1])
    assert rep["registered_candidates"] == 0 and rep["duplicate_submissions"] == 3 and len(reg) == before
    assert len(ws.log().of_type("duplicate_submission")) == 3


@acc(id="ADV-DUP-02", area="duplicates", requires=("hte",))
def test_dup02_an_identical_evaluation_is_reused_not_recounted(tmp_path):
    from manhattan.hte.log import AttemptLog
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner, reconcile
    ws, panel, out = fresh_hte_run(tmp_path)
    n_starts = len(AttemptLog(ws.log_path).of_type("attempt_started"))
    again = Runner(ws, panel, Policy(), chunk_size=17).run()
    assert again["reused"] is True and again["result_root"] == out["result_root"]
    assert len(AttemptLog(ws.log_path).of_type("attempt_started")) == n_starts      # no new attempts
    assert AttemptLog(ws.log_path).of_type("run_reused")
    assert reconcile(ws, out["run_id"])["violations"] == []


@acc(id="ADV-DUP-03", area="duplicates", requires=("access",))
def test_dup03_a_finished_attempt_cannot_be_evaluated_or_superseded_again(tmp_path):
    from manhattan import ledger as L
    from manhattan.engine import evaluate, pit
    import s16_fixtures as F
    open_, _ = F.fences()
    book, st = F.ledger(tmp_path / "ledger.jsonl"), F.pit_store()
    s, e = date(2009, 11, 2), date(2009, 11, 30)
    ctx = F.register(book, st, start=s, end=e, role="exploration", fence=open_, caller="session")
    w = pit.Reader(st, caller="session", domain=F.DOM, fence=open_, attempt=ctx).window(s, e)
    evaluate.evaluate(w, F.hold(), ledger=book, **F.spec_kwargs(), attempt=ctx, log_path=tmp_path / "v.csv")
    n = len(book)
    with pytest.raises(pit.AccessError, match="registered and active"):    # the attempt has ended
        evaluate.evaluate(w, F.hold(), ledger=book, **F.spec_kwargs(), attempt=ctx, log_path=tmp_path / "v.csv")
    with pytest.raises(L.LedgerError):                               # a finished attempt cannot be "retried"
        F.register(book, st, start=s, end=e, role="exploration", fence=open_, caller="session",
                   supersedes=ctx.attempt_id)
    assert len(book) == n


@acc(id="ADV-DUP-04", area="duplicates", requires=("evidence",))
def test_dup04_the_same_evidence_cannot_be_counted_twice(monkeypatch):
    from manhattan import config, evidence as E
    import s16_fixtures as F
    monkeypatch.setattr(E, "TRUSTED_AUTHORITIES", frozenset({"s16-sim"}))
    md = F.hte_evidence_metadata(F.stand_in_panel(), "HR-s16")
    one = E.classify(md, F.honest_synthetic_results(md, "s16-sim"), fence=F.evidence_fence(), config=config.load())
    two = E.classify(md, F.honest_synthetic_results(md, "s16-sim"), fence=F.evidence_fence(), config=config.load())
    assert one.provenance == E.SYNTHETIC and E.issued(one) and E.issued(two)
    assert E.combine([one, two]).provenance == E.UNVERIFIED          # same subject, window and span
    assert E.combine([one, one]).provenance == E.UNVERIFIED


# ================================================================================================ interruption

@acc(id="ADV-INT-01", area="interruption", requires=("hte",))
@pytest.mark.parametrize("fault,expect", [("exit_after_start:3", "attempt_interrupted"),
                                          ("torn_completion:4", "torn_tail_quarantined")])
def test_int01_an_interrupted_run_is_never_reported_and_resumes_to_the_clean_result(tmp_path, fault, expect):
    from manhattan.hte.log import AttemptLog
    from manhattan.hte.runner import Workspace, reconcile
    _, _, clean = fresh_hte_run(tmp_path / "clean")
    crashed = tmp_path / "crashed"
    p = hte_subprocess(crashed, fault)
    assert p.returncode == 77, p.stderr[-2000:]
    ws = Workspace(crashed)
    run_id = clean["run_id"]                                         # same inputs, same identity
    types = [r["type"] for r in AttemptLog(ws.log_path).records()] if expect != "torn_tail_quarantined" else []
    assert "run_closed" not in types
    if expect == "attempt_interrupted":
        mid = reconcile(ws, run_id)
        assert mid["state"] == "incomplete" and mid["final_status"] is None
        assert mid["attempts"]["unfinished"] >= 1
    p2 = hte_subprocess(crashed)
    assert p2.returncode == 0, p2.stderr[-3000:]
    res = json.loads(p2.stdout.strip().splitlines()[-1])
    assert res["run_id"] == run_id and res["root"] == clean["result_root"]
    recs = AttemptLog(ws.log_path).records()
    assert expect in [r["type"] for r in recs]
    rec = reconcile(ws, run_id)
    assert rec["state"] == "closed" and rec["violations"] == []
    if expect == "attempt_interrupted":
        assert rec["attempts"]["interrupted"] >= 1                   # counted, never erased
        assert any(r["payload"].get("supersedes") for r in recs if r["type"] == "attempt_started")


@acc(id="ADV-INT-02", area="interruption", requires=("access",))
def test_int02_a_crash_after_registration_is_visible_until_a_retry_completes(tmp_path):
    from manhattan import attempts
    from manhattan.engine import evaluate, pit
    import s16_fixtures as F
    open_, _ = F.fences()
    st = F.pit_store()
    s, e = date(2009, 11, 2), date(2009, 11, 30)
    book = F.ledger(tmp_path / "ledger.jsonl")
    F.register(book, st, start=s, end=e, role="exploration", fence=open_, caller="session")
    del book                                                         # the process dies after the start record
    book = F.ledger(tmp_path / "ledger.jsonl")
    (start,) = book.unfinished()
    r = attempts.reconcile(ledger_path=book.path, ledger_anchor=F.anchor(book))
    assert not r["access_reconciled"] and r["unfinished"] == 1
    assert any(v["code"] == "missing_terminal" for v in r["violations"])
    retry = F.register(book, st, start=s, end=e, role="exploration", fence=open_, caller="session",
                       supersedes=start["hash"])
    w = pit.Reader(st, caller="session", domain=F.DOM, fence=open_, attempt=retry).window(s, e)
    evaluate.evaluate(w, F.hold(), ledger=book, **F.spec_kwargs(), attempt=retry, log_path=tmp_path / "v.csv")
    r = attempts.reconcile(ledger_path=book.path, ledger_anchor=F.anchor(book))
    assert r["access_reconciled"] and r["retries"] == 1 and r["completed"] == 1


# ================================================================================================ corruption

def _flip_byte(path: Path, offset: int = -9) -> None:
    b = bytearray(path.read_bytes())
    b[offset] ^= 0xFF
    path.write_bytes(bytes(b))


@acc(id="ADV-COR-01", area="corruption", requires=("hte",))
@pytest.mark.parametrize("target,code", [("results", "results_tampered"), ("attempt_file", "attempt_file_corrupt"),
                                         ("package", "package_tampered"), ("results_deleted", "results_missing")])
def test_cor01_damaged_artifacts_mark_the_run_corrupted(tmp_path, target, code):
    from manhattan.hte.runner import reconcile
    ws, _, out = fresh_hte_run(tmp_path)
    rdir = ws.run_dir(out["run_id"])
    if target == "results":
        _flip_byte(rdir / "results.bin")
    elif target == "results_deleted":
        (rdir / "results.bin").unlink()
    elif target == "attempt_file":
        _flip_byte(sorted((rdir / "A").iterdir())[0])
    else:                                       # a package edited to claim more than it may
        pk = sorted((rdir / "packages").glob("*.json"))[0]
        d = json.loads(pk.read_text())
        d["confirmatory"] = True
        d["evidence_class"] = "confirmatory"
        pk.write_text(json.dumps(d))
    rec = reconcile(ws, out["run_id"])
    assert rec["state"] == "corrupted", rec["violations"]
    assert code in {v["code"] for v in rec["violations"]}


@acc(id="ADV-COR-02", area="corruption", requires=("hte",))
@pytest.mark.parametrize("damage", ["alter", "delete_line", "reorder"])
def test_cor02_a_rewritten_attempt_log_is_refused(tmp_path, damage):
    from manhattan.hte import log as HL
    from manhattan.hte.runner import reconcile
    ws, _, out = fresh_hte_run(tmp_path)
    lines = ws.log_path.read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if '"attempt_completed"' in ln)
    if damage == "alter":
        r = json.loads(lines[i])
        r["payload"]["hi"] = r["payload"]["hi"] + 1
        lines[i] = json.dumps(r)
    elif damage == "delete_line":
        del lines[i]
    else:
        lines[i], lines[i + 1] = lines[i + 1], lines[i]
    ws.log_path.write_text("\n".join(lines) + "\n")
    with pytest.raises(HL.LogError):
        HL.verify(ws.log_path)
    with pytest.raises(HL.LogError):
        reconcile(ws, out["run_id"])


@acc(id="ADV-COR-03", area="corruption", requires=("hte",))
def test_cor03_a_swapped_synthetic_panel_is_refused():
    from manhattan.hte import data as D, fixtures as X
    p = D.generate(X.SMALL_PANEL)
    D.verify_synthetic(p)
    r = {k: v.copy() for k, v in p._returns.items()}
    r["fx"][5, 0] += 0.01
    for v in r.values():
        v.setflags(write=False)
    forged = dataclasses.replace(p, _returns=r)
    with pytest.raises(D.NotSynthetic):
        D.verify_synthetic(forged)
    with pytest.raises(D.NotSynthetic):
        D.verify_synthetic(dataclasses.replace(p, provenance={"synthetic": True, "generator": "real-feed/1"}))


@acc(id="ADV-COR-04", area="corruption", requires=("access",))
@pytest.mark.parametrize("damage", ["delete", "alter", "truncate"])
def test_cor04_a_rewritten_manhattan_ledger_never_reconciles(tmp_path, damage):
    from manhattan import attempts
    from manhattan.engine import evaluate, pit
    import s16_fixtures as F
    open_, _ = F.fences()
    book, st = F.ledger(tmp_path / "ledger.jsonl"), F.pit_store()
    s, e = date(2009, 11, 2), date(2009, 11, 30)
    ctx = F.register(book, st, start=s, end=e, role="exploration", fence=open_, caller="session")
    w = pit.Reader(st, caller="session", domain=F.DOM, fence=open_, attempt=ctx).window(s, e)
    evaluate.evaluate(w, F.hold(), ledger=book, **F.spec_kwargs(), attempt=ctx, log_path=tmp_path / "v.csv")
    a = F.anchor(book)
    rows = book.path.read_text().splitlines()
    if damage == "delete":
        del rows[0]
    elif damage == "truncate":
        rows.pop()
    else:
        r = json.loads(rows[-1])
        r["payload"]["evidential_weight"] = 1
        rows[-1] = json.dumps(r)
    book.path.write_text("\n".join(rows) + "\n")
    with pytest.raises(attempts.ReconciliationError):
        attempts.reconcile(ledger_path=book.path, ledger_anchor=a)


# ================================================================================================ promotion

@acc(id="ADV-PRO-01", area="promotion", requires=("evidence",))
def test_pro01_forged_or_unauthenticated_evidence_gets_no_weight(monkeypatch):
    from manhattan import config, evidence as E
    import s16_fixtures as F

    md = F.hte_evidence_metadata(F.stand_in_panel(), "HR-s16")
    fence, cfg = F.evidence_fence(), config.load()
    # 1. claimed labels without verifiers
    claimed = dict(md, claimed_provenance="captured_forward", claimed_role="forward")
    c = E.classify(claimed, None, fence=fence, config=cfg)
    assert c.provenance == E.UNVERIFIED and c.weight_ceiling == 0 and E.cap_weight(c, 1) == 0
    # 2. a verifier result from an authority nobody trusts
    c = E.classify(md, F.honest_synthetic_results(md, "self-declared"), fence=fence, config=cfg)
    assert c.provenance == E.UNVERIFIED and E.cap_weight(c, 1) == 0
    # 3. a classification forged into a forward candidate
    forged = dataclasses.replace(c, provenance=E.CAPTURED_FORWARD, eligibility=E.E_FORWARD, weight_ceiling=1,
                                 authenticated=True, promotion_authorized=True)
    assert E.issued(forged) is False and E.cap_weight(forged, 1) == 0
    assert E.combine([forged]).provenance == E.UNVERIFIED
    object.__setattr__(c, "weight_ceiling", 1)                       # mutated in place after issue
    assert E.cap_weight(c, 1) == 0
    # 4. metadata changed after verification
    monkeypatch.setattr(E, "TRUSTED_AUTHORITIES", frozenset({"s16-sim"}))
    res = F.honest_synthetic_results(md, "s16-sim")
    edited = json.loads(json.dumps(md))
    edited["span"]["end"] = "2030-12-31"
    assert E.classify(edited, res, fence=fence, config=cfg).provenance == E.UNVERIFIED


@acc(id="ADV-PRO-02", area="promotion", requires=())
def test_pro02_promotion_and_claims_are_disabled_on_this_tree():
    from manhattan import config
    from manhattan.ops import promotion
    cfg = config.load()
    assert cfg["claims"]["enabled"] is False
    for tier in promotion.TIERS:
        with pytest.raises(promotion.PromotionDisabled):
            promotion.promote("s16-family", tier, protocol_hash=None, config=cfg)
    forged = json.loads(json.dumps(cfg))
    forged["claims"]["enabled"] = True                               # a caller-supplied config cannot open it
    with pytest.raises(promotion.PromotionDisabled):
        promotion.promote("s16-family", promotion.TIERS[-1], protocol_hash="0" * 64, config=forged)


@acc(id="ADV-PRO-03", area="promotion", requires=("equities",))
def test_pro03_equities_research_records_cannot_be_promoted():
    from manhattan import config
    from manhattan.equities import evidence as EQ
    from manhattan.equities.errors import EvidenceError
    rec = EQ.ResearchRecord(sorted(EQ.CANDIDATE_KINDS)[0], "ab" * 32)
    assert rec.evidential_weight == 0
    with pytest.raises(EvidenceError):
        EQ.promote(rec, "promising", config=config.load())
    assert EQ.scope_status(config=config.load())["enforced_in_protected_pipeline"] is False


@acc(id="ADV-PRO-04", area="promotion", requires=("hte",))
def test_pro04_hte_cannot_produce_confirmatory_output(tmp_path):
    from manhattan.hte import protected
    import manhattan.hte as HTE
    assert HTE.CONFIRMATORY is False
    src = "".join(p.read_text() for p in (ROOT / "manhattan" / "hte").glob("*.py"))
    assert '"confirmatory": True' not in src and "'confirmatory': True" not in src
    with pytest.raises(protected.ProtectedEvaluationDisabled):
        protected.evaluate(enabled=True, force=True, confirmatory=True)


# ================================================================================================ protected data

@acc(id="ADV-PRT-01", area="protected_data", requires=())
def test_prt01_reserve_forward_claims_and_real_money_are_disabled():
    from manhattan import config
    cfg = config.load()
    assert cfg["reserve"]["enabled"] is False
    assert cfg["claims"]["enabled"] is False
    assert cfg["forward"]["real_money"] is False and cfg["forward"]["loss_cap_usd"] == 0
    assert str(cfg["exploration"]["data_end"]) == "2019-12-31"


@acc(id="ADV-PRT-02", area="protected_data", requires=("hte",))
def test_prt02_hte_stage5_and_its_adapters_refuse_whatever_the_caller_passes(hte_null_experiment):
    from manhattan.hte import adapters, protected
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    e = hte_null_experiment
    with pytest.raises(protected.ProtectedEvaluationDisabled):
        Runner(e["ws"], e["panel"], Policy(), stages=(1, 2, 3, 4, 5))
    with pytest.raises(protected.ProtectedEvaluationDisabled):
        protected.evaluate(enabled=True)
    for ctor in (adapters.Pr86AccessAdapter, adapters.Pr85ExecutionAdapter, adapters.to_pr85_decisions):
        with pytest.raises(adapters.AdapterDisabled):
            ctor(enabled=True)


@acc(id="ADV-PRT-03", area="protected_data", requires=("access",))
def test_prt03_reserve_and_forward_windows_need_a_registered_authorized_attempt(tmp_path):
    from manhattan import roles
    from manhattan.engine import pit
    import s16_fixtures as F
    open_, reserve = F.fences()
    st = F.pit_store()
    wid = f"{F.DOM}:reserve"
    rs, re_ = date(2010, 1, 4), date(2010, 1, 15)
    with pytest.raises(pit.AccessError):                       # a valid token but no registered attempt
        pit.Reader(st, caller="runner", domain=F.DOM, fence=reserve, token=F.reserve_token(wid),
                   window_id=wid).window(rs, re_)
    for caller in ("session", "explorer"):                      # interactive callers never reach the reserve
        with pytest.raises(roles.RoleError):
            pit.Reader(st, caller=caller, domain=F.DOM, fence=reserve).window(rs, re_)
    book = F.ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(roles.RoleError):                        # reserve registration without a token
        F.register(book, st, start=rs, end=re_, role="reserve", fence=reserve, window_id=wid)
    with pytest.raises((pit.AccessError, roles.RoleError)):     # forward dates relabelled as exploration
        F.register(book, st, start=rs, end=re_, role="exploration", fence=open_, freeze=F.FREEZE)
    with pytest.raises((pit.AccessError, roles.RoleError)):     # a session cannot hold a protected attempt
        F.register(book, st, start=rs, end=re_, role="forward", fence=open_, freeze=F.FREEZE, caller="session")
    assert len(book) == 0                                       # nothing written by a refused registration
    ctx = F.register(book, st, start=date(2009, 11, 2), end=date(2009, 12, 31), role="exploration",
                     fence=reserve, caller="session")
    with pytest.raises(pit.AccessError):                        # an exploration attempt cannot open reserve dates
        pit.Reader(st, caller="runner", domain=F.DOM, fence=reserve, token=F.reserve_token(wid), window_id=wid,
                   attempt=ctx).window(rs, re_)


@acc(id="ADV-PRT-04", area="protected_data", requires=("equities",))
def test_prt04_licensed_and_non_synthetic_equity_sources_are_refused():
    from manhattan import roles
    from manhattan.engine.pit import PitStore
    from manhattan.equities import pit_bridge, research, sources, synthetic as syn
    from manhattan.equities.errors import ContractError, EvidenceError
    w = syn.world()
    lic = sources.DataContract("lic", "fundamentals_pit", "vendor", "licensed", "doc", "filing_acceptance_time",
                               "vintaged", True, ("signal",), coverage_evidence="synthetic acceptance fixture")
    with pytest.raises(ContractError, match="public repository"):
        pit_bridge.fundamentals_to_pit(w.fundamentals, PitStore(), lic)
    public = sources.ContractRegistry([sources.DataContract(
        "px", "prices_daily", "vendor", "public", "doc", "date_only", "immutable", False, ("descriptive",))])
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
    with pytest.raises(EvidenceError):
        research.open_window(PitStore(), domain="x", start=date(2004, 1, 2), end=date(2004, 6, 30), fence=fence,
                             contracts=public)


_NEW_CODE = ("manhattan/hte", "manhattan/execution", "manhattan/equities", "manhattan/evidence.py",
             "manhattan/access.py")
_NETWORK = {"socket", "requests", "urllib", "urllib.request", "http.client", "ftplib", "smtplib", "paramiko",
            "boto3", "httpx", "aiohttp"}
_PRIVATE_STRINGS = ("EM_MACRO_DATA", "DATA_REPO_READ_TOKEN", "DATA_REPO_URL", "em-macro-data")


@acc(id="ADV-PRT-05", area="protected_data", requires=())
def test_prt05_new_platform_code_has_no_network_or_private_store_path():
    """Static: the approved PRs' packages import no network client and name no private-store variable."""
    files = []
    for rel in _NEW_CODE:
        p = ROOT / rel
        files += sorted(p.rglob("*.py")) if p.is_dir() else ([p] if p.exists() else [])
    findings = []
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                findings += [f"{f.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in
                             {n.split(".")[0] for n in _NETWORK}]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in \
                    {n.split(".")[0] for n in _NETWORK}:
                findings.append(f"{f.name}: from {node.module}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                findings += [f"{f.name}: '{s}'" for s in _PRIVATE_STRINGS if s in node.value]
    # PR #89 names em-macro-data only inside its own guard list (a test that HTE never imports it)
    findings = [x for x in findings if not x.startswith("adapters.py")]
    assert findings == [], findings


# ================================================================================================ observability

@acc(id="ADV-OBS-01", area="observability", requires=("hte",))
def test_obs01_a_failure_in_any_phase_is_recorded_and_leaves_no_result_of_record(tmp_path, monkeypatch):
    from manhattan.hte import data as D, fixtures as X, package as PK
    from manhattan.hte.log import AttemptLog
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner, Workspace, reconcile
    ws = Workspace(tmp_path)
    reg = ws.registry()
    reg.submit(X.small_bundles())
    reg.freeze()

    def boom(*a, **k):
        raise RuntimeError("S16 injected stage-4 failure")

    monkeypatch.setattr(PK, "build", boom)
    r = Runner(ws, D.generate(X.SMALL_PANEL), Policy(), chunk_size=60)
    with pytest.raises(RuntimeError, match="S16 injected"):
        r.run()
    recs = AttemptLog(ws.log_path).records()
    failed = [x["payload"] for x in recs if x["type"] == "run_failed"]
    assert failed and failed[-1]["phase"] == "stage4" and failed[-1]["error_class"] == "RuntimeError"
    assert "run_closed" not in [x["type"] for x in recs]
    rec = reconcile(ws, r.run_id)
    assert rec["state"] != "closed" and rec["final_status"] is None
    assert rec["failed_invocations"] and rec["unrecorded_results_file"] is True   # present, but not of record


@acc(id="ADV-OBS-02", area="observability", requires=("hte",))
def test_obs02_rejected_and_refused_work_leaves_a_reason(tmp_path, monkeypatch):
    import shutil as SH
    from manhattan.hte import data as D, fixtures as X, registry as R
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import RunError, Runner, Workspace
    ws = Workspace(tmp_path)
    reg = ws.registry()
    b = X.small_bundles(domains=("fx",), templates=("trend",))[0]
    spec = json.loads(json.dumps(b.spec))
    spec["grid"]["lookback"] = [400]
    assert reg.submit([R.Bundle(b.family, b.hypothesis, spec)])["rejected"] == 1
    assert ws.log().of_type("submission_rejected")[-1]["payload"]["reasons"]
    reg.submit(X.small_bundles())
    reg.freeze()
    monkeypatch.setattr(SH, "disk_usage", lambda p: SH._ntuple_diskusage(10 ** 12, 10 ** 12, 0))
    with pytest.raises(RunError):
        Runner(ws, D.generate(X.SMALL_PANEL), Policy()).run()
    refused = ws.log().of_type("run_refused")
    assert refused and refused[-1]["payload"]["reason"] == "insufficient_disk"
