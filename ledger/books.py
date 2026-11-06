"""The three books, side by side: Me (my decisions), the Algorithm (v1.0 and v1.1, mechanical rules) and Janus (AI).

Every figure here is computed from the repository's files on each build (and by ``ledger.changes`` after each
automated run); nothing is stored by hand.

* **Me:** live P&L in % of my account from my decisions (data/ledger/decisions.csv): open positions marked at
  first-hand daily marks (ledger/marks.py ``live_mark`` rules), resolved positions at their booked P&L.
  Index = 100 + cumulative P&L, from the first decision's date.
* **Algorithm:** the official monthly paper P&L (results/systematic*/paper_pnl.csv) for booked live months, and
  for the month in progress an *estimate, month to date*: the current positions times each instrument's move
  since the last mark on or before the month start, with carry accrued at the latest policy rates (FX: local
  rate minus the US rate; bonds: yield minus the local policy rate; spreads: the spread). Instruments without a
  free daily source are carried at their last mark and flagged. The 3rd-of-month official figure replaces the
  estimate when the month is booked.
* **Janus:** ledger/janus.py's daily equity.
* **Cash:** the 3-month US Treasury bill (FRED DTB3) accrued daily from each book's live start.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from . import capacity as CAP
from . import derivs as DV
from . import janus as JN
from . import pricing as PX
from .marks import latest_marks, live_mark, load_registry, mark_can_act, match_instrument, read_marks
from .schema import parse_date, parse_number, parse_probability, stop_level
from .scoring import pnl_at_level, score_decision

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"me": "blue", "algorithm": "gold", "janus": "purple"}
ME_RISK_LIMIT_PCT = 10.0          # total % of account at risk across my open positions (2% each: ledger/risk.py)
ALGO_LEVERAGE_CAP = 6.0           # frozen design gross_leverage_cap
CURRENCY_OF = {"BRA": "BRL", "MEX": "MXN", "ZAF": "ZAR", "TUR": "TRY", "IDN": "IDR", "POL": "PLN", "GBR": "GBP",
               "COL": "COP", "CHL": "CLP", "FRA": "EUR", "ITA": "EUR", "ESP": "EUR", "DEU": "EUR", "USA": "USD",
               "JPN": "JPY", "CHE": "CHF", "AUS": "AUD", "CAN": "CAD"}


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def bdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


class MarkBook:
    """Daily marks by instrument (first-hand daily marks only, unless ``all_marks``)."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows if rows is not None else read_marks()
        self.reg = {r["instrument"]: r for r in load_registry()}
        self._s: dict[tuple, list] = {}

    def series(self, inst: str, all_marks: bool = False) -> list[tuple[date, float, dict]]:
        key = (inst, all_marks)
        if key not in self._s:
            self._s[key] = JN.series(self.rows, inst, actable_only=not all_marks)
        return self._s[key]

    def on(self, inst: str, d: date, all_marks: bool = False):
        best = None
        for x in self.series(inst, all_marks):
            if x[0] <= d:
                best = x
            else:
                break
        return best

    def kind(self, inst: str) -> str:
        return PX.kind_of(self.reg.get(inst, {}))

    def frequency(self, inst: str) -> str:
        return (self.reg.get(inst) or {}).get("frequency") or ""


# ----------------------------------------------------------------------------- cash
def cash_index(mb: MarkBook, start: date, end: date) -> list[list]:
    idx, out = 100.0, []
    days = bdays(start, end)
    for a, b in zip(days, days[1:]):
        lv = mb.on("USDCASH", a)
        if lv:
            idx *= 1 + lv[1] / 100.0 * (b - a).days / 365.0
        out.append([b.isoformat(), round(idx, 4)])
    return [[start.isoformat(), 100.0]] + out


