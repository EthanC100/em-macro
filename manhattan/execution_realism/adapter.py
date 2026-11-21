"""The execution adapter: target weights (or contracts) on a panel in, delayed and costed fills and daily P&L out.

    result = execute(panel, costs, ExecutionPolicy(capital=1e7), weights=W)

``W[t, a]`` is the target weight of root ``a`` decided at the close of day ``t`` from data through that close
(``NaN`` = no decision that day: the previous target stands). Pure and deterministic: no file, clock, network,
environment variable or randomness.

**Each decision.** Sized at the decision, from what was known then: ``contracts = W × capital / (|level[t]| ×
point_value × fx[t])``, rounded (``nearest``, half to even, or ``toward_zero``). Under ``hold`` a missing level
sizes from the root's last published level and is listed in ``stale_sizing``; under ``raise`` it stops the run.
It executes on day ``t + lag`` (``timing.py``); a decision that would execute after the last day is listed in
``unexecuted``.

**Each day ``d``, each root** (the order of PR #85's ``run``):

1. *Mark.* A held position earns ``q × (exit_level[d] − last mark) × point_value``, converted at ``fx[d]``. A
   missing settlement stops the run (``raise``) or keeps the last mark (``hold``; the gap's P&L is booked when the
   price returns, and the day is listed in ``stale_marks``).
2. *Trade* toward the latest target. Liquidity: a decision executing today uses the estimate known at its
   decision (row ``t``); a carried remainder or a roll uses the previous close's (row ``d - 1``). At most
   ``floor(max_participation × ADV)`` contracts per contract per day: ``raise`` stops the run, ``clip`` fills the cap
   and carries the rest. On one contract month this is exactly PR #85's close-first reversal rule (closing is the
   first part of the path from ``q`` to the target).
3. *Roll* (the held month changes at this close). The old month is closed in full at ``exit_level[d]`` and the new
   one opened at ``level[d]``: two legs, each paying spread, slippage, impact, rounding and fees, the new leg
   combined with any change of the target into one fill (PR #85's ``roll+decision``). **Fails closed**
   (``RollError``) when either price is missing or the cap cannot close the old month or open the rolled part of
   the new one: the panel has no price for the old month after its roll day. PR #85's paired, multi-day partial
   roll is the reference model for that case.
4. *Exposure* after the close at the last mark.

``net = gross − (spread + slippage + impact + rounding + commission + exchange_fee + fx_conversion)`` exactly, every
day, every root (tested).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np

from . import timing as TM
from .costs import CostModel, Fill, capacity, fill
from .errors import LiquidityError, MissingInputError, RollError, UnitError
from .instruments import finite
from .panel import SettlementPanel

MISSING = ("raise", "hold")
SHORTFALL = ("raise", "clip")
ROUNDING = ("nearest", "toward_zero")
COST_PARTS = ("spread", "slippage", "impact", "rounding", "commission", "exchange_fee", "fx_conversion")


@dataclass(frozen=True)
class ExecutionPolicy:
    capital: float                              # base currency; fixed (no compounding)
    timing: TM.ExecutionTiming = field(default_factory=TM.ExecutionTiming)
    sizing_rounding: str = "nearest"
    on_missing_price: str = "raise"
    on_liquidity_shortfall: str = "raise"

    def __post_init__(self):
        finite(self.capital, "capital", positive=True)
        if not isinstance(self.timing, TM.ExecutionTiming):
            raise UnitError("timing is an ExecutionTiming")
        if self.sizing_rounding not in ROUNDING:
            raise UnitError(f"sizing_rounding is one of {ROUNDING}")
        if self.on_missing_price not in MISSING:
            raise UnitError(f"on_missing_price is one of {MISSING}")
        if self.on_liquidity_shortfall not in SHORTFALL:
            raise UnitError(f"on_liquidity_shortfall is one of {SHORTFALL}")

    @property
    def lag(self) -> int:
        return self.timing.lag

    def describe(self) -> dict:
        return {"capital": self.capital, "timing": self.timing.as_dict(), "sizing_rounding": self.sizing_rounding,
                "on_missing_price": self.on_missing_price, "on_liquidity_shortfall": self.on_liquidity_shortfall,
                "calibrated": False}


@dataclass(frozen=True, eq=False)
class Shocks:
    """Adverse-condition multipliers per day and root, ``(n, A)``, all scenario-class: on the half-spread, on the
    slippage, and on ADV (``< 1`` a liquidity drought: a smaller cap and more impact). ``None`` = 1."""
    name: str = "none"
    spread: np.ndarray | None = None
    slippage: np.ndarray | None = None
    adv: np.ndarray | None = None

    def check(self, shape) -> None:
        for f in ("spread", "slippage", "adv"):
            x = getattr(self, f)
            if x is None:
                continue
            x = np.asarray(x, float)
            if x.shape != tuple(shape) or not np.isfinite(x).all() or (x < 0).any():
                raise UnitError(f"shock {f} must be finite, non-negative and shaped {tuple(shape)}")

    def at(self, f: str, d: int, a: int) -> float:
        x = getattr(self, f)
        return 1.0 if x is None else float(x[d][a])

    def as_dict(self) -> dict:
        def h(x):
            return None if x is None else hashlib.sha256(np.ascontiguousarray(x, "<f8").tobytes()).hexdigest()
        return {"name": self.name, "spread": h(self.spread), "slippage": h(self.slippage), "adv": h(self.adv)}


@dataclass(frozen=True)
class Unfilled:
    day: int
    root: str
    leg: str
    requested: int
    filled: int
    why: str                    # "no settlement" or "liquidity"
    reason: str


@dataclass(frozen=True)
class Unexecuted:
    decision_day: int
    root: str
    target: int


@dataclass(frozen=True)
class RollEvent:
    day: int
    root: str
    contracts: int              # contracts moved from the old month to the new one (0 for a reversal or exit)
    from_price: float
    to_price: float
    calendar_gap_points: float  # what a spliced series would book as a jump; never P&L here


@dataclass(frozen=True, eq=False)
class ExecutionResult:
    panel_digest: str
    policy: dict
    cost_model_id: str
    cost_model_name: str
    cost_sources: dict          # {root: {component: Source as it applies to this window}}
    shocks: dict
    data_kind: str
    roots: tuple
    targets: np.ndarray         # (n, A) contracts decided (NaN: no decision)
    positions: np.ndarray       # (n, A) contracts after each close
    gross: np.ndarray           # (n, A) base currency
    parts: dict                 # part -> (n, A) base currency
    turnover: np.ndarray        # (n, A) base currency notional traded
    gross_exposure: np.ndarray  # (n, A) after the close
    net_exposure: np.ndarray
    fills: tuple
    unfilled: tuple
    unexecuted: tuple
    rolls: tuple
    stale_marks: tuple          # (day, root)
    stale_sizing: tuple         # (decision day, root)
    fx_conversion_unmodelled: tuple   # roots quoted outside the base currency with no fx_conversion_bps term
    capital: float

    @property
    def lag(self) -> int:
        return int(self.policy["timing"]["lag"])

    @property
    def same_close(self) -> bool:
        return self.lag == 0

    @property
    def costs(self) -> np.ndarray:
        return sum(self.parts[p] for p in COST_PARTS)

    @property
    def net(self) -> np.ndarray:
        return self.gross - self.costs

    def daily_net(self) -> np.ndarray:
        return self.net.sum(axis=1)

    def daily_returns(self) -> np.ndarray:
        """Net P&L over the fixed capital, per day: the quantity Protocol v3.1 section 2.1 calls ``r_{x,t}``
        (excess of cash) for a futures book, **under this run's assumptions**. Labelled by ``summary``."""
        return self.daily_net() / self.capital

    def totals(self) -> dict:
        out = {"gross": float(self.gross.sum()), "net": float(self.net.sum()), "costs": float(self.costs.sum()),
               "turnover": float(self.turnover.sum())}
        for p in COST_PARTS:
            out[p] = float(self.parts[p].sum())
        out.update(n_fills=sum(1 for f in self.fills if f.filled), n_unfilled=len(self.unfilled),
                   n_unexecuted=len(self.unexecuted), n_rolls=len(self.rolls), n_stale_marks=len(self.stale_marks),
                   n_stale_sizing=len(self.stale_sizing),
                   contracts_traded=sum(abs(f.filled) for f in self.fills))
        return out

    def stats(self) -> dict:
        r = self.daily_returns()
        n = r.size
        mean = float(r.mean())
        sd = float(r.std(ddof=1)) if n > 1 else 0.0
        cum = np.cumsum(r)
        peak = np.maximum.accumulate(np.maximum(cum, 0.0))
        g = self.gross.sum(axis=1) / self.capital
        return {"days": n, "ann_net_return": mean * 252.0, "ann_gross_return": float(g.mean()) * 252.0,
                "ann_vol": sd * math.sqrt(252.0), "sharpe": mean / sd * math.sqrt(252.0) if sd > 0 else 0.0,
                "max_drawdown": float((peak - cum).max()) if n else 0.0,
                "ann_cost_drag": float(self.costs.sum(axis=1).mean()) / self.capital * 252.0,
                "ann_turnover": float(self.turnover.sum(axis=1).mean()) / self.capital * 252.0}

    def summary(self) -> dict:
        """Statistics with their label. At lag 0 every statistic is renamed ``same_close_optimistic_*`` so it
        cannot be mistaken for a trading return."""
        from . import realism
        a = realism.assess(self)
        st = self.stats()
        if self.same_close:
            st = {f"same_close_optimistic_{k}": v for k, v in st.items()}
        return {"label": a.label, "lag": self.lag, "timing": self.policy["timing"]["label"],
                "data_kind": self.data_kind, "cost_class": a.cost_class, "realistic_return_claims": False,
                "unmet_requirements": list(a.unmet), "warnings": list(a.warnings), "stats": st,
                "result_hash": self.result_hash()}

    def result_hash(self) -> str:
        """SHA-256 of the inputs' identities (panel digest, decisions, policy, cost model and sources, shocks) and
        every output, amounts rounded to 8 decimals of the base currency."""
        def r8(x):
            return [format(round(float(v), 8) + 0.0, ".8f") for v in np.ravel(x)]
        doc = {"panel": self.panel_digest, "policy": self.policy, "costs": self.cost_model_id,
               "sources": {r: {k: s.as_dict() for k, s in v.items()} for r, v in self.cost_sources.items()},
               "shocks": self.shocks,
               "targets": hashlib.sha256(np.ascontiguousarray(self.targets, "<f8").tobytes()).hexdigest(),
               "positions": np.asarray(self.positions, int).ravel().tolist(), "gross": r8(self.gross),
               "parts": {p: r8(self.parts[p]) for p in COST_PARTS}, "turnover": r8(self.turnover),
               "fills": [[f.day, f.root, f.leg, f.reason, f.requested, f.filled, repr(f.fill_price)] for f in self.fills],
               "unfilled": [list(u.__dict__.values()) for u in self.unfilled],
               "unexecuted": [list(u.__dict__.values()) for u in self.unexecuted],
               "stale": [list(x) for x in self.stale_marks], "stale_sizing": [list(x) for x in self.stale_sizing]}
        return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def size(panel: SettlementPanel, weights, policy: ExecutionPolicy) -> tuple[np.ndarray, tuple]:
    """Contracts decided per row from target weights, with what was known at each decision."""
    W = np.asarray(weights, float)
    n, A = panel.shape
    if W.shape != (n, A):
        raise UnitError(f"weights have shape {W.shape}, expected {(n, A)}")
    if np.isinf(W).any():
        raise UnitError("weights must be finite (NaN means no decision)")
    out = np.full((n, A), np.nan)
    stale = []
    for a, inst in enumerate(panel.instruments):
        last = math.nan
        for t in range(n):
            lv = panel.level[t, a]
            if math.isfinite(lv):
                last = lv
            w = W[t, a]
            if math.isnan(w):
                continue
            if w == 0.0:
                out[t, a] = 0.0
                continue
            px = lv
            if not math.isfinite(px):
                if policy.on_missing_price == "raise" or not math.isfinite(last):
                    raise MissingInputError(f"{inst.root}: no settlement on {panel.days[t]} to size a decision")
                px = last
                stale.append((t, inst.root))
            if px == 0.0:
                raise UnitError(f"{inst.root}: a weight cannot be sized at a zero price ({panel.days[t]})")
            x = w * policy.capital / (abs(px) * inst.point_value * panel.fx_rate(inst.currency, t))
            out[t, a] = float(round(x)) if policy.sizing_rounding == "nearest" else float(math.trunc(x))
    return out, tuple(stale)


