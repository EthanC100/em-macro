"""Diagnostics of the frozen v1.0 systematic strategy (spec §17.2 Builds 1-3).

    python -m em_macro.diagnostics attribution   # Build 1 -> results/diagnostics/attribution_*.csv
    python -m em_macro.diagnostics risk          # Build 2 -> results/diagnostics/risk_*.csv
    python -m em_macro.diagnostics stats         # Build 3 -> results/diagnostics/stats_*.csv (needs trials.csv)
    python -m em_macro.diagnostics report        # results/diagnostics_v1.md from the saved tables

Read-only with respect to the strategy: it imports em_macro.systematic (tag v1.0-frozen) and
re-runs it exactly as frozen; no trading logic is changed.
"""
from __future__ import annotations

import itertools
import math
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import mtstats as MT
from . import panel_sources as PS
from . import sources as S
from . import systematic as SY
from .config import PROC, RESULTS, ROOT

OUT = RESULTS / "diagnostics"
REPORT = RESULTS / "diagnostics_v1.md"
PERIODS = {"2005-2019": (None, SY.FIT_END), "2020-01 to 2026-09": (SY.TEST_START, pd.Period("2026-09", "M"))}
SIGNALS = ["carry", "trend", "value"]
COUNTRY = {"BRL": "Brazil", "MXN": "Mexico", "ZAR": "South Africa", "TRY": "Turkey", "IDR": "Indonesia",
           "PLN": "Poland", "GBP": "United Kingdom", "COP": "Colombia", "CLP": "Chile", "EUR": "euro area",
           "BR10Y": "Brazil", "MX10Y": "Mexico", "ZA10Y": "South Africa", "TR10Y": "Turkey", "ID10Y": "Indonesia",
           "CO10Y": "Colombia", "CL10Y": "Chile", "FR-DE": "France", "IT-DE": "Italy", "ES-DE": "Spain",
           "GB-DE": "United Kingdom", "PL-DE": "Poland", "DE10Y": "Germany"}
EM8 = ["BRL", "MXN", "ZAR", "TRY", "IDR", "PLN", "COP", "CLP"]


def _period(df, name):
    a, b = PERIODS[name]
    return df.loc[a:b]


# =========================================================== v1 per position
def v1_positions():
    """Per-instrument monthly gross P&L, cost and net of the frozen v1, decomposed
    exactly as SY.run aggregates them (FX weights earn t+1, bond weights t+2)."""
    inp = SY.build_inputs()
    res = SY.run(inp, SY.VARIANTS["combined"])
    W = res.attrs["weights"]
    lag = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}
    gross, cost, book = {}, {}, {}
    for b in ("fx", "bond"):
        for k in inp[b]["ret"].columns:
            w = W[k]
            gross[k] = (w.shift(lag[b]) * inp[b]["ret"][k]).fillna(0.0)
            cost[k] = (w.diff().abs().shift(lag[b]) * inp["cost"][k]).fillna(0.0)
            book[k] = b
    gross, cost = pd.DataFrame(gross).loc[res.index], pd.DataFrame(cost).loc[res.index]
    net = gross - cost
    err = float((net.sum(axis=1) - res["net"]).abs().max())
    assert err < 1e-12, f"per-position P&L does not add up to v1 net ({err})"
    return inp, res, W, net, book, lag


# ============================================================ Build 1
def signal_shares(inp, book, lag, months) -> dict[str, pd.DataFrame]:
    """Spec proportional rule, evaluated at each position's decision month:
    share_k = (z_k/K)/S if |S| > 0.1 else 1/K, K = number of available signals,
    S = their mean (= the v1 composite)."""
    out = {k: [] for k in SIGNALS}
    for b in ("fx", "bond"):
        sig = SY.signals(inp[b])
        Z = {k: sig[k] for k in SIGNALS}
        K = sum(z.notna().astype(float) for z in Z.values())
        Ssum = sum(z.fillna(0.0) for z in Z.values())
        Smean = Ssum / K.replace(0, np.nan)
        for k in SIGNALS:
            prop = (Z[k] / K) / Smean
            eq = Z[k].notna() / K.replace(0, np.nan)
            sh = prop.where(Smean.abs() > 0.1, eq).where(Z[k].notna(), 0.0)
            out[k].append(sh.shift(lag[b]))
    return {k: pd.concat(v, axis=1).reindex(months).fillna(0.0) for k, v in out.items()}


