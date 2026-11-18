"""Pair discovery inside an explicit information boundary, and spread diagnostics out of sample. Synthetic only.

    boundary = Boundary(formation_start, formation_end, evaluation_start, evaluation_end)
    disc = PairDiscovery(days, log_prices, boundary, rules, link=same_category)   # keeps formation data only
    cands = disc.candidates()                                                   # status "candidate", weight 0
    report = out_of_sample(cands[0], days, log_prices, rules)                   # stable or broken, and why

**The boundary is enforced by construction.** ``PairDiscovery`` copies only the observations dated inside
``[formation_start, formation_end]``; it never holds a later price. Evaluation data are passed separately to
``out_of_sample``, which uses the hedge ratio, spread mean and spread standard deviation **frozen at formation**.
At least ``rules.embargo_sessions`` sessions (one or more) must lie strictly between the two windows: both
``PairDiscovery`` and ``out_of_sample`` count them in ``days`` and refuse otherwise (S8 M2).

**Economic link first.** With ``rules.require_link`` (the default) a pair is considered only if ``link(a, b, t)``
returns a reason at ``t = formation_end`` (same technology category, a supplier/customer edge in the relationship
graph usable at ``t`` ...). Statistics alone over all pairs of a few hundred stocks is a multiple-testing machine.

**Correlation is not cointegration, and cointegration is not profit.** The filters are, in order: return
correlation; the Engle–Granger test in **both** directions (the larger p-value is kept); a mean-reversion half-life
within bounds; and stability across ``n_subperiods`` sub-windows of the formation window (hedge-ratio drift and a
per-window ADF test of the full-window spread). Before any of them, a pair with either leg missing on more than
``max_missing_frac`` of sessions or for more than ``max_gap_sessions`` in a row is ``insufficient_data``.
Passing them makes a pair a *candidate*.

``out_of_sample`` is a **retrospective** diagnostic (S8 M3): after the evaluation window has ended it classifies the
relationship over that window as stable or broken — a non-stationary spread, a variance blow-up, a shift of the
spread's mean (also per segment), a re-estimated hedge ratio that has moved, a leg missing, interrupted or no longer
trading. It uses the whole window, so it is never a signal inside it. These are diagnostics of a candidate filter
whose parameters (``PairRules``) must be frozen in a hypothesis spec before any designated evaluation; they are not
Manhattan decision rules and none of them is a test of profitability. Their synthetic hit rates (tests) describe the
code on one generator, not markets.

Hedge ratios: ``ols_hedge`` (static), ``rolling_hedge`` (estimated on the ``window`` sessions strictly before each
day), ``beta_neutral_hedge`` (the ratio that makes the spread's market beta zero) and ``residual_spread`` (spread
of market- or factor-model residuals, with loadings estimated on the formation window).
"""
from __future__ import annotations

import hashlib
import itertools
import warnings
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .errors import BorrowError, EquityDataError, TemporalError


@dataclass(frozen=True)
class Boundary:
    formation_start: date
    formation_end: date
    evaluation_start: date
    evaluation_end: date

    def __post_init__(self):
        if not self.formation_start < self.formation_end < self.evaluation_start <= self.evaluation_end:
            raise TemporalError("a boundary needs formation_start < formation_end < evaluation_start <= "
                                "evaluation_end (estimation precedes evaluation, with an embargo)")


@dataclass(frozen=True)
class PairRules:
    """Declared parameters of the candidate filter and of the break diagnostics. Set by looking at synthetic cases
    only; on real data they are a grid to freeze in a hypothesis spec, never something tuned on evaluation data."""
    min_obs: int = 250
    min_return_corr: float = 0.5
    max_eg_pvalue: float = 0.05
    min_half_life: float = 1.0
    max_half_life: float = 60.0
    n_subperiods: int = 3
    max_beta_drift: float = 0.35            # (max − min) of sub-window hedge ratios / |full-window ratio|
    max_sub_adf_pvalue: float = 0.20
    require_link: bool = True
    embargo_sessions: int = 1               # sessions strictly between formation_end and evaluation_start (S8 M2)
    max_missing_frac: float = 0.02          # share of sessions with either leg missing (S8 M1)
    max_gap_sessions: int = 3               # longest run of sessions with either leg missing (S8 M1)
    # retrospective break diagnostics on the evaluation window
    max_oos_adf_pvalue: float = 0.10
    max_variance_ratio: float = 3.0         # evaluation spread variance / formation spread variance
    max_mean_shift: float = 1.5             # |mean_eval − mean_form| / sd_form
    max_oos_beta_drift: float = 0.35
    n_eval_segments: int = 2                # each segment is also checked, so a late break is not averaged away

    def __post_init__(self):
        if isinstance(self.embargo_sessions, bool) or not isinstance(self.embargo_sessions, int) \
                or self.embargo_sessions < 1:
            raise TemporalError("the embargo between formation and evaluation is at least one session")
        if self.n_eval_segments < 1 or self.max_gap_sessions < 0 or not 0 <= self.max_missing_frac < 1:
            raise EquityDataError("invalid pair rules")


