"""S16 phase 2: acceptance of delayed-execution HTE -> PR #93 integration.

Two groups:

* ``CON93-*``: contract tests on PR #93 alone (execution_realism). They run as soon as #93 is in the tree:
  - lag semantics;
  - cost and lag assumptions in the result identity;
  - causality and look-ahead;
  - the volatility-target trap;
  - same-close leakage and its labelling;
  - provenance.
* ``DEX93-*``: the HTE -> #93 integration, run against a driver as in test_s16_acc86.py. The ``adapter`` run is
  BLOCKED until an HTE <-> #93 binding exists (PR #93 X5), and UNBOUND until it is bound in s16_drivers.py. The
  ``oracle`` run (``ORC-DEX93-*``) composes PR #90's identity functions with PR #93's ``screening.series``. It is
  test-only and never stands in for the adapter.
"""
from __future__ import annotations

import hashlib
import shutil

import numpy as np
import pytest

import s16_drivers as DRV

acc = pytest.mark.acceptance
X93 = ("execution_realism",)
COMPONENTS = ("hte", "execution_realism", "hte_identity_levels")
P = DRV.driver_params


def _world():
    from manhattan.execution_realism import fixtures as FX
    return FX, FX.world(n=300)


def _run(panel, costs, lag=1, *, weights, capital=1e7, allow=False, shocks=None, missing="raise"):
    from manhattan.execution_realism import ExecutionPolicy, ExecutionTiming, execute
    pol = ExecutionPolicy(capital=capital, timing=ExecutionTiming(lag, allow_same_close=allow),
                          on_liquidity_shortfall="clip", on_missing_price=missing)
    return execute(panel, costs, pol, weights=weights, shocks=shocks)


# ============================================================================================ PR #93 contracts

@acc(id="CON93-01", area="execution", requires=X93)
def test_con93_01_delay_is_the_default_and_same_close_is_opt_in_and_labelled():
    from manhattan.execution_realism import DEFAULT_LAG, ExecutionPolicy, ExecutionTiming
    from manhattan.execution_realism.errors import OptimisticExecutionError
    import manhattan.execution_realism as XR
    assert DEFAULT_LAG >= 1 and ExecutionTiming().lag >= 1 and ExecutionPolicy(capital=1e6).lag >= 1
    assert XR.RESEARCH_ONLY is True and XR.CALIBRATED is False
    with pytest.raises(OptimisticExecutionError):
        ExecutionTiming(0)
    FX, w = _world()
    r0 = _run(w, FX.synthetic_costs(), 0, weights=FX.trend_weights(w), allow=True)
    s0 = r0.summary()
    assert s0["label"] == "throughput_only" and s0["realistic_return_claims"] is False
    assert all(k.startswith("same_close_optimistic_") for k in s0["stats"])
    s1 = _run(w, FX.synthetic_costs(), 1, weights=FX.trend_weights(w)).summary()
    assert s1["realistic_return_claims"] is False and not any(k.startswith("same_close") for k in s1["stats"])


@acc(id="CON93-02", area="identity", requires=X93)
def test_con93_02_cost_and_lag_assumptions_are_in_the_result_identity():
    from manhattan.execution_realism import Shocks
    FX, w = _world()
    W = FX.trend_weights(w)
    base_costs = FX.synthetic_costs()
    h = lambda **kw: _run(w, kw.pop("costs", base_costs), kw.pop("lag", 1), weights=W, **kw).result_hash()  # noqa
    ref = h()
    assert h() == ref                                                         # deterministic
    others = {"lag 2": h(lag=2), "costs x2": h(costs=base_costs.scaled(2.0)),
              "capital": h(capital=2e7), "fixture sources": h(costs=FX.fixture_sourced_costs()),
              "shock": h(shocks=Shocks("s16", spread=np.full(w.shape, 2.0)))}
    # an assumption that changes no output here (no price is missing) must still change the identity
    quiet = _run(w, base_costs, 1, weights=W, missing="hold")
    assert quiet.totals() == _run(w, base_costs, 1, weights=W).totals()
    others["missing-price policy"] = quiet.result_hash()
    for what, x in others.items():
        assert x != ref, f"{what} is not reflected in the result identity"
    # the cost model's id is a content address: a new name changes nothing, any term or source changes it
    assert base_costs.model_id() == FX.synthetic_costs(name="renamed").model_id()
    assert base_costs.model_id() != base_costs.scaled(1.01).model_id()
    assert base_costs.model_id() != FX.fixture_sourced_costs().model_id()


