"""What a result may be called: the minimum execution requirements and the presentation guard.

**Three labels**, weakest first. No label in this package says "realistic", "calibrated" or "evidence": that needs
costs measured from recorded quotes or fills (Protocol v3.1 section 8: paper costs measured over at least three
months; section 10: median recorded half-spreads and fees), which nothing here has.

| label | meaning | how a result gets it |
|---|---|---|
| ``throughput_only`` | pipeline and throughput tests only: same-close timing is wrong, and its bias can have **either sign** (it flatters a fade of yesterday's move and penalises a trend when returns reverse at lag 1; the fixtures show both), so it is not even a bound | ``lag = 0`` (same-close fill), whatever else holds |
| ``screening_net`` | delayed and net of costs, but below the exploratory minimum | ``lag >= 1`` and any requirement R2-R8 unmet (for example proportional costs, or synthetic or scenario costs) |
| ``exploratory_grade`` | meets the minimum for historical exploratory research | every requirement R1-R8 met; R9 checked when it is presented |

``present_trading_return`` is the **only** function that returns a net-return figure without a qualifying prefix,
and it refuses anything below ``exploratory_grade`` or without the R9 sensitivity rows. ``summary()`` on a result
is always allowed, and at lag 0 it renames every statistic ``same_close_optimistic_*``.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import OptimisticExecutionError
from .provenance import weakest

LABELS = ("throughput_only", "screening_net", "exploratory_grade")
REQUIRED_COMPONENTS = ("commission", "exchange_fee", "half_spread_ticks", "slippage_ticks", "impact_coefficient",
                       "max_participation")
STALE_WARN = 0.05

REQUIREMENTS = (
    ("R1", "Execution at least one trading day after the close whose data the decision used (Protocol v3.1 "
           "section 2.1; PR #85 lag >= 1). Same-close fills are a throughput convention only."),
    ("R2", "Fills and marks at tradable settlements of the contract month actually held; P&L from same-contract "
           "changes; no back-adjusted, ratio-adjusted or spliced series is traded or marked."),
    ("R3", "Whole contracts sized from the multiplier, price and FX known at the decision; fills rounded to the "
           "tick grid against the trader."),
    ("R4", "Every cost component (commission, exchange fee, half-spread, slippage, impact coefficient, "
           "participation cap) stated with a non-scenario source and a reference; a 'known' source counts only "
           "inside the dates it is known for (otherwise it is 'extrapolated', an estimate)."),
    ("R5", "A participation cap on every order, sized with the liquidity estimate known at the decision "
           "(carried orders and rolls: the previous close's)."),
    ("R6", "Missing settlements stop the run or are held with every stale mark counted and reported; a missing "
           "FX rate or liquidity estimate always stops the run."),
    ("R7", "Rolls cost both legs (spread, slippage, impact, rounding, fees on each), and a roll that cannot "
           "complete fails closed rather than lapsing or doubling the position."),
    ("R8", "Roots quoted outside the base currency are converted at the day's fix, with an FX conversion cost "
           "term stated (zero allowed, with its source)."),
    ("R9", "A sensitivity is attached to any presented figure: costs x0, x1 and x2, and lag + 1, on the same "
           "decisions."),
)


@dataclass(frozen=True)
class Assessment:
    label: str
    cost_class: str
    met: tuple
    unmet: tuple
    warnings: tuple


def assess(result) -> Assessment:
    """Label a result of ``adapter.execute`` (contract tier) or ``screening.ScreeningResult`` (proportional tier)."""
    from .adapter import ExecutionResult
    met, unmet, warn = [], [], []

    def check(rid: str, ok: bool, why: str = ""):
        (met if ok else unmet).append(rid if ok else f"{rid}: {why}")

    lag = result.lag
    check("R1", lag >= 1, "same-close fill (lag 0)")
    contract_tier = isinstance(result, ExecutionResult)
    if not contract_tier:
        for rid in ("R2", "R3", "R5", "R6", "R7", "R8"):
            check(rid, False, "proportional-cost tier: no contracts, settlements, liquidity cap or rolls")
        sources = getattr(result, "cost_sources", {})
    else:
        check("R2", True)
        check("R3", True)
        check("R5", True)
        check("R6", True)
        check("R7", True)
        check("R8", not result.fx_conversion_unmodelled,
              f"no fx_conversion_bps term for {', '.join(result.fx_conversion_unmodelled)}")
        sources = result.cost_sources
        days = result.positions.shape[0]
        if days and result.stale_marks and len(result.stale_marks) / (days * len(result.roots)) > STALE_WARN:
            warn.append(f"stale marks on {len(result.stale_marks)} root-days (more than {STALE_WARN:.0%})")
        if result.stale_sizing:
            warn.append(f"{len(result.stale_sizing)} decisions sized from a stale price")
        if result.unexecuted:
            warn.append(f"{len(result.unexecuted)} decisions fell after the last day and were not executed")
        if result.unfilled:
            warn.append(f"{len(result.unfilled)} orders not filled in full (liquidity or missing settlement)")
    classes, missing, extrap = [], [], []
    for root, comps in sources.items():
        for c in REQUIRED_COMPONENTS:
            if c not in comps:
                missing.append(f"{root}.{c}")
        for c, s in comps.items():
            classes.append(s.cls)
            if s.kind == "extrapolated":
                extrap.append(f"{root}.{c}")
    cost_class = weakest(classes) if classes else "scenario"
    check("R4", not missing and cost_class != "scenario",
          f"missing {missing}" if missing else f"weakest cost source is '{cost_class}'")
    if extrap:
        warn.append(f"known costs used outside their dates (extrapolated): {', '.join(sorted(extrap))}")
    if result.data_kind == "synthetic":
        warn.append("synthetic data: every figure describes the generator, not a market")
    if lag == 0:
        label = "throughput_only"
    elif unmet:
        label = "screening_net"
    else:
        label = "exploratory_grade"
    return Assessment(label, cost_class, tuple(met), tuple(unmet), tuple(warn))


def require_sensitivity(rows, lag: int) -> None:
    """R9: the rows of ``sensitivity.grid`` must include costs x0, x1, x2 at ``lag`` and x1 at ``lag + 1``."""
    have = {(r["lag"], float(r["cost_multiple"])) for r in rows}
    need = {(lag, 0.0), (lag, 1.0), (lag, 2.0), (lag + 1, 1.0)}
    if not need <= have:
        raise OptimisticExecutionError(f"R9: the sensitivity lacks {sorted(need - have)} (lag, cost multiple)")


def present_trading_return(result, sensitivity_rows) -> dict:
    """The figure a research note may quote as a net return estimate under modelled costs. Refuses below
    ``exploratory_grade`` and without the R9 rows. Even then it is exploratory, not evidence."""
    a = assess(result)
    if a.label != "exploratory_grade":
        raise OptimisticExecutionError(
            f"this result is '{a.label}', not 'exploratory_grade', and may not be presented as a trading return; "
            f"unmet: {list(a.unmet)}")
    if result.data_kind != "historical":
        raise OptimisticExecutionError(f"data_kind is '{result.data_kind}': a synthetic panel's return describes "
                                       "its generator and is never presented as a trading return")
    require_sensitivity(sensitivity_rows, result.lag)
    st = result.stats()
    return {"label": a.label, "net_of_modelled_costs": True, "realistic_return_claims": False, "evidence": False,
            "cost_class": a.cost_class, "lag": result.lag, "data_kind": result.data_kind,
            "ann_net_return": st["ann_net_return"], "sharpe": st["sharpe"], "ann_cost_drag": st["ann_cost_drag"],
            "sensitivity": list(sensitivity_rows), "warnings": list(a.warnings), "result_hash": result.result_hash()}
