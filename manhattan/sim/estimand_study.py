"""What the forward e-process tests, measured on synthetic series (session 6M; a study, not a pre-registered run).

    python -m manhattan.sim.estimand_study --out results/manhattan_sim/v2/estimand_study.json
    python -m manhattan.sim.estimand_study --report results/manhattan_sim/v2/ESTIMAND_AND_TAIL_RISK.md

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




# ------------------------------------------------------------------ the tables of ESTIMAND_AND_TAIL_RISK.md

def _row(s: dict) -> str:
    lo = f"({-s['gap_sharpe']:.3f}, 0]" if s["gap_sharpe"] >= 0.0005 else "none"
    return (f"| {s['name']} | {s['crash_in_weekly_sd']:.1f} | {s['share_weeks_truncated'] * 520:.1f} | {s['gap_sharpe']:.3f} | {lo} |")


def tables(res: dict) -> dict:
    """Markdown tables from a result of ``run``: population gap, sample sign disagreement, the proposed check,
    and the skipping experiment."""
    signs = res["signs"]
    zero = [s for s in signs if s["sharpe"] == 0.0]
    T = {}
    T["population"] = "\n".join(
        ["| process | a crash in ex-ante weekly standard deviations | weeks truncated per decade | truncated mean minus "
         "untruncated mean, in annualised Sharpe units | true Sharpe ratios for which the two means have opposite signs |",
         "|---|---|---|---|---|"] + [_row(s) for s in zero])
    cut = lambda s, k: " / ".join(f"{s[f'y{h}_{k}']:.3f}" for h in res["horizons_years"])
    T["sample"] = "\n".join(
        ["| process | true Sharpe | truncated mean positive while the untruncated mean is not, after 2 / 5 / 10 years | "
         "no week truncated yet, after 2 / 5 / 10 years |", "|---|---|---|---|"]
        + [f"| {s['name']} | {s['sharpe']:+.2f} | {cut(s, 'sign_differs')} | {cut(s, 'no_truncated_week')} |"
           for s in signs if s["sharpe"] <= 0.0])
    T["check"] = "\n".join(
        ["| process | true Sharpe | declared stress loss (weekly standard deviations) | truncated record positive, 2 / 5 / 10 years | "
         "**check passed with the stress loss declared**, 2 / 5 / 10 years | check passed with only the floor of 12 declared |",
         "|---|---|---|---|---|---|"]
        + [f"| {s['name']} | {s['sharpe']:+.2f} | {s['declared_stress']:.1f} | {cut(s, 'truncated_positive')} | "
           f"**{cut(s, 'check_declared')}** | {cut(s, 'check_floor')} |" for s in signs])
    T["skipping"] = "\n".join(
        ["| series | rule | share of weeks with a bet | wealth ever reaches 20 (bound 0.05 under the null) | ever reaches 100 "
         "(bound 0.01) | mean of Y in the weeks bet on | mean of Y in all weeks |", "|---|---|---|---|---|---|---|"]
        + [f"| {r['series']} | {r['rule']} | {r['bet_rate']:.3f} | {r['reach_20']:.4f} | {r['reach_100']:.4f} | "
           f"{r['mean_Y_bet_weeks']:+.4f} | {r['mean_Y_all_weeks']:+.4f} |" for r in res["skipping"]])
    return T


def report(res: dict) -> str:
    """ESTIMAND_AND_TAIL_RISK.md: the argument is written here; every number is read from ``res``."""
    T = tables(res)
    z = [s for s in res["signs"] if s["sharpe"] == 0.0]
    fat = [s["gap_sharpe"] for s in z if s["J"] == 0 and s["name"] != "normal"]
    by_j = {J: [s for s in z if s["J"] == J and s["name"].startswith("crash")] for J in (10.0, 20.0, 40.0, 100.0)}
    rng_ = lambda J, k: f"{min(s[k] for s in by_j[J]):.2f} to {max(s[k] for s in by_j[J]):.2f}"
    neg = [s for s in res["signs"] if s["sharpe"] < 0 and s["population_sign_differs"]]
    crash = [s for s in res["signs"] if s["sharpe"] <= 0 and s["name"].startswith("crash")]
    worst = max(max(s[f"y{h}_sign_differs"] for h in res["horizons_years"]) for s in crash)
    hon = {(s["name"], s["sharpe"]): s for s in res["signs"] if s["sharpe"] > 0}
    c3 = lambda s: " / ".join(f"{s[f'y{h}_check_declared']:.2f}" for h in res["horizons_years"])
    sk = {(r["series"], r["rule"]): r for r in res["skipping"]}
    nulls = [r for r in res["skipping"] if not r["series"].startswith("zero mean")]
    fair = [r["reach_20"] for r in nulls if r["rule"].startswith("variance")]
    cheat = [r["reach_20"] for r in nulls if r["rule"].startswith("weeks dropped")]
    spell = [r for r in res["skipping"] if r["series"].startswith("zero mean")]
    L = f"""# The forward e-process: what a rejection proves, what truncation hides, a tail-risk check, and week-skipping

