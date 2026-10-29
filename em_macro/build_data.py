"""Assemble the daily market panel and the data coverage report.

Output
------
data/processed/daily_panel.csv   one row per weekday 2005-01-03 .. latest, NaN on
                                 days with no observation (holidays, gaps)
data/processed/coverage.csv      one row per series
results/coverage_report.md       human-readable coverage + cross-checks
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sources as S
from . import yields as Y
from . import extra_yields as XY
from .config import (BCB_CDI, BIS_POLICY, COUNTRIES, CCY, FRED_LT_MONTHLY, FX_CHECK, FX_PRIMARY,
                     GLOBAL, NAMES, PROC, RESULTS, SARB_10Y, SARB_JIBAR3M, BANXICO_TIIE28, START)

SRC_LABEL = {"fred": "FRED", "yahoo": "Yahoo Finance", "bcb_sgs": "BCB SGS", "banxico": "Banxico SIE",
             "sarb": "SARB", "nbp": "NBP"}


def _fetch(src: str, ident, refresh=False) -> pd.Series:
    if src == "nbp":
        return S.nbp_fx(ident, refresh)
    return getattr(S, src)(ident, refresh)


def clean_spikes(s: pd.Series, jump: float = 0.08) -> tuple[pd.Series, int]:
    """Drop isolated bad ticks: a log move > ``jump`` that is (mostly) reversed
    the next observation.  Genuine crashes (e.g. TRY Aug-2018) do not reverse
    fully next day and are kept."""
    s = s.copy()
    r = np.log(s).diff()
    bad = (r.abs() > jump) & (r.shift(-1) * r < 0) & (r.shift(-1).abs() > 0.8 * r.abs())
    s[bad] = np.nan
    return s, int(bad.sum())


def build(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols, meta, notes = {}, [], []

    def add(name, s, source, desc, freq="daily"):
        s = s[s.index >= START].astype(float)
        cols[name] = s
        meta.append(dict(series=name, source=source, description=desc, frequency=freq))

    # --- FX (local per USD) ---
    for c in COUNTRIES:
        src, ident = FX_PRIMARY[c]
        s = _fetch(src, ident, refresh)
        if src == "yahoo":
            s, n_bad = clean_spikes(s)
            if n_bad:
                notes.append(f"{CCY[c]}: removed {n_bad} isolated Yahoo bad ticks (>8% move reversed next day).")
        add(f"FX_{c}", s, f"{SRC_LABEL[src]} {ident}", f"{CCY[c]} per USD, spot")
        if FX_CHECK[c]:
            src2, id2 = FX_CHECK[c]
            add(f"FXCHK_{c}", _fetch(src2, id2, refresh), f"{SRC_LABEL[src2]} {id2}",
                f"{CCY[c]} per USD, cross-check source")

    # --- 10-year local-currency government bond yields ---
    br, brm = Y.brazil_10y(refresh)
    add("Y10_BR", br, "Tesouro Direto (Tesouro Transparente) NTN-F",
        "~10y fixed-rate NTN-F yield, mid of buy/sell, interpolated to 10y (shorter before 2007)")
    add("Y10MAT_BR", brm, "derived", "maturity (years) underlying Y10_BR")
    mx, mxm = Y.mexico_10y(refresh)
    add("Y10_MX", mx, "Banxico SIE CF300 (SF45455/45478/45430)",
        "YTM of on-the-run Bono M in 7-10y bucket, computed from dirty price")
    add("Y10MAT_MX", mxm, "derived", "maturity (years) underlying Y10_MX")
    add("Y10_ZA", S.sarb(SARB_10Y, refresh), f"SARB {SARB_10Y}",
        "daily average yield, govt bonds 10y and longer")
    for c in ["TR", "ID", "PL"]:
        s, src, desc, freq = XY.daily_10y(c, refresh)
        if s is not None:
            add(f"Y10_{c}", s, src, desc, freq)

    # --- policy and short rates ---
    for c, area in BIS_POLICY.items():
        add(f"POL_{c}", S.bis_policy(area, refresh), f"BIS WS_CBPOL D.{area}", "central bank policy rate, %")
    cdi = S.bcb_sgs(BCB_CDI, refresh)
    add("STR_BR", ((1 + cdi / 100) ** 252 - 1) * 100, "BCB SGS 12", "CDI overnight, % p.a. (252-day)")
    add("STR_MX", S.banxico(BANXICO_TIIE28, refresh), f"Banxico {BANXICO_TIIE28}", "TIIE 28-day, %")
    add("STR_ZA", S.sarb(SARB_JIBAR3M, refresh), f"SARB {SARB_JIBAR3M}", "JIBAR 3-month, %")

    # --- global controls ---
    for name, (src, ident) in GLOBAL.items():
        add(name, _fetch(src, ident, refresh), f"{SRC_LABEL[src]} {ident}", name)

    end = max(s.index.max() for s in cols.values())
    idx = pd.bdate_range(START, end)
    panel = pd.DataFrame({k: v[~v.index.duplicated()].reindex(idx) for k, v in cols.items()})
    panel.index.name = "date"

    # monthly long-term yield cross-checks (not part of the daily panel)
    monthly = {c: S.fred(i, refresh) for c, i in FRED_LT_MONTHLY.items()}

    cov = coverage(panel, cols, pd.DataFrame(meta))
    PROC.mkdir(parents=True, exist_ok=True)
    panel.to_csv(PROC / "daily_panel.csv", float_format="%.6g")
    cov.to_csv(PROC / "coverage.csv", index=False)
    write_report(panel, cov, monthly, notes)
    return panel, cov


def coverage(panel: pd.DataFrame, raw: dict, meta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, m in meta.iterrows():
        s = raw[m.series].dropna()
        s = s[s.index >= START]
        p = panel[m.series]
        span = p.loc[s.index.min():]
        gaps = s.index.to_series().diff().dt.days
        rows.append(dict(series=m.series, source=m.source, description=m.description, frequency=m.frequency,
                         first=s.index.min().date(), last=s.index.max().date(), n_obs=len(s),
                         pct_weekdays_since_2005=round(100 * p.notna().mean(), 1),
                         pct_weekdays_since_first=round(100 * span.notna().mean(), 1),
                         max_gap_days=int(gaps.max()) if len(gaps) > 1 else None))
    return pd.DataFrame(rows)


def write_report(panel, cov, monthly, notes):
    L = ["# Data coverage report", "",
         f"Daily panel: {panel.index.min().date()} to {panel.index.max().date()}, "
         f"{len(panel)} weekdays. Coverage = share of weekdays with an observation "
         "(holidays count as missing, so ~96% is complete).", "",
         "## Series", "",
         "| series | source | first | last | obs | % weekdays since 2005 | % since first obs | max gap (days) |",
         "|---|---|---|---|---|---|---|---|"]
    for r in cov.itertuples():
        L.append(f"| {r.series} | {r.source} | {r.first} | {r.last} | {r.n_obs} | "
                 f"{r.pct_weekdays_since_2005} | {r.pct_weekdays_since_first} | {r.max_gap_days} |")
    L += ["", "## Cross-checks", "", "FX: correlation of daily log changes, primary vs. second source "
          "(timing differs: H.10 = noon New York, Yahoo ~ London close, PTAX/FIX/NBP = local fixings, "
          "so daily correlations below 1 are expected; 5-day correlations should be close to 1).", "",
          "| pair | daily corr | 5-day corr | median abs level gap % | n |", "|---|---|---|---|---|"]
    for c in COUNTRIES:
        if f"FXCHK_{c}" not in panel:
            continue
        a, b = np.log(panel[f"FX_{c}"]), np.log(panel[f"FXCHK_{c}"])
        d1 = pd.concat([a.ffill(limit=3).diff(), b.ffill(limit=3).diff()], axis=1).dropna()
        d5 = pd.concat([a.ffill(limit=3).diff(5), b.ffill(limit=3).diff(5)], axis=1).dropna()
        lv = ((a - b).abs() * 100).median()
        L.append(f"| {CCY[c]} | {d1.corr().iloc[0, 1]:.3f} | {d5.corr().iloc[0, 1]:.3f} | {lv:.2f} | {len(d1)} |")
    L += ["", "10-year yields vs. OECD monthly long-term rate (FRED IRLTLT01..., monthly average of daily):", "",
          "| country | corr of monthly levels | mean diff (pp) | n months |", "|---|---|---|---|"]
    for c, m in monthly.items():
        if f"Y10_{c}" not in panel:
            continue
        d = pd.concat([panel[f"Y10_{c}"].resample("MS").mean(), m], axis=1).dropna()
        d = d[d.index >= START]
        L.append(f"| {NAMES[c]} | {d.corr().iloc[0, 1]:.3f} | {(d.iloc[:, 0] - d.iloc[:, 1]).mean():+.2f} | {len(d)} |")
    L += ["", "## Gaps and caveats", ""] + [f"- {n}" for n in notes + XY.CAVEATS]
    (RESULTS).mkdir(parents=True, exist_ok=True)
    (RESULTS / "coverage_report.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    build()
