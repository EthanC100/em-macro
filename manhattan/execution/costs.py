"""Cost scenarios and the fill of one order.

**Nothing here is calibrated.** A ``CostScenario`` holds caller-supplied numbers and says where they came from:
``provenance`` is ``synthetic`` (made up for a test or a sensitivity grid) or ``caller-supplied`` (some other
source the caller vouches for). The model refuses any other label, so no output of it can be presented as an
empirically calibrated cost. There are no default cost values: every term is given explicitly, per root.

**One order, one day** (all prices in the contract's price units, ``q`` signed whole contracts, ``side = sign(q)``):

    reference    ref    = the contract's tradable settlement on the execution day
    spread       s      = half_spread_ticks × tick_size
    slippage     g      = slippage_ticks × tick_size
    impact       i      = impact_coefficient × daily_vol_points × sqrt(|q| / adv_contracts)
    unrounded    raw    = ref + side × (s + g + i)
    fill         fill   = raw rounded to the tick grid against the trader (buy up, sell down)
    rounding     r      = side × (fill − raw)  ≥ 0 (within 1e-9 of a tick)

    execution cost (currency) = (fill − ref) × q × point_value = (s + g + i + r) × |q| × point_value   ≥ 0
    fees (fee currency)       = |q| × (commission_per_contract + exchange_fee_per_contract)

Fractional ticks cost whole ticks: half a tick of half-spread fills a full tick away, shown as 0.5 tick of
``spread`` and 0.5 tick of ``rounding`` (a conservative convention, kept on purpose: design section 5).

The four execution parts are reported separately and add up exactly to ``(fill − ref) × q × point_value``; fees
are per contract per side, in their own currency. A roll is two orders (close the old month, open the new one), so
it pays both legs' spread, slippage, impact and fees, once each.

**Liquidity cap.** At most ``floor(max_participation × adv_contracts)`` contracts per contract per day, with the
liquidity estimate known at the decision. An ADV of zero allows nothing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import date, datetime

from . import units as U
from .contracts import ContractSpec, adverse_round
from .errors import LiquidityError, LookAheadError, MissingInputError, UnitError
from .market import Liquidity, Settlement

PROVENANCE = ("synthetic", "caller-supplied")
SHORTFALL = ("raise", "clip")


@dataclass(frozen=True)
class CostTerms:
    """The cost terms of one root. Every field is required; zero is allowed and means "none"."""
    fee_currency: str
    commission_per_contract: float          # fee_currency per contract per side (broker)
    exchange_fee_per_contract: float        # fee_currency per contract per side (exchange and clearing)
    half_spread_ticks: float                # ticks from the reference price to the touch
    slippage_ticks: float                   # further ticks paid beyond the touch
    impact_coefficient: float               # dimensionless; multiplies daily_vol_points × sqrt(|q| / ADV)
    max_participation: float                # fraction of ADV that may be traded per contract per day, in (0, 1]
    margin_funding_bps_per_year: float      # cost of funding initial margin, bp a year of the margin; 0 = none

    def __post_init__(self):
        U.currency(self.fee_currency)
        for f in ("commission_per_contract", "exchange_fee_per_contract", "half_spread_ticks", "slippage_ticks",
                  "impact_coefficient", "margin_funding_bps_per_year"):
            U.finite(getattr(self, f), f, nonneg=True)
        p = U.finite(self.max_participation, "max_participation", positive=True)
        if p > 1:
            raise UnitError(f"max_participation is a fraction of ADV in (0, 1], not {p}")

    def scaled(self, factor: float) -> "CostTerms":
        """Every price-moving cost and fee times ``factor``; the participation cap is unchanged."""
        k = U.finite(factor, "scale factor", nonneg=True)
        return CostTerms(self.fee_currency, self.commission_per_contract * k, self.exchange_fee_per_contract * k,
                         self.half_spread_ticks * k, self.slippage_ticks * k, self.impact_coefficient * k,
                         self.max_participation, self.margin_funding_bps_per_year * k)

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class CostScenario:
    name: str
    provenance: str                         # "synthetic" or "caller-supplied"; never "calibrated"
    terms: tuple                            # ((root, CostTerms), ...), one per root

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise UnitError("a cost scenario needs a name")
        if self.provenance not in PROVENANCE:
            raise UnitError(f"provenance is one of {PROVENANCE} (this model holds no calibrated costs), "
                            f"not {self.provenance!r}")
        pairs = list(self.terms.items()) if isinstance(self.terms, dict) else list(self.terms)
        items = dict(pairs)
        if len(items) != len(pairs):
            raise UnitError(f"cost scenario {self.name!r} gives one root's terms twice")
        if not items:
            raise MissingInputError(f"cost scenario {self.name!r} has no cost terms")
        for root, t in items.items():
            if not isinstance(t, CostTerms):
                raise TypeError(f"cost terms of {root!r} must be CostTerms")
        object.__setattr__(self, "terms", tuple(sorted(items.items())))

    def for_root(self, root: str) -> CostTerms:
        t = dict(self.terms).get(root)
        if t is None:
            raise MissingInputError(f"cost scenario {self.name!r} has no cost terms for root {root!r}")
        return t

    def scaled(self, factor: float, name: str | None = None) -> "CostScenario":
        return CostScenario(name or f"{self.name} x{factor:g}", self.provenance,
                            tuple((r, t.scaled(factor)) for r, t in self.terms))

    def as_dict(self) -> dict:
        return {"name": self.name, "provenance": self.provenance,
                "terms": {r: t.as_dict() for r, t in self.terms}}

    def scenario_id(self) -> str:
        """Content address of the scenario's economics, for an executable's ``cost_model_id`` (ARCHITECTURE
        section 3): the provenance and every root's terms. The name is a label and is left out, so renaming a
        scenario keeps its id and two scenarios with the same terms share one."""
        from manhattan import spec
        d = self.as_dict()
        del d["name"]
        return "AC-" + spec.spec_hash(d)[:16]


@dataclass(frozen=True)
class Fill:
    """One executed (possibly clipped) order. Amounts in ``currency`` are the contract's; fees in ``fee_currency``."""
    day: date
    contract_id: str
    root: str
    reason: str                     # "decision" or "roll"
    requested: int                  # signed contracts wanted
    filled: int                     # signed contracts done (same sign, |filled| <= |requested|)
    reference_price: float
    fill_price: float
    currency: str
    spread_cost: float
    slippage_cost: float
    impact_cost: float
    rounding_cost: float
    fee_currency: str
    commission: float
    exchange_fee: float
    traded_notional: float          # |filled| × |reference_price| × point_value, in ``currency``
    liquidity_known_at: datetime | None
    roll_quantity: int = 0          # signed contracts of ``filled`` that are a leg of a roll (0 for an outright order)

    @property
    def execution_cost(self) -> float:
        return self.spread_cost + self.slippage_cost + self.impact_cost + self.rounding_cost