Written by `python -m manhattan.sim.estimand_study --report` (session 6M, 2026-11-13). **Synthetic series only.
Nothing here is adopted: Protocol section 6 is word for word what it was, and the check of section 3 is a proposal
for Ethan (ETHAN_ACTIONS item 23).**

The simulation behind sections 2 to 4 is `manhattan/sim/estimand_study.py`: single return series, {res['paths']:,}
paths of ten years for each process, run through the protocol's own code for the ex-ante scale, the weekly sums,
the truncation at 6 and the variance-ratio rule (`manhattan.stats.eprocess`). **It is not a held-out scenario**: no
programme, no screening, no e-LOND and no metric of the pre-registration is computed, nothing is drawn from the
held-out generator, its random streams are its own, and no method was changed after seeing it.

## 1. What a rejection proves, exactly

**The objects.** For each component `j` of family `f` (each hypothesis portfolio and the family portfolio) and each
test week `t` after the family's enrolment:

- `P_(j,t)`: the week's sum of the component's daily **core-hedged, net** returns. Hedge ratios come from data
  before each day (Protocol §2.2); costs are the modelled ones.
- `s_(j,t)`: the weekly scale, fixed before the week from earlier days.
- `Y_(j,t) = max( P_(j,t) / s_(j,t) , −6 )`: the standardised return with any loss beyond six scales counted as
  six.
- `b_(j,t)`: 1 if the component bets that week, 0 if the variance-ratio rule, looking at the 252 days before the
  week, says not to (§6.7).
- Wealth `W_j` is the equal-weight mean, over six fixed fractions `λ`, of `Π_t ( 1 + λ · b_(j,t) · Y_(j,t) )`, and
  `W_f` is the mean of the components' wealth (§6.4, §6.5).

**The null that is tested.**

```
H0_f :  for every component j of f and every week t after enrolment in which j bets,
        E[ max( P_(j,t) / s_(j,t) , −6 )  |  everything recorded before the week ]  ≤  0
```

Under `H0_f` every factor `1 + λ b Y` has conditional expectation at most 1 and is at least 0.1, so `W_f` is a
non-negative supermartingale started at 1. e-LOND rejects when `W_f` reaches the family's bar and keeps the false
discovery rate over all enrolled families at or below 5% at every time, under any dependence (§6.8, Appendix
A.2).

**So "family `f` is formally supported" proves this and no more**, with that error rate:

> For at least one component of `f`, in at least one week in which it bet, the conditional mean, given the past,
> of the week's **core-hedged net** return **with any loss beyond six ex-ante weekly standard deviations counted
> as a loss of exactly six** was positive.

Because `s_(j,t)` is positive and known before the week, the standardisation changes nothing in that sentence:
`E[max(P/s, −6) | past] > 0` is the same event as `E[max(P, −6s) | past] > 0`.

Word by word:

