"""SIM_PREREG_v2, the model-fitting half: one replication at size HB with the analytic hierarchical model of
Protocol v3.1 section 7 (``manhattan.stats.hier_analytic``) in place of the sampled model of v3.0.

Everything around the model is version 1's (``manhattan/sim/hb.py``, imported, not copied): the HB programme
(24 batches of 10 families), the designated evaluation of every family and both screening candidates, the
evaluation dates (years 2, 4, 7 and 10), the tier state machine, the dormancy forecast and the counts behind
metrics M7, M8 and M9.

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
- **Dormancy rule.** That of Protocol v3.1 section 9.1 as revised before adoption (``manhattan.stats.dormancy``):
  the forecast below 0.05 **and** the family's own forward record against an edge of ``θ_min`` (one-sided
  ``p^F`` below 0.05, at least 252 forward days), both at two consecutive evaluation dates; reactivation when
  either is at or above 0.15. At the last date there is no forecast, so no family becomes dormant there, and a
  dormant family can still be reactivated by its forward record.
- **Two shadow paths, for diagnostics only.** On the same fits, the tier state machine is also stepped with the
  dormancy rule of 3.0 (the forecast alone, on the random stream the pilot of session 5M used, so that it
  reproduces that pilot) and with no dormancy at all. They decide nothing and feed no criterion: they give what
  the revision costs in attention, the delays dormancy causes to tier entry, and what reactivation does.
- **Channels.** Every family of these scenarios is a blind family with a designated evaluation, so every
  reserve estimate has evidential weight 1. The weight is computed by the model from the channel
  (``hier_analytic.Data.reserve_weight``), never passed in.
"""
from __future__ import annotations

import time
from dataclasses import replace

import numpy as np

from manhattan.stats import dormancy, hier_analytic, screening, tiers

from . import hb, pipeline, seeds, world

MODEL = "analytic-normal-normal-3.1"
RULES = ("v31", "v30", "none")          # the rule of record; the rule of 3.0 and no dormancy, as shadows
FORECAST_STREAM = {"v31": 300, "v30": 100}      # 100 is the stream of session 5M's pilot, kept for the 3.0 shadow


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


