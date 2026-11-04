"""The original study's surprise definition and the spec 4.10 pre-registered rule.

Pure functions, no I/O except `load_frozen_fit`, which reads the frozen coefficients
from results/fit/frozen_params.json (read-only; never re-estimated here).

Definitions (docs/elections/ORIGINAL_STUDY.md):
* margin           = share(a) - share(b), pp; a = final-poll leader, b = runner-up
* poll error       = actual margin - final poll margin
* surprise         = poll error * market_sign, market_sign = +1 if a is the
                     market-preferred side, -1 if b; + = market-preferred side beat its polls
* expected day-1   = const + slope * surprise   (abnormal % move of the local currency vs USD)

Rule (docs/research/algorithm_spec_2026-11.md section 4.10):
* entry at the close of the first full trading day after the result
* direction = sign(surprise): +1 = long the local currency against USD
* hold H = 5 trading days
* risk = min(0.5 * 0.25 * Kelly(p, b), 2%) of NAV, p = mean of Beta(9, 2)
* stop = 1.5 * sigma_daily * sqrt(H)

Observation only: `implied_position` returns what the rule WOULD do, so the paper trade can be scored
(trial T15 in trials.csv). Every logged position has size POSITION_SIZE = 0 and is labelled POSITION_LABEL;
nothing is traded. Continuation after day 1 is not established (docs/elections/ORIGINAL_STUDY.md section 7).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "results" / "fit" / "frozen_params.json"
FIT_SPEC = "signed poll surprise (pp, + = market-preferred beat polls)"

# Spec 4.10 constants, fixed here so every alert uses the same numbers.
HOLD_DAYS = 5
KELLY_MULT = 0.5 * 0.25         # "half of quarter-Kelly"
RISK_CAP = 0.02                 # 2% of NAV at risk
STOP_K = 1.5
PRIOR_WINS, PRIOR_LOSSES = 8, 1  # 8 of 9 out-of-sample day-1 signs right
PAYOFF_B = 1.0                  # [A] Kelly odds b: not given in the spec; see docs/elections/README_RULE.md
EWMA_HALFLIFE = 60              # spec section 7: 60-day EWMA volatility

# Observation only: the rule's position is computed for scoring, but the size actually taken is zero.
POSITION_SIZE = 0.0
POSITION_LABEL = "paper, observation only"
TRIAL_ID = "T15"                # trials.csv row for the prospective test of the continuation rule
PASS_MIN_EVENTS = 15            # pass rule: at least 15 new scored elections, then
PASS_MIN_HIT = 0.65             #   post-day-1 move in the surprise's direction in >= 65% of events, and
PASS_MAX_P = 0.10               #   mean trade return > 0 with one-sided p < 0.10


@dataclass(frozen=True)
class Fit:
    const: float
    slope: float
    n: int
    p: float
    r2: float


def load_frozen_fit(path: Path = FROZEN) -> Fit:
    """Day-1 FX regression on the signed poll surprise, as frozen in 2021-sample fit."""
    with open(path) as f:
        params = json.load(f)
    for r in params["election_regressions"]:
        if r["asset"] == "FX" and r["h"] == 1 and r["spec"] == FIT_SPEC:
            return Fit(const=float(r["const"]), slope=float(r["b_surprise_mp_pp"]),
                       n=int(r["n"]), p=float(r["p_surprise_mp_pp"]), r2=float(r["r2"]))
    raise KeyError("day-1 FX election regression not found in frozen_params.json")


def _finite(*xs) -> bool:
    return all(x is not None and isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def margin(share_a: float, share_b: float) -> float:
    if not _finite(share_a, share_b):
        raise ValueError("shares must be finite numbers")
    return float(share_a) - float(share_b)


def market_sign_from_code(code: str | None) -> int | None:
    """'a' -> +1, 'b' -> -1, anything else (blank, 'ambiguous') -> None (excluded)."""
    if code is None:
        return None
    code = str(code).strip().lower()
    return {"a": 1, "b": -1}.get(code)


def surprise(actual_margin: float, poll_margin: float, market_sign: int | None) -> float | None:
    """Signed poll surprise in pp of margin. None when the sign is ambiguous (spec: excluded)."""
    if market_sign not in (1, -1):
        return None
    if not _finite(actual_margin, poll_margin):
        raise ValueError("margins must be finite numbers")
    return (float(actual_margin) - float(poll_margin)) * market_sign


def expected_day1_move(s: float, fit: Fit) -> float:
    """Predicted abnormal day-1 move, % of the local currency's USD value."""
    return fit.const + fit.slope * s


