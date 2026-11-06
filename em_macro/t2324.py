"""Trials T23-T24: T21 (basis-momentum) and T22 (diversified futures trend) on 1979-1999, rules unchanged.

    EM_MACRO_DATA=... AQR_DATA=... python -m em_macro.t2324 run      # -> results/T23-T24/*, private derived/T23-T24/
    python -m em_macro.t2324 report                                  # -> results/T23-T24_pre2000.md

Pre-registration: docs/prereg/T23-T24_pre2000_backtest.md (215b3c4) with Amendments 1 (648534b) and 2 (a6fe7d8).  The rules are
T21's and T22's as run at a160bfd: every market, signal, sleeve and statistic function used here is imported from
em_macro/t2022.py (and commod_data / commod_build0) unchanged.  This module adds only (i) the window (t2324_window:
schedule and contract loading start earlier; the sleeves' rebalance months are each trial's window), (ii) the
run-time data checks D0-D3 of section 6, (iii) the gates of section 4 and Amendment 1, and (iv) the reporting.

Licence: per-market series (held weights, signals, trades, daily gross by market, A3/A9 series) go only to the
private data repo (norgate/derived/T23-T24/); this repository receives aggregate sleeve returns and statistics.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import commod_build0 as B0
from . import commod_data as CD
from . import t2022 as T
from . import t2324_avail as AV
from . import t2324_window as WIN
from .config import RESULTS, ROOT

OUT = RESULTS / "T23-T24"
REPORT = RESULTS / "T23-T24_pre2000.md"
W23 = (pd.Period("1979-05", "M"), pd.Period("1999-12", "M"))
W24 = (pd.Period("1979-05", "M"), pd.Period("1999-12", "M"))   # Amendment 2 (was 1979-04)
SUB_A_END = pd.Period("1991-01", "M")          # sub-window (a): never computed by any earlier run
SUB_B = (pd.Period("1991-02", "M"), pd.Period("1999-12", "M"))
S1_P = 0.02275                                 # 1 - Phi(2): T21's "t > 2"
MIN_ACTIVE = 6
A3_MIN = 0.90
PRE_PREG = "215b3c4"
AMEND_1 = "648534b"
AMEND_2 = "a6fe7d8"
CODE_A160 = {   # SHA-256 at a160bfd (pre-registration header): D0
    "em_macro/t2022.py": "d54cdc750668baa26eb408bfb394ec25e0467fd6e7b77ea919583f8a3345528a",
    "em_macro/commod_data.py": "e5ffe76b98d959d268f46e38b97eb2bfe78aa2f114922efb43b9bbbb8f49cb25",
    "em_macro/commod_build0.py": "2c58f7e2bde920e76605d973a2cf6763fdf49b670c7724a33265affaf5e1951c",
    "em_macro/t18_rebal.py": "dda6456d676281b48080d3c0a6c304d51c928cea39e0f70c696a364a10f96c43",
    "em_macro/systematic.py": "1eb4cf6b1c537c1711e5fff0b7aa044fee932c20992eb0d3cea4c3c5fc50be66",
    "em_macro/t01.py": "bc52b3e01869efd0bf8c18bc891bcd17df376e96bbc8e68e40fe2f8412432b2b",
}
AQR_URLS = {B0.AQR_CFLR: "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/" + B0.AQR_CFLR,
            B0.AQR_COFP: "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/" + B0.AQR_COFP}
HE_LEAN_FIRST = (1997, 2)    # live hogs -> lean hogs: first lean-hog contract (Feb 1997), for the straddle count

READINGS: list[str] = []


def reading(s: str) -> None:
    if s not in READINGS:
        READINGS.append(s)


class Stop(Exception):
    """A pre-registered stop: reported, nothing further is computed."""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def win(s: pd.Series, w) -> pd.Series:
    return s.loc[w[0]:w[1]]


# ============================================================ gates (section 4 and Amendment 1)
def p_one_sided(t: float) -> float:
    from scipy.stats import norm
    return float(1 - norm.cdf(t)) if np.isfinite(t) else np.nan


def breakeven(gross: pd.Series, cost1: pd.Series) -> float:
    """t2022's break-even: annualised mean gross / annualised cost drag at 1 x c_raw."""
    return float(gross.mean() * 12 / (cost1.mean() * 12)) if cost1.mean() > 0 else np.nan


def first_held_month(held: pd.DataFrame, w) -> pd.Period | None:
    h = win(held, w)
    nz = h.index[(h.abs().sum(axis=1) > 0).to_numpy()]
    return nz[0] if len(nz) else None


