"""Session "6M Manhattan C: dormancy fix and statistical checks", development experiment (outside the runner):
one HB replication of the branch's pipeline with the tier state machine stepped four ways on the **same fits**:

    branch   Protocol 3.1 section 9.1 as it stands on build/manhattan (the forecast and Π^max; manhattan.stats.dormancy)
    v30      the rule of 3.0 (the forecast alone; manhattan.stats.tiers)
    own      an alternative, not adopted: the forecast and the family's own forward record (own_record.py, beside this file)
    none     no dormancy

Same seeds, worlds, fits and forecast stream as ``manhattan.sim.hb_v2.run_replication``, which is imported and not
edited; the ``branch`` path reproduces the pilot of record replication by replication, and ``v30`` session 5M's.
Synthetic data only; development scenarios only. It writes one JSON file per replication and nothing else.

    python paths.py OUTDIR SCENARIO REP [years, comma separated; default 2,4,7,10]

What it keeps, per path, are the diagnostics the pilot's records do not hold: families with a true edge ever made
dormant, how long they were dormant, what reactivation did, the delay dormancy caused to tier entry, and the
reviews written.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = ("branch", "v30", "own", "none")


class Track:
    """Candidate (i)'s tiers and dormancy under one rule."""

    def __init__(self, rule, fams, tiers):
        self.rule = rule
        self.state = {f.idx: tiers.at_freeze(f.ev.passed["i"]) for f in fams}
        self.since, self.days = {}, {f.idx: 0 for f in fams}
        self.ever, self.woken, self.entry = set(), {}, {}
        self.written = self.possible = 0
        self.dormant_at_last = set()
        self.by_year = {}                                       # review year -> [dormant with an edge, dormant with none]

    def review(self, f, t, rev, pi_max, p_forward, last, mods):
        tiers, dormancy, own_record = mods
        s = self.state[f.idx]
        was = s.dormant
        if last and was:
            self.dormant_at_last.add(f.idx)
        if self.rule == "branch":
            s = dormancy.step(s, rev, pi_max)
        elif self.rule == "v30":
            s = tiers.step(s, rev)
        elif self.rule == "own":
            s = own_record.step(s, rev, p_forward)
        else:
            s = tiers.step(s, replace(rev, pp_max=None))
        self.state[f.idx] = s
        self.possible += 1
        self.written += 0 if (was and s.dormant) else 1
        if s.dormant and not was:
            self.since[f.idx] = t
            self.ever.add(f.idx)
        if was and not s.dormant:
            self.days[f.idx] += t - self.since.pop(f.idx)
            self.woken[f.idx] = self.woken.get(f.idx, 0) + 1
        if s.supported and f.idx not in self.entry:
            self.entry[f.idx] = t

    def close(self, end):
        for idx, since in self.since.items():
            self.days[idx] += end - since
        self.since = {}

    def gone(self, f, end):
        return bool(self.state[f.idx].dormant or self.days[f.idx] > 0.5 * (end - f.freeze))

    def summary(self, fams, end, none, theta_min):
        edge = [f for f in fams if f.true >= theta_min]
        null = [f for f in fams if f.true < theta_min]
        share = lambda f: self.days[f.idx] / (end - f.freeze)
        out = {"m8_num": sum(self.gone(f, end) for f in edge), "m8_den": len(edge), "n_null": len(null),
               "end_dormant": sum(s.dormant for s in self.state.values()),
               "edge_ever_dormant": sum(f.idx in self.ever for f in edge),
               "null_ever_dormant": sum(f.idx in self.ever for f in null),
               "edge_end_dormant": sum(self.state[f.idx].dormant for f in edge),
               "null_end_dormant": sum(self.state[f.idx].dormant for f in null),
               "m8_num_no_last_wake": sum(f.idx in self.dormant_at_last or self.gone(f, end) for f in edge),
               "edge_dormant_share": [round(share(f), 4) for f in edge if f.idx in self.ever],
               "edge_dormant_years": [round(self.days[f.idx] / 252.0, 3) for f in edge if f.idx in self.ever],
               "edge_ever_true": [round(f.true, 3) for f in edge if f.idx in self.ever],
               "null_dormant_share_sum": round(sum(share(f) for f in null if f.idx in self.ever), 4),
               "null_dormant_years_sum": round(sum(self.days[f.idx] / 252.0 for f in null if f.idx in self.ever), 3),
               "edge_reactivations": sum(self.woken.get(f.idx, 0) for f in edge),
               "null_reactivations": sum(self.woken.get(f.idx, 0) for f in null),
               "edge_woken": sum(f.idx in self.woken for f in edge),
               "edge_woken_supported": sum(f.idx in self.woken and self.state[f.idx].supported for f in edge),
               "edge_woken_promising": sum(f.idx in self.woken and self.state[f.idx].promising for f in edge),
               "edge_woken_end_dormant": sum(f.idx in self.woken and self.state[f.idx].dormant for f in edge),
               "null_woken": sum(f.idx in self.woken for f in null),
               "null_woken_end_dormant": sum(f.idx in self.woken and self.state[f.idx].dormant for f in null),
               "reviews_written": self.written, "reviews_possible": self.possible,
               "edge_supported_ever": sum(f.idx in self.entry for f in edge),
               "edge_supported_end": sum(self.state[f.idx].supported for f in edge),
               "edge_families": [[round(f.true, 3), f.freeze, self.entry.get(f.idx, -1), none.entry.get(f.idx, -1)] for f in edge],
               "by_year": self.by_year}
        both = [f for f in edge if f.idx in none.entry and f.idx in self.entry]
        out["edge_entry_delay_years"] = [round((self.entry[f.idx] - none.entry[f.idx]) / 252.0, 3) for f in both]
        out["edge_entry_lost"] = sum(f.idx in none.entry and f.idx not in self.entry for f in edge)
        out["edge_entry_without_dormancy"] = sum(f.idx in none.entry for f in edge)
        return out


