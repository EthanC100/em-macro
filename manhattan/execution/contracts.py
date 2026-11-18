"""Contract identifiers, contract metadata, tick arithmetic and the roll rule.

**Identifier.** ``<ROOT><month code><YYYY>``, for example ``SYNCLH2027`` = root ``SYNCL``, March 2027. The year has
four digits: ``CLH7`` could be 2017 or 2027 and is refused. The identifier must agree with ``root`` and
``delivery_month``.

**Units.** A price is quoted in ``price_unit_value`` units of ``currency`` per underlying unit (1.0 for dollars,
0.01 for cents) and a contract holds ``multiplier`` underlying units. So one price point is worth
``point_value = multiplier × price_unit_value`` of ``currency`` per contract, and one tick is worth
``tick_size × point_value``. The caller states ``tick_value`` as well; if it disagrees with that product the
metadata is refused (this is how a cents-quoted contract described as dollar-quoted is caught).

**Roll rule** (the repository's convention: ``ledger/janus_fut.py``, ``em_macro/commod_data.py``). A position is
opened in the earliest listed contract whose notice date (``min(first notice, last trade)``) is more than
``buffer_days`` calendar days after the trade day, and rolled at the settlement of the first trading day on which
the held contract is ``roll_before_notice_days`` or fewer calendar days from its notice date. The rule reads
contract metadata only (dates fixed at listing), never prices, volume or open interest, so it cannot look ahead.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal

from . import units as U
from .errors import InvalidContractError, MissingInputError, UnitError

MONTH_CODES = "FGHJKMNQUVXZ"            # January .. December
SETTLEMENT_TYPES = ("physical", "cash")
_ON_TICK_TOL = Decimal("1e-9")         # in ticks: tolerance for binary floating point (70.23 is not exact)


def contract_id(root: str, delivery_month: str) -> str:
    y, m = _month(delivery_month)
    return f"{root}{MONTH_CODES[m - 1]}{y:04d}"


def _month(s) -> tuple[int, int]:
    if not isinstance(s, str) or len(s) != 7 or s[4] != "-" or not (s[:4] + s[5:]).isdigit():
        raise UnitError(f"delivery_month must be 'YYYY-MM', not {s!r}")
    y, m = int(s[:4]), int(s[5:])
    if not 1 <= m <= 12:
        raise UnitError(f"delivery_month {s!r} has no month {m}")
    return y, m


@dataclass(frozen=True)
class ContractSpec:
    """One listed contract month. Every field is required except ``first_notice`` (None for cash settlement) and
    ``initial_margin`` (needed only when margin is reported or funded)."""
    contract_id: str
    root: str
    exchange: str
    delivery_month: str             # YYYY-MM
    currency: str                   # currency of prices, tick value, P&L and margin
    tick_size: float                # in price units
    tick_value: float               # currency per tick per contract
    multiplier: float               # underlying units per contract
    price_unit_value: float         # currency per price unit per underlying unit (1.0 dollars, 0.01 cents)
    first_trade: date
    last_trade: date
    settlement_type: str            # "physical" or "cash"
    first_notice: date | None = None
    initial_margin: float | None = None     # currency per contract, caller-supplied

    def __post_init__(self):
        for f in ("contract_id", "root", "exchange"):
            v = getattr(self, f)
            if not isinstance(v, str) or not v or v != v.strip():
                raise UnitError(f"{f} must be a non-empty string without surrounding spaces, not {v!r}")
        if not self.root.isalnum() or not self.root.isupper():
            raise UnitError(f"root must be upper-case letters and digits, not {self.root!r}")
        if self.contract_id != contract_id(self.root, self.delivery_month):
            raise UnitError(f"contract_id {self.contract_id!r} does not match root {self.root!r} and delivery month "
                            f"{self.delivery_month!r} (expected {contract_id(self.root, self.delivery_month)!r})")
        U.currency(self.currency)
        U.finite(self.tick_size, "tick_size", positive=True)
        U.finite(self.tick_value, "tick_value", positive=True)
        U.finite(self.multiplier, "multiplier", positive=True)
        U.finite(self.price_unit_value, "price_unit_value", positive=True)
        implied = self.tick_size * self.multiplier * self.price_unit_value
        if abs(implied - self.tick_value) > 1e-9 * max(1.0, abs(self.tick_value)):
            raise UnitError(f"{self.contract_id}: tick_value {self.tick_value} {self.currency} disagrees with "
                            f"tick_size x multiplier x price_unit_value = {implied:.10g}; check the price unit")
        U.day(self.first_trade, "first_trade")
        U.day(self.last_trade, "last_trade")
        if self.last_trade < self.first_trade:
            raise InvalidContractError(f"{self.contract_id}: last_trade is before first_trade")
        if self.settlement_type not in SETTLEMENT_TYPES:
            raise UnitError(f"settlement_type is one of {SETTLEMENT_TYPES}, not {self.settlement_type!r}")
        if self.settlement_type == "physical":
            if self.first_notice is None:
                raise MissingInputError(f"{self.contract_id}: a physically settled contract needs its first notice date")
            U.day(self.first_notice, "first_notice")
            if self.first_notice < self.first_trade:
                raise InvalidContractError(f"{self.contract_id}: first notice is before first trade")
        elif self.first_notice is not None:
            U.day(self.first_notice, "first_notice")
        if self.initial_margin is not None:
            U.finite(self.initial_margin, "initial_margin", nonneg=True)

    @property
    def point_value(self) -> float:
        """Currency per contract for a move of 1.0 in the quoted price."""
        return self.multiplier * self.price_unit_value

    @property
    def notice(self) -> date:
        """The date a holder must be out by: min(first notice, last trade)."""
        return min(self.first_notice, self.last_trade) if self.first_notice is not None else self.last_trade

    @property
    def physical(self) -> bool:
        return self.settlement_type == "physical"

    def tradable_on(self, d: date) -> bool:
        """Inside the exchange trading life (first to last trade day). For a physical contract the model allows
        less: see ``may_hold_into`` and ``require_model_tradable``."""
        return self.first_trade <= d <= self.last_trade

    def may_hold_into(self, d: date) -> bool:
        """May a position still be open at the close before trading day ``d`` and so be carried into ``d``?

        Two boundaries, and the earlier one binds:

        * **Expiry.** No contract may be carried past its last trading day (``d <= last_trade``): after it there is no
          market to close in, and final settlement is not modelled.
        * **Delivery** (physical only). This model has no delivery management, so a physically settled contract may
          not be carried into its first notice date either (``d < first_notice``), even when first notice falls
          after the last trading day. Exchanges that assign delivery on positions held earlier (a first position or
          intention day) are modelled by giving that earlier date as ``first_notice``."""
        if d > self.last_trade:
            return False
        return d < self.first_notice if self.physical else True

    def hold_boundary(self, d: date) -> str | None:
        """Why a position may not be carried into ``d`` (None when it may): the binding boundary, for messages."""
        if self.physical and d >= self.first_notice:
            return (f"its first notice date {self.first_notice} (delivery boundary; the model has no delivery "
                    "management)")
        if d > self.last_trade:
            return f"after its last trading day {self.last_trade} (expiry; final settlement is not modelled)"
        return None

    def require_model_tradable(self, d: date) -> None:
        """``require_tradable``, and no trade at all in a physical contract on or after its first notice date."""
        self.require_tradable(d)
        if self.physical and d >= self.first_notice:
            raise InvalidContractError(f"{self.contract_id} is physically settled and {d} is on or after its first "
                                       f"notice date {self.first_notice}: the model does not trade or hold it in the "
                                       "delivery period")

    def require_tradable(self, d: date) -> None:
        if d < self.first_trade:
            raise InvalidContractError(f"{self.contract_id} is not listed until {self.first_trade} (asked on {d})")
        if d > self.last_trade:
            raise InvalidContractError(f"{self.contract_id} stopped trading on {self.last_trade} (asked on {d})")


def require_spec(specs, cid: str) -> ContractSpec:
    s = specs.get(cid)
    if s is None:
        raise MissingInputError(f"no contract metadata for {cid!r}")
    return s


# ------------------------------------------------------------------ ticks
def _d(x: float) -> Decimal:
    return Decimal(repr(float(x)))


def _ticks(price: float, tick: float) -> tuple[Decimal, Decimal]:
    n = _d(price) / _d(tick)
    k = n.to_integral_value(rounding=ROUND_HALF_EVEN)
    return n, k


def on_tick(price: float, tick: float) -> bool:
    n, k = _ticks(price, tick)
    return abs(n - k) <= _ON_TICK_TOL


def round_to_tick(price: float, tick: float, mode: str) -> float:
    """``mode``: ``nearest`` (half to even), ``up`` or ``down``. A price already on the grid (within 1e-9 of a
    tick) stays where it is in every mode."""
    U.finite(price, "price")
    U.finite(tick, "tick", positive=True)
    if mode not in ("nearest", "up", "down"):
        raise ValueError(f"mode is 'nearest', 'up' or 'down', not {mode!r}")
    n, k = _ticks(price, tick)
    if abs(n - k) > _ON_TICK_TOL:
        if mode == "up":
            k = n.to_integral_value(rounding=ROUND_CEILING)
        elif mode == "down":
            k = n.to_integral_value(rounding=ROUND_FLOOR)
    return float(k * _d(tick))


def adverse_round(price: float, tick: float, side: int) -> float:
    """Round against the trader: a buy (side +1) up, a sell (side −1) down."""
    if side not in (1, -1):
        raise ValueError("side is +1 (buy) or -1 (sell)")
    return round_to_tick(price, tick, "up" if side > 0 else "down")


# ------------------------------------------------------------------ roll rule
@dataclass(frozen=True)
class RollPolicy:
    buffer_days: int                # open only contracts whose notice is more than this many days after the trade day
    roll_before_notice_days: int    # roll on the first trading day within this many days of the held notice date

    def __post_init__(self):
        for f in ("buffer_days", "roll_before_notice_days"):
            v = getattr(self, f)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise UnitError(f"{f} is a whole number of calendar days, 0 or more, not {v!r}")
        if self.buffer_days <= self.roll_before_notice_days:
            raise UnitError("buffer_days must exceed roll_before_notice_days, or a new contract is due to roll at once")

    def roll_due(self, spec: ContractSpec, d: date) -> bool:
        return (spec.notice - d).days <= self.roll_before_notice_days

    def must_exit(self, spec: ContractSpec, d: date, next_day: date) -> bool:
        """True when a position in ``spec`` has to be gone by the close of trading day ``d``: the roll window has
        been reached, the contract can no longer be traded, or carrying it into ``next_day`` would cross its
        delivery boundary or its last trading day (``ContractSpec.may_hold_into``)."""
        return self.roll_due(spec, d) or not spec.tradable_on(d) or not spec.may_hold_into(next_day)

    def select(self, specs, root: str, d: date) -> ContractSpec:
        """The contract to open for ``root`` on trading day ``d``, from metadata only."""
        cands = [s for s in specs.values() if s.root == root and s.tradable_on(d) and (s.notice - d).days > self.buffer_days]
        if not cands:
            if not any(s.root == root for s in specs.values()):
                raise MissingInputError(f"no contract metadata for root {root!r}")
            raise InvalidContractError(f"no listed {root} contract on {d} has its notice date more than "
                                       f"{self.buffer_days} days ahead")
        return min(cands, key=lambda s: (s.notice, s.delivery_month, s.contract_id))
