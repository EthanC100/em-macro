"""Instrument registry and daily marks for the Ledger.

    python -m ledger.marks                 # fetch every instrument in data/ledger/instruments.csv,
                                           # append the marks to data/ledger/marks.csv
    python -m ledger.marks --only BRL,DE10Y
    python -m ledger.marks --dry-run       # fetch and print, write nothing

The registry (data/ledger/instruments.csv) maps every instrument of the v1.0 universe, and the
legs its spreads need, to a free official daily source, with a fallback. Where no free daily
source exists the row says ``monthly`` and the app shows the mark as monthly. Each mark is the
latest observation of the source (its own date, not the fetch date). A source that fails is
replaced by its fallback, and if that fails too the previous mark is kept with a note; one bad
source never stops the run.

Sources (``source`` column): fred, ecb_exr, bcb_sgs, banxico, sarb, nbp, boe, bde, bundesbank,
riksbank (Sveriges Riksbank SWEA API: daily benchmark 10-year yields of FR, DE, US, GB, JP and others),
mof_jgb (Japan Ministry of Finance JGB curve), mindicador, datos_gov_co, em_macro (a loader of this
repository), panel_daily, panel_monthly (the project's own panels, refreshed monthly) and spread (leg
minus leg, in bp).

Which marks may act on a position (2026-11-06, after D001 was shown at a 30 Sep monthly average):
only a ``daily`` mark that is not stale and is not a carried-forward previous mark can trigger a stop
or a horizon close (``mark_can_act``). A monthly mark is a monthly *average* dated at the month end;
it is shown, flagged, and never prices or closes anything.

    python -m ledger.marks --backfill 2026-10-30 --only FR-DE   # daily history from a start date
                                                                 # (sources with a date-range API)

Only the standard library is needed for every source except ``em_macro``.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .schema import parse_date, parse_number
from .scoring import pnl_at_level

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/ledger/instruments.csv"
MARKS = ROOT / "data/ledger/marks.csv"
CONFIG = json.loads((ROOT / "ledger/automation.json").read_text(encoding="utf-8"))
MARK_COLUMNS = ["date", "instrument", "value", "unit", "frequency", "source", "source_url", "fetched_at", "note"]
USER_AGENT = "em-macro-ledger/1.0 (+https://github.com/ethanc100/em-macro)"
BROWSER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/124.0 Safari/537.36")
SPANISH_MONTHS = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SEP": 9,
                  "OCT": 10, "NOV": 11, "DIC": 12}


# ----------------------------------------------------------------------------- http
def http_get(url: str, timeout: int = 60, tries: int = 3, browser: bool = False) -> bytes:
    """GET with a short retry; raises on the final failure."""
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_AGENT if browser else USER_AGENT,
                                                       "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - every failure is retried, then reported
            err = e
            if i < tries - 1:
                time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def _last(points: list[tuple[date, float]]) -> tuple[date, float]:
    pts = sorted((d, v) for d, v in points if d is not None and v is not None)
    if not pts:
        raise ValueError("no observations")
    return pts[-1]


def _num(x) -> float | None:
    try:
        s = str(x).strip().replace(",", ".")
        if s in ("", ".", "_", "-", "NaN", "nan", "null", "None"):
            return None
        return float(s)
    except ValueError:
        return None


# ----------------------------------------------------------------------------- fetchers
# every fetcher returns (date, value, url) for the latest observation
def fetch_fred(series: str, get=http_get):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    rows = list(csv.reader(get(url).decode("utf-8", "replace").splitlines()))
    pts = [(parse_date(r[0]), _num(r[1])) for r in rows[1:] if len(r) >= 2]
    d, v = _last(pts)
    return d, v, url


def _ecb_exr_series(ccy: str, get) -> dict[date, float]:
    url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A?format=csvdata&lastNObservations=15"
    rows = list(csv.DictReader(get(url).decode("utf-8", "replace").splitlines()))
    out = {}
    for r in rows:
        d, v = parse_date(r.get("TIME_PERIOD")), _num(r.get("OBS_VALUE"))
        if d and v is not None:
            out[d] = v
    return out


def fetch_ecb_exr(ccy: str, get=http_get):
    """Local currency per USD from the ECB euro reference rates (USD per EUR for ``USD``)."""
    usd = _ecb_exr_series("USD", get)
    url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A?format=csvdata&lastNObservations=15"
    if ccy == "USD":
        d, v = _last(list(usd.items()))
        return d, v, url
    loc = _ecb_exr_series(ccy, get)
    common = [(d, loc[d] / usd[d]) for d in loc if d in usd and usd[d]]
    d, v = _last(common)
    return d, round(v, 6), url


def fetch_bcb_sgs(code: str, get=http_get):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/15?formato=json"
    rows = json.loads(get(url).decode("utf-8", "replace"))
    pts = [(parse_date(r.get("data")), _num(r.get("valor"))) for r in rows]
    d, v = _last(pts)
    return d, v, url


def fetch_banxico(series: str, get=http_get):
    url = (f"https://www.banxico.org.mx/SieInternet/consultaSerieGrafica.do?s={series},CF300,1"
           f"&versionSerie=LA-MAS-RECIENTE&l=es")
    d = json.loads(get(url).decode("utf-8", "replace"))
    pts = [(parse_date(v[0]), _num(v[1])) for v in d.get("valores", [])]
    dd, vv = _last(pts)
    return dd, vv, url


def fetch_sarb(code: str, get=http_get):
    start = (date.today() - timedelta(days=60)).isoformat()
    end = (date.today() + timedelta(days=1)).isoformat()
    url = ("https://custom.resbank.co.za/SarbWebApi/WebIndicators/Shared/"
           f"GetTimeseriesObservations/{code}/{start}/{end}")
    rows = json.loads(get(url).decode("utf-8", "replace"))
    pts = [(parse_date(str(r.get("Period", ""))[:10]), _num(r.get("Value"))) for r in rows]
    d, v = _last(pts)
    return d, v, url


def fetch_nbp(code: str, get=http_get):
    url = f"https://api.nbp.pl/api/exchangerates/rates/a/{code}/last/15/?format=json"
    d = json.loads(get(url).decode("utf-8", "replace"))
    pts = [(parse_date(r.get("effectiveDate")), _num(r.get("mid"))) for r in d.get("rates", [])]
    dd, vv = _last(pts)
    return dd, vv, url


def fetch_boe(code: str, get=http_get, today: date | None = None):
    today = today or date.today()
    frm, to = (today - timedelta(days=45)).strftime("%d/%b/%Y"), today.strftime("%d/%b/%Y")
    url = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes"
           f"&Datefrom={frm}&Dateto={to}&SeriesCodes={code}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
    rows = list(csv.reader(get(url, browser=True).decode("utf-8", "replace").splitlines()))
    pts = [(parse_date(r[0]), _num(r[1])) for r in rows[1:] if len(r) >= 2]
    d, v = _last(pts)
    return d, v, url


def _spanish_date(s: str) -> date | None:
    m = re.match(r"^\s*(\d{1,2})\s*([A-Z]{3})\s*(\d{4})\s*$", s.strip().upper())
    if not m or m.group(2) not in SPANISH_MONTHS:
        return None
    return date(int(m.group(3)), SPANISH_MONTHS[m.group(2)], int(m.group(1)))


def fetch_bde(spec: str, get=http_get):
    """Banco de Espana statistical table CSV: ``table:alias`` (for example ti_1_3:TI_1_3.11)."""
    table, alias = spec.split(":")
    url = f"https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/{table}.csv"
    rows = list(csv.reader(get(url, browser=True).decode("latin-1").splitlines()))
    aliases = rows[2]
    col = aliases.index(alias)
    pts = []
    for r in rows[6:]:
        if not r or r[0].strip().upper() in ("FUENTE", "NOTAS"):
            continue
        d = _spanish_date(r[0])
        if d and len(r) > col:
            pts.append((d, _num(r[col])))
    d, v = _last(pts)
    return d, v, url


def fetch_bundesbank(key: str, get=http_get):
    start = (date.today() - timedelta(days=45)).isoformat()
    url = f"https://api.statistiken.bundesbank.de/rest/data/BBSIS/{key}?format=csv&lang=en&startPeriod={start}"
    rows = list(csv.reader(get(url).decode("utf-8-sig", "replace").splitlines()))
    pts = [(parse_date(r[0]), _num(r[1])) for r in rows if r and re.match(r"^\d{4}-\d{2}-\d{2}$", r[0])]
    d, v = _last(pts)
    return d, v, url


def riksbank_history(series: str, start: date, get=http_get, end: date | None = None):
    """Sveriges Riksbank SWEA API (keyless): daily observations of ``series`` from ``start``.
    The international government bond series (FRGVB10Y, DEGVB10Y, USGVB10Y, GBGVB10Y, JPGVB10Y, ...)
    are benchmark 10-year yields, one value per business day."""
    end = end or (date.today() + timedelta(days=1))
    url = f"https://api.riksbank.se/swea/v1/Observations/{series}/{start.isoformat()}/{end.isoformat()}"
    rows = json.loads(get(url).decode("utf-8", "replace"))
    pts = sorted((parse_date(r.get("date")), _num(r.get("value"))) for r in rows if r.get("value") is not None)
    return [(d, v) for d, v in pts if d and v is not None], url


def fetch_riksbank(series: str, get=http_get):
    pts, url = riksbank_history(series, date.today() - timedelta(days=21), get)
    d, v = _last(pts)
    return d, v, url


def mof_jgb_history(tenor: str = "10Y", get=http_get):
    """Japan Ministry of Finance JGB constant-maturity yields (keyless CSV, one row per business day)."""
    url = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
    rows = list(csv.reader(get(url, browser=True).decode("utf-8", "replace").splitlines()))
    head = next((i for i, r in enumerate(rows) if r and r[0].strip().lower() == "date"), None)
    if head is None:
        raise ValueError("JGB csv: no header row")
    col = [c.strip() for c in rows[head]].index(tenor)
    pts = []
    for r in rows[head + 1:]:
        if len(r) > col and re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", r[0].strip()):
            y, m, d = (int(x) for x in r[0].strip().split("/"))
            v = _num(r[col])
            if v is not None:
                pts.append((date(y, m, d), v))
    return pts, url


def fetch_mof_jgb(tenor: str, get=http_get):
    pts, url = mof_jgb_history(tenor or "10Y", get)
    d, v = _last(pts)
    return d, v, url


def fetch_mindicador(indicator: str, get=http_get):
    url = f"https://mindicador.cl/api/{indicator}"
    d = json.loads(get(url).decode("utf-8", "replace"))
    pts = [(parse_date(str(r.get("fecha", ""))[:10]), _num(r.get("valor"))) for r in d.get("serie", [])]
    dd, vv = _last(pts)
    return dd, vv, url


def fetch_datos_gov_co(resource: str, get=http_get):
    url = f"https://www.datos.gov.co/resource/{resource}.json?$limit=15&$order=vigenciadesde%20DESC"
    rows = json.loads(get(url).decode("utf-8", "replace"))
    pts = [(parse_date(str(r.get("vigenciadesde", ""))[:10]), _num(r.get("valor"))) for r in rows]
    d, v = _last(pts)
    return d, v, url


def fetch_em_macro(spec: str, get=None):
    """A loader of this repository, ``module.function``, returning a pandas Series (or a tuple
    whose first item is one). Needs pandas and the project's dependencies."""
    import importlib
    mod, func = spec.rsplit(".", 1)
    s = getattr(importlib.import_module(f"em_macro.{mod}"), func)(refresh=True)
    if isinstance(s, tuple):
        s = s[0]
    s = s.dropna()
    pts = [((i.date() if hasattr(i, "date") else parse_date(str(i))), float(v)) for i, v in s.tail(40).items()]
    d, v = _last(pts)
    return d, v, f"em_macro.{spec}"