def capacity(liq: Liquidity, terms: CostTerms) -> int:
    """Whole contracts allowed per day by the participation cap."""
    return int(math.floor(terms.max_participation * liq.adv_contracts + 1e-9))


def fill_order(spec: ContractSpec, settlement: Settlement, quantity: int, liq: Liquidity, terms: CostTerms, *,
               decided_at: datetime, shortfall: str = "raise", reason: str = "decision", roll_quantity: int = 0) -> Fill:
    """Fill ``quantity`` (signed contracts) of ``spec`` at ``settlement``'s day, with the liquidity known at
    ``decided_at``. ``roll_quantity`` says how many of those contracts are a roll leg (same sign, not more).
    Pure: the same inputs always give the same ``Fill``."""
    q = U.contracts(quantity)
    rq = U.contracts(roll_quantity, "roll_quantity")
    if rq and (abs(rq) > abs(q) or (rq > 0) != (q > 0)):
        raise UnitError(f"roll_quantity {rq} must have the sign of the order {q} and be no larger")
    if shortfall not in SHORTFALL:
        raise UnitError(f"shortfall policy is one of {SHORTFALL}, not {shortfall!r}")
    if not isinstance(settlement, Settlement) or not getattr(settlement, "tradable", False):
        raise TypeError("a fill needs a tradable Settlement as its reference price, not an adjusted series value")
    if settlement.contract_id != spec.contract_id or liq.contract_id != spec.contract_id:
        raise UnitError("the settlement, the liquidity estimate and the contract must be the same contract month")
    decided_at = U.utc(decided_at, "decided_at")
    if liq.known_at > decided_at:
        raise LookAheadError(f"liquidity for {spec.contract_id} known at {liq.known_at.isoformat()} is used for a "
                             f"decision at {decided_at.isoformat()}")
    if settlement.known_at <= decided_at:
        raise LookAheadError(f"{spec.contract_id}: the settlement of {settlement.day} was already published at "
                             f"{settlement.known_at.isoformat()}, before the decision at {decided_at.isoformat()}; "
                             "a decision cannot trade at a price it has already seen")
    spec.require_model_tradable(settlement.day)
    side = 1 if q > 0 else -1
    cap = capacity(liq, terms)
    done = q
    if abs(q) > cap:
        if shortfall == "raise":
            raise LiquidityError(f"{spec.contract_id} on {settlement.day}: {abs(q)} contracts wanted, the cap allows "
                                 f"{cap} ({terms.max_participation:g} of ADV {liq.adv_contracts:g})")
        done = side * cap
    ref = settlement.price
    pv = spec.point_value
    n = abs(done)
    zero = dict(spread_cost=0.0, slippage_cost=0.0, impact_cost=0.0, rounding_cost=0.0, commission=0.0,
                exchange_fee=0.0, traded_notional=0.0)
    if n == 0:
        return Fill(settlement.day, spec.contract_id, spec.root, reason, q, 0, ref, ref, spec.currency,
                    fee_currency=terms.fee_currency, liquidity_known_at=liq.known_at, roll_quantity=0, **zero)
    s = terms.half_spread_ticks * spec.tick_size
    g = terms.slippage_ticks * spec.tick_size
    i = terms.impact_coefficient * liq.daily_vol_points * math.sqrt(n / liq.adv_contracts)
    raw = ref + side * (s + g + i)
    px = adverse_round(raw, spec.tick_size, side)
    r = side * (px - raw)           # >= 0 up to binary noise; not clipped, so the parts add up exactly
    return Fill(settlement.day, spec.contract_id, spec.root, reason, q, done, ref, px, spec.currency,
                spread_cost=s * n * pv, slippage_cost=g * n * pv, impact_cost=i * n * pv, rounding_cost=r * n * pv,
                fee_currency=terms.fee_currency, commission=n * terms.commission_per_contract,
                exchange_fee=n * terms.exchange_fee_per_contract, traded_notional=n * abs(ref) * pv,
                liquidity_known_at=liq.known_at, roll_quantity=side * min(abs(rq), n) if rq else 0)


