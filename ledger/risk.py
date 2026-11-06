"""Risk Manager: checks every new decision record before it is logged. No API.

Rejects (the record is not logged) when
  * the stop has no numeric price or yield level;
  * a continuous position risks more than 2% of the account;
  * an event bet is not sized at half of quarter-Kelly on its stated probability.
Flags (logged, but reported) when
  * the algorithm (results/systematic/positions.csv) holds a position in the same country or
    the same currency;
  * a catalyst from the Ledger calendar (elections and events in data/events/, rating reviews in
    data/events/rating_calendar.csv, open forecasts' resolution dates, other open decisions'
    horizons, the monthly rebalance) falls inside the holding period.
The result is posted as a comment on the issue by the intake workflow.
"""
from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from .marks import load_registry, match_instrument
from .schema import (MAX_RISK_PCT, kelly_size_pct, parse_date, parse_number, parse_probability, position_type, stop_level,
                     validate_decision)

ROOT = Path(__file__).resolve().parents[1]
CURRENCY_OF = {"BRA": "BRL", "MEX": "MXN", "ZAF": "ZAR", "TUR": "TRY", "IDN": "IDR", "POL": "PLN", "GBR": "GBP",
               "COL": "COP", "CHL": "CLP", "FRA": "EUR", "ITA": "EUR", "ESP": "EUR", "DEU": "EUR", "USA": "USD"}
COUNTRY_ISO3 = {"brazil": "BRA", "mexico": "MEX", "south africa": "ZAF", "turkey": "TUR", "türkiye": "TUR",
                "indonesia": "IDN", "poland": "POL", "united kingdom": "GBR", "uk": "GBR", "britain": "GBR",
                "colombia": "COL", "chile": "CHL", "france": "FRA", "italy": "ITA", "spain": "ESP",
                "germany": "DEU", "euro area": "DEU", "eurozone": "DEU", "united states": "USA", "us": "USA"}
NAME_OF = {"BRA": "Brazil", "MEX": "Mexico", "ZAF": "South Africa", "TUR": "Turkey", "IDN": "Indonesia",
           "POL": "Poland", "GBR": "United Kingdom", "COL": "Colombia", "CHL": "Chile", "FRA": "France",
           "ITA": "Italy", "ESP": "Spain", "DEU": "Germany", "USA": "United States"}
REBALANCE_DAY = 3


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def country_iso3(text: str) -> str | None:
    t = (text or "").strip().lower()
    if t.upper() in NAME_OF:
        return t.upper()
    for name, iso in sorted(COUNTRY_ISO3.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(name)}\b", t):
            return iso
    return None


def decision_scope(rec: dict, registry: list[dict]) -> dict:
    """Country (ISO3), currency and registry instrument of a decision."""
    reg = match_instrument(rec.get("instrument", ""), registry)
    iso3 = (reg or {}).get("iso3") or country_iso3(rec.get("country", "")) or country_iso3(rec.get("instrument", ""))
    ccy = CURRENCY_OF.get(iso3 or "")
    if reg and reg.get("book") == "fx":
        ccy = reg["instrument"]
    return {"iso3": iso3, "currency": ccy, "instrument": (reg or {}).get("instrument"), "registry": reg}


# ----------------------------------------------------------------------------- overlap
def algorithm_overlap(scope: dict, registry: list[dict], root: Path = ROOT) -> list[dict]:
    by_id = {r["instrument"]: r for r in registry}
    out = []
    for p in _rows(root / "results/systematic/positions.csv"):
        inst = p.get("instrument", "")
        reg = by_id.get(inst, {})
        p_iso3, p_ccy = reg.get("iso3"), CURRENCY_OF.get(reg.get("iso3", ""))
        if reg.get("book") == "fx":
            p_ccy = inst
        reasons = []
        if scope.get("instrument") and inst == scope["instrument"]:
            reasons.append("same instrument")
        if scope.get("iso3") and p_iso3 == scope["iso3"]:
            reasons.append("same country")
        if scope.get("currency") and p_ccy == scope["currency"]:
            reasons.append(f"same currency ({p_ccy})")
        if reasons:
            out.append({"instrument": inst, "side": p.get("side"), "size_pct_of_capital": parse_number(p.get("size_pct_of_capital")),
                        "country": reg.get("country") or inst, "reasons": sorted(set(reasons), key=reasons.index),
                        "effective_from": p.get("effective_from")})
    return out