# ----------------------------------------------------------------------------- me
def me_book(today: date, mb: MarkBook) -> dict:
    from .audit import corrections as _corrections
    corr = _corrections()
    registry = load_registry()
    decisions = _rows(ROOT / "data/ledger/decisions.csv")
    positions = [d for d in decisions if d.get("action") in ("Buy", "Sell")]
    start = min((parse_date(d["date"]) for d in decisions if parse_date(d.get("date"))), default=today)
    latest = latest_marks(rows=mb.rows)
    rows = []
    for d in decisions:
        reg = match_instrument(d.get("instrument", ""), registry)
        status = (d.get("status") or "open").strip().lower()
        dv = DV.live(d)                     # futures/options: P&L in % from contract-month settlements, no prices
        if dv:
            reg = None
        lm = (dv if dv else live_mark(d, registry, latest)) if status == "open" else ({"derivative": dv["derivative"]} if dv else {})
        inst = reg["instrument"] if reg else None
        hist = []
        if inst:
            dd = parse_date(d.get("date"))
            for x in mb.series(inst, all_marks=True):
                if dd and x[0] >= dd - timedelta(days=7):
                    hist.append([x[0].isoformat(), x[1], (x[2].get("frequency") or "")])
        sc = score_decision(d)
        rows.append({"book": "me", "id": d["id"], "instrument": d.get("instrument"), "mark_instrument": inst,
                     "country": d.get("country"), "iso3": (reg or {}).get("iso3"), "action": d.get("action"),
                     "direction": "long" if d.get("action") == "Buy" else ("short" if d.get("action") == "Sell" else "none"),
                     "status": status, "size_pct": parse_number(d.get("size_pct")), "date": d.get("date"),
                     "horizon": d.get("horizon"), "probability": parse_probability(d.get("probability")),
                     "entry_level": parse_number(d.get("entry_level")), "entry_text": d.get("entry_level"),
                     "stop": stop_level(d.get("stop")),
                     "corrections": [c for c in corr if c["kind"] == "decision" and c["id"] == d["id"]],
                     "thesis": d.get("thesis"), "change_mind": d.get("change_mind"), "outcome": d.get("outcome"),
                     "pnl_pct": sc["pnl_pct"], "brier": sc["brier"], "unit": (reg or {}).get("unit"),
                     "asset_class": "Commodities" if dv else asset_class((reg or {}).get("kind"), (reg or {}).get("book")),
                     "currency": currency_of(inst, reg), "mark_history": hist, **lm})
    series = []
    dterms = DV.load_terms()
    for day in bdays(start, today):
        tot = 0.0
        for d in positions:
            dd = parse_date(d.get("date"))
            if not dd or dd > day:
                continue
            st = (d.get("status") or "open").lower()
            rd = parse_date(d.get("resolved_date"))
            if st == "resolved" and rd and rd <= day:
                tot += score_decision(d)["pnl_pct"] or 0.0
                continue
            if d["id"] in dterms:
                tot += DV.pnl_on(d["id"], day) or 0.0
                continue
            reg = match_instrument(d.get("instrument", ""), registry)
            if not reg:
                continue
            lv = mb.on(reg["instrument"], day)
            if lv and lv[0] >= dd:
                p = pnl_at_level(d, lv[1])
                tot += p or 0.0
        series.append([day.isoformat(), round(100.0 + tot, 4)])
    open_pos = [r for r in rows if r["status"] == "open" and r["action"] in ("Buy", "Sell")]
    resolved = [r for r in rows if r["status"] == "resolved"]
    briers = [r["brier"] for r in resolved if r["brier"] is not None]
    risk = sum(abs(r["size_pct"] or 0) for r in open_pos)
    return {"id": "me", "name": "Me", "color": COLORS["me"], "kind": "discretionary (my decisions)",
            "live_start": start.isoformat(), "series": series, "positions": rows,
            "open_count": len(open_pos), "risk_used_pct": round(risk, 3), "risk_limit_pct": ME_RISK_LIMIT_PCT,
            "risk_label": "% of account at risk (2% max each)",
            "brier": round(sum(briers) / len(briers), 4) if briers else None, "brier_n": len(briers),
            "unit": "% of my account", "estimate": False}


def asset_class(kind: str | None, book: str | None = None) -> str:
    k = (kind or "").lower()
    if k == "fx":
        return "FX"
    if k == "spread":
        return "Rates spreads"
    if k == "commodity":
        return "Commodities"
    if k in ("yield", "rates"):
        return "Rates"
    return "Other"


def currency_of(inst: str | None, reg: dict | None) -> str | None:
    if not reg:
        return None
    if reg.get("kind") == "fx":
        return inst
    return None


