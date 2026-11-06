"""Trials T20-T22: commodity carry, basis-momentum and diversified futures trend against frozen v1.1.

    EM_MACRO_DATA=... python -m em_macro.t2022 run       # -> results/T20-T22/*.csv, criteria.json, RUN.json
    python -m em_macro.t2022 report                      # -> results/T20-T22_commodity_trials.md

Pre-registration: docs/prereg/T20-T22_commodity_trials.md with Amendments 1-4 (Amendment 3: roll-rule guard;
Amendment 4: A4 not gating, C1 Holm p < 0.05 for T20 and T21, missing-month rule for vendor gaps).  Build 0:
results/T20-T22/build0.md.  v1.0 and v1.1 are imported and never modified (systematic.py, systematic_v11.py,
t18_rebal.py); the v1.1 reproduction check calls the comparison functions without writing any v1.1 file.

Licence: per-market price, return, weight and signal series are written only to the private data repo
(norgate/derived/trials/); this repository receives code, the report and aggregate tables (sleeve and portfolio
returns and statistics, which the pre-registration's section 7 requires).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import commod_build0 as B0
from . import commod_data as CD
from . import mtstats as MT
from . import systematic as SY
from . import systematic_v11 as V11
from . import t01 as T01
from . import t18_rebal as T18
from . import tstrend as TS
from .config import RESULTS, ROOT

OUT = RESULTS / "T20-T22"
SEED = 20261103
TEST = (pd.Period("2020-01", "M"), pd.Period("2026-09", "M"))
DESIGN = (pd.Period("2000-01", "M"), pd.Period("2019-12", "M"))
FULL = (pd.Period("2000-01", "M"), pd.Period("2026-09", "M"))
CW_WINDOW = (pd.Period("2010-01", "M"), pd.Period("2026-09", "M"))
SLEEVE_VOL = 0.10
BUDGET = 0.25
CAP_RISK = 0.10
MIN_ACTIVE = 6
COMMISSION = 3.0
NONINF_MARGIN = 0.05
C1_ALPHA = {"T20": 0.05, "T21": 0.05, "T22": 0.10}          # Amendment 4 (A4.2)
N_V11, N_TRIAL = 13, 16
CAPITAL_PAPER = 10_000_000

XS = list(CD.XS_UNIVERSE)                                     # 20 markets (Amendment 1)
XS_HALF = {"A": ["B", "NG", "G", "ZC", "ZS", "ZW", "KC", "CT", "LE", "GF"],
           "B": ["CL", "RB", "HO", "HG", "KE", "ZM", "ZL", "SB", "CC", "HE"]}
T22_HALF = {"A": ["B", "NG", "G", "SI", "PL", "ZC", "ZS", "ZW", "KC", "CT", "LE", "GF", "6M", "6E", "FGBL", "FBON"],
            "B": ["CL", "RB", "HO", "HG", "GC", "PA", "KE", "ZM", "ZL", "SB", "CC", "HE",
                  "6L", "6Z", "6B", "R", "FOAT", "FBTP"]}
FX_CCY = {"FGBL": "EUR", "FOAT": "EUR", "FBTP": "EUR", "R": "GBP"}

DECISIONS = []      # implementation readings taken under the simplest-reading rule (reported)


def note(s: str):
    if s not in DECISIONS:
        DECISIONS.append(s)


# ============================================================ market preparation
def build0_dropped() -> set[str]:
    """Markets dropped by the Build 0 data rules (coverage gate; not in Norgate)."""
    b0 = json.loads((OUT / "build0.json").read_text())
    drop = {c for c, m in b0["markets"].items() if m["coverage"]["coverage"] is not None
            and m["coverage"]["coverage"] < 0.95}
    drop |= {c for c, m in CD.MARKETS.items() if m.norgate is None}
    return drop


def fx_daily() -> pd.DataFrame:
    """USD per EUR and per GBP, daily (FRED DEXUSEU, DEXUSUK) via the programme's loader."""
    from . import sources as S
    return pd.DataFrame({"EUR": S.fred("DEXUSEU"), "GBP": S.fred("DEXUSUK")}).sort_index()


class Mkt:
    """One market's daily and monthly data for the trials."""

    def __init__(self, code: str, fx: pd.DataFrame):
        self.code = code
        self.md = md = CD.MarketData(code)
        self.m = md.m
        self.rolls = md.rolls.dropna(subset=["F1"]).copy()
        self.days = md.close.index
        self.ct = md.contracts
        self.r1 = md.daily_returns("F1")
        self.r2 = md.daily_returns("F2")
        self.entry = B0.entry_month(md, self.r1)
        self.idx1 = (1 + self.r1["r"].fillna(0.0)).cumprod()
        self.idx2 = (1 + self.r2["r"].fillna(0.0)).cumprod()
        ccy = FX_CCY.get(code)
        self.fx = (fx[ccy].reindex(self.days).ffill().bfill() if ccy else pd.Series(1.0, index=self.days))
        self.mult = self.m.tick_value / self.m.tick
        # Amendment 4 (A4.4): a market-month whose F1 or F2 has no settlement on the decision date is missing
        self.rolls["missing"] = [not (md.has_settle(a, t) and md.has_settle(b, t))
                                 for a, b, t in zip(self.rolls["F1"], self.rolls["F2"], self.rolls["decision"])]
        self.monthly = self.calendar_month_returns()

    def calendar_month_returns(self) -> pd.Series:
        """Calendar-month excess return of the F1 chained index (section 2.3), full months only."""
        me = self.idx1.groupby(self.idx1.index.to_period("M")).last()
        return me.pct_change().iloc[1:]

    def settle(self, c, d) -> float:
        return self.md.settle(c, d)

    # ---------------------------------------------------------------- volatility
    def sigma_blend(self) -> pd.Series:
        """T20/T21 (section 2.4): 0.5 EWMA (lambda 0.94, zero mean) + 0.5 one-year SD, daily, annualised sqrt(252)."""
        r = self.r1["r"].dropna()
        ew = np.sqrt((r ** 2).ewm(alpha=0.06, adjust=False).mean())
        sd = r.rolling(252, min_periods=252).std()
        n = pd.Series(np.arange(1, len(r) + 1), index=r.index)
        s = (0.5 * ew + 0.5 * sd) * np.sqrt(252)
        return s.where(n >= 252)

    def sigma_mop(self) -> pd.Series:
        """T22 (section 2.4): EWMA, centre of mass 60 trading days, on daily r_ex, annualised sqrt(252)."""
        r = self.r1["r"].dropna()
        n = pd.Series(np.arange(1, len(r) + 1), index=r.index)
        return (r.ewm(com=60, adjust=True).std() * np.sqrt(252)).where(n >= 252)


