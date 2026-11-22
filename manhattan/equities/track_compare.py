"""Technology-only, non-technology-only and combined equity portfolios on one pipeline (issue #102). Synthetic only.

    cfg = CompareConfig(is_end=date(2006, 12, 29))
    report = compare(world, cfg, cost_model)          # per sleeve: costs, drawdown, volatility; correlations; OOS
    vols = sector_volatility(world, start, end)       # measured, never assumed

This is **infrastructure validation**: a fixed, declared portfolio rule run through the shared equity pipeline so that
every control can be checked. It is not a strategy search and not evidence. **It runs only on a synthetic world**
(``synthetic.is_synthetic``). No draft catalogue family can be tested through it, and any experiment on another world
must first be pre-registered and admitted by ``registration.admit`` (hypothesis first; issue #102 review). Every report carries
``evidential_weight: 0``, ``scientifically_validated: False`` and ``evidence_class: synthetic_infrastructure``.

**Controls, each tested in tests/test_manhattan_equities_nontech.py:**

* **Universe.** Each sleeve's universe on each decision day is ``universe.track_snapshots`` on that day, with the
  classification, listing, liquidity, price, history and corporate-action screens all evaluated as known at that
  close. Companies that later failed are in it before they failed; an IPO is absent before it lists.
* **Signal.** Total return over ``[t - lookback, t - skip]``, read through ``PriceBook.total_returns(as_of=t)``.
  Splits and dividends are applied as known at t.
* **Execution.** Trades fill at the close ``lag >= 1`` sessions after the decision. ``lag = 0`` (a fill at the close
  that produced the signal) is refused. A target that is not traded on the execution day is not bought.
* **Delistings.** Outcomes use ``total_returns`` with ``DelistingPolicy.require()``: a delisted holding earns its
  delisting return, then cash. A missing delisting return raises; it is never silently dropped.
* **Costs.** ``EquityCostModel.turnover_cost`` applies to the change from the *drifted* weights to the targets, with
  ADV and volatility estimated from data known at the decision. The caller must supply the cost model with a stated
  reference; there is no default.
* **Out of sample.**
  - ``is_end`` is a date fixed in the configuration. Each sleeve's variant (its lookback) is chosen on net Sharpe
    over the decision days up to ``is_end`` only.
  - The out-of-sample block starts after ``is_end``, and only the chosen variant is reported there.
  - Every variant tried is listed, so the selection is visible and can be counted.
  - Results up to ``is_end`` are identical whatever happens after it (tested by truncation).
* **Combined.** The combined portfolio is one costed book holding each track's chosen names at half the capital
  each. It is not an uncosted blend of two return series. Its components stay counted in their own tracks
  (``manhattan.tracks``).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from datetime import date

import numpy as np

from .costs import EquityCostModel
from .errors import EquityDataError
from .prices import DelistingPolicy
from .risk import drawdown
from .sectors import EQUITY_TRACKS, NON_TECHNOLOGY_TRACK, TECHNOLOGY_TRACK, sector_of
from .universe import UniverseBuilder, track_rules

LABEL = {"evidence_class": "synthetic_infrastructure", "evidential_weight": 0, "confirmatory": False,
         "scientifically_validated": False,
         "note": "synthetic data: describes the generator and the pipeline, never a market"}


@dataclass(frozen=True)
class CompareConfig:
    is_end: date                                 # last decision day of the in-sample block (fixed in advance)
    lookbacks: tuple = (63, 126, 252)            # the declared variant grid; every variant is reported
    skip: int = 21
    rebalance_every: int = 21
    lag: int = 1                                 # sessions from the decision close to the execution close
    warmup: int = 260
    top_fraction: float = 1 / 3
    capital: float = 1e7
    est_sessions: int = 63                       # ADV and volatility estimation window (known at the decision)

    def __post_init__(self):
        if isinstance(self.lag, bool) or not isinstance(self.lag, int) or self.lag < 1:
            raise EquityDataError("lag must be a whole number of sessions, at least 1: a fill at the close that "
                                  "produced the signal is not achievable")
        if not self.lookbacks or any(not isinstance(x, int) or x <= self.skip for x in self.lookbacks):
            raise EquityDataError("lookbacks are whole numbers of sessions, each longer than skip")
        if self.warmup < max(self.lookbacks) + 1:
            raise EquityDataError("warmup must cover the longest lookback")
        if not 0 < self.top_fraction <= 1:
            raise EquityDataError("top_fraction is in (0, 1]")


@dataclass
class Sleeve:
    name: str
    tracks: tuple
    lookbacks: dict
    days: list = field(default_factory=list)
    gross: list = field(default_factory=list)
    costs: list = field(default_factory=list)
    turnover: list = field(default_factory=list)
    decisions: list = field(default_factory=list)    # (decision day, execution day, n members, n held)
    unfilled: list = field(default_factory=list)

    @property
    def net(self) -> np.ndarray:
        return np.asarray(self.gross) - np.asarray(self.costs)


class _Outcomes:
    """Daily total returns (outcomes, never signals), delisting returns included, known at ``end`` (default: the
    end of the record). With an ``end``, nothing dated after it is read: a delisting return not yet known then
    raises (survivorship), it is never assumed."""

    def __init__(self, world, end: date | None = None):
        self.w = world
        self.end = end
        self._cache: dict = {}

    def get(self, sid: str) -> dict:
        if sid not in self._cache:
            d0 = self.w.days[0]
            d1 = self.w.days[-1] if self.end is None else max(d for d in self.w.days if d <= self.end)
            rs = self.w.prices.total_returns(sid, d0, d1, as_of=d1, delisting=DelistingPolicy.require())
            self._cache[sid] = dict(zip(rs.days, rs.returns))
        return self._cache[sid]


def _signal(world, sid, days, i, lookback, skip):
    d = days[i]
    rs = world.prices.total_returns(sid, days[i - lookback], days[i - skip], as_of=d)
    need = 0.9 * (lookback - skip)
    if rs.returns.size < need:
        return None
    return float(np.prod(1.0 + rs.returns) - 1.0)


def _estimates(world, sid, days, i, n):
    """(median dollar volume, daily return volatility) over the ``n`` sessions to decision day ``days[i]``, both
    known at its close."""
    d = days[i]
    dv = world.prices.dollar_volume(sid, d, n)
    rs = world.prices.total_returns(sid, days[max(0, i - n)], d, as_of=d)
    vol = float(np.std(rs.returns, ddof=1)) if rs.returns.size > 2 else float("nan")
    return (float(np.median(dv)) if dv.size else float("nan")), vol


def _require_synthetic(world) -> None:
    """Dormant (issue #102 review): this module runs a portfolio rule and selects a variant, so it runs only on a
    synthetic world. A real-data experiment goes through ``registration.admit`` and its pre-registration, and even
    then is refused while ``registration.EXECUTION_ON_REAL_DATA`` is False."""
    from .synthetic import is_synthetic
    if not is_synthetic(world):
        raise EquityDataError("dormant: portfolio rules run only on a synthetic world; any other world needs a "
                              "pre-registered experiment (registration.admit), and real-data execution is off")


def _check_sleeve_args(world, cost_model, lookbacks) -> None:
    _require_synthetic(world)
    if not isinstance(cost_model, EquityCostModel):
        raise EquityDataError("a cost model with a stated reference is required (no default)")
    for t in lookbacks:
        if t not in EQUITY_TRACKS:
            raise EquityDataError(f"{t!r} is not an equity research track")


def run_sleeve(world, cfg: CompareConfig, cost_model: EquityCostModel, lookbacks: dict, *, name: str,
               end: date | None = None) -> Sleeve:
    """One costed book over the **selection window only**. ``lookbacks``: {track: lookback}. With one track, a
    track-only sleeve; with both, the combined book, in which each track has an equal share of capital. ``end``:
    ignore every session after it (truncation); it is required and must be on or before ``cfg.is_end``.

    A window past ``cfg.is_end`` is a holdout: it is read once, for the locked variant of an admitted experiment,
    through ``registration.run_holdout`` (which records the look in the persistent ledger first), never directly
    here (S17 C1)."""
    _check_sleeve_args(world, cost_model, lookbacks)
    if end is None or end > cfg.is_end:
        raise EquityDataError("run_sleeve reads the selection window only (end on or before cfg.is_end): a holdout "
                              "is read once, through registration.run_holdout")
    return _sleeve(world, cfg, cost_model, lookbacks, name=name, end=end)


def _sleeve(world, cfg: CompareConfig, cost_model: EquityCostModel, lookbacks: dict, *, name: str,
            end: date | None = None) -> Sleeve:
    """``run_sleeve`` without the selection-window check: ``compare`` (the declared infrastructure report) and the
    registration gate's holdout only (a static test pins its callers)."""
    _check_sleeve_args(world, cost_model, lookbacks)
    days = list(world.days) if end is None else [d for d in world.days if d <= end]
    n = len(days)
    builders = {t: UniverseBuilder(world.master, world.prices, world.classes, track_rules(t)) for t in lookbacks}
    out = _Outcomes(world, end)
    share = 1.0 / len(lookbacks)
    sl = Sleeve(name, tuple(lookbacks), dict(lookbacks))
    held: dict = {}                    # current (drifted) weights, fraction of capital
    rebal = list(range(cfg.warmup, n - cfg.lag - 1, cfg.rebalance_every))
    exec_at = {i + cfg.lag: i for i in rebal}
    first = rebal[0] + cfg.lag if rebal else n
    for e in range(first, n):
        day = days[e]
        cost = turn = 0.0
        if e in exec_at:
            i = exec_at[e]
            d = days[i]
            target: dict = {}
            n_members = 0
            for t, lb in lookbacks.items():
                snap = builders[t].snapshot(d)
                sig = {}
                for sid in snap.members:
                    s = _signal(world, sid, days, i, lb, cfg.skip)
                    if s is not None:
                        sig[sid] = s
                n_members += len(snap.members)
                ranked = sorted(sig, key=lambda s: (-sig[s], s))
                k = max(1, math.ceil(cfg.top_fraction * len(ranked))) if ranked else 0
                chosen = ranked[:k]
                fill = [s for s in chosen if world.prices.last_traded(s, day) == day]
                sl.unfilled += [(d, s) for s in chosen if s not in fill]
                for s in fill:
                    target[s] = target.get(s, 0.0) + share / len(fill)
            before = {s: w for s, w in held.items() if world.prices.last_traded(s, day) == day}   # delisted = cash
            adv, vol = {}, {}
            for s in set(before) | set(target):
                adv[s], vol[s] = _estimates(world, s, days, i, cfg.est_sessions)
                if not (adv[s] > 0 and np.isfinite(vol[s])):
                    raise EquityDataError(f"{s}: no ADV or volatility known at {d}")
            cost = cost_model.turnover_cost(before, target, cfg.capital, adv, vol)
            turn = sum(abs(target.get(s, 0.0) - before.get(s, 0.0)) for s in set(before) | set(target))
            held = dict(target)
            sl.decisions.append((d, day, n_members, len(target)))
            sl.days.append(day)
            sl.gross.append(0.0)              # the fill is at this close: holdings earn from the next session
            sl.costs.append(cost)
            sl.turnover.append(turn)
            continue
        r = {s: out.get(s).get(day, 0.0) for s in held}
        g = sum(w * r[s] for s, w in held.items())
        cash = 1.0 - sum(held.values())
        tot = sum(w * (1 + r[s]) for s, w in held.items()) + cash
        held = {s: w * (1 + r[s]) / tot for s, w in held.items()} if tot > 0 else {}
        sl.days.append(day)
        sl.gross.append(g)
        sl.costs.append(cost)
        sl.turnover.append(turn)
    return sl


def metrics(r) -> dict:
    r = np.asarray(r, float)
    if r.size < 2:
        return {"days": int(r.size)}
    sd = float(np.std(r, ddof=1))
    dd = drawdown(r)
    return {"days": int(r.size), "ann_return": float(np.mean(r)) * 252, "ann_vol": sd * math.sqrt(252),
            "sharpe": float(np.mean(r)) / sd * math.sqrt(252) if sd > 0 else 0.0,
            "max_drawdown": dd["max_drawdown"], "longest_underwater": dd["longest_underwater"]}


def _split(sl: Sleeve, is_end: date):
    days = np.array(sl.days, dtype=object)
    k = np.array([d <= is_end for d in days])
    net, cost, turn = sl.net, np.asarray(sl.costs), np.asarray(sl.turnover)
    part = lambda m: {**metrics(net[m]), "cost_drag": float(cost[m].sum()) * 252 / max(int(m.sum()), 1),  # noqa
                      "ann_turnover": float(turn[m].sum()) * 252 / max(int(m.sum()), 1)}
    return part(k), part(~k), net[k], net[~k], days[~k]


def compare(world, cfg: CompareConfig, cost_model: EquityCostModel, *, end: date | None = None) -> dict:
    """Run every declared variant of each track-only sleeve, choose each sleeve's lookback on in-sample net Sharpe,
    then report out of sample: technology only, non-technology only and the combined costed book."""
    tracks = (TECHNOLOGY_TRACK, NON_TECHNOLOGY_TRACK)
    variants, chosen, oos_series = {}, {}, {}
    for t in tracks:
        rows = []
        for lb in cfg.lookbacks:
            sl = _sleeve(world, cfg, cost_model, {t: lb}, name=f"{t}:{lb}", end=end)
            ins, oos, _, oos_net, oos_days = _split(sl, cfg.is_end)
            rows.append({"lookback": lb, "in_sample": ins, "_oos": oos, "_oos_net": oos_net, "_oos_days": oos_days,
                         "decisions": len(sl.decisions), "unfilled": len(sl.unfilled)})
        best = max(rows, key=lambda x: (x["in_sample"].get("sharpe", float("-inf")), -x["lookback"]))
        chosen[t] = best["lookback"]
        oos_series[t] = (best["_oos_days"], best["_oos_net"])
        variants[t] = {"variants_tried": len(rows), "grid": list(cfg.lookbacks), "chosen_lookback": best["lookback"],
                       "selection_rule": "max in-sample net Sharpe; ties -> shorter lookback",
                       "in_sample_by_variant": {r["lookback"]: r["in_sample"] for r in rows},
                       "out_of_sample_chosen": best["_oos"], "decisions": best["decisions"],
                       "unfilled_targets": best["unfilled"]}
    # benchmark: the costed equal-weight book of the same track universe (every member, no signal). Long-only sleeves
    # earn the market; only the excess over their own universe speaks to the signal
    bench_cfg = replace(cfg, top_fraction=1.0)
    for t in tracks:
        b = _sleeve(world, bench_cfg, cost_model, {t: cfg.lookbacks[0]}, name=f"{t}:equal_weight", end=end)
        bins, boos, _, b_oos, b_days = _split(b, cfg.is_end)
        days_t, net_t = oos_series[t]
        if list(b_days) != list(days_t):
            raise EquityDataError(f"{t}: benchmark and sleeve out-of-sample days differ")
        variants[t]["benchmark_equal_weight"] = {"in_sample": bins, "out_of_sample": boos}
        variants[t]["out_of_sample_excess_over_benchmark"] = metrics(net_t - b_oos)
    comb = _sleeve(world, cfg, cost_model, dict(chosen), name="combined_equities", end=end)
    cins, coos, _, comb_oos, comb_days = _split(comb, cfg.is_end)
    (dt, nt), (dn, nn) = oos_series[TECHNOLOGY_TRACK], oos_series[NON_TECHNOLOGY_TRACK]
    if list(dt) != list(dn):
        raise EquityDataError("the two track sleeves' out-of-sample days differ: their returns cannot be compared")
    corr = float(np.corrcoef(nt, nn)[0, 1]) if len(nt) > 2 and np.std(nt) > 0 and np.std(nn) > 0 else None
    return {**LABEL, "config": {**asdict(cfg), "is_end": cfg.is_end.isoformat()},
            "cost_model": {"name": cost_model.name, "reference": cost_model.reference},
            "execution": {"lag_sessions": cfg.lag, "fill": "close of decision day + lag", "same_close": False},
            "tracks": variants,
            "combined_equities": {"lookbacks": dict(chosen), "capital_split": "equal per track",
                                  "in_sample": cins, "out_of_sample": coos,
                                  "components_counted_in": list(tracks)},
            "out_of_sample_correlation_tech_vs_nontech": corr,
            "out_of_sample_days": int(len(comb_days))}


def sector_volatility(world, start: date, end: date) -> dict:
    """Annualised volatility, measured from total returns, by sector and by track. Each day's return is assigned to
    the security's category **as known that day**. Reports the mean single-stock volatility and the volatility of the
    equal-weight sector average. Descriptive; nothing is assumed about which sector is calmer."""
    _require_synthetic(world)
    days = [d for d in world.days if start <= d <= end]
    by_sector: dict = {}
    single: dict = {}
    for sid in _all_securities(world):
        sec = world.master.security(sid)
        try:
            rs = world.prices.total_returns(sid, start, end, as_of=end, delisting=DelistingPolicy.require())
        except EquityDataError:
            continue
        for d, x in zip(rs.days, rs.returns):
            sec_name = sector_of(world.classes.category(sec.company_id, d))
            if sec_name is None or sec.security_type not in ("common", "adr", "reit"):
                continue
            by_sector.setdefault(sec_name, {}).setdefault(d, []).append(float(x))
            single.setdefault((sec_name, sid), []).append(float(x))
    out = {}
    for s, per_day in by_sector.items():
        idx = np.array([np.mean(per_day[d]) for d in days if d in per_day])
        stocks = [np.std(v, ddof=1) * math.sqrt(252) for (ss, _), v in single.items() if ss == s and len(v) > 20]
        out[s] = {"track": "technology_equities" if s == "technology" else "non_technology_equities",
                  "sector_index_ann_vol": float(np.std(idx, ddof=1) * math.sqrt(252)) if idx.size > 2 else None,
                  "mean_single_stock_ann_vol": float(np.mean(stocks)) if stocks else None,
                  "securities": len(stocks)}
    return {**LABEL, "by_sector": out}


def _all_securities(world):
    seen = set()
    for d in world.days:
        for sid in world.master.listed(d):
            if sid not in seen:
                seen.add(sid)
                yield sid