@acc(id="CON93-03", area="lookahead", requires=X93)
def test_con93_03_lagged_series_is_causal():
    from manhattan.execution_realism import screening as S
    rng = np.random.default_rng(16)
    n, A, Wu = 400, 3, 120
    Pm = np.sign(rng.normal(size=(n, A)))
    R = rng.normal(0, 0.01, size=(n, A))
    kw = dict(warmup=Wu, fence=n, c=1e-4, k=1e-4)
    for lag in (1, 2, 5):
        base = S.series(Pm, R, lag=lag, **kw).net
        t = 250                                                               # decision rows >= t changed
        P2 = Pm.copy()
        P2[t:] = -P2[t:]
        alt = S.series(P2, R, lag=lag, **kw).net
        first = t - Wu + 1 + lag                                              # first earning period they reach
        assert np.array_equal(base[:first], alt[:first]), lag                 # nothing earlier saw them
        assert not np.array_equal(base[first:first + 1], alt[first:first + 1]), lag
        j = 300                                                               # realised returns >= j changed
        R2 = R.copy()
        R2[j:] *= -3.0
        alt = S.series(Pm, R2, lag=lag, **kw).net
        assert np.array_equal(base[: j - Wu], alt[: j - Wu]) and not np.array_equal(base[j - Wu], alt[j - Wu])
    from manhattan.execution_realism.errors import UnitError
    with pytest.raises(UnitError):
        S.align_lagged(Pm, R, 3, n, 5)                                        # no decision row before the window


@acc(id="CON93-04", area="lookahead", requires=X93)
def test_con93_04_the_volatility_scale_moves_with_the_decision():
    """PR #93 I7: a lagged position must be scaled with returns its decision could see."""
    from manhattan.execution_realism import screening as S
    rng = np.random.default_rng(7)
    g = rng.normal(0, 0.01, 300)
    act = np.ones(300, bool)
    kw = dict(halflife=20, min_obs=20, target_daily=0.10 / np.sqrt(252), cap=5.0)
    for lag in (1, 3):
        s = S.lagged_scales(g, act, lag=lag, **kw)
        j = 150
        g2 = g.copy()
        g2[j:] *= 10.0
        s2 = S.lagged_scales(g2, act, lag=lag, **kw)
        assert np.array_equal(s[: j + 1 + lag], s2[: j + 1 + lag])           # s[i] reads g[: i - lag] only
        assert not np.array_equal(s[j + 1 + lag:], s2[j + 1 + lag:])


@acc(id="CON93-05", area="lookahead", requires=X93)
def test_con93_05_same_close_leakage_is_measured_and_never_presented():
    from manhattan.execution_realism import present_trading_return, sensitivity
    from manhattan.execution_realism.errors import OptimisticExecutionError
    FX, w = _world()
    W = FX.reversal_weights(w)                                                # a planted same-close-only effect
    r0 = _run(w, FX.synthetic_costs(), 0, weights=W, allow=True)
    r1 = _run(w, FX.synthetic_costs(), 1, weights=W)
    sr0 = r0.summary()["stats"]["same_close_optimistic_sharpe"]
    sr1 = r1.summary()["stats"]["sharpe"]
    assert sr0 > 2.0 and sr1 < sr0 - 2.0                                       # the gain exists only at the close
    rows = sensitivity.grid(w, FX.synthetic_costs(), r1_policy(), weights=W)
    for res in (r0, r1):
        with pytest.raises(OptimisticExecutionError):                         # synthetic and/or same-close
            present_trading_return(res, rows)


def r1_policy():
    from manhattan.execution_realism import ExecutionPolicy
    return ExecutionPolicy(capital=1e7, on_liquidity_shortfall="clip")


@acc(id="CON93-06", area="promotion", requires=X93)
@pytest.mark.parametrize("kind", ["calibrated", "realistic", "actual", "measured", "live"])
def test_con93_06_no_cost_can_claim_calibration(kind):
    from manhattan.execution_realism import Source
    from manhattan.execution_realism.errors import ProvenanceError
    with pytest.raises(ProvenanceError):
        Source(kind, "S16 acceptance: must be refused")


# ===================================================================================== HTE -> #93 integration

class _Returns:
    """Realised returns replaced from row ``j`` on (for causality probes); positions are untouched."""
    def __init__(self, panel, j, factor):
        self.panel, self.j, self.factor = panel, j, factor

    def returns(self, dom):
        r = np.array(self.panel.returns(dom), copy=True)
        r[self.j:] *= self.factor
        return r