def asof(s: pd.Series, d) -> float:
    s = s.dropna()
    v = s.loc[:d]
    return float(v.iloc[-1]) if len(v) else np.nan


# ============================================================ signals
def ltd(mk: Mkt, c) -> pd.Timestamp:
    return mk.ct.at[c, "ltd"]


def carry_log(mk: Mkt, t, a, b) -> float:
    fa, fb = mk.settle(a, t), mk.settle(b, t)
    if not (np.isfinite(fa) and np.isfinite(fb)) or fa <= 0 or fb <= 0:
        return np.nan
    da, db = (ltd(mk, a) - t).days, (ltd(mk, b) - t).days
    return (np.log(fa) - np.log(fb)) * 365.0 / (db - da) if db > da else np.nan


def signal_t20(mk: Mkt, option: str) -> pd.Series:
    out = {}
    if option == "A":
        for m, row in mk.rolls.iterrows():
            out[m] = (carry_log(mk, row["decision"], row["F1"], row["F13"]) if isinstance(row["F13"], str)
                      else np.nan)
        return pd.Series(out)
    cl = pd.Series({m: carry_log(mk, row["decision"], row["F1"], row["F2"]) for m, row in mk.rolls.iterrows()})
    for m in cl.index:
        past = [cl.get(m - 12 * k, np.nan) for k in range(1, 6)]
        past = [x for x in past if np.isfinite(x)]
        out[m] = cl[m] - np.mean(past) if len(past) >= 3 and np.isfinite(cl[m]) else np.nan
    return pd.Series(out)


def signal_t21(mk: Mkt) -> pd.Series:
    """BM = 12-month compounded return of the first-nearby minus that of the second-nearby rolled series."""
    note("T21: the 12 holding months are measured between consecutive decision dates (the twelve months to t, "
         "settlements up to and including t), from the chained F1 and F2 indices")
    out = {}
    dec = mk.rolls["decision"]
    for m in mk.rolls.index:
        t, t0 = dec[m], dec.get(m - 12)
        if t0 is None or pd.isna(t0):
            out[m] = np.nan
            continue
        a1, b1 = asof(mk.idx1, t0), asof(mk.idx1, t)
        a2, b2 = asof(mk.idx2, t0), asof(mk.idx2, t)
        ok = t0 >= mk.idx2.index[0] and t0 >= mk.idx1.index[0]
        out[m] = (b1 / a1 - 1) - (b2 / a2 - 1) if ok else np.nan
    return pd.Series(out)


def signal_t22(mk: Mkt, sigma: pd.Series) -> pd.Series:
    """TREND = mean over k in {1,3,12} of sign(idx[t]/idx[t-k months]-1) * 0.40/sigma (the 1/S_t follows)."""
    out = {}
    for m, row in mk.rolls.iterrows():
        t = row["decision"]
        s = asof(sigma, t)
        if not np.isfinite(s) or s <= 0:
            out[m] = np.nan
            continue
        now = asof(mk.idx1, t)
        parts = []
        for k in (1, 3, 12):
            back = t - pd.DateOffset(months=k)
            if back < mk.idx1.index[0]:
                parts = None
                break
            parts.append(np.sign(now / asof(mk.idx1, back) - 1) * 0.40 / s)
        out[m] = np.mean(parts) if parts else np.nan
    return pd.Series(out)


# ============================================================ sleeve construction
def cap_risk(w: pd.Series, sig: pd.Series, cap: float = CAP_RISK, iters: int = 10) -> pd.Series:
    """No market above 10% of the sleeve's risk (|w| sigma share); excess redistributed proportionally over the
    others; iterated, at most 10 iterations (section 2.4)."""
    w = w.copy()
    for _ in range(iters):
        r = (w.abs() * sig)
        share = r / r.sum()
        over = share > cap + 1e-12
        if not over.any():
            break
        excess = (share[over] - cap).sum()
        under = ~over
        new = share.copy()
        new[over] = cap
        if share[under].sum() > 0:
            new[under] = share[under] + excess * share[under] / share[under].sum()
        w = np.sign(w) * new * r.sum() / sig
    return w


def scale_to_target(W: pd.DataFrame, R: pd.DataFrame, target: float = SLEEVE_VOL, lag_months: int = 1) -> pd.Series:
    """v1.0's pro-forma rule: trailing 36-month SD of the current weights on the markets' monthly excess returns,
    at least 12 months.  For a sleeve decided near the start of month m the last complete month is m-1."""
    L, mn = SY.DESIGN["vol_lookback_months"], SY.DESIGN["vol_min_months"]
    out = {}
    for m in W.index:
        hist = R.loc[: m - lag_months].iloc[-L:].reindex(columns=W.columns).fillna(0.0)
        pv = (hist @ W.loc[m]).std() * np.sqrt(12) if len(hist) >= mn else np.nan
        out[m] = target / pv if pv and pv > 0 else 0.0
    return pd.Series(out)


