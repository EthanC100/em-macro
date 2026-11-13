"""Is the edge share of the two-group candidate (``manhattan/stats/hier_spike.py``) identified by the data a
programme has? A development experiment of session "10M Manhattan C" (2026-11-13), outside the runner.

    python results/manhattan_sim/v2/dev_10M/spike_identification.py synthetic      # part A
    python results/manhattan_sim/v2/dev_10M/spike_identification.py d08 [reps]     # part B (default 12 replications)
    python results/manhattan_sim/v2/dev_10M/spike_identification.py apparent       # part C: where D08's two groups are
    python results/manhattan_sim/v2/dev_10M/spike_identification.py report         # D08_SPIKE_SLAB.md from the three

An earlier attempt at a two-group prior put the share near 0.9 where the truth was 0.35. So the share is checked
**before** the candidate is wired into any pipeline, and the criterion is fixed here, before the first run:

    THE SHARE IS IDENTIFIED if, in D08 at HB on the pilot's 12 replications, at year 4 AND at year 10 (the two
    dates at which V6 is decided), under the central model:
      (1) the posterior standard deviation of the share is at most HALF the prior's (0.287 / 2 = 0.144) on
          average over replications, and
      (2) the posterior mean of the share is within 0.10 of the true share of families with an edge, on
          average over replications (mean absolute error).
    Otherwise it is not identified, the candidate is not adopted, and D08 stays a documented limitation.

Part A asks the same of data drawn from the candidate itself (well specified, so a failure there cannot be blamed
on the simulated world), at the programme's size and at sizes no programme has. Part B is the test that counts.

Development scenarios only (D08, seed branch 0). No held-out scenario. Nothing here is a run of record.
"""
from __future__ import annotations

import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent

from manhattan.stats import hier_analytic as ha            # noqa: E402
from manhattan.stats import hier_spike as hs               # noqa: E402

PRIOR_SD = float(np.std(hs.SHARE_GRID))                    # 0.287: ten equal nodes
SD_MAX, ERR_MAX = PRIOR_SD / 2, 0.10
TRUE_SHARE = 0.35
BINS = 10


def calib(pi: np.ndarray, edge: np.ndarray) -> list:
    """Counts behind the expected calibration error, as ``hb.review_metrics`` keeps them."""
    b = np.minimum((pi * BINS).astype(int), BINS - 1)
    return [np.bincount(b, minlength=BINS).tolist(), np.bincount(b, weights=edge, minlength=BINS).tolist(),
            np.bincount(b, weights=pi, minlength=BINS).tolist()]


def ece(triples: list) -> float:
    n, t, p = (np.sum([x[i] for x in triples], axis=0) for i in range(3))
    ok = n > 0
    return float((np.abs(t[ok] - p[ok])).sum() / n.sum())


def summarise(fit: hs.Fit) -> dict:
    return {"share_mean": fit.share_mean, "share_sd": fit.share_sd, "share_post": fit.share_post.round(5).tolist(),
            "loglik_range": float(np.ptp(fit.share_loglik)),
            "loglik": (fit.share_loglik - fit.share_loglik.max()).round(3).tolist(),
            "mode": float(fit.share_grid[int(np.argmax(fit.share_post))]), "seconds": round(fit.seconds, 1)}


# ----------------------------------------------------------------------------------------------- part A

def draw(seed: int, n: int, horizon: float) -> tuple[ha.Data, np.ndarray]:
    """Families from the candidate itself: share 0.35 in the slab; apparent edges Normal(1.0, 0.35²); retention
    0.7 in every class; reserve window of 1,750 days; forward records of 0.25 to ``horizon`` years (families
    frozen at an even pace); no common shock."""
    rng = np.random.default_rng([10, seed, n, int(horizon * 4)])
    a = 1.0 + 0.35 * rng.standard_normal(n)
    slab = rng.random(n) < TRUE_SHARE
    theta = np.where(slab, 0.7 * a, 0.0) + ha.ETA_SD * rng.standard_normal(n)
    s_H = np.full(n, 1.0 / math.sqrt(1750 / 252))
    years = rng.uniform(0.25, horizon, n)
    s_F = 1.0 / np.sqrt(years)
    data = ha.Data(y_H=a + s_H * rng.standard_normal(n), s_H=s_H, y_F=theta + s_F * rng.standard_normal(n), s_F=s_F,
                   mech=rng.integers(0, 3, n), age=years)
    return data, slab


