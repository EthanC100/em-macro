"""Evidence-aware variant limits (criteria O-23 to O-26).

Every parameter a grid varies must say **why it varies** (an economic reason) and **what range the mechanism
implies**. In the hypothesis spec:

    "grid_justification": {
        "lookback": {"reason": "<the economics>", "mechanism_range": [20, 120]},
        "venue":    {"reason": "<the economics>", "mechanism_values": ["a", "b"]}
    }

A parameter with a single value is not varied and needs nothing. The mechanical checks here (missing reason, a
reason that is only a generic phrase, a value outside the stated range) are the critic's rejections of an
unjustified dimension; whether the economics is good is the critic model's opinion, never a block.

The **budget**: above ``DEFAULT_BUDGET`` raw variants per hypothesis, a hypothesis must carry a recorded
``budget_justification``. Every variant is counted in the batch counts whether or not it is above the budget.

The **report** per grid: the raw count; an effective count (Li and Ji, from ``manhattan.stats.meff``, on the
correlation of the variants' returns over exploration-role data; the raw count when no data are given); and the
expected loss of power of a max-type test from searching the grid. The loss is an **approximation**: a single test
at level ``alpha`` against a test whose critical value is the Šidák value for ``M_eff`` independent tests, for a
true edge of ``theta`` (annualised Sharpe ratio) over ``years`` of data, so the standardised effect is
``theta * sqrt(years)``. Hansen's SPA test, which accounts for the correlation directly and recentres poor variants,
loses less than this when variants are correlated, so the figure is an upper bound on the price of the search under
those assumptions, not a property of SPA itself.
"""
from __future__ import annotations

import math
import re

import numpy as np
from scipy.stats import norm

from manhattan.stats import meff

DEFAULT_BUDGET = 16                    # raw variants per hypothesis; an ops default, Ethan's to change
THETA_MIN = 0.25                       # Protocol v3 Appendix B
MIN_REASON_CHARS = 40
GENERIC = re.compile(r"^\s*(for\s+)?(robustness|robust|sensitivity|standard|common|typical|to be safe|to check|"
                     r"various|different values|explore|exploration|tuning|optimi[sz]ation|grid search|"
                     r"literature|commonly used|default)[\s.,;:!-]*$", re.I)


class JustificationError(ValueError):
    pass


def _num(v) -> float | None:
    """A number, also in the canonical form's decimal-string spelling; None for anything else."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            x = float(v)
        except ValueError:
            return None
        return x if math.isfinite(x) else None
    return None


def varied(h: dict) -> dict:
    return {k: v for k, v in (h.get("grid") or {}).items() if isinstance(v, (list, tuple)) and len(v) > 1}


def check_justification(h: dict) -> list[dict]:
    """Findings for each varied parameter: ``{param, problem}``. Empty when every dimension is justified."""
    out = []
    just = h.get("grid_justification") or {}
    if not isinstance(just, dict):
        return [{"param": "*", "problem": "grid_justification must map each varied parameter to its reason and range"}]
    for name, values in varied(h).items():
        j = just.get(name)
        if not isinstance(j, dict):
            out.append({"param": name, "problem": "no justification: say why it varies and what range the mechanism implies"})
            continue
        reason = j.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON_CHARS:
            out.append({"param": name, "problem": f"the reason is missing or shorter than {MIN_REASON_CHARS} characters"})
        elif GENERIC.match(reason.strip()):
            out.append({"param": name, "problem": "the reason is a generic phrase, not an economic reason"})
        rng, vals = j.get("mechanism_range"), j.get("mechanism_values")
        if rng is None and vals is None:
            out.append({"param": name, "problem": "no mechanism_range or mechanism_values"})
        elif rng is not None:
            try:
                lo, hi = float(rng[0]), float(rng[1])
                if not lo <= hi:
                    raise ValueError
            except (TypeError, ValueError, IndexError):
                out.append({"param": name, "problem": "mechanism_range must be [low, high]"})
                continue
            bad = [v for v in values if _num(v) is None or not lo <= _num(v) <= hi]
            if bad:
                out.append({"param": name, "problem": f"{len(bad)} value(s) outside the mechanism range"})
        else:
            if not isinstance(vals, list) or any(v not in vals for v in values):
                out.append({"param": name, "problem": "a value is not among mechanism_values"})
    for name in set(just) - set(varied(h)):
        if name not in (h.get("grid") or {}):
            out.append({"param": name, "problem": "justification for a parameter that is not in the grid"})
    return out


def raw_count(h: dict) -> int:
    return math.prod(len(v) for v in (h.get("grid") or {}).values()) if h.get("grid") else 0


def budget_finding(h: dict, budget: int = DEFAULT_BUDGET) -> dict | None:
    n = raw_count(h)
    if n <= budget:
        return None
    j = h.get("budget_justification")
    if isinstance(j, str) and len(j.strip()) >= MIN_REASON_CHARS and not GENERIC.match(j.strip()):
        return {"over_budget": n - budget, "justified": True}
    return {"over_budget": n - budget, "justified": False,
            "problem": f"{n} variants is above the budget of {budget}: a budget_justification is required"}


def effective_count(returns: np.ndarray | None, raw: int) -> float:
    """Li-Ji effective number of the variants (columns of ``returns``); the raw count without data."""
    if returns is None:
        return float(raw)
    r = np.asarray(returns, dtype=float)
    if r.ndim != 2 or r.shape[1] < 2:
        return float(r.shape[1] if r.ndim == 2 else raw)
    keep = r.std(axis=0) > 0
    if keep.sum() < 2:
        return float(max(int(keep.sum()), 1))
    c = np.corrcoef(r[:, keep], rowvar=False)
    return float(min(max(meff.li_ji(c), 1.0), raw))


def power_loss(m_eff: float, *, theta: float = THETA_MIN, years: float = 5.0, alpha: float = 0.05) -> dict:
    """Approximate power of one test and of the search over ``m_eff`` (Šidák critical value), one-sided."""
    m = max(float(m_eff), 1.0)
    delta = theta * math.sqrt(years)
    c1 = norm.ppf(1 - alpha)
    cm = norm.ppf((1 - alpha) ** (1.0 / m))
    p1, pm = 1 - norm.cdf(c1 - delta), 1 - norm.cdf(cm - delta)
    return {"theta": theta, "years": years, "alpha": alpha, "m_eff": round(m, 3), "critical_single": round(float(c1), 4),
            "critical_search": round(float(cm), 4), "power_single": round(float(p1), 4),
            "power_search": round(float(pm), 4), "power_loss": round(float(p1 - pm), 4),
            "method": "approximation: single test vs Sidak critical value at M_eff (upper bound under the stated assumptions)"}


def grid_report(h: dict, returns: np.ndarray | None = None, *, years: float = 5.0, budget: int = DEFAULT_BUDGET) -> dict:
    """What the compiler reports for one hypothesis's grid."""
    raw = raw_count(h)
    m = effective_count(returns, raw)
    return {"raw_variants": raw, "varied_parameters": sorted(varied(h)), "effective_variants": round(m, 3),
            "effective_basis": "li_ji_exploration_returns" if returns is not None else "raw_count_no_data",
            "budget": budget, "over_budget": budget_finding(h, budget),
            "power": power_loss(m, years=years), "justification_findings": check_justification(h)}
