"""Trial T17: factor-capped sizing (pre-registration docs/prereg/T16-T19_risk_batch.md, section 3.2).

The one change to v1.0: at each decision month its target weights w0 (after the 10% total rescaling) are
adjusted so that the USD factor's share of ex-ante portfolio risk is at most 25% and the EM FX factor's
share at most 40% (spec section 7 caps), by

    w = argmin ||w - w0||^2  s.t.  share_USD(w) <= 0.25,  share_EM(w) <= 0.40

(SLSQP from w0; projection fallback), then re-scaled to the 10% target with v1.0's own rule (spec Build 5
order), then v1.0's 6x cap, 25% band and costs.  Risk measure: the risk audit's version B -- Ledoit-Wolf
covariance of the trailing 60 monthly returns (NaN -> 0, at least 36 months with data), factors USD =
month-end log change of the dollar index and EM = equal-weight mean of the 8 EM currencies' monthly excess
returns, B = OLS betas, Omega = factor covariance, share_f = beta_f (Omega beta)_f / (w' Sigma w).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import systematic as SY
from . import tstrend as TS
from .config import PROC

CAPS = {"USD": 0.25, "EM": 0.40}
WINDOW, MIN_MONTHS = 60, 36
TOL = 1e-6
EM8 = ["BRL", "MXN", "ZAR", "TRY", "IDR", "PLN", "COP", "CLP"]
V1 = ["carry", "trend", "value"]


def ledoit_wolf(X: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf (2004) shrinkage towards a scaled identity (diagnostics.ledoit_wolf, same estimator)."""
    X = X - X.mean(axis=0)
    n, p = X.shape
    Sm = X.T @ X / n
    mu = np.trace(Sm) / p
    delta = ((Sm - mu * np.eye(p)) ** 2).sum() / p
    X2 = X ** 2
    beta_bar = ((X2.T @ X2) / n - Sm ** 2).sum() / (p * n)
    shrink = 0.0 if delta == 0 else min(beta_bar, delta) / delta
    return shrink * mu * np.eye(p) + (1 - shrink) * Sm


def factor_series(inp: dict) -> pd.DataFrame:
    """USD = month-end log change of DXY (daily panel); EM = mean monthly excess return of the 8 EM currencies."""
    months = inp["months"]
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    usd = np.log(SY._me(daily["DXY"])).diff().reindex(months)
    em = inp["fx"]["ret"].reindex(columns=[c for c in EM8 if c in inp["fx"]["ret"].columns]).mean(axis=1)
    return pd.DataFrame({"USD": usd, "EM": em.reindex(months)})


class RiskModel:
    """Sigma, B and Omega for one decision month."""

    def __init__(self, R: np.ndarray, F: np.ndarray, scale: float = 12.0):
        self.Sigma = ledoit_wolf(R) * scale
        X = np.column_stack([np.ones(len(F)), F])
        self.B = np.linalg.lstsq(X, R, rcond=None)[0][1:]          # 2 x p
        self.Omega = np.cov(F, rowvar=False) * scale

    def shares(self, w: np.ndarray) -> np.ndarray:
        var = float(w @ self.Sigma @ w)
        if var <= 0:
            return np.zeros(2)
        beta = self.B @ w
        return beta * (self.Omega @ beta) / var


def enforce_caps(w0: np.ndarray, rm: RiskModel, caps=(CAPS["USD"], CAPS["EM"])) -> tuple[np.ndarray, dict]:
    """min ||w - w0||^2 s.t. shares <= caps.  Returns (w, info)."""
    caps = np.asarray(caps, float)
    s0 = rm.shares(w0)
    info = {"shares_before": s0, "adjusted": False, "fallback": False, "iterations": 0}
    if np.all(s0 <= caps + TOL):
        return w0.copy(), {**info, "shares_after": s0}
    cons = [{"type": "ineq", "fun": (lambda w, k=k: caps[k] - rm.shares(w)[k])} for k in range(2)]
    res = minimize(lambda w: float(((w - w0) ** 2).sum()), w0, jac=lambda w: 2 * (w - w0), method="SLSQP",
                   constraints=cons, options={"ftol": 1e-12, "maxiter": 500})
    w = res.x
    s = rm.shares(w)
    info["iterations"] = int(res.nit)
    if np.all(s <= caps + TOL):
        return w, {**info, "adjusted": True, "shares_after": s}
    # fallback: remove the breached factors' exposure along their beta vectors, smallest feasible lambda
    breached = [k for k in range(2) if s0[k] > caps[k] + TOL]
    Bk = rm.B[breached].T                                   # p x m
    P = Bk @ np.linalg.pinv(Bk.T @ Bk) @ Bk.T               # projector onto span of the beta vectors
    Pw = P @ w0
    for lam in np.arange(1, 1001) / 1000:
        wl = w0 - lam * Pw
        sl = rm.shares(wl)
        if np.all(sl <= caps + TOL):
            return wl, {**info, "adjusted": True, "fallback": True, "lambda": lam, "shares_after": sl}
    wl = w0 - Pw
    return wl, {**info, "adjusted": True, "fallback": True, "lambda": 1.0, "shares_after": rm.shares(wl)}


