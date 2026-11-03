"""Builds results/diagnostics_v1.md from the tables saved by em_macro.diagnostics."""
from __future__ import annotations

import pandas as pd

from .config import ROOT
from .diagnostics import OUT, _md

PCT = "{:.1%}"


def _read(name):
    p = OUT / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


def section_attribution() -> list[str]:
    summ = _read("attribution_summary")
    if summ is None:
        return []
    L = ["## Step 1 — Attribution (spec Build 1)", "",
         "**How it was computed.**",
         "- **Re-run:** the frozen v1.0 (tag `v1.0-frozen`) was re-run without changes. Each instrument's monthly P&L is "
         "`w × r − cost`: currency weights decided at month t earn month t+1; bond weights earn t+2 because of the "
         "execution lag. The per-instrument P&L adds up exactly to v1.0's monthly net return.",
         "- **Units:** P&L is in % of capital a year, as the **arithmetic** mean of monthly net returns × 12. That is "
         "+4.0% a year for 2005–2019 and +6.25% for 2020-01 to 2026-09. The headline +6.0% is the geometric "
         "(compounded) rate.",
         "- **Shares:** shares are of total net P&L, so they can exceed 100% when other parts lose money.", ""]
    L += ["### Summary and flags", "", _md(summ.rename(columns={
        "total_net_%pa": "total net, % a year (arithmetic)", "top3_share": "top-3 share", "BRL_MXN_share": "BRL+MXN share",
        "flag_BRL_MXN_over_50%": "FLAG: BRL+MXN > 50%",
        "Brazil_Mexico_all_instruments_share": "Brazil+Mexico, all instruments, share"}),
        {"top-3 share": PCT, "BRL+MXN share": PCT, "Brazil+Mexico, all instruments, share": PCT}), ""]
    ctry = _read("attribution_country")
    for p, g in ctry.groupby("period", sort=False):
        L += [f"### By country, {p} (% a year)", "",
              _md(g.drop(columns="period"), {"share_of_total": PCT}), ""]
    ac = _read("attribution_asset_class")
    L += ["### By asset class (% a year)", "", _md(ac, {"share_of_total": PCT}), ""]
    sig = _read("attribution_signal")
    L += ["### By signal (% a year)", "",
          "Two methods are shown:",
          "- **Proportional (spec):** each position's monthly P&L is split by `share_k = (z_k/K)/S` if |S| > 0.1, else "
          "1/K. K is the number of signals available at the decision date and S is their mean (v1.0's composite).",
          "- **Shapley:** exact Shapley values over the 2³ signal subsets. Each subset is run through the same frozen "
          "machinery (selection, sizing, 10% vol target, costs). The value of a subset is its annualised mean net return.",
          "", _md(sig, {"share_of_total": PCT}), "",
          "Subset values used for the Shapley decomposition (% a year):", "",
          _md(_read("attribution_shapley_subsets")), ""]
    fac = _read("attribution_factors")
    L += ["### By factor exposure", "",
          "OLS of monthly net returns (%) on:",
          "- the dollar-index log change (Yahoo DX-Y.NYB);",
          "- changes in the US 2-year and 10-year yields (FRED DGS2, DGS10; bp);",
          "- the MSCI World return (Yahoo ^990100-USD-STRD, price index);",
          "- the IMF all-commodity index log change (FRED PALLFNFINDEXM, monthly average). A Bloomberg commodity index "
          "is not freely available;",
          "- an equal-weight EM FX basket spot return (BRL, MXN, ZAR, TRY, IDR, PLN, COP, CLP vs USD; + = EM up);",
          "- the change in the VIX.",
          "",
          "Standard errors are HAC with 3 lags. Contribution = coefficient × factor mean × 12. The dollar index and the EM "
          "basket are strongly negatively correlated, so their individual coefficients are not separately well "
          "identified.", ""]
    for p, g in fac.groupby("period", sort=False):
        L += [f"**{p}** (R² {g['r2'].iloc[0]:.2f}, n = {int(g['n'].iloc[0])}):", "",
              _md(g[["term", "coef", "t", "contribution_%pa"]], {"coef": "{:.3f}"}), ""]
    return L


