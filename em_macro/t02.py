"""Trial T02 runner: pre-registered comparison of T02 (economic momentum as a fourth FX signal) with v1.0.

    python -m em_macro.t02 run        # -> results/T02/*.csv, results/T02/criteria.json, results/T02/RUN.json
    python -m em_macro.t02 report     # -> results/T02_econ_momentum.md from the saved tables

Pre-registration: docs/prereg/T02_econ_momentum.md (commit 0b40b2a).  v1.0 numbers come from the frozen
em_macro/systematic.py (tag v1.0-frozen, commit 7886867), which is imported, never modified.  The ECONMOM
score is injected into the FX book's signal dictionary; the frozen book_weights, run and evaluate are
called unchanged.  For the bond book the injected frame is all-missing, so its composite is v1.0's
mean(carry, trend, value) exactly (asserted below).
"""
from __future__ import annotations

import contextlib
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import econmom as EM
from . import holdout as HO
from . import systematic as SY
from . import t01 as T1
from . import tstrend as TS
from .config import RESULTS

OUT = RESULTS / "T02"
SEED = 20261103
TEST = (pd.Period("2020-01", "M"), pd.Period("2026-09", "M"))
INSAMPLE = (None, pd.Period("2019-12", "M"))
PERIODS = {"2020-01..2026-09 (test)": TEST, "2005-2019 (in-sample, context)": INSAMPLE}
V1 = ["carry", "trend", "value"]
T2 = ["carry", "trend", "value", "econmom"]
N_SPEC_V1, N_SPEC_T02, N_SPEC_V1_ALT = 7, 9, 8
N_LEDGER_V1, N_LEDGER_T02 = 11, 12
V1_DSR_N7_RECORDED = 0.619          # results/T01_ts_trend.md §5 (the pre-registered comparison value)
FX = list(SY.FX_INSTR)


# ============================================================ injection into the frozen machinery
_FROZEN_SIGNALS = SY.signals


def _signals_with_econmom(book: dict) -> dict:
    sig = _FROZEN_SIGNALS(book)
    if "econmom" in book:
        sig["econmom"] = SY._xs_z(book["econmom"].reindex(index=book["ret"].index, columns=book["ret"].columns))
    else:     # bond book: no economic-momentum signal; an all-missing frame leaves the mean of the others
        sig["econmom"] = pd.DataFrame(np.nan, index=book["ret"].index, columns=book["ret"].columns)
    return sig


@contextlib.contextmanager
def injected():
    SY.signals = _signals_with_econmom
    try:
        yield
    finally:
        SY.signals = _FROZEN_SIGNALS


def with_econmom(inp: dict, score: pd.DataFrame) -> dict:
    out = dict(inp)
    out["fx"] = {**inp["fx"], "econmom": score}
    return out


def run_t02(inp: dict, books=("fx", "bond")) -> pd.DataFrame:
    with injected():
        return SY.run(inp, T2, books)


def run_sleeve(inp: dict) -> pd.DataFrame:
    with injected():
        return SY.run(inp, ["econmom"], ("fx",))


# ============================================================ statistics
def nw_alpha(y: pd.Series, X: pd.DataFrame, lags: int = 3) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    m = sm.OLS(d["y"], sm.add_constant(d[X.columns])).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    out = {"n": int(m.nobs), "alpha_monthly_%": 100 * float(m.params["const"]),
           "alpha_ann_%": 1200 * float(m.params["const"]), "t_alpha": float(m.tvalues["const"]), "r2": float(m.rsquared)}
    for c in X.columns:
        out[f"beta_{c}"] = float(m.params[c])
        out[f"t_{c}"] = float(m.tvalues[c])
    return out


def year_stats(r: pd.Series) -> pd.DataFrame:
    rows = []
    for y, x in r.groupby(r.index.year):
        w = (1 + x).cumprod()
        rows.append({"year": int(y), "months": len(x), "return_%": 100 * (w.iloc[-1] - 1),
                     "vol_%": 100 * x.std() * np.sqrt(12), "sharpe": T1.sharpe(x),
                     "max_drawdown_%": 100 * float((w / w.cummax().clip(lower=1.0) - 1).min())})
    return pd.DataFrame(rows)