# ----------------------------------------------------------------------------- algorithm
def _policy_rates() -> tuple[dict[str, float], float | None]:
    rows = _rows(ROOT / "data/processed/country_month_panel.csv")
    pol, us = {}, None
    for r in sorted(rows, key=lambda r: r.get("month", "")):
        v = parse_number(r.get("policy_rate"))
        if v is not None:
            pol[r["iso3"]] = v
        f = parse_number(r.get("fed_funds"))
        if f is not None:
            us = f
    return pol, us


def algo_estimate(positions: list[dict], mb: MarkBook, month: str, today: date) -> dict:
    """Estimate, month to date, of a set of positions effective ``month`` (YYYY-MM)."""
    y, m = int(month[:4]), int(month[5:7])
    start = date(y, m, 1)
    base_day = start - timedelta(days=1)
    pol, us = _policy_rates()
    per, flagged = [], []
    days = bdays(start, min(today, date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)))
    daily = {d: 0.0 for d in days}
    for p in positions:
        inst = p["instrument"]
        w = (p.get("size_pct_of_capital") or 0.0) / 100.0
        reg = mb.reg.get(inst, {})
        k = PX.kind_of(reg)
        base = mb.on(inst, base_day, all_marks=True)
        last = mb.on(inst, today, all_marks=True)
        daily_src = mb.frequency(inst) == "daily" and base is not None and mark_can_act(base[2])
        iso = reg.get("iso3")
        if k in ("fx_per_usd", "usd_per_fx"):
            carry_rate = ((pol.get(iso) or 0.0) - (us or 0.0)) / 100.0
        elif k == "yield":
            carry_rate = None
        else:
            carry_rate = None
        contrib = None
        if base and last:
            if not daily_src or not mark_can_act(last[2]):
                flagged.append(inst)
            for d in days:
                lv = mb.on(inst, d, all_marks=True) or base
                n = (d - base_day).days
                if k == "yield":
                    r = PX.ret_long(k, base[1], lv[1], days=n, carry=True, funding=pol.get(iso))
                elif k == "spread":
                    leg = mb.on(inst.split("-")[0] + "10Y", d, all_marks=True)
                    r = PX.ret_long(k, base[1], lv[1], days=n, carry=True, leg_yield=leg[1] if leg else None)
                else:
                    r = PX.ret_long(k, base[1], lv[1]) + (carry_rate or 0.0) * n / 365.0
                daily[d] += w * r
                contrib = w * r
        else:
            flagged.append(inst)
        per.append({"instrument": inst, "country": p.get("country"), "side": p.get("side"),
                    "size_pct": p.get("size_pct_of_capital"), "asset_class": "FX" if p.get("book") == "fx" else (
                        "Rates spreads" if "-" in inst else "Rates"),
                    "base_mark": base[1] if base else None, "base_date": base[0].isoformat() if base else None,
                    "mark": last[1] if last else None, "mark_date": last[0].isoformat() if last else None,
                    "mtd_pct": round(100 * contrib, 4) if contrib is not None else None,
                    "carried": inst in flagged,
                    "carry_z": p.get("carry_z"), "trend_z": p.get("trend_z"), "value_z": p.get("value_z"),
                    "unit": reg.get("unit"), "frequency": mb.frequency(inst), "description": p.get("description"),
                    "risk_share_pct": p.get("risk_share_pct"), "instrument_vol_pct": p.get("instrument_vol_pct"),
                    "mark_history": [[x[0].isoformat(), x[1], x[2].get("frequency") or ""]
                                     for x in mb.series(inst, all_marks=True) if x[0] >= base_day - timedelta(days=10)]})
    series = [[d.isoformat(), round(100 * v, 4)] for d, v in sorted(daily.items())]
    return {"month": month, "base_date": base_day.isoformat(), "mtd_pct": series[-1][1] if series else 0.0,
            "series": series, "positions": per, "carried": sorted(set(flagged)),
            "label": "estimate, month to date",
            "note": ("Estimate, month to date: current positions x each instrument's move since the last mark on or before "
                     f"{base_day.isoformat()}, plus carry at the latest policy rates; costs and the bond model's monthly-average "
                     "timing are not replicated. Instruments without a free daily source are carried at their last mark and "
                     "flagged. The official figure from the 3rd-of-month run replaces it.")}


