"""One replication at size HB: the hierarchical model, the tiers and the dormancy rule (SIM_PREREG section 2.5(c)).

The programme is the HB size (24 batches of 10 families). Every family gets its designated evaluation exactly
as at STD (``pipeline.evaluate_family``), and both screening candidates are run. Then, at years 2, 4, 7 and 10,
the six models of Protocol v3 section 7.2(e) are fitted to every family frozen so far, the tiers of section 8
and the dormancy rule of section 9 are stepped once (consecutive evaluation dates stand for "two consecutive
reviews"), and the numbers behind metrics M7, M8 and M9 are recorded.

Conventions fixed here where the texts leave a detail open (each is listed in the report as a deviation or an
interpretation):

- **Estimates.** ``â^H_h`` and ``θ̂^F_h`` are annualised sample Sharpe ratios of ``P_h``. A hypothesis has a
  forward estimate once its family has 63 forward days.
- **Covariances.** Standard errors come from the joint stationary bootstrap (199 resamples, one index sequence
  for the hypotheses of a batch, which share their dates). Correlations between two estimates are the sample
  correlation of the two return series over their common dates times the share of dates they have in common,
  then shrunk half-way to zero. One joint bootstrap across batches is not possible: their windows differ.
- **Mechanism classes.** Three, assigned at random at freeze: the truth has no class structure (section 2.3).
- **A review needs all six fits.** If any of the six fails the convergence gate, the review is "model not
  converged": no ``Π``, no tier change.
- **Dormancy forecast.** ``tiers.support_probability`` (a normal update of each model's posterior, not a refit).
  It is not evaluated at the programme's last date, where no future review remains.
- **Naive estimate (M9).** The largest sample Sharpe ratio among the family's variants, each over all its data
  up to the evaluation date.
- **Sampler.** 4 chains, 1,000 warm-up and 1,000 kept draws each unless ``MANHATTAN_SIM_SAMPLER`` says otherwise
  (``"warmup,draws"``); the setting is written into every replication record, and anything smaller than the
  default is a pilot setting.
"""
from __future__ import annotations

import math
import os
import time

import numpy as np

from manhattan.stats import blocklen, bootstrap, hier, screening, tiers

from . import pipeline, seeds, world

EVAL_YEARS = (2, 4, 7, 10)
MIN_FWD_DAYS = 63
N_MECH = 3
SE_RESAMPLES = 199
DEFAULT_SAMPLER = (1000, 1000)
PP_DRAWS = 200
PI_BINS = 10


def sampler_setting() -> tuple[int, int]:
    raw = os.environ.get("MANHATTAN_SIM_SAMPLER", "")
    if not raw:
        return DEFAULT_SAMPLER
    w, s = (int(x) for x in raw.split(","))
    return w, s


def eval_years() -> tuple[int, ...]:
    raw = os.environ.get("MANHATTAN_SIM_EVAL_YEARS", "")
    return tuple(int(x) for x in raw.split(",")) if raw else EVAL_YEARS


def sharpe(x: np.ndarray) -> np.ndarray:
    """Annualised sample Sharpe ratio along the last axis."""
    return x.mean(axis=-1) / x.std(axis=-1) * math.sqrt(world.YEAR)


def sharpe_se(x: np.ndarray, rng: np.random.Generator, resamples: int = SE_RESAMPLES) -> np.ndarray:
    """Bootstrap standard error of each row's annualised Sharpe ratio: one joint stationary bootstrap for all
    rows (they share their dates), with the block length of Protocol v3 section 5.2."""
    x = np.atleast_2d(x)
    n = x.shape[1]
    L = blocklen.protocol_block_length(x)
    c = bootstrap.counts(bootstrap.draw_blocks(rng, n, 1.0 / L, resamples))
    m1, m2 = c @ x.T / n, c @ (x * x).T / n
    sd = np.sqrt(np.maximum(m2 - m1 * m1, 1e-300))
    return (m1 / sd * math.sqrt(world.YEAR)).std(axis=0, ddof=1)


def overlap_correlation(series: list[np.ndarray], starts: list[int], length: int) -> np.ndarray:
    """Correlation between estimates made on windows that only partly overlap: for each pair, the sample
    correlation over common dates times the share of common dates, shrunk half-way to zero. ``series[i]`` starts
    on calendar day ``starts[i]``; ``length`` is the calendar's length."""
    k = len(series)
    Z = np.zeros((k, length))
    n = np.empty(k)
    for i, (x, s) in enumerate(zip(series, starts)):
        Z[i, s : s + x.size] = (x - x.mean()) / x.std()
        n[i] = x.size
    C = (Z @ Z.T) / np.sqrt(np.outer(n, n))
    np.fill_diagonal(C, 1.0)
    return 0.5 * C + 0.5 * np.eye(k)


