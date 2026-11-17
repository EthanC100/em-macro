"""Session 6M: which part of the dormancy rule retires families that have an edge? Reads the traces of
trace_hb.py and replays the tier state machine with one part of the rule changed at a time."""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

from manhattan.sim import metrics, world
from manhattan.stats import tiers

S = os.path.dirname(os.path.abspath(__file__))
YEARS = (2, 4, 7, 10)


def load(scenario, tag=""):
    out = []
    for p in sorted(glob.glob(f"{S}/trace/{scenario}_*{tag}.json"), key=lambda p: int(os.path.basename(p).split("_")[1].split(".")[0])):
        if tag == "" and "_y" in os.path.basename(p):
            continue
        out.append(json.load(open(p)))
    return out


def replay(tr, *, pp_key="pp", cut=0.05, react=0.15, min_years=0.0, pimax_cut=None, need=2, dormancy=True,
           pf_cut=None, pf_only=False, last_wake=True):
    """Replay candidate (i)'s state machine on one traced replication with a variant of the dormancy rule.
    Returns per-family dict: true, freeze, dormant_end, dormant_days, ever_dormant, supported_year, reviews_active."""
    years = tr["years"]
    fam = {int(k): v for k, v in tr["fam"].items()}
    st = {i: tiers.at_freeze(v["passed"]) for i, v in fam.items()}
    since, ddays = {}, {i: 0 for i in fam}
    ever, sup_year, active = set(), {}, {i: 0 for i in fam}
    low = {i: 0 for i in fam}
    dorm = {i: False for i in fam}
    for y in years:
        r = tr["reviews"][str(y)]
        t = y * world.YEAR
        pis = np.array(r["pi"])
        pmin, pmax = pis.min(axis=0), pis.max(axis=0)
        pp = np.array(r[pp_key]).max(axis=0) if (pp_key in r and dormancy) else None
        yF, sF = np.array(r["y_F"]), np.array(r["s_F"])
        from scipy.stats import norm as _n
        pf = np.where((yF > -90) & (np.array(r["fwd_years"]) >= 1.0), _n.cdf((yF - 0.25) / sF), 1.0)
        if pf_only and pp is not None:
            pp = np.zeros_like(pp)
        for j, i in enumerate(r["idx"]):
            f = fam[i]
            fy = r["fwd_years"][j]
            # dormancy bookkeeping done here; tiers.step is used for the tiers only
            if dorm[i]:
                wake_pf = pf_cut is not None and pf[j] >= pf_cut[1] and (pp is not None or last_wake)
                if wake_pf or (pp is not None and (pp[j] >= react or (pimax_cut is not None and pmax[j] >= max(pimax_cut[1], 0)))):
                    dorm[i] = False
                    low[i] = 0
                    ddays[i] += t - since.pop(i)
                else:
                    continue
            active[i] += 1
            s = tiers.step(st[i], tiers.Review(pi_min=float(pmin[j]), forward_days=t - f["freeze"],
                                               forward_mean_positive=bool(r["fwd_pos"][j]), rw_reserve=f["rw"], pp_max=None))
            st[i] = s
            if s.supported and i not in sup_year:
                sup_year[i] = y
            if pp is not None and not s.supported:
                is_low = (pp[j] < cut and fy >= min_years and (pimax_cut is None or pmax[j] < pimax_cut[0])
                          and (pf_cut is None or pf[j] < pf_cut[0]))
                low[i] = low[i] + 1 if is_low else 0
                if low[i] >= need:
                    dorm[i] = True
                    low[i] = 0
                    since[i] = t
                    ever.add(i)
            elif s.supported:
                low[i] = 0
    for i, s0 in since.items():
        ddays[i] += world.T_END - s0
    return {i: dict(true=f["true"], freeze=f["freeze"], dormant_end=dorm[i], dormant_days=ddays[i], ever=i in ever,
                    sup_year=sup_year.get(i), active=active[i]) for i, f in fam.items()}