def signal_attribution(per: list[dict]) -> list[dict]:
    """Approximate: each position's month-to-date P&L split across carry, trend and value by the share of each
    signal's z-score that points the same way as the position (signals pointing the other way get no share)."""
    out = {"carry": 0.0, "trend": 0.0, "value": 0.0}
    for p in per:
        if p.get("mtd_pct") is None:
            continue
        sgn = 1.0 if (p.get("size_pct") or 0) > 0 else -1.0
        zs = {s: max(0.0, sgn * (p.get(f"{s}_z") or 0.0)) for s in out}
        tot = sum(zs.values())
        if tot <= 0:
            continue
        for s in out:
            out[s] += p["mtd_pct"] * zs[s] / tot
    return [{"key": k, "pnl_pct": round(v, 4)} for k, v in out.items()]


def group(per: list[dict], key: str, val: str) -> list[dict]:
    g: dict[str, float] = {}
    for p in per:
        if p.get(val) is None:
            continue
        g[p.get(key) or "Other"] = g.get(p.get(key) or "Other", 0.0) + p[val]
    return [{"key": k, "pnl_pct": round(v, 4)} for k, v in sorted(g.items(), key=lambda kv: -abs(kv[1]))]


def positions_set(vid: str) -> str | None:
    """The date the current positions were set: the run date in the positions file (v1.0), else its rebalance log."""
    rel = "results/systematic/positions.csv" if vid == "v1.0" else "results/systematic_v1.1/positions.csv"
    rows = _rows(ROOT / rel)
    if rows and rows[0].get("run_date"):
        return rows[0]["run_date"]
    log = _rows(ROOT / ("results/systematic_v1.1/rebalance_log.csv" if vid == "v1.1" else "results/systematic/rebalance_log.csv"))
    if log:
        return log[-1].get("run_date") or log[-1].get("date")
    from .capacity import _git
    return (_git("log", "-1", "--format=%as", "--", rel) or "").strip() or None


def algo_book(alg: dict, mb: MarkBook, today: date) -> dict:
    """Both versions; ``alg`` is ledger.build.build_algorithm()'s output."""
    versions = []
    for vid, months, pos, live_start, cap in (
            ("v1.0", alg["months"], alg["positions"], alg["rebalance"]["live_start_month"], alg.get("capacity")),
            ("v1.1", alg["v11"]["months"], alg["v11"]["positions"], alg["v11"]["live_start_month"], alg["v11"].get("capacity"))):
        eff = pos[0].get("effective_from") if pos else None
        est = algo_estimate(pos, mb, eff, today) if eff else None
        live_months = [m for m in months if m.get("live")]
        # daily index: 100 at the live start, official month ends, then the estimate for the month in progress
        y, mm = int(live_start[:4]), int(live_start[5:7])
        start_day = date(y, mm, 1) - timedelta(days=1)
        series, idx = [[start_day.isoformat(), 100.0, "official"]], 100.0
        idx_imp = 100.0
        imp_series = [[start_day.isoformat(), 100.0]]
        for m in live_months:
            idx *= 1 + (m["net"] or 0.0)
            idx_imp *= 1 + (m.get("net_with_impact") if m.get("net_with_impact") is not None else (m["net"] or 0.0))
            yy, m2 = int(m["month"][:4]), int(m["month"][5:7])
            end = date(yy + (m2 == 12), m2 % 12 + 1, 1) - timedelta(days=1)
            series.append([end.isoformat(), round(idx, 4), "official"])
            imp_series.append([end.isoformat(), round(idx_imp, 4)])
        is_live = bool(eff and eff >= live_start)
        booked = {m["month"] for m in live_months}
        mtd_imp = 0.0
        if est and eff not in booked:
            if is_live:
                hist = CAP.monthly_impact(CAP.position_history(
                    "results/systematic/positions.csv" if vid == "v1.0" else "results/systematic_v1.1/positions.csv"),
                    CAP.load_reference(), {p["instrument"]: p.get("instrument_vol_pct") for p in pos})
                mtd_imp = 100 * (hist.get(eff, {}).get("impact_frac") or 0.0)
                for d, v in est["series"]:
                    series.append([d, round(idx * (1 + v / 100.0), 4), "estimate"])
                    imp_series.append([d, round(idx_imp * (1 + (v - mtd_imp) / 100.0), 4)])
        gross = sum(abs(p.get("size_pct_of_capital") or 0) for p in pos) / 100.0
        prev_month_end = series[-1][1]
        mtd = est["mtd_pct"] if (est and is_live and eff not in booked) else None
        versions.append({
            "id": vid, "label": "v1.0 (frozen control)" if vid == "v1.0" else "v1.1 (v1.0 + T18 turnover rule)",
            "live_start_month": live_start, "live_start": start_day.isoformat(), "is_live": is_live,
            "series": series if is_live or live_months else [], "impact_series": imp_series if (is_live or live_months) else [],
            "estimate": est, "mtd_pct": mtd, "mtd_impact_pct": round(mtd_imp, 4) if is_live else None,
            "pre_live_estimate_pct": est["mtd_pct"] if (est and not is_live) else None,
            "index": series[-1][1] if (is_live or live_months) else 100.0, "official_index": round(idx, 4),
            "n_positions": len(pos), "gross_leverage": round(gross, 3), "leverage_cap": ALGO_LEVERAGE_CAP,
            "effective_from": eff, "positions_set": positions_set(vid),
            "capacity_flagged": (cap or {}).get("flagged", []),
            "attribution": {
                "country": group(est["positions"], "country", "mtd_pct") if est else [],
                "asset_class": group(est["positions"], "asset_class", "mtd_pct") if est else [],
                "signal": signal_attribution(est["positions"]) if est else [],
                "official_books": [{"key": "FX", "pnl_pct": round(100 * sum(m.get("fx_gross") or 0 for m in live_months), 4)},
                                   {"key": "Bonds", "pnl_pct": round(100 * sum(m.get("bond_gross") or 0 for m in live_months), 4)},
                                   {"key": "Costs", "pnl_pct": round(-100 * sum(m.get("cost") or 0 for m in live_months), 4)}]
                if vid == "v1.0" else [],
            },
        })
    v10 = versions[0]
    return {"id": "algorithm", "name": "Algorithm", "color": COLORS["algorithm"],
            "kind": "mechanical rules (not AI): v1.0 frozen control and v1.1", "versions": versions,
            "live_start": v10["live_start"], "series": v10["series"], "open_count": v10["n_positions"],
            "risk_used": v10["gross_leverage"], "risk_limit": ALGO_LEVERAGE_CAP,
            "risk_label": "gross leverage (x capital) against the frozen cap",
            "mtd_pct": v10["mtd_pct"], "estimate": True, "capital_usd": CAP.algo_capital("2026-12")}


