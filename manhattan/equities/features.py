"""Cross-sectional features: normalisation, neutralisation and common factor exposures, computed point in time.

**Exposure or signal.** A ``CrossSection`` is either an ``exposure`` (a description of a security: its beta, its
momentum, its valuation) or a ``candidate_signal`` (a proposed predictor of return). A candidate signal must name the
hypothesis it belongs to (``hypothesis``, a Manhattan spec id or a catalogue id) and carries zero evidential weight.
Common factors computed here are exposures: they are what an alpha signal must be neutralised against, not alpha.

**Point in time.** Every function takes ``as_of`` and the universe ``Snapshot`` formed at ``as_of``
(``assert_snapshot_for``); return panels are cut at ``as_of`` inside the function, so appending future data cannot
change a result. Normalisation and neutralisation use only that day's cross-section of that day's members: a
z-score that used the future universe or full-sample moments would leak.

**Neutralisation is verified.** ``neutralize`` regresses on exposures (weighted least squares, optionally within
groups) and returns the residual; ``check_neutral`` then measures the residual's exposure to each factor and raises
``NeutralizationError`` when it is not neutral to tolerance (a rank-deficient design, a factor left out of the
regression, or a neutralisation done on a different universe).

    raw momentum      Σ log(1 + r) over [t − lookback, t − skip)
    industry-relative momentum minus its category mean
    residual momentum the same sum of residuals of a market (and category) regression estimated on the formation
                      window only, divided by the residual standard deviation
    short-term reversal  − Σ log(1 + r) over the last ``window`` sessions
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from .errors import EquityDataError, NeutralizationError, TemporalError
from .fundamentals import FundamentalStore
from .universe import Snapshot, assert_snapshot_for

KINDS = ("exposure", "candidate_signal")


@dataclass(frozen=True)
class CrossSection:
    name: str
    as_of: date
    ids: tuple
    values: np.ndarray
    kind: str = "exposure"
    universe_hash: str = ""
    hypothesis: str | None = None
    evidential_weight: int = 0

    def __post_init__(self):
        if self.kind not in KINDS:
            raise EquityDataError(f"{self.name}: kind is one of {KINDS}")
        if self.kind == "candidate_signal" and not self.hypothesis:
            raise EquityDataError(f"{self.name}: a candidate signal names the hypothesis it belongs to")
        if self.evidential_weight != 0:
            raise EquityDataError(f"{self.name}: a feature carries no evidential weight")
        if len(self.ids) != len(self.values):
            raise EquityDataError(f"{self.name}: ids and values differ in length")

    def as_dict(self) -> dict:
        return {i: float(v) for i, v in zip(self.ids, self.values)}


@dataclass(frozen=True)
class ReturnPanel:
    """Daily total returns: ``R[i, j]`` is the return of ``ids[j]`` on ``days[i]`` (NaN when missing)."""
    days: np.ndarray
    ids: tuple
    R: np.ndarray

    def __post_init__(self):
        if self.R.shape != (len(self.days), len(self.ids)):
            raise EquityDataError("return panel shape does not match its days and ids")
        if len(self.days) > 1 and not all(a < b for a, b in zip(self.days, self.days[1:])):
            raise TemporalError("return panel days must be strictly increasing")

    def upto(self, as_of: date) -> "ReturnPanel":
        keep = np.array([d <= as_of for d in self.days], dtype=bool)
        return ReturnPanel(self.days[keep], self.ids, self.R[keep])

    def columns(self, ids) -> np.ndarray:
        idx = {s: j for j, s in enumerate(self.ids)}
        missing = [s for s in ids if s not in idx]
        if missing:
            raise EquityDataError(f"securities not in the panel: {missing[:5]}")
        return self.R[:, [idx[s] for s in ids]]


# ---------------------------------------------------------------- normalisation
def winsorize(x: np.ndarray, lower: float = 0.01, upper: float = 0.99) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    ok = np.isfinite(x)
    if ok.sum() < 3:
        return x.copy()
    lo, hi = np.quantile(x[ok], [lower, upper])
    return np.where(ok, np.clip(x, lo, hi), np.nan)


def zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    ok = np.isfinite(x)
    out = np.full_like(x, np.nan)
    if ok.sum() < 2:
        return out
    sd = x[ok].std(ddof=1)
    if sd == 0:
        out[ok] = 0.0
        return out
    out[ok] = (x[ok] - x[ok].mean()) / sd
    return out


def rank_normalize(x: np.ndarray) -> np.ndarray:
    """Ranks mapped to (−0.5, 0.5); ties share their mean rank; NaN stays NaN."""
    x = np.asarray(x, dtype=float)
    ok = np.isfinite(x)
    out = np.full_like(x, np.nan)
    n = int(ok.sum())
    if n == 0:
        return out
    v = x[ok]
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(n)
    ranks[order] = np.arange(n, dtype=float)
    for u in np.unique(v):                                   # mean rank for ties
        m = v == u
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    out[ok] = (ranks + 0.5) / n - 0.5
    return out


def demean_within(x: np.ndarray, groups, min_size: int = 2) -> np.ndarray:
    """Subtract each group's mean; members of groups smaller than ``min_size`` become NaN."""
    x = np.asarray(x, dtype=float)
    g = np.asarray(groups, dtype=object)
    out = np.full_like(x, np.nan)
    for k in set(g.tolist()):
        m = (g == k) & np.isfinite(x)
        if m.sum() >= min_size:
            out[m] = x[m] - x[m].mean()
    return out