def execute(panel: SettlementPanel, costs: CostModel, policy: ExecutionPolicy, *, weights=None, contracts=None,
            shocks: Shocks | None = None) -> ExecutionResult:
    if not isinstance(panel, SettlementPanel):
        raise UnitError("panel is a SettlementPanel")
    if not isinstance(costs, CostModel):
        raise UnitError("costs is a CostModel")
    if (weights is None) == (contracts is None):
        raise UnitError("give exactly one of weights and contracts")
    n, A = panel.shape
    shocks = shocks or Shocks()
    shocks.check((n, A))
    if weights is not None:
        targets, stale_sizing = size(panel, weights, policy)
    else:
        targets = np.array(contracts, float)
        if targets.shape != (n, A):
            raise UnitError(f"contracts have shape {targets.shape}, expected {(n, A)}")
        ok = np.isnan(targets) | (np.isfinite(targets) & (targets == np.round(targets)))
        if not ok.all():
            raise UnitError("contracts are whole numbers (NaN means no decision)")
        stale_sizing = ()
    targets.setflags(write=False)
    lag = policy.lag
    start, end = panel.days[0], panel.days[-1]

    gross = np.zeros((n, A))
    parts = {p: np.zeros((n, A)) for p in COST_PARTS}
    turnover = np.zeros((n, A))
    gexp = np.zeros((n, A))
    nexp = np.zeros((n, A))
    positions = np.zeros((n, A), int)
    fills, unfilled, unexecuted, rolls, stale_marks = [], [], [], [], []
    no_fxc = []

    for a, inst in enumerate(panel.instruments):
        root, pv = inst.root, inst.point_value
        terms = costs.for_root(root)
        foreign = inst.currency != panel.base_currency
        if foreign and terms.fx_conversion_bps is None:
            no_fxc.append(root)
        fxc_bps = terms.fx_conversion_bps.value if (foreign and terms.fx_conversion_bps is not None) else 0.0
        execs = {}
        for t in np.flatnonzero(~np.isnan(targets[:, a])):
            d = int(t) + lag
            if d >= n:
                unexecuted.append(Unexecuted(int(t), root, int(targets[t, a])))
            else:
                execs[d] = int(t)
        q, mark, T = 0, math.nan, None
        for d in range(n):
            g_ccy = 0.0
            if q:
                px = panel.exit_level[d, a]
                if math.isnan(px):
                    if policy.on_missing_price == "raise":
                        raise MissingInputError(f"no settlement for held {root} on {panel.days[d]}")
                    stale_marks.append((d, root))
                else:
                    g_ccy = q * (px - mark) * pv
                    mark = px
            row = execs.get(d)
            if row is not None:
                T, t_liq, base_reason = int(targets[row, a]), row, "decision"
            else:
                t_liq, base_reason = d - 1, "carry"
            today: list[Fill] = []

            def liquidity() -> tuple[float, float, int]:
                adv = panel.adv[t_liq, a] * shocks.at("adv", d, a)
                vol = panel.vol_points[t_liq, a]
                if math.isnan(adv):
                    raise MissingInputError(f"no ADV estimate for {root} known at {panel.days[t_liq]}")
                return adv, vol, capacity(adv, terms)

            def do_fill(leg, reason, requested, qty, ref, adv, vol):
                f = fill(inst, terms, day=d, leg=leg, reason=reason, requested=requested, quantity=qty, ref=ref,
                         adv=adv, vol_points=vol, liquidity_day=t_liq, spread_shock=shocks.at("spread", d, a),
                         slippage_shock=shocks.at("slippage", d, a))
                today.append(f)
                return f

            if T is not None and not (q == 0 and T == 0):
                if panel.roll[d, a] and q:
                    old_ref, new_ref = panel.exit_level[d, a], panel.level[d, a]
                    if math.isnan(old_ref) or math.isnan(new_ref):
                        raise RollError(f"{root} rolls on {panel.days[d]} but a leg has no settlement; the panel has "
                                        "no later price for the old month, so the adapter stops (fail closed)")
                    adv, vol, cap = liquidity()
                    same = T != 0 and _sign(T) == _sign(q)
                    K = _sign(T) * min(abs(q), abs(T)) if same else 0
                    if abs(q) > cap or (same and abs(K) > cap):
                        if policy.on_liquidity_shortfall == "raise":
                            raise LiquidityError(f"{root} roll on {panel.days[d]}: {max(abs(q), abs(K))} contracts "
                                                 f"needed, the cap allows {cap}")
                        raise RollError(f"{root} roll on {panel.days[d]}: the cap ({cap}) cannot close {abs(q)} in the "
                                        "old month and open the rolled part in the new one; the panel adapter fails "
                                        "closed (PR #85 models a partial, paired roll)")
                    out_reason = "roll" if same and abs(K) == abs(q) else (f"roll+{base_reason}" if same
                                                                          else base_reason)
                    do_fill("roll_out", out_reason, -q, -q, old_ref, adv, vol)
                    newq = 0
                    if T:
                        in_reason = "roll" if same and K == T else (f"roll+{base_reason}" if same else base_reason)
                        newq = T
                        if abs(T) > cap:
                            if policy.on_liquidity_shortfall == "raise":
                                raise LiquidityError(f"{root} on {panel.days[d]}: {abs(T)} contracts wanted, cap {cap}")
                            newq = _sign(T) * cap
                            unfilled.append(Unfilled(d, root, "roll_in", T, newq, "liquidity", in_reason))
                        do_fill("roll_in", in_reason, T, newq, new_ref, adv, vol)
                    if K:                                   # a reversal or an exit is never a roll (PR #85 N1)
                        rolls.append(RollEvent(d, root, abs(K), float(old_ref), float(new_ref),
                                               float(new_ref - old_ref)))
                    q, mark = newq, (new_ref if newq else math.nan)
                else:
                    want = T - q
                    if want:
                        ref = panel.level[d, a]
                        if math.isnan(ref):
                            if policy.on_missing_price == "raise":
                                raise MissingInputError(f"no settlement for {root} on {panel.days[d]} to trade at")
                            unfilled.append(Unfilled(d, root, "outright", want, 0, "no settlement", base_reason))
                        else:
                            adv, vol, cap = liquidity()
                            qty = want
                            if abs(want) > cap:
                                if policy.on_liquidity_shortfall == "raise":
                                    raise LiquidityError(f"{root} on {panel.days[d]}: {abs(want)} contracts wanted, "
                                                         f"the cap allows {cap}")
                                qty = _sign(want) * cap
                                unfilled.append(Unfilled(d, root, "outright", want, qty, "liquidity", base_reason))
                            if qty:
                                do_fill("outright", base_reason, want, qty, ref, adv, vol)
                                q += qty
                                mark = ref
            fills.extend(today)
            if q == 0 and not today and g_ccy == 0.0:
                positions[d, a] = 0
                continue
            rate = panel.fx_rate(inst.currency, d)
            fee_rate = panel.fx_rate(terms.fee_currency, d)
            gross[d, a] = g_ccy * rate
            local = g_ccy
            for f in today:
                parts["spread"][d, a] += f.spread * rate
                parts["slippage"][d, a] += f.slippage * rate
                parts["impact"][d, a] += f.impact * rate
                parts["rounding"][d, a] += f.rounding * rate
                parts["commission"][d, a] += f.commission * fee_rate
                parts["exchange_fee"][d, a] += f.exchange_fee * fee_rate
                turnover[d, a] += f.traded_notional * rate
                local -= f.execution_cost
                if terms.fee_currency == inst.currency:
                    local -= f.commission + f.exchange_fee
            parts["fx_conversion"][d, a] = abs(local) * rate * fxc_bps / 1e4
            positions[d, a] = q
            if q:
                size_ = abs(q) * abs(mark) * pv * rate
                gexp[d, a] = size_
                nexp[d, a] = _sign(q) * size_

    sources = {r: {k: s.for_window(start, end) for k, s in t.sources().items()} for r, t in costs.terms
               if r in panel.roots}
    return ExecutionResult(panel.digest(), policy.describe(), costs.model_id(), costs.name, sources,
                           shocks.as_dict(), panel.data_kind, panel.roots, targets, positions, gross, parts,
                           turnover, gexp, nexp, tuple(fills), tuple(unfilled), tuple(unexecuted), tuple(rolls),
                           tuple(stale_marks), tuple(stale_sizing), tuple(no_fxc), policy.capital)