# ----------------------------------------------------------------------------- janus
def janus_book(today: date, mb: MarkBook) -> dict:
    recs = JN.load()
    s = JN.summarize(recs, mb.rows, today)
    eq = s["equity"]
    return {"id": "janus", "name": "Janus", "color": COLORS["janus"], "kind": "AI discretionary (experiment)",
            "live_start": s["start"]["date"] if s["start"] else None, "series": eq,
            "open_count": s["n_open"], "risk_used_pct": s["risk_used_pct"], "risk_limit_pct": s["risk_limit_pct"],
            "risk_label": "% of account at risk (2% max each)", "summary": s}


# ----------------------------------------------------------------------------- shared
def mtd(series: list[list], today: date) -> float | None:
    """Month-to-date change of an index series [[date, value, ...]]: from the last point of the previous month."""
    if not series:
        return None
    month_start = today.replace(day=1)
    before = [p for p in series if parse_date(p[0]) < month_start]
    base = before[-1][1] if before else series[0][1]
    return round(series[-1][1] - base, 4) if base else None


def exposures(me: dict, algo: dict, janus: dict) -> dict:
    """Signed exposures by country and by currency across the books (in % of each book's own capital: notional for
    the algorithm and Janus, % at risk for my decisions), flagging any country or currency held by more than one book."""
    items = []
    for p in me["positions"]:
        if p["status"] == "open" and p["action"] in ("Buy", "Sell"):
            items.append({"book": "me", "id": p["id"], "instrument": p["mark_instrument"] or p["instrument"],
                          "country": p["country"], "currency": p["currency"],
                          "direction": p["direction"], "measure": "% at risk", "value": p["size_pct"]})
    reg = {r["instrument"]: r for r in load_registry()}
    for v in algo["versions"]:
        src = v["estimate"]["positions"] if v.get("estimate") else []
        for p in src:
            r = reg.get(p["instrument"], {})
            items.append({"book": f"algorithm {v['id']}", "id": p["instrument"], "instrument": p["instrument"],
                          "country": p["country"], "currency": p["instrument"] if r.get("kind") == "fx" else None,
                          "direction": p["side"], "measure": "% notional", "value": abs(p["size_pct"] or 0)})
    for p in janus["summary"]["open"]:
        r = reg.get(p["instrument"], {})
        items.append({"book": "janus", "id": p["id"], "instrument": p["instrument"], "country": p["country"],
                      "currency": p["instrument"] if r.get("kind") == "fx" else None, "direction": p["direction"],
                      "measure": "% notional", "value": round(100 * ((p.get("fill") or {}).get("notional_frac") or 0), 2)})

    def agg(key):
        g: dict[str, dict] = {}
        for it in items:
            k = it.get(key)
            if not k:
                continue
            row = g.setdefault(k, {"key": k, "books": {}, "items": []})
            sgn = -1 if str(it["direction"]).lower() in ("short", "sell") else 1
            row["books"][it["book"]] = round(row["books"].get(it["book"], 0) + sgn * (it["value"] or 0), 3)
            row["items"].append(f"{it['book']}: {it['direction']} {it['instrument']}")
        out = []
        for row in g.values():
            owners = {b.split(" ")[0] for b in row["books"]}
            row["shared"] = len(owners) > 1
            signs = {1 if v > 0 else -1 for v in row["books"].values() if v}
            row["opposed"] = row["shared"] and len(signs) > 1
            out.append(row)
        return sorted(out, key=lambda r: (not r["shared"], r["key"]))
    return {"items": items, "by_country": agg("country"), "by_currency": agg("currency"),
            "note": ("Exposure per book in % of that book's own capital: notional for the algorithm and Janus (signed: + long, "
                     "− short), % of account at risk for my decisions. Currency exposure counts FX positions only; local "
                     "bonds are rates exposure in the algorithm's excess-return model. 'Shared' marks a country or currency held "
                     "by more than one book (v1.0 and v1.1 count as one book).")}