def _panel_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_panel_daily(col: str, get=None, root: Path = ROOT):
    path = root / "data/processed/daily_panel.csv"
    pts = [(parse_date(r.get("date")), _num(r.get(col))) for r in _panel_rows(path)]
    d, v = _last(pts)
    return d, v, "data/processed/daily_panel.csv"


def fetch_panel_monthly(spec: str, get=None, root: Path = ROOT):
    """``column:ISO3`` from the 13-country monthly panel; the mark date is the month end."""
    col, iso3 = spec.split(":")
    path = root / "data/processed/country_month_panel.csv"
    pts = []
    for r in _panel_rows(path):
        if r.get("iso3") != iso3:
            continue
        v = _num(r.get(col))
        m = r.get("month", "")
        if v is not None and re.match(r"^\d{4}-\d{2}$", m):
            y, mm = int(m[:4]), int(m[5:7])
            pts.append((date(y, mm, calendar.monthrange(y, mm)[1]), v))
    d, v = _last(pts)
    return d, v, "data/processed/country_month_panel.csv"


FETCHERS = {
    "fred": fetch_fred, "ecb_exr": fetch_ecb_exr, "bcb_sgs": fetch_bcb_sgs, "banxico": fetch_banxico,
    "sarb": fetch_sarb, "nbp": fetch_nbp, "boe": fetch_boe, "bde": fetch_bde, "bundesbank": fetch_bundesbank,
    "mindicador": fetch_mindicador, "datos_gov_co": fetch_datos_gov_co, "em_macro": fetch_em_macro,
    "panel_daily": fetch_panel_daily, "panel_monthly": fetch_panel_monthly,
    "riksbank": fetch_riksbank, "mof_jgb": fetch_mof_jgb,
}


