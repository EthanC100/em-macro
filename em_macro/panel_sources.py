"""Fetchers for the country-month panel (keyless public APIs).

All results are cached under data/raw/ (gitignored) like em_macro.sources.
"""
from __future__ import annotations

import io
import json
import re

import pandas as pd

from .config import RAW
from .sources import _get


def ecb_irs(iso2: list[str], refresh: bool = False) -> pd.DataFrame:
    """ECB 'EMU convergence criterion' long-term (10y) government bond yields,
    monthly averages (dataset IRS).  Columns = ISO2."""
    key = "+".join(iso2)
    url = (f"https://data-api.ecb.europa.eu/service/data/IRS/M.{key}.L.L40.CI.0000..N.Z"
           "?format=csvdata&startPeriod=2004-01")
    raw = _get(url, RAW / "ecb" / f"IRS_{key}.csv", refresh)
    d = pd.read_csv(io.BytesIO(raw), usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    d["TIME_PERIOD"] = pd.PeriodIndex(d["TIME_PERIOD"], freq="M")
    return d.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE")


def ecb_series(key: str, refresh: bool = False) -> pd.Series:
    """Any ECB data-portal series, e.g. 'FM/D.U2.EUR.4F.KR.DFR.LEV'."""
    flow, k = key.split("/", 1)
    url = f"https://data-api.ecb.europa.eu/service/data/{flow}/{k}?format=csvdata&startPeriod=1999-01"
    raw = _get(url, RAW / "ecb" / f"{flow}_{k}.csv", refresh)
    d = pd.read_csv(io.BytesIO(raw), usecols=["TIME_PERIOD", "OBS_VALUE"])
    return pd.Series(d["OBS_VALUE"].values, index=pd.to_datetime(d["TIME_PERIOD"]), name=key).sort_index()


def oecd_lt_rate(iso3: list[str], refresh: bool = False) -> pd.DataFrame:
    """OECD Main Economic Indicators long-term interest rate (10y govt), monthly
    (dataset DF_FINMARK, measure IRLT).  Columns = ISO3."""
    key = "+".join(iso3)
    url = (f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,/{key}.M.IRLT.PA....."
           "?startPeriod=2004-01&format=csvfilewithlabels")
    raw = _get(url, RAW / "oecd" / f"IRLT_{key}.csv", refresh)
    d = pd.read_csv(io.BytesIO(raw), usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    d["TIME_PERIOD"] = pd.PeriodIndex(d["TIME_PERIOD"], freq="M")
    return d.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE")


def bis_cpi_yoy(area: str, refresh: bool = False) -> pd.Series:
    """BIS long consumer price series, year-on-year % change (unit 771), monthly."""
    url = f"https://stats.bis.org/api/v1/data/WS_LONG_CPI/M.{area}.771?format=csv"
    raw = _get(url, RAW / "bis" / f"CPI_{area}.csv", refresh)
    d = pd.read_csv(io.BytesIO(raw), usecols=["TIME_PERIOD", "OBS_VALUE"])
    s = pd.Series(pd.to_numeric(d["OBS_VALUE"], errors="coerce").values,
                  index=pd.PeriodIndex(d["TIME_PERIOD"], freq="M"), name=f"cpi_{area}")
    return s.dropna().sort_index()


def imf_weo(iso3: str, indicator: str, refresh: bool = False) -> tuple[pd.Series, str]:
    """IMF World Economic Outlook (latest vintage) annual series via the IMF
    SDMX API.  Returns (series by year, country update date of the vintage)."""
    url = f"https://api.imf.org/external/sdmx/2.1/data/IMF.RES,WEO/{iso3}.{indicator}.A?startPeriod=2000"
    x = _get(url, RAW / "imf_weo" / f"{iso3}_{indicator}.xml", refresh).decode()
    upd = re.search(r'COUNTRY_UPDATE_DATE="([^"]*)"', x)
    obs = re.findall(r'<Obs TIME_PERIOD="(\d{4})" OBS_VALUE="([^"]*)"', x)
    s = pd.Series({int(y): float(v) for y, v in obs if v not in ("", "NaN")}, name=indicator, dtype=float)
    return s.sort_index(), (upd.group(1) if upd else "")


def worldbank(iso3: list[str], indicator: str, source: int | None = None, refresh: bool = False) -> pd.DataFrame:
    """World Bank API annual indicator; columns = ISO3, index = year."""
    src = f"&source={source}" if source else ""
    url = (f"https://api.worldbank.org/v2/country/{';'.join(iso3)}/indicator/{indicator}"
           f"?format=json&date=2000:2030&per_page=2000{src}")
    d = json.loads(_get(url, RAW / "worldbank" / f"{indicator}.json", refresh))
    rows = [(r["countryiso3code"], int(r["date"]), r["value"]) for r in (d[1] or []) if r["value"] is not None]
    out = pd.DataFrame(rows, columns=["iso3", "year", "value"])
    return out.pivot_table(index="year", columns="iso3", values="value")


def colombia_trm(refresh: bool = False) -> pd.Series:
    """Banco de la República TRM (COP per USD, official daily rate) via datos.gov.co."""
    url = "https://www.datos.gov.co/resource/32sa-8pi3.json?$limit=50000&$where=vigenciadesde>='2004-01-01'"
    d = json.loads(_get(url, RAW / "colombia" / "trm.json", refresh))
    s = pd.Series([float(r["valor"]) for r in d], index=pd.to_datetime([r["vigenciadesde"] for r in d]), name="TRM")
    return s[~s.index.duplicated()].sort_index()


def chile_dolar_observado(refresh: bool = False) -> pd.Series:
    """Banco Central de Chile 'dólar observado' (CLP per USD, daily) via the
    keyless mindicador.cl mirror, one request per year."""
    rows = []
    for y in range(2004, pd.Timestamp.today().year + 1):
        d = json.loads(_get(f"https://mindicador.cl/api/dolar/{y}", RAW / "chile" / f"dolar_{y}.json",
                            refresh and y == pd.Timestamp.today().year))
        rows += [(r["fecha"][:10], r["valor"]) for r in d["serie"]]
    s = pd.Series({pd.Timestamp(f): float(v) for f, v in rows}, name="dolar_observado")
    return s[~s.index.duplicated()].sort_index()