def comparison(me: dict, algo: dict, janus: dict, mb: MarkBook, today: date) -> dict:
    starts = [parse_date(b["live_start"]) for b in (me, algo, janus) if b.get("live_start")]
    first = min(starts) if starts else today
    cash = cash_index(mb, first, today)
    vs_cash = {}
    for b in (me, algo, janus):
        if b.get("live_start") and b.get("series"):
            c = cash_index(mb, parse_date(b["live_start"]), today)
            tot = total_return(b["series"], mb)
            vs_cash[b["id"]] = {"book_pct": round(b["series"][-1][1] - 100, 4), "cash_pct": round(c[-1][1] - 100, 4),
                                "total_pct": round(tot[-1][1] - 100, 4) if tot else None}
    return {"cash": cash, "vs_cash": vs_cash,
            "note": "Each book starts at 100 on its own live start; cash (3-month US T-bill, FRED DTB3) at 100 on the earliest."}


# ----------------------------------------------------------------------------- collateral interest (display only)
TBILL_NOTE = ("Total return = excess return + collateral interest: the book's capital is assumed to earn the 3-month "
              "US T-bill rate (FRED DTB3) on its full account value, as a fully collateralised futures and FX fund "
              "would. Interest accrues daily (actual/365) at the latest daily T-bill rate and compounds with the "
              "book's daily excess return. Display only: every evaluation (trials, Sharpe ratios, drawdown tests, the "
              "Fund's allocation rule, live-versus-backtest comparisons) uses excess returns, and no recorded P&L "
              "row changes.")


def _cash_factors(mb: MarkBook, start: date, end: date) -> dict[date, float]:
    """Cumulative T-bill accrual factor on each business day from ``start`` (1.0 at start)."""
    out, f = {}, 1.0
    days = bdays(start, end)
    if not days:
        return {start: 1.0}
    out[days[0]] = 1.0
    for a, b in zip(days, days[1:]):
        lv = mb.on("USDCASH", a) or next(iter(mb.series("USDCASH")), None)
        if lv:
            f *= 1 + lv[1] / 100.0 * (b - a).days / 365.0
        out[b] = f
    return out


def _factor_on(fac: dict[date, float], d: date) -> float:
    best = 1.0
    for k in sorted(fac):
        if k <= d:
            best = fac[k]
        else:
            break
    return best


