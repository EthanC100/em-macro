"""SIM_PREREG_v2, the model-fitting half: one replication at size HB with the analytic hierarchical model of
Protocol v3.1 section 7 (``manhattan.stats.hier_analytic``) in place of the sampled model of v3.0.

Everything around the model is version 1's (``manhattan/sim/hb.py``, imported, not copied): the HB programme
(24 batches of 10 families), the designated evaluation of every family and both screening candidates, the
evaluation dates (years 2, 4, 7 and 10), the tier state machine, the dormancy forecast and the counts behind
metrics M7, M8 and M9. The dormancy rule is Protocol v3.1 section 9.1 (``manhattan.stats.dormancy``).

What differs, each listed in the report:

- **Estimates are of the family portfolio.** ``y^H_f`` and ``y^F_f`` are annualised sample Sharpe ratios of
  ``P_f`` on the reserve window and on the forward record (63 forward days at least). The truth they are judged
  against is the family portfolio's true forward Sharpe ratio (SIM_PREREG section 2.4), which is what ``θ_f``
  now is.
- **Standard errors** come from the joint stationary bootstrap of version 1 (199 resamples, one index sequence
  for the families of a batch).
- **Dependence between families** enters as one number, ``r``: the average sampling correlation between the
  forward estimates of different families (``common_share``: for each pair, the sample correlation of the two
  return series over their common dates times the share of dates they have in common, as version 1 computed
  it, averaged over all pairs, not shrunk, floored at 0). The model gives every forward estimate one common
  shock carrying that share of its variance. No other covariance is passed.
- **No convergence gate.** A fit is a deterministic computation. It is used unless more than 1% of the
  posterior mass of ``μ_A`` sits on the ends of its grid (``hier_analytic.EDGE_MASS_MAX``); a review needs all
  six fits, as before.
- **Dormancy forecast.** ``tiers.support_probability`` as in version 1, fed with 200 draws of ``θ_f`` from
  each model's closed-form posterior.
- **Dormancy rule.** Protocol v3.1 section 9.1 as revised before adoption: a family becomes dormant when, at
  two consecutive evaluation dates with at least 252 forward days each, both the forecast ``PP^max`` and
  ``Π^max`` (the largest of the six models' probabilities of an edge of at least ``θ_min``) are below 0.05; it
  is reactivated when either is at least 0.15. At the last date there is no forecast, so no family becomes
  dormant there; a dormant family can still be reactivated there by ``Π^max``.
- **Kept for the report, not used by any rule:** how many families are dormant after each date and how many
  reviews are written (a family that is dormant and stays so needs none), and for every family with a true
  edge its true Sharpe ratio, its freeze day and the first date at which it was Statistically supported.
- **Channels.** Every family of these scenarios is a blind family with a designated evaluation, so every
  reserve estimate has evidential weight 1. The weight is computed by the model from the channel
  (``hier_analytic.Data.reserve_weight``), never passed in.
"""
from __future__ import annotations

import time

import numpy as np

from manhattan.stats import dormancy, hier_analytic, screening, tiers

from . import hb, pipeline, seeds, world

MODEL = "analytic-normal-normal-3.1"


class Fam(hb.Fam):
    """Version 1's record of a family, plus its family portfolio."""

    def __init__(self, fam: world.Family, ev: pipeline.FamilyEval, mech: int, rng: np.random.Generator):
        super().__init__(fam, ev, mech, rng)
        self.P_f = self.P_h.mean(axis=0)                                # (days,)
        self.y_H = float(hb.sharpe(self.P_f[world.EXPLORE : world.HISTORY]))

    def forward_f(self, t: int) -> np.ndarray:
        return self.P_f[world.HISTORY : world.HISTORY + t - self.freeze]


def common_share(series: list[np.ndarray], starts: list[int], length: int) -> float:
    """The average sampling correlation between estimates made on windows that only partly overlap: for each
    pair, the sample correlation of the two series over their common dates times the share of common dates
    (``hb.overlap_correlation`` without its shrinkage), averaged over all pairs and floored at 0. With
    ``w_i`` = the standardised series ``i`` divided by ``√n_i`` and placed on the calendar, the sum over all
    pairs is ``‖Σ w_i‖² − k``."""
    k = len(series)
    if k < 2:
        return 0.0
    total = np.zeros(length)
    for x, s in zip(series, starts):
        sd = x.std()
        if sd > 0:
            total[s : s + x.size] += (x - x.mean()) / (sd * np.sqrt(x.size))
    return float(min(max((total @ total - k) / (k * (k - 1)), 0.0), hier_analytic.R_F_MAX))