class Fam:
    """What the HB pipeline keeps of one family."""

    def __init__(self, fam: world.Family, ev: pipeline.FamilyEval, mech: int, rng: np.random.Generator):
        self.idx, self.batch, self.freeze, self.mech, self.ev = fam.idx, fam.batch, fam.freeze, mech, ev
        self.true = fam.true_sharpe_f
        self.P_h = fam.X.mean(axis=1)                                   # (H, days)
        self.a_hat = sharpe(self.P_h[:, world.EXPLORE : world.HISTORY])
        self.naive, self.n_days = {}, fam.X.shape[2]
        for y in eval_years():
            t = y * world.YEAR
            if t > fam.freeze:
                self.naive[y] = float(sharpe(fam.X[:, :, : world.HISTORY + t - fam.freeze]).max())

    def forward(self, t: int) -> np.ndarray:
        return self.P_h[:, world.HISTORY : world.HISTORY + t - self.freeze]


def build_data(fams: list[Fam], t: int, se_H: dict, rng: np.random.Generator) -> tuple[hier.Data, list[Fam], dict]:
    """The model's inputs at programme day ``t`` for the families frozen before it."""
    live = [f for f in fams if f.freeze < t]
    H = live[0].P_h.shape[0]
    cal = world.HISTORY + world.T_END
    fam_idx = np.repeat(np.arange(len(live)), H)
    a_hat = np.concatenate([f.a_hat for f in live])
    sdH = np.concatenate([se_H[f.idx] for f in live])
    CH = overlap_correlation([x for f in live for x in f.P_h[:, world.EXPLORE : world.HISTORY]],
                             [f.freeze + world.EXPLORE for f in live for _ in range(H)], cal)
    fwd_fams = [i for i, f in enumerate(live) if t - f.freeze >= MIN_FWD_DAYS]
    fwd_idx, theta_hat, sdF, fser, fstart = [], [], [], [], []
    by_batch: dict = {}
    for i in fwd_fams:
        by_batch.setdefault(live[i].batch, []).append(i)
    info = {"fwd_sharpe_f": np.zeros(len(live)), "fwd_years": np.zeros(len(live))}
    for members in by_batch.values():
        x = np.concatenate([live[i].forward(t) for i in members])       # (members · H, days): one window
        se = sharpe_se(x, rng)
        est = sharpe(x)
        for j, i in enumerate(members):
            for h in range(H):
                fwd_idx.append(i * H + h); theta_hat.append(est[j * H + h]); sdF.append(se[j * H + h])
                fser.append(x[j * H + h]); fstart.append(live[i].freeze + world.HISTORY)
            pf = live[i].forward(t).mean(axis=0)
            info["fwd_sharpe_f"][i] = float(sharpe(pf))
            info["fwd_years"][i] = (t - live[i].freeze) / world.YEAR
    order = np.argsort(fwd_idx)
    fwd_idx, theta_hat, sdF = np.array(fwd_idx, int)[order], np.array(theta_hat)[order], np.array(sdF)[order]
    if fwd_idx.size:
        CF = overlap_correlation([fser[k] for k in order], [fstart[k] for k in order], cal)
        cov_F = CF * np.outer(sdF, sdF)
    else:
        cov_F = np.zeros((0, 0))
    data = hier.Data(a_hat=a_hat, cov_H=CH * np.outer(sdH, sdH), fam=fam_idx, mech=np.array([f.mech for f in live]),
                     fwd=fwd_idx, theta_hat=theta_hat, cov_F=cov_F,
                     age=np.array([(t - f.freeze) / world.YEAR for f in live]))
    return data, live, info


def fit_all(data: hier.Data, seed_base: int, sampler: tuple[int, int]) -> list[hier.Fit]:
    return [hier.fit(data, spec, seed_base + k, warmup=sampler[0], samples=sampler[1], keep_draws=PP_DRAWS)
            for k, spec in enumerate(hier.SPECS)]


def review_metrics(live: list[Fam], pi_min: np.ndarray, fit0: hier.Fit, states: dict, year: int) -> dict:
    """Counts behind M7 and M9 at one evaluation date."""
    true = np.array([f.true for f in live])
    edge = true >= world.THETA_MIN
    out = {"n_eval": len(live), "n_edge": int(edge.sum())}
    for cut in (0.80, 0.40):
        sel = pi_min >= cut
        out[f"pimin{int(cut * 100)}_n"] = int(sel.sum())
        out[f"pimin{int(cut * 100)}_true"] = int((sel & edge).sum())
    b = np.minimum((fit0.pi * PI_BINS).astype(int), PI_BINS - 1)
    out["cal_n"] = np.bincount(b, minlength=PI_BINS).tolist()
    out["cal_true"] = np.bincount(b, weights=edge, minlength=PI_BINS).tolist()
    out["cal_p"] = np.bincount(b, weights=fit0.pi, minlength=PI_BINS).tolist()
    naive = np.array([f.naive[year] for f in live])
    for cand in pipeline.CANDIDATES:
        st = [states[cand][f.idx] for f in live]
        for name, sel in (("prom", np.array([s.promising or s.supported or s.formal for s in st])),
                          ("supp", np.array([s.supported or s.formal for s in st]))):
            out[f"m9_{name}_{cand}_n"] = int(sel.sum())
            out[f"m9_{name}_{cand}_model"] = float((fit0.mean - true)[sel].sum())
            out[f"m9_{name}_{cand}_naive"] = float((naive - true)[sel].sum())
    return out


