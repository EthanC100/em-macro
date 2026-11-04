"""Trial T16: carry-crash filter (pre-registration docs/prereg/T16-T19_risk_batch.md, section 3.1; spec 6.2).

The one change to v1.0: each long currency position is multiplied by

    scale_{i,t} = clip(1 - (p_{i,t} - p_base) / (2 p_base), 0, 1)

where p is the walk-forward probability, from a pooled L2 logistic regression (no country effects), that
the currency's cumulative excess return over the next 1-3 months falls to -2 sigma sqrt(3/12) or below.
The scale is applied after v1.0's 10% total rescaling and before its 6x cap and 25% band.  For each year Y
the model is fitted on labelled observations with decision month <= September(Y-1) (purged); C is chosen
by 5-block time-blocked cross-validation (3-month purge) over {0.01, 0.1, 1, 10, 100}, ties -> 1.0.
Features (section 3.1): carry z, RER value, WEO current account (year Y-1), reserves in months of imports
(year Y-1), log(sigma_1m/sigma_12m) from daily spot, 3-month changes in VIX, log DXY and US 2y, own
12-month return, election within 3 months.  Missing features are imputed at the training mean.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import rankdata

from . import panel_sources as PS
from . import sources as S
from . import systematic as SY
from . import tstrend as TS
from .config import EVENTS, PROC

H = 3
CRASH_SIGMAS = 2.0
C_GRID = (0.01, 0.1, 1.0, 10.0, 100.0)
C_DEFAULT = 1.0
N_BLOCKS = 5
PURGE = 3
FIRST_WF_YEAR_CONTEXT, FIRST_WF_YEAR_TEST, LAST_WF_YEAR = 2010, 2020, 2026
FEATURES = ["carry_z", "value", "ca_gdp", "res_imp", "vol_ratio", "d3_vix", "d3_usd", "d3_us2y", "own12", "election"]
COUNTRY_ISO3 = {"BRL": ["BRA"], "MXN": ["MEX"], "ZAR": ["ZAF"], "TRY": ["TUR"], "IDR": ["IDN"], "PLN": ["POL"],
                "GBP": ["GBR"], "COP": ["COL"], "CLP": ["CHL"], "EUR": ["DEU", "FRA", "ITA", "ESP"]}
V1 = ["carry", "trend", "value"]


# ============================================================ labels and features
def labels(fx_ret: pd.DataFrame, h: int = H, k: float = CRASH_SIGMAS) -> pd.DataFrame:
    """CR_{i,t} = 1 if min over tau<=h of the cumulative excess return over t+1..t+tau <= -k sigma_{i,t} sqrt(h/12)."""
    sigma = SY._vol(fx_ret)
    c = np.log1p(fx_ret).cumsum()
    c = c.where(fx_ret.notna())
    worst = None
    for tau in range(1, h + 1):
        cum = np.expm1(c.shift(-tau) - c)
        ok = fx_ret.notna()
        for s in range(1, tau + 1):
            ok &= fx_ret.shift(-s).notna()
        cum = cum.where(ok)
        worst = cum if worst is None else np.minimum(worst, cum)
    thr = -k * sigma * np.sqrt(h / 12)
    lab = (worst <= thr).astype(float).where(worst.notna() & thr.notna())
    return lab


def _spot_daily(currencies: list[str]) -> pd.DataFrame:
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    spot = {}
    for k in currencies:
        c = SY.FX_INSTR[k]
        if c in ("BR", "MX", "ZA", "TR", "ID", "PL"):
            spot[k] = daily[f"FX_{c}"]
        elif k == "GBP":
            spot[k] = 1 / S.fred("DEXUSUK")
        elif k == "EUR":
            spot[k] = 1 / S.fred("DEXUSEU")
        elif k == "COP":
            spot[k] = PS.colombia_trm()
        elif k == "CLP":
            spot[k] = PS.chile_dolar_observado()
    out = {}
    for k, s in spot.items():
        s = s.dropna()
        out[k] = s[~s.index.duplicated()].sort_index()
    return pd.DataFrame(out)


def vol_ratio(currencies: list[str], months: pd.PeriodIndex) -> pd.DataFrame:
    """log(sigma_1m / sigma_12m): std of daily log spot changes over 21 (min 15) vs 252 (min 200) business days."""
    spot = _spot_daily(currencies)
    out = {}
    for k in spot.columns:
        s = spot[k].dropna()
        d = np.log(s).diff()
        ratio = np.log(d.rolling(21, min_periods=15).std() / d.rolling(252, min_periods=200).std())
        out[k] = ratio.groupby(ratio.index.to_period("M")).last()
    return pd.DataFrame(out).reindex(months)


def global_features(months: pd.PeriodIndex) -> pd.DataFrame:
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    me = lambda s: SY._me(s).reindex(months)
    vix, dxy, us2 = me(daily["VIX"]), np.log(me(daily["DXY"])), me(S.fred("DGS2"))
    return pd.DataFrame({"d3_vix": vix.diff(3), "d3_usd": dxy.diff(3), "d3_us2y": us2.diff(3)})


def external_features(currencies: list[str], months: pd.PeriodIndex) -> dict[str, pd.DataFrame]:
    """WEO current account / GDP and reserves in months of imports, value of year Y-1 used in year Y."""
    panel = pd.read_csv(PROC / "country_month_panel.csv")
    panel["month"] = pd.PeriodIndex(panel["month"], freq="M")
    out = {}
    for name, col in (("ca_gdp", "current_account_gdp"), ("res_imp", "reserves_months_imports")):
        pv = panel.pivot(index="month", columns="iso3", values=col).reindex(months)
        f = pd.DataFrame({k: pv[[c for c in COUNTRY_ISO3[k] if c in pv.columns]].mean(axis=1) for k in currencies})
        out[name] = f.shift(12)
    return out


def election_feature(currencies: list[str], months: pd.PeriodIndex, h: int = H) -> pd.DataFrame:
    ev = pd.read_csv(EVENTS / "elections.csv")
    dates = pd.to_datetime(ev["vote_date"])
    out = pd.DataFrame(0.0, index=months, columns=currencies)
    for k in currencies:
        d = dates[ev["iso3"].isin(COUNTRY_ISO3[k])]
        for t in months:
            lo, hi = t.end_time.normalize(), (t + h).end_time.normalize()
            out.at[t, k] = float(((d > lo) & (d <= hi)).any())
    return out


def features(fx: dict, months: pd.PeriodIndex) -> pd.DataFrame:
    """Long frame indexed by (month, currency) with the FEATURES columns, for the currencies of `fx`."""
    ccy = list(fx["ret"].columns)
    sig = SY.signals(fx)
    c = np.log1p(fx["ret"]).cumsum().where(fx["ret"].notna())
    own12 = np.expm1(c - c.shift(12)).where(fx["ret"].rolling(12).count() == 12)
    ext = external_features(ccy, months)
    g = global_features(months)
    parts = {"carry_z": sig["carry"], "value": fx["value"], "ca_gdp": ext["ca_gdp"], "res_imp": ext["res_imp"],
             "vol_ratio": vol_ratio(ccy, months), "own12": own12, "election": election_feature(ccy, months)}
    frames = []
    for k in ccy:
        f = pd.DataFrame({n: v[k].reindex(months) for n, v in parts.items()})
        for n in g.columns:
            f[n] = g[n]
        f["currency"] = k
        f.index.name = "month"
        frames.append(f.reset_index())
    out = pd.concat(frames).set_index(["month", "currency"])[FEATURES]
    return out


# ============================================================ logistic regression
def fit_logistic(X: np.ndarray, y: np.ndarray, C: float) -> np.ndarray:
    """Minimise sum log-loss + ||beta||^2 / (2C) (intercept unpenalised); returns [b0, beta]."""
    n, p = X.shape
    Xa = np.column_stack([np.ones(n), X])

    def f(th):
        z = Xa @ th
        ll = np.logaddexp(0, z) - y * z
        pen = th[1:] @ th[1:] / (2 * C)
        return ll.sum() + pen

    def g(th):
        z = Xa @ th
        pr = 1 / (1 + np.exp(-z))
        gr = Xa.T @ (pr - y)
        gr[1:] += th[1:] / C
        return gr

    res = minimize(f, np.zeros(p + 1), jac=g, method="L-BFGS-B", options={"maxiter": 1000, "gtol": 1e-8})
    return res.x


def predict(theta: np.ndarray, X: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(theta[0] + X @ theta[1:])))


def standardise(train: pd.DataFrame, other: pd.DataFrame | None = None):
    mu, sd = train.mean(), train.std(ddof=0).replace(0, 1.0).fillna(1.0)
    f = lambda d: ((d - mu) / sd).fillna(0.0)          # missing -> training mean
    return f(train), (f(other) if other is not None else None), int(train.isna().sum().sum())


def choose_c(Xtr: pd.DataFrame, ytr: pd.Series, months: pd.Series, grid=C_GRID) -> tuple[float, dict]:
    """5 contiguous month blocks; purge training rows within PURGE months of the held-out block; mean
    out-of-fold log-likelihood; ties -> C_DEFAULT."""
    um = np.array(sorted(months.unique()))
    blocks = np.array_split(um, N_BLOCKS)
    scores = {C: [] for C in grid}
    for blk in blocks:
        lo, hi = blk[0], blk[-1]
        test = months.isin(blk)
        train = (months < lo - PURGE) | (months > hi + PURGE)
        if test.sum() == 0 or train.sum() == 0 or ytr[train].nunique() < 2:
            continue
        Xa, Xb, _ = standardise(Xtr[train], Xtr[test])
        for C in grid:
            th = fit_logistic(Xa.values, ytr[train].values, C)
            pr = np.clip(predict(th, Xb.values), 1e-12, 1 - 1e-12)
            yb = ytr[test].values
            scores[C].append(float(np.mean(yb * np.log(pr) + (1 - yb) * np.log(1 - pr))))
    mean = {C: (np.mean(v) if v else -np.inf) for C, v in scores.items()}
    best = max(mean.values())
    tied = [C for C, v in mean.items() if v >= best - 1e-12]
    C = C_DEFAULT if C_DEFAULT in tied else max(tied)
    return C, {str(k): v for k, v in mean.items()}


# ============================================================ walk-forward
def walk_forward(feat: pd.DataFrame, lab: pd.DataFrame, train_ccy: list[str], pred_ccy: list[str],
                 first_year: int = FIRST_WF_YEAR_CONTEXT, last_year: int = LAST_WF_YEAR) -> dict:
    """For each year Y: fit on labelled rows of train_ccy with month <= Sep(Y-1), predict pred_ccy in Y.
    Returns {'p': DataFrame months x pred_ccy, 'scale': same, 'years': [...], 'rows': predictions frame}."""
    lab_long = lab.stack(future_stack=True).rename("y")
    lab_long.index.names = ["month", "currency"]
    df = feat.join(lab_long, how="left")
    months_all = feat.index.get_level_values("month").unique().sort_values()
    p = pd.DataFrame(np.nan, index=months_all, columns=pred_ccy)
    years, rows = [], []
    for Y in range(first_year, last_year + 1):
        cut = pd.Period(f"{Y - 1}-09", "M")
        m = df.index.get_level_values("month")
        cc = df.index.get_level_values("currency")
        tr = df[(m <= cut) & cc.isin(train_ccy) & df["y"].notna()]
        if len(tr) < 50 or tr["y"].nunique() < 2:
            years.append({"year": Y, "fitted": False, "n_train": len(tr)})
            continue
        te = df[(m.year == Y) & cc.isin(pred_ccy)]
        if te.empty:
            continue
        C, cv = choose_c(tr[FEATURES], tr["y"], pd.Series(tr.index.get_level_values("month"), index=tr.index))
        Xa, Xb, n_imp = standardise(tr[FEATURES], te[FEATURES])
        th = fit_logistic(Xa.values, tr["y"].values, C)
        pr = predict(th, Xb.values)
        p_base = float(tr["y"].mean())
        for (mm, k), v in zip(te.index, pr):
            p.at[mm, k] = v
            rows.append({"month": str(mm), "currency": k, "p": v, "p_base": p_base, "y": te.at[(mm, k), "y"]})
        years.append({"year": Y, "fitted": True, "n_train": len(tr), "n_pred": len(te), "C": C, "cv_loglik": cv,
                      "p_base": p_base, "imputed_cells_train": n_imp,
                      "imputed_cells_pred": int(te[FEATURES].isna().sum().sum()),
                      "coef": dict(zip(["intercept", *FEATURES], map(float, th)))})
    rows = pd.DataFrame(rows)
    pb = p.copy()
    if len(rows):
        base = rows.pivot(index="month", columns="currency", values="p_base")
        base.index = pd.PeriodIndex(base.index, freq="M")
        pb = base.reindex(index=months_all, columns=pred_ccy)
    scale = (1 - (p - pb) / (2 * pb)).clip(0, 1).where(p.notna(), 1.0)
    return {"p": p, "p_base": pb, "scale": scale.fillna(1.0), "years": years, "rows": rows}


def auc(y: np.ndarray, s: np.ndarray) -> float:
    y, s = np.asarray(y, float), np.asarray(s, float)
    n1, n0 = (y == 1).sum(), (y == 0).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def skill(rows: pd.DataFrame, a: pd.Period, b: pd.Period) -> dict:
    """AUC and Brier skill (vs p_base) of the walk-forward predictions with a label, months a..b."""
    r = rows.copy()
    r["month"] = pd.PeriodIndex(r["month"], freq="M")
    r = r[(r["month"] >= a) & (r["month"] <= b) & r["y"].notna()]
    if r.empty:
        return {"n": 0}
    bs = float(((r["p"] - r["y"]) ** 2).mean())
    bs0 = float(((r["p_base"] - r["y"]) ** 2).mean())
    return {"n": int(len(r)), "crash_rate": float(r["y"].mean()), "auc": auc(r["y"].values, r["p"].values),
            "brier": bs, "brier_base": bs0, "brier_skill": 1 - bs / bs0 if bs0 > 0 else np.nan,
            "mean_p": float(r["p"].mean())}


# ============================================================ the strategy
def targets(inp: dict, scale: pd.DataFrame, books=TS.BOOKS) -> pd.DataFrame:
    """v1.0's targets after the 10% rescaling, long currency positions multiplied by scale."""
    W = TS.core_targets(inp, V1, books)
    fx = [c for c in inp["fx"]["ret"].columns if c in W.columns] if "fx" in books else []
    s = scale.reindex(index=W.index, columns=fx).fillna(1.0)
    longs = W[fx] > 0
    W[fx] = W[fx].where(~longs, W[fx] * s)
    return W


def run(inp: dict, scale: pd.DataFrame, books=TS.BOOKS) -> pd.DataFrame:
    return TS.finish(inp, targets(inp, scale, books), books)
