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
* **Outcome selection is by the calendar only, never by whether an outcome happens to be there (S8 H2, R1).** A
  pool's ``OutcomePolicy`` declares one publication grace period (bounded by ``MAX_OUTCOME_GRACE_DAYS``) and where it
  comes from. An observation is *settled* at ``T`` when ``as_of + horizon + grace <= T`` — the same rule for every
  company, failed or not. Unsettled observations are excluded as ``not_settled`` (ordinary right-censoring by date).
  A settled observation **must** have an outcome published by ``T``; otherwise ``MissingOutcomeError``. Excluding it
  instead would drop exactly the companies whose outcomes arrive late or never — bankruptcies, liquidations,
  delistings — and bias every training sample towards survivors. An outcome published later than its window end
  plus the grace is refused when it is added (``LateOutcomeError``): the policy does not hold for that record. A
  company whose final value takes longer to resolve (a liquidation) must be recorded within the grace with a
  conservative provisional value (``Outcome.assumed=True``, for example −100%), which forecasts report.
  Conflicting duplicate outcomes are refused (S8 L7). An outcome whose window does not match the horizon is
  refused.
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


MAX_OUTCOME_GRACE_DAYS = 90        # a hard bound: a longer "grace" turns missing failures into censoring (S8 R1)


class MissingOutcomeError(EvidenceError):
    """Training analogues whose outcomes should be observable at T but are not recorded (survivorship hazard)."""


class LateOutcomeError(EvidenceError):
    """An outcome published later than its pool's declared grace allows (the policy does not hold for it)."""


@dataclass(frozen=True)
class OutcomePolicy:
    """How long after an outcome window ends its value is published, for every company alike, and on what basis
    (the outcome source's documented publication schedule, or the rule used to build provisional values)."""
    grace_days: int
    provenance: str

    def __post_init__(self):
        if isinstance(self.grace_days, bool) or not isinstance(self.grace_days, int) \
                or not 0 <= self.grace_days <= MAX_OUTCOME_GRACE_DAYS:
            raise EquityDataError(f"outcome grace is a whole number of days from 0 to {MAX_OUTCOME_GRACE_DAYS}; a "
                                  "longer one would treat missing failed-company outcomes as censoring")
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise EquityDataError("an outcome policy states the provenance of its publication grace")


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
    assumed: bool = False            # a conservative provisional value (e.g. −100% for a liquidation still open)

    def __post_init__(self):
        if not self.start < self.end <= self.known_from:
            raise TemporalError(f"{self.company_id}: an outcome needs start < end <= known_from")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not np.isfinite(self.value):
            raise EquityDataError(f"{self.company_id}: an outcome value is a finite number")


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
    def __init__(self, outcome_policy: OutcomePolicy | None = None):
        if outcome_policy is not None and not isinstance(outcome_policy, OutcomePolicy):
            raise EquityDataError("outcome_policy must be an OutcomePolicy")
        self.outcome_policy = outcome_policy
        self._obs: list[Observation] = []
        self._out: dict[tuple, Outcome] = {}

    def add(self, o: Observation) -> None:
        if any(p.company_id == o.company_id and p.as_of == o.as_of for p in self._obs):
            raise EquityDataError(f"{o.company_id} {o.as_of}: duplicate observation")
        self._obs.append(o)

    def add_outcome(self, o: Outcome) -> None:
        key = (o.company_id, o.start)
        if key in self._out:
            if self._out[key] != o:
                raise EquityDataError(f"{o.company_id} {o.start}: a second, different outcome; outcomes are never "
                                      "overwritten (record a correction explicitly instead)")
            return
        pol = self.outcome_policy
        if pol is not None and (o.known_from - o.end).days > pol.grace_days:
            raise LateOutcomeError(f"{o.company_id} {o.start}: published {(o.known_from - o.end).days} days after its "
                                   f"window, beyond the declared grace of {pol.grace_days} ({pol.provenance}); record "
                                   "a provisional value within the grace (assumed=True) or revise the policy")
        self._out[key] = o

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
        if purpose == "training" and self.outcome_policy is None:
            raise EquityDataError("training eligibility needs the pool's OutcomePolicy (a declared, bounded grace)")
        excl = {"future": 0, "self": 0, "not_in_universe": 0, "constraint": 0, "not_settled": 0,
                "overlapping_horizon": 0}
        keep, missing = [], []
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
            elif purpose == "training" and \
                    o.as_of + timedelta(days=horizon_days + self.outcome_policy.grace_days) > T:
                excl["not_settled"] += 1                        # by the calendar, the same for every company
            elif purpose == "training" and self.outcome(o.company_id, o.as_of, T) is None:
                rec = self._out.get((o.company_id, o.as_of))
                missing.append((o.company_id, o.as_of, "not published by T" if rec is not None else "no record"))
            else:
                if purpose == "training":
                    rec = self._out[(o.company_id, o.as_of)]
                    if abs((rec.end - rec.start).days - horizon_days) > 7:
                        raise EquityDataError(f"{o.company_id} {o.as_of}: outcome window of {(rec.end - rec.start).days}"
                                              f" days, horizon {horizon_days}")
                keep.append(o)
        if missing:
            raise MissingOutcomeError(f"{len(missing)} settled observations have no outcome published by {T}: "
                                      f"{missing[:5]}; record their outcomes (with delisting returns, or a "
                                      "conservative provisional value) instead of dropping them")
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
    assumed = sum(1 for m in res.matches if pool.outcome(m.company_id, m.as_of, res.T).assumed)
    return {"forecast": float(w @ np.array(vals)), "n": len(vals), "effective_n": float(1 / np.sum(w * w)),
            "assumed_outcomes": assumed, "evidential_weight": 0}


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
