"""Downloaders for free public data sources.

Every fetcher returns a float ``pd.Series`` indexed by ``DatetimeIndex`` and
caches the raw response under ``data/raw`` so the pipeline can be re-run
offline.  Pass ``refresh=True`` to re-download.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pandas as pd
import requests

from .config import RAW, START, TESOURO_URL

SESSION = requests.Session()


def _get(url: str, cache: Path, refresh: bool = False, tries: int = 4, timeout: int = 120) -> bytes:
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and not refresh:
        return cache.read_bytes()
    err = None
    for i in range(tries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            cache.write_bytes(r.content)
            return r.content
        except requests.RequestException as e:  # network hiccup: back off and retry
            err = e
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"download failed: {url}: {err}")


def fred(series_id: str, refresh: bool = False) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    raw = _get(url, RAW / "fred" / f"{series_id}.csv", refresh)
    df = pd.read_csv(io.BytesIO(raw), na_values=["."])
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                  index=pd.to_datetime(df.iloc[:, 0]), name=series_id)
    return s.dropna()


def yahoo(ticker: str, refresh: bool = False) -> pd.Series:
    cache = RAW / "yahoo" / f"{ticker.replace('^', '').replace('=', '_')}.csv"
    if cache.exists() and not refresh:
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        return df.iloc[:, 0].dropna().rename(ticker)
    import yfinance as yf
    d = yf.download(ticker, start=START, progress=False, auto_adjust=False)
    s = d["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s = s.dropna().rename(ticker)
    s.index = pd.to_datetime(s.index).tz_localize(None)
    cache.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame().to_csv(cache)
    return s


def bis_policy(area: str, refresh: bool = False) -> pd.Series:
    url = f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.{area}?format=csv"
    raw = _get(url, RAW / "bis" / f"CBPOL_{area}.csv", refresh)
    df = pd.read_csv(io.BytesIO(raw), usecols=["TIME_PERIOD", "OBS_VALUE"])
    s = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values,
                  index=pd.to_datetime(df["TIME_PERIOD"]), name=f"policy_{area}")
    return s.dropna().sort_index()


def bcb_sgs(code: int, refresh: bool = False) -> pd.Series:
    """BCB SGS series; the API limits daily series to 10-year windows."""
    cache = RAW / "bcb" / f"sgs_{code}.json"
    if cache.exists() and not refresh:
        rows = json.loads(cache.read_text())
    else:
        rows = []
        for y0 in range(2005, pd.Timestamp.today().year + 1, 10):
            url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json"
                   f"&dataInicial=01/01/{y0}&dataFinal=31/12/{y0 + 9}")
            rows += json.loads(_get(url, RAW / "bcb" / f"sgs_{code}_{y0}.json", True))
        cache.write_text(json.dumps(rows))
    df = pd.DataFrame(rows)
    s = pd.Series(pd.to_numeric(df["valor"], errors="coerce").values,
                  index=pd.to_datetime(df["data"], dayfirst=True), name=f"sgs_{code}")
    return s[~s.index.duplicated()].dropna().sort_index()


def banxico(series_id: str, refresh: bool = False) -> pd.Series:
    """Banxico SIE series via the public JSON that backs the SIE web charts."""
    url = (f"https://www.banxico.org.mx/SieInternet/consultaSerieGrafica.do?"
           f"s={series_id},CF300,1&versionSerie=LA-MAS-RECIENTE&l=es")
    d = json.loads(_get(url, RAW / "banxico" / f"{series_id}.json", refresh))
    vals = d["valores"]
    s = pd.Series([v[1] for v in vals], index=pd.to_datetime([v[0] for v in vals]), name=series_id)
    return pd.to_numeric(s, errors="coerce").dropna().sort_index()


def sarb(code: str, refresh: bool = False) -> pd.Series:
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    url = ("https://custom.resbank.co.za/SarbWebApi/WebIndicators/Shared/"
           f"GetTimeseriesObservations/{code}/{START}/{end}")
    d = json.loads(_get(url, RAW / "sarb" / f"{code}.json", refresh))
    s = pd.Series([r["Value"] for r in d], index=pd.to_datetime([r["Period"] for r in d]), name=code)
    return pd.to_numeric(s, errors="coerce").dropna().sort_index()


def nbp_fx(code: str = "usd", refresh: bool = False) -> pd.Series:
    """NBP table A mid rate (PLN per unit); API allows 367-day windows."""
    cache = RAW / "nbp" / f"fx_{code}.json"
    if cache.exists() and not refresh:
        rows = json.loads(cache.read_text())
    else:
        rows = []
        today = pd.Timestamp.today()
        for y in range(2005, today.year + 1):
            a, b = f"{y}-01-01", min(pd.Timestamp(f"{y}-12-31"), today).strftime("%Y-%m-%d")
            url = f"https://api.nbp.pl/api/exchangerates/rates/a/{code}/{a}/{b}/?format=json"
            rows += json.loads(_get(url, RAW / "nbp" / f"fx_{code}_{y}.json", True))["rates"]
        cache.write_text(json.dumps(rows))
    s = pd.Series([r["mid"] for r in rows], index=pd.to_datetime([r["effectiveDate"] for r in rows]),
                  name=f"nbp_{code}")
    return s.sort_index()


def tesouro_direto(refresh: bool = False) -> pd.DataFrame:
    """Tesouro Direto daily rates/prices for all retail Treasury bonds (2002+)."""
    raw = _get(TESOURO_URL, RAW / "tesouro" / "PrecoTaxaTesouroDireto.csv", refresh, timeout=300)
    df = pd.read_csv(io.BytesIO(raw), sep=";", decimal=",")
    df["Data Base"] = pd.to_datetime(df["Data Base"], dayfirst=True)
    df["Data Vencimento"] = pd.to_datetime(df["Data Vencimento"], dayfirst=True)
    return df


def bcb_copom(refresh: bool = False) -> pd.DataFrame:
    """Copom meeting history (date, Selic target) from the BCB website API."""
    url = "https://www.bcb.gov.br/api/servico/sitebcb/historicotaxasjuros"
    d = json.loads(_get(url, RAW / "bcb" / "copom_historico.json", refresh))
    return pd.DataFrame(d["conteudo"])


def bcb_focus_selic(refresh: bool = False) -> pd.DataFrame:
    """BCB Focus survey: market expectations for the Selic at each Copom meeting."""
    url = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
           "ExpectativasMercadoSelic?$format=json&$select=Data,Reuniao,Mediana,Media,numeroRespondentes,baseCalculo"
           "&$top=1000000")
    d = json.loads(_get(url, RAW / "bcb" / "focus_selic.json", refresh, timeout=300))
    return pd.DataFrame(d["value"])


def _bondspot_day(d: pd.Timestamp) -> list[dict]:
    import html
    import re
    url = f"https://www.bondspot.pl/fixing_obligacji?date={d:%Y%m%d}&month={d.month}&year={d.year}"
    t = None
    for i in range(4):
        try:
            r = SESSION.get(url, timeout=60)
            r.raise_for_status()
            t = r.text
            break
        except requests.RequestException:
            time.sleep(2 ** (i + 1))
    if t is None:
        return [{"date": d.date(), "name": None}]      # mark as attempted
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t, flags=re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]
        if len(c) == 9 and re.fullmatch(r"PL\w{10}", c[2] or ""):
            out.append({"date": d.date(), "name": c[1], "isin": c[2], "price_fix": c[7], "yield_fix": c[8]})
    return out or [{"date": d.date(), "name": None}]


def bondspot_fixings(refresh: bool = False, workers: int = 3) -> pd.DataFrame:
    """Treasury BondSpot Poland daily fixing (price and yield of every listed
    Polish government bond), one page per business day; parsed rows are cached
    per year under data/raw/bondspot/."""
    from concurrent.futures import ThreadPoolExecutor
    folder = RAW / "bondspot"
    folder.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today().normalize()
    frames = []
    for y in range(2005, today.year + 1):
        f = folder / f"fixing_{y}.csv"
        days = pd.bdate_range(f"{y}-01-01", min(pd.Timestamp(f"{y}-12-31"), today - pd.Timedelta(days=1)))
        have = pd.read_csv(f) if f.exists() and not refresh else pd.DataFrame(columns=["date", "name"])
        done = set(pd.to_datetime(have["date"]).dt.date) if len(have) else set()
        todo = [d for d in days if d.date() not in done]
        if todo:
            with ThreadPoolExecutor(workers) as ex:
                rows = [r for day in ex.map(_bondspot_day, todo) for r in day]
            have = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
            have.to_csv(f, index=False)
        frames.append(have)
    df = pd.concat(frames, ignore_index=True).dropna(subset=["name"])
    df["date"] = pd.to_datetime(df["date"])
    df["yield_fix"] = pd.to_numeric(df["yield_fix"], errors="coerce")
    return df


def _bist_day(d: pd.Timestamp) -> list[dict]:
    import zipfile
    url = f"https://www.borsaistanbul.com/data/ttb/{d:%Y}/{d:%m}/ttb{d:%Y%m%d}3.zip"
    content = None
    for i in range(3):
        try:
            r = SESSION.get(url, timeout=60)
            if r.status_code == 404:
                return [{"date": d.date(), "isin": None}]
            r.raise_for_status()
            content = r.content
            break
        except requests.RequestException:
            time.sleep(2 ** (i + 1))
    if content is None:
        return []                                    # transient failure: retry on next run
    try:
        z = zipfile.ZipFile(io.BytesIO(content))
        df = pd.read_csv(z.open(z.namelist()[0]), sep=";", encoding="latin-1", skiprows=[1], dtype=str)
    except Exception:
        return [{"date": d.date(), "isin": None}]
    df = df[df["PAZAR ISMI"].str.contains("KES", na=False) & (df["PARA BIRIMI"] == "TRY")
            & df["ISIN/KOD"].str.startswith("TRT", na=False)]
    out = [{"date": d.date(), "isin": r["ISIN/KOD"], "dtm": r["VKG/REPO SURESI"],
            "wavg_compound": r["AG. ORT. BILESIK GETIRI"], "close_compound": r["KAPANIS BILESIK GETIRI"],
            "volume": r["ISLEM HACMI"]} for _, r in df.iterrows()]
    return out or [{"date": d.date(), "isin": None}]


def bist_bonds(refresh: bool = False, workers: int = 3, start: str = "2018-07-02") -> pd.DataFrame:
    """Borsa Istanbul Debt Securities Market end-of-day bulletin (CSV format,
    available from July 2018): fixed-coupon TRY government bonds (ISIN TRT...)
    with days to maturity and compound yields.  Cached per year."""
    from concurrent.futures import ThreadPoolExecutor
    folder = RAW / "bist"
    folder.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today().normalize()
    frames = []
    for y in range(pd.Timestamp(start).year, today.year + 1):
        f = folder / f"ttb_{y}.csv"
        days = pd.bdate_range(max(pd.Timestamp(start), pd.Timestamp(f"{y}-01-01")),
                              min(pd.Timestamp(f"{y}-12-31"), today - pd.Timedelta(days=1)))
        have = pd.read_csv(f) if f.exists() and not refresh else pd.DataFrame(columns=["date", "isin"])
        done = set(pd.to_datetime(have["date"]).dt.date) if len(have) else set()
        todo = [d for d in days if d.date() not in done]
        if todo:
            with ThreadPoolExecutor(workers) as ex:
                rows = [r for day in ex.map(_bist_day, todo) for r in day]
            have = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
            have.to_csv(f, index=False)
        frames.append(have)
    df = pd.concat(frames, ignore_index=True).dropna(subset=["isin"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ["dtm", "wavg_compound", "close_compound", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