| word | what it means | what it does not mean |
|---|---|---|
| truncated | each week's loss is capped at six ex-ante weekly standard deviations before the mean is taken | the mean of the return itself is positive. `Y ≥ Z` always, so the truncated mean is the larger one; the gap is the expected loss beyond the cap (section 2) |
| core-hedged | the return left after the **estimated** hedge of §2.2, with what that hedge lets through | a new mechanism. A hedge that lags leaves part of a core factor's premium in it (§2.2) |
| net | after the cost model | after real costs. Tiers above Statistically supported need measured costs (§8) |
| at least one component | a hypothesis portfolio or the family portfolio | which one (§6.10 names components at a stricter bar), or all of them |
| at least one week | the conditional mean was positive at some time | at every time, on average over time, or today. An edge that existed and decayed is validly rejected, and so is a strategy with zero mean overall whose mean is positive in spells the past reveals (section 4, last rows) |
| in which it bet | weeks the variance-ratio rule allowed | the weeks it skipped. Those are not tested at all (section 4) |
| given the past | the shared record of every family | given the family's own past only |

**The guard adds one thing, and it is not in the 5% accounting.** At the moment of rejection the running mean of
the **untruncated** standardised return of the leading component, over **all** weeks since enrolment (skipped
ones included), has an asymptotic 95% lower confidence bound above zero (§6.3). That stops a rejection when the
truncated and untruncated **records** disagree. It cannot see a loss that has not happened yet.

**A profitability claim needs more than a rejection.** "This family makes money" is a statement about the mean
of the untruncated return, over all weeks, after real costs, from now on. A rejection gives none of the four.
Section 2 measures the first gap; section 3 proposes a check for it.

## 2. How often the truncated and the untruncated mean differ in sign

**Population.** The scale is fixed before the week, so the sign of `E[Z]` is the sign of the true Sharpe ratio,
exactly. `E[Y] = E[Z] + gap`, where `gap = E[(−6 − Z)⁺]` is the expected loss beyond the cap. The two means
have opposite signs exactly when the true Sharpe ratio is zero or negative and the gap is larger than `|E[Z]|`:
in annualised Sharpe units, when the true Sharpe ratio lies in `(−gap, 0]`. Processes with a true Sharpe ratio of
zero (the gap barely moves with the mean):

{T['population']}

A crash is one day's loss of the stated number of daily standard deviations; the mean outside crashes is set so
that the Sharpe ratio of the whole return, crashes included, is the stated one.

- **Fat tails without a direction do almost nothing.** Student-t with 3 degrees of freedom, and Student-t with 5
  and volatility clustering: the gap is {min(fat):.3f} to {max(fat):.3f} of a Sharpe ratio. The signs differ only
  for a strategy whose true Sharpe ratio is within about a hundredth below zero.
- **Jumps are what matter, and only when they are beyond the cap.** A crash of 10 daily standard deviations is
  4.5 weekly ones: inside the cap, nothing is hidden (gap {rng_(10.0, 'gap_sharpe')}). A crash of 20 (8.9
  weekly) hides {rng_(20.0, 'gap_sharpe')} of a Sharpe ratio, of 40 (17.9 weekly) {rng_(40.0, 'gap_sharpe')}, of
  100 (44.7 weekly) {rng_(100.0, 'gap_sharpe')}, rising with how often it happens (0.5 to 5 times a decade).
- **A strategy that loses money can have a positive truncated mean.** With a true Sharpe ratio of −0.25 the
  truncated mean is positive for: {', '.join(s['name'] for s in neg)}. For those the tested null is false
  although the strategy has no edge, and the test offers no protection, as §6.3 says. The table gives the size
  of that hole: up to {max(s['gap_sharpe'] for s in z):.2f} of a Sharpe ratio on this grid.

**Samples.** How often a record of 2, 5 and 10 years shows a positive truncated mean while its untruncated mean
is zero or negative (the only way the two can disagree), for true Sharpe ratios of 0 and −0.25:

{T['sample']}