def _stage3_computed(e):
    from manhattan.hte import store
    from manhattan.hte.runner import S3
    t = store.read_arrays(e["ws"].run_dir(e["out"]["run_id"]) / "results.bin", e["out"]["results_sha256"])
    return t, [i for i in range(t["s3"].shape[0]) if t["s3"][i] == S3["computed"]]


@pytest.mark.parametrize("which", P("delayed", "DEX93-01", "execution", COMPONENTS))
def test_dex93_01_lag_zero_reproduces_hte_and_lag_one_does_not(which, hte_null_experiment):
    """Conformance: at lag 0 (explicitly allowed) the integration reproduces HTE's arithmetic: bit for bit against
    HTE's reference kernel, and within 1e-12 of HTE's results of record, whose hashes come from the vectorised
    kernel. At lag 1 every computed candidate's series differs."""
    from manhattan.hte import kernels, templates as TP
    from manhattan.hte.runner import signed_positions
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("delayed", which)
    t, idx = _stage3_computed(e)
    assert idx
    for i in idx:
        d = r.view.describe(i)
        Pw, Rw = kernels.align(signed_positions(r.cache, d), r.panel.returns(d["domain"]), r.policy.warmup,
                               r.panel.fence)
        c, k = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
        ref = kernels.ref_stage3_series(Pw, Rw, c, k, r.policy)
        vec = kernels.stage3_series([Pw], [Rw], [c], [k], r.policy)["net"][0]
        assert hashlib.sha256(vec.tobytes()).digest() == bytes(t["series_sha256"][i])   # HTE's record
        z = drv.evaluate(r, i, lag=0, allow_same_close=True)
        assert np.array_equal(z["net"], ref), i
        assert np.max(np.abs(z["net"] - vec)) <= 1e-12, i
        one = drv.evaluate(r, i, lag=1)
        assert one["lag"] == 1 and not np.array_equal(one["net"], z["net"]), i


@pytest.mark.parametrize("which", P("delayed", "DEX93-02", "identity", COMPONENTS))
def test_dex93_02_lag_and_costs_are_in_the_executable_identity(which, hte_null_experiment, tmp_path):
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner, Workspace
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("delayed", which)
    acct = DRV.OracleAccounting()
    for i in (0, 41, 119):
        same_close = acct.identity(r, i)                                      # HTE's own same-close executable
        ids_ = {(lag, m): drv.identity(r, i, lag=lag, cost_multiplier=m, allow_same_close=(lag == 0))
                for lag in (0, 1, 2) for m in (1.0, 2.0)}
        hashes = [x["spec_hash"] for x in ids_.values()]
        assert len(set(hashes)) == len(hashes), "two lag/cost assumptions share an executable"
        assert same_close["spec_hash"] not in {ids_[(lag, m)]["spec_hash"] for lag in (1, 2) for m in (1.0, 2.0)}
        for x in ids_.values():                                               # one scientific candidate throughout
            assert (x["family"], x["hypothesis"], x["variant"]) == (same_close["family"], same_close["hypothesis"],
                                                                    same_close["variant"])
            assert x["executable"] == x["spec_hash"] and x["role"] == "exploration" and x["designated"] is False
        a = drv.identity(r, i, lag=1)
        b = drv.identity(r, i, lag=1, code=DRV.code_of(r, engine="e" * 64))
        c = drv.identity(r, i, lag=1, code=DRV.code_of(r, env_core="S16OtherCore"))
        assert len({a["spec_hash"], b["spec_hash"], c["spec_hash"]}) == 3
        assert a["binding"] == b["binding"] == c["binding"]                   # engine/environment: same evaluation
    shutil.copytree(e["ws"].root, tmp_path / "copy")
    r2 = Runner(Workspace(tmp_path / "copy"), e["panel"], Policy(), chunk_size=9)
    assert drv.identity(r2, 7, lag=1) == drv.identity(r, 7, lag=1)            # deterministic across processes' state


