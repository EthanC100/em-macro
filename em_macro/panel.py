"""Country-month panel, 13 countries, 2005-01 onward (no modelling).

    python -m em_macro.panel          # builds data/processed/country_month_panel.csv
                                      # and results/panel_coverage.md

One row per country x month.  Each factor keeps its native timing:
market data are monthly averages (and month-end where noted); annual data
(IMF WEO, WGI, V-Dem, CBI) are assigned to every month of their calendar
year; quarterly data to the months of their quarter.  Annual values are
*final/latest-vintage* numbers, not what was known in real time -- see the
coverage report before using them in any forecasting exercise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import panel_sources as PS
from . import sources as S
from .config import EVENTS, PROC, RESULTS, ROOT

EXT = ROOT / "data" / "external"
START, = pd.period_range("2005-01", periods=1, freq="M")

COUNTRIES = ["BR", "MX", "FR", "ZA", "TR", "ID", "PL", "IT", "ES", "GB", "CO", "CL", "DE"]
FOCUS = ["BR", "MX", "FR"]
ISO3 = {"BR": "BRA", "MX": "MEX", "ZA": "ZAF", "TR": "TUR", "ID": "IDN", "PL": "POL", "FR": "FRA",
        "IT": "ITA", "ES": "ESP", "GB": "GBR", "CO": "COL", "CL": "CHL", "DE": "DEU"}
NAMES = {"BR": "Brazil", "MX": "Mexico", "ZA": "South Africa", "TR": "Turkey", "ID": "Indonesia",
         "PL": "Poland", "FR": "France", "IT": "Italy", "ES": "Spain", "GB": "United Kingdom",
         "CO": "Colombia", "CL": "Chile", "DE": "Germany"}
CCY = {"BR": "BRL", "MX": "MXN", "ZA": "ZAR", "TR": "TRY", "ID": "IDR", "PL": "PLN", "FR": "EUR",
       "IT": "EUR", "ES": "EUR", "GB": "GBP", "CO": "COP", "CL": "CLP", "DE": "EUR"}
EURO = {"FR", "IT", "ES", "DE"}
# spread benchmark: Bund for EU/UK members, US Treasury otherwise (Turkey priced vs. USTs)
EUROPEAN = {"FR", "IT", "ES", "GB", "PL", "DE"}

WEO = {"GGXCNL_NGDP": "fiscal_balance_gdp", "GGXONLB_NGDP": "primary_balance_gdp",
       "GGXWDG_NGDP": "gross_debt_gdp", "GGXWDN_NGDP": "net_debt_gdp", "BCA_NGDPD": "current_account_gdp",
       "NGDP_RPCH": "real_gdp_growth", "PCPIPCH": "inflation_weo"}
WGI = ["VA", "PV", "GE", "RQ", "RL", "CC"]

SCALE_SP = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B",
            "B-", "CCC+", "CCC", "CCC-", "CC", "C"]
SCALE_MD = ["Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3", "B1", "B2",
            "B3", "Caa1", "Caa2", "Caa3", "Ca", "C"]
RATING_NUM = {**{r: 21 - i for i, r in enumerate(SCALE_SP)}, **{r: 21 - i for i, r in enumerate(SCALE_MD)},
              "SD": 1, "RD": 1, "D": 1}
OUTLOOK_ADJ = {"positive": 1 / 3, "negative": -1 / 3, "watch_positive": 2 / 3, "watch_negative": -2 / 3,
               "developing": 0.0, "stable": 0.0}

SOURCES: dict[str, str] = {}          # column -> source description (filled while building)
NOTES: dict[str, str] = {}            # column -> caveat


def _months(end: pd.Period, start=START) -> pd.PeriodIndex:
    return pd.period_range(start, end, freq="M")


def _monthly(s: pd.Series, how: str = "mean") -> pd.Series:
    s = s.dropna()
    g = s.groupby(s.index.to_period("M"))
    return g.mean() if how == "mean" else g.last()


def _annual_to_months(s: pd.Series, months: pd.PeriodIndex) -> pd.Series:
    """Assign an annual value (index = year) to every month of that year."""
    return pd.Series([s.get(m.year, np.nan) for m in months], index=months)


def _read_ext(path):
    return pd.read_csv(path) if path.exists() else None


# --------------------------------------------------------------- market data
def market_block(months) -> dict[str, pd.DataFrame]:
    """Returns {column: DataFrame(index=months, columns=countries)}."""
    out = {}
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)

    # 10-year yields
    y = pd.DataFrame(index=months, columns=COUNTRIES, dtype=float)
    src = {}
    for c in ["BR", "MX", "ZA", "PL", "TR"]:
        y[c] = _monthly(daily[f"Y10_{c}"]).reindex(months)
        src[c] = "monthly mean of the project's daily 10y series (see results/coverage_report.md)"
    irs = PS.ecb_irs(["FR", "IT", "ES", "DE"])
    for c in ["FR", "IT", "ES", "DE"]:
        y[c] = irs[c].reindex(months)
        src[c] = "ECB IRS, EMU convergence 10y yield (monthly average)"
    oecd = PS.oecd_lt_rate(["GBR", "COL", "CHL", "IDN", "USA", "TUR"])
    for c in ["GB", "CO", "CL", "ID"]:
        y[c] = oecd[ISO3[c]].reindex(months)
        src[c] = "OECD MEI long-term interest rate IRLT (monthly average)"
    us10 = _monthly(daily["US10Y"]).reindex(months)
    out["y10"] = y
    out["spread_vs_de_bp"] = y.sub(y["DE"], axis=0) * 100
    out["spread_vs_us_bp"] = y.sub(us10, axis=0) * 100
    bench = pd.DataFrame({c: out["spread_vs_de_bp"][c] if c in EUROPEAN else out["spread_vs_us_bp"][c]
                          for c in COUNTRIES})
    bench["DE"] = out["spread_vs_us_bp"]["DE"]
    out["spread_bench_bp"] = bench
    SOURCES["y10"] = "; ".join(f"{c}: {s}" for c, s in src.items())
    SOURCES["spread_vs_de_bp"] = "y10 minus Germany y10 (ECB IRS)"
    SOURCES["spread_vs_us_bp"] = "y10 minus US 10y (FRED DGS10, monthly mean)"
    SOURCES["spread_bench_bp"] = "vs Germany for FR, IT, ES, GB, PL; vs US for BR, MX, ZA, TR, ID, CO, CL, DE"

    # FX: local currency per USD, monthly mean and month-end
    fx = {}
    for c in ["BR", "MX", "ZA", "TR", "ID", "PL"]:
        fx[c] = daily[f"FX_{c}"]
    eur = 1 / S.fred("DEXUSEU")
    for c in EURO:
        fx[c] = eur
    fx["GB"] = 1 / S.fred("DEXUSUK")
    fx["CO"] = PS.colombia_trm()
    fx["CL"] = PS.chile_dolar_observado()
    out["fx_per_usd_avg"] = pd.DataFrame({c: _monthly(fx[c]).reindex(months) for c in COUNTRIES})
    out["fx_per_usd_end"] = pd.DataFrame({c: _monthly(fx[c], "last").reindex(months) for c in COUNTRIES})
    out["fx_ret_vs_usd_pct"] = -100 * np.log(out["fx_per_usd_end"]).diff()
    SOURCES["fx_per_usd_avg"] = ("BRL/MXN/ZAR: FRED H.10; TRY/IDR/PLN: Yahoo Finance; COP: Banco de la Republica "
                                 "TRM (datos.gov.co); CLP: Banco Central de Chile dolar observado (mindicador.cl); "
                                 "EUR, GBP: FRED DEXUSEU/DEXUSUK inverted (FR/IT/ES/DE share EUR)")
    SOURCES["fx_per_usd_end"] = SOURCES["fx_per_usd_avg"] + "; last observation in month"
    SOURCES["fx_ret_vs_usd_pct"] = "-100*dlog(month-end local per USD); + = local currency up"
    yc = _monthly(S.yahoo("COP=X")).reindex(months)
    corr = np.log(out["fx_per_usd_avg"]["CO"]).diff().corr(np.log(yc).diff())
    NOTES["fx_per_usd_avg"] = (f"COP and CLP use official fixings because Yahoo's COP history has bad prints "
                               f"(monthly-change correlation with the TRM only {corr:.2f}). EUR and GBP rows are "
                               "identical across the euro countries.")

    # policy rates and inflation
    pol = {}
    for c in COUNTRIES:
        area = "XM" if c in EURO else c
        pol[c] = _monthly(S.bis_policy(area)).reindex(months)
    out["policy_rate"] = pd.DataFrame(pol)
    cpi = pd.DataFrame({c: PS.bis_cpi_yoy(c).reindex(months) for c in COUNTRIES})
    out["cpi_yoy"] = cpi
    out["real_policy_rate"] = out["policy_rate"] - cpi
    SOURCES["policy_rate"] = ("BIS WS_CBPOL daily, monthly mean; euro countries = BIS euro-area series (XM), "
                              "which follows the ECB MRO rate and later the deposit facility rate -- both ECB "
                              "rates are also in the panel as ecb_mro_rate / ecb_deposit_rate")
    SOURCES["cpi_yoy"] = "BIS WS_LONG_CPI national CPI, y/y %"
    SOURCES["real_policy_rate"] = "policy_rate minus cpi_yoy (ex post, same month)"

    # reserves (USD m, excl. gold), monthly where FRED carries IMF IFS
    res = {}
    for c in COUNTRIES:
        try:
            res[c] = _monthly(S.fred(f"TRESEG{c}M052N"), "last").reindex(months)
        except RuntimeError:
            res[c] = pd.Series(np.nan, index=months)
    out["reserves_usd_m"] = pd.DataFrame(res)
    SOURCES["reserves_usd_m"] = "IMF IFS total reserves excl. gold via FRED TRESEG<cc>M052N (monthly)"
    NOTES["reserves_usd_m"] = "Colombia and Chile are not on FRED; see reserves_months_imports (annual) for them."
    return out


def global_block(months) -> pd.DataFrame:
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    g = pd.DataFrame(index=months)
    g["us10y"] = _monthly(daily["US10Y"]).reindex(months)
    g["dxy"] = _monthly(daily["DXY"]).reindex(months)
    g["vix"] = _monthly(daily["VIX"]).reindex(months)
    g["fed_funds"] = _monthly(daily["US_FF"]).reindex(months)
    g["ecb_deposit_rate"] = _monthly(PS.ecb_series("FM/D.U2.EUR.4F.KR.DFR.LEV")).reindex(months)
    mro = PS.ecb_series("FM/D.U2.EUR.4F.KR.MRR_FR.LEV")            # fixed-rate tenders from Oct 2008
    mbr = PS.ecb_series("FM/D.U2.EUR.4F.KR.MRR_MBR.LEV")           # minimum bid rate before that
    g["ecb_mro_rate"] = _monthly(mro.dropna().combine_first(mbr.dropna())).reindex(months)
    SOURCES.update({"us10y": "FRED DGS10", "dxy": "Yahoo DX-Y.NYB", "vix": "FRED VIXCLS", "fed_funds": "FRED DFF",
                    "ecb_deposit_rate": "ECB FM DFR",
                    "ecb_mro_rate": "ECB FM MRO fixed rate (from Oct 2008), minimum bid rate before"})
    return g


# ---------------------------------------------------------------- annual data
def annual_block(months) -> dict[str, pd.DataFrame]:
    out = {}
    vint = {}
    for code, name in WEO.items():
        cols = {}
        for c in COUNTRIES:
            s, upd = PS.imf_weo(ISO3[c], code)
            cols[c] = s
            vint[c] = upd
        df = pd.DataFrame(cols)
        out[name] = pd.DataFrame({c: _annual_to_months(df[c], months) for c in COUNTRIES})
        SOURCES[name] = f"IMF WEO {code}, latest vintage (annual, assigned to calendar-year months)"
        if name == "gross_debt_gdp":
            out["debt_change_1y_pp"] = pd.DataFrame(
                {c: _annual_to_months(df[c].diff(), months) for c in COUNTRIES})
            out["debt_change_next5y_pp"] = pd.DataFrame(
                {c: _annual_to_months(df[c].shift(-5) - df[c], months) for c in COUNTRIES})
            SOURCES["debt_change_1y_pp"] = "gross_debt_gdp(t) - gross_debt_gdp(t-1), WEO latest vintage"
            SOURCES["debt_change_next5y_pp"] = ("gross_debt_gdp(t+5) - gross_debt_gdp(t), WEO latest vintage: "
                                                "realised history + current projections")
    NOTES["gross_debt_gdp"] = ("WEO latest vintage (country update dates: "
                               + ", ".join(f"{c} {v}" for c, v in vint.items()) + "). Real-time vintages "
                               "(what was known at each date) are not included: imf.org WEO vintage files "
                               "were rate-limited (HTTP 429) during the build.")
    NOTES["debt_change_next5y_pp"] = ("Ex post: for past years this is the realised 5-year change; for recent "
                                      "years it mixes outturns with the latest projections (to 2031). Do not "
                                      "use as an ex-ante expectation.")

    iso = [ISO3[c] for c in COUNTRIES]
    for k in WGI:
        df = PS.worldbank(iso, f"GOV_WGI_{k}.EST", source=3)
        out[f"wgi_{k.lower()}"] = pd.DataFrame({c: _annual_to_months(df.get(ISO3[c], pd.Series(dtype=float)), months)
                                                for c in COUNTRIES})
        SOURCES[f"wgi_{k.lower()}"] = f"World Bank WGI {k}.EST (annual estimate, -2.5..2.5)"
    for ind, name in [("FI.RES.TOTL.MO", "reserves_months_imports"), ("FI.RES.TOTL.CD", "reserves_usd_annual")]:
        df = PS.worldbank(iso, ind)
        out[name] = pd.DataFrame({c: _annual_to_months(df.get(ISO3[c], pd.Series(dtype=float)), months)
                                  for c in COUNTRIES})
        SOURCES[name] = f"World Bank {ind} (annual)"
    return out


# ------------------------------------------------------ research / agent files
def external_block(months) -> dict[str, pd.DataFrame]:
    out = {}
    iso2 = {v: k for k, v in ISO3.items()}
    st = EXT / "structural"

    cbi = _read_ext(st / "cbi.csv")
    if cbi is not None:
        for col in [c for c in ("cbie_index", "garriga_lvau", "garriga_lvaw") if c in cbi]:
            p = cbi.pivot_table(index="year", columns="iso3", values=col)
            out[col] = pd.DataFrame({c: _annual_to_months(p.get(ISO3[c], pd.Series(dtype=float)), months)
                                     for c in COUNTRIES})
            SOURCES[col] = "data/external/structural/cbi.csv (see cbi_SOURCE.md)"
    vd = _read_ext(st / "vdem.csv")
    if vd is not None:
        for col in ("v2x_jucon", "v2juhcind", "v2juncind", "v2x_rule", "v2x_corr"):
            if col in vd:
                p = vd.pivot_table(index="year", columns="iso3", values=col)
                out[f"vdem_{col}"] = pd.DataFrame({c: _annual_to_months(p.get(ISO3[c], pd.Series(dtype=float)),
                                                                        months) for c in COUNTRIES})
                SOURCES[f"vdem_{col}"] = "data/external/structural/vdem.csv (V-Dem; see vdem_SOURCE.md)"
    dh = _read_ext(st / "debt_holders.csv")
    if dh is not None:
        # sources measure different things (coverage, valuation, government level), so
        # each keeps its own column instead of being spliced
        tag = np.select([dh["source"].str.contains("Arslanalp"), dh["source"].str.contains("Quarterly Public"),
                         dh["source"].str.contains("Eurostat")], ["at", "qpsd", "eurostat"], "other")
        dh = dh.assign(tag=tag, q_or_a=dh["freq"].str.upper().str[0])
        dh = dh.sort_values("q_or_a", ascending=False)      # quarterly rows win over annual ones
        for col in ("foreign_share_pct", "fx_share_pct"):
            for src in ("at", "qpsd", "eurostat"):
                frames = {}
                for c in COUNTRIES:
                    g = dh[(dh["iso3"] == ISO3[c]) & (dh["tag"] == src)].dropna(subset=[col])
                    s = {}
                    for r in g.itertuples():
                        per = str(r.period)
                        if r.q_or_a == "Q":
                            q = pd.Period(per, freq="Q")
                            ms = pd.period_range(q.asfreq("M", "s"), q.asfreq("M", "e"), freq="M")
                        else:
                            ms = pd.period_range(f"{int(float(per))}-01", f"{int(float(per))}-12", freq="M")
                        for m in ms:
                            s.setdefault(m, getattr(r, col))
                    frames[c] = pd.Series(s, dtype=float).reindex(months)
                df = pd.DataFrame(frames)
                if df.notna().any().any():
                    name = f"debt_{col.replace('_pct', '')}_{src}"
                    out[name] = df
                    SOURCES[name] = {"at": "Arslanalp-Tsuda sovereign investor base (IMF, 2016 vintage, to 2016Q2)",
                                     "qpsd": "World Bank/IMF Quarterly Public Sector Debt (API source 20)",
                                     "eurostat": "Eurostat gov_10q_ggdebt (quarterly) / gov_10dd_ggd (annual)"}[src] \
                        + "; % of general/central government debt; data/external/structural/debt_holders.csv"
        NOTES["debt_foreign_share_at"] = ("Levels differ across sources (e.g. GBR 2010Q4: 26.2% A-T vs 16.8% QPSD); "
                                          "never splice them. Euro-area 'foreign' includes other euro residents.")

    tg = _read_ext(st / "inflation_targets.csv")
    if tg is not None:
        tgt = pd.DataFrame(index=months, columns=COUNTRIES, dtype=float)
        lo, hi = tgt.copy(), tgt.copy()
        for r in tg.itertuples():
            c = iso2.get(r.iso3)
            if c is None:
                continue
            s = pd.Period(pd.Timestamp(r.start_date), "M")
            e = pd.Period(pd.Timestamp(r.end_date), "M") if isinstance(r.end_date, str) and r.end_date else months[-1]
            sel = (months >= s) & (months <= e)
            point = r.target_point_pct
            if pd.isna(point):            # band-only regimes: midpoint; ECB pre-2021 "below 2%": the ceiling
                point = (r.band_low_pct + r.band_high_pct) / 2 if pd.notna(r.band_low_pct) else r.band_high_pct
            tgt.loc[sel, c] = point
            lo.loc[sel, c] = r.band_low_pct
            hi.loc[sel, c] = r.band_high_pct
        out["inflation_target"] = tgt
        out["inflation_target_low"] = lo
        out["inflation_target_high"] = hi
        SOURCES["inflation_target"] = ("data/external/structural/inflation_targets.csv (central bank sources); "
                                       "point target, else band midpoint (e.g. SARB 3-6% -> 4.5), else ceiling "
                                       "(ECB 'below but close to 2%' before Jul 2021 -> 2.0)")
        SOURCES["inflation_target_low"] = "lower tolerance band (blank where none, e.g. UK, ECB)"
        SOURCES["inflation_target_high"] = "upper tolerance band / ceiling"

    im = _read_ext(st / "imf_programmes.csv")
    if im is not None:
        flag = pd.DataFrame(0.0, index=months, columns=COUNTRIES)
        fac = pd.DataFrame("", index=months, columns=COUNTRIES)
        for r in im.itertuples():
            c = iso2.get(r.iso3)
            if c is None or not isinstance(r.approval_date, str):
                continue
            s = pd.Period(pd.Timestamp(r.approval_date), "M")
            e = (pd.Period(pd.Timestamp(r.expiry_date), "M") if isinstance(r.expiry_date, str) and r.expiry_date
                 else months[-1])
            sel = (months >= s) & (months <= e)
            flag.loc[sel, c] = 1.0
            fac.loc[sel, c] = r.facility
        out["imf_programme"] = flag
        out["imf_facility"] = fac
        SOURCES["imf_programme"] = "data/external/structural/imf_programmes.csv (IMF lending history)"
    return out


def _norm_outlook(x) -> str:
    """'watch negative', 'review for downgrade', 'rating watch negative' -> watch_negative, etc."""
    s = str(x).strip().lower()
    if any(w in s for w in ("watch", "review", "creditwatch")):
        if any(w in s for w in ("neg", "down")):
            return "watch_negative"
        if any(w in s for w in ("pos", "up")):
            return "watch_positive"
        return "developing"
    for k in ("positive", "negative", "developing", "stable"):
        if k in s:
            return k
    return s


def ratings_block(months) -> dict[str, pd.DataFrame]:
    files = sorted((EVENTS / "raw").glob("rating_actions_*.csv"))
    if not files:
        return {}
    ra = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    ra["date"] = pd.to_datetime(ra["date"], errors="coerce")
    ra = ra.dropna(subset=["date"]).sort_values("date")
    ra["agency"] = ra["agency"].str.replace("’", "'").str.strip()
    iso2 = {v: k for k, v in ISO3.items()}
    out = {}
    num = {}
    for agency, short in [("S&P", "sp"), ("Moody's", "moodys"), ("Fitch", "fitch")]:
        lvl = pd.DataFrame(index=months, columns=COUNTRIES, dtype=float)
        adj = lvl.copy()
        for c in COUNTRIES:
            g = ra[(ra["iso3"] == ISO3[c]) & (ra["agency"].str.lower() == agency.lower())]
            if g.empty:
                continue
            r_num = g["rating_after"].astype(str).str.strip().map(RATING_NUM)
            o_adj = g["outlook_after"].map(_norm_outlook).map(OUTLOOK_ADJ)
            s_lvl = pd.Series(r_num.values, index=g["date"].values).groupby(level=0).last()
            s_adj = pd.Series((r_num + o_adj.fillna(0)).values, index=g["date"].values).groupby(level=0).last()
            me = months.to_timestamp(how="end")
            lvl[c] = s_lvl.reindex(s_lvl.index.union(me)).ffill().reindex(me).values
            adj[c] = s_adj.reindex(s_adj.index.union(me)).ffill().reindex(me).values
        out[f"rating_{short}"] = lvl
        num[short] = adj
        SOURCES[f"rating_{short}"] = (f"{agency} long-term FC sovereign rating, month-end, numeric (AAA/Aaa=21 ... "
                                      "C=1); data/events/raw/rating_actions_*.csv")
    out["rating_avg_outlook_adj"] = (num["sp"] + num["moodys"] + num["fitch"]) / 3
    SOURCES["rating_avg_outlook_adj"] = "mean of the three agencies' numeric ratings incl. outlook (+/-1/3, watch +/-2/3)"
    acts = ra[ra["action"].isin(["upgrade", "downgrade", "outlook_change", "watch_on", "watch_off"])]
    for kind in ("upgrade", "downgrade"):
        g = acts[acts["action"] == kind]
        cnt = g.groupby([g["iso3"].map(iso2), g["date"].dt.to_period("M")]).size().unstack(0)
        have = [c for c in COUNTRIES if (ra["iso3"] == ISO3[c]).any()]   # zero only where histories exist
        out[f"rating_{kind}s_n"] = cnt.reindex(index=months, columns=COUNTRIES)
        out[f"rating_{kind}s_n"][have] = out[f"rating_{kind}s_n"][have].fillna(0)
        SOURCES[f"rating_{kind}s_n"] = f"number of {kind}s across S&P/Moody's/Fitch in the month"
    return out


PARTY_MEASURES = {   # parties_*.csv column -> panel suffix, description
    "parlgov_left_right": ("lr_parlgov", "ParlGov expert-survey left-right, 0-10"),
    "ches_lrecon": ("lr_econ_ches", "Chapel Hill Expert Survey economic left-right, 0-10"),
    "vparty_v2pariglef": ("lr_econ_vparty", "V-Party v2pariglef economic left-right (higher = right)"),
    "gps_lr_econ": ("lr_econ_gps", "Global Party Survey 2019 economic left-right"),
    "vparty_v2xpa_popul": ("populism_vparty", "V-Party v2xpa_popul populism index, 0-1"),
    "gps_populism": ("populism_gps", "Global Party Survey 2019 populism"),
    "populist_popu_list": ("populist_popu_list", "PopuList populist flag (Europe only)"),
}


def politics_block(months) -> dict[str, pd.DataFrame]:
    pol = EXT / "politics"
    cab_files = sorted(pol.glob("cabinets_*.csv")) if pol.exists() else []
    if not cab_files:
        return {}
    cab = pd.concat([pd.read_csv(f) for f in cab_files], ignore_index=True)
    cab["start"] = pd.to_datetime(cab["start_date"], errors="coerce")
    cab["end"] = pd.to_datetime(cab["end_date"], errors="coerce")
    cab = cab.dropna(subset=["start"]).sort_values("start")
    pfiles = sorted(pol.glob("parties_*.csv"))
    parties = pd.concat([pd.read_csv(f) for f in pfiles], ignore_index=True) if pfiles else pd.DataFrame()
    measures = {k: v for k, v in PARTY_MEASURES.items() if k in parties}
    keys = ["gov_seat_share", "gov_n_parties", "gov_minority", "n_governments_prior5y"]
    keys += [f"{who}_{suf}" for suf, _ in measures.values() for who in ("head_party", "gov_parties")]
    out = {k: pd.DataFrame(index=months, columns=COUNTRIES, dtype=float) for k in keys}
    me = months.to_timestamp(how="end").normalize()      # last calendar day of the month
    for c in COUNTRIES:
        g = cab[cab["iso3"] == ISO3[c]]
        if g.empty:
            continue
        pc = parties[parties["iso3"] == ISO3[c]] if len(parties) else pd.DataFrame()
        for m, t in zip(months, me):
            out["n_governments_prior5y"].loc[m, c] = ((g["start"] > t - pd.DateOffset(years=5))
                                                      & (g["start"] <= t)).sum()
            cur = g[(g["start"] <= t) & (g["end"].isna() | (g["end"] >= t))]
            if cur.empty:
                continue
            r = cur.iloc[-1]
            parts = [x.strip() for x in str(r.get("parties", "")).split(";") if x.strip() and x != "nan"]
            share = pd.to_numeric(r.get("seat_share"), errors="coerce")
            if pd.notna(share) and share <= 1:
                share *= 100
            technocratic = not parts and str(r.get("caretaker", "")).upper() == "Y"
            if technocratic:              # technocratic cabinet without party ministers (Monti): not 0%
                share = np.nan
            out["gov_seat_share"].loc[m, c] = share
            out["gov_n_parties"].loc[m, c] = np.nan if technocratic else len(parts)
            out["gov_minority"].loc[m, c] = float(share < 50) if pd.notna(share) else np.nan
            for col, (suf, _) in measures.items():
                out[f"head_party_{suf}"].loc[m, c] = _party_score(pc, r.get("head_party"), col, t.year)
                vals = [_party_score(pc, p_, col, t.year) for p_ in parts]
                vals = [v for v in vals if pd.notna(v)]
                out[f"gov_parties_{suf}"].loc[m, c] = np.mean(vals) if vals else np.nan
    SOURCES["gov_seat_share"] = ("lower-house seat share (%) of parties holding cabinet posts at cabinet start; "
                                 "data/external/politics/cabinets_*.csv (ParlGov + Wikipedia/official extensions; "
                                 "presidential systems: governing coalition, see NOTES files)")
    SOURCES["gov_n_parties"] = "number of parties holding cabinet posts (coalition size)"
    SOURCES["gov_minority"] = "1 if gov_seat_share < 50"
    SOURCES["n_governments_prior5y"] = "cabinets/government spells starting in the 5 years up to month end"
    for col, (suf, desc) in measures.items():
        SOURCES[f"head_party_{suf}"] = f"{desc}; party of the head of government; latest reference election <= year"
        SOURCES[f"gov_parties_{suf}"] = f"{desc}; unweighted mean over cabinet parties"
    NOTES["head_party_lr_econ_vparty"] = ("V-Party (v2) ends with 2019 elections; later months carry forward each "
                                          "party's latest scored election. Same for gov_parties_* V-Party columns.")
    NOTES["gov_seat_share"] = ("Seat counts are at cabinet start (not updated for defections). Turkey after 2018: "
                               "People's Alliance; France 2017-2020: ParlGov counts LR in Philippe II/Castex "
                               "(see politics NOTES).")
    return out


def _party_score(pc: pd.DataFrame, party, col: str, year: int) -> float:
    if pc is None or not len(pc) or party is None or pd.isna(party):
        return np.nan
    g = pc[pc["party"].astype(str).str.strip().str.lower() == str(party).strip().lower()]
    if g.empty or col not in g:
        return np.nan
    yr = pd.to_numeric(g.get("vparty_year"), errors="coerce") if "vparty_year" in g else pd.Series(np.nan, g.index)
    g = g.assign(_y=yr).dropna(subset=[col])
    past = g[g["_y"].isna() | (g["_y"] <= year)].sort_values("_y")
    return float(past[col].iloc[-1]) if len(past) else np.nan


# ---------------------------------------------------------------- assembly
def build(start: str | None = None, write: bool = True) -> pd.DataFrame:
    """start: first month (default 2005-01).  The risk model builds from 2004-01
    with write=False so that 12-month publication lags have data for 2005."""
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    end = pd.Period(daily.index.max(), "M")
    months = _months(end, pd.Period(start, "M") if start else START)
    blocks = {}
    for f in (market_block, annual_block, external_block, ratings_block, politics_block):
        blocks.update(f(months))
    if "inflation_target" in blocks:
        blocks["inflation_vs_target_pp"] = blocks["cpi_yoy"] - blocks["inflation_target"]
        SOURCES["inflation_vs_target_pp"] = "cpi_yoy minus inflation_target"
        hi, lo = blocks["inflation_target_high"], blocks["inflation_target_low"]
        cpi = blocks["cpi_yoy"]
        outside = ((cpi > hi) | (cpi < lo)).astype(float).where(cpi.notna() & (hi.notna() | lo.notna()))
        blocks["inflation_outside_band"] = outside
        SOURCES["inflation_outside_band"] = "1 if cpi_yoy is above the upper or below the lower band"
    rows = []
    for c in COUNTRIES:
        d = pd.DataFrame({k: v[c] for k, v in blocks.items() if c in v}, index=months)
        d.insert(0, "currency", CCY[c])
        d.insert(0, "focus", c in FOCUS)
        d.insert(0, "country", NAMES[c])
        d.insert(0, "iso3", ISO3[c])
        d.index.name = "month"
        rows.append(d.reset_index())
    panel = pd.concat(rows, ignore_index=True)
    glob = global_block(months).reset_index().rename(columns={"index": "month"})
    panel = panel.merge(glob, on="month", how="left")
    panel["month"] = panel["month"].astype(str)
    if not write:
        return panel
    PROC.mkdir(parents=True, exist_ok=True)
    panel.to_csv(PROC / "country_month_panel.csv", index=False, float_format="%.6g")
    coverage(panel, months)
    return panel


def coverage(panel: pd.DataFrame, months):
    cols = [c for c in panel.columns if c not in ("iso3", "country", "focus", "currency", "month")]
    rows = []
    for col in cols:
        for iso, g in panel.groupby("iso3"):
            s = g.set_index("month")[col]
            ok = s.notna() & (s.astype(str) != "")
            rows.append({"factor": col, "iso3": iso, "first": s[ok].index.min() if ok.any() else "",
                         "last": s[ok].index.max() if ok.any() else "",
                         "pct_months": round(100 * ok.mean(), 1), "source": SOURCES.get(col, ""),
                         "note": NOTES.get(col, "")})
    cov = pd.DataFrame(rows)
    cov.to_csv(PROC / "panel_coverage.csv", index=False)
    order = [ISO3[c] for c in COUNTRIES]
    mat = cov.pivot_table(index="factor", columns="iso3", values="pct_months").reindex(columns=order)
    mat = mat.reindex(cols)
    L = ["# Country-month panel: coverage by factor and country", "",
         f"`data/processed/country_month_panel.csv`: {panel['iso3'].nunique()} countries x {len(months)} months "
         f"({months[0]} to {months[-1]}), {len(cols)} factors. Cells = % of months with a value. Focus countries: "
         "Brazil, Mexico, France.", "",
         "| factor | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    for f, r in mat.iterrows():
        L.append(f"| {f} | " + " | ".join("" if pd.isna(v) else f"{v:.0f}" for v in r.values) + " |")
    L += ["", "## Sources and notes by factor", ""]
    for col in cols:
        L.append(f"- **{col}** — {SOURCES.get(col, 'n/a')}" + (f" *Note:* {NOTES[col]}" if col in NOTES else ""))
    L += ["", "## Spans by factor and country (first-last month with data)", "",
          "| factor | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    span = cov.assign(span=cov["first"].astype(str).str[:7] + "–" + cov["last"].astype(str).str[:7])
    sp = span.pivot_table(index="factor", columns="iso3", values="span", aggfunc="first").reindex(index=cols,
                                                                                                  columns=order)
    for f, r in sp.iterrows():
        L.append(f"| {f} | " + " | ".join("" if (pd.isna(v) or v == "–") else v for v in r.values) + " |")
    (RESULTS / "panel_coverage.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    build()
