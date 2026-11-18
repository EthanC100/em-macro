"""Historical fundamental analogues: which companies, at which past dates, looked like this company does now.

    pool = AnaloguePool()
    pool.add(Observation("C7", date(2004, 3, 31), {"rev_growth": 0.41, "gross_margin": 0.62, ...},
                         known={"rev_growth": date(2004, 3, 2), ...}, category="enterprise_software",
                         in_universe=True))
    pool.add_outcome(Outcome("C7", start=date(2004, 3, 31), end=date(2005, 3, 31), value=..., known_from=...))
    res = match(pool, target, T=date(2010, 6, 30), k=10, purpose="descriptive")
    fc = forecast(pool, match(pool, target, T, k=10, purpose="training", horizon_days=365))

**Temporal integrity at a prediction date T.**

* A target's or candidate's features were known at its own observation date: ``Observation`` refuses a feature
  whose ``known`` date is later than ``as_of``; a target observed at ``T`` must have ``as_of == T``.
* Candidates are observations with ``as_of <= T`` that were **in the point-in-time universe** at their own date
  (``in_universe``); the pool is built from universe snapshots, never from today's survivors.
* The target company's own observations are excluded (``exclude_self``), so its later path cannot match itself.
* **Descriptive** eligibility stops there: such analogues may be shown, never used to fit or score a forecast.
* **Training** eligibility further requires an outcome whose whole window ended, and whose value was observable
  (``known_from``), by ``T``; and keeps at most one observation per company per outcome horizon (the latest), so
  overlapping outcome windows of one company are not counted as independent analogues.
* The matcher never sees outcomes. ``match`` reads only features; outcomes are attached afterwards by ``forecast``,
  which re-checks that each is known at ``T``. A feature whose name looks like an outcome
  (``OUTCOME_LIKE``) is refused.
* Normalisation (median and MAD, and the covariance for Mahalanobis distance) is fitted on the eligible candidates
  at ``T`` only.

**Distances** (all missing-data aware: only features present in both, at least ``min_overlap`` of them, averaged
over the present ones): ``standardized`` (scaled Euclidean), ``mahalanobis`` (shrunk covariance), ``trajectory``
(the mean standardised distance over the last ``trajectory_len`` aligned observations of target and candidate).
Constraints: same ``category`` (industry-constrained), same growth ``stage``, same ``regime``.

**Explanations.** Each match carries each feature's share of its squared distance and both standardised values.

Baselines (sector mean, linear model) are built on exactly the training-eligible set, so an analogue forecast can
later be compared with them on equal information. Whether analogues add anything beyond common factors is a
hypothesis (catalogue family B): nothing here measures it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from .errors import EquityDataError, EvidenceError, TemporalError

PURPOSES = ("descriptive", "training")
METHODS = ("standardized", "mahalanobis", "trajectory")
OUTCOME_LIKE = re.compile(r"(^|_)(fwd|forward|future|outcome|target|next|subsequent|realized|realised)(_|$)", re.I)


@dataclass(frozen=True)
class Observation:
    company_id: str
    as_of: date
    features: dict
    known: dict                      # feature -> day it became usable
    category: str = ""
    stage: str = ""
    regime: str = ""
    in_universe: bool = True

    def __post_init__(self):
        for f in self.features:
            if OUTCOME_LIKE.search(f):
                raise EvidenceError(f"feature {f!r} looks like an outcome: outcomes never enter matching")
            if f not in self.known:
                raise TemporalError(f"{self.company_id} {self.as_of}: no availability date for feature {f!r}")
            if self.known[f] > self.as_of:
                raise TemporalError(f"{self.company_id} {self.as_of}: feature {f!r} known only from {self.known[f]}")


@dataclass(frozen=True)
class Outcome:
    company_id: str
    start: date                      # the observation date it follows
    end: date                        # end of the outcome window
    value: float
    known_from: date                 # first day the full outcome was observable (≥ end; delisting proceeds later)

    def __post_init__(self):
        if not self.start < self.end <= self.known_from:
            raise TemporalError(f"{self.company_id}: an outcome needs start < end <= known_from")


@dataclass(frozen=True)
class Match:
    company_id: str
    as_of: date
    distance: float
    contributions: dict              # feature -> share of the squared distance
    target_z: dict
    candidate_z: dict
    n_features: int


@dataclass
class MatchResult:
    target: Observation
    T: date
    purpose: str
    method: str
    matches: list
    pool_size: int
    excluded: dict = field(default_factory=dict)
    horizon_days: int | None = None
    centre: dict = field(default_factory=dict)
    scale: dict = field(default_factory=dict)
    evidential_weight: int = 0


class AnaloguePool:
    def __init__(self):
        self._obs: list[Observation] = []
        self._out: dict[tuple, Outcome] = {}

    def add(self, o: Observation) -> None:
        if any(p.company_id == o.company_id and p.as_of == o.as_of for p in self._obs):
            raise EquityDataError(f"{o.company_id} {o.as_of}: duplicate observation")
        self._obs.append(o)

    def add_outcome(self, o: Outcome) -> None:
        self._out[(o.company_id, o.start)] = o

    def observations(self) -> list[Observation]:
        return list(self._obs)

    def history(self, company_id: str, upto: date) -> list[Observation]:
        return sorted((o for o in self._obs if o.company_id == company_id and o.as_of <= upto), key=lambda o: o.as_of)

    def outcome(self, company_id: str, start: date, T: date) -> Outcome | None:
        """The outcome following ``(company, start)`` if fully observable at ``T``; never one that is not."""
        o = self._out.get((company_id, start))
        if o is None or o.known_from > T:
            return None
        return o

    def eligible(self, target: Observation, T: date, *, purpose: str, horizon_days: int | None = None,
                 exclude_self: bool = True, category: bool = False, stage: bool = False,
                 regime: bool = False) -> tuple[list[Observation], dict]:
        if purpose not in PURPOSES:
            raise EquityDataError(f"purpose is one of {PURPOSES}")
        if target.as_of != T:
            raise TemporalError(f"the target is observed at {target.as_of}, the prediction is at {T}")
        if purpose == "training" and not horizon_days:
            raise EquityDataError("training eligibility needs the outcome horizon")
        excl = {"future": 0, "self": 0, "not_in_universe": 0, "constraint": 0, "outcome_unobservable": 0,
                "overlapping_horizon": 0}
        keep = []
        for o in self._obs:
            if o.as_of > T:
                excl["future"] += 1
            elif exclude_self and o.company_id == target.company_id:
                excl["self"] += 1
            elif not o.in_universe:
                excl["not_in_universe"] += 1
            elif (category and o.category != target.category) or (stage and o.stage != target.stage) \
                    or (regime and o.regime != target.regime):
                excl["constraint"] += 1
            elif purpose == "training" and self.outcome(o.company_id, o.as_of, T) is None:
                excl["outcome_unobservable"] += 1
            else:
                keep.append(o)
        if purpose == "training":                   # one observation per company per horizon: the latest
            keep.sort(key=lambda o: (o.company_id, o.as_of), reverse=True)
            thinned, last = [], {}
            for o in keep:
                prev = last.get(o.company_id)
                if prev is not None and (prev - o.as_of).days < horizon_days:
                    excl["overlapping_horizon"] += 1
                    continue
                thinned.append(o)
                last[o.company_id] = o.as_of
            keep = thinned
        return sorted(keep, key=lambda o: (o.company_id, o.as_of)), excl


# ---------------------------------------------------------------- normalisation and distance
def robust_scale(pool: list[Observation], names) -> tuple[dict, dict]:
    centre, scale = {}, {}
    for f in names:
        v = np.array([o.features.get(f, np.nan) for o in pool], float)
        v = v[np.isfinite(v)]
        if v.size < 3:
            centre[f], scale[f] = np.nan, np.nan
            continue
        med = float(np.median(v))
        mad = float(np.median(np.abs(v - med))) * 1.4826
        sd = float(v.std(ddof=1))
        centre[f], scale[f] = med, (mad if mad > 0 else (sd if sd > 0 else np.nan))
    return centre, scale


def _z(o: Observation, names, centre, scale) -> np.ndarray:
    return np.array([(o.features.get(f, np.nan) - centre[f]) / scale[f] if np.isfinite(scale[f]) else np.nan
                     for f in names], float)


def shrunk_covariance(Z: np.ndarray, shrink: float = 0.2) -> np.ndarray:
    """Covariance of complete rows, shrunk toward its diagonal: (1 − s)·S + s·diag(S)."""
    Zc = Z[np.isfinite(Z).all(1)]
    if Zc.shape[0] <= Z.shape[1] + 1:
        return np.eye(Z.shape[1])
    S = np.cov(Zc, rowvar=False)
    return (1 - shrink) * S + shrink * np.diag(np.diag(S))


def _pair_distance(zt: np.ndarray, zc: np.ndarray, names, *, min_overlap: int, cov_inv=None, weights=None):
    ok = np.isfinite(zt) & np.isfinite(zc)
    if ok.sum() < min_overlap:
        return None
    d = zt[ok] - zc[ok]
    w = np.ones(ok.sum()) if weights is None else np.asarray(weights, float)[ok]
    if cov_inv is None:
        parts = w * d * d
        total = float(parts.sum() / w.sum())
    else:
        Ci = cov_inv(ok)
        total = float(d @ Ci @ d) / ok.sum()
        parts = d * (Ci @ d)
    tot = parts.sum()
    contrib = {n: float(p / tot) if tot > 0 else 0.0 for n, p in zip(np.asarray(names)[ok], parts)}
    return float(np.sqrt(max(total, 0.0))), contrib, int(ok.sum())


def match(pool: AnaloguePool, target: Observation, T: date, *, k: int = 10, purpose: str = "descriptive",
          method: str = "standardized", features=None, horizon_days: int | None = None, min_overlap: int = 3,
          trajectory_len: int = 4, shrink: float = 0.2, **constraints) -> MatchResult:
    if method not in METHODS:
        raise EquityDataError(f"method is one of {METHODS}")
    names = sorted(features or target.features)
    for n in names:
        if OUTCOME_LIKE.search(n):
            raise EvidenceError(f"feature {n!r} looks like an outcome")
    cands, excl = pool.eligible(target, T, purpose=purpose, horizon_days=horizon_days, **constraints)
    centre, scale = robust_scale(cands, names)
    zt = _z(target, names, centre, scale)
    cov_inv = None
    if method == "mahalanobis":
        Z = np.array([_z(o, names, centre, scale) for o in cands]) if cands else np.zeros((0, len(names)))
        C = shrunk_covariance(Z, shrink) if len(cands) else np.eye(len(names))

        def cov_inv(mask, C=C):
            return np.linalg.pinv(C[np.ix_(mask, mask)])
    out = []
    for o in cands:
        zc = _z(o, names, centre, scale)
        if method == "trajectory":
            th = pool.history(target.company_id, T)[-trajectory_len:]
            ch = pool.history(o.company_id, o.as_of)[-trajectory_len:]
            if len(th) < trajectory_len or len(ch) < trajectory_len:
                continue
            ds, contrib, nf = [], {}, 0
            for a, b in zip(th, ch):
                r = _pair_distance(_z(a, names, centre, scale), _z(b, names, centre, scale), names,
                                   min_overlap=min_overlap)
                if r is None:
                    break
                ds.append(r[0] ** 2)
                for f, v in r[1].items():
                    contrib[f] = contrib.get(f, 0.0) + v / trajectory_len
                nf = max(nf, r[2])
            if len(ds) < trajectory_len:
                continue
            res = (float(np.sqrt(np.mean(ds))), contrib, nf)
        else:
            res = _pair_distance(zt, zc, names, min_overlap=min_overlap, cov_inv=cov_inv)
        if res is None:
            continue
        dist, contrib, nf = res
        out.append(Match(o.company_id, o.as_of, dist, contrib,
                         {n: float(v) for n, v in zip(names, zt)}, {n: float(v) for n, v in zip(names, zc)}, nf))
    out.sort(key=lambda m: (m.distance, m.company_id, m.as_of))
    return MatchResult(target, T, purpose, method, out[:k], len(cands), excl, horizon_days, centre, scale)


def forecast(pool: AnaloguePool, res: MatchResult, *, bandwidth: float | None = None) -> dict:
    """Kernel-weighted mean of the matched analogues' outcomes. Only for training-eligible matches."""
    if res.purpose != "training":
        raise EvidenceError("descriptive analogues cannot be used to fit or score a forecast")
    vals, ws = [], []
    h = bandwidth or (np.median([m.distance for m in res.matches]) if res.matches else 1.0) or 1.0
    for m in res.matches:
        o = pool.outcome(m.company_id, m.as_of, res.T)
        if o is None:
            raise TemporalError(f"{m.company_id} {m.as_of}: outcome not observable at {res.T}")
        if (o.end - o.start).days > (res.horizon_days or 0) + 7 or o.known_from > res.T:
            raise TemporalError(f"{m.company_id}: outcome window or availability inconsistent with T")
        vals.append(o.value)
        ws.append(np.exp(-0.5 * (m.distance / h) ** 2))
    if not vals:
        return {"forecast": float("nan"), "n": 0, "evidential_weight": 0}
    w = np.array(ws) / np.sum(ws)
    return {"forecast": float(w @ np.array(vals)), "n": len(vals), "effective_n": float(1 / np.sum(w * w)),
            "evidential_weight": 0}