def build_data(fams: list[Fam], t: int, se_H: dict, rng: np.random.Generator):
    """The model's inputs at programme day ``t`` for the families frozen before it."""
    live = [f for f in fams if f.freeze < t]
    n = len(live)
    y_F, s_F = np.full(n, np.nan), np.ones(n)
    info = {"fwd_sharpe_f": np.zeros(n), "fwd_years": np.zeros(n)}
    by_batch: dict = {}
    for i, f in enumerate(live):
        if t - f.freeze >= hb.MIN_FWD_DAYS:
            by_batch.setdefault(f.batch, []).append(i)
    for members in by_batch.values():
        x = np.stack([live[i].forward_f(t) for i in members])           # one window: the batch shares its dates
        est, se = hb.sharpe(x), hb.sharpe_se(x, rng)
        for j, i in enumerate(members):
            y_F[i], s_F[i] = est[j], se[j]
            info["fwd_sharpe_f"][i] = est[j]
            info["fwd_years"][i] = (t - live[i].freeze) / world.YEAR
    has = [i for members in by_batch.values() for i in members]
    info["r_F"] = common_share([live[i].forward_f(t) for i in has], [live[i].freeze + world.HISTORY for i in has],
                               world.HISTORY + world.T_END)
    data = hier_analytic.Data(
        y_H=np.array([f.y_H for f in live]), s_H=np.array([se_H[f.idx] for f in live]), y_F=y_F, s_F=s_F,
        mech=np.array([f.mech for f in live]), age=np.array([(t - f.freeze) / world.YEAR for f in live]),
        channel=np.full(n, "blind"), designated=np.ones(n, dtype=bool), r_F=info["r_F"])
    return data, live, info