def build_targets(mks: dict[str, Mkt], sig: dict[str, pd.Series], sigma: dict[str, pd.Series], kind: str,
                  months: pd.PeriodIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Target weights (10% sleeve) and the sigma panel, per rebalance month."""
    W = pd.DataFrame(0.0, index=months, columns=list(mks))
    SG = pd.DataFrame(np.nan, index=months, columns=list(mks))
    for m in months:
        vals, sg = {}, {}
        for c, mk in mks.items():
            if m not in mk.rolls.index or mk.entry is None or m < mk.entry or mk.rolls.at[m, "missing"]:
                continue
            s = asof(sigma[c], mk.rolls.at[m, "decision"])
            v = sig[c].get(m, np.nan)
            if np.isfinite(s) and s > 0 and np.isfinite(v):
                vals[c], sg[c] = v, s
        SG.loc[m, list(sg)] = pd.Series(sg)
        if kind in ("T20", "T21"):
            if len(vals) < MIN_ACTIVE:
                continue
            v = pd.Series(vals)
            s = v.rank() - (len(v) + 1) / 2
            s = s / s.abs().sum() * 2
            w = s / pd.Series(sg)
        else:
            if not vals:
                continue
            w = pd.Series(vals) / len(vals)          # TREND / S_t (MOP equal weight)
        w = cap_risk(w, pd.Series(sg)[w.index])     # section 2.4 convention, applied to every sleeve
        W.loc[m, w.index] = w
    note("The 10% single-market risk cap of section 2.4 (a sleeve-construction convention) is applied to all "
         "three sleeves, measured with each sleeve's own sigma")
    return W, SG


class Sleeve:
    """A sleeve's held weights and daily gross P&L and costs (1x c_raw) at 10% target."""

    def __init__(self, name: str, mks: dict[str, Mkt], targets: pd.DataFrame, sigma: pd.DataFrame):
        self.name, self.mks = name, mks
        R = pd.DataFrame({c: mk.monthly for c, mk in mks.items()})
        self.R = R
        scale = scale_to_target(targets, R)
        self.targets = targets.mul(scale, axis=0)
        held, log = T18.apply_rules(self.targets, sigma.fillna(np.nan), {c: "sleeve" for c in targets.columns})
        self.held = held
        self.log = log
        self.daily_gross, self.daily_cost1, self.per_market_gross, self.trades = self._daily()

    def _daily(self):
        gross_parts, cost_parts, trade_rows = {}, {}, []
        for c, mk in self.mks.items():
            r = mk.rolls
            ex = list(r["execution"])
            months = list(r.index)
            g = pd.Series(0.0, index=mk.days)
            k = pd.Series(0.0, index=mk.days)
            prev_w, prev_c = 0.0, None
            for j, m in enumerate(months):
                w = float(self.held.at[m, c]) if m in self.held.index else 0.0
                a = ex[j]
                b = ex[j + 1] if j + 1 < len(ex) else mk.days[-1]
                cnew = r.at[m, "F1"]
                # cost at the execution settlement (2 legs on a roll); c_raw in fraction of notional
                if prev_c is not None and cnew != prev_c and prev_w != 0:
                    k[a] += abs(prev_w) * self.c_raw(mk, prev_c, a)
                    if w != 0:
                        k[a] += abs(w) * self.c_raw(mk, cnew, a)
                    kind = "roll"
                else:
                    if w != prev_w:
                        k[a] += abs(w - prev_w) * self.c_raw(mk, cnew, a)
                    kind = "trade"
                if w != prev_w or (prev_c is not None and cnew != prev_c and prev_w != 0):
                    trade_rows.append({"market": c, "month": str(m), "date": a, "kind": kind, "w_old": prev_w,
                                       "w_new": w, "contract_old": prev_c, "contract_new": cnew})
                if w != 0:
                    px = mk.md.close[cnew].reindex(mk.days).ffill()
                    fx = mk.fx
                    ref = px.get(a)
                    seg = (mk.days > a) & (mk.days <= b)
                    if np.isfinite(ref) and ref != 0:
                        dP = px.diff() * fx                    # contracts x mult x (F_d - F_d-1) x fx_d
                        g[seg] += w * dP[seg] / (ref * fx.get(a))
                prev_w, prev_c = w, cnew
            gross_parts[c], cost_parts[c] = g, k
        G = pd.DataFrame(gross_parts).fillna(0.0)
        K = pd.DataFrame(cost_parts).fillna(0.0)
        return G.sum(axis=1), K.sum(axis=1), G, pd.DataFrame(trade_rows)

    @staticmethod
    def c_raw(mk: Mkt, contract, d) -> float:
        """(US$3 + slippage ticks x tick value) / notional, at the trade's settlement (section 2.5)."""
        F = mk.md.close[contract].reindex(mk.days).ffill().get(d)
        fx = mk.fx.get(d)
        if not np.isfinite(F) or F == 0:
            return 0.0
        tick_usd = mk.m.slip_ticks * mk.m.tick_value * fx
        return (COMMISSION + tick_usd) / abs(F * mk.mult * fx)

    def monthly(self, cost_mult: float) -> pd.Series:
        d = self.daily_gross - cost_mult * self.daily_cost1
        return (1 + d).groupby(d.index.to_period("M")).prod() - 1

    def monthly_cost(self, cost_mult: float = 1.0) -> pd.Series:
        return self.monthly(0.0) - self.monthly(cost_mult)

    def notional_cost_rate(self, m) -> pd.Series:
        """c_raw per market at month m's execution (for scale-change trades in the combined book)."""
        out = {}
        for c, mk in self.mks.items():
            if m in mk.rolls.index:
                out[c] = self.c_raw(mk, mk.rolls.at[m, "F1"], mk.rolls.at[m, "execution"])
        return pd.Series(out)


# ============================================================ combination with v1.1 (section 2.6)
def combine(inp: dict, v11: pd.DataFrame, sl: Sleeve, cost_mult_v11: float, cost_mult_sleeve: float) -> pd.DataFrame:
    """Monthly combined book: W_mix = 0.75 W_v11 + 0.25 W_s, s_t = 10% / pro-forma vol(W_mix) (36 months of the
    mix's instruments, min 12), then the 6x gross cap on the whole book.  v1.1 legs through v1.1's accounting
    (lags, cost model); the sleeve leg earns kappa_t x the sleeve's net return in month t+1, and changes of kappa
    are charged at the sleeve's cost rates."""
    note("Combination timing: the scale s_t and the gross cap are set at month-end t from v1.1's held weights and "
         "the sleeve's weights held after its rebalance in month t; the sleeve leg earns kappa_t = 0.25 s_t (capped) "
         "times the sleeve's net return in month t+1 (positions decided at month-end earn next month, as v1.1's FX "
         "legs); a change of kappa is a trade of |dkappa| x the sleeve's held notional, charged at its cost rates")
    Wv = v11.attrs["weights"]
    months = Wv.index
    Ws = sl.held.reindex(months).fillna(0.0)
    Rv = TS.all_returns(inp)
    Rs = sl.R.reindex(months)
    Rmix = pd.concat([Rv, Rs], axis=1)
    L, mn = SY.DESIGN["vol_lookback_months"], SY.DESIGN["vol_min_months"]
    scale, kappa = pd.Series(0.0, index=months), pd.Series(0.0, index=months)
    Vleg = Wv * 0.0
    for t in months:
        mix = pd.concat([BUDGET_V11 * Wv.loc[t], BUDGET * Ws.loc[t]])
        hist = Rmix.loc[:t].iloc[-L:].reindex(columns=mix.index).fillna(0.0)
        pv = (hist @ mix).std() * np.sqrt(12) if len(hist) >= mn else np.nan
        s = 0.10 / pv if pv and pv > 0 else 0.0
        gross = s * mix.abs().sum()
        g = min(1.0, SY.DESIGN["gross_leverage_cap"] / gross) if gross > 0 else 0.0
        scale[t] = s * g
        Vleg.loc[t] = BUDGET_V11 * s * g * Wv.loc[t]
        kappa[t] = BUDGET * s * g
    inp_c = TS.with_costs(inp, cost_mult_v11) if cost_mult_v11 != 1.0 else inp
    vres = T18.pnl(inp_c, Vleg)
    sm = sl.monthly(cost_mult_sleeve).reindex(months).fillna(0.0)
    sleeve_leg = kappa.shift(1).fillna(0.0) * sm
    # scale-change cost: |kappa_t - kappa_{t-1}| x sum_i |h_i,t| c_i, charged in month t+1
    sc = pd.Series(0.0, index=months)
    for i, t in enumerate(months[1:], 1):
        dk = abs(kappa[t] - kappa[months[i - 1]])
        if dk > 0:
            rates = sl.notional_cost_rate(t).reindex(Ws.columns).fillna(0.0)
            sc[t] = dk * float((Ws.loc[t].abs() * rates).sum()) * cost_mult_sleeve
    sc = sc.shift(1).fillna(0.0)
    out = pd.DataFrame(index=vres.index)
    out["v11_leg_net"] = vres["net"]
    out["sleeve_leg_net"] = (sleeve_leg - sc).reindex(out.index).fillna(0.0)
    out["net"] = out["v11_leg_net"] + out["sleeve_leg_net"]
    out["scale"] = scale.reindex(out.index)
    out["kappa"] = kappa.reindex(out.index)
    out["gross_leverage"] = (Vleg.abs().sum(axis=1) + kappa * Ws.abs().sum(axis=1)).shift(1).reindex(out.index)
    # one-way notional traded per month: v1.1 legs, the sleeve leg's own trades and kappa changes
    dsl = Ws.diff().abs().sum(axis=1)
    out["turnover"] = (Vleg.diff().abs().sum(axis=1) + kappa.shift(1).fillna(0.0) * dsl
                       + kappa.diff().abs().fillna(0.0) * Ws.abs().sum(axis=1)).reindex(out.index)
    out.attrs = {"scale_all": scale, "kappa_all": kappa}
    return out


BUDGET_V11 = 1 - BUDGET


# ============================================================ statistics
def sr(r) -> float:
    return T01.sharpe(r)


def nw_tstat(x: pd.Series, lags: int = 6) -> tuple[float, float]:
    """Mean and Newey-West (Bartlett, `lags`) t-statistic of the mean."""
    x = np.asarray(pd.Series(x).dropna(), float)
    T = len(x)
    u = x - x.mean()
    s = (u @ u) / T
    for l in range(1, lags + 1):
        s += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / T
    se = np.sqrt(s / T)
    return float(x.mean()), float(x.mean() / se) if se > 0 else np.nan


def nw_regression(y: pd.Series, x: pd.Series, lags: int = 6) -> dict:
    import statsmodels.api as sm
    d = pd.concat([y, x], axis=1).dropna()
    res = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"months": len(d), "alpha_monthly": float(res.params.iloc[0]), "alpha_ann": float(res.params.iloc[0] * 12),
            "alpha_t": float(res.tvalues.iloc[0]), "beta": float(res.params.iloc[1]), "beta_t": float(res.tvalues.iloc[1])}


