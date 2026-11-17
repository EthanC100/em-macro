"""Session 6M: where the central model's calibration error comes from (from the traces)."""
from __future__ import annotations

import os
import sys

import numpy as np
from scipy.special import logsumexp
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse_traces import load                   # noqa: E402
from manhattan.sim import metrics, world          # noqa: E402


def gather(trs, year):
    rows = []
    for ri, tr in enumerate(trs):
        r = tr["reviews"][str(year)]
        fam = {int(k): v for k, v in tr["fam"].items()}
        for j, i in enumerate(r["idx"]):
            rows.append((ri, fam[i]["true"], r["pi"][0][j], r["mean"][0][j], r["sd"][0][j], fam[i]["y_H"], fam[i]["s_H"],
                         r["y_F"][j], r["s_F"][j], r["fwd_years"][j]))
    return np.array(rows)


def ece(rep, p, edge, R):
    b = np.minimum((p * 10).astype(int), 9)
    bins = [(np.bincount(b[rep == k], minlength=10), np.bincount(b[rep == k], weights=edge[rep == k], minlength=10),
             np.bincount(b[rep == k], weights=p[rep == k], minlength=10)) for k in range(R)]
    return metrics.ece_ci(bins)


def two_group(yH, sH, yF, sF, grid_pi=np.linspace(0.02, 0.98, 49), grid_m=np.linspace(0.2, 1.4, 25), grid_v=np.array([0.15, 0.25, 0.35, 0.5, 0.7])):
    """A deliberately simple check, not a proposal: theta is 0 with probability pi0, else Normal(m, v^2); the
    reserve and forward estimates are both unbiased for theta (no decay in D08). pi0, m, v by maximum likelihood
    on the replication. Returns Pr(theta >= 0.25 | data)."""
    hasF = yF > -90
    prec = 1 / sH**2 + np.where(hasF, 1 / sF**2, 0.0)
    ybar = (yH / sH**2 + np.where(hasF, yF / sF**2, 0.0)) / prec
    s2 = 1 / prec
    best = (-np.inf, None)
    l0 = norm.logpdf(ybar, 0.0, np.sqrt(s2))
    for m in grid_m:
        for v in grid_v:
            l1 = norm.logpdf(ybar, m, np.sqrt(s2 + v * v))
            for pi0 in grid_pi:
                ll = np.logaddexp(np.log(pi0) + l0, np.log1p(-pi0) + l1).sum()
                if ll > best[0]:
                    best = (ll, (pi0, m, v))
    pi0, m, v = best[1]
    l1 = norm.logpdf(ybar, m, np.sqrt(s2 + v * v))
    w1 = np.exp(np.log1p(-pi0) + l1 - np.logaddexp(np.log(pi0) + l0, np.log1p(-pi0) + l1))
    pv = 1 / (1 / v**2 + prec)
    pm = pv * (m / v**2 + ybar * prec)
    return w1 * norm.sf((0.25 - pm) / np.sqrt(pv)), best[1]


def main(scen):
    for s in scen:
        trs = load(s)
        R = len(trs)
        print(f"\n===== {s}: {R} replications")
        for year in (4, 7, 10):
            a = gather(trs, year)
            rep, true, p = a[:, 0].astype(int), a[:, 1], a[:, 2]
            edge = (true >= world.THETA_MIN).astype(float)
            e, lo, hi = ece(rep, p, edge, R)
            print(f"\n year {year}: {len(a)} family evaluations, {int(edge.sum())} with an edge of at least 0.25; ECE {e:.4f} ({lo:.4f} to {hi:.4f})")
            b = np.minimum((p * 10).astype(int), 9)
            print("  bin     n   stated  observed   gap*n/N   null(0)  weak(0<θ<0.25)  0.25-0.4  0.4-0.7  >0.7   mean fwd yrs")
            for k in range(10):
                m = b == k
                if not m.any():
                    continue
                t = true[m]
                print(f"  {k/10:.1f}  {m.sum():5d}   {p[m].mean():.3f}    {edge[m].mean():.3f}    {abs(p[m].sum() - edge[m].sum()) / len(a):.4f}"
                      f"    {(t <= 0).mean():.2f}       {((t > 0) & (t < 0.25)).mean():.2f}         {((t >= 0.25) & (t < 0.4)).mean():.2f}"
                      f"     {((t >= 0.4) & (t < 0.7)).mean():.2f}    {(t >= 0.7).mean():.2f}     {a[m, 9].mean():.1f}")
            if year == 10:
                # the same calibration with a two-group prior fitted per replication (a check of the cause)
                p2 = np.empty_like(p)
                pars = []
                for k in range(R):
                    m = rep == k
                    p2[m], par = two_group(a[m, 5], a[m, 6], a[m, 7], a[m, 8])
                    pars.append(par)
                e2, lo2, hi2 = ece(rep, p2, edge, R)
                print(f"  two-group check (point mass at zero + normal, fitted per replication): ECE {e2:.4f} ({lo2:.4f} to {hi2:.4f}); "
                      f"fitted share at zero {np.mean([q[0] for q in pars]):.2f}, slab mean {np.mean([q[1] for q in pars]):.2f}, sd {np.mean([q[2] for q in pars]):.2f}")
                # the threshold itself: how the error moves if the question were asked at another level
                for thr in (0.10, 0.15, 0.25, 0.35):
                    pt = norm.sf((thr - a[:, 3]) / np.maximum(a[:, 4], 1e-9))
                    et = (true >= thr).astype(float)
                    print(f"  normal approximation of the S0 posterior, question 'θ ≥ {thr}': ECE {ece(rep, pt, et, R)[0]:.4f}"
                          f" (share true {et.mean():.3f})")
                truth = np.round(true, 2)
                vals, cnt = np.unique(np.where(truth <= 0, 0.0, np.round(true / 0.05) * 0.05), return_counts=True)
                print("  true family Sharpe (rounded to 0.05): " + ", ".join(f"{v:.2f}:{c / len(a):.3f}" for v, c in zip(vals, cnt) if c / len(a) >= 0.01))
                print(f"  hyper S0 (means over reps): " + ", ".join(f"{k}={np.mean([t['reviews']['10']['hyper'][0][k] for t in trs]):.3f}"
                                                                    for k in ("mu_A", "tau_A", "psi", "rho_0", "rho_1", "rho_2")))


if __name__ == "__main__":
    main(sys.argv[1:] or ["D08"])
