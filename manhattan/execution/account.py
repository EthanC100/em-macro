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
3. *Trades* at ``d``'s settlement (``manhattan.execution.costs.fill_order``). The gross already assumes the trade
   happened at the settlement, so the only trading charges are the execution parts (spread, slippage, impact,
   tick rounding) and the fees. Nothing is charged twice: ``net = gross − costs`` and, equivalently, the net equals
   the cash flows at the actual fill prices plus the final marks, minus fees and financing.
4. *Exposure* after the close: gross and net notional at settlement, and margin.

**Missing data** (``on_missing_price``). ``raise`` (default): any held or traded contract without a settlement on
a calendar day stops the run. ``hold``: a held contract keeps its last mark and the gap's P&L is booked on the day
its price returns; a trade in it waits. Holding a contract past its last trading day always stops the run.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

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
    gross_exposure: float           # after the close
    net_exposure: float
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
    why: str                        # "liquidity", "no settlement", "roll leg not closed" or "roll leg not opened"


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
        """SHA-256 of a canonical form (amounts rounded to 8 decimals): equal inputs give equal hashes."""
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
        doc = {"base": self.base_currency, "scenario_id": self.scenario_id, "capital": self.capital,
               "days": [asdict(r) for r in self.days], "fills": [asdict(f) for f in self.fills],
               "rolls": [asdict(r) for r in self.rolls], "unfilled": [asdict(u) for u in self.unfilled],
               "unexecuted": [asdict(d) for d in self.unexecuted]}
        b = json.dumps(canon(doc), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(b).hexdigest()


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


def run(market: MarketData, decisions, policy: ExecutionPolicy, scenario: CostScenario) -> Result:
    """Account for ``decisions`` under ``policy`` and ``scenario``. Pure and deterministic."""
    if not isinstance(market, MarketData):
        raise TypeError("market must be a MarketData")
    if not isinstance(scenario, CostScenario):
        raise TypeError("scenario must be a CostScenario")
    base = policy.base_currency
    specs = market.specs
    by_day, unexecuted = _schedule(market, tuple(decisions), policy, scenario)
    pos: dict[str, int] = {}
    mark: dict[str, float] = {}
    target: dict[str, int] = {}
    days, fills, rolls, unfilled = [], [], [], []
    for k, td in enumerate(market.calendar):
        d = td.day
        acc = dict.fromkeys(("gross", *COST_PARTS, "turnover"), 0.0)
        stale = []
        # 1. marks and 2. financing, on the positions held over (D_{k-1}, D_k]
        for cid in sorted(pos):
            q, spec = pos[cid], specs[cid]
            if d > spec.last_trade:
                raise InvalidContractError(f"{cid} is still held ({q} contracts) on {d}, after its last trading day "
                                           f"{spec.last_trade}")
            st = market.settlement(cid, d)
            if st is None:
                if policy.on_missing_price == "raise":
                    raise MissingInputError(f"no settlement for held contract {cid} on {d}")
                stale.append(cid)
            else:
                acc["gross"] += market.convert(q * (st.price - mark[cid]) * spec.point_value, spec.currency, base, d)
                mark[cid] = st.price
            terms = scenario.for_root(spec.root)
            if k and terms.margin_funding_bps_per_year > 0:
                if spec.initial_margin is None:
                    raise MissingInputError(f"{cid}: margin funding is costed but its initial margin is not given")
                yrs = (d - market.calendar[k - 1].day).days / 365.0
                acc["financing"] += market.convert(abs(q) * spec.initial_margin * terms.margin_funding_bps_per_year
                                                   / 1e4 * yrs, spec.currency, base, d)
        # 3. trades
        today = by_day.get(k, {})
        for root, dec in today.items():
            target[root] = dec.contracts
        roots = sorted(set(target) | {specs[c].root for c in pos})
        for root in roots:
            tgt = target.get(root, 0)
            held = {c: q for c, q in pos.items() if specs[c].root == root and q}
            if tgt == 0:
                desired, primary = {}, None
            else:
                only = next(iter(held)) if len(held) == 1 else None
                if only is not None and specs[only].tradable_on(d) and not policy.roll.roll_due(specs[only], d):
                    primary = only
                else:
                    primary = policy.roll.select(specs, root, d).contract_id
                desired = {primary: tgt}
            trades = {c: desired.get(c, 0) - held.get(c, 0) for c in sorted(set(desired) | set(held))}
            trades = {c: q for c, q in trades.items() if q}
            if not trades:
                continue
            if root in today:
                reason, t_liq = "decision", today[root].decided_at
            else:
                if k == 0:
                    raise InvalidContractError(f"{root}: a trade without a decision on the first day")   # unreachable
                rolling = bool(held) and primary is not None and (primary not in held or len(held) > 1)
                reason = "roll" if rolling else "carry"
                t_liq = market.calendar[k - 1].close_at
            terms = scenario.for_root(root)
            done = {}
            closes = [c for c in trades if c in held and c != primary]
            opens = [c for c in trades if c not in closes]
            close_room = None
            if reason == "roll" and primary in trades:
                # a roll is a calendar spread: never close more of the old month than the new month can absorb
                if market.settlement(primary, d) is None:
                    if policy.on_missing_price == "raise":
                        raise MissingInputError(f"no settlement for {primary} on {d}, so the roll cannot be filled")
                    close_room = 0
                elif policy.on_liquidity_shortfall == "clip":
                    close_room = capacity(market.liquidity_as_of(primary, t_liq), terms)
            for cid in closes + opens:
                q = trades[cid]
                if close_room is not None and cid in closes:
                    allowed = min(abs(q), close_room)
                    if allowed < abs(q):
                        unfilled.append(Unfilled(d, cid, q, (1 if q > 0 else -1) * allowed, "roll leg not opened"))
                        q = (1 if q > 0 else -1) * allowed
                    close_room -= allowed
                    if not q:
                        continue
                if reason == "roll" and cid not in closes:
                    # never open more of the new month than was closed of the old one today
                    room = sum(abs(done.get(c, 0)) for c in closes)
                    if abs(q) > room:
                        unfilled.append(Unfilled(d, cid, q, (1 if q > 0 else -1) * room, "roll leg not closed"))
                        q = (1 if q > 0 else -1) * room
                    if not q:
                        continue
                spec = require_spec(specs, cid)
                st = market.settlement(cid, d)
                if st is None:
                    if policy.on_missing_price == "raise":
                        raise MissingInputError(f"no settlement for {cid} on {d}, so the trade cannot be filled")
                    unfilled.append(Unfilled(d, cid, q, 0, "no settlement"))
                    continue
                liq = market.liquidity_as_of(cid, t_liq)
                f = fill_order(spec, st, q, liq, terms, decided_at=t_liq, shortfall=policy.on_liquidity_shortfall,
                               reason=reason)
                fills.append(f)
                if f.filled != f.requested:
                    unfilled.append(Unfilled(d, cid, f.requested, f.filled, "liquidity"))
                if not f.filled:
                    continue
                done[cid] = f.filled
                pos[cid] = pos.get(cid, 0) + f.filled
                mark[cid] = st.price
                for part, amount, ccy in (("spread", f.spread_cost, f.currency), ("slippage", f.slippage_cost, f.currency),
                                          ("impact", f.impact_cost, f.currency), ("rounding", f.rounding_cost, f.currency),
                                          ("commission", f.commission, f.fee_currency),
                                          ("exchange_fee", f.exchange_fee, f.fee_currency),
                                          ("turnover", f.traded_notional, f.currency)):
                    acc[part] += market.convert(amount, ccy, base, d)
            if reason == "roll" and primary in done:
                closed = [c for c in done if c != primary and c in held]
                if closed:
                    moved = min(abs(done[primary]), sum(abs(done[c]) for c in closed))
                    a, b = market.settlement(closed[0], d).price, market.settlement(primary, d).price
                    rolls.append(RollEvent(d, root, tuple(closed), primary, moved, a, b, b - a))
        for cid in [c for c, q in pos.items() if q == 0]:
            del pos[cid], mark[cid]
        # 4. exposure and margin after the close
        gexp = nexp = 0.0
        if policy.report_margin or all(specs[c].initial_margin is not None for c in pos):
            margin = 0.0
        else:
            margin = None                                             # not reported: some initial margin is unknown
        for cid in sorted(pos):
            q, spec = pos[cid], specs[cid]
            notional = market.convert(q * mark[cid] * spec.point_value, spec.currency, base, d)
            gexp += abs(notional)
            nexp += notional
            if margin is not None:
                if spec.initial_margin is None:
                    raise MissingInputError(f"{cid}: margin is reported but its initial margin is not given")
                margin += market.convert(abs(q) * spec.initial_margin, spec.currency, base, d)
        costs = sum(acc[p] for p in COST_PARTS)
        days.append(DayRecord(d, acc["gross"], *(acc[p] for p in COST_PARTS), net=acc["gross"] - costs,
                              turnover=acc["turnover"], gross_exposure=gexp, net_exposure=nexp, margin=margin,
                              positions=tuple(sorted(pos.items())), stale_marks=tuple(stale)))
    return Result(base, scenario.name, scenario.scenario_id(), scenario.provenance, policy.capital, tuple(days),
                  tuple(fills), tuple(rolls), tuple(unfilled), unexecuted,
                  meta={"lag": policy.lag, "roll": asdict(policy.roll), "on_missing_price": policy.on_missing_price,
                        "on_liquidity_shortfall": policy.on_liquidity_shortfall, "calibrated": False})


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
