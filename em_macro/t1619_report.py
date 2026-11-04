"""results/T16-T19_risk_batch.md from the tables written by `python -m em_macro.t1619 run`."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import t1619 as B
from .config import RESULTS

OUT = B.OUT
TRIALS = B.TRIALS
NAMES = {"T16": "T16 carry-crash filter", "T17": "T17 factor-capped sizing", "T18": "T18 turnover reduction",
         "T19": "T19 volatility forecasting"}
LEDGER = {"T16": "G15_carry_crash_filter", "T17": "G16_factor_capped_sizing", "T18": "G17_turnover_reduction",
          "T19": "G18_vol_forecast_sizing"}


def _md(df: pd.DataFrame, fmt: dict | None = None, default: str = "{:.2f}") -> str:
    fmt = fmt or {}
    cols = list(df.columns)
    L = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        cells = []
        for c, v in zip(cols, r):
            if isinstance(v, (bool, np.bool_)):
                cells.append("PASS" if v else "FAIL")
            elif isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else fmt.get(c, default).format(v))
            else:
                cells.append(str(v).replace("|", "\\|"))
        L.append("| " + " | ".join(cells) + " |")
    return "\n".join(L)


def _perf_table(perf: pd.DataFrame, universe: str, period: str, strategies: list[str], costs=("1x", "2x")) -> str:
    rows = []
    for cm in costs:
        for s in strategies:
            x = perf[(perf.universe == universe) & (perf.period == period) & (perf.strategy == s) & (perf.costs == cm)]
            if x.empty:
                continue
            x = x.iloc[0]
            rows.append({"costs": cm, "strategy": s, "start": x["start"], "months": int(x["months"]), "Sharpe": x["sharpe"],
                         "return %/yr": x["ann_return_%"], "vol %": x["ann_vol_%"], "MaxDD %": x["max_drawdown_%"],
                         "ES97.5 % (monthly)": x["ES97.5_monthly_%"], "turnover x/yr": x["turnover_x_pa"],
                         "costs %/yr": x["cost_drag_%_pa"], "avg gross lev.": x["avg_gross_leverage"]})
    return _md(pd.DataFrame(rows))


def build() -> str:
    perf = pd.read_csv(OUT / "performance.csv")
    yr = pd.read_csv(OUT / "by_year_2020_2026.csv")
    wm = pd.read_csv(OUT / "worst_months.csv")
    crit = json.loads((OUT / "criteria.json").read_text())
    diag = json.loads((OUT / "diagnostics.json").read_text())
    run = json.loads((OUT / "RUN.json").read_text())
    holm = {cm: pd.read_csv(OUT / f"holm_{cm}.csv") for cm in ("1x", "2x")}
    S = ["v1.0", *TRIALS]
    L = []
    L.append("# Trials T16–T19: risk batch against frozen v1.0 — results\n")
    L.append("| item | value |\n|---|---|")
    L.append("| pre-registration | `docs/prereg/T16-T19_risk_batch.md`, committed in `4c10856` before any T16–T19 code or computation; ledger rows (pending) in `293799b` |")
    L.append("| ledger | `trials.csv` ids **T16, T17, T18, T19**, groups " + ", ".join(f"`{LEDGER[t]}`" for t in TRIALS) + " |")
    L.append(f"| code at run | `{run['git_head_at_run'][:7]}` (branch `trial/T16-T19-risk-batch`); `em_macro/t16_crash.py`, `t17_factorcap.py`, `t18_rebal.py`, `t19_vol.py`, `t1619.py`; re-uses `em_macro/t01.py` (statistics), `em_macro/tstrend.py` (v1.0 machinery helpers), `em_macro/holdout.py` |")
    L.append(f"| run | {run['run_started_utc']} to {run['run_finished_utc']} UTC; pandas {run['pandas']}, numpy {run['numpy']}; data through {run['last_month']}; one run per trial, universe and cost setting |")
    rp = run["v1_reproduction"]
    L.append(f"| v1.0 reproduction | `python -m em_macro.verify_v1`: both committed tables byte-identical (run before the batch); frozen `systematic.evaluate` on this run's inputs vs the committed tables: test 2020-01..2026-09 max abs diff {rp['test']['max_abs_diff_at_4dp']:.4f} ({rp['test']['rows']} rows), design 2005-2019 max abs diff {rp['fit']['max_abs_diff_at_4dp']:.4f} ({rp['fit']['rows']} rows), at the files' 4 decimals |")
    L.append("| v1.0 baseline | tag `v1.0-frozen` = `7886867`; `em_macro/systematic.py` SHA-256 `1eb4cf6b1c537c17…` (unchanged) |")
    L.append("| decision basis | 1x costs (v1.0's cost model), 2020-01..2026-09, all 23 instruments, with the half-B holdout and the deflated Sharpe; 2x costs, 2005-2019 and half A reported, not decisive |")
    L.append("| family | the four trials are one family: Holm correction of the four bootstrap p-values; DSR at N = 13 |")
    L.append("\nv1.0's figures remain \"OOS for v1.0 only\". Each trial's figures are reported separately and are not merged with v1.0's track record. Each trial is a single change to v1.0 tested on its own; no combination was run.\n")

    # ---------------- 1. pass/fail
    L.append("## 1. Pre-registered pass/fail tables\n")
    for cm in ("1x", "2x"):
        L.append(f"### {cm} costs ({'decisive' if cm == '1x' else 'sensitivity, not decisive'})\n")
        summary = []
        for t in TRIALS:
            tab = crit[cm]["tables"][t]
            summary.append({"trial": NAMES[t], "criteria passed": f"{tab['n_pass']} of {tab['n']}", "overall": tab["overall_pass"]})
        L.append(_md(pd.DataFrame(summary)))
        L.append("")
        for t in TRIALS:
            tab = crit[cm]["tables"][t]
            df = pd.DataFrame(tab["criteria"]).rename(columns={"trial": t, "pass": "result"})
            L.append(f"**{NAMES[t]}** — overall: **{'PASS' if tab['overall_pass'] else 'FAIL'}** ({tab['n_pass']} of {tab['n']} criteria).\n")
            L.append(_md(df))
            L.append("")
        h = holm[cm].copy()
        h["trial"] = h["trial"].map(NAMES)
        h.columns = ["trial", "p raw (one-sided, H1: dSR > -0.05)", "p Holm-adjusted", "dSR point", "bootstrap SD of dSR"]
        L.append(f"**Holm correction ({cm}).** Paired circular block bootstrap, block 6 months, B = 10,000, seed 20261103; "
                 "the null is centred at dSR = -0.05 (Sharpe non-inferiority with margin 0.05). The four p-values are one family.\n")
        L.append(_md(h, {"p raw (one-sided, H1: dSR > -0.05)": "{:.4f}", "p Holm-adjusted": "{:.4f}", "dSR point": "{:+.3f}", "bootstrap SD of dSR": "{:.3f}"}))
        L.append("")
        bsrows = []
        for t in TRIALS:
            b = crit[cm]["per_trial"][t]["bootstrap"]
            bsrows.append({"trial": t, "dSR": b["delta_sr"], "boot mean": b["boot_mean"], "boot SD": b["boot_sd"],
                           "5%": b["boot_q05"], "95%": b["boot_q95"], "p (margin 0.05)": b["p_one_sided"],
                           "p (margin 0, spec rule, context)": b["p_one_sided_margin0"]})
        L.append(_md(pd.DataFrame(bsrows), {"dSR": "{:+.3f}", "boot mean": "{:+.3f}", "boot SD": "{:.3f}", "5%": "{:+.3f}", "95%": "{:+.3f}",
                                           "p (margin 0.05)": "{:.4f}", "p (margin 0, spec rule, context)": "{:.4f}"}))
        L.append("")

    # ---------------- 2. side by side
    L.append("## 2. v1.0 and each trial side by side\n")
    L.append("Sharpe = mean/SD × √12 of monthly net returns; return = compounded; MaxDD on the compounded monthly index; ES97.5 = historical expected shortfall of monthly net returns (Acerbi-Tasche), as a loss; turnover = one-way notional traded per year, in multiples of capital; costs = cost drag per year.\n")
    L.append("**Test, 2020-01..2026-09, all 23 instruments (decisive).**\n")
    L.append(_perf_table(perf, "all", "2020-01..2026-09 (test)", S))
    L.append("\n**Holdout, half B (BR, CO, ZA, TR, GB, FR, IT; 12 instruments), 2020-01..2026-09.** Each strategy run as a stand-alone universe of half B; T16's crash model trained on half A only.\n")
    L.append(_perf_table(perf, "half B", "2020-01..2026-09 (test)", S))
    L.append("\n**In-sample context, 2005-2019 (cannot affect the decision).** v1.0 was designed on this period; T16's filter is active from 2010 (walk-forward) and off before.\n")
    L.append(_perf_table(perf, "all", "2005-2019 (in-sample, context)", S))
    L.append("\n**Context: half A (MX, CL, PL, ID, ES, DE, euro area), 2020-01..2026-09, and half B 2005-2019, 1x costs.**\n")
    rows = []
    for uni, per in (("half A", "2020-01..2026-09 (test)"), ("half B", "2005-2019 (in-sample, context)"), ("half A", "2005-2019 (in-sample, context)")):
        for s in S:
            x = perf[(perf.universe == uni) & (perf.period == per) & (perf.strategy == s) & (perf.costs == "1x")].iloc[0]
            rows.append({"universe": uni, "period": per, "strategy": s, "months": int(x["months"]), "Sharpe": x["sharpe"],
                         "return %/yr": x["ann_return_%"], "vol %": x["ann_vol_%"], "MaxDD %": x["max_drawdown_%"],
                         "ES97.5 % (monthly)": x["ES97.5_monthly_%"], "turnover x/yr": x["turnover_x_pa"]})
    L.append(_md(pd.DataFrame(rows)))
    L.append("\n**v1.0 with no band at all (context for T18, all instruments).**\n")
    L.append(_perf_table(perf, "all", "2020-01..2026-09 (test)", ["v1.0", "v1.0 no band (context)", "T18"]))

    # ---------------- 3. by year
    L.append("\n## 3. By year, 2020–2026 (2026 = January–September), all instruments\n")
    L.append("Return compounded within the year; MaxDD within the year from the start-of-year level; turnover = notional traded in the year. The trials estimate nothing on returns except T16's walk-forward crash model (fitted each year on data to September of the year before), so each year is a walk-forward year.\n")
    for cm in ("1x", "2x"):
        L.append(f"*{cm} costs*\n")
        for metric, label, f in (("return_%", "return %", "{:.2f}"), ("sharpe", "Sharpe", "{:.2f}"), ("max_drawdown_%", "MaxDD %", "{:.2f}"),
                                 ("vol_%", "vol %", "{:.2f}"), ("turnover_x", "turnover x", "{:.2f}")):
            piv = yr[yr.costs == cm].pivot(index="year", columns="strategy", values=metric)[S]
            piv.columns = [f"{s} {label}" for s in piv.columns]
            piv = piv.reset_index()
            L.append(_md(piv, {c: f for c in piv.columns if c != "year"}))
            L.append("")

    # ---------------- 4. worst months
    L.append("## 4. v1.0's five worst months, 2020-01..2026-09 (net return, %)\n")
    L.append("The five lowest monthly net returns of v1.0 at 1x costs, with each trial's net return in the same months.\n")
    cols1 = ["month"] + [c for c in wm.columns if c.endswith(" 1x %")]
    cols2 = ["month"] + [c for c in wm.columns if c.endswith(" 2x %")]
    L.append(_md(wm[cols1]))
    L.append("")
    L.append(_md(wm[cols2]))
    L.append("")
    sums = {c: wm[c].sum() for c in wm.columns if c != "month"}
    L.append("Sum over the five months: " + "; ".join(f"{k.replace(' %', '')} {v:+.2f}%" for k, v in sums.items()) + ".\n")

    # ---------------- 5. DSR
    L.append("## 5. Deflated-Sharpe update\n")
    L.append("PSR and DSR (spec §0.2; `em_macro/mtstats.py`) from each strategy's realised 2020-01..2026-09 monthly Sharpe, skewness and raw kurtosis, T = 81. Noise-only null: trial-Sharpe SD = 1/√80 per month (decisive). Dispersed: SD 0.20 annualised. N incremented for the whole family: spec convention 7 → 13 (each trial at 13 against v1.0 at 7); ledger convention 14 → 18 (context).\n")
    for cm in ("1x", "2x"):
        rows = []
        for conv in ("spec", "ledger"):
            d = crit[cm]["dsr_v1"][conv]
            rows.append({"strategy": "v1.0", "convention": conv, **{k: d[k] for k in ("N", "SR_ann", "skew", "kurtosis_raw", "PSR(SR*=0)", "SR0_noise_ann", "DSR_noise", "SR0_dispersed_ann", "DSR_dispersed")}})
            for t in TRIALS:
                d = crit[cm]["per_trial"][t]["dsr"][conv]
                rows.append({"strategy": t, "convention": conv, **{k: d[k] for k in ("N", "SR_ann", "skew", "kurtosis_raw", "PSR(SR*=0)", "SR0_noise_ann", "DSR_noise", "SR0_dispersed_ann", "DSR_dispersed")}})
        df = pd.DataFrame(rows)
        df["N"] = df["N"].astype(int)
        L.append(f"*{cm} costs*\n")
        L.append(_md(df, {c: "{:.3f}" for c in df.columns if c not in ("strategy", "convention", "N")}))
        L.append("")

    # ---------------- 6. diagnostics
    L.append("## 6. Trial diagnostics (context; not pass criteria)\n")
    d16 = diag["T16"]
    L.append("### T16 carry-crash filter\n")
    rows = []
    for u in ("all", "half B", "half A"):
        x = d16[u]
        st, sc = x["skill_test"], x["skill_context_2010_2019"]
        rows.append({"universe (model trained on)": f"{u} ({'half A' if u == 'half B' else u})", "labelled obs": x["labelled_obs"],
                     "crash rate (all labels)": x["crash_rate_all_labels"], "test obs": st.get("n", 0), "test crash rate": st.get("crash_rate", np.nan),
                     "AUC test": st.get("auc", np.nan), "Brier skill test": st.get("brier_skill", np.nan),
                     "AUC 2010-19": sc.get("auc", np.nan), "Brier skill 2010-19": sc.get("brier_skill", np.nan),
                     "share of currency-months scaled < 1 (test)": x["share_scaled_below_1_test"],
                     "share scaled to 0 (test)": x["share_scaled_to_0_test"], "mean scale (test)": x["mean_scale_test"],
                     "imputed feature cells": x["features_imputed_cells_total"]})
    L.append(_md(pd.DataFrame(rows), {"crash rate (all labels)": "{:.3f}", "test crash rate": "{:.3f}", "AUC test": "{:.3f}", "Brier skill test": "{:+.3f}",
                                     "AUC 2010-19": "{:.3f}", "Brier skill 2010-19": "{:+.3f}", "share of currency-months scaled < 1 (test)": "{:.3f}",
                                     "share scaled to 0 (test)": "{:.3f}", "mean scale (test)": "{:.3f}"}))
    L.append("\nThe spec's own filter checks (§6.2: walk-forward AUC > 0.60, Brier skill > 0 on half B) are shown for information; the pre-registered pass rule is §4 of the pre-registration.\n")
    yrows = []
    for y in d16["all"]["years"]:
        if y.get("fitted"):
            yrows.append({"year": y["year"], "train obs": y["n_train"], "C chosen": y["C"], "p_base": y["p_base"],
                          "coef carry_z": y["coef"]["carry_z"], "coef value": y["coef"]["value"], "coef ca_gdp": y["coef"]["ca_gdp"],
                          "coef res_imp": y["coef"]["res_imp"], "coef vol_ratio": y["coef"]["vol_ratio"], "coef d3_vix": y["coef"]["d3_vix"],
                          "coef d3_usd": y["coef"]["d3_usd"], "coef d3_us2y": y["coef"]["d3_us2y"], "coef own12": y["coef"]["own12"],
                          "coef election": y["coef"]["election"]})
    L.append("Walk-forward fits on all 10 currencies (standardised coefficients; C by time-blocked CV):\n")
    L.append(_md(pd.DataFrame(yrows), {"C chosen": "{:g}", "p_base": "{:.3f}", **{f"coef {k}": "{:+.2f}" for k in ["carry_z", "value", "ca_gdp", "res_imp", "vol_ratio", "d3_vix", "d3_usd", "d3_us2y", "own12", "election"]}}))
    L.append("")
    d17 = diag["T17"]
    L.append("### T17 factor-capped sizing\n")
    hs = d17["held_shares_test"]
    L.append(_md(pd.DataFrame([
        {"item": "decision months modelled, 2020-01..2026-09", "value": f"{d17['decision_months_test']}"},
        {"item": "months in which a cap bound (adjusted)", "value": f"{d17['months_adjusted_test']} (USD cap breached {d17['months_usd_breached_test']}, EM cap breached {d17['months_em_breached_test']}; fallback used {d17['months_fallback_test']})"},
        {"item": "max USD / EM share of v1.0's targets before capping (test)", "value": f"{100 * d17['max_usd_share_before_test']:.1f}% / {100 * d17['max_em_share_before_test']:.1f}%"},
        {"item": "when adjusted: mean ||w - w0||, mean positions opened in unselected instruments, their mean gross", "value": f"{d17['mean_distance_when_adjusted']:.3f}; {d17['mean_positions_opened_when_adjusted']:.1f}; {d17['mean_opened_gross_when_adjusted']:.3f}"},
        {"item": "months adjusted, all months 2005-2026", "value": f"{d17['months_adjusted_all']} of {d17['decision_months_all']}"},
        {"item": "held positions, version-B USD share, test: v1.0 mean / max", "value": f"{100 * hs['v1.0']['usd_mean']:.1f}% / {100 * hs['v1.0']['usd_max']:.1f}%"},
        {"item": "held positions, version-B USD share, test: T17 mean / max", "value": f"{100 * hs['T17']['usd_mean']:.1f}% / {100 * hs['T17']['usd_max']:.1f}%"},
        {"item": "held positions, version-B EM share, test: v1.0 mean / max", "value": f"{100 * hs['v1.0']['em_mean']:.1f}% / {100 * hs['v1.0']['em_max']:.1f}%"},
        {"item": "held positions, version-B EM share, test: T17 mean / max", "value": f"{100 * hs['T17']['em_mean']:.1f}% / {100 * hs['T17']['em_max']:.1f}%"},
        {"item": "held positions, USD+EM combined, test: v1.0 mean / max; T17 mean / max", "value": f"{100 * hs['v1.0']['usd_em_mean']:.1f}% / {100 * hs['v1.0']['usd_em_max']:.1f}%; {100 * hs['T17']['usd_em_mean']:.1f}% / {100 * hs['T17']['usd_em_max']:.1f}%"},
    ])))
    L.append("\nThe held-position shares differ from the target shares because the 6× cap, the band and the one-month bond lag act after the cap. The 75% USD share in the risk audit was the daily-priced version A (14 instruments); version B (full book, monthly) is the measure T17 caps.\n")
    d18 = diag["T18"]
    L.append("### T18 turnover reduction\n")
    tb = d18["turnover_by_book_test"]
    L.append(_md(pd.DataFrame([
        {"item": "turnover x/yr, FX book: v1.0 / T18", "value": f"{tb['fx']['v1.0']:.2f} / {tb['fx']['T18']:.2f}"},
        {"item": "turnover x/yr, bond book: v1.0 / T18", "value": f"{tb['bond']['v1.0']:.2f} / {tb['bond']['T18']:.2f}"},
        {"item": "proposed trades 2020-2026 (target differs from held)", "value": f"{d18['proposed_trades_test']}; suppressed by the band {d18['trades_suppressed_by_band_test']} ({100 * d18['share_suppressed_test']:.1f}%); residual closes {d18['residual_closes_test']}"},
        {"item": "mean gross held / gross target (test)", "value": f"{d18['mean_gross_held_over_target_test']:.3f}"},
        {"item": "average gross leverage (test): v1.0 / T18", "value": f"{d18['avg_gross_leverage_test']['v1.0']:.2f} / {d18['avg_gross_leverage_test']['T18']:.2f}"},
    ])))
    L.append("")
    d19 = diag["T19"]
    L.append("### T19 volatility forecasting\n")
    rv = d19["realised_vol_by_year"]
    L.append(_md(pd.DataFrame([
        {"item": "share of instrument-months in which the floor 0.8·σ_EWMA250 sets the estimate (test)", "value": f"{100 * d19['share_instrument_months_floor_binds_test']:.1f}%"},
        {"item": "mean ratio of T19's instrument vol estimate to v1.0's 36-month vol (test)", "value": f"{d19['mean_ratio_T19_vol_to_v1_vol_test']:.3f}"},
        {"item": "average gross leverage (test): v1.0 / T19", "value": f"{d19['avg_gross_leverage_test']['v1.0']:.2f} / {d19['avg_gross_leverage_test']['T19']:.2f}"},
        {"item": "realised vol by year, % (v1.0 / T19)", "value": "; ".join(f"{y}: {v['v1.0']:.1f} / {v['T19']:.1f}" for y, v in rv.items())},
    ])))
    L.append("")

    # ---------------- 7. decisions
    L.append("## 7. Decisions taken under the task's rules\n")
    L.append("All were fixed in the pre-registration (§7 there) before any computation; none was changed afterwards.\n")
    L.append("\n".join([
        "1. **T16 horizon h = 3 months:** the spec gives h ∈ {1, 3, 6}; the central value was used.",
        "2. **T16 features and proxies:** NFA/GDP and the CFTC positioning z-score omitted (no data among the inputs; no proxy measures the same thing). Reserves/short-term debt proxied by reserves in months of imports (World Bank, in the panel). VAL_reer proxied by v1.0's real-exchange-rate value (BIS REER not among the inputs). WEO current account from the single latest vintage (October 2026), the value of year Y−1 used throughout year Y: revised data, a flagged look-ahead risk. Euro-area external features = mean of DE, FR, IT, ES. Election feature from `data/events/elections.csv` (snap elections a small look-ahead).",
        "3. **T16 penalty:** C chosen by 5-block time-blocked cross-validation over {0.01, 0.1, 1, 10, 100} with a 3-month purge; ties → C = 1.0 (the spec code's default). Missing features imputed at the training mean.",
        "4. **T16 walk-forward start:** expanding window from 2005 (inputs start then; the spec's 1995 is not available). Decisive years 2020–2026; context years 2010–2019; no filter before 2010.",
        "5. **T16 placement:** the scale multiplies long currency positions after v1.0's 10% total rescaling and before the 6× cap and the band. The holdout model is trained on half A only and applied to half B.",
        "6. **T17 risk measure:** the risk audit's version B (monthly returns, Ledoit-Wolf, 60 months, all 23 instruments) rather than the spec's 3-day version A, which covers only 14 instruments. Caps USD 25% and EM 40% (the spec's [A] values); the country, LatAm and duration caps were excluded as not part of the single change. Adjustment by SLSQP with a projection fallback, support unrestricted as the spec's QP is written; re-scaled to 10% after the cap with v1.0's own rule (spec Build 5 order).",
        "7. **T18 rules:** both of the spec's rebalancing rules with the spec's values (band 0.1 of the position's risk budget, applied to the proposed trade; partial factor 0.5). The position's risk budget is the equal risk v1.0 gives each selected position of a book. The residual of an exited position is closed once its half-trade falls inside the band.",
        "8. **T19 estimator:** the spec's floor formula max(σ_EWMA60, 0.8·σ_EWMA250) with half-lives converted to months at 21 trading days (2.857 and 11.905), a zero-mean EWMA of squared monthly returns (spec §7 recursion), min 12 months; applied at all three points where v1.0 uses its 36-month volatility (instrument vol, book scaler, total scaler).",
        "9. **Sharpe criterion:** a non-inferiority test with margin 0.05 (H1: ΔSR > −0.05), one-sided 6-month block-bootstrap p, Holm-adjusted across the four trials, level 0.10 (the spec's); the point estimate must also be ≥ −0.05.",
        "10. **Risk criterion:** \"at least 10% better\" = the trial's |MaxDD| or ES97.5 at most 0.90 × v1.0's; the same metric must meet the bar in half B.",
        "11. **Deflated Sharpe:** spec convention N = 7 → 13 (7 + T01 + T02 + the four of this family), every trial compared with v1.0 at N = 7; ledger convention 14 → 18 reported as context.",
        "12. **2x costs:** the trial rules applied identically with every cost doubled; reported only.",
        "13. **Raw data:** one archive of the raw downloads used (FRED, Yahoo, BIS, BanRep, BCCh/mindicador) under `data/kept/T16-T19/`, recorded in `docs/raw_data_archive.md` for the four trials.",
        "14. **Merge conflicts with `main`:** none arose (the branch was cut from `main` at `360f816`); the rule was to keep both sides.",
    ]))
    L.append("")

    # ---------------- 8. combination note
    passing = [t for t in TRIALS if crit["1x"]["tables"][t]["overall_pass"]]
    L.append("## 8. Note on combining passing trials (not tested here)\n")
    if len(passing) >= 2:
        L.append(f"Trials that passed at 1x: {', '.join(NAMES[t] for t in passing)}. They were tested one at a time against v1.0 and never together. "
                 "A combination would be a new, separately pre-registered trial with its own ledger row and N increment; the pre-registration would have to fix the order in which the changes act in the pipeline "
                 "(T16's scale and T17's cap both act on the targets after the 10% rescaling; T18 replaces the band at the end; T19 changes the volatility estimate at the start), since the result of applying two of them is not the sum of their separate effects.")
    elif len(passing) == 1:
        L.append(f"One trial passed at 1x ({NAMES[passing[0]]}); there is nothing to combine it with from this family. Any future combination with a trial from another family would be a new pre-registered trial.")
    else:
        L.append("No trial passed the pre-registered rule at 1x, so there is no passing trial to combine. Any future combination would be a new, separately pre-registered trial.")
    L.append("")

    # ---------------- 9. notes and files
    L.append("## 9. Notes\n")
    L.append("\n".join([
        "- **Identity checks run before the comparison:** each trial's code reproduces frozen v1.0 exactly when its one change is switched off (T18 with v1.0's band through the T18 P&L path; T19 with v1.0's 36-month estimator; T17 with caps that never bind; T16 with scale 1), on this run's inputs (asserted in the runner) and on synthetic inputs (`tests/test_t1619.py`).",
        "- **Moments and DSR.** Skewness is the pandas bias-corrected skewness; kurtosis is raw (normal = 3).",
        "- **T16 look-ahead caveats.** Two features use the latest WEO/WDI vintage (lagged one year) and the election calendar as recorded now; the model is otherwise point-in-time (walk-forward fits, labels purged). Daily spot for the volatility ratio comes from the same sources as v1.0's month-end spot.",
        "- **Runs.** Every table in `results/T16-T19/` comes from one invocation of `python -m em_macro.t1619 run`; no trial was re-run or re-parameterised.",
    ]))
    L.append("")
    L.append("## 10. Files\n")
    L.append("\n".join([
        "- `results/T16-T19/performance.csv`: every strategy × universe (all, half A, half B) × costs × period; `monthly_net.csv`: monthly net returns of every run; `by_year_2020_2026.csv`; `worst_months.csv`.",
        "- `results/T16-T19/pass_fail_<trial>_{1x,2x}.csv`, `holm_{1x,2x}.csv`, `criteria.json` (bootstrap, DSR, every criterion statistic).",
        "- `results/T16-T19/diagnostics.json`, `t16_model.json`, `t16_{features,prob,scale}_<universe>.csv`, `t17_caplog_*.csv`, `t17_shares_{v1,T17}.csv`, `t18_tradelog_*.csv`.",
        "- `results/T16-T19/RUN.json`: run time, code commit, SHA-256 of code, pre-registration and input files, the v1.0 reproduction check.",
        "- Code: `em_macro/t16_crash.py`, `t17_factorcap.py`, `t18_rebal.py`, `t19_vol.py` (one module per trial), `em_macro/t1619.py` (runner and statistics), `em_macro/t1619_report.py`. Tests: `tests/test_t1619.py`.",
        "- Raw data: `data/kept/T16-T19/` (see `docs/raw_data_archive.md`).",
    ]))
    return "\n".join(L) + "\n"


def write():
    B.REPORT.write_text(build())
    print("wrote", B.REPORT)
