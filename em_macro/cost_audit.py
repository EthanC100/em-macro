"""Cost audit of the frozen v1.0 systematic strategy (diagnostic only).

    python -m em_macro.cost_audit model         # step 1: cost model, turnover and cost shares by instrument
    python -m em_macro.cost_audit sensitivity   # step 3: v1.0 2020-01..2026-09 at cost multiples and per-instrument
                                                #         low / central / high estimates; break-even multiples
    python -m em_macro.cost_audit turnover      # step 4: turnover decomposition (signal / vol rescaling / band)

The write-up is results/cost_audit_v1.md.

Read-only with respect to the strategy.  It imports em_macro.systematic (tag v1.0-frozen, unchanged) and calls
its frozen functions.  Costs in v1.0 never feed back into weights (selection, sizing, vol targeting, leverage cap
and no-trade band are all cost-free), so changing the cost vector passed to SY.run changes only the cost line of
the P&L: the positions are v1.0's positions in every row reported here.  No alternative trading rule is run.

Step 2 (literature cost estimates) is a hand-built table, results/cost_audit/cost_estimates.csv, with sources in
the report.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from . import systematic as SY
from .config import RAW, RESULTS, ROOT

OUT = RESULTS / "cost_audit"
REPORT = RESULTS / "cost_audit_v1.md"
CACHE = RAW / "cost_audit_inputs.pkl"   # local cache of SY.build_inputs() (data/raw is gitignored)
TEST = (SY.TEST_START, pd.Period("2026-09", "M"))
DESIGN_P = (None, SY.FIT_END)
V1 = SY.VARIANTS["combined"]
LAG = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}
MULTIPLES = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
FX = list(SY.FX_INSTR)
FROZEN_SHA = "1eb4cf6b1c537c1711e5fff0b7aa044fee932c20992eb0d3cea4c3c5fc50be66"


# ================================================================ helpers
def _sha(path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def check_frozen():
    sha = _sha("em_macro/systematic.py")
    assert sha == FROZEN_SHA, f"em_macro/systematic.py differs from v1.0 ({sha})"
    return sha


def inputs(refresh: bool = False) -> dict:
    """SY.build_inputs() (frozen), cached locally because some sources download slowly."""
    if CACHE.exists() and not refresh:
        return pickle.loads(CACHE.read_bytes())
    inp = SY.build_inputs()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps(inp))
    return inp


def net(res: pd.DataFrame) -> pd.Series:
    return pd.Series(res["net"].to_numpy(), index=res.index, name="net")


def perf(r: pd.Series) -> dict:
    """Same definitions as SY.stats: Sharpe = mean/sd (ddof 1) x sqrt(12); compounded return; MaxDD on the
    compounded monthly index."""
    r = r.dropna()
    w = (1 + r).cumprod()
    yrs = len(r) / 12
    return {"months": len(r), "sharpe": float(r.mean() / r.std() * np.sqrt(12)),
            "ann_return_%": 100 * float(w.iloc[-1] ** (1 / yrs) - 1), "ann_vol_%": 100 * float(r.std() * np.sqrt(12)),
            "max_drawdown_%": 100 * float((w / w.cummax() - 1).min()), "ann_mean_%": 100 * 12 * float(r.mean())}


def run_with_costs(inp: dict, cost: dict) -> pd.DataFrame:
    """Frozen SY.run with a different per-instrument cost vector (same positions)."""
    inp2 = dict(inp)
    inp2["cost"] = {k: float(cost[k]) for k in inp["cost"]}
    return SY.run(inp2, V1)


def traded(W: pd.DataFrame, index) -> pd.DataFrame:
    """|dW| per instrument, dated like v1.0's costs (the month the trade starts earning)."""
    out = {}
    for k in W.columns:
        out[k] = W[k].diff().abs().shift(LAG["fx" if k in FX else "bond"])
    return pd.DataFrame(out).reindex(index).fillna(0.0)


def held(W: pd.DataFrame, index) -> pd.DataFrame:
    """|W| per instrument dated like its P&L (the month the position earns)."""
    out = {}
    for k in W.columns:
        out[k] = W[k].abs().shift(LAG["fx" if k in FX else "bond"])
    return pd.DataFrame(out).reindex(index).fillna(0.0)