def one_synthetic(job):
    seed, n, horizon = job
    data, slab = draw(seed, n, horizon)
    fit = hs.fit(data)
    return {"seed": seed, "families": n, "horizon": horizon, "true_share": float(slab.mean()), **summarise(fit)}


def synthetic(workers: int = 3, seeds: int = 12) -> None:
    jobs = [(s, n, h) for n, h in ((96, 4.0), (240, 10.0), (960, 10.0), (2400, 10.0)) for s in range(seeds)]
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(one_synthetic, jobs))
    (HERE / "spike_synthetic.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    for n, h in sorted({(r["families"], r["horizon"]) for r in rows}):
        v = [r for r in rows if (r["families"], r["horizon"]) == (n, h)]
        print(n, h, "mean share", round(np.mean([r["share_mean"] for r in v]), 3), "sd", round(np.mean([r["share_sd"] for r in v]), 3),
              "abs err", round(np.mean([abs(r["share_mean"] - r["true_share"]) for r in v]), 3),
              "loglik range", round(np.mean([r["loglik_range"] for r in v]), 2))


# ----------------------------------------------------------------------------------------------- part B

def one_d08(rep: int) -> list[dict]:
    """The inputs of the pilot's reviews of D08 at HB (years 2, 4, 7 and 10, by the HB pipeline's own functions and
    random streams), fitted by the central model with one group and with two."""
    from manhattan.sim import hb, hb_v2, pipeline, seeds, world
    from manhattan.stats import screening
    scn, size = world.SCENARIOS["D08"], world.SIZES["HB"]
    streams = seeds.Streams(seeds.prereg_hash(), seeds.DEVELOPMENT, "D08", "HB", rep)
    mech_rng, est_rng = streams.rng(seeds.MODEL, 0), streams.rng(seeds.ESTIMATE)
    procs = {"i": screening.BatchBH(size.N), "ii": screening.EbhElond(size.N)}
    fams, se_H = [], {}
    for _, _, batch in world.batches(scn, size, streams):
        evs = [pipeline.evaluate_family(f, streams) for f in batch]
        pipeline.decide_batch(evs, procs)
        new = [hb_v2.Fam(f, e, int(mech_rng.integers(hb.N_MECH)), est_rng) for f, e in zip(batch, evs)]
        se = hb.sharpe_se(np.stack([f.P_f[world.EXPLORE : world.HISTORY] for f in new]), est_rng)
        for j, f in enumerate(new):
            se_H[f.idx] = float(se[j])
        fams.extend(new)
    out = []
    for year in (2, 4, 7, 10):
        data, live, _ = hb_v2.build_data(fams, year * world.YEAR, se_H, est_rng)
        if year not in (4, 10):
            continue
        true = np.array([f.true for f in live])
        edge = true >= world.THETA_MIN
        t0 = time.time()
        two, one = hs.fit(data), ha.fit(data)
        out.append({"rep": rep, "year": year, "families": len(live), "with_forward": int(data.has_forward.sum()),
                    "true_share_edge": float(edge.mean()), "true_share_nonzero": float((true > 0).mean()),
                    **summarise(two), "rho_two": [two.hyper[k] for k in sorted(two.hyper) if k.startswith("rho_")],
                    "rho_one": [one.hyper[k] for k in sorted(one.hyper) if k.startswith("rho_")],
                    "cal_two": calib(two.pi, edge), "cal_one": calib(one.pi, edge),
                    "slab_edge": float(two.slab[edge].mean()) if edge.any() else None,
                    "slab_null": float(two.slab[~edge].mean()) if (~edge).any() else None,
                    "fit_seconds": round(time.time() - t0, 1)})
    return out


def d08(reps: int = 12, workers: int = 3) -> None:
    with ProcessPoolExecutor(workers) as pool:
        rows = [r for part in pool.map(one_d08, range(reps)) for r in part]
    (HERE / "spike_d08.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    for y in (4, 10):
        v = [r for r in rows if r["year"] == y]
        print("year", y, "true", round(np.mean([r["true_share_edge"] for r in v]), 3), "mean share", round(np.mean([r["share_mean"] for r in v]), 3),
              "sd", round(np.mean([r["share_sd"] for r in v]), 3),
              "abs err", round(np.mean([abs(r["share_mean"] - r["true_share_edge"]) for r in v]), 3),
              "ECE one/two", round(ece([r["cal_one"] for r in v]), 3), round(ece([r["cal_two"] for r in v]), 3))


# ----------------------------------------------------------------------------------------------- part C

def apparent(reps: int = 3) -> None:
    """Where D08's two groups are: the family portfolio's sample Sharpe ratio on the exploration window (which
    the best-of-20 selection looks at) and on the reserve window (which the model reads), for families with and
    without an edge. The worlds of the pilot's first replications; no model is fitted."""
    from manhattan.sim import hb, seeds, world
    out = []
    for rep in range(reps):
        scn, size = world.SCENARIOS["D08"], world.SIZES["HB"]
        streams = seeds.Streams(seeds.prereg_hash(), seeds.DEVELOPMENT, "D08", "HB", rep)
        yh, ye, true = [], [], []
        for _, _, batch in world.batches(scn, size, streams):
            for f in batch:
                P_f = f.X.mean(axis=1).mean(axis=0)
                yh.append(float(hb.sharpe(P_f[world.EXPLORE : world.HISTORY])))
                ye.append(float(hb.sharpe(P_f[: world.EXPLORE])))
                true.append(f.true_sharpe_f)
        yh, ye, true = map(np.array, (yh, ye, true))
        null = true < world.THETA_MIN
        out.append({"rep": rep, "n_null": int(null.sum()), "n_edge": int((~null).sum()),
                    "reserve_null_mean": float(yh[null].mean()), "reserve_null_sd": float(yh[null].std()),
                    "reserve_edge_mean": float(yh[~null].mean()), "explore_null_mean": float(ye[null].mean()),
                    "explore_edge_mean": float(ye[~null].mean()), "true_edge_mean": float(true[~null].mean()),
                    "true_null_exact_zero": int((true[null] == 0).sum())})
    (HERE / "spike_apparent.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out))


# ----------------------------------------------------------------------------------------------- the document

def report() -> None:
    from manhattan.sim import metrics
    syn = json.loads((HERE / "spike_synthetic.json").read_text(encoding="utf-8"))
    d08_rows = json.loads((HERE / "spike_d08.json").read_text(encoding="utf-8"))
    f3 = lambda x: f"{x:.3f}"
    L = ["# D08 and a two-group (\"spike and slab\") prior: the edge share is not identified, and the candidate is not adopted",
         "",
         "Written by `results/manhattan_sim/v2/dev_10M/spike_identification.py report` (session \"10M Manhattan C: final "
         "pre-adoption changes\", 2026-11-13). **Synthetic data only. Development scenario D08 only (seed branch 0). No "
         "held-out scenario was coded or run. A development experiment outside the runner (note `note-10M-01` in the run "
         "log): it decides nothing, and no run of record uses the candidate.**",
         "",
         "## 1. What was tried, and the test fixed before it was run",
         "",
         "Protocol 3.1 §7.2(d) states a limitation: where a large share of families has an edge of exactly zero and the "
         "rest have clear ones (D08), the central model's one hump says too much in the middle of the scale (calibration "
         "error 0.101 at year 10 against a bound of 0.10). Ethan asked for one repair to be tried "
         "(`manhattan/stats/hier_spike.py`):",
         "",
         "- **slab** (probability `π`): the model as it is, `θ_f = ρ a_f + η_f`;",
         "- **spike** (probability `1 − π`): the slab at retention 0 with the existing 0.02 innovation, `θ_f = η_f`, "
         "`η_f ~ Normal(0, 0.02²)`. No new constant;",
         "- **the edge share `π`**: uniform on ten grid nodes, 0.05, 0.15, ..., 0.95, one share for the programme.",
         "",
         "With the share fixed at 1 the candidate is the analytic model number for number "
         "(`tests/test_manhattan_hier_spike.py`: all six models, with a common shock, missing forward records and an "
         "adaptive-channel family; log evidence to 1e-9, every family's `Π`, mean and standard deviation to 1e-10).",
         "",
         "An earlier attempt at a two-group prior had put the share near 0.9 where the truth was 0.35, so the share was "
         "checked **first**, before the candidate was wired into any pipeline. The criterion was written into the script "
         "before its first run:",
         "",
         f"> The share is identified if, in D08 at HB on the pilot's 12 replications, at year 4 **and** at year 10 (the dates "
         f"at which V6 is decided), under the central model: (1) the posterior standard deviation of the share is at most "
         f"half the prior's ({PRIOR_SD:.3f} / 2 = {SD_MAX:.3f}) on average, and (2) the posterior mean is within "
         f"{ERR_MAX:.2f} of the true share of families with an edge, on average. Otherwise it is not identified, the "
         "candidate is not adopted, and D08 stays a documented limitation.",
         "",
         "## 2. Result on D08 (the test that counts)",
         "",
         "The inputs are the pilot of record's own: the HB pipeline's functions and random streams, the same estimates and "
         "standard errors (the one-group fit below reproduces the pilot's calibration counts at year 10 bin for bin). "
         "Central model (S0).",
         "",
         "| date | replications | families at the review | true share with an edge of at least 0.25 (mean; range) | "
         "**posterior mean of the share** (mean; range) | posterior sd (mean) | mean absolute error | most probable node | "
         "log likelihood, best node minus worst (mean) | criterion (1): sd ≤ " + f"{SD_MAX:.3f}" + " | criterion (2): error ≤ "
         + f"{ERR_MAX:.2f}" + " |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    verdicts = []
    for y in (4, 10):
        v = [r for r in d08_rows if r["year"] == y]
        true = np.array([r["true_share_edge"] for r in v])
        mean = np.array([r["share_mean"] for r in v])
        sd = float(np.mean([r["share_sd"] for r in v]))
        err = float(np.mean(np.abs(mean - true)))
        modes = sorted({round(r["mode"], 2) for r in v})
        c1, c2 = sd <= SD_MAX, err <= ERR_MAX
        verdicts.append(c1 and c2)
        L.append(f"| year {y} | {len(v)} | {v[0]['families']} | {f3(true.mean())} ({f3(true.min())} to {f3(true.max())}) | "
                 f"**{f3(mean.mean())}** ({f3(mean.min())} to {f3(mean.max())}) | {f3(sd)} | {f3(err)} | "
                 f"{', '.join(f'{m:.2f}' for m in modes)} | {np.mean([r['loglik_range'] for r in v]):.1f} | "
                 f"{'met' if c1 else '**not met**'} | {'met' if c2 else '**not met**'} |")
    L += ["",
          "**Verdict: the share is not identified.** " + ("" if any(verdicts) else "Neither date meets the criterion. ")
          + "At year 10 the posterior is narrow and in the wrong place: 0.90 where 0.33 of the families have an edge, the "
          "figure the earlier attempt had found. More data do not help it; they make it surer (the log likelihood of the "
          "best node is 20 to 50 above the worst at year 10). At year 4 it is wider and no nearer.",
          "",
          "Replication by replication:",
          "",
          "| replication | year 4: true share / posterior mean / sd | year 10: true share / posterior mean / sd | "
          "year 10: posterior probability of the slab, families with an edge / families with none | "
          "year 10: retention of the three classes, one group / two groups |",
          "|---|---|---|---|---|"]
    for rep in sorted({r["rep"] for r in d08_rows}):
        a, b = (next(r for r in d08_rows if r["rep"] == rep and r["year"] == y) for y in (4, 10))
        L.append(f"| {rep} | {f3(a['true_share_edge'])} / {f3(a['share_mean'])} / {f3(a['share_sd'])} | "
                 f"{f3(b['true_share_edge'])} / {f3(b['share_mean'])} / {f3(b['share_sd'])} | "
                 f"{b['slab_edge']:.2f} / {b['slab_null']:.2f} | "
                 f"{', '.join(f'{x:.2f}' for x in b['rho_one'])} / {', '.join(f'{x:.2f}' for x in b['rho_two'])} |")
    v10 = [r for r in d08_rows if r["year"] == 10]
    L += ["",
          "## 3. Why: the two groups of D08 are not where this spike is",
          "",
          f"The candidate gives a family with **no** edge a probability of {np.mean([r['slab_null'] for r in v10]):.2f} of "
          f"being in the slab at year 10, against {np.mean([r['slab_edge'] for r in v10]):.2f} for a family with one: it "
          "cannot tell them apart, and it does not need to. The spike says \"this family's forward edge has nothing to do "
          "with its apparent edge\". In D08 a family is the best of 20 by its **exploration** window; the reserve estimate "
          "the model reads comes from the window after it and is not selected on. So a family with no edge has an apparent "
          "edge near zero as well, and the slab already describes it: `θ = ρ · a` with `a` near zero is near zero. The "
          "retention the model learns is 0.65 to 0.91 with one group or with two (last column above), which is right for "
          "D08: an edge that is there stays. What the share measures is therefore the share of families whose forward edge "
          "follows their apparent edge, and in D08 that is nearly all of them. **D08's two groups are in the apparent edge "
          "`a_f` itself** (two thirds at zero, one third at 0.5 to 1.5), which is the prior of `a_f`, one hump with a "
          "learned centre and spread; a spike in the retention does not change that prior.",
          "",
          "Checked on the worlds themselves (`apparent`, no model): the family portfolio's sample Sharpe ratio, mean over "
          "families.",
          "",
          "| replication | families with no edge / with one | no edge: exploration window (selected on) | **no edge: reserve "
          "window (what the model reads)** | with an edge: exploration window | with an edge: reserve window | with an "
          "edge: true Sharpe ratio |",
          "|---|---|---|---|---|---|---|"]
    for r in json.loads((HERE / "spike_apparent.json").read_text(encoding="utf-8")):
        L.append(f"| {r['rep']} | {r['n_null']} / {r['n_edge']} | {r['explore_null_mean']:.2f} | **{r['reserve_null_mean']:.2f}** "
                 f"(sd {r['reserve_null_sd']:.2f}) | {r['explore_edge_mean']:.2f} | {r['reserve_edge_mean']:.2f} | "
                 f"{r['true_edge_mean']:.2f} |")
    L += ["",
          "Selection inflates the exploration window (0.7 for a family with nothing) and leaves the reserve window alone "
          "(about zero, with the spread sampling error gives): on the reserve the two groups are already apart.",
          "",
          "## 4. The same check on data drawn from the candidate itself",
          "",
          "To see whether the failure is in the algebra or in the fit to D08: families drawn from the two-group model "
          "(share 0.35; apparent edges Normal(1.0, 0.35²), so that a spike family has a high apparent edge and nothing "
          "forward; retention 0.7; reserve window 1,750 days; forward records of a quarter to `horizon` years; 12 draws a "
          "row).",
          "",
          "| families | forward records up to | posterior mean of the share (true 0.35) | posterior sd | mean absolute error | "
          "log likelihood, best node minus worst | identified by the criterion |",
          "|---|---|---|---|---|---|---|"]
    for n, h in sorted({(r["families"], r["horizon"]) for r in syn}):
        v = [r for r in syn if (r["families"], r["horizon"]) == (n, h)]
        sd = float(np.mean([r["share_sd"] for r in v]))
        err = float(np.mean([abs(r["share_mean"] - r["true_share"]) for r in v]))
        L.append(f"| {n} | {h:g} years | {np.mean([r['share_mean'] for r in v]):.3f} | {sd:.3f} | {err:.3f} | "
                 f"{np.mean([r['loglik_range'] for r in v]):.1f} | {'yes' if sd <= SD_MAX and err <= ERR_MAX else 'no'} |")
    L += ["",
          "Where the world is the candidate's own, 240 families with up to ten forward years recover the share, and the 96 "
          "families a programme has at year 4 do not (the posterior stays near the prior's 0.5). So the algebra is right, "
          "the share can be learned when the two groups differ in retention and the records are long, and even then V6's "
          "first decision date comes too early for it.",
          "",
          "## 5. Calibration, for the record",
          "",
          "The candidate was not to be adopted unless D08's calibration improved and no other scenario worsened beyond its "
          "bound. The first test failed, so the other scenarios were not run. D08's own figures, by the pipeline's "
          "estimator (`metrics.ece_ci`: bins with at least 200 observations, percentile interval over replications):",
          "",
          "| date | one group (the model of Protocol 3.1) | two groups (the candidate) | bound on the upper end |",
          "|---|---|---|---|"]
    for y in (4, 10):
        v = [r for r in d08_rows if r["year"] == y]
        one = metrics.ece_ci([tuple(r["cal_one"]) for r in v])
        two = metrics.ece_ci([tuple(r["cal_two"]) for r in v])
        L.append(f"| year {y} | {one[0]:.3f} ({one[1]:.3f} to {one[2]:.3f}) | {two[0]:.3f} ({two[1]:.3f} to {two[2]:.3f}) | 0.10 |")
    v = v10
    for k, name in (("cal_one", "one group"), ("cal_two", "two groups")):
        n, t, pp = (np.sum([r[k][i] for r in v], axis=0) for i in range(3))
        L += ["", f"Year 10, {name}: stated probability / observed share with an edge / families, by bin: "
              + "; ".join(f"{pp[i] / n[i]:.2f} / {t[i] / n[i]:.2f} / {int(n[i])}" for i in range(BINS) if n[i]) + "."]
    L += ["",
          "At year 10, where the limitation is, the error is all but unchanged (the middle of the scale still says too "
          "much: families given about 0.45 have an edge about a fifth of the time under either model) and the interval's "
          "upper end stays above the bound. At year 4 the candidate is better, and D08 was already inside its bound there.",
          "",
          "## 6. What was done with it",
          "",
          "- **Stopped, as the brief said.** The candidate is in no code list of `manhattan/sim/run.py`, the HB pipeline "
          "does not import it, it has no posterior draws for the dormancy forecast, and no pilot was run with it.",
          "- **D08 stays a documented limitation** (Protocol 3.1 §7.2(d), which now cites this file). If the full run "
          "confirms the error, V6 fails in D08 and the posterior-based tiers stay off (SIM_PREREG_v2 §5).",
          "- **Kept:** `manhattan/stats/hier_spike.py`, its five tests and this script, so the check can be repeated.",
          "- **What a repair would have to be**, from section 3: two groups in the apparent edge `a_f` (a share of families "
          "at zero on the reserve window as well as forward), not in the retention. `DORMANCY_DIAGNOSIS.md` part 2 measured "
          "a prior of that shape given the truth (calibration error 0.009), and the second session of 2026-11-13 measured a "
          "crude fitted one (0.013 in D08, but 0.034 against 0.014 in D02, where edges are rare). It is another model, it "
          "would be built on the scenarios' convention that a family with no edge has a mean of exactly zero, and it is "
          "Ethan's to ask for (ETHAN_ACTIONS item 21(b)).",
          "",
          "## 7. What this file does not show",
          "",
          "1. Anything at the pre-registered count: 12 replications of one scenario.",
          "2. The candidate under the other five models (S1 to S5): the central model only.",
          "3. The candidate in D01, D02, D05 or D10: not run, because the first test failed.",
          "4. That no two-group prior can be identified: only that this one, a spike in the retention, is not what D08 needs.",
          ""]
    (HERE.parent / "D08_SPIKE_SLAB.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote", HERE.parent / "D08_SPIKE_SLAB.md")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "synthetic":
        synthetic()
    elif what == "d08":
        d08(int(sys.argv[2]) if len(sys.argv) > 2 else 12)
    elif what == "apparent":
        apparent()
    elif what == "report":
        report()
    else:
        print(__doc__)
