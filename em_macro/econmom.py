"""Trial T02: the economic-momentum signal (Dahlquist and Hasseltoft 2020), built from real-time vintages.

Pre-registration: docs/prereg/T02_econ_momentum.md (commit 0b40b2a), §2.2-2.5.  Inputs: the raw files
downloaded by `python -m em_macro.t02_data download` into data/raw/econ_momentum/ (verified against
results/T02/raw_data_manifest.csv before use).  Nothing here reads a currency or bond return.

For each decision month t (end of month t), currency c and index i in {econ, infl}:
    g_econ = mean of the available {RS_t/RS_{t-1} - 1, IP_t/IP_{t-1} - 1, U_{t-1}/U_t - 1}
    g_infl = CPI_t/CPI_{t-1} - 1
    FI     = chain-linked index of (1 + g), first value 100, built within one vintage only
    z_l    = ln FI_T - ln FI_{T-l}, l = 1..60, T = last month of the index in the vintage
Cross-sectional demeaned ranks per (i, l) (>= 3 currencies), score = mean over the available (i, l),
defined when >= 12 of the 120 sub-signals exist.  v1.0 z-scores the score across the FX book.

Source rule per (country, component, decision month): the pre-registration's table §2.4, encoded in
`SOURCE_PLAN` below.  Segment boundaries are decision months.  Fallback segments ("revised, lagged 3
months") take the latest revised series truncated at t-3 and are flagged as look-ahead risk.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import RAW

RAWDIR = RAW / "econ_momentum"
LOOKBACKS = range(1, 61)
INDICES = ("econ", "infl")
MIN_XS = 3                # currencies needed for a sub-signal's cross-sectional rank
MIN_SUBSIGNALS = 12       # of 120, for a currency's score
FALLBACK_LAG = 3          # months, revised series where no vintage exists (as in the paper)
STALE_MONTHS = 6          # an OECD edition is "stale" for a series when its last observation is > 6 months old
                          # (the definition behind the coverage tables and the pre-registration's dates)

CCY_AREA = {"BRL": "BRA", "MXN": "MEX", "ZAR": "ZAF", "TRY": "TUR", "IDR": "IDN", "PLN": "POL", "GBP": "GBR",
            "COP": "COL", "CLP": "CHL", "EUR": "EA"}
COMPONENTS = ("IP", "RS", "U", "CPI")
OECD_MEASURE = {"IP": "PRVM", "RS": "TOVM", "U": "UNEMP", "CPI": "CP"}
OECD_ACTIVITY = {"PRVM": "BTE", "TOVM": "G47", "CP": "_Z", "UNEMP": "_T"}
ECB_KEY = {"IP": "RTD.M.S0.Y.I_XCONS.X", "RS": "RTD.M.S0.Y.O_RTXMOTVD.X", "U": "RTD.M.S0.S.L_UNETO.F",
           "CPI": "RTD.M.S0.N.P_C_OV.X"}
ECB_FILE = {"IP": "I_XCONS", "RS": "O_RTXMOTVD", "U": "L_UNETO", "CPI": "P_C_OV"}

P = lambda s: pd.Period(s, "M")
LO, HI = P("1990-01"), P("2100-12")


@dataclass(frozen=True)
class Seg:
    """Source for decision months start..end (inclusive)."""
    start: pd.Period
    end: pd.Period
    kind: str                 # oecd | oecd_gapfill | ecb | alfred | alfred_fixed | revised | omit
    arg: str = ""             # series id (alfred), vintage date (alfred_fixed: "sid@YYYY-MM-DD")
    flagged: bool = False     # fallback to revised data (look-ahead risk)
    quarterly: bool = False


def _oecd(start="1990-01", end="2100-12"):
    return Seg(P(start), P(end), "oecd")


def _rev(start, end):
    return Seg(P(start), P(end), "revised", flagged=True)


# pre-registration §2.4, decision-month segments; anything not covered -> component missing that month
SOURCE_PLAN: dict[str, dict[str, list[Seg]]] = {
    "BRA": {"IP": [_oecd()], "RS": [_oecd()], "CPI": [_oecd()],
            "U": [_oecd("1990-01", "2012-05"),
                  Seg(P("2012-06"), P("2013-05"), "alfred_fixed", "LRUNTTTTBRM156S@2013-06-03", flagged=True),
                  Seg(P("2013-06"), P("2015-11"), "alfred", "LRUNTTTTBRM156S"),
                  Seg(P("2015-12"), HI, "omit")]},
    "MEX": {"IP": [_oecd()], "RS": [_oecd()], "U": [_oecd()],
            "CPI": [_oecd("1990-01", "2026-03"), _rev("2026-04", "2100-12")]},
    "ZAF": {"IP": [_oecd()], "RS": [_oecd()],
            "CPI": [_oecd("1990-01", "2025-07"), _rev("2025-08", "2100-12")],
            "U": [Seg(LO, P("2013-06"), "alfred_fixed", "LRUNTTTTZAQ156S@2013-07-01", flagged=True, quarterly=True),
                  Seg(P("2013-07"), HI, "alfred", "LRUNTTTTZAQ156S", quarterly=True)]},
    "TUR": {"IP": [_oecd()],
            "CPI": [_oecd("1990-01", "2026-06"), _rev("2026-07", "2100-12")],
            "U": [_rev("1990-01", "2006-03"), _oecd("2006-04")],
            "RS": [Seg(LO, P("2009-12"), "omit"), _rev("2010-01", "2018-06"),
                   Seg(P("2018-07"), P("2024-03"), "alfred", "TURSLRTTO01IXOBSAM"), _rev("2024-04", "2100-12")]},
    "IDN": {"CPI": [_oecd()],
            "IP": [_rev("1990-01", "2005-06"), Seg(P("2005-07"), HI, "oecd_gapfill", flagged=False)],
            "RS": [Seg(LO, HI, "omit")], "U": [Seg(LO, HI, "omit")]},
    "POL": {"IP": [_oecd()], "RS": [_oecd()], "U": [_oecd()],
            "CPI": [_oecd("1990-01", "2026-06"), _rev("2026-07", "2100-12")]},
    "GBR": {"IP": [_oecd()], "RS": [_oecd()], "U": [_oecd()], "CPI": [_oecd()]},
    "COL": {"IP": [_rev("1990-01", "2018-06"), Seg(P("2018-07"), P("2020-04"), "alfred", "COLPRMNTO01IXOBSAM"),
                   _oecd("2020-05")],
            "RS": [_rev("1990-01", "2018-06"), Seg(P("2018-07"), P("2020-04"), "alfred", "COLSLRTTO01IXOBSAM"),
                   _oecd("2020-05")],
            "CPI": [_rev("1990-01", "2018-06"), Seg(P("2018-07"), P("2020-04"), "alfred", "COLCPALTT01IXOBM"),
                    _oecd("2020-05")],
            "U": [_rev("1990-01", "2020-04"), _oecd("2020-05")]},
    "CHL": {"IP": [_rev("1990-01", "2010-05"), _oecd("2010-06")],
            "U": [_rev("1990-01", "2010-05"), _oecd("2010-06")],
            "CPI": [_rev("1990-01", "2010-05"), _oecd("2010-06", "2024-06"), _rev("2024-07", "2100-12")],
            "RS": [_rev("1990-01", "2010-05"), _oecd("2010-06")]},
    "EA": {c: [Seg(LO, HI, "ecb")] for c in COMPONENTS},
}
# Notes on the encoding (all from the pre-registration's §2.4 table):
# - "revised" = the OECD key short-term indicators (KEI) series of the same measure and activity; where the
#   KEI has no such series (Indonesia IP BTE, Chile retail), the latest edition of the OECD revisions
#   database, which is the OECD's latest revised print of the same series.  Truncated at t-3.
# - Chile CPI after 2023-12: the pre-registration names "FRED/BCCh CPI"; no such file was downloaded at the
#   data step (results/T02/raw_data_manifest.csv), so per §2.4 the extension is unavailable and the revised
#   series simply ends where the KEI ends (2023-12).
# - Indonesia IP "in gaps" (oecd_gapfill): the OECD edition in force is used unless it is stale (> 6 months
#   between edition and last observation); then the revised series lagged 3 months, flagged.
# - Colombia retail 2018-07..2020-04: ALFRED COLSLRTTO01IXOBSAM (the series continued in the OECD database);
#   COLSLRTTO02IXOBSAM (older, discontinued 2018-12) is not needed because 01 has a vintage in every month.


# ============================================================ raw readers (cached)
def _end_of_month(t: pd.Period) -> pd.Timestamp:
    return t.to_timestamp(how="end").normalize()


@lru_cache(maxsize=None)
def oecd_editions(area: str, measure: str) -> pd.DataFrame:
    """Rows TIME_PERIOD (Period M), columns EDITION (Period M); values as printed in each edition."""
    f = RAWDIR / "oecd_stes_revisions" / f"{area}_M_{measure}_all_editions.csv"
    if not f.exists():
        return pd.DataFrame()
    d = pd.read_csv(f, dtype=str, usecols=["ACTIVITY", "EDITION", "TIME_PERIOD", "OBS_VALUE"])
    d = d[d.ACTIVITY == OECD_ACTIVITY[measure]]
    d["OBS_VALUE"] = pd.to_numeric(d.OBS_VALUE, errors="coerce")
    d = d.dropna(subset=["OBS_VALUE"])
    d["EDITION"] = pd.PeriodIndex([e[:4] + "-" + e[4:6] for e in d.EDITION], freq="M")
    d["TIME_PERIOD"] = pd.PeriodIndex(d.TIME_PERIOD, freq="M")
    return d.pivot_table(index="TIME_PERIOD", columns="EDITION", values="OBS_VALUE", aggfunc="last").sort_index()


def _oecd_area(country: str) -> list[str]:
    return [country]


@lru_cache(maxsize=None)
def kei_revised(area: str, measure: str) -> pd.Series:
    f = RAWDIR / "oecd_kei_latest" / f"KEI_M_{measure}_latest.csv"
    d = pd.read_csv(f, dtype=str)
    unit = "PT_LF" if measure == "UNEMP" else "IX"
    d = d[(d.REF_AREA == area) & (d.ACTIVITY == OECD_ACTIVITY[measure]) & (d.TRANSFORMATION == "_Z")
          & (d.UNIT_MEASURE == unit)]
    s = pd.Series(pd.to_numeric(d.OBS_VALUE, errors="coerce").values,
                  index=pd.PeriodIndex(d.TIME_PERIOD, freq="M")).dropna().sort_index()
    return s


@lru_cache(maxsize=None)
def revised_series(country: str, comp: str) -> tuple[pd.Series, str]:
    """Latest revised series for the fallback: KEI, else the latest OECD revisions edition."""
    m = OECD_MEASURE[comp]
    s = kei_revised(country, m)
    if len(s):
        return s, f"OECD KEI {country} {m} {OECD_ACTIVITY[m]}"
    ed = oecd_editions(country, m)
    if ed.shape[1]:
        return ed[ed.columns.max()].dropna(), f"OECD revisions latest edition {ed.columns.max()} {country} {m}"
    return pd.Series(dtype=float), "none"


@lru_cache(maxsize=None)
def ecb_history(comp: str) -> pd.DataFrame:
    f = RAWDIR / "ecb_rtd" / f"RTD_M_S0_all_{ECB_FILE[comp]}_history.csv"
    d = pd.read_csv(f, dtype=str, usecols=["KEY", "TIME_PERIOD", "OBS_VALUE", "VALID_FROM"])
    d = d[d.KEY == ECB_KEY[comp]].copy()
    d["OBS_VALUE"] = pd.to_numeric(d.OBS_VALUE, errors="coerce")
    # VALID_FROM carries a local offset; the calendar date as published is what the rule compares
    d["vf"] = pd.to_datetime(d.VALID_FROM.str[:10])
    d["TIME_PERIOD"] = pd.PeriodIndex(d.TIME_PERIOD, freq="M")
    return d.sort_values(["vf"])[["TIME_PERIOD", "OBS_VALUE", "vf"]]


def ecb_vintage(comp: str, asof: pd.Timestamp) -> pd.Series:
    d = ecb_history(comp)
    d = d[d.vf <= asof]
    s = d.groupby("TIME_PERIOD").OBS_VALUE.last()      # latest VALID_FROM per reference period
    return s.dropna().sort_index()


@lru_cache(maxsize=None)
def alfred_vintages(sid: str) -> dict[pd.Timestamp, pd.Series]:
    out = {}
    for f in sorted((RAWDIR / "alfred" / sid).glob(f"{sid}_*.csv")):
        vd = pd.Timestamp(f.stem[-10:])
        d = pd.read_csv(f, na_values=["."])
        s = pd.Series(pd.to_numeric(d.iloc[:, 1], errors="coerce").values,
                      index=pd.PeriodIndex(pd.to_datetime(d.iloc[:, 0]), freq="M")).dropna()
        out[vd] = s.sort_index()
    return out


def alfred_vintage(sid: str, asof: pd.Timestamp) -> pd.Series | None:
    v = alfred_vintages(sid)
    ok = [d for d in v if d <= asof]
    return v[max(ok)] if ok else None


def quarterly_to_monthly(s: pd.Series) -> pd.Series:
    """Quarterly observations (dated by the quarter's first month) carried to the quarter's three months."""
    out = {}
    for p, v in s.items():
        for k in range(3):
            out[p + k] = v
    return pd.Series(out).sort_index()


# ============================================================ the information set at t
@dataclass
class CompData:
    series: pd.Series          # monthly levels as known at the end of t (may be empty)
    source: str
    flagged: bool


def _segment(country: str, comp: str, t: pd.Period) -> Seg | None:
    for s in SOURCE_PLAN[country].get(comp, []):
        if s.start <= t <= s.end:
            return s
    return None


def _oecd_at(country: str, comp: str, t: pd.Period) -> tuple[pd.Series, pd.Period | None]:
    ed = oecd_editions(country, OECD_MEASURE[comp])
    if not ed.shape[1]:
        return pd.Series(dtype=float), None
    cols = [e for e in ed.columns if e <= t]
    if not cols:
        return pd.Series(dtype=float), None
    e = max(cols)
    return ed[e].dropna(), e


def component(country: str, comp: str, t: pd.Period) -> CompData:
    seg = _segment(country, comp, t)
    empty = pd.Series(dtype=float)
    if seg is None or seg.kind == "omit":
        return CompData(empty, "omitted", False)
    asof = _end_of_month(t)
    if seg.kind == "oecd":
        s, e = _oecd_at(country, comp, t)
        return CompData(s, f"OECD edition {e}" if e is not None else "none", False)
    if seg.kind == "oecd_gapfill":
        s, e = _oecd_at(country, comp, t)
        stale = e is None or not len(s) or (e - s.index.max()).n > STALE_MONTHS
        if not stale:
            return CompData(s, f"OECD edition {e}", False)
        r, src = revised_series(country, comp)
        return CompData(r[r.index <= t - FALLBACK_LAG], f"revised lag3 ({src})", True)
    if seg.kind == "revised":
        r, src = revised_series(country, comp)
        return CompData(r[r.index <= t - FALLBACK_LAG], f"revised lag3 ({src})", True)
    if seg.kind == "ecb":
        return CompData(ecb_vintage(comp, asof), "ECB RTD", False)
    if seg.kind == "alfred":
        s = alfred_vintage(seg.arg, asof)
        if s is None:
            return CompData(empty, "none", False)
        return CompData(quarterly_to_monthly(s) if seg.quarterly else s, f"ALFRED {seg.arg}", False)
    if seg.kind == "alfred_fixed":
        sid, vd = seg.arg.split("@")
        s = alfred_vintages(sid).get(pd.Timestamp(vd))
        if s is None:
            return CompData(empty, "none", True)
        s = s[s.index <= t - FALLBACK_LAG]
        return CompData(quarterly_to_monthly(s) if seg.quarterly else s, f"revised lag3 (ALFRED {sid} {vd})", True)
    raise ValueError(seg.kind)


# ============================================================ indices and trends
def _growth(s: pd.Series, inverse: bool = False) -> pd.Series:
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    idx = pd.period_range(s.index.min(), s.index.max(), freq="M")
    s = s.reindex(idx)
    return (s.shift(1) / s - 1) if inverse else (s / s.shift(1) - 1)


def fundamental_index(parts: dict[str, pd.Series], kind: str) -> pd.Series:
    """Chain-linked index (first value 100) of the mean available monthly growth.  A month with no
    available growth breaks the chain; the index is the unbroken run that ends at its last month."""
    comps = ("IP", "RS", "U") if kind == "econ" else ("CPI",)
    g = []
    for c in comps:
        s = parts.get(c)
        if s is not None and len(s) >= 2:
            g.append(_growth(s, inverse=(c == "U")).rename(c))
    if not g:
        return pd.Series(dtype=float)
    G = pd.concat(g, axis=1)
    G = G.reindex(pd.period_range(G.index.min(), G.index.max(), freq="M"))
    gm = G.mean(axis=1, skipna=True).replace([np.inf, -np.inf], np.nan)
    if gm.notna().sum() == 0:
        return pd.Series(dtype=float)
    last = gm.last_valid_index()
    gm = gm.loc[:last]
    miss = gm.index[gm.isna()]
    first = (miss.max() + 1) if len(miss) else gm.index.min()
    run = gm.loc[first:]
    base = first - 1
    fi = pd.concat([pd.Series([100.0], index=pd.PeriodIndex([base], freq="M")), 100.0 * (1 + run).cumprod()])
    return fi


def trends(fi: pd.Series) -> pd.Series:
    """z_l = ln FI_T - ln FI_{T-l}, l = 1..60 (NaN where the index does not reach back)."""
    out = pd.Series(np.nan, index=list(LOOKBACKS), dtype=float)
    if len(fi) < 2:
        return out
    T = fi.index.max()
    lf = np.log(fi)
    for l in LOOKBACKS:
        if (T - l) in lf.index:
            out[l] = lf[T] - lf[T - l]
    return out


@dataclass
class Vintage:
    z: pd.DataFrame            # rows (index, lookback), columns currency
    last_month: dict           # (currency, index) -> T(c, t)
    sources: dict              # (currency, component) -> CompData


def vintage(t: pd.Period, currencies, delay: int = 0) -> Vintage:
    zs, last, src = {}, {}, {}
    for ccy in currencies:
        area = CCY_AREA[ccy]
        parts = {}
        for comp in COMPONENTS:
            cd = component(area, comp, t - delay)
            src[(ccy, comp)] = cd
            if len(cd.series):
                parts[comp] = cd.series
        col = {}
        for i in INDICES:
            fi = fundamental_index(parts, i)
            last[(ccy, i)] = fi.index.max() if len(fi) else None
            for l, v in trends(fi).items():
                col[(i, l)] = v
        zs[ccy] = pd.Series(col)
    return Vintage(pd.DataFrame(zs), last, src)


def score_from_z(z: pd.DataFrame) -> pd.Series:
    """Mean over sub-signals of the demeaned cross-sectional rank; >= 3 currencies per sub-signal,
    >= 12 sub-signals per currency."""
    ok = z.notna().sum(axis=1) >= MIN_XS
    zz = z[ok]
    rk = zz.rank(axis=1, method="average")
    r = rk.sub(rk.mean(axis=1), axis=0)
    n = r.notna().sum(axis=0)
    s = r.mean(axis=0)
    return s.where(n >= MIN_SUBSIGNALS)


def build(months: pd.PeriodIndex, currencies, delay: int = 0) -> dict:
    """ECONMOM score (rows months, columns currencies) and diagnostics for each decision month."""
    scores, flags, nsub, comp_rows, stale_rows = {}, {}, {}, [], []
    for t in months:
        v = vintage(t, currencies, delay)
        sc = score_from_z(v.z)
        scores[t] = sc
        ok = v.z.notna().sum(axis=1) >= MIN_XS
        nsub[t] = v.z[ok].notna().sum(axis=0)
        fl = {}
        for ccy in currencies:
            used = [c for c in COMPONENTS if len(v.sources[(ccy, c)].series)]
            fl[ccy] = any(v.sources[(ccy, c)].flagged for c in used)
            for c in COMPONENTS:
                cd = v.sources[(ccy, c)]
                age = (t - cd.series.index.max()).n if len(cd.series) else np.nan
                comp_rows.append({"month": str(t), "currency": ccy, "component": c, "source": cd.source,
                                  "flagged": cd.flagged and len(cd.series) > 0, "available": len(cd.series) > 0,
                                  "last_obs": str(cd.series.index.max()) if len(cd.series) else "",
                                  "age_months": age, "stale": bool(len(cd.series) and age > STALE_MONTHS)})
            for i in INDICES:
                T = v.last_month[(ccy, i)]
                stale_rows.append({"month": str(t), "currency": ccy, "index": i,
                                   "T": str(T) if T is not None else "",
                                   "age_months": (t - T).n if T is not None else np.nan})
        flags[t] = pd.Series(fl)
    S = pd.DataFrame(scores).T.reindex(columns=list(currencies))
    S.index = pd.PeriodIndex(S.index, freq="M")
    F = pd.DataFrame(flags).T.reindex(columns=list(currencies))
    F.index = S.index
    N = pd.DataFrame(nsub).T.reindex(columns=list(currencies))
    N.index = S.index
    return {"score": S, "flagged": F, "n_subsignals": N, "components": pd.DataFrame(comp_rows),
            "index_age": pd.DataFrame(stale_rows)}


# ============================================================ latest-data version (diagnostic, spec §13)
def latest_component(area: str, comp: str, rt: CompData) -> pd.Series:
    """The latest vintage of the same source, truncated at the real-time vintage's last observation."""
    if not len(rt.series):
        return rt.series
    end = rt.series.index.max()
    src = rt.source
    if src.startswith("OECD edition"):
        ed = oecd_editions(area, OECD_MEASURE[comp])
        s = ed[ed.columns.max()].dropna()
    elif src == "ECB RTD":
        s = ecb_vintage(comp, pd.Timestamp("2100-01-01"))
    elif src.startswith("ALFRED"):
        sid = src.split()[1]
        v = alfred_vintages(sid)
        s = v[max(v)]
        if area == "ZAF" and comp == "U":
            s = quarterly_to_monthly(s)
    else:                       # revised fallback: already the latest revised data
        return rt.series
    s = s[s.index <= end]
    return s if len(s) else rt.series


def build_latest(months: pd.PeriodIndex, currencies) -> pd.DataFrame:
    scores = {}
    for t in months:
        zs = {}
        for ccy in currencies:
            area = CCY_AREA[ccy]
            parts = {}
            for comp in COMPONENTS:
                rt = component(area, comp, t)
                s = latest_component(area, comp, rt)
                if len(s):
                    parts[comp] = s
            col = {}
            for i in INDICES:
                for l, v in trends(fundamental_index(parts, i)).items():
                    col[(i, l)] = v
            zs[ccy] = pd.Series(col)
        scores[t] = score_from_z(pd.DataFrame(zs))
    S = pd.DataFrame(scores).T.reindex(columns=list(currencies))
    S.index = pd.PeriodIndex(S.index, freq="M")
    return S