# ----------------------------------------------------------------------------- calendar
def ledger_calendar(root: Path = ROOT, today: date | None = None, exclude_id: str | None = None) -> list[dict]:
    """Every dated catalyst the Ledger knows about, from today on."""
    today = today or date.today()
    cal: list[dict] = []

    def add(d, kind, country, label, source=""):
        d = parse_date(d) if not isinstance(d, date) else d
        if d and d >= today:
            cal.append({"date": d, "kind": kind, "iso3": country_iso3(country or "") or (country.upper() if country and len(country) == 3 else None),
                        "country": country or "", "label": " ".join(str(label or "").split())[:140], "source": source})

    ev = root / "data/events"
    for r in _rows(ev / "upcoming_events.csv"):
        add(r.get("date"), r.get("event_type") or "event", r.get("country") or r.get("iso3"), r.get("description"), "data/events/upcoming_events.csv")
    for r in _rows(ev / "elections.csv"):
        add(r.get("vote_date"), "election", r.get("country") or r.get("iso3"), r.get("election"), "data/events/elections.csv")
    for r in _rows(ev / "calendar_13.csv"):
        add(r.get("date"), r.get("event_type") or "event", r.get("country") or r.get("iso3"), r.get("description"), "data/events/calendar_13.csv")
    for r in _rows(ev / "rating_calendar.csv"):
        add(r.get("date"), "rating review", r.get("country") or r.get("iso3"), f"{r.get('agency', '')} {r.get('description', '')}".strip(), "data/events/rating_calendar.csv")
    el = root / "data/elections/calendar.csv"
    for r in _rows(el):
        add(r.get("date") or r.get("vote_date"), "election", r.get("country") or r.get("iso3"), r.get("election") or r.get("description"), "data/elections/calendar.csv")
    for r in _rows(root / "data/ledger/forecasts.csv"):
        if (r.get("status") or "open").lower() == "open" and r.get("id") != exclude_id:
            add(r.get("resolution_date"), "forecast resolves", r.get("country"), f"{r.get('id')} {r.get('question')}", "data/ledger/forecasts.csv")
    for r in _rows(root / "data/ledger/decisions.csv"):
        if (r.get("status") or "open").lower() == "open" and r.get("id") != exclude_id:
            add(r.get("horizon"), "decision horizon", r.get("country"), f"{r.get('id')} {r.get('instrument')} ({r.get('action')})", "data/ledger/decisions.csv")
    # monthly rebalances of the algorithm on the 3rd, next 18 months
    y, m = today.year, today.month
    for _ in range(18):
        d = date(y, m, REBALANCE_DAY)
        if d >= today:
            cal.append({"date": d, "kind": "algorithm rebalance", "iso3": None, "country": "", "label": "v1.0 monthly rebalance (positions may change)",
                        "source": ".github/workflows/systematic.yml"})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    cal.sort(key=lambda c: (c["date"], c["kind"]))
    seen, out = set(), []
    for c in cal:
        k = (c["date"], c["kind"], c["label"])
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def catalysts_in_period(scope: dict, start: date, end: date, calendar: list[dict], rec: dict | None = None) -> tuple[list[dict], int, int]:
    """Same-country catalysts between start and end; plus the counts of other catalysts and of
    monthly rebalances in the period. The record's own horizon is left out."""
    same, others, rebalances = [], 0, 0
    own = f"{(rec or {}).get('instrument', '')} ({(rec or {}).get('action', '')})"
    for c in calendar:
        if not (start <= c["date"] <= end):
            continue
        if c["kind"] == "algorithm rebalance":
            rebalances += 1
        elif c["kind"] == "decision horizon" and rec and c["date"] == end and c["label"].endswith(own):
            continue
        elif scope.get("iso3") and c["iso3"] == scope["iso3"]:
            same.append(c)
        else:
            others += 1
    return same, others, rebalances


