"""results/T02_econ_momentum.md from the tables saved by `python -m em_macro.t02 run`."""
from __future__ import annotations

import json

import pandas as pd

from .config import RESULTS
from .t01_report import COLS, _md

OUT = RESULTS / "T02"
REPORT = RESULTS / "T02_econ_momentum.md"
TESTP, ISP = "2020-01..2026-09 (test)", "2005-2019 (in-sample, context)"
DEL = "T02 (macro inputs delayed 3m, robustness)"
SLV = "econ momentum sleeve"
SIDE = ["sharpe", "ann_return_%", "ann_vol_%", "max_drawdown_%", "ES97.5_monthly_%", "turnover_x_pa",
        "cost_drag_%_pa", "avg_gross_leverage"]


def _perf(perf, uni, period, strategies, costs=("1x", "2x"), cols=None):
    cols = cols or SIDE
    d = perf[(perf.universe == uni) & (perf.period == period) & perf.strategy.isin(strategies) & perf.costs.isin(costs)]
    d = d.assign(_o=d.strategy.map({s: i for i, s in enumerate(strategies)})).sort_values(["costs", "_o"])
    return _md(d[["costs", "strategy", "start", "months"] + cols].rename(columns=COLS))


def _crit_table(c):
    return _md(pd.DataFrame(c["criteria"]).rename(columns={"pass": "result"}), 3)


def _overall(c):
    p = [str(x["#"]) for x in c["criteria"] if x["pass"]]
    f = [str(x["#"]) for x in c["criteria"] if not x["pass"]]
    return (f"**Overall (all five required): {'PASS' if c['overall_pass'] else 'FAIL'}** — criteria passed: "
            f"{len(p)} of 5 ({', '.join(p) or 'none'}); failed: {', '.join(f) or 'none'}.")