# ---------------------------------------------------------------- baselines on the same information
def training_set(pool: AnaloguePool, target: Observation, T: date, horizon_days: int, **constraints):
    cands, _ = pool.eligible(target, T, purpose="training", horizon_days=horizon_days, **constraints)
    return [(o, pool.outcome(o.company_id, o.as_of, T)) for o in cands]


def sector_mean_baseline(pool: AnaloguePool, target: Observation, T: date, horizon_days: int) -> float:
    rows = training_set(pool, target, T, horizon_days, category=True)
    return float(np.mean([y.value for _, y in rows])) if rows else float("nan")


def linear_baseline(pool: AnaloguePool, target: Observation, T: date, horizon_days: int, features,
                    ridge: float = 1.0) -> float:
    """Ridge regression of outcome on standardised features, fitted on the training-eligible set at ``T``."""
    rows = training_set(pool, target, T, horizon_days)
    names = sorted(features)
    centre, scale = robust_scale([o for o, _ in rows], names)
    X = np.array([_z(o, names, centre, scale) for o, _ in rows]) if rows else np.zeros((0, len(names)))
    y = np.array([r.value for _, r in rows], float)
    ok = np.isfinite(X).all(1) if X.size else np.zeros(0, bool)
    if ok.sum() <= len(names):
        return float("nan")
    Xo = np.column_stack([np.ones(ok.sum()), X[ok]])
    P = ridge * np.eye(Xo.shape[1])
    P[0, 0] = 0
    b = np.linalg.solve(Xo.T @ Xo + P, Xo.T @ y[ok])
    zt = _z(target, names, centre, scale)
    if not np.isfinite(zt).all():
        return float("nan")
    return float(b[0] + zt @ b[1:])


def growth_stage(rev_growth: float, operating_margin: float) -> str:
    """A declared, coarse stage label (for the ``stage`` constraint). Boundaries are definitions, not fitted."""
    if not (np.isfinite(rev_growth) and np.isfinite(operating_margin)):
        return "unknown"
    if rev_growth >= 0.30:
        return "hypergrowth_profitable" if operating_margin > 0 else "hypergrowth_unprofitable"
    if rev_growth >= 0.10:
        return "growth_profitable" if operating_margin > 0 else "growth_unprofitable"
    return "mature" if operating_margin > 0 else "declining_or_distressed"


def horizon_end(start: date, horizon_days: int) -> date:
    return start + timedelta(days=horizon_days)
