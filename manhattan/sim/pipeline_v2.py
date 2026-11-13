"""SIM_PREREG_v2, the screening and forward half: scenarios in which the core hedge is **estimated**.

Protocol v3.1 changes one thing here: the SPA test re-estimates the hedge in every resample
(``manhattan.stats.spa_hedged``). Where returns are hedged by construction there is no hedge to re-estimate and
the test is that of v3.0, so only two kinds of run are made by this module:

- **D11** (the full pipeline). Every family is first evaluated exactly as under version 1
  (``pipeline.evaluate_family``: the v3.0 test on the already hedged returns, the reserve e-value, the forward
  record). Its SPA p-values and Romano-Wolf statistics are then replaced by the hedge-aware ones, which feed
  screening candidate (i), the admission levels and every metric. The v3.0 p-values, and those of the same test
  on the **true** hedged returns (an oracle no real analysis has), are kept beside them, so every replication
  is a paired comparison of the three on the same resamples.
- **Hedged twins** ``D01h`` ... ``D08h`` (SPA only). A development scenario of version 1 with D11's hedge layer
  on top: the same true returns, drawn from the same seeds as the version 1 scenario, plus a core factor
  exposure that must be hedged by the live rule. They show whether the hedge-aware test keeps its size under fat
  tails, volatility clustering, serial correlation, correlated variants and selection. No screening or forward
  test is run on a twin: those are covered by the version 1 scenario.

The world is ``manhattan/sim/world.py`` untouched. The unhedged returns and the factor are rebuilt here from the
same random streams ``world._apply_hedge`` used; a test checks that hedging them reproduces the family's
returns exactly.
"""
from __future__ import annotations

import math
import time
from dataclasses import replace

import numpy as np

from manhattan.stats import hedge, screening, spa, spa_hedged

from . import pipeline, seeds, world

TWINS = {"D01h": "D01", "D02h": "D02", "D03h": "D03", "D04h": "D04", "D05h": "D05", "D06h": "D06",
         "D07ah": "D07a", "D07bh": "D07b", "D08h": "D08"}
METHODS = ("v31", "v30", "oracle")       # hedge-aware; v3.0 on the estimated hedge; v3.0 on the true hedged returns
WINDOW = (world.EXPLORE, world.RESERVE)


def scenario(scenario_id: str) -> world.Scenario:
    """The scenario object of a v2 run: D11 itself, or a version 1 scenario with the hedge layer."""
    if scenario_id in TWINS:
        base = world.SCENARIOS[TWINS[scenario_id]]
        return replace(base, id=scenario_id, title=base.title + ", with an estimated core hedge", sizes=("STD",),
                       e_all=(), hedge=True)
    scn = world.SCENARIOS[scenario_id]
    if not scn.hedge:
        raise ValueError(f"{scenario_id} has no estimated hedge: it is run under version 1")
    return scn


def stream_id(scenario_id: str) -> str:
    """A twin draws its world from its base scenario's streams, so its true returns are version 1's."""
    return TWINS.get(scenario_id, scenario_id)


def unhedged(fam: world.Family, streams: seeds.Streams, cm: world.Common) -> tuple[np.ndarray, np.ndarray]:
    """The family's unhedged returns ``(H·m, days)`` and the core factor ``(1, days)``, as ``world._apply_hedge``
    built them: the true hedged returns plus ``β_t C_t``, one ``β`` path per hypothesis."""
    H, m, days = fam.X.shape
    C = cm.factor[fam.freeze : fam.freeze + days]
    rng = streams.rng(seeds.FACTOR, fam.idx)
    beta = world.BETA_START + np.cumsum(rng.standard_normal((H, days)) * world.BETA_ANNUAL_SD / math.sqrt(world.YEAR), axis=1)
    return (fam.extra["true_X"] + beta[:, None, :] * C).reshape(H * m, days), C[None, :]


def three_tests(fam: world.Family, streams: seeds.Streams, cm: world.Common, v30: spa.SpaResult | None = None) -> dict:
    """The hedge-aware test, the v3.0 test on the estimated hedge and the v3.0 test on the true hedged returns,
    each from a fresh generator on the family's bootstrap stream (so they see the same block draws)."""
    H, m, _ = fam.X.shape
    w0, n = WINDOW
    r, C = unhedged(fam, streams, cm)
    boot = lambda: streams.rng(seeds.BOOTSTRAP, fam.idx)
    out = {"v31": spa_hedged.spa_test(r, boot(), factors=C, window=WINDOW)}
    out["v30"] = v30 or spa.spa_test(fam.X[:, :, w0 : w0 + n].reshape(H * m, n), boot())
    out["oracle"] = spa.spa_test(fam.extra["true_X"][:, :, w0 : w0 + n].reshape(H * m, n), boot())
    return out