- For fat tails without a direction the disagreement is at most a few records in a hundred.
- For crash processes it reaches {worst:.2f} on this grid. It grows with the length of the record, because a
  record must contain a crash before the two means can differ: the last column is the share of records in which
  no week has been truncated yet, where the truncated and untruncated records are the same record and both look
  fine. That case, the disaster that has not happened, is the one no test on returns can see.

## 3. A tail-risk check before any profitability claim (proposed, not adopted)

**The rule proposed.** Before a family is described as profitable, as having a positive mean return, or is made
Live-experiment eligible (§8.3), its leading component's forward record of `n` weeks must satisfy

```
Σ Y_t  −  U( N_trunc ) · ( L − 6 )  >  0          and          Σ Z_t  >  0
```

- `Σ Y_t`: the truncated record's total gain, in ex-ante weekly standard deviations (it is what the e-process
  bets on).
- `N_trunc`: the number of weeks truncated so far (already recorded, §6.3).
- `U(N)`: the one-sided 95% upper confidence bound for the mean of a Poisson count after `N` events: 3.00 after
  none (the rule of three), 4.74 after one, 6.30 after two.
- `L`: the stress loss of one week, in ex-ante weekly standard deviations: the largest of the loss the family
  spec declares under "tail exposure", the worst week on the family's whole record, and a floor of 12 (twice the
  cap).

**In plain English.** The record has gone `n` weeks with `N` weeks beyond the cap. That is compatible, at 95%,
with as many as `U(N)` such weeks in a stretch of this length. Charge the record for that many, each at the
declared stress loss less the six already counted. If what the capped record earned does not cover the charge,
the profit could be the premium for a crash that has merely not arrived, and no claim of profit is made. With no
truncated week and the floor, the capped record must have earned 18 weekly standard deviations in total.

**Why this form.** The gap of section 2 is `(crashes per week) × (loss beyond the cap)`. Returns cannot bound
either factor from a record without crashes (Protocol §6.2: Bahadur and Savage). The check takes the frequency
from the record itself, at the upper end of what the record allows, and the size from outside the record: the
spec's declared tail exposure, which the protocol already requires and the critic already reviews. Protocol
§6.3 rejected a tail charge **inside** the e-process, because with only a variance bound the charge kills every
edge. Here it is a separate, later gate with a declared size, and the test's exactness is untouched.

**What it costs an honest strategy** (share of records that pass, after 2 / 5 / 10 years):
Sharpe 0.5: normal {c3(hon[('normal', 0.5)])}, Student-t 3 {c3(hon[('Student-t, 3 df', 0.5)])};
Sharpe 1.0: normal {c3(hon[('normal', 1.0)])}, Student-t 3 {c3(hon[('Student-t, 3 df', 1.0)])}. A formal rejection
takes far longer than that (§6.9: 15 years at a Sharpe ratio of 1), so for the top tier the check would rarely
be the binding condition; for claims built on the posterior tiers after two to five years it would.

**What it stops** (all processes; the bold column is the proposal):

{T['check']}

- With the stress loss declared at its true size, a zero-mean strategy with crashes of 40 passes in at most
  {max(max(s[f'y{h}_check_declared'] for h in res['horizons_years']) for s in by_j[40.0]):.2f} of records and
  with crashes of 100 in at most {max(max(s[f'y{h}_check_declared'] for h in res['horizons_years']) for s in by_j[100.0]):.2f},
  while its truncated record is positive in up to {max(s['y10_truncated_positive'] for s in by_j[100.0]):.2f} of them.
- With only the floor declared the same strategies pass in up to
  {max(max(s[f'y{h}_check_floor'] for h in res['horizons_years']) for s in by_j[100.0]):.2f}: **an undeclared
  tail defeats the check**, as it defeats everything else. The declaration is the control; the check makes it
  bind.
- It is not a test of the mean and must not be read as one: a strategy with no edge and no crash passes it in
  about a fifth of ten-year records. It is a condition **added to** a rejection or a tier, never a substitute.
- For crashes inside twice the cap (10 and 20 daily standard deviations) the floor is the stress loss and the
  check adds little; there the hidden part is at most {max(s['gap_sharpe'] for s in by_j[20.0]):.2f} of a Sharpe ratio.