def _sl(df, p):
    return df.loc[p[0]:p[1]]


# ================================================================ step 1
CODE_REFS = {
    "cost_params": "em_macro/systematic.py:58-59 (DESIGN['costs']: major 0.001, high_cost 0.003, "
                   "high_cost_countries TR ID CO CL, spread_legs 2); also results/systematic/fit/frozen_design.json",
    "cost_map": "em_macro/systematic.py:153-158 (build_inputs: per-instrument cost dict)",
    "cost_charge": "em_macro/systematic.py:264-265 (run: cost = |w_t - w_{t-1}| x cost, charged in the month the "
                   "new weight starts earning)",
    "fx_return": "em_macro/systematic.py:118-125 (FX excess return: spot change x (1 + local policy rate x tau) "
                 "- (1 + fed funds x tau); BIS policy rates, FRED DFF, monthly averages)",
    "bond_return": "em_macro/systematic.py:131-142 (bond excess return: (y - funding)/12 - D dy + C dy^2/2; "
                   "funding = local policy rate for EM 10y and the Bund, 0 for the spreads)",
    "net": "em_macro/systematic.py:266-270 (net = gross - cost; nothing else is added)",
}
TYPE = {"BRL": "NDF (1m, synthetic)", "COP": "NDF (1m, synthetic)", "CLP": "NDF (1m, synthetic)",
        "IDR": "NDF (1m, synthetic)", "MXN": "deliverable forward (1m, synthetic)",
        "ZAR": "deliverable forward (1m, synthetic)", "TRY": "deliverable forward (1m, synthetic)",
        "PLN": "deliverable forward (1m, synthetic)", "GBP": "G10 forward (1m, synthetic)",
        "EUR": "G10 forward (1m, synthetic)"}
for _c in SY.EM_BONDS:
    TYPE[f"{_c}10Y"] = "EM local 10y bond (synthetic, monthly-average yield)"
for _c in SY.EU_SPREADS:
    TYPE[f"{_c}-DE"] = "10y spread over Bund, two legs (synthetic)"
TYPE["DE10Y"] = "10y Bund (synthetic)"


def funding_text(k: str) -> str:
    if k in FX:
        return ("excess return over USD: earns local policy rate, pays fed funds (BIS / FRED DFF monthly avg, "
                "prior month); no forward points, NDF basis or cross-currency basis")
    if k.endswith("-DE"):
        return "no funding leg (long country bond, short Bund; return = spread/12 - D dspread); no repo spread"
    if k == "DE10Y":
        return "excess over the euro-area policy rate (BIS XM); no repo spread"
    return "excess over the local policy rate (BIS); no repo spread; local-currency (FX-hedged) return"