def run_replication(scenario_id: str, rep: int, *, branch: int = seeds.DEVELOPMENT, sha: str | None = None,
                    scenario: world.Scenario | None = None) -> dict:
    t0 = time.time()
    scn = scenario or world.SCENARIOS[scenario_id]
    size = world.SIZES["HB"]
    streams = seeds.Streams(sha or seeds.prereg_hash(), branch, scenario_id, "HB", rep)
    years = hb.eval_years()
    mech_rng, est_rng = streams.rng(seeds.MODEL, 0), streams.rng(seeds.ESTIMATE)
    procs = {"i": screening.BatchBH(size.N), "ii": screening.EbhElond(size.N)}
    fams: list[Fam] = []
    se_H: dict = {}
    for _, _, batch in world.batches(scn, size, streams):
        evs = [pipeline.evaluate_family(f, streams) for f in batch]
        pipeline.decide_batch(evs, procs)
        new = [Fam(f, e, int(mech_rng.integers(hb.N_MECH)), est_rng) for f, e in zip(batch, evs)]
        se = hb.sharpe_se(np.stack([f.P_f[world.EXPLORE : world.HISTORY] for f in new]), est_rng)
        for j, f in enumerate(new):
            se_H[f.idx] = float(se[j])
        fams.extend(new)
    t_eval = time.time()
    states = {c: {f.idx: tiers.at_freeze(f.ev.passed[c]) for f in fams} for c in pipeline.CANDIDATES}
    dormant_since = {c: {} for c in pipeline.CANDIDATES}
    dormant_days = {c: {f.idx: 0 for f in fams} for c in pipeline.CANDIDATES}
    first_supported = {c: {} for c in pipeline.CANDIDATES}            # for the report: the date a family entered the tier
    out: dict = {"scenario": scenario_id, "size": "HB", "rep": rep, "branch": branch, "model": MODEL,
                 "eval_years": list(years), "n_families": len(fams), "reviews": {}}
    for yi, year in enumerate(years):
        t = year * world.YEAR
        data, live, info = build_data(fams, t, se_H, est_rng)
        t_fit = time.time()
        fits = hier_analytic.fit_many(data, draws=hb.PP_DRAWS,
                                      seed=int(streams.seq(seeds.MODEL, 1 + yi).generate_state(1)[0]))
        rec = {"ok": [f.ok for f in fits], "edge_mass": [round(f.edge_mass, 6) for f in fits],
               "fit_seconds": [round(f.seconds, 3) for f in fits], "six_fits_seconds": round(time.time() - t_fit, 3),
               "grid_points": [f.grid_points for f in fits], "n_live": len(live), "r_F": round(info["r_F"], 4),
               "hyper": {k: round(v, 4) for k, v in fits[0].hyper.items()}}
        ok = all(f.ok for f in fits)
        rec["review_ok"] = ok
        pi_min = np.min([f.pi for f in fits], axis=0) if ok else None
        pi_max = np.max([f.pi for f in fits], axis=0) if ok else None
        gaps = [b - a for a, b in zip(years[yi:], years[yi + 1 :])]
        for cand in pipeline.CANDIDATES:
            pp_max, written = None, 0
            if ok and gaps:
                st = [states[cand][f.idx] for f in live]
                pp = tiers.support_probability(
                    np.stack([f.draws for f in fits]), np.stack([f.mean for f in fits]), np.stack([f.sd for f in fits]),
                    fwd_years=info["fwd_years"], fwd_sum=info["fwd_sharpe_f"] * info["fwd_years"],
                    promising=np.array([s.promising for s in st]),
                    rw_reserve=np.array([bool(f.ev.rw_adm_any.get(cand)) for f in live]), review_gaps=gaps,
                    rng=streams.rng(seeds.MODEL, 100 + yi, pipeline.CANDIDATES.index(cand)),
                    decay_model=next((k for k, sp in enumerate(hier_analytic.SPECS) if sp.decay), None))
                pp_max = pp.max(axis=0)
            for j, f in enumerate(live):
                s = states[cand][f.idx]
                was = s.dormant
                s = dormancy.step(s, tiers.Review(
                    pi_min=None if pi_min is None else float(pi_min[j]), forward_days=t - f.freeze,
                    forward_mean_positive=bool(info["fwd_sharpe_f"][j] > 0),
                    rw_reserve=bool(f.ev.rw_adm_any.get(cand)), pp_max=None if pp_max is None else float(pp_max[j])),
                    None if pi_max is None else float(pi_max[j]))
                states[cand][f.idx] = s
                if s.dormant and not was:
                    dormant_since[cand][f.idx] = t
                if was and not s.dormant:
                    dormant_days[cand][f.idx] += t - dormant_since[cand].pop(f.idx)
                written += not (was and s.dormant)                     # dormant before and after: no review write-up
                if s.supported:
                    first_supported[cand].setdefault(f.idx, year)
            rec[f"written_{cand}"] = int(written)
            rec[f"dormant_{cand}"] = int(sum(states[cand][f.idx].dormant for f in live))
        if ok:
            rec.update(hb.review_metrics(live, pi_min, fits[0], states, year))
            # for the report only: among families with a true edge, which model is the most cautious, and how
            # far the most cautious and the most hopeful are from the central one
            edge = np.array([f.true >= world.THETA_MIN for f in live])
            pis = np.array([f.pi for f in fits])
            rec["binding_edge"] = np.bincount(np.argmin(pis[:, edge], axis=0), minlength=len(fits)).tolist()
            rec["pi_edge_sum"] = [float(pi_min[edge].sum()), float(fits[0].pi[edge].sum()), float(pis.max(axis=0)[edge].sum())]
            for cand in pipeline.CANDIDATES:
                st = [states[cand][f.idx] for f in live]
                rec[f"edge_dormant_{cand}"] = int(sum(s.dormant for s, e in zip(st, edge) if e))
                rec[f"edge_supported_{cand}"] = int(sum(s.supported for s, e in zip(st, edge) if e))
        out["reviews"][str(year)] = rec
    end = world.T_END
    for cand in pipeline.CANDIDATES:
        for idx, since in dormant_since[cand].items():
            dormant_days[cand][idx] += end - since
        edge = [f for f in fams if f.true >= world.THETA_MIN]
        gone = [f for f in edge if states[cand][f.idx].dormant or dormant_days[cand][f.idx] > 0.5 * (end - f.freeze)]
        st = list(states[cand].values())
        out[f"m8_den_{cand}"] = len(edge)
        out[f"m8_num_{cand}"] = len(gone)
        out[f"end_promising_{cand}"] = sum(s.promising for s in st)
        out[f"end_supported_{cand}"] = sum(s.supported for s in st)
        out[f"end_dormant_{cand}"] = sum(s.dormant for s in st)
        out[f"screened_{cand}"] = sum(f.ev.passed[cand] for f in fams)
        out[f"null_dormant_{cand}"] = sum(states[cand][f.idx].dormant for f in fams if f.true < world.THETA_MIN)
        out[f"written_{cand}"] = sum(v[f"written_{cand}"] for v in out["reviews"].values())
        out[f"edge_first_supported_{cand}"] = [int(first_supported[cand].get(f.idx, 0)) for f in edge]
        out[f"edge_dormant_end_{cand}"] = [int(states[cand][f.idx].dormant) for f in edge]
    edge = [f for f in fams if f.true >= world.THETA_MIN]
    out["edge_true"] = [round(float(f.true), 4) for f in edge]
    out["edge_freeze"] = [int(f.freeze) for f in edge]
    out["family_reviews"] = sum(v["n_live"] for v in out["reviews"].values())
    out["dormancy"] = dormancy.RULE
    out["model_seconds"] = round(time.time() - t_eval, 2)
    out["seconds"] = round(time.time() - t0, 1)
    return out