def capped_targets(inp: dict, factors: pd.DataFrame, books=TS.BOOKS, caps=CAPS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """T17 targets after the caps and the re-scaling to 10% (before v1.0's 6x cap and band), plus a monthly log."""
    W0 = TS.core_targets(inp, V1, books)
    R_all = TS.all_returns(inp, books)
    cols = list(W0.columns)
    W = W0.copy()
    rows = []
    for t in W0.index:
        w0 = W0.loc[t].values.astype(float)
        if np.abs(w0).sum() == 0:
            continue
        Rm = R_all.loc[:t, cols].tail(WINDOW)
        if Rm.dropna(how="all").shape[0] < MIN_MONTHS:
            rows.append({"month": str(t), "modelled": False})
            continue
        F = factors.loc[Rm.index, ["USD", "EM"]].fillna(0.0).values
        rm = RiskModel(Rm.fillna(0.0).values, F)
        w, info = enforce_caps(w0, rm, (caps["USD"], caps["EM"]))
        W.loc[t] = w
        opened = int(((w0 == 0) & (np.abs(w) > 1e-10)).sum())
        rows.append({"month": str(t), "modelled": True, "usd_share_before": info["shares_before"][0],
                     "em_share_before": info["shares_before"][1], "usd_share_after": info["shares_after"][0],
                     "em_share_after": info["shares_after"][1], "adjusted": info["adjusted"],
                     "fallback": info["fallback"], "lambda": info.get("lambda", np.nan),
                     "distance": float(np.sqrt(((w - w0) ** 2).sum())), "gross_before": float(np.abs(w0).sum()),
                     "gross_after": float(np.abs(w).sum()), "positions_opened": opened,
                     "opened_gross": float(np.abs(w[(w0 == 0)]).sum())})
    W = TS.scale_to_vol(W, R_all)
    return W, pd.DataFrame(rows)


def run(inp: dict, factors: pd.DataFrame, books=TS.BOOKS, caps=CAPS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """T17 monthly P&L (systematic.run's columns; attrs['weights'] = held weights) and the cap log."""
    W, log = capped_targets(inp, factors, books, caps)
    return TS.finish(inp, W, books), log


def shares_of_held(W_held: pd.DataFrame, inp: dict, factors: pd.DataFrame, books=TS.BOOKS) -> pd.DataFrame:
    """Version-B USD and EM shares of a strategy's positions, month by month (positions held in month m+1:
    FX decided at m, bonds at m-1, as in the risk audit)."""
    R_all = TS.all_returns(inp, books)
    cols = list(W_held.columns)
    book = {c: b for b in books for c in inp[b]["ret"].columns}
    rows = []
    for m in W_held.index:
        w = pd.Series({k: W_held.at[m, k] if book[k] == "fx" else (W_held.at[m - 1, k] if (m - 1) in W_held.index else 0.0)
                       for k in cols})
        if w.abs().sum() == 0:
            continue
        Rm = R_all.loc[:m, cols].tail(WINDOW)
        if Rm.dropna(how="all").shape[0] < MIN_MONTHS:
            continue
        F = factors.loc[Rm.index, ["USD", "EM"]].fillna(0.0).values
        rm = RiskModel(Rm.fillna(0.0).values, F)
        s = rm.shares(w.values)
        rows.append({"month": str(m), "usd_share": s[0], "em_share": s[1], "usd_em_share": s.sum(),
                     "sigma_p": float(np.sqrt(w.values @ rm.Sigma @ w.values))})
    return pd.DataFrame(rows)