def write():
    perf = pd.read_csv(OUT / "performance.csv")
    yrs = pd.read_csv(OUT / "by_year_2020_2026.csv")
    crit = json.loads((OUT / "criteria.json").read_text())
    run = json.loads((OUT / "RUN.json").read_text())
    cor = pd.read_csv(OUT / "sleeve_correlations.csv")
    scor = pd.read_csv(OUT / "signal_correlations.csv")
    fb = pd.read_csv(OUT / "fallback_share.csv")
    fbc = pd.read_csv(OUT / "fallback_by_currency_2020_2026.csv")
    cases = pd.read_csv(OUT / "gap_and_fallback_cases_2020_2026.csv")
    # wording only: a component more than six months behind has not necessarily ended
    cases["case"] = cases["case"].str.replace("ended, index continues on other components",
                                              "> 6 months old, index continues on other components", regex=False)
    flr = pd.read_csv(OUT / "first_release_vs_latest.csv")
    c1, c2 = crit["1x"], crit["2x"]
    L = []
    L.append("# Trial T02: economic momentum as a fourth currency signal — results\n")
    L.append("| item | value |\n|---|---|")
    L.append("| pre-registration | `docs/prereg/T02_econ_momentum.md`, committed in `0b40b2a` before any T02 run |")
    L.append("| ledger | `trials.csv` id **T13** (named T02; `T02` is the gold event trades' ledger id), group "
             "`G12_econ_momentum` |")
    L.append(f"| code at run | `{run['git_head_at_run'][:7]}` (branch `trial/T02-econ-momentum`); `em_macro/econmom.py`, "
             "`em_macro/t02.py`; re-uses `em_macro/t01.py` (statistics), `em_macro/tstrend.py` (cost and subset "
             "helpers), `em_macro/holdout.py` |")
    L.append(f"| run | {run['run_started_utc']} to {run['run_finished_utc']} UTC; pandas {run['pandas']}, numpy "
             f"{run['numpy']}; data through {run['last_month']} |")
    rp = run["v1_reproduction"]
    L.append(f"| v1.0 reproduction | frozen `systematic.evaluate` on this run's inputs vs the committed tables: test "
             f"2020-01..2026-09 max abs diff {rp['test']['max_abs_diff_at_4dp']:.4f} ({rp['test']['rows']} rows), "
             f"design 2005-2019 max abs diff {rp['fit']['max_abs_diff_at_4dp']:.4f} ({rp['fit']['rows']} rows), at "
             "the files' 4 decimals; checked before T02 was run |")
    L.append("| v1.0 baseline | tag `v1.0-frozen` = `7886867`; `em_macro/systematic.py` SHA-256 "
             f"`{run['sha256']['em_macro/systematic.py'][:16]}…` (unchanged) |")
    L.append("| macro data | raw vintages re-downloaded 2026-11-04 and verified against "
             "`results/T02/raw_data_manifest.csv`: every first-release vintage file identical; the five OECD KEI "
             "revised-fallback files changed hash (same size and shape) and were used as re-downloaded, decided "
             "before any computation (`results/T02/raw_data_verification.md`); the raw set as used is kept in "
             "`data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz` |")
    L.append("| decision basis | 1x costs (v1.0's cost model), 2020-01..2026-09; 2x costs, 2005-2019, half A and "
             "the robustness checks reported, not decisive |\n")
    L.append("v1.0's figures remain \"OOS for v1.0 only\". T02's figures are reported separately and are not "
             "merged with v1.0's track record.\n")

    # 1
    L.append("## 1. Pre-registered pass/fail table\n")
    L.append("**1x costs (decisive).**\n")
    L.append(_crit_table(c1))
    L.append("\n" + _overall(c1) + "\n")
    bs = c1["bootstrap"]
    L.append(f"Bootstrap (criterion 1): paired circular block bootstrap, block {bs['block']} months, B = {bs['B']:,}, "
             f"seed {bs['seed']}; bootstrap dSR mean {bs['boot_mean']:+.3f}, SD {bs['boot_sd']:.3f}, "
             f"5%–95% range {bs['boot_q05']:+.3f} to {bs['boot_q95']:+.3f}.\n")
    L.append("Criterion 4 compares with v1.0's DSR at N = 7 as recorded in T01's report (0.619), as "
             "pre-registered; the value recomputed on this run's v1.0 returns is shown in brackets.\n")
    L.append("**2x costs (sensitivity, not decisive).**\n")
    L.append(_crit_table(c2))
    L.append(f"\nOverall at 2x costs: {'PASS' if c2['overall_pass'] else 'FAIL'}. (At 2x costs criterion 4 compares "
             "T02's 2x DSR with v1.0's 2x DSR at N = 7, as in T01's 2x table.)\n")

    # 2
    L.append("## 2. v1.0 and T02 side by side\n")
    L.append("Sharpe = mean/SD × √12 of monthly net returns; return = compounded; MaxDD on the compounded monthly "
             "index; ES97.5 = historical expected shortfall of monthly net returns (Acerbi-Tasche), as a loss; "
             "turnover = one-way notional traded per year, in multiples of capital; costs = cost drag per year.\n")
    L.append("**Test, 2020-01..2026-09, all 23 instruments (decisive).**\n")
    L.append(_perf(perf, "all", TESTP, ["v1.0", "T02"]))
    L.append("\n**Holdout, half B (BR, CO, ZA, TR, GB, FR, IT; 12 instruments, 5 currencies), 2020-01..2026-09.** "
             "Each strategy run as a stand-alone universe of half B; ECONMOM ranks over the half-B currencies.\n")
    L.append(_perf(perf, "half B", TESTP, ["v1.0", "T02"]))
    L.append("\n**In-sample context, 2005-2019 (cannot affect the decision).** v1.0 was designed on this period.\n")
    L.append(_perf(perf, "all", ISP, ["v1.0", "T02"]))
    L.append("\n**Context: half B 2005-2019, and half A (MX, CL, PL, ID, ES, DE, euro area) in both periods, 1x.**\n")
    ctx = pd.concat([perf[(perf.universe == "half B") & (perf.period == ISP)], perf[perf.universe == "half A"]])
    ctx = ctx[ctx.strategy.isin(["v1.0", "T02"]) & (ctx.costs == "1x")]
    L.append(_md(ctx[["universe", "period", "strategy", "months"] + SIDE[:6]].rename(columns=COLS)))

    L.append("\n**By year, 2020–2026 (2026 = January–September), all instruments.** Return compounded within the "
             "year; MaxDD within the year from the start-of-year level; turnover = notional traded in the year.\n")
    for cm in ("1x", "2x"):
        rows = []
        for y in sorted(yrs.year.unique()):
            g = yrs[(yrs.year == y) & (yrs.costs == cm)].set_index("strategy")
            v, t = g.loc["v1.0"], g.loc["T02"]
            rows.append({"year": int(y), "v1.0 return %": v["return_%"], "T02 return %": t["return_%"],
                         "T02 − v1.0 (pp)": t["return_%"] - v["return_%"], "v1.0 vol %": v["vol_%"],
                         "T02 vol %": t["vol_%"], "v1.0 Sharpe": v["sharpe"], "T02 Sharpe": t["sharpe"],
                         "v1.0 MaxDD %": v["max_drawdown_%"], "T02 MaxDD %": t["max_drawdown_%"],
                         "v1.0 turnover x": v["turnover_x"], "T02 turnover x": t["turnover_x"]})
        L.append(f"*{cm} costs*\n")
        L.append(_md(pd.DataFrame(rows)))
        L.append("")
    L.append("T02 estimates no parameters, so the spec's year-by-year walk-forward equals this single causal run; "
             "the years above are its walk-forward years.\n")

    # 3 sleeve
    L.append("## 3. The economic-momentum sleeve on its own\n")
    L.append("The FX book run through v1.0's frozen machinery with ECONMOM as its only signal (thirds, inverse-vol "
             "sizing, 10% book and total volatility, 6x cap, 25% band, v1.0 costs). The carry, trend and value "
             "sleeves are frozen v1.0 run with that one signal in both books.\n")
    sl = [SLV, "carry sleeve (v1.0 carry only)", "trend sleeve (v1.0 trend only)", "value sleeve (v1.0 value only)"]
    L.append(_perf(perf, "all", TESTP, sl))
    L.append("\nIn-sample context, 2005-2019:\n")
    L.append(_perf(perf, "all", ISP, sl, costs=("1x",)))
    L.append("\n**Alpha regression (criterion 5).** Sleeve net monthly returns on the net returns of the carry-, "
             "trend- and value-only runs, OLS with intercept, Newey-West standard errors with 3 lags.\n")
    rows = []
    for cm, c in (("1x", c1), ("2x", c2)):
        for p, r in c["alpha"].items():
            rows.append({"costs": cm, "window": p + (" — decisive" if (p == TESTP and cm == "1x") else ""),
                         "n": r["n"], "alpha %/yr": r["alpha_ann_%"], "t(alpha)": r["t_alpha"],
                         "beta carry": r["beta_carry"], "t": r["t_carry"], "beta trend": r["beta_trend"],
                         "t ": r["t_trend"], "beta value": r["beta_value"], "t  ": r["t_value"], "R2": r["r2"]})
    L.append(_md(pd.DataFrame(rows), 3))
    L.append("\n**Correlations of the sleeve's net monthly returns (1x) with the carry, trend and value sleeves "
             "and with v1.0.**\n")
    L.append(_md(cor.pivot_table(index=["period", "months"], columns="with", values="corr", sort=False)
                 .reset_index()[["period", "months", "carry", "trend", "value", "v1.0"]], 3))
    L.append("\n**Signal-level correlations** of the ECONMOM z-score with v1.0's FX carry, trend and value "
             "z-scores (pooled over currency-months, and the mean of the monthly cross-sectional correlations).\n")
    L.append(_md(scor.rename(columns={"pooled_corr": "pooled corr", "mean_monthly_xs_corr": "mean monthly XS corr"}), 3))

    # 4 DSR
    L.append("\n## 4. Deflated-Sharpe update\n")
    L.append("PSR and DSR (spec §0.2; `em_macro/mtstats.py`) from each strategy's realised 2020-01..2026-09 monthly "
             "Sharpe, skewness and raw kurtosis, T = 81. Noise-only null: trial-Sharpe SD = 1/√80 per month "
             "(decisive). Dispersed: SD 0.20 annualised. Adding T02 increments N by one: spec convention 8 → 9 "
             "(T02 at 9 compared with v1.0 at 7, the stricter comparison; v1.0 at 8 shown), ledger convention "
             "11 → 12.\n")
    for cm, c in (("1x", c1), ("2x", c2)):
        rows = []
        for who, key in (("v1.0", "spec N7"), ("v1.0", "spec N8"), ("T02", "spec N9"), ("v1.0", "ledger N11"),
                         ("T02", "ledger N12")):
            d = c["dsr"][who][key]
            rows.append({"strategy": who, "convention": key.split()[0], "N": d["N"], "SR_ann": d["SR_ann"],
                         "skew": d["skew"], "kurtosis": d["kurtosis_raw"], "PSR(SR*=0)": d["PSR(SR*=0)"],
                         "SR0 noise (ann.)": d["SR0_noise_ann"], "DSR noise": d["DSR_noise"],
                         "SR0 dispersed (ann.)": d["SR0_dispersed_ann"], "DSR dispersed": d["DSR_dispersed"]})
        L.append(f"*{cm} costs*\n")
        L.append(_md(pd.DataFrame(rows), 3))
        L.append("")

    # 5 robustness a
    L.append("## 5. Robustness (a): every macro input delayed three more months\n")
    L.append("Not a pass criterion. The ECONMOM score used at the end of month t is the one built from the "
             "vintages in force at the end of month t−3 (equivalently, every macro input, first-release or "
             "fallback, enters three months after its vintage date; the fallbacks are then lagged six months). "
             "Everything else is T02 unchanged. The same five statistics are computed for comparison.\n")
    L.append(_perf(perf, "all", TESTP, ["v1.0", "T02", DEL]))
    L.append("\nHalf B, 2020-01..2026-09:\n")
    L.append(_perf(perf, "half B", TESTP, ["v1.0", "T02", DEL], costs=("1x",)))
    L.append("\nIn-sample context, 2005-2019:\n")
    L.append(_perf(perf, "all", ISP, ["v1.0", "T02", DEL], costs=("1x",)))
    L.append("\nThe sleeve with delayed inputs:\n")
    L.append(_perf(perf, "all", TESTP, [SLV, "econ momentum sleeve (delayed 3m)"], costs=("1x",)))
    L.append("\nThe five statistics of the pass rule for the delayed version (1x; reported, not decisive):\n")
    L.append(_crit_table(crit["robustness delayed 3m 1x"]))
    L.append("\nDelayed version, all five statistics met: "
             f"{'yes' if crit['robustness delayed 3m 1x']['overall_pass'] else 'no'} (1x); "
             f"{'yes' if crit['robustness delayed 3m 2x']['overall_pass'] else 'no'} (2x).\n")
    L.append("By year, 2020–2026, 1x:\n")
    rows = []
    for y in sorted(yrs.year.unique()):
        g = yrs[(yrs.year == y) & (yrs.costs == "1x")].set_index("strategy")["return_%"]
        rows.append({"year": int(y), "v1.0 %": g["v1.0"], "T02 %": g["T02"], "T02 delayed 3m %": g[DEL]})
    L.append(_md(pd.DataFrame(rows)))

    # 6 robustness b
    L.append("\n## 6. Robustness (b): signal observations using revised or stale data\n")
    L.append("A signal observation is one (currency, month) ECONMOM score. **Revised** = at least one component "
             "came from a revised fallback series (pre-registration §2.4, lagged three months) instead of a "
             "first-release vintage. **Stale** = the economic-activity or inflation index ended more than six "
             "months before the decision month, so its sub-signals used the last published values "
             "(point-in-time; the series had stopped updating). Component-level shares count "
             "(currency, component, month) inputs that exist.\n")
    L.append(_md(fb.rename(columns=lambda c: c.replace("_", " ")), 2))
    L.append("\nBy currency, 2020-01..2026-09 (months with a score):\n")
    L.append(_md(fbc.rename(columns=lambda c: c.replace("_", " "))))
    L.append("\n**Every gap and fallback case, 2020-01..2026-09** (runs of decision months; any input not from "
             "an up-to-date first-release vintage). \"> 6 months old, index continues\" = that component's last "
             "observation is more than six months old, and the index keeps being extended by its other "
             "components; \"stale, index not updated\" = no "
             "component of that index is updated, and its last value is used.\n")
    L.append(_md(cases.astype(object).where(cases.notna(), "").rename(columns=lambda c: c.replace("_", " ")), 0))
    L.append("\n**First-release vs latest data (diagnostic, spec §13).** The same score rebuilt with each "
             "first-release input replaced by the latest vintage of the same source, truncated at the same last "
             "observation (revisions only; fallback inputs unchanged).\n")
    L.append(_md(flr.rename(columns=lambda c: c.replace("_", " ")), 3))

    # 7 notes
    L.append("\n## 7. Implementation notes\n")
    L.append("- **Integration.** ECONMOM is injected into the FX book's signal dictionary; frozen `book_weights` "
             "and `run` are called with `[\"carry\", \"trend\", \"value\", \"econmom\"]`. The bond book receives an "
             "all-missing ECONMOM frame, so its composite stays the mean of carry, trend and value; the run "
             "asserts that the bond-book weights equal v1.0's exactly in every universe and cost setting.")
    L.append("- **Source segments.** The pre-registration's §2.4 table is encoded in `econmom.SOURCE_PLAN`; its "
             "dates are read as decision months (for example Turkish retail sales: ALFRED vintages for decisions "
             "2018-07..2024-03, the revised series lagged three months from 2024-04).")
    L.append("- **Revised series.** The OECD KEI series of the same measure and activity. The KEI has no total "
             "industry ex construction for Indonesia and no retail series for Chile; there the latest print of "
             "the OECD revisions database (edition 2026-10) is used as the revised series, under the same rule "
             "(truncated at t−3, flagged).")
    L.append("- **Stale series** keep their last published value (point-in-time): the index's last month T(c,t) "
             "is the last month published in the vintage. This applies, in the test window, to the CPI of "
             "Mexico, South Africa, Chile, Turkey and Poland once the OECD stopped updating them, and to "
             "euro-area industrial production and retail sales after the ECB RTD's last vintage of those series "
             "(2025-10-29); see §6.")
    L.append("- **Chile CPI after 2023-12** is omitted: the pre-registered extension (\"FRED/BCCh CPI\") was not "
             "among the downloaded files, so Chile's CPI ends with the KEI series in 2023-12, and its inflation "
             "index keeps that last value.")
    L.append("- **Indonesia IP \"gaps\"**: an OECD edition is used unless its last observation is more than six "
             "months old, in which case the revised series (lag 3, flagged) is used.")
    L.append("- **Quarterly South African unemployment** is carried to the three months of each quarter within "
             "each vintage.")
    L.append("- **Chain breaks.** A month in which no component of an index has a growth rate breaks the chain; "
             "the index is the unbroken run ending at its last month.")
    L.append("- **ECB RTD**: euro-area IP `RTD.M.S0.Y.I_XCONS.X`, retail `RTD.M.S0.Y.O_RTXMOTVD.X`, unemployment "
             "rate `RTD.M.S0.S.L_UNETO.F`, HICP `RTD.M.S0.N.P_C_OV.X`; VALID_FROM compared by calendar date.")
    L.append("- **Moments and DSR.** Skewness is the pandas bias-corrected skewness; kurtosis is raw (normal = 3).")
    L.append("- **Runs.** The pre-registered run was made once at `da7fc20` and its outputs committed. Its 2x "
             "sensitivity table compared T02's 2x DSR with v1.0's 1x value (0.619), which mixes cost settings. The "
             "runner was changed (`6b43beb`) so that the 2x table compares with v1.0's 2x DSR, as T01's 2x table "
             "did. The 1x decisive comparison is unchanged at the pre-registered 0.619. The same deterministic "
             "pipeline was then run again. Every output file is byte-identical to the first run except the 2x "
             "criterion-4 row (and the same row of the delayed robustness check) and the run times in "
             "`RUN.json`. The 2x row changed from FAIL (0.293 vs 0.619) to PASS (0.293 vs 0.237); the 2x overall "
             "result is FAIL either way.")
    L.append("- **Packages.** statsmodels 0.15.0, yfinance 1.8.0 and pytest were installed in this session "
             "(listed in `requirements.txt`, absent from the container); pandas and numpy are the versions T01 "
             "used.")

    L.append("\n## 8. Not tested here: macro momentum in bonds\n")
    L.append("The bond version of macro momentum, trends in growth and inflation applied across bond markets "
             "(Brooks 2017, \"A Half Century of Macro Momentum\", AQR Capital Management), is a candidate future "
             "trial. It was not tested in T02, which applies economic momentum to the 10 currencies only "
             "(pre-registration §2.1). If run, it needs its own pre-registration and ledger row.\n")

    L.append("## 9. Files\n")
    L.append("- `results/T02/performance.csv`: every strategy × universe (all, half A, half B) × costs × period.")
    L.append("- `results/T02/monthly_net.csv`: monthly net returns of every run; `results/T02/by_year_2020_2026.csv`.")
    L.append("- `results/T02/pass_fail_1x.csv`, `results/T02/pass_fail_2x.csv`, `results/T02/criteria.json` "
             "(bootstrap, DSR, alpha regressions, and the same statistics for the delayed version).")
    L.append("- `results/T02/econmom_score_{all,halfB,halfA}.csv`: the ECONMOM scores; "
             "`econmom_score_latest_data.csv`; `econmom_n_subsignals.csv`; `econmom_fallback_flags.csv`.")
    L.append("- `results/T02/econmom_component_sources.csv` (source, flag, last observation of every input, every "
             "month), `econmom_index_age.csv`, `fallback_share.csv`, `fallback_by_currency_2020_2026.csv`, "
             "`gap_and_fallback_cases_2020_2026.csv`, `first_release_vs_latest.csv`.")
    L.append("- `results/T02/sleeve_correlations.csv`, `results/T02/signal_correlations.csv`.")
    L.append("- `results/T02/RUN.json`: run time, code commit, SHA-256 of code, pre-registration and input files, "
             "and the v1.0 reproduction check.")
    L.append("- Code: `em_macro/econmom.py` (signal), `em_macro/t02.py` (runner), `em_macro/t02_report.py`, "
             "`em_macro/t02_verify.py`. Tests: `tests/test_econmom.py`.")
    REPORT.write_text("\n".join(L) + "\n")
    print(REPORT.read_text())


if __name__ == "__main__":
    write()