def bootstrap(a: pd.Series, b: pd.Series, B: int = 10_000, L: int = 6, seed: int = SEED) -> dict:
    """Paired circular block bootstrap of SR(a) - SR(b): non-inferiority p (Amendment 1, margin 0.05) and the
    superiority p (context)."""
    x = np.column_stack([np.asarray(a, float), np.asarray(b, float)])
    T = len(x)
    d_hat = sr(x[:, 0]) - sr(x[:, 1])
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for i in range(B):
        s = x[T01.circular_block_indices(T, L, rng)]
        d[i] = sr(s[:, 0]) - sr(s[:, 1])
    return {"delta_sr": d_hat, "p_noninf": float((1 + np.sum(d - d_hat >= d_hat + NONINF_MARGIN)) / (B + 1)),
            "p_superiority": float((1 + np.sum(d - d_hat >= d_hat)) / (B + 1)),
            "boot_mean": float(d.mean()), "boot_sd": float(d.std(ddof=1)), "boot_q05": float(np.quantile(d, 0.05)),
            "boot_q95": float(np.quantile(d, 0.95)), "B": B, "block": L, "seed": seed, "months": T}


def holm(p: dict[str, float]) -> dict[str, float]:
    keys = sorted(p, key=p.get)
    m = len(keys)
    out, run = {}, 0.0
    for j, k in enumerate(keys):
        run = max(run, min(1.0, (m - j) * p[k]))
        out[k] = run
    return out


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 2:
        return {"months": len(r)}
    w = (1 + r).cumprod()
    yrs = len(r) / 12
    return {"start": str(r.index[0]), "end": str(r.index[-1]), "months": len(r),
            "ann_return_%": 100 * (w.iloc[-1] ** (1 / yrs) - 1), "ann_vol_%": 100 * r.std() * np.sqrt(12),
            "sharpe": sr(r), "max_drawdown_%": 100 * T01.max_drawdown(r), "ES97.5_monthly_%": 100 * T01.expected_shortfall(r)}


