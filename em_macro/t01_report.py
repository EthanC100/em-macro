"""results/T01_ts_trend.md from the tables saved by `python -m em_macro.t01 run`."""
from __future__ import annotations

import json

import pandas as pd

from .config import RESULTS

OUT = RESULTS / "T01"
REPORT = RESULTS / "T01_ts_trend.md"
TESTP, ISP = "2020-01..2026-09 (test)", "2005-2019 (in-sample, context)"
COLS = {"sharpe": "Sharpe", "ann_return_%": "return %/yr", "ann_vol_%": "vol %", "max_drawdown_%": "MaxDD %",
        "ES97.5_monthly_%": "ES97.5 % (monthly)", "turnover_x_pa": "turnover x/yr", "cost_drag_%_pa": "costs %/yr",
        "avg_gross_leverage": "avg gross lev.", "skew": "skew", "months": "months", "start": "start"}


def _md(df: pd.DataFrame, digits: int = 2) -> str:
    def f(v):
        if isinstance(v, float):
            return f"{v:.{digits}f}"
        if isinstance(v, bool):
            return "PASS" if v else "FAIL"
        return str(v).replace("|", "\\|")
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(f(v) for v in row) + " |" for row in df.itertuples(index=False))


def _perf(perf, uni, period, strategies, costs=("1x", "2x"), cols=None):
    cols = cols or ["sharpe", "ann_return_%", "ann_vol_%", "max_drawdown_%", "ES97.5_monthly_%", "turnover_x_pa",
                    "cost_drag_%_pa", "avg_gross_leverage"]
    d = perf[(perf.universe == uni) & (perf.period == period) & perf.strategy.isin(strategies) & perf.costs.isin(costs)]
    d = d.assign(_o=d.strategy.map({s: i for i, s in enumerate(strategies)})).sort_values(["costs", "_o"])
    d = d[["costs", "strategy", "start", "months"] + cols].rename(columns=COLS)
    return _md(d)


