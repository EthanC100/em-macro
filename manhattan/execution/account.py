"""Daily accounting of a futures position plan: gross versus net, costs by kind, turnover, exposure, rolls.

**Inputs.** A ``MarketData`` (calendar, contract metadata, tradable settlements, liquidity, FX), a sequence of
``Decision`` (hold ``contracts`` of ``root`` from now on, decided at ``decided_at``), an ``ExecutionPolicy`` and a
``CostScenario``. Decisions name a **root**, not a contract month: the roll rule picks the month.

**Time line.** A decision taken at ``decided_at`` executes at the settlement of the ``lag``-th trading day whose
close is strictly after ``decided_at`` (``lag`` ≥ 1: a decision never trades at a price that was already printed
when it was taken). Liquidity used to size and cost it is the latest estimate known at ``decided_at``. A roll, or
the rest of an order the liquidity cap clipped, is worked on later days with the liquidity known at the previous
day's close. Decisions that could only execute after the last day of the calendar are reported, not executed.

**Each day** ``d`` (in order):

1. *Marks.* Every contract held over the period is marked to its settlement on ``d``:
   ``gross += q × (S_d − S_prev) × point_value``, converted to the base currency at ``d``'s rate. The same-contract
   price change is the whole P&L: the roll yield is in it, and nothing is booked for the price difference between
   two contract months at a roll.
2. *Financing.* ``|q| × initial_margin × bp/10,000 × days/365`` for the margin held over the period, when the
   scenario funds margin. Futures need no financing of their notional: returns are in excess of cash.
3. *Trades* at ``d``'s settlement (``manhattan.execution.costs.fill_order``), per root: first a **roll**, decided
   from the holdings alone (any held month that is not the month to hold), executed as a paired calendar spread;
   then the **net change** of the target, outright (``_plan_root``; design section 7). A decision on a roll day is
   a roll plus a net change, never a replacement for the roll. The gross already assumes the trade
   happened at the settlement, so the only trading charges are the execution parts (spread, slippage, impact,
   tick rounding) and the fees. Nothing is charged twice: ``net = gross − costs`` and, equivalently, the net equals
   the cash flows at the actual fill prices plus the final marks, minus fees and financing.
4. *Exposure* after the close: gross and net notional at settlement, and margin.

**Missing data** (``on_missing_price``). ``raise`` (default): any held or traded contract without a settlement on
a calendar day stops the run. ``hold``: a held contract keeps its last mark and the gap's P&L is booked on the day
its price returns; a trade in it waits. A position is never carried across a delivery boundary: a physical
contract must be flat by the close before its first notice date, a cash-settled one by the close of its last
trading day (``ContractSpec.may_hold_into``), or the run stops.

**FX.** Day ``d``'s amounts are valued at ``d``'s fix: ex post by default, or only with rates published by the close
plus ``fx_valuation_cutoff``. Nothing here decides from FX; decision-time conversion is ``MarketData.rate_as_of``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

from . import units as U
from .contracts import RollPolicy, require_spec
from .costs import SHORTFALL, CostScenario, capacity, fill_order
from .errors import InvalidContractError, LookAheadError, MissingInputError, UnitError
from .market import MarketData

MISSING = ("raise", "hold")


@dataclass(frozen=True)
class Decision:
    root: str
    contracts: int                  # signed target holding, whole contracts
    decided_at: datetime
    inputs_known_at: datetime | None = None     # the latest time of any input the decision used, if the caller knows it

    def __post_init__(self):
        if not isinstance(self.root, str) or not self.root:
            raise UnitError(f"a decision names a root, not {self.root!r}")
        U.contracts(self.contracts, f"target of {self.root}")
        object.__setattr__(self, "decided_at", U.utc(self.decided_at, "decided_at"))
        if self.inputs_known_at is not None:
            t = U.utc(self.inputs_known_at, "inputs_known_at")
            object.__setattr__(self, "inputs_known_at", t)
            if t > self.decided_at:
                raise LookAheadError(f"a {self.root} decision at {self.decided_at.isoformat()} used an input known only "
                                     f"at {t.isoformat()}")


@dataclass(frozen=True)
class ExecutionPolicy:
    base_currency: str
    roll: RollPolicy
    lag: int = 1
    on_missing_price: str = "raise"
    on_liquidity_shortfall: str = "raise"
    capital: float | None = None    # base currency; when given, every amount is also reported as a fraction of it
    report_margin: bool = False     # require initial margin for every held contract and report it
    fx_valuation_cutoff: timedelta | None = None    # None: ex-post valuation; else rates must be known by close + this

    def __post_init__(self):
        U.currency(self.base_currency)
        if not isinstance(self.roll, RollPolicy):
            raise TypeError("roll must be a RollPolicy")
        if isinstance(self.lag, bool) or not isinstance(self.lag, int) or self.lag < 1:
            raise UnitError("lag is a whole number of trading days, at least 1")
        if self.on_missing_price not in MISSING:
            raise UnitError(f"on_missing_price is one of {MISSING}")
        if self.on_liquidity_shortfall not in SHORTFALL:
            raise UnitError(f"on_liquidity_shortfall is one of {SHORTFALL}")
        if self.capital is not None:
            U.finite(self.capital, "capital", positive=True)
        if self.fx_valuation_cutoff is not None:
            if not isinstance(self.fx_valuation_cutoff, timedelta) or self.fx_valuation_cutoff < timedelta(0):
                raise UnitError("fx_valuation_cutoff is a non-negative timedelta after the day's close, or None")

    def describe(self) -> dict:
        """The policy as plain data: part of the result hash, so two runs under different rules never share one."""
        cut = self.fx_valuation_cutoff
        return {"base_currency": self.base_currency, "roll": asdict(self.roll), "lag": self.lag,
                "on_missing_price": self.on_missing_price, "on_liquidity_shortfall": self.on_liquidity_shortfall,
                "capital": self.capital, "report_margin": self.report_margin,
                "fx_valuation": "ex_post" if cut is None else f"by_close_plus_{int(cut.total_seconds())}s",
                "calibrated": False}


COST_PARTS = ("spread", "slippage", "impact", "rounding", "commission", "exchange_fee", "financing")


@dataclass(frozen=True)
class DayRecord:
    """One trading day, all amounts in the base currency."""
    day: date
    gross: float
    spread: float
    slippage: float
    impact: float
    rounding: float
    commission: float
    exchange_fee: float
    financing: float
    net: float
    turnover: float                 # Σ |filled| × |settlement| × point value
    gross_exposure: float           # after the close: Σ |q| × |S| × point value
    net_exposure: float             # Σ sign(q) × |q| × |S| × point value: a long is positive at any price
    margin: float | None
    positions: tuple                # ((contract_id, contracts), ...) after the close
    stale_marks: tuple = ()         # held contracts with no settlement today (``hold`` policy)

    @property
    def costs(self) -> float:
        return sum(getattr(self, p) for p in COST_PARTS)


@dataclass(frozen=True)
class RollEvent:
    day: date
    root: str
    from_contracts: tuple           # contract ids closed
    to_contract: str
    contracts: int                  # contracts moved (the smaller of closed and opened)
    from_price: float               # settlement of the (first) closed month on the roll day
    to_price: float                 # settlement of the new month on the roll day
    calendar_gap_points: float      # to_price − from_price: what a naive spliced series would book as a jump


@dataclass(frozen=True)
class Unfilled:
    day: date
    contract_id: str
    requested: int
    filled: int
    why: str                        # "no settlement", "liquidity" (its own cap), "paired leg" (the roll's other leg)
                                    # or "reversal: old side not closed" (an opposite-side position is still open)
    reason: str = ""                # what the order was: "decision", "carry", "roll" or "roll+decision"/"roll+carry"


@dataclass(frozen=True)
class Result:
    base_currency: str
    scenario: str
    scenario_id: str
    provenance: str
    capital: float | None
    days: tuple
    fills: tuple
    rolls: tuple
    unfilled: tuple
    unexecuted: tuple               # decisions that could not execute inside the calendar
    meta: dict = field(default_factory=dict)
    market_digest: str = ""         # MarketData.digest() of the inputs (S6 N4)
    decisions_digest: str = ""      # decisions_digest() of the decisions

    def totals(self) -> dict:
        out = {k: sum(getattr(r, k) for r in self.days) for k in ("gross", *COST_PARTS, "net", "turnover")}
        out["costs"] = sum(out[p] for p in COST_PARTS)
        out["execution_costs"] = out["spread"] + out["slippage"] + out["impact"] + out["rounding"]
        out["fees"] = out["commission"] + out["exchange_fee"]
        out.update(n_days=len(self.days), n_fills=sum(1 for f in self.fills if f.filled), n_rolls=len(self.rolls),
                   n_unfilled=len(self.unfilled), n_unexecuted=len(self.unexecuted),
                   contracts_traded=sum(abs(f.filled) for f in self.fills))
        if self.capital:
            for k in ("gross", "costs", "net", "turnover"):
                out[f"{k}_fraction_of_capital"] = out[k] / self.capital
        return out

    def result_hash(self) -> str:
        """SHA-256 of a canonical form of the run: the digest of the market inputs and of the decisions, the
        policy, the scenario id and every output, amounts rounded to 8 decimals of the base currency. The same
        inputs give the same hash; any change of an input value, a position, fill, cost (beyond 1e-8), policy or
        scenario changes it. It identifies the run; it does not authenticate where the market data came from
        (design section 15)."""
        def canon(x):
            if isinstance(x, float):
                return format(round(x, 8) + 0.0, ".8f")
            if isinstance(x, (date, datetime)):
                return x.isoformat()
            if isinstance(x, dict):
                return {k: canon(v) for k, v in sorted(x.items())}
            if isinstance(x, (list, tuple)):
                return [canon(v) for v in x]
            return x
        doc = {"base": self.base_currency, "scenario_id": self.scenario_id, "capital": self.capital, "policy": self.meta,
               "market_digest": self.market_digest, "decisions_digest": self.decisions_digest,
               "days": [asdict(r) for r in self.days], "fills": [asdict(f) for f in self.fills],
               "rolls": [asdict(r) for r in self.rolls], "unfilled": [asdict(u) for u in self.unfilled],
               "unexecuted": [asdict(d) for d in self.unexecuted]}
        b = json.dumps(canon(doc), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(b).hexdigest()


def decisions_digest(decisions) -> str:
    """SHA-256 of the decisions in a canonical, order-free form: (root, contracts, decided_at, inputs_known_at)."""
    rows = sorted([d.root, d.contracts, d.decided_at.isoformat(),
                   d.inputs_known_at.isoformat() if d.inputs_known_at else None] for d in decisions)
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("ascii")).hexdigest()


def execution_index(market: MarketData, decided_at: datetime, lag: int) -> int | None:
    """Index of the trading day a decision executes on, or None when it falls after the calendar."""
    after = [i for i, t in enumerate(market.calendar) if t.close_at > decided_at]
    return after[lag - 1] if len(after) >= lag else None


def _schedule(market: MarketData, decisions, policy: ExecutionPolicy, scenario: CostScenario):
    by_day: dict[int, dict[str, Decision]] = {}
    unexecuted = []
    for dec in sorted(decisions, key=lambda x: (x.decided_at, x.root, x.contracts)):
        if not isinstance(dec, Decision):
            raise TypeError("decisions are Decision objects")
        if not any(s.root == dec.root for s in market.specs.values()):
            raise MissingInputError(f"no contract metadata for root {dec.root!r}")
        scenario.for_root(dec.root)
        k = execution_index(market, dec.decided_at, policy.lag)
        if k is None:
            unexecuted.append(dec)
            continue
        day = by_day.setdefault(k, {})
        prev = day.get(dec.root)
        if prev is not None and prev.decided_at == dec.decided_at and prev.contracts != dec.contracts:
            raise UnitError(f"two {dec.root} decisions at {dec.decided_at.isoformat()} disagree: ambiguous")
        day[dec.root] = dec                                           # the later decision of the day wins
    return by_day, tuple(unexecuted)


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def _plan_root(held: dict, tgt: int, primary: str | None) -> tuple[int, dict, dict]:
    """Split today's trades in one root into a roll and a net change.

    ``held``: contracts held now (non-zero). ``primary``: the month to hold after today (None when the target is
    flat). Returns ``(K, roll, net)``: ``K`` the signed contracts to move from the other months into ``primary`` as
    a calendar spread, ``roll`` the signed close of each old month that belongs to that spread (and ``+K`` on
    ``primary``), ``net`` every remaining signed trade (closing the rest of the old months, and the change of the
    target in ``primary``). ``roll + net`` takes ``held`` exactly to ``{primary: tgt}``."""
    old = {c: q for c, q in held.items() if c != primary}
    p = held.get(primary, 0) if primary else 0
    want = tgt - p                                                   # what ``primary`` still needs
    old_sum = sum(old.values())
    K = _sign(want) * min(abs(old_sum), abs(want)) if primary and old_sum and _sign(old_sum) == _sign(want) else 0
    roll, left = {}, abs(K)
    for c in sorted(old):                                            # move from the old months in a fixed order
        if left and _sign(old[c]) == _sign(K):
            x = min(left, abs(old[c]))
            roll[c] = -_sign(old[c]) * x
            left -= x
    if K:
        roll[primary] = K
    net = {c: -(q + roll.get(c, 0)) for c, q in old.items()}         # the rest of each old month is closed outright
    if primary:
        net[primary] = want - K                                      # the change of the target, outright
    return K, roll, {c: q for c, q in net.items() if q}


def run(market: MarketData, decisions, policy: ExecutionPolicy, scenario: CostScenario) -> Result:
    """Account for ``decisions`` under ``policy`` and ``scenario``. Pure and deterministic."""
    if not isinstance(market, MarketData):
        raise TypeError("market must be a MarketData")
    if not isinstance(scenario, CostScenario):
        raise TypeError("scenario must be a CostScenario")
    base = policy.base_currency
    specs = market.specs
    cal = market.calendar
    decisions = tuple(decisions)
    by_day, unexecuted = _schedule(market, decisions, policy, scenario)
    pos: dict[str, int] = {}
    mark: dict[str, float] = {}
    target: dict[str, int] = {}
    days, fills, rolls, unfilled = [], [], [], []

    def fx(amount: float, ccy: str, k: int) -> float:
        """Valuation of a day-``k`` amount in the base currency (section 13 of the design)."""
        if ccy == base:
            return amount
        d = cal[k].day
        if policy.fx_valuation_cutoff is not None:
            rec = market.fx.get((ccy, base, d)) or market.fx.get((base, ccy, d))
            limit = cal[k].close_at + policy.fx_valuation_cutoff
            if rec is not None and rec.known_at > limit:
                raise LookAheadError(f"{rec.base}{rec.quote} rate of {d} was published at {rec.known_at.isoformat()}, "
                                     f"after the valuation cut-off {limit.isoformat()}")
        return market.convert(amount, ccy, base, d)

    for k, td in enumerate(cal):
        d = td.day
        next_day = cal[k + 1].day if k + 1 < len(cal) else d + timedelta(days=1)
        acc = dict.fromkeys(("gross", *COST_PARTS, "turnover"), 0.0)
        stale = []
        # 1. marks and 2. financing, on the positions held over (D_{k-1}, D_k]
        for cid in sorted(pos):
            q, spec = pos[cid], specs[cid]
            if not spec.may_hold_into(d):                             # defence in depth: the close check stops this
                raise InvalidContractError(f"{cid} is held ({q} contracts) into {d}: {spec.hold_boundary(d)}")
            st = market.settlement(cid, d)
            if st is None:
                if policy.on_missing_price == "raise":
                    raise MissingInputError(f"no settlement for held contract {cid} on {d}")
                stale.append(cid)
            else:
                acc["gross"] += fx(q * (st.price - mark[cid]) * spec.point_value, spec.currency, k)
                mark[cid] = st.price
            terms = scenario.for_root(spec.root)
            if k and terms.margin_funding_bps_per_year > 0:
                if spec.initial_margin is None:
                    raise MissingInputError(f"{cid}: margin funding is costed but its initial margin is not given")
                yrs = (d - cal[k - 1].day).days / 365.0
                acc["financing"] += fx(abs(q) * spec.initial_margin * terms.margin_funding_bps_per_year / 1e4 * yrs,
                                       spec.currency, k)
        # 3. trades: per root, a paired roll first, then the net change of the target
        today = by_day.get(k, {})
        for root, dec in today.items():
            target[root] = dec.contracts
        for root in sorted(set(target) | {specs[c].root for c in pos}):
            tgt = target.get(root, 0)
            held = {c: q for c, q in pos.items() if specs[c].root == root and q}
            if not held and tgt == 0:
                continue
            dec = today.get(root)
            if dec is None and k == 0:
                raise InvalidContractError(f"{root}: a trade without a decision on the first day")   # unreachable
            t_liq = dec.decided_at if dec is not None else cal[k - 1].close_at
            base_reason = "decision" if dec is not None else "carry"
            primary = None
            if tgt:
                staying = sorted(c for c in held if not policy.roll.must_exit(specs[c], d, next_day))
                choice = policy.roll.select(specs, root, d).contract_id
                if choice in staying or not staying:
                    primary = choice
                else:
                    primary = max(staying, key=lambda c: (abs(held[c]), c))
                if policy.roll.must_exit(specs[primary], d, next_day):
                    raise InvalidContractError(f"{root}: no contract on {d} can be held past the next trading day "
                                               f"({primary} reaches its delivery boundary or last trading day)")
            # a reversal closes first: positions on the other side of the target are closed before anything is
            # opened in the target's direction, and a reversal is never booked as a roll (S6 N1)
            against = {c: q for c, q in held.items() if tgt and _sign(q) == -_sign(tgt)}
            keep = {c: q for c, q in held.items() if c not in against}
            close1 = {c: -q for c, q in against.items()}
            K, roll, net = _plan_root(keep, tgt, primary)
            legs = sorted(set(close1) | set(roll) | set(net))
            if not legs:
                continue
            want = {c: close1.get(c, 0) + roll.get(c, 0) + net.get(c, 0) for c in legs}
            terms = scenario.for_root(root)
            # what each contract can trade today: its cap under ``clip`` (unbounded under ``raise``: fill_order then
            # refuses an order over the cap); nothing without a settlement under ``hold``
            avail, own = {}, {}
            for c in legs:
                st = market.settlement(c, d)
                if st is None:
                    if policy.on_missing_price == "raise":
                        raise MissingInputError(f"no settlement for {c} on {d}, so the trade cannot be filled")
                    avail[c] = 0
                elif policy.on_liquidity_shortfall == "clip":
                    avail[c] = capacity(market.liquidity_as_of(c, t_liq), terms)
                else:
                    avail[c] = abs(close1.get(c, 0)) + abs(roll.get(c, 0)) + abs(net.get(c, 0))
                own[c] = avail[c]
            close_done = {}
            for c in sorted(close1):
                x = min(abs(close1[c]), avail[c])
                if x:
                    close_done[c] = _sign(close1[c]) * x
                    avail[c] -= x
            reversed_fully = all(abs(close_done.get(c, 0)) == abs(q) for c, q in close1.items())
            if not reversed_fully:
                # the old side is still open: nothing may be opened on the new side today; positions already on
                # the target's side may still be rolled (exposure-neutral), but not increased
                K, roll, net = _plan_root(keep, sum(keep.values()), primary if keep else None)
            # risk-reducing trades next (S6 N3): closing what the target no longer needs comes before the roll,
            # so a cut is never queued behind a roll for the same old month's capacity
            net_done = {}
            for c in sorted(net):
                if c in keep and _sign(net[c]) == -_sign(keep[c]):
                    x = min(abs(net[c]), abs(keep[c]), avail[c])
                    if x:
                        net_done[c] = _sign(net[c]) * x
                        avail[c] -= x
            # the roll moves only as many contracts as both sides can trade: exposure neither lapses nor doubles
            n = 0
            if K:
                closable = sum(min(abs(roll[c]), avail[c]) for c in roll if c != primary)
                n = min(abs(K), avail[primary], closable)
            roll_done, left = {}, n
            for c in sorted(c for c in roll if c != primary):
                x = min(left, abs(roll[c]), avail[c])
                if x:
                    roll_done[c] = _sign(roll[c]) * x
                    avail[c] -= x
                    left -= x
            if n:
                roll_done[primary] = _sign(K) * n
                avail[primary] -= n
            # then the trades that add exposure, with what capacity is left
            for c in sorted(net):
                x = min(abs(net[c]) - abs(net_done.get(c, 0)), avail[c])
                if x > 0:
                    net_done[c] = net_done.get(c, 0) + _sign(net[c]) * x
                    avail[c] -= x
            moved_from = []
            for c in legs:
                r_q, n_q = roll_done.get(c, 0), net_done.get(c, 0) + close_done.get(c, 0)
                q = r_q + n_q
                if q != want[c]:
                    why = ("no settlement" if market.settlement(c, d) is None
                           else "liquidity" if abs(q) >= own[c]
                           else "reversal: old side not closed" if not reversed_fully and c not in close1
                           else "paired leg")
                    unfilled.append(Unfilled(d, c, want[c], q, why, base_reason if not roll.get(c) else
                                             ("roll" if not (net.get(c) or close1.get(c)) else f"roll+{base_reason}")))
                if not q:
                    continue
                reason = "roll" if not n_q else (base_reason if not r_q else f"roll+{base_reason}")
                st = market.settlement(c, d)
                f = fill_order(require_spec(specs, c), st, q, market.liquidity_as_of(c, t_liq), terms,
                               decided_at=t_liq, shortfall=policy.on_liquidity_shortfall, reason=reason,
                               roll_quantity=r_q)
                fills.append(f)
                pos[c] = pos.get(c, 0) + f.filled
                mark[c] = st.price
                if r_q and c != primary:
                    moved_from.append(c)
                for part, amount, ccy in (("spread", f.spread_cost, f.currency), ("slippage", f.slippage_cost, f.currency),
                                          ("impact", f.impact_cost, f.currency), ("rounding", f.rounding_cost, f.currency),
                                          ("commission", f.commission, f.fee_currency),
                                          ("exchange_fee", f.exchange_fee, f.fee_currency),
                                          ("turnover", f.traded_notional, f.currency)):
                    acc[part] += fx(amount, ccy, k)
            if n:
                a = market.settlement(moved_from[0], d).price
                b = market.settlement(primary, d).price
                rolls.append(RollEvent(d, root, tuple(moved_from), primary, n, a, b, b - a))
        for cid in [c for c, q in pos.items() if q == 0]:
            del pos[cid], mark[cid]
        # the delivery boundary and the last trading day: fail closed at the close, never carry a position across
        for cid in sorted(pos):
            spec = specs[cid]
            if not spec.may_hold_into(next_day):
                raise InvalidContractError(f"{cid} is still held ({pos[cid]} contracts) at the close of {d} and would be "
                                           f"carried into {next_day}: {spec.hold_boundary(next_day)}")
        # 4. exposure and margin after the close
        gexp = nexp = 0.0
        if policy.report_margin or all(specs[c].initial_margin is not None for c in pos):
            margin = 0.0
        else:
            margin = None                                             # not reported: some initial margin is unknown
        for cid in sorted(pos):
            q, spec = pos[cid], specs[cid]
            size = fx(abs(q) * abs(mark[cid]) * spec.point_value, spec.currency, k)
            gexp += size
            nexp += _sign(q) * size                                   # signed by the position, not by the price
            if margin is not None:
                if spec.initial_margin is None:
                    raise MissingInputError(f"{cid}: margin is reported but its initial margin is not given")
                margin += fx(abs(q) * spec.initial_margin, spec.currency, k)
        costs = sum(acc[p] for p in COST_PARTS)
        days.append(DayRecord(d, acc["gross"], *(acc[p] for p in COST_PARTS), net=acc["gross"] - costs,
                              turnover=acc["turnover"], gross_exposure=gexp, net_exposure=nexp, margin=margin,
                              positions=tuple(sorted(pos.items())), stale_marks=tuple(stale)))
    return Result(base, scenario.name, scenario.scenario_id(), scenario.provenance, policy.capital, tuple(days),
                  tuple(fills), tuple(rolls), tuple(unfilled), unexecuted, meta=policy.describe(),
                  market_digest=market.digest(), decisions_digest=decisions_digest(decisions))


def run_scenarios(market: MarketData, decisions, policy: ExecutionPolicy, scenarios) -> dict:
    """The same plan under every scenario, keyed and ordered by scenario name. Names must be unique."""
    scen = list(scenarios)
    names = [s.name for s in scen]
    if len(set(names)) != len(names):
        raise UnitError("scenario names must be unique")
    if not scen:
        raise MissingInputError("no cost scenarios given")
    decisions = tuple(decisions)
    return {s.name: run(market, decisions, policy, s) for s in sorted(scen, key=lambda s: s.name)}


def sensitivity_table(results: dict) -> list[dict]:
    """One row of totals per scenario, sorted by name, with the scenario id and the result hash."""
    rows = []
    for name in sorted(results):
        r = results[name]
        rows.append({"scenario": name, "scenario_id": r.scenario_id, "provenance": r.provenance, **r.totals(),
                     "result_hash": r.result_hash()})
    return rows
