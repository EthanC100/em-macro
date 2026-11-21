"""Dormant HTE execution bridge (manhattan/hte_execution_bridge, docs/manhattan/HTE_EXECUTION_BRIDGE.md).

Every number is synthetic. Two cross-checks run only with checkouts of the unmerged reviewed code:

    EXEC_REALISM_HTE_CHECKOUT=<checkout of PR #89 at 232d0d6>    real HTE panels, templates, stage 3 and scales
    EXEC_REALISM_PR85_CHECKOUT=<checkout of PR #85 at 3f6b213>   PR #85's execution_index and run on bridge output
"""
from __future__ import annotations

import ast
import importlib
import os
import sys
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from manhattan.execution_realism import adapter as AD
from manhattan.execution_realism import errors as XE
from manhattan.execution_realism import realism as RL
from manhattan.execution_realism import screening as SC
from manhattan.hte_execution_bridge import bridge as B
from manhattan.hte_execution_bridge import clock as CK
from manhattan.hte_execution_bridge import compare as CP
from manhattan.hte_execution_bridge import fixtures as FX
from manhattan.hte_execution_bridge import identity as ID
from manhattan.hte_execution_bridge import market as MK
from manhattan.hte_execution_bridge.errors import BridgeDisabled, BridgeError

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "manhattan/hte_execution_bridge"
CLIP = B.BridgeSettings(on_liquidity_shortfall="clip")


@pytest.fixture(scope="module")
def null():
    return FX.candidate("null")


@pytest.fixture(scope="module")
def null_out(null):
    return B.evaluate(null, CLIP)


# ================================================================== 1. dormant, research only, isolated
def test_the_bridge_is_dormant_and_synthetic_only(null):
    assert B.ENABLED is False and B.HteExecutionStage.enabled is False
    with pytest.raises(BridgeDisabled) as e:
        B.HteExecutionStage()
    assert all(cid in str(e.value) for cid, _ in B.CONNECTION_REQUIREMENTS)
    for prov in ({}, {"synthetic": False}, {"synthetic": "yes"}):
        with pytest.raises(BridgeDisabled):
            replace(null, provenance=prov)


def test_imports_neither_hte_nor_pr85_and_does_no_io():
    banned_attrs = {"environ", "getenv", "system", "popen", "urlopen", "socket", "write_text", "write_bytes",
                    "savetxt", "save", "tofile", "unlink", "mkdir", "now", "today", "read_text", "read_bytes"}
    for f in sorted(PKG.glob("*.py")):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                mod = node.module
                assert mod.split(".")[0] in {"__future__", "dataclasses", "datetime", "hashlib", "json", "math",
                                             "re", "types", "numpy", "manhattan"}, (f.name, mod)
                if mod.startswith("manhattan"):
                    assert mod.startswith("manhattan.execution_realism"), (f.name, mod)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in {"hashlib", "json", "math", "re", "numpy"}, (f.name, a.name)
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    assert fn.id not in {"open", "exec", "eval", "__import__"}, (f.name, fn.id)
                if isinstance(fn, ast.Attribute):
                    assert fn.attr not in banned_attrs, (f.name, fn.attr)
        text = f.read_text().lower()
        for word in ("ib_insync", "ibapi", "alpaca", "ccxt", "oanda", "databento", "norgate", "place_order",
                     "api_key", "data_repo_read_token"):
            assert word not in text, (f.name, word)