def stage_model():
    check_frozen()
    inp = inputs()
    res = SY.run(inp, V1)
    W = res.attrs["weights"]
    tr = _sl(traded(W, res.index), TEST)
    ho = _sl(held(W, res.index), TEST)
    cost = pd.Series(inp["cost"])
    yrs = len(tr) / 12
    cdrag = tr.mul(cost, axis=1)
    # identity: per-instrument costs add up to v1.0's cost line
    err = float((cdrag.sum(axis=1) - _sl(res["cost"], TEST)).abs().max())
    assert err < 1e-12, err
    rows = []
    for k in W.columns:
        rows.append({"instrument": k, "book": "FX" if k in FX else "bonds", "type_assumed": TYPE[k],
                     "one_way_cost_bp": 1e4 * cost[k],
                     "cost_rule": ("high_cost x 2 legs" if k.endswith("-DE") and k[:2] in SY.DESIGN["costs"]["high_cost_countries"]
                                   else "major x 2 legs" if k.endswith("-DE")
                                   else "high_cost" if (SY.FX_INSTR.get(k, k[:2]) in SY.DESIGN["costs"]["high_cost_countries"])
                                   else "major"),
                     "roll_cost_bp": 0.0, "funding": funding_text(k),
                     "avg_gross_position_x": float(ho[k].mean()),
                     "turnover_x_pa": float(tr[k].sum() / yrs),
                     "cost_drag_%_pa": 100 * float(cdrag[k].sum() / yrs)})
    t = pd.DataFrame(rows)
    t["turnover_share_%"] = 100 * t["turnover_x_pa"] / t["turnover_x_pa"].sum()
    t["cost_share_%"] = 100 * t["cost_drag_%_pa"] / t["cost_drag_%_pa"].sum()
    t["turnover_per_unit_held"] = t["turnover_x_pa"] / t["avg_gross_position_x"].replace(0, np.nan)
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "step1_cost_model.csv", index=False, float_format="%.4f")
    # totals and checks against the committed v1.0 result
    p = perf(_sl(net(res), TEST))
    summ = {"period": f"{TEST[0]}..{TEST[1]}", "months": len(tr),
            "total_turnover_x_pa": float(t["turnover_x_pa"].sum()),
            "total_cost_drag_%_pa": float(t["cost_drag_%_pa"].sum()),
            "v1_cost_drag_%_pa_from_run": 100 * float(_sl(res["cost"], TEST).mean() * 12),
            "avg_cost_bp_per_unit_traded": 1e4 * float(t["cost_drag_%_pa"].sum() / 100 / t["turnover_x_pa"].sum()),
            "fx_turnover_x_pa": float(t.loc[t.book == "FX", "turnover_x_pa"].sum()),
            "bond_turnover_x_pa": float(t.loc[t.book == "bonds", "turnover_x_pa"].sum()),
            "fx_cost_%_pa": float(t.loc[t.book == "FX", "cost_drag_%_pa"].sum()),
            "bond_cost_%_pa": float(t.loc[t.book == "bonds", "cost_drag_%_pa"].sum()),
            "gross_%_pa_arith": 100 * float(_sl(res["gross"], TEST).mean() * 12),
            "net_%_pa_arith": 100 * float(_sl(res["net"], TEST).mean() * 12),
            "sharpe_1x": p["sharpe"], "ann_return_1x_%": p["ann_return_%"], "maxdd_1x_%": p["max_drawdown_%"],
            "avg_gross_leverage": float(_sl(res["gross_leverage"], TEST).mean()),
            "cash_interest_included": False, "code_refs": CODE_REFS,
            "systematic_py_sha256": check_frozen()}
    # reproduction of the committed v1.0 test table
    tab = SY.evaluate(inp, slice(*TEST))
    ref = pd.read_csv(ROOT / "results/systematic/test/performance_2020_on.csv")
    num = [c for c in ref.columns if ref[c].dtype.kind == "f"]
    summ["reproduction_max_abs_diff_4dp"] = float(np.nanmax(np.abs(tab[num].astype(float).round(4).values
                                                                    - ref[num].values)))
    (OUT / "step1_summary.json").write_text(json.dumps(summ, indent=1))
    print(t.round(3).to_string())
    print(json.dumps({k: v for k, v in summ.items() if k != "code_refs"}, indent=1))


# ================================================================ step 3
def load_estimates() -> pd.DataFrame:
    return pd.read_csv(OUT / "cost_estimates.csv").set_index("instrument")


def roll_cost_series(inp: dict, W: pd.DataFrame, oneway: dict, index) -> pd.Series:
    """Roll cost under the spec section 8 convention (roll = 0.5 x one-way cost on the whole position at each
    roll).  FX forwards / NDFs roll monthly; the bond positions are treated as futures or funded cash bonds
    rolled quarterly (Mar/Jun/Sep/Dec).  Charged on the position earning in that month."""
    H = held(W, index)
    out = pd.Series(0.0, index=index)
    q = np.array([m.month in (3, 6, 9, 12) for m in index])
    for k in W.columns:
        c = 0.5 * oneway[k] * H[k]
        out += c if k in FX else c * q
    return out