def shapley(inp, period: str) -> pd.DataFrame:
    """Exact Shapley values over the 2^3 signal subsets.  v(S) = annualised mean
    net return (% a year) of v1 run with only the signals in S (same frozen
    machinery, each subset re-scaled to 10% volatility); v(empty) = 0."""
    val = {(): 0.0}
    for r in range(1, 4):
        for sub in itertools.combinations(SIGNALS, r):
            net = SY.run(inp, list(sub))["net"]
            val[sub] = 1200 * _period(net, period).mean()
    rows = []
    n = len(SIGNALS)
    for k in SIGNALS:
        others = [s for s in SIGNALS if s != k]
        phi = 0.0
        for r in range(0, n):
            for sub in itertools.combinations(others, r):
                with_k = tuple(s for s in SIGNALS if s in sub or s == k)
                wgt = math.factorial(len(sub)) * math.factorial(n - len(sub) - 1) / math.factorial(n)
                phi += wgt * (val[with_k] - val[tuple(s for s in SIGNALS if s in sub)])
        rows.append({"period": period, "signal": k, "shapley_%pa": phi})
    vals = pd.DataFrame([{"period": period, "subset": "+".join(s) if s else "(none)", "ann_mean_net_%": v}
                         for s, v in val.items()])
    return pd.DataFrame(rows), vals


def factor_series(months) -> pd.DataFrame:
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    me = lambda s: SY._me(s).reindex(months)
    f = pd.DataFrame(index=months)
    f["DXY_%"] = 100 * np.log(me(daily["DXY"])).diff()
    f["dUS2y_bp"] = 100 * me(S.fred("DGS2")).diff()
    f["dUS10y_bp"] = 100 * me(daily["US10Y"]).diff()
    f["MSCI_World_%"] = 100 * me(S.yahoo("^990100-USD-STRD")).pct_change()
    com = S.fred("PALLFNFINDEXM")
    f["Commodities_%"] = 100 * np.log(com.groupby(com.index.to_period("M")).last().reindex(months)).diff()
    spot = {k: daily[f"FX_{c}"] for k, c in SY.FX_INSTR.items() if c in ("BR", "MX", "ZA", "TR", "ID", "PL")}
    spot["COP"], spot["CLP"] = PS.colombia_trm(), PS.chile_dolar_observado()
    em = pd.DataFrame({k: -100 * np.log(me(v)).diff() for k, v in spot.items()})
    f["EM_FX_basket_%"] = em[EM8].mean(axis=1)
    f["dVIX_pts"] = me(daily["VIX"]).diff()
    return f


