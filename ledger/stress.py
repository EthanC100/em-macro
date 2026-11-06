"""Stress tests: each book's current positions replayed through three historical episodes.

    python -m ledger.stress           # fetch any missing history, then write data/ledger/stress.json

Each position is held unchanged from the episode's start to its end, and the instrument moves as it did then:
  * FX and commodities by the relative price change; yields and spreads by the absolute change in % or bp;
  * the algorithm: weight x long return (bonds and spreads through the 10-year duration at the start level, no carry);
  * Janus: notional x position return (filled positions; pending orders at their requested risk);
  * my decisions: size x level change x direction / |entry - stop| (the P&L formula of ledger/scoring.py), the change
    applied to the current mark (relative for prices, absolute for yields and spreads).
Instruments without history over an episode are listed, not guessed. Monthly-average history (marked) is used only
where no daily series exists, and the result says so.

Sources: data/processed/daily_panel.csv (EM FX and yields, the project's panel), data/processed/country_month_panel.csv
(monthly averages: Indonesia, Colombia, Chile, Italy and Spain), FRED (US 10y, major FX, energy), Bundesbank (Bund),
Bank of England (gilt), Japan MoF (JGB), Riksbank (French and German benchmarks). Fetched endpoints are cached in
data/ledger/stress_history.json, so the episodes are downloaded once.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from . import janus as JN
from . import pricing as PX
from .marks import (bundesbank_history, fred_history, http_get, load_registry, mof_jgb_history,
                    riksbank_history)
from .schema import parse_date, parse_number

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/ledger/stress_history.json"
OUT = ROOT / "data/ledger/stress.json"
SCENARIOS = [
    {"id": "gfc", "name": "Sep-Oct 2008 (Lehman)", "start": "2008-08-29", "end": "2008-10-31"},
    {"id": "covid", "name": "March 2020 (Covid)", "start": "2020-02-28", "end": "2020-03-31"},
    {"id": "rates2022", "name": "2022 rate shock", "start": "2021-12-31", "end": "2022-10-31"},
]
PANEL_DAILY = {"BRL": "FX_BR", "MXN": "FX_MX", "ZAR": "FX_ZA", "TRY": "FX_TR", "IDR": "FX_ID", "PLN": "FX_PL",
               "BR10Y": "Y10_BR", "MX10Y": "Y10_MX", "ZA10Y": "Y10_ZA", "TR10Y": "Y10_TR", "PL10Y": "Y10_PL"}
PANEL_MONTHLY = {"ID10Y": ("y10", "IDN"), "CO10Y": ("y10", "COL"), "CL10Y": ("y10", "CHL"),
                 "IT-DE": ("spread_vs_de_bp", "ITA"), "ES-DE": ("spread_vs_de_bp", "ESP"),
                 "COP": ("fx_per_usd_end", "COL"), "CLP": ("fx_per_usd_end", "CHL")}
FRED = {"US10Y": "DGS10", "EUR": "DEXUSEU", "GBP": "DEXUSUK", "JPY": "DEXJPUS", "CHF": "DEXSZUS", "CAD": "DEXCAUS",
        "AUD": ("DEXUSAL", "invert"), "WTI": "DCOILWTICO", "BRENT": "DCOILBRENTEU", "NATGAS": "DHHNGSP",
        "HEATOIL": "DHOILNYH", "RBOB": "DGASNYH"}
SPREADS = {"FR-DE": ("FR10Y", "DE10YBM"), "GB-DE": ("GB10Y", "DE10Y"), "PL-DE": ("PL10Y", "DE10Y")}


def _csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _endpoints(points: list[tuple[date, float]], start: date, end: date) -> tuple | None:
    """The last observation on or before ``start`` (within 10 days) and on or before ``end``."""
    pts = sorted((d, v) for d, v in points if d and v is not None)
    a = [p for p in pts if start - timedelta(days=10) <= p[0] <= start]
    b = [p for p in pts if end - timedelta(days=10) <= p[0] <= end]
    if not a or not b:
        return None
    return a[-1], b[-1]


def history_endpoints(inst: str, sc: dict, get=http_get) -> dict | None:
    s, e = parse_date(sc["start"]), parse_date(sc["end"])
    src, monthly = None, False
    pts: list = []
    if inst in PANEL_DAILY:
        col = PANEL_DAILY[inst]
        pts = [(parse_date(r["date"]), parse_number(r.get(col))) for r in _csv(ROOT / "data/processed/daily_panel.csv")]
        src = f"data/processed/daily_panel.csv {col}"
    elif inst in PANEL_MONTHLY:
        col, iso = PANEL_MONTHLY[inst]
        for r in _csv(ROOT / "data/processed/country_month_panel.csv"):
            if r.get("iso3") == iso and parse_number(r.get(col)) is not None:
                y, m = int(r["month"][:4]), int(r["month"][5:7])
                nd = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
                pts.append((nd, parse_number(r[col])))
        src, monthly = f"data/processed/country_month_panel.csv {col}:{iso} (monthly)", col != "fx_per_usd_end"
    elif inst in FRED:
        sid = FRED[inst]
        inv = isinstance(sid, tuple)
        sid = sid[0] if inv else sid
        pts, _ = fred_history(sid, s - timedelta(days=20), get)
        if inv:
            pts = [(d, 1.0 / v) for d, v in pts if v]
        src, monthly = f"FRED {sid}", sid.startswith("IRLTLT")
    elif inst == "GB10Y":
        frm, to = (s - timedelta(days=20)).strftime("%d/%b/%Y"), (e + timedelta(days=1)).strftime("%d/%b/%Y")
        url = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes"
               f"&Datefrom={frm}&Dateto={to}&SeriesCodes=IUDMNPY&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
        rows = list(csv.reader(get(url, browser=True).decode("utf-8", "replace").splitlines()))
        from .marks import _num
        pts = [(parse_date(r[0]), _num(r[1])) for r in rows[1:] if len(r) >= 2]
        src = "Bank of England IUDMNPY"
    elif inst in ("DE10Y",):
        pts, _ = bundesbank_history("D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A", s - timedelta(days=20), get)
        src = "Bundesbank BBSIS 10y"
    elif inst in ("DE10YBM", "FR10Y"):
        sid = "DEGVB10Y" if inst == "DE10YBM" else "FRGVB10Y"
        pts, _ = riksbank_history(sid, s - timedelta(days=20), get, end=e + timedelta(days=1))
        src = f"Riksbank {sid}"
    elif inst == "JP10Y":
        import urllib.request  # noqa: F401
        url = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
        rows = list(csv.reader(get(url, browser=True).decode("utf-8", "replace").splitlines()))
        head = next(i for i, r in enumerate(rows) if r and r[0].strip().lower() == "date")
        col = [c.strip() for c in rows[head]].index("10Y")
        for r in rows[head + 1:]:
            try:
                y, m, d = (int(x) for x in r[0].split("/"))
                pts.append((date(y, m, d), float(r[col])))
            except (ValueError, IndexError):
                continue
        src = "Japan MoF jgbcme_all.csv 10Y"
    elif inst in SPREADS:
        a, b = SPREADS[inst]
        ea, eb = history_endpoints(a, sc, get), history_endpoints(b, sc, get)
        if not ea or not eb:
            return None
        return {"v0": round((ea["v0"] - eb["v0"]) * 100, 2), "v1": round((ea["v1"] - eb["v1"]) * 100, 2),
                "d0": ea["d0"], "d1": ea["d1"], "source": f"{ea['source']} minus {eb['source']}",
                "monthly": ea["monthly"] or eb["monthly"], "leg_yield": ea["v0"]}
    else:
        return None
    ep = _endpoints(pts, s, e)
    if not ep:
        return None
    (d0, v0), (d1, v1) = ep
    return {"v0": v0, "v1": v1, "d0": d0.isoformat(), "d1": d1.isoformat(), "source": src, "monthly": monthly}


def load_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def fill_cache(instruments: set[str], refresh: bool = False) -> dict:
    cache = load_cache()
    for inst in sorted(instruments):
        for sc in SCENARIOS:
            key = f"{inst}|{sc['id']}"
            if key in cache and not refresh:
                continue
            try:
                cache[key] = history_endpoints(inst, sc)
            except Exception as e:  # noqa: BLE001 - a source that fails is listed, not guessed
                cache[key] = {"error": str(e)[:200]}
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    return cache


def run(books: dict, cache: dict | None = None) -> dict:
    """``books``: ledger.books.build_books output (positions of each book)."""
    reg = {r["instrument"]: r for r in load_registry()}
    cache = cache if cache is not None else load_cache()
    out = {"scenarios": [], "method": __doc__.split("Sources:")[0].strip()}
    # positions per book: (book, id, instrument, fn(scenario endpoints) -> loss % of the book's capital)
    pos = []
    for v in books["algorithm"]["versions"]:
        for p in (v["estimate"] or {}).get("positions", []):
            pos.append((f"algorithm {v['id']}", p["instrument"], p["instrument"], ("algo", (p["size_pct"] or 0) / 100.0)))
    for p in books["janus"]["summary"]["open"]:
        nf = (p.get("fill") or {}).get("notional_frac")
        pos.append(("janus", p["id"], p["instrument"], ("janus", (nf, p["direction"], p.get("requested_risk_pct"), p["stop"],
                                                                  p.get("mark")))))
    for p in books["me"]["positions"]:
        if p["status"] == "open" and p["action"] in ("Buy", "Sell") and p.get("mark_instrument"):
            pos.append(("me", p["id"], p["mark_instrument"], ("me", p)))
    for sc in SCENARIOS:
        per_book: dict[str, float] = {}
        rows, missing = [], []
        for book, pid, inst, (mode, arg) in pos:
            ep = cache.get(f"{inst}|{sc['id']}")
            if not ep or ep.get("error") or ep.get("v0") is None:
                missing.append({"book": book, "id": pid, "instrument": inst,
                                "reason": (ep or {}).get("error") or "no history over this episode"})
                continue
            k = PX.kind_of(reg.get(inst, {}))
            leg = ep.get("leg_yield")
            r_long = PX.ret_long(k, ep["v0"], ep["v1"], leg_yield=leg)
            if mode == "algo":
                loss = 100 * arg * r_long
            elif mode == "janus":
                nf, direction, req_risk, stop, mark = arg
                if nf is None and mark is not None:
                    sr = PX.stop_return(k, direction, mark, stop)
                    nf = (req_risk or 0) / 100.0 / abs(sr) if sr else 0.0
                loss = 100 * (nf or 0) * PX.signed(direction) * r_long
            else:
                d = arg
                entry, stop, size, mark = d.get("entry_level"), d.get("stop"), d.get("size_pct"), d.get("mark")
                if None in (entry, stop, size, mark) or entry == stop:
                    missing.append({"book": book, "id": pid, "instrument": inst, "reason": "no entry level or stop"})
                    continue
                delta = (ep["v1"] - ep["v0"]) if k in ("yield", "spread") else mark * (ep["v1"] / ep["v0"] - 1)
                direction = 1.0 if entry > stop else -1.0
                loss = size * delta * direction / abs(entry - stop)
            per_book[book] = per_book.get(book, 0.0) + loss
            rows.append({"book": book, "id": pid, "instrument": inst, "pnl_pct": round(loss, 3),
                         "move": f"{ep['v0']:g} -> {ep['v1']:g} ({ep['d0']} to {ep['d1']})", "source": ep["source"],
                         "monthly": bool(ep.get("monthly"))})
        out["scenarios"].append({**sc, "by_book": {k: round(v, 3) for k, v in per_book.items()}, "positions": rows,
                                 "missing": missing})
    return out


def main(argv=None) -> int:
    from datetime import date as _d
    from . import build, books as B
    alg = build.build_algorithm()
    bk = B.build_books(_d.today(), alg)
    insts = {p["instrument"] for v in bk["algorithm"]["versions"] for p in (v["estimate"] or {}).get("positions", [])}
    insts |= {p["instrument"] for p in bk["janus"]["summary"]["open"]}
    insts |= {p["mark_instrument"] for p in bk["me"]["positions"] if p.get("mark_instrument")}
    insts |= set(JN.UNIVERSE)
    cache = fill_cache(insts)
    res = run(bk, cache)
    res["as_of"] = _d.today().isoformat()
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for sc in res["scenarios"]:
        print(sc["name"], sc["by_book"], "missing:", [m["instrument"] for m in sc["missing"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