def stage_sensitivity():
    check_frozen()
    inp = inputs()
    base = pd.Series(inp["cost"])
    res1 = SY.run(inp, V1)
    W = res1.attrs["weights"]
    g = net(res1) + res1["cost"]                     # gross P&L (positions do not depend on costs)
    c1 = res1["cost"]
    rows, check = [], []
    for m in MULTIPLES:
        res = run_with_costs(inp, (base * m).to_dict())
        assert (res.attrs["weights"] - W).abs().max().max() == 0.0          # same positions
        r = net(res)
        check.append(float((r - (g - m * c1)).abs().max()))
        for pname, p in (("2020-01..2026-09", TEST), ("2005-2019 (design, context)", DESIGN_P)):
            rows.append({"scenario": f"{m:g}x v1.0 costs", "period": pname, **perf(_sl(r, p)),
                         "cost_drag_%_pa": 100 * float(_sl(res["cost"], p).mean() * 12)})
    est = load_estimates()
    for col in ("low", "central", "high"):
        cv = (est[f"{col}_bp"] / 1e4).to_dict()
        res = run_with_costs(inp, cv)
        assert (res.attrs["weights"] - W).abs().max().max() == 0.0
        for pname, p in (("2020-01..2026-09", TEST), ("2005-2019 (design, context)", DESIGN_P)):
            rows.append({"scenario": f"literature {col} (per instrument)", "period": pname, **perf(_sl(net(res), p)),
                         "cost_drag_%_pa": 100 * float(_sl(res["cost"], p).mean() * 12)})
        # same, plus roll costs (spec section 8 convention) -- an add-on to the frozen P&L, not a new strategy
        roll = roll_cost_series(inp, W, cv, res.index)
        r2 = net(res) - roll
        for pname, p in (("2020-01..2026-09", TEST), ("2005-2019 (design, context)", DESIGN_P)):
            rows.append({"scenario": f"literature {col} + roll costs", "period": pname, **perf(_sl(r2, p)),
                         "cost_drag_%_pa": 100 * float((_sl(res["cost"], p) + _sl(roll, p)).mean() * 12)})
    tab = pd.DataFrame(rows)
    # break-even multiples of v1.0's cost vector (net = gross - m x cost; exact, positions fixed)
    be = {}
    for pname, p in (("2020-01..2026-09", TEST), ("2005-2019 (design, context)", DESIGN_P)):
        gg, cc = _sl(g, p), _sl(c1, p)
        f = lambda m, tgt: perf(gg - m * cc)["sharpe"] - tgt
        be[pname] = {"sharpe_at_0x": perf(gg)["sharpe"], "sharpe_at_1x": perf(gg - cc)["sharpe"]}
        for tgt in (0.0, 0.3):
            try:
                be[pname][f"multiple_sharpe_{tgt:g}"] = brentq(f, 0.0, 20.0, args=(tgt,))
            except ValueError:
                be[pname][f"multiple_sharpe_{tgt:g}"] = float("nan")
        # same break-evens expressed as multiples of the literature central vector (incl. and excl. rolls)
        cen = (load_estimates()["central_bp"] / 1e4).to_dict()
        rc = run_with_costs(inp, cen)
        ccen = _sl(rc["cost"], p)
        rollc = _sl(roll_cost_series(inp, W, cen, rc.index), p)
        for lab, cvec in (("central", ccen), ("central_plus_roll", ccen + rollc)):
            for tgt in (0.0, 0.3):
                fn = lambda m: perf(gg - m * cvec)["sharpe"] - tgt
                try:
                    be[pname][f"{lab}_multiple_sharpe_{tgt:g}"] = brentq(fn, 0.0, 20.0)
                except ValueError:
                    be[pname][f"{lab}_multiple_sharpe_{tgt:g}"] = float("nan")
        be[pname]["breakeven_avg_cost_bp_sharpe_0"] = (
            be[pname]["multiple_sharpe_0"] * 1e4 * float(cc.sum()) / float(traded(W, res1.index).loc[p[0]:p[1]].sum().sum()))
        be[pname]["breakeven_avg_cost_bp_sharpe_0.3"] = (
            be[pname]["multiple_sharpe_0.3"] * 1e4 * float(cc.sum()) / float(traded(W, res1.index).loc[p[0]:p[1]].sum().sum()))
    # fine grid for the report
    grid = []
    gg, cc = _sl(g, TEST), _sl(c1, TEST)
    for m in np.round(np.arange(0, 3.01, 0.25), 2):
        grid.append({"multiple": m, **perf(gg - m * cc)})
    OUT.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT / "step3_sensitivity.csv", index=False, float_format="%.4f")
    pd.DataFrame(grid).to_csv(OUT / "step3_grid.csv", index=False, float_format="%.4f")
    meta = {"breakeven": be, "max_abs_diff_run_vs_identity": max(check),
            "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_head": _git_head(),
            "systematic_py_sha256": check_frozen(), "pandas": pd.__version__, "numpy": np.__version__}
    (OUT / "step3_breakeven.json").write_text(json.dumps(meta, indent=1))
    print(tab[tab.period == "2020-01..2026-09"].round(3).to_string())
    print(json.dumps(be, indent=1))