def one_way_cost_fraction(spec: ContractSpec, reference_price: float, contracts: int, liq: Liquidity, terms: CostTerms,
                          fee_rate: float = 1.0) -> float:
    """The cost of one side of ``contracts`` as a fraction of the traded notional, at one price and one size.

    For comparison with a proportional one-way cost (``manhattan.engine.backtest.Instrument.cost``) only: it is
    exact for this price and size and nothing else (fees per contract and tick costs shrink as a fraction when the
    price rises; impact grows with size). ``fee_rate`` converts the fee currency into the contract currency."""
    n = abs(U.contracts(contracts))
    ref = U.finite(reference_price, "reference_price")
    if n == 0 or ref == 0:
        raise UnitError("a cost fraction needs a non-zero size and a non-zero price")
    if liq.adv_contracts <= 0:
        raise LiquidityError(f"{spec.contract_id}: ADV is zero, so no size can be traded")
    pv = spec.point_value
    s = (terms.half_spread_ticks + terms.slippage_ticks) * spec.tick_size
    i = terms.impact_coefficient * liq.daily_vol_points * math.sqrt(n / liq.adv_contracts)
    raw_up = ref + s + i
    r = adverse_round(raw_up, spec.tick_size, 1) - raw_up
    fees = (terms.commission_per_contract + terms.exchange_fee_per_contract) * U.finite(fee_rate, "fee_rate", positive=True)
    return ((s + i + max(r, 0.0)) * pv + fees) / (abs(ref) * pv)