def evaluate(s21: dict, s22: dict, s20: dict, held20: pd.DataFrame) -> dict:
    """Gates of T23 and T24 from monthly series.  s21/s22: {'net', 'gross', 'cost1'} (decisive net = 2 x c_raw);
    s20: {'net'} of the T20 control; held20: the control's held weights (S2 regression span)."""
    out = {}
    n21, n22 = win(s21["net"], W23), win(s22["net"], W24)
    m21, t21 = T.nw_tstat(n21, 6)
    m22, t22 = T.nw_tstat(n22, 6)
    praw = {"T23": p_one_sided(t21), "T24": p_one_sided(t22)}
    padj = T.holm(praw)
    # T23 S2: alpha vs the T20 control from its first held month to 1999-12
    start20 = first_held_month(held20, W23)
    if start20 is not None:
        span = (start20, W23[1])
        alpha = T.nw_regression(win(s21["net"], span), win(s20["net"], span), 6)
        alpha["span"] = [str(span[0]), str(span[1])]
    else:
        alpha = {"months": 0, "alpha_ann": np.nan, "alpha_t": np.nan, "span": None}
    be21 = breakeven(win(s21["gross"], W23), win(s21["cost1"], W23))
    be22 = breakeven(win(s22["gross"], W24), win(s22["cost1"], W24))
    a21 = win(s21["net"], (W23[0], SUB_A_END))
    a22 = win(s22["net"], (W24[0], SUB_A_END))
    sr22 = T.sr(n22)
    out["T23"] = [
        {"#": "S1", "criterion": "NW (6) t of mean net return > 2 and Holm-adjusted one-sided p < 0.0228, 1979-05..1999-12",
         "value": f"t {t21:.3f}; p raw {praw['T23']:.4f}, Holm {padj['T23']:.4f}",
         "pass": bool(t21 > 2 and padj["T23"] < S1_P)},
        {"#": "S2", "criterion": "alpha vs the T20 carry control > 0 and NW t > 1.5",
         "value": (f"alpha {100 * alpha['alpha_ann']:.2f}%/yr, t {alpha['alpha_t']:.3f} "
                   f"({alpha['span'][0]}..{alpha['span'][1]}, {alpha['months']} months)") if alpha["span"] else "no control",
         "pass": bool(alpha["span"] is not None and alpha["alpha_ann"] > 0 and alpha["alpha_t"] > 1.5)},
        {"#": "S3", "criterion": "break-even cost multiple >= 2, 1979-05..1999-12", "value": f"{be21:.2f}",
         "pass": bool(be21 >= 2)},
        {"#": "A", "criterion": "mean net return > 0 over sub-window (a) 1979-05..1991-01 (Amendment 1)",
         "value": f"{100 * a21.mean():+.3f}%/month ({len(a21)} months)", "pass": bool(a21.mean() > 0)},
    ]
    out["T24"] = [
        {"#": "S1", "criterion": "net SR > 0.20, 1979-05..1999-12", "value": f"{sr22:.4f}", "pass": bool(sr22 > 0.20)},
        {"#": "S3", "criterion": "break-even cost multiple >= 2, 1979-05..1999-12", "value": f"{be22:.2f}",
         "pass": bool(be22 >= 2)},
        {"#": "A", "criterion": "mean net return > 0 over sub-window (a) 1979-05..1991-01 (Amendment 1)",
         "value": f"{100 * a22.mean():+.3f}%/month ({len(a22)} months)", "pass": bool(a22.mean() > 0)},
    ]
    for k in ("T23", "T24"):
        out[f"{k}_overall_pass"] = all(g["pass"] for g in out[k])
    out["_stats"] = {"T23_nw": {"mean": m21, "t": t21, "months": int(len(n21))},
                     "T24_nw": {"mean": m22, "t": t22, "months": int(len(n22)), "sharpe": sr22},
                     "p_raw": praw, "p_holm": padj, "T24_p_gates_T24": False,
                     "alpha_vs_T20": alpha, "breakeven": {"T23": be21, "T24": be22},
                     "sub_a_mean": {"T23": float(a21.mean()), "T24": float(a22.mean())},
                     "T20_first_held_month": str(start20) if start20 is not None else None}
    return out


# ============================================================ sleeves
def make_sleeve(name: str, mks: dict, sig: dict, sgm: dict, kind: str, w, min_active: int | None = None):
    """t2022.build_targets + t2022.Sleeve with the rebalance months = the trial's window (positions start flat).
    `min_active` zeroes target months with fewer active markets (only for T22's half universes, section 4.5)."""
    months = pd.period_range(w[0], w[1], freq="M")
    W, SG = T.build_targets(mks, sig, sgm, kind, months)
    if min_active is not None:
        thin = SG.notna().sum(axis=1) < min_active
        W.loc[thin] = 0.0
    return T.Sleeve(name, mks, W, SG), SG


def series(sl) -> dict:
    return {"net": sl.monthly(2.0), "net2x": sl.monthly(4.0), "gross": sl.monthly(0.0), "cost1": sl.monthly_cost(1.0)}


# ============================================================ data checks D0-D3 (section 6 step 3)
def d0_hashes() -> dict:
    got = {f: sha(ROOT / f) for f in CODE_A160}
    ok = all(got[f] == h for f, h in CODE_A160.items())
    return {"pass": ok, "sha256": got}