def factor_regression(ret_pct: pd.Series, F: pd.DataFrame) -> pd.DataFrame:
    d = pd.concat([ret_pct.rename("r"), F], axis=1).dropna()
    m = sm.OLS(d["r"], sm.add_constant(d[F.columns])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    rows = [{"term": "alpha (% a year)", "coef": 12 * m.params["const"], "t": m.tvalues["const"],
             "contribution_%pa": 12 * m.params["const"]}]
    for c in F.columns:
        rows.append({"term": c, "coef": m.params[c], "t": m.tvalues[c],
                     "contribution_%pa": 12 * m.params[c] * d[c].mean()})
    out = pd.DataFrame(rows)
    out.attrs.update(r2=m.rsquared, n=int(m.nobs))
    return out


def stage_attribution():
    OUT.mkdir(parents=True, exist_ok=True)
    inp, res, W, net, book, lag = v1_positions()
    months = net.index
    shares = signal_shares(inp, book, lag, months)
    F = factor_series(months)
    rows_c, rows_a, rows_s, rows_i, rows_f, rows_sh, rows_v, summ = [], [], [], [], [], [], [], []
    for p in PERIODS:
        N = _period(net, p)
        tot = N.sum().sum()
        ann = lambda x: 1200 * x / len(N)
        # by instrument and country (sum of monthly contributions, % of capital; and % a year)
        inst = N.sum()
        for k, v in inst.items():
            rows_i.append({"period": p, "instrument": k, "country": COUNTRY[k], "book": book[k],
                           "pnl_sum_%": 100 * v, "pnl_%pa": ann(v), "share_of_total": v / tot})
        ctry = inst.groupby(lambda k: COUNTRY[k]).sum().sort_values(ascending=False)
        fxc = inst[[k for k in inst.index if book[k] == "fx"]].groupby(lambda k: COUNTRY[k]).sum()
        bdc = inst[[k for k in inst.index if book[k] == "bond"]].groupby(lambda k: COUNTRY[k]).sum()
        for c, v in ctry.items():
            rows_c.append({"period": p, "country": c, "fx_%pa": ann(fxc.get(c, 0.0)), "bonds_%pa": ann(bdc.get(c, 0.0)),
                           "total_%pa": ann(v), "share_of_total": v / tot})
        for b in ("fx", "bond"):
            v = inst[[k for k in inst.index if book[k] == b]].sum()
            rows_a.append({"period": p, "asset_class": "FX" if b == "fx" else "bonds", "pnl_%pa": ann(v),
                           "share_of_total": v / tot})
        alloc = 0.0
        for k in SIGNALS:
            v = (N * _period(shares[k], p)).sum().sum()
            alloc += v
            rows_s.append({"period": p, "signal": k, "method": "proportional", "pnl_%pa": ann(v),
                           "share_of_total": v / tot})
        rows_s.append({"period": p, "signal": "unattributed (position held by the no-trade band, no signal at decision)",
                       "method": "proportional", "pnl_%pa": ann(tot - alloc), "share_of_total": (tot - alloc) / tot})
        sh, vals = shapley(inp, p)
        rows_sh.append(sh)
        rows_v.append(vals)
        fr = factor_regression(100 * _period(res["net"], p), _period(F, p))
        fr.insert(0, "period", p)
        fr["r2"], fr["n"] = fr.attrs["r2"], fr.attrs["n"]
        rows_f.append(fr)
        top3 = ctry.head(3)
        brl_mxn = inst.get("BRL", 0) + inst.get("MXN", 0)
        br_mx = ctry.get("Brazil", 0) + ctry.get("Mexico", 0)
        summ.append({"period": p, "total_net_%pa": ann(tot), "top3_countries": ", ".join(top3.index),
                     "top3_share": top3.sum() / tot, "BRL_MXN_share": brl_mxn / tot,
                     "flag_BRL_MXN_over_50%": bool(brl_mxn / tot > 0.5),
                     "Brazil_Mexico_all_instruments_share": br_mx / tot})
    pd.DataFrame(rows_i).to_csv(OUT / "attribution_instrument.csv", index=False, float_format="%.4f")
    pd.DataFrame(rows_c).to_csv(OUT / "attribution_country.csv", index=False, float_format="%.4f")
    pd.DataFrame(rows_a).to_csv(OUT / "attribution_asset_class.csv", index=False, float_format="%.4f")
    sig = pd.DataFrame(rows_s)
    shp = pd.concat(rows_sh)
    tot = {s["period"]: s["total_net_%pa"] for s in summ}
    shp["share_of_total"] = shp["shapley_%pa"] / shp["period"].map(tot)
    shp = shp.rename(columns={"shapley_%pa": "pnl_%pa"}).assign(method="Shapley")
    pd.concat([sig, shp[sig.columns]]).to_csv(OUT / "attribution_signal.csv", index=False, float_format="%.4f")
    pd.concat(rows_v).to_csv(OUT / "attribution_shapley_subsets.csv", index=False, float_format="%.4f")
    pd.concat(rows_f).to_csv(OUT / "attribution_factors.csv", index=False, float_format="%.4f")
    pd.DataFrame(summ).to_csv(OUT / "attribution_summary.csv", index=False, float_format="%.4f")
    print(pd.DataFrame(summ).to_string())


# ============================================================ Build 2
def ledoit_wolf(X: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage towards a scaled identity (the estimator of
    sklearn.covariance.LedoitWolf).  X: n observations x p variables."""
    X = X - X.mean(axis=0)
    n, p = X.shape
    Sm = X.T @ X / n
    mu = np.trace(Sm) / p
    delta = ((Sm - mu * np.eye(p)) ** 2).sum() / p
    X2 = X ** 2
    beta_bar = ((X2.T @ X2) / n - Sm ** 2).sum() / (p * n)
    shrink = 0.0 if delta == 0 else min(beta_bar, delta) / delta
    return shrink * mu * np.eye(p) + (1 - shrink) * Sm, float(shrink)


def risk_decomposition(w: np.ndarray, R: np.ndarray, Fm: np.ndarray, scale: float):
    """Position risk contributions and USD/EM factor shares.
    R: window returns (n x p) of the instruments, Fm: factor returns (n x 2).
    Sigma = Ledoit-Wolf(R) * scale (annualising); B = OLS betas of R on Fm;
    factor share_f = beta_f (Omega beta)_f / sigma_p^2 with beta = B'w."""
    Sig, shrink = ledoit_wolf(R)
    Sig *= scale
    var_p = float(w @ Sig @ w)
    sp = np.sqrt(var_p)
    rc = w * (Sig @ w) / sp                      # sums to sigma_p
    X = np.column_stack([np.ones(len(Fm)), Fm])
    B = np.linalg.lstsq(X, R, rcond=None)[0][1:]  # 2 x p
    Om = np.cov(Fm, rowvar=False) * scale
    beta = B @ w
    fs = beta * (Om @ beta) / var_p
    return sp, rc / sp, fs, shrink


def stage_risk():
    OUT.mkdir(parents=True, exist_ok=True)
    from . import overlay as OV
    inp, res, W, net, book, lag = v1_positions()
    months = res.index
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    rd = OV.daily_returns(inp["months"])
    dly = list(rd.columns)                                   # 10 currencies + BR/MX/ZA/TR 10y
    usd_d = np.log(daily["DXY"]).diff().reindex(rd.index)
    em_d = rd[EM8].mean(axis=1)
    usd_m = np.log(SY._me(daily["DXY"])).diff().reindex(inp["months"])
    allR = pd.concat([inp["fx"]["ret"], inp["bond"]["ret"]], axis=1)
    em_m = inp["fx"]["ret"][EM8].mean(axis=1)

    def held(m):
        """Positions earning in month m+1 under v1's accounting: FX decided at m,
        bonds decided at m-1 (one-month bond execution lag)."""
        w = pd.Series({k: W.at[m, k] if book[k] == "fx" else (W.at[m - 1, k] if (m - 1) in W.index else 0.0)
                       for k in W.columns})
        return w

    rows, pos_rows = [], []
    for m in months:
        w_all = held(m)
        if w_all.abs().sum() == 0:
            continue
        end = m.end_time.normalize()
        # (A) spec version: Ledoit-Wolf on non-overlapping 3-day returns, daily-priced instruments
        win = rd.loc[:end].tail(252)
        fwin = pd.concat([usd_d, em_d], axis=1).loc[win.index]
        blk = np.arange(len(win)) // 3
        R3 = win.fillna(0.0).groupby(blk).sum()
        F3 = fwin.fillna(0.0).groupby(blk).sum()
        wA = w_all[dly].values
        recA = {}
        if len(R3) >= 60 and np.abs(wA).sum() > 0:
            sp, rc, fs, sh = risk_decomposition(wA, R3.values, F3.values, 252 / 3)
            recA = {"A_sigma_p_%": 100 * sp, "A_usd_share": fs[0], "A_em_share": fs[1],
                    "A_usd_em_share": fs.sum(), "A_shrinkage": sh,
                    "A_gross_notional_coverage": np.abs(wA).sum() / w_all.abs().sum(),
                    "A_top_position": dly[int(np.argmax(rc))], "A_top_position_share": float(rc.max())}
            for k, v in zip(dly, rc):
                if wA[dly.index(k)] != 0:
                    pos_rows.append({"month": str(m), "version": "A (3-day, daily-priced)", "instrument": k,
                                     "weight": wA[dly.index(k)], "risk_share": v})
        # (B) full book: Ledoit-Wolf on trailing 60 monthly returns, all 23 instruments
        Rm = allR.loc[:m].tail(60)
        Fm = pd.concat([usd_m, em_m], axis=1).loc[Rm.index]
        recB = {}
        if Rm.dropna(how="all").shape[0] >= 36:
            Rf = Rm.fillna(0.0)
            wB = w_all[Rf.columns].values
            sp, rc, fs, sh = risk_decomposition(wB, Rf.values, Fm.fillna(0.0).values, 12)
            recB = {"B_sigma_p_%": 100 * sp, "B_usd_share": fs[0], "B_em_share": fs[1], "B_usd_em_share": fs.sum(),
                    "B_shrinkage": sh, "B_top_position": Rf.columns[int(np.argmax(rc))],
                    "B_top_position_share": float(rc.max())}
            for k, v in zip(Rf.columns, rc):
                if w_all[k] != 0:
                    pos_rows.append({"month": str(m), "version": "B (monthly, full book)", "instrument": k,
                                     "weight": w_all[k], "risk_share": v})
        rows.append({"month": str(m), "n_positions": int((w_all != 0).sum()),
                     "gross_leverage": float(w_all.abs().sum()), **recA, **recB})
    ts = pd.DataFrame(rows)
    ts.to_csv(OUT / "risk_monthly.csv", index=False, float_format="%.4f")
    pos = pd.DataFrame(pos_rows)
    pos.to_csv(OUT / "risk_positions.csv", index=False, float_format="%.4f")
    print(ts[[c for c in ts.columns if "share" in c and "top" not in c]].describe().round(3).to_string())


# ============================================================ Build 3
def v1_monthly_returns() -> pd.Series:
    p = pd.read_csv(RESULTS / "systematic" / "paper_pnl.csv")
    return pd.Series(p["net"].values, index=pd.PeriodIndex(p["month"], freq="M"))


def stage_stats():
    OUT.mkdir(parents=True, exist_ok=True)
    trials = pd.read_csv(ROOT / "trials.csv")
    N_spec = 7
    N_ledger = int(trials["trial_group"].nunique())
    r = v1_monthly_returns()
    rows = []
    T, sr_ann = 81, 0.65
    sr_m = sr_ann / np.sqrt(12)
    scen = {"S1 normal (spec)": (0.0, 3.0), "S2 carry-like (spec)": (-0.7, 5.0), "S3 severe (spec)": (-1.0, 6.0)}
    oos = r.loc["2020-01":"2026-09"]
    g3, g4 = float(oos.skew()), float(oos.kurt() + 3)
    act_sr_m = float(oos.mean() / oos.std())
    scen[f"actual v1 2020-01..2026-09 (skew {g3:.2f}, kurt {g4:.2f})"] = (g3, g4)
    fit = r.loc[:"2019-12"]
    g3i, g4i = float(fit.skew()), float(fit.kurt() + 3)
    nv = MT.naive_test(sr_ann, T / 12)
    for name, (a, b) in scen.items():
        for N, label in ((N_spec, "spec N=7"), (N_ledger, f"ledger N={N_ledger}")):
            sd_noise = 1 / np.sqrt(T - 1)
            sd_disp = 0.20 / np.sqrt(12)
            rows.append({
                "scenario": name, "trials": label, "SR_ann": sr_ann, "T_months": T, "skew": a, "kurtosis": b,
                "t": nv["t"], "p_two_sided": nv["p_two_sided"],
                "PSR(SR*=0)": MT.psr(sr_m, T, a, b),
                "SR0_noise_ann": MT.sr0(N, sd_noise) * np.sqrt(12),
                "DSR_noise": MT.dsr(sr_m, T, N, sd_noise, a, b),
                "SR0_dispersed_ann": MT.sr0(N, sd_disp) * np.sqrt(12),
                "DSR_dispersed": MT.dsr(sr_m, T, N, sd_disp, a, b),
                "MinTRL_90%_years": MT.min_trl(sr_m, a, b, 0.90) / 12,
                "MinTRL_95%_years": MT.min_trl(sr_m, a, b, 0.95) / 12,
                "MinTRL_90%_vs_SR0_years": MT.min_trl(sr_m, a, b, 0.90, MT.sr0(N, sd_noise)) / 12,
                "HL_Bonferroni_SR": MT.haircut_bonferroni(sr_ann, T / 12, N),
                "HL_Sidak_SR": MT.haircut_sidak(sr_ann, T / 12, N),
                "HL_BHY_SR": MT.haircut_bhy(sr_ann, T / 12, N)})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "stats_v1.csv", index=False, float_format="%.4f")
    extra = pd.DataFrame([{"sample": "2020-01..2026-09 (test)", "months": len(oos), "SR_ann_actual": act_sr_m * np.sqrt(12),
                           "skew": g3, "kurtosis_raw": g4},
                          {"sample": "2006-02..2019-12 (design)", "months": len(fit),
                           "SR_ann_actual": float(fit.mean() / fit.std() * np.sqrt(12)), "skew": g3i, "kurtosis_raw": g4i}])
    extra.to_csv(OUT / "stats_moments.csv", index=False, float_format="%.4f")
    print(tab.round(3).to_string())
    print(extra.round(3).to_string())


# ================================================================= report
def _md(df: pd.DataFrame, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    cols = list(df.columns)
    L = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        cells = []
        for c, v in zip(cols, r):
            if isinstance(v, (float, np.floating)):
                f = fmt.get(c, "{:.2f}")
                cells.append("" if pd.isna(v) else f.format(v))
            else:
                cells.append(str(v))
        L.append("| " + " | ".join(cells) + " |")
    return "\n".join(L)


def stage_report():
    from .diagnostics_report import build
    REPORT.write_text(build())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"attribution": stage_attribution, "risk": stage_risk, "stats": stage_stats,
     "report": stage_report}.get(cmd, lambda: sys.exit(__doc__))()
