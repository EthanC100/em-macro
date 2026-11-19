"""Cost terms per root, each with its provenance, and the fill of one order.

**One order on one day** (prices in the contract's price units, ``n = |q|`` whole contracts, ``side = sign(q)``):

    reference  ref  = the tradable settlement of the contract traded, on the execution day
    spread     s    = half_spread_ticks × tick_size × spread_shock
    slippage   g    = slippage_ticks × tick_size × slippage_shock
    impact     i    = impact_coefficient × daily_vol_points × sqrt(n / adv_contracts)
    fill            = (ref + side × (s + g + i)) rounded to the tick grid against the trader
    rounding   r    = side × (fill − (ref + side × (s + g + i)))          ≥ 0

    execution cost  = (s + g + i + r) × n × point_value        (instrument currency)
    fees            = n × (commission + exchange_fee)           (fee currency, per contract per side)

This is PR #85's ``fill_order`` (``manhattan/execution/costs.py`` at 3f6b213) term for term, with two additions:
day-by-day shocks to the spread and slippage (adverse-condition scenarios) and a provenance on every term. The
conformance test (``tests/test_manhattan_execution_realism.py``) checks the two agree to 1e-8 on a common plan.

**No defaults.** Every term is given explicitly with its ``Source`` (``provenance.py``). Zero is allowed and
means "none" (it still needs a source: "zero" is a claim too).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields

from .errors import LiquidityError, MissingInputError, UnitError
from .instruments import Instrument, adverse_round, currency, finite
from .provenance import SYNTHETIC, Source

PRICE_MOVING = ("half_spread_ticks", "slippage_ticks", "impact_coefficient")
FEES = ("commission", "exchange_fee")
COMPONENTS = FEES + PRICE_MOVING + ("max_participation", "fx_conversion_bps")


@dataclass(frozen=True)
class CostValue:
    value: float
    source: Source

    def __post_init__(self):
        finite(self.value, "cost value", nonneg=True)
        if not isinstance(self.source, Source):
            raise UnitError("a cost value needs a provenance.Source")


def synthetic(x: float) -> CostValue:
    return CostValue(float(x), SYNTHETIC)


@dataclass(frozen=True)
class RootCosts:
    """Every cost term of one root. ``fx_conversion_bps`` is charged on each day's foreign-currency amounts
    converted into the base currency; it is required (zero allowed) for a root not quoted in the base currency."""
    fee_currency: str
    commission: CostValue           # fee currency per contract per side (broker)
    exchange_fee: CostValue         # fee currency per contract per side (exchange and clearing)
    half_spread_ticks: CostValue    # ticks from the settlement to the touch
    slippage_ticks: CostValue       # further ticks beyond the touch
    impact_coefficient: CostValue   # dimensionless, times daily_vol_points × sqrt(n / ADV)
    max_participation: CostValue    # fraction of ADV per contract per day, in (0, 1]
    fx_conversion_bps: CostValue | None = None

    def __post_init__(self):
        currency(self.fee_currency)
        for f in COMPONENTS:
            v = getattr(self, f)
            if v is None and f == "fx_conversion_bps":
                continue
            if not isinstance(v, CostValue):
                raise UnitError(f"{f} must be a CostValue (a number with its provenance)")
        if not 0 < self.max_participation.value <= 1:
            raise UnitError(f"max_participation is a fraction of ADV in (0, 1], not {self.max_participation.value}")

    def scaled(self, k: float) -> "RootCosts":
        """Fees and price-moving costs times ``k``; the participation cap is unchanged. Each scaled value becomes a
        ``scenario`` source that names the one it was derived from (``k == 1`` keeps the sources)."""
        k = finite(k, "cost multiple", nonneg=True)

        def sc(v: CostValue | None) -> CostValue | None:
            if v is None or k == 1:
                return v
            src = Source("scenario", f"{k:g}x of {v.source.kind}: {v.source.reference or 'synthetic'}")
            return CostValue(v.value * k, src)
        return RootCosts(self.fee_currency, sc(self.commission), sc(self.exchange_fee), sc(self.half_spread_ticks),
                         sc(self.slippage_ticks), sc(self.impact_coefficient), self.max_participation,
                         sc(self.fx_conversion_bps))

    def sources(self) -> dict:
        return {f: getattr(self, f).source for f in COMPONENTS if getattr(self, f) is not None}

    def as_dict(self) -> dict:
        out = {"fee_currency": self.fee_currency}
        for f in COMPONENTS:
            v = getattr(self, f)
            out[f] = None if v is None else {"value": v.value, "source": v.source.as_dict()}
        return out


@dataclass(frozen=True)
class CostModel:
    name: str
    terms: tuple                    # ((root, RootCosts), ...)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise UnitError("a cost model needs a name")
        pairs = list(self.terms.items()) if isinstance(self.terms, dict) else list(self.terms)
        items = dict(pairs)
        if len(items) != len(pairs) or not items:
            raise UnitError("a cost model gives each root's terms exactly once, and at least one root")
        for r, t in items.items():
            if not isinstance(t, RootCosts):
                raise UnitError(f"terms of {r!r} must be RootCosts")
        object.__setattr__(self, "terms", tuple(sorted(items.items())))

    def for_root(self, root: str) -> RootCosts:
        t = dict(self.terms).get(root)
        if t is None:
            raise MissingInputError(f"cost model {self.name!r} has no terms for root {root!r}")
        return t

    def scaled(self, k: float, name: str | None = None) -> "CostModel":
        return CostModel(name or f"{self.name} x{k:g}", tuple((r, t.scaled(k)) for r, t in self.terms))

    def as_dict(self) -> dict:
        return {"terms": {r: t.as_dict() for r, t in self.terms}}

    def model_id(self) -> str:
        """Content address of the economics and their sources (the name is a label and is left out)."""
        b = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return "XR-" + hashlib.sha256(b).hexdigest()[:16]


@dataclass(frozen=True)
class Fill:
    day: int                        # panel day index
    root: str
    leg: str                        # "outright", "roll_out" (old month) or "roll_in" (new month)
    reason: str                     # "decision", "carry", "roll" or "roll+decision" / "roll+carry"
    requested: int
    filled: int
    reference_price: float
    fill_price: float
    spread: float                   # instrument currency
    slippage: float
    impact: float
    rounding: float
    commission: float               # fee currency
    exchange_fee: float
    traded_notional: float          # |filled| × |reference| × point value, instrument currency
    liquidity_day: int              # panel day whose liquidity estimate sized and costed this fill

    @property
    def execution_cost(self) -> float:
        return self.spread + self.slippage + self.impact + self.rounding


def capacity(adv: float, terms: RootCosts) -> int:
    """Whole contracts allowed per contract per day by the participation cap (PR #85's rule)."""
    return int(math.floor(terms.max_participation.value * adv + 1e-9))


def fill(inst: Instrument, terms: RootCosts, *, day: int, leg: str, reason: str, requested: int, quantity: int,
         ref: float, adv: float, vol_points: float, liquidity_day: int, spread_shock: float = 1.0,
         slippage_shock: float = 1.0) -> Fill:
    """Fill ``quantity`` signed contracts at ``ref``. The caller has already applied the participation cap."""
    n = abs(int(quantity))
    if n == 0:
        z = 0.0
        return Fill(day, inst.root, leg, reason, requested, 0, ref, ref, z, z, z, z, z, z, z, liquidity_day)
    if not (math.isfinite(adv) and adv > 0):
        raise LiquidityError(f"{inst.root} day {day}: no positive ADV estimate, so nothing can be traded")
    if not math.isfinite(vol_points) or vol_points < 0:
        raise MissingInputError(f"{inst.root} day {day}: no daily volatility estimate for the impact term")
    side = 1 if quantity > 0 else -1
    pv = inst.point_value
    s = terms.half_spread_ticks.value * inst.tick_size * spread_shock
    g = terms.slippage_ticks.value * inst.tick_size * slippage_shock
    i = terms.impact_coefficient.value * vol_points * math.sqrt(n / adv)
    raw = ref + side * (s + g + i)
    px = adverse_round(raw, inst.tick_size, side)
    r = side * (px - raw)
    return Fill(day, inst.root, leg, reason, requested, side * n, ref, px, s * n * pv, g * n * pv, i * n * pv,
                r * n * pv, n * terms.commission.value, n * terms.exchange_fee.value, n * abs(ref) * pv,
                liquidity_day)


def one_way_cost_fraction(inst: Instrument, terms: RootCosts, *, price: float, contracts: int, adv: float,
                          vol_points: float, fee_rate: float = 1.0) -> float:
    """The cost of one buy of ``contracts`` as a fraction of its notional at ``price``: the proportional cost a
    weights-based model (HTE stage 3, the engine's ``Instrument.cost``) would need to match this fill, exactly
    at this price and size only. ``fee_rate`` converts the fee currency into the instrument currency."""
    f = fill(inst, terms, day=0, leg="outright", reason="decision", requested=contracts, quantity=abs(contracts),
             ref=price, adv=adv, vol_points=vol_points, liquidity_day=0)
    notional = abs(contracts) * abs(price) * inst.point_value
    if notional == 0:
        raise UnitError("a cost fraction needs a non-zero size and price")
    return (f.execution_cost + (f.commission + f.exchange_fee) * fee_rate) / notional


def hte_equivalent_coefficients(inst: Instrument, terms: RootCosts, *, price: float, adv: float, vol_points: float,
                                capital: float, fee_rate: float = 1.0) -> tuple[float, float]:
    """``(c, k)`` such that HTE's per-unit-notional cost ``c·|ΔW| + k·|ΔW|^1.5`` (``manhattan/hte/kernels.py``)
    reproduces this model's spread, slippage, fees and impact for a trade of ``|ΔW|`` of ``capital``, ignoring
    tick rounding and whole contracts:

        c = (half_spread + slippage) × tick / |price| + fees / (|price| × point_value)
        k = impact_coefficient × (vol_points / |price|) × sqrt(capital / (|price| × point_value × ADV))

    ``k`` depends on capital / ADV: HTE's fixed ``k`` therefore fixes a capital-to-liquidity ratio that its
    run identity does not state (design document, section 1)."""
    p = abs(finite(price, "price", positive=False))
    if p == 0:
        raise UnitError("no proportional cost at a zero price")
    c = (terms.half_spread_ticks.value + terms.slippage_ticks.value) * inst.tick_size / p
    c += (terms.commission.value + terms.exchange_fee.value) * fee_rate / (p * inst.point_value)
    k = terms.impact_coefficient.value * (vol_points / p) * math.sqrt(capital / (p * inst.point_value * adv))
    return c, k


def describe_fields() -> list[str]:
    return [f.name for f in fields(RootCosts)]