def section_risk() -> list[str]:
    ts = _read("risk_monthly")
    if ts is None:
        return []
    pos = _read("risk_positions")
    L = ["## Step 2 — Risk audit (spec Build 2)", "",
         "**Positions:** each month-end, the positions that earn the next month under v1.0's accounting: currencies "
         "decided that month, bonds decided the month before.", "",
         "**Risk contributions:** RC_i = w_i(Σw)_i/σ_p, shown as shares of σ_p (they sum to 100%).", "",
         "**Factor shares (spec §7):** `β_f(Ωβ)_f/σ_p²`, where:",
         "- β = B'w;",
         "- B holds each instrument's OLS betas on two factors over the same window: the USD factor (dollar-index log "
         "return) and the EM factor (equal-weight EM FX basket return);",
         "- Ω is the factor covariance.",
         "",
         "Cross terms are split between the two factors by this formula, so a single factor's share can be negative or "
         "above 100%.", "",
         "**Shrinkage effect.** σ_p² uses the Ledoit-Wolf-shrunk covariance; the spec formula's factor covariance is not "
         "shrunk. In the unit test, a pure single-factor position therefore reads about 93% instead of 100%, so factor "
         "shares are slightly understated.", "",
         "Two versions are reported:",
         "- **A — spec version: Ledoit-Wolf on non-overlapping 3-day returns**, trailing 252 business days (84 "
         "observations). Daily prices exist only for the 10 currencies and the Brazilian, Mexican, South African and "
         "Turkish 10-year bonds, so version A covers those 14 instruments. Its coverage of v1.0's gross notional is "
         "reported.",
         "- **B — full book: Ledoit-Wolf on trailing 60 monthly returns**, all 23 instruments (bond returns from "
         "monthly-average yields).",
         ""]
    rows = []
    for v in ("A", "B"):
        for col, lab in ((f"{v}_usd_share", "USD factor share"), (f"{v}_em_share", "EM factor share"),
                         (f"{v}_usd_em_share", "USD + EM combined"), (f"{v}_sigma_p_%", "ex-ante vol, %"),
                         (f"{v}_top_position_share", "largest single-position risk share")):
            s = ts[col].dropna()
            rows.append({"version": v, "measure": lab, "average": s.mean(), "max": s.max(),
                         "month of max": ts.loc[s.idxmax(), "month"], "current book": s.iloc[-1],
                         "months": len(s)})
        if f"{v}_gross_notional_coverage" in ts:
            s = ts[f"{v}_gross_notional_coverage"].dropna()
            rows.append({"version": v, "measure": "coverage of v1.0 gross notional", "average": s.mean(),
                         "max": s.max(), "month of max": ts.loc[s.idxmax(), "month"], "current book": s.iloc[-1],
                         "months": len(s)})
    tab = pd.DataFrame(rows)
    pct = lambda r: r["measure"] != "ex-ante vol, %"
    tab_fmt = tab.copy()
    for c in ("average", "max", "current book"):
        tab_fmt[c] = [f"{v:.1%}" if pct(r) else f"{v:.1f}" for v, (_, r) in zip(tab[c], tab.iterrows())]
    L += ["### Summary, 2005–2026", "", _md(tab_fmt), ""]
    flags = []
    for v in ("A", "B"):
        avg = ts[f"{v}_usd_em_share"].dropna().mean()
        flags.append({"version": v, "average USD+EM share": f"{avg:.1%}",
                      "FLAG: average above 60%": "YES" if avg > 0.6 else "no"})
    L += ["### Flag", "", _md(pd.DataFrame(flags)), ""]
    cur = ts["month"].iloc[-1]
    for v, lab in (("A", "A (3-day, daily-priced)"), ("B", "B (monthly, full book)")):
        g = pos[(pos["version"] == lab) & (pos["month"] == cur)].sort_values("risk_share", ascending=False)
        L += [f"### Current book ({cur} month-end, held in {pd.Period(cur, 'M') + 1}), version {v}", "",
              _md(g[["instrument", "weight", "risk_share"]], {"weight": "{:.3f}", "risk_share": PCT}), ""]
    avgpos = (pos.groupby(["version", "instrument"])["risk_share"].agg(["mean", "max", "count"])
              .reset_index().sort_values(["version", "mean"], ascending=[True, False]))
    L += ["### Average risk share by position (months when held)", "",
          _md(avgpos.rename(columns={"mean": "average", "count": "months held"}),
              {"average": PCT, "max": PCT}), ""]
    return L