def total_return(series: list[list], mb: MarkBook) -> list[list]:
    """[[date, total-return index]] from an excess-return index [[date, index, ...]]: on each step the excess return
    of the index plus the T-bill interest accrued over the same days on the full account value, compounded."""
    pts = [(parse_date(p[0]), float(p[1])) for p in series if parse_date(p[0]) and p[1] is not None]
    if not pts:
        return []
    fac = _cash_factors(mb, pts[0][0], pts[-1][0])
    tr, out = pts[0][1], [[pts[0][0].isoformat(), round(pts[0][1], 4)]]
    for (a, ea), (b, eb) in zip(pts, pts[1:]):
        r = eb / ea - 1 if ea else 0.0
        i = _factor_on(fac, b) / _factor_on(fac, a) - 1
        tr *= 1 + r + i
        out.append([b.isoformat(), round(tr, 4)])
    return out


def monthly_with_tbill(series: list[list], total: list[list]) -> list[dict]:
    """Per calendar month: excess return, T-bill interest and total return, in %, from the two indices (each month
    measured from the previous month's last point, the first from the index start)."""
    def month_ends(ser):
        out = {}
        for p in ser:
            out[str(p[0])[:7]] = float(p[1])
        return out
    ex, tt = month_ends(series), month_ends(total)
    rows, pe, pt = [], (float(series[0][1]) if series else None), (float(total[0][1]) if total else None)
    for m in sorted(ex):
        if m not in tt or not pe or not pt:
            continue
        e, t = ex[m] / pe - 1, tt[m] / pt - 1
        rows.append({"month": m, "excess_pct": round(100 * e, 4), "total_pct": round(100 * t, 4),
                     "tbill_pct": round(100 * ((1 + t) / (1 + e) - 1) if e > -1 else 0.0, 4)})
        pe, pt = ex[m], tt[m]
    return rows


def add_total_return(obj: dict, mb: MarkBook, today: date, series_key: str = "series") -> dict:
    """Adds total_series, total_mtd_pct, total_since_start_pct, monthly (excess, T-bill, total) and the note to a
    book-like dict with an excess index ``series_key``. Nothing else in ``obj`` changes."""
    ser = obj.get(series_key) or []
    tot = total_return(ser, mb)
    obj["total_series"] = tot
    obj["total_mtd_pct"] = mtd(tot, today) if tot else None
    obj["total_since_start_pct"] = round(tot[-1][1] - tot[0][1], 4) if tot else None
    obj["excess_since_start_pct"] = round(float(ser[-1][1]) - float(ser[0][1]), 4) if ser else None
    obj["monthly_tbill"] = monthly_with_tbill(ser, tot) if tot else []
    obj["tbill_note"] = TBILL_NOTE
    return obj


def build_books(today: date, alg: dict) -> dict:
    mb = MarkBook()
    me, algo, janus = me_book(today, mb), algo_book(alg, mb, today), janus_book(today, mb)
    for b in (me, janus):
        b["mtd_pct"] = mtd(b["series"], today)
    # collateral interest, display only: computed from each book's excess index and never fed back into it
    for b in (me, janus, algo):
        add_total_return(b, mb, today)
    for v in algo["versions"]:
        add_total_return(v, mb, today)
    me["attribution"] = {"country": group([p for p in me["positions"] if p.get("live_pnl_pct") is not None],
                                          "country", "live_pnl_pct"),
                         "asset_class": group([p for p in me["positions"] if p.get("live_pnl_pct") is not None],
                                              "asset_class", "live_pnl_pct")}
    jpos = [p for p in janus["summary"]["positions"] if p.get("net_pnl_pct") is not None]
    janus["attribution"] = {"country": group(jpos, "country", "net_pnl_pct"),
                            "asset_class": group(jpos, "asset_class", "net_pnl_pct")}
    return {"me": me, "algorithm": algo, "janus": janus, "exposures": exposures(me, algo, janus),
            "comparison": comparison(me, algo, janus, mb, today), "as_of": today.isoformat(),
            "latest_mark": max((r.get("date") or "" for r in mb.rows if r.get("value")), default=None),
            "latest_fetch": max((r.get("fetched_at") or "" for r in mb.rows if r.get("value")), default=None)}