def fred_history(series: str, start: date, get=http_get):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start.isoformat()}"
    rows = list(csv.reader(get(url).decode("utf-8", "replace").splitlines()))
    pts = [(parse_date(r[0]), _num(r[1])) for r in rows[1:] if len(r) >= 2]
    return [(d, v) for d, v in pts if d and v is not None and d >= start], url


def bundesbank_history(key: str, start: date, get=http_get):
    url = f"https://api.statistiken.bundesbank.de/rest/data/BBSIS/{key}?format=csv&lang=en&startPeriod={start.isoformat()}"
    rows = list(csv.reader(get(url).decode("utf-8-sig", "replace").splitlines()))
    pts = [(parse_date(r[0]), _num(r[1])) for r in rows if r and re.match(r"^\d{4}-\d{2}-\d{2}$", r[0])]
    return [(d, v) for d, v in pts if d and v is not None], url


def ecb_exr_history(ccy: str, start: date, get=http_get):
    """Local currency per USD (USD per EUR for ``USD``) from the ECB reference rates since ``start``."""
    def series(c):
        url = (f"https://data-api.ecb.europa.eu/service/data/EXR/D.{c}.EUR.SP00.A?format=csvdata"
               f"&startPeriod={start.isoformat()}")
        out = {}
        for r in csv.DictReader(get(url).decode("utf-8", "replace").splitlines()):
            d, v = parse_date(r.get("TIME_PERIOD")), _num(r.get("OBS_VALUE"))
            if d and v is not None:
                out[d] = v
        return out, url
    usd, url = series("USD")
    if ccy == "USD":
        return sorted(usd.items()), url
    loc, url = series(ccy)
    return sorted((d, round(loc[d] / usd[d], 6)) for d in loc if d in usd and usd[d]), url