def win(s: pd.Series, w) -> pd.Series:
    return s.loc[w[0]:w[1]]


# ============================================================ Clark-West (T20 S2, section 2.8)
def clark_west(mks: dict[str, Mkt], sig: dict[str, pd.Series]) -> dict:
    note("Clark-West: target = the market's F1 holding-period excess return from this execution to the next; the "
         "prevailing mean and the pooled slope use pairs with s < t as pre-registered (holding periods of earlier "
         "rebalance months, first forecast at the 2010-01 decision); beta_t = OLS slope of r on z with an "
         "intercept; z = cross-sectional ranks standardised to mean 0, SD 1, winsorised at +-2")
    hold = {}
    for c, mk in mks.items():
        ex = mk.rolls["execution"]
        idx = mk.idx1
        h = {}
        ms = list(ex.index)
        for j, m in enumerate(ms[:-1]):
            h[m] = asof(idx, ex[ms[j + 1]]) / asof(idx, ex[m]) - 1
        hold[c] = pd.Series(h)
    H = pd.DataFrame(hold)
    S = pd.DataFrame(sig).reindex(H.index)
    Z = S.rank(axis=1)
    Z = Z.sub(Z.mean(axis=1), axis=0).div(Z.std(axis=1, ddof=0), axis=0).clip(-2, 2)
    months = [m for m in H.index if m >= FULL[0]]
    fbar = {}
    for m in months:
        if m < CW_WINDOW[0] or m > CW_WINDOW[1]:
            continue
        past = [p for p in H.index if FULL[0] <= p <= m - 1]
        if len(past) < 120:
            continue
        zz = Z.loc[past].stack()
        rr = H.loc[past].stack()
        d = pd.concat([rr, zz], axis=1, keys=["r", "z"]).dropna()
        if len(d) < 30:
            continue
        beta = np.cov(d["r"], d["z"], ddof=1)[0, 1] / np.var(d["z"], ddof=1)
        f = []
        for c in H.columns:
            r = H.at[m, c] if m in H.index else np.nan
            z = Z.at[m, c] if m in Z.index else np.nan
            prev = H.loc[[p for p in H.index if p <= m - 1], c].dropna()
            if not (np.isfinite(r) and np.isfinite(z)) or len(prev) == 0:
                continue
            rbar = prev.mean()
            rhat = rbar + beta * z
            f.append((r - rbar) ** 2 - ((r - rhat) ** 2 - (rbar - rhat) ** 2))
        if f:
            fbar[m] = np.mean(f)
    fb = pd.Series(fbar)
    from scipy.stats import norm
    out = {}
    for name, w in {"2010-01..2026-09": CW_WINDOW, "2020-01..2026-09": TEST}.items():
        x = fb.loc[w[0]:w[1]]
        mean, t = nw_tstat(x, 6)
        out[name] = {"months": int(len(x)), "mean_f": mean, "cw_t": t, "p_one_sided": float(1 - norm.cdf(t))}
    return out


# ============================================================ run
def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def reproduce(inp: dict) -> dict:
    """v1.0 and v1.1 reproduction (section 2.6), without writing any v1.0/v1.1 file."""
    from . import verify_v1 as V
    ok_v1 = all(r["identical"] for r in V.compare({
        V.DESIGN_TABLE: SY.evaluate(inp, slice(None, SY.FIT_END)),
        V.TEST_TABLE: SY.evaluate(inp, slice(*V11.TEST))}).values())
    checks = V11.reproduce_t18(inp)
    ok_v11 = all(c["identical"] for c in checks.values())
    return {"v1.0_identical": ok_v1, "v1.1_reproduces_T18": ok_v11,
            "checks": {k: {a: b for a, b in c.items() if a != "values"} for k, c in checks.items()}}


