"""Write results/T20-T22_commodity_trials.md from the saved tables of `python -m em_macro.t2022 run`
(pre-registration section 7).  Mechanical: no editorial judgement beyond the pass/fail rules."""
from __future__ import annotations

import json

import pandas as pd

from .config import RESULTS

OUT = RESULTS / "T20-T22"
REPORT = RESULTS / "T20-T22_commodity_trials.md"
TRIALS = {"T20": "commodity carry", "T21": "basis-momentum", "T22": "diversified futures trend"}


def _f(x, nd=3):
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def write():
    crit = json.loads((OUT / "criteria.json").read_text())
    run = json.loads((OUT / "RUN.json").read_text())
    diag = json.loads((OUT / "diagnostics.json").read_text())
    b0 = json.loads((OUT / "build0.json").read_text())
    perf = pd.read_csv(OUT / "performance.csv")
    ex = crit["_extra"]
    L = []
    a = L.append
    a("# Trials T20–T22: commodity carry, basis-momentum and diversified futures trend against frozen v1.1 — results\n")
    a("**A4 and Amendment 4.** The Build 0 carry benchmark test A4 measured a correlation of "
      f"{b0['A4']['corr']:.3f} with AQR's commodity carry factor, against a threshold of 0.70. The A4 diagnostic found "
      "that AQR's own documented construction on these data correlates 0.679 "
      "(`results/T20-T22/build0_a4_diagnostic.md`). Under Amendment 4 (decided after those results), A4 is reported "
      "and does not gate the trials. In exchange, T20 and T21 must meet C1 at a Holm-adjusted p < 0.05 instead of "
      "0.10.\n")
    a("| item | value |\n|---|---|")
    a("| pre-registration | `docs/prereg/T20-T22_commodity_trials.md` with Amendments 1–4 |")
    a("| Build 0 | `results/T20-T22/build0.md` (committed before this run) |")
    a(f"| run | {run['run_started_utc']} to {run['run_finished_utc']} UTC, commit `{run['git_head_at_run'][:7]}`, "
      f"pandas {run['pandas']}, numpy {run['numpy']} |")
    rep = run["reproduction"]
    a(f"| reproduction | v1.0 tables identical: {rep['v1.0_identical']}; v1.1 reproduces T18: "
      f"{rep['v1.1_reproduces_T18']} |")
    a(f"| markets dropped (Build 0) | {', '.join(ex['dropped'])} |")
    a(f"| T22 universe | {len(ex['t22_universe'])} instruments: {' '.join(ex['t22_universe'])} |")
    a(f"| T20 Option A/B | A: {' '.join(c for c, o in ex['option'].items() if o == 'A')}; "
      f"B: {' '.join(c for c, o in ex['option'].items() if o == 'B')} |\n")
    a("Each trial's figures are reported separately and are never merged with v1.0's or v1.1's track record. "
      "v1.1's figures are \"T18's single test, OOS for v1.1 only\".\n")

    a("## 1. Pass/fail (decisive costs)\n")
    a("| trial | overall | C1 | C2 | C3 | C4 | S1 | S2 | S3 |\n|---|---|---|---|---|---|---|---|---|")
    for t in TRIALS:
        c = {x["#"]: x["pass"] for x in crit[t]["combined"] + crit[t]["sleeve"]}
        a(f"| {t} {TRIALS[t]} | **{'PASS' if crit[t]['overall_pass'] else 'FAIL'}** | " +
          " | ".join("pass" if c[k] else "FAIL" for k in ("C1", "C2", "C3", "C4", "S1", "S2", "S3")) + " |")
    for t in TRIALS:
        a(f"\n### {t} — {TRIALS[t]}\n")
        a("| # | criterion | measured | result |\n|---|---|---|---|")
        for x in crit[t]["combined"] + crit[t]["sleeve"]:
            a(f"| {x['#']} | {x['criterion']} | {x['value']} | {'pass' if x['pass'] else '**FAIL**'} |")

    a("\n## 2. Non-inferiority bootstrap and Holm correction (C1)\n")
    a("| trial | ΔSR | p (non-inferiority, raw) | Holm | threshold | superiority p (context) | bootstrap mean | SD | "
      "5%–95% | 2x costs: Holm p |\n|---|---|---|---|---|---|---|---|---|---|")
    for t in TRIALS:
        b = crit[t]["bootstrap"]
        thr = 0.05 if t in ("T20", "T21") else 0.10
        a(f"| {t} | {b['delta_sr']:+.4f} | {b['p_noninf']:.4f} | {crit[t]['p_holm']:.4f} | < {thr:.2f} | "
          f"{b['p_superiority']:.4f} | {b['boot_mean']:+.4f} | {b['boot_sd']:.4f} | {b['boot_q05']:+.3f} to "
          f"{b['boot_q95']:+.3f} | {crit[t]['p_holm_2x']:.4f} |")

    a("\n## 3. v1.1 and the combined books, 2020-01..2026-09\n")
    keys = ["v1.1|decisive"] + [f"v1.1+{t}|full|decisive" for t in TRIALS]

    def table(series, period):
        a("| book | Sharpe | return %/yr | vol %/yr | MaxDD % | ES97.5 % | turnover x/yr |\n|---|---|---|---|---|---|---|")
        for k in series:
            r = perf[(perf.series == k) & (perf.period == period)]
            if r.empty:
                continue
            r = r.iloc[0]
            a(f"| {k} | {_f(r.sharpe)} | {_f(r['ann_return_%'], 2)} | {_f(r['ann_vol_%'], 2)} | "
              f"{_f(r['max_drawdown_%'], 2)} | {_f(r['ES97.5_monthly_%'], 2)} | {_f(r.get('turnover_x_pa'), 2)} |")
    table(keys, "2020-01..2026-09")
    a("\n**Half B (holdout, C2)**, 2020-01..2026-09, against the full v1.1:\n")
    table(["v1.1|decisive"] + [f"v1.1+{t}|half B|decisive" for t in TRIALS], "2020-01..2026-09")
    a("\n**2x costs** (reported, not decisive):\n")
    table(["v1.1|2x"] + [f"v1.1+{t}|full|2x" for t in TRIALS], "2020-01..2026-09")
    a("\n**Context: 2000-01..2019-12** (v1.1 exists from its first live month):\n")
    table(keys, "2000-01..2019-12")
    a("\n**By year, 2020–2026** (%; 2026 = January–September):\n")
    by = diag["by_year_%"]
    yrs = sorted({y for v in by.values() for y in v})
    a("| series | " + " | ".join(yrs) + " |\n|---|" + "---|" * len(yrs))
    for k, v in by.items():
        a(f"| {k} | " + " | ".join(_f(v.get(y), 2) for y in yrs) + " |")

    a("\n## 4. Stand-alone sleeves (10% target, decisive costs)\n")
    for t in TRIALS:
        a(f"\n**{t}**\n")
        a("| universe | period | Sharpe | return %/yr | vol %/yr | MaxDD % | turnover x/yr |\n|---|---|---|---|---|---|---|")
        for uni in ("full", "half B", "half A"):
            for per in ("2000-01..2019-12", "2020-01..2026-09", "2000-01..2026-09"):
                r = perf[(perf.series == f"{t} sleeve|{uni}|decisive") & (perf.period == per)]
                if r.empty:
                    continue
                r = r.iloc[0]
                a(f"| {uni} | {per} | {_f(r.sharpe)} | {_f(r['ann_return_%'], 2)} | {_f(r['ann_vol_%'], 2)} | "
                  f"{_f(r['max_drawdown_%'], 2)} | {_f(r.get('turnover_x_pa'), 2)} |")

    a("\n## 5. Sleeve-level statistics\n")
    cw = ex["clark_west"]
    a("| statistic | value |\n|---|---|")
    for k, v in cw.items():
        a(f"| T20 Clark–West, {k} | CW t {_f(v['cw_t'])}, one-sided p {_f(v['p_one_sided'], 4)} "
          f"({v['months']} months) |")
    al = ex["t21_alpha_vs_t20"]
    a(f"| T21 alpha vs the T20 sleeve, 2000-01..2026-09 | {100 * al['alpha_ann']:.2f}%/yr, NW t {_f(al['alpha_t'])}; "
      f"beta {_f(al['beta'])} ({al['months']} months) |")
    a(f"| T21 mean net return, NW t | {_f(ex['t21_nw']['t'])} |")
    for t, v in ex["breakeven"].items():
        a(f"| {t} break-even cost multiple (2000-01..2026-09) | {_f(v, 2)} |")
    a(f"| carry's worst 8 months (v1.0 carry-only), 2020-01..2026-09 | {' '.join(ex['carry_worst_months'])} |")

    a("\n## 6. Deflated Sharpe (C4)\n")
    a("| book | N | SR | DSR (noise-only null) | DSR (dispersed, context) |\n|---|---|---|---|---|")
    d = crit["T20"]["dsr"]["v1.1"]
    a(f"| v1.1 | {d['N']} | {_f(d['SR_ann'])} | {_f(d['DSR_noise'], 4)} | {_f(d['DSR_dispersed'], 4)} |")
    for t in TRIALS:
        d = crit[t]["dsr"]["trial"]
        a(f"| v1.1 + {t} | {d['N']} | {_f(d['SR_ann'])} | {_f(d['DSR_noise'], 4)} | {_f(d['DSR_dispersed'], 4)} |")

    a("\n## 7. Diagnostics (section 3; not criteria)\n")
    a("**Correlations, 2020-01..2026-09** (stand-alone sleeves at decisive costs, v1.1, v1.0's carry sleeve, S&P 500):\n")
    C = pd.DataFrame(diag["corr_2020_2026"])
    a("| | " + " | ".join(C.columns) + " |\n|---|" + "---|" * len(C.columns))
    for i, row in C.iterrows():
        a(f"| {i} | " + " | ".join(_f(x, 2) for x in row) + " |")
    a("\n**v1.1's five worst months, 2020-01..2026-09** (%):\n")
    w = diag["v11_worst5"]
    cols = list(next(iter(w.values())).keys())
    a("| month | " + " | ".join(cols) + " |\n|---|" + "---|" * len(cols))
    for m, v in w.items():
        a(f"| {m} | " + " | ".join(_f(v[c], 2) for c in cols) + " |")
    a("\n| diagnostic | value |\n|---|---|")
    a(f"| T20 share of markets on Option A | {_f(diag['option_A_share'], 2)} |")
    a(f"| BM and carry signals, mean cross-sectional rank correlation | {_f(diag['bm_carry_signal_rank_corr_mean'])} |")
    a(f"| T20 and T21 sleeves, return correlation 2000-01..2026-09 | {_f(diag['t20_t21_sleeve_corr_2000_2026'])} |")
    for k, v in diag["t22_gross_by_asset_class_ann_%"].items():
        a(f"| T22 gross P&L, {k}, %/yr 2000-01..2026-09 | {_f(v, 2)} |")
    a(f"| T22 mean net currency-futures notional (long foreign currency), 2020-01..2026-09 | "
      f"{_f(diag['t22_net_fx_notional_mean'])} |")
    a(f"| T22 mean net bond-futures notional, 2020-01..2026-09 | {_f(diag['t22_net_bond_notional_mean'])} |")
    for t, v in diag["rounding_10m"].items():
        a(f"| {t} integer contracts at US$10m: median rounding error / position; position-months > 50% | "
          f"{_f(v['median_rounding_error_share'], 3)}; {v['position_months_over_50pct']} of {v['positions']} |")
    for t in ("T20", "T21"):
        a(f"| {t} mean net weight by sector, 2020-01..2026-09 | " +
          ", ".join(f"{k} {_f(v, 3)}" for k, v in diag[f"{t}_mean_net_weight_by_sector"].items()) + " |")
    a("\n## 8. Implementation readings (decisions taken under the simplest-reading rule)\n")
    for i, d in enumerate(run["decisions"], 1):
        a(f"{i}. {d}")
    a("\nNot reported: T22's P&L attribution by horizon and its net duration. The sleeve holds one blended position "
      "per instrument after the T18 band, so a horizon split would itself require an allocation rule. Duration data "
      "for the bond futures are not in the inputs, so net bond notional is shown instead.\n")
    a("## 9. Combinations\n")
    passing = [t for t in TRIALS if crit[t]["overall_pass"]]
    a(("Passing trials: " + ", ".join(passing) + ". Any combination of them would be a future pre-registered trial; "
       "none is tested here.") if passing else
      "No trial passed, so no combination is proposed. Any later variant is a new trial with its own "
      "pre-registration.")
    REPORT.write_text("\n".join(L) + "\n")
    print(f"wrote {REPORT}")