def write():
    perf = pd.read_csv(OUT / "performance.csv")
    ann = pd.read_csv(OUT / "annual_2020_2026.csv")
    crit = json.loads((OUT / "criteria.json").read_text())
    run = json.loads((OUT / "RUN.json").read_text())
    c1 = crit["1x"]
    L = []
    L.append("# Trial T01: time-series trend sleeve — results\n")
    L.append("| item | value |\n|---|---|")
    L.append("| pre-registration | `docs/prereg/T01_ts_trend.md`, committed in `dc71998` before any T01 code or run |")
    L.append("| ledger | `trials.csv` id **T12** (named T01; `T01` is v1.0's ledger id), group `G11_ts_trend_sleeve` |")
    L.append(f"| code at run | `{run['git_head_at_run'][:7]}` (branch `trial/T01-ts-trend`); `em_macro/tstrend.py`, "
             "`em_macro/t01.py`, `em_macro/holdout.py` |")
    L.append(f"| run | {run['run_started_utc']} to {run['run_finished_utc']} UTC; pandas {run['pandas']}, numpy "
             f"{run['numpy']}; data through {run['last_month']} |")
    rp = run["v1_reproduction"]
    L.append(f"| v1.0 reproduction | frozen `systematic.evaluate` on this run's inputs vs the committed tables: test "
             f"2020-01..2026-09 max abs diff {rp['test']['max_abs_diff_at_4dp']:.4f} ({rp['test']['rows']} rows), "
             f"design 2005-2019 max abs diff {rp['fit']['max_abs_diff_at_4dp']:.4f} ({rp['fit']['rows']} rows), at "
             "the files' 4 decimals |")
    L.append("| v1.0 baseline | tag `v1.0-frozen` = `7886867`; `em_macro/systematic.py` SHA-256 "
             f"`{run['sha256']['em_macro/systematic.py'][:16]}…` (unchanged) |")
    L.append("| decision basis | 1x costs (v1.0's cost model), 2020-01..2026-09; 2x costs and 2005-2019 reported, "
             "not decisive |\n")

    L.append("v1.0's figures remain \"OOS for v1.0 only\". T01's figures are reported separately and are not "
             "merged with v1.0's track record.\n")

    # 1. pass/fail
    L.append("## 1. Pre-registered pass/fail table\n")
    L.append("**1x costs (decisive).**\n")
    t = pd.DataFrame(c1["criteria"]).rename(columns={"pass": "result"})
    L.append(_md(t, 3))
    L.append(f"\n**Overall (all five required): {'PASS' if c1['overall_pass'] else 'FAIL'}** — criteria passed: "
             f"{sum(x['pass'] for x in c1['criteria'])} of 5 "
             f"({', '.join(str(x['#']) for x in c1['criteria'] if x['pass']) or 'none'}); failed: "
             f"{', '.join(str(x['#']) for x in c1['criteria'] if not x['pass']) or 'none'}.\n")
    bs = c1["bootstrap"]
    L.append(f"Bootstrap (criterion 1): paired circular block bootstrap, block {bs['block']} months, B = {bs['B']:,}, "
             f"seed {bs['seed']}; bootstrap dSR mean {bs['boot_mean']:+.3f}, SD {bs['boot_sd']:.3f}, "
             f"5%–95% range {bs['boot_q05']:+.3f} to {bs['boot_q95']:+.3f}.\n")
    L.append("**2x costs (sensitivity, not decisive).**\n")
    t2 = pd.DataFrame(crit["2x"]["criteria"]).rename(columns={"pass": "result"})
    L.append(_md(t2, 3))
    L.append(f"\nOverall at 2x costs: {'PASS' if crit['2x']['overall_pass'] else 'FAIL'}.\n")

    # 2. annual
    L.append("## 2. Annual returns, 2020–2026 (2026 = January–September), all instruments\n")
    rows = []
    for y in sorted(ann.year.unique()):
        g = ann[ann.year == y].set_index(["costs", "strategy"])["return_%"]
        rows.append({"year": int(y), "v1.0 1x %": g[("1x", "v1.0")], "T01 1x %": g[("1x", "T01")],
                     "T01 − v1.0 1x (pp)": g[("1x", "T01")] - g[("1x", "v1.0")],
                     "v1.0 2x %": g[("2x", "v1.0")], "T01 2x %": g[("2x", "T01")],
                     "trend sleeve 1x %": g[("1x", "trend sleeve (T01)")]})
    L.append(_md(pd.DataFrame(rows)))
    L.append("\nT01 estimates no parameters, so the spec's year-by-year walk-forward equals this single causal run; "
             "the years above are its walk-forward years.\n")

    # 3. summary stats
    L.append("## 3. Side-by-side statistics\n")
    L.append("Sharpe = mean/SD × √12 of monthly net returns; return = compounded; MaxDD on the compounded monthly "
             "index; ES97.5 = historical expected shortfall of monthly net returns (Acerbi-Tasche), as a loss; "
             "turnover = one-way notional traded per year, in multiples of capital.\n")
    L.append("**Test, 2020-01..2026-09, all 23 instruments.**\n")
    L.append(_perf(perf, "all", TESTP, ["v1.0", "T01"]))
    L.append("\n**Holdout, half B (BR, CO, ZA, TR, GB, FR, IT; 12 instruments), 2020-01..2026-09.** Each strategy run "
             "as a stand-alone universe of half B.\n")
    L.append(_perf(perf, "half B", TESTP, ["v1.0", "T01"]))
    L.append("\n**In-sample context, 2005-2019 (cannot affect the decision).** v1.0 was designed on this period.\n")
    L.append(_perf(perf, "all", ISP, ["v1.0", "T01"]))
    L.append("\n**Context: half B 2005-2019, and half A (MX, CL, PL, ID, ES, DE, euro area) in both periods.**\n")
    ctx = pd.concat([
        perf[(perf.universe == "half B") & (perf.period == ISP)],
        perf[(perf.universe == "half A")]])
    ctx = ctx[ctx.strategy.isin(["v1.0", "T01"]) & (ctx.costs == "1x")]
    L.append(_md(ctx[["universe", "period", "strategy", "months", "sharpe", "ann_return_%", "ann_vol_%",
                      "max_drawdown_%", "ES97.5_monthly_%"]].rename(columns=COLS)))

    # 4. trend sleeve
    L.append("\n## 4. The trend sleeve on its own\n")
    L.append("The stand-alone TSMOM sleeve (spec §2.2 blend, k ∈ {1, 3, 6, 12}, all 23 instruments) at 10% target "
             "volatility, with v1.0's 6x cap, no-trade band and costs. The carry sleeve is frozen v1.0 run with "
             "carry only.\n")
    L.append(_perf(perf, "all", TESTP, ["trend sleeve (T01)", "carry sleeve (v1.0 carry only)"]))
    L.append("\nIn-sample context, 2005-2019:\n")
    L.append(_perf(perf, "all", ISP, ["trend sleeve (T01)", "carry sleeve (v1.0 carry only)"], costs=("1x",)))
    L.append("\n**Correlation with the carry sleeve (1x costs).** Carry's worst 10% of months = the round(10% × "
             "months) months with the lowest carry-sleeve net return in each window.\n")
    rows = []
    for p, v in c1["carry_worst"].items():
        rows.append({"window": p + (" — decisive (criterion 5)" if p == TESTP else ""), "months": v["months"],
                     "corr, all months": v["corr_all"], "n worst": v["n_worst"],
                     "corr in carry's worst 10%": v["corr_worst10"], "carry mean in those months %": v["carry_mean_in_worst_%"],
                     "trend mean in those months %": v["trend_mean_in_worst_%"]})
    L.append(_md(pd.DataFrame(rows), 3))
    L.append(f"\nCarry's worst months, 2020-01..2026-09: {c1['carry_worst'][TESTP]['worst_months']}.\n")

    # 5. DSR
    L.append("## 5. Deflated-Sharpe update\n")
    L.append("PSR and DSR (spec §0.2; `em_macro/mtstats.py`) from each strategy's realised 2020-01..2026-09 monthly "
             "Sharpe, skewness and raw kurtosis, T = 81. Noise-only null: trial-Sharpe SD = 1/√80 per month "
             "(decisive, spec N). Dispersed: SD 0.20 annualised. Adding T01 increments N by one: spec convention "
             "7 → 8, ledger convention 10 → 11.\n")
    rows = []
    for who, key, conv in (("v1.0", "spec", "spec"), ("T01", "spec", "spec"), ("v1.0", "ledger", "ledger"),
                           ("T01", "ledger", "ledger")):
        d = c1["dsr"][who][key]
        rows.append({"strategy": who, "convention": conv, "N": d["N"], "SR_ann": d["SR_ann"], "skew": d["skew"],
                     "kurtosis": d["kurtosis_raw"], "PSR(SR*=0)": d["PSR(SR*=0)"], "SR0 noise (ann.)": d["SR0_noise_ann"],
                     "DSR noise": d["DSR_noise"], "SR0 dispersed (ann.)": d["SR0_dispersed_ann"],
                     "DSR dispersed": d["DSR_dispersed"]})
    L.append(_md(pd.DataFrame(rows), 3))

    # 6. diagnostic
    L.append("\n## 6. Diagnostic only — core sleeve alone (carry + value, no trend). CANNOT BE ADOPTED\n")
    L.append("This is frozen v1.0 run with the trend signal removed (identical to the T01 core sleeve before the "
             "trend sleeve is added). It was not a pre-registered candidate. Choosing it after seeing these "
             "results would be in-sample selection on 2020-2026, and its 2020-2026 mean return was already "
             "known from the v1.0 Shapley diagnostics. Shown for attribution only.\n")
    L.append(_perf(perf, "all", TESTP, ["v1.0", "core sleeve alone (diagnostic)", "T01"]))
    L.append("\nHalf B, 2020-01..2026-09:\n")
    L.append(_perf(perf, "half B", TESTP, ["v1.0", "core sleeve alone (diagnostic)", "T01"], costs=("1x",)))
    L.append("\nIn-sample context, 2005-2019:\n")
    L.append(_perf(perf, "all", ISP, ["v1.0", "core sleeve alone (diagnostic)", "T01"], costs=("1x",)))

    L.append("\n## 7. Notes\n")
    L.append("- **Ledger id.** The trial is called T01 in the pre-registration, branch and this report. Its "
             "`trials.csv` id is T12, because T01 is v1.0's ledger id.")
    L.append("- **EWMA volatility.** As pre-registered (§2.3), σ is an EWMA on each instrument's monthly "
             "excess-return series, with the 60-trading-day centre of mass converted to 60/21 months. Daily prices "
             "exist for only 14 of the 23 instruments, and v1.0's bond returns come from monthly-average yields.")
    L.append("- **Runs.** The first invocation of the run crashed in the criteria step: pandas 3 propagated a "
             "DataFrame held in `attrs`. All strategy runs had finished by then, and three tables had been written "
             "(`performance.csv`, `monthly_net.csv`, `annual_2020_2026.csv`). Those files were deleted without "
             "being opened. No result was printed or read. The fix (`62524ff`) strips `attrs` from the "
             "net-return series and changes no calculation. The same code then ran once, end to end, and its "
             "output is reported here.")
    L.append("- **v1.0 inputs.** Cached raw downloads (FRED, Yahoo, BIS and others) were re-downloaded in this "
             "session. The frozen v1.0 still reproduces both of its committed result tables exactly (see the "
             "header).")
    L.append("- **Moments and DSR.** Skewness is the pandas bias-corrected skewness; kurtosis is raw (normal = 3).")

    L.append("\n## 8. Files\n")
    L.append("- `results/T01/performance.csv`: every strategy × universe (all, half A, half B) × costs × period.")
    L.append("- `results/T01/monthly_net.csv`: monthly net returns of every run.")
    L.append("- `results/T01/annual_2020_2026.csv`, `results/T01/pass_fail_1x.csv`, `results/T01/pass_fail_2x.csv`, "
             "`results/T01/criteria.json` (bootstrap, DSR, carry-worst-month details).")
    L.append("- `results/T01/holdout_split.csv`: the half A / half B assignment (seed 20261103).")
    L.append("- `results/T01/RUN.json`: run time, code commit, SHA-256 of code, pre-registration and input files, and "
             "the v1.0 reproduction check.")
    L.append("- Code: `em_macro/tstrend.py` (sleeves and combination), `em_macro/t01.py` (runner and statistics), "
             "`em_macro/holdout.py`, `em_macro/t01_report.py`. Tests: `tests/test_tstrend.py`.")
    REPORT.write_text("\n".join(L) + "\n")
    print(REPORT.read_text())


if __name__ == "__main__":
    write()