def run_replication(scenario_id: str, rep: int, *, branch: int = seeds.DEVELOPMENT, sha: str | None = None,
                    scenario: world.Scenario | None = None) -> dict:
    t0 = time.time()
    scn = scenario or world.SCENARIOS[scenario_id]
    size = world.SIZES["HB"]
    streams = seeds.Streams(sha or seeds.prereg_hash(), branch, scenario_id, "HB", rep)
    sampler, years = sampler_setting(), eval_years()
    mech_rng, est_rng = streams.rng(seeds.MODEL, 0), streams.rng(seeds.ESTIMATE)
    procs = {"i": screening.BatchBH(size.N), "ii": screening.EbhElond(size.N)}
    fams: list[Fam] = []
    se_H: dict = {}
    for _, _, batch in world.batches(scn, size, streams):
        evs = [pipeline.evaluate_family(f, streams) for f in batch]
        pipeline.decide_batch(evs, procs)
        new = [Fam(f, e, int(mech_rng.integers(N_MECH)), est_rng) for f, e in zip(batch, evs)]
        se = sharpe_se(np.concatenate([f.P_h[:, world.EXPLORE : world.HISTORY] for f in new]), est_rng)
        H = new[0].P_h.shape[0]
        for j, f in enumerate(new):
            se_H[f.idx] = se[j * H : (j + 1) * H]
        fams.extend(new)
    states = {c: {f.idx: tiers.at_freeze(f.ev.passed[c]) for f in fams} for c in pipeline.CANDIDATES}
    dormant_since = {c: {} for c in pipeline.CANDIDATES}
    dormant_days = {c: {f.idx: 0 for f in fams} for c in pipeline.CANDIDATES}
    out: dict = {"scenario": scenario_id, "size": "HB", "rep": rep, "branch": branch, "sampler": list(sampler),
                 "eval_years": list(years), "n_families": len(fams), "reviews": {}}
    for yi, year in enumerate(years):
        t = year * world.YEAR
        data, live, info = build_data(fams, t, se_H, est_rng)
        fits = fit_all(data, int(streams.seq(seeds.MODEL, 1 + yi).generate_state(1)[0]), sampler)
        rec = {"converged": [f.converged for f in fits], "rhat_max": [round(f.rhat_max, 4) for f in fits],
               "ess_min": [round(f.ess_min, 1) for f in fits], "divergences": [f.divergences for f in fits],
               "fit_seconds": [round(f.seconds, 1) for f in fits], "n_live": len(live)}
        ok = all(f.converged for f in fits)
        rec["review_ok"] = ok
        pi_min = np.min([f.pi for f in fits], axis=0) if ok else None
        gaps = [b - a for a, b in zip(years[yi:], years[yi + 1 :])]
        for cand in pipeline.CANDIDATES:
            pp_max = None
            if ok and gaps:
                st = [states[cand][f.idx] for f in live]
                pp = tiers.support_probability(
                    np.stack([f.draws for f in fits]), np.stack([f.mean for f in fits]), np.stack([f.sd for f in fits]),
                    fwd_years=info["fwd_years"], fwd_sum=info["fwd_sharpe_f"] * info["fwd_years"],
                    promising=np.array([s.promising for s in st]),
                    rw_reserve=np.array([bool(f.ev.rw_adm_any.get(cand)) for f in live]), review_gaps=gaps,
                    rng=streams.rng(seeds.MODEL, 100 + yi, pipeline.CANDIDATES.index(cand)),
                    decay_model=next((k for k, sp in enumerate(hier.SPECS) if sp.decay), None))
                pp_max = pp.max(axis=0)
            for j, f in enumerate(live):
                s = states[cand][f.idx]
                was = s.dormant
                s = tiers.step(s, tiers.Review(
                    pi_min=None if pi_min is None else float(pi_min[j]), forward_days=t - f.freeze,
                    forward_mean_positive=bool(info["fwd_sharpe_f"][j] > 0),
                    rw_reserve=bool(f.ev.rw_adm_any.get(cand)), pp_max=None if pp_max is None else float(pp_max[j])))
                states[cand][f.idx] = s
                if s.dormant and not was:
                    dormant_since[cand][f.idx] = t
                if was and not s.dormant:
                    dormant_days[cand][f.idx] += t - dormant_since[cand].pop(f.idx)
        if ok:
            rec.update(review_metrics(live, pi_min, fits[0], states, year))
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
    out["seconds"] = round(time.time() - t0, 1)
    return out
