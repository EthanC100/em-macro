"""Session 6M: who the dormancy rule of 3.0 retires, and why (from the traces)."""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse_traces import load, replay           # noqa: E402
from trace_hb import forecast                     # noqa: E402
from manhattan.sim import world                   # noqa: E402

BINS = [(0.25, 0.40), (0.40, 0.70), (0.70, 1.10), (1.10, 9.0)]


def main(scen):
    for s in scen:
        trs = load(s)
        rows = []          # one per true-edge family made dormant: the review at which it became dormant
        edge_all, share = [], {b: [0, 0] for b in BINS}
        for tr in trs:
            out = replay(tr)
            fam = {int(k): v for k, v in tr["fam"].items()}
            years = tr["years"]
            prev_prom = {i: f["passed"] for i, f in fam.items()}
            dormant_at = {}
            for yi, y in enumerate(years):
                r = tr["reviews"][str(y)]
                idx = r["idx"]
                if "pp" in r:
                    gaps = [b - a for a, b in zip(years[yi:], years[yi + 1:])]
                    M, SD = np.array(r["mean"]), np.array(r["sd"])
                    true = np.array([fam[i]["true"] for i in idx])
                    D = np.broadcast_to(true, (6, 200, len(idx))).copy()
                    fy = np.array(r["fwd_years"])
                    yF = np.where(np.array(r["y_F"]) > -90, np.array(r["y_F"]), 0.0)
                    oracle = forecast(D, M, SD, fwd_years=fy, fwd_sum=yF * fy,
                                      promising=np.array([prev_prom[i] for i in idx]),
                                      rw_reserve=np.array([fam[i]["rw"] for i in idx]), review_gaps=gaps,
                                      rng=np.random.default_rng([7, yi]), decay_model=None)[0]
                    r["_oracle"] = oracle
                for j, i in enumerate(idx):
                    was = prev_prom[i]
                    st = r["state"][j]
                    if st[2] and i not in dormant_at:
                        dormant_at[i] = (y, j)
                    prev_prom[i] = bool(st[0])
            for i, o in out.items():
                if o["true"] < world.THETA_MIN:
                    continue
                gone = o["dormant_end"] or o["dormant_days"] > 0.5 * (world.T_END - o["freeze"])
                edge_all.append((o["true"], gone))
                for b in BINS:
                    if b[0] <= o["true"] < b[1]:
                        share[b][1] += 1
                        share[b][0] += int(gone)
                if gone and i in dormant_at:
                    y, j = dormant_at[i]
                    r = tr["reviews"][str(y)]
                    pis = np.array(r["pi"])[:, j]
                    pp = np.array(r["pp"])[:, j]
                    rows.append(dict(true=o["true"], year=y, fwd=r["fwd_years"][j], yF=r["y_F"][j], sF=r["s_F"][j],
                                     pi0=pis[0], pimax=pis.max(), pimin=pis.min(), mean0=r["mean"][0][j], sd0=r["sd"][0][j],
                                     ppmax=pp.max(), oracle=float(r["_oracle"][j]), yH=fam[i]["y_H"],
                                     pF=float(__import__("scipy.stats", fromlist=["norm"]).norm.cdf((r["y_F"][j] - 0.25) / r["s_F"][j]))))
        n_edge = len(edge_all)
        n_gone = sum(g for _, g in edge_all)
        print(f"\n===== {s}: {n_gone} of {n_edge} families with a true edge retired")
        print("  by true Sharpe: " + "; ".join(f"{b[0]:.2f}-{b[1]:.2f}: {v[0]}/{v[1]}" + (f" ({v[0] / v[1]:.2f})" if v[1] else "") for b, v in share.items()))
        if not rows:
            continue
        a = {k: np.array([r[k] for r in rows]) for k in rows[0]}
        q = lambda x: "/".join(f"{v:.2f}" for v in np.percentile(x, [10, 50, 90]))
        print(f"  became dormant at year 4: {(a['year'] == 4).sum()}, at year 7: {(a['year'] == 7).sum()}")
        print(f"  at that review (10th/50th/90th percentile): true Sharpe {q(a['true'])}; forward years {q(a['fwd'])}; "
              f"forward Sharpe estimate {q(a['yF'])}; reserve estimate {q(a['yH'])}")
        print(f"     posterior mean under S0 {q(a['mean0'])} (sd {q(a['sd0'])}); Pi S0 {q(a['pi0'])}; Pi max {q(a['pimax'])}; PP max {q(a['ppmax'])}")
        print(f"     forecast with the truth in place of the posterior draws (PP): {q(a['oracle'])}; share with that PP >= 0.05: {(a['oracle'] >= 0.05).mean():.2f}; >= 0.15: {(a['oracle'] >= 0.15).mean():.2f}")
        print(f"     share with Pi max < 0.05: {(a['pimax'] < 0.05).mean():.2f}; < 0.10: {(a['pimax'] < 0.10).mean():.2f}; < 0.20: {(a['pimax'] < 0.20).mean():.2f}")
        print(f"     own forward record against an edge of 0.25 (one-sided p): {q(a['pF'])}; share below 0.05: {(a['pF'] < 0.05).mean():.2f}")
        print(f"     share whose posterior mean under S0 is below their true Sharpe: {(a['mean0'] < a['true']).mean():.2f}; mean shortfall {np.mean(a['true'] - a['mean0']):.2f}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["D02", "D05", "D08", "D10"])
