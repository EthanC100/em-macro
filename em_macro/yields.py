"""Construct daily ~10-year local-currency government bond yields where no
published daily 10y series is freely available."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from . import sources as S
from .config import BANXICO_MBONO_7_10


def mbono_ytm(dirty: float, coupon_pct: float, days: float) -> float:
    """Yield (% p.a., Banxico convention: 182-day periods, act/360 rate) of a
    Mexican Bono M from its dirty price per 100 face."""
    if not (np.isfinite(dirty) and np.isfinite(coupon_pct) and days > 0):
        return np.nan
    n = int(np.ceil(days / 182.0))
    frac = (days - (n - 1) * 182.0) / 182.0   # fraction of period to next coupon
    cpn = 100 * coupon_pct / 100 * 182 / 360
    k = np.arange(n) + frac

    def pv(y):
        d = (1 + y / 100 * 182 / 360) ** -k
        return cpn * d.sum() + 100 * d[-1] - dirty

    try:
        return brentq(pv, -5, 60)
    except ValueError:
        return np.nan


def mexico_10y(refresh: bool = False) -> tuple[pd.Series, pd.Series]:
    """YTM of the on-the-run Bono M in Banxico's 7-10y bucket (vector de precios,
    SIE cuadro CF300).  Returns (yield, years to maturity)."""
    ids = BANXICO_MBONO_7_10
    df = pd.concat({k: S.banxico(v, refresh) for k, v in ids.items()}, axis=1).dropna()
    y = pd.Series([mbono_ytm(r.dirty, r.coupon, r.days) for r in df.itertuples()],
                  index=df.index, name="MX_10Y")
    return y, (df["days"] / 365.25).rename("MX_10Y_mat")


def brazil_10y(refresh: bool = False, target: float = 10.0) -> tuple[pd.Series, pd.Series]:
    """~10y nominal yield from fixed-rate NTN-F bonds traded in Tesouro Direto.

    Each day, linearly interpolate the mid of the buy/sell rates across NTN-F
    maturities to 10 years; if no bond is longer than 10y, use the longest
    (maturity reported alongside so users can filter)."""
    td = S.tesouro_direto(refresh)
    ntnf = td[td["Tipo Titulo"] == "Tesouro Prefixado com Juros Semestrais"].copy()
    buy, sell = ntnf["Taxa Compra Manha"], ntnf["Taxa Venda Manha"]
    ntnf["rate"] = (buy + sell) / 2
    ntnf = ntnf[(buy > 0) & (sell > 0)]   # bonds not on sale are quoted with a zero/placeholder rate
    ntnf["mat"] = (ntnf["Data Vencimento"] - ntnf["Data Base"]).dt.days / 365.25
    ntnf = ntnf[(ntnf["rate"] > 0) & (ntnf["mat"] > 1)]
    out, mats = {}, {}
    for d, g in ntnf.groupby("Data Base"):
        g = g.sort_values("mat")
        m, r = g["mat"].to_numpy(), g["rate"].to_numpy()
        if m[-1] >= target and m[0] <= target:
            out[d], mats[d] = float(np.interp(target, m, r)), target
        else:
            i = int(np.argmin(abs(m - target)))
            out[d], mats[d] = float(r[i]), float(m[i])
    return pd.Series(out, name="BR_10Y").sort_index(), pd.Series(mats, name="BR_10Y_mat").sort_index()
