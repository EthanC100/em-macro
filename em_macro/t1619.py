"""Risk batch T16-T19 runner: pre-registered comparison of four single changes with frozen v1.0.

    python -m em_macro.t1619 run        # -> results/T16-T19/*.csv, *.json, RUN.json
    python -m em_macro.t1619 report     # -> results/T16-T19_risk_batch.md from the saved tables

Pre-registration: docs/prereg/T16-T19_risk_batch.md (commit 4c10856).  v1.0 numbers come from the frozen
em_macro/systematic.py (tag v1.0-frozen, commit 7886867), imported and never modified.  Statistics re-use
em_macro/t01.py (metrics, ES, DSR rows, resampling) so that every trial report is comparable.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import holdout as HO
from . import systematic as SY
from . import t01 as T01
from . import t16_crash as T16
from . import t17_factorcap as T17
from . import t18_rebal as T18
from . import t19_vol as T19
from . import tstrend as TS
from .config import RESULTS, ROOT

OUT = RESULTS / "T16-T19"
REPORT = RESULTS / "T16-T19_risk_batch.md"
PREREG = "docs/prereg/T16-T19_risk_batch.md"
SEED = 20261103
TEST = T01.TEST
PERIODS = T01.PERIODS
TRIALS = ["T16", "T17", "T18", "T19"]
V1 = ["carry", "trend", "value"]
MARGIN = 0.05                 # Sharpe non-inferiority margin
RISK_CUT = 0.90               # at least 10% better
ALPHA = 0.10
N_SPEC_V1, N_SPEC_TRIAL = 7, 13       # spec convention: 7 + T01 + T02 + the four of this family
N_LEDGER_V1, N_LEDGER_TRIAL = 14, 18  # ledger convention (14 trial groups before this family)
TURNOVER_CUT = 0.75
UNIVERSES = ("all", "half B", "half A")
COSTS = (1.0, 2.0)
_net, sharpe, max_drawdown, expected_shortfall = T01._net, T01.sharpe, T01.max_drawdown, T01.expected_shortfall


# ============================================================ statistics
def bootstrap_noninferiority(a: pd.Series, b: pd.Series, margin: float = MARGIN, B: int = 10_000, L: int = 6,
                             seed: int = SEED) -> dict:
    """Paired circular block bootstrap of dSR = SR(a) - SR(b).  One-sided p for H1: dSR > -margin from the
    bootstrap distribution centred on the null boundary: p = (1 + #{dSR* - dSR_hat >= dSR_hat + margin}) / (B+1)."""
    x = np.column_stack([np.asarray(a, float), np.asarray(b, float)])
    T = len(x)
    d_hat = sharpe(x[:, 0]) - sharpe(x[:, 1])
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for i in range(B):
        s = x[T01.circular_block_indices(T, L, rng)]
        d[i] = sharpe(s[:, 0]) - sharpe(s[:, 1])
    p = (1 + np.sum(d - d_hat >= d_hat + margin)) / (B + 1)
    p0 = (1 + np.sum(d - d_hat >= d_hat)) / (B + 1)
    return {"delta_sr": float(d_hat), "margin": margin, "p_one_sided": float(p), "p_one_sided_margin0": float(p0),
            "boot_mean": float(d.mean()), "boot_sd": float(d.std(ddof=1)), "boot_q05": float(np.quantile(d, 0.05)),
            "boot_q95": float(np.quantile(d, 0.95)), "B": B, "block": L, "seed": seed}


def holm(p: dict[str, float]) -> dict[str, float]:
    """Holm (1979) step-down adjusted p-values."""
    items = sorted(p.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, v) in enumerate(items):
        running = max(running, min(1.0, (m - i) * v))
        out[k] = running
    return out


def by_year(res: pd.DataFrame, a=TEST[0], b=TEST[1]) -> pd.DataFrame:
    r = _net(res).loc[a:b]
    to = T01.turnover(res).loc[a:b]
    rows = []
    for y, x in r.groupby(r.index.year):
        rows.append({"year": int(y), "months": len(x), "return_%": 100 * ((1 + x).prod() - 1),
                     "vol_%": 100 * x.std() * np.sqrt(12), "sharpe": sharpe(x), "max_drawdown_%": 100 * max_drawdown(x),
                     "turnover_x": float(to.loc[x.index].sum())})
    return pd.DataFrame(rows)


def _sha(path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Period, pd.Timestamp)):
        return str(o)
    return str(o)


