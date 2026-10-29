"""Daily 10y yields for Poland and Turkey built from per-bond exchange data.

* Poland: Treasury BondSpot Poland daily fixing yields of all fixed-rate bonds
  (OK/PS/DS/WS...), linearly interpolated to 10 years.  Maturity is taken from
  the bond name (MMYY; Polish bonds mature on the 25th).
* Turkey: Borsa Istanbul debt-market bulletin, fixed-coupon TRY bonds (TRT...),
  weighted-average compound yield of the traded bond whose days-to-maturity
  are closest to 10 years (6-12y window).  CSV bulletins start July 2018, and
  no 10y TRY bond existed before 2010.
* Indonesia: no free, keyless daily 10y source was found (see README).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sources as S

CAVEATS = [
    "Indonesia: no free, keyless daily 10y government yield found (PHEI/IBPA publishes only the latest two days; "
    "DJPPR only PDFs; IDX blocks API access; OECD monthly covers 2012-2024 only). Indonesian bond events are not "
    "studied.",
    "Turkey: daily 10y yield only from July 2018 (Borsa Istanbul CSV bulletins); traded-bond closest to 10y, so "
    "the series switches bonds and is noisy. Older bulletins are legacy .xls with changing layouts and no 10y TRY "
    "bond existed before 2010.",
    "Poland: BondSpot fixing interpolated to 10y across fixed-rate bonds.",
    "Brazil: Tesouro Direto NTN-F quotes are morning (\"Manha\") rates; before ~2007 the longest NTN-F was <10y, "
    "so Y10_BR is the longest available bond (see Y10MAT_BR).",
    "Mexico: yield computed from Banxico's on-the-run 7-10y Bono M dirty price, coupon and days to maturity; "
    "maturity drifts between ~7.5 and 10.9 years as the benchmark rolls (Y10MAT_MX).",
    "South Africa: SARB average yield on government bonds with 10 years and longer to maturity (not a single "
    "benchmark).",
]


def _interp(m: np.ndarray, r: np.ndarray, target: float = 10.0, tol: float = 2.0):
    o = np.argsort(m)
    m, r = m[o], r[o]
    if m[0] <= target <= m[-1]:
        return float(np.interp(target, m, r)), target
    i = int(np.argmin(abs(m - target)))
    return (float(r[i]), float(m[i])) if abs(m[i] - target) <= tol else (np.nan, np.nan)


def poland_10y(refresh: bool = False) -> tuple[pd.Series, pd.Series]:
    df = S.bondspot_fixings(refresh).dropna(subset=["yield_fix"])
    mm = df["name"].str.extract(r"^[A-Z]{2}(\d{2})(\d{2})$").astype(float)
    df = df[mm[0].between(1, 12)].copy()
    mm = mm.loc[df.index]
    mat = pd.to_datetime(dict(year=2000 + mm[1], month=mm[0], day=25), errors="coerce")
    df["mat"] = (mat - df["date"]).dt.days / 365.25
    df = df[df["mat"] > 0.5]
    out, mats = {}, {}
    for d, g in df.groupby("date"):
        out[d], mats[d] = _interp(g["mat"].to_numpy(), g["yield_fix"].to_numpy())
    return pd.Series(out, name="PL_10Y").dropna(), pd.Series(mats, name="PL_10Y_mat").dropna()


def turkey_10y(refresh: bool = False) -> tuple[pd.Series, pd.Series]:
    df = S.bist_bonds(refresh)
    df["y"] = df["wavg_compound"].fillna(df["close_compound"])
    df["mat"] = df["dtm"] / 365.25
    df = df.dropna(subset=["y"])
    df = df[df["mat"].between(6, 12) & (df["y"] > 0)]
    df["dist"] = (df["mat"] - 10).abs()
    best = df.sort_values(["date", "dist"]).groupby("date").first()
    return best["y"].rename("TR_10Y"), best["mat"].rename("TR_10Y_mat")


def daily_10y(country: str, refresh: bool = False):
    if country == "PL":
        s, _ = poland_10y(refresh)
        return s, "Treasury BondSpot Poland fixing", "fixed-rate bond fixing yields interpolated to 10y", "daily"
    if country == "TR":
        s, _ = turkey_10y(refresh)
        return (s, "Borsa Istanbul debt market bulletin",
                "compound yield of traded TRY fixed-coupon bond closest to 10y (6-12y), from 2018-07", "daily")
    return None, None, None, None