# ================================================================ step 4
def _components(inp: dict):
    """Rebuild v1.0's weight components from the frozen functions:
    target_{i,t} = sign x a_{i,t} x b_{book,t} x c_t, with a = 1/vol_i (SY._vol), b = book vol scaler
    (SY.book_weights / raw), c = 0.5 x portfolio vol scaler x leverage-cap factor (pre-band target from SY.run
    with the band switched off, which is the identical code path up to the band)."""
    Wb = {b: SY.book_weights(inp[b], V1) for b in ("fx", "bond")}
    vol = {b: SY._vol(inp[b]["ret"]) for b in ("fx", "bond")}
    target = SY.run(inp, V1, band=0).attrs["weights"]          # band=0 -> `if band:` skipped: pre-band targets
    heldW = SY.run(inp, V1).attrs["weights"]
    assert (SY._apply_band(target, SY.DESIGN["no_trade_band"]) - heldW).abs().max().max() == 0.0
    months = inp["months"]
    A = pd.concat([1 / vol[b] for b in ("fx", "bond")], axis=1)[target.columns]
    B = pd.DataFrame(np.nan, index=months, columns=target.columns)
    for b in ("fx", "bond"):
        cols = inp[b]["ret"].columns
        ratio = (Wb[b][cols].abs() / (1 / vol[b][cols])).where(Wb[b][cols] != 0)
        kb = ratio.median(axis=1)
        assert float((ratio.sub(kb, axis=0)).abs().max().max()) < 1e-9
        for c in cols:
            B[c] = kb
    allW = pd.concat([Wb[b] * 0.5 for b in ("fx", "bond")], axis=1)[target.columns]
    ratio = (target / allW).where(allW != 0)
    C = ratio.median(axis=1)
    assert float(ratio.sub(C, axis=0).abs().max().max()) < 1e-9
    # split c into the portfolio vol scaler and the leverage-cap factor (replicating SY.run lines 245-256)
    allR = pd.concat([inp[b]["ret"] for b in ("fx", "bond")], axis=1)[target.columns]
    scale = pd.Series(np.nan, index=months)
    for t in months:
        hist = allR.loc[:t].iloc[-SY.DESIGN["vol_lookback_months"]:].fillna(0.0)
        pv = (hist @ allW.loc[t]).std() * np.sqrt(12) if len(hist) >= SY.DESIGN["vol_min_months"] else np.nan
        scale[t] = SY.DESIGN["portfolio_target_vol"] / pv if pv and pv > 0 else 0.0
    capf = C / scale                      # target = sign x a x b x 0.5 x scale x capf; C = scale x capf
    capf = capf.where(C.notna())
    return target, heldW, A, B, C, scale, capf, Wb


