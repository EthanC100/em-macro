"""T02 (economic momentum) — Step 2 data feasibility: download the real-time (first-release) macro
vintages and the revised fallback series for the countries behind v1.0's 10 currencies, and
summarise their coverage.  No signal, return or backtest is computed here.

    python -m em_macro.t02_data download   # raw files into data/raw/econ_momentum/ (never modified afterwards)
    python -m em_macro.t02_data coverage   # coverage tables -> results/T02/data_coverage_*.csv and the manifest

Sources (all free, no key):
  OECD short-term economic statistics revisions database (DSD_STES_REVISIONS@DF_STES_REVISIONS): every
      monthly edition (vintage) since 1999-02 of industrial production (PRVM), retail trade volume (TOVM),
      consumer prices (CP) and the unemployment rate (UNEMP).  An edition dated YYYYMM is the data as
      published in the OECD Main Economic Indicators of that month.
  OECD key short-term economic indicators (DSD_KEI@DF_KEI): the latest, revised series (fallback only).
  ECB Real Time Database (RTD): euro-area series with VALID_FROM timestamps for every published value
      since 2001-01-03 (industrial production, retail trade, HICP, standardised unemployment, PPI).
  ALFRED (St. Louis Fed): vintages since 2011 of the OECD-sourced FRED series, one request per vintage,
      used only where the OECD editions have gaps.
"""
from __future__ import annotations

import hashlib
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .config import RAW, RESULTS

OUT = RAW / "econ_momentum"
RES = RESULTS / "T02"
CA = "/root/.ccr/ca-bundle.crt"

AREAS = ["BRA", "MEX", "ZAF", "TUR", "IDN", "POL", "GBR", "COL", "CHL", "EA19", "EA20"]   # EA19/EA20: euro area
MEASURES = ["PRVM", "TOVM", "CP", "UNEMP"]
ACTIVITY = {"PRVM": "BTE", "TOVM": "G47", "CP": "_Z", "UNEMP": "_T"}   # industry ex construction; retail; CPI; total
OECD_REV = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES_REVISIONS@DF_STES_REVISIONS,4.0"
OECD_KEI = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0"
ECB_RTD = "https://data-api.ecb.europa.eu/service/data/RTD"
ECB_CONCEPTS = ["I_XCONS", "I_INDTO", "P_C_OV", "L_UNETO", "O_RTXMOTVD", "O_RTXMOTV", "P_P_XCONS_DS"]
# ALFRED series used to fill OECD gaps (series id -> label); vintages are listed on the series' download page
ALFRED = {
    "COLPRMNTO01IXOBSAM": "Colombia production of manufacturing, SA (OECD MEI via FRED; no total-industry id exists)",
    "COLSLRTTO01IXOBSAM": "Colombia retail trade volume, SA (OECD MEI via FRED; from 2013-01)",
    "COLSLRTTO02IXOBSAM": "Colombia retail trade volume, SA, older series (OECD MEI via FRED; 1999-01 to 2018-12)",
    "COLCPALTT01IXOBM": "Colombia CPI, all items (OECD MEI via FRED)",
    "LRUNTTTTBRM156S": "Brazil unemployment rate, monthly (OECD MEI via FRED; ends 2015-11)",
    "LRUNTTTTZAQ156S": "South Africa unemployment rate, quarterly (OECD MEI via FRED)",
    "TURSLRTTO01IXOBSAM": "Turkey retail trade volume, SA (OECD MEI via FRED; from 2010-01)",
}
# Probed and absent from FRED (2026-11-03): Colombia unemployment (any frequency), Indonesia retail sales,
# Indonesia unemployment, Indonesia production other than the OECD total already covered by the revisions database.


def _get(url: str, dest: Path, timeout: int = 900, tries: int = 3, headers: dict | None = None) -> int:
    """Download url to dest unless dest already exists (raw files are never overwritten)."""
    if dest.exists() and dest.stat().st_size > 0:
        return 0
    ctx = ssl.create_default_context(cafile=CA)
    hdr = {"User-Agent": "curl/8"} | (headers or {})
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout, context=ctx) as r:
                data = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return -404
            time.sleep(20 * (a + 1))
        except Exception:
            time.sleep(20 * (a + 1))
    return -1


