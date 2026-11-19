"""Translate one HTE candidate into the execution-realism adapter's inputs, run it, and identify the run.

    inp = from_hte(view, i, cache, signed_positions=runner.signed_positions,
                   cost_coefficients=kernels.cost_coefficients, cost_models=templates.COST_MODELS, fence=fence)
    out = evaluate(inp, BridgeSettings())            # lag 1, next available settlement, never same close

**The translation, row by row** (``F`` the fence, ``W`` the warm-up, ``L`` the lag):

| HTE | adapter / PR #85 |
|---|---|
| ``signed_positions(cache, describe(i))[t]``: weight held from close ``t``, data through close ``t`` | a decision at ``decided_at = close_t + decision_delay`` (``clock.py``) |
| HTE stage-3 vol scale ``s[i]`` from ``g[:i]`` | the decision-time scale from ``g[:i − L]`` (``scaling.py``) |
| weight ``s × P[t]`` | whole contracts ``round(w × capital / (|S_t| × point value × fx_t))`` at row ``t`` |
| fill at close ``t`` (same close) | fill at the settlement of ``t + L``, the ``L``-th close strictly after ``decided_at`` |
| ``panel.returns(domain)`` | tick-grid settlements of a synthetic held month, rolls, ADV, vol known at close, FX (``market.py``) |
| ``kernels.COSTS[domain] × COST_MODELS[cost_model]`` | ``hte_matched_costs``: per-contract terms with ``scenario`` provenance |
| ``evaluation_spec["execution"] = "same_close_fill_next_day_return/v1"`` | the full execution block (``identity.py``) |

Only decision rows ``[W − 1 − L, F − 1 − L)`` carry decisions, so the positions earn exactly HTE's evaluation
window ``[W, F)``. The window's net series adds the entry day's costs (day ``W − 1``) to its first day, HTE's
convention (I5 in docs/manhattan/EXECUTION_REALISM.md). No row at or past the fence exists in the panel.

**Dormant.** ``ENABLED`` is ``False``. Inputs must carry synthetic provenance; ``HteExecutionStage`` (the hook a
connected HTE would call) refuses construction and lists ``CONNECTION_REQUIREMENTS``. Nothing imports this
package; it imports neither HTE nor PR #85 (HTE's functions are passed in by the caller).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import numpy as np

from manhattan.execution_realism import adapter as AD
from manhattan.execution_realism import realism as RL
from manhattan.execution_realism.costs import CostModel
from manhattan.execution_realism.timing import ExecutionTiming

from . import identity as ID
from .clock import DecisionClock, as_dates
from .errors import BridgeDisabled, BridgeError
from .market import ContractMap, contractise, hte_matched_costs
from .scaling import decision_weights

ENABLED = False
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

CONNECTION_REQUIREMENTS = (
    ("C1", "PR #85 and PR #93 merged; the #93 conformance tests made permanent (no checkout skip), or the "
           "adapter's fill delegated to PR #85's fill_order (manhattan/execution/costs.py)."),
    ("C2", "PR #89 merged. HTE gains a policy field `lag` (default 1) and a contract-execution stage that calls "
           "this bridge only on stage-3 representatives (aliases copy results). HTE's own stage-3 vol scale is "
           "replaced by the decision-time scale (scaling.py), and `kernels.EXECUTION_TIMING` in "
           "`run_identity` and `evaluation_spec` is replaced by `identity.executable_spec`."),
    ("C3", "PR #86 attempt accounting merged, with owner decisions D-1, D-10 and B4 made. The attempt identity's "
           "`spec_hash` is the bridge's `spec_hash`; `data_hash` and `market_digest` are both recorded "
           "(PR #85 design section 16 item 6)."),
    ("C4", "A deterministic, private panel builder from em-macro-data settlements with `known_at` times, "
           "contract metadata history and roll dates from PR #85's RollPolicy, replacing `market.contractise`. "
           "Only digests and aggregates may be public (CLAUDE.md hard rule 7). The same `data_hash` must always "
           "give the same `market_digest`."),
    ("C5", "Cost terms with `recorded` or `published_schedule` sources valid for the window (Protocol v3.1 "
           "section 10), replacing `hte_matched_costs`. Until then results stay `screening_net`."),
    ("C6", "Point-in-time ADV and volatility per contract month, stamped with when they were known."),
    ("C7", "Per-exchange close times and publication delays from availability records (manhattan/availability.py), "
           "replacing `DecisionClock`'s synthetic defaults; the decision must still precede the next close."),
    ("C8", "Roll-binding and opening-month cases (#93 divergences D1, D2) routed to PR #85's run, or accepted as "
           "fail-closed and counted."),
    ("C9", "Pre-registration of the execution methodology (lag, clock, vol rule, cost sources, sensitivity rows) "
           "before any use on exploration data: Ethan's decision (CLAUDE.md hard rule 4)."),
    ("C10", "The synthetic-only guard (`CandidateInput`, `ENABLED`) lifted only by a change Ethan approves. "
            "`config/manhattan.yaml` switches (claims, reserve, real money) stay as they are."),
)


@dataclass(frozen=True, eq=False)
class CandidateInput:
    candidate_hash: str
    domain: str
    positions: np.ndarray           # (fence, A) HTE signed positions; row t decided from data through close t
    returns: np.ndarray             # (fence, A) HTE returns; r[t] realised over day t
    dates: tuple                    # fence trading days
    data_hash: str                  # HTE panel data hash
    provenance: dict                # must say synthetic
    hte_costs: tuple                # (c, k) per unit notional for this candidate's domain and cost model
    hte_spec: dict | None = None    # HTE adapters.evaluation_spec, if available

    def __post_init__(self):
        if not (isinstance(self.provenance, dict) and self.provenance.get("synthetic") is True):
            raise BridgeDisabled("the bridge is dormant and accepts synthetic panels only (CONNECTION_REQUIREMENTS "
                                 "C4, C10)")
        P = np.array(self.positions, float, copy=True)
        R = np.array(self.returns, float, copy=True)
        if P.ndim != 2 or P.shape != R.shape:
            raise BridgeError("positions and returns must have the same (days, assets) shape")
        days = as_dates(self.dates)
        if len(days) != P.shape[0]:
            raise BridgeError("one date per row")
        if not _HEX64.match(str(self.data_hash)):
            raise BridgeError("data_hash is a 64-hex SHA-256")
        c, k = self.hte_costs
        if not (c >= 0 and k >= 0):
            raise BridgeError("HTE cost coefficients are non-negative")
        for x in (P, R):
            x.setflags(write=False)
        object.__setattr__(self, "positions", P)
        object.__setattr__(self, "returns", R)
        object.__setattr__(self, "dates", days)
        object.__setattr__(self, "hte_costs", (float(c), float(k)))

    @property
    def fence(self) -> int:
        return self.positions.shape[0]


@dataclass(frozen=True)
class BridgeSettings:
    lag: int = 1
    allow_same_close: bool = False          # only for the comparison's same-close column
    capital: float = 1e8
    warmup: int = 300                       # HTE Policy.warmup
    vol_target_ann: float = 0.10            # HTE Policy defaults
    vol_halflife: int = 20
    vol_min_obs: int = 20
    leverage_cap: float = 5.0
    sizing_rounding: str = "nearest"
    on_missing_price: str = "raise"         # PR #85's default
    on_liquidity_shortfall: str = "raise"   # PR #85's default
    clock: DecisionClock = field(default_factory=DecisionClock)
    contract_map: ContractMap = field(default_factory=ContractMap)
    commission: float = 1.0
    exchange_fee: float = 0.5
    max_participation: float = 0.1
    fx_conversion_bps: float | None = 1.0

    def __post_init__(self):
        self.timing()                       # lag 0 without allow_same_close is refused here
        self.policy()

    def timing(self) -> ExecutionTiming:
        return ExecutionTiming(self.lag, allow_same_close=self.allow_same_close)

    def policy(self) -> AD.ExecutionPolicy:
        return AD.ExecutionPolicy(capital=self.capital, timing=self.timing(), sizing_rounding=self.sizing_rounding,
                                  on_missing_price=self.on_missing_price,
                                  on_liquidity_shortfall=self.on_liquidity_shortfall)


@dataclass(frozen=True, eq=False)
class Translation:
    panel: object
    costs: CostModel
    weights: np.ndarray
    scale: np.ndarray
    decision_rows: np.ndarray
    execution_rows: np.ndarray
    spec: dict


@dataclass(frozen=True, eq=False)
class BridgeResult:
    translation: Translation
    result: AD.ExecutionResult
    window_net: np.ndarray          # daily net / capital over [W, F); entry-day costs in the first element
    assessment: RL.Assessment
    identity: dict

    @property
    def label(self) -> str:
        return self.assessment.label


def execution_block(settings: BridgeSettings, costs: CostModel, panel, shocks: AD.Shocks | None) -> dict:
    start, end = panel.days[0], panel.days[-1]
    return {
        "timing": settings.timing().as_dict(),
        "clock": settings.clock.as_dict(),
        "vol_scaling": {"rule": "decision_time_ewma/v1", "lag": settings.lag, "target_ann": settings.vol_target_ann,
                        "halflife": settings.vol_halflife, "min_obs": settings.vol_min_obs,
                        "leverage_cap": settings.leverage_cap},
        "sizing": {"capital": settings.capital, "rounding": settings.sizing_rounding, "unit": "whole_contracts"},
        "policy": {"on_missing_price": settings.on_missing_price,
                   "on_liquidity_shortfall": settings.on_liquidity_shortfall},
        "window": {"warmup": settings.warmup},
        "contract_map": settings.contract_map.digest(),
        "costs": {"model_id": costs.model_id(),
                  "sources": {r: {k: s.for_window(start, end).as_dict() for k, s in t.sources().items()}
                              for r, t in costs.terms}},
        "shocks": (shocks or AD.Shocks()).as_dict(),
        "adapter": ID.ADAPTER_VERSION,
    }


def translate(inp: CandidateInput, settings: BridgeSettings = BridgeSettings(), *, missing=(), adv_scale=None,
              cost_model: CostModel | None = None, shocks: AD.Shocks | None = None) -> Translation:
    if ENABLED or not inp.provenance.get("synthetic"):
        raise BridgeDisabled("dormant bridge: synthetic inputs only")
    fence = inp.fence
    panel = contractise(inp.returns, inp.dates, inp.domain, settings.contract_map, missing=missing,
                        adv_scale=adv_scale)
    dw = decision_weights(inp.positions, inp.returns, warmup=settings.warmup, fence=fence, lag=settings.lag,
                          vol_target_ann=settings.vol_target_ann, vol_halflife=settings.vol_halflife,
                          vol_min_obs=settings.vol_min_obs, leverage_cap=settings.leverage_cap)
    ex = settings.clock.execution_rows(inp.domain, inp.dates, dw["rows"], settings.lag)
    want = dw["rows"] + settings.lag
    want[want >= fence] = -1
    if not np.array_equal(ex, want):                 # the clock and the adapter's row rule must agree
        raise BridgeError("decision clock and execution rows disagree")
    c, k = inp.hte_costs
    costs = cost_model or hte_matched_costs(panel, settings.contract_map, inp.domain, c=c, k=k,
                                            capital=settings.capital, commission=settings.commission,
                                            exchange_fee=settings.exchange_fee,
                                            max_participation=settings.max_participation,
                                            fx_conversion_bps=settings.fx_conversion_bps)
    spec = ID.executable_spec({**(inp.hte_spec or {}), "candidate": inp.candidate_hash, "domain": inp.domain},
                              execution_block(settings, costs, panel, shocks))
    return Translation(panel, costs, dw["weights"], dw["scale"], dw["rows"], ex, spec)


def evaluate(inp: CandidateInput, settings: BridgeSettings = BridgeSettings(), *, missing=(), adv_scale=None,
             cost_model: CostModel | None = None, shocks: AD.Shocks | None = None) -> BridgeResult:
    tr = translate(inp, settings, missing=missing, adv_scale=adv_scale, cost_model=cost_model, shocks=shocks)
    res = AD.execute(tr.panel, tr.costs, settings.policy(), weights=tr.weights, shocks=shocks)
    daily = res.daily_returns()
    W = settings.warmup
    net = daily[W:].copy()
    net[0] += daily[:W].sum()                         # entry-day costs (no gross before W)
    ident = ID.executable_identity(tr.spec, data_hash=inp.data_hash, market_digest=tr.panel.digest(),
                                   result_hash=res.result_hash())
    return BridgeResult(tr, res, net, RL.assess(res), ident)


def from_hte(view, i: int, cache, *, signed_positions, cost_coefficients, cost_models: dict, fence: int,
             evaluation_spec=None) -> CandidateInput:
    """Build a ``CandidateInput`` from HTE objects without importing HTE: the caller passes HTE's
    ``runner.signed_positions``, ``kernels.cost_coefficients`` and ``templates.COST_MODELS`` (and optionally a
    zero-argument callable returning ``adapters.evaluation_spec`` for this candidate)."""
    d = view.describe(int(i))
    panel = cache.panel
    if fence > panel.fence:
        raise BridgeError("the evaluation fence cannot pass the panel's protected fence")
    P = np.asarray(signed_positions(cache, d))[:fence]
    R = np.asarray(panel.returns(d["domain"]))[:fence]
    c, k = cost_coefficients(d["domain"], cost_models[d["cost_model"]])
    return CandidateInput(view.candidate_hash(int(i)), d["domain"], P, R, tuple(np.asarray(panel.dates)[:fence]),
                          panel.data_hash, dict(panel.provenance), (c, k),
                          evaluation_spec() if evaluation_spec else None)


def pr85_decision_records(inp: CandidateInput, out: BridgeResult, settings: BridgeSettings) -> list[dict]:
    """The decisions in PR #85's terms (``Decision(root, contracts, decided_at, inputs_known_at)``), as data."""
    res, tr = out.result, out.translation
    recs = []
    for t in tr.decision_rows:
        d = inp.dates[int(t)]
        for a, root in enumerate(res.roots):
            v = res.targets[int(t), a]
            if np.isfinite(v):
                recs.append({"root": root, "contracts": int(v),
                             "decided_at": settings.clock.decided_at(inp.domain, d).isoformat(),
                             "inputs_known_at": settings.clock.published_at(inp.domain, d).isoformat(),
                             "lag": settings.lag})
    return recs


class HteExecutionStage:
    """The hook a connected HTE stage would construct. Disabled until every connection requirement is met."""
    enabled = False

    def __init__(self, *args, **kwargs):
        raise BridgeDisabled("the HTE execution bridge is dormant: " +
                             "; ".join(f"{k} {v}" for k, v in CONNECTION_REQUIREMENTS))


def with_lag(settings: BridgeSettings, lag: int) -> BridgeSettings:
    return replace(settings, lag=lag, allow_same_close=(lag == 0))