@dataclass(frozen=True)
class PairCandidate:
    y: str
    x: str
    link: str
    boundary: Boundary
    return_corr: float
    alpha: float
    beta: float
    eg_pvalue: float
    adf_pvalue: float
    half_life: float
    spread_mean: float
    spread_sd: float
    sub_betas: tuple
    sub_adf_pvalues: tuple
    reasons: tuple                           # empty when the pair passed every formation filter
    formation_hash: str
    status: str = "candidate"
    evidential_weight: int = 0

    @property
    def passed(self) -> bool:
        return not self.reasons


@dataclass
class StabilityReport:
    """A **retrospective** classification of a candidate's relationship over a whole evaluation window, computed
    after that window ended (S8 M3). It uses every observation of the window, so it is not a forecast, not a
    trading signal and not usable at any date inside the window; and its synthetic error rates (tests) describe the
    code on one generator, not how often real relationships break or persist."""
    pair: tuple
    n: int
    adf_pvalue: float
    half_life: float
    variance_ratio: float
    mean_shift: float
    beta_eval: float
    beta_drift: float
    flags: tuple
    events_in_window: int = 0
    zscores: np.ndarray = field(default_factory=lambda: np.zeros(0))
    missing: int = 0
    longest_gap: int = 0
    kind: str = "retrospective"
    usable_from: date | None = None          # the evaluation window's end: nothing here is known before it

    @property
    def stable(self) -> bool:
        return not self.flags


def missing_profile(y: np.ndarray, x: np.ndarray) -> dict:
    """Sessions with either leg missing: count, share, longest run, and whether a leg stops for good (a trailing
    run: delisting, merger or a long suspension)."""
    miss = ~(np.isfinite(np.asarray(y, float)) & np.isfinite(np.asarray(x, float)))
    run = longest = 0
    for m in miss:
        run = run + 1 if m else 0
        longest = max(longest, run)
    trailing = int(len(miss) - np.flatnonzero(~miss)[-1] - 1) if (~miss).any() else len(miss)
    return {"missing": int(miss.sum()), "share": float(miss.mean()) if miss.size else 1.0, "longest_gap": longest,
            "trailing": trailing}


def embargo_sessions(days, boundary: Boundary) -> int:
    """Sessions in ``days`` strictly between the formation end and the evaluation start."""
    return int(sum(1 for d in days if boundary.formation_end < d < boundary.evaluation_start))