# ============================================================ run
def stage_run():
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inp1 = SY.build_inputs()
    repro = T01.reproduce_v1(inp1)
    print("v1.0 reproduction:", repro)
    if not (repro["test"]["exact"] and repro["fit"]["exact"]):
        sys.exit("v1.0 does not reproduce exactly on these inputs; nothing run")
    months = inp1["months"]
    halfB, halfA = HO.instruments("B"), HO.instruments("A")
    uni_ins = {"all": None, "half B": halfB, "half A": halfA}
    factors = T17.factor_series(inp1)

    # ---- T16 crash model: features, labels and walk-forward per universe (independent of costs)
    sub = {u: (inp1 if ins is None else TS.subset(inp1, ins)) for u, ins in uni_ins.items()}
    feats = {u: T16.features(sub[u]["fx"], months) for u in UNIVERSES}
    labs = {u: T16.labels(sub[u]["fx"]["ret"]) for u in UNIVERSES}
    fxcols = {u: list(sub[u]["fx"]["ret"].columns) for u in UNIVERSES}
    wf = {}
    wf["all"] = T16.walk_forward(feats["all"], labs["all"], fxcols["all"], fxcols["all"])
    wf["half A"] = T16.walk_forward(feats["half A"], labs["half A"], fxcols["half A"], fxcols["half A"])
    wf["half B"] = T16.walk_forward(pd.concat([feats["half A"], feats["half B"]]),
                                    pd.concat([labs["half A"], labs["half B"]], axis=1),
                                    fxcols["half A"], fxcols["half B"])
    t16_diag = {}
    for u in UNIVERSES:
        sc = wf[u]["scale"]
        test_sc = sc.loc[TEST[0]:TEST[1]]
        t16_diag[u] = {"years": wf[u]["years"],
                       "skill_test": T16.skill(wf[u]["rows"], TEST[0], TEST[1]),
                       "skill_context_2010_2019": T16.skill(wf[u]["rows"], pd.Period("2010-01", "M"), pd.Period("2019-12", "M")),
                       "share_scaled_below_1_test": float((test_sc < 1 - 1e-12).mean().mean()),
                       "mean_scale_test": float(test_sc.mean().mean()),
                       "share_scaled_to_0_test": float((test_sc <= 1e-12).mean().mean()),
                       "features_imputed_cells_total": int(feats[u].isna().sum().sum()),
                       "features_rows": int(len(feats[u])), "labelled_obs": int(labs[u].notna().sum().sum()),
                       "crash_rate_all_labels": float(labs[u].stack().mean())}
        wf[u]["scale"].reset_index().rename(columns={"index": "month"}).assign(month=lambda d: d["month"].astype(str)) \
            .to_csv(OUT / f"t16_scale_{u.replace(' ', '')}.csv", index=False, float_format="%.6f")
        wf[u]["p"].reset_index().rename(columns={"index": "month"}).assign(month=lambda d: d["month"].astype(str)) \
            .to_csv(OUT / f"t16_prob_{u.replace(' ', '')}.csv", index=False, float_format="%.6f")
        feats[u].reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(
            OUT / f"t16_features_{u.replace(' ', '')}.csv", index=False, float_format="%.6f")
    (OUT / "t16_model.json").write_text(json.dumps(t16_diag, indent=1, default=_json))
    print("T16 walk-forward done")

    # ---- strategy runs
    runs, logs = {}, {}
    for cm in COSTS:
        for u in UNIVERSES:
            x = sub[u] if cm == 1.0 else TS.with_costs(sub[u], cm)
            runs[(u, cm, "v1.0")] = SY.run(x, V1)
            runs[(u, cm, "T16")] = T16.run(x, wf[u]["scale"])
            runs[(u, cm, "T17")], logs[(u, cm, "T17")] = T17.run(x, factors)
            runs[(u, cm, "T18")], logs[(u, cm, "T18")] = T18.run(x)
            runs[(u, cm, "T19")] = T19.run(x)
            if u == "all":
                runs[(u, cm, "v1.0 no band (context)")] = SY.run(x, V1, band=0)
            print("done", u, cm)
    # the T18 machinery with v1.0's band must equal v1.0 (identity check of the P&L path)
    chk = T18.pnl(inp1, SY._apply_band(T18.capped_targets(inp1), SY.DESIGN["no_trade_band"]))
    assert (chk["net"] - runs[("all", 1.0, "v1.0")]["net"]).abs().max() < 1e-12
    # T19 with v1.0's own estimator must equal v1.0
    chk19 = T19.run(inp1, vol_fn=T19.v1_vol_fn)
    assert (chk19["net"] - runs[("all", 1.0, "v1.0")]["net"]).abs().max() < 1e-12

    # ---- performance table
    rows = []
    for (u, cm, strat), res in runs.items():
        for pname, per in PERIODS.items():
            rows.append({"universe": u, "costs": f"{cm:g}x", "strategy": strat, "period": pname, **T01.metrics(res, per)})
    perf = pd.DataFrame(rows)
    perf.to_csv(OUT / "performance.csv", index=False, float_format="%.4f")

    # ---- monthly net returns, by year, worst months
    mon = pd.DataFrame({f"{u}|{cm:g}x|{s}": _net(r) for (u, cm, s), r in runs.items()})
    mon.index.name = "month"
    mon.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(OUT / "monthly_net.csv", index=False,
                                                                           float_format="%.6f")
    yr = []
    for cm in COSTS:
        for s in ["v1.0", *TRIALS]:
            t = by_year(runs[("all", cm, s)])
            t.insert(0, "strategy", s)
            t.insert(0, "costs", f"{cm:g}x")
            yr.append(t)
    pd.concat(yr).to_csv(OUT / "by_year_2020_2026.csv", index=False, float_format="%.4f")
    v1 = _net(runs[("all", 1.0, "v1.0")]).loc[TEST[0]:TEST[1]]
    worst = v1.nsmallest(5).index
    wm = []
    for m in worst:
        row = {"month": str(m)}
        for cm in COSTS:
            for s in ["v1.0", *TRIALS]:
                row[f"{s} {cm:g}x %"] = 100 * float(_net(runs[("all", cm, s)]).get(m, np.nan))
        wm.append(row)
    pd.DataFrame(wm).to_csv(OUT / "worst_months.csv", index=False, float_format="%.4f")

    # ---- criteria
    crit = {}
    for cm in COSTS:
        tag = f"{cm:g}x"
        v1 = _net(runs[("all", cm, "v1.0")]).loc[TEST[0]:TEST[1]]
        vB = _net(runs[("half B", cm, "v1.0")]).loc[TEST[0]:TEST[1]]
        d_v1 = {"spec": T01.dsr_row(v1, N_SPEC_V1), "ledger": T01.dsr_row(v1, N_LEDGER_V1)}
        es_v, dd_v = expected_shortfall(v1), max_drawdown(v1)
        es_vB, dd_vB = expected_shortfall(vB), max_drawdown(vB)
        to_v = float(T01.turnover(runs[("all", cm, "v1.0")]).loc[TEST[0]:TEST[1]].mean() * 12)
        per_trial = {}
        for tr in TRIALS:
            t = _net(runs[("all", cm, tr)]).loc[TEST[0]:TEST[1]]
            tB = _net(runs[("half B", cm, tr)]).loc[TEST[0]:TEST[1]]
            assert len(v1) == len(t) == 81 and (v1.index == t.index).all()
            bs = bootstrap_noninferiority(t, v1)
            es_t, dd_t = expected_shortfall(t), max_drawdown(t)
            es_tB, dd_tB = expected_shortfall(tB), max_drawdown(tB)
            dd_ratio, es_ratio = abs(dd_t) / abs(dd_v), es_t / es_v
            dd_ratioB, es_ratioB = abs(dd_tB) / abs(dd_vB), es_tB / es_vB
            passed_metrics = [m for m, r in (("MaxDD", dd_ratio), ("ES97.5", es_ratio)) if r <= RISK_CUT]
            holdB = {"MaxDD": dd_ratioB <= RISK_CUT, "ES97.5": es_ratioB <= RISK_CUT}
            to_t = float(T01.turnover(runs[("all", cm, tr)]).loc[TEST[0]:TEST[1]].mean() * 12)
            d_t = {"spec": T01.dsr_row(t, N_SPEC_TRIAL), "ledger": T01.dsr_row(t, N_LEDGER_TRIAL)}
            per_trial[tr] = {
                "sr": sharpe(t), "sr_v1": sharpe(v1), "dsr_point": sharpe(t) - sharpe(v1), "bootstrap": bs,
                "dd": dd_t, "dd_v1": dd_v, "es": es_t, "es_v1": es_v, "dd_ratio": dd_ratio, "es_ratio": es_ratio,
                "risk_pass": len(passed_metrics) > 0, "risk_metrics_passed": passed_metrics,
                "srB": sharpe(tB), "srB_v1": sharpe(vB), "ddB": dd_tB, "ddB_v1": dd_vB, "esB": es_tB, "esB_v1": es_vB,
                "dd_ratioB": dd_ratioB, "es_ratioB": es_ratioB,
                "riskB_pass": any(holdB[m] for m in passed_metrics),
                "srB_pass": sharpe(tB) >= sharpe(vB) - MARGIN,
                "dsr": d_t, "turnover": to_t, "turnover_v1": to_v, "turnover_ratio": to_t / to_v}
        praw = {tr: per_trial[tr]["bootstrap"]["p_one_sided"] for tr in TRIALS}
        padj = holm(praw)
        tables = {}
        for tr in TRIALS:
            x = per_trial[tr]
            c1 = bool(x["risk_pass"] and x["dsr_point"] >= -MARGIN and padj[tr] < ALPHA)
            c2 = bool(x["riskB_pass"] and x["srB_pass"])
            c3 = bool(x["dsr"]["spec"]["DSR_noise"] >= d_v1["spec"]["DSR_noise"])
            c4 = bool(x["turnover_ratio"] <= TURNOVER_CUT) if tr == "T18" else None
            rows = [
                {"#": 1, "criterion": "2020-01..2026-09: |MaxDD| or ES97.5 <= 0.90 x v1.0, dSR >= -0.05, Holm-adjusted bootstrap p < 0.10",
                 "trial": f"SR {x['sr']:.3f}, MaxDD {100 * x['dd']:.2f}%, ES {100 * x['es']:.2f}%",
                 "v1.0": f"SR {x['sr_v1']:.3f}, MaxDD {100 * x['dd_v1']:.2f}%, ES {100 * x['es_v1']:.2f}%",
                 "statistic": f"DD ratio {x['dd_ratio']:.3f}; ES ratio {x['es_ratio']:.3f}; dSR {x['dsr_point']:+.3f}; "
                              f"p raw {praw[tr]:.4f}, Holm {padj[tr]:.4f}",
                 "pass": c1},
                {"#": 2, "criterion": "holdout half B: the same risk metric <= 0.90 x v1.0 and SR >= v1.0 - 0.05",
                 "trial": f"SR {x['srB']:.3f}, MaxDD {100 * x['ddB']:.2f}%, ES {100 * x['esB']:.2f}%",
                 "v1.0": f"SR {x['srB_v1']:.3f}, MaxDD {100 * x['ddB_v1']:.2f}%, ES {100 * x['esB_v1']:.2f}%",
                 "statistic": f"DD ratio {x['dd_ratioB']:.3f}; ES ratio {x['es_ratioB']:.3f}; dSR {x['srB'] - x['srB_v1']:+.3f}; "
                              f"metric(s) from (1): {', '.join(x['risk_metrics_passed']) or 'none'}",
                 "pass": c2},
                {"#": 3, "criterion": "DSR (noise-only null) at N = 13 >= DSR of v1.0 at N = 7",
                 "trial": f"DSR {x['dsr']['spec']['DSR_noise']:.3f} (N 13)",
                 "v1.0": f"DSR {d_v1['spec']['DSR_noise']:.3f} (N 7)",
                 "statistic": f"difference {x['dsr']['spec']['DSR_noise'] - d_v1['spec']['DSR_noise']:+.3f}",
                 "pass": c3},
            ]
            if tr == "T18":
                rows.append({"#": 4, "criterion": "T18 only: turnover <= 0.75 x v1.0's (2020-01..2026-09, all instruments)",
                             "trial": f"{x['turnover']:.2f}x/yr", "v1.0": f"{x['turnover_v1']:.2f}x/yr",
                             "statistic": f"ratio {x['turnover_ratio']:.3f}", "pass": c4})
            overall = all(r["pass"] for r in rows)
            tables[tr] = {"criteria": rows, "overall_pass": overall, "n_pass": sum(r["pass"] for r in rows), "n": len(rows)}
            pd.DataFrame(rows).to_csv(OUT / f"pass_fail_{tr}_{tag}.csv", index=False)
        crit[tag] = {"per_trial": per_trial, "p_raw": praw, "p_holm": padj, "tables": tables, "dsr_v1": d_v1,
                     "worst_months_v1": [str(m) for m in worst]}
        pd.DataFrame({"trial": TRIALS, "p_raw": [praw[t] for t in TRIALS], "p_holm": [padj[t] for t in TRIALS],
                      "delta_sr": [per_trial[t]["dsr_point"] for t in TRIALS],
                      "boot_sd": [per_trial[t]["bootstrap"]["boot_sd"] for t in TRIALS]}).to_csv(
            OUT / f"holm_{tag}.csv", index=False, float_format="%.6f")
    (OUT / "criteria.json").write_text(json.dumps(crit, indent=1, default=_json))

    # ---- trial diagnostics
    diag = {}
    # T17: cap log and version-B shares of v1.0 and T17 positions (all, 1x)
    for (u, cm, s), lg in logs.items():
        if s == "T17":
            lg.to_csv(OUT / f"t17_caplog_{u.replace(' ', '')}_{cm:g}x.csv", index=False, float_format="%.6f")
        if s == "T18":
            lg.to_csv(OUT / f"t18_tradelog_{u.replace(' ', '')}_{cm:g}x.csv", index=False, float_format="%.6f")
    lg = logs[("all", 1.0, "T17")]
    lt = lg[lg["modelled"] == True].copy()
    lt["month_p"] = pd.PeriodIndex(lt["month"], freq="M")
    ltt = lt[(lt["month_p"] >= TEST[0]) & (lt["month_p"] <= TEST[1])]
    sh_v1 = T17.shares_of_held(runs[("all", 1.0, "v1.0")].attrs["weights"], inp1, factors)
    sh_t17 = T17.shares_of_held(runs[("all", 1.0, "T17")].attrs["weights"], inp1, factors)
    sh_v1.to_csv(OUT / "t17_shares_v1.csv", index=False, float_format="%.6f")
    sh_t17.to_csv(OUT / "t17_shares_T17.csv", index=False, float_format="%.6f")
    shv = sh_v1.assign(m=lambda d: pd.PeriodIndex(d["month"], freq="M")).query("m >= @TEST[0] and m <= @TEST[1]")
    sht = sh_t17.assign(m=lambda d: pd.PeriodIndex(d["month"], freq="M")).query("m >= @TEST[0] and m <= @TEST[1]")
    diag["T17"] = {"decision_months_test": int(len(ltt)), "months_adjusted_test": int(ltt["adjusted"].sum()),
                   "months_fallback_test": int(ltt["fallback"].sum()),
                   "months_usd_breached_test": int((ltt["usd_share_before"] > T17.CAPS["USD"] + T17.TOL).sum()),
                   "months_em_breached_test": int((ltt["em_share_before"] > T17.CAPS["EM"] + T17.TOL).sum()),
                   "max_usd_share_before_test": float(ltt["usd_share_before"].max()),
                   "max_em_share_before_test": float(ltt["em_share_before"].max()),
                   "mean_positions_opened_when_adjusted": float(ltt.loc[ltt["adjusted"], "positions_opened"].mean()) if ltt["adjusted"].any() else 0.0,
                   "mean_opened_gross_when_adjusted": float(ltt.loc[ltt["adjusted"], "opened_gross"].mean()) if ltt["adjusted"].any() else 0.0,
                   "mean_distance_when_adjusted": float(ltt.loc[ltt["adjusted"], "distance"].mean()) if ltt["adjusted"].any() else 0.0,
                   "months_adjusted_all": int(lt["adjusted"].sum()), "decision_months_all": int(len(lt)),
                   "held_shares_test": {"v1.0": {"usd_mean": float(shv["usd_share"].mean()), "usd_max": float(shv["usd_share"].max()),
                                                 "em_mean": float(shv["em_share"].mean()), "em_max": float(shv["em_share"].max()),
                                                 "usd_em_mean": float(shv["usd_em_share"].mean()), "usd_em_max": float(shv["usd_em_share"].max())},
                                        "T17": {"usd_mean": float(sht["usd_share"].mean()), "usd_max": float(sht["usd_share"].max()),
                                                "em_mean": float(sht["em_share"].mean()), "em_max": float(sht["em_share"].max()),
                                                "usd_em_mean": float(sht["usd_em_share"].mean()), "usd_em_max": float(sht["usd_em_share"].max())}}}
    # T18: turnover by book and band statistics (all, 1x)
    lg = logs[("all", 1.0, "T18")].copy()
    lg["month_p"] = pd.PeriodIndex(lg["month"], freq="M")
    lgt = lg[(lg["month_p"] >= TEST[0] - 2) & (lg["month_p"] <= TEST[1])]
    res18, resv1 = runs[("all", 1.0, "T18")], runs[("all", 1.0, "v1.0")]
    W18, Wv1 = res18.attrs["weights"], resv1.attrs["weights"]
    book = T18.book_of(inp1)
    tob = {}
    for b in ("fx", "bond"):
        cols = [c for c in W18.columns if book[c] == b]
        lagb = T18.LAG[b]
        tob[b] = {"T18": float(W18[cols].diff().abs().sum(axis=1).shift(lagb).loc[TEST[0]:TEST[1]].mean() * 12),
                  "v1.0": float(Wv1[cols].diff().abs().sum(axis=1).shift(lagb).loc[TEST[0]:TEST[1]].mean() * 12)}
    tgt18 = T18.capped_targets(inp1)
    ratio = (W18.abs().sum(axis=1) / tgt18.abs().sum(axis=1).replace(0, np.nan)).loc[TEST[0]:TEST[1]]
    diag["T18"] = {"turnover_by_book_test": tob,
                   "proposed_trades_test": int(len(lgt)), "trades_suppressed_by_band_test": int((~lgt["traded"]).sum()),
                   "share_suppressed_test": float((~lgt["traded"]).mean()) if len(lgt) else np.nan,
                   "residual_closes_test": int(((lgt["target"] == 0) & lgt["traded"] & (lgt["trade_risk"] <= T18.BAND_RISK * lgt["budget"])).sum()),
                   "mean_gross_held_over_target_test": float(ratio.mean()),
                   "avg_gross_leverage_test": {"T18": float(res18["gross_leverage"].loc[TEST[0]:TEST[1]].mean()),
                                               "v1.0": float(resv1["gross_leverage"].loc[TEST[0]:TEST[1]].mean())}}
    # T19: floor binding and realised vol by year
    R_all = TS.all_returns(inp1)
    fb = T19.floor_binds(R_all).loc[TEST[0]:TEST[1]]
    sig_v1 = SY._vol(R_all).loc[TEST[0]:TEST[1]]
    sig_19 = T19.vol_est(R_all).loc[TEST[0]:TEST[1]]
    r19, rv1 = _net(runs[("all", 1.0, "T19")]).loc[TEST[0]:TEST[1]], _net(runs[("all", 1.0, "v1.0")]).loc[TEST[0]:TEST[1]]
    diag["T19"] = {"share_instrument_months_floor_binds_test": float(fb.where(sig_19.notna()).stack().mean()),
                   "mean_ratio_T19_vol_to_v1_vol_test": float((sig_19 / sig_v1).stack().mean()),
                   "realised_vol_by_year": {str(y): {"T19": float(x.std() * np.sqrt(12) * 100), "v1.0": float(rv1.loc[x.index].std() * np.sqrt(12) * 100)}
                                            for y, x in r19.groupby(r19.index.year)},
                   "avg_gross_leverage_test": {"T19": float(runs[("all", 1.0, "T19")]["gross_leverage"].loc[TEST[0]:TEST[1]].mean()),
                                               "v1.0": float(resv1["gross_leverage"].loc[TEST[0]:TEST[1]].mean())}}
    diag["T16"] = t16_diag
    (OUT / "diagnostics.json").write_text(json.dumps(diag, indent=1, default=_json))

    files = ["em_macro/systematic.py", "results/systematic/fit/frozen_design.json", "em_macro/t16_crash.py",
             "em_macro/t17_factorcap.py", "em_macro/t18_rebal.py", "em_macro/t19_vol.py", "em_macro/t1619.py",
             "em_macro/t01.py", "em_macro/tstrend.py", "em_macro/holdout.py", PREREG,
             "data/processed/daily_panel.csv", "data/processed/country_month_panel.csv",
             "data/processed/risk_model_input.csv", "data/events/elections.csv"]
    (OUT / "RUN.json").write_text(json.dumps({
        "run_started_utc": started, "run_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_run": _git_head(), "pandas": pd.__version__, "numpy": np.__version__,
        "last_month": str(months[-1]), "v1_reproduction": repro, "decision_costs": "1x",
        "overall_pass_1x": {tr: crit["1x"]["tables"][tr]["overall_pass"] for tr in TRIALS},
        "sha256": {f: _sha(f) for f in files}}, indent=1))
    for tr in TRIALS:
        print(tr, "OVERALL (1x):", "PASS" if crit["1x"]["tables"][tr]["overall_pass"] else "FAIL")
        print(pd.DataFrame(crit["1x"]["tables"][tr]["criteria"]).to_string())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        stage_run()
    elif cmd == "report":
        from . import t1619_report
        t1619_report.write()
    else:
        sys.exit(__doc__)