def download_oecd_revisions() -> None:
    d = OUT / "oecd_stes_revisions"
    for c in AREAS:
        for m in MEASURES:
            f = d / f"{c}_M_{m}_all_editions.csv"
            n = _get(f"{OECD_REV}/{c}.M.{m}....?format=csvfile&startPeriod=1990-01", f)
            print("oecd revisions", c, m, n, flush=True)
            time.sleep(3)


def download_oecd_kei() -> None:
    d = OUT / "oecd_kei_latest"
    areas = "+".join(a for a in AREAS if a != "EA19") + "+EA"
    for m in MEASURES + ["PP"]:
        n = _get(f"{OECD_KEI}/{areas}.M.{m}.....?format=csvfile&startPeriod=1990-01", d / f"KEI_M_{m}_latest.csv")
        print("oecd kei", m, n, flush=True)
        time.sleep(3)


def download_ecb_rtd() -> None:
    d = OUT / "ecb_rtd"
    ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    for c in ECB_CONCEPTS:
        n = _get(f"{ECB_RTD}/M.S0..{c}.?format=csvdata&includeHistory=true", d / f"RTD_M_S0_all_{c}_history.csv",
                 headers=ua)
        print("ecb rtd", c, n, flush=True)


def alfred_vintage_dates(series_id: str) -> list[str]:
    p = OUT / "alfred" / f"{series_id}_downloadpage.html"
    _get(f"https://alfred.stlouisfed.org/series/downloaddata?seid={series_id}", p, timeout=60)
    if not p.exists():
        return []
    return sorted(set(re.findall(r'<option value="(\d{4}-\d{2}-\d{2})">', p.read_text(errors="ignore"))))


def download_alfred() -> None:
    d = OUT / "alfred"
    for sid in ALFRED:
        vd = alfred_vintage_dates(sid)
        print("alfred", sid, len(vd), "vintages", flush=True)
        for v in vd:
            n = _get(f"https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={sid}&vintage_date={v}",
                     d / sid / f"{sid}_{v}.csv", timeout=60)
            if n:
                time.sleep(1.0)


# ------------------------------------------------------------------------- coverage
def coverage_oecd_revisions() -> pd.DataFrame:
    rows = []
    for f in sorted((OUT / "oecd_stes_revisions").glob("*_all_editions.csv")):
        c, _, m = f.name.split("_")[:3]
        df = pd.read_csv(f, dtype=str, usecols=["UNIT_MEASURE", "ACTIVITY", "EDITION", "TIME_PERIOD", "OBS_VALUE"])
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
        d = df.dropna(subset=["OBS_VALUE"])
        d = d[d.ACTIVITY == ACTIVITY[m]]
        last = d.groupby("EDITION").TIME_PERIOD.max()
        ed = sorted(last.index)
        lag = pd.Series([(pd.Period(e[:4] + "-" + e[4:], "M") - pd.Period(last[e], "M")).n for e in ed], index=ed)
        cur = lag[lag <= 6]
        last_current = cur.index[-1] if len(cur) else ""
        rows.append({
            "area": c, "measure": m, "activity": ACTIVITY[m], "unit": ";".join(sorted(d.UNIT_MEASURE.unique())),
            "n_editions": len(ed), "first_edition": ed[0], "last_edition": ed[-1],
            "last_current_edition": last_current,
            "obs_start_latest_edition": d[d.EDITION == ed[-1]].TIME_PERIOD.min(),
            "last_obs_latest_edition": last[ed[-1]],
            "pub_lag_months_median": float(lag.median()), "pub_lag_months_p90": float(lag.quantile(0.9)),
            "n_editions_stale_gt6m": int((lag > 6).sum()), "bytes": f.stat().st_size,
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "file": str(f.relative_to(RAW.parent.parent)),
        })
    return pd.DataFrame(rows)