def d1_availability() -> dict:
    committed = subprocess.run(["git", "show", f"{PRE_PREG}:results/T23-T24/availability_counts.csv"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout
    AV.run()
    now = (OUT / "availability_counts.csv").read_text()
    a = pd.read_csv(io.StringIO(committed), index_col=0)
    b = pd.read_csv(OUT / "availability_counts.csv", index_col=0)
    same = a.equals(b)
    return {"pass": bool(same), "rows": int(len(b)), "identical_text": committed == now}


def unit_break_candidates(r: pd.DataFrame, lo, hi) -> list[dict]:
    """Same-contract one-day moves above 30% that do not reverse (Build 0's unit_breaks formula), in [lo, hi].
    Classified as a unit break when the move is a rescaling by a power of ten (factor within 2% of 10^k, k != 0);
    otherwise a market move (reported)."""
    x = r[(r.index >= lo) & (r.index <= hi)]
    rr = x["r"]
    nxt = rr.shift(-1)
    big = (rr.abs() > 0.30) & (((1 + rr) * (1 + nxt) - 1).abs() > 0.5 * rr.abs())
    out = []
    for d in x.index[big.fillna(False).to_numpy()]:
        f = 1 + rr[d]
        unit = bool(f > 0 and min(abs(np.log10(f) - k) for k in (-3, -2, -1, 1, 2, 3)) < np.log10(1.02))
        out.append({"date": str(d.date()), "contract": x.at[d, "contract"], "unit_break": unit})
    return out


def d2_quality(mks: dict, xs: set, lo: dict, hi: dict) -> dict:
    """Build 0's A9 (gaps, 8-MAD reversing spikes resolved by the curve, limit-lock flags) and the unit-break check
    on the held series in the window: F1 for every market, F2 for the T21 / T20 markets.  A market with an
    unresolved spike, a gap over 5 days or a unit break in a held series is dropped (section 7 item 4)."""
    reading("D2: the A9 rolling statistics use each market's history from 1977 up to the window end; issues are "
            "counted from the window's first execution to the execution after 1999-12 (the exit of December's "
            "positions); a unit break is a non-reversing same-contract move above 30% whose factor is within 2% of a "
            "power of ten (a price-unit rescaling); other such moves are market moves and are listed")
    res, drop, issues_all = {}, set(), []
    for c, mk in mks.items():
        rets = {w: mk.r1 if w == "F1" else mk.r2 for w in ("F1", "F2")}
        rets = {w: d[d.index <= hi[c]] for w, d in rets.items()}
        q, issues = B0.a9_quality(mk.md, rets)
        issues = B0.resolve_spikes(mk.md, issues)
        held = ["F1", "F2"] if c in xs else ["F1"]
        bad = pd.DataFrame()
        if not issues.empty:
            issues = issues[(pd.to_datetime(issues["from"]) >= lo[c]) & (pd.to_datetime(issues["from"]) <= hi[c])]
            issues.insert(0, "market", c)
            issues_all.append(issues)
            bad = issues[issues["series"].isin(held) & (issues["status"] == "unresolved")]
        ub = {w: unit_break_candidates(rets[w], lo[c], hi[c]) for w in held}
        units = [u for w in held for u in ub[w] if u["unit_break"]]
        res[c] = {"held_series": held, "issues_in_window": int(len(issues)) if not issues.empty else 0,
                  "unresolved_in_held": int(len(bad)),
                  "spikes_genuine": int(((issues["type"] == "spike") & (issues["status"] != "unresolved")).sum())
                  if not issues.empty else 0,
                  "limit_locked_flags_1977_1999": {w: q[w]["limit_locked_flags"] for w in q},
                  "large_moves": {w: ub[w] for w in held}, "unit_breaks": len(units)}
        if len(bad) or units:
            drop.add(c)
    issues_df = pd.concat(issues_all) if issues_all else pd.DataFrame()
    return {"markets": res, "dropped": sorted(drop), "pass_no_drop": not drop}, issues_df


def d3_a3(mks: dict, commodities: list[str], aqr_dir: Path) -> tuple[dict, pd.DataFrame]:
    import os
    os.environ[B0.AQR_DIR_ENV] = str(aqr_dir)
    ew_aqr, _ = B0.load_aqr()
    m1 = pd.DataFrame({c: B0.monthly_f1_returns(mks[c].r1) for c in commodities})
    ew = m1.mean(axis=1, skipna=True)
    ew = ew[m1.notna().sum(axis=1) > 0]
    j = pd.concat([ew.rename("ours"), ew_aqr], axis=1, join="inner").dropna().loc[W24[0]:W24[1]]
    corr = float(j.corr().iloc[0, 1])
    res = {"months": int(len(j)), "first": str(j.index[0]), "last": str(j.index[-1]), "corr": corr,
           "corr_to_1990_01": float(j.loc[:"1990-01"].corr().iloc[0, 1]),
           "corr_1990_02_on": float(j.loc["1990-02":].corr().iloc[0, 1]),
           "markets_per_month_min": int(m1.loc[j.index].notna().sum(axis=1).min()),
           "markets_per_month_max": int(m1.loc[j.index].notna().sum(axis=1).max()),
           "threshold": A3_MIN, "pass": bool(corr >= A3_MIN)}
    priv = pd.concat([m1.loc[j.index], ew.loc[j.index].rename("ew_ours"), ew_aqr.loc[j.index].rename("aqr_ew")], axis=1)
    return res, priv


def fetch_aqr(aqr_dir: Path) -> dict:
    """Download the two AQR workbooks (public; kept outside this repository) and record their SHA-256."""
    import urllib.request
    aqr_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, url in AQR_URLS.items():
        p = aqr_dir / name
        if not p.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "em-macro research script"})
            with urllib.request.urlopen(req, timeout=120) as r:
                p.write_bytes(r.read())
        out[name] = {"bytes": p.stat().st_size, "sha256": sha(p), "url": url,
                     "downloaded_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
    return out


# ============================================================ context (reported, not decisive)
def straddles_he(mk) -> list[str]:
    """Months of T23's window whose HE F1 is a live-hog contract and F2 a lean-hog one (T20 control's carry legs)."""
    out = []
    for m, row in win(mk.rolls, W23).iterrows():
        a, b = row["F1"], row["F2"]
        if isinstance(a, str) and isinstance(b, str):
            ya, yb = CD.parse_contract(a), CD.parse_contract(b)
            if ya < HE_LEAN_FIRST <= yb:
                out.append(str(m))
    return out


def curve_moves(mk, around: str | None = None) -> dict:
    """Build 0's spec-change check on the window: month-on-month change of ln(F2/F1) on decision dates, in multiples
    of its median absolute change over the window; the three largest, and the largest within +-3 months of `around`."""
    r = win(mk.rolls, W23)
    sp = pd.Series({m: (np.log(mk.settle(a, t)) - np.log(mk.settle(b, t)))
                    if mk.settle(a, t) > 0 and mk.settle(b, t) > 0 else np.nan
                    for m, a, b, t in zip(r.index, r["F1"], r["F2"], r["decision"])})
    z = sp.diff().abs()
    z = z / z.median()
    top = z.sort_values(ascending=False).head(3)
    res = {"top3": [(str(k), round(float(v), 1)) for k, v in top.items() if np.isfinite(v)], "of": int(z.notna().sum())}
    if around:
        p = pd.Period(around, "M")
        w_ = z.loc[p - 3:p + 3].dropna()
        if len(w_):
            res["around"] = {"month": around, "max_multiple": round(float(w_.max()), 1), "at": str(w_.idxmax()),
                             "rank": int((z.dropna() > w_.max()).sum()) + 1}
    return res


def context(sl: dict, ser: dict, sg: dict, mks: dict, start20) -> dict:
    out = {}
    # performance table rows
    rows = []
    periods = {"window": None, "sub-window (a)": "a", "sub-window (b) 1991-02..1999-12": SUB_B,
               "1979..1989": "80s", "1990..1999": (pd.Period("1990-01", "M"), pd.Period("1999-12", "M"))}
    for key, s in ser.items():
        trial = "T23" if key.startswith("T21") else "T24" if key.startswith("T22") else "T23"
        w = W24 if trial == "T24" else W23
        if key.startswith("T20"):
            w = (start20, W23[1]) if start20 is not None else W23
        for pn, pw in periods.items():
            if pw is None:
                pw = w
            elif pw == "a":
                pw = (w[0], SUB_A_END)
            elif pw == "80s":
                pw = (w[0], pd.Period("1989-12", "M"))
            for cm in ("net", "net2x"):
                x = win(s[cm], pw).dropna()
                if len(x) >= 12:
                    st = T.stats(x)
                    st["nw_t_mean"] = T.nw_tstat(x, 6)[1]
                    rows.append({"series": key, "costs": "decisive" if cm == "net" else "2x", "period": pn, **st})
    out["performance"] = rows
    # by year
    by_year = {}
    for key in ("T21 sleeve|full", "T22 sleeve|full"):
        x = win(ser[key]["net"], W24 if key.startswith("T22") else W23)
        by_year[key] = {str(y): 100 * float((1 + g).prod() - 1) for y, g in x.groupby(x.index.year)}
    out["by_year_%"] = by_year
    # correlations (decisive net)
    span = (start20, W23[1]) if start20 is not None else W23
    fr = pd.DataFrame({"T21": ser["T21 sleeve|full"]["net"], "T22": ser["T22 sleeve|full"]["net"],
                       "T20 control": ser["T20 control|full"]["net"]})
    out["corr_T20_span"] = win(fr, span).corr().round(4).to_dict()
    out["corr_T21_T22_window"] = float(win(fr["T21"], W23).corr(win(fr["T22"], W23)))
    # T24's crisis correlation against the T20 control's worst 10% months (context for T22's S2)
    cs = win(fr["T20 control"], span)
    worst = cs.nsmallest(int(round(0.10 * len(cs)))).index
    out["T24_vs_T20control_worst10pct"] = {"months": [str(m) for m in sorted(worst)],
                                           "corr": float(fr["T22"].reindex(worst).corr(cs.loc[worst]))}
    # T24 P&L by asset class (gross, annualised)
    g22 = sl["T22 sleeve|full"].per_market_gross
    cls = {c: "commodities" if CD.MARKETS[c].kind == "commodity" else "currencies" for c in g22.columns}
    by = g22.T.groupby(cls).sum().T
    by = (1 + by).groupby(by.index.to_period("M")).prod() - 1
    out["T24_gross_by_asset_class_ann_%"] = {k: 100 * float(win(by[k], W24).mean() * 12) for k in by}
    # active markets and thin months
    act = {}
    for key, w in (("T21 sleeve|full", W23), ("T22 sleeve|full", W24), ("T20 control|full", W23)):
        n = sg[key].notna().sum(axis=1)
        act[key] = {"min": int(win(n, w).min()), "max": int(win(n, w).max()),
                    "months_6_to_9": [str(m) for m in win(n, w).index if 6 <= n[m] <= 9],
                    "months_below_6": [str(m) for m in win(n, w).index if n[m] < 6]}
    out["active"] = act
    # sleeve turnover
    out["turnover_x_pa"] = {k: float(win(s.held.diff().abs().sum(axis=1), W24 if k.startswith("T22") else W23).mean() * 12)
                            for k, s in sl.items()}
    # HE straddles and curve moves (T20 control's carry; section 7 item 3)
    out["HE_live_lean_straddle_months"] = straddles_he(mks["HE"]) if "HE" in mks else []
    out["curve_moves"] = {"HE": curve_moves(mks["HE"], "1997-02") if "HE" in mks else None,
                          "GF": curve_moves(mks["GF"]) if "GF" in mks else None,
                          "HG": curve_moves(mks["HG"]) if "HG" in mks else None}
    # sub-window (b) against the a160bfd run's committed 1991-1999 series (how closely (b) reproduces them)
    old = pd.read_csv(RESULTS / "T20-T22" / "monthly_net.csv", index_col=0)
    old.index = pd.PeriodIndex(old.index, freq="M")
    rep = {}
    for key, col in (("T21 sleeve|full", "T21 sleeve|full|decisive"), ("T22 sleeve|full", "T22 sleeve|full|decisive")):
        a, b = win(ser[key]["net"], SUB_B), win(old[col], SUB_B)
        rep[key] = {"corr": float(a.corr(b)), "mean_abs_diff_%": float(100 * (a - b).abs().mean()), "months": int(len(a))}
    out["sub_b_vs_a160bfd_run"] = rep
    return out


def window_check(mks: dict, sig: dict, sgm: dict, u21: list, u22: list) -> dict:
    """Active counts from t2022.build_targets alone (targets, no Sleeve): >= 6 in every window month, < 6 before."""
    out = {}
    for key, codes, w, kind, sk in (("T21 sleeve|full", u21, W23, "T21", "blend"),
                                    ("T22 sleeve|full", u22, W24, "T22", "mop")):
        months = pd.period_range(w[0] - 1, w[1], freq="M")
        _, SG = T.build_targets({c: mks[c] for c in codes}, {c: sig[kind][c] for c in codes},
                                {c: sgm[sk][c] for c in codes}, kind, months)
        n = SG.notna().sum(axis=1)
        inw, before = n.loc[w[0]:w[1]], int(n.loc[w[0] - 1])
        out[f"active_{key}"] = {"min_in_window": int(inw.min()), "before_window": before,
                                "first_month": str(w[0]), "pass": bool(inw.min() >= MIN_ACTIVE and before < MIN_ACTIVE)}
    return out


# ============================================================ run
def stage_run(aqr_dir: Path):
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    priv = CD.data_root() / "norgate" / "derived" / "T23-T24"
    priv.mkdir(parents=True, exist_ok=True)
    checks = {}

    def stop(msg: str):
        (OUT / "RUN.json").write_text(json.dumps({"stopped": msg, "checks": checks, "started_utc": started},
                                                 indent=1, default=str))
        raise Stop(msg)

    checks["D0"] = d0_hashes()
    print("D0", checks["D0"]["pass"], flush=True)
    if not checks["D0"]["pass"]:
        stop("D0: a160bfd code hash mismatch")
    checks["D1"] = d1_availability()
    print("D1", checks["D1"]["pass"], flush=True)
    if not checks["D1"]["pass"]:
        stop("D1: availability counts differ from the committed Phase 1 counts")
    av = json.loads((OUT / "availability.json").read_text())
    u21 = list(av["passing"]["T21"])
    u22 = list(av["passing"]["T22"])
    u20 = list(av["passing"]["T20"])
    WIN.apply()
    fx = pd.DataFrame(columns=["EUR", "GBP"])
    assert not set(u22) & set(T.FX_CCY), "a window instrument needs FX conversion"
    reading("No FX conversion: every window instrument is USD-quoted (6B, 6M; commodities), so t2022.Mkt receives an "
            "empty EUR/GBP frame")
    mks = {}
    for c in [c for c in CD.MARKETS if c in set(u21) | set(u22)]:
        print("market", c, flush=True)
        mks[c] = T.Mkt(c, fx)
    # D2
    lo, hi = {}, {}
    for c, mk in mks.items():
        start = max(W24[0], mk.entry)          # held in a trial from the later of the earliest window and entry
        r = win(mk.rolls, (start, W24[1] + 1))
        lo[c], hi[c] = r["execution"].iloc[0], r["execution"].iloc[-1]
    checks["D2"], issues = d2_quality(mks, set(u21) | set(u20), lo, hi)
    print("D2 dropped:", checks["D2"]["dropped"], flush=True)
    drop = set(checks["D2"]["dropped"])
    u21 = [c for c in u21 if c not in drop]
    u22 = [c for c in u22 if c not in drop]
    u20 = [c for c in u20 if c not in drop]
    # D3
    checks["aqr_files"] = fetch_aqr(aqr_dir)
    comm = [c for c in u22 if CD.MARKETS[c].kind == "commodity"]
    checks["D3"], a3priv = d3_a3(mks, comm, aqr_dir)
    print("D3", checks["D3"]["corr"], checks["D3"]["pass"], flush=True)
    a3priv.to_csv(priv / "A3_window_series.csv")
    if not issues.empty:
        issues.to_csv(priv / "A9_window_issues.csv", index=False)
    if not checks["D3"]["pass"]:
        stop("D3: A3 correlation below 0.90; T23 and T24 not run")

    # ---------------- signals and sleeves (one run each)
    b0 = json.loads((RESULTS / "T20-T22" / "build0.json").read_text())
    option = {c: b0["markets"][c]["A7"]["option"] for c in u20}
    sig = {"T20": {}, "T21": {}, "T22": {}}
    sgm = {"blend": {}, "mop": {}}
    for c, mk in mks.items():
        sgm["blend"][c], sgm["mop"][c] = mk.sigma_blend(), mk.sigma_mop()
        if c in u21:
            sig["T21"][c] = T.signal_t21(mk)
        if c in u20:
            sig["T20"][c] = T.signal_t20(mk, option[c])
        if c in u22:
            sig["T22"][c] = T.signal_t22(mk, sgm["mop"][c])
    halves21 = {h: [c for c in T.XS_HALF[h] if c in u21] for h in ("A", "B")}
    halves22 = {h: [c for c in T.T22_HALF[h] if c in u22] for h in ("A", "B")}
    plan = [("T21 sleeve|full", "T21", u21, W23, None, "blend"),
            ("T21 sleeve|half A", "T21", halves21["A"], W23, None, "blend"),
            ("T21 sleeve|half B", "T21", halves21["B"], W23, None, "blend"),
            ("T22 sleeve|full", "T22", u22, W24, None, "mop"),
            ("T22 sleeve|half A", "T22", halves22["A"], W24, MIN_ACTIVE, "mop"),
            ("T22 sleeve|half B", "T22", halves22["B"], W24, MIN_ACTIVE, "mop"),
            ("T20 control|full", "T20", u20, W23, None, "blend")]
    # window check (Amendment 2): targets only, before any sleeve, position or P&L is computed
    reading("Window check (Amendment 2): t2022.build_targets alone (no Sleeve) for each full sleeve over its window and "
            "the month before; at least 6 active in every window month and fewer than 6 in the month before")
    checks.update(window_check(mks, sig, sgm, u21, u22))
    print("window check", {k: v for k, v in checks.items() if k.startswith("active_")}, flush=True)
    if not all(v["pass"] for k, v in checks.items() if k.startswith("active_")):
        stop("window check: active counts do not reproduce the pre-registered windows (Amendment 2)")
    sl, sg = {}, {}
    for key, kind, codes, w, mina, sk in plan:
        sub = {c: mks[c] for c in codes}
        sl[key], sg[key] = make_sleeve(key, sub, {c: sig[kind][c] for c in codes}, {c: sgm[sk][c] for c in codes},
                                       kind, w, mina)
        print("sleeve", key, flush=True)
    reading("T22 half universes (context): target months with fewer than 6 active instruments hold nothing (section "
            "4.5); the full T22 sleeve has at least 6 in every window month, so nothing is zeroed there")

    ser = {k: series(s) for k, s in sl.items()}
    crit = evaluate({k: ser["T21 sleeve|full"][k] for k in ("net", "gross", "cost1")},
                    {k: ser["T22 sleeve|full"][k] for k in ("net", "gross", "cost1")},
                    {"net": ser["T20 control|full"]["net"]}, sl["T20 control|full"].held)
    start20 = first_held_month(sl["T20 control|full"].held, W23)
    crit["_universe"] = {"T23": u21, "T24": u22, "T20 control": u20, "dropped_D2": sorted(drop),
                         "option": option, "halves": {"T21": halves21, "T22": halves22}}
    (OUT / "criteria.json").write_text(json.dumps(crit, indent=1, default=float))     # the decision, saved first
    ctx = context(sl, ser, sg, mks, start20)
    (OUT / "context.json").write_text(json.dumps(ctx, indent=1, default=float))
    pd.DataFrame(ctx["performance"]).to_csv(OUT / "performance.csv", index=False, float_format="%.4f")
    # aggregate monthly sleeve series, window months only
    mon = {}
    for k, s in ser.items():
        w = W24 if k.startswith("T22") else W23
        for cm in ("net", "net2x", "gross", "cost1"):
            name = {"net": "decisive", "net2x": "2x", "gross": "gross", "cost1": "cost1x"}[cm]
            mon[f"{k}|{name}"] = win(s[cm], w)
    M = pd.DataFrame(mon).loc[W24[0]:W24[1]]
    M.index = M.index.astype(str)
    M.index.name = "month"
    M.to_csv(OUT / "monthly_net.csv", float_format="%.6f")
    # private per-market outputs
    for k, s in sl.items():
        tag = k.replace(" sleeve", "").replace(" control", "_control").replace("|", "_").replace(" ", "")
        s.held.to_csv(priv / f"held_{tag}.csv")
        s.per_market_gross.loc["1979-01-01":"2000-01-31"].to_csv(priv / f"daily_gross_by_market_{tag}.csv")
        s.trades.to_csv(priv / f"trades_{tag}.csv", index=False)
    for t_ in sig:
        pd.DataFrame(sig[t_]).loc[:W24[1]].to_csv(priv / f"signals_{t_}.csv")
    files = list(CODE_A160) + ["em_macro/t2324.py", "em_macro/t2324_window.py", "em_macro/t2324_avail.py",
                               "docs/prereg/T23-T24_pre2000_backtest.md", "results/T23-T24/availability_counts.csv"]
    (OUT / "RUN.json").write_text(json.dumps({
        "run_started_utc": started, "run_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_run": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                          text=True).stdout.strip(),
        "pre_registration": PRE_PREG, "amendment_1": AMEND_1, "amendment_2": AMEND_2,
        "pandas": pd.__version__, "numpy": np.__version__, "checks": checks,
        "inputs": {"norgate": [CD.SNAPSHOT, CD.FIN_SNAPSHOT, CD.META_SNAPSHOT],
                   "norgate_manifest_sha256": {s: sha(CD.data_root() / "norgate" / s / ("metadata.csv" if s == CD.META_SNAPSHOT else "manifest.csv"))
                                               for s in (CD.SNAPSHOT, CD.FIN_SNAPSHOT, CD.META_SNAPSHOT)},
                   "aqr": checks["aqr_files"]},
        "readings": READINGS + T.DECISIONS,
        "sha256": {f: sha(ROOT / f) for f in files if (ROOT / f).exists()}}, indent=1, default=str))
    WIN.restore()
    for k in ("T23", "T24"):
        print(k, "OVERALL", "PASS" if crit[f"{k}_overall_pass"] else "FAIL", flush=True)