# ============================================================ run
def criteria(runs: dict, cm: float, tag_strat: str = "T02") -> dict:
    """The five pre-registered criteria for strategy `tag_strat` vs v1.0, at cost multiplier cm."""
    a, b = TEST
    v1 = T1._net(runs[("all", cm, "v1.0")]).loc[a:b]
    t2 = T1._net(runs[("all", cm, tag_strat)]).loc[a:b]
    assert len(v1) == len(t2) == 81 and (v1.index == t2.index).all()
    bs = T1.bootstrap_delta_sharpe(t2, v1, seed=SEED)
    vB = T1._net(runs[("half B", cm, "v1.0")]).loc[a:b]
    tB = T1._net(runs[("half B", cm, tag_strat)]).loc[a:b]
    d_v1 = {"spec N7": T1.dsr_row(v1, N_SPEC_V1), "spec N8": T1.dsr_row(v1, N_SPEC_V1_ALT),
            "ledger N11": T1.dsr_row(v1, N_LEDGER_V1)}
    d_t2 = {"spec N9": T1.dsr_row(t2, N_SPEC_T02), "ledger N12": T1.dsr_row(t2, N_LEDGER_T02)}
    es_v, es_t = T1.expected_shortfall(v1), T1.expected_shortfall(t2)
    dd_v, dd_t = T1.max_drawdown(v1), T1.max_drawdown(t2)
    sleeve_key = "econ momentum sleeve" if tag_strat == "T02" else "econ momentum sleeve (delayed 3m)"
    sl = T1._net(runs[("all", cm, sleeve_key)])
    X = pd.DataFrame({k: T1._net(runs[("all", cm, f"{k} sleeve (v1.0 {k} only)")]) for k in V1})
    reg = {p: nw_alpha(sl.loc[x:y], X.loc[x:y]) for p, (x, y) in PERIODS.items()}
    rt = reg["2020-01..2026-09 (test)"]
    dsr_ref = V1_DSR_N7_RECORDED
    c = [
        {"#": 1, "criterion": "2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10",
         "T02": f"SR {T1.sharpe(t2):.3f}", "v1.0": f"SR {T1.sharpe(v1):.3f}",
         "statistic": f"dSR {bs['delta_sr']:+.3f}, p = {bs['p_one_sided']:.4f}",
         "pass": bool(bs["delta_sr"] > 0 and bs["p_one_sided"] < 0.10)},
        {"#": 2, "criterion": "holdout half B, 2020-01..2026-09: dSR > 0 and |MaxDD| not worse",
         "T02": f"SR {T1.sharpe(tB):.3f}, MaxDD {100 * T1.max_drawdown(tB):.2f}%",
         "v1.0": f"SR {T1.sharpe(vB):.3f}, MaxDD {100 * T1.max_drawdown(vB):.2f}%",
         "statistic": f"dSR {T1.sharpe(tB) - T1.sharpe(vB):+.3f}; |DD| ratio "
                      f"{T1.max_drawdown(tB) / T1.max_drawdown(vB):.3f}",
         "pass": bool(T1.sharpe(tB) > T1.sharpe(vB) and abs(T1.max_drawdown(tB)) <= abs(T1.max_drawdown(vB)))},
        {"#": 3, "criterion": "2020-01..2026-09: |MaxDD| and ES97.5 each <= 1.10 x v1.0",
         "T02": f"MaxDD {100 * dd_t:.2f}%, ES {100 * es_t:.2f}%",
         "v1.0": f"MaxDD {100 * dd_v:.2f}%, ES {100 * es_v:.2f}%",
         "statistic": f"DD ratio {dd_t / dd_v:.3f}; ES ratio {es_t / es_v:.3f}",
         "pass": bool(abs(dd_t) <= 1.10 * abs(dd_v) and es_t <= 1.10 * es_v)},
        {"#": 4, "criterion": "DSR (noise-only null) of T02 at N = 9 >= DSR of v1.0 at N = 7 (0.619, T01 report)",
         "T02": f"DSR {d_t2['spec N9']['DSR_noise']:.3f} (N 9)",
         "v1.0": f"DSR {dsr_ref:.3f} (N 7; recomputed {d_v1['spec N7']['DSR_noise']:.3f})",
         "statistic": f"difference {d_t2['spec N9']['DSR_noise'] - dsr_ref:+.3f}",
         "pass": bool(d_t2["spec N9"]["DSR_noise"] >= dsr_ref)},
        {"#": 5, "criterion": "econ-momentum sleeve alpha vs v1.0 carry/trend/value sleeves, 2020-01..2026-09: "
                              "alpha > 0 and NW(3) t > 1.5",
         "T02": f"alpha {rt['alpha_ann_%']:+.2f}%/yr, t {rt['t_alpha']:+.2f} (n {rt['n']})", "v1.0": "n/a",
         "statistic": f"betas carry {rt['beta_carry']:+.2f}, trend {rt['beta_trend']:+.2f}, value "
                      f"{rt['beta_value']:+.2f}; R2 {rt['r2']:.2f}",
         "pass": bool(rt["alpha_monthly_%"] > 0 and rt["t_alpha"] > 1.5)},
    ]
    return {"criteria": c, "overall_pass": all(x["pass"] for x in c), "bootstrap": bs,
            "dsr": {"v1.0": d_v1, "T02": d_t2, "v1.0 N7 recorded (T01 report)": dsr_ref}, "alpha": reg}