def coverage_ecb_rtd() -> pd.DataFrame:
    rows = []
    for f in sorted((OUT / "ecb_rtd").glob("*.csv")):
        df = pd.read_csv(f, dtype=str)
        if "KEY" not in df:
            continue
        for k, g in df.groupby("KEY"):
            vf = pd.to_datetime(g.VALID_FROM.str[:10], errors="coerce").dropna()
            rows.append({"key": k, "title": g.TITLE_COMPL.iloc[0][:90], "rows": len(g),
                         "obs_start": g.TIME_PERIOD.min(), "obs_end": g.TIME_PERIOD.max(),
                         "first_valid_from": str(vf.min().date()), "last_valid_from": str(vf.max().date()),
                         "n_vintage_dates": vf.nunique(), "bytes": f.stat().st_size,
                         "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                         "file": str(f.relative_to(RAW.parent.parent))})
    return pd.DataFrame(rows)


def coverage_oecd_kei() -> pd.DataFrame:
    rows = []
    for f in sorted((OUT / "oecd_kei_latest").glob("KEI_*.csv")):
        df = pd.read_csv(f, dtype=str)
        if "OBS_VALUE" not in df:
            continue
        df["OBS_VALUE"] = pd.to_numeric(df.OBS_VALUE, errors="coerce")
        d = df.dropna(subset=["OBS_VALUE"])
        d = d[(d.TRANSFORMATION == "_Z") & (d.UNIT_MEASURE.isin(["IX", "PT_LF"]))]
        for (a, m, act, adj), g in d.groupby(["REF_AREA", "MEASURE", "ACTIVITY", "ADJUSTMENT"]):
            rows.append({"area": a, "measure": m, "activity": act, "adjustment": adj, "obs_start": g.TIME_PERIOD.min(),
                         "obs_end": g.TIME_PERIOD.max(), "n_obs": len(g), "file": str(f.relative_to(RAW.parent.parent)),
                         "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    return pd.DataFrame(rows)


def coverage_alfred() -> pd.DataFrame:
    rows = []
    for sid in ALFRED:
        d = OUT / "alfred" / sid
        files = sorted(d.glob(f"{sid}_*.csv")) if d.exists() else []
        if not files:
            rows.append({"series_id": sid, "label": ALFRED[sid], "n_vintages": 0})
            continue
        first, last = files[0], files[-1]
        s0 = pd.read_csv(first, na_values=["."]); s1 = pd.read_csv(last, na_values=["."])
        rows.append({"series_id": sid, "label": ALFRED[sid], "n_vintages": len(files),
                     "first_vintage": first.stem[-10:], "last_vintage": last.stem[-10:],
                     "obs_start_first_vintage": s0.iloc[0, 0], "obs_end_first_vintage": s0.dropna().iloc[-1, 0],
                     "obs_end_last_vintage": s1.dropna().iloc[-1, 0],
                     "sha256_concat": hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()})
    return pd.DataFrame(rows)


def coverage() -> None:
    RES.mkdir(parents=True, exist_ok=True)
    tabs = {"oecd_revisions": coverage_oecd_revisions(), "ecb_rtd": coverage_ecb_rtd(),
            "oecd_kei_latest": coverage_oecd_kei(), "alfred": coverage_alfred()}
    for k, t in tabs.items():
        t.to_csv(RES / f"data_coverage_{k}.csv", index=False)
        print("==", k); print(t.drop(columns=[c for c in t.columns if "sha256" in c], errors="ignore").to_string())
    man = []
    for f in sorted(OUT.rglob("*")):
        if f.is_file() and f.suffix in (".csv", ".html", ".txt"):
            man.append({"file": str(f.relative_to(RAW.parent.parent)), "bytes": f.stat().st_size,
                        "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    pd.DataFrame(man).to_csv(RES / "raw_data_manifest.csv", index=False)
    print("manifest:", len(man), "files")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "coverage"
    if stage == "download":
        download_oecd_revisions(); download_oecd_kei(); download_ecb_rtd(); download_alfred()
    elif stage == "coverage":
        coverage()
    else:
        raise SystemExit("stage must be download or coverage")