# ============================================================ report
def _f(x, d=3):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def write_report():
    crit = json.loads((OUT / "criteria.json").read_text())
    ctx = json.loads((OUT / "context.json").read_text())
    run = json.loads((OUT / "RUN.json").read_text())
    ck = run["checks"]
    st = crit["_stats"]
    L = []
    a = L.append
    a("# Trials T23–T24: T21 basis-momentum and T22 diversified trend on 1979–1999 — results\n")
    a("| item | value |\n|---|---|")
    a("| pre-registration | `docs/prereg/T23-T24_pre2000_backtest.md` (`215b3c4`) with Amendment 1 (`648534b`) and Amendment 2 (`a6fe7d8`: T24 from 1979-05; window check before any sleeve) |")
    a(f"| rules and code | T21 and T22 exactly as run at `a160bfd` (code identical at `7405e5f`); D0 hash check: "
      f"{'pass' if ck['D0']['pass'] else 'FAIL'} |")
    a(f"| run | {run['run_started_utc']} to {run['run_finished_utc']} UTC, commit `{run['git_head_at_run'][:7]}`, "
      f"pandas {run['pandas']}, numpy {run['numpy']}; one run, nothing re-run |")
    a("| code provenance | the commit before the run failed (stale path in `git add`), so the run used the amended "
      "runner from the working tree on HEAD `633e983`; those files were committed unchanged in `1e0eb4f` (each "
      "SHA-256 recorded in `RUN.json` equals the committed file) |")
    a("| first attempt | stopped at the window check before any gate (`results/T23-T24/attempt1_stop_report.md`); "
      "Amendment 2 moved T24's start to 1979-05 and the check ahead of any sleeve |")
    a(f"| windows | T23 1979-05..1999-12 ({st['T23_nw']['months']} months); T24 1979-05..1999-12 "
      f"({st['T24_nw']['months']} months) |")
    u = crit["_universe"]
    a(f"| T23 universe | {len(u['T23'])}: {' '.join(u['T23'])} |")
    a(f"| T24 universe | {len(u['T24'])}: {' '.join(u['T24'])} |")
    a(f"| T20 control | {len(u['T20 control'])} markets, Build 0 Option A/B unchanged; first held month "
      f"{st['T20_first_held_month']} |")
    a(f"| markets dropped by D2 | {', '.join(u['dropped_D2']) or 'none'} |\n")
    a("Each sleeve is stand-alone at a 10% volatility target, at decisive costs (2 × the cost estimate) unless stated. "
      "v1.0 and v1.1 do not exist before 2005, so only the sleeve-level gates run. 1991-02..1999-12 was computed, "
      "but not reported, by the a160bfd run; the months before were never computed (Amendment 1's gate A).\n")
    a("## 1. Pass/fail (decisive costs)\n")
    a("| trial | overall | S1 | S2 | S3 | A |\n|---|---|---|---|---|---|")
    for k, name in (("T23", "T23 basis-momentum (T21 rules)"), ("T24", "T24 diversified trend (T22 rules)")):
        g = {x["#"]: ("pass" if x["pass"] else "**FAIL**") for x in crit[k]}
        a(f"| {name} | **{'PASS' if crit[k + '_overall_pass'] else 'FAIL'}** | {g.get('S1')} | "
          f"{g.get('S2', 'not applicable (no v1.0 carry sleeve before 2005)')} | {g.get('S3')} | {g.get('A')} |")
    for k in ("T23", "T24"):
        a(f"\n### {k}\n\n| # | gate | measured | result |\n|---|---|---|---|")
        for x in crit[k]:
            a(f"| {x['#']} | {x['criterion']} | {x['value']} | {'pass' if x['pass'] else '**FAIL**'} |")
    a("\n## 2. Holm adjustment (§4.3)\n")
    a("| trial | NW t of mean net return | one-sided p | Holm-adjusted p | gates the trial? |\n|---|---|---|---|---|")
    a(f"| T23 | {_f(st['T23_nw']['t'])} | {_f(st['p_raw']['T23'], 4)} | {_f(st['p_holm']['T23'], 4)} | yes (< 0.0228) |")
    a(f"| T24 | {_f(st['T24_nw']['t'])} | {_f(st['p_raw']['T24'], 4)} | {_f(st['p_holm']['T24'], 4)} | no (reported) |")
    a("\n## 3. Data checks before any sleeve (§6 step 3)\n")
    a("| check | result |\n|---|---|")
    a(f"| D0 a160bfd code SHA-256 | {'pass' if ck['D0']['pass'] else 'FAIL'} |")
    a(f"| D1 Phase 1 counts reproduced | {'pass' if ck['D1']['pass'] else 'FAIL'} ({ck['D1']['rows']} months) |")
    d2 = ck["D2"]["markets"]
    n_issues = sum(v["issues_in_window"] for v in d2.values())
    n_gen = sum(v["spikes_genuine"] for v in d2.values())
    n_large = sum(len(x) for v in d2.values() for x in v["large_moves"].values())
    a(f"| D2 A9 and unit breaks on held series | {'no market dropped' if ck['D2']['pass_no_drop'] else 'dropped: ' + ', '.join(ck['D2']['dropped'])}; "
      f"{n_issues} A9 issues in the window, {n_gen} curve-confirmed spikes; {n_large} non-reversing moves above 30%, "
      f"{sum(v['unit_breaks'] for v in d2.values())} of them unit breaks |")
    d3 = ck["D3"]
    a(f"| D3 A3 vs AQR *Commodities for the Long Run* | **{d3['corr']:.3f}** ({d3['months']} months {d3['first']}..{d3['last']}, "
      f"{d3['markets_per_month_min']}–{d3['markets_per_month_max']} markets; to 1990-01: {d3['corr_to_1990_01']:.3f}; "
      f"from 1990-02: {d3['corr_1990_02_on']:.3f}); threshold 0.90: {'pass' if d3['pass'] else 'FAIL'} |")
    for k in ("active_T21 sleeve|full", "active_T22 sleeve|full"):
        a(f"| window check, {k[7:]} | at least {ck[k]['min_in_window']} active in every window month; "
          f"{ck[k]['before_window']} in the month before |")
    big = [f"{c} {x['date']} ({x['contract']})" for c, v in d2.items() for s in v["large_moves"].values() for x in s]
    if big:
        a(f"\nNon-reversing same-contract moves above 30% (market moves, not unit breaks): {'; '.join(big)}.")
    a("\n## 4. Stand-alone sleeves (reported; decisive costs unless stated)\n")
    a("| series | costs | period | months | Sharpe | return %/yr | vol %/yr | MaxDD % | NW t |\n|---|---|---|---|---|---|---|---|---|")
    for r in ctx["performance"]:
        a(f"| {r['series']} | {r['costs']} | {r['period']} ({r['start']}..{r['end']}) | {r['months']} | {_f(r['sharpe'])} | "
          f"{_f(r['ann_return_%'], 2)} | {_f(r['ann_vol_%'], 2)} | {_f(r['max_drawdown_%'], 2)} | {_f(r['nw_t_mean'], 2)} |")
    a("\nThe T20 control is not a trial; its figures are not a test of T20, which stays failed.\n")
    a("**By year** (%, decisive):\n")
    yrs = sorted(set(ctx["by_year_%"]["T22 sleeve|full"]) | set(ctx["by_year_%"]["T21 sleeve|full"]))
    a("| year | " + " | ".join(yrs) + " |\n|---|" + "---|" * len(yrs))
    for k, v in ctx["by_year_%"].items():
        a(f"| {k} | " + " | ".join(_f(v.get(y), 1) for y in yrs) + " |")
    a("\n## 5. Other context\n")
    a("| item | value |\n|---|---|")
    al = st["alpha_vs_T20"]
    a(f"| T23 regression on the T20 control | alpha {100 * al['alpha_ann']:.2f}%/yr (t {_f(al['alpha_t'])}), beta {_f(al.get('beta'))} "
      f"(t {_f(al.get('beta_t'))}), {al['months']} months |")
    a(f"| correlation T21–T22 sleeves, T23 window | {_f(ctx['corr_T21_T22_window'])} |")
    c = ctx["corr_T20_span"]
    a(f"| correlations over the T20 control's span | T21–T20 {_f(c['T21']['T20 control'])}, T22–T20 {_f(c['T22']['T20 control'])} |")
    cw = ctx["T24_vs_T20control_worst10pct"]
    a(f"| T24 vs the T20 control in its worst 10% of months (context for T22's S2) | {_f(cw['corr'])} over {len(cw['months'])} months |")
    for k, v in ctx["T24_gross_by_asset_class_ann_%"].items():
        a(f"| T24 gross P&L, {k}, %/yr | {_f(v, 2)} |")
    for k, v in ctx["active"].items():
        a(f"| active markets, {k} | {v['min']}–{v['max']}; 6–9 in {len(v['months_6_to_9'])} months "
          f"({', '.join(v['months_6_to_9'][:10])}{' …' if len(v['months_6_to_9']) > 10 else ''}); below 6 in {len(v['months_below_6'])} |")
    for k, v in ctx["turnover_x_pa"].items():
        a(f"| turnover {k}, x/yr | {_f(v, 2)} |")
    a(f"| HE live/lean straddles in the T20 control's carry | {len(ctx['HE_live_lean_straddle_months'])} months "
      f"({', '.join(ctx['HE_live_lean_straddle_months'])}) |")
    for k, v in ctx["curve_moves"].items():
        if v:
            ar = v.get("around")
            extra = (f"; within 3 months of {ar['month']}: {ar['max_multiple']} at {ar['at']}, rank {ar['rank']} of {v['of']}"
                     if ar else "")
            top = ", ".join(f"{m} {x}" for m, x in v["top3"])
            a(f"| {k} largest ln(F2/F1) monthly changes (x median) | {top}{extra} |")
    for k, v in ctx["sub_b_vs_a160bfd_run"].items():
        a(f"| sub-window (b) vs the a160bfd run's 1991–1999 {k} | correlation {_f(v['corr'])}, mean absolute "
          f"difference {_f(v['mean_abs_diff_%'], 3)}%/month over {v['months']} months |")
    a("\n## 6. Implementation readings\n")
    for i, r in enumerate(run["readings"], 1):
        a(f"{i}. {r}")
    a("\n## 7. What the result means (pre-registered, §1)\n")
    p23, p24 = crit["T23_overall_pass"], crit["T24_overall_pass"]
    if not p23 and not p24:
        a("Both trials fail, so **the commodity line is closed**: no further commodity sleeve is pre-registered in this "
          "programme. v1.0 and v1.1 are unchanged, and the T20–T22 combination tests stay failed.")
    else:
        for k, p in (("T23", p23), ("T24", p24)):
            a(f"- {k}: {'passes — supports a separate, later pre-registration of a zero-size live shadow' if p else 'fails — this sleeve is closed'}.")
        a("\nv1.0 and v1.1 are unchanged, and the T20–T22 combination tests stay failed.")
    REPORT.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        import os
        try:
            stage_run(Path(os.environ.get(B0.AQR_DIR_ENV, CD.data_root().parent / "aqr")))
        except Stop as e:
            sys.exit(f"STOPPED (pre-registered stop rule): {e}")
    elif cmd == "report":
        write_report()
    else:
        sys.exit(__doc__)
