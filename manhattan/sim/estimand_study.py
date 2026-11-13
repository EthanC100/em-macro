"""What the forward e-process tests, measured on synthetic series (session 6M; a study, not a pre-registered run).

    python -m manhattan.sim.estimand_study --out results/manhattan_sim/v2/estimand_study.json

Protocol section 6.3 tests the **truncated** null ``E[max(Z_t, −c) | past] ≤ 0`` on weekly returns standardised
by an ex-ante scale, and bets only in weeks the variance-ratio rule allows (section 6.7). Three questions:

1. How far apart are the truncated mean ``E[Y]`` and the untruncated mean ``E[Z]``, and how often do they (and
   their sample versions over 2, 5 and 10 years) differ in sign, under fat tails and under jumps?
2. Does skipping weeks by a rule that looks only at the past keep the wealth process a supermartingale under the
   null, what happens when a week is dropped after it has been seen, and what does skipping do to the meaning of
   a rejection?
3. How would the tail-risk check proposed in ``ESTIMAND_AND_TAIL_RISK.md`` behave on the same series?

**This is not a held-out scenario.** It simulates single return series on a fixed grid of parameters written
below. It runs no programme, no screening, no e-LOND and no metric of SIM_PREREG.md, draws nothing from the
held-out generator (``seeds.heldout_rng``), and changes no method. Its random streams are its own
(``SEED``), so it consumes none of the pre-registration's.

The transforms are the protocol's own code (``manhattan.stats.eprocess``): the ex-ante scale, the weekly sums,
the truncation at 6, the variance-ratio rule and the six-fraction wealth.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import chi2

from manhattan.stats import eprocess

SEED = 20261113
YEAR, WEEK = 252, 5
BURN = 252                                  # days of history before the first test week (scale and variance ratio)
YEARS = 10
HORIZONS = (2, 5, 10)
SCALE_FLOOR = 0.5                           # the simulation's convention: half the declared daily volatility of 1
C = eprocess.C_WEEKLY
CHUNK = 250                                 # paths at a time: bounds the memory of the variance-ratio windows
DEFAULT_STRESS = 2 * C                      # the proposed check's floor for a declared stress loss: twice the truncation point
GARCH = (0.02, 0.10, 0.88)


@dataclass(frozen=True)
class Dgp:
    """One return process: daily return = mean + noise − crash, in units of the noise's daily standard deviation.

    ``sharpe`` is the **true annualised Sharpe ratio of the untruncated return**, crashes included: the mean is
    set so that it holds exactly. ``J`` is the size of a crash in daily standard deviations of the noise and
    ``per_decade`` the expected number of crashes in ten years; ``symmetric`` crashes take either sign."""
    name: str
    dist: str = "normal"                    # "normal", "t3", "t5"
    garch: bool = False
    J: float = 0.0
    per_decade: float = 0.0
    symmetric: bool = False
    sharpe: float = 0.0

    @property
    def p(self) -> float:
        return self.per_decade / (YEARS * YEAR)

    @property
    def daily_sd(self) -> float:
        p = self.p
        return math.sqrt(1.0 + (p if self.symmetric else p * (1.0 - p)) * self.J**2)

    @property
    def daily_mean(self) -> float:
        return self.sharpe * self.daily_sd / math.sqrt(YEAR)

    @property
    def premium(self) -> float:
        """Daily mean outside crashes: what the strategy earns while nothing happens."""
        return self.daily_mean + (0.0 if self.symmetric else self.p * self.J)


def _noise(rng, shape, dist):
    if dist == "normal":
        return rng.standard_normal(shape)
    df = int(dist[1:])
    return rng.standard_t(df, shape) * math.sqrt((df - 2) / df)


def _garch_sigma(z: np.ndarray) -> np.ndarray:
    w, a, b = GARCH
    s2 = np.ones(z.shape[0])
    out = np.empty_like(z)
    for t in range(z.shape[1]):
        out[:, t] = np.sqrt(s2)
        s2 = w + (a * z[:, t] ** 2 + b) * s2
    return out


def simulate(d: Dgp, paths: int, rng: np.random.Generator) -> np.ndarray:
    """``(paths, BURN + 10 years)`` daily returns."""
    days = BURN + YEARS * YEAR
    e = _noise(rng, (paths, days), d.dist)
    if d.garch:
        e = e * _garch_sigma(e)
    x = d.premium + e
    if d.J:
        hit = rng.random((paths, days)) < d.p
        sign = np.where(rng.random((paths, days)) < 0.5, 1.0, -1.0) if d.symmetric else 1.0
        x = x - d.J * hit * sign
    return x


def weekly(x: np.ndarray) -> dict:
    """The protocol's weekly inputs for every path: ``Z``, ``Y``, ``bet`` and the weekly scale ``s`` (each
    ``(paths, weeks)``)."""
    n_weeks = YEARS * YEAR // WEEK
    out = {"Z": [], "Y": [], "bet": [], "s": []}
    for a in range(0, x.shape[0], CHUNK):
        wi = eprocess.weekly_inputs(x[a : a + CHUNK], BURN, n_weeks, SCALE_FLOOR)
        for k in out:
            out[k].append(wi[k])
    return {k: np.concatenate(v) for k, v in out.items()}


def poisson_upper(n: np.ndarray, level: float = 0.95) -> np.ndarray:
    """One-sided upper confidence bound for a Poisson mean after ``n`` events (3.00 for none: the rule of three)."""
    return 0.5 * chi2.ppf(level, 2 * (np.asarray(n) + 1))


def tail_check(Z: np.ndarray, Y: np.ndarray, L: float) -> np.ndarray:
    """The proposed check (not adopted): the truncated record's total gain must pay for the losses beyond the
    truncation point that the record cannot rule out at 95%, each taken at the declared stress loss ``L``
    (in ex-ante weekly standard deviations), and the untruncated record must be positive.

        Σ Y  −  U_95(N_trunc) · (max(L, worst observed loss) − c)  >  0     and     Σ Z > 0
    """
    n_trunc = (Y > Z).sum(axis=1)
    worst = np.maximum(L, -Z.min(axis=1))
    return (Y.sum(axis=1) - poisson_upper(n_trunc) * (worst - C) > 0) & (Z.sum(axis=1) > 0)


def crossing(Y: np.ndarray, bet: np.ndarray, level: float) -> float:
    """Share of paths whose six-fraction wealth ever reaches ``level``."""
    cum = eprocess.cumulative_log(eprocess.log_increments(Y, bet))            # (paths, 6, weeks + 1)
    wealth = np.exp(cum).mean(axis=1)
    return float((wealth.max(axis=1) >= level).mean())


def study_signs(d: Dgp, paths: int, rng: np.random.Generator) -> dict:
    """Question 1 for one process. Population means: ``E[Z] = E[week's return] · E[1/s]`` exactly, because the
    scale is fixed before the week, so its sign is the sign of the true Sharpe ratio; ``E[Y] = E[Z] + gap`` with
    ``gap = E[(−c − Z)⁺]`` estimated from the simulated weeks."""
    w = weekly(simulate(d, paths, rng))
    Z, Y = w["Z"], w["Y"]
    sd_z = float(Z.std())
    ez = WEEK * d.daily_mean * float((1.0 / w["s"]).mean())
    gap = float((Y - Z).mean())
    se = float((Y - Z).mean(axis=1).std(ddof=1) / math.sqrt(paths))
    crash_weekly = d.J / math.sqrt(WEEK)                          # a crash in ex-ante weekly standard deviations
    honest = max(DEFAULT_STRESS, crash_weekly)
    out = {"name": d.name, "sharpe": d.sharpe, "J": d.J, "per_decade": d.per_decade, "paths": paths,
           "premium_sharpe": d.premium * math.sqrt(YEAR), "crash_in_weekly_sd": crash_weekly,
           "mean_Z": ez, "mean_Y": ez + gap, "gap": gap, "gap_se": se,
           "gap_sharpe": gap / sd_z * math.sqrt(52), "truncated_sharpe": (ez + gap) / sd_z * math.sqrt(52),
           "population_sign_differs": bool(ez <= 0 and ez + gap - 2 * se > 0),
           "share_weeks_truncated": float((Y > Z).mean()), "declared_stress": honest}
    for h in HORIZONS:
        n = h * 52
        zb, yb = Z[:, :n].mean(axis=1), Y[:, :n].mean(axis=1)
        out[f"y{h}_sign_differs"] = float(((yb > 0) & (zb <= 0)).mean())
        out[f"y{h}_no_truncated_week"] = float(((Y[:, :n] > Z[:, :n]).sum(axis=1) == 0).mean())
        out[f"y{h}_truncated_positive"] = float((yb > 0).mean())
        out[f"y{h}_untruncated_positive"] = float((zb > 0).mean())
        out[f"y{h}_check_floor"] = float(tail_check(Z[:, :n], Y[:, :n], DEFAULT_STRESS).mean())
        out[f"y{h}_check_declared"] = float(tail_check(Z[:, :n], Y[:, :n], honest).mean())
    return out


def sign_grid() -> list[Dgp]:
    out = []
    for sr in (-0.25, 0.0, 0.5, 1.0):
        out += [Dgp("normal", sharpe=sr), Dgp("Student-t, 3 df", dist="t3", sharpe=sr),
                Dgp("Student-t, 5 df, GARCH", dist="t5", garch=True, sharpe=sr),
                Dgp("two-sided jumps of 20, 5 a decade", J=20, per_decade=5, symmetric=True, sharpe=sr)]
    for J in (10.0, 20.0, 40.0, 100.0):
        for k in (0.5, 1.0, 2.0, 5.0):
            for sr in (-0.25, 0.0):
                out.append(Dgp(f"crash of {J:g}, {k:g} a decade", J=J, per_decade=k, sharpe=sr))
    return out


def study_skipping(paths: int, rng: np.random.Generator) -> list[dict]:
    """Question 2. Nulls with conditional mean exactly zero; the wealth is watched every week for ten years.
    Ville's bound for reaching 20 is 0.05, for reaching 100 it is 0.01. The third rule of each series is
    deliberately invalid: it drops a week after seeing it."""
    rows = []
    nulls = [Dgp("normal", sharpe=0.0), Dgp("Student-t, 3 df", dist="t3", sharpe=0.0),
             Dgp("Student-t, 5 df, GARCH", dist="t5", garch=True, sharpe=0.0)]
    for d in nulls:
        x = simulate(d, paths, rng)
        w = weekly(x)
        rules = (("always bet", np.ones_like(w["bet"])), ("variance-ratio rule (past only)", w["bet"]),
                 # not a rule of the protocol: a week is dropped after it is seen (a loss beyond 2 standard
                 # deviations is called a data problem). It shows that the protection is predictability.
                 ("weeks dropped after the fact (Z < -2)", w["Z"] >= -2.0))
        for label, bet in rules:
            rows.append({"series": d.name, "rule": label, "bet_rate": float(bet.mean()),
                         "reach_20": crossing(w["Y"], bet, 20.0), "reach_100": crossing(w["Y"], bet, 100.0),
                         "mean_Y_bet_weeks": float(w["Y"][bet].mean()), "mean_Y_all_weeks": float(w["Y"].mean()),
                         "paths": paths})
    # what skipping changes: the weeks that are tested. A series with zero mean overall whose mean depends on a
    # state the rule can see: trending spells (first-order autocorrelation 0.35, negative mean) alternate with
    # quiet spells (no autocorrelation, positive mean).
    days = BURN + YEARS * YEAR
    state = np.zeros((paths, days), dtype=bool)
    s = rng.random(paths) < 0.4
    stay_t, stay_q = 1 - 1 / 378.0, 1 - 1 / 567.0                # mean spells of 1.5 and 2.25 years: 40% trending
    for t in range(days):
        state[:, t] = s
        flip = rng.random(paths) > np.where(s, stay_t, stay_q)
        s = s ^ flip
    e = rng.standard_normal((paths, days))
    x = np.empty_like(e)
    prev = np.zeros(paths)
    phi = 0.35
    for t in range(days):
        prev = np.where(state[:, t], phi * prev + math.sqrt(1 - phi**2) * e[:, t], e[:, t])
        x[:, t] = prev
    mu = 1.0 / math.sqrt(YEAR)                                   # quiet spells: annualised Sharpe 1
    x = x + np.where(state, -mu * 0.6 / 0.4, mu)                 # trending spells lose it back: mean zero overall
    w = weekly(x)
    for label, bet in (("always bet", np.ones_like(w["bet"])), ("variance-ratio rule (past only)", w["bet"])):
        rows.append({"series": "zero mean overall; gains in quiet spells, losses in trending spells", "rule": label,
                     "bet_rate": float(bet.mean()), "reach_20": crossing(w["Y"], bet, 20.0),
                     "reach_100": crossing(w["Y"], bet, 100.0), "mean_Y_bet_weeks": float(w["Y"][bet].mean()),
                     "mean_Y_all_weeks": float(w["Y"].mean()), "paths": paths})
    return rows


def run(paths: int = 2000, skip_paths: int = 4000) -> dict:
    root = np.random.SeedSequence(SEED)
    grid = sign_grid()
    kids = root.spawn(len(grid) + 1)
    signs = [study_signs(d, paths, np.random.default_rng(k)) for d, k in zip(grid, kids)]
    return {"seed": SEED, "paths": paths, "c": C, "horizons_years": list(HORIZONS), "signs": signs,
            "skipping": study_skipping(skip_paths, np.random.default_rng(kids[-1]))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.estimand_study", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--paths", type=int, default=2000)
    ap.add_argument("--skip-paths", type=int, default=4000)
    a = ap.parse_args(argv)
    res = run(a.paths, a.skip_paths)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