def beta_posterior_mean(wins: int = PRIOR_WINS, losses: int = PRIOR_LOSSES,
                        a0: float = 1.0, b0: float = 1.0) -> float:
    """Mean of Beta(a0 + wins, b0 + losses); uniform prior and 8/9 give Beta(9, 2) = 9/11."""
    return (a0 + wins) / (a0 + wins + b0 + losses)


def kelly_fraction(p: float, b: float) -> float:
    """Kelly fraction for a bet won with probability p paying b per unit risked; floored at 0."""
    if not (0.0 <= p <= 1.0):
        raise ValueError("p must be in [0, 1]")
    if b <= 0:
        raise ValueError("b must be positive")
    return max(0.0, p - (1.0 - p) / b)


def risk_fraction(p: float, b: float = PAYOFF_B, mult: float = KELLY_MULT, cap: float = RISK_CAP) -> float:
    """Fraction of NAV put at risk (lost if the stop is hit): min(mult * Kelly, cap)."""
    return min(mult * kelly_fraction(p, b), cap)


def stop_distance(sigma_daily_pct: float, hold: int = HOLD_DAYS, k: float = STOP_K) -> float:
    """Stop distance in % of the local currency's value: k * sigma_daily * sqrt(H)."""
    if not _finite(sigma_daily_pct) or sigma_daily_pct <= 0:
        raise ValueError("sigma_daily must be a positive number (in %)")
    return k * sigma_daily_pct * math.sqrt(hold)


@dataclass
class Position:
    direction: int            # +1 long local currency vs USD, -1 short, 0 no trade
    p: float
    b: float
    kelly: float
    risk_frac: float          # fraction of NAV lost at the stop
    stop_pct: float           # stop distance, % move against the position
    notional_frac: float      # notional as a fraction of NAV = risk_frac / (stop_pct / 100)
    hold_days: int

    def as_dict(self) -> dict:
        return asdict(self)


def implied_position(s: float | None, sigma_daily_pct: float, p: float | None = None,
                     b: float = PAYOFF_B) -> Position:
    """Position the pre-registered rule WOULD take for surprise `s` (pp).

    Used for scoring only: the tracker logs it with size POSITION_SIZE (0) and POSITION_LABEL."""
    p = beta_posterior_mean() if p is None else p
    stop = stop_distance(sigma_daily_pct)
    if s is None or s == 0:
        return Position(0, p, b, kelly_fraction(p, b), 0.0, stop, 0.0, HOLD_DAYS)
    rf = risk_fraction(p, b)
    return Position(direction=1 if s > 0 else -1, p=p, b=b, kelly=kelly_fraction(p, b),
                    risk_frac=rf, stop_pct=stop, notional_frac=rf / (stop / 100.0), hold_days=HOLD_DAYS)


def ewma_vol(returns_pct, halflife: int = EWMA_HALFLIFE) -> float:
    """EWMA standard deviation (zero mean) of daily % returns, most recent last."""
    r = [float(x) for x in returns_pct if x is not None and math.isfinite(float(x))]
    if len(r) < 20:
        raise ValueError("need at least 20 daily returns")
    lam = 0.5 ** (1.0 / halflife)
    w = [lam ** i for i in range(len(r))][::-1]          # weight 1 on the latest
    return math.sqrt(sum(wi * x * x for wi, x in zip(w, r)) / sum(w))