class Track:
    """One screening candidate's tiers and dormancy under one dormancy rule: ``"v31"`` (Protocol 3.1 section
    9.1, the rule of record), ``"v30"`` (the forecast alone) or ``"none"``."""

    def __init__(self, rule: str, cand: str, fams: list[Fam]):
        self.rule, self.cand = rule, cand
        self.state = {f.idx: tiers.at_freeze(f.ev.passed[cand]) for f in fams}
        self.since: dict = {}                               # family -> day it became dormant (while dormant)
        self.days = {f.idx: 0 for f in fams}                # dormant days so far
        self.ever: set = set()
        self.woken: dict = {}                               # family -> number of reactivations
        self.entry: dict = {}                               # family -> day it first was Statistically supported
        self.written = self.possible = 0                    # family-reviews with a write-up; family-reviews in all
        self.gate = [0, 0, 0, 0]                            # both low / forecast only / forward record only / neither
        self.dormant_at_last: set = set()

    def review(self, f: Fam, t: int, rev: tiers.Review, p_forward: float, last: bool) -> None:
        s = self.state[f.idx]
        was = s.dormant
        if last and was:
            self.dormant_at_last.add(f.idx)
        if self.rule == "v31":
            if not was and not s.supported and rev.pp_max is not None and rev.pi_min is not None:
                self.gate[(0 if p_forward < dormancy.DORMANT_BELOW else 1) if rev.pp_max < dormancy.DORMANT_BELOW
                          else (2 if p_forward < dormancy.DORMANT_BELOW else 3)] += 1
            s = dormancy.step(s, rev, p_forward)
        elif self.rule == "v30":
            s = tiers.step(s, rev)
        else:
            s = tiers.step(s, replace(rev, pp_max=None))
        self.state[f.idx] = s
        self.possible += 1
        self.written += 0 if (was and s.dormant) else 1     # a dormant family gets the reactivation check only
        if s.dormant and not was:
            self.since[f.idx] = t
            self.ever.add(f.idx)
        if was and not s.dormant:
            self.days[f.idx] += t - self.since.pop(f.idx)
            self.woken[f.idx] = self.woken.get(f.idx, 0) + 1
        if s.supported and f.idx not in self.entry:
            self.entry[f.idx] = t

    def close(self, end: int) -> None:
        for idx, since in self.since.items():
            self.days[idx] += end - since
        self.since = {}

    def gone(self, f: Fam, end: int) -> bool:
        """Metric M8's numerator (SIM_PREREG section 4): dormant at the end, or for more than half its forward life."""
        return bool(self.state[f.idx].dormant or self.days[f.idx] > 0.5 * (end - f.freeze))

    def summary(self, fams: list[Fam], end: int, none: "Track | None" = None) -> dict:
        """Diagnostics only (no criterion reads them). ``none`` is the path without dormancy on the same fits."""
        edge = [f for f in fams if f.true >= world.THETA_MIN]
        null = [f for f in fams if f.true < world.THETA_MIN]
        share = lambda f: self.days[f.idx] / (end - f.freeze)
        out = {"m8_num": sum(self.gone(f, end) for f in edge), "m8_den": len(edge), "n_null": len(null),
               "edge_ever_dormant": sum(f.idx in self.ever for f in edge),
               "null_ever_dormant": sum(f.idx in self.ever for f in null),
               "edge_end_dormant": sum(self.state[f.idx].dormant for f in edge),
               "null_end_dormant": sum(self.state[f.idx].dormant for f in null),
               "edge_dormant_at_last": sum(f.idx in self.dormant_at_last for f in edge),
               # M8's numerator had nothing been able to wake at the last date
               "m8_num_no_last_wake": sum(f.idx in self.dormant_at_last or self.gone(f, end) for f in edge),
               "edge_dormant_share": [round(share(f), 4) for f in edge if f.idx in self.ever],
               "null_dormant_share_sum": round(sum(share(f) for f in null if f.idx in self.ever), 4),
               "edge_reactivations": sum(self.woken.get(f.idx, 0) for f in edge),
               "null_reactivations": sum(self.woken.get(f.idx, 0) for f in null),
               "edge_woken": sum(f.idx in self.woken for f in edge),
               "edge_woken_supported": sum(f.idx in self.woken and self.state[f.idx].supported for f in edge),
               "edge_woken_end_dormant": sum(f.idx in self.woken and self.state[f.idx].dormant for f in edge),
               "null_woken": sum(f.idx in self.woken for f in null),
               "null_woken_end_dormant": sum(f.idx in self.woken and self.state[f.idx].dormant for f in null),
               "reviews_written": self.written, "reviews_possible": self.possible,
               "edge_supported_ever": sum(f.idx in self.entry for f in edge),
               "edge_entry_years": [round((self.entry[f.idx] - f.freeze) / world.YEAR, 3) for f in edge if f.idx in self.entry]}
        if self.rule == "v31":
            out["gate"] = list(self.gate)
        if none is not None:        # what dormancy did to tier entry, against the same fits without dormancy
            both = [f for f in edge if f.idx in none.entry and f.idx in self.entry]
            out["edge_entry_delay_years"] = [round((self.entry[f.idx] - none.entry[f.idx]) / world.YEAR, 3) for f in both]
            out["edge_entry_lost"] = sum(f.idx in none.entry and f.idx not in self.entry for f in edge)
            out["edge_entry_without_dormancy"] = sum(f.idx in none.entry for f in edge)
            # one row per family with a true edge, for the table of tier entry against the true Sharpe ratio:
            # true Sharpe, freeze day, day of first entry under this rule and with no dormancy (−1: never)
            out["edge_families"] = [[round(f.true, 3), f.freeze, self.entry.get(f.idx, -1), none.entry.get(f.idx, -1)]
                                    for f in edge]
        return out


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
    tracks = {c: {rule: Track(rule, c, fams) for rule in RULES} for c in pipeline.CANDIDATES}
    states = {c: tracks[c]["v31"].state for c in pipeline.CANDIDATES}       # the path of record
    decay = next((k for k, sp in enumerate(hier_analytic.SPECS) if sp.decay), None)
    forecast_seconds = 0.0
    out: dict = {"scenario": scenario_id, "size": "HB", "rep": rep, "branch": branch, "model": MODEL,
                 "dormancy": "3.1", "eval_years": list(years), "n_families": len(fams), "reviews": {}}
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
        gaps = [b - a for a, b in zip(years[yi:], years[yi + 1 :])]
        days = np.array([t - f.freeze for f in live])
        p_fwd = dormancy.forward_p(data.y_F, data.s_F, days)             # the family's own forward record: no model
        for ci, cand in enumerate(pipeline.CANDIDATES):
            rw = np.array([bool(f.ev.rw_adm_any.get(cand)) for f in live])
            for rule in RULES:
                tr = tracks[cand][rule]
                pp_max = None
                if ok and gaps and rule in FORECAST_STREAM:
                    t_pp = time.time()
                    pp = tiers.support_probability(
                        np.stack([f.draws for f in fits]), np.stack([f.mean for f in fits]), np.stack([f.sd for f in fits]),
                        fwd_years=info["fwd_years"], fwd_sum=info["fwd_sharpe_f"] * info["fwd_years"],
                        promising=np.array([tr.state[f.idx].promising for f in live]), rw_reserve=rw, review_gaps=gaps,
                        rng=streams.rng(seeds.MODEL, FORECAST_STREAM[rule] + yi, ci), decay_model=decay)
                    pp_max = pp.max(axis=0)
                    forecast_seconds += time.time() - t_pp
                for j, f in enumerate(live):
                    tr.review(f, t, tiers.Review(
                        pi_min=None if pi_min is None else float(pi_min[j]), forward_days=int(days[j]),
                        forward_mean_positive=bool(info["fwd_sharpe_f"][j] > 0), rw_reserve=bool(rw[j]),
                        pp_max=None if pp_max is None else float(pp_max[j])), float(p_fwd[j]), last=not gaps)
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
    out["diag"] = {}
    for cand in pipeline.CANDIDATES:
        for tr in tracks[cand].values():
            tr.close(end)
        main, none = tracks[cand]["v31"], tracks[cand]["none"]
        edge = [f for f in fams if f.true >= world.THETA_MIN]
        st = list(states[cand].values())
        out[f"m8_den_{cand}"] = len(edge)
        out[f"m8_num_{cand}"] = sum(main.gone(f, end) for f in edge)
        out[f"end_promising_{cand}"] = sum(s.promising for s in st)
        out[f"end_supported_{cand}"] = sum(s.supported for s in st)
        out[f"end_dormant_{cand}"] = sum(s.dormant for s in st)
        out[f"screened_{cand}"] = sum(f.ev.passed[cand] for f in fams)
        out["diag"][cand] = {rule: tracks[cand][rule].summary(fams, end, None if rule == "none" else none) for rule in RULES}
        out["diag"][cand]["v30"]["end_dormant"] = sum(s.dormant for s in tracks[cand]["v30"].state.values())
    out["forecast_seconds"] = round(forecast_seconds, 2)
    out["model_seconds"] = round(time.time() - t_eval, 2)
    out["seconds"] = round(time.time() - t0, 1)
    return out
