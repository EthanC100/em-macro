"""Drivers for the S16 integration-adapter acceptance tests (phase 2).

Every adapter acceptance test runs against a *driver*, the narrow interface the test needs:

    AccountingDriver   candidate-level HTE -> PR #86 accounting: identity, lineage, register, complete
    DelayedDriver      HTE -> PR #93 delayed execution: evaluate a candidate at a lag, and its identity

Two kinds of driver:

* ``adapter``: the real integration adapter (S11 for PR #86, S14 for PR #93). While the adapter does not exist the
  test is BLOCKED by its capability probe. When the probe finds it, ``get`` fails the test as UNBOUND until a binding
  to the adapter's real API is written in ``ADAPTER_BINDINGS`` below. S16 never guesses that API, so an adapter that
  exists but is unbound can never pass.
* ``oracle``: a **test-only reference** composed from the components' public functions:
  - PR #90: ``to_pr86_identity``, ``lineage``, ``evaluation_spec`` and ``executable_spec``;
  - PR #86: ``access.register_evaluation`` and ``Ledger.record_evaluation``;
  - PR #93: ``ExecutionTiming`` and ``screening.series``.

  It is not an adapter and nothing outside tests/acceptance imports it. Running the tests against it shows that
  each test can pass on a correct implementation. The mutation check also plants defects in it, which shows that
  each test fails on a broken one. Its results are reported under ``ORC-*`` ids, never under the adapter's ids.
"""
from __future__ import annotations

from datetime import date

import s16_capabilities as CAP

ORACLE, ADAPTER = "oracle", "adapter"
HTE_DOMAIN = "hte-synthetic"

# The real adapters, once they exist: kind -> zero-argument factory returning a driver. Filled in only when S11/S14's
# adapter API is merged and reviewed; until then an adapter that a probe finds present fails as UNBOUND.
ADAPTER_BINDINGS: dict = {"accounting": None, "delayed": None}
ADAPTER_CAPABILITY = {"accounting": "adapter:hte->access", "delayed": "adapter:hte->delayed-execution"}


def window_of(runner) -> dict:
    """The evaluation window of an HTE run as PR #86 window identity (synthetic dates, warm-up to fence)."""
    d = runner.panel.dates
    return {"id": f"{runner.run_id}:eval", "start": str(d[runner.policy.warmup]), "end": str(d[runner.panel.fence - 1]),
            "frequency": "daily"}


def code_of(runner, *, engine: str | None = None, env_core: str | None = None) -> dict:
    """The runner's real code identity, optionally with another engine digest or BLAS core (a different numerical
    environment, accounted for explicitly)."""
    from manhattan.hte import ids
    code = dict(runner.code)
    if not isinstance(code.get("commit"), str) or len(code.get("commit") or "") != 40:
        code["commit"] = "5" * 40                      # a synthetic commit: the workspace may not be a git checkout
    if engine is not None:
        code["engine_sha256"] = engine
    if env_core is not None:
        env = dict(code["numeric_environment"])
        env["blas"] = dict(env.get("blas") or {}, runtime_core=env_core)
        code["numeric_environment"] = env
        code["numeric_environment_sha256"] = ids.full_hash(env)
    return code


# ------------------------------------------------------------------------------------------- accounting (PR #86)

class OracleAccounting:
    """Candidate-level registration: one PR #86 engine-evaluation attempt per HTE candidate (B4 option "one attempt
    per candidate"), registered before the completion, exploration role only."""
    name = ORACLE

    def identity(self, runner, i, *, code=None, policy=None):
        from manhattan.hte import adapters
        return adapters.to_pr86_identity(runner.view, i, run_id=runner.run_id, data_hash=runner.data_hash,
                                         code=code or code_of(runner), window=window_of(runner),
                                         policy=policy or runner.policy, fence=runner.panel.fence)

    def lineage(self, runner, i, *, code=None, policy=None):
        from manhattan.hte import adapters
        return adapters.lineage(runner.view, i, code=code or code_of(runner), policy=policy or runner.policy,
                                fence=runner.panel.fence)

    def register(self, ledger, runner, i, *, code=None, policy=None, supersedes=None) -> str:
        from manhattan import access, roles
        ident = self.identity(runner, i, code=code, policy=policy)
        w = ident["window"]
        dw = access.DeclaredWindow(w["id"], HTE_DOMAIN, date.fromisoformat(w["start"]), date.fromisoformat(w["end"]),
                                   "exploration", "evaluation", ident["data_hash"])
        fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
        ctx = access.register_evaluation(ledger, identity=ident, windows=[dw], caller=roles.RUNNER, fence=fence,
                                         supersedes=supersedes)
        return ctx.attempt_id

    def complete(self, ledger, runner, i, attempt_id, result_hash, *, code=None, policy=None) -> dict:
        ident = self.identity(runner, i, code=code, policy=policy)
        return ledger.record_evaluation(**ident, result_hash=result_hash, n_obs=int(runner.panel.fence
                                                                                    - runner.policy.warmup),
                                        summary={}, seed=0, attempt_id=attempt_id)

    def account_run(self, ledger, runner, result_hashes: dict, *, code=None) -> dict:
        out = {}
        for i in range(len(runner.view)):
            aid = self.register(ledger, runner, i, code=code)
            self.complete(ledger, runner, i, aid, result_hashes[i], code=code)
            out[i] = aid
        return out