def stage_run():
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    priv = CD.data_root() / "norgate" / "derived" / "trials"
    priv.mkdir(parents=True, exist_ok=True)
    V11.check_frozen()
    with tempfile.TemporaryDirectory() as tmp:
        inp = V11.frozen_inputs(Path(tmp))
    rep = reproduce(inp)
    print("reproduction:", rep["v1.0_identical"], rep["v1.1_reproduces_T18"])
    if not (rep["v1.0_identical"] and rep["v1.1_reproduces_T18"]):
        (OUT / "RUN.json").write_text(json.dumps({"stopped": "reproduction check failed", **rep}, indent=1, default=str))
        sys.exit("reproduction check failed: nothing is run (section 2.6)")

    drop = build0_dropped()
    fx = fx_daily()
    b0 = json.loads((OUT / "build0.json").read_text())
    option = {c: b0["markets"][c]["A7"]["option"] for c in XS}
    t22_univ = [c for c in CD.COMMODITIES + CD.FINANCIALS if c not in drop]
    mks = {c: Mkt(c, fx) for c in sorted(set(XS) | set(t22_univ), key=list(CD.MARKETS).index)}
    months = pd.period_range(pd.Period("1991-01", "M"), FULL[1], freq="M")

    sig, sgm = {"T20": {}, "T21": {}, "T22": {}}, {"blend": {}, "mop": {}}
    for c, mk in mks.items():
        sgm["blend"][c], sgm["mop"][c] = mk.sigma_blend(), mk.sigma_mop()
        if c in XS:
            sig["T20"][c] = signal_t20(mk, option[c])
            sig["T21"][c] = signal_t21(mk)
        if c in t22_univ:
            sig["T22"][c] = signal_t22(mk, sgm["mop"][c])

    universes = {"T20": {"full": XS, "half B": XS_HALF["B"], "half A": XS_HALF["A"]},
                 "T21": {"full": XS, "half B": XS_HALF["B"], "half A": XS_HALF["A"]},
                 "T22": {"full": t22_univ, "half B": [c for c in T22_HALF["B"] if c in t22_univ],
                         "half A": [c for c in T22_HALF["A"] if c in t22_univ]}}
    sleeves = {}
    for trial, unis in universes.items():
        sk = "mop" if trial == "T22" else "blend"
        for uni, codes in unis.items():
            sub = {c: mks[c] for c in codes}
            W, SG = build_targets(sub, {c: sig[trial][c] for c in codes}, {c: sgm[sk][c] for c in codes}, trial, months)
            sleeves[(trial, uni)] = Sleeve(f"{trial} {uni}", sub, W, SG)
            print("sleeve", trial, uni, flush=True)

    v11 = {1.0: V11.run(TS.with_costs(inp, 1.0))[0], 2.0: V11.run(TS.with_costs(inp, 2.0))[0]}
    carry = SY.run(inp, ["carry"])
    comb = {}
    for (trial, uni), sl in sleeves.items():
        for cm, (cv, cs) in {"decisive": (1.0, 2.0), "2x": (2.0, 4.0)}.items():
            comb[(trial, uni, cm)] = combine(inp, v11[cv], sl, cv, cs)

    # ---------------- monthly series (aggregate: sleeves and books; written to results/)
    mon = {}
    for cm, cv in (("decisive", 1.0), ("2x", 2.0)):
        mon[f"v1.1|{cm}"] = T01._net(v11[cv])
    for (trial, uni), sl in sleeves.items():
        mon[f"{trial} sleeve|{uni}|decisive"] = sl.monthly(2.0)
        mon[f"{trial} sleeve|{uni}|2x"] = sl.monthly(4.0)
        mon[f"{trial} sleeve|{uni}|gross"] = sl.monthly(0.0)
        mon[f"{trial} sleeve|{uni}|cost1x"] = sl.monthly_cost(1.0)
    for (trial, uni, cm), cb in comb.items():
        mon[f"v1.1+{trial}|{uni}|{cm}"] = cb["net"]
    mon["v1.0 carry sleeve"] = T01._net(carry)
    mon["S&P 500"] = inp["spx"]
    M = pd.DataFrame(mon)
    M.index = M.index.astype(str)
    M.index.name = "month"
    M.to_csv(OUT / "monthly_net.csv", float_format="%.6f")

    # ---------------- criteria
    crit = {}
    v_dec = win(T01._net(v11[1.0]), TEST)
    praw, praw2 = {}, {}
    for trial in ("T20", "T21", "T22"):
        c = win(comb[(trial, "full", "decisive")]["net"], TEST)
        assert len(c) == len(v_dec) == 81 and (c.index == v_dec.index).all()
        bs = bootstrap(c, v_dec)
        c2 = win(comb[(trial, "full", "2x")]["net"], TEST)
        v2 = win(T01._net(v11[2.0]), TEST)
        bs2 = bootstrap(c2, v2)
        praw[trial], praw2[trial] = bs["p_noninf"], bs2["p_noninf"]
        crit[trial] = {"bootstrap": bs, "bootstrap_2x": bs2}
    padj, padj2 = holm(praw), holm(praw2)

    def dsr(r, N):
        return T01.dsr_row(r, N)

    vB = v_dec
    d_v = dsr(v_dec, N_V11)
    for trial in ("T20", "T21", "T22"):
        c = win(comb[(trial, "full", "decisive")]["net"], TEST)
        cB = win(comb[(trial, "half B", "decisive")]["net"], TEST)
        bs = crit[trial]["bootstrap"]
        d_c = dsr(c, N_TRIAL)
        dd_v, dd_c, es_v, es_c = T01.max_drawdown(v_dec), T01.max_drawdown(c), T01.expected_shortfall(v_dec), \
            T01.expected_shortfall(c)
        C = [
            {"#": "C1", "criterion": f"non-inferiority dSR >= -0.05 and Holm p < {C1_ALPHA[trial]:.2f}",
             "value": f"dSR {bs['delta_sr']:+.4f}; p raw {praw[trial]:.4f}, Holm {padj[trial]:.4f}",
             "pass": bool(bs["delta_sr"] >= -NONINF_MARGIN and padj[trial] < C1_ALPHA[trial])},
            {"#": "C2", "criterion": "half B: dSR >= -0.05 and |MaxDD| <= v1.1's",
             "value": f"dSR {sr(cB) - sr(vB):+.4f}; MaxDD {100 * T01.max_drawdown(cB):.2f}% vs {100 * dd_v:.2f}%",
             "pass": bool(sr(cB) - sr(vB) >= -NONINF_MARGIN and abs(T01.max_drawdown(cB)) <= abs(dd_v))},
            {"#": "C3", "criterion": "|MaxDD| and ES97.5 <= 1.10 x v1.1's",
             "value": f"MaxDD {100 * dd_c:.2f}% vs {100 * dd_v:.2f}%; ES {100 * es_c:.2f}% vs {100 * es_v:.2f}%",
             "pass": bool(abs(dd_c) <= 1.10 * abs(dd_v) and es_c <= 1.10 * es_v)},
            {"#": "C4", "criterion": "DSR(N=16) >= DSR(v1.1, N=13), noise-only null",
             "value": f"{d_c['DSR_noise']:.4f} vs {d_v['DSR_noise']:.4f}",
             "pass": bool(d_c["DSR_noise"] >= d_v["DSR_noise"])},
        ]
        crit[trial].update({"combined": C, "dsr": {"trial": d_c, "v1.1": d_v}, "p_holm": padj[trial],
                            "p_holm_2x": padj2[trial]})

    # sleeve-level gates
    s20 = sleeves[("T20", "full")]
    s21 = sleeves[("T21", "full")]
    s22 = sleeves[("T22", "full")]

    def breakeven(sl):
        g = win(sl.monthly(0.0), FULL)
        k = win(sl.monthly_cost(1.0), FULL)
        return float(g.mean() * 12 / (k.mean() * 12)) if k.mean() > 0 else np.nan

    net20, net21, net22 = s20.monthly(2.0), s21.monthly(2.0), s22.monthly(2.0)
    cw = clark_west({c: mks[c] for c in XS}, {c: sig["T20"][c] for c in XS})
    m21, t21 = nw_tstat(win(net21, FULL))
    alpha = nw_regression(win(net21, FULL), win(net20, FULL))
    cs = win(T01._net(carry), TEST)
    worst = cs.nsmallest(int(round(0.10 * len(cs)))).index
    corr_crisis = float(net22.reindex(worst).corr(cs.loc[worst]))
    be = {t: breakeven(s) for t, s in (("T20", s20), ("T21", s21), ("T22", s22))}
    crit["T20"]["sleeve"] = [
        {"#": "S1", "criterion": "net SR > 0.20 in 2000-01..2019-12 and 2020-01..2026-09",
         "value": f"{sr(win(net20, DESIGN)):.4f} / {sr(win(net20, TEST)):.4f}",
         "pass": bool(sr(win(net20, DESIGN)) > 0.20 and sr(win(net20, TEST)) > 0.20)},
        {"#": "S2", "criterion": "Clark-West one-sided p < 0.05, 2010-01..2026-09",
         "value": f"t {cw['2010-01..2026-09']['cw_t']:.3f}, p {cw['2010-01..2026-09']['p_one_sided']:.4f}",
         "pass": bool(cw["2010-01..2026-09"]["p_one_sided"] < 0.05)},
        {"#": "S3", "criterion": "break-even cost multiple >= 2", "value": f"{be['T20']:.2f}", "pass": bool(be["T20"] >= 2)}]
    crit["T21"]["sleeve"] = [
        {"#": "S1", "criterion": "NW (6) t of mean net return > 2, 2000-01..2026-09", "value": f"t {t21:.3f}",
         "pass": bool(t21 > 2)},
        {"#": "S2", "criterion": "alpha vs T20 sleeve > 0 and NW t > 1.5",
         "value": f"alpha {100 * alpha['alpha_ann']:.2f}%/yr, t {alpha['alpha_t']:.3f}",
         "pass": bool(alpha["alpha_ann"] > 0 and alpha["alpha_t"] > 1.5)},
        {"#": "S3", "criterion": "break-even cost multiple >= 2", "value": f"{be['T21']:.2f}", "pass": bool(be["T21"] >= 2)}]
    crit["T22"]["sleeve"] = [
        {"#": "S1", "criterion": "net SR > 0.20 in 2000-01..2019-12 and 2020-01..2026-09",
         "value": f"{sr(win(net22, DESIGN)):.4f} / {sr(win(net22, TEST)):.4f}",
         "pass": bool(sr(win(net22, DESIGN)) > 0.20 and sr(win(net22, TEST)) > 0.20)},
        {"#": "S2", "criterion": "corr(T22 sleeve, v1.0 carry sleeve) < 0 in carry's worst 8 months, 2020-01..2026-09",
         "value": f"{corr_crisis:+.4f} ({' '.join(str(m) for m in sorted(worst))})", "pass": bool(corr_crisis < 0)},
        {"#": "S3", "criterion": "break-even cost multiple >= 2", "value": f"{be['T22']:.2f}", "pass": bool(be["T22"] >= 2)}]
    for trial in ("T20", "T21", "T22"):
        allc = crit[trial]["combined"] + crit[trial]["sleeve"]
        crit[trial]["overall_pass"] = all(x["pass"] for x in allc)
    crit["_extra"] = {"clark_west": cw, "t21_alpha_vs_t20": alpha, "t21_nw": {"mean": m21, "t": t21},
                      "breakeven": be, "carry_worst_months": [str(m) for m in sorted(worst)],
                      "holm_noninf": padj, "holm_noninf_2x": padj2, "praw_noninf": praw, "option": option,
                      "dropped": sorted(drop), "t22_universe": t22_univ}
    (OUT / "criteria.json").write_text(json.dumps(crit, indent=1, default=float))

    # ---------------- performance tables (aggregate)
    rows = []
    periods = {"2020-01..2026-09": TEST, "2000-01..2019-12": DESIGN, "2000-01..2026-09": FULL}
    for k in M.columns:
        if k.endswith("|gross") or k.endswith("|cost1x"):
            continue
        s = M[k].copy()
        s.index = pd.PeriodIndex(s.index, freq="M")
        for pn, pw in periods.items():
            x = win(s, pw).dropna()
            if len(x) >= 12:
                rows.append({"series": k, "period": pn, **stats(x)})
    turn = {f"v1.1|{cm}": V11.turnover(v11[cv]) for cm, cv in (("decisive", 1.0), ("2x", 2.0))}
    turn.update({f"v1.1+{t}|{u}|{cm}": cb["turnover"] for (t, u, cm), cb in comb.items()})
    turn.update({f"{t} sleeve|{u}|{cm}": sl.held.diff().abs().sum(axis=1) for (t, u), sl in sleeves.items()
                 for cm in ("decisive", "2x")})
    for row in rows:
        tv = turn.get(row["series"])
        pw = periods[row["period"]]
        row["turnover_x_pa"] = float(win(tv, pw).mean() * 12) if tv is not None else np.nan
    pd.DataFrame(rows).to_csv(OUT / "performance.csv", index=False, float_format="%.4f")

    # ---------------- private per-market outputs
    for (trial, uni), sl in sleeves.items():
        tag = f"{trial}_{uni.replace(' ', '')}"
        sl.held.to_csv(priv / f"held_{tag}.csv")
        sl.per_market_gross.to_csv(priv / f"daily_gross_by_market_{tag}.csv")
        sl.trades.to_csv(priv / f"trades_{tag}.csv", index=False)
    for trial in sig:
        pd.DataFrame(sig[trial]).to_csv(priv / f"signals_{trial}.csv")

    diag = diagnostics(inp, v11, carry, sleeves, comb, sig, mks, option)
    (OUT / "diagnostics.json").write_text(json.dumps(diag, indent=1, default=float))

    files = ["em_macro/t2022.py", "em_macro/t2022_report.py", "em_macro/commod_data.py", "em_macro/commod_build0.py",
             "em_macro/systematic.py", "em_macro/systematic_v11.py", "em_macro/t18_rebal.py",
             "docs/prereg/T20-T22_commodity_trials.md", "results/T20-T22/build0.md", "results/T20-T22/build0.json"]
    (OUT / "RUN.json").write_text(json.dumps({
        "run_started_utc": started, "run_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_run": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                          text=True).stdout.strip(),
        "pandas": pd.__version__, "numpy": np.__version__, "reproduction": rep,
        "inputs": {"norgate": [CD.SNAPSHOT, CD.FIN_SNAPSHOT, CD.META_SNAPSHOT],
                   "v1.1": "v1.0 data/processed snapshots at 7886867 and data/kept/T16-T19 raw cache",
                   "fx": "FRED DEXUSEU, DEXUSUK"},
        "decisions": DECISIONS,
        "sha256": {f: _sha(f) for f in files if (ROOT / f).exists()}}, indent=1, default=str))
    for trial in ("T20", "T21", "T22"):
        print(trial, "OVERALL", "PASS" if crit[trial]["overall_pass"] else "FAIL")