# ---------------------------------------------------------------- primitives
def ols_hedge(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    y, x = np.asarray(y, float), np.asarray(x, float)
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < 3:
        raise EquityDataError("a hedge ratio needs at least three joint observations")
    X = np.column_stack([np.ones(ok.sum()), x[ok]])
    (a, b), *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    return float(a), float(b)


def rolling_hedge(y: np.ndarray, x: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """(alpha_t, beta_t) for each t, estimated on observations ``t − window .. t − 1`` only (NaN before)."""
    n = len(y)
    a, b = np.full(n, np.nan), np.full(n, np.nan)
    for t in range(window, n):
        try:
            a[t], b[t] = ols_hedge(y[t - window:t], x[t - window:t])
        except EquityDataError:
            pass
    return a, b


def beta_neutral_hedge(beta_y: float, beta_x: float) -> float:
    """Units of x per unit of y that make the spread's market beta zero."""
    if beta_x == 0 or not np.isfinite(beta_x):
        raise EquityDataError("the hedge leg has no market beta: a beta-neutral ratio is undefined")
    return float(beta_y / beta_x)


def spread(y, x, alpha: float, beta: float) -> np.ndarray:
    return np.asarray(y, float) - alpha - beta * np.asarray(x, float)


def residual_spread(ry: np.ndarray, rx: np.ndarray, factors: np.ndarray, formation: np.ndarray) -> np.ndarray:
    """Cumulative difference of the two legs' factor-model residual returns. Loadings are estimated on the
    ``formation`` rows only (boolean mask) and applied to every row."""
    F = np.asarray(factors, float).reshape(len(ry), -1)
    X = np.column_stack([np.ones(len(ry)), F])
    res = []
    for r in (ry, rx):
        ok = formation & np.isfinite(r) & np.isfinite(F).all(1)
        b, *_ = np.linalg.lstsq(X[ok], r[ok], rcond=None)
        res.append(np.where(np.isfinite(r), r - X @ b, 0.0))
    return np.cumsum(res[0] - res[1])


def half_life(s: np.ndarray) -> float:
    """Half-life (in observations) of an AR(1) fit ``Δs_t = c + φ s_{t−1}``; inf when not mean-reverting."""
    s = np.asarray(s, float)
    s = s[np.isfinite(s)]
    if s.size < 10:
        return float("nan")
    ds, lag = np.diff(s), s[:-1]
    X = np.column_stack([np.ones(lag.size), lag])
    (_, phi), *_ = np.linalg.lstsq(X, ds, rcond=None)
    if phi >= 0 or phi <= -1:
        return float("inf") if phi >= 0 else float("nan")
    return float(-np.log(2) / np.log1p(phi))


def adf_pvalue(s: np.ndarray, maxlag: int | None = None) -> float:
    from statsmodels.tsa.stattools import adfuller
    s = np.asarray(s, float)
    s = s[np.isfinite(s)]
    if s.size < 20 or np.ptp(s) == 0:
        return float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(adfuller(s, maxlag=maxlag, autolag="AIC" if maxlag is None else None)[1])


def engle_granger_pvalue(y: np.ndarray, x: np.ndarray) -> float:
    """The larger of the two Engle–Granger p-values (y on x, x on y): a pair must cointegrate both ways round."""
    from statsmodels.tsa.stattools import coint
    y, x = np.asarray(y, float), np.asarray(x, float)
    ok = np.isfinite(y) & np.isfinite(x)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p1 = coint(y[ok], x[ok])[1]
        p2 = coint(x[ok], y[ok])[1]
    return float(max(p1, p2))


def _hash_arrays(*arrays) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(np.round(np.asarray(a, float), 12) + 0.0, dtype="<f8").tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------- discovery
class PairDiscovery:
    """Candidate pairs from formation-window data only. ``log_prices`` maps id -> log price array aligned with
    ``days`` (log of a total-return index; NaN when not trading).

    **Every pair looked at is counted (S8 L8).** ``attempts`` records, for multiple-testing accounting, how many
    pairs were considered and what happened to each: ``no_link``, ``insufficient_data`` (missing observations or
    trading discontinuities), ``rejected`` (a statistical filter) or ``passed``; ``attempt_log`` lists them. The
    number of candidates that passed is meaningless without the number tried."""

    def __init__(self, days, log_prices: dict, boundary: Boundary, rules: PairRules = PairRules(), *, link=None):
        days = np.asarray(days, dtype=object)
        if len(days) > 1 and not all(a < b for a, b in zip(days, days[1:])):
            raise TemporalError("days must be strictly increasing")
        for k, v in log_prices.items():
            if len(v) != len(days):
                raise EquityDataError(f"{k}: price array does not match the days")
        if embargo_sessions(days, boundary) < rules.embargo_sessions:
            raise TemporalError(f"only {embargo_sessions(days, boundary)} sessions between formation end and "
                                f"evaluation start; the rules declare an embargo of {rules.embargo_sessions}")
        m = np.array([boundary.formation_start <= d <= boundary.formation_end for d in days], dtype=bool)
        self.days = days[m]
        self.prices = {k: np.asarray(v, float)[m].copy() for k, v in sorted(log_prices.items())}
        self.boundary, self.rules, self.link = boundary, rules, link
        if rules.require_link and link is None:
            raise EquityDataError("rules require an economic link but no link function was given")
        self.attempts = {"considered": 0, "no_link": 0, "insufficient_data": 0, "rejected": 0, "passed": 0}
        self.attempt_log: list[tuple] = []

    def _record(self, a: str, b: str, outcome: str) -> None:
        self.attempts["considered"] += 1
        self.attempts[outcome] += 1
        self.attempt_log.append((a, b, outcome))

    def evaluate_pair(self, a: str, b: str) -> PairCandidate | None:
        r, bd = self.rules, self.boundary
        link = self.link(a, b, bd.formation_end) if self.link is not None else "none required"
        if r.require_link and not link:
            self._record(a, b, "no_link")
            return None
        y, x = self.prices[a], self.prices[b]
        mp = missing_profile(y, x)
        ok = np.isfinite(y) & np.isfinite(x)
        short = []
        if ok.sum() < r.min_obs:
            short.append(f"{int(ok.sum())} joint obs")
        if mp["share"] > r.max_missing_frac:
            short.append(f"{mp['missing']} sessions with a leg missing")
        if mp["longest_gap"] > r.max_gap_sessions:
            short.append(f"trading discontinuity of {mp['longest_gap']} sessions")
        if short:
            self._record(a, b, "insufficient_data")
            return PairCandidate(a, b, str(link), bd, *([float("nan")] * 8), (), (), tuple(short),
                                 _hash_arrays(y, x))
        y, x = y[ok], x[ok]
        reasons = []
        ry, rx = np.diff(y), np.diff(x)
        corr = float(np.corrcoef(ry, rx)[0, 1])
        alpha, beta = ols_hedge(y, x)
        s = spread(y, x, alpha, beta)
        eg = engle_granger_pvalue(y, x)
        adf = adf_pvalue(s)
        hl = half_life(s)
        k = r.n_subperiods
        cuts = np.linspace(0, len(y), k + 1).astype(int)
        sub_b, sub_p = [], []
        for i in range(k):
            ys, xs = y[cuts[i]:cuts[i + 1]], x[cuts[i]:cuts[i + 1]]
            sub_b.append(ols_hedge(ys, xs)[1])
            sub_p.append(adf_pvalue(s[cuts[i]:cuts[i + 1]]))     # the full-window spread, piece by piece
        if corr < r.min_return_corr:
            reasons.append(f"return correlation {corr:.2f}")
        if not eg <= r.max_eg_pvalue:
            reasons.append(f"Engle-Granger p {eg:.3f}")
        if not (r.min_half_life <= hl <= r.max_half_life):
            reasons.append(f"half-life {hl:.1f}")
        drift = (max(sub_b) - min(sub_b)) / abs(beta) if beta != 0 else float("inf")
        if not drift <= r.max_beta_drift:
            reasons.append(f"hedge ratio drift {drift:.2f} across formation sub-windows")
        if any(not p <= r.max_sub_adf_pvalue for p in sub_p):
            reasons.append("spread not stationary in every formation sub-window")
        self._record(a, b, "rejected" if reasons else "passed")
        return PairCandidate(a, b, str(link), bd, corr, alpha, beta, eg, adf, hl, float(s.mean()),
                             float(s.std(ddof=1)), tuple(sub_b), tuple(sub_p), tuple(reasons), _hash_arrays(y, x))

    def candidates(self, *, include_failed: bool = False) -> list[PairCandidate]:
        out = []
        for a, b in itertools.combinations(sorted(self.prices), 2):
            c = self.evaluate_pair(a, b)
            if c is not None and (include_failed or c.passed):
                out.append(c)
        return out


# ---------------------------------------------------------------- retrospective evaluation diagnostics
def _segment_flags(s: np.ndarray, c: PairCandidate, rules: PairRules) -> list[str]:
    flags = []
    vr = float(s.var(ddof=1) / c.spread_sd ** 2)
    shift = float(abs(s.mean() - c.spread_mean) / c.spread_sd)
    if vr > rules.max_variance_ratio:
        flags.append(f"spread variance ratio {vr:.2f}")
    if shift > rules.max_mean_shift:
        flags.append(f"spread mean shifted {shift:.2f} formation sd")
    return flags


def out_of_sample(c: PairCandidate, days, log_prices: dict, rules: PairRules = PairRules(), *,
                  events=()) -> StabilityReport:
    """Retrospective diagnostics of the candidate's spread over the evaluation window, with formation parameters
    frozen. ``events`` are dates of earnings releases or corporate actions of either leg (counted, never hidden).
    A leg that is missing, interrupted or stops trading is flagged, never dropped (S8 M1); the whole-window checks
    are repeated on ``n_eval_segments`` consecutive segments so a late break is not averaged away."""
    days = np.asarray(days, dtype=object)
    bd = c.boundary
    if embargo_sessions(days, bd) < rules.embargo_sessions:
        raise TemporalError("the evaluation window starts inside the declared embargo")
    m = np.array([bd.evaluation_start <= d <= bd.evaluation_end for d in days], dtype=bool)
    y, x = np.asarray(log_prices[c.y], float)[m], np.asarray(log_prices[c.x], float)[m]
    mp = missing_profile(y, x)
    flags = []
    if mp["trailing"] > 0:
        flags.append(f"a leg stops trading {mp['trailing']} sessions before the window ends (delisting, merger or "
                     "suspension): the pair ended")
    if mp["share"] > rules.max_missing_frac:
        flags.append(f"{mp['missing']} sessions with a leg missing")
    if mp["longest_gap"] > rules.max_gap_sessions:
        flags.append(f"trading discontinuity of {mp['longest_gap']} sessions")
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    if y.size < 30:
        flags.append(f"only {y.size} joint evaluation observations")
        return StabilityReport((c.y, c.x), int(y.size), float("nan"), float("nan"), float("nan"), float("nan"),
                               float("nan"), float("nan"), tuple(flags), 0, np.zeros(0), mp["missing"],
                               mp["longest_gap"], usable_from=bd.evaluation_end)
    s = spread(y, x, c.alpha, c.beta)
    z = (s - c.spread_mean) / c.spread_sd
    adf, hl = adf_pvalue(s), half_life(s)
    vr = float(s.var(ddof=1) / c.spread_sd ** 2)
    shift = float(abs(s.mean() - c.spread_mean) / c.spread_sd)
    _, b_eval = ols_hedge(y, x)
    drift = float(abs(b_eval - c.beta) / abs(c.beta)) if c.beta else float("inf")
    if not adf <= rules.max_oos_adf_pvalue:
        flags.append(f"evaluation spread not stationary (ADF p {adf:.3f})")
    flags += _segment_flags(s, c, rules)
    if drift > rules.max_oos_beta_drift:
        flags.append(f"hedge ratio moved {drift:.2f} of its formation value")
    if rules.n_eval_segments > 1:
        cuts = np.linspace(0, s.size, rules.n_eval_segments + 1).astype(int)
        for i in range(rules.n_eval_segments):
            seg = s[cuts[i]:cuts[i + 1]]
            if seg.size >= 20:
                for f in _segment_flags(seg, c, rules):
                    flags.append(f"segment {i + 1}/{rules.n_eval_segments}: {f}")
    n_ev = sum(1 for e in events if bd.evaluation_start <= e <= bd.evaluation_end)
    return StabilityReport((c.y, c.x), int(y.size), adf, hl, vr, shift, float(b_eval), drift, tuple(dict.fromkeys(flags)),
                           n_ev, z, mp["missing"], mp["longest_gap"], usable_from=bd.evaluation_end)


# ---------------------------------------------------------------- trading constraints
@dataclass(frozen=True)
class PairPosition:
    long: str
    short: str
    long_weight: float
    short_weight: float                      # positive number: the short leg's notional as a fraction of capital

    def weights(self) -> dict:
        return {self.long: self.long_weight, self.short: -self.short_weight}


def position_from_z(c: PairCandidate, z: float, gross: float) -> PairPosition:
    """Spread rich (z > 0): short y, long β·x; cheap (z < 0): the reverse. Legs scaled to total ``gross``."""
    wy, wx = 1.0, abs(c.beta)
    k = gross / (wy + wx)
    if z > 0:
        return PairPosition(c.x, c.y, wx * k, wy * k)
    return PairPosition(c.y, c.x, wy * k, wx * k)


def feasibility(pos: PairPosition, day: date, cost_model, betas: dict, *, earnings_within: dict | None = None) -> dict:
    """What it costs and what is left: borrow availability and fee of the short leg (``BorrowError`` if not
    borrowable or unknown), daily holding cost, gross and net exposure, residual market beta, and whether either
    leg reports earnings inside the holding window. A "market-neutral" pair can carry large residual beta."""
    w = pos.weights()
    cost_model.check_book(w, day)
    if pos.long not in betas or pos.short not in betas:
        raise EquityDataError("residual beta needs both legs' betas")
    rec = cost_model.borrow.status(pos.short, day)
    if not rec.available:
        raise BorrowError(f"{pos.short}: not borrowable at {day}")
    ew = earnings_within or {}
    return {"gross": pos.long_weight + pos.short_weight, "net": pos.long_weight - pos.short_weight,
            "beta": pos.long_weight * betas[pos.long] - pos.short_weight * betas[pos.short],
            "borrow_fee_annual": rec.fee_annual, "holding_cost_daily": cost_model.holding_cost_daily(w, day),
            "earnings_in_window": bool(ew.get(pos.long) or ew.get(pos.short))}