def m8(reps_out):
    num, den, null_dorm, null_n, act, tot = [], [], [], [], [], []
    for out in reps_out:
        edge = [v for v in out.values() if v["true"] >= world.THETA_MIN]
        gone = [v for v in edge if v["dormant_end"] or v["dormant_days"] > 0.5 * (world.T_END - v["freeze"])]
        null = [v for v in out.values() if v["true"] < world.THETA_MIN]
        num.append(len(gone)); den.append(len(edge))
        null_dorm.append(sum(v["dormant_end"] for v in null)); null_n.append(len(null))
        act.append(sum(v["active"] for v in out.values()))
        tot.append(sum(sum(1 for y in YEARS if y * world.YEAR > v["freeze"]) for v in out.values()))
    e, lo, hi = metrics.ratio_ci(num, den)
    return dict(rate=e, lo=lo, hi=hi, num=int(sum(num)), den=int(sum(den)), null_dormant=sum(null_dorm) / max(1, sum(null_n)),
                reviews=sum(act) / sum(tot))


def line(name, r):
    return (f"{name:46s} M8 {r['rate']:.3f} ({r['lo']:.3f} to {r['hi']:.3f}) {r['num']:3d}/{r['den']:4d}   "
            f"null dormant at end {r['null_dormant']:.3f}   family-reviews written {r['reviews']:.3f}")


VARIANTS = [
    ("rule as written (0.05 twice / 0.15)", {}),
    ("cut-off 0.02", dict(cut=0.02)),
    ("cut-off 0.01", dict(cut=0.01)),
    ("cut-off 0.005 (no draw of 200 enters)", dict(cut=0.005)),
    ("reactivate at 0.05", dict(react=0.05)),
    ("three low reviews, not two", dict(need=3)),
    ("at least 3 forward years", dict(min_years=3.0)),
    ("at least 5 forward years", dict(min_years=5.0)),
    ("tier bar on S0 alone", dict(pp_key="pp_s0bar")),
    ("tier bar without S5", dict(pp_key="pp_no_s5")),
    ("tier bar without S4 and S5", dict(pp_key="pp_no_s45")),
    ("ten more years of reviews", dict(pp_key="pp_long")),
    ("ten more years and S0 bar", dict(pp_key="pp_long_s0bar")),
    ("and Pi^max < 0.20 (wake at 0.20)", dict(pimax_cut=(0.20, 0.20))),
    ("and Pi^max < 0.10 (wake at 0.20)", dict(pimax_cut=(0.10, 0.20))),
    ("and Pi^max < 0.05 (wake at 0.15)", dict(pimax_cut=(0.05, 0.15))),
    ("and Pi^max < 0.05 (wake at 0.20)", dict(pimax_cut=(0.05, 0.20))),
    ("and Pi^max < 0.02 (wake at 0.15)", dict(pimax_cut=(0.02, 0.15))),
    ("and p^F < 0.05 (wake at p^F >= 0.15)", dict(pf_cut=(0.05, 0.15))),
    ("same, no wake at the last review", dict(pf_cut=(0.05, 0.15), last_wake=False)),
    ("and p^F < 0.05 (wake at p^F >= 0.05)", dict(pf_cut=(0.05, 0.05))),
    ("and p^F < 0.10 (wake at p^F >= 0.20)", dict(pf_cut=(0.10, 0.20))),
    ("and p^F < 0.025 (wake at p^F >= 0.15)", dict(pf_cut=(0.025, 0.15))),
    ("p^F < 0.05 alone, no forecast", dict(pf_cut=(0.05, 0.15), pf_only=True)),
    ("no dormancy", dict(dormancy=False)),
]

if __name__ == "__main__":
    scen = sys.argv[1:] or ["D02", "D05", "D08", "D10"]
    for s in scen:
        trs = load(s)
        print(f"\n===== {s}: {len(trs)} replications; recorded M8 {sum(t['m8_num_i'] for t in trs)}/{sum(t['m8_den_i'] for t in trs)}")
        for name, kw in VARIANTS:
            print(line(name, m8([replay(t, **kw) for t in trs])))
