"""Exposure reports for the two kinds of technology-equity book, kept apart.

``long_short_report`` (relative value) and ``directional_report`` (stock selection) describe a book of weights
(fractions of capital) at one date. They do not size, optimise or trade anything; the existing Manhattan engine
and any later portfolio layer own that (``integration.PortfolioSink``).

**Different tickers are not diversification.** ``effective_bets`` is the squared diversification ratio: ten
technology stocks driven by one factor are close to one bet, whatever their names. (Meucci's entropy of principal
portfolios was considered and not used: with nearly equal eigenvalues its principal portfolios are arbitrary and the
measure is unstable on sample covariances.)

**One factor, one count.** ``aggregate_factor_exposure`` adds the factor exposures of several books (for example
a directional technology book, a long/short book and a macro book) and reports which factor is carried by more
than one of them, so that the same rate or growth exposure is not counted as several independent sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import EquityDataError


def _w(weights: dict) -> tuple[tuple, np.ndarray]:
    ids = tuple(sorted(weights))
    w = np.array([weights[i] for i in ids], float)
    if not np.isfinite(w).all():
        raise EquityDataError("weights must be finite")
    return ids, w


def _need(ids, table: dict, what: str) -> np.ndarray:
    missing = [i for i in ids if i not in table]
    if missing:
        raise EquityDataError(f"{what} missing for {missing[:5]}: an unknown exposure is not a zero exposure")
    return np.array([table[i] for i in ids], float)


def effective_bets(weights: dict, cov: np.ndarray, cov_ids: tuple) -> float:
    """Effective number of independent bets: the squared diversification ratio
    ``(Σ |w_i| σ_i)² / (w' Σ w)`` (Choueifaty and Coignard 2008). It equals N for N equal, independent positions
    of equal volatility and approaches 1 when every position loads on one factor."""
    ids, w = _w(weights)
    idx = {s: j for j, s in enumerate(cov_ids)}
    if any(i not in idx for i in ids):
        raise EquityDataError("every position needs a row in the covariance matrix")
    sel = [idx[i] for i in ids]
    S = np.asarray(cov, float)[np.ix_(sel, sel)]
    var = float(w @ S @ w)
    if var <= 0:
        return 0.0
    return float((np.abs(w) @ np.sqrt(np.clip(np.diag(S), 0, None))) ** 2 / var)


def concentration(w: np.ndarray) -> dict:
    a = np.abs(w)
    g = a.sum()
    if g == 0:
        return {"max_name": 0.0, "hhi": 0.0, "names_effective": 0.0}
    s = a / g
    return {"max_name": float(a.max()), "hhi": float((s * s).sum()), "names_effective": float(1 / (s * s).sum())}


@dataclass
class ExposureReport:
    kind: str
    gross: float
    net: float
    beta: float
    industry: dict
    factors: dict
    concentration: dict
    liquidity_days_max: float
    extra: dict = field(default_factory=dict)


def _common(weights, betas, industries, factors, adv, capital, participation):
    ids, w = _w(weights)
    b = _need(ids, betas, "beta")
    ind = {}
    for i, x in zip(ids, w):
        if i not in industries:
            raise EquityDataError(f"industry missing for {i}")
        ind[industries[i]] = ind.get(industries[i], 0.0) + float(x)
    fac = {}
    for f, table in (factors or {}).items():
        fac[f] = float(w @ _need(ids, table, f"factor {f}"))
    a = _need(ids, adv, "ADV")
    if (a <= 0).any():
        raise EquityDataError("ADV must be positive")
    days = np.abs(w) * capital / (participation * a)
    return ids, w, float(w @ b), ind, fac, float(days.max()) if days.size else 0.0


def long_short_report(weights: dict, *, betas: dict, industries: dict, factors: dict | None, adv: dict,
                      capital: float, borrow_fees: dict, earnings_soon: dict | None = None,
                      days_to_cover: dict | None = None, corporate_action_pending: dict | None = None,
                      participation: float = 0.1, squeeze_days_to_cover: float = 10.0) -> ExposureReport:
    ids, w, beta, ind, fac, liq = _common(weights, betas, industries, factors, adv, capital, participation)
    shorts = [i for i, x in zip(ids, w) if x < 0]
    fee = 0.0
    for i in shorts:
        if i not in borrow_fees:
            raise EquityDataError(f"{i}: short position without a borrow fee (an omission is not a zero fee)")
        fee += -weights[i] * borrow_fees[i]
    es, dtc, cap = earnings_soon or {}, days_to_cover or {}, corporate_action_pending or {}
    extra = {"long": float(w[w > 0].sum()), "short": float(-w[w < 0].sum()),
             "borrow_cost_annual": float(fee),
             "earnings_event_gross": float(sum(abs(weights[i]) for i in ids if es.get(i))),
             "squeeze_risk_names": tuple(i for i in shorts if dtc.get(i, 0.0) >= squeeze_days_to_cover),
             "corporate_action_gross": float(sum(abs(weights[i]) for i in ids if cap.get(i)))}
    return ExposureReport("long_short", float(np.abs(w).sum()), float(w.sum()), beta, ind, fac, concentration(w),
                          liq, extra)


def directional_report(weights: dict, *, betas: dict, industries: dict, factors: dict | None, adv: dict,
                       capital: float, previous: dict | None = None, rate_sensitivity: dict | None = None,
                       participation: float = 0.1) -> ExposureReport:
    ids, w, beta, ind, fac, liq = _common(weights, betas, industries, factors, adv, capital, participation)
    if (w < 0).any():
        raise EquityDataError("a directional book here is long-only; use long_short_report for shorts")
    prev = previous or {}
    turnover = float(sum(abs(weights.get(i, 0.0) - prev.get(i, 0.0)) for i in set(weights) | set(prev)) / 2)
    extra = {"turnover_one_way": turnover,
             "technology_share": float(sum(v for k, v in ind.items() if k != "non_technology") / max(w.sum(), 1e-12))}
    if rate_sensitivity is not None:
        extra["rate_sensitivity"] = float(w @ _need(ids, rate_sensitivity, "rate sensitivity"))
    return ExposureReport("directional", float(w.sum()), float(w.sum()), beta, ind, fac, concentration(w), liq, extra)


def drawdown(returns: np.ndarray) -> dict:
    """Maximum drawdown and its length from a return series (description of a record, never a forecast)."""
    r = np.asarray(returns, float)
    wealth = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    dd = wealth / peak - 1
    return {"max_drawdown": float(dd.min()) if dd.size else 0.0,
            "longest_underwater": int(max((len(s) for s in "".join("1" if x < 0 else "0" for x in dd).split("0")),
                                          default=0))}


def aggregate_factor_exposure(reports: dict, *, threshold: float = 0.05) -> dict:
    """Sum each factor's exposure across books (``{book: ExposureReport}``) and list factors carried by more than
    one book above ``threshold`` (in absolute exposure): the same factor is one risk, not several."""
    total, carriers = {}, {}
    for name, rep in reports.items():
        for f, v in rep.factors.items():
            total[f] = total.get(f, 0.0) + v
            if abs(v) >= threshold:
                carriers.setdefault(f, []).append(name)
    return {"total": total, "shared": {f: tuple(sorted(b)) for f, b in carriers.items() if len(b) > 1}}
