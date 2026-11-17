"""What the forward-record dormancy rule does to a family by arithmetic alone, at four review dates and at
quarterly reviews. A development experiment of session "10M Manhattan C" (2026-11-13), outside the runner.

    python results/manhattan_sim/v2/dev_10M/dormancy_cadence.py        # writes dormancy_cadence.json

No world, no model and no pipeline: a family's forward record is a random walk around its true edge (annualised
Sharpe units, standard error 1/sqrt(years)), the forecast is taken to be zero at every review that has one (the
worst case: on the pilots it was below 0.05 at about nine reviews in ten), and the rule is the code itself
(``manhattan.stats.dormancy.step`` with ``dormancy.forward_p``). Counted as M8 counts: dormant at the end, or
dormant for more than half the forward life. It decides nothing; it says what size of M8 to expect from the rule
for a family of a given edge, so that the pilot's small counts can be read.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from manhattan.stats import dormancy, tiers            # noqa: E402

YEAR, STEP, END = 252, 63, 2520
PATHS = 4000
CALENDARS = {"four dates (years 2, 4, 7, 10)": [2 * YEAR, 4 * YEAR, 7 * YEAR, 10 * YEAR],
             "every year": [y * YEAR for y in range(1, 11)],
             "every quarter (40 reviews)": list(range(STEP, END + 1, STEP))}


def one(theta: float, freeze: int, days: list[int], rng: np.random.Generator) -> dict:
    """Share of families retired (M8's count), ever dormant, and dormant at the end."""
    days = [d for d in days if d > freeze]
    n_q = (END - freeze) // STEP
    inc = theta * STEP / YEAR + math.sqrt(STEP / YEAR) * rng.standard_normal((PATHS, n_q))     # Sharpe units per quarter
    cum = np.concatenate([np.zeros((PATHS, 1)), inc.cumsum(axis=1)], axis=1)
    gone = ever = at_end = 0
    for i in range(PATHS):
        s, since, total, was_ever = tiers.State(), None, 0, False
        for d in days:
            fwd = d - freeze
            years = fwd / YEAR
            # the walk is on the quarterly grid; a review date inside a quarter reads the last full quarter
            y = cum[i, fwd // STEP] / max(years, 1e-9)
            p = float(dormancy.forward_p(y, 1.0 / math.sqrt(years), fwd))
            was = s.dormant
            s = dormancy.step(s, tiers.Review(pi_min=0.10, forward_days=fwd, forward_mean_positive=bool(y > 0),
                                              pp_max=None if d == days[-1] else 0.0), p)
            if s.dormant and not was:
                since, was_ever = d, True
            if was and not s.dormant:
                total += d - since
                since = None
        if since is not None:
            total += END - since
        gone += bool(s.dormant or total > 0.5 * (END - freeze))
        ever += was_ever
        at_end += s.dormant
    return {"retired": gone / PATHS, "ever_dormant": ever / PATHS, "dormant_at_end": at_end / PATHS}


def main() -> None:
    rng = np.random.default_rng(20261113)
    rows = []
    for name, days in CALENDARS.items():
        for freeze in (0, 5 * YEAR):
            for theta in (-0.2, 0.0, 0.25, 0.30, 0.40, 0.50, 0.75, 1.0):
                r = one(theta, freeze, days, rng)
                rows.append({"calendar": name, "freeze_year": freeze // YEAR, "edge": theta, **r})
                print(name, freeze // YEAR, theta, r, flush=True)
    (Path(__file__).resolve().parent / "dormancy_cadence.json").write_text(json.dumps({"paths": PATHS, "rows": rows}, indent=1) + "\n",
                                                                           encoding="utf-8")


if __name__ == "__main__":
    main()