def diagnostics(inp, v11, carry, sleeves, comb, sig, mks, option) -> dict:
    out = {}
    v = T01._net(v11[1.0])
    s = {t: sleeves[(t, "full")].monthly(2.0) for t in ("T20", "T21", "T22")}
    frame = pd.DataFrame({"T20": s["T20"], "T21": s["T21"], "T22": s["T22"], "v1.1": v,
                          "v1.0 carry": T01._net(carry), "S&P 500": inp["spx"]})
    out["corr_2020_2026"] = win(frame, TEST).corr().round(4).to_dict()
    out["corr_2000_2019"] = win(frame, DESIGN).corr().round(4).to_dict()
    worst = win(v, TEST).nsmallest(5).index
    out["v11_worst5"] = {str(m): {"v1.1_%": 100 * v[m], **{f"{t}_sleeve_%": 100 * s[t].get(m, np.nan)
                                                            for t in s}} for m in sorted(worst)}
    out["option_A_share"] = float(np.mean([o == "A" for o in option.values()]))
    # cross-sectional correlation of the BM and carry signals, averaged over months
    S20, S21 = pd.DataFrame(sig["T20"]), pd.DataFrame(sig["T21"])
    cc = [S20.loc[m].corr(S21.loc[m], method="spearman") for m in S20.index.intersection(S21.index)
          if FULL[0] <= m <= FULL[1] and S20.loc[m].notna().sum() >= 6 and S21.loc[m].notna().sum() >= 6]
    out["bm_carry_signal_rank_corr_mean"] = float(np.nanmean(cc))
    out["t20_t21_sleeve_corr_2000_2026"] = float(win(s["T20"], FULL).corr(win(s["T21"], FULL)))
    by_year = {}
    for k, ser in {"v1.1": v, **{f"v1.1+{t}": comb[(t, "full", "decisive")]["net"] for t in s},
                   **{f"{t} sleeve": s[t] for t in s}}.items():
        x = win(ser, TEST)
        by_year[k] = {str(y): 100 * ((1 + g).prod() - 1) for y, g in x.groupby(x.index.year)}
    out["by_year_%"] = by_year
    turn = {}
    for t in s:
        h = sleeves[(t, "full")].held
        turn[t] = {str(y): float(g.diff().abs().sum(axis=1).sum()) for y, g in win(h, FULL).groupby(win(h, FULL).index.year)}
    out["sleeve_turnover_by_year_x"] = turn
    # T22: P&L by asset class (stand-alone sleeve, gross, 2000-01..2026-09)
    g22 = sleeves[("T22", "full")].per_market_gross
    cls = {c: ("commodities" if CD.MARKETS[c].kind == "commodity" else
               "currencies" if CD.MARKETS[c].sector == "currencies" else "bonds") for c in g22.columns}
    by_cls = g22.T.groupby(cls).sum().T
    by_cls = (1 + by_cls).groupby(by_cls.index.to_period("M")).prod() - 1
    out["t22_gross_by_asset_class_ann_%"] = {k: 100 * float(win(by_cls[k], FULL).mean() * 12) for k in by_cls}
    h22 = sleeves[("T22", "full")].held
    fxc = [c for c in h22.columns if CD.MARKETS[c].sector == "currencies"]
    bdc = [c for c in h22.columns if CD.MARKETS[c].sector == "bonds"]
    out["t22_net_fx_notional_mean"] = float(win(h22[fxc].sum(axis=1), TEST).mean()) if fxc else None
    out["t22_net_bond_notional_mean"] = float(win(h22[bdc].sum(axis=1), TEST).mean()) if bdc else None
    # sector exposure (mean net weight) of T20 and T21, 2020-01..2026-09
    for t in ("T20", "T21"):
        h = win(sleeves[(t, "full")].held, TEST)
        sec = {c: CD.MARKETS[c].sector for c in h.columns}
        out[f"{t}_mean_net_weight_by_sector"] = h.T.groupby(sec).sum().T.mean().round(4).to_dict()
    # rounding diagnostic at US$10m: combined sleeve leg in integer contracts
    rnd = {}
    for t in s:
        sl = sleeves[(t, "full")]
        kap = comb[(t, "full", "decisive")]["kappa"]
        errs, drops = [], 0
        for m in win(sl.held, TEST).index:
            for c, mk in sl.mks.items():
                w = sl.held.at[m, c] * kap.get(m, np.nan)
                if not np.isfinite(w) or w == 0 or m not in mk.rolls.index:
                    continue
                a = mk.rolls.at[m, "execution"]
                F = mk.md.close[mk.rolls.at[m, "F1"]].reindex(mk.days).ffill().get(a)
                n = w * CAPITAL_PAPER / (F * mk.mult * mk.fx.get(a))
                e = abs(round(n) - n) / abs(n)
                errs.append(e)
                drops += e > 0.5
        rnd[t] = {"positions": len(errs), "median_rounding_error_share": float(np.median(errs)) if errs else None,
                  "position_months_over_50pct": int(drops)}
    out["rounding_10m"] = rnd
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        stage_run()
    elif cmd == "report":
        from . import t2022_report
        t2022_report.write()
    else:
        sys.exit(__doc__)
