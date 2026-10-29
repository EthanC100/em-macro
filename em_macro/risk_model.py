"""Sovereign risk model on the 13-country panel.

    python -m em_macro.risk_model data      # lagged design matrix -> data/processed/risk_model_input.csv
    python -m em_macro.risk_model fit       # 2005-2019 only -> results/risk_model/fit/ (frozen_params.json)
    python -m em_macro.risk_model test      # 2020+ with frozen parameters, once -> results/risk_model/test/
    python -m em_macro.risk_model fit --v2  # post-hoc v2: separate spread equations over Bunds / over USTs
    python -m em_macro.risk_model test --v2
    python -m em_macro.risk_model outputs   # fair value, factor contributions, similar cases, what-if

Spread equation: 10y spread (bp; over Germany for FR/IT/ES/GB/PL, over US
Treasuries otherwise; Germany is the benchmark and is not modelled) on
lagged fundamentals with country fixed effects.  Currency equation: 100*log
real exchange rate vs USD (local per USD, CPI-deflated; + = weaker local
currency) for the nine non-euro currencies, adding the policy-rate
differential and commodity prices (country-specific slopes).

Estimation: ridge on within-country demeaned, pooled-standardised factors,
penalty chosen by blocked (3-year) cross-validation inside 2005-2019;
Driscoll-Kraay standard errors (Bartlett kernel, 12 lags).  The earlier
frozen event-study results (results/fit, results/test) are not touched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import panel_sources as PS
from . import sources as S
from .config import PROC, RESULTS, ROOT
from .panel import COUNTRIES, EURO, FOCUS, ISO3, NAMES

OUT = RESULTS / "risk_model"
FIT_DIR, TEST_DIR = OUT / "fit", OUT / "test"                     # v1: as specified, frozen and tested once
FIT_DIR_V2, TEST_DIR_V2 = OUT / "fit_v2_posthoc", OUT / "test_v2_posthoc"
EXT = ROOT / "data" / "external" / "structural"
FIT_END, TEST_START = pd.Period("2019-12", "M"), pd.Period("2020-01", "M")
HORIZONS = (3, 6)
SPREAD_C = [c for c in COUNTRIES if c != "DE"]
EU_C = ["FR", "IT", "ES", "GB", "PL"]                                 # spreads over Bunds
EM_C = ["BR", "MX", "ZA", "TR", "ID", "CO", "CL"]                     # spreads over US Treasuries
FX_C = [c for c in COUNTRIES if c not in EURO]
DK_LAGS = 12

# publication lags in months (documented in the README)
LAGS = {
    "debt": 12, "deficit": 12, "debt_traj": 12, "current_account": 12,   # IMF WEO / annual fiscal
    "wgi": 12, "jucon": 12, "high_court_indep": 12,                       # World Bank WGI, V-Dem
    "cbi": 12, "reserves_months": 12,                                    # annual datasets (CBIE, WDI)
    "foreign_share": 6,                                                  # quarterly debt-holder data
    "infl_gap": 1, "real_rate": 1,                                       # monthly macro (CPI)
    "rating": 0, "seat_share": 0, "n_gov5y": 0, "lr_vparty": 0, "populism_vparty": 0,
    "lr_ches": 0, "populist_popu_list": 0, "imf_programme": 0,          # ratings, government, parties
    "us10y": 0, "log_vix": 0, "ecb_rate": 0, "rate_diff": 0,           # market data
}
LABELS = {
    "debt": "gross debt, % GDP", "deficit": "fiscal deficit, % GDP", "debt_traj": "debt trajectory (3y avg change, pp/yr)",
    "current_account": "current account, % GDP", "wgi": "governance (WGI mean)", "jucon": "judicial constraints (V-Dem)",
    "high_court_indep": "high-court independence (V-Dem)", "cbi": "central bank independence (CBIE)",
    "reserves_months": "reserves, months of imports", "foreign_share": "debt held abroad, %",
    "infl_gap": "inflation minus target, pp", "real_rate": "real policy rate, %", "rating": "average rating (notches)",
    "seat_share": "government seat share, %", "n_gov5y": "governments in prior 5 years",
    "lr_vparty": "governing parties' economic position (V-Party, + = right)",
    "populism_vparty": "governing parties' populism (V-Party)", "lr_ches": "governing parties' economic position (CHES)",
    "populist_popu_list": "populist party in government (PopuList)", "imf_programme": "IMF programme",
    "us10y": "US 10y yield, %", "log_vix": "VIX (log)", "ecb_rate": "ECB deposit rate, %",
    "rate_diff": "policy rate minus fed funds, pp", "debt_x_seat": "debt x government seat share",
    "commodities": "commodity prices",
}
SPREAD_F = ["debt", "deficit", "debt_traj", "foreign_share", "cbi", "infl_gap", "real_rate", "seat_share",
            "n_gov5y", "lr_vparty", "populism_vparty", "lr_ches", "populist_popu_list", "wgi", "jucon",
            "high_court_indep", "current_account", "reserves_months", "imf_programme", "rating", "us10y",
            "log_vix", "ecb_rate"]
COMMOD = {"all": "PALLFNFINDEXM", "oil": "POILBREUSDM", "copper": "PCOPPUSDM", "soy": "PSOYBUSDM",
          "iron_ore": "PIORECRUSDM"}
FX_F = SPREAD_F + ["rate_diff"]
ANALOG_F = ["debt", "deficit", "debt_traj", "foreign_share", "cbi", "infl_gap", "real_rate", "seat_share",
            "n_gov5y", "lr_vparty", "populism_vparty", "wgi", "jucon", "current_account", "reserves_months",
            "imf_programme", "rating"]


# ======================================================================= data
def _annual_prev_year(df_year: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    """Annual value (index=year, columns=country) -> each month gets the value of
    the previous calendar year, i.e. a 12-month publication lag."""
    rows = {m: df_year.loc[m.year - 1] if (m.year - 1) in df_year.index else pd.Series(np.nan, df_year.columns)
            for m in months}
    return pd.DataFrame(rows).T.reindex(columns=COUNTRIES)


def _foreign_share(months) -> pd.DataFrame:
    """One series per country: Arslanalp-Tsuda (to 2016Q2) extended with QPSD,
    else Eurostat, ratio-spliced at the last overlapping quarter; if there is no
    overlap the new source is level-matched to the last earlier value; after the
    last observation the value is carried forward."""
    dh = pd.read_csv(EXT / "debt_holders.csv")
    dh = dh[dh["freq"].str.upper().str[0] == "Q"].dropna(subset=["foreign_share_pct"])
    tag = np.select([dh["source"].str.contains("Arslanalp"), dh["source"].str.contains("Quarterly Public"),
                     dh["source"].str.contains("Eurostat")], ["at", "qpsd", "eurostat"], "other")
    dh = dh.assign(tag=tag, q=pd.PeriodIndex(dh["period"], freq="Q"))
    out = {}
    for c in COUNTRIES:
        g = dh[dh["iso3"] == ISO3[c]]
        at = g[g.tag == "at"].set_index("q")["foreign_share_pct"].sort_index()
        s = at.copy()
        for src in ("qpsd", "eurostat"):
            new = g[g.tag == src].set_index("q")["foreign_share_pct"].sort_index()
            new = new[~new.index.duplicated()]
            if new.empty:
                continue
            if s.empty:
                s = new
                continue
            ov = s.index.intersection(new.index)
            if len(ov):
                k = ov.max()
                scaled = new * (s[k] / new[k]) if new[k] else new
            else:
                scaled = new - new.iloc[0] + s.iloc[-1]
            s = s.combine_first(scaled[scaled.index > s.index.max()])
        if s.empty:
            out[c] = pd.Series(np.nan, index=months)
            continue
        mq = pd.Series({m: s.get(m.asfreq("Q"), np.nan) for m in months})
        out[c] = mq.ffill()
    return pd.DataFrame(out).reindex(index=months)


def build_data() -> pd.DataFrame:
    p = pd.read_csv(PROC / "country_month_panel.csv")
    p["month"] = pd.PeriodIndex(p["month"], freq="M")
    iso2 = {v: k for k, v in ISO3.items()}
    p["c"] = p["iso3"].map(iso2)
    months = pd.period_range(p["month"].min(), p["month"].max(), freq="M")
    wide = lambda col: p.pivot(index="month", columns="c", values=col).reindex(index=months, columns=COUNTRIES)
    f = {}

    # annual, previous-year values (12-month lag)
    weo = {}
    for code in ("GGXWDG_NGDP", "GGXCNL_NGDP", "BCA_NGDPD"):
        weo[code] = pd.DataFrame({c: PS.imf_weo(ISO3[c], code)[0] for c in COUNTRIES})
    d = weo["GGXWDG_NGDP"]
    f["debt"] = _annual_prev_year(d, months)
    f["deficit"] = _annual_prev_year(-weo["GGXCNL_NGDP"], months)
    f["debt_traj"] = _annual_prev_year((d - d.shift(3)) / 3, months)
    f["current_account"] = _annual_prev_year(weo["BCA_NGDPD"], months)
    iso = [ISO3[c] for c in COUNTRIES]
    wgi = sum(PS.worldbank(iso, f"GOV_WGI_{k}.EST", source=3) for k in ("VA", "PV", "GE", "RQ", "RL", "CC")) / 6
    f["wgi"] = _annual_prev_year(wgi.rename(columns=iso2), months)
    res = PS.worldbank(iso, "FI.RES.TOTL.MO").rename(columns=iso2)
    f["reserves_months"] = _annual_prev_year(res, months)
    vd = pd.read_csv(EXT / "vdem.csv")
    vd["c"] = vd["iso3"].map(iso2)
    f["jucon"] = _annual_prev_year(vd.pivot(index="year", columns="c", values="v2x_jucon"), months)
    f["high_court_indep"] = _annual_prev_year(vd.pivot(index="year", columns="c", values="v2juhcind"), months)
    cbi = pd.read_csv(EXT / "cbi.csv")
    cbi["c"] = cbi["iso3"].map(iso2)
    cb = cbi.pivot(index="year", columns="c", values="cbie_index")
    cb = cb.reindex(range(cb.index.min(), months.max().year + 1)).ffill()   # CBIE ends 2023: carried forward
    f["cbi"] = _annual_prev_year(cb, months)
    # quarterly, 6-month lag
    f["foreign_share"] = _foreign_share(months).shift(LAGS["foreign_share"])
    # monthly macro, 1-month lag
    cpi = wide("cpi_yoy")
    f["infl_gap"] = (cpi - wide("inflation_target")).shift(1)
    f["real_rate"] = wide("policy_rate") - cpi.shift(1)
    # unlagged: ratings, government, parties, programmes, market
    f["rating"] = wide("rating_avg_outlook_adj")
    f["seat_share"] = wide("gov_seat_share")
    f["n_gov5y"] = wide("n_governments_prior5y")
    f["lr_vparty"] = wide("gov_parties_lr_econ_vparty")
    f["populism_vparty"] = wide("gov_parties_populism_vparty")
    f["lr_ches"] = wide("gov_parties_lr_econ_ches")
    f["populist_popu_list"] = wide("gov_parties_populist_popu_list")
    f["imf_programme"] = wide("imf_programme")
    glob = p.drop_duplicates("month").set_index("month").reindex(months)
    for name, col, tf in (("us10y", "us10y", None), ("log_vix", "vix", np.log), ("ecb_rate", "ecb_deposit_rate", None)):
        s = glob[col] if tf is None else tf(glob[col])
        f[name] = pd.DataFrame({c: s for c in COUNTRIES})
    f["rate_diff"] = wide("policy_rate").sub(glob["fed_funds"], axis=0)
    for k, code in COMMOD.items():
        s = np.log(S.fred(code))
        s = s.groupby(s.index.to_period("M")).last().reindex(months)
        f[f"commod_{k}"] = pd.DataFrame({c: s for c in COUNTRIES})

    # dependent variables
    y_spread = wide("spread_bench_bp")
    fx = wide("fx_per_usd_avg")
    us_cpi = PS.bis_cpi_index("US").reindex(months)
    rer = {}
    for c in FX_C:
        loc = PS.bis_cpi_index(c).reindex(months)
        rer[c] = 100 * np.log(fx[c] * us_cpi / loc)
    y_fx = pd.DataFrame(rer).reindex(columns=COUNTRIES)

    long = []
    for c in COUNTRIES:
        d = pd.DataFrame({k: v[c] for k, v in f.items()}, index=months)
        d["spread"] = y_spread[c]
        d["fx_rer"] = y_fx[c]
        d["fx_spot"] = fx[c]
        d["fx_end"] = wide("fx_per_usd_end")[c]
        d.insert(0, "c", c)
        long.append(d)
    data = pd.concat(long)
    data.index.name = "month"
    data = data.reset_index()
    data.assign(month=data["month"].astype(str)).to_csv(PROC / "risk_model_input.csv", index=False,
                                                         float_format="%.6g")
    return data


def load_data() -> pd.DataFrame:
    d = pd.read_csv(PROC / "risk_model_input.csv")
    d["month"] = pd.PeriodIndex(d["month"], freq="M")
    return d


# ================================================================== design
def _design(d: pd.DataFrame, feats: list[str], std: dict, cmeans: dict, commod: bool) -> pd.DataFrame:
    """Pooled z-scores (fit-sample mean/sd), missing values carried forward
    within country and otherwise set to the country's fit-sample mean; plus the
    debt x seat-share interaction (within-country centred) and, for the
    currency equation, commodity prices with country-specific slopes."""
    X = pd.DataFrame(index=d.index)
    for k in feats:
        z = (d[k] - std[k][0]) / std[k][1]
        z = z.groupby(d["c"]).ffill()
        X[k] = z.fillna(d["c"].map(cmeans[k]).fillna(0.0))
    dc = X["debt"] - d["c"].map(cmeans["debt"]).fillna(0)
    sc = X["seat_share"] - d["c"].map(cmeans["seat_share"]).fillna(0)
    X["debt_x_seat"] = dc * sc
    if commod:
        for k in COMMOD:
            z = (d[f"commod_{k}"] - std[f"commod_{k}"][0]) / std[f"commod_{k}"][1]
            for c in FX_C:
                X[f"commod_{k}:{c}"] = np.where(d["c"] == c, z, 0.0)
    return X


def _standardisers(d: pd.DataFrame, feats: list[str], commod: bool):
    fit = d[d["month"] <= FIT_END]
    keys = feats + ([f"commod_{k}" for k in COMMOD] if commod else [])
    std = {k: (float(fit[k].mean()), float(fit[k].std()) or 1.0) for k in keys}
    cmeans = {}
    for k in feats:
        z = (fit[k] - std[k][0]) / std[k][1]
        z = z.groupby(fit["c"]).ffill()
        cmeans[k] = z.groupby(fit["c"]).mean().to_dict()
    return std, cmeans


def _ridge(Xd: np.ndarray, yd: np.ndarray, lam: float) -> np.ndarray:
    k = Xd.shape[1]
    return np.linalg.solve(Xd.T @ Xd + lam * np.eye(k), Xd.T @ yd)


def _within(X: pd.DataFrame, y: pd.Series, c: pd.Series, xm=None, ym=None):
    xm = X.groupby(c).mean() if xm is None else xm
    ym = y.groupby(c).mean() if ym is None else ym
    return X - xm.reindex(c).values, y - ym.reindex(c).values, xm, ym


def _cv_lambda(X: pd.DataFrame, y: pd.Series, c: pd.Series, month: pd.Series, grid) -> tuple[float, pd.DataFrame, pd.Series]:
    """Blocked CV: 3-year blocks of 2005-2019 held out in turn; fixed effects and
    coefficients are re-estimated on the remaining blocks."""
    blocks = ((month.dt.year - 2005) // 3).values
    rows, oof_best = [], None
    for lam in grid:
        pred = pd.Series(np.nan, index=y.index)
        for b in np.unique(blocks):
            tr, te = blocks != b, blocks == b
            Xd, yd, xm, ym = _within(X[tr], y[tr], c[tr])
            beta = _ridge(Xd.values, yd.values, lam)
            alpha = ym - xm @ beta
            ok = c[te].isin(alpha.index)
            idx = y.index[te][ok.values]
            pred.loc[idx] = alpha.reindex(c.loc[idx]).values + X.loc[idx].values @ beta
        mse = float(((y - pred) ** 2).mean())
        rows.append({"lambda": lam, "cv_mse": mse, "cv_rmse": mse ** 0.5})
        if oof_best is None or mse < oof_best[0]:
            oof_best = (mse, lam, pred)
    return oof_best[1], pd.DataFrame(rows), oof_best[2]


def _driscoll_kraay(Xd: np.ndarray, resid: np.ndarray, month: np.ndarray, lam: float, lags: int = DK_LAGS):
    """Driscoll-Kraay covariance of the ridge estimator A X'y, A=(X'X+lam I)^-1:
    V = A S A with S the Bartlett-weighted long-run covariance of the
    cross-sectional sums h_t = sum_i x_it e_it."""
    k = Xd.shape[1]
    A = np.linalg.inv(Xd.T @ Xd + lam * np.eye(k))
    h = pd.DataFrame(Xd * resid[:, None]).groupby(month).sum().sort_index().values
    S = h.T @ h
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        G = h[l:].T @ h[:-l]
        S += w * (G + G.T)
    return A @ S @ A


def _fit_equation(d: pd.DataFrame, yname: str, feats: list[str], countries: list[str], commod: bool) -> dict:
    d = d[d["c"].isin(countries)].copy()
    std, cmeans = _standardisers(d, feats, commod)
    X = _design(d, feats, std, cmeans, commod)
    fit = (d["month"] <= FIT_END) & d[yname].notna()
    Xf, yf, cf, mf = X[fit], d.loc[fit, yname], d.loc[fit, "c"], d.loc[fit, "month"]
    grid = np.logspace(0, 5, 21) * len(yf) / 1000
    lam, cvtab, oof = _cv_lambda(Xf, yf, cf, mf.dt.to_timestamp(), grid)
    Xd, yd, xm, ym = _within(Xf, yf, cf)
    beta = _ridge(Xd.values, yd.values, lam)
    alpha = ym - xm @ beta
    resid = yd.values - Xd.values @ beta
    V = _driscoll_kraay(Xd.values, resid, mf.astype(str).values, lam)
    se = np.sqrt(np.diag(V))
    resid_sd = pd.Series(resid, index=cf.index).groupby(cf).std()
    cols = list(X.columns)
    # natural units: coefficient per unit of the raw factor (z-coefficient / pooled sd)
    nat = [beta[i] / std[k][1] if k in std and k in feats else np.nan for i, k in enumerate(cols)]
    coef = pd.DataFrame({"term": cols, "label": [LABELS.get(k.split(":")[0].replace("commod_", "commodities: "), k)
                                                 if not k.startswith("commod_") else f"commodity {k[7:]}" for k in cols],
                         "coef_per_sd": beta, "se_dk": se, "t_dk": beta / se, "coef_per_unit": nat,
                         "lag_months": [LAGS.get(k, 0) for k in cols]})
    return {"y": yname, "feats": feats, "countries": countries, "commod": commod, "lambda": lam,
            "std": std, "cmeans": cmeans, "beta": dict(zip(cols, beta)), "alpha": alpha.to_dict(),
            "resid_sd": resid_sd.to_dict(), "cov": V.tolist(), "cols": cols, "n_obs": int(fit.sum()),
            "within_r2": float(1 - (resid ** 2).sum() / (yd.values ** 2).sum()),
            "cv": cvtab.to_dict("records"), "_coef": coef, "_oof": oof, "_d": d, "_X": X}


def predict(eq: dict, d: pd.DataFrame) -> pd.DataFrame:
    """Fitted value and gap with frozen parameters for every country-month."""
    d = d[d["c"].isin(eq["countries"])].copy()
    X = _design(d, eq["feats"], eq["std"], eq["cmeans"], eq["commod"])
    b = np.array([eq["beta"][k] for k in eq["cols"]])
    d["fitted"] = d["c"].map(eq["alpha"]).values + X[eq["cols"]].values @ b
    d["gap"] = d[eq["y"]] - d["fitted"]
    d["gap_z"] = d["gap"] / d["c"].map(eq["resid_sd"])
    return d, X


def _future_change(d: pd.DataFrame, col: str, h: int) -> pd.Series:
    return d.groupby("c")[col].shift(-h) - d[col]


# ===================================================================== fit
EQUATIONS = {
    # v1: one pooled spread equation + currency equation, exactly as specified (frozen, tested once)
    "v1": [("spread", "spread", SPREAD_F, SPREAD_C, False), ("fx", "fx_rer", FX_F, FX_C, True)],
    # v2 (post hoc): separate spread equations for spreads over Bunds and over US Treasuries,
    # because v1 pools two different dependent variables (see README)
    "v2": [("spread_eu", "spread", SPREAD_F, EU_C, False), ("spread_em", "spread", SPREAD_F, EM_C, False)],
}


def _dirs(version):
    return (FIT_DIR, TEST_DIR) if version == "v1" else (FIT_DIR_V2, TEST_DIR_V2)


def stage_fit(version: str = "v1"):
    fit_dir = _dirs(version)[0]
    fit_dir.mkdir(parents=True, exist_ok=True)
    d = load_data()
    frozen = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "version": version,
              "fit_end": str(FIT_END), "test_start": str(TEST_START), "lags_months": LAGS, "equations": {}}
    for name, y, feats, cs, commod in EQUATIONS[version]:
        eq = _fit_equation(d, y, feats, cs, commod)
        eq["_coef"].to_csv(fit_dir / f"coefficients_{name}.csv", index=False, float_format="%.5g")
        pd.DataFrame(eq["cv"]).to_csv(fit_dir / f"cv_{name}.csv", index=False, float_format="%.5g")
        # mispricing -> future change, estimated on out-of-fold gaps (fit sample only)
        dd = eq["_d"]
        gap_oof = dd[y] - eq["_oof"].reindex(dd.index)
        kappa = {}
        for h in HORIZONS:
            dy = _future_change(dd, y, h)
            ok = (dd["month"] + h <= FIT_END) & gap_oof.notna() & dy.notna()
            g, r = gap_oof[ok].values, dy[ok].values
            kappa[h] = float(-(g @ r) / (g @ g))          # forecast = -kappa * gap
        eq["kappa"] = kappa
        frozen["equations"][name] = {k: v for k, v in eq.items() if not k.startswith("_")}
        print(f"{name}: lambda={eq['lambda']:.3g}, within R2={eq['within_r2']:.2f}, n={eq['n_obs']}, kappa={kappa}")
    (fit_dir / "frozen_params.json").write_text(json.dumps(frozen, indent=1, default=float))


def load_frozen(version: str = "v1") -> dict:
    fr = json.loads((_dirs(version)[0] / "frozen_params.json").read_text())
    for eq in fr["equations"].values():
        eq["kappa"] = {int(k): v for k, v in eq["kappa"].items()}
    return fr


# ==================================================================== test
def _dm(loss_model: pd.Series, loss_zero: pd.Series, month: pd.Series, h: int) -> float:
    """Diebold-Mariano t-stat: cross-sectional mean loss differential per month,
    Newey-West with h-1 lags (overlapping horizons).  > 0 favours the model."""
    dlt = (loss_zero - loss_model).groupby(month).mean().sort_index().values
    n = len(dlt)
    if n < 10:
        return np.nan
    u = dlt - dlt.mean()
    v = u @ u / n
    for l in range(1, max(h, 1)):
        v += 2 * (1 - l / h) * (u[l:] @ u[:-l]) / n
    return float(dlt.mean() / np.sqrt(v / n)) if v > 0 else np.nan


def _eval(df: pd.DataFrame, h: int) -> dict:
    if len(df) == 0:
        return {"n": 0}
    lm, lz = (df["actual"] - df["forecast"]) ** 2, df["actual"] ** 2
    return {"n": len(df), "rmse_model": float(np.sqrt(lm.mean())), "rmse_no_change": float(np.sqrt(lz.mean())),
            "rmse_ratio": float(np.sqrt(lm.mean() / lz.mean())) if lz.mean() > 0 else np.nan,
            "dm_t": _dm(lm, lz, df["month"], h),
            "hit_rate": float((np.sign(df["forecast"]) == np.sign(df["actual"]))[df["actual"] != 0].mean())}


def forecast_eval(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """frame: c, month, h, forecast, actual.  Pooled and by country, with and
    without the five largest moves (pooled: five largest |actual| overall;
    by country: that country's five largest)."""
    rows = []
    frame = frame.reset_index(drop=True)          # unique labels, so "drop top 5" drops exactly five rows
    for h, g in frame.groupby("h"):
        top5 = g["actual"].abs().nlargest(5).index
        rows.append({"model": label, "h": h, "scope": "pooled", "drop_top5": False, **_eval(g, h)})
        rows.append({"model": label, "h": h, "scope": "pooled", "drop_top5": True, **_eval(g.drop(top5), h)})
        for c, gc in g.groupby("c"):
            t5 = gc["actual"].abs().nlargest(5).index
            rows.append({"model": label, "h": h, "scope": NAMES[c], "drop_top5": False, **_eval(gc, h)})
            rows.append({"model": label, "h": h, "scope": NAMES[c], "drop_top5": True, **_eval(gc.drop(t5), h)})
    return pd.DataFrame(rows)


def stage_test(force: bool = False, version: str = "v1"):
    test_dir = _dirs(version)[1]
    test_dir.mkdir(parents=True, exist_ok=True)
    guard = test_dir / "TEST_RUN.json"
    if guard.exists() and not force:
        sys.exit(f"hold-out already evaluated ({guard}); re-running would turn 2020+ into a fit sample.")
    fr = load_frozen(version)
    d = load_data()
    allres = []
    for name, eq in fr["equations"].items():
        pdx, _ = predict(eq, d)
        frames = []
        for h in HORIZONS:
            dy = _future_change(pdx, eq["y"], h)
            ok = (pdx["month"] >= TEST_START) & pdx["gap"].notna() & dy.notna()
            frames.append(pd.DataFrame({"c": pdx.loc[ok, "c"], "month": pdx.loc[ok, "month"], "h": h,
                                        "gap": pdx.loc[ok, "gap"], "forecast": -eq["kappa"][h] * pdx.loc[ok, "gap"],
                                        "actual": dy[ok]}))
        fc = pd.concat(frames)
        fc.assign(month=fc["month"].astype(str)).to_csv(test_dir / f"mispricing_forecasts_{name}.csv", index=False,
                                                        float_format="%.4f")
        allres.append(forecast_eval(fc, f"mispricing_{name}"))
    if version == "v2":                     # the two group equations evaluated together as well
        both = pd.concat([pd.read_csv(test_dir / f"mispricing_forecasts_{n}.csv") for n in ("spread_eu", "spread_em")])
        allres.append(forecast_eval(both, "mispricing_spread_v2"))
    if version == "v1":
        # past-cases (analog) forecasts, out of sample; they use no fitted coefficients
        an = analog_forecasts(d, fr)
        an.assign(month=an["month"].astype(str)).to_csv(test_dir / "analog_forecasts.csv", index=False,
                                                        float_format="%.4f")
        for asset, g in an.groupby("asset"):
            allres.append(forecast_eval(g, f"analog_{asset}"))
    res = pd.concat(allres, ignore_index=True)
    res.to_csv(test_dir / "forecast_tests.csv", index=False, float_format="%.4f")
    guard.write_text(json.dumps({"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "frozen_params_created_utc": fr["created_utc"]}, indent=1))
    print(res[(res.scope == "pooled")].round(3).to_string())


# ============================================================ past cases
def _analog_matrix(d: pd.DataFrame, fr: dict) -> pd.DataFrame:
    """Pooled z-scores of the lagged factors (fit-sample standardisation)."""
    std = fr["equations"]["spread"]["std"]
    Z = pd.DataFrame({k: (d[k] - std[k][0]) / std[k][1] for k in ANALOG_F})
    return Z.groupby(d["c"]).ffill()


def _neighbours(Z, d, i, cand_mask, k=5, min_dims=8):
    """k nearest candidates to row i (RMS distance over shared non-missing
    factors); at most one case per country within any 12-month window."""
    zi = Z.iloc[i].values
    C = Z[cand_mask].values
    both = ~np.isnan(C) & ~np.isnan(zi)
    nd = both.sum(1)
    diff = np.where(both, C - zi, 0.0)
    dist = np.sqrt((diff ** 2).sum(1) / np.maximum(nd, 1))
    dist[nd < min_dims] = np.inf
    cand = d[cand_mask].assign(dist=dist).sort_values("dist")
    picked = []
    for r in cand.itertuples():
        if not np.isfinite(r.dist):
            break
        if any(p.c == r.c and abs((p.month - r.month).n) < 12 for p in picked):
            continue
        picked.append(r)
        if len(picked) == k:
            break
    return picked


def analog_forecasts(d: pd.DataFrame, fr: dict) -> pd.DataFrame:
    """Out-of-sample: for each country-month from 2020, average the next-h
    change of the five nearest past cases whose h-month outcome was already
    known (case month + h <= query month); cases are other countries, or the
    same country more than 24 months earlier."""
    d = d.reset_index(drop=True)
    Z = _analog_matrix(d, fr)
    out = {h: _future_change(d, "spread", h) for h in HORIZONS}
    fxr = {h: -100 * np.log(d.groupby("c")["fx_end"].shift(-h) / d["fx_end"]) for h in HORIZONS}
    rows = []
    for i in d.index[(d["month"] >= TEST_START) & d["c"].isin(SPREAD_C)]:
        c, m = d.at[i, "c"], d.at[i, "month"]
        for h in HORIZONS:
            known = (d["month"] + h <= m) & (((d["c"] != c)) | (d["month"] <= m - 24)) & d["c"].isin(SPREAD_C)
            for asset, target in (("spread", out[h]), ("fx", fxr[h])):
                if asset == "fx" and c not in FX_C:
                    continue
                if pd.isna(target.iloc[i]):
                    continue
                mask = known & target.notna()
                if asset == "fx":
                    mask &= d["c"].isin(FX_C)
                nb = _neighbours(Z, d, i, mask.values)
                if not nb:
                    continue
                rows.append({"c": c, "month": m, "h": h, "asset": asset,
                             "forecast": float(np.mean([target.iloc[r.Index] for r in nb])),
                             "actual": float(target.iloc[i])})
    return pd.DataFrame(rows)


# ================================================================= outputs
def _fair_value_and_factors(fr: dict, d: pd.DataFrame, names: list[str]):
    """Fair value rows and factor contributions.  Contributions are measured
    against the country's own 2005-2019 average of each factor, so
    baseline + contributions = fair value."""
    fv_rows, fac_rows = [], []
    for name in names:
        eq = fr["equations"][name]
        pdx, X = predict(eq, d)
        cols = eq["cols"]
        b = pd.Series(eq["beta"])[cols]
        fitmask = (pdx["month"] <= FIT_END) & pdx[eq["y"]].notna()
        xbar = X[fitmask].groupby(pdx.loc[fitmask, "c"]).mean()[cols]
        base = {c: eq["alpha"][c] + float(xbar.loc[c] @ b) for c in xbar.index}
        is_fx = eq["y"] == "fx_rer"
        asset = "fx_pct" if is_fx else "spread_bp"
        group = {k: ("commodities" if k.startswith("commod_") else k) for k in cols}
        for i in pdx.index[pdx["fitted"].notna()]:
            c, m = pdx.at[i, "c"], pdx.at[i, "month"]
            date = f"{m}-01"
            if not is_fx:
                if pd.isna(pdx.at[i, "spread"]):
                    continue
                fv_rows.append({"country": ISO3[c], "date": date, "asset": "spread_bp", "actual": pdx.at[i, "spread"],
                                "fair_value": pdx.at[i, "fitted"], "gap": pdx.at[i, "gap"], "gap_z": pdx.at[i, "gap_z"]})
            else:
                spot, gap = pdx.at[i, "fx_spot"], pdx.at[i, "gap"]
                if pd.isna(spot) or pd.isna(gap):
                    continue
                fv_rows.append({"country": ISO3[c], "date": date, "asset": "fx_per_usd", "actual": spot,
                                "fair_value": spot * np.exp(-gap / 100), "gap": gap, "gap_z": pdx.at[i, "gap_z"]})
            if m.year < 2015 or c not in xbar.index:
                continue
            fac_rows.append({"country": ISO3[c], "date": date, "asset": asset,
                             "factor": "baseline (country average 2005-2019)", "contribution": base[c]})
            ctr = (X.loc[i, cols] - xbar.loc[c]) * b
            for key, v in ctr.groupby(group).sum().items():
                fac_rows.append({"country": ISO3[c], "date": date, "asset": asset,
                                 "factor": LABELS.get(key, key), "contribution": float(v)})
    return pd.DataFrame(fv_rows), pd.DataFrame(fac_rows)


def stage_outputs():
    """Dashboard files (names and columns fixed by forecast-panel's
    site/config.yaml): spread fair value and factors from the v2 (post-hoc,
    group-specific) spread equations; similar cases (model-free); what-if from
    v2.  The v1 (frozen, tested) outputs and the currency equation are written
    to subfolders/files of their own."""
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_data()
    v1, v2 = load_frozen("v1"), load_frozen("v2")
    fv, fac = _fair_value_and_factors(v2, d, ["spread_eu", "spread_em"])
    fv.to_csv(OUT / "fair_value.csv", index=False, float_format="%.4f")
    fac.to_csv(OUT / "factors.csv", index=False, float_format="%.3f")
    similar_cases(d, v1).to_csv(OUT / "similar_cases.csv", index=False, float_format="%.3f")
    pd.concat([what_if(d, v2, ["spread_eu", "spread_em"]), what_if(d, v1, ["fx"])]).to_csv(
        OUT / "what_if.csv", index=False, float_format="%.2f")
    fxv, fxf = _fair_value_and_factors(v1, d, ["fx"])
    fxv.to_csv(OUT / "fx_fair_value.csv", index=False, float_format="%.4f")
    fxf.to_csv(OUT / "fx_factors.csv", index=False, float_format="%.3f")
    sub = OUT / "v1_frozen"
    sub.mkdir(exist_ok=True)
    f1, a1 = _fair_value_and_factors(v1, d, ["spread"])
    f1.to_csv(sub / "fair_value.csv", index=False, float_format="%.4f")
    a1.to_csv(sub / "factors.csv", index=False, float_format="%.3f")
    what_if(d, v1, ["spread"]).to_csv(sub / "what_if.csv", index=False, float_format="%.2f")


def similar_cases(d: pd.DataFrame, fr: dict, start="2007-01") -> pd.DataFrame:
    d = d.reset_index(drop=True)
    Z = _analog_matrix(d, fr)
    sp = {h: _future_change(d, "spread", h) for h in (3, 6, 12)}
    fx = {h: -100 * np.log(d.groupby("c")["fx_end"].shift(-h) / d["fx_end"]) for h in (3, 6, 12)}
    rows = []
    q = d.index[(d["month"] >= pd.Period(start, "M")) & d["c"].isin(SPREAD_C)]
    for i in q:
        c, m = d.at[i, "c"], d.at[i, "month"]
        mask = ((d["month"] + 3 <= m) & ((d["c"] != c) | (d["month"] <= m - 24))
                & d["c"].isin(SPREAD_C) & d["spread"].notna()).values
        for r in _neighbours(Z, d, i, mask):
            j = r.Index
            fmt = lambda s, unit: "/".join("n/a" if pd.isna(s[h].iloc[j]) or d.at[j, "month"] + h > m
                                           else f"{s[h].iloc[j]:+.0f}{unit}" if unit == "bp"
                                           else f"{s[h].iloc[j]:+.1f}{unit}" for h in (3, 6, 12))
            note = f"spread {fmt(sp, 'bp')} at 3/6/12m"
            if r.c in FX_C:
                note += f"; currency vs USD {fmt(fx, '%')}"
            elif r.c in EURO:
                note += "; currency: euro"
            rows.append({"country": ISO3[c], "date": f"{m}-01", "asset": "spread_bp", "case_country": ISO3[r.c],
                         "case_date": f"{r.month}-01", "similarity": 1 / (1 + r.dist), "outcome_note": note})
    return pd.DataFrame(rows)


SCENARIOS = {
    "lose_majority": "government loses its majority (seat share to 45%; already-minority governments: -10pp)",
    "deficit_plus1": "fiscal deficit +1 point of GDP (enters with the 12-month publication lag)",
    "downgrade_1": "one-notch rating downgrade (average of the three agencies)",
    "populism_plus1sd": "governing parties' populism (V-Party) up one standard deviation",
}


def what_if(d: pd.DataFrame, fr: dict, names: list[str]) -> pd.DataFrame:
    rows = []
    for name in names:
        eq = fr["equations"][name]
        cols, b = eq["cols"], np.array([eq["beta"][k] for k in eq["cols"]])
        V = np.array(eq["cov"])
        std, cm = eq["std"], eq["cmeans"]
        pdx, X = predict(eq, d)
        for c in FOCUS:
            if c not in eq["countries"]:
                continue
            g = pdx[(pdx["c"] == c) & pdx[eq["y"]].notna()]
            i = g.index.max()
            x0 = X.loc[i, cols].astype(float)
            raw_seat = d.at[i, "seat_share"]
            for sc, desc in SCENARIOS.items():
                x1 = x0.copy()
                note = ""
                if sc == "lose_majority":
                    new = 45.0 if raw_seat >= 50 else raw_seat - 10
                    note = "" if raw_seat >= 50 else f"already a minority ({raw_seat:.0f}%): seat share -10pp"
                    x1["seat_share"] += (new - raw_seat) / std["seat_share"][1]
                elif sc == "deficit_plus1":
                    x1["deficit"] += 1 / std["deficit"][1]
                elif sc == "downgrade_1":
                    x1["rating"] -= 1 / std["rating"][1]
                elif sc == "populism_plus1sd":
                    x1["populism_vparty"] += 1.0
                dc = x1["debt"] - cm["debt"].get(c, 0.0)
                x1["debt_x_seat"] = dc * (x1["seat_share"] - cm["seat_share"].get(c, 0.0))
                dx = (x1 - x0).values
                eff, se = float(dx @ b), float(np.sqrt(dx @ V @ dx))
                rows.append({"country": ISO3[c], "date": f"{d.at[i, 'month']}-01",
                             "asset": "fx_pct" if eq["y"] == "fx_rer" else "spread_bp", "scenario": sc,
                             "description": desc, "estimate": eff, "lo90": eff - 1.645 * se, "hi90": eff + 1.645 * se,
                             "se": se, "note": note})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    ver = "v2" if "--v2" in sys.argv else "v1"
    if cmd == "data":
        build_data()
    elif cmd == "fit":
        stage_fit(ver)
    elif cmd == "test":
        stage_test("--force" in sys.argv, ver)
    elif cmd == "outputs":
        stage_outputs()
    else:
        sys.exit(__doc__)