def stage_turnover():
    check_frozen()
    inp = inputs()
    target, heldW, A, B, C, scale, capf, Wb = _components(inp)
    months = inp["months"]
    cols = list(target.columns)
    # decision-dated trades on held weights; LMDI (log-mean Divisia) split of same-sign resizes
    rec = []
    last_trade = {k: None for k in cols}
    for i, t in enumerate(months):
        for k in cols:
            new = heldW.at[t, k]
            prev = heldW.iat[i - 1, cols.index(k)] if i > 0 else 0.0
            d = new - prev
            if d == 0:
                continue
            row = {"decision_month": t, "instrument": k, "traded": abs(d)}
            if np.sign(new) != np.sign(prev):
                row["kind"] = ("entry" if prev == 0 else "exit" if new == 0 else "flip")
                row.update({"signal": abs(d), "inst_vol": 0.0, "book_scale": 0.0, "port_scale": 0.0, "lev_cap": 0.0})
            else:
                t0 = last_trade[k]
                L = d / (np.log(abs(new)) - np.log(abs(prev)))
                dl = {"inst_vol": np.log(A.at[t, k] / A.at[t0, k]), "book_scale": np.log(B.at[t, k] / B.at[t0, k]),
                      "port_scale": np.log(scale[t] / scale[t0]), "lev_cap": np.log(capf[t] / capf[t0])}
                tot = sum(dl.values())
                assert abs(tot - (np.log(abs(new)) - np.log(abs(prev)))) < 1e-8, (t, k)
                row["kind"] = "resize"
                row["signal"] = 0.0
                for key, v in dl.items():
                    row[key] = float(L * v * np.sign(d))   # signed shares summing to |d|
            last_trade[k] = t
            rec.append(row)
    tr = pd.DataFrame(rec)
    tr["book"] = np.where(tr.instrument.isin(FX), "FX", "bonds")
    # which signal moved: for entry / exit / flip trades, split |trade| by each signal's absolute change in its
    # share of the composite, c_k = z_k / K (K = signals available), between t-1 and t: share_k = |dc_k| / sum |dc|.
    # Ranks are cross-sectional, so other instruments' moves also matter; this is an approximation.
    zc = {}
    for bk in ("fx", "bond"):
        sig = SY.signals(inp[bk])
        K = sum(sig[g].notna().astype(float) for g in V1).replace(0, np.nan)
        for g in V1:
            zc.setdefault(g, []).append(sig[g].fillna(0.0) / K)
    zc = {g: pd.concat(v, axis=1)[cols] for g, v in zc.items()}
    for g in V1:
        tr[f"sig_{g}"] = 0.0
    for j, row in tr.iterrows():
        if row["kind"] == "resize":
            continue
        t, k = row["decision_month"], row["instrument"]
        dz = {g: float(zc[g].at[t, k] - zc[g].at[t - 1, k]) if t - 1 in zc[g].index else np.nan for g in V1}
        tot = sum(abs(v) for v in dz.values())
        if not np.isfinite(tot) or abs(tot) < 1e-12:
            continue
        for g in V1:
            tr.at[j, f"sig_{g}"] = row["traded"] * abs(dz[g]) / tot
    # date the trades like v1.0's costs (month the trade starts earning) to match the step-1 totals
    tr["cost_month"] = [m + LAG["fx" if k in FX else "bond"] for m, k in zip(tr.decision_month, tr.instrument)]
    sel = tr[(tr.cost_month >= TEST[0]) & (tr.cost_month <= TEST[1])]
    yrs = len(pd.period_range(TEST[0], TEST[1], freq="M")) / 12
    comp = ["signal", "inst_vol", "book_scale", "port_scale", "lev_cap"]
    # check against step-1 total
    res = SY.run(inp, V1)
    tot_ref = float(_sl(traded(heldW, res.index), TEST).sum().sum() / yrs)
    tot = float(sel.traded.sum() / yrs)
    assert abs(tot - tot_ref) < 1e-9, (tot, tot_ref)
    by_src = (sel[comp].sum() / yrs).rename("turnover_x_pa").to_frame()
    by_src["share_%"] = 100 * by_src["turnover_x_pa"] / tot
    by_kind = sel.groupby("kind").agg(trades=("traded", "size"), turnover=("traded", "sum"))
    by_kind["turnover_x_pa"] = by_kind.pop("turnover") / yrs
    by_kind["share_%"] = 100 * by_kind["turnover_x_pa"] / tot
    by_book = sel.groupby("book")[comp + ["traded"]].sum() / yrs
    sigcols = [f"sig_{g}" for g in V1]
    by_signal = (sel.groupby("book")[sigcols + ["signal"]].sum() / yrs)
    by_signal.loc["total"] = by_signal.sum()
    by_signal["unattributed"] = by_signal["signal"] - by_signal[sigcols].sum(axis=1)
    # band: turnover of the pre-band targets vs executed, same dating
    tt = _sl(traded(target, res.index), TEST)
    th = _sl(traded(heldW, res.index), TEST)
    band = pd.DataFrame({"target_turnover_x_pa": tt.sum() / yrs, "executed_turnover_x_pa": th.sum() / yrs})
    band["suppressed_x_pa"] = band.target_turnover_x_pa - band.executed_turnover_x_pa
    # target-path decomposition (selection vs resize), same rule
    rec2 = {"selection": 0.0, "resize": 0.0}
    for k in cols:
        lag = LAG["fx" if k in FX else "bond"]
        x = target[k]
        d = x.diff().abs().shift(lag).reindex(res.index).fillna(0.0)
        flip = (np.sign(x) != np.sign(x.shift(1))).shift(lag).reindex(res.index).fillna(False).astype(bool)
        d, flip = _sl(d, TEST), _sl(flip, TEST)
        rec2["selection"] += float(d[flip].sum() / yrs)
        rec2["resize"] += float(d[~flip].sum() / yrs)
    # months held under the band, per instrument
    inband = (np.sign(target) == np.sign(heldW)) & (target != 0) & (target != heldW)
    held_months = pd.Series({k: int(_sl(inband[k].shift(LAG["fx" if k in FX else "bond"]).reindex(res.index)
                                        .fillna(False).astype(bool), TEST).sum()) for k in cols})
    # per instrument
    inst = sel.groupby("instrument").agg(trades=("traded", "size"), turnover=("traded", "sum"),
                                         signal=("signal", "sum"), resize_vol=("inst_vol", "sum"),
                                         resize_book=("book_scale", "sum"), resize_port=("port_scale", "sum"),
                                         resize_cap=("lev_cap", "sum"))
    inst = inst / [1, yrs, yrs, yrs, yrs, yrs, yrs]
    inst = inst.rename(columns={"turnover": "turnover_x_pa"})
    inst["share_%"] = 100 * inst.turnover_x_pa / tot
    inst["signal_share_%"] = 100 * inst.signal / inst.turnover_x_pa
    inst["months_band_held"] = held_months.reindex(inst.index)
    inst["band_suppressed_x_pa"] = band["suppressed_x_pa"].reindex(inst.index)
    ho = _sl(held(heldW, res.index), TEST).mean()
    inst["avg_gross_position_x"] = ho.reindex(inst.index)
    inst["turnover_per_unit_held"] = inst.turnover_x_pa / inst.avg_gross_position_x
    inst["sign_changes_pa"] = (sel[sel.kind != "resize"].groupby("instrument").size() / yrs).reindex(inst.index).fillna(0)
    inst = inst.sort_values("turnover_x_pa", ascending=False)
    # annual
    sel = sel.assign(year=[m.year for m in sel.cost_month])
    yr = sel.groupby("year")[comp + ["traded"]].sum()
    nmon = sel.groupby("year").cost_month.nunique()
    yr = yr.div(nmon / 12, axis=0)
    OUT.mkdir(parents=True, exist_ok=True)
    by_src.to_csv(OUT / "step4_by_source.csv", float_format="%.4f")
    by_kind.to_csv(OUT / "step4_by_kind.csv", float_format="%.4f")
    by_book.to_csv(OUT / "step4_by_book.csv", float_format="%.4f")
    by_signal.to_csv(OUT / "step4_selection_by_signal.csv", float_format="%.4f")
    inst.to_csv(OUT / "step4_by_instrument.csv", float_format="%.4f")
    yr.to_csv(OUT / "step4_by_year.csv", float_format="%.4f")
    band.to_csv(OUT / "step4_band.csv", float_format="%.4f")
    meta = {"total_turnover_x_pa": tot, "target_turnover_x_pa": float(band.target_turnover_x_pa.sum()),
            "executed_turnover_x_pa": float(band.executed_turnover_x_pa.sum()),
            "target_path_selection_x_pa": rec2["selection"], "target_path_resize_x_pa": rec2["resize"],
            "leverage_cap_binding_months_test": int(_sl((capf < 1 - 1e-12), TEST).sum()),
            "months_test": int(len(_sl(capf, TEST)))}
    (OUT / "step4_meta.json").write_text(json.dumps(meta, indent=1))
    print(by_src.round(3).to_string()); print(by_kind.round(3).to_string()); print(by_book.round(3).to_string())
    print(by_signal.round(3).to_string())
    print(inst.round(3).to_string()); print(yr.round(3).to_string()); print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"model": stage_model, "sensitivity": stage_sensitivity, "turnover": stage_turnover}.get(
        cmd, lambda: sys.exit(__doc__))()