# ----------------------------------------------------------------------------- the check
def risk_check(rec: dict, root: Path = ROOT, today: date | None = None, registry: list[dict] | None = None,
               derivative: dict | None = None) -> dict:
    """``derivative``: ledger.derivs.build_terms's (terms, errors, notes) for a futures or options position; its
    errors reject the record and its terms add the maximum-loss check."""
    today = today or date.today()
    registry = registry if registry is not None else load_registry(root / "data/ledger/instruments.csv")
    errors, notes = validate_decision(rec)
    if derivative:
        errors += derivative.get("errors") or []
        notes += derivative.get("notes") or []
    scope = decision_scope(rec, registry)
    flags: list[str] = []
    checks: list[tuple[bool, str]] = []
    stop_lv = stop_level(rec.get("stop"))
    checks.append((stop_lv is not None, "Stop has a numeric level" + (f": {stop_lv:g}" if stop_lv is not None else "")))
    size, prob = parse_number(rec.get("size_pct")), parse_probability(rec.get("probability"))
    ptype = position_type(rec)
    if rec.get("action") in ("Buy", "Sell"):
        if ptype == "event":
            req = kelly_size_pct(prob) if prob is not None else None
            ok = req is not None and req > 0 and size is not None and abs(size - req) <= 0.05
            checks.append((ok, f"Event bet sized at half of quarter-Kelly: required {req:g}% at p {prob:g}%, size {size if size is not None else '?'}%"
                           if req is not None else "Event bet sized at half of quarter-Kelly: probability missing"))
        else:
            ok = size is not None and 0 < size <= MAX_RISK_PCT
            checks.append((ok, f"Continuous position risks at most {MAX_RISK_PCT:g}%: size {size if size is not None else '?'}%"))
    else:
        checks.append((size in (None, 0), "No trade has size 0"))
    dt = (derivative or {}).get("terms")
    if dt:
        what = {"future": "Futures position", "call": "Long call", "put": "Long put"}.get(dt["structure"], dt["structure"].capitalize())
        checks.append((True, f"{what} on {dt['product']} {dt['contract_month']}: maximum loss "
                             f"{dt['risk_per_unit']} per unit" + (" (the premium)" if dt["entry_premium"] and float(dt["entry_premium"]) > 0 else "")
                             + f", which is the size at risk ({size if size is not None else '?'}% of account)"))
        if dt["structure"] != "future":
            checks.append((True, f"Implied volatility at entry {dt['iv_entry_pct']}% ({dt['iv_source']})"))
    elif derivative and derivative.get("errors"):
        checks.append((False, "Futures/options terms complete"))
    overlap = []
    cats, n_other, n_reb = [], 0, 0
    if not errors:
        overlap = algorithm_overlap(scope, registry, root)
        for o in overlap:
            flags.append(f"Overlap with the algorithm: {o['side']} {o['instrument']} "
                         f"({o['size_pct_of_capital']:+.1f}% of capital, {o['country']}, effective {o['effective_from']}; "
                         f"{', '.join(o['reasons'])})")
        start, end = parse_date(rec.get("date")) or today, parse_date(rec.get("horizon"))
        if end:
            cal = ledger_calendar(root, min(today, start), exclude_id=rec.get("id"))
            cats, n_other, n_reb = catalysts_in_period(scope, start, end, cal, rec)
            for c in cats:
                flags.append(f"Catalyst in the holding period: {c['date'].isoformat()} {c['kind']}"
                             f"{' (' + c['country'] + ')' if c['country'] else ''}: {c['label']}")
    verdict = "rejected" if errors else (f"passed with {len(flags)} flag{'s' if len(flags) != 1 else ''}" if flags else "passed")
    lines = [f"### Risk Manager: {verdict}",
             f"{rec.get('action')} {rec.get('instrument')} ({rec.get('country')}), {ptype or 'no trade'}, "
             f"size {rec.get('size_pct')}%, p {rec.get('probability')}%, horizon {rec.get('horizon')}"
             + (f"; marked at the {dt['mark_source']} of {dt['contract_month']}{' (proxy)' if dt['proxy'] == 'yes' else ''}"
                if dt else f"; registry instrument {scope['instrument']}" if scope.get("instrument")
                else "; instrument not in the registry (no marks, no overlap check by instrument)"),
             ""]
    lines += [f"- {'✅' if ok else '❌'} {text}" for ok, text in checks]
    lines += [f"- ❌ {e}" for e in errors]
    lines += [f"- ⚠️ {fl}" for fl in flags]
    if not errors and not overlap:
        lines.append("- ✅ No algorithm position in the same country or currency")
    if not errors and not cats and parse_date(rec.get("horizon")):
        lines.append(f"- ✅ No same-country catalyst in the holding period" + (f" ({n_other} elsewhere)" if n_other else ""))
    elif not errors and n_other:
        lines.append(f"- ℹ️ {n_other} other catalyst{'s' if n_other != 1 else ''} elsewhere in the period")
    if not errors and n_reb:
        lines.append(f"- ℹ️ {n_reb} monthly rebalance{'s' if n_reb != 1 else ''} of the algorithm in the period (its positions may change)")
    lines += [f"- ℹ️ {n}" for n in notes]
    return {"ok": not errors, "errors": errors, "flags": flags, "notes": notes, "checks": checks, "overlap": overlap,
            "catalysts": [{**c, "date": c["date"].isoformat()} for c in cats], "verdict": verdict, "scope": scope,
            "comment": "\n".join(lines)}