# ------------------------------------------------------------------------------------- delayed execution (PR #93)

class OracleDelayed:
    """A candidate's positions from HTE, executed by PR #93's lagged HTE-shaped tier. Its identity is HTE's binding
    with the execution convention, lag and cost assumptions it actually used; the executable adds engine and
    numerical environment, as PR #90's executable_spec does."""
    name = ORACLE
    MODEL = "manhattan.execution_realism.screening.series/1"

    def _costs(self, runner, i, cost_multiplier):
        from manhattan.hte import kernels, templates as TP
        d = runner.view.describe(int(i))
        c, k = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
        return d, c * cost_multiplier, k * cost_multiplier

    def evaluate(self, runner, i, *, lag: int, cost_multiplier: float = 1.0, allow_same_close: bool = False,
                 panel=None) -> dict:
        """``panel``: an object with ``returns(domain)`` replacing the realised returns (positions still come from the
        run's own panel): used to probe causality."""
        from manhattan.execution_realism import ExecutionTiming, screening
        from manhattan.hte.runner import signed_positions
        ExecutionTiming(lag, allow_same_close=allow_same_close)          # lag 0 refused unless explicitly allowed
        d, c, k = self._costs(runner, i, cost_multiplier)
        P = signed_positions(runner.cache, d)
        R = (panel or runner.panel).returns(d["domain"])
        pol = runner.policy
        res = screening.series(P, R, warmup=pol.warmup, fence=runner.panel.fence, lag=lag, c=c, k=k,
                               vol_target_ann=pol.vol_target_ann, vol_halflife=pol.vol_halflife,
                               vol_min_obs=pol.vol_min_obs, leverage_cap=pol.leverage_cap)
        return {"net": res.net, "scale": res.scale, "lag": res.lag,
                "label": ExecutionTiming(lag, allow_same_close=allow_same_close).label,
                "identity": self.identity(runner, i, lag=lag, cost_multiplier=cost_multiplier,
                                          allow_same_close=allow_same_close)}

    def binding_spec(self, runner, i, *, lag: int, cost_multiplier: float = 1.0,
                     allow_same_close: bool = False) -> dict:
        from manhattan.execution_realism import ExecutionTiming
        from manhattan.hte import adapters
        _, c, k = self._costs(runner, i, cost_multiplier)
        spec = adapters.evaluation_spec(runner.view, i, policy=runner.policy, fence=runner.panel.fence)
        spec["execution"] = {**ExecutionTiming(lag, allow_same_close=allow_same_close).as_dict(), "model": self.MODEL}
        spec["costs"] = {"linear": c, "impact": k, "impact_power": 1.5, "multiplier": cost_multiplier}
        return spec

    def identity(self, runner, i, *, lag: int, cost_multiplier: float = 1.0, allow_same_close: bool = False,
                 code=None) -> dict:
        from manhattan.hte import adapters, ids
        code = code or code_of(runner)
        binding = ids.full_hash(self.binding_spec(runner, i, lag=lag, cost_multiplier=cost_multiplier,
                                                  allow_same_close=allow_same_close))
        exe = ids.full_hash(adapters.executable_spec(binding, code))
        base = adapters.to_pr86_identity(runner.view, i, run_id=runner.run_id, data_hash=runner.data_hash, code=code,
                                         window=window_of(runner), policy=runner.policy, fence=runner.panel.fence)
        return {**base, "executable": exe, "spec_hash": exe, "binding": binding, "lag": lag}


# --------------------------------------------------------------------------------------------------------- access

def get(kind: str, which: str):
    """The driver for ``kind`` (accounting | delayed). The adapter driver is reached only when its capability probe
    passed (the test's ``requires`` already BLOCKED it otherwise); with no binding it fails as UNBOUND."""
    if which == ORACLE:
        return {"accounting": OracleAccounting, "delayed": OracleDelayed}[kind]()
    factory = ADAPTER_BINDINGS.get(kind)
    if factory is None:
        from s16_helpers import unbound
        unbound(ADAPTER_CAPABILITY[kind], f"bind the real {kind} adapter in tests/acceptance/s16_drivers.py "
                                          f"ADAPTER_BINDINGS[{kind!r}] (driver interface: see Oracle"
                                          f"{'Accounting' if kind == 'accounting' else 'Delayed'})")
    return factory()


def driver_params(kind: str, aid: str, area: str, requires: tuple):
    """pytest params for one acceptance test: the adapter (id ``aid``) and the oracle (id ``ORC-aid``)."""
    import pytest
    cap = ADAPTER_CAPABILITY[kind]
    return [pytest.param(ADAPTER, id="adapter", marks=pytest.mark.acceptance(id=aid, area=area,
                                                                            requires=requires + (cap,))),
            pytest.param(ORACLE, id="oracle", marks=pytest.mark.acceptance(id=f"ORC-{aid}", area="harness",
                                                                          requires=requires))]


assert set(ADAPTER_CAPABILITY.values()) <= set(CAP.PROBES)