HISTORY = {"riksbank": riksbank_history, "fred": fred_history, "bundesbank": bundesbank_history,
           "ecb_exr": ecb_exr_history,
           "mof_jgb": lambda ident, start, get=http_get: (lambda r: ([p for p in r[0] if p[0] >= start], r[1]))(
               mof_jgb_history(ident or "10Y", get))}


def history_for(row: dict, start: date, get=http_get, cache: dict | None = None) -> tuple[list[tuple[date, float]], str]:
    """Daily history of a registry row from ``start`` (primary source only; spreads from their legs,
    on the dates both legs have). Raises if the source has no date-range API."""
    cache = cache if cache is not None else {}
    src, ident = row.get("source", ""), row.get("source_id", "")
    key = (src, ident, start)
    if key in cache:
        return cache[key]
    if src == "spread":
        raise ValueError("spread history needs the registry; use spread_history")
    fn = HISTORY.get(src)
    if fn is None:
        raise ValueError(f"no history API for source {src!r}")
    out = fn(ident, start, get)
    cache[key] = out
    return out


def spread_history(row: dict, by_id: dict[str, dict], start: date, get=http_get, cache: dict | None = None):
    a, b = row["source_id"].split("-", 1) if row.get("source") == "spread" else (None, None)
    if a is None:
        return history_for(row, start, get, cache)
    pa, ua = history_for(by_id[a], start, get, cache)
    pb, ub = history_for(by_id[b], start, get, cache)
    db = dict(pb)
    return [(d, round((v - db[d]) * 100, 2)) for d, v in pa if d in db], f"{ua} ; {ub}"