def run(scenario_id: str, rep: int, years: tuple) -> dict:
    os.environ["MANHATTAN_SIM_EVAL_YEARS"] = ",".join(str(y) for y in years)
    sys.path.insert(0, HERE)
    import own_record
    from manhattan.sim import hb, hb_v2, pipeline, seeds, world
    from manhattan.stats import dormancy, hier_analytic, screening, tiers
    mods = (tiers, dormancy, own_record)
    t0 = time.time()
    scn, size = world.SCENARIOS[scenario_id], world.SIZES["HB"]
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
    tracks = {rule: Track(rule, fams, tiers) for rule in RULES}
    decay = next((k for k, sp in enumerate(hier_analytic.SPECS) if sp.decay), None)
    out = {"scenario": scenario_id, "rep": rep, "years": list(years), "code": hb_v2.dormancy.RULE, "gate": [0, 0, 0, 0]}
    for yi, year in enumerate(years):
        t = year * world.YEAR
        data, live, info = hb_v2.build_data(fams, t, se_H, est_rng)
        fits = hier_analytic.fit_many(data, draws=hb.PP_DRAWS, seed=int(streams.seq(seeds.MODEL, 1 + yi).generate_state(1)[0]))
        assert all(f.ok for f in fits)
        pis = np.array([f.pi for f in fits])
        pi_min, pi_max = pis.min(axis=0), pis.max(axis=0)
        gaps = [b - a for a, b in zip(years[yi:], years[yi + 1:])]
        days = np.array([t - f.freeze for f in live])
        p_fwd = own_record.forward_p(data.y_F, data.s_F, days)
        rw = np.array([bool(f.ev.rw_adm_any.get("i")) for f in live])
        for rule in RULES:
            tr = tracks[rule]
            pp_max = None
            if gaps and rule != "none":                         # the pipeline's own forecast, on the pipeline's own stream
                pp = tiers.support_probability(
                    np.stack([f.draws for f in fits]), np.stack([f.mean for f in fits]), np.stack([f.sd for f in fits]),
                    fwd_years=info["fwd_years"], fwd_sum=info["fwd_sharpe_f"] * info["fwd_years"],
                    promising=np.array([tr.state[f.idx].promising for f in live]), rw_reserve=rw, review_gaps=gaps,
                    rng=streams.rng(seeds.MODEL, 100 + yi, 0), decay_model=decay)
                pp_max = pp.max(axis=0)
                if rule == "branch":                            # which conditions hold, among families neither dormant nor supported
                    for j, f in enumerate(live):
                        s = tr.state[f.idx]
                        if not s.dormant and not s.supported and days[j] >= 252:
                            lo_pp, lo_pi, lo_p = pp_max[j] < 0.05, pi_max[j] < 0.05, p_fwd[j] < 0.05
                            out["gate"][0] += int(lo_pp); out["gate"][1] += int(lo_pp and lo_pi)
                            out["gate"][2] += int(lo_pp and lo_p); out["gate"][3] += 1
            for j, f in enumerate(live):
                tr.review(f, t, tiers.Review(pi_min=float(pi_min[j]), forward_days=int(days[j]),
                                             forward_mean_positive=bool(info["fwd_sharpe_f"][j] > 0), rw_reserve=bool(rw[j]),
                                             pp_max=None if pp_max is None else float(pp_max[j])),
                          float(pi_max[j]), float(p_fwd[j]), not gaps, mods)
            tr.by_year[str(year)] = [sum(tr.state[f.idx].dormant for f in live if f.true >= world.THETA_MIN),
                                     sum(tr.state[f.idx].dormant for f in live if f.true < world.THETA_MIN)]
    for tr in tracks.values():
        tr.close(world.T_END)
    out["diag"] = {rule: tracks[rule].summary(fams, world.T_END, tracks["none"], world.THETA_MIN) for rule in RULES}
    out["seconds"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    outdir, scenario, rep = sys.argv[1], sys.argv[2], int(sys.argv[3])
    years = tuple(int(x) for x in sys.argv[4].split(",")) if len(sys.argv) > 4 else (2, 4, 7, 10)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{scenario}_{rep}.json")
    if not os.path.exists(path):
        r = run(scenario, rep, years)
        with open(path, "w") as f:
            json.dump(r, f, sort_keys=True, separators=(",", ":"))
        d = r["diag"]
        print(scenario, rep, " ".join(f"{k} {d[k]['m8_num']}/{d[k]['m8_den']}" for k in ("branch", "v30", "own")), r["seconds"], flush=True)
