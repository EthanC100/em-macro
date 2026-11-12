"""One replication: a whole simulated programme run through Protocol v3 (SIM_PREREG section 2.5).

For every family, at its freeze: the designated SPA test and Romano-Wolf step-down on the reserve window (frozen
grid only), the reserve e-value (the betting process replayed through the reserve), and the forward betting
record of its components. Then, batch by batch, both screening candidates; then the forward e-LOND, once per
screening candidate and, where the scenario asks, once with every family enrolled at its freeze (``E-ALL``).

Declared reductions (SIM_PREREG section 2.5): (a) the bootstrap stops at 9,999 resamples; (b) at STD and LONG the
hierarchical model is not fitted and enrolment is by the screening route only; (d) ``E-ALL``.

Conventions fixed here, where the pre-registration leaves a detail open (each is listed in the report):

- quarterly reviews are every 63 days from day 63; a family that passed screening is enrolled at the first review
  on or after its freeze, and its test process starts with the first week that begins on or after that review;
- a week's return enters the forward process one week after the week ends (the 7-day lag of Protocol v3
  section 6.6), so a rejection is dated two weeks after the start of the week that produced it;
- every executable's declared volatility target is 1 a day (the simulated unit), so the scale floor is 0.5 a day;
- sensitivity p-values at ``L/2`` and ``2L`` are not computed (they decide nothing).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from manhattan.stats import elond, eprocess, screening, spa
from manhattan.stats.schedule import gamma

from . import seeds, world

SCALE_FLOOR = 0.5
REVIEW_EVERY = 63
LAG_WEEKS = 1
RESERVE_WEEKS = world.RESERVE // world.WEEK
PROGRAMME_WEEKS = world.T_END // world.WEEK
CANDIDATES = ("i", "ii")
YEAR_CHECKPOINTS = (3, 5, 10)
CROSS = (20.0, 100.0)
P_LEVELS = (0.20, 0.05, 0.001)


@dataclass
class FamilyEval:
    idx: int
    batch: int
    freeze: int
    reserve_null: bool
    forward_null: bool
    has_edge: bool
    true_sharpe_f: float
    p_c: float
    p_l: float
    p_u: float
    B: int
    L: float
    E: float
    no_edge: np.ndarray                 # (variants,) True where the variant's historical edge is at most 0
    rw05: np.ndarray                    # (variants,) Romano-Wolf rejections at 0.05
    comp_null: np.ndarray               # (H + 1,) True where the component's forward mean is at most 0
    cum_fwd: np.ndarray = field(repr=False, default=None)    # (H + 1, 6, forward weeks + 1)
    Z_fwd: np.ndarray = field(repr=False, default=None)      # (H + 1, forward weeks)
    track_max: np.ndarray = None        # (H + 1,) largest tracking wealth from the freeze
    n_trunc: int = 0
    bet_rate: float = 1.0
    spa: spa.SpaResult = field(repr=False, default=None)
    passed: dict = field(default_factory=dict)       # candidate -> bool
    admission: dict = field(default_factory=dict)    # candidate -> a_f
    rw_adm_null: dict = field(default_factory=dict)  # candidate -> Romano-Wolf at a_f named a variant with no edge
    rw_adm_any: dict = field(default_factory=dict)
    p_adaptive: float | None = None     # D09b: SPA on the full set after the adaptive rounds
    adaptive_null: bool | None = None
    extra: dict = field(default_factory=dict)


def components(X: np.ndarray) -> np.ndarray:
    """Hypothesis portfolios and the family portfolio (Protocol v3 section 2.3): ``(H + 1, days)``."""
    ph = X.mean(axis=1)
    return np.vstack([ph, ph.mean(axis=0, keepdims=True)])


def evaluate_family(fam: world.Family, streams: seeds.Streams, *, adaptive_spa: bool = False,
                    keep_forward: bool = True) -> FamilyEval:
    """The designated evaluation of one blind family at its freeze, and its forward betting record."""
    H, m, days = fam.X.shape
    d = fam.X[:, :, world.EXPLORE : world.HISTORY].reshape(H * m, world.RESERVE)
    res = spa.spa_test(d, streams.rng(seeds.BOOTSTRAP, fam.idx))
    comps = components(fam.X)
    n_weeks = (days - world.EXPLORE) // world.WEEK
    wi = eprocess.weekly_inputs(comps, world.EXPLORE, n_weeks, SCALE_FLOOR)
    cum = eprocess.cumulative_log(eprocess.log_increments(wi["Y"], wi["bet"]))
    E = float(eprocess.family_wealth(eprocess.wealth_paths(cum[:, :, : RESERVE_WEEKS + 1]))[-1])
    cum_fwd = cum[:, :, RESERVE_WEEKS:] - cum[:, :, RESERVE_WEEKS : RESERVE_WEEKS + 1]
    track = np.exp(cum_fwd).mean(axis=1)
    ev = FamilyEval(
        idx=fam.idx, batch=fam.batch, freeze=fam.freeze, reserve_null=fam.reserve_null,
        forward_null=fam.forward_null, has_edge=fam.has_edge, true_sharpe_f=fam.true_sharpe_f,
        p_c=res.p_c, p_l=res.p_l, p_u=res.p_u, B=res.B, L=res.L, E=E,
        no_edge=(fam.theta <= 0).ravel(), rw05=spa.romano_wolf(res.tstat, res.tstar, 0.05),
        comp_null=fam.component_edges <= 0, track_max=track.max(axis=1),
        n_trunc=int(np.count_nonzero(wi["Y"][:, RESERVE_WEEKS:] > wi["Z"][:, RESERVE_WEEKS:])),
        bet_rate=float(wi["bet"].mean()), spa=res)
    if keep_forward:
        ev.cum_fwd, ev.Z_fwd = cum_fwd, wi["Z"][:, RESERVE_WEEKS:]
    if adaptive_spa and fam.X_adaptive is not None:
        full = np.concatenate([fam.X, fam.X_adaptive], axis=1)[:, :, world.EXPLORE : world.HISTORY]
        ev.p_adaptive = spa.spa_test(full.reshape(-1, world.RESERVE), streams.rng(seeds.ADAPTIVE_BOOT, fam.idx)).p_c
        ev.adaptive_null = bool(fam.reserve_null and np.all(fam.theta_adaptive <= 0))
    return ev


def decide_batch(evals: list[FamilyEval], procs: dict) -> None:
    """Both screening candidates on one batch, then Romano-Wolf at each passing family's admission level."""
    stats = {"i": np.array([e.p_c for e in evals]), "ii": np.array([e.E for e in evals])}
    for cand in CANDIDATES:
        dec = procs[cand].step(stats[cand])
        for e, rej in zip(evals, dec.rejected):
            e.passed[cand] = bool(rej)
            e.admission[cand] = dec.admission if rej else 0.0
            if rej:
                named = spa.romano_wolf(e.spa.tstat, e.spa.tstar, dec.admission)
                e.rw_adm_null[cand] = bool((named & e.no_edge).any())
                e.rw_adm_any[cand] = bool(named.any())
    for e in evals:
        e.spa = None                                   # the resampled statistics are not needed again


