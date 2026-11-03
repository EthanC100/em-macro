"""Cross-sectional holdout split of v1.0's countries (spec §0.3(c)).

    python -m em_macro.holdout          # prints the split and writes results/T01/holdout_split.csv

Every v1.0 instrument belongs to one "country unit".  The euro (EUR) is its own unit, "euro area",
because it is not specific to any one of France, Italy, Spain or Germany; the Bund (DE10Y) belongs to
Germany.  Units are stratified by region and developed/emerging, shuffled within each stratum with a
fixed seed, and dealt one at a time to whichever half currently holds fewer units (ties broken by a
coin flip from the same generator).  The split depends only on the seed and the unit list below,
never on returns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RESULTS

SEED = 20261103

# unit -> (stratum, instruments in v1.0)
UNITS = {
    "BR": ("EM Latin America", ["BRL", "BR10Y"]),
    "MX": ("EM Latin America", ["MXN", "MX10Y"]),
    "CO": ("EM Latin America", ["COP", "CO10Y"]),
    "CL": ("EM Latin America", ["CLP", "CL10Y"]),
    "ZA": ("EM Europe, Middle East and Africa", ["ZAR", "ZA10Y"]),
    "TR": ("EM Europe, Middle East and Africa", ["TRY", "TR10Y"]),
    "PL": ("EM Europe, Middle East and Africa", ["PLN", "PL-DE"]),
    "ID": ("EM Asia", ["IDR", "ID10Y"]),
    "GB": ("DM Europe", ["GBP", "GB-DE"]),
    "FR": ("DM Europe", ["FR-DE"]),
    "IT": ("DM Europe", ["IT-DE"]),
    "ES": ("DM Europe", ["ES-DE"]),
    "DE": ("DM Europe", ["DE10Y"]),
    "XM": ("DM Europe", ["EUR"]),
}
STRATA = ["EM Latin America", "EM Europe, Middle East and Africa", "EM Asia", "DM Europe"]


def split(seed: int = SEED) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    half, count = {}, {"A": 0, "B": 0}
    for st in STRATA:
        members = sorted(u for u, (s, _) in UNITS.items() if s == st)
        for u in rng.permutation(members):
            if count["A"] == count["B"]:
                h = "A" if rng.random() < 0.5 else "B"
            else:
                h = "A" if count["A"] < count["B"] else "B"
            half[str(u)] = h
            count[h] += 1
    return half


def instruments(h: str, seed: int = SEED) -> list[str]:
    s = split(seed)
    return [i for u, (_, ins) in UNITS.items() if s[u] == h for i in ins]


def table(seed: int = SEED) -> pd.DataFrame:
    s = split(seed)
    return pd.DataFrame([{"unit": u, "stratum": st, "half": s[u], "instruments": " ".join(ins)}
                         for u, (st, ins) in UNITS.items()]).sort_values(["half", "stratum", "unit"])


if __name__ == "__main__":
    t = table()
    out = RESULTS / "T01"
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / "holdout_split.csv", index=False)
    print(t.to_string(index=False))