def backfill(registry: list[dict], start: date, only: set[str] | None = None, get=http_get) -> list[dict]:
    """Daily marks from ``start`` for every (selected) instrument whose source has a date-range API."""
    by_id = registry_index(registry)
    cache: dict = {}
    out = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for row in registry:
        if only and row["instrument"] not in only:
            continue
        if (row.get("frequency") or "daily") != "daily":
            continue
        try:
            pts, url = spread_history(row, by_id, start, get, cache)
        except Exception as e:  # noqa: BLE001 - report and carry on
            print(f"{row['instrument']:8s} no history: {str(e)[:120]}")
            continue
        src = f"{row.get('source', '')} {row.get('source_id', '')}".strip()
        for d, v in pts:
            out.append({"date": d.isoformat(), "instrument": row["instrument"], "value": f"{v:.6g}",
                        "unit": row.get("unit", ""), "frequency": "daily", "source": src, "source_url": url,
                        "fetched_at": now, "note": "backfilled history"})
        print(f"{row['instrument']:8s} {len(pts)} daily marks from {start}")
    return out


# ----------------------------------------------------------------------------- registry
def load_registry(path: Path = REGISTRY) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def registry_index(registry: list[dict]) -> dict[str, dict]:
    return {r["instrument"]: r for r in registry}


def match_instrument(text: str, registry: list[dict]) -> dict | None:
    """The registry row whose instrument code or alias appears in ``text`` (the free-text
    instrument of a decision or the question of a forecast). Longest alias wins; legs of spreads
    (kind ``leg``) only match when no tradeable instrument does."""
    if not text:
        return None
    t = " ".join(str(text).split())
    best, best_len, best_leg = None, 0, True
    for r in registry:
        names = [r["instrument"]] + [a for a in (r.get("aliases") or "").split("|") if a.strip()]
        for a in names:
            a = a.strip()
            if not a:
                continue
            pat = r"(?<![A-Za-z0-9])" + re.escape(a).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9])"
            if re.search(pat, t, re.I):
                is_leg = r.get("book") == "leg"
                if (best_leg and not is_leg) or (is_leg == best_leg and len(a) > best_len):
                    best, best_len, best_leg = r, len(a), is_leg
    return best