def enrolment(evals: list[FamilyEval], cand: str | None) -> list[tuple[int, FamilyEval]]:
    """(first test week, family) in enrolment order. ``cand=None`` enrols every family at its freeze (E-ALL)."""
    out = []
    for e in evals:
        if cand is None:
            out.append((e.freeze // world.WEEK, e.freeze, e))
        elif e.passed.get(cand):
            review = REVIEW_EVERY * max(1, math.ceil(e.freeze / REVIEW_EVERY))
            out.append((math.ceil(review / world.WEEK), review, e))
    out.sort(key=lambda r: (r[1], r[2].idx))
    return [(w, e) for w, _, e in out]


def forward_test(evals: list[FamilyEval], cand: str | None, N_F: int) -> dict:
    """Forward e-LOND for one enrolment rule. Returns the enrolled families, their rejection days (−1 if none)
    and the rejection count path by programme week."""
    enrolled = enrolment(evals, cand)
    n = len(enrolled)
    wealth = np.ones((n, PROGRAMME_WEEKS))
    guard = np.zeros((n, PROGRAMME_WEEKS), dtype=bool)
    start = np.zeros(n, dtype=int)
    for i, (week, e) in enumerate(enrolled):
        j0 = week - e.freeze // world.WEEK
        start[i] = week
        if j0 >= e.Z_fwd.shape[1]:
            start[i] = PROGRAMME_WEEKS
            continue
        cw = eprocess.wealth_paths(e.cum_fwd, start=j0)
        wealth[i, week:] = eprocess.family_wealth(cw)[1:]
        guard[i, week:] = eprocess.family_guard(cw, e.Z_fwd[:, j0:])
    out = elond.run(wealth, guard, start, N_F) if n else {"reject_at": np.zeros(0, int), "R": np.zeros(PROGRAMME_WEEKS, int)}
    day = np.where(out["reject_at"] >= 0, world.WEEK * (out["reject_at"] + 1 + LAG_WEEKS), -1)
    day = np.where(day > world.T_END, -1, day)                         # known only after the programme's end
    return {"families": [e for _, e in enrolled], "reject_day": day, "start_week": start}


def _fdp(rejected: int, false: int) -> float:
    return false / rejected if rejected else 0.0


def summarise(evals: list[FamilyEval], scn: world.Scenario, size: world.Size, forward: dict) -> dict:
    """The per-replication numbers behind metrics M1-M6, M10 and M11 (SIM_PREREG section 4)."""
    out: dict = {"n_families": len(evals)}
    B = size.B
    checkpoints = sorted({max(1, B // 4), B // 2, B})
    null = np.array([e.reserve_null for e in evals])
    batch = np.array([e.batch for e in evals])
    out["n_reserve_null"] = int(null.sum())
    for cand in CANDIDATES:
        passed = np.array([e.passed[cand] for e in evals])
        for k in checkpoints:
            upto = batch < k
            out[f"m1_{cand}_b{k}"] = _fdp(int((passed & upto).sum()), int((passed & upto & null).sum()))
            out[f"scr_rej_{cand}_b{k}"] = int((passed & upto).sum())
            out[f"scr_false_{cand}_b{k}"] = int((passed & upto & null).sum())
        out[f"m6_scr_num_{cand}"] = int((passed & ~null).sum())
        n_pass = int(passed.sum())
        bad = sum(1 for e in evals if e.passed[cand] and e.rw_adm_null[cand])
        out[f"m4_{cand}"] = _fdp(n_pass, bad)
        out[f"m4_n_{cand}"] = n_pass
        out[f"m4_bad_{cand}"] = bad
        out[f"rw_adm_any_{cand}"] = sum(1 for e in evals if e.passed[cand] and e.rw_adm_any[cand])
    out["m6_scr_den"] = int((~null).sum())
    p = {k: np.array([getattr(e, k) for e in evals]) for k in ("p_c", "p_l", "p_u")}
    for a in P_LEVELS:
        out[f"m3_p{a}_num"] = int((p["p_c"][null] <= a).sum())
    out["m3_pl05_num"] = int((p["p_l"][null] <= 0.05).sum())
    out["m3_pu05_num"] = int((p["p_u"][null] <= 0.05).sum())
    has_null_variant = np.array([e.no_edge.any() for e in evals])
    out["m3_rw_den"] = int(has_null_variant.sum())
    out["m3_rw_num"] = sum(1 for e in evals if (e.rw05 & e.no_edge).any())
    comp_null = np.concatenate([e.comp_null for e in evals])
    tmax = np.concatenate([e.track_max for e in evals])
    out["m5_den"] = int(comp_null.sum())
    for c in CROSS:
        out[f"m5_{int(c)}_num"] = int((tmax[comp_null] >= c).sum())
    q1 = world.T_END // 4
    for key, fw in forward.items():
        fams, day = fw["families"], fw["reject_day"]
        fnull = np.array([e.forward_null for e in fams], dtype=bool)
        out[f"fwd_enrolled_{key}"] = len(fams)
        for y in YEAR_CHECKPOINTS:
            hit = (day >= 0) & (day <= y * world.YEAR)
            out[f"m2_{key}_y{y}"] = _fdp(int(hit.sum()), int((hit & fnull).sum()))
            out[f"fwd_rej_{key}_y{y}"] = int(hit.sum())
            out[f"fwd_false_{key}_y{y}"] = int((hit & fnull).sum())
        sup = {e.idx: d for e, d in zip(fams, day) if d >= 0}
        target = [e for e in evals if not e.forward_null and e.freeze < q1]
        out[f"m6_fwd_den_{key}"] = len(target)
        out[f"m6_fwd_num_{key}"] = sum(1 for e in target if e.idx in sup)
        out[f"m6_fwd_years_{key}"] = [round((sup[e.idx] - e.freeze) / world.YEAR, 3) for e in target if e.idx in sup]
    if scn.adaptive == "reserve":
        an = np.array([bool(e.adaptive_null) for e in evals])
        pa = np.array([e.p_adaptive for e in evals])
        out["m11_den"] = int(an.sum())
        out["m11_num"] = int((pa[an] <= 0.05).sum())
    out["mean_B"] = float(np.mean([e.B for e in evals]))
    out["mean_L"] = float(np.mean([e.L for e in evals]))
    out["bet_rate"] = float(np.mean([e.bet_rate for e in evals]))
    out["n_trunc"] = int(sum(e.n_trunc for e in evals))
    return out


def run_replication(scenario_id: str, size_name: str, rep: int, *, branch: int = seeds.DEVELOPMENT,
                    sha: str | None = None, scenario: world.Scenario | None = None) -> dict:
    """One replication of a scenario at STD or LONG: the per-replication record for the metrics."""
    t0 = time.time()
    scn = scenario or world.SCENARIOS[scenario_id]
    size = world.SIZES[size_name]
    streams = seeds.Streams(sha or seeds.prereg_hash(), branch, scenario_id, size_name, rep)
    procs = {"i": screening.BatchBH(size.N), "ii": screening.EbhElond(size.N)}
    evals: list[FamilyEval] = []
    for _, _, fams in world.batches(scn, size, streams):
        batch_evals = [evaluate_family(f, streams, adaptive_spa=scn.adaptive == "reserve") for f in fams]
        decide_batch(batch_evals, procs)
        evals.extend(batch_evals)
    forward = {c: forward_test(evals, c, size.N_F) for c in CANDIDATES}
    if size_name in scn.e_all:
        forward["all"] = forward_test(evals, None, size.N_F_all)
    out = summarise(evals, scn, size, forward)
    out.update(scenario=scenario_id, size=size_name, rep=rep, branch=branch, seconds=round(time.time() - t0, 2))
    return out


def designated_statistics(scenario: world.Scenario, scenario_id: str, size_name: str, rep: int, *,
                          branch: int = seeds.DEVELOPMENT, sha: str | None = None, max_batches: int | None = None):
    """The blind p-values and e-values of record, in family order (for criterion V10(a))."""
    size = world.SIZES[size_name]
    streams = seeds.Streams(sha or seeds.prereg_hash(), branch, scenario_id, size_name, rep)
    p, e = [], []
    for b, _, fams in world.batches(scenario, size, streams):
        if max_batches is not None and b >= max_batches:
            break
        for f in fams:
            ev = evaluate_family(f, streams, keep_forward=False)
            p.append(ev.p_c); e.append(ev.E)
    return np.array(p), np.array(e)