**What Ethan would decide** if he wants it: the level (95%), the floor (12), which claims it gates, and whether
a family that declares no tail exposure may make a profitability claim at all. Adopting it is a new protocol
version with its own simulation criterion; nothing in the repository applies it.

## 4. Does skipping weeks by a predictable rule preserve validity?

**Yes. Confirmed, with one condition and one consequence.**

**The argument.** Write the wealth of one fixed fraction as `W_t = W_(t−1) · ( 1 + λ · b_t · Y_t )`, with `b_t`
equal to 0 or 1. If `b_t` is a function of what was recorded before week `t`, then under the null

```
E[ W_t | past ]  =  W_(t−1) · ( 1 + λ · b_t · E[ Y_t | past ] )  ≤  W_(t−1),
```

because `λ b_t ≥ 0` is known and `E[Y_t | past] ≤ 0`. Each factor is at least `1 − 0.15 × 6 = 0.1`, so `W` is a
non-negative supermartingale and Ville's inequality holds: the probability of ever reaching `1/a` is at most
`a`. Skipping is betting the fraction zero, and a bet may be any non-negative number chosen from the past. The
mean over six fractions and over components keeps the property. Nothing about the rule matters except that it
looks only backwards: not its threshold, not whether it is a good rule.

**The condition.** `b_t` must be computable from the record as it stood before week `t`. In the code it is
(`eprocess.weekly_variance_ratio` reads the 252 days before the week's first day; a test alters the week and
everything after it and checks that the decision does not move). One sentence of the protocol leaves a gap for
production: §6.6 enters a week 7 days after it ends "using the values stored then", and §6.7 computes the
variance ratio from "the previous 252 trading days". If the final settlements of the last days before a week
arrive after that week has begun, a variance ratio computed from them is not a function of the past as §6.1
defines it. With complete, unrevised data, as in every simulation here, the two coincide. **Recommended wording
for a later version** (not made here; §6 is unchanged): "the variance ratio for week `t` uses the values on
record at the decision cut-off of week `t`".

**The numbers.** Series with conditional mean exactly zero, wealth watched every week for ten years
({res['skipping'][0]['paths']:,} paths each):

{T['skipping']}

- With the protocol's rule the wealth reaches 20 in {min(fair):.3f} to {max(fair):.3f} of null paths, the same
  as with no skipping, and well inside the bound of 0.05.
- The third rule of each series is not the protocol's: it drops a week **after seeing it** (a loss beyond two
  standard deviations is treated as a data problem). The wealth then reaches 20 in {min(cheat):.2f} to
  {max(cheat):.2f} of null paths. What protects the test is that the rule cannot see the week, which is why
  §6.6's rule that no observation is ever dropped matters as much as the skipping rule.

**The consequence: skipping changes what is tested.** The last two rows are a strategy whose mean over all
weeks is zero: it gains in quiet spells and gives it back in trending spells, and the variance-ratio rule skips
most of the trending weeks. The mean of `Y` in the weeks bet on is {spell[1]['mean_Y_bet_weeks']:+.3f} a week
against {spell[1]['mean_Y_all_weeks']:+.3f} in all weeks, and the wealth reaches 20 in
{spell[1]['reach_20']:.2f} of paths ({spell[0]['reach_20']:.2f} with no skipping, because the conditional mean
is positive in the quiet spells either way). Those rejections are **valid**: the null says the conditional mean
is never positive, and here it sometimes is. They are not evidence that holding the strategy every week makes
money. A claim about the strategy as held needs the record of all weeks, which is what the guard and the check
of section 3 look at.
"""
    return L


def _main_report(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.estimand_study --report")
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--json", type=Path, default=Path("results/manhattan_sim/v2/estimand_study.json"))
    a = ap.parse_args(argv)
    a.report.write_text(report(json.loads(a.json.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"wrote {a.report}")
    return 0


if __name__ == "__main__":
    sys.exit(_main_report() if "--report" in sys.argv else main())