def stage_run():
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inp1 = SY.build_inputs()
    repro = T1.reproduce_v1(inp1)
    print("v1.0 reproduction:", repro, flush=True)
    if not (repro["test"]["exact"] and repro["fit"]["exact"]):
        sys.exit("v1.0 does not reproduce its committed tables on these inputs; stopping before T02.")

    months = inp1["months"]
    calc = pd.period_range(months[0] - 3, months[-1], freq="M")      # 3 extra months for the delayed variant
    halfB = HO.instruments("B")
    halfA = HO.instruments("A")
    fxB = [c for c in FX if c in halfB]
    fxA = [c for c in FX if c in halfA]
    sig = {"all": EM.build(calc, FX), "half B": EM.build(calc, fxB), "half A": EM.build(calc, fxA)}
    print("signals built", flush=True)
    score = {u: s["score"] for u, s in sig.items()}
    delayed = {u: s.shift(3) for u, s in score.items()}        # vintage of t-3 used at t (robustness a)
    # save the signal and its diagnostics
    for u, s in sig.items():
        tag = u.replace(" ", "")
        s["score"].reindex(months).rename_axis("month").reset_index().assign(month=lambda d: d.month.astype(str)) \
            .to_csv(OUT / f"econmom_score_{tag}.csv", index=False, float_format="%.6f")
    sig["all"]["flagged"].reindex(months).rename_axis("month").reset_index() \
        .assign(month=lambda d: d.month.astype(str)).to_csv(OUT / "econmom_fallback_flags.csv", index=False)
    sig["all"]["n_subsignals"].reindex(months).rename_axis("month").reset_index() \
        .assign(month=lambda d: d.month.astype(str)).to_csv(OUT / "econmom_n_subsignals.csv", index=False)
    comp = sig["all"]["components"]
    comp[pd.PeriodIndex(comp.month, freq="M") >= months[0]].to_csv(OUT / "econmom_component_sources.csv", index=False)
    age = sig["all"]["index_age"]
    age[pd.PeriodIndex(age.month, freq="M") >= months[0]].to_csv(OUT / "econmom_index_age.csv", index=False)

    halves = {"all": None, "half B": halfB, "half A": halfA}
    runs = {}
    for cm in (1.0, 2.0):
        inp_c = TS.with_costs(inp1, cm) if cm != 1.0 else inp1
        for uni, ins in halves.items():
            x = inp_c if ins is None else TS.subset(inp_c, ins)
            xe = with_econmom(x, score[uni])
            xd = with_econmom(x, delayed[uni])
            v1 = SY.run(x, V1)
            t2 = run_t02(xe)
            # the bond book under T02 must be exactly v1.0's bond book
            with injected():
                wb = SY.book_weights(xe["bond"], T2)
            assert (wb - SY.book_weights(x["bond"], V1)).abs().max().max() < 1e-12
            runs[(uni, cm, "v1.0")] = v1
            runs[(uni, cm, "T02")] = t2
            runs[(uni, cm, "T02 (macro inputs delayed 3m, robustness)")] = run_t02(xd)
            runs[(uni, cm, "econ momentum sleeve")] = run_sleeve(xe)
            runs[(uni, cm, "econ momentum sleeve (delayed 3m)")] = run_sleeve(xd)
            if uni == "all":
                for k in V1:
                    runs[(uni, cm, f"{k} sleeve (v1.0 {k} only)")] = SY.run(x, [k])
            print("done", uni, cm, flush=True)

    # ---- performance table
    rows = []
    for (uni, cm, strat), res in runs.items():
        for pname, per in PERIODS.items():
            rows.append({"universe": uni, "costs": f"{cm:g}x", "strategy": strat, "period": pname,
                         **T1.metrics(res, per)})
    perf = pd.DataFrame(rows)
    perf.to_csv(OUT / "performance.csv", index=False, float_format="%.4f")

    mon = pd.DataFrame({f"{uni}|{cm:g}x|{s}": T1._net(r) for (uni, cm, s), r in runs.items()})
    mon.index.name = "month"
    mon.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(OUT / "monthly_net.csv", index=False,
                                                                           float_format="%.6f")
    # ---- by year, 2020-2026
    yrs = []
    for cm in (1.0, 2.0):
        for s in ("v1.0", "T02", "econ momentum sleeve", "T02 (macro inputs delayed 3m, robustness)"):
            res = runs[("all", cm, s)]
            ys = year_stats(T1._net(res).loc[TEST[0]:TEST[1]])
            to = T1.turnover(res).loc[TEST[0]:TEST[1]]
            ys["turnover_x"] = ys.year.map(to.groupby(to.index.year).sum())
            ys.insert(0, "strategy", s)
            ys.insert(0, "costs", f"{cm:g}x")
            yrs.append(ys)
    pd.concat(yrs).to_csv(OUT / "by_year_2020_2026.csv", index=False, float_format="%.4f")

    # ---- correlations of the sleeve with the carry, trend and value sleeves (1x)
    cor = []
    for pname, (a, b) in {**PERIODS, "2006-2026 (all months)": (None, TEST[1])}.items():
        d = pd.DataFrame({"econ momentum": T1._net(runs[("all", 1.0, "econ momentum sleeve")]),
                          **{k: T1._net(runs[("all", 1.0, f"{k} sleeve (v1.0 {k} only)")]) for k in V1},
                          "v1.0": T1._net(runs[("all", 1.0, "v1.0")])}).loc[a:b].dropna()
        for k in V1 + ["v1.0"]:
            cor.append({"period": pname, "months": len(d), "with": k, "corr": float(d["econ momentum"].corr(d[k]))})
    pd.DataFrame(cor).to_csv(OUT / "sleeve_correlations.csv", index=False, float_format="%.4f")

    # ---- signal correlations (score level): econmom vs carry/trend/value z-scores of the FX book
    fxsig = SY.signals(inp1["fx"])
    ez = SY._xs_z(score["all"].reindex(index=months, columns=FX))
    sc = []
    for pname, (a, b) in PERIODS.items():
        for k in V1:
            x = pd.concat([ez.loc[a:b].stack(), fxsig[k].loc[a:b].stack()], axis=1).dropna()
            xs = [ez.loc[t].corr(fxsig[k].loc[t]) for t in ez.loc[a:b].index]
            sc.append({"period": pname, "with": k, "pooled_corr": float(x.iloc[:, 0].corr(x.iloc[:, 1])),
                       "mean_monthly_xs_corr": float(np.nanmean(xs)), "n": len(x)})
    pd.DataFrame(sc).to_csv(OUT / "signal_correlations.csv", index=False, float_format="%.4f")

    # ---- fallback share and staleness (robustness b), signal coverage
    sc_all = score["all"].reindex(months)
    comp = comp.assign(m=pd.PeriodIndex(comp.month, freq="M"))
    av = comp[comp.available]
    per_cm = av.groupby(["m", "currency"]).agg(revised=("flagged", "any"))
    rev = per_cm["revised"].unstack().reindex(index=months, columns=FX).fillna(False).astype(bool)
    # stale = an index (econ or infl) whose last month is > 6 months before the decision month, so the
    # sub-signals of that index are computed on old data (the last published value kept, point-in-time)
    ag = age.assign(m=pd.PeriodIndex(age.month, freq="M"), stale=age.age_months > EM.STALE_MONTHS)
    stl = ag.groupby(["m", "currency"]).stale.any().unstack().reindex(index=months, columns=FX) \
        .fillna(False).astype(bool)
    idx_stale = ag.set_index(["m", "currency", "index"]).stale
    comp = comp.assign(index=np.where(comp.component == "CPI", "infl", "econ"))
    comp["index_stale"] = [bool(idx_stale.get((m, c, i), False)) for m, c, i in zip(comp.m, comp.currency, comp["index"])]
    av = comp[comp.available]
    fb = []
    for pname, (a, b) in PERIODS.items():
        have = sc_all.loc[a:b].notna()
        r, s = rev.loc[a:b] & have, stl.loc[a:b] & have
        cr = av[(av.m >= (a or months[0])) & (av.m <= b)]
        n = int(have.sum().sum())
        fb.append({"period": pname, "score_obs": n,
                   "score_obs_revised": int(r.sum().sum()), "share_revised_%": 100 * r.sum().sum() / n,
                   "score_obs_stale": int(s.sum().sum()), "share_stale_%": 100 * s.sum().sum() / n,
                   "score_obs_revised_or_stale": int((r | s).sum().sum()),
                   "share_revised_or_stale_%": 100 * (r | s).sum().sum() / n,
                   "component_months_available": len(cr),
                   "share_component_months_revised_%": 100 * float(cr.flagged.mean()),
                   "share_component_months_stale_%": 100 * float(cr.stale.mean()),
                   "share_component_months_revised_or_stale_%": 100 * float((cr.flagged | cr.stale).mean())})
    pd.DataFrame(fb).to_csv(OUT / "fallback_share.csv", index=False, float_format="%.4f")
    # every gap and fallback case in the test window, per currency and component (contiguous month runs)
    cases = []
    tw = comp[(comp.m >= TEST[0]) & (comp.m <= TEST[1])].sort_values(["currency", "component", "m"])
    for (ccy, c), g in tw.groupby(["currency", "component"], sort=False):
        stale_txt = np.where(g.index_stale, "stale, index not updated (last value kept)",
                             "ended, index continues on other components")
        kind = np.where(~g.available, "omitted (no source)",
                        np.where(g.flagged & g.stale, "revised fallback (lag 3), " + stale_txt,
                                 np.where(g.flagged, "revised fallback (lag 3)",
                                          np.where(g.stale, "first-release, " + stale_txt, "first-release"))))
        g = g.assign(kind=kind, src=g.source.str.replace(r"edition \d{4}-\d{2}", "editions", regex=True))
        run_id = ((g.kind != g.kind.shift()) | (g.src != g.src.shift())).cumsum()
        for _, h in g.groupby(run_id):
            if h.kind.iloc[0] == "first-release":
                continue
            cases.append({"currency": ccy, "component": c, "from": str(h.m.min()), "to": str(h.m.max()),
                          "months": len(h), "case": h.kind.iloc[0], "source": h.src.iloc[0],
                          "last_obs_range": f"{h.last_obs.min()}..{h.last_obs.max()}" if h.available.any() else "",
                          "max_age_months": float(h.age_months.max()) if h.available.any() else np.nan})
    pd.DataFrame(cases).to_csv(OUT / "gap_and_fallback_cases_2020_2026.csv", index=False)
    fbc = []
    for ccy in FX:
        s = sc_all.loc[TEST[0]:TEST[1], ccy].notna()
        r, st = rev.loc[TEST[0]:TEST[1], ccy] & s, stl.loc[TEST[0]:TEST[1], ccy] & s
        fbc.append({"currency": ccy, "score_months": int(s.sum()), "months_revised": int(r.sum()),
                    "months_stale": int(st.sum()), "months_revised_or_stale": int((r | st).sum())})
    pd.DataFrame(fbc).to_csv(OUT / "fallback_by_currency_2020_2026.csv", index=False)

    # ---- first-release vs latest-data signal (diagnostic, spec §13)
    latest = EM.build_latest(months, FX)
    lc = []
    for pname, (a, b) in PERIODS.items():
        x, y = sc_all.loc[a:b], latest.loc[a:b]
        st = pd.concat([x.stack(), y.stack()], axis=1).dropna()
        rk = [x.loc[t].rank().corr(y.loc[t].rank()) for t in x.index if x.loc[t].notna().sum() >= 3]
        sel = [(np.sign(x.loc[t].dropna()) == np.sign(y.loc[t].reindex(x.loc[t].dropna().index))).mean()
               for t in x.index if x.loc[t].notna().sum() >= 3]
        lc.append({"period": pname, "n": len(st), "pooled_corr": float(st.iloc[:, 0].corr(st.iloc[:, 1])),
                   "mean_monthly_rank_corr": float(np.nanmean(rk)), "same_sign_share_%": 100 * float(np.nanmean(sel))})
    pd.DataFrame(lc).to_csv(OUT / "first_release_vs_latest.csv", index=False, float_format="%.4f")
    latest.rename_axis("month").reset_index().assign(month=lambda d: d.month.astype(str)) \
        .to_csv(OUT / "econmom_score_latest_data.csv", index=False, float_format="%.6f")

    # ---- criteria
    crit = {}
    for cm in (1.0, 2.0):
        tag = f"{cm:g}x"
        crit[tag] = criteria(runs, cm, "T02")
        pd.DataFrame(crit[tag]["criteria"]).to_csv(OUT / f"pass_fail_{tag}.csv", index=False)
        crit[f"robustness delayed 3m {tag}"] = criteria(runs, cm, "T02 (macro inputs delayed 3m, robustness)")
    (OUT / "criteria.json").write_text(json.dumps(crit, indent=1, default=float))

    files = ["em_macro/systematic.py", "results/systematic/fit/frozen_design.json", "em_macro/econmom.py",
             "em_macro/t02.py", "em_macro/t01.py", "em_macro/tstrend.py", "em_macro/holdout.py",
             "docs/prereg/T02_econ_momentum.md", "data/processed/daily_panel.csv",
             "data/processed/country_month_panel.csv", "data/processed/risk_model_input.csv",
             "results/T02/raw_data_manifest.csv"]
    (OUT / "RUN.json").write_text(json.dumps({
        "run_started_utc": started, "run_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_run": T1._git_head(), "pandas": pd.__version__, "numpy": np.__version__,
        "last_month": str(months[-1]), "v1_reproduction": repro, "decision_costs": "1x",
        "overall_pass_1x": crit["1x"]["overall_pass"], "sha256": {f: T1._sha(f) for f in files}}, indent=1))
    print(pd.DataFrame(crit["1x"]["criteria"]).to_string())
    print("OVERALL (1x):", "PASS" if crit["1x"]["overall_pass"] else "FAIL")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        stage_run()
    elif cmd == "report":
        from . import t02_report
        t02_report.write()
    else:
        sys.exit(__doc__)