def _family_row(fam: world.Family, res: dict) -> dict:
    """The few numbers kept of one family's three tests (the resampled statistics are dropped here)."""
    no_edge = (fam.theta <= 0).ravel()
    row = {"null": bool(fam.reserve_null), "has_null_variant": bool(no_edge.any())}
    for k, r in res.items():
        row[k] = (r.p_c, r.p_l, r.p_u, r.B, bool((spa.romano_wolf(r.tstat, r.tstar, 0.05) & no_edge).any()))
    row["L"] = res["v31"].L
    return row


def _spa_counts(rows: list[dict]) -> dict:
    """Counts behind M3 for each of the three tests, over the replication's families."""
    null = np.array([r["null"] for r in rows])
    out = {"n_reserve_null": int(null.sum()), "m3_rw_den": int(sum(r["has_null_variant"] for r in rows))}
    for k in METHODS:
        v = np.array([r[k] for r in rows], dtype=float)                  # p_c, p_l, p_u, B, Romano-Wolf error
        for a in pipeline.P_LEVELS:
            out[f"{k}_p{a}_num"] = int((v[null, 0] <= a).sum())
        out[f"{k}_pl05_num"] = int((v[null, 1] <= 0.05).sum())
        out[f"{k}_pu05_num"] = int((v[null, 2] <= 0.05).sum())
        out[f"{k}_rw_num"] = int(v[:, 4].sum())
        out[f"{k}_mean_B"] = float(v[:, 3].mean())
    out["mean_L"] = float(np.mean([r["L"] for r in rows]))
    return out


def run_spa_replication(scenario_id: str, rep: int, *, branch: int = seeds.DEVELOPMENT, sha: str | None = None,
                        size_name: str = "STD") -> dict:
    """One replication of a hedged twin: the three SPA tests on every family, nothing else."""
    t0 = time.time()
    scn, size = scenario(scenario_id), world.SIZES[size_name]
    streams = seeds.Streams(sha or seeds.prereg_hash(), branch, stream_id(scenario_id), size_name, rep)
    cm = world.common(scn, streams)
    rows = []
    for _, _, fams in world.batches(scn, size, streams):
        for fam in fams:
            rows.append(_family_row(fam, three_tests(fam, streams, cm)))
    out: dict = {"n_families": len(rows), **_spa_counts(rows)}
    out.update(scenario=scenario_id, size=size_name, rep=rep, branch=branch, kind="spa_only",
               seconds=round(time.time() - t0, 2))
    return out


def run_replication(scenario_id: str, size_name: str, rep: int, *, branch: int = seeds.DEVELOPMENT,
                    sha: str | None = None) -> dict:
    """One replication of D11 under version 2: the version 1 pipeline with the hedge-aware p-values of record,
    and the three tests' counts side by side."""
    t0 = time.time()
    scn, size = scenario(scenario_id), world.SIZES[size_name]
    streams = seeds.Streams(sha or seeds.prereg_hash(), branch, stream_id(scenario_id), size_name, rep)
    cm = world.common(scn, streams)
    procs = {"i": screening.BatchBH(size.N), "ii": screening.EbhElond(size.N)}
    evals: list[pipeline.FamilyEval] = []
    rows = []
    for _, _, fams in world.batches(scn, size, streams):
        batch_evals = []
        for fam in fams:
            ev = pipeline.evaluate_family(fam, streams)
            res = three_tests(fam, streams, cm, v30=ev.spa)
            new = res["v31"]
            ev.p_c, ev.p_l, ev.p_u, ev.B, ev.L, ev.spa = new.p_c, new.p_l, new.p_u, new.B, new.L, new
            ev.rw05 = spa.romano_wolf(new.tstat, new.tstar, 0.05)
            rows.append(_family_row(fam, res))
            batch_evals.append(ev)
        pipeline.decide_batch(batch_evals, procs)
        evals.extend(batch_evals)
    forward = {c: pipeline.forward_test(evals, c, size.N_F) for c in pipeline.CANDIDATES}
    out = pipeline.summarise(evals, scn, size, forward)
    extra = _spa_counts(rows)
    assert extra["n_reserve_null"] == out["n_reserve_null"] and extra["v31_p0.05_num"] == out["m3_p0.05_num"]
    out.update({k: v for k, v in extra.items() if k not in out})
    out.update(scenario=scenario_id, size=size_name, rep=rep, branch=branch, kind="full",
               seconds=round(time.time() - t0, 2))
    return out


def hedge_reproduces_the_world(fam: world.Family, streams: seeds.Streams, cm: world.Common) -> bool:
    """True when hedging the rebuilt unhedged returns gives the family's returns exactly (used by a test)."""
    H, m, days = fam.X.shape
    r, C = unhedged(fam, streams, cm)
    X, _ = hedge.hedged(r, C[0])
    return bool(np.array_equal(X.reshape(H, m, days), fam.X))