@pytest.mark.parametrize("which", P("delayed", "DEX93-03", "lookahead", COMPONENTS))
def test_dex93_03_delayed_results_never_see_the_future(which, hte_null_experiment):
    from manhattan.execution_realism.errors import OptimisticExecutionError
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("delayed", which)
    with pytest.raises(OptimisticExecutionError):
        drv.evaluate(r, 3, lag=0)                                             # same close is never implicit
    _, idx = _stage3_computed(e)
    W, F = r.policy.warmup, r.panel.fence
    j = (W + F) // 2
    for i in idx[:12]:
        for lag in (1, 2):
            base = drv.evaluate(r, i, lag=lag)
            assert base["label"] != "same_close_fill_next_day_return/v1"
            alt = drv.evaluate(r, i, lag=lag, panel=_Returns(r.panel, j, -2.0))
            assert np.array_equal(base["net"][: j - W], alt["net"][: j - W]), (i, lag)


@pytest.mark.parametrize("which", P("delayed", "DEX93-04", "statistics", COMPONENTS))
def test_dex93_04_planted_effect_survives_delay_in_its_predicted_direction(which, hte_planted_experiment):
    """The planted synthetic trend depends on returns up to t-1 only, so it must survive a one-day delay; a result
    that vanished at lag 1 would mean the integration mis-aligned positions and returns."""
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner
    e = hte_planted_experiment
    r = Runner(e["ws"], e["panel"], Policy(), chunk_size=64)
    drv = DRV.get("delayed", which)
    trend = [i for i in range(len(r.view)) if r.view.describe(i)["template"] == "trend"]
    assert trend
    mean = lambda x: float(np.mean(x))                                        # noqa: E731
    lag1 = [mean(drv.evaluate(r, i, lag=1, cost_multiplier=0.0)["net"]) for i in trend]
    assert np.median(lag1) > 0, "the planted effect disappeared at lag 1"


@pytest.mark.parametrize("which", P("delayed", "DEX93-05", "accounting", COMPONENTS + ("access",)))
def test_dex93_05_delayed_evaluations_are_separate_looks_and_retry_only_identically(which, hte_null_experiment,
                                                                                   tmp_path):
    from datetime import date
    from manhattan import access, attempts as A, ledger as L, roles
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("delayed", which)
    book = L.Ledger(tmp_path / "ledger.jsonl", writer="s16-dex93", protocol="0" * 64)
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)

    def ident(**kw):
        x = drv.identity(r, 11, **kw)
        return {k: x[k] for k in L.IDENTITY_FIELDS}

    def register(x, supersedes=None):
        w = x["window"]
        dw = access.DeclaredWindow(w["id"], DRV.HTE_DOMAIN, date.fromisoformat(w["start"]),
                                   date.fromisoformat(w["end"]), "exploration", "evaluation", x["data_hash"])
        return access.register_evaluation(book, identity=x, windows=[dw], caller=roles.RUNNER, fence=fence,
                                          supersedes=supersedes).attempt_id

    def complete(x, aid, res):
        return book.record_evaluation(**x, result_hash=res, n_obs=1, summary={}, seed=0, attempt_id=aid)

    def res_hash(**kw):
        return hashlib.sha256(drv.evaluate(r, 11, **kw)["net"].tobytes()).hexdigest()

    looks = [dict(lag=1), dict(lag=2), dict(lag=1, cost_multiplier=2.0), dict(lag=0, allow_same_close=True)]
    for kw in looks:
        x = ident(**kw)
        assert complete(x, register(x), res_hash(**kw))["type"] == "evaluation", kw
    x = ident(lag=1)
    assert complete(x, register(x), res_hash(lag=1))["type"] == "rerun"
    assert book.looks() == len(looks) and book.suspended_families() == set()
    first = register(ident(lag=1))                                            # interrupted
    with pytest.raises(L.LedgerError):
        register(ident(lag=2), supersedes=first)                              # a retry cannot change the lag
    with pytest.raises(L.LedgerError):
        register(ident(lag=1, cost_multiplier=2.0), supersedes=first)         # nor the costs
    retry = register(ident(lag=1), supersedes=first)
    assert complete(ident(lag=1), retry, res_hash(lag=1))["type"] == "rerun"
    rep = A.reconcile(ledger_path=book.path, ledger_anchor={"records": len(book), "head": book.head})
    assert rep["access_reconciled"] and rep["violations"] == [] and rep["retries"] == 1


@pytest.mark.parametrize("which", P("delayed", "DEX93-06", "identity", COMPONENTS))
def test_dex93_06_delayed_results_are_deterministic(which, hte_null_experiment):
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("delayed", which)
    _, idx = _stage3_computed(e)
    for i in idx[:8]:
        a, b = drv.evaluate(r, i, lag=1), drv.evaluate(r, i, lag=1)
        assert a["net"].tobytes() == b["net"].tobytes() and a["identity"] == b["identity"]
