"""Brier scores and P&L for resolved decisions and forecasts.

Brier score of a probability p (0-1) for an event that happened (1) or not (0) is (p - o)^2;
0 is perfect, 0.25 is a coin flip, 1 is the worst. A decision's event is "my view was
right". A forecast's event is "the question resolved yes". The market's and Claude's
scores are computed on exactly the same resolved forecasts, so they are comparable.

Decision P&L in % of account, when it can be computed: the size is the % of account lost
at the stop, so P&L = size x (exit - entry) x direction / |entry - stop|, where the direction
is +1 when the stop is below the entry level (the position loses when the level falls) and
-1 when it is above. That works for prices, yields and spreads alike. It needs a numeric
entry level, stop and exit price; otherwise a P&L entered at resolution is used, else none.
"""
from __future__ import annotations

from .schema import parse_number, parse_probability, stop_level


def brier(p_pct, outcome01) -> float | None:
    p = parse_probability(p_pct)
    if p is None or outcome01 is None:
        return None
    return round((p / 100.0 - outcome01) ** 2, 4)


def decision_outcome01(d: dict) -> int | None:
    o = (d.get("outcome") or "").strip().lower()
    if o == "right":
        return 1
    if o == "wrong":
        return 0
    return None


def forecast_outcome01(f: dict) -> int | None:
    o = (f.get("outcome") or "").strip().lower()
    if o == "yes":
        return 1
    if o == "no":
        return 0
    return None


def decision_pnl_pct(d: dict) -> float | None:
    """P&L in % of account, see module docstring."""
    explicit = parse_number(d.get("pnl_pct"))
    if explicit is not None:
        return round(explicit, 3)
    if d.get("action") not in ("Buy", "Sell"):
        return None
    entry = parse_number(d.get("entry_level"))
    stop = stop_level(d.get("stop"))
    exit_ = parse_number(d.get("exit_price"))
    size = parse_number(d.get("size_pct"))
    if None in (entry, stop, exit_, size) or entry == stop:
        return None
    direction = 1.0 if entry > stop else -1.0
    return round(size * (exit_ - entry) * direction / abs(entry - stop), 3)


def pnl_at_level(d: dict, level: float) -> float | None:
    """P&L in % of account if the position were closed at ``level`` (a live mark or an exit),
    from the entry level, stop and size; None when any of them is missing."""
    if d.get("action") not in ("Buy", "Sell") or level is None:
        return None
    entry = parse_number(d.get("entry_level"))
    stop = stop_level(d.get("stop"))
    size = parse_number(d.get("size_pct"))
    if None in (entry, stop, size) or entry == stop:
        return None
    direction = 1.0 if entry > stop else -1.0
    return round(size * (float(level) - entry) * direction / abs(entry - stop), 3)


def score_decision(d: dict) -> dict:
    o = decision_outcome01(d)
    return {
        "outcome01": o,
        "brier": brier(d.get("probability"), o),
        "brier_claude": brier(d.get("claude_probability"), o) if d.get("claude_probability") else None,
        "pnl_pct": decision_pnl_pct(d) if d.get("status") == "resolved" else None,
    }


def score_forecast(f: dict) -> dict:
    o = forecast_outcome01(f)
    return {
        "outcome01": o,
        "brier_me": brier(f.get("my_prob"), o),
        "brier_market": brier(f.get("market_prob"), o),
        "brier_claude": brier(f.get("claude_prob"), o) if f.get("claude_prob") else None,
    }


def cumulative(values: list[float | None]) -> dict:
    """Mean Brier over the non-null values, with the count, and the running mean."""
    xs = [v for v in values if v is not None]
    running, acc = [], 0.0
    for v in values:
        if v is None:
            running.append(None)
            continue
        acc += v
        running.append(round(acc / len([r for r in running if r is not None] + [v]), 4))
    return {"n": len(xs), "mean": round(sum(xs) / len(xs), 4) if xs else None, "running": running}


def calibration_bins(pairs: list[tuple[float, int]], edges=(0, 20, 40, 60, 80, 101)) -> list[dict]:
    """Bin (probability %, outcome) pairs: mean forecast vs observed frequency per bin."""
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        inb = [(p, o) for p, o in pairs if lo <= p < hi]
        out.append({
            "bin": f"{lo}-{min(hi - 1, 100)}",
            "n": len(inb),
            "mean_forecast": round(sum(p for p, _ in inb) / len(inb), 1) if inb else None,
            "observed": round(100 * sum(o for _, o in inb) / len(inb), 1) if inb else None,
        })
    return out
