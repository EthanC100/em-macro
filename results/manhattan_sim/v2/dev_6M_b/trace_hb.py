"""Session 6M, development experiment (outside the runner): an instrumented copy of hb_v2.run_replication that
keeps, for every family at every review, what the dormancy rule saw. Same seeds and streams as the pilot of record,
so the baseline columns reproduce it. Synthetic data only; development scenarios only.

    python trace_hb.py OUTDIR SCENARIO REP [years, comma separated]
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from scipy.stats import norm


def forecast(draws, post_mean, post_sd, *, fwd_years, fwd_sum, promising, rw_reserve, review_gaps, rng,
             decay_model, models=None, half_life=3.0):
    """tiers.support_probability with one more knob: ``models`` = the models whose smallest Π is the tier bar
    (None: all six, i.e. the rule as written). Returns PP[k, f]."""
    from manhattan.stats import tiers as T
    K, S, F = draws.shape
    gaps = np.asarray(review_gaps, dtype=float)
    out = np.zeros((K, F))
    if gaps.size == 0:
        return out
    use = np.arange(K) if models is None else np.asarray(models)
    t_end = np.cumsum(gaps)
    t_start = t_end - gaps
    prec0 = 1.0 / np.maximum(post_sd, 1e-6) ** 2
    for k in range(K):
        theta = draws[k]
        entered = np.zeros((S, F), dtype=bool)
        prom = np.broadcast_to(promising, (S, F)).copy()
        csum = np.zeros((S, F))
        for j, gap in enumerate(gaps):
            if decay_model is not None and k == decay_model:
                c = np.log(2.0) / half_life
                mean = theta * (np.exp(-c * t_start[j]) - np.exp(-c * t_end[j])) / c
            else:
                mean = theta * gap
            csum += mean + np.sqrt(gap) * rng.standard_normal((S, F))
            years = t_end[j]
            prec = prec0[:, None, :] + years
            m = (post_mean[:, None, :] * prec0[:, None, :] + csum[None, :, :]) / prec
            pi_min = norm.sf((T.THETA_MIN - m) * np.sqrt(prec))[use].min(axis=0)
            days = (fwd_years + years) * 252.0
            prom |= (pi_min >= T.PROMISING_ENTER) & (days >= T.DAYS_PROMISING)
            ok_days = days >= np.where(rw_reserve, T.DAYS_SUPPORTED_RW, T.DAYS_SUPPORTED)
            entered |= prom & (pi_min >= T.SUPPORTED_ENTER) & ((fwd_sum + csum) > 0) & ok_days
        out[k] = entered.mean(axis=0)
    return out


def trace(scenario_id: str, rep: int, years: tuple) -> dict:
    os.environ["MANHATTAN_SIM_EVAL_YEARS"] = ",".join(str(y) for y in years)
    from manhattan.sim import hb, hb_v2, pipeline, seeds, world
    from manhattan.stats import hier_analytic, screening, tiers
    t0 = time.time()
    scn = world.SCENARIOS[scenario_id]
    size = world.SIZES["HB"]
    streams = seeds.Streams(seeds.prereg_hash(), seeds.DEVELOPMENT, scenario_id, "HB", rep)
    mech_rng, est_rng = streams.rng(seeds.MODEL, 0), streams.rng(seeds.ESTIMATE)
    procs = {"i": screening.BatchBH(size.N), "ii": screening.EbhElond(size.N)}
    fams, se_H = [], {}
    for _, _, batch in world.batches(scn, size, streams):
        evs = [pipeline.evaluate_family(f, streams) for f in batch]
        pipeline.decide_batch(evs, procs)
        new = [hb_v2.Fam(f, e, int(mech_rng.integers(hb.N_MECH)), est_rng) for f, e in zip(batch, evs)]
        se = hb.sharpe_se(np.stack([f.P_f[world.EXPLORE: world.HISTORY] for f in new]), est_rng)
        for j, f in enumerate(new):
            se_H[f.idx] = float(se[j])
        fams.extend(new)
    cand = "i"
    states = {f.idx: tiers.at_freeze(f.ev.passed[cand]) for f in fams}
    dormant_since, dormant_days = {}, {f.idx: 0 for f in fams}
    decay = next((k for k, sp in enumerate(hier_analytic.SPECS) if sp.decay), None)
    out = {"scenario": scenario_id, "rep": rep, "years": list(years),
           "fam": {f.idx: {"freeze": f.freeze, "true": f.true, "passed": bool(f.ev.passed[cand]),
                           "rw": bool(f.ev.rw_adm_any.get(cand)), "y_H": f.y_H, "s_H": se_H[f.idx]} for f in fams},
           "reviews": {}}
    for yi, year in enumerate(years):
        t = year * world.YEAR
        data, live, info = hb_v2.build_data(fams, t, se_H, est_rng)
        fits = hier_analytic.fit_many(data, draws=hb.PP_DRAWS,
                                      seed=int(streams.seq(seeds.MODEL, 1 + yi).generate_state(1)[0]))
        assert all(f.ok for f in fits)
        pis = np.array([f.pi for f in fits])
        pi_min = pis.min(axis=0)
        gaps = [b - a for a, b in zip(years[yi:], years[yi + 1:])]
        rec = {"idx": [f.idx for f in live], "pi": np.round(pis, 4).tolist(),
               "mean": np.round([f.mean for f in fits], 4).tolist(), "sd": np.round([f.sd for f in fits], 4).tolist(),
               "y_F": np.round(np.nan_to_num(data.y_F, nan=-99.0), 4).tolist(), "s_F": np.round(data.s_F, 4).tolist(),
               "fwd_years": np.round(info["fwd_years"], 4).tolist(), "r_F": info["r_F"],
               "hyper": [f.hyper for f in fits]}
        pp_max = None
        if gaps:
            st = [states[f.idx] for f in live]
            common = dict(fwd_years=info["fwd_years"], fwd_sum=info["fwd_sharpe_f"] * info["fwd_years"],
                          promising=np.array([s.promising for s in st]),
                          rw_reserve=np.array([bool(f.ev.rw_adm_any.get(cand)) for f in live]))
            D, M, SD = (np.stack([getattr(f, a) for f in fits]) for a in ("draws", "mean", "sd"))
            pp = tiers.support_probability(D, M, SD, review_gaps=gaps, decay_model=decay,
                                           rng=streams.rng(seeds.MODEL, 100 + yi, 0), **common)
            pp_max = pp.max(axis=0)
            rec["pp"] = np.round(pp, 4).tolist()
            # the same forecast with other assumption sets and horizons, each on its own stream
            alt = lambda tag, **kw: np.round(forecast(D, M, SD, decay_model=decay,
                                                      rng=np.random.default_rng([rep, yi, sum(tag.encode())]),
                                                      **{**common, **kw}), 4).tolist()
            rec["pp_s0bar"] = alt("s0bar", review_gaps=gaps, models=[0])                # tier bar on the central model
            rec["pp_no_s5"] = alt("no_s5", review_gaps=gaps, models=[0, 1, 2, 3, 4])    # bar without the decay model
            rec["pp_no_s45"] = alt("no_s45", review_gaps=gaps, models=[0, 1, 2, 3])
            rec["pp_long"] = alt("long", review_gaps=gaps + [3, 3, 4])                  # ten more years of reviews
            rec["pp_long_s0bar"] = alt("long_s0bar", review_gaps=gaps + [3, 3, 4], models=[0])
        flags = []
        for j, f in enumerate(live):
            s = states[f.idx]
            was = s.dormant
            s = tiers.step(s, tiers.Review(
                pi_min=float(pi_min[j]), forward_days=t - f.freeze, forward_mean_positive=bool(info["fwd_sharpe_f"][j] > 0),
                rw_reserve=bool(f.ev.rw_adm_any.get(cand)), pp_max=None if pp_max is None else float(pp_max[j])))
            states[f.idx] = s
            if s.dormant and not was:
                dormant_since[f.idx] = t
            if was and not s.dormant:
                dormant_days[f.idx] += t - dormant_since.pop(f.idx)
            flags.append([int(s.promising), int(s.supported), int(s.dormant)])
        rec["state"] = flags
        rec["fwd_pos"] = [bool(x > 0) for x in info["fwd_sharpe_f"]]
        out["reviews"][str(year)] = rec
    end = world.T_END
    for idx, since in dormant_since.items():
        dormant_days[idx] += end - since
    edge = [f for f in fams if f.true >= world.THETA_MIN]
    gone = [f for f in edge if states[f.idx].dormant or dormant_days[f.idx] > 0.5 * (end - f.freeze)]
    out["m8_den_i"], out["m8_num_i"] = len(edge), len(gone)
    out["dormant_days"] = dormant_days
    out["seconds"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    outdir, scenario, rep = sys.argv[1], sys.argv[2], int(sys.argv[3])
    years = tuple(int(x) for x in sys.argv[4].split(",")) if len(sys.argv) > 4 else (2, 4, 7, 10)
    tag = "" if years == (2, 4, 7, 10) else "_y" + "-".join(str(y) for y in years)
    path = os.path.join(outdir, f"{scenario}_{rep}{tag}.json")
    if not os.path.exists(path):
        r = trace(scenario, rep, years)
        with open(path, "w") as f:
            json.dump(r, f)
        print(scenario, rep, tag, r["m8_num_i"], r["m8_den_i"], r["seconds"], flush=True)