# ---------------------------------------------------------------- neutralisation
def _design(exposures: np.ndarray, groups=None) -> np.ndarray:
    X = np.asarray(exposures, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    cols = [np.ones(X.shape[0])] if groups is None else []
    if groups is not None:
        g = np.asarray(groups, dtype=object)
        for k in sorted(set(g.tolist()), key=str):
            cols.append((g == k).astype(float))
    return np.column_stack(cols + [X[:, j] for j in range(X.shape[1])]) if X.size else np.column_stack(cols)


def neutralize(x: np.ndarray, exposures: np.ndarray, *, groups=None, weights=None) -> np.ndarray:
    """Residual of ``x`` after weighted least squares on an intercept (or group dummies) and ``exposures``.
    Raises when the design is rank-deficient or has too few observations."""
    x = np.asarray(x, dtype=float)
    X = _design(np.asarray(exposures, dtype=float).reshape(len(x), -1), groups)
    w = np.ones(len(x)) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(x) & np.isfinite(X).all(axis=1) & np.isfinite(w) & (w > 0)
    Xo, xo, sw = X[ok], x[ok], np.sqrt(w[ok])
    keep = Xo.any(axis=0)                                     # drop empty group dummies
    Xo = Xo[:, keep]
    if ok.sum() <= Xo.shape[1] + 1:
        raise NeutralizationError(f"{int(ok.sum())} observations cannot be neutralised against {Xo.shape[1]} terms")
    if np.linalg.matrix_rank(Xo * sw[:, None]) < Xo.shape[1]:
        raise NeutralizationError("the exposure design is rank-deficient (collinear factors or a constant factor)")
    beta, *_ = np.linalg.lstsq(Xo * sw[:, None], xo * sw, rcond=None)
    out = np.full_like(x, np.nan)
    out[ok] = xo - Xo @ beta
    return out


def residual_exposure(x: np.ndarray, exposures: np.ndarray, weights=None) -> np.ndarray:
    """Weighted correlation-like exposure of ``x`` to each column: Σ w x f / sqrt(Σ w x² · Σ w f̃²), f̃ demeaned."""
    x = np.asarray(x, dtype=float)
    F = np.asarray(exposures, dtype=float).reshape(len(x), -1)
    w = np.ones(len(x)) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(x) & np.isfinite(F).all(axis=1)
    x, F, w = x[ok], F[ok], w[ok]
    F = F - (w[:, None] * F).sum(0) / w.sum()
    den = np.sqrt((w * x * x).sum() * (w[:, None] * F * F).sum(0))
    return np.where(den > 0, (w[:, None] * x[:, None] * F).sum(0) / np.where(den > 0, den, 1.0), 0.0)


def check_neutral(x: np.ndarray, exposures: np.ndarray, *, names=None, weights=None, tol: float = 1e-6) -> None:
    """``NeutralizationError`` unless ``x`` has (numerically) zero exposure to every column."""
    e = residual_exposure(x, exposures, weights)
    bad = [(names[i] if names else i, float(v)) for i, v in enumerate(e) if abs(v) > tol]
    if bad:
        raise NeutralizationError(f"signal is not neutral: residual exposures {bad}")


# ---------------------------------------------------------------- return-based exposures
def _log_sum(R: np.ndarray, min_frac: float) -> np.ndarray:
    lr = np.log1p(R)
    ok = np.isfinite(lr)
    s = np.where(ok, lr, 0.0).sum(0)
    return np.where(ok.mean(0) >= min_frac, s, np.nan) if R.shape[0] else np.full(R.shape[1], np.nan)


def momentum(panel: ReturnPanel, snap: Snapshot, as_of: date, *, lookback: int = 252, skip: int = 21,
             min_frac: float = 0.8) -> CrossSection:
    assert_snapshot_for(snap, as_of)
    p = panel.upto(as_of)
    if lookback <= skip:
        raise EquityDataError("lookback must exceed skip")
    n = len(p.days)
    if n < lookback:
        raise EquityDataError(f"momentum needs {lookback} sessions before {as_of}; have {n}")
    R = p.columns(snap.members)[n - lookback:n - skip]
    return CrossSection(f"mom_{lookback}_{skip}", as_of, snap.members, _log_sum(R, min_frac), "exposure",
                        snap.membership_hash())


def industry_relative(cs: CrossSection, snap: Snapshot) -> CrossSection:
    assert_snapshot_for(snap, cs.as_of)
    if cs.ids != snap.members:
        raise EquityDataError("the cross-section is not on the snapshot's members")
    groups = [snap.categories[s] for s in cs.ids]
    return CrossSection(cs.name + "_ind_rel", cs.as_of, cs.ids, demean_within(cs.values, groups), cs.kind,
                        cs.universe_hash, cs.hypothesis)


def short_term_reversal(panel: ReturnPanel, snap: Snapshot, as_of: date, *, window: int = 21,
                        min_frac: float = 0.8) -> CrossSection:
    assert_snapshot_for(snap, as_of)
    p = panel.upto(as_of)
    if len(p.days) < window:
        raise EquityDataError(f"reversal needs {window} sessions before {as_of}")
    R = p.columns(snap.members)[-window:]
    return CrossSection(f"strev_{window}", as_of, snap.members, -_log_sum(R, min_frac), "exposure",
                        snap.membership_hash())


def rolling_beta(panel: ReturnPanel, market: np.ndarray, snap: Snapshot, as_of: date, *, window: int = 252,
                 min_obs: int = 126) -> CrossSection:
    """Market beta from the ``window`` sessions up to ``as_of``. ``market`` is aligned with ``panel.days``."""
    assert_snapshot_for(snap, as_of)
    keep = np.array([d <= as_of for d in panel.days])
    m = np.asarray(market, dtype=float)[keep][-window:]
    R = panel.upto(as_of).columns(snap.members)[-window:]
    out = np.full(R.shape[1], np.nan)
    for j in range(R.shape[1]):
        ok = np.isfinite(R[:, j]) & np.isfinite(m)
        if ok.sum() >= min_obs:
            mm = m[ok] - m[ok].mean()
            out[j] = float((mm * (R[ok, j] - R[ok, j].mean())).sum() / (mm * mm).sum())
    return CrossSection(f"beta_{window}", as_of, snap.members, out, "exposure", snap.membership_hash())


def residual_momentum(panel: ReturnPanel, market: np.ndarray, snap: Snapshot, as_of: date, *, lookback: int = 252,
                      skip: int = 21, min_frac: float = 0.8) -> CrossSection:
    """Sum of market-model residuals over [t − lookback, t − skip), scaled by their standard deviation; the
    regression is estimated on that same formation window only (no later return enters it)."""
    assert_snapshot_for(snap, as_of)
    keep = np.array([d <= as_of for d in panel.days])
    m_all = np.asarray(market, dtype=float)[keep]
    R_all = panel.upto(as_of).columns(snap.members)
    n = R_all.shape[0]
    if n < lookback:
        raise EquityDataError(f"residual momentum needs {lookback} sessions before {as_of}")
    R, m = R_all[n - lookback:n - skip], m_all[n - lookback:n - skip]
    out = np.full(R.shape[1], np.nan)
    for j in range(R.shape[1]):
        ok = np.isfinite(R[:, j]) & np.isfinite(m)
        if ok.mean() < min_frac:
            continue
        X = np.column_stack([np.ones(ok.sum()), m[ok]])
        b, *_ = np.linalg.lstsq(X, R[ok, j], rcond=None)
        e = R[ok, j] - X @ b
        sd = e.std(ddof=2)
        out[j] = e.sum() / sd if sd > 0 else np.nan
    return CrossSection(f"resmom_{lookback}_{skip}", as_of, snap.members, out, "exposure", snap.membership_hash())


# ---------------------------------------------------------------- fundamental exposures
FUNDAMENTAL_EXPOSURES = {
    # name: (numerator metric, denominator metric or None, transform)
    "gross_profitability": ("gross_profit_ttm", "total_assets"),
    "operating_margin": ("operating_income_ttm", "revenue_ttm"),
    "fcf_margin": ("free_cash_flow_ttm", "revenue_ttm"),
    "rd_intensity": ("rd_expense_ttm", "revenue_ttm"),
    "sbc_intensity": ("sbc_expense_ttm", "revenue_ttm"),
    "capital_intensity": ("capex_ttm", "revenue_ttm"),
    "leverage": ("total_debt", "total_assets"),
    "cash_to_assets": ("cash", "total_assets"),
}


def fundamental_exposure(name: str, store: FundamentalStore, snap: Snapshot, as_of: date, company_of,
                         *, max_age_days: int = 200) -> CrossSection:
    """A ratio of two metrics, each the latest value known at ``as_of`` (and not older than ``max_age_days``)."""
    assert_snapshot_for(snap, as_of)
    if name not in FUNDAMENTAL_EXPOSURES:
        raise EquityDataError(f"unknown fundamental exposure {name!r}")
    num, den = FUNDAMENTAL_EXPOSURES[name]
    vals = []
    for s in snap.members:
        v = store.ratio(company_of(s), num, den, as_of, max_age_days=max_age_days)
        vals.append(np.nan if v is None else v)
    return CrossSection(name, as_of, snap.members, np.array(vals, dtype=float), "exposure", snap.membership_hash())


def growth_exposure(metric: str, store: FundamentalStore, snap: Snapshot, as_of: date, company_of,
                    *, lag: int = 4) -> CrossSection:
    assert_snapshot_for(snap, as_of)
    vals = [store.growth(company_of(s), metric, as_of, lag=lag) for s in snap.members]
    return CrossSection(f"{metric}_growth_{lag}", as_of, snap.members,
                        np.array([np.nan if v is None else v for v in vals], dtype=float), "exposure",
                        snap.membership_hash())


def valuation_exposure(metric: str, store: FundamentalStore, prices, snap: Snapshot, as_of: date, company_of,
                       *, shares_metric: str = "shares_outstanding", max_age_days: int = 200) -> CrossSection:
    """``metric`` per share over the close at ``as_of`` (a yield: earnings, sales, book or cash flow to price)."""
    assert_snapshot_for(snap, as_of)
    vals = []
    for s in snap.members:
        c = company_of(s)
        m = store.value(c, metric, as_of, max_age_days=max_age_days)
        sh = store.value(c, shares_metric, as_of, max_age_days=max_age_days)
        bars = prices.bars(s, as_of, as_of)
        if m is None or sh is None or not bars or sh.value <= 0:
            vals.append(np.nan)
            continue
        if m.currency and m.currency != prices.currency(s):
            raise EquityDataError(f"{s}: {metric} in {m.currency}, price in {prices.currency(s)}")
        vals.append(m.value / (sh.value * bars[-1].close))
    return CrossSection(f"{metric}_yield", as_of, snap.members, np.array(vals, dtype=float), "exposure",
                        snap.membership_hash())


def candidate_signal(cs: CrossSection, hypothesis: str, *, neutral_to: np.ndarray | None = None,
                     groups=None, names=None) -> CrossSection:
    """Turn an exposure into a candidate signal of ``hypothesis``, optionally neutralised (and verified neutral)
    against ``neutral_to`` exposures computed on the same members and day."""
    v = cs.values
    if neutral_to is not None:
        F = np.asarray(neutral_to, dtype=float).reshape(len(v), -1)
        v = neutralize(v, F, groups=groups)
        check_neutral(v, F, names=names)
    return CrossSection(cs.name, cs.as_of, cs.ids, v, "candidate_signal", cs.universe_hash, hypothesis)