def section_stats() -> list[str]:
    st = _read("stats_v1")
    if st is None:
        return []
    tr = pd.read_csv(ROOT / "trials.csv")
    mo = _read("stats_moments")
    L = ["## Step 3 — Trial ledger and multiple-testing statistics (spec Build 3)", "",
         f"`trials.csv` has {len(tr)} rows in {tr['trial_group'].nunique()} distinct trial groups. "
         f"{int(tr['counted_in_spec_N7'].sum())} rows in {tr.loc[tr['counted_in_spec_N7'], 'trial_group'].nunique()} "
         "groups are the spec's N = 7. The sovereign fair-value v1 and its post-hoc v2 share one group, as in the spec. "
         "The rest come from this repository's history and are reported as a second N (\"ledger N\").",
         "Full hypotheses, samples, results and sources are in `trials.csv`.", "",
         _md(tr[["trial_id", "trial_group", "date_tested", "name", "result", "decision", "counted_in_spec_N7"]]), "",
         "Functions: `em_macro/mtstats.py`; tests: `tests/test_mtstats.py`, which reproduce every §0.2 number.",
         "- Inputs, as in the spec: SR 0.65, T = 81 months, monthly SR = 0.65/√12 = 0.1876. The actual test Sharpe is 0.654.",
         "- **Noise-only null:** trial-Sharpe SD = 1/√(T−1) per month.",
         "- **Dispersed trials:** SD 0.20 annualised.",
         "- **Moments:** kurtosis is raw (normal = 3).", "",
         "Moments of the actual v1.0 monthly net returns:", "", _md(mo), ""]
    cols = ["scenario", "trials", "skew", "kurtosis", "t", "p_two_sided", "PSR(SR*=0)", "SR0_noise_ann", "DSR_noise",
            "SR0_dispersed_ann", "DSR_dispersed", "MinTRL_90%_years", "MinTRL_95%_years", "MinTRL_90%_vs_SR0_years",
            "HL_Bonferroni_SR", "HL_Sidak_SR", "HL_BHY_SR"]
    L += ["### Statistics table", "", _md(st[cols], {"p_two_sided": "{:.3f}", "PSR(SR*=0)": "{:.3f}",
                                                    "DSR_noise": "{:.3f}", "DSR_dispersed": "{:.3f}",
                                                    "t": "{:.3f}"}), "",
          "Notes:",
          "- **What varies:** the naive t-statistic and the Harvey-Liu haircuts do not depend on skew and kurtosis; "
          "they change only with N.",
          "- **BHY = 0.00:** an adjusted p of at least 1 (a 100% haircut), with v1.0 treated as the top-ranked test.",
          "- **One spec claim does not reproduce.** §0.2 says MinTRL against SR* = 0.537 is \"more than 200 years\". The "
          "formula gives 131 years (S1, 90%) to 262 years (S3, 95%); 90% values are in the table. It exceeds 200 years "
          "only at 95% confidence.", ""]
    return L


def build() -> str:
    L = ["# Diagnostics of the frozen v1.0 systematic strategy", "",
         "Spec: `docs/research/algorithm_spec_2026-11.md` (Builds 1–3, §17.2).",
         "Freeze record: `docs/v1.0_freeze.md` (tag `v1.0-frozen` → commit 7886867). No trading logic was changed; "
         "every number here comes from re-running the frozen code.",
         "Tables: `results/diagnostics/*.csv`. Code: `em_macro/diagnostics.py`, `em_macro/mtstats.py`.", ""]
    L += section_attribution() + section_risk() + section_stats()
    summ = OUT / "summary.md"
    if summ.exists():
        L += [summ.read_text()]
    return "\n".join(L) + "\n"