# ----------------------------------------------------------------------------- fetch all
_CAPTURE: list | None = None


def _fetch_one(source: str, ident: str, get, today: date, capture: list | None = None):
    """Latest (date, value, url). With ``capture`` (a list), also collects every observation the source
    returned (each fetcher passes its points through ``_last``), so a daily run stores the recent history
    and a missed run leaves no gap."""
    global _CAPTURE, _last
    fn = FETCHERS.get(source)
    if fn is None and source != "boe":
        raise ValueError(f"unknown source {source!r}")
    orig = _last
    if capture is not None:
        def _last(points):  # noqa: F811 - temporary wrapper, restored below
            capture.extend(sorted((d, v) for d, v in points if d is not None and v is not None))
            return orig(points)
    try:
        if source == "boe":
            return fetch_boe(ident, get, today)
        return fn(ident, get)
    finally:
        _last = orig


def fetch_instrument(row: dict, by_id: dict[str, dict], results: dict[str, dict], today: date,
                     get=http_get, previous: dict[str, dict] | None = None) -> dict:
    """One mark for a registry row: primary source, then fallback, then the previous mark."""
    inst = row["instrument"]
    attempts = [(row.get("source", ""), row.get("source_id", ""), row.get("frequency") or "daily", "")]
    if row.get("fallback_source"):
        attempts.append((row["fallback_source"], row.get("fallback_id", ""),
                         "monthly" if row["fallback_source"] == "panel_monthly" else (row.get("frequency") or "daily"),
                         "fallback"))
    errors = []
    for source, ident, freq, tag in attempts:
        try:
            if source == "spread":
                a, b = ident.split("-", 1)
                ra, rb = results.get(a), results.get(b)
                if not ra or not rb or ra.get("value") in (None, "") or rb.get("value") in (None, ""):
                    raise ValueError(f"legs {a}/{b} not marked")
                d = min(parse_date(ra["date"]), parse_date(rb["date"]))
                v = round((float(ra["value"]) - float(rb["value"])) * 100, 2)
                url = f"{ra.get('source_url', '')} ; {rb.get('source_url', '')}"
                freq = "monthly" if "monthly" in (ra.get("frequency"), rb.get("frequency")) else "daily"
                note = f"{a} {ra['value']} ({ra['date']}) minus {b} {rb['value']} ({rb['date']})"
                ha, hb = dict(ra.get("_history") or []), dict(rb.get("_history") or [])
                hist = sorted((dd, round((ha[dd] - hb[dd]) * 100, 2)) for dd in ha if dd in hb) if freq == "daily" else []
            else:
                pts: list = []
                d, v, url = _fetch_one(source, ident, get, today, pts)
                note = ""
                if freq == "daily":
                    hist = sorted({pd_: pv for pd_, pv in pts if (today - pd_).days <= 31}.items())
                else:
                    hist = []
            if tag:
                prev = (previous or {}).get(inst)
                pd_ = parse_date(prev.get("date")) if prev else None
                if prev and prev.get("value") and pd_ and pd_ >= d and (prev.get("frequency") or "daily") == "daily":
                    # never replace a newer first-hand daily mark with an older (or monthly) fallback
                    raise ValueError(f"fallback {source} {ident} is older ({d}) than the previous daily mark ({pd_})")
                note = (f"fallback {source} {ident} after: " + "; ".join(errors) + ("; " + note if note else ""))[:300]
            age = (today - d).days
            if freq == "daily" and age > CONFIG["stale_mark_days"]:
                note = (note + "; " if note else "") + f"stale: last observation {age} days old"
            return {"date": d.isoformat(), "instrument": inst, "value": f"{v:.6g}", "unit": row.get("unit", ""),
                    "frequency": freq, "source": f"{source} {ident}".strip(), "source_url": url,
                    "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "note": note,
                    "_history": [(hd, hv) for hd, hv in hist if hd < d]}
        except Exception as e:  # noqa: BLE001 - try the next source
            errors.append(f"{source} {ident}: {str(e)[:160]}")
    prev = (previous or {}).get(inst)
    if prev:
        p = dict(prev)
        p["note"] = ("kept previous mark; " + "; ".join(errors))[:300]
        p["fetched_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return p
    return {"date": "", "instrument": inst, "value": "", "unit": row.get("unit", ""), "frequency": row.get("frequency", ""),
            "source": row.get("source", ""), "source_url": row.get("source_url", ""),
            "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "note": ("no mark: " + "; ".join(errors))[:300]}


def fetch_all(registry: list[dict], today: date | None = None, get=http_get, only: set[str] | None = None,
              previous: dict[str, dict] | None = None) -> list[dict]:
    today = today or date.today()
    by_id = registry_index(registry)
    results: dict[str, dict] = {}
    # legs and simple instruments first, spreads after their legs
    order = [r for r in registry if r.get("source") != "spread"] + [r for r in registry if r.get("source") == "spread"]
    for row in order:
        if only and row["instrument"] not in only:
            continue
        results[row["instrument"]] = fetch_instrument(row, by_id, results, today, get, previous)
        print(f"{row['instrument']:7s} {results[row['instrument']]['date'] or '-':10s} "
              f"{results[row['instrument']]['value'] or '-':>12s} {results[row['instrument']]['unit']:12s} "
              f"{results[row['instrument']]['source'][:40]} {results[row['instrument']]['note'][:80]}", flush=True)
    return list(results.values())


# ----------------------------------------------------------------------------- marks file
def read_marks(path: Path = MARKS) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def latest_marks(path: Path = MARKS, rows: list[dict] | None = None) -> dict[str, dict]:
    """Latest mark per instrument (by observation date, then fetch time)."""
    out: dict[str, dict] = {}
    for r in (rows if rows is not None else read_marks(path)):
        if not r.get("value"):
            continue
        cur = out.get(r["instrument"])
        if cur is None or (r["date"], r.get("fetched_at", "")) >= (cur["date"], cur.get("fetched_at", "")):
            out[r["instrument"]] = r
    return out


def marks_on_or_before(instrument: str, day: date, rows: list[dict]) -> dict | None:
    """The latest mark of ``instrument`` dated on or before ``day``."""
    best = None
    for r in rows:
        if r.get("instrument") != instrument or not r.get("value"):
            continue
        d = parse_date(r.get("date"))
        if d and d <= day and (best is None or d >= parse_date(best["date"])):
            best = r
    return best


def write_marks(new: list[dict], path: Path = MARKS) -> int:
    """Merge the new marks into the file: one row per (instrument, date), newest fetch wins."""
    rows = read_marks(path)
    keyed = {(r["instrument"], r["date"]): r for r in rows}
    n = 0
    for m in new:
        if not m.get("value") or not m.get("date"):
            continue
        k = (m["instrument"], m["date"])
        if k not in keyed or keyed[k].get("value") != m.get("value"):
            n += 1
        keyed[k] = {c: m.get(c, "") for c in MARK_COLUMNS}
    out = sorted(keyed.values(), key=lambda r: (r["date"], r["instrument"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MARK_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in out:
            w.writerow(r)
    return n


# ----------------------------------------------------------------------------- live P&L
def mark_can_act(mark: dict | None) -> bool:
    """True if a mark may trigger a stop or a horizon close: a first-hand daily observation. A monthly
    average (dated at its month end), a monthly fallback, a mark flagged stale when fetched (its
    observation older than ``stale_mark_days``) and a carried-forward previous mark never act."""
    if not mark or mark.get("value") in (None, ""):
        return False
    if (mark.get("frequency") or "").strip().lower() != "daily":
        return False
    note = (mark.get("note") or "").lower()
    return not ("kept previous mark" in note or "stale" in note or "panel_monthly" in note)


def mark_is_current(decision: dict, mark: dict | None) -> bool:
    """A mark can price or close a decision only if it is dated on or after the decision date
    (a monthly average from before the decision says nothing about the position)."""
    if not mark or not mark.get("value"):
        return False
    md, dd = parse_date(mark.get("date")), parse_date(decision.get("date"))
    return bool(md and (dd is None or md >= dd))


def live_mark(decision: dict, registry: list[dict], latest: dict[str, dict]) -> dict:
    """The current mark of a decision's instrument and the P&L at that mark."""
    row = match_instrument(decision.get("instrument", ""), registry)
    out = {"mark_instrument": row["instrument"] if row else None, "mark": None, "mark_date": None,
           "mark_unit": row.get("unit") if row else None, "mark_frequency": row.get("frequency") if row else None,
           "mark_source": None, "mark_source_url": None, "mark_note": None, "live_pnl_pct": None,
           "stop_distance": None}
    if not row:
        return out
    m = latest.get(row["instrument"])
    if not m:
        return out
    v = _num(m.get("value"))
    out.update({"mark": v, "mark_date": m.get("date"), "mark_frequency": m.get("frequency") or row.get("frequency"),
                "mark_source": m.get("source"), "mark_source_url": m.get("source_url"), "mark_note": m.get("note"),
                "mark_can_act": mark_can_act(m),
                "mark_flag": None if mark_can_act(m) else
                ("monthly average carried at its month end; estimate only, never used for stops or closes"
                 if (m.get("frequency") or "") == "monthly" else "stale or carried-forward mark; never used for stops or closes")})
    if not mark_is_current(decision, m):
        out["mark_note"] = ((out["mark_note"] + "; ") if out["mark_note"] else "") + \
            f"mark dated {m.get('date')} predates the decision ({decision.get('date')}); no live P&L until a newer mark"
        return out
    if v is not None and decision.get("action") in ("Buy", "Sell"):
        out["live_pnl_pct"] = pnl_at_level(decision, v)
    stop = parse_number(decision.get("stop"))
    if v is not None and stop is not None:
        out["stop_distance"] = round(v - stop, 4)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma-separated instrument codes")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--today", default=None)
    ap.add_argument("--backfill", default=None, help="YYYY-MM-DD: write daily history from this date")
    a = ap.parse_args(argv)
    today = parse_date(a.today) if a.today else date.today()
    registry = load_registry()
    only = {s.strip() for s in a.only.split(",") if s.strip()} or None
    if a.backfill:
        rows = backfill(registry, parse_date(a.backfill), only)
        if a.dry_run:
            print(json.dumps(rows[:20], indent=1))
            return 0
        n = write_marks(rows)
        print(f"{n} backfilled marks written to {MARKS.relative_to(ROOT)}")
        return 0
    if only:
        # a spread needs its legs
        for r in registry:
            if r["instrument"] in only and r.get("source") == "spread":
                only |= set(r["source_id"].split("-", 1))
            if r["instrument"] in only and r.get("fallback_source") == "spread":
                only |= set(r["fallback_id"].split("-", 1))
    marks = fetch_all(registry, today, only=only, previous=latest_marks())
    missing = [m["instrument"] for m in marks if not m.get("value")]
    if a.dry_run:
        print(json.dumps(marks, indent=1))
        return 0
    hist_rows = []
    for m in marks:
        for hd, hv in m.get("_history") or []:
            hist_rows.append({**m, "date": hd.isoformat(), "value": f"{hv:.6g}", "note": "recent history returned by the source"})
    existing = {(r["instrument"], r["date"]) for r in read_marks()}
    n = write_marks([r for r in hist_rows if (r["instrument"], r["date"]) not in existing] + marks)
    print(f"{n} new or changed marks written to {MARKS.relative_to(ROOT)}; "
          f"{len(marks) - len(missing)} of {len(marks)} instruments marked"
          + (f"; no mark for {', '.join(missing)}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