def test_nothing_imports_the_bridge():
    me = Path(__file__).resolve()
    for f in ROOT.rglob("*.py"):
        if PKG in f.parents or f.resolve() == me or ".git" in f.parts:
            continue
        try:
            tree = ast.parse(f.read_text(errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any("hte_execution_bridge" in n for n in names), f
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "import_module":
                assert "hte_execution_bridge" not in ast.unparse(node), f


# ================================================================== 2. timing: next available price, never same close
def test_default_is_lag_one_and_same_close_needs_an_explicit_allowance(null):
    assert B.BridgeSettings().lag == 1
    with pytest.raises(XE.OptimisticExecutionError):
        B.BridgeSettings(lag=0)
    out = B.evaluate(null, CLIP)
    assert out.label != "throughput_only" and out.result.lag == 1
    first = out.translation.decision_rows[0]
    fills = [f for f in out.result.fills if f.filled]
    assert fills[0].day == first + 1 and fills[0].liquidity_day == first        # next close, liquidity at decision
    assert np.array_equal(out.translation.execution_rows, out.translation.decision_rows + 1)


def test_clock_timestamps_and_refusals():
    ck = CK.DecisionClock()
    d = date(2000, 1, 3)
    assert ck.close_at("commodity", d) < ck.published_at("commodity", d) <= ck.decided_at("commodity", d)
    days = FX.weekdays(10)
    assert ck.execution_rows("commodity", days, [0, 4, 8], 2).tolist() == [2, 6, -1]
    late = CK.DecisionClock(decision_delay=timedelta(hours=30))           # past the next weekday close
    with pytest.raises(BridgeError, match="next close"):
        late.execution_rows("commodity", days, [0], 1)
    with pytest.raises(BridgeError):
        CK.DecisionClock(settlement_publication=timedelta(hours=2), decision_delay=timedelta(hours=1))
    with pytest.raises(BridgeError):
        CK.DecisionClock(settlement_publication=timedelta(0))


# ================================================================== 3. volatility scaling at decision time
def test_weights_never_depend_on_returns_after_the_decision(null):
    W0 = B.translate(null, CLIP).weights
    for t in (320, 600, 1000):
        R = np.array(null.returns)
        R[t + 1:] *= 3.0
        R[t + 1:, 0] = -R[t + 1:, 0]
        alt = replace(null, returns=R)
        W1 = B.translate(alt, CLIP).weights
        assert np.array_equal(W0[: t + 1], W1[: t + 1], equal_nan=True)
        assert not np.array_equal(W0[t + 1:], W1[t + 1:], equal_nan=True)
        # HTE's own rule kept after shifting positions by the lag would have read the future
        naive0 = SC.series(null.positions, null.returns, warmup=300, fence=null.fence, lag=0, c=0, k=0).scale
        naive1 = SC.series(alt.positions, alt.returns, warmup=300, fence=null.fence, lag=0, c=0, k=0).scale
        i = t - 300 + 2                       # the earning period of decision row t + 1 at lag 1 ... reads g[:i]
        assert naive0[i] != naive1[i]


def test_lag_zero_weights_are_htes_same_close_scaled_positions(null):
    s0 = replace(CLIP, lag=0, allow_same_close=True)
    tr = B.translate(null, s0)
    ref = SC.series(null.positions, null.returns, warmup=300, fence=null.fence, lag=0, c=0, k=0)
    Pw, _ = SC.align_lagged(null.positions, null.returns, 300, null.fence, 0)
    assert np.array_equal(tr.weights[299:null.fence - 1], ref.scale[:, None] * Pw + 0.0)


# ================================================================== 4. contracts, rolls, caps, FX, costs, provenance
def test_contract_aware_execution_is_complete(null_out):
    r, tr = null_out.result, null_out.translation
    assert np.issubdtype(r.positions.dtype, np.integer)
    insts = {i.root: i for i in tr.panel.instruments}
    for f in r.fills[:200]:
        assert float(f.fill_price / insts[f.root].tick_size).is_integer() or abs(
            f.fill_price / insts[f.root].tick_size - round(f.fill_price / insts[f.root].tick_size)) < 1e-6
    legs = {f.leg for f in r.fills}
    assert {"outright", "roll_out", "roll_in"} <= legs and r.rolls
    t = r.totals()
    assert min(t["spread"], t["slippage"], t["impact"], t["commission"], t["exchange_fee"]) > 0
    assert np.array_equal(r.net, r.gross - r.costs)


def test_fx_roots_are_converted_and_costed():
    inp = FX.candidate("null", domain="rates", n=500)
    out = B.evaluate(inp, CLIP)
    eur = [i.root for i in out.translation.panel.instruments if i.currency == "EUR"]
    assert eur == ["HR01", "HR03"] and "EUR" in out.translation.panel.fx
    assert out.result.totals()["fx_conversion"] > 0 and not out.result.fx_conversion_unmodelled


def test_cost_provenance_and_readiness_are_preserved(null_out):
    a = null_out.assessment
    assert a.label == "screening_net" and a.cost_class == "scenario"
    assert any(u.startswith("R4") for u in a.unmet)
    src = null_out.result.cost_sources["HC00"]["half_spread_ticks"]
    assert src.kind == "scenario" and "HTE per-notional costs" in src.reference
    assert any("synthetic data" in w for w in a.warnings)
    with pytest.raises(XE.OptimisticExecutionError):
        RL.present_trading_return(null_out.result, [])


def test_matched_costs_reproduce_htes_per_notional_cost_at_the_match_point():
    from manhattan.execution_realism.costs import fill
    cm = MK.ContractMap()
    t = cm.templates["commodity"]
    inp = FX.candidate("null", n=400)
    panel = MK.contractise(inp.returns, inp.dates, "commodity", cm)
    costs = MK.hte_matched_costs(panel, cm, "commodity", c=4e-4, k=2e-3, capital=1e8)
    inst = panel.instruments[0]
    n = 300
    f = fill(inst, costs.for_root(inst.root), day=0, leg="outright", reason="decision", requested=n, quantity=n,
             ref=t.anchor_price, adv=t.adv_contracts, vol_points=t.nominal_daily_vol * t.anchor_price,
             liquidity_day=0)
    dW = n * t.anchor_price * inst.point_value / 1e8
    continuous = f.spread + f.slippage + f.impact + f.commission + f.exchange_fee
    assert continuous == pytest.approx((4e-4 * dW + 2e-3 * dW ** 1.5) * 1e8, rel=1e-9)
    with pytest.raises(BridgeError, match="fees alone"):
        MK.hte_matched_costs(panel, cm, "commodity", c=1e-6, k=0.0, capital=1e8)


# ================================================================== 5. identity
def test_execution_assumptions_are_in_the_executable_identity(null, null_out):
    spec = null_out.translation.spec
    assert spec["execution"]["replaces"] == ID.HTE_SAME_CLOSE and spec["bridge"] == ID.BRIDGE_VERSION
    base = null_out.identity
    assert base["data_hash"] == null.data_hash and base["market_digest"] == null_out.translation.panel.digest()
    variants = [replace(CLIP, lag=2), replace(CLIP, capital=5e7), replace(CLIP, sizing_rounding="toward_zero"),
                replace(CLIP, on_missing_price="hold"), replace(CLIP, on_liquidity_shortfall="raise"),
                replace(CLIP, vol_halflife=30), replace(CLIP, leverage_cap=3.0), replace(CLIP, commission=2.0),
                replace(CLIP, clock=CK.DecisionClock(decision_delay=timedelta(minutes=50))),
                replace(CLIP, contract_map=MK.ContractMap(roll_every=42)),
                replace(CLIP, lag=0, allow_same_close=True)]
    hashes = {ID.sha(B.translate(null, s).spec) for s in variants}
    assert len(hashes) == len(variants) and ID.sha(spec) not in hashes
    n, A = null.positions.shape
    sh = AD.Shocks("wide", spread=np.full((n, A), 2.0))
    assert ID.sha(B.translate(null, CLIP, shocks=sh).spec) != ID.sha(spec)
    with pytest.raises(ValueError):
        ID.executable_spec({"execution": "something_else/v9"}, {})


def test_reruns_are_deterministic(null):
    a, b = B.evaluate(null, CLIP), B.evaluate(FX.candidate("null"), CLIP)
    assert a.identity == b.identity
    assert np.array_equal(a.window_net, b.window_net) and a.result.result_hash() == b.result.result_hash()
    assert a.identity["result_hash"] == b.identity["result_hash"]
    assert B.pr85_decision_records(null, a, CLIP) == B.pr85_decision_records(null, b, CLIP)


# ================================================================== 6. planted effects
def test_a_same_close_effect_disappears_after_the_lag():
    cmp_ = CP.compare(FX.candidate("reversal"), CLIP)
    rows = cmp_["rows"]
    assert rows["hte_throughput"]["ratio"] > 2 and rows["contract_same_close"]["ratio"] > 1.5
    assert rows["hte_lagged"]["ratio"] < 0 and rows["contract_delayed"]["ratio"] < 0
    assert rows["hte_throughput"]["label"] == rows["contract_same_close"]["label"] == "throughput_only"
    assert cmp_["effects"]["timing_ratio"] > 4


def test_a_lag_robust_effect_disappears_after_costs():
    gross = CP.compare(FX.candidate("fast_edge", cost_multiplier=0.0), replace(CLIP, commission=0.0, exchange_fee=0.0))
    net = CP.compare(FX.candidate("fast_edge"), CLIP)
    assert gross["rows"]["contract_delayed"]["ratio"] > 0.5 and gross["rows"]["hte_lagged"]["ratio"] > 0.5
    assert net["rows"]["contract_delayed"]["ratio"] < 0 and net["rows"]["hte_lagged"]["ratio"] < 0


# ================================================================== 7. missing settlements, blocked rolls, clipping
def test_missing_settlements_raise_or_hold(null):
    miss = [(500, "HC02"), (501, "HC02"), (700, "HC00")]
    with pytest.raises(XE.MissingInputError):
        B.evaluate(null, CLIP, missing=miss)
    out = B.evaluate(null, replace(CLIP, on_missing_price="hold"), missing=miss)
    assert {(d, r) for d, r in out.result.stale_marks} == set(miss)
    assert np.array_equal(out.result.net, out.result.gross - out.result.costs)
    assert out.identity["market_digest"] != B.evaluate(null, replace(CLIP, on_missing_price="hold")).identity[
        "market_digest"]


def test_blocked_rolls_fail_closed(null):
    roll_row = 315                                               # 5 x 63: the held month changes at this close
    with pytest.raises(XE.RollError):
        B.evaluate(null, replace(CLIP, on_missing_price="hold"), missing=[(roll_row, "HC01")])
    n, A = null.positions.shape
    dry = np.ones((n, A))
    dry[roll_row - 1] = 1e-4                                     # the estimate the roll day's decision reads
    with pytest.raises(XE.RollError):
        B.evaluate(null, CLIP, adv_scale=dry)
    with pytest.raises(XE.LiquidityError):
        B.evaluate(null, replace(CLIP, on_liquidity_shortfall="raise"), adv_scale=dry)


def test_clipping_leaves_targets_unmet_and_is_reported(null, null_out):
    n, A = null.positions.shape
    dry = np.ones((n, A))
    for r in range(400, 1300):
        if r % 63 not in (62,):                                  # keep roll days liquid: only clipping here
            dry[r] = 0.002
    out = B.evaluate(null, CLIP, adv_scale=dry)
    assert len(out.result.unfilled) > 50 and all(u.why == "liquidity" for u in out.result.unfilled)
    assert not np.array_equal(out.result.positions, null_out.result.positions)
    assert any("not filled in full" in w for w in out.assessment.warnings)
    with pytest.raises(XE.LiquidityError):
        B.evaluate(null, replace(CLIP, on_liquidity_shortfall="raise"), adv_scale=dry)


# ================================================================== 8. comparison and decision records
def test_comparison_is_labelled_and_claims_nothing(null):
    cmp_ = CP.compare(null, CLIP)
    assert cmp_["verified_profitability"] is False and set(cmp_["rows"]) == set(CP.COLUMNS)
    assert cmp_["rows"]["hte_throughput"]["label"] == "throughput_only"
    assert cmp_["rows"]["contract_delayed"]["label"] == "screening_net"
    flat = repr(cmp_).lower()
    assert "p_value" not in flat and "significan" not in flat
    md = CP.render_markdown([cmp_], ["null"])
    assert CP.DISCLAIMER in md and md.count("| null |") == 4
    with pytest.raises(ValueError):
        CP.compare(null, replace(CLIP, lag=0, allow_same_close=True))


def test_pr85_decision_records_are_timestamped_after_the_close(null, null_out):
    recs = B.pr85_decision_records(null, null_out, CLIP)
    assert recs and {r["lag"] for r in recs} == {1}
    for r in recs[:50]:
        dec = datetime.fromisoformat(r["decided_at"])
        day = dec.date()
        assert dec > CK.DecisionClock().close_at("commodity", day)
        assert datetime.fromisoformat(r["inputs_known_at"]) <= dec


def test_from_hte_uses_the_callers_hte_functions_and_respects_the_fence(null):
    panel = SimpleNamespace(fence=1000, data_hash=null.data_hash, provenance=dict(null.provenance),
                            dates=np.array(null.dates, dtype="datetime64[D]"),
                            returns=lambda dom: null.returns[:1000])
    cache = SimpleNamespace(panel=panel)
    view = SimpleNamespace(describe=lambda i: {"domain": "commodity", "cost_model": "c2"},
                           candidate_hash=lambda i: "ab" * 32)
    inp = B.from_hte(view, 0, cache, signed_positions=lambda c, d: null.positions, fence=1000,
                     cost_coefficients=lambda dom, m: (FX.HTE_COSTS[dom][0] * m, FX.HTE_COSTS[dom][1] * m),
                     cost_models={"c1": 1.0, "c2": 2.0})
    assert inp.fence == 1000 and inp.hte_costs == (8e-4, 4e-3) and inp.dates[0] == date(2000, 1, 3)
    with pytest.raises(BridgeError):
        B.from_hte(view, 0, cache, signed_positions=lambda c, d: null.positions, fence=1100,
                   cost_coefficients=lambda dom, m: (0.0, 0.0), cost_models={"c2": 2.0})


# ================================================================== 9. cross-checks against the reviewed heads
def _from_checkout(env, sub):
    path = os.environ.get(env)
    if not path:
        pytest.skip(f"{env} not set (needs an unmerged branch checkout)")
    import manhattan
    extra = str(Path(path) / "manhattan")
    before = set(sys.modules)
    manhattan.__path__.append(extra)
    try:
        return importlib.import_module(f"manhattan.{sub}"), before
    finally:
        manhattan.__path__.remove(extra)


def _forget(before):
    for k in set(sys.modules) - before:
        if k.startswith("manhattan."):
            del sys.modules[k]


def test_cross_check_with_real_hte_candidates():
    K, before = _from_checkout("EXEC_REALISM_HTE_CHECKOUT", "hte.kernels")
    try:
        D = importlib.import_module("manhattan.hte.data")
        Fe = importlib.import_module("manhattan.hte.features")
        TP = importlib.import_module("manhattan.hte.templates")
        RU = importlib.import_module("manhattan.hte.runner")
        HP = importlib.import_module("manhattan.hte.policy")
        Hx = importlib.import_module("manhattan.hte.fixtures")
        assert K.EXECUTION_TIMING == ID.HTE_SAME_CLOSE
        for dom in ("commodity", "rates", "fx"):
            assert K.cost_coefficients(dom, 1.0) == FX.HTE_COSTS[dom]
        panel = D.generate(Hx.SMALL_PANEL)
        cache = Fe.FeatureCache(panel, enabled=True)
        hp = HP.Policy()
        for dom, tmpl, params in (("fx", "trend", {"lookback": 40, "shape": "sign", "vol_halflife": 20,
                                                   "rebalance": 1}),
                                  ("rates", "meanrev", {"lookback": 10, "entry": 1.0, "hold": 3})):
            d = {"template": tmpl, "domain": dom, "params": params, "cost_model": "c1", "sizing": "unit_risk",
                 "sign": "+"}
            view = SimpleNamespace(describe=lambda i, d=d: d, candidate_hash=lambda i: "cd" * 32)
            inp = B.from_hte(view, 0, cache, signed_positions=RU.signed_positions, fence=panel.fence,
                             cost_coefficients=K.cost_coefficients, cost_models=TP.COST_MODELS)
            Pw, Rw = K.align(RU.signed_positions(cache, d), panel.returns(dom), hp.warmup, panel.fence)
            c, k = K.cost_coefficients(dom, 1.0)
            ref = K.ref_stage3_series(Pw, Rw, c, k, hp)
            cmp_ = CP.compare(inp, CLIP)
            th = SC.series(inp.positions, inp.returns, warmup=hp.warmup, fence=panel.fence, lag=0, c=c, k=k)
            assert np.array_equal(th.net, ref)                  # the throughput column is HTE stage 3, bit for bit
            # the bridge's lag-0 decision weights are HTE's scale times its positions: bit for bit with HTE's
            # reference loop (whose net series matched above), and within a few ulps of HTE's vectorised kernel,
            # which sums each row with numpy's pairwise summation (HTE's own kernel and reference differ there)
            s3 = K.stage3_series([Pw], [Rw], [c], [k], hp)["scale"][0]
            tr0 = B.translate(inp, replace(CLIP, lag=0, allow_same_close=True))
            w0 = tr0.weights[hp.warmup - 1: panel.fence - 1]
            assert np.array_equal(w0, th.scale[:, None] * Pw + 0.0)
            eps4 = 4 * np.finfo(float).eps                           # a few ulps, never more
            assert np.allclose(w0, s3[:, None] * Pw, rtol=eps4, atol=0)
            assert np.max(np.abs(s3 - th.scale) / np.abs(th.scale)) <= eps4
            assert cmp_["rows"]["contract_delayed"]["label"] == "screening_net"
    finally:
        _forget(before)


def test_cross_check_with_pr85_on_bridge_output():
    X, before = _from_checkout("EXEC_REALISM_PR85_CHECKOUT", "execution")
    try:
        A_ = importlib.import_module("manhattan.execution.account")
        inp = FX.candidate("null", domain="rates", n=420, assets=2)
        cmap = MK.ContractMap(eur_assets={"rates": (1,)}, roll_every=10_000)     # one month, no roll in window
        st = replace(CLIP, contract_map=cmap, fx_conversion_bps=None)
        out = B.evaluate(inp, st)
        tr, res, ck = out.translation, out.result, st.clock
        pan = tr.panel
        cal = [X.TradingDay(d, ck.close_at("rates", d)) for d in pan.days]
        # PR #85's own execution_index on the bridge's timestamps
        mkt_cal = SimpleNamespace(calendar=cal)
        for t, e in zip(tr.decision_rows, tr.execution_rows):
            assert A_.execution_index(mkt_cal, ck.decided_at("rates", pan.days[int(t)]), 1) == e
        specs, setl, liq, fxr = [], [], [], []
        cid = {}
        for a, inst in enumerate(pan.instruments):
            c = X.contract_id(inst.root, "2099-12")
            cid[inst.root] = c
            specs.append(X.ContractSpec(c, inst.root, "SYNX", "2099-12", inst.currency, inst.tick_size,
                                        inst.tick_value, inst.multiplier, inst.price_unit_value, date(1999, 1, 4),
                                        date(2099, 12, 15), "cash"))
            for i, d in enumerate(pan.days):
                setl.append(X.Settlement(c, d, float(pan.level[i, a]), ck.published_at("rates", d)))
                liq.append(X.Liquidity(c, float(pan.adv[i, a]), float(pan.vol_points[i, a]), ck.close_at("rates", d)))
        for i, d in enumerate(pan.days):
            fxr.append(X.FxRate("EUR", "USD", d, float(pan.fx["EUR"][i]), ck.published_at("rates", d)))
        market = X.MarketData(calendar=cal, contracts=specs, settlements=setl, liquidity=liq, fx=fxr)
        decs = [X.Decision(r["root"], r["contracts"], datetime.fromisoformat(r["decided_at"]),
                           inputs_known_at=datetime.fromisoformat(r["inputs_known_at"]))
                for r in B.pr85_decision_records(inp, out, st)]
        terms = []
        for root, t in tr.costs.terms:
            terms.append((root, X.CostTerms(t.fee_currency, t.commission.value, t.exchange_fee.value,
                                             t.half_spread_ticks.value, t.slippage_ticks.value,
                                             t.impact_coefficient.value, t.max_participation.value, 0.0)))
        ref = X.run(market, decs, X.ExecutionPolicy("USD", X.RollPolicy(35, 10), lag=1,
                                                    on_liquidity_shortfall="clip"),
                    X.CostScenario("bridge cross-check", "synthetic", tuple(terms)))
        assert len(ref.days) == pan.shape[0]
        for i, day in enumerate(ref.days):
            assert res.gross[i].sum() == pytest.approx(day.gross, abs=1e-6), i
            assert res.costs[i].sum() == pytest.approx(day.costs, abs=1e-6), i
            pos = {cid[r]: int(res.positions[i, a]) for a, r in enumerate(pan.roots) if res.positions[i, a]}
            assert dict(day.positions) == pos, i
        assert sum(1 for f in ref.fills if f.filled) == sum(1 for f in res.fills if f.filled) > 0
    finally:
        _forget(before)
